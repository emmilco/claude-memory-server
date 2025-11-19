"""Tests for indexed content visibility features (FEAT-046)."""

import pytest
import pytest_asyncio
import asyncio
from pathlib import Path
from datetime import datetime, UTC

from src.store.sqlite_store import SQLiteMemoryStore
from src.core.server import MemoryRAGServer
from src.config import ServerConfig


@pytest_asyncio.fixture
async def sqlite_store():
    """Create a temporary SQLite store for testing."""
    config = ServerConfig(
        storage_backend="sqlite",
        sqlite_path=":memory:",  # In-memory database
    )
    store = SQLiteMemoryStore(config)
    await store.initialize()
    yield store
    await store.close()


@pytest_asyncio.fixture
async def sample_indexed_code(sqlite_store):
    """Create sample indexed code units for testing."""
    # Sample Python function
    await sqlite_store.store(
        content="def hello_world():\n    print('Hello')",
        embedding=[0.1] * 384,
        metadata={
            "id": "unit-1",
            "category": "code",
            "context_level": "CORE",
            "scope": "project",
            "project_name": "test-project",
            "importance": 0.8,
            "metadata": {
                "name": "hello_world",
                "unit_type": "function",
                "file_path": "/test/hello.py",
                "language": "Python",
                "start_line": 1,
                "end_line": 2,
                "signature": "def hello_world()",
            },
        },
    )

    # Sample JavaScript class
    await sqlite_store.store(
        content="class User { constructor(name) { this.name = name; } }",
        embedding=[0.2] * 384,
        metadata={
            "id": "unit-2",
            "category": "code",
            "context_level": "CORE",
            "scope": "project",
            "project_name": "test-project",
            "importance": 0.9,
            "metadata": {
                "name": "User",
                "unit_type": "class",
                "file_path": "/test/user.js",
                "language": "JavaScript",
                "start_line": 1,
                "end_line": 1,
                "signature": "class User",
            },
        },
    )

    # Sample Python class from different file
    await sqlite_store.store(
        content="class MyClass:\n    pass",
        embedding=[0.3] * 384,
        metadata={
            "id": "unit-3",
            "category": "code",
            "context_level": "DETAIL",
            "scope": "project",
            "project_name": "test-project",
            "importance": 0.5,
            "metadata": {
                "name": "MyClass",
                "unit_type": "class",
                "file_path": "/test/classes.py",
                "language": "Python",
                "start_line": 1,
                "end_line": 2,
                "signature": "class MyClass",
            },
        },
    )

    return sqlite_store


@pytest.mark.asyncio
async def test_get_indexed_files_all(sample_indexed_code):
    """Test getting all indexed files."""
    result = await sample_indexed_code.get_indexed_files()

    assert "files" in result
    assert "total" in result
    assert "limit" in result
    assert "offset" in result

    assert result["total"] == 3  # 3 unique files
    assert len(result["files"]) == 3
    assert result["limit"] == 50
    assert result["offset"] == 0

    # Check file details
    file_paths = {f["file_path"] for f in result["files"]}
    assert "/test/hello.py" in file_paths
    assert "/test/user.js" in file_paths
    assert "/test/classes.py" in file_paths


@pytest.mark.asyncio
async def test_get_indexed_files_with_project(sample_indexed_code):
    """Test filtering files by project."""
    result = await sample_indexed_code.get_indexed_files(project_name="test-project")

    assert result["total"] == 3
    assert len(result["files"]) == 3


@pytest.mark.asyncio
async def test_get_indexed_files_pagination(sample_indexed_code):
    """Test pagination of indexed files."""
    # Get first page (limit 2)
    result = await sample_indexed_code.get_indexed_files(limit=2, offset=0)

    assert result["total"] == 3
    assert len(result["files"]) == 2
    assert result["limit"] == 2
    assert result["offset"] == 0

    # Get second page
    result_page2 = await sample_indexed_code.get_indexed_files(limit=2, offset=2)

    assert result_page2["total"] == 3
    assert len(result_page2["files"]) == 1
    assert result_page2["offset"] == 2


@pytest.mark.asyncio
async def test_list_indexed_units_all(sample_indexed_code):
    """Test listing all indexed units."""
    result = await sample_indexed_code.list_indexed_units()

    assert "units" in result
    assert "total" in result
    assert "limit" in result
    assert "offset" in result

    assert result["total"] == 3
    assert len(result["units"]) == 3

    # Check unit details
    unit_names = {u["name"] for u in result["units"]}
    assert "hello_world" in unit_names
    assert "User" in unit_names
    assert "MyClass" in unit_names


