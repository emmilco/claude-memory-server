"""Scheduler for automated health maintenance jobs."""

import asyncio
import logging
from pathlib import Path
from typing import Optional, Dict, Any, Callable
from datetime import datetime, UTC
from dataclasses import dataclass
import json

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from src.memory.health_jobs import HealthMaintenanceJobs, JobResult
from src.memory.lifecycle_manager import LifecycleManager
from src.memory.health_scorer import HealthScorer
from src.store.factory import create_store
from src.config import get_config

logger = logging.getLogger(__name__)


@dataclass
class HealthScheduleConfig:
    """Configuration for health job scheduling."""

    enabled: bool = False
    weekly_archival_enabled: bool = True
    weekly_archival_day: int = 6  # Sunday (0=Monday, 6=Sunday)
    weekly_archival_time: str = "01:00"  # HH:MM format
    weekly_archival_threshold_days: int = 90  # Archive memories older than 90 days

    monthly_cleanup_enabled: bool = True
    monthly_cleanup_day: int = 1  # 1st of month
    monthly_cleanup_time: str = "02:00"
    monthly_cleanup_threshold_days: int = 180  # Delete stale memories older than 180 days

    weekly_report_enabled: bool = True
    weekly_report_day: int = 0  # Monday
    weekly_report_time: str = "09:00"

    notification_callback: Optional[Callable] = None


