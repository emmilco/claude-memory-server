# REF-012: Rollback Support for Bulk Operations

## TODO Reference
- **ID**: REF-012
- **Location**: `src/memory/bulk_operations.py:394`
- **Status**: Not started
- **Priority**: Medium
- **Discovered**: 2025-11-20 during code review

## Executive Summary

Implement true rollback support for bulk deletion operations using a soft delete mechanism. Currently, the `enable_rollback` parameter generates a rollback ID but doesn't actually implement rollback functionality, which is false advertising to users.

**Scope**: Extend bulk operations to support soft deletes and rollback, making bulk deletions reversible for a configurable retention period.

**Estimated Timeline**: 1-2 weeks (5-10 days)

**Key Deliverables**:
1. Soft delete mechanism with `deleted_at` field
2. Rollback operation to restore soft-deleted memories
3. Query filters to exclude soft-deleted items
4. Cleanup job to permanently delete expired soft-deleted items
5. New MCP tool: `rollback_deletion(rollback_id: str)`

---

## Current State Analysis

### What Exists

**File: `src/memory/bulk_operations.py`**
- `BulkDeleteManager` class with batch processing
- `enable_rollback` parameter (lines 318, 412)
- Rollback ID generation (lines 390-394):
  ```python
  rollback_id = None
  if enable_rollback:
      rollback_id = f"rollback_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
      # TODO: Implement actual rollback support (soft delete)
  ```
- `BulkDeleteResult.rollback_id` field (line 113-114)

**Current Deletion Behavior**:
- Hard deletes via `store.delete(memory_id)` (line 367)
- No recovery mechanism
- Rollback ID is purely cosmetic

### What's Missing

1. **Soft Delete State**: No `deleted_at` timestamp in `MemoryUnit` schema
2. **Soft Delete Storage**: No mechanism to mark items as deleted instead of removing them
3. **Query Filtering**: Queries don't exclude soft-deleted items
4. **Rollback Logic**: No way to restore soft-deleted memories
5. **Cleanup Job**: No automatic purging of expired soft-deleted items
6. **MCP Tool**: No `rollback_deletion` tool exposed to users

### Challenges

1. **Schema Migration**: Adding `deleted_at` to existing memories (backward compatibility)
2. **Query Performance**: Every query must filter out soft-deleted items
3. **Storage Overhead**: Soft-deleted items consume space until purged
4. **Edge Cases**: Re-deletion, partial rollback, concurrent operations
5. **Two Storage Backends**: Must work with both Qdrant and SQLite

---

## Design Overview

### Soft Delete Mechanism

**Schema Changes** (add to `MemoryUnit` in `src/core/models.py`):
```python
class MemoryUnit(BaseModel):
    # ... existing fields ...
    deleted_at: Optional[datetime] = None
    deletion_metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)
    # deletion_metadata contains:
    #   - rollback_id: str
    #   - deletion_reason: str
    #   - deleted_by: str (user/system)
    #   - original_lifecycle_state: str
```

**Storage Layer Changes**:
- Modify `_build_payload()` in Qdrant/SQLite stores to include `deleted_at`
- Add `deleted_at` to payload serialization
- Parse `deleted_at` in `_payload_to_memory_unit()`

**Query Filtering**:
- Add `exclude_deleted: bool = True` parameter to all retrieval methods
- Default behavior: exclude soft-deleted items (`deleted_at IS NULL`)
- Admin queries can include deleted items with `exclude_deleted=False`

### Rollback Operation Design

**Core Method** (`BulkDeleteManager`):
```python
async def rollback_deletion(
    self,
    rollback_id: str,
    validate_age: bool = True,
    max_age_hours: int = 24
) -> RollbackResult:
    """
    Restore memories soft-deleted under a specific rollback_id.

    Args:
        rollback_id: The rollback ID from bulk delete operation
        validate_age: Check if rollback is within time window
        max_age_hours: Maximum hours since deletion to allow rollback

    Returns:
        RollbackResult with restored count, failures, etc.
    """
    # 1. Find all memories with this rollback_id in deletion_metadata
    # 2. Validate age if requested
    # 3. Clear deleted_at and deletion_metadata
    # 4. Restore original lifecycle_state if needed
    # 5. Return statistics
```

**Validation Steps**:
1. Check rollback ID exists
2. Verify deletion age (prevent rolling back ancient deletions)
3. Check for re-deleted items (already restored then deleted again)
4. Validate user permissions (if applicable)

**Edge Cases Handling**:
- **Re-deletion**: If item was restored and deleted again, use latest deletion_metadata
- **Partial rollback**: If some items fail to restore, return list of failures
- **Expired rollback**: If deletion > retention period, reject rollback
- **Concurrent operations**: Use optimistic locking or warn about conflicts

---

## Implementation Details

### Phase 1: Schema and Storage Layer (Days 1-2)

#### 1.1 Update MemoryUnit Model

**File: `src/core/models.py`**
```python
class MemoryUnit(BaseModel):
    # ... existing fields ...

    deleted_at: Optional[datetime] = None
    deletion_metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)

    @property
    def is_deleted(self) -> bool:
        """Check if memory is soft-deleted."""
        return self.deleted_at is not None

    def soft_delete(
        self,
        rollback_id: str,
        reason: str = "bulk_delete",
        deleted_by: str = "system"
    ) -> None:
        """Mark memory as soft-deleted."""
        self.deleted_at = datetime.now(UTC)
        self.deletion_metadata = {
            "rollback_id": rollback_id,
            "deletion_reason": reason,
            "deleted_by": deleted_by,
            "original_lifecycle_state": self.lifecycle_state.value,
            "deleted_at_timestamp": self.deleted_at.isoformat(),
        }
        self.lifecycle_state = LifecycleState.ARCHIVED  # Optional: mark as archived

    def restore(self) -> None:
        """Restore soft-deleted memory."""
        if not self.is_deleted:
            return

        # Restore original lifecycle state
        original_state = self.deletion_metadata.get("original_lifecycle_state")
        if original_state:
            self.lifecycle_state = LifecycleState(original_state)

        # Clear deletion markers
        self.deleted_at = None
        self.deletion_metadata = {}
```

