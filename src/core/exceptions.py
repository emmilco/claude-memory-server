"""Custom exceptions for Claude Memory RAG Server with actionable solutions."""


class MemoryRAGError(Exception):
    """Base exception for all Memory RAG errors with actionable solutions."""

    def __init__(self, message: str, solution: str = None, docs_url: str = None):
        """
        Initialize error with actionable guidance.

        Args:
            message: Error description
            solution: Suggested solution or next steps
            docs_url: Link to relevant documentation
        """
        self.solution = solution
        self.docs_url = docs_url

        # Build comprehensive error message
        full_message = message
        if solution:
            full_message += f"\n\n💡 Solution: {solution}"
        if docs_url:
            full_message += f"\n📖 Docs: {docs_url}"

        super().__init__(full_message)


class StorageError(MemoryRAGError):
    """Raised when storage backend operations fail."""

    pass


class ValidationError(MemoryRAGError):
    """Raised when input validation fails."""

    pass


class ReadOnlyError(MemoryRAGError):
    """Raised when write operations are attempted in read-only mode."""

    def __init__(self, operation: str = "write"):
        self.operation = operation
        super().__init__(
            f"Cannot perform {operation} operation: server is in read-only mode"
        )


class RetrievalError(MemoryRAGError):
    """Raised when memory retrieval fails."""

    pass


class SecurityError(MemoryRAGError):
    """Raised when security violations are detected."""

    pass


class EmbeddingError(MemoryRAGError):
    """Raised when embedding generation fails with actionable guidance."""

    def __init__(self, message: str):
        solution = (
            "Check:\n"
            "1. sentence-transformers is installed: pip install sentence-transformers\n"
            "2. Model is valid: all-MiniLM-L6-v2, all-mpnet-base-v2\n"
            "3. Sufficient memory available (model requires ~100MB)\n"
            "4. Text is not empty or too long (max ~8000 tokens)"
        )
        super().__init__(message, solution)


class ParsingError(MemoryRAGError):
    """Raised when code parsing fails."""

    pass


class IndexingError(MemoryRAGError):
    """Raised when code indexing fails."""

    pass


class ConfigurationError(MemoryRAGError):
    """Raised when configuration is invalid."""

    pass


class QdrantConnectionError(StorageError):
    """Raised when Qdrant connection fails with actionable fallback."""

    def __init__(self, url: str, reason: str = "Connection failed"):
        self.url = url
        self.reason = reason

        message = f"Cannot connect to Qdrant at {url}: {reason}"
        solution = (
            "Options:\n"
            "1. Start Qdrant: docker-compose up -d\n"
            "2. Use SQLite instead: Set CLAUDE_RAG_STORAGE_BACKEND=sqlite in .env\n"
            "3. Check Qdrant is running: curl http://localhost:6333/health"
        )
        docs_url = "https://github.com/anthropics/claude-code/blob/main/docs/setup.md"

        super().__init__(message, solution, docs_url)


class CollectionNotFoundError(StorageError):
    """Raised when a Qdrant collection does not exist."""

    def __init__(self, collection_name: str):
        self.collection_name = collection_name

        message = f"Collection '{collection_name}' not found"
        solution = (
            f"The collection will be created automatically on first write.\n"
            f"To create it manually: python -m src.cli index ./your-code --project-name {collection_name}"
        )

        super().__init__(message, solution)


class MemoryNotFoundError(StorageError):
    """Raised when a memory with specified ID is not found."""

    def __init__(self, memory_id: str):
        self.memory_id = memory_id
        super().__init__(f"Memory with ID '{memory_id}' not found")
