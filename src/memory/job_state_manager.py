"""Job state management for background indexing operations."""

import json
import sqlite3
from dataclasses import dataclass, asdict
from datetime import datetime, UTC
from enum import Enum
from pathlib import Path
from typing import Optional, List, Dict, Any
from uuid import uuid4


class JobStatus(str, Enum):
    """Job status enumeration."""
    QUEUED = "queued"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class IndexingJob:
    """Indexing job state."""
    id: str
    project_name: str
    directory_path: str
    recursive: bool
    status: JobStatus
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    total_files: Optional[int] = None
    indexed_files: int = 0
    failed_files: int = 0
    total_units: int = 0
    error_message: Optional[str] = None
    last_indexed_file: Optional[str] = None
    indexed_file_list: Optional[List[str]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        data = asdict(self)
        data['status'] = self.status.value
        return data


class JobStateManager:
    """Manages indexing job state in SQLite."""

    def __init__(self, db_path: str):
        """
        Initialize job state manager.

        Args:
            db_path: Path to SQLite database
        """
        self.db_path = db_path
        self._ensure_table()

    def _ensure_table(self) -> None:
        """Create indexing_jobs table if not exists."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS indexing_jobs (
                    id TEXT PRIMARY KEY,
                    project_name TEXT NOT NULL,
                    directory_path TEXT NOT NULL,
                    recursive INTEGER NOT NULL DEFAULT 1,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    completed_at TEXT,
                    total_files INTEGER,
                    indexed_files INTEGER DEFAULT 0,
                    failed_files INTEGER DEFAULT 0,
                    total_units INTEGER DEFAULT 0,
                    error_message TEXT,
                    last_indexed_file TEXT,
                    indexed_file_list TEXT
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_jobs_status ON indexing_jobs(status)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_jobs_project ON indexing_jobs(project_name)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_jobs_created ON indexing_jobs(created_at DESC)"
            )
            conn.commit()

    def create_job(
        self,
        project_name: str,
        directory_path: Path,
        recursive: bool = True,
    ) -> IndexingJob:
        """
        Create new indexing job.

        Args:
            project_name: Project name
            directory_path: Directory to index
            recursive: Whether to index recursively

        Returns:
            Created job
        """
        job = IndexingJob(
            id=str(uuid4()),
            project_name=project_name,
            directory_path=str(directory_path),
            recursive=recursive,
            status=JobStatus.QUEUED,
            created_at=datetime.now(UTC).isoformat(),
            indexed_file_list=[],
        )

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO indexing_jobs
                (id, project_name, directory_path, recursive, status, created_at, indexed_file_list)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job.id,
                    job.project_name,
                    job.directory_path,
                    1 if job.recursive else 0,
                    job.status.value,
                    job.created_at,
                    json.dumps(job.indexed_file_list),
                ),
            )
            conn.commit()

        return job

    def get_job(self, job_id: str) -> Optional[IndexingJob]:
        """
        Get job by ID.

        Args:
            job_id: Job ID

        Returns:
            Job or None if not found
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM indexing_jobs WHERE id = ?",
                (job_id,),
            )
            row = cursor.fetchone()

        if not row:
            return None

        return self._row_to_job(row)

    def list_jobs(
        self,
        status: Optional[JobStatus] = None,
        project_name: Optional[str] = None,
        limit: int = 100,
    ) -> List[IndexingJob]:
        """
        List jobs, optionally filtered.

        Args:
            status: Filter by status
            project_name: Filter by project name
            limit: Maximum number of jobs to return

        Returns:
            List of jobs
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            query = "SELECT * FROM indexing_jobs WHERE 1=1"
            params = []

            if status:
                query += " AND status = ?"
                params.append(status.value)

            if project_name:
                query += " AND project_name = ?"
                params.append(project_name)

            query += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)

            cursor = conn.execute(query, params)
            rows = cursor.fetchall()

        return [self._row_to_job(row) for row in rows]

    def update_job_status(
        self,
        job_id: str,
        status: JobStatus,
        error_message: Optional[str] = None,
    ) -> None:
        """
        Update job status.

        Args:
            job_id: Job ID
            status: New status
            error_message: Optional error message for failed jobs
        """
        updates = ["status = ?"]
        params = [status.value]

        # Set timestamps based on status
        if status == JobStatus.RUNNING:
            updates.append("started_at = ?")
            params.append(datetime.now(UTC).isoformat())
        elif status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED):
            updates.append("completed_at = ?")
            params.append(datetime.now(UTC).isoformat())

        if error_message:
            updates.append("error_message = ?")
            params.append(error_message)

        params.append(job_id)

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                f"UPDATE indexing_jobs SET {', '.join(updates)} WHERE id = ?",
                params,
            )
            conn.commit()

    def update_job_progress(
        self,
        job_id: str,
        indexed_files: int,
        failed_files: int,
        total_units: int,
        last_indexed_file: Optional[str] = None,
        total_files: Optional[int] = None,
    ) -> None:
        """
        Update job progress.

        Args:
            job_id: Job ID
            indexed_files: Number of files indexed
            failed_files: Number of files failed
            total_units: Total semantic units indexed
            last_indexed_file: Last file indexed
            total_files: Total files to index (if known)
        """
        updates = [
            "indexed_files = ?",
            "failed_files = ?",
            "total_units = ?",
        ]
        params = [indexed_files, failed_files, total_units]

        if last_indexed_file:
            updates.append("last_indexed_file = ?")
            params.append(last_indexed_file)

        if total_files is not None:
            updates.append("total_files = ?")
            params.append(total_files)

        params.append(job_id)

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                f"UPDATE indexing_jobs SET {', '.join(updates)} WHERE id = ?",
                params,
            )
            conn.commit()

    def add_indexed_file(self, job_id: str, file_path: str) -> None:
        """
        Add file to indexed file list.

        Args:
            job_id: Job ID
            file_path: File path that was indexed
        """
        job = self.get_job(job_id)
        if not job:
            return

        if job.indexed_file_list is None:
            job.indexed_file_list = []

        job.indexed_file_list.append(file_path)

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE indexing_jobs SET indexed_file_list = ? WHERE id = ?",
                (json.dumps(job.indexed_file_list), job_id),
            )
            conn.commit()

    def get_indexed_files(self, job_id: str) -> List[str]:
        """
        Get list of indexed files for a job.

        Args:
            job_id: Job ID

        Returns:
            List of indexed file paths
        """
        job = self.get_job(job_id)
        if not job or not job.indexed_file_list:
            return []

        return job.indexed_file_list

    def delete_job(self, job_id: str) -> bool:
        """
        Delete job from database.

        Args:
            job_id: Job ID

        Returns:
            True if deleted, False if not found
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "DELETE FROM indexing_jobs WHERE id = ?",
                (job_id,),
            )
            conn.commit()
            return cursor.rowcount > 0

    def clean_old_jobs(self, days: int = 30) -> int:
        """
        Delete completed/failed jobs older than specified days.

        Args:
            days: Age threshold in days

        Returns:
            Number of jobs deleted
        """
        from datetime import timedelta

        cutoff = (datetime.now(UTC) - timedelta(days=days)).isoformat()

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                DELETE FROM indexing_jobs
                WHERE completed_at < ?
                AND status IN (?, ?, ?)
                """,
                (cutoff, JobStatus.COMPLETED.value, JobStatus.FAILED.value, JobStatus.CANCELLED.value),
            )
            conn.commit()
            return cursor.rowcount

    def _row_to_job(self, row: sqlite3.Row) -> IndexingJob:
        """Convert database row to IndexingJob."""
        indexed_file_list = None
        if row["indexed_file_list"]:
            try:
                indexed_file_list = json.loads(row["indexed_file_list"])
            except json.JSONDecodeError:
                indexed_file_list = []

        return IndexingJob(
            id=row["id"],
            project_name=row["project_name"],
            directory_path=row["directory_path"],
            recursive=bool(row["recursive"]),
            status=JobStatus(row["status"]),
            created_at=row["created_at"],
            started_at=row["started_at"],
            completed_at=row["completed_at"],
            total_files=row["total_files"],
            indexed_files=row["indexed_files"],
            failed_files=row["failed_files"],
            total_units=row["total_units"],
            error_message=row["error_message"],
            last_indexed_file=row["last_indexed_file"],
            indexed_file_list=indexed_file_list,
        )
