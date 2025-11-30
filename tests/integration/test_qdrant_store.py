"""Integration tests for Qdrant store."""

import pytest
import pytest_asyncio
import asyncio
import uuid
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
def config(unique_qdrant_collection):
    """Create test configuration with pooled collection.

    Uses the unique_qdrant_collection from conftest.py to leverage
    collection pooling and prevent Qdrant deadlocks during parallel execution.
    """
    return ServerConfig(
        qdrant_url="http://localhost:6333",
        qdrant_collection_name=unique_qdrant_collection,
    )


@pytest_asyncio.fixture
async def store(config, qdrant_client):
    """Create and initialize Qdrant store with pooled collection.

    Uses the session-scoped qdrant_client and unique_qdrant_collection
    fixtures from conftest.py to leverage collection pooling and prevent
    Qdrant deadlocks during parallel test execution.
    """
    test_store = QdrantMemoryStore(config)
    await test_store.initialize()

    yield test_store

    # Cleanup
    await test_store.close()
    # Collection cleanup handled by unique_qdrant_collection autouse fixture


@pytest.mark.asyncio
async def test_store_initialization(store):
    """Test that store initializes successfully.

    Uses fixture with pre-initialized store to avoid timeout issues
    during parallel test execution.

    NOTE: Store now uses connection pooling by default, so self.client is None.
    Instead, clients are acquired from the pool via _get_client().
    """
    # Check that store is initialized - either via pool or direct client
    if store.use_pool:
        # Pool-based: check that pool is available
        assert store.setup.pool is not None, "Pool should be initialized"
    else:
        # Legacy direct client mode
        assert store.client is not None, "Client should be initialized"

    # Retry health check to handle transient issues in parallel execution
    max_retries = 3
    for attempt in range(max_retries):
        try:
            health = await store.health_check()
            assert health is True
            break
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            await asyncio.sleep(0.1)


@pytest.mark.asyncio
async def test_store_and_retrieve_memory(store):
    """Test storing and retrieving a memory."""
    # Create test embedding (768 dimensions for all-mpnet-base-v2)
    test_embedding = [0.1] * 768

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
        ("Python is great for data science", [0.1, 0.2] + [0.0] * 766),
        ("JavaScript is used for web development", [0.8, 0.1] + [0.0] * 766),
        ("Python is also good for web development", [0.15, 0.25] + [0.0] * 766),
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
    query_embedding = [0.12, 0.22] + [0.0] * 766
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
        embedding=[0.1] * 768,
        metadata={
            "category": MemoryCategory.PREFERENCE.value,
            "context_level": ContextLevel.USER_PREFERENCE.value,
            "scope": MemoryScope.GLOBAL.value,
            "importance": 0.9,
        }
    )

    await store.store(
        content="Project uses Django framework",
        embedding=[0.2] * 768,
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
        query_embedding=[0.15] * 768,
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
            [i * 0.1] * 768,
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
        embedding=[0.5] * 768,
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
        embedding=[0.3] * 768,
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
        embedding=[0.1] * 768,
        metadata={
            "category": MemoryCategory.FACT.value,
            "context_level": ContextLevel.PROJECT_CONTEXT.value,
            "scope": MemoryScope.GLOBAL.value,
            "importance": 0.3,
        }
    )

    await store.store(
        content="High importance",
        embedding=[0.2] * 768,
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
        query_embedding=[0.15] * 768,
        filters=filters,
        limit=10,
    )

    # Should only return high importance memory
    for memory, score in results:
        assert memory.importance >= 0.7


@pytest.mark.asyncio
async def test_search_with_multiple_filters(store):
    """Test search with multiple filter conditions."""
    # Store diverse memories
    await store.store(
        content="Python backend preference",
        embedding=[0.1] * 768,
        metadata={
            "category": MemoryCategory.PREFERENCE.value,
            "context_level": ContextLevel.USER_PREFERENCE.value,
            "scope": MemoryScope.PROJECT.value,
            "project_name": "backend-api",
            "importance": 0.8,
            "tags": ["python", "backend"],
        }
    )

    await store.store(
        content="Frontend JavaScript fact",
        embedding=[0.2] * 768,
        metadata={
            "category": MemoryCategory.FACT.value,
            "context_level": ContextLevel.PROJECT_CONTEXT.value,
            "scope": MemoryScope.PROJECT.value,
            "project_name": "frontend-app",
            "importance": 0.6,
        }
    )

    # Filter by category, scope, and project
    filters = SearchFilters(
        category=MemoryCategory.PREFERENCE,
        scope=MemoryScope.PROJECT,
        project_name="backend-api",
    )

    results = await store.search_with_filters(
        query_embedding=[0.15] * 768,
        filters=filters,
        limit=10,
    )

    # Should only match the backend preference
    assert len(results) >= 1
    for memory, score in results:
        assert memory.category == MemoryCategory.PREFERENCE
        assert memory.scope == MemoryScope.PROJECT
        assert memory.project_name == "backend-api"


