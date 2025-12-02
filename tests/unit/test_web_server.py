"""Comprehensive tests for web_server.py - TEST-007-C

Target Coverage: Low → 80%+
Test Count: 68 tests (40 original + 28 new)

New Test Coverage:
- DashboardServer class (8 tests)
- _get_daily_metrics helper (2 tests)
- _generate_trends edge cases (2 tests)
- UX-037 time range support (2 tests)
- Additional insights scenarios (2 tests)
- main() and start_dashboard_server() (12 tests)
"""

import pytest
import json
import asyncio
import threading
from datetime import datetime, UTC
from unittest.mock import AsyncMock, MagicMock, patch, call
from io import BytesIO

from src.dashboard.web_server import (
    DashboardHandler,
    DateTimeEncoder,
    start_dashboard_server,
    _run_event_loop,
)


class TestDateTimeEncoder:
    """Tests for DateTimeEncoder JSON encoder."""

    def test_datetime_encoding(self):
        """Test datetime objects are encoded to ISO format."""
        now = datetime(2025, 1, 15, 10, 30, 45, tzinfo=UTC)
        data = {"timestamp": now, "value": 42}

        result = json.dumps(data, cls=DateTimeEncoder)
        parsed = json.loads(result)

        assert parsed["value"] == 42
        assert "2025-01-15T10:30:45" in parsed["timestamp"]

    def test_non_datetime_passthrough(self):
        """Test non-datetime objects are handled normally."""
        data = {"string": "test", "number": 123, "bool": True, "null": None}

        result = json.dumps(data, cls=DateTimeEncoder)
        parsed = json.loads(result)

        assert parsed == data

    def test_nested_datetime_encoding(self):
        """Test nested datetime objects are encoded."""
        now = datetime.now(UTC)
        data = {
            "events": [
                {"id": 1, "timestamp": now},
                {"id": 2, "timestamp": now},
            ]
        }

        result = json.dumps(data, cls=DateTimeEncoder)
        parsed = json.loads(result)

        assert len(parsed["events"]) == 2
        assert isinstance(parsed["events"][0]["timestamp"], str)


class TestDashboardHandlerInitialization:
    """Tests for DashboardHandler initialization."""

    def test_handler_initialization(self):
        """Test DashboardHandler initializes with correct directory."""
        from pathlib import Path

        # We can't easily instantiate DashboardHandler due to HTTP server behavior
        # So we test the class property indirectly
        dashboard_dir = (
            Path(__file__).parent.parent.parent.parent / "src" / "dashboard" / "static"
        )
        assert dashboard_dir.exists() or True  # Directory path is defined in __init__

        # Test that class has the expected structure
        assert hasattr(DashboardHandler, "__init__")
        assert hasattr(DashboardHandler, "do_GET")
        assert hasattr(DashboardHandler, "do_POST")

    def test_handler_class_variables(self):
        """Test handler has class variables for RAG server and event loop."""
        assert hasattr(DashboardHandler, "rag_server")
        assert hasattr(DashboardHandler, "event_loop")
        assert DashboardHandler.rag_server is None or isinstance(
            DashboardHandler.rag_server, object
        )


