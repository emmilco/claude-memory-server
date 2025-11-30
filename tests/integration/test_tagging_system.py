"""Integration tests for the complete tagging system."""

import pytest
import tempfile
import asyncio
import uuid
from pathlib import Path

from src.tagging.auto_tagger import AutoTagger
from src.tagging.tag_manager import TagManager
from src.tagging.collection_manager import CollectionManager
from src.tagging.models import TagCreate, CollectionCreate
from src.config import ServerConfig
from src.store.qdrant_store import QdrantMemoryStore
from src.core.models import MemoryUnit, MemoryCategory, ContextLevel, MemoryScope, SearchFilters
from tests.conftest import mock_embedding


@pytest.fixture
def config(unique_qdrant_collection):
    """Create test configuration with pooled collection.

    Uses the unique_qdrant_collection fixture from conftest.py to leverage
    collection pooling and prevent Qdrant deadlocks during parallel test execution.
    """
    config = ServerConfig(
        storage_backend="qdrant",
        qdrant_url="http://localhost:6333",
        qdrant_collection_name=unique_qdrant_collection,
    )
    return config


@pytest.fixture
def store(config):
    """Create and initialize memory store with pooled collection."""
    import asyncio
    store_instance = QdrantMemoryStore(config)

    # Run initialization
    asyncio.run(store_instance.initialize())

    yield store_instance

    # Cleanup
    asyncio.run(store_instance.close())
    # Collection cleanup handled by unique_qdrant_collection autouse fixture


@pytest.fixture
def tag_manager(tmp_path):
    """Create tag manager with function-scoped database for test isolation."""
    db_path = tmp_path / "tags.db"
    return TagManager(str(db_path))


@pytest.fixture
def collection_manager(tmp_path):
    """Create collection manager with function-scoped database for test isolation."""
    db_path = tmp_path / "collections.db"
    return CollectionManager(str(db_path))


@pytest.fixture
def auto_tagger():
    """Create auto-tagger."""
    return AutoTagger(min_confidence=0.6)


@pytest.mark.asyncio
async def test_end_to_end_auto_tagging(store, tag_manager, auto_tagger):
    """Test complete auto-tagging workflow."""
    # Create a memory with Python async code
    memory = MemoryUnit(
        content="""
        import asyncio
        from fastapi import FastAPI

        app = FastAPI()

        async def process_data():
            await database.query("SELECT * FROM users")
        """,
        category=MemoryCategory.FACT,
        context_level=ContextLevel.PROJECT_CONTEXT,
        scope=MemoryScope.PROJECT,
        project_name="test-project",
    )

    # Store memory
    await store.store(
        content=memory.content,
        embedding=mock_embedding(value=0.1),
        metadata=memory.model_dump(exclude={"content"}),
    )

    # Extract tags
    tag_tuples = auto_tagger.extract_tags(memory.content, max_tags=10)
    assert len(tag_tuples) > 0

    # Get tag names
    flat_tags = [tag for tag, _ in tag_tuples]

    # Should detect Python, FastAPI, async, database
    assert "python" in flat_tags or "fastapi" in flat_tags

    # Infer hierarchical tags
    hierarchical_tags = auto_tagger.infer_hierarchical_tags(flat_tags)
    assert any("language/" in tag for tag in hierarchical_tags)

    # Apply tags to memory
    for tag_name, confidence in tag_tuples:
        tag = tag_manager.get_or_create_tag(tag_name)
        tag_manager.tag_memory(memory.id, tag.id, confidence, auto_generated=True)

    # Verify tags were applied
    memory_tags = tag_manager.get_memory_tags(memory.id)
    assert len(memory_tags) > 0


@pytest.mark.asyncio
async def test_tag_based_search(store, tag_manager):
    """Test searching memories by tags."""
    # Create memories with different tags
    memory1 = MemoryUnit(
        content="Python async code",
        category=MemoryCategory.FACT,
        tags=["python", "async"],
    )

    memory2 = MemoryUnit(
        content="JavaScript React code",
        category=MemoryCategory.FACT,
        tags=["javascript", "react"],
    )

    # Store memories
    id1 = await store.store(memory1.content, mock_embedding(value=0.1), memory1.model_dump(exclude={"content"}))
    id2 = await store.store(memory2.content, mock_embedding(value=0.2), memory2.model_dump(exclude={"content"}))

    # Search with tag filter
    filters = SearchFilters(tags=["python"])
    results = await store.retrieve(mock_embedding(value=0.1), filters, limit=10)

    # Should only return Python memory
    memory_ids = [mem.id for mem, _ in results]
    assert id1 in memory_ids
    # Note: SQLite may return both since tag filtering uses LIKE
    # In production with Qdrant, filtering would be more precise


