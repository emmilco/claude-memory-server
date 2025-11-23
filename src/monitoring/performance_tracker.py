"""
Performance regression detection and tracking.

Tracks performance metrics over time, establishes baselines,
detects anomalies, and provides actionable recommendations.
"""

import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, UTC
from typing import Optional, List, Dict, Any, Tuple
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


class PerformanceMetric(str, Enum):
    """Performance metrics tracked for regression detection."""

    SEARCH_LATENCY_P50 = "search_latency_p50"
    SEARCH_LATENCY_P95 = "search_latency_p95"
    SEARCH_LATENCY_P99 = "search_latency_p99"
    INDEXING_THROUGHPUT = "indexing_throughput"  # files/sec
    CACHE_HIT_RATE = "cache_hit_rate"  # percentage


class RegressionSeverity(str, Enum):
    """Severity levels for performance regressions."""

    NONE = "NONE"  # <10% degradation
    MINOR = "MINOR"  # 10-25% degradation
    MODERATE = "MODERATE"  # 25-40% degradation
    SEVERE = "SEVERE"  # 40-60% degradation
    CRITICAL = "CRITICAL"  # >60% degradation


@dataclass
class PerformanceSnapshot:
    """Single performance measurement."""

    timestamp: datetime
    metric: PerformanceMetric
    value: float
    metadata: Dict[str, Any]  # Context (project, collection size, etc.)


@dataclass
class PerformanceBaseline:
    """Baseline statistics for a metric."""

    metric: PerformanceMetric
    mean: float
    stddev: float
    min_value: float
    max_value: float
    sample_count: int
    period_days: int
    last_updated: datetime


@dataclass
class PerformanceRegression:
    """Detected performance regression."""

    metric: PerformanceMetric
    current_value: float
    baseline_value: float
    degradation_percent: float
    severity: RegressionSeverity
    detected_at: datetime
    recommendations: List[str]
    context: Dict[str, Any]


@dataclass
class PerformanceReport:
    """Performance report comparing current metrics to baselines."""

    generated_at: datetime
    period_days: int

    # Current values
    current_metrics: Dict[PerformanceMetric, float]

    # Baselines
    baselines: Dict[PerformanceMetric, PerformanceBaseline]

    # Detected regressions
    regressions: List[PerformanceRegression]

    # Overall status
    has_regressions: bool
    worst_severity: RegressionSeverity
    total_regressions: int


