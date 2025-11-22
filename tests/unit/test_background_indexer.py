"""Unit tests for BackgroundIndexer."""

import pytest
import asyncio
import tempfile
import uuid
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch, MagicMock

from src.memory.background_indexer import BackgroundIndexer
from src.memory.job_state_manager import JobStatus
from src.memory.notification_manager import NotificationManager, NotificationBackend
from src.config import ServerConfig


class MockNotificationBackend(NotificationBackend):
    """Mock backend for capturing notifications."""

    def __init__(self):
        """Initialize mock backend."""
        self.notifications = []

    async def notify(self, title: str, message: str, level: str = "info") -> None:
        """Record notification."""
        self.notifications.append((title, message, level))


@pytest.fixture
def temp_dir():
    """Create temporary directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def test_files(temp_dir):
    """Create test files."""
    # Create some Python files
    (temp_dir / "file1.py").write_text("def func1(): pass")
    (temp_dir / "file2.py").write_text("def func2(): pass")
    (temp_dir / "file3.py").write_text("def func3(): pass")

    return temp_dir


@pytest.fixture
def job_db():
    """Create temporary job database."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as f:
        yield f.name
    Path(f.name).unlink(missing_ok=True)


@pytest.fixture
def notification_backend():
    """Create test notification backend."""
    return MockNotificationBackend()


@pytest.fixture
def notification_manager(notification_backend):
    """Create notification manager with test backend."""
    return NotificationManager(backends=[notification_backend])


@pytest.fixture
def config():
    """Create test configuration with unique collection name."""
    return ServerConfig(
        storage_backend="qdrant",
        qdrant_url="http://localhost:6333",
        qdrant_collection_name=f"test_bg_{uuid.uuid4().hex[:8]}",
        enable_parallel_embeddings=False,  # Disable for faster tests
    )


@pytest.fixture
def indexer(job_db, notification_manager, config):
    """Create background indexer."""
    return BackgroundIndexer(
        config=config,
        job_db_path=job_db,
        notification_manager=notification_manager,
    )


@pytest.mark.asyncio
@patch('src.memory.background_indexer.IncrementalIndexer')
async def test_start_indexing_job(mock_indexer_class, indexer, test_files):
    """Test starting indexing job."""
    # Mock IncrementalIndexer
    mock_indexer = AsyncMock()
    mock_indexer.initialize = AsyncMock()
    mock_indexer.index_file = AsyncMock(return_value={
        "units_indexed": 1,
        "skipped": False,
    })
    mock_indexer.close = AsyncMock()
    mock_indexer.SUPPORTED_EXTENSIONS = {".py"}
    mock_indexer_class.return_value = mock_indexer

    # Start job
    job_id = await indexer.start_indexing_job(
        directory=test_files,
        project_name="test-project",
        recursive=True,
        background=False,  # Run synchronously for testing
    )

    assert job_id is not None

    # Verify job was created
    job = await indexer.get_job_status(job_id)
    assert job is not None
    assert job.project_name == "test-project"
    assert job.status == JobStatus.COMPLETED


@pytest.mark.asyncio
@patch('src.memory.background_indexer.IncrementalIndexer')
async def test_start_background_job(mock_indexer_class, indexer, test_files):
    """Test starting job in background."""
    # Mock IncrementalIndexer
    mock_indexer = AsyncMock()
    mock_indexer.initialize = AsyncMock()
    mock_indexer.index_file = AsyncMock(return_value={
        "units_indexed": 1,
        "skipped": False,
    })
    mock_indexer.close = AsyncMock()
    mock_indexer.SUPPORTED_EXTENSIONS = {".py"}
    mock_indexer_class.return_value = mock_indexer

    # Start job in background
    job_id = await indexer.start_indexing_job(
        directory=test_files,
        project_name="test-project",
        recursive=True,
        background=True,
    )

    assert job_id is not None

    # Give the background task a moment to start
    await asyncio.sleep(0.1)

    # Job should be queued, running, or completed
    job = await indexer.get_job_status(job_id)
    assert job.status in (JobStatus.QUEUED, JobStatus.RUNNING, JobStatus.COMPLETED)

    # Wait for job to complete
    await asyncio.sleep(0.5)

    job = await indexer.get_job_status(job_id)
    assert job.status == JobStatus.COMPLETED


