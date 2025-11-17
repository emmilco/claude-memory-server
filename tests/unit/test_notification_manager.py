"""Unit tests for NotificationManager."""

import pytest
import asyncio
from typing import List, Tuple

from src.memory.notification_manager import (
    NotificationManager,
    NotificationBackend,
    ConsoleNotificationBackend,
    LogNotificationBackend,
    CallbackNotificationBackend,
)


class TestNotificationBackend(NotificationBackend):
    """Test backend that records notifications."""

    def __init__(self):
        """Initialize test backend."""
        self.notifications: List[Tuple[str, str, str]] = []

    async def notify(self, title: str, message: str, level: str = "info") -> None:
        """Record notification."""
        self.notifications.append((title, message, level))


@pytest.fixture
def test_backend():
    """Create test backend."""
    return TestNotificationBackend()


@pytest.fixture
def manager(test_backend):
    """Create notification manager with test backend."""
    return NotificationManager(backends=[test_backend])


@pytest.mark.asyncio
async def test_notify_started(manager, test_backend):
    """Test started notification."""
    await manager.notify_started(
        job_id="job123",
        project_name="test-project",
        directory="/test/dir",
        total_files=100,
    )

    assert len(test_backend.notifications) == 1
    title, message, level = test_backend.notifications[0]

    assert "test-project" in title
    assert "Started" in title or "🚀" in title
    assert "100" in message
    assert "/test/dir" in message
    assert "job123" in message
    assert level == "info"


@pytest.mark.asyncio
async def test_notify_started_no_total(manager, test_backend):
    """Test started notification without total files."""
    await manager.notify_started(
        job_id="job123",
        project_name="test-project",
        directory="/test/dir",
    )

    assert len(test_backend.notifications) == 1
    title, message, level = test_backend.notifications[0]

    assert "test-project" in title
    assert "/test/dir" in message


@pytest.mark.asyncio
async def test_notify_progress(manager, test_backend):
    """Test progress notification."""
    await manager.notify_progress(
        job_id="job123",
        project_name="test-project",
        indexed_files=50,
        total_files=100,
        total_units=150,
        current_file="test.py",
    )

    assert len(test_backend.notifications) == 1
    title, message, level = test_backend.notifications[0]

    assert "test-project" in title
    assert "Progress" in title or "⏳" in title
    assert "50" in message
    assert "100" in message
    assert "50.0%" in message
    assert "150" in message
    assert "test.py" in message
    assert level == "info"


@pytest.mark.asyncio
async def test_notify_progress_throttling(manager, test_backend):
    """Test that progress notifications are throttled."""
    # Send multiple progress notifications quickly
    for i in range(5):
        await manager.notify_progress(
            job_id="job123",
            project_name="test-project",
            indexed_files=i * 20,
            total_files=100,
            total_units=i * 60,
        )

    # Should only have 1 notification (first one, rest throttled)
    assert len(test_backend.notifications) == 1


@pytest.mark.asyncio
async def test_notify_progress_throttling_different_jobs(manager, test_backend):
    """Test that throttling is per-job."""
    await manager.notify_progress(
        job_id="job1",
        project_name="project1",
        indexed_files=50,
        total_files=100,
        total_units=150,
    )

    await manager.notify_progress(
        job_id="job2",
        project_name="project2",
        indexed_files=30,
        total_files=100,
        total_units=90,
    )

    # Should have 2 notifications (different jobs)
    assert len(test_backend.notifications) == 2


@pytest.mark.asyncio
async def test_notify_completed(manager, test_backend):
    """Test completed notification."""
    await manager.notify_completed(
        job_id="job123",
        project_name="test-project",
        indexed_files=100,
        total_units=300,
        elapsed_seconds=45.5,
        failed_files=2,
    )

    assert len(test_backend.notifications) == 1
    title, message, level = test_backend.notifications[0]

    assert "test-project" in title
    assert "Complete" in title or "✅" in title
    assert "100" in message
    assert "300" in message
    assert "45.5" in message
    assert "2" in message  # failed files
    assert level == "success"


@pytest.mark.asyncio
async def test_notify_completed_no_failures(manager, test_backend):
    """Test completed notification with no failures."""
    await manager.notify_completed(
        job_id="job123",
        project_name="test-project",
        indexed_files=100,
        total_units=300,
        elapsed_seconds=45.5,
    )

    assert len(test_backend.notifications) == 1
    title, message, level = test_backend.notifications[0]

    assert "test-project" in title
    assert "Complete" in title or "✅" in title


