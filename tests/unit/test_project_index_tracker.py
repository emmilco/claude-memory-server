"""Tests for ProjectIndexTracker - project metadata tracking for auto-indexing."""

import pytest
import pytest_asyncio
import asyncio
import tempfile
import sqlite3
from pathlib import Path
from datetime import datetime, UTC, timedelta

from src.memory.project_index_tracker import ProjectIndexTracker, ProjectIndexMetadata
from src.core.exceptions import StorageError
from src.config import ServerConfig


@pytest_asyncio.fixture
async def temp_db():
    """Create a temporary database for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_tracker.db"
        yield db_path


@pytest_asyncio.fixture
async def tracker(temp_db):
    """Create a ProjectIndexTracker instance for testing."""
    config = ServerConfig(sqlite_path=str(temp_db))
    tracker = ProjectIndexTracker(config=config)
    await tracker.initialize()
    yield tracker
    await tracker.close()


@pytest_asyncio.fixture
async def sample_project_dir():
    """Create a temporary project directory with some files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_path = Path(tmpdir) / "sample_project"
        project_path.mkdir()

        # Create some sample files
        (project_path / "file1.py").write_text("print('hello')")
        (project_path / "file2.py").write_text("print('world')")
        (project_path / "subdir").mkdir()
        (project_path / "subdir" / "file3.py").write_text("print('test')")

        yield project_path


class TestProjectIndexMetadata:
    """Test ProjectIndexMetadata model."""

    def test_metadata_creation(self):
        """Test creating metadata instance."""
        now = datetime.now(UTC)
        metadata = ProjectIndexMetadata(
            project_name="test_project",
            first_indexed_at=now,
            last_indexed_at=now,
            total_files=10,
            total_units=50,
            is_watching=True,
            index_version="1.0",
        )

        assert metadata.project_name == "test_project"
        assert metadata.total_files == 10
        assert metadata.total_units == 50
        assert metadata.is_watching is True
        assert metadata.index_version == "1.0"

    def test_metadata_to_dict(self):
        """Test converting metadata to dictionary."""
        now = datetime.now(UTC)
        metadata = ProjectIndexMetadata(
            project_name="test_project",
            first_indexed_at=now,
            last_indexed_at=now,
            total_files=10,
            total_units=50,
        )

        data = metadata.to_dict()
        assert data["project_name"] == "test_project"
        assert data["total_files"] == 10
        assert data["total_units"] == 50
        assert "first_indexed_at" in data
        assert "last_indexed_at" in data

    def test_metadata_from_dict(self):
        """Test creating metadata from dictionary."""
        now = datetime.now(UTC)
        data = {
            "project_name": "test_project",
            "first_indexed_at": now.isoformat(),
            "last_indexed_at": now.isoformat(),
            "total_files": 10,
            "total_units": 50,
            "is_watching": True,
            "index_version": "1.0",
        }

        metadata = ProjectIndexMetadata.from_dict(data)
        assert metadata.project_name == "test_project"
        assert metadata.total_files == 10
        assert metadata.is_watching is True

    def test_metadata_roundtrip(self):
        """Test converting to dict and back."""
        now = datetime.now(UTC)
        original = ProjectIndexMetadata(
            project_name="test_project",
            first_indexed_at=now,
            last_indexed_at=now,
            total_files=15,
            total_units=75,
            is_watching=False,
        )

        data = original.to_dict()
        restored = ProjectIndexMetadata.from_dict(data)

        assert restored.project_name == original.project_name
        assert restored.total_files == original.total_files
        assert restored.total_units == original.total_units
        assert restored.is_watching == original.is_watching


class TestProjectIndexTrackerInitialization:
    """Test tracker initialization."""

    @pytest.mark.asyncio
    async def test_tracker_initialization(self, temp_db):
        """Test tracker initializes correctly."""
        config = ServerConfig(sqlite_path=str(temp_db))
        tracker = ProjectIndexTracker(config=config)

        await tracker.initialize()

        # Check that database file was created
        assert temp_db.exists()

        # Check that table was created
        conn = sqlite3.connect(str(temp_db))
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='project_index_metadata'"
        )
        result = cursor.fetchone()
        assert result is not None
        conn.close()

        await tracker.close()

    @pytest.mark.asyncio
    async def test_tracker_creates_index(self, temp_db):
        """Test that tracker creates database index."""
        config = ServerConfig(sqlite_path=str(temp_db))
        tracker = ProjectIndexTracker(config=config)

        await tracker.initialize()

        # Check that index was created
        conn = sqlite3.connect(str(temp_db))
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_last_indexed'"
        )
        result = cursor.fetchone()
        assert result is not None
        conn.close()

        await tracker.close()

    @pytest.mark.asyncio
    async def test_tracker_initialization_failure(self):
        """Test tracker handles initialization errors."""
        # Use a path that exists but with read-only permissions to trigger error
        with tempfile.TemporaryDirectory() as tmpdir:
            ro_dir = Path(tmpdir) / "readonly"
            ro_dir.mkdir()
            # Make directory read-only
            import os
            os.chmod(ro_dir, 0o444)

            try:
                config = ServerConfig(sqlite_path=str(ro_dir / "db.sqlite"))
                tracker = ProjectIndexTracker(config=config)

                with pytest.raises((StorageError, PermissionError, OSError)):
                    await tracker.initialize()
            finally:
                # Restore permissions for cleanup
                os.chmod(ro_dir, 0o755)


