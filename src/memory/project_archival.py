"""Project archival and reactivation system for managing project lifecycles."""

import json
import logging
from datetime import datetime, UTC
from pathlib import Path
from typing import Dict, List, Any
from enum import Enum

logger = logging.getLogger(__name__)


class ProjectState(Enum):
    """Project lifecycle states."""

    ACTIVE = "active"  # Currently being used
    PAUSED = "paused"  # Temporarily inactive
    ARCHIVED = "archived"  # Long-term inactive, compressed
    DELETED = "deleted"  # Marked for permanent deletion


class ProjectArchivalManager:
    """
    Manage project lifecycle states and archival operations.

    Handles project states, activity tracking, and archival/reactivation workflows.
    Provides graceful degradation for inactive projects.
    """

    def __init__(self, state_file_path: str, inactivity_threshold_days: int = 45):
        """
        Initialize project archival manager.

        Args:
            state_file_path: Path to JSON file storing project states
            inactivity_threshold_days: Days of inactivity before suggesting archival (default 45)
        """
        self.state_file = Path(state_file_path).expanduser()
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.inactivity_threshold_days = inactivity_threshold_days

        # Project state tracking
        # {project_name: {state, last_activity, files_indexed, searches, ...}}
        self.project_states: Dict[str, Dict] = {}

        self._load_states()

    def _load_states(self) -> None:
        """Load project states from file."""
        if self.state_file.exists():
            try:
                with open(self.state_file, "r") as f:
                    data = json.load(f)
                    self.project_states = data.get("projects", {})
                    logger.info(
                        f"Loaded states for {len(self.project_states)} projects"
                    )
            except Exception as e:
                logger.error(f"Failed to load project states: {e}")
                self.project_states = {}
        else:
            self.project_states = {}
            logger.info("No existing project states file, starting fresh")

    def _save_states(self) -> None:
        """Save project states to file."""
        try:
            data = {
                "projects": self.project_states,
                "last_updated": datetime.now(UTC).isoformat(),
            }
            with open(self.state_file, "w") as f:
                json.dump(data, f, indent=2)
            logger.info(f"Saved states for {len(self.project_states)} projects")
        except Exception as e:
            logger.error(f"Failed to save project states: {e}")

    def get_project_state(self, project_name: str) -> ProjectState:
        """
        Get the current state of a project.

        Args:
            project_name: Name of the project

        Returns:
            ProjectState enum value (defaults to ACTIVE for new projects)
        """
        if project_name not in self.project_states:
            # New project defaults to ACTIVE
            self._initialize_project(project_name)
            return ProjectState.ACTIVE

        state_str = self.project_states[project_name].get("state", "active")
        return ProjectState(state_str)

    def _initialize_project(self, project_name: str) -> None:
        """Initialize a new project with default state."""
        self.project_states[project_name] = {
            "state": ProjectState.ACTIVE.value,
            "created_at": datetime.now(UTC).isoformat(),
            "last_activity": datetime.now(UTC).isoformat(),
            "files_indexed": 0,
            "searches_count": 0,
            "index_updates_count": 0,
        }
        self._save_states()
        logger.info(f"Initialized new project: {project_name}")

    def record_activity(
        self, project_name: str, activity_type: str, count: int = 1
    ) -> None:
        """
        Record activity for a project.

        Args:
            project_name: Name of the project
            activity_type: Type of activity (e.g., 'search', 'index_update')
            count: Activity count (default 1)
        """
        if project_name not in self.project_states:
            self._initialize_project(project_name)

        project = self.project_states[project_name]
        project["last_activity"] = datetime.now(UTC).isoformat()

        # Update activity counters
        if activity_type == "search":
            project["searches_count"] = project.get("searches_count", 0) + count
        elif activity_type == "index_update":
            project["index_updates_count"] = (
                project.get("index_updates_count", 0) + count
            )
        elif activity_type == "files_indexed":
            project["files_indexed"] = project.get("files_indexed", 0) + count

        self._save_states()

    def get_days_since_activity(self, project_name: str) -> float:
        """
        Get number of days since last activity for a project.

        Args:
            project_name: Name of the project

        Returns:
            Days since last activity (0.0 for new projects)
        """
        if project_name not in self.project_states:
            return 0.0

        last_activity_str = self.project_states[project_name].get("last_activity")
        if not last_activity_str:
            return 0.0

        try:
            last_activity = datetime.fromisoformat(last_activity_str)
            # Make sure both datetimes are timezone-aware
            if last_activity.tzinfo is None:
                # Assume UTC if not specified
                from datetime import timezone

                last_activity = last_activity.replace(tzinfo=timezone.utc)

            delta = datetime.now(UTC) - last_activity
            return delta.total_seconds() / 86400  # Convert to days
        except Exception as e:
            logger.warning(
                f"Failed to calculate days since activity for {project_name}: {e}"
            )
            return 0.0

    def archive_project(self, project_name: str) -> Dict[str, Any]:
        """
        Archive a project.

        Args:
            project_name: Name of the project to archive

        Returns:
            Dict with archival results
        """
        if project_name not in self.project_states:
            return {"success": False, "message": f"Project '{project_name}' not found"}

        current_state = self.get_project_state(project_name)
        if current_state == ProjectState.ARCHIVED:
            return {
                "success": False,
                "message": f"Project '{project_name}' is already archived",
            }

        # Update state
        self.project_states[project_name]["state"] = ProjectState.ARCHIVED.value
        self.project_states[project_name]["archived_at"] = datetime.now(UTC).isoformat()
        self._save_states()

        logger.info(f"Archived project: {project_name}")

        return {
            "success": True,
            "message": f"Project '{project_name}' archived successfully",
            "state": ProjectState.ARCHIVED.value,
            "archived_at": self.project_states[project_name]["archived_at"],
        }

    def reactivate_project(self, project_name: str) -> Dict[str, Any]:
        """
        Reactivate an archived project.

        Args:
            project_name: Name of the project to reactivate

        Returns:
            Dict with reactivation results
        """
        if project_name not in self.project_states:
            return {"success": False, "message": f"Project '{project_name}' not found"}

        current_state = self.get_project_state(project_name)
        if current_state == ProjectState.ACTIVE:
            return {
                "success": False,
                "message": f"Project '{project_name}' is already active",
            }

        # Update state
        self.project_states[project_name]["state"] = ProjectState.ACTIVE.value
        self.project_states[project_name]["reactivated_at"] = datetime.now(
            UTC
        ).isoformat()
        self.project_states[project_name]["last_activity"] = datetime.now(
            UTC
        ).isoformat()
        self._save_states()

        logger.info(f"Reactivated project: {project_name}")

        return {
            "success": True,
            "message": f"Project '{project_name}' reactivated successfully",
            "state": ProjectState.ACTIVE.value,
            "reactivated_at": self.project_states[project_name]["reactivated_at"],
        }

    def get_inactive_projects(self) -> List[str]:
        """
        Get list of projects that are inactive and candidates for archival.

        Returns:
            List of project names that have been inactive for more than threshold days
        """
        inactive = []
        for project_name in self.project_states:
            state = self.get_project_state(project_name)
            if state == ProjectState.ACTIVE:
                days_inactive = self.get_days_since_activity(project_name)
                if days_inactive >= self.inactivity_threshold_days:
                    inactive.append(project_name)

        return inactive

    def get_all_projects(self) -> Dict[str, Dict]:
        """
        Get all projects with their states and metadata.

        Returns:
            Dict mapping project names to their state dictionaries
        """
        return self.project_states.copy()

    def get_projects_by_state(self, state: ProjectState) -> List[str]:
        """
        Get list of projects in a specific state.

        Args:
            state: ProjectState to filter by

        Returns:
            List of project names in the specified state
        """
        return [
            name
            for name, data in self.project_states.items()
            if data.get("state") == state.value
        ]

    def get_search_weight(self, project_name: str) -> float:
        """
        Get search weight multiplier for a project based on its state.

        Args:
            project_name: Name of the project

        Returns:
            Weight multiplier (1.0 for ACTIVE, 0.5 for PAUSED, 0.1 for ARCHIVED, 0.0 for DELETED)
        """
        state = self.get_project_state(project_name)

        weights = {
            ProjectState.ACTIVE: 1.0,
            ProjectState.PAUSED: 0.5,
            ProjectState.ARCHIVED: 0.1,
            ProjectState.DELETED: 0.0,
        }

        return weights.get(state, 1.0)
