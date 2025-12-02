"""Memory lifecycle management for automatic state transitions and quality maintenance."""

import logging
from datetime import datetime, UTC
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass

from src.core.models import LifecycleState, MemoryUnit, ContextLevel

logger = logging.getLogger(__name__)


@dataclass
class LifecycleConfig:
    """Configuration for lifecycle management."""

    # Transition thresholds (in days)
    active_to_recent_days: int = 7
    recent_to_archived_days: int = 30
    archived_to_stale_days: int = 180

    # Access frequency thresholds (for early promotion)
    high_access_threshold: int = 10  # accesses within window
    moderate_access_threshold: int = 3

    # Search weight multipliers
    active_weight: float = 1.0
    recent_weight: float = 0.7
    archived_weight: float = 0.3
    stale_weight: float = 0.1


class LifecycleManager:
    """
    Manages memory lifecycle states and automatic transitions.

    Lifecycle states:
    - ACTIVE (0-7 days): Current work, frequently accessed, full weight (1.0x)
    - RECENT (7-30 days): Recent context, moderately relevant, reduced weight (0.7x)
    - ARCHIVED (30-180 days): Historical, rarely accessed, heavy penalty (0.3x)
    - STALE (180+ days): Candidates for deletion, minimal weight (0.1x)

    Transitions are based on:
    1. Age since creation/last access
    2. Access frequency (usage tracking)
    3. Project activity (detected via file watcher)
    4. Context relevance (current project context)
    """

    def __init__(self, config: Optional[LifecycleConfig] = None):
        """
        Initialize lifecycle manager.

        Args:
            config: Lifecycle configuration. If None, uses defaults.
        """
        self.config = config or LifecycleConfig()
        logger.info(
            f"LifecycleManager initialized with transitions at "
            f"{self.config.active_to_recent_days}d, "
            f"{self.config.recent_to_archived_days}d, "
            f"{self.config.archived_to_stale_days}d"
        )

    def calculate_state(
        self,
        created_at: datetime,
        last_accessed: datetime,
        use_count: int = 0,
        context_level: Optional[ContextLevel] = None,
    ) -> LifecycleState:
        """
        Calculate the appropriate lifecycle state for a memory.

        Args:
            created_at: When the memory was created
            last_accessed: When the memory was last accessed
            use_count: Number of times accessed (from usage tracking)
            context_level: Memory context level (affects aging)

        Returns:
            Appropriate lifecycle state
        """
        now = datetime.now(UTC)

        # Calculate days since last access (primary factor)
        days_since_access = (now - last_accessed).days

        # Calculate days since creation (secondary factor)
        (now - created_at).days

        # USER_PREFERENCE memories age slower (they're more stable)
        if context_level == ContextLevel.USER_PREFERENCE:
            # Double the thresholds for preferences
            active_threshold = self.config.active_to_recent_days * 2
            recent_threshold = self.config.recent_to_archived_days * 2
            archived_threshold = self.config.archived_to_stale_days * 2
        # SESSION_STATE memories age faster (they're temporary)
        elif context_level == ContextLevel.SESSION_STATE:
            # Halve the thresholds for session state
            active_threshold = self.config.active_to_recent_days // 2
            recent_threshold = self.config.recent_to_archived_days // 2
            archived_threshold = self.config.archived_to_stale_days // 2
        else:
            # Normal aging for PROJECT_CONTEXT
            active_threshold = self.config.active_to_recent_days
            recent_threshold = self.config.recent_to_archived_days
            archived_threshold = self.config.archived_to_stale_days

        # Check for high access frequency (keeps memory ACTIVE longer)
        if use_count >= self.config.high_access_threshold:
            # Heavily used memories stay ACTIVE or RECENT
            if days_since_access < recent_threshold:
                return LifecycleState.ACTIVE
            elif days_since_access < archived_threshold:
                return LifecycleState.RECENT

        # Standard lifecycle transitions based on days since last access
        if days_since_access < active_threshold:
            return LifecycleState.ACTIVE
        elif days_since_access < recent_threshold:
            return LifecycleState.RECENT
        elif days_since_access < archived_threshold:
            return LifecycleState.ARCHIVED
        else:
            return LifecycleState.STALE

    def should_transition(
        self,
        current_state: LifecycleState,
        new_state: LifecycleState,
    ) -> bool:
        """
        Check if a state transition is allowed.

        Args:
            current_state: Current lifecycle state
            new_state: Proposed new state

        Returns:
            True if transition should occur
        """
        # Allow transitions in both directions (forward aging and backward promotion)
        if current_state == new_state:
            return False

        return True

    def get_search_weight(
        self,
        lifecycle_state: LifecycleState,
    ) -> float:
        """
        Get the search weight multiplier for a given lifecycle state.

        Args:
            lifecycle_state: Lifecycle state

        Returns:
            Weight multiplier (0.0-1.0)
        """
        weights = {
            LifecycleState.ACTIVE: self.config.active_weight,
            LifecycleState.RECENT: self.config.recent_weight,
            LifecycleState.ARCHIVED: self.config.archived_weight,
            LifecycleState.STALE: self.config.stale_weight,
        }

        return weights.get(lifecycle_state, 1.0)

    def apply_lifecycle_weight(
        self,
        base_score: float,
        lifecycle_state: LifecycleState,
    ) -> float:
        """
        Apply lifecycle weight to a search score.

        Args:
            base_score: Original search score
            lifecycle_state: Memory lifecycle state

        Returns:
            Weighted score
        """
        weight = self.get_search_weight(lifecycle_state)
        return base_score * weight

    def get_stale_memory_ids(
        self,
        memories: List[MemoryUnit],
        threshold_days: Optional[int] = None,
    ) -> List[str]:
        """
        Get IDs of memories that should be considered stale.

        Args:
            memories: List of memory units
            threshold_days: Override stale threshold (default: from config)

        Returns:
            List of memory IDs in STALE state
        """
        threshold = threshold_days or self.config.archived_to_stale_days
        now = datetime.now(UTC)
        stale_ids = []

        for memory in memories:
            days_since_access = (now - memory.last_accessed).days
            if days_since_access >= threshold:
                stale_ids.append(memory.id)

        return stale_ids

    def get_lifecycle_stats(
        self,
        memories: List[MemoryUnit],
    ) -> Dict[str, Any]:
        """
        Get statistics about lifecycle state distribution.

        Args:
            memories: List of memory units

        Returns:
            Dictionary with lifecycle statistics
        """
        stats = {
            "total": len(memories),
            "by_state": {
                LifecycleState.ACTIVE.value: 0,
                LifecycleState.RECENT.value: 0,
                LifecycleState.ARCHIVED.value: 0,
                LifecycleState.STALE.value: 0,
            },
            "percentages": {},
        }

        for memory in memories:
            state = memory.lifecycle_state.value
            stats["by_state"][state] += 1

        # Calculate percentages
        if stats["total"] > 0:
            for state, count in stats["by_state"].items():
                percentage = (count / stats["total"]) * 100
                stats["percentages"][state] = round(percentage, 1)

        return stats

    def bulk_update_states(
        self,
        memories: List[MemoryUnit],
        usage_data: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> List[Tuple[str, LifecycleState, LifecycleState]]:
        """
        Bulk update lifecycle states for multiple memories.

        Args:
            memories: List of memory units to update
            usage_data: Optional dict of {memory_id: {use_count, last_used}}

        Returns:
            List of (memory_id, old_state, new_state) tuples for memories that changed
        """
        transitions = []

        for memory in memories:
            # Get usage data if available
            use_count = 0
            if usage_data and memory.id in usage_data:
                use_count = usage_data[memory.id].get("use_count", 0)

            # Calculate new state
            old_state = memory.lifecycle_state
            new_state = self.calculate_state(
                created_at=memory.created_at,
                last_accessed=memory.last_accessed,
                use_count=use_count,
                context_level=memory.context_level,
            )

            # Check if transition should occur
            if self.should_transition(old_state, new_state):
                transitions.append((memory.id, old_state, new_state))
                memory.lifecycle_state = new_state
                logger.debug(
                    f"Memory {memory.id[:8]} transitioned: {old_state.value} → {new_state.value}"
                )

        logger.info(f"Bulk update: {len(transitions)} memories transitioned")
        return transitions
