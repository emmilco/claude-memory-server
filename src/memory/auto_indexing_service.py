"""Auto-indexing service that orchestrates initial indexing and file watching."""

import asyncio
import logging
from pathlib import Path
from typing import Optional, Callable, Dict, Any, List
from datetime import datetime, UTC

try:
    import pathspec
    PATHSPEC_AVAILABLE = True
except ImportError:
    PATHSPEC_AVAILABLE = False
    logging.warning("pathspec not available - exclude patterns will not work")

from src.config import ServerConfig, get_config
from src.memory.incremental_indexer import IncrementalIndexer
from src.memory.indexing_service import IndexingService
from src.memory.project_index_tracker import ProjectIndexTracker
from src.core.exceptions import IndexingError

logger = logging.getLogger(__name__)


class IndexingProgress:
    """Tracks indexing progress for status queries."""

    def __init__(self):
        """Initialize progress tracker."""
        self.status: str = "idle"  # idle, counting, indexing, complete, error
        self.current_file: Optional[str] = None
        self.files_completed: int = 0
        self.total_files: int = 0
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None
        self.error_message: Optional[str] = None
        self.is_background: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert progress to dictionary."""
        data = {
            "status": self.status,
            "current_file": self.current_file,
            "files_completed": self.files_completed,
            "total_files": self.total_files,
            "is_background": self.is_background,
        }

        if self.start_time:
            data["start_time"] = self.start_time.isoformat()

        if self.end_time:
            data["end_time"] = self.end_time.isoformat()
            if self.start_time:
                elapsed = (self.end_time - self.start_time).total_seconds()
                data["elapsed_seconds"] = elapsed

        if self.error_message:
            data["error_message"] = self.error_message

        # Calculate ETA if indexing
        if self.status == "indexing" and self.files_completed > 0 and self.start_time:
            elapsed = (datetime.now(UTC) - self.start_time).total_seconds()
            rate = self.files_completed / elapsed if elapsed > 0 else 0
            remaining = self.total_files - self.files_completed
            if rate > 0:
                eta_seconds = remaining / rate
                data["eta_seconds"] = eta_seconds

        return data


class AutoIndexingService:
    """
    Service that automatically indexes projects on startup and manages file watching.

    Combines initial indexing with ongoing file monitoring for a seamless
    developer experience.
    """

    def __init__(
        self,
        project_path: Path,
        project_name: str,
        config: Optional[ServerConfig] = None,
    ):
        """
        Initialize auto-indexing service.

        Args:
            project_path: Path to project directory
            project_name: Name of the project
            config: Server configuration (uses global if None)
        """
        if config is None:
            config = get_config()

        self.config = config
        self.project_path = project_path
        self.project_name = project_name

        # Components
        self.tracker = ProjectIndexTracker(config=config)
        self.indexer: Optional[IncrementalIndexer] = None
        self.indexing_service: Optional[IndexingService] = None

        # State
        self.progress = IndexingProgress()
        self.indexing_task: Optional[asyncio.Task] = None
        self.is_initialized = False

        # Exclude pattern matching
        self.exclude_spec: Optional[Any] = None
        if PATHSPEC_AVAILABLE and hasattr(config, 'auto_index_exclude_patterns'):
            try:
                self.exclude_spec = pathspec.PathSpec.from_lines(
                    'gitwildmatch',
                    config.auto_index_exclude_patterns
                )
            except Exception as e:
                logger.warning(f"Failed to compile exclude patterns: {e}")

        logger.info(f"AutoIndexingService created for project: {project_name}")

    async def initialize(self) -> None:
        """Initialize the service and its components."""
        try:
            await self.tracker.initialize()
            self.indexer = IncrementalIndexer(project_name=self.project_name)
            await self.indexer.initialize()
            self.is_initialized = True
            logger.info(f"AutoIndexingService initialized for {self.project_name}")

        except Exception as e:
            raise IndexingError(
                f"Failed to initialize auto-indexing service: {e}",
                solution="Check storage backend connection and configuration. "
                        "Ensure database is accessible.",
                docs_url="https://docs.claude-memory.com/auto-indexing"
            ) from e

    async def should_auto_index(self) -> bool:
        """
        Determine if auto-indexing should run.

        Returns:
            True if project should be auto-indexed
        """
        if not self.is_initialized:
            raise IndexingError("Service not initialized. Call initialize() first.")

        # Check if auto-indexing is enabled
        if not self.config.indexing.auto_index_enabled:
            logger.info("Auto-indexing disabled in configuration")
            return False

        # Check if project has been indexed before
        is_indexed = await self.tracker.is_indexed(self.project_name)

        if not is_indexed:
            logger.info(f"Project {self.project_name} not indexed - will auto-index")
            return True

        # Check if index is stale
        is_stale = await self.tracker.is_stale(self.project_name, self.project_path)

        if is_stale:
            logger.info(f"Project {self.project_name} index is stale - will re-index")
            return True

        logger.info(f"Project {self.project_name} is up-to-date - skipping auto-index")
        return False

    def should_index_file(self, file_path: Path) -> bool:
        """
        Check if a file should be indexed based on exclude patterns.

        Args:
            file_path: Path to the file

        Returns:
            True if file should be indexed
        """
        if not self.exclude_spec:
            return True

        try:
            # Get relative path from project root
            rel_path = file_path.relative_to(self.project_path)
            return not self.exclude_spec.match_file(str(rel_path))
        except ValueError:
            # File not under project path
            return True

    async def _count_indexable_files(self) -> int:
        """
        Count files that would be indexed.

        Returns:
            Number of indexable files
        """
        count = 0
        supported_extensions = {'.py', '.js', '.jsx', '.ts', '.tsx', '.java', '.go', '.rs'}

        for file_path in self.project_path.rglob('*'):
            if not file_path.is_file():
                continue

            if file_path.suffix.lower() not in supported_extensions:
                continue

            if not self.should_index_file(file_path):
                continue

            count += 1

        return count

    async def _index_in_foreground(
        self,
        progress_callback: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """
        Index project in foreground (blocking).

        Args:
            progress_callback: Optional callback for progress updates

        Returns:
            Indexing result dictionary
        """
        self.progress.status = "indexing"
        self.progress.is_background = False
        self.progress.start_time = datetime.now(UTC)

        logger.info(f"Starting foreground indexing for {self.project_name}")

        try:
            # Index directory
            result = await self.indexer.index_directory(
                self.project_path,
                recursive=self.config.indexing.auto_index_recursive,
                show_progress=False,
                progress_callback=progress_callback,
            )

            # Update tracker metadata
            await self.tracker.update_metadata(
                project_name=self.project_name,
                total_files=result['indexed_files'],
                total_units=result['total_units'],
                is_watching=False,
            )

            self.progress.status = "complete"
            self.progress.end_time = datetime.now(UTC)
            self.progress.total_files = result['indexed_files']
            self.progress.files_completed = result['indexed_files']

            logger.info(f"Foreground indexing complete for {self.project_name}: "
                       f"{result['indexed_files']} files, {result['total_units']} units")

            return result

        except Exception as e:
            self.progress.status = "error"
            self.progress.error_message = str(e)
            self.progress.end_time = datetime.now(UTC)
            logger.error(f"Foreground indexing failed for {self.project_name}: {e}")
            raise

    async def _index_in_background(
        self,
        progress_callback: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """
        Index project in background (non-blocking).

        Args:
            progress_callback: Optional callback for progress updates

        Returns:
            Indexing result dictionary
        """
        self.progress.status = "indexing"
        self.progress.is_background = True
        self.progress.start_time = datetime.now(UTC)

        logger.info(f"Starting background indexing for {self.project_name}")

        try:
            # Index directory
            result = await self.indexer.index_directory(
                self.project_path,
                recursive=self.config.indexing.auto_index_recursive,
                show_progress=False,
                progress_callback=progress_callback,
            )

            # Update tracker metadata
            await self.tracker.update_metadata(
                project_name=self.project_name,
                total_files=result['indexed_files'],
                total_units=result['total_units'],
                is_watching=False,
            )

            self.progress.status = "complete"
            self.progress.end_time = datetime.now(UTC)
            self.progress.total_files = result['indexed_files']
            self.progress.files_completed = result['indexed_files']

            logger.info(f"Background indexing complete for {self.project_name}: "
                       f"{result['indexed_files']} files, {result['total_units']} units")

            return result

        except Exception as e:
            self.progress.status = "error"
            self.progress.error_message = str(e)
            self.progress.end_time = datetime.now(UTC)
            logger.error(f"Background indexing failed for {self.project_name}: {e}")
            raise

    async def start_auto_indexing(
        self,
        force: bool = False,
        progress_callback: Optional[Callable] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Start auto-indexing if needed.

        Args:
            force: Force indexing even if not needed
            progress_callback: Optional callback for progress updates

        Returns:
            Indexing result if indexing ran, None if skipped
        """
        if not self.is_initialized:
            raise IndexingError("Service not initialized. Call initialize() first.")

        # Check if we should index
        if not force and not await self.should_auto_index():
            logger.info(f"Skipping auto-index for {self.project_name}")
            return None

        # Count files
        self.progress.status = "counting"
        file_count = await self._count_indexable_files()
        self.progress.total_files = file_count

        logger.info(f"Found {file_count} indexable files in {self.project_name}")

        # Determine foreground vs background mode
        size_threshold = self.config.indexing.auto_index_size_threshold

        if file_count > size_threshold:
            # Background mode for large projects
            logger.info(f"Using background mode (file_count={file_count} > threshold={size_threshold})")

            # Start background task
            self.indexing_task = asyncio.create_task(
                self._index_in_background(progress_callback)
            )

            # Return immediately (non-blocking)
            return {
                "mode": "background",
                "file_count": file_count,
                "status": "indexing"
            }
        else:
            # Foreground mode for small projects
            logger.info(f"Using foreground mode (file_count={file_count} <= threshold={size_threshold})")
            result = await self._index_in_foreground(progress_callback)
            result["mode"] = "foreground"
            return result

    async def start_watching(self) -> None:
        """Start file watcher for incremental updates."""
        if not self.is_initialized:
            raise IndexingError("Service not initialized. Call initialize() first.")

        if not self.config.indexing.file_watcher:
            logger.info("File watcher disabled in configuration")
            return

        try:
            # Create indexing service if not exists
            if not self.indexing_service:
                # PERF-009: Pass existing indexer to avoid creating duplicate
                # ProcessPoolExecutor instances, which causes memory bloat
                self.indexing_service = IndexingService(
                    watch_path=self.project_path,
                    project_name=self.project_name,
                    indexer=self.indexer,  # Reuse our indexer
                )
                await self.indexing_service.initialize()

            # Start watching (non-blocking)
            logger.info(f"Starting file watcher for {self.project_name}")

            # Update tracker to indicate watching
            await self.tracker.set_watching(self.project_name, True)

            # Note: The actual watching happens in the IndexingService's background task

        except Exception as e:
            logger.error(f"Failed to start file watcher: {e}")
            raise

    async def stop_watching(self) -> None:
        """Stop file watcher."""
        if self.indexing_service:
            await self.indexing_service.stop()
            await self.tracker.set_watching(self.project_name, False)
            logger.info(f"Stopped file watcher for {self.project_name}")

    async def get_progress(self) -> Dict[str, Any]:
        """
        Get current indexing progress.

        Returns:
            Progress dictionary
        """
        return self.progress.to_dict()

    async def wait_for_completion(self, timeout: Optional[float] = None) -> Dict[str, Any]:
        """
        Wait for background indexing to complete.

        Args:
            timeout: Optional timeout in seconds

        Returns:
            Indexing result

        Raises:
            asyncio.TimeoutError: If timeout exceeded
        """
        if not self.indexing_task:
            raise IndexingError("No background indexing task running")

        if timeout:
            return await asyncio.wait_for(self.indexing_task, timeout=timeout)
        else:
            return await self.indexing_task

    async def trigger_reindex(self, progress_callback: Optional[Callable] = None) -> Dict[str, Any]:
        """
        Manually trigger a full re-index.

        Args:
            progress_callback: Optional callback for progress updates

        Returns:
            Indexing result
        """
        logger.info(f"Manual re-index triggered for {self.project_name}")
        return await self.start_auto_indexing(force=True, progress_callback=progress_callback)

    async def close(self) -> None:
        """Clean up resources."""
        try:
            # Stop watching if active
            if self.indexing_service:
                await self.stop_watching()

            # Wait for background task if running
            if self.indexing_task and not self.indexing_task.done():
                try:
                    await asyncio.wait_for(self.indexing_task, timeout=5.0)
                except asyncio.TimeoutError:
                    logger.warning("Background indexing task did not complete in time")
                    self.indexing_task.cancel()

            # Close components
            if self.indexer:
                await self.indexer.close()

            if self.indexing_service:
                await self.indexing_service.close()

            await self.tracker.close()

            logger.info(f"AutoIndexingService closed for {self.project_name}")

        except Exception as e:
            logger.error(f"Error closing AutoIndexingService: {e}")
            raise
