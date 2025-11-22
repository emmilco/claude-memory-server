# Round 3: Test Failure Fix Plan

**Date:** 2025-11-21
**Objective:** Fix remaining test failures to achieve >95% pass rate
**Starting State:** 84.7% pass rate (2,267 / 2,675 passing)
**Target:** >95% pass rate (< 135 failures)

---

## Executive Summary

### Current State Analysis

**Test Results (Parallel Run with -n auto):**
- **2,267 PASSED** (84.7%)
- **126 FAILED** (4.7%)
- **266 ERROR** (9.9%)
- **16 SKIPPED** (0.6%)
- **Total issues:** 392 (126 + 266)
- **Execution time:** 11:25 (685s) with 8 workers

### Key Finding: Execution Summary Was Outdated

The execution summary reported 92.5% pass rate (185 issues), but actual results show 84.7% (392 issues). This is significantly worse than expected and suggests either:
1. Recent commits introduced regressions
2. The previous test run was done with different configuration
3. Tests are flaky and results vary between runs

---

## Failure Category Analysis

### Top 5 Failure Categories (Grouped)

#### 1. **Language Parser Registration** (35 FAILED)
**Files:**
- `test_kotlin_parsing.py`: 13 failures
- `test_swift_parsing.py`: 11 failures
- `test_ruby_parsing.py`: 11 failures

**Root Cause:**
```
RuntimeError: Unsupported file extension: kt
RuntimeError: Unsupported file extension: kts
RuntimeError: Unsupported file extension: swift
RuntimeError: Unsupported file extension: rb
```

**Diagnosis:** These language parsers are not registered in the parser configuration. Likely missing from `src/memory/python_parser.py` or Rust module.

**Fix Strategy:**
- Add extension mappings for .kt, .kts, .swift, .rb
- Verify tree-sitter queries exist for these languages
- Add language configs to parser initialization

**Expected Impact:** +35 tests passing (+1.3% pass rate)

---

#### 2. **Export/Import Bug** (13 FAILED)
**File:** `test_export_import.py`

**Root Cause:**
```
StorageError: [E001] Failed to export memories: not enough values to unpack (expected 2, got 0)
```

**Sample Failures:**
- test_export_json_to_file
- test_export_json_as_string
- test_export_markdown
- test_export_with_filtering
- test_import_from_file_skip_mode
- test_import_from_file_overwrite_mode

**Diagnosis:** The export code is trying to unpack a tuple that's empty or has wrong format. Likely `list_memories()` API changed and export code wasn't updated.

**Fix Strategy:**
- Check `src/backup/exporter.py` for unpacking logic
- Update to match current `list_memories` return format
- Verify import functionality after export fix

**Expected Impact:** +13 tests passing (+0.5% pass rate)

---

#### 3. **Server Test Fixtures** (39 ERROR)
**Files:**
- `test_server_extended.py`: 30 errors
- `test_server.py`: 9 errors

**Root Cause:** Test setup/teardown errors, likely cascading from Qdrant connection issues or fixture dependencies.

**Sample Errors:**
- test_store_and_retrieve_memory
- test_readonly_blocks_store
- test_retrieve_preferences_filters_correctly

**Diagnosis:** These tests use fixtures that fail to initialize, possibly due to:
1. Missing unique collection names (test isolation issue)
2. Qdrant timeout during parallel execution
3. Fixture dependency chain broken

**Fix Strategy:**
- Apply unique collection pattern (UUID-based) from Round 2
- Add proper async cleanup with grace period
- Increase Qdrant timeout for parallel tests

**Expected Impact:** +39 tests passing (+1.5% pass rate)

---

#### 4. **Git Storage** (25 ERROR)
**File:** `test_git_storage.py`

**Sample Errors:**
- test_store_commit_uninitialized_store
- test_search_commits_uninitialized_store
- test_get_commit_deserializes_fields
- test_store_file_change_without_diff

**Diagnosis:** Git storage tests have setup/initialization failures. Likely:
1. Missing fixtures
2. Uninitialized store objects
3. Missing mock repositories

**Fix Strategy:**
- Review fixture setup in test_git_storage.py
- Ensure proper git repository mocking
- Add initialization checks

**Expected Impact:** +25 tests passing (+0.9% pass rate)

---

