"""Tests for token usage analytics (UX-029)."""

import pytest
import tempfile
import os
from datetime import datetime, timedelta
from src.analytics.token_tracker import TokenTracker, TokenUsageEvent, TokenAnalytics


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    try:
        os.unlink(path)
    except FileNotFoundError:
        pass


class TestTokenTracker:
    """Test TokenTracker class."""

    def test_init_creates_database(self, temp_db):
        """Test that initialization creates the database schema."""
        TokenTracker(db_path=temp_db)
        assert os.path.exists(temp_db)

    def test_track_search(self, temp_db):
        """Test tracking a search event."""
        tracker = TokenTracker(db_path=temp_db)
        tracker.track_search(
            tokens_used=1000,
            results_count=5,
            relevance_avg=0.85,
            project_name="test-project",
            session_id="session-1",
            query="test query",
        )

        analytics = tracker.get_analytics(period_days=1)
        assert analytics.total_searches == 1
        assert analytics.total_tokens_used == 1000
        assert analytics.total_tokens_saved == 4000  # 5000 - 1000

    def test_track_index(self, temp_db):
        """Test tracking an indexing event."""
        tracker = TokenTracker(db_path=temp_db)
        tracker.track_index(
            files_indexed=10,
            project_name="test-project",
            session_id="session-1",
        )

        analytics = tracker.get_analytics(period_days=1)
        assert analytics.total_files_indexed == 10
        assert analytics.total_tokens_saved == 10 * 500  # AVG_TOKENS_PER_FILE

    def test_get_analytics_period(self, temp_db):
        """Test getting analytics for a specific period."""
        tracker = TokenTracker(db_path=temp_db)

        # Add recent event
        tracker.track_search(
            tokens_used=500,
            results_count=3,
            relevance_avg=0.9,
        )

        # Recent period should include it
        analytics_recent = tracker.get_analytics(period_days=1)
        assert analytics_recent.total_searches == 1

        # Old period should not include it
        analytics_old = tracker.get_analytics(period_days=0)
        assert analytics_old.total_searches == 0

    def test_efficiency_ratio(self, temp_db):
        """Test efficiency ratio calculation."""
        tracker = TokenTracker(db_path=temp_db)

        tracker.track_search(
            tokens_used=1000,  # Used 1000
            results_count=5,
            relevance_avg=0.8,
        )
        # Saved: 5000 - 1000 = 4000
        # Efficiency: 4000 / (1000 + 4000) = 0.8

        analytics = tracker.get_analytics(period_days=1)
        assert abs(analytics.efficiency_ratio - 0.8) < 0.01

    def test_cost_savings_calculation(self, temp_db):
        """Test cost savings calculation."""
        tracker = TokenTracker(db_path=temp_db)

        # Track 1M tokens saved
        tracker.track_search(
            tokens_used=0,
            results_count=200,
            relevance_avg=0.85,
        )
        # This saves ~200 * 5000 = 1,000,000 tokens

        analytics = tracker.get_analytics(period_days=1)
        # At $3 per million input tokens
        expected_savings = (analytics.total_tokens_saved / 1_000_000) * 3.00
        assert abs(analytics.cost_savings_usd - expected_savings) < 0.01

    def test_get_session_summary(self, temp_db):
        """Test getting summary for a specific session."""
        tracker = TokenTracker(db_path=temp_db)

        tracker.track_search(
            tokens_used=500,
            results_count=3,
            relevance_avg=0.9,
            session_id="session-123",
        )
        tracker.track_index(
            files_indexed=5,
            session_id="session-123",
        )

        summary = tracker.get_session_summary("session-123")
        assert summary["session_id"] == "session-123"
        assert summary["searches"] == 1
        assert summary["files_indexed"] == 5

    def test_get_top_sessions(self, temp_db):
        """Test getting top sessions by tokens saved."""
        tracker = TokenTracker(db_path=temp_db)

        # Create multiple sessions with different savings
        for i in range(5):
            tracker.track_search(
                tokens_used=100,
                results_count=i + 1,
                relevance_avg=0.8,
                session_id=f"session-{i}",
            )

        top_sessions = tracker.get_top_sessions(limit=3)
        assert len(top_sessions) == 3
        # Sessions should be ordered by tokens saved (descending)
        assert top_sessions[0]["tokens_saved"] >= top_sessions[1]["tokens_saved"]
        assert top_sessions[1]["tokens_saved"] >= top_sessions[2]["tokens_saved"]

    def test_filter_by_project(self, temp_db):
        """Test filtering analytics by project."""
        tracker = TokenTracker(db_path=temp_db)

        tracker.track_search(
            tokens_used=100,
            results_count=1,
            relevance_avg=0.8,
            project_name="project-a",
        )
        tracker.track_search(
            tokens_used=200,
            results_count=2,
            relevance_avg=0.9,
            project_name="project-b",
        )

        analytics_a = tracker.get_analytics(period_days=1, project_name="project-a")
        assert analytics_a.total_searches == 1
        assert analytics_a.total_tokens_used == 100

        analytics_b = tracker.get_analytics(period_days=1, project_name="project-b")
        assert analytics_b.total_searches == 1
        assert analytics_b.total_tokens_used == 200

    def test_average_relevance(self, temp_db):
        """Test average relevance calculation."""
        tracker = TokenTracker(db_path=temp_db)

        tracker.track_search(tokens_used=100, results_count=1, relevance_avg=0.8)
        tracker.track_search(tokens_used=100, results_count=1, relevance_avg=0.9)
        tracker.track_search(tokens_used=100, results_count=1, relevance_avg=1.0)

        analytics = tracker.get_analytics(period_days=1)
        # Average of 0.8, 0.9, 1.0 = 0.9
        assert abs(analytics.avg_relevance - 0.9) < 0.01

    def test_empty_analytics(self, temp_db):
        """Test analytics with no data."""
        tracker = TokenTracker(db_path=temp_db)
        analytics = tracker.get_analytics(period_days=30)

        assert analytics.total_searches == 0
        assert analytics.total_tokens_used == 0
        assert analytics.total_tokens_saved == 0
        assert analytics.efficiency_ratio == 0.0
        assert analytics.cost_savings_usd == 0.0


class TestTokenUsageEvent:
    """Test TokenUsageEvent dataclass."""

    def test_create_event(self):
        """Test creating a token usage event."""
        event = TokenUsageEvent(
            timestamp=datetime.now(),
            event_type="search",
            tokens_used=100,
            tokens_saved=400,
            project_name="test",
            session_id="session-1",
            query="test query",
            results_count=5,
            relevance_avg=0.85,
        )

        assert event.event_type == "search"
        assert event.tokens_used == 100
        assert event.tokens_saved == 400
        assert event.relevance_avg == 0.85


class TestTokenAnalytics:
    """Test TokenAnalytics dataclass."""

    def test_create_analytics(self):
        """Test creating token analytics."""
        now = datetime.now()
        analytics = TokenAnalytics(
            total_tokens_used=1000,
            total_tokens_saved=4000,
            total_searches=10,
            total_files_indexed=50,
            efficiency_ratio=0.8,
            cost_savings_usd=12.00,
            avg_relevance=0.85,
            period_start=now - timedelta(days=30),
            period_end=now,
        )

        assert analytics.total_tokens_used == 1000
        assert analytics.efficiency_ratio == 0.8
        assert analytics.cost_savings_usd == 12.00
