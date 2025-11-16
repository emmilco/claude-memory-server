"""Integration tests for Qdrant store."""

import pytest
import pytest_asyncio
import asyncio
from typing import List

from src.config import ServerConfig
from src.store.qdrant_store import QdrantMemoryStore
from src.core.models import (
    MemoryCategory,
    ContextLevel,
    MemoryScope,
    SearchFilters,
)


@pytest.fixture
def config():
    """Create test configuration."""
    return ServerConfig(
        qdrant_url="http://localhost:6333",
        qdrant_collection_name="test_memory",
    )


@pytest_asyncio.fixture
async def store(config):
    """Create and initialize Qdrant store."""
    test_store = QdrantMemoryStore(config)
    await test_store.initialize()

    # Clean up any existing test data
    try:
        test_store.client.delete_collection("test_memory")
    except:
        pass

    # Reinitialize with clean collection
    await test_store.initialize()

    yield test_store

    # Cleanup after test
    await test_store.close()


@pytest.mark.asyncio
async def test_store_initialization(store):
    """Test that store initializes successfully."""
    assert store.client is not None
    assert await store.health_check() is True


@pytest.mark.asyncio
async def test_store_and_retrieve_memory(store):
    """Test storing and retrieving a memory."""
    # Create test embedding (384 dimensions for MiniLM-L6)
    test_embedding = [0.1] * 384

    # Store a memory
    memory_id = await store.store(
        content="User prefers Python for backend development",
        embedding=test_embedding,
        metadata={
            "category": MemoryCategory.PREFERENCE.value,
            "context_level": ContextLevel.USER_PREFERENCE.value,
            "scope": MemoryScope.GLOBAL.value,
            "importance": 0.9,
            "tags": ["python", "backend"],
        }
    )

    assert memory_id is not None
    assert isinstance(memory_id, str)

    # Retrieve by ID
    retrieved = await store.get_by_id(memory_id)
    assert retrieved is not None
    assert retrieved.content == "User prefers Python for backend development"
    assert retrieved.category == MemoryCategory.PREFERENCE
    assert retrieved.importance == 0.9


@pytest.mark.asyncio
async def test_vector_search(store):
    """Test vector similarity search."""
    # Store multiple memories with different embeddings
    memories = [
        ("Python is great for data science", [0.1, 0.2] + [0.0] * 382),
        ("JavaScript is used for web development", [0.8, 0.1] + [0.0] * 382),
        ("Python is also good for web development", [0.15, 0.25] + [0.0] * 382),
    ]

    for content, embedding in memories:
        await store.store(
            content=content,
            embedding=embedding,
            metadata={
                "category": MemoryCategory.FACT.value,
                "context_level": ContextLevel.PROJECT_CONTEXT.value,
                "scope": MemoryScope.GLOBAL.value,
            }
        )

    # Search with similar embedding
    query_embedding = [0.12, 0.22] + [0.0] * 382
    results = await store.retrieve(query_embedding, limit=2)

    assert len(results) > 0
    assert len(results) <= 2

    # First result should be most similar
    top_result, score = results[0]
    assert "Python" in top_result.content
    assert 0.0 <= score <= 1.0


@pytest.mark.asyncio
async def test_filtered_search(store):
    """Test search with filters."""
    # Store memories with different categories and scopes
    await store.store(
        content="User prefers FastAPI",
        embedding=[0.1] * 384,
        metadata={
            "category": MemoryCategory.PREFERENCE.value,
            "context_level": ContextLevel.USER_PREFERENCE.value,
            "scope": MemoryScope.GLOBAL.value,
            "importance": 0.9,
        }
    )

    await store.store(
        content="Project uses Django framework",
        embedding=[0.2] * 384,
        metadata={
            "category": MemoryCategory.FACT.value,
            "context_level": ContextLevel.PROJECT_CONTEXT.value,
            "scope": MemoryScope.PROJECT.value,
            "project_name": "my-project",
            "importance": 0.7,
        }
    )

    # Search with filter for preferences only
    filters = SearchFilters(
        context_level=ContextLevel.USER_PREFERENCE,
    )

    results = await store.retrieve(
        query_embedding=[0.15] * 384,
        filters=filters,
        limit=10,
    )

    assert len(results) >= 1
    for memory, score in results:
        assert memory.context_level == ContextLevel.USER_PREFERENCE


@pytest.mark.asyncio
async def test_batch_store(store):
    """Test batch storing multiple memories."""
    items = [
        (
            f"Test memory {i}",
            [i * 0.1] * 384,
            {
                "category": MemoryCategory.CONTEXT.value,
                "context_level": ContextLevel.SESSION_STATE.value,
                "scope": MemoryScope.GLOBAL.value,
            }
        )
        for i in range(10)
    ]

    memory_ids = await store.batch_store(items)

    assert len(memory_ids) == 10
    assert all(isinstance(id, str) for id in memory_ids)

    # Verify count
    count = await store.count()
    assert count >= 10


@pytest.mark.asyncio
async def test_delete_memory(store):
    """Test deleting a memory."""
    # Store a memory
    memory_id = await store.store(
        content="Temporary memory",
        embedding=[0.5] * 384,
        metadata={
            "category": MemoryCategory.EVENT.value,
            "context_level": ContextLevel.SESSION_STATE.value,
            "scope": MemoryScope.GLOBAL.value,
        }
    )

    # Verify it exists
    retrieved = await store.get_by_id(memory_id)
    assert retrieved is not None

    # Delete it
    deleted = await store.delete(memory_id)
    assert deleted is True

    # Verify it's gone
    retrieved_after = await store.get_by_id(memory_id)
    assert retrieved_after is None


@pytest.mark.asyncio
async def test_update_memory(store):
    """Test updating memory metadata."""
    # Store a memory
    memory_id = await store.store(
        content="Original content",
        embedding=[0.3] * 384,
        metadata={
            "category": MemoryCategory.FACT.value,
            "context_level": ContextLevel.PROJECT_CONTEXT.value,
            "scope": MemoryScope.GLOBAL.value,
            "importance": 0.5,
        }
    )

    # Update importance
    updated = await store.update(memory_id, {"importance": 0.9})
    assert updated is True

    # Verify update
    retrieved = await store.get_by_id(memory_id)
    assert retrieved.importance == 0.9


@pytest.mark.asyncio
async def test_importance_filter(store):
    """Test filtering by minimum importance."""
    # Store memories with different importance
    await store.store(
        content="Low importance",
        embedding=[0.1] * 384,
        metadata={
            "category": MemoryCategory.FACT.value,
            "context_level": ContextLevel.PROJECT_CONTEXT.value,
            "scope": MemoryScope.GLOBAL.value,
            "importance": 0.3,
        }
    )

    await store.store(
        content="High importance",
        embedding=[0.2] * 384,
        metadata={
            "category": MemoryCategory.FACT.value,
            "context_level": ContextLevel.PROJECT_CONTEXT.value,
            "scope": MemoryScope.GLOBAL.value,
            "importance": 0.9,
        }
    )

    # Search with minimum importance filter
    filters = SearchFilters(min_importance=0.7)
    results = await store.retrieve(
        query_embedding=[0.15] * 384,
        filters=filters,
        limit=10,
    )

    # Should only return high importance memory
    for memory, score in results:
        assert memory.importance >= 0.7
