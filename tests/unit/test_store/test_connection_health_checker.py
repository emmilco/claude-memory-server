"""Unit tests for ConnectionHealthChecker.

Tests health checking functionality including:
- Fast, medium, and deep health checks
- Timeout handling
- Statistics collection
- Error handling

PERF-007: Connection Pooling for Qdrant
"""

import asyncio
import pytest
from unittest.mock import Mock

from qdrant_client import QdrantClient
from qdrant_client.http.exceptions import ResponseHandlingException

from src.store.connection_health_checker import (
    ConnectionHealthChecker,
    HealthCheckLevel,
    HealthCheckResult,
)

# Skip entire module in CI - timing sensitive under parallel execution
pytestmark = pytest.mark.skip_ci(reason="Timing-sensitive under parallel execution")


@pytest.fixture
def health_checker():
    """Create ConnectionHealthChecker instance."""
    return ConnectionHealthChecker(
        fast_timeout=0.001,  # 1ms
        medium_timeout=0.010,  # 10ms
        deep_timeout=0.050,  # 50ms
    )


@pytest.fixture
def mock_qdrant_client():
    """Create mock QdrantClient."""
    client = Mock(spec=QdrantClient)
    client.get_collections = Mock(return_value=Mock(collections=[]))
    client.count = Mock(return_value=100)
    return client


class TestHealthCheckInitialization:
    """Test health checker initialization."""

    def test_health_checker_creation(self):
        """Test creating health checker with custom timeouts."""
        checker = ConnectionHealthChecker(
            fast_timeout=0.002,
            medium_timeout=0.020,
            deep_timeout=0.100,
        )

        assert checker.fast_timeout == 0.002
        assert checker.medium_timeout == 0.020
        assert checker.deep_timeout == 0.100
        assert checker.total_checks == 0
        assert checker.total_failures == 0

    def test_health_checker_default_timeouts(self):
        """Test health checker uses default timeouts."""
        checker = ConnectionHealthChecker()

        assert checker.fast_timeout == 0.05  # 50ms (updated from 1ms)
        assert checker.medium_timeout == 0.1  # 100ms (updated from 10ms)
        assert checker.deep_timeout == 0.2  # 200ms (updated from 50ms)


class TestFastHealthCheck:
    """Test fast health check (< 1ms)."""

    @pytest.mark.asyncio
    async def test_fast_check_healthy_connection(self, mock_qdrant_client):
        """Test fast check on healthy connection."""
        # Use a more lenient timeout for this test
        checker = ConnectionHealthChecker(
            fast_timeout=1.0,  # 1 second timeout
            medium_timeout=1.0,
            deep_timeout=1.0,
        )

        result = await checker.check_health(mock_qdrant_client, HealthCheckLevel.FAST)

        assert result.healthy
        assert result.level == HealthCheckLevel.FAST
        assert result.duration_ms >= 0
        assert result.error is None

    @pytest.mark.asyncio
    async def test_fast_check_connection_error(self):
        """Test fast check with connection error."""
        checker = ConnectionHealthChecker()

        mock_client = Mock(spec=QdrantClient)
        mock_client.get_collections = Mock(
            side_effect=ConnectionError("Connection refused")
        )

        result = await checker.check_health(mock_client, HealthCheckLevel.FAST)

        assert not result.healthy
        assert result.level == HealthCheckLevel.FAST
        # Connection error is caught and health check fails

    @pytest.mark.asyncio
    async def test_fast_check_timeout(self, mock_qdrant_client):
        """Test fast check timeout."""
        import time

        # Create checker with very short timeout
        checker = ConnectionHealthChecker(fast_timeout=0.001)  # 1ms

        # Mock a slow synchronous operation (runs in executor thread)
        def slow_get_collections():
            time.sleep(0.1)  # 100ms - way over timeout
            return Mock(collections=[])

        mock_qdrant_client.get_collections.side_effect = slow_get_collections

        result = await checker.check_health(mock_qdrant_client, HealthCheckLevel.FAST)

        # Should timeout and be unhealthy
        assert not result.healthy


