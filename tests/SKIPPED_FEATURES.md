# Skipped Integration Tests - Feature Status

This document tracks integration tests that are currently skipped and explains why.

## Summary

| Test File | Reason | Status | Action Needed |
|-----------|--------|--------|---------------|
| `test_call_graph_tools.py` | FEAT-059 not implemented | ⏸️ Pending | Wait for FEAT-059 implementation |
| `test_pattern_search_integration.py` | FEAT-058 partially implemented | ⚠️ Fixable | Add pattern/pattern_mode to search_code() |
| `test_suggest_queries_integration.py` | FEAT-057 not implemented | ⏸️ Pending | Wait for FEAT-057 implementation |
| `test_search_code_ux_integration.py` | FEAT-057 features not implemented | ⏸️ Pending | Wait for FEAT-057 implementation |
| `test_concurrent_operations.py` | Flaky under parallel execution | ⚠️ Fixable | Apply UUID isolation (see below) |

---

## 1. `test_call_graph_tools.py` - FEAT-059 Call Graph Tools

**Status:** ⏸️ **Unimplemented Feature**

### What's Missing

The following 6 MCP tool methods are not implemented on `MemoryRAGServer`:

1. `find_callers()` - Find all functions calling a target function
2. `find_callees()` - Find all functions called by a source function
3. `get_call_chain()` - Find call chain paths between two functions
4. `find_implementations()` - Find all implementations of an interface/abstract class
5. `find_dependencies()` - Find all files that a file depends on (imports)
6. `find_dependents()` - Find all files that depend on a file (reverse dependencies)

### Infrastructure Status

✅ **Backend exists:** `QdrantCallGraphStore` is implemented
✅ **Data model exists:** `CallGraph`, `FunctionNode`, `CallSite`, `InterfaceImplementation`
❌ **MCP methods missing:** None of the 6 methods exist in `src/core/server.py`

### Test File Details

- **File:** `tests/integration/test_call_graph_tools.py`
- **Tests:** 19 integration tests covering all 6 tools
- **Skip reason:** "FEAT-059 MCP tool methods not yet implemented on MemoryRAGServer"

### Action Required

Wait for FEAT-059 implementation. The tests are ready to be enabled once the methods are added to `MemoryRAGServer`.

**Estimated effort to enable:** Remove skip marker at line 19

---

## 2. `test_pattern_search_integration.py` - FEAT-058 Pattern Search

**Status:** ⚠️ **Partially Implemented - Fixable**

### What's Missing

The `PatternMatcher` class is fully implemented in `src/search/pattern_matcher.py`, but the `search_code()` method does NOT accept `pattern` and `pattern_mode` parameters.

**Current signature:**
```python
async def search_code(
    self,
    query: str,
    project_name: Optional[str] = None,
    limit: int = 5,
    file_pattern: Optional[str] = None,
    language: Optional[str] = None,
    search_mode: str = "semantic",
    min_complexity: Optional[int] = None,
    max_complexity: Optional[int] = None,
    has_duplicates: Optional[bool] = None,
    long_functions: Optional[bool] = None,
    maintainability_min: Optional[int] = None,
    include_quality_metrics: bool = True,
) -> Dict[str, Any]:
```

**Missing parameters:**
```python
pattern: Optional[str] = None,         # ❌ NOT present
pattern_mode: str = "filter",          # ❌ NOT present
```

### Infrastructure Status

✅ **PatternMatcher exists:** `src/search/pattern_matcher.py` fully implemented
✅ **Pattern presets exist:** 14 presets (bare_except, TODO_comments, security_keywords, etc.)
✅ **Methods implemented:** `match()`, `find_matches()`, `get_match_count()`, `calculate_pattern_score()`
❌ **Integration missing:** `search_code()` does not use PatternMatcher

### Test File Details

- **File:** `tests/integration/test_pattern_search_integration.py`
- **Tests:** 15 integration tests covering filter, boost, and require modes
- **Skip reason:** "FEAT-058 integration tests have API mismatches - need rewriting"
- **Actual issue:** Tests written before implementation, expecting parameters that don't exist

### Action Required

**Option 1: Complete FEAT-058 (recommended)**
Add `pattern` and `pattern_mode` parameters to `search_code()` method as designed in `planning_docs/FEAT-058_pattern_detection_plan.md`

**Option 2: Rewrite tests**
Modify tests to use the existing `PatternMatcher` directly (not via MCP search_code tool)

**Estimated effort:**
- Option 1: 2-4 hours (implement integration per plan)
- Option 2: 1-2 hours (refactor tests)

---

## 3. `test_suggest_queries_integration.py` - FEAT-057 Query Suggestions

**Status:** ⏸️ **Unimplemented Feature**

### What's Missing

The `suggest_queries()` MCP method is not implemented on `MemoryRAGServer`.

**Expected signature:**
```python
async def suggest_queries(
    self,
    intent: Optional[str] = None,           # implementation, debugging, learning, etc.
    project_name: Optional[str] = None,
    context: Optional[str] = None,
    max_suggestions: int = 8,
) -> Dict[str, Any]:
```

### Purpose

Help users overcome "query formulation paralysis" by suggesting effective queries based on:
- User's current intent (debugging, implementation, learning)
- Project context (indexed codebase)
- Conversation context

### Test File Details

- **File:** `tests/integration/test_suggest_queries_integration.py`
- **Tests:** 7 integration tests
- **Skip reason:** "FEAT-057 suggest_queries() not implemented - planned for v4.1"

### Action Required

Wait for FEAT-057 implementation (planned for v4.1).

---

