"""Tests for feedback tracker."""

import pytest
import tempfile
from pathlib import Path

from src.memory.feedback_tracker import FeedbackTracker
from src.memory.pattern_detector import PatternType


class TestFeedbackTracker:
    """Test suite for FeedbackTracker."""

    @pytest.fixture
    def tracker(self):
        """Create a feedback tracker with temporary database."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "feedback_test.db"
            tracker = FeedbackTracker(db_path=db_path)
            yield tracker

    # Basic Recording Tests

    def test_record_suggestion(self, tracker):
        """Test recording a suggestion."""
        suggestion_id = tracker.record_suggestion(
            pattern_type=PatternType.IMPLEMENTATION_REQUEST,
            confidence=0.92,
        )

        assert suggestion_id is not None
        assert len(suggestion_id) > 0
        # Should be in cache
        assert suggestion_id in tracker._cache

    def test_record_suggestion_custom_id(self, tracker):
        """Test recording a suggestion with custom ID."""
        custom_id = "test-123"
        suggestion_id = tracker.record_suggestion(
            pattern_type=PatternType.CODE_QUESTION,
            confidence=0.85,
            suggestion_id=custom_id,
        )

        assert suggestion_id == custom_id
        assert custom_id in tracker._cache

    def test_record_feedback_accepted(self, tracker):
        """Test recording positive feedback."""
        suggestion_id = tracker.record_suggestion(
            pattern_type=PatternType.ERROR_DEBUGGING,
            confidence=0.95,
        )

        success = tracker.record_feedback(suggestion_id, accepted=True)
        assert success is True

        # Verify it's in database
        feedback = tracker._cache[suggestion_id]
        assert feedback.accepted is True

    def test_record_feedback_rejected(self, tracker):
        """Test recording negative feedback."""
        suggestion_id = tracker.record_suggestion(
            pattern_type=PatternType.REFACTORING_CHANGE,
            confidence=0.88,
        )

        success = tracker.record_feedback(suggestion_id, accepted=False)
        assert success is True

        feedback = tracker._cache[suggestion_id]
        assert feedback.accepted is False

    def test_record_feedback_explicit(self, tracker):
        """Test recording explicit (non-implicit) feedback."""
        suggestion_id = tracker.record_suggestion(
            pattern_type=PatternType.IMPLEMENTATION_REQUEST,
            confidence=0.91,
        )

        success = tracker.record_feedback(suggestion_id, accepted=True, implicit=False)
        assert success is True

        feedback = tracker._cache[suggestion_id]
        assert feedback.implicit is False

    def test_record_feedback_unknown_id(self, tracker):
        """Test recording feedback for unknown suggestion."""
        success = tracker.record_feedback("unknown-id", accepted=True)
        assert success is False

    # Acceptance Rate Tests

    def test_get_acceptance_rate_no_data(self, tracker):
        """Test acceptance rate with no data."""
        rate = tracker.get_acceptance_rate()
        assert rate == 0.0

    def test_get_acceptance_rate_all_accepted(self, tracker):
        """Test acceptance rate when all suggestions accepted."""
        for i in range(5):
            sid = tracker.record_suggestion(
                pattern_type=PatternType.IMPLEMENTATION_REQUEST,
                confidence=0.90,
            )
            tracker.record_feedback(sid, accepted=True)

        rate = tracker.get_acceptance_rate()
        assert rate == 1.0

    def test_get_acceptance_rate_all_rejected(self, tracker):
        """Test acceptance rate when all suggestions rejected."""
        for i in range(5):
            sid = tracker.record_suggestion(
                pattern_type=PatternType.CODE_QUESTION,
                confidence=0.85,
            )
            tracker.record_feedback(sid, accepted=False)

        rate = tracker.get_acceptance_rate()
        assert rate == 0.0

    def test_get_acceptance_rate_mixed(self, tracker):
        """Test acceptance rate with mixed feedback."""
        # 3 accepted, 2 rejected = 60%
        for i in range(3):
            sid = tracker.record_suggestion(
                pattern_type=PatternType.ERROR_DEBUGGING,
                confidence=0.92,
            )
            tracker.record_feedback(sid, accepted=True)

        for i in range(2):
            sid = tracker.record_suggestion(
                pattern_type=PatternType.REFACTORING_CHANGE,
                confidence=0.87,
            )
            tracker.record_feedback(sid, accepted=False)

        rate = tracker.get_acceptance_rate()
        assert rate == 0.6

    def test_get_acceptance_rate_by_pattern_type(self, tracker):
        """Test acceptance rate filtered by pattern type."""
        # Add implementation requests (all accepted)
        for i in range(3):
            sid = tracker.record_suggestion(
                pattern_type=PatternType.IMPLEMENTATION_REQUEST,
                confidence=0.90,
            )
            tracker.record_feedback(sid, accepted=True)

        # Add code questions (all rejected)
        for i in range(2):
            sid = tracker.record_suggestion(
                pattern_type=PatternType.CODE_QUESTION,
                confidence=0.80,
            )
            tracker.record_feedback(sid, accepted=False)

        # Overall rate should be 3/5 = 0.6
        overall_rate = tracker.get_acceptance_rate()
        assert overall_rate == 0.6

        # Implementation request rate should be 100%
        impl_rate = tracker.get_acceptance_rate(
            pattern_type=PatternType.IMPLEMENTATION_REQUEST
        )
        assert impl_rate == 1.0

        # Code question rate should be 0%
        question_rate = tracker.get_acceptance_rate(
            pattern_type=PatternType.CODE_QUESTION
        )
        assert question_rate == 0.0

    # Threshold Adjustment Tests

    def test_recommend_threshold_no_data(self, tracker):
        """Test threshold recommendation with no data."""
        new_threshold, explanation = tracker.recommend_threshold_adjustment(0.90)

        assert new_threshold == 0.90
        assert "Insufficient data" in explanation

    def test_recommend_threshold_in_target_range(self, tracker):
        """Test threshold recommendation when in target range."""
        # Add feedback with 70% acceptance (in target range)
        for i in range(7):
            sid = tracker.record_suggestion(
                pattern_type=PatternType.IMPLEMENTATION_REQUEST,
                confidence=0.90,
            )
            tracker.record_feedback(sid, accepted=True)

        for i in range(3):
            sid = tracker.record_suggestion(
                pattern_type=PatternType.CODE_QUESTION,
                confidence=0.85,
            )
            tracker.record_feedback(sid, accepted=False)

        new_threshold, explanation = tracker.recommend_threshold_adjustment(0.90)

        assert new_threshold == 0.90
        assert "within target range" in explanation

    def test_recommend_threshold_increase(self, tracker):
        """Test threshold increase when acceptance too low."""
        # Add feedback with 40% acceptance (below target)
        for i in range(4):
            sid = tracker.record_suggestion(
                pattern_type=PatternType.IMPLEMENTATION_REQUEST,
                confidence=0.90,
            )
            tracker.record_feedback(sid, accepted=True)

        for i in range(6):
            sid = tracker.record_suggestion(
                pattern_type=PatternType.CODE_QUESTION,
                confidence=0.85,
            )
            tracker.record_feedback(sid, accepted=False)

        current_threshold = 0.90
        new_threshold, explanation = tracker.recommend_threshold_adjustment(
            current_threshold
        )

        assert new_threshold > current_threshold
        assert new_threshold == 0.95
        assert "Increasing threshold" in explanation

    def test_recommend_threshold_decrease(self, tracker):
        """Test threshold decrease when acceptance too high."""
        # Add feedback with 90% acceptance (above target)
        for i in range(9):
            sid = tracker.record_suggestion(
                pattern_type=PatternType.IMPLEMENTATION_REQUEST,
                confidence=0.90,
            )
            tracker.record_feedback(sid, accepted=True)

        for i in range(1):
            sid = tracker.record_suggestion(
                pattern_type=PatternType.CODE_QUESTION,
                confidence=0.85,
            )
            tracker.record_feedback(sid, accepted=False)

        current_threshold = 0.90
        new_threshold, explanation = tracker.recommend_threshold_adjustment(
            current_threshold
        )

        assert new_threshold < current_threshold
        assert new_threshold == 0.85
        assert "Decreasing threshold" in explanation

    def test_recommend_threshold_respects_bounds(self, tracker):
        """Test that threshold stays within min/max bounds."""
        # Test max bound
        new_threshold, _ = tracker.recommend_threshold_adjustment(0.95)
        assert new_threshold <= tracker.MAX_THRESHOLD

        # Test min bound
        new_threshold, _ = tracker.recommend_threshold_adjustment(0.70)
        assert new_threshold >= tracker.MIN_THRESHOLD

    # Statistics Tests

    def test_get_stats_no_data(self, tracker):
        """Test statistics with no data."""
        stats = tracker.get_stats()

        assert stats["total_suggestions"] == 0
        assert stats["total_accepted"] == 0
        assert stats["overall_acceptance_rate"] == 0.0
        assert len(stats["per_pattern"]) == 0

    def test_get_stats_with_data(self, tracker):
        """Test statistics with feedback data."""
        # Add some feedback
        for i in range(3):
            sid = tracker.record_suggestion(
                pattern_type=PatternType.IMPLEMENTATION_REQUEST,
                confidence=0.90,
            )
            tracker.record_feedback(sid, accepted=True, implicit=False)

        for i in range(2):
            sid = tracker.record_suggestion(
                pattern_type=PatternType.CODE_QUESTION,
                confidence=0.85,
            )
            tracker.record_feedback(sid, accepted=False, implicit=True)

        stats = tracker.get_stats()

        assert stats["total_suggestions"] == 5
        assert stats["total_accepted"] == 3
        assert stats["overall_acceptance_rate"] == 0.6
        assert stats["total_implicit"] == 2

        # Check per-pattern stats
        assert "implementation_request" in stats["per_pattern"]
        assert stats["per_pattern"]["implementation_request"]["total"] == 3
        assert stats["per_pattern"]["implementation_request"]["accepted"] == 3
        assert stats["per_pattern"]["implementation_request"]["acceptance_rate"] == 1.0

    def test_get_stats_custom_period(self, tracker):
        """Test statistics with custom time period."""
        # Add feedback
        for i in range(5):
            sid = tracker.record_suggestion(
                pattern_type=PatternType.ERROR_DEBUGGING,
                confidence=0.92,
            )
            tracker.record_feedback(sid, accepted=True)

        # Stats for last 7 days
        stats_7d = tracker.get_stats(days=7)
        assert stats_7d["period_days"] == 7
        assert stats_7d["total_suggestions"] == 5

        # Stats for last 30 days (should include all)
        stats_30d = tracker.get_stats(days=30)
        assert stats_30d["period_days"] == 30
        assert stats_30d["total_suggestions"] == 5

    # Data Management Tests

    def test_clear_old_data(self, tracker):
        """Test clearing old feedback data."""
        # Add some feedback
        for i in range(5):
            sid = tracker.record_suggestion(
                pattern_type=PatternType.IMPLEMENTATION_REQUEST,
                confidence=0.90,
            )
            tracker.record_feedback(sid, accepted=True)

        # Clear data older than 90 days (should clear nothing since data is fresh)
        deleted = tracker.clear_old_data(days=90)
        assert deleted == 0

        # Verify data still there
        stats = tracker.get_stats(days=30)
        assert stats["total_suggestions"] == 5

    def test_database_persistence(self):
        """Test that data persists across tracker instances."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "persist_test.db"

            # Create first tracker and add data
            tracker1 = FeedbackTracker(db_path=db_path)
            sid = tracker1.record_suggestion(
                pattern_type=PatternType.IMPLEMENTATION_REQUEST,
                confidence=0.92,
            )
            tracker1.record_feedback(sid, accepted=True)

            # Create second tracker with same database
            tracker2 = FeedbackTracker(db_path=db_path)

            # Data should persist
            stats = tracker2.get_stats()
            assert stats["total_suggestions"] == 1
            assert stats["total_accepted"] == 1

    def test_concurrent_pattern_types(self, tracker):
        """Test tracking multiple pattern types simultaneously."""
        # Record all pattern types
        for pattern_type in PatternType:
            for i in range(2):
                sid = tracker.record_suggestion(
                    pattern_type=pattern_type, confidence=0.85 + i * 0.05
                )
                tracker.record_feedback(sid, accepted=(i % 2 == 0))

        stats = tracker.get_stats()

        # Should have data for all pattern types
        assert len(stats["per_pattern"]) == len(PatternType)

        # Each pattern should have 2 suggestions, 1 accepted
        for pattern_type in PatternType:
            pattern_stats = stats["per_pattern"][pattern_type.value]
            assert pattern_stats["total"] == 2
            assert pattern_stats["accepted"] == 1
            assert pattern_stats["acceptance_rate"] == 0.5
