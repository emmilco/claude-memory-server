"""Integration tests for hybrid search in the full server context."""

import pytest
import pytest_asyncio
import asyncio
from pathlib import Path
import tempfile
import shutil

from src.core.server import MemoryRAGServer
from src.config import ServerConfig


@pytest_asyncio.fixture
async def server_with_hybrid_search():
    """Create a server instance with hybrid search enabled."""
    # Create temp directory for test data
    temp_dir = tempfile.mkdtemp()

    try:
        config = ServerConfig(
            storage_backend="qdrant",
            qdrant_url="http://localhost:6333",
            qdrant_collection_name="test_hybrid_search",
            enable_hybrid_search=True,
            hybrid_search_alpha=0.5,
            hybrid_fusion_method="weighted",
            bm25_k1=1.5,
            bm25_b=0.75,
            read_only_mode=False,
        )

        server = MemoryRAGServer(config=config)
        await server.initialize()

        yield server

        # Cleanup
        await server.close()

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


@pytest_asyncio.fixture
async def server_without_hybrid_search():
    """Create a server instance with hybrid search disabled."""
    temp_dir = tempfile.mkdtemp()

    try:
        config = ServerConfig(
            storage_backend="qdrant",
            qdrant_url="http://localhost:6333",
            qdrant_collection_name="test_hybrid_search_disabled",
            enable_hybrid_search=False,
            read_only_mode=False,
        )

        server = MemoryRAGServer(config=config)
        await server.initialize()

        yield server

        await server.close()

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


@pytest_asyncio.fixture
async def indexed_code_server(server_with_hybrid_search, mock_embeddings):
    """Server with sample code already indexed (optimized with small corpus)."""
    server = server_with_hybrid_search

    # Create sample Python files - reduced from 3 large files to 3 small files
    temp_code_dir = tempfile.mkdtemp()

    try:
        # Create minimal sample code files for faster indexing
        # Kept minimal but with enough content for test assertions
        auth_file = Path(temp_code_dir) / "auth.py"
        auth_file.write_text("""def authenticate_user(username, password):
    '''Authenticate user with credentials.'''
    return check_credentials(username, password)

def validate_token(token):
    return verify_jwt(token)
""")

        db_file = Path(temp_code_dir) / "database.py"
        db_file.write_text("""def connect_database(host, port):
    return create_connection(host, port)

class DatabasePool:
    def get_connection(self):
        return self.pool.acquire()
""")

        config_file = Path(temp_code_dir) / "config.py"
        config_file.write_text("""def parse_config(file_path):
    with open(file_path) as f:
        return json.load(f)

def load_environment():
    return os.environ
""")

        # Index the codebase
        result = await server.index_codebase(
            directory_path=temp_code_dir,
            project_name="test-hybrid-search",
            recursive=False,
        )

        yield server

    finally:
        shutil.rmtree(temp_code_dir, ignore_errors=True)


