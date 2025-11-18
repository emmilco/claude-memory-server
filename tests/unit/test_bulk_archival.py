"""
Unit tests for bulk archival operations.

Tests bulk archive, bulk reactivate, auto-archive, and archival candidates functionality.
"""

import pytest
import tempfile
from pathlib import Path
from datetime import datetime, UTC, timedelta

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

    # Cleanup happens automatically when temp_root goes out of scope


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
def sample_projects(archival_manager):
    """Create sample projects with various states and activity levels."""
    projects = []

    # Active projects (recent activity)
    for i in range(5):
        project_name = f"active-project-{i}"
        archival_manager.project_states[project_name] = {
            "state": ProjectState.ACTIVE.value,
            "created_at": (datetime.now(UTC) - timedelta(days=100)).isoformat(),
            "last_activity": (datetime.now(UTC) - timedelta(days=i)).isoformat(),
            "files_indexed": 100,
            "searches_count": 50,
            "index_updates_count": 10,
        }
        projects.append(project_name)

    # Inactive projects (old activity, candidates for archival)
    for i in range(5):
        project_name = f"inactive-project-{i}"
        archival_manager.project_states[project_name] = {
            "state": ProjectState.ACTIVE.value,
            "created_at": (datetime.now(UTC) - timedelta(days=200)).isoformat(),
            "last_activity": (datetime.now(UTC) - timedelta(days=60 + i)).isoformat(),
            "files_indexed": 200,
            "searches_count": 100,
            "index_updates_count": 20,
        }
        projects.append(project_name)

    # Already archived projects
    for i in range(3):
        project_name = f"archived-project-{i}"
        archival_manager.project_states[project_name] = {
            "state": ProjectState.ARCHIVED.value,
            "created_at": (datetime.now(UTC) - timedelta(days=300)).isoformat(),
            "last_activity": (datetime.now(UTC) - timedelta(days=90 + i)).isoformat(),
            "archived_at": (datetime.now(UTC) - timedelta(days=30)).isoformat(),
            "files_indexed": 150,
            "searches_count": 75,
        }
        projects.append(project_name)

    archival_manager._save_states()
    return projects


