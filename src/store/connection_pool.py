"""Qdrant connection pooling implementation.

Provides connection pooling, health checking, and lifecycle management for QdrantClient instances.
Improves resource utilization, throughput, and reliability under concurrent load.

PERF-007: Connection Pooling for Qdrant
"""

import asyncio
import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Optional, List, Dict
from datetime import datetime, UTC
from weakref import WeakValueDictionary

from qdrant_client import QdrantClient

from src.config import ServerConfig
from src.core.exceptions import QdrantConnectionError
from src.store.connection_health_checker import (
    ConnectionHealthChecker,
    HealthCheckLevel,
    HealthCheckResult,
)
from src.store.connection_pool_monitor import ConnectionPoolMonitor

logger = logging.getLogger(__name__)


@dataclass
class PoolStats:
    """Connection pool statistics."""

    pool_size: int = 0
    active_connections: int = 0
    idle_connections: int = 0
    total_acquires: int = 0
    total_releases: int = 0
    total_timeouts: int = 0
    total_health_failures: int = 0
    connections_created: int = 0
    connections_recycled: int = 0
    connections_failed: int = 0
    avg_acquire_time_ms: float = 0.0
    p95_acquire_time_ms: float = 0.0
    max_acquire_time_ms: float = 0.0


@dataclass
class PooledConnection:
    """Wrapper for a pooled Qdrant connection."""

    client: QdrantClient
    created_at: datetime
    last_used: datetime
    use_count: int = 0


class ConnectionPoolExhaustedError(Exception):
    """Raised when connection pool is exhausted and cannot acquire a connection."""

    pass


