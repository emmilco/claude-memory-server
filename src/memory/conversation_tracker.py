"""Conversation tracking for context-aware retrieval."""

import asyncio
import logging
from typing import Dict, List, Optional, Set, Tuple
from datetime import datetime, UTC, timedelta
from uuid import uuid4
from dataclasses import dataclass, field

from src.config import ServerConfig

logger = logging.getLogger(__name__)


@dataclass
class QueryRecord:
    """Record of a query in a conversation."""

    query: str
    timestamp: datetime
    results_shown: List[str]  # Memory IDs returned
    query_embedding: Optional[List[float]] = None


@dataclass
class ConversationSession:
    """A conversation session with context tracking."""

    session_id: str
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_activity: datetime = field(default_factory=lambda: datetime.now(UTC))
    description: Optional[str] = None
    queries: List[QueryRecord] = field(default_factory=list)
    shown_memory_ids: Set[str] = field(default_factory=set)

    def update_activity(self) -> None:
        """Update last activity timestamp."""
        self.last_activity = datetime.now(UTC)

    def add_query(
        self,
        query: str,
        results_shown: List[str],
        query_embedding: Optional[List[float]] = None
    ) -> None:
        """Add a query to the session history."""
        record = QueryRecord(
            query=query,
            timestamp=datetime.now(UTC),
            results_shown=results_shown,
            query_embedding=query_embedding,
        )
        self.queries.append(record)
        self.shown_memory_ids.update(results_shown)
        self.update_activity()

    def is_expired(self, timeout_minutes: int) -> bool:
        """Check if session has expired."""
        timeout = timedelta(minutes=timeout_minutes)
        return datetime.now(UTC) - self.last_activity > timeout

    def get_recent_queries(self, limit: int) -> List[QueryRecord]:
        """Get the most recent N queries."""
        return self.queries[-limit:] if self.queries else []


class ConversationTracker:
    """
    Track conversation sessions for context-aware retrieval.

    Features:
    - Session management with automatic expiration
    - Query history tracking
    - Deduplication of shown context
    - Semantic query expansion support
    """

    def __init__(self, config: ServerConfig):
        """
        Initialize conversation tracker.

        Args:
            config: Server configuration
        """
        self.config = config
        self.sessions: Dict[str, ConversationSession] = {}
        self._cleanup_task: Optional[asyncio.Task] = None
        self._running = False

        # Statistics
        self.stats = {
            "sessions_created": 0,
            "sessions_expired": 0,
            "queries_tracked": 0,
            "deduplications_performed": 0,
        }

    async def start(self) -> None:
        """Start background cleanup task."""
        if self._running:
            return

        self._running = True
        self._cleanup_task = asyncio.create_task(self._periodic_cleanup())
        logger.info("Conversation tracker started")

    async def stop(self) -> None:
        """Stop background cleanup task."""
        if not self._running:
            return

        self._running = False

        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

        logger.info("Conversation tracker stopped")

    def create_session(self, description: Optional[str] = None) -> str:
        """
        Create a new conversation session.

        Args:
            description: Optional description of the conversation

        Returns:
            session_id: Unique session identifier
        """
        session_id = str(uuid4())

        session = ConversationSession(
            session_id=session_id,
            description=description,
        )

        self.sessions[session_id] = session
        self.stats["sessions_created"] += 1

        logger.info(f"Created conversation session: {session_id}")
        return session_id

    def get_session(self, session_id: str) -> Optional[ConversationSession]:
        """Get a session by ID."""
        session = self.sessions.get(session_id)

        if session:
            # Check if expired
            if session.is_expired(self.config.conversation_session_timeout_minutes):
                logger.info(f"Session {session_id} has expired")
                self.end_session(session_id)
                return None

            # Update activity
            session.update_activity()

        return session

    def end_session(self, session_id: str) -> bool:
        """
        End a conversation session.

        Args:
            session_id: Session to end

        Returns:
            True if session existed and was ended
        """
        if session_id in self.sessions:
            del self.sessions[session_id]
            logger.info(f"Ended conversation session: {session_id}")
            return True

        return False

    def track_query(
        self,
        session_id: str,
        query: str,
        results_shown: List[str],
        query_embedding: Optional[List[float]] = None
    ) -> None:
        """
        Track a query and its results in a session.

        Args:
            session_id: Session ID
            query: Query text
            results_shown: List of memory IDs that were returned
            query_embedding: Optional query embedding for semantic expansion
        """
        session = self.get_session(session_id)

        if not session:
            logger.warning(f"Session {session_id} not found for query tracking")
            return

        session.add_query(query, results_shown, query_embedding)
        self.stats["queries_tracked"] += 1

    def get_shown_memory_ids(self, session_id: str) -> Set[str]:
        """
        Get all memory IDs shown in a session.

        Args:
            session_id: Session ID

        Returns:
            Set of memory IDs
        """
        session = self.get_session(session_id)
        return session.shown_memory_ids if session else set()

    def get_recent_queries(
        self, session_id: str, limit: Optional[int] = None
    ) -> List[QueryRecord]:
        """
        Get recent queries from a session.

        Args:
            session_id: Session ID
            limit: Maximum queries to return (uses config default if None)

        Returns:
            List of query records
        """
        session = self.get_session(session_id)
        if not session:
            return []

        if limit is None:
            limit = self.config.conversation_query_history_size

        return session.get_recent_queries(limit)

    async def _periodic_cleanup(self) -> None:
        """Background task to clean up expired sessions."""
        while self._running:
            try:
                await asyncio.sleep(60)  # Check every minute
                await self._cleanup_expired_sessions()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in periodic cleanup: {e}")

    async def _cleanup_expired_sessions(self) -> None:
        """Remove expired sessions."""
        expired_sessions = [
            session_id
            for session_id, session in self.sessions.items()
            if session.is_expired(self.config.conversation_session_timeout_minutes)
        ]

        for session_id in expired_sessions:
            self.end_session(session_id)
            self.stats["sessions_expired"] += 1

        if expired_sessions:
            logger.info(f"Cleaned up {len(expired_sessions)} expired sessions")

    def get_stats(self) -> Dict:
        """Get tracker statistics."""
        return {
            **self.stats,
            "active_sessions": len(self.sessions),
        }

    def get_all_sessions(self) -> List[Dict]:
        """Get information about all active sessions."""
        return [
            {
                "session_id": session.session_id,
                "created_at": session.created_at.isoformat(),
                "last_activity": session.last_activity.isoformat(),
                "description": session.description,
                "query_count": len(session.queries),
                "unique_memories_shown": len(session.shown_memory_ids),
            }
            for session in self.sessions.values()
        ]
