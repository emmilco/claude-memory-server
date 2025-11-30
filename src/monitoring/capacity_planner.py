"""
Capacity planning module for predictive analytics and resource forecasting.

Analyzes historical metrics to forecast future capacity needs and
provides recommendations for scaling and optimization.
"""

import logging
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, UTC
from typing import List, Dict, Any, Optional, Literal
import statistics

from src.monitoring.metrics_collector import MetricsCollector, HealthMetrics

logger = logging.getLogger(__name__)


@dataclass
class DatabaseGrowthForecast:
    """Forecast for database growth."""

    current_size_mb: float
    projected_size_mb: float
    growth_rate_mb_per_day: float
    days_until_limit: Optional[int]  # Days until hitting a threshold (e.g., 2GB)
    status: Literal["HEALTHY", "WARNING", "CRITICAL"]
    trend: Literal["GROWING", "STABLE", "SHRINKING"]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


@dataclass
class MemoryCapacityAnalysis:
    """Analysis of memory capacity and projections."""

    current_memories: int
    projected_memories: int
    creation_rate_per_day: float
    days_until_limit: Optional[int]  # Days until hitting a threshold (e.g., 50k)
    status: Literal["HEALTHY", "WARNING", "CRITICAL"]
    trend: Literal["GROWING", "STABLE", "SHRINKING"]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


@dataclass
class ProjectCapacityReport:
    """Report on project capacity and resource usage."""

    current_active_projects: int
    current_total_projects: int
    projected_active_projects: int
    project_addition_rate_per_week: float
    days_until_limit: Optional[int]  # Days until hitting a threshold (e.g., 20 active)
    status: Literal["HEALTHY", "WARNING", "CRITICAL"]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


