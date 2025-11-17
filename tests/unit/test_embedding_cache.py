"""Comprehensive tests for EmbeddingCache."""

import pytest
import pytest_asyncio
from pathlib import Path
from datetime import datetime, timedelta, UTC
from unittest.mock import AsyncMock, patch, MagicMock
from src.embeddings.cache import EmbeddingCache
from src.config import ServerConfig


@pytest.fixture
def cache_config(tmp_path):
    """Create test configuration with temporary cache."""
    cache_path = tmp_path / "test_cache.db"
    return ServerConfig(
        embedding_cache_enabled=True,
        embedding_cache_path=str(cache_path),
        embedding_cache_ttl_days=30,
    )


@pytest.fixture
def disabled_cache_config(tmp_path):
    """Create configuration with cache disabled."""
    return ServerConfig(
        embedding_cache_enabled=False,
    )


@pytest.fixture
def cache(cache_config):
    """Create cache instance."""
    c = EmbeddingCache(cache_config)
    yield c
    c.close()


@pytest.fixture
def disabled_cache(disabled_cache_config):
    """Create disabled cache instance."""
    return EmbeddingCache(disabled_cache_config)


class TestCacheInitialization:
    """Test cache initialization."""

    def test_init_enabled(self, cache_config):
        """Test cache initialization when enabled."""
        cache = EmbeddingCache(cache_config)

        assert cache.enabled is True
        assert cache.conn is not None
        assert cache.hits == 0
        assert cache.misses == 0

        cache.close()

    def test_init_disabled(self, disabled_cache_config):
        """Test cache initialization when disabled."""
        cache = EmbeddingCache(disabled_cache_config)

        assert cache.enabled is False
        assert cache.conn is None

    def test_init_with_default_config(self):
        """Test cache initialization with default config."""
        cache = EmbeddingCache()

        # Should use global config
        assert cache.config is not None
        cache.close()

    def test_database_tables_created(self, cache):
        """Test that database tables are created properly."""
        # Check embeddings table exists
        cursor = cache.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='embeddings'"
        )
        assert cursor.fetchone() is not None

        # Check index exists
        cursor = cache.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_text_model'"
        )
        assert cursor.fetchone() is not None


class TestCacheOperations:
    """Test basic cache operations."""

    @pytest.mark.asyncio
    async def test_set_and_get(self, cache):
        """Test setting and getting an embedding."""
        text = "test text"
        model = "test-model"
        embedding = [0.1, 0.2, 0.3]

        # Set
        await cache.set(text, model, embedding)

        # Get
        result = await cache.get(text, model)

        assert result == embedding
        assert cache.hits == 1
        assert cache.misses == 0

    @pytest.mark.asyncio
    async def test_get_miss(self, cache):
        """Test cache miss."""
        result = await cache.get("nonexistent", "model")

        assert result is None
        assert cache.misses == 1
        assert cache.hits == 0

    @pytest.mark.asyncio
    async def test_get_when_disabled(self, disabled_cache):
        """Test get when cache is disabled."""
        result = await disabled_cache.get("text", "model")

        assert result is None

    @pytest.mark.asyncio
    async def test_set_when_disabled(self, disabled_cache):
        """Test set when cache is disabled."""
        # Should not raise error
        await disabled_cache.set("text", "model", [0.1, 0.2])

    @pytest.mark.asyncio
    async def test_update_access_count(self, cache):
        """Test that access count is updated on get."""
        text = "test"
        model = "model"
        embedding = [0.1]

        await cache.set(text, model, embedding)

        # Get multiple times
        await cache.get(text, model)
        await cache.get(text, model)
        await cache.get(text, model)

        # Check access count in database
        cache_key, _ = cache._compute_key(text, model)
        cursor = cache.conn.execute(
            "SELECT access_count FROM embeddings WHERE cache_key = ?",
            (cache_key,)
        )
        access_count = cursor.fetchone()[0]

        assert access_count == 4  # 1 initial + 3 gets


