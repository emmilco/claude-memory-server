"""Integration tests for search_code UX enhancements."""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock
from src.core.server import MemoryRAGServer
from src.config import ServerConfig
from tests.conftest import mock_embedding


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

    # Mock store and embedding generator
    server.store = AsyncMock()
    server.embedding_generator = AsyncMock()
    server.embedding_generator.generate = AsyncMock(return_value=mock_embedding(value=0.1))

    await server.initialize()
    return server


@pytest.mark.asyncio
@pytest.mark.skip(reason="FEAT-057 facets not implemented - planned for v4.1")
async def test_search_code_with_facets(server):
    """Test that search_code returns facets."""
    # Mock search results
    mock_memory = MagicMock()
    mock_memory.content = "def validate_token():\n    pass"
    mock_memory.metadata = {
        "file_path": "/app/auth.py",
        "language": "python",
        "unit_type": "function",
        "unit_name": "validate_token",
        "start_line": 1,
        "end_line": 2,
    }

    server.store.retrieve = AsyncMock(return_value=[
        (mock_memory, 0.95),
    ])

    response = await server.search_code("authentication")

    # Should have facets
    assert "facets" in response
    assert "languages" in response["facets"]
    assert "unit_types" in response["facets"]
    assert "files" in response["facets"]
    assert "directories" in response["facets"]


@pytest.mark.asyncio
@pytest.mark.skip(reason="FEAT-057 summary not implemented - planned for v4.1")
async def test_search_code_with_summary(server):
    """Test that search_code returns summary."""
    mock_memory = MagicMock()
    mock_memory.content = "def validate_token():\n    pass"
    mock_memory.metadata = {
        "file_path": "/app/auth.py",
        "language": "python",
        "unit_type": "function",
        "unit_name": "validate_token",
        "start_line": 1,
        "end_line": 2,
        "signature": "validate_token()",
    }

    server.store.retrieve = AsyncMock(return_value=[
        (mock_memory, 0.95),
    ])

    response = await server.search_code("authentication")

    # Should have summary
    assert "summary" in response
    assert response["summary"]
    assert "Found" in response["summary"]


@pytest.mark.asyncio
@pytest.mark.skip(reason="FEAT-057 did_you_mean not implemented - planned for v4.1")
async def test_search_code_with_did_you_mean(server):
    """Test did you mean suggestions for poor results."""
    # Mock empty results (typo query)
    server.store.retrieve = AsyncMock(return_value=[])
    server.store.list_memories = AsyncMock(return_value=[
        {
            "metadata": {
                "unit_name": "authenticate",
                "unit_type": "function",
            }
        }
    ])

    response = await server.search_code("athenticate")  # Typo

    # Should have did_you_mean suggestions
    assert "did_you_mean" in response
    # May have suggestions if spelling suggester finds matches
    assert isinstance(response["did_you_mean"], list)


@pytest.mark.asyncio
@pytest.mark.skip(reason="FEAT-057 refinement_hints not implemented - planned for v4.1")
async def test_search_code_with_refinement_hints(server):
    """Test refinement hints."""
    # Mock many results to trigger "too many" hint
    mock_memories = []
    for i in range(60):
        mock_memory = MagicMock()
        mock_memory.content = f"def func{i}():\n    pass"
        mock_memory.metadata = {
            "file_path": f"/app/file{i}.py",
            "language": "python",
            "unit_type": "function",
            "unit_name": f"func{i}",
            "start_line": 1,
            "end_line": 2,
            "signature": f"func{i}()",
        }
        mock_memories.append((mock_memory, 0.8))

    server.store.retrieve = AsyncMock(return_value=mock_memories)

    response = await server.search_code("functions")

    # Should have refinement hints
    assert "refinement_hints" in response
    assert isinstance(response["refinement_hints"], list)
    # Should suggest narrowing due to many results
    if response["refinement_hints"]:
        hints_text = " ".join(response["refinement_hints"])
        assert "narrow" in hints_text.lower() or "pattern" in hints_text.lower()


@pytest.mark.asyncio
@pytest.mark.skip(reason="FEAT-057 facets for empty query not implemented - planned for v4.1")
async def test_search_code_empty_query(server):
    """Test search_code with empty query."""
    response = await server.search_code("")

    # Should have all UX fields with empty/default values
    assert "facets" in response
    assert "summary" in response
    assert "did_you_mean" in response
    assert "refinement_hints" in response
    assert response["total_found"] == 0


@pytest.mark.asyncio
@pytest.mark.skip(reason="FEAT-057 multi-language facets not implemented - planned for v4.1")
async def test_search_code_multi_language_facets(server):
    """Test facets with multiple languages."""
    # Create mock results with different languages
    memories = []
    for lang in ["python", "typescript"]:
        mock_memory = MagicMock()
        mock_memory.content = "code"
        mock_memory.metadata = {
            "file_path": f"/app/auth.{lang[:2]}",
            "language": lang,
            "unit_type": "function",
            "unit_name": "auth_func",
            "start_line": 1,
            "end_line": 2,
            "signature": "auth_func()",
        }
        memories.append((mock_memory, 0.9))

    server.store.retrieve = AsyncMock(return_value=memories)

    response = await server.search_code("authentication")

    # Facets should show multiple languages
    assert "python" in response["facets"]["languages"]
    assert "typescript" in response["facets"]["languages"]


@pytest.mark.asyncio
@pytest.mark.skip(reason="FEAT-057 summary formatting not implemented - planned for v4.1")
async def test_search_code_summary_formats_correctly(server):
    """Test summary formatting for different result scenarios."""
    # Test single result
    mock_memory = MagicMock()
    mock_memory.content = "def test():\n    pass"
    mock_memory.metadata = {
        "file_path": "/app/test.py",
        "language": "python",
        "unit_type": "function",
        "unit_name": "test",
        "start_line": 1,
        "end_line": 2,
        "signature": "test()",
    }

    server.store.retrieve = AsyncMock(return_value=[(mock_memory, 0.9)])

    response = await server.search_code("test")

    # Summary should be grammatically correct for single result
    assert "function" in response["summary"].lower()
    assert "1 file" in response["summary"].lower()


@pytest.mark.asyncio
async def test_search_code_backward_compatible(server):
    """Test that existing fields are still present."""
    mock_memory = MagicMock()
    mock_memory.content = "def test():\n    pass"
    mock_memory.metadata = {
        "file_path": "/app/test.py",
        "language": "python",
        "unit_type": "function",
        "unit_name": "test",
        "start_line": 1,
        "end_line": 2,
        "signature": "test()",
    }

    server.store.retrieve = AsyncMock(return_value=[(mock_memory, 0.9)])

    response = await server.search_code("test")

    # All original fields should still be present
    assert "status" in response
    assert "results" in response
    assert "total_found" in response
    assert "query" in response
    assert "project_name" in response
    assert "search_mode" in response
    assert "query_time_ms" in response
    assert "quality" in response
    assert "confidence" in response
    assert "suggestions" in response
    assert "interpretation" in response
    assert "matched_keywords" in response
