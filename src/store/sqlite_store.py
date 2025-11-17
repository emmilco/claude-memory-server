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

            # Create usage tracking table
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS memory_usage_tracking (
                    memory_id TEXT PRIMARY KEY,
                    first_seen TEXT NOT NULL,
                    last_used TEXT NOT NULL,
                    use_count INTEGER NOT NULL DEFAULT 0,
                    last_search_score REAL NOT NULL DEFAULT 0.0,
                    FOREIGN KEY (memory_id) REFERENCES memories(id) ON DELETE CASCADE
                )
            """)

            # Index for efficient queries
            self.conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_last_used ON memory_usage_tracking(last_used)"
            )

            # Create git commits table
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS git_commits (
                    commit_hash TEXT PRIMARY KEY,
                    repository_path TEXT NOT NULL,
                    author_name TEXT NOT NULL,
                    author_email TEXT NOT NULL,
                    author_date TEXT NOT NULL,
                    committer_name TEXT NOT NULL,
                    committer_date TEXT NOT NULL,
                    message TEXT NOT NULL,
                    message_embedding TEXT NOT NULL,
                    branch_names TEXT,
                    tags TEXT,
                    parent_hashes TEXT,
                    stats TEXT,
                    created_at TEXT NOT NULL
                )
            """)

            # Create git file changes table
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS git_file_changes (
                    id TEXT PRIMARY KEY,
                    commit_hash TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    change_type TEXT NOT NULL,
                    lines_added INTEGER NOT NULL DEFAULT 0,
                    lines_deleted INTEGER NOT NULL DEFAULT 0,
                    diff_content TEXT,
                    diff_embedding TEXT,
                    FOREIGN KEY (commit_hash) REFERENCES git_commits(commit_hash) ON DELETE CASCADE
                )
            """)

            # Create indices for git tables
            self.conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_git_repo ON git_commits(repository_path)"
            )
            self.conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_git_author ON git_commits(author_email)"
            )
            self.conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_git_date ON git_commits(author_date)"
            )
            self.conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_git_file_commit ON git_file_changes(commit_hash)"
            )
            self.conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_git_file_path ON git_file_changes(file_path)"
            )

            # Enable FTS for git commit messages
            self.conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS git_commits_fts USING fts5(
                    commit_hash UNINDEXED,
                    message,
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

    async def get_all_projects(self) -> List[str]:
        """
        Get list of all unique project names in the store.

        Returns:
            List of project names.
        """
        if not self.conn:
            raise StorageError("Store not initialized")

        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT DISTINCT project_name
                FROM memories
                WHERE project_name IS NOT NULL
                ORDER BY project_name
            """)

            projects = [row[0] for row in cursor.fetchall()]
            return projects

        except Exception as e:
            logger.error(f"Error getting all projects: {e}")
            raise StorageError(f"Failed to get projects: {e}")

    async def get_project_stats(self, project_name: str) -> Dict[str, Any]:
        """
        Get statistics for a specific project.

        Args:
            project_name: Name of the project.

        Returns:
            Dictionary with project statistics.
        """
        if not self.conn:
            raise StorageError("Store not initialized")

        try:
            cursor = self.conn.cursor()

            # Get total count
            cursor.execute("""
                SELECT COUNT(*) FROM memories WHERE project_name = ?
            """, (project_name,))
            total_memories = cursor.fetchone()[0]

            # Get category counts
            cursor.execute("""
                SELECT category, COUNT(*)
                FROM memories
                WHERE project_name = ?
                GROUP BY category
            """, (project_name,))
            categories = {row[0]: row[1] for row in cursor.fetchall()}

            # Get context level counts
            cursor.execute("""
                SELECT context_level, COUNT(*)
                FROM memories
                WHERE project_name = ?
                GROUP BY context_level
            """, (project_name,))
            context_levels = {row[0]: row[1] for row in cursor.fetchall()}

            # Get latest update
            cursor.execute("""
                SELECT MAX(updated_at) FROM memories WHERE project_name = ?
            """, (project_name,))
            latest_update = cursor.fetchone()[0]
            if latest_update:
                latest_update = datetime.fromisoformat(latest_update)

            # Get unique file count (from metadata)
            cursor.execute("""
                SELECT metadata FROM memories
                WHERE project_name = ? AND category = 'code'
            """, (project_name,))

            file_paths = set()
            for row in cursor.fetchall():
                try:
                    metadata = json.loads(row[0])
                    if "file_path" in metadata:
                        file_paths.add(metadata["file_path"])
                except:
                    pass

            num_files = len(file_paths)
            num_functions = categories.get("code", 0)
            num_classes = sum(1 for cat in categories if "class" in cat.lower())

            return {
                "project_name": project_name,
                "total_memories": total_memories,
                "num_files": num_files,
                "num_functions": num_functions,
                "num_classes": num_classes,
                "categories": categories,
                "context_levels": context_levels,
                "last_indexed": latest_update,
            }

        except Exception as e:
            logger.error(f"Error getting project stats for {project_name}: {e}")
            raise StorageError(f"Failed to get project stats: {e}")

    async def update_usage(self, usage_data: Dict[str, Any]) -> bool:
        """
        Update usage tracking for a single memory.

        Args:
            usage_data: Dictionary with memory_id, first_seen, last_used, use_count, last_search_score

        Returns:
            True if successful
        """
        if not self.conn:
            raise StorageError("Store not initialized")

        try:
            self.conn.execute(
                """
                INSERT INTO memory_usage_tracking
                (memory_id, first_seen, last_used, use_count, last_search_score)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(memory_id) DO UPDATE SET
                    last_used = excluded.last_used,
                    use_count = excluded.use_count,
                    last_search_score = excluded.last_search_score
                """,
                (
                    usage_data["memory_id"],
                    usage_data["first_seen"],
                    usage_data["last_used"],
                    usage_data["use_count"],
                    usage_data["last_search_score"],
                ),
            )
            self.conn.commit()
            return True

        except Exception as e:
            logger.error(f"Failed to update usage tracking: {e}")
            raise StorageError(f"Failed to update usage tracking: {e}")

    async def batch_update_usage(self, usage_data_list: List[Dict[str, Any]]) -> bool:
        """
        Batch update usage tracking for multiple memories.

        Args:
            usage_data_list: List of usage data dictionaries

        Returns:
            True if successful
        """
        if not self.conn:
            raise StorageError("Store not initialized")

        try:
            self.conn.executemany(
                """
                INSERT INTO memory_usage_tracking
                (memory_id, first_seen, last_used, use_count, last_search_score)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(memory_id) DO UPDATE SET
                    last_used = excluded.last_used,
                    use_count = excluded.use_count,
                    last_search_score = excluded.last_search_score
                """,
                [
                    (
                        data["memory_id"],
                        data["first_seen"],
                        data["last_used"],
                        data["use_count"],
                        data["last_search_score"],
                    )
                    for data in usage_data_list
                ],
            )
            self.conn.commit()
            logger.debug(f"Batch updated {len(usage_data_list)} usage records")
            return True

        except Exception as e:
            logger.error(f"Failed to batch update usage tracking: {e}")
            raise StorageError(f"Failed to batch update usage tracking: {e}")

    async def get_usage_stats(self, memory_id: str) -> Optional[Dict[str, Any]]:
        """
        Get usage statistics for a memory.

        Args:
            memory_id: Memory ID

        Returns:
            Usage stats dictionary, or None if not found
        """
        if not self.conn:
            raise StorageError("Store not initialized")

        try:
            cursor = self.conn.execute(
                "SELECT * FROM memory_usage_tracking WHERE memory_id = ?",
                (memory_id,),
            )
            row = cursor.fetchone()

            if not row:
                return None

            return dict(row)

        except Exception as e:
            logger.error(f"Failed to get usage stats: {e}")
            return None

    async def get_all_usage_stats(self) -> List[Dict[str, Any]]:
        """Get all usage statistics."""
        if not self.conn:
            raise StorageError("Store not initialized")

        try:
            cursor = self.conn.execute("SELECT * FROM memory_usage_tracking")
            return [dict(row) for row in cursor.fetchall()]

        except Exception as e:
            logger.error(f"Failed to get all usage stats: {e}")
            return []

    async def delete_usage_tracking(self, memory_id: str) -> bool:
        """
        Delete usage tracking for a memory.

        Args:
            memory_id: Memory ID

        Returns:
            True if deleted
        """
        if not self.conn:
            raise StorageError("Store not initialized")

        try:
            cursor = self.conn.execute(
                "DELETE FROM memory_usage_tracking WHERE memory_id = ?",
                (memory_id,),
            )
            self.conn.commit()
            return cursor.rowcount > 0

        except Exception as e:
            logger.error(f"Failed to delete usage tracking: {e}")
            return False

    async def cleanup_orphaned_usage_tracking(self) -> int:
        """
        Clean up usage tracking records for deleted memories.

        Returns:
            Number of records deleted
        """
        if not self.conn:
            raise StorageError("Store not initialized")

        try:
            cursor = self.conn.execute(
                """
                DELETE FROM memory_usage_tracking
                WHERE memory_id NOT IN (SELECT id FROM memories)
                """
            )
            self.conn.commit()
            return cursor.rowcount

        except Exception as e:
            logger.error(f"Failed to cleanup orphaned usage tracking: {e}")
            return 0

    async def find_memories_by_criteria(
        self,
        context_level: Optional[Any] = None,
        older_than: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """
        Find memories matching criteria (for pruning).

        Args:
            context_level: Filter by context level
            older_than: Find memories older than this datetime

        Returns:
            List of memory dictionaries
        """
        if not self.conn:
            raise StorageError("Store not initialized")

        try:
            query = "SELECT m.id, m.created_at, u.last_used FROM memories m"
            query += " LEFT JOIN memory_usage_tracking u ON m.id = u.memory_id"
            query += " WHERE 1=1"
            params = []

            if context_level:
                query += " AND m.context_level = ?"
                params.append(context_level.value if hasattr(context_level, "value") else context_level)

            if older_than:
                # Check either last_used or created_at
                query += " AND (COALESCE(u.last_used, m.created_at) < ?)"
                params.append(older_than.isoformat())

            cursor = self.conn.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

        except Exception as e:
            logger.error(f"Failed to find memories by criteria: {e}")
            return []

    async def find_unused_memories(
        self,
        cutoff_time: datetime,
        exclude_context_levels: Optional[List[Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Find memories that haven't been used since cutoff_time.

        Args:
            cutoff_time: Cutoff datetime
            exclude_context_levels: Don't include these context levels

        Returns:
            List of memory dictionaries
        """
        if not self.conn:
            raise StorageError("Store not initialized")

        try:
            query = """
                SELECT m.id, m.created_at, m.context_level, u.last_used, u.use_count
                FROM memories m
                LEFT JOIN memory_usage_tracking u ON m.id = u.memory_id
                WHERE (u.use_count = 0 OR u.use_count IS NULL)
                  AND (COALESCE(u.last_used, m.created_at) < ?)
            """
            params = [cutoff_time.isoformat()]

            if exclude_context_levels:
                placeholders = ",".join(["?"] * len(exclude_context_levels))
                query += f" AND m.context_level NOT IN ({placeholders})"
                params.extend([
                    cl.value if hasattr(cl, "value") else cl
                    for cl in exclude_context_levels
                ])

            cursor = self.conn.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

        except Exception as e:
            logger.error(f"Failed to find unused memories: {e}")
            return []

    async def get_all_memories(self) -> List[Dict[str, Any]]:
        """
        Get all memories (for fallback queries).

        Returns:
            List of all memory dictionaries
        """
        if not self.conn:
            raise StorageError("Store not initialized")

        try:
            cursor = self.conn.execute("SELECT * FROM memories")
            return [dict(row) for row in cursor.fetchall()]

        except Exception as e:
            logger.error(f"Failed to get all memories: {e}")
            return []

    # Git history methods

    async def store_git_commits(
        self, commits: List[Dict[str, Any]]
    ) -> int:
        """
        Store git commits in batch.

        Args:
            commits: List of commit dictionaries

        Returns:
            Number of commits stored
        """
        if not self.conn:
            raise StorageError("Store not initialized")

        try:
            stored_count = 0
            for commit in commits:
                # Serialize complex fields
                message_embedding_json = json.dumps(commit["message_embedding"])
                branch_names_json = json.dumps(commit.get("branch_names", []))
                tags_json = json.dumps(commit.get("tags", []))
                parent_hashes_json = json.dumps(commit.get("parent_hashes", []))
                stats_json = json.dumps(commit.get("stats", {}))

                # Insert into main table
                self.conn.execute(
                    """
                    INSERT OR REPLACE INTO git_commits
                    (commit_hash, repository_path, author_name, author_email,
                     author_date, committer_name, committer_date, message,
                     message_embedding, branch_names, tags, parent_hashes,
                     stats, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        commit["commit_hash"],
                        commit["repository_path"],
                        commit["author_name"],
                        commit["author_email"],
                        commit["author_date"].isoformat(),
                        commit["committer_name"],
                        commit["committer_date"].isoformat(),
                        commit["message"],
                        message_embedding_json,
                        branch_names_json,
                        tags_json,
                        parent_hashes_json,
                        stats_json,
                        datetime.now(UTC).isoformat(),
                    ),
                )

                # Insert into FTS table
                self.conn.execute(
                    """
                    INSERT OR REPLACE INTO git_commits_fts (commit_hash, message)
                    VALUES (?, ?)
                    """,
                    (commit["commit_hash"], commit["message"]),
                )

                stored_count += 1

            self.conn.commit()
            logger.info(f"Stored {stored_count} git commits")
            return stored_count

        except Exception as e:
            self.conn.rollback()
            raise StorageError(f"Failed to store git commits: {e}")

    async def store_git_file_changes(
        self, file_changes: List[Dict[str, Any]]
    ) -> int:
        """
        Store git file changes in batch.

        Args:
            file_changes: List of file change dictionaries

        Returns:
            Number of file changes stored
        """
        if not self.conn:
            raise StorageError("Store not initialized")

        try:
            stored_count = 0
            for change in file_changes:
                # Serialize embedding if present
                diff_embedding_json = None
                if change.get("diff_embedding"):
                    diff_embedding_json = json.dumps(change["diff_embedding"])

                self.conn.execute(
                    """
                    INSERT OR REPLACE INTO git_file_changes
                    (id, commit_hash, file_path, change_type, lines_added,
                     lines_deleted, diff_content, diff_embedding)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        change["id"],
                        change["commit_hash"],
                        change["file_path"],
                        change["change_type"],
                        change["lines_added"],
                        change["lines_deleted"],
                        change.get("diff_content"),
                        diff_embedding_json,
                    ),
                )

                stored_count += 1

            self.conn.commit()
            logger.info(f"Stored {stored_count} git file changes")
            return stored_count

        except Exception as e:
            self.conn.rollback()
            raise StorageError(f"Failed to store git file changes: {e}")

    async def search_git_commits(
        self,
        query: Optional[str] = None,
        repository_path: Optional[str] = None,
        author: Optional[str] = None,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Search git commits with filters.

        Args:
            query: Text search query (uses FTS)
            repository_path: Filter by repository
            author: Filter by author email
            since: Filter by date (after)
            until: Filter by date (before)
            limit: Maximum results

        Returns:
            List of matching commits
        """
        if not self.conn:
            raise StorageError("Store not initialized")

        try:
            # Build query
            if query:
                # Use FTS for text search
                sql = """
                    SELECT c.*
                    FROM git_commits c
                    JOIN git_commits_fts f ON c.commit_hash = f.commit_hash
                    WHERE f.message MATCH ?
                """
                params = [query]
            else:
                sql = "SELECT * FROM git_commits WHERE 1=1"
                params = []

            # Add filters
            if repository_path:
                sql += " AND repository_path = ?"
                params.append(repository_path)

            if author:
                sql += " AND author_email = ?"
                params.append(author)

            if since:
                sql += " AND author_date >= ?"
                params.append(since.isoformat())

            if until:
                sql += " AND author_date <= ?"
                params.append(until.isoformat())

            # Order and limit
            sql += " ORDER BY author_date DESC LIMIT ?"
            params.append(limit)

            cursor = self.conn.execute(sql, params)
            commits = []

            for row in cursor.fetchall():
                commit_dict = dict(row)
                # Deserialize JSON fields
                commit_dict["message_embedding"] = json.loads(commit_dict["message_embedding"])
                commit_dict["branch_names"] = json.loads(commit_dict.get("branch_names", "[]"))
                commit_dict["tags"] = json.loads(commit_dict.get("tags", "[]"))
                commit_dict["parent_hashes"] = json.loads(commit_dict.get("parent_hashes", "[]"))
                commit_dict["stats"] = json.loads(commit_dict.get("stats", "{}"))
                commits.append(commit_dict)

            return commits

        except Exception as e:
            logger.error(f"Failed to search git commits: {e}")
            return []

    async def get_git_commit(self, commit_hash: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific git commit by hash.

        Args:
            commit_hash: Commit hash

        Returns:
            Commit dictionary or None
        """
        if not self.conn:
            raise StorageError("Store not initialized")

        try:
            cursor = self.conn.execute(
                "SELECT * FROM git_commits WHERE commit_hash = ?",
                (commit_hash,),
            )
            row = cursor.fetchone()

            if not row:
                return None

            commit_dict = dict(row)
            # Deserialize JSON fields
            commit_dict["message_embedding"] = json.loads(commit_dict["message_embedding"])
            commit_dict["branch_names"] = json.loads(commit_dict.get("branch_names", "[]"))
            commit_dict["tags"] = json.loads(commit_dict.get("tags", "[]"))
            commit_dict["parent_hashes"] = json.loads(commit_dict.get("parent_hashes", "[]"))
            commit_dict["stats"] = json.loads(commit_dict.get("stats", "{}"))

            return commit_dict

        except Exception as e:
            logger.error(f"Failed to get git commit: {e}")
            return None

    async def get_commits_by_file(
        self, file_path: str, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get commits that modified a specific file.

        Args:
            file_path: File path to search
            limit: Maximum results

        Returns:
            List of matching commits with file change info
        """
        if not self.conn:
            raise StorageError("Store not initialized")

        try:
            cursor = self.conn.execute(
                """
                SELECT c.*, fc.change_type, fc.lines_added, fc.lines_deleted
                FROM git_commits c
                JOIN git_file_changes fc ON c.commit_hash = fc.commit_hash
                WHERE fc.file_path = ?
                ORDER BY c.author_date DESC
                LIMIT ?
                """,
                (file_path, limit),
            )

            commits = []
            for row in cursor.fetchall():
                commit_dict = dict(row)
                # Deserialize JSON fields
                commit_dict["message_embedding"] = json.loads(commit_dict["message_embedding"])
                commit_dict["branch_names"] = json.loads(commit_dict.get("branch_names", "[]"))
                commit_dict["tags"] = json.loads(commit_dict.get("tags", "[]"))
                commit_dict["parent_hashes"] = json.loads(commit_dict.get("parent_hashes", "[]"))
                commit_dict["stats"] = json.loads(commit_dict.get("stats", "{}"))
                commits.append(commit_dict)

            return commits

        except Exception as e:
            logger.error(f"Failed to get commits by file: {e}")
            return []
