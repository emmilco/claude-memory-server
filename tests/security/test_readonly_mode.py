"""Tests for read-only mode functionality.

Tests use the centralized unique_qdrant_collection fixture from conftest.py
to prevent Qdrant deadlocks during parallel execution.
"""

import pytest
import pytest_asyncio
from src.config import ServerConfig
from src.store.readonly_wrapper import ReadOnlyStoreWrapper
from src.store.qdrant_store import QdrantMemoryStore
from src.core.models import MemoryUnit, MemoryCategory, MemoryScope, SearchFilters
from src.core.exceptions import ReadOnlyError


@pytest_asyncio.fixture
async def qdrant_store(unique_qdrant_collection):
    """Create a Qdrant store for testing using collection pooling.

    Uses the centralized collection pool from conftest.py which provides
    pre-created collections that are cleared before each test.
    This avoids overwhelming Qdrant with create/delete operations.
    """
    config = ServerConfig(
        storage_backend="qdrant",
        qdrant_url="http://localhost:6333",
        qdrant_collection_name=unique_qdrant_collection,
        advanced={"read_only_mode": False},
    )

    store = QdrantMemoryStore(config)
    await store.initialize()

    yield store

    await store.close()


@pytest_asyncio.fixture
async def readonly_store(qdrant_store):
    """Create a read-only wrapped store."""
    return ReadOnlyStoreWrapper(qdrant_store)


class TestReadOnlyModeBasic:
    """Basic read-only mode tests."""

    @pytest.mark.asyncio
    async def test_readonly_wrapper_creation(self, qdrant_store):
        """Test that ReadOnlyStoreWrapper can be created."""
        wrapper = ReadOnlyStoreWrapper(qdrant_store)
        assert wrapper is not None
        assert wrapper.wrapped_store is qdrant_store

    @pytest.mark.asyncio
    async def test_readonly_wrapper_initialization(self, readonly_store):
        """Test that read-only store can be initialized."""
        await readonly_store.initialize()
        # Should not raise


class TestReadOnlyModeBlocksWrites:
    """Test that write operations are blocked in read-only mode."""

    @pytest.mark.asyncio
    async def test_store_raises_readonly_error(self, readonly_store):
        """Test that store() raises ReadOnlyError."""
        await readonly_store.initialize()

        with pytest.raises(ReadOnlyError) as exc_info:
            await readonly_store.store(
                content="test content",
                embedding=[0.1] * 384,
                metadata={"category": "fact"},
            )

        assert "read-only mode" in str(exc_info.value).lower()
        assert "store" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_delete_raises_readonly_error(self, readonly_store):
        """Test that delete() raises ReadOnlyError."""
        await readonly_store.initialize()

        with pytest.raises(ReadOnlyError) as exc_info:
            await readonly_store.delete("test-id")

        assert "read-only mode" in str(exc_info.value).lower()
        assert "delete" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_batch_store_raises_readonly_error(self, readonly_store):
        """Test that batch_store() raises ReadOnlyError."""
        await readonly_store.initialize()

        items = [
            ("content1", [0.1] * 384, {"category": "fact"}),
            ("content2", [0.2] * 384, {"category": "preference"}),
        ]

        with pytest.raises(ReadOnlyError) as exc_info:
            await readonly_store.batch_store(items)

        assert "read-only mode" in str(exc_info.value).lower()
        assert "batch" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_update_raises_readonly_error(self, readonly_store):
        """Test that update() raises ReadOnlyError."""
        await readonly_store.initialize()

        with pytest.raises(ReadOnlyError) as exc_info:
            await readonly_store.update("test-id", {"importance": 0.9})

        assert "read-only mode" in str(exc_info.value).lower()
        assert "update" in str(exc_info.value).lower()


