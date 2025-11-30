"""Tests for multi-repository indexer."""

import pytest
import pytest_asyncio
from datetime import datetime, timedelta, UTC
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from src.memory.multi_repository_indexer import (
    MultiRepositoryIndexer,
    RepositoryIndexResult,
    BatchIndexResult,
)
from src.memory.repository_registry import (
    Repository,
    RepositoryRegistry,
    RepositoryType,
    RepositoryStatus,
)
from src.memory.workspace_manager import Workspace, WorkspaceManager
from src.memory.incremental_indexer import IncrementalIndexer
from tests.conftest import mock_embedding


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def temp_registry_file(tmp_path):
    """Create temporary registry storage file."""
    return tmp_path / "repositories.json"


@pytest.fixture
def temp_workspace_file(tmp_path):
    """Create temporary workspace storage file."""
    return tmp_path / "workspaces.json"


@pytest.fixture
def temp_repo_dirs(tmp_path):
    """Create temporary repository directories."""
    repo1 = tmp_path / "repo1"
    repo2 = tmp_path / "repo2"
    repo3 = tmp_path / "repo3"

    # Create directories with some Python files
    for repo_dir in [repo1, repo2, repo3]:
        repo_dir.mkdir()
        (repo_dir / "main.py").write_text("def hello(): pass")
        (repo_dir / "utils.py").write_text("def util(): pass")

    return {"repo1": repo1, "repo2": repo2, "repo3": repo3}


@pytest_asyncio.fixture
async def repository_registry(temp_registry_file, temp_repo_dirs):
    """Create repository registry with test repositories."""
    registry = RepositoryRegistry(str(temp_registry_file))

    # Register test repositories
    await registry.register_repository(
        path=str(temp_repo_dirs["repo1"]),
        name="Repo 1",
        repo_type=RepositoryType.STANDALONE,
    )
    await registry.register_repository(
        path=str(temp_repo_dirs["repo2"]),
        name="Repo 2",
        repo_type=RepositoryType.STANDALONE,
    )
    await registry.register_repository(
        path=str(temp_repo_dirs["repo3"]),
        name="Repo 3",
        repo_type=RepositoryType.STANDALONE,
    )

    return registry


@pytest_asyncio.fixture
async def workspace_manager(temp_workspace_file, repository_registry):
    """Create workspace manager with test workspace."""
    manager = WorkspaceManager(str(temp_workspace_file), repository_registry)

    # Get repository IDs
    repos = await repository_registry.list_repositories()
    repo_ids = [repo.id for repo in repos]

    # Create test workspace
    await manager.create_workspace(
        workspace_id="ws-1",
        name="Test Workspace",
        repository_ids=repo_ids[:2],  # First 2 repos
    )

    return manager


@pytest_asyncio.fixture
async def mock_store():
    """Create mock vector store."""
    store = AsyncMock()
    store.initialize = AsyncMock()
    store.close = AsyncMock()
    return store


@pytest_asyncio.fixture
async def mock_embedding_generator():
    """Create mock embedding generator."""
    generator = AsyncMock()
    generator.initialize = AsyncMock()
    generator.close = AsyncMock()
    generator.batch_generate = AsyncMock(return_value=[mock_embedding(value=0.1)])
    return generator


@pytest_asyncio.fixture
async def multi_repo_indexer(
    repository_registry,
    workspace_manager,
    mock_store,
    mock_embedding_generator,
):
    """Create multi-repository indexer."""
    indexer = MultiRepositoryIndexer(
        repository_registry=repository_registry,
        workspace_manager=workspace_manager,
        store=mock_store,
        embedding_generator=mock_embedding_generator,
        max_concurrent_repos=2,
    )
    await indexer.initialize()
    yield indexer
    await indexer.close()


# ============================================================================
# Result Model Tests
# ============================================================================

