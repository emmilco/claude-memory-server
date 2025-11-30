"""Final targeted tests to push coverage to 85%."""

import pytest
import pytest_asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, UTC

from src.memory.incremental_indexer import IncrementalIndexer
from src.embeddings.generator import EmbeddingGenerator
from src.embeddings.cache import EmbeddingCache
from src.config import ServerConfig, get_config
from tests.conftest import mock_embedding


class TestIncrementalIndexerAdditional:
    """Additional incremental indexer tests for coverage."""

    @pytest.mark.asyncio
    async def test_index_file_with_progress(self, tmp_path):
        """Test indexing file with progress callback."""
        indexer = IncrementalIndexer(project_name="test")
        test_file = tmp_path / "test.py"
        test_file.write_text("def hello():\n    return 'world'")

        with patch.object(indexer.store, 'initialize', new_callable=AsyncMock):
            with patch.object(indexer.store, 'batch_store', new_callable=AsyncMock) as mock_store:
                indexer.is_initialized = True
                mock_store.return_value = ["id1", "id2"]

                result = await indexer.index_file(test_file)

                assert "units_indexed" in result
                assert "file_path" in result

    @pytest.mark.asyncio
    async def test_index_directory_with_progress_callback(self, tmp_path):
        """Test directory indexing with progress display."""
        indexer = IncrementalIndexer(project_name="test")

        # Create test files
        (tmp_path / "file1.py").write_text("def func1(): pass")
        (tmp_path / "file2.py").write_text("def func2(): pass")

        with patch.object(indexer.store, 'initialize', new_callable=AsyncMock):
            with patch.object(indexer.store, 'batch_store', new_callable=AsyncMock):
                indexer.is_initialized = True

                result = await indexer.index_directory(
                    tmp_path,
                    recursive=False,
                    show_progress=True
                )

                assert "total_files" in result
                assert "indexed_files" in result

    @pytest.mark.asyncio
    async def test_index_file_parse_error(self, tmp_path):
        """Test handling of file with parse errors."""
        indexer = IncrementalIndexer(project_name="test")
        bad_file = tmp_path / "bad.py"
        bad_file.write_text("def incomplete(")  # Syntax error

        with patch.object(indexer.store, 'initialize', new_callable=AsyncMock):
            indexer.is_initialized = True

            result = await indexer.index_file(bad_file)

            # Should handle parse error gracefully
            assert "units_indexed" in result or "skipped" in result

    @pytest.mark.asyncio
    async def test_index_binary_file(self, tmp_path):
        """Test indexing binary file (should skip)."""
        indexer = IncrementalIndexer(project_name="test")
        binary_file = tmp_path / "test.bin"
        binary_file.write_bytes(b'\x00\x01\x02\x03')

        with patch.object(indexer.store, 'initialize', new_callable=AsyncMock):
            indexer.is_initialized = True

            result = await indexer.index_file(binary_file)

            # Should skip binary files
            assert result.get("skipped") is True or result["units_indexed"] == 0


class TestCacheAdditional:
    """Additional cache tests for coverage."""

    @pytest.mark.asyncio
    async def test_cache_multiple_models(self, tmp_path):
        """Test caching for multiple models."""
        config = ServerConfig(
            embedding_cache_enabled=True,
            embedding_cache_path=str(tmp_path / "cache.db")
        )
        cache = EmbeddingCache(config)

        text = "test"
        emb1 = mock_embedding(value=0.1)
        emb2 = mock_embedding(value=0.2)

        # Cache for different models
        await cache.set(text, "model1", emb1)
        await cache.set(text, "model2", emb2)

        # Retrieve each
        result1 = await cache.get(text, "model1")
        result2 = await cache.get(text, "model2")

        assert result1 is not None
        assert result2 is not None
        assert len(result1) == len(emb1)
        assert len(result2) == len(emb2)

        cache.close()

    @pytest.mark.asyncio
    async def test_cache_stats_after_operations(self, tmp_path):
        """Test cache statistics tracking."""
        config = ServerConfig(
            embedding_cache_enabled=True,
            embedding_cache_path=str(tmp_path / "cache.db")
        )
        cache = EmbeddingCache(config)

        # Perform operations
        await cache.set("text1", "model", mock_embedding(value=0.1))
        await cache.set("text2", "model", mock_embedding(value=0.2))

        await cache.get("text1", "model")  # Hit
        await cache.get("text1", "model")  # Hit
        await cache.get("text3", "model")  # Miss

        stats = cache.get_stats()

        assert stats["hits"] == 2
        assert stats["misses"] == 1
        assert stats["total_entries"] >= 2
        assert 0.0 <= stats["hit_rate"] <= 1.0

        cache.close()


class TestConfigAdditional:
    """Additional config tests for coverage."""

    def test_config_qdrant_collection_name(self):
        """Test qdrant collection name configuration."""
        config = ServerConfig(qdrant_collection_name="custom_collection")

        assert config.qdrant_collection_name == "custom_collection"

    def test_config_embedding_cache_ttl(self):
        """Test embedding cache TTL configuration."""
        config = ServerConfig(embedding_cache_ttl_days=7)

        assert config.embedding_cache_ttl_days == 7

    def test_config_read_only_mode(self):
        """Test read-only mode configuration."""
        config = ServerConfig(advanced={"read_only_mode": True})

        assert config.advanced.read_only_mode is True

    def test_config_log_level(self):
        """Test log level configuration."""
        for level in ["DEBUG", "INFO", "WARNING", "ERROR"]:
            config = ServerConfig(log_level=level)
            assert config.log_level == level

    def test_get_config_singleton(self):
        """Test get_config returns config."""
        config = get_config()

        assert config is not None
        assert isinstance(config, ServerConfig)


class TestModelsAdditional:
    """Additional model tests for coverage."""

    def test_memory_unit_creation_with_defaults(self):
        """Test MemoryUnit with default values."""
        from src.core.models import MemoryUnit, MemoryCategory, MemoryScope

        memory = MemoryUnit(
            content="Test content",
            category=MemoryCategory.FACT,
            scope=MemoryScope.GLOBAL,
        )

        assert memory.content == "Test content"
        assert memory.category == MemoryCategory.FACT
        assert memory.importance >= 0.0
        assert memory.tags == []

    def test_search_filters_all_options(self):
        """Test SearchFilters with all options."""
        from src.core.models import SearchFilters, MemoryCategory, ContextLevel, MemoryScope

        filters = SearchFilters(
            category=MemoryCategory.PREFERENCE,
            context_level=ContextLevel.USER_PREFERENCE,
            scope=MemoryScope.GLOBAL,
            project_name="test-project",
            min_importance=0.7,
        )

        assert filters.category == MemoryCategory.PREFERENCE
        assert filters.context_level == ContextLevel.USER_PREFERENCE
        assert filters.scope == MemoryScope.GLOBAL
        assert filters.project_name == "test-project"
        assert filters.min_importance == 0.7


