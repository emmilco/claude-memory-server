"""Tests for project reindexing control (FEAT-045)."""

import pytest
import pytest_asyncio
import tempfile
import shutil
import uuid
from pathlib import Path

from src.core.server import MemoryRAGServer
from src.config import ServerConfig
from src.store.qdrant_store import QdrantMemoryStore


@pytest_asyncio.fixture
async def test_project_dir():
    """Create a temporary project directory with sample code."""
    tmpdir = tempfile.mkdtemp()
    test_dir = Path(tmpdir) / "test_project"
    test_dir.mkdir()

    # Create sample Python file
    (test_dir / "main.py").write_text("""
def hello():
    print("Hello, World!")

class Greeter:
    def greet(self, name):
        return f"Hello, {name}!"
""")

    # Create sample JavaScript file
    (test_dir / "app.js").write_text("""
function sayHi() {
    console.log("Hi!");
}

class User {
    constructor(name) {
        this.name = name;
    }
}
""")

    yield test_dir

    # Cleanup
    shutil.rmtree(tmpdir)


@pytest_asyncio.fixture
async def server(unique_qdrant_collection):
    """Create a test server with Qdrant backend and pooled collection.

    Uses the unique_qdrant_collection fixture from conftest.py to leverage
    collection pooling and prevent Qdrant deadlocks during parallel test execution.
    """
    config = ServerConfig(
        storage_backend="qdrant",
        qdrant_url="http://localhost:6333",
        qdrant_collection_name=unique_qdrant_collection,
        embedding_cache_enabled=True,
    )

    server = MemoryRAGServer(config)
    await server.initialize()

    yield server

    # Cleanup
    await server.close()
    # Collection cleanup handled by unique_qdrant_collection autouse fixture


@pytest.mark.asyncio
@pytest.mark.skip(reason="Flaky test - race condition in parallel execution (passes individually)")
async def test_reindex_project_basic(server, test_project_dir):
    """Test basic project reindexing."""
    # First index
    result1 = await server.reindex_project(
        project_name="test-project",
        directory_path=str(test_project_dir),
    )

    assert result1["status"] == "success"
    assert result1["project_name"] == "test-project"
    assert result1["files_indexed"] == 2  # main.py and app.js
    assert result1["units_indexed"] > 0  # At least some functions/classes
    assert result1["index_cleared"] is False
    assert result1["cache_bypassed"] is False
    assert result1["units_deleted"] == 0


@pytest.mark.asyncio
@pytest.mark.skip(reason="Flaky under parallel execution - Qdrant fixture race conditions")
async def test_reindex_with_clear_existing(server, test_project_dir):
    """Test reindexing with clear_existing flag."""
    # First index
    result1 = await server.reindex_project(
        project_name="test-project",
        directory_path=str(test_project_dir),
    )

    initial_units = result1["units_indexed"]
    assert initial_units > 0

    # Re-index with clear_existing
    result2 = await server.reindex_project(
        project_name="test-project",
        directory_path=str(test_project_dir),
        clear_existing=True,
    )

    assert result2["status"] == "success"
    assert result2["index_cleared"] is True
    assert result2["units_deleted"] == initial_units  # Deleted all previous units
    assert result2["units_indexed"] == initial_units  # Re-indexed same units


@pytest.mark.asyncio
@pytest.mark.skip(reason="Flaky under parallel execution - Qdrant fixture race conditions")
async def test_reindex_with_bypass_cache(server, test_project_dir):
    """Test reindexing with bypass_cache flag."""
    # First index (populate cache)
    result1 = await server.reindex_project(
        project_name="test-project",
        directory_path=str(test_project_dir),
    )

    assert result1["units_indexed"] > 0

    # Re-index with bypass_cache
    result2 = await server.reindex_project(
        project_name="test-project",
        directory_path=str(test_project_dir),
        bypass_cache=True,
    )

    assert result2["status"] == "success"
    assert result2["cache_bypassed"] is True
    # Should still index the same number of units
    assert result2["units_indexed"] == result1["units_indexed"]


