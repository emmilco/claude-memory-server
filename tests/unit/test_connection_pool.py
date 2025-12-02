"""Unit tests for Qdrant connection pooling.

Tests cover:
- Pool initialization
- Connection acquisition/release
- Pool size limits
- Timeout handling
- Connection recycling
- Statistics tracking
- Error handling

PERF-007: Connection Pooling for Qdrant
"""

import pytest
import asyncio
from datetime import datetime, timedelta, UTC
from unittest.mock import Mock, patch, AsyncMock

from qdrant_client import QdrantClient

from src.store.connection_pool import (
    QdrantConnectionPool,
    PooledConnection,
    ConnectionPoolExhaustedError,
)
from src.config import ServerConfig
from src.core.exceptions import QdrantConnectionError


@pytest.fixture
def mock_config():
    """Create a mock ServerConfig."""
    config = Mock(spec=ServerConfig)
    config.qdrant_url = "http://localhost:6333"
    config.qdrant_api_key = None
    config.qdrant_prefer_grpc = False
    return config


@pytest.fixture
def mock_qdrant_client():
    """Create a mock QdrantClient."""
    client = Mock(spec=QdrantClient)
    client.get_collections.return_value = Mock(collections=[])
    client.close = Mock()
    return client


class TestConnectionPoolInitialization:
    """Test connection pool initialization."""

    def test_pool_creation_valid_params(self, mock_config):
        """Test pool creation with valid parameters."""
        pool = QdrantConnectionPool(
            config=mock_config,
            min_size=2,
            max_size=10,
            timeout=5.0,
            recycle=3600,
        )

        assert pool.min_size == 2
        assert pool.max_size == 10
        assert pool.timeout == 5.0
        assert pool.recycle == 3600
        assert not pool._initialized
        assert not pool._closed

    def test_pool_creation_invalid_min_size(self, mock_config):
        """Test pool creation with invalid min_size."""
        with pytest.raises(ValueError, match="min_size must be >= 0"):
            QdrantConnectionPool(config=mock_config, min_size=-1, max_size=5)

    def test_pool_creation_invalid_max_size(self, mock_config):
        """Test pool creation with invalid max_size."""
        with pytest.raises(ValueError, match="max_size must be >= 1"):
            QdrantConnectionPool(config=mock_config, min_size=0, max_size=0)

    def test_pool_creation_min_exceeds_max(self, mock_config):
        """Test pool creation when min_size > max_size."""
        with pytest.raises(ValueError, match="cannot exceed max_size"):
            QdrantConnectionPool(config=mock_config, min_size=10, max_size=5)

    def test_pool_creation_invalid_timeout(self, mock_config):
        """Test pool creation with invalid timeout."""
        with pytest.raises(ValueError, match="timeout must be > 0"):
            QdrantConnectionPool(config=mock_config, timeout=0)

    def test_pool_creation_invalid_recycle(self, mock_config):
        """Test pool creation with invalid recycle time."""
        with pytest.raises(ValueError, match="recycle must be > 0"):
            QdrantConnectionPool(config=mock_config, recycle=-100)

    @pytest.mark.asyncio
    async def test_pool_initialize_success(self, mock_config, mock_qdrant_client):
        """Test successful pool initialization."""
        pool = QdrantConnectionPool(
            config=mock_config, min_size=2, max_size=5, enable_health_checks=False
        )

        with patch(
            "src.store.connection_pool.QdrantClient", return_value=mock_qdrant_client
        ):
            await pool.initialize()

            assert pool._initialized
            assert pool._pool.qsize() == 2
            assert pool._created_count == 2

    @pytest.mark.asyncio
    async def test_pool_initialize_already_initialized(
        self, mock_config, mock_qdrant_client
    ):
        """Test initializing an already initialized pool."""
        pool = QdrantConnectionPool(
            config=mock_config, min_size=2, max_size=5, enable_health_checks=False
        )

        with patch(
            "src.store.connection_pool.QdrantClient", return_value=mock_qdrant_client
        ):
            await pool.initialize()
            initial_count = pool._created_count

            # Try to initialize again
            await pool.initialize()

            # Should not create more connections
            assert pool._created_count == initial_count

    @pytest.mark.asyncio
    async def test_pool_initialize_connection_failure(self, mock_config):
        """Test pool initialization when connection creation fails."""
        pool = QdrantConnectionPool(
            config=mock_config, min_size=2, max_size=5, enable_health_checks=False
        )

        failing_client = Mock(spec=QdrantClient)
        failing_client.get_collections.side_effect = ConnectionError(
            "Connection refused"
        )

        with patch(
            "src.store.connection_pool.QdrantClient", return_value=failing_client
        ):
            with pytest.raises(QdrantConnectionError):
                await pool.initialize()

            assert not pool._initialized
            assert pool._closed  # Should be cleaned up


