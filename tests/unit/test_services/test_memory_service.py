"""Tests for MemoryService - Core memory CRUD and lifecycle management.

This test suite covers:
- Memory storage with auto-classification
- Memory retrieval with semantic search
- Memory deletion and updates
- Memory listing with filters
- Import/export functionality
- Duplicate detection and merging
- Context-level classification
- Error handling
"""

import pytest
from datetime import datetime, timedelta, UTC
from unittest.mock import AsyncMock, MagicMock, patch
import json

from src.services.memory_service import MemoryService
from src.config import ServerConfig
from src.core.models import (
    MemoryUnit,
    MemoryCategory,
    ContextLevel,
    MemoryScope,
)
from src.core.exceptions import (
    StorageError,
    ValidationError,
    ReadOnlyError,
    RetrievalError,
)


def create_test_memory(
    id: str = "mem_123",
    content: str = "Test content",
    category: MemoryCategory = MemoryCategory.FACT,
    context_level: ContextLevel = ContextLevel.PROJECT_CONTEXT,
    scope: MemoryScope = MemoryScope.GLOBAL,
    importance: float = 0.5,
    tags: list = None,
    metadata: dict = None,
    project_name: str = None,
) -> MemoryUnit:
    """Create a test MemoryUnit with sensible defaults."""
    return MemoryUnit(
        id=id,
        content=content,
        category=category,
        context_level=context_level,
        scope=scope,
        importance=importance,
        tags=tags or [],
        metadata=metadata or {},
        project_name=project_name,
    )


class TestMemoryServiceInit:
    """Test MemoryService initialization."""

    def test_initialization_with_required_dependencies(self):
        """Test service initializes with required dependencies."""
        store = MagicMock()
        embedding_generator = MagicMock()
        embedding_cache = MagicMock()
        config = ServerConfig()

        service = MemoryService(
            store=store,
            embedding_generator=embedding_generator,
            embedding_cache=embedding_cache,
            config=config,
        )

        assert service.store == store
        assert service.embedding_generator == embedding_generator
        assert service.embedding_cache == embedding_cache
        assert service.config == config

    def test_initialization_with_all_optional_dependencies(self):
        """Test service initializes with all optional dependencies."""
        store = MagicMock()
        embedding_generator = MagicMock()
        embedding_cache = MagicMock()
        config = ServerConfig()
        usage_tracker = MagicMock()
        conversation_tracker = MagicMock()
        query_expander = MagicMock()
        metrics_collector = MagicMock()

        service = MemoryService(
            store=store,
            embedding_generator=embedding_generator,
            embedding_cache=embedding_cache,
            config=config,
            usage_tracker=usage_tracker,
            conversation_tracker=conversation_tracker,
            query_expander=query_expander,
            metrics_collector=metrics_collector,
            project_name="test-project",
        )

        assert service.usage_tracker == usage_tracker
        assert service.conversation_tracker == conversation_tracker
        assert service.query_expander == query_expander
        assert service.metrics_collector == metrics_collector
        assert service.project_name == "test-project"

    def test_initial_stats_are_zero(self):
        """Test service stats start at zero."""
        service = MemoryService(
            store=MagicMock(),
            embedding_generator=MagicMock(),
            embedding_cache=MagicMock(),
            config=ServerConfig(),
        )

        stats = service.get_stats()
        assert stats["memories_stored"] == 0
        assert stats["memories_retrieved"] == 0
        assert stats["memories_deleted"] == 0
        assert stats["queries_processed"] == 0


