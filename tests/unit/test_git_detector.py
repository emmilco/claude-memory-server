"""Tests for git repository detection (FEAT-017)."""

import pytest
import tempfile
import subprocess
from pathlib import Path
from src.memory.git_detector import (
    is_git_repository,
    get_git_root,
    get_git_metadata,
    get_repository_name,
)


@pytest.fixture
def temp_git_repo():
    """Create a temporary git repository for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir)

        # Initialize git repo
        subprocess.run(["git", "init"], cwd=repo_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=repo_path,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=repo_path,
            check=True,
            capture_output=True,
        )

        # Create a test file and commit
        test_file = repo_path / "test.txt"
        test_file.write_text("test content")
        subprocess.run(
            ["git", "add", "test.txt"],
            cwd=repo_path,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "Initial commit"],
            cwd=repo_path,
            check=True,
            capture_output=True,
        )

        yield repo_path


@pytest.fixture
def temp_git_repo_with_remote(temp_git_repo):
    """Create a temporary git repository with a remote configured."""
    subprocess.run(
        [
            "git",
            "remote",
            "add",
            "origin",
            "https://github.com/test/example.git",
        ],
        cwd=temp_git_repo,
        check=True,
        capture_output=True,
    )
    return temp_git_repo


@pytest.fixture
def temp_non_git_dir():
    """Create a temporary non-git directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


class TestIsGitRepository:
    """Tests for is_git_repository function."""

    def test_detects_git_repo(self, temp_git_repo):
        """Test that a git repository is detected."""
        assert is_git_repository(temp_git_repo) is True

    def test_detects_non_git_dir(self, temp_non_git_dir):
        """Test that a non-git directory is not detected as a git repo."""
        assert is_git_repository(temp_non_git_dir) is False

    def test_detects_subdirectory_in_git_repo(self, temp_git_repo):
        """Test that a subdirectory within a git repo is detected."""
        subdir = temp_git_repo / "subdir"
        subdir.mkdir()
        assert is_git_repository(subdir) is True

    def test_handles_nonexistent_path(self):
        """Test that nonexistent paths return False."""
        nonexistent = Path("/nonexistent/path/that/doesnt/exist")
        assert is_git_repository(nonexistent) is False


class TestGetGitRoot:
    """Tests for get_git_root function."""

    def test_returns_root_from_root(self, temp_git_repo):
        """Test getting git root from repository root."""
        root = get_git_root(temp_git_repo)
        assert root.resolve() == temp_git_repo.resolve()

    def test_returns_root_from_subdirectory(self, temp_git_repo):
        """Test getting git root from a subdirectory."""
        subdir = temp_git_repo / "subdir" / "nested"
        subdir.mkdir(parents=True)
        root = get_git_root(subdir)
        assert root.resolve() == temp_git_repo.resolve()

    def test_returns_none_for_non_git_dir(self, temp_non_git_dir):
        """Test that non-git directories return None."""
        root = get_git_root(temp_non_git_dir)
        assert root is None


class TestGetGitMetadata:
    """Tests for get_git_metadata function."""

    def test_extracts_metadata_from_git_repo(self, temp_git_repo):
        """Test extracting metadata from a git repository."""
        metadata = get_git_metadata(temp_git_repo)

        assert metadata is not None
        assert "root" in metadata
        assert Path(metadata["root"]).resolve() == temp_git_repo.resolve()
        assert "remote_url" in metadata
        assert "current_branch" in metadata
        assert "commit_hash" in metadata
        assert "is_dirty" in metadata

        # Check specific values
        assert metadata["remote_url"] is None  # No remote configured
        assert metadata["commit_hash"] is not None  # Should have initial commit
        assert len(metadata["commit_hash"]) == 40  # SHA-1 hash
        assert metadata["is_dirty"] is False  # Clean repo

    def test_extracts_remote_url(self, temp_git_repo_with_remote):
        """Test extracting remote URL when configured."""
        metadata = get_git_metadata(temp_git_repo_with_remote)

        assert metadata is not None
        assert metadata["remote_url"] == "https://github.com/test/example.git"

    def test_detects_dirty_repo(self, temp_git_repo):
        """Test detecting uncommitted changes."""
        # Create an uncommitted file
        new_file = temp_git_repo / "uncommitted.txt"
        new_file.write_text("uncommitted content")

        metadata = get_git_metadata(temp_git_repo)

        assert metadata is not None
        assert metadata["is_dirty"] is True

    def test_returns_none_for_non_git_dir(self, temp_non_git_dir):
        """Test that non-git directories return None."""
        metadata = get_git_metadata(temp_non_git_dir)
        assert metadata is None

    def test_works_from_subdirectory(self, temp_git_repo):
        """Test extracting metadata from a subdirectory."""
        subdir = temp_git_repo / "subdir"
        subdir.mkdir()

        metadata = get_git_metadata(subdir)

        assert metadata is not None
        assert Path(metadata["root"]).resolve() == temp_git_repo.resolve()


class TestGetRepositoryName:
    """Tests for get_repository_name function."""

    def test_extracts_name_from_remote_url_https(self):
        """Test extracting repository name from HTTPS URL."""
        metadata = {"remote_url": "https://github.com/user/my-repo.git"}
        name = get_repository_name(metadata)
        assert name == "my-repo"

    def test_extracts_name_from_remote_url_ssh(self):
        """Test extracting repository name from SSH URL."""
        metadata = {"remote_url": "git@github.com:user/my-repo.git"}
        name = get_repository_name(metadata)
        assert name == "my-repo"

    def test_handles_url_without_git_suffix(self):
        """Test extracting name from URL without .git suffix."""
        metadata = {"remote_url": "https://github.com/user/my-repo"}
        name = get_repository_name(metadata)
        assert name == "my-repo"

    def test_falls_back_to_directory_name(self):
        """Test falling back to directory name when no remote."""
        metadata = {"remote_url": None, "root": "/path/to/my-project"}
        name = get_repository_name(metadata)
        assert name == "my-project"

    def test_handles_missing_remote_and_root(self):
        """Test handling metadata without remote or root."""
        metadata = {}
        name = get_repository_name(metadata)
        assert name == "unknown"


class TestGitDetectorIntegration:
    """Integration tests for git detector."""

    def test_full_workflow(self, temp_git_repo_with_remote):
        """Test complete workflow of detecting and extracting git info."""
        # Check if it's a git repo
        assert is_git_repository(temp_git_repo_with_remote)

        # Get the root
        root = get_git_root(temp_git_repo_with_remote)
        assert root.resolve() == temp_git_repo_with_remote.resolve()

        # Get metadata
        metadata = get_git_metadata(temp_git_repo_with_remote)
        assert metadata is not None

        # Extract repository name
        name = get_repository_name(metadata)
        assert name == "example"  # From the remote URL

    def test_works_with_real_repo(self):
        """Test with the actual project repository."""
        # Get current file's directory
        current_file = Path(__file__).resolve()
        project_root = current_file.parent.parent.parent

        # Check if we're in a git repo (we should be)
        if is_git_repository(project_root):
            metadata = get_git_metadata(project_root)
            assert metadata is not None
            assert "root" in metadata
            assert "commit_hash" in metadata

            # Extract name
            name = get_repository_name(metadata)
            assert name != "unknown"
