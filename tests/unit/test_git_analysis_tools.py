"""Unit tests for FEAT-061 git analysis tools.

Tests the 5 new MCP tools:
- get_change_frequency
- get_churn_hotspots
- get_recent_changes
- blame_search
- get_code_authors
"""

import pytest
import pytest_asyncio
from datetime import datetime, UTC, timedelta
from unittest.mock import Mock, AsyncMock, patch

from src.core.server import MemoryRAGServer
from src.config import ServerConfig


@pytest.fixture
def config():
    """Create test configuration."""
    return ServerConfig(
        storage_backend="qdrant",
        qdrant_url="http://localhost:6333",
    )


@pytest_asyncio.fixture
async def server(config):
    """Create and initialize server with mocked store."""
    server = MemoryRAGServer(config)

    # Mock the store to avoid actual database operations
    server.store = AsyncMock()
    server.embedding_generator = AsyncMock()
    server.embedding_cache = Mock()

    yield server


@pytest.fixture
def sample_commits():
    """Sample commit data for testing."""
    base_date = datetime.now(UTC)
    return [
        {
            "commit_hash": "abc123",
            "author_name": "Alice",
            "author_email": "alice@example.com",
            "author_date": base_date - timedelta(days=i),
            "message": f"Commit {i}",
            "change_type": "modified",
            "lines_added": 10 + i,
            "lines_deleted": 5 + i,
            "stats": {"files_changed": 2, "insertions": 10+i, "deletions": 5+i},
        }
        for i in range(10)
    ]


# Tests for get_change_frequency


@pytest.mark.asyncio
async def test_get_change_frequency_basic(server, sample_commits):
    """Test basic change frequency calculation."""
    server.store.get_commits_by_file = AsyncMock(return_value=sample_commits)

    result = await server.get_change_frequency("src/test.py")

    assert result["file_path"] == "src/test.py"
    assert result["total_changes"] == 10
    assert result["churn_score"] >= 0.0
    assert result["churn_score"] <= 1.0
    assert "interpretation" in result
    assert result["unique_authors"] >= 1


@pytest.mark.asyncio
async def test_get_change_frequency_no_changes(server):
    """Test change frequency with no commits."""
    server.store.get_commits_by_file = AsyncMock(return_value=[])

    result = await server.get_change_frequency("src/test.py")

    assert result["file_path"] == "src/test.py"
    assert result["total_changes"] == 0
    assert result["churn_score"] == 0.0
    assert "no changes" in result["interpretation"]


@pytest.mark.asyncio
async def test_get_change_frequency_with_date_filter(server, sample_commits):
    """Test change frequency with date filtering."""
    server.store.get_commits_by_file = AsyncMock(return_value=sample_commits[:5])

    result = await server.get_change_frequency("src/test.py", since="2024-01-01")

    assert result["total_changes"] == 5
    server.store.get_commits_by_file.assert_called_once()


@pytest.mark.asyncio
async def test_get_change_frequency_churn_score_calculation(server):
    """Test churn score calculation with different scenarios."""
    # High churn scenario: many changes, large sizes
    high_churn_commits = [
        {
            "author_email": f"user{i}@example.com",
            "author_date": datetime.now(UTC) - timedelta(days=i),
            "change_type": "modified",
            "lines_added": 200,
            "lines_deleted": 150,
        }
        for i in range(50)  # 50 commits over 50 days = high churn
    ]

    server.store.get_commits_by_file = AsyncMock(return_value=high_churn_commits)
    result = await server.get_change_frequency("src/high_churn.py")

    # Should have high churn score
    assert result["churn_score"] > 0.5
    assert "high churn" in result["interpretation"].lower() or "medium churn" in result["interpretation"].lower()


# Tests for get_churn_hotspots


@pytest.mark.asyncio
async def test_get_churn_hotspots_basic(server):
    """Test basic churn hotspots detection."""
    server.store.search_git_commits = AsyncMock(return_value=[])

    result = await server.get_churn_hotspots(limit=5, days=90)

    assert "hotspots" in result
    assert "analysis_period_days" in result
    assert result["analysis_period_days"] == 90