class TestConnectionAcquisition:
    """Test connection acquisition from pool."""

    @pytest.mark.asyncio
    async def test_acquire_from_initialized_pool(self, mock_config, mock_qdrant_client):
        """Test acquiring connection from initialized pool."""
        pool = QdrantConnectionPool(
            config=mock_config, min_size=2, max_size=5, enable_health_checks=False
        )

        with patch(
            "src.store.connection_pool.QdrantClient", return_value=mock_qdrant_client
        ):
            await pool.initialize()

            client = await pool.acquire()

            assert client is not None
            assert pool._active_connections == 1
            assert pool._pool.qsize() == 1  # One consumed, one remains

    @pytest.mark.asyncio
    async def test_acquire_from_uninitialized_pool(self, mock_config):
        """Test acquiring from uninitialized pool raises error."""
        pool = QdrantConnectionPool(
            config=mock_config, min_size=2, max_size=5, enable_health_checks=False
        )

        with pytest.raises(RuntimeError, match="Pool not initialized"):
            await pool.acquire()

    @pytest.mark.asyncio
    async def test_acquire_from_closed_pool(self, mock_config, mock_qdrant_client):
        """Test acquiring from closed pool raises error."""
        pool = QdrantConnectionPool(
            config=mock_config, min_size=2, max_size=5, enable_health_checks=False
        )

        with patch(
            "src.store.connection_pool.QdrantClient", return_value=mock_qdrant_client
        ):
            await pool.initialize()
            await pool.close()

            with pytest.raises(RuntimeError, match="Pool is closed"):
                await pool.acquire()

    @pytest.mark.asyncio
    async def test_acquire_creates_new_when_pool_empty(
        self, mock_config, mock_qdrant_client
    ):
        """Test acquiring creates new connection when pool is empty but under max."""
        pool = QdrantConnectionPool(
            config=mock_config,
            min_size=1,
            max_size=5,
            timeout=0.5,
            enable_health_checks=False,
        )

        with patch(
            "src.store.connection_pool.QdrantClient", return_value=mock_qdrant_client
        ):
            await pool.initialize()

            # Acquire all initial connections
            await pool.acquire()

            # Pool is now empty, should create new connection
            client2 = await pool.acquire()

            assert client2 is not None
            assert pool._active_connections == 2
            assert pool._created_count == 2

    @pytest.mark.asyncio
    async def test_acquire_timeout_when_pool_exhausted(
        self, mock_config, mock_qdrant_client
    ):
        """Test acquire times out when pool is exhausted."""
        pool = QdrantConnectionPool(
            config=mock_config,
            min_size=1,
            max_size=1,
            timeout=0.5,
            enable_health_checks=False,
        )

        with patch(
            "src.store.connection_pool.QdrantClient", return_value=mock_qdrant_client
        ):
            await pool.initialize()

            # Acquire the only connection
            await pool.acquire()

            # Try to acquire again - should timeout
            with pytest.raises(ConnectionPoolExhaustedError, match="pool exhausted"):
                await pool.acquire()

    @pytest.mark.asyncio
    async def test_acquire_concurrent_requests(self, mock_config, mock_qdrant_client):
        """Test concurrent acquisition from pool."""
        pool = QdrantConnectionPool(
            config=mock_config, min_size=5, max_size=10, enable_health_checks=False
        )

        with patch(
            "src.store.connection_pool.QdrantClient", return_value=mock_qdrant_client
        ):
            await pool.initialize()

            # Acquire 5 connections concurrently
            clients = await asyncio.gather(*[pool.acquire() for _ in range(5)])

            assert len(clients) == 5
            assert pool._active_connections == 5

    @pytest.mark.asyncio
    async def test_acquire_updates_stats(self, mock_config, mock_qdrant_client):
        """Test that acquire updates pool statistics."""
        pool = QdrantConnectionPool(
            config=mock_config, min_size=2, max_size=5, enable_health_checks=False
        )

        with patch(
            "src.store.connection_pool.QdrantClient", return_value=mock_qdrant_client
        ):
            await pool.initialize()

            initial_acquires = pool._stats.total_acquires

            await pool.acquire()

            assert pool._stats.total_acquires == initial_acquires + 1
            assert pool._stats.active_connections == 1
            assert pool._stats.avg_acquire_time_ms > 0