class TestCacheTTL:
    """Test cache TTL (time-to-live) functionality."""

    @pytest.mark.asyncio
    async def test_expired_entry_deleted(self, cache):
        """Test that expired entries are deleted on get."""
        text = "test"
        model = "model"
        embedding = [0.1]

        # Set entry
        await cache.set(text, model, embedding)

        # Manually update created_at to make it expired
        cache_key, _ = cache._compute_key(text, model)
        old_date = (datetime.now(UTC) - timedelta(days=cache.ttl_days + 1)).isoformat()
        cache.conn.execute(
            "UPDATE embeddings SET created_at = ? WHERE cache_key = ?",
            (old_date, cache_key)
        )
        cache.conn.commit()

        # Try to get - should be deleted
        result = await cache.get(text, model)

        assert result is None
        assert cache.misses == 1

        # Verify entry was deleted
        cursor = cache.conn.execute(
            "SELECT COUNT(*) FROM embeddings WHERE cache_key = ?",
            (cache_key,)
        )
        assert cursor.fetchone()[0] == 0

    @pytest.mark.asyncio
    async def test_clean_old_entries(self, cache):
        """Test cleaning old cache entries."""
        # Add fresh entry
        await cache.set("fresh", "model", [0.1])

        # Add old entry
        cache_key, text_hash = cache._compute_key("old", "model")
        old_date = (datetime.now(UTC) - timedelta(days=40)).isoformat()
        cache.conn.execute(
            """
            INSERT INTO embeddings
            (cache_key, text_hash, model_name, embedding, created_at, accessed_at, access_count)
            VALUES (?, ?, ?, ?, ?, ?, 1)
            """,
            (cache_key, text_hash, "model", "[0.2]", old_date, old_date)
        )
        cache.conn.commit()

        # Clean old entries
        deleted = await cache.clean_old(days=35)

        assert deleted == 1

        # Fresh entry should still exist
        result = await cache.get("fresh", "model")
        assert result == [0.1]

    @pytest.mark.asyncio
    async def test_clean_old_when_disabled(self, disabled_cache):
        """Test clean_old when cache is disabled."""
        result = await disabled_cache.clean_old()
        assert result == 0


class TestCacheStats:
    """Test cache statistics."""

    def test_get_stats_enabled(self, cache):
        """Test getting cache statistics."""
        stats = cache.get_stats()

        assert stats["enabled"] is True
        assert stats["hits"] == 0
        assert stats["misses"] == 0
        assert stats["hit_rate"] == 0.0
        assert stats["total_entries"] == 0
        assert "cache_path" in stats
        assert "ttl_days" in stats

    def test_get_stats_disabled(self, disabled_cache):
        """Test getting stats when cache is disabled."""
        stats = disabled_cache.get_stats()

        assert stats["enabled"] is False
        assert stats["hits"] == 0
        assert stats["misses"] == 0

    @pytest.mark.asyncio
    async def test_hit_rate_calculation(self, cache):
        """Test hit rate calculation."""
        # Add entry
        await cache.set("test", "model", [0.1])

        # 1 hit, 1 miss
        await cache.get("test", "model")  # hit
        await cache.get("nonexistent", "model")  # miss

        stats = cache.get_stats()
        assert stats["hit_rate"] == 0.5
        assert stats["hits"] == 1
        assert stats["misses"] == 1

    @pytest.mark.asyncio
    async def test_stats_total_entries(self, cache):
        """Test total entries count in stats."""
        # Add multiple entries
        await cache.set("text1", "model", [0.1])
        await cache.set("text2", "model", [0.2])
        await cache.set("text3", "model", [0.3])

        stats = cache.get_stats()
        assert stats["total_entries"] == 3