class TestReadOnlyModeAllowsReads:
    """Test that read operations work in read-only mode."""

    @pytest.mark.asyncio
    async def test_retrieve_works_in_readonly_mode(self, qdrant_store):
        """Test that retrieve() works in read-only mode."""
        # First, add some data to the underlying store
        await qdrant_store.initialize()
        memory_id = await qdrant_store.store(
            content="test content",
            embedding=[0.1] * 384,
            metadata={
                "category": MemoryCategory.FACT.value,
                "context_level": "PROJECT_CONTEXT",
                "scope": MemoryScope.GLOBAL.value,
            },
        )

        # Now wrap it in read-only mode
        readonly = ReadOnlyStoreWrapper(qdrant_store)

        # Retrieve should work
        results = await readonly.retrieve(
            query_embedding=[0.1] * 384,
            limit=5,
        )

        assert len(results) > 0
        # Verify our test content is in the results (but don't assume it's first)
        contents = [r[0].content for r in results]
        assert "test content" in contents

    @pytest.mark.asyncio
    async def test_search_with_filters_works(self, qdrant_store):
        """Test that search_with_filters() works in read-only mode."""
        await qdrant_store.initialize()

        # Add data
        await qdrant_store.store(
            content="preference data",
            embedding=[0.2] * 384,
            metadata={
                "category": MemoryCategory.PREFERENCE.value,
                "context_level": "USER_PREFERENCE",
                "scope": MemoryScope.GLOBAL.value,
            },
        )

        # Wrap in read-only
        readonly = ReadOnlyStoreWrapper(qdrant_store)

        # Search with filters
        filters = SearchFilters(category=MemoryCategory.PREFERENCE)
        results = await readonly.search_with_filters(
            query_embedding=[0.2] * 384,
            filters=filters,
            limit=5,
        )

        assert len(results) > 0

    @pytest.mark.asyncio
    async def test_get_by_id_works(self, qdrant_store):
        """Test that get_by_id() works in read-only mode."""
        await qdrant_store.initialize()

        # Add data
        memory_id = await qdrant_store.store(
            content="test content for get",
            embedding=[0.3] * 384,
            metadata={
                "category": MemoryCategory.FACT.value,
                "context_level": "SESSION_STATE",
                "scope": MemoryScope.GLOBAL.value,
            },
        )

        # Wrap in read-only
        readonly = ReadOnlyStoreWrapper(qdrant_store)

        # Get by ID
        memory = await readonly.get_by_id(memory_id)

        assert memory is not None
        assert memory.content == "test content for get"

    @pytest.mark.asyncio
    async def test_count_works(self, qdrant_store):
        """Test that count() works in read-only mode.

        This test verifies the count() method works correctly by checking
        that we can retrieve a count and that it reflects data operations.
        We don't assert exact counts due to collection pooling in parallel tests.
        """
        await qdrant_store.initialize()

        # Add some data with unique content
        import uuid
        test_id = str(uuid.uuid4())[:8]

        for i in range(3):
            await qdrant_store.store(
                content=f"count_test_{test_id}_{i}",
                embedding=[0.1 * i] * 384,
                metadata={
                    "category": MemoryCategory.FACT.value,
                    "context_level": "PROJECT_CONTEXT",
                    "scope": MemoryScope.GLOBAL.value,
                },
            )

        # Wrap in read-only
        readonly = ReadOnlyStoreWrapper(qdrant_store)

        # Count should work and return a positive number
        count = await readonly.count()
        assert count >= 3  # At least our 3 items should be present

    @pytest.mark.asyncio
    async def test_health_check_works(self, readonly_store):
        """Test that health_check() works in read-only mode."""
        await readonly_store.initialize()

        is_healthy = await readonly_store.health_check()
        assert is_healthy is True


class TestReadOnlyModeErrorMessages:
    """Test that error messages are helpful."""

    @pytest.mark.asyncio
    async def test_store_error_message_is_helpful(self, readonly_store):
        """Test that store error message explains how to enable writes."""
        await readonly_store.initialize()

        with pytest.raises(ReadOnlyError) as exc_info:
            await readonly_store.store("test", [0.1] * 384, {})

        error_msg = str(exc_info.value)
        assert "read-only mode" in error_msg.lower()
        assert "--read-only flag" in error_msg.lower() or "restart" in error_msg.lower()

    @pytest.mark.asyncio
    async def test_delete_error_message_is_helpful(self, readonly_store):
        """Test that delete error message is helpful."""
        await readonly_store.initialize()

        with pytest.raises(ReadOnlyError) as exc_info:
            await readonly_store.delete("test-id")

        error_msg = str(exc_info.value)
        assert "read-only mode" in error_msg.lower()
        assert "restart" in error_msg.lower() or "flag" in error_msg.lower()


class TestReadOnlyModeIntegration:
    """Integration tests for read-only mode."""

    @pytest.mark.asyncio
    async def test_readonly_mode_preserves_existing_data(self, qdrant_store):
        """Test that read-only mode doesn't affect existing data."""
        await qdrant_store.initialize()

        # Add data before wrapping
        original_ids = []
        for i in range(5):
            memory_id = await qdrant_store.store(
                content=f"original content {i}",
                embedding=[0.1 * i] * 384,
                metadata={
                    "category": MemoryCategory.FACT.value,
                    "context_level": "PROJECT_CONTEXT",
                    "scope": MemoryScope.GLOBAL.value,
                },
            )
            original_ids.append(memory_id)

        # Wrap in read-only
        readonly = ReadOnlyStoreWrapper(qdrant_store)

        # Verify all data is still accessible
        for memory_id in original_ids:
            memory = await readonly.get_by_id(memory_id)
            assert memory is not None
            assert "original content" in memory.content

    @pytest.mark.asyncio
    async def test_readonly_wrapper_can_be_closed(self, readonly_store):
        """Test that read-only wrapper can be closed safely."""
        await readonly_store.initialize()

        # Should not raise
        await readonly_store.close()


class TestReadOnlyModeWithConfig:
    """Test read-only mode configuration."""

    def test_readonly_flag_explanation(self):
        """Test that we document how to enable read-only mode."""
        # This is a documentation test
        # Users should be able to start server with --read-only flag
        # or set CLAUDE_RAG_READ_ONLY_MODE=true

        # The config should have read_only_mode setting
        from src.config import ServerConfig

        config = ServerConfig(advanced={"read_only_mode": True})
        assert config.advanced.read_only_mode is True

        config2 = ServerConfig(advanced={"read_only_mode": False})
        assert config2.advanced.read_only_mode is False


# ============================================================================
# Summary
# ============================================================================


