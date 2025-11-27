# Skipped Test Analysis Report

**Date:** 2025-11-26
**Total Tests Collected:** 4,100
**Estimated Skipped Tests:** ~335 (from 25 files with whole-file skip markers)
**Additional Individual Skips:** ~15-20 individual test methods

---

## Executive Summary

The test suite has approximately **335-355 skipped tests** across **37 test files**. Analysis reveals:

- **14 files (legitimate)**: Timing-sensitive tests appropriately skipped for CI/parallel execution
- **5 files (fixable)**: Flaky tests that pass individually but fail in parallel
- **7 files (unimplemented)**: Tests for planned features (FEAT-033, FEAT-048, FEAT-056, FEAT-057, FEAT-058, FEAT-059)
- **4 files (dead code)**: Tests for deprecated/removed functionality - **SHOULD BE DELETED**
- **7 files (test issues)**: Tests with design problems or fixture issues - **NEED INVESTIGATION**

---

## Category 1: Legitimate Skips (Keep As-Is)

**Count:** 14 files, ~139 tests
**Status:** ✅ Appropriate
**Action:** Keep skipped - these are timing-sensitive or CI-environment-specific

### Files with `@pytest.mark.skip_ci` (Flaky under parallel execution)
1. **tests/unit/test_indexed_content_visibility.py** (18 tests)
   - Reason: "Flaky under parallel execution - Qdrant timing sensitive"

2. **tests/unit/test_list_memories.py** (16 tests)
   - Reason: "Flaky under parallel execution - Qdrant timing sensitive"

3. **tests/unit/test_connection_health_checker.py** (84-line skip)
   - Reason: "Timing-sensitive under parallel execution"

4. **tests/unit/test_store/test_connection_health_checker.py** (24 tests)
   - Reason: "Timing-sensitive under parallel execution"

5. **tests/unit/test_project_reindexing.py** (3 individual tests)
   - Lines 98, 156, 228
   - Reason: "Flaky under parallel execution - Qdrant timing sensitive"

6. **tests/unit/test_file_watcher.py** (1 test - line 96)
   - Reason: "File I/O timing sensitive in CI environment"

7. **tests/unit/test_parallel_embeddings.py** (3 tests - lines 103, 203, 400)
   - Reason: "Process pool startup exceeds CI timeout"

8. **tests/unit/test_embedding_generator.py** (2 tests - lines 267, 284)
   - Reason: "Concurrent operations may exceed CI timeout"

9. **tests/unit/test_query_synonyms.py** (1 test - line 289)
   - Reason: "Query expansion timing/environment sensitive"

10. **tests/unit/test_server_extended.py** (1 test - line 420)
    - Reason: "Embedding model produces slightly different outputs in CI environment"

11. **tests/integration/test_e2e_workflows.py** (6 tests - lines 66, 120, 623, 1145, 1222, 1283)
    - Reason: "Flaky under parallel execution - Qdrant timing sensitive"

12. **tests/integration/test_indexing_integration.py** (whole file)
    - Reason: "Flaky under parallel execution - Qdrant timing sensitive"

13. **tests/integration/test_health_dashboard_integration.py** (whole file)
    - Reason: "Flaky under parallel execution - Qdrant timing sensitive"

14. **tests/integration/test_mcp_error_handling.py** (1 test - line 237)
    - Reason: "Flaky under parallel execution - Qdrant timing sensitive"

**Note:** conftest.py has automatic Docker detection (lines 661-667) that skips `@pytest.mark.requires_docker` tests when Docker is unavailable. This is working as intended.

---

## Category 2: Flaky - Pass Individually (Consider Sequential CI Job)

**Count:** 5 files, ~82 tests
**Status:** ⚠️ Fixable
**Action:** Consider dedicated sequential CI job or better UUID isolation

1. **tests/integration/test_hybrid_search_integration.py** (20 tests)
   - Reason: "Flaky in parallel execution - pass when run in isolation"
   - Note: May benefit from better collection isolation

2. **tests/integration/test_bug_018_regression.py** (24 tests)
   - Reason: "Flaky in parallel execution - pass when run in isolation"

