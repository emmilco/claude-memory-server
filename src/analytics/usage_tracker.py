"""Usage pattern tracking for analytics and optimization."""

import asyncio
import sqlite3
import logging
from pathlib import Path
from datetime import datetime, timedelta, UTC
from typing import List, Dict, Optional, Any
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)


class UsagePatternTracker:
    """
    Track usage patterns for analytics and optimization.

    Features:
    - Track search queries with results and execution time
    - Track code file/function access
    - Calculate top queries and frequently accessed code
    - Generate usage statistics
    - Automatic data retention (90 days)
    """

    def __init__(self, db_path: str):
        """
        Initialize usage tracker.

        Args:
            db_path: Path to SQLite database for usage tracking
        """
        self.db_path = db_path
        self._setup_database()

    def _setup_database(self):
        """Create database schema if it doesn't exist."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Query history table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS query_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    query_text TEXT NOT NULL,
                    result_count INTEGER,
                    execution_time_ms REAL,
                    user_session TEXT,
                    query_type TEXT
                )
            """)

            # Code access log table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS code_access_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    file_path TEXT NOT NULL,
                    function_name TEXT,
                    access_type TEXT,
                    user_session TEXT
                )
            """)

            # Usage statistics table (aggregated)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS usage_statistics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    stat_type TEXT NOT NULL,
                    item_key TEXT NOT NULL,
                    access_count INTEGER DEFAULT 1,
                    last_accessed DATETIME,
                    avg_result_count REAL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(stat_type, item_key)
                )
            """)

            # Create indexes for performance
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_query_timestamp
                ON query_history(timestamp)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_code_access_timestamp
                ON code_access_log(timestamp)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_usage_stats_type
                ON usage_statistics(stat_type, access_count DESC)
            """)

            conn.commit()

    async def track_query(
        self,
        query: str,
        result_count: int,
        execution_time_ms: float,
        query_type: str = "memory",
        user_session: Optional[str] = None
    ):
        """
        Log a search query.

        Args:
            query: The search query text
            result_count: Number of results returned
            execution_time_ms: Query execution time in milliseconds
            query_type: Type of query ('memory', 'code', 'doc')
            user_session: Optional session identifier
        """
        # Run in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            self._track_query_sync,
            query,
            result_count,
            execution_time_ms,
            query_type,
            user_session
        )

    def _track_query_sync(
        self,
        query: str,
        result_count: int,
        execution_time_ms: float,
        query_type: str,
        user_session: Optional[str]
    ):
        """Synchronous query tracking."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # Insert into query history
                cursor.execute("""
                    INSERT INTO query_history
                    (query_text, result_count, execution_time_ms, query_type, user_session)
                    VALUES (?, ?, ?, ?, ?)
                """, (query, result_count, execution_time_ms, query_type, user_session))

                # Update aggregated statistics
                cursor.execute("""
                    INSERT INTO usage_statistics (stat_type, item_key, access_count, last_accessed, avg_result_count)
                    VALUES ('query', ?, 1, CURRENT_TIMESTAMP, ?)
                    ON CONFLICT(stat_type, item_key) DO UPDATE SET
                        access_count = access_count + 1,
                        last_accessed = CURRENT_TIMESTAMP,
                        avg_result_count = (
                            (avg_result_count * access_count + ?) / (access_count + 1)
                        )
                """, (query, result_count, result_count))

                conn.commit()

        except Exception as e:
            logger.error(f"Failed to track query: {e}")

    async def track_code_access(
        self,
        file_path: str,
        function_name: Optional[str] = None,
        access_type: str = "search",
        user_session: Optional[str] = None
    ):
        """
        Log code file/function access.

        Args:
            file_path: Path to the accessed file
            function_name: Optional function/method name
            access_type: Type of access ('search', 'retrieve', 'view')
            user_session: Optional session identifier
        """
        # Run in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            self._track_code_access_sync,
            file_path,
            function_name,
            access_type,
            user_session
        )

    def _track_code_access_sync(
        self,
        file_path: str,
        function_name: Optional[str],
        access_type: str,
        user_session: Optional[str]
    ):
        """Synchronous code access tracking."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # Insert into code access log
                cursor.execute("""
                    INSERT INTO code_access_log
                    (file_path, function_name, access_type, user_session)
                    VALUES (?, ?, ?, ?)
                """, (file_path, function_name, access_type, user_session))

                # Update aggregated statistics
                item_key = f"{file_path}::{function_name}" if function_name else file_path
                cursor.execute("""
                    INSERT INTO usage_statistics (stat_type, item_key, access_count, last_accessed)
                    VALUES ('code_access', ?, 1, CURRENT_TIMESTAMP)
                    ON CONFLICT(stat_type, item_key) DO UPDATE SET
                        access_count = access_count + 1,
                        last_accessed = CURRENT_TIMESTAMP
                """, (item_key,))

                conn.commit()

        except Exception as e:
            logger.error(f"Failed to track code access: {e}")

    async def get_top_queries(self, limit: int = 10, days: int = 30) -> List[Dict[str, Any]]:
        """
        Get most frequent queries.

        Args:
            limit: Maximum number of results
            days: Look back this many days

        Returns:
            List of query dictionaries with counts and stats
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self._get_top_queries_sync,
            limit,
            days
        )

    def _get_top_queries_sync(self, limit: int, days: int) -> List[Dict[str, Any]]:
        """Synchronous top queries retrieval."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                cutoff_date = (datetime.now(UTC) - timedelta(days=days)).isoformat()

                cursor.execute("""
                    SELECT
                        query_text,
                        COUNT(*) as count,
                        AVG(result_count) as avg_results,
                        AVG(execution_time_ms) as avg_time_ms,
                        MAX(timestamp) as last_used
                    FROM query_history
                    WHERE timestamp > ?
                    GROUP BY query_text
                    ORDER BY count DESC
                    LIMIT ?
                """, (cutoff_date, limit))

                results = []
                for row in cursor.fetchall():
                    results.append({
                        "query": row[0],
                        "count": row[1],
                        "avg_result_count": round(row[2], 1) if row[2] else 0,
                        "avg_execution_time_ms": round(row[3], 2) if row[3] else 0,
                        "last_used": row[4]
                    })

                return results

        except Exception as e:
            logger.error(f"Failed to get top queries: {e}")
            return []

    async def get_frequently_accessed_code(
        self,
        limit: int = 10,
        days: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Get most accessed code files/functions.

        Args:
            limit: Maximum number of results
            days: Look back this many days

        Returns:
            List of code access dictionaries
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self._get_frequently_accessed_code_sync,
            limit,
            days
        )

    def _get_frequently_accessed_code_sync(self, limit: int, days: int) -> List[Dict[str, Any]]:
        """Synchronous frequently accessed code retrieval."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                cutoff_date = (datetime.now(UTC) - timedelta(days=days)).isoformat()

                cursor.execute("""
                    SELECT
                        file_path,
                        function_name,
                        COUNT(*) as count,
                        MAX(timestamp) as last_accessed
                    FROM code_access_log
                    WHERE timestamp > ?
                    GROUP BY file_path, function_name
                    ORDER BY count DESC
                    LIMIT ?
                """, (cutoff_date, limit))

                results = []
                for row in cursor.fetchall():
                    results.append({
                        "file_path": row[0],
                        "function_name": row[1],
                        "access_count": row[2],
                        "last_accessed": row[3]
                    })

                return results

        except Exception as e:
            logger.error(f"Failed to get frequently accessed code: {e}")
            return []

    async def get_usage_stats(self, days: int = 30) -> Dict[str, Any]:
        """
        Get overall usage statistics.

        Args:
            days: Look back this many days

        Returns:
            Dictionary with usage statistics
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self._get_usage_stats_sync,
            days
        )

    def _get_usage_stats_sync(self, days: int) -> Dict[str, Any]:
        """Synchronous usage statistics retrieval."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                cutoff_date = (datetime.now(UTC) - timedelta(days=days)).isoformat()

                # Query statistics
                cursor.execute("""
                    SELECT
                        COUNT(*) as total_queries,
                        COUNT(DISTINCT query_text) as unique_queries,
                        AVG(execution_time_ms) as avg_query_time,
                        AVG(result_count) as avg_result_count
                    FROM query_history
                    WHERE timestamp > ?
                """, (cutoff_date,))

                query_row = cursor.fetchone()

                # Code access statistics
                cursor.execute("""
                    SELECT
                        COUNT(*) as total_accesses,
                        COUNT(DISTINCT file_path) as unique_files,
                        COUNT(DISTINCT function_name) as unique_functions
                    FROM code_access_log
                    WHERE timestamp > ?
                """, (cutoff_date,))

                code_row = cursor.fetchone()

                # Most active day
                cursor.execute("""
                    SELECT DATE(timestamp) as day, COUNT(*) as count
                    FROM query_history
                    WHERE timestamp > ?
                    GROUP BY day
                    ORDER BY count DESC
                    LIMIT 1
                """, (cutoff_date,))

                most_active_row = cursor.fetchone()

                return {
                    "total_queries": query_row[0] or 0,
                    "unique_queries": query_row[1] or 0,
                    "avg_query_time": round(query_row[2], 2) if query_row[2] else 0,
                    "avg_result_count": round(query_row[3], 1) if query_row[3] else 0,
                    "total_code_accesses": code_row[0] or 0,
                    "unique_files": code_row[1] or 0,
                    "unique_functions": code_row[2] or 0,
                    "most_active_day": most_active_row[0] if most_active_row else None,
                    "most_active_day_count": most_active_row[1] if most_active_row else 0
                }

        except Exception as e:
            logger.error(f"Failed to get usage stats: {e}")
            return {}

    async def cleanup_old_data(self, days: int = 90):
        """
        Remove data older than specified days.

        Args:
            days: Delete data older than this many days
        """
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            self._cleanup_old_data_sync,
            days
        )

    def _cleanup_old_data_sync(self, days: int):
        """Synchronous old data cleanup."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                cutoff_date = (datetime.now(UTC) - timedelta(days=days)).isoformat()

                # Delete old query history
                cursor.execute("""
                    DELETE FROM query_history
                    WHERE timestamp < ?
                """, (cutoff_date,))

                query_deleted = cursor.rowcount

                # Delete old code access logs
                cursor.execute("""
                    DELETE FROM code_access_log
                    WHERE timestamp < ?
                """, (cutoff_date,))

                code_deleted = cursor.rowcount

                conn.commit()

                logger.info(
                    f"Cleaned up usage data: {query_deleted} queries, "
                    f"{code_deleted} code accesses older than {days} days"
                )

        except Exception as e:
            logger.error(f"Failed to cleanup old data: {e}")
