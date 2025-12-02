"""
Health reporting and scoring system.

Generates health scores, weekly reports, and trend analysis
for the memory database.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from enum import Enum

from src.monitoring.metrics_collector import HealthMetrics
from src.monitoring.alert_engine import Alert, AlertSeverity


# Trend analysis thresholds (percentage change)
TREND_SIGNIFICANT_CHANGE = 5.0  # % change to consider trend significant
TREND_HIGHLY_SIGNIFICANT = 10.0  # % change to flag as highly significant


class HealthStatus(str, Enum):
    """Overall health status categories."""

    EXCELLENT = "EXCELLENT"
    GOOD = "GOOD"
    FAIR = "FAIR"
    POOR = "POOR"
    CRITICAL = "CRITICAL"


@dataclass
class HealthScore:
    """Comprehensive health score with component breakdown."""

    overall_score: int  # 0-100
    status: HealthStatus

    # Component scores
    performance_score: int  # 0-100
    quality_score: int  # 0-100
    database_health_score: int  # 0-100
    usage_efficiency_score: int  # 0-100

    # Metadata
    timestamp: datetime
    total_alerts: int
    critical_alerts: int
    warning_alerts: int


@dataclass
class TrendAnalysis:
    """Trend analysis for a specific metric."""

    metric_name: str
    current_value: float
    previous_value: float
    change_percent: float
    direction: str  # "improving", "degrading", "stable"
    is_significant: bool  # Change > 10%


@dataclass
class WeeklyReport:
    """Weekly health report with trends and recommendations."""

    period_start: datetime
    period_end: datetime

    current_health: HealthScore
    previous_health: Optional[HealthScore]

    trends: List[TrendAnalysis]
    improvements: List[str]
    concerns: List[str]
    recommendations: List[str]

    usage_summary: Dict[str, Any]
    alert_summary: Dict[str, int]


class HealthReporter:
    """
    Generates health scores and reports from metrics.

    Responsibilities:
    - Calculate overall health score (0-100)
    - Break down scores by component
    - Generate weekly health reports
    - Analyze trends (improvements/regressions)
    - Provide actionable recommendations
    """

    # Score weighting
    PERFORMANCE_WEIGHT = 0.30
    QUALITY_WEIGHT = 0.40
    DB_HEALTH_WEIGHT = 0.20
    USAGE_WEIGHT = 0.10

    def calculate_health_score(
        self, metrics: HealthMetrics, alerts: List[Alert]
    ) -> HealthScore:
        """
        Calculate comprehensive health score.

        Args:
            metrics: Current health metrics
            alerts: Active alerts

        Returns:
            HealthScore with overall and component scores
        """
        # Calculate component scores
        performance_score = self._calculate_performance_score(metrics)
        quality_score = self._calculate_quality_score(metrics)
        db_health_score = self._calculate_db_health_score(metrics)
        usage_score = self._calculate_usage_score(metrics)

        # Calculate weighted overall score
        overall_score = int(
            performance_score * self.PERFORMANCE_WEIGHT
            + quality_score * self.QUALITY_WEIGHT
            + db_health_score * self.DB_HEALTH_WEIGHT
            + usage_score * self.USAGE_WEIGHT
        )

        # Apply alert penalty
        overall_score = self._apply_alert_penalty(overall_score, alerts)

        # Determine status
        status = self._score_to_status(overall_score)

        # Count alerts by severity
        critical_count = sum(1 for a in alerts if a.severity == AlertSeverity.CRITICAL)
        warning_count = sum(1 for a in alerts if a.severity == AlertSeverity.WARNING)

        return HealthScore(
            overall_score=overall_score,
            status=status,
            performance_score=performance_score,
            quality_score=quality_score,
            database_health_score=db_health_score,
            usage_efficiency_score=usage_score,
            timestamp=metrics.timestamp,
            total_alerts=len(alerts),
            critical_alerts=critical_count,
            warning_alerts=warning_count,
        )

    def _calculate_performance_score(self, metrics: HealthMetrics) -> int:
        """
        Calculate performance component score.

        Factors:
        - Search latency (50%)
        - Cache hit rate (30%)
        - Index staleness (20%)
        """
        # Latency score (lower is better)
        # Excellent: <20ms, Good: 20-50ms, Poor: >50ms
        if metrics.avg_search_latency_ms < 20:
            latency_score = 100
        elif metrics.avg_search_latency_ms < 50:
            latency_score = 80 - int((metrics.avg_search_latency_ms - 20) * 2)
        else:
            latency_score = max(0, 80 - int((metrics.avg_search_latency_ms - 50) * 1.5))

        # Cache hit rate score
        cache_score = int(metrics.cache_hit_rate * 100)

        # Index staleness score (lower staleness is better)
        staleness_score = int((1 - metrics.index_staleness_ratio) * 100)

        return int(latency_score * 0.5 + cache_score * 0.3 + staleness_score * 0.2)

    def _calculate_quality_score(self, metrics: HealthMetrics) -> int:
        """
        Calculate quality component score.

        Factors:
        - Average relevance (60%)
        - Noise ratio (30%)
        - Duplicate/contradiction rate (10%)
        """
        # Relevance score
        # Excellent: >0.8, Good: 0.6-0.8, Poor: <0.6
        relevance_score = int(metrics.avg_result_relevance * 100)

        # Noise score (lower is better)
        noise_score = int((1 - metrics.noise_ratio) * 100)

        # Duplicate/contradiction score
        duplicate_penalty = (
            metrics.duplicate_rate + metrics.contradiction_rate
        ) / 2
        dup_score = int((1 - duplicate_penalty) * 100)

        return int(
            relevance_score * 0.6 + noise_score * 0.3 + dup_score * 0.1
        )

    def _calculate_db_health_score(self, metrics: HealthMetrics) -> int:
        """
        Calculate database health component score.

        Factors:
        - Lifecycle distribution (60%)
        - Database size management (30%)
        - Project count (10%)
        """
        if metrics.total_memories == 0:
            return 100  # Empty database is "healthy"

        # Lifecycle distribution score
        # Ideal: 20% ACTIVE, 30% RECENT, 40% ARCHIVED, 10% STALE
        active_pct = metrics.active_memories / metrics.total_memories
        recent_pct = metrics.recent_memories / metrics.total_memories
        archived_pct = metrics.archived_memories / metrics.total_memories
        stale_pct = metrics.stale_memories / metrics.total_memories

        # Score based on how close to ideal
        lifecycle_score = 100
        lifecycle_score -= abs(active_pct - 0.20) * 100  # Prefer ~20% active
        lifecycle_score -= abs(recent_pct - 0.30) * 80  # Prefer ~30% recent
        lifecycle_score -= stale_pct * 150  # Heavily penalize stale

        lifecycle_score = max(0, int(lifecycle_score))

        # Database size score (reasonable growth)
        # Good: <500MB, Fair: 500-1000MB, Poor: >1000MB
        if metrics.database_size_mb < 500:
            size_score = 100
        elif metrics.database_size_mb < 1000:
            size_score = 80
        else:
            size_score = max(0, 80 - int((metrics.database_size_mb - 1000) / 100))

        # Project count score (manageable number)
        # Good: 1-5 active, Fair: 6-10, Poor: >10
        if metrics.active_projects <= 5:
            project_score = 100
        elif metrics.active_projects <= 10:
            project_score = 80
        else:
            project_score = max(0, 80 - (metrics.active_projects - 10) * 5)

        return int(
            lifecycle_score * 0.6 + size_score * 0.3 + project_score * 0.1
        )

    def _calculate_usage_score(self, metrics: HealthMetrics) -> int:
        """
        Calculate usage efficiency component score.

        Factors:
        - Queries per day (activity level)
        - Average results per query (efficiency)
        """
        # Activity score (regular usage is good)
        # Good: 20-100 queries/day, Fair: 5-20 or >100, Poor: <5
        if 20 <= metrics.queries_per_day <= 100:
            activity_score = 100
        elif 5 <= metrics.queries_per_day < 20:
            activity_score = 70 + int((metrics.queries_per_day - 5) * 2)
        elif metrics.queries_per_day > 100:
            activity_score = max(50, 100 - int((metrics.queries_per_day - 100) / 10))
        else:
            activity_score = int(metrics.queries_per_day * 10)

        # Results efficiency (not too many, not too few)
        # Good: 5-10 results/query, Fair: 3-5 or 10-15, Poor: <3 or >15
        if 5 <= metrics.avg_results_per_query <= 10:
            results_score = 100
        elif 3 <= metrics.avg_results_per_query < 5:
            results_score = 80
        elif 10 < metrics.avg_results_per_query <= 15:
            results_score = 80
        else:
            results_score = 60

        return int(activity_score * 0.6 + results_score * 0.4)

    def _apply_alert_penalty(self, score: int, alerts: List[Alert]) -> int:
        """
        Apply penalty to score based on active alerts.

        Caps maximum penalty at 30% of score to prevent excessive reduction.
        This ensures that excellent performance/quality scores remain
        meaningful even with many alerts.
        """
        penalty = 0

        for alert in alerts:
            if alert.severity == AlertSeverity.CRITICAL:
                penalty += 15
            elif alert.severity == AlertSeverity.WARNING:
                penalty += 5
            elif alert.severity == AlertSeverity.INFO:
                penalty += 1

        # Cap penalty at 30% of score to prevent complete reduction to 0
        # This ensures that excellent performance/quality scores still matter
        max_penalty = int(score * 0.30)
        penalty = min(penalty, max_penalty)

        return max(0, score - penalty)

    def _score_to_status(self, score: int) -> HealthStatus:
        """Convert numeric score to status category."""
        if score >= 90:
            return HealthStatus.EXCELLENT
        elif score >= 75:
            return HealthStatus.GOOD
        elif score >= 60:
            return HealthStatus.FAIR
        elif score >= 40:
            return HealthStatus.POOR
        else:
            return HealthStatus.CRITICAL

    def analyze_trends(
        self,
        current_metrics: HealthMetrics,
        previous_metrics: Optional[HealthMetrics],
    ) -> List[TrendAnalysis]:
        """
        Analyze trends by comparing current and previous metrics.

        Args:
            current_metrics: Current metrics snapshot
            previous_metrics: Previous metrics snapshot (e.g., 7 days ago)

        Returns:
            List of trend analyses for key metrics
        """
        if not previous_metrics:
            return []

        trends = []

        # Define metrics to track
        tracked_metrics = [
            ("avg_search_latency_ms", False),  # Lower is better
            ("avg_result_relevance", True),  # Higher is better
            ("noise_ratio", False),  # Lower is better
            ("cache_hit_rate", True),  # Higher is better
            ("total_memories", None),  # Neutral
            ("stale_memories", False),  # Lower is better
            ("database_size_mb", None),  # Neutral
        ]

        for metric_name, higher_is_better in tracked_metrics:
            current_value = getattr(current_metrics, metric_name, 0)
            previous_value = getattr(previous_metrics, metric_name, 0)

            if previous_value == 0:
                continue  # Skip if no baseline

            # Calculate change
            change = current_value - previous_value
            change_percent = (change / previous_value) * 100

            # Determine direction based on metric type and change
            if higher_is_better is None:
                # Neutral metric - just report change
                if abs(change_percent) < TREND_SIGNIFICANT_CHANGE:
                    direction = "stable"
                else:
                    direction = "changed"
            elif higher_is_better:
                # Higher values are better
                if change_percent > TREND_SIGNIFICANT_CHANGE:
                    direction = "improving"
                elif change_percent < -TREND_SIGNIFICANT_CHANGE:
                    direction = "degrading"
                else:
                    direction = "stable"
            else:
                # Lower values are better
                if change_percent < -TREND_SIGNIFICANT_CHANGE:
                    direction = "improving"
                elif change_percent > TREND_SIGNIFICANT_CHANGE:
                    direction = "degrading"
                else:
                    direction = "stable"

            trends.append(
                TrendAnalysis(
                    metric_name=metric_name,
                    current_value=current_value,
                    previous_value=previous_value,
                    change_percent=change_percent,
                    direction=direction,
                    is_significant=abs(change_percent) > TREND_HIGHLY_SIGNIFICANT,
                )
            )

        return trends

    def generate_weekly_report(
        self,
        current_metrics: HealthMetrics,
        current_alerts: List[Alert],
        historical_metrics: List[HealthMetrics],
    ) -> WeeklyReport:
        """
        Generate comprehensive weekly health report.

        Args:
            current_metrics: Most recent metrics
            current_alerts: Active alerts
            historical_metrics: Metrics history for trend analysis

        Returns:
            WeeklyReport with trends and recommendations
        """
        # Calculate current health score
        current_health = self.calculate_health_score(current_metrics, current_alerts)

        # Get previous week's metrics for comparison
        previous_metrics = historical_metrics[0] if historical_metrics else None
        previous_health = None
        if previous_metrics:
            # Note: We don't have previous alerts, so approximate
            previous_health = self.calculate_health_score(previous_metrics, [])

        # Analyze trends
        trends = self.analyze_trends(current_metrics, previous_metrics)

        # Categorize trends into improvements and concerns
        improvements = []
        concerns = []

        for trend in trends:
            if trend.direction == "improving" and trend.is_significant:
                improvements.append(
                    f"{trend.metric_name}: {trend.previous_value:.2f} → "
                    f"{trend.current_value:.2f} ({trend.change_percent:+.1f}%)"
                )
            elif trend.direction == "degrading" and trend.is_significant:
                concerns.append(
                    f"{trend.metric_name}: {trend.previous_value:.2f} → "
                    f"{trend.current_value:.2f} ({trend.change_percent:+.1f}%)"
                )

        # Generate recommendations based on current state
        recommendations = self._generate_recommendations(
            current_metrics, current_alerts, trends
        )

        # Usage summary
        usage_summary = {
            "queries_per_day": current_metrics.queries_per_day,
            "memories_created_per_day": current_metrics.memories_created_per_day,
            "avg_results_per_query": current_metrics.avg_results_per_query,
        }

        # Alert summary
        alert_summary = {
            "total": len(current_alerts),
            "critical": current_health.critical_alerts,
            "warning": current_health.warning_alerts,
            "info": len(current_alerts)
            - current_health.critical_alerts
            - current_health.warning_alerts,
        }

        return WeeklyReport(
            period_start=current_metrics.timestamp - timedelta(days=7),
            period_end=current_metrics.timestamp,
            current_health=current_health,
            previous_health=previous_health,
            trends=trends,
            improvements=improvements,
            concerns=concerns,
            recommendations=recommendations,
            usage_summary=usage_summary,
            alert_summary=alert_summary,
        )

    def _generate_recommendations(
        self,
        metrics: HealthMetrics,
        alerts: List[Alert],
        trends: List[TrendAnalysis],
    ) -> List[str]:
        """Generate actionable recommendations based on current state."""
        recommendations = []

        # Add alert-based recommendations
        for alert in alerts[:5]:  # Top 5 alerts
            for rec in alert.recommendations[:2]:  # Top 2 recs per alert
                if rec not in recommendations:
                    recommendations.append(rec)

        # Add trend-based recommendations
        for trend in trends:
            if trend.direction == "degrading" and trend.is_significant:
                if trend.metric_name == "avg_result_relevance":
                    recommendations.append(
                        "Search quality declining - run health check and pruning"
                    )
                elif trend.metric_name == "noise_ratio":
                    recommendations.append(
                        "Noise increasing - consider archiving inactive projects"
                    )
                elif trend.metric_name == "avg_search_latency_ms":
                    recommendations.append(
                        "Search slowing down - review database size and optimize"
                    )

        # Add general maintenance recommendations
        if metrics.stale_memories > 1000:
            recommendations.append(
                f"Clean up {metrics.stale_memories} stale memories with pruning"
            )

        if metrics.database_size_mb > 1000:
            recommendations.append(
                f"Database size ({metrics.database_size_mb:.0f}MB) is large - "
                "consider archiving old projects"
            )

        if metrics.active_projects > 8:
            recommendations.append(
                f"{metrics.active_projects} active projects - review which are "
                "actually in use"
            )

        # Limit to top 10 recommendations
        return recommendations[:10]