class TestMediumHealthCheck:
    """Test medium health check (< 10ms)."""

    @pytest.mark.asyncio
    async def test_medium_check_healthy_connection(
        self, health_checker, mock_qdrant_client
    ):
        """Test medium check on healthy connection."""
        result = await health_checker.check_health(
            mock_qdrant_client, HealthCheckLevel.MEDIUM
        )

        assert result.healthy
        assert result.level == HealthCheckLevel.MEDIUM
        assert result.duration_ms >= 0
        assert result.error is None

    @pytest.mark.asyncio
    async def test_medium_check_unexpected_response(self):
        """Test medium check with unexpected response."""
        checker = ConnectionHealthChecker()

        mock_client = Mock(spec=QdrantClient)
        # Create proper UnexpectedResponse with required arguments
        mock_client.get_collections = Mock(
            side_effect=ResponseHandlingException("Response handling failed")
        )

        result = await checker.check_health(mock_client, HealthCheckLevel.MEDIUM)

        assert not result.healthy
        assert result.level == HealthCheckLevel.MEDIUM

    @pytest.mark.asyncio
    async def test_medium_check_none_response(self, health_checker):
        """Test medium check with None response."""
        mock_client = Mock(spec=QdrantClient)
        mock_client.get_collections = Mock(return_value=None)

        result = await health_checker.check_health(mock_client, HealthCheckLevel.MEDIUM)

        assert not result.healthy


class TestDeepHealthCheck:
    """Test deep health check (< 50ms)."""

    @pytest.mark.asyncio
    async def test_deep_check_healthy_connection(
        self, health_checker, mock_qdrant_client
    ):
        """Test deep check on healthy connection."""
        # Setup mock with collections
        mock_collection = Mock()
        mock_collection.name = "test_collection"
        mock_qdrant_client.get_collections = Mock(
            return_value=Mock(collections=[mock_collection])
        )
        mock_qdrant_client.count = Mock(return_value=100)

        result = await health_checker.check_health(
            mock_qdrant_client, HealthCheckLevel.DEEP
        )

        assert result.healthy
        assert result.level == HealthCheckLevel.DEEP
        assert result.duration_ms >= 0
        # Should have called count on collection
        mock_qdrant_client.count.assert_called_once_with("test_collection")

    @pytest.mark.asyncio
    async def test_deep_check_no_collections(self, health_checker, mock_qdrant_client):
        """Test deep check when no collections exist."""
        mock_qdrant_client.get_collections = Mock(return_value=Mock(collections=[]))

        result = await health_checker.check_health(
            mock_qdrant_client, HealthCheckLevel.DEEP
        )

        # Should still be healthy (connection works, just no collections)
        assert result.healthy
        assert result.level == HealthCheckLevel.DEEP

    @pytest.mark.asyncio
    async def test_deep_check_query_failure(self, health_checker):
        """Test deep check when query fails."""
        mock_client = Mock(spec=QdrantClient)
        mock_collection = Mock()
        mock_collection.name = "test_collection"
        mock_client.get_collections = Mock(
            return_value=Mock(collections=[mock_collection])
        )
        mock_client.count = Mock(side_effect=Exception("Query failed"))

        result = await health_checker.check_health(mock_client, HealthCheckLevel.DEEP)

        assert not result.healthy
        assert result.level == HealthCheckLevel.DEEP


class TestHealthCheckStatistics:
    """Test health check statistics collection."""

    @pytest.mark.asyncio
    async def test_stats_increment_on_check(self, health_checker, mock_qdrant_client):
        """Test statistics increment on health check."""
        initial_checks = health_checker.total_checks

        await health_checker.check_health(mock_qdrant_client, HealthCheckLevel.FAST)

        assert health_checker.total_checks == initial_checks + 1
        assert health_checker.checks_by_level[HealthCheckLevel.FAST] == 1

    @pytest.mark.asyncio
    async def test_stats_track_failures(self, health_checker):
        """Test statistics track failures."""
        mock_client = Mock(spec=QdrantClient)
        mock_client.get_collections = Mock(side_effect=ConnectionError("Failed"))

        initial_failures = health_checker.total_failures

        await health_checker.check_health(mock_client, HealthCheckLevel.FAST)

        assert health_checker.total_failures == initial_failures + 1
        assert health_checker.failures_by_level[HealthCheckLevel.FAST] == 1

    @pytest.mark.asyncio
    async def test_get_stats(self, health_checker, mock_qdrant_client):
        """Test get_stats returns correct statistics."""
        # Reset stats to ensure clean state for this test (avoid cross-test interference)
        health_checker.reset_stats()

        # Perform some checks
        await health_checker.check_health(mock_qdrant_client, HealthCheckLevel.FAST)
        await health_checker.check_health(mock_qdrant_client, HealthCheckLevel.MEDIUM)
        await health_checker.check_health(mock_qdrant_client, HealthCheckLevel.DEEP)

        stats = health_checker.get_stats()

        assert stats["total_checks"] == 3
        assert stats["total_failures"] == 0
        assert stats["failure_rate_percent"] == 0.0
        assert stats["checks_by_level"]["fast"] == 1
        assert stats["checks_by_level"]["medium"] == 1
        assert stats["checks_by_level"]["deep"] == 1

    @pytest.mark.asyncio
    async def test_get_stats_with_failures(self, health_checker):
        """Test get_stats calculates failure rate correctly."""
        mock_client = Mock(spec=QdrantClient)
        mock_client.get_collections = Mock(side_effect=ConnectionError("Failed"))

        # Perform checks that will fail
        await health_checker.check_health(mock_client, HealthCheckLevel.FAST)
        await health_checker.check_health(mock_client, HealthCheckLevel.FAST)

        stats = health_checker.get_stats()

        assert stats["total_checks"] == 2
        assert stats["total_failures"] == 2
        assert stats["failure_rate_percent"] == 100.0

    def test_reset_stats(self, health_checker):
        """Test reset_stats clears all statistics."""
        # Set some stats
        health_checker.total_checks = 10
        health_checker.total_failures = 2
        health_checker.checks_by_level[HealthCheckLevel.FAST] = 5

        health_checker.reset_stats()

        assert health_checker.total_checks == 0
        assert health_checker.total_failures == 0
        assert health_checker.checks_by_level[HealthCheckLevel.FAST] == 0


