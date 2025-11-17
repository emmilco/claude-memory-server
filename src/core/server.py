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
    ) -> Dict[str, Any]:
        """
        Retrieve memories similar to the query.

        Args:
            query: Search query
            limit: Maximum results to return
            context_level: Filter by context level
            scope: Filter by scope
            project_name: Filter by project name
            category: Filter by category
            min_importance: Minimum importance threshold
            tags: Filter by tags

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
            # Generate query embedding
            query_embedding = await self._get_embedding(query)

            # Build filters
            filters = SearchFilters(
                context_level=request.context_level,
                scope=request.scope,
                project_name=request.project_name,
                category=request.category,
                min_importance=request.min_importance,
                tags=request.tags,
            )

            # Retrieve from store
            results = await self.store.retrieve(
                query_embedding=query_embedding,
                filters=filters if any(filters.to_dict().values()) else None,
                limit=request.limit,
            )

            # Update stats for successful retrieval
            self.stats["queries_retrieved"] += 1

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
    ) -> Dict[str, Any]:
        """
        Search indexed code semantically.

        This searches through indexed code semantic units (functions, classes)
        and returns relevant code snippets with file locations.

        Args:
            query: Search query (e.g., "authentication logic", "database connection")
            project_name: Optional project name filter (uses current project if not specified)
            limit: Maximum number of results (default 5)
            file_pattern: Optional file path pattern filter (e.g., "*/auth/*")
            language: Optional language filter (e.g., "python", "javascript")

        Returns:
            Dict with code search results including file paths, line numbers, and code snippets
        """
        try:
            import time
            start_time = time.time()

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

            # Retrieve from store
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

            return {
                "results": code_results,
                "total_found": len(code_results),
                "query": query,
                "project_name": filter_project_name,
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

    async def close(self) -> None:
        """Clean up resources."""
        if self.store:
            await self.store.close()
        if self.embedding_generator:
            await self.embedding_generator.close()
        if self.embedding_cache:
            self.embedding_cache.close()
        logger.info("Server closed")
