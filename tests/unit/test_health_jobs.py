"""Tests for health maintenance jobs."""

import pytest
from datetime import datetime, UTC, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from src.memory.health_jobs import HealthMaintenanceJobs, JobResult
from src.memory.lifecycle_manager import LifecycleManager
from src.memory.health_scorer import HealthScorer
from src.core.models import LifecycleState, ContextLevel, MemoryUnit


class TestJobResult:
    """Test suite for JobResult dataclass."""

    def test_job_result_initialization(self):
        """Test JobResult initialization with defaults."""
        result = JobResult(
            job_name="test_job",
            success=True,
        )

        assert result.job_name == "test_job"
        assert result.success is True
        assert result.memories_processed == 0
        assert result.memories_archived == 0
        assert result.memories_deleted == 0
        assert result.errors == []
        assert isinstance(result.timestamp, datetime)

    def test_job_result_to_dict(self):
        """Test JobResult serialization to dictionary."""
        result = JobResult(
            job_name="test_job",
            success=True,
            memories_processed=10,
            memories_archived=5,
            memories_deleted=2,
            errors=["error1", "error2"],
        )

        result_dict = result.to_dict()

        assert result_dict["job_name"] == "test_job"
        assert result_dict["success"] is True
        assert result_dict["memories_processed"] == 10
        assert result_dict["memories_archived"] == 5
        assert result_dict["memories_deleted"] == 2
        assert result_dict["error_count"] == 2
        assert len(result_dict["errors"]) == 2
        assert "timestamp" in result_dict

    def test_job_result_error_limiting(self):
        """Test that to_dict limits errors to first 10."""
        errors = [f"error{i}" for i in range(15)]
        result = JobResult(
            job_name="test_job",
            success=False,
            errors=errors,
        )

        result_dict = result.to_dict()

        assert result_dict["error_count"] == 15
        assert len(result_dict["errors"]) == 10  # Limited to first 10


