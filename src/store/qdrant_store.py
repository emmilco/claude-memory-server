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
from src.config import ServerConfig, DEFAULT_EMBEDDING_DIM

logger = logging.getLogger(__name__)


class QdrantMemoryStore(MemoryStore):
    """Qdrant implementation of the MemoryStore interface."""

    def __init__(self, config: Optional[ServerConfig] = None, use_pool: bool = True):
        """
        Initialize Qdrant memory store.

        Args:
            config: Server configuration. If None, uses global config.
            use_pool: If True, use connection pool. If False, use single client (legacy mode).
        """
        if config is None:
            from src.config import get_config
            config = get_config()

        self.config = config
        self.use_pool = use_pool
        self.setup = QdrantSetup(config, use_pool=use_pool)
        self.client: Optional[QdrantClient] = None
        self.collection_name = config.qdrant_collection_name

    async def initialize(self) -> None:
        """Initialize the Qdrant connection/pool and collection."""
        try:
            if self.use_pool:
                # Create connection pool - disable health checks during initialization
                # to avoid chicken-and-egg problem (collection doesn't exist yet)
                await self.setup.create_pool(
                    enable_health_checks=False,  # Disable during init, will work after collection exists
                    enable_monitoring=False,  # Can be enabled for production
                )
                # Acquire a temporary client to ensure collection exists
                client = await self.setup.pool.acquire()
                try:
                    # Use temporary client for setup
                    old_client = self.setup.client
                    self.setup.client = client
                    self.setup.ensure_collection_exists()
                    self.setup.client = old_client
                finally:
                    await self.setup.pool.release(client)

                # Now enable health checks since collection exists
                if self.setup.pool:
                    self.setup.pool.enable_health_checks = True
                    from src.store.connection_health_checker import ConnectionHealthChecker
                    self.setup.pool._health_checker = ConnectionHealthChecker()

                logger.info("Qdrant store initialized with connection pool")
            else:
                # Legacy: single client
                self.client = self.setup.connect()
                self.setup.ensure_collection_exists()
                logger.info("Qdrant store initialized with single client (legacy mode)")
        except Exception as e:
            raise StorageError(f"Failed to initialize Qdrant store: {e}")

    async def _get_client(self) -> QdrantClient:
        """Get a Qdrant client (from pool or single client).

        Returns:
            QdrantClient: Client for Qdrant operations

        Raises:
            StorageError: If not initialized
        """
        if self.use_pool:
            if self.setup.pool is None:
                await self.initialize()
            return await self.setup.pool.acquire()
        else:
            if self.client is None:
                await self.initialize()
            return self.client

    async def _release_client(self, client: QdrantClient) -> None:
        """Release a Qdrant client back to pool (if using pool).

        Args:
            client: Client to release
        """
        if self.use_pool and self.setup.pool:
            await self.setup.pool.release(client)

    async def store(
        self,
        content: str,
        embedding: List[float],
        metadata: Dict[str, Any],
    ) -> str:
        """Store a single memory with its embedding and metadata."""
        client = None
        try:
            client = await self._get_client()
            # Build payload using helper method
            memory_id, payload = self._build_payload(content, embedding, metadata)

            # Create point
            point = PointStruct(
                id=memory_id,
                vector=embedding,
                payload=payload,
            )

            # Upsert to Qdrant
            client.upsert(
                collection_name=self.collection_name,
                points=[point],
            )

            logger.debug(f"Stored memory: {memory_id}")
            return memory_id

        except ValueError as e:
            # Invalid payload structure
            logger.error(f"Invalid payload for storage: {e}", exc_info=True)
            raise ValidationError(f"Invalid memory payload: {e}")
        except ConnectionError as e:
            # Connection issues
            logger.error(f"Connection error during store: {e}", exc_info=True)
            raise StorageError(f"Failed to connect to Qdrant: {e}")
        except Exception as e:
            # Generic fallback
            logger.error(f"Unexpected error storing memory: {e}", exc_info=True)
            raise StorageError(f"Failed to store memory: {e}")
        finally:
            if client is not None:
                await self._release_client(client)

    async def retrieve(
        self,
        query_embedding: List[float],
        filters: Optional[SearchFilters] = None,
        limit: int = 5,
    ) -> List[Tuple[MemoryUnit, float]]:
        """Retrieve memories similar to the query embedding."""
        client = None
        try:
            client = await self._get_client()
            # Cap limit to prevent memory/performance issues from unbounded queries
            safe_limit = min(limit, 100)
            if limit != safe_limit:
                logger.debug(f"Limiting search result count from {limit} to {safe_limit}")

            # Build filter conditions
            filter_conditions = self._build_filter(filters) if filters else None

            # Search using new query API
            search_result = client.query_points(
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
                except (ValueError, KeyError) as e:
                    logger.warning(f"Failed to parse search result payload: {e}")
                    continue

            logger.debug(f"Retrieved {len(results)} memories")
            return results

        except ConnectionError as e:
            logger.error(f"Connection error during retrieval: {e}", exc_info=True)
            raise RetrievalError(f"Failed to connect to Qdrant: {e}")
        except OSError as e:
            # OSError covers socket errors, connection refused, etc.
            logger.error(f"Network error during retrieval: {e}", exc_info=True)
            raise RetrievalError(f"Qdrant connection error: {e}")
        except ValueError as e:
            logger.error(f"Invalid filter or query: {e}", exc_info=True)
            raise RetrievalError(f"Invalid search parameters: {e}")
        except Exception as e:
            # Check if it's a connection-related error by string matching
            error_str = str(e).lower()
            if any(keyword in error_str for keyword in ['connection', 'refused', 'timeout', 'unreachable', 'qdrant']):
                logger.error(f"Connection-related error during retrieval: {e}", exc_info=True)
                raise RetrievalError(f"Failed to connect to Qdrant: {e}")
            logger.error(f"Unexpected error during retrieval: {e}", exc_info=True)
            raise RetrievalError(f"Failed to retrieve memories from Qdrant: {e}")
        finally:
            if client is not None:
                await self._release_client(client)

    async def delete(self, memory_id: str) -> bool:
        """Delete a memory by its ID."""
        client = None
        try:
            client = await self._get_client()
            result = client.delete(
                collection_name=self.collection_name,
                points_selector=[memory_id],
            )

            deleted = result.status == "completed"
            if deleted:
                logger.debug(f"Deleted memory: {memory_id}")
            return deleted

        except Exception as e:
            raise StorageError(f"Failed to delete memory: {e}")
        finally:
            if client is not None:
                await self._release_client(client)

    async def delete_code_units_by_project(self, project_name: str) -> int:
        """
        Delete all CODE category memories for a specific project.

        Args:
            project_name: Name of the project whose code units should be deleted.

        Returns:
            Number of units deleted.

        Raises:
            StorageError: If deletion fails.
        """
        client = None
        try:
            client = await self._get_client()
            # First, count how many units will be deleted by scrolling
            filter_conditions = Filter(
                must=[
                    FieldCondition(
                        key="category",
                        match=MatchValue(value="code")
                    ),
                    FieldCondition(
                        key="scope",
                        match=MatchValue(value="project")
                    ),
                    FieldCondition(
                        key="project_name",
                        match=MatchValue(value=project_name)
                    ),
                ]
            )

            # Count units before deletion
            offset = None
            count = 0

            while True:
                results, offset = client.scroll(
                    collection_name=self.collection_name,
                    scroll_filter=filter_conditions,
                    limit=100,
                    offset=offset,
                    with_payload=False,
                    with_vectors=False,
                )

                count += len(results)

                if offset is None:
                    break

            # Delete using filter
            if count > 0:
                client.delete(
                    collection_name=self.collection_name,
                    points_selector=filter_conditions,
                )
                logger.info(f"Deleted {count} code units for project: {project_name}")

            return count

        except Exception as e:
            logger.error(f"Failed to delete code units for project {project_name}: {e}", exc_info=True)
            raise StorageError(f"Failed to delete code units: {e}")
        finally:
            if client is not None:
                await self._release_client(client)

    async def batch_store(
        self,
        items: List[Tuple[str, List[float], Dict[str, Any]]],
    ) -> List[str]:
        """Store multiple memories in a batch operation."""
        if not items:
            return []

        client = None
        try:
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

            # Get client from pool
            client = await self._get_client()

            # Batch upsert
            client.upsert(
                collection_name=self.collection_name,
                points=points,
            )

            logger.debug(f"Batch stored {len(memory_ids)} memories")
            return memory_ids

        except ValueError as e:
            logger.error(f"Invalid payload in batch: {e}", exc_info=True)
            raise ValidationError(f"Invalid memory payload in batch: {e}")
        except ConnectionError as e:
            logger.error(f"Connection error during batch store: {e}", exc_info=True)
            raise StorageError(f"Failed to connect to Qdrant: {e}")
        except Exception as e:
            logger.error(f"Unexpected error in batch store: {e}", exc_info=True)
            raise StorageError(f"Failed to batch store memories: {e}")
        finally:
            if client is not None:
                await self._release_client(client)

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
        client = None
        try:
            client = await self._get_client()
            result = client.retrieve(
                collection_name=self.collection_name,
                ids=[memory_id],
                with_payload=True,
                with_vectors=False,
            )

            if not result:
                return None

            return self._payload_to_memory_unit(result[0].payload)

        except Exception as e:
            logger.error(f"Failed to get memory by ID: {e}", exc_info=True)
            return None
        finally:
            if client is not None:
                await self._release_client(client)

    async def count(self, filters: Optional[SearchFilters] = None) -> int:
        """Count the number of memories, optionally with filters."""
        client = None
        try:
            client = await self._get_client()
            if not filters:
                # No filters - return total collection count
                collection_info = client.get_collection(self.collection_name)
                return collection_info.points_count

            # Count with filters by scrolling through all matching points
            filter_conditions = self._build_filter(filters)
            total = 0
            offset = None

            while True:
                points, offset = client.scroll(
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
            logger.error(f"Failed to count memories: {e}", exc_info=True)
            return 0
        finally:
            if client is not None:
                await self._release_client(client)

    async def update(
        self,
        memory_id: str,
        updates: Dict[str, Any],
        new_embedding: Optional[List[float]] = None
    ) -> bool:
        """
        Update a memory's metadata and optionally its embedding.

        Args:
            memory_id: ID of memory to update
            updates: Dictionary of fields to update
            new_embedding: Optional new embedding vector (for content updates)

        Returns:
            bool: True if updated, False if not found
        """

        client = None
        try:
            client = await self._get_client()
            # Get existing memory
            existing = await self.get_by_id(memory_id)
            if not existing:
                return False

            # Update timestamp
            updates["updated_at"] = datetime.now(UTC).isoformat()

            if new_embedding is not None:
                # Use upsert to update both vector and payload
                from qdrant_client.models import PointStruct

                # Merge existing payload with updates
                existing_dict = existing.model_dump()

                # IMPORTANT: Merge metadata dicts to preserve existing keys
                merged_metadata = existing.metadata or {}
                if "metadata" in updates:
                    new_metadata = updates["metadata"] or {}
                    merged_metadata = {**merged_metadata, **new_metadata}

                # Build base payload without metadata (we'll flatten it separately)
                base_payload = {
                    "id": memory_id,
                    "content": updates.get("content", existing.content),
                    "category": updates.get("category", existing.category.value if hasattr(existing.category, 'value') else existing.category),
                    "context_level": updates.get("context_level", existing.context_level.value if hasattr(existing.context_level, 'value') else existing.context_level),
                    "scope": updates.get("scope", existing.scope.value if hasattr(existing.scope, 'value') else existing.scope),
                    "project_name": updates.get("project_name", existing.project_name),
                    "importance": updates.get("importance", existing.importance),
                    "tags": updates.get("tags", existing.tags),
                    "created_at": existing.created_at.isoformat(),
                    "updated_at": updates["updated_at"],
                    "last_accessed": existing.last_accessed.isoformat() if existing.last_accessed else None,
                    "lifecycle_state": updates.get("lifecycle_state", existing.lifecycle_state.value if hasattr(existing.lifecycle_state, 'value') else existing.lifecycle_state),
                }

                # Flatten metadata into payload (matches _build_payload behavior)
                merged_payload = {**base_payload, **merged_metadata}

                # Handle provenance
                if hasattr(existing, 'provenance') and existing.provenance:
                    prov = existing.provenance
                    merged_payload["provenance"] = {
                        "source": prov.source.value if hasattr(prov.source, 'value') else prov.source,
                        "created_by": prov.created_by,
                        "confidence": prov.confidence,
                        "verified": prov.verified,
                    }

                client.upsert(
                    collection_name=self.collection_name,
                    points=[PointStruct(
                        id=memory_id,
                        vector=new_embedding,
                        payload=merged_payload
                    )]
                )
            else:
                # Only update payload (no vector change)
                # IMPORTANT: Merge metadata if it's being updated to preserve existing keys
                payload_updates = updates.copy()
                if "metadata" in updates:
                    # Merge new metadata with existing metadata
                    existing_metadata = existing.metadata or {}
                    new_metadata = updates["metadata"] or {}
                    merged_metadata = {**existing_metadata, **new_metadata}

                    # Remove the nested "metadata" key and flatten it into payload
                    payload_updates.pop("metadata", None)
                    payload_updates.update(merged_metadata)

                client.set_payload(
                    collection_name=self.collection_name,
                    payload=payload_updates,
                    points=[memory_id],
                )

            logger.debug(f"Updated memory: {memory_id}")
            return True

        except Exception as e:
            raise StorageError(f"Failed to update memory: {e}")

        finally:
            if client is not None:
                await self._release_client(client)

    async def health_check(self) -> bool:
        """Check if the storage backend is healthy and accessible."""
        return self.setup.health_check()

    async def list_memories(
        self,
        filters: Optional[Dict[str, Any]] = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
        limit: int = 20,
        offset: int = 0
    ) -> Tuple[List[MemoryUnit], int]:
        """
        List memories with filtering, sorting, and pagination.

        Args:
            filters: Optional filters to apply.
            sort_by: Field to sort by (created_at, updated_at, importance).
            sort_order: Sort order (asc, desc).
            limit: Maximum number of results to return.
            offset: Number of results to skip for pagination.

        Returns:
            Tuple of (list of memories, total count before pagination).

        Raises:
            StorageError: If listing operation fails.
        """

        filters = filters or {}

        client = None
        try:
            client = await self._get_client()
            # Build Qdrant filter conditions
            must_conditions = []

            if "category" in filters:
                category = filters["category"]
                must_conditions.append(
                    FieldCondition(
                        key="category",
                        match=MatchValue(value=category.value if hasattr(category, 'value') else category)
                    )
                )

            if "context_level" in filters:
                context_level = filters["context_level"]
                must_conditions.append(
                    FieldCondition(
                        key="context_level",
                        match=MatchValue(value=context_level.value if hasattr(context_level, 'value') else context_level)
                    )
                )

            if "scope" in filters:
                scope = filters["scope"]
                must_conditions.append(
                    FieldCondition(
                        key="scope",
                        match=MatchValue(value=scope.value if hasattr(scope, 'value') else scope)
                    )
                )

            if "project_name" in filters:
                must_conditions.append(
                    FieldCondition(
                        key="project_name",
                        match=MatchValue(value=filters["project_name"])
                    )
                )

            if "tags" in filters:
                # Match ANY of the provided tags
                from qdrant_client.models import MatchAny
                must_conditions.append(
                    FieldCondition(
                        key="tags",
                        match=MatchAny(any=filters["tags"])
                    )
                )

            # Importance range filter
            min_importance = filters.get("min_importance", 0.0)
            max_importance = filters.get("max_importance", 1.0)
            if min_importance > 0.0 or max_importance < 1.0:
                must_conditions.append(
                    FieldCondition(
                        key="importance",
                        range=Range(
                            gte=min_importance,
                            lte=max_importance
                        )
                    )
                )

            # Build filter object
            qdrant_filter = Filter(must=must_conditions) if must_conditions else None

            # Scroll through all matching results
            all_memories = []
            scroll_offset = None

            while True:
                result = client.scroll(
                    collection_name=self.collection_name,
                    scroll_filter=qdrant_filter,
                    limit=100,  # Fetch in batches
                    offset=scroll_offset,
                    with_payload=True,
                    with_vectors=False
                )

                points, next_offset = result

                for point in points:
                    try:
                        memory = self._payload_to_memory_unit(dict(point.payload))
                        all_memories.append(memory)
                    except Exception as e:
                        # Skip memories that fail validation (e.g., content > 50KB)
                        logger.warning(f"Skipping invalid memory {point.id}: {e}")
                        continue

                if next_offset is None:
                    break

                scroll_offset = next_offset

            # Apply date filtering (Qdrant doesn't handle datetime ranges well)
            if "date_from" in filters:
                all_memories = [
                    m for m in all_memories
                    if m.created_at >= filters["date_from"]
                ]

            if "date_to" in filters:
                all_memories = [
                    m for m in all_memories
                    if m.created_at <= filters["date_to"]
                ]

            # Sort memories
            reverse = (sort_order == "desc")
            all_memories.sort(
                key=lambda m: getattr(m, sort_by),
                reverse=reverse
            )

            # Get total count
            total_count = len(all_memories)

            # Apply pagination
            paginated = all_memories[offset:offset + limit]

            logger.debug(f"Listed {len(paginated)} memories (total {total_count})")
            return paginated, total_count

        except Exception as e:
            logger.error(f"Error listing memories: {e}", exc_info=True)
            raise StorageError(f"Failed to list memories: {e}")

        finally:
            if client is not None:
                await self._release_client(client)

    async def get_indexed_files(
        self,
        project_name: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """
        Get list of indexed files with metadata.

        Args:
            project_name: Optional project name to filter by
            limit: Maximum number of files to return (default 50, max 500)
            offset: Number of files to skip for pagination

        Returns:
            Dictionary with files list, total count, and pagination info
        """

        # Validate and cap limit
        limit = min(max(1, limit), 500)
        offset = max(0, offset)

        client = None
        try:
            client = await self._get_client()
            # Build filter for code category
            must_conditions = [
                FieldCondition(
                    key="category",
                    match=MatchValue(value="code")  # Fixed: code is stored with category="code", not "context"
                )
            ]

            if project_name:
                must_conditions.append(
                    FieldCondition(
                        key="project_name",
                        match=MatchValue(value=project_name)
                    )
                )

            qdrant_filter = Filter(must=must_conditions)

            # Scroll through all code memories to group by file
            file_data = {}  # file_path -> {language, last_indexed, unit_count}
            scroll_offset = None

            while True:
                result = client.scroll(
                    collection_name=self.collection_name,
                    scroll_filter=qdrant_filter,
                    limit=100,
                    offset=scroll_offset,
                    with_payload=True,
                    with_vectors=False
                )

                points, next_offset = result

                for point in points:
                    payload = dict(point.payload)
                    file_path = payload.get("file_path")

                    if file_path:
                        if file_path not in file_data:
                            file_data[file_path] = {
                                "file_path": file_path,
                                "language": payload.get("language", "unknown"),
                                "last_indexed": payload.get("updated_at", payload.get("created_at")),
                                "unit_count": 0
                            }

                        file_data[file_path]["unit_count"] += 1

                        # Update to most recent timestamp
                        current_time = payload.get("updated_at", payload.get("created_at"))
                        if current_time and current_time > file_data[file_path]["last_indexed"]:
                            file_data[file_path]["last_indexed"] = current_time

                if next_offset is None:
                    break

                scroll_offset = next_offset

            # Convert to list and sort by last_indexed (most recent first)
            files_list = list(file_data.values())
            files_list.sort(key=lambda x: x["last_indexed"], reverse=True)

            total = len(files_list)

            # Apply pagination
            paginated_files = files_list[offset:offset + limit]

            return {
                "files": paginated_files,
                "total": total,
                "limit": limit,
                "offset": offset,
            }

        except Exception as e:
            logger.error(f"Error getting indexed files: {e}", exc_info=True)
            raise StorageError(f"Failed to get indexed files: {e}")

        finally:
            if client is not None:
                await self._release_client(client)

    async def list_indexed_units(
        self,
        project_name: Optional[str] = None,
        language: Optional[str] = None,
        file_pattern: Optional[str] = None,
        unit_type: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """
        List indexed code units (functions, classes, etc.) with filtering.

        Args:
            project_name: Optional project name to filter by
            language: Optional language to filter by
            file_pattern: Optional glob pattern for file paths
            unit_type: Optional unit type to filter by
            limit: Maximum number of units to return (default 50, max 500)
            offset: Number of units to skip for pagination

        Returns:
            Dictionary with units list, total count, and pagination info
        """

        # Validate and cap limit
        limit = min(max(1, limit), 500)
        offset = max(0, offset)

        client = None
        try:
            client = await self._get_client()
            # Build filter conditions
            must_conditions = [
                FieldCondition(
                    key="category",
                    match=MatchValue(value="code")  # Fixed: code is stored with category="code", not "context"
                )
            ]

            if project_name:
                must_conditions.append(
                    FieldCondition(
                        key="project_name",
                        match=MatchValue(value=project_name)
                    )
                )

            if language:
                must_conditions.append(
                    FieldCondition(
                        key="language",
                        match=MatchValue(value=language)
                    )
                )

            if unit_type:
                must_conditions.append(
                    FieldCondition(
                        key="unit_type",
                        match=MatchValue(value=unit_type)
                    )
                )

            qdrant_filter = Filter(must=must_conditions)

            # Scroll through all matching code units
            all_units = []
            scroll_offset = None

            while True:
                result = client.scroll(
                    collection_name=self.collection_name,
                    scroll_filter=qdrant_filter,
                    limit=100,
                    offset=scroll_offset,
                    with_payload=True,
                    with_vectors=False
                )

                points, next_offset = result

                for point in points:
                    payload = dict(point.payload)

                    # Apply file pattern filter if specified (glob-style)
                    if file_pattern:
                        file_path = payload.get("file_path", "")
                        # Convert glob pattern to simple matching
                        # For now, support basic wildcards
                        import fnmatch
                        if not fnmatch.fnmatch(file_path, file_pattern):
                            continue

                    unit = {
                        "id": payload.get("id", str(point.id)),
                        "name": payload.get("unit_name", ""),
                        "unit_type": payload.get("unit_type", ""),
                        "file_path": payload.get("file_path", ""),
                        "language": payload.get("language", ""),
                        "start_line": payload.get("start_line", 0),
                        "end_line": payload.get("end_line", 0),
                        "signature": payload.get("signature", ""),
                        "last_indexed": payload.get("updated_at", payload.get("created_at", "")),
                    }
                    all_units.append(unit)

                if next_offset is None:
                    break

                scroll_offset = next_offset

            # Sort by last_indexed (most recent first)
            all_units.sort(key=lambda x: x["last_indexed"], reverse=True)

            total = len(all_units)

            # Apply pagination
            paginated_units = all_units[offset:offset + limit]

            return {
                "units": paginated_units,
                "total": total,
                "limit": limit,
                "offset": offset,
            }

        except Exception as e:
            logger.error(f"Error listing indexed units: {e}", exc_info=True)
            raise StorageError(f"Failed to list indexed units: {e}")

        finally:
            if client is not None:
                await self._release_client(client)

    def get_pool_stats(self) -> Optional[Dict[str, Any]]:
        """Get connection pool statistics.

        Returns:
            Pool statistics dictionary or None if not using pool
        """
        if self.use_pool and self.setup.pool:
            pool_stats = self.setup.pool.stats()
            return {
                "pool_size": pool_stats.pool_size,
                "active_connections": pool_stats.active_connections,
                "idle_connections": pool_stats.idle_connections,
                "total_acquires": pool_stats.total_acquires,
                "total_releases": pool_stats.total_releases,
                "total_timeouts": pool_stats.total_timeouts,
                "total_health_failures": pool_stats.total_health_failures,
                "connections_created": pool_stats.connections_created,
                "connections_recycled": pool_stats.connections_recycled,
                "avg_acquire_time_ms": pool_stats.avg_acquire_time_ms,
                "p95_acquire_time_ms": pool_stats.p95_acquire_time_ms,
                "max_acquire_time_ms": pool_stats.max_acquire_time_ms,
            }
        return None

    async def close(self) -> None:
        """Close connections and clean up resources."""
        if self.use_pool and self.setup.pool:
            await self.setup.pool.close()
            logger.info("Qdrant connection pool closed")
        elif self.client:
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

        # Handle advanced filters if present
        if filters.advanced_filters:
            adv = filters.advanced_filters

            # Date range filtering
            if adv.created_after:
                conditions.append(
                    FieldCondition(
                        key="created_at",
                        range=Range(gte=adv.created_after.isoformat())
                    )
                )
            if adv.created_before:
                conditions.append(
                    FieldCondition(
                        key="created_at",
                        range=Range(lte=adv.created_before.isoformat())
                    )
                )
            if adv.updated_after:
                conditions.append(
                    FieldCondition(
                        key="updated_at",
                        range=Range(gte=adv.updated_after.isoformat())
                    )
                )
            if adv.updated_before:
                conditions.append(
                    FieldCondition(
                        key="updated_at",
                        range=Range(lte=adv.updated_before.isoformat())
                    )
                )
            if adv.accessed_after:
                conditions.append(
                    FieldCondition(
                        key="last_accessed",
                        range=Range(gte=adv.accessed_after.isoformat())
                    )
                )
            if adv.accessed_before:
                conditions.append(
                    FieldCondition(
                        key="last_accessed",
                        range=Range(lte=adv.accessed_before.isoformat())
                    )
                )

            # Tag logic - ANY (OR)
            if adv.tags_any:
                tag_any_conditions = []
                for tag in adv.tags_any:
                    tag_any_conditions.append(
                        FieldCondition(key="tags", match=MatchValue(value=tag))
                    )
                if tag_any_conditions:
                    conditions.append(Filter(should=tag_any_conditions))

            # Tag logic - ALL (AND)
            if adv.tags_all:
                for tag in adv.tags_all:
                    conditions.append(
                        FieldCondition(key="tags", match=MatchValue(value=tag))
                    )

            # Tag logic - NONE (NOT)
            if adv.tags_none:
                tag_none_conditions = []
                for tag in adv.tags_none:
                    tag_none_conditions.append(
                        FieldCondition(key="tags", match=MatchValue(value=tag))
                    )
                if tag_none_conditions:
                    conditions.append(Filter(must_not=tag_none_conditions))

            # Lifecycle filtering
            if adv.lifecycle_states:
                lifecycle_conditions = []
                for state in adv.lifecycle_states:
                    lifecycle_conditions.append(
                        FieldCondition(
                            key="lifecycle_state",
                            match=MatchValue(value=state.value if hasattr(state, 'value') else state)
                        )
                    )
                if lifecycle_conditions:
                    conditions.append(Filter(should=lifecycle_conditions))

            # Exclusions - categories
            if adv.exclude_categories:
                exclude_cat_conditions = []
                for cat in adv.exclude_categories:
                    exclude_cat_conditions.append(
                        FieldCondition(
                            key="category",
                            match=MatchValue(value=cat.value if hasattr(cat, 'value') else cat)
                        )
                    )
                if exclude_cat_conditions:
                    conditions.append(Filter(must_not=exclude_cat_conditions))

            # Exclusions - projects
            if adv.exclude_projects:
                exclude_proj_conditions = []
                for proj in adv.exclude_projects:
                    exclude_proj_conditions.append(
                        FieldCondition(key="project_name", match=MatchValue(value=proj))
                    )
                if exclude_proj_conditions:
                    conditions.append(Filter(must_not=exclude_proj_conditions))

            # Provenance filtering - min trust score
            if adv.min_trust_score is not None:
                conditions.append(
                    FieldCondition(
                        key="provenance.confidence",
                        range=Range(gte=adv.min_trust_score)
                    )
                )

            # Provenance filtering - source
            if adv.source:
                conditions.append(
                    FieldCondition(
                        key="provenance.source",
                        match=MatchValue(value=adv.source.value if hasattr(adv.source, 'value') else adv.source)
                    )
                )

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
        client = None
        try:
            client = await self._get_client()
            # Scroll through all points and collect unique project names
            projects = set()
            offset = None

            while True:
                results, offset = client.scroll(
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
            logger.error(f"Error getting all projects: {e}", exc_info=True)
            raise StorageError(f"Failed to get projects: {e}")

        finally:
            if client is not None:
                await self._release_client(client)

    async def get_project_stats(self, project_name: str) -> Dict[str, Any]:
        """
        Get statistics for a specific project.

        Args:
            project_name: Name of the project.

        Returns:
            Dictionary with project statistics (total_memories, categories, etc.).
        """
        client = None
        try:
            client = await self._get_client()
            # Get all memories for this project
            offset = None
            total_memories = 0
            categories = {}
            context_levels = {}
            latest_update = None
            file_paths = set()

            while True:
                results, offset = client.scroll(
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
            logger.error(f"Error getting project stats for {project_name}: {e}", exc_info=True)
            raise StorageError(f"Failed to get project stats: {e}")

        finally:
            if client is not None:
                await self._release_client(client)

    async def update_usage(self, usage_data: Dict[str, Any]) -> bool:
        """
        Update usage tracking for a single memory (stored in payload).

        Args:
            usage_data: Dictionary with memory_id, first_seen, last_used, use_count, last_search_score

        Returns:
            True if successful
        """
        client = None
        try:
            client = await self._get_client()
            memory_id = usage_data["memory_id"]

            # Get current point
            points = client.retrieve(
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
            client.upsert(
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
            logger.error(f"Failed to update usage tracking: {e}", exc_info=True)
            raise StorageError(f"Failed to update usage tracking: {e}")

        finally:
            if client is not None:
                await self._release_client(client)

    async def batch_update_usage(self, usage_data_list: List[Dict[str, Any]]) -> bool:
        """
        Batch update usage tracking for multiple memories.

        Args:
            usage_data_list: List of usage data dictionaries

        Returns:
            True if successful
        """
        client = None
        try:
            client = await self._get_client()
            # Retrieve all points at once
            memory_ids = [data["memory_id"] for data in usage_data_list]

            points = client.retrieve(
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
                client.upsert(
                    collection_name=self.collection_name,
                    points=updated_points,
                )
                logger.debug(f"Batch updated {len(updated_points)} usage records")

            return True

        except Exception as e:
            logger.error(f"Failed to batch update usage tracking: {e}", exc_info=True)
            raise StorageError(f"Failed to batch update usage tracking: {e}")

        finally:
            if client is not None:
                await self._release_client(client)

    async def get_usage_stats(self, memory_id: str) -> Optional[Dict[str, Any]]:
        """
        Get usage statistics for a memory.

        Args:
            memory_id: Memory ID

        Returns:
            Usage stats dictionary, or None if not found
        """
        client = None
        try:
            client = await self._get_client()
            points = client.retrieve(
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
            logger.error(f"Failed to get usage stats: {e}", exc_info=True)
            return None

        finally:
            if client is not None:
                await self._release_client(client)

    async def get_all_usage_stats(self) -> List[Dict[str, Any]]:
        """Get all usage statistics."""
        client = None
        try:
            client = await self._get_client()
            stats = []
            offset = None

            while True:
                results, offset = client.scroll(
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
            logger.error(f"Failed to get all usage stats: {e}", exc_info=True)
            return []

        finally:
            if client is not None:
                await self._release_client(client)

    async def delete_usage_tracking(self, memory_id: str) -> bool:
        """
        Delete usage tracking for a memory (remove from payload).

        Args:
            memory_id: Memory ID

        Returns:
            True if deleted
        """
        client = None
        try:
            client = await self._get_client()
            points = client.retrieve(
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
            client.upsert(
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
            logger.error(f"Failed to delete usage tracking: {e}", exc_info=True)
            return False

        finally:
            if client is not None:
                await self._release_client(client)

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
        client = None
        try:
            client = await self._get_client()
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
                results, offset = client.scroll(
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
            logger.error(f"Failed to find memories by criteria: {e}", exc_info=True)
            return []

        finally:
            if client is not None:
                await self._release_client(client)

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
        client = None
        try:
            client = await self._get_client()
            offset = None
            results_list = []

            while True:
                results, offset = client.scroll(
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
            logger.error(f"Failed to find unused memories: {e}", exc_info=True)
            return []

        finally:
            if client is not None:
                await self._release_client(client)

    async def get_all_memories(self) -> List[Dict[str, Any]]:
        """
        Get all memories (for fallback queries).

        Returns:
            List of all memory dictionaries
        """
        client = None
        try:
            client = await self._get_client()
            offset = None
            memories = []

            while True:
                results, offset = client.scroll(
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
            logger.error(f"Failed to get all memories: {e}", exc_info=True)
            return []

        finally:
            if client is not None:
                await self._release_client(client)

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
        client = None
        try:
            client = await self._get_client()
            # Get the memory
            points = client.retrieve(
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
            client.upsert(
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
            logger.error(f"Error migrating memory {memory_id}: {e}", exc_info=True)
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
        client = None
        try:
            client = await self._get_client()
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
                results, offset = client.scroll(
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
                client.upsert(
                    collection_name=self.collection_name,
                    points=points_to_update,
                )

                if offset is None:
                    break

            logger.info(f"Updated context level for {count} memories to {new_context_level}")
            return count

        except Exception as e:
            logger.error(f"Error bulk updating context level: {e}", exc_info=True)
            raise StorageError(f"Failed to bulk update context level: {e}")

        finally:
            if client is not None:
                await self._release_client(client)

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
        client = None
        try:
            client = await self._get_client()
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
                results, offset = client.scroll(
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
            logger.error(f"Error finding duplicate memories: {e}", exc_info=True)
            raise StorageError(f"Failed to find duplicates: {e}")

        finally:
            if client is not None:
                await self._release_client(client)

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
        if len(memory_ids) < 2:
            raise StorageError("Need at least 2 memories to merge")

        client = None
        try:
            client = await self._get_client()
            # Determine which memory to keep
            target_id = keep_id if keep_id and keep_id in memory_ids else memory_ids[0]
            other_ids = [mid for mid in memory_ids if mid != target_id]

            # Get all memories
            points = client.retrieve(
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

            client.upsert(
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
            client.delete(
                collection_name=self.collection_name,
                points_selector=PointIdsList(points=other_ids),
            )

            logger.info(f"Merged {len(memory_ids)} memories into {target_id}")
            return target_id

        except StorageError:
            raise
            logger.error(f"Error merging memories: {e}", exc_info=True)
            raise StorageError(f"Failed to merge memories: {e}")

    async def get_recent_activity(
        self,
        limit: int = 20,
        project_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get recent activity including searches and memory additions.

        Args:
            limit: Maximum number of items per category (default 20)
            project_name: Optional project filter

        Returns:
            Dictionary with recent_searches and recent_additions
        """
        client = None
        try:
            client = await self._get_client()
            # Get recent searches from feedback database
            # Use the feedback database path from config
            import sqlite3
            from pathlib import Path

            feedback_db = Path.home() / ".claude-rag" / "feedback.db"
            recent_searches = []

            if feedback_db.exists():
                try:
                    conn = sqlite3.connect(str(feedback_db))
                    cursor = conn.cursor()

                    if project_name:
                        cursor.execute("""
                            SELECT search_id, query, timestamp, rating, project_name
                            FROM search_feedback
                            WHERE project_name = ?
                            ORDER BY timestamp DESC
                            LIMIT ?
                        """, (project_name, limit))
                    else:
                        cursor.execute("""
                            SELECT search_id, query, timestamp, rating, project_name
                            FROM search_feedback
                            ORDER BY timestamp DESC
                            LIMIT ?
                        """, (limit,))

                    for row in cursor.fetchall():
                        recent_searches.append({
                            "search_id": row[0],
                            "query": row[1],
                            "timestamp": row[2],
                            "rating": row[3],
                            "project_name": row[4],
                        })

                    conn.close()
                except Exception as e:
                    logger.warning(f"Could not read feedback database: {e}")

            # Get recent memory additions from Qdrant
            recent_additions = []
            offset = None
            collected = 0

            # Build filter if project specified
            scroll_filter = None
            if project_name:
                scroll_filter = Filter(
                    must=[
                        FieldCondition(
                            key="project_name",
                            match=MatchValue(value=project_name)
                        )
                    ]
                )

            # Scroll through points to get recent memories
            # Note: Qdrant doesn't support sorting by payload fields in scroll,
            # so we need to fetch more and sort in memory
            all_memories = []

            while len(all_memories) < limit * 10 and collected < 1000:  # Fetch up to 1000 to sort
                results, next_offset = client.scroll(
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
                    created_at = payload.get("created_at")
                    if created_at:
                        all_memories.append({
                            "id": str(point.id),
                            "content": payload.get("content", ""),
                            "category": payload.get("category", "unknown"),
                            "created_at": created_at,
                            "project_name": payload.get("project_name", ""),
                        })

                collected += len(results)
                offset = next_offset

                if next_offset is None:
                    break

            # Sort by created_at (most recent first) and take limit
            all_memories.sort(key=lambda x: x["created_at"], reverse=True)

            for memory in all_memories[:limit]:
                # Truncate content for overview
                content = memory["content"]
                if len(content) > 100:
                    content = content[:100] + "..."

                recent_additions.append({
                    "id": memory["id"],
                    "content": content,
                    "category": memory["category"],
                    "created_at": memory["created_at"],
                    "project_name": memory["project_name"],
                })

            return {
                "recent_searches": recent_searches,
                "recent_additions": recent_additions,
            }

        except Exception as e:
            logger.error(f"Error retrieving recent activity: {e}", exc_info=True)
            raise StorageError(f"Failed to retrieve recent activity: {e}")

    # ============================================================
    # Git History Storage and Search (FEAT-055)
    # ============================================================

        finally:
            if client is not None:
                await self._release_client(client)

    async def store_git_commits(
        self,
        commits: List[Dict[str, Any]],
    ) -> int:
        """
        Store git commits for semantic search over history.

        Args:
            commits: List of commit data dictionaries with:
                - commit_hash: str - Git commit SHA
                - repository_path: str - Repository path
                - author_name: str - Commit author name
                - author_email: str - Commit author email
                - author_date: datetime - Author date
                - committer_name: str - Committer name
                - committer_date: datetime - Committer date
                - message: str - Commit message
                - message_embedding: List[float] - Embedding of commit message
                - branch_names: List[str] - Branches containing this commit
                - tags: List[str] - Tags pointing to this commit
                - parent_hashes: List[str] - Parent commit hashes
                - stats: Dict[str, int] - Commit statistics

        Returns:
            Number of commits stored

        Raises:
            StorageError: If storage operation fails
        """
        if not commits:
            return 0

        client = None
        try:
            client = await self._get_client()
            import hashlib
            points = []

            for commit_data in commits:
                commit_hash = commit_data["commit_hash"]
                message_embedding = commit_data["message_embedding"]

                # Convert datetime objects to Unix timestamps for Qdrant range filters
                author_date = commit_data["author_date"]
                if isinstance(author_date, datetime):
                    author_date = author_date.timestamp()

                committer_date = commit_data.get("committer_date")
                if isinstance(committer_date, datetime):
                    committer_date = committer_date.timestamp()

                # Build payload for git commit
                payload = {
                    "type": "git_commit",
                    "commit_hash": commit_hash,
                    "repository_path": commit_data["repository_path"],
                    "author_name": commit_data["author_name"],
                    "author_email": commit_data["author_email"],
                    "author_date": author_date,
                    "committer_name": commit_data.get("committer_name"),
                    "committer_date": committer_date,
                    "message": commit_data["message"],
                    "branch_names": commit_data.get("branch_names", []),
                    "tags": commit_data.get("tags", []),
                    "parent_hashes": commit_data.get("parent_hashes", []),
                    "stats": commit_data.get("stats", {}),
                }

                # Generate deterministic UUID from commit hash for Qdrant point ID
                # This allows us to have consistent IDs across re-indexes
                import uuid
                point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"git-commit-{commit_hash}"))
                payload["id"] = point_id

                # Create point with deterministic UUID as ID
                point = PointStruct(
                    id=point_id,
                    vector=message_embedding,
                    payload=payload,
                )
                points.append(point)

            # Batch upsert all commits
            client.upsert(
                collection_name=self.collection_name,
                points=points,
            )

            logger.info(f"Stored {len(commits)} git commits")
            return len(commits)

        except Exception as e:
            logger.error(f"Error storing git commits: {e}", exc_info=True)
            raise StorageError(f"Failed to store git commits: {e}")

        finally:
            if client is not None:
                await self._release_client(client)

    async def store_git_file_changes(
        self,
        file_changes: List[Dict[str, Any]],
    ) -> int:
        """
        Store git file changes for file-level history tracking.

        Args:
            file_changes: List of file change data dictionaries with:
                - id: str - Unique ID (commit_hash:file_path)
                - commit_hash: str - Commit hash
                - file_path: str - File path
                - change_type: str - added|modified|deleted|renamed
                - lines_added: int - Number of lines added
                - lines_deleted: int - Number of lines deleted
                - diff_content: Optional[str] - Diff content
                - diff_embedding: Optional[List[float]] - Embedding of diff

        Returns:
            Number of file changes stored

        Raises:
            StorageError: If storage operation fails
        """
        if not file_changes:
            return 0

        client = None
        try:
            client = await self._get_client()
            points = []

            for change_data in file_changes:
                change_id = change_data["id"]  # This is commit_hash:file_path

                # Use diff embedding if available, otherwise use empty vector
                diff_embedding = change_data.get("diff_embedding")
                if not diff_embedding:
                    # Create zero vector for file changes without diffs
                    diff_embedding = [0.0] * DEFAULT_EMBEDDING_DIM

                # Build payload for file change
                payload = {
                    "type": "git_file_change",
                    "commit_hash": change_data["commit_hash"],
                    "file_path": change_data["file_path"],
                    "change_type": change_data["change_type"],
                    "lines_added": change_data["lines_added"],
                    "lines_deleted": change_data["lines_deleted"],
                    "diff_content": change_data.get("diff_content"),
                }

                # Generate deterministic UUID from change ID for Qdrant point ID
                import uuid
                point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"git-file-change-{change_id}"))
                payload["id"] = point_id

                # Create point with deterministic UUID as ID
                point = PointStruct(
                    id=point_id,
                    vector=diff_embedding,
                    payload=payload,
                )
                points.append(point)

            # Batch upsert all file changes
            client.upsert(
                collection_name=self.collection_name,
                points=points,
            )

            logger.info(f"Stored {len(file_changes)} git file changes")
            return len(file_changes)

        except Exception as e:
            logger.error(f"Error storing git file changes: {e}", exc_info=True)
            raise StorageError(f"Failed to store git file changes: {e}")

        finally:
            if client is not None:
                await self._release_client(client)

    async def search_git_commits(
        self,
        query: Optional[str] = None,
        repository_path: Optional[str] = None,
        author: Optional[str] = None,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Search git commits with optional filters.

        Args:
            query: Optional text query for semantic search over commit messages
            repository_path: Optional repository path filter
            author: Optional author email filter
            since: Optional start date filter
            until: Optional end date filter
            limit: Maximum number of results

        Returns:
            List of commit dictionaries

        Raises:
            StorageError: If search operation fails
        """
        client = None
        try:
            client = await self._get_client()
            # Build filter conditions
            must_conditions = [
                FieldCondition(key="type", match=MatchValue(value="git_commit"))
            ]

            if repository_path:
                must_conditions.append(
                    FieldCondition(
                        key="repository_path",
                        match=MatchValue(value=repository_path)
                    )
                )

            if author:
                must_conditions.append(
                    FieldCondition(
                        key="author_email",
                        match=MatchValue(value=author)
                    )
                )

            if since or until:
                # Date range filter - convert to Unix timestamps for Qdrant
                date_range = {}
                if since:
                    date_range["gte"] = since.timestamp()
                if until:
                    date_range["lte"] = until.timestamp()

                if date_range:
                    must_conditions.append(
                        FieldCondition(
                            key="author_date",
                            range=Range(**date_range)
                        )
                    )

            search_filter = Filter(must=must_conditions) if must_conditions else None

            results = []

            if query:
                # Semantic search over commit messages
                from src.embeddings.generator import EmbeddingGenerator

                generator = EmbeddingGenerator(self.config)
                query_embedding = await generator.generate(query)

                search_results = client.search(
                    collection_name=self.collection_name,
                    query_vector=query_embedding,
                    query_filter=search_filter,
                    limit=limit,
                    with_payload=True,
                    with_vectors=True,  # Include vectors for message_embedding
                )

                for result in search_results:
                    payload = result.payload
                    vector = result.vector if hasattr(result, 'vector') else []
                    results.append(self._deserialize_commit(payload, vector))

            else:
                # No query - just filter and scroll
                offset = None
                collected = 0

                while collected < limit:
                    scroll_results, next_offset = client.scroll(
                        collection_name=self.collection_name,
                        scroll_filter=search_filter,
                        limit=min(100, limit - collected),
                        offset=offset,
                        with_payload=True,
                        with_vectors=True,  # Include vectors for message_embedding
                    )

                    if not scroll_results:
                        break

                    for point in scroll_results:
                        payload = point.payload
                        vector = point.vector if hasattr(point, 'vector') else []
                        results.append(self._deserialize_commit(payload, vector))
                        collected += 1

                    offset = next_offset
                    if offset is None:
                        break

            # Sort by author_date descending (newest first)
            results.sort(key=lambda x: x.get("author_date", ""), reverse=True)

            return results[:limit]

        except Exception as e:
            logger.error(f"Error searching git commits: {e}", exc_info=True)
            raise StorageError(f"Failed to search git commits: {e}")

        finally:
            if client is not None:
                await self._release_client(client)

    async def get_git_commit(
        self,
        commit_hash: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve a specific git commit by hash.

        Args:
            commit_hash: Git commit SHA

        Returns:
            Commit dictionary or None if not found

        Raises:
            StorageError: If retrieval operation fails
        """
        client = None
        try:
            client = await self._get_client()
            # Search by commit_hash field since we use UUIDs for point IDs
            search_filter = Filter(
                must=[
                    FieldCondition(key="type", match=MatchValue(value="git_commit")),
                    FieldCondition(key="commit_hash", match=MatchValue(value=commit_hash)),
                ]
            )

            results, _ = client.scroll(
                collection_name=self.collection_name,
                scroll_filter=search_filter,
                limit=1,
                with_payload=True,
                with_vectors=True,  # Need vectors to get message_embedding
            )

            if not results:
                return None

            point = results[0]
            payload = point.payload
            vector = point.vector if hasattr(point, 'vector') else []

            return self._deserialize_commit(payload, vector)

        except Exception as e:
            logger.error(f"Error retrieving git commit {commit_hash}: {e}", exc_info=True)
            raise StorageError(f"Failed to retrieve git commit: {e}")

        finally:
            if client is not None:
                await self._release_client(client)

    async def get_commits_by_file(
        self,
        file_path: str,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Get commits that modified a specific file.

        Args:
            file_path: File path to search for
            limit: Maximum number of results

        Returns:
            List of commit dictionaries with file change info

        Raises:
            StorageError: If retrieval operation fails
        """
        client = None
        try:
            client = await self._get_client()
            # First, find file changes for this file
            search_filter = Filter(
                must=[
                    FieldCondition(key="type", match=MatchValue(value="git_file_change")),
                    FieldCondition(key="file_path", match=MatchValue(value=file_path)),
                ]
            )

            file_changes = []
            offset = None
            collected = 0

            while collected < limit:
                scroll_results, next_offset = client.scroll(
                    collection_name=self.collection_name,
                    scroll_filter=search_filter,
                    limit=min(100, limit - collected),
                    offset=offset,
                    with_payload=True,
                    with_vectors=False,
                )

                if not scroll_results:
                    break

                for point in scroll_results:
                    payload = point.payload
                    file_changes.append({
                        "commit_hash": payload["commit_hash"],
                        "change_type": payload["change_type"],
                        "lines_added": payload["lines_added"],
                        "lines_deleted": payload["lines_deleted"],
                    })
                    collected += 1

                offset = next_offset
                if offset is None:
                    break

            # Now get the commits for these changes
            commit_hashes = [fc["commit_hash"] for fc in file_changes]

            if not commit_hashes:
                return []

            # Retrieve commits by hash
            commits_dict = {}
            for commit_hash in commit_hashes:
                commit = await self.get_git_commit(commit_hash)
                if commit:
                    commits_dict[commit_hash] = commit

            # Merge file change info with commit info
            results = []
            for file_change in file_changes:
                commit_hash = file_change["commit_hash"]
                if commit_hash in commits_dict:
                    commit = commits_dict[commit_hash].copy()
                    commit["change_type"] = file_change["change_type"]
                    commit["lines_added"] = file_change["lines_added"]
                    commit["lines_deleted"] = file_change["lines_deleted"]
                    results.append(commit)

            # Sort by author_date descending (newest first)
            results.sort(key=lambda x: x.get("author_date", ""), reverse=True)

            return results[:limit]

        except Exception as e:
            logger.error(f"Error getting commits by file {file_path}: {e}", exc_info=True)
            raise StorageError(f"Failed to get commits by file: {e}")

        finally:
            if client is not None:
                await self._release_client(client)

    def _deserialize_commit(
        self,
        payload: Dict[str, Any],
        vector: Optional[List[float]] = None,
    ) -> Dict[str, Any]:
        """
        Deserialize a commit payload from storage.

        Args:
            payload: Raw payload from Qdrant
            vector: Vector embedding (optional)

        Returns:
            Deserialized commit dictionary
        """
        # Convert Unix timestamps back to ISO format strings
        author_date = payload["author_date"]
        if isinstance(author_date, (int, float)):
            author_date = datetime.fromtimestamp(author_date, tz=UTC).isoformat()

        committer_date = payload.get("committer_date")
        if committer_date and isinstance(committer_date, (int, float)):
            committer_date = datetime.fromtimestamp(committer_date, tz=UTC).isoformat()

        return {
            "commit_hash": payload["commit_hash"],
            "repository_path": payload["repository_path"],
            "author_name": payload["author_name"],
            "author_email": payload["author_email"],
            "author_date": author_date,
            "committer_name": payload.get("committer_name"),
            "committer_date": committer_date,
            "message": payload["message"],
            "message_embedding": vector if vector else [],
            "branch_names": payload.get("branch_names", []),
            "tags": payload.get("tags", []),
            "parent_hashes": payload.get("parent_hashes", []),
            "stats": payload.get("stats", {}),
        }
