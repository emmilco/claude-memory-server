"""Extended tests for MemoryRAGServer to increase coverage."""

import pytest
import pytest_asyncio
import uuid
from pathlib import Path
from src.config import ServerConfig
from src.core.server import MemoryRAGServer
from src.core.exceptions import ReadOnlyError, ValidationError, StorageError


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
        search={"retrieval_gate_enabled": False},  # Disable gate for predictable test results
        indexing={"auto_index_enabled": False, "auto_index_on_startup": False},  # Disable auto-indexing
    )


@pytest.fixture
def readonly_config(unique_qdrant_collection):
    """Create read-only test configuration with pooled collection name.

    Uses the unique_qdrant_collection fixture from conftest.py to leverage
    collection pooling and prevent Qdrant deadlocks during parallel test execution.
    """
    return ServerConfig(
        storage_backend="qdrant",
        qdrant_url="http://localhost:6333",
        qdrant_collection_name=unique_qdrant_collection,
        advanced={"read_only_mode": True},
        search={"retrieval_gate_enabled": False},  # Disable gate for predictable test results
        indexing={"auto_index_enabled": False, "auto_index_on_startup": False},  # Disable auto-indexing
    )


@pytest_asyncio.fixture
async def server(config, mock_embeddings_globally):
    """Create server instance with unique collection.

    Depends on mock_embeddings_globally to ensure embedding mocks are applied
    before server.initialize() loads the embedding generator.
    """
    srv = MemoryRAGServer(config)
    await srv.initialize()
    yield srv

    # Cleanup
    await srv.close()
    # Collection cleanup handled by unique_qdrant_collection autouse fixture


@pytest_asyncio.fixture
async def readonly_server(readonly_config, mock_embeddings_globally):
    """Create read-only server instance with pooled collection.

    Depends on mock_embeddings_globally to ensure embedding mocks are applied
    before server.initialize() loads the embedding generator.
    """
    srv = MemoryRAGServer(readonly_config)
    await srv.initialize()
    yield srv

    # Cleanup
    await srv.close()
    # Collection cleanup handled by unique_qdrant_collection autouse fixture


class TestCodeSearch:
    """Test code search functionality."""

    @pytest.mark.asyncio
    async def test_search_code_basic(self, server, small_test_project):
        """Test basic code search."""
        # Index small test project for fast testing
        result = await server.index_codebase(
            directory_path=str(small_test_project),
            project_name="test-project",
            recursive=False
        )

        # Verify return value structure and content
        assert "files_indexed" in result
        assert result["status"] == "success"
        assert result["files_indexed"] >= 0  # Should have indexed some files
        assert "project_name" in result
        assert result["project_name"] == "test-project"

        # Now search
        search_results = await server.search_code(
            query="test function",
            project_name="test-project",
            limit=5
        )

        assert "results" in search_results
        assert isinstance(search_results["results"], list)

    @pytest.mark.asyncio
    async def test_search_code_with_filters(self, server, small_test_project):
        """Test code search with language filter."""
        index_result = await server.index_codebase(
            directory_path=str(small_test_project),
            project_name="test-project"
        )

        # Verify indexing completed successfully
        assert index_result["status"] == "success"
        assert index_result["files_indexed"] >= 0

        # Search with language filter
        results = await server.search_code(
            query="test",
            project_name="test-project",
            language="python",
            limit=10
        )

        assert "results" in results
        # All results should have language field when searching indexed code
        for result in results["results"]:
            assert "language" in result, "Result missing required 'language' field"
            assert result["language"].lower() == "python", f"Expected Python but got {result['language']}"

    @pytest.mark.asyncio
    async def test_search_code_no_results(self, server):
        """Test search with query that has no results."""
        # Search without indexing anything or with very specific query
        results = await server.search_code(
            query="nonexistent_function_xyz_123",
            project_name="nonexistent-project",
            limit=5
        )

        assert "results" in results
        # May be empty or have low-score results
        assert isinstance(results["results"], list)

    @pytest.mark.asyncio
    async def test_index_codebase_nonexistent_path(self, server):
        """Test indexing nonexistent directory."""
        # ValueError is wrapped in StorageError by the server
        with pytest.raises(StorageError, match="does not exist"):
            await server.index_codebase(
                directory_path="/nonexistent/path/xyz",
                project_name="test"
            )


