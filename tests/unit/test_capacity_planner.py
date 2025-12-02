"""Tests for CapacityPlanner (FEAT-022)."""

import pytest
from datetime import datetime, timedelta, UTC
from src.monitoring.capacity_planner import (
    CapacityPlanner,
)
from src.monitoring.metrics_collector import MetricsCollector, HealthMetrics


@pytest.fixture
def temp_db(tmp_path):
    """Create temporary metrics database."""
    db_path = str(tmp_path / "test_metrics.db")
    return db_path


@pytest.fixture
def metrics_collector(temp_db):
    """Create MetricsCollector instance."""
    return MetricsCollector(db_path=temp_db, store=None)


@pytest.fixture
def capacity_planner(metrics_collector):
    """Create CapacityPlanner instance."""
    return CapacityPlanner(metrics_collector)


class TestCapacityPlanner:
    """Test CapacityPlanner functionality."""

    @pytest.mark.asyncio
    async def test_no_data_forecast(self, capacity_planner):
        """Test forecast with no historical data."""
        forecast = await capacity_planner.get_capacity_forecast(days_ahead=30)

        assert forecast.forecast_days == 30
        assert forecast.overall_status == "HEALTHY"
        assert forecast.database_growth.current_size_mb == 0.0
        assert forecast.memory_capacity.current_memories == 0
        assert "No historical data available" in forecast.recommendations[0]

    @pytest.mark.asyncio
    async def test_database_growth_forecast(self, capacity_planner, metrics_collector):
        """Test database growth forecasting with linear trend."""
        # Create historical metrics with growth trend
        base_time = datetime.now(UTC) - timedelta(days=30)
        for i in range(30):
            metrics = HealthMetrics(
                timestamp=base_time + timedelta(days=i),
                database_size_mb=100.0 + (i * 2.0),  # Growing at 2MB/day
                total_memories=1000 + (i * 10),  # Growing at 10 memories/day
                active_memories=500,
                recent_memories=300,
                archived_memories=150,
                stale_memories=50,
                active_projects=3,
                archived_projects=1,
            )
            metrics_collector.store_metrics(metrics)

        forecast = await capacity_planner.get_capacity_forecast(days_ahead=30)

        # Database should be growing
        assert forecast.database_growth.trend == "GROWING"
        assert forecast.database_growth.growth_rate_mb_per_day > 0
        assert (
            forecast.database_growth.projected_size_mb
            > forecast.database_growth.current_size_mb
        )

    @pytest.mark.asyncio
    async def test_memory_capacity_forecast(self, capacity_planner, metrics_collector):
        """Test memory capacity forecasting."""
        # Create metrics with stable memory count
        base_time = datetime.now(UTC) - timedelta(days=15)
        for i in range(15):
            metrics = HealthMetrics(
                timestamp=base_time + timedelta(days=i),
                database_size_mb=100.0,
                total_memories=1000,  # Stable count
                active_memories=500,
                recent_memories=300,
                archived_memories=150,
                stale_memories=50,
                active_projects=2,
                archived_projects=1,
            )
            metrics_collector.store_metrics(metrics)

        forecast = await capacity_planner.get_capacity_forecast(days_ahead=30)

        # Memory count should be stable
        assert forecast.memory_capacity.trend == "STABLE"
        assert abs(forecast.memory_capacity.creation_rate_per_day) < 10

    @pytest.mark.asyncio
    async def test_capacity_warnings(self, capacity_planner, metrics_collector):
        """Test capacity warning thresholds."""
        # Create metrics approaching database size limit
        base_time = datetime.now(UTC) - timedelta(days=10)
        for i in range(10):
            metrics = HealthMetrics(
                timestamp=base_time + timedelta(days=i),
                database_size_mb=1400.0
                + (i * 10.0),  # Growing rapidly toward 1500MB warning
                total_memories=1000 + (i * 100),
                active_memories=500,
                recent_memories=300,
                archived_memories=150,
                stale_memories=50,
                active_projects=2,
                archived_projects=1,
            )
            metrics_collector.store_metrics(metrics)

        forecast = await capacity_planner.get_capacity_forecast(days_ahead=30)

        # Should warn about database growth
        assert forecast.database_growth.status in ["WARNING", "CRITICAL"]
        assert forecast.overall_status in ["WARNING", "CRITICAL"]
        assert any("database" in rec.lower() for rec in forecast.recommendations)

    @pytest.mark.asyncio
    async def test_project_capacity(self, capacity_planner, metrics_collector):
        """Test project capacity forecasting."""
        # Create metrics with increasing project count
        base_time = datetime.now(UTC) - timedelta(days=20)
        for i in range(20):
            metrics = HealthMetrics(
                timestamp=base_time + timedelta(days=i),
                database_size_mb=100.0,
                total_memories=1000,
                active_memories=500,
                recent_memories=300,
                archived_memories=150,
                stale_memories=50,
                active_projects=5 + i,  # Adding 1 project/day
                archived_projects=2,
            )
            metrics_collector.store_metrics(metrics)

        forecast = await capacity_planner.get_capacity_forecast(days_ahead=30)

        # Projects should be growing
        assert forecast.project_capacity.project_addition_rate_per_week > 0
        assert (
            forecast.project_capacity.projected_active_projects
            > forecast.project_capacity.current_active_projects
        )

    @pytest.mark.asyncio
    async def test_forecast_different_periods(
        self, capacity_planner, metrics_collector
    ):
        """Test forecasting for different time periods."""
        # Add some baseline metrics
        base_time = datetime.now(UTC) - timedelta(days=10)
        for i in range(10):
            metrics = HealthMetrics(
                timestamp=base_time + timedelta(days=i),
                database_size_mb=100.0 + i,
                total_memories=1000 + (i * 10),
                active_memories=500,
                recent_memories=300,
                archived_memories=150,
                stale_memories=50,
                active_projects=3,
                archived_projects=1,
            )
            metrics_collector.store_metrics(metrics)

        # Test 7-day forecast
        forecast_7 = await capacity_planner.get_capacity_forecast(days_ahead=7)
        assert forecast_7.forecast_days == 7

        # Test 90-day forecast
        forecast_90 = await capacity_planner.get_capacity_forecast(days_ahead=90)
        assert forecast_90.forecast_days == 90

        # 90-day projection should be larger than 7-day
        assert (
            forecast_90.database_growth.projected_size_mb
            >= forecast_7.database_growth.projected_size_mb
        )