## 4. `test_search_code_ux_integration.py` - FEAT-057 UX Enhancements

**Status:** ⏸️ **Unimplemented Features**

### What's Missing

Multiple UX enhancement features planned for v4.1:

1. **Facets** - Aggregate results by language, unit_type, files, directories
2. **Summary** - Natural language summary of search results
3. **Did you mean** - Spelling suggestions for queries with poor results
4. **Refinement hints** - Suggestions to narrow/broaden search

### Current State

`search_code()` returns basic fields but lacks enhanced UX features:

**Current fields:**
- `status`, `results`, `total_found`, `query`, `project_name`, `search_mode`
- `query_time_ms`, `quality`, `confidence`, `suggestions`, `interpretation`

**Missing fields:**
- `facets` - { languages: {python: 10, js: 5}, unit_types: {function: 8}, ... }
- `summary` - "Found 15 functions across 3 files..."
- `did_you_mean` - ["authenticate", "authorization"] for typo "athenticate"
- `refinement_hints` - ["Too many results? Try adding language filter"]

### Test File Details

- **File:** `tests/integration/test_search_code_ux_integration.py`
- **Tests:** 8 integration tests (7 skipped for v4.1 features, 1 passing for backward compatibility)
- **Skip reason:** "FEAT-057 facets/summary/did_you_mean/refinement_hints not implemented - planned for v4.1"

### Action Required

Wait for FEAT-057 implementation (planned for v4.1).

---

## 5. `test_concurrent_operations.py` - Flaky Tests

**Status:** ⚠️ **Fixable with UUID Isolation**

### Problem

Tests are flaky under parallel execution due to:
1. **Shared Qdrant collection names** - Multiple tests writing to same collection
2. **Race conditions** - Concurrent writes/reads interfering with each other
3. **Resource contention** - High concurrency (50-100 operations) overwhelming Qdrant

### Test File Details

- **File:** `tests/integration/test_concurrent_operations.py`
- **Tests:** 12 concurrent operation tests
- **Skip reasons:**
  - Line 18: "Concurrent operation tests are flaky under parallel execution - need dedicated test environment"
  - Line 59: "Flaky test - race condition in parallel execution (passes individually)"

### Why Flaky

1. **test_concurrent_store_operations** - Multiple tests storing to same collection simultaneously
2. **Shared fixtures** - Using session-scoped Qdrant client but not unique collections
3. **High load** - Tests like `test_high_concurrency_store` with 50 concurrent operations

### Solution: UUID Isolation (Like Other Agents)

Apply the same UUID-based isolation strategy used by other test agent fixes:

**Before:**
```python
@pytest.fixture
def config(unique_qdrant_collection):
    return ServerConfig(
        storage_backend="qdrant",
        qdrant_url="http://localhost:6333",
        qdrant_collection_name=unique_qdrant_collection,  # ✅ Already using this!
    )
```

**Issue:** The fixture is already there, but tests still flaky. Why?

**Root cause:** Tests are designed to test concurrency *intentionally*, and actual race conditions between parallel pytest workers (not within a single test).

### Action Required

**Option 1: Keep skipped (recommended)**
These tests are testing concurrency behavior and *should* run in isolation. They're appropriately skipped during parallel test runs.

**Option 2: Run in dedicated CI job**
Create a separate CI job that runs these tests sequentially:
```bash
pytest tests/integration/test_concurrent_operations.py -v  # No -n auto
```

**Option 3: More aggressive isolation**
Use completely separate Qdrant instances (different ports) per test.

**Estimated effort:**
- Option 1: 0 hours (keep as-is)
- Option 2: 1 hour (add CI job)
- Option 3: 4-6 hours (complex)

### Note

One test at line 59 (`test_concurrent_store_operations`) has an additional skip marker because it's flaky even in the skipped file. This suggests a real concurrency bug that should be investigated separately.

---

## Recommendations

### Immediate Actions

1. **FEAT-058 Pattern Search** - Complete integration (2-4 hours)
   - Add `pattern` and `pattern_mode` to `search_code()`
   - Enable 15 integration tests
   - High value: Eliminates 60% of grep usage

2. **Concurrent Operations** - Keep skipped
   - Tests are appropriately skipped for parallel execution
   - Consider dedicated CI job for sequential run

### Future Work (v4.1)

3. **FEAT-057 Query Suggestions + UX** - Wait for v4.1
   - 7 tests for suggest_queries
   - 7 tests for UX enhancements (facets, summary, etc.)

4. **FEAT-059 Call Graph Tools** - Wait for implementation
   - 19 tests ready to enable
   - Backend infrastructure complete, just need MCP methods

---

## Test Counts

| Category | Total Tests | Skipped | Reason |
|----------|-------------|---------|--------|
| Call Graph (FEAT-059) | 19 | 19 | Feature not implemented |
| Pattern Search (FEAT-058) | 15 | 15 | API integration incomplete |
| Query Suggestions (FEAT-057) | 7 | 7 | Feature not implemented |
| UX Enhancements (FEAT-057) | 7 | 7 | Feature not implemented |
| Concurrent Operations | 12 | 12 | Flaky under parallel execution |
| **Total** | **60** | **60** | |

---

## Next Steps

1. ✅ Document created (this file)
2. ⬜ Complete FEAT-058 integration (2-4 hours)
3. ⬜ Add CI job for concurrent tests (optional, 1 hour)
4. ⬜ Wait for v4.1 features (FEAT-057, FEAT-059)
5. ⬜ Remove skip markers as features are implemented

---

**Last Updated:** 2025-11-25
**Agent:** Test Engineer Agent 16
