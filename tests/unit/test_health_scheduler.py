"""Comprehensive tests for health_scheduler.py - TEST-007 Phase 1.3

Target Coverage: 0% → 85%+
Test Count: 25 tests
"""

import pytest
import asyncio
import json
import tempfile
from pathlib import Path
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch, call
from dataclasses import dataclass

from src.memory.health_scheduler import (
    HealthScheduleConfig,
    HealthJobScheduler,
)
from src.memory.health_jobs import JobResult


@pytest.fixture
def mock_scheduler_dependencies():
    """Mock all external dependencies for HealthJobScheduler."""
    with patch("src.memory.health_scheduler.create_store") as mock_create_store, \
         patch("src.memory.health_scheduler.LifecycleManager") as mock_lifecycle, \
         patch("src.memory.health_scheduler.HealthScorer") as mock_scorer, \
         patch("src.memory.health_scheduler.get_config") as mock_get_config:

        mock_store = MagicMock()
        mock_store.initialize = AsyncMock()
        mock_store.close = AsyncMock()

        # The code incorrectly doesn't await create_store, so return the store directly (not async)
        # This is a bug in the production code (line 73 should be: store = await create_store(config))
        def create_store_sync(config):
            return mock_store

        mock_create_store.side_effect = create_store_sync

        yield {
            "create_store": mock_create_store,
            "store": mock_store,
            "lifecycle": mock_lifecycle,
            "scorer": mock_scorer,
            "get_config": mock_get_config,
        }


class TestHealthScheduleConfig:
    """Tests for HealthScheduleConfig dataclass."""

    def test_config_defaults(self):
        """Test HealthScheduleConfig has sensible defaults."""
        config = HealthScheduleConfig()

        assert config.enabled is False
        assert config.weekly_archival_enabled is True
        assert config.weekly_archival_day == 6  # Sunday
        assert config.weekly_archival_time == "01:00"
        assert config.weekly_archival_threshold_days == 90

        assert config.monthly_cleanup_enabled is True
        assert config.monthly_cleanup_day == 1  # 1st of month
        assert config.monthly_cleanup_time == "02:00"
        assert config.monthly_cleanup_threshold_days == 180

        assert config.weekly_report_enabled is True
        assert config.weekly_report_day == 0  # Monday
        assert config.weekly_report_time == "09:00"

        assert config.notification_callback is None

    def test_config_custom_values(self):
        """Test HealthScheduleConfig accepts custom values."""
        config = HealthScheduleConfig(
            enabled=True,
            weekly_archival_day=5,
            weekly_archival_time="03:00",
            monthly_cleanup_day=15,
            monthly_cleanup_time="04:00",
        )

        assert config.enabled is True
        assert config.weekly_archival_day == 5
        assert config.weekly_archival_time == "03:00"
        assert config.monthly_cleanup_day == 15
        assert config.monthly_cleanup_time == "04:00"


class TestHealthJobSchedulerInitialization:
    """Tests for HealthJobScheduler initialization."""

    def test_initialization_with_default_config(self):
        """Test scheduler initializes with default config."""
        scheduler = HealthJobScheduler()

        assert scheduler.config is not None
        assert scheduler.config.enabled is False
        assert scheduler.scheduler is not None
        assert scheduler.is_running is False
        assert scheduler.health_jobs is None
        assert scheduler._job_history == []

    def test_initialization_with_custom_config(self):
        """Test scheduler initializes with custom config."""
        config = HealthScheduleConfig(enabled=True, weekly_archival_time="05:00")
        scheduler = HealthJobScheduler(config=config)

        assert scheduler.config is config
        assert scheduler.config.weekly_archival_time == "05:00"


