"""Tests for HealthService - Health monitoring, metrics, and alerting.

This test suite covers:
- Performance metrics collection and retrieval
- Health score calculation
- Active alerts management
- Alert resolution
- Capacity forecasting
- Weekly report generation
- Dashboard server starting
- Metrics snapshot collection
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.services.health_service import HealthService
from src.config import ServerConfig
from src.core.exceptions import StorageError


class TestHealthServiceInit:
    """Test HealthService initialization."""

    def test_initialization_with_required_dependencies(self):
        """Test service initializes with required dependencies."""
        store = MagicMock()
        config = ServerConfig()

        service = HealthService(
            store=store,
            config=config,
        )

        assert service.store == store
        assert service.config == config
        assert service.metrics_collector is None
        assert service.alert_engine is None

    def test_initialization_with_all_dependencies(self):
        """Test service initializes with all dependencies."""
        store = MagicMock()
        config = ServerConfig()
        metrics_collector = MagicMock()
        alert_engine = MagicMock()
        health_reporter = MagicMock()
        capacity_planner = MagicMock()

        service = HealthService(
            store=store,
            config=config,
            metrics_collector=metrics_collector,
            alert_engine=alert_engine,
            health_reporter=health_reporter,
            capacity_planner=capacity_planner,
        )

        assert service.metrics_collector == metrics_collector
        assert service.alert_engine == alert_engine
        assert service.health_reporter == health_reporter
        assert service.capacity_planner == capacity_planner

    def test_initial_stats_are_zero(self):
        """Test service stats start at zero."""
        service = HealthService(
            store=MagicMock(),
            config=ServerConfig(),
        )

        stats = service.get_stats()
        assert stats["health_checks"] == 0
        assert stats["alerts_generated"] == 0
        assert stats["metrics_collected"] == 0


class TestSimpleHealthScore:
    """Test simple health score calculation."""

    @pytest.fixture
    def service(self):
        """Create service for health score tests."""
        return HealthService(
            store=MagicMock(),
            config=ServerConfig(),
        )

    def test_perfect_score_with_good_metrics(self, service):
        """Test perfect score with healthy metrics."""
        metrics = {
            "avg_latency_ms": 20,
            "error_rate": 0.0,
            "cache_hit_rate": 0.9,
        }

        score = service._calculate_simple_health_score(metrics)
        assert score == 100

    def test_penalized_high_latency(self, service):
        """Test score penalized for high latency."""
        # Moderate latency (50-100ms)
        metrics_moderate = {
            "avg_latency_ms": 75,
            "error_rate": 0,
            "cache_hit_rate": 1.0,
        }
        score_moderate = service._calculate_simple_health_score(metrics_moderate)
        assert score_moderate == 90  # -10 penalty

        # High latency (>100ms)
        metrics_high = {"avg_latency_ms": 150, "error_rate": 0, "cache_hit_rate": 1.0}
        score_high = service._calculate_simple_health_score(metrics_high)
        assert score_high == 80  # -20 penalty

    def test_penalized_high_error_rate(self, service):
        """Test score penalized for high error rate."""
        # Moderate error rate (5-10%)
        metrics_moderate = {
            "avg_latency_ms": 10,
            "error_rate": 0.07,
            "cache_hit_rate": 1.0,
        }
        score_moderate = service._calculate_simple_health_score(metrics_moderate)
        assert score_moderate == 85  # -15 penalty

        # High error rate (>10%)
        metrics_high = {"avg_latency_ms": 10, "error_rate": 0.15, "cache_hit_rate": 1.0}
        score_high = service._calculate_simple_health_score(metrics_high)
        assert score_high == 70  # -30 penalty

    def test_penalized_low_cache_hit_rate(self, service):
        """Test score penalized for low cache hit rate."""
        metrics = {"avg_latency_ms": 10, "error_rate": 0, "cache_hit_rate": 0.3}
        score = service._calculate_simple_health_score(metrics)
        assert score == 90  # -10 penalty

    def test_combined_penalties(self, service):
        """Test score with multiple penalties."""
        metrics = {
            "avg_latency_ms": 150,  # -20
            "error_rate": 0.15,  # -30
            "cache_hit_rate": 0.3,  # -10
        }
        score = service._calculate_simple_health_score(metrics)
        assert score == 40  # 100 - 20 - 30 - 10

    def test_score_clamped_to_zero(self, service):
        """Test score doesn't go below zero."""
        metrics = {
            "avg_latency_ms": 500,
            "error_rate": 0.5,
            "cache_hit_rate": 0.1,
        }
        score = service._calculate_simple_health_score(metrics)
        assert score >= 0


