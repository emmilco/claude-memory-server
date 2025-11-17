"""Qdrant vector store implementation."""

import logging
from enum import Enum
from typing import List, Tuple, Optional, Dict, Any, Union
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

        now = datetime.now(UTC)
        created_at = metadata.get("created_at", now)
        if isinstance(created_at, datetime):
            created_at = created_at.isoformat()

        last_accessed = metadata.get("last_accessed", now)
        if isinstance(last_accessed, datetime):
            last_accessed = last_accessed.isoformat()

        # Extract and serialize provenance
        provenance = metadata.get("provenance", {})
        if not isinstance(provenance, dict):
            provenance = provenance.model_dump() if hasattr(provenance, 'model_dump') else {}

        provenance_last_confirmed = provenance.get("last_confirmed")
        if provenance_last_confirmed and isinstance(provenance_last_confirmed, datetime):
            provenance_last_confirmed = provenance_last_confirmed.isoformat()

        payload = {
            "id": memory_id,
            "content": content,
            "category": metadata.get("category"),
            "context_level": metadata.get("context_level"),
            "scope": metadata.get("scope", "global"),
            "project_name": metadata.get("project_name"),
            "importance": metadata.get("importance", 0.5),
            "embedding_model": metadata.get("embedding_model", "all-MiniLM-L6-v2"),
            "created_at": created_at,
            "updated_at": now.isoformat(),
            "last_accessed": last_accessed,
            "lifecycle_state": metadata.get("lifecycle_state", "ACTIVE"),
            "tags": metadata.get("tags", []),
            # Provenance fields
            "provenance_source": provenance.get("source", "user_explicit"),
            "provenance_created_by": provenance.get("created_by", "user_statement"),
            "provenance_last_confirmed": provenance_last_confirmed,
            "provenance_confidence": provenance.get("confidence", 0.8),
            "provenance_verified": provenance.get("verified", False),
            "provenance_conversation_id": provenance.get("conversation_id"),
            "provenance_file_context": provenance.get("file_context", []),
            "provenance_notes": provenance.get("notes"),
            **metadata.get("metadata", {}),
        }

        return memory_id, payload

    def _build_field_condition(
        self,
        key: str,
        value: Optional[Union[str, int, float, Enum]],
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
        from src.core.models import LifecycleState, MemoryProvenance, ProvenanceSource

        # Parse datetime strings
        created_at = payload.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
            # Ensure timezone-aware
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=UTC)
        elif created_at is None:
            created_at = datetime.now(UTC)

        updated_at = payload.get("updated_at")
        if isinstance(updated_at, str):
            updated_at = datetime.fromisoformat(updated_at)
            # Ensure timezone-aware
            if updated_at.tzinfo is None:
                updated_at = updated_at.replace(tzinfo=UTC)
        elif updated_at is None:
            updated_at = datetime.now(UTC)

        last_accessed = payload.get("last_accessed", updated_at)
        if isinstance(last_accessed, str):
            last_accessed = datetime.fromisoformat(last_accessed)
            # Ensure timezone-aware
            if last_accessed.tzinfo is None:
                last_accessed = last_accessed.replace(tzinfo=UTC)
        elif last_accessed is None:
            last_accessed = updated_at

        # Parse enums
        category = MemoryCategory(payload.get("category", "context"))
        context_level = ContextLevel(payload.get("context_level", "PROJECT_CONTEXT"))
        scope = MemoryScope(payload.get("scope", "global"))

        # Parse lifecycle state
        lifecycle_state_str = payload.get("lifecycle_state", "ACTIVE")
        try:
            lifecycle_state = LifecycleState(lifecycle_state_str)
        except ValueError:
            lifecycle_state = LifecycleState.ACTIVE

        # Parse provenance
        provenance_last_confirmed = payload.get("provenance_last_confirmed")
        if provenance_last_confirmed and isinstance(provenance_last_confirmed, str):
            provenance_last_confirmed = datetime.fromisoformat(provenance_last_confirmed)
            # Ensure timezone-aware
            if provenance_last_confirmed.tzinfo is None:
                provenance_last_confirmed = provenance_last_confirmed.replace(tzinfo=UTC)

        provenance = MemoryProvenance(
            source=ProvenanceSource(payload.get("provenance_source", "user_explicit")),
            created_by=payload.get("provenance_created_by", "user_statement"),
            last_confirmed=provenance_last_confirmed,
            confidence=float(payload.get("provenance_confidence", 0.8)),
            verified=bool(payload.get("provenance_verified", False)),
            conversation_id=payload.get("provenance_conversation_id"),
            file_context=payload.get("provenance_file_context", []),
            notes=payload.get("provenance_notes")
        )

        # Extract metadata fields (these were flattened by batch_store with **metadata)
        # Known standard fields that shouldn't go into metadata
        standard_fields = {
            "id", "content", "category", "context_level", "scope",
            "project_name", "importance", "embedding_model",
            "created_at", "updated_at", "last_accessed", "lifecycle_state", "tags",
            "provenance_source", "provenance_created_by", "provenance_last_confirmed",
            "provenance_confidence", "provenance_verified", "provenance_conversation_id",
            "provenance_file_context", "provenance_notes"
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
            last_accessed=last_accessed,
            lifecycle_state=lifecycle_state,
            provenance=provenance,
            tags=payload.get("tags", []),
            metadata=metadata,
        )

    async def get_all_projects(self) -> List[str]:
        """
        Get list of all unique project names in the store.

        Returns:
            List of project names.
        """
        if not self.client:
            raise StorageError("Store not initialized")

        try:
            # Scroll through all points and collect unique project names
            projects = set()
            offset = None

            while True:
                results, offset = self.client.scroll(
                    collection_name=self.collection_name,
                    limit=100,
                    offset=offset,
                    with_payload=True,
                    with_vectors=False,
                )

                if not results:
                    break

                for point in results:
                    project_name = point.payload.get("project_name")
                    if project_name:
                        projects.add(project_name)

                if offset is None:
                    break

            return sorted(list(projects))

        except Exception as e:
            logger.error(f"Error getting all projects: {e}")
            raise StorageError(f"Failed to get projects: {e}")

    async def get_project_stats(self, project_name: str) -> Dict[str, Any]:
        """
        Get statistics for a specific project.

        Args:
            project_name: Name of the project.

        Returns:
            Dictionary with project statistics (total_memories, categories, etc.).
        """
        if not self.client:
            raise StorageError("Store not initialized")

        try:
            # Get all memories for this project
            offset = None
            total_memories = 0
            categories = {}
            context_levels = {}
            latest_update = None
            file_paths = set()

            while True:
                results, offset = self.client.scroll(
                    collection_name=self.collection_name,
                    scroll_filter=Filter(
                        must=[
                            FieldCondition(
                                key="project_name",
                                match=MatchValue(value=project_name)
                            )
                        ]
                    ),
                    limit=100,
                    offset=offset,
                    with_payload=True,
                    with_vectors=False,
                )

                if not results:
                    break

                for point in results:
                    total_memories += 1
                    payload = point.payload

                    # Count by category
                    category = payload.get("category", "unknown")
                    categories[category] = categories.get(category, 0) + 1

                    # Count by context level
                    context = payload.get("context_level", "unknown")
                    context_levels[context] = context_levels.get(context, 0) + 1

                    # Track latest update
                    updated_at = payload.get("updated_at")
                    if updated_at:
                        if isinstance(updated_at, str):
                            updated_at = datetime.fromisoformat(updated_at)
                            # Ensure timezone-aware
                            if updated_at.tzinfo is None:
                                updated_at = updated_at.replace(tzinfo=UTC)
                        if latest_update is None or updated_at > latest_update:
                            latest_update = updated_at

                    # Collect unique file paths (for code category)
                    if category == "code":
                        file_path = payload.get("file_path")
                        if file_path:
                            file_paths.add(file_path)

                if offset is None:
                    break

            # Calculate derived stats
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
        Update usage tracking for a single memory (stored in payload).

        Args:
            usage_data: Dictionary with memory_id, first_seen, last_used, use_count, last_search_score

        Returns:
            True if successful
        """
        if not self.client:
            raise StorageError("Store not initialized")

        try:
            memory_id = usage_data["memory_id"]

            # Get current point
            points = self.client.retrieve(
                collection_name=self.collection_name,
                ids=[memory_id],
                with_payload=True,
                with_vectors=True,
            )

            if not points:
                logger.warning(f"Memory {memory_id} not found for usage update")
                return False

            point = points[0]
            payload = dict(point.payload)

            # Update usage tracking fields in payload
            payload["usage_first_seen"] = usage_data.get("first_seen")
            payload["usage_last_used"] = usage_data["last_used"]
            payload["usage_count"] = usage_data["use_count"]
            payload["usage_last_score"] = usage_data["last_search_score"]

            # Update point with new payload
            self.client.upsert(
                collection_name=self.collection_name,
                points=[
                    PointStruct(
                        id=point.id,
                        vector=point.vector,
                        payload=payload,
                    )
                ],
            )

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
        if not self.client:
            raise StorageError("Store not initialized")

        try:
            # Retrieve all points at once
            memory_ids = [data["memory_id"] for data in usage_data_list]

            points = self.client.retrieve(
                collection_name=self.collection_name,
                ids=memory_ids,
                with_payload=True,
                with_vectors=True,
            )

            # Create lookup for usage data
            usage_lookup = {data["memory_id"]: data for data in usage_data_list}

            # Update points
            updated_points = []
            for point in points:
                usage_data = usage_lookup.get(str(point.id))
                if not usage_data:
                    continue

                payload = dict(point.payload)
                payload["usage_first_seen"] = usage_data.get("first_seen")
                payload["usage_last_used"] = usage_data["last_used"]
                payload["usage_count"] = usage_data["use_count"]
                payload["usage_last_score"] = usage_data["last_search_score"]

                updated_points.append(
                    PointStruct(
                        id=point.id,
                        vector=point.vector,
                        payload=payload,
                    )
                )

            if updated_points:
                self.client.upsert(
                    collection_name=self.collection_name,
                    points=updated_points,
                )
                logger.debug(f"Batch updated {len(updated_points)} usage records")

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
        if not self.client:
            raise StorageError("Store not initialized")

        try:
            points = self.client.retrieve(
                collection_name=self.collection_name,
                ids=[memory_id],
                with_payload=True,
                with_vectors=False,
            )

            if not points:
                return None

            payload = points[0].payload

            return {
                "memory_id": memory_id,
                "first_seen": payload.get("usage_first_seen"),
                "last_used": payload.get("usage_last_used"),
                "use_count": payload.get("usage_count", 0),
                "last_search_score": payload.get("usage_last_score", 0.0),
            }

        except Exception as e:
            logger.error(f"Failed to get usage stats: {e}")
            return None

    async def get_all_usage_stats(self) -> List[Dict[str, Any]]:
        """Get all usage statistics."""
        if not self.client:
            raise StorageError("Store not initialized")

        try:
            stats = []
            offset = None

            while True:
                results, offset = self.client.scroll(
                    collection_name=self.collection_name,
                    limit=100,
                    offset=offset,
                    with_payload=True,
                    with_vectors=False,
                )

                if not results:
                    break

                for point in results:
                    payload = point.payload
                    if "usage_count" in payload:  # Has usage tracking
                        stats.append({
                            "memory_id": point.id,
                            "first_seen": payload.get("usage_first_seen"),
                            "last_used": payload.get("usage_last_used"),
                            "use_count": payload.get("usage_count", 0),
                            "last_search_score": payload.get("usage_last_score", 0.0),
                        })

                if offset is None:
                    break

            return stats

        except Exception as e:
            logger.error(f"Failed to get all usage stats: {e}")
            return []

    async def delete_usage_tracking(self, memory_id: str) -> bool:
        """
        Delete usage tracking for a memory (remove from payload).

        Args:
            memory_id: Memory ID

        Returns:
            True if deleted
        """
        if not self.client:
            raise StorageError("Store not initialized")

        try:
            points = self.client.retrieve(
                collection_name=self.collection_name,
                ids=[memory_id],
                with_payload=True,
                with_vectors=True,
            )

            if not points:
                return False

            point = points[0]
            payload = dict(point.payload)

            # Remove usage tracking fields
            payload.pop("usage_first_seen", None)
            payload.pop("usage_last_used", None)
            payload.pop("usage_count", None)
            payload.pop("usage_last_score", None)

            # Update point
            self.client.upsert(
                collection_name=self.collection_name,
                points=[
                    PointStruct(
                        id=point.id,
                        vector=point.vector,
                        payload=payload,
                    )
                ],
            )

            return True

        except Exception as e:
            logger.error(f"Failed to delete usage tracking: {e}")
            return False

    async def cleanup_orphaned_usage_tracking(self) -> int:
        """
        Clean up usage tracking (no-op for Qdrant, data is in payload).

        Returns:
            0 (no orphaned records in Qdrant)
        """
        # In Qdrant, usage tracking is part of the point payload,
        # so there are no orphaned records
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
        if not self.client:
            raise StorageError("Store not initialized")

        try:
            # Build filter conditions
            conditions = []

            if context_level:
                conditions.append(
                    FieldCondition(
                        key="context_level",
                        match=MatchValue(
                            value=context_level.value if hasattr(context_level, "value") else context_level
                        )
                    )
                )

            # For Qdrant, we need to scroll and filter in Python for datetime comparisons
            # since Qdrant doesn't support datetime comparisons directly

            scroll_filter = Filter(must=conditions) if conditions else None
            offset = None
            results_list = []

            while True:
                results, offset = self.client.scroll(
                    collection_name=self.collection_name,
                    scroll_filter=scroll_filter,
                    limit=100,
                    offset=offset,
                    with_payload=True,
                    with_vectors=False,
                )

                if not results:
                    break

                for point in results:
                    payload = point.payload

                    # Check age if older_than is specified
                    if older_than:
                        last_used = payload.get("usage_last_used") or payload.get("created_at")
                        if last_used:
                            if isinstance(last_used, str):
                                last_used = datetime.fromisoformat(last_used)
                                # Ensure timezone-aware
                                if last_used.tzinfo is None:
                                    last_used = last_used.replace(tzinfo=UTC)

                            if last_used >= older_than:
                                continue  # Not old enough

                    results_list.append({
                        "id": point.id,
                        "created_at": payload.get("created_at"),
                        "last_used": payload.get("usage_last_used"),
                    })

                if offset is None:
                    break

            return results_list

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
        if not self.client:
            raise StorageError("Store not initialized")

        try:
            offset = None
            results_list = []

            while True:
                results, offset = self.client.scroll(
                    collection_name=self.collection_name,
                    limit=100,
                    offset=offset,
                    with_payload=True,
                    with_vectors=False,
                )

                if not results:
                    break

                for point in results:
                    payload = point.payload

                    # Check context level exclusions
                    if exclude_context_levels:
                        context_level = payload.get("context_level")
                        if context_level in [
                            cl.value if hasattr(cl, "value") else cl
                            for cl in exclude_context_levels
                        ]:
                            continue

                    # Check usage
                    use_count = payload.get("usage_count", 0)
                    if use_count > 0:
                        continue  # Has been used

                    # Check age
                    last_used = payload.get("usage_last_used") or payload.get("created_at")
                    if last_used:
                        if isinstance(last_used, str):
                            last_used = datetime.fromisoformat(last_used)
                            # Ensure timezone-aware
                            if last_used.tzinfo is None:
                                last_used = last_used.replace(tzinfo=UTC)

                        if last_used >= cutoff_time:
                            continue  # Not old enough

                    results_list.append({
                        "id": point.id,
                        "created_at": payload.get("created_at"),
                        "context_level": payload.get("context_level"),
                        "last_used": payload.get("usage_last_used"),
                        "use_count": use_count,
                    })

                if offset is None:
                    break

            return results_list

        except Exception as e:
            logger.error(f"Failed to find unused memories: {e}")
            return []

    async def get_all_memories(self) -> List[Dict[str, Any]]:
        """
        Get all memories (for fallback queries).

        Returns:
            List of all memory dictionaries
        """
        if not self.client:
            raise StorageError("Store not initialized")

        try:
            offset = None
            memories = []

            while True:
                results, offset = self.client.scroll(
                    collection_name=self.collection_name,
                    limit=100,
                    offset=offset,
                    with_payload=True,
                    with_vectors=False,
                )

                if not results:
                    break

                for point in results:
                    memory_dict = dict(point.payload)
                    memory_dict["id"] = point.id
                    memories.append(memory_dict)

                if offset is None:
                    break

            return memories

        except Exception as e:
            logger.error(f"Failed to get all memories: {e}")
            return []

    async def migrate_memory_scope(self, memory_id: str, new_project_name: Optional[str]) -> bool:
        """
        Migrate a memory to a different scope (change project_name).

        Args:
            memory_id: ID of the memory to migrate
            new_project_name: New project name (None for global scope)

        Returns:
            True if migrated successfully

        Raises:
            StorageError: If migration fails
        """
        if not self.client:
            raise StorageError("Store not initialized")

        try:
            # Get the memory
            points = self.client.retrieve(
                collection_name=self.collection_name,
                ids=[memory_id],
                with_payload=True,
                with_vectors=True,
            )

            if not points:
                raise StorageError(f"Memory not found: {memory_id}")

            point = points[0]
            payload = dict(point.payload)

            # Update project_name
            payload["project_name"] = new_project_name

            # Upsert with updated payload
            self.client.upsert(
                collection_name=self.collection_name,
                points=[
                    PointStruct(
                        id=point.id,
                        vector=point.vector,
                        payload=payload,
                    )
                ],
            )

            scope = new_project_name if new_project_name else "global"
            logger.info(f"Migrated memory {memory_id} to scope: {scope}")
            return True

        except StorageError:
            raise
        except Exception as e:
            logger.error(f"Error migrating memory {memory_id}: {e}")
            raise StorageError(f"Failed to migrate memory scope: {e}")

    async def bulk_update_context_level(
        self,
        new_context_level: str,
        project_name: Optional[str] = None,
        current_context_level: Optional[str] = None,
        category: Optional[str] = None,
    ) -> int:
        """
        Bulk update context level for memories matching criteria.

        Args:
            new_context_level: New context level to set
            project_name: Filter by project name (optional)
            current_context_level: Filter by current context level (optional)
            category: Filter by category (optional)

        Returns:
            Number of memories updated

        Raises:
            StorageError: If update fails
        """
        if not self.client:
            raise StorageError("Store not initialized")

        try:
            # Build filter
            conditions = []
            if project_name is not None:
                conditions.append(
                    FieldCondition(
                        key="project_name",
                        match=MatchValue(value=project_name),
                    )
                )
            if current_context_level is not None:
                conditions.append(
                    FieldCondition(
                        key="context_level",
                        match=MatchValue(value=current_context_level),
                    )
                )
            if category is not None:
                conditions.append(
                    FieldCondition(
                        key="category",
                        match=MatchValue(value=category),
                    )
                )

            filter_obj = Filter(must=conditions) if conditions else None

            # Get all matching memories and update them
            offset = None
            count = 0

            while True:
                results, offset = self.client.scroll(
                    collection_name=self.collection_name,
                    scroll_filter=filter_obj,
                    limit=100,
                    offset=offset,
                    with_payload=True,
                    with_vectors=True,
                )

                if not results:
                    break

                # Update context_level in payloads
                points_to_update = []
                for point in results:
                    payload = dict(point.payload)
                    payload["context_level"] = new_context_level
                    points_to_update.append(
                        PointStruct(
                            id=point.id,
                            vector=point.vector,
                            payload=payload,
                        )
                    )
                    count += 1

                # Upsert updated points
                self.client.upsert(
                    collection_name=self.collection_name,
                    points=points_to_update,
                )

                if offset is None:
                    break

            logger.info(f"Updated context level for {count} memories to {new_context_level}")
            return count

        except Exception as e:
            logger.error(f"Error bulk updating context level: {e}")
            raise StorageError(f"Failed to bulk update context level: {e}")

    async def find_duplicate_memories(
        self,
        project_name: Optional[str] = None,
        similarity_threshold: float = 0.95,
    ) -> List[List[str]]:
        """
        Find potential duplicate memories using embedding similarity.

        Args:
            project_name: Filter by project name (optional)
            similarity_threshold: Similarity threshold (0.0-1.0)

        Returns:
            List of memory ID groups (each group is potential duplicates)

        Raises:
            StorageError: If search fails
        """
        if not self.client:
            raise StorageError("Store not initialized")

        try:
            # Get all memories matching criteria
            filter_obj = None
            if project_name:
                filter_obj = Filter(
                    must=[
                        FieldCondition(
                            key="project_name",
                            match=MatchValue(value=project_name),
                        )
                    ]
                )

            offset = None
            memories = []

            while True:
                results, offset = self.client.scroll(
                    collection_name=self.collection_name,
                    scroll_filter=filter_obj,
                    limit=100,
                    offset=offset,
                    with_payload=True,
                    with_vectors=True,
                )

                if not results:
                    break

                for point in results:
                    memories.append((point.id, point.vector, point.payload.get("content", "")))

                if offset is None:
                    break

            # Find duplicates using embedding similarity
            duplicates = []
            seen = set()

            for i, (id1, vec1, content1) in enumerate(memories):
                if id1 in seen:
                    continue

                group = [id1]
                for j, (id2, vec2, content2) in enumerate(memories[i+1:], start=i+1):
                    if id2 in seen:
                        continue

                    # Calculate cosine similarity
                    import numpy as np
                    similarity = np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2))

                    if similarity >= similarity_threshold:
                        group.append(id2)
                        seen.add(id2)

                if len(group) > 1:
                    duplicates.append(group)
                    seen.add(id1)

            logger.info(f"Found {len(duplicates)} potential duplicate groups")
            return duplicates

        except Exception as e:
            logger.error(f"Error finding duplicate memories: {e}")
            raise StorageError(f"Failed to find duplicates: {e}")

    async def merge_memories(
        self,
        memory_ids: List[str],
        keep_id: Optional[str] = None,
    ) -> str:
        """
        Merge multiple memories into one.

        Args:
            memory_ids: List of memory IDs to merge
            keep_id: ID of memory to keep (uses first if not specified)

        Returns:
            ID of the merged memory

        Raises:
            StorageError: If merge fails
        """
        if not self.client:
            raise StorageError("Store not initialized")

        if len(memory_ids) < 2:
            raise StorageError("Need at least 2 memories to merge")

        try:
            # Determine which memory to keep
            target_id = keep_id if keep_id and keep_id in memory_ids else memory_ids[0]
            other_ids = [mid for mid in memory_ids if mid != target_id]

            # Get all memories
            points = self.client.retrieve(
                collection_name=self.collection_name,
                ids=memory_ids,
                with_payload=True,
                with_vectors=True,
            )

            if len(points) != len(memory_ids):
                raise StorageError("Some memories not found")

            # Find target memory
            target_point = next((p for p in points if p.id == target_id), None)
            if not target_point:
                raise StorageError(f"Target memory not found: {target_id}")

            # Combine content
            target_payload = dict(target_point.payload)
            combined_content = target_payload.get("content", "")

            for point in points:
                if point.id != target_id:
                    content = point.payload.get("content", "")
                    if content and content not in combined_content:
                        combined_content += f"\n\n---\n\n{content}"

            # Update target memory with combined content
            target_payload["content"] = combined_content
            target_payload["updated_at"] = datetime.now(UTC).isoformat()

            self.client.upsert(
                collection_name=self.collection_name,
                points=[
                    PointStruct(
                        id=target_point.id,
                        vector=target_point.vector,
                        payload=target_payload,
                    )
                ],
            )

            # Delete other memories
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=PointIdsList(points=other_ids),
            )

            logger.info(f"Merged {len(memory_ids)} memories into {target_id}")
            return target_id

        except StorageError:
            raise
        except Exception as e:
            logger.error(f"Error merging memories: {e}")
            raise StorageError(f"Failed to merge memories: {e}")
