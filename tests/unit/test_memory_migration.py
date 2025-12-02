"""Tests for memory migration MCP tools (UX-016)."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from src.core.server import MemoryRAGServer
from src.core.exceptions import ReadOnlyError, ValidationError, StorageError


@pytest.fixture
def mock_server():
    """Create a mock server for testing."""
    server = MagicMock(spec=MemoryRAGServer)
    server.config = MagicMock()
    server.config.advanced.read_only_mode = False
    server.store = AsyncMock()
    server.stats = {"memories_deleted": 0}
    return server


class TestMigrateMemoryScope:
    """Test migrate_memory_scope MCP tool."""

    @pytest.mark.asyncio
    async def test_migrate_to_project(self, mock_server):
        """Test migrating memory to a project scope."""
        from src.core.server import MemoryRAGServer

        # Setup
        mock_server.store.migrate_memory_scope.return_value = True

        # Create real instance with mocked store
        server = MemoryRAGServer.__new__(MemoryRAGServer)
        server.config = mock_server.config
        server.store = mock_server.store
        server.stats = mock_server.stats

        # Execute
        result = await server.migrate_memory_scope(
            memory_id="mem-123", new_project_name="my-project"
        )

        # Verify
        assert result["status"] == "success"
        assert result["memory_id"] == "mem-123"
        assert result["scope"] == "my-project"
        assert result["project_name"] == "my-project"
        mock_server.store.migrate_memory_scope.assert_called_once_with(
            "mem-123", "my-project"
        )

    @pytest.mark.asyncio
    async def test_migrate_to_global(self, mock_server):
        """Test migrating memory to global scope."""
        from src.core.server import MemoryRAGServer

        # Setup
        mock_server.store.migrate_memory_scope.return_value = True

        # Create real instance with mocked store
        server = MemoryRAGServer.__new__(MemoryRAGServer)
        server.config = mock_server.config
        server.store = mock_server.store
        server.stats = mock_server.stats

        # Execute
        result = await server.migrate_memory_scope(
            memory_id="mem-123", new_project_name=None
        )

        # Verify
        assert result["status"] == "success"
        assert result["scope"] == "global"
        assert result["project_name"] is None

    @pytest.mark.asyncio
    async def test_migrate_memory_not_found(self, mock_server):
        """Test migrating non-existent memory."""
        from src.core.server import MemoryRAGServer

        # Setup
        mock_server.store.migrate_memory_scope.return_value = False

        # Create real instance with mocked store
        server = MemoryRAGServer.__new__(MemoryRAGServer)
        server.config = mock_server.config
        server.store = mock_server.store
        server.stats = mock_server.stats

        # Execute
        result = await server.migrate_memory_scope(
            memory_id="nonexistent", new_project_name="my-project"
        )

        # Verify
        assert result["status"] == "not_found"

    @pytest.mark.asyncio
    async def test_migrate_read_only_mode(self, mock_server):
        """Test migration fails in read-only mode."""
        from src.core.server import MemoryRAGServer

        # Setup
        mock_server.config.advanced.read_only_mode = True

        # Create real instance with mocked store
        server = MemoryRAGServer.__new__(MemoryRAGServer)
        server.config = mock_server.config
        server.store = mock_server.store
        server.stats = mock_server.stats

        # Execute & Verify
        with pytest.raises(ReadOnlyError):
            await server.migrate_memory_scope("mem-123", "my-project")

    @pytest.mark.asyncio
    async def test_migrate_storage_error(self, mock_server):
        """Test handling of storage errors during migration."""
        from src.core.server import MemoryRAGServer

        # Setup
        mock_server.store.migrate_memory_scope.side_effect = Exception("DB error")

        # Create real instance with mocked store
        server = MemoryRAGServer.__new__(MemoryRAGServer)
        server.config = mock_server.config
        server.store = mock_server.store
        server.stats = mock_server.stats

        # Execute & Verify
        with pytest.raises(StorageError):
            await server.migrate_memory_scope("mem-123", "my-project")


class TestBulkReclassify:
    """Test bulk_reclassify MCP tool."""

    @pytest.mark.asyncio
    async def test_bulk_reclassify_by_project(self, mock_server):
        """Test bulk reclassification for a project."""
        from src.core.server import MemoryRAGServer

        # Setup
        mock_server.store.bulk_update_context_level.return_value = 5

        # Create real instance with mocked store
        server = MemoryRAGServer.__new__(MemoryRAGServer)
        server.config = mock_server.config
        server.store = mock_server.store
        server.stats = mock_server.stats

        # Execute
        result = await server.bulk_reclassify(
            new_context_level="ARCHIVE", project_name="old-project"
        )

        # Verify
        assert result["status"] == "success"
        assert result["count"] == 5
        assert result["new_context_level"] == "ARCHIVE"
        assert result["filters"]["project_name"] == "old-project"
        mock_server.store.bulk_update_context_level.assert_called_once_with(
            new_context_level="ARCHIVE",
            project_name="old-project",
            current_context_level=None,
            category=None,
        )

    @pytest.mark.asyncio
    async def test_bulk_reclassify_with_filters(self, mock_server):
        """Test bulk reclassification with multiple filters."""
        from src.core.server import MemoryRAGServer

        # Setup
        mock_server.store.bulk_update_context_level.return_value = 3

        # Create real instance with mocked store
        server = MemoryRAGServer.__new__(MemoryRAGServer)
        server.config = mock_server.config
        server.store = mock_server.store
        server.stats = mock_server.stats

        # Execute
        result = await server.bulk_reclassify(
            new_context_level="CORE",
            project_name="my-project",
            current_context_level="DETAIL",
            category="CODE",
        )

        # Verify
        assert result["count"] == 3
        assert result["filters"]["current_context_level"] == "DETAIL"
        assert result["filters"]["category"] == "CODE"

    @pytest.mark.asyncio
    async def test_bulk_reclassify_zero_results(self, mock_server):
        """Test bulk reclassification with no matches."""
        from src.core.server import MemoryRAGServer

        # Setup
        mock_server.store.bulk_update_context_level.return_value = 0

        # Create real instance with mocked store
        server = MemoryRAGServer.__new__(MemoryRAGServer)
        server.config = mock_server.config
        server.store = mock_server.store
        server.stats = mock_server.stats

        # Execute
        result = await server.bulk_reclassify(
            new_context_level="ARCHIVE", project_name="nonexistent"
        )

        # Verify
        assert result["count"] == 0

    @pytest.mark.asyncio
    async def test_bulk_reclassify_read_only_mode(self, mock_server):
        """Test bulk reclassification fails in read-only mode."""
        from src.core.server import MemoryRAGServer

        # Setup
        mock_server.config.advanced.read_only_mode = True

        # Create real instance with mocked store
        server = MemoryRAGServer.__new__(MemoryRAGServer)
        server.config = mock_server.config
        server.store = mock_server.store
        server.stats = mock_server.stats

        # Execute & Verify
        with pytest.raises(ReadOnlyError):
            await server.bulk_reclassify("ARCHIVE", project_name="test")


class TestFindDuplicateMemories:
    """Test find_duplicate_memories MCP tool."""

    @pytest.mark.asyncio
    async def test_find_duplicates_global(self, mock_server):
        """Test finding duplicates in global scope."""
        from src.core.server import MemoryRAGServer

        # Setup
        duplicate_groups = [["mem-1", "mem-2"], ["mem-3", "mem-4", "mem-5"]]
        mock_server.store.find_duplicate_memories.return_value = duplicate_groups

        # Create real instance with mocked store
        server = MemoryRAGServer.__new__(MemoryRAGServer)
        server.config = mock_server.config
        server.store = mock_server.store
        server.stats = mock_server.stats

        # Execute
        result = await server.find_duplicate_memories()

        # Verify
        assert result["status"] == "success"
        assert result["total_groups"] == 2
        assert result["duplicate_groups"] == duplicate_groups
        assert result["similarity_threshold"] == 0.95
        mock_server.store.find_duplicate_memories.assert_called_once_with(
            project_name=None,
            similarity_threshold=0.95,
        )

    @pytest.mark.asyncio
    async def test_find_duplicates_by_project(self, mock_server):
        """Test finding duplicates in a specific project."""
        from src.core.server import MemoryRAGServer

        # Setup
        duplicate_groups = [["mem-1", "mem-2"]]
        mock_server.store.find_duplicate_memories.return_value = duplicate_groups

        # Create real instance with mocked store
        server = MemoryRAGServer.__new__(MemoryRAGServer)
        server.config = mock_server.config
        server.store = mock_server.store
        server.stats = mock_server.stats

        # Execute
        result = await server.find_duplicate_memories(
            project_name="my-project", similarity_threshold=0.90
        )

        # Verify
        assert result["project_name"] == "my-project"
        assert result["similarity_threshold"] == 0.90

    @pytest.mark.asyncio
    async def test_find_duplicates_none_found(self, mock_server):
        """Test finding duplicates when none exist."""
        from src.core.server import MemoryRAGServer

        # Setup
        mock_server.store.find_duplicate_memories.return_value = []

        # Create real instance with mocked store
        server = MemoryRAGServer.__new__(MemoryRAGServer)
        server.config = mock_server.config
        server.store = mock_server.store
        server.stats = mock_server.stats

        # Execute
        result = await server.find_duplicate_memories()

        # Verify
        assert result["total_groups"] == 0
        assert result["duplicate_groups"] == []


class TestMergeMemories:
    """Test merge_memories MCP tool."""

    @pytest.mark.asyncio
    async def test_merge_two_memories(self, mock_server):
        """Test merging two memories."""
        from src.core.server import MemoryRAGServer

        # Setup
        mock_server.store.merge_memories.return_value = "mem-1"

        # Create real instance with mocked store
        server = MemoryRAGServer.__new__(MemoryRAGServer)
        server.config = mock_server.config
        server.store = mock_server.store
        server.stats = mock_server.stats

        # Execute
        result = await server.merge_memories(memory_ids=["mem-1", "mem-2"])

        # Verify
        assert result["status"] == "success"
        assert result["merged_id"] == "mem-1"
        assert result["count"] == 2
        assert result["source_ids"] == ["mem-1", "mem-2"]
        mock_server.store.merge_memories.assert_called_once_with(
            memory_ids=["mem-1", "mem-2"],
            keep_id=None,
        )

    @pytest.mark.asyncio
    async def test_merge_multiple_memories_with_keep_id(self, mock_server):
        """Test merging multiple memories with specific keep_id."""
        from src.core.server import MemoryRAGServer

        # Setup
        mock_server.store.merge_memories.return_value = "mem-2"

        # Create real instance with mocked store
        server = MemoryRAGServer.__new__(MemoryRAGServer)
        server.config = mock_server.config
        server.store = mock_server.store
        server.stats = mock_server.stats

        # Execute
        result = await server.merge_memories(
            memory_ids=["mem-1", "mem-2", "mem-3"], keep_id="mem-2"
        )

        # Verify
        assert result["merged_id"] == "mem-2"
        assert result["count"] == 3
        mock_server.store.merge_memories.assert_called_once_with(
            memory_ids=["mem-1", "mem-2", "mem-3"],
            keep_id="mem-2",
        )

    @pytest.mark.asyncio
    async def test_merge_insufficient_memories(self, mock_server):
        """Test merging fails with less than 2 memories."""
        from src.core.server import MemoryRAGServer

        # Create real instance with mocked store
        server = MemoryRAGServer.__new__(MemoryRAGServer)
        server.config = mock_server.config
        server.store = mock_server.store
        server.stats = mock_server.stats

        # Execute & Verify
        with pytest.raises(ValidationError):
            await server.merge_memories(memory_ids=["mem-1"])

    @pytest.mark.asyncio
    async def test_merge_read_only_mode(self, mock_server):
        """Test merge fails in read-only mode."""
        from src.core.server import MemoryRAGServer

        # Setup
        mock_server.config.advanced.read_only_mode = True

        # Create real instance with mocked store
        server = MemoryRAGServer.__new__(MemoryRAGServer)
        server.config = mock_server.config
        server.store = mock_server.store
        server.stats = mock_server.stats

        # Execute & Verify
        with pytest.raises(ReadOnlyError):
            await server.merge_memories(["mem-1", "mem-2"])

    @pytest.mark.asyncio
    async def test_merge_storage_error(self, mock_server):
        """Test handling of storage errors during merge."""
        from src.core.server import MemoryRAGServer

        # Setup
        mock_server.store.merge_memories.side_effect = Exception("DB error")

        # Create real instance with mocked store
        server = MemoryRAGServer.__new__(MemoryRAGServer)
        server.config = mock_server.config
        server.store = mock_server.store
        server.stats = mock_server.stats

        # Execute & Verify
        with pytest.raises(StorageError):
            await server.merge_memories(["mem-1", "mem-2"])


class TestMigrationIntegration:
    """Integration tests for migration workflows."""

    @pytest.mark.asyncio
    async def test_migration_workflow(self, mock_server):
        """Test complete migration workflow: find duplicates → merge → reclassify → migrate."""
        from src.core.server import MemoryRAGServer

        # Setup
        mock_server.store.find_duplicate_memories.return_value = [["mem-1", "mem-2"]]
        mock_server.store.merge_memories.return_value = "mem-1"
        mock_server.store.bulk_update_context_level.return_value = 1
        mock_server.store.migrate_memory_scope.return_value = True

        # Create real instance with mocked store
        server = MemoryRAGServer.__new__(MemoryRAGServer)
        server.config = mock_server.config
        server.store = mock_server.store
        server.stats = mock_server.stats

        # Step 1: Find duplicates
        dup_result = await server.find_duplicate_memories(project_name="test")
        assert dup_result["total_groups"] == 1

        # Step 2: Merge duplicates
        merge_result = await server.merge_memories(["mem-1", "mem-2"])
        assert merge_result["merged_id"] == "mem-1"

        # Step 3: Reclassify merged memory
        reclassify_result = await server.bulk_reclassify(
            new_context_level="CORE", project_name="test"
        )
        assert reclassify_result["count"] == 1

        # Step 4: Migrate to different scope
        migrate_result = await server.migrate_memory_scope("mem-1", "new-project")
        assert migrate_result["scope"] == "new-project"
