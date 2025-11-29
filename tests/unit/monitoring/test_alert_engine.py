"""
Comprehensive tests for alert_engine module.

Tests alert threshold evaluation, alert generation, storage, retrieval,
snoozing, resolution, and cleanup functionality.
"""

import pytest
import tempfile
import os
from datetime import datetime, timedelta, UTC
from pathlib import Path

from src.monitoring.alert_engine import (
    AlertEngine,
    Alert,
    AlertSeverity,
    AlertThreshold,
)
from src.monitoring.metrics_collector import HealthMetrics


class TestAlertThreshold:
    """Test AlertThreshold dataclass."""

    def test_create_threshold(self):
        """Test creating an alert threshold."""
        threshold = AlertThreshold(
            metric_name="test_metric",
            operator=">",
            threshold_value=100.0,
            severity=AlertSeverity.WARNING,
            message="Test alert",
            recommendations=["Fix this", "Try that"],
        )

        assert threshold.metric_name == "test_metric"
        assert threshold.operator == ">"
        assert threshold.threshold_value == 100.0
        assert threshold.severity == AlertSeverity.WARNING
        assert threshold.message == "Test alert"
        assert len(threshold.recommendations) == 2


class TestAlert:
    """Test Alert dataclass and conversion methods."""

    def test_create_alert(self):
        """Test creating an alert."""
        now = datetime.now(UTC)
        alert = Alert(
            id="test_alert_001",
            severity=AlertSeverity.CRITICAL,
            metric_name="test_metric",
            current_value=150.0,
            threshold_value=100.0,
            message="Metric exceeded threshold",
            recommendations=["Action 1", "Action 2"],
            timestamp=now,
        )

        assert alert.id == "test_alert_001"
        assert alert.severity == AlertSeverity.CRITICAL
        assert alert.current_value == 150.0
        assert alert.threshold_value == 100.0
        assert not alert.resolved
        assert alert.resolved_at is None

    def test_alert_to_dict(self):
        """Test converting alert to dictionary."""
        now = datetime.now(UTC)
        alert = Alert(
            id="test_alert_001",
            severity=AlertSeverity.WARNING,
            metric_name="test_metric",
            current_value=50.0,
            threshold_value=100.0,
            message="Test message",
            recommendations=["Fix it"],
            timestamp=now,
        )

        alert_dict = alert.to_dict()

        assert alert_dict["id"] == "test_alert_001"
        assert alert_dict["severity"] == "WARNING"
        assert alert_dict["current_value"] == 50.0
        assert alert_dict["timestamp"] == now.isoformat()

    def test_alert_from_dict(self):
        """Test creating alert from dictionary."""
        now = datetime.now(UTC)
        data = {
            "id": "test_alert_002",
            "severity": "INFO",
            "metric_name": "test_metric",
            "current_value": 25.0,
            "threshold_value": 50.0,
            "message": "Info alert",
            "recommendations": ["Check this"],
            "timestamp": now.isoformat(),
            "resolved": False,
            "resolved_at": None,
            "snoozed_until": None,
        }

        alert = Alert.from_dict(data)

        assert alert.id == "test_alert_002"
        assert alert.severity == AlertSeverity.INFO
        assert alert.current_value == 25.0
        assert alert.timestamp == now


