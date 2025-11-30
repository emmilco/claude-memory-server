"""Health scoring system for memory lifecycle management.

This module calculates various health metrics and provides an overall health score
for the memory system, helping identify quality issues and maintenance needs.
"""

import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, UTC
from dataclasses import dataclass, field

from src.core.models import LifecycleState, MemoryUnit
from src.store import MemoryStore

logger = logging.getLogger(__name__)

# Configurable limits for large dataset operations
MAX_MEMORIES_PER_OPERATION = 50000  # Prevent memory exhaustion on huge datasets
PAGINATION_PAGE_SIZE = 5000  # Process memories in batches to avoid loading all at once
MAX_DUPLICATE_CHECK_MEMORIES = 10000  # Sample cap for duplicate detection
WARN_THRESHOLD_MEMORIES = 25000  # Warn if dataset exceeds this


@dataclass
class HealthScore:
    """Overall health score with detailed breakdown."""

    overall: float  # 0-100
    noise_ratio: float  # 0-1 (percentage of low-value memories)
    duplicate_rate: float  # 0-1 (estimated duplicate content)
    contradiction_rate: float  # 0-1 (conflicting memories)
    distribution_score: float  # 0-100 (lifecycle distribution health)

    # Lifecycle distribution
    active_count: int = 0
    recent_count: int = 0
    archived_count: int = 0
    stale_count: int = 0
    total_count: int = 0

    # Metadata
    grade: str = "Unknown"  # Excellent/Good/Fair/Poor
    recommendations: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        return {
            "overall": round(self.overall, 2),
            "noise_ratio": round(self.noise_ratio, 4),
            "duplicate_rate": round(self.duplicate_rate, 4),
            "contradiction_rate": round(self.contradiction_rate, 4),
            "distribution_score": round(self.distribution_score, 2),
            "lifecycle_distribution": {
                "active": self.active_count,
                "recent": self.recent_count,
                "archived": self.archived_count,
                "stale": self.stale_count,
                "total": self.total_count,
            },
            "grade": self.grade,
            "recommendations": self.recommendations,
            "timestamp": self.timestamp.isoformat(),
        }


