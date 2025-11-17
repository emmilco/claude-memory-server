"""Extended tests for MemoryRAGServer to increase coverage."""

import pytest
import pytest_asyncio
from pathlib import Path
from src.config import ServerConfig
from src.core.server import MemoryRAGServer
from src.core.exceptions import ReadOnlyError, ValidationError


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


class TestCodeSearch:
    """Test code search functionality."""

    @pytest.mark.asyncio
    async def test_search_code_basic(self, server):
        """Test basic code search."""
        # First index some code
        test_dir = Path(__file__).parent.parent / "unit"
        
        result = await server.index_codebase(
            directory_path=str(test_dir),
            project_name="test-project",
            recursive=False
        )
        
        assert "files_indexed" in result
        
        # Now search
        search_results = await server.search_code(
            query="test function",
            project_name="test-project",
            limit=5
        )
        
        assert "results" in search_results
        assert isinstance(search_results["results"], list)

    @pytest.mark.asyncio
    async def test_search_code_with_filters(self, server):
        """Test code search with language filter."""
        test_dir = Path(__file__).parent.parent / "unit"
        
        await server.index_codebase(
            directory_path=str(test_dir),
            project_name="test-project"
        )
        
        # Search with language filter
        results = await server.search_code(
            query="test",
            project_name="test-project",
            language="python",
            limit=10
        )
        
        assert "results" in results
        for result in results["results"]:
            if "language" in result:
                assert result["language"].lower() == "python"

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
        with pytest.raises(Exception):  # Should raise FileNotFoundError or similar
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
        for result in results["results"]:
            if result["memory"].get("project_name"):
                assert result["memory"]["project_name"] == "project-a"


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
        with pytest.raises(Exception):  # Should raise validation error
            await server.store_memory(
                content="test",
                category="invalid_category",
                scope="global"
            )

    @pytest.mark.asyncio
    async def test_retrieve_with_various_limits(self, server):
        """Test retrieval with different limit values."""
        # Test various valid limits
        for limit in [1, 5, 10, 50, 100]:
            results = await server.retrieve_memories(
                query="test",
                limit=limit
            )
            assert "results" in results
            assert len(results["results"]) <= limit

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
        assert len(embedding) == 384  # all-MiniLM-L6-v2 dimensions
        assert all(isinstance(x, float) for x in embedding)

    @pytest.mark.asyncio
    async def test_same_text_uses_cache(self, server):
        """Test that repeated text uses cached embeddings."""
        text = "This is a test for caching"
        
        # First call - generates and caches
        embedding1 = await server._get_embedding(text)
        
        # Second call - should use cache
        embedding2 = await server._get_embedding(text)
        
        # Should be identical (same cache entry)
        assert embedding1 == embedding2
