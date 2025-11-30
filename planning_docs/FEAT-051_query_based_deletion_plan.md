# FEAT-051: Query-based Deletion for Qdrant

**Status:** In Progress
**Created:** 2025-11-29
**Location:** `src/core/server.py`, `src/store/qdrant_store.py`

## Overview

Implement deletion by query filters instead of individual memory IDs. This allows users to efficiently clear entire project indexes, delete memories by category, date range, tags, etc.

## Current State

- **Individual deletion:** `delete_memory(memory_id)` exists - deletes one memory at a time
- **Bulk operations:** `bulk_operations.py` provides `BulkDeleteManager` with filters
- **Qdrant support:** `delete_code_units_by_project()` shows Qdrant supports filter-based deletion
- **Gap:** No MCP tool to expose query-based deletion to users

## Requirements

1. **New method in QdrantStore:** `delete_by_filter()` to delete memories matching filter criteria
2. **New MCP tool in server.py:** `delete_memories_by_query()` to expose functionality
3. **Support filters:**
   - `project_name` - Clear entire project index
   - `category` - Delete by memory category (preference, fact, event, workflow, context, code)
   - `tags` - Delete by tags (match any)
   - `date_from` / `date_to` - Delete by date range
   - `min_importance` / `max_importance` - Delete by importance threshold
   - `lifecycle_state` - Delete by lifecycle state
4. **Safety features:**
   - Dry-run preview showing what would be deleted
   - Count confirmation for large deletions
   - Maximum deletion limit (1000 memories)
5. **Return statistics:**
   - Number of memories deleted
   - Breakdown by category, project, lifecycle state
   - Storage freed

## Implementation Plan

### 1. Add `delete_by_filter()` to QdrantStore

```python
async def delete_by_filter(
    self,
    filters: SearchFilters,
    max_count: int = 1000
) -> int:
    """
    Delete memories matching filter criteria.

    Args:
        filters: Filter criteria (category, project, tags, dates, etc.)
        max_count: Maximum memories to delete (safety limit)

    Returns:
        Number of memories deleted
    """
```

**Implementation:**
- Build Qdrant `Filter` from `SearchFilters`
- Count matching memories with `scroll()`
- Apply `max_count` limit
- Delete using `client.delete(points_selector=filter_conditions)`
- Return count of deleted memories

### 2. Add `delete_memories_by_query()` MCP tool to server.py

```python
async def delete_memories_by_query(
    self,
    category: Optional[str] = None,
    project_name: Optional[str] = None,
    tags: Optional[List[str]] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    min_importance: float = 0.0,
    max_importance: float = 1.0,
    lifecycle_state: Optional[str] = None,
    dry_run: bool = True,
    max_count: int = 1000
) -> Dict[str, Any]:
    """
    Delete memories matching query filters.

    **PROACTIVE USE:**
    - Clear entire project indexes when project is archived/deleted
    - Bulk delete low-importance memories
    - Clean up old memories by date range
    - Remove memories by category or tags

    Args:
        category: Filter by category
        project_name: Filter by project (use to clear project index)
        tags: Filter by tags (match any)
        date_from: Delete memories created after this date
        date_to: Delete memories created before this date
        min_importance: Minimum importance threshold
        max_importance: Maximum importance threshold
        lifecycle_state: Filter by lifecycle state
        dry_run: If True, preview only (default: True for safety)
        max_count: Maximum memories to delete (1-1000, default: 1000)

    Returns:
        Dict with:
        - preview: True if dry_run, False if executed
        - total_matches: Number of matching memories
        - deleted_count: Number actually deleted (0 if dry_run)
        - breakdown_by_category: Count by category
        - breakdown_by_project: Count by project
        - breakdown_by_lifecycle: Count by lifecycle state
        - warnings: List of warnings
        - requires_confirmation: Whether confirmation needed
    """
```

**Implementation:**
- Build `SearchFilters` from parameters
- If `dry_run=True`: Use `BulkDeleteManager.preview_deletion()`
- If `dry_run=False`: Use `store.delete_by_filter()` and return statistics
- Include safety checks and warnings

### 3. Register MCP tool

Add to `src/mcp_server.py`:
```python
@mcp.tool()
async def delete_memories_by_query(...) -> list[types.TextContent]:
    """Delete memories matching query filters."""
    result = await server.delete_memories_by_query(...)
    return [types.TextContent(type="text", text=json.dumps(result, indent=2))]
```

### 4. Tests

Create `tests/unit/test_query_based_deletion.py`:
- Test `delete_by_filter()` with various filters
- Test dry-run vs actual deletion
- Test safety limits (max_count)
- Test breakdown statistics
- Test edge cases (no matches, empty filters)

Estimated: 15-20 tests

## Safety Considerations

1. **Default dry_run=True:** Users must explicitly set `dry_run=False` to delete
2. **Max count limit:** Hard limit of 1000 memories per operation
3. **Confirmation threshold:** Warn if deleting >10 memories
4. **Read-only mode check:** Respect `config.advanced.read_only_mode`
5. **Preview before delete:** Always show what will be deleted

## Examples

### Clear entire project index
```python
result = await delete_memories_by_query(
    project_name="my-project",
    category="code",
    dry_run=False
)
# Deletes all code memories for "my-project"
```

### Delete old low-importance memories
```python
result = await delete_memories_by_query(
    date_to="2024-01-01",
    max_importance=0.3,
    dry_run=False
)
# Deletes memories created before 2024-01-01 with importance ≤0.3
```

### Preview deletion by tags
```python
result = await delete_memories_by_query(
    tags=["deprecated", "outdated"],
    dry_run=True  # Preview only
)
# Shows what would be deleted without actually deleting
```

## Success Criteria

- ✅ `delete_by_filter()` added to QdrantStore
- ✅ `delete_memories_by_query()` MCP tool added
- ✅ MCP tool registered in mcp_server.py
- ✅ Tests pass (15-20 tests)
- ✅ Safety features working (dry-run, max_count, warnings)
- ✅ CHANGELOG.md updated
- ✅ All existing tests still pass

## Timeline

**Estimated:** 2-3 hours
- Implementation: 1-1.5 hours
- Testing: 1 hour
- Documentation: 30 minutes
