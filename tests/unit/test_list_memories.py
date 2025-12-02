"""Unit tests for list_memories functionality."""

import pytest
import pytest_asyncio
from datetime import datetime, UTC, timedelta

from src.config import ServerConfig
from src.core.server import MemoryRAGServer

# Run sequentially on single worker - Qdrant connection sensitive under parallel execution
# Mark as slow - initializes full MemoryRAGServer with embeddings
pytestmark = [pytest.mark.xdist_group("qdrant_sequential"), pytest.mark.slow]


@pytest.fixture
def config(unique_qdrant_collection):
    """Create test configuration with pooled collection name.

    Uses the unique_qdrant_collection fixture from conftest.py to leverage
    collection pooling and prevent Qdrant deadlocks during parallel test execution.
    """
    return ServerConfig(
        storage_backend="qdrant",
        qdrant_url="http://localhost:6333",
        qdrant_collection_name=unique_qdrant_collection,
        advanced={"read_only_mode": False},
        search={"retrieval_gate_enabled": False},
    )


@pytest.fixture
def list_memories_project_name(test_project_name):
    """Unique project name for list_memories tests.

    This allows tests to access the project name for proper
    isolation in parallel execution.
    """
    return test_project_name


@pytest_asyncio.fixture
async def server(config, list_memories_project_name):
    """Create server instance with test memories and unique collection."""
    srv = MemoryRAGServer(config)
    await srv.initialize()

    # Create test memories with different attributes
    # Use unique project_name for isolation in parallel execution
    test_memories = [
        {
            "content": "Python is my preferred language",
            "category": "preference",
            "importance": 0.9,
            "tags": ["python", "languages"],
        },
        {
            "content": "Use tabs for indentation",
            "category": "preference",
            "importance": 0.7,
            "tags": ["formatting", "style"],
        },
        {
            "content": "Project deadline is next week",
            "category": "event",
            "importance": 0.8,
            "tags": ["deadline", "project"],
        },
        {
            "content": "API key is stored in .env",
            "category": "fact",
            "importance": 0.6,
            "tags": ["security", "config"],
        },
        {
            "content": "Always write tests first",
            "category": "workflow",
            "importance": 0.9,
            "tags": ["testing", "tdd"],
        },
    ]

    for mem in test_memories:
        await srv.store_memory(
            **mem, project_name=list_memories_project_name, scope="project"
        )

    yield srv

    # Cleanup
    await srv.close()
    # Collection cleanup handled by unique_qdrant_collection autouse fixture


@pytest.mark.asyncio
async def test_list_all_memories(server, list_memories_project_name):
    """Test listing all memories without filters."""
    # Filter by project name for test isolation in parallel execution
    result = await server.list_memories(
        project_name=list_memories_project_name, limit=100
    )

    assert result["total_count"] >= 5
    assert result["returned_count"] >= 5
    assert len(result["memories"]) >= 5
    # has_more depends on total count, which varies based on other tests


@pytest.mark.asyncio
async def test_filter_by_category(server, list_memories_project_name):
    """Test filtering memories by category."""
    # Filter by project name for test isolation in parallel execution
    result = await server.list_memories(
        project_name=list_memories_project_name, category="preference", limit=100
    )

    # At least 2 from our test data
    assert result["total_count"] >= 2
    assert result["returned_count"] >= 2
    # All results should match the category
    for mem in result["memories"]:
        assert mem["category"] == "preference"


@pytest.mark.asyncio
async def test_filter_by_tags(server, list_memories_project_name):
    """Test filtering memories by tags."""
    # Filter by project name for test isolation in parallel execution
    result = await server.list_memories(
        project_name=list_memories_project_name, tags=["python"], limit=100
    )

    assert result["total_count"] >= 1
    assert any("python" in mem["tags"] for mem in result["memories"])


@pytest.mark.asyncio
async def test_filter_by_importance(server, list_memories_project_name):
    """Test filtering memories by importance range."""
    # Filter by project name for test isolation in parallel execution
    result = await server.list_memories(
        project_name=list_memories_project_name, min_importance=0.8, limit=100
    )

    assert result["total_count"] >= 3
    for mem in result["memories"]:
        assert mem["importance"] >= 0.8