class TestRepositoryIndexResult:
    """Test RepositoryIndexResult dataclass."""

    def test_result_creation_success(self):
        """Test creating successful result."""
        result = RepositoryIndexResult(
            repository_id="repo-1",
            success=True,
            files_indexed=10,
            units_indexed=25,
            duration_seconds=5.5,
        )

        assert result.repository_id == "repo-1"
        assert result.success is True
        assert result.files_indexed == 10
        assert result.units_indexed == 25
        assert result.duration_seconds == 5.5
        assert result.errors == []
        assert result.error_message is None

    def test_result_creation_failure(self):
        """Test creating failure result."""
        result = RepositoryIndexResult(
            repository_id="repo-1",
            success=False,
            error_message="Failed to index",
            errors=["Error 1", "Error 2"],
            duration_seconds=1.0,
        )

        assert result.repository_id == "repo-1"
        assert result.success is False
        assert result.error_message == "Failed to index"
        assert len(result.errors) == 2
        assert result.files_indexed == 0
        assert result.units_indexed == 0


class TestBatchIndexResult:
    """Test BatchIndexResult dataclass."""

    def test_batch_result_creation(self):
        """Test creating batch result."""
        repo_results = [
            RepositoryIndexResult("repo-1", True, 10, 25, duration_seconds=5.0),
            RepositoryIndexResult("repo-2", True, 15, 30, duration_seconds=6.0),
            RepositoryIndexResult("repo-3", False, error_message="Failed"),
        ]

        result = BatchIndexResult(
            total_repositories=3,
            successful=2,
            failed=1,
            repository_results=repo_results,
            total_files=25,
            total_units=55,
            total_duration=12.0,
        )

        assert result.total_repositories == 3
        assert result.successful == 2
        assert result.failed == 1
        assert len(result.repository_results) == 3
        assert result.total_files == 25
        assert result.total_units == 55
        assert result.total_duration == 12.0

    def test_batch_result_to_dict(self):
        """Test converting batch result to dictionary."""
        repo_results = [
            RepositoryIndexResult("repo-1", True, 10, 25),
            RepositoryIndexResult("repo-2", False, error_message="Failed"),
        ]

        result = BatchIndexResult(
            total_repositories=2,
            successful=1,
            failed=1,
            repository_results=repo_results,
            total_files=10,
            total_units=25,
        )

        data = result.to_dict()

        assert data["total_repositories"] == 2
        assert data["successful"] == 1
        assert data["failed"] == 1
        assert len(data["repository_results"]) == 2
        assert data["repository_results"][0]["repository_id"] == "repo-1"
        assert data["repository_results"][0]["success"] is True
        assert data["repository_results"][1]["success"] is False


# ============================================================================
# Initialization Tests
# ============================================================================

class TestMultiRepositoryIndexerInit:
    """Test multi-repository indexer initialization."""

    @pytest.mark.asyncio
    async def test_initialization(
        self, repository_registry, workspace_manager, mock_store, mock_embedding_generator
    ):
        """Test initializing multi-repository indexer."""
        indexer = MultiRepositoryIndexer(
            repository_registry=repository_registry,
            workspace_manager=workspace_manager,
            store=mock_store,
            embedding_generator=mock_embedding_generator,
        )

        await indexer.initialize()

        # Should initialize store and embedding generator
        mock_store.initialize.assert_called_once()
        mock_embedding_generator.initialize.assert_called_once()

        await indexer.close()

    @pytest.mark.asyncio
    async def test_initialization_creates_defaults(self, repository_registry):
        """Test initialization creates default store and generator."""
        indexer = MultiRepositoryIndexer(
            repository_registry=repository_registry,
            max_concurrent_repos=3,
        )

        # Should create defaults
        assert indexer.store is None
        assert indexer.embedding_generator is None
        assert indexer.max_concurrent_repos == 3

        # Note: We don't call initialize() here because it would try to
        # connect to real Qdrant, which may not be running in tests

    @pytest.mark.asyncio
    async def test_close_cleans_up(
        self, repository_registry, workspace_manager, mock_store, mock_embedding_generator
    ):
        """Test close cleans up resources."""
        # Create indexer without using fixture (to avoid double-close)
        indexer = MultiRepositoryIndexer(
            repository_registry=repository_registry,
            workspace_manager=workspace_manager,
            store=mock_store,
            embedding_generator=mock_embedding_generator,
        )
        await indexer.initialize()

        # Add some indexers to cache
        repos = await repository_registry.list_repositories()
        for repo in repos[:2]:
            indexer._get_indexer(repo)

        assert len(indexer._indexer_cache) == 2

        await indexer.close()

        # Cache should be cleared
        assert len(indexer._indexer_cache) == 0

        # Should close store and generator (may be called by child indexers too)
        assert mock_store.close.called
        assert mock_embedding_generator.close.called