class HealthScorer:
    """
    Calculate health scores for memory system.

    Tracks multiple quality metrics:
    - Noise ratio: Low-value memories (STALE + rarely accessed ARCHIVED)
    - Duplicate rate: Similar content (>0.95 similarity)
    - Contradiction rate: Conflicting preferences/facts
    - Distribution: Balance across lifecycle states
    """

    # Ideal distribution percentages
    IDEAL_DISTRIBUTION = {
        LifecycleState.ACTIVE: 0.60,    # 60%
        LifecycleState.RECENT: 0.25,    # 25%
        LifecycleState.ARCHIVED: 0.10,  # 10%
        LifecycleState.STALE: 0.05,     # 5%
    }

    # Thresholds for recommendations
    NOISE_THRESHOLD = 0.15  # 15%
    DUPLICATE_THRESHOLD = 0.10  # 10%
    CONTRADICTION_THRESHOLD = 0.05  # 5%

    def __init__(self, store: MemoryStore):
        """
        Initialize health scorer.

        Args:
            store: Memory store for querying memories
        """
        self.store = store
        logger.info("HealthScorer initialized")

    async def calculate_overall_health(self) -> HealthScore:
        """
        Calculate overall health score with full breakdown.

        Returns:
            HealthScore with all metrics
        """
        # Get lifecycle distribution
        distribution = await self._get_lifecycle_distribution()

        # Calculate individual metrics
        noise_ratio = await self._calculate_noise_ratio(distribution)
        duplicate_rate = await self._calculate_duplicate_rate()
        contradiction_rate = await self._calculate_contradiction_rate()
        distribution_score = self._calculate_distribution_score(distribution)

        # Calculate weighted overall score
        overall = (
            (100 - noise_ratio * 100) * 0.4 +        # 40% weight
            (100 - duplicate_rate * 100) * 0.2 +     # 20% weight
            (100 - contradiction_rate * 100) * 0.2 + # 20% weight
            distribution_score * 0.2                 # 20% weight
        )

        # Determine grade
        if overall >= 90:
            grade = "Excellent"
        elif overall >= 75:
            grade = "Good"
        elif overall >= 60:
            grade = "Fair"
        else:
            grade = "Poor"

        # Generate recommendations
        recommendations = self._generate_recommendations(
            noise_ratio, duplicate_rate, contradiction_rate, distribution
        )

        score = HealthScore(
            overall=overall,
            noise_ratio=noise_ratio,
            duplicate_rate=duplicate_rate,
            contradiction_rate=contradiction_rate,
            distribution_score=distribution_score,
            active_count=distribution.get(LifecycleState.ACTIVE, 0),
            recent_count=distribution.get(LifecycleState.RECENT, 0),
            archived_count=distribution.get(LifecycleState.ARCHIVED, 0),
            stale_count=distribution.get(LifecycleState.STALE, 0),
            total_count=sum(distribution.values()),
            grade=grade,
            recommendations=recommendations,
        )

        logger.info(
            f"Health score calculated: {score.overall:.1f}/100 ({grade}), "
            f"noise={noise_ratio:.2%}, duplicates={duplicate_rate:.2%}"
        )

        return score

    async def _get_lifecycle_distribution(self) -> Dict[LifecycleState, int]:
        """
        Get count of memories in each lifecycle state.

        Uses pagination to prevent memory exhaustion on large datasets.
        Warns and limits processing if dataset exceeds configured thresholds.
        """
        distribution = {
            LifecycleState.ACTIVE: 0,
            LifecycleState.RECENT: 0,
            LifecycleState.ARCHIVED: 0,
            LifecycleState.STALE: 0,
        }

        try:
            # Get all memories with pagination to avoid loading entire dataset at once
            all_memories = await self.store.get_all_memories()
            total_memories = len(all_memories)

            # Warn if dataset is large
            if total_memories > WARN_THRESHOLD_MEMORIES:
                logger.warning(
                    f"Large dataset detected: {total_memories} memories "
                    f"(warn threshold: {WARN_THRESHOLD_MEMORIES}). "
                    f"Processing with pagination."
                )

            # Hard limit to prevent unbounded memory growth
            if total_memories > MAX_MEMORIES_PER_OPERATION:
                logger.error(
                    f"Dataset too large: {total_memories} memories "
                    f"(max: {MAX_MEMORIES_PER_OPERATION}). Aborting operation to prevent memory exhaustion."
                )
                return distribution

            # Process memories in batches (pagination)
            for batch_start in range(0, total_memories, PAGINATION_PAGE_SIZE):
                batch_end = min(batch_start + PAGINATION_PAGE_SIZE, total_memories)
                batch = all_memories[batch_start:batch_end]

                logger.debug(f"Processing lifecycle distribution batch {batch_start}-{batch_end}/{total_memories}")

                for memory in batch:
                    # Support both dict and object (MemoryUnit) access patterns
                    if hasattr(memory, 'lifecycle_state'):
                        state = memory.lifecycle_state
                    elif isinstance(memory, dict):
                        state = memory.get('lifecycle_state', LifecycleState.ACTIVE)
                    else:
                        state = getattr(memory, 'lifecycle_state', LifecycleState.ACTIVE)

                    if isinstance(state, str):
                        # Convert string to LifecycleState enum
                        try:
                            state = LifecycleState(state)
                        except ValueError:
                            state = LifecycleState.ACTIVE
                    if state in distribution:
                        distribution[state] += 1

        except Exception as e:
            logger.error(f"Error getting lifecycle distribution: {e}")
            # Return empty distribution on error
            pass

        return distribution

    async def _calculate_noise_ratio(
        self, distribution: Dict[LifecycleState, int]
    ) -> float:
        """
        Calculate noise ratio (low-value memories).

        Noise = (STALE + rarely accessed ARCHIVED) / total

        Args:
            distribution: Lifecycle state distribution

        Returns:
            Noise ratio (0-1)
        """
        total = sum(distribution.values())
        if total == 0:
            return 0.0

        # STALE memories are always considered noise
        noise_count = distribution.get(LifecycleState.STALE, 0)

        # ARCHIVED memories with low usage are also noise
        # (This would require usage tracking data in a full implementation)
        # For now, assume 50% of ARCHIVED are noise
        archived_count = distribution.get(LifecycleState.ARCHIVED, 0)
        noise_count += int(archived_count * 0.5)

        if total == 0:
            noise_ratio = 0.0
        else:
            noise_ratio = noise_count / total
        return min(1.0, noise_ratio)  # Cap at 1.0

    async def _calculate_duplicate_rate(self) -> float:
        """
        Calculate duplicate content rate.

        In a full implementation, this would:
        1. Sample memories (or use all for small datasets)
        2. Calculate pairwise similarity
        3. Count pairs with >0.95 similarity

        For now, returns a conservative estimate and skips large datasets.

        Returns:
            Duplicate rate (0-1)
        """
        # This is a placeholder implementation
        # Full implementation would require embedding similarity checks
        try:
            all_memories = await self.store.get_all_memories()
            if len(all_memories) < 2:
                return 0.0

            # Size check: Skip duplicate detection for very large datasets
            # to avoid O(N²) memory/time complexity
            if len(all_memories) > MAX_DUPLICATE_CHECK_MEMORIES:
                logger.warning(
                    f"Dataset too large for duplicate detection: {len(all_memories)} memories "
                    f"(max: {MAX_DUPLICATE_CHECK_MEMORIES}). "
                    f"Skipping duplicate rate calculation to prevent memory exhaustion."
                )
                return 0.0

            # Sample approach: Check for exact duplicate content
            content_map = {}
            duplicate_count = 0

            for memory in all_memories:
                # Support both dict and object (MemoryUnit) access patterns
                if hasattr(memory, 'content'):
                    content = memory.content.strip().lower()
                elif isinstance(memory, dict):
                    content = memory.get('content', '').strip().lower()
                else:
                    content = getattr(memory, 'content', '').strip().lower()

                if content in content_map:
                    duplicate_count += 1
                else:
                    content_map[content] = 1

            duplicate_rate = duplicate_count / len(all_memories)
            return min(1.0, duplicate_rate)

        except Exception as e:
            logger.error(f"Error calculating duplicate rate: {e}")
            return 0.0

    async def _calculate_contradiction_rate(self) -> float:
        """
        Calculate contradiction rate (conflicting memories).

        This would check for:
        - Conflicting USER_PREFERENCE memories
        - Contradictory facts
        - Opposing statements

        Full implementation would require semantic similarity analysis (embedding-based),
        which is deferred pending performance requirements and memory system scaling.

        Returns:
            Contradiction rate (0-1)

        Note:
            Currently returns 0.0 (conservative default) as full semantic analysis
            is not yet implemented. This avoids false positives in health scoring.
        """
        try:
            # UNSUPPORTED: Semantic contradiction detection
            # Full implementation would require:
            # 1. Retrieve all memories
            # 2. Cluster memories by topic/category
            # 3. Calculate embedding similarity within clusters
            # 4. Identify semantic contradictions (opposing statements)
            # 5. Weight by memory importance (recency, source reliability)
            #
            # This is deferred because:
            # - Expensive at scale (O(n²) comparisons)
            # - Requires tuning similarity thresholds per domain
            # - May need user feedback for ground truth
            #
            # For now, return conservative estimate (0% contradictions detected)
            return 0.0

        except Exception as e:
            logger.error(f"Error calculating contradiction rate: {e}")
            return 0.0

    def _calculate_distribution_score(
        self, distribution: Dict[LifecycleState, int]
    ) -> float:
        """
        Calculate distribution health score.

        Compares actual distribution to ideal distribution.
        Penalizes deviation from ideal.

        Args:
            distribution: Actual lifecycle state distribution

        Returns:
            Distribution score (0-100)
        """
        total = sum(distribution.values())
        if total == 0:
            return 100.0  # Empty is considered healthy

        # Calculate deviation from ideal
        total_deviation = 0.0

        for state, ideal_pct in self.IDEAL_DISTRIBUTION.items():
            actual_count = distribution.get(state, 0)
            if total == 0:
                actual_pct = 0.0
            else:
                actual_pct = actual_count / total
            deviation = abs(actual_pct - ideal_pct)
            total_deviation += deviation

        # Convert to score (lower deviation = higher score)
        # Max possible deviation is 2.0 (all in one state)
        # Score = 100 * (1 - deviation/2)
        score = 100 * (1 - min(1.0, total_deviation / 2.0))
        return max(0.0, score)

    def _generate_recommendations(
        self,
        noise_ratio: float,
        duplicate_rate: float,
        contradiction_rate: float,
        distribution: Dict[LifecycleState, int],
    ) -> List[str]:
        """
        Generate actionable recommendations based on metrics.

        Args:
            noise_ratio: Noise ratio (0-1)
            duplicate_rate: Duplicate rate (0-1)
            contradiction_rate: Contradiction rate (0-1)
            distribution: Lifecycle distribution

        Returns:
            List of recommendation strings
        """
        recommendations = []

        # Check noise ratio
        if noise_ratio > self.NOISE_THRESHOLD:
            stale_count = distribution.get(LifecycleState.STALE, 0)
            recommendations.append(
                f"⚠ High noise detected ({noise_ratio:.1%}). "
                f"Consider archiving or deleting {stale_count} STALE memories. "
                f"Run 'lifecycle cleanup --dry-run' to preview."
            )

        # Check duplicate rate
        if duplicate_rate > self.DUPLICATE_THRESHOLD:
            recommendations.append(
                f"⚠ High duplicate rate ({duplicate_rate:.1%}). "
                f"Run consolidation to merge similar memories. "
                f"Use 'consolidate --auto' command."
            )

        # Check contradiction rate
        if contradiction_rate > self.CONTRADICTION_THRESHOLD:
            recommendations.append(
                f"⚠ Contradictions detected ({contradiction_rate:.1%}). "
                f"Review and resolve conflicting preferences. "
                f"Run 'verify --contradictions' to see details."
            )

        # Check distribution imbalance
        total = sum(distribution.values())
        if total > 0:
            if total == 0:
                stale_pct = 0.0
            else:
                stale_pct = distribution.get(LifecycleState.STALE, 0) / total
            if stale_pct > 0.15:  # >15% stale
                recommendations.append(
                    f"ℹ {distribution.get(LifecycleState.STALE, 0)} STALE memories "
                    f"({stale_pct:.1%}). Regular cleanup recommended."
                )

        # If health is good, add positive message
        if not recommendations:
            recommendations.append(
                "✓ Health is good! Continue regular maintenance to keep quality high."
            )

        return recommendations

    async def get_quick_stats(self) -> Dict:
        """
        Get quick health statistics without full scoring.

        Returns:
            Dict with key metrics
        """
        distribution = await self._get_lifecycle_distribution()
        total = sum(distribution.values())

        return {
            "total_memories": total,
            "lifecycle_distribution": {
                "active": distribution.get(LifecycleState.ACTIVE, 0),
                "recent": distribution.get(LifecycleState.RECENT, 0),
                "archived": distribution.get(LifecycleState.ARCHIVED, 0),
                "stale": distribution.get(LifecycleState.STALE, 0),
            },
            "stale_percentage": (
                (distribution.get(LifecycleState.STALE, 0) / total * 100)
                if total > 0 else 0.0
            ),
        }