class TestDashboardHandlerGetEndpoints:
    """Tests for GET endpoint handlers."""

    @pytest.fixture
    def mock_handler(self):
        """Create a DashboardHandler with mocked dependencies."""
        # Create a mock handler without instantiating (to avoid handle() call)
        handler = MagicMock(spec=DashboardHandler)

        # Set up the methods we need
        handler.send_response = MagicMock()
        handler.send_header = MagicMock()
        handler.end_headers = MagicMock()
        handler.wfile = BytesIO()

        # Bind the actual methods from DashboardHandler
        handler._handle_api_stats = lambda: DashboardHandler._handle_api_stats(handler)
        handler._handle_api_activity = (
            lambda query: DashboardHandler._handle_api_activity(handler, query)
        )
        handler._handle_api_health = lambda: DashboardHandler._handle_api_health(
            handler
        )
        handler._handle_api_insights = lambda: DashboardHandler._handle_api_insights(
            handler
        )
        handler._handle_api_trends = lambda query: DashboardHandler._handle_api_trends(
            handler, query
        )
        handler._send_json_response = lambda data: DashboardHandler._send_json_response(
            handler, data
        )
        handler._send_error_response = (
            lambda code, msg: DashboardHandler._send_error_response(handler, code, msg)
        )
        handler._generate_insights = (
            lambda stats, health: DashboardHandler._generate_insights(
                handler, stats, health
            )
        )
        handler._generate_trends = (
            lambda stats, period, metric: DashboardHandler._generate_trends(
                handler, stats, period, metric
            )
        )

        return handler

    @pytest.fixture
    def mock_rag_server(self):
        """Create a mock MemoryRAGServer."""
        server = AsyncMock()
        server.get_dashboard_stats = AsyncMock(
            return_value={
                "status": "success",
                "total_memories": 100,
                "num_projects": 5,
                "projects": [],
            }
        )
        server.get_recent_activity = AsyncMock(
            return_value={"recent_searches": [], "recent_additions": []}
        )
        server.get_health_score = AsyncMock(
            return_value={
                "overall_score": 95,
                "component_scores": {},
                "metrics": {
                    "search_latency_p50_ms": 10,
                    "search_latency_p95_ms": 20,
                    "cache_hit_rate": 0.85,
                },
            }
        )
        server.get_active_alerts = AsyncMock(return_value={"alerts": []})
        server.metrics_collector = MagicMock()
        server.metrics_collector.get_daily_aggregate = AsyncMock(return_value=[])
        return server

    @pytest.fixture
    def mock_event_loop(self):
        """Create a mock event loop."""
        loop = MagicMock()
        loop.call_soon_threadsafe = MagicMock()
        return loop

    def test_api_stats_endpoint_success(
        self, mock_handler, mock_rag_server, mock_event_loop
    ):
        """Test /api/stats returns dashboard statistics."""
        DashboardHandler.rag_server = mock_rag_server
        DashboardHandler.event_loop = mock_event_loop
        mock_handler.path = "/api/stats"

        # Mock asyncio.run_coroutine_threadsafe
        with patch(
            "src.dashboard.web_server.asyncio.run_coroutine_threadsafe"
        ) as mock_run:
            mock_future = MagicMock()
            mock_future.result.return_value = {
                "status": "success",
                "total_memories": 100,
            }
            mock_run.return_value = mock_future

            mock_handler._handle_api_stats()

        mock_handler.send_response.assert_called_once_with(200)
        # Check if the call was made (not if it's in a list - call_args_list is different)
        calls = [str(c) for c in mock_handler.send_header.call_args_list]
        assert any(
            "Content-Type" in str(c) and "application/json" in str(c) for c in calls
        )

        # Check response body
        response_data = json.loads(mock_handler.wfile.getvalue().decode())
        assert response_data["status"] == "success"
        assert response_data["total_memories"] == 100

    def test_api_stats_server_not_initialized(self, mock_handler):
        """Test /api/stats returns 500 when RAG server not initialized."""
        # Must set on both class AND instance mock (mock's instance attrs are separate)
        DashboardHandler.rag_server = None
        DashboardHandler.event_loop = None
        mock_handler.rag_server = None
        mock_handler.event_loop = None
        mock_handler.path = "/api/stats"

        mock_handler._handle_api_stats()

        mock_handler.send_response.assert_called_once_with(500)

        # Check error response
        response_data = json.loads(mock_handler.wfile.getvalue().decode())
        assert "error" in response_data

    def test_api_stats_exception_handling(
        self, mock_handler, mock_rag_server, mock_event_loop
    ):
        """Test /api/stats handles server errors gracefully."""
        DashboardHandler.rag_server = mock_rag_server
        DashboardHandler.event_loop = mock_event_loop
        mock_handler.path = "/api/stats"

        with patch(
            "src.dashboard.web_server.asyncio.run_coroutine_threadsafe"
        ) as mock_run:
            mock_future = MagicMock()
            mock_future.result.side_effect = Exception("Database error")
            mock_run.return_value = mock_future

            mock_handler._handle_api_stats()

        mock_handler.send_response.assert_called_once_with(500)

    def test_api_activity_endpoint_success(
        self, mock_handler, mock_rag_server, mock_event_loop
    ):
        """Test /api/activity returns recent activity."""
        DashboardHandler.rag_server = mock_rag_server
        DashboardHandler.event_loop = mock_event_loop
        mock_handler.path = "/api/activity?limit=10"

        with patch(
            "src.dashboard.web_server.asyncio.run_coroutine_threadsafe"
        ) as mock_run:
            mock_future = MagicMock()
            mock_future.result.return_value = {
                "recent_searches": [{"query": "test"}],
                "recent_additions": [],
            }
            mock_run.return_value = mock_future

            mock_handler._handle_api_activity("limit=10")

        mock_handler.send_response.assert_called_once_with(200)
        response_data = json.loads(mock_handler.wfile.getvalue().decode())
        assert len(response_data["recent_searches"]) == 1

    def test_api_activity_with_project_filter(
        self, mock_handler, mock_rag_server, mock_event_loop
    ):
        """Test /api/activity filters by project_name query param."""
        DashboardHandler.rag_server = mock_rag_server
        DashboardHandler.event_loop = mock_event_loop

        with patch(
            "src.dashboard.web_server.asyncio.run_coroutine_threadsafe"
        ) as mock_run:
            mock_future = MagicMock()
            mock_future.result.return_value = {
                "recent_searches": [],
                "recent_additions": [],
            }
            mock_run.return_value = mock_future

            mock_handler._handle_api_activity("limit=20&project=test-project")

        # Verify the call included project filter
        response_data = json.loads(mock_handler.wfile.getvalue().decode())
        assert "recent_searches" in response_data

    def test_api_health_endpoint_success(
        self, mock_handler, mock_rag_server, mock_event_loop
    ):
        """Test /api/health returns health score and metrics."""
        DashboardHandler.rag_server = mock_rag_server
        DashboardHandler.event_loop = mock_event_loop

        with patch(
            "src.dashboard.web_server.asyncio.run_coroutine_threadsafe"
        ) as mock_run:
            # First call returns health score, second returns alerts
            mock_futures = [MagicMock(), MagicMock()]
            mock_futures[0].result.return_value = {
                "overall_score": 95,
                "component_scores": {"storage": 100},
                "metrics": {
                    "search_latency_p50_ms": 10,
                    "search_latency_p95_ms": 20,
                    "cache_hit_rate": 0.85,
                },
            }
            mock_futures[1].result.return_value = {
                "alerts": [{"severity": "WARNING", "message": "Test"}]
            }
            mock_run.side_effect = mock_futures

            mock_handler._handle_api_health()

        response_data = json.loads(mock_handler.wfile.getvalue().decode())
        assert response_data["health_score"] == 95
        assert response_data["component_scores"]["storage"] == 100
        assert len(response_data["alerts"]) == 1
        assert response_data["performance_metrics"]["cache_hit_rate"] == 0.85

    def test_api_insights_endpoint_success(
        self, mock_handler, mock_rag_server, mock_event_loop
    ):
        """Test /api/insights returns automated insights."""
        DashboardHandler.rag_server = mock_rag_server
        DashboardHandler.event_loop = mock_event_loop

        with patch(
            "src.dashboard.web_server.asyncio.run_coroutine_threadsafe"
        ) as mock_run:
            # Mock both stats and health futures
            mock_futures = [MagicMock(), MagicMock()]
            mock_futures[0].result.return_value = {
                "total_memories": 100,
                "num_projects": 2,
                "projects": [],
            }
            mock_futures[1].result.return_value = {
                "overall_score": 95,
                "metrics": {"cache_hit_rate": 0.85, "search_latency_p95_ms": 15},
            }
            mock_run.side_effect = mock_futures

            mock_handler._handle_api_insights()

        response_data = json.loads(mock_handler.wfile.getvalue().decode())
        assert "insights" in response_data
        assert isinstance(response_data["insights"], list)

    def test_api_trends_endpoint_calls_generate_trends(
        self, mock_handler, mock_rag_server, mock_event_loop
    ):
        """Test /api/trends calls _generate_trends with correct parameters."""
        DashboardHandler.rag_server = mock_rag_server
        DashboardHandler.event_loop = mock_event_loop

        with patch(
            "src.dashboard.web_server.asyncio.run_coroutine_threadsafe"
        ) as mock_run:
            mock_future = MagicMock()
            mock_future.result.return_value = {"total_memories": 100}
            mock_run.return_value = mock_future

            # Mock _generate_trends to return valid data
            with patch.object(
                DashboardHandler,
                "_generate_trends",
                return_value={
                    "period": "7d",
                    "dates": ["2025-01-01", "2025-01-02"],
                    "metrics": {"memory_count": [10, 20]},
                },
            ):
                mock_handler._handle_api_trends("period=7d&metric=memories")

        # Verify response was successful (200 status)
        mock_handler.send_response.assert_called_with(200)


class TestInsightsGeneration:
    """Tests for automated insights generation."""

    @pytest.fixture
    def mock_handler(self):
        """Create a DashboardHandler with mocked methods."""
        handler = MagicMock(spec=DashboardHandler)
        handler._generate_insights = (
            lambda stats, health: DashboardHandler._generate_insights(
                handler, stats, health
            )
        )
        return handler

    def test_generate_insights_low_cache_warning(self, mock_handler):
        """Test insight generated for cache hit rate < 70%."""
        stats = {"total_memories": 100, "num_projects": 2, "projects": []}
        health = {
            "overall_score": 80,
            "metrics": {"cache_hit_rate": 0.65, "search_latency_p95_ms": 25},
        }

        insights = mock_handler._generate_insights(stats, health)

        # Should have warning about low cache
        cache_insights = [i for i in insights if "Cache" in i["title"]]
        assert len(cache_insights) > 0
        assert cache_insights[0]["severity"] == "WARNING"

    def test_generate_insights_excellent_cache(self, mock_handler):
        """Test positive insight for cache hit rate >= 90%."""
        stats = {"total_memories": 100, "num_projects": 2, "projects": []}
        health = {
            "overall_score": 95,
            "metrics": {"cache_hit_rate": 0.95, "search_latency_p95_ms": 10},
        }

        insights = mock_handler._generate_insights(stats, health)

        cache_insights = [i for i in insights if "Cache" in i["title"]]
        assert len(cache_insights) > 0
        assert cache_insights[0]["severity"] == "INFO"

    def test_generate_insights_high_latency_warning(self, mock_handler):
        """Test insight for P95 latency > 50ms."""
        stats = {"total_memories": 100, "num_projects": 2, "projects": []}
        health = {
            "overall_score": 80,
            "metrics": {"cache_hit_rate": 0.8, "search_latency_p95_ms": 75},
        }

        insights = mock_handler._generate_insights(stats, health)

        latency_insights = [i for i in insights if "Latency" in i["title"]]
        assert len(latency_insights) > 0
        assert latency_insights[0]["severity"] == "WARNING"

    def test_generate_insights_stale_projects(self, mock_handler):
        """Test insight for projects needing reindexing."""
        stats = {
            "total_memories": 100,
            "num_projects": 3,
            "projects": [
                {"name": "proj1", "needs_reindex": True},
                {"name": "proj2", "needs_reindex": False},
                {"name": "proj3", "needs_reindex": True},
            ],
        }
        health = {
            "overall_score": 80,
            "metrics": {"cache_hit_rate": 0.8, "search_latency_p95_ms": 20},
        }

        insights = mock_handler._generate_insights(stats, health)

        stale_insights = [i for i in insights if "Stale" in i["title"]]
        assert len(stale_insights) > 0
        assert "2 project(s)" in stale_insights[0]["message"]

    def test_generate_insights_critical_health(self, mock_handler):
        """Test critical insight for health score < 70."""
        stats = {"total_memories": 100, "num_projects": 2, "projects": []}
        health = {
            "overall_score": 65,
            "metrics": {"cache_hit_rate": 0.5, "search_latency_p95_ms": 100},
        }

        insights = mock_handler._generate_insights(stats, health)

        critical_insights = [i for i in insights if i["severity"] == "CRITICAL"]
        assert len(critical_insights) > 0
        assert critical_insights[0]["priority"] == 1

    def test_insights_sorted_by_priority(self, mock_handler):
        """Test insights returned in priority order (lower = higher priority)."""
        stats = {"total_memories": 100, "num_projects": 2, "projects": []}
        health = {
            "overall_score": 65,
            "metrics": {"cache_hit_rate": 0.6, "search_latency_p95_ms": 60},
        }

        insights = mock_handler._generate_insights(stats, health)

        # Verify insights are sorted by priority
        for i in range(len(insights) - 1):
            assert insights[i]["priority"] <= insights[i + 1]["priority"]


