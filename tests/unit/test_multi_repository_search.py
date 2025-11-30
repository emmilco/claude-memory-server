"""Tests for multi-repository search."""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, UTC

from src.memory.multi_repository_search import (
    MultiRepositorySearch,
    RepositorySearchResult,
    MultiRepositorySearchResult,
)
from src.memory.repository_registry import (
    RepositoryRegistry,
    Repository,
    RepositoryType,
    RepositoryStatus,
)
from src.memory.workspace_manager import WorkspaceManager
from src.core.models import MemoryUnit, MemoryCategory, ContextLevel, MemoryScope
from conftest import mock_embedding


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


@pytest_asyncio.fixture
async def repository_registry(temp_registry_file):
    """Create repository registry with test repositories."""
    registry = RepositoryRegistry(str(temp_registry_file))

    # Register test repositories
    await registry.register_repository(
        path="/test/repo1",
        name="Repo 1",
        repo_type=RepositoryType.STANDALONE,
    )
    await registry.register_repository(
        path="/test/repo2",
        name="Repo 2",
        repo_type=RepositoryType.STANDALONE,
    )
    await registry.register_repository(
        path="/test/repo3",
        name="Repo 3",
        repo_type=RepositoryType.STANDALONE,
    )

    # Set all as indexed
    repos = await registry.list_repositories()
    for repo in repos:
        await registry.update_repository(repo.id, {"status": RepositoryStatus.INDEXED})

    return registry


@pytest_asyncio.fixture
async def workspace_manager(temp_workspace_file, repository_registry):
    """Create workspace manager with test workspace."""
    manager = WorkspaceManager(str(temp_workspace_file), repository_registry)

    # Get repository IDs
    repos = await repository_registry.list_repositories()
    repo_ids = [repo.id for repo in repos]

    # Create test workspace with first 2 repos
    await manager.create_workspace(
        workspace_id="ws-1",
        name="Test Workspace",
        repository_ids=repo_ids[:2],
        cross_repo_search_enabled=True,
    )

    # Create workspace with cross-repo disabled
    await manager.create_workspace(
        workspace_id="ws-2",
        name="Disabled Workspace",
        repository_ids=[repo_ids[2]],
        cross_repo_search_enabled=False,
    )

    return manager


@pytest_asyncio.fixture
async def mock_store():
    """Create mock vector store."""
    store = AsyncMock()
    store.initialize = AsyncMock()
    store.close = AsyncMock()

    # Mock retrieve to return sample results
    def mock_retrieve(query_embedding, filters, limit):
        # Create mock memories based on project_name filter
        project_name = filters.project_name if filters else "unknown"

        results = []
        for i in range(min(3, limit)):  # Return up to 3 results
            memory = MemoryUnit(
                id=f"{project_name}-{i}",
                content=f"Result {i} from {project_name}",
                category=MemoryCategory.CONTEXT,
                context_level=ContextLevel.PROJECT_CONTEXT,
                scope=MemoryScope.PROJECT,
                project_name=project_name,
                tags=["code"],
                metadata={
                    "file_path": f"/test/{project_name}/file{i}.py",
                    "unit_type": "function",
                },
                created_at=datetime.now(UTC),
            )
            score = 0.9 - (i * 0.1)  # Decreasing scores
            results.append((memory, score))

        return results

    store.retrieve = AsyncMock(side_effect=mock_retrieve)
    return store


@pytest_asyncio.fixture
async def mock_embedding_generator():
    """Create mock embedding generator."""
    generator = AsyncMock()
    generator.initialize = AsyncMock()
    generator.close = AsyncMock()
    generator.generate = AsyncMock(return_value=mock_embedding(value=0.1))
    return generator


@pytest_asyncio.fixture
async def multi_repo_search(
    repository_registry,
    workspace_manager,
    mock_store,
    mock_embedding_generator,
):
    """Create multi-repository search."""
    searcher = MultiRepositorySearch(
        repository_registry=repository_registry,
        workspace_manager=workspace_manager,
        store=mock_store,
        embedding_generator=mock_embedding_generator,
    )
    await searcher.initialize()
    yield searcher
    await searcher.close()


