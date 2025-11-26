# TODO

## 🚨 SPEC COVERAGE AUDIT (2025-11-25)

**Source:** 4-agent parallel analysis of SPEC.md requirements vs test suite coverage.
**Finding:** Testing pyramid inverted (91% unit, 8.6% integration, 0% E2E). Critical gaps in boundary conditions, concurrency, MCP protocol, and E2E workflows.

### 🔴 Critical - Testing Infrastructure Gaps

- [ ] **TEST-023**: Add 40+ Boundary Condition Unit Tests 🔥🔥🔥
  - **Problem:** Missing tests for edge cases at system limits - undefined behavior at boundaries
  - **Impact:** Potential crashes, data corruption, or undefined behavior at limits
  - **Categories to cover:**
    - **Numeric boundaries:** `importance=0.0`, `importance=1.0`, `importance=1.5` (invalid), `limit=0`, `offset > total`
    - **String boundaries:** `content=""` (empty), `content=50KB exactly`, `content=50KB+1` (overflow), `query=10000 chars`
    - **Collection boundaries:** `tags=[]` (empty), `tags=[""]` (empty string), `tags=[1000 items]`
    - **Pagination:** `offset=total+1`, `limit=0`, `limit > max_allowed`
    - **Search:** empty query, single character query, no results scenario
  - **Recommended tests:**
    ```python
    # tests/unit/test_boundary_conditions.py
    @pytest.mark.parametrize("importance", [-0.1, 0.0, 0.5, 1.0, 1.1, None])
    def test_importance_boundary_values(importance): ...

    @pytest.mark.parametrize("content_size", [0, 1, 51199, 51200, 51201])
    def test_content_size_boundaries(content_size): ...

    def test_pagination_offset_exceeds_total(): ...
    def test_search_empty_query(): ...
    def test_filter_complexity_min_greater_than_max(): ...
    ```
  - **Effort:** ~8 hours
  - **Files to create:** `tests/unit/test_boundary_conditions.py`, `tests/unit/test_pagination_edge_cases.py`

- [x] **TEST-024**: Fix Flaky Concurrent Operations Test Suite ✅ **COMPLETE** (2025-11-25)
  - **Problem:** `test_concurrent_operations.py` marked skip due to race conditions - hides real concurrency bugs
  - **Impact:** No concurrent operation testing in CI, race conditions go undetected
  - **Fix applied:**
    - [x] Removed module-level skip marker
    - [x] Added `return_exceptions=True` to all 15 `asyncio.gather()` calls
    - [x] Enhanced error messages with detailed diagnostics
    - [x] Tests use unique collections via pooling (already implemented)
  - **Verification:** 3 consecutive runs, 13/13 tests passing each time (100% stability)
  - **Tests fixed:** 13 tests across 8 test classes
  - **Related:** TEST-016 (flaky tests), extends that work

- [ ] **TEST-025**: Create 25+ End-to-End Workflow Integration Tests 🔥🔥
  - **Problem:** No integration tests for complete user workflows - features tested in isolation but not together
  - **Impact:** Component interactions untested, workflow bugs escape to production
  - **Current state:** 0 E2E workflow tests, only isolated component tests
  - **Required workflows:**
    ```python
    # tests/integration/test_e2e_workflows.py

    # Core memory workflow
    async def test_store_retrieve_update_delete_workflow():
        """Store → Retrieve → Update → Search → Delete complete lifecycle"""

    # Code indexing workflow
    async def test_index_search_similar_export_workflow():
        """Index project → Search code → Find similar → Export results"""

    # Multi-project workflow
    async def test_create_project_index_archive_export_import():
        """Create project → Index → Archive → Export → Reimport → Verify"""

    # Health monitoring workflow
    async def test_memory_lifecycle_affects_health_score():
        """Store memories → Lifecycle transitions → Verify health impact"""

    # Cross-project workflow
    async def test_cross_project_search_with_consent():
        """Create 3 projects → Opt-in 2 → Search → Verify isolation"""
    ```
  - **Workflows to implement (25 minimum):**
    1. Memory CRUD lifecycle (store → retrieve → update → delete)
    2. Code indexing pipeline (parse → embed → store → search)
    3. Project archival (create → index → archive → export → import)
    4. Cross-project search (create → opt-in → search → verify isolation)
    5. Health monitoring integration (actions → metrics → alerts)
    6. Memory lifecycle transitions (ACTIVE → RECENT → ARCHIVED → STALE)
    7. Duplicate detection and merge workflow
    8. Provenance tracking end-to-end
    9. Search with all filter combinations
    10. Pagination across large result sets
    11-25. Additional scenarios per SPEC.md requirements
  - **Effort:** ~12 hours
  - **Files to create:** `tests/integration/test_e2e_workflows.py`, `tests/integration/test_workflow_memory.py`, `tests/integration/test_workflow_indexing.py`

- [ ] **TEST-026**: Create MCP Protocol Integration Test Suite (F010) 🔥🔥🔥
  - **Problem:** Zero tests for MCP protocol integration - SPEC F010 completely untested
  - **Impact:** MCP tool registration, validation, concurrency, error handling all untested
  - **SPEC requirements (4 total, 0% covered):**
    - F010-R001: 16 MCP tools must be registered and accessible
    - F010-R002: Pydantic schema validation for all requests
    - F010-R003: Concurrent async MCP request handling
    - F010-R004: Structured error responses (ValidationError, StorageError, etc.)
  - **Test files referenced in SPEC but don't exist:**
    - `tests/integration/test_mcp_integration.py`
    - `tests/integration/test_mcp_concurrency.py`
    - `tests/integration/test_mcp_error_handling.py`
  - **Tests to implement:**
    ```python
    # tests/integration/test_mcp_integration.py
    async def test_all_16_tools_registered():
        """Verify all 16 MCP tools are discoverable"""

    async def test_tool_schema_validation():
        """Verify Pydantic validates all tool parameters"""

    async def test_tool_returns_structured_errors():
        """Verify errors return proper JSON structure"""

    # tests/integration/test_mcp_concurrency.py
    async def test_100_concurrent_mcp_requests():
        """Stress test: 100 parallel MCP tool calls"""

    async def test_mcp_request_timeout_handling():
        """Verify proper timeout handling for slow operations"""

    # tests/integration/test_mcp_error_handling.py
    async def test_validation_error_response_format():
        """Verify ValidationError returns proper structure"""

    async def test_storage_error_response_format():
        """Verify StorageError returns proper structure"""
    ```
  - **Effort:** ~10 hours
  - **Priority:** CRITICAL - core protocol completely untested

### 🟡 High Priority - Test Quality Improvements

- [ ] **TEST-027**: Convert Manual Tests to Automated E2E 🔥🔥
  - **Problem:** 5 manual test scripts exist but aren't in CI/CD - 0% automated E2E coverage
  - **Impact:** Regression risk, manual testing burden, no E2E coverage in CI
  - **Current manual tests:**
    - `test_all_features.py` - Comprehensive feature walkthrough (MANUAL)
    - `debug_search.py` - Debug utility (not a test)
    - `eval_test.py` - Evaluation script (not a test)
  - **Conversion approach:**
    1. Extract test scenarios from manual scripts
    2. Create pytest fixtures for setup/teardown
    3. Add assertions for expected outcomes
    4. Integrate into CI/CD pipeline
  - **Target: 10-15 automated E2E tests from manual scripts:**
    ```python
    # tests/e2e/test_critical_paths.py

    @pytest.mark.e2e
    async def test_first_time_user_setup():
        """New user: install → configure → index → search"""

    @pytest.mark.e2e
    async def test_daily_workflow():
        """Typical day: search code → store memory → retrieve → export"""

    @pytest.mark.e2e
    async def test_project_migration():
        """Migrate: export project → delete → reimport → verify"""
    ```
  - **Effort:** ~8 hours
  - **Files to create:** `tests/e2e/` directory, `tests/e2e/conftest.py`, `tests/e2e/test_critical_paths.py`
  - **CI integration:** Add `pytest tests/e2e/ -m e2e` to nightly CI run

- [ ] **TEST-028**: Add Performance Regression Test Suite 🔥🔥
  - **Problem:** No automated performance regression detection - silent degradation possible
  - **Impact:** Performance could degrade without detection until users complain
  - **Note:** PERF-006 implemented detection logic, but no automated test suite exists
  - **SPEC requirements:**
    - F007-R001: P95 search latency <50ms (current: 3.96ms)
    - F007-R002: Cache hit rate >90% (current: 98%)
    - F007-R003: Indexing throughput >1 file/sec (current: 2.45 sequential, 10-20 parallel)
    - F007-R006: Concurrent throughput >10 req/sec (current: 55,246 ops/sec)
  - **Tests to implement:**
    ```python
    # tests/performance/test_regression_detection.py

    @pytest.mark.performance
    def test_search_latency_p95_under_50ms():
        """Run 100 queries, assert P95 < 50ms"""

    @pytest.mark.performance
    def test_indexing_throughput_baseline():
        """Index 100 files, assert > 1 file/sec"""

    @pytest.mark.performance
    def test_cache_hit_rate_above_90_percent():
        """Re-index unchanged files, assert cache hits > 90%"""

    @pytest.mark.performance
    def test_concurrent_search_throughput():
        """Run 100 concurrent searches, assert > 10 req/sec"""
    ```
  - **Integration with CI:**
    - Run on merge to main (not every PR)
    - Store baseline metrics in artifact
    - Alert if regression >20% from baseline
  - **Effort:** ~8 hours
  - **Files to create:** `tests/performance/`, `tests/performance/test_latency.py`, `tests/performance/test_throughput.py`
  - **Related:** PERF-006 (detection logic exists, needs test harness)

### 📊 SPEC Coverage Audit Summary

| Category | SPEC Reqs | Current Coverage | After Fixes |
|----------|-----------|------------------|-------------|
| Boundary conditions | ~40 | 5% | 80%+ |
| Concurrent operations | ~15 | 8% (1 flaky) | 90%+ |
| E2E workflows | ~25 | 0% | 80%+ |
| MCP protocol (F010) | 4 | 0% | 100% |
| Performance regression | ~10 | 0% (manual) | 100% |
| **Total new tests** | | | **~120 tests** |

**Estimated effort:** 52 hours (~7 days)
**Impact:** Testing pyramid rebalanced (target: 80% unit, 15% integration, 5% E2E)

---

## 🚨 TEST ANTIPATTERN AUDIT (2025-11-25)

**Source:** 6-agent parallel review analyzing 168 test files for validation theater and antipatterns.
**Methodology:** Each agent reviewed ~25-30 test files for: no assertions, mock overuse, weak assertions, flaky tests, broad exceptions, ignored return values, misleading names.

### 🔴 Critical - Validation Theater (Zero Real Coverage)

