"""Tests for inline confidence score display (UX-030)."""

import pytest
import pytest_asyncio
import uuid
from unittest.mock import AsyncMock, Mock, patch
from src.core.server import MemoryRAGServer
from src.core.models import MemoryUnit, ContextLevel, MemoryCategory, MemoryScope
from src.config import ServerConfig


class TestConfidenceLabels:
    """Test the _get_confidence_label helper method."""

    def test_excellent_confidence_above_0_8(self):
        """Test that scores > 0.8 return 'excellent'."""
        assert MemoryRAGServer._get_confidence_label(0.85) == "excellent"
        assert MemoryRAGServer._get_confidence_label(0.9) == "excellent"
        assert MemoryRAGServer._get_confidence_label(0.95) == "excellent"
        assert MemoryRAGServer._get_confidence_label(1.0) == "excellent"

    def test_excellent_confidence_at_boundary(self):
        """Test that scores at 0.8001 return 'excellent'."""
        assert MemoryRAGServer._get_confidence_label(0.8001) == "excellent"

    def test_good_confidence_range(self):
        """Test that scores between 0.6 and 0.8 return 'good'."""
        assert MemoryRAGServer._get_confidence_label(0.6) == "good"
        assert MemoryRAGServer._get_confidence_label(0.65) == "good"
        assert MemoryRAGServer._get_confidence_label(0.7) == "good"
        assert MemoryRAGServer._get_confidence_label(0.75) == "good"
        assert MemoryRAGServer._get_confidence_label(0.8) == "good"

    def test_weak_confidence_below_0_6(self):
        """Test that scores < 0.6 return 'weak'."""
        assert MemoryRAGServer._get_confidence_label(0.0) == "weak"
        assert MemoryRAGServer._get_confidence_label(0.1) == "weak"
        assert MemoryRAGServer._get_confidence_label(0.3) == "weak"
        assert MemoryRAGServer._get_confidence_label(0.5) == "weak"
        assert MemoryRAGServer._get_confidence_label(0.59) == "weak"


@pytest_asyncio.fixture
async def mock_server():
    """Create a mock server with mocked dependencies and unique collection."""
    config = ServerConfig(
        storage_backend="qdrant",
        qdrant_url="http://localhost:6333",
        qdrant_collection_name=f"test_conf_{uuid.uuid4().hex[:8]}",
        read_only_mode=False,
        enable_retrieval_gate=False,
    )

    server = MemoryRAGServer(config)

    # Mock all dependencies directly without calling initialize()
    server.store = AsyncMock()
    server.embedding_generator = AsyncMock()
    server.embedding_cache = AsyncMock()
    server.usage_tracker = AsyncMock()
    server.pruner = AsyncMock()
    server.conversation_tracker = AsyncMock()
    server.query_expander = AsyncMock()
    server.hybrid_searcher = None
    server.metrics_collector = AsyncMock()

    # Mock cache to return None (cache miss)
    server.embedding_cache.get = AsyncMock(return_value=None)

    # Set initialized flag
    server._initialized = True

    yield server


