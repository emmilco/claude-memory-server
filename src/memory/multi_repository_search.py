"""Multi-repository search for cross-repository code discovery.

This module provides enhanced search capabilities across multiple repositories,
building on the existing search infrastructure to support:
- Repository-scoped search
- Workspace-scoped search
- Cross-repository result aggregation
- Repository-aware ranking and filtering
- Dependency-aware search ordering
"""

import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

from src.config import ServerConfig, get_config
from src.core.models import SearchFilters, MemoryScope, MemoryCategory, ContextLevel
from src.store.qdrant_store import QdrantMemoryStore
from src.embeddings.generator import EmbeddingGenerator
from src.memory.repository_registry import RepositoryRegistry
from src.memory.workspace_manager import WorkspaceManager

logger = logging.getLogger(__name__)


@dataclass
class RepositorySearchResult:
    """Search result from a single repository.

    Attributes:
        repository_id: Repository identifier
        repository_name: Repository name
        results: List of (memory, score) tuples from this repository
        total_found: Total results found in this repository
    """

    repository_id: str
    repository_name: str
    results: List[tuple] = field(default_factory=list)
    total_found: int = 0


@dataclass
class MultiRepositorySearchResult:
    """Aggregated search results across multiple repositories.

    Attributes:
        query: Original search query
        repository_results: Results grouped by repository
        aggregated_results: All results merged and sorted by score
        total_repositories_searched: Number of repositories searched
        total_results_found: Total results across all repositories
        search_mode: Search mode used (semantic, keyword, hybrid)
        query_time_ms: Total search time in milliseconds
    """

    query: str
    repository_results: List[RepositorySearchResult]
    aggregated_results: List[tuple] = field(default_factory=list)
    total_repositories_searched: int = 0
    total_results_found: int = 0
    search_mode: str = "semantic"
    query_time_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "query": self.query,
            "total_repositories_searched": self.total_repositories_searched,
            "total_results_found": self.total_results_found,
            "search_mode": self.search_mode,
            "query_time_ms": self.query_time_ms,
            "repository_results": [
                {
                    "repository_id": rr.repository_id,
                    "repository_name": rr.repository_name,
                    "total_found": rr.total_found,
                    "results": [
                        {
                            "content": memory.content,
                            "score": score,
                            "metadata": memory.metadata,
                            "file_path": memory.metadata.get("file_path"),
                            "unit_type": memory.metadata.get("unit_type"),
                        }
                        for memory, score in rr.results
                    ],
                }
                for rr in self.repository_results
            ],
            "aggregated_results": [
                {
                    "content": memory.content,
                    "score": score,
                    "metadata": memory.metadata,
                    "repository_id": memory.metadata.get("project_name"),
                    "file_path": memory.metadata.get("file_path"),
                    "unit_type": memory.metadata.get("unit_type"),
                }
                for memory, score in self.aggregated_results
            ],
        }


