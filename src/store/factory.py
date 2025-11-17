"""Factory for creating store instances based on configuration."""

from src.config import ServerConfig
from src.store.base import MemoryStore


async def create_store(config: ServerConfig) -> MemoryStore:
    """
    Create and initialize a memory store based on configuration.

    Args:
        config: Server configuration

    Returns:
        Initialized memory store instance
    """
    if config.storage_backend == "qdrant":
        from src.store.qdrant_store import QdrantMemoryStore
        store = QdrantMemoryStore(config)
    else:
        from src.store.sqlite_store import SQLiteMemoryStore
        store = SQLiteMemoryStore(config)

    await store.initialize()
    return store
