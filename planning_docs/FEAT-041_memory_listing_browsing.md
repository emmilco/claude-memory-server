# FEAT-041: Memory Listing and Browsing

## TODO Reference
- **ID:** FEAT-041
- **TODO.md:** Lines 74-83
- **Priority:** HIGH 🔥🔥🔥
- **Estimate:** 2-3 days

## Objective
Enable users to list and browse memories without requiring semantic search. This addresses a critical UX gap where users can't easily see what memories exist or retrieve specific memories by ID.

## Current State
**Missing:**
- `list_memories` - List/filter memories with pagination
- `get_memory_by_id` - Already covered in FEAT-040
- Filtering by category, context_level, tags, date range, project
- Sorting capabilities
- Pagination support

**Use Cases:**
- "Show me all my Python preferences"
- "List recent memories from this week"
- "Browse all memories tagged with 'authentication'"

## Implementation Plan

### Phase 1: Data Models (Day 1, 2 hours)

**File:** `src/core/models.py`

```python
@dataclass
class ListMemoriesRequest:
    """Request to list memories with filtering and pagination."""

    # Filtering
    category: Optional[MemoryCategory] = None
    context_level: Optional[ContextLevel] = None
    scope: Optional[MemoryScope] = None
    project_name: Optional[str] = None
    tags: Optional[List[str]] = None  # ANY of these tags
    tags_all: Optional[List[str]] = None  # ALL of these tags
    min_importance: float = 0.0
    max_importance: float = 1.0
    date_from: Optional[datetime] = None  # created_at >= date_from
    date_to: Optional[datetime] = None    # created_at <= date_to

    # Sorting
    sort_by: str = "created_at"  # created_at, updated_at, importance
    sort_order: str = "desc"  # asc, desc

    # Pagination
    limit: int = 20  # Max 100
    offset: int = 0

    def validate(self):
        if not (1 <= self.limit <= 100):
            raise ValidationError("limit must be 1-100")
        if self.offset < 0:
            raise ValidationError("offset must be >= 0")
        if self.sort_by not in ["created_at", "updated_at", "importance"]:
            raise ValidationError("Invalid sort_by field")
        if self.sort_order not in ["asc", "desc"]:
            raise ValidationError("sort_order must be 'asc' or 'desc'")


@dataclass
class ListMemoriesResponse:
    """Response from list_memories."""

    memories: List[Dict[str, Any]]
    total_count: int  # Total matching memories (before pagination)
    returned_count: int  # Memories in this response
    offset: int
    limit: int
    has_more: bool  # True if more results available
```

### Phase 2: Store Implementation (Day 1-2, 6 hours)

**File:** `src/store/memory_store.py` (interface)

```python
@abstractmethod
async def list_memories(
    self,
    filters: Dict[str, Any],
    sort_by: str = "created_at",
    sort_order: str = "desc",
    limit: int = 20,
    offset: int = 0
) -> Tuple[List[MemoryUnit], int]:
    """
    List memories with filtering, sorting, and pagination.

    Returns:
        Tuple of (memories list, total count)
    """
    pass
```

**Qdrant Implementation:** `src/store/qdrant_store.py`