class MultiRepositorySearch:
    """Enhanced search across multiple repositories.

    This class extends the single-project search capabilities to support
    querying across repository collections, with intelligent result
    aggregation and ranking.

    Features:
    - Repository-scoped search (search within specific repositories)
    - Workspace-scoped search (search all repos in a workspace)
    - Cross-repository aggregation
    - Repository-aware result ranking
    - Dependency-aware search ordering

    Usage:
        searcher = MultiRepositorySearch(registry, workspace_manager, store)
        await searcher.initialize()
        results = await searcher.search_repositories(
            query="authentication logic",
            repository_ids=["repo-1", "repo-2"]
        )
    """

    def __init__(
        self,
        repository_registry: RepositoryRegistry,
        workspace_manager: Optional[WorkspaceManager] = None,
        store: Optional[QdrantMemoryStore] = None,
        embedding_generator: Optional[EmbeddingGenerator] = None,
        config: Optional[ServerConfig] = None,
    ):
        """Initialize multi-repository search.

        Args:
            repository_registry: Registry for repository metadata
            workspace_manager: Optional workspace manager
            store: Vector store for search
            embedding_generator: Embedding generator for query encoding
            config: Server configuration
        """
        self.repository_registry = repository_registry
        self.workspace_manager = workspace_manager
        self.store = store
        self.embedding_generator = embedding_generator
        self.config = config or get_config()

        logger.info("MultiRepositorySearch initialized")

    async def initialize(self) -> None:
        """Initialize the search system."""
        # Initialize store if needed
        if self.store is None:
            self.store = QdrantMemoryStore(self.config)
        await self.store.initialize()

        # Initialize embedding generator if needed
        if self.embedding_generator is None:
            self.embedding_generator = EmbeddingGenerator(self.config)

        if hasattr(self.embedding_generator, "initialize"):
            await self.embedding_generator.initialize()

        logger.info("MultiRepositorySearch ready")

    async def close(self) -> None:
        """Clean up resources."""
        if self.embedding_generator and hasattr(self.embedding_generator, "close"):
            await self.embedding_generator.close()

        if self.store:
            await self.store.close()

        logger.info("MultiRepositorySearch closed")

    async def search_repository(
        self,
        query: str,
        repository_id: str,
        limit: int = 10,
        file_pattern: Optional[str] = None,
        language: Optional[str] = None,
        search_mode: str = "semantic",
    ) -> RepositorySearchResult:
        """Search within a single repository.

        Args:
            query: Search query
            repository_id: Repository to search
            limit: Maximum results to return
            file_pattern: Optional file path filter
            language: Optional language filter
            search_mode: Search mode (semantic, keyword, hybrid)

        Returns:
            RepositorySearchResult with search results

        Raises:
            ValueError: If repository not found
        """
        # Get repository
        repository = await self.repository_registry.get_repository(repository_id)
        if not repository:
            raise ValueError(f"Repository '{repository_id}' not found")

        # Generate query embedding
        query_embedding = await self.embedding_generator.generate(query)

        # Build filters for this repository
        filters = SearchFilters(
            scope=MemoryScope.PROJECT,
            project_name=repository_id,  # Use repo ID as project name
            category=MemoryCategory.CONTEXT,
            context_level=ContextLevel.PROJECT_CONTEXT,
            tags=["code"],
        )

        # TODO: Add file_pattern and language filtering when supported by store

        # Search in vector store
        results = await self.store.retrieve(
            query_embedding=query_embedding,
            filters=filters,
            limit=limit,
        )

        logger.debug(
            f"Found {len(results)} results in repository '{repository.name}' "
            f"({repository_id})"
        )

        return RepositorySearchResult(
            repository_id=repository_id,
            repository_name=repository.name,
            results=results,
            total_found=len(results),
        )

    async def search_repositories(
        self,
        query: str,
        repository_ids: List[str],
        limit_per_repo: int = 10,
        total_limit: Optional[int] = None,
        file_pattern: Optional[str] = None,
        language: Optional[str] = None,
        search_mode: str = "semantic",
        aggregate: bool = True,
    ) -> MultiRepositorySearchResult:
        """Search across multiple repositories.

        Args:
            query: Search query
            repository_ids: List of repository IDs to search
            limit_per_repo: Maximum results per repository
            total_limit: Optional total limit across all repos (for aggregated results)
            file_pattern: Optional file path filter
            language: Optional language filter
            search_mode: Search mode (semantic, keyword, hybrid)
            aggregate: Whether to aggregate and sort results across repos

        Returns:
            MultiRepositorySearchResult with results from all repositories
        """
        import time
        import asyncio

        start_time = time.time()

        logger.info(
            f"Searching {len(repository_ids)} repositories for: '{query}' "
            f"(mode: {search_mode})"
        )

        # Search all repositories in parallel
        search_tasks = [
            self.search_repository(
                query=query,
                repository_id=repo_id,
                limit=limit_per_repo,
                file_pattern=file_pattern,
                language=language,
                search_mode=search_mode,
            )
            for repo_id in repository_ids
        ]

        repository_results = await asyncio.gather(*search_tasks, return_exceptions=True)

        # Handle exceptions
        valid_results = []
        for i, result in enumerate(repository_results):
            if isinstance(result, Exception):
                logger.error(
                    f"Error searching repository {repository_ids[i]}: {result}"
                )
            else:
                valid_results.append(result)

        # Aggregate results if requested
        aggregated_results = []
        if aggregate and valid_results:
            # Combine all results
            all_results = []
            for repo_result in valid_results:
                all_results.extend(repo_result.results)

            # Sort by score (descending)
            all_results.sort(key=lambda x: x[1], reverse=True)

            # Apply total limit if specified
            if total_limit:
                aggregated_results = all_results[:total_limit]
            else:
                aggregated_results = all_results

        total_found = sum(rr.total_found for rr in valid_results)
        query_time_ms = (time.time() - start_time) * 1000

        logger.info(
            f"Multi-repository search complete: {total_found} results from "
            f"{len(valid_results)} repositories ({query_time_ms:.2f}ms)"
        )

        return MultiRepositorySearchResult(
            query=query,
            repository_results=valid_results,
            aggregated_results=aggregated_results,
            total_repositories_searched=len(valid_results),
            total_results_found=total_found,
            search_mode=search_mode,
            query_time_ms=query_time_ms,
        )

    async def search_workspace(
        self,
        query: str,
        workspace_id: str,
        limit_per_repo: int = 10,
        total_limit: Optional[int] = None,
        file_pattern: Optional[str] = None,
        language: Optional[str] = None,
        search_mode: str = "semantic",
    ) -> MultiRepositorySearchResult:
        """Search all repositories in a workspace.

        Args:
            query: Search query
            workspace_id: Workspace to search
            limit_per_repo: Maximum results per repository
            total_limit: Optional total limit across all repos
            file_pattern: Optional file path filter
            language: Optional language filter
            search_mode: Search mode (semantic, keyword, hybrid)

        Returns:
            MultiRepositorySearchResult with results from workspace

        Raises:
            ValueError: If workspace not found or workspace manager not configured
        """
        if not self.workspace_manager:
            raise ValueError("WorkspaceManager not configured")

        # Get workspace
        workspace = await self.workspace_manager.get_workspace(workspace_id)
        if not workspace:
            raise ValueError(f"Workspace '{workspace_id}' not found")

        # Check if cross-repo search is enabled for this workspace
        if not workspace.cross_repo_search_enabled:
            logger.warning(
                f"Cross-repo search disabled for workspace '{workspace.name}'"
            )
            return MultiRepositorySearchResult(
                query=query,
                repository_results=[],
                total_repositories_searched=0,
                total_results_found=0,
                search_mode=search_mode,
            )

        logger.info(
            f"Searching workspace '{workspace.name}' "
            f"({len(workspace.repository_ids)} repositories)"
        )

        # Search all repositories in workspace
        return await self.search_repositories(
            query=query,
            repository_ids=workspace.repository_ids,
            limit_per_repo=limit_per_repo,
            total_limit=total_limit,
            file_pattern=file_pattern,
            language=language,
            search_mode=search_mode,
        )

    async def search_with_dependencies(
        self,
        query: str,
        repository_id: str,
        include_dependencies: bool = True,
        max_depth: int = 2,
        limit_per_repo: int = 10,
        total_limit: Optional[int] = None,
        search_mode: str = "semantic",
    ) -> MultiRepositorySearchResult:
        """Search a repository and its dependencies.

        This is useful for finding code across a repository and the libraries/
        services it depends on.

        Args:
            query: Search query
            repository_id: Primary repository to search
            include_dependencies: Whether to search dependencies
            max_depth: Maximum dependency depth to search
            limit_per_repo: Maximum results per repository
            total_limit: Optional total limit across all repos
            search_mode: Search mode (semantic, keyword, hybrid)

        Returns:
            MultiRepositorySearchResult with results from repo and dependencies

        Raises:
            ValueError: If repository not found
        """
        # Get repository
        repository = await self.repository_registry.get_repository(repository_id)
        if not repository:
            raise ValueError(f"Repository '{repository_id}' not found")

        # Start with the primary repository
        repo_ids_to_search = [repository_id]

        # Add dependencies if requested
        if include_dependencies:
            dependencies = await self.repository_registry.get_dependencies(
                repository_id, max_depth=max_depth
            )

            # Flatten dependency tree into list of repo IDs
            dep_ids = set()
            for level_deps in dependencies.values():
                dep_ids.update(level_deps)

            repo_ids_to_search.extend(list(dep_ids))

            logger.info(
                f"Searching repository '{repository.name}' with "
                f"{len(dep_ids)} dependencies (depth: {max_depth})"
            )

        # Search all repositories
        return await self.search_repositories(
            query=query,
            repository_ids=repo_ids_to_search,
            limit_per_repo=limit_per_repo,
            total_limit=total_limit,
            search_mode=search_mode,
        )

    async def get_search_scope_repositories(
        self,
        workspace_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
        include_stale: bool = False,
    ) -> List[str]:
        """Get list of repository IDs that match search scope criteria.

        This is a utility method for building repository lists based on
        various criteria.

        Args:
            workspace_id: Optional workspace to filter by
            tags: Optional tags to filter by
            include_stale: Whether to include repositories with STALE status

        Returns:
            List of repository IDs matching criteria
        """
        from src.memory.repository_registry import RepositoryStatus

        # Get repositories from workspace if specified
        if workspace_id:
            if not self.workspace_manager:
                raise ValueError("WorkspaceManager not configured")

            workspace = await self.workspace_manager.get_workspace(workspace_id)
            if not workspace:
                raise ValueError(f"Workspace '{workspace_id}' not found")

            # Start with workspace repositories
            candidate_repos = []
            for repo_id in workspace.repository_ids:
                repo = await self.repository_registry.get_repository(repo_id)
                if repo:
                    candidate_repos.append(repo)
        else:
            # Get all repositories
            candidate_repos = await self.repository_registry.list_repositories(
                tags=tags
            )

        # Filter by status
        if not include_stale:
            candidate_repos = [
                repo
                for repo in candidate_repos
                if repo.status == RepositoryStatus.INDEXED
            ]

        return [repo.id for repo in candidate_repos]