class TestProjectIndexTrackerOperations:
    """Test tracker CRUD operations."""

    @pytest.mark.asyncio
    async def test_is_indexed_false_initially(self, tracker):
        """Test that new project is not indexed."""
        is_indexed = await tracker.is_indexed("new_project")
        assert is_indexed is False

    @pytest.mark.asyncio
    async def test_update_metadata_creates_entry(self, tracker):
        """Test updating metadata creates new entry."""
        await tracker.update_metadata(
            project_name="test_project",
            total_files=5,
            total_units=25,
            is_watching=False,
        )

        is_indexed = await tracker.is_indexed("test_project")
        assert is_indexed is True

    @pytest.mark.asyncio
    async def test_get_metadata_returns_none_for_missing(self, tracker):
        """Test getting metadata for non-existent project."""
        metadata = await tracker.get_metadata("missing_project")
        assert metadata is None

    @pytest.mark.asyncio
    async def test_get_metadata_returns_correct_data(self, tracker):
        """Test getting metadata returns correct data."""
        await tracker.update_metadata(
            project_name="test_project",
            total_files=10,
            total_units=50,
            is_watching=True,
        )

        metadata = await tracker.get_metadata("test_project")
        assert metadata is not None
        assert metadata.project_name == "test_project"
        assert metadata.total_files == 10
        assert metadata.total_units == 50
        assert metadata.is_watching is True

    @pytest.mark.asyncio
    async def test_update_metadata_updates_existing(self, tracker):
        """Test updating existing metadata."""
        # Create initial entry
        await tracker.update_metadata(
            project_name="test_project",
            total_files=5,
            total_units=25,
            is_watching=False,
        )

        # Get initial timestamps
        metadata1 = await tracker.get_metadata("test_project")

        # Small delay to ensure timestamp difference
        await asyncio.sleep(0.01)

        # Update
        await tracker.update_metadata(
            project_name="test_project",
            total_files=10,
            total_units=50,
            is_watching=True,
        )

        # Verify update
        metadata2 = await tracker.get_metadata("test_project")
        assert metadata2.total_files == 10
        assert metadata2.total_units == 50
        assert metadata2.is_watching is True
        assert metadata2.last_indexed_at >= metadata1.last_indexed_at

    @pytest.mark.asyncio
    async def test_update_metadata_without_watching_param(self, tracker):
        """Test updating metadata without changing watching status."""
        # Create with watching=True
        await tracker.update_metadata(
            project_name="test_project",
            total_files=5,
            total_units=25,
            is_watching=True,
        )

        # Update without specifying is_watching
        await tracker.update_metadata(
            project_name="test_project",
            total_files=10,
            total_units=50,
            is_watching=None,
        )

        # Verify watching status unchanged
        metadata = await tracker.get_metadata("test_project")
        assert metadata.is_watching is True

    @pytest.mark.asyncio
    async def test_set_watching_updates_status(self, tracker):
        """Test setting watching status."""
        await tracker.update_metadata(
            project_name="test_project",
            total_files=5,
            total_units=25,
            is_watching=False,
        )

        await tracker.set_watching("test_project", True)

        metadata = await tracker.get_metadata("test_project")
        assert metadata.is_watching is True

    @pytest.mark.asyncio
    async def test_delete_metadata(self, tracker):
        """Test deleting project metadata."""
        await tracker.update_metadata(
            project_name="test_project",
            total_files=5,
            total_units=25,
        )

        is_indexed = await tracker.is_indexed("test_project")
        assert is_indexed is True

        await tracker.delete_metadata("test_project")

        is_indexed = await tracker.is_indexed("test_project")
        assert is_indexed is False


