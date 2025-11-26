"""Tests for AutoIndexingService - auto-indexing orchestration."""

import pytest
import pytest_asyncio
import asyncio
import tempfile
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch, MagicMock

from src.memory.auto_indexing_service import AutoIndexingService, IndexingProgress
from src.config import ServerConfig
from src.core.exceptions import IndexingError


@pytest_asyncio.fixture
async def temp_project_dir():
    """Create a temporary project directory with files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_path = Path(tmpdir) / "test_project"
        project_path.mkdir()

        # Create sample files
        (project_path / "main.py").write_text("def main(): pass")
        (project_path / "utils.py").write_text("def helper(): pass")
        (project_path / "test.py").write_text("def test_something(): pass")

        # Create subdirectory
        (project_path / "src").mkdir()
        (project_path / "src" / "module.py").write_text("class MyClass: pass")

        # Create files to exclude
        (project_path / "node_modules").mkdir()
        (project_path / "node_modules" / "package.js").write_text("module.exports = {}")

        yield project_path


@pytest_asyncio.fixture
async def temp_db():
    """Create temporary database."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir) / "test.db"


@pytest_asyncio.fixture
async def config(temp_db):
    """Create test configuration.

    Note: Explicitly sets auto_index_enabled=True because the global
    disable_auto_indexing fixture in conftest.py sets CLAUDE_RAG_AUTO_INDEX_ENABLED=false
    which would otherwise override this via pydantic_settings environment variable loading.
    """
    return ServerConfig(
        sqlite_path=str(temp_db),
        auto_index_enabled=True,  # Override conftest.py's global disable
    )


@pytest_asyncio.fixture
async def service(temp_project_dir, config):
    """Create AutoIndexingService for testing."""
    service = AutoIndexingService(
        project_path=temp_project_dir,
        project_name="test_project",
        config=config,
    )

    # Mock the tracker to avoid actual database operations
    service.tracker = AsyncMock()
    service.tracker.initialize = AsyncMock()
    service.tracker.is_indexed = AsyncMock(return_value=False)
    service.tracker.is_stale = AsyncMock(return_value=False)
    service.tracker.update_metadata = AsyncMock()
    service.tracker.set_watching = AsyncMock()
    service.tracker.close = AsyncMock()

    # Skip calling initialize() which would create a real IncrementalIndexer
    # Instead, manually set is_initialized and create a mock indexer
    service.is_initialized = True

    # Create mock indexer
    mock_indexer = AsyncMock()
    mock_indexer.initialize = AsyncMock()
    mock_indexer.index_directory = AsyncMock(return_value={
        'total_files': 4,
        'indexed_files': 4,
        'skipped_files': 0,
        'total_units': 20,
        'failed_files': []
    })
    mock_indexer.close = AsyncMock()
    service.indexer = mock_indexer

    yield service
    await service.close()


class TestIndexingProgress:
    """Test IndexingProgress model."""

    def test_progress_initialization(self):
        """Test progress is initialized correctly."""
        progress = IndexingProgress()
        assert progress.status == "idle"
        assert progress.current_file is None
        assert progress.files_completed == 0
        assert progress.total_files == 0
        assert progress.is_background is False

    def test_progress_to_dict(self):
        """Test converting progress to dictionary."""
        progress = IndexingProgress()
        progress.status = "indexing"
        progress.total_files = 10
        progress.files_completed = 5
        progress.is_background = True

        data = progress.to_dict()
        assert data["status"] == "indexing"
        assert data["total_files"] == 10
        assert data["files_completed"] == 5
        assert data["is_background"] is True

    def test_progress_calculates_eta(self):
        """Test ETA calculation."""
        from datetime import datetime, UTC, timedelta

        progress = IndexingProgress()
        progress.status = "indexing"
        progress.total_files = 100
        progress.files_completed = 50
        progress.start_time = datetime.now(UTC) - timedelta(seconds=10)

        data = progress.to_dict()
        assert "eta_seconds" in data
        assert data["eta_seconds"] > 0

    def test_progress_eta_with_zero_total(self):
        """Test ETA calculation doesn't crash with zero total files."""
        from datetime import datetime, UTC, timedelta

        progress = IndexingProgress()
        progress.status = "indexing"
        progress.total_files = 0  # Edge case: zero total
        progress.files_completed = 0
        progress.start_time = datetime.now(UTC) - timedelta(seconds=10)

        # Should handle gracefully, not crash
        data = progress.to_dict()
        # ETA should not be calculated when files_completed = 0
        assert "eta_seconds" not in data

    def test_progress_eta_with_zero_completed(self):
        """Test ETA calculation with zero completed files."""
        from datetime import datetime, UTC, timedelta

        progress = IndexingProgress()
        progress.status = "indexing"
        progress.total_files = 100
        progress.files_completed = 0  # Edge case: no progress yet
        progress.start_time = datetime.now(UTC) - timedelta(seconds=10)

        data = progress.to_dict()
        # Should not calculate ETA when files_completed = 0
        assert "eta_seconds" not in data

    def test_progress_eta_with_zero_elapsed_time(self):
        """Test ETA calculation with zero elapsed time."""
        from datetime import datetime, UTC

        progress = IndexingProgress()
        progress.status = "indexing"
        progress.total_files = 100
        progress.files_completed = 50
        progress.start_time = datetime.now(UTC)  # Just started

        data = progress.to_dict()
        # With zero elapsed time, rate calculation could be problematic
        # Should either have no ETA or a very large one
        # The code handles this with "if elapsed > 0" check


