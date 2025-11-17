"""Adaptive retrieval gate for query optimization.

This module implements a configurable gate that decides whether to perform
vector retrieval based on predicted utility, enabling significant performance
and token savings.
"""

import logging
from typing import Dict, Optional, Any
from datetime import datetime
from dataclasses import dataclass, field

from src.router.retrieval_predictor import RetrievalPredictor

logger = logging.getLogger(__name__)


@dataclass
class GatingDecision:
    """Result of a gating decision."""
    should_retrieve: bool
    utility_score: float
    reason: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class GatingMetrics:
    """Metrics for retrieval gating."""
    total_queries: int = 0
    queries_gated: int = 0
    queries_retrieved: int = 0
    total_utility_score: float = 0.0
    estimated_tokens_saved: int = 0

    @property
    def gating_rate(self) -> float:
        """Percentage of queries that were gated."""
        if self.total_queries == 0:
            return 0.0
        return (self.queries_gated / self.total_queries) * 100

    @property
    def average_utility(self) -> float:
        """Average utility score across all queries."""
        if self.total_queries == 0:
            return 0.0
        return self.total_utility_score / self.total_queries

    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary."""
        return {
            "total_queries": self.total_queries,
            "queries_gated": self.queries_gated,
            "queries_retrieved": self.queries_retrieved,
            "gating_rate": f"{self.gating_rate:.2f}%",
            "average_utility": f"{self.average_utility:.3f}",
            "estimated_tokens_saved": self.estimated_tokens_saved,
        }


class RetrievalGate:
    """
    Adaptive gate for controlling retrieval operations.

    Decides whether to perform vector retrieval based on predicted query utility,
    enabling performance optimization and token savings.

    Configuration:
    - threshold: Minimum utility score required to perform retrieval (default: 0.5)
    - tokens_per_result: Estimated tokens per search result (default: 200)
    - enable_logging: Whether to log gating decisions (default: True)
    """

    # Default configuration
    DEFAULT_THRESHOLD = 0.5
    DEFAULT_TOKENS_PER_RESULT = 200

    def __init__(
        self,
        threshold: float = DEFAULT_THRESHOLD,
        tokens_per_result: int = DEFAULT_TOKENS_PER_RESULT,
        enable_logging: bool = True,
        predictor: Optional[RetrievalPredictor] = None,
    ):
        """
        Initialize the retrieval gate.

        Args:
            threshold: Minimum utility score (0-1) to allow retrieval
            tokens_per_result: Estimated tokens per search result
            enable_logging: Whether to log gating decisions
            predictor: Optional custom predictor (creates default if None)
        """
        if not 0.0 <= threshold <= 1.0:
            raise ValueError(f"Threshold must be between 0 and 1, got {threshold}")

        self.threshold = threshold
        self.tokens_per_result = tokens_per_result
        self.enable_logging = enable_logging

        # Initialize predictor
        self.predictor = predictor or RetrievalPredictor()

        # Initialize metrics
        self.metrics = GatingMetrics()

        logger.info(
            f"Initialized RetrievalGate (threshold={threshold}, "
            f"tokens_per_result={tokens_per_result})"
        )

    def should_retrieve(
        self,
        query: str,
        expected_results: int = 5,
    ) -> GatingDecision:
        """
        Determine whether to perform retrieval for this query.

        Args:
            query: The search query
            expected_results: Expected number of results to return

        Returns:
            GatingDecision with the decision and reasoning
        """
        # Predict utility
        utility = self.predictor.predict_utility(query)

        # Make decision
        should_retrieve = utility >= self.threshold

        # Generate reason
        if should_retrieve:
            reason = f"Utility {utility:.3f} >= threshold {self.threshold}"
        else:
            reason = f"Utility {utility:.3f} < threshold {self.threshold} (gated)"

        # Update metrics
        self.metrics.total_queries += 1
        self.metrics.total_utility_score += utility

        if should_retrieve:
            self.metrics.queries_retrieved += 1
        else:
            self.metrics.queries_gated += 1
            # Estimate tokens saved by not retrieving
            estimated_tokens = expected_results * self.tokens_per_result
            self.metrics.estimated_tokens_saved += estimated_tokens

        # Log decision
        if self.enable_logging:
            log_level = logging.DEBUG if should_retrieve else logging.INFO
            logger.log(
                log_level,
                f"Gate: {'RETRIEVE' if should_retrieve else 'SKIP'} | "
                f"Query: '{query[:50]}...' | Utility: {utility:.3f} | "
                f"Threshold: {self.threshold}"
            )

        return GatingDecision(
            should_retrieve=should_retrieve,
            utility_score=utility,
            reason=reason,
        )

    def get_metrics(self) -> Dict[str, Any]:
        """
        Get current gating metrics.

        Returns:
            Dictionary with metrics
        """
        return self.metrics.to_dict()

    def reset_metrics(self) -> None:
        """Reset all metrics to zero."""
        self.metrics = GatingMetrics()
        logger.info("Reset gating metrics")

    def update_threshold(self, new_threshold: float) -> None:
        """
        Update the gating threshold.

        Args:
            new_threshold: New threshold value (0-1)
        """
        if not 0.0 <= new_threshold <= 1.0:
            raise ValueError(f"Threshold must be between 0 and 1, got {new_threshold}")

        old_threshold = self.threshold
        self.threshold = new_threshold
        logger.info(f"Updated gating threshold: {old_threshold} -> {new_threshold}")

    def get_explanation(self, query: str) -> str:
        """
        Get human-readable explanation of how the gate would handle this query.

        Args:
            query: The query to analyze

        Returns:
            Explanation string
        """
        utility = self.predictor.predict_utility(query)
        decision = "RETRIEVE" if utility >= self.threshold else "SKIP"

        explanation = self.predictor.get_explanation(query, utility)
        explanation += f"\nDecision: {decision} (threshold: {self.threshold})"

        return explanation

    def __repr__(self) -> str:
        """String representation of the gate."""
        return (
            f"RetrievalGate(threshold={self.threshold}, "
            f"gated={self.metrics.queries_gated}/{self.metrics.total_queries})"
        )
