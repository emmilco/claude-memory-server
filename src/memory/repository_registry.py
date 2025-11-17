"""Repository registry for multi-repository support."""

import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, UTC
from enum import Enum
from pathlib import Path
from typing import List, Optional, Dict, Any, Set
from uuid import uuid4

logger = logging.getLogger(__name__)


class RepositoryType(str, Enum):
    """Type of repository architecture."""

    MONOREPO = "monorepo"  # Single repo with multiple projects
    MULTI_REPO = "multi_repo"  # Part of multi-repo architecture
    STANDALONE = "standalone"  # Independent repository


class RepositoryStatus(str, Enum):
    """Status of repository indexing."""

    INDEXED = "indexed"  # Fully indexed and up-to-date
    INDEXING = "indexing"  # Currently being indexed
    STALE = "stale"  # Indexed but needs update
    ERROR = "error"  # Indexing failed
    NOT_INDEXED = "not_indexed"  # Registered but not indexed


@dataclass
class Repository:
    """Represents a registered repository."""

    id: str  # UUID
    name: str  # User-friendly name (default: directory name)
    path: str  # Absolute path to repository
    git_url: Optional[str] = None  # Remote URL if git repo
    repo_type: RepositoryType = RepositoryType.STANDALONE
    status: RepositoryStatus = RepositoryStatus.NOT_INDEXED

    # Metadata
    indexed_at: Optional[datetime] = None
    last_updated: Optional[datetime] = None
    file_count: int = 0
    unit_count: int = 0

    # Organization
    workspace_ids: List[str] = field(default_factory=list)  # Workspaces this repo belongs to
    tags: List[str] = field(default_factory=list)  # User-defined tags

    # Relationships
    depends_on: List[str] = field(default_factory=list)  # Repository IDs this depends on
    depended_by: List[str] = field(default_factory=list)  # Repository IDs that depend on this

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        # Convert enums to strings
        data['repo_type'] = self.repo_type.value
        data['status'] = self.status.value
        # Convert datetimes to ISO format
        if self.indexed_at:
            data['indexed_at'] = self.indexed_at.isoformat()
        if self.last_updated:
            data['last_updated'] = self.last_updated.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Repository':
        """Create Repository from dictionary."""
        # Convert enum strings back to enums
        if 'repo_type' in data and isinstance(data['repo_type'], str):
            data['repo_type'] = RepositoryType(data['repo_type'])
        if 'status' in data and isinstance(data['status'], str):
            data['status'] = RepositoryStatus(data['status'])

        # Convert ISO datetime strings back to datetime objects
        if 'indexed_at' in data and isinstance(data['indexed_at'], str):
            data['indexed_at'] = datetime.fromisoformat(data['indexed_at'])
        if 'last_updated' in data and isinstance(data['last_updated'], str):
            data['last_updated'] = datetime.fromisoformat(data['last_updated'])

        return cls(**data)