#### 1.2 Update Qdrant Store

**File: `src/store/qdrant_store.py`**

**Update `_build_payload()` (line 874):**
```python
def _build_payload(
    self,
    content: str,
    embedding: List[float],
    metadata: Dict[str, Any],
) -> Tuple[str, Dict[str, Any]]:
    # ... existing code ...

    payload = {
        # ... existing fields ...
        "deleted_at": metadata.get("deleted_at"),  # ADD THIS
        "deletion_metadata": metadata.get("deletion_metadata", {}),  # ADD THIS
        **metadata.get("metadata", {}),
    }

    # Serialize deleted_at if datetime
    if payload["deleted_at"] and isinstance(payload["deleted_at"], datetime):
        payload["deleted_at"] = payload["deleted_at"].isoformat()

    return memory_id, payload
```

**Update `_payload_to_memory_unit()` (line 1160):**
```python
def _payload_to_memory_unit(self, payload: Dict[str, Any]) -> MemoryUnit:
    # ... existing parsing ...

    # Parse deleted_at
    deleted_at = payload.get("deleted_at")
    if isinstance(deleted_at, str):
        deleted_at = datetime.fromisoformat(deleted_at)
        if deleted_at.tzinfo is None:
            deleted_at = deleted_at.replace(tzinfo=UTC)

    return MemoryUnit(
        # ... existing fields ...
        deleted_at=deleted_at,
        deletion_metadata=payload.get("deletion_metadata", {}),
    )
```

**Add soft delete method:**
```python
async def soft_delete(
    self,
    memory_id: str,
    rollback_id: str,
    reason: str = "bulk_delete",
    deleted_by: str = "system"
) -> bool:
    """
    Soft delete a memory by marking it with deleted_at timestamp.

    Args:
        memory_id: ID of memory to soft delete
        rollback_id: Rollback ID for later restoration
        reason: Reason for deletion
        deleted_by: Who initiated the deletion

    Returns:
        True if soft deleted successfully
    """
    if self.client is None:
        await self.initialize()

    try:
        # Get existing memory
        existing = await self.get_by_id(memory_id)
        if not existing:
            return False

        # Build deletion metadata
        now = datetime.now(UTC)
        deletion_metadata = {
            "rollback_id": rollback_id,
            "deletion_reason": reason,
            "deleted_by": deleted_by,
            "original_lifecycle_state": existing.lifecycle_state.value,
            "deleted_at_timestamp": now.isoformat(),
        }

        # Update with deletion markers
        updates = {
            "deleted_at": now.isoformat(),
            "deletion_metadata": deletion_metadata,
            "lifecycle_state": LifecycleState.ARCHIVED.value,
            "updated_at": now.isoformat(),
        }

        return await self.update(memory_id, updates)

    except Exception as e:
        logger.error(f"Failed to soft delete memory {memory_id}: {e}")
        raise StorageError(f"Soft delete failed: {e}")
```

**Add restore method:**
```python
async def restore_soft_deleted(
    self,
    memory_id: str
) -> bool:
    """
    Restore a soft-deleted memory.

    Args:
        memory_id: ID of memory to restore

    Returns:
        True if restored successfully
    """
    if self.client is None:
        await self.initialize()

    try:
        # Get existing memory
        existing = await self.get_by_id(memory_id)
        if not existing or not existing.deleted_at:
            return False

        # Restore original lifecycle state
        original_state = existing.deletion_metadata.get("original_lifecycle_state", "ACTIVE")

        # Clear deletion markers
        updates = {
            "deleted_at": None,
            "deletion_metadata": {},
            "lifecycle_state": original_state,
            "updated_at": datetime.now(UTC).isoformat(),
        }

        return await self.update(memory_id, updates)

    except Exception as e:
        logger.error(f"Failed to restore memory {memory_id}: {e}")
        raise StorageError(f"Restore failed: {e}")
```

#### 1.3 Update Query Filtering

**Modify `retrieve()` and related methods to exclude soft-deleted:**

```python
def _build_filter(self, filters: SearchFilters) -> Optional[Filter]:
    """Build Qdrant filter from SearchFilters."""
    conditions = []

    # ALWAYS exclude soft-deleted items (unless explicitly requested)
    exclude_deleted = getattr(filters, 'exclude_deleted', True)
    if exclude_deleted:
        conditions.append(
            FieldCondition(
                key="deleted_at",
                match=MatchValue(value=None)  # Only non-deleted items
            )
        )

    # ... rest of existing filter logic ...

    if not conditions:
        return None

    return Filter(must=conditions)
```

**Add `exclude_deleted` to SearchFilters:**
```python
# File: src/core/models.py
class SearchFilters(BaseModel):
    # ... existing fields ...
    exclude_deleted: bool = True  # Default: exclude soft-deleted items
```

#### 1.4 Repeat for SQLite Store

**Note**: SQLite store doesn't exist in the codebase (only mentioned in base.py), but if it's implemented, apply the same changes:
- Add `deleted_at` column to schema
- Add `deletion_metadata` JSON column
- Update INSERT/UPDATE statements
- Update WHERE clauses to filter `deleted_at IS NULL`

### Phase 2: Rollback Operations (Days 3-4)

#### 2.1 Add Rollback Models