- [ ] **TEST-013**: Remove/Fix Entirely Skipped Test Suites (~13 files, ~200+ tests) 🔥🔥🔥
  - **Problem:** Module-level `pytest.mark.skip` disables entire test files, providing false coverage
  - **Impact:** Features appear tested but have ZERO runtime validation
  - **Files to address:**
    - `tests/unit/test_get_dependency_graph.py` - FEAT-048 not implemented
    - `tests/security/test_readonly_mode.py` - Critical security feature untested
    - `tests/unit/test_backup_export.py` - Embedding fixture issues
    - `tests/unit/test_backup_import.py` - Embedding fixture issues
    - `tests/unit/test_export_import.py` - Old API signatures
    - `tests/integration/test_call_graph_tools.py` - FEAT-059 not implemented
    - `tests/integration/test_pattern_search_integration.py` - FEAT-058 API mismatches
    - `tests/integration/test_suggest_queries_integration.py` - FEAT-057 not implemented
    - `tests/integration/test_search_code_ux_integration.py` - v4.1 features
    - `tests/integration/test_concurrent_operations.py` - Flaky under parallel execution
  - **Fix options:**
    1. Implement missing features and remove skip markers
    2. Delete test files for unimplemented features (remove false coverage)
    3. Fix fixture issues (backup tests) and remove skip markers
  - **Tracking:** Create `tests/SKIPPED_FEATURES.md` documenting what's not tested

- [ ] **TEST-014**: Remove `assert True` Validation Theater (4 instances) 🔥🔥
  - **Problem:** Tests that always pass, providing zero validation
  - **Locations:**
    - `tests/unit/test_embedding_generator.py:378` - Coverage summary test
    - `tests/security/test_readonly_mode.py:365` - Coverage summary (skipped anyway)
    - `tests/security/test_injection_attacks.py:447` - Pattern coverage report
    - `tests/integration/test_concurrent_operations.py:446` - Coverage report function
  - **Fix:** Delete these "report" functions or convert to actual tests with assertions
  - **Impact:** Remove 4 false-positive test results

- [ ] **TEST-015**: Add Assertions to 23+ No-Assertion Tests 🔥🔥
  - **Problem:** Tests that only check "function runs without error" (validation theater)
  - **Primary files:**
    - `tests/unit/test_status_command.py` - 16 instances (lines 359, 367, 379, 391, 402, 415, 424, 435, 446, 457, 463, 478, 484, 603, 617, 632)
    - `tests/unit/test_health_command.py` - 7 instances (lines 412, 420, 426, 432, 438, 447, 456)
  - **Pattern:** `cmd.print_something(); # Should not raise` with NO assertions
  - **Fix:** Mock print/console output and assert correct content was displayed
  - **Example fix:**
    ```python
    # Instead of:
    cmd.print_header()  # Should not raise

    # Do:
    with patch.object(cmd.console, 'print') as mock_print:
        cmd.print_header()
        assert mock_print.called
        assert "Status" in str(mock_print.call_args)
    ```

### 🟡 High Priority - Tests That Hide Bugs

- [ ] **TEST-016**: Fix 20+ Flaky Tests Marked Skip (Race Conditions) 🔥🔥
  - **Problem:** Tests skipped due to "race conditions" hide real concurrency bugs
  - **Affected tests:**
    - `tests/unit/test_pattern_detector.py:56-65, 94-100` - Race in parallel execution
    - `tests/unit/test_parallel_embeddings.py:271-293` - Cache hit test race
    - `tests/unit/test_project_reindexing.py:76-167` - 4+ tests skipped
    - `tests/unit/test_connection_health_checker.py:84-92, 308-326` - Timing-sensitive
    - `tests/unit/store/test_call_graph_store.py:149-191` - Upsert race
    - `tests/integration/test_bug_018_regression.py:43, 131` - Core regression tests!
    - `tests/integration/test_qdrant_store.py:51` - Store initialization timeout
    - `tests/integration/test_indexing_integration.py:309` - Delete file index race
  - **Fix approach:**
    1. Add proper synchronization primitives
    2. Use test locks for Qdrant access
    3. Replace timing assertions with Event/Signal patterns
    4. Fix underlying race conditions in implementation
  - **Priority:** BUG-018 regression tests are CRITICAL - must be re-enabled

- [ ] **TEST-017**: Replace 30+ Mock-Only Tests with Behavior Tests 🔥
  - **Problem:** Tests that only verify `mock.assert_called()` don't test real behavior
  - **Affected files:**
    - `tests/unit/test_generator_gpu.py:61-121` - 3 GPU tests verify mocks only
    - `tests/unit/test_qdrant_error_paths.py` - 15+ tests verify mock calls
    - `tests/unit/test_qdrant_setup_coverage.py` - Multiple tests
    - `tests/unit/test_health_scheduler.py:269-290` - Job execution mocked
    - `tests/unit/test_status_command.py:315-350` - Store/config mocked
    - `tests/unit/test_incremental_indexer.py:160-172` - Store mocked
  - **Fix approach:**
    1. Add assertions on actual return values/behavior
    2. Test with real objects where possible (use temp files, in-memory DBs)
    3. If mocking, verify BOTH mock call AND result correctness
  - **Example fix:**
    ```python
    # Instead of:
    mock_store.batch_store.assert_called_once()

    # Do:
    mock_store.batch_store.assert_called_once()
    stored_items = mock_store.batch_store.call_args[0][0]
    assert len(stored_items) == expected_count
    assert all(item.has_embedding for item in stored_items)
    ```

- [ ] **TEST-018**: Strengthen 50+ Weak/Trivial Assertions 🔥
  - **Problem:** Assertions that always pass or only verify type/existence
  - **Categories:**
    1. **Type-only:** `assert isinstance(x, list)` - doesn't verify contents
    2. **Range too wide:** `assert value >= 0` - always true for unsigned
    3. **Existence only:** `assert "key" in result` - doesn't verify value
    4. **Conditional assertions:** `if "field" in x: assert x["field"] == y` - passes if field missing
  - **Affected files:**
    - `tests/unit/test_server.py:51-57` - Only `is not None` checks
    - `tests/unit/test_server_extended.py:87-91` - Conditional field checks
    - `tests/unit/test_complexity_analyzer.py:191-212` - `assert depth >= N`
    - `tests/unit/test_criticality_analyzer.py:78, 216-259` - Weak boundary checks
    - `tests/unit/test_quality_analyzer.py:73-100` - Wide range assertions
    - `tests/unit/test_monitoring_system.py:85-93` - `>= 0` always true
    - `tests/unit/test_bulk_operations.py:120-134` - 10x range (`> 500 and < 5000`)
  - **Fix approach:**
    1. Replace `>= 0` with exact expected values
    2. Replace `is not None` with specific type/value checks
    3. Make conditional assertions unconditional
    4. Tighten range assertions to expected precision

### 🟢 Medium Priority - Test Quality Improvements

- [ ] **TEST-019**: Narrow 10+ Broad Exception Catches
  - **Problem:** `pytest.raises(Exception)` catches any error, hiding wrong exception types
  - **Affected tests:**
    - `tests/unit/test_server_extended.py:129-136` - Should be `FileNotFoundError`
    - `tests/unit/test_cli_commands.py:197-208, 357-368` - Should be specific
    - `tests/unit/test_embedding_generator.py:210-213` - Catches 3 types!
    - `tests/integration/test_error_recovery.py:296-326` - Should be `ValidationError`
  - **Fix:** `pytest.raises(SpecificError, match="expected message")`

- [ ] **TEST-020**: Rename 22+ Misleading Test Names
  - **Problem:** Test names claim to test X but actually test Y
  - **Pattern:** `test_print_X_with_Y` tests don't verify output content
  - **Affected files:**
    - `tests/unit/test_status_command.py` - 16+ "test_print_*" methods
    - `tests/unit/test_health_command.py` - "test_check_*" methods
    - `tests/unit/test_qdrant_error_paths.py` - 6+ methods
  - **Fix:** Rename to match actual behavior (e.g., `test_print_X_no_error`)

- [ ] **TEST-021**: Add Missing Edge Case Tests (~15 areas)
  - **Problem:** Happy-path only testing misses boundary conditions
  - **Missing tests for:**
    - Division by zero (ETA calculation when `total_files=0`)
    - Empty inputs (None, [], "")
    - Boundary values (exactly at limits)
    - Invalid states (corrupted data, disconnected services)
  - **Affected files:**
    - `tests/unit/test_auto_indexing_service.py:124-136` - No edge cases for ETA
    - `tests/unit/test_bulk_operations.py` - No batching edge cases
    - `tests/unit/test_call_graph.py` - No invalid input tests

- [ ] **TEST-022**: Check Ignored Return Values (~10 tests)
  - **Problem:** Tests call functions but don't verify return values
  - **Pattern:** `await cmd.run(args)` with no assertion on result
  - **Affected tests:**
    - `tests/unit/test_cli_commands.py:50-75` - `run()` return ignored
    - `tests/unit/test_server_extended.py:72-91` - Only structure checked
    - `tests/integration/test_error_recovery.py:213-230` - `result` not fully checked

### 📊 Test Antipattern Audit Summary

| Category | Count | Severity | Status |
|----------|-------|----------|--------|
| Skipped test suites (0 coverage) | ~13 files | CRITICAL | ⬜ TODO |
| `assert True` validation theater | 4 | CRITICAL | ⬜ TODO |
| No-assertion tests | 23+ | CRITICAL | ⬜ TODO |
| Flaky tests (skip hiding bugs) | 20+ | HIGH | ⬜ TODO |
| Mock-only tests | 30+ | HIGH | ⬜ TODO |
| Weak/trivial assertions | 50+ | HIGH | ⬜ TODO |
| Broad exception catching | 10+ | MEDIUM | ⬜ TODO |
| Misleading test names | 22+ | MEDIUM | ⬜ TODO |
| Missing edge cases | 15+ areas | MEDIUM | ⬜ TODO |
| Ignored return values | 10+ | MEDIUM | ⬜ TODO |

**Estimated False Coverage:** 15-20% of test suite doesn't actually validate behavior
**Tests That Could Pass With Bugs:** ~100+ tests would pass even with broken implementations

---

## 🚨 CODE REVIEW FINDINGS (2025-11-25)

**Source:** Comprehensive 4-agent code review analyzing architecture, testing, error handling, and developer experience.
**Full Report:** `~/Documents/code_review_2025-11-25.md`

### 🔴 Critical - Must Fix Before Production

- [x] **REF-015**: Fix Unsafe Resource Cleanup Pattern ✅ **COMPLETE** (2025-11-25)
  - **Location:** `src/store/qdrant_store.py` (50+ instances)
  - **Problem:** Using `if 'client' in locals():` for cleanup is fragile and causes resource leaks
  - **Impact:** Connection pool exhaustion under error conditions, silent failures
  - **Fix:** Replace with `client = None; try: client = await self._get_client() finally: if client:`
  - **Better:** Implement async context manager pattern for all resource acquisition
  - **See:** code_review_2025-11-25.md section ARCH-002

- [x] **BUG-034**: Remove Duplicate Config Field `enable_retrieval_gate` ✅ **COMPLETE** (2025-11-25)
  - **Location:** `src/config.py:70` and `src/config.py:93`
  - **Problem:** Same field defined twice in ServerConfig class
  - **Impact:** Configuration confusion, unclear which definition is authoritative
  - **Fix:** Remove duplicate definition at line 93, consolidate comments
  - **See:** code_review_2025-11-25.md section CONFIG-001

- [x] **BUG-035**: Add Exception Chain Preservation ✅ **COMPLETE** (2025-11-25)
  - **Location:** 40+ locations across `src/store/`, `src/embeddings/`, `src/memory/`
  - **Problem:** `raise SomeError(f"message: {e}")` loses original exception chain
  - **Impact:** Cannot debug production failures - original traceback lost
  - **Fix:** Change all to `raise SomeError(f"message: {e}") from e`
  - **Grep:** `grep -r "raise.*Error.*{e}\")" src/`
  - **See:** code_review_2025-11-25.md section ERR-001

