"""Cross-project search consent management for privacy control."""

import json
import logging
from pathlib import Path
from typing import Set, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class CrossProjectConsent:
    """
    Manage user consent for cross-project code search.

    Implements opt-in privacy model where projects must be explicitly
    allowed for cross-project search. Provides granular control over
    which projects can be searched together.
    """

    def __init__(self, consent_file_path: str):
        """
        Initialize consent manager.

        Args:
            consent_file_path: Path to JSON file storing consent data
        """
        self.consent_file = Path(consent_file_path).expanduser()
        self.consent_file.parent.mkdir(parents=True, exist_ok=True)
        self._load_consent()

    def _load_consent(self) -> None:
        """Load consent data from file."""
        if self.consent_file.exists():
            try:
                with open(self.consent_file, 'r') as f:
                    data = json.load(f)
                    self.opted_in_projects: Set[str] = set(data.get("opted_in_projects", []))
                    logger.info(f"Loaded consent for {len(self.opted_in_projects)} projects")
            except Exception as e:
                logger.error(f"Failed to load consent file: {e}")
                self.opted_in_projects = set()
        else:
            self.opted_in_projects = set()
            logger.info("No existing consent file, starting with empty consent")

    def _save_consent(self) -> None:
        """Save consent data to file."""
        try:
            data = {
                "opted_in_projects": list(self.opted_in_projects),
                "last_updated": datetime.now().isoformat(),
            }
            with open(self.consent_file, 'w') as f:
                json.dump(data, f, indent=2)
            logger.info(f"Saved consent for {len(self.opted_in_projects)} projects")
        except Exception as e:
            logger.error(f"Failed to save consent file: {e}")

    def is_project_opted_in(self, project_name: str) -> bool:
        """
        Check if a project is opted in for cross-project search.

        Args:
            project_name: Project name to check

        Returns:
            True if project is opted in, False otherwise
        """
        return project_name in self.opted_in_projects

    def opt_in_project(self, project_name: str) -> None:
        """
        Opt in a project for cross-project search.

        Args:
            project_name: Project name to opt in
        """
        self.opted_in_projects.add(project_name)
        self._save_consent()
        logger.info(f"Opted in project: {project_name}")

    def opt_out_project(self, project_name: str) -> None:
        """
        Opt out a project from cross-project search.

        Args:
            project_name: Project name to opt out
        """
        if project_name in self.opted_in_projects:
            self.opted_in_projects.remove(project_name)
            self._save_consent()
            logger.info(f"Opted out project: {project_name}")

    def get_opted_in_projects(self) -> Set[str]:
        """
        Get all projects opted in for cross-project search.

        Returns:
            Set of project names that are opted in
        """
        return self.opted_in_projects.copy()

    def get_searchable_projects(
        self,
        current_project: Optional[str],
        search_all: bool = False
    ) -> Set[str]:
        """
        Get the set of projects that can be searched.

        Args:
            current_project: Current project name (always searchable)
            search_all: If True, return all opted-in projects; if False, only current

        Returns:
            Set of project names that can be searched
        """
        if not search_all:
            # Only search current project
            return {current_project} if current_project else set()

        # Search all opted-in projects + current project
        searchable = self.opted_in_projects.copy()
        if current_project:
            searchable.add(current_project)

        return searchable

    def clear_all_consent(self) -> None:
        """Clear all consent data."""
        self.opted_in_projects.clear()
        self._save_consent()
        logger.info("Cleared all project consent")