# ============================================================================
# Single Repository Indexing Tests
# ============================================================================

class TestSingleRepositoryIndexing:
    """Test indexing single repositories."""

    @pytest.mark.asyncio
    async def test_index_repository_success(self, multi_repo_indexer):
        """Test successfully indexing a repository."""
        repos = await multi_repo_indexer.repository_registry.list_repositories()
        repo_id = repos[0].id

        # Mock the indexer
        with patch.object(IncrementalIndexer, 'index_directory') as mock_index:
            mock_index.return_value = {
                "total_files": 10,
                "total_units": 25,
                "parse_time_ms": 500.0,
            }

            result = await multi_repo_indexer.index_repository(repo_id)

        assert result.success is True
        assert result.repository_id == repo_id
        assert result.files_indexed == 10
        assert result.units_indexed == 25
        assert result.duration_seconds > 0

        # Repository should be updated
        repo = await multi_repo_indexer.repository_registry.get_repository(repo_id)
        assert repo.status == RepositoryStatus.INDEXED
        assert repo.file_count == 10
        assert repo.unit_count == 25
        assert repo.indexed_at is not None

    @pytest.mark.asyncio
    async def test_index_repository_not_found(self, multi_repo_indexer):
        """Test indexing nonexistent repository fails."""
        with pytest.raises(ValueError, match="not found"):
            await multi_repo_indexer.index_repository("nonexistent")

    @pytest.mark.asyncio
    async def test_index_repository_path_not_exists(
        self, multi_repo_indexer, repository_registry
    ):
        """Test indexing repository with invalid path."""
        # Register repository with invalid path
        repo_id = await repository_registry.register_repository(
            path="/nonexistent/path",
            name="Bad Repo",
        )

        result = await multi_repo_indexer.index_repository(repo_id)

        assert result.success is False
        assert "does not exist" in result.error_message
        assert len(result.errors) > 0

        # Repository should have ERROR status
        repo = await repository_registry.get_repository(repo_id)
        assert repo.status == RepositoryStatus.ERROR

    @pytest.mark.asyncio
    async def test_index_repository_indexing_error(self, multi_repo_indexer):
        """Test handling indexing errors."""
        repos = await multi_repo_indexer.repository_registry.list_repositories()
        repo_id = repos[0].id

        # Mock indexer to raise error
        with patch.object(IncrementalIndexer, 'index_directory') as mock_index:
            mock_index.side_effect = Exception("Indexing failed")

            result = await multi_repo_indexer.index_repository(repo_id)

        assert result.success is False
        assert "Indexing failed" in result.error_message
        assert len(result.errors) > 0

        # Repository should have ERROR status
        repo = await multi_repo_indexer.repository_registry.get_repository(repo_id)
        assert repo.status == RepositoryStatus.ERROR

    @pytest.mark.asyncio
    async def test_index_repository_sets_indexing_status(self, multi_repo_indexer):
        """Test that INDEXING status is set during indexing."""
        repos = await multi_repo_indexer.repository_registry.list_repositories()
        repo_id = repos[0].id

        # Track status changes
        status_changes = []

        original_update = multi_repo_indexer.repository_registry.update_repository

        async def track_updates(rid, updates):
            if "status" in updates:
                status_changes.append(updates["status"])
            await original_update(rid, updates)

        multi_repo_indexer.repository_registry.update_repository = track_updates

        with patch.object(IncrementalIndexer, 'index_directory') as mock_index:
            mock_index.return_value = {"total_files": 5, "total_units": 10}
            await multi_repo_indexer.index_repository(repo_id)

        # Should transition: INDEXING -> INDEXED
        assert RepositoryStatus.INDEXING in status_changes
        assert RepositoryStatus.INDEXED in status_changes

    @pytest.mark.asyncio
    async def test_index_repository_with_progress_callback(self, multi_repo_indexer):
        """Test indexing with progress callback."""
        repos = await multi_repo_indexer.repository_registry.list_repositories()
        repo_id = repos[0].id

        progress_updates = []

        def progress_callback(data):
            progress_updates.append(data)

        with patch.object(IncrementalIndexer, 'index_directory') as mock_index:
            mock_index.return_value = {"total_files": 5, "total_units": 10}

            await multi_repo_indexer.index_repository(
                repo_id,
                progress_callback=progress_callback
            )

        # Callback should have been passed to indexer
        call_kwargs = mock_index.call_args.kwargs
        assert call_kwargs.get("progress_callback") == progress_callback


