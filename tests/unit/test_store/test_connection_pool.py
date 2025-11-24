"""Unit tests for QdrantConnectionPool.

Tests connection pooling functionality including:
- Pool initialization and configuration
- Connection acquire/release
- Pool exhaustion and timeout handling
- Health checking integration
- Connection recycling
- Metrics and statistics

PERF-007: Connection Pooling for Qdrant
"""

import asyncio
import pytest
from datetime import datetime, UTC, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock

from qdrant_client import QdrantClient

from src.config import ServerConfig
from src.core.exceptions import QdrantConnectionError
from src.store.connection_pool import (
    QdrantConnectionPool,
    ConnectionPoolExhaustedError,
    PooledConnection,
    PoolStats,
)
from src.store.connection_health_checker import (
    ConnectionHealthChecker,
    HealthCheckLevel,
    HealthCheckResult,
)


@pytest.fixture
def test_config():
    """Create test configuration."""
    return ServerConfig(
        qdrant_url="http://localhost:6333",
        qdrant_pool_size=5,
        qdrant_pool_min_size=1,
        qdrant_pool_timeout=2.0,
        qdrant_pool_recycle=3600,
    )


@pytest.fixture
def mock_qdrant_client():
    """Create mock QdrantClient."""
    client = Mock(spec=QdrantClient)
    client.get_collections = Mock(return_value=Mock(collections=[]))
    client.close = Mock()
    return client


class TestConnectionPoolInitialization:
    """Test connection pool initialization and configuration."""

    def test_pool_creation_with_valid_params(self, test_config):
        """Test pool creation with valid parameters."""
        pool = QdrantConnectionPool(
            config=test_config,
            min_size=2,
            max_size=10,
            timeout=5.0,
            recycle=1800,
        )

        assert pool.min_size == 2
        assert pool.max_size == 10
        assert pool.timeout == 5.0
        assert pool.recycle == 1800
        assert pool._created_count == 0
        assert pool._active_connections == 0
        assert not pool._initialized
        assert not pool._closed

    def test_pool_creation_with_invalid_min_size(self, test_config):
        """Test pool creation with invalid min_size."""
        with pytest.raises(ValueError, match="min_size must be >= 0"):
            QdrantConnectionPool(
                config=test_config,
                min_size=-1,
                max_size=5,
            )

    def test_pool_creation_with_invalid_max_size(self, test_config):
        """Test pool creation with invalid max_size."""
        with pytest.raises(ValueError, match="max_size must be >= 1"):
            QdrantConnectionPool(
                config=test_config,
                min_size=0,
                max_size=0,
            )

    def test_pool_creation_with_min_greater_than_max(self, test_config):
        """Test pool creation with min_size > max_size."""
        with pytest.raises(ValueError, match="min_size.*cannot exceed max_size"):
            QdrantConnectionPool(
                config=test_config,
                min_size=10,
                max_size=5,
            )

    def test_pool_creation_with_invalid_timeout(self, test_config):
        """Test pool creation with invalid timeout."""
        with pytest.raises(ValueError, match="timeout must be > 0"):
            QdrantConnectionPool(
                config=test_config,
                timeout=0,
            )

    def test_pool_creation_with_invalid_recycle(self, test_config):
        """Test pool creation with invalid recycle."""
        with pytest.raises(ValueError, match="recycle must be > 0"):
            QdrantConnectionPool(
                config=test_config,
                recycle=-100,
            )

    @pytest.mark.asyncio
    async def test_pool_initialization_creates_min_connections(
        self, test_config, mock_qdrant_client
    ):
        """Test pool initialization creates min_size connections."""
        pool = QdrantConnectionPool(
            config=test_config,
            min_size=3,
            max_size=10,
            enable_health_checks=False,
        )

        with patch("src.store.connection_pool.QdrantClient", return_value=mock_qdrant_client):
            await pool.initialize()

            assert pool._initialized
            assert pool._created_count == 3
            assert pool._pool.qsize() == 3

        await pool.close()

    @pytest.mark.asyncio
    async def test_pool_initialization_failure_cleanup(self, test_config):
        """Test pool cleans up on initialization failure."""
        pool = QdrantConnectionPool(
            config=test_config,
            min_size=2,
            max_size=5,
            enable_health_checks=False,
        )

        # Mock client creation to fail
        with patch(
            "src.store.connection_pool.QdrantClient",
            side_effect=ConnectionError("Connection refused")
        ):
            with pytest.raises(QdrantConnectionError):
                await pool.initialize()

            # Pool should not be initialized
            assert not pool._initialized
            assert pool._closed  # Should be closed after cleanup

    @pytest.mark.asyncio
    async def test_double_initialization_warning(self, test_config, mock_qdrant_client):
        """Test that double initialization is handled gracefully."""
        pool = QdrantConnectionPool(
            config=test_config,
            min_size=1,
            max_size=5,
            enable_health_checks=False,
        )

        with patch("src.store.connection_pool.QdrantClient", return_value=mock_qdrant_client):
            await pool.initialize()

            # Second initialization should log warning but not fail
            await pool.initialize()

            assert pool._initialized
            assert pool._created_count == 1  # Should not create duplicates

        await pool.close()


