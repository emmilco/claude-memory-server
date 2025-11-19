"""Cross-project search consent management.

This module provides privacy controls for cross-project search functionality.
Users can explicitly opt-in or opt-out projects from being included in
cross-project searches.
"""

import sqlite3
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime, UTC
import logging

logger = logging.getLogger(__name__)


class CrossProjectConsentManager:
    """
    Manages cross-project search consent preferences.

    By default, all projects are opted-in for cross-project search.
    Users can explicitly opt-out specific projects for privacy.

    Consent preferences are stored in a SQLite database at:
    ~/.claude-rag/consent.db
    """

    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize consent manager.

        Args:
            db_path: Path to SQLite database file (defaults to ~/.claude-rag/consent.db)
        """
        if db_path is None:
            db_path = Path.home() / ".claude-rag" / "consent.db"

        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        """Initialize database schema."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS project_consent (
                project_name TEXT PRIMARY KEY,
                opted_in BOOLEAN NOT NULL DEFAULT 1,
                opted_in_at TIMESTAMP,
                opted_out_at TIMESTAMP,
                updated_at TIMESTAMP NOT NULL
            )
        """)

        conn.commit()
        conn.close()

        logger.debug(f"Initialized consent database at {self.db_path}")

    def opt_in(self, project_name: str) -> Dict[str, Any]:
        """
        Opt-in a project for cross-project search.

        Args:
            project_name: Project to opt-in

        Returns:
            Dict with status and timestamps
        """
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        now = datetime.now(UTC).isoformat()

        # Check if record exists
        cursor.execute("""
            SELECT opted_in FROM project_consent
            WHERE project_name = ?
        """, (project_name,))

        existing = cursor.fetchone()

        if existing:
            # Update existing record
            cursor.execute("""
                UPDATE project_consent
                SET opted_in = 1,
                    opted_in_at = ?,
                    updated_at = ?
                WHERE project_name = ?
            """, (now, now, project_name))

            was_opted_in = bool(existing[0])
        else:
            # Insert new record
            cursor.execute("""
                INSERT INTO project_consent (project_name, opted_in, opted_in_at, updated_at)
                VALUES (?, 1, ?, ?)
            """, (project_name, now, now))

            was_opted_in = False

        conn.commit()
        conn.close()

        logger.info(f"Project '{project_name}' opted-in for cross-project search")

        return {
            "status": "opted_in",
            "project_name": project_name,
            "was_opted_in": was_opted_in,
            "opted_in_at": now,
        }

    def opt_out(self, project_name: str) -> Dict[str, Any]:
        """
        Opt-out a project from cross-project search.

        Args:
            project_name: Project to opt-out

        Returns:
            Dict with status and timestamps
        """
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        now = datetime.now(UTC).isoformat()

        # Check if record exists
        cursor.execute("""
            SELECT opted_in FROM project_consent
            WHERE project_name = ?
        """, (project_name,))

        existing = cursor.fetchone()

        if existing:
            # Update existing record
            cursor.execute("""
                UPDATE project_consent
                SET opted_in = 0,
                    opted_out_at = ?,
                    updated_at = ?
                WHERE project_name = ?
            """, (now, now, project_name))

            was_opted_in = bool(existing[0])
        else:
            # Insert new record as opted-out
            cursor.execute("""
                INSERT INTO project_consent (project_name, opted_in, opted_out_at, updated_at)
                VALUES (?, 0, ?, ?)
            """, (project_name, now, now))

            was_opted_in = True  # Default is opted-in

        conn.commit()
        conn.close()

        logger.info(f"Project '{project_name}' opted-out from cross-project search")

        return {
            "status": "opted_out",
            "project_name": project_name,
            "was_opted_in": was_opted_in,
            "opted_out_at": now,
        }

    def is_opted_in(self, project_name: str) -> bool:
        """
        Check if a project is opted-in for cross-project search.

        Args:
            project_name: Project to check

        Returns:
            True if opted-in (or no preference set), False if explicitly opted-out
        """
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        cursor.execute("""
            SELECT opted_in FROM project_consent
            WHERE project_name = ?
        """, (project_name,))

        result = cursor.fetchone()
        conn.close()

        if result is None:
            # No preference set - default to opted-in
            return True

        return bool(result[0])

    def list_opted_in_projects(self) -> List[str]:
        """
        List all projects that are explicitly opted-in.

        Returns:
            List of project names that are opted-in
        """
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        cursor.execute("""
            SELECT project_name FROM project_consent
            WHERE opted_in = 1
            ORDER BY project_name
        """)

        projects = [row[0] for row in cursor.fetchall()]
        conn.close()

        return projects

    def list_opted_out_projects(self) -> List[str]:
        """
        List all projects that are explicitly opted-out.

        Returns:
            List of project names that are opted-out
        """
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        cursor.execute("""
            SELECT project_name FROM project_consent
            WHERE opted_in = 0
            ORDER BY project_name
        """)

        projects = [row[0] for row in cursor.fetchall()]
        conn.close()

        return projects

    def get_consent_stats(self) -> Dict[str, Any]:
        """
        Get statistics about consent preferences.

        Returns:
            Dict with consent statistics
        """
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                COUNT(*) as total_projects,
                SUM(CASE WHEN opted_in = 1 THEN 1 ELSE 0 END) as opted_in_count,
                SUM(CASE WHEN opted_in = 0 THEN 1 ELSE 0 END) as opted_out_count
            FROM project_consent
        """)

        row = cursor.fetchone()
        conn.close()

        total_projects = row[0] if row[0] is not None else 0
        opted_in_count = row[1] if row[1] is not None else 0
        opted_out_count = row[2] if row[2] is not None else 0

        return {
            "total_projects": total_projects,
            "opted_in_count": opted_in_count,
            "opted_out_count": opted_out_count,
            "default_consent": "opted_in",  # New projects default to opted-in
        }

    def get_project_consent_status(self, project_name: str) -> Dict[str, Any]:
        """
        Get detailed consent status for a specific project.

        Args:
            project_name: Project to check

        Returns:
            Dict with consent details
        """
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        cursor.execute("""
            SELECT opted_in, opted_in_at, opted_out_at, updated_at
            FROM project_consent
            WHERE project_name = ?
        """, (project_name,))

        result = cursor.fetchone()
        conn.close()

        if result is None:
            return {
                "project_name": project_name,
                "opted_in": True,  # Default
                "has_explicit_preference": False,
                "opted_in_at": None,
                "opted_out_at": None,
                "updated_at": None,
            }

        opted_in, opted_in_at, opted_out_at, updated_at = result

        return {
            "project_name": project_name,
            "opted_in": bool(opted_in),
            "has_explicit_preference": True,
            "opted_in_at": opted_in_at,
            "opted_out_at": opted_out_at,
            "updated_at": updated_at,
        }

    def get_opted_in_projects(self) -> List[str]:
        """
        Alias for list_opted_in_projects() for backward compatibility.

        Returns:
            List of project names that are opted-in
        """
        return self.list_opted_in_projects()

    def get_searchable_projects(
        self,
        current_project: Optional[str] = None,
        search_all: bool = False,
    ) -> List[str]:
        """
        Get list of projects that can be searched in cross-project search.

        Args:
            current_project: Current project name (optional, for filtering)
            search_all: If True, return all opted-in projects. If False, exclude current project.

        Returns:
            List of searchable project names
        """
        opted_in = self.list_opted_in_projects()

        if search_all or current_project is None:
            return opted_in

        # Exclude current project
        return [p for p in opted_in if p != current_project]

    def close(self):
        """Close any open connections (no-op for SQLite with auto-close)."""
        pass


# Alias for backward compatibility
CrossProjectConsent = CrossProjectConsentManager