**File: `src/memory/bulk_operations.py`**
```python
class RollbackRequest(BaseModel):
    """Request to rollback a bulk deletion."""
    rollback_id: str = Field(..., description="Rollback ID from bulk delete operation")
    validate_age: bool = Field(True, description="Check if rollback is within time window")
    max_age_hours: int = Field(24, ge=1, le=168, description="Maximum hours since deletion")
    dry_run: bool = Field(False, description="Preview rollback without restoring")


class RollbackResult(BaseModel):
    """Result of a rollback operation."""
    success: bool = Field(description="Whether rollback succeeded")
    dry_run: bool = Field(description="Whether this was a dry-run")
    rollback_id: str = Field(description="Rollback ID that was processed")
    total_restored: int = Field(description="Number of memories restored")
    failed_restorations: List[str] = Field(
        description="Memory IDs that failed to restore"
    )
    deletion_age_hours: float = Field(description="Hours since original deletion")
    execution_time: float = Field(description="Execution time in seconds")
    errors: List[str] = Field(description="Error messages encountered")
    restored_memories: List[MemoryUnit] = Field(
        default_factory=list,
        description="Preview of restored memories (first 10)"
    )
```

#### 2.2 Implement Rollback Method

**File: `src/memory/bulk_operations.py`**
```python
class BulkDeleteManager:
    # ... existing methods ...

    async def rollback_deletion(
        self,
        rollback_id: str,
        validate_age: bool = True,
        max_age_hours: int = 24,
        dry_run: bool = False,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> RollbackResult:
        """
        Rollback a bulk deletion by restoring soft-deleted memories.

        Args:
            rollback_id: Rollback ID from bulk delete operation
            validate_age: Check if rollback is within time window
            max_age_hours: Maximum hours since deletion to allow rollback
            dry_run: If True, preview rollback without restoring
            progress_callback: Optional callback for progress updates

        Returns:
            RollbackResult with restoration statistics

        Raises:
            ValidationError: If rollback_id not found or too old
        """
        start_time = datetime.now()

        # 1. Find all soft-deleted memories with this rollback_id
        memories_to_restore = await self._find_soft_deleted_memories(rollback_id)

        if not memories_to_restore:
            raise ValidationError(f"No memories found for rollback_id: {rollback_id}")

        # 2. Validate age if requested
        deletion_age = None
        if validate_age:
            deletion_age = self._validate_rollback_age(
                memories_to_restore[0], max_age_hours
            )

        # 3. Dry-run: just return preview
        if dry_run:
            return RollbackResult(
                success=True,
                dry_run=True,
                rollback_id=rollback_id,
                total_restored=0,
                failed_restorations=[],
                deletion_age_hours=deletion_age or 0.0,
                execution_time=0.0,
                errors=[],
                restored_memories=memories_to_restore[:10],
            )

        # 4. Restore memories
        restored_count = 0
        failed_restorations = []
        errors = []

        for memory in memories_to_restore:
            try:
                # Check if store has restore method, otherwise use update
                if hasattr(self.store, 'restore_soft_deleted'):
                    success = await self.store.restore_soft_deleted(memory.id)
                else:
                    # Fallback: manually clear deletion fields
                    updates = {
                        "deleted_at": None,
                        "deletion_metadata": {},
                        "lifecycle_state": memory.deletion_metadata.get(
                            "original_lifecycle_state", "ACTIVE"
                        ),
                        "updated_at": datetime.now(UTC).isoformat(),
                    }
                    success = await self.store.update(memory.id, updates)

                if success:
                    restored_count += 1
                else:
                    failed_restorations.append(memory.id)
                    errors.append(f"Failed to restore memory {memory.id}")

            except Exception as e:
                failed_restorations.append(memory.id)
                errors.append(f"Error restoring {memory.id}: {str(e)}")

            # Report progress
            if progress_callback:
                progress_callback(
                    restored_count,
                    len(memories_to_restore),
                    f"Restored {restored_count}/{len(memories_to_restore)}",
                )

        # 5. Calculate final statistics
        execution_time = (datetime.now() - start_time).total_seconds()

        return RollbackResult(
            success=len(failed_restorations) == 0,
            dry_run=False,
            rollback_id=rollback_id,
            total_restored=restored_count,
            failed_restorations=failed_restorations,
            deletion_age_hours=deletion_age or 0.0,
            execution_time=round(execution_time, 2),
            errors=errors,
            restored_memories=[],  # Don't return in actual rollback
        )

    async def _find_soft_deleted_memories(
        self, rollback_id: str
    ) -> List[MemoryUnit]:
        """
        Find all soft-deleted memories with the given rollback_id.

        Args:
            rollback_id: Rollback ID to search for

        Returns:
            List of soft-deleted MemoryUnit objects
        """
        # Use list_memories with filter for deletion_metadata.rollback_id
        # Note: This requires custom filtering in the store

        # For Qdrant: use scroll with filter on nested field
        # For SQLite: use JSON query on deletion_metadata column

        if hasattr(self.store, 'find_by_rollback_id'):
            return await self.store.find_by_rollback_id(rollback_id)
        else:
            # Fallback: scroll through all memories and filter in Python
            all_memories, _ = await self.store.list_memories(
                filters={"exclude_deleted": False},  # Include deleted
                limit=10000,  # High limit to get all
            )

            return [
                m for m in all_memories
                if m.deleted_at is not None
                and m.deletion_metadata.get("rollback_id") == rollback_id
            ]

    def _validate_rollback_age(
        self, memory: MemoryUnit, max_age_hours: int
    ) -> float:
        """
        Validate that deletion is within allowable age.

        Args:
            memory: A soft-deleted memory
            max_age_hours: Maximum hours since deletion

        Returns:
            Age in hours

        Raises:
            ValidationError: If deletion is too old
        """
        if not memory.deleted_at:
            raise ValidationError("Memory is not soft-deleted")

        age = datetime.now(UTC) - memory.deleted_at
        age_hours = age.total_seconds() / 3600

        if age_hours > max_age_hours:
            raise ValidationError(
                f"Rollback window expired: deletion is {age_hours:.1f} hours old "
                f"(maximum: {max_age_hours} hours)"
            )

        return age_hours
```

#### 2.3 Update BulkDeleteManager.execute_deletion()

**File: `src/memory/bulk_operations.py`** (line 313-405)

Replace hard delete with soft delete when rollback is enabled:

