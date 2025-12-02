"""Health Service - Health monitoring, metrics, and alerting.

Extracted from MemoryRAGServer (REF-016) to provide focused health operations.

Responsibilities:
- Collect and report performance metrics
- Monitor system health
- Generate alerts for issues
- Provide capacity forecasting
- Generate health reports
"""

import asyncio
import threading
from typing import Optional, Dict, Any

from src.config import ServerConfig
from src.store import MemoryStore
from src.core.exceptions import StorageError
from src.core.tracing import get_logger

logger = get_logger(__name__)


class HealthService:
    """
    Service for health monitoring, metrics, and alerting.

    This service tracks system health, collects performance metrics,
    generates alerts, and provides capacity forecasting.
    """

    def __init__(
        self,
        store: MemoryStore,
        config: ServerConfig,
        metrics_collector: Optional[Any] = None,
        alert_engine: Optional[Any] = None,
        health_reporter: Optional[Any] = None,
        capacity_planner: Optional[Any] = None,
    ):
        """
        Initialize the Health Service.

        Args:
            store: Memory store backend
            config: Server configuration
            metrics_collector: Metrics collector for performance tracking
            alert_engine: Alert engine for issue notifications
            health_reporter: Health reporter for summaries
            capacity_planner: Capacity planner for forecasting
        """
        self.store = store
        self.config = config
        self.metrics_collector = metrics_collector
        self.alert_engine = alert_engine
        self.health_reporter = health_reporter
        self.capacity_planner = capacity_planner

        # Service statistics
        self.stats = {
            "health_checks": 0,
            "alerts_generated": 0,
            "metrics_collected": 0,
        }
        self._stats_lock = threading.Lock()

    def get_stats(self) -> Dict[str, Any]:
        """Get health service statistics."""
        with self._stats_lock:
            return self.stats.copy()

    def _calculate_simple_health_score(self, metrics) -> int:
        """Calculate 0-100 health score from metrics."""
        score = 100

        # Penalize high latency
        if metrics.get("avg_latency_ms", 0) > 100:
            score -= 20
        elif metrics.get("avg_latency_ms", 0) > 50:
            score -= 10

        # Penalize high error rate
        error_rate = metrics.get("error_rate", 0)
        if error_rate > 0.1:
            score -= 30
        elif error_rate > 0.05:
            score -= 15

        # Penalize low cache hit rate
        cache_hit_rate = metrics.get("cache_hit_rate", 1.0)
        if cache_hit_rate < 0.5:
            score -= 10

        return max(0, min(100, score))

    async def get_performance_metrics(
        self, include_history_days: int = 7
    ) -> Dict[str, Any]:
        """
        Get current and historical performance metrics.

        Args:
            include_history_days: Number of days of history to include

        Returns:
            Dict with performance metrics
        """
        try:
            with self._stats_lock:
                self.stats["health_checks"] += 1

            if not self.metrics_collector:
                return {
                    "status": "disabled",
                    "message": "Metrics collector not configured",
                }

            current_metrics = self.metrics_collector.get_current_metrics()
            historical_metrics = self.metrics_collector.get_historical_metrics(
                days=include_history_days
            )

            return {
                "status": "success",
                "current": current_metrics,
                "historical": historical_metrics,
                "period_days": include_history_days,
            }

        except Exception as e:
            logger.error(f"Failed to get performance metrics: {e}", exc_info=True)
            raise StorageError(f"Failed to get performance metrics: {e}") from e

    async def get_health_score(self) -> Dict[str, Any]:
        """
        Get overall system health score (0-100).

        Returns:
            Dict with health score and component breakdown
        """
        try:
            with self._stats_lock:
                self.stats["health_checks"] += 1

            # Check store health
            try:
                async with asyncio.timeout(30.0):
                    store_healthy = await self.store.health_check()
            except TimeoutError:
                logger.error("Store health check operation timed out after 30s")
                raise StorageError("Store health check operation timed out")

            if self.health_reporter:
                report = self.health_reporter.get_health_report()
                score = report.get("overall_score", 100)
                components = report.get("components", {})
            else:
                # Calculate simple health score
                metrics = {}
                if self.metrics_collector:
                    metrics = self.metrics_collector.get_current_metrics()

                score = self._calculate_simple_health_score(metrics)
                components = {
                    "store": "healthy" if store_healthy else "unhealthy",
                    "metrics": "healthy" if score > 70 else "degraded",
                }

            return {
                "status": "success",
                "health_score": score,
                "store_available": store_healthy,
                "components": components,
                "health_status": "healthy"
                if score >= 80
                else "degraded"
                if score >= 50
                else "unhealthy",
            }

        except Exception as e:
            logger.error(f"Failed to get health score: {e}", exc_info=True)
            raise StorageError(f"Failed to get health score: {e}") from e

    async def get_active_alerts(
        self, severity_filter: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get active system alerts.

        Args:
            severity_filter: Filter by severity (CRITICAL, WARNING, INFO)

        Returns:
            Dict with active alerts
        """
        try:
            if not self.alert_engine:
                return {
                    "status": "disabled",
                    "message": "Alert engine not configured",
                    "alerts": [],
                }

            alerts = self.alert_engine.get_active_alerts(
                severity_filter=severity_filter
            )

            return {
                "status": "success",
                "alerts": alerts,
                "total_count": len(alerts),
                "severity_filter": severity_filter,
            }

        except Exception as e:
            logger.error(f"Failed to get active alerts: {e}", exc_info=True)
            raise StorageError(f"Failed to get active alerts: {e}") from e

    async def resolve_alert(self, alert_id: str) -> Dict[str, Any]:
        """
        Mark alert as resolved.

        Args:
            alert_id: Alert ID to resolve

        Returns:
            Dict with status
        """
        try:
            if not self.alert_engine:
                return {"status": "disabled", "message": "Alert engine not configured"}

            success = self.alert_engine.resolve_alert(alert_id)

            if success:
                logger.info(f"Resolved alert: {alert_id}")
                return {
                    "status": "success",
                    "alert_id": alert_id,
                    "action": "resolved",
                }
            else:
                return {
                    "status": "not_found",
                    "alert_id": alert_id,
                    "message": f"Alert {alert_id} not found",
                }

        except Exception as e:
            logger.error(f"Failed to resolve alert: {e}", exc_info=True)
            raise StorageError(f"Failed to resolve alert: {e}") from e

    async def get_capacity_forecast(self, days_ahead: int = 30) -> Dict[str, Any]:
        """
        Forecast capacity needs.

        Args:
            days_ahead: Number of days to forecast

        Returns:
            Dict with capacity forecast
        """
        try:
            if not self.capacity_planner:
                return {
                    "status": "disabled",
                    "message": "Capacity planner not configured",
                }

            forecast = self.capacity_planner.get_forecast(days_ahead=days_ahead)

            return {
                "status": "success",
                "forecast": forecast,
                "days_ahead": days_ahead,
            }

        except Exception as e:
            logger.error(f"Failed to get capacity forecast: {e}", exc_info=True)
            raise StorageError(f"Failed to get capacity forecast: {e}") from e

    async def get_weekly_report(self) -> Dict[str, Any]:
        """
        Generate weekly health summary.

        Returns:
            Dict with weekly report
        """
        try:
            if not self.health_reporter:
                # Generate basic report
                health_result = await self.get_health_score()
                metrics_result = await self.get_performance_metrics(
                    include_history_days=7
                )

                return {
                    "status": "success",
                    "period": "weekly",
                    "health_score": health_result.get("health_score", 0),
                    "metrics_summary": metrics_result.get("current", {}),
                    "generated_by": "basic_reporter",
                }

            report = self.health_reporter.generate_weekly_report()

            return {
                "status": "success",
                "period": "weekly",
                **report,
            }

        except Exception as e:
            logger.error(f"Failed to generate weekly report: {e}", exc_info=True)
            raise StorageError(f"Failed to generate weekly report: {e}") from e

    async def start_dashboard(
        self, port: int = 8080, host: str = "localhost"
    ) -> Dict[str, Any]:
        """
        Start web dashboard server.

        Args:
            port: Port to run dashboard on
            host: Host to bind to

        Returns:
            Dict with dashboard URL
        """
        try:
            from src.dashboard.web_server import DashboardServer

            server = DashboardServer(
                metrics_collector=self.metrics_collector,
                alert_engine=self.alert_engine,
                health_reporter=self.health_reporter,
                store=self.store,
                config=self.config,
            )

            await server.start(host=host, port=port)

            logger.info(f"Dashboard started at http://{host}:{port}")

            return {
                "status": "success",
                "url": f"http://{host}:{port}",
                "host": host,
                "port": port,
            }

        except Exception as e:
            logger.error(f"Failed to start dashboard: {e}", exc_info=True)
            raise StorageError(f"Failed to start dashboard: {e}") from e

    async def collect_metrics_snapshot(self) -> None:
        """Collect and store current metrics."""
        if self.metrics_collector:
            self.metrics_collector.collect_snapshot()
            with self._stats_lock:
                self.stats["metrics_collected"] += 1
