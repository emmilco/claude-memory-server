"""MCP Server implementation for Claude Memory RAG."""

import logging
import asyncio
from typing import Optional, Dict, Any, List
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
from src.search.hybrid_search import HybridSearcher, FusionMethod

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
        self.hybrid_searcher: Optional[HybridSearcher] = None
        self.scheduler = None  # APScheduler instance

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
            else:
                self.conversation_tracker = None
                self.query_expander = None
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

                code_results.append({
                    "file_path": file_path or "(no path)",
                    "start_line": nested_metadata.get("start_line", 0),
                    "end_line": nested_metadata.get("end_line", 0),
                    "unit_name": nested_metadata.get("unit_name") or nested_metadata.get("name", "(unnamed)"),
                    "unit_type": nested_metadata.get("unit_type", "(unknown type)"),
                    "signature": nested_metadata.get("signature", ""),
                    "language": language_val or "(unknown language)",
                    "code": memory.content,
                    "relevance_score": min(max(score, 0.0), 1.0),
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

            return {
                **response.model_dump(),
                "statistics": self.stats,
                "cache_stats": self.embedding_cache.get_stats(),
                "gate_metrics": gate_metrics,
            }

        except Exception as e:
            logger.error(f"Failed to get status: {e}")
            return {
                "server_name": self.config.server_name,
                "version": "2.0.0",
                "error": str(e),
            }

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

        if self.store:
            await self.store.close()
        if self.embedding_generator:
            await self.embedding_generator.close()
        if self.embedding_cache:
            self.embedding_cache.close()
        logger.info("Server closed")