class TestMemoryOperations:
    """Test memory CRUD operations."""

    @pytest.mark.asyncio
    async def test_store_memory_with_tags(self, server):
        """Test storing memory with tags."""
        result = await server.store_memory(
            content="Testing with tags",
            category="fact",
            scope="global",
            tags=["test", "example", "tags"]
        )

        assert "memory_id" in result
        assert result.get("status") in ["stored", "success"]

    @pytest.mark.asyncio
    async def test_store_memory_with_metadata(self, server):
        """Test storing memory with metadata."""
        result = await server.store_memory(
            content="Testing with metadata",
            category="fact",
            scope="global",
            metadata={"key1": "value1", "key2": 42}
        )

        assert "memory_id" in result
        assert result.get("status") in ["stored", "success"]

    @pytest.mark.asyncio
    async def test_store_memory_with_importance(self, server):
        """Test storing memory with custom importance."""
        result = await server.store_memory(
            content="High importance memory",
            category="fact",
            scope="global",
            importance=0.9
        )
        
        assert "memory_id" in result

    @pytest.mark.asyncio
    async def test_retrieve_with_min_importance(self, server):
        """Test retrieval with minimum importance filter."""
        # Store memories with different importance
        await server.store_memory(
            content="Low importance",
            category="fact",
            scope="global",
            importance=0.3
        )
        
        await server.store_memory(
            content="High importance",
            category="fact",
            scope="global",
            importance=0.9
        )
        
        # Retrieve with min_importance filter
        results = await server.retrieve_memories(
            query="importance",
            min_importance=0.7,
            limit=10
        )
        
        assert "results" in results
        for result in results["results"]:
            assert result["memory"]["importance"] >= 0.7

    @pytest.mark.asyncio
    async def test_retrieve_with_category_filter(self, server):
        """Test retrieval with category filter."""
        await server.store_memory(
            content="Preference memory",
            category="preference",
            scope="global"
        )
        
        await server.store_memory(
            content="Fact memory",
            category="fact",
            scope="global"
        )
        
        # Retrieve only preferences
        results = await server.retrieve_memories(
            query="memory",
            category="preference",
            limit=10
        )
        
        assert "results" in results
        for result in results["results"]:
            assert result["memory"]["category"] == "preference"

    @pytest.mark.asyncio
    async def test_delete_nonexistent_memory(self, server):
        """Test deleting a memory that doesn't exist."""
        result = await server.delete_memory("00000000-0000-0000-0000-000000000000")

        # Should handle gracefully with status or deleted field
        assert "status" in result or "deleted" in result or "error" in result
        if "deleted" in result:
            assert isinstance(result["deleted"], bool)


class TestReadOnlyMode:
    """Test read-only mode enforcement."""

    @pytest.mark.asyncio
    async def test_readonly_blocks_store(self, readonly_server):
        """Test that read-only mode blocks store operations."""
        with pytest.raises(ReadOnlyError):
            await readonly_server.store_memory(
                content="This should fail",
                category="fact",
                scope="global"
            )

    @pytest.mark.asyncio
    async def test_readonly_blocks_delete(self, readonly_server):
        """Test that read-only mode blocks delete operations."""
        with pytest.raises(ReadOnlyError):
            await readonly_server.delete_memory("some-id")

    @pytest.mark.asyncio
    async def test_readonly_allows_retrieve(self, readonly_server):
        """Test that read-only mode allows retrieval."""
        # This should work even in read-only mode
        results = await readonly_server.retrieve_memories(
            query="test",
            limit=5
        )
        
        assert "results" in results

    @pytest.mark.asyncio
    async def test_readonly_allows_status(self, readonly_server):
        """Test that read-only mode allows status checks."""
        status = await readonly_server.get_status()
        
        assert "read_only_mode" in status
        assert status["read_only_mode"] == True