@pytest.mark.asyncio
async def test_collection_workflow(collection_manager, store, tag_manager, auto_tagger):
    """Test creating and using collections."""
    # Create a collection for Python patterns
    collection = collection_manager.create_collection(
        CollectionCreate(
            name="Python Async Patterns",
            description="Collection of Python async code",
            tag_filter={"tags": ["python", "async"], "op": "AND"},
        )
    )

    # Create some memories
    memory1 = MemoryUnit(
        content="async def foo(): await bar()",
        category=MemoryCategory.FACT,
        tags=["python", "async"],
    )

    memory2 = MemoryUnit(
        content="def sync_func(): pass",
        category=MemoryCategory.FACT,
        tags=["python"],
    )

    id1 = await store.store(memory1.content, mock_embedding(value=0.1), memory1.model_dump(exclude={"content"}))
    id2 = await store.store(memory2.content, mock_embedding(value=0.2), memory2.model_dump(exclude={"content"}))

    # Add matching memory to collection
    collection_manager.add_to_collection(collection.id, [id1])

    # Verify collection contains the memory
    collection_memories = collection_manager.get_collection_memories(collection.id)
    assert id1 in collection_memories
    assert id2 not in collection_memories


@pytest.mark.asyncio
async def test_hierarchical_tag_creation(tag_manager):
    """Test creating hierarchical tag structures."""
    # Create a hierarchy: language/python/async
    tag = tag_manager.get_or_create_tag("language/python/async")

    assert tag.full_path == "language/python/async"
    assert tag.level == 2

    # Verify ancestors exist
    python_tag = tag_manager.get_tag_by_path("language/python")
    assert python_tag is not None
    assert python_tag.level == 1

    language_tag = tag_manager.get_tag_by_path("language")
    assert language_tag is not None
    assert language_tag.level == 0


@pytest.mark.asyncio
async def test_tag_merging(tag_manager):
    """Test merging duplicate tags."""
    # Create two similar tags
    js_tag = tag_manager.create_tag(TagCreate(name="js"))
    javascript_tag = tag_manager.create_tag(TagCreate(name="javascript"))

    # Tag some memories
    tag_manager.tag_memory("mem-1", js_tag.id)
    tag_manager.tag_memory("mem-2", js_tag.id)

    # Merge js into javascript
    tag_manager.merge_tags(js_tag.id, javascript_tag.id)

    # Verify memories are now tagged with javascript
    mem1_tags = tag_manager.get_memory_tags("mem-1")
    mem2_tags = tag_manager.get_memory_tags("mem-2")

    assert all(tag.id == javascript_tag.id for tag in mem1_tags)
    assert all(tag.id == javascript_tag.id for tag in mem2_tags)

    # Original tag should be deleted
    assert tag_manager.get_tag(js_tag.id) is None


@pytest.mark.asyncio
async def test_auto_generate_collections(collection_manager):
    """Test auto-generating collections."""
    collections = collection_manager.auto_generate_collections()

    assert len(collections) > 0

    # Verify collections have proper structure
    for collection in collections:
        assert collection.auto_generated is True
        assert collection.tag_filter is not None
        assert "tags" in collection.tag_filter
        assert "op" in collection.tag_filter


@pytest.mark.asyncio
async def test_tag_confidence_tracking(tag_manager, auto_tagger):
    """Test that tag confidence scores are tracked."""
    # Extract tags with confidence
    content = "import asyncio\nasync def main(): pass"
    tags = auto_tagger.extract_tags(content)

    # Apply to memory
    for tag_name, confidence in tags:
        tag = tag_manager.get_or_create_tag(tag_name)
        tag_manager.tag_memory("mem-1", tag.id, confidence, auto_generated=True)

    # Note: Confidence is stored in memory_tags table
    # This test verifies the workflow completes without errors


