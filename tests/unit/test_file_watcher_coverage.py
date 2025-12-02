"""Targeted tests for file_watcher.py uncovered lines."""

import pytest
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from watchdog.events import FileSystemEvent

from src.memory.file_watcher import DebouncedFileWatcher, FileWatcherService


class TestDebouncedFileWatcherCoverage:
    """Test uncovered paths in DebouncedFileWatcher."""

    @pytest.mark.asyncio
    async def test_should_process_non_file(self, tmp_path):
        """Test _should_process returns False for non-files (line 75)."""
        callback = AsyncMock()
        watcher = DebouncedFileWatcher(
            watch_path=tmp_path, callback=callback, debounce_ms=100, patterns={".py"}
        )

        # Test with directory
        dir_path = tmp_path / "subdir"
        dir_path.mkdir()

        assert watcher._should_process(dir_path) is False

        # Test with non-existent path
        non_existent = tmp_path / "does_not_exist.py"
        assert watcher._should_process(non_existent) is False

    @pytest.mark.asyncio
    async def test_compute_file_hash_error(self, tmp_path):
        """Test _compute_file_hash error handling (lines 85-87)."""
        callback = AsyncMock()
        watcher = DebouncedFileWatcher(
            watch_path=tmp_path, callback=callback, debounce_ms=100, patterns={".py"}
        )

        # Create a file but mock open to raise error
        test_file = tmp_path / "test.py"
        test_file.write_text("content")

        with patch("builtins.open", side_effect=PermissionError("Access denied")):
            result = watcher._compute_file_hash(test_file)

        assert result is None

    @pytest.mark.asyncio
    async def test_has_changed_hash_none(self, tmp_path):
        """Test _has_changed when hash computation fails (line 113)."""
        callback = AsyncMock()
        watcher = DebouncedFileWatcher(
            watch_path=tmp_path, callback=callback, debounce_ms=100, patterns={".py"}
        )

        test_file = tmp_path / "test.py"
        test_file.write_text("content")

        # Mock _compute_file_hash to return None
        with patch.object(watcher, "_compute_file_hash", return_value=None):
            result = watcher._has_changed(test_file)

        assert result is False

    @pytest.mark.asyncio
    async def test_has_changed_exception(self, tmp_path):
        """Test _has_changed exception handling (lines 123-125)."""
        callback = AsyncMock()
        watcher = DebouncedFileWatcher(
            watch_path=tmp_path, callback=callback, debounce_ms=100, patterns={".py"}
        )

        test_file = tmp_path / "test.py"
        test_file.write_text("content")

        # Mock stat to raise exception
        with patch.object(Path, "stat", side_effect=OSError("Stat failed")):
            result = watcher._has_changed(test_file)

        assert result is False

    @pytest.mark.asyncio
    async def test_on_modified_directory(self, tmp_path):
        """Test on_modified skips directories (line 129-130)."""
        callback = AsyncMock()
        watcher = DebouncedFileWatcher(
            watch_path=tmp_path, callback=callback, debounce_ms=100, patterns={".py"}
        )

        # Create directory event
        event = MagicMock(spec=FileSystemEvent)
        event.is_directory = True
        event.src_path = str(tmp_path / "subdir")

        watcher.on_modified(event)

        # Callback should not be triggered - use a short wait to verify no callbacks
        # NOTE: Sleep is necessary here to verify callback is NOT triggered
        await asyncio.sleep(0.15)  # Wait longer than debounce to ensure no callback
        callback.assert_not_called()

    @pytest.mark.asyncio
    async def test_on_modified_file(self, tmp_path):
        """Test on_modified processes files (lines 132-135)."""
        callback_event = asyncio.Event()
        callback = AsyncMock(side_effect=lambda path: callback_event.set())
        watcher = DebouncedFileWatcher(
            watch_path=tmp_path, callback=callback, debounce_ms=50, patterns={".py"}
        )

        # Create test file
        test_file = tmp_path / "test.py"
        test_file.write_text("initial")

        # Trigger modified event
        event = MagicMock(spec=FileSystemEvent)
        event.is_directory = False
        event.src_path = str(test_file)

        watcher.on_modified(event)

        # Wait for callback with timeout
        await asyncio.wait_for(callback_event.wait(), timeout=0.2)
        callback.assert_called_once()

    @pytest.mark.asyncio
    async def test_on_created_directory(self, tmp_path):
        """Test on_created skips directories (line 139-140)."""
        callback = AsyncMock()
        watcher = DebouncedFileWatcher(
            watch_path=tmp_path, callback=callback, debounce_ms=100, patterns={".py"}
        )

        # Create directory event
        event = MagicMock(spec=FileSystemEvent)
        event.is_directory = True
        event.src_path = str(tmp_path / "subdir")

        watcher.on_created(event)

        # Callback should not be triggered - use a short wait to verify no callbacks
        # NOTE: Sleep is necessary here to verify callback is NOT triggered
        await asyncio.sleep(0.15)  # Wait longer than debounce to ensure no callback
        callback.assert_not_called()

    @pytest.mark.asyncio
    async def test_on_created_file(self, tmp_path):
        """Test on_created processes files (lines 142-147)."""
        callback_event = asyncio.Event()
        callback = AsyncMock(side_effect=lambda path: callback_event.set())
        watcher = DebouncedFileWatcher(
            watch_path=tmp_path, callback=callback, debounce_ms=50, patterns={".py"}
        )

        # Create test file
        test_file = tmp_path / "new_file.py"
        test_file.write_text("new content")

        # Trigger created event
        event = MagicMock(spec=FileSystemEvent)
        event.is_directory = False
        event.src_path = str(test_file)

        watcher.on_created(event)

        # Wait for callback with timeout
        await asyncio.wait_for(callback_event.wait(), timeout=0.2)
        callback.assert_called_once()

    @pytest.mark.asyncio
    async def test_on_deleted_directory(self, tmp_path):
        """Test on_deleted skips directories (line 151-152)."""
        callback = AsyncMock()
        watcher = DebouncedFileWatcher(
            watch_path=tmp_path, callback=callback, debounce_ms=100, patterns={".py"}
        )

        # Create directory event
        event = MagicMock(spec=FileSystemEvent)
        event.is_directory = True
        event.src_path = str(tmp_path / "subdir")

        watcher.on_deleted(event)

        # Nothing should happen
        assert len(watcher.file_hashes) == 0

    @pytest.mark.asyncio
    async def test_on_deleted_file(self, tmp_path):
        """Test on_deleted removes file from tracking (lines 154-158)."""
        callback = AsyncMock()
        watcher = DebouncedFileWatcher(
            watch_path=tmp_path, callback=callback, debounce_ms=100, patterns={".py"}
        )

        test_file = tmp_path / "to_delete.py"

        # Add file to hash tracking manually
        watcher.file_hashes[test_file] = "dummy_hash"

        # Trigger deleted event
        event = MagicMock(spec=FileSystemEvent)
        event.is_directory = False
        event.src_path = str(test_file)

        watcher.on_deleted(event)

        # File should be removed from tracking
        assert test_file not in watcher.file_hashes

    @pytest.mark.asyncio
    async def test_execute_debounced_callback_empty_files(self, tmp_path):
        """Test _execute_debounced_callback with empty pending files (line 189)."""
        callback = AsyncMock()
        watcher = DebouncedFileWatcher(
            watch_path=tmp_path, callback=callback, debounce_ms=10, patterns={".py"}
        )

        # Call with no pending files
        await watcher._execute_debounced_callback()

        # Callback should not be called
        callback.assert_not_called()

    @pytest.mark.asyncio
    async def test_callback_error_handling(self, tmp_path):
        """Test error handling in callback execution (lines 203-205)."""
        callback_event = asyncio.Event()

        # Create callback that raises error but signals completion
        async def error_callback(path):
            callback_event.set()
            raise RuntimeError("Callback failed")

        callback = AsyncMock(side_effect=error_callback)

        watcher = DebouncedFileWatcher(
            watch_path=tmp_path, callback=callback, debounce_ms=50, patterns={".py"}
        )

        test_file = tmp_path / "test.py"
        test_file.write_text("content")

        # Trigger event
        event = MagicMock(spec=FileSystemEvent)
        event.is_directory = False
        event.src_path = str(test_file)

        watcher.on_modified(event)

        # Wait for callback with timeout
        await asyncio.wait_for(callback_event.wait(), timeout=0.2)

        # Callback should have been called despite error
        callback.assert_called_once()

    @pytest.mark.asyncio
    async def test_sync_callback_support(self, tmp_path):
        """Test that sync callbacks are supported (line 203)."""
        # Create sync callback
        sync_callback = MagicMock()

        watcher = DebouncedFileWatcher(
            watch_path=tmp_path,
            callback=sync_callback,
            debounce_ms=50,
            patterns={".py"},
        )

        test_file = tmp_path / "test.py"
        test_file.write_text("content")

        # Add to pending files
        async with watcher.pending_lock:
            watcher.pending_files.add(test_file)

        # Execute callback
        await watcher._execute_debounced_callback()

        # Sync callback should have been called
        sync_callback.assert_called_once_with(test_file)


