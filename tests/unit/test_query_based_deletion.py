"""
Unit tests for query-based deletion functionality.

Tests both the QdrantStore.delete_by_filter() method and the
MemoryRAGServer.delete_memories_by_query() MCP tool.
"""

import pytest
from datetime import datetime, UTC
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from src.store.qdrant_store import QdrantMemoryStore
from src.core.server import MemoryRAGServer
from src.core.models import MemoryUnit, SearchFilters, MemoryCategory, ContextLevel, MemoryScope, LifecycleState
from src.core.exceptions import ValidationError, ReadOnlyError, StorageError
from src.config import ServerConfig


@pytest.fixture
def mock_config():
    """Create a mock configuration."""
    config = MagicMock()
    config.qdrant_collection_name = "test_memories"
    config.advanced = MagicMock()
    config.advanced.read_only_mode = False
    return config


@pytest.fixture
def sample_memories():
    """Create sample memories for testing."""
    now = datetime.now(UTC)
    return [
        MemoryUnit(
            id=str(uuid4()),
            content="Test memory 1",
            category=MemoryCategory.PREFERENCE,
            context_level=ContextLevel.USER_PREFERENCE,
            scope=MemoryScope.GLOBAL,
            project_name="project1",
            importance=0.5,
            tags=["test", "sample"],
            lifecycle_state=LifecycleState.ACTIVE,
            created_at=now,
            updated_at=now,
        ),
        MemoryUnit(
            id=str(uuid4()),
            content="Test memory 2",
            category=MemoryCategory.CODE,
            context_level=ContextLevel.PROJECT_CONTEXT,
            scope=MemoryScope.PROJECT,
            project_name="project1",
            importance=0.8,
            tags=["code"],
            lifecycle_state=LifecycleState.ACTIVE,
            created_at=now,
            updated_at=now,
        ),
        MemoryUnit(
            id=str(uuid4()),
            content="Test memory 3",
            category=MemoryCategory.CODE,
            context_level=ContextLevel.PROJECT_CONTEXT,
            scope=MemoryScope.PROJECT,
            project_name="project2",
            importance=0.3,
            tags=["code"],
            lifecycle_state=LifecycleState.ARCHIVED,
            created_at=now,
            updated_at=now,
        ),
    ]