@pytest.mark.asyncio
async def test_start_job_nonexistent_directory(indexer):
    """Test starting job with non-existent directory."""
    with pytest.raises(ValueError, match="does not exist"):
        await indexer.start_indexing_job(
            directory=Path("/nonexistent/dir"),
            project_name="test-project",
        )


@pytest.mark.asyncio
async def test_start_job_not_directory(indexer, temp_dir):
    """Test starting job with file instead of directory."""
    file_path = temp_dir / "file.txt"
    file_path.write_text("content")

    with pytest.raises(ValueError, match="Not a directory"):
        await indexer.start_indexing_job(
            directory=file_path,
            project_name="test-project",
        )


@pytest.mark.asyncio
@patch('src.memory.background_indexer.IncrementalIndexer')
async def test_pause_job(mock_indexer_class, indexer, test_files):
    """Test pausing a running job."""
    # Mock IncrementalIndexer with slow indexing
    mock_indexer = AsyncMock()
    mock_indexer.initialize = AsyncMock()

    async def slow_index_file(path):
        await asyncio.sleep(0.5)
        return {"units_indexed": 1, "skipped": False}

    mock_indexer.index_file = slow_index_file
    mock_indexer.close = AsyncMock()
    mock_indexer.SUPPORTED_EXTENSIONS = {".py"}
    mock_indexer_class.return_value = mock_indexer

    # Start job in background
    job_id = await indexer.start_indexing_job(
        directory=test_files,
        project_name="test-project",
        recursive=True,
        background=True,
    )

    # Wait for job to start
    await asyncio.sleep(0.1)

    # Pause job
    result = await indexer.pause_job(job_id)
    assert result is True

    # Check job status
    job = await indexer.get_job_status(job_id)
    assert job.status == JobStatus.PAUSED


@pytest.mark.asyncio
async def test_pause_nonexistent_job(indexer):
    """Test pausing non-existent job."""
    result = await indexer.pause_job("nonexistent-id")
    assert result is False


@pytest.mark.asyncio
@patch('src.memory.background_indexer.IncrementalIndexer')
async def test_pause_completed_job(mock_indexer_class, indexer, test_files):
    """Test pausing already completed job."""
    # Mock IncrementalIndexer
    mock_indexer = AsyncMock()
    mock_indexer.initialize = AsyncMock()
    mock_indexer.index_file = AsyncMock(return_value={
        "units_indexed": 1,
        "skipped": False,
    })
    mock_indexer.close = AsyncMock()
    mock_indexer.SUPPORTED_EXTENSIONS = {".py"}
    mock_indexer_class.return_value = mock_indexer

    # Start and complete job
    job_id = await indexer.start_indexing_job(
        directory=test_files,
        project_name="test-project",
        recursive=True,
        background=False,
    )

    # Try to pause completed job
    result = await indexer.pause_job(job_id)
    assert result is False


@pytest.mark.asyncio
@patch('src.memory.background_indexer.IncrementalIndexer')
async def test_resume_job(mock_indexer_class, indexer, test_files):
    """Test resuming a paused job."""
    # Mock IncrementalIndexer
    mock_indexer = AsyncMock()
    mock_indexer.initialize = AsyncMock()

    call_count = 0

    async def counting_index_file(path):
        nonlocal call_count
        call_count += 1
        if call_count <= 1:
            await asyncio.sleep(0.5)  # First file is slow
        return {"units_indexed": 1, "skipped": False}

    mock_indexer.index_file = counting_index_file
    mock_indexer.close = AsyncMock()
    mock_indexer.SUPPORTED_EXTENSIONS = {".py"}
    mock_indexer_class.return_value = mock_indexer

    # Start job
    job_id = await indexer.start_indexing_job(
        directory=test_files,
        project_name="test-project",
        recursive=True,
        background=True,
    )

    await asyncio.sleep(0.1)

    # Pause job
    await indexer.pause_job(job_id)

    # Resume job
    result = await indexer.resume_job(job_id, background=False)
    assert result is True

    # Check job status
    job = await indexer.get_job_status(job_id)
    assert job.status == JobStatus.COMPLETED