class MultiRepositorySearcher:
    """Simplified searcher for cross-project service integration.

    This class provides a simpler interface for searching within individual
    projects, designed for use by CrossProjectService.

    Unlike MultiRepositorySearch which requires a RepositoryRegistry,
    this class works directly with project names and the vector store.
    """

    def __init__(
        self,
        store: QdrantMemoryStore,
        embedding_generator: EmbeddingGenerator,
        config: Optional[ServerConfig] = None,
    ):
        """Initialize the searcher.

        Args:
            store: Vector store for search operations
            embedding_generator: Embedding generator for queries
            config: Server configuration
        """
        self.store = store
        self.embedding_generator = embedding_generator
        self.config = config or get_config()

    async def search_project(
        self,
        query: str,
        query_embedding: List[float],
        project_name: str,
        limit: int = 10,
        search_mode: str = "semantic",
    ) -> List[Dict[str, Any]]:
        """Search within a specific project.

        Args:
            query: Search query text
            query_embedding: Pre-computed query embedding
            project_name: Project name to search within
            limit: Maximum results to return
            search_mode: Search mode (semantic, keyword, hybrid)

        Returns:
            List of search results with file_path, relevance_score, etc.
        """
        # Build filters for project-scoped search
        filters = SearchFilters(
            project=project_name,
            scope=MemoryScope.PROJECT,
        )

        # Perform search using store
        results = await self.store.search(
            query_embedding=query_embedding,
            limit=limit,
            filters=filters,
        )

        # Convert to expected format
        formatted_results = []
        for memory, score in results:
            formatted_results.append(
                {
                    "content": memory.content,
                    "file_path": memory.metadata.get("file_path", ""),
                    "language": memory.metadata.get("language", ""),
                    "unit_type": memory.metadata.get("unit_type", ""),
                    "relevance_score": score,
                    "metadata": memory.metadata,
                }
            )

        return formatted_results
