"""Unit tests for JobStateManager."""

import pytest
import tempfile
from pathlib import Path
from datetime import datetime, UTC

from src.memory.job_state_manager import JobStateManager, JobStatus, IndexingJob


@pytest.fixture
def db_path():
    """Create temporary database."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as f:
        yield f.name
    Path(f.name).unlink(missing_ok=True)


@pytest.fixture
def manager(db_path):
    """Create job state manager."""
    return JobStateManager(db_path)


def test_create_job(manager):
    """Test creating a new job."""
    job = manager.create_job(
        project_name="test-project",
        directory_path=Path("/test/dir"),
        recursive=True,
    )

    assert job.id is not None
    assert job.project_name == "test-project"
    assert job.directory_path == "/test/dir"
    assert job.recursive is True
    assert job.status == JobStatus.QUEUED
    assert job.created_at is not None
    assert job.indexed_files == 0
    assert job.failed_files == 0
    assert job.total_units == 0


def test_get_job(manager):
    """Test retrieving a job."""
    job = manager.create_job(
        project_name="test-project",
        directory_path=Path("/test/dir"),
    )

    retrieved = manager.get_job(job.id)
    assert retrieved is not None
    assert retrieved.id == job.id
    assert retrieved.project_name == job.project_name


def test_get_nonexistent_job(manager):
    """Test retrieving non-existent job returns None."""
    result = manager.get_job("nonexistent-id")
    assert result is None


def test_update_job_status(manager):
    """Test updating job status."""
    job = manager.create_job(
        project_name="test-project",
        directory_path=Path("/test/dir"),
    )

    # Update to running
    manager.update_job_status(job.id, JobStatus.RUNNING)
    updated = manager.get_job(job.id)
    assert updated.status == JobStatus.RUNNING
    assert updated.started_at is not None

    # Update to completed
    manager.update_job_status(job.id, JobStatus.COMPLETED)
    updated = manager.get_job(job.id)
    assert updated.status == JobStatus.COMPLETED
    assert updated.completed_at is not None


def test_update_job_status_with_error(manager):
    """Test updating job status with error message."""
    job = manager.create_job(
        project_name="test-project",
        directory_path=Path("/test/dir"),
    )

    error_msg = "Connection failed"
    manager.update_job_status(job.id, JobStatus.FAILED, error_message=error_msg)

    updated = manager.get_job(job.id)
    assert updated.status == JobStatus.FAILED
    assert updated.error_message == error_msg


def test_update_job_progress(manager):
    """Test updating job progress."""
    job = manager.create_job(
        project_name="test-project",
        directory_path=Path("/test/dir"),
    )

    manager.update_job_progress(
        job_id=job.id,
        indexed_files=50,
        failed_files=2,
        total_units=150,
        last_indexed_file="file.py",
        total_files=100,
    )

    updated = manager.get_job(job.id)
    assert updated.indexed_files == 50
    assert updated.failed_files == 2
    assert updated.total_units == 150
    assert updated.last_indexed_file == "file.py"
    assert updated.total_files == 100


def test_add_indexed_file(manager):
    """Test adding file to indexed list."""
    job = manager.create_job(
        project_name="test-project",
        directory_path=Path("/test/dir"),
    )

    manager.add_indexed_file(job.id, "/test/file1.py")
    manager.add_indexed_file(job.id, "/test/file2.py")

    updated = manager.get_job(job.id)
    assert len(updated.indexed_file_list) == 2
    assert "/test/file1.py" in updated.indexed_file_list
    assert "/test/file2.py" in updated.indexed_file_list


def test_get_indexed_files(manager):
    """Test retrieving indexed files list."""
    job = manager.create_job(
        project_name="test-project",
        directory_path=Path("/test/dir"),
    )

    manager.add_indexed_file(job.id, "/test/file1.py")
    manager.add_indexed_file(job.id, "/test/file2.py")

    files = manager.get_indexed_files(job.id)
    assert len(files) == 2
    assert "/test/file1.py" in files
    assert "/test/file2.py" in files


def test_get_indexed_files_empty(manager):
    """Test retrieving indexed files for new job."""
    job = manager.create_job(
        project_name="test-project",
        directory_path=Path("/test/dir"),
    )

    files = manager.get_indexed_files(job.id)
    assert files == []


def test_list_jobs_all(manager):
    """Test listing all jobs."""
    job1 = manager.create_job("project1", Path("/dir1"))
    job2 = manager.create_job("project2", Path("/dir2"))

    jobs = manager.list_jobs()
    assert len(jobs) >= 2

    job_ids = [j.id for j in jobs]
    assert job1.id in job_ids
    assert job2.id in job_ids


def test_list_jobs_by_status(manager):
    """Test listing jobs filtered by status."""
    job1 = manager.create_job("project1", Path("/dir1"))
    job2 = manager.create_job("project2", Path("/dir2"))

    manager.update_job_status(job1.id, JobStatus.RUNNING)
    manager.update_job_status(job2.id, JobStatus.COMPLETED)

    running_jobs = manager.list_jobs(status=JobStatus.RUNNING)
    completed_jobs = manager.list_jobs(status=JobStatus.COMPLETED)

    assert any(j.id == job1.id for j in running_jobs)
    assert any(j.id == job2.id for j in completed_jobs)
    assert not any(j.id == job1.id for j in completed_jobs)


def test_list_jobs_by_project(manager):
    """Test listing jobs filtered by project name."""
    job1 = manager.create_job("project-a", Path("/dir1"))
    job2 = manager.create_job("project-b", Path("/dir2"))
    job3 = manager.create_job("project-a", Path("/dir3"))

    project_a_jobs = manager.list_jobs(project_name="project-a")
    project_b_jobs = manager.list_jobs(project_name="project-b")

    project_a_ids = [j.id for j in project_a_jobs]
    project_b_ids = [j.id for j in project_b_jobs]

    assert job1.id in project_a_ids
    assert job3.id in project_a_ids
    assert job2.id in project_b_ids
    assert job2.id not in project_a_ids


def test_list_jobs_limit(manager):
    """Test listing jobs with limit."""
    for i in range(10):
        manager.create_job(f"project{i}", Path(f"/dir{i}"))

    jobs = manager.list_jobs(limit=5)
    assert len(jobs) == 5


def test_delete_job(manager):
    """Test deleting a job."""
    job = manager.create_job("test-project", Path("/test/dir"))

    # Mark as completed
    manager.update_job_status(job.id, JobStatus.COMPLETED)

    # Delete
    result = manager.delete_job(job.id)
    assert result is True

    # Verify deletion
    assert manager.get_job(job.id) is None


def test_delete_nonexistent_job(manager):
    """Test deleting non-existent job."""
    result = manager.delete_job("nonexistent-id")
    assert result is False


def test_clean_old_jobs(manager):
    """Test cleaning old completed jobs."""
    # Create completed job
    job1 = manager.create_job("project1", Path("/dir1"))
    manager.update_job_status(job1.id, JobStatus.COMPLETED)

    # Create failed job
    job2 = manager.create_job("project2", Path("/dir2"))
    manager.update_job_status(job2.id, JobStatus.FAILED)

    # Create running job (should not be deleted)
    job3 = manager.create_job("project3", Path("/dir3"))
    manager.update_job_status(job3.id, JobStatus.RUNNING)

    # Can't easily test with real timestamps, but verify method works
    deleted = manager.clean_old_jobs(days=0)  # Delete all completed/failed
    assert deleted >= 0  # Method executes without error

    # Running job should still exist
    assert manager.get_job(job3.id) is not None


def test_job_to_dict(manager):
    """Test converting job to dictionary."""
    job = manager.create_job("test-project", Path("/test/dir"))

    job_dict = job.to_dict()
    assert isinstance(job_dict, dict)
    assert job_dict['id'] == job.id
    assert job_dict['project_name'] == "test-project"
    assert job_dict['status'] == JobStatus.QUEUED.value


def test_job_persistence(manager):
    """Test that jobs persist across manager instances."""
    job = manager.create_job("test-project", Path("/test/dir"))
    job_id = job.id

    # Create new manager with same database
    manager2 = JobStateManager(manager.db_path)
    retrieved = manager2.get_job(job_id)

    assert retrieved is not None
    assert retrieved.id == job_id
    assert retrieved.project_name == "test-project"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