```python
async def list_memories(
    self,
    filters: Dict[str, Any],
    sort_by: str = "created_at",
    sort_order: str = "desc",
    limit: int = 20,
    offset: int = 0
) -> Tuple[List[MemoryUnit], int]:
    """List memories from Qdrant with filters."""

    # Build Qdrant filter conditions
    must_conditions = []

    if "category" in filters:
        must_conditions.append(
            models.FieldCondition(
                key="category",
                match=models.MatchValue(value=filters["category"].value)
            )
        )

    if "context_level" in filters:
        must_conditions.append(
            models.FieldCondition(
                key="context_level",
                match=models.MatchValue(value=filters["context_level"].value)
            )
        )

    if "project_name" in filters:
        must_conditions.append(
            models.FieldCondition(
                key="project_name",
                match=models.MatchValue(value=filters["project_name"])
            )
        )

    if "tags" in filters:  # ANY tag matches
        tag_conditions = [
            models.FieldCondition(
                key="tags",
                match=models.MatchAny(any=filters["tags"])
            )
        ]
        must_conditions.extend(tag_conditions)

    if "min_importance" in filters or "max_importance" in filters:
        must_conditions.append(
            models.FieldCondition(
                key="importance",
                range=models.Range(
                    gte=filters.get("min_importance", 0.0),
                    lte=filters.get("max_importance", 1.0)
                )
            )
        )

    # Determine collections to search
    collections = self._get_collections_for_scope(filters.get("scope"))

    all_memories = []

    for collection in collections:
        # Scroll through results (Qdrant doesn't support offset natively)
        result = self.client.scroll(
            collection_name=collection,
            scroll_filter=models.Filter(must=must_conditions) if must_conditions else None,
            limit=1000,  # Get all matching
            with_payload=True,
            with_vectors=False
        )

        points = result[0]
        for point in points:
            memory = self._point_to_memory_unit(point)
            all_memories.append(memory)

    # Filter by date range (Qdrant doesn't support datetime range well)
    if "date_from" in filters or "date_to" in filters:
        all_memories = [
            m for m in all_memories
            if (not filters.get("date_from") or m.created_at >= filters["date_from"]) and
               (not filters.get("date_to") or m.created_at <= filters["date_to"])
        ]

    # Sort
    reverse = (sort_order == "desc")
    all_memories.sort(
        key=lambda m: getattr(m, sort_by),
        reverse=reverse
    )

    # Paginate
    total_count = len(all_memories)
    paginated = all_memories[offset:offset + limit]

    return paginated, total_count
```

**SQLite Implementation:** `src/store/sqlite_store.py`

```python
async def list_memories(
    self,
    filters: Dict[str, Any],
    sort_by: str = "created_at",
    sort_order: str = "desc",
    limit: int = 20,
    offset: int = 0
) -> Tuple[List[MemoryUnit], int]:
    """List memories from SQLite with filters."""

    # Build WHERE clauses
    where_clauses = []
    params = []

    if "category" in filters:
        where_clauses.append("category = ?")
        params.append(filters["category"].value)

    if "context_level" in filters:
        where_clauses.append("context_level = ?")
        params.append(filters["context_level"].value)

    if "project_name" in filters:
        where_clauses.append("project_name = ?")
        params.append(filters["project_name"])

    if "tags" in filters:
        # JSON contains any of the tags
        tag_conditions = " OR ".join(["tags LIKE ?" for _ in filters["tags"]])
        where_clauses.append(f"({tag_conditions})")
        params.extend([f'%"{tag}"%' for tag in filters["tags"]])

    if "min_importance" in filters:
        where_clauses.append("importance >= ?")
        params.append(filters["min_importance"])

    if "max_importance" in filters:
        where_clauses.append("importance <= ?")
        params.append(filters["max_importance"])

    if "date_from" in filters:
        where_clauses.append("created_at >= ?")
        params.append(filters["date_from"].isoformat())

    if "date_to" in filters:
        where_clauses.append("created_at <= ?")
        params.append(filters["date_to"].isoformat())

    where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

    # Get total count
    count_sql = f"SELECT COUNT(*) FROM memories WHERE {where_sql}"

    # Get paginated results
    data_sql = f"""
        SELECT * FROM memories
        WHERE {where_sql}
        ORDER BY {sort_by} {sort_order.upper()}
        LIMIT ? OFFSET ?
    """

    async with aiosqlite.connect(self.db_path) as db:
        db.row_factory = aiosqlite.Row

        # Get count
        async with db.execute(count_sql, params) as cursor:
            row = await cursor.fetchone()
            total_count = row[0]

        # Get data
        data_params = params + [limit, offset]
        async with db.execute(data_sql, data_params) as cursor:
            rows = await cursor.fetchall()
            memories = [self._row_to_memory_unit(dict(row)) for row in rows]

    return memories, total_count
```

### Phase 3: MCP Tool (Day 2, 3 hours)

**File:** `src/core/server.py`

