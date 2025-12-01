"""Workspace management for grouping and organizing repositories.

A workspace represents a logical collection of related repositories that should be
indexed and searched together. This enables:
- Multi-repository projects (monorepos split into services)
- Development contexts (e.g., "backend-services", "frontend-apps")
- Team-based organization
- Project-based grouping
"""

import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, UTC
from pathlib import Path
from typing import Optional, List, Dict, Any

from src.memory.repository_registry import RepositoryRegistry

logger = logging.getLogger(__name__)


@dataclass
class Workspace:
    """Represents a workspace - a logical collection of repositories.

    Attributes:
        id: Unique workspace identifier (UUID)
        name: User-friendly workspace name
        description: Optional description of workspace purpose
        repository_ids: List of repository IDs in this workspace
        auto_index: Whether to automatically index new files in workspace repos
        cross_repo_search_enabled: Whether cross-repo search is enabled for this workspace
        created_at: When workspace was created
        updated_at: When workspace was last modified
        tags: Optional tags for categorization
        settings: Optional workspace-specific settings
    """

    id: str
    name: str
    description: Optional[str] = None
    repository_ids: List[str] = field(default_factory=list)
    auto_index: bool = True
    cross_repo_search_enabled: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    tags: List[str] = field(default_factory=list)
    settings: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert workspace to dictionary for JSON serialization.

        Returns:
            Dictionary representation with datetime objects converted to ISO format
        """
        data = asdict(self)
        # Convert datetime objects to ISO format strings
        if isinstance(self.created_at, datetime):
            data['created_at'] = self.created_at.isoformat()
        if isinstance(self.updated_at, datetime):
            data['updated_at'] = self.updated_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Workspace':
        """Create Workspace from dictionary.

        Args:
            data: Dictionary representation of workspace

        Returns:
            Workspace instance
        """
        # Convert ISO format strings back to datetime objects
        if isinstance(data.get('created_at'), str):
            data['created_at'] = datetime.fromisoformat(data['created_at'])
        if isinstance(data.get('updated_at'), str):
            data['updated_at'] = datetime.fromisoformat(data['updated_at'])

        return cls(**data)


class WorkspaceManager:
    """Manages workspaces and their repository memberships.

    The WorkspaceManager provides:
    - Workspace CRUD operations
    - Repository membership management
    - Multi-workspace support (repositories can belong to multiple workspaces)
    - Workspace-based filtering and organization
    - Integration with RepositoryRegistry for consistency

    Storage:
        Uses JSON file at ~/.claude-rag/workspaces.json for persistence

    Thread Safety:
        Not thread-safe. Use external locking if needed.
    """

    def __init__(
        self,
        storage_path: str,
        repository_registry: Optional[RepositoryRegistry] = None
    ):
        """Initialize workspace manager.

        Args:
            storage_path: Path to JSON file for workspace storage
            repository_registry: Optional repository registry for validation
        """
        self.storage_path = Path(storage_path).expanduser()
        self.repository_registry = repository_registry
        self.workspaces: Dict[str, Workspace] = {}

        # Ensure parent directory exists
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)

        # Load existing workspaces
        self._load()

        logger.info(f"WorkspaceManager initialized with {len(self.workspaces)} workspaces")

    # ============================================================================
    # CRUD Operations
    # ============================================================================

    async def create_workspace(
        self,
        workspace_id: str,
        name: str,
        description: Optional[str] = None,
        repository_ids: Optional[List[str]] = None,
        auto_index: bool = True,
        cross_repo_search_enabled: bool = True,
        tags: Optional[List[str]] = None,
        settings: Optional[Dict[str, Any]] = None,
    ) -> Workspace:
        """Create a new workspace.

        Args:
            workspace_id: Unique workspace identifier (typically UUID)
            name: User-friendly workspace name
            description: Optional description
            repository_ids: Initial list of repository IDs
            auto_index: Whether to auto-index workspace repos
            cross_repo_search_enabled: Whether to enable cross-repo search
            tags: Optional tags for categorization
            settings: Optional workspace-specific settings

        Returns:
            Created Workspace instance

        Raises:
            ValueError: If workspace_id already exists or name is empty
        """
        if workspace_id in self.workspaces:
            raise ValueError(f"Workspace with ID '{workspace_id}' already exists")

        if not name or not name.strip():
            raise ValueError("Workspace name cannot be empty")

        # Validate repository IDs if registry is available
        repo_ids = repository_ids or []
        if self.repository_registry and repo_ids:
            for repo_id in repo_ids:
                repo = await self.repository_registry.get_repository(repo_id)
                if not repo:
                    raise ValueError(f"Repository '{repo_id}' not found in registry")

        workspace = Workspace(
            id=workspace_id,
            name=name,
            description=description,
            repository_ids=repo_ids.copy(),
            auto_index=auto_index,
            cross_repo_search_enabled=cross_repo_search_enabled,
            tags=tags.copy() if tags else [],
            settings=settings.copy() if settings else {},
        )

        self.workspaces[workspace_id] = workspace
        self._save()

        # Update repository registry if available
        if self.repository_registry:
            for repo_id in repo_ids:
                await self.repository_registry.add_to_workspace(repo_id, workspace_id)

        logger.info(f"Created workspace '{name}' ({workspace_id}) with {len(repo_ids)} repositories")

        return workspace

    async def delete_workspace(self, workspace_id: str) -> None:
        """Delete a workspace.

        Args:
            workspace_id: ID of workspace to delete

        Raises:
            ValueError: If workspace doesn't exist
        """
        if workspace_id not in self.workspaces:
            raise ValueError(f"Workspace '{workspace_id}' not found")

        workspace = self.workspaces[workspace_id]

        # Remove workspace from repository registry if available
        if self.repository_registry:
            for repo_id in list(workspace.repository_ids):
                try:
                    await self.repository_registry.remove_from_workspace(repo_id, workspace_id)
                except ValueError:
                    # Repository might have been deleted
                    logger.warning(f"Repository '{repo_id}' not found when removing workspace")

        del self.workspaces[workspace_id]
        self._save()

        logger.info(f"Deleted workspace '{workspace.name}' ({workspace_id})")

    async def get_workspace(self, workspace_id: str) -> Optional[Workspace]:
        """Get workspace by ID.

        Args:
            workspace_id: Workspace identifier

        Returns:
            Workspace if found, None otherwise
        """
        return self.workspaces.get(workspace_id)

    async def get_workspace_by_name(self, name: str) -> Optional[Workspace]:
        """Get workspace by name.

        Args:
            name: Workspace name

        Returns:
            Workspace if found, None otherwise
        """
        for workspace in self.workspaces.values():
            if workspace.name == name:
                return workspace
        return None

    async def list_workspaces(
        self,
        tags: Optional[List[str]] = None,
        has_repo: Optional[str] = None,
    ) -> List[Workspace]:
        """List workspaces with optional filtering.

        Args:
            tags: Filter by tags (workspace must have ALL specified tags)
            has_repo: Filter to workspaces containing this repository ID

        Returns:
            List of matching workspaces
        """
        workspaces = list(self.workspaces.values())

        # Filter by tags
        if tags:
            workspaces = [
                ws for ws in workspaces
                if all(tag in ws.tags for tag in tags)
            ]

        # Filter by repository membership
        if has_repo:
            workspaces = [
                ws for ws in workspaces
                if has_repo in ws.repository_ids
            ]

        return workspaces

    async def update_workspace(
        self,
        workspace_id: str,
        updates: Dict[str, Any],
    ) -> None:
        """Update workspace metadata.

        Args:
            workspace_id: ID of workspace to update
            updates: Dictionary of fields to update

        Raises:
            ValueError: If workspace doesn't exist or invalid field
        """
        if workspace_id not in self.workspaces:
            raise ValueError(f"Workspace '{workspace_id}' not found")

        workspace = self.workspaces[workspace_id]

        # Only allow updating certain fields
        allowed_fields = {
            'name', 'description', 'auto_index',
            'cross_repo_search_enabled', 'settings'
        }

        for key, value in updates.items():
            if key not in allowed_fields:
                raise ValueError(
                    f"Cannot update field '{key}'. "
                    f"Use add_repository/remove_repository for repository management."
                )
            setattr(workspace, key, value)

        # Update timestamp
        workspace.updated_at = datetime.now(UTC)

        self._save()
        logger.info(f"Updated workspace '{workspace.name}' ({workspace_id})")

    # ============================================================================
    # Repository Management
    # ============================================================================

    async def add_repository(
        self,
        workspace_id: str,
        repo_id: str,
    ) -> None:
        """Add repository to workspace.

        Args:
            workspace_id: Workspace to add to
            repo_id: Repository to add

        Raises:
            ValueError: If workspace or repository doesn't exist
        """
        if workspace_id not in self.workspaces:
            raise ValueError(f"Workspace '{workspace_id}' not found")

        workspace = self.workspaces[workspace_id]

        # Validate repository exists if registry available
        if self.repository_registry:
            repo = await self.repository_registry.get_repository(repo_id)
            if not repo:
                raise ValueError(f"Repository '{repo_id}' not found in registry")

        # Add if not already present (idempotent)
        if repo_id not in workspace.repository_ids:
            workspace.repository_ids.append(repo_id)
            workspace.updated_at = datetime.now(UTC)
            self._save()

            # Update repository registry
            if self.repository_registry:
                await self.repository_registry.add_to_workspace(repo_id, workspace_id)

            logger.info(f"Added repository '{repo_id}' to workspace '{workspace.name}'")
        else:
            logger.debug(f"Repository '{repo_id}' already in workspace '{workspace.name}'")

    async def remove_repository(
        self,
        workspace_id: str,
        repo_id: str,
    ) -> None:
        """Remove repository from workspace.

        Args:
            workspace_id: Workspace to remove from
            repo_id: Repository to remove

        Raises:
            ValueError: If workspace doesn't exist
        """
        if workspace_id not in self.workspaces:
            raise ValueError(f"Workspace '{workspace_id}' not found")

        workspace = self.workspaces[workspace_id]

        if repo_id in workspace.repository_ids:
            workspace.repository_ids.remove(repo_id)
            workspace.updated_at = datetime.now(UTC)
            self._save()

            # Update repository registry
            if self.repository_registry:
                try:
                    await self.repository_registry.remove_from_workspace(repo_id, workspace_id)
                except ValueError:
                    # Repository might have been deleted
                    logger.warning(f"Repository '{repo_id}' not found in registry")

            logger.info(f"Removed repository '{repo_id}' from workspace '{workspace.name}'")
        else:
            logger.debug(f"Repository '{repo_id}' not in workspace '{workspace.name}'")

    async def get_workspace_repositories(
        self,
        workspace_id: str,
    ) -> List[str]:
        """Get list of repository IDs in a workspace.

        Args:
            workspace_id: Workspace identifier

        Returns:
            List of repository IDs

        Raises:
            ValueError: If workspace doesn't exist
        """
        if workspace_id not in self.workspaces:
            raise ValueError(f"Workspace '{workspace_id}' not found")

        return self.workspaces[workspace_id].repository_ids.copy()

    # ============================================================================
    # Tag Management
    # ============================================================================

    async def add_tag(self, workspace_id: str, tag: str) -> None:
        """Add tag to workspace.

        Args:
            workspace_id: Workspace to tag
            tag: Tag to add

        Raises:
            ValueError: If workspace doesn't exist
        """
        if workspace_id not in self.workspaces:
            raise ValueError(f"Workspace '{workspace_id}' not found")

        workspace = self.workspaces[workspace_id]

        if tag not in workspace.tags:
            workspace.tags.append(tag)
            workspace.updated_at = datetime.now(UTC)
            self._save()
            logger.info(f"Added tag '{tag}' to workspace '{workspace.name}'")

    async def remove_tag(self, workspace_id: str, tag: str) -> None:
        """Remove tag from workspace.

        Args:
            workspace_id: Workspace to remove tag from
            tag: Tag to remove

        Raises:
            ValueError: If workspace doesn't exist
        """
        if workspace_id not in self.workspaces:
            raise ValueError(f"Workspace '{workspace_id}' not found")

        workspace = self.workspaces[workspace_id]

        if tag in workspace.tags:
            workspace.tags.remove(tag)
            workspace.updated_at = datetime.now(UTC)
            self._save()
            logger.info(f"Removed tag '{tag}' from workspace '{workspace.name}'")

    # ============================================================================
    # Persistence
    # ============================================================================

    def _load(self) -> None:
        """Load workspaces from JSON file."""
        if not self.storage_path.exists():
            logger.debug(f"No workspace file found at {self.storage_path}, starting fresh")
            return

        try:
            with open(self.storage_path, 'r') as f:
                data = json.load(f)
                self.workspaces = {
                    ws_id: Workspace.from_dict(ws_data)
                    for ws_id, ws_data in data.items()
                }
            logger.info(f"Loaded {len(self.workspaces)} workspaces from {self.storage_path}")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to load workspaces from {self.storage_path}: {e}")
            logger.warning("Starting with empty workspace registry")
            self.workspaces = {}
        except Exception as e:
            logger.error(f"Unexpected error loading workspaces: {e}")
            self.workspaces = {}

    def _save(self) -> None:
        """Save workspaces to JSON file."""
        try:
            data = {
                ws_id: workspace.to_dict()
                for ws_id, workspace in self.workspaces.items()
            }

            # Write atomically via temp file
            temp_path = self.storage_path.with_suffix('.tmp')
            with open(temp_path, 'w') as f:
                json.dump(data, f, indent=2)
            temp_path.replace(self.storage_path)

            logger.debug(f"Saved {len(self.workspaces)} workspaces to {self.storage_path}")
        except Exception as e:
            logger.error(f"Failed to save workspaces to {self.storage_path}: {e}")
            raise

    # ============================================================================
    # Statistics
    # ============================================================================

    async def get_statistics(self) -> Dict[str, Any]:
        """Get workspace statistics.

        Returns:
            Dictionary with workspace statistics
        """
        total_workspaces = len(self.workspaces)

        # Count repositories across all workspaces
        all_repo_ids = set()
        for workspace in self.workspaces.values():
            all_repo_ids.update(workspace.repository_ids)

        # Count workspaces by settings
        auto_index_count = sum(
            1 for ws in self.workspaces.values() if ws.auto_index
        )
        cross_repo_enabled_count = sum(
            1 for ws in self.workspaces.values() if ws.cross_repo_search_enabled
        )

        # Get all unique tags
        all_tags = set()
        for workspace in self.workspaces.values():
            all_tags.update(workspace.tags)

        # Calculate average repositories per workspace
        total_repo_memberships = sum(
            len(ws.repository_ids) for ws in self.workspaces.values()
        )
        avg_repos_per_workspace = (
            total_repo_memberships / total_workspaces if total_workspaces > 0 else 0
        )

        return {
            'total_workspaces': total_workspaces,
            'total_unique_repositories': len(all_repo_ids),
            'auto_index_enabled': auto_index_count,
            'cross_repo_search_enabled': cross_repo_enabled_count,
            'total_tags': len(all_tags),
            'average_repositories_per_workspace': round(avg_repos_per_workspace, 2),
            'total_repository_memberships': total_repo_memberships,
        }