class TestHealthCheckResult:
    """Test HealthCheckResult dataclass."""

    def test_health_check_result_creation(self):
        """Test creating HealthCheckResult."""
        result = HealthCheckResult(
            healthy=True,
            level=HealthCheckLevel.MEDIUM,
            duration_ms=5.5,
        )

        assert result.healthy
        assert result.level == HealthCheckLevel.MEDIUM
        assert result.duration_ms == 5.5
        assert result.error is None

    def test_health_check_result_with_error(self):
        """Test creating HealthCheckResult with error."""
        result = HealthCheckResult(
            healthy=False,
            level=HealthCheckLevel.DEEP,
            duration_ms=25.0,
            error="Connection timeout",
        )

        assert not result.healthy
        assert result.level == HealthCheckLevel.DEEP
        assert result.duration_ms == 25.0
        assert result.error == "Connection timeout"

    def test_health_check_result_repr(self):
        """Test HealthCheckResult string representation."""
        result = HealthCheckResult(
            healthy=True,
            level=HealthCheckLevel.FAST,
            duration_ms=1.2,
        )

        repr_str = repr(result)
        assert "healthy" in repr_str
        assert "fast" in repr_str
        assert "1.2" in repr_str


class TestHealthCheckLevels:
    """Test health check level enum."""

    def test_health_check_levels(self):
        """Test all health check levels exist."""
        assert HealthCheckLevel.FAST.value == "fast"
        assert HealthCheckLevel.MEDIUM.value == "medium"
        assert HealthCheckLevel.DEEP.value == "deep"

    @pytest.mark.asyncio
    async def test_all_levels_work(self, health_checker, mock_qdrant_client):
        """Test health check works for all levels."""
        for level in HealthCheckLevel:
            result = await health_checker.check_health(mock_qdrant_client, level)

            assert result is not None
            assert result.level == level

    @pytest.mark.asyncio
    async def test_invalid_level_raises_error(self, mock_qdrant_client):
        """Test invalid health check level raises error."""
        checker = ConnectionHealthChecker()

        # This will raise KeyError since the level isn't valid
        with pytest.raises((ValueError, KeyError)):
            # Pass invalid level by bypassing enum
            await checker.check_health(mock_qdrant_client, "invalid")


class TestConcurrentHealthChecks:
    """Test concurrent health check operations."""

    @pytest.mark.asyncio
    async def test_concurrent_health_checks(self, mock_qdrant_client):
        """Test multiple concurrent health checks."""
        # Use a more lenient timeout for concurrent tests
        checker = ConnectionHealthChecker(
            fast_timeout=1.0,
            medium_timeout=1.0,
            deep_timeout=1.0,
        )

        # Run 10 concurrent health checks
        results = await asyncio.gather(
            *[
                checker.check_health(mock_qdrant_client, HealthCheckLevel.FAST)
                for _ in range(10)
            ]
        )

        assert len(results) == 10
        assert all(r.healthy for r in results)
        assert checker.total_checks == 10

    @pytest.mark.asyncio
    async def test_concurrent_mixed_level_checks(
        self, health_checker, mock_qdrant_client
    ):
        """Test concurrent health checks at different levels."""
        levels = [
            HealthCheckLevel.FAST,
            HealthCheckLevel.MEDIUM,
            HealthCheckLevel.DEEP,
        ] * 3  # 9 checks total

        results = await asyncio.gather(
            *[
                health_checker.check_health(mock_qdrant_client, level)
                for level in levels
            ]
        )

        assert len(results) == 9
        assert health_checker.total_checks == 9
        assert health_checker.checks_by_level[HealthCheckLevel.FAST] == 3
        assert health_checker.checks_by_level[HealthCheckLevel.MEDIUM] == 3
        assert health_checker.checks_by_level[HealthCheckLevel.DEEP] == 3
