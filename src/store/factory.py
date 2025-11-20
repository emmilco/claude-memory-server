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
        # SQLite is deprecated for code search
        logger.warning(
            "⚠️  SQLite backend is deprecated for code search.\n"
            "   SQLite provides keyword-only search without semantic similarity.\n"
            "   For proper semantic code search, use Qdrant: docker-compose up -d"
        )
        from src.store.sqlite_store import SQLiteMemoryStore
        store = SQLiteMemoryStore(config)
        await store.initialize()
        return store
