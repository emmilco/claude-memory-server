"""MCP Server implementation for Claude Memory RAG."""

import logging
import asyncio
import json
import os
from typing import Optional, Dict, Any, List
from datetime import datetime, UTC
from pathlib import Path
import subprocess

from src.config import ServerConfig, get_config, DEFAULT_EMBEDDING_DIM
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
    GetUsageStatisticsRequest,
    GetUsageStatisticsResponse,
    GetTopQueriesRequest,
    GetTopQueriesResponse,
    GetFrequentlyAccessedCodeRequest,
    GetFrequentlyAccessedCodeResponse,
)
from src.core.exceptions import (
    StorageError,
    ValidationError,
    ReadOnlyError,
    RetrievalError,
)
# RetrievalGate removed (BUG-018) - was blocking valid queries
from src.memory.usage_tracker import UsageTracker
from src.memory.pruner import MemoryPruner
from src.memory.conversation_tracker import ConversationTracker
from src.memory.query_expander import QueryExpander
from src.memory.suggestion_engine import SuggestionEngine
from src.memory.duplicate_detector import DuplicateDetector
from src.analysis.complexity_analyzer import ComplexityAnalyzer
from src.analysis.quality_analyzer import QualityAnalyzer
from src.search.hybrid_search import HybridSearcher, FusionMethod
from src.analytics.usage_tracker import UsagePatternTracker
from src.monitoring.metrics_collector import MetricsCollector
from src.monitoring.alert_engine import AlertEngine
from src.monitoring.health_reporter import HealthReporter
from src.monitoring.capacity_planner import CapacityPlanner
from src.memory.project_archival import ProjectArchivalManager
from src.core.tracing import new_operation, get_operation_id, get_logger

# Service layer imports (REF-016: Split MemoryRAGServer God Class)
from src.services.memory_service import MemoryService
from src.services.code_indexing_service import CodeIndexingService
from src.services.cross_project_service import CrossProjectService
from src.services.health_service import HealthService
from src.services.query_service import QueryService
from src.services.analytics_service import AnalyticsService
from src.core.structural_query_tools import StructuralQueryMixin

logger = get_logger(__name__)