class TestContextLevelClassification:
    """Test context-level auto-classification."""

    @pytest.fixture
    def service(self):
        """Create service instance for classification tests."""
        return MemoryService(
            store=MagicMock(),
            embedding_generator=MagicMock(),
            embedding_cache=MagicMock(),
            config=ServerConfig(),
        )

    def test_classify_preference_category(self, service):
        """Test preference category yields USER_PREFERENCE level."""
        result = service._classify_context_level(
            content="Some content",
            category=MemoryCategory.PREFERENCE
        )
        assert result == ContextLevel.USER_PREFERENCE

    def test_classify_preference_keywords(self, service):
        """Test preference keywords yield USER_PREFERENCE level."""
        test_cases = [
            "I prefer dark mode",
            "I like tabs over spaces",
            "I dislike verbose logging",
            "Always use type hints",
            "Never use global variables",
            "My coding style is functional",
        ]
        for content in test_cases:
            result = service._classify_context_level(
                content=content,
                category=MemoryCategory.FACT
            )
            assert result == ContextLevel.USER_PREFERENCE, f"Failed for: {content}"

    def test_classify_session_state_keywords(self, service):
        """Test session state keywords yield SESSION_STATE level."""
        test_cases = [
            "Currently working on authentication",
            "Working on the API module",
            "In progress: test refactoring",
            "Debugging the login issue",
            "Fixing the memory leak",
        ]
        for content in test_cases:
            result = service._classify_context_level(
                content=content,
                category=MemoryCategory.FACT
            )
            assert result == ContextLevel.SESSION_STATE, f"Failed for: {content}"

    def test_classify_default_to_project_context(self, service):
        """Test default classification is PROJECT_CONTEXT."""
        result = service._classify_context_level(
            content="The database uses PostgreSQL",
            category=MemoryCategory.FACT
        )
        assert result == ContextLevel.PROJECT_CONTEXT


class TestDateFilterParsing:
    """Test date filter string parsing."""

    @pytest.fixture
    def service(self):
        """Create service instance for date parsing tests."""
        return MemoryService(
            store=MagicMock(),
            embedding_generator=MagicMock(),
            embedding_cache=MagicMock(),
            config=ServerConfig(),
        )

    def test_parse_today(self, service):
        """Test parsing 'today' returns current time."""
        result = service._parse_date_filter("today")
        now = datetime.now(UTC)
        assert abs((result - now).total_seconds()) < 2

    def test_parse_yesterday(self, service):
        """Test parsing 'yesterday' returns yesterday."""
        result = service._parse_date_filter("yesterday")
        expected = datetime.now(UTC) - timedelta(days=1)
        assert abs((result - expected).total_seconds()) < 2

    def test_parse_last_week(self, service):
        """Test parsing 'last week' returns 7 days ago."""
        result = service._parse_date_filter("last week")
        expected = datetime.now(UTC) - timedelta(weeks=1)
        assert abs((result - expected).total_seconds()) < 2

    def test_parse_relative_days(self, service):
        """Test parsing 'N days ago' patterns."""
        result = service._parse_date_filter("5 days ago")
        expected = datetime.now(UTC) - timedelta(days=5)
        assert abs((result - expected).total_seconds()) < 2

    def test_parse_relative_weeks(self, service):
        """Test parsing 'N weeks ago' patterns."""
        result = service._parse_date_filter("2 weeks ago")
        expected = datetime.now(UTC) - timedelta(weeks=2)
        assert abs((result - expected).total_seconds()) < 2

    def test_parse_iso_format(self, service):
        """Test parsing ISO date format."""
        result = service._parse_date_filter("2024-01-15")
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15

    def test_parse_invalid_format_raises(self, service):
        """Test invalid format raises ValidationError."""
        with pytest.raises(ValidationError):
            service._parse_date_filter("invalid-date-format")