3. **tests/integration/test_concurrent_operations.py** (12 tests)
   - Reason: "Flaky in parallel execution - pass when run in isolation"
   - Note: These tests are DESIGNED to test concurrency, so parallel execution conflicts are expected
   - Documented in tests/SKIPPED_FEATURES.md lines 190-256

4. **tests/integration/test_pool_store_integration.py** (17 tests)
   - Reason: "Flaky in parallel execution - pass when run in isolation"

5. **tests/integration/test_mcp_concurrency.py** (9 tests)
   - Reason: "Flaky in parallel execution - pass when run in isolation"

**Recommendation:** Create a dedicated CI job:
```yaml
- name: Sequential Integration Tests
  run: pytest tests/integration/test_concurrent_operations.py tests/integration/test_mcp_concurrency.py -v
```

---

## Category 3: Unimplemented Features (Enable When Ready)

**Count:** 3 files, ~39 tests
**Status:** ⏸️ Pending Implementation
**Action:** Enable when features are implemented

1. **tests/integration/test_suggest_queries_integration.py** (7 tests)
   - Feature: FEAT-057 (Query Suggestions)
   - Reason: "FEAT-057 suggest_queries() not implemented - planned for v4.1"
   - Status: Planned for v4.1

2. **tests/integration/test_call_graph_tools.py** (19 tests)
   - Feature: FEAT-059 (Call Graph Tools)
   - Reason: "FEAT-059 MCP tool methods not yet implemented on MemoryRAGServer"
   - Status: Backend complete, MCP methods missing
   - Documented in tests/SKIPPED_FEATURES.md lines 17-49

3. **tests/unit/test_get_dependency_graph.py** (16 tests)
   - Feature: FEAT-048 (Dependency Graph)
   - Reason: "FEAT-048 get_dependency_graph() method not implemented"

**Documented:** See tests/SKIPPED_FEATURES.md for full details

---

## Category 4: Partial Implementation (Complete or Rewrite)

**Count:** 4 files, ~82 tests
**Status:** ⚠️ Needs Work
**Action:** Complete implementation or update tests to match current API

1. **tests/integration/test_pattern_search_integration.py** (15 tests)
   - Feature: FEAT-058 (Pattern Search)
   - Issue: PatternMatcher class exists but not integrated into search_code()
   - Reason: "FEAT-058 integration tests have API mismatches - need rewriting"
   - **Fix:** Add `pattern` and `pattern_mode` parameters to search_code()
   - Documented in tests/SKIPPED_FEATURES.md lines 52-111

2. **tests/integration/test_search_code_ux_integration.py** (7 skipped + 1 passing)
   - Feature: FEAT-057 (UX Enhancements)
   - Missing: facets, summary, did_you_mean, refinement_hints
   - Reason: "FEAT-057 facets/summary/did_you_mean/refinement_hints not implemented - planned for v4.1"
   - Lines: 35, 65, 93, 116, 149, 163, 192
   - Documented in tests/SKIPPED_FEATURES.md lines 151-187

3. **tests/unit/test_advanced_filtering.py** (22 tests)
   - Feature: FEAT-056 (Advanced Filtering)
   - Issue: exclude_patterns, line_count_min/max, modified_after/before, sort_by not implemented
   - Reason: "FEAT-056 advanced filtering not fully implemented yet"

4. **tests/unit/test_auto_indexing_service.py** (6 skipped tests)
   - Feature: FEAT-033 (Auto-indexing Config)
   - Missing config parameters: auto_index_enabled, auto_index_exclude_patterns, auto_index_size_threshold
   - Lines: 250, 270, 373, 386, 412, 423, 535
   - 30 other tests PASS (service works, just config params missing)

---

## Category 5: Dead Code (DELETE THESE FILES)

**Count:** 4 files, ~51 tests
**Status:** ❌ Obsolete
**Action:** **DELETE** - Tests for deprecated/removed functionality

### Files to Delete:

1. **tests/unit/test_export_import.py** (19 tests) ⭐ HIGH PRIORITY
   - Reason: "Deprecated tests for old API - core functionality tested in test_backup_export.py and test_backup_import.py"
   - Replacement: tests/unit/test_backup_export.py (4 tests) + test_backup_import.py (4 tests)
   - Lines 1-25: File header explicitly recommends deletion (Option A)
   - **Action:** DELETE entire file

