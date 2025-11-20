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