@pytest.mark.asyncio
class TestSearchCodeConfidenceDisplay:
    """Test that search_code includes confidence labels in results."""

    async def test_search_code_includes_confidence_fields(self, mock_server):
        """Test that search results include confidence_label and confidence_display."""
        # Mock the store to return a result with a specific score
        mock_memory = MemoryUnit(
            id="test-1",
            content="def authenticate(user, password):\n    return verify_credentials(user, password)",
            scope=MemoryScope.PROJECT,
            project_name="test-project",
            category=MemoryCategory.CONTEXT,
            context_level=ContextLevel.PROJECT_CONTEXT,
            tags=["code"],
            metadata={
                "file_path": "auth/login.py",
                "start_line": 45,
                "end_line": 47,
                "unit_name": "authenticate",
                "unit_type": "function",
                "signature": "def authenticate(user, password)",
                "language": "python",
            },
        )

        mock_server.store.retrieve = AsyncMock(return_value=[
            (mock_memory, 0.92),  # Excellent score
        ])

        mock_server.embedding_generator.generate = AsyncMock(return_value=[0.1] * 384)

        # Execute search
        result = await mock_server.search_code(query="authentication logic", limit=5)

        # Verify results include confidence fields
        assert "results" in result
        assert len(result["results"]) == 1

        code_result = result["results"][0]
        assert "relevance_score" in code_result
        assert "confidence_label" in code_result
        assert "confidence_display" in code_result

        # Verify values
        assert code_result["relevance_score"] == 0.92
        assert code_result["confidence_label"] == "excellent"
        assert code_result["confidence_display"] == "92% (excellent)"

    async def test_search_code_good_confidence(self, mock_server):
        """Test that 'good' confidence is labeled correctly."""
        mock_memory = MemoryUnit(
            id="test-2",
            content="def login():\n    pass",
            scope=MemoryScope.PROJECT,
            project_name="test-project",
            category=MemoryCategory.CONTEXT,
            context_level=ContextLevel.PROJECT_CONTEXT,
            tags=["code"],
            metadata={
                "file_path": "auth/views.py",
                "start_line": 10,
                "end_line": 12,
                "unit_name": "login",
                "unit_type": "function",
                "language": "python",
            },
        )

        mock_server.store.retrieve = AsyncMock(return_value=[
            (mock_memory, 0.72),  # Good score
        ])

        mock_server.embedding_generator.generate = AsyncMock(return_value=[0.1] * 384)

        result = await mock_server.search_code(query="login function", limit=5)

        code_result = result["results"][0]
        assert code_result["relevance_score"] == 0.72
        assert code_result["confidence_label"] == "good"
        assert code_result["confidence_display"] == "72% (good)"

    async def test_search_code_weak_confidence(self, mock_server):
        """Test that 'weak' confidence is labeled correctly."""
        mock_memory = MemoryUnit(
            id="test-3",
            content="def process_data():\n    pass",
            scope=MemoryScope.PROJECT,
            project_name="test-project",
            category=MemoryCategory.CONTEXT,
            context_level=ContextLevel.PROJECT_CONTEXT,
            tags=["code"],
            metadata={
                "file_path": "utils/helpers.py",
                "start_line": 20,
                "end_line": 22,
                "unit_name": "process_data",
                "unit_type": "function",
                "language": "python",
            },
        )

        mock_server.store.retrieve = AsyncMock(return_value=[
            (mock_memory, 0.45),  # Weak score
        ])

        mock_server.embedding_generator.generate = AsyncMock(return_value=[0.1] * 384)

        result = await mock_server.search_code(query="authentication", limit=5)

        code_result = result["results"][0]
        assert code_result["relevance_score"] == 0.45
        assert code_result["confidence_label"] == "weak"
        assert code_result["confidence_display"] == "45% (weak)"

    async def test_search_code_multiple_results_different_confidences(self, mock_server):
        """Test multiple results with different confidence levels."""
        mock_memories = [
            MemoryUnit(
                id=f"test-{i}",
                content=f"def func{i}():\n    pass",
                scope=MemoryScope.PROJECT,
                project_name="test-project",
                category=MemoryCategory.CONTEXT,
                context_level=ContextLevel.PROJECT_CONTEXT,
                tags=["code"],
                metadata={
                    "file_path": f"module{i}.py",
                    "start_line": i * 10,
                    "end_line": i * 10 + 2,
                    "unit_name": f"func{i}",
                    "unit_type": "function",
                    "language": "python",
                },
            )
            for i in range(3)
        ]

        scores = [0.95, 0.70, 0.50]  # excellent, good, weak

        mock_server.store.retrieve = AsyncMock(return_value=[
            (mock_memories[i], scores[i]) for i in range(3)
        ])

        mock_server.embedding_generator.generate = AsyncMock(return_value=[0.1] * 384)

        result = await mock_server.search_code(query="test query", limit=5)

        assert len(result["results"]) == 3

        # Verify first result (excellent)
        assert result["results"][0]["confidence_label"] == "excellent"
        assert result["results"][0]["confidence_display"] == "95% (excellent)"

        # Verify second result (good)
        assert result["results"][1]["confidence_label"] == "good"
        assert result["results"][1]["confidence_display"] == "70% (good)"

        # Verify third result (weak)
        assert result["results"][2]["confidence_label"] == "weak"
        assert result["results"][2]["confidence_display"] == "50% (weak)"