class TestStoreMemory:
    """Test memory storage operations."""

    @pytest.fixture
    def service(self):
        """Create service instance with mocked dependencies."""
        store = AsyncMock()
        store.store = AsyncMock(return_value="mem_123")

        embedding_generator = AsyncMock()
        embedding_generator.generate = AsyncMock(return_value=[0.1] * 384)

        embedding_cache = AsyncMock()
        embedding_cache.get = AsyncMock(return_value=None)
        embedding_cache.set = AsyncMock()

        config = ServerConfig()

        return MemoryService(
            store=store,
            embedding_generator=embedding_generator,
            embedding_cache=embedding_cache,
            config=config,
        )

    @pytest.mark.asyncio
    async def test_store_memory_success(self, service):
        """Test storing a memory successfully."""
        result = await service.store_memory(
            content="Test memory content",
            category="fact",
            scope="global",
            importance=0.7,
            tags=["test"],
        )

        assert result["status"] == "success"
        assert result["memory_id"] == "mem_123"
        assert "context_level" in result

    @pytest.mark.asyncio
    async def test_store_memory_auto_classifies_context(self, service):
        """Test memory storage auto-classifies context level."""
        result = await service.store_memory(
            content="I prefer using TypeScript",
            category="preference",
        )

        assert result["context_level"] == "USER_PREFERENCE"

    @pytest.mark.asyncio
    async def test_store_memory_uses_provided_context_level(self, service):
        """Test memory storage uses explicitly provided context level."""
        result = await service.store_memory(
            content="Some content",
            category="fact",
            context_level="SESSION_STATE",
        )

        assert result["context_level"] == "SESSION_STATE"

    @pytest.mark.asyncio
    async def test_store_memory_increments_stats(self, service):
        """Test storing memory increments statistics."""
        initial_stats = service.get_stats()
        await service.store_memory(content="Test", category="fact")

        stats = service.get_stats()
        assert stats["memories_stored"] == initial_stats["memories_stored"] + 1

    @pytest.mark.asyncio
    async def test_store_memory_uses_cache(self, service):
        """Test embedding cache is checked before generation."""
        service.embedding_cache.get = AsyncMock(return_value=[0.2] * 384)

        await service.store_memory(content="Cached content", category="fact")

        service.embedding_cache.get.assert_called_once()
        # Embedding generator should not be called since cache hit
        service.embedding_generator.generate.assert_not_called()

    @pytest.mark.asyncio
    async def test_store_memory_read_only_mode_raises(self, service):
        """Test storing in read-only mode raises ReadOnlyError."""
        service.config.advanced.read_only_mode = True

        with pytest.raises(ReadOnlyError):
            await service.store_memory(content="Test", category="fact")

    @pytest.mark.asyncio
    async def test_store_memory_invalid_category_raises(self, service):
        """Test invalid category raises StorageError."""
        with pytest.raises(StorageError):
            await service.store_memory(
                content="Test",
                category="invalid_category",
            )


class TestRetrieveMemories:
    """Test memory retrieval operations."""

    @pytest.fixture
    def service(self):
        """Create service instance with mocked dependencies."""
        # Create real MemoryUnit instance
        test_memory = create_test_memory()

        store = AsyncMock()
        store.retrieve = AsyncMock(return_value=[(test_memory, 0.85)])

        embedding_generator = AsyncMock()
        embedding_generator.generate = AsyncMock(return_value=[0.1] * 384)

        embedding_cache = AsyncMock()
        embedding_cache.get = AsyncMock(return_value=None)
        embedding_cache.set = AsyncMock()

        config = ServerConfig()

        return MemoryService(
            store=store,
            embedding_generator=embedding_generator,
            embedding_cache=embedding_cache,
            config=config,
        )

    @pytest.mark.asyncio
    async def test_retrieve_memories_success(self, service):
        """Test retrieving memories returns results."""
        result = await service.retrieve_memories(
            query="test query",
            limit=5,
        )

        assert "results" in result
        assert "total_found" in result
        assert "query_time_ms" in result
        assert result["total_found"] == 1

    @pytest.mark.asyncio
    async def test_retrieve_memories_with_filters(self, service):
        """Test retrieval with various filters."""
        await service.retrieve_memories(
            query="test",
            context_level="PROJECT_CONTEXT",
            scope="global",
            category="fact",
            min_importance=0.3,
        )

        service.store.retrieve.assert_called_once()

    @pytest.mark.asyncio
    async def test_retrieve_memories_increments_stats(self, service):
        """Test retrieval increments statistics."""
        initial_stats = service.get_stats()
        await service.retrieve_memories(query="test")

        stats = service.get_stats()
        assert stats["queries_processed"] == initial_stats["queries_processed"] + 1

    @pytest.mark.asyncio
    async def test_retrieve_memories_with_session_deduplication(self, service):
        """Test retrieval with session-based deduplication."""
        conversation_tracker = MagicMock()
        conversation_tracker.get_shown_memory_ids.return_value = {"mem_old"}
        conversation_tracker.get_recent_queries.return_value = []
        conversation_tracker.track_query = MagicMock()
        conversation_tracker.track_shown_memories = MagicMock()

        service.conversation_tracker = conversation_tracker
        service.config.deduplication_fetch_multiplier = 2

        result = await service.retrieve_memories(
            query="test",
            session_id="session_123",
        )

        # Should still get results
        assert "results" in result


