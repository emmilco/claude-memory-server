"""Tests for UsagePatternTracker (FEAT-020)."""

import pytest
import pytest_asyncio
import asyncio
import sqlite3
import tempfile
import os
from datetime import datetime, timedelta, UTC

from src.analytics.usage_tracker import UsagePatternTracker


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    # Cleanup
    try:
        os.unlink(path)
    except FileNotFoundError:
        pass


@pytest.fixture
def tracker(temp_db):
    """Create a UsagePatternTracker instance."""
    return UsagePatternTracker(db_path=temp_db)


@pytest_asyncio.fixture
async def populated_tracker(temp_db):
    """Create a tracker with some test data."""
    tracker = UsagePatternTracker(db_path=temp_db)

    # Add some queries
    await tracker.track_query("test query 1", 5, 10.5, "memory")
    await tracker.track_query("test query 2", 3, 8.2, "code")
    await tracker.track_query("test query 1", 7, 12.1, "memory")  # Duplicate

    # Add some code access
    await tracker.track_code_access("file1.py", "function1", "search")
    await tracker.track_code_access("file1.py", "function2", "retrieve")
    await tracker.track_code_access("file1.py", "function1", "view")  # Duplicate

    return tracker


class TestDatabaseSetup:
    """Test database schema creation."""

    def test_database_created(self, tracker, temp_db):
        """Test that database file is created."""
        assert os.path.exists(temp_db)

    def test_tables_created(self, tracker, temp_db):
        """Test that required tables are created."""
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()

        # Check query_history table
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='query_history'
        """)
        assert cursor.fetchone() is not None

        # Check code_access_log table
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='code_access_log'
        """)
        assert cursor.fetchone() is not None

        # Check usage_statistics table
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='usage_statistics'
        """)
        assert cursor.fetchone() is not None

        conn.close()

    def test_indexes_created(self, tracker, temp_db):
        """Test that performance indexes are created."""
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='index'
        """)
        indexes = [row[0] for row in cursor.fetchall()]

        assert "idx_query_timestamp" in indexes
        assert "idx_code_access_timestamp" in indexes
        assert "idx_usage_stats_type" in indexes

        conn.close()


