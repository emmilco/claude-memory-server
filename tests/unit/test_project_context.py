"""Tests for project context detection and management."""

import pytest
import os
import tempfile
from datetime import datetime, timedelta, UTC
from pathlib import Path

from src.memory.project_context import (
    ProjectContext,
    ProjectContextDetector,
)


class TestProjectContext:
    """Test ProjectContext dataclass."""

    def test_creation(self):
        """Test creating a ProjectContext."""
        context = ProjectContext(
            project_name="test-project",
            project_path="/path/to/project",
        )

        assert context.project_name == "test-project"
        assert context.project_path == "/path/to/project"
        assert context.is_active is True
        assert context.file_activity_count == 0
        assert isinstance(context.last_activity, datetime)

    def test_with_git_info(self):
        """Test ProjectContext with git information."""
        context = ProjectContext(
            project_name="my-repo",
            project_path="/path/to/repo",
            git_repo_root="/path/to/repo",
            git_branch="main",
        )

        assert context.git_repo_root == "/path/to/repo"
        assert context.git_branch == "main"


class TestProjectContextDetector:
    """Test ProjectContextDetector functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.detector = ProjectContextDetector()

    def test_initialization(self):
        """Test detector initialization."""
        assert self.detector.current_context is None
        assert len(self.detector.project_history) == 0
        assert self.detector.activity_window == timedelta(minutes=30)

    def test_initialization_with_config(self):
        """Test detector initialization with custom config."""
        config = {"custom_key": "custom_value"}
        detector = ProjectContextDetector(config)

        assert detector.config == config

    def test_set_active_context(self):
        """Test setting active context explicitly."""
        context = self.detector.set_active_context(
            project_name="my-project",
            project_path="/path/to/project",
        )

        assert context.project_name == "my-project"
        assert context.project_path == "/path/to/project"
        assert self.detector.current_context == context

    def test_set_active_context_switching(self):
        """Test switching between projects."""
        # Set first project
        context1 = self.detector.set_active_context("project-a")

        # Switch to second project
        context2 = self.detector.set_active_context("project-b")

        # First context should be archived
        assert len(self.detector.project_history) == 1
        assert self.detector.project_history[0].project_name == "project-a"
        assert self.detector.project_history[0].is_active is False

        # Second context should be active
        assert self.detector.current_context.project_name == "project-b"
        assert self.detector.current_context.is_active is True

    def test_set_active_context_same_project(self):
        """Test setting same project doesn't create history."""
        context1 = self.detector.set_active_context("project-a")
        context2 = self.detector.set_active_context("project-a")

        # Should not create history entry
        assert len(self.detector.project_history) == 0

    def test_get_active_context(self):
        """Test getting active context."""
        # No context initially
        assert self.detector.get_active_context() is None

        # Set context
        self.detector.set_active_context("test-project")

        # Should return context
        context = self.detector.get_active_context()
        assert context is not None
        assert context.project_name == "test-project"

    def test_detect_from_file_path_with_package_json(self):
        """Test detecting project from package.json marker."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create project structure
            project_dir = Path(tmpdir) / "my-node-project"
            project_dir.mkdir()
            (project_dir / "package.json").write_text("{}")

            # Create a file in the project
            src_dir = project_dir / "src"
            src_dir.mkdir()
            test_file = src_dir / "index.js"
            test_file.write_text("console.log('test');")

            # Detect from file
            context = self.detector.detect_from_file_path(str(test_file))

            assert context is not None
            assert context.project_name == "my-node-project"
            assert str(project_dir) in context.project_path

    def test_detect_from_file_path_with_requirements_txt(self):
        """Test detecting project from requirements.txt marker."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create project structure
            project_dir = Path(tmpdir) / "my-python-project"
            project_dir.mkdir()
            (project_dir / "requirements.txt").write_text("pytest")

            # Create a file in the project
            test_file = project_dir / "main.py"
            test_file.write_text("print('test')")

            # Detect from file
            context = self.detector.detect_from_file_path(str(test_file))

            assert context is not None
            assert context.project_name == "my-python-project"

    def test_detect_from_file_path_fallback(self):
        """Test detecting project with no markers (uses directory name)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create directory with no markers
            project_dir = Path(tmpdir) / "unmarked-project"
            project_dir.mkdir()
            test_file = project_dir / "file.txt"
            test_file.write_text("test")

            # Detect from file
            context = self.detector.detect_from_file_path(str(test_file))

            assert context is not None
            assert context.project_name == "unmarked-project"

    def test_track_file_activity_new_project(self):
        """Test tracking file activity creates new context."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir) / "test-project"
            project_dir.mkdir()
            (project_dir / "package.json").write_text("{}")
            test_file = project_dir / "index.js"
            test_file.write_text("test")

            # Track activity
            self.detector.track_file_activity(str(test_file))

            # Should auto-set context
            assert self.detector.current_context is not None
            assert self.detector.current_context.project_name == "test-project"
            assert self.detector.current_context.file_activity_count == 0

    def test_track_file_activity_existing_project(self):
        """Test tracking file activity updates existing context."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir) / "test-project"
            project_dir.mkdir()
            (project_dir / "package.json").write_text("{}")
            test_file = project_dir / "index.js"
            test_file.write_text("test")

            # Set context first
            self.detector.set_active_context(
                "test-project",
                str(project_dir),
                explicit=False,
            )
            initial_count = self.detector.current_context.file_activity_count

            # Track activity
            self.detector.track_file_activity(str(test_file))

            # Should increment activity count
            assert self.detector.current_context.file_activity_count == initial_count + 1

    def test_get_project_weight_no_context(self):
        """Test project weight with no active context."""
        weight = self.detector.get_project_weight("any-project")

        # All projects equal when no context
        assert weight == 1.0

    def test_get_project_weight_active_project(self):
        """Test project weight for active project."""
        self.detector.set_active_context("my-project")

        weight = self.detector.get_project_weight("my-project")

        # Active project gets 2x boost
        assert weight == 2.0

    def test_get_project_weight_inactive_project(self):
        """Test project weight for inactive project."""
        self.detector.set_active_context("my-project")

        weight = self.detector.get_project_weight("other-project")

        # Inactive project gets penalty
        assert weight == 0.3

    def test_should_archive_project_active(self):
        """Test archive check for active project."""
        self.detector.set_active_context("active-project")

        # Active project should never be archived
        should_archive = self.detector.should_archive_project(
            "active-project",
            datetime.now(UTC) - timedelta(days=100),
        )

        assert should_archive is False

    def test_should_archive_project_recent_inactive(self):
        """Test archive check for recently inactive project."""
        self.detector.set_active_context("current-project")

        # Project inactive for 30 days (< 45 threshold)
        should_archive = self.detector.should_archive_project(
            "other-project",
            datetime.now(UTC) - timedelta(days=30),
        )

        assert should_archive is False

    def test_should_archive_project_old_inactive(self):
        """Test archive check for old inactive project."""
        self.detector.set_active_context("current-project")

        # Project inactive for 60 days (> 45 threshold)
        should_archive = self.detector.should_archive_project(
            "other-project",
            datetime.now(UTC) - timedelta(days=60),
        )

        assert should_archive is True

    def test_get_recent_projects(self):
        """Test getting recent projects."""
        # Set multiple projects
        self.detector.set_active_context("project-a")
        self.detector.set_active_context("project-b")
        self.detector.set_active_context("project-c")

        recent = self.detector.get_recent_projects(limit=10)

        # Should have all 3 projects
        assert len(recent) == 3
        # Most recent first
        assert recent[0].project_name == "project-c"
        assert recent[1].project_name == "project-b"
        assert recent[2].project_name == "project-a"

    def test_get_recent_projects_with_limit(self):
        """Test getting recent projects with limit."""
        # Set multiple projects
        for i in range(5):
            self.detector.set_active_context(f"project-{i}")

        recent = self.detector.get_recent_projects(limit=3)

        # Should respect limit
        assert len(recent) == 3
        # Most recent first
        assert recent[0].project_name == "project-4"
        assert recent[1].project_name == "project-3"
        assert recent[2].project_name == "project-2"

    def test_get_context_stats(self):
        """Test getting context statistics."""
        # Set active project
        self.detector.set_active_context("my-project", "/path/to/project")

        stats = self.detector.get_context_stats()

        assert stats["current_project"] == "my-project"
        assert stats["total_projects"] == 1
        assert stats["file_activity_count"] == 0
        assert stats["active_since"] is not None
        assert len(stats["recent_projects"]) == 1
        assert stats["recent_projects"][0]["name"] == "my-project"

    def test_get_context_stats_no_context(self):
        """Test getting context statistics with no context."""
        stats = self.detector.get_context_stats()

        assert stats["current_project"] is None
        assert stats["total_projects"] == 0
        assert stats["file_activity_count"] == 0
        assert stats["active_since"] is None
        assert len(stats["recent_projects"]) == 0

    def test_clear_history(self):
        """Test clearing project history."""
        # Create history
        self.detector.set_active_context("project-a")
        self.detector.set_active_context("project-b")

        assert len(self.detector.project_history) == 1

        # Clear history
        self.detector.clear_history()

        assert len(self.detector.project_history) == 0

    def test_reset_context(self):
        """Test resetting current context."""
        # Set context
        self.detector.set_active_context("my-project")
        assert self.detector.current_context is not None

        # Reset
        self.detector.reset_context()

        assert self.detector.current_context is None
        # Old context should be in history
        assert len(self.detector.project_history) == 1