class TestDeleteMemory:
    """Test memory deletion operations."""

    @pytest.fixture
    def service(self):
        """Create service instance for deletion tests."""
        store = AsyncMock()
        store.delete = AsyncMock(return_value=True)

        return MemoryService(
            store=store,
            embedding_generator=AsyncMock(),
            embedding_cache=AsyncMock(),
            config=ServerConfig(),
        )

    @pytest.mark.asyncio
    async def test_delete_memory_success(self, service):
        """Test deleting a memory successfully."""
        result = await service.delete_memory("mem_123")

        assert result["status"] == "success"
        assert result["memory_id"] == "mem_123"

    @pytest.mark.asyncio
    async def test_delete_memory_not_found(self, service):
        """Test deleting non-existent memory returns not_found."""
        service.store.delete = AsyncMock(return_value=False)

        result = await service.delete_memory("nonexistent")

        assert result["status"] == "not_found"

    @pytest.mark.asyncio
    async def test_delete_memory_increments_stats(self, service):
        """Test deletion increments statistics."""
        initial_stats = service.get_stats()
        await service.delete_memory("mem_123")

        stats = service.get_stats()
        assert stats["memories_deleted"] == initial_stats["memories_deleted"] + 1

    @pytest.mark.asyncio
    async def test_delete_memory_read_only_raises(self, service):
        """Test deletion in read-only mode raises ReadOnlyError."""
        service.config.advanced.read_only_mode = True

        with pytest.raises(ReadOnlyError):
            await service.delete_memory("mem_123")


class TestGetMemoryById:
    """Test getting memory by ID."""

    @pytest.fixture
    def service(self):
        """Create service instance for get by ID tests."""
        test_memory = create_test_memory(
            tags=["tag1"],
            metadata={"key": "value"},
            project_name="test-project",
        )

        store = AsyncMock()
        store.get_by_id = AsyncMock(return_value=test_memory)

        return MemoryService(
            store=store,
            embedding_generator=AsyncMock(),
            embedding_cache=AsyncMock(),
            config=ServerConfig(),
        )

    @pytest.mark.asyncio
    async def test_get_memory_by_id_success(self, service):
        """Test getting memory by ID successfully."""
        result = await service.get_memory_by_id("mem_123")

        assert result["status"] == "success"
        assert result["memory"]["id"] == "mem_123"
        assert result["memory"]["content"] == "Test content"

    @pytest.mark.asyncio
    async def test_get_memory_by_id_not_found(self, service):
        """Test getting non-existent memory returns not_found."""
        service.store.get_by_id = AsyncMock(return_value=None)

        result = await service.get_memory_by_id("nonexistent")

        assert result["status"] == "not_found"