class TestHybridSearchIntegration:
    """Test hybrid search integration in server."""

    @pytest.mark.asyncio
    async def test_server_initialization_with_hybrid(self, server_with_hybrid_search):
        """Test that server initializes hybrid searcher correctly."""
        server = server_with_hybrid_search

        assert server.hybrid_searcher is not None
        assert server.config.enable_hybrid_search is True
        assert server.hybrid_searcher.alpha == 0.5

    @pytest.mark.asyncio
    async def test_server_initialization_without_hybrid(self, server_without_hybrid_search):
        """Test that server doesn't initialize hybrid searcher when disabled."""
        server = server_without_hybrid_search

        assert server.hybrid_searcher is None
        assert server.config.enable_hybrid_search is False

    @pytest.mark.asyncio
    async def test_search_code_with_hybrid_mode(self, indexed_code_server):
        """Test code search with hybrid mode enabled."""
        server = indexed_code_server

        result = await server.search_code(
            query="user authentication",
            project_name="test-hybrid-search",
            limit=5,
            search_mode="hybrid",
        )

        assert result["status"] == "success"
        assert result["search_mode"] == "hybrid"
        assert "results" in result
        assert len(result["results"]) > 0

        # Should find authentication-related code
        results = result["results"]
        content_texts = [r["code"].lower() for r in results]

        # At least one result should mention authentication
        assert any("authenticat" in text for text in content_texts)

    @pytest.mark.asyncio
    async def test_search_code_with_semantic_mode(self, indexed_code_server):
        """Test code search with semantic mode (default)."""
        server = indexed_code_server

        result = await server.search_code(
            query="user authentication",
            project_name="test-hybrid-search",
            limit=5,
            search_mode="semantic",
        )

        assert result["status"] == "success"
        assert result["search_mode"] == "semantic"
        assert "results" in result

    @pytest.mark.asyncio
    async def test_search_code_invalid_mode(self, indexed_code_server):
        """Test that invalid search mode raises error."""
        server = indexed_code_server

        with pytest.raises(Exception):  # Should raise ValidationError
            await server.search_code(
                query="test",
                project_name="test-hybrid-search",
                search_mode="invalid_mode",
            )

    @pytest.mark.asyncio
    async def test_hybrid_fallback_when_disabled(self, server_without_hybrid_search):
        """Test that hybrid mode falls back to semantic when disabled."""
        # Create minimal test setup
        temp_code_dir = tempfile.mkdtemp()

        try:
            test_file = Path(temp_code_dir) / "test.py"
            test_file.write_text("def test_function():\n    pass")

            await server_without_hybrid_search.index_codebase(
                directory_path=temp_code_dir,
                project_name="test-fallback",
            )

            result = await server_without_hybrid_search.search_code(
                query="test",
                project_name="test-fallback",
                search_mode="hybrid",  # Request hybrid
            )

            # Should fallback to semantic
            assert result["search_mode"] == "semantic"

        finally:
            shutil.rmtree(temp_code_dir, ignore_errors=True)

    @pytest.mark.asyncio
    async def test_hybrid_vs_semantic_comparison(self, indexed_code_server):
        """Compare hybrid and semantic search results."""
        server = indexed_code_server

        # Semantic search
        semantic_result = await server.search_code(
            query="database connection",
            project_name="test-hybrid-search",
            limit=3,
            search_mode="semantic",
        )

        # Hybrid search
        hybrid_result = await server.search_code(
            query="database connection",
            project_name="test-hybrid-search",
            limit=3,
            search_mode="hybrid",
        )

        # Both should return results
        assert len(semantic_result["results"]) > 0
        assert len(hybrid_result["results"]) > 0

        # Results might differ due to BM25 influence
        # But both should be valid
        assert semantic_result["search_mode"] == "semantic"
        assert hybrid_result["search_mode"] == "hybrid"

    @pytest.mark.asyncio
    async def test_hybrid_search_exact_term_match(self, indexed_code_server):
        """Test that hybrid search benefits from exact term matches."""
        server = indexed_code_server

        # Search for exact term "DatabasePool"
        result = await server.search_code(
            query="DatabasePool connection",
            project_name="test-hybrid-search",
            limit=5,
            search_mode="hybrid",
        )

        results = result["results"]
        assert len(results) > 0

        # Should find the DatabasePool class
        class_names = [r.get("unit_name", "") for r in results]
        assert "DatabasePool" in class_names or any("DatabasePool" in r["code"] for r in results)

    @pytest.mark.asyncio
    async def test_different_fusion_methods(self):
        """Test different fusion methods produce results."""
        for fusion_method in ["weighted", "rrf", "cascade"]:
            temp_dir = tempfile.mkdtemp()

            try:
                config = ServerConfig(
                    storage_backend="qdrant",
                    qdrant_url="http://localhost:6333",
                    qdrant_collection_name=f"test_fusion_{fusion_method}",
                    enable_hybrid_search=True,
                    hybrid_fusion_method=fusion_method,
                    read_only_mode=False,
                )

                server = MemoryRAGServer(config=config)
                await server.initialize()

                # Create and index sample code
                code_dir = tempfile.mkdtemp()
                try:
                    test_file = Path(code_dir) / "test.py"
                    test_file.write_text("def authenticate_user(username, password):\n    pass")

                    await server.index_codebase(
                        directory_path=code_dir,
                        project_name=f"test-{fusion_method}",
                    )

                    result = await server.search_code(
                        query="authentication",
                        project_name=f"test-{fusion_method}",
                        search_mode="hybrid",
                    )

                    assert result["status"] == "success"
                    assert result["search_mode"] == "hybrid"

                finally:
                    shutil.rmtree(code_dir, ignore_errors=True)

                await server.close()

            finally:
                shutil.rmtree(temp_dir, ignore_errors=True)


class TestHybridSearchPerformance:
    """Test hybrid search performance characteristics."""

    @pytest.mark.asyncio
    async def test_hybrid_search_latency(self, indexed_code_server):
        """Test that hybrid search completes in reasonable time."""
        server = indexed_code_server

        result = await server.search_code(
            query="authentication user login",
            project_name="test-hybrid-search",
            limit=5,
            search_mode="hybrid",
        )

        # Should complete in under 1000ms (generous limit)
        assert result["query_time_ms"] < 1000

    @pytest.mark.asyncio
    async def test_hybrid_search_with_large_limit(self, indexed_code_server):
        """Test hybrid search with large result limit."""
        server = indexed_code_server

        result = await server.search_code(
            query="function",
            project_name="test-hybrid-search",
            limit=50,  # Large limit
            search_mode="hybrid",
        )

        assert result["status"] == "success"
        # Should handle large limits without error

    @pytest.mark.asyncio
    async def test_multiple_concurrent_hybrid_searches(self, indexed_code_server):
        """Test multiple concurrent hybrid searches."""
        server = indexed_code_server

        queries = [
            "authentication",
            "database",
            "configuration",
            "user login",
            "connection pool",
        ]

        # Run searches concurrently
        tasks = [
            server.search_code(
                query=query,
                project_name="test-hybrid-search",
                search_mode="hybrid",
            )
            for query in queries
        ]

        results = await asyncio.gather(*tasks)

        # All should succeed
        assert all(r["status"] == "success" for r in results)
        assert all(r["search_mode"] == "hybrid" for r in results)


