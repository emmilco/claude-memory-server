"""Comprehensive tests for IndexingService."""

import pytest
import pytest_asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from src.memory.indexing_service import IndexingService
from src.config import ServerConfig


@pytest.fixture
def service_config():
    """Create test configuration."""
    return ServerConfig()


@pytest.fixture
def temp_watch_dir(tmp_path):
    """Create temporary directory for watching."""
    watch_dir = tmp_path / "watch"
    watch_dir.mkdir()
    (watch_dir / "test.py").write_text("def test(): pass")
    return watch_dir


@pytest_asyncio.fixture
async def service(temp_watch_dir, service_config):
    """Create IndexingService instance."""
    with patch("src.memory.indexing_service.IncrementalIndexer"):
        with patch("src.memory.indexing_service.FileWatcherService"):
            svc = IndexingService(
                watch_path=temp_watch_dir,
                project_name="test-project",
                config=service_config,
            )
            # Make indexer and watcher async-compatible
            svc.indexer = AsyncMock()
            svc.watcher = MagicMock()
            yield svc
            # Don't call close in fixture as tests handle it


class TestServiceInitialization:
    """Test IndexingService initialization."""

    def test_init_with_path(self, temp_watch_dir, service_config):
        """Test initialization with watch path."""
        with patch("src.memory.indexing_service.IncrementalIndexer"):
            with patch("src.memory.indexing_service.FileWatcherService"):
                service = IndexingService(
                    watch_path=temp_watch_dir,
                    project_name="test-project",
                    config=service_config,
                )

                assert service.watch_path == temp_watch_dir.resolve()
                assert service.project_name == "test-project"
                assert service.is_initialized is False

    def test_init_auto_project_name(self, temp_watch_dir):
        """Test automatic project name from directory."""
        with patch("src.memory.indexing_service.IncrementalIndexer"):
            with patch("src.memory.indexing_service.FileWatcherService"):
                service = IndexingService(
                    watch_path=temp_watch_dir,
                    project_name=None,
                )

                assert service.project_name == temp_watch_dir.name

    def test_init_with_default_config(self, temp_watch_dir):
        """Test initialization with default config."""
        with patch("src.memory.indexing_service.IncrementalIndexer"):
            with patch("src.memory.indexing_service.FileWatcherService"):
                service = IndexingService(
                    watch_path=temp_watch_dir,
                )

                assert service.config is not None


class TestServiceLifecycle:
    """Test service lifecycle (initialize, start, stop)."""

    @pytest.mark.asyncio
    async def test_initialize(self, service):
        """Test service initialization."""
        service.indexer = AsyncMock()

        await service.initialize()

        assert service.is_initialized is True
        service.indexer.initialize.assert_called_once()

    @pytest.mark.asyncio
    async def test_initialize_idempotent(self, service):
        """Test that initialize can be called multiple times safely."""
        service.indexer = AsyncMock()

        await service.initialize()
        await service.initialize()  # Should not reinitialize

        # Should only be called once
        service.indexer.initialize.assert_called_once()

    @pytest.mark.asyncio
    async def test_start(self, service):
        """Test starting the service."""
        service.indexer = AsyncMock()
        service.watcher = MagicMock()

        await service.start()

        assert service.is_initialized is True
        service.watcher.start.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_initializes_if_needed(self, service):
        """Test that start initializes if not already initialized."""
        service.indexer = AsyncMock()
        service.watcher = MagicMock()

        assert service.is_initialized is False

        await service.start()

        assert service.is_initialized is True
        service.indexer.initialize.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop(self, service):
        """Test stopping the service."""
        service.watcher = MagicMock()

        await service.stop()

        service.watcher.stop.assert_called_once()