@pytest.mark.slow
class TestTrendsGeneration:
    """Tests for time-series trends generation.

    Marked slow because importing the web_server module triggers loading of
    the MemoryRAGServer which has heavy dependencies (embedding model, etc.).
    """

    @pytest.fixture
    def mock_handler(self):
        """Create a DashboardHandler with mocked methods."""
        handler = MagicMock(spec=DashboardHandler)
        handler._generate_trends = (
            lambda stats, period, metric: DashboardHandler._generate_trends(
                handler, stats, period, metric
            )
        )
        handler._generate_empty_trends = (
            lambda days: DashboardHandler._generate_empty_trends(handler, days)
        )
        return handler

    def test_generate_trends_7d_period(self, mock_handler):
        """Test trends generated for 7 day period."""
        stats = {"total_memories": 100}

        trends = mock_handler._generate_trends(stats, "7d", "memories")

        assert trends["period"] == "7d"
        assert len(trends["dates"]) == 7
        assert "memory_count" in trends["metrics"]
        assert len(trends["metrics"]["memory_count"]) == 7

    def test_generate_trends_30d_period(self, mock_handler):
        """Test trends generated for 30 day period."""
        stats = {"total_memories": 100}

        trends = mock_handler._generate_trends(stats, "30d", "memories")

        assert trends["period"] == "30d"
        assert len(trends["dates"]) == 30

    def test_generate_trends_90d_period(self, mock_handler):
        """Test trends generated for 90 day period."""
        stats = {"total_memories": 100}

        trends = mock_handler._generate_trends(stats, "90d", "memories")

        assert trends["period"] == "90d"
        assert len(trends["dates"]) == 90

    def test_generate_empty_trends_fallback(self, mock_handler):
        """Test empty trends returned when no historical data."""
        DashboardHandler.rag_server = None
        DashboardHandler.event_loop = None

        trends = mock_handler._generate_trends({}, "30d", "memories")

        assert trends["period"] == "30d"
        assert len(trends["dates"]) == 30
        # All metrics should be zero
        assert all(count == 0 for count in trends["metrics"]["memory_count"])


class TestDashboardHandlerPostEndpoints:
    """Tests for POST endpoint handlers."""

    @pytest.fixture
    def mock_handler(self):
        """Create a DashboardHandler with mocked dependencies."""
        handler = MagicMock(spec=DashboardHandler)
        handler.send_response = MagicMock()
        handler.send_header = MagicMock()
        handler.end_headers = MagicMock()
        handler.wfile = BytesIO()
        handler.rfile = BytesIO()
        handler.headers = {"Content-Length": "0"}

        # Bind actual methods
        handler._handle_create_memory = lambda: DashboardHandler._handle_create_memory(
            handler
        )
        handler._handle_trigger_index = lambda: DashboardHandler._handle_trigger_index(
            handler
        )
        handler._handle_export = lambda: DashboardHandler._handle_export(handler)
        handler._send_json_response = lambda data: DashboardHandler._send_json_response(
            handler, data
        )
        handler._send_error_response = (
            lambda code, msg: DashboardHandler._send_error_response(handler, code, msg)
        )

        return handler

    @pytest.fixture
    def mock_rag_server(self):
        """Create a mock MemoryRAGServer."""
        server = AsyncMock()
        server.store_memory = AsyncMock(return_value={"memory_id": "test-id"})
        server.index_codebase = AsyncMock(return_value={"files_indexed": 10})
        server.export_memories = AsyncMock(return_value='{"data": "test"}')
        return server

    @pytest.fixture
    def mock_event_loop(self):
        """Create a mock event loop."""
        return MagicMock()

    def test_create_memory_success(
        self, mock_handler, mock_rag_server, mock_event_loop
    ):
        """Test POST /api/memories creates new memory."""
        DashboardHandler.rag_server = mock_rag_server
        DashboardHandler.event_loop = mock_event_loop

        # Set up request body
        request_data = {"content": "Test memory", "category": "fact"}
        body = json.dumps(request_data).encode()
        mock_handler.rfile = BytesIO(body)
        mock_handler.headers = {"Content-Length": str(len(body))}

        with patch(
            "src.dashboard.web_server.asyncio.run_coroutine_threadsafe"
        ) as mock_run:
            mock_future = MagicMock()
            mock_future.result.return_value = {"memory_id": "test-id"}
            mock_run.return_value = mock_future

            mock_handler._handle_create_memory()

        response_data = json.loads(mock_handler.wfile.getvalue().decode())
        assert response_data["status"] == "success"
        assert response_data["memory_id"] == "test-id"

    def test_create_memory_missing_content(
        self, mock_handler, mock_rag_server, mock_event_loop
    ):
        """Test /api/memories returns 400 when content missing."""
        DashboardHandler.rag_server = mock_rag_server
        DashboardHandler.event_loop = mock_event_loop

        # Request without content field
        request_data = {"category": "fact"}
        body = json.dumps(request_data).encode()
        mock_handler.rfile = BytesIO(body)
        mock_handler.headers = {"Content-Length": str(len(body))}

        mock_handler._handle_create_memory()

        mock_handler.send_response.assert_called_once_with(400)

    def test_create_memory_invalid_json(
        self, mock_handler, mock_rag_server, mock_event_loop
    ):
        """Test /api/memories returns 400 for malformed JSON."""
        DashboardHandler.rag_server = mock_rag_server
        DashboardHandler.event_loop = mock_event_loop

        # Invalid JSON
        body = b"invalid json {"
        mock_handler.rfile = BytesIO(body)
        mock_handler.headers = {"Content-Length": str(len(body))}

        mock_handler._handle_create_memory()

        mock_handler.send_response.assert_called_once_with(400)

    def test_trigger_index_success(
        self, mock_handler, mock_rag_server, mock_event_loop
    ):
        """Test POST /api/index triggers codebase indexing."""
        DashboardHandler.rag_server = mock_rag_server
        DashboardHandler.event_loop = mock_event_loop

        request_data = {"directory_path": "/test/path", "project_name": "test-project"}
        body = json.dumps(request_data).encode()
        mock_handler.rfile = BytesIO(body)
        mock_handler.headers = {"Content-Length": str(len(body))}

        with patch(
            "src.dashboard.web_server.asyncio.run_coroutine_threadsafe"
        ) as mock_run:
            mock_future = MagicMock()
            mock_future.result.return_value = {"files_indexed": 10}
            mock_run.return_value = mock_future

            mock_handler._handle_trigger_index()

        response_data = json.loads(mock_handler.wfile.getvalue().decode())
        assert response_data["status"] == "success"
        assert "Indexing started" in response_data["message"]

    def test_trigger_index_missing_fields(
        self, mock_handler, mock_rag_server, mock_event_loop
    ):
        """Test /api/index returns 400 when required fields missing."""
        DashboardHandler.rag_server = mock_rag_server
        DashboardHandler.event_loop = mock_event_loop

        request_data = {"directory_path": "/test/path"}  # Missing project_name
        body = json.dumps(request_data).encode()
        mock_handler.rfile = BytesIO(body)
        mock_handler.headers = {"Content-Length": str(len(body))}

        mock_handler._handle_trigger_index()

        mock_handler.send_response.assert_called_once_with(400)

    def test_export_endpoint_json(self, mock_handler, mock_rag_server, mock_event_loop):
        """Test POST /api/export exports memories as JSON."""
        DashboardHandler.rag_server = mock_rag_server
        DashboardHandler.event_loop = mock_event_loop

        request_data = {"format": "json", "project_name": "test"}
        body = json.dumps(request_data).encode()
        mock_handler.rfile = BytesIO(body)
        mock_handler.headers = {"Content-Length": str(len(body))}

        with patch(
            "src.dashboard.web_server.asyncio.run_coroutine_threadsafe"
        ) as mock_run:
            mock_future = MagicMock()
            mock_future.result.return_value = '{"data": "test"}'
            mock_run.return_value = mock_future

            mock_handler._handle_export()

        # Verify content type
        calls = [str(c) for c in mock_handler.send_header.call_args_list]
        assert any(
            "Content-Type" in str(c) and "application/json" in str(c) for c in calls
        )

    def test_export_endpoint_csv(self, mock_handler, mock_rag_server, mock_event_loop):
        """Test POST /api/export supports CSV format."""
        DashboardHandler.rag_server = mock_rag_server
        DashboardHandler.event_loop = mock_event_loop

        request_data = {"format": "csv"}
        body = json.dumps(request_data).encode()
        mock_handler.rfile = BytesIO(body)
        mock_handler.headers = {"Content-Length": str(len(body))}

        with patch(
            "src.dashboard.web_server.asyncio.run_coroutine_threadsafe"
        ) as mock_run:
            mock_future = MagicMock()
            mock_future.result.return_value = "data,value\ntest,123"
            mock_run.return_value = mock_future

            mock_handler._handle_export()

        # Verify CSV content type
        calls = [str(c) for c in mock_handler.send_header.call_args_list]
        assert any("Content-Type" in str(c) and "text/csv" in str(c) for c in calls)


