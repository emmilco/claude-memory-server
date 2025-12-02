"""Factory for creating store instances based on configuration."""

import logging
from src.config import ServerConfig
from src.store.base import MemoryStore

logger = logging.getLogger(__name__)


async def create_store(config: ServerConfig) -> MemoryStore:
    """
    Create and initialize a memory store based on configuration.

    REF-010: SQLite fallback removed - Qdrant is now required for semantic code search.
    This ensures users get proper semantic search capabilities instead of degraded keyword search.

    Args:
        config: Server configuration

    Returns:
        Initialized memory store instance

    Raises:
        RuntimeError: If Qdrant cannot be initialized with setup instructions
        ValueError: If unsupported storage backend is specified
    """
    if config.storage_backend == "qdrant":
        try:
            from src.store.qdrant_store import QdrantMemoryStore

            store = QdrantMemoryStore(config)
            await store.initialize()
            logger.info("✅ Connected to Qdrant vector store")
            return store
        except Exception as e:
            logger.error(f"❌ Qdrant initialization failed: {e}")
            raise RuntimeError(
                f"Failed to initialize Qdrant at {config.qdrant_url}\n\n"
                f"💡 Solution:\n"
                f"  1. Start Qdrant: docker-compose up -d\n"
                f"  2. Check Qdrant health: curl {config.qdrant_url}/health\n"
                f"  3. Verify Docker is running: docker ps\n\n"
                f"Original error: {e}"
            ) from e
    else:
        raise ValueError(
            f"Unsupported storage backend: {config.storage_backend}\n"
            f"Only 'qdrant' is supported. SQLite has been removed.\n"
            f"Start Qdrant with: docker-compose up -d"
        )