#### 5. **Integration Test Errors** (71 ERROR)
**Files:**
- `test_qdrant_store.py`: 19 errors
- `test_retrieval_gate.py`: 17 errors
- `test_hybrid_search_integration.py`: 17 errors
- `test_memory_update_integration.py`: 14 errors
- `test_concurrent_operations.py`: 13 errors
- Others: ~11 errors

**Root Cause:** Similar to server tests - likely Qdrant connection timeouts during parallel execution.

**Fix Strategy:**
- Apply unique collection pattern to all integration tests
- Add retry logic for Qdrant connections
- Possibly reduce parallelism for integration tests

**Expected Impact:** +71 tests passing (+2.7% pass rate)

---

#### 6. **Error Recovery Integration** (15 FAILED)
**File:** `test_error_recovery.py`

**Diagnosis:** Need to sample these failures to understand root cause.

**Fix Strategy:** Sample and analyze in parallel agent.

**Expected Impact:** +15 tests passing (+0.6% pass rate)

---

### Minor Categories (< 10 failures each)

#### Health Jobs (9 FAILED)
- `test_health_jobs.py`: 9 failures

#### Usage Analyzer (7 FAILED)
- `test_usage_analyzer.py`: 7 failures

#### Confidence Scores (6 FAILED)
- `test_confidence_scores.py`: 6 failures

#### Others (~30 FAILED/ERROR)
- Various single-failure tests

---

## Parallel Fix Strategy

### Agent Assignment

#### **Agent 1: FIX-LANG-PARSERS** (Priority: HIGH)
**Worktree:** `.worktrees/FIX-LANG-PARSERS`
**Target:** 35 failures → Kotlin, Swift, Ruby parsing
**Files to modify:**
- `src/memory/python_parser.py` (or Rust equivalent)
- Language configuration files
- Tree-sitter query files (if needed)

**Tasks:**
1. Add .kt, .kts, .swift, .rb to supported extensions
2. Verify tree-sitter grammars loaded
3. Test parser registration
4. Run `pytest tests/unit/test_kotlin_parsing.py -v`
5. Run `pytest tests/unit/test_swift_parsing.py -v`
6. Run `pytest tests/unit/test_ruby_parsing.py -v`

---

#### **Agent 2: FIX-EXPORT-IMPORT** (Priority: HIGH)
**Worktree:** `.worktrees/FIX-EXPORT-IMPORT`
**Target:** 13 failures → Export/import unpacking bug
**Files to modify:**
- `src/backup/exporter.py`
- `src/backup/importer.py` (if needed)

**Tasks:**
1. Find unpacking error in export code
2. Check `list_memories` API return format
3. Update export code to match current API
4. Test with `pytest tests/unit/test_export_import.py -v`

---

#### **Agent 3: FIX-TEST-FIXTURES** (Priority: MEDIUM)
**Worktree:** `.worktrees/FIX-TEST-FIXTURES`
**Target:** 135 errors → Server, integration, git storage test fixtures
**Files to modify:**
- `tests/unit/test_server.py`
- `tests/unit/test_server_extended.py`
- `tests/unit/test_git_storage.py`
- `tests/integration/test_qdrant_store.py`
- `tests/integration/test_hybrid_search_integration.py`
- Others as needed

**Tasks:**
1. Apply unique collection pattern to all integration tests
2. Add proper async cleanup
3. Increase Qdrant connection timeout
4. Fix git storage fixture initialization
5. Run `pytest tests/unit/test_server_extended.py -v`
6. Run `pytest tests/integration/test_qdrant_store.py -v`

---

#### **Agent 4: FIX-ERROR-RECOVERY** (Priority: MEDIUM)
**Worktree:** `.worktrees/FIX-ERROR-RECOVERY`
**Target:** 15 failures → Error recovery integration tests
**Files to modify:**
- `tests/integration/test_error_recovery.py`
- Source files as needed

**Tasks:**
1. Run tests to sample failures
2. Identify root causes
3. Fix identified issues
4. Verify with `pytest tests/integration/test_error_recovery.py -v`

---

#### **Agent 5: FIX-MINOR-CATEGORIES** (Priority: LOW)
**Worktree:** `.worktrees/FIX-MINOR-CATEGORIES`
**Target:** 22 failures → Health jobs, usage analyzer, confidence scores
**Files to modify:**
- `tests/unit/test_health_jobs.py`
- `tests/unit/test_usage_analyzer.py`
- `tests/unit/test_confidence_scores.py`