# ============================================================================
# Batch Indexing Tests
# ============================================================================

class TestBatchIndexing:
    """Test batch indexing operations."""

    @pytest.mark.asyncio
    async def test_index_repositories_multiple(self, multi_repo_indexer):
        """Test indexing multiple repositories."""
        repos = await multi_repo_indexer.repository_registry.list_repositories()
        repo_ids = [repo.id for repo in repos[:2]]

        with patch.object(IncrementalIndexer, 'index_directory') as mock_index:
            mock_index.return_value = {"total_files": 5, "total_units": 10}

            result = await multi_repo_indexer.index_repositories(repo_ids)

        assert result.total_repositories == 2
        assert result.successful == 2
        assert result.failed == 0
        assert result.total_files == 10  # 5 * 2
        assert result.total_units == 20  # 10 * 2
        assert len(result.repository_results) == 2

    @pytest.mark.asyncio
    async def test_index_repositories_with_failures(self, multi_repo_indexer):
        """Test batch indexing with some failures."""
        repos = await multi_repo_indexer.repository_registry.list_repositories()
        repo_ids = [repo.id for repo in repos]

        call_count = [0]

        def mock_index_side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 2:  # Second call fails
                raise Exception("Indexing failed")
            return {"total_files": 5, "total_units": 10}

        with patch.object(IncrementalIndexer, 'index_directory') as mock_index:
            mock_index.side_effect = mock_index_side_effect

            result = await multi_repo_indexer.index_repositories(repo_ids)

        assert result.total_repositories == 3
        assert result.successful == 2
        assert result.failed == 1
        assert result.total_files == 10  # Only successful ones
        assert result.total_units == 20

    @pytest.mark.asyncio
    async def test_index_repositories_respects_concurrency_limit(
        self, multi_repo_indexer
    ):
        """Test that batch indexing respects concurrency limit."""
        repos = await multi_repo_indexer.repository_registry.list_repositories()
        repo_ids = [repo.id for repo in repos]

        # Track concurrent calls
        concurrent_calls = [0]
        max_concurrent = [0]

        async def mock_index(*args, **kwargs):
            concurrent_calls[0] += 1
            max_concurrent[0] = max(max_concurrent[0], concurrent_calls[0])

            # Simulate some work
            import asyncio
            await asyncio.sleep(0.01)

            concurrent_calls[0] -= 1
            return {"total_files": 5, "total_units": 10}

        with patch.object(IncrementalIndexer, 'index_directory') as mock_index_patch:
            mock_index_patch.side_effect = mock_index

            await multi_repo_indexer.index_repositories(repo_ids)

        # Should not exceed max_concurrent_repos (which is 2 in fixture)
        assert max_concurrent[0] <= multi_repo_indexer.max_concurrent_repos

    @pytest.mark.asyncio
    async def test_index_repositories_empty_list(self, multi_repo_indexer):
        """Test batch indexing with empty list."""
        result = await multi_repo_indexer.index_repositories([])

        assert result.total_repositories == 0
        assert result.successful == 0
        assert result.failed == 0
        assert result.repository_results == []


# ============================================================================
# Workspace Indexing Tests
# ============================================================================

