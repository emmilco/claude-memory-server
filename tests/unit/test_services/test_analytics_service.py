"""Tests for AnalyticsService - Usage analytics and pattern tracking.

This test suite covers:
- Usage statistics retrieval
- Top queries retrieval
- Frequently accessed code retrieval
- Token analytics
- Search feedback submission
- Quality metrics retrieval
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from src.services.analytics_service import AnalyticsService
from src.config import ServerConfig
from src.core.exceptions import StorageError


class TestAnalyticsServiceInit:
    """Test AnalyticsService initialization."""

    def test_initialization_with_required_dependencies(self):
        """Test service initializes with required dependencies."""
        store = MagicMock()
        config = ServerConfig()

        service = AnalyticsService(
            store=store,
            config=config,
        )

        assert service.store == store
        assert service.config == config
        assert service.usage_tracker is None
        assert service.pattern_tracker is None
        assert service.metrics_collector is None

    def test_initialization_with_all_dependencies(self):
        """Test service initializes with all dependencies."""
        store = MagicMock()
        config = ServerConfig()
        usage_tracker = MagicMock()
        pattern_tracker = MagicMock()
        metrics_collector = MagicMock()

        service = AnalyticsService(
            store=store,
            config=config,
            usage_tracker=usage_tracker,
            pattern_tracker=pattern_tracker,
            metrics_collector=metrics_collector,
        )

        assert service.usage_tracker == usage_tracker
        assert service.pattern_tracker == pattern_tracker
        assert service.metrics_collector == metrics_collector

    def test_initial_stats_are_zero(self):
        """Test service stats start at zero."""
        service = AnalyticsService(
            store=MagicMock(),
            config=ServerConfig(),
        )

        stats = service.get_stats()
        assert stats["analytics_queries"] == 0


class TestGetUsageStatistics:
    """Test get_usage_statistics method."""

    @pytest.fixture
    def service(self):
        """Create service with pattern tracker."""
        pattern_tracker = MagicMock()
        pattern_tracker.get_usage_statistics.return_value = {
            "total_queries": 1000,
            "total_memories_accessed": 5000,
            "avg_queries_per_day": 35,
        }

        return AnalyticsService(
            store=MagicMock(),
            config=ServerConfig(),
            pattern_tracker=pattern_tracker,
        )

    @pytest.mark.asyncio
    async def test_stats_without_tracker_returns_disabled(self):
        """Test statistics without tracker raises StorageError."""
        service = AnalyticsService(
            store=MagicMock(),
            config=ServerConfig(),
            pattern_tracker=None,
        )

        with pytest.raises(StorageError):
            await service.get_usage_statistics()

    @pytest.mark.asyncio
    async def test_stats_success(self, service):
        """Test successful statistics retrieval."""
        result = await service.get_usage_statistics(days=30)

        assert result["status"] == "success"
        assert "statistics" in result
        assert result["period_days"] == 30

    @pytest.mark.asyncio
    async def test_stats_custom_days(self, service):
        """Test statistics with custom days."""
        await service.get_usage_statistics(days=7)

        service.pattern_tracker.get_usage_statistics.assert_called_with(days=7)

    @pytest.mark.asyncio
    async def test_stats_increments_analytics_queries(self, service):
        """Test statistics retrieval increments analytics queries."""
        initial_stats = service.get_stats()
        await service.get_usage_statistics()

        stats = service.get_stats()
        assert stats["analytics_queries"] == initial_stats["analytics_queries"] + 1

    @pytest.mark.asyncio
    async def test_stats_error_raises(self, service):
        """Test statistics error raises StorageError."""
        service.pattern_tracker.get_usage_statistics.side_effect = Exception(
            "Stats failed"
        )

        with pytest.raises(StorageError):
            await service.get_usage_statistics()


class TestGetTopQueries:
    """Test get_top_queries method."""

    @pytest.fixture
    def service(self):
        """Create service with pattern tracker."""
        pattern_tracker = MagicMock()
        pattern_tracker.get_top_queries.return_value = [
            {"query": "authentication", "count": 150, "avg_results": 5.2},
            {"query": "database connection", "count": 120, "avg_results": 3.8},
            {"query": "error handling", "count": 95, "avg_results": 4.1},
        ]

        return AnalyticsService(
            store=MagicMock(),
            config=ServerConfig(),
            pattern_tracker=pattern_tracker,
        )

    @pytest.mark.asyncio
    async def test_queries_without_tracker_returns_disabled(self):
        """Test queries without tracker raises StorageError."""
        service = AnalyticsService(
            store=MagicMock(),
            config=ServerConfig(),
            pattern_tracker=None,
        )

        with pytest.raises(StorageError):
            await service.get_top_queries()

    @pytest.mark.asyncio
    async def test_queries_success(self, service):
        """Test successful top queries retrieval."""
        result = await service.get_top_queries(limit=10, days=30)

        assert result["status"] == "success"
        assert "queries" in result
        assert len(result["queries"]) == 3
        assert result["total_count"] == 3
        assert result["period_days"] == 30

    @pytest.mark.asyncio
    async def test_queries_with_custom_limit(self, service):
        """Test top queries with custom limit."""
        await service.get_top_queries(limit=5)

        service.pattern_tracker.get_top_queries.assert_called_with(
            limit=5,
            days=30,  # default
        )

    @pytest.mark.asyncio
    async def test_queries_increments_analytics(self, service):
        """Test queries retrieval increments analytics queries."""
        initial_stats = service.get_stats()
        await service.get_top_queries()

        stats = service.get_stats()
        assert stats["analytics_queries"] == initial_stats["analytics_queries"] + 1

    @pytest.mark.asyncio
    async def test_queries_error_raises(self, service):
        """Test queries error raises StorageError."""
        service.pattern_tracker.get_top_queries.side_effect = Exception(
            "Queries failed"
        )

        with pytest.raises(StorageError):
            await service.get_top_queries()


class TestGetFrequentlyAccessedCode:
    """Test get_frequently_accessed_code method."""

    @pytest.fixture
    def service(self):
        """Create service with pattern tracker."""
        pattern_tracker = MagicMock()
        pattern_tracker.get_frequently_accessed_code.return_value = [
            {"file_path": "/auth.py", "function": "authenticate", "access_count": 250},
            {"file_path": "/db.py", "function": "connect", "access_count": 200},
        ]

        return AnalyticsService(
            store=MagicMock(),
            config=ServerConfig(),
            pattern_tracker=pattern_tracker,
        )

    @pytest.mark.asyncio
    async def test_code_without_tracker_returns_disabled(self):
        """Test code access without tracker raises StorageError."""
        service = AnalyticsService(
            store=MagicMock(),
            config=ServerConfig(),
            pattern_tracker=None,
        )

        with pytest.raises(StorageError):
            await service.get_frequently_accessed_code()

    @pytest.mark.asyncio
    async def test_code_success(self, service):
        """Test successful code access retrieval."""
        result = await service.get_frequently_accessed_code(limit=10, days=30)

        assert result["status"] == "success"
        assert "frequently_accessed" in result
        assert len(result["frequently_accessed"]) == 2
        assert result["total_count"] == 2
        assert result["period_days"] == 30

    @pytest.mark.asyncio
    async def test_code_with_custom_params(self, service):
        """Test code access with custom parameters."""
        await service.get_frequently_accessed_code(limit=20, days=7)

        service.pattern_tracker.get_frequently_accessed_code.assert_called_with(
            limit=20,
            days=7,
        )

    @pytest.mark.asyncio
    async def test_code_increments_analytics(self, service):
        """Test code access increments analytics queries."""
        initial_stats = service.get_stats()
        await service.get_frequently_accessed_code()

        stats = service.get_stats()
        assert stats["analytics_queries"] == initial_stats["analytics_queries"] + 1

    @pytest.mark.asyncio
    async def test_code_error_raises(self, service):
        """Test code access error raises StorageError."""
        service.pattern_tracker.get_frequently_accessed_code.side_effect = Exception(
            "Code failed"
        )

        with pytest.raises(StorageError):
            await service.get_frequently_accessed_code()


class TestGetTokenAnalytics:
    """Test get_token_analytics method."""

    @pytest.fixture
    def service(self):
        """Create service with usage tracker."""
        usage_tracker = AsyncMock()
        usage_tracker.get_token_analytics = AsyncMock(
            return_value={
                "total_tokens_saved": 50000,
                "cost_savings_usd": 2.50,
                "sessions_analyzed": 100,
            }
        )

        return AnalyticsService(
            store=MagicMock(),
            config=ServerConfig(),
            usage_tracker=usage_tracker,
        )

    @pytest.mark.asyncio
    async def test_token_analytics_without_tracker_returns_disabled(self):
        """Test token analytics without tracker raises StorageError."""
        service = AnalyticsService(
            store=MagicMock(),
            config=ServerConfig(),
            usage_tracker=None,
        )

        with pytest.raises(StorageError):
            await service.get_token_analytics()

    @pytest.mark.asyncio
    async def test_token_analytics_success(self, service):
        """Test successful token analytics retrieval."""
        result = await service.get_token_analytics(period_days=30)

        assert result["status"] == "success"
        assert "analytics" in result
        assert result["period_days"] == 30

    @pytest.mark.asyncio
    async def test_token_analytics_with_filters(self, service):
        """Test token analytics with session and project filters."""
        await service.get_token_analytics(
            period_days=7,
            session_id="session_123",
            project_name="test-project",
        )

        service.usage_tracker.get_token_analytics.assert_called_with(
            period_days=7,
            session_id="session_123",
            project_name="test-project",
        )

    @pytest.mark.asyncio
    async def test_token_analytics_increments_queries(self, service):
        """Test token analytics increments analytics queries."""
        initial_stats = service.get_stats()
        await service.get_token_analytics()

        stats = service.get_stats()
        assert stats["analytics_queries"] == initial_stats["analytics_queries"] + 1

    @pytest.mark.asyncio
    async def test_token_analytics_error_raises(self, service):
        """Test token analytics error raises StorageError."""
        service.usage_tracker.get_token_analytics = AsyncMock(
            side_effect=Exception("Token analytics failed")
        )

        with pytest.raises(StorageError):
            await service.get_token_analytics()


class TestSubmitSearchFeedback:
    """Test submit_search_feedback method."""

    @pytest.fixture
    def service(self):
        """Create service for feedback tests."""
        store = AsyncMock()
        store.submit_search_feedback = AsyncMock(return_value="feedback_123")

        return AnalyticsService(
            store=store,
            config=ServerConfig(),
        )

    @pytest.mark.asyncio
    async def test_submit_feedback_success(self, service):
        """Test successful feedback submission."""
        result = await service.submit_search_feedback(
            search_id="search_456",
            query="authentication",
            result_ids=["mem_1", "mem_2"],
            rating="helpful",
            comment="Very relevant results",
            project_name="test-project",
        )

        assert result["status"] == "success"
        assert result["feedback_id"] == "feedback_123"
        assert result["search_id"] == "search_456"
        assert result["rating"] == "helpful"

    @pytest.mark.asyncio
    async def test_submit_feedback_not_helpful(self, service):
        """Test feedback submission with not_helpful rating."""
        result = await service.submit_search_feedback(
            search_id="search_789",
            query="test",
            result_ids=["mem_1"],
            rating="not_helpful",
        )

        assert result["status"] == "success"
        assert result["rating"] == "not_helpful"

    @pytest.mark.asyncio
    async def test_submit_feedback_minimal(self, service):
        """Test feedback submission with minimal parameters."""
        result = await service.submit_search_feedback(
            search_id="search_123",
            query="test",
            result_ids=[],
            rating="helpful",
        )

        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_submit_feedback_error_raises(self, service):
        """Test feedback submission error raises StorageError."""
        service.store.submit_search_feedback = AsyncMock(
            side_effect=Exception("Feedback failed")
        )

        with pytest.raises(StorageError):
            await service.submit_search_feedback(
                search_id="search_123",
                query="test",
                result_ids=[],
                rating="helpful",
            )


class TestGetQualityMetrics:
    """Test get_quality_metrics method."""

    @pytest.fixture
    def service(self):
        """Create service for quality metrics tests."""
        store = AsyncMock()
        store.get_quality_metrics = AsyncMock(
            return_value={
                "total_searches": 500,
                "helpful_count": 400,
                "not_helpful_count": 100,
                "helpfulness_rate": 0.8,
                "avg_results_per_search": 4.2,
            }
        )

        return AnalyticsService(
            store=store,
            config=ServerConfig(),
        )

    @pytest.mark.asyncio
    async def test_quality_metrics_success(self, service):
        """Test successful quality metrics retrieval."""
        result = await service.get_quality_metrics(time_range_hours=24)

        assert result["status"] == "success"
        assert "metrics" in result
        assert result["metrics"]["total_searches"] == 500

    @pytest.mark.asyncio
    async def test_quality_metrics_with_project(self, service):
        """Test quality metrics with project filter."""
        await service.get_quality_metrics(
            time_range_hours=48,
            project_name="test-project",
        )

        service.store.get_quality_metrics.assert_called_with(
            time_range_hours=48,
            project_name="test-project",
        )

    @pytest.mark.asyncio
    async def test_quality_metrics_error_raises(self, service):
        """Test quality metrics error raises StorageError."""
        service.store.get_quality_metrics = AsyncMock(
            side_effect=Exception("Metrics failed")
        )

        with pytest.raises(StorageError):
            await service.get_quality_metrics()


class TestStatisticsAccumulation:
    """Test that analytics_queries stat accumulates correctly."""

    @pytest.fixture
    def service(self):
        """Create fully configured service."""
        pattern_tracker = MagicMock()
        pattern_tracker.get_usage_statistics.return_value = {}
        pattern_tracker.get_top_queries.return_value = []
        pattern_tracker.get_frequently_accessed_code.return_value = []

        usage_tracker = AsyncMock()
        usage_tracker.get_token_analytics = AsyncMock(return_value={})

        return AnalyticsService(
            store=MagicMock(),
            config=ServerConfig(),
            pattern_tracker=pattern_tracker,
            usage_tracker=usage_tracker,
        )

    @pytest.mark.asyncio
    async def test_stats_accumulate(self, service):
        """Test analytics queries accumulate across operations."""
        # Call multiple analytics methods
        await service.get_usage_statistics()
        await service.get_top_queries()
        await service.get_frequently_accessed_code()
        await service.get_token_analytics()

        stats = service.get_stats()
        assert stats["analytics_queries"] == 4

    @pytest.mark.asyncio
    async def test_stats_independent_copy(self, service):
        """Test get_stats returns independent copy."""
        stats1 = service.get_stats()
        await service.get_usage_statistics()
        stats2 = service.get_stats()

        # Modifying stats1 should not affect service
        stats1["analytics_queries"] = 100

        assert stats2["analytics_queries"] == 1
        assert service.get_stats()["analytics_queries"] == 1


class TestIntegrationScenarios:
    """Test integration scenarios for analytics service."""

    @pytest.fixture
    def fully_configured_service(self):
        """Create fully configured service for integration tests."""
        pattern_tracker = MagicMock()
        pattern_tracker.get_usage_statistics.return_value = {
            "total_queries": 1000,
        }
        pattern_tracker.get_top_queries.return_value = [
            {"query": "test", "count": 100},
        ]
        pattern_tracker.get_frequently_accessed_code.return_value = [
            {"file_path": "/test.py", "count": 50},
        ]

        usage_tracker = AsyncMock()
        usage_tracker.get_token_analytics = AsyncMock(
            return_value={
                "tokens_saved": 5000,
            }
        )

        store = AsyncMock()
        store.submit_search_feedback = AsyncMock(return_value="fb_123")
        store.get_quality_metrics = AsyncMock(
            return_value={
                "helpfulness_rate": 0.85,
            }
        )

        return AnalyticsService(
            store=store,
            config=ServerConfig(),
            pattern_tracker=pattern_tracker,
            usage_tracker=usage_tracker,
        )

    @pytest.mark.asyncio
    async def test_full_analytics_workflow(self, fully_configured_service):
        """Test complete analytics workflow."""
        service = fully_configured_service

        # Get usage overview
        usage = await service.get_usage_statistics(days=30)
        assert usage["status"] == "success"

        # Get top queries
        queries = await service.get_top_queries(limit=10)
        assert queries["status"] == "success"

        # Get frequently accessed code
        code = await service.get_frequently_accessed_code(limit=10)
        assert code["status"] == "success"

        # Get token analytics
        tokens = await service.get_token_analytics(period_days=30)
        assert tokens["status"] == "success"

        # Submit feedback
        feedback = await service.submit_search_feedback(
            search_id="s1",
            query="test",
            result_ids=["m1"],
            rating="helpful",
        )
        assert feedback["status"] == "success"

        # Get quality metrics
        quality = await service.get_quality_metrics()
        assert quality["status"] == "success"

        # Verify stats accumulated
        stats = service.get_stats()
        assert stats["analytics_queries"] == 4  # 4 analytics queries made


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.fixture
    def service(self):
        """Create service for edge case tests."""
        pattern_tracker = MagicMock()
        pattern_tracker.get_usage_statistics.return_value = {}
        pattern_tracker.get_top_queries.return_value = []
        pattern_tracker.get_frequently_accessed_code.return_value = []

        return AnalyticsService(
            store=MagicMock(),
            config=ServerConfig(),
            pattern_tracker=pattern_tracker,
        )

    @pytest.mark.asyncio
    async def test_zero_days_statistics(self, service):
        """Test statistics with zero days."""
        await service.get_usage_statistics(days=0)

        service.pattern_tracker.get_usage_statistics.assert_called_with(days=0)

    @pytest.mark.asyncio
    async def test_large_days_value(self, service):
        """Test statistics with large days value."""
        await service.get_usage_statistics(days=365)

        service.pattern_tracker.get_usage_statistics.assert_called_with(days=365)

    @pytest.mark.asyncio
    async def test_zero_limit_queries(self, service):
        """Test queries with zero limit."""
        await service.get_top_queries(limit=0)

        service.pattern_tracker.get_top_queries.assert_called_with(
            limit=0,
            days=30,
        )

    @pytest.mark.asyncio
    async def test_empty_result_ids_feedback(self):
        """Test feedback with empty result IDs."""
        store = AsyncMock()
        store.submit_search_feedback = AsyncMock(return_value="fb_123")

        service = AnalyticsService(
            store=store,
            config=ServerConfig(),
        )

        result = await service.submit_search_feedback(
            search_id="s1",
            query="test",
            result_ids=[],
            rating="helpful",
        )

        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_special_characters_in_query(self):
        """Test feedback with special characters in query."""
        store = AsyncMock()
        store.submit_search_feedback = AsyncMock(return_value="fb_123")

        service = AnalyticsService(
            store=store,
            config=ServerConfig(),
        )

        result = await service.submit_search_feedback(
            search_id="s1",
            query="test query with 'quotes' and \"double quotes\" and <brackets>",
            result_ids=["m1"],
            rating="helpful",
        )

        assert result["status"] == "success"


class TestDefaultParameterValues:
    """Test default parameter values are applied correctly."""

    @pytest.fixture
    def service(self):
        """Create service with mocked trackers."""
        pattern_tracker = MagicMock()
        pattern_tracker.get_usage_statistics.return_value = {}
        pattern_tracker.get_top_queries.return_value = []
        pattern_tracker.get_frequently_accessed_code.return_value = []

        return AnalyticsService(
            store=MagicMock(),
            config=ServerConfig(),
            pattern_tracker=pattern_tracker,
        )

    @pytest.mark.asyncio
    async def test_usage_stats_default_days(self, service):
        """Test usage statistics uses default days."""
        await service.get_usage_statistics()

        service.pattern_tracker.get_usage_statistics.assert_called_with(days=30)

    @pytest.mark.asyncio
    async def test_top_queries_default_params(self, service):
        """Test top queries uses default parameters."""
        await service.get_top_queries()

        service.pattern_tracker.get_top_queries.assert_called_with(
            limit=10,
            days=30,
        )

    @pytest.mark.asyncio
    async def test_frequently_accessed_default_params(self, service):
        """Test frequently accessed uses default parameters."""
        await service.get_frequently_accessed_code()

        service.pattern_tracker.get_frequently_accessed_code.assert_called_with(
            limit=10,
            days=30,
        )