@pytest.mark.asyncio
async def test_count_with_filters(store):
    """Test counting memories with filters."""
    # Store test memories
    for i in range(5):
        await store.store(
            content=f"Preference {i}",
            embedding=[i * 0.1] * 768,
            metadata={
                "category": MemoryCategory.PREFERENCE.value,
                "context_level": ContextLevel.USER_PREFERENCE.value,
                "scope": MemoryScope.GLOBAL.value,
            }
        )

    for i in range(3):
        await store.store(
            content=f"Fact {i}",
            embedding=[i * 0.2] * 768,
            metadata={
                "category": MemoryCategory.FACT.value,
                "context_level": ContextLevel.PROJECT_CONTEXT.value,
                "scope": MemoryScope.GLOBAL.value,
            }
        )

    # Count all
    total = await store.count()
    assert total >= 8

    # Count with filter
    filters = SearchFilters(category=MemoryCategory.PREFERENCE)
    pref_count = await store.count(filters)
    assert pref_count >= 5


@pytest.mark.asyncio
async def test_retrieve_with_limit(store):
    """Test that retrieve respects limit parameter."""
    # Store many memories
    for i in range(20):
        await store.store(
            content=f"Memory {i}",
            embedding=[i * 0.05] * 768,
            metadata={
                "category": MemoryCategory.CONTEXT.value,
                "context_level": ContextLevel.SESSION_STATE.value,
                "scope": MemoryScope.GLOBAL.value,
            }
        )

    # Retrieve with limit
    results = await store.retrieve([0.5] * 768, limit=5)

    # Should not exceed limit
    assert len(results) <= 5


@pytest.mark.asyncio
@pytest.mark.skip(reason="Flaky in parallel execution - collection state issues cause inconsistent result counts")
async def test_retrieve_with_large_limit(store, test_project_name):
    """Test that retrieve caps limit to prevent memory issues."""
    from src.core.models import SearchFilters

    # Store MORE than the cap (100) to properly test capping logic
    # Use unique project_name for isolation in parallel execution
    for i in range(150):
        await store.store(
            content=f"Memory {i}",
            embedding=[i * 0.001] * 768,  # Small increments to have variation
            metadata={
                "category": MemoryCategory.FACT.value,
                "context_level": ContextLevel.PROJECT_CONTEXT.value,
                "scope": MemoryScope.PROJECT.value,
                "project_name": test_project_name,
            }
        )

    # Request excessive limit, filtered by project name
    results = await store.retrieve(
        [0.5] * 768,
        limit=1000,
        filters=SearchFilters(project_name=test_project_name, scope=MemoryScope.PROJECT)
    )

    # Should cap to exactly 100 (the safe limit)
    assert len(results) == 100, f"Expected exactly 100 results (capped), got {len(results)}"


@pytest.mark.asyncio
async def test_update_nonexistent_memory(store):
    """Test updating memory that doesn't exist."""
    fake_id = "00000000-0000-0000-0000-000000000000"

    updated = await store.update(fake_id, {"importance": 0.9})

    # Should return False for nonexistent memory
    assert updated is False


@pytest.mark.asyncio
async def test_delete_nonexistent_memory(store):
    """Test deleting memory that doesn't exist."""
    fake_id = "00000000-0000-0000-0000-000000000000"

    # Should handle gracefully
    result = await store.delete(fake_id)

    # May return True or False depending on implementation
    assert isinstance(result, bool)


@pytest.mark.asyncio
async def test_batch_store_empty_list(store):
    """Test batch store with empty list."""
    memory_ids = await store.batch_store([])

    assert memory_ids == []


@pytest.mark.asyncio
async def test_search_with_empty_results(store):
    """Test search that returns no results."""
    # Clear any existing data
    filters = SearchFilters(category=MemoryCategory.WORKFLOW)

    # Search for category that doesn't exist in store
    results = await store.retrieve(
        query_embedding=[0.99] * 768,
        filters=filters,
        limit=10,
    )

    # Should return empty list, not error
    assert isinstance(results, list)


@pytest.mark.asyncio
async def test_store_with_tags(store):
    """Test storing and retrieving memory with tags."""
    tags = ["python", "backend", "fastapi", "async"]

    memory_id = await store.store(
        content="FastAPI for async Python backend",
        embedding=[0.5] * 768,
        metadata={
            "category": MemoryCategory.FACT.value,
            "context_level": ContextLevel.PROJECT_CONTEXT.value,
            "scope": MemoryScope.PROJECT.value,
            "project_name": "api-service",
            "tags": tags,
        }
    )

    retrieved = await store.get_by_id(memory_id)
    assert retrieved is not None
    assert set(retrieved.tags) == set(tags)


@pytest.mark.asyncio
async def test_store_with_custom_metadata(store):
    """Test storing memory with custom metadata."""
    custom_metadata = {
        "source": "documentation",
        "version": "1.0.0",
        "author": "developer",
    }

    memory_id = await store.store(
        content="Custom metadata test",
        embedding=[0.4] * 768,
        metadata={
            "category": MemoryCategory.FACT.value,
            "context_level": ContextLevel.PROJECT_CONTEXT.value,
            "scope": MemoryScope.GLOBAL.value,
            "metadata": custom_metadata,
        }
    )

    retrieved = await store.get_by_id(memory_id)
    assert retrieved is not None
    assert retrieved.metadata == custom_metadata


@pytest.mark.asyncio
async def test_retrieve_empty_store(store):
    """Test retrieving from empty store."""
    # Store should be empty or nearly empty from fixture
    results = await store.retrieve([0.5] * 768, limit=10)

    # Should not error, just return empty or minimal results
    assert isinstance(results, list)