class TestWorkspaceIndexing:
    """Test workspace-based indexing."""

    @pytest.mark.asyncio
    async def test_index_workspace(self, multi_repo_indexer):
        """Test indexing all repositories in a workspace."""
        with patch.object(IncrementalIndexer, 'index_directory') as mock_index:
            mock_index.return_value = {"total_files": 5, "total_units": 10}

            result = await multi_repo_indexer.index_workspace("ws-1")

        # Workspace has 2 repositories
        assert result.total_repositories == 2
        assert result.successful == 2
        assert result.failed == 0

    @pytest.mark.asyncio
    async def test_index_workspace_not_found(self, multi_repo_indexer):
        """Test indexing nonexistent workspace fails."""
        with pytest.raises(ValueError, match="not found"):
            await multi_repo_indexer.index_workspace("nonexistent")

    @pytest.mark.asyncio
    async def test_index_workspace_no_manager(
        self, repository_registry, mock_store, mock_embedding_generator
    ):
        """Test indexing workspace without workspace manager fails."""
        indexer = MultiRepositoryIndexer(
            repository_registry=repository_registry,
            workspace_manager=None,  # No workspace manager
            store=mock_store,
            embedding_generator=mock_embedding_generator,
        )
        await indexer.initialize()

        with pytest.raises(ValueError, match="not configured"):
            await indexer.index_workspace("ws-1")

        await indexer.close()


# ============================================================================
# Stale Repository Re-indexing Tests
# ============================================================================

class TestStaleRepositoryReindexing:
    """Test re-indexing stale repositories."""

    @pytest.mark.asyncio
    async def test_reindex_stale_repositories_by_status(
        self, multi_repo_indexer, repository_registry
    ):
        """Test re-indexing repositories with STALE status."""
        repos = await repository_registry.list_repositories()

        # Mark first repo as STALE
        await repository_registry.update_repository(
            repos[0].id,
            {"status": RepositoryStatus.STALE}
        )

        # Mark second repo as ERROR
        await repository_registry.update_repository(
            repos[1].id,
            {"status": RepositoryStatus.ERROR}
        )

        with patch.object(IncrementalIndexer, 'index_directory') as mock_index:
            mock_index.return_value = {"total_files": 5, "total_units": 10}

            result = await multi_repo_indexer.reindex_stale_repositories()

        # Should re-index both STALE and ERROR repos
        assert result.total_repositories == 2
        assert result.successful == 2

    @pytest.mark.asyncio
    async def test_reindex_stale_repositories_by_age(
        self, multi_repo_indexer, repository_registry
    ):
        """Test re-indexing repositories based on age."""
        repos = await repository_registry.list_repositories()

        # Mark first repo as indexed 10 days ago
        # Note: We have to modify the object directly because update_repository
        # always sets last_updated to now()
        old_date = datetime.now(UTC) - timedelta(days=10)
        repos[0].status = RepositoryStatus.INDEXED
        repos[0].last_updated = old_date
        repository_registry.repositories[repos[0].id] = repos[0]
        repository_registry._save()

        # Mark second repo as recently indexed
        repos[1].status = RepositoryStatus.INDEXED
        repos[1].last_updated = datetime.now(UTC)
        repository_registry.repositories[repos[1].id] = repos[1]
        repository_registry._save()

        with patch.object(IncrementalIndexer, 'index_directory') as mock_index:
            mock_index.return_value = {"total_files": 5, "total_units": 10}

            # Re-index repos older than 7 days
            result = await multi_repo_indexer.reindex_stale_repositories(
                max_age_days=7
            )

        # Should only re-index old repo
        assert result.total_repositories == 1
        assert result.successful == 1

    @pytest.mark.asyncio
    async def test_reindex_stale_repositories_none_stale(self, multi_repo_indexer):
        """Test re-indexing when no repositories are stale."""
        # All repos are NOT_INDEXED (default status)
        result = await multi_repo_indexer.reindex_stale_repositories()

        # Should not re-index any
        assert result.total_repositories == 0
        assert result.successful == 0


# ============================================================================
# Indexer Caching Tests
# ============================================================================

