"""Proactive suggestion engine with adaptive learning.

This module analyzes conversations and automatically suggests relevant context
based on detected patterns, with an adaptive threshold that learns from user feedback.
"""

import logging
import asyncio
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, UTC
from dataclasses import dataclass, field
from uuid import uuid4

from src.config import ServerConfig
from src.store import MemoryStore
from src.core.models import SearchFilters, MemoryResult
from src.memory.pattern_detector import PatternDetector, DetectedPattern, PatternType
from src.memory.feedback_tracker import FeedbackTracker

logger = logging.getLogger(__name__)


@dataclass
class SuggestionResult:
    """Result from suggestion engine analysis."""

    suggestion_id: str
    patterns: List[DetectedPattern]
    should_inject: bool  # True if we should auto-inject context
    search_results: List[MemoryResult] = field(default_factory=list)
    notification_text: Optional[str] = None
    confidence: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    search_performed: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "suggestion_id": self.suggestion_id,
            "patterns": [
                {
                    "type": p.pattern_type.value,
                    "confidence": p.confidence,
                    "query": p.search_query,
                }
                for p in self.patterns
            ],
            "should_inject": self.should_inject,
            "search_performed": self.search_performed,
            "result_count": len(self.search_results),
            "notification": self.notification_text,
            "confidence": self.confidence,
            "timestamp": self.timestamp.isoformat(),
        }


