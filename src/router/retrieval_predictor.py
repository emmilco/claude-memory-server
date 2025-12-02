"""Retrieval utility predictor for adaptive query gating.

This module implements heuristic-based prediction of whether retrieval
will be useful for a given query, enabling intelligent skipping of
unnecessary vector searches.
"""

import re
import logging
from typing import Dict

logger = logging.getLogger(__name__)


class RetrievalPredictor:
    """
    Predicts the utility of retrieval for a given query.

    Uses heuristic rules to analyze query characteristics and determine
    whether performing a vector search is likely to yield useful results.

    Target: Skip 30-40% of queries that are unlikely to benefit from retrieval.
    """

    # Query patterns that typically don't need retrieval
    SMALL_TALK_PATTERNS = [
        r"\b(hi|hello|hey|thanks|thank you|ok|okay|sure|yes|no|got it)\b",
        r"^(great|cool|nice|awesome|perfect)[\s!.]*$",
        r"\b(bye|goodbye|see you|ttyl)\b",
    ]

    # Query patterns that typically DO need retrieval
    NEEDS_RETRIEVAL_PATTERNS = [
        r"\b(how|what|where|when|why|who|which)\b",
        r"\b(find|search|show|get|retrieve|look up)\b",
        r"\b(code|function|class|method|file|implementation)\b",
        r"\b(error|bug|issue|problem|fix)\b",
        r"\b(remember|recall|stored|saved|previous)\b",
        r"\b(example|pattern|similar|like)\b",
    ]

    # Technical/code-related keywords
    TECHNICAL_KEYWORDS = [
        "api",
        "endpoint",
        "database",
        "query",
        "authentication",
        "auth",
        "test",
        "config",
        "deployment",
        "server",
        "client",
        "request",
        "response",
        "handler",
        "middleware",
        "model",
        "controller",
        "service",
        "repository",
        "component",
        "module",
        "package",
        "import",
        "export",
        "interface",
        "type",
        "variable",
        "constant",
        "async",
        "await",
        "promise",
        "callback",
        "event",
        "listener",
    ]

    def __init__(
        self,
        min_query_length: int = 10,
        max_small_talk_length: int = 30,
    ):
        """
        Initialize the retrieval predictor.

        Args:
            min_query_length: Minimum query length to consider for retrieval
            max_small_talk_length: Maximum length for small talk detection
        """
        self.min_query_length = min_query_length
        self.max_small_talk_length = max_small_talk_length

        # Compile regex patterns for efficiency
        self._small_talk_regex = re.compile(
            "|".join(self.SMALL_TALK_PATTERNS), re.IGNORECASE
        )
        self._needs_retrieval_regex = re.compile(
            "|".join(self.NEEDS_RETRIEVAL_PATTERNS), re.IGNORECASE
        )

        logger.info("Initialized RetrievalPredictor")

    def predict_utility(self, query: str) -> float:
        """
        Predict the utility of performing retrieval for this query.

        Args:
            query: The search query text

        Returns:
            Float between 0 and 1 representing predicted utility:
            - 0.0: Retrieval definitely not useful
            - 0.5: Uncertain, may or may not be useful
            - 1.0: Retrieval definitely useful
        """
        if not query or not query.strip():
            return 0.0

        query = query.strip()
        query_lower = query.lower()

        # Calculate various signals
        signals = self._extract_signals(query, query_lower)

        # Compute utility score based on signals
        utility = self._compute_utility(signals)

        logger.debug(
            f"Query: '{query[:50]}...' | Utility: {utility:.3f} | Signals: {signals}"
        )

        return utility

    def _extract_signals(self, query: str, query_lower: str) -> Dict[str, float]:
        """Extract various signals from the query."""
        signals = {}

        # Length-based signals
        query_length = len(query)
        signals["length"] = query_length
        signals["is_very_short"] = 1.0 if query_length < self.min_query_length else 0.0
        signals["is_small_talk_length"] = (
            1.0 if query_length <= self.max_small_talk_length else 0.0
        )

        # Pattern matching signals
        signals["has_small_talk"] = (
            1.0 if self._small_talk_regex.search(query_lower) else 0.0
        )
        signals["has_retrieval_keywords"] = (
            1.0 if self._needs_retrieval_regex.search(query_lower) else 0.0
        )

        # Technical content signals
        technical_count = sum(1 for kw in self.TECHNICAL_KEYWORDS if kw in query_lower)
        signals["technical_keyword_count"] = technical_count
        signals["has_technical_content"] = 1.0 if technical_count > 0 else 0.0

        # Question detection
        signals["is_question"] = 1.0 if "?" in query else 0.0

        # Code-like patterns
        signals["has_code_markers"] = (
            1.0
            if any(marker in query for marker in ["()", "{}", "[]", "->", "=>", "::"])
            else 0.0
        )

        # Specificity indicators
        signals["word_count"] = len(query.split())
        signals["is_specific"] = 1.0 if signals["word_count"] >= 4 else 0.0

        return signals

    def _compute_utility(self, signals: Dict[str, float]) -> float:
        """
        Compute utility score from extracted signals.

        Uses a weighted scoring system based on heuristic rules.
        """
        # Start with neutral utility
        utility = 0.5

        # Strong negative indicators (reduce utility)
        if signals["is_very_short"] and signals["has_small_talk"]:
            return 0.0  # Definitely skip: "ok", "thanks", etc.

        if (
            signals["is_small_talk_length"]
            and signals["has_small_talk"]
            and not signals["has_retrieval_keywords"]
        ):
            return 0.1  # Very likely skip: "cool, got it"

        # Strong positive indicators (increase utility)
        if signals["has_retrieval_keywords"]:
            utility += 0.3

        if signals["has_technical_content"]:
            utility += 0.2

        if signals["is_question"]:
            utility += 0.15

        if signals["has_code_markers"]:
            utility += 0.15

        if signals["is_specific"]:
            utility += 0.1

        # Length-based adjustments
        if signals["length"] > 50:
            utility += 0.1  # Longer queries more likely to need context

        if signals["technical_keyword_count"] >= 3:
            utility += 0.1  # Multiple technical terms = likely needs retrieval

        # Negative adjustments
        if signals["has_small_talk"] and not signals["has_retrieval_keywords"]:
            utility -= 0.3

        if signals["word_count"] <= 2 and not signals["has_code_markers"]:
            utility -= 0.2  # Very short, non-code queries less likely to need retrieval

        # Clamp to [0, 1]
        return max(0.0, min(1.0, utility))

    def get_explanation(self, query: str, utility: float) -> str:
        """
        Get human-readable explanation of the utility prediction.

        Args:
            query: The query that was analyzed
            utility: The predicted utility score

        Returns:
            String explanation of the decision
        """
        query_lower = query.lower()
        signals = self._extract_signals(query, query_lower)

        if utility < 0.3:
            reason = "Query appears to be small talk or very generic"
            if signals["has_small_talk"]:
                reason += " (matches small talk patterns)"
        elif utility > 0.7:
            reasons = []
            if signals["has_retrieval_keywords"]:
                reasons.append("contains retrieval keywords")
            if signals["has_technical_content"]:
                reasons.append("has technical content")
            if signals["is_question"]:
                reasons.append("is a question")
            reason = f"Query likely needs context: {', '.join(reasons)}"
        else:
            reason = "Query utility uncertain, will perform retrieval"

        return f"Utility: {utility:.2f} - {reason}"
