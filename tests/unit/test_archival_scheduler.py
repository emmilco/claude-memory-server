"""
Unit tests for automatic archival scheduler.

Tests scheduler initialization, job execution, configuration updates, and status reporting.
"""

import pytest
import tempfile
from pathlib import Path
from datetime import datetime, UTC, timedelta
from unittest.mock import AsyncMock

from src.memory.archival_scheduler import (
    ArchivalScheduler,
    ArchivalScheduleConfig,
)
from src.memory.bulk_archival import BulkArchivalManager, BulkArchivalResult
from src.memory.project_archival import ProjectArchivalManager, ProjectState
from src.memory.archive_compressor import ArchiveCompressor


@pytest.fixture
def temp_dirs():
    """Create temporary directories for testing."""
    temp_root = Path(tempfile.mkdtemp())
    state_file = temp_root / "project_states.json"
    archive_root = temp_root / "archives"

    yield {
        "state_file": state_file,
        "archive_root": archive_root,
    }


@pytest.fixture
def archival_manager(temp_dirs):
    """Create a ProjectArchivalManager instance."""
    return ProjectArchivalManager(
        state_file_path=str(temp_dirs["state_file"]),
        inactivity_threshold_days=45,
    )


@pytest.fixture
def compressor(temp_dirs):
    """Create an ArchiveCompressor instance."""
    return ArchiveCompressor(
        archive_root=str(temp_dirs["archive_root"]),
        compression_level=6,
    )


@pytest.fixture
def bulk_manager(archival_manager, compressor):
    """Create a BulkArchivalManager instance."""
    return BulkArchivalManager(
        archival_manager=archival_manager,
        archive_compressor=compressor,
        max_projects_per_operation=20,
    )


@pytest.fixture
def schedule_config():
    """Create a default schedule configuration."""
    return ArchivalScheduleConfig(
        enabled=True,
        schedule="weekly",
        inactivity_days=45,
        dry_run=True,
        max_projects_per_run=10,
    )


@pytest.fixture
def scheduler(bulk_manager, schedule_config):
    """Create an ArchivalScheduler instance."""
    return ArchivalScheduler(
        bulk_manager=bulk_manager,
        config=schedule_config,
    )


class TestArchivalScheduleConfig:
    """Test ArchivalScheduleConfig dataclass."""

    def test_default_values(self):
        """Test default configuration values."""
        config = ArchivalScheduleConfig()

        assert config.enabled is False
        assert config.schedule == "weekly"
        assert config.inactivity_days == 45
        assert config.dry_run is True
        assert config.max_projects_per_run == 10

    def test_custom_values(self):
        """Test custom configuration values."""
        config = ArchivalScheduleConfig(
            enabled=True,
            schedule="daily",
            inactivity_days=30,
            dry_run=False,
            max_projects_per_run=5,
        )

        assert config.enabled is True
        assert config.schedule == "daily"
        assert config.inactivity_days == 30
        assert config.dry_run is False
        assert config.max_projects_per_run == 5