@dataclass
class CapacityForecast:
    """Comprehensive capacity forecast and recommendations."""

    forecast_days: int
    timestamp: datetime

    database_growth: DatabaseGrowthForecast
    memory_capacity: MemoryCapacityAnalysis
    project_capacity: ProjectCapacityReport

    recommendations: List[str]

    overall_status: Literal["HEALTHY", "WARNING", "CRITICAL"]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary with ISO timestamp."""
        result = {
            "forecast_days": self.forecast_days,
            "timestamp": self.timestamp.isoformat(),
            "database_growth": self.database_growth.to_dict(),
            "memory_capacity": self.memory_capacity.to_dict(),
            "project_capacity": self.project_capacity.to_dict(),
            "recommendations": self.recommendations,
            "overall_status": self.overall_status,
        }
        return result


class CapacityPlanner:
    """
    Capacity planning and resource forecasting.

    Responsibilities:
    - Forecast database growth trends
    - Analyze memory capacity and project future needs
    - Calculate project capacity limits
    - Generate recommendations for scaling/optimization
    - Provide early warnings for capacity issues
    """

    # Capacity thresholds
    DB_SIZE_WARNING_MB = 1500.0  # Warn at 1.5GB
    DB_SIZE_CRITICAL_MB = 2000.0  # Critical at 2GB

    MEMORY_COUNT_WARNING = 40000
    MEMORY_COUNT_CRITICAL = 50000

    PROJECT_COUNT_WARNING = 15
    PROJECT_COUNT_CRITICAL = 20

    # Growth rate thresholds (for status determination)
    GROWTH_THRESHOLD = 0.05  # 5% growth is considered "stable"

    def __init__(self, metrics_collector: MetricsCollector):
        """
        Initialize capacity planner.

        Args:
            metrics_collector: MetricsCollector instance for historical data
        """
        self.metrics_collector = metrics_collector

    async def get_capacity_forecast(self, days_ahead: int = 30) -> CapacityForecast:
        """
        Generate comprehensive capacity forecast.

        Args:
            days_ahead: Number of days to forecast ahead

        Returns:
            CapacityForecast with all projections and recommendations
        """
        # Get historical metrics for trend analysis
        historical_metrics = self.metrics_collector.get_metrics_history(days=30)

        if not historical_metrics:
            # No historical data - return current state with no projections
            latest = self.metrics_collector.get_latest_metrics()
            if not latest:
                # No data at all - return placeholder
                return self._create_no_data_forecast(days_ahead)

            return self._create_forecast_from_single_snapshot(latest, days_ahead)

        # Forecast database growth
        db_forecast = await self.forecast_database_growth(
            historical_metrics, days_ahead
        )

        # Analyze memory capacity
        memory_analysis = await self.analyze_memory_capacity(
            historical_metrics, days_ahead
        )

        # Calculate project capacity
        project_capacity = await self.calculate_project_capacity(
            historical_metrics, days_ahead
        )

        # Generate recommendations
        recommendations = self._generate_capacity_recommendations(
            db_forecast, memory_analysis, project_capacity
        )

        # Determine overall status
        overall_status = self._determine_overall_status(
            db_forecast, memory_analysis, project_capacity
        )

        return CapacityForecast(
            forecast_days=days_ahead,
            timestamp=datetime.now(UTC),
            database_growth=db_forecast,
            memory_capacity=memory_analysis,
            project_capacity=project_capacity,
            recommendations=recommendations,
            overall_status=overall_status,
        )

    async def forecast_database_growth(
        self,
        historical_metrics: List[HealthMetrics],
        days_ahead: int,
    ) -> DatabaseGrowthForecast:
        """
        Forecast database size growth using linear regression.

        Args:
            historical_metrics: Historical metrics for trend analysis
            days_ahead: Number of days to forecast

        Returns:
            DatabaseGrowthForecast with projections
        """
        if not historical_metrics:
            return DatabaseGrowthForecast(
                current_size_mb=0.0,
                projected_size_mb=0.0,
                growth_rate_mb_per_day=0.0,
                days_until_limit=None,
                status="HEALTHY",
                trend="STABLE",
            )

        # Extract database sizes and timestamps
        sizes = [m.database_size_mb for m in historical_metrics]
        current_size = sizes[-1] if sizes else 0.0

        # Calculate growth rate (MB/day) using linear regression
        growth_rate = self._calculate_linear_growth_rate(historical_metrics, "database_size_mb")

        # Project future size
        projected_size = current_size + (growth_rate * days_ahead)

        # Determine trend
        if abs(growth_rate) < 0.5:  # Less than 0.5 MB/day is stable
            trend = "STABLE"
        elif growth_rate > 0:
            trend = "GROWING"
        else:
            trend = "SHRINKING"

        # Calculate days until hitting limits
        days_until_limit = None
        status = "HEALTHY"

        if growth_rate > 0:
            if growth_rate == 0:
                days_to_warning = float('inf')
                days_to_critical = float('inf')
            else:
                days_to_warning = (self.DB_SIZE_WARNING_MB - current_size) / growth_rate
                days_to_critical = (self.DB_SIZE_CRITICAL_MB - current_size) / growth_rate

            if days_to_critical <= days_ahead:
                status = "CRITICAL"
                days_until_limit = int(days_to_critical)
            elif days_to_warning <= days_ahead:
                status = "WARNING"
                days_until_limit = int(days_to_warning)
            elif days_to_critical > 0:
                days_until_limit = int(days_to_critical)

        return DatabaseGrowthForecast(
            current_size_mb=current_size,
            projected_size_mb=max(0, projected_size),
            growth_rate_mb_per_day=growth_rate,
            days_until_limit=days_until_limit,
            status=status,
            trend=trend,
        )

    async def analyze_memory_capacity(
        self,
        historical_metrics: List[HealthMetrics],
        days_ahead: int,
    ) -> MemoryCapacityAnalysis:
        """
        Analyze memory capacity and forecast future needs.

        Args:
            historical_metrics: Historical metrics for trend analysis
            days_ahead: Number of days to forecast

        Returns:
            MemoryCapacityAnalysis with projections
        """
        if not historical_metrics:
            return MemoryCapacityAnalysis(
                current_memories=0,
                projected_memories=0,
                creation_rate_per_day=0.0,
                days_until_limit=None,
                status="HEALTHY",
                trend="STABLE",
            )

        # Extract memory counts
        counts = [m.total_memories for m in historical_metrics]
        current_count = counts[-1] if counts else 0

        # Calculate creation rate (memories/day) using linear regression
        creation_rate = self._calculate_linear_growth_rate(historical_metrics, "total_memories")

        # Project future count
        projected_count = current_count + (creation_rate * days_ahead)

        # Determine trend
        if abs(creation_rate) < 10:  # Less than 10 memories/day is stable
            trend = "STABLE"
        elif creation_rate > 0:
            trend = "GROWING"
        else:
            trend = "SHRINKING"

        # Calculate days until hitting limits
        days_until_limit = None
        status = "HEALTHY"

        if creation_rate > 0:
            if creation_rate == 0:
                days_to_warning = float('inf')
                days_to_critical = float('inf')
            else:
                days_to_warning = (self.MEMORY_COUNT_WARNING - current_count) / creation_rate
                days_to_critical = (self.MEMORY_COUNT_CRITICAL - current_count) / creation_rate

            if days_to_critical <= days_ahead:
                status = "CRITICAL"
                days_until_limit = int(days_to_critical)
            elif days_to_warning <= days_ahead:
                status = "WARNING"
                days_until_limit = int(days_to_warning)
            elif days_to_critical > 0:
                days_until_limit = int(days_to_critical)

        return MemoryCapacityAnalysis(
            current_memories=current_count,
            projected_memories=int(max(0, projected_count)),
            creation_rate_per_day=creation_rate,
            days_until_limit=days_until_limit,
            status=status,
            trend=trend,
        )

    async def calculate_project_capacity(
        self,
        historical_metrics: List[HealthMetrics],
        days_ahead: int,
    ) -> ProjectCapacityReport:
        """
        Calculate project capacity and resource usage.

        Args:
            historical_metrics: Historical metrics for trend analysis
            days_ahead: Number of days to forecast

        Returns:
            ProjectCapacityReport with capacity analysis
        """
        if not historical_metrics:
            return ProjectCapacityReport(
                current_active_projects=0,
                current_total_projects=0,
                projected_active_projects=0,
                project_addition_rate_per_week=0.0,
                days_until_limit=None,
                status="HEALTHY",
            )

        # Extract project counts
        active_counts = [m.active_projects for m in historical_metrics]
        current_active = active_counts[-1] if active_counts else 0

        total_counts = [m.active_projects + m.archived_projects for m in historical_metrics]
        current_total = total_counts[-1] if total_counts else 0

        # Calculate project addition rate (projects/day)
        addition_rate_per_day = self._calculate_linear_growth_rate(
            historical_metrics, "active_projects"
        )
        addition_rate_per_week = addition_rate_per_day * 7

        # Project future active project count
        projected_active = current_active + (addition_rate_per_day * days_ahead)

        # Calculate days until hitting limits
        days_until_limit = None
        status = "HEALTHY"

        if addition_rate_per_day > 0:
            if addition_rate_per_day == 0:
                days_to_warning = float('inf')
                days_to_critical = float('inf')
            else:
                days_to_warning = (self.PROJECT_COUNT_WARNING - current_active) / addition_rate_per_day
                days_to_critical = (self.PROJECT_COUNT_CRITICAL - current_active) / addition_rate_per_day

            if days_to_critical <= days_ahead:
                status = "CRITICAL"
                days_until_limit = int(days_to_critical)
            elif days_to_warning <= days_ahead:
                status = "WARNING"
                days_until_limit = int(days_to_warning)
            elif days_to_critical > 0:
                days_until_limit = int(days_to_critical)

        return ProjectCapacityReport(
            current_active_projects=current_active,
            current_total_projects=current_total,
            projected_active_projects=int(max(0, projected_active)),
            project_addition_rate_per_week=addition_rate_per_week,
            days_until_limit=days_until_limit,
            status=status,
        )

    def _calculate_linear_growth_rate(
        self,
        historical_metrics: List[HealthMetrics],
        metric_name: str,
    ) -> float:
        """
        Calculate growth rate using linear regression.

        Args:
            historical_metrics: Historical metrics
            metric_name: Name of metric to analyze

        Returns:
            Growth rate per day
        """
        if len(historical_metrics) < 2:
            return 0.0

        # Extract timestamps and values
        data_points = [
            (m.timestamp, getattr(m, metric_name, 0))
            for m in historical_metrics
        ]

        # Sort by timestamp
        data_points.sort(key=lambda x: x[0])

        # Calculate time deltas (in days from first point)
        start_time = data_points[0][0]
        x_values = [
            (timestamp - start_time).total_seconds() / 86400  # Convert to days
            for timestamp, _ in data_points
        ]
        y_values = [value for _, value in data_points]

        # Calculate linear regression slope (growth rate)
        if len(x_values) < 2:
            return 0.0

        # Simple linear regression: y = mx + b, solve for m (slope)
        n = len(x_values)
        sum_x = sum(x_values)
        sum_y = sum(y_values)
        sum_xy = sum(x * y for x, y in zip(x_values, y_values))
        sum_x_squared = sum(x * x for x in x_values)

        denominator = (n * sum_x_squared - sum_x * sum_x)
        if abs(denominator) < 1e-10:  # Avoid division by zero
            return 0.0

        slope = (n * sum_xy - sum_x * sum_y) / denominator

        return slope

    def _generate_capacity_recommendations(
        self,
        db_forecast: DatabaseGrowthForecast,
        memory_analysis: MemoryCapacityAnalysis,
        project_capacity: ProjectCapacityReport,
    ) -> List[str]:
        """Generate actionable capacity planning recommendations."""
        recommendations = []

        # Database size recommendations
        if db_forecast.status == "CRITICAL":
            recommendations.append(
                f"🔴 Database will exceed {self.DB_SIZE_CRITICAL_MB}MB in "
                f"{db_forecast.days_until_limit} days - immediate action required"
            )
            recommendations.append(
                "Archive old projects: claude-memory projects suggest-archive"
            )
            recommendations.append(
                "Run aggressive pruning: claude-memory prune --aggressive"
            )
        elif db_forecast.status == "WARNING":
            recommendations.append(
                f"⚠️ Database approaching capacity limit ({db_forecast.days_until_limit} days)"
            )
            recommendations.append(
                "Consider archiving inactive projects"
            )
        elif db_forecast.trend == "GROWING":
            recommendations.append(
                f"📈 Database growing at {db_forecast.growth_rate_mb_per_day:.2f} MB/day - monitor growth"
            )

        # Memory capacity recommendations
        if memory_analysis.status == "CRITICAL":
            recommendations.append(
                f"🔴 Memory count will exceed {self.MEMORY_COUNT_CRITICAL:,} in "
                f"{memory_analysis.days_until_limit} days"
            )
            recommendations.append(
                "Enable automatic lifecycle management to prune stale memories"
            )
        elif memory_analysis.status == "WARNING":
            recommendations.append(
                f"⚠️ High memory count approaching limit ({memory_analysis.days_until_limit} days)"
            )
            recommendations.append(
                "Review and archive old memories regularly"
            )

        # Project capacity recommendations
        if project_capacity.status == "CRITICAL":
            recommendations.append(
                f"🔴 Active project count will exceed {self.PROJECT_COUNT_CRITICAL} in "
                f"{project_capacity.days_until_limit} days"
            )
            recommendations.append(
                "Archive completed projects to free up capacity"
            )
        elif project_capacity.status == "WARNING":
            recommendations.append(
                f"⚠️ Many active projects ({project_capacity.current_active_projects})"
            )
            recommendations.append(
                "Review which projects are actively used"
            )

        # Default healthy recommendation
        if not recommendations:
            recommendations.append(
                "✅ All capacity metrics are healthy - continue monitoring"
            )

        return recommendations

    def _determine_overall_status(
        self,
        db_forecast: DatabaseGrowthForecast,
        memory_analysis: MemoryCapacityAnalysis,
        project_capacity: ProjectCapacityReport,
    ) -> Literal["HEALTHY", "WARNING", "CRITICAL"]:
        """Determine overall capacity status from components."""
        statuses = [
            db_forecast.status,
            memory_analysis.status,
            project_capacity.status,
        ]

        # Critical if any component is critical
        if "CRITICAL" in statuses:
            return "CRITICAL"

        # Warning if any component is warning
        if "WARNING" in statuses:
            return "WARNING"

        return "HEALTHY"

    def _create_no_data_forecast(self, days_ahead: int) -> CapacityForecast:
        """Create placeholder forecast when no data is available."""
        return CapacityForecast(
            forecast_days=days_ahead,
            timestamp=datetime.now(UTC),
            database_growth=DatabaseGrowthForecast(
                current_size_mb=0.0,
                projected_size_mb=0.0,
                growth_rate_mb_per_day=0.0,
                days_until_limit=None,
                status="HEALTHY",
                trend="STABLE",
            ),
            memory_capacity=MemoryCapacityAnalysis(
                current_memories=0,
                projected_memories=0,
                creation_rate_per_day=0.0,
                days_until_limit=None,
                status="HEALTHY",
                trend="STABLE",
            ),
            project_capacity=ProjectCapacityReport(
                current_active_projects=0,
                current_total_projects=0,
                projected_active_projects=0,
                project_addition_rate_per_week=0.0,
                days_until_limit=None,
                status="HEALTHY",
            ),
            recommendations=["No historical data available - begin collecting metrics"],
            overall_status="HEALTHY",
        )

    def _create_forecast_from_single_snapshot(
        self, metrics: HealthMetrics, days_ahead: int
    ) -> CapacityForecast:
        """Create forecast from single metrics snapshot (no growth projection)."""
        return CapacityForecast(
            forecast_days=days_ahead,
            timestamp=datetime.now(UTC),
            database_growth=DatabaseGrowthForecast(
                current_size_mb=metrics.database_size_mb,
                projected_size_mb=metrics.database_size_mb,  # No change projected
                growth_rate_mb_per_day=0.0,
                days_until_limit=None,
                status="HEALTHY",
                trend="STABLE",
            ),
            memory_capacity=MemoryCapacityAnalysis(
                current_memories=metrics.total_memories,
                projected_memories=metrics.total_memories,  # No change projected
                creation_rate_per_day=0.0,
                days_until_limit=None,
                status="HEALTHY",
                trend="STABLE",
            ),
            project_capacity=ProjectCapacityReport(
                current_active_projects=metrics.active_projects,
                current_total_projects=metrics.active_projects + metrics.archived_projects,
                projected_active_projects=metrics.active_projects,  # No change projected
                project_addition_rate_per_week=0.0,
                days_until_limit=None,
                status="HEALTHY",
            ),
            recommendations=[
                "Insufficient historical data for accurate forecasting - collecting more data"
            ],
            overall_status="HEALTHY",
        )
