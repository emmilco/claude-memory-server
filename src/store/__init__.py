"""Storage backend implementations."""

from typing import Optional
from src.store.base import MemoryStore
from src.config import ServerConfig


def create_memory_store(
    backend: Optional[str] = None, config: Optional[ServerConfig] = None
) -> MemoryStore:
    """
    Factory function to create appropriate memory store based on configuration.

    Args:
        backend: Storage backend type ("qdrant" or "sqlite"). If None, uses config.
        config: Server configuration. If None, uses global config.

    Returns:
        MemoryStore: Configured storage backend instance.
    """
    if config is None:
        from src.config import get_config

        config = get_config()

    if backend is None:
        backend = config.storage_backend

    if backend == "qdrant":
        from src.store.qdrant_store import QdrantMemoryStore

        return QdrantMemoryStore(config)
    elif backend == "sqlite":
        from src.store.sqlite_store import SQLiteMemoryStore

        return SQLiteMemoryStore(config)
    else:
        raise ValueError(f"Unsupported storage backend: {backend}")


__all__ = ["MemoryStore", "create_memory_store"]