class TestGetPerformanceMetrics:
    """Test get_performance_metrics method."""

    @pytest.fixture
    def service(self):
        """Create service with metrics collector."""
        metrics_collector = MagicMock()
        metrics_collector.get_current_metrics.return_value = {
            "avg_latency_ms": 25,
            "queries_per_second": 100,
        }
        metrics_collector.get_historical_metrics.return_value = [
            {"date": "2024-01-01", "avg_latency_ms": 30},
        ]

        return HealthService(
            store=MagicMock(),
            config=ServerConfig(),
            metrics_collector=metrics_collector,
        )

    @pytest.mark.asyncio
    async def test_metrics_without_collector_returns_disabled(self):
        """Test getting metrics without collector returns disabled."""
        service = HealthService(
            store=MagicMock(),
            config=ServerConfig(),
            metrics_collector=None,
        )

        result = await service.get_performance_metrics()

        assert result["status"] == "disabled"

    @pytest.mark.asyncio
    async def test_metrics_success(self, service):
        """Test successful metrics retrieval."""
        result = await service.get_performance_metrics(include_history_days=7)

        assert result["status"] == "success"
        assert "current" in result
        assert "historical" in result
        assert result["period_days"] == 7

    @pytest.mark.asyncio
    async def test_metrics_increments_health_checks(self, service):
        """Test metrics retrieval increments health checks stat."""
        initial_stats = service.get_stats()
        await service.get_performance_metrics()

        stats = service.get_stats()
        assert stats["health_checks"] == initial_stats["health_checks"] + 1


class TestGetHealthScore:
    """Test get_health_score method."""

    @pytest.fixture
    def service(self):
        """Create service for health score tests."""
        store = AsyncMock()
        store.health_check = AsyncMock(return_value=True)

        return HealthService(
            store=store,
            config=ServerConfig(),
        )

    @pytest.mark.asyncio
    async def test_health_score_basic(self, service):
        """Test basic health score retrieval."""
        result = await service.get_health_score()

        assert result["status"] == "success"
        assert "health_score" in result
        assert "store_available" in result
        assert result["store_available"] is True

    @pytest.mark.asyncio
    async def test_health_score_with_reporter(self, service):
        """Test health score with health reporter."""
        health_reporter = MagicMock()
        health_reporter.get_health_report.return_value = {
            "overall_score": 95,
            "components": {
                "store": "healthy",
                "cache": "healthy",
            },
        }
        service.health_reporter = health_reporter

        result = await service.get_health_score()

        assert result["health_score"] == 95
        assert "store" in result["components"]

    @pytest.mark.asyncio
    async def test_health_score_without_reporter(self, service):
        """Test health score calculated without reporter."""
        metrics_collector = MagicMock()
        metrics_collector.get_current_metrics.return_value = {
            "avg_latency_ms": 20,
            "error_rate": 0.0,
            "cache_hit_rate": 0.9,
        }
        service.metrics_collector = metrics_collector

        result = await service.get_health_score()

        assert result["health_score"] == 100

    @pytest.mark.asyncio
    async def test_health_status_healthy(self, service):
        """Test healthy status for high score."""
        service.health_reporter = None
        service.metrics_collector = None  # Will calculate default score

        result = await service.get_health_score()

        assert result["health_status"] == "healthy"

    @pytest.mark.asyncio
    async def test_health_score_store_unavailable(self, service):
        """Test health score when store is unavailable."""
        service.store.health_check = AsyncMock(return_value=False)

        result = await service.get_health_score()

        assert result["store_available"] is False
        assert result["components"]["store"] == "unhealthy"