@pytest.mark.asyncio
async def test_sort_by_importance_desc(server, list_memories_project_name):
    """Test sorting memories by importance descending."""
    result = await server.list_memories(
        project_name=list_memories_project_name,
        sort_by="importance",
        sort_order="desc",
        limit=100,
    )

    importances = [mem["importance"] for mem in result["memories"]]
    assert importances == sorted(importances, reverse=True)


@pytest.mark.asyncio
async def test_sort_by_importance_asc(server, list_memories_project_name):
    """Test sorting memories by importance ascending."""
    result = await server.list_memories(
        project_name=list_memories_project_name,
        sort_by="importance",
        sort_order="asc",
        limit=100,
    )

    importances = [mem["importance"] for mem in result["memories"]]
    assert importances == sorted(importances)


@pytest.mark.asyncio
async def test_pagination_first_page(server, list_memories_project_name):
    """Test pagination - first page."""
    result = await server.list_memories(
        project_name=list_memories_project_name, limit=2, offset=0
    )

    assert result["returned_count"] == 2
    assert len(result["memories"]) == 2
    assert result["offset"] == 0
    assert result["limit"] == 2
    assert result["has_more"] is True


@pytest.mark.asyncio
async def test_pagination_second_page(server, list_memories_project_name):
    """Test pagination - second page."""
    result = await server.list_memories(
        project_name=list_memories_project_name, limit=2, offset=2
    )

    assert result["returned_count"] >= 1
    assert len(result["memories"]) >= 1
    assert result["offset"] == 2


@pytest.mark.asyncio
async def test_combined_filters(server, list_memories_project_name):
    """Test combining multiple filters."""
    result = await server.list_memories(
        project_name=list_memories_project_name,
        category="preference",
        min_importance=0.7,
        limit=100,
    )

    for mem in result["memories"]:
        assert mem["category"] == "preference"
        assert mem["importance"] >= 0.7


@pytest.mark.asyncio
async def test_empty_results(server, list_memories_project_name):
    """Test query that returns no results."""
    result = await server.list_memories(
        project_name=list_memories_project_name,
        category="preference",
        tags=["nonexistent-tag"],
        limit=100,
    )

    assert result["total_count"] == 0
    assert result["returned_count"] == 0
    assert len(result["memories"]) == 0
    assert result["has_more"] is False


@pytest.mark.asyncio
async def test_limit_validation(server):
    """Test that limit is validated."""
    # Test limit too low
    with pytest.raises(Exception):  # ValidationError
        await server.list_memories(limit=0)

    # Test limit too high
    with pytest.raises(Exception):  # ValidationError
        await server.list_memories(limit=101)


@pytest.mark.asyncio
async def test_offset_validation(server):
    """Test that offset is validated."""
    with pytest.raises(Exception):  # ValidationError
        await server.list_memories(offset=-1)


@pytest.mark.asyncio
async def test_sort_by_validation(server):
    """Test that sort_by is validated."""
    with pytest.raises(Exception):  # ValidationError
        await server.list_memories(sort_by="invalid_field")


@pytest.mark.asyncio
async def test_sort_order_validation(server):
    """Test that sort_order is validated."""
    with pytest.raises(Exception):  # ValidationError
        await server.list_memories(sort_order="invalid_order")


@pytest.mark.asyncio
async def test_memory_content_in_response(server, list_memories_project_name):
    """Test that memory details are included in response."""
    result = await server.list_memories(
        project_name=list_memories_project_name, limit=1
    )

    assert len(result["memories"]) >= 1
    mem = result["memories"][0]

    # Check all expected fields are present
    assert "memory_id" in mem
    assert "content" in mem
    assert "category" in mem
    assert "context_level" in mem
    assert "importance" in mem
    assert "tags" in mem
    assert "scope" in mem
    assert "created_at" in mem
    assert "updated_at" in mem


@pytest.mark.asyncio
async def test_date_filtering(server, list_memories_project_name):
    """Test filtering by date range."""
    # Get current date
    now = datetime.now(UTC)
    yesterday = (now - timedelta(days=1)).isoformat()
    tomorrow = (now + timedelta(days=1)).isoformat()

    # Filter for memories created in the last day (should get all recent ones)
    result = await server.list_memories(
        project_name=list_memories_project_name,
        date_from=yesterday,
        date_to=tomorrow,
        limit=100,
    )

    assert result["total_count"] >= 5  # All test memories should be in this range