- [x] **TEST-008**: Delete Empty Placeholder Test Files ✅ **COMPLETE** (2025-11-25)
  - **Location:** `tests/` root directory
  - **Files:** `test_database.py`, `test_ingestion.py`, `test_mcp_server.py`, `test_router.py` (0 bytes each)
  - **Problem:** Empty files create false coverage impression, confuse developers
  - **Impact:** Technical debt, misleading test counts
  - **Fix:** Delete all 4 empty files
  - **See:** code_review_2025-11-25.md section TEST-003

- [x] **BUG-036**: Fix Silent/Swallowed Exceptions ✅ **COMPLETE** (2025-11-25)
  - **Location:** `src/analysis/criticality_analyzer.py:204-211`, `src/review/patterns.py:227`
  - **Problem:** Bare `except: pass` swallows all errors silently
  - **Impact:** TypeError, AttributeError completely invisible - debugging impossible
  - **Fix:** Catch specific exceptions, add logging for unexpected ones
  - **See:** code_review_2025-11-25.md section ERR-002

### 🟡 High Priority - Next Sprint

- [ ] **REF-016**: Split MemoryRAGServer God Class (~1 week) 🔥🔥
  - **Location:** `src/core/server.py` (4,767 lines, 62+ methods)
  - **Problem:** Violates Single Responsibility Principle - handles storage, search, indexing, analytics, monitoring
  - **Impact:** Impossible to test in isolation, high coupling, difficult maintenance
  - **Proposed Solution:** Extract into focused service classes:
    - [ ] `SearchService` - query handling, hybrid search
    - [ ] `IndexingService` - code indexing, file watching
    - [ ] `AnalyticsService` - usage tracking, metrics
    - [ ] `MemoryService` - CRUD operations
  - **Note:** REF-013 Phase 1 (HealthService) already complete - continue pattern
  - **See:** code_review_2025-11-25.md section ARCH-001

- [x] **REF-017**: Consolidate Feature Flags ✅ **COMPLETE** (2025-11-25)
  - **Location:** `src/config.py` (31+ boolean flags)
  - **Problem:** Exponential configuration complexity, untestable combinations
  - **Impact:** 2^31+ config combinations infeasible to test, difficult to reason about behavior
  - **Proposed Solution:**
    - [ ] Group related flags into feature classes (`SearchFeatures`, `AnalyticsFeatures`)
    - [ ] Create semantic feature levels (BASIC, ADVANCED, EXPERIMENTAL)
    - [ ] Remove redundant flags after BUG-034 fix
  - **See:** code_review_2025-11-25.md section ARCH-003

- [x] **UX-049**: Add `exc_info=True` to Error Logs ✅ **COMPLETE** (2025-11-25)
  - **Location:** 100+ `logger.error()` calls throughout codebase
  - **Problem:** Error logs don't include tracebacks
  - **Impact:** Cannot debug production issues - only error message, no stack trace
  - **Fix:** Add `exc_info=True` parameter to all `logger.error()` calls
  - **Grep:** `grep -r "logger.error" src/ | wc -l`
  - **See:** code_review_2025-11-25.md section ERR-003

- [x] **UX-050**: Add Thread-Safe Stats Counters ✅ **COMPLETE** (2025-11-25)
  - **Location:** `src/core/server.py` (stats mutations across 62+ methods)
  - **Problem:** `self.stats["key"] += 1` not thread-safe
  - **Impact:** Lost updates in concurrent scenarios, inconsistent metrics
  - **Fix:** Use Lock or atomic counter primitives:
    ```python
    from threading import Lock
    self._stats_lock = Lock()
    def _increment_stat(self, key, value=1):
        with self._stats_lock:
            self.stats[key] += value
    ```
  - **See:** code_review_2025-11-25.md section ARCH-004

- [x] **TEST-009**: Add Test Parametrization ✅ **COMPLETE** (2025-11-25)
  - **Location:** All 125 unit test files
  - **Problem:** Zero uses of `@pytest.mark.parametrize` despite 100+ duplicate test patterns
  - **Impact:** 5x slower test suite, massive code duplication, maintenance nightmare
  - **Fix:** Replace duplicate tests with parametrized versions
  - **Example:** 50+ near-identical `test_pool_creation_*` methods → 1 parametrized test
  - **See:** code_review_2025-11-25.md section TEST-001

- [x] **TEST-010**: Reduce Excessive Mocking ✅ **COMPLETE** (2025-11-25)
  - **Location:** 30+ test files, especially `test_qdrant_setup_coverage.py`, `test_indexing_progress.py`
  - **Problem:** Tests only verify `mock.assert_called()`, not actual behavior
  - **Impact:** False confidence - unit tests pass but integration tests fail (40+ recent failures)
  - **Fix:** Replace mock-only assertions with behavior verification
  - **See:** code_review_2025-11-25.md section TEST-002

- [x] **TEST-011**: Add Test Markers ✅ **COMPLETE** (2025-11-25)
  - **Location:** All test files
  - **Problem:** No `@pytest.mark.unit`, `@pytest.mark.integration`, `@pytest.mark.slow` markers
  - **Impact:** Can't run `pytest -m "not slow"` to skip slow tests in CI
  - **Fix:** Add markers to all test files, update pytest.ini
  - **See:** code_review_2025-11-25.md section TEST-005

- [x] **TEST-012**: Replace Sleep-Based Tests with Signals ✅ **COMPLETE** (2025-11-25)
  - **Location:** 7 test files with `asyncio.sleep()` or `time.sleep()`
  - **Problem:** Non-deterministic tests fail randomly on slow CI
  - **Impact:** Flaky tests, unreliable CI, wasted debugging time
  - **Fix:** Replace sleeps with Event/Signal patterns
  - **See:** code_review_2025-11-25.md section TEST-004

### 🟢 Medium Priority - Quality Improvements

- [x] **DOC-008**: Add Missing Module Docstrings ✅ **COMPLETE** (2025-11-25)
  - **Location:** `src/analysis/` (5 modules with empty docstrings)
  - **Files:** `code_duplicate_detector.py`, `criticality_analyzer.py`, `usage_analyzer.py`, `importance_scorer.py`, `__init__.py`
  - **Problem:** New developers can't understand module purpose without reading implementation
  - **Impact:** Harder onboarding, poor IDE support
  - **Fix:** Add comprehensive module docstrings following `quality_analyzer.py` pattern
  - **See:** code_review_2025-11-25.md section DOC-001

- [x] **DOC-009**: Create Error Handling Documentation ✅ **COMPLETE** (2025-11-25)
  - **Location:** `docs/ERROR_HANDLING.md` (new file)
  - **Problem:** 15+ custom exceptions in `src/core/exceptions.py` with no usage guide
  - **Impact:** Callers don't know what to catch, no recovery strategies documented
  - **Fix:** Document each exception type, when raised, how to handle
  - **See:** code_review_2025-11-25.md section DOC-002

- [x] **PERF-008**: Add Distributed Tracing Support ✅ **COMPLETE** (2025-11-25)
  - **Location:** Throughout async operations in `src/core/server.py`
  - **Problem:** No operation IDs passed through request chains
  - **Impact:** Cannot correlate logs across services, debugging multi-step failures impossible
  - **Fix:** Add operation IDs via contextvars:
    ```python
    from contextvars import ContextVar
    operation_id: ContextVar[str] = ContextVar('operation_id', default='')
    ```
  - **See:** code_review_2025-11-25.md section ERR-004

- [x] **REF-018**: Remove Global State Patterns ✅ **COMPLETE** (2025-11-25)
  - **Locations:**
    - `src/core/degradation_warnings.py:32-76` - Global `_degradation_tracker`
    - `src/embeddings/parallel_generator.py:36-51` - Global `_worker_model_cache`
  - **Problem:** Hidden dependencies, difficult testing, state leakage between tests
  - **Impact:** Tests affect each other via global state, hard to isolate behavior
  - **Fix:** Pass tracker/cache as dependency injection instead of module-level globals
  - **See:** code_review_2025-11-25.md section ARCH-005

- [x] **REF-019**: Extract ConnectionPool from QdrantStore ✅ **COMPLETE** (2025-11-25)
  - **Location:** `src/store/qdrant_store.py` (2,953 lines, 45 methods)
  - **Problem:** Single class handles connection pooling AND business logic
  - **Impact:** Difficult to test, tight coupling, violates SRP
  - **Fix:** Extract `ConnectionPool` class, keep `QdrantStore` focused on data operations
  - **See:** code_review_2025-11-25.md section ARCH-006

- [x] **UX-051**: Improve Configuration Validation ✅ **COMPLETE** (2025-11-25)
  - **Location:** `src/config.py:172-189`
  - **Problem:** Only validates few fields, doesn't validate ranking weights sum to 1.0
  - **Impact:** Users misconfigure system without warning, suboptimal performance
  - **Fix:** Add comprehensive validation for all interdependent config options
  - **See:** code_review_2025-11-25.md

- [ ] **DOC-010**: Create Configuration Guide (~2 days)
  - **Location:** `docs/CONFIGURATION_GUIDE.md` (new file)
  - **Problem:** 150+ config options, only ~10 documented
  - **Impact:** Users can't discover advanced features, trial-and-error config
  - **Fix:** Document all config categories, common profiles, interdependencies
  - **See:** code_review_2025-11-25.md

### 📊 Code Review Summary

| Severity | Count | Status |
|----------|-------|--------|
| Critical | 5 | ✅ ALL COMPLETE |
| High | 7 | ✅ 6/7 COMPLETE (REF-016 God class split deferred) |
| Medium | 6 | ✅ ALL COMPLETE |

**Total Issues Addressed:** 17/18 tasks from code review (2025-11-25)
**Remaining:** REF-016 (God class refactoring) - larger effort, properly tracked
**Full Report:** `~/Documents/code_review_2025-11-25.md` (101 issues across 4 categories)

---

## 🚨 CRITICAL BUGS FOUND IN E2E TESTING (2025-11-20)

- [x] **BUG-015**: Health Check False Negative for Qdrant ✅ **FIXED** (2025-11-21)
  - **Component:** `src/cli/health_command.py:143`
  - **Issue:** Health check reports Qdrant as unreachable even when functional
  - **Root Cause:** Using wrong endpoint `/health` instead of `/`
  - **Fix:** Already using correct `/` endpoint with JSON validation
  - **Verification:** `curl http://localhost:6333/` returns version info successfully
  - **Status:** Code was already correct, bug may have been user-specific or already fixed

- [x] **BUG-016**: list_memories Returns Incorrect Total Count ✅ **FIXED** (2025-11-22)
  - **Component:** Memory management API
  - **Issue:** `list_memories()` returns `total: 0` when memories exist in results array
  - **Root Cause:** Was a symptom of BUG-018 (RetrievalGate blocking queries)
  - **Fix:** Resolved as duplicate - BUG-018 fix (removing RetrievalGate) resolved this issue
  - **Verification:** All 16 tests in `test_list_memories.py` pass, total_count correctly populated
  - **Status:** Already fixed, no code changes needed

