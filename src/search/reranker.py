"""Result reranking for improved search relevance."""

import logging
import re
from typing import List, Tuple, Optional, Callable
from datetime import datetime, timezone
from dataclasses import dataclass

from src.core.models import MemoryUnit

logger = logging.getLogger(__name__)


@dataclass
class RerankingWeights:
    """Weights for different ranking signals."""
    similarity: float = 0.6  # Vector similarity score
    recency: float = 0.2  # How recent the memory is
    usage: float = 0.2  # How frequently accessed
    length_penalty: float = 0.0  # Penalty for very long/short content
    keyword_boost: float = 0.0  # Boost for exact keyword matches


class ResultReranker:
    """
    Rerank search results using multiple signals.

    Provides advanced reranking strategies beyond simple vector similarity:
    - Recency decay (favor recent memories)
    - Usage frequency (favor frequently accessed memories)
    - Length normalization (penalize very long or very short results)
    - Keyword matching boost (boost exact keyword matches)
    - Diversity promotion (reduce redundancy in top results)
    """

    def __init__(
        self,
        weights: Optional[RerankingWeights] = None,
        recency_halflife_days: float = 7.0,
        diversity_penalty: float = 0.0,
    ):
        """
        Initialize reranker.

        Args:
            weights: Weights for different signals
            recency_halflife_days: Half-life for recency decay (default 7 days)
            diversity_penalty: Penalty for similar results (0-1, default 0)
        """
        self.weights = weights or RerankingWeights()
        self.recency_halflife_days = recency_halflife_days
        self.diversity_penalty = diversity_penalty

        # Validate weights sum to reasonable range
        total_weight = (
            self.weights.similarity +
            self.weights.recency +
            self.weights.usage
        )
        if total_weight < 0.9 or total_weight > 1.1:
            logger.warning(
                f"Reranking weights sum to {total_weight:.2f}, "
                "should be close to 1.0"
            )

        # Statistics
        self.stats = {
            "reranks_performed": 0,
            "avg_position_change": 0.0,
            "diversity_dedupes": 0,
        }

    def rerank(
        self,
        results: List[Tuple[MemoryUnit, float]],
        query: Optional[str] = None,
        usage_data: Optional[dict] = None,
    ) -> List[Tuple[MemoryUnit, float]]:
        """
        Rerank results using multiple signals.

        Args:
            results: List of (memory, similarity_score) tuples
            query: Original query (for keyword matching)
            usage_data: Dict mapping memory_id -> usage stats
                       {"last_used": datetime, "use_count": int}

        Returns:
            Reranked list of (memory, combined_score) tuples
        """
        if not results:
            return []

        self.stats["reranks_performed"] += 1

        # Calculate all signals
        reranked = []
        for memory, similarity_score in results:
            # Recency score
            recency_score = self._calculate_recency_score(memory)

            # Usage score
            usage_score = self._calculate_usage_score(memory, usage_data)

            # Length penalty
            length_penalty = self._calculate_length_penalty(memory)

            # Keyword boost
            keyword_boost = self._calculate_keyword_boost(memory, query)

            # Combined score
            combined_score = (
                self.weights.similarity * similarity_score +
                self.weights.recency * recency_score +
                self.weights.usage * usage_score +
                self.weights.length_penalty * length_penalty +
                self.weights.keyword_boost * keyword_boost
            )

            reranked.append((memory, combined_score))

        # Sort by combined score
        reranked.sort(key=lambda x: x[1], reverse=True)

        # Apply diversity penalty if enabled
        if self.diversity_penalty > 0:
            reranked = self._apply_diversity(reranked, query)

        # Track position changes
        self._track_position_changes(results, reranked)

        return reranked

    def _calculate_recency_score(self, memory: MemoryUnit) -> float:
        """
        Calculate recency score with exponential decay.

        Args:
            memory: Memory unit

        Returns:
            Recency score (0-1)
        """
        if not memory.updated_at:
            return 0.5  # Neutral score if no timestamp

        # Time since update - normalize both datetimes to UTC to avoid timezone mismatch
        now = datetime.now(timezone.utc)

        # Ensure updated_at is timezone-aware (convert if naive)
        updated_at = memory.updated_at
        if updated_at.tzinfo is None:
            # Assume naive datetimes are in UTC
            updated_at = updated_at.replace(tzinfo=timezone.utc)
        else:
            # Convert to UTC if in different timezone
            updated_at = updated_at.astimezone(timezone.utc)

        age_seconds = (now - updated_at).total_seconds()
        age_days = age_seconds / 86400.0

        # Exponential decay: score = 0.5^(age / halflife)
        # halflife days -> score = 0.5
        # 0 days -> score = 1.0
        import math
        decay_factor = math.pow(0.5, age_days / self.recency_halflife_days)

        return min(1.0, decay_factor)

    def _calculate_usage_score(
        self,
        memory: MemoryUnit,
        usage_data: Optional[dict],
    ) -> float:
        """
        Calculate usage frequency score.

        Args:
            memory: Memory unit
            usage_data: Usage statistics

        Returns:
            Usage score (0-1)
        """
        if not usage_data or memory.id not in usage_data:
            return 0.0  # No usage data

        stats = usage_data[memory.id]
        use_count = stats.get("use_count", 0)

        # Logarithmic scaling: score = log(count + 1) / log(max + 1)
        # This prevents very frequently used items from dominating
        import math
        max_use_count = max(
            (s.get("use_count", 0) for s in usage_data.values()),
            default=1
        )

        if max_use_count == 0:
            return 0.0

        score = math.log(use_count + 1) / math.log(max_use_count + 1)
        return min(1.0, score)

    def _calculate_length_penalty(self, memory: MemoryUnit) -> float:
        """
        Calculate length penalty/boost.

        Very short results might be incomplete.
        Very long results might be less focused.

        Args:
            memory: Memory unit

        Returns:
            Length score (-1 to 0, penalty only)
        """
        content_length = len(memory.content)

        # Ideal length range: 100-500 characters
        if 100 <= content_length <= 500:
            return 0.0  # No penalty

        # Too short (< 100)
        if content_length < 100:
            penalty = (100 - content_length) / 100.0
            return -min(0.5, penalty)

        # Too long (> 500)
        if content_length > 500:
            penalty = (content_length - 500) / 1000.0
            return -min(0.5, penalty)

        return 0.0

    def _calculate_keyword_boost(
        self,
        memory: MemoryUnit,
        query: Optional[str],
    ) -> float:
        """
        Calculate keyword matching boost.

        Args:
            memory: Memory unit
            query: Search query

        Returns:
            Keyword boost (0-1)
        """
        if not query:
            return 0.0

        # Extract keywords from query
        keywords = re.findall(r'\w+', query.lower())
        if not keywords:
            return 0.0

        # Count exact matches in content
        content_lower = memory.content.lower()
        matches = sum(1 for kw in keywords if kw in content_lower)

        # Boost based on match percentage
        match_ratio = matches / len(keywords)
        return match_ratio

    def _apply_diversity(
        self,
        results: List[Tuple[MemoryUnit, float]],
        query: Optional[str],
    ) -> List[Tuple[MemoryUnit, float]]:
        """
        Apply diversity penalty to reduce redundancy.

        Penalizes results that are very similar to higher-ranked results.

        Args:
            results: Ranked results
            query: Original query

        Returns:
            Results with diversity penalty applied
        """
        if len(results) <= 1:
            return results

        diverse_results = []
        seen_content_signatures = set()

        for memory, score in results:
            # Create content signature (first 100 chars)
            signature = memory.content[:100].lower().strip()

            # Check similarity to already selected results
            is_duplicate = False
            for seen_sig in seen_content_signatures:
                similarity = self._simple_similarity(signature, seen_sig)
                if similarity > 0.8:  # Very similar
                    # Apply diversity penalty
                    score *= (1.0 - self.diversity_penalty)
                    is_duplicate = True
                    self.stats["diversity_dedupes"] += 1
                    break

            diverse_results.append((memory, score))
            if not is_duplicate:
                seen_content_signatures.add(signature)

        # Re-sort after penalty
        diverse_results.sort(key=lambda x: x[1], reverse=True)

        return diverse_results

    @staticmethod
    def _simple_similarity(text1: str, text2: str) -> float:
        """
        Calculate simple Jaccard similarity between two texts.

        Args:
            text1: First text
            text2: Second text

        Returns:
            Similarity score (0-1)
        """
        # Tokenize
        tokens1 = set(re.findall(r'\w+', text1.lower()))
        tokens2 = set(re.findall(r'\w+', text2.lower()))

        if not tokens1 or not tokens2:
            return 0.0

        # Jaccard similarity
        intersection = len(tokens1 & tokens2)
        union = len(tokens1 | tokens2)

        return intersection / union if union > 0 else 0.0

    def _track_position_changes(
        self,
        original: List[Tuple[MemoryUnit, float]],
        reranked: List[Tuple[MemoryUnit, float]],
    ):
        """
        Track how much positions changed due to reranking.

        Args:
            original: Original ranking
            reranked: After reranking
        """
        if len(original) != len(reranked):
            return

        # Build position maps
        original_positions = {
            mem.id: i for i, (mem, _) in enumerate(original)
        }

        total_change = 0
        for new_pos, (mem, _) in enumerate(reranked):
            if mem.id in original_positions:
                old_pos = original_positions[mem.id]
                total_change += abs(new_pos - old_pos)

        # Update average
        count = self.stats["reranks_performed"]
        current_avg = self.stats["avg_position_change"]
        self.stats["avg_position_change"] = (
            (current_avg * (count - 1) + total_change / len(reranked)) / count
        )

    def get_stats(self) -> dict:
        """Get reranking statistics."""
        return self.stats.copy()


