"""Comprehensive unit tests for SpecializedRetrievalTools."""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock
from src.core.tools import SpecializedRetrievalTools
from src.core.models import (
    ContextLevel,
    MemoryScope,
    MemoryCategory,
    MemoryUnit,
    SearchFilters,
)


@pytest.fixture
def mock_store():
    """Create a mock memory store."""
    store = AsyncMock()
    return store


@pytest.fixture
def mock_embedding_generator():
    """Create a mock embedding generator."""
    generator = AsyncMock()
    generator.generate.return_value = [0.1] * 384  # Mock 384-dim embedding
    return generator


@pytest.fixture
def tools(mock_store, mock_embedding_generator):
    """Create SpecializedRetrievalTools instance."""
    return SpecializedRetrievalTools(
        store=mock_store,
        embedding_generator=mock_embedding_generator
    )


@pytest.fixture
def sample_memory():
    """Create a sample memory unit."""
    return MemoryUnit(
        content="Test content",
        category=MemoryCategory.PREFERENCE,
        context_level=ContextLevel.USER_PREFERENCE,
        scope=MemoryScope.GLOBAL,
        importance=0.8,
        tags=["test"],
    )


class TestRetrievePreferences:
    """Test retrieve_preferences method."""

    @pytest.mark.asyncio
    async def test_retrieve_preferences_basic(self, tools, mock_store, mock_embedding_generator, sample_memory):
        """Test basic preference retrieval."""
        # Setup mock response
        mock_store.search_with_filters.return_value = [
            (sample_memory, 0.95),
        ]

        # Call method
        results = await tools.retrieve_preferences(
            query="coding style",
            limit=5
        )

        # Verify embedding was generated
        mock_embedding_generator.generate.assert_called_once_with("coding style")

        # Verify search was called with correct filters
        call_args = mock_store.search_with_filters.call_args
        assert call_args[1]["limit"] == 5
        filters = call_args[1]["filters"]
        assert filters.context_level == ContextLevel.USER_PREFERENCE

        # Verify results
        assert len(results) == 1
        assert results[0].memory == sample_memory
        assert results[0].score == 0.95

    @pytest.mark.asyncio
    async def test_retrieve_preferences_with_scope(self, tools, mock_store):
        """Test preference retrieval with scope filter."""
        mock_store.search_with_filters.return_value = []

        await tools.retrieve_preferences(
            query="test",
            scope=MemoryScope.GLOBAL,
            limit=10
        )

        # Verify scope was passed in filters
        call_args = mock_store.search_with_filters.call_args
        filters = call_args[1]["filters"]
        assert filters.scope == MemoryScope.GLOBAL

    @pytest.mark.asyncio
    async def test_retrieve_preferences_with_project_name(self, tools, mock_store):
        """Test preference retrieval with project name filter."""
        mock_store.search_with_filters.return_value = []

        await tools.retrieve_preferences(
            query="test",
            project_name="my-project",
            limit=5
        )

        # Verify project_name was passed in filters
        call_args = mock_store.search_with_filters.call_args
        filters = call_args[1]["filters"]
        assert filters.project_name == "my-project"

    @pytest.mark.asyncio
    async def test_retrieve_preferences_with_importance(self, tools, mock_store):
        """Test preference retrieval with minimum importance filter."""
        mock_store.search_with_filters.return_value = []

        await tools.retrieve_preferences(
            query="test",
            min_importance=0.7,
            limit=5
        )

        # Verify min_importance was passed in filters
        call_args = mock_store.search_with_filters.call_args
        filters = call_args[1]["filters"]
        assert filters.min_importance == 0.7

    @pytest.mark.asyncio
    async def test_retrieve_preferences_empty_results(self, tools, mock_store):
        """Test preference retrieval with no results."""
        mock_store.search_with_filters.return_value = []

        results = await tools.retrieve_preferences(
            query="nonexistent preference",
            limit=5
        )

        assert len(results) == 0


