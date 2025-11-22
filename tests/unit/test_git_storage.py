"""Unit tests for git storage in SQLite."""

import pytest
import pytest_asyncio
import tempfile
import uuid
from datetime import datetime, UTC, timedelta
from pathlib import Path

from src.store.qdrant_store import QdrantMemoryStore
from src.config import ServerConfig


@pytest.fixture
def config(unique_qdrant_collection):
    """Create test configuration with pooled collection name.

    Uses the unique_qdrant_collection from conftest.py to leverage
    collection pooling and prevent Qdrant deadlocks during parallel execution.
    """
    config = ServerConfig(
        storage_backend="qdrant",
        qdrant_url="http://localhost:6333",
        qdrant_collection_name=unique_qdrant_collection,
        enable_git_indexing=True,
    )
    return config


@pytest_asyncio.fixture
async def store(config, qdrant_client):
    """Create and initialize Qdrant store with pooled collection.

    Uses the session-scoped qdrant_client and unique_qdrant_collection
    fixtures from conftest.py to leverage collection pooling and prevent
    Qdrant deadlocks during parallel test execution.
    """
    store = QdrantMemoryStore(config)
    await store.initialize()
    yield store

    # Cleanup
    await store.close()
    # Collection cleanup handled by unique_qdrant_collection autouse fixture


@pytest.fixture
def sample_commit():
    """Create sample commit data."""
    return {
        "commit_hash": "abc123def456",
        "repository_path": "/repo/path",
        "author_name": "Test Author",
        "author_email": "author@example.com",
        "author_date": datetime.now(UTC),
        "committer_name": "Test Committer",
        "committer_date": datetime.now(UTC),
        "message": "Test commit message",
        "message_embedding": [0.1] * 384,
        "branch_names": ["main", "develop"],
        "tags": ["v1.0.0"],
        "parent_hashes": ["parent123"],
        "stats": {
            "files_changed": 2,
            "insertions": 10,
            "deletions": 5,
        },
    }


@pytest.fixture
def sample_file_change():
    """Create sample file change data."""
    return {
        "id": "abc123def456:src/file.py",
        "commit_hash": "abc123def456",
        "file_path": "src/file.py",
        "change_type": "modified",
        "lines_added": 10,
        "lines_deleted": 5,
        "diff_content": "+added line\n-removed line",
        "diff_embedding": [0.2] * 384,
    }


class TestStoreGitCommits:
    """Test storing git commits."""

    @pytest.mark.asyncio
    async def test_store_single_commit(self, store, sample_commit):
        """Test storing a single commit."""
        count = await store.store_git_commits([sample_commit])
        assert count == 1

        # Verify stored
        result = await store.get_git_commit(sample_commit["commit_hash"])
        assert result is not None
        assert result["commit_hash"] == sample_commit["commit_hash"]
        assert result["author_name"] == sample_commit["author_name"]
        assert result["message"] == sample_commit["message"]
        assert len(result["message_embedding"]) == 384

    @pytest.mark.asyncio
    async def test_store_multiple_commits(self, store):
        """Test storing multiple commits."""
        commits = []
        for i in range(5):
            commits.append({
                "commit_hash": f"commit{i}",
                "repository_path": "/repo",
                "author_name": f"Author {i}",
                "author_email": f"author{i}@example.com",
                "author_date": datetime.now(UTC) - timedelta(days=i),
                "committer_name": f"Committer {i}",
                "committer_date": datetime.now(UTC) - timedelta(days=i),
                "message": f"Commit {i}",
                "message_embedding": [0.1 * i] * 384,
                "branch_names": ["main"],
                "tags": [],
                "parent_hashes": [],
                "stats": {"files_changed": i, "insertions": i * 2, "deletions": i},
            })

        count = await store.store_git_commits(commits)
        assert count == 5

        # Verify all stored
        for i in range(5):
            result = await store.get_git_commit(f"commit{i}")
            assert result is not None
            assert result["message"] == f"Commit {i}"

    @pytest.mark.asyncio
    async def test_store_commit_replace(self, store, sample_commit):
        """Test replacing an existing commit."""
        # Store initial
        await store.store_git_commits([sample_commit])

        # Update and store again
        sample_commit["message"] = "Updated message"
        await store.store_git_commits([sample_commit])

        # Verify updated
        result = await store.get_git_commit(sample_commit["commit_hash"])
        assert result["message"] == "Updated message"

    @pytest.mark.asyncio
    async def test_store_commit_with_empty_lists(self, store, sample_commit):
        """Test storing commit with empty branch/tag lists."""
        sample_commit["branch_names"] = []
        sample_commit["tags"] = []
        sample_commit["parent_hashes"] = []

        count = await store.store_git_commits([sample_commit])
        assert count == 1

        result = await store.get_git_commit(sample_commit["commit_hash"])
        assert result["branch_names"] == []
        assert result["tags"] == []
        assert result["parent_hashes"] == []

    @pytest.mark.asyncio
    async def test_store_commit_fts_index(self, store, sample_commit):
        """Test FTS index is created for commit message."""
        await store.store_git_commits([sample_commit])

        # Search using FTS
        results = await store.search_git_commits(query="Test commit")
        assert len(results) == 1
        assert results[0]["commit_hash"] == sample_commit["commit_hash"]