class TestHybridSearchQuality:
    """Test hybrid search result quality."""

    @pytest.mark.asyncio
    async def test_relevant_results_ranking(self, indexed_code_server):
        """Test that hybrid search ranks relevant results highly."""
        server = indexed_code_server

        result = await server.search_code(
            query="authenticate user credentials",
            project_name="test-hybrid-search",
            limit=5,
            search_mode="hybrid",
        )

        results = result["results"]
        assert len(results) > 0

        # Top result should have high relevance score
        top_result = results[0]
        assert top_result["relevance_score"] > 0.5

        # Top result should be authentication-related
        top_content = top_result["code"].lower()
        assert any(word in top_content for word in ["authenticat", "user", "credential"])

    @pytest.mark.asyncio
    async def test_quality_indicators(self, indexed_code_server):
        """Test that quality indicators are provided."""
        server = indexed_code_server

        result = await server.search_code(
            query="database connection",
            project_name="test-hybrid-search",
            search_mode="hybrid",
        )

        # Should have quality indicators
        assert "quality" in result
        assert "confidence" in result
        assert "interpretation" in result
        assert "suggestions" in result

        # Quality should be a valid value
        assert result["quality"] in ["excellent", "good", "fair", "poor"]

    @pytest.mark.asyncio
    async def test_empty_query_handling(self, indexed_code_server):
        """Test hybrid search with empty query."""
        server = indexed_code_server

        result = await server.search_code(
            query="",
            project_name="test-hybrid-search",
            search_mode="hybrid",
        )

        # Should handle gracefully
        assert result["status"] == "success"
        # May return few or no results

    @pytest.mark.asyncio
    async def test_nonexistent_terms_query(self, indexed_code_server):
        """Test hybrid search with query containing nonexistent terms."""
        server = indexed_code_server

        result = await server.search_code(
            query="zxcvbnmasdfghjkl qwertyuiop",  # Nonsense query
            project_name="test-hybrid-search",
            search_mode="hybrid",
        )

        # Should handle gracefully
        assert result["status"] == "success"
        # May return low-scoring results or empty results


class TestHybridSearchWithFilters:
    """Test hybrid search with additional filters."""

    @pytest.mark.asyncio
    async def test_hybrid_search_with_language_filter(self, indexed_code_server):
        """Test hybrid search with language filter."""
        server = indexed_code_server

        result = await server.search_code(
            query="function",
            project_name="test-hybrid-search",
            language="python",
            search_mode="hybrid",
        )

        # Should only return Python results
        assert all(r["language"].lower() == "python" for r in result["results"])

    @pytest.mark.asyncio
    async def test_hybrid_search_with_file_pattern(self, indexed_code_server):
        """Test hybrid search with file pattern filter."""
        server = indexed_code_server

        result = await server.search_code(
            query="database",
            project_name="test-hybrid-search",
            file_pattern="database",
            search_mode="hybrid",
        )

        # Should only return results from database files
        assert all("database" in r["file_path"] for r in result["results"])


class TestHybridSearchConfiguration:
    """Test hybrid search configuration options."""

    @pytest.mark.asyncio
    async def test_different_alpha_values(self):
        """Test hybrid search with different alpha values."""
        for alpha in [0.0, 0.3, 0.5, 0.7, 1.0]:
            temp_dir = tempfile.mkdtemp()

            try:
                config = ServerConfig(
                    storage_backend="qdrant",
                    qdrant_url="http://localhost:6333",
                    qdrant_collection_name=f"test_alpha_{int(alpha*100)}",
                    enable_hybrid_search=True,
                    hybrid_search_alpha=alpha,
                    read_only_mode=False,
                )

                server = MemoryRAGServer(config=config)
                await server.initialize()

                assert server.hybrid_searcher.alpha == alpha

                await server.close()

            finally:
                shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.mark.asyncio
    async def test_different_bm25_parameters(self):
        """Test hybrid search with different BM25 parameters."""
        for k1, b in [(1.2, 0.75), (1.5, 0.75), (2.0, 0.5)]:
            temp_dir = tempfile.mkdtemp()

            try:
                config = ServerConfig(
                    storage_backend="qdrant",
                    qdrant_url="http://localhost:6333",
                    qdrant_collection_name=f"test_bm25_k{int(k1*10)}_b{int(b*100)}",
                    enable_hybrid_search=True,
                    bm25_k1=k1,
                    bm25_b=b,
                    read_only_mode=False,
                )

                server = MemoryRAGServer(config=config)
                await server.initialize()

                assert server.hybrid_searcher.bm25.k1 == k1
                assert server.hybrid_searcher.bm25.b == b

                await server.close()

            finally:
                shutil.rmtree(temp_dir, ignore_errors=True)
