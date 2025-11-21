"""Automated health maintenance jobs for memory lifecycle management.

This module provides background jobs for automatic archival, cleanup, and
health reporting to maintain system quality over time.
"""

import logging
import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime, UTC, timedelta
from dataclasses import dataclass

from src.core.models import LifecycleState, ContextLevel
from src.store import MemoryStore
from src.memory.lifecycle_manager import LifecycleManager
from src.memory.health_scorer import HealthScorer, HealthScore

logger = logging.getLogger(__name__)


@dataclass
class JobResult:
    """Result from a maintenance job."""

    job_name: str
    success: bool
    memories_processed: int = 0
    memories_archived: int = 0
    memories_deleted: int = 0
    errors: List[str] = None
    timestamp: datetime = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []
        if self.timestamp is None:
            self.timestamp = datetime.now(UTC)

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "job_name": self.job_name,
            "success": self.success,
            "memories_processed": self.memories_processed,
            "memories_archived": self.memories_archived,
            "memories_deleted": self.memories_deleted,
            "error_count": len(self.errors),
            "errors": self.errors[:10],  # Limit to first 10 errors
            "timestamp": self.timestamp.isoformat(),
        }


class HealthMaintenanceJobs:
    """
    Automated maintenance jobs for memory health.

    Provides scheduled jobs for:
    - Weekly archival of old memories
    - Monthly cleanup of STALE memories
    - Weekly health reporting
    """

    def __init__(
        self,
        store: MemoryStore,
        lifecycle_manager: LifecycleManager,
        health_scorer: Optional[HealthScorer] = None,
    ):
        """
        Initialize health maintenance jobs.

        Args:
            store: Memory store
            lifecycle_manager: Lifecycle manager for state transitions
            health_scorer: Optional health scorer (created if None)
        """
        self.store = store
        self.lifecycle_manager = lifecycle_manager
        self.health_scorer = health_scorer or HealthScorer(store)

        # Job history
        self.job_history: List[JobResult] = []

        logger.info("HealthMaintenanceJobs initialized")

    async def weekly_archival_job(self, dry_run: bool = False) -> JobResult:
        """
        Weekly job to archive memories transitioning to ARCHIVED state.

        Archives memories that are:
        - 30+ days old
        - Not frequently accessed
        - Not USER_PREFERENCE (they age slower)

        Args:
            dry_run: If True, only simulate the operation

        Returns:
            JobResult with operation details
        """
        job_name = "weekly_archival"
        logger.info(f"Starting {job_name} job (dry_run={dry_run})")

        result = JobResult(
            job_name=job_name,
            success=False,
        )

        try:
            # Get all memories to check for archival
            all_memories = await self.store.get_all_memories()
            candidates = []

            for memory in all_memories:
                # Skip if already ARCHIVED or STALE
                current_state = memory.get('lifecycle_state', LifecycleState.ACTIVE)
                if isinstance(current_state, str):
                    try:
                        current_state = LifecycleState(current_state)
                    except ValueError:
                        current_state = LifecycleState.ACTIVE

                if current_state in [LifecycleState.ARCHIVED, LifecycleState.STALE]:
                    continue

                # Parse datetime if it's a string
                created_at = memory.get('created_at')
                if isinstance(created_at, str):
                    from dateutil.parser import parse
                    created_at = parse(created_at)

                last_accessed = memory.get('last_accessed', created_at)
                if isinstance(last_accessed, str):
                    from dateutil.parser import parse
                    last_accessed = parse(last_accessed)

                # Parse context_level if it's a string
                context_level = memory.get('context_level', ContextLevel.SESSION_STATE)
                if isinstance(context_level, str):
                    try:
                        context_level = ContextLevel(context_level)
                    except ValueError:
                        context_level = ContextLevel.SESSION_STATE

                # Calculate what state it should be in
                target_state = self.lifecycle_manager.calculate_state(
                    created_at=created_at,
                    last_accessed=last_accessed,
                    use_count=memory.get('use_count', 0),
                    context_level=context_level,
                )

                # If it should be ARCHIVED or STALE, it's a candidate
                if target_state in [LifecycleState.ARCHIVED, LifecycleState.STALE]:
                    candidates.append((memory, target_state))

            result.memories_processed = len(candidates)

            if dry_run:
                logger.info(
                    f"DRY RUN: Would archive {len(candidates)} memories"
                )
                result.success = True
                result.memories_archived = len(candidates)
            else:
                # Execute archival
                archived_count = 0
                for memory, target_state in candidates:
                    try:
                        # Update lifecycle state
                        await self.store.update_lifecycle_state(
                            memory.get('id'), target_state
                        )
                        archived_count += 1
                    except Exception as e:
                        error_msg = f"Failed to archive memory {memory.get('id')}: {e}"
                        logger.error(error_msg)
                        result.errors.append(error_msg)

                result.memories_archived = archived_count
                result.success = True

                logger.info(
                    f"Archived {archived_count} memories, {len(result.errors)} errors"
                )

        except Exception as e:
            error_msg = f"Weekly archival job failed: {e}"
            logger.error(error_msg, exc_info=True)
            result.errors.append(error_msg)
            result.success = False

        # Store in history
        self.job_history.append(result)

        return result

    async def monthly_cleanup_job(
        self, dry_run: bool = False, min_age_days: int = 180
    ) -> JobResult:
        """
        Monthly job to delete STALE memories with low usage.

        Deletes memories that are:
        - 180+ days old (STALE)
        - Rarely or never accessed
        - Not USER_PREFERENCE (they're kept longer)

        Args:
            dry_run: If True, only simulate the operation
            min_age_days: Minimum age in days for deletion

        Returns:
            JobResult with operation details
        """
        job_name = "monthly_cleanup"
        logger.info(f"Starting {job_name} job (dry_run={dry_run})")

        result = JobResult(
            job_name=job_name,
            success=False,
        )

        try:
            # Get all STALE memories
            all_memories = await self.store.get_all_memories()
            candidates = []

            cutoff_date = datetime.now(UTC) - timedelta(days=min_age_days)

            for memory in all_memories:
                # Only delete STALE memories
                current_state = memory.get('lifecycle_state', LifecycleState.ACTIVE)
                if isinstance(current_state, str):
                    try:
                        current_state = LifecycleState(current_state)
                    except ValueError:
                        current_state = LifecycleState.ACTIVE

                if current_state != LifecycleState.STALE:
                    continue

                # Check age
                created_at = memory.get('created_at')
                if isinstance(created_at, str):
                    from dateutil.parser import parse
                    created_at = parse(created_at)

                if created_at > cutoff_date:
                    continue

                # Skip USER_PREFERENCE (they're more valuable)
                context_level = memory.get('context_level', ContextLevel.SESSION_STATE)
                if isinstance(context_level, str):
                    try:
                        context_level = ContextLevel(context_level)
                    except ValueError:
                        context_level = ContextLevel.SESSION_STATE

                if context_level == ContextLevel.USER_PREFERENCE:
                    continue

                # Check usage (skip if frequently accessed)
                use_count = memory.get('use_count', 0)
                if use_count > 5:  # Has been used at least 5 times
                    continue

                candidates.append(memory)

            result.memories_processed = len(candidates)

            if dry_run:
                logger.info(
                    f"DRY RUN: Would delete {len(candidates)} STALE memories"
                )
                result.success = True
                result.memories_deleted = len(candidates)
            else:
                # Execute deletion
                deleted_count = 0
                for memory in candidates:
                    try:
                        await self.store.delete_memory(memory.get('id'))
                        deleted_count += 1
                    except Exception as e:
                        error_msg = f"Failed to delete memory {memory.get('id')}: {e}"
                        logger.error(error_msg)
                        result.errors.append(error_msg)

                result.memories_deleted = deleted_count
                result.success = True

                logger.info(
                    f"Deleted {deleted_count} STALE memories, {len(result.errors)} errors"
                )

        except Exception as e:
            error_msg = f"Monthly cleanup job failed: {e}"
            logger.error(error_msg, exc_info=True)
            result.errors.append(error_msg)
            result.success = False

        # Store in history
        self.job_history.append(result)

        return result

    async def weekly_health_report_job(self) -> JobResult:
        """
        Weekly job to generate and log health report.

        Calculates health score and logs report with recommendations.

        Returns:
            JobResult with operation details
        """
        job_name = "weekly_health_report"
        logger.info(f"Starting {job_name} job")

        result = JobResult(
            job_name=job_name,
            success=False,
        )

        try:
            # Calculate health score
            health_score = await self.health_scorer.calculate_overall_health()

            # Store health score (if health metrics table exists)
            try:
                await self._store_health_score(health_score)
            except Exception as e:
                logger.warning(f"Could not store health score: {e}")

            # Log health report
            logger.info(
                f"\n"
                f"═══════════════════════════════════════\n"
                f"  Weekly Health Report\n"
                f"═══════════════════════════════════════\n"
                f"Overall Health: {health_score.overall:.1f}/100 ({health_score.grade})\n"
                f"Noise Ratio: {health_score.noise_ratio:.1%}\n"
                f"Duplicate Rate: {health_score.duplicate_rate:.1%}\n"
                f"Contradiction Rate: {health_score.contradiction_rate:.1%}\n"
                f"\n"
                f"Lifecycle Distribution:\n"
                f"  ACTIVE: {health_score.active_count}\n"
                f"  RECENT: {health_score.recent_count}\n"
                f"  ARCHIVED: {health_score.archived_count}\n"
                f"  STALE: {health_score.stale_count}\n"
                f"\n"
                f"Recommendations:\n"
                + "\n".join(f"  • {rec}" for rec in health_score.recommendations)
                + f"\n═══════════════════════════════════════"
            )

            result.success = True
            result.memories_processed = health_score.total_count

        except Exception as e:
            error_msg = f"Weekly health report job failed: {e}"
            logger.error(error_msg, exc_info=True)
            result.errors.append(error_msg)
            result.success = False

        # Store in history
        self.job_history.append(result)

        return result

    async def _store_health_score(self, health_score: HealthScore) -> None:
        """
        Store health score in database for trend tracking.

        Args:
            health_score: Health score to store
        """
        # This would store in a health_metrics table
        # For now, it's a no-op (table creation happens in CLI)
        pass

    def get_job_history(self, limit: int = 10) -> List[Dict]:
        """
        Get recent job history.

        Args:
            limit: Maximum number of jobs to return

        Returns:
            List of job result dictionaries
        """
        recent_jobs = self.job_history[-limit:] if self.job_history else []
        return [job.to_dict() for job in reversed(recent_jobs)]

    def clear_job_history(self) -> None:
        """Clear job history."""
        self.job_history.clear()
        logger.info("Job history cleared")
