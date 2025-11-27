"""Tests for dashboard API endpoints (UX-026 Phase 1)."""

import pytest
from datetime import datetime, UTC
from unittest.mock import AsyncMock, MagicMock, patch
from src.core.server import MemoryRAGServer
from src.core.exceptions import StorageError


@pytest.fixture
def mock_server():
    """Create a mock MemoryRAGServer for testing."""
    with patch("src.core.server.create_memory_store"), \
         patch("src.core.server.EmbeddingGenerator"), \
         patch("src.core.server.EmbeddingCache"):

        server = MemoryRAGServer()
        server.store = AsyncMock()
        return server


class TestGetDashboardStats:
    """Tests for get_dashboard_stats endpoint."""

    @pytest.mark.asyncio
    async def test_get_dashboard_stats_success(self, mock_server):
        """Test successful retrieval of dashboard stats."""
        # Mock store responses
        mock_server.store.count = AsyncMock(return_value=150)
        mock_server.store.get_all_projects = AsyncMock(
            return_value=["project1", "project2"]
        )
        mock_server.store.get_project_stats = AsyncMock(side_effect=[
            {
                "project_name": "project1",
                "total_memories": 80,
                "categories": {"code": 50, "documentation": 30},
                "lifecycle_states": {"ACTIVE": 70, "ARCHIVED": 10},
            },
            {
                "project_name": "project2",
                "total_memories": 60,
                "categories": {"code": 40, "documentation": 20},
                "lifecycle_states": {"ACTIVE": 55, "ARCHIVED": 5},
            },
        ])

        # Mock Qdrant client for global count
        mock_count_result = MagicMock()
        mock_count_result.count = 10
        # Create a proper mock for the client.count method
        mock_server.store.client = MagicMock()
        mock_server.store.client.count = AsyncMock(return_value=mock_count_result)
        mock_server.store.collection_name = "test_collection"

        # Patch Qdrant imports to prevent import errors
        with patch("qdrant_client.models.Filter"), \
             patch("qdrant_client.models.FieldCondition"), \
             patch("qdrant_client.models.IsNullCondition"):
            result = await mock_server.get_dashboard_stats()

        assert result["status"] == "success"
        assert result["total_memories"] == 150
        assert result["num_projects"] == 2
        assert result["global_memories"] == 10
        assert len(result["projects"]) == 2
        assert result["categories"]["code"] == 90  # 50 + 40
        assert result["categories"]["documentation"] == 50  # 30 + 20
        assert result["lifecycle_states"]["ACTIVE"] == 125  # 70 + 55
        assert result["lifecycle_states"]["ARCHIVED"] == 15  # 10 + 5

    @pytest.mark.asyncio
    async def test_get_dashboard_stats_no_projects(self, mock_server):
        """Test dashboard stats with no projects."""
        mock_server.store.count = AsyncMock(return_value=25)
        mock_server.store.get_all_projects = AsyncMock(return_value=[])

        # Mock Qdrant client for global count
        mock_count_result = MagicMock()
        mock_count_result.count = 25
        # Create a proper mock for the client.count method
        mock_server.store.client = MagicMock()
        mock_server.store.client.count = AsyncMock(return_value=mock_count_result)
        mock_server.store.collection_name = "test_collection"

        # Patch Qdrant imports to prevent import errors
        with patch("qdrant_client.models.Filter"), \
             patch("qdrant_client.models.FieldCondition"), \
             patch("qdrant_client.models.IsNullCondition"):
            result = await mock_server.get_dashboard_stats()

        assert result["status"] == "success"
        assert result["total_memories"] == 25
        assert result["num_projects"] == 0
        assert result["global_memories"] == 25
        assert result["projects"] == []
        assert result["categories"] == {}
        assert result["lifecycle_states"] == {}

    @pytest.mark.asyncio
    async def test_get_dashboard_stats_project_failure_continues(self, mock_server):
        """Test that stats continue if one project fails."""
        mock_server.store.count = AsyncMock(return_value=100)
        mock_server.store.get_all_projects = AsyncMock(
            return_value=["project1", "project2", "project3"]
        )
        mock_server.store.get_project_stats = AsyncMock(side_effect=[
            {
                "project_name": "project1",
                "total_memories": 50,
                "categories": {"code": 40},
                "lifecycle_states": {"ACTIVE": 50},
            },
            StorageError("Project 2 failed"),  # Fail on project2
            {
                "project_name": "project3",
                "total_memories": 40,
                "categories": {"code": 30},
                "lifecycle_states": {"ACTIVE": 40},
            },
        ])

        # Mock SQLite conn for global count
        mock_server.store.conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (10,)
        mock_server.store.conn.execute.return_value = mock_cursor

        result = await mock_server.get_dashboard_stats()

        assert result["status"] == "success"
        assert result["total_memories"] == 100
        assert result["num_projects"] == 3
        # Only 2 projects should have stats (project2 failed)
        assert len(result["projects"]) == 2
        assert result["categories"]["code"] == 70  # 40 + 30
        assert result["lifecycle_states"]["ACTIVE"] == 90  # 50 + 40

    @pytest.mark.asyncio
    async def test_get_dashboard_stats_qdrant_backend(self, mock_server):
        """Test dashboard stats with Qdrant backend (no conn attribute)."""
        mock_server.store.count = AsyncMock(return_value=150)
        mock_server.store.get_all_projects = AsyncMock(
            return_value=["project1"]
        )
        mock_server.store.get_project_stats = AsyncMock(return_value={
            "project_name": "project1",
            "total_memories": 140,
            "categories": {"code": 100},
            "lifecycle_states": {"ACTIVE": 140},
        })

        # Mock Qdrant client for global count
        mock_count_result = MagicMock()
        mock_count_result.count = 10
        # Create a proper mock for the client.count method
        mock_server.store.client = MagicMock()
        mock_server.store.client.count = AsyncMock(return_value=mock_count_result)
        mock_server.store.collection_name = "test_collection"

        # Patch Qdrant imports to prevent import errors
        with patch("qdrant_client.models.Filter"), \
             patch("qdrant_client.models.FieldCondition"), \
             patch("qdrant_client.models.IsNullCondition"):
            result = await mock_server.get_dashboard_stats()

        assert result["status"] == "success"
        assert result["total_memories"] == 150
        # Global count from Qdrant client
        assert result["global_memories"] == 10

    @pytest.mark.asyncio
    async def test_get_dashboard_stats_storage_error(self, mock_server):
        """Test error handling when store fails."""
        mock_server.store.count = AsyncMock(side_effect=StorageError("DB error"))

        with pytest.raises(StorageError, match="Failed to retrieve dashboard stats"):
            await mock_server.get_dashboard_stats()