2. **tests/unit/test_store_project_stats.py** (2 individual tests)
   - Lines 92, 175: test_get_all_projects_not_initialized, test_get_project_stats_not_initialized
   - Reason: "Initialization checks removed in CHANGELOG 2025-11-24 - store now auto-initializes via _get_client()"
   - Lines 97-105: Comment says "This test is obsolete"
   - **Action:** DELETE these 2 test methods (keep rest of file)

3. **tests/unit/test_dashboard_api.py** (1 test)
   - Line 327: test_sqlite_backend
   - Reason: "SQLite support removed in REF-010 - Qdrant is now required"
   - **Action:** DELETE this test method

4. **tests/integration/test_provenance_trust_integration.py** (3 tests)
   - Lines 116, 174, 278
   - Reason: "Relationship detection functionality removed (see CHANGELOG 2025-11-20)"
   - **Action:** DELETE these 3 test methods

**Estimated cleanup:** Remove ~51 obsolete tests

---

## Category 6: Test Issues (INVESTIGATE & FIX)

**Count:** 7 files, ~81 tests
**Status:** ⚠️ Needs Investigation
**Action:** Fix test design or underlying issues

1. **tests/integration/test_error_recovery.py** (16 tests) ⭐ INVESTIGATE
   - Issue: "Tests expect ValidationError but server wraps in StorageError"
   - Lines 1-5: Header explains the mismatch
   - **Fix Options:**
     - A) Update server to raise ValidationError directly
     - B) Update tests to expect StorageError wrapper
     - C) Add unwrapping logic to tests
   - **Action:** Investigate error handling flow, then fix

2. **tests/integration/test_qdrant_store.py** (19 tests) ✅ FIXED (2025-11-26)
   - Issue: "Store fixture initialization issues - client is None"
   - **Resolution:** Tests were actually working correctly - just needed skip marker removed
   - All 19 tests now pass (verified both sequential and parallel execution)
   - Tests already had proper pool-aware assertions (lines 61-66)

3. **tests/performance/test_latency.py** (5 tests)
   - Issue: "Performance tests need async fixture fixes (TEST-028)"

4. **tests/performance/test_throughput.py** (5 tests)
   - Issue: "Performance tests need async fixture fixes (TEST-028)"

5. **tests/performance/test_cache.py** (5 tests)
   - Issue: "Performance tests need async fixture fixes (TEST-028)"

6. **tests/performance/test_scalability.py** (5 tests)
   - Issue: "Performance tests need async fixture fixes (TEST-028)"
   - **Action:** Track TEST-028 to fix async fixtures for all performance tests

7. **tests/e2e/test_first_run.py** + **test_critical_paths.py** (18 tests total)
   - Issue: "E2E tests need API compatibility fixes (TEST-027)"
   - **Action:** Track TEST-027 to fix API compatibility

8. **tests/unit/test_index_codebase_initialization.py** (1 test - line 181)
   - Issue: "Test requires live Qdrant and has incorrect mock setup (sets embedding_generator = store)"
   - **Action:** Fix mock setup or delete test if redundant

9. **tests/unit/test_git_storage.py** (27 tests)
   - Issue: "Git storage tests require stable Qdrant connection - skipped to avoid timeouts"
   - Line 24: Uses `pytest.mark.skipif` with GitPython check
   - **Action:** Investigate if tests can be stabilized or need better fixtures

10. **tests/unit/store/test_call_graph_store.py** (1 test - line 150)
    - Issue: "Known limitation: store_function_node creates duplicates instead of updating existing records"
    - **Action:** Fix duplicate bug or document as known limitation in CHANGELOG

---

## Summary Table

| Category | Files | Est. Tests | Action |
|----------|-------|------------|--------|
| Legitimate Skips | 14 | ~139 | ✅ Keep as-is |
| Flaky (Sequential CI) | 5 | ~82 | ⚠️ Consider sequential job |
| Unimplemented Features | 3 | ~39 | ⏸️ Enable when implemented |
| Partial Implementation | 4 | ~82 | ⚠️ Complete or rewrite |
| **Dead Code** | **4** | **~51** | **❌ DELETE** |
| Test Issues | 7 | ~81 | ⚠️ Investigate & fix |
| **TOTAL** | **37** | **~474** | |

