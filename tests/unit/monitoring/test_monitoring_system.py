"""
Comprehensive tests for the health monitoring system.

Tests metrics collection, alert engine, health reporting, and remediation.
"""

import pytest
import sqlite3
import tempfile
from datetime import datetime, timedelta, UTC
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch

from src.monitoring.metrics_collector import HealthMetrics, MetricsCollector
from src.monitoring.alert_engine import (
    Alert,
    AlertEngine,
    AlertSeverity,
    AlertThreshold,
)
from src.monitoring.health_reporter import (
    HealthReporter,
    HealthStatus,
    HealthScore,
    TrendAnalysis,
)
from src.monitoring.remediation import (
    RemediationEngine,
    RemediationAction,
    RemediationResult,
    RemediationTrigger,
)
from src.core.models import LifecycleState


# ============================================================================
# Metrics Collector Tests
# ============================================================================


class TestMetricsCollector:
    """Tests for MetricsCollector class."""

    @pytest.fixture
    def temp_db(self):
        """Create temporary database."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        yield db_path
        Path(db_path).unlink(missing_ok=True)

    @pytest.fixture
    def mock_store(self):
        """Create mock store."""
        store = AsyncMock()
        store.count = AsyncMock(return_value=1000)
        store.count_by_lifecycle = AsyncMock(return_value=200)
        store.get_all_projects = AsyncMock(return_value=[])
        return store

    @pytest.fixture
    def collector(self, temp_db, mock_store):
        """Create metrics collector."""
        return MetricsCollector(temp_db, mock_store)

    def test_init_creates_tables(self, temp_db):
        """Test initialization creates database tables."""
        collector = MetricsCollector(temp_db)

        with sqlite3.connect(temp_db) as conn:
            cursor = conn.cursor()

            # Check health_metrics table exists
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='health_metrics'"
            )
            assert cursor.fetchone() is not None

            # Check query_log table exists
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='query_log'"
            )
            assert cursor.fetchone() is not None

    @pytest.mark.asyncio
    async def test_collect_metrics_basic(self, collector):
        """Test basic metrics collection."""
        metrics = await collector.collect_metrics()

        assert isinstance(metrics, HealthMetrics)
        assert isinstance(metrics.timestamp, datetime)
        assert metrics.total_memories >= 0
        assert metrics.avg_search_latency_ms >= 0

    def test_log_query(self, collector):
        """Test query logging."""
        collector.log_query(
            query="test query",
            latency_ms=15.5,
            result_count=10,
            avg_relevance=0.85,
        )

        with sqlite3.connect(collector.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM query_log")
            count = cursor.fetchone()[0]

        assert count == 1

    def test_store_metrics(self, collector):
        """Test storing metrics."""
        metrics = HealthMetrics(
            timestamp=datetime.now(UTC),
            avg_search_latency_ms=10.0,
            avg_result_relevance=0.75,
            total_memories=1000,
        )

        collector.store_metrics(metrics)

        with sqlite3.connect(collector.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM health_metrics")
            count = cursor.fetchone()[0]

        assert count == 1

    def test_get_latest_metrics(self, collector):
        """Test retrieving latest metrics."""
        # Store some metrics
        metrics1 = HealthMetrics(
            timestamp=datetime.now(UTC) - timedelta(hours=1),
            total_memories=900,
        )
        metrics2 = HealthMetrics(
            timestamp=datetime.now(UTC),
            total_memories=1000,
        )

        collector.store_metrics(metrics1)
        collector.store_metrics(metrics2)

        latest = collector.get_latest_metrics()

        assert latest is not None
        assert latest.total_memories == 1000

    def test_get_metrics_history(self, collector):
        """Test retrieving metrics history."""
        # Store metrics over several days
        for i in range(5):
            metrics = HealthMetrics(
                timestamp=datetime.now(UTC) - timedelta(days=i),
                total_memories=1000 + i * 100,
            )
            collector.store_metrics(metrics)

        history = collector.get_metrics_history(days=7)

        assert len(history) == 5
        assert all(isinstance(m, HealthMetrics) for m in history)

    def test_cleanup_old_metrics(self, collector):
        """Test cleanup of old metrics."""
        # Store old and new metrics
        old_metrics = HealthMetrics(
            timestamp=datetime.now(UTC) - timedelta(days=100),
            total_memories=500,
        )
        new_metrics = HealthMetrics(
            timestamp=datetime.now(UTC),
            total_memories=1000,
        )

        collector.store_metrics(old_metrics)
        collector.store_metrics(new_metrics)

        # Cleanup old metrics (older than 90 days)
        deleted = collector.cleanup_old_metrics(retention_days=90)

        assert deleted > 0

        # Verify new metrics still exist
        latest = collector.get_latest_metrics()
        assert latest.total_memories == 1000


# ============================================================================
# Alert Engine Tests
# ============================================================================


class TestAlertEngine:
    """Tests for AlertEngine class."""

    @pytest.fixture
    def temp_db(self):
        """Create temporary database."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        yield db_path
        Path(db_path).unlink(missing_ok=True)

    @pytest.fixture
    def alert_engine(self, temp_db):
        """Create alert engine."""
        return AlertEngine(temp_db)

    def test_init_creates_tables(self, temp_db):
        """Test initialization creates database tables."""
        engine = AlertEngine(temp_db)

        with sqlite3.connect(temp_db) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='alert_history'"
            )
            assert cursor.fetchone() is not None

    def test_evaluate_metrics_no_violations(self, alert_engine):
        """Test evaluating metrics with no threshold violations."""
        metrics = HealthMetrics(
            timestamp=datetime.now(UTC),
            avg_result_relevance=0.80,  # Above 0.65 threshold
            avg_search_latency_ms=30.0,  # Below 50ms threshold
            noise_ratio=0.20,  # Below 0.30 threshold
        )

        alerts = alert_engine.evaluate_metrics(metrics)

        # Should have no critical or warning alerts for these good metrics
        critical = [a for a in alerts if a.severity == AlertSeverity.CRITICAL]
        assert len(critical) == 0

    def test_evaluate_metrics_critical_violation(self, alert_engine):
        """Test evaluating metrics with critical violation."""
        metrics = HealthMetrics(
            timestamp=datetime.now(UTC),
            avg_result_relevance=0.40,  # Below 0.50 critical threshold
            avg_search_latency_ms=150.0,  # Above 100ms critical threshold
            noise_ratio=0.60,  # Above 0.50 critical threshold
        )

        alerts = alert_engine.evaluate_metrics(metrics)

        critical = [a for a in alerts if a.severity == AlertSeverity.CRITICAL]
        assert len(critical) >= 3  # All three critical thresholds violated

    def test_store_and_retrieve_alerts(self, alert_engine):
        """Test storing and retrieving alerts."""
        alert = Alert(
            id="test_alert_1",
            severity=AlertSeverity.WARNING,
            metric_name="avg_result_relevance",
            current_value=0.62,
            threshold_value=0.65,
            message="Search quality degrading",
            recommendations=["Run health check"],
            timestamp=datetime.now(UTC),
        )

        alert_engine.store_alerts([alert])

        active_alerts = alert_engine.get_active_alerts()

        assert len(active_alerts) == 1
        assert active_alerts[0].id == "test_alert_1"

    def test_resolve_alert(self, alert_engine):
        """Test resolving an alert."""
        alert = Alert(
            id="test_alert_2",
            severity=AlertSeverity.WARNING,
            metric_name="test_metric",
            current_value=0.5,
            threshold_value=0.6,
            message="Test alert",
            recommendations=[],
            timestamp=datetime.now(UTC),
        )

        alert_engine.store_alerts([alert])

        # Resolve the alert
        success = alert_engine.resolve_alert("test_alert_2")

        assert success is True

        # Check it's no longer in active alerts
        active_alerts = alert_engine.get_active_alerts()
        assert len(active_alerts) == 0

    def test_snooze_alert(self, alert_engine):
        """Test snoozing an alert."""
        alert = Alert(
            id="test_alert_3",
            severity=AlertSeverity.INFO,
            metric_name="test_metric",
            current_value=1.0,
            threshold_value=1.0,
            message="Test alert",
            recommendations=[],
            timestamp=datetime.now(UTC),
        )

        alert_engine.store_alerts([alert])

        # Snooze the alert for 24 hours
        success = alert_engine.snooze_alert("test_alert_3", hours=24)

        assert success is True

        # Should not appear in active alerts (without snoozed)
        active_alerts = alert_engine.get_active_alerts(include_snoozed=False)
        assert len(active_alerts) == 0

        # Should appear when including snoozed
        all_alerts = alert_engine.get_active_alerts(include_snoozed=True)
        assert len(all_alerts) == 1

    def test_get_alert_summary(self, alert_engine):
        """Test getting alert summary."""
        alerts = [
            Alert(
                id="critical_1",
                severity=AlertSeverity.CRITICAL,
                metric_name="test",
                current_value=0.0,
                threshold_value=1.0,
                message="Critical",
                recommendations=[],
                timestamp=datetime.now(UTC),
            ),
            Alert(
                id="warning_1",
                severity=AlertSeverity.WARNING,
                metric_name="test",
                current_value=0.0,
                threshold_value=1.0,
                message="Warning",
                recommendations=[],
                timestamp=datetime.now(UTC),
            ),
            Alert(
                id="warning_2",
                severity=AlertSeverity.WARNING,
                metric_name="test",
                current_value=0.0,
                threshold_value=1.0,
                message="Warning 2",
                recommendations=[],
                timestamp=datetime.now(UTC),
            ),
        ]

        alert_engine.store_alerts(alerts)

        summary = alert_engine.get_alert_summary()

        assert summary["total"] == 3
        assert summary["CRITICAL"] == 1
        assert summary["WARNING"] == 2


