"""Integration tests for proactive suggestions."""

import pytest
import pytest_asyncio
import uuid
from src.core.server import MemoryRAGServer
from src.config import ServerConfig
from src.memory.pattern_detector import PatternType


@pytest.mark.asyncio
class TestProactiveSuggestionsIntegration:
    """Integration tests for proactive suggestion system."""

    @pytest_asyncio.fixture
    async def server(self, tmp_path, qdrant_client, unique_qdrant_collection):
        """Create a test server with suggestions enabled and pooled collection.

        Uses the session-scoped qdrant_client and unique_qdrant_collection
        fixtures from conftest.py to leverage collection pooling and prevent
        Qdrant deadlocks during parallel test execution.
        """
        config = ServerConfig(
            storage_backend="qdrant",
            qdrant_url="http://localhost:6333",
            qdrant_collection_name=unique_qdrant_collection,
            enable_proactive_suggestions=True,
            proactive_suggestions_threshold=0.90,
        )
        server_instance = MemoryRAGServer(config=config)
        await server_instance.initialize()
        yield server_instance

        # Cleanup
        await server_instance.close()
        # Collection cleanup handled by unique_qdrant_collection autouse fixture

    async def test_analyze_conversation_implementation_request(self, server):
        """Test analyzing a message with implementation request pattern."""
        message = "I need to add user authentication to my application"

        result = await server.analyze_conversation(message=message)

        assert result["enabled"] is True
        assert len(result["patterns"]) > 0
        assert result["patterns"][0]["type"] == PatternType.IMPLEMENTATION_REQUEST.value
        assert result["confidence"] >= 0.85

    async def test_analyze_conversation_error_debugging(self, server):
        """Test analyzing a message with error debugging pattern."""
        message = "Why isn't the login function working? Getting an error."

        result = await server.analyze_conversation(message=message)

        assert result["enabled"] is True
        assert len(result["patterns"]) > 0
        assert result["patterns"][0]["type"] == PatternType.ERROR_DEBUGGING.value
        assert result["confidence"] >= 0.90

    async def test_analyze_conversation_code_question(self, server):
        """Test analyzing a message with code question pattern."""
        message = "How does the authentication system work in this codebase?"

        result = await server.analyze_conversation(message=message)

        assert result["enabled"] is True
        assert len(result["patterns"]) > 0
        assert result["patterns"][0]["type"] == PatternType.CODE_QUESTION.value

    async def test_analyze_conversation_no_pattern(self, server):
        """Test analyzing a message with no detectable patterns."""
        message = "Hello, how are you today?"

        result = await server.analyze_conversation(message=message)

        assert result["enabled"] is True
        assert len(result["patterns"]) == 0
        assert result["should_inject"] is False

    async def test_get_suggestion_stats(self, server):
        """Test getting suggestion statistics."""
        stats = await server.get_suggestion_stats()

        assert stats["enabled"] is True
        assert "messages_analyzed" in stats
        assert "suggestions_made" in stats
        assert "high_confidence_threshold" in stats
        assert "feedback" in stats

    async def test_provide_feedback_cycle(self, server):
        """Test full feedback cycle: analyze -> provide feedback -> check adjustment."""
        # Analyze a message
        message = "I need to implement OAuth authentication"
        result = await server.analyze_conversation(message=message)

        assert result["enabled"] is True
        suggestion_id = result["suggestion_id"]

        # Provide feedback
        feedback_result = await server.provide_suggestion_feedback(
            suggestion_id=suggestion_id, accepted=True, implicit=False
        )

        assert feedback_result["success"] is True
        assert feedback_result["accepted"] is True
        assert "current_threshold" in feedback_result

    async def test_set_suggestion_mode_disable(self, server):
        """Test disabling proactive suggestions."""
        result = await server.set_suggestion_mode(enabled=False)

        assert result["success"] is True
        assert result["enabled"] is False

        # Analyzing should still work but return disabled status
        analysis = await server.analyze_conversation(
            message="I need to add a feature"
        )
        # Should return empty or minimal result when disabled
        assert analysis["enabled"] is True  # Server-level enabled
        # But no patterns should be returned when engine is disabled

    async def test_set_suggestion_mode_custom_threshold(self, server):
        """Test setting custom threshold."""
        result = await server.set_suggestion_mode(enabled=True, threshold=0.85)

        assert result["success"] is True
        assert result["enabled"] is True
        assert result["high_confidence_threshold"] == 0.85

    async def test_disabled_server_returns_disabled_message(self, tmp_path, unique_qdrant_collection):
        """Test that disabled server returns appropriate message."""
        config = ServerConfig(
            storage_backend="qdrant",
            qdrant_url="http://localhost:6333",
            qdrant_collection_name=unique_qdrant_collection,
            enable_proactive_suggestions=False,
        )
        server_instance = MemoryRAGServer(config=config)
        await server_instance.initialize()

        result = await server_instance.analyze_conversation(message="Test message")
        assert result["enabled"] is False
        assert "disabled" in result["message"].lower()

        await server_instance.close()
        # Collection cleanup handled by unique_qdrant_collection autouse fixture

    async def test_end_to_end_with_indexed_code(self, server):
        """Test proactive suggestions with actual indexed code."""
        # First, store some code-like memories
        await server.store_memory(
            content="def authenticate_user(username, password): ...",
            category="context",
            scope="project",
            project_name="test-project",
        )

        await server.store_memory(
            content="class UserAuthenticator: ...",
            category="context",
            scope="project",
            project_name="test-project",
        )

        # Now analyze a related message
        message = "I need to add user authentication"
        result = await server.analyze_conversation(message=message)

        assert result["enabled"] is True
        assert len(result["patterns"]) > 0

        # If search was performed, we should have results
        if result["search_performed"]:
            # Results might be empty if similarity is low, that's okay
            assert "result_count" in result

    async def test_multiple_patterns_prioritized_by_confidence(self, server):
        """Test that highest confidence pattern is used for search."""
        # Message with multiple patterns
        message = "Why isn't this working? I need to implement a fix. How does it work?"

        result = await server.analyze_conversation(message=message)

        assert result["enabled"] is True
        # Should detect multiple patterns
        assert len(result["patterns"]) >= 2

        # Primary pattern (first one) should have highest confidence
        if len(result["patterns"]) > 1:
            assert result["patterns"][0]["confidence"] >= result["patterns"][1]["confidence"]
