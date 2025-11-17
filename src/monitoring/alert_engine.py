"""
Alert rule engine for health monitoring.

Evaluates health metrics against thresholds and generates alerts
with recommendations for remediation.
"""

import sqlite3
import json
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, UTC
from typing import List, Optional, Dict, Any, Literal
from enum import Enum

from src.monitoring.metrics_collector import HealthMetrics


class AlertSeverity(str, Enum):
    """Alert severity levels."""

    CRITICAL = "CRITICAL"
    WARNING = "WARNING"
    INFO = "INFO"


@dataclass
class AlertThreshold:
    """Defines an alert threshold rule."""

    metric_name: str
    operator: Literal["<", ">", "<=", ">=", "=="]
    threshold_value: float
    severity: AlertSeverity
    message: str
    recommendations: List[str]


@dataclass
class Alert:
    """Represents an active alert."""

    id: str
    severity: AlertSeverity
    metric_name: str
    current_value: float
    threshold_value: float
    message: str
    recommendations: List[str]
    timestamp: datetime
    resolved: bool = False
    resolved_at: Optional[datetime] = None
    snoozed_until: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        result = asdict(self)
        result["severity"] = self.severity.value
        result["timestamp"] = self.timestamp.isoformat()
        if self.resolved_at:
            result["resolved_at"] = self.resolved_at.isoformat()
        if self.snoozed_until:
            result["snoozed_until"] = self.snoozed_until.isoformat()
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Alert":
        """Create from dictionary."""
        data["severity"] = AlertSeverity(data["severity"])
        data["timestamp"] = datetime.fromisoformat(data["timestamp"])
        if data.get("resolved_at"):
            data["resolved_at"] = datetime.fromisoformat(data["resolved_at"])
        if data.get("snoozed_until"):
            data["snoozed_until"] = datetime.fromisoformat(data["snoozed_until"])
        return cls(**data)