class TestUpdateMemory:
    """Test memory update operations."""

    @pytest.fixture
    def service(self):
        """Create service instance for update tests."""
        store = AsyncMock()
        store.update = AsyncMock(return_value=True)

        embedding_generator = AsyncMock()
        embedding_generator.generate = AsyncMock(return_value=[0.1] * 384)

        return MemoryService(
            store=store,
            embedding_generator=embedding_generator,
            embedding_cache=AsyncMock(),
            config=ServerConfig(),
        )

    @pytest.mark.asyncio
    async def test_update_memory_content(self, service):
        """Test updating memory content."""
        result = await service.update_memory(
            memory_id="mem_123",
            content="Updated content",
        )

        assert result["status"] == "updated"
        assert "content" in result["updated_fields"]
        assert result["embedding_regenerated"] is True

    @pytest.mark.asyncio
    async def test_update_memory_metadata_only(self, service):
        """Test updating only metadata does not regenerate embedding."""
        result = await service.update_memory(
            memory_id="mem_123",
            importance=0.9,
        )

        assert result["status"] == "updated"
        assert "importance" in result["updated_fields"]
        assert result["embedding_regenerated"] is False

    @pytest.mark.asyncio
    async def test_update_memory_not_found(self, service):
        """Test updating non-existent memory returns not_found."""
        service.store.update = AsyncMock(return_value=False)

        result = await service.update_memory(
            memory_id="nonexistent",
            content="New content",
        )

        assert result["status"] == "not_found"

    @pytest.mark.asyncio
    async def test_update_memory_no_fields_raises(self, service):
        """Test update with no fields raises ValidationError."""
        with pytest.raises(ValidationError):
            await service.update_memory(memory_id="mem_123")

    @pytest.mark.asyncio
    async def test_update_memory_invalid_importance_raises(self, service):
        """Test invalid importance value raises ValidationError."""
        with pytest.raises(ValidationError):
            await service.update_memory(
                memory_id="mem_123",
                importance=1.5,  # Out of range
            )

    @pytest.mark.asyncio
    async def test_update_memory_read_only_raises(self, service):
        """Test update in read-only mode raises ReadOnlyError."""
        service.config.advanced.read_only_mode = True

        with pytest.raises(ReadOnlyError):
            await service.update_memory(
                memory_id="mem_123",
                content="New content",
            )


class TestListMemories:
    """Test memory listing operations."""

    @pytest.fixture
    def service(self):
        """Create service instance for list tests."""
        test_memory = create_test_memory()

        store = AsyncMock()
        store.list_memories = AsyncMock(return_value=([test_memory], 1))

        return MemoryService(
            store=store,
            embedding_generator=AsyncMock(),
            embedding_cache=AsyncMock(),
            config=ServerConfig(),
        )

    @pytest.mark.asyncio
    async def test_list_memories_default(self, service):
        """Test listing memories with defaults."""
        result = await service.list_memories()

        assert "memories" in result
        assert "total_count" in result
        assert "returned_count" in result
        assert "has_more" in result
        assert result["returned_count"] == 1

    @pytest.mark.asyncio
    async def test_list_memories_with_filters(self, service):
        """Test listing memories with filters."""
        result = await service.list_memories(
            category="fact",
            context_level="PROJECT_CONTEXT",
            min_importance=0.3,
            max_importance=0.8,
        )

        assert result["returned_count"] == 1

    @pytest.mark.asyncio
    async def test_list_memories_pagination(self, service):
        """Test listing with pagination."""
        result = await service.list_memories(
            limit=10,
            offset=5,
        )

        assert result["limit"] == 10
        assert result["offset"] == 5

    @pytest.mark.asyncio
    async def test_list_memories_invalid_limit_raises(self, service):
        """Test invalid limit raises ValidationError."""
        with pytest.raises(ValidationError):
            await service.list_memories(limit=200)  # > 100

    @pytest.mark.asyncio
    async def test_list_memories_invalid_sort_raises(self, service):
        """Test invalid sort field raises ValidationError."""
        with pytest.raises(ValidationError):
            await service.list_memories(sort_by="invalid_field")


class TestMigrateMemoryScope:
    """Test memory scope migration."""

    @pytest.fixture
    def service(self):
        """Create service instance for migration tests."""
        store = AsyncMock()
        store.migrate_memory_scope = AsyncMock(return_value=True)

        return MemoryService(
            store=store,
            embedding_generator=AsyncMock(),
            embedding_cache=AsyncMock(),
            config=ServerConfig(),
        )

    @pytest.mark.asyncio
    async def test_migrate_to_project_scope(self, service):
        """Test migrating memory to project scope."""
        result = await service.migrate_memory_scope(
            memory_id="mem_123",
            new_project_name="new-project",
        )

        assert result["status"] == "success"
        assert result["project_name"] == "new-project"

    @pytest.mark.asyncio
    async def test_migrate_to_global_scope(self, service):
        """Test migrating memory to global scope."""
        result = await service.migrate_memory_scope(
            memory_id="mem_123",
            new_project_name=None,
        )

        assert result["status"] == "success"
        assert result["scope"] == "global"

    @pytest.mark.asyncio
    async def test_migrate_not_found(self, service):
        """Test migrating non-existent memory returns not_found."""
        service.store.migrate_memory_scope = AsyncMock(return_value=False)

        result = await service.migrate_memory_scope(
            memory_id="nonexistent",
            new_project_name="project",
        )

        assert result["status"] == "not_found"


