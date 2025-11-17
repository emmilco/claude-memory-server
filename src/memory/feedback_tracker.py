"""Feedback tracking for adaptive learning of suggestion thresholds.

This module tracks user feedback on proactive suggestions and uses it to
adapt the confidence threshold over time.
"""

import logging
import sqlite3
from typing import Dict, Optional, List, Tuple
from datetime import datetime, UTC, timedelta
from pathlib import Path
from dataclasses import dataclass
from uuid import uuid4

from src.memory.pattern_detector import PatternType

logger = logging.getLogger(__name__)


@dataclass
class SuggestionFeedback:
    """Feedback record for a suggestion."""

    suggestion_id: str
    pattern_type: PatternType
    confidence: float
    accepted: bool  # True if user found it useful
    implicit: bool  # True if inferred from behavior vs explicit feedback
    timestamp: datetime


class FeedbackTracker:
    """
    Track user feedback on proactive suggestions.

    Features:
    - Record suggestions shown and user acceptance
    - Calculate acceptance rates per pattern type
    - Recommend threshold adjustments based on feedback
    - Persistent storage in SQLite
    """

    # Target acceptance rate (70%)
    TARGET_ACCEPTANCE_RATE = 0.70
    ACCEPTANCE_TOLERANCE = 0.10  # ±10%

    # Threshold bounds
    MIN_THRESHOLD = 0.70
    MAX_THRESHOLD = 0.95

    # Adjustment step size
    THRESHOLD_ADJUSTMENT_STEP = 0.05

    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize feedback tracker.

        Args:
            db_path: Path to SQLite database (default: ~/.claude-rag/feedback.db)
        """
        if db_path is None:
            db_path = Path.home() / ".claude-rag" / "feedback.db"

        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Initialize database
        self._init_database()

        # In-memory cache for fast access
        self._cache: Dict[str, SuggestionFeedback] = {}

        logger.info(f"Initialized FeedbackTracker with database: {self.db_path}")

    def _init_database(self) -> None:
        """Initialize the SQLite database schema."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS suggestion_feedback (
                suggestion_id TEXT PRIMARY KEY,
                pattern_type TEXT NOT NULL,
                confidence REAL NOT NULL,
                accepted INTEGER NOT NULL,  -- 0 or 1
                implicit INTEGER NOT NULL,  -- 0 or 1
                timestamp TEXT NOT NULL
            )
        """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_pattern_type
            ON suggestion_feedback(pattern_type)
        """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_timestamp
            ON suggestion_feedback(timestamp)
        """
        )

        conn.commit()
        conn.close()

        logger.debug("Database schema initialized")

    def record_suggestion(
        self,
        pattern_type: PatternType,
        confidence: float,
        suggestion_id: Optional[str] = None,
    ) -> str:
        """
        Record that a suggestion was shown to the user.

        Args:
            pattern_type: Type of pattern detected
            confidence: Confidence score of the suggestion
            suggestion_id: Optional ID (generated if None)

        Returns:
            suggestion_id for future reference
        """
        if suggestion_id is None:
            suggestion_id = str(uuid4())

        # Store in cache (feedback not yet recorded)
        self._cache[suggestion_id] = SuggestionFeedback(
            suggestion_id=suggestion_id,
            pattern_type=pattern_type,
            confidence=confidence,
            accepted=False,  # Unknown until feedback provided
            implicit=True,
            timestamp=datetime.now(UTC),
        )

        logger.debug(
            f"Recorded suggestion {suggestion_id}: "
            f"{pattern_type.value} (confidence={confidence:.2f})"
        )

        return suggestion_id

    def record_feedback(
        self, suggestion_id: str, accepted: bool, implicit: bool = True
    ) -> bool:
        """
        Record user feedback on a suggestion.

        Args:
            suggestion_id: ID of the suggestion
            accepted: True if user found it useful
            implicit: True if inferred from behavior (default)

        Returns:
            True if feedback was recorded, False if suggestion_id not found
        """
        if suggestion_id not in self._cache:
            logger.warning(f"Suggestion {suggestion_id} not found in cache")
            return False

        # Update cache
        feedback = self._cache[suggestion_id]
        feedback.accepted = accepted
        feedback.implicit = implicit

        # Persist to database
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT OR REPLACE INTO suggestion_feedback
            (suggestion_id, pattern_type, confidence, accepted, implicit, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (
                feedback.suggestion_id,
                feedback.pattern_type.value,
                feedback.confidence,
                1 if feedback.accepted else 0,
                1 if feedback.implicit else 0,
                feedback.timestamp.isoformat(),
            ),
        )

        conn.commit()
        conn.close()

        logger.info(
            f"Recorded feedback for {suggestion_id}: "
            f"{'accepted' if accepted else 'rejected'} ({'implicit' if implicit else 'explicit'})"
        )

        return True

    def get_acceptance_rate(
        self, pattern_type: Optional[PatternType] = None, days: int = 30
    ) -> float:
        """
        Calculate acceptance rate for suggestions.

        Args:
            pattern_type: Optional pattern type to filter by
            days: Number of days to look back (default: 30)

        Returns:
            Acceptance rate (0-1), or 0.0 if no data
        """
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        # Calculate cutoff date
        cutoff = datetime.now(UTC) - timedelta(days=days)

        if pattern_type:
            cursor.execute(
                """
                SELECT COUNT(*), SUM(accepted)
                FROM suggestion_feedback
                WHERE pattern_type = ? AND timestamp >= ?
            """,
                (pattern_type.value, cutoff.isoformat()),
            )
        else:
            cursor.execute(
                """
                SELECT COUNT(*), SUM(accepted)
                FROM suggestion_feedback
                WHERE timestamp >= ?
            """,
                (cutoff.isoformat(),),
            )

        result = cursor.fetchone()
        conn.close()

        total_count, accepted_count = result

        if not total_count or total_count == 0:
            return 0.0

        acceptance_rate = (accepted_count or 0) / total_count

        logger.debug(
            f"Acceptance rate ({pattern_type.value if pattern_type else 'all'}, "
            f"last {days} days): {acceptance_rate:.2%} ({accepted_count}/{total_count})"
        )

        return acceptance_rate

    def recommend_threshold_adjustment(
        self, current_threshold: float, days: int = 7
    ) -> Tuple[float, str]:
        """
        Recommend a threshold adjustment based on recent feedback.

        Args:
            current_threshold: Current threshold value
            days: Number of days to analyze (default: 7)

        Returns:
            Tuple of (recommended_threshold, explanation)
        """
        acceptance_rate = self.get_acceptance_rate(days=days)

        # Not enough data
        if acceptance_rate == 0.0:
            return current_threshold, "Insufficient data for adjustment"

        target_min = self.TARGET_ACCEPTANCE_RATE - self.ACCEPTANCE_TOLERANCE
        target_max = self.TARGET_ACCEPTANCE_RATE + self.ACCEPTANCE_TOLERANCE

        # In target range
        if target_min <= acceptance_rate <= target_max:
            return (
                current_threshold,
                f"Acceptance rate {acceptance_rate:.1%} is within target range "
                f"({target_min:.1%}-{target_max:.1%}). No adjustment needed.",
            )

        # Too many false positives (low acceptance)
        if acceptance_rate < target_min:
            new_threshold = min(
                self.MAX_THRESHOLD,
                current_threshold + self.THRESHOLD_ADJUSTMENT_STEP,
            )
            return (
                new_threshold,
                f"Acceptance rate {acceptance_rate:.1%} is below target "
                f"({self.TARGET_ACCEPTANCE_RATE:.1%}). "
                f"Increasing threshold to {new_threshold:.2f} to reduce false positives.",
            )

        # Missing opportunities (high acceptance, can be more aggressive)
        if acceptance_rate > target_max:
            new_threshold = max(
                self.MIN_THRESHOLD,
                current_threshold - self.THRESHOLD_ADJUSTMENT_STEP,
            )
            return (
                new_threshold,
                f"Acceptance rate {acceptance_rate:.1%} is above target "
                f"({self.TARGET_ACCEPTANCE_RATE:.1%}). "
                f"Decreasing threshold to {new_threshold:.2f} to show more suggestions.",
            )

        # Should never reach here
        return current_threshold, "No adjustment needed"

    def get_stats(self, days: int = 30) -> Dict:
        """
        Get feedback statistics.

        Args:
            days: Number of days to analyze

        Returns:
            Dictionary with statistics
        """
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        cutoff = datetime.now(UTC) - timedelta(days=days)

        # Overall stats
        cursor.execute(
            """
            SELECT
                COUNT(*) as total,
                SUM(accepted) as accepted,
                SUM(CASE WHEN implicit = 1 THEN 1 ELSE 0 END) as implicit
            FROM suggestion_feedback
            WHERE timestamp >= ?
        """,
            (cutoff.isoformat(),),
        )

        total, accepted, implicit = cursor.fetchone()

        # Per-pattern stats
        cursor.execute(
            """
            SELECT
                pattern_type,
                COUNT(*) as total,
                SUM(accepted) as accepted
            FROM suggestion_feedback
            WHERE timestamp >= ?
            GROUP BY pattern_type
        """,
            (cutoff.isoformat(),),
        )

        per_pattern = {}
        for pattern_type, count, acc in cursor.fetchall():
            per_pattern[pattern_type] = {
                "total": count,
                "accepted": acc or 0,
                "acceptance_rate": (acc or 0) / count if count > 0 else 0.0,
            }

        conn.close()

        return {
            "period_days": days,
            "total_suggestions": total or 0,
            "total_accepted": accepted or 0,
            "total_implicit": implicit or 0,
            "overall_acceptance_rate": (accepted or 0) / total if total else 0.0,
            "per_pattern": per_pattern,
        }

    def clear_old_data(self, days: int = 90) -> int:
        """
        Clear feedback data older than specified days.

        Args:
            days: Keep data newer than this many days

        Returns:
            Number of records deleted
        """
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        cutoff = datetime.now(UTC) - timedelta(days=days)

        cursor.execute(
            """
            DELETE FROM suggestion_feedback
            WHERE timestamp < ?
        """,
            (cutoff.isoformat(),),
        )

        deleted_count = cursor.rowcount
        conn.commit()
        conn.close()

        logger.info(f"Cleared {deleted_count} feedback records older than {days} days")

        return deleted_count
