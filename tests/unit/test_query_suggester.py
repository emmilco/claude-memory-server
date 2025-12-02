"""Tests for query suggester."""

import pytest
from unittest.mock import AsyncMock
from src.memory.query_suggester import QuerySuggester, QuerySuggestion
from src.config import ServerConfig


@pytest.fixture
def mock_store():
    """Create mock memory store."""
    store = AsyncMock()
    store.list_memories = AsyncMock(return_value=[])
    return store


@pytest.fixture
def config():
    """Create test config."""
    return ServerConfig(
        storage_backend="qdrant",
        qdrant_url="http://localhost:6333",
    )


@pytest.fixture
def suggester(mock_store, config):
    """Create query suggester instance."""
    return QuerySuggester(mock_store, config)


@pytest.mark.asyncio
async def test_suggest_queries_with_intent(suggester):
    """Test intent-based suggestions."""
    response = await suggester.suggest_queries(
        intent="implementation",
        max_suggestions=5,
    )

    assert response.total_suggestions > 0
    assert len(response.suggestions) <= 5

    # Should have at least one template suggestion
    template_suggestions = [s for s in response.suggestions if s.category == "template"]
    assert len(template_suggestions) > 0

    # Verify suggestion structure
    for sug in response.suggestions:
        assert isinstance(sug, QuerySuggestion)
        assert sug.query
        assert sug.category in ["template", "project", "domain", "general"]
        assert sug.description


@pytest.mark.asyncio
async def test_suggest_queries_debugging_intent(suggester):
    """Test debugging intent templates."""
    response = await suggester.suggest_queries(
        intent="debugging",
        max_suggestions=8,
    )

    # Should include debugging-specific suggestions
    queries = [s.query.lower() for s in response.suggestions]
    assert any("error" in q or "exception" in q for q in queries)


@pytest.mark.asyncio
async def test_suggest_queries_with_project_specific(suggester, mock_store):
    """Test project-specific suggestions."""
    # Mock indexed memories with classes
    mock_store.list_memories = AsyncMock(
        return_value=[
            {
                "metadata": {
                    "unit_type": "class",
                    "unit_name": "UserRepository",
                    "language": "python",
                    "file_path": "/app/user.py",
                }
            },
            {
                "metadata": {
                    "unit_type": "class",
                    "unit_name": "UserRepository",  # Duplicate
                    "language": "python",
                    "file_path": "/app/user2.py",
                }
            },
            {
                "metadata": {
                    "unit_type": "function",
                    "unit_name": "process_payment",
                    "language": "python",
                    "file_path": "/app/payment.py",
                }
            },
        ]
    )

    response = await suggester.suggest_queries(
        project_name="test-project",
        max_suggestions=8,
    )

    # Should include project-specific suggestion based on UserRepository
    project_suggestions = [s for s in response.suggestions if s.category == "project"]
    assert len(project_suggestions) > 0


@pytest.mark.asyncio
async def test_suggest_queries_domain_detection(suggester):
    """Test domain-specific preset suggestions."""
    response = await suggester.suggest_queries(
        context="I need to implement authentication",
        max_suggestions=8,
    )

    # Should detect auth domain and include auth suggestions
    domain_suggestions = [s for s in response.suggestions if s.category == "domain"]
    if domain_suggestions:
        queries = [s.query.lower() for s in domain_suggestions]
        assert any("auth" in q or "token" in q or "password" in q for q in queries)


@pytest.mark.asyncio
async def test_get_indexed_stats(suggester, mock_store):
    """Test indexed stats extraction."""
    # Mock indexed memories
    mock_store.list_memories = AsyncMock(
        return_value=[
            {
                "metadata": {
                    "language": "python",
                    "file_path": "/app/auth.py",
                    "unit_type": "function",
                    "unit_name": "validate_token",
                }
            },
            {
                "metadata": {
                    "language": "python",
                    "file_path": "/app/user.py",
                    "unit_type": "class",
                    "unit_name": "User",
                }
            },
            {
                "metadata": {
                    "language": "typescript",
                    "file_path": "/client/api.ts",
                    "unit_type": "function",
                    "unit_name": "fetchUser",
                }
            },
        ]
    )

    stats = await suggester._get_indexed_stats("test-project")

    assert stats["total_files"] == 3
    assert stats["total_units"] == 3
    assert "python" in stats["languages"]
    assert "typescript" in stats["languages"]
    assert stats["languages"]["python"] == 2
    assert stats["languages"]["typescript"] == 1


@pytest.mark.asyncio
async def test_detect_domain_from_context(suggester):
    """Test domain detection from context."""
    # Test auth domain
    domain = suggester._detect_domain("I need to add login functionality", {})
    assert domain == "auth"

    # Test database domain
    domain = suggester._detect_domain("How do I query the database", {})
    assert domain == "database"

    # Test API domain
    domain = suggester._detect_domain("I need to create a REST endpoint", {})
    assert domain == "api"

    # Test error domain
    domain = suggester._detect_domain("How to handle exceptions", {})
    assert domain == "error"


@pytest.mark.asyncio
async def test_detect_domain_from_classes(suggester):
    """Test domain detection from indexed classes."""
    # Test database domain - use non-user classes to avoid auth detection
    stats = {
        "top_classes": ["ProductRepository", "OrderRepository", "InventoryRepository"]
    }

    domain = suggester._detect_domain(None, stats)
    assert domain == "database"  # Repository pattern suggests database

    # Test auth domain
    stats = {"top_classes": ["AuthService", "SessionManager", "TokenValidator"]}

    domain = suggester._detect_domain(None, stats)
    assert domain == "auth"  # Auth-related classes


@pytest.mark.asyncio
async def test_suggest_queries_max_suggestions(suggester):
    """Test max_suggestions limit."""
    response = await suggester.suggest_queries(
        intent="implementation",
        max_suggestions=3,
    )

    assert response.total_suggestions <= 3
    assert len(response.suggestions) <= 3


@pytest.mark.asyncio
async def test_suggest_queries_general_suggestions(suggester):
    """Test general discovery suggestions."""
    response = await suggester.suggest_queries(
        max_suggestions=8,
    )

    # Should always include some general suggestions
    general_suggestions = [s for s in response.suggestions if s.category == "general"]
    assert len(general_suggestions) > 0