class TestConnectionAcquireRelease:
    """Test connection acquire and release operations."""

    @pytest.mark.asyncio
    async def test_acquire_connection_from_pool(self, test_config, mock_qdrant_client):
        """Test acquiring connection from initialized pool."""
        pool = QdrantConnectionPool(
            config=test_config,
            min_size=2,
            max_size=5,
            enable_health_checks=False,
        )

        with patch("src.store.connection_pool.QdrantClient", return_value=mock_qdrant_client):
            await pool.initialize()

            client = await pool.acquire()

            assert client is not None
            assert pool._active_connections == 1
            assert pool._pool.qsize() == 1  # One remaining in pool

        await pool.close()

    @pytest.mark.asyncio
    async def test_acquire_without_initialization_raises_error(self, test_config):
        """Test acquiring from uninitialized pool raises error."""
        pool = QdrantConnectionPool(
            config=test_config,
            min_size=1,
            max_size=5,
        )

        with pytest.raises(RuntimeError, match="Pool not initialized"):
            await pool.acquire()

    @pytest.mark.asyncio
    async def test_acquire_from_closed_pool_raises_error(
        self, test_config, mock_qdrant_client
    ):
        """Test acquiring from closed pool raises error."""
        pool = QdrantConnectionPool(
            config=test_config,
            min_size=1,
            max_size=5,
            enable_health_checks=False,
        )

        with patch("src.store.connection_pool.QdrantClient", return_value=mock_qdrant_client):
            await pool.initialize()
            await pool.close()

            with pytest.raises(RuntimeError, match="Pool is closed"):
                await pool.acquire()

    @pytest.mark.asyncio
    async def test_release_connection_back_to_pool(self, test_config, mock_qdrant_client):
        """Test releasing connection back to pool."""
        pool = QdrantConnectionPool(
            config=test_config,
            min_size=1,
            max_size=5,
            enable_health_checks=False,
        )

        with patch("src.store.connection_pool.QdrantClient", return_value=mock_qdrant_client):
            await pool.initialize()

            client = await pool.acquire()
            initial_idle = pool._pool.qsize()

            await pool.release(client)

            assert pool._active_connections == 0
            assert pool._pool.qsize() == initial_idle + 1

        await pool.close()

    @pytest.mark.asyncio
    async def test_concurrent_acquire_release(self, test_config, mock_qdrant_client):
        """Test concurrent acquire and release operations."""
        pool = QdrantConnectionPool(
            config=test_config,
            min_size=2,
            max_size=10,
            enable_health_checks=False,
        )

        with patch("src.store.connection_pool.QdrantClient", return_value=mock_qdrant_client):
            await pool.initialize()

            # Simulate concurrent workload
            async def worker():
                client = await pool.acquire()
                await asyncio.sleep(0.01)  # Simulate work
                await pool.release(client)

            # Run 20 concurrent workers
            await asyncio.gather(*[worker() for _ in range(20)])

            # All connections should be back in pool
            assert pool._active_connections == 0
            assert pool._pool.qsize() >= 2  # At least min_size

        await pool.close()


