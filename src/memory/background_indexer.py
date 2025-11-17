"""Background indexing with job management and resumption support."""

import asyncio
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any, Callable
from datetime import datetime, UTC
import time

from src.memory.incremental_indexer import IncrementalIndexer
from src.memory.job_state_manager import JobStateManager, JobStatus, IndexingJob
from src.memory.notification_manager import NotificationManager
from src.config import ServerConfig, get_config

logger = logging.getLogger(__name__)


class BackgroundIndexer:
    """
    Background indexing service with job management.

    Features:
    - Non-blocking background indexing
    - Job state persistence (resume after interruption)
    - Progress tracking and notifications
    - Pause/resume/cancel operations
    - Search available on partial results
    """

    def __init__(
        self,
        config: Optional[ServerConfig] = None,
        job_db_path: Optional[str] = None,
        notification_manager: Optional[NotificationManager] = None,
    ):
        """
        Initialize background indexer.

        Args:
            config: Server configuration
            job_db_path: Path to job state database
            notification_manager: Notification manager
        """
        if config is None:
            config = get_config()

        self.config = config

        # Job state manager
        if job_db_path is None:
            from pathlib import Path
            cache_dir = Path.home() / ".claude-rag"
            cache_dir.mkdir(parents=True, exist_ok=True)
            job_db_path = str(cache_dir / "indexing_jobs.db")

        self.job_manager = JobStateManager(job_db_path)

        # Notification manager
        self.notification_manager = notification_manager or NotificationManager()

        # Active jobs (job_id -> asyncio.Task)
        self._active_tasks: Dict[str, asyncio.Task] = {}

        # Cancellation events (job_id -> asyncio.Event)
        self._cancel_events: Dict[str, asyncio.Event] = {}

        logger.info("Background indexer initialized")

    async def start_indexing_job(
        self,
        directory: Path,
        project_name: Optional[str] = None,
        recursive: bool = True,
        background: bool = True,
    ) -> str:
        """
        Start new indexing job.

        Args:
            directory: Directory to index
            project_name: Project name (defaults to directory name)
            recursive: Index recursively
            background: Run in background (non-blocking)

        Returns:
            Job ID
        """
        directory = Path(directory).resolve()

        if not directory.exists():
            raise ValueError(f"Directory does not exist: {directory}")

        if not directory.is_dir():
            raise ValueError(f"Not a directory: {directory}")

        # Determine project name
        if not project_name:
            project_name = directory.name

        # Create job
        job = self.job_manager.create_job(
            project_name=project_name,
            directory_path=directory,
            recursive=recursive,
        )

        logger.info(f"Created indexing job {job.id} for {project_name}")

        # Start job
        if background:
            # Run in background
            task = asyncio.create_task(self._run_job(job.id))
            self._active_tasks[job.id] = task
            logger.info(f"Job {job.id} started in background")
        else:
            # Run synchronously (blocking)
            await self._run_job(job.id)

        return job.id

    async def pause_job(self, job_id: str) -> bool:
        """
        Pause running job.

        Args:
            job_id: Job ID

        Returns:
            True if paused successfully
        """
        job = self.job_manager.get_job(job_id)
        if not job:
            logger.warning(f"Job {job_id} not found")
            return False

        if job.status != JobStatus.RUNNING:
            logger.warning(f"Job {job_id} is not running (status: {job.status})")
            return False

        # Set cancellation event
        if job_id not in self._cancel_events:
            self._cancel_events[job_id] = asyncio.Event()

        self._cancel_events[job_id].set()

        # Update status
        self.job_manager.update_job_status(job_id, JobStatus.PAUSED)

        # Wait for task to complete
        if job_id in self._active_tasks:
            try:
                await asyncio.wait_for(self._active_tasks[job_id], timeout=5.0)
            except asyncio.TimeoutError:
                logger.warning(f"Job {job_id} did not pause gracefully, forcing")

        # Notify
        total_files = job.total_files or 0
        await self.notification_manager.notify_paused(
            job_id=job_id,
            project_name=job.project_name,
            indexed_files=job.indexed_files,
            total_files=total_files,
        )

        logger.info(f"Job {job_id} paused")
        return True

    async def resume_job(self, job_id: str, background: bool = True) -> bool:
        """
        Resume paused job.

        Args:
            job_id: Job ID
            background: Run in background

        Returns:
            True if resumed successfully
        """
        job = self.job_manager.get_job(job_id)
        if not job:
            logger.warning(f"Job {job_id} not found")
            return False

        if job.status != JobStatus.PAUSED:
            logger.warning(f"Job {job_id} is not paused (status: {job.status})")
            return False

        # Clear cancellation event
        if job_id in self._cancel_events:
            self._cancel_events[job_id].clear()

        # Update status
        self.job_manager.update_job_status(job_id, JobStatus.QUEUED)

        # Calculate remaining files
        indexed_count = len(job.indexed_file_list or [])
        total_files = job.total_files or 0
        remaining_files = max(0, total_files - indexed_count)

        # Notify
        await self.notification_manager.notify_resumed(
            job_id=job_id,
            project_name=job.project_name,
            indexed_files=indexed_count,
            remaining_files=remaining_files,
        )

        # Restart job
        if background:
            task = asyncio.create_task(self._run_job(job_id))
            self._active_tasks[job_id] = task
            logger.info(f"Job {job_id} resumed in background")
        else:
            await self._run_job(job_id)

        return True

    async def cancel_job(self, job_id: str) -> bool:
        """
        Cancel job.

        Args:
            job_id: Job ID

        Returns:
            True if cancelled successfully
        """
        job = self.job_manager.get_job(job_id)
        if not job:
            logger.warning(f"Job {job_id} not found")
            return False

        if job.status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED):
            logger.warning(f"Job {job_id} already finished (status: {job.status})")
            return False

        # Set cancellation event
        if job_id not in self._cancel_events:
            self._cancel_events[job_id] = asyncio.Event()

        self._cancel_events[job_id].set()

        # Update status
        self.job_manager.update_job_status(job_id, JobStatus.CANCELLED)

        # Wait for task to complete
        if job_id in self._active_tasks:
            try:
                await asyncio.wait_for(self._active_tasks[job_id], timeout=5.0)
            except asyncio.TimeoutError:
                logger.warning(f"Job {job_id} did not cancel gracefully, forcing")
                self._active_tasks[job_id].cancel()

            del self._active_tasks[job_id]

        # Notify
        total_files = job.total_files or 0
        await self.notification_manager.notify_cancelled(
            job_id=job_id,
            project_name=job.project_name,
            indexed_files=job.indexed_files,
            total_files=total_files,
        )

        logger.info(f"Job {job_id} cancelled")
        return True

    async def get_job_status(self, job_id: str) -> Optional[IndexingJob]:
        """
        Get job status.

        Args:
            job_id: Job ID

        Returns:
            Job or None if not found
        """
        return self.job_manager.get_job(job_id)

    async def list_jobs(
        self,
        status: Optional[JobStatus] = None,
        project_name: Optional[str] = None,
        limit: int = 100,
    ) -> List[IndexingJob]:
        """
        List jobs.

        Args:
            status: Filter by status
            project_name: Filter by project name
            limit: Maximum jobs to return

        Returns:
            List of jobs
        """
        return self.job_manager.list_jobs(status, project_name, limit)

    async def delete_job(self, job_id: str) -> bool:
        """
        Delete job from database.

        Args:
            job_id: Job ID

        Returns:
            True if deleted
        """
        # Can only delete finished jobs
        job = self.job_manager.get_job(job_id)
        if not job:
            return False

        if job.status not in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED):
            logger.warning(f"Cannot delete active job {job_id} (status: {job.status})")
            return False

        return self.job_manager.delete_job(job_id)

    async def _run_job(self, job_id: str) -> None:
        """
        Run indexing job (internal).

        Args:
            job_id: Job ID
        """
        job = self.job_manager.get_job(job_id)
        if not job:
            logger.error(f"Job {job_id} not found")
            return

        # Create cancellation event if needed
        if job_id not in self._cancel_events:
            self._cancel_events[job_id] = asyncio.Event()

        # Update status to running
        self.job_manager.update_job_status(job_id, JobStatus.RUNNING)

        # Get indexed files (for resumption)
        indexed_files_set = set(job.indexed_file_list or [])

        logger.info(f"Starting job {job_id} for {job.project_name}")

        start_time = time.time()
        indexed_count = len(indexed_files_set)
        failed_count = job.failed_files
        units_count = job.total_units

        try:
            # Create indexer
            indexer = IncrementalIndexer(project_name=job.project_name, config=self.config)
            await indexer.initialize()

            # Get list of files to index
            directory = Path(job.directory_path)
            pattern = "**/*" if job.recursive else "*"
            all_files = []

            for ext in indexer.SUPPORTED_EXTENSIONS:
                all_files.extend(directory.glob(f"{pattern}{ext}"))

            # Filter out hidden files and already-indexed files
            files_to_index = [
                f for f in all_files
                if not any(part.startswith(".") for part in f.parts)
                and str(f.resolve()) not in indexed_files_set
            ]

            total_files = len(files_to_index) + len(indexed_files_set)

            logger.info(
                f"Job {job_id}: Found {len(files_to_index)} files to index "
                f"({len(indexed_files_set)} already indexed)"
            )

            # Update total file count
            self.job_manager.update_job_progress(
                job_id=job_id,
                indexed_files=indexed_count,
                failed_files=failed_count,
                total_units=units_count,
                total_files=total_files,
            )

            # Notify started
            await self.notification_manager.notify_started(
                job_id=job_id,
                project_name=job.project_name,
                directory=str(directory),
                total_files=total_files,
            )

            # Index files
            for i, file_path in enumerate(files_to_index):
                # Check for cancellation
                if job_id in self._cancel_events and self._cancel_events[job_id].is_set():
                    logger.info(f"Job {job_id} cancelled/paused")
                    break

                try:
                    # Index file
                    result = await indexer.index_file(file_path)

                    if not result.get("skipped"):
                        units_count += result.get("units_indexed", 0)
                        indexed_count += 1

                        # Track indexed file
                        self.job_manager.add_indexed_file(job_id, str(file_path.resolve()))

                    # Update progress
                    self.job_manager.update_job_progress(
                        job_id=job_id,
                        indexed_files=indexed_count,
                        failed_files=failed_count,
                        total_units=units_count,
                        last_indexed_file=file_path.name,
                    )

                    # Periodic progress notification (every 5 seconds via throttling)
                    await self.notification_manager.notify_progress(
                        job_id=job_id,
                        project_name=job.project_name,
                        indexed_files=indexed_count,
                        total_files=total_files,
                        total_units=units_count,
                        current_file=file_path.name,
                    )

                except Exception as e:
                    logger.error(f"Job {job_id}: Failed to index {file_path}: {e}")
                    failed_count += 1

                    # Update failed count
                    self.job_manager.update_job_progress(
                        job_id=job_id,
                        indexed_files=indexed_count,
                        failed_files=failed_count,
                        total_units=units_count,
                    )

            await indexer.close()

            # Check if cancelled/paused
            if job_id in self._cancel_events and self._cancel_events[job_id].is_set():
                job = self.job_manager.get_job(job_id)
                # Status already updated by pause/cancel handlers
                logger.info(f"Job {job_id} stopped (status: {job.status if job else 'unknown'})")
                return

            # Mark as completed
            elapsed = time.time() - start_time
            self.job_manager.update_job_status(job_id, JobStatus.COMPLETED)

            # Notify completion
            await self.notification_manager.notify_completed(
                job_id=job_id,
                project_name=job.project_name,
                indexed_files=indexed_count,
                total_units=units_count,
                elapsed_seconds=elapsed,
                failed_files=failed_count,
            )

            logger.info(
                f"Job {job_id} completed: {indexed_count} files, {units_count} units, "
                f"{elapsed:.1f}s ({failed_count} failed)"
            )

        except Exception as e:
            logger.error(f"Job {job_id} failed: {e}", exc_info=True)

            # Mark as failed
            error_msg = str(e)
            self.job_manager.update_job_status(job_id, JobStatus.FAILED, error_message=error_msg)

            # Notify failure
            await self.notification_manager.notify_failed(
                job_id=job_id,
                project_name=job.project_name,
                error_message=error_msg,
                indexed_files=indexed_count,
                total_files=total_files if 'total_files' in locals() else None,
            )

        finally:
            # Clean up
            if job_id in self._active_tasks:
                del self._active_tasks[job_id]

            # Keep cancel event for potential resume
