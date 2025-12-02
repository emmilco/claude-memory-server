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
        """Initialize the wrapped store.

        Note: This function is async for framework/interface compatibility, even
        though it doesn't currently use await. Future changes may add async operations.
        """
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

    async def update(
        self,
        memory_id: str,
        updates: Dict[str, Any],
        new_embedding: Optional[List[float]] = None,
    ) -> bool:
        """
        Update operation is blocked in read-only mode.

        Args:
            memory_id: The unique ID of the memory to update.
            updates: Dictionary of fields to update.
            new_embedding: Optional new embedding vector (for content updates).

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


        Note: This function is async for framework/interface compatibility, even
        though it doesn't currently use await. Future changes may add async operations.
        """
        return await self.wrapped_store.health_check()

    async def list_memories(
        self,
        filters: Optional[Dict[str, Any]] = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
        limit: int = 20,
        offset: int = 0,
    ) -> Tuple[List[MemoryUnit], int]:
        """
        List memories (read operation allowed).

        Args:
            filters: Optional filters
            sort_by: Sort field
            sort_order: Sort order
            limit: Max results
            offset: Results to skip

        Returns:
            Tuple of (memories list, total count)
        """
        return await self.wrapped_store.list_memories(
            filters=filters,
            sort_by=sort_by,
            sort_order=sort_order,
            limit=limit,
            offset=offset,
        )

    async def get_indexed_files(
        self,
        project_name: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """
        Get indexed files (read operation allowed).

        Args:
            project_name: Optional project filter
            limit: Max results
            offset: Results to skip

        Returns:
            Dictionary with files list and pagination info
        """
        return await self.wrapped_store.get_indexed_files(
            project_name=project_name, limit=limit, offset=offset
        )

    async def list_indexed_units(
        self,
        project_name: Optional[str] = None,
        language: Optional[str] = None,
        file_pattern: Optional[str] = None,
        unit_type: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """
        List indexed code units (read operation allowed).

        Args:
            project_name: Optional project filter
            language: Optional language filter
            file_pattern: Optional file pattern
            unit_type: Optional unit type filter
            limit: Max results
            offset: Results to skip

        Returns:
            Dictionary with units list and pagination info
        """
        return await self.wrapped_store.list_indexed_units(
            project_name=project_name,
            language=language,
            file_pattern=file_pattern,
            unit_type=unit_type,
            limit=limit,
            offset=offset,
        )

    async def close(self) -> None:
        """Close the wrapped store.

        Note: This function is async for framework/interface compatibility, even
        though it doesn't currently use await. Future changes may add async operations.
        """
        await self.wrapped_store.close()
        logger.info("Read-only wrapper closed")