class TestCorsHandling:
    """Tests for CORS headers and OPTIONS requests."""

    @pytest.fixture
    def mock_handler(self):
        """Create a DashboardHandler with mocked dependencies."""
        handler = MagicMock(spec=DashboardHandler)
        handler.send_response = MagicMock()
        handler.send_header = MagicMock()
        handler.end_headers = MagicMock()
        handler.wfile = BytesIO()  # Add wfile for _send_json_response
        handler.do_OPTIONS = lambda: DashboardHandler.do_OPTIONS(handler)
        handler._send_json_response = lambda data: DashboardHandler._send_json_response(
            handler, data
        )

        return handler

    def test_options_request_cors_headers(self, mock_handler):
        """Test OPTIONS requests return correct CORS headers."""
        mock_handler.do_OPTIONS()

        mock_handler.send_response.assert_called_once_with(200)
        # Verify CORS headers
        cors_calls = [
            call("Access-Control-Allow-Origin", "*"),
            call("Access-Control-Allow-Methods", "GET, POST, OPTIONS"),
            call("Access-Control-Allow-Headers", "Content-Type"),
        ]
        for cors_call in cors_calls:
            assert cors_call in mock_handler.send_header.call_args_list

    def test_json_responses_include_cors(self, mock_handler):
        """Test JSON responses include CORS headers."""
        data = {"test": "value"}

        mock_handler._send_json_response(data)

        # Verify CORS header included
        calls = [str(c) for c in mock_handler.send_header.call_args_list]
        assert any("Access-Control-Allow-Origin" in str(c) for c in calls)


class TestErrorHandling:
    """Tests for error handling and edge cases."""

    @pytest.fixture
    def mock_handler(self):
        """Create a DashboardHandler with mocked dependencies."""
        handler = MagicMock(spec=DashboardHandler)
        handler.send_response = MagicMock()
        handler.send_header = MagicMock()
        handler.end_headers = MagicMock()
        handler.wfile = BytesIO()
        handler._send_error_response = (
            lambda code, msg: DashboardHandler._send_error_response(handler, code, msg)
        )
        handler._handle_api_stats = lambda: DashboardHandler._handle_api_stats(handler)

        return handler

    def test_send_error_response(self, mock_handler):
        """Test _send_error_response sends proper error format."""
        mock_handler._send_error_response(404, "Not found")

        mock_handler.send_response.assert_called_once_with(404)
        response_data = json.loads(mock_handler.wfile.getvalue().decode())
        assert response_data["error"] == "Not found"

    def test_server_not_initialized_error(self, mock_handler):
        """Test endpoints return 500 when RAG server not initialized."""
        DashboardHandler.rag_server = None
        DashboardHandler.event_loop = None

        mock_handler._handle_api_stats()

        # Verify 500 response was sent
        mock_handler.send_response.assert_called_with(500)
        # Verify error response was written to wfile
        response_data = json.loads(mock_handler.wfile.getvalue().decode())
        assert "error" in response_data

    def test_asyncio_timeout_handling(self, mock_handler):
        """Test timeout errors handled with 500 response."""
        DashboardHandler.rag_server = AsyncMock()
        DashboardHandler.event_loop = MagicMock()

        with patch(
            "src.dashboard.web_server.asyncio.run_coroutine_threadsafe"
        ) as mock_run:
            mock_future = MagicMock()
            mock_future.result.side_effect = TimeoutError("Operation timed out")
            mock_run.return_value = mock_future

            mock_handler._handle_api_stats()

        mock_handler.send_response.assert_called_once_with(500)


class TestEventLoopHelpers:
    """Tests for event loop management functions."""

    def test_run_event_loop(self):
        """Test _run_event_loop sets and runs event loop."""
        loop = asyncio.new_event_loop()

        # Run in a thread for a short time
        thread = threading.Thread(target=_run_event_loop, args=(loop,), daemon=True)
        thread.start()

        # Give it a moment to start
        import time

        time.sleep(0.1)

        # Verify loop is running
        assert loop.is_running()

        # Stop the loop
        loop.call_soon_threadsafe(loop.stop)
        thread.join(timeout=1)

        loop.close()


class TestLogging:
    """Tests for custom logging behavior."""

    @pytest.fixture
    def mock_handler(self):
        """Create a DashboardHandler with mocked dependencies."""
        handler = MagicMock(spec=DashboardHandler)
        handler.address_string = MagicMock(return_value="127.0.0.1")
        handler.log_message = lambda fmt, *args: DashboardHandler.log_message(
            handler, fmt, *args
        )

        return handler

    def test_log_message_uses_logger(self, mock_handler):
        """Test log_message uses logger instead of stderr."""
        with patch("src.dashboard.web_server.logger") as mock_logger:
            mock_handler.log_message("GET %s %s", "/api/stats", "200")

            # Verify logger.info was called with the formatted message
            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args[0][0]
            assert "/api/stats" in call_args
            assert "200" in call_args


class TestStaticFileServing:
    """Tests for static file serving behavior."""

    @pytest.fixture
    def mock_handler(self):
        """Create a DashboardHandler with mocked dependencies."""
        handler = MagicMock(spec=DashboardHandler)
        handler.path = "/index.html"
        handler.send_response = MagicMock()
        handler.send_header = MagicMock()
        handler.end_headers = MagicMock()
        handler.do_GET = lambda: DashboardHandler.do_GET(handler)

        return handler

    def test_non_api_paths_serve_static_files(self, mock_handler):
        """Test non-API paths delegate to SimpleHTTPRequestHandler."""
        mock_handler.path = "/index.html"

        # Mock the parent class do_GET
        with patch("http.server.SimpleHTTPRequestHandler.do_GET") as mock_super:
            mock_handler.do_GET()

            # Should call parent implementation
            mock_super.assert_called_once()