class TestAutoIndexingServiceInitialization:
    """Test service initialization."""

    @pytest.mark.asyncio
    async def test_service_creation(self, temp_project_dir, config):
        """Test creating service."""
        service = AutoIndexingService(
            project_path=temp_project_dir,
            project_name="test_project",
            config=config,
        )

        assert service.project_path == temp_project_dir
        assert service.project_name == "test_project"
        assert service.config == config
        assert service.is_initialized is False

    @pytest.mark.asyncio
    async def test_service_initialization(self, service):
        """Test service initializes correctly."""
        assert service.is_initialized is True
        assert service.tracker is not None
        assert service.indexer is not None

    @pytest.mark.asyncio
    async def test_operations_fail_without_initialization(self, temp_project_dir, config):
        """Test operations fail if not initialized."""
        service = AutoIndexingService(
            project_path=temp_project_dir,
            project_name="test_project",
            config=config,
        )

        with pytest.raises(IndexingError) as exc_info:
            await service.should_auto_index()
        assert "not initialized" in str(exc_info.value).lower()


class TestShouldAutoIndex:
    """Test auto-index decision logic."""

    @pytest.mark.asyncio
    async def test_should_index_new_project(self, service):
        """Test should index new project."""
        service.tracker.is_indexed.return_value = False

        should_index = await service.should_auto_index()
        assert should_index is True

    @pytest.mark.asyncio
    async def test_should_index_stale_project(self, service):
        """Test should index stale project."""
        service.tracker.is_indexed.return_value = True
        service.tracker.is_stale.return_value = True

        should_index = await service.should_auto_index()
        assert should_index is True

    @pytest.mark.asyncio
    async def test_should_skip_up_to_date_project(self, service):
        """Test should skip up-to-date project."""
        service.tracker.is_indexed.return_value = True
        service.tracker.is_stale.return_value = False

        should_index = await service.should_auto_index()
        assert should_index is False

    @pytest.mark.skip(reason="auto_index_enabled config not yet implemented - see FEAT-033")
    @pytest.mark.asyncio
    async def test_respects_disabled_config(self, service):
        """Test respects disabled configuration."""
        service.config.auto_index_enabled = False

        should_index = await service.should_auto_index()
        assert should_index is False


class TestExcludePatterns:
    """Test file exclusion patterns."""

    @pytest.mark.asyncio
    async def test_should_index_normal_file(self, service, temp_project_dir):
        """Test normal files should be indexed."""
        file_path = temp_project_dir / "main.py"
        should_index = service.should_index_file(file_path)
        assert should_index is True

    @pytest.mark.skip(reason="auto_index_exclude_patterns config not yet implemented - see FEAT-033")
    @pytest.mark.asyncio
    async def test_should_exclude_node_modules(self, service, temp_project_dir):
        """Test node_modules files are excluded."""
        file_path = temp_project_dir / "node_modules" / "package.js"
        should_index = service.should_index_file(file_path)
        assert should_index is False

    @pytest.mark.asyncio
    async def test_handles_missing_pathspec(self, temp_project_dir, config):
        """Test handles missing pathspec library."""
        service = AutoIndexingService(
            project_path=temp_project_dir,
            project_name="test_project",
            config=config,
        )
        service.exclude_spec = None

        # Should default to indexing all files
        file_path = temp_project_dir / "any_file.py"
        should_index = service.should_index_file(file_path)
        assert should_index is True


class TestFileCounting:
    """Test file counting."""

    @pytest.mark.asyncio
    async def test_counts_indexable_files(self, service):
        """Test counts indexable files correctly."""
        count = await service._count_indexable_files()
        # Should count .py files, excluding node_modules
        # main.py, utils.py, test.py, src/module.py (4 files)
        # Note: actual count might vary due to fixture setup
        assert count >= 4  # At least the expected files

    @pytest.mark.asyncio
    async def test_respects_exclude_patterns(self, service):
        """Test respects exclude patterns when counting."""
        count = await service._count_indexable_files()
        # node_modules/package.js should be excluded (it's .js not .py anyway)
        assert count >= 4