```python
async def list_memories(
    self,
    category: Optional[str] = None,
    context_level: Optional[str] = None,
    scope: Optional[str] = None,
    project_name: Optional[str] = None,
    tags: Optional[List[str]] = None,
    min_importance: float = 0.0,
    max_importance: float = 1.0,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    limit: int = 20,
    offset: int = 0
) -> Dict[str, Any]:
    """
    List memories with filtering, sorting, and pagination.

    Args:
        category: Filter by category (optional)
        context_level: Filter by context level (optional)
        scope: Filter by scope (global/project) (optional)
        project_name: Filter by project (optional)
        tags: Filter by tags - matches ANY tag (optional)
        min_importance: Minimum importance (default 0.0)
        max_importance: Maximum importance (default 1.0)
        date_from: Filter by created_at >= date (ISO format) (optional)
        date_to: Filter by created_at <= date (ISO format) (optional)
        sort_by: Sort field (created_at, updated_at, importance)
        sort_order: Sort order (asc, desc)
        limit: Max results to return (1-100, default 20)
        offset: Number of results to skip (default 0)

    Returns:
        {
            "memories": List[memory dict],
            "total_count": int,
            "returned_count": int,
            "offset": int,
            "limit": int,
            "has_more": bool
        }
    """
    # Build filters dict
    filters = {}

    if category:
        filters["category"] = MemoryCategory(category)
    if context_level:
        filters["context_level"] = ContextLevel(context_level)
    if scope:
        filters["scope"] = MemoryScope(scope)
    if project_name:
        filters["project_name"] = project_name
    if tags:
        filters["tags"] = tags

    filters["min_importance"] = min_importance
    filters["max_importance"] = max_importance

    if date_from:
        filters["date_from"] = datetime.fromisoformat(date_from)
    if date_to:
        filters["date_to"] = datetime.fromisoformat(date_to)

    # Validate
    if not (1 <= limit <= 100):
        raise ValidationError("limit must be 1-100")
    if offset < 0:
        raise ValidationError("offset must be >= 0")
    if sort_by not in ["created_at", "updated_at", "importance"]:
        raise ValidationError("Invalid sort_by field")
    if sort_order not in ["asc", "desc"]:
        raise ValidationError("sort_order must be 'asc' or 'desc'")

    # Query store
    memories, total_count = await self.store.list_memories(
        filters=filters,
        sort_by=sort_by,
        sort_order=sort_order,
        limit=limit,
        offset=offset
    )

    # Convert to dicts
    memory_dicts = [
        {
            "memory_id": m.memory_id,
            "content": m.content,
            "category": m.category.value,
            "context_level": m.context_level.value,
            "importance": m.importance,
            "tags": m.tags,
            "metadata": m.metadata,
            "scope": m.scope.value,
            "project_name": m.project_name,
            "created_at": m.created_at.isoformat(),
            "updated_at": m.updated_at.isoformat(),
        }
        for m in memories
    ]

    return {
        "memories": memory_dicts,
        "total_count": total_count,
        "returned_count": len(memory_dicts),
        "offset": offset,
        "limit": limit,
        "has_more": (offset + len(memory_dicts)) < total_count
    }
```

### Phase 4: Testing (Day 3, 4 hours)

**File:** `tests/unit/test_list_memories.py` (~20 tests)

Test scenarios:
- Filter by each field individually
- Multiple filters combined
- Tag filtering (ANY vs ALL)
- Date range filtering
- Sorting (each field, both directions)
- Pagination (offset, limit, has_more)
- Edge cases (empty results, offset beyond total)
- Both backends (Qdrant, SQLite)

### Phase 5: Documentation (Day 3, 2 hours)

Update API.md and USAGE.md with list_memories documentation and examples.

## Files to Create
1. `tests/unit/test_list_memories.py` (~350 lines)

## Files to Modify
1. `src/core/models.py` - Add ListMemoriesRequest, ListMemoriesResponse
2. `src/store/memory_store.py` - Add list_memories interface
3. `src/store/qdrant_store.py` - Implement list_memories
4. `src/store/sqlite_store.py` - Implement list_memories
5. `src/core/server.py` - Add list_memories MCP tool
6. `src/mcp_server.py` - Register list_memories
7. `docs/API.md` - Document list_memories
8. `docs/USAGE.md` - Add examples

## Success Criteria
- [ ] list_memories MCP tool working with all filters
- [ ] Pagination working correctly
- [ ] Sorting working for all fields
- [ ] Both backends supported
- [ ] 20+ tests passing
- [ ] Documentation complete

## Performance Considerations
- Qdrant: May need to scroll large result sets (optimize with limit)
- SQLite: Indexed queries on category, context_level, created_at
- Consider caching for repeated queries (future optimization)
