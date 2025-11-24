"""Tests for index_codebase initialization bug (QA investigation)."""

import pytest
import pytest_asyncio
import tempfile
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch, MagicMock

from src.core.server import MemoryRAGServer
from src.config import ServerConfig
from src.memory.incremental_indexer import IncrementalIndexer
from src.embeddings.parallel_generator import ParallelEmbeddingGenerator


@pytest.fixture
def config():
    """Create test configuration with parallel embeddings enabled."""
    return ServerConfig(
        storage_backend="qdrant",
        qdrant_url="http://localhost:6333",
        qdrant_collection_name="test_index_init",
        enable_parallel_embeddings=True,  # This is the critical setting
        embedding_parallel_workers=2,
    )


@pytest_asyncio.fixture
async def server(config):
    """Create initialized server."""
    server = MemoryRAGServer(config=config)
    await server.initialize()
    yield server
    await server.close()


@pytest.fixture
def temp_codebase():
    """Create temporary codebase with sample files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create sample Python file
        (tmpdir / "example.py").write_text('''
def hello_world():
    """Say hello."""
    return "Hello, World!"

class Greeter:
    """A greeter class."""

    def greet(self, name):
        """Greet someone."""
        return f"Hello, {name}!"
''')

        # Create sample JavaScript file
        (tmpdir / "example.js").write_text('''
function add(a, b) {
    return a + b;
}

class Calculator {
    subtract(a, b) {
        return a - b;
    }
}
''')

        yield tmpdir


class TestIndexCodebaseInitialization:
    """Test that index_codebase properly initializes the indexer."""

    @pytest.mark.asyncio
    async def test_indexer_is_initialized_before_indexing(self, server, temp_codebase):
        """
        Test that the IncrementalIndexer.initialize() is called.

        This verifies the fix for the bug where initialization was skipped
        in src/core/server.py:2915, causing the ParallelEmbeddingGenerator
        executor to remain None.
        """
        with patch.object(IncrementalIndexer, 'initialize', new_callable=AsyncMock) as mock_init:
            # Also need to mock index_directory to avoid actual indexing
            with patch.object(IncrementalIndexer, 'index_directory', new_callable=AsyncMock) as mock_index:
                mock_index.return_value = {
                    "total_files": 2,
                    "indexed_files": 2,
                    "total_units": 4,
                    "skipped_files": 0,
                    "failed_files": [],
                    "cleaned_entries": 0,
                }

                # Call index_codebase
                result = await server.index_codebase(
                    directory_path=str(temp_codebase),
                    project_name="test_project",
                    recursive=True,
                )

                # CRITICAL ASSERTION: initialize() must be called
                mock_init.assert_called_once()

                # Verify indexing happened
                assert mock_index.called
                assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_parallel_embedding_generator_executor_is_initialized(self, config, temp_codebase):
        """
        Test that ParallelEmbeddingGenerator.executor is not None after initialization.

        This directly tests the symptom of the bug: when initialize() is skipped,
        the ProcessPoolExecutor remains None, causing performance issues.
        """
        from src.store import create_memory_store

        # Create store
        store = create_memory_store(config=config)
        await store.initialize()

        # Create indexer with parallel embeddings
        indexer = IncrementalIndexer(
            store=store,
            config=config,
            project_name="test_project",
        )

        # Check that embedding_generator is ParallelEmbeddingGenerator
        assert isinstance(indexer.embedding_generator, ParallelEmbeddingGenerator)

        # BEFORE initialization: executor should be None
        assert indexer.embedding_generator.executor is None

        # Call initialize
        await indexer.initialize()

        # AFTER initialization: executor should be a ProcessPoolExecutor
        assert indexer.embedding_generator.executor is not None

        # Clean up
        await indexer.close()
        await store.close()

    @pytest.mark.asyncio
    @pytest.mark.skip_ci  # Performance test may exceed CI timeout
    async def test_indexing_performance_with_initialization(self, server, temp_codebase, mock_embeddings):
        """
        Test that indexing completes in reasonable time when properly initialized.

        This is a regression test to ensure the performance issue is fixed.
        """
        import time

        start_time = time.time()

        # Index the temporary codebase
        result = await server.index_codebase(
            directory_path=str(temp_codebase),
            project_name="test_perf",
            recursive=True,
        )

        elapsed_time = time.time() - start_time

        # With proper initialization and 2 small files, this should complete quickly
        # Even with real embedding generation, <5 seconds is reasonable
        # With mocked embeddings, should be <1 second
        assert elapsed_time < 5.0, f"Indexing took too long: {elapsed_time:.2f}s"

        # Verify successful indexing
        assert result["status"] == "success"
        assert result["files_indexed"] >= 2  # At least our 2 test files

    @pytest.mark.asyncio
    async def test_indexer_initialization_called_even_with_initialized_store(self, config, temp_codebase):
        """
        Test that indexer.initialize() is called even when store is already initialized.

        The bug was caused by the assumption that "store is already initialized"
        meant the indexer didn't need initialization. This test verifies that's fixed.
        """
        from src.store import create_memory_store

        # Create and initialize store
        store = create_memory_store(config=config)
        await store.initialize()

        # Store is now initialized
        assert store.client is not None  # For Qdrant

        # Create server with the already-initialized store
        server = MemoryRAGServer(config=config)
        server.store = store  # Use pre-initialized store
        server.embedding_generator = server.store  # Mock to avoid actual generation

        with patch.object(IncrementalIndexer, 'initialize', new_callable=AsyncMock) as mock_init:
            with patch.object(IncrementalIndexer, 'index_directory', new_callable=AsyncMock) as mock_index:
                mock_index.return_value = {
                    "total_files": 0,
                    "indexed_files": 0,
                    "total_units": 0,
                    "skipped_files": 0,
                    "failed_files": [],
                    "cleaned_entries": 0,
                }

                # Call index_codebase
                await server.index_codebase(
                    directory_path=str(temp_codebase),
                    project_name="test",
                )

                # CRITICAL: initialize() must still be called despite store being initialized
                mock_init.assert_called_once()

        await store.close()


@pytest.fixture
def mock_embeddings(monkeypatch):
    """Mock embedding generation for faster tests."""
    async def mock_batch_generate(self, texts, **kwargs):
        # Return dummy 384-dim embeddings
        return [[0.1] * 384 for _ in texts]

    # Patch both generators
    monkeypatch.setattr(
        "src.embeddings.generator.EmbeddingGenerator.batch_generate",
        mock_batch_generate
    )
    monkeypatch.setattr(
        "src.embeddings.parallel_generator.ParallelEmbeddingGenerator.batch_generate",
        mock_batch_generate
    )