- [x] **BUG-018**: Memory Retrieval Not Finding Recently Stored Memories ✅ **FIXED** (2025-11-22)
  - **Component:** Semantic search / memory retrieval
  - **Issue:** Memories stored via `store_memory()` not immediately retrievable via `retrieve_memories()`
  - **Root Cause:** RetrievalGate was blocking queries it deemed "low-value"
  - **Fix:** RetrievalGate removed from codebase (2025-11-20)
  - **Regression Tests:** Added 6 comprehensive tests in `test_bug_018_regression.py`
  - **Status:** Fixed with comprehensive test coverage to prevent recurrence

- [x] **BUG-019**: Docker Container Shows "Unhealthy" Despite Working ✅ **FIXED**
  - **Error:** `docker ps` shows Qdrant as "(unhealthy)", health check exits with -1
  - **Root Cause:** Health check uses `curl` command which doesn't exist in Qdrant container
  - **Location:** `docker-compose.yml` and `planning_docs/TEST-006_docker_compose.yml`
  - **Fix:** Changed health check from `curl -f http://localhost:6333/` to TCP socket test: `timeout 1 bash -c 'cat < /dev/null > /dev/tcp/localhost/6333' || exit 1`
  - **Result:** Container now shows "(healthy)" status, ExitCode: 0, FailingStreak: 0

- [x] **BUG-020**: Inconsistent Return Value Structures ✅ **RECLASSIFIED** (2025-11-22)
  - **Component:** API design consistency
  - **Issue:** Different methods use different success indicators
  - **Analysis:** This is NOT a bug - current API is functionally correct, just inconsistent
  - **Impact:** LOW - Users adapt to each method's return structure
  - **Recommendation:** Reclassify as enhancement (REF-015 or UX-049) for v5.0
  - **Rationale:** Standardization would be breaking change, requires proper migration path
  - **Status:** Analysis complete, recommend deferring to major version bump
  - **See:** planning_docs/BUG-020_api_consistency_analysis.md

- [x] **BUG-021**: PHP Parser Initialization Warning ✅ **FIXED** (2025-11-21)
  - **Component:** `src/memory/python_parser.py`
  - **Issue:** Warning: "Failed to initialize php parser"
  - **Root Cause:** DUPLICATE of BUG-025 - optional language imports breaking entire parser
  - **Fix:** Resolved by BUG-025 fix (lazy imports) - optional languages now skipped gracefully

- [x] **BUG-022**: Code Indexer Extracts Zero Semantic Units ✅ **RESOLVED** (2025-11-21)
  - **Component:** Code indexing / parsing
  - **Issue:** `index_codebase()` extracts 0 semantic units
  - **Root Cause:** BUG-025 broke parser initialization
  - **Fix:** Resolved by fixing BUG-025
  - **Verification:** Parser now extracts functions/classes correctly (tested with 2 units from test file)

- [x] **BUG-024**: Tests Importing Removed Modules ✅ **FIXED** (2025-11-21)
  - **Error:** 11 test files fail collection with `ModuleNotFoundError`
  - **Root Cause:** REF-010/011 removed sqlite_store/retrieval_gate modules but tests not updated
  - **Impact:** 11 test files blocked, ~150+ tests couldn't run
  - **Fix:** Updated all tests to use QdrantMemoryStore, deleted obsolete tests
  - **Result:** 2677 tests now collect successfully (up from 2569 with 11 errors)
  - **Files:** See `planning_docs/BUG-024-026_execution_summary.md`

- [x] **BUG-025**: PythonParser Fails Due to Optional Language Imports ✅ **FIXED** (2025-11-21)
  - **Error:** Parser initialization fails if ANY optional language missing
  - **Root Cause:** Module-level import of ALL languages - if any missing, entire parser disabled
  - **Impact:** Parser fallback mode completely broken, related to BUG-022
  - **Fix:** Lazy import individual language parsers, skip missing languages gracefully
  - **Result:** Parser initializes with 6 installed languages, skips 4 optional ones

- [x] **BUG-026**: Test Helper Classes Named "Test*" ✅ **FIXED** (2025-11-21)
  - **Warning:** `PytestCollectionWarning: cannot collect test class 'TestNotificationBackend'`
  - **Root Cause:** Helper class name starts with "Test" and has `__init__` constructor
  - **Fix:** Renamed `TestNotificationBackend` → `MockNotificationBackend` in 2 files
  - **Result:** Warnings removed

**Full E2E Test Report:** See `E2E_TEST_REPORT.md` for detailed findings
**Bug Hunt Report:** See `planning_docs/BUG-HUNT_2025-11-21_comprehensive_report.md`
**Fix Execution:** See `planning_docs/BUG-024-026_execution_summary.md`
**Full E2E Test Plan:** See `planning_docs/TEST-006_e2e_test_plan.md`, `planning_docs/TEST-006_e2e_bug_tracker.md`, and `planning_docs/TEST-006_e2e_testing_guide.md` for comprehensive manual testing documentation

---

## ID System
Each item has a unique ID for tracking and association with planning documents in `planning_docs/`.
Format: `{TYPE}-{NUMBER}` where TYPE = FEAT|BUG|TEST|DOC|PERF|REF|UX

## Priority System

**Prioritization Rules:**
1. Complete partially finished initiatives before starting new ones
2. Prioritize items that have greater user impact over items that have less impact

## Current Sprint

### 🔴 Critical Bugs (Blocking)

**These bugs completely break core functionality and must be fixed immediately**

- [x] **BUG-012**: MemoryCategory.CODE attribute missing ✅ **FIXED**
  - **Error:** `type object 'MemoryCategory' has no attribute 'CODE'`
  - **Impact:** Code indexing completely broken - 91% of files fail to index (10/11 failures)
  - **Location:** `src/memory/incremental_indexer.py:884` uses `MemoryCategory.CODE.value`
  - **Root Cause:** MemoryCategory enum only has: PREFERENCE, FACT, EVENT, WORKFLOW, CONTEXT
  - **Fix:** Added CODE = "code" to MemoryCategory enum in `src/core/models.py:26`
  - **Result:** All files now index successfully (11/11), 867 semantic units extracted

- [x] **BUG-013**: Parallel embeddings PyTorch model loading failure ✅ **FIXED**
  - **Error:** "Cannot copy out of meta tensor; no data! Please use torch.nn.Module.to_empty() instead of torch.nn.Module.to()"
  - **Impact:** Parallel embedding generation fails, blocks indexing with parallel mode enabled
  - **Location:** `src/embeddings/parallel_generator.py:41` - `model.to("cpu")`
  - **Root Cause:** Worker processes can't use `.to()` on models loaded from main process
  - **Fix:** Changed to `SentenceTransformer(model_name, device="cpu")` instead of `.to("cpu")`
  - **Result:** Parallel embeddings work with 9.7x speedup (37.17 files/sec vs 3.82)

- [x] **BUG-014**: cache_dir_expanded attribute missing from ServerConfig ✅ **FIXED**
  - **Error:** `'ServerConfig' object has no attribute 'cache_dir_expanded'`
  - **Impact:** Health check command crashes when checking cache statistics
  - **Location:** `src/cli/health_command.py:371`
  - **Root Cause:** Code references non-existent attribute; cache is a file, not a directory
  - **Fix:** Changed to use `embedding_cache_path_expanded` and check file size directly
  - **Result:** Health command works perfectly, shows all system statistics

- [x] **BUG-027**: Incomplete SQLite Removal (REF-010) ✅ **FIXED** (2025-11-21)
  - **Error:** 185 ERROR tests with "Input should be 'qdrant'" validation errors
  - **Impact:** 16+ test files broken, 185 runtime test errors
  - **Root Cause:** REF-010 removed SQLite backend but tests still try to use it
  - **Location:** Config validation in `src/config.py:19` only accepts "qdrant"
  - **Fix:** Updated 12 test files to use storage_backend="qdrant", removed sqlite_path parameters
  - **Result:** All integration and unit tests now use Qdrant backend correctly
  - **See:** planning_docs/BUG-HUNT_2025-11-21_runtime_failures.md

- [x] **BUG-028**: Dict vs Object Type Mismatch in Health Components ✅ **FIXED** (2025-11-21)
  - **Error:** "'dict' object has no attribute 'content'" and "'dict' object has no attribute 'created_at'"
  - **Impact:** 8+ FAILED tests, health monitoring system broken
  - **Root Cause:** get_all_memories() returns List[Dict] but consumers expect List[MemoryUnit] objects
  - **Location:** src/memory/health_scorer.py:240, src/memory/health_jobs.py:168
  - **Fix:** Changed all memory.attribute to memory['attribute'], added enum conversions and datetime parsing
  - **Result:** Health monitoring system now works correctly with dictionary access
  - **See:** planning_docs/BUG-HUNT_2025-11-21_runtime_failures.md

- [x] **BUG-029**: Category Changed from "context" to "code" ✅ **FIXED** (2025-11-21)
  - **Error:** "AssertionError: assert 'code' == 'context'"
  - **Impact:** 2+ FAILED tests, outdated documentation
  - **Root Cause:** Code indexing category changed to MemoryCategory.CODE but tests/comments not updated
  - **Location:** tests/integration/test_indexing_integration.py:133, src/core/server.py:3012 comment
  - **Fix:** Updated test assertions to expect "code", updated outdated comment
  - **Result:** All indexing tests now pass with correct category expectations
  - **See:** planning_docs/BUG-HUNT_2025-11-21_runtime_failures.md

- [x] **BUG-030**: Invalid Qdrant Point IDs in Test Fixtures ✅ **FIXED** (2025-11-21)
  - **Error:** "400 Bad Request: value test-1 is not a valid point ID"
  - **Impact:** 4+ ERROR tests in backup/export functionality
  - **Root Cause:** Tests use string IDs like "test-1" but Qdrant requires integers or UUIDs
  - **Location:** tests/unit/test_backup_export.py:30, 44
  - **Fix:** Replaced "test-1", "test-2" with str(uuid.uuid4())
  - **Result:** Test fixtures now use valid UUID format for Point IDs
  - **See:** planning_docs/BUG-HUNT_2025-11-21_runtime_failures.md

- [x] **BUG-031**: Test Collection Count Discrepancy (Documentation) ✅ **FIXED** (2025-11-21)
  - **Issue:** Test count varies between runs (documented: 2,723, actual: 2,677-2,744)
  - **Impact:** Misleading documentation
  - **Location:** CLAUDE.md metrics section
  - **Fix:** Updated CLAUDE.md to reflect ~2,740 tests with note about environment variability
  - **Result:** Documentation now accurately reflects test count range
  - **See:** planning_docs/BUG-HUNT_2025-11-21_runtime_failures.md

- [x] **BUG-032**: Coverage Metric Discrepancy (Documentation) ✅ **FIXED** (2025-11-21)
  - **Issue:** CLAUDE.md claims 67% coverage, actual is 59.6% overall / 71.2% core modules
  - **Impact:** Misleading documentation (but core modules meet target)
  - **Location:** CLAUDE.md Current State section
  - **Fix:** Updated coverage metrics with accurate breakdown (59.6% overall, 71.2% core modules)
  - **Result:** Documentation now clearly explains overall vs core module coverage
  - **See:** planning_docs/BUG-HUNT_2025-11-21_runtime_failures.md