class QdrantConnectionPool:
    """Connection pool for QdrantClient instances.

    Manages a pool of QdrantClient connections with:
    - Min/max pool sizing
    - Connection health checking
    - Age-based recycling
    - Acquisition timeout
    - Performance metrics

    Example:
        >>> pool = QdrantConnectionPool(config, min_size=2, max_size=10)
        >>> await pool.initialize()
        >>> client = await pool.acquire()
        >>> try:
        >>>     # Use client...
        >>> finally:
        >>>     await pool.release(client)
        >>> await pool.close()
    """

    def __init__(
        self,
        config: ServerConfig,
        min_size: int = 1,
        max_size: int = 5,
        timeout: float = 10.0,
        recycle: int = 3600,
        enable_health_checks: bool = True,
        enable_monitoring: bool = False,
    ):
        """
        Initialize connection pool.

        Args:
            config: Server configuration
            min_size: Minimum number of connections to maintain
            max_size: Maximum number of connections allowed
            timeout: Max seconds to wait when acquiring a connection
            recycle: Recycle connections after this many seconds
            enable_health_checks: Enable health checking on acquire (default: True)
            enable_monitoring: Enable background monitoring (default: False)
        """
        if min_size < 0:
            raise ValueError(f"min_size must be >= 0, got {min_size}")
        if max_size < 1:
            raise ValueError(f"max_size must be >= 1, got {max_size}")
        if min_size > max_size:
            raise ValueError(f"min_size ({min_size}) cannot exceed max_size ({max_size})")
        if timeout <= 0:
            raise ValueError(f"timeout must be > 0, got {timeout}")
        if recycle <= 0:
            raise ValueError(f"recycle must be > 0, got {recycle}")

        self.config = config
        self.min_size = min_size
        self.max_size = max_size
        self.timeout = timeout
        self.recycle = recycle

        # Pool storage
        self._pool: asyncio.Queue[PooledConnection] = asyncio.Queue(maxsize=max_size)
        self._active_connections: int = 0
        self._created_count: int = 0
        self._lock = asyncio.Lock()
        self._counter_lock = threading.Lock()  # REF-030: Atomic counter operations
        # BUG-037: Track client -> PooledConnection mapping for proper release()
        self._client_map: Dict[int, PooledConnection] = {}

        # Metrics
        self._stats = PoolStats()
        self._acquire_times: List[float] = []
        self._initialized = False
        self._closed = False

        # Health checking and monitoring
        self.enable_health_checks = enable_health_checks
        self.enable_monitoring = enable_monitoring
        self._health_checker: Optional[ConnectionHealthChecker] = None
        self._monitor: Optional[ConnectionPoolMonitor] = None

        if enable_health_checks:
            self._health_checker = ConnectionHealthChecker()

        if enable_monitoring:
            self._monitor = ConnectionPoolMonitor(pool=self)

        logger.info(
            f"Connection pool created: min_size={min_size}, max_size={max_size}, "
            f"timeout={timeout}s, recycle={recycle}s, health_checks={enable_health_checks}, "
            f"monitoring={enable_monitoring}"
        )

    async def initialize(self) -> None:
        """Initialize pool with min_size connections.

        Raises:
            QdrantConnectionError: If unable to create initial connections
        """
        if self._initialized:
            logger.warning("Pool already initialized, skipping")
            return

        logger.info(f"Initializing connection pool with {self.min_size} connections...")

        try:
            for i in range(self.min_size):
                pooled_conn = await self._create_connection()
                await self._pool.put(pooled_conn)
                logger.debug(f"Created initial connection {i + 1}/{self.min_size}")

            self._initialized = True
            logger.info(f"Connection pool initialized with {self.min_size} connections")

            # Start monitoring if enabled
            if self._monitor:
                await self._monitor.start()
                logger.info("Pool monitoring started")

        except Exception as e:
            logger.error(f"Failed to initialize connection pool: {e}")
            # Clean up any created connections
            await self.close()
            raise QdrantConnectionError(
                url=self.config.qdrant_url,
                reason=f"Pool initialization failed: {e}"
            )

    async def acquire(self) -> QdrantClient:
        """Acquire a connection from the pool.

        Returns:
            QdrantClient: A healthy connection from the pool

        Raises:
            ConnectionPoolExhaustedError: If pool is exhausted and timeout reached
            RuntimeError: If pool is not initialized or is closed
        """
        if self._closed:
            raise RuntimeError("Pool is closed")
        if not self._initialized:
            raise RuntimeError("Pool not initialized. Call initialize() first.")

        start_time = time.time()

        try:
            # Try to get existing connection from pool
            pooled_conn = None

            try:
                # Try to get a connection without blocking
                pooled_conn = self._pool.get_nowait()

                # Check if connection needs recycling
                if self._should_recycle(pooled_conn):
                    logger.debug("Connection needs recycling")
                    await self._recycle_connection(pooled_conn)
                    pooled_conn = await self._create_connection()
                    self._stats.connections_recycled += 1

            except asyncio.QueueEmpty:
                # Pool is empty, try to create new connection if under max
                can_create = False
                async with self._lock:
                    if self._created_count < self.max_size:
                        can_create = True

                if can_create:
                    logger.debug(
                        f"Pool empty, creating new connection "
                        f"({self._created_count + 1}/{self.max_size})"
                    )
                    pooled_conn = await self._create_connection()

            # If still no connection, wait for one to be released
            if pooled_conn is None:
                try:
                    pooled_conn = await asyncio.wait_for(
                        self._pool.get(),
                        timeout=self.timeout
                    )

                    # Check if connection needs recycling
                    if self._should_recycle(pooled_conn):
                        logger.debug("Connection needs recycling")
                        await self._recycle_connection(pooled_conn)
                        pooled_conn = await self._create_connection()
                        self._stats.connections_recycled += 1

                except asyncio.TimeoutError:
                    # Timeout waiting for connection
                    self._stats.total_timeouts += 1
                    raise ConnectionPoolExhaustedError(
                        f"Connection pool exhausted: {self._active_connections} active, "
                        f"{self.max_size} max, {self.timeout}s timeout"
                    )

            # Perform health check if enabled
            if self._health_checker:
                health_result = await self._health_checker.check_health(
                    pooled_conn.client,
                    HealthCheckLevel.FAST  # Use fast check for minimal overhead
                )

                if not health_result.healthy:
                    # Connection is unhealthy, replace it
                    logger.warning(f"Acquired unhealthy connection: {health_result}")
                    self._stats.total_health_failures += 1

                    # Recycle unhealthy connection and create new one
                    await self._recycle_connection(pooled_conn)
                    pooled_conn = await self._create_connection()

                    # Re-check new connection
                    health_result = await self._health_checker.check_health(
                        pooled_conn.client,
                        HealthCheckLevel.FAST
                    )

                    if not health_result.healthy:
                        # Even new connection is unhealthy - serious issue
                        logger.error("Newly created connection is unhealthy!")
                        raise QdrantConnectionError(
                            url=self.config.qdrant_url,
                            reason="Unable to create healthy connection"
                        )

            # Update connection stats
            pooled_conn.last_used = datetime.now(UTC)
            pooled_conn.use_count += 1

            # Track metrics
            async with self._lock:
                with self._counter_lock:  # REF-030: Atomic counter increment
                    self._active_connections += 1
                self._stats.total_acquires += 1
                self._stats.active_connections = self._active_connections
                self._stats.idle_connections = self._pool.qsize()

                duration_ms = (time.time() - start_time) * 1000
                self._acquire_times.append(duration_ms)
                self._update_acquire_stats()

            # BUG-037: Track client -> PooledConnection mapping for proper release()
            self._client_map[id(pooled_conn.client)] = pooled_conn

            logger.debug(
                f"Acquired connection (active: {self._active_connections}, "
                f"idle: {self._pool.qsize()}, acquire_time: {duration_ms:.2f}ms)"
            )

            return pooled_conn.client

        except ConnectionPoolExhaustedError:
            raise
        except Exception as e:
            logger.error(f"Failed to acquire connection: {e}")
            raise

    async def release(self, client: QdrantClient) -> None:
        """Release connection back to pool.

        Args:
            client: The QdrantClient to release

        Raises:
            RuntimeError: If pool is closed
        """
        if self._closed:
            logger.warning("Attempting to release connection to closed pool")
            return

        try:
            # BUG-037: Look up original PooledConnection to preserve metadata
            client_id = id(client)
            pooled_conn = self._client_map.pop(client_id, None)

            if pooled_conn is None:
                # Fallback: client not in map (shouldn't happen in normal operation)
                logger.warning(
                    "Released client not found in tracking map - creating new wrapper. "
                    "This may indicate a bug or the client was acquired before BUG-037 fix."
                )
                pooled_conn = PooledConnection(
                    client=client,
                    created_at=datetime.now(UTC),
                    last_used=datetime.now(UTC),
                )
            else:
                # Update last_used timestamp
                pooled_conn.last_used = datetime.now(UTC)

            # Put back in pool
            await self._pool.put(pooled_conn)

            # Update metrics
            async with self._lock:
                with self._counter_lock:  # REF-030: Atomic counter decrement
                    self._active_connections = max(0, self._active_connections - 1)
                self._stats.total_releases += 1
                self._stats.active_connections = self._active_connections
                self._stats.idle_connections = self._pool.qsize()

            logger.debug(
                f"Released connection (active: {self._active_connections}, "
                f"idle: {self._pool.qsize()})"
            )

        except Exception as e:
            logger.error(f"Failed to release connection: {e}")
            # Don't raise - connection is lost but we continue

    async def close(self) -> None:
        """Close all connections in pool and shut down."""
        if self._closed:
            logger.debug("Pool already closed")
            return

        logger.info("Closing connection pool...")
        self._closed = True

        # Stop monitoring if running
        if self._monitor:
            await self._monitor.stop()
            logger.info("Pool monitoring stopped")

        # Close any active connections tracked in client map
        for client_id, pooled_conn in list(self._client_map.items()):
            try:
                pooled_conn.client.close()
            except Exception as e:
                logger.warning(f"Error closing active connection: {e}")
        self._client_map.clear()

        # Drain and close all connections in pool queue
        closed_count = 0
        while not self._pool.empty():
            try:
                pooled_conn = await asyncio.wait_for(self._pool.get(), timeout=1.0)
                try:
                    pooled_conn.client.close()
                    closed_count += 1
                except Exception as e:
                    logger.warning(f"Error closing connection: {e}")
            except asyncio.TimeoutError:
                break

        logger.info(f"Connection pool closed ({closed_count} connections closed)")

        # Reset state
        self._active_connections = 0
        self._created_count = 0
        self._initialized = False

    async def reset(self) -> None:
        """Reset pool to recover from corrupted state.

        BUG-037: Added recovery mechanism for when pool state becomes corrupted
        (e.g., after Qdrant restart, network issues, or connection leaks).

        This closes all existing connections and reinitializes the pool.
        """
        logger.warning("Resetting connection pool to recover from corrupted state")

        # Close existing pool
        was_initialized = self._initialized
        await self.close()

        # Reset closed flag to allow reinitialization
        self._closed = False

        # Clear any stale state
        self._client_map.clear()
        self._pool = asyncio.Queue(maxsize=self.max_size)

        # Reinitialize if pool was previously initialized
        if was_initialized:
            await self.initialize()
            logger.info("Connection pool reset and reinitialized successfully")
        else:
            logger.info("Connection pool reset (not reinitialized - was not initialized before)")

    def is_healthy(self) -> bool:
        """Check if pool is in a healthy state.

        BUG-037: Added health check to detect corrupted pool state.

        Returns:
            bool: True if pool appears healthy, False if corrupted
        """
        if self._closed or not self._initialized:
            return False

        # Check for state corruption: created_count at max but nothing available
        idle_count = self._pool.qsize()
        active_count = len(self._client_map)  # More accurate than self._active_connections

        if self._created_count >= self.max_size and idle_count == 0 and active_count == 0:
            logger.warning(
                f"Pool state corruption detected: created_count={self._created_count}, "
                f"idle={idle_count}, active={active_count}, max={self.max_size}"
            )
            return False

        return True

    def stats(self) -> PoolStats:
        """Get current pool statistics.

        Returns:
            PoolStats: Current pool statistics snapshot
        """
        return PoolStats(
            pool_size=self._created_count,
            active_connections=self._active_connections,
            idle_connections=self._pool.qsize(),
            total_acquires=self._stats.total_acquires,
            total_releases=self._stats.total_releases,
            total_timeouts=self._stats.total_timeouts,
            total_health_failures=self._stats.total_health_failures,
            connections_created=self._stats.connections_created,
            connections_recycled=self._stats.connections_recycled,
            connections_failed=self._stats.connections_failed,
            avg_acquire_time_ms=self._stats.avg_acquire_time_ms,
            p95_acquire_time_ms=self._stats.p95_acquire_time_ms,
            max_acquire_time_ms=self._stats.max_acquire_time_ms,
        )

    async def _create_connection(self) -> PooledConnection:
        """Create a new Qdrant connection.

        Returns:
            PooledConnection: Newly created pooled connection

        Raises:
            QdrantConnectionError: If connection creation fails
        """
        try:
            # Create new Qdrant client
            client = QdrantClient(
                url=self.config.qdrant_url,
                api_key=self.config.qdrant_api_key,
                timeout=30.0,
                prefer_grpc=getattr(self.config, 'qdrant_prefer_grpc', False),
            )

            # BUG-066: Run blocking get_collections() in executor to prevent event loop blocking
            # QdrantClient methods are synchronous and can hang async code in pytest-asyncio
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, client.get_collections)

            # Wrap in pooled connection
            pooled_conn = PooledConnection(
                client=client,
                created_at=datetime.now(UTC),
                last_used=datetime.now(UTC),
            )

            # Update metrics
            async with self._lock:
                with self._counter_lock:  # REF-030: Atomic counter increment
                    self._created_count += 1
                self._stats.connections_created += 1
                self._stats.pool_size = self._created_count

            logger.debug(f"Created new connection (total: {self._created_count})")
            return pooled_conn

        except Exception as e:
            logger.error(f"Failed to create connection: {e}")
            raise QdrantConnectionError(
                url=self.config.qdrant_url,
                reason=f"Connection creation failed: {e}"
            )

    def _should_recycle(self, pooled_conn: PooledConnection) -> bool:
        """Check if connection should be recycled based on age.

        Args:
            pooled_conn: The pooled connection to check

        Returns:
            bool: True if connection should be recycled
        """
        age_seconds = (datetime.now(UTC) - pooled_conn.created_at).total_seconds()
        should_recycle = age_seconds >= self.recycle

        if should_recycle:
            logger.debug(
                f"Connection age {age_seconds:.1f}s exceeds recycle threshold {self.recycle}s"
            )

        return should_recycle

    async def _recycle_connection(self, pooled_conn: PooledConnection) -> None:
        """Recycle (close) an old connection.

        Args:
            pooled_conn: The pooled connection to recycle
        """
        try:
            pooled_conn.client.close()
            async with self._lock:
                self._created_count = max(0, self._created_count - 1)
                self._stats.pool_size = self._created_count
            logger.debug("Connection recycled")
        except Exception as e:
            logger.warning(f"Error recycling connection: {e}")

    def _update_acquire_stats(self) -> None:
        """Update acquire time statistics (must be called under lock)."""
        if not self._acquire_times:
            return

        # Calculate average
        self._stats.avg_acquire_time_ms = sum(self._acquire_times) / len(self._acquire_times)

        # Calculate P95
        sorted_times = sorted(self._acquire_times)
        p95_idx = int(len(sorted_times) * 0.95)
        self._stats.p95_acquire_time_ms = sorted_times[p95_idx] if sorted_times else 0.0

        # Max
        self._stats.max_acquire_time_ms = max(self._acquire_times)

        # Keep only last 1000 measurements to prevent memory growth
        if len(self._acquire_times) > 1000:
            self._acquire_times = self._acquire_times[-1000:]

    def get_health_stats(self) -> Optional[dict]:
        """Get health checker statistics.

        Returns:
            dict or None: Health check statistics if health checking is enabled
        """
        if self._health_checker:
            return self._health_checker.get_stats()
        return None

    def get_monitor_stats(self) -> Optional[dict]:
        """Get monitor statistics.

        Returns:
            dict or None: Monitor statistics if monitoring is enabled
        """
        if self._monitor:
            return self._monitor.get_stats()
        return None

    def get_monitor(self) -> Optional[ConnectionPoolMonitor]:
        """Get the pool monitor instance.

        Returns:
            ConnectionPoolMonitor or None: Monitor if enabled
        """
        return self._monitor
