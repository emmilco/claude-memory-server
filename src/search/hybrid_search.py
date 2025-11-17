"""Hybrid search combining BM25 keyword and vector semantic search."""

import logging
from typing import List, Tuple, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum

from src.search.bm25 import BM25
from src.core.models import MemoryUnit

logger = logging.getLogger(__name__)


class FusionMethod(str, Enum):
    """Methods for combining keyword and semantic search results."""
    WEIGHTED = "weighted"  # Weighted score combination
    RRF = "rrf"  # Reciprocal Rank Fusion
    CASCADE = "cascade"  # Keyword first, then semantic if needed


@dataclass
class HybridSearchResult:
    """Result from hybrid search with detailed scoring."""
    memory: MemoryUnit
    total_score: float
    vector_score: float
    bm25_score: float
    rank_vector: Optional[int] = None
    rank_bm25: Optional[int] = None
    fusion_method: str = "weighted"


class HybridSearcher:
    """
    Hybrid search combining BM25 keyword search with vector semantic search.

    This provides better recall by combining:
    - BM25: Good for exact term matches, technical terms, rare words
    - Vector: Good for conceptual similarity, synonyms, semantic meaning
    """

    def __init__(
        self,
        alpha: float = 0.5,
        fusion_method: FusionMethod = FusionMethod.WEIGHTED,
        bm25_k1: float = 1.5,
        bm25_b: float = 0.75,
        rrf_k: int = 60,
    ):
        """
        Initialize hybrid searcher.

        Args:
            alpha: Weight for combining scores (0=keyword only, 1=semantic only)
            fusion_method: Method for combining results
            bm25_k1: BM25 term saturation parameter
            bm25_b: BM25 length normalization parameter
            rrf_k: RRF constant (typically 60)
        """
        self.alpha = alpha
        self.fusion_method = fusion_method
        self.rrf_k = rrf_k

        # BM25 searcher
        self.bm25 = BM25(k1=bm25_k1, b=bm25_b)

        # Corpus tracking
        self.documents: List[str] = []
        self.memory_units: List[MemoryUnit] = []

    def index_documents(
        self,
        documents: List[str],
        memory_units: List[MemoryUnit]
    ) -> None:
        """
        Index documents for BM25 search.

        Args:
            documents: Text content of documents
            memory_units: Corresponding memory units
        """
        if len(documents) != len(memory_units):
            raise ValueError("Documents and memory units must have same length")

        self.documents = documents
        self.memory_units = memory_units

        # Build BM25 index
        self.bm25.fit(documents)

        logger.info(f"Indexed {len(documents)} documents for hybrid search")

    def hybrid_search(
        self,
        query: str,
        vector_results: List[Tuple[MemoryUnit, float]],
        limit: int = 10,
    ) -> List[HybridSearchResult]:
        """
        Perform hybrid search combining BM25 and vector results.

        Args:
            query: Search query
            vector_results: Results from vector search (memory, score)
            limit: Maximum number of results

        Returns:
            List of hybrid search results sorted by combined score
        """
        if not self.documents:
            logger.warning("No documents indexed for BM25 search")
            # Return vector results only
            return [
                HybridSearchResult(
                    memory=memory,
                    total_score=score,
                    vector_score=score,
                    bm25_score=0.0,
                    fusion_method=self.fusion_method.value
                )
                for memory, score in vector_results[:limit]
            ]

        # Get BM25 scores for all documents
        bm25_scores = self.bm25.get_scores(query)

        # Build BM25 results
        bm25_results = [
            (self.memory_units[i], bm25_scores[i])
            for i in range(len(self.memory_units))
        ]

        # Sort by BM25 score
        bm25_results.sort(key=lambda x: x[1], reverse=True)

        # Combine results based on fusion method
        if self.fusion_method == FusionMethod.WEIGHTED:
            return self._weighted_fusion(vector_results, bm25_results, limit)
        elif self.fusion_method == FusionMethod.RRF:
            return self._rrf_fusion(vector_results, bm25_results, limit)
        elif self.fusion_method == FusionMethod.CASCADE:
            return self._cascade_fusion(vector_results, bm25_results, limit)
        else:
            raise ValueError(f"Unknown fusion method: {self.fusion_method}")

    def _weighted_fusion(
        self,
        vector_results: List[Tuple[MemoryUnit, float]],
        bm25_results: List[Tuple[MemoryUnit, float]],
        limit: int,
    ) -> List[HybridSearchResult]:
        """
        Combine results using weighted score fusion.

        Score = alpha * vector_score + (1 - alpha) * bm25_score
        """
        # Normalize scores to [0, 1]
        vector_scores_norm = self._normalize_scores(
            [score for _, score in vector_results]
        )
        bm25_scores_norm = self._normalize_scores(
            [score for _, score in bm25_results]
        )

        # Build score dictionaries
        vector_score_dict = {
            memory.id: (score_norm, score_raw, rank)
            for rank, ((memory, score_raw), score_norm)
            in enumerate(zip(vector_results, vector_scores_norm))
        }

        bm25_score_dict = {
            memory.id: (score_norm, score_raw, rank)
            for rank, ((memory, score_raw), score_norm)
            in enumerate(zip(bm25_results, bm25_scores_norm))
        }

        # Combine scores for all unique memories
        all_memory_ids = set(vector_score_dict.keys()) | set(bm25_score_dict.keys())
        combined_results = []

        for memory_id in all_memory_ids:
            # Get scores (default to 0 if not present)
            vec_norm, vec_raw, vec_rank = vector_score_dict.get(memory_id, (0.0, 0.0, None))
            bm25_norm, bm25_raw, bm25_rank = bm25_score_dict.get(memory_id, (0.0, 0.0, None))

            # Combined score
            total_score = self.alpha * vec_norm + (1 - self.alpha) * bm25_norm

            # Find memory unit
            memory = next(
                (m for m, _ in vector_results if m.id == memory_id),
                next((m for m, _ in bm25_results if m.id == memory_id), None)
            )

            if memory:
                combined_results.append(HybridSearchResult(
                    memory=memory,
                    total_score=total_score,
                    vector_score=vec_raw,
                    bm25_score=bm25_raw,
                    rank_vector=vec_rank,
                    rank_bm25=bm25_rank,
                    fusion_method="weighted"
                ))

        # Sort by combined score
        combined_results.sort(key=lambda x: x.total_score, reverse=True)

        return combined_results[:limit]

    def _rrf_fusion(
        self,
        vector_results: List[Tuple[MemoryUnit, float]],
        bm25_results: List[Tuple[MemoryUnit, float]],
        limit: int,
    ) -> List[HybridSearchResult]:
        """
        Combine results using Reciprocal Rank Fusion.

        RRF score = Σ 1 / (k + rank_i)
        where k is typically 60
        """
        # Build rank dictionaries
        vector_ranks = {memory.id: rank for rank, (memory, _) in enumerate(vector_results)}
        bm25_ranks = {memory.id: rank for rank, (memory, _) in enumerate(bm25_results)}

        # Get all unique memories
        all_memory_ids = set(vector_ranks.keys()) | set(bm25_ranks.keys())
        combined_results = []

        for memory_id in all_memory_ids:
            # Calculate RRF score
            rrf_score = 0.0

            if memory_id in vector_ranks:
                rrf_score += 1.0 / (self.rrf_k + vector_ranks[memory_id] + 1)

            if memory_id in bm25_ranks:
                rrf_score += 1.0 / (self.rrf_k + bm25_ranks[memory_id] + 1)

            # Find memory unit and raw scores
            memory = None
            vec_score = 0.0
            bm25_score = 0.0

            for m, s in vector_results:
                if m.id == memory_id:
                    memory = m
                    vec_score = s
                    break

            if not memory:
                for m, s in bm25_results:
                    if m.id == memory_id:
                        memory = m
                        bm25_score = s
                        break
            else:
                # Also get BM25 score
                for m, s in bm25_results:
                    if m.id == memory_id:
                        bm25_score = s
                        break

            if memory:
                combined_results.append(HybridSearchResult(
                    memory=memory,
                    total_score=rrf_score,
                    vector_score=vec_score,
                    bm25_score=bm25_score,
                    rank_vector=vector_ranks.get(memory_id),
                    rank_bm25=bm25_ranks.get(memory_id),
                    fusion_method="rrf"
                ))

        # Sort by RRF score
        combined_results.sort(key=lambda x: x.total_score, reverse=True)

        return combined_results[:limit]

    def _cascade_fusion(
        self,
        vector_results: List[Tuple[MemoryUnit, float]],
        bm25_results: List[Tuple[MemoryUnit, float]],
        limit: int,
    ) -> List[HybridSearchResult]:
        """
        Cascade strategy: BM25 first, fill with vector if needed.

        Uses BM25 results, and if we don't have enough high-quality results,
        backfill with vector results.
        """
        # Start with top BM25 results
        results = []
        seen_ids = set()

        # Add BM25 results
        for rank, (memory, score) in enumerate(bm25_results[:limit]):
            if score > 0:  # Only include non-zero BM25 scores
                results.append(HybridSearchResult(
                    memory=memory,
                    total_score=score,
                    vector_score=0.0,  # Will update if also in vector results
                    bm25_score=score,
                    rank_bm25=rank,
                    fusion_method="cascade"
                ))
                seen_ids.add(memory.id)

        # Backfill with vector results if needed
        for rank, (memory, score) in enumerate(vector_results):
            if len(results) >= limit:
                break

            if memory.id not in seen_ids:
                results.append(HybridSearchResult(
                    memory=memory,
                    total_score=score,
                    vector_score=score,
                    bm25_score=0.0,
                    rank_vector=rank,
                    fusion_method="cascade"
                ))
                seen_ids.add(memory.id)

        return results[:limit]

    @staticmethod
    def _normalize_scores(scores: List[float]) -> List[float]:
        """
        Normalize scores to [0, 1] range.

        Args:
            scores: Raw scores

        Returns:
            Normalized scores
        """
        if not scores:
            return []

        min_score = min(scores)
        max_score = max(scores)

        if max_score == min_score:
            # All scores are the same
            return [1.0] * len(scores)

        # Min-max normalization
        return [
            (score - min_score) / (max_score - min_score)
            for score in scores
        ]