@pytest.mark.asyncio
async def test_resume_nonexistent_job(indexer):
    """Test resuming non-existent job."""
    result = await indexer.resume_job("nonexistent-id")
    assert result is False


@pytest.mark.asyncio
@patch('src.memory.background_indexer.IncrementalIndexer')
async def test_resume_running_job(mock_indexer_class, indexer, test_files):
    """Test resuming already running job."""
    # Mock IncrementalIndexer
    mock_indexer = AsyncMock()
    mock_indexer.initialize = AsyncMock()
    mock_indexer.index_file = AsyncMock(return_value={
        "units_indexed": 1,
        "skipped": False,
    })
    mock_indexer.close = AsyncMock()
    mock_indexer.SUPPORTED_EXTENSIONS = {".py"}
    mock_indexer_class.return_value = mock_indexer

    # Start job
    job_id = await indexer.start_indexing_job(
        directory=test_files,
        project_name="test-project",
        recursive=True,
        background=True,
    )

    await asyncio.sleep(0.1)

    # Try to resume running job
    result = await indexer.resume_job(job_id)
    assert result is False


@pytest.mark.asyncio
@patch('src.memory.background_indexer.IncrementalIndexer')
async def test_cancel_job(mock_indexer_class, indexer, test_files):
    """Test cancelling a running job."""
    # Mock IncrementalIndexer with slow indexing
    mock_indexer = AsyncMock()
    mock_indexer.initialize = AsyncMock()

    async def slow_index_file(path):
        await asyncio.sleep(0.5)
        return {"units_indexed": 1, "skipped": False}

    mock_indexer.index_file = slow_index_file
    mock_indexer.close = AsyncMock()
    mock_indexer.SUPPORTED_EXTENSIONS = {".py"}
    mock_indexer_class.return_value = mock_indexer

    # Start job
    job_id = await indexer.start_indexing_job(
        directory=test_files,
        project_name="test-project",
        recursive=True,
        background=True,
    )

    await asyncio.sleep(0.1)

    # Cancel job
    result = await indexer.cancel_job(job_id)
    assert result is True

    # Check job status
    job = await indexer.get_job_status(job_id)
    assert job.status == JobStatus.CANCELLED


@pytest.mark.asyncio
async def test_cancel_nonexistent_job(indexer):
    """Test cancelling non-existent job."""
    result = await indexer.cancel_job("nonexistent-id")
    assert result is False


@pytest.mark.asyncio
@patch('src.memory.background_indexer.IncrementalIndexer')
async def test_list_jobs(mock_indexer_class, indexer, test_files):
    """Test listing jobs."""
    # Mock IncrementalIndexer
    mock_indexer = AsyncMock()
    mock_indexer.initialize = AsyncMock()
    mock_indexer.index_file = AsyncMock(return_value={
        "units_indexed": 1,
        "skipped": False,
    })
    mock_indexer.close = AsyncMock()
    mock_indexer.SUPPORTED_EXTENSIONS = {".py"}
    mock_indexer_class.return_value = mock_indexer

    # Create multiple jobs
    job1_id = await indexer.start_indexing_job(
        directory=test_files,
        project_name="project1",
        recursive=True,
        background=False,
    )

    job2_id = await indexer.start_indexing_job(
        directory=test_files,
        project_name="project2",
        recursive=True,
        background=False,
    )

    # List all jobs
    jobs = await indexer.list_jobs()
    assert len(jobs) >= 2

    job_ids = [j.id for j in jobs]
    assert job1_id in job_ids
    assert job2_id in job_ids


