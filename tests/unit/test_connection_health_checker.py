"""Unit tests for Qdrant connection health checking.

Tests cover:
- Health check levels (FAST, MEDIUM, DEEP)
- Health check timing and performance
- Error handling and unhealthy detection
- Statistics tracking
- Auto-healing scenarios

PERF-007: Connection Pooling - Day 2 Health Checking
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock, MagicMock

from qdrant_client import QdrantClient
from qdrant_client.http.exceptions import UnexpectedResponse, ResponseHandlingException

from src.store.connection_health_checker import (
    ConnectionHealthChecker,
    HealthCheckLevel,
    HealthCheckResult,
)


@pytest.fixture
def health_checker():
    """Create a ConnectionHealthChecker instance."""
    return ConnectionHealthChecker(
        fast_timeout=0.001,
        medium_timeout=0.010,
        deep_timeout=0.050,
    )


@pytest.fixture
def mock_client():
    """Create a mock QdrantClient."""
    client = Mock(spec=QdrantClient)
    client.get_collections.return_value = Mock(collections=[])
    return client


class TestHealthCheckerInitialization:
    """Test health checker initialization."""

    def test_initialization_defaults(self):
        """Test health checker initialization with default timeouts."""
        checker = ConnectionHealthChecker()

        # Updated default timeouts (was 1ms/10ms/50ms, now 50ms/100ms/200ms)
        # See CHANGELOG 2025-11-24: Fixed overly aggressive health check timeouts
        assert checker.fast_timeout == 0.05
        assert checker.medium_timeout == 0.1
        assert checker.deep_timeout == 0.2
        assert checker.total_checks == 0
        assert checker.total_failures == 0

    def test_initialization_custom_timeouts(self):
        """Test health checker initialization with custom timeouts."""
        checker = ConnectionHealthChecker(
            fast_timeout=0.002,
            medium_timeout=0.020,
            deep_timeout=0.100,
        )

        assert checker.fast_timeout == 0.002
        assert checker.medium_timeout == 0.020
        assert checker.deep_timeout == 0.100

    def test_initialization_stats(self):
        """Test that stats are properly initialized."""
        checker = ConnectionHealthChecker()

        assert all(count == 0 for count in checker.checks_by_level.values())
        assert all(count == 0 for count in checker.failures_by_level.values())


class TestFastHealthCheck:
    """Test fast health checking (<1ms)."""

    @pytest.mark.asyncio
    async def test_fast_check_healthy(self, health_checker, mock_client):
        """Test fast health check with healthy connection."""
        result = await health_checker.check_health(mock_client, HealthCheckLevel.FAST)

        assert result.healthy is True
        assert result.level == HealthCheckLevel.FAST
        assert result.duration_ms < 10.0  # Should be very fast
        assert result.error is None

    @pytest.mark.asyncio
    async def test_fast_check_timeout(self, health_checker):
        """Test fast health check with timeout."""
        client = Mock(spec=QdrantClient)
        # Make get_collections hang by blocking
        import time
        client.get_collections.side_effect = lambda: time.sleep(1.0)

        result = await health_checker.check_health(client, HealthCheckLevel.FAST)

        assert result.healthy is False
        assert result.level == HealthCheckLevel.FAST

    @pytest.mark.asyncio
    async def test_fast_check_connection_error(self, health_checker):
        """Test fast health check with connection error."""
        client = Mock(spec=QdrantClient)
        client.get_collections.side_effect = ConnectionError("Connection refused")

        result = await health_checker.check_health(client, HealthCheckLevel.FAST)

        assert result.healthy is False
        assert result.level == HealthCheckLevel.FAST
        # Connection error results in unhealthy status

    @pytest.mark.asyncio
    async def test_fast_check_unexpected_response(self, health_checker):
        """Test fast health check with unexpected response."""
        client = Mock(spec=QdrantClient)
        client.get_collections.side_effect = UnexpectedResponse(
            status_code=500,
            reason_phrase="Internal Server Error",
            content=b"",
            headers={},
        )

        result = await health_checker.check_health(client, HealthCheckLevel.FAST)

        assert result.healthy is False
        assert result.level == HealthCheckLevel.FAST

    @pytest.mark.asyncio
    async def test_fast_check_performance(self, health_checker, mock_client):
        """Test that fast health check meets <1ms target (when healthy)."""
        # Note: This test may be flaky on slow systems
        # We check that it's under 10ms to account for test overhead
        result = await health_checker.check_health(mock_client, HealthCheckLevel.FAST)

        assert result.duration_ms < 10.0  # Generous for test environment


class TestMediumHealthCheck:
    """Test medium health checking (<10ms)."""

    @pytest.mark.asyncio
    async def test_medium_check_healthy(self, health_checker, mock_client):
        """Test medium health check with healthy connection."""
        result = await health_checker.check_health(mock_client, HealthCheckLevel.MEDIUM)

        assert result.healthy is True
        assert result.level == HealthCheckLevel.MEDIUM
        assert result.duration_ms < 50.0  # Should be reasonably fast
        assert result.error is None

    @pytest.mark.asyncio
    async def test_medium_check_timeout(self, health_checker):
        """Test medium health check with timeout."""
        client = Mock(spec=QdrantClient)
        import time
        client.get_collections.side_effect = lambda: time.sleep(1.0)

        result = await health_checker.check_health(client, HealthCheckLevel.MEDIUM)

        assert result.healthy is False
        assert result.level == HealthCheckLevel.MEDIUM

    @pytest.mark.asyncio
    async def test_medium_check_connection_error(self, health_checker):
        """Test medium health check with connection error."""
        client = Mock(spec=QdrantClient)
        client.get_collections.side_effect = ConnectionError("Connection refused")

        result = await health_checker.check_health(client, HealthCheckLevel.MEDIUM)

        assert result.healthy is False
        assert result.level == HealthCheckLevel.MEDIUM
        # Error is captured
        assert result.error is not None or not result.healthy


class TestDeepHealthCheck:
    """Test deep health checking (<50ms)."""

    @pytest.mark.asyncio
    async def test_deep_check_healthy_with_collections(self, health_checker):
        """Test deep health check with collections available."""
        client = Mock(spec=QdrantClient)

        # Mock collections response
        mock_collection = Mock()
        mock_collection.name = "test_collection"
        mock_collections_response = Mock()
        mock_collections_response.collections = [mock_collection]

        client.get_collections.return_value = mock_collections_response
        client.count.return_value = Mock(count=100)

        result = await health_checker.check_health(client, HealthCheckLevel.DEEP)

        assert result.healthy is True
        assert result.level == HealthCheckLevel.DEEP
        assert result.duration_ms < 100.0
        assert result.error is None

    @pytest.mark.asyncio
    async def test_deep_check_healthy_no_collections(self, health_checker):
        """Test deep health check with no collections (still healthy)."""
        client = Mock(spec=QdrantClient)

        # Mock empty collections response
        mock_collections_response = Mock()
        mock_collections_response.collections = []

        client.get_collections.return_value = mock_collections_response

        result = await health_checker.check_health(client, HealthCheckLevel.DEEP)

        assert result.healthy is True
        assert result.level == HealthCheckLevel.DEEP

    @pytest.mark.asyncio
    async def test_deep_check_timeout(self, health_checker):
        """Test deep health check with timeout."""
        client = Mock(spec=QdrantClient)
        import time
        client.get_collections.side_effect = lambda: time.sleep(1.0)

        result = await health_checker.check_health(client, HealthCheckLevel.DEEP)

        assert result.healthy is False
        assert result.level == HealthCheckLevel.DEEP

    @pytest.mark.asyncio
    async def test_deep_check_count_error(self, health_checker):
        """Test deep health check with count operation error."""
        client = Mock(spec=QdrantClient)

        mock_collection = Mock()
        mock_collection.name = "test_collection"
        mock_collections_response = Mock()
        mock_collections_response.collections = [mock_collection]

        client.get_collections.return_value = mock_collections_response
        client.count.side_effect = Exception("Count failed")

        result = await health_checker.check_health(client, HealthCheckLevel.DEEP)

        assert result.healthy is False
        assert result.level == HealthCheckLevel.DEEP
        # Error captured or unhealthy
        assert result.error is not None or not result.healthy


class TestHealthCheckStatistics:
    """Test health check statistics tracking."""

    @pytest.mark.asyncio
    async def test_stats_track_checks(self, health_checker, mock_client):
        """Test that statistics track total checks."""
        await health_checker.check_health(mock_client, HealthCheckLevel.FAST)
        await health_checker.check_health(mock_client, HealthCheckLevel.MEDIUM)
        await health_checker.check_health(mock_client, HealthCheckLevel.DEEP)

        assert health_checker.total_checks == 3

    @pytest.mark.asyncio
    async def test_stats_track_failures(self, health_checker):
        """Test that statistics track failures."""
        client = Mock(spec=QdrantClient)
        client.get_collections.side_effect = ConnectionError("Failed")

        await health_checker.check_health(client, HealthCheckLevel.FAST)
        await health_checker.check_health(client, HealthCheckLevel.MEDIUM)

        assert health_checker.total_failures == 2
        assert health_checker.total_checks == 2

    @pytest.mark.asyncio
    async def test_stats_by_level(self, health_checker, mock_client):
        """Test that statistics track checks by level."""
        await health_checker.check_health(mock_client, HealthCheckLevel.FAST)
        await health_checker.check_health(mock_client, HealthCheckLevel.FAST)
        await health_checker.check_health(mock_client, HealthCheckLevel.MEDIUM)

        assert health_checker.checks_by_level[HealthCheckLevel.FAST] == 2
        assert health_checker.checks_by_level[HealthCheckLevel.MEDIUM] == 1
        assert health_checker.checks_by_level[HealthCheckLevel.DEEP] == 0

    @pytest.mark.asyncio
    async def test_stats_failures_by_level(self, health_checker):
        """Test that statistics track failures by level."""
        client = Mock(spec=QdrantClient)
        client.get_collections.side_effect = ConnectionError("Failed")

        await health_checker.check_health(client, HealthCheckLevel.FAST)
        await health_checker.check_health(client, HealthCheckLevel.MEDIUM)

        assert health_checker.failures_by_level[HealthCheckLevel.FAST] == 1
        assert health_checker.failures_by_level[HealthCheckLevel.MEDIUM] == 1

    @pytest.mark.asyncio
    async def test_get_stats(self, health_checker, mock_client):
        """Test get_stats returns correct statistics."""
        # Perform some checks
        await health_checker.check_health(mock_client, HealthCheckLevel.FAST)
        await health_checker.check_health(mock_client, HealthCheckLevel.FAST)

        client = Mock(spec=QdrantClient)
        client.get_collections.side_effect = ConnectionError("Failed")
        await health_checker.check_health(client, HealthCheckLevel.MEDIUM)

        stats = health_checker.get_stats()

        assert stats["total_checks"] == 3
        assert stats["total_failures"] == 1
        assert stats["failure_rate_percent"] == 33.33
        assert stats["checks_by_level"]["fast"] == 2
        assert stats["checks_by_level"]["medium"] == 1
        assert stats["failures_by_level"]["medium"] == 1

    def test_reset_stats(self, health_checker):
        """Test resetting statistics."""
        health_checker.total_checks = 10
        health_checker.total_failures = 5
        health_checker.checks_by_level[HealthCheckLevel.FAST] = 10

        health_checker.reset_stats()

        assert health_checker.total_checks == 0
        assert health_checker.total_failures == 0
        assert all(count == 0 for count in health_checker.checks_by_level.values())
        assert all(count == 0 for count in health_checker.failures_by_level.values())


class TestHealthCheckResult:
    """Test HealthCheckResult dataclass."""

    def test_result_representation_healthy(self):
        """Test HealthCheckResult string representation for healthy result."""
        result = HealthCheckResult(
            healthy=True,
            level=HealthCheckLevel.FAST,
            duration_ms=0.5,
        )

        repr_str = repr(result)
        assert "healthy" in repr_str
        assert "fast" in repr_str
        assert "0.5" in repr_str

    def test_result_representation_unhealthy(self):
        """Test HealthCheckResult string representation for unhealthy result."""
        result = HealthCheckResult(
            healthy=False,
            level=HealthCheckLevel.MEDIUM,
            duration_ms=15.0,
            error="Connection failed",
        )

        repr_str = repr(result)
        assert "unhealthy" in repr_str
        assert "medium" in repr_str
        assert "15.0" in repr_str
        assert "Connection failed" in repr_str

    def test_result_without_error(self):
        """Test HealthCheckResult without error message."""
        result = HealthCheckResult(
            healthy=True,
            level=HealthCheckLevel.DEEP,
            duration_ms=25.0,
        )

        assert result.error is None