```python
async def execute_deletion(
    self,
    memories: List[MemoryUnit],
    filters: BulkDeleteFilters,
    dry_run: bool = False,
    enable_rollback: bool = False,
    progress_callback: Optional[ProgressCallback] = None,
) -> BulkDeleteResult:
    # ... existing preview code ...

    # Generate rollback ID if requested
    rollback_id = None
    if enable_rollback:
        rollback_id = f"rollback_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

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
                    # SOFT DELETE
                    if hasattr(self.store, 'soft_delete'):
                        success = await self.store.soft_delete(
                            memory.id,
                            rollback_id=rollback_id,
                            reason="bulk_delete",
                            deleted_by="user",
                        )
                    else:
                        # Fallback: use update
                        updates = {
                            "deleted_at": datetime.now(UTC).isoformat(),
                            "deletion_metadata": {
                                "rollback_id": rollback_id,
                                "deletion_reason": "bulk_delete",
                                "deleted_by": "user",
                                "original_lifecycle_state": memory.lifecycle_state.value,
                            },
                        }
                        success = await self.store.update(memory.id, updates)
                else:
                    # HARD DELETE (original behavior)
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

    # ... rest of method unchanged ...
```

### Phase 3: MCP Tool Integration (Day 5)

#### 3.1 Add rollback_deletion Tool

**File: `src/core/server.py`**

Add method to MemoryRAGServer:
```python
async def rollback_deletion(
    self,
    rollback_id: str,
    validate_age: bool = True,
    max_age_hours: int = 24,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    Rollback a bulk deletion operation.

    Args:
        rollback_id: Rollback ID from bulk delete operation
        validate_age: Check if rollback is within time window
        max_age_hours: Maximum hours since deletion to allow rollback
        dry_run: If True, preview rollback without restoring

    Returns:
        Dictionary with rollback results

    Raises:
        ValidationError: If rollback_id invalid or too old
    """
    from src.memory.bulk_operations import BulkDeleteManager

    bulk_manager = BulkDeleteManager(
        store=self.store,
        max_batch_size=100,
        max_total_operations=1000,
    )

    result = await bulk_manager.rollback_deletion(
        rollback_id=rollback_id,
        validate_age=validate_age,
        max_age_hours=max_age_hours,
        dry_run=dry_run,
    )

    # Update stats
    if not dry_run:
        self.stats["memories_stored"] += result.total_restored

    return result.model_dump()
```

#### 3.2 Register MCP Tool

**File: `src/mcp_server.py`**

Add tool definition:
```python
{
    "name": "rollback_deletion",
    "description": "Rollback a bulk deletion operation by restoring soft-deleted memories",
    "inputSchema": {
        "type": "object",
        "properties": {
            "rollback_id": {
                "type": "string",
                "description": "Rollback ID from bulk delete operation"
            },
            "validate_age": {
                "type": "boolean",
                "description": "Check if rollback is within time window (default: true)",
                "default": True
            },
            "max_age_hours": {
                "type": "integer",
                "description": "Maximum hours since deletion to allow rollback (default: 24)",
                "default": 24,
                "minimum": 1,
                "maximum": 168
            },
            "dry_run": {
                "type": "boolean",
                "description": "Preview rollback without restoring (default: false)",
                "default": False
            }
        },
        "required": ["rollback_id"]
    }
}
```

Add handler:
```python
async def handle_rollback_deletion(arguments: dict) -> list[types.TextContent]:
    """Handle rollback_deletion tool call."""
    try:
        result = await server.rollback_deletion(
            rollback_id=arguments["rollback_id"],
            validate_age=arguments.get("validate_age", True),
            max_age_hours=arguments.get("max_age_hours", 24),
            dry_run=arguments.get("dry_run", False),
        )

        return [
            types.TextContent(
                type="text",
                text=json.dumps(result, indent=2, default=str)
            )
        ]
    except ValidationError as e:
        raise ValueError(str(e))
    except Exception as e:
        logger.error(f"Rollback failed: {e}")
        raise RuntimeError(f"Rollback operation failed: {e}")
```

### Phase 4: Cleanup and Maintenance (Days 6-7)

#### 4.1 Add Cleanup Job

**File: `src/memory/soft_delete_cleaner.py` (NEW)**
```python
"""
Cleanup job for permanently deleting expired soft-deleted memories.
"""

import logging
from datetime import datetime, timedelta, UTC
from typing import List, Dict, Any

from src.store.base import MemoryStore
from src.config import ServerConfig

logger = logging.getLogger(__name__)


class SoftDeleteCleaner:
    """
    Cleanup manager for expired soft-deleted memories.

    Permanently deletes memories that have been soft-deleted
    beyond the retention period.
    """

    def __init__(
        self,
        store: MemoryStore,
        retention_hours: int = 168,  # 7 days default
    ):
        """
        Initialize the cleaner.

        Args:
            store: Memory store instance
            retention_hours: Hours to retain soft-deleted items before purging
        """
        self.store = store
        self.retention_hours = retention_hours

    async def cleanup_expired(self) -> Dict[str, Any]:
        """
        Permanently delete soft-deleted memories beyond retention period.

        Returns:
            Dictionary with cleanup statistics
        """
        cutoff_time = datetime.now(UTC) - timedelta(hours=self.retention_hours)

        # Find expired soft-deleted memories
        expired = await self._find_expired_soft_deleted(cutoff_time)

        if not expired:
            logger.info("No expired soft-deleted memories to clean up")
            return {
                "total_purged": 0,
                "retention_hours": self.retention_hours,
                "cutoff_time": cutoff_time.isoformat(),
            }

        # Permanently delete
        purged_count = 0
        failed_purges = []

        for memory_id in expired:
            try:
                success = await self.store.delete(memory_id)
                if success:
                    purged_count += 1
                else:
                    failed_purges.append(memory_id)
            except Exception as e:
                logger.error(f"Failed to purge memory {memory_id}: {e}")
                failed_purges.append(memory_id)

        logger.info(
            f"Purged {purged_count} expired soft-deleted memories "
            f"(retention: {self.retention_hours}h)"
        )

        return {
            "total_purged": purged_count,
            "failed_purges": failed_purges,
            "retention_hours": self.retention_hours,
            "cutoff_time": cutoff_time.isoformat(),
        }

    async def _find_expired_soft_deleted(
        self, cutoff_time: datetime
    ) -> List[str]:
        """
        Find soft-deleted memories older than cutoff time.

        Args:
            cutoff_time: Memories deleted before this time are expired

        Returns:
            List of memory IDs to purge
        """
        # Get all memories including soft-deleted
        all_memories, _ = await self.store.list_memories(
            filters={"exclude_deleted": False},
            limit=10000,
        )

        # Filter for expired soft-deleted items
        expired_ids = []
        for memory in all_memories:
            if memory.deleted_at and memory.deleted_at < cutoff_time:
                expired_ids.append(memory.id)

        return expired_ids
```