class RepositoryRegistry:
    """
    Manages the registry of all repositories.

    Provides centralized tracking of indexed repositories with metadata,
    relationships, and organization capabilities.
    """

    def __init__(self, storage_path: str):
        """
        Initialize repository registry.

        Args:
            storage_path: Path to JSON file for storing registry data
        """
        self.storage_path = Path(storage_path).expanduser()
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self.repositories: Dict[str, Repository] = {}
        self._load()

        logger.info(f"RepositoryRegistry initialized with {len(self.repositories)} repositories")

    def _load(self) -> None:
        """Load registry data from JSON file."""
        if self.storage_path.exists():
            try:
                with open(self.storage_path, 'r') as f:
                    data = json.load(f)
                    repos_data = data.get('repositories', {})

                    for repo_id, repo_data in repos_data.items():
                        try:
                            self.repositories[repo_id] = Repository.from_dict(repo_data)
                        except Exception as e:
                            logger.error(f"Failed to load repository {repo_id}: {e}")

                logger.info(f"Loaded {len(self.repositories)} repositories from {self.storage_path}")
            except Exception as e:
                logger.error(f"Failed to load registry file: {e}")
                self.repositories = {}
        else:
            self.repositories = {}
            logger.info("No existing registry file, starting with empty registry")

    def _save(self) -> None:
        """Save registry data to JSON file."""
        try:
            data = {
                'repositories': {
                    repo_id: repo.to_dict()
                    for repo_id, repo in self.repositories.items()
                },
                'last_updated': datetime.now(UTC).isoformat(),
            }

            with open(self.storage_path, 'w') as f:
                json.dump(data, f, indent=2)

            logger.info(f"Saved {len(self.repositories)} repositories to {self.storage_path}")
        except Exception as e:
            logger.error(f"Failed to save registry file: {e}")
            raise

    async def register_repository(
        self,
        path: str,
        name: Optional[str] = None,
        repo_type: RepositoryType = RepositoryType.STANDALONE,
        git_url: Optional[str] = None,
        tags: Optional[List[str]] = None
    ) -> str:
        """
        Register a new repository.

        Args:
            path: Absolute path to repository
            name: User-friendly name (defaults to directory name)
            repo_type: Type of repository architecture
            git_url: Git remote URL if applicable
            tags: Initial tags for organization

        Returns:
            Repository ID (UUID)

        Raises:
            ValueError: If repository already registered at this path
        """
        # Normalize path
        repo_path = str(Path(path).resolve())

        # Check if already registered
        existing = await self.get_repository_by_path(repo_path)
        if existing:
            raise ValueError(
                f"Repository already registered at {repo_path} "
                f"(ID: {existing.id}, Name: {existing.name})"
            )

        # Generate ID and default name
        repo_id = str(uuid4())
        repo_name = name or Path(repo_path).name

        # Create repository
        repository = Repository(
            id=repo_id,
            name=repo_name,
            path=repo_path,
            git_url=git_url,
            repo_type=repo_type,
            tags=tags or [],
        )

        self.repositories[repo_id] = repository
        self._save()

        logger.info(
            f"Registered repository: {repo_name} (ID: {repo_id}, Path: {repo_path})"
        )

        return repo_id

    async def unregister_repository(self, repo_id: str) -> None:
        """
        Unregister a repository.

        Note: This does not delete indexed code, only removes from registry.

        Args:
            repo_id: Repository ID to unregister

        Raises:
            KeyError: If repository not found
        """
        if repo_id not in self.repositories:
            raise KeyError(f"Repository not found: {repo_id}")

        repo = self.repositories[repo_id]

        # Remove this repo from any dependents' depends_on lists
        for other_repo in self.repositories.values():
            if repo_id in other_repo.depends_on:
                other_repo.depends_on.remove(repo_id)

        # Remove from registry
        del self.repositories[repo_id]
        self._save()

        logger.info(f"Unregistered repository: {repo.name} (ID: {repo_id})")

    async def get_repository(self, repo_id: str) -> Optional[Repository]:
        """
        Get repository by ID.

        Args:
            repo_id: Repository ID

        Returns:
            Repository if found, None otherwise
        """
        return self.repositories.get(repo_id)

    async def get_repository_by_path(self, path: str) -> Optional[Repository]:
        """
        Get repository by filesystem path.

        Args:
            path: Absolute or relative path to repository

        Returns:
            Repository if found, None otherwise
        """
        # Normalize path for comparison
        search_path = str(Path(path).resolve())

        for repo in self.repositories.values():
            if repo.path == search_path:
                return repo

        return None

    async def get_repository_by_name(self, name: str) -> Optional[Repository]:
        """
        Get repository by name.

        Args:
            name: Repository name

        Returns:
            Repository if found, None otherwise (returns first match if multiple)
        """
        for repo in self.repositories.values():
            if repo.name == name:
                return repo

        return None

    async def list_repositories(
        self,
        status: Optional[RepositoryStatus] = None,
        workspace_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
        repo_type: Optional[RepositoryType] = None
    ) -> List[Repository]:
        """
        List repositories with optional filtering.

        Args:
            status: Filter by repository status
            workspace_id: Filter by workspace membership
            tags: Filter by tags (returns repos with ANY of these tags)
            repo_type: Filter by repository type

        Returns:
            List of repositories matching filters
        """
        results = list(self.repositories.values())

        # Filter by status
        if status is not None:
            results = [r for r in results if r.status == status]

        # Filter by workspace
        if workspace_id is not None:
            results = [r for r in results if workspace_id in r.workspace_ids]

        # Filter by tags (repo must have at least one of the specified tags)
        if tags:
            tag_set = set(tags)
            results = [r for r in results if any(t in tag_set for t in r.tags)]

        # Filter by repo type
        if repo_type is not None:
            results = [r for r in results if r.repo_type == repo_type]

        return results

    async def update_repository(
        self,
        repo_id: str,
        updates: Dict[str, Any]
    ) -> None:
        """
        Update repository metadata.

        Args:
            repo_id: Repository ID
            updates: Dictionary of fields to update

        Raises:
            KeyError: If repository not found
            ValueError: If invalid field or value
        """
        if repo_id not in self.repositories:
            raise KeyError(f"Repository not found: {repo_id}")

        repo = self.repositories[repo_id]

        # Validate and apply updates
        valid_fields = {
            'name', 'git_url', 'repo_type', 'status', 'indexed_at',
            'last_updated', 'file_count', 'unit_count', 'tags'
        }

        for field, value in updates.items():
            if field not in valid_fields:
                raise ValueError(f"Invalid field: {field}")

            # Convert enum strings to enums
            if field == 'repo_type' and isinstance(value, str):
                value = RepositoryType(value)
            elif field == 'status' and isinstance(value, str):
                value = RepositoryStatus(value)
            elif field in ('indexed_at', 'last_updated') and isinstance(value, str):
                value = datetime.fromisoformat(value)

            setattr(repo, field, value)

        # Update last_updated timestamp
        repo.last_updated = datetime.now(UTC)

        self._save()

        logger.info(f"Updated repository {repo_id}: {list(updates.keys())}")

    async def add_dependency(self, repo_id: str, depends_on_id: str) -> None:
        """
        Track dependency relationship between repositories.

        Args:
            repo_id: Repository that has the dependency
            depends_on_id: Repository that is depended upon

        Raises:
            KeyError: If either repository not found
            ValueError: If dependency would create a cycle
        """
        if repo_id not in self.repositories:
            raise KeyError(f"Repository not found: {repo_id}")
        if depends_on_id not in self.repositories:
            raise KeyError(f"Dependency repository not found: {depends_on_id}")

        if repo_id == depends_on_id:
            raise ValueError("Repository cannot depend on itself")

        # Check for cycles
        if await self._would_create_cycle(repo_id, depends_on_id):
            raise ValueError(
                f"Adding dependency would create a cycle: "
                f"{repo_id} -> {depends_on_id}"
            )

        repo = self.repositories[repo_id]
        dep_repo = self.repositories[depends_on_id]

        # Add bidirectional relationship
        if depends_on_id not in repo.depends_on:
            repo.depends_on.append(depends_on_id)

        if repo_id not in dep_repo.depended_by:
            dep_repo.depended_by.append(repo_id)

        self._save()

        logger.info(
            f"Added dependency: {repo.name} depends on {dep_repo.name}"
        )

    async def remove_dependency(self, repo_id: str, depends_on_id: str) -> None:
        """
        Remove dependency relationship between repositories.

        Args:
            repo_id: Repository that has the dependency
            depends_on_id: Repository that is depended upon

        Raises:
            KeyError: If either repository not found
        """
        if repo_id not in self.repositories:
            raise KeyError(f"Repository not found: {repo_id}")
        if depends_on_id not in self.repositories:
            raise KeyError(f"Dependency repository not found: {depends_on_id}")

        repo = self.repositories[repo_id]
        dep_repo = self.repositories[depends_on_id]

        # Remove bidirectional relationship
        if depends_on_id in repo.depends_on:
            repo.depends_on.remove(depends_on_id)

        if repo_id in dep_repo.depended_by:
            dep_repo.depended_by.remove(repo_id)

        self._save()

        logger.info(
            f"Removed dependency: {repo.name} no longer depends on {dep_repo.name}"
        )

    async def get_dependencies(
        self,
        repo_id: str,
        max_depth: int = 3,
        _visited: Optional[Set[str]] = None
    ) -> Dict[str, List[str]]:
        """
        Get all dependencies of a repository (transitive).

        Args:
            repo_id: Repository ID
            max_depth: Maximum depth to traverse (prevents infinite loops)
            _visited: Internal parameter for cycle detection

        Returns:
            Dictionary mapping depth level to list of repository IDs
            Example: {0: [repo_id], 1: [direct_deps], 2: [transitive_deps]}

        Raises:
            KeyError: If repository not found
        """
        if repo_id not in self.repositories:
            raise KeyError(f"Repository not found: {repo_id}")

        if _visited is None:
            _visited = set()

        if repo_id in _visited or max_depth < 0:
            return {}

        _visited.add(repo_id)

        repo = self.repositories[repo_id]
        result: Dict[str, List[str]] = {0: [repo_id]}

        if max_depth == 0:
            return result

        # Get direct dependencies
        direct_deps = repo.depends_on
        if direct_deps:
            result[1] = direct_deps

            # Get transitive dependencies
            if max_depth > 1:
                for dep_id in direct_deps:
                    if dep_id not in _visited:
                        transitive = await self.get_dependencies(
                            dep_id,
                            max_depth - 1,
                            _visited
                        )
                        # Shift depth levels and merge
                        for depth, repos in transitive.items():
                            new_depth = depth + 1
                            if new_depth not in result:
                                result[new_depth] = []
                            result[new_depth].extend(repos)

        return result

    async def _would_create_cycle(
        self,
        repo_id: str,
        new_dependency_id: str
    ) -> bool:
        """
        Check if adding a dependency would create a cycle.

        Args:
            repo_id: Repository to add dependency to
            new_dependency_id: Proposed dependency

        Returns:
            True if cycle would be created, False otherwise
        """
        # If new_dependency already depends on repo_id (directly or transitively),
        # adding repo_id -> new_dependency would create a cycle
        try:
            deps = await self.get_dependencies(new_dependency_id, max_depth=10)
            # Flatten all dependencies
            all_deps = set()
            for level_deps in deps.values():
                all_deps.update(level_deps)

            return repo_id in all_deps
        except KeyError:
            return False

    async def add_tag(self, repo_id: str, tag: str) -> None:
        """
        Add a tag to a repository.

        Args:
            repo_id: Repository ID
            tag: Tag to add

        Raises:
            KeyError: If repository not found
        """
        if repo_id not in self.repositories:
            raise KeyError(f"Repository not found: {repo_id}")

        repo = self.repositories[repo_id]
        if tag not in repo.tags:
            repo.tags.append(tag)
            self._save()
            logger.info(f"Added tag '{tag}' to repository {repo.name}")

    async def remove_tag(self, repo_id: str, tag: str) -> None:
        """
        Remove a tag from a repository.

        Args:
            repo_id: Repository ID
            tag: Tag to remove

        Raises:
            KeyError: If repository not found
        """
        if repo_id not in self.repositories:
            raise KeyError(f"Repository not found: {repo_id}")

        repo = self.repositories[repo_id]
        if tag in repo.tags:
            repo.tags.remove(tag)
            self._save()
            logger.info(f"Removed tag '{tag}' from repository {repo.name}")

    async def add_to_workspace(self, repo_id: str, workspace_id: str) -> None:
        """
        Add repository to a workspace.

        Args:
            repo_id: Repository ID
            workspace_id: Workspace ID

        Raises:
            KeyError: If repository not found
        """
        if repo_id not in self.repositories:
            raise KeyError(f"Repository not found: {repo_id}")

        repo = self.repositories[repo_id]
        if workspace_id not in repo.workspace_ids:
            repo.workspace_ids.append(workspace_id)
            self._save()
            logger.info(f"Added repository {repo.name} to workspace {workspace_id}")

    async def remove_from_workspace(self, repo_id: str, workspace_id: str) -> None:
        """
        Remove repository from a workspace.

        Args:
            repo_id: Repository ID
            workspace_id: Workspace ID

        Raises:
            KeyError: If repository not found
        """
        if repo_id not in self.repositories:
            raise KeyError(f"Repository not found: {repo_id}")

        repo = self.repositories[repo_id]
        if workspace_id in repo.workspace_ids:
            repo.workspace_ids.remove(workspace_id)
            self._save()
            logger.info(f"Removed repository {repo.name} from workspace {workspace_id}")

    async def get_statistics(self) -> Dict[str, Any]:
        """
        Get registry statistics.

        Returns:
            Dictionary with statistics about registered repositories
        """
        total = len(self.repositories)
        by_status = {}
        by_type = {}
        total_files = 0
        total_units = 0

        for repo in self.repositories.values():
            # Count by status
            status_key = repo.status.value
            by_status[status_key] = by_status.get(status_key, 0) + 1

            # Count by type
            type_key = repo.repo_type.value
            by_type[type_key] = by_type.get(type_key, 0) + 1

            # Sum files and units
            total_files += repo.file_count
            total_units += repo.unit_count

        return {
            'total_repositories': total,
            'by_status': by_status,
            'by_type': by_type,
            'total_files_indexed': total_files,
            'total_units_indexed': total_units,
            'storage_path': str(self.storage_path),
        }
