"""Tests for cross-project learning functionality."""

import pytest
import pytest_asyncio
from pathlib import Path
from src.config import ServerConfig
from src.core.server import MemoryRAGServer
from src.core.exceptions import ValidationError
from src.memory.cross_project_consent import CrossProjectConsent


@pytest.fixture
def config(tmp_path):
    """Create test configuration with temporary consent file."""
    consent_file = tmp_path / "cross_project_consent.json"
    return ServerConfig(
        storage_backend="qdrant",
        qdrant_url="http://localhost:6333",
        read_only_mode=False,
        enable_retrieval_gate=False,
        enable_cross_project_search=True,
        cross_project_default_mode="current",
        cross_project_opt_in_file=str(consent_file),
    )


@pytest_asyncio.fixture
async def server(config):
    """Create server instance."""
    srv = MemoryRAGServer(config)
    await srv.initialize()
    yield srv
    await srv.close()


class TestCrossProjectConsent:
    """Test cross-project consent manager."""

    def test_consent_initialization(self, tmp_path):
        """Test consent manager initialization."""
        consent_file = tmp_path / "consent.db"
        consent = CrossProjectConsent(consent_file)

        assert consent.db_path == consent_file
        assert len(consent.get_opted_in_projects()) == 0

    def test_opt_in_project(self, tmp_path):
        """Test opting in a project."""
        consent_file = tmp_path / "consent.db"
        consent = CrossProjectConsent(consent_file)

        consent.opt_in("test-project")

        assert consent.is_opted_in("test-project")
        assert "test-project" in consent.get_opted_in_projects()

    def test_opt_out_project(self, tmp_path):
        """Test opting out a project."""
        consent_file = tmp_path / "consent.db"
        consent = CrossProjectConsent(consent_file)

        consent.opt_in("test-project")
        assert consent.is_opted_in("test-project")

        consent.opt_out("test-project")
        assert not consent.is_opted_in("test-project")

    def test_get_searchable_projects_current_only(self, tmp_path):
        """Test getting searchable projects excluding current."""
        consent_file = tmp_path / "consent.db"
        consent = CrossProjectConsent(consent_file)

        consent.opt_in("project-a")
        consent.opt_in("project-b")
        consent.opt_in("project-c")

        # When search_all=False, exclude current project from opted-in list
        searchable = consent.get_searchable_projects("project-c", search_all=False)
        assert set(searchable) == {"project-a", "project-b"}

    def test_get_searchable_projects_all_mode(self, tmp_path):
        """Test getting all searchable projects."""
        consent_file = tmp_path / "consent.db"
        consent = CrossProjectConsent(consent_file)

        consent.opt_in("project-a")
        consent.opt_in("project-b")

        # All mode - should return all opted-in projects
        searchable = consent.get_searchable_projects("project-c", search_all=True)
        assert set(searchable) == {"project-a", "project-b"}

    def test_persistence(self, tmp_path):
        """Test that consent is persisted across instances."""
        consent_file = tmp_path / "consent.db"

        # First instance - opt in projects
        consent1 = CrossProjectConsent(consent_file)
        consent1.opt_in("project-a")
        consent1.opt_in("project-b")

        # Second instance - should load persisted data
        consent2 = CrossProjectConsent(consent_file)
        assert consent2.is_opted_in("project-a")
        assert consent2.is_opted_in("project-b")


class TestSearchAllProjects:
    """Test search_all_projects functionality."""

    @pytest.mark.asyncio
    async def test_search_all_projects_disabled(self, tmp_path):
        """Test that search fails when cross-project is disabled."""
        config = ServerConfig(
            storage_backend="qdrant",
            qdrant_url="http://localhost:6333",
            read_only_mode=False,
            enable_retrieval_gate=False,
            enable_cross_project_search=False,  # Disabled
        )

        srv = MemoryRAGServer(config)
        await srv.initialize()

        try:
            with pytest.raises(ValidationError):
                await srv.search_all_projects(query="test")
        finally:
            await srv.close()

    @pytest.mark.asyncio
    async def test_search_all_projects_no_opted_in(self, server):
        """Test search with no opted-in projects."""
        # Don't opt in any projects
        result = await server.search_all_projects(query="test function")

        # With no opted-in projects, there are no projects to search
        assert "results" in result
        assert "projects_searched" in result
        # No projects opted in means no projects searched
        assert isinstance(result["projects_searched"], list)

    @pytest.mark.asyncio
    async def test_search_all_projects_with_indexing(self, server, small_test_project):
        """Test cross-project search with actual indexed code."""
        # Get the current project name (auto-detected from git)
        current_project = server.project_name or "test-project-1"

        # Opt in the project for cross-project search
        if hasattr(server, 'consent_manager') and server.consent_manager:
            server.consent_manager.opt_in(current_project)

        # Index with current project name
        await server.index_codebase(
            directory_path=str(small_test_project),
            project_name=current_project,
            recursive=False
        )

        # Search across projects
        result = await server.search_all_projects(
            query="test function",
            limit=5
        )

        # Should have results from the indexed project (if opted in)
        assert "results" in result
        assert "projects_searched" in result
        # If consent manager exists and project was opted in, it should be searched
        if hasattr(server, 'consent_manager') and server.consent_manager:
            assert current_project in result["projects_searched"]
        assert "query_time_ms" in result

    @pytest.mark.asyncio
    async def test_search_all_projects_result_format(self, server, small_test_project):
        """Test that cross-project results have correct format."""
        await server.index_codebase(
            directory_path=str(small_test_project),
            project_name="test-project",
            recursive=False
        )

        # Opt in
        if server.cross_project_consent:
            server.cross_project_consent.opt_in_project("test-project")

        result = await server.search_all_projects(
            query="test",
            limit=3
        )

        # Verify result structure
        assert "total_found" in result
        assert "projects_searched" in result
        assert "projects_with_results" in result
        assert "interpretation" in result
        assert "suggestions" in result

        # Check result items have source_project
        for item in result["results"]:
            assert "source_project" in item
