"""Unit tests for MCP server."""

import pytest
import pytest_asyncio

from src.config import ServerConfig
from src.core.server import MemoryRAGServer
from src.core.exceptions import ReadOnlyError


@pytest.fixture
def config():
    """Create test configuration."""
    return ServerConfig(
        storage_backend="qdrant",
        qdrant_url="http://localhost:6333",
        read_only_mode=False,
        enable_retrieval_gate=False,  # Disable gate for predictable test results
    )


@pytest.fixture
def readonly_config():
    """Create read-only test configuration."""
    return ServerConfig(
        storage_backend="qdrant",
        qdrant_url="http://localhost:6333",
        read_only_mode=True,
        enable_retrieval_gate=False,  # Disable gate for predictable test results
    )


@pytest_asyncio.fixture
async def server(config):
    """Create server instance."""
    srv = MemoryRAGServer(config)
    await srv.initialize()
    yield srv
    await srv.close()


@pytest_asyncio.fixture
async def readonly_server(readonly_config):
    """Create read-only server instance."""
    srv = MemoryRAGServer(readonly_config)
    await srv.initialize()
    yield srv
    await srv.close()


@pytest.mark.asyncio
async def test_server_initialization(server):
    """Test that server initializes correctly."""
    # Verify server instance type
    assert isinstance(server, MemoryRAGServer)

    # Verify store is initialized with correct type
    from src.store.qdrant_store import QdrantMemoryStore
    assert isinstance(server.store, QdrantMemoryStore)
    assert server.store.collection_name is not None
    assert isinstance(server.store.collection_name, str)

    # Verify embedding generator is initialized
    from src.embeddings.generator import EmbeddingGenerator
    assert isinstance(server.embedding_generator, EmbeddingGenerator)

    # Verify embedding cache is initialized
    from src.embeddings.cache import EmbeddingCache
    assert isinstance(server.embedding_cache, EmbeddingCache)


@pytest.mark.asyncio
async def test_store_and_retrieve_memory(server):
    """Test storing and retrieving a memory."""
    # Store a memory
    result = await server.store_memory(
        content="Test memory content",
        category="fact",
        scope="global",
        importance=0.8,
    )

    assert result["status"] == "success"
    assert "memory_id" in result
    memory_id = result["memory_id"]

    # Retrieve it
    retrieval = await server.retrieve_memories(
        query="Test memory",
        limit=5,
    )

    assert retrieval["total_found"] >= 1
    assert len(retrieval["results"]) >= 1


@pytest.mark.asyncio
async def test_context_level_classification(server):
    """Test that context levels are auto-classified correctly."""
    # Preference
    result = await server.store_memory(
        content="I prefer Python over JavaScript",
        category="preference",
        scope="global",
    )
    assert result["context_level"] == "USER_PREFERENCE"

    # Session state
    result = await server.store_memory(
        content="Currently working on authentication feature",
        category="context",
        scope="project",
        project_name="test-project",
    )
    assert result["context_level"] == "SESSION_STATE"

    # Project context (default)
    result = await server.store_memory(
        content="This project uses FastAPI framework",
        category="fact",
        scope="project",
        project_name="test-project",
    )
    assert result["context_level"] == "PROJECT_CONTEXT"


@pytest.mark.asyncio
async def test_readonly_mode_blocks_writes(readonly_server):
    """Test that read-only mode blocks all write operations."""
    # Storing should fail
    with pytest.raises(ReadOnlyError):
        await readonly_server.store_memory(
            content="This should fail",
            category="fact",
        )

    # Deleting should fail (even if memory doesn't exist)
    with pytest.raises(ReadOnlyError):
        await readonly_server.delete_memory("fake-id")


@pytest.mark.asyncio
async def test_readonly_mode_allows_reads(readonly_server):
    """Test that read-only mode allows read operations."""
    # Retrieving should work
    retrieval = await readonly_server.retrieve_memories(
        query="test",
        limit=5,
    )

    assert "results" in retrieval
    assert "total_found" in retrieval


@pytest.mark.asyncio
async def test_get_status(server):
    """Test status endpoint."""
    status = await server.get_status()

    assert status["server_name"] == "claude-memory-rag"
    assert status["storage_backend"] == "qdrant"
    assert "memory_count" in status
    assert "statistics" in status
    assert "cache_stats" in status


@pytest.mark.asyncio
async def test_delete_memory(server):
    """Test deleting a memory."""
    # Store a memory first
    store_result = await server.store_memory(
        content="Memory to delete",
        category="fact",
    )
    memory_id = store_result["memory_id"]

    # Verify it exists
    retrieved = await server.store.get_by_id(memory_id)
    assert retrieved is not None

    # Delete it
    delete_result = await server.delete_memory(memory_id)
    assert delete_result["status"] == "success"

    # Verify it's gone
    retrieved_after = await server.store.get_by_id(memory_id)
    assert retrieved_after is None


@pytest.mark.asyncio
async def test_filtered_retrieval(server):
    """Test retrieving with filters."""
    # Store memories with different categories
    await server.store_memory(
        content="Python preference",
        category="preference",
        scope="global",
    )

    await server.store_memory(
        content="Project fact",
        category="fact",
        scope="project",
        project_name="test-project",
    )

    # Retrieve only preferences
    results = await server.retrieve_memories(
        query="Python",
        category="preference",
        limit=10,
    )

    # Should find the preference
    assert results["total_found"] >= 1

    # Retrieve only project-scoped
    results = await server.retrieve_memories(
        query="Project",
        scope="project",
        limit=10,
    )

    assert results["total_found"] >= 1


@pytest.mark.asyncio
async def test_statistics_tracking(server):
    """Test that statistics are tracked correctly."""
    initial_status = await server.get_status()
    initial_stored = initial_status["statistics"]["memories_stored"]

    # Store a memory
    await server.store_memory(
        content="Test for statistics",
        category="fact",
    )

    # Check statistics updated
    updated_status = await server.get_status()
    assert updated_status["statistics"]["memories_stored"] == initial_stored + 1