class TestBulkReclassify:
    """Test bulk memory reclassification."""

    @pytest.fixture
    def service(self):
        """Create service instance for bulk reclassify tests."""
        store = AsyncMock()
        store.bulk_update_context_level = AsyncMock(return_value=5)

        return MemoryService(
            store=store,
            embedding_generator=AsyncMock(),
            embedding_cache=AsyncMock(),
            config=ServerConfig(),
        )

    @pytest.mark.asyncio
    async def test_bulk_reclassify_success(self, service):
        """Test bulk reclassification succeeds."""
        result = await service.bulk_reclassify(
            new_context_level="USER_PREFERENCE",
            project_name="test-project",
        )

        assert result["status"] == "success"
        assert result["count"] == 5
        assert result["new_context_level"] == "USER_PREFERENCE"

    @pytest.mark.asyncio
    async def test_bulk_reclassify_read_only_raises(self, service):
        """Test bulk reclassify in read-only mode raises."""
        service.config.advanced.read_only_mode = True

        with pytest.raises(ReadOnlyError):
            await service.bulk_reclassify(new_context_level="SESSION_STATE")


class TestFindDuplicateMemories:
    """Test duplicate memory detection."""

    @pytest.fixture
    def service(self):
        """Create service instance for duplicate detection tests."""
        store = AsyncMock()
        store.find_duplicate_memories = AsyncMock(return_value=[
            {"group_id": 1, "memories": ["mem_1", "mem_2"]},
        ])

        return MemoryService(
            store=store,
            embedding_generator=AsyncMock(),
            embedding_cache=AsyncMock(),
            config=ServerConfig(),
        )

    @pytest.mark.asyncio
    async def test_find_duplicates_success(self, service):
        """Test finding duplicate memories."""
        result = await service.find_duplicate_memories(
            similarity_threshold=0.95,
        )

        assert result["status"] == "success"
        assert result["total_groups"] == 1
        assert len(result["duplicate_groups"]) == 1


class TestMergeMemories:
    """Test memory merging."""

    @pytest.fixture
    def service(self):
        """Create service instance for merge tests."""
        store = AsyncMock()
        store.merge_memories = AsyncMock(return_value="merged_mem")

        return MemoryService(
            store=store,
            embedding_generator=AsyncMock(),
            embedding_cache=AsyncMock(),
            config=ServerConfig(),
        )

    @pytest.mark.asyncio
    async def test_merge_memories_success(self, service):
        """Test merging memories successfully."""
        result = await service.merge_memories(
            memory_ids=["mem_1", "mem_2", "mem_3"],
            keep_id="mem_1",
        )

        assert result["status"] == "success"
        assert result["merged_id"] == "merged_mem"
        assert result["count"] == 3

    @pytest.mark.asyncio
    async def test_merge_memories_insufficient_raises(self, service):
        """Test merging < 2 memories raises ValidationError."""
        with pytest.raises(ValidationError):
            await service.merge_memories(memory_ids=["mem_1"])