class TestRetrieveProjectContext:
    """Test retrieve_project_context method."""

    @pytest.mark.asyncio
    async def test_retrieve_project_context_basic(self, tools, mock_store, mock_embedding_generator, sample_memory):
        """Test basic project context retrieval."""
        # Update sample memory to project context
        sample_memory.context_level = ContextLevel.PROJECT_CONTEXT
        sample_memory.category = MemoryCategory.CONTEXT

        mock_store.search_with_filters.return_value = [
            (sample_memory, 0.88),
        ]

        results = await tools.retrieve_project_context(
            query="database setup",
            limit=3
        )

        # Verify embedding was generated
        mock_embedding_generator.generate.assert_called_once_with("database setup")

        # Verify search was called with correct filters
        call_args = mock_store.search_with_filters.call_args
        filters = call_args[1]["filters"]
        assert filters.context_level == ContextLevel.PROJECT_CONTEXT

        # Verify results
        assert len(results) == 1
        assert results[0].score == 0.88

    @pytest.mark.asyncio
    async def test_retrieve_project_context_with_category(self, tools, mock_store):
        """Test project context retrieval with category filter."""
        mock_store.search_with_filters.return_value = []

        await tools.retrieve_project_context(
            query="test",
            category=MemoryCategory.CONTEXT,
            limit=5
        )

        # Verify category was passed in filters
        call_args = mock_store.search_with_filters.call_args
        filters = call_args[1]["filters"]
        assert filters.category == MemoryCategory.CONTEXT

    @pytest.mark.asyncio
    async def test_retrieve_project_context_with_project_name(self, tools, mock_store):
        """Test project context retrieval with specific project."""
        mock_store.search_with_filters.return_value = []

        await tools.retrieve_project_context(
            query="test",
            project_name="specific-project",
            limit=5
        )

        call_args = mock_store.search_with_filters.call_args
        filters = call_args[1]["filters"]
        assert filters.project_name == "specific-project"


class TestRetrieveSessionState:
    """Test retrieve_session_state method."""

    @pytest.mark.asyncio
    async def test_retrieve_session_state_basic(self, tools, mock_store, mock_embedding_generator, sample_memory):
        """Test basic session state retrieval."""
        # Update sample memory to session state
        sample_memory.context_level = ContextLevel.SESSION_STATE

        mock_store.search_with_filters.return_value = [
            (sample_memory, 0.92),
        ]

        results = await tools.retrieve_session_state(
            query="current work",
            limit=5
        )

        # Verify embedding was generated
        mock_embedding_generator.generate.assert_called_once_with("current work")

        # Verify search was called with correct filters
        call_args = mock_store.search_with_filters.call_args
        filters = call_args[1]["filters"]
        assert filters.context_level == ContextLevel.SESSION_STATE

        # Verify results
        assert len(results) == 1
        assert results[0].score == 0.92

    @pytest.mark.asyncio
    async def test_retrieve_session_state_with_project(self, tools, mock_store):
        """Test session state retrieval with project filter."""
        mock_store.search_with_filters.return_value = []

        await tools.retrieve_session_state(
            query="test",
            project_name="my-project",
            limit=5
        )

        call_args = mock_store.search_with_filters.call_args
        filters = call_args[1]["filters"]
        assert filters.project_name == "my-project"

    @pytest.mark.asyncio
    async def test_retrieve_session_state_with_importance(self, tools, mock_store):
        """Test session state retrieval with importance filter."""
        mock_store.search_with_filters.return_value = []

        await tools.retrieve_session_state(
            query="test",
            min_importance=0.5,
            limit=5
        )

        call_args = mock_store.search_with_filters.call_args
        filters = call_args[1]["filters"]
        assert filters.min_importance == 0.5


class TestRetrieveByCategory:
    """Test retrieve_by_category method."""

    @pytest.mark.asyncio
    async def test_retrieve_by_category_workflow(self, tools, mock_store, mock_embedding_generator, sample_memory):
        """Test category-based retrieval for workflows."""
        sample_memory.category = MemoryCategory.WORKFLOW

        mock_store.search_with_filters.return_value = [
            (sample_memory, 0.9),
        ]

        results = await tools.retrieve_by_category(
            query="deployment process",
            category=MemoryCategory.WORKFLOW,
            limit=5
        )

        # Verify search was called with category filter
        call_args = mock_store.search_with_filters.call_args
        filters = call_args[1]["filters"]
        assert filters.category == MemoryCategory.WORKFLOW

        # Verify results
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_retrieve_by_category_with_context_level(self, tools, mock_store):
        """Test category retrieval with context level filter."""
        mock_store.search_with_filters.return_value = []

        await tools.retrieve_by_category(
            query="test",
            category=MemoryCategory.FACT,
            context_level=ContextLevel.PROJECT_CONTEXT,
            limit=5
        )

        call_args = mock_store.search_with_filters.call_args
        filters = call_args[1]["filters"]
        assert filters.category == MemoryCategory.FACT
        assert filters.context_level == ContextLevel.PROJECT_CONTEXT

    @pytest.mark.asyncio
    async def test_retrieve_by_category_with_project(self, tools, mock_store):
        """Test category retrieval with project filter."""
        mock_store.search_with_filters.return_value = []

        await tools.retrieve_by_category(
            query="test",
            category=MemoryCategory.EVENT,
            project_name="test-project",
            limit=5
        )

        call_args = mock_store.search_with_filters.call_args
        filters = call_args[1]["filters"]
        assert filters.category == MemoryCategory.EVENT
        assert filters.project_name == "test-project"