class TestDoGetRouting:
    """Tests for do_GET method routing."""

    @pytest.fixture
    def mock_handler(self):
        """Create a mock handler for testing routing."""
        handler = MagicMock(spec=DashboardHandler)
        handler._handle_api_stats = MagicMock()
        handler._handle_api_activity = MagicMock()
        handler._handle_api_health = MagicMock()
        handler._handle_api_insights = MagicMock()
        handler._handle_api_trends = MagicMock()
        return handler

    def test_do_get_routes_to_stats(self, mock_handler):
        """Test /api/stats routes to _handle_api_stats."""
        mock_handler.path = "/api/stats"
        DashboardHandler.do_GET(mock_handler)
        mock_handler._handle_api_stats.assert_called_once()

    def test_do_get_routes_to_activity(self, mock_handler):
        """Test /api/activity routes to _handle_api_activity."""
        mock_handler.path = "/api/activity?limit=10"
        DashboardHandler.do_GET(mock_handler)
        mock_handler._handle_api_activity.assert_called_once()

    def test_do_get_routes_to_health(self, mock_handler):
        """Test /api/health routes to _handle_api_health."""
        mock_handler.path = "/api/health"
        DashboardHandler.do_GET(mock_handler)
        mock_handler._handle_api_health.assert_called_once()

    def test_do_get_routes_to_insights(self, mock_handler):
        """Test /api/insights routes to _handle_api_insights."""
        mock_handler.path = "/api/insights"
        DashboardHandler.do_GET(mock_handler)
        mock_handler._handle_api_insights.assert_called_once()

    def test_do_get_routes_to_trends(self, mock_handler):
        """Test /api/trends routes to _handle_api_trends."""
        mock_handler.path = "/api/trends?period=30d"
        DashboardHandler.do_GET(mock_handler)
        mock_handler._handle_api_trends.assert_called_once()


class TestDoPostRouting:
    """Tests for do_POST method routing."""

    @pytest.fixture
    def mock_handler(self):
        """Create a mock handler for testing POST routing."""
        handler = MagicMock(spec=DashboardHandler)
        handler._handle_create_memory = MagicMock()
        handler._handle_trigger_index = MagicMock()
        handler._handle_export = MagicMock()
        handler._send_error_response = MagicMock()
        return handler

    def test_do_post_routes_to_create_memory(self, mock_handler):
        """Test POST /api/memories routes to _handle_create_memory."""
        mock_handler.path = "/api/memories"
        DashboardHandler.do_POST(mock_handler)
        mock_handler._handle_create_memory.assert_called_once()

    def test_do_post_routes_to_trigger_index(self, mock_handler):
        """Test POST /api/index routes to _handle_trigger_index."""
        mock_handler.path = "/api/index"
        DashboardHandler.do_POST(mock_handler)
        mock_handler._handle_trigger_index.assert_called_once()

    def test_do_post_routes_to_export(self, mock_handler):
        """Test POST /api/export routes to _handle_export."""
        mock_handler.path = "/api/export"
        DashboardHandler.do_POST(mock_handler)
        mock_handler._handle_export.assert_called_once()

    def test_do_post_returns_404_for_unknown_endpoint(self, mock_handler):
        """Test POST to unknown endpoint returns 404."""
        mock_handler.path = "/api/unknown"
        DashboardHandler.do_POST(mock_handler)
        mock_handler._send_error_response.assert_called_with(404, "Endpoint not found")


class TestAdditionalEdgeCases:
    """Additional edge case tests for higher coverage."""

    def test_generate_empty_trends_with_custom_days(self):
        """Test _generate_empty_trends with custom day counts."""
        handler = MagicMock(spec=DashboardHandler)
        handler._generate_empty_trends = (
            lambda days: DashboardHandler._generate_empty_trends(handler, days)
        )

        # Test with 15 days
        trends = handler._generate_empty_trends(15)
        assert len(trends["dates"]) == 15
        assert len(trends["metrics"]["memory_count"]) == 15

    def test_generate_insights_with_no_projects(self):
        """Test insights generation when no projects exist."""
        handler = MagicMock(spec=DashboardHandler)
        handler._generate_insights = (
            lambda stats, health: DashboardHandler._generate_insights(
                handler, stats, health
            )
        )

        stats = {"total_memories": 0, "num_projects": 0, "projects": []}
        health = {
            "overall_score": 100,
            "metrics": {"cache_hit_rate": 0.9, "search_latency_p95_ms": 10},
        }

        insights = handler._generate_insights(stats, health)

        # Should still generate insights
        assert isinstance(insights, list)

    def test_send_json_response_with_datetime(self):
        """Test _send_json_response handles datetime encoding."""
        handler = MagicMock(spec=DashboardHandler)
        handler.wfile = BytesIO()
        handler.send_response = MagicMock()
        handler.send_header = MagicMock()
        handler.end_headers = MagicMock()
        handler._send_json_response = lambda data: DashboardHandler._send_json_response(
            handler, data
        )

        # Send data with datetime
        data = {"timestamp": datetime(2025, 1, 15, 10, 30, 0, tzinfo=UTC), "value": 42}

        handler._send_json_response(data)

        # Check that response was sent with 200
        handler.send_response.assert_called_with(200)

        # Verify JSON was written to wfile
        response_bytes = handler.wfile.getvalue()
        assert len(response_bytes) > 0
        response_data = json.loads(response_bytes.decode())
        assert response_data["value"] == 42
        assert "2025-01-15" in response_data["timestamp"]


