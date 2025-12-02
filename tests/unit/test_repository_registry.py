"""Tests for repository registry."""

import pytest
import pytest_asyncio
import tempfile
from pathlib import Path
from datetime import datetime, UTC
from src.memory.repository_registry import (
    Repository,
    RepositoryRegistry,
    RepositoryType,
    RepositoryStatus,
)


@pytest_asyncio.fixture
async def registry():
    """Create a test registry with temporary storage."""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage_path = Path(tmpdir) / "test_registry.json"
        reg = RepositoryRegistry(str(storage_path))
        yield reg


@pytest_asyncio.fixture
async def sample_repo_paths():
    """Create sample repository directories."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo1 = Path(tmpdir) / "repo1"
        repo2 = Path(tmpdir) / "repo2"
        repo3 = Path(tmpdir) / "repo3"

        repo1.mkdir()
        repo2.mkdir()
        repo3.mkdir()

        yield {
            "repo1": str(repo1),
            "repo2": str(repo2),
            "repo3": str(repo3),
        }


class TestRepositoryModel:
    """Test Repository data model."""

    def test_repository_creation(self):
        """Test creating a repository instance."""
        repo = Repository(
            id="test-id",
            name="test-repo",
            path="/path/to/repo",
            repo_type=RepositoryType.STANDALONE,
            status=RepositoryStatus.NOT_INDEXED,
        )

        assert repo.id == "test-id"
        assert repo.name == "test-repo"
        assert repo.path == "/path/to/repo"
        assert repo.repo_type == RepositoryType.STANDALONE
        assert repo.status == RepositoryStatus.NOT_INDEXED
        assert repo.file_count == 0
        assert repo.unit_count == 0
        assert repo.workspace_ids == []
        assert repo.tags == []
        assert repo.depends_on == []
        assert repo.depended_by == []

    def test_repository_to_dict(self):
        """Test converting repository to dictionary."""
        repo = Repository(
            id="test-id",
            name="test-repo",
            path="/path/to/repo",
            repo_type=RepositoryType.MONOREPO,
            status=RepositoryStatus.INDEXED,
            tags=["tag1", "tag2"],
        )

        data = repo.to_dict()

        assert data["id"] == "test-id"
        assert data["name"] == "test-repo"
        assert data["repo_type"] == "monorepo"
        assert data["status"] == "indexed"
        assert data["tags"] == ["tag1", "tag2"]

    def test_repository_from_dict(self):
        """Test creating repository from dictionary."""
        data = {
            "id": "test-id",
            "name": "test-repo",
            "path": "/path/to/repo",
            "repo_type": "multi_repo",
            "status": "stale",
            "file_count": 100,
            "unit_count": 500,
            "tags": ["backend", "python"],
            "workspace_ids": ["ws-1"],
            "depends_on": ["repo-2"],
            "depended_by": [],
        }

        repo = Repository.from_dict(data)

        assert repo.id == "test-id"
        assert repo.repo_type == RepositoryType.MULTI_REPO
        assert repo.status == RepositoryStatus.STALE
        assert repo.file_count == 100
        assert repo.unit_count == 500
        assert repo.tags == ["backend", "python"]

    def test_repository_roundtrip(self):
        """Test converting to dict and back preserves data."""
        original = Repository(
            id="test-id",
            name="test-repo",
            path="/path/to/repo",
            git_url="https://github.com/user/repo.git",
            repo_type=RepositoryType.MULTI_REPO,
            status=RepositoryStatus.INDEXED,
            indexed_at=datetime.now(UTC),
            last_updated=datetime.now(UTC),
            file_count=150,
            unit_count=750,
            tags=["tag1", "tag2"],
            workspace_ids=["ws-1", "ws-2"],
            depends_on=["dep-1"],
            depended_by=["dep-2"],
        )

        data = original.to_dict()
        restored = Repository.from_dict(data)

        assert restored.id == original.id
        assert restored.name == original.name
        assert restored.path == original.path
        assert restored.git_url == original.git_url
        assert restored.repo_type == original.repo_type
        assert restored.status == original.status
        assert restored.file_count == original.file_count
        assert restored.unit_count == original.unit_count
        assert restored.tags == original.tags
        assert restored.workspace_ids == original.workspace_ids
        assert restored.depends_on == original.depends_on
        assert restored.depended_by == original.depended_by


class TestRegistryBasics:
    """Test basic registry operations."""

    @pytest.mark.asyncio
    async def test_registry_initialization(self, registry):
        """Test registry initializes correctly."""
        assert len(registry.repositories) == 0
        # Storage file is created on first save, not on init
        assert registry.storage_path.parent.exists()

    @pytest.mark.asyncio
    async def test_register_repository(self, registry, sample_repo_paths):
        """Test registering a repository."""
        repo_id = await registry.register_repository(
            path=sample_repo_paths["repo1"],
            name="Test Repo",
            repo_type=RepositoryType.STANDALONE,
        )

        assert repo_id is not None
        assert len(registry.repositories) == 1

        repo = await registry.get_repository(repo_id)
        assert repo is not None
        assert repo.name == "Test Repo"
        assert repo.repo_type == RepositoryType.STANDALONE
        assert repo.status == RepositoryStatus.NOT_INDEXED

    @pytest.mark.asyncio
    async def test_register_repository_default_name(self, registry, sample_repo_paths):
        """Test registering repository uses directory name as default."""
        repo_id = await registry.register_repository(path=sample_repo_paths["repo1"])

        repo = await registry.get_repository(repo_id)
        assert repo.name == "repo1"  # Directory name

    @pytest.mark.asyncio
    async def test_register_duplicate_path_fails(self, registry, sample_repo_paths):
        """Test registering same path twice raises error."""
        await registry.register_repository(path=sample_repo_paths["repo1"])

        with pytest.raises(ValueError, match="already registered"):
            await registry.register_repository(path=sample_repo_paths["repo1"])

    @pytest.mark.asyncio
    async def test_unregister_repository(self, registry, sample_repo_paths):
        """Test unregistering a repository."""
        repo_id = await registry.register_repository(path=sample_repo_paths["repo1"])
        assert len(registry.repositories) == 1

        await registry.unregister_repository(repo_id)
        assert len(registry.repositories) == 0

    @pytest.mark.asyncio
    async def test_unregister_nonexistent_fails(self, registry):
        """Test unregistering non-existent repository raises error."""
        with pytest.raises(KeyError, match="not found"):
            await registry.unregister_repository("nonexistent-id")


class TestRegistryRetrieval:
    """Test repository retrieval methods."""

    @pytest.mark.asyncio
    async def test_get_repository_by_id(self, registry, sample_repo_paths):
        """Test getting repository by ID."""
        repo_id = await registry.register_repository(
            path=sample_repo_paths["repo1"], name="Test Repo"
        )

        repo = await registry.get_repository(repo_id)
        assert repo is not None
        assert repo.id == repo_id
        assert repo.name == "Test Repo"

    @pytest.mark.asyncio
    async def test_get_nonexistent_repository(self, registry):
        """Test getting non-existent repository returns None."""
        repo = await registry.get_repository("nonexistent-id")
        assert repo is None

    @pytest.mark.asyncio
    async def test_get_repository_by_path(self, registry, sample_repo_paths):
        """Test getting repository by path."""
        await registry.register_repository(
            path=sample_repo_paths["repo1"], name="Test Repo"
        )

        repo = await registry.get_repository_by_path(sample_repo_paths["repo1"])
        assert repo is not None
        assert repo.name == "Test Repo"

    @pytest.mark.asyncio
    async def test_get_repository_by_path_normalizes(self, registry, sample_repo_paths):
        """Test path lookup normalizes paths."""
        await registry.register_repository(path=sample_repo_paths["repo1"])

        # Try with trailing slash
        path_with_slash = sample_repo_paths["repo1"] + "/"
        repo = await registry.get_repository_by_path(path_with_slash)
        assert repo is not None

    @pytest.mark.asyncio
    async def test_get_repository_by_name(self, registry, sample_repo_paths):
        """Test getting repository by name."""
        await registry.register_repository(
            path=sample_repo_paths["repo1"], name="My Special Repo"
        )

        repo = await registry.get_repository_by_name("My Special Repo")
        assert repo is not None
        assert repo.name == "My Special Repo"

    @pytest.mark.asyncio
    async def test_get_repository_by_name_not_found(self, registry):
        """Test getting repository by non-existent name returns None."""
        repo = await registry.get_repository_by_name("Nonexistent")
        assert repo is None


class TestRegistryFiltering:
    """Test repository list filtering."""

    @pytest_asyncio.fixture
    async def populated_registry(self, registry, sample_repo_paths):
        """Create registry with multiple repositories."""
        await registry.register_repository(
            path=sample_repo_paths["repo1"],
            name="Backend API",
            repo_type=RepositoryType.MULTI_REPO,
            tags=["backend", "python"],
        )

        repo2_id = await registry.register_repository(
            path=sample_repo_paths["repo2"],
            name="Frontend App",
            repo_type=RepositoryType.STANDALONE,
            tags=["frontend", "javascript"],
        )

        repo3_id = await registry.register_repository(
            path=sample_repo_paths["repo3"],
            name="Monorepo",
            repo_type=RepositoryType.MONOREPO,
            tags=["backend", "frontend"],
        )

        # Update some statuses
        await registry.update_repository(repo2_id, {"status": RepositoryStatus.INDEXED})
        await registry.update_repository(repo3_id, {"status": RepositoryStatus.STALE})

        return registry

    @pytest.mark.asyncio
    async def test_list_all_repositories(self, populated_registry):
        """Test listing all repositories."""
        repos = await populated_registry.list_repositories()
        assert len(repos) == 3

    @pytest.mark.asyncio
    async def test_filter_by_status(self, populated_registry):
        """Test filtering by repository status."""
        indexed = await populated_registry.list_repositories(
            status=RepositoryStatus.INDEXED
        )
        assert len(indexed) == 1
        assert indexed[0].name == "Frontend App"

        not_indexed = await populated_registry.list_repositories(
            status=RepositoryStatus.NOT_INDEXED
        )
        assert len(not_indexed) == 1
        assert not_indexed[0].name == "Backend API"

    @pytest.mark.asyncio
    async def test_filter_by_repo_type(self, populated_registry):
        """Test filtering by repository type."""
        monorepos = await populated_registry.list_repositories(
            repo_type=RepositoryType.MONOREPO
        )
        assert len(monorepos) == 1
        assert monorepos[0].name == "Monorepo"

        multi_repos = await populated_registry.list_repositories(
            repo_type=RepositoryType.MULTI_REPO
        )
        assert len(multi_repos) == 1
        assert multi_repos[0].name == "Backend API"

    @pytest.mark.asyncio
    async def test_filter_by_tags(self, populated_registry):
        """Test filtering by tags."""
        backend_repos = await populated_registry.list_repositories(tags=["backend"])
        assert len(backend_repos) == 2

        frontend_repos = await populated_registry.list_repositories(tags=["frontend"])
        assert len(frontend_repos) == 2

        python_repos = await populated_registry.list_repositories(tags=["python"])
        assert len(python_repos) == 1
        assert python_repos[0].name == "Backend API"

    @pytest.mark.asyncio
    async def test_filter_by_multiple_tags(self, populated_registry):
        """Test filtering by multiple tags (OR condition)."""
        repos = await populated_registry.list_repositories(
            tags=["python", "javascript"]
        )
        assert len(repos) == 2  # Repos with either tag

    @pytest.mark.asyncio
    async def test_filter_by_workspace(self, populated_registry):
        """Test filtering by workspace membership."""
        # Add repos to workspace
        repos = await populated_registry.list_repositories()
        await populated_registry.add_to_workspace(repos[0].id, "ws-1")
        await populated_registry.add_to_workspace(repos[1].id, "ws-1")

        ws_repos = await populated_registry.list_repositories(workspace_id="ws-1")
        assert len(ws_repos) == 2

        ws2_repos = await populated_registry.list_repositories(workspace_id="ws-2")
        assert len(ws2_repos) == 0

    @pytest.mark.asyncio
    async def test_filter_combined(self, populated_registry):
        """Test combining multiple filters."""
        repos = await populated_registry.list_repositories(
            status=RepositoryStatus.NOT_INDEXED, tags=["backend"]
        )
        assert len(repos) == 1
        assert repos[0].name == "Backend API"


class TestRegistryUpdates:
    """Test repository update operations."""

    @pytest.mark.asyncio
    async def test_update_repository_status(self, registry, sample_repo_paths):
        """Test updating repository status."""
        repo_id = await registry.register_repository(path=sample_repo_paths["repo1"])

        await registry.update_repository(
            repo_id,
            {
                "status": RepositoryStatus.INDEXED,
                "file_count": 100,
                "unit_count": 500,
            },
        )

        repo = await registry.get_repository(repo_id)
        assert repo.status == RepositoryStatus.INDEXED
        assert repo.file_count == 100
        assert repo.unit_count == 500
        assert repo.last_updated is not None

    @pytest.mark.asyncio
    async def test_update_repository_name(self, registry, sample_repo_paths):
        """Test updating repository name."""
        repo_id = await registry.register_repository(
            path=sample_repo_paths["repo1"], name="Old Name"
        )

        await registry.update_repository(repo_id, {"name": "New Name"})

        repo = await registry.get_repository(repo_id)
        assert repo.name == "New Name"

    @pytest.mark.asyncio
    async def test_update_nonexistent_fails(self, registry):
        """Test updating non-existent repository raises error."""
        with pytest.raises(KeyError, match="not found"):
            await registry.update_repository("nonexistent", {"name": "Test"})

    @pytest.mark.asyncio
    async def test_update_invalid_field_fails(self, registry, sample_repo_paths):
        """Test updating invalid field raises error."""
        repo_id = await registry.register_repository(path=sample_repo_paths["repo1"])

        with pytest.raises(ValueError, match="Invalid field"):
            await registry.update_repository(repo_id, {"invalid_field": "value"})

    @pytest.mark.asyncio
    async def test_update_with_string_enums(self, registry, sample_repo_paths):
        """Test updating with string enum values."""
        repo_id = await registry.register_repository(path=sample_repo_paths["repo1"])

        await registry.update_repository(
            repo_id,
            {
                "status": "indexed",  # String instead of enum
                "repo_type": "monorepo",
            },
        )

        repo = await registry.get_repository(repo_id)
        assert repo.status == RepositoryStatus.INDEXED
        assert repo.repo_type == RepositoryType.MONOREPO


class TestDependencyTracking:
    """Test repository dependency tracking."""

    @pytest_asyncio.fixture
    async def multi_repo_registry(self, registry, sample_repo_paths):
        """Create registry with multiple repositories."""
        repo1_id = await registry.register_repository(
            path=sample_repo_paths["repo1"], name="API Gateway"
        )
        repo2_id = await registry.register_repository(
            path=sample_repo_paths["repo2"], name="Auth Service"
        )
        repo3_id = await registry.register_repository(
            path=sample_repo_paths["repo3"], name="User Service"
        )

        return registry, repo1_id, repo2_id, repo3_id

    @pytest.mark.asyncio
    async def test_add_dependency(self, multi_repo_registry):
        """Test adding a dependency relationship."""
        registry, repo1, repo2, _ = multi_repo_registry

        await registry.add_dependency(repo1, repo2)

        r1 = await registry.get_repository(repo1)
        r2 = await registry.get_repository(repo2)

        assert repo2 in r1.depends_on
        assert repo1 in r2.depended_by

    @pytest.mark.asyncio
    async def test_add_dependency_nonexistent_fails(self, registry):
        """Test adding dependency with non-existent repo fails."""
        with pytest.raises(KeyError):
            await registry.add_dependency("nonexistent", "also-nonexistent")

    @pytest.mark.asyncio
    async def test_add_self_dependency_fails(self, multi_repo_registry):
        """Test repository cannot depend on itself."""
        registry, repo1, _, _ = multi_repo_registry

        with pytest.raises(ValueError, match="cannot depend on itself"):
            await registry.add_dependency(repo1, repo1)

    @pytest.mark.asyncio
    async def test_add_dependency_prevents_cycles(self, multi_repo_registry):
        """Test adding dependency that would create cycle fails."""
        registry, repo1, repo2, repo3 = multi_repo_registry

        # Create chain: repo1 -> repo2 -> repo3
        await registry.add_dependency(repo1, repo2)
        await registry.add_dependency(repo2, repo3)

        # Try to create cycle: repo3 -> repo1
        with pytest.raises(ValueError, match="would create a cycle"):
            await registry.add_dependency(repo3, repo1)

    @pytest.mark.asyncio
    async def test_remove_dependency(self, multi_repo_registry):
        """Test removing a dependency relationship."""
        registry, repo1, repo2, _ = multi_repo_registry

        await registry.add_dependency(repo1, repo2)
        await registry.remove_dependency(repo1, repo2)

        r1 = await registry.get_repository(repo1)
        r2 = await registry.get_repository(repo2)

        assert repo2 not in r1.depends_on
        assert repo1 not in r2.depended_by

    @pytest.mark.asyncio
    async def test_get_dependencies_direct(self, multi_repo_registry):
        """Test getting direct dependencies."""
        registry, repo1, repo2, repo3 = multi_repo_registry

        await registry.add_dependency(repo1, repo2)
        await registry.add_dependency(repo1, repo3)

        deps = await registry.get_dependencies(repo1, max_depth=1)

        assert 0 in deps  # Self
        assert 1 in deps  # Direct dependencies
        assert repo1 in deps[0]
        assert repo2 in deps[1]
        assert repo3 in deps[1]

    @pytest.mark.asyncio
    async def test_get_dependencies_transitive(self, multi_repo_registry):
        """Test getting transitive dependencies."""
        registry, repo1, repo2, repo3 = multi_repo_registry

        # Chain: repo1 -> repo2 -> repo3
        await registry.add_dependency(repo1, repo2)
        await registry.add_dependency(repo2, repo3)

        deps = await registry.get_dependencies(repo1, max_depth=3)

        assert 0 in deps  # Self
        assert 1 in deps  # repo2
        assert 2 in deps  # repo3

    @pytest.mark.asyncio
    async def test_get_dependencies_respects_max_depth(self, multi_repo_registry):
        """Test dependency traversal respects max depth."""
        registry, repo1, repo2, repo3 = multi_repo_registry

        await registry.add_dependency(repo1, repo2)
        await registry.add_dependency(repo2, repo3)

        deps = await registry.get_dependencies(repo1, max_depth=1)

        assert 0 in deps  # Self
        assert 1 in deps  # repo2
        assert 2 not in deps  # repo3 not included due to depth limit

    @pytest.mark.asyncio
    async def test_unregister_removes_from_dependencies(self, multi_repo_registry):
        """Test unregistering repository removes it from dependents."""
        registry, repo1, repo2, _ = multi_repo_registry

        await registry.add_dependency(repo1, repo2)
        await registry.unregister_repository(repo2)

        r1 = await registry.get_repository(repo1)
        assert repo2 not in r1.depends_on


class TestTagManagement:
    """Test repository tag operations."""

    @pytest.mark.asyncio
    async def test_add_tag(self, registry, sample_repo_paths):
        """Test adding a tag to repository."""
        repo_id = await registry.register_repository(path=sample_repo_paths["repo1"])

        await registry.add_tag(repo_id, "python")
        await registry.add_tag(repo_id, "backend")

        repo = await registry.get_repository(repo_id)
        assert "python" in repo.tags
        assert "backend" in repo.tags

    @pytest.mark.asyncio
    async def test_add_duplicate_tag_idempotent(self, registry, sample_repo_paths):
        """Test adding same tag twice is idempotent."""
        repo_id = await registry.register_repository(path=sample_repo_paths["repo1"])

        await registry.add_tag(repo_id, "python")
        await registry.add_tag(repo_id, "python")

        repo = await registry.get_repository(repo_id)
        assert repo.tags.count("python") == 1

    @pytest.mark.asyncio
    async def test_remove_tag(self, registry, sample_repo_paths):
        """Test removing a tag from repository."""
        repo_id = await registry.register_repository(
            path=sample_repo_paths["repo1"], tags=["python", "backend"]
        )

        await registry.remove_tag(repo_id, "python")

        repo = await registry.get_repository(repo_id)
        assert "python" not in repo.tags
        assert "backend" in repo.tags

    @pytest.mark.asyncio
    async def test_remove_nonexistent_tag(self, registry, sample_repo_paths):
        """Test removing non-existent tag does nothing."""
        repo_id = await registry.register_repository(path=sample_repo_paths["repo1"])

        # Should not raise error
        await registry.remove_tag(repo_id, "nonexistent")


class TestWorkspaceManagement:
    """Test workspace membership operations."""

    @pytest.mark.asyncio
    async def test_add_to_workspace(self, registry, sample_repo_paths):
        """Test adding repository to workspace."""
        repo_id = await registry.register_repository(path=sample_repo_paths["repo1"])

        await registry.add_to_workspace(repo_id, "ws-1")

        repo = await registry.get_repository(repo_id)
        assert "ws-1" in repo.workspace_ids

    @pytest.mark.asyncio
    async def test_add_to_multiple_workspaces(self, registry, sample_repo_paths):
        """Test repository can belong to multiple workspaces."""
        repo_id = await registry.register_repository(path=sample_repo_paths["repo1"])

        await registry.add_to_workspace(repo_id, "ws-1")
        await registry.add_to_workspace(repo_id, "ws-2")

        repo = await registry.get_repository(repo_id)
        assert "ws-1" in repo.workspace_ids
        assert "ws-2" in repo.workspace_ids

    @pytest.mark.asyncio
    async def test_add_to_workspace_idempotent(self, registry, sample_repo_paths):
        """Test adding to same workspace twice is idempotent."""
        repo_id = await registry.register_repository(path=sample_repo_paths["repo1"])

        await registry.add_to_workspace(repo_id, "ws-1")
        await registry.add_to_workspace(repo_id, "ws-1")

        repo = await registry.get_repository(repo_id)
        assert repo.workspace_ids.count("ws-1") == 1

    @pytest.mark.asyncio
    async def test_remove_from_workspace(self, registry, sample_repo_paths):
        """Test removing repository from workspace."""
        repo_id = await registry.register_repository(path=sample_repo_paths["repo1"])

        await registry.add_to_workspace(repo_id, "ws-1")
        await registry.add_to_workspace(repo_id, "ws-2")
        await registry.remove_from_workspace(repo_id, "ws-1")

        repo = await registry.get_repository(repo_id)
        assert "ws-1" not in repo.workspace_ids
        assert "ws-2" in repo.workspace_ids


class TestPersistence:
    """Test JSON persistence."""

    @pytest.mark.asyncio
    async def test_save_and_load(self, sample_repo_paths):
        """Test registry data persists across instances."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage_path = Path(tmpdir) / "registry.json"

            # Create registry and add repos
            reg1 = RepositoryRegistry(str(storage_path))
            repo_id = await reg1.register_repository(
                path=sample_repo_paths["repo1"],
                name="Test Repo",
                repo_type=RepositoryType.MONOREPO,
                tags=["test"],
            )

            # Create new registry instance with same storage
            reg2 = RepositoryRegistry(str(storage_path))

            # Verify data persisted
            assert len(reg2.repositories) == 1
            repo = await reg2.get_repository(repo_id)
            assert repo.name == "Test Repo"
            assert repo.repo_type == RepositoryType.MONOREPO
            assert "test" in repo.tags

    @pytest.mark.asyncio
    async def test_load_empty_registry(self):
        """Test loading registry when no file exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage_path = Path(tmpdir) / "nonexistent.json"
            reg = RepositoryRegistry(str(storage_path))

            assert len(reg.repositories) == 0

    @pytest.mark.asyncio
    async def test_load_corrupted_file_graceful(self):
        """Test loading corrupted registry file doesn't crash."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage_path = Path(tmpdir) / "registry.json"

            # Write invalid JSON
            storage_path.write_text("{ invalid json }")

            # Should not crash, just load empty
            reg = RepositoryRegistry(str(storage_path))
            assert len(reg.repositories) == 0


