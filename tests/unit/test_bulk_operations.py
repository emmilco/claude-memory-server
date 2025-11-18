"""
Unit tests for bulk memory operations.

Tests the BulkDeleteManager including:
- Preview generation
- Batch processing
- Safety limits
- Error handling
- Dry-run mode
"""

import pytest
from datetime import datetime, timedelta
from typing import List
from unittest.mock import AsyncMock, Mock

from src.memory.bulk_operations import (
    BulkDeleteManager,
    BulkDeleteFilters,
    BulkDeletePreview,
    BulkDeleteResult,
)
from src.core.models import (
    MemoryUnit,
    MemoryCategory,
    ContextLevel,
    LifecycleState,
)


@pytest.fixture
def mock_store():
    """Create a mock memory store."""
    store = AsyncMock()
    store.delete = AsyncMock(return_value=True)
    return store


@pytest.fixture
def bulk_manager(mock_store):
    """Create a BulkDeleteManager instance."""
    return BulkDeleteManager(
        store=mock_store,
        max_batch_size=100,
        max_total_operations=1000,
    )


@pytest.fixture
def sample_memories():
    """Create sample memories for testing."""
    memories = []
    base_time = datetime.now()

    # Create 150 memories with variety
    for i in range(150):
        memories.append(
            MemoryUnit(
                id=f"mem_{i}",
                content=f"Memory content {i}" * 10,  # ~150 bytes
                category=MemoryCategory.CONTEXT if i < 100 else MemoryCategory.FACT,
                context_level=ContextLevel.SESSION_STATE,
                importance=0.3 if i < 50 else 0.8,
                project_name="test-project" if i < 120 else "other-project",
                created_at=base_time - timedelta(days=i),
                updated_at=base_time - timedelta(days=i),
                lifecycle_state=LifecycleState.ACTIVE,
            )
        )

    return memories


class TestBulkDeleteFilters:
    """Test BulkDeleteFilters model."""

    def test_default_filters(self):
        """Test default filter values."""
        filters = BulkDeleteFilters()
        assert filters.max_count == 1000
        assert filters.confirm_threshold == 10
        assert filters.min_importance == 0.0
        assert filters.max_importance == 1.0

    def test_custom_filters(self):
        """Test custom filter values."""
        filters = BulkDeleteFilters(
            category="session_state",
            project_name="test-project",
            max_count=500,
            min_importance=0.5,
        )
        assert filters.category == "session_state"
        assert filters.project_name == "test-project"
        assert filters.max_count == 500
        assert filters.min_importance == 0.5

    def test_max_count_validation(self):
        """Test max_count validation."""
        # Valid
        BulkDeleteFilters(max_count=1)
        BulkDeleteFilters(max_count=1000)

        # Invalid (should fail validation)
        with pytest.raises(Exception):  # Pydantic ValidationError
            BulkDeleteFilters(max_count=0)

        with pytest.raises(Exception):
            BulkDeleteFilters(max_count=1001)