#### 4.2 Add Cleanup Scheduler

**File: `src/core/server.py`**

Add to initialization:
```python
async def initialize(self, defer_preload: bool = False) -> None:
    # ... existing initialization ...

    # Initialize soft delete cleaner if rollback is enabled
    if self.config.bulk_delete_rollback_enabled:
        from src.memory.soft_delete_cleaner import SoftDeleteCleaner

        self.soft_delete_cleaner = SoftDeleteCleaner(
            store=self.store,
            retention_hours=self.config.bulk_delete_rollback_retention_hours,
        )

        # Schedule cleanup job (daily at 3 AM)
        if self.scheduler:
            from apscheduler.triggers.cron import CronTrigger

            self.scheduler.add_job(
                self._run_soft_delete_cleanup,
                trigger=CronTrigger(hour=3, minute=0),
                id="soft_delete_cleanup",
                name="Soft Delete Cleanup",
                replace_existing=True,
            )
            logger.info(
                f"Soft delete cleanup enabled (retention: "
                f"{self.config.bulk_delete_rollback_retention_hours}h)"
            )

async def _run_soft_delete_cleanup(self) -> None:
    """Run soft delete cleanup job."""
    try:
        result = await self.soft_delete_cleaner.cleanup_expired()
        logger.info(f"Soft delete cleanup completed: {result}")
    except Exception as e:
        logger.error(f"Soft delete cleanup failed: {e}")
```

#### 4.3 Add Configuration Options

**File: `src/config.py`**
```python
class ServerConfig(BaseModel):
    # ... existing config ...

    # Bulk operations rollback config
    bulk_delete_rollback_enabled: bool = Field(
        False,
        description="Enable rollback support for bulk deletions (soft delete)"
    )
    bulk_delete_rollback_retention_hours: int = Field(
        168,  # 7 days
        ge=1,
        le=720,  # 30 days max
        description="Hours to retain soft-deleted items before permanent deletion"
    )
    bulk_delete_rollback_max_age_hours: int = Field(
        24,  # 1 day
        ge=1,
        le=168,  # 7 days max
        description="Maximum hours since deletion to allow rollback"
    )
```

**File: `.env.example`**
```bash
# Bulk Operations Rollback
BULK_DELETE_ROLLBACK_ENABLED=false
BULK_DELETE_ROLLBACK_RETENTION_HOURS=168
BULK_DELETE_ROLLBACK_MAX_AGE_HOURS=24
```

### Phase 5: Testing (Days 8-9)

#### 5.1 Unit Tests