- [x] **BUG-033**: Health Scheduler Missing `await` Keyword ✅ **FIXED** (2025-11-22)
  - **Component:** Health monitoring system
  - **Issue:** Health scheduler initialization failed due to missing `await` on async function call
  - **Location:** `src/memory/health_scheduler.py:73`
  - **Root Cause:** Missing `await` on `create_store()` call, redundant `await store.initialize()`
  - **Fix:** Added `await` to `create_store()`, removed redundant initialization, fixed scheduler restart
  - **Result:** All 33 tests passing, coverage improved from 0% to 90.12%
  - **Impact:** Health scheduler now works in production, all maintenance jobs functional

### 🟡 Tier 2: Core Functionality Extensions

**These extend core capabilities with new features (nice-to-have)**

#### Code Intelligence Enhancements

- [x] **FEAT-046**: Indexed Content Visibility ✅ **COMPLETE**
  - [x] Implement `get_indexed_files` MCP tool
  - [x] Implement `list_indexed_units` MCP tool (functions, classes, etc.)
  - [x] Filter by project, language, file_pattern, unit_type
  - [x] Show indexing metadata: last indexed, unit count
  - [x] Pagination with auto-capped limits (1-500)
  - [x] Tests: 17 tests, all passing
  - **Impact:** Transparency into what's indexed, debugging aid
  - **Use case:** "What files are indexed in this project?" or "Show all Python functions indexed"
  - **Enhances:** `get_status` (which only shows counts)

- [x] **FEAT-049**: Intelligent Code Importance Scoring ✅ **COMPLETE** (2025-11-24)
  - [x] **Discovery:** Feature was already fully implemented and enabled by default
  - [x] ImportanceScorer implemented in src/analysis/ (311 lines)
  - [x] Complexity analyzer, usage analyzer, criticality analyzer all complete
  - [x] All 129 tests passing (100% pass rate)
  - [x] Scores distributed across 0.0-1.0 range (validated: 0.297 to 0.577 for test cases)
  - [x] Configuration: `enable_importance_scoring=True` by default
  - **Note:** TODO description was stale from planning phase; implementation was complete months ago
  - **Impact:** Importance scores are dynamic and useful for retrieval ranking, filtering, prioritization
  - **Use case:** "Show me the most important functions in this codebase" returns core logic, not utilities
  - **See:** planning_docs/FEAT-049_importance_scoring_plan.md, planning_docs/FEAT-049_completion_report.md

- [x] **FEAT-055**: Git Storage and History Search ✅ **COMPLETE** (2025-11-22)
  - [x] Implement `store_git_commits()` method in QdrantMemoryStore
  - [x] Implement `store_git_file_changes()` method
  - [x] Implement `search_git_commits()` - Semantic search over commit history
  - [x] Implement `get_file_history()` - Get commits affecting a file
  - [x] Index git history during codebase indexing
  - [x] Support semantic search across commit messages and diffs
  - [x] Tests: 76 comprehensive tests (all passing)
  - **Impact:** Enable semantic search over project history, find commits by intent
  - **Use case:** "Find commits related to authentication changes" or "Show history of this file"

- [x] **FEAT-048**: Dependency Graph Visualization ✅ **COMPLETE** (2025-11-18)
  - [x] Implement `get_dependency_graph` MCP tool
  - [x] Export formats: DOT (Graphviz), JSON (D3.js), Mermaid
  - [x] Filter by depth, file pattern, language
  - [x] Highlight circular dependencies
  - [x] Include node metadata (file size, unit count, last modified)
  - [x] Tests: 84 comprehensive tests (100% passing)
  - **Impact:** Architecture visualization and understanding
  - **Use case:** "Export dependency graph for visualization in Graphviz"
  - **See:** planning_docs/FEAT-048_dependency_graph_visualization.md, planning_docs/FEAT-048_example_outputs.md

#### MCP RAG Tool Enhancements

**Based on empirical evaluation (QA review + architecture discovery tasks), these enhancements address critical gaps in the MCP RAG semantic search capabilities.**

**Phase 1: Quick Wins (2 weeks)**

- [x] **FEAT-056**: Advanced Filtering & Sorting ✅ **COMPLETE** (2025-11-23)
  - [x] Added `file_pattern` parameter to search_code (glob patterns like "*.test.py", "src/**/auth*.ts")
  - [x] Added `exclude_patterns` to filter out test files, generated code, etc.
  - [x] Added `complexity_min` / `complexity_max` filters (cyclomatic complexity)
  - [x] Added `line_count_min` / `line_count_max` filters
  - [x] Added `modified_after` / `modified_before` date range filters
  - [x] Added `sort_by` parameter: relevance (default), complexity, size, recency, importance
  - [x] Added `sort_order` parameter: asc/desc
  - [x] All 22 tests passing
  - **Impact:** Enables precise filtering, eliminates grep usage for pattern matching
  - **See:** planning_docs/FEAT-056_advanced_filtering_plan.md

- [x] **FEAT-057**: Better UX & Discoverability ✅ **COMPLETE** (2025-11-23)
  - [x] Added `suggest_queries()` MCP tool with intent-based suggestions
  - [x] Added faceted search results (languages, unit_types, files, directories)
  - [x] Added natural language result summaries
  - [x] Added "Did you mean?" spelling suggestions
  - [x] Added interactive refinement hints
  - [x] All 43 tests passing
  - **Impact:** Reduced learning curve, better discoverability, improved query success rate
  - **See:** planning_docs/FEAT-057_ux_discoverability_plan.md

- [x] **FEAT-058**: Pattern Detection (Regex + Semantic Hybrid) ✅ **COMPLETE** (2025-11-22)
  - [x] Added `pattern` parameter to search_code (regex pattern matching)
  - [x] Implemented `pattern_mode`: "filter" (semantic + regex filter), "boost" (regex boosts scores), "require" (must match both)
  - [x] Created PatternMatcher class with regex compilation and result filtering
  - [x] Integrated with existing search infrastructure
  - [x] 56 comprehensive tests (40 unit + 16 integration), 100% passing
  - **Impact:** Enables precise code pattern detection, combines semantic and structural search
  - **See:** planning_docs/FEAT-058_pattern_detection_plan.md
  - **Use case:** "Find all TODO markers in authentication code" or "Show error handlers with bare except:"
  - **Tests:** 15-20 tests for pattern modes, presets, hybrid search
  - **See:** planning_docs/FEAT-058_pattern_detection_plan.md

**Phase 2: Structural Analysis (4 weeks)**

- [ ] **FEAT-059**: Structural/Relational Queries (~2 weeks) 🔥🔥🔥
  - **Current Gap:** No call graph analysis, dependency traversal, or relationship queries
  - **Problem:** Architecture discovery needed "find all callers of this function" and "show dependency chains" - impossible with current tools
  - **Proposed Solution:**
    - [ ] Add `find_callers(function_name, project)` - Find all functions calling this function
    - [ ] Add `find_callees(function_name, project)` - Find all functions called by this function
    - [ ] Add `find_implementations(interface_name)` - Find all implementations of interface/trait
    - [ ] Add `find_dependencies(file_path)` - Get dependency graph for a file (imports/requires)
    - [ ] Add `find_dependents(file_path)` - Get reverse dependencies (what imports this file)
    - [ ] Add `get_call_chain(from_function, to_function)` - Show call path between functions
  - **Impact:** Enables architectural analysis, refactoring planning, impact analysis - transforms discovery from 45min → 5min
  - **Use case:** "Show me all callers of authenticate()" or "What's the call chain from main() to database?"
  - **Tests:** 25-30 tests for call graph, dependencies, edge cases
  - **See:** planning_docs/FEAT-059_structural_queries_plan.md

- [x] **FEAT-060**: Code Quality Metrics & Hotspots (~2 weeks) 🔥🔥 ✅ COMPLETE (2025-11-24)
  - **Current Gap:** No code quality analysis, duplication detection, or complexity metrics
  - **Problem:** QA review manually searched for code smells, complex functions, duplicates - took 30+ minutes
  - **Proposed Solution:**
    - [ ] Add `find_quality_hotspots(project)` - Returns top 20 issues: high complexity, duplicates, long functions, deep nesting
    - [ ] Add `find_duplicates(similarity_threshold=0.85)` - Semantic duplicate detection
    - [ ] Add `get_complexity_report(file_or_project)` - Cyclomatic complexity breakdown
    - [ ] Add quality metrics to search results (complexity, duplication score, maintainability index)
    - [ ] Add filters: `min_complexity`, `has_duplicates`, `long_functions` (>100 lines)
  - **Impact:** Automated code review, 60x faster than manual (30min → 30sec), objective quality metrics
  - **Use case:** "Show me the most complex functions in this project" or "Find duplicate authentication logic"
  - **Tests:** 20-25 tests for metrics, hotspots, duplication
  - **See:** planning_docs/FEAT-060_quality_metrics_plan.md

- [ ] **FEAT-061**: Git/Historical Integration (~1 week) 🔥
  - **Current Gap:** No git history, change frequency, or churn analysis
  - **Problem:** Architecture discovery couldn't identify "frequently changed files" or "recent refactorings"
  - **Proposed Solution:**
    - [ ] Add `search_git_history(query, since, until)` - Semantic search over commit messages and diffs
    - [ ] Add `get_change_frequency(file_or_function)` - How often does this change? (commits/month)
    - [ ] Add `get_churn_hotspots(project)` - Files with highest change frequency
    - [ ] Add `get_recent_changes(project, days=30)` - Recent modifications with semantic context
    - [ ] Add `blame_search(pattern)` - Who wrote code matching this pattern?
  - **Impact:** Understand evolution, identify unstable code, find domain experts
  - **Use case:** "Show files changed most frequently in auth code" or "Who worked on the API layer recently?"
  - **Tests:** 15-20 tests for git integration, change analysis
  - **See:** planning_docs/FEAT-061_git_integration_plan.md

**Phase 3: Visualization (4-6 weeks)**

- [ ] **FEAT-062**: Architecture Visualization & Diagrams (~4-6 weeks) 🔥
  - **Current Gap:** No visual representation of architecture, dependencies, or call graphs
  - **Problem:** Architecture discovery relied on mental modeling - difficult to understand complex systems, explain to others, or document
  - **Proposed Solution:**
    - [ ] Add `visualize_architecture(project)` - Generate architecture diagram (components, layers, boundaries)
    - [ ] Add `visualize_dependencies(file_or_module)` - Dependency graph with depth control
    - [ ] Add `visualize_call_graph(function_name)` - Call graph showing function relationships
    - [ ] Export formats: Graphviz DOT, Mermaid, D3.js JSON, PNG/SVG images
    - [ ] Interactive web viewer with zoom, pan, filtering
    - [ ] Highlight patterns: circular dependencies, deep nesting, tight coupling
  - **Impact:** 10x faster architecture understanding, shareable diagrams, documentation automation
  - **Use case:** "Show me the architecture diagram for this project" or "Visualize dependencies for the auth module"
  - **Tests:** 20-25 tests for visualization, exports, patterns
  - **See:** planning_docs/FEAT-062_architecture_visualization_plan.md

### 🟢 Tier 3: UX Improvements & Performance Optimizations

**User experience and performance improvements**

#### Error Handling & Graceful Degradation