# ============================================================================
# Health Reporter Tests
# ============================================================================


class TestHealthReporter:
    """Tests for HealthReporter class."""

    @pytest.fixture
    def reporter(self):
        """Create health reporter."""
        return HealthReporter()

    def test_calculate_health_score_excellent(self, reporter):
        """Test health score calculation for excellent metrics."""
        metrics = HealthMetrics(
            timestamp=datetime.now(UTC),
            avg_search_latency_ms=10.0,
            avg_result_relevance=0.90,
            noise_ratio=0.10,
            cache_hit_rate=0.85,
            total_memories=1000,
            active_memories=200,
            recent_memories=300,
            archived_memories=400,
            stale_memories=100,
            active_projects=3,
            database_size_mb=200.0,
        )

        score = reporter.calculate_health_score(metrics, [])

        assert score.overall_score >= 80
        assert score.status in [HealthStatus.EXCELLENT, HealthStatus.GOOD]

    def test_calculate_health_score_poor(self, reporter):
        """Test health score calculation for poor metrics."""
        metrics = HealthMetrics(
            timestamp=datetime.now(UTC),
            avg_search_latency_ms=150.0,
            avg_result_relevance=0.40,
            noise_ratio=0.60,
            cache_hit_rate=0.50,
            total_memories=10000,
            active_memories=100,
            recent_memories=100,
            archived_memories=1000,
            stale_memories=8800,
            active_projects=15,
            database_size_mb=2000.0,
        )

        score = reporter.calculate_health_score(metrics, [])

        assert score.overall_score < 60
        assert score.status in [HealthStatus.POOR, HealthStatus.CRITICAL]

    def test_alert_penalty(self, reporter):
        """Test that alerts reduce health score."""
        metrics = HealthMetrics(
            timestamp=datetime.now(UTC),
            avg_search_latency_ms=20.0,
            avg_result_relevance=0.80,
            noise_ratio=0.15,
            cache_hit_rate=0.80,
        )

        # Calculate without alerts
        score_no_alerts = reporter.calculate_health_score(metrics, [])

        # Calculate with alerts
        alerts = [
            Alert(
                id="test",
                severity=AlertSeverity.CRITICAL,
                metric_name="test",
                current_value=0.0,
                threshold_value=1.0,
                message="Test",
                recommendations=[],
                timestamp=datetime.now(UTC),
            )
        ]
        score_with_alerts = reporter.calculate_health_score(metrics, alerts)

        assert score_with_alerts.overall_score < score_no_alerts.overall_score

    def test_analyze_trends_improving(self, reporter):
        """Test trend analysis with improving metrics."""
        previous_metrics = HealthMetrics(
            timestamp=datetime.now(UTC) - timedelta(days=7),
            avg_search_latency_ms=50.0,
            avg_result_relevance=0.60,
        )

        current_metrics = HealthMetrics(
            timestamp=datetime.now(UTC),
            avg_search_latency_ms=30.0,  # Improved (lower is better)
            avg_result_relevance=0.75,  # Improved (higher is better)
        )

        trends = reporter.analyze_trends(current_metrics, previous_metrics)

        # Should have improving trends
        improving = [t for t in trends if t.direction == "improving"]
        assert len(improving) >= 2

    def test_analyze_trends_degrading(self, reporter):
        """Test trend analysis with degrading metrics."""
        previous_metrics = HealthMetrics(
            timestamp=datetime.now(UTC) - timedelta(days=7),
            avg_search_latency_ms=20.0,
            avg_result_relevance=0.80,
        )

        current_metrics = HealthMetrics(
            timestamp=datetime.now(UTC),
            avg_search_latency_ms=60.0,  # Degraded
            avg_result_relevance=0.50,  # Degraded
        )

        trends = reporter.analyze_trends(current_metrics, previous_metrics)

        # Should have degrading trends
        degrading = [t for t in trends if t.direction == "degrading"]
        assert len(degrading) >= 2