@pytest.mark.asyncio
async def test_get_churn_hotspots_empty(server):
    """Test churn hotspots with no commits."""
    server.store.search_git_commits = AsyncMock(return_value=[])

    result = await server.get_churn_hotspots()

    assert result["hotspots"] == []
    assert result["total_files_analyzed"] == 0


# Tests for get_recent_changes


@pytest.mark.asyncio
async def test_get_recent_changes_basic(server, sample_commits):
    """Test getting recent changes."""
    server.store.search_git_commits = AsyncMock(return_value=sample_commits)

    result = await server.get_recent_changes(days=7, limit=5)

    assert "changes" in result
    assert result["period_days"] == 7
    assert len(result["changes"]) <= 5


@pytest.mark.asyncio
async def test_get_recent_changes_empty(server):
    """Test recent changes with no commits."""
    server.store.search_git_commits = AsyncMock(return_value=[])

    result = await server.get_recent_changes(days=30)

    assert result["changes"] == []
    assert result["total_changes"] == 0


@pytest.mark.asyncio
async def test_get_recent_changes_sorting(server, sample_commits):
    """Test that recent changes are sorted by date descending."""
    server.store.search_git_commits = AsyncMock(return_value=sample_commits)

    result = await server.get_recent_changes(days=30, limit=10)

    # Check that dates are in descending order
    changes = result["changes"]
    if len(changes) > 1:
        for i in range(len(changes) - 1):
            date1 = changes[i]["commit_date"]
            date2 = changes[i+1]["commit_date"]
            # More recent (higher date) should come first
            assert date1 >= date2


# Tests for blame_search


@pytest.mark.asyncio
async def test_blame_search_basic(server, sample_commits):
    """Test basic blame search."""
    server.store.search_git_commits = AsyncMock(return_value=sample_commits[:3])

    result = await server.blame_search("authentication")

    assert "results" in result
    assert "pattern" in result
    assert result["pattern"] == "authentication"
    assert len(result["results"]) == 3


@pytest.mark.asyncio
async def test_blame_search_no_matches(server):
    """Test blame search with no matches."""
    server.store.search_git_commits = AsyncMock(return_value=[])

    result = await server.blame_search("nonexistent_pattern")

    assert result["results"] == []
    assert result["total_matches"] == 0


@pytest.mark.asyncio
async def test_blame_search_result_format(server, sample_commits):
    """Test that blame search results have correct format."""
    server.store.search_git_commits = AsyncMock(return_value=sample_commits[:1])

    result = await server.blame_search("test pattern")

    assert len(result["results"]) == 1
    match = result["results"][0]

    assert "commit_hash" in match
    assert "author" in match
    assert "commit_date" in match
    assert "commit_message" in match
    assert "relevance" in match


# Tests for get_code_authors


@pytest.mark.asyncio
async def test_get_code_authors_basic(server, sample_commits):
    """Test getting code authors."""
    server.store.get_commits_by_file = AsyncMock(return_value=sample_commits)

    result = await server.get_code_authors("src/test.py")

    assert "file_path" in result
    assert result["file_path"] == "src/test.py"
    assert "authors" in result
    assert len(result["authors"]) >= 1


@pytest.mark.asyncio
async def test_get_code_authors_no_commits(server):
    """Test code authors with no commits."""
    server.store.get_commits_by_file = AsyncMock(return_value=[])

    result = await server.get_code_authors("src/test.py")

    assert result["authors"] == []
    assert result["total_commits"] == 0


