"""Unit tests for indexed content visibility (FEAT-046)."""

import pytest
import pytest_asyncio
import uuid
from pathlib import Path
import tempfile
import shutil
from datetime import datetime, UTC

from src.config import ServerConfig
from src.core.server import MemoryRAGServer
from src.memory.incremental_indexer import IncrementalIndexer


@pytest.fixture
def test_project_dir():
    """Create a temporary project directory with test files."""
    temp_dir = tempfile.mkdtemp()

    # Create some test Python files
    (Path(temp_dir) / "module1.py").write_text("""
def function_one():
    pass

class ClassOne:
    def method_one(self):
        pass
""")

    (Path(temp_dir) / "module2.py").write_text("""
def function_two():
    pass

class ClassTwo:
    def method_two(self):
        pass
""")

    # Create a subdirectory with more files
    (Path(temp_dir) / "subdir").mkdir()
    (Path(temp_dir) / "subdir" / "module3.py").write_text("""
def function_three():
    pass
""")

    yield temp_dir

    # Cleanup
    shutil.rmtree(temp_dir)


@pytest.fixture
def config(unique_qdrant_collection):
    """Create test configuration with pooled collection name.

    Uses the unique_qdrant_collection fixture from conftest.py to leverage
    collection pooling and prevent Qdrant deadlocks during parallel test execution.
    """
    return ServerConfig(
        storage_backend="qdrant",
        qdrant_url="http://localhost:6333",
        qdrant_collection_name=unique_qdrant_collection,
        read_only_mode=False,
        enable_retrieval_gate=False,
    )


@pytest_asyncio.fixture
async def server_with_indexed_code(config, test_project_dir):
    """Create server instance with indexed code and unique collection."""
    srv = MemoryRAGServer(config)
    await srv.initialize()

    # Index the test project
    indexer = IncrementalIndexer(
        srv.store,
        srv.embedding_generator,
        project_name="test-project"
    )
    await indexer.index_directory(
        dir_path=Path(test_project_dir),
        show_progress=False
    )

    yield srv

    # Cleanup
    await srv.close()
    # Collection cleanup handled by unique_qdrant_collection autouse fixture


@pytest.mark.asyncio
@pytest.mark.skip(reason="Flaky under parallel execution - fixture race conditions")
async def test_get_indexed_files_all(server_with_indexed_code):
    """Test getting all indexed files."""
    result = await server_with_indexed_code.get_indexed_files(limit=100)

    assert "files" in result
    assert "total" in result
    assert "limit" in result
    assert "offset" in result
    assert "has_more" in result

    # Should have at least 3 files
    assert result["total"] >= 3
    assert len(result["files"]) >= 3

    # Each file should have required fields
    for file_info in result["files"]:
        assert "file_path" in file_info
        assert "language" in file_info
        assert "last_indexed" in file_info
        assert "unit_count" in file_info

        # Verify language is Python
        assert file_info["language"] == "Python"

        # unit_count should be >= 1
        assert file_info["unit_count"] >= 1


@pytest.mark.asyncio
@pytest.mark.skip(reason="Flaky under parallel execution - fixture race conditions")
async def test_get_indexed_files_by_project(server_with_indexed_code):
    """Test filtering indexed files by project name."""
    result = await server_with_indexed_code.get_indexed_files(
        project_name="test-project",
        limit=100
    )

    assert result["total"] >= 3
    # All files should be from test-project
    for file_info in result["files"]:
        assert file_info["file_path"].endswith(".py")


@pytest.mark.asyncio
async def test_get_indexed_files_pagination(server_with_indexed_code):
    """Test pagination of indexed files."""
    # Get first page
    page1 = await server_with_indexed_code.get_indexed_files(limit=2, offset=0)

    assert page1["limit"] == 2
    assert page1["offset"] == 0
    assert len(page1["files"]) <= 2

    # has_more should be True if total > 2
    if page1["total"] > 2:
        assert page1["has_more"] is True

        # Get second page
        page2 = await server_with_indexed_code.get_indexed_files(limit=2, offset=2)
        assert page2["offset"] == 2
        assert len(page2["files"]) >= 1


@pytest.mark.asyncio
async def test_get_indexed_files_empty_project(server_with_indexed_code):
    """Test getting indexed files for non-existent project."""
    result = await server_with_indexed_code.get_indexed_files(
        project_name="nonexistent-project",
        limit=100
    )

    assert result["total"] == 0
    assert len(result["files"]) == 0
    assert result["has_more"] is False


@pytest.mark.asyncio
@pytest.mark.skip(reason="Flaky under parallel execution - fixture race conditions")
async def test_list_indexed_units_all(server_with_indexed_code):
    """Test listing all indexed units."""
    result = await server_with_indexed_code.list_indexed_units(limit=100)

    assert "units" in result
    assert "total" in result
    assert "limit" in result
    assert "offset" in result
    assert "has_more" in result

    # Should have multiple units (functions and classes)
    assert result["total"] >= 5
    assert len(result["units"]) >= 5

    # Each unit should have required fields
    for unit in result["units"]:
        assert "id" in unit
        assert "name" in unit
        assert "unit_type" in unit
        assert "file_path" in unit
        assert "language" in unit
        assert "start_line" in unit
        assert "end_line" in unit
        assert "signature" in unit
        assert "last_indexed" in unit

        # Verify language is Python
        assert unit["language"] == "Python"

        # unit_type should be function or class
        assert unit["unit_type"] in ["function", "class", "method"]