class TestExportMemories:
    """Test memory export functionality."""

    @pytest.fixture
    def service(self):
        """Create service instance for export tests."""
        test_memory = create_test_memory()

        store = AsyncMock()
        store.list_memories = AsyncMock(return_value=([test_memory], 1))

        return MemoryService(
            store=store,
            embedding_generator=AsyncMock(),
            embedding_cache=AsyncMock(),
            config=ServerConfig(),
        )

    @pytest.mark.asyncio
    async def test_export_json_to_string(self, service):
        """Test exporting memories as JSON string."""
        result = await service.export_memories(format="json")

        assert result["status"] == "success"
        assert result["format"] == "json"
        assert result["count"] == 1
        assert "content" in result

        # Verify JSON is valid
        data = json.loads(result["content"])
        assert "memories" in data

    @pytest.mark.asyncio
    async def test_export_markdown_to_string(self, service):
        """Test exporting memories as Markdown string."""
        result = await service.export_memories(format="markdown")

        assert result["status"] == "success"
        assert result["format"] == "markdown"
        assert "# Memory Export" in result["content"]

    @pytest.mark.asyncio
    async def test_export_json_to_file(self, service, tmp_path):
        """Test exporting memories to JSON file."""
        output_path = str(tmp_path / "export.json")

        result = await service.export_memories(
            format="json",
            output_path=output_path,
        )

        assert result["status"] == "success"
        assert result["file_path"] == output_path

    @pytest.mark.asyncio
    async def test_export_invalid_format_raises(self, service):
        """Test invalid format raises ValidationError."""
        with pytest.raises(ValidationError):
            await service.export_memories(format="xml")


class TestImportMemories:
    """Test memory import functionality."""

    @pytest.fixture
    def service(self):
        """Create service instance for import tests."""
        store = AsyncMock()
        store.get_by_id = AsyncMock(return_value=None)  # No existing memories
        store.store = AsyncMock(return_value="new_mem")

        embedding_generator = AsyncMock()
        embedding_generator.generate = AsyncMock(return_value=[0.1] * 384)

        return MemoryService(
            store=store,
            embedding_generator=embedding_generator,
            embedding_cache=AsyncMock(),
            config=ServerConfig(),
        )

    @pytest.mark.asyncio
    async def test_import_from_content(self, service):
        """Test importing memories from JSON content."""
        import_data = {
            "memories": [
                {
                    "memory_id": "import_1",
                    "content": "Imported memory",
                    "category": "fact",
                }
            ]
        }

        result = await service.import_memories(
            content=json.dumps(import_data),
        )

        assert result["status"] == "success"
        assert result["created"] == 1

    @pytest.mark.asyncio
    async def test_import_skip_existing(self, service):
        """Test importing with skip conflict mode."""
        service.store.get_by_id = AsyncMock(return_value=MagicMock())  # Exists

        import_data = {
            "memories": [
                {"memory_id": "existing", "content": "Test"}
            ]
        }

        result = await service.import_memories(
            content=json.dumps(import_data),
            conflict_mode="skip",
        )

        assert result["skipped"] == 1
        assert result["created"] == 0

    @pytest.mark.asyncio
    async def test_import_invalid_json_raises(self, service):
        """Test invalid JSON raises ValidationError."""
        with pytest.raises(ValidationError):
            await service.import_memories(content="not valid json")

    @pytest.mark.asyncio
    async def test_import_missing_file_raises(self, service):
        """Test missing file raises ValidationError."""
        with pytest.raises(ValidationError):
            await service.import_memories(file_path="/nonexistent/path.json")

    @pytest.mark.asyncio
    async def test_import_no_source_raises(self, service):
        """Test import without file or content raises ValidationError."""
        with pytest.raises(ValidationError):
            await service.import_memories()


