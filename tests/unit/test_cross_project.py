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
        consent_file = tmp_path / "consent.json"
        consent = CrossProjectConsent(str(consent_file))

        assert consent.consent_file == consent_file
        assert len(consent.get_opted_in_projects()) == 0

    def test_opt_in_project(self, tmp_path):
        """Test opting in a project."""
        consent_file = tmp_path / "consent.json"
        consent = CrossProjectConsent(str(consent_file))

        consent.opt_in_project("test-project")

        assert consent.is_project_opted_in("test-project")
        assert "test-project" in consent.get_opted_in_projects()

    def test_opt_out_project(self, tmp_path):
        """Test opting out a project."""
        consent_file = tmp_path / "consent.json"
        consent = CrossProjectConsent(str(consent_file))

        consent.opt_in_project("test-project")
        assert consent.is_project_opted_in("test-project")

        consent.opt_out_project("test-project")
        assert not consent.is_project_opted_in("test-project")

    def test_get_searchable_projects_current_only(self, tmp_path):
        """Test getting searchable projects in current-only mode."""
        consent_file = tmp_path / "consent.json"
        consent = CrossProjectConsent(str(consent_file))

        consent.opt_in_project("project-a")
        consent.opt_in_project("project-b")

        # Current only mode - should only return current project
        searchable = consent.get_searchable_projects("project-c", search_all=False)
        assert searchable == {"project-c"}

    def test_get_searchable_projects_all_mode(self, tmp_path):
        """Test getting searchable projects in all mode."""
        consent_file = tmp_path / "consent.json"
        consent = CrossProjectConsent(str(consent_file))

        consent.opt_in_project("project-a")
        consent.opt_in_project("project-b")

        # All mode - should return all opted-in + current
        searchable = consent.get_searchable_projects("project-c", search_all=True)
        assert searchable == {"project-a", "project-b", "project-c"}

    def test_persistence(self, tmp_path):
        """Test that consent is persisted across instances."""
        consent_file = tmp_path / "consent.json"

        # First instance - opt in projects
        consent1 = CrossProjectConsent(str(consent_file))
        consent1.opt_in_project("project-a")
        consent1.opt_in_project("project-b")

        # Second instance - should load persisted data
        consent2 = CrossProjectConsent(str(consent_file))
        assert consent2.is_project_opted_in("project-a")
        assert consent2.is_project_opted_in("project-b")


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

        # Should search current project (always allowed) but may not have indexed data
        # The current project is auto-detected from git, so it will be searched
        assert "results" in result
        assert "projects_searched" in result
        # Current project is always searchable
        assert len(result["projects_searched"]) >= 1

    @pytest.mark.asyncio
    async def test_search_all_projects_with_indexing(self, server):
        """Test cross-project search with actual indexed code."""
        # Index a test directory
        test_dir = Path(__file__).parent.parent / "unit"

        # Get the current project name (auto-detected from git)
        current_project = server.project_name or "test-project-1"

        # Index with current project name
        await server.index_codebase(
            directory_path=str(test_dir),
            project_name=current_project,
            recursive=False
        )

        # Search across projects
        result = await server.search_all_projects(
            query="test function",
            limit=5
        )

        # Should have results from the indexed project
        assert "results" in result
        assert "projects_searched" in result
        assert current_project in result["projects_searched"]
        assert "query_time_ms" in result

    @pytest.mark.asyncio
    async def test_search_all_projects_result_format(self, server):
        """Test that cross-project results have correct format."""
        # Index a test directory
        test_dir = Path(__file__).parent.parent / "unit"

        await server.index_codebase(
            directory_path=str(test_dir),
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
