"""Tests for cross-project consent management (FEAT-039)."""

import pytest
import pytest_asyncio
import tempfile
import shutil
from pathlib import Path

from src.memory.cross_project_consent import CrossProjectConsentManager, CrossProjectConsent
from src.core.server import MemoryRAGServer
from src.config import ServerConfig


@pytest.fixture
def consent_db():
    """Create a temporary consent database."""
    tmpdir = tempfile.mkdtemp()
    db_path = Path(tmpdir) / "consent.db"

    yield db_path

    # Cleanup
    shutil.rmtree(tmpdir)


@pytest.fixture
def consent_manager(consent_db):
    """Create a CrossProjectConsentManager instance."""
    return CrossProjectConsentManager(db_path=consent_db)


@pytest_asyncio.fixture
async def server():
    """Create a test server with cross-project search enabled."""
    config = ServerConfig(
        storage_backend="qdrant",
        qdrant_url="http://localhost:6333",
        qdrant_collection_name="test_cross_project_consent",
        search={"cross_project_enabled": True},
    )

    server = MemoryRAGServer(config)
    await server.initialize()

    yield server

    await server.close()


# CrossProjectConsentManager Tests


def test_opt_in_new_project(consent_manager):
    """Test opting-in a new project."""
    result = consent_manager.opt_in("my-project")

    assert result["status"] == "opted_in"
    assert result["project_name"] == "my-project"
    assert result["was_opted_in"] is False  # Was not previously opted-in
    assert "opted_in_at" in result


def test_opt_out_existing_project(consent_manager):
    """Test opting-out an existing project."""
    # First opt-in
    consent_manager.opt_in("my-project")

    # Then opt-out
    result = consent_manager.opt_out("my-project")

    assert result["status"] == "opted_out"
    assert result["project_name"] == "my-project"
    assert result["was_opted_in"] is True  # Was previously opted-in
    assert "opted_out_at" in result


def test_re_opt_in_previously_opted_out(consent_manager):
    """Test re-opting-in a previously opted-out project."""
    # Opt-in, opt-out, then opt-in again
    consent_manager.opt_in("my-project")
    consent_manager.opt_out("my-project")
    result = consent_manager.opt_in("my-project")

    assert result["status"] == "opted_in"
    assert result["was_opted_in"] is False  # Was opted-out before this call


def test_is_opted_in_for_opted_in_project(consent_manager):
    """Test checking consent for an opted-in project."""
    consent_manager.opt_in("my-project")

    assert consent_manager.is_opted_in("my-project") is True


def test_is_opted_in_for_opted_out_project(consent_manager):
    """Test checking consent for an opted-out project."""
    consent_manager.opt_out("my-project")

    assert consent_manager.is_opted_in("my-project") is False


def test_is_opted_in_for_nonexistent_project(consent_manager):
    """Test checking consent for a project with no preference set."""
    # Default behavior: projects are opted-in by default
    assert consent_manager.is_opted_in("nonexistent-project") is True


def test_list_opted_in_projects(consent_manager):
    """Test listing all opted-in projects."""
    # Opt-in some projects
    consent_manager.opt_in("project-a")
    consent_manager.opt_in("project-b")
    consent_manager.opt_out("project-c")

    opted_in = consent_manager.list_opted_in_projects()

    assert len(opted_in) == 2
    assert "project-a" in opted_in
    assert "project-b" in opted_in
    assert "project-c" not in opted_in


def test_list_opted_out_projects(consent_manager):
    """Test listing all opted-out projects."""
    consent_manager.opt_in("project-a")
    consent_manager.opt_out("project-b")
    consent_manager.opt_out("project-c")

    opted_out = consent_manager.list_opted_out_projects()

    assert len(opted_out) == 2
    assert "project-b" in opted_out
    assert "project-c" in opted_out
    assert "project-a" not in opted_out


def test_consent_persistence(consent_db):
    """Test that consent preferences persist across manager restarts."""
    # Create first manager and set preferences
    manager1 = CrossProjectConsentManager(db_path=consent_db)
    manager1.opt_in("project-a")
    manager1.opt_out("project-b")

    # Create second manager (simulates restart)
    manager2 = CrossProjectConsentManager(db_path=consent_db)

    assert manager2.is_opted_in("project-a") is True
    assert manager2.is_opted_in("project-b") is False


def test_get_consent_stats(consent_manager):
    """Test getting consent statistics."""
    consent_manager.opt_in("project-a")
    consent_manager.opt_in("project-b")
    consent_manager.opt_out("project-c")

    stats = consent_manager.get_consent_stats()

    assert stats["total_projects"] == 3
    assert stats["opted_in_count"] == 2
    assert stats["opted_out_count"] == 1
    assert stats["default_consent"] == "opted_in"


