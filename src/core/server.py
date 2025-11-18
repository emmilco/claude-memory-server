"""MCP Server implementation for Claude Memory RAG."""

import logging
import asyncio
import json
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime
from pathlib import Path
import subprocess

from src.config import ServerConfig, get_config
from src.store import create_memory_store, MemoryStore
from src.embeddings.generator import EmbeddingGenerator
from src.embeddings.cache import EmbeddingCache
from src.core.models import (
    MemoryUnit,
    StoreMemoryRequest,
    QueryRequest,
    MemoryResult,
    RetrievalResponse,
    DeleteMemoryRequest,
    StatusResponse,
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
from src.router import RetrievalGate
from src.memory.usage_tracker import UsageTracker
from src.memory.pruner import MemoryPruner
from src.memory.conversation_tracker import ConversationTracker
from src.memory.query_expander import QueryExpander
from src.memory.proactive_suggester import ProactiveSuggester
from src.search.hybrid_search import HybridSearcher, FusionMethod
from src.memory.repository_registry import RepositoryRegistry
from src.memory.workspace_manager import WorkspaceManager
from src.memory.multi_repository_indexer import MultiRepositoryIndexer
from src.memory.multi_repository_search import MultiRepositorySearch

logger = logging.getLogger(__name__)


class MemoryRAGServer:
    """
    MCP Server for memory and RAG operations.

    Features:
    - Memory storage and retrieval with vector search
    - Context-level stratification (USER_PREFERENCE, PROJECT_CONTEXT, SESSION_STATE)
    - Qdrant or SQLite backend
    - Embedding caching
    - Read-only mode support
    - Project detection from git
    """

    def __init__(self, config: Optional[ServerConfig] = None):
        """
        Initialize the MCP server.

        Args:
            config: Server configuration. If None, uses global config.
        """
        if config is None:
            config = get_config()

        self.config = config
        self.project_name = self._detect_project()

        logger.info("Initializing Claude Memory RAG Server")
        logger.info(f"Storage backend: {config.storage_backend}")
        logger.info(f"Read-only mode: {config.read_only_mode}")
        logger.info(f"Project: {self.project_name or 'global'}")

        # Initialize components
        self.store: Optional[MemoryStore] = None
        self.embedding_generator: Optional[EmbeddingGenerator] = None
        self.embedding_cache: Optional[EmbeddingCache] = None
        self.retrieval_gate: Optional[RetrievalGate] = None
        self.usage_tracker: Optional[UsageTracker] = None
        self.pruner: Optional[MemoryPruner] = None
        self.conversation_tracker: Optional[ConversationTracker] = None
        self.query_expander: Optional[QueryExpander] = None
        self.proactive_suggester: Optional[ProactiveSuggester] = None
        self.hybrid_searcher: Optional[HybridSearcher] = None
        self.cross_project_consent: Optional = None  # Cross-project consent manager
        self.project_context_detector: Optional = None  # Project context detector
        self.scheduler = None  # APScheduler instance

        # Multi-repository components
        self.repository_registry: Optional = None  # Repository registry
        self.workspace_manager: Optional = None  # Workspace manager
        self.multi_repo_indexer: Optional = None  # Multi-repository indexer
        self.multi_repo_search: Optional = None  # Multi-repository search

        # Statistics
        self.stats = {
            # Core operations
            "memories_stored": 0,
            "memories_retrieved": 0,
            "memories_deleted": 0,
            "queries_processed": 0,
            
            # Performance metrics
            "total_query_time_ms": 0.0,
            "total_store_time_ms": 0.0,
            "total_retrieval_time_ms": 0.0,
            
            # Cache metrics
            "cache_hits": 0,
            "cache_misses": 0,
            
            # Error tracking
            "embedding_generation_errors": 0,
            "storage_errors": 0,
            "retrieval_errors": 0,
            "validation_errors": 0,

            # Retrieval gate metrics
            "queries_gated": 0,
            "queries_retrieved": 0,
            "estimated_tokens_saved": 0,

            # Timestamps
            "server_start_time": datetime.now().isoformat(),
            "last_query_time": None,
        }

    async def initialize(self) -> None:
        """Initialize async components."""
        try:
            # Initialize store
            self.store = create_memory_store(config=self.config)
            await self.store.initialize()

            # Wrap in read-only wrapper if needed
            if self.config.read_only_mode:
                from src.store.readonly_wrapper import ReadOnlyStoreWrapper
                self.store = ReadOnlyStoreWrapper(self.store)
                logger.info("Read-only mode enabled")

            # Initialize embedding generator
            self.embedding_generator = EmbeddingGenerator(self.config)
            
            # Preload embedding model on startup to avoid delay on first query
            await self.embedding_generator.initialize()

            # Initialize embedding cache
            self.embedding_cache = EmbeddingCache(self.config)

            # Initialize retrieval gate if enabled
            if self.config.enable_retrieval_gate:
                self.retrieval_gate = RetrievalGate(
                    threshold=self.config.retrieval_gate_threshold
                )
                logger.info(
                    f"Retrieval gate enabled (threshold: {self.config.retrieval_gate_threshold})"
                )
            else:
                self.retrieval_gate = None
                logger.info("Retrieval gate disabled")

            # Initialize usage tracker if enabled
            if self.config.enable_usage_tracking:
                self.usage_tracker = UsageTracker(self.config, self.store)
                await self.usage_tracker.start()
                logger.info("Usage tracking enabled")
            else:
                self.usage_tracker = None
                logger.info("Usage tracking disabled")

            # Initialize pruner
            self.pruner = MemoryPruner(self.config, self.store)

            # Initialize background scheduler for auto-pruning
            if self.config.enable_auto_pruning:
                await self._start_pruning_scheduler()
                logger.info(
                    f"Auto-pruning enabled (schedule: {self.config.pruning_schedule})"
                )
            else:
                logger.info("Auto-pruning disabled")

            # Initialize conversation tracker if enabled
            if self.config.enable_conversation_tracking:
                self.conversation_tracker = ConversationTracker(self.config)
                await self.conversation_tracker.start()
                logger.info("Conversation tracking enabled")

                # Initialize query expander (requires embedding generator)
                self.query_expander = QueryExpander(self.config, self.embedding_generator)
                logger.info("Query expansion enabled")

                # Initialize proactive suggester (requires conversation tracker and embedding generator)
                self.proactive_suggester = ProactiveSuggester(
                    store=self.store,
                    embedding_generator=self.embedding_generator,
                    conversation_tracker=self.conversation_tracker,
                    confidence_threshold=0.85,
                    max_suggestions=5,
                )
                logger.info("Proactive suggester initialized")
            else:
                self.conversation_tracker = None
                self.query_expander = None
                self.proactive_suggester = None
                logger.info("Conversation tracking disabled")

            # Initialize hybrid searcher if enabled
            if self.config.enable_hybrid_search:
                fusion_method_map = {
                    "weighted": FusionMethod.WEIGHTED,
                    "rrf": FusionMethod.RRF,
                    "cascade": FusionMethod.CASCADE,
                }
                fusion_method = fusion_method_map.get(
                    self.config.hybrid_fusion_method.lower(),
                    FusionMethod.WEIGHTED
                )
                self.hybrid_searcher = HybridSearcher(
                    alpha=self.config.hybrid_search_alpha,
                    fusion_method=fusion_method,
                    bm25_k1=self.config.bm25_k1,
                    bm25_b=self.config.bm25_b,
                )
                logger.info(
                    f"Hybrid search enabled (method: {self.config.hybrid_fusion_method}, "
                    f"alpha: {self.config.hybrid_search_alpha})"
                )
            else:
                self.hybrid_searcher = None
                logger.info("Hybrid search disabled")

            # Initialize project context detector
            from src.memory.project_context import ProjectContextDetector
            self.project_context_detector = ProjectContextDetector(config=self.config.__dict__)
            logger.info("Project context detector initialized")

            # Initialize multi-repository components if enabled
            if self.config.enable_multi_repository:
                # Initialize repository registry
                self.repository_registry = RepositoryRegistry(self.config.repository_storage_path)

                # Initialize workspace manager
                self.workspace_manager = WorkspaceManager(
                    self.config.workspace_storage_path,
                    self.repository_registry
                )

                # Initialize multi-repository indexer
                self.multi_repo_indexer = MultiRepositoryIndexer(
                    repository_registry=self.repository_registry,
                    workspace_manager=self.workspace_manager,
                    store=self.store,
                    embedding_generator=self.embedding_generator,
                    config=self.config,
                    max_concurrent_repos=getattr(self.config, 'multi_repo_max_parallel', 3)
                )
                await self.multi_repo_indexer.initialize()

                # Initialize multi-repository search
                self.multi_repo_search = MultiRepositorySearch(
                    repository_registry=self.repository_registry,
                    workspace_manager=self.workspace_manager,
                    store=self.store,
                    embedding_generator=self.embedding_generator,
                    config=self.config
                )
                await self.multi_repo_search.initialize()

                logger.info("Multi-repository support enabled")
            else:
                self.repository_registry = None
                self.workspace_manager = None
                self.multi_repo_indexer = None
                self.multi_repo_search = None
                logger.info("Multi-repository support disabled")

            # Initialize cross-project consent manager if enabled
            if self.config.enable_cross_project_search:
                from src.memory.cross_project_consent import CrossProjectConsent
                self.cross_project_consent = CrossProjectConsent(
                    self.config.cross_project_opt_in_file
                )
                opted_in_count = len(self.cross_project_consent.get_opted_in_projects())
                logger.info(
                    f"Cross-project search enabled (default: {self.config.cross_project_default_mode}, "
                    f"opted-in projects: {opted_in_count})"
                )
            else:
                self.cross_project_consent = None
                logger.info("Cross-project search disabled")

            logger.info("Server initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize server: {e}")
            raise

    def _detect_project(self) -> Optional[str]:
        """
        Detect current project from git repository.

        Returns:
            str: Project name (git repo name), or None if not in a git repo.
        """
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                capture_output=True,
                text=True,
                timeout=2,
                check=False,
            )
            if result.returncode == 0:
                project_path = result.stdout.strip()
                return Path(project_path).name
        except (subprocess.TimeoutExpired, FileNotFoundError, Exception) as e:
            logger.debug(f"Failed to detect git project: {e}")
        return None

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
        Store a memory with its embedding.

        Args:
            content: Memory content
            category: Memory category (preference, fact, event, workflow, context)
            scope: Memory scope (global or project)
            project_name: Project name if scope is project
            importance: Importance score (0.0-1.0)
            tags: Optional tags
            metadata: Optional metadata
            context_level: Optional context level (auto-classified if not provided)

        Returns:
            Dict with memory_id and status
        """
        if self.config.read_only_mode:
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

            self.stats["memories_stored"] += 1
            logger.info(f"Stored memory: {memory_id}")

            return {
                "memory_id": memory_id,
                "status": "success",
                "context_level": memory_unit.context_level.value,
            }

        except ValidationError as e:
            logger.error(f"Validation error: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to store memory: {e}")
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
    ) -> Dict[str, Any]:
        """
        Retrieve memories similar to the query with conversation awareness.

        Args:
            query: Search query
            limit: Maximum results to return
            context_level: Filter by context level
            scope: Filter by scope
            project_name: Filter by project name
            category: Filter by category
            min_importance: Minimum importance threshold
            tags: Filter by tags
            session_id: Optional conversation session ID for context tracking

        Returns:
            Dict with results and metadata
        """
        try:
            import time
            start_time = time.time()

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
            )

            # Check retrieval gate first (if enabled)
            if self.retrieval_gate is not None:
                gate_decision = self.retrieval_gate.should_retrieve(
                    query=query,
                    expected_results=limit,
                )

                # If gate says skip, return empty results immediately
                if not gate_decision.should_retrieve:
                    query_time_ms = (time.time() - start_time) * 1000
                    self.stats["queries_processed"] += 1
                    self.stats["queries_gated"] += 1

                    # Update gate metrics from the gate itself
                    gate_metrics = self.retrieval_gate.get_metrics()
                    self.stats["estimated_tokens_saved"] = gate_metrics.get("estimated_tokens_saved", 0)

                    response = RetrievalResponse(
                        results=[],
                        total_found=0,
                        query_time_ms=query_time_ms,
                        used_cache=False,
                    )

                    logger.info(
                        f"Query gated (utility: {gate_decision.utility_score:.3f}) - "
                        f"skipped retrieval in {query_time_ms:.2f}ms"
                    )

                    return response.model_dump()

            # Gate approved - proceed with retrieval

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
            results = await self.store.retrieve(
                query_embedding=query_embedding,
                filters=filters if any(filters.to_dict().values()) else None,
                limit=fetch_limit,
            )

            # Apply deduplication if session provided
            if session_id and shown_memory_ids:
                # Filter out already-shown memories
                filtered_results = [
                    (memory, score) for memory, score in results
                    if memory.id not in shown_memory_ids
                ]

                # Trim to requested limit
                results = filtered_results[:request.limit]

                if filtered_results != results[:len(filtered_results)]:
                    logger.debug(
                        f"Deduplication: filtered {len(results) - len(filtered_results)} "
                        f"shown memories"
                    )

            # Update stats for successful retrieval
            self.stats["queries_retrieved"] += 1

            # Apply composite ranking if usage tracking is enabled
            if self.usage_tracker and self.config.enable_usage_tracking:
                reranked_results = []

                for memory, similarity_score in results:
                    # Get usage stats for this memory
                    usage_stats = await self.usage_tracker.get_usage_stats(memory.id)

                    # Calculate composite score
                    if usage_stats:
                        composite_score = self.usage_tracker.calculate_composite_score(
                            similarity_score=similarity_score,
                            created_at=memory.created_at,
                            last_used=datetime.fromisoformat(usage_stats["last_used"]) if usage_stats.get("last_used") else None,
                            use_count=usage_stats.get("use_count", 0),
                        )
                    else:
                        # No usage stats yet - use similarity score only
                        composite_score = similarity_score

                    reranked_results.append((memory, composite_score, similarity_score))

                # Sort by composite score
                reranked_results.sort(key=lambda x: x[1], reverse=True)

                # Track usage for all retrieved memories (asynchronously)
                memory_ids = [memory.id for memory, _, _ in reranked_results]
                scores = [comp_score for _, comp_score, _ in reranked_results]
                await self.usage_tracker.record_batch(memory_ids, scores)

                # Use reranked results
                results = [(memory, composite_score) for memory, composite_score, _ in reranked_results]

            # Convert to response format
            # Clamp scores to [0, 1] range to handle floating point precision issues
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
                used_cache=False,  # TODO: Track cache usage
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
                    query_embedding=query_embedding if self.config.enable_conversation_tracking else None,
                )
                logger.debug(f"Tracked {len(results_shown)} results in session {session_id}")

            return response.model_dump()

        except Exception as e:
            logger.error(f"Failed to retrieve memories: {e}")
            raise RetrievalError(f"Failed to retrieve memories: {e}")

    async def suggest_memories(
        self,
        session_id: str,
        max_suggestions: Optional[int] = None,
        confidence_threshold: Optional[float] = None,
        include_code: bool = True,
        project_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Proactively suggest relevant memories based on conversation context.

        Analyzes recent queries in the conversation session to detect user intent
        and suggests relevant memories and code without requiring explicit queries.

        Args:
            session_id: Conversation session ID for context analysis
            max_suggestions: Maximum suggestions to return (default: 5)
            confidence_threshold: Minimum confidence score 0-1 (default: 0.85)
            include_code: Include code search results (default: True)
            project_name: Filter suggestions by project name (optional)

        Returns:
            Dict with suggestions, detected intent, and metadata

        Raises:
            ValidationError: If session_id is missing or proactive suggester disabled
            RetrievalError: If suggestion generation fails
        """
        if not self.proactive_suggester:
            raise ValidationError(
                "Proactive suggestions are disabled. "
                "Enable conversation tracking to use this feature."
            )

        try:
            # Generate suggestions
            response = await self.proactive_suggester.suggest_memories(
                session_id=session_id,
                max_suggestions=max_suggestions,
                confidence_threshold=confidence_threshold,
                include_code=include_code,
                project_name=project_name or self.project_name,
            )

            # Convert to dict for MCP response
            return {
                "suggestions": [
                    {
                        "memory_id": s.memory_id,
                        "content": s.content,
                        "confidence": s.confidence,
                        "reason": s.reason,
                        "source_type": s.source_type,
                        "relevance_factors": {
                            "semantic_similarity": s.relevance_factors.semantic_similarity,
                            "recency": s.relevance_factors.recency,
                            "importance": s.relevance_factors.importance,
                            "context_match": s.relevance_factors.context_match,
                        },
                        "metadata": s.metadata,
                    }
                    for s in response.suggestions
                ],
                "detected_intent": {
                    "intent_type": response.detected_intent.intent_type,
                    "keywords": response.detected_intent.keywords,
                    "confidence": response.detected_intent.confidence,
                    "search_query": response.detected_intent.search_query,
                },
                "confidence_threshold": response.confidence_threshold,
                "total_suggestions": response.total_suggestions,
                "session_id": response.session_id,
            }

        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Failed to generate suggestions: {e}")
            raise RetrievalError(f"Failed to generate suggestions: {e}")

    async def delete_memory(self, memory_id: str) -> Dict[str, Any]:
        """
        Delete a memory by ID.

        Args:
            memory_id: Memory ID to delete

        Returns:
            Dict with status
        """
        if self.config.read_only_mode:
            raise ReadOnlyError("Cannot delete memory in read-only mode")

        try:
            request = DeleteMemoryRequest(memory_id=memory_id)
            success = await self.store.delete(request.memory_id)

            if success:
                self.stats["memories_deleted"] += 1
                logger.info(f"Deleted memory: {memory_id}")
                return {"status": "success", "memory_id": memory_id}
            else:
                return {"status": "not_found", "memory_id": memory_id}

        except Exception as e:
            logger.error(f"Failed to delete memory: {e}")
            raise StorageError(f"Failed to delete memory: {e}")

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
        List memories with filtering, sorting, and pagination.

        Args:
            category: Filter by category (optional)
            context_level: Filter by context level (optional)
            scope: Filter by scope (global/project) (optional)
            project_name: Filter by project (optional)
            tags: Filter by tags - matches ANY tag (optional)
            min_importance: Minimum importance (default 0.0)
            max_importance: Maximum importance (default 1.0)
            date_from: Filter by created_at >= date (ISO format) (optional)
            date_to: Filter by created_at <= date (ISO format) (optional)
            sort_by: Sort field (created_at, updated_at, importance)
            sort_order: Sort order (asc, desc)
            limit: Max results to return (1-100, default 20)
            offset: Number of results to skip (default 0)

        Returns:
            {
                "memories": List[memory dict],
                "total_count": int,
                "returned_count": int,
                "offset": int,
                "limit": int,
                "has_more": bool
            }

        Raises:
            ValidationError: If parameters are invalid
            StorageError: If listing fails
        """
        try:
            # Validate parameters
            if not (1 <= limit <= 100):
                raise ValidationError("limit must be 1-100")
            if offset < 0:
                raise ValidationError("offset must be >= 0")
            if sort_by not in ["created_at", "updated_at", "importance"]:
                raise ValidationError("Invalid sort_by field")
            if sort_order not in ["asc", "desc"]:
                raise ValidationError("sort_order must be 'asc' or 'desc'")

            # Build filters dict
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

            # Query store
            memories, total_count = await self.store.list_memories(
                filters=filters,
                sort_by=sort_by,
                sort_order=sort_order,
                limit=limit,
                offset=offset
            )

            # Convert to dicts
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
            logger.error(f"Failed to list memories: {e}")
            raise StorageError(f"Failed to list memories: {e}")

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
            output_path: Optional file path to write export. If None, returns content as string.
            format: Export format - "json" or "markdown"
            category: Filter by category
            context_level: Filter by context level
            scope: Filter by scope
            project_name: Filter by project
            tags: Filter by tags (must have all)
            min_importance: Minimum importance (0.0-1.0)
            max_importance: Maximum importance (0.0-1.0)
            date_from: Filter memories created after this date (ISO format)
            date_to: Filter memories created before this date (ISO format)

        Returns:
            Dict with status, file_path/content, and count

        Raises:
            ValidationError: If format is invalid
            StorageError: If export fails
        """
        # Validate format
        if format not in ["json", "markdown"]:
            raise ValidationError(f"Invalid export format: {format}. Must be 'json' or 'markdown'")

        try:
            # Get all matching memories using list_memories (no limit, get all)
            result = await self.list_memories(
                category=category,
                context_level=context_level,
                scope=scope,
                project_name=project_name,
                tags=tags,
                min_importance=min_importance,
                max_importance=max_importance,
                date_from=date_from,
                date_to=date_to,
                sort_by="created_at",
                sort_order="asc",
                limit=10000,  # Large limit to get all memories
                offset=0
            )

            memories = result["memories"]
            total_count = result["total_count"]

            # Generate export content based on format
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

            # Write to file or return content
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
            logger.error(f"Failed to export memories: {e}")
            raise StorageError(f"Failed to export memories: {e}")

    async def import_memories(
        self,
        file_path: Optional[str] = None,
        content: Optional[str] = None,
        conflict_mode: str = "skip",
        format: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Import memories from JSON file or content.

        Args:
            file_path: Path to import file (JSON format)
            content: Direct JSON content string (alternative to file_path)
            conflict_mode: How to handle existing memories - "skip", "overwrite", or "merge"
            format: File format - "json" (auto-detected from extension if not provided)

        Returns:
            Dict with import summary (created, updated, skipped, errors)

        Raises:
            ValidationError: If file doesn't exist, format invalid, or conflict_mode invalid
            StorageError: If import fails
        """
        # Validate conflict mode
        if conflict_mode not in ["skip", "overwrite", "merge"]:
            raise ValidationError(
                f"Invalid conflict mode: {conflict_mode}. Must be 'skip', 'overwrite', or 'merge'"
            )

        # Validate input
        if not file_path and not content:
            raise ValidationError("Must provide either file_path or content")

        try:
            # Load content from file or use provided content
            if file_path:
                import_file = Path(file_path).expanduser()
                if not import_file.exists():
                    raise ValidationError(f"Import file not found: {file_path}")

                # Auto-detect format from extension
                if not format:
                    ext = import_file.suffix.lower()
                    if ext == ".json":
                        format = "json"
                    else:
                        raise ValidationError(
                            f"Cannot auto-detect format from extension: {ext}. "
                            "Supported: .json"
                        )

                import_content = import_file.read_text(encoding='utf-8')
            else:
                import_content = content
                format = format or "json"

            # Validate format
            if format != "json":
                raise ValidationError(f"Only JSON format is supported for import, got: {format}")

            # Parse JSON
            try:
                data = json.loads(import_content)
            except json.JSONDecodeError as e:
                raise ValidationError(f"Invalid JSON format: {e}")

            # Validate schema
            if "memories" not in data:
                raise ValidationError("Import file must contain 'memories' key")

            if not isinstance(data["memories"], list):
                raise ValidationError("'memories' must be a list")

            memories = data["memories"]
            created_count = 0
            updated_count = 0
            skipped_count = 0
            errors = []

            # Process each memory
            for idx, mem_data in enumerate(memories):
                try:
                    # Extract memory ID
                    mem_id = mem_data.get("memory_id") or mem_data.get("id")
                    if not mem_id:
                        errors.append(f"Memory at index {idx}: Missing memory_id/id")
                        continue

                    # Check if memory exists
                    existing = await self.store.get_by_id(mem_id)

                    if existing:
                        # Handle existing memory based on conflict mode
                        if conflict_mode == "skip":
                            skipped_count += 1
                            continue

                        elif conflict_mode == "overwrite":
                            # Generate embedding for new content
                            embedding = await self.embedding_gen.generate(mem_data["content"])

                            # Build metadata
                            metadata = {
                                "category": mem_data.get("category", "general"),
                                "context_level": mem_data.get("context_level", "SESSION"),
                                "scope": mem_data.get("scope", "global"),
                                "importance": mem_data.get("importance", 0.5),
                                "tags": mem_data.get("tags", []),
                                "created_at": mem_data.get("created_at", datetime.now().isoformat()),
                                "updated_at": datetime.now().isoformat(),
                            }

                            # Add optional fields
                            if "project_name" in mem_data:
                                metadata["project_name"] = mem_data["project_name"]
                            if "metadata" in mem_data:
                                metadata["metadata"] = mem_data["metadata"]

                            # Update using store's update method
                            success = await self.store.update(mem_id, {
                                "content": mem_data["content"],
                                "embedding": embedding,
                                "metadata": metadata
                            })

                            if success:
                                updated_count += 1
                            else:
                                errors.append(f"Memory {mem_id}: Update failed")

                        elif conflict_mode == "merge":
                            # Merge: update only non-null fields
                            updates = {}

                            if "content" in mem_data and mem_data["content"]:
                                updates["content"] = mem_data["content"]
                                updates["embedding"] = await self.embedding_gen.generate(mem_data["content"])

                            # Merge metadata
                            metadata_updates = {}
                            for field in ["category", "context_level", "scope", "importance", "tags", "project_name"]:
                                if field in mem_data and mem_data[field] is not None:
                                    metadata_updates[field] = mem_data[field]

                            if metadata_updates:
                                metadata_updates["updated_at"] = datetime.now().isoformat()
                                updates["metadata"] = metadata_updates

                            if updates:
                                success = await self.store.update(mem_id, updates)
                                if success:
                                    updated_count += 1
                                else:
                                    errors.append(f"Memory {mem_id}: Merge update failed")
                            else:
                                skipped_count += 1

                    else:
                        # Memory doesn't exist - create new
                        embedding = await self.embedding_gen.generate(mem_data["content"])

                        # Build metadata
                        metadata = {
                            "category": mem_data.get("category", "general"),
                            "context_level": mem_data.get("context_level", "SESSION"),
                            "scope": mem_data.get("scope", "global"),
                            "importance": mem_data.get("importance", 0.5),
                            "tags": mem_data.get("tags", []),
                            "created_at": mem_data.get("created_at", datetime.now().isoformat()),
                            "updated_at": datetime.now().isoformat(),
                        }

                        # Add optional fields
                        if "project_name" in mem_data:
                            metadata["project_name"] = mem_data["project_name"]
                        if "metadata" in mem_data:
                            metadata["metadata"] = mem_data["metadata"]

                        # Store new memory
                        new_id = await self.store.store(
                            content=mem_data["content"],
                            embedding=embedding,
                            metadata=metadata
                        )

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
            logger.error(f"Failed to import memories: {e}")
            raise StorageError(f"Failed to import memories: {e}")

    async def retrieve_preferences(
        self,
        query: str,
        limit: int = 5,
    ) -> Dict[str, Any]:
        """
        Retrieve user preferences and style guidelines.

        This is a specialized retrieval that only returns USER_PREFERENCE
        context level memories.

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

        This is a specialized retrieval that only returns PROJECT_CONTEXT
        context level memories.

        Args:
            query: Search query
            limit: Maximum results
            project_name: Optional project name filter. If not provided and
                         use_current_project is True, uses detected project.
            use_current_project: Whether to use detected project if project_name not provided

        Returns:
            Dict with results and metadata
        """
        # Use detected project if not specified and use_current_project is True
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

        This is a specialized retrieval that only returns SESSION_STATE
        context level memories, sorted by recency.

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

    async def start_conversation_session(
        self,
        description: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Start a new conversation session for context tracking.

        Call this at the beginning of a new conversation to enable:
        - Deduplication of previously shown context
        - Conversation-aware query expansion
        - Better context relevance over time

        Args:
            description: Optional description of this conversation

        Returns:
            Dict with session_id and status
        """
        if not self.conversation_tracker:
            return {
                "error": "Conversation tracking is disabled",
                "status": "disabled"
            }

        try:
            session_id = self.conversation_tracker.create_session(description)

            logger.info(f"Started conversation session: {session_id}")

            return {
                "session_id": session_id,
                "status": "created",
                "description": description,
            }

        except Exception as e:
            logger.error(f"Failed to start conversation session: {e}")
            return {
                "error": str(e),
                "status": "failed"
            }

    async def end_conversation_session(
        self,
        session_id: str
    ) -> Dict[str, Any]:
        """
        End and cleanup a conversation session.

        Args:
            session_id: Session ID to end

        Returns:
            Dict with status
        """
        if not self.conversation_tracker:
            return {
                "error": "Conversation tracking is disabled",
                "status": "disabled"
            }

        try:
            success = self.conversation_tracker.end_session(session_id)

            if success:
                logger.info(f"Ended conversation session: {session_id}")
                return {"status": "ended"}
            else:
                return {
                    "error": "Session not found",
                    "status": "not_found"
                }

        except Exception as e:
            logger.error(f"Failed to end conversation session: {e}")
            return {
                "error": str(e),
                "status": "failed"
            }

    async def list_conversation_sessions(self) -> Dict[str, Any]:
        """
        List all active conversation sessions.

        Returns:
            Dict with sessions list and stats
        """
        if not self.conversation_tracker:
            return {
                "error": "Conversation tracking is disabled",
                "sessions": []
            }

        try:
            sessions = self.conversation_tracker.get_all_sessions()
            stats = self.conversation_tracker.get_stats()

            return {
                "sessions": sessions,
                "stats": stats,
                "status": "success"
            }

        except Exception as e:
            logger.error(f"Failed to list conversation sessions: {e}")
            return {
                "error": str(e),
                "sessions": []
            }

    def _analyze_search_quality(
        self,
        results: List[Dict[str, Any]],
        query: str,
        project_name: Optional[str],
    ) -> Dict[str, Any]:
        """
        Analyze search result quality and provide helpful suggestions.

        Args:
            results: Search results with relevance scores
            query: Original search query
            project_name: Project being searched

        Returns:
            Dict with quality assessment, confidence level, suggestions, and keyword matches
        """
        # Extract query keywords (simple word tokenization)
        query_keywords = [w.lower() for w in query.split() if len(w) > 2]

        if not results:
            suggestions = [
                f"Verify that code has been indexed for project '{project_name or 'current'}'"
            ]

            # Check if we should suggest other projects
            if project_name:
                suggestions.append(f"Did you mean to search in a different project?")

            suggestions.extend([
                "Try a different query with more general terms",
                "Consider using related keywords or synonyms",
                "Run: python -m src.cli index ./your-project",
            ])

            return {
                "quality": "no_results",
                "confidence": 0.0,
                "interpretation": "No results found",
                "suggestions": suggestions,
                "matched_keywords": [],
            }

        # Analyze score distribution
        scores = [r["relevance_score"] for r in results]
        avg_score = sum(scores) / len(scores)
        max_score = max(scores)
        min_score = min(scores)

        # Determine quality level based on scores
        if max_score >= 0.85:
            quality = "excellent"
            confidence = max_score
            interpretation = f"Found {len(results)} highly relevant results (confidence: {max_score:.0%})"
            suggestions = []
        elif max_score >= 0.70:
            quality = "good"
            confidence = max_score
            interpretation = f"Found {len(results)} relevant results (confidence: {max_score:.0%})"
            suggestions = []
        elif max_score >= 0.55:
            quality = "moderate"
            confidence = max_score
            interpretation = f"Found {len(results)} potentially relevant results (confidence: {max_score:.0%})"
            suggestions = [
                "Consider refining your query to be more specific",
                "Try including keywords from your codebase",
            ]
        else:
            quality = "low"
            confidence = max_score
            interpretation = f"Found {len(results)} results with low relevance (confidence: {max_score:.0%})"
            suggestions = [
                "Query may be too vague or not matching indexed code",
                "Try a more specific query describing the functionality",
                "Verify the code you're looking for has been indexed",
            ]

        # Add suggestions based on score distribution
        if max_score - min_score > 0.3:
            suggestions.append(
                f"Results vary in relevance ({min_score:.0%}-{max_score:.0%}). "
                "Top results are most relevant."
            )

        # Analyze keyword matches in results
        matched_keywords = []
        for keyword in query_keywords:
            for result in results[:3]:  # Check top 3 results
                content = result.get("code", result.get("content", "")).lower()
                if keyword in content:
                    matched_keywords.append(keyword)
                    break

        # Add keyword match info to interpretation
        if matched_keywords:
            keyword_info = f" (matched keywords: {', '.join(matched_keywords)})"
        else:
            keyword_info = " (matched semantically)"

        return {
            "quality": quality,
            "confidence": confidence,
            "interpretation": interpretation + keyword_info,
            "suggestions": suggestions,
            "matched_keywords": matched_keywords,
        }

    @staticmethod
    def _get_confidence_label(score: float) -> str:
        """
        Convert a relevance score to a human-readable confidence label.

        Args:
            score: Relevance score between 0.0 and 1.0

        Returns:
            Confidence label: "excellent", "good", or "weak"
        """
        if score > 0.8:
            return "excellent"
        elif score >= 0.6:
            return "good"
        else:
            return "weak"

    async def search_code(
        self,
        query: str,
        project_name: Optional[str] = None,
        limit: int = 5,
        file_pattern: Optional[str] = None,
        language: Optional[str] = None,
        search_mode: str = "semantic",
    ) -> Dict[str, Any]:
        """
        Search indexed code semantically, with keyword search, or hybrid.

        This searches through indexed code semantic units (functions, classes)
        and returns relevant code snippets with file locations.

        Args:
            query: Search query (e.g., "authentication logic", "database connection")
            project_name: Optional project name filter (uses current project if not specified)
            limit: Maximum number of results (default 5)
            file_pattern: Optional file path pattern filter (e.g., "*/auth/*")
            language: Optional language filter (e.g., "python", "javascript")
            search_mode: Search mode - "semantic" (default), "keyword", or "hybrid"

        Returns:
            Dict with code search results including file paths, line numbers, and code snippets
        """
        try:
            import time
            start_time = time.time()

            # Validate search mode
            if search_mode not in ["semantic", "keyword", "hybrid"]:
                raise ValidationError(f"Invalid search_mode: {search_mode}. Must be 'semantic', 'keyword', or 'hybrid'")

            # Handle empty query
            if not query or not query.strip():
                logger.warning("Empty query provided, returning empty results")
                return {
                    "status": "success",
                    "results": [],
                    "total_found": 0,
                    "query": query,
                    "project_name": project_name or self.project_name,
                    "search_mode": search_mode,
                    "query_time_ms": 0.0,
                    "quality": "poor",
                    "confidence": "very_low",
                    "suggestions": ["Provide a search query with keywords or description"],
                    "interpretation": "Empty query - no search performed",
                    "matched_keywords": [],
                }

            # Use current project if not specified
            filter_project_name = project_name or self.project_name

            # Generate query embedding
            query_embedding = await self._get_embedding(query)

            # Build filters for code search
            filters = SearchFilters(
                scope=MemoryScope.PROJECT,
                project_name=filter_project_name,
                category=MemoryCategory.CONTEXT,
                context_level=ContextLevel.PROJECT_CONTEXT,
                tags=["code"],  # Code semantic units are tagged with "code"
            )

            # Retrieve from store based on search mode
            if search_mode == "hybrid" and self.hybrid_searcher:
                # For hybrid search, retrieve more results to have a larger pool for BM25
                retrieval_limit = max(limit * 3, 50)  # Get 3x more for hybrid ranking

                vector_results = await self.store.retrieve(
                    query_embedding=query_embedding,
                    filters=filters,
                    limit=retrieval_limit,
                )

                # Build BM25 index from retrieved documents
                documents = [memory.content for memory, _ in vector_results]
                memory_units = [memory for memory, _ in vector_results]

                # Index documents for BM25 search
                self.hybrid_searcher.index_documents(documents, memory_units)

                # Perform hybrid search
                hybrid_results = self.hybrid_searcher.hybrid_search(
                    query=query,
                    vector_results=vector_results,
                    limit=limit,
                )

                # Convert to standard (memory, score) format
                results = [(hr.memory, hr.total_score) for hr in hybrid_results]

                logger.info(
                    f"Hybrid search used (method: {self.config.hybrid_fusion_method}, "
                    f"alpha: {self.config.hybrid_search_alpha})"
                )
            else:
                # Standard semantic search (or fallback if hybrid not available)
                if search_mode == "hybrid":
                    logger.warning("Hybrid search requested but not enabled, falling back to semantic search")

                results = await self.store.retrieve(
                    query_embedding=query_embedding,
                    filters=filters,
                    limit=limit,
                )

            # Format results for code search
            code_results = []
            for memory, score in results:
                # Extract code-specific metadata (stored in nested metadata dict during indexing)
                metadata = memory.metadata or {}
                nested_metadata = metadata if isinstance(metadata, dict) else {}

                # Apply post-filter for file pattern and language if specified
                file_path = nested_metadata.get("file_path", "")
                language_val = nested_metadata.get("language", "")

                if file_pattern and file_pattern not in file_path:
                    continue
                if language and language_val.lower() != language.lower():
                    continue

                relevance_score = min(max(score, 0.0), 1.0)
                confidence_label = self._get_confidence_label(relevance_score)

                code_results.append({
                    "file_path": file_path or "(no path)",
                    "start_line": nested_metadata.get("start_line", 0),
                    "end_line": nested_metadata.get("end_line", 0),
                    "unit_name": nested_metadata.get("unit_name") or nested_metadata.get("name", "(unnamed)"),
                    "unit_type": nested_metadata.get("unit_type", "(unknown type)"),
                    "signature": nested_metadata.get("signature", ""),
                    "language": language_val or "(unknown language)",
                    "code": memory.content,
                    "relevance_score": relevance_score,
                    "confidence_label": confidence_label,
                    "confidence_display": f"{relevance_score:.0%} ({confidence_label})",
                })

            query_time_ms = (time.time() - start_time) * 1000

            logger.info(
                f"Code search: '{query}' found {len(code_results)} results "
                f"in {query_time_ms:.2f}ms (project: {filter_project_name})"
            )

            # Add quality indicators and suggestions
            quality_info = self._analyze_search_quality(code_results, query, filter_project_name)

            # Determine actual search mode used
            actual_search_mode = search_mode
            if search_mode == "hybrid" and not self.hybrid_searcher:
                actual_search_mode = "semantic"  # Fallback

            return {
                "status": "success",
                "results": code_results,
                "total_found": len(code_results),
                "query": query,
                "project_name": filter_project_name,
                "search_mode": actual_search_mode,
                "query_time_ms": query_time_ms,
                "quality": quality_info["quality"],
                "confidence": quality_info["confidence"],
                "suggestions": quality_info["suggestions"],
                "interpretation": quality_info["interpretation"],
                "matched_keywords": quality_info["matched_keywords"],
            }

        except Exception as e:
            logger.error(f"Failed to search code: {e}")
            raise RetrievalError(f"Failed to search code: {e}")

    async def find_similar_code(
        self,
        code_snippet: str,
        project_name: Optional[str] = None,
        limit: int = 10,
        file_pattern: Optional[str] = None,
        language: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Find similar code snippets in the indexed codebase.

        This generates an embedding for the provided code snippet and searches
        for similar code in the index. Great for finding duplicates, similar
        implementations, or code patterns.

        Args:
            code_snippet: The code snippet to find similar matches for
            project_name: Optional project name filter (uses current project if not specified)
            limit: Maximum number of results (default 10)
            file_pattern: Optional file path pattern filter (e.g., "*/auth/*")
            language: Optional language filter (e.g., "python", "javascript")

        Returns:
            Dict with similar code results including file paths, line numbers, and similarity scores
        """
        # Validate input first (before try block to let ValidationError propagate)
        if not code_snippet or not code_snippet.strip():
            raise ValidationError("code_snippet cannot be empty")

        try:
            import time
            start_time = time.time()

            # Use current project if not specified
            filter_project_name = project_name or self.project_name

            # Generate embedding for the code snippet
            code_embedding = await self._get_embedding(code_snippet)

            # Build filters for code search
            filters = SearchFilters(
                scope=MemoryScope.PROJECT,
                project_name=filter_project_name,
                category=MemoryCategory.CONTEXT,
                context_level=ContextLevel.PROJECT_CONTEXT,
                tags=["code"],  # Code semantic units are tagged with "code"
            )

            # Retrieve similar code from store
            results = await self.store.retrieve(
                query_embedding=code_embedding,
                filters=filters,
                limit=limit,
            )

            # Format results for code search
            code_results = []
            for memory, score in results:
                # Extract code-specific metadata (stored in nested metadata dict during indexing)
                metadata = memory.metadata or {}
                nested_metadata = metadata if isinstance(metadata, dict) else {}

                # Apply post-filter for file pattern and language if specified
                file_path = nested_metadata.get("file_path", "")
                language_val = nested_metadata.get("language", "")

                if file_pattern and file_pattern not in file_path:
                    continue
                if language and language_val.lower() != language.lower():
                    continue

                similarity_score = min(max(score, 0.0), 1.0)
                confidence_label = self._get_confidence_label(similarity_score)

                code_results.append({
                    "file_path": file_path or "(no path)",
                    "start_line": nested_metadata.get("start_line", 0),
                    "end_line": nested_metadata.get("end_line", 0),
                    "unit_name": nested_metadata.get("unit_name") or nested_metadata.get("name", "(unnamed)"),
                    "unit_type": nested_metadata.get("unit_type", "(unknown type)"),
                    "signature": nested_metadata.get("signature", ""),
                    "language": language_val or "(unknown language)",
                    "code": memory.content,
                    "similarity_score": similarity_score,
                    "confidence_label": confidence_label,
                    "confidence_display": f"{similarity_score:.0%} ({confidence_label})",
                })

            query_time_ms = (time.time() - start_time) * 1000

            logger.info(
                f"Find similar code: found {len(code_results)} results "
                f"in {query_time_ms:.2f}ms (project: {filter_project_name})"
            )

            # Provide interpretation
            if not code_results:
                interpretation = "No similar code found in the indexed codebase"
                suggestions = [
                    f"Verify that code has been indexed for project '{filter_project_name or 'current'}'",
                    "Try indexing more code: python -m src.cli index ./your-project",
                    "The code snippet might be unique or use different patterns",
                ]
            elif code_results[0]["similarity_score"] >= 0.95:
                interpretation = f"Found {len(code_results)} very similar code snippets (likely duplicates or near-duplicates)"
                suggestions = ["Consider consolidating duplicate code", "These snippets may share significant logic"]
            elif code_results[0]["similarity_score"] >= 0.80:
                interpretation = f"Found {len(code_results)} similar code patterns"
                suggestions = ["These snippets implement similar functionality", "Good candidates for refactoring or code reuse"]
            else:
                interpretation = f"Found {len(code_results)} somewhat related code snippets"
                suggestions = ["These snippets may share some concepts but differ significantly", "Consider if these patterns are applicable to your use case"]

            return {
                "results": code_results,
                "total_found": len(code_results),
                "code_snippet_length": len(code_snippet),
                "project_name": filter_project_name,
                "query_time_ms": query_time_ms,
                "interpretation": interpretation,
                "suggestions": suggestions,
            }

        except Exception as e:
            logger.error(f"Failed to find similar code: {e}")
            raise RetrievalError(f"Failed to find similar code: {e}")

    async def search_all_projects(
        self,
        query: str,
        limit: int = 10,
        file_pattern: Optional[str] = None,
        language: Optional[str] = None,
        search_mode: str = "semantic",
    ) -> Dict[str, Any]:
        """
        Search code across all opted-in projects.

        Implements cross-project learning by searching across multiple
        indexed projects. Respects privacy settings - projects must be
        explicitly opted in via consent manager.

        Args:
            query: Search query (e.g., "authentication logic", "database connection")
            limit: Maximum number of results across all projects (default 10)
            file_pattern: Optional file path pattern filter (e.g., "*/auth/*")
            language: Optional language filter (e.g., "python", "javascript")
            search_mode: Search mode - "semantic" (default), "keyword", or "hybrid"

        Returns:
            Dict with code search results from all projects, grouped by project
        """
        # Check if cross-project search is enabled
        if not self.config.enable_cross_project_search or not self.cross_project_consent:
            raise ValidationError(
                "Cross-project search is disabled. Enable it in config to use this feature."
            )

        try:
            import time
            start_time = time.time()

            # Determine which projects to search
            search_all_mode = self.config.cross_project_default_mode == "all"
            searchable_projects = self.cross_project_consent.get_searchable_projects(
                current_project=self.project_name,
                search_all=search_all_mode
            )

            if not searchable_projects:
                return {
                    "results": [],
                    "total_found": 0,
                    "projects_searched": [],
                    "query": query,
                    "interpretation": "No projects available for cross-project search. Opt in projects first.",
                    "suggestions": [
                        "Use the opt-in tool to enable cross-project search for your projects",
                        "Current project is automatically searchable if it exists"
                    ],
                    "query_time_ms": 0.0,
                }

            # Search each project and collect results
            all_results = []
            for project_name in searchable_projects:
                try:
                    # Search this specific project
                    project_results = await self.search_code(
                        query=query,
                        project_name=project_name,
                        limit=limit,  # Get limit per project, then we'll trim overall
                        file_pattern=file_pattern,
                        language=language,
                        search_mode=search_mode,
                    )

                    # Add project name to each result
                    for result in project_results.get("results", []):
                        result["source_project"] = project_name
                        all_results.append(result)

                except Exception as e:
                    logger.warning(f"Failed to search project '{project_name}': {e}")
                    # Continue searching other projects

            # Sort all results by relevance score (descending)
            all_results.sort(key=lambda r: r.get("relevance_score", 0.0), reverse=True)

            # Limit to top N results across all projects
            final_results = all_results[:limit]

            # Group by project for statistics
            projects_with_results = {}
            for result in final_results:
                project = result.get("source_project")
                if project not in projects_with_results:
                    projects_with_results[project] = 0
                projects_with_results[project] += 1

            query_time_ms = (time.time() - start_time) * 1000

            logger.info(
                f"Cross-project search: '{query}' found {len(final_results)} results "
                f"across {len(projects_with_results)} projects in {query_time_ms:.2f}ms"
            )

            # Generate interpretation
            if not final_results:
                interpretation = f"No results found across {len(searchable_projects)} searched projects"
                suggestions = [
                    "Try a different search query",
                    "Verify that projects have been indexed",
                    f"Searched projects: {', '.join(sorted(searchable_projects))}"
                ]
            elif len(projects_with_results) > 1:
                interpretation = (
                    f"Found {len(final_results)} results across {len(projects_with_results)} projects. "
                    f"Similar patterns exist in multiple codebases - consider code reuse!"
                )
                project_breakdown = [f"{p}: {c} results" for p, c in sorted(projects_with_results.items())]
                suggestions = [
                    "Results show similar implementations across your projects",
                    f"Project breakdown: {', '.join(project_breakdown)}",
                    "Consider extracting common patterns into a shared library"
                ]
            else:
                single_project = list(projects_with_results.keys())[0]
                interpretation = f"Found {len(final_results)} results, all from project '{single_project}'"
                suggestions = [
                    f"This pattern appears unique to {single_project}",
                    "Consider if similar solutions exist in other projects",
                ]

            return {
                "results": final_results,
                "total_found": len(final_results),
                "projects_searched": sorted(searchable_projects),
                "projects_with_results": projects_with_results,
                "query": query,
                "search_mode": search_mode,
                "query_time_ms": query_time_ms,
                "interpretation": interpretation,
                "suggestions": suggestions,
            }

        except Exception as e:
            logger.error(f"Failed to search across projects: {e}")
            raise RetrievalError(f"Failed to search across projects: {e}")

    async def index_codebase(
        self,
        directory_path: str,
        project_name: Optional[str] = None,
        recursive: bool = True,
    ) -> Dict[str, Any]:
        """
        Index a codebase directory for semantic code search.

        This will parse all supported source files in the directory,
        extract semantic units (functions, classes), and store them
        with embeddings for semantic search.

        Args:
            directory_path: Path to directory to index
            project_name: Project name for scoping (uses directory name if not specified)
            recursive: Whether to recursively index subdirectories (default True)

        Returns:
            Dict with indexing statistics
        """
        if self.config.read_only_mode:
            raise ReadOnlyError("Cannot index codebase in read-only mode")

        try:
            from pathlib import Path
            from src.memory.incremental_indexer import IncrementalIndexer
            import time

            start_time = time.time()
            dir_path = Path(directory_path).resolve()

            if not dir_path.exists():
                raise ValueError(f"Directory does not exist: {directory_path}")

            if not dir_path.is_dir():
                raise ValueError(f"Path is not a directory: {directory_path}")

            # Determine project name
            index_project_name = project_name or dir_path.name

            # Create indexer
            indexer = IncrementalIndexer(
                store=self.store,
                embedding_generator=self.embedding_generator,
                config=self.config,
                project_name=index_project_name,
            )

            # Initialize indexer (it will use the same store connection)
            # Skip initialization since store is already initialized
            # await indexer.initialize()

            # Index directory
            logger.info(f"Indexing codebase: {dir_path} (project: {index_project_name})")
            result = await indexer.index_directory(
                dir_path=dir_path,
                recursive=recursive,
                show_progress=True,
            )

            total_time_s = time.time() - start_time

            logger.info(
                f"Indexed {result['total_units']} semantic units from "
                f"{result['indexed_files']} files in {total_time_s:.2f}s"
            )

            return {
                "status": "success",
                "project_name": index_project_name,
                "directory": str(dir_path),
                "files_indexed": result["indexed_files"],
                "units_indexed": result["total_units"],
                "total_time_s": total_time_s,
                "languages": result.get("languages", {}),
            }

        except Exception as e:
            logger.error(f"Failed to index codebase: {e}")
            raise StorageError(f"Failed to index codebase: {e}")

    async def get_file_dependencies(
        self,
        file_path: str,
        project_name: Optional[str] = None,
        include_transitive: bool = False,
    ) -> Dict[str, Any]:
        """
        Get dependencies for a specific file (what it imports).

        Args:
            file_path: File path to query
            project_name: Optional project filter
            include_transitive: If True, include transitive dependencies

        Returns:
            Dict with dependency information
        """
        try:
            from pathlib import Path
            from src.memory.dependency_graph import DependencyGraph

            file_path = str(Path(file_path).resolve())
            filter_project_name = project_name or self.project_name

            # Build dependency graph from stored metadata
            graph = await self._build_dependency_graph(filter_project_name)

            # Get dependencies
            if include_transitive:
                deps = graph.get_all_dependencies(file_path)
            else:
                deps = graph.get_dependencies(file_path)

            # Get import details
            import_details = []
            for dep in deps:
                details = graph.get_import_details(file_path, dep)
                if details:
                    import_details.extend([
                        {
                            "target_file": dep,
                            "module": d["module"],
                            "items": d["items"],
                            "type": d["type"],
                            "line": d["line"],
                        }
                        for d in details
                    ])

            return {
                "file": file_path,
                "project": filter_project_name,
                "dependency_count": len(deps),
                "dependencies": sorted(list(deps)),
                "import_details": import_details,
                "transitive": include_transitive,
            }

        except Exception as e:
            logger.error(f"Failed to get file dependencies: {e}")
            raise RetrievalError(f"Failed to get file dependencies: {e}")

    async def get_file_dependents(
        self,
        file_path: str,
        project_name: Optional[str] = None,
        include_transitive: bool = False,
    ) -> Dict[str, Any]:
        """
        Get dependents for a specific file (what imports it).

        Args:
            file_path: File path to query
            project_name: Optional project filter
            include_transitive: If True, include transitive dependents

        Returns:
            Dict with dependent information
        """
        try:
            from pathlib import Path
            from src.memory.dependency_graph import DependencyGraph

            file_path = str(Path(file_path).resolve())
            filter_project_name = project_name or self.project_name

            # Build dependency graph from stored metadata
            graph = await self._build_dependency_graph(filter_project_name)

            # Get dependents
            if include_transitive:
                deps = graph.get_all_dependents(file_path)
            else:
                deps = graph.get_dependents(file_path)

            return {
                "file": file_path,
                "project": filter_project_name,
                "dependent_count": len(deps),
                "dependents": sorted(list(deps)),
                "transitive": include_transitive,
            }

        except Exception as e:
            logger.error(f"Failed to get file dependents: {e}")
            raise RetrievalError(f"Failed to get file dependents: {e}")

    async def find_dependency_path(
        self,
        source_file: str,
        target_file: str,
        project_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Find import path between two files.

        Args:
            source_file: Source file path
            target_file: Target file path
            project_name: Optional project filter

        Returns:
            Dict with path information
        """
        try:
            from pathlib import Path
            from src.memory.dependency_graph import DependencyGraph

            source_file = str(Path(source_file).resolve())
            target_file = str(Path(target_file).resolve())
            filter_project_name = project_name or self.project_name

            # Build dependency graph from stored metadata
            graph = await self._build_dependency_graph(filter_project_name)

            # Find path
            path = graph.find_path(source_file, target_file)

            if path:
                # Get import details for each edge in the path
                path_details = []
                for i in range(len(path) - 1):
                    src = path[i]
                    tgt = path[i + 1]
                    details = graph.get_import_details(src, tgt)
                    path_details.append({
                        "from": src,
                        "to": tgt,
                        "imports": details,
                    })

                return {
                    "source": source_file,
                    "target": target_file,
                    "path_found": True,
                    "path_length": len(path) - 1,
                    "path": path,
                    "path_details": path_details,
                }
            else:
                return {
                    "source": source_file,
                    "target": target_file,
                    "path_found": False,
                    "message": "No import path exists between these files",
                }

        except Exception as e:
            logger.error(f"Failed to find dependency path: {e}")
            raise RetrievalError(f"Failed to find dependency path: {e}")

    async def get_dependency_stats(
        self,
        project_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get dependency graph statistics for a project.

        Args:
            project_name: Optional project filter

        Returns:
            Dict with dependency statistics
        """
        try:
            from src.memory.dependency_graph import DependencyGraph

            filter_project_name = project_name or self.project_name

            # Build dependency graph from stored metadata
            graph = await self._build_dependency_graph(filter_project_name)

            # Get statistics
            stats = graph.get_statistics()

            # Detect circular dependencies
            cycles = graph.detect_circular_dependencies()

            return {
                "project": filter_project_name,
                "statistics": stats,
                "circular_dependencies": len(cycles),
                "circular_dependency_chains": cycles[:5],  # Limit to first 5
            }

        except Exception as e:
            logger.error(f"Failed to get dependency stats: {e}")
            raise RetrievalError(f"Failed to get dependency stats: {e}")

    async def _build_dependency_graph(
        self,
        project_name: Optional[str]
    ) -> "DependencyGraph":
        """
        Build dependency graph from stored metadata.

        Args:
            project_name: Project to build graph for

        Returns:
            DependencyGraph instance
        """
        from src.memory.dependency_graph import DependencyGraph
        from src.core.models import SearchFilters, MemoryCategory, ContextLevel

        graph = DependencyGraph()

        # Query all code units for this project
        filters = SearchFilters(
            project_name=project_name,
            category=MemoryCategory.CONTEXT,
            context_level=ContextLevel.PROJECT_CONTEXT,
            tags=["code"],
        )

        # Get all code units (use empty embedding to get all)
        # This is a bit of a hack - we need all units, not just similar ones
        # We'll retrieve a large number to get most/all units
        empty_embedding = [0.0] * 384  # Match embedding dimension
        results = await self.store.retrieve(
            query_embedding=empty_embedding,
            filters=filters,
            limit=10000,  # Large limit to get all units
        )

        # Group by file and collect import metadata
        file_imports: Dict[str, List[Dict[str, Any]]] = {}
        for memory, _ in results:
            metadata = memory.metadata
            file_path = metadata.get("file_path")
            imports = metadata.get("imports", [])

            if file_path and imports:
                if file_path not in file_imports:
                    file_imports[file_path] = imports
                # Note: All units from same file have same imports,
                # so we only need to process each file once

        # Add dependencies to graph
        for file_path, imports in file_imports.items():
            graph.add_file_dependencies(file_path, imports)

        return graph

    async def get_status(self) -> Dict[str, Any]:
        """
        Get server status and statistics.

        Returns:
            Dict with server status
        """
        try:
            memory_count = await self.store.count()
            qdrant_available = await self.store.health_check()

            response = StatusResponse(
                server_name=self.config.server_name,
                version="2.0.0",
                read_only_mode=self.config.read_only_mode,
                storage_backend=self.config.storage_backend,
                memory_count=memory_count,
                qdrant_available=qdrant_available,
                file_watcher_enabled=self.config.enable_file_watcher,
                retrieval_gate_enabled=self.config.enable_retrieval_gate,
            )

            # Get gate metrics
            gate_metrics = self.retrieval_gate.get_metrics() if self.retrieval_gate else {}

            # Get active project info
            active_project_info = None
            if self.project_context_detector:
                context = self.project_context_detector.get_active_context()
                if context:
                    active_project_info = {
                        "name": context.project_name,
                        "path": context.project_path,
                        "git_branch": context.git_branch,
                        "last_activity": context.last_activity.isoformat(),
                    }

            return {
                **response.model_dump(),
                "statistics": self.stats,
                "cache_stats": self.embedding_cache.get_stats(),
                "gate_metrics": gate_metrics,
                "active_project": active_project_info,
            }

        except Exception as e:
            logger.error(f"Failed to get status: {e}")
            return {
                "server_name": self.config.server_name,
                "version": "2.0.0",
                "error": str(e),
            }

    async def get_token_analytics(
        self,
        period_days: int = 30,
        session_id: Optional[str] = None,
        project_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get token usage analytics and cost savings.

        Returns analytics on token usage including tokens saved, cost savings,
        efficiency ratios, and search quality metrics.

        Args:
            period_days: Number of days to analyze (default 30)
            session_id: Filter by specific session ID (optional)
            project_name: Filter by specific project (optional)

        Returns:
            Dict with token analytics including:
            - total_tokens_used: Actual tokens consumed
            - total_tokens_saved: Tokens saved vs manual approach
            - cost_savings_usd: Estimated cost savings in USD
            - efficiency_ratio: Ratio of saved to total tokens
            - avg_relevance: Average search result quality
            - total_searches: Number of searches performed
            - total_files_indexed: Number of files indexed
        """
        try:
            from src.analytics.token_tracker import TokenTracker

            tracker = TokenTracker()
            analytics = tracker.get_analytics(
                period_days=period_days,
                session_id=session_id,
                project_name=project_name,
            )

            return {
                "total_tokens_used": analytics.total_tokens_used,
                "total_tokens_saved": analytics.total_tokens_saved,
                "cost_savings_usd": round(analytics.cost_savings_usd, 2),
                "efficiency_ratio": round(analytics.efficiency_ratio * 100, 1),
                "avg_relevance": round(analytics.avg_relevance, 2),
                "total_searches": analytics.total_searches,
                "total_files_indexed": analytics.total_files_indexed,
                "period_days": period_days,
                "session_id": session_id,
                "project_name": project_name,
            }

        except Exception as e:
            logger.error(f"Failed to get token analytics: {e}")
            raise RetrievalError(f"Failed to get token analytics: {e}")

    async def search_git_history(
        self,
        query: str,
        project_name: Optional[str] = None,
        author: Optional[str] = None,
        since: Optional[str] = None,
        until: Optional[str] = None,
        file_path: Optional[str] = None,
        limit: int = 10,
    ) -> Dict[str, Any]:
        """
        Search git commit history semantically.

        Searches both commit messages and diff content (if indexed) for relevant
        code changes. Useful for queries like:
        - "commits related to authentication"
        - "bug fixes from last week"
        - "changes to login functionality"

        Args:
            query: Search query (natural language)
            project_name: Filter by project
            author: Filter by author email
            since: Date filter (e.g., "2024-01-01", "last week")
            until: Date filter (e.g., "2024-12-31", "yesterday")
            file_path: Filter by file path pattern
            limit: Maximum results (default 10)

        Returns:
            Dict with matching commits
        """
        try:
            from datetime import datetime, timedelta, UTC
            import re

            logger.info(f"Searching git history: '{query}' (project: {project_name})")

            # Parse date filters
            since_dt = None
            until_dt = None

            if since:
                since_dt = self._parse_date_filter(since)
            if until:
                until_dt = self._parse_date_filter(until)

            # Search commits in SQLite store
            commits = await self.store.search_git_commits(
                query=query,
                repository_path=None,  # TODO: Map project_name to repo_path
                author=author,
                since=since_dt,
                until=until_dt,
                limit=limit * 2,  # Fetch more for filtering
            )

            # Filter by file path if specified
            if file_path and commits:
                filtered_commits = []
                for commit in commits:
                    # Get file changes for this commit
                    file_changes = await self.store.get_commits_by_file(
                        file_path, limit=100
                    )
                    if any(fc["commit_hash"] == commit["commit_hash"] for fc in file_changes):
                        filtered_commits.append(commit)
                        if len(filtered_commits) >= limit:
                            break
                commits = filtered_commits
            else:
                commits = commits[:limit]

            # Format results
            results = []
            for commit in commits:
                results.append({
                    "commit_hash": commit["commit_hash"],
                    "author": f"{commit['author_name']} <{commit['author_email']}>",
                    "date": commit["author_date"],
                    "message": commit["message"],
                    "branches": commit.get("branch_names", []),
                    "tags": commit.get("tags", []),
                    "stats": commit.get("stats", {}),
                })

            logger.info(f"Found {len(results)} matching commits")

            return {
                "status": "success",
                "query": query,
                "results": results,
                "count": len(results),
                "filters": {
                    "project": project_name,
                    "author": author,
                    "since": since,
                    "until": until,
                    "file_path": file_path,
                },
            }

        except Exception as e:
            logger.error(f"Failed to search git history: {e}")
            raise RetrievalError(f"Failed to search git history: {e}")

    async def index_git_history(
        self,
        repository_path: str,
        project_name: str,
        num_commits: Optional[int] = None,
        include_diffs: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """
        Index git repository history for semantic search.

        This will extract and index commit metadata, messages, and optionally
        diffs for semantic search over code changes.

        Args:
            repository_path: Path to git repository
            project_name: Project name for organization
            num_commits: Number of commits to index (default from config)
            include_diffs: Whether to index diff content (default: auto-detect)

        Returns:
            Dict with indexing statistics
        """
        if self.config.read_only_mode:
            raise ReadOnlyError("Cannot index git history in read-only mode")

        try:
            from src.memory.git_indexer import GitIndexer
            from pathlib import Path
            import time

            start_time = time.time()
            repo_path = Path(repository_path).resolve()

            if not repo_path.exists():
                raise ValueError(f"Repository does not exist: {repository_path}")

            logger.info(
                f"Indexing git history: {repo_path} "
                f"(project: {project_name}, commits: {num_commits or 'config default'})"
            )

            # Create git indexer
            git_indexer = GitIndexer(self.config, self.embedding_generator)

            # Index repository
            commits_data, file_changes_data = await git_indexer.index_repository(
                str(repo_path),
                project_name,
                num_commits=num_commits,
                include_diffs=include_diffs,
            )

            # Store in database
            # Convert to dicts
            commits_dicts = [
                {
                    "commit_hash": c.commit_hash,
                    "repository_path": c.repository_path,
                    "author_name": c.author_name,
                    "author_email": c.author_email,
                    "author_date": c.author_date,
                    "committer_name": c.committer_name,
                    "committer_date": c.committer_date,
                    "message": c.message,
                    "message_embedding": c.message_embedding,
                    "branch_names": c.branch_names,
                    "tags": c.tags,
                    "parent_hashes": c.parent_hashes,
                    "stats": c.stats,
                }
                for c in commits_data
            ]

            file_changes_dicts = [
                {
                    "id": f.id,
                    "commit_hash": f.commit_hash,
                    "file_path": f.file_path,
                    "change_type": f.change_type,
                    "lines_added": f.lines_added,
                    "lines_deleted": f.lines_deleted,
                    "diff_content": f.diff_content,
                    "diff_embedding": f.diff_embedding,
                }
                for f in file_changes_data
            ]

            # Store commits
            commits_stored = await self.store.store_git_commits(commits_dicts)

            # Store file changes
            changes_stored = 0
            if file_changes_dicts:
                changes_stored = await self.store.store_git_file_changes(file_changes_dicts)

            total_time_s = time.time() - start_time
            stats = git_indexer.get_stats()

            logger.info(
                f"Indexed {commits_stored} commits and {changes_stored} file changes "
                f"in {total_time_s:.2f}s"
            )

            return {
                "status": "success",
                "project_name": project_name,
                "repository_path": str(repo_path),
                "commits_indexed": stats["commits_indexed"],
                "commits_stored": commits_stored,
                "file_changes_indexed": stats["file_changes_indexed"],
                "file_changes_stored": changes_stored,
                "diffs_embedded": stats["diffs_embedded"],
                "errors": stats["errors"],
                "indexing_time_seconds": round(total_time_s, 2),
            }

        except ImportError as e:
            raise ValidationError(
                "GitPython is required for git indexing. "
                "Install with: pip install GitPython>=3.1.40"
            )
        except Exception as e:
            logger.error(f"Failed to index git history: {e}")
            raise StorageError(f"Failed to index git history: {e}")

    async def show_function_evolution(
        self,
        file_path: str,
        function_name: Optional[str] = None,
        limit: int = 10,
    ) -> Dict[str, Any]:
        """
        Show the evolution of a file or function over time.

        Returns commits that modified the specified file, optionally filtered
        to commits that likely affected a specific function.

        Args:
            file_path: File path to track
            function_name: Optional function name to focus on
            limit: Maximum commits to return (default 10)

        Returns:
            Dict with commit history
        """
        try:
            logger.info(f"Showing evolution: {file_path}" + (f" ({function_name})" if function_name else ""))

            # Get commits that modified this file
            commits = await self.store.get_commits_by_file(file_path, limit=limit * 2)

            # If function name specified, try to filter to relevant commits
            if function_name and commits:
                filtered = []
                for commit in commits:
                    # Check if commit message or diff mentions the function
                    message_lower = commit.get("message", "").lower()
                    function_lower = function_name.lower()

                    if function_lower in message_lower:
                        filtered.append(commit)
                        continue

                    # TODO: Could also check diff content if available
                    # For now, if message doesn't mention it, include it anyway
                    # since we want to show all changes to the file
                    filtered.append(commit)

                commits = filtered[:limit]
            else:
                commits = commits[:limit]

            # Format results
            results = []
            for commit in commits:
                result = {
                    "commit_hash": commit["commit_hash"],
                    "author": f"{commit['author_name']} <{commit['author_email']}>",
                    "date": commit["author_date"],
                    "message": commit["message"],
                    "change_type": commit.get("change_type", "modified"),
                    "lines_added": commit.get("lines_added", 0),
                    "lines_deleted": commit.get("lines_deleted", 0),
                }

                # Add branches and tags if available
                if "branch_names" in commit:
                    result["branches"] = commit["branch_names"]
                if "tags" in commit:
                    result["tags"] = commit["tags"]

                results.append(result)

            logger.info(f"Found {len(results)} commits modifying {file_path}")

            return {
                "status": "success",
                "file_path": file_path,
                "function_name": function_name,
                "commits": results,
                "count": len(results),
            }

        except Exception as e:
            logger.error(f"Failed to show function evolution: {e}")
            raise RetrievalError(f"Failed to show function evolution: {e}")

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
        from datetime import datetime, timedelta, UTC
        import re

        date_str = date_str.lower().strip()

        # Relative dates
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
            return cached

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
        # Simple rule-based classification
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

    async def _start_pruning_scheduler(self) -> None:
        """Start background scheduler for auto-pruning."""
        try:
            from apscheduler.schedulers.asyncio import AsyncIOScheduler
            from apscheduler.triggers.cron import CronTrigger

            self.scheduler = AsyncIOScheduler()

            # Parse cron schedule (format: "minute hour day month day_of_week")
            # Default: "0 2 * * *" = 2 AM daily
            schedule_parts = self.config.pruning_schedule.split()

            self.scheduler.add_job(
                self._auto_prune_job,
                CronTrigger(
                    minute=schedule_parts[0] if len(schedule_parts) > 0 else "0",
                    hour=schedule_parts[1] if len(schedule_parts) > 1 else "2",
                    day=schedule_parts[2] if len(schedule_parts) > 2 else "*",
                    month=schedule_parts[3] if len(schedule_parts) > 3 else "*",
                    day_of_week=schedule_parts[4] if len(schedule_parts) > 4 else "*",
                ),
                id="auto_prune",
                name="Auto-prune expired memories",
                replace_existing=True,
            )

            self.scheduler.start()
            logger.info("Pruning scheduler started")

        except Exception as e:
            logger.error(f"Failed to start pruning scheduler: {e}")
            # Don't fail server initialization if scheduler fails
            self.scheduler = None

    async def _auto_prune_job(self) -> None:
        """Background job to auto-prune expired memories."""
        try:
            logger.info("Running auto-prune job")

            if not self.pruner:
                logger.warning("Pruner not initialized, skipping auto-prune")
                return

            # Prune expired SESSION_STATE memories
            result = await self.pruner.prune_expired(
                dry_run=False,
                ttl_hours=None,  # Use config default
                safety_check=True,
            )

            logger.info(
                f"Auto-prune completed: {result.memories_deleted} memories deleted, "
                f"{len(result.errors)} errors"
            )

            # Cleanup orphaned usage tracking
            orphaned_count = await self.pruner.cleanup_orphaned_usage_tracking()
            if orphaned_count > 0:
                logger.info(f"Cleaned up {orphaned_count} orphaned usage tracking records")

        except Exception as e:
            logger.error(f"Auto-prune job failed: {e}", exc_info=True)

    async def switch_project(self, project_name: str) -> Dict[str, Any]:
        """
        Switch active project context (MCP tool).

        Args:
            project_name: Name of project to switch to

        Returns:
            Dictionary with switch status and project info

        Raises:
            ValueError: If project not found or detector not initialized
        """
        if not self.project_context_detector:
            raise ValueError("Project context detector not initialized")

        # Validate project exists by checking if it has any indexed data
        projects = await self.store.get_all_projects()
        if project_name not in projects:
            # Provide helpful error with suggestions
            raise ValueError(
                f"Project '{project_name}' not found. "
                f"Available projects: {', '.join(projects) if projects else 'none'}"
            )

        # Switch context
        context = self.project_context_detector.set_active_context(
            project_name=project_name,
            explicit=True
        )

        # Get project stats
        stats = await self.store.get_project_stats(project_name)

        logger.info(f"Switched to project: {project_name}")

        return {
            "status": "success",
            "project_name": project_name,
            "project_path": context.project_path,
            "git_repo": context.git_repo_root,
            "git_branch": context.git_branch,
            "statistics": stats,
            "message": f"Switched to project '{project_name}'",
        }

    async def get_active_project(self) -> Dict[str, Any]:
        """
        Get currently active project context (MCP tool).

        Returns:
            Dictionary with active project info
        """
        if not self.project_context_detector:
            return {
                "status": "no_detector",
                "project_name": None,
                "message": "Project context detector not initialized",
            }

        context = self.project_context_detector.get_active_context()

        if not context:
            return {
                "status": "no_active_project",
                "project_name": None,
                "message": "No active project set",
            }

        # Get project stats if available
        stats = None
        try:
            stats = await self.store.get_project_stats(context.project_name)
        except Exception as e:
            logger.warning(f"Could not get stats for {context.project_name}: {e}")

        return {
            "status": "success",
            "project_name": context.project_name,
            "project_path": context.project_path,
            "git_repo": context.git_repo_root,
            "git_branch": context.git_branch,
            "last_activity": context.last_activity.isoformat(),
            "file_activity_count": context.file_activity_count,
            "is_active": context.is_active,
            "statistics": stats,
        }

    # ========== Multi-Repository Management Tools ==========

    async def register_repository(
        self,
        path: str,
        name: Optional[str] = None,
        git_url: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Register a new repository for indexing and search.

        Args:
            path: Absolute path to repository
            name: Optional user-friendly name (defaults to directory name)
            git_url: Optional git repository URL
            tags: Optional tags for organizing repositories

        Returns:
            Dict with repository_id and details
        """
        if not self.repository_registry:
            return {
                "error": "Multi-repository support is disabled",
                "status": "disabled"
            }

        try:
            repo_id = await self.repository_registry.register_repository(
                path=path,
                name=name,
                git_url=git_url,
                tags=tags or []
            )

            repository = await self.repository_registry.get_repository(repo_id)

            logger.info(f"Registered repository: {repository.name} ({repo_id})")

            return {
                "repository_id": repo_id,
                "name": repository.name,
                "path": repository.path,
                "status": repository.status.value,
                "message": "Repository registered successfully"
            }

        except Exception as e:
            logger.error(f"Failed to register repository: {e}")
            return {
                "error": str(e),
                "status": "failed"
            }

    async def unregister_repository(self, repo_id: str) -> Dict[str, Any]:
        """
        Unregister a repository and optionally clean up its indexed data.

        Args:
            repo_id: Repository ID to unregister

        Returns:
            Dict with status
        """
        if not self.repository_registry:
            return {
                "error": "Multi-repository support is disabled",
                "status": "disabled"
            }

        try:
            # Get repository info before unregistering
            repository = await self.repository_registry.get_repository(repo_id)
            if not repository:
                return {
                    "error": f"Repository '{repo_id}' not found",
                    "status": "not_found"
                }

            repo_name = repository.name

            # Unregister the repository
            success = await self.repository_registry.unregister_repository(repo_id)

            if success:
                logger.info(f"Unregistered repository: {repo_name} ({repo_id})")
                return {
                    "repository_id": repo_id,
                    "name": repo_name,
                    "status": "unregistered",
                    "message": "Repository unregistered successfully"
                }
            else:
                return {
                    "error": f"Failed to unregister repository '{repo_id}'",
                    "status": "failed"
                }

        except Exception as e:
            logger.error(f"Failed to unregister repository: {e}")
            return {
                "error": str(e),
                "status": "failed"
            }

    async def list_repositories(
        self,
        status: Optional[str] = None,
        workspace_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        List repositories with optional filtering.

        Args:
            status: Filter by status (INDEXED, INDEXING, STALE, ERROR, NOT_INDEXED)
            workspace_id: Filter by workspace membership
            tags: Filter by tags

        Returns:
            Dict with repositories list
        """
        if not self.repository_registry:
            return {
                "error": "Multi-repository support is disabled",
                "repositories": []
            }

        try:
            from src.memory.repository_registry import RepositoryStatus

            # Parse status if provided
            status_filter = None
            if status:
                try:
                    status_filter = RepositoryStatus(status.upper())
                except ValueError:
                    return {
                        "error": f"Invalid status: {status}",
                        "repositories": []
                    }

            # Get repositories
            repositories = await self.repository_registry.list_repositories(
                status=status_filter,
                workspace_id=workspace_id,
                tags=tags
            )

            # Convert to dict format
            repos_data = [
                {
                    "repository_id": repo.id,
                    "name": repo.name,
                    "path": repo.path,
                    "status": repo.status.value,
                    "repo_type": repo.repo_type.value,
                    "file_count": repo.file_count,
                    "unit_count": repo.unit_count,
                    "indexed_at": repo.indexed_at.isoformat() if repo.indexed_at else None,
                    "tags": repo.tags,
                    "workspace_ids": repo.workspace_ids,
                }
                for repo in repositories
            ]

            return {
                "repositories": repos_data,
                "count": len(repos_data),
                "status": "success"
            }

        except Exception as e:
            logger.error(f"Failed to list repositories: {e}")
            return {
                "error": str(e),
                "repositories": []
            }

    async def get_repository_info(self, repo_id: str) -> Dict[str, Any]:
        """
        Get detailed information about a repository.

        Args:
            repo_id: Repository ID

        Returns:
            Dict with repository details
        """
        if not self.repository_registry:
            return {
                "error": "Multi-repository support is disabled",
                "status": "disabled"
            }

        try:
            repository = await self.repository_registry.get_repository(repo_id)

            if not repository:
                return {
                    "error": f"Repository '{repo_id}' not found",
                    "status": "not_found"
                }

            # Get dependencies
            dependencies = await self.repository_registry.get_dependencies(repo_id)

            return {
                "repository_id": repository.id,
                "name": repository.name,
                "path": repository.path,
                "git_url": repository.git_url,
                "status": repository.status.value,
                "repo_type": repository.repo_type.value,
                "file_count": repository.file_count,
                "unit_count": repository.unit_count,
                "indexed_at": repository.indexed_at.isoformat() if repository.indexed_at else None,
                "last_updated": repository.last_updated.isoformat() if repository.last_updated else None,
                "tags": repository.tags,
                "workspace_ids": repository.workspace_ids,
                "dependencies": {
                    str(depth): deps for depth, deps in dependencies.items()
                },
                "dependency_count": sum(len(deps) for deps in dependencies.values()),
                "status": "success"
            }

        except Exception as e:
            logger.error(f"Failed to get repository info: {e}")
            return {
                "error": str(e),
                "status": "failed"
            }

    # ========== Workspace Management Tools ==========

    async def create_workspace(
        self,
        name: str,
        description: Optional[str] = None,
        repository_ids: Optional[List[str]] = None,
        auto_index: bool = True,
        cross_repo_search_enabled: bool = True,
    ) -> Dict[str, Any]:
        """
        Create a new workspace for organizing repositories.

        Args:
            name: Workspace name
            description: Optional description
            repository_ids: Optional list of repository IDs to add
            auto_index: Whether to auto-index when repositories are added
            cross_repo_search_enabled: Whether to enable cross-repo search

        Returns:
            Dict with workspace_id and details
        """
        if not self.workspace_manager:
            return {
                "error": "Multi-repository support is disabled",
                "status": "disabled"
            }

        try:
            # Generate workspace ID from name
            import re
            workspace_id = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')

            workspace = await self.workspace_manager.create_workspace(
                workspace_id=workspace_id,
                name=name,
                description=description,
                repository_ids=repository_ids or [],
                auto_index=auto_index,
                cross_repo_search_enabled=cross_repo_search_enabled
            )

            logger.info(f"Created workspace: {name} ({workspace_id})")

            return {
                "workspace_id": workspace.id,
                "name": workspace.name,
                "description": workspace.description,
                "repository_count": len(workspace.repository_ids),
                "auto_index": workspace.auto_index,
                "cross_repo_search_enabled": workspace.cross_repo_search_enabled,
                "message": "Workspace created successfully"
            }

        except Exception as e:
            logger.error(f"Failed to create workspace: {e}")
            return {
                "error": str(e),
                "status": "failed"
            }

    async def delete_workspace(self, workspace_id: str) -> Dict[str, Any]:
        """
        Delete a workspace.

        Args:
            workspace_id: Workspace ID to delete

        Returns:
            Dict with status
        """
        if not self.workspace_manager:
            return {
                "error": "Multi-repository support is disabled",
                "status": "disabled"
            }

        try:
            # Get workspace info before deleting
            workspace = await self.workspace_manager.get_workspace(workspace_id)
            if not workspace:
                return {
                    "error": f"Workspace '{workspace_id}' not found",
                    "status": "not_found"
                }

            workspace_name = workspace.name

            # Delete the workspace
            success = await self.workspace_manager.delete_workspace(workspace_id)

            if success:
                logger.info(f"Deleted workspace: {workspace_name} ({workspace_id})")
                return {
                    "workspace_id": workspace_id,
                    "name": workspace_name,
                    "status": "deleted",
                    "message": "Workspace deleted successfully"
                }
            else:
                return {
                    "error": f"Failed to delete workspace '{workspace_id}'",
                    "status": "failed"
                }

        except Exception as e:
            logger.error(f"Failed to delete workspace: {e}")
            return {
                "error": str(e),
                "status": "failed"
            }

    async def list_workspaces(
        self,
        tags: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        List all workspaces with optional filtering.

        Args:
            tags: Filter by tags

        Returns:
            Dict with workspaces list
        """
        if not self.workspace_manager:
            return {
                "error": "Multi-repository support is disabled",
                "workspaces": []
            }

        try:
            workspaces = await self.workspace_manager.list_workspaces(tags=tags)

            workspaces_data = [
                {
                    "workspace_id": ws.id,
                    "name": ws.name,
                    "description": ws.description,
                    "repository_count": len(ws.repository_ids),
                    "auto_index": ws.auto_index,
                    "cross_repo_search_enabled": ws.cross_repo_search_enabled,
                    "tags": ws.tags,
                    "created_at": ws.created_at.isoformat(),
                    "updated_at": ws.updated_at.isoformat(),
                }
                for ws in workspaces
            ]

            return {
                "workspaces": workspaces_data,
                "count": len(workspaces_data),
                "status": "success"
            }

        except Exception as e:
            logger.error(f"Failed to list workspaces: {e}")
            return {
                "error": str(e),
                "workspaces": []
            }

    async def add_repo_to_workspace(
        self,
        workspace_id: str,
        repo_id: str
    ) -> Dict[str, Any]:
        """
        Add a repository to a workspace.

        Args:
            workspace_id: Workspace ID
            repo_id: Repository ID to add

        Returns:
            Dict with status
        """
        if not self.workspace_manager:
            return {
                "error": "Multi-repository support is disabled",
                "status": "disabled"
            }

        try:
            await self.workspace_manager.add_repository(workspace_id, repo_id)

            logger.info(f"Added repository {repo_id} to workspace {workspace_id}")

            return {
                "workspace_id": workspace_id,
                "repository_id": repo_id,
                "status": "added",
                "message": "Repository added to workspace successfully"
            }

        except Exception as e:
            logger.error(f"Failed to add repository to workspace: {e}")
            return {
                "error": str(e),
                "status": "failed"
            }

    async def remove_repo_from_workspace(
        self,
        workspace_id: str,
        repo_id: str
    ) -> Dict[str, Any]:
        """
        Remove a repository from a workspace.

        Args:
            workspace_id: Workspace ID
            repo_id: Repository ID to remove

        Returns:
            Dict with status
        """
        if not self.workspace_manager:
            return {
                "error": "Multi-repository support is disabled",
                "status": "disabled"
            }

        try:
            await self.workspace_manager.remove_repository(workspace_id, repo_id)

            logger.info(f"Removed repository {repo_id} from workspace {workspace_id}")

            return {
                "workspace_id": workspace_id,
                "repository_id": repo_id,
                "status": "removed",
                "message": "Repository removed from workspace successfully"
            }

        except Exception as e:
            logger.error(f"Failed to remove repository from workspace: {e}")
            return {
                "error": str(e),
                "status": "failed"
            }

    # ========== Multi-Repository Indexing Tools ==========

    async def index_repository(
        self,
        repo_id: str,
        force: bool = False,
        recursive: bool = True,
    ) -> Dict[str, Any]:
        """
        Index a single repository.

        Args:
            repo_id: Repository ID to index
            force: Force re-indexing even if already indexed
            recursive: Recursively index subdirectories

        Returns:
            Dict with indexing results
        """
        if not self.multi_repo_indexer:
            return {
                "error": "Multi-repository support is disabled",
                "status": "disabled"
            }

        try:
            result = await self.multi_repo_indexer.index_repository(
                repository_id=repo_id,
                recursive=recursive,
                show_progress=True
            )

            if result.success:
                logger.info(
                    f"Indexed repository {repo_id}: "
                    f"{result.files_indexed} files, {result.units_indexed} units"
                )

                return {
                    "repository_id": repo_id,
                    "success": True,
                    "files_indexed": result.files_indexed,
                    "units_indexed": result.units_indexed,
                    "duration_seconds": result.duration_seconds,
                    "message": "Repository indexed successfully"
                }
            else:
                return {
                    "repository_id": repo_id,
                    "success": False,
                    "error": result.error_message,
                    "errors": result.errors,
                    "status": "failed"
                }

        except Exception as e:
            logger.error(f"Failed to index repository: {e}")
            return {
                "error": str(e),
                "status": "failed"
            }

    async def index_workspace(
        self,
        workspace_id: str,
        force: bool = False,
        recursive: bool = True,
    ) -> Dict[str, Any]:
        """
        Index all repositories in a workspace.

        Args:
            workspace_id: Workspace ID
            force: Force re-indexing
            recursive: Recursively index subdirectories

        Returns:
            Dict with batch indexing results
        """
        if not self.multi_repo_indexer:
            return {
                "error": "Multi-repository support is disabled",
                "status": "disabled"
            }

        try:
            result = await self.multi_repo_indexer.index_workspace(
                workspace_id=workspace_id,
                recursive=recursive,
                show_progress=True
            )

            logger.info(
                f"Indexed workspace {workspace_id}: "
                f"{result.successful}/{result.total_repositories} repositories, "
                f"{result.total_files} files, {result.total_units} units"
            )

            return {
                "workspace_id": workspace_id,
                "total_repositories": result.total_repositories,
                "successful": result.successful,
                "failed": result.failed,
                "total_files": result.total_files,
                "total_units": result.total_units,
                "total_duration": result.total_duration,
                "repository_results": [
                    {
                        "repository_id": r.repository_id,
                        "success": r.success,
                        "files_indexed": r.files_indexed,
                        "units_indexed": r.units_indexed,
                        "duration_seconds": r.duration_seconds,
                        "error_message": r.error_message,
                    }
                    for r in result.repository_results
                ],
                "message": f"Workspace indexed: {result.successful}/{result.total_repositories} successful"
            }

        except Exception as e:
            logger.error(f"Failed to index workspace: {e}")
            return {
                "error": str(e),
                "status": "failed"
            }

    async def refresh_stale_repositories(
        self,
        max_age_days: int = 7
    ) -> Dict[str, Any]:
        """
        Re-index repositories that haven't been updated recently.

        Args:
            max_age_days: Consider repositories stale if not indexed in this many days

        Returns:
            Dict with batch indexing results
        """
        if not self.multi_repo_indexer:
            return {
                "error": "Multi-repository support is disabled",
                "status": "disabled"
            }

        try:
            result = await self.multi_repo_indexer.reindex_stale_repositories(
                max_age_days=max_age_days,
                show_progress=True
            )

            logger.info(
                f"Refreshed stale repositories: "
                f"{result.successful}/{result.total_repositories} successful"
            )

            return result.to_dict()

        except Exception as e:
            logger.error(f"Failed to refresh stale repositories: {e}")
            return {
                "error": str(e),
                "status": "failed"
            }

    # ========== Multi-Repository Search Tools ==========

    async def search_repositories(
        self,
        query: str,
        repository_ids: List[str],
        limit_per_repo: int = 10,
        total_limit: Optional[int] = None,
        search_mode: str = "semantic",
    ) -> Dict[str, Any]:
        """
        Search across multiple repositories.

        Args:
            query: Search query
            repository_ids: List of repository IDs to search
            limit_per_repo: Maximum results per repository
            total_limit: Optional total limit across all repositories
            search_mode: Search mode (semantic, keyword, hybrid)

        Returns:
            Dict with search results grouped by repository
        """
        if not self.multi_repo_search:
            return {
                "error": "Multi-repository support is disabled",
                "results": []
            }

        try:
            result = await self.multi_repo_search.search_repositories(
                query=query,
                repository_ids=repository_ids,
                limit_per_repo=limit_per_repo,
                total_limit=total_limit,
                search_mode=search_mode
            )

            logger.info(
                f"Multi-repository search: '{query}' across {result.total_repositories_searched} repositories, "
                f"{result.total_results_found} results ({result.query_time_ms:.2f}ms)"
            )

            return result.to_dict()

        except Exception as e:
            logger.error(f"Failed to search repositories: {e}")
            return {
                "error": str(e),
                "results": []
            }

    async def search_workspace(
        self,
        query: str,
        workspace_id: str,
        limit_per_repo: int = 10,
        total_limit: Optional[int] = None,
        search_mode: str = "semantic",
    ) -> Dict[str, Any]:
        """
        Search all repositories in a workspace.

        Args:
            query: Search query
            workspace_id: Workspace ID
            limit_per_repo: Maximum results per repository
            total_limit: Optional total limit across all repositories
            search_mode: Search mode (semantic, keyword, hybrid)

        Returns:
            Dict with search results from workspace
        """
        if not self.multi_repo_search:
            return {
                "error": "Multi-repository support is disabled",
                "results": []
            }

        try:
            result = await self.multi_repo_search.search_workspace(
                query=query,
                workspace_id=workspace_id,
                limit_per_repo=limit_per_repo,
                total_limit=total_limit,
                search_mode=search_mode
            )

            logger.info(
                f"Workspace search: '{query}' in {workspace_id}, "
                f"{result.total_results_found} results ({result.query_time_ms:.2f}ms)"
            )

            return result.to_dict()

        except Exception as e:
            logger.error(f"Failed to search workspace: {e}")
            return {
                "error": str(e),
                "results": []
            }

    async def search_with_dependencies(
        self,
        query: str,
        repository_id: str,
        max_depth: int = 2,
        limit_per_repo: int = 10,
        total_limit: Optional[int] = None,
        search_mode: str = "semantic",
    ) -> Dict[str, Any]:
        """
        Search a repository and its dependencies.

        Args:
            query: Search query
            repository_id: Primary repository ID
            max_depth: Maximum dependency depth to search
            limit_per_repo: Maximum results per repository
            total_limit: Optional total limit
            search_mode: Search mode (semantic, keyword, hybrid)

        Returns:
            Dict with search results from repository and dependencies
        """
        if not self.multi_repo_search:
            return {
                "error": "Multi-repository support is disabled",
                "results": []
            }

        try:
            result = await self.multi_repo_search.search_with_dependencies(
                query=query,
                repository_id=repository_id,
                max_depth=max_depth,
                limit_per_repo=limit_per_repo,
                total_limit=total_limit,
                search_mode=search_mode
            )

            logger.info(
                f"Dependency search: '{query}' from {repository_id}, "
                f"{result.total_results_found} results across {result.total_repositories_searched} repositories"
            )

            return result.to_dict()

        except Exception as e:
            logger.error(f"Failed to search with dependencies: {e}")
            return {
                "error": str(e),
                "results": []
            }

    async def close(self) -> None:
        """Clean up resources."""
        # Stop conversation tracker
        if self.conversation_tracker:
            await self.conversation_tracker.stop()
            logger.info("Conversation tracker stopped")

        # Stop usage tracker
        if self.usage_tracker:
            await self.usage_tracker.stop()
            logger.info("Usage tracker stopped")

        # Stop scheduler
        if self.scheduler:
            self.scheduler.shutdown(wait=False)
            logger.info("Pruning scheduler stopped")

        # Close multi-repository components
        if self.multi_repo_search:
            await self.multi_repo_search.close()
            logger.info("Multi-repository search closed")

        if self.multi_repo_indexer:
            await self.multi_repo_indexer.close()
            logger.info("Multi-repository indexer closed")

        if self.store:
            await self.store.close()
        if self.embedding_generator:
            await self.embedding_generator.close()
        if self.embedding_cache:
            self.embedding_cache.close()
        logger.info("Server closed")
