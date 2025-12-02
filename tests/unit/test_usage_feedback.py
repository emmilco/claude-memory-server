"""Tests for usage feedback mechanisms (UX-024)."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from src.core.server import MemoryRAGServer
from src.core.exceptions import StorageError


@pytest.fixture
def mock_server():
    """Create a mock server for testing."""
    server = MagicMock(spec=MemoryRAGServer)
    server.config = MagicMock()
    server.config.advanced.read_only_mode = False
    server.store = AsyncMock()
    server.stats = {}
    return server


class TestSubmitSearchFeedback:
    """Test submit_search_feedback MCP tool."""

    @pytest.mark.asyncio
    async def test_submit_helpful_feedback(self, mock_server):
        """Test submitting helpful feedback."""
        from src.core.server import MemoryRAGServer

        # Setup
        mock_server.store.submit_search_feedback.return_value = "feedback-123"

        # Create real instance with mocked store
        server = MemoryRAGServer.__new__(MemoryRAGServer)
        server.config = mock_server.config
        server.store = mock_server.store
        server.stats = mock_server.stats

        # Execute
        result = await server.submit_search_feedback(
            search_id="search-1",
            query="python async functions",
            result_ids=["mem-1", "mem-2", "mem-3"],
            rating="helpful",
        )

        # Verify
        assert result["status"] == "success"
        assert result["feedback_id"] == "feedback-123"
        assert result["search_id"] == "search-1"
        assert result["rating"] == "helpful"

        mock_server.store.submit_search_feedback.assert_called_once_with(
            search_id="search-1",
            query="python async functions",
            result_ids=["mem-1", "mem-2", "mem-3"],
            rating="helpful",
            comment=None,
            project_name=None,
        )

    @pytest.mark.asyncio
    async def test_submit_not_helpful_feedback(self, mock_server):
        """Test submitting not helpful feedback."""
        from src.core.server import MemoryRAGServer

        # Setup
        mock_server.store.submit_search_feedback.return_value = "feedback-456"

        # Create real instance with mocked store
        server = MemoryRAGServer.__new__(MemoryRAGServer)
        server.config = mock_server.config
        server.store = mock_server.store
        server.stats = mock_server.stats

        # Execute
        result = await server.submit_search_feedback(
            search_id="search-2",
            query="database optimization",
            result_ids=[],
            rating="not_helpful",
            comment="Results not relevant",
        )

        # Verify
        assert result["status"] == "success"
        assert result["rating"] == "not_helpful"

    @pytest.mark.asyncio
    async def test_submit_feedback_with_project_context(self, mock_server):
        """Test submitting feedback with project context."""
        from src.core.server import MemoryRAGServer

        # Setup
        mock_server.store.submit_search_feedback.return_value = "feedback-789"

        # Create real instance with mocked store
        server = MemoryRAGServer.__new__(MemoryRAGServer)
        server.config = mock_server.config
        server.store = mock_server.store
        server.stats = mock_server.stats

        # Execute
        result = await server.submit_search_feedback(
            search_id="search-3",
            query="authentication flow",
            result_ids=["mem-5"],
            rating="helpful",
            comment="Very useful!",
            project_name="my-app",
        )

        # Verify
        assert result["status"] == "success"
        mock_server.store.submit_search_feedback.assert_called_once()
        call_kwargs = mock_server.store.submit_search_feedback.call_args[1]
        assert call_kwargs["project_name"] == "my-app"
        assert call_kwargs["comment"] == "Very useful!"

    @pytest.mark.asyncio
    async def test_submit_feedback_storage_error(self, mock_server):
        """Test handling of storage errors during feedback submission."""
        from src.core.server import MemoryRAGServer

        # Setup
        mock_server.store.submit_search_feedback.side_effect = Exception("DB error")

        # Create real instance with mocked store
        server = MemoryRAGServer.__new__(MemoryRAGServer)
        server.config = mock_server.config
        server.store = mock_server.store
        server.stats = mock_server.stats

        # Execute & Verify
        with pytest.raises(StorageError):
            await server.submit_search_feedback(
                search_id="search-error", query="test", result_ids=[], rating="helpful"
            )


class TestGetQualityMetrics:
    """Test get_quality_metrics MCP tool."""

    @pytest.mark.asyncio
    async def test_get_metrics_default_time_range(self, mock_server):
        """Test getting quality metrics with default time range."""
        from src.core.server import MemoryRAGServer

        # Setup
        mock_metrics = {
            "time_range_hours": 24,
            "window_start": "2025-11-17T00:00:00Z",
            "window_end": "2025-11-18T00:00:00Z",
            "total_searches": 100,
            "helpful_count": 75,
            "not_helpful_count": 25,
            "helpfulness_rate": 0.75,
            "project_name": None,
        }
        mock_server.store.get_quality_metrics.return_value = mock_metrics

        # Create real instance with mocked store
        server = MemoryRAGServer.__new__(MemoryRAGServer)
        server.config = mock_server.config
        server.store = mock_server.store
        server.stats = mock_server.stats

        # Execute
        result = await server.get_quality_metrics()

        # Verify
        assert result["status"] == "success"
        assert result["metrics"]["total_searches"] == 100
        assert result["metrics"]["helpful_count"] == 75
        assert result["metrics"]["helpfulness_rate"] == 0.75

        mock_server.store.get_quality_metrics.assert_called_once_with(
            time_range_hours=24,
            project_name=None,
        )

    @pytest.mark.asyncio
    async def test_get_metrics_custom_time_range(self, mock_server):
        """Test getting quality metrics with custom time range."""
        from src.core.server import MemoryRAGServer

        # Setup
        mock_metrics = {
            "time_range_hours": 168,  # 1 week
            "window_start": "2025-11-11T00:00:00Z",
            "window_end": "2025-11-18T00:00:00Z",
            "total_searches": 500,
            "helpful_count": 400,
            "not_helpful_count": 100,
            "helpfulness_rate": 0.80,
            "project_name": None,
        }
        mock_server.store.get_quality_metrics.return_value = mock_metrics

        # Create real instance with mocked store
        server = MemoryRAGServer.__new__(MemoryRAGServer)
        server.config = mock_server.config
        server.store = mock_server.store
        server.stats = mock_server.stats

        # Execute
        result = await server.get_quality_metrics(time_range_hours=168)

        # Verify
        assert result["metrics"]["time_range_hours"] == 168
        assert result["metrics"]["total_searches"] == 500
        assert result["metrics"]["helpfulness_rate"] == 0.80

    @pytest.mark.asyncio
    async def test_get_metrics_with_project_filter(self, mock_server):
        """Test getting quality metrics filtered by project."""
        from src.core.server import MemoryRAGServer

        # Setup
        mock_metrics = {
            "time_range_hours": 24,
            "window_start": "2025-11-17T00:00:00Z",
            "window_end": "2025-11-18T00:00:00Z",
            "total_searches": 50,
            "helpful_count": 45,
            "not_helpful_count": 5,
            "helpfulness_rate": 0.90,
            "project_name": "my-project",
        }
        mock_server.store.get_quality_metrics.return_value = mock_metrics

        # Create real instance with mocked store
        server = MemoryRAGServer.__new__(MemoryRAGServer)
        server.config = mock_server.config
        server.store = mock_server.store
        server.stats = mock_server.stats

        # Execute
        result = await server.get_quality_metrics(
            time_range_hours=24, project_name="my-project"
        )

        # Verify
        assert result["metrics"]["project_name"] == "my-project"
        assert result["metrics"]["total_searches"] == 50

    @pytest.mark.asyncio
    async def test_get_metrics_no_feedback(self, mock_server):
        """Test getting metrics when no feedback exists."""
        from src.core.server import MemoryRAGServer

        # Setup
        mock_metrics = {
            "time_range_hours": 24,
            "window_start": "2025-11-17T00:00:00Z",
            "window_end": "2025-11-18T00:00:00Z",
            "total_searches": 0,
            "helpful_count": 0,
            "not_helpful_count": 0,
            "helpfulness_rate": 0.0,
            "project_name": None,
        }
        mock_server.store.get_quality_metrics.return_value = mock_metrics

        # Create real instance with mocked store
        server = MemoryRAGServer.__new__(MemoryRAGServer)
        server.config = mock_server.config
        server.store = mock_server.store
        server.stats = mock_server.stats

        # Execute
        result = await server.get_quality_metrics()

        # Verify
        assert result["metrics"]["total_searches"] == 0
        assert result["metrics"]["helpfulness_rate"] == 0.0

    @pytest.mark.asyncio
    async def test_get_metrics_storage_error(self, mock_server):
        """Test handling of storage errors during metrics retrieval."""
        from src.core.server import MemoryRAGServer

        # Setup
        mock_server.store.get_quality_metrics.side_effect = Exception("DB error")

        # Create real instance with mocked store
        server = MemoryRAGServer.__new__(MemoryRAGServer)
        server.config = mock_server.config
        server.store = mock_server.store
        server.stats = mock_server.stats

        # Execute & Verify
        with pytest.raises(StorageError):
            await server.get_quality_metrics()


class TestFeedbackIntegration:
    """Integration tests for feedback workflow."""

    @pytest.mark.asyncio
    async def test_feedback_workflow(self, mock_server):
        """Test complete feedback workflow: submit → retrieve metrics."""
        from src.core.server import MemoryRAGServer

        # Setup
        mock_server.store.submit_search_feedback.return_value = "feedback-1"
        mock_metrics = {
            "time_range_hours": 24,
            "total_searches": 1,
            "helpful_count": 1,
            "not_helpful_count": 0,
            "helpfulness_rate": 1.0,
        }
        mock_server.store.get_quality_metrics.return_value = mock_metrics

        # Create real instance with mocked store
        server = MemoryRAGServer.__new__(MemoryRAGServer)
        server.config = mock_server.config
        server.store = mock_server.store
        server.stats = mock_server.stats

        # Submit feedback
        feedback_result = await server.submit_search_feedback(
            search_id="search-1",
            query="test query",
            result_ids=["mem-1"],
            rating="helpful",
        )
        assert feedback_result["status"] == "success"

        # Get metrics
        metrics_result = await server.get_quality_metrics()
        assert metrics_result["status"] == "success"
        assert metrics_result["metrics"]["helpful_count"] == 1
        assert metrics_result["metrics"]["helpfulness_rate"] == 1.0
