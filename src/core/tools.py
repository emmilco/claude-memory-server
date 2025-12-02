"""Specialized retrieval tools for context-level filtered memory access."""

import logging
from typing import List, Optional
from src.core.models import (
    ContextLevel,
    MemoryScope,
    MemoryCategory,
    SearchFilters,
    MemoryResult,
)
from src.store.base import MemoryStore
from src.embeddings.generator import EmbeddingGenerator

logger = logging.getLogger(__name__)


class SpecializedRetrievalTools:
    """
    Specialized tools for context-level specific memory retrieval.

    These tools provide convenient, filtered access to memories based on
    their context stratification level.
    """

    def __init__(
        self,
        store: MemoryStore,
        embedding_generator: EmbeddingGenerator,
    ):
        """
        Initialize specialized retrieval tools.

        Args:
            store: Memory store instance
            embedding_generator: Embedding generator instance
        """
        self.store = store
        self.embedding_generator = embedding_generator

    async def retrieve_preferences(
        self,
        query: str,
        limit: int = 5,
        scope: Optional[MemoryScope] = None,
        project_name: Optional[str] = None,
        min_importance: float = 0.0,
    ) -> List[MemoryResult]:
        """
        Retrieve user preferences and style guidelines.

        This method filters for memories with context_level=USER_PREFERENCE,
        providing quick access to user coding styles, preferences, and guidelines.

        Args:
            query: Search query
            limit: Maximum number of results (default: 5)
            scope: Optional scope filter (global or project)
            project_name: Optional project name filter
            min_importance: Minimum importance score (0-1)

        Returns:
            List of MemoryResult objects with user preferences

        Example:
            ```python
            results = await tools.retrieve_preferences(
                query="coding style preferences",
                limit=10
            )
            ```
        """
        # Generate embedding for query
        query_embedding = await self.embedding_generator.generate(query)

        # Create filters for user preferences
        filters = SearchFilters(
            context_level=ContextLevel.USER_PREFERENCE,
            scope=scope,
            project_name=project_name,
            min_importance=min_importance,
        )

        # Retrieve from store
        results = await self.store.search_with_filters(
            query_embedding=query_embedding,
            filters=filters,
            limit=limit,
        )

        # Convert to MemoryResult objects
        memory_results = [
            MemoryResult(memory=memory, score=score) for memory, score in results
        ]

        logger.info(
            f"Retrieved {len(memory_results)} user preferences for query: {query[:50]}"
        )
        return memory_results

    async def retrieve_project_context(
        self,
        query: str,
        limit: int = 5,
        project_name: Optional[str] = None,
        category: Optional[MemoryCategory] = None,
        min_importance: float = 0.0,
    ) -> List[MemoryResult]:
        """
        Retrieve project-specific context and architecture information.

        This method filters for memories with context_level=PROJECT_CONTEXT,
        providing access to project architecture, dependencies, and setup.

        Args:
            query: Search query
            limit: Maximum number of results (default: 5)
            project_name: Optional project name filter
            category: Optional category filter
            min_importance: Minimum importance score (0-1)

        Returns:
            List of MemoryResult objects with project context

        Example:
            ```python
            results = await tools.retrieve_project_context(
                query="database configuration",
                project_name="my-api",
                limit=3
            )
            ```
        """
        # Generate embedding for query
        query_embedding = await self.embedding_generator.generate(query)

        # Create filters for project context
        filters = SearchFilters(
            context_level=ContextLevel.PROJECT_CONTEXT,
            project_name=project_name,
            category=category,
            min_importance=min_importance,
        )

        # Retrieve from store
        results = await self.store.search_with_filters(
            query_embedding=query_embedding,
            filters=filters,
            limit=limit,
        )

        # Convert to MemoryResult objects
        memory_results = [
            MemoryResult(memory=memory, score=score) for memory, score in results
        ]

        logger.info(
            f"Retrieved {len(memory_results)} project context items for query: {query[:50]}"
        )
        return memory_results

    async def retrieve_session_state(
        self,
        query: str,
        limit: int = 5,
        project_name: Optional[str] = None,
        min_importance: float = 0.0,
    ) -> List[MemoryResult]:
        """
        Retrieve session-specific state and temporary information.

        This method filters for memories with context_level=SESSION_STATE,
        providing access to current work, temporary decisions, and session info.

        Args:
            query: Search query
            limit: Maximum number of results (default: 5)
            project_name: Optional project name filter
            min_importance: Minimum importance score (0-1)

        Returns:
            List of MemoryResult objects with session state

        Example:
            ```python
            results = await tools.retrieve_session_state(
                query="current work in progress",
                limit=5
            )
            ```
        """
        # Generate embedding for query
        query_embedding = await self.embedding_generator.generate(query)

        # Create filters for session state
        filters = SearchFilters(
            context_level=ContextLevel.SESSION_STATE,
            project_name=project_name,
            min_importance=min_importance,
        )

        # Retrieve from store
        results = await self.store.search_with_filters(
            query_embedding=query_embedding,
            filters=filters,
            limit=limit,
        )

        # Convert to MemoryResult objects
        memory_results = [
            MemoryResult(memory=memory, score=score) for memory, score in results
        ]

        logger.info(
            f"Retrieved {len(memory_results)} session state items for query: {query[:50]}"
        )
        return memory_results

    async def retrieve_by_category(
        self,
        query: str,
        category: MemoryCategory,
        limit: int = 5,
        context_level: Optional[ContextLevel] = None,
        project_name: Optional[str] = None,
    ) -> List[MemoryResult]:
        """
        Retrieve memories by category.

        Args:
            query: Search query
            category: Memory category to filter by
            limit: Maximum number of results (default: 5)
            context_level: Optional context level filter
            project_name: Optional project name filter

        Returns:
            List of MemoryResult objects matching the category
        """
        # Generate embedding for query
        query_embedding = await self.embedding_generator.generate(query)

        # Create filters
        filters = SearchFilters(
            category=category,
            context_level=context_level,
            project_name=project_name,
        )

        # Retrieve from store
        results = await self.store.search_with_filters(
            query_embedding=query_embedding,
            filters=filters,
            limit=limit,
        )

        # Convert to MemoryResult objects
        memory_results = [
            MemoryResult(memory=memory, score=score) for memory, score in results
        ]

        logger.info(
            f"Retrieved {len(memory_results)} {category.value} memories for query: {query[:50]}"
        )
        return memory_results

    async def retrieve_multi_level(
        self,
        query: str,
        context_levels: List[ContextLevel],
        limit: int = 10,
        project_name: Optional[str] = None,
    ) -> dict[ContextLevel, List[MemoryResult]]:
        """
        Retrieve memories from multiple context levels in one call.

        This is useful for getting a comprehensive view across different
        stratification levels.

        Args:
            query: Search query
            context_levels: List of context levels to retrieve from
            limit: Maximum results per level (default: 10)
            project_name: Optional project name filter

        Returns:
            Dictionary mapping ContextLevel to list of MemoryResults

        Example:
            ```python
            results = await tools.retrieve_multi_level(
                query="python coding",
                context_levels=[
                    ContextLevel.USER_PREFERENCE,
                    ContextLevel.PROJECT_CONTEXT
                ],
                limit=5
            )
            # results[ContextLevel.USER_PREFERENCE] -> user preferences
            # results[ContextLevel.PROJECT_CONTEXT] -> project info
            ```
        """
        # Generate embedding once for all queries
        query_embedding = await self.embedding_generator.generate(query)

        results = {}

        for level in context_levels:
            # Create filters for this level
            filters = SearchFilters(
                context_level=level,
                project_name=project_name,
            )

            # Retrieve from store
            level_results = await self.store.search_with_filters(
                query_embedding=query_embedding,
                filters=filters,
                limit=limit,
            )

            # Convert to MemoryResult objects
            memory_results = [
                MemoryResult(memory=memory, score=score)
                for memory, score in level_results
            ]

            results[level] = memory_results

        logger.info(
            f"Retrieved memories from {len(context_levels)} levels for query: {query[:50]}"
        )
        return results