class TestConnectionRelease:
    """Test connection release back to pool."""

    @pytest.mark.asyncio
    async def test_release_to_pool(self, mock_config, mock_qdrant_client):
        """Test releasing connection back to pool."""
        pool = QdrantConnectionPool(
            config=mock_config, min_size=2, max_size=5, enable_health_checks=False
        )

        with patch(
            "src.store.connection_pool.QdrantClient", return_value=mock_qdrant_client
        ):
            await pool.initialize()

            client = await pool.acquire()
            initial_idle = pool._pool.qsize()

            await pool.release(client)

            assert pool._active_connections == 0
            assert pool._pool.qsize() == initial_idle + 1

    @pytest.mark.asyncio
    async def test_release_updates_stats(self, mock_config, mock_qdrant_client):
        """Test that release updates pool statistics."""
        pool = QdrantConnectionPool(
            config=mock_config, min_size=2, max_size=5, enable_health_checks=False
        )

        with patch(
            "src.store.connection_pool.QdrantClient", return_value=mock_qdrant_client
        ):
            await pool.initialize()

            client = await pool.acquire()
            initial_releases = pool._stats.total_releases

            await pool.release(client)

            assert pool._stats.total_releases == initial_releases + 1

    @pytest.mark.asyncio
    async def test_release_to_closed_pool(self, mock_config, mock_qdrant_client):
        """Test releasing to closed pool (should not raise)."""
        pool = QdrantConnectionPool(
            config=mock_config, min_size=2, max_size=5, enable_health_checks=False
        )

        with patch(
            "src.store.connection_pool.QdrantClient", return_value=mock_qdrant_client
        ):
            await pool.initialize()
            client = await pool.acquire()
            await pool.close()

            # Should not raise
            await pool.release(client)

    @pytest.mark.asyncio
    async def test_acquire_release_cycle(self, mock_config, mock_qdrant_client):
        """Test multiple acquire/release cycles."""
        pool = QdrantConnectionPool(
            config=mock_config, min_size=2, max_size=5, enable_health_checks=False
        )

        with patch(
            "src.store.connection_pool.QdrantClient", return_value=mock_qdrant_client
        ):
            await pool.initialize()

            for i in range(10):
                client = await pool.acquire()
                assert pool._active_connections == 1

                await pool.release(client)
                assert pool._active_connections == 0

            # Should have reused connections
            assert pool._stats.total_acquires == 10
            assert pool._stats.total_releases == 10


class TestConnectionRecycling:
    """Test connection recycling based on age."""

    def test_should_recycle_old_connection(self, mock_config):
        """Test that old connections are marked for recycling."""
        pool = QdrantConnectionPool(config=mock_config, recycle=10)

        # Create connection older than recycle threshold
        old_time = datetime.now(UTC) - timedelta(seconds=15)
        pooled_conn = PooledConnection(
            client=Mock(),
            created_at=old_time,
            last_used=datetime.now(UTC),
        )

        assert pool._should_recycle(pooled_conn)

    def test_should_not_recycle_new_connection(self, mock_config):
        """Test that new connections are not recycled."""
        pool = QdrantConnectionPool(config=mock_config, recycle=3600)

        # Create recent connection
        pooled_conn = PooledConnection(
            client=Mock(),
            created_at=datetime.now(UTC),
            last_used=datetime.now(UTC),
        )

        assert not pool._should_recycle(pooled_conn)

    @pytest.mark.asyncio
    async def test_acquire_recycles_old_connection(
        self, mock_config, mock_qdrant_client
    ):
        """Test that acquire recycles old connections."""
        pool = QdrantConnectionPool(
            config=mock_config,
            min_size=1,
            max_size=5,
            recycle=1,
            enable_health_checks=False,
        )

        with patch(
            "src.store.connection_pool.QdrantClient", return_value=mock_qdrant_client
        ):
            await pool.initialize()

            # Wait for connection to age
            await asyncio.sleep(1.5)

            # Acquire should trigger recycling
            initial_recycled = pool._stats.connections_recycled
            await pool.acquire()

            assert pool._stats.connections_recycled == initial_recycled + 1

    @pytest.mark.asyncio
    async def test_recycle_connection_closes_client(self, mock_config):
        """Test that recycling closes the client."""
        pool = QdrantConnectionPool(config=mock_config)

        mock_client = Mock(spec=QdrantClient)
        pooled_conn = PooledConnection(
            client=mock_client,
            created_at=datetime.now(UTC),
            last_used=datetime.now(UTC),
        )

        await pool._recycle_connection(pooled_conn)

        mock_client.close.assert_called_once()


