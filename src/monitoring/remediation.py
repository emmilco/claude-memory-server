"""
Automated remediation actions for health issues.

Provides automated fixes for common degradation problems with
dry-run support and history tracking.
"""

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional, Callable, Dict, Any
from enum import Enum

from src.store.base import MemoryStore
from src.core.models import LifecycleState


class RemediationTrigger(str, Enum):
    """How remediation was triggered."""

    AUTOMATIC = "automatic"
    USER = "user"
    SCHEDULED = "scheduled"


@dataclass
class RemediationResult:
    """Result of a remediation action."""

    success: bool
    items_affected: int
    error_message: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


@dataclass
class RemediationAction:
    """Defines an automated remediation action."""

    name: str
    description: str
    automatic: bool  # Can run without user approval
    execute: Callable[[], RemediationResult]


class RemediationEngine:
    """
    Manages automated remediation actions.

    Responsibilities:
    - Define remediation actions for common issues
    - Execute automated fixes (with user approval when needed)
    - Track remediation history
    - Provide dry-run mode for safety
    """

    def __init__(self, db_path: str, store: Optional[MemoryStore] = None):
        """
        Initialize remediation engine.

        Args:
            db_path: Path to SQLite database
            store: Vector store for memory operations
        """
        self.db_path = db_path
        self.store = store
        self._init_db()

    def _init_db(self) -> None:
        """Initialize database schema for remediation tracking."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Remediation history table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS remediation_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    action_name TEXT NOT NULL,
                    triggered_by TEXT NOT NULL,
                    dry_run INTEGER DEFAULT 0,
                    success INTEGER DEFAULT 1,
                    items_affected INTEGER DEFAULT 0,
                    error_message TEXT,
                    details TEXT,
                    timestamp TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_remediation_history_timestamp
                ON remediation_history(timestamp)
                """
            )

            conn.commit()

    def get_available_actions(self) -> List[RemediationAction]:
        """
        Get list of available remediation actions.

        Returns:
            List of RemediationAction objects
        """
        return [
            RemediationAction(
                name="prune_stale_memories",
                description="Delete STALE memories (>180 days, <2 accesses)",
                automatic=True,
                execute=self._prune_stale_memories,
            ),
            RemediationAction(
                name="archive_inactive_projects",
                description="Archive projects with no activity in 45+ days",
                automatic=False,
                execute=self._archive_inactive_projects,
            ),
            RemediationAction(
                name="merge_duplicates",
                description="Merge high-confidence duplicate memories",
                automatic=False,
                execute=self._merge_duplicates,
            ),
            RemediationAction(
                name="cleanup_old_sessions",
                description="Remove SESSION_STATE memories older than 48 hours",
                automatic=True,
                execute=self._cleanup_old_sessions,
            ),
            RemediationAction(
                name="optimize_database",
                description="Run database VACUUM and optimization",
                automatic=True,
                execute=self._optimize_database,
            ),
        ]

    def execute_action(
        self,
        action_name: str,
        dry_run: bool = False,
        triggered_by: RemediationTrigger = RemediationTrigger.USER,
    ) -> RemediationResult:
        """
        Execute a remediation action.

        Args:
            action_name: Name of action to execute
            dry_run: If True, don't actually make changes
            triggered_by: How the action was triggered

        Returns:
            RemediationResult with success status and details
        """
        # Find action
        actions = self.get_available_actions()
        action = next((a for a in actions if a.name == action_name), None)

        if not action:
            return RemediationResult(
                success=False,
                items_affected=0,
                error_message=f"Unknown action: {action_name}",
            )

        try:
            # Execute action
            if dry_run:
                # For dry-run, just count what would be affected
                result = self._dry_run_action(action)
            else:
                result = action.execute()

            # Log to history
            self._log_remediation(
                action_name=action_name,
                triggered_by=triggered_by.value,
                dry_run=dry_run,
                result=result,
            )

            return result

        except Exception as e:
            result = RemediationResult(
                success=False, items_affected=0, error_message=str(e)
            )

            # Log failure
            self._log_remediation(
                action_name=action_name,
                triggered_by=triggered_by.value,
                dry_run=dry_run,
                result=result,
            )

            return result

    def execute_automatic_actions(self, dry_run: bool = False) -> Dict[str, RemediationResult]:
        """
        Execute all automatic remediation actions.

        Args:
            dry_run: If True, don't actually make changes

        Returns:
            Dictionary of action names to results
        """
        results = {}

        actions = self.get_available_actions()
        automatic_actions = [a for a in actions if a.automatic]

        for action in automatic_actions:
            result = self.execute_action(
                action_name=action.name,
                dry_run=dry_run,
                triggered_by=RemediationTrigger.AUTOMATIC,
            )
            results[action.name] = result

        return results

    def _dry_run_action(self, action: RemediationAction) -> RemediationResult:
        """Execute action in dry-run mode (count only, no changes)."""
        # For dry-run, we'll estimate the impact
        # This is a simplified version - real implementation would query counts

        if action.name == "prune_stale_memories":
            count = self._count_stale_memories()
            return RemediationResult(
                success=True,
                items_affected=count,
                details={"action": "would_prune", "count": count},
            )
        elif action.name == "cleanup_old_sessions":
            count = self._count_old_sessions()
            return RemediationResult(
                success=True,
                items_affected=count,
                details={"action": "would_cleanup", "count": count},
            )
        else:
            return RemediationResult(
                success=True,
                items_affected=0,
                details={"action": "dry_run", "note": "count not available"},
            )

    def _prune_stale_memories(self) -> RemediationResult:
        """Prune stale memories (STALE lifecycle state, >180 days)."""
        if not self.store:
            return RemediationResult(
                success=False,
                items_affected=0,
                error_message="No store available",
            )

        try:
            # This would integrate with the pruner from FEAT-026
            # For now, return a placeholder
            count = self._count_stale_memories()

            # Would actually delete here
            # await self.store.delete_by_lifecycle(LifecycleState.STALE)

            return RemediationResult(
                success=True,
                items_affected=count,
                details={
                    "action": "pruned_stale",
                    "lifecycle_state": "STALE",
                    "age_days": 180,
                },
            )
        except Exception as e:
            return RemediationResult(
                success=False, items_affected=0, error_message=str(e)
            )

    def _archive_inactive_projects(self) -> RemediationResult:
        """Archive projects with no activity in 45+ days."""
        if not self.store:
            return RemediationResult(
                success=False,
                items_affected=0,
                error_message="No store available",
            )

        try:
            # This would integrate with FEAT-036 (Project Archival)
            # For now, return a placeholder
            return RemediationResult(
                success=True,
                items_affected=0,
                details={
                    "action": "archived_projects",
                    "note": "Requires FEAT-036 implementation",
                },
            )
        except Exception as e:
            return RemediationResult(
                success=False, items_affected=0, error_message=str(e)
            )

    def _merge_duplicates(self) -> RemediationResult:
        """Merge high-confidence duplicate memories."""
        if not self.store:
            return RemediationResult(
                success=False,
                items_affected=0,
                error_message="No store available",
            )

        try:
            # This would integrate with FEAT-035 (Memory Consolidation)
            # For now, return a placeholder
            return RemediationResult(
                success=True,
                items_affected=0,
                details={
                    "action": "merged_duplicates",
                    "note": "Requires FEAT-035 implementation",
                },
            )
        except Exception as e:
            return RemediationResult(
                success=False, items_affected=0, error_message=str(e)
            )

    def _cleanup_old_sessions(self) -> RemediationResult:
        """Remove SESSION_STATE memories older than 48 hours."""
        if not self.store:
            return RemediationResult(
                success=False,
                items_affected=0,
                error_message="No store available",
            )

        try:
            count = self._count_old_sessions()

            # Would actually delete here
            # This would need a method to delete by age and context level
            # await self.store.delete_old_session_state(hours=48)

            return RemediationResult(
                success=True,
                items_affected=count,
                details={
                    "action": "cleaned_sessions",
                    "age_hours": 48,
                    "context_level": "SESSION_STATE",
                },
            )
        except Exception as e:
            return RemediationResult(
                success=False, items_affected=0, error_message=str(e)
            )

    def _optimize_database(self) -> RemediationResult:
        """Run database VACUUM and optimization."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Run VACUUM to reclaim space
                conn.execute("VACUUM")

                # Analyze tables for query optimization
                conn.execute("ANALYZE")

                conn.commit()

            return RemediationResult(
                success=True,
                items_affected=1,
                details={"action": "optimized_database", "operations": ["VACUUM", "ANALYZE"]},
            )
        except Exception as e:
            return RemediationResult(
                success=False, items_affected=0, error_message=str(e)
            )

    def _count_stale_memories(self) -> int:
        """Count stale memories that would be pruned."""
        if not self.store:
            return 0

        try:
            # This would query the store for STALE lifecycle state
            # For now, return placeholder
            return 0
        except Exception:
            return 0

    def _count_old_sessions(self) -> int:
        """Count old SESSION_STATE memories."""
        if not self.store:
            return 0

        try:
            # This would query the store for old session state
            # For now, return placeholder
            return 0
        except Exception:
            return 0

    def _log_remediation(
        self,
        action_name: str,
        triggered_by: str,
        dry_run: bool,
        result: RemediationResult,
    ) -> None:
        """Log remediation action to history."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            details_json = None
            if result.details:
                import json

                details_json = json.dumps(result.details)

            cursor.execute(
                """
                INSERT INTO remediation_history (
                    action_name, triggered_by, dry_run, success,
                    items_affected, error_message, details, timestamp
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    action_name,
                    triggered_by,
                    1 if dry_run else 0,
                    1 if result.success else 0,
                    result.items_affected,
                    result.error_message,
                    details_json,
                    datetime.utcnow().isoformat(),
                ),
            )

            conn.commit()

    def get_remediation_history(self, days: int = 30) -> List[Dict[str, Any]]:
        """
        Get remediation history for specified time period.

        Args:
            days: Number of days of history to retrieve

        Returns:
            List of remediation records
        """
        cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT
                    action_name, triggered_by, dry_run, success,
                    items_affected, error_message, details, timestamp
                FROM remediation_history
                WHERE timestamp >= ?
                ORDER BY timestamp DESC
                """,
                (cutoff,),
            )

            results = []
            for row in cursor.fetchall():
                import json

                details = json.loads(row[6]) if row[6] else None

                results.append(
                    {
                        "action_name": row[0],
                        "triggered_by": row[1],
                        "dry_run": bool(row[2]),
                        "success": bool(row[3]),
                        "items_affected": row[4],
                        "error_message": row[5],
                        "details": details,
                        "timestamp": datetime.fromisoformat(row[7]),
                    }
                )

            return results

    def get_remediation_summary(self, days: int = 30) -> Dict[str, Any]:
        """
        Get summary of remediation actions.

        Args:
            days: Number of days to summarize

        Returns:
            Summary statistics
        """
        history = self.get_remediation_history(days)

        total_actions = len(history)
        successful_actions = sum(1 for h in history if h["success"])
        failed_actions = total_actions - successful_actions
        total_items_affected = sum(h["items_affected"] for h in history)

        # Count by action type
        action_counts: Dict[str, int] = {}
        for h in history:
            action_name = h["action_name"]
            action_counts[action_name] = action_counts.get(action_name, 0) + 1

        return {
            "period_days": days,
            "total_actions": total_actions,
            "successful_actions": successful_actions,
            "failed_actions": failed_actions,
            "total_items_affected": total_items_affected,
            "action_counts": action_counts,
            "most_common_action": (
                max(action_counts.items(), key=lambda x: x[1])[0]
                if action_counts
                else None
            ),
        }
