"""Tests for project statistics methods in stores."""

import pytest
from datetime import datetime, UTC
from unittest.mock import Mock, AsyncMock, MagicMock, patch
from src.store.qdrant_store import QdrantMemoryStore
from src.store.sqlite_store import SQLiteMemoryStore
from src.core.exceptions import StorageError


class TestQdrantProjectStats:
    """Test project statistics methods in Qdrant store."""

    @pytest.mark.asyncio
    async def test_get_all_projects_empty(self):
        """Test get_all_projects with no projects."""
        store = QdrantMemoryStore()
        store.client = MagicMock()
        store.client.scroll.return_value = ([], None)

        projects = await store.get_all_projects()

        assert projects == []

    @pytest.mark.asyncio
    async def test_get_all_projects_single_page(self):
        """Test get_all_projects with single page of results."""
        store = QdrantMemoryStore()
        store.client = MagicMock()

        # Mock points with project names
        mock_points = [
            MagicMock(payload={"project_name": "project1"}),
            MagicMock(payload={"project_name": "project2"}),
            MagicMock(payload={"project_name": "project1"}),  # Duplicate
        ]

        store.client.scroll.return_value = (mock_points, None)

        projects = await store.get_all_projects()

        assert len(projects) == 2
        assert "project1" in projects
        assert "project2" in projects
        assert projects == sorted(projects)  # Should be sorted

    @pytest.mark.asyncio
    async def test_get_all_projects_multiple_pages(self):
        """Test get_all_projects with pagination."""
        store = QdrantMemoryStore()
        store.client = MagicMock()

        # First page
        page1 = [
            MagicMock(payload={"project_name": "project1"}),
            MagicMock(payload={"project_name": "project2"}),
        ]

        # Second page
        page2 = [
            MagicMock(payload={"project_name": "project3"}),
        ]

        store.client.scroll.side_effect = [
            (page1, "offset1"),
            (page2, None),
        ]

        projects = await store.get_all_projects()

        assert len(projects) == 3
        assert projects == ["project1", "project2", "project3"]

    @pytest.mark.asyncio
    async def test_get_all_projects_filters_none(self):
        """Test that None project names are filtered out."""
        store = QdrantMemoryStore()
        store.client = MagicMock()

        mock_points = [
            MagicMock(payload={"project_name": "project1"}),
            MagicMock(payload={"project_name": None}),
            MagicMock(payload={}),  # No project_name key
        ]

        store.client.scroll.return_value = (mock_points, None)

        projects = await store.get_all_projects()

        assert len(projects) == 1
        assert projects == ["project1"]

    @pytest.mark.asyncio
    async def test_get_all_projects_not_initialized(self):
        """Test get_all_projects when store not initialized."""
        store = QdrantMemoryStore()
        store.client = None

        with pytest.raises(StorageError, match="not initialized"):
            await store.get_all_projects()

    @pytest.mark.asyncio
    async def test_get_all_projects_error(self):
        """Test get_all_projects handles errors."""
        store = QdrantMemoryStore()
        store.client = MagicMock()
        store.client.scroll.side_effect = Exception("Scroll error")

        with pytest.raises(StorageError, match="Failed to get projects"):
            await store.get_all_projects()

    @pytest.mark.asyncio
    async def test_get_project_stats(self):
        """Test get_project_stats returns correct statistics."""
        store = QdrantMemoryStore()
        store.client = MagicMock()

        # Mock project memories
        mock_points = [
            MagicMock(payload={
                "project_name": "test-project",
                "category": "code",
                "context_level": "FILE",
                "updated_at": "2025-01-01T12:00:00+00:00",
                "file_path": "/path/to/file1.py"
            }),
            MagicMock(payload={
                "project_name": "test-project",
                "category": "code",
                "context_level": "FUNCTION",
                "updated_at": "2025-01-02T12:00:00+00:00",
                "file_path": "/path/to/file2.py"
            }),
            MagicMock(payload={
                "project_name": "test-project",
                "category": "context",
                "context_level": "PROJECT_CONTEXT",
                "updated_at": "2025-01-01T10:00:00+00:00",
            }),
        ]

        store.client.scroll.return_value = (mock_points, None)

        stats = await store.get_project_stats("test-project")

        assert stats["project_name"] == "test-project"
        assert stats["total_memories"] == 3
        assert stats["num_files"] == 2
        assert stats["num_functions"] == 2  # code category count
        assert "code" in stats["categories"]
        assert stats["categories"]["code"] == 2
        assert stats["categories"]["context"] == 1
        assert "FILE" in stats["context_levels"]
        assert stats["last_indexed"] is not None

    @pytest.mark.asyncio
    async def test_get_project_stats_empty(self):
        """Test get_project_stats with no memories."""
        store = QdrantMemoryStore()
        store.client = MagicMock()
        store.client.scroll.return_value = ([], None)

        stats = await store.get_project_stats("empty-project")

        assert stats["total_memories"] == 0
        assert stats["num_files"] == 0
        assert stats["num_functions"] == 0
        assert stats["categories"] == {}

    @pytest.mark.asyncio
    async def test_get_project_stats_not_initialized(self):
        """Test get_project_stats when store not initialized."""
        store = QdrantMemoryStore()
        store.client = None

        with pytest.raises(StorageError, match="not initialized"):
            await store.get_project_stats("test-project")

    @pytest.mark.asyncio
    async def test_get_project_stats_error(self):
        """Test get_project_stats handles errors."""
        store = QdrantMemoryStore()
        store.client = MagicMock()
        store.client.scroll.side_effect = Exception("Scroll error")

        with pytest.raises(StorageError, match="Failed to get project stats"):
            await store.get_project_stats("test-project")