**Note:** Some files have overlapping categories (e.g., individual skips + whole-file marks), so totals are estimates.

---

## Immediate Actions (Priority Order)

### 1. DELETE Dead Code (Highest Priority) ⭐⭐⭐

Remove ~51 obsolete tests:

```bash
# Delete entire file
rm tests/unit/test_export_import.py

# Edit to remove specific test methods:
# - tests/unit/test_store_project_stats.py (lines 92-105, 175-end of test)
# - tests/unit/test_dashboard_api.py (line 327-end of test)
# - tests/integration/test_provenance_trust_integration.py (lines 116-140, 174-200, 278-300)
```

**Expected gain:** Cleaner test suite, reduced confusion about deprecated APIs

### 2. INVESTIGATE Test Issues ⭐⭐

~~Focus on these 2 files first:~~ (1/2 COMPLETE)

**Completed:**
- ✅ `test_qdrant_store.py`: All 19 tests now pass (skip marker removed)

**Remaining:**
```bash
# Test if this passes when skip is removed
python -m pytest tests/integration/test_error_recovery.py -xvs
```

**Expected outcome:**
- `test_error_recovery.py`: Need to fix error type expectations

### 3. TRACK Feature Implementation

Monitor these tickets in TODO.md:
- FEAT-033 (auto-indexing config) - 6 tests waiting
- FEAT-048 (dependency graph) - 16 tests waiting
- FEAT-056 (advanced filtering) - 22 tests waiting
- FEAT-057 (query suggestions + UX) - 14 tests waiting
- FEAT-058 (pattern search) - 15 tests waiting
- FEAT-059 (call graph tools) - 19 tests waiting

**Total:** ~92 tests waiting on feature completion

### 4. CONSIDER Sequential CI Job

Create `.github/workflows/sequential-tests.yml`:

```yaml
name: Sequential Integration Tests
on: [push, pull_request]
jobs:
  sequential:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Run concurrent operation tests
        run: |
          pytest tests/integration/test_concurrent_operations.py -v
          pytest tests/integration/test_mcp_concurrency.py -v
          pytest tests/integration/test_hybrid_search_integration.py -v
```

**Expected gain:** ~82 tests could be unskipped for CI

---

## Tests That May Pass Now (Candidates for Unskipping)

~~These tests might pass if skip markers are removed:~~ (1/2 COMPLETE)

1. ✅ **tests/integration/test_qdrant_store.py** (19 tests) - FIXED 2025-11-26
   - Skip marker removed, all tests passing
   - Tests already had proper pool-aware assertions

2. **tests/unit/test_git_storage.py** (27 tests)
   - Reason: Skip condition is `not GITPYTHON_AVAILABLE or SKIP_GIT_TESTS`
   - Test: Verify GitPython is installed, may work with better fixtures

---

## Conclusion

**Key Findings:**

1. **Dead Code (51 tests):** DELETE immediately - no value, causes confusion
2. **Legitimate Skips (139 tests):** Keep as-is - appropriate for CI/parallel execution
3. **Test Issues (62 tests):** Investigate - may reveal real bugs in error handling or initialization
   - ✅ 19 FIXED: test_qdrant_store.py (2025-11-26)
4. **Pending Features (92 tests):** Enable progressively as features ship
5. **Flaky Tests (82 tests):** Consider sequential CI job to unskip

**Net Result:** Of 335 skipped tests:
- **51 should be deleted** (dead code)
- **139 are correctly skipped** (timing-sensitive)
- **82 could run sequentially** (flaky in parallel)
- **92 waiting on features** (planned work)
- **62 need investigation** (potential bugs, down from 81)
- **19 now passing** (test_qdrant_store.py fixed)

**Next Steps:**
1. Delete dead code (test_export_import.py + 6 individual tests)
2. ✅ ~~Investigate test_qdrant_store.py~~ and test_error_recovery.py
3. Track TEST-027, TEST-028 for E2E/performance test fixes
4. Monitor FEAT-033/048/056/057/058/059 completion

---

**Report Generated:** 2025-11-26
**Test Suite Version:** main branch (commit: b25cbba)
**Analysis Method:** Static analysis + pytest collection + manual review
