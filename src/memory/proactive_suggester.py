"""Proactive memory suggestion system."""

import logging
from typing import List, Optional, Dict, Any, Set
from datetime import datetime, UTC, timedelta

from src.core.models import (
    Suggestion,
    SuggestionResponse,
    DetectedIntentInfo,
    RelevanceFactors,
    MemoryResult,
    QueryRequest,
    SearchFilters,
    ProvenanceSource,
)
from src.memory.intent_detector import IntentDetector, DetectedIntent
from src.memory.conversation_tracker import ConversationTracker, QueryRecord
from src.store import MemoryStore
from src.embeddings.generator import EmbeddingGenerator

logger = logging.getLogger(__name__)


class ProactiveSuggester:
    """
    Proactive suggestion system for memories and code.

    Analyzes conversation context to suggest relevant memories and code
    without requiring explicit queries.

    Features:
    - Intent detection from conversation
    - Dual search (memories + code)
    - Confidence-based ranking
    - Deduplication of shown results
    - Configurable thresholds
    """

    def __init__(
        self,
        store: MemoryStore,
        embedding_generator: EmbeddingGenerator,
        conversation_tracker: ConversationTracker,
        intent_detector: Optional[IntentDetector] = None,
        confidence_threshold: float = 0.85,
        max_suggestions: int = 5,
        context_window: int = 5,
    ):
        """
        Initialize proactive suggester.

        Args:
            store: Memory store for searching
            embedding_generator: Embedding generator
            conversation_tracker: Conversation tracker for context
            intent_detector: Intent detector (creates default if None)
            confidence_threshold: Minimum confidence for suggestions (0-1)
            max_suggestions: Maximum suggestions to return
            context_window: Number of recent queries to analyze
        """
        self.store = store
        self.embedding_generator = embedding_generator
        self.conversation_tracker = conversation_tracker
        self.intent_detector = intent_detector or IntentDetector(context_window=context_window)
        self.confidence_threshold = confidence_threshold
        self.max_suggestions = max_suggestions

        # Statistics
        self.stats = {
            "suggestions_generated": 0,
            "total_candidates": 0,
            "deduplications": 0,
            "intent_detections": 0,
        }

    async def suggest_memories(
        self,
        session_id: str,
        max_suggestions: Optional[int] = None,
        confidence_threshold: Optional[float] = None,
        include_code: bool = True,
        project_name: Optional[str] = None,
    ) -> SuggestionResponse:
        """
        Generate proactive suggestions based on conversation context.

        Args:
            session_id: Conversation session ID
            max_suggestions: Max suggestions to return (uses default if None)
            confidence_threshold: Min confidence (uses default if None)
            include_code: Include code search results
            project_name: Project context for filtering

        Returns:
            SuggestionResponse with suggestions and metadata
        """
        # Use defaults if not specified
        max_suggestions = max_suggestions or self.max_suggestions
        confidence_threshold = confidence_threshold or self.confidence_threshold

        # Get conversation context
        session = self.conversation_tracker.get_session(session_id)
        if not session:
            logger.warning(f"Session {session_id} not found")
            return self._empty_response(session_id, confidence_threshold)

        # Get recent queries
        recent_queries = self.conversation_tracker.get_recent_queries(session_id)
        if not recent_queries:
            logger.debug(f"No recent queries in session {session_id}")
            return self._empty_response(session_id, confidence_threshold)

        # Extract query text
        query_texts = [q.query for q in recent_queries]

        # Detect intent
        detected_intent = self.intent_detector.detect_intent(query_texts)
        self.stats["intent_detections"] += 1

        logger.debug(
            f"Detected intent: {detected_intent.intent_type} "
            f"(confidence: {detected_intent.confidence:.2f})"
        )

        # Search for candidates
        candidates = await self._search_candidates(
            detected_intent,
            include_code=include_code,
            project_name=project_name,
        )

        self.stats["total_candidates"] += len(candidates)

        # Get already-shown memory IDs for deduplication
        shown_ids = self.conversation_tracker.get_shown_memory_ids(session_id)

        # Score and filter candidates
        suggestions = await self._score_and_filter(
            candidates,
            detected_intent,
            shown_ids,
            confidence_threshold,
            max_suggestions,
        )

        self.stats["suggestions_generated"] += len(suggestions)

        # Build response
        response = SuggestionResponse(
            suggestions=suggestions,
            detected_intent=DetectedIntentInfo(
                intent_type=detected_intent.intent_type,
                keywords=detected_intent.keywords,
                confidence=detected_intent.confidence,
                search_query=detected_intent.search_query,
            ),
            confidence_threshold=confidence_threshold,
            total_suggestions=len(suggestions),
            session_id=session_id,
        )

        logger.info(
            f"Generated {len(suggestions)} suggestions "
            f"(threshold: {confidence_threshold:.2f})"
        )

        return response

    async def _search_candidates(
        self,
        detected_intent: DetectedIntent,
        include_code: bool,
        project_name: Optional[str],
    ) -> List[MemoryResult]:
        """
        Search for candidate memories and code.

        Args:
            detected_intent: Detected intent with search query
            include_code: Include code search results
            project_name: Project context for filtering

        Returns:
            List of candidate memory results
        """
        if not detected_intent.search_query:
            return []

        # Build search filters
        filters = SearchFilters(
            project_name=project_name,
        ) if project_name else None

        # Generate query embedding
        query_embedding = await self.embedding_generator.generate_embedding(
            detected_intent.search_query
        )

        # Search memories
        try:
            results = await self.store.search(
                embedding=query_embedding,
                limit=20,  # Get more candidates for filtering
                threshold=0.5,  # Lower threshold, will filter by confidence later
                filters=filters,
            )

            logger.debug(f"Found {len(results)} candidate results")
            return results

        except Exception as e:
            logger.error(f"Error searching candidates: {e}")
            return []

    async def _score_and_filter(
        self,
        candidates: List[MemoryResult],
        detected_intent: DetectedIntent,
        shown_ids: Set[str],
        confidence_threshold: float,
        max_suggestions: int,
    ) -> List[Suggestion]:
        """
        Score candidates and filter by confidence.

        Args:
            candidates: Candidate memory results
            detected_intent: Detected intent for context matching
            shown_ids: Already-shown memory IDs to deduplicate
            confidence_threshold: Minimum confidence
            max_suggestions: Maximum suggestions to return

        Returns:
            List of suggestions ordered by confidence
        """
        suggestions: List[Suggestion] = []

        for candidate in candidates:
            # Skip if already shown
            if candidate.memory.id in shown_ids:
                self.stats["deduplications"] += 1
                continue

            # Calculate confidence score
            confidence, factors = self._calculate_confidence(
                candidate,
                detected_intent,
            )

            # Filter by threshold
            if confidence < confidence_threshold:
                continue

            # Generate reason
            reason = self._generate_reason(
                candidate,
                detected_intent,
                factors,
            )

            # Determine source type
            source_type = self._determine_source_type(candidate)

            # Build suggestion
            suggestion = Suggestion(
                memory_id=candidate.memory.id,
                content=candidate.memory.content,
                confidence=confidence,
                reason=reason,
                source_type=source_type,
                relevance_factors=factors,
                metadata=candidate.memory.metadata or {},
            )

            suggestions.append(suggestion)

        # Sort by confidence (highest first)
        suggestions.sort(key=lambda s: s.confidence, reverse=True)

        # Limit results
        return suggestions[:max_suggestions]

    def _calculate_confidence(
        self,
        candidate: MemoryResult,
        detected_intent: DetectedIntent,
    ) -> tuple[float, RelevanceFactors]:
        """
        Calculate overall confidence score for a candidate.

        Args:
            candidate: Candidate memory result
            detected_intent: Detected intent

        Returns:
            (confidence, relevance_factors) tuple
        """
        # Semantic similarity (from search score, already 0-1)
        semantic_similarity = min(candidate.score, 1.0)

        # Recency score (newer is better)
        recency = self._calculate_recency_score(candidate.memory.last_accessed)

        # Importance score (from memory importance)
        importance = candidate.memory.importance

        # Context match score (keyword overlap)
        context_match = self._calculate_context_match(
            candidate.memory.content,
            detected_intent.keywords,
        )

        # Weighted combination
        confidence = (
            semantic_similarity * 0.5 +
            recency * 0.2 +
            importance * 0.2 +
            context_match * 0.1
        )

        factors = RelevanceFactors(
            semantic_similarity=semantic_similarity,
            recency=recency,
            importance=importance,
            context_match=context_match,
        )

        return confidence, factors

    def _calculate_recency_score(self, last_accessed: datetime) -> float:
        """
        Calculate recency score (0-1, higher is more recent).

        Args:
            last_accessed: Last access timestamp

        Returns:
            Recency score (0-1)
        """
        now = datetime.now(UTC)
        age = now - last_accessed

        # Score decays over 180 days
        days_old = age.total_seconds() / 86400
        if days_old <= 7:
            return 1.0  # Very recent
        elif days_old <= 30:
            return 0.8  # Recent
        elif days_old <= 90:
            return 0.5  # Moderate
        elif days_old <= 180:
            return 0.3  # Old
        else:
            return 0.1  # Very old

    def _calculate_context_match(
        self,
        content: str,
        keywords: List[str],
    ) -> float:
        """
        Calculate context match score based on keyword overlap.

        Args:
            content: Memory content
            keywords: Detected keywords

        Returns:
            Context match score (0-1)
        """
        if not keywords:
            return 0.5  # Neutral if no keywords

        content_lower = content.lower()
        matches = sum(1 for keyword in keywords if keyword.lower() in content_lower)

        # Score based on proportion of keywords matched
        return min(matches / len(keywords), 1.0)

    def _generate_reason(
        self,
        candidate: MemoryResult,
        detected_intent: DetectedIntent,
        factors: RelevanceFactors,
    ) -> str:
        """
        Generate human-readable reason for suggestion.

        Args:
            candidate: Candidate memory
            detected_intent: Detected intent
            factors: Relevance factors

        Returns:
            Reason string
        """
        # Determine primary reason based on highest factor
        if factors.semantic_similarity >= 0.8:
            base_reason = "Highly relevant to your query"
        elif factors.importance >= 0.8:
            base_reason = "Important reference"
        elif factors.recency >= 0.8:
            base_reason = "Recently accessed"
        else:
            base_reason = "Related to your conversation"

        # Add intent-specific context
        if detected_intent.intent_type == "implementation":
            base_reason = f"Similar implementation pattern - {base_reason.lower()}"
        elif detected_intent.intent_type == "debugging":
            base_reason = f"May help debug your issue - {base_reason.lower()}"
        elif detected_intent.intent_type == "learning":
            base_reason = f"Example that may help - {base_reason.lower()}"
        elif detected_intent.intent_type == "exploration":
            base_reason = f"Related content - {base_reason.lower()}"

        # Add keyword match context
        if factors.context_match >= 0.5 and detected_intent.keywords:
            top_keywords = detected_intent.keywords[:3]
            base_reason += f" (matches: {', '.join(top_keywords)})"

        return base_reason

    def _determine_source_type(self, candidate: MemoryResult) -> str:
        """
        Determine if candidate is from memory or code.

        Args:
            candidate: Candidate memory result

        Returns:
            "memory" or "code"
        """
        # Check metadata for code indicators
        metadata = candidate.memory.metadata or {}

        if metadata.get("file_path") or metadata.get("source_file"):
            return "code"

        # Check provenance
        provenance = candidate.memory.provenance
        if provenance and provenance.source == ProvenanceSource.CODE_INDEXED:
            return "code"

        return "memory"

    def _empty_response(
        self,
        session_id: str,
        confidence_threshold: float,
    ) -> SuggestionResponse:
        """
        Create empty response for cases with no context.

        Args:
            session_id: Session ID
            confidence_threshold: Confidence threshold

        Returns:
            Empty SuggestionResponse
        """
        return SuggestionResponse(
            suggestions=[],
            detected_intent=DetectedIntentInfo(
                intent_type="general",
                keywords=[],
                confidence=0.0,
                search_query="",
            ),
            confidence_threshold=confidence_threshold,
            total_suggestions=0,
            session_id=session_id,
        )

    def get_stats(self) -> Dict[str, Any]:
        """Get suggester statistics."""
        return dict(self.stats)