class TestStoreGitFileChanges:
    """Test storing git file changes."""

    @pytest.mark.asyncio
    async def test_store_single_file_change(self, store, sample_commit, sample_file_change):
        """Test storing a single file change."""
        # Store commit first
        await store.store_git_commits([sample_commit])

        # Store file change
        count = await store.store_git_file_changes([sample_file_change])
        assert count == 1

    @pytest.mark.asyncio
    async def test_store_multiple_file_changes(self, store, sample_commit):
        """Test storing multiple file changes."""
        await store.store_git_commits([sample_commit])

        file_changes = []
        for i in range(3):
            file_changes.append({
                "id": f"{sample_commit['commit_hash']}:file{i}.py",
                "commit_hash": sample_commit["commit_hash"],
                "file_path": f"src/file{i}.py",
                "change_type": "modified",
                "lines_added": i * 2,
                "lines_deleted": i,
                "diff_content": f"diff {i}",
                "diff_embedding": [0.1 * i] * 384,
            })

        count = await store.store_git_file_changes(file_changes)
        assert count == 3

    @pytest.mark.asyncio
    async def test_store_file_change_without_diff(self, store, sample_commit):
        """Test storing file change without diff content."""
        await store.store_git_commits([sample_commit])

        file_change = {
            "id": f"{sample_commit['commit_hash']}:file.py",
            "commit_hash": sample_commit["commit_hash"],
            "file_path": "file.py",
            "change_type": "added",
            "lines_added": 10,
            "lines_deleted": 0,
            "diff_content": None,
            "diff_embedding": None,
        }

        count = await store.store_git_file_changes([file_change])
        assert count == 1

    @pytest.mark.asyncio
    async def test_store_file_change_replace(self, store, sample_commit, sample_file_change):
        """Test replacing an existing file change."""
        await store.store_git_commits([sample_commit])
        await store.store_git_file_changes([sample_file_change])

        # Update and store again
        sample_file_change["lines_added"] = 20
        await store.store_git_file_changes([sample_file_change])

        # Note: Direct verification would require a get_file_change method
        # For now, we just verify it doesn't raise an error


