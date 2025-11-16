"""Custom exceptions for Claude Memory RAG Server."""


class MemoryRAGError(Exception):
    """Base exception for all Memory RAG errors."""

    pass


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
    """Raised when embedding generation fails."""

    pass


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
    """Raised when Qdrant connection fails."""

    def __init__(self, url: str, reason: str = "Connection failed"):
        self.url = url
        self.reason = reason
        super().__init__(f"Cannot connect to Qdrant at {url}: {reason}")


class CollectionNotFoundError(StorageError):
    """Raised when a Qdrant collection does not exist."""

    def __init__(self, collection_name: str):
        self.collection_name = collection_name
        super().__init__(f"Collection '{collection_name}' not found")


class MemoryNotFoundError(StorageError):
    """Raised when a memory with specified ID is not found."""

    def __init__(self, memory_id: str):
        self.memory_id = memory_id
        super().__init__(f"Memory with ID '{memory_id}' not found")
