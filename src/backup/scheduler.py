"""Automated backup scheduler with retention policies."""

import asyncio
import logging
import re
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta, UTC
from dataclasses import dataclass
import json

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from src.backup.exporter import DataExporter
from src.store.factory import create_store
from src.config import get_config

logger = logging.getLogger(__name__)


@dataclass
class BackupScheduleConfig:
    """Configuration for backup scheduling."""

    enabled: bool = False
    frequency: str = "daily"  # daily, weekly, monthly, hourly
    time: str = "02:00"  # For daily/weekly/monthly (HH:MM format)
    day_of_week: int = 0  # For weekly (0=Monday, 6=Sunday)
    day_of_month: int = 1  # For monthly (1-31)
    retention_days: int = 30  # Keep backups for N days
    max_backups: int = 10  # Maximum number of backups to keep
    backup_format: str = "archive"  # archive or json
    backup_dir: Optional[str] = None  # Custom backup directory
    notification_callback: Optional[Any] = None


class BackupScheduler:
    """Manages automated backup scheduling and retention."""

    def __init__(self, config: Optional[BackupScheduleConfig] = None):
        """
        Initialize backup scheduler.

        Args:
            config: Backup schedule configuration
        """
        self.config = config or BackupScheduleConfig()
        self.scheduler = AsyncIOScheduler()
        self.is_running = False
        self._last_backup_time: Optional[datetime] = None
        self._last_backup_path: Optional[Path] = None

    async def start(self):
        """Start the backup scheduler."""
        if not self.config.enabled:
            logger.info("Backup scheduler is disabled")
            return

        if self.is_running:
            logger.warning("Backup scheduler is already running")
            return

        # Add backup job based on frequency
        trigger = self._create_trigger()
        self.scheduler.add_job(
            self._run_backup_job,
            trigger=trigger,
            id="automated_backup",
            name="Automated Backup",
            replace_existing=True,
        )

        # Add cleanup job (runs daily at 3 AM)
        cleanup_trigger = CronTrigger(hour=3, minute=0)
        self.scheduler.add_job(
            self._run_cleanup_job,
            trigger=cleanup_trigger,
            id="backup_cleanup",
            name="Backup Cleanup",
            replace_existing=True,
        )

        self.scheduler.start()
        self.is_running = True

        logger.info(
            f"Backup scheduler started - {self.config.frequency} backups "
            f"with {self.config.retention_days} day retention"
        )

    async def stop(self):
        """Stop the backup scheduler."""
        if not self.is_running:
            return

        self.scheduler.shutdown(wait=True)
        self.is_running = False
        logger.info("Backup scheduler stopped")

    def _create_trigger(self):
        """Create APScheduler trigger based on frequency."""
        if self.config.frequency == "hourly":
            return IntervalTrigger(hours=1)

        # Validate time format for non-hourly frequencies
        if self.config.frequency in ("daily", "weekly", "monthly"):
            if not re.match(r'^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$', self.config.time):
                raise ValueError(
                    f"Invalid time format: '{self.config.time}'. "
                    f"Expected HH:MM format (00:00-23:59)"
                )

        if self.config.frequency == "daily":
            hour, minute = map(int, self.config.time.split(":"))
            return CronTrigger(hour=hour, minute=minute)

        elif self.config.frequency == "weekly":
            hour, minute = map(int, self.config.time.split(":"))
            return CronTrigger(
                day_of_week=self.config.day_of_week,
                hour=hour,
                minute=minute,
            )

        elif self.config.frequency == "monthly":
            hour, minute = map(int, self.config.time.split(":"))
            return CronTrigger(
                day=self.config.day_of_month,
                hour=hour,
                minute=minute,
            )

        else:
            raise ValueError(f"Invalid frequency: {self.config.frequency}")

    async def _run_backup_job(self):
        """Execute scheduled backup."""
        try:
            logger.info("Starting scheduled backup...")

            # Determine backup directory
            if self.config.backup_dir:
                backup_dir = Path(self.config.backup_dir).expanduser()
            else:
                config = get_config()
                backup_dir = config.data_dir / "backups"

            backup_dir.mkdir(parents=True, exist_ok=True)

            # Generate backup filename
            timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
            if self.config.backup_format == "archive":
                filename = f"auto_backup_{timestamp}.tar.gz"
            else:
                filename = f"auto_backup_{timestamp}.json"

            backup_path = backup_dir / filename

            # Create backup
            config = get_config()
            store = create_store(config)
            await store.initialize()

            exporter = DataExporter(store)

            if self.config.backup_format == "archive":
                stats = await exporter.create_portable_archive(
                    output_path=backup_path,
                )
            else:
                stats = await exporter.export_to_json(
                    output_path=backup_path,
                )

            await store.close()

            self._last_backup_time = datetime.now(UTC)
            self._last_backup_path = backup_path

            logger.info(
                f"Scheduled backup completed: {backup_path} "
                f"({stats.get('total_memories', 0)} memories)"
            )

            # Notify if callback provided
            if self.config.notification_callback:
                await self.config.notification_callback(
                    "backup_completed",
                    {
                        "path": str(backup_path),
                        "stats": stats,
                        "timestamp": self._last_backup_time.isoformat(),
                    },
                )

        except Exception as e:
            logger.error(f"Scheduled backup failed: {e}", exc_info=True)

            # Notify of failure
            if self.config.notification_callback:
                await self.config.notification_callback(
                    "backup_failed",
                    {"error": str(e), "timestamp": datetime.now(UTC).isoformat()},
                )

    async def _run_cleanup_job(self):
        """Execute backup cleanup based on retention policies."""
        try:
            logger.info("Starting backup cleanup...")

            # Determine backup directory
            if self.config.backup_dir:
                backup_dir = Path(self.config.backup_dir).expanduser()
            else:
                config = get_config()
                backup_dir = config.data_dir / "backups"

            if not backup_dir.exists():
                logger.info("Backup directory doesn't exist, skipping cleanup")
                return

            # Get all backup files
            backup_files = []
            for pattern in ["auto_backup_*.tar.gz", "auto_backup_*.json"]:
                backup_files.extend(backup_dir.glob(pattern))

            if not backup_files:
                logger.info("No automated backups found, skipping cleanup")
                return

            # Sort by modification time (newest first)
            backup_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)

            deleted_count = 0
            cutoff_date = datetime.now(UTC) - timedelta(days=self.config.retention_days)

            # Apply retention policies
            for i, backup_file in enumerate(backup_files):
                file_time = datetime.fromtimestamp(backup_file.stat().st_mtime, tz=UTC)

                # Delete if:
                # 1. Exceeds max_backups count (keep newest N)
                # 2. Older than retention_days
                should_delete = (
                    i >= self.config.max_backups or file_time < cutoff_date
                )

                if should_delete:
                    logger.info(f"Deleting old backup: {backup_file.name}")
                    backup_file.unlink()
                    deleted_count += 1

            logger.info(
                f"Backup cleanup completed: deleted {deleted_count} old backups, "
                f"kept {len(backup_files) - deleted_count}"
            )

            # Notify if callback provided
            if self.config.notification_callback:
                await self.config.notification_callback(
                    "cleanup_completed",
                    {
                        "deleted_count": deleted_count,
                        "remaining_count": len(backup_files) - deleted_count,
                        "timestamp": datetime.now(UTC).isoformat(),
                    },
                )

        except Exception as e:
            logger.error(f"Backup cleanup failed: {e}", exc_info=True)

    async def trigger_backup_now(self) -> Dict[str, Any]:
        """Manually trigger a backup immediately."""
        await self._run_backup_job()

        return {
            "status": "success",
            "backup_path": str(self._last_backup_path) if self._last_backup_path else None,
            "backup_time": self._last_backup_time.isoformat() if self._last_backup_time else None,
        }

    async def trigger_cleanup_now(self) -> Dict[str, Any]:
        """Manually trigger cleanup immediately."""
        await self._run_cleanup_job()

        return {
            "status": "success",
            "timestamp": datetime.now(UTC).isoformat(),
        }

    def get_status(self) -> Dict[str, Any]:
        """Get scheduler status."""
        next_run = None
        if self.is_running and self.scheduler.get_jobs():
            backup_job = self.scheduler.get_job("automated_backup")
            if backup_job:
                next_run = backup_job.next_run_time

        return {
            "enabled": self.config.enabled,
            "running": self.is_running,
            "frequency": self.config.frequency,
            "retention_days": self.config.retention_days,
            "max_backups": self.config.max_backups,
            "next_backup": next_run.isoformat() if next_run else None,
            "last_backup": self._last_backup_time.isoformat() if self._last_backup_time else None,
            "last_backup_path": str(self._last_backup_path) if self._last_backup_path else None,
        }

    async def update_config(self, new_config: BackupScheduleConfig):
        """Update scheduler configuration and restart if running."""
        was_running = self.is_running

        if was_running:
            await self.stop()

        self.config = new_config

        if was_running and new_config.enabled:
            await self.start()

        logger.info("Backup scheduler configuration updated")

    @staticmethod
    def load_config_from_file(config_path: Path) -> BackupScheduleConfig:
        """Load configuration from JSON file."""
        if not config_path.exists():
            return BackupScheduleConfig()

        with open(config_path) as f:
            data = json.load(f)

        return BackupScheduleConfig(**data)

    @staticmethod
    def save_config_to_file(config: BackupScheduleConfig, config_path: Path):
        """Save configuration to JSON file."""
        config_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "enabled": config.enabled,
            "frequency": config.frequency,
            "time": config.time,
            "day_of_week": config.day_of_week,
            "day_of_month": config.day_of_month,
            "retention_days": config.retention_days,
            "max_backups": config.max_backups,
            "backup_format": config.backup_format,
            "backup_dir": config.backup_dir,
        }

        with open(config_path, "w") as f:
            json.dump(data, f, indent=2)

        logger.info(f"Saved backup schedule configuration to {config_path}")
