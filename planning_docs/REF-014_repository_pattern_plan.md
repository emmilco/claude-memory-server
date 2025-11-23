# REF-014: Extract Qdrant-Specific Logic using Repository Pattern

## Executive Summary

**Problem:** The current `qdrant_store.py` implementation (2,328 lines) has significant Qdrant-specific coupling that makes business logic dependent on vector database implementation details. This violates the dependency inversion principle and makes it difficult to:
- Test business logic without Qdrant
- Switch storage backends efficiently
- Maintain code as Qdrant APIs change
- Understand what operations are domain logic vs. infrastructure

**Solution:** Implement a repository pattern with:
1. **Domain Models** - Pure Python objects representing search results, filters, pagination (Qdrant-agnostic)
2. **Repository Interface** - Business-focused API that hides storage implementation
3. **Mapper Layer** - Bidirectional transformation between domain models and Qdrant structures
4. **Incremental Migration** - Phased refactoring over 6 milestones to avoid breaking changes

**Timeline:** 6-8 weeks (1-2 months)
**Effort:** ~80-120 hours
**Impact:** High - Improves testability, maintainability, and architectural integrity

---

## Current State Analysis

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    Business Logic Layer                      │
│  (MemoryRAGServer, HybridSearcher, MemoryPruner, etc.)      │
└───────────────────────┬─────────────────────────────────────┘
                        │ Uses MemoryStore interface (base.py)
                        ▼
┌─────────────────────────────────────────────────────────────┐
│                QdrantMemoryStore (qdrant_store.py)           │
│  ⚠️  2,328 lines - TIGHT COUPLING TO QDRANT                 │
│                                                               │
│  Problems:                                                    │
│  - Direct imports: PointStruct, Filter, FieldCondition       │
│  - Qdrant-specific logic in 40+ methods                      │
│  - Business logic mixed with infrastructure                  │
│  - Hard to test without Qdrant running                       │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
                 ┌──────────────┐
                 │    Qdrant    │
                 │   (Docker)   │
                 └──────────────┘
```

### Coupling Points

**1. Direct Qdrant Imports (Lines 9-17)**
```python
from qdrant_client.models import (
    PointStruct,          # Vector point representation
    Filter,               # Query filtering
    FieldCondition,       # Field-level filters
    MatchValue,           # Exact match filters
    Range,                # Range filters
    SearchParams,         # Search configuration
)
```
**Impact:** Business logic depends on Qdrant SDK types

**2. Filter Building Logic (Lines 973-1158)**
```python
def _build_filter(self, filters: SearchFilters) -> Optional[Filter]:
    """Build Qdrant filter from SearchFilters."""
    conditions = []

    # Context level
    if filters.context_level:
        conditions.append(FieldCondition(
            key="context_level",
            match=MatchValue(value=filters.context_level.value)
        ))

    # Advanced filters - 185 lines of Qdrant-specific logic
    if filters.advanced_filters:
        # Date ranges using Qdrant Range
        if adv.created_after:
            conditions.append(FieldCondition(
                key="created_at",
                range=Range(gte=adv.created_after.isoformat())
            ))
        # ... 150+ more lines
```
**Impact:** 185 lines of Qdrant filter translation logic embedded in store

**3. Payload Transformation (Lines 874-937, 1160-1264)**
```python
def _build_payload(...) -> Tuple[str, Dict[str, Any]]:
    """Build Qdrant payload with flattened metadata."""
    # Flattens provenance, serializes datetimes, handles enums
    payload = {
        "id": memory_id,
        "content": content,
        "category": metadata.get("category"),
        "provenance_source": provenance.get("source"),
        # ... 30+ fields with Qdrant-specific flattening
    }
    return memory_id, payload

def _payload_to_memory_unit(payload: Dict[str, Any]) -> MemoryUnit:
    """Convert Qdrant payload back to domain model."""
    # 104 lines of deserialization, enum parsing, datetime handling
```
**Impact:** Domain model ↔ Qdrant transformation scattered across 2 methods

**4. Scroll/Pagination Logic (Lines 220-246, 571-598)**
```python
# Qdrant scroll API used directly in business methods
offset = None
while True:
    results, offset = self.client.scroll(
        collection_name=self.collection_name,
        scroll_filter=filter_conditions,
        limit=100,
        offset=offset,
    )
    # Process results...
    if offset is None:
        break