class TestSearchGitCommits:
    """Test searching git commits."""

    @pytest.mark.asyncio
    async def test_search_all_commits(self, store):
        """Test searching without filters returns all commits."""
        commits = []
        for i in range(3):
            commits.append({
                "commit_hash": f"commit{i}",
                "repository_path": "/repo",
                "author_name": f"Author {i}",
                "author_email": f"author{i}@example.com",
                "author_date": datetime.now(UTC) - timedelta(days=i),
                "committer_name": f"Committer {i}",
                "committer_date": datetime.now(UTC),
                "message": f"Message {i}",
                "message_embedding": [0.1] * 384,
                "branch_names": [],
                "tags": [],
                "parent_hashes": [],
                "stats": {},
            })

        await store.store_git_commits(commits)

        results = await store.search_git_commits()
        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_search_by_query(self, store):
        """Test FTS text search."""
        commits = [
            {
                "commit_hash": "commit1",
                "repository_path": "/repo",
                "author_name": "Author",
                "author_email": "author@example.com",
                "author_date": datetime.now(UTC),
                "committer_name": "Committer",
                "committer_date": datetime.now(UTC),
                "message": "Fix authentication bug",
                "message_embedding": [0.1] * 384,
                "branch_names": [],
                "tags": [],
                "parent_hashes": [],
                "stats": {},
            },
            {
                "commit_hash": "commit2",
                "repository_path": "/repo",
                "author_name": "Author",
                "author_email": "author@example.com",
                "author_date": datetime.now(UTC),
                "committer_name": "Committer",
                "committer_date": datetime.now(UTC),
                "message": "Add new feature",
                "message_embedding": [0.1] * 384,
                "branch_names": [],
                "tags": [],
                "parent_hashes": [],
                "stats": {},
            },
        ]

        await store.store_git_commits(commits)

        results = await store.search_git_commits(query="authentication")
        assert len(results) == 1
        assert results[0]["commit_hash"] == "commit1"

    @pytest.mark.asyncio
    async def test_search_by_repository(self, store):
        """Test filtering by repository path."""
        commits = []
        for i, repo in enumerate(["/repo1", "/repo2"]):
            commits.append({
                "commit_hash": f"commit{i}",
                "repository_path": repo,
                "author_name": "Author",
                "author_email": "author@example.com",
                "author_date": datetime.now(UTC),
                "committer_name": "Committer",
                "committer_date": datetime.now(UTC),
                "message": f"Commit {i}",
                "message_embedding": [0.1] * 384,
                "branch_names": [],
                "tags": [],
                "parent_hashes": [],
                "stats": {},
            })

        await store.store_git_commits(commits)

        results = await store.search_git_commits(repository_path="/repo1")
        assert len(results) == 1
        assert results[0]["commit_hash"] == "commit0"

    @pytest.mark.asyncio
    async def test_search_by_author(self, store):
        """Test filtering by author email."""
        commits = []
        for i, email in enumerate(["alice@example.com", "bob@example.com"]):
            commits.append({
                "commit_hash": f"commit{i}",
                "repository_path": "/repo",
                "author_name": f"Author {i}",
                "author_email": email,
                "author_date": datetime.now(UTC),
                "committer_name": "Committer",
                "committer_date": datetime.now(UTC),
                "message": f"Commit {i}",
                "message_embedding": [0.1] * 384,
                "branch_names": [],
                "tags": [],
                "parent_hashes": [],
                "stats": {},
            })

        await store.store_git_commits(commits)

        results = await store.search_git_commits(author="alice@example.com")
        assert len(results) == 1
        assert results[0]["author_email"] == "alice@example.com"

    @pytest.mark.asyncio
    async def test_search_by_date_range(self, store):
        """Test filtering by date range."""
        now = datetime.now(UTC)
        commits = []
        for i in range(5):
            commits.append({
                "commit_hash": f"commit{i}",
                "repository_path": "/repo",
                "author_name": "Author",
                "author_email": "author@example.com",
                "author_date": now - timedelta(days=i * 2),
                "committer_name": "Committer",
                "committer_date": now,
                "message": f"Commit {i}",
                "message_embedding": [0.1] * 384,
                "branch_names": [],
                "tags": [],
                "parent_hashes": [],
                "stats": {},
            })

        await store.store_git_commits(commits)

        # Search last 5 days
        since = now - timedelta(days=5)
        results = await store.search_git_commits(since=since)

        # Should get commits 0, 1, 2 (0, 2, 4 days ago)
        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_search_with_limit(self, store):
        """Test result limit."""
        commits = []
        for i in range(10):
            commits.append({
                "commit_hash": f"commit{i}",
                "repository_path": "/repo",
                "author_name": "Author",
                "author_email": "author@example.com",
                "author_date": datetime.now(UTC) - timedelta(days=i),
                "committer_name": "Committer",
                "committer_date": datetime.now(UTC),
                "message": f"Commit {i}",
                "message_embedding": [0.1] * 384,
                "branch_names": [],
                "tags": [],
                "parent_hashes": [],
                "stats": {},
            })

        await store.store_git_commits(commits)

        results = await store.search_git_commits(limit=5)
        assert len(results) == 5

    @pytest.mark.asyncio
    async def test_search_combined_filters(self, store):
        """Test combining multiple filters."""
        now = datetime.now(UTC)
        commits = []

        # Alice's commits
        for i in range(3):
            commits.append({
                "commit_hash": f"alice{i}",
                "repository_path": "/repo1",
                "author_name": "Alice",
                "author_email": "alice@example.com",
                "author_date": now - timedelta(days=i),
                "committer_name": "Alice",
                "committer_date": now,
                "message": f"Fix bug {i}",
                "message_embedding": [0.1] * 384,
                "branch_names": [],
                "tags": [],
                "parent_hashes": [],
                "stats": {},
            })

        # Bob's commits
        for i in range(3):
            commits.append({
                "commit_hash": f"bob{i}",
                "repository_path": "/repo2",
                "author_name": "Bob",
                "author_email": "bob@example.com",
                "author_date": now - timedelta(days=i),
                "committer_name": "Bob",
                "committer_date": now,
                "message": f"Add feature {i}",
                "message_embedding": [0.1] * 384,
                "branch_names": [],
                "tags": [],
                "parent_hashes": [],
                "stats": {},
            })

        await store.store_git_commits(commits)

        # Search for Alice's bug fixes
        results = await store.search_git_commits(
            query="bug",
            author="alice@example.com",
        )

        assert len(results) == 3
        assert all(r["author_email"] == "alice@example.com" for r in results)

    @pytest.mark.asyncio
    async def test_search_ordered_by_date(self, store):
        """Test results are ordered by date descending."""
        now = datetime.now(UTC)
        commits = []
        for i in range(5):
            commits.append({
                "commit_hash": f"commit{i}",
                "repository_path": "/repo",
                "author_name": "Author",
                "author_email": "author@example.com",
                "author_date": now - timedelta(days=i),
                "committer_name": "Committer",
                "committer_date": now,
                "message": f"Commit {i}",
                "message_embedding": [0.1] * 384,
                "branch_names": [],
                "tags": [],
                "parent_hashes": [],
                "stats": {},
            })

        await store.store_git_commits(commits)

        results = await store.search_git_commits()

        # Should be ordered newest first
        assert results[0]["commit_hash"] == "commit0"
        assert results[4]["commit_hash"] == "commit4"


