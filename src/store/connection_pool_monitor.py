"""Connection pool monitoring and metrics collection.

Provides continuous monitoring of connection pool health:
- Metrics collection every 30s (configurable)
- Pool exhaustion alerts
- High latency detection
- Connection failure tracking
- Automated alerting

PERF-007: Connection Pooling - Day 2 Monitoring
"""

import asyncio
import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, UTC
from typing import Optional, List, Callable, Awaitable
from enum import Enum

logger = logging.getLogger(__name__)


class AlertSeverity(Enum):
    """Alert severity levels."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class PoolAlert:
    """Alert triggered by pool monitor."""

    severity: AlertSeverity
    message: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    metric_name: Optional[str] = None
    metric_value: Optional[float] = None

    def __repr__(self) -> str:
        return (
            f"PoolAlert({self.severity.value}, '{self.message}', "
            f"timestamp={self.timestamp.isoformat()})"
        )


@dataclass
class PoolMetrics:
    """Snapshot of pool metrics at a point in time."""

    timestamp: datetime
    active_connections: int
    idle_connections: int
    total_connections: int
    wait_queue_size: int
    acquire_latency_p95_ms: float
    acquire_latency_avg_ms: float
    total_acquires: int
    total_releases: int
    total_timeouts: int
    total_health_failures: int


class ConnectionPoolMonitor:
    """Monitor for connection pool health and performance.

    Collects metrics periodically and generates alerts based on thresholds:
    - Pool exhaustion (>90% utilization)
    - High latency (P95 > threshold)
    - Connection failures
    - Timeout spikes

    Example:
        >>> monitor = ConnectionPoolMonitor(
        ...     pool=pool,
        ...     collection_interval=30.0,
        ...     alert_callback=handle_alert
        ... )
        >>> await monitor.start()
        >>> # ... monitor runs in background ...
        >>> await monitor.stop()
    """

    def __init__(
        self,
        pool: "QdrantConnectionPool",  # Forward reference
        collection_interval: float = 30.0,
        alert_callback: Optional[Callable[[PoolAlert], Awaitable[None]]] = None,
        exhaustion_threshold: float = 0.9,  # 90% utilization
        latency_threshold_ms: float = 100.0,  # 100ms P95
    ):
        """Initialize pool monitor.

        Args:
            pool: Connection pool to monitor
            collection_interval: Seconds between metric collections
            alert_callback: Optional async callback for alerts
            exhaustion_threshold: Pool utilization % that triggers exhaustion alert
            latency_threshold_ms: P95 latency (ms) that triggers high latency alert
        """
        self.pool = pool
        self.collection_interval = collection_interval
        self.alert_callback = alert_callback
        self.exhaustion_threshold = exhaustion_threshold
        self.latency_threshold_ms = latency_threshold_ms

        # State
        self._running = False
        self._monitor_task: Optional[asyncio.Task] = None
        self._metrics_history: List[PoolMetrics] = []
        self._alerts: List[PoolAlert] = []
        self._last_collection: Optional[datetime] = None

        # Stats
        self.total_collections = 0
        self.total_alerts = 0
        self._counter_lock = threading.Lock()  # REF-030: Atomic counter operations

        logger.info(
            f"Pool monitor initialized: interval={collection_interval}s, "
            f"exhaustion_threshold={exhaustion_threshold*100}%, "
            f"latency_threshold={latency_threshold_ms}ms"
        )

    async def start(self) -> None:
        """Start monitoring in background task."""
        if self._running:
            logger.warning("Monitor already running")
            return

        self._running = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info("Pool monitor started")

    async def stop(self) -> None:
        """Stop monitoring and cleanup."""
        if not self._running:
            logger.debug("Monitor not running")
            return

        self._running = False

        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
            self._monitor_task = None

        logger.info("Pool monitor stopped")

    async def _monitor_loop(self) -> None:
        """Main monitoring loop - runs continuously."""
        logger.debug("Monitor loop starting")

        while self._running:
            try:
                await self._collect_metrics()
                await asyncio.sleep(self.collection_interval)

            except asyncio.CancelledError:
                logger.debug("Monitor loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in monitor loop: {e}")
                # Continue monitoring despite errors
                await asyncio.sleep(self.collection_interval)

        logger.debug("Monitor loop stopped")

    async def _collect_metrics(self) -> None:
        """Collect pool metrics and check for alert conditions."""
        try:
            # Get stats from pool
            stats = self.pool.stats()

            # Create metrics snapshot
            metrics = PoolMetrics(
                timestamp=datetime.now(UTC),
                active_connections=stats.active_connections,
                idle_connections=stats.idle_connections,
                total_connections=stats.pool_size,
                wait_queue_size=0,  # Will calculate from pool state
                acquire_latency_p95_ms=stats.p95_acquire_time_ms,
                acquire_latency_avg_ms=stats.avg_acquire_time_ms,
                total_acquires=stats.total_acquires,
                total_releases=stats.total_releases,
                total_timeouts=stats.total_timeouts,
                total_health_failures=stats.total_health_failures,
            )

            # Store metrics
            self._metrics_history.append(metrics)
            self._last_collection = metrics.timestamp
            with self._counter_lock:  # REF-030: Atomic counter increment
                self.total_collections += 1

            # Limit history size to prevent memory growth (keep last 1000)
            if len(self._metrics_history) > 1000:
                self._metrics_history = self._metrics_history[-1000:]

            # Check for alert conditions
            await self._check_alerts(metrics)

            logger.debug(
                f"Metrics collected: active={metrics.active_connections}, "
                f"idle={metrics.idle_connections}, p95={metrics.acquire_latency_p95_ms:.2f}ms"
            )

        except Exception as e:
            logger.error(f"Failed to collect metrics: {e}")

    async def _check_alerts(self, metrics: PoolMetrics) -> None:
        """Check metrics against thresholds and generate alerts.

        Args:
            metrics: Current pool metrics
        """
        # Check pool exhaustion
        if metrics.total_connections > 0:
            utilization = metrics.active_connections / metrics.total_connections

            if utilization >= self.exhaustion_threshold:
                await self._raise_alert(
                    AlertSeverity.WARNING if utilization < 0.95 else AlertSeverity.CRITICAL,
                    f"Pool exhaustion: {utilization*100:.1f}% utilization "
                    f"({metrics.active_connections}/{metrics.total_connections} active)",
                    metric_name="pool_utilization",
                    metric_value=utilization,
                )

        # Check high latency
        if metrics.acquire_latency_p95_ms > self.latency_threshold_ms:
            await self._raise_alert(
                AlertSeverity.WARNING,
                f"High acquire latency: P95={metrics.acquire_latency_p95_ms:.2f}ms "
                f"(threshold={self.latency_threshold_ms}ms)",
                metric_name="acquire_latency_p95_ms",
                metric_value=metrics.acquire_latency_p95_ms,
            )

        # Check for timeout spikes
        if len(self._metrics_history) > 1:
            prev_metrics = self._metrics_history[-2]
            new_timeouts = metrics.total_timeouts - prev_metrics.total_timeouts

            if new_timeouts > 0:
                await self._raise_alert(
                    AlertSeverity.WARNING,
                    f"Connection timeouts detected: {new_timeouts} new timeout(s)",
                    metric_name="timeouts",
                    metric_value=float(new_timeouts),
                )

        # Check for health check failures
        if len(self._metrics_history) > 1:
            prev_metrics = self._metrics_history[-2]
            new_failures = metrics.total_health_failures - prev_metrics.total_health_failures

            if new_failures > 0:
                await self._raise_alert(
                    AlertSeverity.WARNING,
                    f"Health check failures detected: {new_failures} new failure(s)",
                    metric_name="health_failures",
                    metric_value=float(new_failures),
                )

    async def _raise_alert(
        self,
        severity: AlertSeverity,
        message: str,
        metric_name: Optional[str] = None,
        metric_value: Optional[float] = None,
    ) -> None:
        """Raise an alert and invoke callback if configured.

        Args:
            severity: Alert severity level
            message: Alert message
            metric_name: Optional metric name that triggered alert
            metric_value: Optional metric value
        """
        alert = PoolAlert(
            severity=severity,
            message=message,
            metric_name=metric_name,
            metric_value=metric_value,
        )

        self._alerts.append(alert)
        with self._counter_lock:  # REF-030: Atomic counter increment
            self.total_alerts += 1

        # Limit alert history
        if len(self._alerts) > 1000:
            self._alerts = self._alerts[-1000:]

        # Log alert
        log_func = logger.critical if severity == AlertSeverity.CRITICAL else logger.warning
        log_func(f"Pool alert: {alert}")

        # Invoke callback if configured
        if self.alert_callback:
            try:
                await self.alert_callback(alert)
            except Exception as e:
                logger.error(f"Error invoking alert callback: {e}")

    def get_current_metrics(self) -> Optional[PoolMetrics]:
        """Get most recent metrics snapshot.

        Returns:
            PoolMetrics or None if no metrics collected yet
        """
        return self._metrics_history[-1] if self._metrics_history else None

    def get_metrics_history(self, limit: int = 100) -> List[PoolMetrics]:
        """Get recent metrics history.

        Args:
            limit: Maximum number of metrics to return

        Returns:
            List of recent PoolMetrics, newest first
        """
        return list(reversed(self._metrics_history[-limit:]))

    def get_recent_alerts(self, limit: int = 100) -> List[PoolAlert]:
        """Get recent alerts.

        Args:
            limit: Maximum number of alerts to return

        Returns:
            List of recent alerts, newest first
        """
        return list(reversed(self._alerts[-limit:]))

    def get_stats(self) -> dict:
        """Get monitor statistics.

        Returns:
            dict: Monitor stats including collection count, alert count, etc.
        """
        current = self.get_current_metrics()

        return {
            "running": self._running,
            "total_collections": self.total_collections,
            "total_alerts": self.total_alerts,
            "metrics_history_size": len(self._metrics_history),
            "alerts_history_size": len(self._alerts),
            "last_collection": self._last_collection.isoformat() if self._last_collection else None,
            "current_metrics": {
                "active_connections": current.active_connections,
                "idle_connections": current.idle_connections,
                "total_connections": current.total_connections,
                "acquire_latency_p95_ms": current.acquire_latency_p95_ms,
            } if current else None,
        }

    def reset_stats(self) -> None:
        """Reset monitor statistics (does not clear history)."""
        self.total_collections = 0
        self.total_alerts = 0
        logger.debug("Monitor stats reset")
