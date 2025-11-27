"""Query Service - Query expansion, conversation tracking, and suggestions.

Extracted from MemoryRAGServer (REF-016) to provide focused query operations.

Responsibilities:
- Expand and optimize queries
- Track conversation sessions
- Generate proactive suggestions
- Collect search quality feedback
"""

import logging
from typing import Optional, Dict, Any, List

from src.config import ServerConfig
from src.core.exceptions import StorageError
from src.core.tracing import get_logger

logger = get_logger(__name__)


class QueryService:
    """
    Service for query expansion, conversation tracking, and proactive suggestions.

    This service enhances search queries through expansion, tracks conversation
    sessions for context, and provides proactive suggestions based on patterns.
    """

    def __init__(
        self,
        config: ServerConfig,
        conversation_tracker: Optional[Any] = None,
        query_expander: Optional[Any] = None,
        suggestion_engine: Optional[Any] = None,
        hybrid_searcher: Optional[Any] = None,
    ):
        """
        Initialize the Query Service.

        Args:
            config: Server configuration
            conversation_tracker: Conversation tracker for session management
            query_expander: Query expander for enhancing queries
            suggestion_engine: Suggestion engine for proactive suggestions
            hybrid_searcher: Hybrid searcher for combined search
        """
        self.config = config
        self.conversation_tracker = conversation_tracker
        self.query_expander = query_expander
        self.suggestion_engine = suggestion_engine
        self.hybrid_searcher = hybrid_searcher

        # Service statistics
        self.stats = {
            "sessions_created": 0,
            "sessions_ended": 0,
            "queries_expanded": 0,
            "suggestions_generated": 0,
            "feedback_collected": 0,
        }

    def get_stats(self) -> Dict[str, Any]:
        """Get query service statistics."""
        return self.stats.copy()

    async def start_conversation_session(
        self,
        description: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Start a new conversation session for context tracking.

        Args:
            description: Optional description of this conversation

        Returns:
            Dict with session_id and status
        """
        if not self.conversation_tracker:
            return {
                "error": "Conversation tracking is disabled",
                "status": "disabled"
            }

        try:
            session_id = self.conversation_tracker.create_session(description)
            self.stats["sessions_created"] += 1

            logger.info(f"Started conversation session: {session_id}")

            return {
                "session_id": session_id,
                "status": "created",
                "description": description,
            }

        except Exception as e:
            logger.error(f"Failed to start conversation session: {e}", exc_info=True)
            return {
                "error": str(e),
                "status": "failed"
            }

    async def end_conversation_session(
        self,
        session_id: str
    ) -> Dict[str, Any]:
        """
        End and cleanup a conversation session.

        Args:
            session_id: Session ID to end

        Returns:
            Dict with session summary
        """
        if not self.conversation_tracker:
            return {
                "error": "Conversation tracking is disabled",
                "status": "disabled"
            }

        try:
            summary = self.conversation_tracker.end_session(session_id)
            self.stats["sessions_ended"] += 1

            logger.info(f"Ended conversation session: {session_id}")

            return {
                "session_id": session_id,
                "status": "ended",
                "summary": summary,
            }

        except Exception as e:
            logger.error(f"Failed to end conversation session: {e}", exc_info=True)
            return {
                "error": str(e),
                "status": "failed"
            }

    async def list_conversation_sessions(self) -> Dict[str, Any]:
        """
        List tracked conversation sessions.

        Returns:
            Dict with sessions list
        """
        if not self.conversation_tracker:
            return {
                "error": "Conversation tracking is disabled",
                "status": "disabled"
            }

        try:
            sessions = self.conversation_tracker.list_sessions()

            return {
                "status": "success",
                "sessions": sessions,
                "total_count": len(sessions),
            }

        except Exception as e:
            logger.error(f"Failed to list conversation sessions: {e}", exc_info=True)
            return {
                "error": str(e),
                "status": "failed"
            }

    async def analyze_conversation(
        self,
        messages: List[str],
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Analyze conversation for suggestions.

        Args:
            messages: List of conversation messages
            session_id: Optional session ID

        Returns:
            Dict with analysis results and suggestions
        """
        if not self.suggestion_engine:
            return {
                "error": "Suggestion engine is disabled",
                "status": "disabled"
            }

        try:
            analysis = self.suggestion_engine.analyze(
                messages=messages,
                session_id=session_id
            )

            self.stats["suggestions_generated"] += 1

            return {
                "status": "success",
                "analysis": analysis,
                "suggestions": analysis.get("suggestions", []),
                "session_id": session_id,
            }

        except Exception as e:
            logger.error(f"Failed to analyze conversation: {e}", exc_info=True)
            return {
                "error": str(e),
                "status": "failed"
            }

    async def get_suggestion_stats(self) -> Dict[str, Any]:
        """
        Get suggestion system statistics.

        Returns:
            Dict with suggestion stats
        """
        if not self.suggestion_engine:
            return {
                "error": "Suggestion engine is disabled",
                "status": "disabled"
            }

        try:
            stats = self.suggestion_engine.get_statistics()

            return {
                "status": "success",
                "statistics": stats,
            }

        except Exception as e:
            logger.error(f"Failed to get suggestion stats: {e}", exc_info=True)
            return {
                "error": str(e),
                "status": "failed"
            }

    async def provide_suggestion_feedback(
        self,
        suggestion_id: str,
        accepted: bool,
        feedback: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Record feedback on a suggestion.

        Args:
            suggestion_id: Suggestion ID
            accepted: Whether suggestion was accepted
            feedback: Optional feedback text

        Returns:
            Dict with status
        """
        if not self.suggestion_engine:
            return {
                "error": "Suggestion engine is disabled",
                "status": "disabled"
            }

        try:
            self.suggestion_engine.record_feedback(
                suggestion_id=suggestion_id,
                accepted=accepted,
                feedback=feedback
            )

            self.stats["feedback_collected"] += 1

            return {
                "status": "success",
                "suggestion_id": suggestion_id,
                "accepted": accepted,
            }

        except Exception as e:
            logger.error(f"Failed to record suggestion feedback: {e}", exc_info=True)
            return {
                "error": str(e),
                "status": "failed"
            }

    async def set_suggestion_mode(
        self,
        mode: str,
        confidence_threshold: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Configure suggestion behavior.

        Args:
            mode: Suggestion mode (aggressive, balanced, conservative)
            confidence_threshold: Optional confidence threshold

        Returns:
            Dict with status
        """
        if not self.suggestion_engine:
            return {
                "error": "Suggestion engine is disabled",
                "status": "disabled"
            }

        try:
            if mode not in ["aggressive", "balanced", "conservative"]:
                return {
                    "error": f"Invalid mode: {mode}",
                    "status": "failed"
                }

            self.suggestion_engine.set_mode(
                mode=mode,
                confidence_threshold=confidence_threshold
            )

            return {
                "status": "success",
                "mode": mode,
                "confidence_threshold": confidence_threshold,
            }

        except Exception as e:
            logger.error(f"Failed to set suggestion mode: {e}", exc_info=True)
            return {
                "error": str(e),
                "status": "failed"
            }

    async def expand_query(
        self,
        query: str,
        context: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Expand a query using context.

        Args:
            query: Original query
            context: Optional context from recent queries

        Returns:
            Dict with original and expanded query
        """
        if not self.query_expander:
            return {
                "original_query": query,
                "expanded_query": query,
                "expansion_applied": False,
                "status": "disabled"
            }

        try:
            expanded = await self.query_expander.expand_query(query, context or [])
            expansion_applied = expanded != query

            if expansion_applied:
                self.stats["queries_expanded"] += 1

            return {
                "original_query": query,
                "expanded_query": expanded,
                "expansion_applied": expansion_applied,
                "status": "success"
            }

        except Exception as e:
            logger.error(f"Failed to expand query: {e}", exc_info=True)
            return {
                "original_query": query,
                "expanded_query": query,
                "expansion_applied": False,
                "error": str(e),
                "status": "failed"
            }
