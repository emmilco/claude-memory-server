"""Memory usage tracking with batched updates."""

import asyncio
import logging
import math
from typing import Dict, Any, Optional, List
from datetime import datetime, UTC, timedelta
from collections import defaultdict

from src.config import ServerConfig

logger = logging.getLogger(__name__)


class UsageStats:
    """Statistics for a single memory."""

    def __init__(
        self,
        memory_id: str,
        first_seen: Optional[datetime] = None,
        last_used: Optional[datetime] = None,
        use_count: int = 0,
        last_search_score: float = 0.0,
    ):
        self.memory_id = memory_id
        self.first_seen = first_seen or datetime.now(UTC)
        self.last_used = last_used or datetime.now(UTC)
        self.use_count = use_count
        self.last_search_score = last_search_score

    def update_usage(self, search_score: float) -> None:
        """Update usage statistics."""
        self.last_used = datetime.now(UTC)
        self.use_count += 1
        self.last_search_score = search_score

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "memory_id": self.memory_id,
            "first_seen": self.first_seen.isoformat(),
            "last_used": self.last_used.isoformat(),
            "use_count": self.use_count,
            "last_search_score": self.last_search_score,
        }


class UsageTracker:
    """
    Track memory usage with batched updates.

    Accumulates usage data in memory and flushes to storage periodically
    to minimize I/O overhead.
    """

    def __init__(self, config: ServerConfig, storage_backend: Any):
        """
        Initialize usage tracker.

        Args:
            config: Server configuration
            storage_backend: Storage backend (SQLite or Qdrant store)
        """
        self.config = config
        self.storage = storage_backend

        # Pending updates (memory_id -> UsageStats)
        self._pending_updates: Dict[str, UsageStats] = {}
        self._lock = asyncio.Lock()

        # Background flush task
        self._flush_task: Optional[asyncio.Task] = None
        self._running = False

        # Statistics
        self.stats = {
            "total_tracked": 0,
            "total_flushed": 0,
            "flush_count": 0,
            "last_flush_time": None,
        }

    async def start(self) -> None:
        """Start background flush task."""
        if self._running:
            return

        self._running = True
        self._flush_task = asyncio.create_task(self._periodic_flush())
        logger.info(
            f"Usage tracker started (batch_size={self.config.usage_batch_size}, "
            f"flush_interval={self.config.usage_flush_interval_seconds}s)"
        )

    async def stop(self) -> None:
        """Stop background flush task and flush remaining updates."""
        if not self._running:
            return

        self._running = False

        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass

        # Final flush
        await self._flush()
        logger.info("Usage tracker stopped")

    async def record_usage(
        self, memory_id: str, search_score: float = 0.0
    ) -> None:
        """
        Record usage of a memory.

        Args:
            memory_id: Memory ID
            search_score: Search similarity score
        """
        if not self.config.enable_usage_tracking:
            return

        async with self._lock:
            if memory_id in self._pending_updates:
                self._pending_updates[memory_id].update_usage(search_score)
            else:
                self._pending_updates[memory_id] = UsageStats(
                    memory_id=memory_id,
                    last_search_score=search_score,
                )

            self.stats["total_tracked"] += 1

            # Check if we should flush (schedule as task to avoid deadlock)
            if len(self._pending_updates) >= self.config.usage_batch_size:
                asyncio.create_task(self._flush())

    async def record_batch(
        self, memory_ids: List[str], scores: Optional[List[float]] = None
    ) -> None:
        """
        Record usage for multiple memories at once.

        Args:
            memory_ids: List of memory IDs
            scores: Optional list of search scores (same length as memory_ids)
        """
        if scores is None:
            scores = [0.0] * len(memory_ids)

        for memory_id, score in zip(memory_ids, scores):
            await self.record_usage(memory_id, score)

    async def _periodic_flush(self) -> None:
        """Background task to flush updates periodically."""
        while self._running:
            try:
                await asyncio.sleep(self.config.usage_flush_interval_seconds)
                await self._flush()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in periodic flush: {e}")

    async def _flush(self) -> None:
        """Flush pending updates to storage."""
        async with self._lock:
            if not self._pending_updates:
                return

            try:
                # Get pending updates
                updates = list(self._pending_updates.values())
                update_count = len(updates)

                # Call storage backend's update method
                if hasattr(self.storage, "batch_update_usage"):
                    await self.storage.batch_update_usage(
                        [stats.to_dict() for stats in updates]
                    )
                else:
                    # Fallback: update one by one
                    for stats in updates:
                        await self.storage.update_usage(stats.to_dict())

                # Clear pending updates
                self._pending_updates.clear()

                # Update stats
                self.stats["total_flushed"] += update_count
                self.stats["flush_count"] += 1
                self.stats["last_flush_time"] = datetime.now(UTC).isoformat()

                logger.debug(f"Flushed {update_count} usage updates")

            except Exception as e:
                logger.error(f"Failed to flush usage updates: {e}")
                # Keep updates in memory for next flush attempt

    def calculate_composite_score(
        self,
        similarity_score: float,
        created_at: datetime,
        last_used: Optional[datetime] = None,
        use_count: int = 0,
    ) -> float:
        """
        Calculate composite ranking score.

        Score = (
            weight_similarity * similarity_score +
            weight_recency * recency_score +
            weight_usage * usage_score
        )

        Args:
            similarity_score: Semantic similarity (0-1)
            created_at: When memory was created
            last_used: When memory was last used (None if never)
            use_count: Number of times memory was accessed

        Returns:
            Composite score (0-1)
        """
        # Similarity component (already 0-1)
        similarity_component = similarity_score

        # Recency component: exponential decay
        # Use last_used if available, otherwise created_at
        reference_time = last_used or created_at
        age_hours = (datetime.now(UTC) - reference_time).total_seconds() / 3600

        # Convert half-life from days to hours
        halflife_hours = self.config.recency_decay_halflife_days * 24

        # Exponential decay: score = 2^(-age/halflife)
        # This gives 1.0 for age=0, 0.5 for age=halflife, 0.25 for age=2*halflife
        recency_score = math.pow(2, -age_hours / halflife_hours)

        # Usage component: logarithmic scaling
        # log(use_count + 1) normalized to 0-1
        # We assume max reasonable use_count is 1000 for normalization
        max_use_count = 1000
        usage_score = min(math.log(use_count + 1) / math.log(max_use_count + 1), 1.0)

        # Weighted combination
        composite_score = (
            self.config.ranking_weight_similarity * similarity_component +
            self.config.ranking_weight_recency * recency_score +
            self.config.ranking_weight_usage * usage_score
        )

        # Ensure result is in [0, 1]
        return max(0.0, min(1.0, composite_score))

    async def get_usage_stats(self, memory_id: str) -> Optional[Dict[str, Any]]:
        """
        Get usage statistics for a memory.

        Args:
            memory_id: Memory ID

        Returns:
            Usage statistics dict, or None if not found
        """
        # Check pending updates first
        async with self._lock:
            if memory_id in self._pending_updates:
                return self._pending_updates[memory_id].to_dict()

        # Query storage backend
        if hasattr(self.storage, "get_usage_stats"):
            return await self.storage.get_usage_stats(memory_id)

        return None

    async def get_all_stats(self) -> List[Dict[str, Any]]:
        """
        Get all usage statistics.

        Returns:
            List of usage statistics dicts
        """
        if hasattr(self.storage, "get_all_usage_stats"):
            return await self.storage.get_all_usage_stats()

        return []

    def get_tracker_stats(self) -> Dict[str, Any]:
        """Get tracker statistics."""
        async def _get_pending_count():
            async with self._lock:
                return len(self._pending_updates)

        # Note: This is a sync method returning stats
        # pending_updates count requires async access, so we return what we can
        return {
            **self.stats,
            "pending_updates": len(self._pending_updates),  # Best effort
            "running": self._running,
        }
