"""SQLite memory store implementation (fallback)."""

import sqlite3
import json
import logging
from typing import List, Tuple, Optional, Dict, Any
from datetime import datetime, UTC
from pathlib import Path

from src.store.base import MemoryStore
from src.core.models import MemoryUnit, SearchFilters, MemoryCategory, ContextLevel, MemoryScope
from src.core.exceptions import StorageError, MemoryNotFoundError
from src.config import ServerConfig

logger = logging.getLogger(__name__)


class SQLiteMemoryStore(MemoryStore):
    """
    SQLite implementation of the MemoryStore interface.

    This is a fallback/simple implementation that doesn't use vector search.
    Instead, it uses simple text search. For production use with semantic
    search, use QdrantMemoryStore instead.
    """

    def __init__(self, config: Optional[ServerConfig] = None):
        """
        Initialize SQLite memory store.

        Args:
            config: Server configuration. If None, uses global config.
        """
        if config is None:
            from src.config import get_config
            config = get_config()

        self.config = config
        self.db_path = config.sqlite_path_expanded
        self.conn: Optional[sqlite3.Connection] = None

        logger.info(f"SQLite store initialized at {self.db_path}")

    async def initialize(self) -> None:
        """Initialize the SQLite database and create tables."""
        try:
            self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
            self.conn.row_factory = sqlite3.Row

            # Create tables
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY,
                    content TEXT NOT NULL,
                    category TEXT NOT NULL,
                    context_level TEXT NOT NULL,
                    scope TEXT NOT NULL,
                    project_name TEXT,
                    importance REAL NOT NULL,
                    embedding_model TEXT NOT NULL,
                    embedding TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    tags TEXT,
                    metadata TEXT
                )
            """)

            # Create indices
            self.conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_category ON memories(category)"
            )
            self.conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_context_level ON memories(context_level)"
            )
            self.conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_scope ON memories(scope)"
            )
            self.conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_project_name ON memories(project_name)"
            )

            # Enable FTS (Full-Text Search)
            self.conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
                    id UNINDEXED,
                    content,
                    tokenize = 'porter'
                )
            """)

            self.conn.commit()
            logger.info("SQLite store initialized successfully")

        except Exception as e:
            raise StorageError(f"Failed to initialize SQLite store: {e}")

    async def store(
        self,
        content: str,
        embedding: List[float],
        metadata: Dict[str, Any],
    ) -> str:
        """Store a single memory."""
        if self.conn is None:
            await self.initialize()

        try:
            from uuid import uuid4
            memory_id = metadata.get("id") or str(uuid4())
            embedding_json = json.dumps(embedding)
            tags_json = json.dumps(metadata.get("tags", []))
            metadata_json = json.dumps(metadata.get("metadata", {}))

            # Insert into main table
            self.conn.execute(
                """
                INSERT OR REPLACE INTO memories
                (id, content, category, context_level, scope, project_name,
                 importance, embedding_model, embedding, created_at, updated_at,
                 tags, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    memory_id,
                    content,
                    metadata.get("category"),
                    metadata.get("context_level"),
                    metadata.get("scope", "global"),
                    metadata.get("project_name"),
                    metadata.get("importance", 0.5),
                    metadata.get("embedding_model", "all-MiniLM-L6-v2"),
                    embedding_json,
                    metadata.get("created_at", datetime.now(UTC)).isoformat() if isinstance(metadata.get("created_at"), datetime) else metadata.get("created_at", datetime.now(UTC).isoformat()),
                    datetime.now(UTC).isoformat(),
                    tags_json,
                    metadata_json,
                ),
            )

            # Insert into FTS table
            self.conn.execute(
                """
                INSERT OR REPLACE INTO memories_fts (id, content)
                VALUES (?, ?)
                """,
                (memory_id, content),
            )

            self.conn.commit()
            logger.debug(f"Stored memory: {memory_id}")
            return memory_id

        except Exception as e:
            raise StorageError(f"Failed to store memory: {e}")

    async def retrieve(
        self,
        query_embedding: List[float],
        filters: Optional[SearchFilters] = None,
        limit: int = 5,
    ) -> List[Tuple[MemoryUnit, float]]:
        """
        Retrieve memories using FTS (not vector search).

        Note: This is a simplified implementation using text search.
        For proper semantic search, use QdrantMemoryStore.
        """
        if self.conn is None:
            await self.initialize()

        try:
            # Build query - note: we don't actually use query_embedding in SQLite
            # This is just FTS-based search
            query = """
                SELECT m.*
                FROM memories m
                WHERE 1=1
            """
            params = []

            # Apply filters
            if filters:
                if filters.context_level:
                    query += " AND m.context_level = ?"
                    params.append(filters.context_level.value)
                if filters.scope:
                    query += " AND m.scope = ?"
                    params.append(filters.scope.value)
                if filters.category:
                    query += " AND m.category = ?"
                    params.append(filters.category.value)
                if filters.project_name:
                    query += " AND m.project_name = ?"
                    params.append(filters.project_name)
                if filters.min_importance > 0.0:
                    query += " AND m.importance >= ?"
                    params.append(filters.min_importance)

            query += " ORDER BY m.created_at DESC LIMIT ?"
            params.append(limit)

            cursor = self.conn.execute(query, params)
            rows = cursor.fetchall()

            results = []
            for row in rows:
                memory = self._row_to_memory_unit(dict(row))
                # Simplified scoring - just use importance since we don't have
                # vector similarity in SQLite
                score = row["importance"]
                results.append((memory, score))

            logger.debug(f"Retrieved {len(results)} memories")
            return results

        except Exception as e:
            raise StorageError(f"Failed to retrieve memories: {e}")

    async def delete(self, memory_id: str) -> bool:
        """Delete a memory by its ID."""
        if self.conn is None:
            await self.initialize()

        try:
            # Delete from main table
            cursor = self.conn.execute(
                "DELETE FROM memories WHERE id = ?", (memory_id,)
            )

            # Delete from FTS table
            self.conn.execute("DELETE FROM memories_fts WHERE id = ?", (memory_id,))

            self.conn.commit()

            deleted = cursor.rowcount > 0
            if deleted:
                logger.debug(f"Deleted memory: {memory_id}")
            return deleted

        except Exception as e:
            raise StorageError(f"Failed to delete memory: {e}")

    async def batch_store(
        self,
        items: List[Tuple[str, List[float], Dict[str, Any]]],
    ) -> List[str]:
        """Store multiple memories in a batch."""
        memory_ids = []
        for content, embedding, metadata in items:
            memory_id = await self.store(content, embedding, metadata)
            memory_ids.append(memory_id)
        return memory_ids

    async def search_with_filters(
        self,
        query_embedding: List[float],
        filters: SearchFilters,
        limit: int = 5,
    ) -> List[Tuple[MemoryUnit, float]]:
        """Search with filters."""
        return await self.retrieve(query_embedding, filters, limit)

    async def get_by_id(self, memory_id: str) -> Optional[MemoryUnit]:
        """Retrieve a specific memory by its ID."""
        if self.conn is None:
            await self.initialize()

        try:
            cursor = self.conn.execute(
                "SELECT * FROM memories WHERE id = ?", (memory_id,)
            )
            row = cursor.fetchone()

            if row is None:
                return None

            return self._row_to_memory_unit(dict(row))

        except Exception as e:
            logger.error(f"Failed to get memory by ID: {e}")
            return None

    async def count(self, filters: Optional[SearchFilters] = None) -> int:
        """Count the number of memories."""
        if self.conn is None:
            await self.initialize()

        try:
            query = "SELECT COUNT(*) FROM memories WHERE 1=1"
            params = []

            if filters:
                if filters.context_level:
                    query += " AND context_level = ?"
                    params.append(filters.context_level.value)
                if filters.scope:
                    query += " AND scope = ?"
                    params.append(filters.scope.value)

            cursor = self.conn.execute(query, params)
            return cursor.fetchone()[0]

        except Exception as e:
            logger.error(f"Failed to count memories: {e}")
            return 0

    async def update(self, memory_id: str, updates: Dict[str, Any]) -> bool:
        """Update a memory's metadata."""
        if self.conn is None:
            await self.initialize()

        try:
            # Build update query
            set_parts = []
            params = []

            for key, value in updates.items():
                if key == "tags":
                    set_parts.append(f"{key} = ?")
                    params.append(json.dumps(value))
                elif key == "metadata":
                    set_parts.append(f"{key} = ?")
                    params.append(json.dumps(value))
                else:
                    set_parts.append(f"{key} = ?")
                    params.append(value)

            set_parts.append("updated_at = ?")
            params.append(datetime.now(UTC).isoformat())

            params.append(memory_id)

            query = f"UPDATE memories SET {', '.join(set_parts)} WHERE id = ?"

            cursor = self.conn.execute(query, params)
            self.conn.commit()

            return cursor.rowcount > 0

        except Exception as e:
            raise StorageError(f"Failed to update memory: {e}")

    async def health_check(self) -> bool:
        """Check if the storage backend is healthy."""
        try:
            if self.conn is None:
                return False
            self.conn.execute("SELECT 1")
            return True
        except Exception:
            return False

    async def close(self) -> None:
        """Close the database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None
            logger.info("SQLite store closed")

    def _row_to_memory_unit(self, row: Dict[str, Any]) -> MemoryUnit:
        """Convert database row to MemoryUnit."""
        # Parse datetime strings
        created_at = row.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)

        updated_at = row.get("updated_at")
        if isinstance(updated_at, str):
            updated_at = datetime.fromisoformat(updated_at)

        # Parse JSON fields
        tags = json.loads(row.get("tags", "[]"))
        metadata = json.loads(row.get("metadata", "{}"))

        return MemoryUnit(
            id=row["id"],
            content=row["content"],
            category=MemoryCategory(row["category"]),
            context_level=ContextLevel(row["context_level"]),
            scope=MemoryScope(row["scope"]),
            project_name=row.get("project_name"),
            importance=row["importance"],
            embedding_model=row["embedding_model"],
            created_at=created_at,
            updated_at=updated_at,
            tags=tags,
            metadata=metadata,
        )