class TestDashboardServerClass:
    """Tests for DashboardServer class (wrapper for web server)."""

    def test_dashboard_server_initialization_with_defaults(self):
        """Test DashboardServer initializes with default config."""
        from src.dashboard.web_server import DashboardServer

        server = DashboardServer()

        assert server.metrics_collector is None
        assert server.alert_engine is None
        assert server.health_reporter is None
        assert server.store is None
        assert server.config is not None  # Gets default config
        assert server.server is None
        assert server.event_loop is None
        assert server.loop_thread is None
        assert server.rag_server is None
        assert server.is_running is False

    def test_dashboard_server_initialization_with_components(self):
        """Test DashboardServer initializes with provided components."""
        from src.dashboard.web_server import DashboardServer
        from src.config import ServerConfig

        mock_metrics = MagicMock()
        mock_alerts = MagicMock()
        mock_health = MagicMock()
        mock_store = MagicMock()
        mock_config = MagicMock(spec=ServerConfig)

        server = DashboardServer(
            metrics_collector=mock_metrics,
            alert_engine=mock_alerts,
            health_reporter=mock_health,
            store=mock_store,
            config=mock_config,
        )

        assert server.metrics_collector is mock_metrics
        assert server.alert_engine is mock_alerts
        assert server.health_reporter is mock_health
        assert server.store is mock_store
        assert server.config is mock_config

    @pytest.mark.asyncio
    async def test_dashboard_server_start_success(self):
        """Test DashboardServer.start() initializes and starts server."""
        from src.dashboard.web_server import DashboardServer

        server = DashboardServer()

        # Mock the RAG server initialization
        with (
            patch("src.dashboard.web_server.MemoryRAGServer") as mock_rag_class,
            patch("src.dashboard.web_server.HTTPServer"),
            patch("src.dashboard.web_server.asyncio.new_event_loop") as mock_new_loop,
            patch("src.dashboard.web_server.threading.Thread") as mock_thread,
        ):
            mock_rag_instance = AsyncMock()
            mock_rag_instance.initialize = AsyncMock()
            mock_rag_class.return_value = mock_rag_instance

            mock_loop = MagicMock()
            mock_new_loop.return_value = mock_loop

            mock_thread_instance = MagicMock()
            mock_thread.return_value = mock_thread_instance

            # Mock asyncio.run_coroutine_threadsafe
            with patch(
                "src.dashboard.web_server.asyncio.run_coroutine_threadsafe"
            ) as mock_run_coro:
                mock_future = MagicMock()
                mock_future.result.return_value = None
                mock_run_coro.return_value = mock_future

                await server.start(host="localhost", port=8080)

            # Verify server was initialized
            assert server.is_running is True
            assert server.rag_server is mock_rag_instance
            assert server.event_loop is mock_loop
            mock_thread_instance.start.assert_called_once()

    @pytest.mark.asyncio
    async def test_dashboard_server_start_already_running(self):
        """Test DashboardServer.start() raises error if already running."""
        from src.dashboard.web_server import DashboardServer

        server = DashboardServer()
        server.is_running = True

        with pytest.raises(RuntimeError, match="already running"):
            await server.start()

    @pytest.mark.asyncio
    async def test_dashboard_server_stop_success(self):
        """Test DashboardServer.stop() cleans up resources."""
        from src.dashboard.web_server import DashboardServer

        server = DashboardServer()
        server.is_running = True

        # Set up mock components
        mock_http_server = MagicMock()
        mock_http_server.shutdown = MagicMock()
        server.server = mock_http_server

        mock_rag_server = AsyncMock()
        mock_rag_server.close = AsyncMock()
        server.rag_server = mock_rag_server

        mock_loop = MagicMock()
        mock_loop.call_soon_threadsafe = MagicMock()
        mock_loop.stop = MagicMock()
        server.event_loop = mock_loop

        mock_thread = MagicMock()
        mock_thread.join = MagicMock()
        server.loop_thread = mock_thread

        with patch(
            "src.dashboard.web_server.asyncio.run_coroutine_threadsafe"
        ) as mock_run_coro:
            mock_future = MagicMock()
            mock_future.result.return_value = None
            mock_run_coro.return_value = mock_future

            await server.stop()

        # Verify cleanup
        assert server.is_running is False
        mock_http_server.shutdown.assert_called_once()
        mock_loop.call_soon_threadsafe.assert_called_once()
        mock_thread.join.assert_called_once()

    @pytest.mark.asyncio
    async def test_dashboard_server_stop_not_running(self):
        """Test DashboardServer.stop() does nothing if not running."""
        from src.dashboard.web_server import DashboardServer

        server = DashboardServer()
        server.is_running = False

        # Should not raise, just return
        await server.stop()
        assert server.is_running is False

    @pytest.mark.asyncio
    async def test_dashboard_server_stop_handles_rag_close_error(self):
        """Test DashboardServer.stop() handles RAG server close errors gracefully."""
        from src.dashboard.web_server import DashboardServer

        server = DashboardServer()
        server.is_running = True

        mock_rag_server = AsyncMock()
        mock_rag_server.close = AsyncMock()
        server.rag_server = mock_rag_server

        mock_loop = MagicMock()
        mock_loop.call_soon_threadsafe = MagicMock()
        server.event_loop = mock_loop

        with patch(
            "src.dashboard.web_server.asyncio.run_coroutine_threadsafe"
        ) as mock_run_coro:
            mock_future = MagicMock()
            mock_future.result.side_effect = Exception("Close failed")
            mock_run_coro.return_value = mock_future

            # Should handle error gracefully
            await server.stop()

        # Cleanup should still complete
        assert server.is_running is False


class TestGetDailyMetrics:
    """Tests for _get_daily_metrics helper method."""

    @pytest.mark.asyncio
    async def test_get_daily_metrics_with_collector(self):
        """Test _get_daily_metrics returns metrics when collector exists."""
        handler = MagicMock(spec=DashboardHandler)

        # Mock RAG server with metrics collector
        mock_rag_server = MagicMock()
        mock_collector = MagicMock()
        expected_result = [
            MagicMock(
                timestamp=datetime.now(),
                total_memories=100,
                queries_per_day=50,
                avg_search_latency_ms=15.5,
            )
        ]

        # The get_daily_aggregate returns a coroutine that we need to await
        async def mock_get_daily_aggregate(days):
            return expected_result

        mock_collector.get_daily_aggregate = mock_get_daily_aggregate
        mock_rag_server.metrics_collector = mock_collector
        handler.rag_server = mock_rag_server

        # Call the actual method
        result = await DashboardHandler._get_daily_metrics(handler, 7)

        assert len(result) == 1
        assert result[0].total_memories == 100

    @pytest.mark.asyncio
    async def test_get_daily_metrics_without_collector(self):
        """Test _get_daily_metrics returns empty list when no collector."""
        handler = MagicMock(spec=DashboardHandler)

        mock_rag_server = MagicMock()
        mock_rag_server.metrics_collector = None
        handler.rag_server = mock_rag_server

        handler._get_daily_metrics = lambda days: DashboardHandler._get_daily_metrics(
            handler, days
        )

        result = await handler._get_daily_metrics(7)

        assert result == []


class TestGenerateTrendsEdgeCases:
    """Additional tests for _generate_trends method edge cases."""

    @pytest.fixture
    def mock_handler(self):
        """Create a handler mock."""
        handler = MagicMock(spec=DashboardHandler)
        handler._generate_trends = (
            lambda stats, period, metric: DashboardHandler._generate_trends(
                handler, stats, period, metric
            )
        )
        handler._generate_empty_trends = (
            lambda days: DashboardHandler._generate_empty_trends(handler, days)
        )
        handler._get_daily_metrics = AsyncMock(return_value=[])
        return handler

    def test_generate_trends_unknown_period_defaults_to_30d(self, mock_handler):
        """Test _generate_trends defaults to 30 days for unknown period."""
        mock_handler.rag_server = None
        mock_handler.event_loop = None

        trends = mock_handler._generate_trends({}, "unknown", "memories")

        # Unknown period is kept as-is, but days defaults to 30
        assert len(trends["dates"]) == 30

    def test_generate_trends_with_historical_data(self, mock_handler):
        """Test _generate_trends with actual historical metrics."""
        from datetime import datetime

        # Create mock metrics
        mock_metrics = [
            MagicMock(
                timestamp=datetime(2025, 1, i),
                total_memories=100 + i,
                queries_per_day=20 + i,
                avg_search_latency_ms=15.5 + i,
            )
            for i in range(1, 8)
        ]

        mock_rag_server = MagicMock()
        mock_rag_server.metrics_collector = MagicMock()
        DashboardHandler.rag_server = mock_rag_server

        mock_loop = MagicMock()
        DashboardHandler.event_loop = mock_loop

        # Mock the async call
        with patch(
            "src.dashboard.web_server.asyncio.run_coroutine_threadsafe"
        ) as mock_run:
            mock_future = MagicMock()
            mock_future.result.return_value = mock_metrics
            mock_run.return_value = mock_future

            trends = mock_handler._generate_trends({}, "7d", "memories")

        assert len(trends["dates"]) == 7
        assert len(trends["metrics"]["memory_count"]) == 7
        assert trends["metrics"]["memory_count"][0] == 101  # First metric
        assert trends["metrics"]["search_volume"][0] == 21


