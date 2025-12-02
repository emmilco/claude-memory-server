"""Cross-Project Service - Multi-project search and consent management.

Extracted from MemoryRAGServer (REF-016) to provide focused cross-project operations.

Responsibilities:
- Search across multiple projects
- Manage cross-project consent
- Track opted-in projects
"""

import threading
import time
from typing import Optional, Dict, Any

from src.config import ServerConfig
from src.store import MemoryStore
from src.embeddings.generator import EmbeddingGenerator
from src.core.exceptions import RetrievalError
from src.core.tracing import get_logger

logger = get_logger(__name__)


class CrossProjectService:
    """
    Service for multi-repository search and consent management.

    This service enables searching across multiple projects while
    respecting privacy through explicit opt-in consent.
    """

    def __init__(
        self,
        store: MemoryStore,
        embedding_generator: EmbeddingGenerator,
        config: ServerConfig,
        cross_project_consent: Optional[Any] = None,
        metrics_collector: Optional[Any] = None,
    ):
        """
        Initialize the Cross-Project Service.

        Args:
            store: Memory store backend
            embedding_generator: Embedding generator for semantic search
            config: Server configuration
            cross_project_consent: Cross-project consent manager
            metrics_collector: Optional metrics collector for monitoring
        """
        self.store = store
        self.embedding_generator = embedding_generator
        self.config = config
        self.consent = cross_project_consent
        self.metrics_collector = metrics_collector

        # Service statistics
        self.stats = {
            "cross_project_searches": 0,
            "projects_opted_in": 0,
            "projects_opted_out": 0,
        }
        self._stats_lock = threading.Lock()

    def get_stats(self) -> Dict[str, Any]:
        """Get cross-project service statistics."""
        with self._stats_lock:
            return self.stats.copy()

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

        Args:
            query: Natural language search query
            limit: Maximum total results across all projects
            file_pattern: Optional path filter
            language: Optional language filter
            search_mode: "semantic", "keyword", or "hybrid"

        Returns:
            Dict with results grouped by project
        """
        if not self.consent:
            return {
                "error": "Cross-project consent manager not configured",
                "status": "disabled",
            }

        try:
            start_time = time.time()

            # Get opted-in projects
            opted_in = self.consent.get_opted_in_projects()

            if not opted_in:
                return {
                    "results": [],
                    "total_found": 0,
                    "projects_searched": [],
                    "query": query,
                    "message": "No projects have opted in for cross-project search",
                }

            # Search each opted-in project
            from src.memory.multi_repository_search import MultiRepositorySearcher

            searcher = MultiRepositorySearcher(
                store=self.store,
                embedding_generator=self.embedding_generator,
                config=self.config,
            )

            all_results = []
            projects_searched = []
            failed_projects = []

            for project in opted_in:
                try:
                    query_embedding = await self.embedding_generator.generate(query)

                    project_results = await searcher.search_project(
                        query=query,
                        query_embedding=query_embedding,
                        project_name=project,
                        limit=limit,
                        search_mode=search_mode,
                    )

                    # Filter by file pattern and language if specified
                    if file_pattern or language:
                        filtered = []
                        for result in project_results:
                            file_path = result.get("file_path", "")
                            lang = result.get("language", "")

                            if file_pattern and file_pattern not in file_path:
                                continue
                            if language and lang.lower() != language.lower():
                                continue
                            filtered.append(result)
                        project_results = filtered

                    for result in project_results:
                        result["project_name"] = project

                    all_results.extend(project_results)
                    projects_searched.append(project)

                except Exception as e:
                    logger.error(
                        f"Failed to search project {project}: {e}", exc_info=True
                    )
                    failed_projects.append({"project": project, "error": str(e)})
                    continue

            # Sort by relevance and limit
            all_results.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)
            all_results = all_results[:limit]

            query_time_ms = (time.time() - start_time) * 1000
            with self._stats_lock:
                self.stats["cross_project_searches"] += 1

            if self.metrics_collector:
                avg_relevance = (
                    sum(r.get("relevance_score", 0) for r in all_results)
                    / len(all_results)
                    if all_results
                    else 0.0
                )
                self.metrics_collector.log_query(
                    query=query,
                    latency_ms=query_time_ms,
                    result_count=len(all_results),
                    avg_relevance=avg_relevance,
                )

            logger.info(
                f"Cross-project search: '{query}' found {len(all_results)} results "
                f"across {len(projects_searched)} projects in {query_time_ms:.2f}ms"
            )

            response = {
                "results": all_results,
                "total_found": len(all_results),
                "projects_searched": projects_searched,
                "query": query,
                "search_mode": search_mode,
                "query_time_ms": query_time_ms,
            }

            if failed_projects:
                response["failed_projects"] = failed_projects
                logger.warning(
                    f"Cross-project search had {len(failed_projects)} project failures"
                )

            return response

        except Exception as e:
            logger.error(f"Failed to search all projects: {e}", exc_info=True)
            raise RetrievalError(f"Failed to search all projects: {e}")

    async def opt_in_cross_project(self, project_name: str) -> Dict[str, Any]:
        """
        Enable project for cross-project search.

        Args:
            project_name: Project to opt in

        Returns:
            Dict with status
        """
        if not self.consent:
            return {
                "error": "Cross-project consent manager not configured",
                "status": "disabled",
            }

        try:
            self.consent.opt_in(project_name)
            with self._stats_lock:
                self.stats["projects_opted_in"] += 1

            logger.info(f"Project {project_name} opted in for cross-project search")

            return {
                "status": "success",
                "project_name": project_name,
                "action": "opted_in",
            }

        except Exception as e:
            logger.error(f"Failed to opt in project: {e}", exc_info=True)
            raise RetrievalError(f"Failed to opt in project: {e}")

    async def opt_out_cross_project(self, project_name: str) -> Dict[str, Any]:
        """
        Disable project from cross-project search.

        Args:
            project_name: Project to opt out

        Returns:
            Dict with status
        """
        if not self.consent:
            return {
                "error": "Cross-project consent manager not configured",
                "status": "disabled",
            }

        try:
            self.consent.opt_out(project_name)
            with self._stats_lock:
                self.stats["projects_opted_out"] += 1

            logger.info(f"Project {project_name} opted out of cross-project search")

            return {
                "status": "success",
                "project_name": project_name,
                "action": "opted_out",
            }

        except Exception as e:
            logger.error(f"Failed to opt out project: {e}", exc_info=True)
            raise RetrievalError(f"Failed to opt out project: {e}")

    async def list_opted_in_projects(self) -> Dict[str, Any]:
        """
        List all projects opted in for cross-project search.

        Returns:
            Dict with opted-in and opted-out projects
        """
        if not self.consent:
            return {
                "error": "Cross-project consent manager not configured",
                "status": "disabled",
            }

        try:
            opted_in = self.consent.get_opted_in_projects()
            opted_out = self.consent.get_opted_out_projects()
            stats = self.consent.get_statistics()

            logger.info(f"Retrieved {len(opted_in)} opted-in projects")

            return {
                "opted_in_projects": opted_in,
                "opted_out_projects": opted_out,
                "statistics": stats,
            }

        except Exception as e:
            logger.error(f"Failed to list opted-in projects: {e}", exc_info=True)
            raise RetrievalError(f"Failed to list opted-in projects: {e}")
