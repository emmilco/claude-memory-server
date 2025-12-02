"""Multi-repository indexer for batch operations across repository collections.

This module provides high-level orchestration for indexing multiple repositories,
either individually or grouped by workspace. It builds on IncrementalIndexer to
provide:
- Batch indexing of multiple repositories
- Workspace-scoped indexing
- Parallel repository processing
- Progress tracking across repositories
- Error handling and recovery
- Repository status updates
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, UTC
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable

from src.config import ServerConfig, get_config
from src.memory.incremental_indexer import IncrementalIndexer
from src.memory.repository_registry import (
    RepositoryRegistry,
    Repository,
    RepositoryStatus,
)
from src.memory.workspace_manager import WorkspaceManager
from src.store.qdrant_store import QdrantMemoryStore
from src.embeddings.generator import EmbeddingGenerator
from src.embeddings.parallel_generator import ParallelEmbeddingGenerator

logger = logging.getLogger(__name__)


@dataclass
class RepositoryIndexResult:
    """Result of indexing a single repository.

    Attributes:
        repository_id: Repository identifier
        success: Whether indexing succeeded
        files_indexed: Number of files indexed
        units_indexed: Number of semantic units indexed
        errors: List of error messages encountered
        duration_seconds: Time taken to index
        error_message: Main error message if failed
    """

    repository_id: str
    success: bool
    files_indexed: int = 0
    units_indexed: int = 0
    errors: List[str] = field(default_factory=list)
    duration_seconds: float = 0.0
    error_message: Optional[str] = None


@dataclass
class BatchIndexResult:
    """Result of batch indexing operation.

    Attributes:
        total_repositories: Total repositories attempted
        successful: Number successfully indexed
        failed: Number that failed
        repository_results: Individual results per repository
        total_files: Total files indexed across all repos
        total_units: Total units indexed across all repos
        total_duration: Total time taken
    """

    total_repositories: int
    successful: int
    failed: int
    repository_results: List[RepositoryIndexResult]
    total_files: int = 0
    total_units: int = 0
    total_duration: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "total_repositories": self.total_repositories,
            "successful": self.successful,
            "failed": self.failed,
            "total_files": self.total_files,
            "total_units": self.total_units,
            "total_duration": self.total_duration,
            "repository_results": [
                {
                    "repository_id": r.repository_id,
                    "success": r.success,
                    "files_indexed": r.files_indexed,
                    "units_indexed": r.units_indexed,
                    "errors": r.errors,
                    "duration_seconds": r.duration_seconds,
                    "error_message": r.error_message,
                }
                for r in self.repository_results
            ],
        }


class MultiRepositoryIndexer:
    """Orchestrates indexing operations across multiple repositories.

    This class provides high-level batch operations for indexing code across
    repository collections. It coordinates with RepositoryRegistry and
    WorkspaceManager to organize indexing tasks and update metadata.

    Features:
    - Batch index multiple repositories in parallel
    - Workspace-scoped indexing (index all repos in a workspace)
    - Progress tracking with callbacks
    - Automatic repository status updates
    - Error handling and recovery
    - Dependency-aware indexing order

    Usage:
        indexer = MultiRepositoryIndexer(registry, workspace_manager)
        await indexer.initialize()
        result = await indexer.index_repositories(["repo-1", "repo-2"])
    """

    def __init__(
        self,
        repository_registry: RepositoryRegistry,
        workspace_manager: Optional[WorkspaceManager] = None,
        store: Optional[QdrantMemoryStore] = None,
        embedding_generator: Optional[EmbeddingGenerator] = None,
        config: Optional[ServerConfig] = None,
        max_concurrent_repos: int = 3,
    ):
        """Initialize multi-repository indexer.

        Args:
            repository_registry: Registry for repository metadata
            workspace_manager: Optional workspace manager for workspace operations
            store: Vector store (shared across all indexers)
            embedding_generator: Embedding generator (shared across all indexers)
            config: Server configuration
            max_concurrent_repos: Maximum concurrent repository indexing tasks
        """
        self.repository_registry = repository_registry
        self.workspace_manager = workspace_manager
        self.store = store
        self.embedding_generator = embedding_generator
        self.config = config or get_config()
        self.max_concurrent_repos = max_concurrent_repos

        # Cache for IncrementalIndexer instances (one per repository)
        self._indexer_cache: Dict[str, IncrementalIndexer] = {}

        logger.info(
            f"MultiRepositoryIndexer initialized "
            f"(max_concurrent: {max_concurrent_repos})"
        )

    async def initialize(self) -> None:
        """Initialize the multi-repository indexer.

        This sets up shared resources (store, embedding generator) that will
        be reused across all repository indexers.
        """
        # Initialize store if needed
        if self.store is None:
            self.store = QdrantMemoryStore(self.config)
        await self.store.initialize()

        # Initialize embedding generator if needed
        if self.embedding_generator is None:
            if self.config.performance.parallel_embeddings:
                logger.info("Using parallel embedding generator")
                self.embedding_generator = ParallelEmbeddingGenerator(self.config)
            else:
                self.embedding_generator = EmbeddingGenerator(self.config)

        if hasattr(self.embedding_generator, "initialize"):
            await self.embedding_generator.initialize()

        logger.info("MultiRepositoryIndexer ready")

    async def close(self) -> None:
        """Clean up resources."""
        # Close all cached indexers
        for indexer in self._indexer_cache.values():
            await indexer.close()
        self._indexer_cache.clear()

        # Close shared resources
        if self.embedding_generator and hasattr(self.embedding_generator, "close"):
            await self.embedding_generator.close()

        if self.store:
            await self.store.close()

        logger.info("MultiRepositoryIndexer closed")

    def _get_indexer(self, repository: Repository) -> IncrementalIndexer:
        """Get or create IncrementalIndexer for a repository.

        Args:
            repository: Repository to get indexer for

        Returns:
            IncrementalIndexer instance
        """
        # Check cache
        if repository.id in self._indexer_cache:
            return self._indexer_cache[repository.id]

        # Create new indexer
        indexer = IncrementalIndexer(
            store=self.store,
            embedding_generator=self.embedding_generator,
            config=self.config,
            project_name=repository.id,  # Use repo ID as project name
        )

        # Cache it
        self._indexer_cache[repository.id] = indexer

        return indexer

    async def index_repository(
        self,
        repository_id: str,
        recursive: bool = True,
        show_progress: bool = True,
        progress_callback: Optional[Callable] = None,
    ) -> RepositoryIndexResult:
        """Index a single repository.

        Args:
            repository_id: Repository to index
            recursive: Recursively index subdirectories
            show_progress: Show progress logging
            progress_callback: Optional callback for progress updates

        Returns:
            RepositoryIndexResult with indexing statistics

        Raises:
            ValueError: If repository not found
        """
        import time

        start_time = time.time()

        # Get repository
        repository = await self.repository_registry.get_repository(repository_id)
        if not repository:
            raise ValueError(f"Repository '{repository_id}' not found")

        # Validate repository path exists
        repo_path = Path(repository.path)
        if not repo_path.exists():
            error_msg = f"Repository path does not exist: {repository.path}"
            logger.error(error_msg)

            # Update status to ERROR
            await self.repository_registry.update_repository(
                repository_id, {"status": RepositoryStatus.ERROR}
            )

            return RepositoryIndexResult(
                repository_id=repository_id,
                success=False,
                error_message=error_msg,
                errors=[error_msg],
                duration_seconds=time.time() - start_time,
            )

        # Update status to INDEXING
        await self.repository_registry.update_repository(
            repository_id, {"status": RepositoryStatus.INDEXING}
        )

        try:
            logger.info(f"Indexing repository '{repository.name}' ({repository_id})")

            # Get indexer for this repository
            indexer = self._get_indexer(repository)

            # Ensure indexer is initialized
            if indexer not in self._indexer_cache.values():
                await indexer.initialize()

            # Index the repository directory
            index_result = await indexer.index_directory(
                repo_path,
                recursive=recursive,
                show_progress=show_progress,
                progress_callback=progress_callback,
            )

            # Update repository metadata
            updates = {
                "status": RepositoryStatus.INDEXED,
                "indexed_at": datetime.now(UTC),
                "last_updated": datetime.now(UTC),
                "file_count": index_result.get("total_files", 0),
                "unit_count": index_result.get("total_units", 0),
            }
            await self.repository_registry.update_repository(repository_id, updates)

            duration = time.time() - start_time

            logger.info(
                f"Successfully indexed '{repository.name}': "
                f"{index_result['total_files']} files, "
                f"{index_result['total_units']} units "
                f"({duration:.2f}s)"
            )

            return RepositoryIndexResult(
                repository_id=repository_id,
                success=True,
                files_indexed=index_result.get("total_files", 0),
                units_indexed=index_result.get("total_units", 0),
                duration_seconds=duration,
            )

        except Exception as e:
            error_msg = f"Failed to index repository '{repository.name}': {e}"
            logger.error(error_msg, exc_info=True)

            # Update status to ERROR
            await self.repository_registry.update_repository(
                repository_id, {"status": RepositoryStatus.ERROR}
            )

            return RepositoryIndexResult(
                repository_id=repository_id,
                success=False,
                error_message=str(e),
                errors=[error_msg],
                duration_seconds=time.time() - start_time,
            )

    async def index_repositories(
        self,
        repository_ids: List[str],
        recursive: bool = True,
        show_progress: bool = True,
        progress_callback: Optional[Callable] = None,
    ) -> BatchIndexResult:
        """Index multiple repositories in parallel.

        Args:
            repository_ids: List of repository IDs to index
            recursive: Recursively index subdirectories
            show_progress: Show progress logging
            progress_callback: Optional callback for progress updates

        Returns:
            BatchIndexResult with aggregated statistics
        """
        import time

        start_time = time.time()

        logger.info(f"Starting batch indexing of {len(repository_ids)} repositories")

        # Create semaphore for concurrency control
        semaphore = asyncio.Semaphore(self.max_concurrent_repos)

        async def index_with_semaphore(repo_id: str) -> RepositoryIndexResult:
            async with semaphore:
                return await self.index_repository(
                    repo_id,
                    recursive=recursive,
                    show_progress=show_progress,
                    progress_callback=progress_callback,
                )

        # Index all repositories in parallel (with concurrency limit)
        results = await asyncio.gather(
            *[index_with_semaphore(repo_id) for repo_id in repository_ids],
            return_exceptions=True,
        )

        # Handle exceptions from gather
        repository_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Exception indexing repository: {result}")
                repository_results.append(
                    RepositoryIndexResult(
                        repository_id=repository_ids[i],
                        success=False,
                        error_message=str(result),
                        errors=[str(result)],
                    )
                )
            else:
                repository_results.append(result)

        # Aggregate results
        successful = sum(1 for r in repository_results if r.success)
        failed = len(repository_results) - successful
        total_files = sum(r.files_indexed for r in repository_results)
        total_units = sum(r.units_indexed for r in repository_results)
        total_duration = time.time() - start_time

        batch_result = BatchIndexResult(
            total_repositories=len(repository_ids),
            successful=successful,
            failed=failed,
            repository_results=repository_results,
            total_files=total_files,
            total_units=total_units,
            total_duration=total_duration,
        )

        logger.info(
            f"Batch indexing complete: {successful}/{len(repository_ids)} successful, "
            f"{total_files} files, {total_units} units ({total_duration:.2f}s)"
        )

        return batch_result

    async def index_workspace(
        self,
        workspace_id: str,
        recursive: bool = True,
        show_progress: bool = True,
        progress_callback: Optional[Callable] = None,
    ) -> BatchIndexResult:
        """Index all repositories in a workspace.

        Args:
            workspace_id: Workspace to index
            recursive: Recursively index subdirectories
            show_progress: Show progress logging
            progress_callback: Optional callback for progress updates

        Returns:
            BatchIndexResult with aggregated statistics

        Raises:
            ValueError: If workspace not found or workspace manager not configured
        """
        if not self.workspace_manager:
            raise ValueError("WorkspaceManager not configured")

        # Get workspace
        workspace = await self.workspace_manager.get_workspace(workspace_id)
        if not workspace:
            raise ValueError(f"Workspace '{workspace_id}' not found")

        logger.info(
            f"Indexing workspace '{workspace.name}' "
            f"({len(workspace.repository_ids)} repositories)"
        )

        # Index all repositories in workspace
        return await self.index_repositories(
            workspace.repository_ids,
            recursive=recursive,
            show_progress=show_progress,
            progress_callback=progress_callback,
        )

    async def reindex_stale_repositories(
        self,
        max_age_days: int = 7,
        recursive: bool = True,
        show_progress: bool = True,
    ) -> BatchIndexResult:
        """Re-index repositories that haven't been updated recently.

        Args:
            max_age_days: Consider repos stale if not indexed in this many days
            recursive: Recursively index subdirectories
            show_progress: Show progress logging

        Returns:
            BatchIndexResult with aggregated statistics
        """
        from datetime import timedelta

        # Get all repositories with STALE or ERROR status
        stale_repos = await self.repository_registry.list_repositories(
            status=RepositoryStatus.STALE
        )
        error_repos = await self.repository_registry.list_repositories(
            status=RepositoryStatus.ERROR
        )

        # Also check for old INDEXED repos
        all_repos = await self.repository_registry.list_repositories()
        cutoff_date = datetime.now(UTC) - timedelta(days=max_age_days)

        old_repos = [
            repo
            for repo in all_repos
            if repo.status == RepositoryStatus.INDEXED
            and repo.last_updated
            and repo.last_updated < cutoff_date
        ]

        # Combine all stale repositories (use set of IDs to deduplicate)
        stale_repo_ids = {repo.id for repo in stale_repos}
        error_repo_ids = {repo.id for repo in error_repos}
        old_repo_ids = {repo.id for repo in old_repos}

        repo_ids = list(stale_repo_ids | error_repo_ids | old_repo_ids)

        logger.info(
            f"Re-indexing {len(repo_ids)} stale repositories "
            f"(>{max_age_days} days old or status != INDEXED)"
        )

        if not repo_ids:
            return BatchIndexResult(
                total_repositories=0,
                successful=0,
                failed=0,
                repository_results=[],
            )

        return await self.index_repositories(
            repo_ids,
            recursive=recursive,
            show_progress=show_progress,
        )

    async def get_indexing_status(self) -> Dict[str, Any]:
        """Get overall indexing status across all repositories.

        Returns:
            Dictionary with indexing statistics
        """
        all_repos = await self.repository_registry.list_repositories()

        status_counts = {
            RepositoryStatus.INDEXED: 0,
            RepositoryStatus.INDEXING: 0,
            RepositoryStatus.STALE: 0,
            RepositoryStatus.ERROR: 0,
            RepositoryStatus.NOT_INDEXED: 0,
        }

        for repo in all_repos:
            status_counts[repo.status] += 1

        total_files = sum(repo.file_count for repo in all_repos)
        total_units = sum(repo.unit_count for repo in all_repos)

        return {
            "total_repositories": len(all_repos),
            "status_counts": {
                status.value: count for status, count in status_counts.items()
            },
            "total_files_indexed": total_files,
            "total_units_indexed": total_units,
            "indexer_cache_size": len(self._indexer_cache),
        }
