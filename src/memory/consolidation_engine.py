"""Memory consolidation and merging (FEAT-035 Phase 2)."""

import logging
import json
from typing import List, Tuple, Optional, Dict, Any
from datetime import datetime, UTC
from enum import Enum

from src.core.models import MemoryUnit, MemoryCategory
from src.store.base import MemoryStore
from src.core.exceptions import StorageError

logger = logging.getLogger(__name__)


class MergeStrategy(str, Enum):
    """Strategy for merging duplicate memories."""

    KEEP_MOST_RECENT = "keep_most_recent"  # Keep the newest memory
    KEEP_HIGHEST_IMPORTANCE = "keep_highest_importance"  # Keep most important
    KEEP_MOST_ACCESSED = "keep_most_accessed"  # Keep most frequently accessed
    MERGE_CONTENT = "merge_content"  # Combine content from all
    USER_SELECTED = "user_selected"  # User manually selected canonical


class ConsolidationEngine:
    """
    Engine for consolidating and merging duplicate memories.

    Provides multiple merge strategies and tracks merge history for undo capability.
    """

    def __init__(self, store: MemoryStore):
        """
        Initialize consolidation engine.

        Args:
            store: Memory store for reading/writing memories
        """
        self.store = store
        logger.info("ConsolidationEngine initialized")

    async def merge_memories(
        self,
        canonical_id: str,
        duplicate_ids: List[str],
        strategy: MergeStrategy = MergeStrategy.KEEP_MOST_RECENT,
        dry_run: bool = False
    ) -> Optional[MemoryUnit]:
        """
        Merge duplicate memories into a canonical memory.

        Args:
            canonical_id: ID of the memory to keep
            duplicate_ids: IDs of memories to merge and delete
            strategy: Merge strategy to use
            dry_run: If True, don't actually perform the merge

        Returns:
            Merged memory unit, or None if dry_run=True
        """
        try:
            # Fetch all memories
            canonical = await self.store.get_by_id(canonical_id)
            if not canonical:
                raise ValueError(f"Canonical memory not found: {canonical_id}")

            duplicates = []
            for dup_id in duplicate_ids:
                dup = await self.store.get_by_id(dup_id)
                if dup:
                    duplicates.append(dup)
                else:
                    logger.warning(f"Duplicate memory not found: {dup_id}")

            if not duplicates:
                logger.info("No duplicates to merge")
                return canonical

            # Apply merge strategy
            merged = await self._apply_merge_strategy(canonical, duplicates, strategy)

            if dry_run:
                logger.info(f"Dry run: would merge {len(duplicates)} memories into {canonical_id}")
                return None

            # Store merge history
            await self._record_merge(
                canonical_id=merged.id,
                duplicate_ids=[d.id for d in duplicates],
                strategy=strategy
            )

            # Update canonical memory
            from src.embeddings.generator import EmbeddingGenerator
            embedding_gen = EmbeddingGenerator()
            embedding = await embedding_gen.generate(merged.content)

            await self.store.store(
                content=merged.content,
                embedding=embedding,
                metadata={
                    "id": merged.id,
                    "category": merged.category.value,
                    "context_level": merged.context_level.value,
                    "scope": merged.scope.value,
                    "project_name": merged.project_name,
                    "importance": merged.importance,
                    "tags": merged.tags,
                    "metadata": merged.metadata,
                    "created_at": merged.created_at,
                    "provenance": merged.provenance.model_dump() if merged.provenance else {},
                }
            )

            # Delete duplicates
            for dup in duplicates:
                await self.store.delete(dup.id)
                logger.debug(f"Deleted duplicate memory: {dup.id}")

            logger.info(
                f"Merged {len(duplicates)} memories into {canonical_id} "
                f"using strategy {strategy.value}"
            )
            return merged

        except Exception as e:
            logger.error(f"Error merging memories: {e}")
            raise StorageError(f"Failed to merge memories: {e}")

    async def _apply_merge_strategy(
        self,
        canonical: MemoryUnit,
        duplicates: List[MemoryUnit],
        strategy: MergeStrategy
    ) -> MemoryUnit:
        """
        Apply merge strategy to combine memories.

        Args:
            canonical: Canonical memory
            duplicates: Duplicate memories
            strategy: Merge strategy

        Returns:
            Merged memory unit
        """
        all_memories = [canonical] + duplicates

        if strategy == MergeStrategy.KEEP_MOST_RECENT:
            # Keep the most recently created memory
            most_recent = max(all_memories, key=lambda m: m.created_at)
            return most_recent

        elif strategy == MergeStrategy.KEEP_HIGHEST_IMPORTANCE:
            # Keep the memory with highest importance
            highest_importance = max(all_memories, key=lambda m: m.importance)
            return highest_importance

        elif strategy == MergeStrategy.KEEP_MOST_ACCESSED:
            # Keep the most frequently accessed memory
            # Use metadata access_count if available
            def get_access_count(mem: MemoryUnit) -> int:
                return mem.metadata.get("access_count", 0)

            most_accessed = max(all_memories, key=get_access_count)
            return most_accessed

        elif strategy == MergeStrategy.MERGE_CONTENT:
            # Combine content from all memories
            merged_content = self._merge_content([m.content for m in all_memories])
            merged_tags = list(set(tag for m in all_memories for tag in m.tags))
            merged_importance = max(m.importance for m in all_memories)

            # Create new memory with merged content
            merged = canonical.model_copy(deep=True)
            merged.content = merged_content
            merged.tags = merged_tags
            merged.importance = merged_importance
            merged.updated_at = datetime.now(UTC)

            return merged

        elif strategy == MergeStrategy.USER_SELECTED:
            # User explicitly selected canonical, use it as-is
            return canonical

        else:
            logger.warning(f"Unknown merge strategy: {strategy}, using canonical")
            return canonical

    def _merge_content(self, contents: List[str]) -> str:
        """
        Merge multiple content strings intelligently.

        Args:
            contents: List of content strings

        Returns:
            Merged content
        """
        # Remove exact duplicates
        unique_contents = list(dict.fromkeys(contents))

        if len(unique_contents) == 1:
            return unique_contents[0]

        # For now, use simple concatenation with separator
        # TODO: Use LLM to merge more intelligently
        merged = "\n\n---\n\n".join(unique_contents)
        return f"[Merged from {len(unique_contents)} memories]\n\n{merged}"

    async def _record_merge(
        self,
        canonical_id: str,
        duplicate_ids: List[str],
        strategy: MergeStrategy
    ) -> str:
        """
        Record merge in history for potential undo.

        Args:
            canonical_id: ID of canonical memory
            duplicate_ids: IDs of merged duplicates
            strategy: Merge strategy used

        Returns:
            Merge ID
        """
        # TODO: Implement merge history table
        # For now, just log it
        merge_id = f"merge_{datetime.now(UTC).timestamp()}"
        logger.info(
            f"Recorded merge {merge_id}: {canonical_id} <- {duplicate_ids} "
            f"(strategy={strategy.value})"
        )
        return merge_id

    async def detect_contradictions(
        self,
        category: MemoryCategory = MemoryCategory.PREFERENCE,
        min_similarity: float = 0.7
    ) -> List[Tuple[MemoryUnit, MemoryUnit, float]]:
        """
        Detect potentially contradictory memories.

        For preferences, looks for:
        - Similar subject but different objects ("I prefer X" vs "I prefer Y")
        - Temporal separation (created > 30 days apart)
        - Both still ACTIVE

        Args:
            category: Category to check (typically PREFERENCE)
            min_similarity: Minimum semantic similarity to consider

        Returns:
            List of (memory_a, memory_b, similarity_score) tuples
        """
        # TODO: Implement full contradiction detection
        # This is a complex NLP task requiring:
        # 1. Entity extraction
        # 2. Sentiment/preference analysis
        # 3. Temporal reasoning
        # 4. Mutual exclusivity checking

        logger.info(f"Contradiction detection not yet implemented for {category.value}")
        return []

    async def get_consolidation_suggestions(
        self,
        category: Optional[MemoryCategory] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get suggestions for memories to consolidate.

        Returns memories that:
        - Have high-confidence duplicates
        - Have contradictions
        - Are stale and could be archived

        Args:
            category: Optional category filter
            limit: Maximum suggestions to return

        Returns:
            List of suggestion dicts with type, memories, confidence
        """
        suggestions = []

        # Use duplicate detector to find candidates
        from src.memory.duplicate_detector import DuplicateDetector
        from src.embeddings.generator import EmbeddingGenerator

        detector = DuplicateDetector(
            store=self.store,
            embedding_generator=EmbeddingGenerator()
        )

        # Find auto-merge candidates
        auto_merge = await detector.get_auto_merge_candidates(category=category)
        for canonical_id, duplicates in list(auto_merge.items())[:limit]:
            canonical = await self.store.get_by_id(canonical_id)
            if canonical:
                suggestions.append({
                    "type": "auto_merge",
                    "canonical": canonical,
                    "duplicates": [dup_id for dup_id, _ in duplicates],
                    "confidence": "high",
                    "action": "merge"
                })

        # Find review candidates
        if len(suggestions) < limit:
            review = await detector.get_user_review_candidates(category=category)
            for canonical_id, duplicates in list(review.items())[:limit - len(suggestions)]:
                canonical = await self.store.get_by_id(canonical_id)
                if canonical:
                    suggestions.append({
                        "type": "needs_review",
                        "canonical": canonical,
                        "duplicates": [dup_id for dup_id, _ in duplicates],
                        "confidence": "medium",
                        "action": "review"
                    })

        logger.info(f"Generated {len(suggestions)} consolidation suggestions")
        return suggestions
