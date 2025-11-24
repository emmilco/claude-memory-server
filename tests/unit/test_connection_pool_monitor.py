"""Unit tests for connection pool monitoring.

Tests cover:
- Monitor initialization and lifecycle
- Metrics collection
- Alert generation
- Alert thresholds
- Statistics tracking

PERF-007: Connection Pooling - Day 2 Monitoring
"""

import pytest
import asyncio
from datetime import datetime, UTC
from unittest.mock import Mock, AsyncMock, patch

from src.store.connection_pool_monitor import (
    ConnectionPoolMonitor,
    PoolMetrics,
    PoolAlert,
    AlertSeverity,
)
from src.store.connection_pool import PoolStats


@pytest.fixture
def mock_pool():
    """Create a mock connection pool."""
    pool = Mock()
    pool.stats.return_value = PoolStats(
        pool_size=5,
        active_connections=2,
        idle_connections=3,
        total_acquires=100,
        total_releases=98,
        total_timeouts=0,
        total_health_failures=0,
        connections_created=5,
        connections_recycled=0,
        connections_failed=0,
        avg_acquire_time_ms=5.0,
        p95_acquire_time_ms=10.0,
        max_acquire_time_ms=15.0,
    )
    return pool


@pytest.fixture
def monitor(mock_pool):
    """Create a ConnectionPoolMonitor instance."""
    return ConnectionPoolMonitor(
        pool=mock_pool,
        collection_interval=0.1,  # Fast for testing
        exhaustion_threshold=0.9,
        latency_threshold_ms=100.0,
    )


class TestMonitorInitialization:
    """Test monitor initialization."""

    def test_initialization_defaults(self, mock_pool):
        """Test monitor initialization with defaults."""
        monitor = ConnectionPoolMonitor(pool=mock_pool)

        assert monitor.pool == mock_pool
        assert monitor.collection_interval == 30.0
        assert monitor.exhaustion_threshold == 0.9
        assert monitor.latency_threshold_ms == 100.0
        assert not monitor._running
        assert monitor.total_collections == 0
        assert monitor.total_alerts == 0

    def test_initialization_custom_params(self, mock_pool):
        """Test monitor initialization with custom parameters."""
        monitor = ConnectionPoolMonitor(
            pool=mock_pool,
            collection_interval=10.0,
            exhaustion_threshold=0.8,
            latency_threshold_ms=50.0,
        )

        assert monitor.collection_interval == 10.0
        assert monitor.exhaustion_threshold == 0.8
        assert monitor.latency_threshold_ms == 50.0

    def test_initialization_with_callback(self, mock_pool):
        """Test monitor initialization with alert callback."""
        async def alert_handler(alert):
            pass

        monitor = ConnectionPoolMonitor(
            pool=mock_pool,
            alert_callback=alert_handler,
        )

        assert monitor.alert_callback == alert_handler


class TestMonitorLifecycle:
    """Test monitor start/stop lifecycle."""

    @pytest.mark.asyncio
    async def test_start_monitor(self, monitor):
        """Test starting the monitor."""
        await monitor.start()

        assert monitor._running is True
        assert monitor._monitor_task is not None

        await monitor.stop()

    @pytest.mark.asyncio
    async def test_stop_monitor(self, monitor):
        """Test stopping the monitor."""
        await monitor.start()
        await asyncio.sleep(0.05)  # Let it run briefly
        await monitor.stop()

        assert monitor._running is False
        assert monitor._monitor_task is None

    @pytest.mark.asyncio
    async def test_start_already_running(self, monitor):
        """Test starting an already running monitor (should be idempotent)."""
        await monitor.start()
        await monitor.start()  # Second start should be no-op

        assert monitor._running is True

        await monitor.stop()

    @pytest.mark.asyncio
    async def test_stop_not_running(self, monitor):
        """Test stopping a monitor that's not running (should be idempotent)."""
        await monitor.stop()  # Should not raise

        assert not monitor._running


