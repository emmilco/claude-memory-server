"""Tests for session summary command (UX-031)."""

import pytest
import tempfile
import os
from unittest.mock import patch, MagicMock
from src.cli.session_summary_command import run_session_summary_command
from src.analytics.token_tracker import TokenTracker


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


class TestSessionSummaryCommand:
    """Test session summary CLI command."""

    @patch("src.cli.session_summary_command.TokenTracker")
    def test_run_session_summary_with_id(self, mock_tracker_class, temp_db):
        """Test displaying summary for a specific session."""
        # Mock tracker instance
        mock_tracker = MagicMock()
        mock_tracker_class.return_value = mock_tracker

        # Mock session summary data
        mock_tracker.get_session_summary.return_value = {
            "session_id": "test-session-123",
            "searches": 10,
            "files_indexed": 50,
            "tokens_used": 5000,
            "tokens_saved": 20000,
            "cost_savings_usd": 0.06,
            "efficiency_ratio": 80.0,
            "avg_relevance": 0.85,
        }

        # Run command (should not raise)
        run_session_summary_command(session_id="test-session-123")

        # Verify tracker was called correctly
        mock_tracker.get_session_summary.assert_called_once_with("test-session-123")

    @patch("src.cli.session_summary_command.TokenTracker")
    def test_run_session_summary_without_id(self, mock_tracker_class, temp_db):
        """Test displaying recent sessions when no ID provided."""
        # Mock tracker instance
        mock_tracker = MagicMock()
        mock_tracker_class.return_value = mock_tracker

        # Mock top sessions data
        mock_tracker.get_top_sessions.return_value = [
            {
                "session_id": "session-1",
                "tokens_saved": 10000,
                "events": 5,
            },
            {
                "session_id": "session-2",
                "tokens_saved": 8000,
                "events": 3,
            },
        ]

        # Run command (should not raise)
        run_session_summary_command()

        # Verify tracker was called correctly
        mock_tracker.get_top_sessions.assert_called_once_with(limit=10)

    def test_session_summary_integration(self, temp_db):
        """Integration test with real tracker."""
        tracker = TokenTracker(db_path=temp_db)

        # Add some test data
        tracker.track_search(
            tokens_used=1000,
            results_count=5,
            relevance_avg=0.9,
            session_id="integration-test",
        )

        # Get summary
        summary = tracker.get_session_summary("integration-test")

        # Verify summary structure
        assert "session_id" in summary
        assert "searches" in summary
        assert "tokens_saved" in summary
        assert summary["searches"] == 1