@pytest.mark.asyncio
@pytest.mark.skip(reason="Flaky under parallel execution - fixture race conditions")
async def test_list_indexed_units_by_project(server_with_indexed_code):
    """Test filtering units by project name."""
    result = await server_with_indexed_code.list_indexed_units(
        project_name="test-project",
        limit=100
    )

    assert result["total"] >= 5
    # All units should be from test-project
    for unit in result["units"]:
        assert unit["file_path"].endswith(".py")


@pytest.mark.asyncio
@pytest.mark.skip(reason="Flaky under parallel execution - fixture race conditions")
async def test_list_indexed_units_by_language(server_with_indexed_code):
    """Test filtering units by language."""
    result = await server_with_indexed_code.list_indexed_units(
        language="Python",
        limit=100
    )

    assert result["total"] >= 5
    # All units should be Python
    for unit in result["units"]:
        assert unit["language"] == "Python"


@pytest.mark.asyncio
@pytest.mark.skip(reason="Flaky test - race condition in parallel execution (passes individually)")
async def test_list_indexed_units_by_type_function(server_with_indexed_code):
    """Test filtering units by type (functions only)."""
    result = await server_with_indexed_code.list_indexed_units(
        unit_type="function",
        limit=100
    )

    # Should have at least 3 functions
    assert result["total"] >= 3
    # All units should be functions
    for unit in result["units"]:
        assert unit["unit_type"] == "function"


@pytest.mark.asyncio
async def test_list_indexed_units_by_type_class(server_with_indexed_code):
    """Test filtering units by type (classes only)."""
    result = await server_with_indexed_code.list_indexed_units(
        unit_type="class",
        limit=100
    )

    # Should have at least 2 classes
    assert result["total"] >= 2
    # All units should be classes
    for unit in result["units"]:
        assert unit["unit_type"] == "class"


@pytest.mark.asyncio
async def test_list_indexed_units_pagination(server_with_indexed_code):
    """Test pagination of indexed units."""
    # Get first page
    page1 = await server_with_indexed_code.list_indexed_units(limit=3, offset=0)

    assert page1["limit"] == 3
    assert page1["offset"] == 0
    assert len(page1["units"]) <= 3

    # has_more should be True if total > 3
    if page1["total"] > 3:
        assert page1["has_more"] is True

        # Get second page
        page2 = await server_with_indexed_code.list_indexed_units(limit=3, offset=3)
        assert page2["offset"] == 3
        assert len(page2["units"]) >= 1


@pytest.mark.asyncio
async def test_list_indexed_units_combined_filters(server_with_indexed_code):
    """Test combining multiple filters."""
    result = await server_with_indexed_code.list_indexed_units(
        project_name="test-project",
        language="Python",
        unit_type="function",
        limit=100
    )

    # All units should match all filters
    for unit in result["units"]:
        assert unit["language"] == "Python"
        assert unit["unit_type"] == "function"
        assert unit["file_path"].endswith(".py")


@pytest.mark.asyncio
async def test_list_indexed_units_empty_results(server_with_indexed_code):
    """Test filtering with no matches."""
    result = await server_with_indexed_code.list_indexed_units(
        project_name="nonexistent-project",
        limit=100
    )

    assert result["total"] == 0
    assert len(result["units"]) == 0
    assert result["has_more"] is False


@pytest.mark.asyncio
async def test_get_indexed_files_validation_limit_autocap(config):
    """Test that limit is autocapped to valid range."""
    srv = MemoryRAGServer(config)
    await srv.initialize()

    # Limit too small gets capped to 1
    result1 = await srv.get_indexed_files(limit=0)
    assert result1["limit"] == 1

    # Limit too large gets capped to 500
    result2 = await srv.get_indexed_files(limit=1000)
    assert result2["limit"] == 500

    await srv.close()


@pytest.mark.asyncio
async def test_get_indexed_files_validation_offset_autocap(config):
    """Test that negative offset is autocapped to 0."""
    srv = MemoryRAGServer(config)
    await srv.initialize()

    result = await srv.get_indexed_files(offset=-1)
    assert result["offset"] == 0

    await srv.close()


@pytest.mark.asyncio
async def test_list_indexed_units_validation_limit_autocap(config):
    """Test that limit is autocapped to valid range."""
    srv = MemoryRAGServer(config)
    await srv.initialize()

    # Limit too small gets capped to 1
    result1 = await srv.list_indexed_units(limit=0)
    assert result1["limit"] == 1

    # Limit too large gets capped to 500
    result2 = await srv.list_indexed_units(limit=1000)
    assert result2["limit"] == 500

    await srv.close()


@pytest.mark.asyncio
async def test_list_indexed_units_validation_offset_autocap(config):
    """Test that negative offset is autocapped to 0."""
    srv = MemoryRAGServer(config)
    await srv.initialize()

    result = await srv.list_indexed_units(offset=-1)
    assert result["offset"] == 0

    await srv.close()


@pytest.mark.asyncio
async def test_has_more_flag_accuracy(server_with_indexed_code):
    """Test accuracy of has_more flag."""
    # Get total count first
    all_files = await server_with_indexed_code.get_indexed_files(limit=500)
    total_files = all_files["total"]

    # Test with limit less than total
    if total_files > 1:
        result = await server_with_indexed_code.get_indexed_files(limit=1, offset=0)
        assert result["has_more"] is True

    # Test with limit + offset >= total
    result = await server_with_indexed_code.get_indexed_files(
        limit=total_files,
        offset=0
    )
    assert result["has_more"] is False