- [x] **UX-012**: Graceful degradation ✅ **COMPLETE**
  - [x] Auto-fallback: Qdrant unavailable → SQLite
  - [x] Auto-fallback: Rust unavailable → Python parser
  - [x] Warn user about performance implications
  - [x] Option to upgrade later
  - **Implementation:** Config flags `allow_qdrant_fallback`, `allow_rust_fallback`, `warn_on_degradation`
  - **Files:** `src/store/factory.py`, `src/memory/incremental_indexer.py`, `src/core/degradation_warnings.py`
  - **Tests:** 15 tests in `test_graceful_degradation.py`, all passing
  - **Impact:** Better first-run experience, no hard failures for missing dependencies

#### Health & Monitoring

- [ ] **UX-032**: Health Check Improvements (~2 days) 🔥🔥
  - [ ] **Confirm overall feature design with user before proceeding**
  - [ ] Extend existing health check command
  - [ ] Add: Qdrant latency monitoring (warn if >20ms)
  - [ ] Add: Cache hit rate display (warn if <70%)
  - [ ] Add: Token savings this week
  - [ ] Add: Stale project detection (not indexed in 30+ days)
  - [ ] Proactive recommendations: "Consider upgrading to Qdrant"
  - [ ] Show indexed projects count and size
  - **Impact:** Proactive issue detection, optimization guidance

#### Performance Optimizations

- [x] **PERF-002**: GPU acceleration ✅ **COMPLETE**
  - [x] Use CUDA for embedding model
  - [x] Target: 50-100x speedup
  - **Impact:** Massive speedup (requires GPU hardware)
  - **Status:** Merged to main (2025-11-24)

---

### 🌐 Tier 4: Language Support Extensions

- [ ] **FEAT-007**: Add support for Ruby (~3 days)
  - [ ] tree-sitter-ruby integration
  - [ ] Method, class, module extraction

- [x] **FEAT-008**: Add support for PHP ✅ **COMPLETE**
  - [x] tree-sitter-php integration
  - [x] Function, class, trait extraction

- [x] **FEAT-009**: Add support for Swift ✅ **COMPLETE**
  - [x] tree-sitter-swift integration
  - [x] Function, struct, class extraction

- [x] **FEAT-010**: Add support for Kotlin ✅ **COMPLETE**
  - [x] tree-sitter-kotlin integration
  - [x] Function, class, object extraction

### 🚀 Tier 5: Advanced/Future Features

- [x] **FEAT-016**: Auto-indexing ✅ **MERGED** (2025-11-24)
  - [x] Automatically index on project open
  - [x] Background indexing for large projects
  - [x] ProjectIndexTracker for staleness detection
  - [x] AutoIndexingService with foreground/background modes
  - [x] 11 new configuration options
  - [x] MCP tools: get_indexing_status(), trigger_reindex()

- [ ] **FEAT-017**: Multi-repository support
  - [ ] Index across multiple repositories
  - [ ] Cross-repo code search

- [x] **FEAT-018**: Query DSL ✅ **MERGED** (2025-11-24)
  - [x] Advanced filters (by file pattern, date, author, etc.)
  - [x] Complex query expressions
  - **Status:** MVP complete and merged to main
  - **Implementation:** Query DSL parser with filter aliases, date filters, exclusions
  - **Testing:** 20 comprehensive tests, all passing
  - **Files:** `src/search/query_dsl_parser.py`, `tests/unit/test_query_dsl_parser.py`
  - **Commit:** af53087

- [ ] **FEAT-014**: Semantic refactoring
  - [ ] Find all usages semantically
  - [ ] Suggest refactoring opportunities

- [ ] **FEAT-015**: Code review features
  - [ ] LLM-powered suggestions based on patterns
  - [ ] Identify code smells

- [ ] **FEAT-050**: Track cache usage in queries
  - [ ] Add cache hit/miss tracking to retrieve_memories()
  - [ ] Include used_cache flag in QueryResponse
  - **Location:** src/core/server.py:631
  - **Discovered:** 2025-11-20 during code review

- [ ] **FEAT-051**: Query-based deletion for Qdrant
  - [ ] Implement deletion by query filters instead of memory IDs
  - [ ] Support clearing entire project indexes
  - **Location:** src/core/server.py:2983
  - **Discovered:** 2025-11-20 during code review

- [ ] **FEAT-052**: Map project_name to repo_path for git history
  - [ ] Add configuration mapping between project names and repository paths
  - [ ] Enable git history search by project_name instead of hardcoded paths
  - **Location:** src/core/server.py:3448
  - **Discovered:** 2025-11-20 during code review

- [ ] **FEAT-053**: Enhanced file history with diff content
  - [ ] Include diff content analysis in file history search
  - [ ] Match changes in diff content, not just commit messages
  - **Location:** src/core/server.py:3679
  - **Discovered:** 2025-11-20 during code review

- [ ] **FEAT-054**: File pattern and language filtering for multi-repo search
  - [ ] Add file_pattern parameter to cross-project search
  - [ ] Add language filter support to search_all_projects()
  - **Location:** src/memory/multi_repository_search.py:221
  - **Discovered:** 2025-11-20 during code review

- [ ] **REF-011**: Integrate ProjectArchivalManager with metrics
  - [ ] Connect metrics_collector to ProjectArchivalManager
  - [ ] Enable accurate active vs archived project counts
  - **Location:** src/monitoring/metrics_collector.py:201
  - **Discovered:** 2025-11-20 during code review

- [ ] **REF-012**: Implement rollback support for bulk operations
  - [ ] Add soft delete capability for bulk operations
  - [ ] Enable rollback of bulk deletions
  - **Location:** src/memory/bulk_operations.py:394
  - **Discovered:** 2025-11-20 during code review

- [x] **UX-026**: Web dashboard MVP ✅ **COMPLETE**
  - [x] Basic web UI with statistics
  - [x] Project breakdown display
  - [x] Category and lifecycle charts
  - [x] Recent activity view
  - **Status**: MVP complete, see enhancements below

#### Web Dashboard Enhancements (Post-MVP)

**Phase 1: Core Usability (~20-24 hours, 1-2 weeks)**

**Progress**: 7/15 features complete (47%). See `planning_docs/UX-034-048_dashboard_enhancements_progress.md` for comprehensive implementation guide. All Phase 4 "Quick Wins" features completed!

- [x] **UX-034**: Dashboard Search and Filter Panel ✅ **COMPLETE** (~3 hours)
  - [x] Global search bar for memories (with 300ms debouncing)
  - [x] Filter dropdowns: project, category, date range, lifecycle state
  - [x] Real-time filtering of displayed data (client-side)
  - [x] URL parameters for shareable filtered views
  - [x] Empty state messaging and filter badge
  - [x] Responsive mobile design
  - **Impact**: Users can find specific memories/projects quickly
  - **Implementation**: Client-side filtering, ~300 lines of code added
  - **Reference**: planning_docs/UX-034_search_filter_panel.md

- [x] **UX-035**: Memory Detail Modal ✅ **COMPLETE** (~1 hour)
  - [x] Click any memory to see full details
  - [x] Full content with syntax highlighting for code
  - [x] Display all metadata: tags, importance, provenance, timestamps
  - [x] Modal with smooth animations (fadeIn, slideUp)
  - [x] Escape key support and click-outside-to-close
  - [x] Responsive mobile design
  - **Impact**: Transform from view-only to interactive tool
  - **Implementation**: Modal overlay with basic syntax highlighting (~350 lines)
  - **Reference**: planning_docs/UX-034-048_dashboard_enhancements_progress.md

- [x] **UX-036**: Health Dashboard Widget ✅ **COMPLETE** (~4-6 hours)
  - [x] Health score gauge (0-100) with color coding (green/yellow/red)
  - [x] Active alerts count with severity badges (CRITICAL/WARNING/INFO)
  - [x] Performance metrics: P95 search latency, cache hit rate
  - [x] SVG-based semicircular gauge visualization
  - [x] Auto-refresh every 30 seconds
  - **Implementation**: Backend `/api/health` endpoint + frontend widget
  - **Files**: src/dashboard/web_server.py, src/dashboard/static/dashboard.js, index.html, dashboard.css
  - **Status**: Merged on 2025-11-20 (commit f24784e)

- [x] **UX-037**: Interactive Time Range Selector ✅ **COMPLETE** (2025-11-22)
  - [x] Preset buttons: Last Hour, Today, Last 7 Days, Last 30 Days, All Time
  - [x] Custom date picker with range selection
  - [x] Real-time chart updates based on selection
  - [x] LocalStorage persistence across sessions
  - [x] Integrated with existing dashboard charts and metrics
  - **Impact**: Time-based analytics and historical pattern analysis
  - **See:** Integrated with dashboard tests

**Phase 2: Advanced Analytics (~32-40 hours, 1-2 weeks)**

- [x] **UX-038**: Trend Charts and Sparklines (~2.5 hours) ✅ **COMPLETE** (2025-11-22)
  - [x] Enhanced existing Chart.js charts with zoom/pan interactivity
  - [x] Line charts for memory count and latency with hover effects
  - [x] Bar chart for search volume with gradients
  - [x] Performance insights in tooltips (Excellent/Good/Fair indicators)
  - [x] Dark mode support for all chart elements
  - [x] Responsive design with mobile layout
  - [x] Hint text explaining zoom/pan functionality
  - **Impact**: Interactive analytics tools for pattern identification
  - **Note**: Heatmap and P50/P95/P99 metrics deferred (require backend changes)
  - **See**: planning_docs/UX-038_trend_charts_implementation.md

- [ ] **UX-039**: Memory Relationships Graph Viewer (~10-12 hours)
  - [ ] Interactive graph using D3.js or vis.js
  - [ ] Click memory to see relationships (SUPERSEDES, CONTRADICTS, RELATED_TO)
  - [ ] Color-coded by relationship type
  - [ ] Zoom/pan controls
  - **Impact**: Understand knowledge structure, discover related content
  - **Data Source**: Existing MemoryRelationship model in database
  - **Reference**: planning_docs/UX-026_dashboard_enhancement_analysis.md

- [ ] **UX-040**: Project Comparison View (~6-8 hours)
  - [ ] Select 2-4 projects to compare side-by-side
  - [ ] Bar charts: memory count, file count, function count
  - [ ] Category distribution comparison
  - [ ] Performance metrics comparison (index time, search latency)
  - **Impact**: Identify outliers, understand relative project complexity
  - **Reference**: planning_docs/UX-026_dashboard_enhancement_analysis.md

- [ ] **UX-041**: Top Insights and Recommendations (~8-10 hours)
  - [ ] Automatic insight detection:
    - "Project X hasn't been indexed in 45 days"
    - "Search latency increased 40% this week"
    - "15 memories marked 'not helpful' - consider cleanup"
    - "Cache hit rate below 70% - consider increasing cache size"
  - [ ] Priority/severity levels
  - [ ] One-click actions ("Index Now", "View Memories", "Adjust Settings")
  - **Impact**: Proactive guidance to improve memory system usage
  - **Backend**: Add insight detection logic
  - **Reference**: planning_docs/UX-026_dashboard_enhancement_analysis.md

**Phase 3: Productivity Features (~16-22 hours, 1 week)**

- [ ] **UX-042**: Quick Actions Toolbar (~6-8 hours)
  - [ ] Buttons for: Index Project, Create Memory, Export Data, Run Health Check
  - [ ] Forms with validation
  - [ ] Status feedback (loading, success, error)
  - **Impact**: Avoid switching to CLI for frequent tasks
  - **Reference**: planning_docs/UX-026_dashboard_enhancement_analysis.md

