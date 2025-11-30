"""Tests for proactive suggester."""

import pytest
from datetime import datetime, UTC, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from src.memory.proactive_suggester import ProactiveSuggester
from src.memory.intent_detector import IntentDetector, DetectedIntent
from src.memory.conversation_tracker import ConversationTracker, QueryRecord
from src.core.models import (
from conftest import mock_embedding
    MemoryResult,
    MemoryUnit,
    MemoryProvenance,
    ProvenanceSource,
    MemoryCategory,
    ContextLevel,
)


def create_memory_result(
    id: str = "mem_1",
    content: str = "test content",
    score: float = 0.9,
    importance: float = 0.8,
    last_accessed: datetime = None,
    metadata: dict = None,
) -> MemoryResult:
    """Helper to create MemoryResult for testing."""
    if last_accessed is None:
        last_accessed = datetime.now(UTC)
    if metadata is None:
        metadata = {}

    memory = MemoryUnit(
        id=id,
        content=content,
        category=MemoryCategory.FACT,
        context_level=ContextLevel.PROJECT_CONTEXT,
        importance=importance,
        last_accessed=last_accessed,
        metadata=metadata,
    )

    return MemoryResult(
        memory=memory,
        score=score,
    )


@pytest.fixture
def mock_store():
    """Create mock memory store."""
    store = AsyncMock()
    return store


@pytest.fixture
def mock_embedding_generator():
    """Create mock embedding generator."""
    generator = AsyncMock()
    generator.generate_embedding.return_value = mock_embedding(value=0.1)  # Mock embedding
    return generator


@pytest.fixture
def conversation_tracker():
    """Create conversation tracker."""
    from src.config import ServerConfig
    config = ServerConfig()
    return ConversationTracker(config)


@pytest.fixture
def intent_detector():
    """Create intent detector."""
    return IntentDetector(context_window=5)


@pytest.fixture
def suggester(mock_store, mock_embedding_generator, conversation_tracker, intent_detector):
    """Create proactive suggester."""
    return ProactiveSuggester(
        store=mock_store,
        embedding_generator=mock_embedding_generator,
        conversation_tracker=conversation_tracker,
        intent_detector=intent_detector,
        confidence_threshold=0.85,
        max_suggestions=5,
    )