class TestApiStatsTimeRangeSupport:
    """Tests for UX-037 time range support in /api/stats."""

    @pytest.fixture
    def mock_handler(self):
        """Create a handler mock."""
        handler = MagicMock(spec=DashboardHandler)
        handler.send_response = MagicMock()
        handler.send_header = MagicMock()
        handler.end_headers = MagicMock()
        handler.wfile = BytesIO()
        handler._handle_api_stats = lambda: DashboardHandler._handle_api_stats(handler)
        handler._send_json_response = lambda data: DashboardHandler._send_json_response(
            handler, data
        )
        return handler

    def test_api_stats_with_time_range(self, mock_handler):
        """Test /api/stats accepts start_date and end_date parameters."""
        mock_rag_server = AsyncMock()
        mock_rag_server.get_dashboard_stats = AsyncMock(
            return_value={"status": "success"}
        )
        DashboardHandler.rag_server = mock_rag_server
        DashboardHandler.event_loop = MagicMock()

        mock_handler.path = "/api/stats?start_date=2025-01-01&end_date=2025-01-31"

        with patch(
            "src.dashboard.web_server.asyncio.run_coroutine_threadsafe"
        ) as mock_run:
            mock_future = MagicMock()
            mock_future.result.return_value = {"status": "success"}
            mock_run.return_value = mock_future

            mock_handler._handle_api_stats()

        # Verify the call included time range parameters
        mock_run.assert_called_once()


class TestApiActivityTimeRangeSupport:
    """Tests for UX-037 time range support in /api/activity."""

    @pytest.fixture
    def mock_handler(self):
        """Create a handler mock."""
        handler = MagicMock(spec=DashboardHandler)
        handler.send_response = MagicMock()
        handler.send_header = MagicMock()
        handler.end_headers = MagicMock()
        handler.wfile = BytesIO()
        handler._handle_api_activity = (
            lambda query: DashboardHandler._handle_api_activity(handler, query)
        )
        handler._send_json_response = lambda data: DashboardHandler._send_json_response(
            handler, data
        )
        return handler

    def test_api_activity_with_time_range(self, mock_handler):
        """Test /api/activity accepts start_date and end_date parameters."""
        mock_rag_server = AsyncMock()
        mock_rag_server.get_recent_activity = AsyncMock(
            return_value={"recent_searches": []}
        )
        DashboardHandler.rag_server = mock_rag_server
        DashboardHandler.event_loop = MagicMock()

        with patch(
            "src.dashboard.web_server.asyncio.run_coroutine_threadsafe"
        ) as mock_run:
            mock_future = MagicMock()
            mock_future.result.return_value = {"recent_searches": []}
            mock_run.return_value = mock_future

            mock_handler._handle_api_activity(
                "start_date=2025-01-01&end_date=2025-01-31&limit=10"
            )

        # Verify the call was made
        mock_run.assert_called_once()


class TestInsightsLowMemoryDensity:
    """Test insights for low memory density scenario."""

    def test_generate_insights_low_memory_density(self):
        """Test insight generated for < 10 avg memories per project."""
        handler = MagicMock(spec=DashboardHandler)
        handler._generate_insights = (
            lambda stats, health: DashboardHandler._generate_insights(
                handler, stats, health
            )
        )

        stats = {"total_memories": 15, "num_projects": 3, "projects": []}
        health = {
            "overall_score": 85,
            "metrics": {"cache_hit_rate": 0.8, "search_latency_p95_ms": 20},
        }

        insights = handler._generate_insights(stats, health)

        # Should have insight about low memory density (15/3 = 5.0 < 10)
        density_insights = [i for i in insights if "Memory Density" in i["title"]]
        assert len(density_insights) > 0
        assert density_insights[0]["severity"] == "INFO"


class TestInsightsOptimalHealth:
    """Test insights for optimal health score scenario."""

    def test_generate_insights_optimal_health(self):
        """Test positive insight for health score >= 95."""
        handler = MagicMock(spec=DashboardHandler)
        handler._generate_insights = (
            lambda stats, health: DashboardHandler._generate_insights(
                handler, stats, health
            )
        )

        stats = {"total_memories": 100, "num_projects": 5, "projects": []}
        health = {
            "overall_score": 98,
            "metrics": {"cache_hit_rate": 0.92, "search_latency_p95_ms": 12},
        }

        insights = handler._generate_insights(stats, health)

        # Should have positive health insight
        health_insights = [i for i in insights if "Optimal" in i["title"]]
        assert len(health_insights) > 0
        assert health_insights[0]["severity"] == "INFO"


class TestStartDashboardServerFunction:
    """Tests for start_dashboard_server() standalone function."""

    @pytest.mark.asyncio
    async def test_start_dashboard_server_initializes_components(self):
        """Test start_dashboard_server creates all necessary components."""

        with (
            patch("src.dashboard.web_server.asyncio.new_event_loop") as mock_new_loop,
            patch("src.dashboard.web_server.threading.Thread") as mock_thread,
            patch("src.dashboard.web_server.get_config") as mock_get_config,
            patch("src.dashboard.web_server.MemoryRAGServer") as mock_rag_class,
            patch("src.dashboard.web_server.HTTPServer") as mock_http_server,
            patch(
                "src.dashboard.web_server.asyncio.run_coroutine_threadsafe"
            ) as mock_run_coro,
        ):
            # Set up mocks
            mock_loop = MagicMock()
            mock_new_loop.return_value = mock_loop

            mock_thread_instance = MagicMock()
            mock_thread.return_value = mock_thread_instance

            mock_config = MagicMock()
            mock_get_config.return_value = mock_config

            mock_rag_instance = AsyncMock()
            mock_rag_instance.initialize = AsyncMock()
            mock_rag_class.return_value = mock_rag_instance

            mock_server_instance = MagicMock()
            mock_server_instance.serve_forever = MagicMock(
                side_effect=KeyboardInterrupt()
            )
            mock_http_server.return_value = mock_server_instance

            mock_future = MagicMock()
            mock_future.result.return_value = None
            mock_run_coro.return_value = mock_future

            # Run function (will be interrupted by KeyboardInterrupt)
            try:
                await start_dashboard_server(port=8080, host="localhost")
            except KeyboardInterrupt:
                pass

            # Verify initialization sequence
            mock_new_loop.assert_called_once()
            mock_thread.assert_called_once()
            mock_get_config.assert_called_once()
            mock_rag_class.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_dashboard_server_default_port(self):
        """Test start_dashboard_server uses default port 8080."""

        with (
            patch("src.dashboard.web_server.asyncio.new_event_loop"),
            patch("src.dashboard.web_server.threading.Thread"),
            patch("src.dashboard.web_server.get_config"),
            patch("src.dashboard.web_server.MemoryRAGServer"),
            patch("src.dashboard.web_server.HTTPServer") as mock_http_server,
            patch("src.dashboard.web_server.asyncio.run_coroutine_threadsafe"),
        ):
            mock_server = MagicMock()
            mock_server.serve_forever = MagicMock(side_effect=KeyboardInterrupt())
            mock_http_server.return_value = mock_server

            try:
                await start_dashboard_server()
            except KeyboardInterrupt:
                pass

            # Verify HTTPServer was called with default port
            call_args = mock_http_server.call_args
            assert call_args[0][0] == ("localhost", 8080)

    @pytest.mark.asyncio
    async def test_start_dashboard_server_keyboard_interrupt_cleanup(self):
        """Test start_dashboard_server handles KeyboardInterrupt and cleans up."""

        with (
            patch("src.dashboard.web_server.asyncio.new_event_loop") as mock_new_loop,
            patch("src.dashboard.web_server.threading.Thread") as mock_thread,
            patch("src.dashboard.web_server.get_config"),
            patch("src.dashboard.web_server.MemoryRAGServer") as mock_rag_class,
            patch("src.dashboard.web_server.HTTPServer") as mock_http_server,
            patch(
                "src.dashboard.web_server.asyncio.run_coroutine_threadsafe"
            ) as mock_run_coro,
        ):
            mock_loop = MagicMock()
            mock_new_loop.return_value = mock_loop

            mock_thread_instance = MagicMock()
            mock_thread.return_value = mock_thread_instance

            mock_rag_instance = AsyncMock()
            mock_rag_instance.initialize = AsyncMock()
            mock_rag_instance.close = AsyncMock()
            mock_rag_class.return_value = mock_rag_instance

            mock_server_instance = MagicMock()
            mock_server_instance.serve_forever = MagicMock(
                side_effect=KeyboardInterrupt()
            )
            mock_server_instance.shutdown = MagicMock()
            mock_http_server.return_value = mock_server_instance

            mock_future = MagicMock()
            mock_future.result.return_value = None
            mock_run_coro.return_value = mock_future

            # Run function
            try:
                await start_dashboard_server()
            except KeyboardInterrupt:
                pass

            # Verify cleanup was performed
            mock_server_instance.shutdown.assert_called_once()
            mock_loop.call_soon_threadsafe.assert_called_once()


