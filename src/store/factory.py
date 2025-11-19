"""Factory for creating store instances based on configuration."""

import logging
from src.config import ServerConfig
from src.store.base import MemoryStore

logger = logging.getLogger(__name__)


async def create_store(config: ServerConfig) -> MemoryStore:
    """
    Create and initialize a memory store based on configuration.

    Implements graceful degradation (UX-012):
    - If Qdrant is unavailable and allow_qdrant_fallback=True, falls back to SQLite
    - Logs warnings when degradation occurs if warn_on_degradation=True

    Args:
        config: Server configuration

    Returns:
        Initialized memory store instance

    Raises:
        RuntimeError: If store cannot be initialized and fallback is disabled
    """
    store = None

    if config.storage_backend == "qdrant":
        try:
            from src.store.qdrant_store import QdrantMemoryStore
            store = QdrantMemoryStore(config)
            await store.initialize()
            return store
        except Exception as e:
            if config.allow_qdrant_fallback:
                if config.warn_on_degradation:
                    logger.warning(
                        f"Qdrant unavailable ({e}), falling back to SQLite. "
                        "Performance may be reduced. Consider starting Qdrant with 'docker-compose up -d' "
                        "or set STORAGE_BACKEND=sqlite in .env to suppress this warning."
                    )
                # Fallback to SQLite
                from src.store.sqlite_store import SQLiteMemoryStore
                store = SQLiteMemoryStore(config)
            else:
                raise RuntimeError(
                    f"Failed to connect to Qdrant ({e}). "
                    "Set ALLOW_QDRANT_FALLBACK=true to automatically fall back to SQLite."
                ) from e
    else:
        from src.store.sqlite_store import SQLiteMemoryStore
        store = SQLiteMemoryStore(config)

    await store.initialize()
    return store
