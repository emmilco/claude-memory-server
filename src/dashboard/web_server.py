"""Minimal web server for memory dashboard (UX-026 Phase 2)."""

import asyncio
import json
import logging
import threading
from datetime import datetime
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from typing import Optional, Any
from urllib.parse import urlparse, parse_qs

from src.core.server import MemoryRAGServer
from src.config import get_config

logger = logging.getLogger(__name__)


class DateTimeEncoder(json.JSONEncoder):
    """JSON encoder that handles datetime objects."""

    def default(self, obj: Any) -> Any:
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


class DashboardHandler(SimpleHTTPRequestHandler):
    """HTTP handler for dashboard requests."""

    # Class variables to store server instance and event loop
    rag_server: Optional[MemoryRAGServer] = None
    event_loop: Optional[asyncio.AbstractEventLoop] = None

    def __init__(self, *args, **kwargs):
        # Set directory to static files
        dashboard_dir = Path(__file__).parent / "static"
        super().__init__(*args, directory=str(dashboard_dir), **kwargs)

    def do_GET(self):
        """Handle GET requests."""
        parsed_path = urlparse(self.path)

        # API endpoints
        if parsed_path.path == "/api/stats":
            self._handle_api_stats()
        elif parsed_path.path == "/api/activity":
            self._handle_api_activity(parsed_path.query)
        elif parsed_path.path == "/api/health":
            self._handle_api_health()
        elif parsed_path.path == "/api/insights":
            self._handle_api_insights()
        else:
            # Serve static files
            super().do_GET()

    def _handle_api_stats(self):
        """Handle /api/stats endpoint."""
        try:
            if not self.rag_server or not self.event_loop:
                self._send_error_response(500, "Server not initialized")
                return

            # Run async method in the dedicated event loop
            future = asyncio.run_coroutine_threadsafe(
                self.rag_server.get_dashboard_stats(),
                self.event_loop
            )
            result = future.result(timeout=10)  # 10 second timeout

            self._send_json_response(result)
        except Exception as e:
            logger.error(f"Error handling /api/stats: {e}")
            self._send_error_response(500, str(e))

    def _handle_api_activity(self, query_string: str):
        """Handle /api/activity endpoint."""
        try:
            if not self.rag_server or not self.event_loop:
                self._send_error_response(500, "Server not initialized")
                return

            # Parse query parameters
            params = parse_qs(query_string)
            limit = int(params.get('limit', ['20'])[0])
            project_name = params.get('project', [None])[0]

            # Run async method in the dedicated event loop
            future = asyncio.run_coroutine_threadsafe(
                self.rag_server.get_recent_activity(
                    limit=limit,
                    project_name=project_name
                ),
                self.event_loop
            )
            result = future.result(timeout=10)  # 10 second timeout

            self._send_json_response(result)
        except Exception as e:
            logger.error(f"Error handling /api/activity: {e}")
            self._send_error_response(500, str(e))

    def _handle_api_health(self):
        """Handle /api/health endpoint - returns system health metrics."""
        try:
            if not self.rag_server or not self.event_loop:
                self._send_error_response(500, "Server not initialized")
                return

            # Get health score and alerts in parallel
            health_future = asyncio.run_coroutine_threadsafe(
                self.rag_server.get_health_score(),
                self.event_loop
            )
            alerts_future = asyncio.run_coroutine_threadsafe(
                self.rag_server.get_active_alerts(),
                self.event_loop
            )

            health_data = health_future.result(timeout=10)
            alerts_data = alerts_future.result(timeout=10)

            # Combine into response
            response = {
                "health_score": health_data.get("overall_score", 0),
                "component_scores": health_data.get("component_scores", {}),
                "alerts": alerts_data.get("alerts", []),
                "performance_metrics": {
                    "search_latency_p50": health_data.get("metrics", {}).get("search_latency_p50_ms", 0),
                    "search_latency_p95": health_data.get("metrics", {}).get("search_latency_p95_ms", 0),
                    "cache_hit_rate": health_data.get("metrics", {}).get("cache_hit_rate", 0)
                }
            }

            self._send_json_response(response)
        except Exception as e:
            logger.error(f"Error handling /api/health: {e}")
            self._send_error_response(500, str(e))

    def _handle_api_insights(self):
        """Handle /api/insights endpoint - returns automated insights and recommendations."""
        try:
            if not self.rag_server or not self.event_loop:
                self._send_error_response(500, "Server not initialized")
                return

            # Get stats and health data for insight generation
            stats_future = asyncio.run_coroutine_threadsafe(
                self.rag_server.get_dashboard_stats(),
                self.event_loop
            )
            health_future = asyncio.run_coroutine_threadsafe(
                self.rag_server.get_health_score(),
                self.event_loop
            )

            stats_data = stats_future.result(timeout=10)
            health_data = health_future.result(timeout=10)

            # Generate insights based on data patterns
            insights = self._generate_insights(stats_data, health_data)

            self._send_json_response({"insights": insights})
        except Exception as e:
            logger.error(f"Error handling /api/insights: {e}")
            self._send_error_response(500, str(e))

    def _generate_insights(self, stats: dict, health: dict) -> list:
        """Generate automated insights based on system data."""
        insights = []

        # Get metrics
        metrics = health.get("metrics", {})
        cache_hit_rate = metrics.get("cache_hit_rate", 0)
        search_latency_p95 = metrics.get("search_latency_p95_ms", 0)

        # Insight 1: Cache performance
        if cache_hit_rate < 0.7:
            insights.append({
                "type": "performance",
                "severity": "WARNING",
                "title": "Low Cache Hit Rate",
                "message": f"Cache hit rate at {cache_hit_rate * 100:.1f}% (target: 80%)",
                "action": "Consider increasing cache size or reviewing indexing patterns",
                "priority": 2
            })
        elif cache_hit_rate >= 0.9:
            insights.append({
                "type": "performance",
                "severity": "INFO",
                "title": "Excellent Cache Performance",
                "message": f"Cache hit rate at {cache_hit_rate * 100:.1f}% - optimal performance",
                "action": None,
                "priority": 5
            })

        # Insight 2: Search latency
        if search_latency_p95 > 50:
            insights.append({
                "type": "performance",
                "severity": "WARNING",
                "title": "High Search Latency",
                "message": f"P95 search latency at {search_latency_p95:.2f}ms (target: <50ms)",
                "action": "Review index size, consider optimization",
                "priority": 2
            })

        # Insight 3: Stale projects
        projects = stats.get("projects", [])
        stale_projects = [p for p in projects if p.get("needs_reindex", False)]
        if stale_projects:
            insights.append({
                "type": "maintenance",
                "severity": "WARNING",
                "title": "Stale Projects Detected",
                "message": f"{len(stale_projects)} project(s) need reindexing",
                "action": f"Reindex: {', '.join([p['name'] for p in stale_projects[:3]])}",
                "priority": 3
            })

        # Insight 4: Project distribution
        total_memories = stats.get("total_memories", 0)
        num_projects = stats.get("num_projects", 0)
        if num_projects > 0:
            avg_memories_per_project = total_memories / num_projects
            if avg_memories_per_project < 10:
                insights.append({
                    "type": "usage",
                    "severity": "INFO",
                    "title": "Low Memory Density",
                    "message": f"Average {avg_memories_per_project:.1f} memories per project",
                    "action": "Consider consolidating small projects or adding more memories",
                    "priority": 4
                })

        # Insight 5: Overall health
        health_score = health.get("overall_score", 0)
        if health_score >= 95:
            insights.append({
                "type": "health",
                "severity": "INFO",
                "title": "System Running Optimally",
                "message": f"Health score: {health_score}/100 - all systems nominal",
                "action": None,
                "priority": 6
            })
        elif health_score < 70:
            insights.append({
                "type": "health",
                "severity": "CRITICAL",
                "title": "System Health Critical",
                "message": f"Health score: {health_score}/100 - immediate attention required",
                "action": "Check alerts and run diagnostics",
                "priority": 1
            })

        # Sort by priority (lower number = higher priority)
        insights.sort(key=lambda x: x["priority"])

        return insights

    def _send_json_response(self, data: dict):
        """Send JSON response."""
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, indent=2, cls=DateTimeEncoder).encode())

    def _send_error_response(self, code: int, message: str):
        """Send error response."""
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        error_data = {"error": message}
        self.wfile.write(json.dumps(error_data).encode())

    def log_message(self, format, *args):
        """Override to use logger instead of stderr."""
        logger.info(f"{self.address_string()} - {format % args}")