class TestRetrieveMultiLevel:
    """Test retrieve_multi_level method."""

    @pytest.mark.asyncio
    async def test_retrieve_multi_level_two_levels(self, tools, mock_store, mock_embedding_generator, sample_memory):
        """Test retrieval from multiple context levels."""
        # Setup different memories for different levels
        pref_memory = MemoryUnit(
            content="Preference content",
            category=MemoryCategory.PREFERENCE,
            context_level=ContextLevel.USER_PREFERENCE,
            scope=MemoryScope.GLOBAL,
        )

        project_memory = MemoryUnit(
            content="Project content",
            category=MemoryCategory.CONTEXT,
            context_level=ContextLevel.PROJECT_CONTEXT,
            scope=MemoryScope.PROJECT,
            project_name="test-project",
        )

        # Mock store to return different results for different context levels
        def search_side_effect(query_embedding, filters, limit):
            if filters.context_level == ContextLevel.USER_PREFERENCE:
                return [(pref_memory, 0.9)]
            elif filters.context_level == ContextLevel.PROJECT_CONTEXT:
                return [(project_memory, 0.85)]
            return []

        mock_store.search_with_filters.side_effect = search_side_effect

        # Call method
        results = await tools.retrieve_multi_level(
            query="python coding",
            context_levels=[
                ContextLevel.USER_PREFERENCE,
                ContextLevel.PROJECT_CONTEXT
            ],
            limit=5
        )

        # Verify embedding generated once
        mock_embedding_generator.generate.assert_called_once_with("python coding")

        # Verify search called twice (once per level)
        assert mock_store.search_with_filters.call_count == 2

        # Verify results structure
        assert ContextLevel.USER_PREFERENCE in results
        assert ContextLevel.PROJECT_CONTEXT in results
        assert len(results[ContextLevel.USER_PREFERENCE]) == 1
        assert len(results[ContextLevel.PROJECT_CONTEXT]) == 1
        assert results[ContextLevel.USER_PREFERENCE][0].memory == pref_memory
        assert results[ContextLevel.PROJECT_CONTEXT][0].memory == project_memory

    @pytest.mark.asyncio
    async def test_retrieve_multi_level_with_project(self, tools, mock_store):
        """Test multi-level retrieval with project filter."""
        mock_store.search_with_filters.return_value = []

        await tools.retrieve_multi_level(
            query="test",
            context_levels=[ContextLevel.USER_PREFERENCE],
            project_name="my-project",
            limit=10
        )

        # Verify project_name was passed in filters
        call_args = mock_store.search_with_filters.call_args
        filters = call_args[1]["filters"]
        assert filters.project_name == "my-project"

    @pytest.mark.asyncio
    async def test_retrieve_multi_level_all_three_levels(self, tools, mock_store, mock_embedding_generator):
        """Test retrieval from all three context levels."""
        mock_store.search_with_filters.return_value = []

        results = await tools.retrieve_multi_level(
            query="comprehensive search",
            context_levels=[
                ContextLevel.USER_PREFERENCE,
                ContextLevel.PROJECT_CONTEXT,
                ContextLevel.SESSION_STATE
            ],
            limit=10
        )

        # Verify search called three times
        assert mock_store.search_with_filters.call_count == 3

        # Verify all three levels in results
        assert len(results) == 3
        assert ContextLevel.USER_PREFERENCE in results
        assert ContextLevel.PROJECT_CONTEXT in results
        assert ContextLevel.SESSION_STATE in results

    @pytest.mark.asyncio
    async def test_retrieve_multi_level_empty_results(self, tools, mock_store):
        """Test multi-level retrieval with no results."""
        mock_store.search_with_filters.return_value = []

        results = await tools.retrieve_multi_level(
            query="nonexistent",
            context_levels=[ContextLevel.USER_PREFERENCE],
            limit=5
        )

        assert ContextLevel.USER_PREFERENCE in results
        assert len(results[ContextLevel.USER_PREFERENCE]) == 0

    @pytest.mark.asyncio
    async def test_retrieve_multi_level_respects_limit(self, tools, mock_store, sample_memory):
        """Test that multi-level retrieval respects the limit parameter."""
        # Create multiple mock results
        mock_results = [(sample_memory, 0.9) for _ in range(10)]
        mock_store.search_with_filters.return_value = mock_results

        await tools.retrieve_multi_level(
            query="test",
            context_levels=[ContextLevel.USER_PREFERENCE],
            limit=3  # Should only request 3 per level
        )

        # Verify limit was passed correctly
        call_args = mock_store.search_with_filters.call_args
        assert call_args[1]["limit"] == 3