class TestPoolClosure:
    """Test pool shutdown and cleanup."""

    @pytest.mark.asyncio
    async def test_close_pool(self, mock_config, mock_qdrant_client):
        """Test closing the pool."""
        pool = QdrantConnectionPool(
            config=mock_config, min_size=3, max_size=5, enable_health_checks=False
        )

        with patch(
            "src.store.connection_pool.QdrantClient", return_value=mock_qdrant_client
        ):
            await pool.initialize()
            await pool.close()

            assert pool._closed
            assert pool._pool.qsize() == 0
            assert pool._active_connections == 0

    @pytest.mark.asyncio
    async def test_close_already_closed_pool(self, mock_config, mock_qdrant_client):
        """Test closing an already closed pool (should be idempotent)."""
        pool = QdrantConnectionPool(
            config=mock_config, min_size=2, max_size=5, enable_health_checks=False
        )

        with patch(
            "src.store.connection_pool.QdrantClient", return_value=mock_qdrant_client
        ):
            await pool.initialize()
            await pool.close()
            await pool.close()  # Should not raise

            assert pool._closed

    @pytest.mark.asyncio
    async def test_close_calls_client_close(self, mock_config, mock_qdrant_client):
        """Test that close calls close on all clients."""
        pool = QdrantConnectionPool(
            config=mock_config, min_size=2, max_size=5, enable_health_checks=False
        )

        with patch(
            "src.store.connection_pool.QdrantClient", return_value=mock_qdrant_client
        ):
            await pool.initialize()

            # Reset call count
            mock_qdrant_client.close.reset_mock()

            await pool.close()

            # Should have called close for each connection in pool
            assert mock_qdrant_client.close.call_count == 2


class TestPoolStatistics:
    """Test pool statistics collection."""

    @pytest.mark.asyncio
    async def test_stats_initial_state(self, mock_config):
        """Test statistics in initial state."""
        pool = QdrantConnectionPool(config=mock_config, min_size=2, max_size=5)

        stats = pool.stats()

        assert stats.pool_size == 0
        assert stats.active_connections == 0
        assert stats.idle_connections == 0
        assert stats.total_acquires == 0
        assert stats.total_releases == 0

    @pytest.mark.asyncio
    async def test_stats_after_operations(self, mock_config, mock_qdrant_client):
        """Test statistics after pool operations."""
        pool = QdrantConnectionPool(
            config=mock_config, min_size=2, max_size=5, enable_health_checks=False
        )

        with patch(
            "src.store.connection_pool.QdrantClient", return_value=mock_qdrant_client
        ):
            await pool.initialize()

            client1 = await pool.acquire()
            await pool.acquire()
            await pool.release(client1)

            stats = pool.stats()

            assert stats.pool_size == 2
            assert stats.active_connections == 1
            assert stats.idle_connections == 1
            assert stats.total_acquires == 2
            assert stats.total_releases == 1
            assert stats.connections_created == 2

    @pytest.mark.asyncio
    async def test_stats_acquire_time_tracking(self, mock_config, mock_qdrant_client):
        """Test that acquire time statistics are tracked."""
        pool = QdrantConnectionPool(
            config=mock_config, min_size=2, max_size=5, enable_health_checks=False
        )

        with patch(
            "src.store.connection_pool.QdrantClient", return_value=mock_qdrant_client
        ):
            await pool.initialize()

            # Perform some acquires
            for _ in range(5):
                client = await pool.acquire()
                await pool.release(client)

            stats = pool.stats()

            assert stats.avg_acquire_time_ms > 0
            assert stats.max_acquire_time_ms > 0
            assert stats.p95_acquire_time_ms > 0

    @pytest.mark.asyncio
    async def test_stats_limits_history_size(self, mock_config, mock_qdrant_client):
        """Test that acquire time history is limited to prevent memory growth."""
        pool = QdrantConnectionPool(
            config=mock_config, min_size=2, max_size=5, enable_health_checks=False
        )

        with patch(
            "src.store.connection_pool.QdrantClient", return_value=mock_qdrant_client
        ):
            await pool.initialize()

            # Perform many acquires
            for _ in range(1500):
                client = await pool.acquire()
                await pool.release(client)

            # History should be capped at 1000
            assert len(pool._acquire_times) <= 1000