**Tasks:**
1. Sample failures from each file
2. Identify patterns
3. Fix root causes
4. Run tests to verify

---

## Execution Plan

### Phase 1: Parallel Fixing (Agents 1-5)

1. **Create worktrees** for each agent
2. **Launch agents** in parallel
3. **Monitor progress** via test output
4. **Agents commit** to their branches when complete

### Phase 2: Sequential Merging

Merge order (by priority):
1. FIX-LANG-PARSERS (+35 tests)
2. FIX-EXPORT-IMPORT (+13 tests)
3. FIX-TEST-FIXTURES (+135 tests)
4. FIX-ERROR-RECOVERY (+15 tests)
5. FIX-MINOR-CATEGORIES (+22 tests)

**Total expected gain:** +220 tests (7.8% pass rate improvement)
**Target pass rate:** 92.5% → 95%+ if all fixes succeed

### Phase 3: Verification

1. Run full test suite: `pytest tests/ -n auto -v`
2. Check pass rate >= 95%
3. If < 95%, analyze remaining failures and iterate

---

## Expected Outcomes

### Best Case (All Fixes Successful)
- **Pass rate:** 92.3% (2,467 / 2,675)
- **Remaining issues:** ~208 (down from 392)
- **Improvement:** +7.6% pass rate

### Realistic Case (80% Success)
- **Pass rate:** 90.8% (2,431 / 2,675)
- **Remaining issues:** ~244 (down from 392)
- **Improvement:** +6.1% pass rate
- **Status:** Close to 95% target, one more round needed

### Conservative Case (60% Success)
- **Pass rate:** 89.3% (2,395 / 2,675)
- **Remaining issues:** ~280 (down from 392)
- **Improvement:** +4.6% pass rate
- **Status:** Multiple rounds needed

---

## Risk Assessment

### High Risk

**Parallel Test Execution Overwhelming Qdrant:**
- 266 ERRORs suggest Qdrant timeout issues
- May need to reduce parallelism or increase Qdrant resources
- Mitigation: Add retry logic, increase timeouts

**API Changes Breaking Tests:**
- Export/import failures suggest API drift
- Multiple test categories may have similar issues
- Mitigation: Check API compatibility across codebase

### Medium Risk

**Test Flakiness:**
- Different results between runs suggest flaky tests
- May need to address test isolation more comprehensively
- Mitigation: Unique collections, proper cleanup

**Cascading Failures:**
- Fixture failures causing multiple test errors
- Fixing one issue may reveal hidden issues
- Mitigation: Fix foundational issues first (fixtures)

---

## Success Criteria

### Round 3 Goals
- [ ] Pass rate > 90% (minimum acceptable)
- [ ] Pass rate > 95% (target)
- [ ] < 135 total failures (95% threshold)
- [ ] All language parsers working (Kotlin, Swift, Ruby)
- [ ] Export/import functionality restored
- [ ] Test fixtures stabilized

### Production Readiness (v4.0)
- [ ] Pass rate > 95%
- [ ] All critical functionality tested
- [ ] No high-priority bugs remaining
- [ ] Documentation updated

---

## Timeline Estimate

**Agent work:** 1-2 hours per agent (parallel)
**Merging:** 30 minutes (sequential)
**Verification:** 30 minutes
**Total:** 2-3 hours (wall clock time)

---

## Notes

### Infrastructure Concerns

The 266 ERRORs are likely test infrastructure issues, not code bugs:
- Qdrant connection timeouts during parallel execution
- Fixture initialization failures cascading
- Async cleanup race conditions

**Recommendation:** After fixing code bugs, consider:
1. Running tests with reduced parallelism: `pytest -n 4` instead of `-n auto`
2. Increasing Qdrant connection pool size
3. Adding retry decorators to Qdrant operations in tests
4. Separating integration tests into slower, more reliable runs

### Test Run Consistency

Need to establish why execution summary showed 92.5% but current run shows 84.7%:
- [ ] Check git commit hash for previous run
- [ ] Check test configuration differences
- [ ] Verify Qdrant was healthy during previous run
- [ ] Document standard test execution procedure

---

**Plan Created:** 2025-11-21
**Test Suite:** v4.0 RC1 (current main)
**Python:** 3.13.6
**Pytest Workers:** 8 (auto)
**Qdrant:** Docker localhost:6333
