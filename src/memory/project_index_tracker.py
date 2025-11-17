"""Project index metadata tracking for auto-indexing decisions."""

import logging
import sqlite3
from typing import Optional, Dict, Any
from datetime import datetime, UTC
from pathlib import Path

from src.config import ServerConfig, get_config
from src.core.exceptions import StorageError

logger = logging.getLogger(__name__)


class ProjectIndexMetadata:
    """Metadata about a project's indexing state."""

    def __init__(
        self,
        project_name: str,
        first_indexed_at: datetime,
        last_indexed_at: datetime,
        total_files: int,
        total_units: int,
        is_watching: bool = False,
        index_version: str = "1.0",
    ):
        """
        Initialize project metadata.

        Args:
            project_name: Name of the project
            first_indexed_at: When project was first indexed
            last_indexed_at: When project was last fully indexed
            total_files: Number of files indexed
            total_units: Number of semantic units indexed
            is_watching: Whether file watcher is active
            index_version: Schema version for future migrations
        """
        self.project_name = project_name
        self.first_indexed_at = first_indexed_at
        self.last_indexed_at = last_indexed_at
        self.total_files = total_files
        self.total_units = total_units
        self.is_watching = is_watching
        self.index_version = index_version

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "project_name": self.project_name,
            "first_indexed_at": self.first_indexed_at.isoformat(),
            "last_indexed_at": self.last_indexed_at.isoformat(),
            "total_files": self.total_files,
            "total_units": self.total_units,
            "is_watching": self.is_watching,
            "index_version": self.index_version,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProjectIndexMetadata":
        """Create from dictionary representation."""
        return cls(
            project_name=data["project_name"],
            first_indexed_at=datetime.fromisoformat(data["first_indexed_at"]),
            last_indexed_at=datetime.fromisoformat(data["last_indexed_at"]),
            total_files=data["total_files"],
            total_units=data["total_units"],
            is_watching=data.get("is_watching", False),
            index_version=data.get("index_version", "1.0"),
        )