# ============================================================================
# Remediation Engine Tests
# ============================================================================


class TestRemediationEngine:
    """Tests for RemediationEngine class."""

    @pytest.fixture
    def temp_db(self):
        """Create temporary database."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        yield db_path
        Path(db_path).unlink(missing_ok=True)

    @pytest.fixture
    def mock_store(self):
        """Create mock store."""
        return AsyncMock()

    @pytest.fixture
    def remediation(self, temp_db, mock_store):
        """Create remediation engine."""
        return RemediationEngine(temp_db, mock_store)

    def test_init_creates_tables(self, temp_db):
        """Test initialization creates database tables."""
        engine = RemediationEngine(temp_db)

        with sqlite3.connect(temp_db) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='remediation_history'"
            )
            assert cursor.fetchone() is not None

    def test_get_available_actions(self, remediation):
        """Test getting available remediation actions."""
        actions = remediation.get_available_actions()

        assert len(actions) > 0
        assert all(isinstance(a, RemediationAction) for a in actions)

        # Check for expected actions
        action_names = [a.name for a in actions]
        assert "prune_stale_memories" in action_names
        assert "optimize_database" in action_names

    def test_execute_action_dry_run(self, remediation):
        """Test executing action in dry-run mode."""
        result = remediation.execute_action(
            "prune_stale_memories",
            dry_run=True,
            triggered_by=RemediationTrigger.USER,
        )

        assert isinstance(result, RemediationResult)
        assert result.success is True

    def test_execute_action_optimize_database(self, remediation):
        """Test executing database optimization."""
        result = remediation.execute_action(
            "optimize_database",
            dry_run=False,
            triggered_by=RemediationTrigger.USER,
        )

        assert result.success is True
        assert result.items_affected >= 0

    def test_execute_unknown_action(self, remediation):
        """Test executing unknown action."""
        result = remediation.execute_action(
            "unknown_action",
            dry_run=False,
            triggered_by=RemediationTrigger.USER,
        )

        assert result.success is False
        assert "Unknown action" in result.error_message

    def test_log_remediation(self, remediation):
        """Test logging remediation history."""
        result = RemediationResult(
            success=True,
            items_affected=10,
            details={"action": "test"},
        )

        remediation._log_remediation(
            action_name="test_action",
            triggered_by="user",
            dry_run=False,
            result=result,
        )

        history = remediation.get_remediation_history(days=1)

        assert len(history) == 1
        assert history[0]["action_name"] == "test_action"
        assert history[0]["success"] is True
        assert history[0]["items_affected"] == 10

    def test_get_remediation_summary(self, remediation):
        """Test getting remediation summary."""
        # Execute some actions
        remediation.execute_action(
            "optimize_database",
            dry_run=False,
            triggered_by=RemediationTrigger.AUTOMATIC,
        )

        summary = remediation.get_remediation_summary(days=1)

        assert summary["total_actions"] >= 1
        assert "action_counts" in summary


# ============================================================================
# Integration Tests
# ============================================================================


class TestMonitoringIntegration:
    """Integration tests for monitoring system."""

    @pytest.fixture
    def temp_db(self):
        """Create temporary database."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        yield db_path
        Path(db_path).unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_full_monitoring_workflow(self, temp_db):
        """Test complete monitoring workflow."""
        # Setup
        mock_store = AsyncMock()
        mock_store.count = AsyncMock(return_value=1000)
        mock_store.count_by_lifecycle = AsyncMock(return_value=200)
        mock_store.get_all_projects = AsyncMock(return_value=[])

        collector = MetricsCollector(temp_db, mock_store)
        alert_engine = AlertEngine(temp_db)
        reporter = HealthReporter()

        # Collect metrics
        metrics = await collector.collect_metrics()
        collector.store_metrics(metrics)

        # Evaluate alerts
        alerts = alert_engine.evaluate_metrics(metrics)
        alert_engine.store_alerts(alerts)

        # Calculate health score
        health_score = reporter.calculate_health_score(metrics, alerts)

        # Verify results
        assert isinstance(health_score, HealthScore)
        assert 0 <= health_score.overall_score <= 100
        assert health_score.status in HealthStatus

    @pytest.mark.asyncio
    async def test_alert_remediation_workflow(self, temp_db):
        """Test alert → remediation workflow."""
        mock_store = AsyncMock()
        mock_store.count = AsyncMock(return_value=5000)
        mock_store.count_by_lifecycle = AsyncMock(return_value=3000)

        # Create degraded metrics
        metrics = HealthMetrics(
            timestamp=datetime.now(UTC),
            avg_result_relevance=0.40,  # Critical
            noise_ratio=0.60,  # Critical
            stale_memories=3000,  # Warning
        )

        # Evaluate and get alerts
        alert_engine = AlertEngine(temp_db)
        alerts = alert_engine.evaluate_metrics(metrics)
        alert_engine.store_alerts(alerts)

        # Should have critical alerts
        active_alerts = alert_engine.get_active_alerts()
        critical = [a for a in active_alerts if a.severity == AlertSeverity.CRITICAL]
        assert len(critical) >= 2

        # Execute remediation
        remediation = RemediationEngine(temp_db, mock_store)
        results = remediation.execute_automatic_actions(dry_run=True)

        # Should have executed some actions
        assert len(results) > 0
        assert any(r.success for r in results.values())