class TestProjectIndexTrackerStaleness:
    """Test staleness detection."""

    @pytest.mark.asyncio
    async def test_is_stale_false_for_unindexed(self, tracker, sample_project_dir):
        """Test that unindexed project is not stale."""
        is_stale = await tracker.is_stale("test_project", sample_project_dir)
        assert is_stale is False

    @pytest.mark.asyncio
    async def test_is_stale_false_for_fresh_index(self, tracker, sample_project_dir):
        """Test that freshly indexed project is not stale."""
        await tracker.update_metadata(
            project_name="test_project",
            total_files=3,
            total_units=15,
        )

        is_stale = await tracker.is_stale("test_project", sample_project_dir)
        assert is_stale is False

    @pytest.mark.asyncio
    async def test_is_stale_true_after_file_modification(self, tracker, sample_project_dir):
        """Test that project becomes stale after file modification."""
        # Index project
        await tracker.update_metadata(
            project_name="test_project",
            total_files=3,
            total_units=15,
        )

        # Wait a bit
        await asyncio.sleep(0.1)

        # Modify a file (this will update its mtime)
        (sample_project_dir / "file1.py").write_text("print('modified')")

        # Check staleness
        is_stale = await tracker.is_stale("test_project", sample_project_dir)
        assert is_stale is True

    @pytest.mark.asyncio
    async def test_is_stale_handles_empty_directory(self, tracker, temp_db):
        """Test staleness check on empty directory."""
        empty_dir = Path(tempfile.mkdtemp())

        await tracker.update_metadata(
            project_name="test_project",
            total_files=0,
            total_units=0,
        )

        is_stale = await tracker.is_stale("test_project", empty_dir)
        assert is_stale is False

        # Cleanup
        empty_dir.rmdir()

    @pytest.mark.asyncio
    async def test_is_stale_handles_missing_directory(self, tracker):
        """Test staleness check on non-existent directory."""
        missing_dir = Path("/nonexistent/path")

        await tracker.update_metadata(
            project_name="test_project",
            total_files=0,
            total_units=0,
        )

        # Should not raise error, should return False
        is_stale = await tracker.is_stale("test_project", missing_dir)
        assert is_stale is False


class TestProjectIndexTrackerErrorHandling:
    """Test error handling."""

    @pytest.mark.asyncio
    async def test_operations_fail_without_initialization(self, temp_db):
        """Test that operations fail if not initialized."""
        config = ServerConfig(sqlite_path=str(temp_db))
        tracker = ProjectIndexTracker(config=config)

        with pytest.raises(StorageError) as exc_info:
            await tracker.is_indexed("test_project")
        assert "not initialized" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_get_metadata_fails_without_initialization(self, temp_db):
        """Test get_metadata fails without initialization."""
        config = ServerConfig(sqlite_path=str(temp_db))
        tracker = ProjectIndexTracker(config=config)

        with pytest.raises(StorageError):
            await tracker.get_metadata("test_project")

    @pytest.mark.asyncio
    async def test_update_metadata_fails_without_initialization(self, temp_db):
        """Test update_metadata fails without initialization."""
        config = ServerConfig(sqlite_path=str(temp_db))
        tracker = ProjectIndexTracker(config=config)

        with pytest.raises(StorageError):
            await tracker.update_metadata("test_project", 5, 25)


class TestProjectIndexTrackerMultipleProjects:
    """Test tracker with multiple projects."""

    @pytest.mark.asyncio
    async def test_multiple_projects_independent(self, tracker):
        """Test that multiple projects are tracked independently."""
        await tracker.update_metadata("project_a", 10, 50, is_watching=True)
        await tracker.update_metadata("project_b", 20, 100, is_watching=False)

        metadata_a = await tracker.get_metadata("project_a")
        metadata_b = await tracker.get_metadata("project_b")

        assert metadata_a.total_files == 10
        assert metadata_a.is_watching is True

        assert metadata_b.total_files == 20
        assert metadata_b.is_watching is False

    @pytest.mark.asyncio
    async def test_deleting_one_project_preserves_others(self, tracker):
        """Test that deleting one project doesn't affect others."""
        await tracker.update_metadata("project_a", 10, 50)
        await tracker.update_metadata("project_b", 20, 100)

        await tracker.delete_metadata("project_a")

        assert await tracker.is_indexed("project_a") is False
        assert await tracker.is_indexed("project_b") is True


class TestProjectIndexTrackerConcurrency:
    """Test concurrent operations."""

    @pytest.mark.asyncio
    async def test_concurrent_updates(self, tracker):
        """Test concurrent metadata updates."""
        async def update_project(name: str, files: int):
            await tracker.update_metadata(name, files, files * 5)

        # Update multiple projects concurrently
        await asyncio.gather(
            update_project("project_1", 10),
            update_project("project_2", 20),
            update_project("project_3", 30),
        )

        # Verify all updates succeeded
        metadata_1 = await tracker.get_metadata("project_1")
        metadata_2 = await tracker.get_metadata("project_2")
        metadata_3 = await tracker.get_metadata("project_3")

        assert metadata_1.total_files == 10
        assert metadata_2.total_files == 20
        assert metadata_3.total_files == 30
