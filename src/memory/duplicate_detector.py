"""Duplicate memory detection using semantic similarity (FEAT-035 Phase 1)."""

import logging
import numpy as np
from typing import List, Tuple, Optional, Dict, Any
from datetime import datetime, UTC

from src.core.models import MemoryUnit, MemoryCategory
from src.store.base import MemoryStore
from src.embeddings.generator import EmbeddingGenerator
from src.core.exceptions import ValidationError

logger = logging.getLogger(__name__)


class DuplicateDetector:
    """
    Detect duplicate and similar memories using semantic similarity.

    Uses cosine similarity between embeddings to find duplicates.
    Three confidence levels:
    - High (>0.95): Safe for auto-merge
    - Medium (0.85-0.95): Prompt user
    - Low (0.75-0.85): Flag as related
    """

    def __init__(
        self,
        store: MemoryStore,
        embedding_generator: EmbeddingGenerator,
        high_threshold: float = 0.95,
        medium_threshold: float = 0.85,
        low_threshold: float = 0.75
    ):
        """
        Initialize duplicate detector.

        Args:
            store: Memory store for retrieving memories
            embedding_generator: Generator for creating embeddings
            high_threshold: Threshold for high-confidence duplicates (auto-merge)
            medium_threshold: Threshold for medium-confidence duplicates (prompt user)
            low_threshold: Threshold for low-confidence duplicates (flag as related)
        """
        if not (0.0 <= low_threshold <= medium_threshold <= high_threshold <= 1.0):
            raise ValidationError("Thresholds must satisfy: 0 <= low <= medium <= high <= 1")

        self.store = store
        self.embedding_generator = embedding_generator
        self.high_threshold = high_threshold
        self.medium_threshold = medium_threshold
        self.low_threshold = low_threshold

        logger.info(
            f"DuplicateDetector initialized (high={high_threshold}, "
            f"medium={medium_threshold}, low={low_threshold})"
        )

    async def find_duplicates(
        self,
        memory: MemoryUnit,
        min_threshold: Optional[float] = None
    ) -> List[Tuple[MemoryUnit, float]]:
        """
        Find memories similar to the given memory.

        Args:
            memory: Memory to find duplicates of
            min_threshold: Minimum similarity threshold (default: low_threshold)

        Returns:
            List of (similar_memory, similarity_score) tuples, sorted by score descending
        """
        threshold = min_threshold if min_threshold is not None else self.low_threshold

        try:
            # Generate embedding for the query memory
            query_embedding = await self.embedding_generator.generate(memory.content)

            # Retrieve similar memories from store
            # Use same category and scope filters to narrow search
            from src.core.models import SearchFilters
            filters = SearchFilters(
                category=memory.category,
                scope=memory.scope,
                project_name=memory.project_name
            )

            similar_memories = await self.store.retrieve(
                query_embedding=query_embedding,
                filters=filters,
                limit=100  # Cast wide net for duplicate detection
            )

            # Filter out the memory itself and apply threshold
            duplicates = []
            for similar_memory, score in similar_memories:
                if similar_memory.id != memory.id and score >= threshold:
                    duplicates.append((similar_memory, score))

            # Sort by score descending
            duplicates.sort(key=lambda x: x[1], reverse=True)

            logger.debug(
                f"Found {len(duplicates)} duplicates for memory {memory.id[:8]} "
                f"(threshold={threshold:.2f})"
            )
            return duplicates

        except Exception as e:
            logger.error(f"Error finding duplicates: {e}")
            raise

    async def find_all_duplicates(
        self,
        category: Optional[MemoryCategory] = None,
        min_threshold: Optional[float] = None
    ) -> Dict[str, List[Tuple[str, float]]]:
        """
        Scan entire database for duplicate clusters.

        Args:
            category: Optional category filter
            min_threshold: Minimum similarity threshold (default: medium_threshold)

        Returns:
            Dict mapping canonical memory ID to list of (duplicate_id, score) tuples
        """
        threshold = min_threshold if min_threshold is not None else self.medium_threshold

        try:
            # Get all memories
            from src.core.models import SearchFilters
            filters = SearchFilters(category=category) if category else None
            all_memories_results = await self.store.retrieve(
                query_embedding=[0.0] * 384,  # Dummy embedding to get all results
                filters=filters,
                limit=10000
            )

            all_memories = [mem for mem, _ in all_memories_results]

            logger.info(f"Scanning {len(all_memories)} memories for duplicates...")

            # Build duplicate clusters
            duplicate_clusters: Dict[str, List[Tuple[str, float]]] = {}
            processed = set()

            for memory in all_memories:
                if memory.id in processed:
                    continue

                # Find duplicates for this memory
                duplicates = await self.find_duplicates(memory, min_threshold=threshold)

                if duplicates:
                    # This memory has duplicates
                    duplicate_ids = [(dup.id, score) for dup, score in duplicates]
                    duplicate_clusters[memory.id] = duplicate_ids

                    # Mark all duplicates as processed
                    processed.add(memory.id)
                    for dup, _ in duplicates:
                        processed.add(dup.id)

            logger.info(f"Found {len(duplicate_clusters)} duplicate clusters")
            return duplicate_clusters

        except Exception as e:
            logger.error(f"Error scanning for duplicates: {e}")
            raise

    def classify_similarity(self, score: float) -> str:
        """
        Classify similarity score into confidence level.

        Args:
            score: Similarity score (0-1)

        Returns:
            Confidence level: "high", "medium", "low", or "none"
        """
        if score >= self.high_threshold:
            return "high"
        elif score >= self.medium_threshold:
            return "medium"
        elif score >= self.low_threshold:
            return "low"
        else:
            return "none"

    async def get_auto_merge_candidates(
        self,
        category: Optional[MemoryCategory] = None
    ) -> Dict[str, List[Tuple[str, float]]]:
        """
        Get high-confidence duplicate clusters safe for automatic merging.

        Args:
            category: Optional category filter

        Returns:
            Dict mapping canonical memory ID to list of (duplicate_id, score) tuples
        """
        all_duplicates = await self.find_all_duplicates(
            category=category,
            min_threshold=self.high_threshold
        )

        # Filter to only include clusters with high-confidence duplicates
        auto_merge_candidates = {
            canonical_id: duplicates
            for canonical_id, duplicates in all_duplicates.items()
            if all(score >= self.high_threshold for _, score in duplicates)
        }

        logger.info(
            f"Found {len(auto_merge_candidates)} clusters with "
            f"high-confidence duplicates (threshold={self.high_threshold})"
        )
        return auto_merge_candidates

    async def get_user_review_candidates(
        self,
        category: Optional[MemoryCategory] = None
    ) -> Dict[str, List[Tuple[str, float]]]:
        """
        Get medium-confidence duplicates that need user review.

        Args:
            category: Optional category filter

        Returns:
            Dict mapping canonical memory ID to list of (duplicate_id, score) tuples
        """
        all_duplicates = await self.find_all_duplicates(
            category=category,
            min_threshold=self.medium_threshold
        )

        # Filter to clusters that have at least one medium-confidence duplicate
        # but not all high-confidence (those go to auto-merge)
        review_candidates = {}
        for canonical_id, duplicates in all_duplicates.items():
            # Check if any duplicate is in medium range
            has_medium = any(
                self.medium_threshold <= score < self.high_threshold
                for _, score in duplicates
            )
            if has_medium:
                review_candidates[canonical_id] = duplicates

        logger.info(
            f"Found {len(review_candidates)} clusters needing user review "
            f"(threshold={self.medium_threshold}-{self.high_threshold})"
        )
        return review_candidates

    @staticmethod
    def cosine_similarity(embedding1: List[float], embedding2: List[float]) -> float:
        """
        Calculate cosine similarity between two embeddings.

        Args:
            embedding1: First embedding vector
            embedding2: Second embedding vector

        Returns:
            Cosine similarity (0-1)
        """
        vec1 = np.array(embedding1)
        vec2 = np.array(embedding2)

        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return float(dot_product / (norm1 * norm2))