class TestGetGitCommit:
    """Test getting individual commits."""

    @pytest.mark.asyncio
    async def test_get_existing_commit(self, store, sample_commit):
        """Test getting an existing commit."""
        await store.store_git_commits([sample_commit])

        result = await store.get_git_commit(sample_commit["commit_hash"])
        assert result is not None
        assert result["commit_hash"] == sample_commit["commit_hash"]
        assert result["message"] == sample_commit["message"]

    @pytest.mark.asyncio
    async def test_get_nonexistent_commit(self, store):
        """Test getting a commit that doesn't exist."""
        result = await store.get_git_commit("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_commit_deserializes_fields(self, store, sample_commit):
        """Test that JSON fields are deserialized correctly."""
        await store.store_git_commits([sample_commit])

        result = await store.get_git_commit(sample_commit["commit_hash"])
        assert isinstance(result["message_embedding"], list)
        assert isinstance(result["branch_names"], list)
        assert isinstance(result["tags"], list)
        assert isinstance(result["parent_hashes"], list)
        assert isinstance(result["stats"], dict)


class TestGetCommitsByFile:
    """Test getting commits by file path."""

    @pytest.mark.asyncio
    async def test_get_commits_by_file(self, store, sample_commit):
        """Test getting commits that modified a file."""
        await store.store_git_commits([sample_commit])

        file_changes = [
            {
                "id": f"{sample_commit['commit_hash']}:src/file.py",
                "commit_hash": sample_commit["commit_hash"],
                "file_path": "src/file.py",
                "change_type": "modified",
                "lines_added": 10,
                "lines_deleted": 5,
            },
        ]
        await store.store_git_file_changes(file_changes)

        results = await store.get_commits_by_file("src/file.py")
        assert len(results) == 1
        assert results[0]["commit_hash"] == sample_commit["commit_hash"]
        assert results[0]["change_type"] == "modified"
        assert results[0]["lines_added"] == 10

    @pytest.mark.asyncio
    async def test_get_commits_by_file_multiple(self, store):
        """Test getting multiple commits for a file."""
        commits = []
        for i in range(3):
            commits.append({
                "commit_hash": f"commit{i}",
                "repository_path": "/repo",
                "author_name": f"Author {i}",
                "author_email": f"author{i}@example.com",
                "author_date": datetime.now(UTC) - timedelta(days=i),
                "committer_name": "Committer",
                "committer_date": datetime.now(UTC),
                "message": f"Update file {i}",
                "message_embedding": [0.1] * 384,
                "branch_names": [],
                "tags": [],
                "parent_hashes": [],
                "stats": {},
            })

        await store.store_git_commits(commits)

        file_changes = []
        for i in range(3):
            file_changes.append({
                "id": f"commit{i}:file.py",
                "commit_hash": f"commit{i}",
                "file_path": "file.py",
                "change_type": "modified",
                "lines_added": i * 5,
                "lines_deleted": i * 2,
            })

        await store.store_git_file_changes(file_changes)

        results = await store.get_commits_by_file("file.py")
        assert len(results) == 3
        # Should be ordered by date descending
        assert results[0]["commit_hash"] == "commit0"

    @pytest.mark.asyncio
    async def test_get_commits_by_file_with_limit(self, store):
        """Test limiting results."""
        commits = []
        for i in range(10):
            commits.append({
                "commit_hash": f"commit{i}",
                "repository_path": "/repo",
                "author_name": "Author",
                "author_email": "author@example.com",
                "author_date": datetime.now(UTC) - timedelta(days=i),
                "committer_name": "Committer",
                "committer_date": datetime.now(UTC),
                "message": f"Update {i}",
                "message_embedding": [0.1] * 384,
                "branch_names": [],
                "tags": [],
                "parent_hashes": [],
                "stats": {},
            })

        await store.store_git_commits(commits)

        file_changes = []
        for i in range(10):
            file_changes.append({
                "id": f"commit{i}:file.py",
                "commit_hash": f"commit{i}",
                "file_path": "file.py",
                "change_type": "modified",
                "lines_added": 1,
                "lines_deleted": 0,
            })

        await store.store_git_file_changes(file_changes)

        results = await store.get_commits_by_file("file.py", limit=5)
        assert len(results) == 5

    @pytest.mark.asyncio
    async def test_get_commits_by_nonexistent_file(self, store):
        """Test getting commits for a file that doesn't exist."""
        results = await store.get_commits_by_file("nonexistent.py")
        assert len(results) == 0


class TestErrorHandling:
    """Test error handling in git storage."""

    @pytest.mark.asyncio
    async def test_store_commit_uninitialized_store(self, config, sample_commit):
        """Test storing commits with uninitialized store."""
        store = SQLiteMemoryStore(config)
        # Don't initialize

        with pytest.raises(Exception):  # StorageError
            await store.store_git_commits([sample_commit])

    @pytest.mark.asyncio
    async def test_search_commits_uninitialized_store(self, config):
        """Test searching commits with uninitialized store."""
        store = SQLiteMemoryStore(config)

        with pytest.raises(Exception):  # StorageError
            await store.search_git_commits()

    @pytest.mark.asyncio
    async def test_search_commits_with_invalid_query(self, store):
        """Test search handles invalid FTS queries gracefully."""
        # Store a commit first
        commit = {
            "commit_hash": "test",
            "repository_path": "/repo",
            "author_name": "Author",
            "author_email": "author@example.com",
            "author_date": datetime.now(UTC),
            "committer_name": "Committer",
            "committer_date": datetime.now(UTC),
            "message": "Test",
            "message_embedding": [0.1] * 384,
            "branch_names": [],
            "tags": [],
            "parent_hashes": [],
            "stats": {},
        }
        await store.store_git_commits([commit])

        # Invalid FTS query syntax should return empty list (not crash)
        results = await store.search_git_commits(query="\"")
        # Implementation returns [] on error
        assert isinstance(results, list)