@pytest.mark.asyncio
@patch('src.memory.background_indexer.IncrementalIndexer')
async def test_list_jobs_by_status(mock_indexer_class, indexer, test_files):
    """Test listing jobs filtered by status."""
    # Mock IncrementalIndexer
    mock_indexer = AsyncMock()
    mock_indexer.initialize = AsyncMock()
    mock_indexer.index_file = AsyncMock(return_value={
        "units_indexed": 1,
        "skipped": False,
    })
    mock_indexer.close = AsyncMock()
    mock_indexer.SUPPORTED_EXTENSIONS = {".py"}
    mock_indexer_class.return_value = mock_indexer

    # Create completed job
    job_id = await indexer.start_indexing_job(
        directory=test_files,
        project_name="test-project",
        recursive=True,
        background=False,
    )

    # List completed jobs
    completed_jobs = await indexer.list_jobs(status=JobStatus.COMPLETED)
    assert any(j.id == job_id for j in completed_jobs)


@pytest.mark.asyncio
@patch('src.memory.background_indexer.IncrementalIndexer')
async def test_delete_completed_job(mock_indexer_class, indexer, test_files):
    """Test deleting a completed job."""
    # Mock IncrementalIndexer
    mock_indexer = AsyncMock()
    mock_indexer.initialize = AsyncMock()
    mock_indexer.index_file = AsyncMock(return_value={
        "units_indexed": 1,
        "skipped": False,
    })
    mock_indexer.close = AsyncMock()
    mock_indexer.SUPPORTED_EXTENSIONS = {".py"}
    mock_indexer_class.return_value = mock_indexer

    # Create completed job
    job_id = await indexer.start_indexing_job(
        directory=test_files,
        project_name="test-project",
        recursive=True,
        background=False,
    )

    # Delete job
    result = await indexer.delete_job(job_id)
    assert result is True

    # Verify deletion
    job = await indexer.get_job_status(job_id)
    assert job is None


@pytest.mark.asyncio
@patch('src.memory.background_indexer.IncrementalIndexer')
async def test_cannot_delete_running_job(mock_indexer_class, indexer, test_files):
    """Test that running jobs cannot be deleted."""
    # Mock IncrementalIndexer with slow indexing
    mock_indexer = AsyncMock()
    mock_indexer.initialize = AsyncMock()

    async def slow_index_file(path):
        await asyncio.sleep(0.5)
        return {"units_indexed": 1, "skipped": False}

    mock_indexer.index_file = slow_index_file
    mock_indexer.close = AsyncMock()
    mock_indexer.SUPPORTED_EXTENSIONS = {".py"}
    mock_indexer_class.return_value = mock_indexer

    # Start job
    job_id = await indexer.start_indexing_job(
        directory=test_files,
        project_name="test-project",
        recursive=True,
        background=True,
    )

    await asyncio.sleep(0.1)

    # Try to delete running job
    result = await indexer.delete_job(job_id)
    assert result is False

    # Cancel and cleanup
    await indexer.cancel_job(job_id)


@pytest.mark.asyncio
@patch('src.memory.background_indexer.IncrementalIndexer')
async def test_notifications_sent(mock_indexer_class, indexer, test_files, notification_backend):
    """Test that notifications are sent during indexing."""
    # Mock IncrementalIndexer
    mock_indexer = AsyncMock()
    mock_indexer.initialize = AsyncMock()
    mock_indexer.index_file = AsyncMock(return_value={
        "units_indexed": 1,
        "skipped": False,
    })
    mock_indexer.close = AsyncMock()
    mock_indexer.SUPPORTED_EXTENSIONS = {".py"}
    mock_indexer_class.return_value = mock_indexer

    # Start job
    await indexer.start_indexing_job(
        directory=test_files,
        project_name="test-project",
        recursive=True,
        background=False,
    )

    # Check notifications
    notifications = notification_backend.notifications
    assert len(notifications) >= 2  # At least started and completed

    # Check for started notification
    assert any("Started" in title or "🚀" in title for title, _, _ in notifications)

    # Check for completed notification
    assert any("Complete" in title or "✅" in title for title, _, _ in notifications)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
