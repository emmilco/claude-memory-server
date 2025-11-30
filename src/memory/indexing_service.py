"""Indexing service that combines file watching and incremental indexing."""

import asyncio
import logging
from pathlib import Path
from typing import Optional

from src.memory.file_watcher import FileWatcherService
from src.memory.incremental_indexer import IncrementalIndexer
from src.config import ServerConfig, get_config

logger = logging.getLogger(__name__)


class IndexingService:
    """
    Service that watches a directory and automatically re-indexes changed files.

    Combines:
    - File watcher (detects file changes with debouncing)
    - Incremental indexer (parses and stores semantic units)
    """

    def __init__(
        self,
        watch_path: Path,
        project_name: Optional[str] = None,
        config: Optional[ServerConfig] = None,
        indexer: Optional[IncrementalIndexer] = None,
    ):
        """
        Initialize indexing service.

        Args:
            watch_path: Directory to watch for changes
            project_name: Project name for scoping
            config: Server configuration
            indexer: Optional existing indexer to reuse. If None, creates a new one.
                     PERF-009: Pass an existing indexer to avoid creating duplicate
                     ProcessPoolExecutor instances, which causes memory bloat.
        """
        if config is None:
            config = get_config()

        self.config = config
        self.watch_path = Path(watch_path).resolve()
        self.project_name = project_name or self.watch_path.name

        # PERF-009: Reuse existing indexer if provided, otherwise create new one
        # This prevents duplicate ProcessPoolExecutor/embedding generator instances
        if indexer is not None:
            self.indexer = indexer
            self._owns_indexer = False  # Don't close it - caller owns it
            logger.info(f"Indexing service reusing existing indexer for {self.watch_path}")
        else:
            self.indexer = IncrementalIndexer(
                project_name=self.project_name,
                config=config,
            )
            self._owns_indexer = True  # We created it, we close it
            logger.info(f"Indexing service created new indexer for {self.watch_path}")

        # File watcher will be created when starting (needs event loop)
        self.watcher = None

        self.is_initialized = False

    async def initialize(self) -> None:
        """Initialize the service."""
        if self.is_initialized:
            return

        # PERF-009: Only initialize indexer if we own it (created it ourselves)
        # If reusing an existing indexer, it's already initialized
        if self._owns_indexer:
            await self.indexer.initialize()
        self.is_initialized = True
        logger.info("Indexing service initialized")

    async def start(self) -> None:
        """Start watching for file changes."""
        if not self.is_initialized:
            await self.initialize()

        # Create watcher with current event loop if not already created
        if self.watcher is None:
            loop = asyncio.get_running_loop()
            self.watcher = FileWatcherService(
                watch_path=self.watch_path,
                callback=self._on_file_change,
                config=self.config,
                loop=loop,
            )

        logger.info(f"Starting file watcher for {self.watch_path}")
        self.watcher.start()

    async def stop(self) -> None:
        """Stop watching for file changes."""
        logger.info("Stopping indexing service")
        if self.watcher is not None:
            self.watcher.stop()

    async def _on_file_change(self, file_path: Path) -> None:
        """
        Callback for file watcher - re-index changed files.

        Args:
            file_path: Path to changed file
        """
        try:
            if file_path.exists():
                logger.info(f"File changed, re-indexing: {file_path.name}")
                result = await self.indexer.index_file(file_path)

                if not result.get("skipped"):
                    logger.info(
                        f"Re-indexed {result['units_indexed']} units from {file_path.name} "
                        f"({result.get('parse_time_ms', 0):.2f}ms)"
                    )
            else:
                # File was deleted
                logger.info(f"File deleted, removing index: {file_path.name}")
                deleted_count = await self.indexer.delete_file_index(file_path)
                logger.info(f"Removed {deleted_count} units from index")

        except Exception as e:
            logger.error(f"Error processing file change for {file_path}: {e}")

    async def run_until_stopped(self) -> None:
        """
        Start watching and run until stopped (blocking).

        Use this for the watch CLI command.
        """
        await self.start()

        try:
            logger.info("Indexing service running. Press Ctrl+C to stop.")
            # Run indefinitely
            while True:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            logger.info("Indexing service cancelled")
        finally:
            await self.stop()

    async def index_initial(self, recursive: bool = True) -> dict:
        """
        Perform initial indexing of all files in watch directory.

        Args:
            recursive: Recursively index subdirectories

        Returns:
            Indexing statistics
        """
        if not self.is_initialized:
            await self.initialize()

        logger.info(f"Starting initial indexing of {self.watch_path}")
        result = await self.indexer.index_directory(
            self.watch_path,
            recursive=recursive,
            show_progress=True,
        )
        logger.info(
            f"Initial indexing complete: {result['indexed_files']} files, "
            f"{result['total_units']} units"
        )
        return result

    async def close(self) -> None:
        """Clean up resources."""
        await self.stop()
        # PERF-009: Only close indexer if we own it (created it ourselves)
        # If reusing an existing indexer, the caller is responsible for closing it
        if self._owns_indexer:
            await self.indexer.close()
        logger.info("Indexing service closed")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        asyncio.run(self.close())
