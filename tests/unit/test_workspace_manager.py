"""Tests for workspace manager."""

import pytest
import pytest_asyncio
from datetime import datetime, UTC
from unittest.mock import AsyncMock

from src.memory.workspace_manager import Workspace, WorkspaceManager
from src.memory.repository_registry import (
    Repository,
    RepositoryRegistry,
    RepositoryType,
    RepositoryStatus,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def temp_workspace_file(tmp_path):
    """Create temporary workspace storage file."""
    return tmp_path / "workspaces.json"


@pytest_asyncio.fixture
async def mock_registry():
    """Create mock repository registry."""
    registry = AsyncMock(spec=RepositoryRegistry)

    # Mock some repositories
    repo1 = Repository(
        id="repo-1",
        name="Test Repo 1",
        path="/path/to/repo1",
        repo_type=RepositoryType.STANDALONE,
        status=RepositoryStatus.INDEXED,
    )
    repo2 = Repository(
        id="repo-2",
        name="Test Repo 2",
        path="/path/to/repo2",
        repo_type=RepositoryType.STANDALONE,
        status=RepositoryStatus.INDEXED,
    )
    repo3 = Repository(
        id="repo-3",
        name="Test Repo 3",
        path="/path/to/repo3",
        repo_type=RepositoryType.STANDALONE,
        status=RepositoryStatus.INDEXED,
    )

    # Configure mock to return repositories
    async def get_repository(repo_id):
        repos = {"repo-1": repo1, "repo-2": repo2, "repo-3": repo3}
        return repos.get(repo_id)

    registry.get_repository.side_effect = get_repository
    registry.add_to_workspace = AsyncMock()
    registry.remove_from_workspace = AsyncMock()

    return registry


@pytest_asyncio.fixture
async def workspace_manager(temp_workspace_file, mock_registry):
    """Create workspace manager with mock registry."""
    return WorkspaceManager(str(temp_workspace_file), mock_registry)


@pytest_asyncio.fixture
async def workspace_manager_no_registry(temp_workspace_file):
    """Create workspace manager without registry."""
    return WorkspaceManager(str(temp_workspace_file), None)


# ============================================================================
# Workspace Model Tests
# ============================================================================


class TestWorkspaceModel:
    """Test Workspace dataclass."""

    def test_workspace_creation(self):
        """Test creating a workspace."""
        workspace = Workspace(
            id="ws-1",
            name="Test Workspace",
            description="A test workspace",
            repository_ids=["repo-1", "repo-2"],
            auto_index=True,
            cross_repo_search_enabled=True,
            tags=["backend", "services"],
        )

        assert workspace.id == "ws-1"
        assert workspace.name == "Test Workspace"
        assert workspace.description == "A test workspace"
        assert workspace.repository_ids == ["repo-1", "repo-2"]
        assert workspace.auto_index is True
        assert workspace.cross_repo_search_enabled is True
        assert workspace.tags == ["backend", "services"]
        assert isinstance(workspace.created_at, datetime)
        assert isinstance(workspace.updated_at, datetime)

    def test_workspace_to_dict(self):
        """Test converting workspace to dictionary."""
        workspace = Workspace(
            id="ws-1",
            name="Test Workspace",
            repository_ids=["repo-1"],
        )

        data = workspace.to_dict()

        assert data["id"] == "ws-1"
        assert data["name"] == "Test Workspace"
        assert data["repository_ids"] == ["repo-1"]
        assert isinstance(data["created_at"], str)  # ISO format
        assert isinstance(data["updated_at"], str)  # ISO format

    def test_workspace_from_dict(self):
        """Test creating workspace from dictionary."""
        now = datetime.now(UTC)
        data = {
            "id": "ws-1",
            "name": "Test Workspace",
            "description": "Test",
            "repository_ids": ["repo-1"],
            "auto_index": True,
            "cross_repo_search_enabled": False,
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
            "tags": ["test"],
            "settings": {"key": "value"},
        }

        workspace = Workspace.from_dict(data)

        assert workspace.id == "ws-1"
        assert workspace.name == "Test Workspace"
        assert workspace.repository_ids == ["repo-1"]
        assert isinstance(workspace.created_at, datetime)
        assert isinstance(workspace.updated_at, datetime)

    def test_workspace_roundtrip(self):
        """Test workspace serialization roundtrip."""
        original = Workspace(
            id="ws-1",
            name="Test Workspace",
            repository_ids=["repo-1", "repo-2"],
            tags=["backend"],
        )

        data = original.to_dict()
        restored = Workspace.from_dict(data)

        assert restored.id == original.id
        assert restored.name == original.name
        assert restored.repository_ids == original.repository_ids
        assert restored.tags == original.tags


# ============================================================================
# Manager Basics Tests
# ============================================================================


class TestWorkspaceManagerBasics:
    """Test basic workspace manager operations."""

    @pytest.mark.asyncio
    async def test_manager_initialization(self, temp_workspace_file):
        """Test workspace manager initialization."""
        manager = WorkspaceManager(str(temp_workspace_file))

        assert manager.storage_path == temp_workspace_file
        assert manager.storage_path.parent.exists()
        assert len(manager.workspaces) == 0

    @pytest.mark.asyncio
    async def test_create_workspace(self, workspace_manager):
        """Test creating a workspace."""
        workspace = await workspace_manager.create_workspace(
            workspace_id="ws-1",
            name="Test Workspace",
            description="A test workspace",
            repository_ids=["repo-1", "repo-2"],
            tags=["backend"],
        )

        assert workspace.id == "ws-1"
        assert workspace.name == "Test Workspace"
        assert workspace.description == "A test workspace"
        assert workspace.repository_ids == ["repo-1", "repo-2"]
        assert workspace.tags == ["backend"]

        # Should be in manager
        assert "ws-1" in workspace_manager.workspaces

        # Should update registry
        workspace_manager.repository_registry.add_to_workspace.assert_any_call(
            "repo-1", "ws-1"
        )
        workspace_manager.repository_registry.add_to_workspace.assert_any_call(
            "repo-2", "ws-1"
        )

    @pytest.mark.asyncio
    async def test_create_workspace_duplicate_id_fails(self, workspace_manager):
        """Test creating workspace with duplicate ID fails."""
        await workspace_manager.create_workspace(
            workspace_id="ws-1",
            name="First Workspace",
        )

        with pytest.raises(ValueError, match="already exists"):
            await workspace_manager.create_workspace(
                workspace_id="ws-1",
                name="Second Workspace",
            )

    @pytest.mark.asyncio
    async def test_create_workspace_empty_name_fails(self, workspace_manager):
        """Test creating workspace with empty name fails."""
        with pytest.raises(ValueError, match="cannot be empty"):
            await workspace_manager.create_workspace(
                workspace_id="ws-1",
                name="",
            )

        with pytest.raises(ValueError, match="cannot be empty"):
            await workspace_manager.create_workspace(
                workspace_id="ws-1",
                name="   ",
            )

    @pytest.mark.asyncio
    async def test_create_workspace_invalid_repo_fails(self, workspace_manager):
        """Test creating workspace with invalid repository ID fails."""
        with pytest.raises(ValueError, match="not found in registry"):
            await workspace_manager.create_workspace(
                workspace_id="ws-1",
                name="Test Workspace",
                repository_ids=["nonexistent-repo"],
            )

    @pytest.mark.asyncio
    async def test_create_workspace_no_registry(self, workspace_manager_no_registry):
        """Test creating workspace without registry."""
        workspace = await workspace_manager_no_registry.create_workspace(
            workspace_id="ws-1",
            name="Test Workspace",
            repository_ids=["repo-1"],  # Not validated without registry
        )

        assert workspace.id == "ws-1"
        assert workspace.repository_ids == ["repo-1"]

    @pytest.mark.asyncio
    async def test_delete_workspace(self, workspace_manager):
        """Test deleting a workspace."""
        await workspace_manager.create_workspace(
            workspace_id="ws-1",
            name="Test Workspace",
            repository_ids=["repo-1"],
        )

        await workspace_manager.delete_workspace("ws-1")

        assert "ws-1" not in workspace_manager.workspaces

        # Should update registry
        workspace_manager.repository_registry.remove_from_workspace.assert_called_once_with(
            "repo-1", "ws-1"
        )

    @pytest.mark.asyncio
    async def test_delete_nonexistent_workspace_fails(self, workspace_manager):
        """Test deleting nonexistent workspace fails."""
        with pytest.raises(ValueError, match="not found"):
            await workspace_manager.delete_workspace("nonexistent")


# ============================================================================
# Retrieval Tests
# ============================================================================


class TestWorkspaceRetrieval:
    """Test workspace retrieval operations."""

    @pytest.mark.asyncio
    async def test_get_workspace_by_id(self, workspace_manager):
        """Test getting workspace by ID."""
        await workspace_manager.create_workspace(
            workspace_id="ws-1",
            name="Test Workspace",
        )

        workspace = await workspace_manager.get_workspace("ws-1")

        assert workspace is not None
        assert workspace.id == "ws-1"
        assert workspace.name == "Test Workspace"

    @pytest.mark.asyncio
    async def test_get_nonexistent_workspace(self, workspace_manager):
        """Test getting nonexistent workspace returns None."""
        workspace = await workspace_manager.get_workspace("nonexistent")
        assert workspace is None

    @pytest.mark.asyncio
    async def test_get_workspace_by_name(self, workspace_manager):
        """Test getting workspace by name."""
        await workspace_manager.create_workspace(
            workspace_id="ws-1",
            name="Test Workspace",
        )

        workspace = await workspace_manager.get_workspace_by_name("Test Workspace")

        assert workspace is not None
        assert workspace.id == "ws-1"
        assert workspace.name == "Test Workspace"

    @pytest.mark.asyncio
    async def test_get_workspace_by_name_not_found(self, workspace_manager):
        """Test getting workspace by name returns None if not found."""
        workspace = await workspace_manager.get_workspace_by_name("Nonexistent")
        assert workspace is None

    @pytest.mark.asyncio
    async def test_list_all_workspaces(self, workspace_manager):
        """Test listing all workspaces."""
        await workspace_manager.create_workspace("ws-1", "Workspace 1")
        await workspace_manager.create_workspace("ws-2", "Workspace 2")
        await workspace_manager.create_workspace("ws-3", "Workspace 3")

        workspaces = await workspace_manager.list_workspaces()

        assert len(workspaces) == 3
        names = {ws.name for ws in workspaces}
        assert names == {"Workspace 1", "Workspace 2", "Workspace 3"}

    @pytest.mark.asyncio
    async def test_list_workspaces_filter_by_tags(self, workspace_manager):
        """Test listing workspaces filtered by tags."""
        await workspace_manager.create_workspace(
            "ws-1", "Workspace 1", tags=["backend", "api"]
        )
        await workspace_manager.create_workspace(
            "ws-2", "Workspace 2", tags=["frontend"]
        )
        await workspace_manager.create_workspace(
            "ws-3", "Workspace 3", tags=["backend"]
        )

        # Filter by single tag
        workspaces = await workspace_manager.list_workspaces(tags=["backend"])
        assert len(workspaces) == 2
        names = {ws.name for ws in workspaces}
        assert names == {"Workspace 1", "Workspace 3"}

        # Filter by multiple tags (must have ALL)
        workspaces = await workspace_manager.list_workspaces(tags=["backend", "api"])
        assert len(workspaces) == 1
        assert workspaces[0].name == "Workspace 1"

    @pytest.mark.asyncio
    async def test_list_workspaces_filter_by_repository(self, workspace_manager):
        """Test listing workspaces filtered by repository membership."""
        await workspace_manager.create_workspace(
            "ws-1", "Workspace 1", repository_ids=["repo-1", "repo-2"]
        )
        await workspace_manager.create_workspace(
            "ws-2", "Workspace 2", repository_ids=["repo-2", "repo-3"]
        )
        await workspace_manager.create_workspace(
            "ws-3", "Workspace 3", repository_ids=["repo-3"]
        )

        workspaces = await workspace_manager.list_workspaces(has_repo="repo-2")

        assert len(workspaces) == 2
        names = {ws.name for ws in workspaces}
        assert names == {"Workspace 1", "Workspace 2"}

    @pytest.mark.asyncio
    async def test_list_workspaces_combined_filters(self, workspace_manager):
        """Test listing workspaces with combined filters."""
        await workspace_manager.create_workspace(
            "ws-1", "Workspace 1", repository_ids=["repo-1"], tags=["backend"]
        )
        await workspace_manager.create_workspace(
            "ws-2", "Workspace 2", repository_ids=["repo-1"], tags=["frontend"]
        )
        await workspace_manager.create_workspace(
            "ws-3", "Workspace 3", repository_ids=["repo-2"], tags=["backend"]
        )

        workspaces = await workspace_manager.list_workspaces(
            tags=["backend"], has_repo="repo-1"
        )

        assert len(workspaces) == 1
        assert workspaces[0].name == "Workspace 1"


# ============================================================================
# Update Tests
# ============================================================================


class TestWorkspaceUpdates:
    """Test workspace update operations."""

    @pytest.mark.asyncio
    async def test_update_workspace_name(self, workspace_manager):
        """Test updating workspace name."""
        await workspace_manager.create_workspace("ws-1", "Old Name")

        await workspace_manager.update_workspace("ws-1", {"name": "New Name"})

        workspace = await workspace_manager.get_workspace("ws-1")
        assert workspace.name == "New Name"

    @pytest.mark.asyncio
    async def test_update_workspace_description(self, workspace_manager):
        """Test updating workspace description."""
        await workspace_manager.create_workspace("ws-1", "Test Workspace")

        await workspace_manager.update_workspace(
            "ws-1", {"description": "New description"}
        )

        workspace = await workspace_manager.get_workspace("ws-1")
        assert workspace.description == "New description"

    @pytest.mark.asyncio
    async def test_update_workspace_settings(self, workspace_manager):
        """Test updating workspace settings."""
        await workspace_manager.create_workspace("ws-1", "Test Workspace")

        await workspace_manager.update_workspace(
            "ws-1",
            {
                "auto_index": False,
                "cross_repo_search_enabled": False,
                "settings": {"key": "value"},
            },
        )

        workspace = await workspace_manager.get_workspace("ws-1")
        assert workspace.auto_index is False
        assert workspace.cross_repo_search_enabled is False
        assert workspace.settings == {"key": "value"}

    @pytest.mark.asyncio
    async def test_update_nonexistent_workspace_fails(self, workspace_manager):
        """Test updating nonexistent workspace fails."""
        with pytest.raises(ValueError, match="not found"):
            await workspace_manager.update_workspace(
                "nonexistent", {"name": "New Name"}
            )

    @pytest.mark.asyncio
    async def test_update_workspace_invalid_field_fails(self, workspace_manager):
        """Test updating invalid field fails."""
        await workspace_manager.create_workspace("ws-1", "Test Workspace")

        with pytest.raises(ValueError, match="Cannot update field"):
            await workspace_manager.update_workspace(
                "ws-1", {"repository_ids": ["repo-1"]}
            )

        with pytest.raises(ValueError, match="Cannot update field"):
            await workspace_manager.update_workspace("ws-1", {"id": "new-id"})

    @pytest.mark.asyncio
    async def test_update_workspace_updates_timestamp(self, workspace_manager):
        """Test updating workspace updates the updated_at timestamp."""
        await workspace_manager.create_workspace("ws-1", "Test Workspace")

        workspace = await workspace_manager.get_workspace("ws-1")
        original_updated_at = workspace.updated_at

        # Wait a bit to ensure timestamp changes
        import asyncio

        await asyncio.sleep(0.01)

        await workspace_manager.update_workspace("ws-1", {"name": "New Name"})

        workspace = await workspace_manager.get_workspace("ws-1")
        assert workspace.updated_at > original_updated_at


# ============================================================================
# Repository Management Tests
# ============================================================================


class TestWorkspaceRepositoryManagement:
    """Test workspace repository management."""

    @pytest.mark.asyncio
    async def test_add_repository(self, workspace_manager):
        """Test adding repository to workspace."""
        await workspace_manager.create_workspace("ws-1", "Test Workspace")

        await workspace_manager.add_repository("ws-1", "repo-1")

        workspace = await workspace_manager.get_workspace("ws-1")
        assert "repo-1" in workspace.repository_ids

        # Should update registry
        workspace_manager.repository_registry.add_to_workspace.assert_called_with(
            "repo-1", "ws-1"
        )

    @pytest.mark.asyncio
    async def test_add_repository_idempotent(self, workspace_manager):
        """Test adding same repository twice is idempotent."""
        await workspace_manager.create_workspace("ws-1", "Test Workspace")

        await workspace_manager.add_repository("ws-1", "repo-1")
        await workspace_manager.add_repository("ws-1", "repo-1")

        workspace = await workspace_manager.get_workspace("ws-1")
        assert workspace.repository_ids == ["repo-1"]  # Only once

    @pytest.mark.asyncio
    async def test_add_repository_nonexistent_workspace_fails(self, workspace_manager):
        """Test adding repository to nonexistent workspace fails."""
        with pytest.raises(ValueError, match="not found"):
            await workspace_manager.add_repository("nonexistent", "repo-1")

    @pytest.mark.asyncio
    async def test_add_repository_invalid_repo_fails(self, workspace_manager):
        """Test adding invalid repository fails."""
        await workspace_manager.create_workspace("ws-1", "Test Workspace")

        with pytest.raises(ValueError, match="not found in registry"):
            await workspace_manager.add_repository("ws-1", "nonexistent-repo")

    @pytest.mark.asyncio
    async def test_remove_repository(self, workspace_manager):
        """Test removing repository from workspace."""
        await workspace_manager.create_workspace(
            "ws-1", "Test Workspace", repository_ids=["repo-1", "repo-2"]
        )

        await workspace_manager.remove_repository("ws-1", "repo-1")

        workspace = await workspace_manager.get_workspace("ws-1")
        assert "repo-1" not in workspace.repository_ids
        assert "repo-2" in workspace.repository_ids

        # Should update registry
        workspace_manager.repository_registry.remove_from_workspace.assert_called_with(
            "repo-1", "ws-1"
        )

    @pytest.mark.asyncio
    async def test_remove_repository_not_in_workspace(self, workspace_manager):
        """Test removing repository not in workspace is no-op."""
        await workspace_manager.create_workspace("ws-1", "Test Workspace")

        # Should not raise error
        await workspace_manager.remove_repository("ws-1", "repo-1")

    @pytest.mark.asyncio
    async def test_remove_repository_nonexistent_workspace_fails(
        self, workspace_manager
    ):
        """Test removing repository from nonexistent workspace fails."""
        with pytest.raises(ValueError, match="not found"):
            await workspace_manager.remove_repository("nonexistent", "repo-1")

    @pytest.mark.asyncio
    async def test_get_workspace_repositories(self, workspace_manager):
        """Test getting list of workspace repositories."""
        await workspace_manager.create_workspace(
            "ws-1", "Test Workspace", repository_ids=["repo-1", "repo-2"]
        )

        repos = await workspace_manager.get_workspace_repositories("ws-1")

        assert repos == ["repo-1", "repo-2"]

    @pytest.mark.asyncio
    async def test_get_workspace_repositories_nonexistent_fails(
        self, workspace_manager
    ):
        """Test getting repositories of nonexistent workspace fails."""
        with pytest.raises(ValueError, match="not found"):
            await workspace_manager.get_workspace_repositories("nonexistent")


# ============================================================================
# Tag Management Tests
# ============================================================================


class TestWorkspaceTagManagement:
    """Test workspace tag management."""

    @pytest.mark.asyncio
    async def test_add_tag(self, workspace_manager):
        """Test adding tag to workspace."""
        await workspace_manager.create_workspace("ws-1", "Test Workspace")

        await workspace_manager.add_tag("ws-1", "backend")

        workspace = await workspace_manager.get_workspace("ws-1")
        assert "backend" in workspace.tags

    @pytest.mark.asyncio
    async def test_add_tag_idempotent(self, workspace_manager):
        """Test adding same tag twice is idempotent."""
        await workspace_manager.create_workspace("ws-1", "Test Workspace")

        await workspace_manager.add_tag("ws-1", "backend")
        await workspace_manager.add_tag("ws-1", "backend")

        workspace = await workspace_manager.get_workspace("ws-1")
        assert workspace.tags == ["backend"]  # Only once

    @pytest.mark.asyncio
    async def test_add_tag_nonexistent_workspace_fails(self, workspace_manager):
        """Test adding tag to nonexistent workspace fails."""
        with pytest.raises(ValueError, match="not found"):
            await workspace_manager.add_tag("nonexistent", "backend")

    @pytest.mark.asyncio
    async def test_remove_tag(self, workspace_manager):
        """Test removing tag from workspace."""
        await workspace_manager.create_workspace(
            "ws-1", "Test Workspace", tags=["backend", "api"]
        )

        await workspace_manager.remove_tag("ws-1", "backend")

        workspace = await workspace_manager.get_workspace("ws-1")
        assert "backend" not in workspace.tags
        assert "api" in workspace.tags

    @pytest.mark.asyncio
    async def test_remove_tag_not_present(self, workspace_manager):
        """Test removing tag not present is no-op."""
        await workspace_manager.create_workspace("ws-1", "Test Workspace")

        # Should not raise error
        await workspace_manager.remove_tag("ws-1", "nonexistent")

    @pytest.mark.asyncio
    async def test_remove_tag_nonexistent_workspace_fails(self, workspace_manager):
        """Test removing tag from nonexistent workspace fails."""
        with pytest.raises(ValueError, match="not found"):
            await workspace_manager.remove_tag("nonexistent", "backend")


# ============================================================================
# Persistence Tests
# ============================================================================


class TestWorkspacePersistence:
    """Test workspace persistence."""

    @pytest.mark.asyncio
    async def test_save_and_load(self, temp_workspace_file, mock_registry):
        """Test saving and loading workspaces."""
        # Create manager and add workspaces
        manager1 = WorkspaceManager(str(temp_workspace_file), mock_registry)
        await manager1.create_workspace(
            "ws-1",
            "Workspace 1",
            description="First workspace",
            repository_ids=["repo-1"],
            tags=["backend"],
        )
        await manager1.create_workspace("ws-2", "Workspace 2")

        # Create new manager (should load existing data)
        manager2 = WorkspaceManager(str(temp_workspace_file), mock_registry)

        assert len(manager2.workspaces) == 2

        ws1 = await manager2.get_workspace("ws-1")
        assert ws1.name == "Workspace 1"
        assert ws1.description == "First workspace"
        assert ws1.repository_ids == ["repo-1"]
        assert ws1.tags == ["backend"]

        ws2 = await manager2.get_workspace("ws-2")
        assert ws2.name == "Workspace 2"

    @pytest.mark.asyncio
    async def test_load_empty_file(self, temp_workspace_file):
        """Test loading when file doesn't exist."""
        manager = WorkspaceManager(str(temp_workspace_file))

        assert len(manager.workspaces) == 0

    @pytest.mark.asyncio
    async def test_load_corrupted_file_graceful(self, temp_workspace_file):
        """Test loading corrupted file fails gracefully."""
        # Write invalid JSON
        temp_workspace_file.write_text("invalid json {{{")

        manager = WorkspaceManager(str(temp_workspace_file))

        # Should start with empty workspaces
        assert len(manager.workspaces) == 0


# ============================================================================
# Statistics Tests
# ============================================================================


class TestWorkspaceStatistics:
    """Test workspace statistics."""

    @pytest.mark.asyncio
    async def test_get_statistics(self, workspace_manager):
        """Test getting workspace statistics."""
        await workspace_manager.create_workspace(
            "ws-1",
            "Workspace 1",
            repository_ids=["repo-1", "repo-2"],
            auto_index=True,
            cross_repo_search_enabled=True,
            tags=["backend"],
        )
        await workspace_manager.create_workspace(
            "ws-2",
            "Workspace 2",
            repository_ids=["repo-2", "repo-3"],
            auto_index=False,
            cross_repo_search_enabled=True,
            tags=["frontend"],
        )
        await workspace_manager.create_workspace(
            "ws-3",
            "Workspace 3",
            repository_ids=["repo-3"],
            auto_index=True,
            cross_repo_search_enabled=False,
            tags=["backend", "api"],
        )

        stats = await workspace_manager.get_statistics()

        assert stats["total_workspaces"] == 3
        assert stats["total_unique_repositories"] == 3  # repo-1, repo-2, repo-3
        assert stats["auto_index_enabled"] == 2
        assert stats["cross_repo_search_enabled"] == 2
        assert stats["total_tags"] == 3  # backend, frontend, api
        assert stats["total_repository_memberships"] == 5  # 2 + 2 + 1
        assert stats["average_repositories_per_workspace"] == 1.67  # 5 / 3 rounded

    @pytest.mark.asyncio
    async def test_get_statistics_empty(self, workspace_manager):
        """Test getting statistics for empty manager."""
        stats = await workspace_manager.get_statistics()

        assert stats["total_workspaces"] == 0
        assert stats["total_unique_repositories"] == 0
        assert stats["auto_index_enabled"] == 0
        assert stats["cross_repo_search_enabled"] == 0
        assert stats["total_tags"] == 0
        assert stats["average_repositories_per_workspace"] == 0
