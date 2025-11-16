"""Embedding cache using SQLite for fast lookups."""

import sqlite3
import hashlib
import json
import logging
from typing import List, Optional
from datetime import datetime, timedelta, UTC
from pathlib import Path

from src.config import ServerConfig

logger = logging.getLogger(__name__)


class EmbeddingCache:
    """
    SQLite-based cache for embedding vectors.

    Features:
    - SHA256-based key lookup
    - Automatic expiration (configurable TTL)
    - Cache statistics tracking
    - Thread-safe operations
    """

    def __init__(self, config: Optional[ServerConfig] = None):
        """
        Initialize embedding cache.

        Args:
            config: Server configuration. If None, uses global config.
        """
        if config is None:
            from src.config import get_config
            config = get_config()

        self.config = config
        self.cache_path = config.embedding_cache_path_expanded
        self.ttl_days = config.embedding_cache_ttl_days
        self.enabled = config.embedding_cache_enabled
        self.conn: Optional[sqlite3.Connection] = None

        # Statistics
        self.hits = 0
        self.misses = 0

        if self.enabled:
            self._initialize_db()
            logger.info(f"Embedding cache initialized at {self.cache_path}")
        else:
            logger.info("Embedding cache disabled")

    def _initialize_db(self) -> None:
        """Initialize the SQLite database and create tables."""
        try:
            self.conn = sqlite3.Connection(
                str(self.cache_path),
                check_same_thread=False,
            )

            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS embeddings (
                    cache_key TEXT PRIMARY KEY,
                    text_hash TEXT NOT NULL,
                    model_name TEXT NOT NULL,
                    embedding TEXT NOT NULL,
                    created_at TIMESTAMP NOT NULL,
                    accessed_at TIMESTAMP NOT NULL,
                    access_count INTEGER DEFAULT 1
                )
            """)

            # Create index for faster lookups
            self.conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_text_model
                ON embeddings(text_hash, model_name)
            """)

            self.conn.commit()
            logger.debug("Embedding cache database initialized")

        except Exception as e:
            logger.error(f"Failed to initialize cache database: {e}")
            self.enabled = False

    def _compute_key(self, text: str, model_name: str) -> tuple[str, str]:
        """
        Compute cache key from text and model name.

        Args:
            text: Input text.
            model_name: Model name.

        Returns:
            tuple: (cache_key, text_hash)
        """
        text_hash = hashlib.sha256(text.encode('utf-8')).hexdigest()
        cache_key = f"{text_hash}:{model_name}"
        return cache_key, text_hash

    async def get(self, text: str, model_name: str) -> Optional[List[float]]:
        """
        Retrieve embedding from cache.

        Args:
            text: Input text.
            model_name: Model name used to generate embedding.

        Returns:
            List[float]: Cached embedding vector, or None if not found.
        """
        if not self.enabled or self.conn is None:
            return None

        try:
            cache_key, _ = self._compute_key(text, model_name)

            # Query cache
            cursor = self.conn.execute(
                """
                SELECT embedding, created_at, access_count
                FROM embeddings
                WHERE cache_key = ?
                """,
                (cache_key,)
            )

            row = cursor.fetchone()

            if row is None:
                self.misses += 1
                return None

            embedding_json, created_at_str, access_count = row

            # Check expiration
            created_at = datetime.fromisoformat(created_at_str)
            if datetime.now(UTC) - created_at > timedelta(days=self.ttl_days):
                # Expired, delete it
                self.conn.execute("DELETE FROM embeddings WHERE cache_key = ?", (cache_key,))
                self.conn.commit()
                self.misses += 1
                return None

            # Update access statistics
            self.conn.execute(
                """
                UPDATE embeddings
                SET accessed_at = ?, access_count = ?
                WHERE cache_key = ?
                """,
                (datetime.now(UTC).isoformat(), access_count + 1, cache_key)
            )
            self.conn.commit()

            # Deserialize embedding
            embedding = json.loads(embedding_json)
            self.hits += 1
            logger.debug(f"Cache hit for key: {cache_key[:16]}...")
            return embedding

        except Exception as e:
            logger.error(f"Cache get error: {e}")
            self.misses += 1
            return None

    async def set(self, text: str, model_name: str, embedding: List[float]) -> None:
        """
        Store embedding in cache.

        Args:
            text: Input text.
            model_name: Model name.
            embedding: Embedding vector to cache.
        """
        if not self.enabled or self.conn is None:
            return

        try:
            cache_key, text_hash = self._compute_key(text, model_name)
            embedding_json = json.dumps(embedding)
            now = datetime.now(UTC).isoformat()

            # Insert or replace
            self.conn.execute(
                """
                INSERT OR REPLACE INTO embeddings
                (cache_key, text_hash, model_name, embedding, created_at, accessed_at, access_count)
                VALUES (?, ?, ?, ?, ?, ?, 1)
                """,
                (cache_key, text_hash, model_name, embedding_json, now, now)
            )
            self.conn.commit()
            logger.debug(f"Cached embedding for key: {cache_key[:16]}...")

        except Exception as e:
            logger.error(f"Cache set error: {e}")

    async def get_or_generate(
        self,
        text: str,
        model_name: str,
        generator_func,
    ) -> List[float]:
        """
        Get embedding from cache or generate if not found.

        Args:
            text: Input text.
            model_name: Model name.
            generator_func: Async function to generate embedding if not cached.

        Returns:
            List[float]: Embedding vector.
        """
        # Try cache first
        cached = await self.get(text, model_name)
        if cached is not None:
            return cached

        # Generate and cache
        embedding = await generator_func(text)
        await self.set(text, model_name, embedding)
        return embedding

    async def clean_old(self, days: Optional[int] = None) -> int:
        """
        Remove expired cache entries.

        Args:
            days: Age threshold in days. If None, uses config TTL.

        Returns:
            int: Number of entries removed.
        """
        if not self.enabled or self.conn is None:
            return 0

        try:
            days = days or self.ttl_days
            cutoff = (datetime.now(UTC) - timedelta(days=days)).isoformat()

            cursor = self.conn.execute(
                "DELETE FROM embeddings WHERE created_at < ?",
                (cutoff,)
            )

            deleted = cursor.rowcount
            self.conn.commit()

            logger.info(f"Cleaned {deleted} expired cache entries (older than {days} days)")
            return deleted

        except Exception as e:
            logger.error(f"Cache clean error: {e}")
            return 0

    def get_stats(self) -> dict:
        """
        Get cache statistics.

        Returns:
            dict: Cache statistics including hit rate, size, etc.
        """
        if not self.enabled or self.conn is None:
            return {
                "enabled": False,
                "hits": 0,
                "misses": 0,
                "hit_rate": 0.0,
                "total_entries": 0,
            }

        try:
            cursor = self.conn.execute("SELECT COUNT(*) FROM embeddings")
            total_entries = cursor.fetchone()[0]

            total_requests = self.hits + self.misses
            hit_rate = self.hits / total_requests if total_requests > 0 else 0.0

            return {
                "enabled": True,
                "hits": self.hits,
                "misses": self.misses,
                "hit_rate": hit_rate,
                "total_entries": total_entries,
                "cache_path": str(self.cache_path),
                "ttl_days": self.ttl_days,
            }

        except Exception as e:
            logger.error(f"Failed to get cache stats: {e}")
            return {"enabled": True, "error": str(e)}

    async def clear(self) -> int:
        """
        Clear all cache entries.

        Returns:
            int: Number of entries cleared.
        """
        if not self.enabled or self.conn is None:
            return 0

        try:
            cursor = self.conn.execute("DELETE FROM embeddings")
            deleted = cursor.rowcount
            self.conn.commit()

            # Reset stats
            self.hits = 0
            self.misses = 0

            logger.info(f"Cleared {deleted} cache entries")
            return deleted

        except Exception as e:
            logger.error(f"Cache clear error: {e}")
            return 0

    def close(self) -> None:
        """Close the cache database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None
            logger.info("Embedding cache closed")
