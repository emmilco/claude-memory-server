"""Automatic archival scheduler for periodic project archival."""

import logging
from datetime import datetime, UTC
from typing import Optional, Dict, Callable
from dataclasses import dataclass
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from src.memory.bulk_archival import BulkArchivalManager, BulkArchivalResult

logger = logging.getLogger(__name__)


@dataclass
class ArchivalScheduleConfig:
    """Configuration for automatic archival scheduling."""

    enabled: bool = False
    schedule: str = "weekly"  # daily, weekly, monthly
    inactivity_days: int = 45
    dry_run: bool = True  # Safety first - default to dry-run
    max_projects_per_run: int = 10


class ArchivalScheduler:
    """
    Automatic archival scheduler for periodic project archival.

    Runs scheduled jobs to automatically archive inactive projects based on
    configured inactivity thresholds and schedules.
    """

    def __init__(
        self,
        bulk_manager: BulkArchivalManager,
        config: ArchivalScheduleConfig,
        notification_callback: Optional[Callable[[BulkArchivalResult], None]] = None,
    ):
        """
        Initialize archival scheduler.

        Args:
            bulk_manager: BulkArchivalManager for bulk operations
            config: Schedule configuration
            notification_callback: Optional callback for archival completion notifications
        """
        self.bulk_manager = bulk_manager
        self.config = config
        self.notification_callback = notification_callback

        self.scheduler: Optional[AsyncIOScheduler] = None
        self.is_running = False
        self.last_run: Optional[datetime] = None
        self.last_result: Optional[BulkArchivalResult] = None

    def start(self) -> bool:
        """
        Start the archival scheduler.

        Returns:
            True if started successfully, False if already running or disabled
        """
        if not self.config.enabled:
            logger.info("Archival scheduler is disabled, not starting")
            return False

        if self.is_running:
            logger.warning("Archival scheduler is already running")
            return False

        self.scheduler = AsyncIOScheduler()

        # Determine cron trigger based on schedule
        trigger = self._get_cron_trigger(self.config.schedule)

        # Add archival job
        self.scheduler.add_job(
            self._run_auto_archival,
            trigger=trigger,
            id="auto_archival",
            name="Automatic Project Archival",
            replace_existing=True,
        )

        self.scheduler.start()
        self.is_running = True

        logger.info(
            f"Archival scheduler started: schedule={self.config.schedule}, "
            f"threshold={self.config.inactivity_days}d, dry_run={self.config.dry_run}"
        )

        return True

    def stop(self) -> bool:
        """
        Stop the archival scheduler.

        Returns:
            True if stopped successfully, False if not running
        """
        if not self.is_running or not self.scheduler:
            logger.warning("Archival scheduler is not running")
            return False

        self.scheduler.shutdown(wait=True)
        self.scheduler = None
        self.is_running = False

        logger.info("Archival scheduler stopped")
        return True

    async def trigger_manual_run(self) -> BulkArchivalResult:
        """
        Manually trigger an archival run immediately.

        Returns:
            BulkArchivalResult with operation statistics
        """
        logger.info("Manual archival run triggered")
        return await self._run_auto_archival()

    async def _run_auto_archival(self) -> BulkArchivalResult:
        """
        Execute automatic archival of inactive projects.

        Returns:
            BulkArchivalResult with operation statistics
        """
        self.last_run = datetime.now(UTC)

        logger.info(
            f"Running automatic archival: threshold={self.config.inactivity_days}d, "
            f"max_projects={self.config.max_projects_per_run}, dry_run={self.config.dry_run}"
        )

        try:
            result = await self.bulk_manager.auto_archive_inactive(
                days_threshold=self.config.inactivity_days,
                dry_run=self.config.dry_run,
                max_projects=self.config.max_projects_per_run,
            )

            self.last_result = result

            # Log results
            if self.config.dry_run:
                logger.info(
                    f"[DRY RUN] Would have archived {result.successful} projects "
                    f"(total candidates: {result.total_projects})"
                )
            else:
                logger.info(
                    f"Archived {result.successful} projects "
                    f"(total: {result.total_projects}, failed: {result.failed}, skipped: {result.skipped})"
                )

            # Notify if callback provided
            if self.notification_callback:
                try:
                    self.notification_callback(result)
                except Exception as e:
                    logger.error(f"Error in notification callback: {e}")

            return result

        except Exception as e:
            logger.error(f"Error during automatic archival: {e}")
            # Create error result
            error_result = BulkArchivalResult(
                dry_run=self.config.dry_run,
                total_projects=0,
                successful=0,
                failed=0,
                skipped=0,
                execution_time_seconds=0.0,
                results=[],
                errors=[str(e)],
            )
            self.last_result = error_result
            return error_result

    def _get_cron_trigger(self, schedule: str) -> CronTrigger:
        """
        Get CronTrigger based on schedule string.

        Args:
            schedule: Schedule string (daily, weekly, monthly)

        Returns:
            CronTrigger for the specified schedule
        """
        if schedule == "daily":
            # Run daily at 2 AM
            return CronTrigger(hour=2, minute=0)
        elif schedule == "weekly":
            # Run weekly on Sunday at 2 AM
            return CronTrigger(day_of_week="sun", hour=2, minute=0)
        elif schedule == "monthly":
            # Run monthly on the 1st at 2 AM
            return CronTrigger(day=1, hour=2, minute=0)
        else:
            # Default to weekly
            logger.warning(f"Unknown schedule '{schedule}', defaulting to weekly")
            return CronTrigger(day_of_week="sun", hour=2, minute=0)

    def get_status(self) -> Dict:
        """
        Get scheduler status information.

        Returns:
            Dict with scheduler status details
        """
        next_run = None
        if self.is_running and self.scheduler:
            job = self.scheduler.get_job("auto_archival")
            if job and job.next_run_time:
                next_run = job.next_run_time.isoformat()

        return {
            "enabled": self.config.enabled,
            "running": self.is_running,
            "schedule": self.config.schedule,
            "inactivity_threshold_days": self.config.inactivity_days,
            "dry_run_mode": self.config.dry_run,
            "max_projects_per_run": self.config.max_projects_per_run,
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "next_run": next_run,
            "last_result": {
                "total_projects": self.last_result.total_projects,
                "successful": self.last_result.successful,
                "failed": self.last_result.failed,
                "skipped": self.last_result.skipped,
                "dry_run": self.last_result.dry_run,
            }
            if self.last_result
            else None,
        }

    def update_config(
        self,
        enabled: Optional[bool] = None,
        schedule: Optional[str] = None,
        inactivity_days: Optional[int] = None,
        dry_run: Optional[bool] = None,
        max_projects_per_run: Optional[int] = None,
    ) -> bool:
        """
        Update scheduler configuration.

        Args:
            enabled: Enable/disable scheduler
            schedule: Schedule string (daily, weekly, monthly)
            inactivity_days: Inactivity threshold in days
            dry_run: Enable/disable dry-run mode
            max_projects_per_run: Max projects to archive per run

        Returns:
            True if configuration updated successfully
        """
        restart_needed = False

        if enabled is not None and enabled != self.config.enabled:
            self.config.enabled = enabled
            restart_needed = True

        if schedule is not None and schedule != self.config.schedule:
            self.config.schedule = schedule
            restart_needed = True

        if inactivity_days is not None:
            self.config.inactivity_days = inactivity_days

        if dry_run is not None:
            self.config.dry_run = dry_run

        if max_projects_per_run is not None:
            self.config.max_projects_per_run = max_projects_per_run

        # Restart scheduler if needed
        if restart_needed and self.is_running:
            self.stop()

            # Only restart if still enabled
            if self.config.enabled:
                logger.info("Restarting scheduler with new configuration")
                return self.start()
            else:
                logger.info("Scheduler disabled via config update")
                return True

        logger.info("Scheduler configuration updated")
        return True
