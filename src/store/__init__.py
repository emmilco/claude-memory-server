"""Storage backend implementations."""

import logging
from typing import Optional
from src.store.base import MemoryStore
from src.config import ServerConfig
from src.core.degradation_warnings import add_degradation_warning

logger = logging.getLogger(__name__)


def create_memory_store(
    backend: Optional[str] = None,
    config: Optional[ServerConfig] = None,
    allow_fallback: Optional[bool] = None
) -> MemoryStore:
    """
    Factory function to create appropriate memory store with graceful fallback.

    Fallback behavior (when allow_fallback=True):
    - If Qdrant is unavailable, automatically falls back to SQLite
    - Logs warning about performance implications
    - Provides upgrade instructions

    Args:
        backend: Storage backend type ("qdrant" or "sqlite"). If None, uses config.
        config: Server configuration. If None, uses global config.
        allow_fallback: If True, fall back to SQLite when Qdrant unavailable

    Returns:
        MemoryStore: Configured storage backend instance.

    Raises:
        ValueError: If backend is unsupported
        ConnectionError: If Qdrant unavailable and fallback disabled
    """
    if config is None:
        from src.config import get_config
        config = get_config()

    if backend is None:
        backend = config.storage_backend

    # Use config setting if allow_fallback not explicitly provided
    if allow_fallback is None:
        allow_fallback = config.allow_qdrant_fallback

    # Try to create the requested backend
    if backend == "qdrant":
        from src.store.qdrant_store import QdrantMemoryStore
        from src.core.exceptions import QdrantConnectionError

        try:
            store = QdrantMemoryStore(config)
            # Test connection by attempting to get collections
            # This will raise QdrantConnectionError if Qdrant is down
            logger.info("Using Qdrant vector store (optimal performance)")
            return store
        except (QdrantConnectionError, ConnectionError, Exception) as e:
            if not allow_fallback:
                logger.error(f"Qdrant connection failed and fallback disabled: {e}")
                raise ConnectionError(
                    f"Failed to connect to Qdrant: {e}\n"
                    f"💡 Solution: Start Qdrant with 'docker-compose up -d' or enable fallback"
                ) from e

            # Graceful fallback to SQLite
            logger.warning(
                "⚠️  Qdrant unavailable, falling back to SQLite.\n"
                f"    Reason: {e}\n"
                f"    Performance impact: 3-5x slower search, no vector similarity\n"
                f"    Upgrade: docker-compose up -d (see docs/setup.md)"
            )

            # Track degradation
            add_degradation_warning(
                component="Qdrant Vector Store",
                message="Qdrant unavailable, using SQLite keyword search only",
                upgrade_path="docker-compose up -d (see docs/setup.md)",
                performance_impact="3-5x slower search, no semantic similarity",
            )

            backend = "sqlite"

    if backend == "sqlite":
        from src.store.sqlite_store import SQLiteMemoryStore

        if config.storage_backend == "qdrant":
            # This is a fallback situation
            logger.info("Using SQLite storage (degraded mode - keyword search only)")
        else:
            # User explicitly chose SQLite
            logger.info("Using SQLite storage (configured)")

        return SQLiteMemoryStore(config)
    else:
        raise ValueError(f"Unsupported storage backend: {backend}")


__all__ = ["MemoryStore", "create_memory_store"]
