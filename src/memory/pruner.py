"""Memory pruning service for cleaning up stale memories."""

import logging
from typing import Dict, Any, List, Optional, TYPE_CHECKING
from datetime import datetime, UTC, timedelta

from src.config import ServerConfig
from src.core.models import ContextLevel

if TYPE_CHECKING:
    from src.store.base import MemoryStore

logger = logging.getLogger(__name__)


class PruneResult:
    """Result of a pruning operation."""

    def __init__(self):
        self.memories_deleted = 0
        self.memories_scanned = 0
        self.storage_freed_bytes = 0
        self.errors: List[str] = []
        self.deleted_ids: List[str] = []

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "memories_deleted": self.memories_deleted,
            "memories_scanned": self.memories_scanned,
            "storage_freed_bytes": self.storage_freed_bytes,
            "errors": self.errors,
            "deleted_count": len(self.deleted_ids),
        }


class MemoryPruner:
    """
    Memory pruning service.

    Handles:
    - Auto-expiration of SESSION_STATE memories
    - Cleanup of stale memories
    - Storage optimization
    - Usage tracking cleanup
    """

    def __init__(self, config: ServerConfig, storage_backend: "MemoryStore"):
        """
        Initialize memory pruner.

        Args:
            config: Server configuration
            storage_backend: Storage backend (SQLite or Qdrant store)
        """
        self.config = config
        self.storage = storage_backend

        # Statistics
        self.stats = {
            "total_prunes": 0,
            "total_deleted": 0,
            "last_prune_time": None,
            "last_prune_deleted": 0,
        }

    async def find_expired_sessions(
        self, ttl_hours: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Find SESSION_STATE memories that have expired.

        Args:
            ttl_hours: Time-to-live in hours (uses config default if None)

        Returns:
            List of expired memory dicts with id, created_at, last_used
        """
        if ttl_hours is None:
            ttl_hours = self.config.memory.session_state_ttl_hours

        # Calculate cutoff time
        cutoff_time = datetime.now(UTC) - timedelta(hours=ttl_hours)

        # Query storage for SESSION_STATE memories older than cutoff
        if hasattr(self.storage, "find_memories_by_criteria"):
            expired = await self.storage.find_memories_by_criteria(
                context_level=ContextLevel.SESSION_STATE,
                older_than=cutoff_time,
            )
        else:
            # Fallback: query all memories and filter
            expired = await self._find_expired_fallback(cutoff_time)

        return expired

    async def _find_expired_fallback(
        self, cutoff_time: datetime
    ) -> List[Dict[str, Any]]:
        """
        Fallback method to find expired memories.

        Queries all SESSION_STATE memories and filters by age.
        """
        expired = []

        try:
            # Get all memories (this is inefficient but works as fallback)
            if hasattr(self.storage, "get_all_memories"):
                all_memories = await self.storage.get_all_memories()

                for memory in all_memories:
                    # Check if SESSION_STATE
                    if memory.get("context_level") != "SESSION_STATE":
                        continue

                    # Check age - use last_used if available, otherwise created_at
                    last_used = memory.get("last_used")
                    created_at = memory.get("created_at")

                    reference_time = last_used or created_at
                    if not reference_time:
                        continue

                    # Parse datetime if string
                    if isinstance(reference_time, str):
                        reference_time = datetime.fromisoformat(reference_time)

                    # Check if expired
                    if reference_time < cutoff_time:
                        expired.append(
                            {
                                "id": memory.get("id"),
                                "created_at": created_at,
                                "last_used": last_used,
                            }
                        )

        except Exception as e:
            logger.error(f"Error in fallback expired search: {e}")

        return expired

    async def find_stale_memories(self, days_unused: int = 30) -> List[Dict[str, Any]]:
        """
        Find memories that haven't been used in a long time.

        Args:
            days_unused: Number of days without usage

        Returns:
            List of stale memory dicts
        """
        cutoff_time = datetime.now(UTC) - timedelta(days=days_unused)

        if hasattr(self.storage, "find_unused_memories"):
            return await self.storage.find_unused_memories(
                cutoff_time=cutoff_time,
                exclude_context_levels=[
                    ContextLevel.USER_PREFERENCE,
                    ContextLevel.PROJECT_CONTEXT,
                ],
            )

        return []

    async def prune_expired(
        self,
        dry_run: bool = False,
        ttl_hours: Optional[int] = None,
        safety_check: bool = True,
    ) -> PruneResult:
        """
        Prune expired SESSION_STATE memories.

        Args:
            dry_run: If True, don't actually delete, just report what would be deleted
            ttl_hours: Time-to-live in hours (uses config default if None)
            safety_check: If True, never delete memories used in last 24h

        Returns:
            PruneResult with statistics
        """
        result = PruneResult()

        try:
            # Find expired memories
            expired = await self.find_expired_sessions(ttl_hours)
            result.memories_scanned = len(expired)

            logger.info(f"Found {len(expired)} expired SESSION_STATE memories")

            # Apply safety check: never delete recently used memories
            if safety_check:
                safety_cutoff = datetime.now(UTC) - timedelta(hours=24)
                safe_to_delete = []

                for memory in expired:
                    last_used = memory.get("last_used")
                    if last_used:
                        if isinstance(last_used, str):
                            last_used = datetime.fromisoformat(last_used)

                        # Skip if used in last 24h
                        if last_used >= safety_cutoff:
                            logger.debug(f"Skipping {memory['id']} - used in last 24h")
                            continue

                    safe_to_delete.append(memory)

                expired = safe_to_delete
                logger.info(
                    f"After safety check: {len(expired)} memories safe to delete"
                )

            # Delete memories
            if not dry_run:
                for memory in expired:
                    memory_id = memory["id"]

                    try:
                        deleted = await self.storage.delete(memory_id)

                        if deleted:
                            result.memories_deleted += 1
                            result.deleted_ids.append(memory_id)

                            # Delete usage tracking data too
                            if hasattr(self.storage, "delete_usage_tracking"):
                                await self.storage.delete_usage_tracking(memory_id)

                    except Exception as e:
                        error_msg = f"Failed to delete {memory_id}: {e}"
                        logger.error(error_msg)
                        result.errors.append(error_msg)
            else:
                # Dry run - just count
                result.memories_deleted = len(expired)
                result.deleted_ids = [m["id"] for m in expired]

            # Update stats
            self.stats["total_prunes"] += 1
            self.stats["total_deleted"] += result.memories_deleted
            self.stats["last_prune_time"] = datetime.now(UTC).isoformat()
            self.stats["last_prune_deleted"] = result.memories_deleted

            logger.info(
                f"Pruning complete: {result.memories_deleted} memories deleted "
                f"(dry_run={dry_run})"
            )

        except Exception as e:
            error_msg = f"Pruning failed: {e}"
            logger.error(error_msg)
            result.errors.append(error_msg)

        return result

    async def prune_stale(
        self,
        days_unused: int = 30,
        dry_run: bool = False,
    ) -> PruneResult:
        """
        Prune stale memories (not used in N days).

        Only affects memories that are not USER_PREFERENCE or PROJECT_CONTEXT.

        Args:
            days_unused: Number of days without usage
            dry_run: If True, don't actually delete

        Returns:
            PruneResult with statistics
        """
        result = PruneResult()

        try:
            # Find stale memories
            stale = await self.find_stale_memories(days_unused)
            result.memories_scanned = len(stale)

            logger.info(f"Found {len(stale)} stale memories (>{days_unused} days)")

            # Delete memories
            if not dry_run:
                for memory in stale:
                    memory_id = memory["id"]

                    try:
                        deleted = await self.storage.delete(memory_id)

                        if deleted:
                            result.memories_deleted += 1
                            result.deleted_ids.append(memory_id)

                            # Delete usage tracking data
                            if hasattr(self.storage, "delete_usage_tracking"):
                                await self.storage.delete_usage_tracking(memory_id)

                    except Exception as e:
                        error_msg = f"Failed to delete {memory_id}: {e}"
                        logger.error(error_msg)
                        result.errors.append(error_msg)
            else:
                result.memories_deleted = len(stale)
                result.deleted_ids = [m["id"] for m in stale]

            # Update stats
            self.stats["total_prunes"] += 1
            self.stats["total_deleted"] += result.memories_deleted
            self.stats["last_prune_time"] = datetime.now(UTC).isoformat()
            self.stats["last_prune_deleted"] = result.memories_deleted

            logger.info(
                f"Stale pruning complete: {result.memories_deleted} memories deleted"
            )

        except Exception as e:
            error_msg = f"Stale pruning failed: {e}"
            logger.error(error_msg)
            result.errors.append(error_msg)

        return result

    async def cleanup_orphaned_usage_tracking(self) -> int:
        """
        Clean up usage tracking data for deleted memories.

        Returns:
            Number of orphaned tracking records deleted
        """
        if not hasattr(self.storage, "cleanup_orphaned_usage_tracking"):
            logger.warning("Storage backend does not support usage tracking cleanup")
            return 0

        try:
            count = await self.storage.cleanup_orphaned_usage_tracking()
            logger.info(f"Cleaned up {count} orphaned usage tracking records")
            return count

        except Exception as e:
            logger.error(f"Failed to cleanup orphaned usage tracking: {e}")
            return 0

    def get_stats(self) -> Dict[str, Any]:
        """Get pruner statistics."""
        return self.stats.copy()
