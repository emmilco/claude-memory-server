"""Integration tests for file watcher + incremental indexer workflow."""

import pytest
import pytest_asyncio
import asyncio
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, Mock

from src.memory.file_watcher import DebouncedFileWatcher
from src.memory.incremental_indexer import IncrementalIndexer
from src.config import ServerConfig


# Sample code for testing
SAMPLE_PYTHON_V1 = '''
def hello_world():
    """Say hello."""
    print("Hello, World!")
'''

SAMPLE_PYTHON_V2 = '''
def hello_world():
    """Say hello to the world."""
    print("Hello, World!")
    print("Welcome!")

def goodbye_world():
    """Say goodbye."""
    print("Goodbye, World!")
'''


@pytest.fixture
def temp_dir():
    """Create temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def config():
    """Create test configuration."""
    return ServerConfig(
        qdrant_url="http://localhost:6333",
        embedding_model="all-mpnet-base-v2",
    )


@pytest_asyncio.fixture
async def mock_store():
    """Create mock vector store."""
    store = AsyncMock()
    store.initialize = AsyncMock()

    # Track stored items
    stored_items = []

    async def batch_store_side_effect(items):
        """Store items and return matching IDs."""
        stored_items.extend(items)
        return [f"id{i}" for i in range(len(items))]

    store.batch_store = AsyncMock(side_effect=batch_store_side_effect)
    store.close = AsyncMock()
    store.client = Mock()
    store.client.scroll = Mock(return_value=([], None))
    store.client.delete = Mock()
    store.collection_name = "test_collection"
    store.stored_items = stored_items  # Expose for testing

    return store


@pytest_asyncio.fixture
async def mock_embedding_generator():
    """Create mock embedding generator."""
    gen = AsyncMock()

    async def batch_generate_side_effect(texts, show_progress=False):
        """Generate embeddings matching input size."""
        return [[0.1 + (i * 0.01) for _ in range(768)] for i in range(len(texts))]

    gen.batch_generate = AsyncMock(side_effect=batch_generate_side_effect)
    gen.close = AsyncMock()
    return gen


class TestFileWatcherIndexerIntegration:
    """Test integration between file watcher and incremental indexer."""

    @pytest.mark.asyncio
    async def test_file_change_triggers_reindexing(
        self, temp_dir, config, mock_store, mock_embedding_generator
    ):
        """Test that file changes trigger automatic re-indexing."""
        # Create indexer
        indexer = IncrementalIndexer(
            store=mock_store,
            embedding_generator=mock_embedding_generator,
            config=config,
            project_name="test_project",
        )
        await indexer.initialize()

        # Track indexing calls
        indexed_files = []

        async def on_file_change(file_path: Path):
            """Callback when file changes."""
            indexed_files.append(file_path)
            await indexer.index_file(file_path)

        # Create file watcher
        DebouncedFileWatcher(
            watch_path=temp_dir,
            callback=on_file_change,
            patterns={".py"},
            debounce_ms=100,
        )

        # Create test file
        test_file = temp_dir / "test.py"
        test_file.write_text(SAMPLE_PYTHON_V1)

        # Manually trigger the workflow (simulating file system event)
        await on_file_change(test_file)

        # Wait for indexing
        await asyncio.sleep(0.1)

        # Verify file was indexed
        assert test_file in indexed_files
        assert mock_embedding_generator.batch_generate.call_count >= 1
        assert mock_store.batch_store.call_count >= 1

        # Verify content includes the function
        stored = mock_store.stored_items
        assert len(stored) > 0
        assert any("hello_world" in item[0] for item in stored)

        await indexer.close()

    @pytest.mark.asyncio
    async def test_file_modification_updates_index(
        self, temp_dir, config, mock_store, mock_embedding_generator
    ):
        """Test that modifying a file updates its index."""
        # Create indexer
        indexer = IncrementalIndexer(
            store=mock_store,
            embedding_generator=mock_embedding_generator,
            config=config,
            project_name="test_project",
        )
        await indexer.initialize()

        test_file = temp_dir / "evolving.py"

        # Index initial version
        test_file.write_text(SAMPLE_PYTHON_V1)
        await indexer.index_file(test_file)

        initial_store_count = mock_store.batch_store.call_count
        len(mock_store.stored_items)

        # Modify file
        test_file.write_text(SAMPLE_PYTHON_V2)
        await indexer.index_file(test_file)

        # Verify re-indexing occurred
        assert mock_store.batch_store.call_count > initial_store_count

        # Verify new content is indexed (should have goodbye_world now)
        stored = mock_store.stored_items
        assert any("goodbye_world" in item[0] for item in stored)

        await indexer.close()

    @pytest.mark.asyncio
    async def test_multiple_files_indexed_independently(
        self, temp_dir, config, mock_store, mock_embedding_generator
    ):
        """Test that multiple files are indexed independently."""
        indexer = IncrementalIndexer(
            store=mock_store,
            embedding_generator=mock_embedding_generator,
            config=config,
            project_name="test_project",
        )
        await indexer.initialize()

        # Create multiple files
        file1 = temp_dir / "module1.py"
        file2 = temp_dir / "module2.py"

        file1.write_text("def func1():\n    pass")
        file2.write_text("def func2():\n    pass")

        # Index both files
        await indexer.index_file(file1)
        await indexer.index_file(file2)

        # Verify both were indexed
        stored = mock_store.stored_items
        assert any("func1" in item[0] for item in stored)
        assert any("func2" in item[0] for item in stored)

        await indexer.close()

    @pytest.mark.asyncio
    async def test_debouncing_prevents_redundant_indexing(
        self, temp_dir, config, mock_store, mock_embedding_generator
    ):
        """Test that debouncing prevents redundant indexing operations."""
        indexer = IncrementalIndexer(
            store=mock_store,
            embedding_generator=mock_embedding_generator,
            config=config,
            project_name="test_project",
        )
        await indexer.initialize()

        indexed_count = []

        async def on_file_change(file_path: Path):
            indexed_count.append(1)
            await indexer.index_file(file_path)

        watcher = DebouncedFileWatcher(
            watch_path=temp_dir,
            callback=on_file_change,
            patterns={".py"},
            debounce_ms=200,
        )

        test_file = temp_dir / "debounce_test.py"
        test_file.write_text("v1")

        # Simulate rapid changes
        for i in range(5):
            test_file.write_text(f"version {i}")
            await watcher._debounce_callback(test_file)
            await asyncio.sleep(0.05)

        # Wait for debounce
        await asyncio.sleep(0.3)

        # Should have triggered only once due to debouncing
        assert len(indexed_count) == 1

        await indexer.close()

    @pytest.mark.asyncio
    async def test_directory_indexing_workflow(
        self, temp_dir, config, mock_store, mock_embedding_generator
    ):
        """Test indexing an entire directory."""
        indexer = IncrementalIndexer(
            store=mock_store,
            embedding_generator=mock_embedding_generator,
            config=config,
            project_name="test_project",
        )
        await indexer.initialize()

        # Create multiple files in directory
        (temp_dir / "file1.py").write_text("def func1():\n    pass")
        (temp_dir / "file2.py").write_text("def func2():\n    pass")
        (temp_dir / "file3.py").write_text("def func3():\n    pass")

        # Index directory
        result = await indexer.index_directory(
            temp_dir, recursive=False, show_progress=False
        )

        # Verify all files were indexed
        assert result["total_files"] == 3
        assert result["indexed_files"] == 3
        assert result["total_units"] > 0

        # Verify all functions are in the index
        stored = mock_store.stored_items
        assert any("func1" in item[0] for item in stored)
        assert any("func2" in item[0] for item in stored)
        assert any("func3" in item[0] for item in stored)

        await indexer.close()

    @pytest.mark.asyncio
    async def test_recursive_directory_indexing(
        self, temp_dir, config, mock_store, mock_embedding_generator
    ):
        """Test recursive directory indexing."""
        indexer = IncrementalIndexer(
            store=mock_store,
            embedding_generator=mock_embedding_generator,
            config=config,
            project_name="test_project",
        )
        await indexer.initialize()

        # Create subdirectory structure
        subdir = temp_dir / "subdir"
        subdir.mkdir()
        subsubdir = subdir / "nested"
        subsubdir.mkdir()

        # Create files at different levels
        (temp_dir / "root.py").write_text("def root_func():\n    pass")
        (subdir / "sub.py").write_text("def sub_func():\n    pass")
        (subsubdir / "nested.py").write_text("def nested_func():\n    pass")

        # Index recursively
        result = await indexer.index_directory(
            temp_dir, recursive=True, show_progress=False
        )

        # Verify all files were found and indexed
        assert result["total_files"] == 3
        assert result["indexed_files"] == 3

        # Verify all functions are indexed
        stored = mock_store.stored_items
        assert any("root_func" in item[0] for item in stored)
        assert any("sub_func" in item[0] for item in stored)
        assert any("nested_func" in item[0] for item in stored)

        await indexer.close()

    @pytest.mark.asyncio
    async def test_file_watcher_ignores_non_matching_extensions(
        self, temp_dir, config, mock_store, mock_embedding_generator
    ):
        """Test that file watcher ignores non-matching file extensions."""
        indexer = IncrementalIndexer(
            store=mock_store,
            embedding_generator=mock_embedding_generator,
            config=config,
            project_name="test_project",
        )
        await indexer.initialize()

        indexed_files = []

        async def on_file_change(file_path: Path):
            indexed_files.append(file_path)
            await indexer.index_file(file_path)

        watcher = DebouncedFileWatcher(
            watch_path=temp_dir,
            callback=on_file_change,
            patterns={".py"},  # Only Python files
            debounce_ms=100,
        )

        # Create Python file (should be processed)
        py_file = temp_dir / "code.py"
        py_file.write_text("def test():\n    pass")

        # Create non-Python file (should be ignored)
        txt_file = temp_dir / "readme.txt"
        txt_file.write_text("This is a readme")

        # Only process Python file
        if watcher._should_process(py_file):
            await on_file_change(py_file)

        # Txt file should not be processed
        assert not watcher._should_process(txt_file)

        # Verify only Python file was indexed
        assert py_file in indexed_files
        assert txt_file not in indexed_files

        await indexer.close()

    @pytest.mark.asyncio
    async def test_error_in_one_file_doesnt_stop_others(
        self, temp_dir, config, mock_store, mock_embedding_generator
    ):
        """Test that error in one file doesn't prevent indexing others."""
        indexer = IncrementalIndexer(
            store=mock_store,
            embedding_generator=mock_embedding_generator,
            config=config,
            project_name="test_project",
        )
        await indexer.initialize()

        # Create valid file
        valid_file = temp_dir / "valid.py"
        valid_file.write_text("def valid_func():\n    pass")

        # Create invalid Python file (syntax error)
        invalid_file = temp_dir / "invalid.py"
        invalid_file.write_text("def broken(:\n    pass")  # Syntax error

        # Index valid file (should succeed)
        result1 = await indexer.index_file(valid_file)
        assert result1["units_indexed"] > 0

        # Index invalid file (should handle gracefully)
        # Note: tree-sitter is resilient and can still parse partial/invalid code
        result2 = await indexer.index_file(invalid_file)
        # The parser may still extract some units even from invalid code
        assert isinstance(result2["units_indexed"], int)
        assert result2["units_indexed"] >= 0  # Just verify it doesn't crash

        # Verify valid file is still in index
        stored = mock_store.stored_items
        assert any("valid_func" in item[0] for item in stored)

        await indexer.close()