class SuggestionEngine:
    """
    Generate proactive context suggestions with adaptive learning.

    Features:
    - Detect patterns in user messages
    - Automatically search for relevant context
    - Auto-inject at high confidence (>threshold)
    - Adaptive threshold based on user feedback
    - Track suggestion metrics
    """

    # Default configuration
    DEFAULT_HIGH_CONFIDENCE_THRESHOLD = 0.90
    DEFAULT_MEDIUM_CONFIDENCE_THRESHOLD = 0.70
    MAX_SEARCH_RESULTS = 5

    def __init__(
        self,
        config: ServerConfig,
        store: MemoryStore,
        pattern_detector: Optional[PatternDetector] = None,
        feedback_tracker: Optional[FeedbackTracker] = None,
    ):
        """
        Initialize suggestion engine.

        Args:
            config: Server configuration
            store: Memory store for searching
            pattern_detector: Optional custom pattern detector
            feedback_tracker: Optional custom feedback tracker
        """
        self.config = config
        self.store = store

        # Initialize components
        self.pattern_detector = pattern_detector or PatternDetector()
        self.feedback_tracker = feedback_tracker or FeedbackTracker()

        # Adaptive threshold (starts at 0.90, adjusts based on feedback)
        self.high_confidence_threshold = self.DEFAULT_HIGH_CONFIDENCE_THRESHOLD
        self.medium_confidence_threshold = self.DEFAULT_MEDIUM_CONFIDENCE_THRESHOLD

        # Feature flag
        self.enabled = True

        # Statistics
        self.stats = {
            "messages_analyzed": 0,
            "patterns_detected": 0,
            "suggestions_made": 0,
            "auto_injections": 0,
            "searches_performed": 0,
        }

        logger.info(
            f"Initialized SuggestionEngine "
            f"(threshold={self.high_confidence_threshold:.2f})"
        )

    async def analyze_message(
        self,
        message: str,
        session_id: Optional[str] = None,
        project_name: Optional[str] = None,
    ) -> SuggestionResult:
        """
        Analyze a user message for proactive suggestions.

        Args:
            message: The user's message
            session_id: Optional conversation session ID
            project_name: Optional project context

        Returns:
            SuggestionResult with detected patterns and suggestions
        """
        self.stats["messages_analyzed"] += 1

        # Check if enabled
        if not self.enabled:
            logger.debug("Suggestion engine disabled")
            return SuggestionResult(
                suggestion_id=str(uuid4()),
                patterns=[],
                should_inject=False,
            )

        # Detect patterns
        patterns = self.pattern_detector.detect_patterns(message)

        if not patterns:
            logger.debug("No patterns detected in message")
            return SuggestionResult(
                suggestion_id=str(uuid4()),
                patterns=[],
                should_inject=False,
            )

        self.stats["patterns_detected"] += len(patterns)

        # Use highest confidence pattern
        primary_pattern = patterns[0]  # Already sorted by confidence

        # Determine if we should auto-inject
        should_inject = primary_pattern.confidence >= self.high_confidence_threshold

        # Generate suggestion ID
        suggestion_id = str(uuid4())

        # Record suggestion for feedback tracking
        self.feedback_tracker.record_suggestion(
            pattern_type=primary_pattern.pattern_type,
            confidence=primary_pattern.confidence,
            suggestion_id=suggestion_id,
        )

        # Perform search if we're going to show results
        search_results: List[MemoryResult] = []
        search_performed = False

        if (
            should_inject
            or primary_pattern.confidence >= self.medium_confidence_threshold
        ):
            # Perform search
            search_results = await self._perform_search(
                primary_pattern, project_name
            )
            search_performed = True
            self.stats["searches_performed"] += 1

        # Generate notification if we have results
        notification_text = None
        if search_results:
            notification_text = self._format_notification(
                primary_pattern, search_results
            )
            self.stats["suggestions_made"] += 1

            if should_inject:
                self.stats["auto_injections"] += 1

        # Create result
        result = SuggestionResult(
            suggestion_id=suggestion_id,
            patterns=patterns,
            should_inject=should_inject and len(search_results) > 0,
            search_results=search_results,
            notification_text=notification_text,
            confidence=primary_pattern.confidence,
            search_performed=search_performed,
        )

        logger.info(
            f"Analyzed message: {len(patterns)} patterns, "
            f"confidence={primary_pattern.confidence:.2f}, "
            f"inject={result.should_inject}, "
            f"results={len(search_results)}"
        )

        return result

    async def _perform_search(
        self, pattern: DetectedPattern, project_name: Optional[str]
    ) -> List[MemoryResult]:
        """
        Perform search based on detected pattern.

        Args:
            pattern: Detected pattern with search query
            project_name: Optional project context

        Returns:
            List of search results
        """
        try:
            # Build search filters
            filters = SearchFilters()
            if project_name:
                filters.project_name = project_name

            # Perform search based on strategy
            if pattern.search_strategy == "find_similar_code":
                # Use code search for implementation patterns
                results = await self.store.search_code(
                    query=pattern.search_query,
                    filters=filters,
                    limit=self.MAX_SEARCH_RESULTS,
                )
            else:
                # Default: semantic search
                results = await self.store.search(
                    query=pattern.search_query,
                    filters=filters,
                    limit=self.MAX_SEARCH_RESULTS,
                )

            logger.debug(
                f"Search for '{pattern.search_query}' returned {len(results)} results"
            )

            return results

        except Exception as e:
            logger.error(f"Error performing search: {e}")
            return []

    def _format_notification(
        self, pattern: DetectedPattern, results: List[MemoryResult]
    ) -> str:
        """
        Format a notification about the suggested context.

        Args:
            pattern: Detected pattern
            results: Search results to show

        Returns:
            Formatted notification string
        """
        # Header
        notification = "💡 I found relevant context that might help:\n\n"

        # Show top results
        for i, result in enumerate(results[:3], 1):  # Show top 3
            # Format based on memory type
            if hasattr(result, "file_path") and result.file_path:
                # Code result
                location = f"{result.file_path}"
                if hasattr(result, "name") and result.name:
                    location += f":{result.name}()"
                notification += f"   {i}. `{location}`"
            else:
                # Memory result
                content_preview = result.content[:60] + (
                    "..." if len(result.content) > 60 else ""
                )
                notification += f"   {i}. {content_preview}"

            # Add similarity score
            similarity_pct = int(result.similarity * 100)
            notification += f" ({similarity_pct}% match)\n"

        # Footer with metadata
        notification += f"\n   Search: \"{pattern.search_query}\"\n"
        notification += f"   Confidence: {int(pattern.confidence * 100)}% (high)\n"

        return notification

    def record_feedback(
        self, suggestion_id: str, accepted: bool, implicit: bool = True
    ) -> bool:
        """
        Record user feedback on a suggestion.

        Args:
            suggestion_id: ID of the suggestion
            accepted: True if user found it useful
            implicit: True if inferred from behavior

        Returns:
            True if feedback was recorded
        """
        return self.feedback_tracker.record_feedback(
            suggestion_id=suggestion_id, accepted=accepted, implicit=implicit
        )

    def update_threshold(self) -> Tuple[float, str]:
        """
        Update the confidence threshold based on recent feedback.

        Returns:
            Tuple of (new_threshold, explanation)
        """
        new_threshold, explanation = (
            self.feedback_tracker.recommend_threshold_adjustment(
                current_threshold=self.high_confidence_threshold, days=7
            )
        )

        if new_threshold != self.high_confidence_threshold:
            old_threshold = self.high_confidence_threshold
            self.high_confidence_threshold = new_threshold
            logger.info(
                f"Updated confidence threshold: {old_threshold:.2f} -> {new_threshold:.2f}"
            )

        return new_threshold, explanation

    def get_stats(self) -> Dict[str, Any]:
        """
        Get suggestion engine statistics.

        Returns:
            Dictionary with statistics
        """
        feedback_stats = self.feedback_tracker.get_stats(days=30)

        return {
            **self.stats,
            "enabled": self.enabled,
            "high_confidence_threshold": self.high_confidence_threshold,
            "medium_confidence_threshold": self.medium_confidence_threshold,
            "feedback": feedback_stats,
        }

    def enable(self) -> None:
        """Enable proactive suggestions."""
        self.enabled = True
        logger.info("Enabled proactive suggestions")

    def disable(self) -> None:
        """Disable proactive suggestions."""
        self.enabled = False
        logger.info("Disabled proactive suggestions")

    def set_threshold(self, threshold: float) -> None:
        """
        Manually set the confidence threshold.

        Args:
            threshold: New threshold value (0-1)
        """
        if not 0.0 <= threshold <= 1.0:
            raise ValueError(f"Threshold must be between 0 and 1, got {threshold}")

        old_threshold = self.high_confidence_threshold
        self.high_confidence_threshold = threshold
        logger.info(
            f"Manually updated threshold: {old_threshold:.2f} -> {threshold:.2f}"
        )
