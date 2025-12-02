"""Notification system for background indexing events."""

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Optional, List, Callable, Dict, Any
from datetime import datetime, UTC

try:
    from rich.console import Console
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

logger = logging.getLogger(__name__)


class NotificationBackend(ABC):
    """Abstract base class for notification backends."""

    @abstractmethod
    async def notify(self, title: str, message: str, level: str = "info") -> None:
        """
        Send notification.

        Args:
            title: Notification title
            message: Notification message
            level: Notification level (info, success, warning, error)
        """
        pass


class ConsoleNotificationBackend(NotificationBackend):
    """Console notification backend using Rich."""

    def __init__(self):
        """Initialize console backend."""
        self.console = Console() if RICH_AVAILABLE else None

    async def notify(self, title: str, message: str, level: str = "info") -> None:
        """Print notification to console."""
        if self.console:
            # Rich formatting
            level_styles = {
                "info": "blue",
                "success": "green",
                "warning": "yellow",
                "error": "red",
            }
            style = level_styles.get(level, "white")

            self.console.print(f"\n[{style}]▶ {title}[/{style}]")
            self.console.print(f"  [dim]{message}[/dim]\n")
        else:
            # Plain text fallback
            print(f"\n{title}")
            print(f"  {message}\n")


class LogNotificationBackend(NotificationBackend):
    """Log notification backend."""

    async def notify(self, title: str, message: str, level: str = "info") -> None:
        """Log notification."""
        log_message = f"{title}: {message}"

        if level == "error":
            logger.error(log_message)
        elif level == "warning":
            logger.warning(log_message)
        else:
            logger.info(log_message)


class CallbackNotificationBackend(NotificationBackend):
    """Callback notification backend for custom handlers."""

    def __init__(self, callback: Callable[[str, str, str], None]):
        """
        Initialize callback backend.

        Args:
            callback: Function to call with (title, message, level)
        """
        self.callback = callback

    async def notify(self, title: str, message: str, level: str = "info") -> None:
        """Call custom callback."""
        try:
            if asyncio.iscoroutinefunction(self.callback):
                await self.callback(title, message, level)
            else:
                self.callback(title, message, level)
        except Exception as e:
            logger.error(f"Notification callback error: {e}")


