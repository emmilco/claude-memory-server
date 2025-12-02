"""Storage optimization analysis and suggestions for memory lifecycle management."""

import logging
from datetime import datetime, timedelta, UTC
from typing import List, Dict, Optional, Callable, Any
from dataclasses import dataclass, field
from collections import defaultdict

from src.core.models import MemoryUnit, LifecycleState
from src.store.base import MemoryStore

logger = logging.getLogger(__name__)


@dataclass
class OptimizationOpportunity:
    """Single storage optimization opportunity."""

    type: str  # 'compress', 'archive', 'delete', 'deduplicate'
    description: str
    affected_count: int
    storage_savings_mb: float
    risk_level: str  # 'safe', 'low', 'medium', 'high'
    action: Optional[Callable] = None  # Function to execute optimization
    details: Dict[str, Any] = field(default_factory=dict)  # Additional context

    def __lt__(self, other: "OptimizationOpportunity") -> bool:
        """Sort by storage savings (descending) then risk level."""
        if self.storage_savings_mb != other.storage_savings_mb:
            return self.storage_savings_mb > other.storage_savings_mb

        # Lower risk first
        risk_order = {"safe": 0, "low": 1, "medium": 2, "high": 3}
        return risk_order.get(self.risk_level, 3) < risk_order.get(other.risk_level, 3)


@dataclass
class StorageAnalysisResult:
    """Result of storage analysis."""

    total_memories: int
    total_size_mb: float
    by_lifecycle_state: Dict[str, int]
    by_lifecycle_size_mb: Dict[str, float]
    opportunities: List[OptimizationOpportunity]
    potential_savings_mb: float
    analyzed_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def get_summary(self) -> str:
        """Get a human-readable summary."""
        lines = [
            f"Storage Analysis - {self.analyzed_at.strftime('%Y-%m-%d %H:%M:%S')}",
            f"Total Memories: {self.total_memories:,}",
            f"Total Storage: {self.total_size_mb:.2f} MB",
            "",
            "Lifecycle Distribution:",
        ]

        for state in ["ACTIVE", "RECENT", "ARCHIVED", "STALE"]:
            count = self.by_lifecycle_state.get(state, 0)
            size = self.by_lifecycle_size_mb.get(state, 0.0)
            if count > 0:
                pct = (
                    (count / self.total_memories * 100)
                    if self.total_memories > 0
                    else 0
                )
                lines.append(
                    f"  {state}: {count:,} memories ({pct:.1f}%), {size:.2f} MB"
                )

        lines.extend(
            [
                "",
                f"Optimization Opportunities: {len(self.opportunities)}",
                f"Potential Savings: {self.potential_savings_mb:.2f} MB",
            ]
        )

        return "\n".join(lines)


@dataclass
class LifecycleConfig:
    """Configuration for lifecycle management and optimization."""

    # Session state expiration
    session_expiry_hours: int = 48

    # Importance decay
    importance_decay_half_life_days: int = 7

    # Auto-archival thresholds
    auto_archive_threshold_days: int = 180
    auto_delete_threshold_days: int = 365

    # Compression thresholds
    compression_size_threshold_kb: int = 10
    enable_auto_compression: bool = True

    # Auto-optimization
    enable_auto_archival: bool = True
    enable_auto_deduplication: bool = True

    # Storage limits
    max_total_size_mb: Optional[float] = None  # Alert if exceeded
    max_stale_memories: Optional[int] = 10000  # Alert if exceeded