```
**Impact:** Pagination logic tied to Qdrant's scroll API

**5. Search Configuration (Lines 119-130)**
```python
search_result = self.client.query_points(
    collection_name=self.collection_name,
    query=query_embedding,
    query_filter=filter_conditions,
    limit=safe_limit,
    search_params=SearchParams(
        hnsw_ef=128,  # Qdrant-specific tuning
        exact=False,   # Qdrant algorithm selection
    ),
)
```
**Impact:** Vector search configuration hardcoded with Qdrant parameters

### Affected Business Logic (24 files)

From grep analysis, these files import from `qdrant_store`:
- `src/memory/incremental_indexer.py` - Code indexing
- `src/core/server.py` - Main MCP server
- `src/backup/exporter.py` - Data export
- `src/cli/validate_install.py` - Installation checks
- `tests/integration/*.py` - 5+ integration test files

**Key Observation:** Most business logic uses the abstract `MemoryStore` interface, but integration tests and some utilities directly instantiate `QdrantMemoryStore`.

### Why This Matters

1. **Testing Complexity:** Unit tests require Qdrant Docker container or extensive mocking
2. **Vendor Lock-in:** Switching to a different vector DB requires rewriting 2,328 lines
3. **Code Comprehension:** Developers must understand Qdrant APIs to work with storage
4. **Maintenance Burden:** Qdrant SDK changes break our codebase
5. **Performance Tuning:** Can't optimize queries without deep Qdrant knowledge

---

## Domain Model Design

### Principles

1. **Technology-Agnostic:** Domain models should not reference Qdrant, SQL, or any specific storage
2. **Business-Focused:** Models represent what the application needs, not how storage works
3. **Rich Types:** Use enums, value objects, and validation to prevent invalid states
4. **Immutable Where Possible:** Use frozen dataclasses for search criteria

### Core Domain Models

```python
# File: src/store/domain/models.py

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict, Any
from enum import Enum

from src.core.models import MemoryUnit, ContextLevel, MemoryScope, MemoryCategory


@dataclass(frozen=True)
class SearchCriteria:
    """
    Domain model for search criteria (replaces SearchFilters).

    Immutable to ensure thread-safety and prevent accidental mutation.
    """
    # Basic filters
    context_level: Optional[ContextLevel] = None
    scope: Optional[MemoryScope] = None
    category: Optional[MemoryCategory] = None
    project_name: Optional[str] = None
    min_importance: float = 0.0
    tags: List[str] = field(default_factory=list)

    # Date filters
    created_after: Optional[datetime] = None
    created_before: Optional[datetime] = None
    updated_after: Optional[datetime] = None
    updated_before: Optional[datetime] = None
    accessed_after: Optional[datetime] = None
    accessed_before: Optional[datetime] = None

    # Tag logic
    tags_any: List[str] = field(default_factory=list)  # OR logic
    tags_all: List[str] = field(default_factory=list)  # AND logic
    tags_none: List[str] = field(default_factory=list)  # NOT logic

    # Lifecycle filters
    lifecycle_states: List[str] = field(default_factory=list)

    # Exclusions
    exclude_categories: List[MemoryCategory] = field(default_factory=list)
    exclude_projects: List[str] = field(default_factory=list)

    # Provenance
    min_trust_score: Optional[float] = None
    source: Optional[str] = None

    def __post_init__(self):
        """Validate criteria after initialization."""
        if self.min_importance < 0.0 or self.min_importance > 1.0:
            raise ValueError("min_importance must be between 0.0 and 1.0")
        if self.min_trust_score is not None:
            if self.min_trust_score < 0.0 or self.min_trust_score > 1.0:
                raise ValueError("min_trust_score must be between 0.0 and 1.0")


@dataclass
class SearchResult:
    """
    Domain model for a single search result.

    Decouples from Qdrant's ScoredPoint structure.
    """
    memory: MemoryUnit
    score: float
    rank: int  # Position in result set (1-based)

    # Metadata about the search
    matched_fields: List[str] = field(default_factory=list)  # Which fields matched
    score_breakdown: Optional[Dict[str, float]] = None  # Vector, BM25, etc.

    def __post_init__(self):
        """Validate result after initialization."""
        if self.score < 0.0 or self.score > 1.0:
            raise ValueError("score must be between 0.0 and 1.0")
        if self.rank < 1:
            raise ValueError("rank must be >= 1")


@dataclass
class SearchResults:
    """
    Domain model for a collection of search results with metadata.

    Provides rich information about the search operation.
    """
    results: List[SearchResult]
    total_matches: int  # Total results before pagination
    query_time_ms: float

    # Pagination
    limit: int
    offset: int
    has_more: bool

    # Search context
    search_criteria: Optional[SearchCriteria] = None
    query_text: Optional[str] = None

    @property
    def is_empty(self) -> bool:
        """Check if search returned no results."""
        return len(self.results) == 0

    @property
    def result_count(self) -> int:
        """Number of results in this page."""
        return len(self.results)


@dataclass(frozen=True)
class Pagination:
    """
    Domain model for pagination parameters.

    Immutable to prevent accidental changes during query execution.
    """
    limit: int = 20
    offset: int = 0

    def __post_init__(self):
        """Validate pagination parameters."""
        if self.limit < 1:
            raise ValueError("limit must be >= 1")
        if self.limit > 500:
            raise ValueError("limit cannot exceed 500")
        if self.offset < 0:
            raise ValueError("offset must be >= 0")

    @property
    def end(self) -> int:
        """Calculate end index (exclusive)."""
        return self.offset + self.limit


@dataclass(frozen=True)
class SortOrder:
    """
    Domain model for sorting criteria.
    """
    field: str = "created_at"
    descending: bool = True

    def __post_init__(self):
        """Validate sort field."""
        valid_fields = {
            "created_at", "updated_at", "last_accessed",
            "importance", "score"
        }
        if self.field not in valid_fields:
            raise ValueError(
                f"Invalid sort field: {self.field}. "
                f"Valid fields: {valid_fields}"
            )


@dataclass
class VectorSearchOptions:
    """
    Domain model for vector search configuration.

    Decouples from Qdrant's SearchParams.
    """
    # Search quality
    use_exact_search: bool = False  # True = brute force, False = HNSW
    search_depth: int = 128  # How deep to search (Qdrant: hnsw_ef)

    # Result filtering
    min_score: float = 0.0  # Minimum similarity score
    score_threshold: Optional[float] = None  # Alias for min_score

    def __post_init__(self):
        """Validate options."""
        if self.search_depth < 1:
            raise ValueError("search_depth must be >= 1")
        if self.min_score < 0.0 or self.min_score > 1.0:
            raise ValueError("min_score must be between 0.0 and 1.0")


@dataclass
class BatchStoreRequest:
    """
    Domain model for batch storage operations.
    """
    items: List[tuple[str, List[float], Dict[str, Any]]]  # content, embedding, metadata

    @property
    def size(self) -> int:
        """Number of items in batch."""
        return len(self.items)

    def validate(self) -> None:
        """Validate batch request."""
        if self.size == 0:
            raise ValueError("Batch cannot be empty")
        if self.size > 1000:
            raise ValueError("Batch size cannot exceed 1000")

        for i, (content, embedding, metadata) in enumerate(self.items):
            if not content.strip():
                raise ValueError(f"Item {i}: content cannot be empty")
            if not embedding:
                raise ValueError(f"Item {i}: embedding cannot be empty")


@dataclass
class ProjectStats:
    """
    Domain model for project statistics.

    Aggregated information about a project's indexed content.
    """
    project_name: str
    total_memories: int
    num_files: int
    num_functions: int
    num_classes: int
    categories: Dict[str, int]  # category -> count
    context_levels: Dict[str, int]  # context_level -> count
    last_indexed: Optional[datetime] = None

    @property
    def avg_memories_per_file(self) -> float:
        """Calculate average memories per file."""
        if self.num_files == 0:
            return 0.0
        return self.total_memories / self.num_files
```

---

## Repository Interface Design

### Principles

1. **Business Language:** Method names reflect business operations, not storage details
2. **Rich Return Types:** Return domain models, not dictionaries or tuples
3. **Explicit Contracts:** Clear input/output types, no "magic" parameters
4. **Error Handling:** Domain-specific exceptions, not storage exceptions

### Repository Interface

```python
# File: src/store/domain/repository.py

from abc import ABC, abstractmethod
from typing import List, Optional
from datetime import datetime

from src.core.models import MemoryUnit
from src.store.domain.models import (
    SearchCriteria,
    SearchResults,
    Pagination,
    SortOrder,
    VectorSearchOptions,
    BatchStoreRequest,
    ProjectStats,
)


class MemoryRepository(ABC):
    """
    Domain repository for memory operations.

    This interface defines business operations WITHOUT implementation details.
    Implementations (Qdrant, SQLite, etc.) handle the "how", not the "what".
    """

    # ============================================================================
    # CORE OPERATIONS
    # ============================================================================

    @abstractmethod
    async def store_memory(
        self,
        content: str,
        embedding: List[float],
        metadata: dict,
    ) -> str:
        """
        Store a single memory.

        Args:
            content: Memory text content
            embedding: Vector embedding (384 dimensions)
            metadata: Memory metadata (category, tags, etc.)

        Returns:
            Memory ID (UUID string)

        Raises:
            StorageError: If storage fails
            ValidationError: If inputs are invalid
        """
        pass

    @abstractmethod
    async def store_batch(self, request: BatchStoreRequest) -> List[str]:
        """
        Store multiple memories in a single transaction.

        Args:
            request: Batch storage request with validation

        Returns:
            List of memory IDs in same order as request

        Raises:
            StorageError: If batch storage fails
            ValidationError: If request is invalid
        """
        pass

    @abstractmethod
    async def get_memory_by_id(self, memory_id: str) -> Optional[MemoryUnit]:
        """
        Retrieve a memory by its unique identifier.

        Args:
            memory_id: Memory UUID

        Returns:
            MemoryUnit if found, None otherwise

        Raises:
            StorageError: If retrieval fails
        """
        pass

    @abstractmethod
    async def delete_memory(self, memory_id: str) -> bool:
        """
        Delete a memory permanently.

        Args:
            memory_id: Memory UUID

        Returns:
            True if deleted, False if not found

        Raises:
            StorageError: If deletion fails
        """
        pass

    @abstractmethod
    async def update_memory(
        self,
        memory_id: str,
        updates: dict,
        new_embedding: Optional[List[float]] = None,
    ) -> bool:
        """
        Update memory metadata and optionally its embedding.

        Args:
            memory_id: Memory UUID
            updates: Fields to update (partial update)
            new_embedding: New embedding vector (if content changed)

        Returns:
            True if updated, False if not found

        Raises:
            StorageError: If update fails
        """
        pass

    # ============================================================================
    # SEARCH OPERATIONS
    # ============================================================================

    @abstractmethod
    async def search_by_vector(
        self,
        query_embedding: List[float],
        criteria: Optional[SearchCriteria] = None,
        pagination: Pagination = Pagination(),
        options: Optional[VectorSearchOptions] = None,
    ) -> SearchResults:
        """
        Search memories by semantic similarity.

        Args:
            query_embedding: Query vector (384 dimensions)
            criteria: Optional search filters
            pagination: Result pagination
            options: Vector search tuning

        Returns:
            SearchResults with ranked memories

        Raises:
            StorageError: If search fails
        """
        pass

    @abstractmethod
    async def search_by_criteria(
        self,
        criteria: SearchCriteria,
        pagination: Pagination = Pagination(),
        sort: SortOrder = SortOrder(),
    ) -> SearchResults:
        """
        Search memories by metadata criteria (no vector search).

        Useful for browsing, filtering, and listing operations.

        Args:
            criteria: Search filters
            pagination: Result pagination
            sort: Sort order

        Returns:
            SearchResults with filtered memories

        Raises:
            StorageError: If search fails
        """
        pass

    @abstractmethod
    async def count_memories(
        self,
        criteria: Optional[SearchCriteria] = None,
    ) -> int:
        """
        Count memories matching criteria.

        Args:
            criteria: Optional filters (None = count all)

        Returns:
            Number of matching memories

        Raises:
            StorageError: If count fails
        """
        pass

    # ============================================================================
    # PROJECT OPERATIONS
    # ============================================================================

    @abstractmethod
    async def get_all_projects(self) -> List[str]:
        """
        List all unique project names.

        Returns:
            Sorted list of project names

        Raises:
            StorageError: If listing fails
        """
        pass

    @abstractmethod
    async def get_project_stats(self, project_name: str) -> ProjectStats:
        """
        Get aggregated statistics for a project.

        Args:
            project_name: Project to analyze

        Returns:
            ProjectStats with counts and metadata

        Raises:
            StorageError: If stats retrieval fails
        """
        pass

    @abstractmethod
    async def delete_project_memories(
        self,
        project_name: str,
        category: Optional[str] = None,
    ) -> int:
        """
        Delete all memories for a project.

        Args:
            project_name: Project to delete
            category: Optional category filter (e.g., "code")

        Returns:
            Number of memories deleted

        Raises:
            StorageError: If deletion fails
        """
        pass

    # ============================================================================
    # HEALTH & MAINTENANCE
    # ============================================================================

    @abstractmethod
    async def health_check(self) -> bool:
        """
        Check if storage backend is healthy.

        Returns:
            True if healthy, False otherwise
        """
        pass

    @abstractmethod
    async def initialize(self) -> None:
        """
        Initialize storage backend (create collections, indexes, etc.).

        Raises:
            StorageError: If initialization fails
        """
        pass

    @abstractmethod
    async def close(self) -> None:
        """
        Close connections and release resources.
        """
        pass
```

### Key Design Decisions

**1. Rich Domain Models Instead of Primitives**
- ❌ Before: `retrieve(embedding, filters: Optional[SearchFilters], limit: int)`
- ✅ After: `search_by_vector(embedding, criteria: SearchCriteria, pagination: Pagination)`
- **Why:** Type safety, validation, self-documenting code

**2. Explicit Pagination Model**
- ❌ Before: `limit` and `offset` as separate parameters
- ✅ After: `Pagination` dataclass with validation
- **Why:** Prevents invalid pagination (negative offset, limit > 500)

**3. Search Results with Metadata**
- ❌ Before: `List[Tuple[MemoryUnit, float]]`
- ✅ After: `SearchResults` with total count, query time, pagination info
- **Why:** Clients need total count for pagination UI, query time for monitoring

**4. Separation of Vector Search and Criteria Search**
- `search_by_vector()` - Semantic similarity with optional filters
- `search_by_criteria()` - Metadata-only filtering (browsing, listing)
- **Why:** Different use cases, different performance characteristics

---

## Mapper Layer Design

### Principles

1. **Bidirectional:** Domain ↔ Storage transformations in both directions
2. **Stateless:** Mappers are pure functions, no side effects
3. **Explicit:** All transformations are visible, no "magic"
4. **Testable:** Easy to unit test without storage

### Mapper Architecture

```python
# File: src/store/qdrant/mappers.py

from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime
from uuid import uuid4

from qdrant_client.models import (
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
    Range,
    SearchParams,
    ScoredPoint,
)

from src.core.models import MemoryUnit, MemoryProvenance
from src.store.domain.models import (
    SearchCriteria,
    SearchResult,
    SearchResults,
    VectorSearchOptions,
    ProjectStats,
)


class QdrantMapper:
    """
    Mapper for bidirectional transformation between domain and Qdrant models.

    All Qdrant-specific knowledge is centralized here.
    """

    # ============================================================================
    # DOMAIN → QDRANT (Outbound)
    # ============================================================================

    @staticmethod
    def to_qdrant_point(
        content: str,
        embedding: List[float],
        metadata: dict,
    ) -> Tuple[str, PointStruct]:
        """
        Convert domain memory to Qdrant PointStruct.

        Args:
            content: Memory content
            embedding: Vector embedding
            metadata: Memory metadata

        Returns:
            (memory_id, PointStruct)
        """
        memory_id = metadata.get("id", str(uuid4()))

        # Build payload (flatten nested structures for Qdrant)
        payload = QdrantMapper._build_payload(memory_id, content, metadata)

        point = PointStruct(
            id=memory_id,
            vector=embedding,
            payload=payload,
        )

        return memory_id, point

    @staticmethod
    def to_qdrant_filter(criteria: SearchCriteria) -> Optional[Filter]:
        """
        Convert domain SearchCriteria to Qdrant Filter.

        Args:
            criteria: Domain search criteria

        Returns:
            Qdrant Filter or None if no criteria
        """
        conditions = []

        # Context level
        if criteria.context_level:
            conditions.append(FieldCondition(
                key="context_level",
                match=MatchValue(value=criteria.context_level.value)
            ))

        # Scope
        if criteria.scope:
            conditions.append(FieldCondition(
                key="scope",
                match=MatchValue(value=criteria.scope.value)
            ))

        # Category
        if criteria.category:
            conditions.append(FieldCondition(
                key="category",
                match=MatchValue(value=criteria.category.value)
            ))

        # Project name
        if criteria.project_name:
            conditions.append(FieldCondition(
                key="project_name",
                match=MatchValue(value=criteria.project_name)
            ))

        # Importance range
        if criteria.min_importance > 0.0:
            conditions.append(FieldCondition(
                key="importance",
                range=Range(gte=criteria.min_importance)
            ))

        # Date ranges
        if criteria.created_after:
            conditions.append(FieldCondition(
                key="created_at",
                range=Range(gte=criteria.created_after.isoformat())
            ))
        if criteria.created_before:
            conditions.append(FieldCondition(
                key="created_at",
                range=Range(lte=criteria.created_before.isoformat())
            ))

        # Tag logic - ANY (OR)
        if criteria.tags_any:
            from qdrant_client.models import MatchAny
            conditions.append(FieldCondition(
                key="tags",
                match=MatchAny(any=criteria.tags_any)
            ))

        # Tag logic - ALL (AND)
        for tag in criteria.tags_all:
            conditions.append(FieldCondition(
                key="tags",
                match=MatchValue(value=tag)
            ))

        # Tag logic - NONE (NOT)
        if criteria.tags_none:
            tag_none_conditions = [
                FieldCondition(key="tags", match=MatchValue(value=tag))
                for tag in criteria.tags_none
            ]
            conditions.append(Filter(must_not=tag_none_conditions))

        # Lifecycle states
        if criteria.lifecycle_states:
            lifecycle_conditions = [
                FieldCondition(
                    key="lifecycle_state",
                    match=MatchValue(value=state)
                )
                for state in criteria.lifecycle_states
            ]
            conditions.append(Filter(should=lifecycle_conditions))

        # Exclusions
        if criteria.exclude_categories:
            exclude_cat_conditions = [
                FieldCondition(
                    key="category",
                    match=MatchValue(value=cat.value)
                )
                for cat in criteria.exclude_categories
            ]
            conditions.append(Filter(must_not=exclude_cat_conditions))

        if criteria.exclude_projects:
            exclude_proj_conditions = [
                FieldCondition(key="project_name", match=MatchValue(value=proj))
                for proj in criteria.exclude_projects
            ]
            conditions.append(Filter(must_not=exclude_proj_conditions))

        # Provenance filters
        if criteria.min_trust_score is not None:
            conditions.append(FieldCondition(
                key="provenance.confidence",
                range=Range(gte=criteria.min_trust_score)
            ))

        if criteria.source:
            conditions.append(FieldCondition(
                key="provenance.source",
                match=MatchValue(value=criteria.source)
            ))

        if not conditions:
            return None

        return Filter(must=conditions)

    @staticmethod
    def to_qdrant_search_params(options: VectorSearchOptions) -> SearchParams:
        """
        Convert domain VectorSearchOptions to Qdrant SearchParams.

        Args:
            options: Domain search options

        Returns:
            Qdrant SearchParams
        """
        return SearchParams(
            hnsw_ef=options.search_depth,
            exact=options.use_exact_search,
        )

    # ============================================================================
    # QDRANT → DOMAIN (Inbound)
    # ============================================================================

    @staticmethod
    def from_qdrant_point(point: ScoredPoint) -> MemoryUnit:
        """
        Convert Qdrant ScoredPoint to domain MemoryUnit.

        Args:
            point: Qdrant search result

        Returns:
            Domain MemoryUnit
        """
        payload = dict(point.payload)
        return QdrantMapper._payload_to_memory_unit(payload)

    @staticmethod
    def from_qdrant_search_results(
        points: List[ScoredPoint],
        total_count: int,
        query_time_ms: float,
        limit: int,
        offset: int,
        criteria: Optional[SearchCriteria] = None,
        query_text: Optional[str] = None,
    ) -> SearchResults:
        """
        Convert Qdrant search results to domain SearchResults.

        Args:
            points: Qdrant search results
            total_count: Total matches before pagination
            query_time_ms: Query execution time
            limit: Page size
            offset: Page offset
            criteria: Original search criteria
            query_text: Original query text

        Returns:
            Domain SearchResults
        """
        results = []
        for rank, point in enumerate(points, start=1):
            memory = QdrantMapper.from_qdrant_point(point)
            result = SearchResult(
                memory=memory,
                score=float(point.score),
                rank=rank,
            )
            results.append(result)

        return SearchResults(
            results=results,
            total_matches=total_count,
            query_time_ms=query_time_ms,
            limit=limit,
            offset=offset,
            has_more=(offset + len(results)) < total_count,
            search_criteria=criteria,
            query_text=query_text,
        )

    # ============================================================================
    # PRIVATE HELPERS
    # ============================================================================

    @staticmethod
    def _build_payload(
        memory_id: str,
        content: str,
        metadata: dict,
    ) -> Dict[str, Any]:
        """
        Build Qdrant payload from memory metadata.

        Flattens nested structures (provenance) for Qdrant filtering.
        """
        from datetime import UTC

        now = datetime.now(UTC)
        created_at = metadata.get("created_at", now)
        if isinstance(created_at, datetime):
            created_at = created_at.isoformat()

        # Extract and flatten provenance
        provenance = metadata.get("provenance", {})
        if not isinstance(provenance, dict):
            provenance = provenance.model_dump() if hasattr(provenance, 'model_dump') else {}

        payload = {
            "id": memory_id,
            "content": content,
            "category": metadata.get("category"),
            "context_level": metadata.get("context_level"),
            "scope": metadata.get("scope", "global"),
            "project_name": metadata.get("project_name"),
            "importance": metadata.get("importance", 0.5),
            "created_at": created_at,
            "updated_at": now.isoformat(),
            "last_accessed": metadata.get("last_accessed", now.isoformat()),
            "lifecycle_state": metadata.get("lifecycle_state", "ACTIVE"),
            "tags": metadata.get("tags", []),
            # Flatten provenance
            "provenance_source": provenance.get("source", "user_explicit"),
            "provenance_created_by": provenance.get("created_by", "user_statement"),
            "provenance_confidence": provenance.get("confidence", 0.8),
            "provenance_verified": provenance.get("verified", False),
            # Merge custom metadata
            **metadata.get("metadata", {}),
        }

        return payload

    @staticmethod
    def _payload_to_memory_unit(payload: Dict[str, Any]) -> MemoryUnit:
        """
        Convert Qdrant payload to domain MemoryUnit.

        Reconstructs nested structures (provenance) from flattened payload.
        """
        from datetime import UTC
        from src.core.models import (
            MemoryCategory,
            ContextLevel,
            MemoryScope,
            LifecycleState,
            MemoryProvenance,
            ProvenanceSource,
        )

        # Parse datetimes
        created_at = payload.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=UTC)

        # Parse enums
        category = MemoryCategory(payload.get("category", "context"))
        context_level = ContextLevel(payload.get("context_level", "PROJECT_CONTEXT"))
        scope = MemoryScope(payload.get("scope", "global"))
        lifecycle_state = LifecycleState(payload.get("lifecycle_state", "ACTIVE"))

        # Reconstruct provenance
        provenance = MemoryProvenance(
            source=ProvenanceSource(payload.get("provenance_source", "user_explicit")),
            created_by=payload.get("provenance_created_by", "user_statement"),
            confidence=float(payload.get("provenance_confidence", 0.8)),
            verified=bool(payload.get("provenance_verified", False)),
        )

        # Extract custom metadata (everything not in standard fields)
        standard_fields = {
            "id", "content", "category", "context_level", "scope",
            "project_name", "importance", "created_at", "updated_at",
            "last_accessed", "lifecycle_state", "tags",
            "provenance_source", "provenance_created_by",
            "provenance_confidence", "provenance_verified",
        }
        metadata = {
            k: v for k, v in payload.items()
            if k not in standard_fields
        }

        return MemoryUnit(
            id=payload["id"],
            content=payload["content"],
            category=category,
            context_level=context_level,
            scope=scope,
            project_name=payload.get("project_name"),
            importance=payload.get("importance", 0.5),
            created_at=created_at,
            lifecycle_state=lifecycle_state,
            provenance=provenance,
            tags=payload.get("tags", []),
            metadata=metadata,
        )
```

### Error Handling Strategy

```python
# File: src/store/qdrant/exceptions.py

class QdrantMappingError(Exception):
    """Raised when Qdrant ↔ Domain mapping fails."""
    pass


class QdrantConnectionError(Exception):
    """Raised when Qdrant connection fails."""
    pass


# In mapper:
def to_qdrant_filter(criteria: SearchCriteria) -> Optional[Filter]:
    try:
        # ... mapping logic
    except Exception as e:
        raise QdrantMappingError(
            f"Failed to convert SearchCriteria to Qdrant Filter: {e}"
        ) from e
```

---

## Migration Strategy

### Overview

Incremental migration over **6 phases** to minimize risk and maintain backward compatibility.

### Phase 1: Foundation (Week 1) ⚙️

**Goal:** Establish domain models and repository interface without breaking existing code.

**Tasks:**
1. Create `src/store/domain/` directory
2. Implement domain models (`models.py`)
3. Define repository interface (`repository.py`)
4. Write unit tests for domain models (validation, immutability)
5. Update `ARCHITECTURE.md` with new patterns

**Deliverables:**
- `src/store/domain/models.py` (300 lines)
- `src/store/domain/repository.py` (250 lines)
- `tests/unit/test_domain_models.py` (150 lines)

**Validation:**
- All domain model tests pass
- No changes to existing code (parallel implementation)

**Effort:** 12-16 hours

---

### Phase 2: Mapper Layer (Week 2) 🔄

**Goal:** Centralize all Qdrant-specific transformation logic.

**Tasks:**
1. Create `src/store/qdrant/` directory
2. Implement `QdrantMapper` class
3. Extract existing transformation logic from `qdrant_store.py`:
   - `_build_payload()` → `QdrantMapper.to_qdrant_point()`
   - `_payload_to_memory_unit()` → `QdrantMapper.from_qdrant_point()`
   - `_build_filter()` → `QdrantMapper.to_qdrant_filter()`
4. Write comprehensive mapper unit tests
5. Add error handling for mapping failures

**Deliverables:**
- `src/store/qdrant/mappers.py` (500 lines)
- `tests/unit/test_qdrant_mapper.py` (300 lines)

**Validation:**
- Mapper tests cover all SearchCriteria combinations
- Bidirectional mapping: `domain → qdrant → domain` preserves data
- Performance: Mapping adds <1ms overhead

**Effort:** 16-20 hours

---

### Phase 3: Repository Adapter (Week 3-4) 🏗️

**Goal:** Implement `MemoryRepository` interface using Qdrant via mappers.

**Tasks:**
1. Create `QdrantMemoryRepository` implementing `MemoryRepository`
2. Delegate to mappers for all transformations
3. Migrate core methods:
   - `store_memory()` using `QdrantMapper.to_qdrant_point()`
   - `search_by_vector()` using `QdrantMapper.to_qdrant_filter()`
   - `get_memory_by_id()` using `QdrantMapper.from_qdrant_point()`
4. Implement scroll-based pagination in repository layer
5. Add integration tests using Docker Qdrant

**Deliverables:**
- `src/store/qdrant/repository.py` (800 lines)
- `tests/integration/test_qdrant_repository.py` (400 lines)

**Validation:**
- All repository interface methods implemented
- Integration tests pass with Docker Qdrant
- Backward compatibility: `QdrantMemoryStore` still works

**Effort:** 24-32 hours

---

### Phase 4: Business Logic Migration (Week 5) 🔌

**Goal:** Migrate business logic to use repository interface.

**Tasks:**
1. Update `MemoryRAGServer` to use `MemoryRepository`
2. Refactor search methods:
   - Replace `SearchFilters` with `SearchCriteria`
   - Replace `List[Tuple[MemoryUnit, float]]` with `SearchResults`
3. Update `HybridSearcher` to accept `SearchResults`
4. Migrate `MemoryPruner`, `UsageTracker` to repository
5. Update all MCP tools to use new types

**Deliverables:**
- Updated `src/core/server.py`
- Updated `src/search/hybrid_search.py`
- Updated `src/memory/pruner.py`, `usage_tracker.py`

**Validation:**
- All MCP tools work with new repository
- Integration tests pass end-to-end
- No regressions in search quality

**Effort:** 20-24 hours

---

### Phase 5: Legacy Cleanup (Week 6) 🧹

**Goal:** Remove old implementations and consolidate code.

**Tasks:**
1. Mark `QdrantMemoryStore` as deprecated
2. Remove duplicate transformation logic
3. Update all tests to use `MemoryRepository`
4. Consolidate Qdrant code:
   - Move `qdrant_store.py` → `src/store/qdrant/legacy_store.py`
   - Keep for backward compatibility (if needed)
5. Update documentation and examples

**Deliverables:**
- Deprecated `QdrantMemoryStore` with migration guide
- Updated `README.md`, `ARCHITECTURE.md`, `API.md`
- Migration script for users with custom integrations

**Validation:**
- All tests use `MemoryRepository`
- Code coverage maintained (>85%)
- Documentation examples updated

**Effort:** 12-16 hours

---

### Phase 6: Testing & Optimization (Week 7-8) ⚡

**Goal:** Ensure quality, performance, and production readiness.

**Tasks:**
1. **Testing:**
   - Add mock repository for unit tests (no Docker needed)
   - Increase test coverage to 90%+ for repository layer
   - Add property-based tests (hypothesis) for mappers
   - Load testing with 100k+ memories
2. **Performance:**
   - Benchmark repository vs. old store (should be ±5%)
   - Optimize mapper allocations (reuse objects)
   - Profile memory usage
3. **Documentation:**
   - Add repository pattern guide to `docs/ARCHITECTURE.md`
   - Document mapper customization for future backends
   - Create migration guide for external users

**Deliverables:**
- Mock repository implementation
- Performance benchmarks report
- Updated architecture documentation

**Validation:**
- Test coverage >90% for repository layer
- Performance within 5% of original
- Zero production issues in staging

**Effort:** 16-24 hours

---

## Testing Strategy

### 1. Unit Tests (No Docker)

**Domain Models:**
```python
# tests/unit/test_domain_models.py

def test_search_criteria_immutable():
    """Verify SearchCriteria is immutable."""
    criteria = SearchCriteria(min_importance=0.5)

    with pytest.raises(AttributeError):
        criteria.min_importance = 0.7  # Should fail (frozen)


def test_pagination_validation():
    """Verify Pagination validates inputs."""
    with pytest.raises(ValueError):
        Pagination(limit=0)  # Must be >= 1

    with pytest.raises(ValueError):
        Pagination(limit=1000)  # Cannot exceed 500

    with pytest.raises(ValueError):
        Pagination(offset=-1)  # Must be >= 0


def test_search_results_metadata():
    """Verify SearchResults provides rich metadata."""
    results = SearchResults(
        results=[],
        total_matches=100,
        query_time_ms=15.3,
        limit=20,
        offset=0,
        has_more=True,
    )

    assert results.is_empty is True
    assert results.result_count == 0
    assert results.has_more is True
```

**Mapper Tests:**
```python
# tests/unit/test_qdrant_mapper.py

def test_to_qdrant_filter_basic():
    """Verify basic filter conversion."""
    criteria = SearchCriteria(
        category=MemoryCategory.CODE,
        min_importance=0.7,
    )

    qdrant_filter = QdrantMapper.to_qdrant_filter(criteria)

    assert qdrant_filter is not None
    assert len(qdrant_filter.must) == 2
    # Verify filter structure without coupling to Qdrant details


def test_bidirectional_mapping_preserves_data():
    """Verify domain → Qdrant → domain is lossless."""
    original_memory = MemoryUnit(
        content="Test memory",
        category=MemoryCategory.FACT,
        importance=0.8,
        tags=["test"],
    )

    # Convert to Qdrant
    memory_id, point = QdrantMapper.to_qdrant_point(
        content=original_memory.content,
        embedding=[0.1] * 384,
        metadata=original_memory.model_dump(),
    )

    # Convert back to domain
    reconstructed = QdrantMapper._payload_to_memory_unit(point.payload)

    # Verify equivalence
    assert reconstructed.content == original_memory.content
    assert reconstructed.category == original_memory.category
    assert reconstructed.importance == original_memory.importance
    assert reconstructed.tags == original_memory.tags
```

### 2. Integration Tests (Qdrant Docker)

```python
# tests/integration/test_qdrant_repository.py

@pytest.fixture
async def qdrant_repository():
    """Provide a Qdrant repository for integration tests."""
    config = ServerConfig(storage_backend="qdrant")
    repo = QdrantMemoryRepository(config)
    await repo.initialize()
    yield repo
    await repo.close()


async def test_search_by_vector_with_criteria(qdrant_repository):
    """Verify vector search with complex criteria."""
    # Store test data
    embedding = [0.1] * 384
    await qdrant_repository.store_memory(
        content="Python function for data processing",
        embedding=embedding,
        metadata={
            "category": "code",
            "tags": ["python", "data"],
            "importance": 0.9,
        },
    )

    # Search with criteria
    criteria = SearchCriteria(
        category=MemoryCategory.CODE,
        tags_any=["python"],
        min_importance=0.8,
    )

    results = await qdrant_repository.search_by_vector(
        query_embedding=embedding,
        criteria=criteria,
        pagination=Pagination(limit=10),
    )

    assert results.total_matches >= 1
    assert results.results[0].memory.category == MemoryCategory.CODE
    assert "python" in results.results[0].memory.tags
```

### 3. Mock Repository (Fast Tests)

```python
# tests/mocks/mock_repository.py

class MockMemoryRepository(MemoryRepository):
    """In-memory repository for fast unit tests."""

    def __init__(self):
        self.memories: Dict[str, MemoryUnit] = {}
        self.embeddings: Dict[str, List[float]] = {}

    async def store_memory(self, content, embedding, metadata) -> str:
        memory_id = str(uuid4())
        memory = MemoryUnit(
            id=memory_id,
            content=content,
            **metadata,
        )
        self.memories[memory_id] = memory
        self.embeddings[memory_id] = embedding
        return memory_id

    async def search_by_vector(self, query_embedding, criteria, pagination, options):
        # Simple cosine similarity search
        results = []
        for mem_id, memory in self.memories.items():
            if self._matches_criteria(memory, criteria):
                score = self._cosine_similarity(
                    query_embedding,
                    self.embeddings[mem_id]
                )
                results.append(SearchResult(
                    memory=memory,
                    score=score,
                    rank=0,  # Will be set after sorting
                ))

        # Sort and paginate
        results.sort(key=lambda r: r.score, reverse=True)
        # ... pagination logic

        return SearchResults(...)
```

**Usage in tests:**
```python
def test_memory_rag_server_with_mock():
    """Test server without Docker dependency."""
    mock_repo = MockMemoryRepository()
    server = MemoryRAGServer(repository=mock_repo)

    # Test business logic without Qdrant
    result = await server.store_memory(...)
    assert result is not None
```

---

## Benefits and Trade-offs

### Benefits

**1. Reduced Coupling (High Impact)**
- Business logic independent of Qdrant SDK
- Can switch vector DBs in days, not months
- Storage implementation changes don't ripple to 24+ files

**2. Improved Testability (High Impact)**
- Unit tests without Docker: ~2s runtime (was ~60s)
- Mock repository enables 1000+ tests in CI
- Property-based testing of mappers catches edge cases

**3. Better Code Organization (Medium Impact)**
- Single Responsibility: Repository handles storage, Mapper handles transformation
- Domain models self-document business rules
- Easier onboarding for new developers

**4. Type Safety (Medium Impact)**
- Rich domain types prevent runtime errors
- IDE autocomplete for `SearchResults.total_matches`
- Compile-time validation of search criteria

**5. Flexibility for Future Backends (Low Impact - Long Term)**
- SQLite repository can reuse domain models
- PostgreSQL/pgvector integration easier
- In-memory repository for testing

### Trade-offs

**1. Additional Abstraction Layers**
- **Cost:** More files, more interfaces
- **Mitigation:** Clear documentation, examples
- **Verdict:** Worth it for testability gains

**2. Performance Overhead**
- **Cost:** Mapper allocations, extra objects
- **Measurement:** Expect <1ms overhead per query
- **Mitigation:** Optimize hot paths, object pooling
- **Verdict:** Negligible compared to network I/O

**3. Migration Effort**
- **Cost:** 80-120 hours over 6-8 weeks
- **Risk:** Temporary code duplication during migration
- **Mitigation:** Incremental migration, maintain backward compatibility
- **Verdict:** One-time cost, long-term benefit

**4. Learning Curve**
- **Cost:** Developers must learn repository pattern
- **Mitigation:** Documentation, code reviews, examples
- **Verdict:** Industry-standard pattern, transferable knowledge

### Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Performance regression | Medium | High | Benchmark each phase, optimize mappers |
| Breaking changes | Low | High | Maintain backward compatibility through Phase 4 |
| Incomplete migration | Low | Medium | Incremental commits, feature flags |
| Test coverage gaps | Medium | Medium | Require 90% coverage for new code |
| Team resistance | Low | Low | Show benefits with mock repository demos |

---

## Timeline and Effort Estimate

### Summary

| Phase | Duration | Effort | Deliverables |
|-------|----------|--------|--------------|
| 1. Foundation | Week 1 | 12-16h | Domain models, repository interface |
| 2. Mapper Layer | Week 2 | 16-20h | QdrantMapper, transformation tests |
| 3. Repository Adapter | Week 3-4 | 24-32h | QdrantMemoryRepository implementation |
| 4. Business Logic Migration | Week 5 | 20-24h | Update server, tools, pruner |
| 5. Legacy Cleanup | Week 6 | 12-16h | Deprecate old code, docs |
| 6. Testing & Optimization | Week 7-8 | 16-24h | Mock repo, benchmarks, polish |
| **TOTAL** | **6-8 weeks** | **100-132h** | Production-ready repository pattern |

### Detailed Schedule

**Week 1: Foundation**
- Day 1-2: Design domain models, review with team
- Day 3-4: Implement models and validation
- Day 5: Write unit tests, update docs

**Week 2: Mapper Layer**
- Day 1-2: Extract transformation logic to mappers
- Day 3-4: Implement bidirectional mapping
- Day 5: Unit tests for all mapper combinations

**Week 3-4: Repository Adapter**
- Week 3: Implement core repository methods
- Week 4: Add pagination, filtering, project operations
- Both weeks: Integration tests in parallel

**Week 5: Business Logic Migration**
- Day 1-2: Update MemoryRAGServer
- Day 3: Migrate HybridSearcher
- Day 4-5: Update tools, pruner, usage tracker

**Week 6: Legacy Cleanup**
- Day 1-2: Deprecate old code, migration guide
- Day 3-4: Update all documentation
- Day 5: Final cleanup, remove dead code

**Week 7-8: Testing & Optimization**
- Week 7: Mock repository, increase coverage
- Week 8: Performance tuning, benchmarks, staging tests

### Resource Requirements

**People:**
- 1 senior engineer (lead, architecture decisions)
- 1 engineer (implementation, testing)
- 0.2 tech lead (code reviews, unblocking)

**Infrastructure:**
- Staging Qdrant cluster for load testing
- CI/CD pipeline with parallel test runners
- Performance monitoring for benchmarks

---

## Next Steps

### Immediate Actions (This Week)

1. **Review this plan** with the team
2. **Validate domain models** - Are these the right abstractions?
3. **Spike investigation** - Prototype `QdrantMapper.to_qdrant_filter()` to verify approach
4. **Set up tracking** - Create GitHub project board for 6 phases

### Approval Criteria

- [ ] Team consensus on repository interface
- [ ] Stakeholder approval for 6-8 week timeline
- [ ] Commitment to maintain backward compatibility
- [ ] Agreement on 90% test coverage target

### Success Metrics

After completion, measure:
- **Unit test runtime:** <5s without Docker (was 60s)
- **Test coverage:** >90% for repository layer
- **Performance:** Within 5% of original implementation
- **Code quality:** Reduced cyclomatic complexity in business logic
- **Developer satisfaction:** Survey team on new architecture

---

## References

### Existing Patterns in Codebase

- `src/store/base.py` - Abstract interface (to be enhanced)
- `src/search/hybrid_search.py` - Good example of domain-focused design
- `src/core/models.py` - Domain models for MemoryUnit

### External Resources

- **Repository Pattern:** Martin Fowler's "Patterns of Enterprise Application Architecture"
- **Domain-Driven Design:** Eric Evans' DDD principles
- **Python Type Safety:** PEP 589 (TypedDict), PEP 604 (Union types)

### Related TODOs

- **REF-009:** Code review findings (architecture improvements)
- **TEST-006:** Test infrastructure (will benefit from mock repository)
- **FEAT-017:** Multi-repository support (needs storage abstraction)

---

## Appendix: Code Examples

### Example: Business Logic Before vs. After

**Before (Coupled to Qdrant):**
```python
# In MemoryRAGServer
async def retrieve_memories(self, query: str):
    embedding = await self.embedding_generator.generate(query)

    # Build Qdrant filter (tight coupling)
    from qdrant_client.models import Filter, FieldCondition, MatchValue
    qdrant_filter = Filter(must=[
        FieldCondition(key="category", match=MatchValue(value="code"))
    ])

    # Get raw tuples
    results = await self.store.retrieve(
        query_embedding=embedding,
        filters=qdrant_filter,  # Qdrant type leaked!
        limit=10,
    )

    # Returns List[Tuple[MemoryUnit, float]] - not self-documenting
    return results
```

**After (Repository Pattern):**
```python
# In MemoryRAGServer
async def retrieve_memories(self, query: str):
    embedding = await self.embedding_generator.generate(query)

    # Build domain criteria (no Qdrant knowledge)
    criteria = SearchCriteria(
        category=MemoryCategory.CODE,
        min_importance=0.5,
    )

    # Search using domain types
    results = await self.repository.search_by_vector(
        query_embedding=embedding,
        criteria=criteria,
        pagination=Pagination(limit=10),
    )

    # Returns rich SearchResults with metadata
    print(f"Found {results.total_matches} total matches")
    print(f"Query took {results.query_time_ms}ms")
    return results.results  # List[SearchResult]
```

### Example: Testing Before vs. After

**Before (Requires Docker):**
```python
# tests/integration/test_server.py

@pytest.fixture
async def qdrant_store():
    # Must start Docker Qdrant
    config = ServerConfig(storage_backend="qdrant")
    store = QdrantMemoryStore(config)
    await store.initialize()
    yield store
    await store.close()


async def test_search(qdrant_store):
    # 60s startup time for Docker
    server = MemoryRAGServer(store=qdrant_store)
    # ... test logic
```

**After (Mock Repository):**
```python
# tests/unit/test_server.py

@pytest.fixture
def mock_repository():
    # Instant startup, no Docker
    return MockMemoryRepository()


async def test_search(mock_repository):
    # <1s runtime
    server = MemoryRAGServer(repository=mock_repository)
    # ... test business logic
```

---

**Document Version:** 1.0
**Created:** 2025-11-22
**Author:** AI Software Architect
**Status:** ✅ Ready for Review
**Next Review:** After team feedback