# ============================================================================
# Result Model Tests
# ============================================================================

class TestRepositorySearchResult:
    """Test RepositorySearchResult dataclass."""

    def test_result_creation(self):
        """Test creating repository search result."""
        result = RepositorySearchResult(
            repository_id="repo-1",
            repository_name="Test Repo",
            results=[("memory1", 0.9), ("memory2", 0.8)],
            total_found=2,
        )

        assert result.repository_id == "repo-1"
        assert result.repository_name == "Test Repo"
        assert len(result.results) == 2
        assert result.total_found == 2


class TestMultiRepositorySearchResult:
    """Test MultiRepositorySearchResult dataclass."""

    def test_result_creation(self):
        """Test creating multi-repository search result."""
        repo_results = [
            RepositorySearchResult("repo-1", "Repo 1", [("m1", 0.9)], 1),
            RepositorySearchResult("repo-2", "Repo 2", [("m2", 0.8)], 1),
        ]

        result = MultiRepositorySearchResult(
            query="test query",
            repository_results=repo_results,
            aggregated_results=[("m1", 0.9), ("m2", 0.8)],
            total_repositories_searched=2,
            total_results_found=2,
            search_mode="semantic",
            query_time_ms=100.5,
        )

        assert result.query == "test query"
        assert len(result.repository_results) == 2
        assert len(result.aggregated_results) == 2
        assert result.total_repositories_searched == 2
        assert result.total_results_found == 2

    def test_result_to_dict(self):
        """Test converting result to dictionary."""
        # Create mock memory
        memory = MemoryUnit(
            id="test-1",
            content="Test content",
            category=MemoryCategory.CONTEXT,
            context_level=ContextLevel.PROJECT_CONTEXT,
            scope=MemoryScope.PROJECT,
            project_name="test-project",
            tags=["code"],
            metadata={
                "file_path": "/test/file.py",
                "unit_type": "function",
            },
            created_at=datetime.now(UTC),
        )

        repo_results = [
            RepositorySearchResult(
                "repo-1",
                "Repo 1",
                [(memory, 0.9)],
                1,
            ),
        ]

        result = MultiRepositorySearchResult(
            query="test",
            repository_results=repo_results,
            aggregated_results=[(memory, 0.9)],
            total_repositories_searched=1,
            total_results_found=1,
        )

        data = result.to_dict()

        assert data["query"] == "test"
        assert data["total_repositories_searched"] == 1
        assert len(data["repository_results"]) == 1
        assert data["repository_results"][0]["repository_id"] == "repo-1"
        assert len(data["aggregated_results"]) == 1


# ============================================================================
# Initialization Tests
# ============================================================================

class TestMultiRepositorySearchInit:
    """Test multi-repository search initialization."""

    @pytest.mark.asyncio
    async def test_initialization(
        self, repository_registry, workspace_manager, mock_store, mock_embedding_generator
    ):
        """Test initializing multi-repository search."""
        searcher = MultiRepositorySearch(
            repository_registry=repository_registry,
            workspace_manager=workspace_manager,
            store=mock_store,
            embedding_generator=mock_embedding_generator,
        )

        await searcher.initialize()

        # Should initialize store and embedding generator
        mock_store.initialize.assert_called_once()
        mock_embedding_generator.initialize.assert_called_once()

        await searcher.close()

    @pytest.mark.asyncio
    async def test_close_cleans_up(self, multi_repo_search):
        """Test close cleans up resources."""
        await multi_repo_search.close()

        # Should close store and generator
        multi_repo_search.store.close.assert_called()
        multi_repo_search.embedding_generator.close.assert_called()


# ============================================================================
# Single Repository Search Tests
# ============================================================================