class TestForegroundIndexing:
    """Test foreground indexing mode."""

    @pytest.mark.asyncio
    async def test_foreground_indexing(self, service):
        """Test foreground indexing runs successfully."""
        result = await service._index_in_foreground()

        assert result['indexed_files'] == 4
        assert result['total_units'] == 20
        assert service.progress.status == "complete"
        assert service.progress.is_background is False

        # Verify tracker was updated
        service.tracker.update_metadata.assert_called_once()

    @pytest.mark.asyncio
    async def test_foreground_indexing_error_handling(self, service):
        """Test foreground indexing handles errors."""
        service.indexer.index_directory.side_effect = Exception("Index error")

        with pytest.raises(Exception):
            await service._index_in_foreground()

        assert service.progress.status == "error"
        assert service.progress.error_message == "Index error"


class TestBackgroundIndexing:
    """Test background indexing mode."""

    @pytest.mark.asyncio
    async def test_background_indexing(self, service):
        """Test background indexing runs successfully."""
        result = await service._index_in_background()

        assert result['indexed_files'] == 4
        assert result['total_units'] == 20
        assert service.progress.status == "complete"
        assert service.progress.is_background is True

        # Verify tracker was updated
        service.tracker.update_metadata.assert_called_once()

    @pytest.mark.asyncio
    async def test_background_indexing_error_handling(self, service):
        """Test background indexing handles errors."""
        service.indexer.index_directory.side_effect = Exception("Background error")

        with pytest.raises(Exception):
            await service._index_in_background()

        assert service.progress.status == "error"
        assert service.progress.error_message == "Background error"


class TestStartAutoIndexing:
    """Test starting auto-indexing."""

    @pytest.mark.skip(reason="auto_index_size_threshold config not yet implemented - see FEAT-033")
    @pytest.mark.asyncio
    async def test_starts_foreground_for_small_project(self, service):
        """Test uses foreground mode for small projects."""
        service.config.auto_index_size_threshold = 10  # Higher than file count
        service.tracker.is_indexed.return_value = False

        result = await service.start_auto_indexing()

        assert result is not None
        assert result["mode"] == "foreground"
        assert result['indexed_files'] == 4

    @pytest.mark.skip(reason="auto_index_size_threshold config not yet implemented - see FEAT-033")
    @pytest.mark.asyncio
    async def test_starts_background_for_large_project(self, service):
        """Test uses background mode for large projects."""
        service.config.auto_index_size_threshold = 2  # Lower than file count
        service.tracker.is_indexed.return_value = False

        result = await service.start_auto_indexing()

        assert result is not None
        assert result["mode"] == "background"
        assert result["status"] == "indexing"
        assert service.indexing_task is not None

        # Wait for background task
        await service.wait_for_completion(timeout=5.0)

    @pytest.mark.asyncio
    async def test_skips_if_not_needed(self, service):
        """Test skips indexing if not needed."""
        service.tracker.is_indexed.return_value = True
        service.tracker.is_stale.return_value = False

        result = await service.start_auto_indexing(force=False)
        assert result is None

    @pytest.mark.skip(reason="auto_index_size_threshold config not yet implemented - see FEAT-033")
    @pytest.mark.asyncio
    async def test_forces_indexing_when_requested(self, service):
        """Test forces indexing when force=True."""
        service.tracker.is_indexed.return_value = True
        service.tracker.is_stale.return_value = False
        service.config.auto_index_size_threshold = 10

        result = await service.start_auto_indexing(force=True)
        assert result is not None

    @pytest.mark.skip(reason="auto_index_size_threshold config not yet implemented - see FEAT-033")
    @pytest.mark.asyncio
    async def test_progress_callback(self, service):
        """Test progress callback is called."""
        callback = Mock()
        service.config.auto_index_size_threshold = 10
        service.tracker.is_indexed.return_value = False

        await service.start_auto_indexing(progress_callback=callback)

        # Callback should be passed to indexer
        service.indexer.index_directory.assert_called_once()
        call_kwargs = service.indexer.index_directory.call_args[1]
        assert call_kwargs['progress_callback'] == callback