class TestHealthMaintenanceJobs:
    """Test suite for HealthMaintenanceJobs."""

    @pytest.fixture
    def mock_store(self):
        """Create a mock memory store."""
        store = AsyncMock()
        return store

    @pytest.fixture
    def lifecycle_manager(self):
        """Create a lifecycle manager instance."""
        return LifecycleManager()

    @pytest.fixture
    def health_scorer(self, mock_store):
        """Create a health scorer instance."""
        return HealthScorer(mock_store)

    @pytest.fixture
    def jobs(self, mock_store, lifecycle_manager, health_scorer):
        """Create a health maintenance jobs instance."""
        return HealthMaintenanceJobs(mock_store, lifecycle_manager, health_scorer)

    @pytest.mark.asyncio
    async def test_weekly_archival_job_dry_run_empty(self, jobs, mock_store):
        """Test weekly archival job with dry run on empty database."""
        mock_store.get_all_memories = AsyncMock(return_value=[])

        result = await jobs.weekly_archival_job(dry_run=True)

        assert result.success is True
        assert result.memories_processed == 0
        assert result.memories_archived == 0
        assert len(result.errors) == 0
        assert result.job_name == "weekly_archival"

    @pytest.mark.asyncio
    async def test_weekly_archival_job_dry_run_with_candidates(self, jobs, mock_store):
        """Test weekly archival job with dry run finds candidates."""
        # Create memories that should be archived
        memories = []

        # 5 old ACTIVE memories (should be archived)
        for i in range(5):
            mem = {
                'id': f"old-active-{i}",
                'lifecycle_state': LifecycleState.ACTIVE,
                'content': f"Old content {i}",
                'created_at': datetime.now(UTC) - timedelta(days=200),
                'last_accessed': datetime.now(UTC) - timedelta(days=190),
                'use_count': 0,
                'context_level': ContextLevel.SESSION_STATE,
            }
            memories.append(mem)

        # 3 recent ACTIVE memories (should NOT be archived)
        for i in range(3):
            mem = {
                'id': f"recent-active-{i}",
                'lifecycle_state': LifecycleState.ACTIVE,
                'content': f"Recent content {i}",
                'created_at': datetime.now(UTC) - timedelta(days=3),
                'last_accessed': datetime.now(UTC) - timedelta(days=1),
                'use_count': 5,
                'context_level': ContextLevel.SESSION_STATE,
            }
            memories.append(mem)

        mock_store.get_all_memories = AsyncMock(return_value=memories)

        result = await jobs.weekly_archival_job(dry_run=True)

        assert result.success is True
        assert result.memories_processed == 5  # Only old memories
        assert result.memories_archived == 5
        assert len(result.errors) == 0

    @pytest.mark.asyncio
    async def test_weekly_archival_job_execution(self, jobs, mock_store):
        """Test weekly archival job execution (not dry run)."""
        # Create old ACTIVE memories
        memories = []
        for i in range(3):
            mem = {
                'id': f"old-{i}",
                'lifecycle_state': LifecycleState.ACTIVE,
                'content': f"Old content {i}",
                'created_at': datetime.now(UTC) - timedelta(days=200),
                'last_accessed': datetime.now(UTC) - timedelta(days=190),
                'use_count': 0,
                'context_level': ContextLevel.SESSION_STATE,
            }
            memories.append(mem)

        mock_store.get_all_memories = AsyncMock(return_value=memories)
        mock_store.update_lifecycle_state = AsyncMock(return_value=True)

        result = await jobs.weekly_archival_job(dry_run=False)

        assert result.success is True
        assert result.memories_processed == 3
        assert result.memories_archived == 3
        assert len(result.errors) == 0

        # Verify update_lifecycle_state was called
        assert mock_store.update_lifecycle_state.call_count == 3

    @pytest.mark.asyncio
    async def test_weekly_archival_job_skip_already_archived(self, jobs, mock_store):
        """Test that archival job skips already ARCHIVED/STALE memories."""
        memories = []

        # Already ARCHIVED
        mem = {
            'id': "already-archived",
            'lifecycle_state': LifecycleState.ARCHIVED,
            'content': "Archived content",
            'created_at': datetime.now(UTC) - timedelta(days=200),
        }
        memories.append(mem)

        # Already STALE
        mem = {
            'id': "already-stale",
            'lifecycle_state': LifecycleState.STALE,
            'content': "Stale content",
            'created_at': datetime.now(UTC) - timedelta(days=300),
        }
        memories.append(mem)

        mock_store.get_all_memories = AsyncMock(return_value=memories)

        result = await jobs.weekly_archival_job(dry_run=True)

        assert result.success is True
        assert result.memories_processed == 0  # Should skip both
        assert result.memories_archived == 0

    @pytest.mark.asyncio
    async def test_weekly_archival_job_error_handling(self, jobs, mock_store):
        """Test weekly archival job error handling."""
        # Create one old memory
        mem = {
            'id': "old-mem",
            'lifecycle_state': LifecycleState.ACTIVE,
            'content': "Old content",
            'created_at': datetime.now(UTC) - timedelta(days=200),
            'last_accessed': datetime.now(UTC) - timedelta(days=190),
            'use_count': 0,
            'context_level': ContextLevel.SESSION_STATE,
        }

        mock_store.get_all_memories = AsyncMock(return_value=[mem])
        mock_store.update_lifecycle_state = AsyncMock(
            side_effect=Exception("Database error")
        )

        result = await jobs.weekly_archival_job(dry_run=False)

        assert result.success is True  # Overall success even with individual errors
        assert result.memories_processed == 1
        assert result.memories_archived == 0
        assert len(result.errors) == 1
        assert "Database error" in result.errors[0]

    @pytest.mark.asyncio
    async def test_monthly_cleanup_job_dry_run_empty(self, jobs, mock_store):
        """Test monthly cleanup job with dry run on empty database."""
        mock_store.get_all_memories = AsyncMock(return_value=[])

        result = await jobs.monthly_cleanup_job(dry_run=True)

        assert result.success is True
        assert result.memories_processed == 0
        assert result.memories_deleted == 0
        assert len(result.errors) == 0
        assert result.job_name == "monthly_cleanup"

    @pytest.mark.asyncio
    async def test_monthly_cleanup_job_dry_run_with_candidates(self, jobs, mock_store):
        """Test monthly cleanup job with dry run finds candidates."""
        memories = []

        # 5 old STALE memories with low usage (should be deleted)
        for i in range(5):
            mem = {
                'id': f"stale-{i}",
                'lifecycle_state': LifecycleState.STALE,
                'content': f"Stale content {i}",
                'created_at': datetime.now(UTC) - timedelta(days=200),
                'use_count': 1,
                'context_level': ContextLevel.SESSION_STATE,
            }
            memories.append(mem)

        # 2 old STALE memories with high usage (should NOT be deleted)
        for i in range(2):
            mem = {
                'id': f"stale-used-{i}",
                'lifecycle_state': LifecycleState.STALE,
                'content': f"Used content {i}",
                'created_at': datetime.now(UTC) - timedelta(days=200),
                'use_count': 10,
                'context_level': ContextLevel.SESSION_STATE,
            }
            memories.append(mem)

        # 1 old STALE USER_PREFERENCE (should NOT be deleted)
        mem = {
            'id': "stale-pref",
            'lifecycle_state': LifecycleState.STALE,
            'content': "Preference",
            'created_at': datetime.now(UTC) - timedelta(days=200),
            'use_count': 0,
            'context_level': ContextLevel.USER_PREFERENCE,
        }
        memories.append(mem)

        mock_store.get_all_memories = AsyncMock(return_value=memories)

        result = await jobs.monthly_cleanup_job(dry_run=True)

        assert result.success is True
        assert result.memories_processed == 5  # Only low-usage STALE
        assert result.memories_deleted == 5
        assert len(result.errors) == 0

    @pytest.mark.asyncio
    async def test_monthly_cleanup_job_execution(self, jobs, mock_store):
        """Test monthly cleanup job execution (not dry run)."""
        # Create old STALE memories
        memories = []
        for i in range(3):
            mem = {
                'id': f"stale-{i}",
                'lifecycle_state': LifecycleState.STALE,
                'content': f"Stale content {i}",
                'created_at': datetime.now(UTC) - timedelta(days=200),
                'use_count': 1,
                'context_level': ContextLevel.SESSION_STATE,
            }
            memories.append(mem)

        mock_store.get_all_memories = AsyncMock(return_value=memories)
        mock_store.delete_memory = AsyncMock(return_value=True)

        result = await jobs.monthly_cleanup_job(dry_run=False)

        assert result.success is True
        assert result.memories_processed == 3
        assert result.memories_deleted == 3
        assert len(result.errors) == 0

        # Verify delete_memory was called
        assert mock_store.delete_memory.call_count == 3

    @pytest.mark.asyncio
    async def test_monthly_cleanup_job_min_age_filter(self, jobs, mock_store):
        """Test monthly cleanup job respects min_age_days parameter."""
        memories = []

        # STALE memory older than min_age (should be deleted)
        mem = {
            'id': "old-stale",
            'lifecycle_state': LifecycleState.STALE,
            'content': "Old stale",
            'created_at': datetime.now(UTC) - timedelta(days=200),
            'use_count': 1,
            'context_level': ContextLevel.SESSION_STATE,
        }
        memories.append(mem)

        # STALE memory younger than min_age (should NOT be deleted)
        mem = {
            'id': "young-stale",
            'lifecycle_state': LifecycleState.STALE,
            'content': "Young stale",
            'created_at': datetime.now(UTC) - timedelta(days=100),
            'use_count': 1,
            'context_level': ContextLevel.SESSION_STATE,
        }
        memories.append(mem)

        mock_store.get_all_memories = AsyncMock(return_value=memories)

        result = await jobs.monthly_cleanup_job(dry_run=True, min_age_days=180)

        assert result.success is True
        assert result.memories_processed == 1  # Only the old one
        assert result.memories_deleted == 1

    @pytest.mark.asyncio
    async def test_monthly_cleanup_job_error_handling(self, jobs, mock_store):
        """Test monthly cleanup job error handling."""
        # Create one STALE memory
        mem = {
            'id': "stale-mem",
            'lifecycle_state': LifecycleState.STALE,
            'content': "Stale content",
            'created_at': datetime.now(UTC) - timedelta(days=200),
            'use_count': 1,
            'context_level': ContextLevel.SESSION_STATE,
        }

        mock_store.get_all_memories = AsyncMock(return_value=[mem])
        mock_store.delete_memory = AsyncMock(side_effect=Exception("Delete error"))

        result = await jobs.monthly_cleanup_job(dry_run=False)

        assert result.success is True  # Overall success even with individual errors
        assert result.memories_processed == 1
        assert result.memories_deleted == 0
        assert len(result.errors) == 1
        assert "Delete error" in result.errors[0]

    @pytest.mark.asyncio
    async def test_weekly_health_report_job(self, jobs, mock_store, health_scorer):
        """Test weekly health report job."""
        # Mock get_all_memories for health scorer
        memories = []
        for i in range(10):
            mem = {
                'id': f"mem-{i}",
                'lifecycle_state': LifecycleState.ACTIVE,
                'content': f"Content {i}",
                'created_at': datetime.now(UTC),
            }
            memories.append(mem)

        mock_store.get_all_memories = AsyncMock(return_value=memories)

        result = await jobs.weekly_health_report_job()

        assert result.success is True
        assert result.memories_processed == 10
        assert len(result.errors) == 0
        assert result.job_name == "weekly_health_report"

    @pytest.mark.asyncio
    async def test_weekly_health_report_job_with_store_error(self, jobs, mock_store):
        """Test weekly health report job when store has errors.

        Note: The health scorer is designed to be resilient and will catch
        store errors, returning empty/zero values rather than failing. This
        test verifies that the job completes successfully even when the store
        has issues.
        """
        mock_store.get_all_memories = AsyncMock(
            side_effect=Exception("Health calculation error")
        )

        result = await jobs.weekly_health_report_job()

        # Job should succeed (health scorer catches the error gracefully)
        assert result.success is True
        assert result.memories_processed == 0  # Empty result due to error

    def test_get_job_history_empty(self, jobs):
        """Test get_job_history with no jobs."""
        history = jobs.get_job_history()

        assert history == []

    def test_get_job_history_with_jobs(self, jobs):
        """Test get_job_history returns recent jobs."""
        # Add some jobs to history
        for i in range(15):
            result = JobResult(
                job_name=f"job-{i}",
                success=True,
                memories_processed=i,
            )
            jobs.job_history.append(result)

        # Get last 10
        history = jobs.get_job_history(limit=10)

        assert len(history) == 10
        # Should be in reverse order (most recent first)
        assert history[0]["job_name"] == "job-14"
        assert history[9]["job_name"] == "job-5"

    def test_clear_job_history(self, jobs):
        """Test clearing job history."""
        # Add some jobs
        for i in range(5):
            result = JobResult(job_name=f"job-{i}", success=True)
            jobs.job_history.append(result)

        assert len(jobs.job_history) == 5

        jobs.clear_job_history()

        assert len(jobs.job_history) == 0
