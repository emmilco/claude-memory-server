"""Collection management for organizing memories by themes."""

import sqlite3
import json
from typing import List, Optional, Dict, Any
from datetime import datetime, UTC

from src.tagging.models import Collection, CollectionCreate, CollectionMemory
from src.core.exceptions import ValidationError, StorageError


class CollectionManager:
    """
    Manage memory collections.

    Features:
    - Create, read, update, delete collections
    - Add/remove memories from collections
    - Auto-generate collections from tag patterns
    - Tag-based filtering
    """

    def __init__(self, db_path: str):
        """
        Initialize collection manager.

        Args:
            db_path: Path to SQLite database
        """
        self.db_path = db_path
        self._ensure_tables()

    def _ensure_tables(self) -> None:
        """Create collections tables if not exist."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS collections (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL UNIQUE,
                    description TEXT,
                    auto_generated INTEGER DEFAULT 0,
                    tag_filter TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS collection_memories (
                    collection_id TEXT NOT NULL,
                    memory_id TEXT NOT NULL,
                    added_at TEXT NOT NULL,
                    PRIMARY KEY (collection_id, memory_id)
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_collection_memories_collection "
                "ON collection_memories(collection_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_collection_memories_memory "
                "ON collection_memories(memory_id)"
            )
            conn.commit()

    def create_collection(self, collection_create: CollectionCreate) -> Collection:
        """
        Create a new collection.

        Args:
            collection_create: Collection creation request

        Returns:
            Created collection

        Raises:
            StorageError: If collection already exists or database error
        """
        collection = Collection(
            name=collection_create.name,
            description=collection_create.description,
            tag_filter=collection_create.tag_filter,
        )

        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    INSERT INTO collections (id, name, description, auto_generated, tag_filter, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        collection.id,
                        collection.name,
                        collection.description,
                        0,
                        json.dumps(collection.tag_filter) if collection.tag_filter else None,
                        collection.created_at.isoformat(),
                        collection.updated_at.isoformat(),
                    ),
                )
                conn.commit()
        except sqlite3.IntegrityError as e:
            if "UNIQUE constraint failed" in str(e):
                raise StorageError(f"Collection already exists: {collection.name}")
            raise StorageError(f"Failed to create collection: {e}") from e

        return collection

    def get_collection(self, collection_id: str) -> Optional[Collection]:
        """
        Get collection by ID.

        Args:
            collection_id: Collection ID

        Returns:
            Collection if found, None otherwise
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM collections WHERE id = ?",
                (collection_id,),
            )
            row = cursor.fetchone()

        if not row:
            return None

        data = dict(row)
        if data.get("tag_filter"):
            data["tag_filter"] = json.loads(data["tag_filter"])
        data["auto_generated"] = bool(data.get("auto_generated", 0))

        return Collection(**data)

    def get_collection_by_name(self, name: str) -> Optional[Collection]:
        """
        Get collection by name.

        Args:
            name: Collection name

        Returns:
            Collection if found, None otherwise
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM collections WHERE name = ?",
                (name,),
            )
            row = cursor.fetchone()

        if not row:
            return None

        data = dict(row)
        if data.get("tag_filter"):
            data["tag_filter"] = json.loads(data["tag_filter"])
        data["auto_generated"] = bool(data.get("auto_generated", 0))

        return Collection(**data)

    def list_collections(self) -> List[Collection]:
        """
        List all collections.

        Returns:
            List of collections
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM collections ORDER BY name"
            )
            rows = cursor.fetchall()

        collections = []
        for row in rows:
            data = dict(row)
            if data.get("tag_filter"):
                data["tag_filter"] = json.loads(data["tag_filter"])
            data["auto_generated"] = bool(data.get("auto_generated", 0))
            collections.append(Collection(**data))

        return collections

    def add_to_collection(self, collection_id: str, memory_ids: List[str]) -> None:
        """
        Add memories to a collection.

        Args:
            collection_id: Collection ID
            memory_ids: List of memory IDs to add

        Raises:
            ValidationError: If collection not found
            StorageError: If database error occurs
        """
        collection = self.get_collection(collection_id)
        if not collection:
            raise ValidationError(f"Collection not found: {collection_id}")

        try:
            with sqlite3.connect(self.db_path) as conn:
                for memory_id in memory_ids:
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO collection_memories (collection_id, memory_id, added_at)
                        VALUES (?, ?, ?)
                        """,
                        (collection_id, memory_id, datetime.now(UTC).isoformat()),
                    )
                conn.execute(
                    "UPDATE collections SET updated_at = ? WHERE id = ?",
                    (datetime.now(UTC).isoformat(), collection_id),
                )
                conn.commit()
        except sqlite3.Error as e:
            raise StorageError(f"Failed to add memories to collection: {e}") from e

    def remove_from_collection(self, collection_id: str, memory_ids: List[str]) -> None:
        """
        Remove memories from a collection.

        Args:
            collection_id: Collection ID
            memory_ids: List of memory IDs to remove

        Raises:
            StorageError: If database error occurs
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                placeholders = ",".join("?" * len(memory_ids))
                conn.execute(
                    f"""
                    DELETE FROM collection_memories
                    WHERE collection_id = ? AND memory_id IN ({placeholders})
                    """,
                    [collection_id] + memory_ids,
                )
                conn.execute(
                    "UPDATE collections SET updated_at = ? WHERE id = ?",
                    (datetime.now(UTC).isoformat(), collection_id),
                )
                conn.commit()
        except sqlite3.Error as e:
            raise StorageError(f"Failed to remove memories from collection: {e}") from e

    def get_collection_memories(self, collection_id: str) -> List[str]:
        """
        Get all memory IDs in a collection.

        Args:
            collection_id: Collection ID

        Returns:
            List of memory IDs
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT memory_id FROM collection_memories WHERE collection_id = ? ORDER BY added_at DESC",
                (collection_id,),
            )
            rows = cursor.fetchall()

        return [row[0] for row in rows]

    def delete_collection(self, collection_id: str) -> None:
        """
        Delete a collection.

        Args:
            collection_id: Collection ID to delete

        Raises:
            StorageError: If database error occurs
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "DELETE FROM collection_memories WHERE collection_id = ?",
                    (collection_id,),
                )
                conn.execute(
                    "DELETE FROM collections WHERE id = ?",
                    (collection_id,),
                )
                conn.commit()
        except sqlite3.Error as e:
            raise StorageError(f"Failed to delete collection: {e}") from e

    def auto_generate_collections(
        self, tag_patterns: Optional[Dict[str, List[str]]] = None
    ) -> List[Collection]:
        """
        Auto-generate collections based on common tag patterns.

        Args:
            tag_patterns: Optional dict of {collection_name: [tags]}
                         If None, uses default patterns

        Returns:
            List of auto-generated collections

        Default patterns:
        - "Python Async Patterns": ["python", "async"]
        - "React Components": ["react", "javascript"]
        - "Database Queries": ["database", "sql"]
        - "API Endpoints": ["api", "endpoint"]
        - "Testing Code": ["testing", "pytest"]
        """
        if tag_patterns is None:
            tag_patterns = {
                "Python Async Patterns": ["python", "async"],
                "React Components": ["react", "javascript"],
                "Database Queries": ["database", "sql"],
                "API Endpoints": ["api", "endpoint"],
                "Testing Code": ["testing", "pytest"],
                "FastAPI Routes": ["fastapi", "api"],
                "Authentication Logic": ["auth", "login"],
            }

        generated = []

        for name, tags in tag_patterns.items():
            # Check if collection already exists
            existing = self.get_collection_by_name(name)
            if existing:
                continue

            # Create collection with tag filter
            tag_filter = {"tags": tags, "op": "AND"}

            collection = Collection(
                name=name,
                description=f"Auto-generated collection for {', '.join(tags)} patterns",
                auto_generated=True,
                tag_filter=tag_filter,
            )

            try:
                with sqlite3.connect(self.db_path) as conn:
                    conn.execute(
                        """
                        INSERT INTO collections (id, name, description, auto_generated, tag_filter, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            collection.id,
                            collection.name,
                            collection.description,
                            1,
                            json.dumps(collection.tag_filter),
                            collection.created_at.isoformat(),
                            collection.updated_at.isoformat(),
                        ),
                    )
                    conn.commit()
                    generated.append(collection)
            except sqlite3.IntegrityError:
                # Collection already exists, skip
                pass

        return generated