@pytest.mark.asyncio
async def test_get_code_authors_multiple_authors(server):
    """Test code authors with multiple contributors."""
    commits = [
        {
            "author_name": "Alice",
            "author_email": "alice@example.com",
            "author_date": datetime.now(UTC),
            "lines_added": 100,
            "lines_deleted": 50,
        },
        {
            "author_name": "Bob",
            "author_email": "bob@example.com",
            "author_date": datetime.now(UTC) - timedelta(days=1),
            "lines_added": 200,
            "lines_deleted": 100,
        },
        {
            "author_name": "Alice",
            "author_email": "alice@example.com",
            "author_date": datetime.now(UTC) - timedelta(days=2),
            "lines_added": 50,
            "lines_deleted": 25,
        },
    ]

    server.store.get_commits_by_file = AsyncMock(return_value=commits)

    result = await server.get_code_authors("src/test.py")

    # Should have 2 unique authors
    assert len(result["authors"]) == 2

    # Alice should have 2 commits
    alice = next((a for a in result["authors"] if a["author_email"] == "alice@example.com"), None)
    assert alice is not None
    assert alice["commit_count"] == 2
    assert alice["lines_added"] == 150
    assert alice["lines_deleted"] == 75


@pytest.mark.asyncio
async def test_get_code_authors_sorted_by_commits(server):
    """Test that authors are sorted by commit count."""
    commits = [
        {"author_email": "alice@example.com", "author_name": "Alice", "author_date": datetime.now(UTC), "lines_added": 10, "lines_deleted": 5},
        {"author_email": "bob@example.com", "author_name": "Bob", "author_date": datetime.now(UTC), "lines_added": 10, "lines_deleted": 5},
        {"author_email": "alice@example.com", "author_name": "Alice", "author_date": datetime.now(UTC), "lines_added": 10, "lines_deleted": 5},
        {"author_email": "alice@example.com", "author_name": "Alice", "author_date": datetime.now(UTC), "lines_added": 10, "lines_deleted": 5},
        {"author_email": "bob@example.com", "author_name": "Bob", "author_date": datetime.now(UTC), "lines_added": 10, "lines_deleted": 5},
    ]

    server.store.get_commits_by_file = AsyncMock(return_value=commits)

    result = await server.get_code_authors("src/test.py")

    # Alice has 3 commits, Bob has 2 - Alice should be first
    assert result["authors"][0]["author_email"] == "alice@example.com"
    assert result["authors"][0]["commit_count"] == 3
    assert result["authors"][1]["author_email"] == "bob@example.com"
    assert result["authors"][1]["commit_count"] == 2


# Tests for get_file_history (alias test)


@pytest.mark.asyncio
async def test_get_file_history_alias(server, sample_commits):
    """Test that get_file_history correctly calls show_function_evolution."""
    # Mock show_function_evolution
    server.show_function_evolution = AsyncMock(return_value={"status": "success", "commits": []})

    await server.get_file_history("src/test.py", limit=50)

    # Verify it was called with correct parameters
    server.show_function_evolution.assert_called_once_with("src/test.py", None, 50)


# Edge case tests


@pytest.mark.asyncio
async def test_change_frequency_handles_missing_dates(server):
    """Test change frequency with commits missing date fields."""
    commits = [
        {
            "author_email": "user@example.com",
            "author_date": None,  # Missing date
            "lines_added": 10,
            "lines_deleted": 5,
        }
    ]

    server.store.get_commits_by_file = AsyncMock(return_value=commits)

    result = await server.get_change_frequency("src/test.py")

    # Should handle gracefully
    assert result["total_changes"] == 1
    assert "no date information" in result["interpretation"]


@pytest.mark.asyncio
async def test_change_frequency_single_commit(server):
    """Test change frequency with only one commit."""
    commits = [
        {
            "author_email": "user@example.com",
            "author_date": datetime.now(UTC),
            "change_type": "added",
            "lines_added": 100,
            "lines_deleted": 0,
        }
    ]

    server.store.get_commits_by_file = AsyncMock(return_value=commits)

    result = await server.get_change_frequency("src/test.py")

    # Should handle single commit without errors
    assert result["total_changes"] == 1
    assert result["churn_score"] >= 0.0
