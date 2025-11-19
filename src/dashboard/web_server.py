"""Minimal web server for memory dashboard (UX-026 Phase 2)."""

import asyncio
import json
import logging
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse, parse_qs

from src.core.server import MemoryRAGServer
from src.config import get_config

logger = logging.getLogger(__name__)


class DashboardHandler(SimpleHTTPRequestHandler):
    """HTTP handler for dashboard requests."""

    # Class variable to store server instance
    rag_server: Optional[MemoryRAGServer] = None

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
        else:
            # Serve static files
            super().do_GET()

    def _handle_api_stats(self):
        """Handle /api/stats endpoint."""
        try:
            if not self.rag_server:
                self._send_error_response(500, "Server not initialized")
                return

            # Run async method in event loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(self.rag_server.get_dashboard_stats())
            finally:
                loop.close()

            self._send_json_response(result)
        except Exception as e:
            logger.error(f"Error handling /api/stats: {e}")
            self._send_error_response(500, str(e))

    def _handle_api_activity(self, query_string: str):
        """Handle /api/activity endpoint."""
        try:
            if not self.rag_server:
                self._send_error_response(500, "Server not initialized")
                return

            # Parse query parameters
            params = parse_qs(query_string)
            limit = int(params.get('limit', ['20'])[0])
            project_name = params.get('project', [None])[0]

            # Run async method in event loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(
                    self.rag_server.get_recent_activity(
                        limit=limit,
                        project_name=project_name
                    )
                )
            finally:
                loop.close()

            self._send_json_response(result)
        except Exception as e:
            logger.error(f"Error handling /api/activity: {e}")
            self._send_error_response(500, str(e))

    def _send_json_response(self, data: dict):
        """Send JSON response."""
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, indent=2).encode())

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

    # Initialize RAG server
    config = get_config()
    rag_server = MemoryRAGServer(config)
    await rag_server.initialize()

    # Set RAG server on handler class
    DashboardHandler.rag_server = rag_server

    # Create HTTP server
    server = HTTPServer((host, port), DashboardHandler)

    logger.info(f"Dashboard server running at http://{host}:{port}")
    logger.info("Press Ctrl+C to stop")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down dashboard server")
        server.shutdown()
        await rag_server.close()


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
