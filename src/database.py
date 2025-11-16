"""Database operations for Claude Memory + RAG system."""

import sqlite3
import json
import logging
import threading
import numpy as np
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import io
import hashlib

logger = logging.getLogger(__name__)


class MemoryDatabase:
    """Handles all database operations for unified memory and documentation storage."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = None
        self._write_lock = threading.Lock()
        self._initialize_db()

    def _initialize_db(self):
        """Initialize database with schema."""
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row

        # Read and execute schema
        schema_path = Path(__file__).parent / "schema.sql"
        with open(schema_path, 'r') as f:
            self.conn.executescript(f.read())
        self.conn.commit()

    def store_memory(
        self,
        content: str,
        category: str,
        memory_type: str,
        scope: str,
        project_name: Optional[str],
        embedding: np.ndarray,
        source_file: Optional[str] = None,
        heading: Optional[str] = None,
        tags: Optional[List[str]] = None,
        importance: float = 0.5
    ) -> int:
        """Store a memory with its embedding."""
        embedding_bytes = self._serialize_embedding(embedding)
        tags_json = json.dumps(tags) if tags else None

        with self._write_lock:
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT INTO memories (
                    content, category, memory_type, scope, project_name,
                    source_file, heading, embedding, tags, importance
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                content, category, memory_type, scope, project_name,
                source_file, heading, embedding_bytes, tags_json, importance
            ))

            self.conn.commit()
            return cursor.lastrowid

    def store_documentation(
        self,
        content: str,
        project_name: str,
        source_file: str,
        heading: str,
        embedding: np.ndarray,
        tags: Optional[List[str]] = None,
        importance: float = 0.6
    ) -> int:
        """Store a documentation chunk."""
        return self.store_memory(
            content=content,
            category='documentation',
            memory_type='documentation',
            scope='project',
            project_name=project_name,
            embedding=embedding,
            source_file=source_file,
            heading=heading,
            tags=tags,
            importance=importance
        )

    def retrieve_similar_memories(
        self,
        query_embedding: np.ndarray,
        limit: int = 10,
        filters: Optional[Dict] = None,
        min_importance: float = 0.0
    ) -> List[Dict]:
        """Retrieve memories similar to query embedding using cosine similarity."""
        cursor = self.conn.cursor()

        # Build query with filters
        query = """
            SELECT id, content, category, memory_type, scope, project_name,
                   source_file, heading, timestamp, tags, importance, embedding
            FROM memories
            WHERE importance >= ?
        """
        params = [min_importance]

        # Apply filters
        if filters:
            for key, value in filters.items():
                if value is not None:
                    query += f" AND {key} = ?"
                    params.append(value)

        cursor.execute(query, params)
        rows = cursor.fetchall()

        # Calculate cosine similarity for each memory
        results = []
        for row in rows:
            memory_embedding = self._deserialize_embedding(row['embedding'])
            similarity = self._cosine_similarity(query_embedding, memory_embedding)

            results.append({
                'id': row['id'],
                'content': row['content'],
                'category': row['category'],
                'memory_type': row['memory_type'],
                'scope': row['scope'],
                'project_name': row['project_name'],
                'source_file': row['source_file'],
                'heading': row['heading'],
                'timestamp': row['timestamp'],
                'tags': json.loads(row['tags']) if row['tags'] else [],
                'importance': row['importance'],
                'similarity': float(similarity)
            })

        # Sort by similarity and return top results
        results.sort(key=lambda x: x['similarity'], reverse=True)
        return results[:limit]

    def get_recent_memories(
        self,
        limit: int = 5,
        hours: int = 24,
        memory_type: Optional[str] = None
    ) -> List[Dict]:
        """Get recent memories from the last N hours."""
        cursor = self.conn.cursor()

        query = """
            SELECT id, content, category, memory_type, scope, project_name,
                   source_file, heading, timestamp, tags, importance
            FROM memories
            WHERE timestamp >= datetime('now', ?)
        """
        params = [f'-{hours} hours']

        if memory_type:
            query += " AND memory_type = ?"
            params.append(memory_type)

        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        cursor.execute(query, params)

        results = []
        for row in cursor.fetchall():
            results.append({
                'id': row['id'],
                'content': row['content'],
                'category': row['category'],
                'memory_type': row['memory_type'],
                'scope': row['scope'],
                'project_name': row['project_name'],
                'source_file': row['source_file'],
                'heading': row['heading'],
                'timestamp': row['timestamp'],
                'tags': json.loads(row['tags']) if row['tags'] else [],
                'importance': row['importance']
            })

        return results

    def delete_memory(self, memory_id: int) -> bool:
        """Delete a memory by ID."""
        with self._write_lock:
            cursor = self.conn.cursor()
            cursor.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
            self.conn.commit()
            return cursor.rowcount > 0

    def mark_doc_ingested(
        self,
        project_name: str,
        file_path: str,
        file_hash: str,
        chunk_count: int
    ):
        """Mark a documentation file as ingested."""
        with self._write_lock:
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO ingested_docs
                (project_name, file_path, file_hash, chunk_count, ingested_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (project_name, file_path, file_hash, chunk_count))
            self.conn.commit()

    def check_doc_changed(
        self,
        project_name: str,
        file_path: str,
        current_hash: str
    ) -> bool:
        """Check if a file has changed since last ingestion."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT file_hash FROM ingested_docs
            WHERE project_name = ? AND file_path = ?
        """, (project_name, file_path))

        row = cursor.fetchone()
        if not row:
            return True  # Not ingested yet, so "changed"

        return row['file_hash'] != current_hash

    def get_stats(self) -> Dict:
        """Get statistics about stored memories."""
        cursor = self.conn.cursor()

        cursor.execute("SELECT COUNT(*) as total FROM memories")
        total = cursor.fetchone()['total']

        cursor.execute("""
            SELECT category, COUNT(*) as count
            FROM memories
            GROUP BY category
        """)
        by_category = {row['category']: row['count'] for row in cursor.fetchall()}

        cursor.execute("""
            SELECT memory_type, COUNT(*) as count
            FROM memories
            GROUP BY memory_type
        """)
        by_type = {row['memory_type']: row['count'] for row in cursor.fetchall()}

        cursor.execute("""
            SELECT scope, COUNT(*) as count
            FROM memories
            GROUP BY scope
        """)
        by_scope = {row['scope']: row['count'] for row in cursor.fetchall()}

        cursor.execute("""
            SELECT project_name, COUNT(*) as count
            FROM memories
            WHERE project_name IS NOT NULL
            GROUP BY project_name
        """)
        by_project = {row['project_name']: row['count'] for row in cursor.fetchall()}

        return {
            'total': total,
            'by_category': by_category,
            'by_type': by_type,
            'by_scope': by_scope,
            'by_project': by_project
        }

    def _serialize_embedding(self, embedding: np.ndarray) -> bytes:
        """Serialize numpy array to bytes."""
        buffer = io.BytesIO()
        np.save(buffer, embedding, allow_pickle=False)
        return buffer.getvalue()

    def _deserialize_embedding(self, embedding_bytes: bytes) -> np.ndarray:
        """Deserialize bytes to numpy array."""
        buffer = io.BytesIO(embedding_bytes)
        return np.load(buffer, allow_pickle=False)

    def _cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """Calculate cosine similarity between two vectors."""
        dot_product = np.dot(a, b)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return dot_product / (norm_a * norm_b)

    def close(self):
        """Close database connection."""
        if self.conn:
            try:
                self.conn.close()
                logger.info("Database connection closed")
            except Exception as e:
                logger.error(f"Error closing database connection: {e}")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
        return False


def compute_file_hash(file_path: str) -> str:
    """Compute SHA-256 hash of file content."""
    hasher = hashlib.sha256()
    with open(file_path, 'rb') as f:
        # Read in chunks to handle large files efficiently
        for chunk in iter(lambda: f.read(8192), b''):
            hasher.update(chunk)
    return hasher.hexdigest()
