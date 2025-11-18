"""Bulk archival operations for managing multiple projects efficiently."""

import logging
from datetime import datetime, UTC
from pathlib import Path
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass

from src.memory.project_archival import ProjectArchivalManager, ProjectState
from src.memory.archive_compressor import ArchiveCompressor

logger = logging.getLogger(__name__)

# Type alias for progress callback
ProgressCallback = Callable[[str, int, int], None]


@dataclass
class BulkArchivalResult:
    """Result of a bulk archival operation."""

    dry_run: bool
    total_projects: int
    successful: int
    failed: int
    skipped: int
    execution_time_seconds: float
    results: List[Dict]  # List of per-project results
    errors: List[str]

    @property
    def success_rate(self) -> float:
        """Calculate success rate percentage."""
        if self.total_projects == 0:
            return 0.0
        return (self.successful / self.total_projects) * 100


class BulkArchivalManager:
    """
    Manage bulk archival and reactivation operations for multiple projects.

    Provides efficient batch processing with safety limits, dry-run mode,
    and progress tracking for archiving/reactivating multiple projects.
    """

    def __init__(
        self,
        archival_manager: ProjectArchivalManager,
        archive_compressor: ArchiveCompressor,
        max_projects_per_operation: int = 20,
    ):
        """
        Initialize bulk archival manager.

        Args:
            archival_manager: Project archival manager for state tracking
            archive_compressor: Archive compressor for compression operations
            max_projects_per_operation: Maximum projects per bulk operation (default 20)
        """
        self.archival_manager = archival_manager
        self.compressor = archive_compressor
        self.max_projects_per_operation = max_projects_per_operation

    async def bulk_archive_projects(
        self,
        project_names: List[str],
        dry_run: bool = False,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> BulkArchivalResult:
        """
        Archive multiple projects with compression.

        Args:
            project_names: List of project names to archive
            dry_run: If True, simulate operation without actually archiving
            progress_callback: Optional callback for progress updates (project_name, current, total)

        Returns:
            BulkArchivalResult with operation statistics
        """
        start_time = datetime.now(UTC)

        # Validate project count
        if len(project_names) > self.max_projects_per_operation:
            return BulkArchivalResult(
                dry_run=dry_run,
                total_projects=len(project_names),
                successful=0,
                failed=0,
                skipped=len(project_names),
                execution_time_seconds=0.0,
                results=[],
                errors=[
                    f"Exceeded max projects limit: {len(project_names)} > {self.max_projects_per_operation}"
                ],
            )

        results = []
        successful = 0
        failed = 0
        skipped = 0
        errors = []

        for idx, project_name in enumerate(project_names, 1):
            if progress_callback:
                progress_callback(project_name, idx, len(project_names))

            try:
                # Check if project can be archived
                current_state = self.archival_manager.get_project_state(project_name)

                if current_state == ProjectState.ARCHIVED:
                    logger.info(f"Project {project_name} already archived, skipping")
                    skipped += 1
                    results.append({
                        "project": project_name,
                        "status": "skipped",
                        "reason": "Already archived",
                    })
                    continue

                if dry_run:
                    logger.info(f"[DRY RUN] Would archive project: {project_name}")
                    successful += 1
                    results.append({
                        "project": project_name,
                        "status": "would_archive",
                        "current_state": current_state.value,
                    })
                else:
                    # Get project info for compression
                    # NOTE: This assumes projects have index paths - may need to be configurable
                    project_info = self.archival_manager.project_states.get(project_name, {})

                    # Archive the project (set state to ARCHIVED)
                    result = self.archival_manager.archive_project(project_name)

                    if result["success"]:
                        logger.info(f"Successfully archived project: {project_name}")
                        successful += 1
                        results.append({
                            "project": project_name,
                            "status": "archived",
                            "previous_state": current_state.value,
                            "archived_at": datetime.now(UTC).isoformat(),
                        })
                    else:
                        logger.error(f"Failed to archive project: {project_name}")
                        failed += 1
                        errors.append(f"Failed to archive {project_name}")
                        results.append({
                            "project": project_name,
                            "status": "failed",
                            "reason": "Archival operation failed",
                        })

            except Exception as e:
                logger.error(f"Error archiving project {project_name}: {e}")
                failed += 1
                errors.append(f"Error archiving {project_name}: {str(e)}")
                results.append({
                    "project": project_name,
                    "status": "error",
                    "error": str(e),
                })

        execution_time = (datetime.now(UTC) - start_time).total_seconds()

        return BulkArchivalResult(
            dry_run=dry_run,
            total_projects=len(project_names),
            successful=successful,
            failed=failed,
            skipped=skipped,
            execution_time_seconds=execution_time,
            results=results,
            errors=errors,
        )

    async def bulk_reactivate_projects(
        self,
        project_names: List[str],
        dry_run: bool = False,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> BulkArchivalResult:
        """
        Reactivate multiple archived projects.

        Args:
            project_names: List of project names to reactivate
            dry_run: If True, simulate operation without actually reactivating
            progress_callback: Optional callback for progress updates

        Returns:
            BulkArchivalResult with operation statistics
        """
        start_time = datetime.now(UTC)

        # Validate project count
        if len(project_names) > self.max_projects_per_operation:
            return BulkArchivalResult(
                dry_run=dry_run,
                total_projects=len(project_names),
                successful=0,
                failed=0,
                skipped=len(project_names),
                execution_time_seconds=0.0,
                results=[],
                errors=[
                    f"Exceeded max projects limit: {len(project_names)} > {self.max_projects_per_operation}"
                ],
            )

        results = []
        successful = 0
        failed = 0
        skipped = 0
        errors = []

        for idx, project_name in enumerate(project_names, 1):
            if progress_callback:
                progress_callback(project_name, idx, len(project_names))

            try:
                # Check if project can be reactivated
                current_state = self.archival_manager.get_project_state(project_name)

                if current_state != ProjectState.ARCHIVED:
                    logger.info(f"Project {project_name} not archived (state: {current_state.value}), skipping")
                    skipped += 1
                    results.append({
                        "project": project_name,
                        "status": "skipped",
                        "reason": f"Not archived (current state: {current_state.value})",
                    })
                    continue

                if dry_run:
                    logger.info(f"[DRY RUN] Would reactivate project: {project_name}")
                    successful += 1
                    results.append({
                        "project": project_name,
                        "status": "would_reactivate",
                        "current_state": current_state.value,
                    })
                else:
                    # Reactivate the project
                    result = self.archival_manager.reactivate_project(project_name)

                    if result["success"]:
                        logger.info(f"Successfully reactivated project: {project_name}")
                        successful += 1
                        results.append({
                            "project": project_name,
                            "status": "reactivated",
                            "previous_state": current_state.value,
                            "reactivated_at": datetime.now(UTC).isoformat(),
                        })
                    else:
                        logger.error(f"Failed to reactivate project: {project_name}")
                        failed += 1
                        errors.append(f"Failed to reactivate {project_name}")
                        results.append({
                            "project": project_name,
                            "status": "failed",
                            "reason": "Reactivation operation failed",
                        })

            except Exception as e:
                logger.error(f"Error reactivating project {project_name}: {e}")
                failed += 1
                errors.append(f"Error reactivating {project_name}: {str(e)}")
                results.append({
                    "project": project_name,
                    "status": "error",
                    "error": str(e),
                })

        execution_time = (datetime.now(UTC) - start_time).total_seconds()

        return BulkArchivalResult(
            dry_run=dry_run,
            total_projects=len(project_names),
            successful=successful,
            failed=failed,
            skipped=skipped,
            execution_time_seconds=execution_time,
            results=results,
            errors=errors,
        )

    async def auto_archive_inactive(
        self,
        days_threshold: Optional[int] = None,
        dry_run: bool = False,
        max_projects: Optional[int] = None,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> BulkArchivalResult:
        """
        Automatically archive inactive projects based on inactivity threshold.

        Args:
            days_threshold: Archive projects inactive for this many days (default: use manager's threshold)
            dry_run: If True, simulate operation without actually archiving
            max_projects: Maximum projects to archive in this operation (default: use manager limit)
            progress_callback: Optional callback for progress updates

        Returns:
            BulkArchivalResult with operation statistics
        """
        # Set custom threshold temporarily if provided
        original_threshold = self.archival_manager.inactivity_threshold_days
        if days_threshold is not None:
            self.archival_manager.inactivity_threshold_days = days_threshold

        try:
            # Get inactive projects (uses manager's inactivity_threshold_days)
            inactive_project_names = self.archival_manager.get_inactive_projects()

            if not inactive_project_names:
                threshold = days_threshold if days_threshold is not None else original_threshold
                logger.info(f"No inactive projects found with threshold {threshold} days")
                return BulkArchivalResult(
                    dry_run=dry_run,
                    total_projects=0,
                    successful=0,
                    failed=0,
                    skipped=0,
                    execution_time_seconds=0.0,
                    results=[],
                    errors=[],
                )

            # Filter for ACTIVE or PAUSED projects only (don't re-archive)
            archivable_projects = [
                project_name
                for project_name in inactive_project_names
                if self.archival_manager.get_project_state(project_name) in [
                    ProjectState.ACTIVE,
                    ProjectState.PAUSED,
                ]
            ]
        finally:
            # Restore original threshold
            self.archival_manager.inactivity_threshold_days = original_threshold

        # Limit to max_projects
        limit = max_projects if max_projects is not None else self.max_projects_per_operation
        if len(archivable_projects) > limit:
            logger.warning(
                f"Found {len(archivable_projects)} archivable projects, limiting to {limit}"
            )
            archivable_projects = archivable_projects[:limit]

        logger.info(
            f"Auto-archiving {len(archivable_projects)} projects "
            f"(inactive for {days_threshold}+ days, dry_run={dry_run})"
        )

        # Use bulk_archive_projects
        return await self.bulk_archive_projects(
            project_names=archivable_projects,
            dry_run=dry_run,
            progress_callback=progress_callback,
        )

    def get_archival_candidates(
        self,
        days_threshold: Optional[int] = None,
        max_results: int = 100,
    ) -> List[Dict]:
        """
        Get list of projects that are candidates for archival.

        Args:
            days_threshold: Consider projects inactive for this many days (default: use manager's threshold)
            max_results: Maximum number of results to return

        Returns:
            List of project info dicts with archival candidate details
        """
        # Set custom threshold temporarily if provided
        original_threshold = self.archival_manager.inactivity_threshold_days
        if days_threshold is not None:
            self.archival_manager.inactivity_threshold_days = days_threshold

        try:
            inactive_project_names = self.archival_manager.get_inactive_projects()

            # Filter for archivable states and add extra info
            candidates = []
            for project_name in inactive_project_names:
                state = self.archival_manager.get_project_state(project_name)

                # Only suggest ACTIVE or PAUSED projects
                if state in [ProjectState.ACTIVE, ProjectState.PAUSED]:
                    days_inactive = self.archival_manager.get_days_since_activity(project_name)
                    candidates.append({
                        "project_name": project_name,
                        "current_state": state.value,
                        "days_inactive": days_inactive,
                        "recommendation": "archive",
                        "reason": f"Inactive for {days_inactive:.1f} days",
                    })

            return candidates[:max_results]
        finally:
            # Restore original threshold
            self.archival_manager.inactivity_threshold_days = original_threshold