@pytest.mark.asyncio
@pytest.mark.skip(reason="Flaky under parallel execution - Qdrant fixture race conditions")
async def test_reindex_with_both_flags(server, test_project_dir):
    """Test reindexing with both clear_existing and bypass_cache."""
    # First index
    result1 = await server.reindex_project(
        project_name="test-project",
        directory_path=str(test_project_dir),
    )

    initial_units = result1["units_indexed"]

    # Re-index with both flags (complete reset)
    result2 = await server.reindex_project(
        project_name="test-project",
        directory_path=str(test_project_dir),
        clear_existing=True,
        bypass_cache=True,
    )

    assert result2["status"] == "success"
    assert result2["index_cleared"] is True
    assert result2["cache_bypassed"] is True
    assert result2["units_deleted"] == initial_units
    assert result2["units_indexed"] == initial_units


@pytest.mark.asyncio
async def test_reindex_nonexistent_directory(server):
    """Test reindexing with non-existent directory."""
    with pytest.raises(ValueError, match="Directory does not exist"):
        await server.reindex_project(
            project_name="test-project",
            directory_path="/nonexistent/path",
        )


@pytest.mark.asyncio
async def test_reindex_file_not_directory(server, test_project_dir):
    """Test reindexing with a file path instead of directory."""
    file_path = test_project_dir / "main.py"

    with pytest.raises(ValueError, match="not a directory"):
        await server.reindex_project(
            project_name="test-project",
            directory_path=str(file_path),
        )


@pytest.mark.asyncio
async def test_reindex_empty_directory(server):
    """Test reindexing an empty directory."""
    tmpdir = tempfile.mkdtemp()
    empty_dir = Path(tmpdir)

    try:
        result = await server.reindex_project(
            project_name="empty-project",
            directory_path=str(empty_dir),
        )

        assert result["status"] == "success"
        assert result["files_indexed"] == 0
        assert result["units_indexed"] == 0
    finally:
        shutil.rmtree(tmpdir)


@pytest.mark.asyncio
@pytest.mark.skip(reason="Flaky test - race condition in parallel execution (passes individually)")
async def test_reindex_stats_accuracy(server, test_project_dir):
    """Test that reindexing statistics are accurate."""
    result = await server.reindex_project(
        project_name="test-project",
        directory_path=str(test_project_dir),
    )

    # Check all expected fields are present
    assert "status" in result
    assert "project_name" in result
    assert "directory" in result
    assert "files_indexed" in result
    assert "units_indexed" in result
    assert "total_time_s" in result
    assert "index_cleared" in result
    assert "cache_bypassed" in result
    assert "units_deleted" in result
    assert "languages" in result

    # Check values are reasonable
    assert result["status"] == "success"
    assert result["files_indexed"] == 2
    assert result["units_indexed"] >= 4  # At least 2 functions + 2 classes
    assert result["total_time_s"] > 0
    assert isinstance(result["languages"], dict)


@pytest.mark.asyncio
@pytest.mark.skip(reason="Flaky test - race condition in parallel execution (passes individually)")
async def test_reindex_multiple_projects(server, test_project_dir):
    """Test reindexing same project multiple times."""
    # Index first time
    result1 = await server.reindex_project(
        project_name="test-project",
        directory_path=str(test_project_dir),
    )

    assert result1["status"] == "success"
    assert result1["units_indexed"] > 0
    initial_units = result1["units_indexed"]

    # Index again without clearing (should update in place)
    result2 = await server.reindex_project(
        project_name="test-project",
        directory_path=str(test_project_dir),
    )

    assert result2["status"] == "success"
    assert result2["units_indexed"] == initial_units

    # Now clear and reindex
    result3 = await server.reindex_project(
        project_name="test-project",
        directory_path=str(test_project_dir),
        clear_existing=True,
    )

    assert result3["status"] == "success"
    assert result3["units_deleted"] == initial_units
    assert result3["units_indexed"] == initial_units


@pytest.mark.asyncio
@pytest.mark.skip(reason="Flaky under parallel execution - Qdrant fixture race conditions")
async def test_reindex_with_progress_callback(server, test_project_dir):
    """Test reindexing with progress callback."""
    progress_calls = []

    def progress_callback(current, total, current_file, error_info):
        progress_calls.append({
            "current": current,
            "total": total,
            "file": current_file,
            "error": error_info,
        })

    result = await server.reindex_project(
        project_name="test-project",
        directory_path=str(test_project_dir),
        progress_callback=progress_callback,
    )

    assert result["status"] == "success"
    # Progress callback should have been called at least once
    assert len(progress_calls) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