@pytest.mark.asyncio
async def test_list_indexed_units_filter_by_language(sample_indexed_code):
    """Test filtering units by language."""
    # Filter Python units
    result = await sample_indexed_code.list_indexed_units(language="Python")

    assert result["total"] == 2  # hello_world and MyClass
    assert len(result["units"]) == 2

    unit_names = {u["name"] for u in result["units"]}
    assert "hello_world" in unit_names
    assert "MyClass" in unit_names
    assert "User" not in unit_names


@pytest.mark.asyncio
async def test_list_indexed_units_filter_by_file_pattern(sample_indexed_code):
    """Test filtering units by file pattern."""
    # Filter .py files
    result = await sample_indexed_code.list_indexed_units(file_pattern="%.py")

    assert result["total"] == 2  # Files ending with .py
    assert len(result["units"]) == 2

    # Filter specific directory
    result_js = await sample_indexed_code.list_indexed_units(file_pattern="%.js")

    assert result_js["total"] == 1  # Only user.js
    assert len(result_js["units"]) == 1
    assert result_js["units"][0]["name"] == "User"


@pytest.mark.asyncio
async def test_list_indexed_units_filter_by_unit_type(sample_indexed_code):
    """Test filtering units by unit type."""
    # Filter functions
    result = await sample_indexed_code.list_indexed_units(unit_type="function")

    assert result["total"] == 1  # Only hello_world
    assert len(result["units"]) == 1
    assert result["units"][0]["name"] == "hello_world"

    # Filter classes
    result_classes = await sample_indexed_code.list_indexed_units(unit_type="class")

    assert result_classes["total"] == 2  # User and MyClass
    assert len(result_classes["units"]) == 2


@pytest.mark.asyncio
async def test_list_indexed_units_combined_filters(sample_indexed_code):
    """Test combining multiple filters."""
    # Filter Python classes
    result = await sample_indexed_code.list_indexed_units(
        language="Python",
        unit_type="class",
    )

    assert result["total"] == 1  # Only MyClass
    assert len(result["units"]) == 1
    assert result["units"][0]["name"] == "MyClass"


@pytest.mark.asyncio
async def test_list_indexed_units_pagination(sample_indexed_code):
    """Test pagination of indexed units."""
    # Get first page
    result = await sample_indexed_code.list_indexed_units(limit=2, offset=0)

    assert result["total"] == 3
    assert len(result["units"]) == 2
    assert result["limit"] == 2
    assert result["offset"] == 0

    # Get second page
    result_page2 = await sample_indexed_code.list_indexed_units(limit=2, offset=2)

    assert result_page2["total"] == 3
    assert len(result_page2["units"]) == 1
    assert result_page2["offset"] == 2


@pytest.mark.asyncio
async def test_empty_results(sqlite_store):
    """Test handling of empty results."""
    # No indexed code yet
    result = await sqlite_store.get_indexed_files()

    assert result["total"] == 0
    assert len(result["files"]) == 0

    result_units = await sqlite_store.list_indexed_units()

    assert result_units["total"] == 0
    assert len(result_units["units"]) == 0


@pytest.mark.asyncio
async def test_limit_validation(sample_indexed_code):
    """Test limit validation and capping."""
    # Test limit < 1 (should be capped to 1)
    result = await sample_indexed_code.get_indexed_files(limit=0)
    assert result["limit"] == 1

    # Test limit > 500 (should be capped to 500)
    result = await sample_indexed_code.get_indexed_files(limit=1000)
    assert result["limit"] == 500


@pytest.mark.asyncio
async def test_unit_metadata_completeness(sample_indexed_code):
    """Test that all expected metadata fields are present."""
    result = await sample_indexed_code.list_indexed_units(limit=1)

    assert len(result["units"]) == 1
    unit = result["units"][0]

    # Check all expected fields are present
    assert "id" in unit
    assert "name" in unit
    assert "unit_type" in unit
    assert "file_path" in unit
    assert "language" in unit
    assert "start_line" in unit
    assert "end_line" in unit
    assert "signature" in unit
    assert "last_indexed" in unit


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
