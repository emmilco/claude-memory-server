"""Memory Service - Core memory CRUD and lifecycle management.

Extracted from MemoryRAGServer (REF-016) to provide focused memory operations.

Responsibilities:
- Store/retrieve/update/delete memories
- Memory deduplication and merging
- Context-level classification
- Import/export functionality
- Memory listing and filtering
"""

import asyncio
import json
import logging
import re
from datetime import datetime, timedelta, UTC
from pathlib import Path
from typing import Optional, Dict, Any, List

from src.config import ServerConfig
from src.store import MemoryStore
from src.embeddings.generator import EmbeddingGenerator
from src.embeddings.cache import EmbeddingCache
from src.core.models import (
    MemoryUnit,
    StoreMemoryRequest,
    QueryRequest,
    MemoryResult,
    RetrievalResponse,
    DeleteMemoryRequest,
    SearchFilters,
    ContextLevel,
    MemoryCategory,
    MemoryScope,
)
from src.core.exceptions import (
    StorageError,
    ValidationError,
    ReadOnlyError,
    RetrievalError,
)
from src.core.tracing import new_operation, get_logger

logger = get_logger(__name__)


class MemoryService:
    """
    Service for memory storage, retrieval, and lifecycle management.

    This service handles all memory CRUD operations, providing a clean
    interface for storing, retrieving, updating, and deleting memories
    with support for semantic search, context-level classification,
    and deduplication.
    """

    def __init__(
        self,
        store: MemoryStore,
        embedding_generator: EmbeddingGenerator,
        embedding_cache: EmbeddingCache,
        config: ServerConfig,
        usage_tracker: Optional[Any] = None,
        conversation_tracker: Optional[Any] = None,
        query_expander: Optional[Any] = None,
        metrics_collector: Optional[Any] = None,
        project_name: Optional[str] = None,
    ):
        """
        Initialize the Memory Service.

        Args:
            store: Memory store backend (Qdrant or SQLite)
            embedding_generator: Embedding generator for semantic search
            embedding_cache: Cache for embeddings
            config: Server configuration
            usage_tracker: Optional usage tracker for composite scoring
            conversation_tracker: Optional conversation tracker for deduplication
            query_expander: Optional query expander for conversation-aware search
            metrics_collector: Optional metrics collector for monitoring
            project_name: Current project name (auto-detected if not provided)
        """
        self.store = store
        self.embedding_generator = embedding_generator
        self.embedding_cache = embedding_cache
        self.config = config
        self.usage_tracker = usage_tracker
        self.conversation_tracker = conversation_tracker
        self.query_expander = query_expander
        self.metrics_collector = metrics_collector
        self.project_name = project_name

        # Service statistics
        self.stats = {
            "memories_stored": 0,
            "memories_retrieved": 0,
            "memories_deleted": 0,
            "memories_updated": 0,
            "queries_processed": 0,
            "queries_gated": 0,
            "queries_retrieved": 0,
            "cache_hits": 0,
            "cache_misses": 0,
        }

    def get_stats(self) -> Dict[str, Any]:
        """Get memory service statistics."""
        return self.stats.copy()

    async def _get_embedding(self, text: str) -> List[float]:
        """
        Get embedding for text, using cache if available.

        Args:
            text: Text to embed

        Returns:
            Embedding vector
        """
        # Try cache first
        cached = await self.embedding_cache.get(text, self.config.embedding_model)
        if cached is not None:
            self.stats["cache_hits"] += 1
            return cached

        self.stats["cache_misses"] += 1

        # Generate embedding
        embedding = await self.embedding_generator.generate(text)

        # Cache it
        await self.embedding_cache.set(text, self.config.embedding_model, embedding)

        return embedding

    def _classify_context_level(
        self, content: str, category: MemoryCategory
    ) -> ContextLevel:
        """
        Auto-classify context level based on content and category.

        Args:
            content: Memory content
            category: Memory category

        Returns:
            ContextLevel: Classified context level
        """
        content_lower = content.lower()

        # Check for preference indicators
        if category == MemoryCategory.PREFERENCE or any(
            word in content_lower
            for word in ["prefer", "like", "dislike", "always", "never", "style"]
        ):
            return ContextLevel.USER_PREFERENCE

        # Check for session state indicators
        if any(
            word in content_lower
            for word in [
                "currently",
                "working on",
                "in progress",
                "debugging",
                "fixing",
            ]
        ):
            return ContextLevel.SESSION_STATE

        # Default to project context
        return ContextLevel.PROJECT_CONTEXT

    def _parse_date_filter(self, date_str: str) -> datetime:
        """
        Parse date filter string to datetime.

        Supports:
        - ISO format: "2024-01-01"
        - Relative: "last week", "yesterday", "last month"

        Args:
            date_str: Date filter string

        Returns:
            Parsed datetime
        """
        date_str = date_str.lower().strip()
        now = datetime.now(UTC)

        if date_str in ["today", "now"]:
            return now
        elif date_str == "yesterday":
            return now - timedelta(days=1)
        elif date_str == "last week" or date_str == "1 week ago":
            return now - timedelta(weeks=1)
        elif date_str == "last month" or date_str == "1 month ago":
            return now - timedelta(days=30)
        elif date_str == "last year" or date_str == "1 year ago":
            return now - timedelta(days=365)

        # Pattern: "N days/weeks/months ago"
        match = re.match(r"(\d+)\s+(day|week|month|year)s?\s+ago", date_str)
        if match:
            num = int(match.group(1))
            unit = match.group(2)
            if unit == "day":
                return now - timedelta(days=num)
            elif unit == "week":
                return now - timedelta(weeks=num)
            elif unit == "month":
                return now - timedelta(days=num * 30)
            elif unit == "year":
                return now - timedelta(days=num * 365)

        # ISO format
        try:
            return datetime.fromisoformat(date_str).replace(tzinfo=UTC)
        except ValueError:
            pass

        # Default: treat as ISO date only
        try:
            return datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=UTC)
        except ValueError:
            raise ValidationError(f"Invalid date format: {date_str}")

    async def store_memory(
        self,
        content: str,
        category: str,
        scope: str = "global",
        project_name: Optional[str] = None,
        importance: float = 0.5,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        context_level: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Store a memory with automatic context-level classification and deduplication.

        Args:
            content: Memory content (clear, concise description)
            category: Memory category (preference, fact, event, workflow, context)
            scope: Memory scope - "global" for all projects, "project" for specific project
            project_name: Required if scope is "project"
            importance: Importance score 0.0-1.0 (default: 0.5)
            tags: Optional tags for categorization
            metadata: Optional structured metadata
            context_level: Auto-classified if not provided

        Returns:
            Dict with memory_id, status, and auto-classified context_level
        """
        op_id = new_operation()
        logger.info(f"Storing memory: {content[:50]}...")

        if self.config.advanced.read_only_mode:
            raise ReadOnlyError("Cannot store memory in read-only mode")

        try:
            # Validate request
            request = StoreMemoryRequest(
                content=content,
                category=MemoryCategory(category),
                scope=MemoryScope(scope),
                project_name=project_name,
                importance=importance,
                tags=tags or [],
                metadata=metadata or {},
                context_level=ContextLevel(context_level) if context_level else None,
            )

            # Auto-classify context level if not provided
            if request.context_level is None:
                request.context_level = self._classify_context_level(
                    request.content, request.category
                )

            # Generate embedding
            embedding = await self._get_embedding(content)

            # Create memory unit
            memory_unit = MemoryUnit(
                content=request.content,
                category=request.category,
                context_level=request.context_level,
                scope=request.scope,
                project_name=request.project_name,
                importance=request.importance,
                embedding_model=self.config.embedding_model,
                tags=request.tags,
                metadata=request.metadata,
            )

            # Store in database
            try:
                async with asyncio.timeout(30.0):
                    memory_id = await self.store.store(
                        content=memory_unit.content,
                        embedding=embedding,
                        metadata={
                            "id": memory_unit.id,
                            "category": memory_unit.category.value,
                            "context_level": memory_unit.context_level.value,
                            "scope": memory_unit.scope.value,
                            "project_name": memory_unit.project_name,
                            "importance": memory_unit.importance,
                            "embedding_model": memory_unit.embedding_model,
                            "created_at": memory_unit.created_at,
                            "tags": memory_unit.tags,
                            "metadata": memory_unit.metadata,
                        },
                    )
            except TimeoutError:
                logger.error("Store operation timed out after 30s")
                raise StorageError("Memory store operation timed out")

            self.stats["memories_stored"] += 1
            logger.info(f"Stored memory: {memory_id}")

            return {
                "memory_id": memory_id,
                "status": "success",
                "context_level": memory_unit.context_level.value,
            }

        except ValidationError as e:
            logger.error(f"Validation error: {e}", exc_info=True)
            raise
        except Exception as e:
            logger.error(f"Failed to store memory: {e}", exc_info=True)
            raise StorageError(f"Failed to store memory: {e}")

    async def retrieve_memories(
        self,
        query: str,
        limit: int = 5,
        context_level: Optional[str] = None,
        scope: Optional[str] = None,
        project_name: Optional[str] = None,
        category: Optional[str] = None,
        min_importance: float = 0.0,
        tags: Optional[List[str]] = None,
        session_id: Optional[str] = None,
        advanced_filters: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Retrieve relevant memories using semantic search with smart routing.

        Args:
            query: Natural language search query
            limit: Maximum results to return (default: 5)
            context_level: Filter by USER_PREFERENCE, PROJECT_CONTEXT, or SESSION_STATE
            scope: Filter by "global" or "project"
            project_name: Required if scope is "project"
            category: Filter by preference, fact, event, workflow, or context
            min_importance: Minimum importance 0.0-1.0
            tags: Filter by tags
            session_id: Optional session ID for conversation-aware context tracking
            advanced_filters: Advanced options (date ranges, tag logic, exclusions)

        Returns:
            Dict with results, relevance scores, total_found, query_time_ms
        """
        op_id = new_operation()
        logger.info(f"Retrieving memories: query='{query[:50]}', limit={limit}")

        try:
            import time
            start_time = time.time()

            # Construct advanced_filters if provided
            adv_filters_obj = None
            if advanced_filters:
                from src.core.models import AdvancedSearchFilters
                adv_filters_obj = AdvancedSearchFilters(**advanced_filters)

            # Validate request
            request = QueryRequest(
                query=query,
                limit=limit,
                context_level=ContextLevel(context_level) if context_level else None,
                scope=MemoryScope(scope) if scope else None,
                project_name=project_name,
                category=MemoryCategory(category) if category else None,
                min_importance=min_importance,
                tags=tags or [],
                advanced_filters=adv_filters_obj,
            )

            # Conversation-aware query expansion (if session provided)
            expanded_query = query
            recent_queries = []
            if session_id and self.conversation_tracker and self.query_expander:
                recent_queries = self.conversation_tracker.get_recent_queries(session_id)
                if recent_queries:
                    expanded_query = await self.query_expander.expand_query(
                        query, recent_queries
                    )
                    if expanded_query != query:
                        logger.debug(f"Expanded query: '{query}' -> '{expanded_query}'")

            # Generate query embedding (use expanded query)
            query_embedding = await self._get_embedding(expanded_query)

            # Build filters
            filters = SearchFilters(
                context_level=request.context_level,
                scope=request.scope,
                project_name=request.project_name,
                category=request.category,
                min_importance=request.min_importance,
                tags=request.tags,
                advanced_filters=request.advanced_filters,
            )

            # Determine fetch limit (with deduplication multiplier if needed)
            fetch_limit = request.limit
            shown_memory_ids = set()

            if session_id and self.conversation_tracker:
                # Fetch more to account for deduplication
                fetch_limit = request.limit * self.config.deduplication_fetch_multiplier
                shown_memory_ids = self.conversation_tracker.get_shown_memory_ids(session_id)
                logger.debug(
                    f"Deduplication enabled: fetching {fetch_limit} results "
                    f"(filtering {len(shown_memory_ids)} shown)"
                )

            # Retrieve from store
            try:
                async with asyncio.timeout(30.0):
                    results = await self.store.retrieve(
                        query_embedding=query_embedding,
                        filters=filters if any(filters.to_dict().values()) else None,
                        limit=fetch_limit,
                    )
            except TimeoutError:
                logger.error("Retrieve operation timed out after 30s")
                raise RetrievalError("Memory retrieval operation timed out")

            # Apply deduplication if session provided
            if session_id and shown_memory_ids:
                filtered_results = [
                    (memory, score) for memory, score in results
                    if memory.id not in shown_memory_ids
                ]
                results = filtered_results[:request.limit]

            # Update stats for successful retrieval
            self.stats["queries_retrieved"] += 1

            # Apply composite ranking if usage tracking is enabled
            if self.usage_tracker and self.config.analytics.usage_tracking:
                reranked_results = []

                for memory, similarity_score in results:
                    usage_stats = await self.usage_tracker.get_usage_stats(memory.id)

                    if usage_stats:
                        composite_score = self.usage_tracker.calculate_composite_score(
                            similarity_score=similarity_score,
                            created_at=memory.created_at,
                            last_used=datetime.fromisoformat(usage_stats["last_used"]) if usage_stats.get("last_used") else None,
                            use_count=usage_stats.get("use_count", 0),
                        )
                    else:
                        composite_score = similarity_score

                    reranked_results.append((memory, composite_score, similarity_score))

                reranked_results.sort(key=lambda x: x[1], reverse=True)

                memory_ids = [memory.id for memory, _, _ in reranked_results]
                scores = [comp_score for _, comp_score, _ in reranked_results]
                await self.usage_tracker.record_batch(memory_ids, scores)

                results = [(memory, composite_score) for memory, composite_score, _ in reranked_results]

            # Convert to response format
            memory_results = [
                MemoryResult(memory=memory, score=min(max(score, 0.0), 1.0))
                for memory, score in results
            ]

            query_time_ms = (time.time() - start_time) * 1000
            self.stats["memories_retrieved"] += len(memory_results)
            self.stats["queries_processed"] += 1

            response = RetrievalResponse(
                results=memory_results,
                total_found=len(memory_results),
                query_time_ms=query_time_ms,
                used_cache=False,
            )

            logger.info(
                f"Retrieved {len(memory_results)} memories in {query_time_ms:.2f}ms"
            )

            # Track query and results in conversation session
            if session_id and self.conversation_tracker:
                results_shown = [result.memory.id for result in memory_results]
                self.conversation_tracker.track_query(
                    session_id=session_id,
                    query=query,
                    results_shown=results_shown,
                    query_embedding=query_embedding if self.config.memory.conversation_tracking else None,
                )

            # Log metrics for performance monitoring
            if self.metrics_collector:
                avg_relevance = sum(r.score for r in memory_results) / len(memory_results) if memory_results else 0.0
                self.metrics_collector.log_query(
                    query=query,
                    latency_ms=query_time_ms,
                    result_count=len(memory_results),
                    avg_relevance=avg_relevance
                )

            return response.model_dump()

        except Exception as e:
            logger.error(f"Failed to retrieve memories: {e}", exc_info=True)
            raise RetrievalError(f"Failed to retrieve memories: {e}")

    async def delete_memory(self, memory_id: str) -> Dict[str, Any]:
        """
        Delete a memory by ID.

        Args:
            memory_id: Memory ID to delete

        Returns:
            Dict with status ("success" or "not_found")
        """
        op_id = new_operation()
        logger.info(f"Deleting memory: {memory_id}")

        if self.config.advanced.read_only_mode:
            raise ReadOnlyError("Cannot delete memory in read-only mode")

        try:
            request = DeleteMemoryRequest(memory_id=memory_id)
            try:
                async with asyncio.timeout(30.0):
                    success = await self.store.delete(request.memory_id)
            except TimeoutError:
                logger.error("Delete operation timed out after 30s")
                raise StorageError("Memory delete operation timed out")

            if success:
                self.stats["memories_deleted"] += 1
                logger.info(f"Deleted memory: {memory_id}")
                return {"status": "success", "memory_id": memory_id}
            else:
                return {"status": "not_found", "memory_id": memory_id}

        except Exception as e:
            logger.error(f"Failed to delete memory: {e}", exc_info=True)
            raise StorageError(f"Failed to delete memory: {e}")

    async def get_memory_by_id(self, memory_id: str) -> Dict[str, Any]:
        """
        Retrieve a specific memory by its ID.

        Args:
            memory_id: The unique ID of the memory to retrieve

        Returns:
            Dict with status and memory data
        """
        try:
            try:
                async with asyncio.timeout(30.0):
                    memory = await self.store.get_by_id(memory_id)
            except TimeoutError:
                logger.error("Get by ID operation timed out after 30s")
                raise StorageError("Memory retrieval by ID timed out")

            if memory:
                return {
                    "status": "success",
                    "memory": {
                        "id": memory.id,
                        "memory_id": memory.id,
                        "content": memory.content,
                        "category": memory.category.value if hasattr(memory.category, 'value') else memory.category,
                        "context_level": memory.context_level.value if hasattr(memory.context_level, 'value') else memory.context_level,
                        "importance": memory.importance,
                        "tags": memory.tags or [],
                        "metadata": memory.metadata or {},
                        "scope": memory.scope.value if hasattr(memory.scope, 'value') else memory.scope,
                        "project_name": memory.project_name,
                        "created_at": memory.created_at.isoformat() if hasattr(memory.created_at, 'isoformat') else memory.created_at,
                        "updated_at": memory.updated_at.isoformat() if hasattr(memory.updated_at, 'isoformat') else memory.updated_at,
                        "last_accessed": memory.last_accessed.isoformat() if memory.last_accessed and hasattr(memory.last_accessed, 'isoformat') else memory.last_accessed,
                    }
                }
            else:
                return {
                    "status": "not_found",
                    "message": f"Memory {memory_id} not found"
                }

        except Exception as e:
            logger.error(f"Failed to get memory by ID: {e}", exc_info=True)
            raise StorageError(f"Failed to get memory by ID: {e}")

    async def update_memory(
        self,
        memory_id: str,
        content: Optional[str] = None,
        category: Optional[str] = None,
        importance: Optional[float] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        context_level: Optional[str] = None,
        regenerate_embedding: bool = True,
    ) -> Dict[str, Any]:
        """
        Update an existing memory.

        Args:
            memory_id: ID of memory to update
            content: New content (optional)
            category: New category (optional)
            importance: New importance score 0.0-1.0 (optional)
            tags: New tags list (optional)
            metadata: New metadata dict (optional)
            context_level: New context level (optional)
            regenerate_embedding: Whether to regenerate embedding if content changes

        Returns:
            Dict with status and update details
        """
        if self.config.advanced.read_only_mode:
            raise ReadOnlyError("Cannot update memory in read-only mode")

        try:
            updates = {}
            updated_fields = []

            if content is not None:
                if not (1 <= len(content) <= 50000):
                    raise ValidationError("content must be 1-50000 characters")
                updates["content"] = content
                updated_fields.append("content")

            if category is not None:
                cat = MemoryCategory(category)
                updates["category"] = cat.value
                updated_fields.append("category")

            if importance is not None:
                if not (0.0 <= importance <= 1.0):
                    raise ValidationError("importance must be between 0.0 and 1.0")
                updates["importance"] = importance
                updated_fields.append("importance")

            if tags is not None:
                for tag in tags:
                    if not isinstance(tag, str) or len(tag) > 50:
                        raise ValidationError("Tags must be strings <= 50 chars")
                updates["tags"] = tags
                updated_fields.append("tags")

            if metadata is not None:
                if not isinstance(metadata, dict):
                    raise ValidationError("metadata must be a dictionary")
                updates["metadata"] = metadata
                updated_fields.append("metadata")

            if context_level is not None:
                cl = ContextLevel(context_level)
                updates["context_level"] = cl.value
                updated_fields.append("context_level")

            if not updates:
                raise ValidationError("At least one field must be provided for update")

            # Regenerate embedding if content changed
            new_embedding = None
            embedding_regenerated = False

            if "content" in updates and regenerate_embedding:
                embedding_regenerated = True
                new_embedding = await self.embedding_generator.generate(updates["content"])

            # Perform update
            try:
                async with asyncio.timeout(30.0):
                    success = await self.store.update(
                        memory_id=memory_id,
                        updates=updates,
                        new_embedding=new_embedding
                    )
            except TimeoutError:
                logger.error("Update operation timed out after 30s")
                raise StorageError("Memory update operation timed out")

            if success:
                self.stats["memories_updated"] = self.stats.get("memories_updated", 0) + 1

                return {
                    "status": "updated",
                    "updated_fields": updated_fields,
                    "embedding_regenerated": embedding_regenerated,
                    "updated_at": datetime.now(UTC).isoformat()
                }
            else:
                return {
                    "status": "not_found",
                    "message": f"Memory {memory_id} not found"
                }

        except ValidationError:
            raise
        except ReadOnlyError:
            raise
        except Exception as e:
            logger.error(f"Failed to update memory {memory_id}: {e}", exc_info=True)
            raise StorageError(f"Failed to update memory: {e}")

    async def list_memories(
        self,
        category: Optional[str] = None,
        context_level: Optional[str] = None,
        scope: Optional[str] = None,
        project_name: Optional[str] = None,
        tags: Optional[List[str]] = None,
        min_importance: float = 0.0,
        max_importance: float = 1.0,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
        limit: int = 20,
        offset: int = 0
    ) -> Dict[str, Any]:
        """
        List and browse memories with filtering and pagination.

        Args:
            category: Filter by preference, fact, event, workflow, or context
            context_level: Filter by USER_PREFERENCE, PROJECT_CONTEXT, SESSION_STATE
            scope: Filter by "global" or "project"
            project_name: Filter by specific project
            tags: Filter by tags (matches ANY tag)
            min_importance: Minimum importance 0.0-1.0
            max_importance: Maximum importance 0.0-1.0
            date_from: Filter created_at >= date (ISO format)
            date_to: Filter created_at <= date (ISO format)
            sort_by: Sort by "created_at", "updated_at", or "importance"
            sort_order: "asc" or "desc"
            limit: Results per page (1-100, default: 20)
            offset: Skip N results (for pagination)

        Returns:
            Dict with memories list, total_count, returned_count, offset, limit, has_more
        """
        try:
            if not (1 <= limit <= 100):
                raise ValidationError("limit must be 1-100")
            if offset < 0:
                raise ValidationError("offset must be >= 0")
            if sort_by not in ["created_at", "updated_at", "importance"]:
                raise ValidationError("Invalid sort_by field")
            if sort_order not in ["asc", "desc"]:
                raise ValidationError("sort_order must be 'asc' or 'desc'")

            filters = {}

            if category:
                filters["category"] = MemoryCategory(category)
            if context_level:
                filters["context_level"] = ContextLevel(context_level)
            if scope:
                filters["scope"] = MemoryScope(scope)
            if project_name:
                filters["project_name"] = project_name
            if tags:
                filters["tags"] = tags

            filters["min_importance"] = min_importance
            filters["max_importance"] = max_importance

            if date_from:
                filters["date_from"] = datetime.fromisoformat(date_from)
            if date_to:
                filters["date_to"] = datetime.fromisoformat(date_to)

            try:
                async with asyncio.timeout(30.0):
                    memories, total_count = await self.store.list_memories(
                        filters=filters,
                        sort_by=sort_by,
                        sort_order=sort_order,
                        limit=limit,
                        offset=offset
                    )
            except TimeoutError:
                logger.error("List memories operation timed out after 30s")
                raise StorageError("List memories operation timed out")

            memory_dicts = [
                {
                    "memory_id": m.id,
                    "content": m.content,
                    "category": m.category.value,
                    "context_level": m.context_level.value,
                    "importance": m.importance,
                    "tags": m.tags,
                    "metadata": m.metadata,
                    "scope": m.scope.value,
                    "project_name": m.project_name,
                    "created_at": m.created_at.isoformat(),
                    "updated_at": m.updated_at.isoformat(),
                }
                for m in memories
            ]

            logger.info(f"Listed {len(memory_dicts)} memories (total {total_count})")

            return {
                "memories": memory_dicts,
                "total_count": total_count,
                "returned_count": len(memory_dicts),
                "offset": offset,
                "limit": limit,
                "has_more": (offset + len(memory_dicts)) < total_count
            }

        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Failed to list memories: {e}", exc_info=True)
            raise StorageError(f"Failed to list memories: {e}")

    async def migrate_memory_scope(
        self,
        memory_id: str,
        new_project_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Migrate a memory to a different scope (global ↔ project).

        Args:
            memory_id: ID of the memory to migrate
            new_project_name: Target project name (None for global scope)

        Returns:
            Dict with status and scope information
        """
        if self.config.advanced.read_only_mode:
            raise ReadOnlyError("Cannot migrate memory in read-only mode")

        try:
            try:
                async with asyncio.timeout(30.0):
                    success = await self.store.migrate_memory_scope(memory_id, new_project_name)
            except TimeoutError:
                logger.error("Migrate memory scope operation timed out after 30s")
                raise StorageError("Migrate memory scope operation timed out")

            if success:
                scope = new_project_name if new_project_name else "global"
                logger.info(f"Migrated memory {memory_id} to scope: {scope}")
                return {
                    "status": "success",
                    "memory_id": memory_id,
                    "scope": scope,
                    "project_name": new_project_name,
                }
            else:
                return {"status": "not_found", "memory_id": memory_id}

        except Exception as e:
            logger.error(f"Failed to migrate memory scope: {e}", exc_info=True)
            raise StorageError(f"Failed to migrate memory scope: {e}")

    async def bulk_reclassify(
        self,
        new_context_level: str,
        project_name: Optional[str] = None,
        current_context_level: Optional[str] = None,
        category: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Bulk reclassify memories by changing their context level.

        Args:
            new_context_level: New context level to set
            project_name: Filter by project name (optional)
            current_context_level: Filter by current context level (optional)
            category: Filter by category (optional)

        Returns:
            Dict with count of updated memories
        """
        if self.config.advanced.read_only_mode:
            raise ReadOnlyError("Cannot reclassify memories in read-only mode")

        try:
            try:
                async with asyncio.timeout(30.0):
                    count = await self.store.bulk_update_context_level(
                        new_context_level=new_context_level,
                        project_name=project_name,
                        current_context_level=current_context_level,
                        category=category,
                    )
            except TimeoutError:
                logger.error("Bulk update context level operation timed out after 30s")
                raise StorageError("Bulk update context level operation timed out")

            logger.info(
                f"Bulk reclassified {count} memories to context level: {new_context_level}"
            )
            return {
                "status": "success",
                "count": count,
                "new_context_level": new_context_level,
                "filters": {
                    "project_name": project_name,
                    "current_context_level": current_context_level,
                    "category": category,
                },
            }

        except Exception as e:
            logger.error(f"Failed to bulk reclassify memories: {e}", exc_info=True)
            raise StorageError(f"Failed to bulk reclassify memories: {e}")

    async def find_duplicate_memories(
        self,
        project_name: Optional[str] = None,
        similarity_threshold: float = 0.95,
    ) -> Dict[str, Any]:
        """
        Find potential duplicate memories based on content similarity.

        Args:
            project_name: Filter by project name (optional)
            similarity_threshold: Similarity threshold (0.0-1.0, default: 0.95)

        Returns:
            Dict with duplicate groups
        """
        try:
            try:
                async with asyncio.timeout(30.0):
                    duplicate_groups = await self.store.find_duplicate_memories(
                        project_name=project_name,
                        similarity_threshold=similarity_threshold,
                    )
            except TimeoutError:
                logger.error("Find duplicate memories operation timed out after 30s")
                raise StorageError("Find duplicate memories operation timed out")

            logger.info(f"Found {len(duplicate_groups)} potential duplicate groups")
            return {
                "status": "success",
                "duplicate_groups": duplicate_groups,
                "total_groups": len(duplicate_groups),
                "similarity_threshold": similarity_threshold,
                "project_name": project_name,
            }

        except Exception as e:
            logger.error(f"Failed to find duplicate memories: {e}", exc_info=True)
            raise StorageError(f"Failed to find duplicate memories: {e}")

    async def merge_memories(
        self,
        memory_ids: List[str],
        keep_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Merge multiple memories into one.

        Args:
            memory_ids: List of memory IDs to merge
            keep_id: ID of memory to keep (uses first if not specified)

        Returns:
            Dict with merged memory ID
        """
        if self.config.advanced.read_only_mode:
            raise ReadOnlyError("Cannot merge memories in read-only mode")

        if len(memory_ids) < 2:
            raise ValidationError("Need at least 2 memories to merge")

        try:
            try:
                async with asyncio.timeout(30.0):
                    merged_id = await self.store.merge_memories(
                        memory_ids=memory_ids,
                        keep_id=keep_id,
                    )
            except TimeoutError:
                logger.error("Merge memories operation timed out after 30s")
                raise StorageError("Merge memories operation timed out")

            logger.info(f"Merged {len(memory_ids)} memories into {merged_id}")
            return {
                "status": "success",
                "merged_id": merged_id,
                "source_ids": memory_ids,
                "count": len(memory_ids),
            }

        except Exception as e:
            logger.error(f"Failed to merge memories: {e}", exc_info=True)
            raise StorageError(f"Failed to merge memories: {e}")

    async def export_memories(
        self,
        output_path: Optional[str] = None,
        format: str = "json",
        category: Optional[str] = None,
        context_level: Optional[str] = None,
        scope: Optional[str] = None,
        project_name: Optional[str] = None,
        tags: Optional[List[str]] = None,
        min_importance: float = 0.0,
        max_importance: float = 1.0,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Export memories to JSON or Markdown format.

        Args:
            output_path: File path to write (if None, returns content as string)
            format: "json" or "markdown"
            category: Filter by category
            context_level: Filter by context level
            scope: Filter by "global" or "project"
            project_name: Filter by project
            tags: Filter by tags
            min_importance: Minimum importance 0.0-1.0
            max_importance: Maximum importance 0.0-1.0
            date_from: Filter created >= date (ISO format)
            date_to: Filter created <= date (ISO format)

        Returns:
            Dict with status, file_path (or content), memory_count
        """
        if format not in ["json", "markdown"]:
            raise ValidationError(f"Invalid export format: {format}. Must be 'json' or 'markdown'")

        try:
            filters = SearchFilters(
                category=MemoryCategory(category) if category else None,
                context_level=ContextLevel(context_level) if context_level else None,
                scope=MemoryScope(scope) if scope else None,
                tags=tags or [],
                min_importance=min_importance,
                max_importance=max_importance,
                date_from=date_from,
                date_to=date_to,
            )

            filters_dict = filters.to_dict() if filters else {}
            if project_name:
                filters_dict['project_name'] = project_name

            try:
                async with asyncio.timeout(30.0):
                    memories_list, total_count = await self.store.list_memories(
                        filters=filters_dict,
                        limit=999999,
                        offset=0
                    )
            except TimeoutError:
                logger.error("List memories for export operation timed out after 30s")
                raise StorageError("List memories for export operation timed out")

            memories = []
            for mem in memories_list:
                memories.append({
                    "id": mem.id,
                    "memory_id": mem.id,
                    "content": mem.content,
                    "category": mem.category.value if hasattr(mem.category, 'value') else mem.category,
                    "context_level": mem.context_level.value if hasattr(mem.context_level, 'value') else mem.context_level,
                    "importance": mem.importance,
                    "tags": mem.tags or [],
                    "metadata": mem.metadata or {},
                    "scope": mem.scope.value if hasattr(mem.scope, 'value') else mem.scope,
                    "project_name": mem.project_name,
                    "created_at": mem.created_at.isoformat() if hasattr(mem.created_at, 'isoformat') else mem.created_at,
                    "updated_at": mem.updated_at.isoformat() if hasattr(mem.updated_at, 'isoformat') else mem.updated_at,
                    "last_accessed": mem.last_accessed.isoformat() if mem.last_accessed and hasattr(mem.last_accessed, 'isoformat') else mem.last_accessed,
                })

            total_count = len(memories)

            if format == "json":
                export_data = {
                    "version": "1.0",
                    "exported_at": datetime.now().isoformat(),
                    "total_count": total_count,
                    "filters": {
                        "category": category,
                        "context_level": context_level,
                        "scope": scope,
                        "project_name": project_name,
                        "tags": tags,
                        "min_importance": min_importance,
                        "max_importance": max_importance,
                        "date_from": date_from,
                        "date_to": date_to,
                    },
                    "memories": memories
                }
                content = json.dumps(export_data, indent=2)
            else:  # markdown
                lines = [
                    "# Memory Export",
                    f"Exported: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                    f"Total Memories: {total_count}",
                    ""
                ]

                for mem in memories:
                    lines.append(f"## Memory: {mem['memory_id']}")
                    lines.append(f"**Category:** {mem['category']}")
                    lines.append(f"**Importance:** {mem['importance']:.2f}")
                    lines.append(f"**Context Level:** {mem['context_level']}")
                    lines.append(f"**Scope:** {mem['scope']}")
                    if mem.get('project_name'):
                        lines.append(f"**Project:** {mem['project_name']}")
                    if mem.get('tags'):
                        lines.append(f"**Tags:** {', '.join(mem['tags'])}")
                    lines.append(f"**Created:** {mem['created_at']}")
                    lines.append(f"**Updated:** {mem.get('updated_at', 'N/A')}")
                    lines.append("")
                    lines.append(mem['content'])
                    lines.append("")
                    lines.append("---")
                    lines.append("")

                content = "\n".join(lines)

            if output_path:
                output_file = Path(output_path).expanduser()
                output_file.parent.mkdir(parents=True, exist_ok=True)
                output_file.write_text(content, encoding='utf-8')

                logger.info(f"Exported {total_count} memories to {output_path} ({format} format)")
                return {
                    "status": "success",
                    "file_path": str(output_file),
                    "format": format,
                    "count": total_count
                }
            else:
                return {
                    "status": "success",
                    "content": content,
                    "format": format,
                    "count": total_count
                }

        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Failed to export memories: {e}", exc_info=True)
            raise StorageError(f"Failed to export memories: {e}")

    async def import_memories(
        self,
        file_path: Optional[str] = None,
        content: Optional[str] = None,
        conflict_mode: str = "skip",
        format: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Import memories from JSON file with conflict resolution.

        Args:
            file_path: Path to JSON file
            content: Direct JSON string (alternative to file_path)
            conflict_mode: "skip", "overwrite", or "merge"
            format: "json" (auto-detected from extension if file_path provided)

        Returns:
            Dict with memories_created, memories_updated, memories_skipped, errors list
        """
        if conflict_mode not in ["skip", "overwrite", "merge"]:
            raise ValidationError(
                f"Invalid conflict mode: {conflict_mode}. Must be 'skip', 'overwrite', or 'merge'"
            )

        if not file_path and not content:
            raise ValidationError("Must provide either file_path or content")

        try:
            if file_path:
                import_file = Path(file_path).expanduser()
                if not import_file.exists():
                    raise ValidationError(f"Import file not found: {file_path}")

                if not format:
                    ext = import_file.suffix.lower()
                    if ext == ".json":
                        format = "json"
                    else:
                        raise ValidationError(
                            f"Cannot auto-detect format from extension: {ext}. Supported: .json"
                        )

                import_content = import_file.read_text(encoding='utf-8')
            else:
                import_content = content
                format = format or "json"

            if format != "json":
                raise ValidationError(f"Only JSON format is supported for import, got: {format}")

            try:
                data = json.loads(import_content)
            except json.JSONDecodeError as e:
                raise ValidationError(f"Invalid JSON format: {e}")

            if "memories" not in data:
                raise ValidationError("Import file must contain 'memories' key")

            if not isinstance(data["memories"], list):
                raise ValidationError("'memories' must be a list")

            memories = data["memories"]
            created_count = 0
            updated_count = 0
            skipped_count = 0
            errors = []

            for idx, mem_data in enumerate(memories):
                try:
                    mem_id = mem_data.get("memory_id") or mem_data.get("id")
                    if not mem_id:
                        errors.append(f"Memory at index {idx}: Missing memory_id/id")
                        continue

                    try:
                        async with asyncio.timeout(30.0):
                            existing = await self.store.get_by_id(mem_id)
                    except TimeoutError:
                        logger.error(f"Get by ID for import timed out after 30s (ID: {mem_id})")
                        errors.append(f"Memory {mem_id}: Timeout during retrieval")
                        continue

                    if existing:
                        if conflict_mode == "skip":
                            skipped_count += 1
                            continue
                        elif conflict_mode == "overwrite":
                            embedding = await self.embedding_generator.generate(mem_data["content"])

                            updates = {
                                "content": mem_data["content"],
                                "category": mem_data.get("category", "fact"),
                                "context_level": mem_data.get("context_level", "SESSION_STATE"),
                                "importance": mem_data.get("importance", 0.5),
                                "tags": mem_data.get("tags", []),
                            }

                            if "metadata" in mem_data:
                                updates["metadata"] = mem_data["metadata"]

                            try:
                                async with asyncio.timeout(30.0):
                                    success = await self.store.update(mem_id, updates, embedding)
                            except TimeoutError:
                                logger.error(f"Update for import timed out after 30s (ID: {mem_id})")
                                errors.append(f"Memory {mem_id}: Timeout during update")
                                continue

                            if success:
                                updated_count += 1
                            else:
                                errors.append(f"Memory {mem_id}: Update failed")
                        elif conflict_mode == "merge":
                            updates = {}

                            if "content" in mem_data and mem_data["content"]:
                                updates["content"] = mem_data["content"]
                                embedding = await self.embedding_generator.generate(mem_data["content"])
                            else:
                                embedding = None

                            for field in ["category", "context_level", "scope", "importance", "tags", "project_name"]:
                                if field in mem_data and mem_data[field] is not None:
                                    updates[field] = mem_data[field]

                            if "metadata" in mem_data and mem_data["metadata"]:
                                updates["metadata"] = mem_data["metadata"]

                            if updates:
                                try:
                                    async with asyncio.timeout(30.0):
                                        success = await self.store.update(mem_id, updates, embedding)
                                except TimeoutError:
                                    logger.error(f"Update for merge import timed out after 30s (ID: {mem_id})")
                                    errors.append(f"Memory {mem_id}: Timeout during merge update")
                                    continue

                                if success:
                                    updated_count += 1
                                else:
                                    errors.append(f"Memory {mem_id}: Merge update failed")
                            else:
                                skipped_count += 1
                    else:
                        embedding = await self.embedding_generator.generate(mem_data["content"])

                        request = StoreMemoryRequest(
                            content=mem_data["content"],
                            category=mem_data.get("category", "fact"),
                            context_level=mem_data.get("context_level", "SESSION_STATE"),
                            importance=mem_data.get("importance", 0.5),
                            tags=mem_data.get("tags", []),
                            metadata=mem_data.get("metadata", {}),
                            scope=mem_data.get("scope", "global"),
                            project_name=mem_data.get("project_name"),
                        )

                        store_metadata = {
                            "id": mem_id,
                            "category": request.category.value if hasattr(request.category, 'value') else request.category,
                            "context_level": request.context_level.value if hasattr(request.context_level, 'value') else request.context_level,
                            "scope": request.scope.value if hasattr(request.scope, 'value') else request.scope,
                            "importance": request.importance,
                            "tags": request.tags,
                            "metadata": request.metadata,
                            "project_name": request.project_name,
                        }

                        try:
                            async with asyncio.timeout(30.0):
                                new_id = await self.store.store(
                                    content=request.content,
                                    embedding=embedding,
                                    metadata=store_metadata,
                                )
                        except TimeoutError:
                            logger.error(f"Store for import timed out after 30s (ID: {mem_id})")
                            errors.append(f"Memory {mem_id}: Timeout during store")
                            continue

                        created_count += 1

                except Exception as e:
                    errors.append(f"Memory at index {idx} (ID: {mem_id if 'mem_id' in locals() else 'unknown'}): {str(e)}")

            logger.info(
                f"Import completed: {created_count} created, {updated_count} updated, "
                f"{skipped_count} skipped, {len(errors)} errors"
            )

            return {
                "status": "success" if len(errors) == 0 else "partial",
                "created": created_count,
                "updated": updated_count,
                "skipped": skipped_count,
                "errors": errors,
                "total_processed": len(memories)
            }

        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Failed to import memories: {e}", exc_info=True)
            raise StorageError(f"Failed to import memories: {e}")

    async def retrieve_preferences(
        self,
        query: str,
        limit: int = 5,
    ) -> Dict[str, Any]:
        """
        Retrieve user preferences and style guidelines.

        Args:
            query: Search query
            limit: Maximum results

        Returns:
            Dict with results and metadata
        """
        return await self.retrieve_memories(
            query=query,
            limit=limit,
            context_level="USER_PREFERENCE",
        )

    async def retrieve_project_context(
        self,
        query: str,
        limit: int = 5,
        project_name: Optional[str] = None,
        use_current_project: bool = True,
    ) -> Dict[str, Any]:
        """
        Retrieve project-specific context and facts.

        Args:
            query: Search query
            limit: Maximum results
            project_name: Optional project name filter
            use_current_project: Whether to use detected project if project_name not provided

        Returns:
            Dict with results and metadata
        """
        filter_project_name = project_name
        if filter_project_name is None and use_current_project:
            filter_project_name = self.project_name

        return await self.retrieve_memories(
            query=query,
            limit=limit,
            context_level="PROJECT_CONTEXT",
            project_name=filter_project_name,
        )

    async def retrieve_session_state(
        self,
        query: str,
        limit: int = 3,
    ) -> Dict[str, Any]:
        """
        Retrieve current session state and temporary context.

        Args:
            query: Search query
            limit: Maximum results (default 3 for recency)

        Returns:
            Dict with results and metadata
        """
        return await self.retrieve_memories(
            query=query,
            limit=limit,
            context_level="SESSION_STATE",
        )

    async def get_dashboard_stats(self) -> Dict[str, Any]:
        """
        Get aggregated statistics for the dashboard.

        Returns:
            Dict with dashboard statistics
        """
        try:
            try:
                async with asyncio.timeout(30.0):
                    total_memories = await self.store.count()
                    projects = await self.store.get_all_projects()
            except TimeoutError:
                logger.error("Count/get_all_projects operation timed out after 30s")
                raise StorageError("Dashboard stats retrieval timed out")

            project_stats = []
            all_categories: Dict[str, int] = {}
            all_lifecycle_states: Dict[str, int] = {}

            for project in projects:
                try:
                    try:
                        async with asyncio.timeout(30.0):
                            stats = await self.store.get_project_stats(project)
                    except TimeoutError:
                        logger.warning(f"Get project stats timed out for {project}")
                        continue

                    project_stats.append(stats)

                    for category, count in stats.get("categories", {}).items():
                        all_categories[category] = all_categories.get(category, 0) + count

                    for state, count in stats.get("lifecycle_states", {}).items():
                        all_lifecycle_states[state] = all_lifecycle_states.get(state, 0) + count

                except Exception as e:
                    logger.warning(f"Failed to get stats for project {project}: {e}")
                    continue

            # Try to count global memories
            # Use store API method for backend compatibility
            try:
                # Create filters to count only global memories (project_name is None)
                # SearchFilters doesn't directly support filtering for None/null values,
                # so we use an empty scope filter (which matches global-scoped memories)
                from src.core.models import SearchFilters, MemoryScope

                # Create a filter for global-scoped memories only
                global_filters = SearchFilters(scope=MemoryScope.GLOBAL)
                try:
                    async with asyncio.timeout(30.0):
                        global_count = await self.store.count(filters=global_filters)
                except TimeoutError:
                    logger.warning("Count global memories timed out after 30s")
                    global_count = 0
            except Exception as e:
                logger.debug(f"Could not count global memories: {e}")
                global_count = 0

            logger.info(
                f"Dashboard stats: {total_memories} total memories, "
                f"{len(projects)} projects, {global_count} global memories"
            )

            return {
                "status": "success",
                "total_memories": total_memories,
                "num_projects": len(projects),
                "global_memories": global_count,
                "projects": project_stats,
                "categories": all_categories,
                "lifecycle_states": all_lifecycle_states,
            }

        except Exception as e:
            logger.error(f"Failed to retrieve dashboard stats: {e}", exc_info=True)
            raise StorageError(f"Failed to retrieve dashboard stats: {e}")

    async def get_recent_activity(
        self,
        limit: int = 20,
        project_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get recent activity including searches and memory additions.

        Args:
            limit: Maximum number of items per category
            project_name: Optional project filter

        Returns:
            Dict with recent activity data
        """
        try:
            try:
                async with asyncio.timeout(30.0):
                    activity = await self.store.get_recent_activity(
                        limit=limit,
                        project_name=project_name,
                    )
            except TimeoutError:
                logger.error("Get recent activity operation timed out after 30s")
                raise StorageError("Get recent activity operation timed out")

            logger.info(
                f"Retrieved recent activity: {len(activity.get('recent_searches', []))} searches, "
                f"{len(activity.get('recent_additions', []))} additions"
            )

            return {
                "status": "success",
                **activity,
            }

        except Exception as e:
            logger.error(f"Failed to retrieve recent activity: {e}", exc_info=True)
            raise StorageError(f"Failed to retrieve recent activity: {e}")