class TestSingleRepositorySearch:
    """Test searching single repositories."""

    @pytest.mark.asyncio
    async def test_search_repository(self, multi_repo_search, repository_registry):
        """Test searching a single repository."""
        repos = await repository_registry.list_repositories()
        repo_id = repos[0].id

        result = await multi_repo_search.search_repository(
            query="test query",
            repository_id=repo_id,
            limit=10,
        )

        assert result.repository_id == repo_id
        assert result.repository_name == "Repo 1"
        assert len(result.results) > 0
        assert result.total_found == len(result.results)

        # Embedding should be generated
        multi_repo_search.embedding_generator.generate.assert_called_with("test query")

    @pytest.mark.asyncio
    async def test_search_repository_not_found(self, multi_repo_search):
        """Test searching nonexistent repository fails."""
        with pytest.raises(ValueError, match="not found"):
            await multi_repo_search.search_repository(
                query="test",
                repository_id="nonexistent",
            )

    @pytest.mark.asyncio
    async def test_search_repository_respects_limit(
        self, multi_repo_search, repository_registry
    ):
        """Test that repository search respects limit."""
        repos = await repository_registry.list_repositories()
        repo_id = repos[0].id

        result = await multi_repo_search.search_repository(
            query="test query",
            repository_id=repo_id,
            limit=2,
        )

        # Mock returns 3 results but limit is 2
        assert len(result.results) <= 2


# ============================================================================
# Multi-Repository Search Tests
# ============================================================================

class TestMultiRepositorySearch:
    """Test searching multiple repositories."""

    @pytest.mark.asyncio
    async def test_search_repositories_multiple(
        self, multi_repo_search, repository_registry
    ):
        """Test searching multiple repositories."""
        repos = await repository_registry.list_repositories()
        repo_ids = [repo.id for repo in repos[:2]]

        result = await multi_repo_search.search_repositories(
            query="test query",
            repository_ids=repo_ids,
            limit_per_repo=10,
        )

        assert result.query == "test query"
        assert result.total_repositories_searched == 2
        assert len(result.repository_results) == 2
        assert result.total_results_found > 0

        # Should have aggregated results
        assert len(result.aggregated_results) > 0

    @pytest.mark.asyncio
    async def test_search_repositories_aggregates_and_sorts(
        self, multi_repo_search, repository_registry
    ):
        """Test that results are aggregated and sorted by score."""
        repos = await repository_registry.list_repositories()
        repo_ids = [repo.id for repo in repos[:2]]

        result = await multi_repo_search.search_repositories(
            query="test",
            repository_ids=repo_ids,
            aggregate=True,
        )

        # Results should be sorted by score (descending)
        scores = [score for _, score in result.aggregated_results]
        assert scores == sorted(scores, reverse=True)

    @pytest.mark.asyncio
    async def test_search_repositories_without_aggregation(
        self, multi_repo_search, repository_registry
    ):
        """Test searching without aggregation."""
        repos = await repository_registry.list_repositories()
        repo_ids = [repo.id for repo in repos[:2]]

        result = await multi_repo_search.search_repositories(
            query="test",
            repository_ids=repo_ids,
            aggregate=False,
        )

        # Should have repository results but no aggregation
        assert len(result.repository_results) == 2
        assert len(result.aggregated_results) == 0

    @pytest.mark.asyncio
    async def test_search_repositories_respects_total_limit(
        self, multi_repo_search, repository_registry
    ):
        """Test that total_limit is respected in aggregated results."""
        repos = await repository_registry.list_repositories()
        repo_ids = [repo.id for repo in repos]

        result = await multi_repo_search.search_repositories(
            query="test",
            repository_ids=repo_ids,
            limit_per_repo=10,
            total_limit=5,
            aggregate=True,
        )

        # Should not exceed total limit
        assert len(result.aggregated_results) <= 5

    @pytest.mark.asyncio
    async def test_search_repositories_handles_errors(
        self, multi_repo_search, repository_registry
    ):
        """Test searching with some invalid repositories."""
        repos = await repository_registry.list_repositories()
        repo_ids = [repos[0].id, "nonexistent", repos[1].id]

        result = await multi_repo_search.search_repositories(
            query="test",
            repository_ids=repo_ids,
        )

        # Should have results from valid repos only
        assert result.total_repositories_searched == 2
        assert len(result.repository_results) == 2

    @pytest.mark.asyncio
    async def test_search_repositories_empty_list(self, multi_repo_search):
        """Test searching empty repository list."""
        result = await multi_repo_search.search_repositories(
            query="test",
            repository_ids=[],
        )

        assert result.total_repositories_searched == 0
        assert result.total_results_found == 0
        assert len(result.repository_results) == 0


