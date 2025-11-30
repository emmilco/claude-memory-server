# AUDIT-003 Part 17: Output Contract Verification (2025-11-30)

**Investigation Scope:** Do outputs match documented contracts? Check return types vs type hints, error response consistency, success response fields, pagination correctness, metadata completeness, and different code path output shapes.

**Files Analyzed:**
- `src/services/code_indexing_service.py` - Code search/indexing outputs
- `src/services/memory_service.py` - Memory CRUD outputs
- `src/services/query_service.py` - Query expansion/session outputs
- `src/services/health_service.py` - Health/metrics outputs
- `src/services/analytics_service.py` - Analytics outputs
- `src/core/server.py` - MCP tool response formatting
- `src/store/qdrant_store.py` - Storage layer returns

## VERIFIED CORRECT Patterns

**Pagination Contract Consistency:**
- All paginated endpoints correctly return `has_more` boolean
- `list_memories()`: Returns `{"memories": [], "total_count": int, "returned_count": int, "offset": int, "limit": int, "has_more": bool}`
- `get_indexed_files()`: Store returns `{"files": [], "total": int, "limit": int, "offset": int}`, service adds `has_more`
- `list_indexed_units()`: Store returns `{"units": [], "total": int, "limit": int, "offset": int}`, service adds `has_more`
- `has_more` calculation is consistent: `(offset + len(results)) < total`

**Timestamp Format Consistency:**
- All timestamps use `.isoformat()` for ISO 8601 format
- Optional timestamps properly handle None: `memory.last_accessed.isoformat() if memory.last_accessed else None`
- Consistent across `created_at`, `updated_at`, `last_accessed` fields

**Success Response Consistency:**
- All methods consistently return `{"status": "success", ...}` for successful operations
- Error paths consistently return `{"status": "not_found", ...}` or `{"status": "error", ...}`
- Health checks return `{"status": "disabled", ...}` when feature not configured

**Empty Result Handling:**
- Search methods return empty lists (not None): `"results": []`, `"total_found": 0`
- Empty lists properly initialized before loops
- No confusion between None and empty list

**Type Hint Compliance:**
- All service methods properly typed: `async def method(...) -> Dict[str, Any]:`
- Store layer correctly returns `Tuple[List[MemoryUnit], int]` for list operations
- Service layer correctly transforms tuples to dicts for API consumers

## MEDIUM Priority Findings

### BUG-250: Inconsistent "status" Field in Error vs Success Responses
- **Location:** All services - error returns vs success returns
- **Problem:** Success responses include `"status": "success"` but some error paths return dict without status field, relying on exception propagation instead
- **Evidence:**
  ```python
  # memory_service.py:565 - has status
  return {"status": "success", "memory_id": memory_id}
  # memory_service.py:567 - has status
  return {"status": "not_found", "memory_id": memory_id}
  # BUT query_service.py raises StorageError instead of returning error dict
  ```
- **Impact:** MCP layer consumers can't consistently check response["status"] to determine success/failure
- **Expected:** All methods should return dicts with status field, or consistently raise exceptions (not mix both patterns)
- **Severity:** MEDIUM (inconsistent but functional)

### BUG-251: Export Memories Returns Different Keys for File vs Content Mode
- **Location:** `src/services/memory_service.py:1164-1176` (export_memories)
- **Problem:** When `output_path` provided returns `{"status": "success", "file_path": str, "format": str, "count": int}`, but when `output_path=None` returns `{"status": "success", "content": str, "format": str, "count": int}` - different top-level keys
- **Evidence:**
  ```python
  if output_path:
      return {"status": "success", "file_path": str(output_file), "format": format, "count": total_count}
  else:
      return {"status": "success", "content": content, "format": format, "count": total_count}
  ```
- **Impact:** Consumers must check which key exists (file_path vs content) to handle both modes
- **Expected:** Could use Optional fields with both always present: `{"file_path": str | None, "content": str | None}` or add `"output_mode": "file"|"string"` discriminator
- **Severity:** MEDIUM (forces consumers to check key existence)

### BUG-252: Import Memories Returns "status": "partial" Without Clear Definition
- **Location:** `src/services/memory_service.py:1375` (import_memories)
- **Problem:** Returns `"status": "success" if len(errors) == 0 else "partial"` but "partial" isn't clearly defined in docstring contract - does it mean some succeeded? All failed? Need to check errors array?
- **Evidence:**
  ```python
  return {
      "status": "success" if len(errors) == 0 else "partial",
      "created": created_count,
      "updated": updated_count,
      "skipped": skipped_count,
      "errors": errors,
      "total_processed": len(memories)
  }
  ```
- **Impact:** Consumers must parse multiple fields to determine if import succeeded, partially succeeded, or completely failed
- **Expected:** Docstring should document: "status: 'success' if all memories imported without errors, 'partial' if some succeeded and some failed (check errors array for details)"
- **Severity:** MEDIUM (ambiguous contract)

### REF-200: get_memory_by_id Returns Nested "memory" Dict vs list_memories Returns Flat Array
- **Location:** `src/services/memory_service.py:592-609` (get_by_id) vs `816-842` (list_memories)
- **Problem:** `get_memory_by_id` returns `{"status": "success", "memory": {...}}` with single nested object, but `list_memories` returns `{"memories": [{...}, {...}], ...}` with flat array of objects - inconsistent nesting depth
- **Evidence:**
  ```python
  # get_memory_by_id returns:
  {"status": "success", "memory": {"id": ..., "content": ..., ...}}

  # list_memories returns:
  {"memories": [{"memory_id": ..., "content": ..., ...}, ...], ...}
  ```