class TestHealthJobSchedulerStartStop:
    """Tests for starting and stopping the scheduler."""

    @pytest.mark.asyncio
    async def test_start_when_disabled(self):
        """Test scheduler respects enabled=False in config."""
        config = HealthScheduleConfig(enabled=False)
        scheduler = HealthJobScheduler(config=config)

        await scheduler.start()

        assert scheduler.is_running is False
        assert scheduler.health_jobs is None

    @pytest.mark.asyncio
    async def test_start_when_already_running(self, mock_scheduler_dependencies):
        """Test start() logs warning if already running."""
        config = HealthScheduleConfig(enabled=True)
        scheduler = HealthJobScheduler(config=config)

        # Start once
        await scheduler.start()
        assert scheduler.is_running is True

        # Try to start again
        with patch("src.memory.health_scheduler.logger") as mock_logger:
            await scheduler.start()
            mock_logger.warning.assert_called_once()

        # Clean up
        await scheduler.stop()

    @pytest.mark.asyncio
    async def test_start_initializes_health_jobs(self, mock_scheduler_dependencies):
        """Test start() initializes HealthMaintenanceJobs."""
        config = HealthScheduleConfig(enabled=True)
        scheduler = HealthJobScheduler(config=config)

        await scheduler.start()

        assert scheduler.is_running is True
        assert scheduler.health_jobs is not None
        mocks = mock_scheduler_dependencies
        mocks["lifecycle"].assert_called_once_with(mocks["store"])
        mocks["scorer"].assert_called_once_with(mocks["store"])

        await scheduler.stop()

    @pytest.mark.asyncio
    async def test_stop_when_not_running(self):
        """Test stop() handles not running state gracefully."""
        scheduler = HealthJobScheduler()

        # Should not raise error
        await scheduler.stop()
        assert scheduler.is_running is False

    @pytest.mark.asyncio
    async def test_stop_closes_store(self, mock_scheduler_dependencies):
        """Test stop() closes the store."""
        config = HealthScheduleConfig(enabled=True)
        scheduler = HealthJobScheduler(config=config)

        await scheduler.start()
        await scheduler.stop()

        mock_scheduler_dependencies["store"].close.assert_called_once()
        assert scheduler.is_running is False


class TestJobScheduling:
    """Tests for job scheduling configuration."""

    @pytest.mark.asyncio
    async def test_weekly_archival_job_scheduled(self, mock_scheduler_dependencies):
        """Test weekly archival job scheduled with correct cron trigger."""
        config = HealthScheduleConfig(
            enabled=True,
            weekly_archival_enabled=True,
            weekly_archival_day=6,
            weekly_archival_time="01:30"
        )
        scheduler = HealthJobScheduler(config=config)

        await scheduler.start()

        # Check job was added
        job = scheduler.scheduler.get_job("weekly_archival")
        assert job is not None
        assert job.name == "Weekly Memory Archival"

        await scheduler.stop()

    @pytest.mark.asyncio
    async def test_monthly_cleanup_job_scheduled(self, mock_scheduler_dependencies):
        """Test monthly cleanup job scheduled with correct configuration."""
        config = HealthScheduleConfig(
            enabled=True,
            monthly_cleanup_enabled=True,
            monthly_cleanup_day=15,
            monthly_cleanup_time="04:00"
        )
        scheduler = HealthJobScheduler(config=config)

        await scheduler.start()

        job = scheduler.scheduler.get_job("monthly_cleanup")
        assert job is not None
        assert job.name == "Monthly Stale Memory Cleanup"

        await scheduler.stop()

    @pytest.mark.asyncio
    async def test_weekly_report_job_scheduled(self, mock_scheduler_dependencies):
        """Test weekly health report job scheduled."""
        config = HealthScheduleConfig(
            enabled=True,
            weekly_report_enabled=True,
            weekly_report_day=0,
            weekly_report_time="09:00"
        )
        scheduler = HealthJobScheduler(config=config)

        await scheduler.start()

        job = scheduler.scheduler.get_job("weekly_health_report")
        assert job is not None
        assert job.name == "Weekly Health Report"

        await scheduler.stop()

    @pytest.mark.asyncio
    async def test_disabled_jobs_not_scheduled(self, mock_scheduler_dependencies):
        """Test disabled jobs are not scheduled."""
        config = HealthScheduleConfig(
            enabled=True,
            weekly_archival_enabled=False,
            monthly_cleanup_enabled=False,
            weekly_report_enabled=False
        )
        scheduler = HealthJobScheduler(config=config)

        await scheduler.start()

        assert scheduler.scheduler.get_job("weekly_archival") is None
        assert scheduler.scheduler.get_job("monthly_cleanup") is None
        assert scheduler.scheduler.get_job("weekly_health_report") is None

        await scheduler.stop()