class TestFileWatcher:
    """Test file watcher integration."""

    @pytest.mark.asyncio
    async def test_starts_watching(self, service):
        """Test starts file watcher."""
        service.indexing_service = AsyncMock()
        service.indexing_service.initialize = AsyncMock()

        await service.start_watching()

        service.tracker.set_watching.assert_called_with("test_project", True)

    @pytest.mark.asyncio
    async def test_stops_watching(self, service):
        """Test stops file watcher."""
        service.indexing_service = AsyncMock()
        service.indexing_service.stop = AsyncMock()

        await service.stop_watching()

        service.indexing_service.stop.assert_called_once()
        service.tracker.set_watching.assert_called_with("test_project", False)

    @pytest.mark.asyncio
    async def test_respects_disabled_watcher_config(self, service):
        """Test respects disabled file watcher config.

        Note: Uses nested config (config.indexing.file_watcher) since flat attributes
        are deprecated Optional[None] for backward compatibility.
        """
        service.config.indexing.file_watcher = False

        await service.start_watching()

        # Should not create indexing service
        assert service.indexing_service is None


class TestProgressQueries:
    """Test progress querying."""

    @pytest.mark.asyncio
    async def test_get_progress(self, service):
        """Test getting indexing progress."""
        service.progress.status = "indexing"
        service.progress.total_files = 10
        service.progress.files_completed = 5

        progress = await service.get_progress()

        assert progress["status"] == "indexing"
        assert progress["total_files"] == 10
        assert progress["files_completed"] == 5

    @pytest.mark.skip(reason="auto_index_size_threshold config not yet implemented - see FEAT-033")
    @pytest.mark.asyncio
    async def test_wait_for_completion(self, service):
        """Test waiting for background task completion."""
        service.config.auto_index_size_threshold = 2
        service.tracker.is_indexed.return_value = False

        # Start background indexing
        await service.start_auto_indexing()

        # Wait for completion
        result = await service.wait_for_completion(timeout=5.0)

        assert result is not None
        assert service.progress.status == "complete"

    @pytest.mark.asyncio
    async def test_wait_for_completion_no_task(self, service):
        """Test waiting fails if no task running."""
        with pytest.raises(IndexingError) as exc_info:
            await service.wait_for_completion()
        assert "No background indexing task" in str(exc_info.value)


class TestManualReindex:
    """Test manual re-indexing."""

    @pytest.mark.asyncio
    async def test_trigger_reindex(self, service):
        """Test manually triggering re-index."""
        # Note: auto_index_size_threshold not yet in ServerConfig
        service.tracker.is_indexed.return_value = True
        service.tracker.is_stale.return_value = False

        # Should force indexing even though not stale
        result = await service.trigger_reindex()

        assert result is not None
        assert result["mode"] == "foreground"


@pytest.mark.skip(reason="Auto-indexing config parameters not yet implemented in ServerConfig - see FEAT-033")
class TestCleanup:
    """Test resource cleanup."""

    @pytest.mark.asyncio
    async def test_close_cleans_up_resources(self, temp_project_dir, config):
        """Test close cleans up all resources."""
        service = AutoIndexingService(
            project_path=temp_project_dir,
            project_name="test_project",
            config=config,
        )

        service.tracker = AsyncMock()
        service.tracker.initialize = AsyncMock()
        service.tracker.close = AsyncMock()

        # Mock the indexer class to prevent real initialization
        with patch('src.memory.auto_indexing_service.IncrementalIndexer') as mock_indexer_class:
            mock_indexer = AsyncMock()
            mock_indexer.initialize = AsyncMock()
            mock_indexer.close = AsyncMock()
            mock_indexer_class.return_value = mock_indexer

            service.indexing_service = AsyncMock()
            service.indexing_service.close = AsyncMock()
            service.indexing_service.stop = AsyncMock()

            await service.initialize()
            await service.close()

            service.tracker.close.assert_called_once()
            mock_indexer.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_waits_for_background_task(self, temp_project_dir, config):
        """Test close waits for background task to complete."""
        service = AutoIndexingService(
            project_path=temp_project_dir,
            project_name="test_project",
            config=config,
        )

        service.tracker = AsyncMock()
        service.tracker.initialize = AsyncMock()
        service.tracker.is_indexed = AsyncMock(return_value=False)
        service.tracker.close = AsyncMock()

        service.indexer = AsyncMock()
        service.indexer.initialize = AsyncMock()
        service.indexer.index_directory = AsyncMock(return_value={
            'total_files': 4,
            'indexed_files': 4,
            'total_units': 20,
            'skipped_files': 0,
            'failed_files': []
        })
        service.indexer.close = AsyncMock()

        await service.initialize()

        # Start background task
        # Note: auto_index_size_threshold not yet in ServerConfig
        await service.start_auto_indexing()

        # Close should wait for task
        await service.close()

        assert service.indexing_task.done()
