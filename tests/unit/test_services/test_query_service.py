"""Tests for QueryService - Query expansion, conversation tracking, and suggestions.

This test suite covers:
- Conversation session management (start, end, list)
- Query expansion with context
- Conversation analysis for suggestions
- Suggestion feedback collection
- Suggestion mode configuration
- Suggestion statistics
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from src.services.query_service import QueryService
from src.config import ServerConfig


class TestQueryServiceInit:
    """Test QueryService initialization."""

    def test_initialization_with_required_dependencies(self):
        """Test service initializes with required dependencies."""
        config = ServerConfig()

        service = QueryService(config=config)

        assert service.config == config
        assert service.conversation_tracker is None
        assert service.query_expander is None
        assert service.suggestion_engine is None

    def test_initialization_with_all_dependencies(self):
        """Test service initializes with all dependencies."""
        config = ServerConfig()
        conversation_tracker = MagicMock()
        query_expander = MagicMock()
        suggestion_engine = MagicMock()
        hybrid_searcher = MagicMock()

        service = QueryService(
            config=config,
            conversation_tracker=conversation_tracker,
            query_expander=query_expander,
            suggestion_engine=suggestion_engine,
            hybrid_searcher=hybrid_searcher,
        )

        assert service.conversation_tracker == conversation_tracker
        assert service.query_expander == query_expander
        assert service.suggestion_engine == suggestion_engine
        assert service.hybrid_searcher == hybrid_searcher

    def test_initial_stats_are_zero(self):
        """Test service stats start at zero."""
        service = QueryService(config=ServerConfig())

        stats = service.get_stats()
        assert stats["sessions_created"] == 0
        assert stats["sessions_ended"] == 0
        assert stats["queries_expanded"] == 0
        assert stats["suggestions_generated"] == 0
        assert stats["feedback_collected"] == 0


class TestStartConversationSession:
    """Test start_conversation_session method."""

    @pytest.fixture
    def service(self):
        """Create service with conversation tracker."""
        conversation_tracker = MagicMock()
        conversation_tracker.create_session.return_value = "session_123"

        return QueryService(
            config=ServerConfig(),
            conversation_tracker=conversation_tracker,
        )

    @pytest.mark.asyncio
    async def test_start_without_tracker_returns_disabled(self):
        """Test starting session without tracker raises StorageError."""
        from src.core.exceptions import StorageError

        service = QueryService(
            config=ServerConfig(),
            conversation_tracker=None,
        )

        with pytest.raises(StorageError):
            await service.start_conversation_session()

    @pytest.mark.asyncio
    async def test_start_success(self, service):
        """Test successful session start."""
        result = await service.start_conversation_session(
            description="Testing session"
        )

        assert result["status"] == "created"
        assert result["session_id"] == "session_123"
        assert result["description"] == "Testing session"

    @pytest.mark.asyncio
    async def test_start_increments_stats(self, service):
        """Test starting session increments statistics."""
        initial_stats = service.get_stats()
        await service.start_conversation_session()

        stats = service.get_stats()
        assert stats["sessions_created"] == initial_stats["sessions_created"] + 1

    @pytest.mark.asyncio
    async def test_start_error_returns_failed(self, service):
        """Test start error raises StorageError."""
        from src.core.exceptions import StorageError

        service.conversation_tracker.create_session.side_effect = Exception("Creation failed")

        with pytest.raises(StorageError):
            await service.start_conversation_session()


class TestEndConversationSession:
    """Test end_conversation_session method."""

    @pytest.fixture
    def service(self):
        """Create service with conversation tracker."""
        conversation_tracker = MagicMock()
        conversation_tracker.end_session.return_value = {
            "queries_count": 10,
            "duration_minutes": 30,
        }

        return QueryService(
            config=ServerConfig(),
            conversation_tracker=conversation_tracker,
        )

    @pytest.mark.asyncio
    async def test_end_without_tracker_returns_disabled(self):
        """Test ending session without tracker raises StorageError."""
        from src.core.exceptions import StorageError

        service = QueryService(
            config=ServerConfig(),
            conversation_tracker=None,
        )

        with pytest.raises(StorageError):
            await service.end_conversation_session("session_123")

    @pytest.mark.asyncio
    async def test_end_success(self, service):
        """Test successful session end."""
        result = await service.end_conversation_session("session_123")

        assert result["status"] == "ended"
        assert result["session_id"] == "session_123"
        assert "summary" in result

    @pytest.mark.asyncio
    async def test_end_increments_stats(self, service):
        """Test ending session increments statistics."""
        initial_stats = service.get_stats()
        await service.end_conversation_session("session_123")

        stats = service.get_stats()
        assert stats["sessions_ended"] == initial_stats["sessions_ended"] + 1

    @pytest.mark.asyncio
    async def test_end_error_returns_failed(self, service):
        """Test end error raises StorageError."""
        from src.core.exceptions import StorageError

        service.conversation_tracker.end_session.side_effect = Exception("End failed")

        with pytest.raises(StorageError):
            await service.end_conversation_session("session_123")


class TestListConversationSessions:
    """Test list_conversation_sessions method."""

    @pytest.fixture
    def service(self):
        """Create service with conversation tracker."""
        conversation_tracker = MagicMock()
        conversation_tracker.list_sessions.return_value = [
            {"session_id": "session_1", "description": "Test 1"},
            {"session_id": "session_2", "description": "Test 2"},
        ]

        return QueryService(
            config=ServerConfig(),
            conversation_tracker=conversation_tracker,
        )

    @pytest.mark.asyncio
    async def test_list_without_tracker_returns_disabled(self):
        """Test listing without tracker raises StorageError."""
        from src.core.exceptions import StorageError

        service = QueryService(
            config=ServerConfig(),
            conversation_tracker=None,
        )

        with pytest.raises(StorageError):
            await service.list_conversation_sessions()

    @pytest.mark.asyncio
    async def test_list_success(self, service):
        """Test successful session listing."""
        result = await service.list_conversation_sessions()

        assert result["status"] == "success"
        assert len(result["sessions"]) == 2
        assert result["total_count"] == 2

    @pytest.mark.asyncio
    async def test_list_error_returns_failed(self, service):
        """Test list error raises StorageError."""
        from src.core.exceptions import StorageError

        service.conversation_tracker.list_sessions.side_effect = Exception("List failed")

        with pytest.raises(StorageError):
            await service.list_conversation_sessions()


class TestAnalyzeConversation:
    """Test analyze_conversation method."""

    @pytest.fixture
    def service(self):
        """Create service with suggestion engine."""
        suggestion_engine = MagicMock()
        suggestion_engine.analyze.return_value = {
            "topics": ["authentication", "security"],
            "suggestions": [
                {"suggestion_id": "s1", "text": "Try searching for auth flows"},
            ],
        }

        return QueryService(
            config=ServerConfig(),
            suggestion_engine=suggestion_engine,
        )

    @pytest.mark.asyncio
    async def test_analyze_without_engine_returns_disabled(self):
        """Test analyzing without engine raises StorageError."""
        from src.core.exceptions import StorageError

        service = QueryService(
            config=ServerConfig(),
            suggestion_engine=None,
        )

        with pytest.raises(StorageError):
            await service.analyze_conversation(messages=["test"])

    @pytest.mark.asyncio
    async def test_analyze_success(self, service):
        """Test successful conversation analysis."""
        result = await service.analyze_conversation(
            messages=["How do I implement auth?", "What about OAuth?"],
            session_id="session_123",
        )

        assert result["status"] == "success"
        assert "analysis" in result
        assert "suggestions" in result
        assert result["session_id"] == "session_123"

    @pytest.mark.asyncio
    async def test_analyze_increments_stats(self, service):
        """Test analysis increments statistics."""
        initial_stats = service.get_stats()
        await service.analyze_conversation(messages=["test"])

        stats = service.get_stats()
        assert stats["suggestions_generated"] == initial_stats["suggestions_generated"] + 1

    @pytest.mark.asyncio
    async def test_analyze_error_returns_failed(self, service):
        """Test analysis error raises StorageError."""
        from src.core.exceptions import StorageError

        service.suggestion_engine.analyze.side_effect = Exception("Analysis failed")

        with pytest.raises(StorageError):
            await service.analyze_conversation(messages=["test"])


class TestGetSuggestionStats:
    """Test get_suggestion_stats method."""

    @pytest.fixture
    def service(self):
        """Create service with suggestion engine."""
        suggestion_engine = MagicMock()
        suggestion_engine.get_statistics.return_value = {
            "total_suggestions": 100,
            "accepted_rate": 0.75,
        }

        return QueryService(
            config=ServerConfig(),
            suggestion_engine=suggestion_engine,
        )

    @pytest.mark.asyncio
    async def test_stats_without_engine_returns_disabled(self):
        """Test stats without engine raises StorageError."""
        from src.core.exceptions import StorageError

        service = QueryService(
            config=ServerConfig(),
            suggestion_engine=None,
        )

        with pytest.raises(StorageError):
            await service.get_suggestion_stats()

    @pytest.mark.asyncio
    async def test_stats_success(self, service):
        """Test successful statistics retrieval."""
        result = await service.get_suggestion_stats()

        assert result["status"] == "success"
        assert "statistics" in result

    @pytest.mark.asyncio
    async def test_stats_error_returns_failed(self, service):
        """Test stats error raises StorageError."""
        from src.core.exceptions import StorageError

        service.suggestion_engine.get_statistics.side_effect = Exception("Stats failed")

        with pytest.raises(StorageError):
            await service.get_suggestion_stats()


class TestProvideSuggestionFeedback:
    """Test provide_suggestion_feedback method."""

    @pytest.fixture
    def service(self):
        """Create service with suggestion engine."""
        suggestion_engine = MagicMock()
        suggestion_engine.record_feedback = MagicMock()

        return QueryService(
            config=ServerConfig(),
            suggestion_engine=suggestion_engine,
        )

    @pytest.mark.asyncio
    async def test_feedback_without_engine_returns_disabled(self):
        """Test feedback without engine raises StorageError."""
        from src.core.exceptions import StorageError

        service = QueryService(
            config=ServerConfig(),
            suggestion_engine=None,
        )

        with pytest.raises(StorageError):
            await service.provide_suggestion_feedback(
                suggestion_id="s1",
                accepted=True,
            )

    @pytest.mark.asyncio
    async def test_feedback_accepted(self, service):
        """Test successful accepted feedback."""
        result = await service.provide_suggestion_feedback(
            suggestion_id="s1",
            accepted=True,
            feedback="Very helpful suggestion",
        )

        assert result["status"] == "success"
        assert result["suggestion_id"] == "s1"
        assert result["accepted"] is True

    @pytest.mark.asyncio
    async def test_feedback_rejected(self, service):
        """Test successful rejected feedback."""
        result = await service.provide_suggestion_feedback(
            suggestion_id="s2",
            accepted=False,
            feedback="Not relevant",
        )

        assert result["status"] == "success"
        assert result["accepted"] is False

    @pytest.mark.asyncio
    async def test_feedback_increments_stats(self, service):
        """Test feedback increments statistics."""
        initial_stats = service.get_stats()
        await service.provide_suggestion_feedback(
            suggestion_id="s1",
            accepted=True,
        )

        stats = service.get_stats()
        assert stats["feedback_collected"] == initial_stats["feedback_collected"] + 1

    @pytest.mark.asyncio
    async def test_feedback_error_returns_failed(self, service):
        """Test feedback error raises StorageError."""
        from src.core.exceptions import StorageError

        service.suggestion_engine.record_feedback.side_effect = Exception("Feedback failed")

        with pytest.raises(StorageError):
            await service.provide_suggestion_feedback(
                suggestion_id="s1",
                accepted=True,
            )


class TestSetSuggestionMode:
    """Test set_suggestion_mode method."""

    @pytest.fixture
    def service(self):
        """Create service with suggestion engine."""
        suggestion_engine = MagicMock()
        suggestion_engine.set_mode = MagicMock()

        return QueryService(
            config=ServerConfig(),
            suggestion_engine=suggestion_engine,
        )

    @pytest.mark.asyncio
    async def test_mode_without_engine_returns_disabled(self):
        """Test setting mode without engine raises StorageError."""
        from src.core.exceptions import StorageError

        service = QueryService(
            config=ServerConfig(),
            suggestion_engine=None,
        )

        with pytest.raises(StorageError):
            await service.set_suggestion_mode(mode="balanced")

    @pytest.mark.asyncio
    async def test_mode_aggressive(self, service):
        """Test setting aggressive mode."""
        result = await service.set_suggestion_mode(mode="aggressive")

        assert result["status"] == "success"
        assert result["mode"] == "aggressive"

    @pytest.mark.asyncio
    async def test_mode_balanced(self, service):
        """Test setting balanced mode."""
        result = await service.set_suggestion_mode(
            mode="balanced",
            confidence_threshold=0.7,
        )

        assert result["status"] == "success"
        assert result["mode"] == "balanced"
        assert result["confidence_threshold"] == 0.7

    @pytest.mark.asyncio
    async def test_mode_conservative(self, service):
        """Test setting conservative mode."""
        result = await service.set_suggestion_mode(mode="conservative")

        assert result["status"] == "success"
        assert result["mode"] == "conservative"

    @pytest.mark.asyncio
    async def test_mode_invalid_returns_failed(self, service):
        """Test invalid mode raises StorageError."""
        from src.core.exceptions import StorageError

        with pytest.raises(StorageError, match="Invalid.*mode"):
            await service.set_suggestion_mode(mode="invalid_mode")

    @pytest.mark.asyncio
    async def test_mode_error_returns_failed(self, service):
        """Test mode setting error raises StorageError."""
        from src.core.exceptions import StorageError

        service.suggestion_engine.set_mode.side_effect = Exception("Mode failed")

        with pytest.raises(StorageError):
            await service.set_suggestion_mode(mode="balanced")


class TestExpandQuery:
    """Test expand_query method."""

    @pytest.fixture
    def service(self):
        """Create service with query expander."""
        query_expander = AsyncMock()
        query_expander.expand_query = AsyncMock(
            return_value="authentication login user credentials"
        )

        return QueryService(
            config=ServerConfig(),
            query_expander=query_expander,
        )

    @pytest.mark.asyncio
    async def test_expand_without_expander_returns_original(self):
        """Test expanding without expander raises StorageError."""
        from src.core.exceptions import StorageError

        service = QueryService(
            config=ServerConfig(),
            query_expander=None,
        )

        with pytest.raises(StorageError):
            await service.expand_query(query="auth login")

    @pytest.mark.asyncio
    async def test_expand_success(self, service):
        """Test successful query expansion."""
        result = await service.expand_query(
            query="auth login",
            context=["previous query about users"],
        )

        assert result["status"] == "success"
        assert result["original_query"] == "auth login"
        assert result["expanded_query"] == "authentication login user credentials"
        assert result["expansion_applied"] is True

    @pytest.mark.asyncio
    async def test_expand_no_change(self, service):
        """Test expansion when query unchanged."""
        service.query_expander.expand_query = AsyncMock(return_value="same query")

        result = await service.expand_query(query="same query")

        assert result["expansion_applied"] is False

    @pytest.mark.asyncio
    async def test_expand_increments_stats_on_change(self, service):
        """Test expansion increments stats when query changes."""
        initial_stats = service.get_stats()
        await service.expand_query(query="auth")

        stats = service.get_stats()
        assert stats["queries_expanded"] == initial_stats["queries_expanded"] + 1

    @pytest.mark.asyncio
    async def test_expand_no_increment_when_unchanged(self, service):
        """Test expansion does not increment stats when unchanged."""
        service.query_expander.expand_query = AsyncMock(return_value="same")

        initial_stats = service.get_stats()
        await service.expand_query(query="same")

        stats = service.get_stats()
        assert stats["queries_expanded"] == initial_stats["queries_expanded"]

    @pytest.mark.asyncio
    async def test_expand_error_returns_original(self, service):
        """Test expansion error raises StorageError."""
        from src.core.exceptions import StorageError

        service.query_expander.expand_query = AsyncMock(
            side_effect=Exception("Expansion failed")
        )

        with pytest.raises(StorageError, match="Failed to expand query"):
            await service.expand_query(query="test query")


class TestIntegrationScenarios:
    """Test integration scenarios for query service."""

    @pytest.fixture
    def fully_configured_service(self):
        """Create fully configured service."""
        conversation_tracker = MagicMock()
        conversation_tracker.create_session.return_value = "session_123"
        conversation_tracker.end_session.return_value = {"queries": 10}
        conversation_tracker.list_sessions.return_value = []

        query_expander = AsyncMock()
        query_expander.expand_query = AsyncMock(
            side_effect=lambda q, c: f"expanded: {q}"
        )

        suggestion_engine = MagicMock()
        suggestion_engine.analyze.return_value = {"suggestions": []}
        suggestion_engine.get_statistics.return_value = {}
        suggestion_engine.record_feedback = MagicMock()
        suggestion_engine.set_mode = MagicMock()

        return QueryService(
            config=ServerConfig(),
            conversation_tracker=conversation_tracker,
            query_expander=query_expander,
            suggestion_engine=suggestion_engine,
        )

    @pytest.mark.asyncio
    async def test_full_session_workflow(self, fully_configured_service):
        """Test complete session workflow."""
        service = fully_configured_service

        # Start session
        start_result = await service.start_conversation_session(
            description="Test session"
        )
        assert start_result["status"] == "created"
        session_id = start_result["session_id"]

        # Expand some queries
        expand_result = await service.expand_query(query="test query")
        assert expand_result["status"] == "success"

        # Analyze conversation
        analyze_result = await service.analyze_conversation(
            messages=["query 1", "query 2"],
            session_id=session_id,
        )
        assert analyze_result["status"] == "success"

        # End session
        end_result = await service.end_conversation_session(session_id)
        assert end_result["status"] == "ended"

    @pytest.mark.asyncio
    async def test_suggestion_feedback_workflow(self, fully_configured_service):
        """Test suggestion and feedback workflow."""
        service = fully_configured_service

        # Set mode
        mode_result = await service.set_suggestion_mode(mode="balanced")
        assert mode_result["status"] == "success"

        # Analyze conversation to get suggestions
        analyze_result = await service.analyze_conversation(
            messages=["How do I implement caching?"]
        )
        assert analyze_result["status"] == "success"

        # Provide feedback
        feedback_result = await service.provide_suggestion_feedback(
            suggestion_id="s1",
            accepted=True,
            feedback="Helpful",
        )
        assert feedback_result["status"] == "success"

        # Check stats
        stats_result = await service.get_suggestion_stats()
        assert stats_result["status"] == "success"


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.fixture
    def service(self):
        """Create service for edge case tests."""
        conversation_tracker = MagicMock()
        conversation_tracker.create_session.return_value = "session_edge"

        query_expander = AsyncMock()
        query_expander.expand_query = AsyncMock(side_effect=lambda q, c: q)

        return QueryService(
            config=ServerConfig(),
            conversation_tracker=conversation_tracker,
            query_expander=query_expander,
        )

    @pytest.mark.asyncio
    async def test_empty_description_session(self, service):
        """Test starting session with empty description."""
        result = await service.start_conversation_session(description="")

        assert result["status"] == "created"
        assert result["description"] == ""

    @pytest.mark.asyncio
    async def test_none_description_session(self, service):
        """Test starting session with None description."""
        result = await service.start_conversation_session(description=None)

        assert result["status"] == "created"
        assert result["description"] is None

    @pytest.mark.asyncio
    async def test_expand_empty_query(self, service):
        """Test expanding empty query."""
        result = await service.expand_query(query="")

        assert result["expanded_query"] == ""
        assert result["expansion_applied"] is False

    @pytest.mark.asyncio
    async def test_expand_with_empty_context(self, service):
        """Test expanding with empty context list."""
        result = await service.expand_query(
            query="test",
            context=[],
        )

        # Should still work
        assert "expanded_query" in result

    @pytest.mark.asyncio
    async def test_analyze_empty_messages(self):
        """Test analyzing empty messages list."""
        suggestion_engine = MagicMock()
        suggestion_engine.analyze.return_value = {"suggestions": []}

        service = QueryService(
            config=ServerConfig(),
            suggestion_engine=suggestion_engine,
        )

        result = await service.analyze_conversation(messages=[])

        assert result["status"] == "success"


class TestStatisticsAccumulation:
    """Test that statistics accumulate correctly."""

    @pytest.fixture
    def service(self):
        """Create fully configured service for stats tests."""
        conversation_tracker = MagicMock()
        conversation_tracker.create_session.return_value = "session"
        conversation_tracker.end_session.return_value = {}

        query_expander = AsyncMock()
        query_expander.expand_query = AsyncMock(
            side_effect=lambda q, c: f"expanded_{q}"
        )

        suggestion_engine = MagicMock()
        suggestion_engine.analyze.return_value = {"suggestions": []}
        suggestion_engine.record_feedback = MagicMock()

        return QueryService(
            config=ServerConfig(),
            conversation_tracker=conversation_tracker,
            query_expander=query_expander,
            suggestion_engine=suggestion_engine,
        )

    @pytest.mark.asyncio
    async def test_stats_accumulate_over_multiple_operations(self, service):
        """Test statistics accumulate correctly."""
        # Start multiple sessions
        for _ in range(3):
            await service.start_conversation_session()

        # End some sessions
        for _ in range(2):
            await service.end_conversation_session("session")

        # Expand queries
        for _ in range(5):
            await service.expand_query(query="test")

        # Analyze conversations
        for _ in range(4):
            await service.analyze_conversation(messages=["test"])

        # Provide feedback
        for _ in range(6):
            await service.provide_suggestion_feedback(
                suggestion_id="s1",
                accepted=True,
            )

        stats = service.get_stats()
        assert stats["sessions_created"] == 3
        assert stats["sessions_ended"] == 2
        assert stats["queries_expanded"] == 5
        assert stats["suggestions_generated"] == 4
        assert stats["feedback_collected"] == 6

    @pytest.mark.asyncio
    async def test_stats_independent(self, service):
        """Test get_stats returns copy, not reference."""
        stats1 = service.get_stats()
        await service.start_conversation_session()
        stats2 = service.get_stats()

        # Modifying stats1 should not affect internal state
        stats1["sessions_created"] = 100

        assert stats2["sessions_created"] == 1
        assert service.get_stats()["sessions_created"] == 1