class MMRReranker:
    """
    Maximal Marginal Relevance (MMR) reranker.

    Balances relevance and diversity by iteratively selecting results
    that are relevant to the query but different from already selected results.
    """

    def __init__(self, lambda_param: float = 0.5):
        """
        Initialize MMR reranker.

        Args:
            lambda_param: Balance between relevance (1.0) and diversity (0.0)
                         Default 0.5 = equal balance
        """
        self.lambda_param = lambda_param

    def rerank(
        self,
        results: List[Tuple[MemoryUnit, float]],
        k: int = 10,
    ) -> List[Tuple[MemoryUnit, float]]:
        """
        Rerank using MMR algorithm.

        Args:
            results: List of (memory, similarity_score) tuples
            k: Number of results to return

        Returns:
            Reranked results with diversity
        """
        if not results or k <= 0:
            return []

        # Start with empty selection
        selected = []
        remaining = list(results)

        # Iteratively select k results
        for _ in range(min(k, len(results))):
            if not remaining:
                break

            # Calculate MMR score for each remaining result
            best_idx = 0
            best_score = float('-inf')

            for idx, (memory, relevance) in enumerate(remaining):
                # Relevance component
                relevance_score = relevance

                # Diversity component (max similarity to selected)
                if selected:
                    max_similarity = max(
                        self._content_similarity(memory, sel_mem)
                        for sel_mem, _ in selected
                    )
                else:
                    max_similarity = 0.0

                # MMR formula: λ * relevance - (1-λ) * max_similarity
                mmr_score = (
                    self.lambda_param * relevance_score -
                    (1 - self.lambda_param) * max_similarity
                )

                if mmr_score > best_score:
                    best_score = mmr_score
                    best_idx = idx

            # Select best and move to selected list
            best_result = remaining.pop(best_idx)
            selected.append(best_result)

        return selected

    @staticmethod
    def _content_similarity(mem1: MemoryUnit, mem2: MemoryUnit) -> float:
        """
        Calculate content similarity between two memories.

        Args:
            mem1: First memory
            mem2: Second memory

        Returns:
            Similarity score (0-1)
        """
        # Simple Jaccard similarity
        tokens1 = set(re.findall(r'\w+', mem1.content.lower()))
        tokens2 = set(re.findall(r'\w+', mem2.content.lower()))

        if not tokens1 or not tokens2:
            return 0.0

        intersection = len(tokens1 & tokens2)
        union = len(tokens1 | tokens2)

        return intersection / union if union > 0 else 0.0


def rerank_with_custom_function(
    results: List[Tuple[MemoryUnit, float]],
    scoring_fn: Callable[[MemoryUnit, float], float],
) -> List[Tuple[MemoryUnit, float]]:
    """
    Rerank results using a custom scoring function.

    Args:
        results: Original results
        scoring_fn: Function that takes (memory, original_score) and returns new score

    Returns:
        Reranked results
    """
    rescored = [
        (memory, scoring_fn(memory, score))
        for memory, score in results
    ]

    rescored.sort(key=lambda x: x[1], reverse=True)
    return rescored
