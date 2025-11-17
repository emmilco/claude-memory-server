"""Tests for project archival and lifecycle management."""

import pytest
from pathlib import Path
from src.memory.project_archival import ProjectArchivalManager, ProjectState


@pytest.fixture
def manager(tmp_path):
    """Create a project archival manager with temporary state file."""
    state_file = tmp_path / "project_states.json"
    return ProjectArchivalManager(str(state_file), inactivity_threshold_days=45)


class TestProjectArchivalManager:
    """Test project archival manager."""

    def test_initialization(self, manager):
        """Test manager initialization."""
        assert manager.project_states == {}
        assert manager.inactivity_threshold_days == 45

    def test_initialize_new_project(self, manager):
        """Test initializing a new project."""
        state = manager.get_project_state("test-project")

        assert state == ProjectState.ACTIVE
        assert "test-project" in manager.project_states
        assert manager.project_states["test-project"]["state"] == "active"

    def test_record_activity_search(self, manager):
        """Test recording search activity."""
        manager.record_activity("test-project", "search", count=5)

        assert manager.project_states["test-project"]["searches_count"] == 5

        # Record more activity
        manager.record_activity("test-project", "search", count=3)
        assert manager.project_states["test-project"]["searches_count"] == 8

    def test_record_activity_index_update(self, manager):
        """Test recording index update activity."""
        manager.record_activity("test-project", "index_update", count=1)

        assert manager.project_states["test-project"]["index_updates_count"] == 1

    def test_record_activity_files_indexed(self, manager):
        """Test recording files indexed."""
        manager.record_activity("test-project", "files_indexed", count=100)

        assert manager.project_states["test-project"]["files_indexed"] == 100

    def test_get_days_since_activity_new_project(self, manager):
        """Test days since activity for new project."""
        manager._initialize_project("test-project")

        days = manager.get_days_since_activity("test-project")

        # Should be very close to 0 for newly created project
        assert days < 0.01  # Less than ~15 minutes

    def test_archive_project(self, manager):
        """Test archiving a project."""
        manager._initialize_project("test-project")

        result = manager.archive_project("test-project")

        assert result["success"] is True
        assert "archived successfully" in result["message"]
        assert manager.get_project_state("test-project") == ProjectState.ARCHIVED

    def test_archive_project_not_found(self, manager):
        """Test archiving non-existent project."""
        result = manager.archive_project("nonexistent")

        assert result["success"] is False
        assert "not found" in result["message"]

    def test_archive_project_already_archived(self, manager):
        """Test archiving already archived project."""
        manager._initialize_project("test-project")
        manager.archive_project("test-project")

        # Try to archive again
        result = manager.archive_project("test-project")

        assert result["success"] is False
        assert "already archived" in result["message"]

    def test_reactivate_project(self, manager):
        """Test reactivating an archived project."""
        manager._initialize_project("test-project")
        manager.archive_project("test-project")

        result = manager.reactivate_project("test-project")

        assert result["success"] is True
        assert "reactivated successfully" in result["message"]
        assert manager.get_project_state("test-project") == ProjectState.ACTIVE

    def test_reactivate_project_not_found(self, manager):
        """Test reactivating non-existent project."""
        result = manager.reactivate_project("nonexistent")

        assert result["success"] is False
        assert "not found" in result["message"]

    def test_reactivate_project_already_active(self, manager):
        """Test reactivating already active project."""
        manager._initialize_project("test-project")

        result = manager.reactivate_project("test-project")

        assert result["success"] is False
        assert "already active" in result["message"]

    def test_get_projects_by_state(self, manager):
        """Test getting projects by state."""
        manager._initialize_project("active-project")
        manager._initialize_project("archived-project")
        manager.archive_project("archived-project")

        active_projects = manager.get_projects_by_state(ProjectState.ACTIVE)
        archived_projects = manager.get_projects_by_state(ProjectState.ARCHIVED)

        assert "active-project" in active_projects
        assert "archived-project" in archived_projects
        assert "archived-project" not in active_projects
        assert "active-project" not in archived_projects

    def test_get_search_weight(self, manager):
        """Test getting search weight for different project states."""
        manager._initialize_project("active-project")
        manager._initialize_project("archived-project")
        manager.archive_project("archived-project")

        active_weight = manager.get_search_weight("active-project")
        archived_weight = manager.get_search_weight("archived-project")

        assert active_weight == 1.0
        assert archived_weight == 0.1

    def test_persistence(self, tmp_path):
        """Test that project states are persisted across instances."""
        state_file = tmp_path / "states.json"

        # First instance - create and archive a project
        manager1 = ProjectArchivalManager(str(state_file))
        manager1._initialize_project("test-project")
        manager1.archive_project("test-project")

        # Second instance - should load the persisted state
        manager2 = ProjectArchivalManager(str(state_file))

        assert manager2.get_project_state("test-project") == ProjectState.ARCHIVED

    def test_get_all_projects(self, manager):
        """Test getting all projects."""
        manager._initialize_project("project1")
        manager._initialize_project("project2")
        manager._initialize_project("project3")

        all_projects = manager.get_all_projects()

        assert len(all_projects) == 3
        assert "project1" in all_projects
        assert "project2" in all_projects
        assert "project3" in all_projects