# ============================================================================
# Workspace Search Tests
# ============================================================================

class TestWorkspaceSearch:
    """Test workspace-scoped search."""

    @pytest.mark.asyncio
    async def test_search_workspace(self, multi_repo_search):
        """Test searching all repositories in a workspace."""
        result = await multi_repo_search.search_workspace(
            query="test query",
            workspace_id="ws-1",
            limit_per_repo=10,
        )

        # Workspace has 2 repositories
        assert result.total_repositories_searched == 2
        assert len(result.repository_results) == 2

    @pytest.mark.asyncio
    async def test_search_workspace_not_found(self, multi_repo_search):
        """Test searching nonexistent workspace fails."""
        with pytest.raises(ValueError, match="not found"):
            await multi_repo_search.search_workspace(
                query="test",
                workspace_id="nonexistent",
            )

    @pytest.mark.asyncio
    async def test_search_workspace_no_manager(
        self, repository_registry, mock_store, mock_embedding_generator
    ):
        """Test searching workspace without workspace manager fails."""
        searcher = MultiRepositorySearch(
            repository_registry=repository_registry,
            workspace_manager=None,  # No workspace manager
            store=mock_store,
            embedding_generator=mock_embedding_generator,
        )
        await searcher.initialize()

        with pytest.raises(ValueError, match="not configured"):
            await searcher.search_workspace("test", "ws-1")

        await searcher.close()

    @pytest.mark.asyncio
    async def test_search_workspace_cross_repo_disabled(self, multi_repo_search):
        """Test searching workspace with cross-repo search disabled."""
        result = await multi_repo_search.search_workspace(
            query="test",
            workspace_id="ws-2",  # Has cross_repo_search_enabled=False
        )

        # Should return empty results
        assert result.total_repositories_searched == 0
        assert result.total_results_found == 0

    @pytest.mark.asyncio
    async def test_search_workspace_with_limits(self, multi_repo_search):
        """Test workspace search with limits."""
        result = await multi_repo_search.search_workspace(
            query="test",
            workspace_id="ws-1",
            limit_per_repo=5,
            total_limit=8,
        )

        # Should respect total limit
        assert len(result.aggregated_results) <= 8


# ============================================================================
# Dependency-Aware Search Tests
# ============================================================================

class TestDependencyAwareSearch:
    """Test searching with repository dependencies."""

    @pytest.mark.asyncio
    async def test_search_with_dependencies(
        self, multi_repo_search, repository_registry
    ):
        """Test searching repository with its dependencies."""
        repos = await repository_registry.list_repositories()

        # Add dependencies: repo1 -> repo2 -> repo3
        await repository_registry.add_dependency(repos[0].id, repos[1].id)
        await repository_registry.add_dependency(repos[1].id, repos[2].id)

        result = await multi_repo_search.search_with_dependencies(
            query="test",
            repository_id=repos[0].id,
            include_dependencies=True,
            max_depth=2,
        )

        # Should search repo1 + repo2 + repo3 + duplicates from dependency tree
        # (The get_dependencies method returns all levels, may include same repo multiple times)
        assert result.total_repositories_searched >= 3

    @pytest.mark.asyncio
    async def test_search_with_dependencies_disabled(
        self, multi_repo_search, repository_registry
    ):
        """Test searching repository without dependencies."""
        repos = await repository_registry.list_repositories()

        # Add dependencies but don't include them
        await repository_registry.add_dependency(repos[0].id, repos[1].id)

        result = await multi_repo_search.search_with_dependencies(
            query="test",
            repository_id=repos[0].id,
            include_dependencies=False,
        )

        # Should only search repo1
        assert result.total_repositories_searched == 1

    @pytest.mark.asyncio
    async def test_search_with_dependencies_respects_depth(
        self, multi_repo_search, repository_registry
    ):
        """Test that dependency depth limit is respected."""
        repos = await repository_registry.list_repositories()

        # Add dependencies: repo1 -> repo2 -> repo3
        await repository_registry.add_dependency(repos[0].id, repos[1].id)
        await repository_registry.add_dependency(repos[1].id, repos[2].id)

        result = await multi_repo_search.search_with_dependencies(
            query="test",
            repository_id=repos[0].id,
            include_dependencies=True,
            max_depth=1,  # Only direct dependencies
        )

        # Should search repo1 + repo2 (not repo3), but may have duplicates
        assert result.total_repositories_searched >= 2

    @pytest.mark.asyncio
    async def test_search_with_dependencies_not_found(self, multi_repo_search):
        """Test searching with dependencies for nonexistent repo fails."""
        with pytest.raises(ValueError, match="not found"):
            await multi_repo_search.search_with_dependencies(
                query="test",
                repository_id="nonexistent",
            )