def test_get_project_consent_status_opted_in(consent_manager):
    """Test getting detailed consent status for opted-in project."""
    consent_manager.opt_in("my-project")

    status = consent_manager.get_project_consent_status("my-project")

    assert status["project_name"] == "my-project"
    assert status["opted_in"] is True
    assert status["has_explicit_preference"] is True
    assert status["opted_in_at"] is not None


def test_get_project_consent_status_opted_out(consent_manager):
    """Test getting detailed consent status for opted-out project."""
    consent_manager.opt_out("my-project")

    status = consent_manager.get_project_consent_status("my-project")

    assert status["project_name"] == "my-project"
    assert status["opted_in"] is False
    assert status["has_explicit_preference"] is True
    assert status["opted_out_at"] is not None


def test_get_project_consent_status_no_preference(consent_manager):
    """Test getting consent status for project with no explicit preference."""
    status = consent_manager.get_project_consent_status("nonexistent-project")

    assert status["project_name"] == "nonexistent-project"
    assert status["opted_in"] is True  # Default
    assert status["has_explicit_preference"] is False
    assert status["opted_in_at"] is None
    assert status["opted_out_at"] is None


def test_get_searchable_projects_all(consent_manager):
    """Test getting searchable projects with search_all=True."""
    consent_manager.opt_in("project-a")
    consent_manager.opt_in("project-b")
    consent_manager.opt_out("project-c")

    searchable = consent_manager.get_searchable_projects(
        current_project="project-a",
        search_all=True,
    )

    assert len(searchable) == 2
    assert "project-a" in searchable
    assert "project-b" in searchable
    assert "project-c" not in searchable


def test_get_searchable_projects_exclude_current(consent_manager):
    """Test getting searchable projects excluding current project."""
    consent_manager.opt_in("project-a")
    consent_manager.opt_in("project-b")
    consent_manager.opt_out("project-c")

    searchable = consent_manager.get_searchable_projects(
        current_project="project-a",
        search_all=False,
    )

    assert len(searchable) == 1
    assert "project-a" not in searchable  # Current project excluded
    assert "project-b" in searchable
    assert "project-c" not in searchable


def test_class_alias():
    """Test that CrossProjectConsent is an alias for CrossProjectConsentManager."""
    assert CrossProjectConsent is CrossProjectConsentManager


# MCP Tools Tests


@pytest.mark.asyncio
@pytest.mark.slow
async def test_opt_in_cross_project_tool(server):
    """Test opt_in_cross_project MCP tool."""
    result = await server.opt_in_cross_project("my-project")

    assert result["status"] == "opted_in"
    assert result["project_name"] == "my-project"


@pytest.mark.asyncio
@pytest.mark.slow
async def test_opt_out_cross_project_tool(server):
    """Test opt_out_cross_project MCP tool."""
    # First opt-in
    await server.opt_in_cross_project("my-project")

    # Then opt-out
    result = await server.opt_out_cross_project("my-project")

    assert result["status"] == "opted_out"
    assert result["project_name"] == "my-project"


@pytest.mark.asyncio
@pytest.mark.slow
async def test_list_opted_in_projects_tool(server):
    """Test list_opted_in_projects MCP tool."""
    # Set up some projects
    await server.opt_in_cross_project("project-a")
    await server.opt_in_cross_project("project-b")
    await server.opt_out_cross_project("project-c")

    result = await server.list_opted_in_projects()

    # Check that our projects are in the right lists (may have more from other tests)
    assert "project-a" in result["opted_in_projects"]
    assert "project-b" in result["opted_in_projects"]
    assert "project-c" in result["opted_out_projects"]
    assert "project-c" not in result["opted_in_projects"]
    # Statistics should reflect at least our changes
    assert result["statistics"]["opted_in_count"] >= 2
    assert result["statistics"]["opted_out_count"] >= 1


@pytest.mark.asyncio
@pytest.mark.slow
async def test_tools_with_cross_project_disabled():
    """Test that consent tools raise error when cross-project search is disabled."""
    config = ServerConfig(
        storage_backend="qdrant",
        qdrant_url="http://localhost:6333",
        qdrant_collection_name="test_cross_project_disabled",
        search={"cross_project_enabled": False},
    )

    server = MemoryRAGServer(config)
    await server.initialize()

    from src.core.exceptions import ValidationError

    with pytest.raises(ValidationError, match="Cross-project search is disabled"):
        await server.opt_in_cross_project("my-project")

    with pytest.raises(ValidationError, match="Cross-project search is disabled"):
        await server.opt_out_cross_project("my-project")

    with pytest.raises(ValidationError, match="Cross-project search is disabled"):
        await server.list_opted_in_projects()

    await server.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
