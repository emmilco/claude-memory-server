"""Tag hierarchy management and CRUD operations."""

import sqlite3
from typing import List, Optional, Dict
from pathlib import Path

from src.tagging.models import Tag, TagCreate
from src.core.exceptions import ValidationError, StorageError


class TagManager:
    """
    Manage hierarchical tags with CRUD operations.

    Features:
    - Create, read, update, delete tags
    - Hierarchy validation
    - Tag normalization
    - Merge duplicate tags
    - Get ancestors and descendants
    """

    def __init__(self, db_path: str):
        """
        Initialize tag manager.

        Args:
            db_path: Path to SQLite database
        """
        self.db_path = db_path
        self._ensure_tables()

    def _ensure_tables(self) -> None:
        """Create tags table if not exists."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tags (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    parent_id TEXT REFERENCES tags(id),
                    level INTEGER NOT NULL,
                    full_path TEXT NOT NULL UNIQUE,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_tags_parent ON tags(parent_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_tags_path ON tags(full_path)")

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS memory_tags (
                    memory_id TEXT NOT NULL,
                    tag_id TEXT NOT NULL,
                    confidence REAL DEFAULT 1.0,
                    auto_generated INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (memory_id, tag_id)
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_memory_tags_memory ON memory_tags(memory_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_memory_tags_tag ON memory_tags(tag_id)"
            )
            conn.commit()

    def create_tag(self, tag_create: TagCreate) -> Tag:
        """
        Create a new tag.

        Args:
            tag_create: Tag creation request

        Returns:
            Created tag

        Raises:
            ValidationError: If tag validation fails
            StorageError: If tag already exists or database error
        """
        # Normalize name
        name = tag_create.name.strip().lower()

        # Get parent tag if specified
        parent_tag = None
        if tag_create.parent_id:
            parent_tag = self.get_tag(tag_create.parent_id)
            if not parent_tag:
                raise ValidationError(f"Parent tag not found: {tag_create.parent_id}")

            # Validate hierarchy depth
            if parent_tag.level >= 3:  # Max 4 levels (0-3)
                raise ValidationError("Tag hierarchy cannot exceed 4 levels")

        # Build full path
        if parent_tag:
            level = parent_tag.level + 1
            full_path = f"{parent_tag.full_path}/{name}"
        else:
            level = 0
            full_path = name

        # Create tag object
        tag = Tag(
            name=name,
            parent_id=tag_create.parent_id,
            level=level,
            full_path=full_path,
        )

        # Store in database
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    INSERT INTO tags (id, name, parent_id, level, full_path, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        tag.id,
                        tag.name,
                        tag.parent_id,
                        tag.level,
                        tag.full_path,
                        tag.created_at.isoformat(),
                    ),
                )
                conn.commit()
        except sqlite3.IntegrityError as e:
            if "UNIQUE constraint failed" in str(e):
                raise StorageError(f"Tag already exists: {full_path}")
            raise StorageError(f"Failed to create tag: {e}") from e

        return tag

    def get_tag(self, tag_id: str) -> Optional[Tag]:
        """
        Get tag by ID.

        Args:
            tag_id: Tag ID

        Returns:
            Tag if found, None otherwise
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM tags WHERE id = ?",
                (tag_id,),
            )
            row = cursor.fetchone()

        if not row:
            return None

        return Tag(**dict(row))

    def get_tag_by_path(self, full_path: str) -> Optional[Tag]:
        """
        Get tag by full path.

        Args:
            full_path: Tag full path (e.g., "language/python")

        Returns:
            Tag if found, None otherwise
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM tags WHERE full_path = ?",
                (full_path.lower(),),
            )
            row = cursor.fetchone()

        if not row:
            return None

        return Tag(**dict(row))

    def list_tags(self, parent_id: Optional[str] = None, prefix: str = "") -> List[Tag]:
        """
        List tags, optionally filtered by parent or prefix.

        Args:
            parent_id: Filter by parent tag ID (None = root tags)
            prefix: Filter by path prefix (e.g., "language/")

        Returns:
            List of tags
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            if prefix:
                cursor = conn.execute(
                    "SELECT * FROM tags WHERE full_path LIKE ? ORDER BY full_path",
                    (f"{prefix}%",),
                )
            elif parent_id:
                cursor = conn.execute(
                    "SELECT * FROM tags WHERE parent_id = ? ORDER BY name",
                    (parent_id,),
                )
            else:
                cursor = conn.execute(
                    "SELECT * FROM tags WHERE parent_id IS NULL ORDER BY name"
                )

            rows = cursor.fetchall()

        return [Tag(**dict(row)) for row in rows]

    def get_ancestors(self, tag_id: str) -> List[Tag]:
        """
        Get all ancestor tags (parent, grandparent, etc.).

        Args:
            tag_id: Tag ID

        Returns:
            List of ancestor tags, ordered from root to parent
        """
        ancestors = []
        current_tag = self.get_tag(tag_id)

        while current_tag and current_tag.parent_id:
            parent = self.get_tag(current_tag.parent_id)
            if parent:
                ancestors.insert(0, parent)
                current_tag = parent
            else:
                break

        return ancestors

    def get_descendants(self, tag_id: str) -> List[Tag]:
        """
        Get all descendant tags (children, grandchildren, etc.).

        Args:
            tag_id: Tag ID

        Returns:
            List of descendant tags
        """
        tag = self.get_tag(tag_id)
        if not tag:
            return []

        descendants = []
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM tags WHERE full_path LIKE ? AND id != ? ORDER BY full_path",
                (f"{tag.full_path}/%", tag_id),
            )
            rows = cursor.fetchall()

        return [Tag(**dict(row)) for row in rows]

    def delete_tag(self, tag_id: str, cascade: bool = False) -> None:
        """
        Delete a tag.

        Args:
            tag_id: Tag ID to delete
            cascade: If True, delete all descendants. If False, reassign children to parent

        Raises:
            ValidationError: If tag has children and cascade=False
            StorageError: If database error occurs
        """
        tag = self.get_tag(tag_id)
        if not tag:
            raise ValidationError(f"Tag not found: {tag_id}")

        descendants = self.get_descendants(tag_id)

        if descendants and not cascade:
            raise ValidationError(
                f"Tag has {len(descendants)} descendants. Use cascade=True to delete all."
            )

        try:
            with sqlite3.connect(self.db_path) as conn:
                if cascade:
                    # Delete all descendants
                    for desc in descendants:
                        conn.execute("DELETE FROM memory_tags WHERE tag_id = ?", (desc.id,))
                        conn.execute("DELETE FROM tags WHERE id = ?", (desc.id,))

                # Delete memory associations
                conn.execute("DELETE FROM memory_tags WHERE tag_id = ?", (tag_id,))

                # Delete tag
                conn.execute("DELETE FROM tags WHERE id = ?", (tag_id,))
                conn.commit()
        except sqlite3.Error as e:
            raise StorageError(f"Failed to delete tag: {e}") from e

    def merge_tags(self, source_tag_id: str, target_tag_id: str) -> None:
        """
        Merge source tag into target tag.

        All memories tagged with source will be retagged with target.
        Source tag will be deleted.

        Args:
            source_tag_id: Tag to merge from
            target_tag_id: Tag to merge into

        Raises:
            ValidationError: If tags not found or invalid
            StorageError: If database error occurs
        """
        source = self.get_tag(source_tag_id)
        target = self.get_tag(target_tag_id)

        if not source:
            raise ValidationError(f"Source tag not found: {source_tag_id}")
        if not target:
            raise ValidationError(f"Target tag not found: {target_tag_id}")

        try:
            with sqlite3.connect(self.db_path) as conn:
                # Update all memory_tags associations
                # First, try to update
                conn.execute(
                    """
                    UPDATE OR IGNORE memory_tags
                    SET tag_id = ?
                    WHERE tag_id = ?
                    """,
                    (target_tag_id, source_tag_id),
                )

                # Delete remaining duplicates
                conn.execute(
                    "DELETE FROM memory_tags WHERE tag_id = ?",
                    (source_tag_id,),
                )

                # Delete source tag
                conn.execute("DELETE FROM tags WHERE id = ?", (source_tag_id,))
                conn.commit()
        except sqlite3.Error as e:
            raise StorageError(f"Failed to merge tags: {e}") from e

    def tag_memory(
        self, memory_id: str, tag_id: str, confidence: float = 1.0, auto_generated: bool = False
    ) -> None:
        """
        Associate a tag with a memory.

        Args:
            memory_id: Memory ID
            tag_id: Tag ID
            confidence: Confidence score (0-1)
            auto_generated: Whether tag was auto-generated

        Raises:
            StorageError: If database error occurs
        """
        from datetime import datetime, UTC

        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO memory_tags
                    (memory_id, tag_id, confidence, auto_generated, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        memory_id,
                        tag_id,
                        confidence,
                        1 if auto_generated else 0,
                        datetime.now(UTC).isoformat(),
                    ),
                )
                conn.commit()
        except sqlite3.Error as e:
            raise StorageError(f"Failed to tag memory: {e}") from e

    def untag_memory(self, memory_id: str, tag_id: str) -> None:
        """
        Remove a tag from a memory.

        Args:
            memory_id: Memory ID
            tag_id: Tag ID

        Raises:
            StorageError: If database error occurs
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "DELETE FROM memory_tags WHERE memory_id = ? AND tag_id = ?",
                    (memory_id, tag_id),
                )
                conn.commit()
        except sqlite3.Error as e:
            raise StorageError(f"Failed to untag memory: {e}") from e

    def get_memory_tags(self, memory_id: str) -> List[Tag]:
        """
        Get all tags for a memory.

        Args:
            memory_id: Memory ID

        Returns:
            List of tags associated with the memory
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT t.* FROM tags t
                JOIN memory_tags mt ON t.id = mt.tag_id
                WHERE mt.memory_id = ?
                ORDER BY t.full_path
                """,
                (memory_id,),
            )
            rows = cursor.fetchall()

        return [Tag(**dict(row)) for row in rows]

    def get_or_create_tag(self, full_path: str) -> Tag:
        """
        Get tag by path, creating hierarchy if needed.

        Args:
            full_path: Full tag path (e.g., "language/python/async")

        Returns:
            Tag (existing or newly created)
        """
        # Check if tag exists
        existing = self.get_tag_by_path(full_path)
        if existing:
            return existing

        # Create hierarchy
        parts = full_path.split("/")
        parent_id = None

        for i, part in enumerate(parts):
            current_path = "/".join(parts[: i + 1])
            existing_tag = self.get_tag_by_path(current_path)

            if existing_tag:
                parent_id = existing_tag.id
            else:
                tag_create = TagCreate(name=part, parent_id=parent_id)
                created_tag = self.create_tag(tag_create)
                parent_id = created_tag.id

        # Return final tag
        return self.get_tag_by_path(full_path)  # type: ignore