class PerformanceTracker:
    """
    Performance regression detection system.

    Responsibilities:
    - Track performance metrics over time (search latency, indexing throughput, cache hit rate)
    - Establish rolling baselines (30-day average)
    - Detect anomalies (>40% degradation)
    - Provide actionable recommendations
    """

    # Degradation thresholds
    MINOR_THRESHOLD = 0.10  # 10%
    MODERATE_THRESHOLD = 0.25  # 25%
    SEVERE_THRESHOLD = 0.40  # 40%
    CRITICAL_THRESHOLD = 0.60  # 60%

    # Baseline configuration
    DEFAULT_BASELINE_DAYS = 30
    MIN_SAMPLES_FOR_BASELINE = 10

    def __init__(self, db_path: str):
        """
        Initialize performance tracker.

        Args:
            db_path: Path to SQLite database for storing metrics
        """
        self.db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        """Initialize database schema for performance tracking."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Performance metrics table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS performance_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    metric TEXT NOT NULL,
                    value REAL NOT NULL,
                    metadata TEXT,  -- JSON
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_perf_metrics_timestamp
                ON performance_metrics(timestamp)
                """
            )

            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_perf_metrics_metric
                ON performance_metrics(metric)
                """
            )

            # Baselines table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS performance_baselines (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    metric TEXT NOT NULL UNIQUE,
                    mean REAL NOT NULL,
                    stddev REAL NOT NULL,
                    min_value REAL NOT NULL,
                    max_value REAL NOT NULL,
                    sample_count INTEGER NOT NULL,
                    period_days INTEGER NOT NULL,
                    last_updated TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

            # Regression history table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS performance_regressions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    metric TEXT NOT NULL,
                    current_value REAL NOT NULL,
                    baseline_value REAL NOT NULL,
                    degradation_percent REAL NOT NULL,
                    severity TEXT NOT NULL,
                    detected_at TEXT NOT NULL,
                    recommendations TEXT,  -- JSON
                    context TEXT,  -- JSON
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_perf_regressions_detected_at
                ON performance_regressions(detected_at)
                """
            )

            conn.commit()

    def record_metric(
        self,
        metric: PerformanceMetric,
        value: float,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Record a performance metric measurement.

        Args:
            metric: Metric type
            value: Measured value
            metadata: Optional context (project, collection size, etc.)
        """
        import json

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO performance_metrics (timestamp, metric, value, metadata)
                VALUES (?, ?, ?, ?)
                """,
                (
                    datetime.now(UTC).isoformat(),
                    metric.value,
                    value,
                    json.dumps(metadata or {}),
                ),
            )
            conn.commit()

    def calculate_baseline(
        self, metric: PerformanceMetric, days: int = DEFAULT_BASELINE_DAYS
    ) -> Optional[PerformanceBaseline]:
        """
        Calculate rolling baseline for a metric.

        Args:
            metric: Metric to calculate baseline for
            days: Number of days to include in baseline (default: 30)

        Returns:
            PerformanceBaseline or None if insufficient data
        """
        cutoff = (datetime.now(UTC) - timedelta(days=days)).isoformat()

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT value FROM performance_metrics
                WHERE metric = ? AND timestamp >= ?
                ORDER BY timestamp ASC
                """,
                (metric.value, cutoff),
            )

            values = [row[0] for row in cursor.fetchall()]

            if len(values) < self.MIN_SAMPLES_FOR_BASELINE:
                logger.warning(
                    f"Insufficient samples for {metric.value} baseline: "
                    f"{len(values)} < {self.MIN_SAMPLES_FOR_BASELINE}"
                )
                return None

            # Calculate statistics
            import statistics

            mean = statistics.mean(values)
            stddev = statistics.stdev(values) if len(values) > 1 else 0.0
            min_value = min(values)
            max_value = max(values)

            baseline = PerformanceBaseline(
                metric=metric,
                mean=mean,
                stddev=stddev,
                min_value=min_value,
                max_value=max_value,
                sample_count=len(values),
                period_days=days,
                last_updated=datetime.now(UTC),
            )

            # Store baseline in database
            self._store_baseline(baseline)

            return baseline

    def _store_baseline(self, baseline: PerformanceBaseline) -> None:
        """Store baseline in database."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO performance_baselines
                (metric, mean, stddev, min_value, max_value, sample_count, period_days, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    baseline.metric.value,
                    baseline.mean,
                    baseline.stddev,
                    baseline.min_value,
                    baseline.max_value,
                    baseline.sample_count,
                    baseline.period_days,
                    baseline.last_updated.isoformat(),
                ),
            )
            conn.commit()

    def get_baseline(self, metric: PerformanceMetric) -> Optional[PerformanceBaseline]:
        """
        Get stored baseline for a metric.

        Args:
            metric: Metric to get baseline for

        Returns:
            PerformanceBaseline or None if not found
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT metric, mean, stddev, min_value, max_value, sample_count, period_days, last_updated
                FROM performance_baselines
                WHERE metric = ?
                """,
                (metric.value,),
            )

            row = cursor.fetchone()
            if not row:
                return None

            return PerformanceBaseline(
                metric=PerformanceMetric(row[0]),
                mean=row[1],
                stddev=row[2],
                min_value=row[3],
                max_value=row[4],
                sample_count=row[5],
                period_days=row[6],
                last_updated=datetime.fromisoformat(row[7]),
            )

    def get_current_value(self, metric: PerformanceMetric, days: int = 1) -> Optional[float]:
        """
        Get current (recent) value for a metric.

        Args:
            metric: Metric to get current value for
            days: Number of days to average (default: 1)

        Returns:
            Average value or None if no data
        """
        cutoff = (datetime.now(UTC) - timedelta(days=days)).isoformat()

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT AVG(value) FROM performance_metrics
                WHERE metric = ? AND timestamp >= ?
                """,
                (metric.value, cutoff),
            )

            result = cursor.fetchone()
            return float(result[0]) if result[0] is not None else None

    def detect_regression(
        self, metric: PerformanceMetric, current_value: Optional[float] = None
    ) -> Optional[PerformanceRegression]:
        """
        Detect performance regression for a metric.

        Args:
            metric: Metric to check
            current_value: Current value (if None, calculate from recent data)

        Returns:
            PerformanceRegression or None if no regression detected
        """
        # Get current value if not provided
        if current_value is None:
            current_value = self.get_current_value(metric)
            if current_value is None:
                logger.warning(f"No current data for {metric.value}")
                return None

        # Get baseline
        baseline = self.get_baseline(metric)
        if not baseline:
            logger.warning(f"No baseline for {metric.value}, calculating...")
            baseline = self.calculate_baseline(metric)
            if not baseline:
                return None

        # Calculate degradation percentage
        # For latency metrics, higher is worse
        # For throughput/hit rate, lower is worse
        if metric in (
            PerformanceMetric.SEARCH_LATENCY_P50,
            PerformanceMetric.SEARCH_LATENCY_P95,
            PerformanceMetric.SEARCH_LATENCY_P99,
        ):
            # Higher latency is degradation
            degradation = (current_value - baseline.mean) / baseline.mean
        else:
            # Lower throughput/hit rate is degradation
            degradation = (baseline.mean - current_value) / baseline.mean

        # Determine severity
        severity = self._calculate_severity(degradation)

        # Only return regression if there's actual degradation
        if severity == RegressionSeverity.NONE:
            return None

        # Generate recommendations
        recommendations = self._generate_recommendations(metric, degradation, current_value, baseline)

        regression = PerformanceRegression(
            metric=metric,
            current_value=current_value,
            baseline_value=baseline.mean,
            degradation_percent=degradation * 100,
            severity=severity,
            detected_at=datetime.now(UTC),
            recommendations=recommendations,
            context={
                "baseline_samples": baseline.sample_count,
                "baseline_period_days": baseline.period_days,
                "baseline_stddev": baseline.stddev,
            },
        )

        # Store regression in database
        self._store_regression(regression)

        return regression

    def _calculate_severity(self, degradation: float) -> RegressionSeverity:
        """Calculate regression severity from degradation percentage."""
        abs_degradation = abs(degradation)

        if abs_degradation >= self.CRITICAL_THRESHOLD:
            return RegressionSeverity.CRITICAL
        elif abs_degradation >= self.SEVERE_THRESHOLD:
            return RegressionSeverity.SEVERE
        elif abs_degradation >= self.MODERATE_THRESHOLD:
            return RegressionSeverity.MODERATE
        elif abs_degradation >= self.MINOR_THRESHOLD:
            return RegressionSeverity.MINOR
        else:
            return RegressionSeverity.NONE

    def _generate_recommendations(
        self,
        metric: PerformanceMetric,
        degradation: float,
        current_value: float,
        baseline: PerformanceBaseline,
    ) -> List[str]:
        """Generate actionable recommendations for performance regression."""
        recommendations = []

        if metric in (
            PerformanceMetric.SEARCH_LATENCY_P50,
            PerformanceMetric.SEARCH_LATENCY_P95,
            PerformanceMetric.SEARCH_LATENCY_P99,
        ):
            # Search latency recommendations
            recommendations.append("Check Qdrant collection size - large collections slow down search")
            recommendations.append("Consider enabling quantization to reduce memory and improve speed")
            recommendations.append("Review query complexity - simplify filters if possible")

            if current_value > 50:  # >50ms is slow
                recommendations.append("Search latency >50ms - consider optimizing vector index")
                recommendations.append("Check if Qdrant has sufficient memory allocated")

            if degradation > 0.5:  # >50% degradation
                recommendations.append("CRITICAL: Review recent code changes that may impact search")

        elif metric == PerformanceMetric.INDEXING_THROUGHPUT:
            # Indexing throughput recommendations
            recommendations.append("Check if parallel indexing is enabled (4-8x faster)")
            recommendations.append("Verify embedding model is loaded correctly")
            recommendations.append("Review file sizes - very large files slow down parsing")

            if current_value < 5:  # <5 files/sec is slow
                recommendations.append("Indexing <5 files/sec - consider enabling Rust parser (6x faster)")
                recommendations.append("Check CPU utilization - may need more workers")

        elif metric == PerformanceMetric.CACHE_HIT_RATE:
            # Cache hit rate recommendations
            recommendations.append("Low cache hit rate - consider increasing embedding cache size")
            recommendations.append("Review cache eviction policy - may be evicting too aggressively")

            if current_value < 0.5:  # <50% hit rate
                recommendations.append("Cache hit rate <50% - verify cache is functioning correctly")
                recommendations.append("Check if cache file permissions are correct")

        # Add link to performance tuning docs
        recommendations.append(
            "See docs/PERFORMANCE.md for detailed performance tuning guide"
        )

        return recommendations[:5]  # Limit to top 5 recommendations

    def _store_regression(self, regression: PerformanceRegression) -> None:
        """Store regression in database."""
        import json

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO performance_regressions
                (metric, current_value, baseline_value, degradation_percent, severity, detected_at, recommendations, context)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    regression.metric.value,
                    regression.current_value,
                    regression.baseline_value,
                    regression.degradation_percent,
                    regression.severity.value,
                    regression.detected_at.isoformat(),
                    json.dumps(regression.recommendations),
                    json.dumps(regression.context),
                ),
            )
            conn.commit()

    def generate_report(self, period_days: int = 7) -> PerformanceReport:
        """
        Generate comprehensive performance report.

        Args:
            period_days: Number of days to analyze (default: 7)

        Returns:
            PerformanceReport with current metrics, baselines, and regressions
        """
        current_metrics = {}
        baselines = {}
        regressions = []

        # Check all tracked metrics
        for metric in PerformanceMetric:
            # Get current value
            current_value = self.get_current_value(metric, days=1)
            if current_value is not None:
                current_metrics[metric] = current_value

            # Get baseline
            baseline = self.get_baseline(metric)
            if baseline:
                baselines[metric] = baseline

            # Check for regression
            if current_value is not None:
                regression = self.detect_regression(metric, current_value)
                if regression:
                    regressions.append(regression)

        # Determine overall status
        has_regressions = len(regressions) > 0
        worst_severity = RegressionSeverity.NONE

        if regressions:
            severity_order = [
                RegressionSeverity.CRITICAL,
                RegressionSeverity.SEVERE,
                RegressionSeverity.MODERATE,
                RegressionSeverity.MINOR,
            ]
            for severity in severity_order:
                if any(r.severity == severity for r in regressions):
                    worst_severity = severity
                    break

        return PerformanceReport(
            generated_at=datetime.now(UTC),
            period_days=period_days,
            current_metrics=current_metrics,
            baselines=baselines,
            regressions=regressions,
            has_regressions=has_regressions,
            worst_severity=worst_severity,
            total_regressions=len(regressions),
        )

    def get_metric_history(
        self, metric: PerformanceMetric, days: int = 30
    ) -> List[Tuple[datetime, float]]:
        """
        Get historical data points for a metric.

        Args:
            metric: Metric to retrieve
            days: Number of days of history

        Returns:
            List of (timestamp, value) tuples
        """
        cutoff = (datetime.now(UTC) - timedelta(days=days)).isoformat()

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT timestamp, value FROM performance_metrics
                WHERE metric = ? AND timestamp >= ?
                ORDER BY timestamp ASC
                """,
                (metric.value, cutoff),
            )

            return [(datetime.fromisoformat(row[0]), row[1]) for row in cursor.fetchall()]

    def get_regression_history(self, days: int = 30) -> List[PerformanceRegression]:
        """
        Get historical regressions.

        Args:
            days: Number of days of history

        Returns:
            List of PerformanceRegression
        """
        import json

        cutoff = (datetime.now(UTC) - timedelta(days=days)).isoformat()

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT metric, current_value, baseline_value, degradation_percent,
                       severity, detected_at, recommendations, context
                FROM performance_regressions
                WHERE detected_at >= ?
                ORDER BY detected_at DESC
                """,
                (cutoff,),
            )

            regressions = []
            for row in cursor.fetchall():
                regressions.append(
                    PerformanceRegression(
                        metric=PerformanceMetric(row[0]),
                        current_value=row[1],
                        baseline_value=row[2],
                        degradation_percent=row[3],
                        severity=RegressionSeverity(row[4]),
                        detected_at=datetime.fromisoformat(row[5]),
                        recommendations=json.loads(row[6]) if row[6] else [],
                        context=json.loads(row[7]) if row[7] else {},
                    )
                )

            return regressions