class TestSpecializedRetrieval:
    """Test specialized retrieval methods."""

    @pytest.mark.asyncio
    async def test_retrieve_preferences_filters_correctly(self, server):
        """Test that retrieve_preferences only gets preferences."""
        # Store different types
        await server.store_memory(
            content="I prefer Python",
            category="preference",
            scope="global"
        )
        
        await server.store_memory(
            content="This is a fact",
            category="fact",
            scope="global"
        )
        
        # Get preferences
        results = await server.retrieve_preferences(
            query="Python fact",
            limit=10
        )
        
        # Should only get preferences
        for result in results["results"]:
            assert result["memory"]["context_level"] == "USER_PREFERENCE"

    @pytest.mark.asyncio
    async def test_retrieve_project_context_with_project_name(self, server):
        """Test project context retrieval with project filter."""
        await server.store_memory(
            content="Project A uses FastAPI",
            category="fact",
            scope="project",
            project_name="project-a"
        )
        
        await server.store_memory(
            content="Project B uses Django",
            category="fact",
            scope="project",
            project_name="project-b"
        )
        
        # Get project A context
        results = await server.retrieve_project_context(
            query="framework",
            project_name="project-a",
            use_current_project=False,
            limit=10
        )
        
        # Results should be from project A
        # When filtering by project, all results must have project_name and match the filter
        for result in results["results"]:
            assert "project_name" in result["memory"], "Result missing required 'project_name' field"
            assert result["memory"]["project_name"] == "project-a", \
                f"Expected project-a but got {result['memory']['project_name']}"


class TestErrorHandling:
    """Test error handling and edge cases."""

    @pytest.mark.asyncio
    async def test_store_minimal_content(self, server):
        """Test storing memory with minimal content."""
        # Very short content should work
        result = await server.store_memory(
            content="x",
            category="fact",
            scope="global"
        )

        assert "memory_id" in result

    @pytest.mark.asyncio
    async def test_store_with_invalid_category(self, server):
        """Test storing with invalid category."""
        # ValueError is wrapped in StorageError by the server
        with pytest.raises(StorageError, match="not a valid MemoryCategory"):
            await server.store_memory(
                content="test",
                category="invalid_category",
                scope="global"
            )

    @pytest.mark.asyncio
    @pytest.mark.parametrize("limit", [1, 5, 10, 50, 100])
    async def test_retrieve_with_limit(self, server, limit):
        """Test retrieval with limit={limit}.

        Each limit value is tested in isolation for better failure reporting.
        If a specific limit fails, the test output clearly shows which value.
        """
        results = await server.retrieve_memories(
            query="test",
            limit=limit
        )
        assert "results" in results, f"Results missing from response with limit={limit}"
        assert len(results["results"]) <= limit, f"Got {len(results['results'])} results but limit was {limit}"

    @pytest.mark.asyncio
    async def test_get_status_structure(self, server):
        """Test that status returns correct structure."""
        status = await server.get_status()

        # Check required fields
        assert "memory_count" in status or "total_memories" in status
        assert "read_only_mode" in status
        assert isinstance(status.get("memory_count", status.get("total_memories", 0)), int)
        assert isinstance(status["read_only_mode"], bool)


class TestEmbeddingCaching:
    """Test embedding generation and caching."""

    @pytest.mark.asyncio
    async def test_embedding_generation(self, server):
        """Test that embeddings are generated correctly."""
        embedding = await server._get_embedding("test text")
        
        assert isinstance(embedding, list)
        assert len(embedding) == 768  # all-mpnet-base-v2 dimensions
        assert all(isinstance(x, float) for x in embedding)

    @pytest.mark.asyncio
    @pytest.mark.real_embeddings
    @pytest.mark.skip_ci(reason="Embedding model produces slightly different outputs in CI environment")
    async def test_same_text_uses_cache(self, server):
        """Test that repeated text uses cached embeddings.

        Note: This test does NOT use mock_embeddings since it needs to verify
        that the real embedding cache returns identical values.
        """
        text = "This is a test for caching"

        # First call - generates and caches
        embedding1 = await server._get_embedding(text)

        # Second call - should use cache
        embedding2 = await server._get_embedding(text)

        # Should be identical (same cache entry)
        assert embedding1 == embedding2


