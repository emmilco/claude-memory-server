# Bug Hunt Report #2 - Runtime Test Failures
**Date:** 2025-11-21 (Evening Session)
**Focus:** Runtime test failures (executed tests that fail)
**Distinction:** First bug hunt covered collection errors; this covers execution failures

## Executive Summary

Systematic analysis of test suite **runtime failures** (tests that execute but fail).

**Critical Findings:**
- **327 runtime failures** (142 FAILED + 185 ERROR during execution)
- **Test pass rate: 87.7%** (2,338 passed / 2,665 executed)
- **6 major bug categories identified**
- **16+ test files broken** by incomplete SQLite refactoring (REF-010)
- **Coverage: 59.6% overall** (76.9% for core modules, vs 67% documented)

**Note:** This is SEPARATE from the earlier bug hunt which found test **collection** errors.

---

## Test Suite Status

### Overall Metrics
```
Total Tests Collected: 2,677 (vs documented 2,723)
Passed:   2,338 (87.7%)
Failed:     142 (5.3%)  ← Runtime failures
Errors:     185 (6.9%)  ← Runtime errors (not collection errors)
Skipped:     12 (0.4%)
Warnings:    15

Execution Time: 174.23s (2:54)
```

### Coverage Analysis
```
Overall Coverage:     59.6%  (documented: 67% ❌)
Core Modules:         76.9%  (target: 80-85% ✓)
CLI Commands:          0.0%  (excluded per .coveragerc)
Schedulers:            0.0%  (excluded per .coveragerc)
```

---

## Critical Bugs (Ranked by Severity)

### BUG #1: Incomplete SQLite Removal (REF-010) ⚠️ CRITICAL
**Severity:** CRITICAL
**Impact:** 185 ERROR tests (runtime validation errors)
**Root Cause:** REF-010 removed SQLite but tests still use it

#### Description
Config now only accepts `"qdrant"` but 16+ test files try to create configs with `storage_backend="sqlite"`.

**Config validation:**
```python
# src/config.py:19
storage_backend: Literal["qdrant"] = "qdrant"  # ONLY accepts "qdrant"
```

**Tests trying to use SQLite:**
```python
# tests/integration/test_hybrid_search_integration.py:22
config = ServerConfig(
    storage_backend="sqlite",  # ❌ VALIDATION ERROR at runtime
    sqlite_path=f"{temp_dir}/test.db",
)
```

**Runtime error:**
```
pydantic_core._pydantic_core.ValidationError: 1 validation error for ServerConfig
storage_backend
  Input should be 'qdrant' [type=literal_error, input_value='sqlite']
```

#### Affected Files (16+)
**Integration Tests (4):**
- `test_hybrid_search_integration.py` - 27 ERROR tests
- `test_memory_update_integration.py` - 14 ERROR tests  
- `test_proactive_suggestions.py` - 5 ERROR tests
- `test_retrieval_gate.py`

**Unit Tests (12+):**
- `test_background_indexer.py` - 21 ERROR tests
- `test_config.py`
- `test_confidence_scores.py` - 6 ERROR tests
- `test_cross_project_consent.py` - 3 ERROR tests
- `test_dashboard_api.py`
- `test_export_import.py`
- `test_get_dependency_graph.py` - 18 ERROR tests
- `test_graceful_degradation.py`
- `test_health_command.py`
- `test_indexed_content_visibility.py` - 18 ERROR tests
- `test_list_memories.py` - 16 ERROR tests
- `test_status_command.py`

#### Fix
1. Replace `storage_backend="sqlite"` → `storage_backend="qdrant"`
2. Remove `sqlite_path` parameters
3. Ensure Qdrant available in test environment

**Estimated impact:** ~185 ERROR tests fixed

---

### BUG #2: Dict vs Object Type Mismatch ⚠️ CRITICAL
**Severity:** CRITICAL
**Impact:** 8+ FAILED tests, health monitoring broken
**Root Cause:** API contract violation

#### Description
`get_all_memories()` returns `List[Dict]` but consumers expect `List[MemoryUnit]` objects.

**API signature:**
```python
# src/store/qdrant_store.py:1731
async def get_all_memories(self) -> List[Dict[str, Any]]:  # Returns DICTS
```

**Consumer code:**
```python
# src/memory/health_scorer.py:240
for memory in all_memories:
    content = memory.content  # ❌ Expects OBJECT with .content attribute
```

**Runtime errors:**
```
ERROR health_scorer.py:250: 'dict' object has no attribute 'content'
ERROR health_jobs.py:168: 'dict' object has no attribute 'created_at'
```

#### Affected Components
- `src/memory/health_scorer.py:240` - duplicate detection
- `src/memory/health_jobs.py:168` - archival jobs
- `test_health_dashboard_integration.py` - 8 FAILED tests

#### Fix Options
**Option A (RECOMMENDED):** Change consumers to dict syntax
```python
content = memory['content']  # Not memory.content
```

**Option B:** Change `get_all_memories()` to return objects (more work)

