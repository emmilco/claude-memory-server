"""File watcher for automatic code indexing."""

import asyncio
import logging
import hashlib
from pathlib import Path
from typing import Set, Optional, Callable, Dict, Any
from datetime import datetime, UTC
from collections import defaultdict

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileSystemEvent

from src.config import ServerConfig, get_config

logger = logging.getLogger(__name__)


class DebouncedFileWatcher(FileSystemEventHandler):
    """
    File system watcher with debouncing to avoid excessive re-indexing.

    Features:
    - Monitors file changes in a directory
    - Debounces rapid changes (default: 1000ms)
    - Filters by file patterns (e.g., *.py, *.js)
    - Async callback support
    - Tracks file hashes to detect actual changes
    """

    def __init__(
        self,
        watch_path: Path,
        callback: Callable[[Path], None],
        patterns: Optional[Set[str]] = None,
        debounce_ms: int = 1000,
        recursive: bool = True,
    ):
        """
        Initialize file watcher.

        Args:
            watch_path: Directory to watch
            callback: Async function to call when files change
            patterns: File patterns to watch (e.g., {".py", ".js", ".ts"})
            debounce_ms: Milliseconds to wait before triggering callback
            recursive: Watch subdirectories
        """
        super().__init__()

        self.watch_path = Path(watch_path).resolve()
        self.callback = callback
        self.patterns = patterns or {".py", ".js", ".ts", ".java", ".go", ".rs", ".md"}
        self.debounce_ms = debounce_ms
        self.recursive = recursive

        # Debouncing state
        self.pending_files: Set[Path] = set()
        self.pending_lock = asyncio.Lock()
        self.debounce_task: Optional[asyncio.Task] = None

        # File hash tracking (to detect actual content changes)
        self.file_hashes: Dict[Path, str] = {}

        logger.info(f"File watcher initialized for {watch_path}")
        logger.info(f"Watching patterns: {self.patterns}")
        logger.info(f"Debounce: {debounce_ms}ms, Recursive: {recursive}")

    def _should_process(self, file_path: Path) -> bool:
        """Check if file should be processed based on patterns."""
        if not file_path.is_file():
            return False

        # Check if file extension matches patterns
        return file_path.suffix in self.patterns

    def _compute_file_hash(self, file_path: Path) -> Optional[str]:
        """Compute SHA256 hash of file contents."""
        try:
            with open(file_path, "rb") as f:
                return hashlib.sha256(f.read()).hexdigest()
        except Exception as e:
            logger.warning(f"Failed to hash {file_path}: {e}")
            return None

    def _has_changed(self, file_path: Path) -> bool:
        """Check if file content has actually changed."""
        current_hash = self._compute_file_hash(file_path)
        if current_hash is None:
            return False

        previous_hash = self.file_hashes.get(file_path)
        has_changed = previous_hash != current_hash

        # Update hash
        self.file_hashes[file_path] = current_hash

        return has_changed

    def on_modified(self, event: FileSystemEvent):
        """Handle file modification events."""
        if event.is_directory:
            return

        file_path = Path(event.src_path)
        if self._should_process(file_path) and self._has_changed(file_path):
            logger.debug(f"File modified: {file_path}")
            asyncio.create_task(self._debounce_callback(file_path))

    def on_created(self, event: FileSystemEvent):
        """Handle file creation events."""
        if event.is_directory:
            return

        file_path = Path(event.src_path)
        if self._should_process(file_path):
            logger.debug(f"File created: {file_path}")
            # New file - mark as changed
            self._compute_file_hash(file_path)  # Initialize hash
            asyncio.create_task(self._debounce_callback(file_path))

    def on_deleted(self, event: FileSystemEvent):
        """Handle file deletion events."""
        if event.is_directory:
            return

        file_path = Path(event.src_path)
        if file_path in self.file_hashes:
            logger.debug(f"File deleted: {file_path}")
            # Remove from hash tracking
            del self.file_hashes[file_path]
            # Note: deletion handling could trigger cleanup in vector DB

    async def _debounce_callback(self, file_path: Path):
        """Add file to pending queue and schedule debounced callback."""
        async with self.pending_lock:
            self.pending_files.add(file_path)

            # Cancel existing debounce task
            if self.debounce_task and not self.debounce_task.done():
                self.debounce_task.cancel()

            # Schedule new debounced callback
            self.debounce_task = asyncio.create_task(
                self._execute_debounced_callback()
            )

    async def _execute_debounced_callback(self):
        """Execute callback after debounce delay."""
        # Wait for debounce period
        await asyncio.sleep(self.debounce_ms / 1000.0)

        async with self.pending_lock:
            if not self.pending_files:
                return

            # Process all pending files
            files_to_process = list(self.pending_files)
            self.pending_files.clear()

        logger.info(f"Processing {len(files_to_process)} changed files")

        # Call callback for each file
        for file_path in files_to_process:
            try:
                if asyncio.iscoroutinefunction(self.callback):
                    await self.callback(file_path)
                else:
                    self.callback(file_path)
            except Exception as e:
                logger.error(f"Error processing {file_path}: {e}")


class FileWatcherService:
    """
    File watcher service that integrates with the MCP server.

    Monitors code files and triggers automatic indexing when changes are detected.
    """

    def __init__(
        self,
        watch_path: Path,
        callback: Callable[[Path], None],
        config: Optional[ServerConfig] = None,
    ):
        """
        Initialize file watcher service.

        Args:
            watch_path: Directory to watch
            callback: Async callback for file changes
            config: Server configuration
        """
        if config is None:
            config = get_config()

        self.config = config
        self.watch_path = Path(watch_path).resolve()
        self.callback = callback

        # Create event handler
        self.event_handler = DebouncedFileWatcher(
            watch_path=self.watch_path,
            callback=self.callback,
            debounce_ms=self.config.watch_debounce_ms,
            recursive=True,
        )

        # Create observer
        self.observer = Observer()
        self.observer.schedule(
            self.event_handler,
            str(self.watch_path),
            recursive=True,
        )

        self.is_running = False
        logger.info(f"File watcher service initialized for {watch_path}")

    def start(self):
        """Start watching for file changes."""
        if self.is_running:
            logger.warning("File watcher already running")
            return

        logger.info(f"Starting file watcher for {self.watch_path}")
        self.observer.start()
        self.is_running = True

    def stop(self):
        """Stop watching for file changes."""
        if not self.is_running:
            return

        logger.info("Stopping file watcher")
        self.observer.stop()
        self.observer.join()
        self.is_running = False

    async def start_async(self):
        """Start watcher asynchronously."""
        self.start()

        try:
            # Run until stopped
            while self.is_running:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            self.stop()
            raise

    def __enter__(self):
        """Context manager entry."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop()


async def example_callback(file_path: Path):
    """Example callback for file changes."""
    logger.info(f"File changed: {file_path}")
    # Here you would trigger re-indexing
    # await index_file(file_path)


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Watch current directory
    watcher = FileWatcherService(
        watch_path=Path.cwd(),
        callback=example_callback,
    )

    try:
        watcher.start()
        # Keep running
        import time
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        watcher.stop()