- [ ] **UX-043**: Export and Reporting (~6-8 hours)
  - [ ] Export formats: JSON, CSV, Markdown, PDF (summary report)
  - [ ] Filters: by project, date range, category
  - [ ] Optional: Scheduled reports (daily/weekly email)
  - **Impact**: Share insights, backup data, integration with other tools
  - **Data Source**: Existing export_memories() MCP tool
  - **Reference**: planning_docs/UX-026_dashboard_enhancement_analysis.md

**Phase 4: UX Polish (~12-17 hours, 3-5 days)** ✅ **COMPLETE**

- [x] **UX-044**: Dark Mode Toggle ✅ **COMPLETE** (~2 hours)
  - [x] Dark color scheme with CSS variables
  - [x] Toggle switch in header with sun/moon icons
  - [x] localStorage persistence
  - [x] Keyboard shortcut 'd' for toggle
  - **Impact**: Reduced eye strain, professional appearance
  - **Implementation**: Theme management with data-theme attribute, ~80 lines
  - **Reference**: planning_docs/UX-034-048_dashboard_enhancements_progress.md

- [x] **UX-045**: Keyboard Shortcuts ✅ **COMPLETE** (~2 hours)
  - [x] `/` - Focus search
  - [x] `r` - Refresh data
  - [x] `d` - Toggle dark mode
  - [x] `c` - Clear filters
  - [x] `?` - Show keyboard shortcuts help
  - [x] `Esc` - Close modals
  - **Impact**: Power user productivity boost
  - **Implementation**: Global keydown handler + help modal, ~90 lines
  - **Reference**: planning_docs/UX-034-048_dashboard_enhancements_progress.md

- [x] **UX-046**: Tooltips and Help System ✅ **COMPLETE** (~3 hours)
  - [x] Tippy.js integration from CDN
  - [x] Tooltips on all filter controls
  - [x] Help icons (ⓘ) on section headers
  - [x] Detailed explanations for categories, lifecycle, etc.
  - **Impact**: Reduced learning curve, better discoverability
  - **Implementation**: Tippy.js with data attributes, ~46 lines
  - **Reference**: planning_docs/UX-034-048_dashboard_enhancements_progress.md

- [x] **UX-047**: Loading States and Skeleton Screens ✅ **COMPLETE** (~2 hours)
  - [x] Animated skeleton screens with gradient
  - [x] Different skeleton types (cards, lists, stats)
  - [x] Applied to all loading points
  - **Impact**: Professional UX, perceived performance improvement
  - **Implementation**: CSS animations + JavaScript injection, ~55 lines
  - **Reference**: planning_docs/UX-034-048_dashboard_enhancements_progress.md

- [x] **UX-048**: Error Handling and Retry ✅ **COMPLETE** (~3-4 hours)
  - [x] Toast notification system (error, warning, success, info)
  - [x] Automatic retry with exponential backoff (3 attempts)
  - [x] Offline detection and reconnection handling
  - [x] Auto-dismiss after 5 seconds
  - **Impact**: Better error UX, resilient to network issues
  - **Implementation**: Toast system + fetchWithRetry + offline listeners, ~140 lines
  - **Reference**: planning_docs/UX-034-048_dashboard_enhancements_progress.md

- [ ] **UX-027**: VS Code extension (~2-3 weeks)
  - [ ] Inline code search results
  - [ ] Memory panel
  - [ ] Quick indexing actions
  - [ ] Status bar integration

- [ ] **UX-028**: Telemetry & analytics (opt-in) (~1 week)
  - [ ] Usage patterns (opt-in, privacy-preserving)
  - [ ] Error frequency tracking
  - [ ] Performance metrics
  - [ ] Feature adoption rates
  - [ ] Helps identify UX issues in the wild

### 🔨 Tier 6: Refactoring & Tech Debt

- [x] **REF-010**: Remove SQLite fallback, require Qdrant ✅ **COMPLETE** (~1 day) 🔥
  - **Rationale:** SQLite mode provides poor UX for code search (keyword-only, no semantic similarity, misleading 0.700 scores). Empirical evaluation (EVAL-001) showed it adds complexity without value.
  - [x] Remove SQLite fallback logic from `src/store/__init__.py` and `src/store/factory.py`
  - [x] Remove `allow_qdrant_fallback` config option from ServerConfig (deprecated configs ignored for backward compatibility)
  - [x] Update `create_memory_store()` and `create_store()` to fail fast if Qdrant unavailable
  - [x] Update error messages with actionable setup instructions
  - [x] Keep `src/store/sqlite_store.py` for backward compatibility (deprecated, shows warning)
  - [x] Update documentation to require Qdrant for code search (README.md)
  - [x] Add `validate-setup` CLI command to check Qdrant availability
  - [x] Update tests: `test_graceful_degradation.py`, `test_config.py`, `test_actionable_errors.py`
  - [x] Add clear error in `QdrantConnectionError` with setup instructions
  - **Benefits:** Simpler architecture, clear expectations, better error messages, no misleading degraded mode
  - **Implemented:** 2025-11-19

- [ ] **REF-007**: Consolidate two server implementations
  - Merge old mcp_server.py with new src/core/
  - Unified architecture

- [ ] **REF-008**: Remove deprecated API usage
  - Update to latest Qdrant APIs
  - Update to latest MCP SDK

- [ ] **REF-013**: Split Monolithic Core Server (~4-6 months) 🔥🔥🔥
  - [x] **Phase 1 COMPLETE** ✅ (2025-11-24): HealthService Extraction
    - [x] Extracted 9 health methods (~507 lines) into src/services/health_service.py
    - [x] Created 44 tests (28 unit + 16 integration, 100% passing)
    - [x] Zero breaking changes, full backward compatibility via delegation
    - [x] Proof of concept validates service extraction approach
    - **See:** planning_docs/REF-013_PHASE1_BASELINE.md, REF-013_PHASE1_COMPLETION_SUMMARY.md
  - **Current State:** `src/core/server.py` is 5,192 lines - violates Single Responsibility Principle
  - **Problem:** Difficult to test, understand, modify, and maintain. High coupling, low cohesion.
  - **Impact:** Slows down development, increases bug risk, makes onboarding difficult
  - **Remaining Phases:** Extract remaining services (MemoryService, CodeIndexingService, QueryService, CrossProjectService)
  - **Proposed Solution:** Continue extracting into domain-specific service modules:
    - [x] `HealthService` - Monitoring, metrics, alerts, remediation ✅ COMPLETE
    - [ ] `MemoryService` - Memory storage, retrieval, lifecycle management
    - [ ] `CodeIndexingService` - Code indexing, search, similar code
    - [ ] `CrossProjectService` - Multi-repository search and consent
    - [ ] `QueryService` - Query expansion, intent detection, hybrid search
  - **Approach:**
    - [x] Create service interfaces with clear contracts ✅ (validated in Phase 1)
    - [x] Extract one service at a time (incremental refactor) ✅ (Phase 1 complete)
    - [x] Maintain 100% backward compatibility during transition ✅ (proven)
    - [x] Add integration tests for each service ✅ (44 tests for HealthService)
    - [ ] Update MCP server to use new services (partially done for HealthService)
    - [ ] Continue with remaining 4 services (4-5 months estimated)
  - **Success Criteria:** No file >1000 lines, clear separation of concerns, improved test coverage
  - **Priority:** Critical for long-term maintainability
  - **Next:** Phase 2 - MemoryService extraction recommended
  - **See:** `planning_docs/REF-013_split_server_implementation_plan.md`

- [ ] **TEST-007**: Increase Test Coverage to 80%+ (~2-3 months) 🔥🔥
  - **Current State:** 63.68% overall coverage (7,291 of 20,076 lines uncovered)
  - **Critical Gaps:**
    - `src/core/security_logger.py` - 0% (99 lines) 🔴 CRITICAL
    - `src/dashboard/web_server.py` - 0% (299 lines) 🔴 CRITICAL
    - `src/memory/health_scheduler.py` - 0% (172 lines) 🔴 CRITICAL
    - `src/memory/duplicate_detector.py` - 0% (93 lines)
    - `src/router/retrieval_predictor.py` - 0% (82 lines)
    - 20+ modules below 60% coverage
  - **Target:** 80%+ for core modules (src/core, src/store, src/memory, src/embeddings)
  - **Approach:**
    - [ ] Phase 1: Critical modules (security_logger, web_server, health_scheduler) - 0% → 80%
    - [ ] Phase 2: Low coverage modules (<30%) to 60%+
    - [ ] Phase 3: Medium coverage modules (60-79%) to 80%+
    - [ ] Add missing integration tests for end-to-end workflows
    - [ ] Add edge case and error path tests
  - **Impact:** Increased confidence, fewer regressions, better code quality
  - **Priority:** High - essential for production readiness
  - **See:** `planning_docs/TEST-007_coverage_improvement_plan.md`

- [ ] **REF-014**: Extract Qdrant-Specific Logic (~1-2 months) 🔥
  - **Current State:** Qdrant-specific code leaks into business logic
  - **Problem:** 2,328-line `qdrant_store.py` with complex Qdrant queries, tight coupling
  - **Impact:** Difficult to swap backends, test business logic, understand data flow
  - **Proposed Solution:** Repository pattern with clear domain models
    - [ ] Define domain repository interface (independent of Qdrant)
    - [ ] Create domain models for search results, filters, pagination
    - [ ] Implement mapper layer (domain models ↔ Qdrant models)
    - [ ] Refactor QdrantStore to implement domain repository
    - [ ] Update business logic to use domain models only
    - [ ] Add integration tests with mock repository
  - **Benefits:** Cleaner architecture, easier testing, potential for alternative backends
  - **Priority:** High - improves architecture quality
  - **See:** `planning_docs/REF-014_repository_pattern_plan.md`

- [x] **PERF-007**: Connection Pooling for Qdrant ✅ **COMPLETE** (2025-11-24)
  - [x] Core connection pool implementation (src/store/connection_pool.py - 540 lines)
  - [x] Health checking (src/store/connection_health_checker.py - 289 lines)
  - [x] Pool monitoring (src/store/connection_pool_monitor.py - 367 lines)
  - [x] Comprehensive unit tests added (56 tests total):
    - [x] Connection pool tests (33 tests) - initialization, acquire/release, exhaustion, recycling, metrics
    - [x] Health checker tests (23 tests) - fast/medium/deep checks, statistics, concurrent operations
  - [x] All tests passing (56 passed, 1 skipped)
  - [x] Test coverage: 97%+ for connection pool modules
  - **Configuration:** 11 config options (pool size, retry, timeouts, health checks)
  - **Impact:** Supports higher concurrent request volumes, better reliability, efficient resource utilization
  - **See:** `planning_docs/PERF-007_connection_pooling_plan.md`

- [x] **REF-002**: Add Structured Logging ✅ **COMPLETE** (~1 hour)
  - Created `src/logging/structured_logger.py` with JSON formatter
  - 19 comprehensive tests, all passing
  - Backward compatible with existing logging patterns

- [x] **REF-003**: Split Validation Module ✅ **COMPLETE** (~1.5 hours)
  - Split monolithic validation.py (532 lines) into separate modules
  - Prevents circular import issues by separating concerns
  - Maintains backward compatibility through __init__.py exports

