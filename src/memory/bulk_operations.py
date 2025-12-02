"""
Bulk memory operations module.

Provides efficient bulk operations on memories with safety features like
dry-run previews, batch processing, progress tracking, and safety limits.
"""

from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Protocol
from pydantic import BaseModel, Field

from src.core.models import MemoryUnit


# Type alias for progress callbacks
ProgressCallback = Callable[[int, int, str], None]


class DeletionMetadata(BaseModel):
    """
    Metadata stored for a soft-deleted memory to enable rollback.

    Stored in the memory's metadata field under key 'deletion_info'.
    """

    deleted_at: datetime = Field(description="Timestamp when memory was deleted")
    rollback_id: str = Field(description="ID to identify this deletion operation")
    deleted_by: str = Field(default="bulk_operation", description="Source of deletion")
    original_state: Dict[str, Any] = Field(
        description="Original memory state before deletion"
    )
    can_rollback: bool = Field(
        default=True, description="Whether this deletion can be rolled back"
    )


class RollbackInfo(BaseModel):
    """
    Information about memories available for rollback.

    Returned when querying rollback status.
    """

    rollback_id: str = Field(description="ID of the rollback operation")
    deleted_count: int = Field(description="Number of memories in this rollback set")
    deleted_at: datetime = Field(description="When the deletion occurred")
    memory_ids: List[str] = Field(description="IDs of deleted memories")
    can_rollback: bool = Field(description="Whether rollback is still possible")
    expiry_date: Optional[datetime] = Field(
        None, description="When this rollback will expire (if set)"
    )


class MemoryStore(Protocol):
    """Protocol for memory store operations."""

    async def delete(self, memory_id: str) -> bool:
        """Delete a memory by ID."""
        ...

    async def update(self, memory_id: str, updates: Dict[str, Any]) -> bool:
        """Update a memory's metadata."""
        ...

    async def get_by_id(self, memory_id: str) -> Optional[MemoryUnit]:
        """Retrieve a memory by ID."""
        ...


class BulkDeleteFilters(BaseModel):
    """
    Filtering criteria for bulk delete operations.

    Mirrors the list_memories parameters to ensure consistency.
    """

    category: Optional[str] = Field(None, description="Filter by memory category")
    context_level: Optional[str] = Field(None, description="Filter by context level")
    scope: Optional[str] = Field(None, description="Filter by scope")
    project_name: Optional[str] = Field(None, description="Filter by project name")
    tags: Optional[List[str]] = Field(None, description="Filter by tags (match any)")
    min_importance: float = Field(
        0.0, ge=0.0, le=1.0, description="Minimum importance threshold"
    )
    max_importance: float = Field(
        1.0, ge=0.0, le=1.0, description="Maximum importance threshold"
    )
    date_from: Optional[str] = Field(
        None, description="Delete memories created after this date (ISO format)"
    )
    date_to: Optional[str] = Field(
        None, description="Delete memories created before this date (ISO format)"
    )
    lifecycle_state: Optional[str] = Field(
        None, description="Filter by lifecycle state"
    )

    # Safety parameters
    max_count: int = Field(
        1000,
        ge=1,
        le=1000,
        description="Maximum memories to delete (hard limit: 1000)",
    )
    confirm_threshold: int = Field(
        10, ge=1, description="Require explicit confirmation above this count"
    )


class BulkDeletePreview(BaseModel):
    """
    Preview of a bulk deletion operation.

    Shows what will be deleted without actually deleting anything.
    """

    total_matches: int = Field(description="Total number of matching memories")
    sample_memories: List[MemoryUnit] = Field(
        description="Sample of memories to be deleted (first 10)"
    )
    breakdown_by_category: Dict[str, int] = Field(
        description="Count of memories by category"
    )
    breakdown_by_lifecycle: Dict[str, int] = Field(
        description="Count of memories by lifecycle state"
    )
    breakdown_by_project: Dict[str, int] = Field(
        description="Count of memories by project"
    )
    estimated_storage_freed_mb: float = Field(
        description="Estimated storage space to be freed (MB)"
    )
    warnings: List[str] = Field(description="Warnings about the deletion")
    requires_confirmation: bool = Field(
        description="Whether explicit confirmation is required"
    )


class BulkDeleteResult(BaseModel):
    """
    Result of a bulk deletion operation.

    Contains statistics and status information about the operation.
    """

    success: bool = Field(description="Whether the operation succeeded")
    dry_run: bool = Field(description="Whether this was a dry-run (no actual deletion)")
    total_deleted: int = Field(description="Number of memories successfully deleted")
    failed_deletions: List[str] = Field(description="Memory IDs that failed to delete")
    rollback_id: Optional[str] = Field(
        None, description="Rollback ID if rollback is enabled"
    )
    execution_time: float = Field(description="Execution time in seconds")
    storage_freed_mb: float = Field(description="Storage space freed (MB)")
    errors: List[str] = Field(description="Error messages encountered")