class TestPoolExhaustion:
    """Test pool exhaustion and timeout handling."""

    @pytest.mark.asyncio
    async def test_pool_exhaustion_with_timeout(self, test_config, mock_qdrant_client):
        """Test pool exhaustion raises timeout error."""
        pool = QdrantConnectionPool(
            config=test_config,
            min_size=1,
            max_size=2,
            timeout=0.5,  # Short timeout for test
            enable_health_checks=False,
        )

        with patch("src.store.connection_pool.QdrantClient", return_value=mock_qdrant_client):
            await pool.initialize()

            # Acquire all connections
            client1 = await pool.acquire()
            client2 = await pool.acquire()

            # Pool is exhausted, next acquire should timeout
            with pytest.raises(ConnectionPoolExhaustedError, match="Connection pool exhausted"):
                await pool.acquire()

            # Release connections
            await pool.release(client1)
            await pool.release(client2)

        await pool.close()

    @pytest.mark.asyncio
    async def test_pool_creates_new_connection_when_empty(
        self, test_config, mock_qdrant_client
    ):
        """Test pool creates new connection when empty but under max."""
        pool = QdrantConnectionPool(
            config=test_config,
            min_size=1,
            max_size=5,
            enable_health_checks=False,
        )

        with patch("src.store.connection_pool.QdrantClient", return_value=mock_qdrant_client):
            await pool.initialize()

            # Acquire all initial connections
            client1 = await pool.acquire()

            # Pool is empty but can create new connection
            client2 = await pool.acquire()

            assert pool._created_count == 2
            assert client1 is not None
            assert client2 is not None

            await pool.release(client1)
            await pool.release(client2)

        await pool.close()

    @pytest.mark.asyncio
    async def test_pool_tracks_timeout_stats(self, test_config, mock_qdrant_client):
        """Test pool tracks timeout statistics."""
        pool = QdrantConnectionPool(
            config=test_config,
            min_size=1,
            max_size=1,
            timeout=0.1,  # Very short timeout
            enable_health_checks=False,
        )

        with patch("src.store.connection_pool.QdrantClient", return_value=mock_qdrant_client):
            await pool.initialize()

            # Acquire the only connection
            client = await pool.acquire()

            # Try to acquire again (should timeout)
            try:
                await pool.acquire()
            except ConnectionPoolExhaustedError:
                pass

            stats = pool.stats()
            assert stats.total_timeouts == 1

            await pool.release(client)

        await pool.close()


class TestHealthChecking:
    """Test health checking integration."""

    @pytest.mark.asyncio
    async def test_acquire_performs_health_check(self, test_config, mock_qdrant_client):
        """Test acquire performs health check on connection."""
        pool = QdrantConnectionPool(
            config=test_config,
            min_size=1,
            max_size=5,
            enable_health_checks=True,
        )

        # Mock health checker
        mock_health_result = HealthCheckResult(
            healthy=True,
            level=HealthCheckLevel.FAST,
            duration_ms=0.5,
        )

        with patch("src.store.connection_pool.QdrantClient", return_value=mock_qdrant_client):
            await pool.initialize()

            # Mock health check
            with patch.object(
                pool._health_checker,
                "check_health",
                return_value=mock_health_result,
            ):
                client = await pool.acquire()

                assert client is not None
                # Health check should have been called
                pool._health_checker.check_health.assert_called_once()

            await pool.release(client)

        await pool.close()

    @pytest.mark.asyncio
    async def test_unhealthy_connection_replaced(self, test_config, mock_qdrant_client):
        """Test unhealthy connection is replaced automatically."""
        pool = QdrantConnectionPool(
            config=test_config,
            min_size=1,
            max_size=5,
            enable_health_checks=True,
        )

        with patch("src.store.connection_pool.QdrantClient", return_value=mock_qdrant_client):
            await pool.initialize()

            # First health check fails, second succeeds
            unhealthy_result = HealthCheckResult(
                healthy=False,
                level=HealthCheckLevel.FAST,
                duration_ms=1.0,
                error="Connection lost",
            )
            healthy_result = HealthCheckResult(
                healthy=True,
                level=HealthCheckLevel.FAST,
                duration_ms=0.5,
            )

            with patch.object(
                pool._health_checker,
                "check_health",
                side_effect=[unhealthy_result, healthy_result],
            ):
                client = await pool.acquire()

                assert client is not None
                assert pool._stats.total_health_failures == 1
                # Should have created a replacement connection
                assert pool._stats.connections_created >= 2

            await pool.release(client)

        await pool.close()

    @pytest.mark.asyncio
    async def test_health_check_disabled(self, test_config, mock_qdrant_client):
        """Test pool works with health checking disabled."""
        pool = QdrantConnectionPool(
            config=test_config,
            min_size=1,
            max_size=5,
            enable_health_checks=False,
        )

        assert pool._health_checker is None

        with patch("src.store.connection_pool.QdrantClient", return_value=mock_qdrant_client):
            await pool.initialize()

            client = await pool.acquire()
            assert client is not None

            await pool.release(client)

        await pool.close()


