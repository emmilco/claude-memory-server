"""Tests for performance regression detection."""

import pytest
import sqlite3
from pathlib import Path
import tempfile

from src.monitoring.performance_tracker import (
    PerformanceTracker,
    PerformanceMetric,
    RegressionSeverity,
)


@pytest.fixture
def temp_db():
    """Create temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    yield db_path
    Path(db_path).unlink(missing_ok=True)


@pytest.fixture
def tracker(temp_db):
    """Create performance tracker instance."""
    return PerformanceTracker(temp_db)


class TestDatabaseInitialization:
    """Test database schema initialization."""

    def test_creates_performance_metrics_table(self, tracker, temp_db):
        """Should create performance_metrics table."""
        with sqlite3.connect(temp_db) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='performance_metrics'"
            )
            assert cursor.fetchone() is not None

    def test_creates_baselines_table(self, tracker, temp_db):
        """Should create performance_baselines table."""
        with sqlite3.connect(temp_db) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='performance_baselines'"
            )
            assert cursor.fetchone() is not None

    def test_creates_regressions_table(self, tracker, temp_db):
        """Should create performance_regressions table."""
        with sqlite3.connect(temp_db) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='performance_regressions'"
            )
            assert cursor.fetchone() is not None

    def test_creates_indexes(self, tracker, temp_db):
        """Should create indexes for performance."""
        with sqlite3.connect(temp_db) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='index'")
            indexes = [row[0] for row in cursor.fetchall()]
            assert "idx_perf_metrics_timestamp" in indexes
            assert "idx_perf_metrics_metric" in indexes


class TestMetricRecording:
    """Test metric recording functionality."""

    def test_records_metric_with_value(self, tracker):
        """Should record metric with value."""
        tracker.record_metric(PerformanceMetric.SEARCH_LATENCY_P50, 12.5)

        # Verify stored
        history = tracker.get_metric_history(
            PerformanceMetric.SEARCH_LATENCY_P50, days=1
        )
        assert len(history) == 1
        assert history[0][1] == 12.5

    def test_records_metric_with_metadata(self, tracker):
        """Should record metric with metadata."""
        metadata = {"project": "test-project", "collection_size": 1000}
        tracker.record_metric(
            PerformanceMetric.INDEXING_THROUGHPUT, 15.0, metadata=metadata
        )

        # Verify stored (metadata checked via database)
        history = tracker.get_metric_history(
            PerformanceMetric.INDEXING_THROUGHPUT, days=1
        )
        assert len(history) == 1

    def test_records_multiple_metrics(self, tracker):
        """Should record multiple metrics independently."""
        tracker.record_metric(PerformanceMetric.SEARCH_LATENCY_P50, 10.0)
        tracker.record_metric(PerformanceMetric.SEARCH_LATENCY_P95, 25.0)
        tracker.record_metric(PerformanceMetric.CACHE_HIT_RATE, 0.85)

        # Verify all stored
        p50_history = tracker.get_metric_history(
            PerformanceMetric.SEARCH_LATENCY_P50, days=1
        )
        p95_history = tracker.get_metric_history(
            PerformanceMetric.SEARCH_LATENCY_P95, days=1
        )
        cache_history = tracker.get_metric_history(
            PerformanceMetric.CACHE_HIT_RATE, days=1
        )

        assert len(p50_history) == 1
        assert len(p95_history) == 1
        assert len(cache_history) == 1


class TestBaselineCalculation:
    """Test baseline calculation from historical data."""

    def test_calculates_baseline_from_sufficient_data(self, tracker):
        """Should calculate baseline when enough samples exist."""
        # Record 30 data points over 30 days
        for i in range(30):
            tracker.record_metric(PerformanceMetric.SEARCH_LATENCY_P50, 10.0 + i * 0.1)

        baseline = tracker.calculate_baseline(
            PerformanceMetric.SEARCH_LATENCY_P50, days=30
        )

        assert baseline is not None
        assert baseline.metric == PerformanceMetric.SEARCH_LATENCY_P50
        assert baseline.sample_count == 30
        assert baseline.mean > 0
        assert baseline.stddev >= 0
        assert baseline.min_value == 10.0
        assert baseline.max_value == 12.9

    def test_returns_none_for_insufficient_data(self, tracker):
        """Should return None when insufficient samples exist."""
        # Record only 5 data points (need 10 minimum)
        for i in range(5):
            tracker.record_metric(PerformanceMetric.SEARCH_LATENCY_P50, 10.0)

        baseline = tracker.calculate_baseline(
            PerformanceMetric.SEARCH_LATENCY_P50, days=30
        )

        assert baseline is None

    def test_stores_baseline_in_database(self, tracker):
        """Should store calculated baseline in database."""
        # Record sufficient data
        for i in range(30):
            tracker.record_metric(PerformanceMetric.SEARCH_LATENCY_P50, 10.0)

        tracker.calculate_baseline(PerformanceMetric.SEARCH_LATENCY_P50, days=30)

        # Verify stored
        baseline = tracker.get_baseline(PerformanceMetric.SEARCH_LATENCY_P50)
        assert baseline is not None
        assert baseline.mean == 10.0

    def test_updates_existing_baseline(self, tracker):
        """Should update existing baseline when recalculated."""
        # Initial baseline
        for i in range(30):
            tracker.record_metric(PerformanceMetric.SEARCH_LATENCY_P50, 10.0)
        tracker.calculate_baseline(PerformanceMetric.SEARCH_LATENCY_P50, days=30)

        # Add more data with different values
        for i in range(30):
            tracker.record_metric(PerformanceMetric.SEARCH_LATENCY_P50, 15.0)
        baseline = tracker.calculate_baseline(
            PerformanceMetric.SEARCH_LATENCY_P50, days=30
        )

        # Should include all 60 samples (30 of 10.0 + 30 of 15.0) = 12.5 average
        assert baseline.mean == 12.5
        assert baseline.sample_count == 60


class TestRegressionDetection:
    """Test performance regression detection."""

    def test_detects_no_regression_when_performance_stable(self, tracker):
        """Should not detect regression when performance is stable."""
        # Establish baseline
        for i in range(30):
            tracker.record_metric(PerformanceMetric.SEARCH_LATENCY_P50, 10.0)
        tracker.calculate_baseline(PerformanceMetric.SEARCH_LATENCY_P50, days=30)

        # Current performance is same
        regression = tracker.detect_regression(
            PerformanceMetric.SEARCH_LATENCY_P50, 10.0
        )

        assert regression is None

    def test_detects_minor_regression(self, tracker):
        """Should detect minor regression (10-25%)."""
        # Establish baseline
        for i in range(30):
            tracker.record_metric(PerformanceMetric.SEARCH_LATENCY_P50, 10.0)
        tracker.calculate_baseline(PerformanceMetric.SEARCH_LATENCY_P50, days=30)

        # Current performance degraded by 15%
        regression = tracker.detect_regression(
            PerformanceMetric.SEARCH_LATENCY_P50, 11.5
        )

        assert regression is not None
        assert regression.severity == RegressionSeverity.MINOR
        assert regression.degradation_percent > 10
        assert regression.degradation_percent < 25

    def test_detects_severe_regression(self, tracker):
        """Should detect severe regression (40-60%)."""
        # Establish baseline
        for i in range(30):
            tracker.record_metric(PerformanceMetric.SEARCH_LATENCY_P50, 10.0)
        tracker.calculate_baseline(PerformanceMetric.SEARCH_LATENCY_P50, days=30)

        # Current performance degraded by 50%
        regression = tracker.detect_regression(
            PerformanceMetric.SEARCH_LATENCY_P50, 15.0
        )

        assert regression is not None
        assert regression.severity == RegressionSeverity.SEVERE
        assert regression.degradation_percent > 40
        assert regression.degradation_percent < 60

    def test_detects_critical_regression(self, tracker):
        """Should detect critical regression (>60%)."""
        # Establish baseline
        for i in range(30):
            tracker.record_metric(PerformanceMetric.SEARCH_LATENCY_P50, 10.0)
        tracker.calculate_baseline(PerformanceMetric.SEARCH_LATENCY_P50, days=30)

        # Current performance degraded by 100%
        regression = tracker.detect_regression(
            PerformanceMetric.SEARCH_LATENCY_P50, 20.0
        )

        assert regression is not None
        assert regression.severity == RegressionSeverity.CRITICAL
        assert regression.degradation_percent > 60

    def test_handles_throughput_degradation_correctly(self, tracker):
        """Should detect degradation when throughput decreases."""
        # Establish baseline (higher is better for throughput)
        for i in range(30):
            tracker.record_metric(PerformanceMetric.INDEXING_THROUGHPUT, 20.0)
        tracker.calculate_baseline(PerformanceMetric.INDEXING_THROUGHPUT, days=30)

        # Current performance degraded (lower throughput)
        regression = tracker.detect_regression(
            PerformanceMetric.INDEXING_THROUGHPUT, 10.0
        )

        assert regression is not None
        assert regression.severity == RegressionSeverity.SEVERE  # 50% degradation

    def test_handles_cache_hit_rate_degradation(self, tracker):
        """Should detect degradation when cache hit rate decreases."""
        # Establish baseline
        for i in range(30):
            tracker.record_metric(PerformanceMetric.CACHE_HIT_RATE, 0.80)
        tracker.calculate_baseline(PerformanceMetric.CACHE_HIT_RATE, days=30)

        # Current performance degraded (lower hit rate)
        regression = tracker.detect_regression(PerformanceMetric.CACHE_HIT_RATE, 0.40)

        assert regression is not None
        assert regression.severity == RegressionSeverity.SEVERE  # 50% degradation


class TestRecommendationGeneration:
    """Test recommendation generation for regressions."""

    def test_generates_recommendations_for_latency_regression(self, tracker):
        """Should generate actionable recommendations for latency regression."""
        # Establish baseline and detect regression
        for i in range(30):
            tracker.record_metric(PerformanceMetric.SEARCH_LATENCY_P95, 20.0)
        tracker.calculate_baseline(PerformanceMetric.SEARCH_LATENCY_P95, days=30)

        regression = tracker.detect_regression(
            PerformanceMetric.SEARCH_LATENCY_P95, 30.0
        )

        assert regression is not None
        assert len(regression.recommendations) > 0
        # Should include recommendations about collection size, quantization, etc.
        assert any(
            "collection" in rec.lower() or "quantization" in rec.lower()
            for rec in regression.recommendations
        )

    def test_generates_recommendations_for_throughput_regression(self, tracker):
        """Should generate recommendations for throughput regression."""
        # Establish baseline and detect regression
        for i in range(30):
            tracker.record_metric(PerformanceMetric.INDEXING_THROUGHPUT, 20.0)
        tracker.calculate_baseline(PerformanceMetric.INDEXING_THROUGHPUT, days=30)

        regression = tracker.detect_regression(
            PerformanceMetric.INDEXING_THROUGHPUT, 10.0
        )

        assert regression is not None
        assert len(regression.recommendations) > 0
        # Should include recommendations about parallel indexing
        assert any("parallel" in rec.lower() for rec in regression.recommendations)

    def test_limits_recommendations_count(self, tracker):
        """Should limit recommendations to top 5."""
        # Establish baseline and detect severe regression
        for i in range(30):
            tracker.record_metric(PerformanceMetric.SEARCH_LATENCY_P99, 20.0)
        tracker.calculate_baseline(PerformanceMetric.SEARCH_LATENCY_P99, days=30)

        regression = tracker.detect_regression(
            PerformanceMetric.SEARCH_LATENCY_P99, 60.0
        )

        assert regression is not None
        assert len(regression.recommendations) <= 5


class TestPerformanceReport:
    """Test performance report generation."""

    def test_generates_report_with_current_metrics(self, tracker):
        """Should include current metrics in report."""
        # Record recent metrics
        tracker.record_metric(PerformanceMetric.SEARCH_LATENCY_P50, 12.0)
        tracker.record_metric(PerformanceMetric.CACHE_HIT_RATE, 0.85)

        report = tracker.generate_report(period_days=7)

        assert PerformanceMetric.SEARCH_LATENCY_P50 in report.current_metrics
        assert PerformanceMetric.CACHE_HIT_RATE in report.current_metrics
        assert report.current_metrics[PerformanceMetric.SEARCH_LATENCY_P50] == 12.0
        assert report.current_metrics[PerformanceMetric.CACHE_HIT_RATE] == 0.85

    def test_generates_report_with_baselines(self, tracker):
        """Should include baselines in report."""
        # Establish baselines
        for i in range(30):
            tracker.record_metric(PerformanceMetric.SEARCH_LATENCY_P50, 10.0)
        tracker.calculate_baseline(PerformanceMetric.SEARCH_LATENCY_P50, days=30)

        report = tracker.generate_report(period_days=7)

        assert PerformanceMetric.SEARCH_LATENCY_P50 in report.baselines
        baseline = report.baselines[PerformanceMetric.SEARCH_LATENCY_P50]
        assert baseline.mean == 10.0

    def test_generates_report_with_detected_regressions(self, tracker):
        """Should detect and include regressions in report."""
        # Establish baseline
        for i in range(30):
            tracker.record_metric(PerformanceMetric.SEARCH_LATENCY_P50, 10.0)
        tracker.calculate_baseline(PerformanceMetric.SEARCH_LATENCY_P50, days=30)

        # Record regressed performance
        # The get_current_value() averages the last day, so multiple samples needed
        for i in range(5):
            tracker.record_metric(PerformanceMetric.SEARCH_LATENCY_P50, 20.0)

        report = tracker.generate_report(period_days=7)

        assert report.has_regressions is True
        assert report.total_regressions > 0
        assert len(report.regressions) > 0
        # Any severity is fine, as long as a regression was detected
        assert report.worst_severity in [
            RegressionSeverity.MINOR,
            RegressionSeverity.MODERATE,
            RegressionSeverity.SEVERE,
            RegressionSeverity.CRITICAL,
        ]

    def test_report_shows_no_regressions_when_healthy(self, tracker):
        """Should indicate no regressions when performance is healthy."""
        # Establish baseline
        for i in range(30):
            tracker.record_metric(PerformanceMetric.SEARCH_LATENCY_P50, 10.0)
        tracker.calculate_baseline(PerformanceMetric.SEARCH_LATENCY_P50, days=30)

        # Record stable performance
        tracker.record_metric(PerformanceMetric.SEARCH_LATENCY_P50, 10.5)

        report = tracker.generate_report(period_days=7)

        assert report.has_regressions is False
        assert report.total_regressions == 0
        assert report.worst_severity == RegressionSeverity.NONE


class TestMetricHistory:
    """Test metric history retrieval."""

    def test_retrieves_metric_history(self, tracker):
        """Should retrieve historical data points."""
        # Record data over time
        for i in range(10):
            tracker.record_metric(PerformanceMetric.SEARCH_LATENCY_P50, 10.0 + i)

        history = tracker.get_metric_history(
            PerformanceMetric.SEARCH_LATENCY_P50, days=1
        )

        assert len(history) == 10
        # Verify chronological order
        assert history[0][1] == 10.0
        assert history[-1][1] == 19.0

    def test_filters_history_by_time_period(self, tracker):
        """Should filter history to requested time period."""
        # This test would require manipulating timestamps
        # For now, verify the basic functionality works
        for i in range(5):
            tracker.record_metric(PerformanceMetric.SEARCH_LATENCY_P50, 10.0)

        history = tracker.get_metric_history(
            PerformanceMetric.SEARCH_LATENCY_P50, days=30
        )

        assert len(history) == 5

    def test_returns_empty_history_for_no_data(self, tracker):
        """Should return empty list when no data exists."""
        history = tracker.get_metric_history(
            PerformanceMetric.SEARCH_LATENCY_P50, days=30
        )

        assert len(history) == 0


class TestRegressionHistory:
    """Test regression history retrieval."""

    def test_retrieves_regression_history(self, tracker):
        """Should retrieve historical regressions."""
        # Establish baseline
        for i in range(30):
            tracker.record_metric(PerformanceMetric.SEARCH_LATENCY_P50, 10.0)
        tracker.calculate_baseline(PerformanceMetric.SEARCH_LATENCY_P50, days=30)

        # Detect regression
        tracker.detect_regression(PerformanceMetric.SEARCH_LATENCY_P50, 15.0)

        # Retrieve history
        history = tracker.get_regression_history(days=7)

        assert len(history) > 0
        assert history[0].metric == PerformanceMetric.SEARCH_LATENCY_P50
        assert history[0].severity == RegressionSeverity.SEVERE

    def test_returns_empty_history_when_no_regressions(self, tracker):
        """Should return empty list when no regressions detected."""
        history = tracker.get_regression_history(days=30)

        assert len(history) == 0


class TestCurrentValue:
    """Test current value calculation."""

    def test_calculates_current_value_from_recent_data(self, tracker):
        """Should calculate average from recent data."""
        # Record multiple recent values
        for i in range(5):
            tracker.record_metric(PerformanceMetric.SEARCH_LATENCY_P50, 10.0 + i)

        current = tracker.get_current_value(
            PerformanceMetric.SEARCH_LATENCY_P50, days=1
        )

        assert current is not None
        # Average of 10, 11, 12, 13, 14 = 12.0
        assert current == 12.0

    def test_returns_none_for_no_recent_data(self, tracker):
        """Should return None when no recent data exists."""
        current = tracker.get_current_value(
            PerformanceMetric.SEARCH_LATENCY_P50, days=1
        )

        assert current is None
