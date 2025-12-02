"""Custom exceptions for Claude Memory RAG Server with actionable solutions."""


class MemoryRAGError(Exception):
    """Base exception for all Memory RAG errors with actionable solutions."""

    error_code = "E000"  # Default error code, overridden by subclasses

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

        # Build comprehensive error message with error code
        full_message = f"[{self.error_code}] {message}"
        if solution:
            full_message += f"\n\n💡 Solution: {solution}"
        if docs_url:
            full_message += f"\n📖 Docs: {docs_url}"

        super().__init__(full_message)


class StorageError(MemoryRAGError):
    """Raised when storage backend operations fail."""

    error_code = "E001"


class ValidationError(MemoryRAGError):
    """Raised when input validation fails."""

    error_code = "E002"


class ReadOnlyError(MemoryRAGError):
    """Raised when write operations are attempted in read-only mode."""

    error_code = "E003"

    def __init__(self, operation: str = "write"):
        self.operation = operation
        super().__init__(
            f"Cannot perform {operation} operation: server is in read-only mode"
        )


class RetrievalError(MemoryRAGError):
    """Raised when memory retrieval fails."""

    error_code = "E004"


class SecurityError(MemoryRAGError):
    """Raised when security violations are detected."""

    error_code = "E005"


class EmbeddingError(MemoryRAGError):
    """Raised when embedding generation fails with actionable guidance."""

    error_code = "E006"

    def __init__(self, message: str):
        solution = (
            "Check:\n"
            "1. sentence-transformers is installed: pip install sentence-transformers\n"
            "2. Model is valid: all-mpnet-base-v2, all-mpnet-base-v2\n"
            "3. Sufficient memory available (model requires ~100MB)\n"
            "4. Text is not empty or too long (max ~8000 tokens)"
        )
        super().__init__(message, solution)


class ParsingError(MemoryRAGError):
    """Raised when code parsing fails."""

    error_code = "E007"


class IndexingError(MemoryRAGError):
    """Raised when code indexing fails."""

    error_code = "E008"


class ConfigurationError(MemoryRAGError):
    """Raised when configuration is invalid."""

    error_code = "E009"


class QdrantConnectionError(StorageError):
    """Raised when Qdrant connection fails with actionable setup instructions."""

    error_code = "E010"

    def __init__(self, url: str, reason: str = "Connection failed"):
        self.url = url
        self.reason = reason

        message = f"Cannot connect to Qdrant at {url}: {reason}"
        solution = (
            "Steps to fix:\n"
            "1. Start Qdrant: docker-compose up -d\n"
            "2. Check Qdrant is running: curl http://localhost:6333/health\n"
            "3. Verify Docker is running: docker ps\n"
            "4. Use validate-setup command: claude-rag validate-setup"
        )
        docs_url = "See docs/SETUP.md for detailed setup instructions"

        super().__init__(message, solution, docs_url)


class CollectionNotFoundError(StorageError):
    """Raised when a Qdrant collection does not exist."""

    error_code = "E011"

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

    error_code = "E012"

    def __init__(self, memory_id: str):
        self.memory_id = memory_id
        super().__init__(f"Memory with ID '{memory_id}' not found")


class DependencyError(MemoryRAGError):
    """Raised when a required dependency is missing or incompatible."""

    error_code = "E013"

    def __init__(self, package_name: str, context: str = ""):
        import platform

        os_type = platform.system()

        # OS-specific install command
        if os_type == "Darwin":
            install_cmd = f"pip install {package_name}"
        elif os_type == "Linux":
            # Try both pip and apt
            apt_name = package_name.replace("_", "-").replace("-", "-")
            install_cmd = (
                f"pip install {package_name}\n"
                f"# Or system package:\n"
                f"sudo apt-get install python3-{apt_name}  # Ubuntu/Debian"
            )
        else:  # Windows
            install_cmd = f"pip install {package_name}"

        message = f"Required dependency '{package_name}' not found"
        if context:
            message += f" ({context})"

        solution = (
            f"Install the missing package:\n\n"
            f"  {install_cmd}\n\n"
            f"Or install all dependencies:\n"
            f"  pip install -r requirements.txt"
        )

        docs_url = "See docs/TROUBLESHOOTING.md for dependency issues"

        super().__init__(message, solution, docs_url)


class DockerNotRunningError(MemoryRAGError):
    """Raised when Docker is required but not running."""

    error_code = "E014"

    def __init__(self):
        import platform

        os_type = platform.system()

        if os_type == "Darwin":
            start_cmd = "Open Docker Desktop application"
        elif os_type == "Linux":
            start_cmd = "sudo systemctl start docker"
        else:  # Windows
            start_cmd = "Start Docker Desktop"

        message = "Docker is required for Qdrant vector store but is not running"
        solution = (
            f"Start Docker:\n\n"
            f"  {start_cmd}\n\n"
            f"Then start Qdrant:\n\n"
            f"  docker-compose up -d"
        )
        docs_url = "See docs/SETUP.md for Docker setup instructions"

        super().__init__(message, solution, docs_url)


class RustBuildError(MemoryRAGError):
    """Raised when Rust parser build fails."""

    error_code = "E015"

    def __init__(self, error_message: str):
        message = f"Failed to build Rust parser: {error_message}"
        solution = (
            "Options:\n\n"
            "1. Install Rust and retry:\n\n"
            "   curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh\n"
            "   source $HOME/.cargo/env\n"
            "   cd rust_core && maturin develop\n\n"
            "2. Use Python parser (slower but no build required):\n\n"
            "   The system will automatically fall back to Python parser\n"
            "   Performance: ~10-20x slower than Rust parser"
        )
        docs_url = "See docs/TROUBLESHOOTING.md for Rust parser issues"

        super().__init__(message, solution, docs_url)