class AlertEngine:
    """
    Alert rule engine for evaluating metrics and generating alerts.

    Responsibilities:
    - Define and evaluate alert thresholds
    - Generate alerts for threshold violations
    - Track alert history
    - Provide snooze/resolve functionality
    - Prevent alert spam
    """

    # Default thresholds (can be customized via config)
    DEFAULT_THRESHOLDS = [
        # CRITICAL thresholds
        AlertThreshold(
            metric_name="avg_result_relevance",
            operator="<",
            threshold_value=0.50,
            severity=AlertSeverity.CRITICAL,
            message="Search quality critically low",
            recommendations=[
                "Run aggressive pruning: claude-memory prune --aggressive",
                "Archive inactive projects to reduce noise",
                "Consider rebuilding indexes from scratch",
            ],
        ),
        AlertThreshold(
            metric_name="avg_search_latency_ms",
            operator=">",
            threshold_value=100.0,
            severity=AlertSeverity.CRITICAL,
            message="Search too slow",
            recommendations=[
                "Check database size - may need archival",
                "Verify Qdrant/SQLite performance",
                "Consider enabling query optimization",
            ],
        ),
        AlertThreshold(
            metric_name="noise_ratio",
            operator=">",
            threshold_value=0.50,
            severity=AlertSeverity.CRITICAL,
            message="Database heavily polluted",
            recommendations=[
                "Run immediate pruning: claude-memory prune",
                "Archive old projects: claude-memory projects suggest-archive",
                "Review and delete unnecessary memories",
            ],
        ),
        # WARNING thresholds
        AlertThreshold(
            metric_name="avg_result_relevance",
            operator="<",
            threshold_value=0.65,
            severity=AlertSeverity.WARNING,
            message="Search quality degrading",
            recommendations=[
                "Run memory health check: claude-memory health-monitor",
                "Consider pruning stale memories",
                "Review duplicate memories for consolidation",
            ],
        ),
        AlertThreshold(
            metric_name="avg_search_latency_ms",
            operator=">",
            threshold_value=50.0,
            severity=AlertSeverity.WARNING,
            message="Search slowing down",
            recommendations=[
                "Monitor database growth",
                "Consider archiving inactive projects",
                "Check for index staleness",
            ],
        ),
        AlertThreshold(
            metric_name="noise_ratio",
            operator=">",
            threshold_value=0.30,
            severity=AlertSeverity.WARNING,
            message="Database accumulating noise",
            recommendations=[
                "Schedule regular pruning",
                "Review stale memories: claude-memory lifecycle review-stale",
                "Enable automatic lifecycle management",
            ],
        ),
        AlertThreshold(
            metric_name="stale_memories",
            operator=">",
            threshold_value=2000,
            severity=AlertSeverity.WARNING,
            message="Many stale memories detected",
            recommendations=[
                "Run pruning to clean stale memories",
                "Enable automatic pruning schedule",
                "Review lifecycle configuration",
            ],
        ),
        AlertThreshold(
            metric_name="cache_hit_rate",
            operator="<",
            threshold_value=0.70,
            severity=AlertSeverity.WARNING,
            message="Cache performance poor",
            recommendations=[
                "Review cache configuration",
                "Check if cache size is sufficient",
                "Monitor query patterns for optimization",
            ],
        ),
        # INFO thresholds
        AlertThreshold(
            metric_name="database_size_mb",
            operator=">",
            threshold_value=1000.0,
            severity=AlertSeverity.INFO,
            message="Database growing large",
            recommendations=[
                "Consider archiving old projects",
                "Review storage optimization options",
                "Plan for scaling if needed",
            ],
        ),
        AlertThreshold(
            metric_name="active_projects",
            operator=">",
            threshold_value=10,
            severity=AlertSeverity.INFO,
            message="Many active projects",
            recommendations=[
                "Review which projects are actually active",
                "Consider archiving completed projects",
                "Use project context switching for focus",
            ],
        ),
    ]

    def __init__(self, db_path: str, thresholds: Optional[List[AlertThreshold]] = None):
        """
        Initialize alert engine.

        Args:
            db_path: Path to SQLite database
            thresholds: Custom alert thresholds (uses defaults if None)
        """
        self.db_path = db_path
        self.thresholds = thresholds or self.DEFAULT_THRESHOLDS
        self._init_db()

    def _init_db(self) -> None:
        """Initialize database schema for alert tracking."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Alert history table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS alert_history (
                    id TEXT PRIMARY KEY,
                    severity TEXT NOT NULL,
                    metric_name TEXT NOT NULL,
                    current_value REAL NOT NULL,
                    threshold_value REAL NOT NULL,
                    message TEXT NOT NULL,
                    recommendations TEXT,
                    timestamp TEXT NOT NULL,
                    resolved INTEGER DEFAULT 0,
                    resolved_at TEXT,
                    snoozed_until TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_alert_history_timestamp
                ON alert_history(timestamp)
                """
            )

            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_alert_history_severity
                ON alert_history(severity)
                """
            )

            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_alert_history_resolved
                ON alert_history(resolved)
                """
            )

            conn.commit()

    def evaluate_metrics(self, metrics: HealthMetrics) -> List[Alert]:
        """
        Evaluate metrics against thresholds and generate alerts.

        Args:
            metrics: Health metrics to evaluate

        Returns:
            List of active alerts
        """
        alerts = []

        for threshold in self.thresholds:
            # Get metric value
            metric_value = getattr(metrics, threshold.metric_name, None)
            if metric_value is None:
                continue

            # Evaluate threshold
            if self._check_threshold(
                metric_value, threshold.operator, threshold.threshold_value
            ):
                # Generate alert
                alert = Alert(
                    id=self._generate_alert_id(threshold.metric_name, metrics.timestamp),
                    severity=threshold.severity,
                    metric_name=threshold.metric_name,
                    current_value=float(metric_value),
                    threshold_value=threshold.threshold_value,
                    message=threshold.message,
                    recommendations=threshold.recommendations,
                    timestamp=metrics.timestamp,
                )
                alerts.append(alert)

        return alerts

    def _check_threshold(
        self, value: float, operator: str, threshold: float
    ) -> bool:
        """Check if value violates threshold."""
        if operator == "<":
            return value < threshold
        elif operator == ">":
            return value > threshold
        elif operator == "<=":
            return value <= threshold
        elif operator == ">=":
            return value >= threshold
        elif operator == "==":
            return value == threshold
        return False

    def _generate_alert_id(self, metric_name: str, timestamp: datetime) -> str:
        """Generate unique alert ID."""
        date_str = timestamp.strftime("%Y%m%d")
        return f"alert_{metric_name}_{date_str}"

    def store_alerts(self, alerts: List[Alert]) -> None:
        """
        Store alerts in database.

        Args:
            alerts: Alerts to store
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            for alert in alerts:
                # Check if alert already exists
                cursor.execute(
                    "SELECT id FROM alert_history WHERE id = ?", (alert.id,)
                )
                if cursor.fetchone():
                    # Update existing alert
                    cursor.execute(
                        """
                        UPDATE alert_history
                        SET current_value = ?, timestamp = ?
                        WHERE id = ?
                        """,
                        (alert.current_value, alert.timestamp.isoformat(), alert.id),
                    )
                else:
                    # Insert new alert
                    cursor.execute(
                        """
                        INSERT INTO alert_history (
                            id, severity, metric_name, current_value,
                            threshold_value, message, recommendations,
                            timestamp, resolved, resolved_at, snoozed_until
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            alert.id,
                            alert.severity.value,
                            alert.metric_name,
                            alert.current_value,
                            alert.threshold_value,
                            alert.message,
                            json.dumps(alert.recommendations),
                            alert.timestamp.isoformat(),
                            1 if alert.resolved else 0,
                            alert.resolved_at.isoformat() if alert.resolved_at else None,
                            (
                                alert.snoozed_until.isoformat()
                                if alert.snoozed_until
                                else None
                            ),
                        ),
                    )

            conn.commit()

    def get_active_alerts(
        self, include_snoozed: bool = False
    ) -> List[Alert]:
        """
        Get currently active (unresolved) alerts.

        Args:
            include_snoozed: Whether to include snoozed alerts

        Returns:
            List of active alerts
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            query = """
                SELECT * FROM alert_history
                WHERE resolved = 0
            """

            if not include_snoozed:
                now = datetime.now(UTC).isoformat()
                query += f" AND (snoozed_until IS NULL OR snoozed_until < '{now}')"

            query += " ORDER BY severity DESC, timestamp DESC"

            cursor.execute(query)

            return [self._row_to_alert(row) for row in cursor.fetchall()]

    def get_alerts_by_severity(
        self, severity: AlertSeverity
    ) -> List[Alert]:
        """
        Get alerts filtered by severity.

        Args:
            severity: Alert severity to filter by

        Returns:
            List of alerts with specified severity
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM alert_history
                WHERE severity = ? AND resolved = 0
                ORDER BY timestamp DESC
                """,
                (severity.value,),
            )

            return [self._row_to_alert(row) for row in cursor.fetchall()]

    def resolve_alert(self, alert_id: str) -> bool:
        """
        Mark an alert as resolved.

        Args:
            alert_id: ID of alert to resolve

        Returns:
            True if alert was resolved, False if not found
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE alert_history
                SET resolved = 1, resolved_at = ?
                WHERE id = ?
                """,
                (datetime.now(UTC).isoformat(), alert_id),
            )
            conn.commit()
            return cursor.rowcount > 0

    def snooze_alert(self, alert_id: str, hours: int = 24) -> bool:
        """
        Snooze an alert for specified duration.

        Args:
            alert_id: ID of alert to snooze
            hours: Number of hours to snooze

        Returns:
            True if alert was snoozed, False if not found
        """
        snooze_until = datetime.now(UTC) + timedelta(hours=hours)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE alert_history
                SET snoozed_until = ?
                WHERE id = ?
                """,
                (snooze_until.isoformat(), alert_id),
            )
            conn.commit()
            return cursor.rowcount > 0

    def get_alert_summary(self) -> Dict[str, int]:
        """
        Get summary of active alerts by severity.

        Returns:
            Dictionary with counts by severity
        """
        summary = {
            "CRITICAL": 0,
            "WARNING": 0,
            "INFO": 0,
            "total": 0,
        }

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT severity, COUNT(*) as count
                FROM alert_history
                WHERE resolved = 0
                GROUP BY severity
                """
            )

            for row in cursor.fetchall():
                severity, count = row
                summary[severity] = count
                summary["total"] += count

        return summary

    def _row_to_alert(self, row: tuple) -> Alert:
        """Convert database row to Alert object."""
        return Alert(
            id=row[0],
            severity=AlertSeverity(row[1]),
            metric_name=row[2],
            current_value=row[3],
            threshold_value=row[4],
            message=row[5],
            recommendations=json.loads(row[6]) if row[6] else [],
            timestamp=datetime.fromisoformat(row[7]),
            resolved=bool(row[8]),
            resolved_at=datetime.fromisoformat(row[9]) if row[9] else None,
            snoozed_until=datetime.fromisoformat(row[10]) if row[10] else None,
        )

    def cleanup_old_alerts(self, retention_days: int = 90) -> int:
        """
        Clean up resolved alerts older than retention period.

        Args:
            retention_days: Number of days to retain resolved alerts

        Returns:
            Number of alerts deleted
        """
        cutoff = (datetime.now(UTC) - timedelta(days=retention_days)).isoformat()

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                DELETE FROM alert_history
                WHERE resolved = 1 AND resolved_at < ?
                """,
                (cutoff,),
            )
            deleted = cursor.rowcount
            conn.commit()

        return deleted
