"""Token usage analytics tracking (UX-029)."""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from pathlib import Path
import sqlite3
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


@dataclass
class TokenUsageEvent:
    """Represents a single token usage event."""

    timestamp: datetime
    event_type: str  # "search", "index", "retrieve"
    tokens_used: int  # Actual tokens consumed
    tokens_saved: int  # Tokens saved compared to manual approach
    project_name: Optional[str]
    session_id: Optional[str]
    query: Optional[str]  # For search events
    results_count: int  # Number of results returned
    relevance_avg: float  # Average relevance score


@dataclass
class TokenAnalytics:
    """Aggregated token usage analytics."""

    total_tokens_used: int
    total_tokens_saved: int
    total_searches: int
    total_files_indexed: int
    efficiency_ratio: float  # tokens_saved / (tokens_used + tokens_saved)
    cost_savings_usd: float  # Estimated cost savings
    avg_relevance: float  # Average relevance score across searches
    period_start: datetime
    period_end: datetime


class TokenTracker:
    """
    Track token usage and compute analytics.

    This class tracks all token usage from searches, retrievals, and indexing,
    and computes analytics like tokens saved, cost savings, and efficiency ratios.
    """

    # Token pricing (Claude 3.5 Sonnet rates per million tokens)
    INPUT_COST_PER_MILLION = 3.00  # $3 per million input tokens
    OUTPUT_COST_PER_MILLION = 15.00  # $15 per million output tokens

    # Estimation parameters
    AVG_TOKENS_PER_FILE = 500  # Average tokens in a code file
    AVG_TOKENS_PER_SEARCH_MANUAL = 5000  # Avg tokens user would paste manually
    AVG_TOKENS_PER_SEARCH_WITH_RAG = 1000  # Avg tokens with semantic search

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize the token tracker.

        Args:
            db_path: Path to SQLite database. Defaults to ~/.claude-rag/token_analytics.db
        """
        if db_path is None:
            home = Path.home()
            db_dir = home / ".claude-rag"
            db_dir.mkdir(parents=True, exist_ok=True)
            db_path = str(db_dir / "token_analytics.db")

        self.db_path = db_path
        self._init_database()

    def _init_database(self) -> None:
        """Initialize the SQLite database schema."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Create token_usage_events table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS token_usage_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    tokens_used INTEGER NOT NULL,
                    tokens_saved INTEGER NOT NULL,
                    project_name TEXT,
                    session_id TEXT,
                    query TEXT,
                    results_count INTEGER NOT NULL,
                    relevance_avg REAL NOT NULL
                )
            """)

            # Create index on timestamp for faster queries
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_timestamp
                ON token_usage_events(timestamp)
            """)

            # Create index on session_id
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_session_id
                ON token_usage_events(session_id)
            """)

            conn.commit()

        logger.info(f"Token analytics database initialized at {self.db_path}")

    def track_search(
        self,
        tokens_used: int,
        results_count: int,
        relevance_avg: float,
        project_name: Optional[str] = None,
        session_id: Optional[str] = None,
        query: Optional[str] = None,
    ) -> None:
        """
        Track a search operation.

        Args:
            tokens_used: Actual tokens consumed in the search
            results_count: Number of results returned
            relevance_avg: Average relevance score of results
            project_name: Project name (if applicable)
            session_id: Session ID for grouping
            query: Search query (optional, for debugging)
        """
        # Estimate tokens saved: assume user would have pasted 5000 tokens manually
        tokens_saved = self.AVG_TOKENS_PER_SEARCH_MANUAL - tokens_used

        event = TokenUsageEvent(
            timestamp=datetime.now(),
            event_type="search",
            tokens_used=tokens_used,
            tokens_saved=max(tokens_saved, 0),  # Can't save negative tokens
            project_name=project_name,
            session_id=session_id,
            query=query,
            results_count=results_count,
            relevance_avg=relevance_avg,
        )

        self._store_event(event)

    def track_index(
        self,
        files_indexed: int,
        project_name: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> None:
        """
        Track an indexing operation.

        Args:
            files_indexed: Number of files indexed
            project_name: Project name
            session_id: Session ID for grouping
        """
        # Indexing costs tokens but saves future manual searches
        tokens_used = files_indexed * 50  # Rough estimate for embedding generation
        tokens_saved = files_indexed * self.AVG_TOKENS_PER_FILE  # Future savings

        event = TokenUsageEvent(
            timestamp=datetime.now(),
            event_type="index",
            tokens_used=tokens_used,
            tokens_saved=tokens_saved,
            project_name=project_name,
            session_id=session_id,
            query=None,
            results_count=files_indexed,
            relevance_avg=1.0,  # N/A for indexing
        )

        self._store_event(event)

    def _store_event(self, event: TokenUsageEvent) -> None:
        """Store a token usage event in the database."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO token_usage_events
                (timestamp, event_type, tokens_used, tokens_saved, project_name,
                 session_id, query, results_count, relevance_avg)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    event.timestamp.isoformat(),
                    event.event_type,
                    event.tokens_used,
                    event.tokens_saved,
                    event.project_name,
                    event.session_id,
                    event.query,
                    event.results_count,
                    event.relevance_avg,
                ),
            )
            conn.commit()

        logger.debug(
            f"Tracked {event.event_type} event: {event.tokens_used} used, "
            f"{event.tokens_saved} saved"
        )

    def get_analytics(
        self,
        period_days: int = 30,
        session_id: Optional[str] = None,
        project_name: Optional[str] = None,
    ) -> TokenAnalytics:
        """
        Get aggregated token analytics for a time period.

        Args:
            period_days: Number of days to analyze (default 30)
            session_id: Filter by session ID (optional)
            project_name: Filter by project name (optional)

        Returns:
            TokenAnalytics object with aggregated data
        """
        period_start = datetime.now() - timedelta(days=period_days)
        period_end = datetime.now()

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Build query with optional filters
            query = """
                SELECT
                    SUM(tokens_used) as total_used,
                    SUM(tokens_saved) as total_saved,
                    COUNT(CASE WHEN event_type = 'search' THEN 1 END) as searches,
                    SUM(CASE WHEN event_type = 'index' THEN results_count ELSE 0 END) as files_indexed,
                    AVG(CASE WHEN event_type = 'search' THEN relevance_avg END) as avg_relevance
                FROM token_usage_events
                WHERE timestamp >= ?
            """

            params = [period_start.isoformat()]

            if session_id:
                query += " AND session_id = ?"
                params.append(session_id)

            if project_name:
                query += " AND project_name = ?"
                params.append(project_name)

            cursor.execute(query, params)
            row = cursor.fetchone()

        total_used = row[0] or 0
        total_saved = row[1] or 0
        searches = row[2] or 0
        files_indexed = row[3] or 0
        avg_relevance = row[4] or 0.0

        # Calculate efficiency ratio
        total_tokens = total_used + total_saved
        efficiency_ratio = total_saved / total_tokens if total_tokens > 0 else 0.0

        # Calculate cost savings (assuming input tokens)
        cost_savings_usd = (total_saved / 1_000_000) * self.INPUT_COST_PER_MILLION

        return TokenAnalytics(
            total_tokens_used=total_used,
            total_tokens_saved=total_saved,
            total_searches=searches,
            total_files_indexed=files_indexed,
            efficiency_ratio=efficiency_ratio,
            cost_savings_usd=cost_savings_usd,
            avg_relevance=avg_relevance,
            period_start=period_start,
            period_end=period_end,
        )

    def get_session_summary(self, session_id: str) -> Dict[str, Any]:
        """
        Get analytics for a specific session.

        Args:
            session_id: Session ID to analyze

        Returns:
            Dictionary with session analytics
        """
        analytics = self.get_analytics(period_days=365, session_id=session_id)

        return {
            "session_id": session_id,
            "searches": analytics.total_searches,
            "files_indexed": analytics.total_files_indexed,
            "tokens_used": analytics.total_tokens_used,
            "tokens_saved": analytics.total_tokens_saved,
            "cost_savings_usd": round(analytics.cost_savings_usd, 2),
            "efficiency_ratio": round(analytics.efficiency_ratio * 100, 1),
            "avg_relevance": round(analytics.avg_relevance, 2),
        }

    def get_top_sessions(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get top sessions by tokens saved.

        Args:
            limit: Maximum number of sessions to return

        Returns:
            List of session summaries, sorted by tokens saved (descending)
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT
                    session_id,
                    SUM(tokens_saved) as total_saved,
                    COUNT(*) as event_count
                FROM token_usage_events
                WHERE session_id IS NOT NULL
                GROUP BY session_id
                ORDER BY total_saved DESC
                LIMIT ?
            """,
                (limit,),
            )

            results = []
            for row in cursor.fetchall():
                session_id, total_saved, event_count = row
                results.append(
                    {
                        "session_id": session_id,
                        "tokens_saved": total_saved,
                        "events": event_count,
                    }
                )

            return results