@pytest.mark.asyncio
class TestFindSimilarCodeConfidenceDisplay:
    """Test that find_similar_code includes confidence labels in results."""

    async def test_find_similar_code_includes_confidence_fields(self, mock_server):
        """Test that find_similar_code results include confidence fields."""
        mock_memory = MemoryUnit(
            id="similar-1",
            content="def authenticate(user, password):\n    return check_password(user, password)",
            scope=MemoryScope.PROJECT,
            project_name="test-project",
            category=MemoryCategory.CONTEXT,
            context_level=ContextLevel.PROJECT_CONTEXT,
            tags=["code"],
            metadata={
                "file_path": "auth/verify.py",
                "start_line": 100,
                "end_line": 102,
                "unit_name": "authenticate",
                "unit_type": "function",
                "language": "python",
            },
        )

        mock_server.store.retrieve = AsyncMock(return_value=[
            (mock_memory, 0.88),  # Excellent similarity
        ])

        mock_server.embedding_generator.generate = AsyncMock(return_value=[0.1] * 384)

        code_snippet = "def auth(u, p):\n    return verify(u, p)"
        result = await mock_server.find_similar_code(code_snippet=code_snippet, limit=10)

        assert "results" in result
        assert len(result["results"]) == 1

        code_result = result["results"][0]
        assert "similarity_score" in code_result
        assert "confidence_label" in code_result
        assert "confidence_display" in code_result

        # Verify values
        assert code_result["similarity_score"] == 0.88
        assert code_result["confidence_label"] == "excellent"
        assert code_result["confidence_display"] == "88% (excellent)"

    async def test_find_similar_code_boundary_scores(self, mock_server):
        """Test boundary scores in find_similar_code."""
        mock_memories = [
            MemoryUnit(
                id=f"boundary-{i}",
                content=f"def func{i}():\n    pass",
                scope=MemoryScope.PROJECT,
                project_name="test-project",
                category=MemoryCategory.CONTEXT,
                context_level=ContextLevel.PROJECT_CONTEXT,
                tags=["code"],
                metadata={
                    "file_path": f"file{i}.py",
                    "start_line": i,
                    "end_line": i + 2,
                    "unit_name": f"func{i}",
                    "unit_type": "function",
                    "language": "python",
                },
            )
            for i in range(3)
        ]

        # Test boundary scores: 0.81 (excellent), 0.8 (good), 0.6 (good)
        scores = [0.81, 0.8, 0.6]

        mock_server.store.retrieve = AsyncMock(return_value=[
            (mock_memories[i], scores[i]) for i in range(3)
        ])

        mock_server.embedding_generator.generate = AsyncMock(return_value=[0.1] * 384)

        code_snippet = "def test():\n    pass"
        result = await mock_server.find_similar_code(code_snippet=code_snippet, limit=10)

        assert len(result["results"]) == 3

        # 0.81 should be excellent
        assert result["results"][0]["similarity_score"] == 0.81
        assert result["results"][0]["confidence_label"] == "excellent"

        # 0.8 should be good
        assert result["results"][1]["similarity_score"] == 0.8
        assert result["results"][1]["confidence_label"] == "good"

        # 0.6 should be good
        assert result["results"][2]["similarity_score"] == 0.6
        assert result["results"][2]["confidence_label"] == "good"