class NotificationManager:
    """
    Manages notifications for background indexing events.

    Supports multiple backends:
    - Console (Rich formatted output)
    - Log (standard logging)
    - Callback (custom handlers)
    - Desktop (platform-specific, future)
    """

    def __init__(
        self,
        backends: Optional[List[NotificationBackend]] = None,
        throttle_seconds: int = 5,
    ):
        """
        Initialize notification manager.

        Args:
            backends: List of notification backends to use
            throttle_seconds: Minimum seconds between progress notifications
        """
        if backends is None:
            # Default: console + log
            backends = [
                ConsoleNotificationBackend(),
                LogNotificationBackend(),
            ]

        self.backends = backends
        self.throttle_seconds = throttle_seconds
        self._last_progress_time: Dict[str, float] = {}
        self._throttle_lock = asyncio.Lock()

    async def notify_started(
        self,
        job_id: str,
        project_name: str,
        directory: str,
        total_files: Optional[int] = None,
    ) -> None:
        """
        Notify that indexing job has started.

        Args:
            job_id: Job ID
            project_name: Project name
            directory: Directory being indexed
            total_files: Total files to index (if known)
        """
        title = f"🚀 Indexing Started: {project_name}"

        if total_files:
            message = f"Indexing {total_files:,} files from {directory}"
        else:
            message = f"Indexing files from {directory}"

        message += f"\nJob ID: {job_id}"

        await self._notify_all(title, message, "info")

    async def notify_progress(
        self,
        job_id: str,
        project_name: str,
        indexed_files: int,
        total_files: int,
        total_units: int,
        current_file: Optional[str] = None,
    ) -> None:
        """
        Notify of indexing progress (throttled).

        Args:
            job_id: Job ID
            project_name: Project name
            indexed_files: Files indexed so far
            total_files: Total files to index
            total_units: Semantic units indexed so far
            current_file: Current file being indexed
        """
        # Throttle progress notifications (thread-safe)
        async with self._throttle_lock:
            now = datetime.now(UTC).timestamp()
            last_time = self._last_progress_time.get(job_id, 0)

            if now - last_time < self.throttle_seconds:
                return  # Skip this notification

            self._last_progress_time[job_id] = now

        percent = (indexed_files / total_files * 100) if total_files > 0 else 0
        title = f"⏳ Indexing Progress: {project_name}"
        message = f"{indexed_files:,}/{total_files:,} files ({percent:.1f}%)"
        message += f"\n{total_units:,} semantic units indexed"

        if current_file:
            message += f"\nCurrent: {current_file}"

        await self._notify_all(title, message, "info")

    async def notify_completed(
        self,
        job_id: str,
        project_name: str,
        indexed_files: int,
        total_units: int,
        elapsed_seconds: float,
        failed_files: int = 0,
    ) -> None:
        """
        Notify that indexing job has completed.

        Args:
            job_id: Job ID
            project_name: Project name
            indexed_files: Total files indexed
            total_units: Total semantic units indexed
            elapsed_seconds: Time elapsed
            failed_files: Number of failed files
        """
        title = f"✅ Indexing Complete: {project_name}"

        message = f"Indexed {indexed_files:,} files"
        message += f"\n{total_units:,} semantic units"
        message += f"\nTime: {elapsed_seconds:.1f}s"

        if indexed_files > 0:
            files_per_sec = indexed_files / elapsed_seconds
            message += f" ({files_per_sec:.1f} files/sec)"

        if failed_files > 0:
            message += f"\n⚠️  {failed_files} files failed"

        await self._notify_all(title, message, "success")

    async def notify_paused(
        self,
        job_id: str,
        project_name: str,
        indexed_files: int,
        total_files: int,
    ) -> None:
        """
        Notify that indexing job has been paused.

        Args:
            job_id: Job ID
            project_name: Project name
            indexed_files: Files indexed before pause
            total_files: Total files to index
        """
        title = f"⏸️  Indexing Paused: {project_name}"
        percent = (indexed_files / total_files * 100) if total_files > 0 else 0
        message = f"Progress: {indexed_files:,}/{total_files:,} files ({percent:.1f}%)"
        message += f"\nJob ID: {job_id}"

        await self._notify_all(title, message, "warning")

    async def notify_resumed(
        self,
        job_id: str,
        project_name: str,
        indexed_files: int,
        remaining_files: int,
    ) -> None:
        """
        Notify that indexing job has been resumed.

        Args:
            job_id: Job ID
            project_name: Project name
            indexed_files: Files already indexed
            remaining_files: Files remaining
        """
        title = f"▶️  Indexing Resumed: {project_name}"
        message = f"Already indexed: {indexed_files:,} files"
        message += f"\nRemaining: {remaining_files:,} files"
        message += f"\nJob ID: {job_id}"

        await self._notify_all(title, message, "info")

    async def notify_failed(
        self,
        job_id: str,
        project_name: str,
        error_message: str,
        indexed_files: int = 0,
        total_files: Optional[int] = None,
    ) -> None:
        """
        Notify that indexing job has failed.

        Args:
            job_id: Job ID
            project_name: Project name
            error_message: Error description
            indexed_files: Files indexed before failure
            total_files: Total files to index
        """
        title = f"❌ Indexing Failed: {project_name}"
        message = f"Error: {error_message}"

        if total_files:
            percent = (indexed_files / total_files * 100) if total_files > 0 else 0
            message += f"\nProgress before failure: {indexed_files:,}/{total_files:,} ({percent:.1f}%)"
        else:
            message += f"\nFiles indexed before failure: {indexed_files:,}"

        message += f"\nJob ID: {job_id}"

        await self._notify_all(title, message, "error")

    async def notify_cancelled(
        self,
        job_id: str,
        project_name: str,
        indexed_files: int,
        total_files: Optional[int] = None,
    ) -> None:
        """
        Notify that indexing job was cancelled.

        Args:
            job_id: Job ID
            project_name: Project name
            indexed_files: Files indexed before cancellation
            total_files: Total files to index
        """
        title = f"🛑 Indexing Cancelled: {project_name}"

        if total_files:
            percent = (indexed_files / total_files * 100) if total_files > 0 else 0
            message = f"Progress: {indexed_files:,}/{total_files:,} files ({percent:.1f}%)"
        else:
            message = f"Files indexed: {indexed_files:,}"

        message += f"\nJob ID: {job_id}"

        await self._notify_all(title, message, "warning")

    def add_backend(self, backend: NotificationBackend) -> None:
        """
        Add notification backend.

        Args:
            backend: Backend to add
        """
        self.backends.append(backend)

    def remove_backend(self, backend: NotificationBackend) -> None:
        """
        Remove notification backend.

        Args:
            backend: Backend to remove
        """
        if backend in self.backends:
            self.backends.remove(backend)

    async def _notify_all(self, title: str, message: str, level: str) -> None:
        """Send notification to all backends."""
        import asyncio

        tasks = [
            backend.notify(title, message, level)
            for backend in self.backends
        ]

        # Send to all backends concurrently
        await asyncio.gather(*tasks, return_exceptions=True)