class TestQdrantStoreDeleteByFilter:
    """Test QdrantStore.delete_by_filter() method."""

    @pytest.mark.asyncio
    async def test_delete_by_filter_with_project(self, mock_config, sample_memories):
        """Test deleting by project name."""
        store = QdrantMemoryStore(config=mock_config, use_pool=False)

        # Mock client
        mock_client = AsyncMock()
        mock_point1 = MagicMock()
        mock_point1.id = sample_memories[0].id
        mock_point1.payload = {
            "category": "preference",
            "project_name": "project1",
            "lifecycle_state": "active"
        }
        mock_point2 = MagicMock()
        mock_point2.id = sample_memories[1].id
        mock_point2.payload = {
            "category": "code",
            "project_name": "project1",
            "lifecycle_state": "active"
        }

        # Mock scroll to return 2 memories
        mock_client.scroll.return_value = ([mock_point1, mock_point2], None)
        mock_client.delete.return_value = MagicMock(status="completed")

        with patch.object(store, '_get_client', return_value=mock_client), \
             patch.object(store, '_release_client'):

            filters = SearchFilters(project_name="project1")
            result = await store.delete_by_filter(filters, max_count=1000)

            assert result["deleted_count"] == 2
            assert result["breakdown_by_project"]["project1"] == 2
            assert "preference" in result["breakdown_by_category"]
            assert "code" in result["breakdown_by_category"]

    @pytest.mark.asyncio
    async def test_delete_by_filter_with_category(self, mock_config, sample_memories):
        """Test deleting by category."""
        store = QdrantMemoryStore(config=mock_config, use_pool=False)

        mock_client = AsyncMock()
        mock_point = MagicMock()
        mock_point.id = sample_memories[1].id
        mock_point.payload = {
            "category": "code",
            "project_name": "project1",
            "lifecycle_state": "active"
        }

        mock_client.scroll.return_value = ([mock_point], None)
        mock_client.delete.return_value = MagicMock(status="completed")

        with patch.object(store, '_get_client', return_value=mock_client), \
             patch.object(store, '_release_client'):

            filters = SearchFilters(category="code")
            result = await store.delete_by_filter(filters, max_count=1000)

            assert result["deleted_count"] == 1
            assert result["breakdown_by_category"]["code"] == 1

    @pytest.mark.asyncio
    async def test_delete_by_filter_max_count_limit(self, mock_config):
        """Test that max_count is enforced."""
        store = QdrantMemoryStore(config=mock_config, use_pool=False)

        mock_client = AsyncMock()
        # Create 5 mock points
        mock_points = []
        for i in range(5):
            point = MagicMock()
            point.id = str(uuid4())
            point.payload = {"category": "code", "project_name": "test", "lifecycle_state": "active"}
            mock_points.append(point)

        mock_client.scroll.return_value = (mock_points, None)
        mock_client.delete.return_value = MagicMock(status="completed")

        with patch.object(store, '_get_client', return_value=mock_client), \
             patch.object(store, '_release_client'):

            filters = SearchFilters(category="code")
            result = await store.delete_by_filter(filters, max_count=3)

            # Should only delete 3 memories
            assert result["deleted_count"] == 3

    @pytest.mark.asyncio
    async def test_delete_by_filter_invalid_max_count(self, mock_config):
        """Test that invalid max_count raises ValidationError."""
        store = QdrantMemoryStore(config=mock_config, use_pool=False)

        filters = SearchFilters(category="code")

        # Test max_count < 1
        with pytest.raises(ValidationError, match="max_count must be between 1 and 1000"):
            await store.delete_by_filter(filters, max_count=0)

        # Test max_count > 1000
        with pytest.raises(ValidationError, match="max_count must be between 1 and 1000"):
            await store.delete_by_filter(filters, max_count=1001)

    @pytest.mark.asyncio
    async def test_delete_by_filter_no_matches(self, mock_config):
        """Test deleting when no memories match the filter."""
        store = QdrantMemoryStore(config=mock_config, use_pool=False)

        mock_client = AsyncMock()
        mock_client.scroll.return_value = ([], None)

        with patch.object(store, '_get_client', return_value=mock_client), \
             patch.object(store, '_release_client'):

            filters = SearchFilters(project_name="nonexistent")
            result = await store.delete_by_filter(filters, max_count=1000)

            assert result["deleted_count"] == 0
            assert result["breakdown_by_category"] == {}
            assert result["breakdown_by_project"] == {}

    @pytest.mark.asyncio
    async def test_delete_by_filter_with_tags(self, mock_config):
        """Test deleting by tags."""
        store = QdrantMemoryStore(config=mock_config, use_pool=False)

        mock_client = AsyncMock()
        mock_point = MagicMock()
        mock_point.id = str(uuid4())
        mock_point.payload = {
            "category": "preference",
            "project_name": "test",
            "lifecycle_state": "active",
            "tags": ["test", "sample"]
        }

        mock_client.scroll.return_value = ([mock_point], None)
        mock_client.delete.return_value = MagicMock(status="completed")

        with patch.object(store, '_get_client', return_value=mock_client), \
             patch.object(store, '_release_client'):

            filters = SearchFilters(tags=["test"])
            result = await store.delete_by_filter(filters, max_count=1000)

            assert result["deleted_count"] == 1

    @pytest.mark.asyncio
    async def test_delete_by_filter_with_importance_range(self, mock_config):
        """Test deleting by importance range."""
        store = QdrantMemoryStore(config=mock_config, use_pool=False)

        mock_client = AsyncMock()
        mock_point = MagicMock()
        mock_point.id = str(uuid4())
        mock_point.payload = {
            "category": "preference",
            "project_name": "test",
            "lifecycle_state": "active"
        }

        mock_client.scroll.return_value = ([mock_point], None)
        mock_client.delete.return_value = MagicMock(status="completed")

        with patch.object(store, '_get_client', return_value=mock_client), \
             patch.object(store, '_release_client'):

            filters = SearchFilters(min_importance=0.0, max_importance=0.5)
            result = await store.delete_by_filter(filters, max_count=1000)

            assert result["deleted_count"] == 1

    @pytest.mark.asyncio
    async def test_delete_by_filter_error_handling(self, mock_config):
        """Test that errors are properly handled."""
        store = QdrantMemoryStore(config=mock_config, use_pool=False)

        mock_client = AsyncMock()
        mock_client.scroll.side_effect = Exception("Database error")

        with patch.object(store, '_get_client', return_value=mock_client), \
             patch.object(store, '_release_client'):

            filters = SearchFilters(category="code")

            with pytest.raises(StorageError, match="Failed to delete memories by filter"):
                await store.delete_by_filter(filters, max_count=1000)