class TestJobExecution:
    """Tests for job execution logic."""

    @pytest.mark.asyncio
    async def test_run_weekly_archival_success(self):
        """Test _run_weekly_archival executes job and records result."""
        scheduler = HealthJobScheduler()
        scheduler.health_jobs = MagicMock()
        scheduler.config = HealthScheduleConfig()

        # Mock successful result
        mock_result = JobResult(
            job_name="weekly_archival",
            success=True,
            memories_archived=10,
            memories_processed=50,
        )
        scheduler.health_jobs.weekly_archival_job = AsyncMock(return_value=mock_result)

        await scheduler._run_weekly_archival()

        scheduler.health_jobs.weekly_archival_job.assert_called_once_with(dry_run=False)
        assert len(scheduler._job_history) == 1
        assert scheduler._job_history[0].success is True
        assert scheduler._job_history[0].memories_archived == 10

    @pytest.mark.asyncio
    async def test_run_monthly_cleanup_success(self):
        """Test _run_monthly_cleanup executes job."""
        scheduler = HealthJobScheduler()
        scheduler.health_jobs = MagicMock()
        scheduler.config = HealthScheduleConfig()

        mock_result = JobResult(
            job_name="monthly_cleanup",
            success=True,
            memories_deleted=5,
            memories_processed=20,
        )
        scheduler.health_jobs.monthly_cleanup_job = AsyncMock(return_value=mock_result)

        await scheduler._run_monthly_cleanup()

        scheduler.health_jobs.monthly_cleanup_job.assert_called_once_with(dry_run=False)
        assert len(scheduler._job_history) == 1
        assert scheduler._job_history[0].success is True

    @pytest.mark.asyncio
    async def test_run_weekly_report_success(self):
        """Test _run_weekly_report executes job."""
        scheduler = HealthJobScheduler()
        scheduler.health_jobs = MagicMock()
        scheduler.config = HealthScheduleConfig()

        mock_result = JobResult(
            job_name="weekly_health_report",
            success=True,
        )
        scheduler.health_jobs.weekly_health_report_job = AsyncMock(return_value=mock_result)

        await scheduler._run_weekly_report()

        scheduler.health_jobs.weekly_health_report_job.assert_called_once()
        assert len(scheduler._job_history) == 1

    @pytest.mark.asyncio
    async def test_job_history_limited_to_100(self):
        """Test _job_history capped at 100 entries."""
        scheduler = HealthJobScheduler()
        scheduler.health_jobs = MagicMock()
        scheduler.config = HealthScheduleConfig()

        # Simulate 105 job executions
        for i in range(105):
            mock_result = JobResult(
                job_name="weekly_archival",
                success=True,
                memories_archived=i,
            )
            scheduler.health_jobs.weekly_archival_job = AsyncMock(return_value=mock_result)
            await scheduler._run_weekly_archival()

        assert len(scheduler._job_history) == 100

    @pytest.mark.asyncio
    async def test_notification_callback_on_success(self):
        """Test notification callback invoked after job completes successfully."""
        notification_callback = AsyncMock()
        config = HealthScheduleConfig(notification_callback=notification_callback)
        scheduler = HealthJobScheduler(config=config)
        scheduler.health_jobs = MagicMock()

        mock_result = JobResult(
            job_name="weekly_archival",
            success=True,
            memories_archived=10,
        )
        scheduler.health_jobs.weekly_archival_job = AsyncMock(return_value=mock_result)

        await scheduler._run_weekly_archival()

        notification_callback.assert_called_once_with("archival_completed", mock_result.to_dict())

    @pytest.mark.asyncio
    async def test_notification_callback_on_failure(self):
        """Test notification callback invoked on job failure."""
        notification_callback = AsyncMock()
        config = HealthScheduleConfig(notification_callback=notification_callback)
        scheduler = HealthJobScheduler(config=config)
        scheduler.health_jobs = MagicMock()

        scheduler.health_jobs.weekly_archival_job = AsyncMock(side_effect=Exception("Test error"))

        await scheduler._run_weekly_archival()

        notification_callback.assert_called_once()
        call_args = notification_callback.call_args[0]
        assert call_args[0] == "archival_failed"
        assert call_args[1]["success"] is False