class TestGetActiveAlerts:
    """Test get_active_alerts method."""

    @pytest.fixture
    def service(self):
        """Create service with alert engine."""
        alert_engine = MagicMock()
        alert_engine.get_active_alerts.return_value = [
            {"id": "alert1", "severity": "WARNING", "message": "High latency"},
            {"id": "alert2", "severity": "CRITICAL", "message": "Database error"},
        ]

        return HealthService(
            store=MagicMock(),
            config=ServerConfig(),
            alert_engine=alert_engine,
        )

    @pytest.mark.asyncio
    async def test_alerts_without_engine_returns_disabled(self):
        """Test getting alerts without engine returns disabled."""
        service = HealthService(
            store=MagicMock(),
            config=ServerConfig(),
            alert_engine=None,
        )

        result = await service.get_active_alerts()

        assert result["status"] == "disabled"
        assert result["alerts"] == []

    @pytest.mark.asyncio
    async def test_alerts_success(self, service):
        """Test successful alerts retrieval."""
        result = await service.get_active_alerts()

        assert result["status"] == "success"
        assert len(result["alerts"]) == 2
        assert result["total_count"] == 2

    @pytest.mark.asyncio
    async def test_alerts_with_severity_filter(self, service):
        """Test alerts with severity filter."""
        await service.get_active_alerts(severity_filter="CRITICAL")

        service.alert_engine.get_active_alerts.assert_called_with(
            severity_filter="CRITICAL"
        )


class TestResolveAlert:
    """Test resolve_alert method."""

    @pytest.fixture
    def service(self):
        """Create service with alert engine."""
        alert_engine = MagicMock()
        alert_engine.resolve_alert.return_value = True

        return HealthService(
            store=MagicMock(),
            config=ServerConfig(),
            alert_engine=alert_engine,
        )

    @pytest.mark.asyncio
    async def test_resolve_without_engine_returns_disabled(self):
        """Test resolving without engine returns disabled."""
        service = HealthService(
            store=MagicMock(),
            config=ServerConfig(),
            alert_engine=None,
        )

        result = await service.resolve_alert("alert1")

        assert result["status"] == "disabled"

    @pytest.mark.asyncio
    async def test_resolve_success(self, service):
        """Test successful alert resolution."""
        result = await service.resolve_alert("alert1")

        assert result["status"] == "success"
        assert result["alert_id"] == "alert1"
        assert result["action"] == "resolved"

    @pytest.mark.asyncio
    async def test_resolve_not_found(self, service):
        """Test resolving non-existent alert."""
        service.alert_engine.resolve_alert.return_value = False

        result = await service.resolve_alert("nonexistent")

        assert result["status"] == "not_found"


class TestGetCapacityForecast:
    """Test get_capacity_forecast method."""

    @pytest.fixture
    def service(self):
        """Create service with capacity planner."""
        capacity_planner = MagicMock()
        capacity_planner.get_forecast.return_value = {
            "projected_memory_usage": 0.85,
            "projected_storage": 500,
            "recommendations": ["Consider scaling storage"],
        }

        return HealthService(
            store=MagicMock(),
            config=ServerConfig(),
            capacity_planner=capacity_planner,
        )

    @pytest.mark.asyncio
    async def test_forecast_without_planner_returns_disabled(self):
        """Test forecast without planner returns disabled."""
        service = HealthService(
            store=MagicMock(),
            config=ServerConfig(),
            capacity_planner=None,
        )

        result = await service.get_capacity_forecast()

        assert result["status"] == "disabled"

    @pytest.mark.asyncio
    async def test_forecast_success(self, service):
        """Test successful capacity forecast."""
        result = await service.get_capacity_forecast(days_ahead=30)

        assert result["status"] == "success"
        assert "forecast" in result
        assert result["days_ahead"] == 30


