"""Storage backend implementations."""

import logging
from typing import Optional
from src.store.base import MemoryStore
from src.config import ServerConfig

logger = logging.getLogger(__name__)


def create_memory_store(
    backend: Optional[str] = None,
    config: Optional[ServerConfig] = None,
) -> MemoryStore:
    """
    Factory function to create Qdrant memory store.

    REF-010: SQLite fallback removed - Qdrant is now required for semantic code search.
    This ensures users get proper semantic search capabilities instead of degraded keyword search.

    Args:
        backend: Storage backend type ("qdrant" or "sqlite"). If None, uses config.
        config: Server configuration. If None, uses global config.

    Returns:
        MemoryStore: Configured Qdrant storage backend instance.

    Raises:
        ValueError: If backend is unsupported
        ConnectionError: If Qdrant is unavailable with setup instructions
    """
    if config is None:
        from src.config import get_config
        config = get_config()

    if backend is None:
        backend = config.storage_backend

    if backend == "qdrant":
        from src.store.qdrant_store import QdrantMemoryStore
        from src.core.exceptions import QdrantConnectionError

        try:
            store = QdrantMemoryStore(config)
            logger.info("✅ Connected to Qdrant vector store")
            return store
        except (QdrantConnectionError, ConnectionError, Exception) as e:
            logger.error(f"❌ Qdrant connection failed: {e}")
            raise ConnectionError(
                f"Failed to connect to Qdrant at {config.qdrant_url}\n\n"
                f"💡 Solution:\n"
                f"  1. Start Qdrant: docker-compose up -d\n"
                f"  2. Check Qdrant health: curl {config.qdrant_url}/health\n"
                f"  3. Verify Docker is running: docker ps\n\n"
                f"Original error: {e}"
            ) from e

    elif backend == "sqlite":
        # SQLite is deprecated for code search
        logger.warning(
            "⚠️  SQLite backend is deprecated for code search.\n"
            "   SQLite provides keyword-only search without semantic similarity.\n"
            "   For proper semantic code search, use Qdrant: docker-compose up -d"
        )
        from src.store.sqlite_store import SQLiteMemoryStore
        return SQLiteMemoryStore(config)

    else:
        raise ValueError(
            f"Unsupported storage backend: {backend}\n"
            f"Supported backends: 'qdrant' (recommended), 'sqlite' (deprecated)"
        )


__all__ = ["MemoryStore", "create_memory_store"]