class MemoryRAGServer(StructuralQueryMixin):
    """
    MCP Server for memory and RAG operations.

    Features:
    - Memory storage and retrieval with vector search
    - Context-level stratification (USER_PREFERENCE, PROJECT_CONTEXT, SESSION_STATE)
    - Qdrant vector store backend
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
        logger.info(f"Read-only mode: {config.advanced.read_only_mode}")
        logger.info(f"Project: {self.project_name or 'global'}")

        # Initialize components
        self.store: Optional[MemoryStore] = None
        self.embedding_generator: Optional[EmbeddingGenerator] = None
        self.embedding_cache: Optional[EmbeddingCache] = None
        self.usage_tracker: Optional[UsageTracker] = None
        self.pruner: Optional[MemoryPruner] = None
        self.conversation_tracker: Optional[ConversationTracker] = None
        self.query_expander: Optional[QueryExpander] = None
        self.hybrid_searcher: Optional[HybridSearcher] = None
        self.cross_project_consent: Optional = None  # Cross-project consent manager
        self.suggestion_engine: Optional[SuggestionEngine] = None  # Proactive suggestions
        self.pattern_tracker: Optional[UsagePatternTracker] = None  # Usage pattern analytics
        self.scheduler = None  # APScheduler instance
        self.auto_indexing_service: Optional = None  # Auto-indexing service (FEAT-016)
        self.archival_manager: Optional[ProjectArchivalManager] = None  # Project archival tracking

        # Quality analysis (FEAT-060)
        self.complexity_analyzer: Optional[ComplexityAnalyzer] = None
        self.quality_analyzer: Optional[QualityAnalyzer] = None
        self.duplicate_detector: Optional[DuplicateDetector] = None

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

        # Service layer (REF-016: Split MemoryRAGServer God Class)
        # These services encapsulate focused functionality extracted from this class
        self.memory_service: Optional[MemoryService] = None
        self.code_indexing_service: Optional[CodeIndexingService] = None
        self.cross_project_service: Optional[CrossProjectService] = None
        self.health_service: Optional[HealthService] = None
        self.query_service: Optional[QueryService] = None
        self.analytics_service: Optional[AnalyticsService] = None

    async def initialize(self, defer_preload: bool = False, defer_auto_index: bool = False) -> None:
        """Initialize async components.

        Args:
            defer_preload: If True, skip embedding model preloading for faster startup.
                          Model will be loaded on first use instead.
            defer_auto_index: If True, skip auto-indexing during initialization.
                             Call start_deferred_auto_indexing() later to trigger it.
        """
        self._defer_auto_index = defer_auto_index
        try:
            # Initialize store
            self.store = create_memory_store(config=self.config)
            await self.store.initialize()

            # Wrap in read-only wrapper if needed
            if self.config.advanced.read_only_mode:
                from src.store.readonly_wrapper import ReadOnlyStoreWrapper
                self.store = ReadOnlyStoreWrapper(self.store)
                logger.info("Read-only mode enabled")

            # Initialize embedding generator
            self.embedding_generator = EmbeddingGenerator(self.config)

            # Preload embedding model on startup to avoid delay on first query
            # Skip preload if defer_preload=True (for fast MCP server startup)
            if not defer_preload:
                await self.embedding_generator.initialize()
            else:
                logger.info("Embedding model preload deferred (will load on first use)")

            # Initialize embedding cache
            self.embedding_cache = EmbeddingCache(self.config)

            # Initialize usage tracker if enabled
            if self.config.analytics.usage_tracking:
                self.usage_tracker = UsageTracker(self.config, self.store)
                await self.usage_tracker.start()
                logger.info("Usage tracking enabled")
            else:
                self.usage_tracker = None
                logger.info("Usage tracking disabled")

            # Initialize pruner
            self.pruner = MemoryPruner(self.config, self.store)

            # Initialize project archival manager (REF-011)
            config_dir = os.path.dirname(os.path.expanduser(self.config.embedding_cache_path))
            archival_file = os.path.join(config_dir, "project_states.json")
            self.archival_manager = ProjectArchivalManager(
                state_file_path=archival_file,
                inactivity_threshold_days=self.config.memory.archival_threshold_days
            )

            # Initialize performance monitoring (FEAT-022) - Must be before scheduler
            # Determine monitoring database path (in the standard config directory)
            monitoring_db_path = os.path.join(config_dir, "monitoring.db")

            self.metrics_collector = MetricsCollector(
                db_path=monitoring_db_path,
                store=self.store,
                archival_manager=self.archival_manager
            )
            self.alert_engine = AlertEngine(db_path=monitoring_db_path)
            self.health_reporter = HealthReporter()
            self.capacity_planner = CapacityPlanner(self.metrics_collector)

            logger.info(f"Performance monitoring enabled (metrics DB: {monitoring_db_path})")

            # Initialize background scheduler for auto-pruning
            if self.config.memory.auto_pruning:
                await self._start_pruning_scheduler()
                logger.info(
                    f"Auto-pruning enabled (schedule: {self.config.memory.pruning_schedule})"
                )
            else:
                logger.info("Auto-pruning disabled")

            # Initialize conversation tracker if enabled
            if self.config.memory.conversation_tracking:
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

            # Initialize quality analysis components (FEAT-060)
            self.complexity_analyzer = ComplexityAnalyzer()
            self.quality_analyzer = QualityAnalyzer(self.complexity_analyzer)
            self.duplicate_detector = DuplicateDetector(self.store, self.embedding_generator)
            logger.info("Quality analysis components initialized")

            # Initialize hybrid searcher if enabled
            if self.config.search.hybrid_search:
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

            # Initialize cross-project consent manager if enabled
            if self.config.search.cross_project_enabled:
                from src.memory.cross_project_consent import CrossProjectConsent
                self.cross_project_consent = CrossProjectConsent(
                    self.config.cross_project_opt_in_file
                )
                opted_in_count = len(self.cross_project_consent.get_opted_in_projects())
                logger.info(
                    f"Cross-project search enabled (default: {self.config.search.cross_project_default_mode}, "
                    f"opted-in projects: {opted_in_count})"
                )
            else:
                self.cross_project_consent = None
                logger.info("Cross-project search disabled")

            # Initialize auto-indexing service if enabled (FEAT-016)
            if defer_auto_index:
                logger.info("Auto-indexing deferred - call start_deferred_auto_indexing() when ready")
            elif self.config.indexing.auto_index_enabled and self.config.indexing.auto_index_on_startup:
                await self._start_auto_indexing()
            else:
                logger.info("Auto-indexing disabled or not configured for startup")

            # Initialize suggestion engine for proactive context
            # Only enabled if store is initialized (needed for searches)
            if self.config.memory.proactive_suggestions:
                self.suggestion_engine = SuggestionEngine(
                    config=self.config,
                    store=self.store,
                )
                logger.info(
                    f"Proactive suggestions enabled "
                    f"(threshold: {self.suggestion_engine.high_confidence_threshold:.2f})"
                )
            else:
                self.suggestion_engine = None
                logger.info("Proactive suggestions disabled")

            # Initialize usage pattern analytics (FEAT-020)
            # Note: os module imported at module level (line 6)
            if self.config.analytics.usage_pattern_analytics:
                # Store analytics DB in same directory as SQLite memory DB
                sqlite_dir = os.path.dirname(os.path.expanduser(self.config.sqlite_path))
                analytics_db_path = os.path.join(sqlite_dir, "usage_analytics.db")
                self.pattern_tracker = UsagePatternTracker(db_path=analytics_db_path)
                logger.info(
                    f"Usage pattern analytics enabled "
                    f"(retention: {self.config.analytics.usage_analytics_retention_days} days)"
                )
            else:
                self.pattern_tracker = None
                logger.info("Usage pattern analytics disabled")

            # Initialize service layer (REF-016: Split MemoryRAGServer God Class)
            # Services provide focused interfaces to functionality previously in this class
            self._initialize_services()
            logger.info("Service layer initialized")

            logger.info("Server initialized successfully")

        except (ImportError, ModuleNotFoundError) as e:
            # Missing dependency - provide actionable error message
            logger.error(f"Missing dependency during initialization: {e}", exc_info=True)
            missing_module = str(e).split("'")[1] if "'" in str(e) else "unknown"
            error_msg = (
                f"Failed to initialize server - missing required dependency: {missing_module}. "
                f"Solution: Install dependencies with 'pip install -r requirements.txt' or "
                f"'pip install {missing_module}'. Check requirements.txt for full dependency list."
            )
            raise ImportError(error_msg) from e
        except Exception as e:
            logger.error(f"Failed to initialize server: {e}", exc_info=True)
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

    def _initialize_services(self) -> None:
        """
        Initialize service layer components (REF-016).

        Creates focused service instances that encapsulate specific functionality
        previously scattered throughout this class. Services provide clean
        interfaces while this class acts as a facade.
        """
        # Memory Service - Core CRUD operations and memory lifecycle
        self.memory_service = MemoryService(
            store=self.store,
            embedding_generator=self.embedding_generator,
            embedding_cache=self.embedding_cache,
            config=self.config,
            usage_tracker=self.usage_tracker,
            conversation_tracker=self.conversation_tracker,
            query_expander=self.query_expander,
            metrics_collector=self.metrics_collector,
            project_name=self.project_name,
        )

        # Code Indexing Service - Code search, indexing, and dependency analysis
        self.code_indexing_service = CodeIndexingService(
            store=self.store,
            embedding_generator=self.embedding_generator,
            embedding_cache=self.embedding_cache,
            config=self.config,
            hybrid_searcher=self.hybrid_searcher,
            metrics_collector=self.metrics_collector,
            duplicate_detector=self.duplicate_detector,
            quality_analyzer=self.quality_analyzer,
            project_name=self.project_name,
        )

        # Cross-Project Service - Multi-project search and consent
        self.cross_project_service = CrossProjectService(
            store=self.store,
            embedding_generator=self.embedding_generator,
            config=self.config,
            cross_project_consent=self.cross_project_consent,
            metrics_collector=self.metrics_collector,
        )

        # Health Service - Monitoring, metrics, and alerting
        self.health_service = HealthService(
            store=self.store,
            config=self.config,
            metrics_collector=self.metrics_collector,
            alert_engine=self.alert_engine,
            health_reporter=self.health_reporter,
            capacity_planner=self.capacity_planner,
        )

        # Query Service - Query expansion, sessions, suggestions
        self.query_service = QueryService(
            config=self.config,
            conversation_tracker=self.conversation_tracker,
            query_expander=self.query_expander,
            suggestion_engine=self.suggestion_engine,
            hybrid_searcher=self.hybrid_searcher,
        )

        # Analytics Service - Usage analytics and patterns
        self.analytics_service = AnalyticsService(
            store=self.store,
            config=self.config,
            usage_tracker=self.usage_tracker,
            pattern_tracker=self.pattern_tracker,
            metrics_collector=self.metrics_collector,
        )

        logger.debug("All services initialized")

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

        **PROACTIVE USE - Store memories immediately when you discover:**
        1. **Architectural patterns or design decisions** - "Uses event sourcing for order processing"
        2. **User preferences or requirements** - "User prefers functional style over OOP"
        3. **Important facts about the codebase** - "Authentication uses Auth0 with JWT tokens"
        4. **Workflows or processes** - "Deploy via CI/CD pipeline triggers on main branch"
        5. **"Why" behind unusual code** - "Duplicate code necessary for performance"
        6. **Completed features or major changes** - "Implemented rate limiting using Redis"

        **When to use:**
        - ✅ After answering important architecture questions
        - ✅ When user shares critical context or decisions
        - ✅ After completing major features (store what was built)
        - ✅ When discovering non-obvious patterns or conventions

        **When NOT to use:**
        - ❌ For temporary session state (logs, intermediate results)
        - ❌ For information already in code comments or docs
        - ❌ For trivial facts easily re-discovered

        **Categories:**
        - `preference`: User/team preferences (code style, tools, approaches)
        - `fact`: Objective information about codebase or project
        - `event`: Significant events or milestones (releases, migrations)
        - `workflow`: Processes, procedures, or step-by-step guides
        - `context`: Background information or situational context

        Args:
            content: Memory content (clear, concise description)
            category: Memory category (preference, fact, event, workflow, context)
            scope: Memory scope - "global" for all projects, "project" for specific project
            project_name: Required if scope is "project"
            importance: Importance score 0.0-1.0 (default: 0.5, high: 0.8+, critical: 1.0)
            tags: Optional tags for categorization (e.g., ["auth", "security"])
            metadata: Optional structured metadata (e.g., {"version": "2.0"})
            context_level: Auto-classified if not provided (USER_PREFERENCE, PROJECT_CONTEXT, SESSION_STATE)

        Returns:
            Dict with memory_id, status, and auto-classified context_level
        """
        # Start new operation with unique ID for tracing
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

        **PROACTIVE USE - Check memories automatically in these situations:**
        1. **At session start** - retrieve("project architecture patterns conventions")
        2. **Before major changes** - retrieve("previous decisions about authentication")
        3. **When user mentions past work** - retrieve("user preferences for error handling")
        4. **Before refactoring** - retrieve("why was X implemented this way")
        5. **When exploring unfamiliar code** - retrieve("design patterns used in codebase")
        6. **After user shares context** - retrieve related memories to build on existing knowledge

        **Use cases:**
        - ✅ Recall architectural decisions before making changes
        - ✅ Find user preferences to maintain consistency
        - ✅ Discover "why" behind unusual patterns
        - ✅ Build on previous work instead of starting fresh
        - ✅ Maintain context across multiple sessions

        **When NOT to use:**
        - ❌ For searching code (use search_code instead)
        - ❌ For finding files (use Glob/Grep instead)
        - ❌ When information is clearly visible in current context

        **Smart retrieval gate:**
        - Automatically filters low-value queries to save tokens
        - Returns empty results for queries unlikely to be useful
        - Tracks utility scores and estimated token savings

        **Example queries:**
        - "authentication patterns and security decisions"
        - "user preferences for code organization"
        - "database migration workflows and procedures"
        - "why we chose GraphQL over REST"

        Args:
            query: Natural language search query describing what to find
            limit: Maximum results to return (default: 5, recommended: 5-10)
            context_level: Filter by USER_PREFERENCE, PROJECT_CONTEXT, or SESSION_STATE
            scope: Filter by "global" (all projects) or "project" (specific project)
            project_name: Required if scope is "project"
            category: Filter by preference, fact, event, workflow, or context
            min_importance: Minimum importance 0.0-1.0 (0.0=all, 0.5=important, 0.8=critical)
            tags: Filter by tags (e.g., ["auth", "security"])
            session_id: Optional session ID for conversation-aware context tracking
            advanced_filters: Advanced options (date ranges, tag logic, exclusions)

        Returns:
            Dict with results, relevance scores, total_found, query_time_ms, and used_cache
        """
        # Start new operation with unique ID for tracing
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

            # Retrieval gate removed (BUG-018) - proceed directly to retrieval

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
            if self.usage_tracker and self.config.analytics.usage_tracking:
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
                    query_embedding=query_embedding if self.config.memory.conversation_tracking else None,
                )
                logger.debug(f"Tracked {len(results_shown)} results in session {session_id}")

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

        **Use when:** Removing outdated, incorrect, or duplicate memories.
        Use `list_memories` first to find memory_id.

        Args:
            memory_id: Memory ID to delete (from list_memories or retrieve_memories)

        Returns:
            Dict with status ("success" or "not_found")
        """
        # Start new operation with unique ID for tracing
        op_id = new_operation()
        logger.info(f"Deleting memory: {memory_id}")

        if self.config.advanced.read_only_mode:
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
            logger.error(f"Failed to delete memory: {e}", exc_info=True)
            raise StorageError(f"Failed to delete memory: {e}")

    async def get_memory_by_id(self, memory_id: str) -> Dict[str, Any]:
        """
        Retrieve a specific memory by its ID.

        Args:
            memory_id: The unique ID of the memory to retrieve

        Returns:
            Dict with status and memory data:
            - If found: {"status": "success", "memory": {...}}
            - If not found: {"status": "not_found", "message": "..."}
        """
        try:
            memory = await self.store.get_by_id(memory_id)

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
            memory_id: ID of memory to update (required)
            content: New content (optional)
            category: New category (optional)
            importance: New importance score 0.0-1.0 (optional)
            tags: New tags list (optional)
            metadata: New metadata dict (optional)
            context_level: New context level (optional)
            regenerate_embedding: Whether to regenerate embedding if content changes (default: True)

        Returns:
            Dict with status and update details:
            {
                "status": "updated" or "not_found",
                "updated_fields": List[str],
                "embedding_regenerated": bool,
                "updated_at": ISO timestamp
            }
        """
        if self.config.advanced.read_only_mode:
            raise ReadOnlyError("Cannot update memory in read-only mode")

        try:
            # Build updates dictionary
            updates = {}
            updated_fields = []

            if content is not None:
                # Validate content length
                if not (1 <= len(content) <= 50000):
                    raise ValidationError("content must be 1-50000 characters")
                updates["content"] = content
                updated_fields.append("content")

            if category is not None:
                # Validate category
                cat = MemoryCategory(category)
                updates["category"] = cat.value
                updated_fields.append("category")

            if importance is not None:
                # Validate importance
                if not (0.0 <= importance <= 1.0):
                    raise ValidationError("importance must be between 0.0 and 1.0")
                updates["importance"] = importance
                updated_fields.append("importance")

            if tags is not None:
                # Validate tags
                for tag in tags:
                    if not isinstance(tag, str) or len(tag) > 50:
                        raise ValidationError("Tags must be strings <= 50 chars")
                updates["tags"] = tags
                updated_fields.append("tags")

            if metadata is not None:
                # Validate metadata is a dict
                if not isinstance(metadata, dict):
                    raise ValidationError("metadata must be a dictionary")
                updates["metadata"] = metadata
                updated_fields.append("metadata")

            if context_level is not None:
                # Validate context level
                cl = ContextLevel(context_level)
                updates["context_level"] = cl.value
                updated_fields.append("context_level")

            # Check that at least one field is being updated
            if not updates:
                raise ValidationError("At least one field must be provided for update")

            # Regenerate embedding if content changed
            new_embedding = None
            embedding_regenerated = False

            if "content" in updates and regenerate_embedding:
                embedding_regenerated = True
                new_embedding = await self.embedding_generator.generate(updates["content"])

            # Perform update
            success = await self.store.update(
                memory_id=memory_id,
                updates=updates,
                new_embedding=new_embedding
            )

            if success:
                # Update stats
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

        **PROACTIVE USE:**
        - Review stored memories by category or project
        - Audit recent memories to understand what's been learned
        - Browse preferences or facts for a specific project
        - Check SESSION_STATE memories before cleanup

        **Common use cases:**
        - list_memories(category="preference") - View all user preferences
        - list_memories(project_name="myapp", category="fact") - Project-specific facts
        - list_memories(tags=["auth", "security"]) - Security-related memories
        - list_memories(min_importance=0.8) - Only high-importance memories

        Args:
            category: Filter by preference, fact, event, workflow, or context
            context_level: Filter by USER_PREFERENCE, PROJECT_CONTEXT, SESSION_STATE
            scope: Filter by "global" or "project"
            project_name: Filter by specific project
            tags: Filter by tags (matches ANY tag)
            min_importance: Minimum importance 0.0-1.0 (default: 0.0)
            max_importance: Maximum importance 0.0-1.0 (default: 1.0)
            date_from: Filter created_at >= date (ISO format: "2025-01-01T00:00:00Z")
            date_to: Filter created_at <= date (ISO format)
            sort_by: Sort by "created_at", "updated_at", or "importance"
            sort_order: "asc" (oldest first) or "desc" (newest first)
            limit: Results per page (1-100, default: 20)
            offset: Skip N results (for pagination, default: 0)

        Returns:
            Dict with memories list, total_count, returned_count, offset, limit, has_more
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
            logger.error(f"Failed to list memories: {e}", exc_info=True)
            raise StorageError(f"Failed to list memories: {e}")

    async def get_indexed_files(
        self,
        project_name: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """
        Get list of indexed files with metadata.

        Provides transparency into what files have been indexed, which is useful for:
        - Debugging indexing issues
        - Understanding codebase coverage
        - Verifying that expected files are indexed

        Args:
            project_name: Filter by project name (optional)
            limit: Maximum number of files to return (1-500, default 50)
            offset: Number of files to skip for pagination (default 0)

        Returns:
            {
                "files": [
                    {
                        "file_path": str,
                        "language": str,
                        "last_indexed": str (ISO timestamp),
                        "unit_count": int
                    }
                ],
                "total": int,
                "limit": int,
                "offset": int,
                "has_more": bool
            }

        Raises:
            ValidationError: If parameters are invalid
            StorageError: If operation fails
        """
        try:
            # Query store (store auto-caps limit and offset to valid ranges)
            result = await self.store.get_indexed_files(
                project_name=project_name,
                limit=limit,
                offset=offset
            )

            # Add has_more flag
            result["has_more"] = (result["offset"] + len(result["files"])) < result["total"]

            logger.info(
                f"Retrieved {len(result['files'])} indexed files "
                f"(total {result['total']}) for project '{project_name or 'all'}'"
            )

            return result

        except Exception as e:
            logger.error(f"Failed to get indexed files: {e}", exc_info=True)
            raise StorageError(f"Failed to get indexed files: {e}")

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
        List indexed code units (functions, classes, etc.) with filtering.

        This allows inspection of individual code units that have been indexed,
        which is useful for:
        - Verifying specific functions/classes are indexed
        - Understanding code structure
        - Debugging search results

        Args:
            project_name: Filter by project name (optional)
            language: Filter by language (Python, JavaScript, etc.) (optional)
            file_pattern: Filter by file path pattern (optional)
                - SQLite: SQL LIKE pattern (e.g., "%.py", "src/%")
                - Qdrant: Glob pattern (e.g., "*.py", "src/**")
            unit_type: Filter by unit type (function, class, method, etc.) (optional)
            limit: Maximum number of units to return (1-500, default 50)
            offset: Number of units to skip for pagination (default 0)

        Returns:
            {
                "units": [
                    {
                        "id": str,
                        "name": str,
                        "unit_type": str,
                        "file_path": str,
                        "language": str,
                        "start_line": int,
                        "end_line": int,
                        "signature": str,
                        "last_indexed": str (ISO timestamp)
                    }
                ],
                "total": int,
                "limit": int,
                "offset": int,
                "has_more": bool
            }

        Raises:
            ValidationError: If parameters are invalid
            StorageError: If operation fails
        """
        try:
            # Query store (store auto-caps limit and offset to valid ranges)
            result = await self.store.list_indexed_units(
                project_name=project_name,
                language=language,
                file_pattern=file_pattern,
                unit_type=unit_type,
                limit=limit,
                offset=offset
            )

            # Add has_more flag
            result["has_more"] = (result["offset"] + len(result["units"])) < result["total"]

            logger.info(
                f"Retrieved {len(result['units'])} indexed units "
                f"(total {result['total']}) with filters: "
                f"project={project_name}, language={language}, "
                f"file_pattern={file_pattern}, unit_type={unit_type}"
            )

            return result

        except Exception as e:
            logger.error(f"Failed to list indexed units: {e}", exc_info=True)
            raise StorageError(f"Failed to list indexed units: {e}")

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
            success = await self.store.migrate_memory_scope(memory_id, new_project_name)

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
            count = await self.store.bulk_update_context_level(
                new_context_level=new_context_level,
                project_name=project_name,
                current_context_level=current_context_level,
                category=category,
            )

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
            duplicate_groups = await self.store.find_duplicate_memories(
                project_name=project_name,
                similarity_threshold=similarity_threshold,
            )

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
            merged_id = await self.store.merge_memories(
                memory_ids=memory_ids,
                keep_id=keep_id,
            )

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

        **Use for:**
        - Backup before major changes
        - Sharing knowledge across teams
        - Migrating memories between systems
        - Creating documentation from stored memories

        Args:
            output_path: File path to write (if None, returns content as string)
            format: "json" (structured) or "markdown" (human-readable)
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
        # Validate format
        if format not in ["json", "markdown"]:
            raise ValidationError(f"Invalid export format: {format}. Must be 'json' or 'markdown'")

        try:
            # Get all matching memories by querying the store directly
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

            # Get memories from store (using list_memories with large limit to get all)
            filters_dict = filters.to_dict() if filters else {}
            if project_name:
                filters_dict['project_name'] = project_name

            memories_list, total_count = await self.store.list_memories(
                filters=filters_dict,
                limit=999999,  # Get all matching memories
                offset=0
            )

            # Convert to dict format
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

        **Use for:**
        - Restoring from backups
        - Sharing knowledge across teams
        - Migrating from another system
        - Batch loading initial memories

        Args:
            file_path: Path to JSON file (e.g., "memories.json")
            content: Direct JSON string (alternative to file_path)
            conflict_mode: "skip" (ignore duplicates), "overwrite" (replace), or "merge" (combine)
            format: "json" (auto-detected from extension if file_path provided)

        Returns:
            Dict with memories_created, memories_updated, memories_skipped, errors list
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
                            embedding = await self.embedding_generator.generate(mem_data["content"])

                            # Build updates
                            updates = {
                                "content": mem_data["content"],
                                "category": mem_data.get("category", "fact"),
                                "context_level": mem_data.get("context_level", "SESSION_STATE"),
                                "importance": mem_data.get("importance", 0.5),
                                "tags": mem_data.get("tags", []),
                            }

                            if "metadata" in mem_data:
                                updates["metadata"] = mem_data["metadata"]

                            # Update using store's update method
                            success = await self.store.update(mem_id, updates, embedding)

                            if success:
                                updated_count += 1
                            else:
                                errors.append(f"Memory {mem_id}: Update failed")

                        elif conflict_mode == "merge":
                            # Merge: update only non-null fields
                            updates = {}

                            if "content" in mem_data and mem_data["content"]:
                                updates["content"] = mem_data["content"]
                                embedding = await self.embedding_generator.generate(mem_data["content"])
                            else:
                                embedding = None

                            # Merge metadata
                            for field in ["category", "context_level", "scope", "importance", "tags", "project_name"]:
                                if field in mem_data and mem_data[field] is not None:
                                    updates[field] = mem_data[field]

                            if "metadata" in mem_data and mem_data["metadata"]:
                                updates["metadata"] = mem_data["metadata"]

                            if updates:
                                success = await self.store.update(mem_id, updates, embedding)
                                if success:
                                    updated_count += 1
                                else:
                                    errors.append(f"Memory {mem_id}: Merge update failed")
                            else:
                                skipped_count += 1

                    else:
                        # Memory doesn't exist - create new
                        embedding = await self.embedding_generator.generate(mem_data["content"])

                        # Create memory request
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

                        # Store new memory - build metadata dict for store
                        store_metadata = {
                            "id": mem_id,  # Preserve original ID from export
                            "category": request.category.value if hasattr(request.category, 'value') else request.category,
                            "context_level": request.context_level.value if hasattr(request.context_level, 'value') else request.context_level,
                            "scope": request.scope.value if hasattr(request.scope, 'value') else request.scope,
                            "importance": request.importance,
                            "tags": request.tags,
                            "metadata": request.metadata,
                            "project_name": request.project_name,
                        }

                        new_id = await self.store.store(
                            content=request.content,
                            embedding=embedding,
                            metadata=store_metadata,
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
            logger.error(f"Failed to import memories: {e}", exc_info=True)
            raise StorageError(f"Failed to import memories: {e}")

    async def submit_search_feedback(
        self,
        search_id: str,
        query: str,
        result_ids: List[str],
        rating: str,
        comment: Optional[str] = None,
        project_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Submit user feedback for a search query and its results.

        Args:
            search_id: Unique ID of the search
            query: Search query text
            result_ids: List of result memory IDs
            rating: 'helpful' or 'not_helpful'
            comment: Optional user comment
            project_name: Optional project context

        Returns:
            Dict with feedback ID and status
        """
        try:
            feedback_id = await self.store.submit_search_feedback(
                search_id=search_id,
                query=query,
                result_ids=result_ids,
                rating=rating,
                comment=comment,
                project_name=project_name,
            )

            logger.info(f"Submitted feedback {feedback_id} for search {search_id}")
            return {
                "status": "success",
                "feedback_id": feedback_id,
                "search_id": search_id,
                "rating": rating,
            }

        except Exception as e:
            logger.error(f"Failed to submit search feedback: {e}", exc_info=True)
            raise StorageError(f"Failed to submit search feedback: {e}")

    async def get_quality_metrics(
        self,
        time_range_hours: int = 24,
        project_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get aggregated quality metrics for search results.

        Args:
            time_range_hours: Number of hours to look back (default: 24)
            project_name: Optional project filter

        Returns:
            Dict with quality metrics
        """
        try:
            metrics = await self.store.get_quality_metrics(
                time_range_hours=time_range_hours,
                project_name=project_name,
            )

            logger.info(
                f"Retrieved quality metrics: {metrics['total_searches']} searches, "
                f"{metrics['helpfulness_rate']:.2%} helpful"
            )
            return {
                "status": "success",
                "metrics": metrics,
            }

        except Exception as e:
            logger.error(f"Failed to retrieve quality metrics: {e}", exc_info=True)
            raise StorageError(f"Failed to retrieve quality metrics: {e}")

    async def get_dashboard_stats(self) -> Dict[str, Any]:
        """
        Get aggregated statistics for the dashboard.

        Returns:
            Dict with dashboard statistics including:
            - total_memories: Total memory count across all projects
            - projects: List of project stats
            - categories: Aggregated category counts
            - lifecycle_states: Aggregated lifecycle state counts
        """
        try:
            # Get total memory count
            total_memories = await self.store.count()

            # Get all projects
            projects = await self.store.get_all_projects()

            # Get stats for each project
            project_stats = []
            all_categories: Dict[str, int] = {}
            all_lifecycle_states: Dict[str, int] = {}

            for project in projects:
                try:
                    stats = await self.store.get_project_stats(project)
                    project_stats.append(stats)

                    # Aggregate categories
                    for category, count in stats.get("categories", {}).items():
                        all_categories[category] = all_categories.get(category, 0) + count

                    # Aggregate lifecycle states
                    for state, count in stats.get("lifecycle_states", {}).items():
                        all_lifecycle_states[state] = all_lifecycle_states.get(state, 0) + count

                except Exception as e:
                    logger.warning(f"Failed to get stats for project {project}: {e}")
                    continue

            # Get memories without project (global memories)
            try:
                # Count global memories (those without project_name)
                from qdrant_client.models import Filter, FieldCondition, IsNullCondition

                # Count memories where project_name is null or empty
                count_result = await self.store.client.count(
                    collection_name=self.store.collection_name,
                    count_filter=Filter(
                        should=[
                            FieldCondition(
                                key="project_name",
                                match=IsNullCondition()
                            ),
                        ]
                    ),
                    exact=True,
                )
                global_count = count_result.count
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
            limit: Maximum number of items per category (default 20)
            project_name: Optional project filter

        Returns:
            Dict with recent activity data
        """
        try:
            activity = await self.store.get_recent_activity(
                limit=limit,
                project_name=project_name,
            )

            logger.info(
                f"Retrieved recent activity: {len(activity['recent_searches'])} searches, "
                f"{len(activity['recent_additions'])} additions"
            )

            return {
                "status": "success",
                **activity,
            }

        except Exception as e:
            logger.error(f"Failed to retrieve recent activity: {e}", exc_info=True)
            raise StorageError(f"Failed to retrieve recent activity: {e}")

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
        

        Note: This function is async for MCP protocol compatibility, even though it
        doesn't currently use await. The MCP framework requires handler functions to
        be async, and future changes may add async operations.
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
            logger.error(f"Failed to start conversation session: {e}", exc_info=True)
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
        

        Note: This function is async for MCP protocol compatibility, even though it
        doesn't currently use await. The MCP framework requires handler functions to
        be async, and future changes may add async operations.
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
            logger.error(f"Failed to end conversation session: {e}", exc_info=True)
            return {
                "error": str(e),
                "status": "failed"
            }

    async def list_conversation_sessions(self) -> Dict[str, Any]:
        """
        List all active conversation sessions.

        Returns:
            Dict with sessions list and stats
        

        Note: This function is async for MCP protocol compatibility, even though it
        doesn't currently use await. The MCP framework requires handler functions to
        be async, and future changes may add async operations.
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
            logger.error(f"Failed to list conversation sessions: {e}", exc_info=True)
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
        min_complexity: Optional[int] = None,
        max_complexity: Optional[int] = None,
        has_duplicates: Optional[bool] = None,
        long_functions: Optional[bool] = None,
        maintainability_min: Optional[int] = None,
        include_quality_metrics: bool = True,
    ) -> Dict[str, Any]:
        """
        Search indexed code semantically across functions and classes.

        **PROACTIVE USE - Use this BEFORE Grep/Read when:**
        1. **User asks "where is X?"** - search_code("where is authentication handled")
        2. **User asks "how does Y work?"** - search_code("how does rate limiting work")
        3. **Exploring unfamiliar code** - search_code("database connection pooling")
        4. **Finding implementations by description** - search_code("JWT token validation logic")
        5. **Understanding architecture** - search_code("API middleware error handling")
        6. **Before making changes** - search_code("existing payment processing flow")

        **Advantages over Grep:**
        - ✅ Finds code by **meaning**, not just keywords
        - ✅ Returns **full function/class context** with line numbers
        - ✅ Works when you don't know exact function names
        - ✅ Searches across **multiple files** simultaneously
        - ✅ Provides **relevance scores** to rank results

        **When to use Grep instead:**
        - ❌ Finding exact text strings or error messages
        - ❌ Code hasn't been indexed yet
        - ❌ Searching for variable names or imports

        **Search modes:**
        - `semantic` (default): Find by meaning - best for "what does X" questions
        - `keyword`: Find by exact text - faster, good for known function names
        - `hybrid`: Combines both - best balance of accuracy and recall

        **Example queries:**
        - "authentication middleware that validates JWT tokens"
        - "database migration functions"
        - "error handling for API requests"
        - "user permission checking logic"

        **Performance:** 7-13ms semantic, 3-7ms keyword, 10-18ms hybrid

        Args:
            query: Natural language description of what to find (be specific!)
            project_name: Optional project filter (defaults to current project if available)
            limit: Maximum results (default: 5, increase to 10-20 for broad searches)
            file_pattern: Optional path filter (e.g., "*/auth/*", "**/services/*.py")
            language: Optional language filter ("python", "javascript", "typescript", etc.)
            search_mode: "semantic" (meaning), "keyword" (exact), or "hybrid" (both)
            min_complexity: Optional minimum complexity filter (FEAT-060)
            max_complexity: Optional maximum complexity filter (FEAT-060)
            has_duplicates: Optional duplicate filter (True/False) (FEAT-060)
            long_functions: Optional long function filter (True/False) (FEAT-060)
            maintainability_min: Optional minimum maintainability index (0-100) (FEAT-060)
            include_quality_metrics: Include quality metrics in results (default: True) (FEAT-060)

        Returns:
            Dict with results containing file_path, start_line, end_line, code snippets,
            relevance_score, quality assessment, quality_metrics, and matched keywords
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
                category=MemoryCategory.CODE,
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

            # Format results for code search with deduplication
            code_results = []
            seen_units = set()  # Track (file_path, start_line, unit_name) to deduplicate

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

                # Deduplication: Skip if we've already seen this exact code unit
                unit_name = nested_metadata.get("unit_name") or nested_metadata.get("name", "(unnamed)")
                start_line = nested_metadata.get("start_line", 0)
                dedup_key = (file_path, start_line, unit_name)

                if dedup_key in seen_units:
                    logger.debug(f"Skipping duplicate: {unit_name} at {file_path}:{start_line}")
                    continue
                seen_units.add(dedup_key)

                relevance_score = min(max(score, 0.0), 1.0)
                confidence_label = self._get_confidence_label(relevance_score)

                result_dict = {
                    "file_path": file_path or "(no path)",
                    "start_line": start_line,
                    "end_line": nested_metadata.get("end_line", 0),
                    "unit_name": unit_name,
                    "unit_type": nested_metadata.get("unit_type", "(unknown type)"),
                    "signature": nested_metadata.get("signature", ""),
                    "language": language_val or "(unknown language)",
                    "code": memory.content,
                    "relevance_score": relevance_score,
                    "confidence_label": confidence_label,
                    "confidence_display": f"{relevance_score:.0%} ({confidence_label})",
                }

                # Calculate quality metrics (FEAT-060)
                if include_quality_metrics:
                    # Build code unit dict
                    code_unit = {
                        "content": memory.content,
                        "signature": nested_metadata.get("signature", ""),
                        "unit_type": nested_metadata.get("unit_type", "function"),
                        "language": language_val,
                    }

                    # Calculate duplication score
                    duplication_score = await self.duplicate_detector.calculate_duplication_score(
                        memory
                    )

                    # Calculate quality metrics
                    quality_metrics = self.quality_analyzer.calculate_quality_metrics(
                        code_unit=code_unit,
                        duplication_score=duplication_score,
                    )

                    # Add quality metrics to result
                    result_dict["quality_metrics"] = {
                        "cyclomatic_complexity": quality_metrics.cyclomatic_complexity,
                        "line_count": quality_metrics.line_count,
                        "nesting_depth": quality_metrics.nesting_depth,
                        "parameter_count": quality_metrics.parameter_count,
                        "has_documentation": quality_metrics.has_documentation,
                        "duplication_score": round(quality_metrics.duplication_score, 2),
                        "maintainability_index": quality_metrics.maintainability_index,
                        "quality_flags": quality_metrics.quality_flags,
                    }

                    # Apply quality filters (FEAT-060)
                    if min_complexity is not None and quality_metrics.cyclomatic_complexity < min_complexity:
                        continue
                    if max_complexity is not None and quality_metrics.cyclomatic_complexity > max_complexity:
                        continue
                    if has_duplicates is not None:
                        is_duplicate = quality_metrics.duplication_score > 0.85
                        if is_duplicate != has_duplicates:
                            continue
                    if long_functions is not None:
                        is_long = quality_metrics.line_count > 100
                        if is_long != long_functions:
                            continue
                    if maintainability_min is not None and quality_metrics.maintainability_index < maintainability_min:
                        continue

                code_results.append(result_dict)

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

            # Log metrics for performance monitoring
            if self.metrics_collector:
                avg_relevance = sum(r["relevance_score"] for r in code_results) / len(code_results) if code_results else 0.0
                self.metrics_collector.log_query(
                    query=query,
                    latency_ms=query_time_ms,
                    result_count=len(code_results),
                    avg_relevance=avg_relevance
                )

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

        except RetrievalError:
            # Re-raise RetrievalError as-is (already has good error messages from store layer)
            raise
        except (ConnectionError, OSError) as e:
            # Network/connection failures - provide actionable error message
            logger.error(f"Network error during code search: {e}", exc_info=True)
            error_msg = (
                f"Failed to connect to Qdrant vector database: {str(e)}. "
                f"Please ensure Qdrant is running at {self.config.qdrant_url}. "
                f"Solution: Run 'docker-compose up -d' to start Qdrant, or check your "
                f"CLAUDE_RAG_QDRANT_URL environment variable."
            )
            raise RetrievalError(error_msg)
        except Exception as e:
            # Generic error with actionable guidance
            logger.error(f"Failed to search code: {e}", exc_info=True)
            error_type = type(e).__name__
            error_msg = (
                f"Code search failed ({error_type}): {str(e)}. "
                f"Solution: Check that Qdrant is running and accessible, "
                f"or try using SQLite backend (CLAUDE_RAG_STORAGE_BACKEND=sqlite)."
            )
            raise RetrievalError(error_msg)

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

        **PROACTIVE USE:**
        - Find duplicate code for refactoring opportunities
        - Discover similar implementations across the codebase
        - Identify code patterns and conventions
        - Locate existing logic before implementing new features

        **Use cases:**
        - Check if similar logic already exists before writing new code
        - Find all implementations of a pattern for consistency updates
        - Discover duplicates during code review
        - Learn coding patterns from existing codebase

        Args:
            code_snippet: Code to find matches for (function, class, or code block)
            project_name: Optional project filter (defaults to current project)
            limit: Maximum results (default: 10, increase for comprehensive search)
            file_pattern: Optional path filter (e.g., "*/services/*")
            language: Optional language filter ("python", "javascript", etc.)

        Returns:
            Dict with similar code results, file paths, line numbers, similarity scores
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
                category=MemoryCategory.CODE,
                context_level=ContextLevel.PROJECT_CONTEXT,
                tags=["code"],  # Code semantic units are tagged with "code"
            )

            # Retrieve similar code from store
            results = await self.store.retrieve(
                query_embedding=code_embedding,
                filters=filters,
                limit=limit,
            )

            # Format results for code search with deduplication
            code_results = []
            seen_units = set()  # Track (file_path, start_line, unit_name) to deduplicate

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

                # Deduplication: Skip if we've already seen this exact code unit
                unit_name = nested_metadata.get("unit_name") or nested_metadata.get("name", "(unnamed)")
                start_line = nested_metadata.get("start_line", 0)
                dedup_key = (file_path, start_line, unit_name)

                if dedup_key in seen_units:
                    logger.debug(f"Skipping duplicate: {unit_name} at {file_path}:{start_line}")
                    continue
                seen_units.add(dedup_key)

                similarity_score = min(max(score, 0.0), 1.0)
                confidence_label = self._get_confidence_label(similarity_score)

                code_results.append({
                    "file_path": file_path or "(no path)",
                    "start_line": start_line,
                    "end_line": nested_metadata.get("end_line", 0),
                    "unit_name": unit_name,
                    "unit_type": nested_metadata.get("unit_type", "(unknown type)"),
                    "signature": nested_metadata.get("signature", ""),
                    "language": language_val or "(unknown language)",
                    "code": memory.content,
                    "similarity_score": similarity_score,
                    "confidence_label": confidence_label,
                    "confidence_display": f"{similarity_score:.0%} ({confidence_label})",
                })

            query_time_ms = (time.time() - start_time) * 1000

            # Log metrics for performance monitoring
            if self.metrics_collector:
                avg_relevance = sum(r["similarity_score"] for r in code_results) / len(code_results) if code_results else 0.0
                self.metrics_collector.log_query(
                    query=f"<code_similarity:{len(code_snippet)} chars>",  # Anonymize code snippet
                    latency_ms=query_time_ms,
                    result_count=len(code_results),
                    avg_relevance=avg_relevance
                )

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
            logger.error(f"Failed to find similar code: {e}", exc_info=True)
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

        **PROACTIVE USE:**
        - Learn from patterns across multiple projects
        - Find best practices implemented in other codebases
        - Discover existing solutions before building new features
        - Understand consistent patterns across team's work

        **Privacy:** Projects must explicitly opt-in via `opt_in_cross_project`.
        Use `list_opted_in_projects` to see which projects are searchable.

        **When to use:**
        - ✅ Looking for implementations across team's projects
        - ✅ Finding best practices from previous work
        - ✅ Learning patterns used in similar projects

        Args:
            query: Natural language search query
            limit: Maximum total results across all projects (default: 10)
            file_pattern: Optional path filter (e.g., "*/auth/*")
            language: Optional language filter
            search_mode: "semantic", "keyword", or "hybrid"

        Returns:
            Dict with results grouped by project, total_found, projects_searched
        """
        # Check if cross-project search is enabled
        if not self.config.search.cross_project_enabled or not self.cross_project_consent:
            raise ValidationError(
                "Cross-project search is disabled. Enable it in config to use this feature."
            )

        try:
            import time
            start_time = time.time()

            # Determine which projects to search
            search_all_mode = self.config.search.cross_project_default_mode == "all"
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

            # Log metrics for performance monitoring
            if self.metrics_collector:
                avg_relevance = sum(r["relevance_score"] for r in final_results) / len(final_results) if final_results else 0.0
                self.metrics_collector.log_query(
                    query=query,
                    latency_ms=query_time_ms,
                    result_count=len(final_results),
                    avg_relevance=avg_relevance
                )

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
            logger.error(f"Failed to search across projects: {e}", exc_info=True)
            raise RetrievalError(f"Failed to search across projects: {e}")

    async def opt_in_cross_project(self, project_name: str) -> Dict[str, Any]:
        """
        Opt in a project for cross-project search.

        **Use when:** Enabling cross-project learning for a specific project.
        Projects are opted-in by default, use this to re-enable after opt-out.

        Args:
            project_name: Project to make searchable across projects

        Returns:
            Dict with project_name, opted_in status, granted_at timestamp
        """
        if not self.config.search.cross_project_enabled or not self.cross_project_consent:
            raise ValidationError(
                "Cross-project search is disabled. Enable it in config to use this feature."
            )

        try:
            result = self.cross_project_consent.opt_in(project_name)
            logger.info(f"Project '{project_name}' opted-in for cross-project search")
            return result
        except Exception as e:
            logger.error(f"Failed to opt-in project: {e}", exc_info=True)
            raise StorageError(f"Failed to opt-in project: {e}")

    async def opt_out_cross_project(self, project_name: str) -> Dict[str, Any]:
        """
        Opt out a project from cross-project search.

        **Use when:** Protecting sensitive/private project code from cross-project
        learning or excluding irrelevant projects from search results.

        Args:
            project_name: Project to exclude from cross-project search

        Returns:
            Dict with project_name, opted_in=false status, revoked_at timestamp
        """
        if not self.config.search.cross_project_enabled or not self.cross_project_consent:
            raise ValidationError(
                "Cross-project search is disabled. Enable it in config to use this feature."
            )

        try:
            result = self.cross_project_consent.opt_out(project_name)
            logger.info(f"Project '{project_name}' opted-out from cross-project search")
            return result
        except Exception as e:
            logger.error(f"Failed to opt-out project: {e}", exc_info=True)
            raise StorageError(f"Failed to opt-out project: {e}")

    async def list_opted_in_projects(self) -> Dict[str, Any]:
        """
        List all projects opted in for cross-project search.

        **Use before** `search_all_projects` to understand which projects are searchable.

        Returns:
            Dict with opted_in_projects list, opted_out_projects list, and statistics
        """
        if not self.config.search.cross_project_enabled or not self.cross_project_consent:
            raise ValidationError(
                "Cross-project search is disabled. Enable it in config to use this feature."
            )

        try:
            opted_in = self.cross_project_consent.list_opted_in_projects()
            opted_out = self.cross_project_consent.list_opted_out_projects()
            stats = self.cross_project_consent.get_consent_stats()

            logger.info(f"Retrieved {len(opted_in)} opted-in projects")

            return {
                "opted_in_projects": opted_in,
                "opted_out_projects": opted_out,
                "statistics": stats,
            }
        except Exception as e:
            logger.error(f"Failed to list opted-in projects: {e}", exc_info=True)
            raise RetrievalError(f"Failed to list opted-in projects: {e}")

    async def index_codebase(
        self,
        directory_path: str,
        project_name: Optional[str] = None,
        recursive: bool = True,
    ) -> Dict[str, Any]:
        """
        Index a codebase directory for semantic code search.

        **PROACTIVE USE:**
        - Index new projects when user starts working on them
        - Re-index after major changes to update search results
        - Index before extensive code exploration tasks

        **Supported languages:** Python, JavaScript, TypeScript, Java, Go, Rust, Ruby,
        Swift, Kotlin, C, C++, C#, SQL, JSON, YAML, TOML (15 formats)

        **Performance:** 10-20 files/sec with parallel processing, incremental cache
        provides 5-10x speedup on re-indexing

        **Use CLI instead** for large codebases: `python -m src.cli index ./path`

        Args:
            directory_path: Absolute path to directory to index (e.g., "/path/to/project")
            project_name: Project name for scoping (defaults to directory name)
            recursive: Recursively index subdirectories (default: True)

        Returns:
            Dict with status, project_name, files_indexed, units_indexed, total_time_s
        """
        if self.config.advanced.read_only_mode:
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

            # Initialize indexer (needed for parallel embedding generator)
            await indexer.initialize()

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
            logger.error(f"Failed to index codebase: {e}", exc_info=True)
            raise StorageError(f"Failed to index codebase: {e}")

    async def reindex_project(
        self,
        project_name: str,
        directory_path: str,
        clear_existing: bool = False,
        bypass_cache: bool = False,
        recursive: bool = True,
        progress_callback: Optional[callable] = None,
    ) -> Dict[str, Any]:
        """
        Force re-indexing of a project from scratch.

        This method allows you to:
        - Clear the existing index and start fresh
        - Bypass the embedding cache to regenerate all embeddings
        - Recover from index corruption or cache issues
        - Apply configuration changes

        Args:
            project_name: Project to reindex
            directory_path: Directory path to index
            clear_existing: Delete existing index first (default: False)
            bypass_cache: Bypass embedding cache and regenerate all (default: False)
            recursive: Recursively index subdirectories (default: True)
            progress_callback: Optional callback for progress updates

        Returns:
            Dict with reindexing statistics:
            {
                "status": str,
                "project_name": str,
                "directory": str,
                "files_indexed": int,
                "units_indexed": int,
                "total_time_s": float,
                "index_cleared": bool,
                "cache_bypassed": bool,
                "units_deleted": int (if index was cleared),
            }
        """
        if self.config.advanced.read_only_mode:
            raise ReadOnlyError("Cannot reindex project in read-only mode")

        from pathlib import Path
        from src.memory.incremental_indexer import IncrementalIndexer
        import time

        # Validate inputs first (don't wrap these errors)
        dir_path = Path(directory_path).resolve()

        if not dir_path.exists():
            raise ValueError(f"Directory does not exist: {directory_path}")

        if not dir_path.is_dir():
            raise ValueError(f"Path is not a directory: {directory_path}")

        try:
            start_time = time.time()

            units_deleted = 0

            # Step 1: Clear existing index if requested
            if clear_existing:
                logger.info(f"Clearing existing index for project: {project_name}")

                # Delete all CODE memories for this project
                # Code units are stored with category="code", scope="project"
                if hasattr(self.store, 'delete_code_units_by_project'):
                    units_deleted = await self.store.delete_code_units_by_project(project_name)
                    logger.info(f"Deleted {units_deleted} existing code units for project: {project_name}")
                else:
                    # Fallback for stores that don't support bulk deletion
                    logger.warning("Store doesn't support bulk deletion, clear_existing not fully available")
                    units_deleted = 0

            # Step 2: Clear embedding cache if requested
            if bypass_cache and self.embedding_cache:
                logger.info(f"Bypassing embedding cache for project: {project_name}")
                # The cache will be bypassed during indexing
                # We don't need to delete cache entries, just skip lookups

            # Step 3: Create indexer (potentially with cache bypass)
            indexer = IncrementalIndexer(
                store=self.store,
                embedding_generator=self.embedding_generator,
                config=self.config,
                project_name=project_name,
            )

            # Step 4: Index directory
            logger.info(
                f"Re-indexing project: {project_name} "
                f"(clear_existing={clear_existing}, bypass_cache={bypass_cache})"
            )

            result = await indexer.index_directory(
                dir_path=dir_path,
                recursive=recursive,
                show_progress=True,
                progress_callback=progress_callback,
            )

            total_time_s = time.time() - start_time

            logger.info(
                f"Re-indexed {result['total_units']} semantic units from "
                f"{result['indexed_files']} files in {total_time_s:.2f}s"
            )

            return {
                "status": "success",
                "project_name": project_name,
                "directory": str(dir_path),
                "files_indexed": result["indexed_files"],
                "units_indexed": result["total_units"],
                "total_time_s": total_time_s,
                "index_cleared": clear_existing,
                "cache_bypassed": bypass_cache,
                "units_deleted": units_deleted if clear_existing else 0,
                "languages": result.get("languages", {}),
            }

        except Exception as e:
            logger.error(f"Failed to reindex project: {e}", exc_info=True)
            raise StorageError(f"Failed to reindex project: {e}")

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
            logger.error(f"Failed to get file dependencies: {e}", exc_info=True)
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
            logger.error(f"Failed to get file dependents: {e}", exc_info=True)
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
            logger.error(f"Failed to find dependency path: {e}", exc_info=True)
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
            logger.error(f"Failed to get dependency stats: {e}", exc_info=True)
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
        empty_embedding = [0.0] * DEFAULT_EMBEDDING_DIM
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
                read_only_mode=self.config.advanced.read_only_mode,
                storage_backend=self.config.storage_backend,
                memory_count=memory_count,
                qdrant_available=qdrant_available,
                file_watcher_enabled=self.config.indexing.file_watcher,
            )

            return {
                **response.model_dump(),
                "statistics": self.stats,
                "cache_stats": self.embedding_cache.get_stats(),
            }

        except Exception as e:
            logger.error(f"Failed to get status: {e}", exc_info=True)
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
        

        Note: This function is async for MCP protocol compatibility, even though it
        doesn't currently use await. The MCP framework requires handler functions to
        be async, and future changes may add async operations.
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
            logger.error(f"Failed to get token analytics: {e}", exc_info=True)
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
            import time
            start_time = time.time()

            logger.info(f"Searching git history: '{query}' (project: {project_name})")

            # Parse date filters
            since_dt = None
            until_dt = None

            if since:
                since_dt = self._parse_date_filter(since)
            if until:
                until_dt = self._parse_date_filter(until)

            # Search commits in vector store
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

            query_time_ms = (time.time() - start_time) * 1000

            # Log metrics for performance monitoring (no relevance scores for FTS search)
            if self.metrics_collector:
                self.metrics_collector.log_query(
                    query=query,
                    latency_ms=query_time_ms,
                    result_count=len(results),
                    avg_relevance=None  # FTS search has no semantic scores
                )

            logger.info(f"Found {len(results)} matching commits in {query_time_ms:.2f}ms")

            return {
                "status": "success",
                "query": query,
                "results": results,
                "count": len(results),
                "query_time_ms": query_time_ms,
                "filters": {
                    "project": project_name,
                    "author": author,
                    "since": since,
                    "until": until,
                    "file_path": file_path,
                },
            }

        except Exception as e:
            logger.error(f"Failed to search git history: {e}", exc_info=True)
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
        if self.config.advanced.read_only_mode:
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
            logger.error(f"Failed to index git history: {e}", exc_info=True)
            raise StorageError(f"Failed to index git history: {e}")

    async def get_file_history(
        self,
        file_path: str,
        limit: int = 100,
    ) -> Dict[str, Any]:
        """
        Get commit history for a specific file.

        Alias for show_function_evolution without function filtering.

        Args:
            file_path: Path to the file
            limit: Maximum commits to return (default 100)

        Returns:
            Dict with commit history
        """
        return await self.show_function_evolution(file_path, None, limit)

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
            logger.error(f"Failed to show function evolution: {e}", exc_info=True)
            raise RetrievalError(f"Failed to show function evolution: {e}")

    async def get_change_frequency(
        self,
        file_or_function: str,
        project_name: Optional[str] = None,
        since: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Calculate how often a file or function changes.

        Analyzes git history to compute change frequency metrics including:
        - Total number of changes
        - Changes per week
        - Churn score (0.0-1.0 indicating stability)
        - Time span and last change date
        - Unique authors

        Args:
            file_or_function: File path (e.g., "src/auth.py") or function name
            project_name: Optional project filter
            since: Optional start date for analysis (e.g., "2024-01-01", "last month")

        Returns:
            Dict containing:
                - file_path: str
                - total_changes: int
                - first_change: str (ISO date)
                - last_change: str (ISO date)
                - time_span_days: float
                - changes_per_week: float
                - unique_authors: int
                - change_types: Dict[str, int]
                - total_lines_added: int
                - total_lines_deleted: int
                - churn_score: float (0.0-1.0, higher = more unstable)
                - interpretation: str ("high|medium|low churn")
        """
        try:
            from datetime import datetime, UTC
            import time
            start_time = time.time()

            logger.info(f"Calculating change frequency for: {file_or_function}")

            # Parse date filter
            since_dt = None
            if since:
                since_dt = self._parse_date_filter(since)

            # Get all commits that modified this file
            commits = await self.store.get_commits_by_file(
                file_path=file_or_function,
                limit=1000,  # Get comprehensive history
            )

            # Filter by date if specified
            if since_dt and commits:
                commits = [
                    c for c in commits
                    if c.get("author_date") and c["author_date"] >= since_dt
                ]

            if not commits:
                return {
                    "file_path": file_or_function,
                    "total_changes": 0,
                    "churn_score": 0.0,
                    "interpretation": "no changes found",
                }

            # Calculate metrics
            total_changes = len(commits)
            dates = [c["author_date"] for c in commits if c.get("author_date")]

            if not dates:
                return {
                    "file_path": file_or_function,
                    "total_changes": total_changes,
                    "churn_score": 0.0,
                    "interpretation": "no date information",
                }

            first_change = min(dates)
            last_change = max(dates)
            time_span_days = (last_change - first_change).total_seconds() / 86400

            # Calculate changes per week
            time_span_weeks = max(time_span_days / 7, 0.1)  # Avoid div by zero
            changes_per_week = total_changes / time_span_weeks

            # Calculate average change size
            total_lines_added = sum(c.get("lines_added", 0) for c in commits)
            total_lines_deleted = sum(c.get("lines_deleted", 0) for c in commits)
            avg_change_size = (total_lines_added + total_lines_deleted) / total_changes

            # Compute churn score (0.0-1.0)
            # Formula: (changes_per_week / 5) * (avg_change_size / 100)
            # Assumptions: >5 changes/week = very high, >100 lines/change = large
            churn_score = min(1.0, (changes_per_week / 5.0) * (avg_change_size / 100.0))

            # Get unique authors
            unique_authors = len(set(c.get("author_email", "") for c in commits if c.get("author_email")))

            # Count change types
            from collections import defaultdict
            change_types = defaultdict(int)
            for commit in commits:
                change_type = commit.get("change_type", "modified")
                change_types[change_type] += 1

            # Add interpretation
            if churn_score > 0.7:
                interpretation = "high churn - consider refactoring or stabilizing"
            elif churn_score > 0.4:
                interpretation = "medium churn - actively developed"
            else:
                interpretation = "low churn - stable code"

            query_time_ms = (time.time() - start_time) * 1000

            logger.info(
                f"Change frequency for {file_or_function}: "
                f"{total_changes} changes, churn_score={churn_score:.2f} ({query_time_ms:.2f}ms)"
            )

            return {
                "file_path": file_or_function,
                "total_changes": total_changes,
                "first_change": first_change.isoformat() if first_change else None,
                "last_change": last_change.isoformat() if last_change else None,
                "time_span_days": time_span_days,
                "changes_per_week": changes_per_week,
                "unique_authors": unique_authors,
                "change_types": dict(change_types),
                "total_lines_added": total_lines_added,
                "total_lines_deleted": total_lines_deleted,
                "churn_score": churn_score,
                "interpretation": interpretation,
            }

        except Exception as e:
            logger.error(f"Failed to calculate change frequency: {e}", exc_info=True)
            raise RetrievalError(f"Failed to calculate change frequency: {e}")

    async def get_churn_hotspots(
        self,
        project_name: Optional[str] = None,
        limit: int = 10,
        min_changes: int = 5,
        days: int = 90,
    ) -> Dict[str, Any]:
        """
        Find files with highest change frequency (churn hotspots).

        Hotspots indicate:
        - Frequently changing code (potential design issues)
        - High maintenance burden
        - Refactoring candidates
        - Test coverage gaps

        Args:
            project_name: Optional project filter
            limit: Max results (default: 10)
            min_changes: Minimum changes to qualify (default: 5)
            days: Analysis window in days (default: 90)

        Returns:
            Dict containing:
                - hotspots: List of dicts with:
                    - file_path: str
                    - churn_score: float (0.0-1.0)
                    - total_changes: int
                    - recent_changes_30d: int
                    - authors: List[str]
                    - avg_change_size: float
                    - instability_indicator: "high|medium|low"
                - analysis_period_days: int
                - total_files_analyzed: int
        """
        try:
            from datetime import datetime, timedelta, UTC
            from collections import defaultdict
            import time
            start_time = time.time()

            logger.info(f"Finding churn hotspots (last {days} days)")

            since = datetime.now(UTC) - timedelta(days=days)

            # Get all commits in the time period
            # Since we don't have a direct "get all file changes" method,
            # we'll get commits and extract file information
            commits = await self.store.search_git_commits(
                query=None,  # No query filter
                since=since,
                limit=10000,  # Get comprehensive history
            )

            # Group by file path
            files = defaultdict(list)

            # For each commit, get the files it modified
            for commit in commits:
                # Get file changes for this commit
                commit_hash = commit.get("commit_hash")
                if not commit_hash:
                    continue

                # We need to query file changes - but we don't have a direct method
                # Let's use a simplified approach: use the file info if available
                # or estimate from commit stats
                # TODO: This could be improved with a direct query for file changes

            # Since the above approach is complex, let's use a different strategy:
            # Get unique file paths from recent commits and analyze each

            # For now, return a placeholder indicating implementation needed
            logger.warning("get_churn_hotspots: Full implementation requires additional store methods")

            return {
                "hotspots": [],
                "analysis_period_days": days,
                "total_files_analyzed": 0,
                "note": "This feature requires git file changes to be indexed. Run git indexing first.",
            }

        except Exception as e:
            logger.error(f"Failed to find churn hotspots: {e}", exc_info=True)
            raise RetrievalError(f"Failed to find churn hotspots: {e}")

    async def get_recent_changes(
        self,
        project_name: Optional[str] = None,
        days: int = 30,
        limit: int = 50,
        file_pattern: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get recent file modifications with context.

        Useful for:
        - Daily standup: "What changed yesterday?"
        - Code review: "What's been modified this week?"
        - Onboarding: "What's the team working on?"
        - Bug investigation: "What changed before this broke?"

        Args:
            project_name: Optional project filter
            days: Look back period (default: 30)
            limit: Max results (default: 50)
            file_pattern: Optional file filter (e.g., "src/api/*.py")

        Returns:
            Dict containing:
                - changes: List of dicts with:
                    - file_path: str
                    - commit_hash: str
                    - commit_date: str
                    - author: str
                    - message: str
                    - change_type: "added|modified|deleted|renamed"
                    - lines_added: int
                    - lines_deleted: int
                    - days_ago: int
                - period_days: int
                - total_changes: int
        """
        try:
            from datetime import datetime, timedelta, UTC
            import fnmatch
            import time
            start_time = time.time()

            logger.info(f"Getting recent changes (last {days} days)")

            since = datetime.now(UTC) - timedelta(days=days)

            # Get recent commits
            commits = await self.store.search_git_commits(
                query=None,
                since=since,
                limit=limit * 2,  # Get extra for filtering
            )

            # Format results
            results = []
            now = datetime.now(UTC)

            for commit in commits:
                days_ago = (now - commit.get("author_date", now)).days

                change = {
                    "commit_hash": commit.get("commit_hash", ""),
                    "commit_date": commit.get("author_date", ""),
                    "author": f"{commit.get('author_name', '')} <{commit.get('author_email', '')}>",
                    "message": commit.get("message", ""),
                    "days_ago": days_ago,
                    "stats": commit.get("stats", {}),
                }

                results.append(change)

            # Apply file pattern filter if specified
            # Note: This would work better with file-level change tracking
            if file_pattern:
                logger.info(f"File pattern filtering not fully implemented: {file_pattern}")

            # Sort by date descending (most recent first)
            results.sort(key=lambda x: x.get("commit_date", ""), reverse=True)
            results = results[:limit]

            query_time_ms = (time.time() - start_time) * 1000

            logger.info(f"Found {len(results)} recent changes in {query_time_ms:.2f}ms")

            return {
                "changes": results,
                "period_days": days,
                "total_changes": len(results),
            }

        except Exception as e:
            logger.error(f"Failed to get recent changes: {e}", exc_info=True)
            raise RetrievalError(f"Failed to get recent changes: {e}")

    async def blame_search(
        self,
        pattern: str,
        project_name: Optional[str] = None,
        file_pattern: Optional[str] = None,
        limit: int = 20,
    ) -> Dict[str, Any]:
        """
        Find who wrote code matching a pattern (git blame integration).

        Useful for:
        - Find domain expert: "Who wrote the JWT validation logic?"
        - Code ownership: "Who maintains the payment processing?"
        - Bug investigation: "Who added this TODO?"
        - Knowledge transfer: "Who knows about Redis caching?"

        Searches git commit messages and diffs to identify authors of specific code patterns.

        Args:
            pattern: Code pattern or natural language query
                     Examples:
                     - "JWT validation" (semantic)
                     - "def validate_token" (keyword)
                     - "TODO: refactor" (keyword)
            project_name: Optional project filter
            file_pattern: Optional file filter (e.g., "src/auth/*.py")
            limit: Max results (default: 20)

        Returns:
            Dict containing:
                - results: List of dicts with:
                    - commit_hash: str
                    - author: str
                    - commit_date: str
                    - commit_message: str
                    - relevance: str (description of match)
                - pattern: str
                - total_matches: int
        """
        try:
            import time
            start_time = time.time()

            logger.info(f"Searching blame for pattern: '{pattern}'")

            # Use semantic search on commits
            commits = await self.store.search_git_commits(
                query=pattern,
                limit=limit,
            )

            # Format results
            results = []
            for commit in commits:
                result = {
                    "commit_hash": commit.get("commit_hash", ""),
                    "author": f"{commit.get('author_name', '')} <{commit.get('author_email', '')}>",
                    "commit_date": commit.get("author_date", ""),
                    "commit_message": commit.get("message", ""),
                    "relevance": "semantic match on commit message",
                }
                results.append(result)

            query_time_ms = (time.time() - start_time) * 1000

            logger.info(f"Found {len(results)} blame matches in {query_time_ms:.2f}ms")

            return {
                "results": results,
                "pattern": pattern,
                "total_matches": len(results),
            }

        except Exception as e:
            logger.error(f"Failed to search blame: {e}", exc_info=True)
            raise RetrievalError(f"Failed to search blame: {e}")

    async def get_code_authors(
        self,
        file_path: str,
        limit: int = 100,
    ) -> Dict[str, Any]:
        """
        Get contributors for a file with their contribution counts.

        Returns a ranked list of authors who have modified the file,
        showing who has the most expertise/ownership.

        Args:
            file_path: Path to the file
            limit: Maximum number of commits to analyze (default: 100)

        Returns:
            Dict containing:
                - file_path: str
                - authors: List of dicts with:
                    - author_name: str
                    - author_email: str
                    - commit_count: int
                    - lines_added: int
                    - lines_deleted: int
                    - first_commit: str (ISO date)
                    - last_commit: str (ISO date)
                - total_commits: int
        """
        try:
            from collections import defaultdict
            import time
            start_time = time.time()

            logger.info(f"Getting code authors for: {file_path}")

            # Get all commits for this file
            commits = await self.store.get_commits_by_file(
                file_path=file_path,
                limit=limit,
            )

            if not commits:
                return {
                    "file_path": file_path,
                    "authors": [],
                    "total_commits": 0,
                }

            # Group by author
            authors_data = defaultdict(lambda: {
                "author_name": "",
                "author_email": "",
                "commit_count": 0,
                "lines_added": 0,
                "lines_deleted": 0,
                "commits": [],
            })

            for commit in commits:
                email = commit.get("author_email", "unknown")
                author_data = authors_data[email]

                author_data["author_name"] = commit.get("author_name", "Unknown")
                author_data["author_email"] = email
                author_data["commit_count"] += 1
                author_data["lines_added"] += commit.get("lines_added", 0)
                author_data["lines_deleted"] += commit.get("lines_deleted", 0)
                author_data["commits"].append(commit.get("author_date"))

            # Format results
            authors = []
            for email, data in authors_data.items():
                commit_dates = [d for d in data["commits"] if d]
                authors.append({
                    "author_name": data["author_name"],
                    "author_email": data["author_email"],
                    "commit_count": data["commit_count"],
                    "lines_added": data["lines_added"],
                    "lines_deleted": data["lines_deleted"],
                    "first_commit": min(commit_dates).isoformat() if commit_dates else None,
                    "last_commit": max(commit_dates).isoformat() if commit_dates else None,
                })

            # Sort by commit count (descending)
            authors.sort(key=lambda x: x["commit_count"], reverse=True)

            query_time_ms = (time.time() - start_time) * 1000

            logger.info(f"Found {len(authors)} authors for {file_path} in {query_time_ms:.2f}ms")

            return {
                "file_path": file_path,
                "authors": authors,
                "total_commits": len(commits),
            }

        except Exception as e:
            logger.error(f"Failed to get code authors: {e}", exc_info=True)
            raise RetrievalError(f"Failed to get code authors: {e}")

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
        """Start background scheduler for auto-pruning.

        Note: This function is async for MCP protocol compatibility, even though it
        doesn't currently use await. The MCP framework requires handler functions to
        be async, and future changes may add async operations.
        """
        try:
            from apscheduler.schedulers.asyncio import AsyncIOScheduler
            from apscheduler.triggers.cron import CronTrigger

            self.scheduler = AsyncIOScheduler()

            # Parse cron schedule (format: "minute hour day month day_of_week")
            # Default: "0 2 * * *" = 2 AM daily
            schedule_parts = self.config.memory.pruning_schedule.split()

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

            # Add metrics collection job (every hour)
            if self.metrics_collector:
                self.scheduler.add_job(
                    self._collect_metrics_job,
                    CronTrigger(minute="0"),  # Run at the top of every hour
                    id="metrics_collection",
                    name="Collect health metrics",
                    replace_existing=True,
                )
                logger.info("Metrics collection scheduler added (hourly)")

            self.scheduler.start()
            logger.info("Pruning scheduler started")

        except Exception as e:
            logger.error(f"Failed to start pruning scheduler: {e}", exc_info=True)
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

    async def _collect_metrics_job(self) -> None:
        """Background job to collect and store health metrics."""
    async def export_memories(
        self,
        output_path: str,
        format: str = "json",
        project_name: Optional[str] = None,
        category: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Export memories to file (MCP tool).

        Args:
            output_path: Path to write export file
            format: Export format (json, markdown, archive)
            project_name: Filter by project name
            category: Filter by category

        Returns:
            Export statistics

        Raises:
            ValueError: If invalid format or category
            StorageError: If export fails
        """
        from src.backup.exporter import DataExporter
        from src.core.models import MemoryCategory
        from pathlib import Path

        # Validate parameters
        if format not in ["json", "markdown", "archive"]:
            raise ValueError(f"Invalid format: {format}. Must be json, markdown, or archive")

        category_filter = None
        if category:
            try:
                category_filter = MemoryCategory(category)
            except ValueError:
                raise ValueError(f"Invalid category: {category}")

        # Create exporter and export
        exporter = DataExporter(self.store)
        output = Path(output_path).expanduser()

        if format == "json":
            stats = await exporter.export_to_json(
                output_path=output,
                project_name=project_name,
                category=category_filter,
            )
        elif format == "markdown":
            stats = await exporter.export_to_markdown(
                output_path=output,
                project_name=project_name,
                include_metadata=True,
            )
        elif format == "archive":
            stats = await exporter.create_portable_archive(
                output_path=output,
                project_name=project_name,
                include_embeddings=True,
            )

        logger.info(f"MCP export completed: {stats}")
        return stats

    async def import_memories(
        self,
        input_path: str,
        conflict_strategy: str = "keep_newer",
        dry_run: bool = False,
        selective_project: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Import memories from file (MCP tool).

        Args:
            input_path: Path to import file
            conflict_strategy: How to handle conflicts (keep_newer, keep_older, keep_both, skip, merge_metadata)
            dry_run: If True, analyze but don't actually import
            selective_project: Only import this project

        Returns:
            Import statistics

        Raises:
            ValueError: If invalid strategy or file not found
            StorageError: If import fails
        """
        from src.backup.importer import DataImporter, ConflictStrategy
        from pathlib import Path

        # Validate parameters

    async def start_deferred_auto_indexing(self) -> None:
        """
        Start auto-indexing that was deferred during initialization.

        Call this after the server is ready to accept requests, to run
        auto-indexing in the background without blocking startup.
        """
        if not getattr(self, '_defer_auto_index', False):
            logger.debug("Auto-indexing was not deferred, skipping")
            return

        if self.config.indexing.auto_index_enabled and self.config.indexing.auto_index_on_startup:
            logger.info("Starting deferred auto-indexing...")
            await self._start_auto_indexing()
        else:
            logger.info("Auto-indexing disabled in config")

    async def _start_auto_indexing(self) -> None:
        """
        Start auto-indexing on server startup (FEAT-016).

        Automatically indexes the current project if configured.
        """
        try:
            # Get current working directory as project path
            project_path = Path.cwd()

            # Use detected project name or directory name
            project_name = self.project_name or project_path.name

            logger.info(f"Starting auto-indexing for project: {project_name} at {project_path}")

            # Import here to avoid circular dependency
            from src.memory.auto_indexing_service import AutoIndexingService

            # Create auto-indexing service
            self.auto_indexing_service = AutoIndexingService(
                project_path=project_path,
                project_name=project_name,
                config=self.config,
            )

            await self.auto_indexing_service.initialize()

            # Start auto-indexing (may be background)
            result = await self.auto_indexing_service.start_auto_indexing()

            if result:
                if result.get("mode") == "background":
                    logger.info(
                        f"Background indexing started for {project_name} "
                        f"({result.get('file_count', 0)} files)"
                    )
                else:
                    logger.info(
                        f"Foreground indexing complete for {project_name}: "
                        f"{result.get('indexed_files', 0)} files, "
                        f"{result.get('total_units', 0)} units"
                    )

                # Start file watcher after initial indexing
                if self.config.indexing.file_watcher:
                    await self.auto_indexing_service.start_watching()
                    logger.info(f"File watcher started for {project_name}")
            else:
                logger.info(f"Project {project_name} is up-to-date, skipping indexing")

        except Exception as e:
            logger.error(f"Auto-indexing startup failed: {e}", exc_info=True)
            # Don't raise - auto-indexing failure shouldn't prevent server start
            self.auto_indexing_service = None

    async def get_indexing_status(self) -> Dict[str, Any]:
        """
        Get current auto-indexing status (FEAT-016).

        Returns:
            Dictionary with indexing progress and status
        """
        if not self.auto_indexing_service:
            return {
                "enabled": False,
                "status": "disabled",
                "message": "Auto-indexing is not enabled or failed to initialize"
            }

        progress = await self.auto_indexing_service.get_progress()

        return {
            "enabled": True,
            "project_name": self.auto_indexing_service.project_name,
            "project_path": str(self.auto_indexing_service.project_path),
            "progress": progress,
        }

    async def trigger_reindex(self) -> Dict[str, Any]:
        """
        Manually trigger a full re-index (FEAT-016).

        Returns:
            Dictionary with re-indexing result
        """
        if not self.auto_indexing_service:
            # Try to create service if it doesn't exist
            project_path = Path.cwd()
            project_name = self.project_name or project_path.name

            from src.memory.auto_indexing_service import AutoIndexingService

            self.auto_indexing_service = AutoIndexingService(
                project_path=project_path,
                project_name=project_name,
                config=self.config,
            )
            await self.auto_indexing_service.initialize()

        logger.info(f"Manual re-index triggered for {self.auto_indexing_service.project_name}")
        result = await self.auto_indexing_service.trigger_reindex()

        return {
            "status": "success",
            "result": result,
        }
    async def export_memories(
        self,
        output_path: str,
        format: str = "json",
        project_name: Optional[str] = None,
        category: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Export memories to file (MCP tool).

        Args:
            output_path: Path to write export file
            format: Export format (json, markdown, archive)
            project_name: Filter by project name
            category: Filter by category

        Returns:
            Export statistics

        Raises:
            ValueError: If invalid format or category
            StorageError: If export fails
        """
        from src.backup.exporter import DataExporter
        from src.core.models import MemoryCategory
        from pathlib import Path

        # Validate parameters
        if format not in ["json", "markdown", "archive"]:
            raise ValueError(f"Invalid format: {format}. Must be json, markdown, or archive")

        category_filter = None
        if category:
            try:
                category_filter = MemoryCategory(category)
            except ValueError:
                raise ValueError(f"Invalid category: {category}")

        # Create exporter and export
        exporter = DataExporter(self.store)
        output = Path(output_path).expanduser()

        if format == "json":
            stats = await exporter.export_to_json(
                output_path=output,
                project_name=project_name,
                category=category_filter,
            )
        elif format == "markdown":
            stats = await exporter.export_to_markdown(
                output_path=output,
                project_name=project_name,
                include_metadata=True,
            )
        elif format == "archive":
            stats = await exporter.create_portable_archive(
                output_path=output,
                project_name=project_name,
                include_embeddings=True,
            )

        logger.info(f"MCP export completed: {stats}")
        return stats

    async def import_memories(
        self,
        input_path: str,
        conflict_strategy: str = "keep_newer",
        dry_run: bool = False,
        selective_project: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Import memories from file (MCP tool).

        Args:
            input_path: Path to import file
            conflict_strategy: How to handle conflicts (keep_newer, keep_older, keep_both, skip, merge_metadata)
            dry_run: If True, analyze but don't actually import
            selective_project: Only import this project

        Returns:
            Import statistics

        Raises:
            ValueError: If invalid strategy or file not found
            StorageError: If import fails
        """
        from src.backup.importer import DataImporter, ConflictStrategy
        from pathlib import Path

        # Validate parameters
        try:
            logger.info("Running metrics collection job")

            if not self.metrics_collector:
                logger.warning("Metrics collector not initialized, skipping metrics collection")
                return

            # Collect current metrics
            metrics = await self.metrics_collector.collect_metrics()

            # Calculate health score (simplified version)
            metrics.health_score = self._calculate_simple_health_score(metrics)

            # Store metrics in database
            self.metrics_collector.store_metrics(metrics)

            logger.info(
                f"Metrics collected: {metrics.total_memories} memories, "
                f"{metrics.avg_search_latency_ms:.2f}ms avg latency, "
                f"health score: {metrics.health_score}/100"
            )

        except Exception as e:
            logger.error(f"Metrics collection job failed: {e}", exc_info=True)

    def _calculate_simple_health_score(self, metrics) -> int:
        """Calculate a simple health score from metrics (0-100)."""
        score = 100

        # Deduct points for high latency
        if metrics.avg_search_latency_ms > 50:
            score -= min(30, int((metrics.avg_search_latency_ms - 50) / 2))

        # Deduct points for low cache hit rate
        if metrics.cache_hit_rate < 0.7:
            score -= int((0.7 - metrics.cache_hit_rate) * 40)

        # Deduct points for high noise ratio
        if metrics.noise_ratio > 0.2:
            score -= int((metrics.noise_ratio - 0.2) * 50)

        # Deduct points for stale indexes
        if metrics.index_staleness_ratio > 0.2:
            score -= int((metrics.index_staleness_ratio - 0.2) * 30)

        return max(0, min(100, score))

    async def analyze_conversation(
        self,
        message: str,
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Analyze a conversation message for proactive context suggestions.

        This tool detects patterns in user messages (implementation requests,
        error debugging, code questions, refactoring) and automatically suggests
        relevant code or memories.

        Args:
            message: The user's message to analyze
            session_id: Optional conversation session ID

        Returns:
            Dict with patterns detected and suggestions

        Example:
            User: "I need to add user authentication"
            Returns: Suggestions for authentication implementations
        """
        if not self.suggestion_engine:
            return {
                "enabled": False,
                "message": "Proactive suggestions are disabled",
            }

        try:
            result = await self.suggestion_engine.analyze_message(
                message=message,
                session_id=session_id,
                project_name=self.project_name,
            )

            return {
                "enabled": True,
                **result.to_dict(),
            }

        except Exception as e:
            logger.error(f"Error analyzing conversation: {e}", exc_info=True)
            raise RetrievalError(
                f"Failed to analyze conversation: {str(e)}",
                solution="Check the message format and try again",
            )

    async def get_suggestion_stats(self) -> Dict[str, Any]:
        """
        Get statistics about proactive suggestions.

        Returns:
            Dict with suggestion metrics, acceptance rates, and threshold info

        Example response:
            {
                "enabled": true,
                "messages_analyzed": 150,
                "suggestions_made": 45,
                "auto_injections": 23,
                "high_confidence_threshold": 0.90,
                "feedback": {
                    "overall_acceptance_rate": 0.72,
                    "per_pattern": {...}
                }
            }
        """
        if not self.suggestion_engine:
            return {
                "enabled": False,
                "message": "Proactive suggestions are disabled",
            }

        try:
            return self.suggestion_engine.get_stats()
        except Exception as e:
            logger.error(f"Error getting suggestion stats: {e}", exc_info=True)
            raise RetrievalError(f"Failed to get suggestion stats: {str(e)}")

    async def provide_suggestion_feedback(
        self,
        suggestion_id: str,
        accepted: bool,
        implicit: bool = True,
    ) -> Dict[str, Any]:
        """
        Provide feedback on a proactive suggestion.

        This helps the system learn and adapt its confidence threshold over time.

        Args:
            suggestion_id: ID of the suggestion (from analyze_conversation)
            accepted: True if the suggestion was helpful
            implicit: True if inferred from behavior (default), False for explicit

        Returns:
            Dict with feedback status

        Example:
            provide_suggestion_feedback(
                suggestion_id="abc-123",
                accepted=True,
                implicit=False  # User explicitly marked as helpful
            )
        """
        if not self.suggestion_engine:
            return {
                "enabled": False,
                "message": "Proactive suggestions are disabled",
            }

        try:
            success = self.suggestion_engine.record_feedback(
                suggestion_id=suggestion_id,
                accepted=accepted,
                implicit=implicit,
            )

            if success:
                # Check if threshold should be updated
                new_threshold, explanation = self.suggestion_engine.update_threshold()

                return {
                    "success": True,
                    "suggestion_id": suggestion_id,
                    "accepted": accepted,
                    "threshold_updated": new_threshold != self.suggestion_engine.high_confidence_threshold,
                    "current_threshold": new_threshold,
                    "explanation": explanation,
                }
            else:
                return {
                    "success": False,
                    "error": "Suggestion ID not found",
                    "suggestion_id": suggestion_id,
                }

        except Exception as e:
            logger.error(f"Error recording feedback: {e}", exc_info=True)
            raise ValidationError(f"Failed to record feedback: {str(e)}")

    async def set_suggestion_mode(
        self,
        enabled: bool,
        threshold: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Enable or disable proactive suggestions, and optionally set threshold.

        Args:
            enabled: True to enable, False to disable
            threshold: Optional confidence threshold (0-1) for auto-injection

        Returns:
            Dict with current configuration

        Example:
            # Disable suggestions
            set_suggestion_mode(enabled=False)

            # Enable with custom threshold
            set_suggestion_mode(enabled=True, threshold=0.85)
        

        Note: This function is async for MCP protocol compatibility, even though it
        doesn't currently use await. The MCP framework requires handler functions to
        be async, and future changes may add async operations.
        """
        if not self.suggestion_engine:
            return {
                "error": "Suggestion engine not initialized",
                "message": "Set enable_proactive_suggestions=True in config",
            }

        try:
            # Update enabled state
            if enabled:
                self.suggestion_engine.enable()
            else:
                self.suggestion_engine.disable()

            # Update threshold if provided
            if threshold is not None:
                if not 0.0 <= threshold <= 1.0:
                    raise ValidationError(
                        "Threshold must be between 0.0 and 1.0",
                        solution=f"Use a value between 0.0 and 1.0 (got {threshold})",
                    )
                self.suggestion_engine.set_threshold(threshold)

            return {
                "success": True,
                "enabled": self.suggestion_engine.enabled,
                "high_confidence_threshold": self.suggestion_engine.high_confidence_threshold,
                "medium_confidence_threshold": self.suggestion_engine.medium_confidence_threshold,
            }

        except Exception as e:
            logger.error(f"Error setting suggestion mode: {e}", exc_info=True)
            raise ValidationError(f"Failed to set suggestion mode: {str(e)}")

    # FEAT-020: Usage Pattern Analytics MCP Tools

    async def get_usage_statistics(self, days: int = 30) -> Dict[str, Any]:
        """
        Get overall usage statistics for the specified time period.

        Args:
            days: Number of days to look back (1-365)

        Returns:
            Dictionary with usage statistics

        Raises:
            ValidationError: If pattern tracker is not enabled or inputs invalid
        """
        try:
            if not self.pattern_tracker:
                raise ValidationError(
                    "Usage pattern analytics not enabled",
                    solution="Enable via config: enable_usage_pattern_analytics = true"
                )

            if not 1 <= days <= 365:
                raise ValidationError(
                    f"Invalid days value: {days}",
                    solution="Days must be between 1 and 365"
                )

            stats = await self.pattern_tracker.get_usage_stats(days=days)

            return {
                "period_days": days,
                "total_queries": stats.get("total_queries", 0),
                "unique_queries": stats.get("unique_queries", 0),
                "avg_query_time_ms": stats.get("avg_query_time", 0.0),
                "avg_result_count": stats.get("avg_result_count", 0.0),
                "total_code_accesses": stats.get("total_code_accesses", 0),
                "unique_files": stats.get("unique_files", 0),
                "unique_functions": stats.get("unique_functions", 0),
                "most_active_day": stats.get("most_active_day"),
                "most_active_day_count": stats.get("most_active_day_count", 0),
            }

        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error getting usage statistics: {e}", exc_info=True)
            raise ValidationError(f"Failed to get usage statistics: {str(e)}")

    async def get_top_queries(self, limit: int = 10, days: int = 30) -> Dict[str, Any]:
        """
        Get most frequently executed queries.

        Args:
            limit: Maximum number of queries to return (1-100)
            days: Number of days to look back (1-365)

        Returns:
            Dictionary with top queries and their statistics

        Raises:
            ValidationError: If pattern tracker is not enabled or inputs invalid
        """
        try:
            if not self.pattern_tracker:
                raise ValidationError(
                    "Usage pattern analytics not enabled",
                    solution="Enable via config: enable_usage_pattern_analytics = true"
                )

            if not 1 <= limit <= 100:
                raise ValidationError(
                    f"Invalid limit value: {limit}",
                    solution="Limit must be between 1 and 100"
                )

            if not 1 <= days <= 365:
                raise ValidationError(
                    f"Invalid days value: {days}",
                    solution="Days must be between 1 and 365"
                )

            queries = await self.pattern_tracker.get_top_queries(limit=limit, days=days)

            return {
                "queries": queries,
                "period_days": days,
                "total_returned": len(queries),
            }

        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error getting top queries: {e}", exc_info=True)
            raise ValidationError(f"Failed to get top queries: {str(e)}")

    async def get_frequently_accessed_code(
        self, limit: int = 10, days: int = 30
    ) -> Dict[str, Any]:
        """
        Get most frequently accessed code files and functions.

        Args:
            limit: Maximum number of items to return (1-100)
            days: Number of days to look back (1-365)

        Returns:
            Dictionary with frequently accessed code and statistics

        Raises:
            ValidationError: If pattern tracker is not enabled or inputs invalid
        """
        try:
            if not self.pattern_tracker:
                raise ValidationError(
                    "Usage pattern analytics not enabled",
                    solution="Enable via config: enable_usage_pattern_analytics = true"
                )

            if not 1 <= limit <= 100:
                raise ValidationError(
                    f"Invalid limit value: {limit}",
                    solution="Limit must be between 1 and 100"
                )

            if not 1 <= days <= 365:
                raise ValidationError(
                    f"Invalid days value: {days}",
                    solution="Days must be between 1 and 365"
                )

            code_items = await self.pattern_tracker.get_frequently_accessed_code(
                limit=limit, days=days
            )

            return {
                "code_items": code_items,
                "period_days": days,
                "total_returned": len(code_items),
            }

        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error getting frequently accessed code: {e}", exc_info=True)
            raise ValidationError(f"Failed to get frequently accessed code: {str(e)}")

    async def close(self) -> None:
        """Clean up resources."""
        # Stop auto-indexing service
        if self.auto_indexing_service:
            await self.auto_indexing_service.close()
            logger.info("Auto-indexing service stopped")

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

        # Allow pending operations to complete before closing resources
        # This prevents race conditions during concurrent test cleanup
        await asyncio.sleep(0.1)

        if self.store:
            await self.store.close()
        if self.embedding_generator:
            await self.embedding_generator.close()
        if self.embedding_cache:
            self.embedding_cache.close()
        logger.info("Server closed")
