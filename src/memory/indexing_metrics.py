"""Storage and retrieval of indexing performance metrics."""

import sqlite3
from typing import Optional, List, Dict
from datetime import datetime, UTC


class IndexingMetricsStore:
    """Store and retrieve indexing performance metrics."""

    def __init__(self, db_path: str):
        """
        Initialize metrics store.

        Args:
            db_path: Path to SQLite database
        """
        self.db_path = db_path
        self._ensure_table()

    def _ensure_table(self) -> None:
        """Create metrics table if not exists."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS indexing_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_name TEXT,
                    files_indexed INTEGER NOT NULL,
                    total_time_seconds REAL NOT NULL,
                    avg_time_per_file_ms REAL NOT NULL,
                    total_size_bytes INTEGER,
                    timestamp TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_metrics_project ON indexing_metrics(project_name)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_metrics_timestamp ON indexing_metrics(timestamp)"
            )
            conn.commit()

    def store_metrics(
        self,
        files_indexed: int,
        total_time_seconds: float,
        project_name: Optional[str] = None,
        total_size_bytes: Optional[int] = None,
    ) -> None:
        """
        Store indexing metrics.

        Args:
            files_indexed: Number of files indexed
            total_time_seconds: Total indexing time in seconds
            project_name: Optional project name
            total_size_bytes: Optional total size of indexed files
        """
        avg_time_per_file_ms = (
            (total_time_seconds / files_indexed) * 1000 if files_indexed > 0 else 0
        )

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO indexing_metrics
                (project_name, files_indexed, total_time_seconds, avg_time_per_file_ms, total_size_bytes, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    project_name,
                    files_indexed,
                    total_time_seconds,
                    avg_time_per_file_ms,
                    total_size_bytes,
                    datetime.now(UTC).isoformat(),
                ),
            )
            conn.commit()

    def get_average_time_per_file(
        self, project_name: Optional[str] = None, limit: int = 10
    ) -> Optional[float]:
        """
        Get average time per file from recent indexing runs.

        Args:
            project_name: Filter by project name
            limit: Number of recent runs to average

        Returns:
            Average time per file in seconds, or None if no data
        """
        with sqlite3.connect(self.db_path) as conn:
            if project_name:
                cursor = conn.execute(
                    """
                    SELECT avg_time_per_file_ms
                    FROM indexing_metrics
                    WHERE project_name = ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                    """,
                    (project_name, limit),
                )
            else:
                cursor = conn.execute(
                    """
                    SELECT avg_time_per_file_ms
                    FROM indexing_metrics
                    ORDER BY timestamp DESC
                    LIMIT ?
                    """,
                    (limit,),
                )

            rows = cursor.fetchall()

        if not rows:
            return None

        # Average the recent runs (convert ms to seconds)
        avg_ms = sum(row[0] for row in rows) / len(rows)
        return avg_ms / 1000.0

    def get_recent_metrics(self, limit: int = 5) -> List[Dict]:
        """
        Get recent indexing metrics.

        Args:
            limit: Number of recent entries to retrieve

        Returns:
            List of metric dictionaries
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT *
                FROM indexing_metrics
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (limit,),
            )
            rows = cursor.fetchall()

        return [dict(row) for row in rows]

    def clear_old_metrics(self, days: int = 30) -> int:
        """
        Clear metrics older than specified days.

        Args:
            days: Age threshold in days

        Returns:
            Number of entries deleted
        """
        from datetime import timedelta

        cutoff = (datetime.now(UTC) - timedelta(days=days)).isoformat()

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "DELETE FROM indexing_metrics WHERE timestamp < ?",
                (cutoff,),
            )
            conn.commit()
            return cursor.rowcount