class TestGetRecentActivity:
    """Tests for get_recent_activity endpoint."""

    @pytest.mark.asyncio
    async def test_get_recent_activity_success(self, mock_server):
        """Test successful retrieval of recent activity."""
        mock_activity = {
            "recent_searches": [
                {
                    "search_id": "search1",
                    "query": "authentication",
                    "timestamp": "2025-01-15T10:00:00Z",
                    "rating": "helpful",
                    "project_name": "project1",
                },
                {
                    "search_id": "search2",
                    "query": "database",
                    "timestamp": "2025-01-15T09:00:00Z",
                    "rating": "not_helpful",
                    "project_name": "project1",
                },
            ],
            "recent_additions": [
                {
                    "id": "mem1",
                    "content": "New auth module implementation",
                    "category": "code",
                    "created_at": "2025-01-15T10:30:00Z",
                    "project_name": "project1",
                },
                {
                    "id": "mem2",
                    "content": "Updated database schema",
                    "category": "documentation",
                    "created_at": "2025-01-15T09:30:00Z",
                    "project_name": "project1",
                },
            ],
        }

        mock_server.store.get_recent_activity = AsyncMock(return_value=mock_activity)

        result = await mock_server.get_recent_activity(limit=20)

        assert result["status"] == "success"
        assert len(result["recent_searches"]) == 2
        assert len(result["recent_additions"]) == 2
        assert result["recent_searches"][0]["query"] == "authentication"
        assert result["recent_additions"][0]["content"] == "New auth module implementation"

        # Verify store was called with correct params
        mock_server.store.get_recent_activity.assert_called_once_with(
            limit=20,
            project_name=None,
        )

    @pytest.mark.asyncio
    async def test_get_recent_activity_with_project_filter(self, mock_server):
        """Test recent activity with project filter."""
        mock_activity = {
            "recent_searches": [
                {
                    "search_id": "search1",
                    "query": "test",
                    "timestamp": "2025-01-15T10:00:00Z",
                    "rating": "helpful",
                    "project_name": "project1",
                },
            ],
            "recent_additions": [
                {
                    "id": "mem1",
                    "content": "Test data",
                    "category": "code",
                    "created_at": "2025-01-15T10:30:00Z",
                    "project_name": "project1",
                },
            ],
        }

        mock_server.store.get_recent_activity = AsyncMock(return_value=mock_activity)

        result = await mock_server.get_recent_activity(
            limit=10,
            project_name="project1"
        )

        assert result["status"] == "success"
        assert len(result["recent_searches"]) == 1
        assert result["recent_searches"][0]["project_name"] == "project1"

        # Verify store was called with project filter
        mock_server.store.get_recent_activity.assert_called_once_with(
            limit=10,
            project_name="project1",
        )

    @pytest.mark.asyncio
    async def test_get_recent_activity_empty(self, mock_server):
        """Test recent activity with no data."""
        mock_activity = {
            "recent_searches": [],
            "recent_additions": [],
        }

        mock_server.store.get_recent_activity = AsyncMock(return_value=mock_activity)

        result = await mock_server.get_recent_activity()

        assert result["status"] == "success"
        assert result["recent_searches"] == []
        assert result["recent_additions"] == []

    @pytest.mark.asyncio
    async def test_get_recent_activity_custom_limit(self, mock_server):
        """Test recent activity with custom limit."""
        mock_activity = {
            "recent_searches": [{"search_id": f"s{i}"} for i in range(5)],
            "recent_additions": [{"id": f"m{i}"} for i in range(5)],
        }

        mock_server.store.get_recent_activity = AsyncMock(return_value=mock_activity)

        result = await mock_server.get_recent_activity(limit=5)

        assert result["status"] == "success"
        assert len(result["recent_searches"]) == 5
        assert len(result["recent_additions"]) == 5

        mock_server.store.get_recent_activity.assert_called_once_with(
            limit=5,
            project_name=None,
        )

    @pytest.mark.asyncio
    async def test_get_recent_activity_storage_error(self, mock_server):
        """Test error handling when store fails."""
        mock_server.store.get_recent_activity = AsyncMock(
            side_effect=StorageError("DB error")
        )

        with pytest.raises(StorageError, match="Failed to retrieve recent activity"):
            await mock_server.get_recent_activity()