class TestProactiveSuggester:
    """Test ProactiveSuggester class."""

    @pytest.mark.asyncio
    async def test_suggest_memories_no_session(self, suggester):
        """Test with non-existent session."""
        response = await suggester.suggest_memories(session_id="nonexistent")

        assert response.total_suggestions == 0
        assert len(response.suggestions) == 0
        assert response.session_id == "nonexistent"

    @pytest.mark.asyncio
    async def test_suggest_memories_empty_queries(self, suggester, conversation_tracker):
        """Test with session but no queries."""
        session_id = conversation_tracker.create_session()

        response = await suggester.suggest_memories(session_id=session_id)

        assert response.total_suggestions == 0
        assert len(response.suggestions) == 0

    @pytest.mark.asyncio
    async def test_suggest_memories_basic_flow(
        self, suggester, conversation_tracker, mock_store
    ):
        """Test basic suggestion flow."""
        # Create session with queries
        session_id = conversation_tracker.create_session()
        conversation_tracker.track_query(
            session_id,
            "How do I implement authentication?",
            []
        )

        # Mock search results
        mock_result = create_memory_result(
            id="mem_1",
            content="def authenticate(user, password): ...",
            score=0.95,
            importance=0.8,
            metadata={"file_path": "auth.py"},
        )
        mock_store.search.return_value = [mock_result]

        response = await suggester.suggest_memories(
            session_id=session_id,
            confidence_threshold=0.7,  # Lower threshold for test
        )

        # Should detect implementation intent
        assert response.detected_intent.intent_type == "implementation"
        assert "authentication" in response.detected_intent.keywords or \
               "auth" in response.detected_intent.keywords

        # Should return at least one suggestion
        assert response.total_suggestions >= 1
        if response.suggestions:
            assert response.suggestions[0].confidence >= response.confidence_threshold

    @pytest.mark.asyncio
    async def test_deduplication_of_shown_results(
        self, suggester, conversation_tracker, mock_store
    ):
        """Test that already-shown results are deduplicated."""
        # Create session and track a shown result
        session_id = conversation_tracker.create_session()
        conversation_tracker.track_query(
            session_id,
            "How do I authenticate users?",
            ["mem_1"]  # Already shown
        )

        # Mock search results including the already-shown memory
        mock_result_shown = create_memory_result(
            id="mem_1",  # Already shown
            content="def authenticate(): ...",
            score=0.95,
            importance=0.9,
        )
        mock_result_new = create_memory_result(
            id="mem_2",  # New
            content="def authorize(): ...",
            score=0.90,
            importance=0.8,
        )
        mock_store.search.return_value = [mock_result_shown, mock_result_new]

        response = await suggester.suggest_memories(session_id=session_id)

        # Should filter out already-shown memory
        suggestion_ids = [s.memory_id for s in response.suggestions]
        assert "mem_1" not in suggestion_ids
        assert suggester.stats["deduplications"] > 0

    @pytest.mark.asyncio
    async def test_confidence_threshold_filtering(
        self, suggester, conversation_tracker, mock_store
    ):
        """Test that low-confidence results are filtered."""
        # Create session with query
        session_id = conversation_tracker.create_session()
        conversation_tracker.track_query(
            session_id,
            "How do I implement auth?",
            []
        )

        # Mock low-confidence result
        old_date = datetime.now(UTC) - timedelta(days=200)  # Very old
        mock_result = create_memory_result(
            id="mem_1",
            content="unrelated content",
            score=0.3,  # Low similarity
            importance=0.2,  # Low importance
            last_accessed=old_date,  # Very old
        )
        mock_store.search.return_value = [mock_result]

        response = await suggester.suggest_memories(
            session_id=session_id,
            confidence_threshold=0.85,
        )

        # Should filter out low-confidence result
        assert response.total_suggestions == 0

    @pytest.mark.asyncio
    async def test_max_suggestions_limit(
        self, suggester, conversation_tracker, mock_store
    ):
        """Test that max suggestions limit is respected."""
        # Create session with query
        session_id = conversation_tracker.create_session()
        conversation_tracker.track_query(
            session_id,
            "Show me authentication examples",
            []
        )

        # Mock many high-confidence results
        mock_results = [
            create_memory_result(
                id=f"mem_{i}",
                content=f"def auth_{i}(): ...",
                score=0.95,
                importance=0.9,
            )
            for i in range(20)
        ]
        mock_store.search.return_value = mock_results

        response = await suggester.suggest_memories(
            session_id=session_id,
            max_suggestions=3,
        )

        # Should limit to 3 suggestions
        assert response.total_suggestions <= 3
        assert len(response.suggestions) <= 3

    @pytest.mark.asyncio
    async def test_confidence_calculation_high_similarity(self, suggester):
        """Test confidence calculation with high semantic similarity."""
        mock_result = create_memory_result(
            id="mem_1",
            content="test content",
            score=0.95,  # High similarity
            importance=0.5,
        )

        detected_intent = DetectedIntent(
            intent_type="general",
            keywords=["test"],
            confidence=0.8,
            search_query="test",
            original_queries=["test"],
        )

        confidence, factors = suggester._calculate_confidence(
            mock_result,
            detected_intent,
        )

        # High similarity should dominate (50% weight)
        assert factors.semantic_similarity >= 0.9
        assert confidence > 0.7  # Should be high overall

    @pytest.mark.asyncio
    async def test_confidence_calculation_recency(self, suggester):
        """Test recency score calculation."""
        now = datetime.now(UTC)

        # Test very recent
        recent_date = now - timedelta(days=3)
        recent_score = suggester._calculate_recency_score(recent_date)
        assert recent_score == 1.0

        # Test moderate age
        moderate_date = now - timedelta(days=60)
        moderate_score = suggester._calculate_recency_score(moderate_date)
        assert 0.3 <= moderate_score <= 0.8

        # Test very old
        old_date = now - timedelta(days=200)
        old_score = suggester._calculate_recency_score(old_date)
        assert old_score == 0.1

    @pytest.mark.asyncio
    async def test_context_match_calculation(self, suggester):
        """Test context match scoring."""
        content = "This is about JWT authentication and token validation"
        keywords = ["jwt", "authentication", "token"]

        # All keywords present
        score = suggester._calculate_context_match(content, keywords)
        assert score == 1.0

        # Partial match
        partial_keywords = ["jwt", "nonexistent"]
        partial_score = suggester._calculate_context_match(content, partial_keywords)
        assert partial_score == 0.5

        # No keywords
        empty_score = suggester._calculate_context_match(content, [])
        assert empty_score == 0.5  # Neutral

    @pytest.mark.asyncio
    async def test_reason_generation_implementation(self, suggester):
        """Test reason generation for implementation intent."""
        mock_result = create_memory_result(
            id="mem_1",
            content="def authenticate(): ...",
            score=0.9,
            importance=0.8,
            last_accessed=datetime.now(UTC)
        )

        detected_intent = DetectedIntent(
            intent_type="implementation",
            keywords=["authentication"],
            confidence=0.85,
            search_query="implement authentication",
            original_queries=["How do I implement authentication?"],
        )

        confidence, factors = suggester._calculate_confidence(
            mock_result,
            detected_intent,
        )

        reason = suggester._generate_reason(
            mock_result,
            detected_intent,
            factors,
        )

        # Should mention implementation pattern
        assert "implementation" in reason.lower() or "similar" in reason.lower()

    @pytest.mark.asyncio
    async def test_reason_generation_debugging(self, suggester):
        """Test reason generation for debugging intent."""
        mock_result = create_memory_result(
            id="mem_1",
            content="Common auth errors and fixes",
            score=0.85,
            importance=0.7,
            last_accessed=datetime.now(UTC)
        )

        detected_intent = DetectedIntent(
            intent_type="debugging",
            keywords=["error", "auth"],
            confidence=0.8,
            search_query="fix auth error",
            original_queries=["Why is auth failing?"],
        )

        confidence, factors = suggester._calculate_confidence(
            mock_result,
            detected_intent,
        )

        reason = suggester._generate_reason(
            mock_result,
            detected_intent,
            factors,
        )

        # Should mention debugging help
        assert "debug" in reason.lower() or "help" in reason.lower()

    @pytest.mark.asyncio
    async def test_source_type_detection_code(self, suggester):
        """Test source type detection for code."""
        # Test with file_path in metadata
        code_result = create_memory_result(
            id="mem_1",
            content="def test(): pass",
            score=0.9,
            importance=0.8,
            metadata={"file_path": "src/auth.py"},
        )

        source_type = suggester._determine_source_type(code_result)
        assert source_type == "code"

    @pytest.mark.asyncio
    async def test_source_type_detection_memory(self, suggester):
        """Test source type detection for memory."""
        memory_result = create_memory_result(
            id="mem_1",
            content="User prefers tabs over spaces",
            score=0.9,
            importance=0.8,
            last_accessed=datetime.now(UTC),
            metadata={},
        )

        source_type = suggester._determine_source_type(memory_result)
        assert source_type == "memory"

    @pytest.mark.asyncio
    async def test_suggestions_sorted_by_confidence(
        self, suggester, conversation_tracker, mock_store
    ):
        """Test that suggestions are sorted by confidence."""
        session_id = conversation_tracker.create_session()
        conversation_tracker.track_query(
            session_id,
            "authentication",
            []
        )

        # Mock results with varying scores
        mock_results = [
            create_memory_result(
            id="mem_1",
            content="low relevance",
            score=0.6,
            importance=0.5,
            last_accessed=datetime.now(UTC) - timedelta(days=100),
            ),
            create_memory_result(
            id="mem_2",
            content="high relevance authentication",
            score=0.95,
            importance=0.9,
            last_accessed=datetime.now(UTC)
            ),
            create_memory_result(
            id="mem_3",
            content="medium relevance auth",
            score=0.8,
            importance=0.7,
            last_accessed=datetime.now(UTC) - timedelta(days=30),
            ),
        ]
        mock_store.search.return_value = mock_results

        response = await suggester.suggest_memories(
            session_id=session_id,
            confidence_threshold=0.5,  # Lower threshold to include all
        )

        # Suggestions should be sorted by confidence (highest first)
        if len(response.suggestions) > 1:
            for i in range(len(response.suggestions) - 1):
                assert (
                    response.suggestions[i].confidence >=
                    response.suggestions[i + 1].confidence
                )

    @pytest.mark.asyncio
    async def test_search_error_handling(
        self, suggester, conversation_tracker, mock_store
    ):
        """Test graceful handling of search errors."""
        session_id = conversation_tracker.create_session()
        conversation_tracker.track_query(
            session_id,
            "test query",
            []
        )

        # Mock search error
        mock_store.search.side_effect = Exception("Search failed")

        response = await suggester.suggest_memories(session_id=session_id)

        # Should return empty response, not crash
        assert response.total_suggestions == 0
        assert len(response.suggestions) == 0

    @pytest.mark.asyncio
    async def test_stats_tracking(self, suggester, conversation_tracker, mock_store):
        """Test that statistics are tracked."""
        session_id = conversation_tracker.create_session()
        conversation_tracker.track_query(
            session_id,
            "authentication",
            []
        )

        mock_result = create_memory_result(
            id="mem_1",
            content="auth code",
            score=0.9,
            importance=0.8,
            last_accessed=datetime.now(UTC)
        )
        mock_store.search.return_value = [mock_result]

        initial_stats = suggester.get_stats()

        await suggester.suggest_memories(session_id=session_id)

        updated_stats = suggester.get_stats()

        # Stats should be incremented
        assert updated_stats["intent_detections"] > initial_stats["intent_detections"]
        assert updated_stats["total_candidates"] > initial_stats["total_candidates"]

    @pytest.mark.asyncio
    async def test_project_filtering(
        self, suggester, conversation_tracker, mock_store
    ):
        """Test project-specific filtering."""
        session_id = conversation_tracker.create_session()
        conversation_tracker.track_query(
            session_id,
            "authentication code",
            []
        )

        mock_store.search.return_value = []

        await suggester.suggest_memories(
            session_id=session_id,
            project_name="my-project",
        )

        # Should call search with project filter
        mock_store.search.assert_called_once()
        call_kwargs = mock_store.search.call_args.kwargs
        assert call_kwargs["filters"] is not None
        assert call_kwargs["filters"].project_name == "my-project"