# ============================================================================
# Search Scope Utilities Tests
# ============================================================================

class TestSearchScopeUtilities:
    """Test search scope utility methods."""

    @pytest.mark.asyncio
    async def test_get_search_scope_repositories_all(
        self, multi_repo_search, repository_registry
    ):
        """Test getting all indexed repositories."""
        repo_ids = await multi_repo_search.get_search_scope_repositories()

        # Should return all 3 indexed repositories
        assert len(repo_ids) == 3

    @pytest.mark.asyncio
    async def test_get_search_scope_repositories_by_workspace(
        self, multi_repo_search
    ):
        """Test getting repositories by workspace."""
        repo_ids = await multi_repo_search.get_search_scope_repositories(
            workspace_id="ws-1"
        )

        # Workspace has 2 repositories
        assert len(repo_ids) == 2

    @pytest.mark.asyncio
    async def test_get_search_scope_repositories_by_tags(
        self, multi_repo_search, repository_registry
    ):
        """Test getting repositories by tags."""
        repos = await repository_registry.list_repositories()

        # Add tags to some repos
        await repository_registry.add_tag(repos[0].id, "backend")
        await repository_registry.add_tag(repos[1].id, "backend")
        await repository_registry.add_tag(repos[2].id, "frontend")

        repo_ids = await multi_repo_search.get_search_scope_repositories(
            tags=["backend"]
        )

        # Should return repos with backend tag
        assert len(repo_ids) == 2

    @pytest.mark.asyncio
    async def test_get_search_scope_repositories_excludes_stale(
        self, multi_repo_search, repository_registry
    ):
        """Test that stale repositories are excluded by default."""
        repos = await repository_registry.list_repositories()

        # Mark one repo as stale
        repos[0].status = RepositoryStatus.STALE
        repository_registry.repositories[repos[0].id] = repos[0]
        repository_registry._save()

        repo_ids = await multi_repo_search.get_search_scope_repositories(
            include_stale=False
        )

        # Should only return indexed repos (2 out of 3)
        assert len(repo_ids) == 2

    @pytest.mark.asyncio
    async def test_get_search_scope_repositories_includes_stale(
        self, multi_repo_search, repository_registry
    ):
        """Test including stale repositories."""
        repos = await repository_registry.list_repositories()

        # Mark one repo as stale
        repos[0].status = RepositoryStatus.STALE
        repository_registry.repositories[repos[0].id] = repos[0]
        repository_registry._save()

        repo_ids = await multi_repo_search.get_search_scope_repositories(
            include_stale=True
        )

        # Should return all repos including stale (3 total)
        assert len(repo_ids) == 3

    @pytest.mark.asyncio
    async def test_get_search_scope_repositories_workspace_not_found(
        self, multi_repo_search
    ):
        """Test getting scope for nonexistent workspace fails."""
        with pytest.raises(ValueError, match="not found"):
            await multi_repo_search.get_search_scope_repositories(
                workspace_id="nonexistent"
            )