class TestIndexerCaching:
    """Test IncrementalIndexer caching."""

    @pytest.mark.asyncio
    async def test_get_indexer_creates_and_caches(self, multi_repo_indexer):
        """Test that _get_indexer creates and caches indexers."""
        repos = await multi_repo_indexer.repository_registry.list_repositories()
        repo = repos[0]

        assert len(multi_repo_indexer._indexer_cache) == 0

        indexer1 = multi_repo_indexer._get_indexer(repo)

        assert len(multi_repo_indexer._indexer_cache) == 1
        assert repo.id in multi_repo_indexer._indexer_cache

        # Getting again should return same instance
        indexer2 = multi_repo_indexer._get_indexer(repo)

        assert indexer1 is indexer2
        assert len(multi_repo_indexer._indexer_cache) == 1

    @pytest.mark.asyncio
    async def test_get_indexer_uses_repo_id_as_project_name(
        self, multi_repo_indexer
    ):
        """Test that indexer uses repository ID as project name."""
        repos = await multi_repo_indexer.repository_registry.list_repositories()
        repo = repos[0]

        indexer = multi_repo_indexer._get_indexer(repo)

        # Project name should be repository ID
        assert indexer.project_name == repo.id

    @pytest.mark.asyncio
    async def test_close_clears_indexer_cache(self, multi_repo_indexer):
        """Test that close() clears indexer cache."""
        repos = await multi_repo_indexer.repository_registry.list_repositories()

        # Create some indexers
        for repo in repos:
            multi_repo_indexer._get_indexer(repo)

        assert len(multi_repo_indexer._indexer_cache) == len(repos)

        await multi_repo_indexer.close()

        assert len(multi_repo_indexer._indexer_cache) == 0


# ============================================================================
# Status Tracking Tests
# ============================================================================

class TestIndexingStatus:
    """Test indexing status tracking."""

    @pytest.mark.asyncio
    async def test_get_indexing_status(self, multi_repo_indexer, repository_registry):
        """Test getting overall indexing status."""
        repos = await repository_registry.list_repositories()

        # Set different statuses
        await repository_registry.update_repository(
            repos[0].id,
            {
                "status": RepositoryStatus.INDEXED,
                "file_count": 10,
                "unit_count": 25,
            }
        )
        await repository_registry.update_repository(
            repos[1].id,
            {
                "status": RepositoryStatus.STALE,
                "file_count": 5,
                "unit_count": 12,
            }
        )
        await repository_registry.update_repository(
            repos[2].id,
            {"status": RepositoryStatus.ERROR}
        )

        status = await multi_repo_indexer.get_indexing_status()

        assert status["total_repositories"] == 3
        assert status["status_counts"][RepositoryStatus.INDEXED.value] == 1
        assert status["status_counts"][RepositoryStatus.STALE.value] == 1
        assert status["status_counts"][RepositoryStatus.ERROR.value] == 1
        assert status["total_files_indexed"] == 15  # 10 + 5 + 0
        assert status["total_units_indexed"] == 37  # 25 + 12 + 0

    @pytest.mark.asyncio
    async def test_get_indexing_status_includes_cache_size(
        self, multi_repo_indexer
    ):
        """Test that status includes indexer cache size."""
        repos = await multi_repo_indexer.repository_registry.list_repositories()

        # Create some cached indexers
        multi_repo_indexer._get_indexer(repos[0])
        multi_repo_indexer._get_indexer(repos[1])

        status = await multi_repo_indexer.get_indexing_status()

        assert status["indexer_cache_size"] == 2

    @pytest.mark.asyncio
    async def test_get_indexing_status_empty(
        self, mock_store, mock_embedding_generator
    ):
        """Test getting status with no repositories."""
        # Create registry with no repositories
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            registry_path = f.name

        registry = RepositoryRegistry(registry_path)
        indexer = MultiRepositoryIndexer(
            repository_registry=registry,
            store=mock_store,
            embedding_generator=mock_embedding_generator,
        )
        await indexer.initialize()

        status = await indexer.get_indexing_status()

        assert status["total_repositories"] == 0
        assert status["total_files_indexed"] == 0
        assert status["total_units_indexed"] == 0
        assert all(count == 0 for count in status["status_counts"].values())

        await indexer.close()