class TestLinearRegressionCalculation:
    """Test linear regression calculations."""

    def test_calculate_growth_rate_single_point(
        self, capacity_planner, metrics_collector
    ):
        """Test growth rate with single data point."""
        metrics = HealthMetrics(
            timestamp=datetime.now(UTC),
            database_size_mb=100.0,
            total_memories=1000,
            active_memories=500,
            recent_memories=300,
            archived_memories=150,
            stale_memories=50,
            active_projects=3,
            archived_projects=1,
        )
        metrics_collector.store_metrics(metrics)

        history = metrics_collector.get_metrics_history(days=7)
        growth_rate = capacity_planner._calculate_linear_growth_rate(
            history, "database_size_mb"
        )

        # Single point should yield zero growth rate
        assert growth_rate == 0.0

    def test_calculate_growth_rate_upward_trend(
        self, capacity_planner, metrics_collector
    ):
        """Test growth rate with upward trend."""
        base_time = datetime.now(UTC) - timedelta(days=10)
        for i in range(10):
            metrics = HealthMetrics(
                timestamp=base_time + timedelta(days=i),
                database_size_mb=100.0 + (i * 5.0),  # 5MB/day growth
                total_memories=1000,
                active_memories=500,
                recent_memories=300,
                archived_memories=150,
                stale_memories=50,
                active_projects=3,
                archived_projects=1,
            )
            metrics_collector.store_metrics(metrics)

        history = metrics_collector.get_metrics_history(days=10)
        growth_rate = capacity_planner._calculate_linear_growth_rate(
            history, "database_size_mb"
        )

        # Should detect ~5MB/day growth
        assert 4.5 <= growth_rate <= 5.5

    def test_calculate_growth_rate_downward_trend(
        self, capacity_planner, metrics_collector
    ):
        """Test growth rate with downward trend."""
        base_time = datetime.now(UTC) - timedelta(days=10)
        for i in range(10):
            metrics = HealthMetrics(
                timestamp=base_time + timedelta(days=i),
                total_memories=2000 - (i * 20),  # Decreasing by 20/day
                database_size_mb=100.0,
                active_memories=500,
                recent_memories=300,
                archived_memories=150,
                stale_memories=50,
                active_projects=3,
                archived_projects=1,
            )
            metrics_collector.store_metrics(metrics)

        history = metrics_collector.get_metrics_history(days=10)
        growth_rate = capacity_planner._calculate_linear_growth_rate(
            history, "total_memories"
        )

        # Should detect negative growth
        assert growth_rate < 0
        assert -25 <= growth_rate <= -15


class TestCapacityRecommendations:
    """Test capacity recommendation generation."""

    @pytest.mark.asyncio
    async def test_healthy_recommendations(self, capacity_planner, metrics_collector):
        """Test recommendations for healthy system."""
        # Add stable metrics
        base_time = datetime.now(UTC) - timedelta(days=5)
        for i in range(5):
            metrics = HealthMetrics(
                timestamp=base_time + timedelta(days=i),
                database_size_mb=100.0,  # Stable
                total_memories=1000,  # Stable
                active_memories=500,
                recent_memories=300,
                archived_memories=150,
                stale_memories=50,
                active_projects=3,  # Stable
                archived_projects=1,
            )
            metrics_collector.store_metrics(metrics)

        forecast = await capacity_planner.get_capacity_forecast(days_ahead=30)

        # Should have healthy status and recommendation
        assert forecast.overall_status == "HEALTHY"
        assert any("healthy" in rec.lower() for rec in forecast.recommendations)

    @pytest.mark.asyncio
    async def test_critical_recommendations(self, capacity_planner, metrics_collector):
        """Test recommendations for critical capacity issues."""
        # Add metrics with critical growth
        base_time = datetime.now(UTC) - timedelta(days=10)
        for i in range(10):
            metrics = HealthMetrics(
                timestamp=base_time + timedelta(days=i),
                database_size_mb=1900.0
                + (i * 20.0),  # Approaching 2000MB limit rapidly
                total_memories=48000 + (i * 500),  # Approaching 50000 limit
                active_memories=500,
                recent_memories=300,
                archived_memories=150,
                stale_memories=50,
                active_projects=18 + i,  # Approaching 20 limit
                archived_projects=1,
            )
            metrics_collector.store_metrics(metrics)

        forecast = await capacity_planner.get_capacity_forecast(days_ahead=7)

        # Should have critical status
        assert forecast.overall_status == "CRITICAL"
        # Should have actionable recommendations
        assert len(forecast.recommendations) > 1
        assert any(
            "🔴" in rec or "immediate" in rec.lower()
            for rec in forecast.recommendations
        )