class TestPooledConnection:
    """Test PooledConnection wrapper class."""

    def test_pooled_connection_creation(self):
        """Test creating a PooledConnection."""
        mock_client = Mock(spec=QdrantClient)
        now = datetime.now(UTC)

        pooled_conn = PooledConnection(
            client=mock_client,
            created_at=now,
            last_used=now,
        )

        assert pooled_conn.client == mock_client
        assert pooled_conn.created_at == now
        assert pooled_conn.last_used == now
        assert pooled_conn.use_count == 0

    def test_pooled_connection_use_tracking(self):
        """Test tracking connection usage."""
        pooled_conn = PooledConnection(
            client=Mock(),
            created_at=datetime.now(UTC),
            last_used=datetime.now(UTC),
        )

        pooled_conn.use_count += 1
        pooled_conn.use_count += 1

        assert pooled_conn.use_count == 2


class TestHealthCheckingIntegration:
    """Test health checking integration in connection pool.

    PERF-007: Day 2 - Health Checking
    """

    @pytest.mark.asyncio
    async def test_pool_with_health_checks_enabled(
        self, mock_config, mock_qdrant_client
    ):
        """Test pool with health checking enabled."""
        pool = QdrantConnectionPool(
            config=mock_config,
            min_size=1,
            max_size=3,
            enable_health_checks=True,
        )

        with patch(
            "src.store.connection_pool.QdrantClient", return_value=mock_qdrant_client
        ):
            await pool.initialize()

            assert pool._health_checker is not None
            assert pool.enable_health_checks is True

            await pool.close()

    @pytest.mark.asyncio
    async def test_pool_with_health_checks_disabled(
        self, mock_config, mock_qdrant_client
    ):
        """Test pool with health checking disabled."""
        pool = QdrantConnectionPool(
            config=mock_config,
            min_size=1,
            max_size=3,
            enable_health_checks=False,
        )

        with patch(
            "src.store.connection_pool.QdrantClient", return_value=mock_qdrant_client
        ):
            await pool.initialize()

            assert pool._health_checker is None
            assert pool.enable_health_checks is False

            await pool.close()

    @pytest.mark.asyncio
    async def test_acquire_performs_health_check(self, mock_config, mock_qdrant_client):
        """Test that acquire performs health check on connection."""
        pool = QdrantConnectionPool(
            config=mock_config,
            min_size=1,
            max_size=3,
            enable_health_checks=True,
        )

        with patch(
            "src.store.connection_pool.QdrantClient", return_value=mock_qdrant_client
        ):
            await pool.initialize()

            # Mock health checker
            pool._health_checker.check_health = AsyncMock(
                return_value=Mock(healthy=True, duration_ms=0.5)
            )

            client = await pool.acquire()

            # Health check should have been called
            pool._health_checker.check_health.assert_called_once()

            await pool.release(client)
            await pool.close()

    @pytest.mark.asyncio
    async def test_acquire_replaces_unhealthy_connection(
        self, mock_config, mock_qdrant_client
    ):
        """Test that acquire replaces unhealthy connections."""
        pool = QdrantConnectionPool(
            config=mock_config,
            min_size=1,
            max_size=3,
            enable_health_checks=True,
        )

        with patch(
            "src.store.connection_pool.QdrantClient", return_value=mock_qdrant_client
        ):
            await pool.initialize()

            # Mock health checker to return unhealthy first, then healthy
            health_results = [
                Mock(healthy=False, duration_ms=0.5, error="Connection failed"),
                Mock(healthy=True, duration_ms=0.5),
            ]
            pool._health_checker.check_health = AsyncMock(side_effect=health_results)

            # Track initial stats
            initial_failures = pool.stats().total_health_failures

            client = await pool.acquire()

            # Should have replaced unhealthy connection
            assert pool.stats().total_health_failures > initial_failures

            await pool.release(client)
            await pool.close()

    @pytest.mark.asyncio
    async def test_get_health_stats(self, mock_config, mock_qdrant_client):
        """Test getting health checker statistics."""
        pool = QdrantConnectionPool(
            config=mock_config,
            min_size=1,
            max_size=3,
            enable_health_checks=True,
        )

        with patch(
            "src.store.connection_pool.QdrantClient", return_value=mock_qdrant_client
        ):
            await pool.initialize()

            stats = pool.get_health_stats()

            assert stats is not None
            assert "total_checks" in stats
            assert "total_failures" in stats

            await pool.close()

    @pytest.mark.asyncio
    async def test_get_health_stats_disabled(self, mock_config, mock_qdrant_client):
        """Test getting health stats when health checking is disabled."""
        pool = QdrantConnectionPool(
            config=mock_config,
            min_size=1,
            max_size=3,
            enable_health_checks=False,
        )

        with patch(
            "src.store.connection_pool.QdrantClient", return_value=mock_qdrant_client
        ):
            await pool.initialize()

            stats = pool.get_health_stats()
            assert stats is None

            await pool.close()