class TestGetOrGenerate:
    """Test get_or_generate functionality."""

    @pytest.mark.asyncio
    async def test_get_or_generate_cache_hit(self, cache):
        """Test get_or_generate with cache hit."""
        text = "test"
        model = "model"
        embedding = [0.1, 0.2]

        # Pre-populate cache
        await cache.set(text, model, embedding)

        # Mock generator (should not be called)
        generator = AsyncMock()

        result = await cache.get_or_generate(text, model, generator)

        assert result == embedding
        generator.assert_not_called()
        assert cache.hits == 1

    @pytest.mark.asyncio
    async def test_get_or_generate_cache_miss(self, cache):
        """Test get_or_generate with cache miss (generates and caches)."""
        text = "test"
        model = "model"
        embedding = [0.1, 0.2]

        # Mock generator
        async def mock_generator(t):
            return embedding

        result = await cache.get_or_generate(text, model, mock_generator)

        assert result == embedding
        assert cache.misses == 1

        # Verify it was cached
        cached = await cache.get(text, model)
        assert cached == embedding


class TestCacheClear:
    """Test cache clearing."""

    @pytest.mark.asyncio
    async def test_clear_cache(self, cache):
        """Test clearing all cache entries."""
        # Add entries
        await cache.set("text1", "model", [0.1])
        await cache.set("text2", "model", [0.2])
        await cache.set("text3", "model", [0.3])

        # Set some hits/misses
        await cache.get("text1", "model")
        await cache.get("nonexistent", "model")

        # Clear
        deleted = await cache.clear()

        assert deleted == 3
        assert cache.hits == 0
        assert cache.misses == 0

        # Verify database is empty
        stats = cache.get_stats()
        assert stats["total_entries"] == 0

    @pytest.mark.asyncio
    async def test_clear_when_disabled(self, disabled_cache):
        """Test clear when cache is disabled."""
        result = await disabled_cache.clear()
        assert result == 0


class TestCacheKeyComputation:
    """Test cache key computation."""

    def test_compute_key_deterministic(self, cache):
        """Test that key computation is deterministic."""
        key1, hash1 = cache._compute_key("test", "model")
        key2, hash2 = cache._compute_key("test", "model")

        assert key1 == key2
        assert hash1 == hash2

    def test_compute_key_different_text(self, cache):
        """Test different text produces different keys."""
        key1, _ = cache._compute_key("text1", "model")
        key2, _ = cache._compute_key("text2", "model")

        assert key1 != key2

    def test_compute_key_different_model(self, cache):
        """Test different model produces different keys."""
        key1, _ = cache._compute_key("text", "model1")
        key2, _ = cache._compute_key("text", "model2")

        assert key1 != key2


class TestCacheErrorHandling:
    """Test error handling in cache operations."""

    @pytest.mark.asyncio
    async def test_get_error_handling(self, cache):
        """Test that get handles errors gracefully."""
        # Close connection to simulate error
        cache.conn.close()
        cache.conn = MagicMock()
        cache.conn.execute.side_effect = Exception("Database error")

        result = await cache.get("text", "model")

        assert result is None
        assert cache.misses == 1

    @pytest.mark.asyncio
    async def test_set_error_handling(self, cache):
        """Test that set handles errors gracefully."""
        # Close connection to simulate error
        cache.conn.close()
        cache.conn = MagicMock()
        cache.conn.execute.side_effect = Exception("Database error")

        # Should not raise
        await cache.set("text", "model", [0.1])

    def test_stats_error_handling(self, cache):
        """Test that get_stats handles errors gracefully."""
        # Simulate error
        cache.conn.close()
        cache.conn = MagicMock()
        cache.conn.execute.side_effect = Exception("Database error")

        stats = cache.get_stats()

        assert "error" in stats


class TestCacheClose:
    """Test cache connection closing."""

    def test_close(self, cache_config):
        """Test closing cache connection."""
        cache = EmbeddingCache(cache_config)

        assert cache.conn is not None

        cache.close()

        assert cache.conn is None

    def test_close_when_no_connection(self, disabled_cache):
        """Test closing when there's no connection."""
        # Should not raise error
        disabled_cache.close()
