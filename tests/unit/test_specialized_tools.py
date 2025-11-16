"""Unit tests for specialized retrieval tools."""

import pytest
import pytest_asyncio

from src.config import ServerConfig
from src.core.server import MemoryRAGServer


@pytest.fixture
def config():
    """Create test configuration."""
    return ServerConfig(
        storage_backend="qdrant",
        qdrant_url="http://localhost:6333",
        read_only_mode=False,
    )


@pytest_asyncio.fixture
async def server(config):
    """Create server instance with test data."""
    srv = MemoryRAGServer(config)
    await srv.initialize()

    # Store test memories with different context levels
    await srv.store_memory(
        content="I prefer Python for backend development",
        category="preference",
        scope="global",
    )

    await srv.store_memory(
        content="This project uses FastAPI framework",
        category="fact",
        scope="project",
        project_name="test-project",
    )

    await srv.store_memory(
        content="Currently debugging the authentication module",
        category="context",
        scope="project",
        project_name="test-project",
    )

    yield srv
    await srv.close()


@pytest.mark.asyncio
async def test_retrieve_preferences(server):
    """Test retrieving only user preferences."""
    results = await server.retrieve_preferences(
        query="Python preference",
        limit=10,
    )

    assert "results" in results
    assert results["total_found"] >= 1

    # All results should be USER_PREFERENCE context level
    for result in results["results"]:
        assert result["memory"]["context_level"] == "USER_PREFERENCE"


@pytest.mark.asyncio
async def test_retrieve_project_context(server):
    """Test retrieving only project context."""
    # Don't filter by project name in test environment
    results = await server.retrieve_project_context(
        query="FastAPI project",
        limit=10,
        use_current_project=False,  # Don't filter by detected project in tests
    )

    assert "results" in results
    assert results["total_found"] >= 1

    # All results should be PROJECT_CONTEXT
    for result in results["results"]:
        assert result["memory"]["context_level"] == "PROJECT_CONTEXT"


@pytest.mark.asyncio
async def test_retrieve_session_state(server):
    """Test retrieving only session state."""
    results = await server.retrieve_session_state(
        query="debugging authentication",
        limit=10,
    )

    assert "results" in results
    assert results["total_found"] >= 1

    # All results should be SESSION_STATE
    for result in results["results"]:
        assert result["memory"]["context_level"] == "SESSION_STATE"


@pytest.mark.asyncio
async def test_specialized_tools_isolation(server):
    """Test that specialized tools don't return other context levels."""
    # Store one of each type
    await server.store_memory(
        content="I like dark mode in my IDE",
        category="preference",
        scope="global",
    )

    await server.store_memory(
        content="The database schema uses PostgreSQL",
        category="fact",
        scope="project",
        project_name="test-project",
    )

    await server.store_memory(
        content="Currently working on the login page",
        category="context",
        scope="project",
        project_name="test-project",
    )

    # Retrieve preferences - should only get preferences
    pref_results = await server.retrieve_preferences("IDE", limit=10)
    pref_count = pref_results["total_found"]

    # Retrieve project context - should only get project context
    proj_results = await server.retrieve_project_context(
        "database", limit=10, use_current_project=False
    )
    proj_count = proj_results["total_found"]

    # Retrieve session state - should only get session state
    session_results = await server.retrieve_session_state("working", limit=10)
    session_count = session_results["total_found"]

    # Each should have found something
    assert pref_count >= 1
    assert proj_count >= 1
    assert session_count >= 1

    # Verify isolation
    for result in pref_results["results"]:
        assert result["memory"]["context_level"] == "USER_PREFERENCE"

    for result in proj_results["results"]:
        assert result["memory"]["context_level"] == "PROJECT_CONTEXT"

    for result in session_results["results"]:
        assert result["memory"]["context_level"] == "SESSION_STATE"


@pytest.mark.asyncio
async def test_retrieve_preferences_with_limit(server):
    """Test that limit parameter works for specialized tools."""
    # Store multiple preferences
    for i in range(5):
        await server.store_memory(
            content=f"Preference number {i}",
            category="preference",
            scope="global",
        )

    # Request only 2
    results = await server.retrieve_preferences("Preference", limit=2)

    # Should respect limit
    assert len(results["results"]) <= 2