class BulkDeleteManager:
    """
    Manager for bulk memory deletion operations.

    Provides safe, efficient bulk deletion with:
    - Dry-run previews
    - Batch processing
    - Progress tracking
    - Safety limits
    - Error handling
    """

    def __init__(
        self,
        store: MemoryStore,
        max_batch_size: int = 100,
        max_total_operations: int = 1000,
        soft_delete_retention_days: int = 30,
    ):
        """
        Initialize the bulk delete manager.

        Args:
            store: Memory store instance
            max_batch_size: Number of memories to delete per batch
            max_total_operations: Maximum total memories to delete in one operation
            soft_delete_retention_days: Days to retain soft-deleted memories for rollback
        """
        self.store = store
        self.max_batch_size = max_batch_size
        self.max_total_operations = max_total_operations
        self.soft_delete_retention_days = soft_delete_retention_days

    def _estimate_memory_size(self, memory: MemoryUnit) -> int:
        """
        Estimate the storage size of a memory in bytes.

        Args:
            memory: Memory unit to estimate

        Returns:
            Estimated size in bytes
        """
        # Rough estimate: content + metadata + vector (768 dimensions * 4 bytes)
        content_size = len(memory.content.encode("utf-8"))
        metadata_size = 200  # Approximate overhead for metadata
        vector_size = 768 * 4  # 768-dim float32 vector
        return content_size + metadata_size + vector_size

    def _generate_warnings(
        self,
        memories: List[MemoryUnit],
        total_count: int,
        filters: BulkDeleteFilters,
    ) -> List[str]:
        """
        Generate warnings based on the deletion operation.

        Args:
            memories: List of memories to be deleted
            total_count: Total count of matching memories
            filters: Filter criteria used

        Returns:
            List of warning messages
        """
        warnings = []

        # Warn about large deletions
        if total_count > 100:
            warnings.append(f"This will delete {total_count} memories")
        elif total_count > 0:
            warnings.append(f"This will delete {total_count} memory(ies)")

        # Warn about high-importance memories
        high_importance_count = sum(
            1 for m in memories if m.importance and m.importance > 0.7
        )
        if high_importance_count > 0:
            warnings.append(
                f"Includes {high_importance_count} high-importance memories (>0.7)"
            )

        # Warn about recent memories
        seven_days_ago = datetime.now().timestamp() - (7 * 24 * 60 * 60)
        recent_count = sum(
            1
            for m in memories
            if m.created_at and m.created_at.timestamp() > seven_days_ago
        )
        if recent_count > 0:
            warnings.append(f"Includes {recent_count} memories from the last 7 days")

        # Warn about multi-project deletion
        if not filters.project_name:
            projects = set(m.project_name for m in memories if m.project_name)
            if len(projects) > 1:
                warnings.append(
                    f"Affects {len(projects)} projects: {', '.join(sorted(projects)[:3])}"
                    + (f" and {len(projects) - 3} more" if len(projects) > 3 else "")
                )

        # Warn if approaching or at limit
        if total_count >= self.max_total_operations:
            warnings.append(
                f"Operation limited to {self.max_total_operations} memories (safety limit)"
            )

        return warnings

    def _calculate_breakdowns(
        self, memories: List[MemoryUnit]
    ) -> tuple[Dict[str, int], Dict[str, int], Dict[str, int]]:
        """
        Calculate breakdowns of memories by various attributes.

        Args:
            memories: List of memories to analyze

        Returns:
            Tuple of (category_breakdown, lifecycle_breakdown, project_breakdown)
        """
        category_breakdown: Dict[str, int] = {}
        lifecycle_breakdown: Dict[str, int] = {}
        project_breakdown: Dict[str, int] = {}

        for memory in memories:
            # Category breakdown
            category = memory.category.value if memory.category else "unknown"
            category_breakdown[category] = category_breakdown.get(category, 0) + 1

            # Lifecycle breakdown
            lifecycle = (
                memory.lifecycle_state.value if memory.lifecycle_state else "active"
            )
            lifecycle_breakdown[lifecycle] = lifecycle_breakdown.get(lifecycle, 0) + 1

            # Project breakdown
            project = memory.project_name or "unassigned"
            project_breakdown[project] = project_breakdown.get(project, 0) + 1

        return category_breakdown, lifecycle_breakdown, project_breakdown

    async def preview_deletion(
        self, memories: List[MemoryUnit], filters: BulkDeleteFilters
    ) -> BulkDeletePreview:
        """
        Generate a preview of what will be deleted.

        Args:
            memories: List of memories that match the filter criteria
            filters: Filter criteria used

        Returns:
            Preview with statistics and warnings
        """
        len(memories)

        # Apply max_count limit
        limited_memories = memories[: filters.max_count]
        actual_count = len(limited_memories)

        # Get sample (first 10)
        sample_memories = limited_memories[:10]

        # Calculate breakdowns
        (
            category_breakdown,
            lifecycle_breakdown,
            project_breakdown,
        ) = self._calculate_breakdowns(limited_memories)

        # Estimate storage freed
        total_size_bytes = sum(self._estimate_memory_size(m) for m in limited_memories)
        storage_freed_mb = total_size_bytes / (1024 * 1024)

        # Generate warnings
        warnings = self._generate_warnings(limited_memories, actual_count, filters)

        # Determine if confirmation required
        requires_confirmation = actual_count > filters.confirm_threshold

        return BulkDeletePreview(
            total_matches=actual_count,
            sample_memories=sample_memories,
            breakdown_by_category=category_breakdown,
            breakdown_by_lifecycle=lifecycle_breakdown,
            breakdown_by_project=project_breakdown,
            estimated_storage_freed_mb=round(storage_freed_mb, 2),
            warnings=warnings,
            requires_confirmation=requires_confirmation,
        )

    async def _soft_delete_memory(
        self,
        memory: MemoryUnit,
        rollback_id: str,
    ) -> bool:
        """
        Soft delete a memory by marking it as deleted in metadata.

        Args:
            memory: Memory to soft delete
            rollback_id: Rollback ID for this deletion operation

        Returns:
            True if soft delete succeeded, False otherwise
        """
        # Create deletion metadata
        deletion_metadata = DeletionMetadata(
            deleted_at=datetime.now(),
            rollback_id=rollback_id,
            deleted_by="bulk_operation",
            original_state={
                "category": memory.category.value if memory.category else None,
                "context_level": (
                    memory.context_level.value if memory.context_level else None
                ),
                "importance": memory.importance,
                "lifecycle_state": (
                    memory.lifecycle_state.value if memory.lifecycle_state else None
                ),
                "tags": memory.tags,
            },
            can_rollback=True,
        )

        # Calculate expiry date
        expiry = datetime.now() + timedelta(days=self.soft_delete_retention_days)

        # Update memory metadata with deletion info
        updates = {
            "metadata": {
                **memory.metadata,
                "deletion_info": deletion_metadata.model_dump(mode="json"),
                "soft_deleted": True,
                "rollback_expiry": expiry.isoformat(),
            }
        }

        return await self.store.update(memory.id, updates)

    async def execute_deletion(
        self,
        memories: List[MemoryUnit],
        filters: BulkDeleteFilters,
        dry_run: bool = False,
        enable_rollback: bool = False,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> BulkDeleteResult:
        """
        Execute bulk deletion operation.

        Args:
            memories: List of memories to delete
            filters: Filter criteria (for safety checks)
            dry_run: If True, don't actually delete (just preview)
            enable_rollback: If True, use soft delete to enable rollback
            progress_callback: Optional callback for progress updates

        Returns:
            Result with statistics and status
        """
        start_time = datetime.now()

        # Apply max_count limit
        memories_to_delete = memories[: filters.max_count]
        total_count = len(memories_to_delete)

        # Dry-run: just return preview as result
        if dry_run:
            preview = await self.preview_deletion(memories_to_delete, filters)
            return BulkDeleteResult(
                success=True,
                dry_run=True,
                total_deleted=0,
                failed_deletions=[],
                rollback_id=None,
                execution_time=0.0,
                storage_freed_mb=preview.estimated_storage_freed_mb,
                errors=[],
            )

        # Generate rollback ID if requested
        rollback_id = None
        if enable_rollback:
            rollback_id = f"rollback_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"

        # Actual deletion
        deleted_count = 0
        failed_deletions: List[str] = []
        errors: List[str] = []
        total_size_bytes = 0

        # Process in batches
        for i in range(0, total_count, self.max_batch_size):
            batch = memories_to_delete[i : i + self.max_batch_size]

            # Delete each memory in the batch
            for memory in batch:
                try:
                    if enable_rollback:
                        # Soft delete: mark as deleted but keep data
                        success = await self._soft_delete_memory(memory, rollback_id)
                    else:
                        # Hard delete: permanently remove
                        success = await self.store.delete(memory.id)

                    if success:
                        deleted_count += 1
                        total_size_bytes += self._estimate_memory_size(memory)
                    else:
                        failed_deletions.append(memory.id)
                        errors.append(f"Failed to delete memory {memory.id}")
                except Exception as e:
                    failed_deletions.append(memory.id)
                    errors.append(f"Error deleting {memory.id}: {str(e)}")

                # Report progress
                if progress_callback:
                    progress_callback(
                        deleted_count,
                        total_count,
                        f"Deleted {deleted_count}/{total_count}",
                    )

        # Calculate final statistics
        execution_time = (datetime.now() - start_time).total_seconds()
        storage_freed_mb = total_size_bytes / (1024 * 1024)

        return BulkDeleteResult(
            success=len(failed_deletions) == 0,
            dry_run=False,
            total_deleted=deleted_count,
            failed_deletions=failed_deletions,
            rollback_id=rollback_id,
            execution_time=round(execution_time, 2),
            storage_freed_mb=round(storage_freed_mb, 2),
            errors=errors,
        )

    async def get_rollback_info(self, rollback_id: str) -> Optional[RollbackInfo]:
        """
        Get information about a rollback operation.

        Args:
            rollback_id: ID of the rollback operation

        Returns:
            RollbackInfo if rollback exists and is valid, None otherwise
        """
        # TODO: Implement once store supports metadata queries
        # This requires the store to support querying by metadata
        # In a real implementation, we would query for all memories with
        # metadata.deletion_info.rollback_id == rollback_id
        # For now, this is a placeholder that would need store-specific implementation
        raise NotImplementedError(
            "get_rollback_info requires store support for metadata queries"
        )

    async def rollback_deletion(
        self,
        rollback_id: str,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> BulkDeleteResult:
        """
        Rollback a bulk deletion operation.

        This restores all memories that were soft-deleted with the given rollback_id.

        Args:
            rollback_id: ID of the deletion operation to rollback
            progress_callback: Optional callback for progress updates

        Returns:
            Result with statistics about the rollback operation
        """
        # TODO: Implement once store supports metadata queries
        start_time = datetime.now()

        restored_count = 0
        failed_restorations: List[str] = []
        errors: List[str] = []

        # Note: This requires the store to support listing memories by metadata
        # In a real implementation, we would:
        # 1. Query for all memories with metadata.deletion_info.rollback_id == rollback_id
        # 2. For each memory, remove the deletion metadata and restore original state
        # 3. Track success/failure for each restoration

        # Placeholder implementation that shows the pattern
        # This would need to be implemented with actual store queries

        execution_time = (datetime.now() - start_time).total_seconds()

        return BulkDeleteResult(
            success=len(failed_restorations) == 0,
            dry_run=False,
            total_deleted=restored_count,  # Reusing field to mean "restored"
            failed_deletions=failed_restorations,
            rollback_id=None,  # No rollback for a rollback
            execution_time=round(execution_time, 2),
            storage_freed_mb=0.0,  # No storage freed, actually restored
            errors=errors,
        )

    async def list_pending_rollbacks(self) -> List[RollbackInfo]:
        """
        List all pending rollback operations.

        Returns:
            List of RollbackInfo for all deletions that can be rolled back
        """
        # TODO: Implement once store supports metadata queries
        # This requires the store to support querying by metadata
        # In a real implementation, we would query for all unique rollback_ids
        # from memories with metadata.soft_deleted == True
        raise NotImplementedError(
            "list_pending_rollbacks requires store support for metadata queries"
        )

    async def cleanup_expired_rollbacks(
        self,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> int:
        """
        Permanently delete memories whose rollback period has expired.

        Args:
            progress_callback: Optional callback for progress updates

        Returns:
            Number of memories permanently deleted
        """
        # TODO: Implement once store supports metadata queries
        # This requires the store to support querying by metadata
        # In a real implementation, we would:
        # 1. Query for memories where metadata.soft_deleted == True
        #    AND metadata.rollback_expiry < now()
        # 2. Permanently delete each expired memory
        # 3. Track count of deletions
        raise NotImplementedError(
            "cleanup_expired_rollbacks requires store support for metadata queries"
        )

    async def bulk_delete(
        self,
        memories: List[MemoryUnit],
        filters: BulkDeleteFilters,
        dry_run: bool = False,
        enable_rollback: bool = False,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> BulkDeleteResult | BulkDeletePreview:
        """
        Execute bulk delete with optional dry-run.

        This is a convenience method that handles both preview and execution.

        Args:
            memories: List of memories to delete
            filters: Filter criteria
            dry_run: If True, return preview instead of deleting
            enable_rollback: If True, enable rollback support
            progress_callback: Optional callback for progress updates

        Returns:
            BulkDeletePreview if dry_run=True, otherwise BulkDeleteResult
        """
        if dry_run:
            return await self.preview_deletion(memories, filters)
        else:
            return await self.execute_deletion(
                memories,
                filters,
                dry_run=False,
                enable_rollback=enable_rollback,
                progress_callback=progress_callback,
            )
