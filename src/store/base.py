"""Abstract base class for memory storage backends."""

from abc import ABC, abstractmethod
from typing import List, Tuple, Optional, Dict, Any
from src.core.models import MemoryUnit, SearchFilters


class MemoryStore(ABC):
    """
    Abstract base class defining the interface for memory storage backends.

    All storage implementations (Qdrant, SQLite, etc.) must implement this interface.
    """

    @abstractmethod
    async def store(
        self,
        content: str,
        embedding: List[float],
        metadata: Dict[str, Any],
    ) -> str:
        """
        Store a single memory with its embedding and metadata.

        Args:
            content: The text content of the memory.
            embedding: The vector embedding of the content.
            metadata: Additional metadata (category, context_level, tags, etc.).

        Returns:
            str: The unique ID of the stored memory.

        Raises:
            StorageError: If storage operation fails.
        """
        pass

    @abstractmethod
    async def retrieve(
        self,
        query_embedding: List[float],
        filters: Optional[SearchFilters] = None,
        limit: int = 5,
    ) -> List[Tuple[MemoryUnit, float]]:
        """
        Retrieve memories similar to the query embedding.

        Args:
            query_embedding: The vector embedding of the query.
            filters: Optional filters to apply (context_level, scope, etc.).
            limit: Maximum number of results to return.

        Returns:
            List of tuples (MemoryUnit, similarity_score), sorted by descending score.

        Raises:
            RetrievalError: If retrieval operation fails.
        """
        pass

    @abstractmethod
    async def delete(self, memory_id: str) -> bool:
        """
        Delete a memory by its ID.

        Args:
            memory_id: The unique ID of the memory to delete.

        Returns:
            bool: True if deleted, False if not found.

        Raises:
            StorageError: If deletion operation fails.
        """
        pass

    @abstractmethod
    async def batch_store(
        self,
        items: List[Tuple[str, List[float], Dict[str, Any]]],
    ) -> List[str]:
        """
        Store multiple memories in a batch operation.

        Args:
            items: List of (content, embedding, metadata) tuples.

        Returns:
            List[str]: List of memory IDs for the stored items.

        Raises:
            StorageError: If batch operation fails.
        """
        pass

    @abstractmethod
    async def search_with_filters(
        self,
        query_embedding: List[float],
        filters: SearchFilters,
        limit: int = 5,
    ) -> List[Tuple[MemoryUnit, float]]:
        """
        Search memories with specific filters applied.

        Args:
            query_embedding: The vector embedding of the query.
            filters: Filters to apply during search.
            limit: Maximum number of results.

        Returns:
            List of tuples (MemoryUnit, similarity_score).

        Raises:
            RetrievalError: If search operation fails.
        """
        pass

    @abstractmethod
    async def get_by_id(self, memory_id: str) -> Optional[MemoryUnit]:
        """
        Retrieve a specific memory by its ID.

        Args:
            memory_id: The unique ID of the memory.

        Returns:
            MemoryUnit if found, None otherwise.

        Raises:
            StorageError: If retrieval operation fails.
        """
        pass

    @abstractmethod
    async def count(self, filters: Optional[SearchFilters] = None) -> int:
        """
        Count the number of memories, optionally with filters.

        Args:
            filters: Optional filters to apply when counting.

        Returns:
            int: Number of memories matching the criteria.

        Raises:
            StorageError: If count operation fails.
        """
        pass

    @abstractmethod
    async def update(self, memory_id: str, updates: Dict[str, Any]) -> bool:
        """
        Update a memory's metadata.

        Args:
            memory_id: The unique ID of the memory to update.
            updates: Dictionary of fields to update.

        Returns:
            bool: True if updated, False if not found.

        Raises:
            StorageError: If update operation fails.
        """
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """
        Check if the storage backend is healthy and accessible.

        Returns:
            bool: True if healthy, False otherwise.
        """
        pass

    @abstractmethod
    async def initialize(self) -> None:
        """
        Initialize the storage backend (create collections, tables, etc.).

        Raises:
            StorageError: If initialization fails.
        """
        pass

    @abstractmethod
    async def close(self) -> None:
        """
        Close connections and clean up resources.
        """
        pass

    @abstractmethod
    async def list_memories(
        self,
        filters: Optional[Dict[str, Any]] = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
        limit: int = 20,
        offset: int = 0
    ) -> Tuple[List[MemoryUnit], int]:
        """
        List memories with filtering, sorting, and pagination.

        Args:
            filters: Optional filters to apply (category, context_level, tags, etc.).
            sort_by: Field to sort by (created_at, updated_at, importance).
            sort_order: Sort order (asc, desc).
            limit: Maximum number of results to return.
            offset: Number of results to skip for pagination.

        Returns:
            Tuple of (list of memories, total count before pagination).

        Raises:
            StorageError: If listing operation fails.
        """
        pass
