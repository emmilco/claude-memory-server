"""Code Indexing Service - Code search, indexing, and dependency analysis.

Extracted from MemoryRAGServer (REF-016) to provide focused code operations.

Responsibilities:
- Index codebases for semantic search
- Search code semantically
- Find similar code snippets
- Analyze dependencies and relationships
- Track indexed files and units
"""

import asyncio
import logging
import threading
import time
from pathlib import Path
from typing import Optional, Dict, Any, List, Callable

from src.config import ServerConfig, DEFAULT_EMBEDDING_DIM
from src.store import MemoryStore
from src.embeddings.generator import EmbeddingGenerator
from src.embeddings.cache import EmbeddingCache
from src.core.models import (
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
from src.core.tracing import get_logger

logger = get_logger(__name__)


class CodeIndexingService:
    """
    Service for code indexing, search, and dependency analysis.

    This service handles all code-related operations including indexing
    codebases for semantic search, finding similar code, and analyzing
    import dependencies.
    """

    def __init__(
        self,
        store: MemoryStore,
        embedding_generator: EmbeddingGenerator,
        embedding_cache: EmbeddingCache,
        config: ServerConfig,
        hybrid_searcher: Optional[Any] = None,
        metrics_collector: Optional[Any] = None,
        duplicate_detector: Optional[Any] = None,
        quality_analyzer: Optional[Any] = None,
        project_name: Optional[str] = None,
    ):
        """
        Initialize the Code Indexing Service.

        Args:
            store: Memory store backend
            embedding_generator: Embedding generator for semantic search
            embedding_cache: Cache for embeddings
            config: Server configuration
            hybrid_searcher: Optional hybrid searcher for combined search
            metrics_collector: Optional metrics collector for monitoring
            duplicate_detector: Optional duplicate detector for quality analysis
            quality_analyzer: Optional quality analyzer for code metrics
            project_name: Current project name
        """
        self.store = store
        self.embedding_generator = embedding_generator
        self.embedding_cache = embedding_cache
        self.config = config
        self.hybrid_searcher = hybrid_searcher
        self.metrics_collector = metrics_collector
        self.duplicate_detector = duplicate_detector
        self.quality_analyzer = quality_analyzer
        self.project_name = project_name

        # Service statistics
        self.stats = {
            "searches_performed": 0,
            "files_indexed": 0,
            "units_indexed": 0,
            "similar_code_searches": 0,
        }
        self._stats_lock = threading.Lock()

    def get_stats(self) -> Dict[str, Any]:
        """Get code indexing service statistics."""
        with self._stats_lock:
            return self.stats.copy()

    async def _get_embedding(self, text: str) -> List[float]:
        """Get embedding for text, using cache if available."""
        cached = await self.embedding_cache.get(text, self.config.embedding_model)
        if cached is not None:
            return cached

        embedding = await self.embedding_generator.generate(text)
        await self.embedding_cache.set(text, self.config.embedding_model, embedding)
        return embedding

    @staticmethod
    def _get_confidence_label(score: float) -> str:
        """Convert relevance score to human-readable confidence label."""
        if score > 0.8:
            return "excellent"
        elif score >= 0.6:
            return "good"
        else:
            return "weak"

    def _analyze_search_quality(
        self,
        results: List[Dict[str, Any]],
        query: str,
        project_name: Optional[str]
    ) -> Dict[str, Any]:
        """Analyze search result quality and provide suggestions."""
        if not results:
            return {
                "quality": "no_results",
                "confidence": "none",
                "interpretation": f"No code found matching '{query}'",
                "suggestions": [
                    f"Verify that code has been indexed for project '{project_name or 'current'}'",
                    "Try rephrasing the query or using more specific terms",
                    "Check if the search mode (semantic/keyword/hybrid) is appropriate",
                ],
                "matched_keywords": [],
            }

        scores = [r.get("relevance_score", 0) for r in results]
        max_score = max(scores)
        avg_score = sum(scores) / len(scores) if scores else 0.0

        if max_score >= 0.85:
            quality = "excellent"
            confidence = "high"
            interpretation = f"Found {len(results)} highly relevant results"
        elif max_score >= 0.7:
            quality = "good"
            confidence = "medium"
            interpretation = f"Found {len(results)} relevant results"
        elif max_score >= 0.5:
            quality = "fair"
            confidence = "low"
            interpretation = f"Found {len(results)} possibly relevant results"
        else:
            quality = "poor"
            confidence = "very_low"
            interpretation = f"Found {len(results)} weakly matching results"

        suggestions = []
        if max_score < 0.7:
            suggestions.append("Try using more specific search terms")
            suggestions.append("Consider using hybrid search mode for better results")

        if len(results) == 1:
            suggestions.append("Only one result found - consider broadening search")

        # Extract keywords from query
        query_keywords = [w.lower() for w in query.split() if len(w) > 2]

        # Analyze keyword matches
        matched_keywords = []
        for keyword in query_keywords:
            for result in results[:3]:
                content = result.get("code", "").lower()
                if keyword in content:
                    matched_keywords.append(keyword)
                    break

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
        min_complexity: Optional[int] = None,
        max_complexity: Optional[int] = None,
        has_duplicates: Optional[bool] = None,
        long_functions: Optional[bool] = None,
        maintainability_min: Optional[int] = None,
        include_quality_metrics: bool = True,
    ) -> Dict[str, Any]:
        """
        Search indexed code semantically across functions and classes.

        Args:
            query: Natural language description of what to find
            project_name: Optional project filter
            limit: Maximum results (default: 5)
            file_pattern: Optional path filter (e.g., "*/auth/*")
            language: Optional language filter
            search_mode: "semantic", "keyword", or "hybrid"
            min_complexity: Optional minimum complexity filter
            max_complexity: Optional maximum complexity filter
            has_duplicates: Optional duplicate filter
            long_functions: Optional long function filter
            maintainability_min: Optional minimum maintainability index
            include_quality_metrics: Include quality metrics in results

        Returns:
            Dict with results containing file_path, code snippets, relevance_score
        """
        try:
            start_time = time.time()

            if search_mode not in ["semantic", "keyword", "hybrid"]:
                raise ValidationError(f"Invalid search_mode: {search_mode}")

            if not query or not query.strip():
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
                    "suggestions": ["Provide a search query"],
                    "interpretation": "Empty query - no search performed",
                    "matched_keywords": [],
                }

            filter_project_name = project_name or self.project_name
            query_embedding = await self._get_embedding(query)

            filters = SearchFilters(
                scope=MemoryScope.PROJECT,
                project_name=filter_project_name,
                category=MemoryCategory.CODE,
                context_level=ContextLevel.PROJECT_CONTEXT,
                tags=["code"],
            )

            # Perform search based on mode
            if search_mode == "hybrid" and self.hybrid_searcher:
                retrieval_limit = max(limit * 3, 50)
                try:
                    async with asyncio.timeout(30.0):
                        vector_results = await self.store.retrieve(
                            query_embedding=query_embedding,
                            filters=filters,
                            limit=retrieval_limit,
                        )
                except TimeoutError:
                    logger.error("Hybrid search retrieve operation timed out after 30s")
                    raise RetrievalError("Code search retrieval operation timed out")

                documents = [memory.content for memory, _ in vector_results]
                memory_units = [memory for memory, _ in vector_results]
                self.hybrid_searcher.index_documents(documents, memory_units)

                hybrid_results = self.hybrid_searcher.hybrid_search(
                    query=query,
                    vector_results=vector_results,
                    limit=limit,
                )
                results = [(hr.memory, hr.total_score) for hr in hybrid_results]
            else:
                if search_mode == "hybrid":
                    logger.warning("Hybrid search not available, using semantic")

                try:
                    async with asyncio.timeout(30.0):
                        results = await self.store.retrieve(
                            query_embedding=query_embedding,
                            filters=filters,
                            limit=limit,
                        )
                except TimeoutError:
                    logger.error("Code search retrieve operation timed out after 30s")
                    raise RetrievalError("Code search retrieval operation timed out")

            # Format results
            code_results = []
            seen_units = set()

            for memory, score in results:
                metadata = memory.metadata or {}

                file_path = metadata.get("file_path", "")
                language_val = metadata.get("language", "")

                if file_pattern and file_pattern not in file_path:
                    continue
                if language and language_val.lower() != language.lower():
                    continue

                unit_name = metadata.get("unit_name") or metadata.get("name", "(unnamed)")
                start_line = metadata.get("start_line", 0)
                dedup_key = (file_path, start_line, unit_name)

                if dedup_key in seen_units:
                    continue
                seen_units.add(dedup_key)

                relevance_score = min(max(score, 0.0), 1.0)
                confidence_label = self._get_confidence_label(relevance_score)

                result_dict = {
                    "file_path": file_path or "(no path)",
                    "start_line": start_line,
                    "end_line": metadata.get("end_line", 0),
                    "unit_name": unit_name,
                    "unit_type": metadata.get("unit_type", "(unknown type)"),
                    "signature": metadata.get("signature", ""),
                    "language": language_val or "(unknown language)",
                    "code": memory.content,
                    "relevance_score": relevance_score,
                    "confidence_label": confidence_label,
                    "confidence_display": f"{relevance_score:.0%} ({confidence_label})",
                }

                # Calculate quality metrics if requested
                if include_quality_metrics and self.quality_analyzer and self.duplicate_detector:
                    code_unit = {
                        "content": memory.content,
                        "signature": metadata.get("signature", ""),
                        "unit_type": metadata.get("unit_type", "function"),
                        "language": language_val,
                    }

                    duplication_score = await self.duplicate_detector.calculate_duplication_score(memory)
                    quality_metrics = self.quality_analyzer.calculate_quality_metrics(
                        code_unit=code_unit,
                        duplication_score=duplication_score,
                    )

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

                    # Apply quality filters
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
            with self._stats_lock:
                self.stats["searches_performed"] += 1

            quality_info = self._analyze_search_quality(code_results, query, filter_project_name)

            actual_search_mode = search_mode
            if search_mode == "hybrid" and not self.hybrid_searcher:
                actual_search_mode = "semantic"

            if self.metrics_collector:
                avg_relevance = sum(r["relevance_score"] for r in code_results) / len(code_results) if code_results else 0.0
                self.metrics_collector.log_query(
                    query=query,
                    latency_ms=query_time_ms,
                    result_count=len(code_results),
                    avg_relevance=avg_relevance
                )

            logger.info(
                f"Code search: '{query}' found {len(code_results)} results "
                f"in {query_time_ms:.2f}ms (project: {filter_project_name})"
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
            raise
        except (ConnectionError, OSError) as e:
            logger.error(f"Network error during code search: {e}", exc_info=True)
            raise RetrievalError(
                f"Failed to connect to Qdrant: {str(e)}. "
                f"Please ensure Qdrant is running."
            )
        except Exception as e:
            logger.error(f"Failed to search code: {e}", exc_info=True)
            raise RetrievalError(f"Code search failed: {e}") from e

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

        Args:
            code_snippet: Code to find matches for
            project_name: Optional project filter
            limit: Maximum results (default: 10)
            file_pattern: Optional path filter
            language: Optional language filter

        Returns:
            Dict with similar code results and similarity scores
        """
        if not code_snippet or not code_snippet.strip():
            raise ValidationError("code_snippet cannot be empty")

        try:
            start_time = time.time()
            filter_project_name = project_name or self.project_name

            code_embedding = await self._get_embedding(code_snippet)

            filters = SearchFilters(
                scope=MemoryScope.PROJECT,
                project_name=filter_project_name,
                category=MemoryCategory.CODE,
                context_level=ContextLevel.PROJECT_CONTEXT,
                tags=["code"],
            )

            try:
                async with asyncio.timeout(30.0):
                    results = await self.store.retrieve(
                        query_embedding=code_embedding,
                        filters=filters,
                        limit=limit,
                    )
            except TimeoutError:
                logger.error("Find similar code retrieve operation timed out after 30s")
                raise RetrievalError("Find similar code retrieval operation timed out")

            code_results = []
            seen_units = set()

            for memory, score in results:
                metadata = memory.metadata or {}

                file_path = metadata.get("file_path", "")
                language_val = metadata.get("language", "")

                if file_pattern and file_pattern not in file_path:
                    continue
                if language and language_val.lower() != language.lower():
                    continue

                unit_name = metadata.get("unit_name") or metadata.get("name", "(unnamed)")
                start_line = metadata.get("start_line", 0)
                dedup_key = (file_path, start_line, unit_name)

                if dedup_key in seen_units:
                    continue
                seen_units.add(dedup_key)

                similarity_score = min(max(score, 0.0), 1.0)
                confidence_label = self._get_confidence_label(similarity_score)

                code_results.append({
                    "file_path": file_path or "(no path)",
                    "start_line": start_line,
                    "end_line": metadata.get("end_line", 0),
                    "unit_name": unit_name,
                    "unit_type": metadata.get("unit_type", "(unknown type)"),
                    "signature": metadata.get("signature", ""),
                    "language": language_val or "(unknown language)",
                    "code": memory.content,
                    "similarity_score": similarity_score,
                    "confidence_label": confidence_label,
                    "confidence_display": f"{similarity_score:.0%} ({confidence_label})",
                })

            query_time_ms = (time.time() - start_time) * 1000
            with self._stats_lock:
                self.stats["similar_code_searches"] += 1

            if self.metrics_collector:
                avg_relevance = sum(r["similarity_score"] for r in code_results) / len(code_results) if code_results else 0.0
                self.metrics_collector.log_query(
                    query=f"<code_similarity:{len(code_snippet)} chars>",
                    latency_ms=query_time_ms,
                    result_count=len(code_results),
                    avg_relevance=avg_relevance
                )

            # Generate interpretation
            if not code_results:
                interpretation = "No similar code found"
                suggestions = [
                    f"Verify code has been indexed for project '{filter_project_name or 'current'}'",
                    "Try indexing more code",
                ]
            elif code_results[0]["similarity_score"] >= 0.95:
                interpretation = f"Found {len(code_results)} very similar snippets (likely duplicates)"
                suggestions = ["Consider consolidating duplicate code"]
            elif code_results[0]["similarity_score"] >= 0.80:
                interpretation = f"Found {len(code_results)} similar code patterns"
                suggestions = ["Good candidates for refactoring or code reuse"]
            else:
                interpretation = f"Found {len(code_results)} somewhat related snippets"
                suggestions = ["These may share some concepts but differ significantly"]

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
            raise RetrievalError(f"Failed to find similar code: {e}") from e

    async def index_codebase(
        self,
        directory_path: str,
        project_name: Optional[str] = None,
        recursive: bool = True,
    ) -> Dict[str, Any]:
        """
        Index a codebase directory for semantic code search.

        Args:
            directory_path: Absolute path to directory to index
            project_name: Project name for scoping
            recursive: Recursively index subdirectories

        Returns:
            Dict with status, files_indexed, units_indexed, total_time_s
        """
        if self.config.advanced.read_only_mode:
            raise ReadOnlyError("Cannot index codebase in read-only mode")

        try:
            from src.memory.incremental_indexer import IncrementalIndexer

            start_time = time.time()
            dir_path = Path(directory_path).resolve()

            if not dir_path.exists():
                raise ValueError(f"Directory does not exist: {directory_path}")

            if not dir_path.is_dir():
                raise ValueError(f"Path is not a directory: {directory_path}")

            index_project_name = project_name or dir_path.name

            indexer = IncrementalIndexer(
                store=self.store,
                embedding_generator=self.embedding_generator,
                config=self.config,
                project_name=index_project_name,
            )

            await indexer.initialize()

            logger.info(f"Indexing codebase: {dir_path} (project: {index_project_name})")
            result = await indexer.index_directory(
                dir_path=dir_path,
                recursive=recursive,
                show_progress=True,
            )

            total_time_s = time.time() - start_time
            with self._stats_lock:
                self.stats["files_indexed"] += result["indexed_files"]
                self.stats["units_indexed"] += result["total_units"]

            logger.info(
                f"Indexed {result['total_units']} units from "
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
            raise StorageError(f"Failed to index codebase: {e}") from e

    async def reindex_project(
        self,
        project_name: str,
        directory_path: str,
        clear_existing: bool = False,
        bypass_cache: bool = False,
        recursive: bool = True,
        progress_callback: Optional[Callable[..., Any]] = None,
    ) -> Dict[str, Any]:
        """
        Force re-indexing of a project.

        Args:
            project_name: Project to reindex
            directory_path: Directory path to index
            clear_existing: Delete existing index first
            bypass_cache: Bypass embedding cache
            recursive: Recursively index subdirectories
            progress_callback: Optional callback for progress updates

        Returns:
            Dict with reindexing statistics
        """
        if self.config.advanced.read_only_mode:
            raise ReadOnlyError("Cannot reindex project in read-only mode")

        from src.memory.incremental_indexer import IncrementalIndexer

        dir_path = Path(directory_path).resolve()

        if not dir_path.exists():
            raise ValueError(f"Directory does not exist: {directory_path}")

        if not dir_path.is_dir():
            raise ValueError(f"Path is not a directory: {directory_path}")

        try:
            start_time = time.time()
            units_deleted = 0

            if clear_existing:
                logger.info(f"Clearing existing index for project: {project_name}")
                if hasattr(self.store, 'delete_code_units_by_project'):
                    try:
                        async with asyncio.timeout(30.0):
                            units_deleted = await self.store.delete_code_units_by_project(project_name)
                    except TimeoutError:
                        logger.error("Delete code units operation timed out after 30s")
                        raise StorageError("Delete code units operation timed out")
                    logger.info(f"Deleted {units_deleted} existing code units")

            if bypass_cache and self.embedding_cache:
                logger.info(f"Bypassing embedding cache for project: {project_name}")

            indexer = IncrementalIndexer(
                store=self.store,
                embedding_generator=self.embedding_generator,
                config=self.config,
                project_name=project_name,
            )

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
                f"Re-indexed {result['total_units']} units from "
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
            raise StorageError(f"Failed to reindex project: {e}") from e

    async def get_indexed_files(
        self,
        project_name: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """
        Get list of indexed files with metadata.

        Args:
            project_name: Filter by project name
            limit: Maximum number of files to return
            offset: Number of files to skip for pagination

        Returns:
            Dict with files list, total, and pagination info
        """
        try:
            try:
                async with asyncio.timeout(30.0):
                    result = await self.store.get_indexed_files(
                        project_name=project_name,
                        limit=limit,
                        offset=offset
                    )
            except TimeoutError:
                logger.error("Get indexed files operation timed out after 30s")
                raise StorageError("Get indexed files operation timed out")

            result["has_more"] = (result["offset"] + len(result["files"])) < result["total"]

            logger.info(
                f"Retrieved {len(result['files'])} indexed files "
                f"(total {result['total']}) for project '{project_name or 'all'}'"
            )

            return result

        except Exception as e:
            logger.error(f"Failed to get indexed files: {e}", exc_info=True)
            raise StorageError(f"Failed to get indexed files: {e}") from e

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

        Args:
            project_name: Filter by project name
            language: Filter by language
            file_pattern: Filter by file path pattern
            unit_type: Filter by unit type
            limit: Maximum number of units to return
            offset: Number of units to skip for pagination

        Returns:
            Dict with units list, total, and pagination info
        """
        try:
            try:
                async with asyncio.timeout(30.0):
                    result = await self.store.list_indexed_units(
                        project_name=project_name,
                        language=language,
                        file_pattern=file_pattern,
                        unit_type=unit_type,
                        limit=limit,
                        offset=offset
                    )
            except TimeoutError:
                logger.error("List indexed units operation timed out after 30s")
                raise StorageError("List indexed units operation timed out")

            result["has_more"] = (result["offset"] + len(result["units"])) < result["total"]

            logger.info(
                f"Retrieved {len(result['units'])} indexed units "
                f"(total {result['total']})"
            )

            return result

        except Exception as e:
            logger.error(f"Failed to list indexed units: {e}", exc_info=True)
            raise StorageError(f"Failed to list indexed units: {e}") from e

    async def _build_dependency_graph(
        self,
        project_name: Optional[str]
    ) -> Any:
        """Build dependency graph from stored metadata."""
        from src.memory.dependency_graph import DependencyGraph

        graph = DependencyGraph()

        filters = SearchFilters(
            project_name=project_name,
            category=MemoryCategory.CONTEXT,
            context_level=ContextLevel.PROJECT_CONTEXT,
            tags=["code"],
        )

        empty_embedding = [0.0] * DEFAULT_EMBEDDING_DIM
        try:
            async with asyncio.timeout(30.0):
                results = await self.store.retrieve(
                    query_embedding=empty_embedding,
                    filters=filters,
                    limit=10000,
                )
        except TimeoutError:
            logger.error("Build dependency graph retrieve operation timed out after 30s")
            raise RetrievalError("Build dependency graph retrieval operation timed out")

        file_imports: Dict[str, List[Dict[str, Any]]] = {}
        for memory, _ in results:
            metadata = memory.metadata
            file_path = metadata.get("file_path")
            imports = metadata.get("imports", [])

            if file_path and imports:
                if file_path not in file_imports:
                    file_imports[file_path] = imports

        for file_path, imports in file_imports.items():
            graph.add_file_dependencies(file_path, imports)

        return graph

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
            file_path = str(Path(file_path).resolve())
            filter_project_name = project_name or self.project_name

            graph = await self._build_dependency_graph(filter_project_name)

            if include_transitive:
                deps = graph.get_all_dependencies(file_path)
            else:
                deps = graph.get_dependencies(file_path)

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
            raise RetrievalError(f"Failed to get file dependencies: {e}") from e

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
            file_path = str(Path(file_path).resolve())
            filter_project_name = project_name or self.project_name

            graph = await self._build_dependency_graph(filter_project_name)

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
            raise RetrievalError(f"Failed to get file dependents: {e}") from e

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
            source_file = str(Path(source_file).resolve())
            target_file = str(Path(target_file).resolve())
            filter_project_name = project_name or self.project_name

            graph = await self._build_dependency_graph(filter_project_name)
            path = graph.find_path(source_file, target_file)

            if path:
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
            raise RetrievalError(f"Failed to find dependency path: {e}") from e

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
            filter_project_name = project_name or self.project_name
            graph = await self._build_dependency_graph(filter_project_name)

            stats = graph.get_statistics()
            cycles = graph.detect_circular_dependencies()

            return {
                "project": filter_project_name,
                "statistics": stats,
                "circular_dependencies": len(cycles),
                "circular_dependency_chains": cycles[:5],
            }

        except Exception as e:
            logger.error(f"Failed to get dependency stats: {e}", exc_info=True)
            raise RetrievalError(f"Failed to get dependency stats: {e}") from e