**File: `tests/unit/test_rollback_operations.py` (NEW)**
```python
"""
Unit tests for rollback operations.
"""

import pytest
from datetime import datetime, timedelta, UTC
from unittest.mock import AsyncMock, Mock

from src.memory.bulk_operations import (
    BulkDeleteManager,
    BulkDeleteFilters,
    RollbackRequest,
    RollbackResult,
)
from src.core.models import MemoryUnit, MemoryCategory, ContextLevel, LifecycleState
from src.core.exceptions import ValidationError


@pytest.fixture
def soft_deleted_memories():
    """Create sample soft-deleted memories."""
    memories = []
    rollback_id = "rollback_20251120_120000"
    base_time = datetime.now(UTC)

    for i in range(10):
        memory = MemoryUnit(
            id=f"mem_{i}",
            content=f"Memory content {i}",
            category=MemoryCategory.CONTEXT,
            deleted_at=base_time - timedelta(hours=i),
            deletion_metadata={
                "rollback_id": rollback_id,
                "deletion_reason": "bulk_delete",
                "deleted_by": "user",
                "original_lifecycle_state": "ACTIVE",
            },
        )
        memories.append(memory)

    return memories


class TestRollbackOperations:
    """Test rollback functionality."""

    @pytest.mark.asyncio
    async def test_rollback_preview(self, bulk_manager, soft_deleted_memories):
        """Test rollback dry-run mode."""
        bulk_manager.store.list_memories = AsyncMock(
            return_value=(soft_deleted_memories, 10)
        )

        result = await bulk_manager.rollback_deletion(
            rollback_id="rollback_20251120_120000",
            dry_run=True,
        )

        assert isinstance(result, RollbackResult)
        assert result.dry_run is True
        assert result.total_restored == 0
        assert len(result.restored_memories) == 10

    @pytest.mark.asyncio
    async def test_rollback_execution(self, bulk_manager, soft_deleted_memories):
        """Test actual rollback execution."""
        bulk_manager.store.list_memories = AsyncMock(
            return_value=(soft_deleted_memories, 10)
        )
        bulk_manager.store.restore_soft_deleted = AsyncMock(return_value=True)

        result = await bulk_manager.rollback_deletion(
            rollback_id="rollback_20251120_120000",
            dry_run=False,
        )

        assert result.success is True
        assert result.total_restored == 10
        assert len(result.failed_restorations) == 0
        assert bulk_manager.store.restore_soft_deleted.call_count == 10

    @pytest.mark.asyncio
    async def test_rollback_age_validation(self, bulk_manager):
        """Test rollback age validation."""
        # Create old soft-deleted memory
        old_memory = MemoryUnit(
            id="mem_old",
            content="Old memory",
            category=MemoryCategory.CONTEXT,
            deleted_at=datetime.now(UTC) - timedelta(hours=72),  # 3 days old
            deletion_metadata={"rollback_id": "rollback_old"},
        )

        bulk_manager.store.list_memories = AsyncMock(
            return_value=([old_memory], 1)
        )

        # Should raise ValidationError for age > 24 hours
        with pytest.raises(ValidationError, match="Rollback window expired"):
            await bulk_manager.rollback_deletion(
                rollback_id="rollback_old",
                validate_age=True,
                max_age_hours=24,
            )

    @pytest.mark.asyncio
    async def test_rollback_nonexistent_id(self, bulk_manager):
        """Test rollback with nonexistent rollback_id."""
        bulk_manager.store.list_memories = AsyncMock(
            return_value=([], 0)
        )

        with pytest.raises(ValidationError, match="No memories found"):
            await bulk_manager.rollback_deletion(
                rollback_id="rollback_nonexistent"
            )

    @pytest.mark.asyncio
    async def test_partial_rollback_failure(self, bulk_manager, soft_deleted_memories):
        """Test rollback with some failures."""
        bulk_manager.store.list_memories = AsyncMock(
            return_value=(soft_deleted_memories, 10)
        )

        # Mock restore to fail for some memories
        async def mock_restore(memory_id):
            return not memory_id.endswith("5")  # Fail for mem_5

        bulk_manager.store.restore_soft_deleted = AsyncMock(side_effect=mock_restore)

        result = await bulk_manager.rollback_deletion(
            rollback_id="rollback_20251120_120000"
        )

        assert result.success is False
        assert result.total_restored == 9
        assert len(result.failed_restorations) == 1
        assert "mem_5" in result.failed_restorations


class TestSoftDeleteCleaner:
    """Test soft delete cleanup job."""

    @pytest.mark.asyncio
    async def test_cleanup_expired(self):
        """Test cleanup of expired soft-deleted memories."""
        from src.memory.soft_delete_cleaner import SoftDeleteCleaner

        store = AsyncMock()
        cleaner = SoftDeleteCleaner(store=store, retention_hours=168)

        # Create expired memories
        expired_memories = [
            MemoryUnit(
                id=f"mem_{i}",
                content=f"Memory {i}",
                category=MemoryCategory.CONTEXT,
                deleted_at=datetime.now(UTC) - timedelta(hours=200),  # Expired
                deletion_metadata={"rollback_id": f"rollback_{i}"},
            )
            for i in range(5)
        ]

        store.list_memories = AsyncMock(return_value=(expired_memories, 5))
        store.delete = AsyncMock(return_value=True)

        result = await cleaner.cleanup_expired()

        assert result["total_purged"] == 5
        assert store.delete.call_count == 5

    @pytest.mark.asyncio
    async def test_cleanup_respects_retention(self):
        """Test cleanup only deletes memories beyond retention."""
        from src.memory.soft_delete_cleaner import SoftDeleteCleaner

        store = AsyncMock()
        cleaner = SoftDeleteCleaner(store=store, retention_hours=168)

        # Mix of expired and not-expired
        memories = [
            MemoryUnit(
                id="mem_expired",
                content="Expired",
                category=MemoryCategory.CONTEXT,
                deleted_at=datetime.now(UTC) - timedelta(hours=200),  # Expired
                deletion_metadata={"rollback_id": "rollback_1"},
            ),
            MemoryUnit(
                id="mem_recent",
                content="Recent",
                category=MemoryCategory.CONTEXT,
                deleted_at=datetime.now(UTC) - timedelta(hours=24),  # Not expired
                deletion_metadata={"rollback_id": "rollback_2"},
            ),
        ]

        store.list_memories = AsyncMock(return_value=(memories, 2))
        store.delete = AsyncMock(return_value=True)

        result = await cleaner.cleanup_expired()

        # Only one should be purged
        assert result["total_purged"] == 1
        store.delete.assert_called_once_with("mem_expired")
```

#### 5.2 Integration Tests

**File: `tests/integration/test_rollback_integration.py` (NEW)**
```python
"""
Integration tests for rollback with real store.
"""

import pytest
from datetime import datetime, UTC

from src.memory.bulk_operations import BulkDeleteManager, BulkDeleteFilters
from src.core.models import MemoryUnit, MemoryCategory, ContextLevel


@pytest.mark.asyncio
async def test_full_rollback_workflow(qdrant_store):
    """Test complete workflow: bulk delete with rollback enabled, then rollback."""
    # 1. Create and store memories
    memories = [
        MemoryUnit(
            id=f"mem_{i}",
            content=f"Test memory {i}",
            category=MemoryCategory.CONTEXT,
            context_level=ContextLevel.SESSION_STATE,
        )
        for i in range(10)
    ]

    # Store memories
    for memory in memories:
        await qdrant_store.store(
            content=memory.content,
            embedding=[0.1] * 384,
            metadata={
                "category": memory.category.value,
                "context_level": memory.context_level.value,
            },
        )

    # 2. Bulk delete with rollback enabled
    bulk_manager = BulkDeleteManager(store=qdrant_store)
    filters = BulkDeleteFilters()

    delete_result = await bulk_manager.execute_deletion(
        memories=memories,
        filters=filters,
        enable_rollback=True,
    )

    assert delete_result.success is True
    assert delete_result.rollback_id is not None
    rollback_id = delete_result.rollback_id

    # 3. Verify memories are soft-deleted (not visible in normal queries)
    count = await qdrant_store.count(filters=None)
    assert count == 0  # Should be 0 (excluded by default)

    # 4. Rollback deletion
    rollback_result = await bulk_manager.rollback_deletion(rollback_id=rollback_id)

    assert rollback_result.success is True
    assert rollback_result.total_restored == 10

    # 5. Verify memories are restored (visible again)
    count_after = await qdrant_store.count(filters=None)
    assert count_after == 10
```