@pytest.mark.asyncio
async def test_notify_paused(manager, test_backend):
    """Test paused notification."""
    await manager.notify_paused(
        job_id="job123",
        project_name="test-project",
        indexed_files=50,
        total_files=100,
    )

    assert len(test_backend.notifications) == 1
    title, message, level = test_backend.notifications[0]

    assert "test-project" in title
    assert "Paused" in title or "⏸" in title
    assert "50" in message
    assert "100" in message
    assert "50.0%" in message
    assert "job123" in message
    assert level == "warning"


@pytest.mark.asyncio
async def test_notify_resumed(manager, test_backend):
    """Test resumed notification."""
    await manager.notify_resumed(
        job_id="job123",
        project_name="test-project",
        indexed_files=50,
        remaining_files=50,
    )

    assert len(test_backend.notifications) == 1
    title, message, level = test_backend.notifications[0]

    assert "test-project" in title
    assert "Resumed" in title or "▶" in title
    assert "50" in message
    assert "job123" in message
    assert level == "info"


@pytest.mark.asyncio
async def test_notify_failed(manager, test_backend):
    """Test failed notification."""
    await manager.notify_failed(
        job_id="job123",
        project_name="test-project",
        error_message="Connection failed",
        indexed_files=30,
        total_files=100,
    )

    assert len(test_backend.notifications) == 1
    title, message, level = test_backend.notifications[0]

    assert "test-project" in title
    assert "Failed" in title or "❌" in title
    assert "Connection failed" in message
    assert "30" in message
    assert "100" in message
    assert "job123" in message
    assert level == "error"


@pytest.mark.asyncio
async def test_notify_cancelled(manager, test_backend):
    """Test cancelled notification."""
    await manager.notify_cancelled(
        job_id="job123",
        project_name="test-project",
        indexed_files=40,
        total_files=100,
    )

    assert len(test_backend.notifications) == 1
    title, message, level = test_backend.notifications[0]

    assert "test-project" in title
    assert "Cancelled" in title or "🛑" in title
    assert "40" in message
    assert "100" in message
    assert "job123" in message
    assert level == "warning"


@pytest.mark.asyncio
async def test_multiple_backends(test_backend):
    """Test notifications sent to multiple backends."""
    backend2 = TestNotificationBackend()
    manager = NotificationManager(backends=[test_backend, backend2])

    await manager.notify_started(
        job_id="job123",
        project_name="test-project",
        directory="/test/dir",
    )

    # Both backends should receive notification
    assert len(test_backend.notifications) == 1
    assert len(backend2.notifications) == 1


@pytest.mark.asyncio
async def test_add_backend(manager, test_backend):
    """Test adding backend dynamically."""
    backend2 = TestNotificationBackend()
    manager.add_backend(backend2)

    await manager.notify_started(
        job_id="job123",
        project_name="test-project",
        directory="/test/dir",
    )

    # Both backends should receive notification
    assert len(test_backend.notifications) == 1
    assert len(backend2.notifications) == 1


@pytest.mark.asyncio
async def test_remove_backend(manager, test_backend):
    """Test removing backend dynamically."""
    manager.remove_backend(test_backend)

    await manager.notify_started(
        job_id="job123",
        project_name="test-project",
        directory="/test/dir",
    )

    # Removed backend should not receive notification
    assert len(test_backend.notifications) == 0


@pytest.mark.asyncio
async def test_callback_backend():
    """Test callback notification backend."""
    notifications = []

    def callback(title: str, message: str, level: str):
        notifications.append((title, message, level))

    backend = CallbackNotificationBackend(callback)
    await backend.notify("Test Title", "Test Message", "info")

    assert len(notifications) == 1
    assert notifications[0] == ("Test Title", "Test Message", "info")


@pytest.mark.asyncio
async def test_callback_backend_async():
    """Test callback backend with async function."""
    notifications = []

    async def async_callback(title: str, message: str, level: str):
        await asyncio.sleep(0.001)  # Simulate async work
        notifications.append((title, message, level))

    backend = CallbackNotificationBackend(async_callback)
    await backend.notify("Test Title", "Test Message", "info")

    assert len(notifications) == 1
    assert notifications[0] == ("Test Title", "Test Message", "info")


@pytest.mark.asyncio
async def test_console_backend():
    """Test console backend doesn't crash."""
    backend = ConsoleNotificationBackend()
    # Should not raise exception
    await backend.notify("Test Title", "Test Message", "info")


@pytest.mark.asyncio
async def test_log_backend():
    """Test log backend doesn't crash."""
    backend = LogNotificationBackend()
    # Should not raise exception
    await backend.notify("Test Title", "Test Message", "info")
    await backend.notify("Error Title", "Error Message", "error")
    await backend.notify("Warning Title", "Warning Message", "warning")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