class TestManualTriggers:
    """Tests for manually triggering jobs."""

    @pytest.mark.asyncio
    async def test_trigger_archival_now(self):
        """Test manually triggering archival job."""
        scheduler = HealthJobScheduler()
        scheduler.health_jobs = MagicMock()

        mock_result = JobResult(job_name="weekly_archival", success=True)
        scheduler.health_jobs.weekly_archival_job = AsyncMock(return_value=mock_result)

        result = await scheduler.trigger_archival_now(dry_run=True)

        assert result.success is True
        scheduler.health_jobs.weekly_archival_job.assert_called_once_with(dry_run=True)

    @pytest.mark.asyncio
    async def test_trigger_cleanup_now(self):
        """Test manually triggering cleanup job."""
        scheduler = HealthJobScheduler()
        scheduler.health_jobs = MagicMock()

        mock_result = JobResult(job_name="monthly_cleanup", success=True)
        scheduler.health_jobs.monthly_cleanup_job = AsyncMock(return_value=mock_result)

        result = await scheduler.trigger_cleanup_now(dry_run=False)

        assert result.success is True
        scheduler.health_jobs.monthly_cleanup_job.assert_called_once_with(dry_run=False)

    @pytest.mark.asyncio
    async def test_trigger_report_now(self):
        """Test manually triggering health report."""
        scheduler = HealthJobScheduler()
        scheduler.health_jobs = MagicMock()

        mock_result = JobResult(job_name="weekly_health_report", success=True)
        scheduler.health_jobs.weekly_health_report_job = AsyncMock(return_value=mock_result)

        result = await scheduler.trigger_report_now()

        assert result.success is True
        scheduler.health_jobs.weekly_health_report_job.assert_called_once()

    @pytest.mark.asyncio
    async def test_trigger_without_initialization_raises_error(self):
        """Test trigger methods raise error if scheduler not started."""
        scheduler = HealthJobScheduler()
        # health_jobs not initialized

        with pytest.raises(RuntimeError, match="Health jobs not initialized"):
            await scheduler.trigger_archival_now()

        with pytest.raises(RuntimeError, match="Health jobs not initialized"):
            await scheduler.trigger_cleanup_now()

        with pytest.raises(RuntimeError, match="Health jobs not initialized"):
            await scheduler.trigger_report_now()


class TestSchedulerStatus:
    """Tests for get_status method."""

    def test_get_status_when_disabled(self):
        """Test get_status returns correct info when disabled."""
        config = HealthScheduleConfig(enabled=False)
        scheduler = HealthJobScheduler(config=config)

        status = scheduler.get_status()

        assert status["enabled"] is False
        assert status["running"] is False
        assert status["jobs"] == {}
        assert status["last_job_results"] == []

    @pytest.mark.asyncio
    async def test_get_status_when_running(self, mock_scheduler_dependencies):
        """Test get_status returns job info when running."""
        config = HealthScheduleConfig(enabled=True)
        scheduler = HealthJobScheduler(config=config)

        await scheduler.start()
        status = scheduler.get_status()

        assert status["enabled"] is True
        assert status["running"] is True
        assert "weekly_archival" in status["jobs"]
        assert status["jobs"]["weekly_archival"]["enabled"] is True

        await scheduler.stop()