class ProjectIndexTracker:
    """
    Tracks indexing metadata for projects to enable auto-indexing decisions.

    Stores information about when projects were indexed, file counts, and
    watching status to determine if auto-indexing should trigger.
    """

    def __init__(self, config: Optional[ServerConfig] = None):
        """
        Initialize project index tracker.

        Args:
            config: Server configuration. If None, uses global config.
        """
        if config is None:
            config = get_config()

        self.config = config
        self.db_path = config.sqlite_path_expanded
        self.conn: Optional[sqlite3.Connection] = None

        logger.info("ProjectIndexTracker initialized")

    async def initialize(self) -> None:
        """Initialize the tracker and create tables if needed."""
        try:
            self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
            self.conn.row_factory = sqlite3.Row

            # Create project index metadata table
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS project_index_metadata (
                    project_name TEXT PRIMARY KEY,
                    first_indexed_at TEXT NOT NULL,
                    last_indexed_at TEXT NOT NULL,
                    total_files INTEGER NOT NULL DEFAULT 0,
                    total_units INTEGER NOT NULL DEFAULT 0,
                    is_watching INTEGER NOT NULL DEFAULT 0,
                    index_version TEXT NOT NULL DEFAULT '1.0'
                )
            """)

            # Create index for efficient queries
            self.conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_last_indexed ON project_index_metadata(last_indexed_at)"
            )

            self.conn.commit()
            logger.info("ProjectIndexTracker tables created")

        except Exception as e:
            raise StorageError(
                f"Failed to initialize project index tracker: {e}",
                solution="Check database permissions and disk space. "
                        "Ensure SQLite database is not corrupted.",
                docs_url="https://docs.claude-memory.com/troubleshooting#storage-errors"
            ) from e

    async def is_indexed(self, project_name: str) -> bool:
        """
        Check if a project has been indexed before.

        Args:
            project_name: Name of the project

        Returns:
            True if project has been indexed, False otherwise
        """
        if not self.conn:
            raise StorageError("Tracker not initialized. Call initialize() first.")

        try:
            cursor = self.conn.execute(
                "SELECT 1 FROM project_index_metadata WHERE project_name = ? LIMIT 1",
                (project_name,)
            )
            return cursor.fetchone() is not None

        except Exception as e:
            raise StorageError(
                f"Failed to check if project is indexed: {e}",
                solution="Check database connection and query syntax.",
                docs_url="https://docs.claude-memory.com/troubleshooting#storage-errors"
            ) from e

    async def get_metadata(self, project_name: str) -> Optional[ProjectIndexMetadata]:
        """
        Get metadata for a project.

        Args:
            project_name: Name of the project

        Returns:
            ProjectIndexMetadata if project exists, None otherwise
        """
        if not self.conn:
            raise StorageError("Tracker not initialized. Call initialize() first.")

        try:
            cursor = self.conn.execute(
                """
                SELECT project_name, first_indexed_at, last_indexed_at,
                       total_files, total_units, is_watching, index_version
                FROM project_index_metadata
                WHERE project_name = ?
                """,
                (project_name,)
            )

            row = cursor.fetchone()
            if not row:
                return None

            return ProjectIndexMetadata(
                project_name=row["project_name"],
                first_indexed_at=datetime.fromisoformat(row["first_indexed_at"]),
                last_indexed_at=datetime.fromisoformat(row["last_indexed_at"]),
                total_files=row["total_files"],
                total_units=row["total_units"],
                is_watching=bool(row["is_watching"]),
                index_version=row["index_version"],
            )

        except Exception as e:
            raise StorageError(
                f"Failed to get project metadata: {e}",
                solution="Check database connection and data integrity.",
                docs_url="https://docs.claude-memory.com/troubleshooting#storage-errors"
            ) from e

    async def update_metadata(
        self,
        project_name: str,
        total_files: int,
        total_units: int,
        is_watching: Optional[bool] = None,
    ) -> None:
        """
        Update or create project metadata.

        Args:
            project_name: Name of the project
            total_files: Total number of files indexed
            total_units: Total number of semantic units indexed
            is_watching: Whether file watcher is active (None = no change)
        """
        if not self.conn:
            raise StorageError("Tracker not initialized. Call initialize() first.")

        try:
            now = datetime.now(UTC).isoformat()

            # Check if project exists
            exists = await self.is_indexed(project_name)

            if exists:
                # Update existing record
                if is_watching is not None:
                    self.conn.execute(
                        """
                        UPDATE project_index_metadata
                        SET last_indexed_at = ?,
                            total_files = ?,
                            total_units = ?,
                            is_watching = ?
                        WHERE project_name = ?
                        """,
                        (now, total_files, total_units, int(is_watching), project_name)
                    )
                else:
                    self.conn.execute(
                        """
                        UPDATE project_index_metadata
                        SET last_indexed_at = ?,
                            total_files = ?,
                            total_units = ?
                        WHERE project_name = ?
                        """,
                        (now, total_files, total_units, project_name)
                    )
            else:
                # Insert new record
                watching = int(is_watching) if is_watching is not None else 0
                self.conn.execute(
                    """
                    INSERT INTO project_index_metadata
                        (project_name, first_indexed_at, last_indexed_at,
                         total_files, total_units, is_watching, index_version)
                    VALUES (?, ?, ?, ?, ?, ?, '1.0')
                    """,
                    (project_name, now, now, total_files, total_units, watching)
                )

            self.conn.commit()
            logger.debug(f"Updated metadata for project: {project_name}")

        except Exception as e:
            self.conn.rollback()
            raise StorageError(
                f"Failed to update project metadata: {e}",
                solution="Check database connection and permissions.",
                docs_url="https://docs.claude-memory.com/troubleshooting#storage-errors"
            ) from e

    async def set_watching(self, project_name: str, is_watching: bool) -> None:
        """
        Update the watching status for a project.

        Args:
            project_name: Name of the project
            is_watching: Whether file watcher is active
        """
        if not self.conn:
            raise StorageError("Tracker not initialized. Call initialize() first.")

        try:
            self.conn.execute(
                "UPDATE project_index_metadata SET is_watching = ? WHERE project_name = ?",
                (int(is_watching), project_name)
            )
            self.conn.commit()
            logger.debug(f"Set watching={is_watching} for project: {project_name}")

        except Exception as e:
            self.conn.rollback()
            raise StorageError(
                f"Failed to update watching status: {e}",
                solution="Check database connection.",
                docs_url="https://docs.claude-memory.com/troubleshooting#storage-errors"
            ) from e

    async def is_stale(self, project_name: str, project_path: Path) -> bool:
        """
        Check if a project index is stale (files changed since last index).

        Compares the last indexed timestamp with the most recently modified
        file in the project directory.

        Args:
            project_name: Name of the project
            project_path: Path to the project directory

        Returns:
            True if index is stale, False if up-to-date or not indexed
        """
        if not self.conn:
            raise StorageError("Tracker not initialized. Call initialize() first.")

        metadata = await self.get_metadata(project_name)
        if not metadata:
            # Not indexed yet, so not stale (should trigger initial index)
            return False

        try:
            # Find most recently modified file in project
            latest_mtime = 0.0
            for file_path in project_path.rglob('*'):
                if file_path.is_file():
                    try:
                        mtime = file_path.stat().st_mtime
                        if mtime > latest_mtime:
                            latest_mtime = mtime
                    except (OSError, PermissionError):
                        # Skip files we can't access
                        continue

            if latest_mtime == 0.0:
                # No files found, not stale
                return False

            # Compare with last indexed time
            latest_file_time = datetime.fromtimestamp(latest_mtime, tz=UTC)
            return latest_file_time > metadata.last_indexed_at

        except Exception as e:
            logger.warning(f"Error checking staleness for {project_name}: {e}")
            # On error, assume not stale (safer for auto-indexing)
            return False

    async def delete_metadata(self, project_name: str) -> None:
        """
        Delete metadata for a project.

        Args:
            project_name: Name of the project
        """
        if not self.conn:
            raise StorageError("Tracker not initialized. Call initialize() first.")

        try:
            self.conn.execute(
                "DELETE FROM project_index_metadata WHERE project_name = ?",
                (project_name,)
            )
            self.conn.commit()
            logger.info(f"Deleted metadata for project: {project_name}")

        except Exception as e:
            self.conn.rollback()
            raise StorageError(
                f"Failed to delete project metadata: {e}",
                solution="Check database connection.",
                docs_url="https://docs.claude-memory.com/troubleshooting#storage-errors"
            ) from e

    async def close(self) -> None:
        """Close the database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None
            logger.debug("ProjectIndexTracker connection closed")