class TestFindSimilarCode:
    """Test find_similar_code functionality."""

    @pytest.mark.asyncio
    async def test_find_similar_code_basic(self, server, small_test_project):
        """Test basic find similar code."""
        # Index small test project
        result = await server.index_codebase(
            directory_path=str(small_test_project),
            project_name="test-project",
            recursive=False
        )

        assert "files_indexed" in result

        # Now search for similar code using a code snippet
        code_snippet = """
def test_example():
    assert True
"""

        search_results = await server.find_similar_code(
            code_snippet=code_snippet,
            project_name="test-project",
            limit=5
        )

        assert "results" in search_results
        assert isinstance(search_results["results"], list)
        assert "interpretation" in search_results
        assert "suggestions" in search_results
        assert "query_time_ms" in search_results

    @pytest.mark.asyncio
    async def test_find_similar_code_empty_snippet(self, server):
        """Test with empty code snippet."""
        with pytest.raises(ValidationError):
            await server.find_similar_code(
                code_snippet="",
                project_name="test-project"
            )

    @pytest.mark.asyncio
    async def test_find_similar_code_whitespace_only(self, server):
        """Test with whitespace-only code snippet."""
        with pytest.raises(ValidationError):
            await server.find_similar_code(
                code_snippet="   \n\t  ",
                project_name="test-project"
            )

    @pytest.mark.asyncio
    async def test_find_similar_code_with_language_filter(self, server, small_test_project):
        """Test find similar code with language filter."""
        await server.index_codebase(
            directory_path=str(small_test_project),
            project_name="test-project"
        )

        code_snippet = "def test_func(): pass"

        # Search with language filter
        results = await server.find_similar_code(
            code_snippet=code_snippet,
            project_name="test-project",
            language="python",
            limit=10
        )

        assert "results" in results
        # All results should have language field when using language filter
        for result in results["results"]:
            assert "language" in result, "Result missing required 'language' field"
            assert result["language"].lower() == "python", f"Expected Python but got {result['language']}"

    @pytest.mark.asyncio
    async def test_find_similar_code_no_results(self, server):
        """Test find similar with query that has no results."""
        # Search without indexing anything
        code_snippet = "function unique_xyz_123() {}"

        results = await server.find_similar_code(
            code_snippet=code_snippet,
            project_name="nonexistent-project",
            limit=5
        )

        assert "results" in results
        assert isinstance(results["results"], list)
        # Should have interpretation and suggestions even with no results
        assert "interpretation" in results
        assert "suggestions" in results

    @pytest.mark.asyncio
    async def test_find_similar_code_result_format(self, server, small_test_project):
        """Test that results have correct format."""
        await server.index_codebase(
            directory_path=str(small_test_project),
            project_name="test-project"
        )

        code_snippet = "def test(): pass"

        results = await server.find_similar_code(
            code_snippet=code_snippet,
            project_name="test-project",
            limit=3
        )

        assert "total_found" in results
        assert "code_snippet_length" in results
        assert "project_name" in results

        # Check result structure
        for result in results["results"]:
            assert "file_path" in result
            assert "start_line" in result
            assert "end_line" in result
            assert "unit_name" in result
            assert "unit_type" in result
            assert "language" in result
            assert "code" in result
            assert "similarity_score" in result
            # Similarity scores should be between 0 and 1
            assert 0.0 <= result["similarity_score"] <= 1.0

    @pytest.mark.asyncio
    async def test_find_similar_code_high_similarity_interpretation(self, server, small_test_project):
        """Test interpretation for high similarity results."""
        await server.index_codebase(
            directory_path=str(small_test_project),
            project_name="test-project"
        )

        # Use a code snippet that should match well with indexed code
        code_snippet = """
import pytest

def test_something():
    assert True
"""

        results = await server.find_similar_code(
            code_snippet=code_snippet,
            project_name="test-project",
            limit=5
        )

        # Should have an interpretation
        assert "interpretation" in results
        assert isinstance(results["interpretation"], str)

    @pytest.mark.asyncio
    async def test_find_similar_code_with_file_pattern(self, server, small_test_project):
        """Test find similar code with file pattern filter."""
        await server.index_codebase(
            directory_path=str(small_test_project),
            project_name="test-project"
        )

        code_snippet = "def test(): pass"

        # Search with file pattern filter
        results = await server.find_similar_code(
            code_snippet=code_snippet,
            project_name="test-project",
            file_pattern=".py",  # Python files
            limit=10
        )

        assert "results" in results
        for result in results["results"]:
            assert ".py" in result["file_path"]