class TestStatistics:
    """Test registry statistics."""

    @pytest_asyncio.fixture
    async def stats_registry(self, registry, sample_repo_paths):
        """Create registry with repos in various states."""
        repo1_id = await registry.register_repository(
            path=sample_repo_paths["repo1"], repo_type=RepositoryType.STANDALONE
        )
        await registry.update_repository(
            repo1_id,
            {"status": RepositoryStatus.INDEXED, "file_count": 100, "unit_count": 500},
        )

        repo2_id = await registry.register_repository(
            path=sample_repo_paths["repo2"], repo_type=RepositoryType.MONOREPO
        )
        await registry.update_repository(
            repo2_id,
            {"status": RepositoryStatus.INDEXED, "file_count": 200, "unit_count": 1000},
        )

        await registry.register_repository(
            path=sample_repo_paths["repo3"], repo_type=RepositoryType.MULTI_REPO
        )  # NOT_INDEXED

        return registry

    @pytest.mark.asyncio
    async def test_get_statistics(self, stats_registry):
        """Test getting registry statistics."""
        stats = await stats_registry.get_statistics()

        assert stats["total_repositories"] == 3
        assert stats["total_files_indexed"] == 300
        assert stats["total_units_indexed"] == 1500

        assert stats["by_status"]["indexed"] == 2
        assert stats["by_status"]["not_indexed"] == 1

        assert stats["by_type"]["standalone"] == 1
        assert stats["by_type"]["monorepo"] == 1
        assert stats["by_type"]["multi_repo"] == 1