class TestArchivalScheduler:
    """Test ArchivalScheduler functionality."""

    def test_initialization(self, scheduler, bulk_manager, schedule_config):
        """Test scheduler initialization."""
        assert scheduler.bulk_manager == bulk_manager
        assert scheduler.config == schedule_config
        assert scheduler.scheduler is None
        assert scheduler.is_running is False
        assert scheduler.last_run is None
        assert scheduler.last_result is None

    def test_start_disabled(self, scheduler):
        """Test starting scheduler when disabled."""
        scheduler.config.enabled = False

        result = scheduler.start()

        assert result is False
        assert scheduler.is_running is False
        assert scheduler.scheduler is None

    @pytest.mark.asyncio
    async def test_start_enabled(self, scheduler):
        """Test starting scheduler when enabled."""
        result = scheduler.start()

        assert result is True
        assert scheduler.is_running is True
        assert scheduler.scheduler is not None

        # Cleanup
        scheduler.stop()

    @pytest.mark.asyncio
    async def test_start_already_running(self, scheduler):
        """Test starting scheduler when already running."""
        scheduler.start()

        # Try to start again
        result = scheduler.start()

        assert result is False
        assert scheduler.is_running is True

        # Cleanup
        scheduler.stop()

    @pytest.mark.asyncio
    async def test_stop(self, scheduler):
        """Test stopping scheduler."""
        scheduler.start()
        assert scheduler.is_running is True

        result = scheduler.stop()

        assert result is True
        assert scheduler.is_running is False
        assert scheduler.scheduler is None

    def test_stop_not_running(self, scheduler):
        """Test stopping scheduler when not running."""
        result = scheduler.stop()

        assert result is False
        assert scheduler.is_running is False

    @pytest.mark.asyncio
    async def test_manual_trigger(self, scheduler, archival_manager):
        """Test manual archival run trigger."""
        # Add some inactive projects
        for i in range(3):
            project_name = f"inactive-project-{i}"
            archival_manager.project_states[project_name] = {
                "state": ProjectState.ACTIVE.value,
                "created_at": (datetime.now(UTC) - timedelta(days=100)).isoformat(),
                "last_activity": (
                    datetime.now(UTC) - timedelta(days=60 + i)
                ).isoformat(),
                "files_indexed": 100,
                "searches_count": 50,
            }
        archival_manager._save_states()

        result = await scheduler.trigger_manual_run()

        assert result.dry_run is True  # Default config has dry_run=True
        assert result.total_projects == 3
        assert result.successful == 3
        assert scheduler.last_run is not None
        assert scheduler.last_result == result

    @pytest.mark.asyncio
    async def test_auto_archival_execution(self, scheduler, archival_manager):
        """Test automatic archival execution."""
        # Add inactive projects
        for i in range(5):
            project_name = f"inactive-project-{i}"
            archival_manager.project_states[project_name] = {
                "state": ProjectState.ACTIVE.value,
                "created_at": (datetime.now(UTC) - timedelta(days=100)).isoformat(),
                "last_activity": (
                    datetime.now(UTC) - timedelta(days=50 + i)
                ).isoformat(),
                "files_indexed": 100,
                "searches_count": 50,
            }
        archival_manager._save_states()

        result = await scheduler._run_auto_archival()

        assert result.dry_run is True
        assert result.total_projects == 5
        assert result.successful == 5
        assert scheduler.last_run is not None
        assert scheduler.last_result == result

    @pytest.mark.asyncio
    async def test_auto_archival_with_notification_callback(
        self, bulk_manager, schedule_config
    ):
        """Test archival with notification callback."""
        callback_called = []

        def notification_callback(result: BulkArchivalResult):
            callback_called.append(result)

        scheduler = ArchivalScheduler(
            bulk_manager=bulk_manager,
            config=schedule_config,
            notification_callback=notification_callback,
        )

        result = await scheduler.trigger_manual_run()

        assert len(callback_called) == 1
        assert callback_called[0] == result

    @pytest.mark.asyncio
    async def test_auto_archival_error_handling(self, scheduler):
        """Test error handling during auto-archival."""
        # Mock bulk_manager to raise exception
        scheduler.bulk_manager.auto_archive_inactive = AsyncMock(
            side_effect=Exception("Test error")
        )

        result = await scheduler._run_auto_archival()

        assert result.dry_run == scheduler.config.dry_run
        assert result.total_projects == 0
        assert result.successful == 0
        assert len(result.errors) > 0
        assert "Test error" in result.errors[0]

    def test_get_cron_trigger_daily(self, scheduler):
        """Test cron trigger for daily schedule."""
        trigger = scheduler._get_cron_trigger("daily")

        # Check that it's configured for daily runs (hour=2, minute=0)
        hour_field = next(f for f in trigger.fields if f.name == "hour")
        minute_field = next(f for f in trigger.fields if f.name == "minute")
        assert str(hour_field) == "2"
        assert str(minute_field) == "0"

    def test_get_cron_trigger_weekly(self, scheduler):
        """Test cron trigger for weekly schedule."""
        trigger = scheduler._get_cron_trigger("weekly")

        # Check that it's configured for weekly runs (Sunday)
        dow_field = next(f for f in trigger.fields if f.name == "day_of_week")
        assert str(dow_field) == "sun"

    def test_get_cron_trigger_monthly(self, scheduler):
        """Test cron trigger for monthly schedule."""
        trigger = scheduler._get_cron_trigger("monthly")

        # Check that it's configured for monthly runs (day=1)
        day_field = next(f for f in trigger.fields if f.name == "day")
        assert str(day_field) == "1"

    def test_get_cron_trigger_unknown(self, scheduler):
        """Test cron trigger for unknown schedule defaults to weekly."""
        trigger = scheduler._get_cron_trigger("unknown")

        # Should default to weekly
        assert trigger.fields[4].name == "day_of_week"
        assert str(trigger.fields[4]) == "sun"

    def test_get_status_not_running(self, scheduler):
        """Test getting status when scheduler is not running."""
        status = scheduler.get_status()

        assert status["enabled"] is True
        assert status["running"] is False
        assert status["schedule"] == "weekly"
        assert status["inactivity_threshold_days"] == 45
        assert status["dry_run_mode"] is True
        assert status["max_projects_per_run"] == 10
        assert status["last_run"] is None
        assert status["next_run"] is None
        assert status["last_result"] is None

    @pytest.mark.asyncio
    async def test_get_status_running(self, scheduler):
        """Test getting status when scheduler is running."""
        scheduler.start()

        status = scheduler.get_status()

        assert status["enabled"] is True
        assert status["running"] is True
        assert status["next_run"] is not None  # Should have next run time

        # Cleanup
        scheduler.stop()

    @pytest.mark.asyncio
    async def test_get_status_with_last_result(self, scheduler):
        """Test getting status after a run."""
        await scheduler.trigger_manual_run()

        status = scheduler.get_status()

        assert status["last_run"] is not None
        assert status["last_result"] is not None
        assert status["last_result"]["dry_run"] is True

    def test_update_config_simple_changes(self, scheduler):
        """Test updating configuration without restart."""
        result = scheduler.update_config(
            inactivity_days=60,
            dry_run=False,
            max_projects_per_run=15,
        )

        assert result is True
        assert scheduler.config.inactivity_days == 60
        assert scheduler.config.dry_run is False
        assert scheduler.config.max_projects_per_run == 15

    @pytest.mark.asyncio
    async def test_update_config_with_restart(self, scheduler):
        """Test updating configuration that requires restart."""
        scheduler.start()
        assert scheduler.is_running is True

        result = scheduler.update_config(schedule="daily")

        assert result is True
        assert scheduler.config.schedule == "daily"
        assert scheduler.is_running is True  # Should still be running after restart

        # Cleanup
        scheduler.stop()

    @pytest.mark.asyncio
    async def test_update_config_enable_disable(self, scheduler):
        """Test enabling/disabling scheduler via config update."""
        # Start enabled
        scheduler.start()
        assert scheduler.is_running is True

        # Disable
        result = scheduler.update_config(enabled=False)

        assert result is True
        assert scheduler.config.enabled is False
        assert scheduler.is_running is False  # Should have stopped

    @pytest.mark.asyncio
    async def test_notification_callback_error_handling(
        self, bulk_manager, schedule_config
    ):
        """Test that callback errors don't break archival."""

        def bad_callback(result):
            raise Exception("Callback error")

        scheduler = ArchivalScheduler(
            bulk_manager=bulk_manager,
            config=schedule_config,
            notification_callback=bad_callback,
        )

        # Should not raise, even though callback fails
        result = await scheduler.trigger_manual_run()

        assert result is not None  # Archival should complete
        assert scheduler.last_result is not None