class TestBulkArchivalManager:
    """Test BulkArchivalManager functionality."""

    def test_initialization(self, bulk_manager):
        """Test manager initialization."""
        assert bulk_manager.archival_manager is not None
        assert bulk_manager.compressor is not None
        assert bulk_manager.max_projects_per_operation == 20

    @pytest.mark.asyncio
    async def test_bulk_archive_dry_run(self, bulk_manager, sample_projects):
        """Test bulk archive in dry-run mode."""
        projects_to_archive = ["active-project-0", "active-project-1", "inactive-project-0"]

        result = await bulk_manager.bulk_archive_projects(
            project_names=projects_to_archive,
            dry_run=True,
        )

        assert result.dry_run is True
        assert result.total_projects == 3
        assert result.successful == 3
        assert result.failed == 0
        assert result.skipped == 0
        assert len(result.results) == 3
        assert all(r["status"] == "would_archive" for r in result.results)

        # Verify states didn't actually change
        assert bulk_manager.archival_manager.get_project_state("active-project-0") == ProjectState.ACTIVE

    @pytest.mark.asyncio
    async def test_bulk_archive_actual(self, bulk_manager, sample_projects):
        """Test actual bulk archive operation."""
        projects_to_archive = ["active-project-0", "active-project-1"]

        result = await bulk_manager.bulk_archive_projects(
            project_names=projects_to_archive,
            dry_run=False,
        )

        assert result.dry_run is False
        assert result.total_projects == 2
        assert result.successful == 2
        assert result.failed == 0
        assert result.skipped == 0
        assert len(result.results) == 2

        # Verify states changed to ARCHIVED
        assert bulk_manager.archival_manager.get_project_state("active-project-0") == ProjectState.ARCHIVED
        assert bulk_manager.archival_manager.get_project_state("active-project-1") == ProjectState.ARCHIVED

    @pytest.mark.asyncio
    async def test_bulk_archive_skip_already_archived(self, bulk_manager, sample_projects):
        """Test that already archived projects are skipped."""
        projects_to_archive = ["archived-project-0", "archived-project-1"]

        result = await bulk_manager.bulk_archive_projects(
            project_names=projects_to_archive,
            dry_run=False,
        )

        assert result.total_projects == 2
        assert result.successful == 0
        assert result.failed == 0
        assert result.skipped == 2
        assert all(r["status"] == "skipped" for r in result.results)

    @pytest.mark.asyncio
    async def test_bulk_archive_exceeds_limit(self, bulk_manager, sample_projects):
        """Test that bulk archive rejects operations exceeding max limit."""
        # Try to archive 25 projects (exceeds limit of 20)
        projects_to_archive = [f"project-{i}" for i in range(25)]

        result = await bulk_manager.bulk_archive_projects(
            project_names=projects_to_archive,
            dry_run=False,
        )

        assert result.total_projects == 25
        assert result.successful == 0
        assert result.failed == 0
        assert result.skipped == 25
        assert len(result.errors) > 0
        assert "Exceeded max projects limit" in result.errors[0]

    @pytest.mark.asyncio
    async def test_bulk_archive_with_progress_callback(self, bulk_manager, sample_projects):
        """Test bulk archive with progress callback."""
        projects_to_archive = ["active-project-0", "active-project-1", "active-project-2"]
        progress_calls = []

        def progress_callback(project_name: str, current: int, total: int):
            progress_calls.append((project_name, current, total))

        result = await bulk_manager.bulk_archive_projects(
            project_names=projects_to_archive,
            dry_run=False,
            progress_callback=progress_callback,
        )

        assert result.successful == 3
        assert len(progress_calls) == 3
        assert progress_calls[0] == ("active-project-0", 1, 3)
        assert progress_calls[1] == ("active-project-1", 2, 3)
        assert progress_calls[2] == ("active-project-2", 3, 3)

    @pytest.mark.asyncio
    async def test_bulk_reactivate_dry_run(self, bulk_manager, sample_projects):
        """Test bulk reactivate in dry-run mode."""
        projects_to_reactivate = ["archived-project-0", "archived-project-1"]

        result = await bulk_manager.bulk_reactivate_projects(
            project_names=projects_to_reactivate,
            dry_run=True,
        )

        assert result.dry_run is True
        assert result.total_projects == 2
        assert result.successful == 2
        assert result.failed == 0
        assert result.skipped == 0
        assert all(r["status"] == "would_reactivate" for r in result.results)

        # Verify states didn't actually change
        assert bulk_manager.archival_manager.get_project_state("archived-project-0") == ProjectState.ARCHIVED

    @pytest.mark.asyncio
    async def test_bulk_reactivate_actual(self, bulk_manager, sample_projects):
        """Test actual bulk reactivate operation."""
        projects_to_reactivate = ["archived-project-0", "archived-project-1"]

        result = await bulk_manager.bulk_reactivate_projects(
            project_names=projects_to_reactivate,
            dry_run=False,
        )

        assert result.dry_run is False
        assert result.total_projects == 2
        assert result.successful == 2
        assert result.failed == 0
        assert result.skipped == 0

        # Verify states changed to ACTIVE
        assert bulk_manager.archival_manager.get_project_state("archived-project-0") == ProjectState.ACTIVE
        assert bulk_manager.archival_manager.get_project_state("archived-project-1") == ProjectState.ACTIVE

    @pytest.mark.asyncio
    async def test_bulk_reactivate_skip_not_archived(self, bulk_manager, sample_projects):
        """Test that non-archived projects are skipped during reactivation."""
        projects_to_reactivate = ["active-project-0", "inactive-project-0"]

        result = await bulk_manager.bulk_reactivate_projects(
            project_names=projects_to_reactivate,
            dry_run=False,
        )

        assert result.total_projects == 2
        assert result.successful == 0
        assert result.failed == 0
        assert result.skipped == 2
        assert all(r["status"] == "skipped" for r in result.results)

    @pytest.mark.asyncio
    async def test_bulk_reactivate_exceeds_limit(self, bulk_manager):
        """Test that bulk reactivate rejects operations exceeding max limit."""
        projects_to_reactivate = [f"project-{i}" for i in range(25)]

        result = await bulk_manager.bulk_reactivate_projects(
            project_names=projects_to_reactivate,
            dry_run=False,
        )

        assert result.total_projects == 25
        assert result.successful == 0
        assert result.skipped == 25
        assert "Exceeded max projects limit" in result.errors[0]

    @pytest.mark.asyncio
    async def test_auto_archive_inactive_dry_run(self, bulk_manager, sample_projects):
        """Test auto-archive inactive projects in dry-run mode."""
        result = await bulk_manager.auto_archive_inactive(
            days_threshold=50,  # Should catch inactive-project-0 through inactive-project-4
            dry_run=True,
        )

        assert result.dry_run is True
        assert result.total_projects == 5  # 5 inactive projects
        assert result.successful == 5
        assert result.failed == 0
        assert result.skipped == 0

        # Verify states didn't change
        assert bulk_manager.archival_manager.get_project_state("inactive-project-0") == ProjectState.ACTIVE

    @pytest.mark.asyncio
    async def test_auto_archive_inactive_actual(self, bulk_manager, sample_projects):
        """Test actual auto-archive of inactive projects."""
        result = await bulk_manager.auto_archive_inactive(
            days_threshold=50,
            dry_run=False,
        )

        assert result.dry_run is False
        assert result.total_projects == 5
        assert result.successful == 5
        assert result.failed == 0

        # Verify states changed to ARCHIVED
        for i in range(5):
            project_name = f"inactive-project-{i}"
            assert bulk_manager.archival_manager.get_project_state(project_name) == ProjectState.ARCHIVED

    @pytest.mark.asyncio
    async def test_auto_archive_no_inactive_projects(self, bulk_manager, sample_projects):
        """Test auto-archive when no projects meet threshold."""
        result = await bulk_manager.auto_archive_inactive(
            days_threshold=200,  # Very high threshold, no projects match
            dry_run=False,
        )

        assert result.total_projects == 0
        assert result.successful == 0
        assert result.failed == 0
        assert result.skipped == 0

    @pytest.mark.asyncio
    async def test_auto_archive_with_max_limit(self, bulk_manager, sample_projects):
        """Test auto-archive with max_projects limit."""
        result = await bulk_manager.auto_archive_inactive(
            days_threshold=50,
            dry_run=False,
            max_projects=3,  # Limit to 3 projects
        )

        assert result.total_projects == 3  # Limited to 3
        assert result.successful == 3

    @pytest.mark.asyncio
    async def test_auto_archive_excludes_already_archived(self, bulk_manager, sample_projects):
        """Test that auto-archive doesn't re-archive already archived projects."""
        # All archived-project-* are already archived and meet threshold
        result = await bulk_manager.auto_archive_inactive(
            days_threshold=50,
            dry_run=False,
        )

        # Should only archive the inactive-project-* that are ACTIVE
        assert result.total_projects == 5  # Only the ACTIVE inactive projects
        assert "archived-project-0" not in [r["project"] for r in result.results]

    def test_get_archival_candidates(self, bulk_manager, sample_projects):
        """Test getting archival candidates."""
        candidates = bulk_manager.get_archival_candidates(
            days_threshold=50,
            max_results=100,
        )

        assert len(candidates) == 5  # 5 inactive ACTIVE projects
        assert all(c["current_state"] in ["active", "paused"] for c in candidates)
        assert all(c["recommendation"] == "archive" for c in candidates)
        assert all(c["days_inactive"] >= 50 for c in candidates)

    def test_get_archival_candidates_max_results(self, bulk_manager, sample_projects):
        """Test archival candidates with max_results limit."""
        candidates = bulk_manager.get_archival_candidates(
            days_threshold=50,
            max_results=3,
        )

        assert len(candidates) == 3  # Limited to 3

    def test_get_archival_candidates_high_threshold(self, bulk_manager, sample_projects):
        """Test archival candidates with high threshold (no matches)."""
        candidates = bulk_manager.get_archival_candidates(
            days_threshold=200,
            max_results=100,
        )

        assert len(candidates) == 0  # No projects meet threshold

    def test_bulk_archival_result_success_rate(self):
        """Test BulkArchivalResult success_rate calculation."""
        result = BulkArchivalResult(
            dry_run=False,
            total_projects=10,
            successful=8,
            failed=2,
            skipped=0,
            execution_time_seconds=5.0,
            results=[],
            errors=[],
        )

        assert result.success_rate == 80.0

        # Test with zero projects
        result_empty = BulkArchivalResult(
            dry_run=False,
            total_projects=0,
            successful=0,
            failed=0,
            skipped=0,
            execution_time_seconds=0.0,
            results=[],
            errors=[],
        )

        assert result_empty.success_rate == 0.0

    @pytest.mark.asyncio
    async def test_bulk_archive_mixed_results(self, bulk_manager, sample_projects):
        """Test bulk archive with mixed success/skip results."""
        projects_to_archive = [
            "active-project-0",  # Should succeed
            "archived-project-0",  # Should skip (already archived)
            "inactive-project-0",  # Should succeed
        ]

        result = await bulk_manager.bulk_archive_projects(
            project_names=projects_to_archive,
            dry_run=False,
        )

        assert result.total_projects == 3
        assert result.successful == 2
        assert result.failed == 0
        assert result.skipped == 1
        assert result.success_rate == pytest.approx(66.67, rel=0.1)