def _run_event_loop(loop: asyncio.AbstractEventLoop):
    """Run event loop in a separate thread."""
    asyncio.set_event_loop(loop)
    loop.run_forever()


async def start_dashboard_server(
    port: int = 8080,
    host: str = "localhost"
) -> None:
    """
    Start the dashboard web server.

    Args:
        port: Port to listen on (default 8080)
        host: Host to bind to (default localhost)
    """
    logger.info(f"Initializing dashboard server on {host}:{port}")

    # Create a dedicated event loop for async operations
    event_loop = asyncio.new_event_loop()

    # Start event loop in a separate thread
    loop_thread = threading.Thread(target=_run_event_loop, args=(event_loop,), daemon=True)
    loop_thread.start()

    # Initialize RAG server in the dedicated event loop
    config = get_config()
    rag_server = MemoryRAGServer(config)

    # Initialize server in the event loop
    future = asyncio.run_coroutine_threadsafe(rag_server.initialize(), event_loop)
    future.result()

    # Set RAG server and event loop on handler class
    DashboardHandler.rag_server = rag_server
    DashboardHandler.event_loop = event_loop

    # Create HTTP server
    server = HTTPServer((host, port), DashboardHandler)

    logger.info(f"Dashboard server running at http://{host}:{port}")
    logger.info("Press Ctrl+C to stop")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down dashboard server")
        server.shutdown()

        # Close RAG server in the event loop
        future = asyncio.run_coroutine_threadsafe(rag_server.close(), event_loop)
        future.result(timeout=5)

        # Stop event loop
        event_loop.call_soon_threadsafe(event_loop.stop)
        loop_thread.join(timeout=5)


def main():
    """CLI entry point for dashboard server."""
    import argparse

    parser = argparse.ArgumentParser(description="Claude Memory Dashboard Server")
    parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="Port to listen on (default: 8080)"
    )
    parser.add_argument(
        "--host",
        default="localhost",
        help="Host to bind to (default: localhost)"
    )
    args = parser.parse_args()

    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Run server
    asyncio.run(start_dashboard_server(port=args.port, host=args.host))


if __name__ == "__main__":
    main()