class TestSpecializedRetrieval:
    """Test specialized retrieval methods."""

    @pytest.fixture
    def service(self):
        """Create service instance for specialized retrieval tests."""
        test_memory = create_test_memory(
            category=MemoryCategory.PREFERENCE,
            context_level=ContextLevel.USER_PREFERENCE,
        )

        store = AsyncMock()
        store.retrieve = AsyncMock(return_value=[(test_memory, 0.85)])

        embedding_generator = AsyncMock()
        embedding_generator.generate = AsyncMock(return_value=[0.1] * 384)

        embedding_cache = AsyncMock()
        embedding_cache.get = AsyncMock(return_value=None)
        embedding_cache.set = AsyncMock()

        return MemoryService(
            store=store,
            embedding_generator=embedding_generator,
            embedding_cache=embedding_cache,
            config=ServerConfig(),
            project_name="test-project",
        )

    @pytest.mark.asyncio
    async def test_retrieve_preferences(self, service):
        """Test retrieving user preferences."""
        result = await service.retrieve_preferences(query="coding style")

        assert "results" in result
        # Verify USER_PREFERENCE context level is used

    @pytest.mark.asyncio
    async def test_retrieve_project_context(self, service):
        """Test retrieving project context."""
        result = await service.retrieve_project_context(
            query="database setup",
            use_current_project=True,
        )

        assert "results" in result

    @pytest.mark.asyncio
    async def test_retrieve_session_state(self, service):
        """Test retrieving session state."""
        result = await service.retrieve_session_state(query="current task")

        assert "results" in result


class TestDashboardStats:
    """Test dashboard statistics."""

    @pytest.fixture
    def service(self):
        """Create service instance for dashboard stats tests."""
        store = AsyncMock()
        store.count = AsyncMock(return_value=100)
        store.get_all_projects = AsyncMock(return_value=["project1", "project2"])
        store.get_project_stats = AsyncMock(return_value={
            "project_name": "project1",
            "memory_count": 50,
            "categories": {"fact": 30, "preference": 20},
            "lifecycle_states": {"active": 40, "archived": 10},
        })

        return MemoryService(
            store=store,
            embedding_generator=AsyncMock(),
            embedding_cache=AsyncMock(),
            config=ServerConfig(),
        )

    @pytest.mark.asyncio
    async def test_get_dashboard_stats(self, service):
        """Test getting dashboard statistics."""
        result = await service.get_dashboard_stats()

        assert result["status"] == "success"
        assert result["total_memories"] == 100
        assert result["num_projects"] == 2


class TestRecentActivity:
    """Test recent activity retrieval."""

    @pytest.fixture
    def service(self):
        """Create service instance for recent activity tests."""
        store = AsyncMock()
        store.get_recent_activity = AsyncMock(return_value={
            "recent_searches": [],
            "recent_additions": [],
        })

        return MemoryService(
            store=store,
            embedding_generator=AsyncMock(),
            embedding_cache=AsyncMock(),
            config=ServerConfig(),
        )

    @pytest.mark.asyncio
    async def test_get_recent_activity(self, service):
        """Test getting recent activity."""
        result = await service.get_recent_activity(limit=10)

        assert result["status"] == "success"


class TestEmbeddingCaching:
    """Test embedding cache behavior."""

    @pytest.fixture
    def service(self):
        """Create service instance for cache tests."""
        embedding_cache = AsyncMock()
        embedding_cache.get = AsyncMock(return_value=None)
        embedding_cache.set = AsyncMock()

        embedding_generator = AsyncMock()
        embedding_generator.generate = AsyncMock(return_value=[0.1] * 384)

        return MemoryService(
            store=AsyncMock(),
            embedding_generator=embedding_generator,
            embedding_cache=embedding_cache,
            config=ServerConfig(),
        )

    @pytest.mark.asyncio
    async def test_cache_miss_generates_and_caches(self, service):
        """Test cache miss generates embedding and stores in cache."""
        service.embedding_cache.get = AsyncMock(return_value=None)

        result = await service._get_embedding("test text")

        service.embedding_cache.get.assert_called_once()
        service.embedding_generator.generate.assert_called_once()
        service.embedding_cache.set.assert_called_once()
        assert service.stats["cache_misses"] == 1

    @pytest.mark.asyncio
    async def test_cache_hit_returns_cached(self, service):
        """Test cache hit returns cached embedding."""
        cached_embedding = [0.2] * 384
        service.embedding_cache.get = AsyncMock(return_value=cached_embedding)

        result = await service._get_embedding("cached text")

        service.embedding_cache.get.assert_called_once()
        service.embedding_generator.generate.assert_not_called()
        assert result == cached_embedding
        assert service.stats["cache_hits"] == 1