class TestMetricsCollection:
    """Test metrics collection."""

    @pytest.mark.asyncio
    async def test_collect_metrics(self, monitor):
        """Test that metrics are collected."""
        await monitor.start()
        await asyncio.sleep(0.15)  # Wait for at least one collection
        await monitor.stop()

        assert monitor.total_collections > 0
        assert len(monitor._metrics_history) > 0

    @pytest.mark.asyncio
    async def test_metrics_snapshot(self, monitor, mock_pool):
        """Test that metrics snapshot captures pool state."""
        await monitor._collect_metrics()

        metrics = monitor.get_current_metrics()

        assert metrics is not None
        assert metrics.active_connections == 2
        assert metrics.idle_connections == 3
        assert metrics.total_connections == 5
        assert metrics.acquire_latency_p95_ms == 10.0

    @pytest.mark.asyncio
    async def test_metrics_history_limit(self, monitor, mock_pool):
        """Test that metrics history is limited to prevent memory growth."""
        # Manually add many metrics
        for i in range(1100):
            monitor._metrics_history.append(
                PoolMetrics(
                    timestamp=datetime.now(UTC),
                    active_connections=1,
                    idle_connections=1,
                    total_connections=2,
                    wait_queue_size=0,
                    acquire_latency_p95_ms=5.0,
                    acquire_latency_avg_ms=3.0,
                    total_acquires=i,
                    total_releases=i,
                    total_timeouts=0,
                    total_health_failures=0,
                )
            )

        await monitor._collect_metrics()

        # Should be limited to 1000
        assert len(monitor._metrics_history) == 1000

    @pytest.mark.asyncio
    async def test_get_current_metrics(self, monitor):
        """Test getting current metrics."""
        await monitor._collect_metrics()

        current = monitor.get_current_metrics()

        assert current is not None
        assert isinstance(current, PoolMetrics)

    @pytest.mark.asyncio
    async def test_get_metrics_history(self, monitor):
        """Test getting metrics history."""
        await monitor._collect_metrics()
        await asyncio.sleep(0.05)
        await monitor._collect_metrics()

        history = monitor.get_metrics_history(limit=10)

        assert len(history) >= 1
        # Should be newest first
        assert history[0].timestamp >= history[-1].timestamp if len(history) > 1 else True


class TestAlertGeneration:
    """Test alert generation."""

    @pytest.mark.asyncio
    async def test_pool_exhaustion_alert_warning(self, monitor, mock_pool):
        """Test pool exhaustion alert at WARNING level (90-95%)."""
        # Set pool to 90% utilization
        mock_pool.stats.return_value.active_connections = 9
        mock_pool.stats.return_value.pool_size = 10

        await monitor._collect_metrics()

        # Should have generated a warning
        alerts = monitor.get_recent_alerts()
        assert len(alerts) > 0
        assert any(
            alert.severity == AlertSeverity.WARNING and "exhaustion" in alert.message.lower()
            for alert in alerts
        )

    @pytest.mark.asyncio
    async def test_pool_exhaustion_alert_critical(self, monitor, mock_pool):
        """Test pool exhaustion alert at CRITICAL level (>95%)."""
        # Set pool to 100% utilization
        mock_pool.stats.return_value.active_connections = 10
        mock_pool.stats.return_value.pool_size = 10

        await monitor._collect_metrics()

        # Should have generated a critical alert
        alerts = monitor.get_recent_alerts()
        assert len(alerts) > 0
        assert any(
            alert.severity == AlertSeverity.CRITICAL and "exhaustion" in alert.message.lower()
            for alert in alerts
        )

    @pytest.mark.asyncio
    async def test_high_latency_alert(self, monitor, mock_pool):
        """Test high latency alert."""
        # Set P95 latency above threshold
        mock_pool.stats.return_value.p95_acquire_time_ms = 150.0

        await monitor._collect_metrics()

        # Should have generated a latency alert
        alerts = monitor.get_recent_alerts()
        assert len(alerts) > 0
        assert any(
            "latency" in alert.message.lower()
            for alert in alerts
        )

    @pytest.mark.asyncio
    async def test_timeout_alert(self, monitor, mock_pool):
        """Test timeout alert when timeouts increase."""
        # First collection
        mock_pool.stats.return_value.total_timeouts = 0
        await monitor._collect_metrics()

        # Second collection with new timeouts
        mock_pool.stats.return_value.total_timeouts = 5
        await monitor._collect_metrics()

        # Should have generated a timeout alert
        alerts = monitor.get_recent_alerts()
        assert len(alerts) > 0
        assert any(
            "timeout" in alert.message.lower()
            for alert in alerts
        )

    @pytest.mark.asyncio
    async def test_health_failure_alert(self, monitor, mock_pool):
        """Test health failure alert when health checks fail."""
        # First collection
        mock_pool.stats.return_value.total_health_failures = 0
        await monitor._collect_metrics()

        # Second collection with new failures
        mock_pool.stats.return_value.total_health_failures = 3
        await monitor._collect_metrics()

        # Should have generated a health failure alert
        alerts = monitor.get_recent_alerts()
        assert len(alerts) > 0
        assert any(
            "health" in alert.message.lower() and "failure" in alert.message.lower()
            for alert in alerts
        )

    @pytest.mark.asyncio
    async def test_alert_callback_invoked(self, monitor, mock_pool):
        """Test that alert callback is invoked when alerts are raised."""
        callback_invoked = False
        received_alert = None

        async def alert_handler(alert):
            nonlocal callback_invoked, received_alert
            callback_invoked = True
            received_alert = alert

        monitor.alert_callback = alert_handler

        # Trigger an alert
        mock_pool.stats.return_value.active_connections = 10
        mock_pool.stats.return_value.pool_size = 10

        await monitor._collect_metrics()

        assert callback_invoked is True
        assert received_alert is not None
        assert isinstance(received_alert, PoolAlert)

    @pytest.mark.asyncio
    async def test_alerts_history_limit(self, monitor):
        """Test that alerts history is limited."""
        # Manually add many alerts
        for i in range(1100):
            monitor._alerts.append(
                PoolAlert(
                    severity=AlertSeverity.INFO,
                    message=f"Test alert {i}",
                )
            )

        await monitor._raise_alert(AlertSeverity.INFO, "New alert")

        # Should be limited to 1000
        assert len(monitor._alerts) == 1000