class TestGetWeeklyReport:
    """Test get_weekly_report method."""

    @pytest.fixture
    def service(self):
        """Create service for weekly report tests."""
        store = AsyncMock()
        store.health_check = AsyncMock(return_value=True)

        metrics_collector = MagicMock()
        metrics_collector.get_current_metrics.return_value = {
            "avg_latency_ms": 25,
        }
        metrics_collector.get_historical_metrics.return_value = []

        return HealthService(
            store=store,
            config=ServerConfig(),
            metrics_collector=metrics_collector,
        )

    @pytest.mark.asyncio
    async def test_weekly_report_without_reporter(self, service):
        """Test weekly report generated without reporter."""
        result = await service.get_weekly_report()

        assert result["status"] == "success"
        assert result["period"] == "weekly"
        assert result["generated_by"] == "basic_reporter"

    @pytest.mark.asyncio
    async def test_weekly_report_with_reporter(self, service):
        """Test weekly report with health reporter."""
        health_reporter = MagicMock()
        health_reporter.generate_weekly_report.return_value = {
            "overall_health": "good",
            "key_metrics": {},
            "recommendations": [],
        }
        service.health_reporter = health_reporter

        result = await service.get_weekly_report()

        assert result["status"] == "success"
        assert result["period"] == "weekly"
        assert "overall_health" in result


class TestStartDashboard:
    """Test start_dashboard method."""

    @pytest.fixture
    def service(self):
        """Create service for dashboard tests."""
        return HealthService(
            store=MagicMock(),
            config=ServerConfig(),
        )

    @pytest.mark.asyncio
    @pytest.mark.skip(
        reason="DashboardServer class not available - needs implementation"
    )
    async def test_start_dashboard_success(self, service):
        """Test successful dashboard start."""
        with patch("src.dashboard.web_server.DashboardServer") as MockServer:
            mock_server = AsyncMock()
            mock_server.start = AsyncMock()
            MockServer.return_value = mock_server

            result = await service.start_dashboard(port=8080, host="localhost")

            assert result["status"] == "success"
            assert result["url"] == "http://localhost:8080"
            assert result["port"] == 8080

    @pytest.mark.asyncio
    @pytest.mark.skip(
        reason="DashboardServer class not available - needs implementation"
    )
    async def test_start_dashboard_custom_host_port(self, service):
        """Test dashboard with custom host and port."""
        with patch("src.dashboard.web_server.DashboardServer") as MockServer:
            mock_server = AsyncMock()
            mock_server.start = AsyncMock()
            MockServer.return_value = mock_server

            result = await service.start_dashboard(port=9000, host="0.0.0.0")

            assert result["url"] == "http://0.0.0.0:9000"
            assert result["host"] == "0.0.0.0"
            assert result["port"] == 9000

    @pytest.mark.asyncio
    @pytest.mark.skip(
        reason="DashboardServer class not available - needs implementation"
    )
    async def test_start_dashboard_error_raises(self, service):
        """Test dashboard start error raises StorageError."""
        with patch("src.dashboard.web_server.DashboardServer") as MockServer:
            MockServer.side_effect = Exception("Failed to start")

            with pytest.raises(StorageError):
                await service.start_dashboard()


class TestCollectMetricsSnapshot:
    """Test collect_metrics_snapshot method."""

    @pytest.fixture
    def service(self):
        """Create service with metrics collector."""
        metrics_collector = MagicMock()
        metrics_collector.collect_snapshot = MagicMock()

        return HealthService(
            store=MagicMock(),
            config=ServerConfig(),
            metrics_collector=metrics_collector,
        )

    @pytest.mark.asyncio
    async def test_collect_snapshot_with_collector(self, service):
        """Test collecting snapshot with collector."""
        initial_stats = service.get_stats()
        await service.collect_metrics_snapshot()

        service.metrics_collector.collect_snapshot.assert_called_once()
        stats = service.get_stats()
        assert stats["metrics_collected"] == initial_stats["metrics_collected"] + 1

    @pytest.mark.asyncio
    async def test_collect_snapshot_without_collector(self):
        """Test collecting snapshot without collector does nothing."""
        service = HealthService(
            store=MagicMock(),
            config=ServerConfig(),
            metrics_collector=None,
        )

        # Should not raise
        await service.collect_metrics_snapshot()


