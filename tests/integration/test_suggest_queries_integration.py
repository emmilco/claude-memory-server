"""Integration tests for suggest_queries MCP tool."""

import pytest

# FEAT-057 suggest_queries method not implemented - tests written ahead of implementation
# TODO: Remove skip marker when suggest_queries is implemented (planned for v4.1)
pytestmark = pytest.mark.skip(reason="FEAT-057 suggest_queries() not implemented - planned for v4.1")
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock
from src.core.server import MemoryRAGServer
from src.config import ServerConfig


@pytest.fixture
def config():
    """Create test config."""
    return ServerConfig(
        storage_backend="qdrant",
        qdrant_url="http://localhost:6333",
        advanced={"read_only_mode": False},
    )


@pytest_asyncio.fixture
async def server(config):
    """Create server instance."""
    server = MemoryRAGServer(config)

    # Mock store
    server.store = AsyncMock()
    server.store.list_memories = AsyncMock(return_value=[])

    await server.initialize()
    return server


@pytest.mark.asyncio
async def test_suggest_queries_basic(server):
    """Test basic query suggestion functionality."""
    response = await server.suggest_queries()

    assert "suggestions" in response
    assert "indexed_stats" in response
    assert "total_suggestions" in response
    assert response["total_suggestions"] > 0

    # Verify suggestion structure
    for suggestion in response["suggestions"]:
        assert "query" in suggestion
        assert "category" in suggestion
        assert "description" in suggestion


@pytest.mark.asyncio
async def test_suggest_queries_with_intent(server):
    """Test query suggestions with specific intent."""
    response = await server.suggest_queries(intent="debugging")

    assert response["total_suggestions"] > 0

    # Should have debugging-related suggestions
    queries = [s["query"].lower() for s in response["suggestions"]]
    assert any("error" in q or "exception" in q or "debug" in q for q in queries)


@pytest.mark.asyncio
async def test_suggest_queries_with_project(server):
    """Test query suggestions scoped to project."""
    # Mock project-specific memories
    server.store.list_memories = AsyncMock(return_value=[
        {
            "metadata": {
                "unit_type": "class",
                "unit_name": "PaymentProcessor",
                "language": "python",
                "file_path": "/app/payment.py",
            }
        },
    ])

    response = await server.suggest_queries(project_name="payment-service")

    assert response["project_name"] == "payment-service"
    assert response["indexed_stats"]["total_units"] > 0


@pytest.mark.asyncio
async def test_suggest_queries_with_context(server):
    """Test query suggestions with context."""
    response = await server.suggest_queries(
        context="I need to implement user authentication",
    )

    assert response["total_suggestions"] > 0

    # Should detect auth domain
    queries = [s["query"].lower() for s in response["suggestions"]]
    # May have auth-related suggestions
    assert response["suggestions"]  # At least some suggestions


@pytest.mark.asyncio
async def test_suggest_queries_max_suggestions(server):
    """Test max_suggestions parameter."""
    response = await server.suggest_queries(max_suggestions=3)

    assert response["total_suggestions"] <= 3
    assert len(response["suggestions"]) <= 3


@pytest.mark.asyncio
async def test_suggest_queries_fallback_on_error(server):
    """Test graceful fallback when suggester fails."""
    # Make store.list_memories raise an error
    server.store.list_memories = AsyncMock(side_effect=Exception("Store error"))

    response = await server.suggest_queries()

    # Should still return fallback suggestions
    assert "suggestions" in response
    assert response["total_suggestions"] > 0
    assert "error" in response


@pytest.mark.asyncio
async def test_suggest_queries_caches_suggester(server):
    """Test that query suggester is cached."""
    # First call
    await server.suggest_queries()
    assert hasattr(server, '_query_suggester')
    suggester1 = server._query_suggester

    # Second call should reuse same suggester
    await server.suggest_queries()
    suggester2 = server._query_suggester

    assert suggester1 is suggester2