- **Impact:** Consumers can't use same code path to handle single vs multiple memories (different access pattern: result["memory"] vs result["memories"][0])
- **Expected:** Consider returning `{"memories": [single_memory]}` for consistency, or document this intentional difference
- **Severity:** MEDIUM (inconsistent shape)

### REF-201: Duplicate "id" and "memory_id" Fields in get_memory_by_id Response
- **Location:** `src/services/memory_service.py:595-596`
- **Problem:** Response includes both `"id": memory.id` and `"memory_id": memory.id` with identical values
- **Evidence:**
  ```python
  "memory": {
      "id": memory.id,
      "memory_id": memory.id,  # duplicate
      "content": memory.content,
      ...
  }
  ```
- **Impact:** Wastes bytes, confuses consumers about which field is canonical
- **Expected:** Use only `"memory_id"` for consistency with other endpoints, or document why both exist
- **Severity:** LOW (wasteful but harmless)

## LOW Priority Findings

### REF-202: search_code Empty Query Returns Success Instead of Validation Error
- **Location:** `src/services/code_indexing_service.py:234-248`
- **Problem:** Empty query `if not query or not query.strip()` returns `{"status": "success", "results": [], "total_found": 0, ...}` with success status instead of raising ValidationError
- **Evidence:**
  ```python
  if not query or not query.strip():
      return {"status": "success", "results": [], ...}  # Should this be an error?
  ```
- **Impact:** Consumers can't distinguish "search found nothing" from "invalid empty query"
- **Expected:** Either raise `ValidationError("query cannot be empty")` OR document that empty query is valid and returns empty results
- **Severity:** LOW (debatable design choice)

### REF-203: health_service Returns "status": "disabled" vs Other Services Raise StorageError
- **Location:** `src/services/health_service.py:115-118`, `198-202`, etc.
- **Problem:** Health service returns `{"status": "disabled", "message": "..."}` when optional components not configured, but other services raise `StorageError("... is disabled")` in same scenario
- **Evidence:**
  ```python
  # health_service.py - returns dict
  if not self.metrics_collector:
      return {"status": "disabled", "message": "Metrics collector not configured"}

  # query_service.py - raises exception
  if not self.conversation_tracker:
      raise StorageError("Conversation tracking is disabled")
  ```
- **Impact:** Inconsistent error handling pattern across services
- **Expected:** Either all services return error dicts, or all raise exceptions - pick one pattern
- **Severity:** LOW (inconsistent but functional)

### REF-204: update_memory Returns "status": "updated" vs Other Methods Use "status": "success"
- **Location:** `src/services/memory_service.py:715-720`
- **Problem:** `update_memory` returns `{"status": "updated", ...}` but all other write operations return `{"status": "success", ...}` - special case for update
- **Evidence:**
  ```python
  return {
      "status": "updated",  # Why not "success"?
      "updated_fields": updated_fields,
      "embedding_regenerated": embedding_regenerated,
      "updated_at": datetime.now(UTC).isoformat()
  }
  ```
- **Impact:** Consumers checking `response["status"] == "success"` will miss updates
- **Expected:** Use "success" for consistency, include "operation": "updated" if caller needs to distinguish
- **Severity:** LOW (inconsistent but documented)

### REF-205: Optional Metadata Fields Use "or {}" vs "or []" Inconsistently
- **Location:** Throughout services
- **Problem:** Some fields use `memory.tags or []` to default None to empty list, others use `memory.metadata or {}` to default to empty dict - inconsistent None handling pattern
- **Evidence:**
  ```python
  "tags": memory.tags or [],           # defaults None -> []
  "metadata": memory.metadata or {},   # defaults None -> {}
  ```
- **Impact:** No functional issue, but could simplify by using same pattern (default in model class instead of at every access point)
- **Expected:** Move defaults to MemoryUnit dataclass: `tags: List[str] = field(default_factory=list)`
- **Severity:** LOW (works but verbose)

## Summary Statistics

**Output Contract Issues Found:**
- CRITICAL: 0 issues
- MEDIUM: 5 issues (BUG-250 through REF-201)
- LOW: 5 issues (REF-202 through REF-205)

**Contract Verification Checklist:**
- ✅ All methods return declared types (Dict[str, Any])
- ⚠️ Error responses have mostly consistent structure (BUG-250 - some inconsistency)
- ✅ Success responses include all documented fields
- ✅ Pagination cursors work correctly (has_more, offset, limit)
- ✅ Total counts are accurate
- ✅ Timestamps in consistent ISO format
- ✅ Optional fields properly nullable (None vs [] vs {})

**Key Findings:**
1. **Pagination works correctly** - all paginated endpoints properly calculate `has_more` and return consistent structure
2. **Timestamp formatting is consistent** - all use `.isoformat()` and handle None properly
3. **Empty results handled well** - no None vs [] confusion
4. **Main issue is status field inconsistency** - some paths return error dicts, others raise exceptions
5. **Minor shape inconsistencies** - get_by_id vs list, export file vs content modes

**Recommended Actions:**
1. **BUG-250 (MEDIUM):** Standardize on exception-based error handling OR dict-based error returns across all services
2. **BUG-251 (MEDIUM):** Add `output_mode` discriminator to export_memories or unify response shape
3. **BUG-252 (MEDIUM):** Document "partial" status meaning clearly in import_memories docstring
4. **REF-200 (MEDIUM):** Consider unifying get_by_id to return `{"memories": [single]}` for consistency
5. **REF-204 (LOW):** Change update_memory to return "status": "success" like other write operations