class TestMonitoringIntegration:
    """Test monitoring integration in connection pool.

    PERF-007: Day 2 - Monitoring
    """

    @pytest.mark.asyncio
    async def test_pool_with_monitoring_enabled(self, mock_config, mock_qdrant_client):
        """Test pool with monitoring enabled."""
        pool = QdrantConnectionPool(
            config=mock_config,
            min_size=1,
            max_size=3,
            enable_monitoring=True,
        )

        with patch(
            "src.store.connection_pool.QdrantClient", return_value=mock_qdrant_client
        ):
            await pool.initialize()

            assert pool._monitor is not None
            assert pool.enable_monitoring is True
            assert pool._monitor._running is True

            await pool.close()

    @pytest.mark.asyncio
    async def test_pool_with_monitoring_disabled(self, mock_config, mock_qdrant_client):
        """Test pool with monitoring disabled."""
        pool = QdrantConnectionPool(
            config=mock_config,
            min_size=1,
            max_size=3,
            enable_monitoring=False,
        )

        with patch(
            "src.store.connection_pool.QdrantClient", return_value=mock_qdrant_client
        ):
            await pool.initialize()

            assert pool._monitor is None
            assert pool.enable_monitoring is False

            await pool.close()

    @pytest.mark.asyncio
    async def test_monitoring_stops_on_close(self, mock_config, mock_qdrant_client):
        """Test that monitoring stops when pool is closed."""
        pool = QdrantConnectionPool(
            config=mock_config,
            min_size=1,
            max_size=3,
            enable_monitoring=True,
        )

        with patch(
            "src.store.connection_pool.QdrantClient", return_value=mock_qdrant_client
        ):
            await pool.initialize()

            assert pool._monitor._running is True

            await pool.close()

            assert pool._monitor._running is False

    @pytest.mark.asyncio
    async def test_get_monitor_stats(self, mock_config, mock_qdrant_client):
        """Test getting monitor statistics."""
        pool = QdrantConnectionPool(
            config=mock_config,
            min_size=1,
            max_size=3,
            enable_monitoring=True,
        )

        with patch(
            "src.store.connection_pool.QdrantClient", return_value=mock_qdrant_client
        ):
            await pool.initialize()

            stats = pool.get_monitor_stats()

            assert stats is not None
            assert "running" in stats
            assert "total_collections" in stats

            await pool.close()

    @pytest.mark.asyncio
    async def test_get_monitor_instance(self, mock_config, mock_qdrant_client):
        """Test getting monitor instance."""
        pool = QdrantConnectionPool(
            config=mock_config,
            min_size=1,
            max_size=3,
            enable_monitoring=True,
        )

        with patch(
            "src.store.connection_pool.QdrantClient", return_value=mock_qdrant_client
        ):
            await pool.initialize()

            monitor = pool.get_monitor()

            assert monitor is not None
            assert monitor == pool._monitor

            await pool.close()