class StorageOptimizer:
    """
    Analyze and optimize memory storage.

    Identifies optimization opportunities:
    - Large memories that could be compressed
    - Duplicate/redundant memories
    - Stale embeddings (unused for 180+ days)
    - Oversized memories (>10KB that could be summarized)
    """

    def __init__(self, store: MemoryStore, config: Optional[LifecycleConfig] = None):
        """
        Initialize storage optimizer.

        Args:
            store: Memory store implementation
            config: Lifecycle configuration. If None, uses defaults.
        """
        self.store = store
        self.config = config or LifecycleConfig()
        logger.info("StorageOptimizer initialized")

    async def analyze(self) -> StorageAnalysisResult:
        """
        Analyze storage for optimization opportunities.

        Returns:
            Storage analysis result with opportunities
        """
        logger.info("Starting storage analysis...")

        # Get all memories
        memories = await self._get_all_memories()
        total_memories = len(memories)
        total_size_mb = sum(self._estimate_memory_size_mb(m) for m in memories)

        # Calculate distribution by lifecycle state
        by_lifecycle_state = defaultdict(int)
        by_lifecycle_size_mb = defaultdict(float)

        for memory in memories:
            state = memory.lifecycle_state.value
            by_lifecycle_state[state] += 1
            by_lifecycle_size_mb[state] += self._estimate_memory_size_mb(memory)

        # Find optimization opportunities
        opportunities = []

        # 1. Find large memories that could be compressed
        large_memory_opps = await self._find_large_memory_opportunities(memories)
        opportunities.extend(large_memory_opps)

        # 2. Find duplicate candidates
        duplicate_opps = await self._find_duplicate_opportunities(memories)
        opportunities.extend(duplicate_opps)

        # 3. Find unused embeddings/stale memories
        stale_opps = await self._find_stale_opportunities(memories)
        opportunities.extend(stale_opps)

        # 4. Find SESSION_STATE memories to expire
        session_opps = await self._find_session_expiry_opportunities(memories)
        opportunities.extend(session_opps)

        # Sort opportunities by potential savings
        opportunities.sort()

        # Calculate total potential savings
        potential_savings_mb = sum(opp.storage_savings_mb for opp in opportunities)

        result = StorageAnalysisResult(
            total_memories=total_memories,
            total_size_mb=total_size_mb,
            by_lifecycle_state=dict(by_lifecycle_state),
            by_lifecycle_size_mb=dict(by_lifecycle_size_mb),
            opportunities=opportunities,
            potential_savings_mb=potential_savings_mb,
        )

        logger.info(
            f"Analysis complete: {total_memories} memories, "
            f"{len(opportunities)} opportunities, "
            f"{potential_savings_mb:.2f} MB potential savings"
        )

        return result

    async def _get_all_memories(self) -> List[MemoryUnit]:
        """Get all memories from the store."""
        # Use search with no filters to get all
        from src.core.models import SearchFilters

        filters = SearchFilters()
        results = await self.store.search("", top_k=100000, filters=filters)
        return [result.memory for result in results]

    def _estimate_memory_size_mb(self, memory: MemoryUnit) -> float:
        """
        Estimate memory size in MB.

        Args:
            memory: Memory unit

        Returns:
            Estimated size in MB
        """
        # Content size (UTF-8 encoded)
        content_size = len(memory.content.encode("utf-8"))

        # Embedding size (384 dimensions * 4 bytes per float32)
        embedding_size = 384 * 4

        # Metadata size (rough estimate)
        metadata_size = (
            len(str(memory.metadata).encode("utf-8")) if memory.metadata else 0
        )

        total_bytes = content_size + embedding_size + metadata_size
        return total_bytes / (1024 * 1024)  # Convert to MB

    async def _find_large_memory_opportunities(
        self, memories: List[MemoryUnit]
    ) -> List[OptimizationOpportunity]:
        """
        Find memories larger than threshold that could be compressed.

        Args:
            memories: List of memory units

        Returns:
            List of compression opportunities
        """
        opportunities = []
        threshold_bytes = self.config.compression_size_threshold_kb * 1024

        large_memories = [
            m for m in memories if len(m.content.encode("utf-8")) > threshold_bytes
        ]

        if not large_memories:
            return opportunities

        # Group by lifecycle state for better recommendations
        by_state = defaultdict(list)
        for memory in large_memories:
            by_state[memory.lifecycle_state.value].append(memory)

        for state, state_memories in by_state.items():
            if not state_memories:
                continue

            total_size = sum(self._estimate_memory_size_mb(m) for m in state_memories)
            # Estimate 30-50% compression ratio
            estimated_savings = total_size * 0.4

            risk = "low" if state in ["ARCHIVED", "STALE"] else "medium"

            opportunities.append(
                OptimizationOpportunity(
                    type="compress",
                    description=f"Compress {len(state_memories)} large {state} memories (>{self.config.compression_size_threshold_kb}KB each)",
                    affected_count=len(state_memories),
                    storage_savings_mb=estimated_savings,
                    risk_level=risk,
                    details={
                        "state": state,
                        "memory_ids": [m.id for m in state_memories[:10]],  # First 10
                        "total_memories": len(state_memories),
                    },
                )
            )

        return opportunities

    async def _find_duplicate_opportunities(
        self, memories: List[MemoryUnit]
    ) -> List[OptimizationOpportunity]:
        """
        Find potential duplicate memories.

        Args:
            memories: List of memory units

        Returns:
            List of deduplication opportunities
        """
        opportunities = []

        # Simple heuristic: group by content length and category
        # In practice, would use semantic similarity
        by_signature = defaultdict(list)

        for memory in memories:
            # Create a signature: category + rough content length
            length_bucket = (len(memory.content) // 100) * 100
            signature = (
                f"{memory.category.value}_{memory.context_level.value}_{length_bucket}"
            )
            by_signature[signature].append(memory)

        # Find buckets with multiple memories
        potential_duplicates = {
            sig: mems for sig, mems in by_signature.items() if len(mems) >= 2
        }

        if potential_duplicates:
            total_count = sum(len(mems) - 1 for mems in potential_duplicates.values())
            # Estimate savings: assume we keep 1 from each group
            total_savings = sum(
                sum(self._estimate_memory_size_mb(m) for m in mems[1:])
                for mems in potential_duplicates.values()
            )

            opportunities.append(
                OptimizationOpportunity(
                    type="deduplicate",
                    description=f"Review {total_count} potential duplicate memories across {len(potential_duplicates)} groups",
                    affected_count=total_count,
                    storage_savings_mb=total_savings,
                    risk_level="medium",
                    details={
                        "groups": len(potential_duplicates),
                        "sample_signatures": list(potential_duplicates.keys())[:5],
                    },
                )
            )

        return opportunities

    async def _find_stale_opportunities(
        self, memories: List[MemoryUnit]
    ) -> List[OptimizationOpportunity]:
        """
        Find stale memories that haven't been accessed in threshold days.

        Args:
            memories: List of memory units

        Returns:
            List of stale memory opportunities
        """
        opportunities = []
        now = datetime.now(UTC)
        threshold = timedelta(days=self.config.auto_archive_threshold_days)

        stale_memories = [
            m
            for m in memories
            if (now - m.last_accessed) > threshold
            and m.lifecycle_state == LifecycleState.STALE
        ]

        if not stale_memories:
            return opportunities

        total_size = sum(self._estimate_memory_size_mb(m) for m in stale_memories)

        opportunities.append(
            OptimizationOpportunity(
                type="delete",
                description=f"Delete {len(stale_memories)} STALE memories unused for {self.config.auto_archive_threshold_days}+ days",
                affected_count=len(stale_memories),
                storage_savings_mb=total_size,
                risk_level="low",  # STALE memories are expected to be deleted
                details={
                    "memory_ids": [m.id for m in stale_memories[:10]],
                    "oldest_access": min(
                        m.last_accessed for m in stale_memories
                    ).isoformat(),
                },
            )
        )

        return opportunities

    async def _find_session_expiry_opportunities(
        self, memories: List[MemoryUnit]
    ) -> List[OptimizationOpportunity]:
        """
        Find SESSION_STATE memories that should be expired.

        Args:
            memories: List of memory units

        Returns:
            List of session expiry opportunities
        """
        from src.core.models import ContextLevel

        opportunities = []
        now = datetime.now(UTC)
        threshold = timedelta(hours=self.config.session_expiry_hours)

        expired_sessions = [
            m
            for m in memories
            if m.context_level == ContextLevel.SESSION_STATE
            and (now - m.last_accessed) > threshold
        ]

        if not expired_sessions:
            return opportunities

        total_size = sum(self._estimate_memory_size_mb(m) for m in expired_sessions)

        opportunities.append(
            OptimizationOpportunity(
                type="delete",
                description=f"Delete {len(expired_sessions)} expired SESSION_STATE memories (>{self.config.session_expiry_hours}h old)",
                affected_count=len(expired_sessions),
                storage_savings_mb=total_size,
                risk_level="safe",  # Session state is temporary by definition
                details={
                    "memory_ids": [m.id for m in expired_sessions[:10]],
                    "threshold_hours": self.config.session_expiry_hours,
                },
            )
        )

        return opportunities

    async def apply_optimization(
        self, opportunity: OptimizationOpportunity, dry_run: bool = True
    ) -> int:
        """
        Apply an optimization opportunity.

        Args:
            opportunity: Optimization to apply
            dry_run: If True, don't actually modify data (default)

        Returns:
            Number of memories affected
        """
        if dry_run:
            logger.info(f"[DRY RUN] Would apply: {opportunity.description}")
            return opportunity.affected_count

        logger.info(f"Applying optimization: {opportunity.description}")

        if opportunity.type == "delete":
            memory_ids = opportunity.details.get("memory_ids", [])
            for memory_id in memory_ids:
                try:
                    await self.store.delete(memory_id)
                except Exception as e:
                    logger.error(f"Failed to delete memory {memory_id}: {e}")

            return len(memory_ids)

        elif opportunity.type == "compress":
            logger.warning("Compression not yet implemented")
            return 0

        elif opportunity.type == "deduplicate":
            logger.warning(
                "Deduplication not yet implemented (use FEAT-035 consolidation)"
            )
            return 0

        else:
            logger.warning(f"Unknown optimization type: {opportunity.type}")
            return 0

    async def get_safe_optimizations(
        self, analysis: StorageAnalysisResult
    ) -> List[OptimizationOpportunity]:
        """
        Filter analysis for only safe optimizations that can be auto-applied.

        Args:
            analysis: Storage analysis result

        Returns:
            List of safe optimization opportunities
        """
        return [opp for opp in analysis.opportunities if opp.risk_level == "safe"]

    async def auto_optimize(self, dry_run: bool = True) -> Dict[str, Any]:
        """
        Run automatic optimization applying only safe operations.

        Args:
            dry_run: If True, don't actually modify data (default)

        Returns:
            Dictionary with optimization results
        """
        logger.info(f"Starting auto-optimization (dry_run={dry_run})...")

        # Run analysis
        analysis = await self.analyze()

        # Get safe opportunities
        safe_opps = await self.get_safe_optimizations(analysis)

        if not safe_opps:
            logger.info("No safe optimizations found")
            return {
                "total_memories": analysis.total_memories,
                "opportunities_found": len(analysis.opportunities),
                "safe_opportunities": 0,
                "applied": 0,
                "savings_mb": 0.0,
            }

        # Apply safe optimizations
        total_applied = 0
        total_savings = 0.0

        for opp in safe_opps:
            count = await self.apply_optimization(opp, dry_run=dry_run)
            total_applied += count
            total_savings += opp.storage_savings_mb

        logger.info(
            f"Auto-optimization complete: {total_applied} memories processed, "
            f"{total_savings:.2f} MB savings"
        )

        return {
            "total_memories": analysis.total_memories,
            "opportunities_found": len(analysis.opportunities),
            "safe_opportunities": len(safe_opps),
            "applied": total_applied,
            "savings_mb": total_savings,
            "dry_run": dry_run,
        }