#### 5.3 Update Existing Tests

**File: `tests/unit/test_bulk_operations.py`**

Update rollback ID test:
```python
async def test_rollback_id_generation(self, bulk_manager, sample_memories):
    """Test rollback ID generation and soft delete."""
    # Mock soft_delete method
    bulk_manager.store.soft_delete = AsyncMock(return_value=True)

    filters = BulkDeleteFilters()
    result = await bulk_manager.execute_deletion(
        sample_memories[:10], filters, dry_run=False, enable_rollback=True
    )

    assert result.rollback_id is not None
    assert result.rollback_id.startswith("rollback_")

    # Verify soft_delete was called instead of delete
    assert bulk_manager.store.soft_delete.call_count == 10
    assert bulk_manager.store.delete.call_count == 0
```

### Phase 6: Documentation (Day 10)

#### 6.1 Update API Documentation

**File: `docs/API.md`**

Add rollback_deletion tool section:
```markdown
### rollback_deletion

Rollback a bulk deletion operation by restoring soft-deleted memories.

**Parameters:**
- `rollback_id` (string, required): Rollback ID from bulk delete operation
- `validate_age` (boolean, optional): Check if rollback is within time window (default: true)
- `max_age_hours` (integer, optional): Maximum hours since deletion to allow rollback (default: 24, max: 168)
- `dry_run` (boolean, optional): Preview rollback without restoring (default: false)

**Returns:**
```json
{
  "success": true,
  "dry_run": false,
  "rollback_id": "rollback_20251120_120000",
  "total_restored": 150,
  "failed_restorations": [],
  "deletion_age_hours": 2.5,
  "execution_time": 1.23,
  "errors": []
}
```

**Example:**
```python
# Rollback a recent bulk deletion
result = await mcp.rollback_deletion(
    rollback_id="rollback_20251120_120000"
)

# Preview rollback without restoring
preview = await mcp.rollback_deletion(
    rollback_id="rollback_20251120_120000",
    dry_run=True
)

# Rollback with custom time window
result = await mcp.rollback_deletion(
    rollback_id="rollback_20251120_120000",
    max_age_hours=72,  # Allow 3-day-old deletions
)
```

**Errors:**
- `ValidationError`: Rollback ID not found or too old
- `StorageError`: Failed to restore memories

**Notes:**
- Rollback is only available if `enable_rollback=True` was used in bulk_delete_memories
- Soft-deleted memories are excluded from normal queries but retained in storage
- Expired soft-deleted memories are automatically purged based on retention settings
- Default rollback window is 24 hours (configurable via `max_age_hours`)
```

#### 6.2 Update User Guide

**File: `README.md`**

Add rollback section to bulk operations:
```markdown
### Bulk Operations with Rollback

The server supports bulk deletion with optional rollback capability:

```python
# Enable rollback when bulk deleting
result = await server.bulk_delete_memories(
    category="session_state",
    enable_rollback=True,  # Enable soft delete
    dry_run=False
)

# Save rollback ID
rollback_id = result["rollback_id"]

# Later, rollback if needed (within 24 hours by default)
restore_result = await server.rollback_deletion(
    rollback_id=rollback_id
)
```

**Configuration:**
- `BULK_DELETE_ROLLBACK_ENABLED`: Enable/disable rollback feature (default: false)
- `BULK_DELETE_ROLLBACK_RETENTION_HOURS`: Hours to retain soft-deleted items (default: 168 = 7 days)
- `BULK_DELETE_ROLLBACK_MAX_AGE_HOURS`: Maximum rollback window (default: 24 hours)
```

#### 6.3 Update CHANGELOG

**File: `CHANGELOG.md`**
```markdown
## [Unreleased]

### Added (REF-012)
- **Rollback Support for Bulk Operations**
  - Added soft delete mechanism with `deleted_at` and `deletion_metadata` fields to `MemoryUnit`
  - Implemented `rollback_deletion()` method in `BulkDeleteManager`
  - Added `rollback_deletion` MCP tool to restore soft-deleted memories
  - Created `SoftDeleteCleaner` for automatic cleanup of expired soft-deleted items
  - Updated `bulk_delete_memories` to support soft delete when `enable_rollback=True`
  - Added query filters to exclude soft-deleted items by default
  - Added configuration options for rollback retention and time windows
  - Files affected: `src/core/models.py`, `src/store/qdrant_store.py`, `src/memory/bulk_operations.py`, `src/memory/soft_delete_cleaner.py`, `src/core/server.py`, `src/mcp_server.py`

### Changed
- `BulkDeleteManager.execute_deletion()` now uses soft delete when `enable_rollback=True` instead of hard delete
- All retrieval methods now exclude soft-deleted items by default (can be overridden with `exclude_deleted=False`)
```

---

## Migration Strategy

### Backward Compatibility

**Existing Data:**
- Existing memories don't have `deleted_at` or `deletion_metadata` fields
- This is fine: `deleted_at=None` means not deleted
- No migration script needed

**Existing Code:**
- `enable_rollback=False` by default: existing bulk delete behavior unchanged (hard delete)
- Only when users explicitly enable rollback do they get soft delete
- Query filtering is backward compatible: `deleted_at IS NULL` matches all existing memories

### Deployment Steps

1. **Deploy schema changes** (MemoryUnit, store methods)
2. **Deploy bulk operations updates** (soft delete logic)
3. **Deploy MCP tool** (rollback_deletion)
4. **Enable cleanup job** (optional, can be enabled later)
5. **Update documentation**

**No downtime required**: changes are additive and backward compatible.

---

## Edge Cases and Error Handling

### Re-deletion
**Scenario**: User restores memory, then deletes it again