class HealthJobScheduler:
    """Manages automated health maintenance job scheduling."""

    def __init__(self, config: Optional[HealthScheduleConfig] = None):
        """
        Initialize health job scheduler.

        Args:
            config: Health schedule configuration
        """
        self.config = config or HealthScheduleConfig()
        self.scheduler = AsyncIOScheduler()
        self.is_running = False
        self.health_jobs: Optional[HealthMaintenanceJobs] = None
        self._job_history: list[JobResult] = []

    async def start(self):
        """Start the health job scheduler."""
        if not self.config.enabled:
            logger.info("Health job scheduler is disabled")
            return

        if self.is_running:
            logger.warning("Health job scheduler is already running")
            return

        # Initialize health jobs
        config = get_config()
        store = create_store(config)
        await store.initialize()

        lifecycle_manager = LifecycleManager(store)
        health_scorer = HealthScorer(store)

        self.health_jobs = HealthMaintenanceJobs(
            store=store,
            lifecycle_manager=lifecycle_manager,
            health_scorer=health_scorer,
        )

        # Add jobs based on configuration
        if self.config.weekly_archival_enabled:
            hour, minute = map(int, self.config.weekly_archival_time.split(":"))
            archival_trigger = CronTrigger(
                day_of_week=self.config.weekly_archival_day,
                hour=hour,
                minute=minute,
            )
            self.scheduler.add_job(
                self._run_weekly_archival,
                trigger=archival_trigger,
                id="weekly_archival",
                name="Weekly Memory Archival",
                replace_existing=True,
            )

        if self.config.monthly_cleanup_enabled:
            hour, minute = map(int, self.config.monthly_cleanup_time.split(":"))
            cleanup_trigger = CronTrigger(
                day=self.config.monthly_cleanup_day,
                hour=hour,
                minute=minute,
            )
            self.scheduler.add_job(
                self._run_monthly_cleanup,
                trigger=cleanup_trigger,
                id="monthly_cleanup",
                name="Monthly Stale Memory Cleanup",
                replace_existing=True,
            )

        if self.config.weekly_report_enabled:
            hour, minute = map(int, self.config.weekly_report_time.split(":"))
            report_trigger = CronTrigger(
                day_of_week=self.config.weekly_report_day,
                hour=hour,
                minute=minute,
            )
            self.scheduler.add_job(
                self._run_weekly_report,
                trigger=report_trigger,
                id="weekly_health_report",
                name="Weekly Health Report",
                replace_existing=True,
            )

        self.scheduler.start()
        self.is_running = True

        logger.info("Health job scheduler started with jobs:")
        if self.config.weekly_archival_enabled:
            logger.info(f"  - Weekly archival: Day {self.config.weekly_archival_day} at {self.config.weekly_archival_time}")
        if self.config.monthly_cleanup_enabled:
            logger.info(f"  - Monthly cleanup: Day {self.config.monthly_cleanup_day} at {self.config.monthly_cleanup_time}")
        if self.config.weekly_report_enabled:
            logger.info(f"  - Weekly report: Day {self.config.weekly_report_day} at {self.config.weekly_report_time}")

    async def stop(self):
        """Stop the health job scheduler."""
        if not self.is_running:
            return

        self.scheduler.shutdown(wait=True)
        self.is_running = False

        # Close store
        if self.health_jobs and self.health_jobs.store:
            await self.health_jobs.store.close()

        logger.info("Health job scheduler stopped")

    async def _run_weekly_archival(self):
        """Execute weekly archival job."""
        try:
            logger.info("Starting weekly archival job...")

            result = await self.health_jobs.weekly_archival_job(dry_run=False)
            self._job_history.append(result)

            # Keep only last 100 job results
            if len(self._job_history) > 100:
                self._job_history = self._job_history[-100:]

            logger.info(
                f"Weekly archival completed: {result.memories_archived} memories archived, "
                f"{result.memories_processed} processed"
            )

            # Notify if callback provided
            if self.config.notification_callback:
                await self.config.notification_callback("archival_completed", result.to_dict())

        except Exception as e:
            logger.error(f"Weekly archival job failed: {e}", exc_info=True)

            # Record failure
            result = JobResult(
                job_name="weekly_archival",
                success=False,
                errors=[str(e)],
            )
            self._job_history.append(result)

            if self.config.notification_callback:
                await self.config.notification_callback("archival_failed", result.to_dict())

    async def _run_monthly_cleanup(self):
        """Execute monthly cleanup job."""
        try:
            logger.info("Starting monthly cleanup job...")

            result = await self.health_jobs.monthly_cleanup_job(dry_run=False)
            self._job_history.append(result)

            # Keep only last 100 job results
            if len(self._job_history) > 100:
                self._job_history = self._job_history[-100:]

            logger.info(
                f"Monthly cleanup completed: {result.memories_deleted} memories deleted, "
                f"{result.memories_processed} processed"
            )

            # Notify if callback provided
            if self.config.notification_callback:
                await self.config.notification_callback("cleanup_completed", result.to_dict())

        except Exception as e:
            logger.error(f"Monthly cleanup job failed: {e}", exc_info=True)

            # Record failure
            result = JobResult(
                job_name="monthly_cleanup",
                success=False,
                errors=[str(e)],
            )
            self._job_history.append(result)

            if self.config.notification_callback:
                await self.config.notification_callback("cleanup_failed", result.to_dict())

    async def _run_weekly_report(self):
        """Execute weekly health report job."""
        try:
            logger.info("Starting weekly health report job...")

            result = await self.health_jobs.weekly_health_report_job()
            self._job_history.append(result)

            # Keep only last 100 job results
            if len(self._job_history) > 100:
                self._job_history = self._job_history[-100:]

            logger.info("Weekly health report completed")

            # Notify if callback provided
            if self.config.notification_callback:
                await self.config.notification_callback("report_completed", result.to_dict())

        except Exception as e:
            logger.error(f"Weekly health report job failed: {e}", exc_info=True)

            # Record failure
            result = JobResult(
                job_name="weekly_health_report",
                success=False,
                errors=[str(e)],
            )
            self._job_history.append(result)

            if self.config.notification_callback:
                await self.config.notification_callback("report_failed", result.to_dict())

    async def trigger_archival_now(self, dry_run: bool = False) -> JobResult:
        """Manually trigger archival job immediately."""
        if not self.health_jobs:
            raise RuntimeError("Health jobs not initialized. Start scheduler first.")

        return await self.health_jobs.weekly_archival_job(dry_run=dry_run)

    async def trigger_cleanup_now(self, dry_run: bool = False) -> JobResult:
        """Manually trigger cleanup job immediately."""
        if not self.health_jobs:
            raise RuntimeError("Health jobs not initialized. Start scheduler first.")

        return await self.health_jobs.monthly_cleanup_job(dry_run=dry_run)

    async def trigger_report_now(self) -> JobResult:
        """Manually trigger health report immediately."""
        if not self.health_jobs:
            raise RuntimeError("Health jobs not initialized. Start scheduler first.")

        return await self.health_jobs.weekly_health_report_job()

    def get_status(self) -> Dict[str, Any]:
        """Get scheduler status."""
        jobs_status = {}

        if self.is_running and self.scheduler.get_jobs():
            for job_id in ["weekly_archival", "monthly_cleanup", "weekly_health_report"]:
                job = self.scheduler.get_job(job_id)
                if job:
                    jobs_status[job_id] = {
                        "enabled": True,
                        "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
                    }
                else:
                    jobs_status[job_id] = {"enabled": False}

        return {
            "enabled": self.config.enabled,
            "running": self.is_running,
            "jobs": jobs_status,
            "last_job_results": [r.to_dict() for r in self._job_history[-10:]],  # Last 10 results
        }

    def get_job_history(self, limit: int = 50) -> list[Dict[str, Any]]:
        """Get job execution history."""
        return [r.to_dict() for r in self._job_history[-limit:]]

    async def update_config(self, new_config: HealthScheduleConfig):
        """Update scheduler configuration and restart if running."""
        was_running = self.is_running

        if was_running:
            await self.stop()

        self.config = new_config

        if was_running and new_config.enabled:
            await self.start()

        logger.info("Health job scheduler configuration updated")

    @staticmethod
    def load_config_from_file(config_path: Path) -> HealthScheduleConfig:
        """Load configuration from JSON file."""
        if not config_path.exists():
            return HealthScheduleConfig()

        with open(config_path) as f:
            data = json.load(f)

        return HealthScheduleConfig(**{k: v for k, v in data.items() if k != "notification_callback"})

    @staticmethod
    def save_config_to_file(config: HealthScheduleConfig, config_path: Path):
        """Save configuration to JSON file."""
        config_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "enabled": config.enabled,
            "weekly_archival_enabled": config.weekly_archival_enabled,
            "weekly_archival_day": config.weekly_archival_day,
            "weekly_archival_time": config.weekly_archival_time,
            "weekly_archival_threshold_days": config.weekly_archival_threshold_days,
            "monthly_cleanup_enabled": config.monthly_cleanup_enabled,
            "monthly_cleanup_day": config.monthly_cleanup_day,
            "monthly_cleanup_time": config.monthly_cleanup_time,
            "monthly_cleanup_threshold_days": config.monthly_cleanup_threshold_days,
            "weekly_report_enabled": config.weekly_report_enabled,
            "weekly_report_day": config.weekly_report_day,
            "weekly_report_time": config.weekly_report_time,
        }

        with open(config_path, "w") as f:
            json.dump(data, f, indent=2)

        logger.info(f"Saved health schedule configuration to {config_path}")
