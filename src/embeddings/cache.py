"""Embedding cache using SQLite for fast lookups."""

import asyncio
import sqlite3
import hashlib
import json
import logging
import threading
from typing import List, Optional
from datetime import datetime, timedelta, UTC
from pathlib import Path

from src.config import ServerConfig
from src.embeddings.rust_bridge import RustBridge

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

        # Thread lock for SQLite operations (required for check_same_thread=False)
        self._db_lock = threading.RLock()

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
                timeout=5.0,  # Add timeout for concurrent access
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

        # Run blocking SQLite operations in thread pool for proper async handling
        return await asyncio.to_thread(self._get_sync, text, model_name)

    def _get_sync(self, text: str, model_name: str) -> Optional[List[float]]:
        """Synchronous implementation of get() for thread pool execution."""
        try:
            cache_key, _ = self._compute_key(text, model_name)

            # Query cache with lock for thread safety
            with self._db_lock:
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

                # Normalize cached embedding to match fresh embeddings
                # Fresh embeddings from generator are normalized via Rust bridge
                normalized = RustBridge.batch_normalize([embedding])[0]

                self.hits += 1
                logger.debug(f"Cache hit for key: {cache_key[:16]}...")
                return normalized

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

        # Run blocking SQLite operations in thread pool for proper async handling
        await asyncio.to_thread(self._set_sync, text, model_name, embedding)

    def _set_sync(self, text: str, model_name: str, embedding: List[float]) -> None:
        """Synchronous implementation of set() for thread pool execution."""
        try:
            cache_key, text_hash = self._compute_key(text, model_name)
            embedding_json = json.dumps(embedding)
            now = datetime.now(UTC).isoformat()

            # Insert or replace with lock for thread safety
            with self._db_lock:
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

    async def batch_get(
        self,
        texts: List[str],
        model_name: str,
    ) -> List[Optional[List[float]]]:
        """
        Retrieve multiple embeddings from cache in a single query.

        Avoids N+1 query pattern compared to calling get() in a loop.

        Args:
            texts: List of input texts.
            model_name: Model name.

        Returns:
            List[Optional[List[float]]]: List of embeddings (None if not found/expired).
        """
        if not self.enabled or self.conn is None:
            return {}

        # Run blocking SQLite operations in thread pool for proper async handling
        return await asyncio.to_thread(self._batch_get_sync, texts, model_name)

    def _batch_get_sync(self, texts: List[str], model_name: str) -> dict[str, Optional[List[float]]]:
        """Synchronous implementation of batch_get() for thread pool execution."""
        if not self.enabled or self.conn is None or not texts:
            return [None] * len(texts)

        try:
            # Compute cache keys for all texts
            cache_keys = [self._compute_key(text, model_name)[0] for text in texts]
            
            with self._db_lock:
                # Single query for all keys using IN clause
                placeholders = ','.join('?' * len(cache_keys))
                cursor = self.conn.execute(
                    f"""
                    SELECT cache_key, embedding, created_at, access_count
                    FROM embeddings
                    WHERE cache_key IN ({placeholders})
                    """,
                    cache_keys
                )

                rows = cursor.fetchall()
                embeddings_by_key = {}
                expired_keys = []

                # Process results
                for row in rows:
                    cache_key, embedding_json, created_at_str, access_count = row
                    
                    # Check expiration
                    created_at = datetime.fromisoformat(created_at_str)
                    if datetime.now(UTC) - created_at > timedelta(days=self.ttl_days):
                        expired_keys.append(cache_key)
                        continue

                    # Deserialize and normalize
                    embedding = json.loads(embedding_json)
                    normalized = RustBridge.batch_normalize([embedding])[0]
                    embeddings_by_key[cache_key] = normalized
                    
                    # Update access statistics
                    self.conn.execute(
                        """
                        UPDATE embeddings
                        SET accessed_at = ?, access_count = ?
                        WHERE cache_key = ?
                        """,
                        (datetime.now(UTC).isoformat(), access_count + 1, cache_key)
                    )

                # Delete expired entries
                if expired_keys:
                    placeholders = ','.join('?' * len(expired_keys))
                    self.conn.execute(
                        f"DELETE FROM embeddings WHERE cache_key IN ({placeholders})",
                        expired_keys
                    )
                    
                self.conn.commit()

                # Build result list in same order as input
                results = []
                for cache_key in cache_keys:
                    if cache_key in embeddings_by_key:
                        results.append(embeddings_by_key[cache_key])
                        self.hits += 1
                    else:
                        results.append(None)
                        self.misses += 1

                logger.debug(f"Batch cache lookup: {len(cache_keys)} keys, {len(embeddings_by_key)} hits")
                return results

        except Exception as e:
            logger.error(f"Batch cache get error: {e}")
            return [None] * len(texts)

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

        # Run blocking SQLite operations in thread pool for proper async handling
        return await asyncio.to_thread(self._clean_old_sync, days)

    def _clean_old_sync(self, days: Optional[int] = None) -> int:
        """Synchronous implementation of clean_old() for thread pool execution."""
        if not self.enabled or self.conn is None:
            return 0

        try:
            days = days or self.ttl_days
            cutoff = (datetime.now(UTC) - timedelta(days=days)).isoformat()

            with self._db_lock:
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
            with self._db_lock:
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

        # Run blocking SQLite operations in thread pool for proper async handling
        return await asyncio.to_thread(self._clear_sync)

    def _clear_sync(self) -> int:
        """Synchronous implementation of clear() for thread pool execution."""
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
        with self._db_lock:
            if self.conn:
                try:
                    # Commit any pending transactions before closing
                    self.conn.commit()
                except Exception as e:
                    logger.debug(f"Error committing on close (may be expected): {e}")

                try:
                    self.conn.close()
                except Exception as e:
                    logger.error(f"Error closing connection: {e}")
                finally:
                    self.conn = None
                    logger.info("Embedding cache closed")