class TestServerDeleteMemoriesByQuery:
    """Test MemoryRAGServer.delete_memories_by_query() method."""

    @pytest.mark.asyncio
    async def test_dry_run_mode(self, mock_config, sample_memories):
        """Test dry_run mode (preview only)."""
        server = MemoryRAGServer(config=mock_config)
        server.store = AsyncMock()

        # Mock store.list_memories to return sample memories
        server.store.list_memories = AsyncMock(return_value=sample_memories[:2])

        result = await server.delete_memories_by_query(
            project_name="project1",
            dry_run=True
        )

        assert result["preview"] is True
        assert result["total_matches"] == 2
        assert result["deleted_count"] == 0
        assert "project1" in result["breakdown_by_project"]
        assert len(result["warnings"]) > 0

    @pytest.mark.asyncio
    async def test_actual_deletion(self, mock_config):
        """Test actual deletion mode."""
        server = MemoryRAGServer(config=mock_config)

        # Mock store.delete_by_filter
        mock_result = {
            "deleted_count": 2,
            "breakdown_by_category": {"code": 2},
            "breakdown_by_project": {"project1": 2},
            "breakdown_by_lifecycle": {"active": 2}
        }

        with patch.object(server.store, 'delete_by_filter', return_value=mock_result):
            result = await server.delete_memories_by_query(
                project_name="project1",
                category="code",
                dry_run=False
            )

            assert result["preview"] is False
            assert result["deleted_count"] == 2
            assert result["breakdown_by_category"]["code"] == 2

    @pytest.mark.asyncio
    async def test_read_only_mode_check(self, mock_config):
        """Test that read-only mode prevents deletion."""
        mock_config.advanced.read_only_mode = True
        server = MemoryRAGServer(config=mock_config)

        with pytest.raises(ReadOnlyError, match="Cannot delete memories in read-only mode"):
            await server.delete_memories_by_query(
                project_name="test",
                dry_run=False
            )

    @pytest.mark.asyncio
    async def test_dry_run_with_high_importance_warning(self, mock_config):
        """Test that dry_run generates warning for high importance memories."""
        server = MemoryRAGServer(config=mock_config)

        high_importance_memory = MemoryUnit(
            id=str(uuid4()),
            content="Important memory",
            category=MemoryCategory.PREFERENCE,
            context_level=ContextLevel.USER_PREFERENCE,
            scope=MemoryScope.GLOBAL,
            importance=0.9,
            lifecycle_state=LifecycleState.ACTIVE,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        with patch.object(server.store, 'list_memories', return_value=[high_importance_memory]):
            result = await server.delete_memories_by_query(
                max_importance=1.0,
                dry_run=True
            )

            # Check for high-importance warning
            assert any("high-importance" in w for w in result["warnings"])

    @pytest.mark.asyncio
    async def test_dry_run_with_multiple_projects_warning(self, mock_config, sample_memories):
        """Test that dry_run warns about multi-project deletion."""
        server = MemoryRAGServer(config=mock_config)

        # Use all sample memories (includes project1 and project2)
        with patch.object(server.store, 'list_memories', return_value=sample_memories):
            result = await server.delete_memories_by_query(
                category="code",
                dry_run=True
            )

            # Check for multi-project warning
            assert any("projects" in w for w in result["warnings"])

    @pytest.mark.asyncio
    async def test_requires_confirmation_threshold(self, mock_config):
        """Test that requires_confirmation is set correctly."""
        server = MemoryRAGServer(config=mock_config)

        # Create 15 memories (above threshold of 10)
        many_memories = [
            MemoryUnit(
                id=str(uuid4()),
                content=f"Memory {i}",
                category=MemoryCategory.PREFERENCE,
                context_level=ContextLevel.USER_PREFERENCE,
                scope=MemoryScope.GLOBAL,
                lifecycle_state=LifecycleState.ACTIVE,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
            for i in range(15)
        ]

        with patch.object(server.store, 'list_memories', return_value=many_memories):
            result = await server.delete_memories_by_query(dry_run=True)

            assert result["requires_confirmation"] is True

    @pytest.mark.asyncio
    async def test_filter_combination(self, mock_config):
        """Test combining multiple filters."""
        server = MemoryRAGServer(config=mock_config)

        mock_result = {
            "deleted_count": 1,
            "breakdown_by_category": {"code": 1},
            "breakdown_by_project": {"project1": 1},
            "breakdown_by_lifecycle": {"active": 1}
        }

        with patch.object(server.store, 'delete_by_filter', return_value=mock_result):
            result = await server.delete_memories_by_query(
                project_name="project1",
                category="code",
                tags=["test"],
                min_importance=0.3,
                max_importance=0.7,
                dry_run=False
            )

            assert result["deleted_count"] == 1

    @pytest.mark.asyncio
    async def test_stats_update_on_deletion(self, mock_config):
        """Test that server stats are updated after deletion."""
        server = MemoryRAGServer(config=mock_config)
        initial_deleted = server.stats.get("memories_deleted", 0)

        mock_result = {
            "deleted_count": 5,
            "breakdown_by_category": {"code": 5},
            "breakdown_by_project": {"project1": 5},
            "breakdown_by_lifecycle": {"active": 5}
        }

        with patch.object(server.store, 'delete_by_filter', return_value=mock_result):
            await server.delete_memories_by_query(
                project_name="project1",
                dry_run=False
            )

            assert server.stats["memories_deleted"] == initial_deleted + 5

    @pytest.mark.asyncio
    async def test_error_propagation(self, mock_config):
        """Test that errors are properly propagated."""
        server = MemoryRAGServer(config=mock_config)

        with patch.object(server.store, 'delete_by_filter', side_effect=Exception("Database error")):
            with pytest.raises(StorageError, match="Failed to delete memories by query"):
                await server.delete_memories_by_query(
                    project_name="test",
                    dry_run=False
                )

    @pytest.mark.asyncio
    async def test_empty_filters(self, mock_config):
        """Test deletion with no filters (matches all, limited by max_count)."""
        server = MemoryRAGServer(config=mock_config)

        # Create some memories for dry run
        memories = [
            MemoryUnit(
                id=str(uuid4()),
                content=f"Memory {i}",
                category=MemoryCategory.PREFERENCE,
                context_level=ContextLevel.USER_PREFERENCE,
                scope=MemoryScope.GLOBAL,
                lifecycle_state=LifecycleState.ACTIVE,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
            for i in range(5)
        ]

        with patch.object(server.store, 'list_memories', return_value=memories):
            result = await server.delete_memories_by_query(dry_run=True)

            assert result["total_matches"] == 5
            assert result["deleted_count"] == 0