class TestFileChangeCallback:
    """Test file change callback handling."""

    @pytest.mark.asyncio
    async def test_on_file_change_existing_file(self, service, temp_watch_dir):
        """Test callback when file is changed."""
        service.indexer = AsyncMock()
        service.indexer.index_file.return_value = {
            "units_indexed": 5,
            "parse_time_ms": 10.5,
            "skipped": False,
        }

        test_file = temp_watch_dir / "test.py"

        await service._on_file_change(test_file)

        service.indexer.index_file.assert_called_once_with(test_file)

    @pytest.mark.asyncio
    async def test_on_file_change_deleted_file(self, service, temp_watch_dir):
        """Test callback when file is deleted."""
        service.indexer = AsyncMock()
        service.indexer.delete_file_index.return_value = 3

        deleted_file = temp_watch_dir / "deleted.py"
        # File doesn't exist

        await service._on_file_change(deleted_file)

        service.indexer.delete_file_index.assert_called_once_with(deleted_file)

    @pytest.mark.asyncio
    async def test_on_file_change_skipped_file(self, service, temp_watch_dir):
        """Test callback when file is skipped during indexing."""
        service.indexer = AsyncMock()
        service.indexer.index_file.return_value = {
            "skipped": True,
        }

        test_file = temp_watch_dir / "test.py"

        await service._on_file_change(test_file)

        service.indexer.index_file.assert_called_once_with(test_file)

    @pytest.mark.asyncio
    async def test_on_file_change_error_handling(self, service, temp_watch_dir):
        """Test that callback handles errors gracefully."""
        service.indexer = AsyncMock()
        service.indexer.index_file.side_effect = Exception("Indexing error")

        test_file = temp_watch_dir / "test.py"

        # Should not raise
        await service._on_file_change(test_file)


class TestInitialIndexing:
    """Test initial directory indexing."""

    @pytest.mark.asyncio
    async def test_index_initial_recursive(self, service, temp_watch_dir):
        """Test initial indexing with recursion."""
        service.indexer = AsyncMock()
        service.indexer.index_directory.return_value = {
            "indexed_files": 5,
            "total_units": 25,
        }

        result = await service.index_initial(recursive=True)

        assert result["indexed_files"] == 5
        assert result["total_units"] == 25
        service.indexer.index_directory.assert_called_once_with(
            temp_watch_dir,
            recursive=True,
            show_progress=True,
        )

    @pytest.mark.asyncio
    async def test_index_initial_non_recursive(self, service, temp_watch_dir):
        """Test initial indexing without recursion."""
        service.indexer = AsyncMock()
        service.indexer.index_directory.return_value = {
            "indexed_files": 2,
            "total_units": 10,
        }

        result = await service.index_initial(recursive=False)

        assert result["indexed_files"] == 2
        service.indexer.index_directory.assert_called_once_with(
            temp_watch_dir,
            recursive=False,
            show_progress=True,
        )

    @pytest.mark.asyncio
    async def test_index_initial_initializes_if_needed(self, service):
        """Test that index_initial initializes if not already initialized."""
        service.indexer = AsyncMock()
        service.indexer.index_directory.return_value = {
            "indexed_files": 1,
            "total_units": 5,
        }

        assert service.is_initialized is False

        await service.index_initial()

        assert service.is_initialized is True
        service.indexer.initialize.assert_called_once()


class TestServiceClose:
    """Test service cleanup."""

    @pytest.mark.asyncio
    async def test_close(self, service):
        """Test closing the service."""
        service.watcher = MagicMock()
        service.indexer = AsyncMock()

        await service.close()

        service.watcher.stop.assert_called_once()
        service.indexer.close.assert_called_once()


class TestRunUntilStopped:
    """Test long-running service operation."""

    @pytest.mark.asyncio
    async def test_run_until_stopped_cancelled(self, service):
        """Test run_until_stopped handles cancellation."""
        service.watcher = MagicMock()
        service.indexer = AsyncMock()

        # Mock asyncio.sleep to raise CancelledError immediately
        with patch("asyncio.sleep", side_effect=asyncio.CancelledError()):
            await service.run_until_stopped()

        # Should have started and stopped
        service.watcher.start.assert_called_once()
        service.watcher.stop.assert_called_once()


class TestContextManager:
    """Test context manager functionality."""

    def test_context_manager_enter(self, temp_watch_dir):
        """Test context manager entry."""
        with patch("src.memory.indexing_service.IncrementalIndexer"):
            with patch("src.memory.indexing_service.FileWatcherService"):
                service = IndexingService(watch_path=temp_watch_dir)
                service.indexer = AsyncMock()
                service.watcher = MagicMock()

                with service as svc:
                    assert svc is service

    def test_context_manager_exit(self, temp_watch_dir):
        """Test context manager exit."""
        with patch("src.memory.indexing_service.IncrementalIndexer"):
            with patch("src.memory.indexing_service.FileWatcherService"):
                service = IndexingService(watch_path=temp_watch_dir)
                service.indexer = AsyncMock()
                service.watcher = MagicMock()

                # Use context manager
                with patch("asyncio.run") as mock_run:
                    with service:
                        pass

                # Should have called close via asyncio.run
                mock_run.assert_called_once()


import asyncio  # Add this import for the test