class TestBulkDeleteManager:
    """Test BulkDeleteManager functionality."""

    def test_initialization(self, bulk_manager):
        """Test manager initialization."""
        assert bulk_manager.max_batch_size == 100
        assert bulk_manager.max_total_operations == 1000

    def test_estimate_memory_size(self, bulk_manager):
        """Test memory size estimation."""
        memory = MemoryUnit(
            id="test",
            content="Hello" * 100,  # ~500 bytes
            category=MemoryCategory.FACT,
            context_level=ContextLevel.SESSION_STATE,
        )

        size = bulk_manager._estimate_memory_size(memory)

        # Should be content + metadata + vector
        # ~500 + 200 + 1536 = ~2236 bytes
        assert size > 500
        assert size < 5000

    def test_calculate_breakdowns(self, bulk_manager, sample_memories):
        """Test breakdown calculations."""
        (
            category_breakdown,
            lifecycle_breakdown,
            project_breakdown,
        ) = bulk_manager._calculate_breakdowns(sample_memories)

        # Check category breakdown
        assert category_breakdown["context"] == 100
        assert category_breakdown["fact"] == 50

        # Check lifecycle breakdown
        assert lifecycle_breakdown["ACTIVE"] == 150

        # Check project breakdown
        assert project_breakdown["test-project"] == 120
        assert project_breakdown["other-project"] == 30

    def test_generate_warnings_large_deletion(self, bulk_manager, sample_memories):
        """Test warning generation for large deletions."""
        filters = BulkDeleteFilters(max_count=1000)
        warnings = bulk_manager._generate_warnings(sample_memories, 150, filters)

        # Should warn about large deletion
        assert any("150 memories" in w for w in warnings)

    def test_generate_warnings_high_importance(self, bulk_manager, sample_memories):
        """Test warning generation for high-importance memories."""
        filters = BulkDeleteFilters()
        warnings = bulk_manager._generate_warnings(sample_memories, 150, filters)

        # Should warn about high-importance memories (100 with importance 0.8)
        assert any("high-importance" in w.lower() for w in warnings)

    def test_generate_warnings_recent_memories(self, bulk_manager):
        """Test warning generation for recent memories."""
        recent_memories = [
            MemoryUnit(
                id=f"mem_{i}",
                content="Recent memory",
                category=MemoryCategory.FACT,
                context_level=ContextLevel.SESSION_STATE,
                created_at=datetime.now() - timedelta(days=1),
            )
            for i in range(10)
        ]

        filters = BulkDeleteFilters()
        warnings = bulk_manager._generate_warnings(recent_memories, 10, filters)

        # Should warn about recent memories
        assert any("last 7 days" in w.lower() for w in warnings)

    def test_generate_warnings_multi_project(self, bulk_manager, sample_memories):
        """Test warning generation for multi-project deletion."""
        filters = BulkDeleteFilters()  # No project_name filter
        warnings = bulk_manager._generate_warnings(sample_memories, 150, filters)

        # Should warn about affecting multiple projects
        assert any("projects" in w.lower() for w in warnings)

    @pytest.mark.asyncio
    async def test_preview_deletion(self, bulk_manager, sample_memories):
        """Test deletion preview generation."""
        filters = BulkDeleteFilters(max_count=1000)
        preview = await bulk_manager.preview_deletion(sample_memories, filters)

        assert isinstance(preview, BulkDeletePreview)
        assert preview.total_matches == 150
        assert len(preview.sample_memories) == 10  # First 10
        assert preview.breakdown_by_category["context"] == 100
        assert preview.breakdown_by_category["fact"] == 50
        assert preview.estimated_storage_freed_mb > 0
        assert len(preview.warnings) > 0
        assert preview.requires_confirmation  # > 10 memories

    @pytest.mark.asyncio
    async def test_preview_with_max_count_limit(self, bulk_manager, sample_memories):
        """Test preview respects max_count limit."""
        filters = BulkDeleteFilters(max_count=50)
        preview = await bulk_manager.preview_deletion(sample_memories, filters)

        # Should limit to 50 even though 150 match
        assert preview.total_matches == 50
        assert len(preview.sample_memories) == 10

    @pytest.mark.asyncio
    async def test_execute_deletion_dry_run(self, bulk_manager, sample_memories):
        """Test dry-run mode doesn't actually delete."""
        filters = BulkDeleteFilters()
        result = await bulk_manager.execute_deletion(
            sample_memories[:10], filters, dry_run=True
        )

        assert isinstance(result, BulkDeleteResult)
        assert result.dry_run is True
        assert result.total_deleted == 0
        assert len(result.failed_deletions) == 0

        # Verify store.delete was never called
        bulk_manager.store.delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_deletion_actual(self, bulk_manager, sample_memories):
        """Test actual deletion."""
        filters = BulkDeleteFilters()
        result = await bulk_manager.execute_deletion(
            sample_memories[:10], filters, dry_run=False
        )

        assert isinstance(result, BulkDeleteResult)
        assert result.dry_run is False
        assert result.total_deleted == 10
        assert len(result.failed_deletions) == 0
        assert result.success is True
        assert result.execution_time >= 0  # May be 0 for very fast execution
        assert result.storage_freed_mb > 0

        # Verify store.delete was called for each memory
        assert bulk_manager.store.delete.call_count == 10

    @pytest.mark.asyncio
    async def test_execute_deletion_with_failures(self, bulk_manager, sample_memories):
        """Test deletion with some failures."""
        # Make delete fail for specific IDs
        async def mock_delete(memory_id: str) -> bool:
            return memory_id != "mem_5"

        bulk_manager.store.delete = AsyncMock(side_effect=mock_delete)

        filters = BulkDeleteFilters()
        result = await bulk_manager.execute_deletion(
            sample_memories[:10], filters, dry_run=False
        )

        assert result.total_deleted == 9  # 10 - 1 failure
        assert len(result.failed_deletions) == 1
        assert "mem_5" in result.failed_deletions
        assert result.success is False  # Has failures
        assert len(result.errors) == 1

    @pytest.mark.asyncio
    async def test_execute_deletion_batch_processing(self, bulk_manager, sample_memories):
        """Test batch processing for large deletions."""
        # Use 150 memories with batch size of 100
        filters = BulkDeleteFilters()
        result = await bulk_manager.execute_deletion(
            sample_memories, filters, dry_run=False
        )

        assert result.total_deleted == 150
        assert bulk_manager.store.delete.call_count == 150

    @pytest.mark.asyncio
    async def test_execute_deletion_progress_callback(
        self, bulk_manager, sample_memories
    ):
        """Test progress callback during deletion."""
        progress_updates = []

        def progress_callback(current: int, total: int, message: str):
            progress_updates.append((current, total, message))

        filters = BulkDeleteFilters()
        await bulk_manager.execute_deletion(
            sample_memories[:10],
            filters,
            dry_run=False,
            progress_callback=progress_callback,
        )

        # Should have 10 progress updates
        assert len(progress_updates) == 10
        assert progress_updates[0] == (1, 10, "Deleted 1/10")
        assert progress_updates[9] == (10, 10, "Deleted 10/10")

    @pytest.mark.asyncio
    async def test_bulk_delete_convenience_method(self, bulk_manager, sample_memories):
        """Test bulk_delete convenience method."""
        filters = BulkDeleteFilters()

        # Dry-run
        preview = await bulk_manager.bulk_delete(
            sample_memories[:10], filters, dry_run=True
        )
        assert isinstance(preview, BulkDeletePreview)

        # Actual deletion
        result = await bulk_manager.bulk_delete(
            sample_memories[:10], filters, dry_run=False
        )
        assert isinstance(result, BulkDeleteResult)
        assert result.total_deleted == 10

    @pytest.mark.asyncio
    async def test_max_count_enforcement(self, bulk_manager):
        """Test that max_count is enforced."""
        # Create 1500 memories
        many_memories = [
            MemoryUnit(
                id=f"mem_{i}",
                content="test",
                category=MemoryCategory.FACT,
                context_level=ContextLevel.SESSION_STATE,
            )
            for i in range(1500)
        ]

        filters = BulkDeleteFilters(max_count=1000)
        result = await bulk_manager.execute_deletion(
            many_memories, filters, dry_run=False
        )

        # Should only delete first 1000
        assert result.total_deleted == 1000

    @pytest.mark.asyncio
    async def test_rollback_id_generation(self, bulk_manager, sample_memories):
        """Test rollback ID generation when enabled."""
        filters = BulkDeleteFilters()
        result = await bulk_manager.execute_deletion(
            sample_memories[:10], filters, dry_run=False, enable_rollback=True
        )

        assert result.rollback_id is not None
        assert result.rollback_id.startswith("rollback_")

    @pytest.mark.asyncio
    async def test_no_rollback_by_default(self, bulk_manager, sample_memories):
        """Test that rollback is disabled by default."""
        filters = BulkDeleteFilters()
        result = await bulk_manager.execute_deletion(
            sample_memories[:10], filters, dry_run=False
        )

        assert result.rollback_id is None
