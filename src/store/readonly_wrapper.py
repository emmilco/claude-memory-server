"""Read-only wrapper for memory stores."""

import logging
from typing import List, Tuple, Optional, Dict, Any

from src.store.base import MemoryStore
from src.core.models import MemoryUnit, SearchFilters
from src.core.exceptions import ReadOnlyError

logger = logging.getLogger(__name__)


class ReadOnlyStoreWrapper(MemoryStore):
    """
    Wrapper that makes any MemoryStore implementation read-only.

    All write operations (store, delete, batch_store, update) will raise
    ReadOnlyError. Read operations are passed through to the underlying store.

    This is useful for:
    - Security: Prevent modifications in production environments
    - Audit: Ensure data integrity during auditing
    - Third-party integrations: Allow safe read access
    """

    def __init__(self, wrapped_store: MemoryStore):
        """
        Initialize read-only wrapper.

        Args:
            wrapped_store: The underlying store to wrap
        """
        self.wrapped_store = wrapped_store
        logger.info(f"Read-only wrapper enabled for {type(wrapped_store).__name__}")

    async def initialize(self) -> None:
        """Initialize the wrapped store."""
        await self.wrapped_store.initialize()

    async def store(
        self,
        content: str,
        embedding: List[float],
        metadata: Dict[str, Any],
    ) -> str:
        """
        Store operation is blocked in read-only mode.

        Raises:
            ReadOnlyError: Always raised in read-only mode
        """
        raise ReadOnlyError(
            "Cannot store memory in read-only mode. "
            "Restart server without --read-only flag to enable writes."
        )

    async def retrieve(
        self,
        query_embedding: List[float],
        filters: Optional[SearchFilters] = None,
        limit: int = 5,
    ) -> List[Tuple[MemoryUnit, float]]:
        """
        Retrieve memories (read operation allowed).

        Args:
            query_embedding: Query vector
            filters: Optional filters
            limit: Maximum results

        Returns:
            List of (MemoryUnit, score) tuples
        """
        return await self.wrapped_store.retrieve(query_embedding, filters, limit)

    async def delete(self, memory_id: str) -> bool:
        """
        Delete operation is blocked in read-only mode.

        Raises:
            ReadOnlyError: Always raised in read-only mode
        """
        raise ReadOnlyError(
            "Cannot delete memory in read-only mode. "
            "Restart server without --read-only flag to enable deletions."
        )

    async def batch_store(
        self,
        items: List[Tuple[str, List[float], Dict[str, Any]]],
    ) -> List[str]:
        """
        Batch store operation is blocked in read-only mode.

        Raises:
            ReadOnlyError: Always raised in read-only mode
        """
        raise ReadOnlyError(
            "Cannot batch store memories in read-only mode. "
            "Restart server without --read-only flag to enable writes."
        )

    async def search_with_filters(
        self,
        query_embedding: List[float],
        filters: SearchFilters,
        limit: int = 5,
    ) -> List[Tuple[MemoryUnit, float]]:
        """
        Search with filters (read operation allowed).

        Args:
            query_embedding: Query vector
            filters: Search filters
            limit: Maximum results

        Returns:
            List of (MemoryUnit, score) tuples
        """
        return await self.wrapped_store.search_with_filters(
            query_embedding, filters, limit
        )

    async def get_by_id(self, memory_id: str) -> Optional[MemoryUnit]:
        """
        Get memory by ID (read operation allowed).

        Args:
            memory_id: Memory ID

        Returns:
            MemoryUnit if found, None otherwise
        """
        return await self.wrapped_store.get_by_id(memory_id)

    async def count(self, filters: Optional[SearchFilters] = None) -> int:
        """
        Count memories (read operation allowed).

        Args:
            filters: Optional filters

        Returns:
            Number of memories matching filters
        """
        return await self.wrapped_store.count(filters)

    async def update(self, memory_id: str, updates: Dict[str, Any]) -> bool:
        """
        Update operation is blocked in read-only mode.

        Raises:
            ReadOnlyError: Always raised in read-only mode
        """
        raise ReadOnlyError(
            "Cannot update memory in read-only mode. "
            "Restart server without --read-only flag to enable updates."
        )

    async def health_check(self) -> bool:
        """
        Health check (read operation allowed).

        Returns:
            True if healthy
        """
        return await self.wrapped_store.health_check()

    async def close(self) -> None:
        """Close the wrapped store."""
        await self.wrapped_store.close()
        logger.info("Read-only wrapper closed")