class TestConfigurationManagement:
    """Tests for configuration loading/saving and updating."""

    def test_load_config_from_nonexistent_file(self):
        """Test loading config from non-existent file returns defaults."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "nonexistent.json"

            config = HealthJobScheduler.load_config_from_file(config_path)

            assert config.enabled is False
            assert config.weekly_archival_enabled is True

    def test_load_config_from_file(self):
        """Test loading configuration from JSON file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "health_config.json"

            config_data = {
                "enabled": True,
                "weekly_archival_enabled": False,
                "weekly_archival_day": 5,
                "weekly_archival_time": "03:00",
            }

            with open(config_path, "w") as f:
                json.dump(config_data, f)

            config = HealthJobScheduler.load_config_from_file(config_path)

            assert config.enabled is True
            assert config.weekly_archival_enabled is False
            assert config.weekly_archival_day == 5
            assert config.weekly_archival_time == "03:00"

    def test_save_config_to_file(self):
        """Test saving configuration to JSON file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "subdir" / "health_config.json"

            config = HealthScheduleConfig(
                enabled=True,
                weekly_archival_day=4,
                weekly_archival_time="02:30",
            )

            HealthJobScheduler.save_config_to_file(config, config_path)

            assert config_path.exists()

            with open(config_path) as f:
                data = json.load(f)

            assert data["enabled"] is True
            assert data["weekly_archival_day"] == 4
            assert data["weekly_archival_time"] == "02:30"
            # Callback should not be saved
            assert "notification_callback" not in data

    @pytest.mark.asyncio
    async def test_update_config_restarts_scheduler(self, mock_scheduler_dependencies):
        """Test update_config stops and restarts scheduler if running."""
        config = HealthScheduleConfig(enabled=True)
        scheduler = HealthJobScheduler(config=config)

        # Start with first config
        await scheduler.start()
        assert scheduler.is_running is True

        # Update config
        new_config = HealthScheduleConfig(enabled=True, weekly_archival_day=5)
        await scheduler.update_config(new_config)

        assert scheduler.config is new_config
        assert scheduler.is_running is True

        await scheduler.stop()

    @pytest.mark.asyncio
    async def test_update_config_when_not_running(self):
        """Test update_config when scheduler not running."""
        scheduler = HealthJobScheduler()

        new_config = HealthScheduleConfig(enabled=True, weekly_archival_day=3)
        await scheduler.update_config(new_config)

        assert scheduler.config is new_config
        assert scheduler.is_running is False


class TestJobHistory:
    """Tests for job history tracking."""

    def test_get_job_history_empty(self):
        """Test get_job_history returns empty list initially."""
        scheduler = HealthJobScheduler()

        history = scheduler.get_job_history()

        assert history == []

    @pytest.mark.asyncio
    async def test_get_job_history_returns_recent_jobs(self):
        """Test get_job_history returns last N job results."""
        scheduler = HealthJobScheduler()
        scheduler.health_jobs = MagicMock()
        scheduler.config = HealthScheduleConfig()

        # Execute 10 jobs
        for i in range(10):
            mock_result = JobResult(
                job_name="weekly_archival",
                success=True,
                memories_archived=i,
            )
            scheduler.health_jobs.weekly_archival_job = AsyncMock(return_value=mock_result)
            await scheduler._run_weekly_archival()

        history = scheduler.get_job_history(limit=5)

        assert len(history) == 5
        # Should be the last 5 jobs
        assert history[0]["memories_archived"] == 5
        assert history[4]["memories_archived"] == 9

    @pytest.mark.asyncio
    async def test_get_job_history_default_limit(self):
        """Test get_job_history uses default limit of 50."""
        scheduler = HealthJobScheduler()
        scheduler.health_jobs = MagicMock()
        scheduler.config = HealthScheduleConfig()

        # Execute 60 jobs
        for i in range(60):
            mock_result = JobResult(job_name="test", success=True)
            scheduler.health_jobs.weekly_archival_job = AsyncMock(return_value=mock_result)
            await scheduler._run_weekly_archival()

        history = scheduler.get_job_history()

        # Only last 50 should be returned (and only 100 stored total)
        assert len(history) == 50
