"""Tests for file watcher functionality."""

import pytest
import asyncio
import tempfile
from pathlib import Path

from src.memory.file_watcher import DebouncedFileWatcher, FileWatcherService


@pytest.fixture
def temp_watch_dir():
    """Create temporary directory for watching."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def changed_files():
    """Track files that triggered callbacks."""
    files = []
    return files


@pytest.mark.asyncio
async def test_file_watcher_detects_changes(temp_watch_dir, changed_files):
    """Test that file watcher detects file modifications via direct debounce call."""

    callback_event = asyncio.Event()

    async def callback(file_path: Path):
        changed_files.append(file_path)
        callback_event.set()

    # Create watcher (without full observer for unit test)
    watcher = DebouncedFileWatcher(
        watch_path=temp_watch_dir,
        callback=callback,
        patterns={".txt"},
        debounce_ms=100,
    )

    # Create and modify a test file
    test_file = temp_watch_dir / "test.txt"
    test_file.write_text("initial content")

    # Manually trigger debounce callback (simulating file change event)
    await watcher._debounce_callback(test_file)

    # Wait for callback with timeout (debounce is 100ms, so 500ms is generous)
    await asyncio.wait_for(callback_event.wait(), timeout=0.5)

    # Should have detected the change
    assert len(changed_files) >= 1
    assert changed_files[0] == test_file


@pytest.mark.asyncio
async def test_file_watcher_debouncing(temp_watch_dir, changed_files):
    """Test that debouncing prevents excessive callbacks."""

    callback_event = asyncio.Event()

    async def callback(file_path: Path):
        changed_files.append(file_path)
        callback_event.set()

    watcher = DebouncedFileWatcher(
        watch_path=temp_watch_dir,
        callback=callback,
        patterns={".txt"},
        debounce_ms=200,
    )

    # Create test file
    test_file = temp_watch_dir / "test.txt"
    test_file.write_text("v1")

    # Simulate rapid changes
    # NOTE: Sleep is necessary here to test debounce timing behavior
    for i in range(5):
        test_file.write_text(f"version {i}")
        await watcher._debounce_callback(test_file)
        await asyncio.sleep(0.05)  # 50ms between changes - tests debounce window

    # Wait for debounce to complete (200ms + buffer)
    await asyncio.wait_for(callback_event.wait(), timeout=0.5)

    # Should have debounced to exactly 1 callback
    # (all 5 rapid changes within 250ms total should trigger only 1 final callback)
    assert (
        len(changed_files) == 1
    ), f"Expected 1 callback after debouncing, got {len(changed_files)}"
    assert changed_files[0] == test_file


@pytest.mark.skip_ci(reason="File I/O timing sensitive in CI environment")
def test_file_hash_detection(temp_watch_dir):
    """Test that file hash correctly detects content changes."""

    async def callback(file_path: Path):
        pass

    watcher = DebouncedFileWatcher(
        watch_path=temp_watch_dir,
        callback=callback,
        patterns={".txt"},
    )

    test_file = temp_watch_dir / "test.txt"
    test_file.write_text("content")

    # First hash
    assert watcher._has_changed(test_file) is True

    # Same content - should not detect change
    assert watcher._has_changed(test_file) is False

    # Modify content
    test_file.write_text("new content")
    assert watcher._has_changed(test_file) is True


def test_pattern_filtering(temp_watch_dir):
    """Test that only matching file patterns are processed."""

    async def callback(file_path: Path):
        pass

    watcher = DebouncedFileWatcher(
        watch_path=temp_watch_dir,
        callback=callback,
        patterns={".py", ".js"},
    )

    # Python file - should process
    py_file = temp_watch_dir / "test.py"
    py_file.write_text("print('hello')")
    assert watcher._should_process(py_file) is True

    # JavaScript file - should process
    js_file = temp_watch_dir / "test.js"
    js_file.write_text("console.log('hello')")
    assert watcher._should_process(js_file) is True

    # Text file - should NOT process
    txt_file = temp_watch_dir / "test.txt"
    txt_file.write_text("hello")
    assert watcher._should_process(txt_file) is False


def test_service_start_stop(temp_watch_dir):
    """Test that service starts and stops correctly."""

    async def callback(file_path: Path):
        pass

    service = FileWatcherService(
        watch_path=temp_watch_dir,
        callback=callback,
    )

    assert service.is_running is False

    service.start()
    assert service.is_running is True

    service.stop()
    assert service.is_running is False


def test_context_manager(temp_watch_dir):
    """Test that context manager works."""

    async def callback(file_path: Path):
        pass

    with FileWatcherService(temp_watch_dir, callback) as service:
        assert service.is_running is True

    assert service.is_running is False
