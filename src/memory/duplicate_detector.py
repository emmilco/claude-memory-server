"""Duplicate memory detection using semantic similarity (FEAT-035 Phase 1, enhanced in FEAT-060)."""

import logging
import numpy as np
from typing import List, Tuple, Optional, Dict, Any, Set
from datetime import datetime, UTC
from dataclasses import dataclass

from src.core.models import MemoryUnit, MemoryCategory
from src.store.base import MemoryStore
from src.embeddings.generator import EmbeddingGenerator
from src.core.exceptions import ValidationError
from src.config import DEFAULT_EMBEDDING_DIM

logger = logging.getLogger(__name__)


@dataclass
class DuplicateMember:
    """Member of a duplicate cluster."""
    id: str
    file_path: str
    unit_name: str
    similarity_to_canonical: float
    line_count: int


@dataclass
class DuplicateCluster:
    """Group of similar code units."""
    canonical_id: str  # ID of the "best" version
    canonical_name: str
    canonical_file: str
    members: List[DuplicateMember]
    average_similarity: float
    cluster_size: int

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "canonical_id": self.canonical_id,
            "canonical_name": self.canonical_name,
            "canonical_file": self.canonical_file,
            "members": [
                {
                    "id": m.id,
                    "file_path": m.file_path,
                    "unit_name": m.unit_name,
                    "similarity": m.similarity_to_canonical,
                    "line_count": m.line_count,
                }
                for m in self.members
            ],
            "average_similarity": self.average_similarity,
            "cluster_size": self.cluster_size,
        }


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
                query_embedding=[0.0] * DEFAULT_EMBEDDING_DIM,
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

    async def cluster_duplicates(
        self,
        min_threshold: float = 0.85,
        project_name: Optional[str] = None,
        category: Optional[MemoryCategory] = None,
    ) -> List[DuplicateCluster]:
        """
        Group similar code into duplicate clusters.

        Algorithm:
        1. Get all code units (category=CODE or specified category)
        2. For each unit, find duplicates above threshold
        3. Build clusters using union-find algorithm
        4. Select canonical member (best quality: documented, lowest complexity)
        5. Return clusters sorted by size (largest first)

        Args:
            min_threshold: Minimum similarity threshold (default: 0.85)
            project_name: Optional project filter
            category: Optional category filter (default: CODE)

        Returns:
            List of duplicate clusters, sorted by cluster size descending
        """
        try:
            # Get all code units
            from src.core.models import SearchFilters, MemoryCategory
            filters = SearchFilters(
                project_name=project_name,
                category=category or MemoryCategory.CODE,
            )

            all_code_results = await self.store.retrieve(
                query_embedding=[0.0] * DEFAULT_EMBEDDING_DIM,
                filters=filters,
                limit=10000,
            )
            all_code = [mem for mem, _ in all_code_results]

            if not all_code:
                logger.info("No code units found for clustering")
                return []

            logger.info(f"Clustering {len(all_code)} code units (threshold={min_threshold})")

            # Build similarity graph (edges)
            edges: List[Tuple[str, str, float]] = []
            for unit in all_code:
                duplicates = await self.find_duplicates(unit, min_threshold=min_threshold)
                for dup, score in duplicates:
                    # Add edge (avoid duplicates by sorting IDs)
                    id1, id2 = sorted([unit.id, dup.id])
                    edges.append((id1, id2, score))

            # Remove duplicate edges
            unique_edges = {}
            for id1, id2, score in edges:
                key = (id1, id2)
                if key not in unique_edges or score > unique_edges[key]:
                    unique_edges[key] = score

            edges = [(id1, id2, score) for (id1, id2), score in unique_edges.items()]

            logger.debug(f"Found {len(edges)} unique duplicate pairs")

            # Union-find clustering
            clusters_dict = self._union_find_clustering(edges, all_code)

            # Convert to DuplicateCluster objects
            clusters = []
            for canonical_id, members_data in clusters_dict.items():
                # Find canonical memory
                canonical = next((m for m in all_code if m.id == canonical_id), None)
                if not canonical:
                    continue

                # Create cluster
                members = []
                total_similarity = 0.0
                for member_id, similarity in members_data:
                    member = next((m for m in all_code if m.id == member_id), None)
                    if member:
                        members.append(DuplicateMember(
                            id=member.id,
                            file_path=member.metadata.get("file_path", "unknown"),
                            unit_name=member.metadata.get("unit_name", "unknown"),
                            similarity_to_canonical=similarity,
                            line_count=member.metadata.get("line_count", 0),
                        ))
                        total_similarity += similarity

                if members:
                    avg_similarity = total_similarity / len(members)
                    clusters.append(DuplicateCluster(
                        canonical_id=canonical_id,
                        canonical_name=canonical.metadata.get("unit_name", "unknown"),
                        canonical_file=canonical.metadata.get("file_path", "unknown"),
                        members=members,
                        average_similarity=avg_similarity,
                        cluster_size=len(members) + 1,  # +1 for canonical
                    ))

            # Sort by cluster size (largest first)
            clusters.sort(key=lambda c: c.cluster_size, reverse=True)

            logger.info(f"Found {len(clusters)} duplicate clusters")
            return clusters

        except Exception as e:
            logger.error(f"Error clustering duplicates: {e}")
            raise

    def _union_find_clustering(
        self,
        edges: List[Tuple[str, str, float]],
        all_memories: List[MemoryUnit],
    ) -> Dict[str, List[Tuple[str, float]]]:
        """
        Use union-find algorithm to cluster connected memories.

        Args:
            edges: List of (id1, id2, similarity_score) tuples
            all_memories: All memory units

        Returns:
            Dict mapping canonical_id to list of (member_id, similarity) tuples
        """
        # Initialize union-find structure
        parent: Dict[str, str] = {}
        for memory in all_memories:
            parent[memory.id] = memory.id

        # Find with path compression
        def find(x: str) -> str:
            if parent[x] != x:
                parent[x] = find(parent[x])
            return parent[x]

        # Union operation
        def union(x: str, y: str):
            root_x = find(x)
            root_y = find(y)
            if root_x != root_y:
                parent[root_y] = root_x

        # Build clusters
        for id1, id2, _ in edges:
            union(id1, id2)

        # Group by root (canonical)
        clusters: Dict[str, List[str]] = {}
        for memory in all_memories:
            root = find(memory.id)
            if root not in clusters:
                clusters[root] = []
            if memory.id != root:
                clusters[root].append(memory.id)

        # Find similarities to canonical
        edge_map = {(id1, id2): score for id1, id2, score in edges}
        result: Dict[str, List[Tuple[str, float]]] = {}

        for canonical_id, member_ids in clusters.items():
            if not member_ids:  # Skip singleton clusters
                continue

            members_with_scores = []
            for member_id in member_ids:
                # Find similarity to canonical
                id1, id2 = sorted([canonical_id, member_id])
                similarity = edge_map.get((id1, id2), 0.0)
                members_with_scores.append((member_id, similarity))

            # Select best canonical (most documented, lowest complexity if available)
            canonical = self._select_canonical(
                canonical_id,
                member_ids,
                all_memories,
            )
            result[canonical] = members_with_scores

        return result

    def _select_canonical(
        self,
        current_canonical: str,
        members: List[str],
        all_memories: List[MemoryUnit],
    ) -> str:
        """
        Select the best canonical member from a cluster.

        Preference order:
        1. Has documentation
        2. Lowest complexity (if available in metadata)
        3. Shortest (least lines)

        Args:
            current_canonical: Current canonical ID
            members: List of member IDs
            all_memories: All memory units

        Returns:
            ID of best canonical member
        """
        all_ids = [current_canonical] + members
        candidates = [m for m in all_memories if m.id in all_ids]

        # Score each candidate
        def score_candidate(mem: MemoryUnit) -> Tuple[int, int, int]:
            has_docs = mem.metadata.get("has_documentation", False)
            complexity = mem.metadata.get("cyclomatic_complexity", 999)
            line_count = mem.metadata.get("line_count", 999)

            # Return tuple for sorting (higher is better)
            return (
                1 if has_docs else 0,  # Prefer documented
                -complexity,  # Prefer lower complexity
                -line_count,  # Prefer shorter
            )

        # Sort and pick best
        candidates.sort(key=score_candidate, reverse=True)
        return candidates[0].id if candidates else current_canonical

    async def calculate_duplication_score(
        self,
        code_unit: MemoryUnit,
    ) -> float:
        """
        Calculate duplication score for a single unit.

        Returns:
            0.0 = unique code (no duplicates)
            1.0 = exact duplicate exists
            0.5-0.9 = partial duplicates exist
        """
        try:
            # Find top 3 most similar code units
            duplicates = await self.find_duplicates(code_unit, min_threshold=0.75)

            if not duplicates:
                return 0.0

            # Return highest similarity score
            return duplicates[0][1]  # (unit, score)

        except Exception as e:
            logger.error(f"Error calculating duplication score: {e}")
            return 0.0