- [x] **REF-005**: Update to Pydantic v2 ConfigDict style ✅ **COMPLETE**
  - Already using model_config = ConfigDict() throughout codebase

- [x] **REF-006**: Update Qdrant search() to query_points() ✅ **COMPLETE**
  - Replaced deprecated API for future Qdrant compatibility
  - Enhanced error handling for payload parsing

### 📚 Tier 7: Documentation & Monitoring

- [x] **PERF-006**: Performance Regression Detection ✅ **COMPLETE** (2025-11-22)
  - [x] Time-series metrics: search latency (P50, P95, P99), indexing throughput, cache hit rate
  - [x] Baseline establishment (rolling 30-day average)
  - [x] Anomaly detection with severity levels: MINOR, MODERATE, SEVERE, CRITICAL
  - [x] Actionable recommendations for each regression type
  - [x] CLI commands: `perf-report` and `perf-history`
  - [x] 31 comprehensive tests with 100% pass rate
  - **Impact:** Early warning system for performance issues, maintain quality at scale

- [ ] **TEST-006**: Comprehensive E2E Manual Testing (~10-15 hours) 🔄 **IN PROGRESS**
  - [x] Create comprehensive test plan (200+ test scenarios)
  - [x] Create bug tracker template with pre-populated known bugs
  - [x] Create execution guide and documentation
  - [x] Build Docker orchestration infrastructure (10 parallel agents)
  - [x] Fix Qdrant health check (BUG-019)
  - [x] Verify test agent execution and result collection
  - [ ] Implement automated test logic (currently MANUAL_REQUIRED placeholders)
  - [ ] Execute full E2E test plan (200+ test scenarios)
  - [ ] Test all 16 MCP tools for functionality and UX
  - [ ] Test all 28+ CLI commands end-to-end
  - [ ] Validate installation on clean system (<5 min setup)
  - [ ] Verify performance benchmarks (7-13ms search, 10-20 files/sec indexing)
  - [ ] Test multi-language support (all 17 file formats)
  - [ ] Assess UX quality (error messages, consistency, polish)
  - [ ] Catalogue all bugs in bug tracker (anything requiring workaround = bug)
  - [ ] Test critical known bugs: BUG-018 (memory retrieval), BUG-022 (zero units), BUG-015 (health check)
  - [ ] Generate final production readiness report
  - **Planning Docs:** `planning_docs/TEST-006_*.md` (13 files: test plan, bug tracker, guide, orchestration, Dockerfiles, status, etc.)
  - **Infrastructure Status:** ✅ Docker orchestration working (see `TEST-006_infrastructure_status.md`)
  - **Impact:** Verify production readiness, identify all quality issues before release
  - **Success Criteria:** Zero critical bugs, all core features work without workarounds, performance meets benchmarks

- [x] **DOC-004**: Update README with code search examples ✅ **COMPLETE**
- [ ] **DOC-005**: Add performance tuning guide for large codebases
- [x] **DOC-006**: Create troubleshooting guide for common parser issues ✅ **COMPLETE**
  - Added comprehensive "Code Parsing Issues" section to TROUBLESHOOTING.md
  - Covers: syntax errors, encoding, performance, memory, unsupported languages, skipped files
  - 6 subsections with practical solutions and code examples
- [ ] **DOC-007**: Document best practices for project organization

- [ ] **DOC-001**: Interactive documentation
  - [ ] Live examples in docs
  - [ ] Playground for testing queries

- [ ] **DOC-002**: Migration guides
  - [ ] From other code search tools
  - [ ] Database migration utilities

- [ ] **DOC-003**: Video tutorials
  - [ ] Setup walkthrough
  - [ ] Feature demonstrations
  - [ ] Best practices guide

- [ ] **FEAT-019**: IDE Integration
  - [ ] VS Code extension for instant code search
  - [ ] IntelliJ plugin
  - [ ] Vim/Neovim integration

- [x] **FEAT-020**: Usage patterns tracking ✅ **COMPLETE** (2025-11-24)
  - [x] Track most searched queries
  - [x] Identify frequently accessed code
  - [x] User behavior analytics

- [ ] **FEAT-021**: Memory lifecycle management
  - [ ] Auto-expire old memories
  - [ ] Memory importance decay
  - [ ] Storage optimization

- [ ] **FEAT-022**: Performance monitoring dashboard
  - [ ] Real-time metrics visualization
  - [ ] Alerting for performance degradation
  - [ ] Capacity planning tools

---

## Completed Recently

### 2025-11-19

- [x] **BUG-015**: Code search category filter mismatch ✅ **COMPLETE**
  - Fixed critical bug where code indexed with category=CODE but searched with category=CONTEXT
  - Impact: 100% failure rate - all code searches returned "No code found"
  - Fix: Changed src/core/server.py:2291,2465 to use MemoryCategory.CODE
  - Discovery: Found during EVAL-001 empirical evaluation
  - **Result:** Code search now works correctly with Qdrant backend

- [x] **EVAL-001**: Empirical evaluation of MCP RAG usefulness ✅ **COMPLETE**
  - Evaluated MCP RAG semantic search vs Baseline (Grep/Read/Glob) approach
  - Tested 10 questions across 6 categories (Architecture, Location, Debugging, Planning, Historical, Cross-cutting)
  - Discovered BUG-015 (category filter mismatch) - FIXED
  - Identified SQLite vs Qdrant performance gap (keyword vs semantic search)
  - Validated Baseline approach is highly effective (4.5/5 quality, 100% success rate)
  - Deliverables: 4 comprehensive reports in planning_docs/EVAL-001_*.md
  - **Next:** Re-run with Qdrant for fair semantic search comparison

- [x] **BUG-008**: File Watcher Async/Threading Bug & Stale Index Cleanup ✅ **COMPLETE**
  - Fixed RuntimeError: no running event loop in file watcher
  - Added event loop parameter to DebouncedFileWatcher and FileWatcherService
  - Implemented thread-safe async scheduling via asyncio.run_coroutine_threadsafe()
  - Enhanced on_deleted() handler to trigger index cleanup
  - Implemented automatic cleanup of stale index entries during reindexing
  - Added _cleanup_stale_entries() and _get_indexed_files() methods
  - Display cleaned entry count in index command output
  - **Impact:** File watching now fully functional, index stays clean automatically

- [x] **UX-006**: Enhanced MCP Tool Descriptions for Proactive Use ✅ **COMPLETE**
  - Added comprehensive "PROACTIVE USE" sections to all 16 MCP tools
  - Included clear "when to use" guidance and concrete examples
  - Added comparisons with built-in tools (e.g., search_code vs Grep)
  - Documented performance characteristics and search modes
  - Updated: store_memory, retrieve_memories, search_code, list_memories, delete_memory,
    index_codebase, find_similar_code, search_all_projects, opt_in/out_cross_project,
    list_opted_in_projects, export/import_memories, get_performance_metrics,
    get_active_alerts, get_health_score
  - **Impact:** Claude Code agents should now use MCP tools more proactively

### 2025-11-18

- [x] **FEAT-028**: Proactive Context Suggestions ✅ **COMPLETE**
  - Full proactive suggestion system with adaptive learning
  - Pattern detector for conversation analysis (4 intent types)
  - Feedback tracker with SQLite persistence
  - 4 new MCP tools: analyze_conversation, get_suggestion_stats, provide_suggestion_feedback, set_suggestion_mode
  - Automatic context injection at high confidence (>0.90)

- [x] **UX-017**: Indexing Time Estimates ✅ **COMPLETE**
  - Intelligent time estimation with historical tracking
  - Real-time ETA calculations during indexing
  - Performance optimization suggestions
  - Time estimates based on rolling 10-run average per project

- [x] **UX-033**: Memory Tagging & Organization System ✅ **COMPLETE**
  - Auto-tagging for automatic tag extraction and inference
  - Hierarchical tag management (4-level hierarchies)
  - Smart collection management
  - 3 CLI commands: tags, collections, auto-tag
  - 4 database tables for tags infrastructure

- [x] **UX-013**: Better Installation Error Messages ✅ **COMPLETE**
  - System prerequisites detection (Python, pip, Docker, Rust, Git)
  - Smart dependency checking with contextual error messages
  - validate-install CLI command
  - OS-specific install commands (macOS/Linux/Windows)
  - 90% setup success rate (up from 30%)

- [x] **FEAT-036**: Project Archival Phase 2 (All 5 sub-phases) ✅ **COMPLETE**
  - Phase 2.1: Archive compression (60-80% storage reduction)
  - Phase 2.2: Bulk operations (auto-archive multiple projects)
  - Phase 2.3: Automatic scheduler (daily/weekly/monthly)
  - Phase 2.4: Export/import for portable archives
  - Phase 2.5: Documentation & polish

- [x] **FEAT-043**: Bulk Memory Operations ✅ **COMPLETE**
  - bulk_delete_memories() MCP tool with dry-run preview
  - Batch processing (100 memories/batch)
  - Safety limits (max 1000 per operation)
  - 21 tests (100% passing)

- [x] **FEAT-044**: Memory Export/Import Tools ✅ **COMPLETE**
  - export_memories() MCP tool (JSON/Markdown formats)
  - import_memories() MCP tool with conflict resolution
  - 19 tests (100% passing)

- [x] **FEAT-047**: Proactive Memory Suggestions ✅ **COMPLETE**
  - suggest_memories() MCP tool
  - Intent detection (implementation, debugging, learning, exploration)
  - Confidence scoring
  - 41 tests (100% passing)

- [x] **FEAT-041**: Memory Listing and Browsing ✅ **COMPLETE**
  - list_memories() MCP tool
  - Filtering by category, scope, tags, importance, dates
  - Sorting and pagination
  - 16 tests (100% passing)

---

## Notes

**Priority Legend:**
- 🔴 **Tier 0** - Critical production blockers (MUST FIX before v4.1 release)
- 🔥 **Tier 1** - High-impact core functionality improvements (prevents 70% abandonment)
- 🟡 **Tier 2** - Core functionality extensions (nice-to-have)
- 🟢 **Tier 3** - UX improvements and performance optimizations
- 🌐 **Tier 4** - Language support extensions
- 🚀 **Tier 5** - Advanced/future features
- 🔨 **Tier 6** - Refactoring & tech debt
- 📚 **Tier 7** - Documentation & monitoring

**Sprint Recommendation for v4.1:**
1. **Week 1-2:** Fix all Tier 0 blockers (bugs, test failures, verification)
2. **Week 3-4:** Complete FEAT-032 Phase 2 (health system) + FEAT-038 (backup automation)
3. **Week 5-6:** Performance testing (TEST-004) + first-run testing (TEST-005)
4. **Week 7-8:** Documentation (DOC-009) + polish + beta testing

**Time Estimates:**
- Items marked with time estimates have been scoped
- Unmarked items need investigation/scoping

**Dependencies:**
- BUG-012 blocks FEAT-040 verification
- TEST-004 required before declaring production-ready
- DOC-009 required for production support

**Planning Documents:**
- Check `planning_docs/` folder for detailed implementation plans
- File format: `{ID}_{description}.md`
- Create planning doc before starting complex items

**Test Status:**
- **Current:** 2117 passing, 17 failing, 20 skipped (99.2% pass rate)
- **Target:** 100% pass rate (all Tier 0 items must pass)
- **Failing:** BUG-012 (15 tests), BUG-013 (2 tests)