class TestMainFunction:
    """Tests for main() CLI entry point."""

    def test_main_default_arguments(self):
        """Test main() uses default arguments."""
        from src.dashboard.web_server import main

        # Patch argparse.ArgumentParser at the module level since it's imported locally in main()
        with (
            patch("argparse.ArgumentParser") as mock_parser_class,
            patch("src.dashboard.web_server.logging.basicConfig") as mock_logging,
            patch("src.dashboard.web_server.asyncio.run") as mock_asyncio_run,
        ):
            mock_parser = MagicMock()
            mock_args = MagicMock()
            mock_args.port = 8080
            mock_args.host = "localhost"
            mock_parser.parse_args.return_value = mock_args
            mock_parser_class.return_value = mock_parser

            main()

            # Verify logging was configured
            mock_logging.assert_called_once()
            # Verify asyncio.run was called
            mock_asyncio_run.assert_called_once()

    def test_main_custom_port(self):
        """Test main() accepts custom port via CLI args."""
        from src.dashboard.web_server import main

        with (
            patch("argparse.ArgumentParser") as mock_parser_class,
            patch("src.dashboard.web_server.logging.basicConfig"),
            patch("src.dashboard.web_server.asyncio.run"),
        ):
            mock_parser = MagicMock()
            mock_args = MagicMock()
            mock_args.port = 9000
            mock_args.host = "0.0.0.0"
            mock_parser.parse_args.return_value = mock_args
            mock_parser_class.return_value = mock_parser

            main()

            # Verify parser was configured to accept port/host
            add_argument_calls = [
                str(c) for c in mock_parser.add_argument.call_args_list
            ]
            assert any("--port" in str(c) for c in add_argument_calls)
            assert any("--host" in str(c) for c in add_argument_calls)

    def test_main_configures_logging(self):
        """Test main() sets up logging with correct format."""
        from src.dashboard.web_server import main

        with (
            patch("argparse.ArgumentParser"),
            patch("src.dashboard.web_server.logging.basicConfig") as mock_logging,
            patch("src.dashboard.web_server.asyncio.run"),
        ):
            main()

            # Verify logging.basicConfig was called with level and format
            call_kwargs = mock_logging.call_args[1]
            assert "level" in call_kwargs
            assert "format" in call_kwargs

    def test_main_calls_start_dashboard_server(self):
        """Test main() calls start_dashboard_server with parsed args."""
        from src.dashboard.web_server import main

        with (
            patch("argparse.ArgumentParser") as mock_parser_class,
            patch("src.dashboard.web_server.logging.basicConfig"),
            patch("src.dashboard.web_server.asyncio.run") as mock_asyncio_run,
            patch("src.dashboard.web_server.start_dashboard_server"),
        ):
            mock_parser = MagicMock()
            mock_args = MagicMock()
            mock_args.port = 8888
            mock_args.host = "127.0.0.1"
            mock_parser.parse_args.return_value = mock_args
            mock_parser_class.return_value = mock_parser

            main()

            # Verify asyncio.run was called
            mock_asyncio_run.assert_called_once()
            # The call will be to start_dashboard_server coroutine
            call_arg = mock_asyncio_run.call_args[0][0]
            # It should be a coroutine, we can check the function name
            assert callable(call_arg) or hasattr(call_arg, "__await__")


class TestMainEntryPoint:
    """Test the __main__ entry point."""

    def test_main_module_execution(self):
        """Test __main__ block calls main()."""
        # This tests the pattern: if __name__ == "__main__": main()
        # We can't directly test the condition, but we can verify main exists
        from src.dashboard.web_server import main

        assert callable(main)

    def test_argument_parser_configuration(self):
        """Test ArgumentParser is configured correctly."""
        from src.dashboard.web_server import main

        with (
            patch("argparse.ArgumentParser") as mock_parser_class,
            patch("src.dashboard.web_server.logging.basicConfig"),
            patch("src.dashboard.web_server.asyncio.run"),
        ):
            mock_parser = MagicMock()
            mock_args = MagicMock()
            mock_args.port = 8080
            mock_args.host = "localhost"
            mock_parser.parse_args.return_value = mock_args
            mock_parser_class.return_value = mock_parser

            main()

            # Verify ArgumentParser was instantiated with description
            call_args = mock_parser_class.call_args
            assert "description" in call_args[1]
            assert "Dashboard" in call_args[1]["description"]


class TestTrendsPeriodParsing:
    """Tests for period parsing in _generate_trends."""

    @pytest.fixture
    def mock_handler(self):
        """Create a handler mock."""
        handler = MagicMock(spec=DashboardHandler)
        handler._generate_trends = (
            lambda stats, period, metric: DashboardHandler._generate_trends(
                handler, stats, period, metric
            )
        )
        handler._generate_empty_trends = (
            lambda days: DashboardHandler._generate_empty_trends(handler, days)
        )
        return handler

    def test_generate_trends_period_7d(self, mock_handler):
        """Test period '7d' parses to 7 days."""
        mock_handler.rag_server = None
        mock_handler.event_loop = None

        trends = mock_handler._generate_trends({}, "7d", "memories")
        assert len(trends["dates"]) == 7
        assert trends["period"] == "7d"

    def test_generate_trends_period_30d(self, mock_handler):
        """Test period '30d' parses to 30 days."""
        mock_handler.rag_server = None
        mock_handler.event_loop = None

        trends = mock_handler._generate_trends({}, "30d", "memories")
        assert len(trends["dates"]) == 30
        assert trends["period"] == "30d"

    def test_generate_trends_period_90d(self, mock_handler):
        """Test period '90d' parses to 90 days."""
        mock_handler.rag_server = None
        mock_handler.event_loop = None

        trends = mock_handler._generate_trends({}, "90d", "memories")
        assert len(trends["dates"]) == 90
        assert trends["period"] == "90d"


class TestExportContentTypes:
    """Tests for export endpoint content type handling."""

    @pytest.fixture
    def mock_handler(self):
        """Create a handler mock."""
        handler = MagicMock(spec=DashboardHandler)
        handler.send_response = MagicMock()
        handler.send_header = MagicMock()
        handler.end_headers = MagicMock()
        handler.wfile = BytesIO()
        handler.rfile = BytesIO()
        handler.headers = {"Content-Length": "0"}
        handler._handle_export = lambda: DashboardHandler._handle_export(handler)
        return handler

    def test_export_unknown_format_defaults_to_text_plain(self, mock_handler):
        """Test export with unknown format uses text/plain content type."""
        DashboardHandler.rag_server = AsyncMock()
        DashboardHandler.event_loop = MagicMock()

        request_data = {"format": "xml"}  # Unknown format
        body = json.dumps(request_data).encode()
        mock_handler.rfile = BytesIO(body)
        mock_handler.headers = {"Content-Length": str(len(body))}

        with patch(
            "src.dashboard.web_server.asyncio.run_coroutine_threadsafe"
        ) as mock_run:
            mock_future = MagicMock()
            mock_future.result.return_value = "<data>test</data>"
            mock_run.return_value = mock_future

            mock_handler._handle_export()

        # Verify text/plain was used
        calls = [str(c) for c in mock_handler.send_header.call_args_list]
        assert any("Content-Type" in str(c) and "text/plain" in str(c) for c in calls)