class TestMonitorStatistics:
    """Test monitor statistics."""

    @pytest.mark.asyncio
    async def test_get_stats(self, monitor):
        """Test get_stats returns correct statistics."""
        await monitor._collect_metrics()

        stats = monitor.get_stats()

        assert "running" in stats
        assert "total_collections" in stats
        assert "total_alerts" in stats
        assert "metrics_history_size" in stats
        assert "current_metrics" in stats

    @pytest.mark.asyncio
    async def test_stats_running_state(self, monitor):
        """Test that stats reflect running state."""
        stats = monitor.get_stats()
        assert stats["running"] is False

        await monitor.start()
        stats = monitor.get_stats()
        assert stats["running"] is True

        await monitor.stop()

    @pytest.mark.asyncio
    async def test_get_recent_alerts(self, monitor, mock_pool):
        """Test getting recent alerts."""
        # Generate some alerts
        mock_pool.stats.return_value.active_connections = 10
        mock_pool.stats.return_value.pool_size = 10
        await monitor._collect_metrics()

        alerts = monitor.get_recent_alerts(limit=10)

        assert len(alerts) > 0
        assert all(isinstance(alert, PoolAlert) for alert in alerts)

    def test_reset_stats(self, monitor):
        """Test resetting monitor statistics."""
        monitor.total_collections = 100
        monitor.total_alerts = 50

        monitor.reset_stats()

        assert monitor.total_collections == 0
        assert monitor.total_alerts == 0


class TestPoolAlert:
    """Test PoolAlert dataclass."""

    def test_alert_creation(self):
        """Test creating a PoolAlert."""
        alert = PoolAlert(
            severity=AlertSeverity.WARNING,
            message="Test alert",
            metric_name="test_metric",
            metric_value=42.0,
        )

        assert alert.severity == AlertSeverity.WARNING
        assert alert.message == "Test alert"
        assert alert.metric_name == "test_metric"
        assert alert.metric_value == 42.0
        assert isinstance(alert.timestamp, datetime)

    def test_alert_representation(self):
        """Test PoolAlert string representation."""
        alert = PoolAlert(
            severity=AlertSeverity.CRITICAL,
            message="Critical issue",
        )

        repr_str = repr(alert)
        assert "critical" in repr_str.lower()
        assert "Critical issue" in repr_str


class TestPoolMetrics:
    """Test PoolMetrics dataclass."""

    def test_metrics_creation(self):
        """Test creating a PoolMetrics snapshot."""
        metrics = PoolMetrics(
            timestamp=datetime.now(UTC),
            active_connections=5,
            idle_connections=3,
            total_connections=8,
            wait_queue_size=2,
            acquire_latency_p95_ms=25.0,
            acquire_latency_avg_ms=15.0,
            total_acquires=100,
            total_releases=95,
            total_timeouts=1,
            total_health_failures=0,
        )

        assert metrics.active_connections == 5
        assert metrics.idle_connections == 3
        assert metrics.total_connections == 8
        assert metrics.acquire_latency_p95_ms == 25.0