class TestQueryTracking:
    """Test query tracking functionality."""

    @pytest.mark.asyncio
    async def test_track_query_basic(self, tracker, temp_db):
        """Test basic query tracking."""
        await tracker.track_query(
            query="test query",
            result_count=5,
            execution_time_ms=10.5,
            query_type="memory",
        )

        # Verify data was inserted
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM query_history")
        rows = cursor.fetchall()
        conn.close()

        assert len(rows) == 1
        assert rows[0][2] == "test query"  # query_text
        assert rows[0][3] == 5  # result_count
        assert rows[0][4] == 10.5  # execution_time_ms
        assert rows[0][6] == "memory"  # query_type

    @pytest.mark.asyncio
    async def test_track_query_with_session(self, tracker, temp_db):
        """Test query tracking with user session."""
        await tracker.track_query(
            query="test query",
            result_count=3,
            execution_time_ms=8.2,
            query_type="code",
            user_session="session-123",
        )

        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute("SELECT user_session FROM query_history")
        session = cursor.fetchone()[0]
        conn.close()

        assert session == "session-123"

    @pytest.mark.asyncio
    async def test_track_query_updates_statistics(self, tracker, temp_db):
        """Test that query tracking updates usage statistics."""
        query = "repeated query"

        # Track same query multiple times
        await tracker.track_query(query, 5, 10.0)
        await tracker.track_query(query, 7, 12.0)
        await tracker.track_query(query, 3, 8.0)

        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT access_count, avg_result_count
            FROM usage_statistics
            WHERE stat_type='query' AND item_key=?
        """,
            (query,),
        )
        row = cursor.fetchone()
        conn.close()

        assert row[0] == 3  # access_count
        assert 4.5 < row[1] < 5.5  # avg_result_count (approx 5)

    @pytest.mark.asyncio
    async def test_track_multiple_queries(self, tracker, temp_db):
        """Test tracking multiple different queries."""
        await tracker.track_query("query 1", 5, 10.0)
        await tracker.track_query("query 2", 3, 8.0)
        await tracker.track_query("query 3", 7, 12.0)

        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(DISTINCT query_text) FROM query_history")
        count = cursor.fetchone()[0]
        conn.close()

        assert count == 3


class TestCodeAccessTracking:
    """Test code access tracking functionality."""

    @pytest.mark.asyncio
    async def test_track_code_access_basic(self, tracker, temp_db):
        """Test basic code access tracking."""
        await tracker.track_code_access(
            file_path="src/test.py", function_name="test_function", access_type="search"
        )

        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM code_access_log")
        rows = cursor.fetchall()
        conn.close()

        assert len(rows) == 1
        assert rows[0][2] == "src/test.py"  # file_path
        assert rows[0][3] == "test_function"  # function_name
        assert rows[0][4] == "search"  # access_type

    @pytest.mark.asyncio
    async def test_track_code_access_file_only(self, tracker, temp_db):
        """Test tracking code access without function name."""
        await tracker.track_code_access(file_path="src/test.py", access_type="view")

        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute("SELECT function_name FROM code_access_log")
        function_name = cursor.fetchone()[0]
        conn.close()

        assert function_name is None

    @pytest.mark.asyncio
    async def test_track_code_access_updates_statistics(self, tracker, temp_db):
        """Test that code access updates statistics correctly."""
        file_path = "src/test.py"
        function_name = "test_func"

        # Track same code multiple times
        await tracker.track_code_access(file_path, function_name, "search")
        await tracker.track_code_access(file_path, function_name, "view")
        await tracker.track_code_access(file_path, function_name, "retrieve")

        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        item_key = f"{file_path}::{function_name}"
        cursor.execute(
            """
            SELECT access_count
            FROM usage_statistics
            WHERE stat_type='code_access' AND item_key=?
        """,
            (item_key,),
        )
        count = cursor.fetchone()[0]
        conn.close()

        assert count == 3

    @pytest.mark.asyncio
    async def test_track_code_access_with_session(self, tracker, temp_db):
        """Test code access tracking with user session."""
        await tracker.track_code_access(
            file_path="src/test.py",
            function_name="test_func",
            access_type="search",
            user_session="session-456",
        )

        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute("SELECT user_session FROM code_access_log")
        session = cursor.fetchone()[0]
        conn.close()

        assert session == "session-456"


class TestTopQueries:
    """Test top queries retrieval."""

    @pytest.mark.asyncio
    async def test_get_top_queries_basic(self, populated_tracker):
        """Test getting top queries."""
        queries = await populated_tracker.get_top_queries(limit=10, days=30)

        assert len(queries) > 0
        assert queries[0]["query"] == "test query 1"  # Most frequent
        assert queries[0]["count"] == 2

    @pytest.mark.asyncio
    async def test_get_top_queries_limit(self, populated_tracker):
        """Test limit parameter."""
        # Add more queries
        for i in range(10):
            await populated_tracker.track_query(f"query {i}", 1, 1.0)

        queries = await populated_tracker.get_top_queries(limit=5, days=30)

        assert len(queries) <= 5

    @pytest.mark.asyncio
    async def test_get_top_queries_empty(self, tracker):
        """Test getting top queries when no data exists."""
        queries = await tracker.get_top_queries(limit=10, days=30)

        assert queries == []

    @pytest.mark.asyncio
    async def test_get_top_queries_time_filtering(self, temp_db):
        """Test time-based filtering of queries."""
        tracker = UsagePatternTracker(db_path=temp_db)

        # Add recent query
        await tracker.track_query("recent query", 5, 10.0)

        # Add old query manually (31 days ago)
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        old_date = (datetime.now(UTC) - timedelta(days=31)).isoformat()
        cursor.execute(
            """
            INSERT INTO query_history (query_text, result_count, execution_time_ms, timestamp)
            VALUES (?, ?, ?, ?)
        """,
            ("old query", 3, 8.0, old_date),
        )
        conn.commit()
        conn.close()

        # Get queries from last 30 days
        queries = await tracker.get_top_queries(limit=10, days=30)

        query_texts = [q["query"] for q in queries]
        assert "recent query" in query_texts
        assert "old query" not in query_texts

    @pytest.mark.asyncio
    async def test_get_top_queries_statistics(self, populated_tracker):
        """Test that statistics are calculated correctly."""
        queries = await populated_tracker.get_top_queries(limit=10, days=30)

        # Find "test query 1" which was tracked twice (5 results, 7 results)
        query_1 = next(q for q in queries if q["query"] == "test query 1")

        assert query_1["count"] == 2
        assert query_1["avg_result_count"] == 6.0  # (5 + 7) / 2
        assert query_1["avg_execution_time_ms"] > 0
        assert query_1["last_used"] is not None


class TestFrequentlyAccessedCode:
    """Test frequently accessed code retrieval."""

    @pytest.mark.asyncio
    async def test_get_frequently_accessed_code_basic(self, populated_tracker):
        """Test getting frequently accessed code."""
        code_items = await populated_tracker.get_frequently_accessed_code(
            limit=10, days=30
        )

        assert len(code_items) > 0
        # "file1.py::function1" was accessed twice
        assert any(
            item["file_path"] == "file1.py"
            and item["function_name"] == "function1"
            and item["access_count"] == 2
            for item in code_items
        )

    @pytest.mark.asyncio
    async def test_get_frequently_accessed_code_limit(self, populated_tracker):
        """Test limit parameter."""
        # Add more code accesses
        for i in range(10):
            await populated_tracker.track_code_access(f"file{i}.py", f"func{i}")

        code_items = await populated_tracker.get_frequently_accessed_code(
            limit=5, days=30
        )

        assert len(code_items) <= 5

    @pytest.mark.asyncio
    async def test_get_frequently_accessed_code_empty(self, tracker):
        """Test getting code when no data exists."""
        code_items = await tracker.get_frequently_accessed_code(limit=10, days=30)

        assert code_items == []

    @pytest.mark.asyncio
    async def test_get_frequently_accessed_code_time_filtering(self, temp_db):
        """Test time-based filtering of code access."""
        tracker = UsagePatternTracker(db_path=temp_db)

        # Add recent access
        await tracker.track_code_access("recent.py", "recent_func")

        # Add old access manually
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        old_date = (datetime.now(UTC) - timedelta(days=31)).isoformat()
        cursor.execute(
            """
            INSERT INTO code_access_log (file_path, function_name, access_type, timestamp)
            VALUES (?, ?, ?, ?)
        """,
            ("old.py", "old_func", "search", old_date),
        )
        conn.commit()
        conn.close()

        # Get code from last 30 days
        code_items = await tracker.get_frequently_accessed_code(limit=10, days=30)

        file_paths = [item["file_path"] for item in code_items]
        assert "recent.py" in file_paths
        assert "old.py" not in file_paths


class TestUsageStatistics:
    """Test overall usage statistics."""

    @pytest.mark.asyncio
    async def test_get_usage_stats_basic(self, populated_tracker):
        """Test getting usage statistics."""
        stats = await populated_tracker.get_usage_stats(days=30)

        assert stats["total_queries"] >= 3
        assert stats["unique_queries"] == 2  # "test query 1" and "test query 2"
        assert stats["total_code_accesses"] >= 3
        assert stats["unique_files"] == 1  # "file1.py"
        assert stats["unique_functions"] >= 2  # "function1" and "function2"

    @pytest.mark.asyncio
    async def test_get_usage_stats_empty(self, tracker):
        """Test statistics when no data exists."""
        stats = await tracker.get_usage_stats(days=30)

        assert stats["total_queries"] == 0
        assert stats["unique_queries"] == 0
        assert stats["total_code_accesses"] == 0
        assert stats["unique_files"] == 0

    @pytest.mark.asyncio
    async def test_get_usage_stats_averages(self, tracker):
        """Test that averages are calculated correctly."""
        # Add queries with known values
        await tracker.track_query("query 1", 10, 20.0)
        await tracker.track_query("query 2", 20, 40.0)

        stats = await tracker.get_usage_stats(days=30)

        assert stats["avg_result_count"] == 15.0  # (10 + 20) / 2
        assert stats["avg_query_time"] == 30.0  # (20 + 40) / 2

    @pytest.mark.asyncio
    async def test_get_usage_stats_most_active_day(self, tracker):
        """Test most active day calculation."""
        # Add multiple queries
        for i in range(5):
            await tracker.track_query(f"query {i}", 1, 1.0)

        stats = await tracker.get_usage_stats(days=30)

        assert stats["most_active_day"] is not None
        assert stats["most_active_day_count"] == 5


class TestDataCleanup:
    """Test old data cleanup."""

    @pytest.mark.asyncio
    async def test_cleanup_old_data(self, temp_db):
        """Test cleanup of old data."""
        tracker = UsagePatternTracker(db_path=temp_db)

        # Add recent data
        await tracker.track_query("recent query", 5, 10.0)
        await tracker.track_code_access("recent.py", "recent_func")

        # Add old data manually
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        old_date = (datetime.now(UTC) - timedelta(days=91)).isoformat()

        cursor.execute(
            """
            INSERT INTO query_history (query_text, result_count, execution_time_ms, timestamp)
            VALUES (?, ?, ?, ?)
        """,
            ("old query", 3, 8.0, old_date),
        )

        cursor.execute(
            """
            INSERT INTO code_access_log (file_path, function_name, access_type, timestamp)
            VALUES (?, ?, ?, ?)
        """,
            ("old.py", "old_func", "search", old_date),
        )

        conn.commit()
        conn.close()

        # Run cleanup
        await tracker.cleanup_old_data(days=90)

        # Verify old data was deleted
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()

        cursor.execute("SELECT query_text FROM query_history")
        queries = [row[0] for row in cursor.fetchall()]

        cursor.execute("SELECT file_path FROM code_access_log")
        files = [row[0] for row in cursor.fetchall()]

        conn.close()

        assert "recent query" in queries
        assert "old query" not in queries
        assert "recent.py" in files
        assert "old.py" not in files


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_track_query_error_recovery(self, temp_db):
        """Test that query tracking errors don't crash the system."""
        tracker = UsagePatternTracker(db_path=temp_db)

        # Close the database connection to simulate error
        os.unlink(temp_db)

        # Should not raise exception (errors are logged)
        await tracker.track_query("test", 1, 1.0)

    @pytest.mark.asyncio
    async def test_track_code_access_error_recovery(self, temp_db):
        """Test that code access tracking errors don't crash the system."""
        tracker = UsagePatternTracker(db_path=temp_db)

        # Close the database connection to simulate error
        os.unlink(temp_db)

        # Should not raise exception (errors are logged)
        await tracker.track_code_access("test.py", "test_func")

    @pytest.mark.asyncio
    async def test_get_top_queries_error_recovery(self, temp_db):
        """Test error recovery when fetching top queries."""
        tracker = UsagePatternTracker(db_path=temp_db)

        # Delete database to simulate error
        os.unlink(temp_db)

        # Should return empty list on error
        queries = await tracker.get_top_queries(limit=10, days=30)
        assert queries == []

    @pytest.mark.asyncio
    async def test_concurrent_tracking(self, tracker):
        """Test concurrent tracking operations."""
        # Track multiple items concurrently
        tasks = [tracker.track_query(f"query {i}", i, float(i)) for i in range(10)]
        tasks.extend(
            [tracker.track_code_access(f"file{i}.py", f"func{i}") for i in range(10)]
        )

        # Should complete without errors
        await asyncio.gather(*tasks)

        stats = await tracker.get_usage_stats(days=30)
        assert stats["total_queries"] == 10
        assert stats["total_code_accesses"] == 10