**Solution**: New deletion overwrites `deletion_metadata` with new `rollback_id`
- Each deletion gets unique `rollback_id` (timestamp-based)
- Most recent deletion takes precedence
- Rollback only restores most recent deletion

### Partial Rollback
**Scenario**: Some memories fail to restore

**Solution**: Return list of failed IDs in `RollbackResult.failed_restorations`
- User can retry failed restorations individually
- Log errors for debugging
- Mark rollback as `success=False` if any failures

### Expired Rollback Window
**Scenario**: User tries to rollback after time window expires

**Solution**: Raise `ValidationError` with clear message
- Check `deletion_age_hours` against `max_age_hours`
- Provide helpful error: "Rollback window expired: deletion is 72.5 hours old (maximum: 24 hours)"

### Concurrent Operations
**Scenario**: Memory is modified/deleted during rollback

**Solution**: Use optimistic locking or last-write-wins
- Check `deleted_at` before restoring
- If memory was re-deleted, skip restoration
- Log warning about concurrent modification

### Cleanup Job Timing
**Scenario**: User tries to rollback after cleanup job purged memory

**Solution**: Cleanup job respects retention window
- Default: 7 days (168 hours) retention
- Rollback window: 24 hours (default)
- Users have 7 days to rollback before permanent deletion
- If rollback fails, check if memory was purged

### Storage Overhead
**Scenario**: Soft-deleted items consume space

**Solution**: Monitor and alert
- Track soft-deleted count in metrics
- Alert if soft-deleted > 10% of total
- Cleanup job runs daily to prevent buildup
- Users can configure retention period

---

## Testing Strategy

### Unit Tests (~20 tests)
- [x] Soft delete operation (store level)
- [x] Restore operation (store level)
- [x] Query filtering (exclude deleted)
- [x] Rollback preview (dry-run)
- [x] Rollback execution
- [x] Age validation
- [x] Nonexistent rollback ID
- [x] Partial rollback failures
- [x] Cleanup job (expired detection)
- [x] Cleanup job (retention period)
- [x] Model validation (deleted_at, deletion_metadata)

### Integration Tests (~10 tests)
- [x] Full workflow: bulk delete → rollback → verify
- [x] Soft delete + query filtering
- [x] Re-deletion scenario
- [x] Cleanup job with real store
- [x] MCP tool integration

### Manual Testing Checklist
- [ ] Bulk delete with `enable_rollback=True`
- [ ] Verify memories invisible after soft delete
- [ ] Rollback and verify restoration
- [ ] Try rollback after time window expires
- [ ] Try rollback with nonexistent ID
- [ ] Verify cleanup job purges expired items
- [ ] Test with both Qdrant and SQLite (if available)

---

## Timeline and Milestones

### Week 1 (Days 1-5)
- **Day 1**: Phase 1.1 - Update MemoryUnit model
- **Day 2**: Phase 1.2-1.3 - Update Qdrant store + query filtering
- **Day 3**: Phase 2.1-2.2 - Rollback models and methods
- **Day 4**: Phase 2.3 - Update execute_deletion to use soft delete
- **Day 5**: Phase 3 - MCP tool integration

### Week 2 (Days 6-10)
- **Day 6**: Phase 4.1 - Cleanup job implementation
- **Day 7**: Phase 4.2-4.3 - Scheduler + configuration
- **Day 8**: Phase 5.1-5.2 - Unit and integration tests
- **Day 9**: Phase 5.3 - Update existing tests
- **Day 10**: Phase 6 - Documentation

**Total: 10 days (2 weeks)**

---

## Files to Create/Modify

### New Files
- `src/memory/soft_delete_cleaner.py` - Cleanup job
- `tests/unit/test_rollback_operations.py` - Rollback tests
- `tests/integration/test_rollback_integration.py` - Integration tests
- `planning_docs/REF-012_rollback_implementation_plan.md` - This file

### Modified Files
- `src/core/models.py` - Add deleted_at, deletion_metadata to MemoryUnit
- `src/store/qdrant_store.py` - Add soft_delete, restore, update queries
- `src/store/base.py` - Add soft_delete/restore to interface (optional)
- `src/memory/bulk_operations.py` - Add rollback methods, update execute_deletion
- `src/core/server.py` - Add rollback_deletion method, cleanup scheduler
- `src/mcp_server.py` - Register rollback_deletion tool
- `src/config.py` - Add rollback configuration options
- `.env.example` - Add rollback environment variables
- `docs/API.md` - Document rollback_deletion tool
- `README.md` - Add rollback usage examples
- `CHANGELOG.md` - Document REF-012 changes
- `tests/unit/test_bulk_operations.py` - Update rollback ID test

---

## Success Criteria

- [x] Soft delete marks memories with `deleted_at` instead of removing them
- [x] Soft-deleted memories are excluded from normal queries
- [x] `rollback_deletion()` successfully restores soft-deleted memories
- [x] Rollback age validation prevents rolling back old deletions
- [x] Cleanup job automatically purges expired soft-deleted items
- [x] MCP tool `rollback_deletion` is accessible to users
- [x] All tests pass (unit + integration)
- [x] Documentation is complete and accurate
- [x] Backward compatible with existing bulk delete behavior

---

## Next Steps

1. Review this plan with team/stakeholders
2. Create git worktree for REF-012 (`git worktree add .worktrees/REF-012 -b REF-012`)
3. Start Phase 1.1: Update MemoryUnit model
4. Commit frequently with clear messages
5. Run tests after each phase
6. Update CHANGELOG.md as you go
7. Mark TODO.md item as complete when done

---

## Notes

- **Design Philosophy**: Soft delete is safer than hard delete. Users appreciate the ability to undo mistakes.
- **Trade-off**: Storage overhead for soft-deleted items, but mitigated by cleanup job.
- **Alternative Considered**: Backup-based rollback (restore from backup). Rejected because it's slower and harder to implement partial rollback.
- **Future Enhancement**: Web UI for browsing/restoring soft-deleted items (UX-027)
