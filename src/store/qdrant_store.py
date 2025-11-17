"""Qdrant vector store implementation."""

import logging
from typing import List, Tuple, Optional, Dict, Any
from uuid import uuid4
from datetime import datetime, UTC

from qdrant_client import QdrantClient
from qdrant_client.models import (
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
    Range,
    SearchParams,
)

from src.store.base import MemoryStore
from src.store.qdrant_setup import QdrantSetup
from src.core.models import MemoryUnit, SearchFilters, MemoryCategory, ContextLevel, MemoryScope
from src.core.exceptions import StorageError, RetrievalError, MemoryNotFoundError, ValidationError
from src.config import ServerConfig

logger = logging.getLogger(__name__)


class QdrantMemoryStore(MemoryStore):
    """Qdrant implementation of the MemoryStore interface."""

    def __init__(self, config: Optional[ServerConfig] = None):
        """
        Initialize Qdrant memory store.

        Args:
            config: Server configuration. If None, uses global config.
        """
        if config is None:
            from src.config import get_config
            config = get_config()

        self.config = config
        self.setup = QdrantSetup(config)
        self.client: Optional[QdrantClient] = None
        self.collection_name = config.qdrant_collection_name

    async def initialize(self) -> None:
        """Initialize the Qdrant connection and collection."""
        try:
            self.client = self.setup.connect()
            self.setup.ensure_collection_exists()
            logger.info("Qdrant store initialized successfully")
        except Exception as e:
            raise StorageError(f"Failed to initialize Qdrant store: {e}")

    async def store(
        self,
        content: str,
        embedding: List[float],
        metadata: Dict[str, Any],
    ) -> str:
        """Store a single memory with its embedding and metadata."""
        if self.client is None:
            await self.initialize()

        try:
            # Build payload using helper method
            memory_id, payload = self._build_payload(content, embedding, metadata)

            # Create point
            point = PointStruct(
                id=memory_id,
                vector=embedding,
                payload=payload,
            )

            # Upsert to Qdrant
            self.client.upsert(
                collection_name=self.collection_name,
                points=[point],
            )

            logger.debug(f"Stored memory: {memory_id}")
            return memory_id

        except ValueError as e:
            # Invalid payload structure
            logger.error(f"Invalid payload for storage: {e}")
            raise ValidationError(f"Invalid memory payload: {e}")
        except ConnectionError as e:
            # Connection issues
            logger.error(f"Connection error during store: {e}")
            raise StorageError(f"Failed to connect to Qdrant: {e}")
        except Exception as e:
            # Generic fallback
            logger.error(f"Unexpected error storing memory: {e}")
            raise StorageError(f"Failed to store memory: {e}")

    async def retrieve(
        self,
        query_embedding: List[float],
        filters: Optional[SearchFilters] = None,
        limit: int = 5,
    ) -> List[Tuple[MemoryUnit, float]]:
        """Retrieve memories similar to the query embedding."""
        if self.client is None:
            await self.initialize()

        try:
            # Cap limit to prevent memory/performance issues from unbounded queries
            safe_limit = min(limit, 100)
            if limit != safe_limit:
                logger.debug(f"Limiting search result count from {limit} to {safe_limit}")

            # Build filter conditions
            filter_conditions = self._build_filter(filters) if filters else None

            # Search using new query API
            search_result = self.client.query_points(
                collection_name=self.collection_name,
                query=query_embedding,
                query_filter=filter_conditions,
                limit=safe_limit,
                with_payload=True,
                with_vectors=False,
                search_params=SearchParams(
                    hnsw_ef=128,  # Search accuracy
                    exact=False,  # Use HNSW index
                ),
            ).points

            # Convert results to MemoryUnit tuples
            results = []
            for hit in search_result:
                try:
                    memory = self._payload_to_memory_unit(hit.payload)
                    score = float(hit.score)
                    results.append((memory, score))
                except ValueError as e:
                    logger.warning(f"Failed to parse search result payload: {e}")
                    continue

            logger.debug(f"Retrieved {len(results)} memories")
            return results

        except ConnectionError as e:
            logger.error(f"Connection error during retrieval: {e}")
            raise RetrievalError(f"Failed to connect to Qdrant: {e}")
        except ValueError as e:
            logger.error(f"Invalid filter or query: {e}")
            raise RetrievalError(f"Invalid search parameters: {e}")
        except Exception as e:
            logger.error(f"Unexpected error during retrieval: {e}")
            raise RetrievalError(f"Failed to retrieve memories: {e}")

    async def delete(self, memory_id: str) -> bool:
        """Delete a memory by its ID."""
        if self.client is None:
            await self.initialize()

        try:
            result = self.client.delete(
                collection_name=self.collection_name,
                points_selector=[memory_id],
            )

            deleted = result.status == "completed"
            if deleted:
                logger.debug(f"Deleted memory: {memory_id}")
            return deleted

        except Exception as e:
            raise StorageError(f"Failed to delete memory: {e}")

    async def batch_store(
        self,
        items: List[Tuple[str, List[float], Dict[str, Any]]],
    ) -> List[str]:
        """Store multiple memories in a batch operation."""
        if self.client is None:
            await self.initialize()

        try:
            if not items:
                return []

            points = []
            memory_ids = []

            for content, embedding, metadata in items:
                # Build payload using helper method
                memory_id, payload = self._build_payload(content, embedding, metadata)
                memory_ids.append(memory_id)

                points.append(PointStruct(
                    id=memory_id,
                    vector=embedding,
                    payload=payload,
                ))

            # Batch upsert
            self.client.upsert(
                collection_name=self.collection_name,
                points=points,
            )

            logger.debug(f"Batch stored {len(memory_ids)} memories")
            return memory_ids

        except ValueError as e:
            logger.error(f"Invalid payload in batch: {e}")
            raise ValidationError(f"Invalid memory payload in batch: {e}")
        except ConnectionError as e:
            logger.error(f"Connection error during batch store: {e}")
            raise StorageError(f"Failed to connect to Qdrant: {e}")
        except Exception as e:
            logger.error(f"Unexpected error in batch store: {e}")
            raise StorageError(f"Failed to batch store memories: {e}")

    async def search_with_filters(
        self,
        query_embedding: List[float],
        filters: SearchFilters,
        limit: int = 5,
    ) -> List[Tuple[MemoryUnit, float]]:
        """Search memories with specific filters applied."""
        return await self.retrieve(query_embedding, filters, limit)

    async def get_by_id(self, memory_id: str) -> Optional[MemoryUnit]:
        """Retrieve a specific memory by its ID."""
        if self.client is None:
            await self.initialize()

        try:
            result = self.client.retrieve(
                collection_name=self.collection_name,
                ids=[memory_id],
                with_payload=True,
                with_vectors=False,
            )

            if not result:
                return None

            return self._payload_to_memory_unit(result[0].payload)

        except Exception as e:
            logger.error(f"Failed to get memory by ID: {e}")
            return None

    async def count(self, filters: Optional[SearchFilters] = None) -> int:
        """Count the number of memories, optionally with filters."""
        if self.client is None:
            await self.initialize()

        try:
            if not filters:
                # No filters - return total collection count
                collection_info = self.client.get_collection(self.collection_name)
                return collection_info.points_count
            
            # Count with filters by scrolling through all matching points
            filter_conditions = self._build_filter(filters)
            total = 0
            offset = None
            
            while True:
                points, offset = self.client.scroll(
                    collection_name=self.collection_name,
                    scroll_filter=filter_conditions,
                    offset=offset,
                    limit=100,
                    with_payload=False,
                    with_vectors=False,
                )
                
                total += len(points)
                
                # No more points to scroll through
                if not points or offset is None:
                    break
            
            return total

        except Exception as e:
            logger.error(f"Failed to count memories: {e}")
            return 0

    async def update(self, memory_id: str, updates: Dict[str, Any]) -> bool:
        """Update a memory's metadata."""
        if self.client is None:
            await self.initialize()

        try:
            # Get existing memory
            existing = await self.get_by_id(memory_id)
            if not existing:
                return False

            # Update timestamp
            updates["updated_at"] = datetime.now(UTC).isoformat()

            # Set payload (merge with existing)
            self.client.set_payload(
                collection_name=self.collection_name,
                payload=updates,
                points=[memory_id],
            )

            logger.debug(f"Updated memory: {memory_id}")
            return True

        except Exception as e:
            raise StorageError(f"Failed to update memory: {e}")

    async def health_check(self) -> bool:
        """Check if the storage backend is healthy and accessible."""
        return self.setup.health_check()

    async def close(self) -> None:
        """Close connections and clean up resources."""
        if self.client:
            self.client.close()
            self.client = None
            logger.info("Qdrant store closed")

    def _build_payload(
        self,
        content: str,
        embedding: List[float],
        metadata: Dict[str, Any],
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Build a standard memory payload for storage.

        Args:
            content: Memory content text.
            embedding: Vector embedding (used for ID generation context).
            metadata: Memory metadata.

        Returns:
            Tuple of (memory_id, payload_dict).
        """
        memory_id = metadata.get("id", str(uuid4()))

        payload = {
            "id": memory_id,
            "content": content,
            "category": metadata.get("category"),
            "context_level": metadata.get("context_level"),
            "scope": metadata.get("scope", "global"),
            "project_name": metadata.get("project_name"),
            "importance": metadata.get("importance", 0.5),
            "embedding_model": metadata.get("embedding_model", "all-MiniLM-L6-v2"),
            "created_at": metadata.get("created_at", datetime.now(UTC)).isoformat(),
            "updated_at": datetime.now(UTC).isoformat(),
            "tags": metadata.get("tags", []),
            **metadata.get("metadata", {}),
        }

        return memory_id, payload

    def _build_field_condition(
        self,
        key: str,
        value: Any,
        use_range: bool = False,
    ) -> Optional[FieldCondition]:
        """
        Build a single field condition for filtering.

        Args:
            key: Field name.
            value: Field value to match.
            use_range: If True, treat as range condition (for numeric fields).

        Returns:
            FieldCondition, or None if value is empty.
        """
        if value is None:
            return None

        if use_range:
            # Range condition for numeric fields like importance
            if isinstance(value, (int, float)) and value > 0.0:
                return FieldCondition(key=key, range=Range(gte=value))
            return None

        # Match condition for enums and strings
        if hasattr(value, 'value'):  # Enum
            return FieldCondition(key=key, match=MatchValue(value=value.value))
        elif isinstance(value, (str, int, float)) and value:
            return FieldCondition(key=key, match=MatchValue(value=value))

        return None

    def _build_filter(self, filters: SearchFilters) -> Optional[Filter]:
        """
        Build Qdrant filter from SearchFilters.

        Args:
            filters: Search filters to apply.

        Returns:
            Filter: Qdrant filter object, or None if no filters.
        """
        conditions = []

        # Add context level condition
        context_condition = self._build_field_condition(
            "context_level", filters.context_level
        )
        if context_condition:
            conditions.append(context_condition)

        # Add scope condition
        scope_condition = self._build_field_condition("scope", filters.scope)
        if scope_condition:
            conditions.append(scope_condition)

        # Add category condition
        category_condition = self._build_field_condition(
            "category", filters.category
        )
        if category_condition:
            conditions.append(category_condition)

        # Add project name condition
        if filters.project_name:
            project_condition = self._build_field_condition(
                "project_name", filters.project_name
            )
            if project_condition:
                conditions.append(project_condition)

        # Add importance range condition
        importance_condition = self._build_field_condition(
            "importance", filters.min_importance, use_range=True
        )
        if importance_condition:
            conditions.append(importance_condition)

        # Add tag conditions (multiple tags as OR conditions would require nested logic)
        if filters.tags:
            for tag in filters.tags:
                tag_condition = self._build_field_condition("tags", tag)
                if tag_condition:
                    conditions.append(tag_condition)

        if not conditions:
            return None

        return Filter(must=conditions)

    def _payload_to_memory_unit(self, payload: Dict[str, Any]) -> MemoryUnit:
        """
        Convert Qdrant payload to MemoryUnit.

        Args:
            payload: Qdrant point payload.

        Returns:
            MemoryUnit: Parsed memory unit.
        """
        # Parse datetime strings
        created_at = payload.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        elif created_at is None:
            created_at = datetime.now(UTC)

        updated_at = payload.get("updated_at")
        if isinstance(updated_at, str):
            updated_at = datetime.fromisoformat(updated_at)
        elif updated_at is None:
            updated_at = datetime.now(UTC)

        # Parse enums
        category = MemoryCategory(payload.get("category", "context"))
        context_level = ContextLevel(payload.get("context_level", "PROJECT_CONTEXT"))
        scope = MemoryScope(payload.get("scope", "global"))

        # Extract metadata fields (these were flattened by batch_store with **metadata)
        # Known standard fields that shouldn't go into metadata
        standard_fields = {
            "id", "content", "category", "context_level", "scope",
            "project_name", "importance", "embedding_model",
            "created_at", "updated_at", "tags"
        }

        # Collect any extra fields as metadata
        metadata = {}
        for key, value in payload.items():
            if key not in standard_fields:
                metadata[key] = value

        return MemoryUnit(
            id=payload["id"],
            content=payload["content"],
            category=category,
            context_level=context_level,
            scope=scope,
            project_name=payload.get("project_name"),
            importance=payload.get("importance", 0.5),
            embedding_model=payload.get("embedding_model", "all-MiniLM-L6-v2"),
            created_at=created_at,
            updated_at=updated_at,
            tags=payload.get("tags", []),
            metadata=metadata,
        )