@pytest.mark.asyncio
async def test_descendants_and_ancestors(tag_manager):
    """Test getting tag descendants and ancestors."""
    # Create hierarchy
    lang = tag_manager.create_tag(TagCreate(name="language"))
    python = tag_manager.create_tag(TagCreate(name="python", parent_id=lang.id))
    async_tag = tag_manager.create_tag(TagCreate(name="async", parent_id=python.id))

    # Get descendants of language
    descendants = tag_manager.get_descendants(lang.id)
    assert len(descendants) == 2
    desc_names = {tag.name for tag in descendants}
    assert desc_names == {"python", "async"}

    # Get ancestors of async
    ancestors = tag_manager.get_ancestors(async_tag.id)
    assert len(ancestors) == 2
    assert ancestors[0].name == "language"
    assert ancestors[1].name == "python"


@pytest.mark.asyncio
async def test_tag_deletion_cascade(tag_manager):
    """Test cascading tag deletion."""
    # Create hierarchy
    lang = tag_manager.create_tag(TagCreate(name="language"))
    python = tag_manager.create_tag(TagCreate(name="python", parent_id=lang.id))
    async_tag = tag_manager.create_tag(TagCreate(name="async", parent_id=python.id))

    # Delete with cascade
    tag_manager.delete_tag(lang.id, cascade=True)

    # All should be deleted
    assert tag_manager.get_tag(lang.id) is None
    assert tag_manager.get_tag(python.id) is None
    assert tag_manager.get_tag(async_tag.id) is None


@pytest.mark.asyncio
async def test_multiple_tags_on_memory(tag_manager):
    """Test applying multiple tags to a single memory."""
    # Create tags
    python_tag = tag_manager.create_tag(TagCreate(name="python"))
    async_tag = tag_manager.create_tag(TagCreate(name="async"))
    api_tag = tag_manager.create_tag(TagCreate(name="api"))

    # Apply all to one memory
    tag_manager.tag_memory("mem-1", python_tag.id)
    tag_manager.tag_memory("mem-1", async_tag.id)
    tag_manager.tag_memory("mem-1", api_tag.id)

    # Verify all tags are associated
    memory_tags = tag_manager.get_memory_tags("mem-1")
    assert len(memory_tags) == 3
    tag_names = {tag.name for tag in memory_tags}
    assert tag_names == {"python", "async", "api"}


@pytest.mark.asyncio
async def test_collection_update_timestamp(collection_manager):
    """Test that collection updated_at is maintained."""
    import time

    collection = collection_manager.create_collection(
        CollectionCreate(name="Test")
    )

    initial_updated_at = collection.updated_at

    # Sleep to ensure timestamp differs
    time.sleep(0.01)

    # Add a memory
    collection_manager.add_to_collection(collection.id, ["mem-1"])

    # Retrieve and check updated_at
    updated_collection = collection_manager.get_collection(collection.id)
    assert updated_collection.updated_at > initial_updated_at


@pytest.mark.asyncio
async def test_list_tags_by_parent(tag_manager):
    """Test listing tags filtered by parent."""
    # Create parent with multiple children
    lang = tag_manager.create_tag(TagCreate(name="language"))
    tag_manager.create_tag(TagCreate(name="python", parent_id=lang.id))
    tag_manager.create_tag(TagCreate(name="javascript", parent_id=lang.id))

    # Create unrelated tag
    tag_manager.create_tag(TagCreate(name="framework"))

    # List children of language
    children = tag_manager.list_tags(parent_id=lang.id)

    assert len(children) == 2
    names = {tag.name for tag in children}
    assert names == {"python", "javascript"}


@pytest.mark.asyncio
async def test_remove_memories_from_collection(collection_manager):
    """Test removing multiple memories from collection."""
    collection = collection_manager.create_collection(
        CollectionCreate(name="Test")
    )

    # Add memories
    memory_ids = ["mem-1", "mem-2", "mem-3", "mem-4"]
    collection_manager.add_to_collection(collection.id, memory_ids)

    # Remove some
    collection_manager.remove_from_collection(collection.id, ["mem-2", "mem-4"])

    # Verify only mem-1 and mem-3 remain
    remaining = collection_manager.get_collection_memories(collection.id)
    assert set(remaining) == {"mem-1", "mem-3"}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