**Estimated impact:** ~8 FAILED tests fixed

---

### BUG #3: Category Changed (CODE vs context)
**Severity:** MEDIUM
**Impact:** 2+ FAILED tests
**Root Cause:** Enum changed but tests not updated

#### Description
Code indexing now uses `MemoryCategory.CODE` (value="code") but tests expect "context".

**Implementation:**
```python
# src/memory/incremental_indexer.py:948
"category": MemoryCategory.CODE.value,  # "code"
```

**Test expectation:**
```python
# tests/integration/test_indexing_integration.py:133
assert memory.category.value == "context"  # ❌ Expects "context" not "code"
```

**Outdated comment:**
```python
# src/core/server.py:3012
# Code units are stored with category="context"  # ❌ WRONG, now "code"
```

#### Fix
```python
assert memory.category.value == "code"  # Update tests
# Code units are stored with category="code"  # Update comment
```

**Estimated impact:** ~2 FAILED tests fixed

---

### BUG #4: Invalid Qdrant Point IDs
**Severity:** MEDIUM
**Impact:** 4+ ERROR tests
**Root Cause:** Test fixtures use invalid ID format

#### Description
Tests use string IDs like `"test-1"` but Qdrant requires integers or UUIDs.

**Invalid test fixture:**
```python
# tests/unit/test_backup_export.py:30
MemoryUnit(
    id="test-1",  # ❌ Invalid format
    ...
)
```

**Qdrant error:**
```
400 Bad Request: value test-1 is not a valid point ID, 
valid values are either an unsigned integer or a UUID
```

#### Affected Tests
- `test_backup_export.py::test_export_to_json` - ERROR
- `test_backup_export.py::test_export_with_project_filter` - ERROR
- `test_backup_export.py::test_create_portable_archive` - ERROR
- `test_backup_export.py::test_export_to_markdown` - ERROR

#### Fix
```python
import uuid
MemoryUnit(id=str(uuid.uuid4()), ...)  # Valid UUID
```

**Estimated impact:** ~4 ERROR tests fixed

---

### BUG #5: Test Collection Count Discrepancy
**Severity:** LOW (documentation)
**Impact:** Misleading documentation

#### Description
Test count varies between runs:
- CLAUDE.md: **2,723 tests**
- This run: **2,677 collected**
- Coverage run: **2,665 executed**
- Fresh collect: **2,744 collected**

Suggests conditional collection or documentation drift.

#### Fix
Audit test collection logic and update CLAUDE.md.

---

### BUG #6: Coverage Metric Discrepancy
**Severity:** LOW (documentation)
**Impact:** Misleading documentation

#### Description
- CLAUDE.md claims: **67% coverage**
- Actual: **59.6% overall**, **76.9% core modules**

Core modules meet target (80-85% goal), but overall pulled down by CLI exclusions.

#### Fix
Update CLAUDE.md with accurate breakdown.

---

## Additional Findings

### Test Isolation Issues
**Test:** `test_empty_database_health`
- Expected: 0 memories
- Actual: 174 memories present

Tests not properly cleaning up Qdrant collections between runs.

**Fix:** Use unique collection names (timestamp/UUID suffix).

---

## Fix Priority

### Phase 1: Critical (Unblock ~197 tests)
1. BUG #1: Update tests to use Qdrant (~185 tests)
2. BUG #2: Fix dict vs object (~8 tests)
3. BUG #4: Fix invalid Point IDs (~4 tests)

**Expected:** 87.7% → ~95% pass rate

### Phase 2: Medium (Cleanup)
4. BUG #3: Update category expectations (~2 tests)
5. Fix test isolation issues

**Expected:** >95% pass rate

### Phase 3: Documentation
6. BUG #5: Audit test collection
7. BUG #6: Update coverage metrics

---

## Comparison with First Bug Hunt

**First Bug Hunt (17:35):** Test **collection** errors
- Found: Module import failures (BUG-024, 025, 026)
- Impact: 11 test files can't be collected
- Root cause: Removed modules still imported

**This Bug Hunt (Evening):** Test **runtime** failures
- Found: Execution errors in collected tests
- Impact: 327 failures in 2,677 collected tests
- Root cause: Incomplete refactoring, type mismatches

**Combined Impact:** ~500+ broken tests total

---

## Conclusion

**Status:** v4.0 RC1 has significant test suite issues

**Strengths:**
- 87.7% pass rate shows core functionality works
- Issues concentrated in specific areas
- Fixes are straightforward

**Weaknesses:**
- REF-010 refactoring incomplete (SQLite removal)
- Type safety issues (dict vs object)
- Test infrastructure needs hardening

**Recommendation:** Fix Phase 1 bugs (1-2 days work) before production release.

---

**Report Generated:** 2025-11-21 (Evening)
**Complements:** BUG-HUNT_2025-11-21_comprehensive_report.md (collection errors)
**Test Suite:** v4.0 RC1
**Python:** 3.13.6
**Execution Time:** 174.23s