class TestErrorHandling:
    """Test error handling in health service."""

    @pytest.fixture
    def service(self):
        """Create service with failing components."""
        store = AsyncMock()
        store.health_check = AsyncMock(side_effect=Exception("Connection failed"))

        return HealthService(
            store=store,
            config=ServerConfig(),
        )

    @pytest.mark.asyncio
    async def test_health_score_error_raises(self, service):
        """Test health score error raises StorageError."""
        with pytest.raises(StorageError):
            await service.get_health_score()

    @pytest.mark.asyncio
    async def test_performance_metrics_error_raises(self):
        """Test performance metrics error raises StorageError."""
        metrics_collector = MagicMock()
        metrics_collector.get_current_metrics.side_effect = Exception("Metrics error")

        service = HealthService(
            store=MagicMock(),
            config=ServerConfig(),
            metrics_collector=metrics_collector,
        )

        with pytest.raises(StorageError):
            await service.get_performance_metrics()

    @pytest.mark.asyncio
    async def test_alerts_error_raises(self):
        """Test alerts retrieval error raises StorageError."""
        alert_engine = MagicMock()
        alert_engine.get_active_alerts.side_effect = Exception("Alert engine error")

        service = HealthService(
            store=MagicMock(),
            config=ServerConfig(),
            alert_engine=alert_engine,
        )

        with pytest.raises(StorageError):
            await service.get_active_alerts()

    @pytest.mark.asyncio
    async def test_weekly_report_error_raises(self):
        """Test weekly report error raises StorageError."""
        health_reporter = MagicMock()
        health_reporter.generate_weekly_report.side_effect = Exception("Report error")

        store = AsyncMock()
        store.health_check = AsyncMock(side_effect=Exception("Store error"))

        service = HealthService(
            store=store,
            config=ServerConfig(),
            health_reporter=health_reporter,
        )

        with pytest.raises(StorageError):
            await service.get_weekly_report()


class TestIntegrationScenarios:
    """Test integration scenarios for health service."""

    @pytest.fixture
    def fully_configured_service(self):
        """Create fully configured service."""
        store = AsyncMock()
        store.health_check = AsyncMock(return_value=True)

        metrics_collector = MagicMock()
        metrics_collector.get_current_metrics.return_value = {
            "avg_latency_ms": 30,
            "error_rate": 0.01,
            "cache_hit_rate": 0.85,
        }
        metrics_collector.get_historical_metrics.return_value = []
        metrics_collector.collect_snapshot = MagicMock()

        alert_engine = MagicMock()
        alert_engine.get_active_alerts.return_value = []
        alert_engine.resolve_alert.return_value = True

        health_reporter = MagicMock()
        health_reporter.get_health_report.return_value = {
            "overall_score": 95,
            "components": {"store": "healthy", "cache": "healthy"},
        }
        health_reporter.generate_weekly_report.return_value = {
            "overall_health": "good",
        }

        capacity_planner = MagicMock()
        capacity_planner.get_forecast.return_value = {
            "projected_memory_usage": 0.75,
        }

        return HealthService(
            store=store,
            config=ServerConfig(),
            metrics_collector=metrics_collector,
            alert_engine=alert_engine,
            health_reporter=health_reporter,
            capacity_planner=capacity_planner,
        )

    @pytest.mark.asyncio
    async def test_full_health_check_workflow(self, fully_configured_service):
        """Test complete health check workflow."""
        service = fully_configured_service

        # Get health score
        health = await service.get_health_score()
        assert health["status"] == "success"
        assert health["health_score"] == 95

        # Get metrics
        metrics = await service.get_performance_metrics()
        assert metrics["status"] == "success"

        # Get alerts
        alerts = await service.get_active_alerts()
        assert alerts["status"] == "success"

        # Get forecast
        forecast = await service.get_capacity_forecast()
        assert forecast["status"] == "success"

        # Get weekly report
        report = await service.get_weekly_report()
        assert report["status"] == "success"

    @pytest.mark.asyncio
    async def test_health_monitoring_over_time(self, fully_configured_service):
        """Test health monitoring accumulates stats."""
        service = fully_configured_service

        # Perform multiple health operations
        for _ in range(3):
            await service.get_health_score()
            await service.get_performance_metrics()
            await service.collect_metrics_snapshot()

        stats = service.get_stats()
        assert (
            stats["health_checks"] == 6
        )  # 3 from get_health_score + 3 from get_performance_metrics
        assert stats["metrics_collected"] == 3