class TestConnectionRecycling:
    """Test connection recycling based on age."""

    @pytest.mark.asyncio
    async def test_old_connection_recycled_on_acquire(
        self, test_config, mock_qdrant_client
    ):
        """Test old connection is recycled when acquired."""
        pool = QdrantConnectionPool(
            config=test_config,
            min_size=1,
            max_size=5,
            recycle=1,  # Recycle after 1 second
            enable_health_checks=False,
        )

        with patch("src.store.connection_pool.QdrantClient", return_value=mock_qdrant_client):
            await pool.initialize()

            # Get initial connection count
            initial_count = pool._created_count

            # Manually age a connection by modifying its created_at time
            pooled_conn = await pool._pool.get()
            pooled_conn.created_at = datetime.now(UTC) - timedelta(seconds=2)
            await pool._pool.put(pooled_conn)

            # Acquire should recycle the old connection
            client = await pool.acquire()

            assert client is not None
            assert pool._stats.connections_recycled == 1
            # New connection should have been created
            assert pool._created_count == initial_count

            await pool.release(client)

        await pool.close()

    @pytest.mark.asyncio
    async def test_connection_recycling_stats(self, test_config, mock_qdrant_client):
        """Test connection recycling statistics are tracked."""
        pool = QdrantConnectionPool(
            config=test_config,
            min_size=2,
            max_size=5,
            recycle=1,
            enable_health_checks=False,
        )

        with patch("src.store.connection_pool.QdrantClient", return_value=mock_qdrant_client):
            await pool.initialize()

            # Age all connections
            aged_connections = []
            while not pool._pool.empty():
                conn = await pool._pool.get()
                conn.created_at = datetime.now(UTC) - timedelta(seconds=2)
                aged_connections.append(conn)

            for conn in aged_connections:
                await pool._pool.put(conn)

            # Acquire should recycle
            client1 = await pool.acquire()
            client2 = await pool.acquire()

            stats = pool.stats()
            assert stats.connections_recycled >= 2

            await pool.release(client1)
            await pool.release(client2)

        await pool.close()


class TestMetricsAndStatistics:
    """Test metrics and statistics collection."""

    @pytest.mark.asyncio
    async def test_stats_initialization(self, test_config):
        """Test statistics are initialized correctly."""
        pool = QdrantConnectionPool(
            config=test_config,
            min_size=1,
            max_size=5,
        )

        stats = pool.stats()

        assert stats.pool_size == 0
        assert stats.active_connections == 0
        assert stats.idle_connections == 0
        assert stats.total_acquires == 0
        assert stats.total_releases == 0
        assert stats.total_timeouts == 0
        assert stats.connections_created == 0
        assert stats.connections_recycled == 0

    @pytest.mark.asyncio
    async def test_acquire_updates_metrics(self, test_config, mock_qdrant_client):
        """Test acquire updates metrics correctly."""
        pool = QdrantConnectionPool(
            config=test_config,
            min_size=1,
            max_size=5,
            enable_health_checks=False,
        )

        with patch("src.store.connection_pool.QdrantClient", return_value=mock_qdrant_client):
            await pool.initialize()

            client = await pool.acquire()

            stats = pool.stats()
            assert stats.total_acquires == 1
            assert stats.active_connections == 1
            assert stats.connections_created >= 1
            assert stats.avg_acquire_time_ms > 0

            await pool.release(client)

        await pool.close()

    @pytest.mark.asyncio
    async def test_release_updates_metrics(self, test_config, mock_qdrant_client):
        """Test release updates metrics correctly."""
        pool = QdrantConnectionPool(
            config=test_config,
            min_size=1,
            max_size=5,
            enable_health_checks=False,
        )

        with patch("src.store.connection_pool.QdrantClient", return_value=mock_qdrant_client):
            await pool.initialize()

            client = await pool.acquire()
            await pool.release(client)

            stats = pool.stats()
            assert stats.total_releases == 1
            assert stats.active_connections == 0

        await pool.close()

    @pytest.mark.asyncio
    async def test_acquire_latency_metrics(self, test_config, mock_qdrant_client):
        """Test acquire latency metrics are calculated."""
        pool = QdrantConnectionPool(
            config=test_config,
            min_size=2,
            max_size=5,
            enable_health_checks=False,
        )

        with patch("src.store.connection_pool.QdrantClient", return_value=mock_qdrant_client):
            await pool.initialize()

            # Acquire multiple times to build metrics
            clients = []
            for _ in range(5):
                client = await pool.acquire()
                clients.append(client)

            stats = pool.stats()
            assert stats.avg_acquire_time_ms > 0
            assert stats.p95_acquire_time_ms > 0
            assert stats.max_acquire_time_ms >= stats.avg_acquire_time_ms

            # Release all
            for client in clients:
                await pool.release(client)

        await pool.close()

    @pytest.mark.asyncio
    async def test_metrics_history_limit(self, test_config, mock_qdrant_client):
        """Test metrics history is limited to prevent memory growth."""
        pool = QdrantConnectionPool(
            config=test_config,
            min_size=2,
            max_size=5,
            enable_health_checks=False,
        )

        with patch("src.store.connection_pool.QdrantClient", return_value=mock_qdrant_client):
            await pool.initialize()

            # Acquire many times to exceed history limit
            for _ in range(1500):
                client = await pool.acquire()
                await pool.release(client)

            # History should be capped at 1000
            assert len(pool._acquire_times) <= 1000

        await pool.close()