class TestAlertEngine:
    """Test AlertEngine functionality."""

    @pytest.fixture
    def temp_db(self):
        """Create temporary database for testing."""
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        yield path
        # Cleanup
        if os.path.exists(path):
            os.unlink(path)

    @pytest.fixture
    def engine(self, temp_db):
        """Create AlertEngine instance with temp database."""
        return AlertEngine(db_path=temp_db)

    @pytest.fixture
    def sample_metrics(self):
        """Create sample health metrics for testing."""
        return HealthMetrics(
            timestamp=datetime.now(UTC),
            total_memories=1000,
            total_code_chunks=500,
            database_size_mb=50.0,
            avg_search_latency_ms=25.0,
            avg_result_relevance=0.75,
            cache_hit_rate=0.80,
            noise_ratio=0.20,
            stale_memories=100,
            active_projects=5,
            search_count_24h=100,
            indexing_errors_24h=0,
        )

    def test_init_creates_database(self, temp_db):
        """Test that initialization creates database schema."""
        engine = AlertEngine(db_path=temp_db)

        # Verify tables exist
        import sqlite3

        with sqlite3.connect(temp_db) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='alert_history'"
            )
            assert cursor.fetchone() is not None

    def test_check_threshold_operators(self, engine):
        """Test threshold checking with different operators."""
        # Greater than
        assert engine._check_threshold(150.0, ">", 100.0)
        assert not engine._check_threshold(50.0, ">", 100.0)

        # Less than
        assert engine._check_threshold(50.0, "<", 100.0)
        assert not engine._check_threshold(150.0, "<", 100.0)

        # Greater than or equal
        assert engine._check_threshold(100.0, ">=", 100.0)
        assert engine._check_threshold(150.0, ">=", 100.0)
        assert not engine._check_threshold(50.0, ">=", 100.0)

        # Less than or equal
        assert engine._check_threshold(100.0, "<=", 100.0)
        assert engine._check_threshold(50.0, "<=", 100.0)
        assert not engine._check_threshold(150.0, "<=", 100.0)

        # Equal
        assert engine._check_threshold(100.0, "==", 100.0)
        assert not engine._check_threshold(99.0, "==", 100.0)

    def test_evaluate_metrics_no_violations(self, engine, sample_metrics):
        """Test evaluating metrics with no threshold violations."""
        # All metrics are within acceptable ranges
        alerts = engine.evaluate_metrics(sample_metrics)

        # Should have no alerts
        assert len(alerts) == 0

    def test_evaluate_metrics_critical_low_relevance(self, engine):
        """Test alert generation for critically low search relevance."""
        metrics = HealthMetrics(
            timestamp=datetime.now(UTC),
            total_memories=1000,
            total_code_chunks=500,
            database_size_mb=50.0,
            avg_search_latency_ms=25.0,
            avg_result_relevance=0.40,  # Below critical threshold (0.50)
            cache_hit_rate=0.80,
            noise_ratio=0.20,
            stale_memories=100,
            active_projects=5,
            search_count_24h=100,
            indexing_errors_24h=0,
        )

        alerts = engine.evaluate_metrics(metrics)

        # Should have critical alert for low relevance
        assert len(alerts) > 0
        critical_alerts = [a for a in alerts if a.severity == AlertSeverity.CRITICAL]
        assert len(critical_alerts) > 0

        relevance_alert = next(
            (a for a in critical_alerts if a.metric_name == "avg_result_relevance"),
            None,
        )
        assert relevance_alert is not None
        assert relevance_alert.current_value == 0.40
        assert "low" in relevance_alert.message.lower()
        assert len(relevance_alert.recommendations) > 0

    def test_evaluate_metrics_high_latency(self, engine):
        """Test alert generation for high search latency."""
        metrics = HealthMetrics(
            timestamp=datetime.now(UTC),
            total_memories=1000,
            total_code_chunks=500,
            database_size_mb=50.0,
            avg_search_latency_ms=150.0,  # Above critical threshold (100.0)
            avg_result_relevance=0.75,
            cache_hit_rate=0.80,
            noise_ratio=0.20,
            stale_memories=100,
            active_projects=5,
            search_count_24h=100,
            indexing_errors_24h=0,
        )

        alerts = engine.evaluate_metrics(metrics)

        latency_alert = next(
            (
                a
                for a in alerts
                if a.metric_name == "avg_search_latency_ms"
                and a.severity == AlertSeverity.CRITICAL
            ),
            None,
        )
        assert latency_alert is not None
        assert latency_alert.current_value == 150.0
        assert "slow" in latency_alert.message.lower()

    def test_evaluate_metrics_high_noise_ratio(self, engine):
        """Test alert generation for high noise ratio."""
        metrics = HealthMetrics(
            timestamp=datetime.now(UTC),
            total_memories=1000,
            total_code_chunks=500,
            database_size_mb=50.0,
            avg_search_latency_ms=25.0,
            avg_result_relevance=0.75,
            cache_hit_rate=0.80,
            noise_ratio=0.60,  # Above critical threshold (0.50)
            stale_memories=100,
            active_projects=5,
            search_count_24h=100,
            indexing_errors_24h=0,
        )

        alerts = engine.evaluate_metrics(metrics)

        noise_alert = next(
            (
                a
                for a in alerts
                if a.metric_name == "noise_ratio"
                and a.severity == AlertSeverity.CRITICAL
            ),
            None,
        )
        assert noise_alert is not None
        assert "pollut" in noise_alert.message.lower()
        assert any("prun" in r.lower() for r in noise_alert.recommendations)

    def test_evaluate_metrics_warning_level(self, engine):
        """Test alert generation at warning level."""
        metrics = HealthMetrics(
            timestamp=datetime.now(UTC),
            total_memories=1000,
            total_code_chunks=500,
            database_size_mb=50.0,
            avg_search_latency_ms=60.0,  # Above warning (50.0), below critical (100.0)
            avg_result_relevance=0.75,
            cache_hit_rate=0.80,
            noise_ratio=0.20,
            stale_memories=100,
            active_projects=5,
            search_count_24h=100,
            indexing_errors_24h=0,
        )

        alerts = engine.evaluate_metrics(metrics)

        warning_alerts = [a for a in alerts if a.severity == AlertSeverity.WARNING]
        assert len(warning_alerts) > 0

    def test_store_and_retrieve_alerts(self, engine, sample_metrics):
        """Test storing and retrieving alerts."""
        # Create metrics that will generate alerts
        metrics = HealthMetrics(
            timestamp=datetime.now(UTC),
            total_memories=1000,
            total_code_chunks=500,
            database_size_mb=50.0,
            avg_search_latency_ms=25.0,
            avg_result_relevance=0.40,  # Critical
            cache_hit_rate=0.80,
            noise_ratio=0.20,
            stale_memories=100,
            active_projects=5,
            search_count_24h=100,
            indexing_errors_24h=0,
        )

        alerts = engine.evaluate_metrics(metrics)
        engine.store_alerts(alerts)

        # Retrieve active alerts
        active = engine.get_active_alerts()
        assert len(active) == len(alerts)
        assert all(not a.resolved for a in active)

    def test_get_alerts_by_severity(self, engine):
        """Test filtering alerts by severity."""
        # Create alerts with different severities
        now = datetime.now(UTC)
        alerts = [
            Alert(
                id="critical_1",
                severity=AlertSeverity.CRITICAL,
                metric_name="test",
                current_value=100.0,
                threshold_value=50.0,
                message="Critical alert",
                recommendations=[],
                timestamp=now,
            ),
            Alert(
                id="warning_1",
                severity=AlertSeverity.WARNING,
                metric_name="test",
                current_value=60.0,
                threshold_value=50.0,
                message="Warning alert",
                recommendations=[],
                timestamp=now,
            ),
        ]

        engine.store_alerts(alerts)

        # Get critical alerts
        critical = engine.get_alerts_by_severity(AlertSeverity.CRITICAL)
        assert len(critical) == 1
        assert critical[0].severity == AlertSeverity.CRITICAL

        # Get warning alerts
        warnings = engine.get_alerts_by_severity(AlertSeverity.WARNING)
        assert len(warnings) == 1
        assert warnings[0].severity == AlertSeverity.WARNING

    def test_resolve_alert(self, engine):
        """Test resolving an alert."""
        now = datetime.now(UTC)
        alert = Alert(
            id="resolve_test",
            severity=AlertSeverity.WARNING,
            metric_name="test",
            current_value=100.0,
            threshold_value=50.0,
            message="Test alert",
            recommendations=[],
            timestamp=now,
        )

        engine.store_alerts([alert])

        # Resolve the alert
        result = engine.resolve_alert("resolve_test")
        assert result is True

        # Verify it's no longer in active alerts
        active = engine.get_active_alerts()
        assert len(active) == 0

    def test_resolve_nonexistent_alert(self, engine):
        """Test resolving a non-existent alert."""
        result = engine.resolve_alert("nonexistent_id")
        assert result is False

    def test_snooze_alert(self, engine):
        """Test snoozing an alert."""
        now = datetime.now(UTC)
        alert = Alert(
            id="snooze_test",
            severity=AlertSeverity.INFO,
            metric_name="test",
            current_value=100.0,
            threshold_value=50.0,
            message="Test alert",
            recommendations=[],
            timestamp=now,
        )

        engine.store_alerts([alert])

        # Snooze for 24 hours
        result = engine.snooze_alert("snooze_test", hours=24)
        assert result is True

        # Should not appear in active alerts (by default)
        active = engine.get_active_alerts(include_snoozed=False)
        assert len(active) == 0

        # But should appear when including snoozed
        active_with_snoozed = engine.get_active_alerts(include_snoozed=True)
        assert len(active_with_snoozed) == 1
        assert active_with_snoozed[0].snoozed_until is not None

    def test_snooze_nonexistent_alert(self, engine):
        """Test snoozing a non-existent alert."""
        result = engine.snooze_alert("nonexistent_id", hours=1)
        assert result is False

    def test_alert_summary(self, engine):
        """Test getting alert summary."""
        now = datetime.now(UTC)
        alerts = [
            Alert(
                id="critical_1",
                severity=AlertSeverity.CRITICAL,
                metric_name="test",
                current_value=100.0,
                threshold_value=50.0,
                message="Critical 1",
                recommendations=[],
                timestamp=now,
            ),
            Alert(
                id="critical_2",
                severity=AlertSeverity.CRITICAL,
                metric_name="test",
                current_value=100.0,
                threshold_value=50.0,
                message="Critical 2",
                recommendations=[],
                timestamp=now,
            ),
            Alert(
                id="warning_1",
                severity=AlertSeverity.WARNING,
                metric_name="test",
                current_value=60.0,
                threshold_value=50.0,
                message="Warning",
                recommendations=[],
                timestamp=now,
            ),
            Alert(
                id="info_1",
                severity=AlertSeverity.INFO,
                metric_name="test",
                current_value=55.0,
                threshold_value=50.0,
                message="Info",
                recommendations=[],
                timestamp=now,
            ),
        ]

        engine.store_alerts(alerts)

        summary = engine.get_alert_summary()
        assert summary["CRITICAL"] == 2
        assert summary["WARNING"] == 1
        assert summary["INFO"] == 1
        assert summary["total"] == 4

    def test_cleanup_old_alerts(self, engine):
        """Test cleaning up old resolved alerts."""
        # Create old resolved alert
        old_time = datetime.now(UTC) - timedelta(days=100)
        old_alert = Alert(
            id="old_resolved",
            severity=AlertSeverity.INFO,
            metric_name="test",
            current_value=100.0,
            threshold_value=50.0,
            message="Old alert",
            recommendations=[],
            timestamp=old_time,
            resolved=True,
            resolved_at=old_time,
        )

        # Create recent resolved alert
        recent_time = datetime.now(UTC) - timedelta(days=10)
        recent_alert = Alert(
            id="recent_resolved",
            severity=AlertSeverity.INFO,
            metric_name="test",
            current_value=100.0,
            threshold_value=50.0,
            message="Recent alert",
            recommendations=[],
            timestamp=recent_time,
            resolved=True,
            resolved_at=recent_time,
        )

        engine.store_alerts([old_alert, recent_alert])

        # Cleanup alerts older than 30 days
        deleted = engine.cleanup_old_alerts(retention_days=30)
        assert deleted == 1  # Only old alert should be deleted

    def test_update_existing_alert(self, engine):
        """Test updating an existing alert with new metric value."""
        now = datetime.now(UTC)
        alert = Alert(
            id="update_test",
            severity=AlertSeverity.WARNING,
            metric_name="test_metric",
            current_value=60.0,
            threshold_value=50.0,
            message="Test alert",
            recommendations=[],
            timestamp=now,
        )

        engine.store_alerts([alert])

        # Update with new value
        updated_alert = Alert(
            id="update_test",
            severity=AlertSeverity.WARNING,
            metric_name="test_metric",
            current_value=75.0,  # Updated value
            threshold_value=50.0,
            message="Test alert",
            recommendations=[],
            timestamp=datetime.now(UTC),
        )

        engine.store_alerts([updated_alert])

        # Retrieve and verify update
        active = engine.get_active_alerts()
        assert len(active) == 1
        assert active[0].current_value == 75.0

    def test_generate_alert_id(self, engine):
        """Test alert ID generation."""
        now = datetime.now(UTC)
        alert_id = engine._generate_alert_id("test_metric", now)

        # Should contain metric name and date
        assert "test_metric" in alert_id
        assert now.strftime("%Y%m%d") in alert_id

    def test_custom_thresholds(self, temp_db):
        """Test creating engine with custom thresholds."""
        custom_thresholds = [
            AlertThreshold(
                metric_name="custom_metric",
                operator=">",
                threshold_value=200.0,
                severity=AlertSeverity.CRITICAL,
                message="Custom alert",
                recommendations=["Custom fix"],
            )
        ]

        engine = AlertEngine(db_path=temp_db, thresholds=custom_thresholds)
        assert len(engine.thresholds) == 1
        assert engine.thresholds[0].metric_name == "custom_metric"

    def test_multiple_severity_levels_same_metric(self, engine):
        """Test that same metric can have multiple severity thresholds."""
        # Create metrics that trigger both warning and critical
        metrics = HealthMetrics(
            timestamp=datetime.now(UTC),
            total_memories=1000,
            total_code_chunks=500,
            database_size_mb=50.0,
            avg_search_latency_ms=150.0,  # Triggers both warning and critical
            avg_result_relevance=0.75,
            cache_hit_rate=0.80,
            noise_ratio=0.20,
            stale_memories=100,
            active_projects=5,
            search_count_24h=100,
            indexing_errors_24h=0,
        )

        alerts = engine.evaluate_metrics(metrics)

        # Should have alerts for latency
        latency_alerts = [a for a in alerts if a.metric_name == "avg_search_latency_ms"]

        # Both warning and critical thresholds should be triggered
        severities = {a.severity for a in latency_alerts}
        assert AlertSeverity.WARNING in severities
        assert AlertSeverity.CRITICAL in severities

    def test_alert_with_recommendations(self, engine):
        """Test that alerts include actionable recommendations."""
        metrics = HealthMetrics(
            timestamp=datetime.now(UTC),
            total_memories=1000,
            total_code_chunks=500,
            database_size_mb=50.0,
            avg_search_latency_ms=25.0,
            avg_result_relevance=0.40,  # Critical
            cache_hit_rate=0.80,
            noise_ratio=0.20,
            stale_memories=100,
            active_projects=5,
            search_count_24h=100,
            indexing_errors_24h=0,
        )

        alerts = engine.evaluate_metrics(metrics)
        assert len(alerts) > 0

        # All alerts should have recommendations
        for alert in alerts:
            assert len(alert.recommendations) > 0
            # Recommendations should be actionable strings
            for rec in alert.recommendations:
                assert isinstance(rec, str)
                assert len(rec) > 0