class TestFileWatcherServiceCoverage:
    """Test uncovered paths in FileWatcherService."""

    def test_start_already_running(self, tmp_path):
        """Test start when already running (lines 258-259)."""
        callback = MagicMock()
        service = FileWatcherService(watch_path=tmp_path, callback=callback)

        # Start once
        service.start()
        assert service.is_running is True

        # Try to start again - should log warning
        service.start()

        # Should still be running
        assert service.is_running is True

        # Cleanup
        service.stop()

    def test_stop_not_running(self, tmp_path):
        """Test stop when not running (line 268)."""
        callback = MagicMock()
        service = FileWatcherService(watch_path=tmp_path, callback=callback)

        # Service should not be running initially
        assert service.is_running is False

        # Stop should return early without error
        service.stop()

        # Should still not be running
        assert service.is_running is False

    @pytest.mark.asyncio
    async def test_start_async(self, tmp_path):
        """Test start_async method (lines 277-278, 280-282)."""
        callback = AsyncMock()
        service = FileWatcherService(watch_path=tmp_path, callback=callback)

        # Start async and cancel after short time
        task = asyncio.create_task(service.start_async())

        # Let it run briefly to ensure it starts
        # NOTE: Sleep is necessary here to allow service to initialize
        await asyncio.sleep(0.1)

        # Service should be running
        assert service.is_running is True

        # Cancel the task
        task.cancel()

        # Wait for cancellation
        try:
            await task
        except asyncio.CancelledError:
            pass

        # Service should be stopped
        assert service.is_running is False

    @pytest.mark.asyncio
    async def test_start_async_cancellation(self, tmp_path):
        """Test start_async cancellation handling (lines 283-285)."""
        callback = AsyncMock()
        service = FileWatcherService(watch_path=tmp_path, callback=callback)

        # Start async
        task = asyncio.create_task(service.start_async())
        # NOTE: Sleep is necessary here to allow service to initialize before cancellation
        await asyncio.sleep(0.05)

        # Cancel
        task.cancel()

        # Should raise CancelledError and stop service
        with pytest.raises(asyncio.CancelledError):
            await task

        # Service should be stopped
        assert service.is_running is False

    def test_context_manager_exit(self, tmp_path):
        """Test context manager __exit__ (line 299)."""
        callback = MagicMock()

        # Use context manager
        with FileWatcherService(watch_path=tmp_path, callback=callback) as service:
            # Should be running inside context
            assert service.is_running is True

        # Should be stopped after exiting
        assert service.is_running is False