class TestBUG037ClientTracking:
    """Test BUG-037 fix: client -> PooledConnection tracking.

    BUG-037: Connection pool state corruption after Qdrant restart
    """

    @pytest.mark.asyncio
    async def test_client_map_populated_on_acquire(
        self, mock_config, mock_qdrant_client
    ):
        """Test that client mapping is populated when connection is acquired."""
        pool = QdrantConnectionPool(
            config=mock_config, min_size=1, max_size=3, enable_health_checks=False
        )

        with patch(
            "src.store.connection_pool.QdrantClient", return_value=mock_qdrant_client
        ):
            await pool.initialize()

            # Initially empty
            assert len(pool._client_map) == 0

            # Acquire connection
            client = await pool.acquire()

            # Client should be in map
            assert len(pool._client_map) == 1
            assert id(client) in pool._client_map

            await pool.release(client)
            await pool.close()

    @pytest.mark.asyncio
    async def test_client_map_cleared_on_release(self, mock_config, mock_qdrant_client):
        """Test that client is removed from map on release."""
        pool = QdrantConnectionPool(
            config=mock_config, min_size=1, max_size=3, enable_health_checks=False
        )

        with patch(
            "src.store.connection_pool.QdrantClient", return_value=mock_qdrant_client
        ):
            await pool.initialize()

            client = await pool.acquire()
            client_id = id(client)
            assert client_id in pool._client_map

            await pool.release(client)

            # Client should be removed from map
            assert client_id not in pool._client_map

            await pool.close()

    @pytest.mark.asyncio
    async def test_release_preserves_original_created_at(
        self, mock_config, mock_qdrant_client
    ):
        """Test that release preserves original PooledConnection metadata."""
        pool = QdrantConnectionPool(
            config=mock_config, min_size=1, max_size=3, enable_health_checks=False
        )

        with patch(
            "src.store.connection_pool.QdrantClient", return_value=mock_qdrant_client
        ):
            await pool.initialize()

            # Get initial connection and record its created_at
            client = await pool.acquire()
            original_pooled = pool._client_map[id(client)]
            original_created_at = original_pooled.created_at

            await pool.release(client)

            # Re-acquire (should get same connection from pool)
            client2 = await pool.acquire()
            new_pooled = pool._client_map[id(client2)]

            # created_at should be preserved (not reset to now)
            assert new_pooled.created_at == original_created_at

            await pool.release(client2)
            await pool.close()

    @pytest.mark.asyncio
    async def test_multiple_concurrent_acquires_tracked(self, mock_config):
        """Test that multiple concurrent acquires are all tracked."""
        pool = QdrantConnectionPool(
            config=mock_config, min_size=3, max_size=5, enable_health_checks=False
        )

        # Create unique mock clients for each connection
        def create_unique_client(*args, **kwargs):
            client = Mock(spec=QdrantClient)
            client.get_collections.return_value = Mock(collections=[])
            client.close = Mock()
            return client

        with patch(
            "src.store.connection_pool.QdrantClient", side_effect=create_unique_client
        ):
            await pool.initialize()

            # Acquire 3 connections (pool starts with 3, so no new creations needed)
            clients = [await pool.acquire() for _ in range(3)]

            # All should be tracked with unique IDs
            assert len(pool._client_map) == 3
            client_ids = {id(c) for c in clients}
            assert len(client_ids) == 3  # All unique
            for client in clients:
                assert id(client) in pool._client_map

            # Release all
            for client in clients:
                await pool.release(client)

            # Map should be empty
            assert len(pool._client_map) == 0

            await pool.close()