class TestPoolClosing:
    """Test pool closing and cleanup."""

    @pytest.mark.asyncio
    async def test_pool_close_drains_connections(self, test_config, mock_qdrant_client):
        """Test pool close drains and closes all connections."""
        pool = QdrantConnectionPool(
            config=test_config,
            min_size=3,
            max_size=5,
            enable_health_checks=False,
        )

        with patch("src.store.connection_pool.QdrantClient", return_value=mock_qdrant_client):
            await pool.initialize()

            await pool.close()

            assert pool._closed
            assert pool._pool.empty()
            assert pool._active_connections == 0
            assert pool._created_count == 0
            assert not pool._initialized
            # All clients should have been closed
            assert mock_qdrant_client.close.call_count >= 3

    @pytest.mark.asyncio
    async def test_double_close_is_safe(self, test_config, mock_qdrant_client):
        """Test closing pool twice is safe."""
        pool = QdrantConnectionPool(
            config=test_config,
            min_size=1,
            max_size=5,
            enable_health_checks=False,
        )

        with patch("src.store.connection_pool.QdrantClient", return_value=mock_qdrant_client):
            await pool.initialize()

            await pool.close()
            # Second close should be safe
            await pool.close()

            assert pool._closed

    @pytest.mark.asyncio
    async def test_release_to_closed_pool_handled_gracefully(
        self, test_config, mock_qdrant_client
    ):
        """Test releasing connection to closed pool is handled gracefully."""
        pool = QdrantConnectionPool(
            config=test_config,
            min_size=1,
            max_size=5,
            enable_health_checks=False,
        )

        with patch("src.store.connection_pool.QdrantClient", return_value=mock_qdrant_client):
            await pool.initialize()

            client = await pool.acquire()
            await pool.close()

            # Release to closed pool should not raise
            await pool.release(client)


class TestPooledConnection:
    """Test PooledConnection wrapper."""

    def test_pooled_connection_creation(self, mock_qdrant_client):
        """Test creating pooled connection."""
        now = datetime.now(UTC)
        pooled = PooledConnection(
            client=mock_qdrant_client,
            created_at=now,
            last_used=now,
        )

        assert pooled.client == mock_qdrant_client
        assert pooled.created_at == now
        assert pooled.last_used == now
        assert pooled.use_count == 0

    def test_pooled_connection_use_tracking(self, mock_qdrant_client):
        """Test pooled connection tracks usage."""
        pooled = PooledConnection(
            client=mock_qdrant_client,
            created_at=datetime.now(UTC),
            last_used=datetime.now(UTC),
        )

        # Simulate usage
        pooled.use_count += 1
        pooled.last_used = datetime.now(UTC)

        assert pooled.use_count == 1
        assert pooled.last_used > pooled.created_at


class TestPoolStats:
    """Test PoolStats dataclass."""

    def test_pool_stats_creation(self):
        """Test creating PoolStats."""
        stats = PoolStats(
            pool_size=5,
            active_connections=2,
            idle_connections=3,
            total_acquires=100,
            total_releases=98,
            total_timeouts=0,
            total_health_failures=1,
            connections_created=5,
            connections_recycled=2,
            connections_failed=1,
            avg_acquire_time_ms=1.5,
            p95_acquire_time_ms=3.2,
            max_acquire_time_ms=5.8,
        )

        assert stats.pool_size == 5
        assert stats.active_connections == 2
        assert stats.idle_connections == 3
        assert stats.total_acquires == 100
        assert stats.avg_acquire_time_ms == 1.5
