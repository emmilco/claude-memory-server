"""Tests for incremental code indexer."""

import pytest
import pytest_asyncio
import asyncio
import tempfile
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch

from src.memory.incremental_indexer import IncrementalIndexer
from src.config import ServerConfig


# Sample Python code for testing
SAMPLE_PYTHON_CODE = '''
def calculate_sum(a, b):
    """Calculate the sum of two numbers."""
    return a + b

class Calculator:
    """A simple calculator class."""

    def __init__(self):
        self.result = 0

    def add(self, value):
        """Add a value to the result."""
        self.result += value
        return self.result
'''

SAMPLE_JAVASCRIPT_CODE = '''
function greet(name) {
    return `Hello, ${name}!`;
}

class Person {
    constructor(name) {
        this.name = name;
    }

    introduce() {
        return `I am ${this.name}`;
    }
}
'''


@pytest.fixture
def config():
    """Create test configuration."""
    return ServerConfig(
        qdrant_url="http://localhost:6333",
        embedding_model="all-MiniLM-L6-v2",
    )


@pytest.fixture
def temp_dir():
    """Create temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_python_file(temp_dir):
    """Create sample Python file."""
    file_path = temp_dir / "sample.py"
    file_path.write_text(SAMPLE_PYTHON_CODE)
    return file_path


@pytest.fixture
def sample_js_file(temp_dir):
    """Create sample JavaScript file."""
    file_path = temp_dir / "sample.js"
    file_path.write_text(SAMPLE_JAVASCRIPT_CODE)
    return file_path


@pytest_asyncio.fixture
async def mock_store():
    """Create mock vector store."""
    store = AsyncMock()
    store.initialize = AsyncMock()
    
    # Smart mock that returns IDs matching input size
    async def batch_store_side_effect(items):
        """Store items and return matching IDs."""
        return [f"id{i}" for i in range(len(items))]
    
    store.batch_store = AsyncMock(side_effect=batch_store_side_effect)
    store.close = AsyncMock()
    store.client = Mock()
    store.client.scroll = Mock(return_value=([Mock(id="id1")], None))
    store.client.delete = Mock()
    store.collection_name = "test_collection"
    return store


@pytest_asyncio.fixture
async def mock_embedding_generator():
    """Create mock embedding generator."""
    gen = AsyncMock()
    
    # Smart mock that returns embeddings matching input size
    async def batch_generate_side_effect(texts, show_progress=False):
        """Generate embeddings matching input size."""
        # Return one embedding per text
        return [[0.1 + (i * 0.01) for _ in range(384)] for i in range(len(texts))]
    
    gen.batch_generate = AsyncMock(side_effect=batch_generate_side_effect)
    gen.close = AsyncMock()
    return gen


class TestIncrementalIndexer:
    """Tests for IncrementalIndexer class."""

    @pytest.mark.asyncio
    async def test_initialization(self, config, mock_store, mock_embedding_generator):
        """Test indexer initialization."""
        indexer = IncrementalIndexer(
            store=mock_store,
            embedding_generator=mock_embedding_generator,
            config=config,
            project_name="test_project",
        )

        assert indexer.project_name == "test_project"
        assert indexer.config == config

        await indexer.initialize()
        mock_store.initialize.assert_called_once()

        await indexer.close()

    @pytest.mark.asyncio
    async def test_index_python_file(self, sample_python_file, config, mock_store, mock_embedding_generator):
        """Test indexing a Python file."""
        indexer = IncrementalIndexer(
            store=mock_store,
            embedding_generator=mock_embedding_generator,
            config=config,
            project_name="test_project",
        )

        await indexer.initialize()

        # Index the file
        result = await indexer.index_file(sample_python_file)

        # Verify results
        assert result["units_indexed"] > 0  # Should find at least the function and class
        assert "parse_time_ms" in result
        assert result["language"] == "Python"
        assert len(result["unit_ids"]) == result["units_indexed"]

        # Verify embeddings were generated
        mock_embedding_generator.batch_generate.assert_called_once()

        # Verify units were stored
        mock_store.batch_store.assert_called_once()

        await indexer.close()

    @pytest.mark.asyncio
    async def test_index_javascript_file(self, sample_js_file, config, mock_store, mock_embedding_generator):
        """Test indexing a JavaScript file."""
        indexer = IncrementalIndexer(
            store=mock_store,
            embedding_generator=mock_embedding_generator,
            config=config,
            project_name="test_project",
        )

        await indexer.initialize()

        # Index the file
        result = await indexer.index_file(sample_js_file)

        # Verify results
        assert result["units_indexed"] > 0
        assert result["language"] == "JavaScript"

        await indexer.close()

    @pytest.mark.asyncio
    async def test_index_unsupported_file(self, temp_dir, config, mock_store, mock_embedding_generator):
        """Test that unsupported files are skipped."""
        # Create unsupported file
        unsupported_file = temp_dir / "test.txt"
        unsupported_file.write_text("This is a text file")

        indexer = IncrementalIndexer(
            store=mock_store,
            embedding_generator=mock_embedding_generator,
            config=config,
            project_name="test_project",
        )

        await indexer.initialize()

        # Index the file
        result = await indexer.index_file(unsupported_file)

        # Verify it was skipped
        assert result["units_indexed"] == 0
        assert result.get("skipped") is True

        # Verify no embeddings or storage calls
        mock_embedding_generator.batch_generate.assert_not_called()
        mock_store.batch_store.assert_not_called()

        await indexer.close()

    @pytest.mark.asyncio
    async def test_index_directory(self, temp_dir, config, mock_store, mock_embedding_generator):
        """Test indexing an entire directory."""
        # Create multiple files
        (temp_dir / "file1.py").write_text(SAMPLE_PYTHON_CODE)
        (temp_dir / "file2.py").write_text(SAMPLE_PYTHON_CODE)
        (temp_dir / "file3.js").write_text(SAMPLE_JAVASCRIPT_CODE)

        indexer = IncrementalIndexer(
            store=mock_store,
            embedding_generator=mock_embedding_generator,
            config=config,
            project_name="test_project",
        )

        await indexer.initialize()

        # Index directory
        result = await indexer.index_directory(temp_dir, recursive=False, show_progress=False)

        # Verify results
        assert result["total_files"] == 3
        assert result["indexed_files"] == 3
        assert result["total_units"] > 0

        # Verify embeddings were generated multiple times
        assert mock_embedding_generator.batch_generate.call_count == 3

        await indexer.close()

    @pytest.mark.asyncio
    async def test_delete_file_units(self, sample_python_file, config, mock_store, mock_embedding_generator):
        """Test deleting units for a specific file."""
        indexer = IncrementalIndexer(
            store=mock_store,
            embedding_generator=mock_embedding_generator,
            config=config,
            project_name="test_project",
        )

        await indexer.initialize()

        # Delete units
        deleted_count = await indexer._delete_file_units(sample_python_file)

        # Verify deletion
        assert deleted_count == 1  # Mock returns 1 point
        mock_store.client.scroll.assert_called_once()
        mock_store.client.delete.assert_called_once()

        await indexer.close()

    @pytest.mark.asyncio
    async def test_build_indexable_content(self, sample_python_file, config, mock_store, mock_embedding_generator):
        """Test building indexable content from semantic unit."""
        from mcp_performance_core import parse_source_file

        indexer = IncrementalIndexer(
            store=mock_store,
            embedding_generator=mock_embedding_generator,
            config=config,
            project_name="test_project",
        )

        # Parse a file to get semantic units
        parse_result = parse_source_file(str(sample_python_file), SAMPLE_PYTHON_CODE)

        assert len(parse_result.units) > 0

        # Build indexable content for first unit
        unit = parse_result.units[0]
        content = indexer._build_indexable_content(sample_python_file, unit)

        # Verify format
        assert "File:" in content
        assert str(sample_python_file.name) in content
        assert unit.name in content
        assert "Signature:" in content
        assert "Content:" in content

    @pytest.mark.asyncio
    async def test_index_file_updates_existing(self, sample_python_file, config, mock_store, mock_embedding_generator):
        """Test that re-indexing a file deletes old units first."""
        indexer = IncrementalIndexer(
            store=mock_store,
            embedding_generator=mock_embedding_generator,
            config=config,
            project_name="test_project",
        )

        await indexer.initialize()

        # Index file twice
        await indexer.index_file(sample_python_file)
        await indexer.index_file(sample_python_file)

        # Verify deletion was called (old units removed before new ones added)
        assert mock_store.client.scroll.call_count == 2
        assert mock_store.client.delete.call_count == 2

        await indexer.close()

    @pytest.mark.asyncio
    async def test_index_nonexistent_file(self, temp_dir, config, mock_store, mock_embedding_generator):
        """Test that indexing a non-existent file raises error."""
        nonexistent = temp_dir / "nonexistent.py"

        indexer = IncrementalIndexer(
            store=mock_store,
            embedding_generator=mock_embedding_generator,
            config=config,
            project_name="test_project",
        )

        await indexer.initialize()

        # Should raise FileNotFoundError
        with pytest.raises(FileNotFoundError):
            await indexer.index_file(nonexistent)

        await indexer.close()

    @pytest.mark.asyncio
    async def test_recursive_directory_indexing(self, temp_dir, config, mock_store, mock_embedding_generator):
        """Test recursive directory indexing."""
        # Create subdirectory with files
        subdir = temp_dir / "subdir"
        subdir.mkdir()
        (subdir / "file1.py").write_text(SAMPLE_PYTHON_CODE)
        (temp_dir / "file2.py").write_text(SAMPLE_PYTHON_CODE)

        indexer = IncrementalIndexer(
            store=mock_store,
            embedding_generator=mock_embedding_generator,
            config=config,
            project_name="test_project",
        )

        await indexer.initialize()

        # Index recursively
        result = await indexer.index_directory(temp_dir, recursive=True, show_progress=False)

        # Should find both files
        assert result["total_files"] == 2
        assert result["indexed_files"] == 2

        await indexer.close()

    @pytest.mark.asyncio
    async def test_skip_hidden_files(self, temp_dir, config, mock_store, mock_embedding_generator):
        """Test that hidden files are skipped."""
        # Create hidden file
        (temp_dir / ".hidden.py").write_text(SAMPLE_PYTHON_CODE)
        (temp_dir / "visible.py").write_text(SAMPLE_PYTHON_CODE)

        indexer = IncrementalIndexer(
            store=mock_store,
            embedding_generator=mock_embedding_generator,
            config=config,
            project_name="test_project",
        )

        await indexer.initialize()

        result = await indexer.index_directory(temp_dir, recursive=False, show_progress=False)

        # Should only find visible file
        assert result["total_files"] == 1

        await indexer.close()