class TestBUG037PoolReset:
    """Test BUG-037 fix: pool reset for recovery from corrupted state."""

    @pytest.mark.asyncio
    async def test_reset_reinitializes_pool(self, mock_config, mock_qdrant_client):
        """Test that reset closes and reinitializes the pool."""
        pool = QdrantConnectionPool(
            config=mock_config, min_size=2, max_size=5, enable_health_checks=False
        )

        with patch(
            "src.store.connection_pool.QdrantClient", return_value=mock_qdrant_client
        ):
            await pool.initialize()
            assert pool._initialized

            # Acquire a connection to put pool in active state
            await pool.acquire()

            # Reset should close and reinitialize
            await pool.reset()

            assert pool._initialized
            assert pool._pool.qsize() == 2  # min_size connections
            assert len(pool._client_map) == 0  # tracking cleared
            assert pool._active_connections == 0

    @pytest.mark.asyncio
    async def test_reset_on_uninitialized_pool(self, mock_config, mock_qdrant_client):
        """Test reset on pool that was never initialized."""
        pool = QdrantConnectionPool(
            config=mock_config, min_size=1, max_size=3, enable_health_checks=False
        )

        with patch(
            "src.store.connection_pool.QdrantClient", return_value=mock_qdrant_client
        ):
            # Reset without initializing first
            await pool.reset()

            # Should not initialize (wasn't initialized before)
            assert not pool._initialized

    @pytest.mark.asyncio
    async def test_reset_clears_client_map(self, mock_config):
        """Test that reset clears the client tracking map."""
        pool = QdrantConnectionPool(
            config=mock_config, min_size=2, max_size=3, enable_health_checks=False
        )

        # Create unique mock clients for each connection
        def create_unique_client(*args, **kwargs):
            client = Mock(spec=QdrantClient)
            client.get_collections.return_value = Mock(collections=[])
            client.close = Mock()
            return client

        with patch(
            "src.store.connection_pool.QdrantClient", side_effect=create_unique_client
        ):
            await pool.initialize()

            # Acquire connections to populate map
            [await pool.acquire() for _ in range(2)]
            assert len(pool._client_map) == 2

            # Reset
            await pool.reset()

            # Map should be cleared
            assert len(pool._client_map) == 0


class TestBUG037PoolHealthCheck:
    """Test BUG-037 fix: pool health checking for corrupted state detection."""

    @pytest.mark.asyncio
    async def test_is_healthy_returns_true_for_healthy_pool(
        self, mock_config, mock_qdrant_client
    ):
        """Test is_healthy returns True for properly functioning pool."""
        pool = QdrantConnectionPool(
            config=mock_config, min_size=2, max_size=5, enable_health_checks=False
        )

        with patch(
            "src.store.connection_pool.QdrantClient", return_value=mock_qdrant_client
        ):
            await pool.initialize()

            assert pool.is_healthy()

            await pool.close()

    @pytest.mark.asyncio
    async def test_is_healthy_returns_false_for_closed_pool(
        self, mock_config, mock_qdrant_client
    ):
        """Test is_healthy returns False for closed pool."""
        pool = QdrantConnectionPool(
            config=mock_config, min_size=1, max_size=3, enable_health_checks=False
        )

        with patch(
            "src.store.connection_pool.QdrantClient", return_value=mock_qdrant_client
        ):
            await pool.initialize()
            await pool.close()

            assert not pool.is_healthy()

    def test_is_healthy_returns_false_for_uninitialized_pool(self, mock_config):
        """Test is_healthy returns False for uninitialized pool."""
        pool = QdrantConnectionPool(config=mock_config, min_size=1, max_size=3)

        assert not pool.is_healthy()

    @pytest.mark.asyncio
    async def test_is_healthy_detects_corrupted_state(
        self, mock_config, mock_qdrant_client
    ):
        """Test is_healthy detects pool state corruption."""
        pool = QdrantConnectionPool(
            config=mock_config, min_size=1, max_size=2, enable_health_checks=False
        )

        with patch(
            "src.store.connection_pool.QdrantClient", return_value=mock_qdrant_client
        ):
            await pool.initialize()

            # Simulate corrupted state: created_count at max, but no connections available
            # This can happen when connections fail without being properly released
            pool._created_count = pool.max_size
            # Drain the pool
            while not pool._pool.empty():
                pool._pool.get_nowait()
            # Clear client map (simulating lost connections)
            pool._client_map.clear()

            # Pool should be detected as unhealthy
            assert not pool.is_healthy()
