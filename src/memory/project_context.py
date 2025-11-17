"""Project context detection and management for cross-project isolation."""

import logging
import os
from datetime import datetime, timedelta, UTC
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field

try:
    from git import Repo, InvalidGitRepositoryError
    GIT_AVAILABLE = True
except ImportError:
    GIT_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning("GitPython not available - git context detection disabled")

logger = logging.getLogger(__name__)


@dataclass
class ProjectContext:
    """Represents the current project context."""

    project_name: str
    project_path: Optional[str] = None
    git_repo_root: Optional[str] = None
    git_branch: Optional[str] = None
    last_activity: datetime = field(default_factory=lambda: datetime.now(UTC))
    file_activity_count: int = 0
    is_active: bool = True


class ProjectContextDetector:
    """
    Detects and manages the user's current project context.

    Detection mechanisms:
    1. Git repository detection (primary)
    2. File activity patterns (secondary)
    3. Explicit user setting (override)

    Context-aware features:
    - Automatic project switching detection
    - Search result weighting (active project 2.0x, others 0.3x)
    - Auto-archival of inactive project memories
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize project context detector.

        Args:
            config: Optional configuration dictionary
        """
        self.config = config or {}
        self.current_context: Optional[ProjectContext] = None
        self.project_history: List[ProjectContext] = []
        self.activity_window = timedelta(minutes=30)  # Track activity in last 30 min
        self.inactivity_threshold = timedelta(days=45)  # Project inactive after 45 days

        logger.info("ProjectContextDetector initialized")

    def detect_from_git(self, directory: Optional[str] = None) -> Optional[ProjectContext]:
        """
        Detect project context from git repository.

        Args:
            directory: Directory to check (default: current working directory)

        Returns:
            ProjectContext if git repo found, None otherwise
        """
        if not GIT_AVAILABLE:
            return None

        try:
            search_path = directory or os.getcwd()
            repo = Repo(search_path, search_parent_directories=True)

            # Get repo root and current branch
            repo_root = str(repo.working_tree_dir)
            branch_name = repo.active_branch.name if repo.active_branch else "detached"

            # Use repo directory name as project name
            project_name = Path(repo_root).name

            context = ProjectContext(
                project_name=project_name,
                project_path=repo_root,
                git_repo_root=repo_root,
                git_branch=branch_name,
            )

            logger.info(
                f"Detected git project: {project_name} "
                f"(branch: {branch_name}, path: {repo_root})"
            )

            return context

        except InvalidGitRepositoryError:
            logger.debug(f"No git repository found in {directory or os.getcwd()}")
            return None
        except Exception as e:
            logger.warning(f"Error detecting git repository: {e}")
            return None

    def detect_from_file_path(self, file_path: str) -> Optional[ProjectContext]:
        """
        Detect project context from a file path.

        Args:
            file_path: Path to a file being accessed

        Returns:
            ProjectContext if project detected, None otherwise
        """
        # Try git first
        file_dir = os.path.dirname(os.path.abspath(file_path))
        context = self.detect_from_git(file_dir)

        if context:
            return context

        # Fallback: use parent directory as project name
        # Look for common project markers
        markers = [
            "package.json",
            "requirements.txt",
            "Cargo.toml",
            "pom.xml",
            "go.mod",
            ".project",
        ]

        current_dir = Path(file_dir)
        for parent in [current_dir] + list(current_dir.parents):
            for marker in markers:
                if (parent / marker).exists():
                    context = ProjectContext(
                        project_name=parent.name,
                        project_path=str(parent),
                    )
                    logger.info(
                        f"Detected project from marker: {context.project_name} "
                        f"(marker: {marker}, path: {parent})"
                    )
                    return context

        # Last resort: use directory name
        context = ProjectContext(
            project_name=current_dir.name,
            project_path=str(current_dir),
        )
        logger.debug(f"Using directory as project: {context.project_name}")
        return context

    def set_active_context(
        self,
        project_name: str,
        project_path: Optional[str] = None,
        explicit: bool = True,
    ) -> ProjectContext:
        """
        Explicitly set the active project context.

        Args:
            project_name: Name of the project
            project_path: Optional path to the project
            explicit: Whether this was explicitly set by user

        Returns:
            The new active context
        """
        # Check if switching projects
        if self.current_context and self.current_context.project_name != project_name:
            logger.info(
                f"Switching project: {self.current_context.project_name} → {project_name}"
            )
            # Archive previous context
            self.current_context.is_active = False
            self.project_history.append(self.current_context)

        # Try to detect git info if path provided
        git_context = None
        if project_path and GIT_AVAILABLE:
            git_context = self.detect_from_git(project_path)

        # Create new context
        if git_context:
            context = git_context
        else:
            context = ProjectContext(
                project_name=project_name,
                project_path=project_path,
            )

        self.current_context = context
        logger.info(f"Active project set: {project_name} (explicit: {explicit})")

        return context

    def get_active_context(self) -> Optional[ProjectContext]:
        """
        Get the currently active project context.

        Returns:
            Current ProjectContext or None
        """
        return self.current_context

    def track_file_activity(self, file_path: str) -> None:
        """
        Track file activity to infer active project.

        Args:
            file_path: Path to file being accessed
        """
        # Detect project from file
        detected = self.detect_from_file_path(file_path)

        if not detected:
            return

        # Update current context if matches
        if self.current_context and self.current_context.project_name == detected.project_name:
            self.current_context.last_activity = datetime.now(UTC)
            self.current_context.file_activity_count += 1
            logger.debug(
                f"Activity tracked for {detected.project_name} "
                f"(count: {self.current_context.file_activity_count})"
            )
        elif not self.current_context:
            # Auto-set context if none active
            self.set_active_context(
                detected.project_name,
                detected.project_path,
                explicit=False,
            )

    def get_project_weight(self, project_name: str) -> float:
        """
        Get search weight multiplier for a given project.

        Args:
            project_name: Name of the project

        Returns:
            Weight multiplier (0.3 for inactive, 2.0 for active)
        """
        if not self.current_context:
            # No active context, all projects equal
            return 1.0

        if project_name == self.current_context.project_name:
            # Active project gets 2x boost
            return 2.0
        else:
            # Other projects get penalty
            return 0.3

    def should_archive_project(self, project_name: str, last_activity: datetime) -> bool:
        """
        Check if a project should be archived due to inactivity.

        Args:
            project_name: Name of the project
            last_activity: When the project was last active

        Returns:
            True if project should be archived
        """
        if self.current_context and project_name == self.current_context.project_name:
            # Never archive current project
            return False

        # Archive if inactive for threshold period
        now = datetime.now(UTC)
        inactive_duration = now - last_activity

        return inactive_duration > self.inactivity_threshold

    def get_recent_projects(self, limit: int = 10) -> List[ProjectContext]:
        """
        Get recently active projects.

        Args:
            limit: Maximum number of projects to return

        Returns:
            List of recent ProjectContext objects
        """
        # Combine current + history
        all_projects = []
        if self.current_context:
            all_projects.append(self.current_context)
        all_projects.extend(self.project_history)

        # Sort by last activity
        sorted_projects = sorted(
            all_projects,
            key=lambda p: p.last_activity,
            reverse=True,
        )

        return sorted_projects[:limit]

    def get_context_stats(self) -> Dict[str, Any]:
        """
        Get statistics about project contexts.

        Returns:
            Dictionary with context statistics
        """
        recent = self.get_recent_projects()

        stats = {
            "current_project": self.current_context.project_name if self.current_context else None,
            "total_projects": len(set(p.project_name for p in recent)),
            "active_since": self.current_context.last_activity.isoformat() if self.current_context else None,
            "file_activity_count": self.current_context.file_activity_count if self.current_context else 0,
            "recent_projects": [
                {
                    "name": p.project_name,
                    "path": p.project_path,
                    "last_activity": p.last_activity.isoformat(),
                    "is_active": p.is_active,
                }
                for p in recent[:5]
            ],
        }

        return stats

    def clear_history(self) -> None:
        """Clear project history (for testing or reset)."""
        self.project_history.clear()
        logger.info("Project history cleared")

    def reset_context(self) -> None:
        """Reset current context (for testing or manual reset)."""
        if self.current_context:
            self.project_history.append(self.current_context)
        self.current_context = None
        logger.info("Current context reset")
