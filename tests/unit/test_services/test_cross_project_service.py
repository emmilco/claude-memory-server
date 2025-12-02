"""Tests for CrossProjectService - Multi-project search and consent management.

This test suite covers:
- Cross-project search across opted-in projects
- Project opt-in consent management
- Project opt-out consent management
- Listing opted-in projects
- Error handling when consent manager not configured
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.services.cross_project_service import CrossProjectService
from src.config import ServerConfig
from src.core.exceptions import RetrievalError
from tests.conftest import mock_embedding


class TestCrossProjectServiceInit:
    """Test CrossProjectService initialization."""

    def test_initialization_with_required_dependencies(self):
        """Test service initializes with required dependencies."""
        store = MagicMock()
        embedding_generator = MagicMock()
        config = ServerConfig()

        service = CrossProjectService(
            store=store,
            embedding_generator=embedding_generator,
            config=config,
        )

        assert service.store == store
        assert service.embedding_generator == embedding_generator
        assert service.config == config
        assert service.consent is None

    def test_initialization_with_all_dependencies(self):
        """Test service initializes with all dependencies."""
        store = MagicMock()
        embedding_generator = MagicMock()
        config = ServerConfig()
        consent = MagicMock()
        metrics_collector = MagicMock()

        service = CrossProjectService(
            store=store,
            embedding_generator=embedding_generator,
            config=config,
            cross_project_consent=consent,
            metrics_collector=metrics_collector,
        )

        assert service.consent == consent
        assert service.metrics_collector == metrics_collector

    def test_initial_stats_are_zero(self):
        """Test service stats start at zero."""
        service = CrossProjectService(
            store=MagicMock(),
            embedding_generator=MagicMock(),
            config=ServerConfig(),
        )

        stats = service.get_stats()
        assert stats["cross_project_searches"] == 0
        assert stats["projects_opted_in"] == 0
        assert stats["projects_opted_out"] == 0


class TestSearchAllProjectsNoConsent:
    """Test search_all_projects when consent manager not configured."""

    @pytest.fixture
    def service(self):
        """Create service without consent manager."""
        return CrossProjectService(
            store=MagicMock(),
            embedding_generator=AsyncMock(),
            config=ServerConfig(),
            cross_project_consent=None,
        )

    @pytest.mark.asyncio
    async def test_search_without_consent_returns_disabled(self, service):
        """Test search returns disabled status without consent manager."""
        result = await service.search_all_projects(query="test")

        assert result["status"] == "disabled"
        assert "error" in result


class TestSearchAllProjectsWithConsent:
    """Test search_all_projects with consent manager configured."""

    @pytest.fixture
    def service(self):
        """Create service with consent manager."""
        consent = MagicMock()
        consent.get_opted_in_projects.return_value = ["project1", "project2"]

        embedding_generator = AsyncMock()
        embedding_generator.generate = AsyncMock(return_value=mock_embedding(value=0.1))

        return CrossProjectService(
            store=AsyncMock(),
            embedding_generator=embedding_generator,
            config=ServerConfig(),
            cross_project_consent=consent,
        )

    @pytest.mark.asyncio
    async def test_search_no_opted_in_projects(self, service):
        """Test search when no projects have opted in."""
        service.consent.get_opted_in_projects.return_value = []

        result = await service.search_all_projects(query="test")

        assert result["total_found"] == 0
        assert "No projects have opted in" in result["message"]

    @pytest.mark.asyncio
    @pytest.mark.skip(
        reason="MultiRepositorySearcher class not available - needs implementation"
    )
    async def test_search_with_opted_in_projects(self, service):
        """Test search across opted-in projects."""
        with patch(
            "src.memory.multi_repository_search.MultiRepositorySearcher"
        ) as MockSearcher:
            mock_searcher = MagicMock()
            mock_searcher.search_project = AsyncMock(
                return_value=[{"file_path": "/test.py", "relevance_score": 0.85}]
            )
            MockSearcher.return_value = mock_searcher

            result = await service.search_all_projects(
                query="test function",
                limit=10,
            )

            assert "results" in result
            assert "projects_searched" in result
            assert "query_time_ms" in result

    @pytest.mark.asyncio
    @pytest.mark.skip(
        reason="MultiRepositorySearcher class not available - needs implementation"
    )
    async def test_search_increments_stats(self, service):
        """Test search increments statistics."""
        with patch(
            "src.memory.multi_repository_search.MultiRepositorySearcher"
        ) as MockSearcher:
            mock_searcher = MagicMock()
            mock_searcher.search_project = AsyncMock(return_value=[])
            MockSearcher.return_value = mock_searcher

            initial_stats = service.get_stats()
            await service.search_all_projects(query="test")

            stats = service.get_stats()
            assert (
                stats["cross_project_searches"]
                == initial_stats["cross_project_searches"] + 1
            )

    @pytest.mark.asyncio
    @pytest.mark.skip(
        reason="MultiRepositorySearcher class not available - needs implementation"
    )
    async def test_search_with_file_filter(self, service):
        """Test search with file pattern filter."""
        with patch(
            "src.memory.multi_repository_search.MultiRepositorySearcher"
        ) as MockSearcher:
            mock_searcher = MagicMock()
            mock_searcher.search_project = AsyncMock(
                return_value=[
                    {
                        "file_path": "/auth.py",
                        "relevance_score": 0.9,
                        "language": "python",
                    },
                    {
                        "file_path": "/utils.py",
                        "relevance_score": 0.7,
                        "language": "python",
                    },
                ]
            )
            MockSearcher.return_value = mock_searcher

            result = await service.search_all_projects(
                query="test",
                file_pattern="auth",
            )

            # Only auth.py should be included
            assert all("auth" in r.get("file_path", "") for r in result["results"])

    @pytest.mark.asyncio
    @pytest.mark.skip(
        reason="MultiRepositorySearcher class not available - needs implementation"
    )
    async def test_search_with_language_filter(self, service):
        """Test search with language filter."""
        with patch(
            "src.memory.multi_repository_search.MultiRepositorySearcher"
        ) as MockSearcher:
            mock_searcher = MagicMock()
            mock_searcher.search_project = AsyncMock(
                return_value=[
                    {
                        "file_path": "/test.py",
                        "relevance_score": 0.9,
                        "language": "python",
                    },
                    {
                        "file_path": "/test.js",
                        "relevance_score": 0.8,
                        "language": "javascript",
                    },
                ]
            )
            MockSearcher.return_value = mock_searcher

            result = await service.search_all_projects(
                query="test",
                language="python",
            )

            # Only Python files should be included
            assert all(
                r.get("language", "").lower() == "python" for r in result["results"]
            )

    @pytest.mark.asyncio
    @pytest.mark.skip(
        reason="MultiRepositorySearcher class not available - needs implementation"
    )
    async def test_search_handles_project_errors(self, service):
        """Test search continues when individual project fails."""
        with patch(
            "src.memory.multi_repository_search.MultiRepositorySearcher"
        ) as MockSearcher:
            mock_searcher = MagicMock()

            async def search_side_effect(
                query, query_embedding, project_name, **kwargs
            ):
                if project_name == "project1":
                    raise Exception("Project search failed")
                return [{"file_path": "/test.py", "relevance_score": 0.8}]

            mock_searcher.search_project = AsyncMock(side_effect=search_side_effect)
            MockSearcher.return_value = mock_searcher

            # Should not raise, should continue with other projects
            result = await service.search_all_projects(query="test")

            # Only project2 should be searched successfully
            assert "project2" in result["projects_searched"]

    @pytest.mark.asyncio
    @pytest.mark.skip(
        reason="MultiRepositorySearcher class not available - needs implementation"
    )
    async def test_search_results_sorted_by_relevance(self, service):
        """Test search results are sorted by relevance score."""
        with patch(
            "src.memory.multi_repository_search.MultiRepositorySearcher"
        ) as MockSearcher:
            mock_searcher = MagicMock()
            mock_searcher.search_project = AsyncMock(
                return_value=[
                    {"file_path": "/low.py", "relevance_score": 0.5},
                    {"file_path": "/high.py", "relevance_score": 0.9},
                ]
            )
            MockSearcher.return_value = mock_searcher

            result = await service.search_all_projects(query="test")

            if len(result["results"]) > 1:
                scores = [r.get("relevance_score", 0) for r in result["results"]]
                assert scores == sorted(scores, reverse=True)

    @pytest.mark.asyncio
    @pytest.mark.skip(
        reason="MultiRepositorySearcher class not available - needs implementation"
    )
    async def test_search_respects_limit(self, service):
        """Test search respects the limit parameter."""
        with patch(
            "src.memory.multi_repository_search.MultiRepositorySearcher"
        ) as MockSearcher:
            mock_searcher = MagicMock()
            mock_searcher.search_project = AsyncMock(
                return_value=[
                    {"file_path": f"/test{i}.py", "relevance_score": 0.9 - i * 0.1}
                    for i in range(10)
                ]
            )
            MockSearcher.return_value = mock_searcher

            result = await service.search_all_projects(
                query="test",
                limit=3,
            )

            assert len(result["results"]) <= 3

    @pytest.mark.asyncio
    @pytest.mark.skip(
        reason="MultiRepositorySearcher class not available - needs implementation"
    )
    async def test_search_logs_metrics(self, service):
        """Test search logs metrics when collector is available."""
        metrics_collector = MagicMock()
        metrics_collector.log_query = MagicMock()
        service.metrics_collector = metrics_collector

        with patch(
            "src.memory.multi_repository_search.MultiRepositorySearcher"
        ) as MockSearcher:
            mock_searcher = MagicMock()
            mock_searcher.search_project = AsyncMock(return_value=[])
            MockSearcher.return_value = mock_searcher

            await service.search_all_projects(query="test")

            metrics_collector.log_query.assert_called_once()


class TestOptInCrossProject:
    """Test opt_in_cross_project consent management."""

    @pytest.fixture
    def service(self):
        """Create service with consent manager."""
        consent = MagicMock()
        consent.opt_in = MagicMock()

        return CrossProjectService(
            store=MagicMock(),
            embedding_generator=MagicMock(),
            config=ServerConfig(),
            cross_project_consent=consent,
        )

    @pytest.mark.asyncio
    async def test_opt_in_without_consent_returns_disabled(self):
        """Test opt-in without consent manager returns disabled."""
        service = CrossProjectService(
            store=MagicMock(),
            embedding_generator=MagicMock(),
            config=ServerConfig(),
            cross_project_consent=None,
        )

        result = await service.opt_in_cross_project("test-project")

        assert result["status"] == "disabled"

    @pytest.mark.asyncio
    async def test_opt_in_success(self, service):
        """Test successful opt-in."""
        result = await service.opt_in_cross_project("test-project")

        assert result["status"] == "success"
        assert result["project_name"] == "test-project"
        assert result["action"] == "opted_in"
        service.consent.opt_in.assert_called_once_with("test-project")

    @pytest.mark.asyncio
    async def test_opt_in_increments_stats(self, service):
        """Test opt-in increments statistics."""
        initial_stats = service.get_stats()
        await service.opt_in_cross_project("test-project")

        stats = service.get_stats()
        assert stats["projects_opted_in"] == initial_stats["projects_opted_in"] + 1

    @pytest.mark.asyncio
    async def test_opt_in_error_raises(self, service):
        """Test opt-in error raises RetrievalError."""
        service.consent.opt_in.side_effect = Exception("Opt-in failed")

        with pytest.raises(RetrievalError):
            await service.opt_in_cross_project("test-project")


class TestOptOutCrossProject:
    """Test opt_out_cross_project consent management."""

    @pytest.fixture
    def service(self):
        """Create service with consent manager."""
        consent = MagicMock()
        consent.opt_out = MagicMock()

        return CrossProjectService(
            store=MagicMock(),
            embedding_generator=MagicMock(),
            config=ServerConfig(),
            cross_project_consent=consent,
        )

    @pytest.mark.asyncio
    async def test_opt_out_without_consent_returns_disabled(self):
        """Test opt-out without consent manager returns disabled."""
        service = CrossProjectService(
            store=MagicMock(),
            embedding_generator=MagicMock(),
            config=ServerConfig(),
            cross_project_consent=None,
        )

        result = await service.opt_out_cross_project("test-project")

        assert result["status"] == "disabled"

    @pytest.mark.asyncio
    async def test_opt_out_success(self, service):
        """Test successful opt-out."""
        result = await service.opt_out_cross_project("test-project")

        assert result["status"] == "success"
        assert result["project_name"] == "test-project"
        assert result["action"] == "opted_out"
        service.consent.opt_out.assert_called_once_with("test-project")

    @pytest.mark.asyncio
    async def test_opt_out_increments_stats(self, service):
        """Test opt-out increments statistics."""
        initial_stats = service.get_stats()
        await service.opt_out_cross_project("test-project")

        stats = service.get_stats()
        assert stats["projects_opted_out"] == initial_stats["projects_opted_out"] + 1

    @pytest.mark.asyncio
    async def test_opt_out_error_raises(self, service):
        """Test opt-out error raises RetrievalError."""
        service.consent.opt_out.side_effect = Exception("Opt-out failed")

        with pytest.raises(RetrievalError):
            await service.opt_out_cross_project("test-project")


class TestListOptedInProjects:
    """Test list_opted_in_projects."""

    @pytest.fixture
    def service(self):
        """Create service with consent manager."""
        consent = MagicMock()
        consent.get_opted_in_projects.return_value = ["project1", "project2"]
        consent.get_opted_out_projects.return_value = ["project3"]
        consent.get_statistics.return_value = {
            "total_opted_in": 2,
            "total_opted_out": 1,
        }

        return CrossProjectService(
            store=MagicMock(),
            embedding_generator=MagicMock(),
            config=ServerConfig(),
            cross_project_consent=consent,
        )

    @pytest.mark.asyncio
    async def test_list_without_consent_returns_disabled(self):
        """Test listing without consent manager returns disabled."""
        service = CrossProjectService(
            store=MagicMock(),
            embedding_generator=MagicMock(),
            config=ServerConfig(),
            cross_project_consent=None,
        )

        result = await service.list_opted_in_projects()

        assert result["status"] == "disabled"

    @pytest.mark.asyncio
    async def test_list_success(self, service):
        """Test successful listing."""
        result = await service.list_opted_in_projects()

        assert "opted_in_projects" in result
        assert "opted_out_projects" in result
        assert "statistics" in result
        assert result["opted_in_projects"] == ["project1", "project2"]
        assert result["opted_out_projects"] == ["project3"]

    @pytest.mark.asyncio
    async def test_list_error_raises(self, service):
        """Test listing error raises RetrievalError."""
        service.consent.get_opted_in_projects.side_effect = Exception("List failed")

        with pytest.raises(RetrievalError):
            await service.list_opted_in_projects()


class TestConsentManagerIntegration:
    """Test consent manager integration scenarios."""

    @pytest.fixture
    def service_with_consent(self):
        """Create service with fully mocked consent manager."""
        consent = MagicMock()
        consent.get_opted_in_projects.return_value = []
        consent.get_opted_out_projects.return_value = []
        consent.get_statistics.return_value = {}
        consent.opt_in = MagicMock()
        consent.opt_out = MagicMock()

        return CrossProjectService(
            store=MagicMock(),
            embedding_generator=AsyncMock(),
            config=ServerConfig(),
            cross_project_consent=consent,
        )

    @pytest.mark.asyncio
    @pytest.mark.skip(
        reason="MultiRepositorySearcher class not available - needs implementation"
    )
    async def test_opt_in_then_search(self, service_with_consent):
        """Test opting in a project then searching."""
        # Opt in
        await service_with_consent.opt_in_cross_project("new-project")
        service_with_consent.consent.opt_in.assert_called_with("new-project")

        # Now configure consent to return the opted-in project
        service_with_consent.consent.get_opted_in_projects.return_value = [
            "new-project"
        ]
        service_with_consent.embedding_generator.generate = AsyncMock(
            return_value=mock_embedding(value=0.1)
        )

        # Search should work
        with patch(
            "src.memory.multi_repository_search.MultiRepositorySearcher"
        ) as MockSearcher:
            mock_searcher = MagicMock()
            mock_searcher.search_project = AsyncMock(return_value=[])
            MockSearcher.return_value = mock_searcher

            result = await service_with_consent.search_all_projects(query="test")
            assert "new-project" in result["projects_searched"]

    @pytest.mark.asyncio
    async def test_opt_out_removes_from_search(self, service_with_consent):
        """Test opting out removes project from search."""
        # Initial state: project is opted in
        service_with_consent.consent.get_opted_in_projects.return_value = ["project1"]
        service_with_consent.embedding_generator.generate = AsyncMock(
            return_value=mock_embedding(value=0.1)
        )

        # Opt out
        await service_with_consent.opt_out_cross_project("project1")

        # After opt-out, project not in list
        service_with_consent.consent.get_opted_in_projects.return_value = []

        # Search should return no projects
        result = await service_with_consent.search_all_projects(query="test")
        assert len(result["projects_searched"]) == 0


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.fixture
    def service(self):
        """Create service with consent manager."""
        consent = MagicMock()
        consent.get_opted_in_projects.return_value = ["project1"]
        consent.opt_in = MagicMock()
        consent.opt_out = MagicMock()

        embedding_generator = AsyncMock()
        embedding_generator.generate = AsyncMock(return_value=mock_embedding(value=0.1))

        return CrossProjectService(
            store=MagicMock(),
            embedding_generator=embedding_generator,
            config=ServerConfig(),
            cross_project_consent=consent,
        )

    @pytest.mark.asyncio
    @pytest.mark.skip(
        reason="MultiRepositorySearcher class not available - needs implementation"
    )
    async def test_empty_query_search(self, service):
        """Test search with empty query."""
        with patch(
            "src.memory.multi_repository_search.MultiRepositorySearcher"
        ) as MockSearcher:
            mock_searcher = MagicMock()
            mock_searcher.search_project = AsyncMock(return_value=[])
            MockSearcher.return_value = mock_searcher

            result = await service.search_all_projects(query="")

            assert "results" in result

    @pytest.mark.asyncio
    async def test_special_characters_in_project_name(self, service):
        """Test opt-in/opt-out with special characters in name."""
        await service.opt_in_cross_project("project-with-dashes_and_underscores")
        service.consent.opt_in.assert_called_with("project-with-dashes_and_underscores")

    @pytest.mark.asyncio
    @pytest.mark.skip(
        reason="MultiRepositorySearcher class not available - needs implementation"
    )
    async def test_search_with_zero_limit(self, service):
        """Test search with zero limit returns empty."""
        with patch(
            "src.memory.multi_repository_search.MultiRepositorySearcher"
        ) as MockSearcher:
            mock_searcher = MagicMock()
            mock_searcher.search_project = AsyncMock(
                return_value=[{"file_path": "/test.py", "relevance_score": 0.9}]
            )
            MockSearcher.return_value = mock_searcher

            result = await service.search_all_projects(
                query="test",
                limit=0,
            )

            assert len(result["results"]) == 0

    @pytest.mark.asyncio
    @pytest.mark.skip(
        reason="MultiRepositorySearcher class not available - needs implementation"
    )
    async def test_search_mode_passed_to_searcher(self, service):
        """Test search mode is passed to underlying searcher."""
        with patch(
            "src.memory.multi_repository_search.MultiRepositorySearcher"
        ) as MockSearcher:
            mock_searcher = MagicMock()
            mock_searcher.search_project = AsyncMock(return_value=[])
            MockSearcher.return_value = mock_searcher

            await service.search_all_projects(
                query="test",
                search_mode="hybrid",
            )

            # Verify search_mode was passed
            call_args = mock_searcher.search_project.call_args
            assert call_args.kwargs.get("search_mode") == "hybrid"
