"""Tests for actionable error messages."""

from src.core.exceptions import (
    MemoryRAGError,
    QdrantConnectionError,
    CollectionNotFoundError,
    EmbeddingError,
)


class TestActionableErrors:
    """Test that errors provide actionable guidance."""

    def test_base_error_with_solution(self):
        """Test base error includes solution in message."""
        error = MemoryRAGError(
            "Something went wrong",
            solution="Try restarting the service",
            docs_url="https://docs.example.com/troubleshooting",
        )

        error_str = str(error)
        assert "Something went wrong" in error_str
        assert "💡 Solution: Try restarting the service" in error_str
        assert "📖 Docs: https://docs.example.com/troubleshooting" in error_str

    def test_qdrant_connection_error_has_solutions(self):
        """Test Qdrant connection error provides multiple solutions (REF-010: SQLite fallback removed)."""
        error = QdrantConnectionError("http://localhost:6333", "Connection refused")

        error_str = str(error)
        assert "Cannot connect to Qdrant" in error_str
        assert "docker-compose up -d" in error_str
        assert "curl http://localhost:6333/health" in error_str
        assert "docker ps" in error_str
        assert "validate-setup" in error_str
        assert "📖 Docs:" in error_str

    def test_collection_not_found_has_solution(self):
        """Test collection not found error provides solution."""
        error = CollectionNotFoundError("my-project")

        error_str = str(error)
        assert "Collection 'my-project' not found" in error_str
        assert "created automatically" in error_str
        assert "python -m src.cli index" in error_str
        assert "my-project" in error_str

    def test_embedding_error_has_checklist(self):
        """Test embedding error provides troubleshooting checklist."""
        error = EmbeddingError("Failed to generate embedding")

        error_str = str(error)
        assert "Failed to generate embedding" in error_str
        assert "sentence-transformers" in error_str
        assert "all-MiniLM-L6-v2" in error_str
        assert "Sufficient memory" in error_str

    def test_error_attributes_accessible(self):
        """Test that solution and docs_url are accessible as attributes."""
        error = MemoryRAGError(
            "Test error", solution="Test solution", docs_url="https://test.com"
        )

        assert error.solution == "Test solution"
        assert error.docs_url == "https://test.com"

    def test_error_without_solution(self):
        """Test that errors work without solution (backward compatible)."""
        error = MemoryRAGError("Simple error")

        error_str = str(error)
        assert "Simple error" in error_str
        assert "💡 Solution:" not in error_str
        assert "📖 Docs:" not in error_str
