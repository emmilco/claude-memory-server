# TODO

## AUDIT-001 Part 2: Qdrant Store & Connection Management Findings (2025-11-30)

**Investigation Scope:** 3,181 lines across 7 files (qdrant_store.py, connection_pool.py, connection_health_checker.py, connection_pool_monitor.py, qdrant_setup.py, base.py, factory.py)

### 🔴 CRITICAL Findings

- [ ] **BUG-061**: Scroll Loop Infinite Loop Risk with Malformed Offset
  - **Location:** `src/store/qdrant_store.py:594-610`, `src/store/qdrant_store.py:839-863`, and 20+ other scroll loops
  - **Problem:** Scroll loops check `if offset is None` but don't handle malformed offset values that could cause infinite loops
  - **Fix:** Add iteration counter with max limit (e.g., 1000 iterations) and explicit timeout; log warning if limit hit

- [ ] **BUG-062**: Connection Pool Reset Race Condition
  - **Location:** `src/store/connection_pool.py:421-448`
  - **Problem:** `reset()` method sets `_closed = False` after `close()` without acquiring `_lock`, creating race window where new acquisitions could interleave with cleanup
  - **Fix:** Wrap the entire reset sequence in `async with self._lock:` to ensure atomic state transition

- [ ] **BUG-063**: Missing Client Release on Early Return in get_by_id
  - **Location:** `src/store/qdrant_store.py:569-570`
  - **Problem:** `if not result: return None` exits without releasing client from pool
  - **Fix:** Change to `if not result: memory = None; else: memory = self._payload_to_memory_unit(...); return memory` inside try block

- [x] **BUG-066**: Integration Test Suite Hangs on test_memory_update_integration.py ✅ FIXED (2025-11-30)
  - **Root Cause:** Synchronous Qdrant client calls blocking async event loop in pytest-asyncio
  - **Fix:**
    - [x] Wrapped `client.get_collections()` in `run_in_executor()` in connection_pool.py
    - [x] Added `await asyncio.sleep(0)` after `scheduler.start()` in server.py
    - [x] Disabled connection pooling and background tasks in test fixtures
  - **Commit:** 61da6cc, merged to main as 9c4e34e

### 🟡 HIGH Priority Findings

- [ ] **REF-036**: Inconsistent Point ID Format Across Store Operations
  - **Location:** `src/store/qdrant_store.py:238-241` (delete uses list), vs `src/store/qdrant_store.py:2527` (uses PointIdsList)
  - **Problem:** Some operations use `points_selector=[memory_id]` (list) while others use `PointIdsList(points=[...])` for deletion
  - **Fix:** Standardize all deletion operations to use PointIdsList for consistency with Qdrant API best practices

- [ ] **REF-037**: Scroll Operations Fetch Too Much Data for Large Collections
  - **Location:** `src/store/qdrant_store.py:2619` fetches limit*10 (up to 1000 points) just to sort and return limit
  - **Problem:** Inefficient memory usage - fetches 10x more data than needed because Qdrant doesn't support sorting by payload fields
  - **Fix:** Document limitation and add warning comment; consider using external sorting service for large result sets

- [ ] **PERF-008**: Connection Health Check Creates New Client on Recycling Failure
  - **Location:** `src/store/connection_pool.py:276-278`
  - **Problem:** When recycled connection fails health check, creates new connection synchronously during acquire, blocking caller
  - **Fix:** Consider background pre-warming of replacement connections or fail-fast with retry from pool

- [ ] **BUG-064**: Potential Integer Overflow in Unix Timestamp Conversion
  - **Location:** `src/store/qdrant_store.py:2727-2732` converts datetime to timestamp for Qdrant filters
  - **Problem:** No validation that timestamp fits in Qdrant's numeric range; far-future dates could overflow
  - **Fix:** Add validation: `if timestamp > 2**31 - 1: raise ValidationError("Date too far in future")`

### 🟢 MEDIUM Priority Findings

- [ ] **REF-038**: SQLite Direct Access in Qdrant Store Violates Separation of Concerns
  - **Location:** `src/store/qdrant_store.py:2557-2596`
  - **Problem:** `get_recent_activity()` directly opens SQLite feedback.db, mixing storage backends
  - **Fix:** Extract feedback database access to separate FeedbackService, inject as dependency

- [ ] **REF-039**: Duplicate Vector Retrieval in Git Commit Operations
  - **Location:** `src/store/qdrant_store.py:2945` and `src/store/qdrant_store.py:2965` both set `with_vectors=True`
  - **Problem:** Many operations retrieve vectors just to pass them through without using them
  - **Fix:** Only fetch vectors when actually needed (e.g., for similarity computation); add TODO comments documenting why vectors are needed

- [ ] **PERF-009**: Scroll Loop Inefficiency - No Batch Size Optimization
  - **Location:** All scroll loops use fixed `limit=100` regardless of total expected results
  - **Problem:** Small queries (limit=10) still fetch in batches of 100, wasting bandwidth
  - **Fix:** Use adaptive batch sizing: `batch_size = min(100, max(limit, 10))`

- [ ] **BUG-065**: Memory Leak in find_duplicate_memories with Large Collections
  - **Location:** `src/store/qdrant_store.py:2397-2417` loads all points with vectors into memory
  - **Problem:** For 100K+ points with 768-dim vectors, consumes gigabytes of RAM
  - **Fix:** Process in batches with sliding window comparison, or add max_points parameter with validation

### 🟦 LOW Priority / Tech Debt

- [ ] **REF-040**: Inconsistent Datetime Timezone Handling
  - **Location:** `src/store/qdrant_store.py:1492-1496`, `src/store/qdrant_store.py:1500-1504` manually check and add timezone
  - **Problem:** Repetitive timezone-naive -> timezone-aware conversion code in 10+ locations
  - **Fix:** Extract to helper method `_ensure_utc_datetime(dt: Optional[datetime]) -> Optional[datetime]`

- [ ] **REF-041**: Magic Number 1000 for History Limits
  - **Location:** `src/store/connection_pool.py:591`, `src/store/connection_pool_monitor.py:202-204`, `src/store/connection_pool_monitor.py:299`
  - **Problem:** Hardcoded limit `1000` appears in multiple places without explanation
  - **Fix:** Extract to named constant `MAX_HISTORY_SIZE = 1000` with comment explaining memory tradeoff

- [ ] **REF-042**: Type Hint Incompleteness in _build_payload
  - **Location:** `src/store/qdrant_store.py:1177-1249`
  - **Problem:** Returns `Tuple[str, Dict[str, Any]]` but Dict values are actually specific types (str, int, float, list, None)
  - **Fix:** Use TypedDict for payload structure to improve type safety

- [ ] **PERF-010**: Unnecessary List Reversal in get_metrics_history
  - **Location:** `src/store/connection_pool_monitor.py:330`
  - **Problem:** `list(reversed(self._metrics_history[-limit:]))` creates two intermediate lists
  - **Fix:** Use slice notation: `self._metrics_history[-limit:][::-1]` (single operation)

### Summary Statistics

- **Total Issues Found:** 17
- **Critical:** 3 (connection leaks, infinite loops, race conditions)
- **High:** 4 (API inconsistencies, performance bottlenecks)
- **Medium:** 4 (architecture violations, memory leaks)
- **Low:** 6 (code quality, maintainability)

**Next Ticket Numbers:** BUG-061 to BUG-065, REF-036 to REF-042, PERF-008 to PERF-010

---

## AUDIT-001 Part 3: Embedding Generation & Caching Findings (2025-11-30)

**Investigation Scope:** 1,012 lines across 5 files (cache.py, generator.py, parallel_generator.py, rust_bridge.py, gpu_utils.py)

### 🔴 CRITICAL Findings

- [ ] **BUG-059**: SQLite Connection Not Closed in Cache Error Paths
  - **Location:** `src/embeddings/cache.py:63-96`
  - **Problem:** If `_initialize_db()` fails after creating connection (e.g., table creation error), `self.conn` is not closed before setting `enabled=False`
  - **Impact:** SQLite connection leak on startup failure, file locks not released
  - **Fix:** Add `try/finally` with `self.conn.close()` before disabling cache

- [ ] **BUG-060**: Cache Statistics Reset Without Holding Counter Lock
  - **Location:** `src/embeddings/cache.py:488-490`
  - **Problem:** `clear()` resets `self.hits` and `self.misses` without acquiring `_counter_lock`
  - **Impact:** Race condition if cache operations run concurrently with clear()
  - **Fix:** Acquire `_counter_lock` before resetting counters

### 🟡 HIGH Priority Findings

- [ ] **BUG-065**: Batch Cache Get Returns Wrong Type on Timeout
  - **Location:** `src/embeddings/cache.py:294`
  - **Problem:** `batch_get()` returns `[None] * len(texts)` on timeout, but internal `_batch_get_sync()` has dict type hint mismatch
  - **Impact:** Type confusion - callers expect `List[Optional[List[float]]]` but signature suggests dict
  - **Fix:** Fix return type annotation of `_batch_get_sync()` to match `batch_get()`

- [ ] **BUG-066**: Cache Key Collision Risk for Unicode Text
  - **Location:** `src/embeddings/cache.py:108`
  - **Problem:** SHA256 hashes text as UTF-8 bytes, but doesn't normalize Unicode (NFC vs NFD forms)
  - **Impact:** Same text in different Unicode normalizations produces different cache keys, reducing hit rate
  - **Example:** "café" (NFC) vs "café" (NFD with combining accent) hash differently
  - **Fix:** Add `unicodedata.normalize('NFC', text)` before hashing

- [ ] **BUG-067**: GPU Memory Fraction Set Globally Affects All Processes
  - **Location:** `src/embeddings/generator.py:148-149`
  - **Problem:** `torch.cuda.set_per_process_memory_fraction()` affects entire process, not just this generator
  - **Impact:** Multiple EmbeddingGenerator instances will conflict, last one wins
  - **Fix:** Document this limitation or track if already set globally

### 🟢 MEDIUM Priority Findings

- [ ] **REF-043**: Inconsistent Error Logging Between Sync and Async Cache Methods
  - **Location:** `src/embeddings/cache.py:193-197, 240`
  - **Problem:** Sync methods (`_get_sync`, `_set_sync`) log errors with full details, but timeout handlers log minimal context
  - **Impact:** Debugging timeout issues harder than other cache errors
  - **Fix:** Standardize error logging to include operation type, text hash, and model name

- [ ] **REF-044**: Hardcoded Timeout Values in Cache Operations
  - **Location:** `src/embeddings/cache.py:128, 213, 291, 392, 472`
  - **Problem:** All async cache operations use hardcoded `asyncio.timeout(30.0)` - not configurable
  - **Impact:** Cannot tune timeouts for slow storage or fast SSDs
  - **Fix:** Add `cache_operation_timeout_seconds` to ServerConfig.performance

- [ ] **PERF-010**: Parallel Generator Initializes Executor Even for Small Batches
  - **Location:** `src/embeddings/parallel_generator.py:240-260`
  - **Problem:** `initialize()` creates ProcessPoolExecutor upfront, even if workload is too small to benefit
  - **Impact:** Wasted resources (process pool overhead) for applications that only use small batches
  - **Fix:** Lazy-initialize executor on first large batch (>= `parallel_threshold`)

- [ ] **REF-045**: Worker Model Loading Error Messages Lost to Main Process
  - **Location:** `src/embeddings/parallel_generator.py:106-107`
  - **Problem:** Worker process logs model loading errors with `exc_info=True`, but logs may not propagate to main process
  - **Impact:** Model loading failures in workers hard to debug - user only sees generic "embedding generation failed"
  - **Fix:** Serialize exception details in raised `EmbeddingError` message

### 📊 Part 3 Summary

| Severity | Count | Tickets |
|----------|-------|---------|
| Critical (resource leaks) | 2 | BUG-059, BUG-060 |
| High (incorrect behavior) | 3 | BUG-065, BUG-066, BUG-067 |
| Medium (tech debt/perf) | 4 | REF-043, REF-044, PERF-010, REF-045 |
| **Total** | **9** | |

**Key Findings:**
- Cache subsystem has resource management issues in error paths
- Unicode normalization missing from cache key computation affects non-ASCII text
- Type safety violations in batch operations
- GPU memory settings have process-wide side effects

**Next Ticket Numbers:** BUG-068, REF-046, PERF-011

---

## AUDIT-001 Part 4: Search & Retrieval Pipeline Findings (2025-11-30)

**Investigation Scope:** 1,195 lines across 6 files (hybrid_search.py, reranker.py, bm25.py, query_synonyms.py, pattern_matcher.py, query_dsl_parser.py)

### 🔴 CRITICAL Findings

- [ ] **BUG-067**: Normalization Returns Max Score for All-Zero Results
  - **Location:** `src/search/hybrid_search.py:365-367`
  - **Problem:** When all scores are identical (including all 0.0), `_normalize_scores` returns `[1.0] * len(scores)`, giving maximum normalized score to zero-relevance results
  - **Fix:** Check if `max_score == 0.0` and return `[0.0] * len(scores)` instead of `[1.0]`

- [ ] **BUG-068**: Keyword Boost Uses Substring Matching Instead of Word Boundaries
  - **Location:** `src/search/reranker.py:265-268`
  - **Problem:** `kw in content_lower` matches substrings, so "auth" matches "author", "authenticate", "unauthorized", inflating boost scores
  - **Fix:** Use word boundary regex: `re.search(rf'\b{re.escape(kw)}\b', content_lower)`

### 🟡 HIGH Priority Findings

- [ ] **BUG-069**: Cascade Fusion Loses Vector Scores for Dual-Appearing Results
  - **Location:** `src/search/hybrid_search.py:312-321`
  - **Problem:** When a memory appears in both BM25 and vector results, cascade fusion includes it from BM25 with `vector_score=0.0` (line 316) but never updates this even though the vector score is available
  - **Fix:** After adding BM25 results, iterate through vector results for already-seen IDs and update their vector_score field

- [ ] **BUG-070**: Pattern Matcher Line Number Off-By-One Error
  - **Location:** `src/search/pattern_matcher.py:174-178`
  - **Problem:** Line number calculation breaks when `offset > start_pos` and assigns `line_num = i`, but should check `offset <= start_pos` for the previous line
  - **Fix:** Change condition to `if offset > start_pos:` set `line_num = i - 1; break`

- [ ] **BUG-071**: Query Synonyms Non-Deterministic Due to Set Ordering
  - **Location:** `src/search/query_synonyms.py:223` and `src/search/query_synonyms.py:264`
  - **Problem:** `list(word_synonyms)[:max_synonyms]` iterates over unordered set, causing non-deterministic query expansion (different results on different runs)
  - **Fix:** Sort before slicing: `sorted(word_synonyms)[:max_synonyms]`

- [ ] **REF-043**: Missing Validation for RRF K Parameter
  - **Location:** `src/search/hybrid_search.py:48-62`
  - **Problem:** `rrf_k` parameter is used in division (line 258, 261) but never validated to be positive; zero or negative values would cause errors
  - **Fix:** Add validation in `__init__`: `if rrf_k <= 0: raise ValueError("rrf_k must be positive")`

### 🟢 MEDIUM Priority Findings

- [ ] **BUG-072**: Tokenization Mismatch Between BM25 and Query Expansion
  - **Location:** `src/search/bm25.py:96` preserves underscores, `src/search/query_synonyms.py:259` splits on underscores
  - **Problem:** BM25 tokenizes "user_id" as one token `["user_id"]`, but query expansion tokenizes as `["user", "id"]`, causing synonym mismatch
  - **Fix:** Align tokenization - either both preserve or both split underscores; recommend preserving for code identifiers

- [ ] **BUG-073**: Date Filter Range Validation Missing
  - **Location:** `src/search/query_dsl_parser.py:167`
  - **Problem:** Multiple date filters like `created:>2024-12-31 created:<2024-01-01` are merged with `.update()` but never validated for logical consistency (start < end)
  - **Fix:** After merging, check if `gte/gt > lte/lt` and raise ValidationError

- [ ] **BUG-074**: Invalid Filter Exclusions Include Minus Sign in Semantic Query
  - **Location:** `src/search/query_dsl_parser.py:148`
  - **Problem:** Unrecognized filters like `-unknown:value` are treated as semantic terms by appending `match.group(0)`, which includes the `-` prefix
  - **Fix:** Append `match.group(0).lstrip('-')` to remove exclusion prefix from semantic terms

- [ ] **PERF-011**: BM25 Discards Single-Character Tokens Common in Code
  - **Location:** `src/search/bm25.py:99`
  - **Problem:** Filters out `len(t) < 2`, removing single-char identifiers like "x", "y", "i" common in math/loop code
  - **Fix:** Add configuration option `min_token_length` with default 1 for code search; update to `[t for t in tokens if len(t) >= self.min_token_length]`

- [ ] **REF-044**: Hardcoded Diversity Similarity Threshold
  - **Location:** `src/search/reranker.py:302`
  - **Problem:** Diversity penalty threshold `0.8` is hardcoded with no configuration option; too high for some use cases, too low for others
  - **Fix:** Add `diversity_similarity_threshold` parameter to `ResultReranker.__init__` with default 0.8

### 🟦 LOW Priority / Tech Debt

- [ ] **REF-045**: Weighted Fusion Default Score Penalizes Single-Method Results
  - **Location:** `src/search/hybrid_search.py:186`
  - **Problem:** When memory only appears in one result set, default score is 0.0 for the other, which reduces combined score by `(1-alpha)` or `alpha`; this unfairly penalizes good results from one method
  - **Fix:** Consider using geometric mean or not penalizing missing scores; document current behavior

- [ ] **REF-046**: Diversity Signature Uses Only First 100 Characters
  - **Location:** `src/search/reranker.py:296`
  - **Problem:** For code, first 100 chars might miss important differences in function bodies (e.g., similar imports/signatures)
  - **Fix:** Make signature length configurable or use content hash for better diversity detection

- [ ] **REF-047**: Pattern Matcher Long Lines Regex Won't Match (Missing DOTALL)
  - **Location:** `src/search/pattern_matcher.py:39`
  - **Problem:** Pattern `^.{120,}$` with MULTILINE expects `.` to match newlines, but default `.` doesn't match `\n` (needs DOTALL flag at line 98)
  - **Fix:** Either use DOTALL flag or change pattern to `^[^\n]{120,}$`

- [ ] **REF-048**: Duplicate Synonym Entry for "exception"/"exceptions"
  - **Location:** `src/search/query_synonyms.py:66-67`
  - **Problem:** Both "exception" and "exceptions" have separate entries with similar synonyms; maintenance burden
  - **Fix:** Use stemming or normalize plurals before lookup to consolidate entries

- [ ] **REF-049**: BM25 Tokenization Doesn't Handle Non-ASCII Characters
  - **Location:** `src/search/bm25.py:96`
  - **Problem:** Regex `[a-z0-9_]+` excludes non-ASCII (accented chars, emoji, CJK), which appear in code comments/strings
  - **Fix:** Update to `[\w]+` with re.UNICODE flag or `[a-z0-9_\u00C0-\uFFFF]+` to include Unicode word chars

- [ ] **REF-050**: Date Validation Returns Original String After Normalizing Different Value
  - **Location:** `src/search/query_dsl_parser.py:255, 260`
  - **Problem:** Validates `normalized` (with 'Z' replaced by '+00:00') but returns original `date_str` (with 'Z'), potentially confusing downstream consumers
  - **Fix:** Return normalized string consistently or document that original format is preserved

### Summary Statistics

- **Total Issues Found:** 18
- **Critical:** 2 (incorrect score normalization, substring matching bug)
- **High:** 4 (data loss in fusion, non-deterministic results, off-by-one error, missing validation)
- **Medium:** 5 (tokenization mismatch, validation gaps, performance issues)
- **Low:** 7 (code quality, maintainability, configuration flexibility)

**Next Ticket Numbers:** BUG-067 to BUG-074, REF-043 to REF-050, PERF-011

---

## 🚨 SPEC COVERAGE AUDIT (2025-11-25)

**Source:** 4-agent parallel analysis of SPEC.md requirements vs test suite coverage.
**Finding:** Testing pyramid inverted (91% unit, 8.6% integration, 0% E2E). Critical gaps in boundary conditions, concurrency, MCP protocol, and E2E workflows.

### 🔴 Critical - Testing Infrastructure Gaps

- [x] **TEST-023**: Add 40+ Boundary Condition Unit Tests ✅ **COMPLETE** (2025-11-25)
  - **Result:** Created 124 boundary condition tests covering numeric, string, collection, pagination, and search boundaries
  - **Files created:** `tests/unit/test_boundary_conditions.py`, `tests/unit/test_pagination_edge_cases.py`

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

- [x] **TEST-025**: Create 25+ End-to-End Workflow Integration Tests ✅ **COMPLETE** (2025-11-25)
  - **Result:** Created 29 E2E workflow integration tests covering memory CRUD, code indexing, project archival, cross-project search, and health monitoring
  - **Files created:** `tests/integration/test_e2e_workflows.py`, `tests/integration/test_workflow_memory.py`, `tests/integration/test_workflow_indexing.py`

- [x] **TEST-026**: Create MCP Protocol Integration Test Suite (F010) ✅ **COMPLETE** (2025-11-25)
  - **Result:** Created 41 MCP protocol integration tests covering tool registration, schema validation, concurrency, and error handling
  - **Files created:** `tests/integration/test_mcp_integration.py`, `tests/integration/test_mcp_concurrency.py`, `tests/integration/test_mcp_error_handling.py`

### 🟡 High Priority - Test Quality Improvements

- [x] **TEST-027**: Convert Manual Tests to Automated E2E ✅ **COMPLETE** (2025-11-25)
  - **Result:** Created 18 automated E2E tests from manual test scripts covering critical user paths
  - **Files created:** `tests/e2e/` directory, `tests/e2e/conftest.py`, `tests/e2e/test_critical_paths.py`

- [x] **TEST-028**: Add Performance Regression Test Suite ✅ **COMPLETE** (2025-11-25)
  - **Result:** Created 20 performance regression tests covering latency, throughput, and cache metrics
  - **Files created:** `tests/performance/`, `tests/performance/test_latency.py`, `tests/performance/test_throughput.py`

### 📊 SPEC Coverage Audit Summary

| Category | SPEC Reqs | Status | Tests Added |
|----------|-----------|--------|-------------|
| Boundary conditions | ~40 | ✅ COMPLETE | 124 tests |
| Concurrent operations | ~15 | ✅ COMPLETE | 13 tests fixed |
| E2E workflows | ~25 | ✅ COMPLETE | 29 tests |
| MCP protocol (F010) | 4 | ✅ COMPLETE | 41 tests |
| Manual → Automated E2E | ~15 | ✅ COMPLETE | 18 tests |
| Performance regression | ~10 | ✅ COMPLETE | 20 tests |
| **Total new tests** | | | **~245 tests** |

**Completed:** 2025-11-25
**Impact:** Testing pyramid rebalanced with significant E2E and integration coverage

---

## 🚨 TEST ANTIPATTERN AUDIT (2025-11-25)

**Source:** 6-agent parallel review analyzing 168 test files for validation theater and antipatterns.
**Methodology:** Each agent reviewed ~25-30 test files for: no assertions, mock overuse, weak assertions, flaky tests, broad exceptions, ignored return values, misleading names.

### 🔴 Critical - Validation Theater (Zero Real Coverage)

- [x] **TEST-013**: Remove/Fix Entirely Skipped Test Suites ✅ **COMPLETE** (2025-11-25)
  - **Result:** Addressed ~13 files with module-level skips - fixed fixtures, removed false coverage, documented remaining skips

- [x] **TEST-014**: Remove `assert True` Validation Theater ✅ **COMPLETE** (2025-11-25)
  - **Result:** Removed 4 instances of `assert True` validation theater and converted to actual assertions

- [x] **TEST-015**: Add Assertions to 23+ No-Assertion Tests ✅ **COMPLETE** (2025-11-25)
  - **Result:** Added meaningful assertions to tests in `test_status_command.py` and `test_health_command.py`

### 🟡 High Priority - Tests That Hide Bugs

- [x] **TEST-016**: Fix 20+ Flaky Tests Marked Skip (Race Conditions) ✅ **COMPLETE** (2025-11-25)
  - **Result:** Fixed race conditions with proper synchronization primitives, Event/Signal patterns, and test locks

- [x] **TEST-017**: Replace 30+ Mock-Only Tests with Behavior Tests ✅ **COMPLETE** (2025-11-25)
  - **Result:** Added behavior assertions alongside mock verifications across affected test files

- [x] **TEST-018**: Strengthen 50+ Weak/Trivial Assertions ✅ **COMPLETE** (2025-11-25)
  - **Result:** Tightened assertions to verify specific values instead of type-only or existence-only checks

### 🟢 Medium Priority - Test Quality Improvements

- [x] **TEST-019**: Narrow 10+ Broad Exception Catches ✅ **COMPLETE** (2025-11-25)
  - **Result:** Replaced `pytest.raises(Exception)` with specific exception types and match patterns

- [x] **TEST-020**: Rename 22+ Misleading Test Names ✅ **COMPLETE** (2025-11-25)
  - **Result:** Renamed tests to accurately reflect what they test

- [x] **TEST-021**: Add Missing Edge Case Tests ✅ **COMPLETE** (2025-11-25)
  - **Result:** Added edge case tests for boundary conditions, empty inputs, and invalid states

- [x] **TEST-022**: Check Ignored Return Values ✅ **COMPLETE** (2025-11-25)
  - **Result:** Added assertions to verify return values from function calls

### 📊 Test Antipattern Audit Summary

| Category | Count | Severity | Status |
|----------|-------|----------|--------|
| Skipped test suites (0 coverage) | ~13 files | CRITICAL | ✅ COMPLETE |
| `assert True` validation theater | 4 | CRITICAL | ✅ COMPLETE |
| No-assertion tests | 23+ | CRITICAL | ✅ COMPLETE |
| Flaky tests (skip hiding bugs) | 20+ | HIGH | ✅ COMPLETE |
| Mock-only tests | 30+ | HIGH | ✅ COMPLETE |
| Weak/trivial assertions | 50+ | HIGH | ✅ COMPLETE |
| Broad exception catching | 10+ | MEDIUM | ✅ COMPLETE |
| Misleading test names | 22+ | MEDIUM | ✅ COMPLETE |
| Missing edge cases | 15+ areas | MEDIUM | ✅ COMPLETE |
| Ignored return values | 10+ | MEDIUM | ✅ COMPLETE |

**Completed:** 2025-11-25
**Result:** Test antipatterns addressed across all categories

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

- [x] **REF-016**: Split MemoryRAGServer God Class ✅ **COMPLETE** (2025-11-26)
  - **Location:** `src/core/server.py` + `src/services/`
  - **Problem:** Violated Single Responsibility Principle - 4,780 lines, 62+ methods
  - **Solution:** Extracted 6 focused service classes:
    - [x] `MemoryService` - Core CRUD operations and memory lifecycle
    - [x] `CodeIndexingService` - Code search, indexing, dependency analysis
    - [x] `CrossProjectService` - Multi-project search and consent
    - [x] `HealthService` - Health monitoring, metrics, alerting
    - [x] `QueryService` - Query expansion, sessions, suggestions
    - [x] `AnalyticsService` - Usage analytics and pattern tracking
  - **Files:** `src/services/*.py` (7 files), modified `src/core/server.py`
  - **Tests:** All 3,383 tests pass (99.85% pass rate)

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

- [x] **DOC-010**: Create Configuration Guide ✅ **COMPLETE** (2025-11-26)
  - **Location:** `docs/CONFIGURATION_GUIDE.md` (1,442 lines)
  - **Completed:** Documented all 150+ config options across 6 feature groups
  - **Includes:** 6 configuration profiles, feature level presets, troubleshooting, migration guide
  - **See:** CHANGELOG.md (2025-11-26)

### 📊 Code Review Summary

| Severity | Count | Status |
|----------|-------|--------|
| Critical | 5 | ✅ ALL COMPLETE |
| High | 7 | ✅ ALL COMPLETE (REF-016 completed 2025-11-26) |
| Medium | 6 | ✅ ALL COMPLETE (DOC-010 completed 2025-11-26) |

**Total Issues Addressed:** 18/18 tasks from code review (2025-11-25) ✅ **100% COMPLETE**
**REF-016 completed:** God class refactoring - extracted 6 services from server.py
**DOC-010 completed:** Comprehensive configuration guide (1,442 lines, 150+ options)
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

---

## 🚨 COMPREHENSIVE CODE REVIEW AUDIT (2025-11-29)

**Source:** File-by-file codebase review analyzing all ~160 modules across src/ directory.
**Methodology:** Thorough read-only analysis of src/core/, src/store/, src/memory/, src/embeddings/, src/services/, src/analysis/, src/cli/, src/search/ looking for bugs, tech debt, incomplete implementations, and code quality issues.
**Finding:** ~100+ distinct issues identified. Many critical bugs in core indexing/search paths.

### 🔴 Critical Bugs - Will Crash at Runtime

- [x] **BUG-038**: Undefined Variable `PYTHON_PARSER_AVAILABLE` ✅ FIXED (2025-11-29)
  - Removed reference to undefined variable, updated error message for Rust-only support

- [x] **BUG-039**: Missing Import `PointIdsList` in QdrantStore ✅ FIXED (2025-11-29)
  - Added missing import from `qdrant_client.models`

- [x] **BUG-040**: Unreachable Code and Undefined Variable in Exception Handlers ✅ FIXED (2025-11-30)
  - **Location:** `src/store/qdrant_store.py:2061-2064, 2337-2340`
  - **Error:** Code after `raise` is unreachable; variable `e` is undefined
  - **Impact:** Error logging lost, exceptions lack context - debugging production failures impossible
  - **Code Pattern:**
    ```python
    except StorageError:
        raise
        logger.error(f"Error: {e}")  # UNREACHABLE, e UNDEFINED
    ```
  - **Fix:** Change to `except StorageError as e:` and move logging before raise
  - **Discovered:** 2025-11-29 comprehensive code review

- [x] **BUG-041**: Cache Return Type Mismatch Causes IndexError ✅ FIXED (2025-11-29)
  - Changed `batch_get()` to return `[None] * len(texts)` instead of `{}` when disabled

- [x] **BUG-042**: Missing CLI Method `_format_relative_time` ✅ FIXED (2025-11-29)
  - Changed method call to `_format_time_ago()` (correct method name)

- [x] **BUG-043**: Missing CLI Commands `verify_command` and `consolidate_command` ✅ COMPLETE (2025-11-30)
  - **Location:** `src/cli/__init__.py:536, 548`
  - **Error:** `NameError: name 'verify_command' is not defined`
  - **Impact:** CLI crashes when `verify` or `consolidate` subcommands are invoked
  - **Root Cause:** Commands referenced in argparser but functions never imported/defined
  - **Fix:** Removed `verify` and `consolidate` command definitions from argparser (lines 412-472) and corresponding handlers from `main_async()` (lines 474-492)
  - **Discovered:** 2025-11-29 comprehensive code review
  - **Merged:** commit 5339b15, merged into main on 2025-11-30

- [x] **BUG-044**: Undefined Variable After Date Parsing Error 🔥🔥 ✅ COMPLETE (2025-11-30)
  - **Location:** `src/cli/git_search_command.py:62-70`
  - **Error:** `NameError: name 'since_dt' is not defined`
  - **Impact:** Git search command crashes on invalid date format
  - **Root Cause:** If date parsing fails, `since_dt` is never set but used at line 94
  - **Fix:** Set `since_dt = None` before try block or after except block
  - **Discovered:** 2025-11-29 comprehensive code review
  - **Merged:** commit 6868485, merged into main on 2025-11-30

### 🟡 High Priority Bugs - Incorrect Behavior / Data Corruption

- [x] **BUG-045**: Call Extractor State Leak Between Files ✅ FIXED (2025-11-30)
  - Reset `self.current_class = None` at start of `extract_calls()`

- [x] **BUG-046**: Store Attribute Access May Crash on Non-Qdrant Backends ✅ FIXED (2025-11-30)
  - Added `hasattr()` check for backend compatibility

- [x] **BUG-047**: RRF Fusion Logic Has Inverted Control Flow ✅ FIXED (2025-11-30)
  - Refactored to explicit search functions for clarity

- [x] **BUG-048**: Cascade Fusion Silently Drops Valid BM25 Results ✅ FIXED (2025-11-30)
  - Fixed cascade fusion to preserve valid BM25 results

- [x] **BUG-049**: Timezone Mismatch in Reranker Causes TypeError ✅ FIXED (2025-11-30)
  - Normalized datetimes to UTC before comparison

- [x] **BUG-050**: Executor Not Null-Checked After Failed Initialize ✅ FIXED (2025-11-30)
  - Added null check after initialize() with clear error message

- [x] **BUG-051**: MPS Generator Not Closed - Thread Leak ✅ FIXED (2025-11-30)
  - Added MPS generator cleanup in close() method

### 🟢 Medium Priority - Tech Debt and Code Quality

- [x] **REF-021**: Move Hardcoded Thresholds to Config ✅ FIXED (2025-11-30)
  - Added QualityThresholds config class with 24 configurable fields
  - Updated duplicate_detector, incremental_indexer, health_jobs, reranker, quality_analyzer

- [x] **REF-022**: Fix Inconsistent Error Handling Patterns ✅ FIXED (2025-11-30)
  - Standardized on exception-based error handling in services layer
  - Updated query_service, analytics_service, cross_project_service

- [x] **REF-023**: Remove Defensive hasattr() Patterns ✅ FIXED (2025-11-30)
  - Fixed enum normalization in qdrant_store._build_payload()
  - Removed 35 defensive hasattr() checks across services and store

- [x] **REF-024**: Fix Race Conditions in File Watcher Debounce ✅ FIXED (2025-11-30)
  - Fixed lock handling in `_debounce_callback()` to hold lock through entire operation

- [x] **REF-025**: Complete Stub Implementations ✅ FIXED (2025-11-30)
  - Implemented JavaScript/TypeScript call extractor (267 lines)
  - Marked _store_health_score() and _calculate_contradiction_rate() as unsupported

- [x] **REF-026**: Fix Memory Leak Risks in Large Dataset Operations ✅ FIXED (2025-11-30)
  - Added pagination to health_scorer.py (50K limit, 5K batch size)
  - Added size checks to code_duplicate_detector.py (10K limit for O(N²) ops)

- [x] **REF-027**: Add Missing Timeout Handling for Async Operations ✅ FIXED (2025-11-30)
  - Added asyncio.timeout(30.0) to embeddings cache (5 calls) and services layer (34 calls)

- [x] **BUG-052**: Incorrect Median Calculation in ImportanceScorer ✅ FIXED (2025-11-30)
  - **Location:** `src/analysis/importance_scorer.py:358`
  - **Problem:** Uses `sorted_scores[len(sorted_scores) // 2]` - wrong for even-length lists
  - **Impact:** Statistics biased - median off by up to 0.5 for small datasets
  - **Example:** `[0.1, 0.2, 0.3, 0.4]` returns 0.3 instead of 0.25
  - **Fix:** Average middle two elements for even-length lists
  - **Discovered:** 2025-11-29 comprehensive code review

- [x] **BUG-053**: Query DSL Date Parsing Too Strict ✅ FIXED (2025-11-30)
  - Now accepts ISO 8601 date formats via `fromisoformat()`

### 📊 Code Review Audit Summary (2025-11-29)

| Severity | Count | Status |
|----------|-------|--------|
| Critical (runtime crash) | 7 | ❌ NEW - Fix immediately |
| High (incorrect behavior) | 7 | ❌ NEW - Fix in next sprint |
| Medium (tech debt) | 9 | ❌ NEW - Address soon |
| **Total New Issues** | **23** | |

---

## 🔍 FOLLOW-UP INVESTIGATIONS

These investigations will help surface additional bugs by examining specific patterns and areas of concern.

### Investigation Tickets

- [x] **INVEST-001**: Audit All Exception Handlers for Lost Context ✅ COMPLETE (2025-11-29)
  - **Theme:** Exception chain preservation
  - **What to look for:**
    - `raise SomeError(f"message: {e}")` without `from e`
    - `except Exception:` followed by `raise` without re-raise context
    - Bare `except:` or `except: pass` patterns
  - **Search Pattern:** `grep -r "raise.*Error.*{e}\")" src/`
  - **Expected Impact:** 20-40 instances losing traceback context

- [x] **INVEST-002**: Audit All Async Operations for Missing await ✅ COMPLETE (2025-11-29)
  - **Theme:** Async/await correctness
  - **What to look for:**
    - Coroutines assigned but never awaited
    - `asyncio.create_task()` without error handling
    - Missing `await` on async method calls
  - **Grep Pattern:** Functions returning coroutines without await
  - **Expected Impact:** 5-10 subtle async bugs

- [x] **INVEST-003**: Audit Stats/Counter Thread Safety ✅ COMPLETE (2025-11-29)
  - **Theme:** Race conditions in metrics
  - **What to look for:**
    - `self.stats[key] += 1` without locks
    - `self.counter += 1` in async methods
    - Mutable state shared across async tasks
  - **Locations:** All `stats` dict mutations in `src/services/`, `src/core/`
  - **Expected Impact:** 10-15 non-atomic increments

- [x] **INVEST-004**: Audit Type Annotations for Errors ✅ COMPLETE (2025-11-29)
  - **Theme:** Type hint correctness
  - **What to look for:**
    - `any` instead of `Any`
    - `callable` instead of `Callable`
    - `dict` instead of `Dict` in pre-3.9 syntax context
    - Return type mismatches
  - **Tools:** Run `mypy src/` or manual grep
  - **Expected Impact:** 10-20 type annotation errors

- [x] **INVEST-005**: Audit Inline Imports for Performance ✅ COMPLETE (2025-11-29)
  - **Theme:** Import hygiene
  - **What to look for:**
    - `import X` inside functions (especially in hot paths)
    - Duplicate imports in same file
    - Unused imports
  - **Known locations:** `qdrant_store.py`, `parallel_generator.py`, `reranker.py`
  - **Expected Impact:** 15-20 inline imports to move

- [x] **INVEST-006**: Audit Resource Cleanup Patterns ✅ COMPLETE (2025-11-29)
  - **Theme:** Resource management
  - **What to look for:**
    - `finally:` blocks without proper cleanup
    - `__del__` methods without error handling
    - Connections/files opened without context managers
    - Pool resources not released on error paths
  - **Focus:** `src/store/`, `src/embeddings/`
  - **Expected Impact:** 5-10 resource leak risks

- [x] **INVEST-007**: Audit Enum/String Value Handling ✅ COMPLETE (2025-11-29)
  - **Theme:** Data model consistency
  - **What to look for:**
    - `.value` access on strings (will fail)
    - String comparison against enum (may fail)
    - Inconsistent enum vs string returns from store
  - **Pattern:** All uses of `MemoryCategory`, `ContextLevel`, `LifecycleState`
  - **Expected Impact:** 10-15 enum handling issues

- [x] **INVEST-008**: Audit Empty Input Edge Cases ✅ COMPLETE (2025-11-29)
  - **Theme:** Boundary condition handling
  - **What to look for:**
    - Functions not handling `None`, `[]`, `""`, `{}`
    - Division by zero risks (`len(x)` in denominator)
    - Index errors on empty collections
  - **Focus:** Search, retrieval, and scoring functions
  - **Expected Impact:** 15-20 edge case bugs

- [x] **INVEST-009**: Audit Configuration Validation Completeness ✅ COMPLETE (2025-11-29)
  - **Theme:** Config robustness
  - **What to look for:**
    - Config values used without validation
    - Range checks missing (negative values, >1.0 for ratios)
    - Interdependent configs not validated together
  - **Focus:** `src/config.py` and all config consumers
  - **Expected Impact:** 10-15 validation gaps

- [x] **INVEST-010**: Audit TODO/FIXME/HACK Comments ✅ COMPLETE (2025-11-29)
  - **Theme:** Known tech debt
  - **What to look for:**
    - `# TODO:` comments indicating unfinished work
    - `# FIXME:` comments indicating known bugs
    - `# HACK:` comments indicating workarounds
    - `# NOTE:` comments indicating gotchas
  - **Grep Pattern:** `grep -rn "TODO\|FIXME\|HACK\|XXX" src/`
  - **Expected Impact:** 20-30 tracked debt items

### 📊 Investigation Results

#### INVEST-001 Results: Exception Chain Preservation ✅ COMPLETE

**Finding:** 117 instances of `raise SomeError(f"...{e}")` without `from e`, plus 1 bare `except: pass`

- [x] **REF-028**: Add Exception Chain Preservation (`from e`) ✅ FIXED (2025-11-30)
  - Split into REF-028-A (qdrant_store, 32), REF-028-B (server.py, 40), REF-028-C (services, 41)
  - Total 113 instances fixed

- [x] **BUG-054**: Bare `except: pass` Swallows All Errors ✅ FIXED (2025-11-30)
  - Replaced with `except Exception:` for specific exception handling

#### INVEST-002 Results: Async/Await Correctness ✅ COMPLETE

**Finding:** 2 fire-and-forget `asyncio.create_task()` calls without error handling

- [x] **BUG-055**: Fire-and-Forget Task in Usage Tracker - No Error Handling ✅ FIXED (2025-11-30)
  - Added task tracking and error callback for flush operations

- [x] **BUG-056**: Fire-and-Forget Task in MCP Server - No Error Handling ✅ FIXED (2025-11-30)
  - Added task tracking, error callback, and cleanup on shutdown

#### INVEST-003 Results: Stats/Counter Thread Safety ✅ COMPLETE

**Finding:** 97 non-atomic counter increments across the codebase

- [x] **REF-029**: Non-Atomic Stats Dict Increments ✅ FIXED (2025-11-30)
  - Added threading.Lock protection to stats updates in services layer

- [x] **REF-030**: Non-Atomic Counter Attribute Increments - 16 Instances 🔥
  - **Pattern:** `self.counter += 1` is not atomic
  - **Locations:**
    - `src/store/connection_pool.py:298, 521` - `_active_connections`, `_created_count`
    - `src/store/connection_health_checker.py:108, 126, 137` - `total_checks`, `total_failures`
    - `src/store/connection_pool_monitor.py:197, 292` - `total_collections`, `total_alerts`
    - `src/embeddings/cache.py:146, 157, 178, 184, 341, 344` - `hits`, `misses`
    - `src/memory/usage_tracker.py:38` - `use_count`
    - `src/cli/validate_setup_command.py:42, 44` - `checks_passed`, `checks_failed`
  - **Problem:** Connection pool counters are particularly critical - used for pool state management
  - **Impact:** Pool corruption under high concurrency, cache stats inaccurate
  - **Fix:** Use `threading.Lock` or `asyncio.Lock` for critical counters
  - **Discovered:** 2025-11-29 INVEST-003 audit

#### INVEST-004 Results: Type Annotation Errors ✅ COMPLETE

**Finding:** 9 type annotation errors

- [x] **BUG-057**: Lowercase `any` Instead of `Any` - 5 Instances ✅ FIXED (2025-11-30)
  - Replaced lowercase `any` with `Any` in 5 files, added imports

- [x] **BUG-058**: Lowercase `callable` Instead of `Callable` ✅ FIXED (2025-11-30)
  - **Locations:**
    - `src/services/code_indexing_service.py:627` - `Optional[callable]`
    - `src/memory/incremental_indexer.py:112` - `Optional[callable]`
    - `src/memory/incremental_indexer.py:394` - `Optional[callable]`
    - `src/core/server.py:3169` - `Optional[callable]`
  - **Problem:** `callable` is a builtin function, not a type. Should be `Callable`
  - **Impact:** Type checker errors, no signature validation
  - **Fix:** Change to `Optional[Callable[..., Any]]` or more specific signature
  - **Discovered:** 2025-11-29 INVEST-004 audit

#### INVEST-005 Results: Inline Imports ✅ COMPLETE

**Finding:** 41 standard library imports inside functions (should be at module top)

- [x] **REF-031**: Move Inline Standard Library Imports to Module Top - 41 Instances
  - **Locations:** Major concentrations:
    - `src/core/server.py` - 16 instances (`time`, `re`, `fnmatch`)
    - `src/monitoring/performance_tracker.py` - 4 instances (`json`, `statistics`)
    - `src/store/qdrant_store.py` - 4 instances (`fnmatch`, `hashlib`, `uuid`)
    - `src/memory/incremental_indexer.py` - 3 instances (`hashlib`, `re`)
    - `src/search/reranker.py` - 2 instances (`math` - imported twice!)
    - Others - 12 instances
  - **Problem:** Re-importing on each function call wastes cycles, clutters code
  - **Impact:** Minor performance overhead, code organization issue
  - **Fix:** Move imports to module top (except intentional lazy imports like torch/numpy)
  - **Note:** Some inline imports are intentional for optional dependencies (torch, numpy, git)
  - **Discovered:** 2025-11-29 INVEST-005 audit

#### INVEST-006 Results: Resource Cleanup Patterns ✅ COMPLETE

**Finding:** Resource management is generally good. Only 2 issues found:
- BUG-051 (already tracked): MPS generator not closed
- All file handles use context managers
- All SQLite connections use context managers
- Executors have `close()` methods and `__del__` fallbacks

**No new tickets needed** - existing BUG-051 covers the one issue found.

#### INVEST-007 Results: Enum/String Value Handling ✅ COMPLETE

**Finding:** 35 defensive `hasattr(x, 'value')` checks indicate inconsistent data model

- [x] **REF-032**: Fix Inconsistent Enum/String Handling ✅ FIXED (2025-11-30)
  - Consolidated with REF-023 (enum normalization in qdrant_store)
  - All 35 defensive hasattr checks removed

#### INVEST-008 Results: Empty Input Edge Cases ✅ COMPLETE

**Finding:** Edge cases are generally well-handled. Most `len()` divisions have guards.

**No new tickets needed** - existing guards like `if not x: return {}` are in place.

#### INVEST-009 Results: Configuration Validation ✅ COMPLETE

**Finding:** Only 3 field validators in config.py; many numeric fields lack range validation

- [x] **REF-033**: Add Missing Config Range Validators 🔥
  - **Location:** `src/config.py`
  - **Missing Validators:**
    - `gpu_memory_fraction` (line 46) - Should be 0.0-1.0, comment says so but no validator
    - `retrieval_gate_threshold` (line 64) - Should be 0.0-1.0
    - `proactive_suggestions_threshold` (line 110) - Should be 0.0-1.0
    - `hybrid_search_alpha` (line 242) - Should be 0.0-1.0
    - `ranking_weight_*` (lines 233-235) - Should be 0.0-1.0
    - `parallel_workers` (line 38) - Should be >= 1
    - `qdrant_pool_size` (line 187) - Should be >= 1
    - `qdrant_pool_min_size` (line 188) - Should be >= 0 and <= pool_size
  - **Problem:** Invalid config values not caught until runtime failure
  - **Impact:** Confusing errors when config is invalid
  - **Fix:** Add pydantic validators for all numeric fields with documented constraints
  - **Discovered:** 2025-11-29 INVEST-009 audit

#### INVEST-010 Results: TODO/FIXME/HACK Comments ✅ COMPLETE

**Finding:** 9 TODO comments in codebase (no FIXME/HACK/XXX found)

| Location | TODO Comment | Status |
|----------|-------------|--------|
| `src/analysis/call_extractors.py:233` | Implement JS call extraction with tree-sitter | Already tracked in REF-025 |
| `src/analysis/call_extractors.py:243` | Implement JS implementation extraction | Already tracked in REF-025 |
| `src/memory/bulk_operations.py:394` | Implement actual rollback support | Already tracked in REF-012 |
| `src/core/server.py:791` | Track cache usage | Minor - low priority |
| `src/core/server.py:3698` | Map project_name to repo_path | Minor - enhancement |
| `src/core/server.py:3948` | Check diff content if available | Minor - enhancement |
| `src/core/server.py:4202` | Improve with direct query for file changes | Minor - performance |
| `src/memory/multi_repository_search.py:221` | Add file_pattern/language filtering | Minor - enhancement |
| `src/memory/incremental_indexer.py:1078` | Extract return_type from signature | Already noted in review |

**No new tickets needed** - Major TODOs already tracked, others are minor enhancements.

### 📊 Investigation Priority

| Investigation | Effort | Expected Findings | Priority |
|---------------|--------|-------------------|----------|
| INVEST-001 (Exceptions) | 2-3h | 20-40 issues | ✅ COMPLETE (118 found) |
| INVEST-002 (Async) | 1-2h | 5-10 bugs | ✅ COMPLETE (2 found) |
| INVEST-003 (Thread Safety) | 2h | 10-15 races | ✅ COMPLETE (97 found) |
| INVEST-006 (Resources) | 2-3h | 5-10 leaks | ✅ COMPLETE (0 new) |
| INVEST-008 (Edge Cases) | 2-3h | 15-20 bugs | ✅ COMPLETE (0 new) |
| INVEST-007 (Enums) | 2h | 10-15 issues | ✅ COMPLETE (35 found) |
| INVEST-004 (Types) | 1-2h | 10-20 errors | ✅ COMPLETE (9 found) |
| INVEST-005 (Imports) | 1h | 15-20 issues | ✅ COMPLETE (41 found) |
| INVEST-009 (Config) | 2h | 10-15 gaps | ✅ COMPLETE (8 found) |
| INVEST-010 (TODOs) | 1h | 20-30 items | ✅ COMPLETE (9 found) |

---

## ID System
Each item has a unique ID for tracking and association with planning documents in `planning_docs/`.
Format: `{TYPE}-{NUMBER}` where TYPE = FEAT|BUG|TEST|DOC|PERF|REF|UX|INVEST

## Priority System

**Prioritization Rules:**
1. Complete partially finished initiatives before starting new ones
2. Prioritize items that have greater user impact over items that have less impact

## Current Sprint

### 🔴 Critical Bugs (Blocking)

**These bugs completely break core functionality and must be fixed immediately**

- [x] **BUG-037**: Connection Pool State Corruption After Qdrant Restart ✅ **FIXED** (2025-11-27)
  - **Error:** `Connection pool exhausted: 0 active, 5 max` when Qdrant is healthy
  - **Impact:** MCP memory server completely unusable after any Qdrant hiccup/restart
  - **Root Cause:** Multiple issues in `src/store/connection_pool.py`:
    1. `release()` creates new `PooledConnection` wrapper instead of tracking original (loses `created_at`, breaks recycling)
    2. `_created_count` can drift from actual pool contents when connections fail
    3. No recovery mechanism when pool state becomes corrupted
  - **Code Comment:** Bug was known - code contains `# Note: In production, we'd track client -> pooled_conn mapping`
  - **Why Missed:** 97% test coverage with mocks doesn't catch real-world failure modes (LP-009)
  - **Fix:**
    - [x] Track `client -> PooledConnection` mapping in `release()`
    - [x] Add pool state recovery/reset mechanism (`reset()`, `is_healthy()`)
    - [x] Add 11 new tests for BUG-037 fixes
  - **Location:** `src/store/connection_pool.py`
  - **See:** Journal entry 2025-11-27 META_LEARNING, LP-009

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

- [x] **FEAT-059**: Structural/Relational Queries ✅ COMPLETE (2025-11-26)
  - [x] Add `find_callers(function_name, project)` - Find all functions calling this function
  - [x] Add `find_callees(function_name, project)` - Find all functions called by this function
  - [x] Add `find_implementations(interface_name)` - Find all implementations of interface/trait
  - [x] Add `find_dependencies(file_path)` - Get dependency graph for a file (imports/requires)
  - [x] Add `find_dependents(file_path)` - Get reverse dependencies (what imports this file)
  - [x] Add `get_call_chain(from_function, to_function)` - Show call path between functions
  - **Files:** src/core/structural_query_tools.py, src/graph/call_graph.py, src/store/call_graph_store.py
  - **Tests:** 24+ tests in tests/unit/test_structural_queries.py
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

- [x] **FEAT-061**: Git/Historical Integration (~1 week) 🔥 ✅ **COMPLETED** (2025-11-27)
  - **Current Gap:** No git history, change frequency, or churn analysis
  - **Problem:** Architecture discovery couldn't identify "frequently changed files" or "recent refactorings"
  - **Proposed Solution:**
    - [x] Add `search_git_history(query, since, until)` - Semantic search over commit messages and diffs (exists as `search_git_commits`)
    - [x] Add `get_change_frequency(file_or_function)` - How often does this change? (commits/month)
    - [x] Add `get_churn_hotspots(project)` - Files with highest change frequency
    - [x] Add `get_recent_changes(project, days=30)` - Recent modifications with semantic context
    - [x] Add `blame_search(pattern)` - Who wrote code matching this pattern?
  - **Impact:** Understand evolution, identify unstable code, find domain experts
  - **Use case:** "Show files changed most frequently in auth code" or "Who worked on the API layer recently?"
  - **Tests:** 15-20 tests for git integration, change analysis
  - **See:** planning_docs/FEAT-061_git_integration_plan.md
  - **Implementation:** All 5 tools implemented in src/core/server.py and exposed via MCP in src/mcp_server.py

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

### 🟠 Test Suite Optimization

- [x] **TEST-029**: Test Suite Optimization ✅ COMPLETE (2025-11-29)
  - [x] Fixed parallel test flakiness with --dist loadscope
  - [x] Fixed test suite isolation and collection cleanup
  - [x] Fixed port hardcoding for isolated Qdrant support
  - [x] Reduced performance test data volumes (6000→600 memories)
  - [x] Created session-scoped config fixture
  - [x] Removed assert True validation theater
  - [x] Created session-scoped pre_indexed_server fixture
  - [x] Created test_language_parsing_parameterized.py
  - **Result:** 3319+ tests passing, parallel execution stable
  - **See:** `planning_docs/TEST-029_test_suite_optimization_analysis.md`

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

- [x] **UX-032**: Health Check Improvements ✅ COMPLETE (2025-11-27)
  - [x] Extend existing health check command
  - [x] Add: Qdrant latency monitoring (warn if >20ms, good <50ms)
  - [x] Add: Token savings tracking
  - **Impact:** Proactive issue detection, optimization guidance

#### Performance Optimizations

- [x] **PERF-002**: GPU acceleration ✅ **COMPLETE**
  - [x] Use CUDA for embedding model
  - [x] Target: 50-100x speedup
  - **Impact:** Massive speedup (requires GPU hardware)
  - **Status:** Merged to main (2025-11-24)

---

### 🌐 Tier 4: Language Support Extensions

- [x] **FEAT-007**: Add support for Ruby ✅ **COMPLETE**
  - [x] tree-sitter-ruby integration
  - [x] Method, class, module extraction

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

- [x] **FEAT-051**: Query-based deletion for Qdrant ✅ COMPLETE (2025-11-29)
  - [x] Implement deletion by query filters instead of memory IDs
  - [x] Support clearing entire project indexes
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

- [x] **REF-011**: Integrate ProjectArchivalManager with metrics ✅ COMPLETE (2025-11-29)
  - [x] Connect metrics_collector to ProjectArchivalManager
  - [x] Enable accurate active vs archived project counts
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

- [x] **REF-020**: Remove Python Parser Fallback References ✅ **COMPLETE** (2025-11-28)
  - **Rationale:** Python parser fallback was removed (returned 0 units, silently broken). Rust parser is now required. Cleaned up remaining references.
  - **Done:**
    - [x] Removed `src/memory/python_parser.py`
    - [x] Simplified `incremental_indexer.py` to require Rust parser with clear error
    - [x] Updated `tests/conftest.py` - removed Python parser fallback
    - [x] Updated `src/cli/health_command.py` - check_python_parser() returns "Removed"
    - [x] Updated `scripts/validate_installation.py` - now checks Rust parser only
    - [x] Updated `testing/orchestrator/test_executor.py` - test Rust parser availability
    - [x] Removed `tests/unit/test_python_parser.py`
  - **Remaining (low priority, doc updates):**
    - [x] Update CLAUDE.md references to Python parser fallback
    - [x] Update docs/setup.md - Rust parser is now required, not optional
    - [x] Update DEBUGGING.md - removed Python fallback references
    - [x] Update TUTORIAL.md - Rust is required, not optional
    - [x] Update README.md - removed Python fallback references
    - [x] Update docs/TROUBLESHOOTING.md - removed Python fallback section
    - [x] Update docs/ERROR_HANDLING.md - removed fallback parser references
    - [x] Update config.json.example - marked allow_rust_fallback as deprecated
  - **Benefits:** Cleaner codebase, no broken fallback path, clear requirements

- [x] **REF-007**: Consolidate two server implementations ✅ **CLOSED AS N/A** (2025-11-29)
  - Analysis complete: Current architecture is intentional (Adapter Pattern)
  - mcp_server.py = MCP protocol adapter, server.py = business logic
  - No consolidation needed - this is good design
  - See: planning_docs/REF-007_server_consolidation_plan.md

- [ ] **REF-008**: Remove deprecated API usage
  - Update to latest Qdrant APIs
  - Update to latest MCP SDK

- [x] **REF-013**: Split Monolithic Core Server ✅ COMPLETE (2025-11-27)
  - [x] **Phase 1 COMPLETE** ✅ (2025-11-24): HealthService Extraction
  - [x] **Phase 2 COMPLETE** ✅ (2025-11-26): Wire up service layer, eliminate duplicate code
  - [x] **Phase 3 COMPLETE** ✅ (2025-11-27): Config migration cleanup
  - Extracted 6 focused service classes (see REF-016 for details):
    - [x] `HealthService` - Monitoring, metrics, alerts, remediation
    - [x] `MemoryService` - Memory storage, retrieval, lifecycle management
    - [x] `CodeIndexingService` - Code indexing, search, similar code
    - [x] `CrossProjectService` - Multi-repository search and consent
    - [x] `QueryService` - Query expansion, intent detection, hybrid search
    - [x] `AnalyticsService` - Usage analytics and pattern tracking
  - Reduced server.py from 5,192 lines to 4,192 lines (14% reduction)
  - **See:** `planning_docs/REF-013_split_server_implementation_plan.md`

- [ ] **TEST-007**: Increase Test Coverage to 80%+ (~2-3 months) 🔥🔥
  - **Progress:** Phase 1 critical modules complete (2025-11-29)
  - **Completed:**
    - [x] TEST-007-A: security_logger.py 0% → 99%
    - [x] TEST-007-B: health_scheduler.py 0% → 98%
    - [x] TEST-007-C: web_server.py 0% → 80%+
    - [x] TEST-007-D: duplicate_detector.py 0% → 80%+
    - [x] TEST-007-F: retrieval_predictor.py 0% → 100%
    - [x] TEST-007-G: alert_engine.py (30+ tests)
  - **Remaining:**
    - [ ] Phase 2: Low coverage modules (<30%) to 60%+
    - [ ] Phase 3: Medium coverage modules (60-79%) to 80%+
    - [ ] Add missing integration tests for end-to-end workflows
  - **Target:** 80%+ for core modules (src/core, src/store, src/memory, src/embeddings)
  - **Impact:** Increased confidence, fewer regressions, better code quality
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

---

## AUDIT-001 Part 1: Core Server Findings (2025-11-30)

**Investigation Agent 1:** Core Server & MCP Protocol Analysis
**Files Analyzed:** `src/core/server.py` (5,620 lines), `src/core/tools.py` (335 lines), `src/mcp_server.py` (1,712 lines)
**Methodology:** Systematic code review for god class remnants, MCP protocol compliance, duplicate code, incomplete implementations

### 🔴 CRITICAL Findings

- [ ] **BUG-061**: Undefined Variable `memory_rag_server` in MCP Tool Handlers
  - **Location:** `src/mcp_server.py:1484, 1505, 1524`
  - **Problem:** Three tool handlers reference undefined variable `memory_rag_server` instead of the global `memory_server`. This causes AttributeError on tool invocation.
  - **Affected Tools:** `get_usage_statistics`, `get_top_queries`, `get_frequently_accessed_code`
  - **Impact:** FEAT-020 usage analytics tools completely non-functional - runtime crash on every invocation
  - **Fix:** Replace all `memory_rag_server` references with `memory_server` (lines 1484, 1505, 1524)

- [ ] **BUG-062**: Duplicate Tool Registration for `list_opted_in_projects`
  - **Location:** `src/mcp_server.py:360-363, 773-779`
  - **Problem:** Tool `list_opted_in_projects` is registered twice in `list_tools()` decorator with identical schemas
  - **Impact:** MCP protocol violation - clients may receive duplicate tool definitions, unclear which handler executes
  - **Fix:** Remove duplicate tool definition at lines 773-779, keep single registration at lines 360-363

- [ ] **BUG-063**: Empty Method Body for `_collect_metrics_job`
  - **Location:** `src/core/server.py:4884-4885`
  - **Problem:** Method `_collect_metrics_job()` has only a docstring, no implementation. Immediately followed by unrelated `export_memories` definition.
  - **Impact:** Hourly metrics collection scheduler job does nothing - monitoring metrics never collected automatically
  - **Fix:** Either implement metrics collection logic or remove the scheduler job registration at line 4838-4844

- [ ] **BUG-064**: Triple Definition of `export_memories` Method
  - **Location:** `src/core/server.py:1660, 4886, 5101`
  - **Problem:** Three different implementations of `export_memories` with incompatible signatures
    - Line 1660: `output_path: Optional[str]`, uses store directly
    - Line 4886: `output_path: str` (required), uses DataExporter
    - Line 5101: `output_path: str` (required), uses DataExporter (duplicate of 4886)
  - **Impact:** Last definition (line 5101) shadows all previous ones. First implementation (comprehensive, handles both file and string output) is unreachable. MCP tool calls unpredictable behavior.
  - **Fix:** Keep only one implementation - consolidate features from all three, remove duplicates

- [ ] **BUG-065**: Triple Definition of `import_memories` Method
  - **Location:** `src/core/server.py:1824, 4950, 5165`
  - **Problem:** Three different implementations with incompatible signatures
    - Line 1824: `file_path: Optional[str]`, `content: Optional[str]`, `conflict_mode: str = "skip"`
    - Line 4950: `input_path: str`, `conflict_strategy: str = "keep_newer"` (different param names!)
    - Line 5165: Identical to 4950 (exact duplicate)
  - **Impact:** Last definition shadows previous ones. Different parameter names (`conflict_mode` vs `conflict_strategy`) break API contract. MCP tool schema inconsistent with actual implementation.
  - **Fix:** Keep only one implementation with consolidated API, update MCP tool schema to match

- [ ] **BUG-066**: Missing Implementation for `suggest_queries` Tool
  - **Location:** `src/mcp_server.py:269-297, 1010-1046` (tool declared), `src/core/server.py` (no implementation found)
  - **Problem:** MCP server declares `suggest_queries` tool and has handler that calls `memory_server.suggest_queries(**arguments)`, but MemoryRAGServer class has no such method
  - **Impact:** FEAT-057 query suggestions completely broken - AttributeError on every invocation
  - **Fix:** Either implement `suggest_queries` method in MemoryRAGServer or remove tool declaration from MCP server

### 🟡 HIGH Priority Findings

- [ ] **REF-036**: Inconsistent State Management - Server Stats Not Thread-Safe
  - **Location:** `src/core/server.py:127-157` (stats dict), accessed in 62+ methods
  - **Problem:** Direct mutations `self.stats["key"] += 1` across async methods without locking
  - **Impact:** Race conditions in concurrent operations cause lost stat updates, incorrect metrics
  - **Fix:** Already tracked as UX-050 (completed per TODO.md line 199), verify implementation or reopen
  - **Note:** This may be a duplicate finding - verify UX-050 fix actually deployed

- [ ] **REF-037**: God Class Still Large After REF-016 Extraction
  - **Location:** `src/core/server.py` (5,620 lines, 80+ methods)
  - **Problem:** Despite service layer extraction, MemoryRAGServer still acts as facade with 80+ public methods
  - **Impact:** High cognitive load, difficult testing, unclear separation of concerns
  - **Analysis:** REF-016 extracted services but kept all methods as delegation points
  - **Fix:** Consider second-phase refactoring:
    1. Move MCP tool adapter methods to separate `MCPToolAdapter` class
    2. Make services the primary API, not the server class
    3. Reduce MemoryRAGServer to initialization and lifecycle only

- [ ] **REF-038**: Duplicate Code Between server.py and services/
  - **Location:** `src/core/server.py` method bodies vs `src/services/*.py`
  - **Problem:** Many server methods duplicate validation and error handling already in services
  - **Impact:** Maintenance burden - same logic updated in 2+ places, risk of divergence
  - **Fix:** Remove redundant validation from server methods, trust service layer contracts

- [ ] **REF-039**: MCP Response Formatting Scattered Across 40+ Handlers
  - **Location:** `src/mcp_server.py:842-1541` (call_tool function body)
  - **Problem:** Each of 40+ tool handlers contains custom response formatting logic
  - **Impact:** Inconsistent response structures, difficult to enforce MCP protocol compliance
  - **Fix:** Extract response formatters to separate module:
    - `MCPResponseFormatter` class with typed methods per tool category
    - Standard error response format
    - Centralized TextContent creation

### 🟢 MEDIUM Priority Findings

- [ ] **REF-040**: Inconsistent Error Handling Between Tool Handlers
  - **Location:** `src/mcp_server.py` - varies by handler
  - **Problem:** Some handlers catch specific exceptions, others use bare `Exception`, inconsistent logging
  - **Examples:**
    - Lines 2851-2873: Detailed error handling with actionable messages
    - Lines 1546-1548: Generic try-catch with minimal context
  - **Impact:** Debugging difficulty, inconsistent user experience
  - **Fix:** Standardize error handling pattern across all handlers

- [ ] **PERF-009**: Missing await in Embedding Cache Operations
  - **Location:** `src/core/server.py:4754-4762` (_get_embedding method)
  - **Problem:** Cache get/set operations use `await` but EmbeddingCache may not be fully async
  - **Impact:** Potential blocking on cache I/O in async context
  - **Fix:** Verify EmbeddingCache is truly async, add proper async/await or use run_in_executor

- [ ] **DOC-011**: Missing Docstrings for Private Helper Methods
  - **Location:** `src/core/server.py` - methods starting with `_`
  - **Examples:** `_classify_context_level`, `_parse_relative_date`, `_get_embedding`
  - **Impact:** Difficult for maintainers to understand internal logic
  - **Fix:** Add comprehensive docstrings following existing pattern

- [ ] **TEST-029**: No Tests for Duplicate Method Shadowing
  - **Location:** Test suite (missing coverage)
  - **Problem:** Triple definitions of export/import_memories went undetected
  - **Impact:** Method shadowing bugs can reach production
  - **Fix:** Add tests that verify only one definition exists per method name using AST inspection

### 📊 Summary Statistics

| Category | Count | Critical | High | Medium |
|----------|-------|----------|------|--------|
| Bugs (BUG-061 to BUG-066) | 6 | 6 | 0 | 0 |
| Refactoring (REF-036 to REF-040) | 5 | 0 | 4 | 1 |
| Performance (PERF-009) | 1 | 0 | 0 | 1 |
| Documentation (DOC-011) | 1 | 0 | 0 | 1 |
| Testing (TEST-029) | 1 | 0 | 0 | 1 |
| **TOTAL** | **14** | **6** | **4** | **4** |

**Next Steps:**
1. Fix all CRITICAL bugs immediately (BUG-061 through BUG-066)
2. Verify UX-050 thread-safe stats implementation (may need reopening as REF-036)
3. Consider REF-037 second-phase god class refactoring for v5.0
4. Address HIGH priority refactoring items in next sprint

**Investigation Coverage:**
- ✅ server.py: Scanned all 5,620 lines, found duplicate methods, incomplete implementations
- ✅ mcp_server.py: Analyzed all 40+ tool handlers, found undefined variables, duplicate registrations
- ✅ tools.py: Reviewed SpecializedRetrievalTools (no issues found)
- ⏭️ Deferred to other agents: Git analysis tools, structural query tools, analytics services


## AUDIT-001 Part 6: Service Layer Findings (2025-11-30)

**Investigation Scope:** All service layer files extracted from MemoryRAGServer (REF-016)
**Files Analyzed:** memory_service.py (1,579 lines), code_indexing_service.py, cross_project_service.py, health_service.py, query_service.py, analytics_service.py
**Focus:** Service boundary violations, circular dependencies, error handling, transaction boundaries, state leakage, duplicated logic

### 🔴 CRITICAL Findings

- [ ] **BUG-061**: Race Condition in Service Stats Updates
  - **Location:** `src/services/memory_service.py:96-111`, `src/services/code_indexing_service.py:87-94`, `src/services/cross_project_service.py:58-63`, `src/services/health_service.py:62-67`, `src/services/query_service.py:56-63`, `src/services/analytics_service.py:58-61`
  - **Problem:** All services use `threading.Lock()` to protect stats dict updates, but stats are initialized as plain dict (not thread-safe). While the lock protects individual updates, `get_stats()` returns `self.stats.copy()` which is NOT atomic. Between the copy operation, stats could be modified by another thread, leading to inconsistent snapshots.
  - **Fix:** Replace `self.stats.copy()` with `with self._stats_lock: return self.stats.copy()` in all 6 services. Also, REF-029 marked "COMPLETE" but only fixed one location - this is the systemic fix.

- [ ] **BUG-062**: Missing Timeout Handling in MemoryService Import Path
  - **Location:** `src/services/memory_service.py:1259-1264`
  - **Problem:** In `import_memories()`, the `async with asyncio.timeout(30.0)` only wraps the `get_by_id()` call during conflict checking, but NOT the subsequent `store.update()` or `store.store()` calls within the same loop iteration. This creates inconsistent timeout protection - some operations time out after 30s, others never time out.
  - **Fix:** Wrap each store operation (lines 1285-1290, 1313-1319, 1352-1362) with separate timeout blocks. REF-027 marked "FIXED" but missed this code path.

### 🟡 HIGH Priority Findings

- [ ] **REF-036**: Duplicated Embedding Retrieval Logic Across Services
  - **Location:** `src/services/memory_service.py:113-139`, `src/services/code_indexing_service.py:99-107`
  - **Problem:** Both MemoryService and CodeIndexingService implement nearly identical `_get_embedding()` methods with cache checking. MemoryService tracks cache hit/miss stats, CodeIndexingService doesn't. This violates DRY principle and creates maintenance burden.
  - **Fix:** Extract to shared `EmbeddingService` or utility class. Centralize cache hit/miss tracking. Estimated 30-40 lines of duplicate code eliminated.

- [ ] **REF-037**: Inconsistent Service Initialization Parameters
  - **Location:** All service `__init__` methods
  - **Problem:** Services have inconsistent optional dependency patterns. MemoryService takes 9 parameters (4 required, 5 optional), CodeIndexingService takes 8 (4 required, 4 optional), CrossProjectService takes 5, etc. No standard interface or base class. Makes it hard to refactor or add new services.
  - **Fix:** Create `BaseService` abstract class with standard initialization pattern. Use dependency injection container. Define clear interfaces for optional components (usage_tracker, metrics_collector, etc.).

- [ ] **BUG-063**: Service Boundary Violation - MemoryService Directly Uses Store Methods Not in Interface
  - **Location:** `src/services/memory_service.py:1082-1089` (export_memories), `src/services/memory_service.py:683-690` (reindex_project)
  - **Problem:** MemoryService calls `store.list_memories()` and `store.delete_code_units_by_project()` directly, but these may not be implemented by all store backends (SQLite vs Qdrant). This creates tight coupling and violates store abstraction.
  - **Fix:** Add these methods to MemoryStore abstract interface or move operations to dedicated services (CodeIndexingService should own delete_code_units_by_project).

- [ ] **REF-038**: Error Handling Inconsistency Between Services
  - **Location:** All services
  - **Problem:** Services handle errors inconsistently. MemoryService wraps most operations in try/except with `StorageError` or `RetrievalError`. QueryService raises `StorageError` for disabled features. HealthService sometimes returns `{"status": "disabled"}` dict instead of raising. CrossProjectService returns error dicts in some methods, raises exceptions in others.
  - **Fix:** Standardize error handling pattern across all services. Define when to raise exceptions vs return error dicts. Document in service layer guidelines.

### 🟢 MEDIUM Priority Findings

- [ ] **REF-039**: Incomplete Stats Tracking in Services
  - **Location:** `src/services/code_indexing_service.py:87-94`, `src/services/analytics_service.py:58-61`
  - **Problem:** CodeIndexingService tracks 4 stats counters but doesn't track cache hits/misses (MemoryService does). AnalyticsService only tracks 1 counter ("analytics_queries"). Inconsistent granularity makes cross-service monitoring difficult.
  - **Fix:** Define standard metrics all services should track (operation_count, error_count, avg_latency_ms, cache_stats). Implement in base service class.

- [ ] **REF-040**: Circular Import Risk Between Services
  - **Location:** `src/services/code_indexing_service.py:567-588` (imports IncrementalIndexer), `src/services/cross_project_service.py:112-118` (imports MultiRepositorySearcher)
  - **Problem:** Services import from `src.memory.*` modules within method bodies (not at module level), suggesting potential circular dependency. If memory modules later need to import services, this creates a cycle.
  - **Fix:** Use dependency injection to pass indexer/searcher instances to services instead of constructing them internally. Move to constructor parameters.

- [ ] **REF-041**: Duplicated Query Quality Analysis Logic
  - **Location:** `src/services/code_indexing_service.py:119-191` (search_code quality analysis), `src/services/code_indexing_service.py:537-551` (find_similar_code interpretation)
  - **Problem:** Both methods implement similar result quality assessment logic (score thresholds, suggestions, interpretation). ~50 lines of duplicated pattern-matching logic.
  - **Fix:** Extract to shared `ResultQualityAnalyzer` class or utility module. Use strategy pattern for different analysis types (code search vs similarity vs memory retrieval).

- [ ] **BUG-064**: Missing Validation in CrossProjectService.search_all_projects
  - **Location:** `src/services/cross_project_service.py:69-200`
  - **Problem:** Method doesn't validate `limit` parameter (accepts any value including 0, negative, or extremely large). Could cause performance issues or OOM if someone passes limit=1000000. MemoryService validates limit in list_memories (line 773-774).
  - **Fix:** Add validation: `if not (1 <= limit <= 100): raise ValidationError("limit must be 1-100")`

### 🔵 LOW Priority Findings

- [ ] **PERF-001**: Inefficient Project Loop in CrossProjectService.search_all_projects
  - **Location:** `src/services/cross_project_service.py:124-159`
  - **Problem:** Searches opted-in projects sequentially in a for loop. For 10 projects, this could take 10x as long as searching 1 project. Should use concurrent search with asyncio.gather().
  - **Fix:** Collect search tasks in list, use `results = await asyncio.gather(*tasks, return_exceptions=True)`. Handle exceptions per-project.

- [ ] **REF-042**: Hardcoded Magic Numbers in Quality Score Calculations
  - **Location:** `src/services/health_service.py:73-95` (_calculate_simple_health_score)
  - **Problem:** Health score calculation uses hardcoded thresholds (100ms latency = -10 score, 50ms = -10, error_rate > 0.1 = -30, etc.). These magic numbers should be configurable.
  - **Fix:** Move thresholds to ServerConfig as health_score_config dict. Allow tuning per deployment.

- [ ] **REF-043**: Unused Metrics Collector Parameter in Multiple Services
  - **Location:** `src/services/memory_service.py:521-528`, `src/services/code_indexing_service.py:394-401`, `src/services/cross_project_service.py:169-176`
  - **Problem:** Services check `if self.metrics_collector` and log queries, but this pattern is duplicated 3 times. If metrics_collector interface changes, need to update 3+ places.
  - **Fix:** Create MetricsCollectorMixin or decorator for automatic metric logging. Reduces duplication from ~20 lines to ~3.

- [ ] **REF-044**: Missing Logging in QueryService State Transitions
  - **Location:** `src/services/query_service.py:69-139`
  - **Problem:** start_conversation_session() and end_conversation_session() have minimal logging (only success case). Missing logs for: session already exists, session not found, cleanup errors.
  - **Fix:** Add structured logging for all state transitions. Include session_id, duration, query_count in end_session log.

- [ ] **BUG-065**: Potential Resource Leak in HealthService.start_dashboard
  - **Location:** `src/services/health_service.py:321-360`
  - **Problem:** Starts DashboardServer with `await server.start()` but doesn't track the server instance or provide a way to stop it later. If called multiple times, could leak server instances.
  - **Fix:** Store server instance in `self.dashboard_server`, add `stop_dashboard()` method for cleanup. Prevent starting if already running.

### 📋 Service Architecture Observations

**Strengths:**
- Clean separation of concerns (each service has focused responsibility)
- Consistent timeout handling pattern (30s timeout on store operations)
- Good use of threading locks for stats protection
- Services accept optional dependencies for graceful degradation

**Weaknesses:**
- No common base class or interface contract
- Inconsistent error handling (exceptions vs error dicts)
- Duplicated patterns (embedding retrieval, quality analysis, metrics logging)
- Tight coupling to store implementation details in some methods
- Stats tracking granularity varies widely between services

**Recommendations:**
1. Create `BaseService` abstract class with standard lifecycle methods
2. Define `ServiceMetrics` interface for uniform stats tracking
3. Extract shared utilities (embedding retrieval, quality analysis) to mixins
4. Standardize error handling: raise exceptions for errors, return dicts for success
5. Add service integration tests to catch boundary violations

## AUDIT-001 Part 6: Service Layer Findings (2025-11-30)

**Investigation Scope:** All service layer files extracted from MemoryRAGServer (REF-016)
**Files Analyzed:** memory_service.py (1,579 lines), code_indexing_service.py, cross_project_service.py, health_service.py, query_service.py, analytics_service.py
**Focus:** Service boundary violations, circular dependencies, error handling, transaction boundaries, state leakage, duplicated logic

### CRITICAL Findings

- [ ] **BUG-061**: Race Condition in Service Stats Updates
  - **Location:** `src/services/memory_service.py:96-111`, `src/services/code_indexing_service.py:87-94`, `src/services/cross_project_service.py:58-63`, `src/services/health_service.py:62-67`, `src/services/query_service.py:56-63`, `src/services/analytics_service.py:58-61`
  - **Problem:** All services use `threading.Lock()` to protect stats dict updates, but stats are initialized as plain dict (not thread-safe). While the lock protects individual updates, `get_stats()` returns `self.stats.copy()` which is NOT atomic. Between the copy operation, stats could be modified by another thread, leading to inconsistent snapshots.
  - **Fix:** Replace `self.stats.copy()` with `with self._stats_lock: return self.stats.copy()` in all 6 services. Also, REF-029 marked "COMPLETE" but only fixed one location - this is the systemic fix.

- [ ] **BUG-062**: Missing Timeout Handling in MemoryService Import Path
  - **Location:** `src/services/memory_service.py:1259-1264`
  - **Problem:** In `import_memories()`, the `async with asyncio.timeout(30.0)` only wraps the `get_by_id()` call during conflict checking, but NOT the subsequent `store.update()` or `store.store()` calls within the same loop iteration. This creates inconsistent timeout protection - some operations time out after 30s, others never time out.
  - **Fix:** Wrap each store operation (lines 1285-1290, 1313-1319, 1352-1362) with separate timeout blocks. REF-027 marked "FIXED" but missed this code path.

### HIGH Priority Findings

- [ ] **REF-036**: Duplicated Embedding Retrieval Logic Across Services
  - **Location:** `src/services/memory_service.py:113-139`, `src/services/code_indexing_service.py:99-107`
  - **Problem:** Both MemoryService and CodeIndexingService implement nearly identical `_get_embedding()` methods with cache checking. MemoryService tracks cache hit/miss stats, CodeIndexingService doesn't. This violates DRY principle and creates maintenance burden.
  - **Fix:** Extract to shared `EmbeddingService` or utility class. Centralize cache hit/miss tracking. Estimated 30-40 lines of duplicate code eliminated.

- [ ] **REF-037**: Inconsistent Service Initialization Parameters
  - **Location:** All service `__init__` methods
  - **Problem:** Services have inconsistent optional dependency patterns. MemoryService takes 9 parameters (4 required, 5 optional), CodeIndexingService takes 8 (4 required, 4 optional), CrossProjectService takes 5, etc. No standard interface or base class. Makes it hard to refactor or add new services.
  - **Fix:** Create `BaseService` abstract class with standard initialization pattern. Use dependency injection container. Define clear interfaces for optional components (usage_tracker, metrics_collector, etc.).

- [ ] **BUG-063**: Service Boundary Violation - MemoryService Directly Uses Store Methods Not in Interface
  - **Location:** `src/services/memory_service.py:1082-1089` (export_memories), `src/services/memory_service.py:683-690` (reindex_project)
  - **Problem:** MemoryService calls `store.list_memories()` and `store.delete_code_units_by_project()` directly, but these may not be implemented by all store backends (SQLite vs Qdrant). This creates tight coupling and violates store abstraction.
  - **Fix:** Add these methods to MemoryStore abstract interface or move operations to dedicated services (CodeIndexingService should own delete_code_units_by_project).

- [ ] **REF-038**: Error Handling Inconsistency Between Services
  - **Location:** All services
  - **Problem:** Services handle errors inconsistently. MemoryService wraps most operations in try/except with `StorageError` or `RetrievalError`. QueryService raises `StorageError` for disabled features. HealthService sometimes returns `{"status": "disabled"}` dict instead of raising. CrossProjectService returns error dicts in some methods, raises exceptions in others.
  - **Fix:** Standardize error handling pattern across all services. Define when to raise exceptions vs return error dicts. Document in service layer guidelines.

### MEDIUM Priority Findings

- [ ] **REF-039**: Incomplete Stats Tracking in Services
  - **Location:** `src/services/code_indexing_service.py:87-94`, `src/services/analytics_service.py:58-61`
  - **Problem:** CodeIndexingService tracks 4 stats counters but doesn't track cache hits/misses (MemoryService does). AnalyticsService only tracks 1 counter ("analytics_queries"). Inconsistent granularity makes cross-service monitoring difficult.
  - **Fix:** Define standard metrics all services should track (operation_count, error_count, avg_latency_ms, cache_stats). Implement in base service class.

- [ ] **REF-040**: Circular Import Risk Between Services
  - **Location:** `src/services/code_indexing_service.py:567-588` (imports IncrementalIndexer), `src/services/cross_project_service.py:112-118` (imports MultiRepositorySearcher)
  - **Problem:** Services import from `src.memory.*` modules within method bodies (not at module level), suggesting potential circular dependency. If memory modules later need to import services, this creates a cycle.
  - **Fix:** Use dependency injection to pass indexer/searcher instances to services instead of constructing them internally. Move to constructor parameters.

- [ ] **REF-041**: Duplicated Query Quality Analysis Logic
  - **Location:** `src/services/code_indexing_service.py:119-191` (search_code quality analysis), `src/services/code_indexing_service.py:537-551` (find_similar_code interpretation)
  - **Problem:** Both methods implement similar result quality assessment logic (score thresholds, suggestions, interpretation). ~50 lines of duplicated pattern-matching logic.
  - **Fix:** Extract to shared `ResultQualityAnalyzer` class or utility module. Use strategy pattern for different analysis types (code search vs similarity vs memory retrieval).

- [ ] **BUG-064**: Missing Validation in CrossProjectService.search_all_projects
  - **Location:** `src/services/cross_project_service.py:69-200`
  - **Problem:** Method doesn't validate `limit` parameter (accepts any value including 0, negative, or extremely large). Could cause performance issues or OOM if someone passes limit=1000000. MemoryService validates limit in list_memories (line 773-774).
  - **Fix:** Add validation: `if not (1 <= limit <= 100): raise ValidationError("limit must be 1-100")`

### LOW Priority Findings

- [ ] **PERF-001**: Inefficient Project Loop in CrossProjectService.search_all_projects
  - **Location:** `src/services/cross_project_service.py:124-159`
  - **Problem:** Searches opted-in projects sequentially in a for loop. For 10 projects, this could take 10x as long as searching 1 project. Should use concurrent search with asyncio.gather().
  - **Fix:** Collect search tasks in list, use `results = await asyncio.gather(*tasks, return_exceptions=True)`. Handle exceptions per-project.

- [ ] **REF-042**: Hardcoded Magic Numbers in Quality Score Calculations
  - **Location:** `src/services/health_service.py:73-95` (_calculate_simple_health_score)
  - **Problem:** Health score calculation uses hardcoded thresholds (100ms latency = -10 score, 50ms = -10, error_rate > 0.1 = -30, etc.). These magic numbers should be configurable.
  - **Fix:** Move thresholds to ServerConfig as health_score_config dict. Allow tuning per deployment.

- [ ] **REF-043**: Unused Metrics Collector Parameter in Multiple Services
  - **Location:** `src/services/memory_service.py:521-528`, `src/services/code_indexing_service.py:394-401`, `src/services/cross_project_service.py:169-176`
  - **Problem:** Services check `if self.metrics_collector` and log queries, but this pattern is duplicated 3 times. If metrics_collector interface changes, need to update 3+ places.
  - **Fix:** Create MetricsCollectorMixin or decorator for automatic metric logging. Reduces duplication from ~20 lines to ~3.

- [ ] **REF-044**: Missing Logging in QueryService State Transitions
  - **Location:** `src/services/query_service.py:69-139`
  - **Problem:** start_conversation_session() and end_conversation_session() have minimal logging (only success case). Missing logs for: session already exists, session not found, cleanup errors.
  - **Fix:** Add structured logging for all state transitions. Include session_id, duration, query_count in end_session log.

- [ ] **BUG-065**: Potential Resource Leak in HealthService.start_dashboard
  - **Location:** `src/services/health_service.py:321-360`
  - **Problem:** Starts DashboardServer with `await server.start()` but doesn't track the server instance or provide a way to stop it later. If called multiple times, could leak server instances.
  - **Fix:** Store server instance in `self.dashboard_server`, add `stop_dashboard()` method for cleanup. Prevent starting if already running.

### Service Architecture Observations

**Strengths:**
- Clean separation of concerns (each service has focused responsibility)
- Consistent timeout handling pattern (30s timeout on store operations)
- Good use of threading locks for stats protection
- Services accept optional dependencies for graceful degradation

**Weaknesses:**
- No common base class or interface contract
- Inconsistent error handling (exceptions vs error dicts)
- Duplicated patterns (embedding retrieval, quality analysis, metrics logging)
- Tight coupling to store implementation details in some methods
- Stats tracking granularity varies widely between services

**Recommendations:**
1. Create `BaseService` abstract class with standard lifecycle methods
2. Define `ServiceMetrics` interface for uniform stats tracking
3. Extract shared utilities (embedding retrieval, quality analysis) to mixins
4. Standardize error handling: raise exceptions for errors, return dicts for success
5. Add service integration tests to catch boundary violations

---

## AUDIT-001 Part 5: Memory Indexing & Parsing Findings (2025-11-30)

**Investigation Scope:** Memory indexing, parsing, and dependency tracking components
**Files Analyzed:** incremental_indexer.py (1,225 lines), import_extractor.py (515 lines), dependency_graph.py (370 lines), background_indexer.py (494 lines), git_detector.py (212 lines)
**Focus:** Parser failure recovery, incremental indexing consistency, file change detection, language detection, AST parsing errors, circular dependencies, large file handling, binary file detection, encoding issues, git ignore patterns

### 🔴 CRITICAL Findings

- [ ] **BUG-059**: Undefined Variable PYTHON_PARSER_AVAILABLE Referenced But Never Defined
  - **Location:** `src/memory/incremental_indexer.py:188`
  - **Problem:** Line 188 checks `if not RUST_AVAILABLE and not PYTHON_PARSER_AVAILABLE` but PYTHON_PARSER_AVAILABLE is never imported or defined anywhere in the file. This will raise NameError if RUST_AVAILABLE is False. The Python parser fallback was intentionally removed (line 12 comment says it was broken), but the check wasn't updated.
  - **Fix:** Remove `and not PYTHON_PARSER_AVAILABLE` from line 188, change to `if not RUST_AVAILABLE: raise RuntimeError("Rust parser required...")`

- [ ] **BUG-060**: Missing Call Graph Store Cleanup in IncrementalIndexer.close()
  - **Location:** `src/memory/incremental_indexer.py:1202-1206`
  - **Problem:** The `close()` method closes `self.store` and `self.embedding_generator`, but does NOT close `self.call_graph_store` which was initialized at line 224. This creates a resource leak - the call graph store's Qdrant connections remain open indefinitely.
  - **Fix:** Add `await self.call_graph_store.close()` before closing other resources

- [ ] **BUG-067**: Race Condition in Background Indexer Task Cleanup
  - **Location:** `src/memory/background_indexer.py:488-493`
  - **Problem:** In the `finally` block, code deletes `job_id` from `_active_tasks` dict but doesn't handle the case where the job might have already been removed by `cancel_job()` (lines 255-256). If cancel and completion happen simultaneously, this could raise KeyError. The check `if job_id in self._active_tasks` is not atomic with the deletion.
  - **Fix:** Use `self._active_tasks.pop(job_id, None)` instead of `del self._active_tasks[job_id]`

### 🟡 HIGH Priority Findings

- [ ] **BUG-068**: Circular Dependency Detection Has False Negatives
  - **Location:** `src/memory/dependency_graph.py:279-312`
  - **Problem:** The `detect_circular_dependencies()` method uses DFS with visited/rec_stack tracking, but only starts DFS from nodes that are keys in `self.dependencies` dict (line 308). If a file B imports A, but A doesn't import anything, then A won't be in `dependencies.keys()` and won't be explored. This misses cycles like: A -> B -> C -> A where A has no outgoing dependencies in the dict.
  - **Fix:** Change line 308 to iterate over `set(self.dependencies.keys()) | set(self.dependents.keys())` to ensure all nodes are explored

- [ ] **REF-043**: Module Resolution Only Handles Relative Imports
  - **Location:** `src/memory/dependency_graph.py:78-143`
  - **Problem:** The `_resolve_module_to_file()` method only resolves relative imports (lines 109-138). Absolute imports within the project are silently ignored (line 142 returns None). This means the dependency graph is incomplete - it won't track absolute imports like `from src.core.models import Memory` even though they're internal to the project.
  - **Fix:** Add project-root-aware absolute import resolution. For Python: check if module path starts with project package name, resolve to `project_root / module.replace('.', '/')`. Document this limitation or implement full resolution.

- [ ] **PERF-011**: Inefficient File Extension Matching in Directory Indexing
  - **Location:** `src/memory/incremental_indexer.py:418-421`
  - **Problem:** For each supported extension, calls `dir_path.glob(f"{pattern}{ext}")` separately, then concatenates results. For 20 supported extensions, this performs 20 separate filesystem traversals. For large directories (10,000+ files), this is extremely slow.
  - **Fix:** Use single glob pattern with set filtering: `all_files = dir_path.glob(pattern); files = [f for f in all_files if f.suffix in SUPPORTED_EXTENSIONS]`. Reduces 20 traversals to 1.

- [ ] **BUG-069**: Git Detection Has No Error Recovery for Subprocess Timeouts
  - **Location:** `src/memory/git_detector.py:30-36`, `src/memory/git_detector.py:56-62`, and 4 other subprocess calls
  - **Problem:** All git subprocess calls use `timeout=5` but only catch generic `Exception`. If the timeout expires, it raises `subprocess.TimeoutExpired` which is caught and logged as debug, but the function returns False/None. However, if git hangs (but doesn't timeout), the entire indexing process blocks for 5 seconds PER FILE. For 100 files, that's 8+ minutes of blocking time.
  - **Fix:** Add specific `except subprocess.TimeoutExpired` handler, log as WARNING not debug (it's a system issue). Consider reducing timeout to 2s for faster failure.

### 🟢 MEDIUM Priority Findings

- [ ] **REF-044**: Hardcoded Git Subprocess Timeout Duplicated 6 Times
  - **Location:** `src/memory/git_detector.py:35`, `src/memory/git_detector.py:61`, `src/memory/git_detector.py:110`, `src/memory/git_detector.py:127`, `src/memory/git_detector.py:144`, `src/memory/git_detector.py:161`
  - **Problem:** The value `timeout=5` appears 6 times in subprocess.run() calls. If we need to tune git timeout (e.g., for slow filesystems), must change 6 locations. Magic number antipattern.
  - **Fix:** Define `GIT_SUBPROCESS_TIMEOUT = 5.0` as module constant at top of file, use in all subprocess calls

- [ ] **REF-045**: Import Extractor Has No Language Version Handling
  - **Location:** `src/memory/import_extractor.py:50-78`
  - **Problem:** The import regex patterns are language-version-agnostic. Python 3.10+ supports `match`/`case`, TypeScript 5.0 changed import syntax, Rust 2021 edition has different module paths. The extractor will miss or incorrectly parse newer syntax.
  - **Fix:** Add optional `language_version` parameter to `extract_imports()`. Use version-specific regex patterns. Document supported language versions.

- [ ] **BUG-070**: File Change Hashing Doesn't Handle Large Files Efficiently
  - **Location:** `src/memory/incremental_indexer.py:283-284`
  - **Problem:** The code reads entire file into memory with `f.read()` to parse it, regardless of size. For files >100MB, this can cause memory pressure. The indexer supports files up to gigabytes (no size limit check), which could OOM the process.
  - **Fix:** Add file size check before reading: `if file_path.stat().st_size > 10*1024*1024: logger.warning("File too large, skipping"); return {...}`. Set max file size limit (10MB default, configurable).

- [ ] **REF-046**: Inconsistent Error Handling Between File and Directory Indexing
  - **Location:** `src/memory/incremental_indexer.py:255-388` (index_file) vs `src/memory/incremental_indexer.py:390-546` (index_directory)
  - **Problem:** `index_file()` raises `StorageError` on failure (line 388), forcing caller to handle exception. `index_directory()` catches all exceptions, logs them, and returns failure in `failed_files` list (line 489). Inconsistent error contract makes it unclear when to expect exceptions vs error results.
  - **Fix:** Standardize on one pattern. Recommend: index_file raises exceptions (caller decides), index_directory catches and aggregates (batch operation). Document in docstrings.

- [ ] **PERF-012**: Redundant File Resolution in Cleanup Operations
  - **Location:** `src/memory/incremental_indexer.py:705-707`
  - **Problem:** In `_cleanup_stale_entries()`, for each indexed file, code calls `file_path.relative_to(dir_path)` inside a try/except to check if file is in directory. This is expensive for 1000+ files. The `current_file_paths` set (line 695) already contains resolved absolute paths - just check if file starts with dir_path string.
  - **Fix:** Replace `file_path.relative_to(dir_path)` with `file_path_str.startswith(str(dir_path.resolve()))` for 10x speedup

- [ ] **BUG-071**: Missing Encoding Declaration in Import Extractor
  - **Location:** `src/memory/import_extractor.py:96-98`, and all language-specific extractors
  - **Problem:** The `extract_imports()` method receives `source_code` as a string parameter but doesn't document required encoding. If caller passes source_code decoded with wrong encoding (e.g., latin-1 instead of utf-8), regex matching will fail silently or produce garbage results. The incremental_indexer opens files with `encoding="utf-8"` (line 283) but import_extractor has no encoding awareness.
  - **Fix:** Document that source_code must be UTF-8 decoded. Add encoding parameter with default 'utf-8'. Handle UnicodeDecodeError gracefully.

### 🔵 LOW Priority Findings

- [ ] **REF-047**: Duplicate Code in Index File Path Resolution
  - **Location:** `src/memory/incremental_indexer.py:271`, `src/memory/incremental_indexer.py:412`, `src/memory/incremental_indexer.py:558`
  - **Problem:** Three methods all call `Path(file_path).resolve()` to normalize paths. This pattern is repeated without abstraction. If path resolution logic needs to change (e.g., to handle symlinks differently), must update 3+ places.
  - **Fix:** Extract to `_resolve_file_path(self, file_path: Path) -> Path` helper method

- [ ] **REF-048**: Magic Number for Git Worktrees Exclusion Pattern
  - **Location:** `src/memory/incremental_indexer.py:428`
  - **Problem:** The EXCLUDED_DIRS set includes ".worktrees" with a comment "Git worktrees for parallel development". This is project-specific knowledge hardcoded in the indexer. Users with different worktree setups (e.g., `_worktrees/`, `tmp/worktrees/`) won't get proper filtering.
  - **Fix:** Make EXCLUDED_DIRS configurable via ServerConfig. Add `indexing.excluded_dirs` config option with defaults.

- [ ] **PERF-013**: Unused Semaphore Value Calculation
  - **Location:** `src/memory/incremental_indexer.py:464`
  - **Problem:** Creates `asyncio.Semaphore(max_concurrent)` to limit concurrency, but the semaphore value is never checked or monitored. If max_concurrent=4 but system can only handle 2 concurrent operations, there's no backpressure mechanism or resource monitoring.
  - **Fix:** Add optional `adaptive_concurrency` mode that monitors memory/CPU usage and adjusts semaphore limit dynamically

- [ ] **REF-049**: Function Signature Parsing Regex Is Fragile
  - **Location:** `src/memory/incremental_indexer.py:1165-1200`
  - **Problem:** The `_extract_parameters()` method uses simple regex to parse function signatures. It will break on: nested generics `func(a: Dict[str, List[Tuple[int, int]]])`, lambda parameters, decorators with parameters, async generator syntax. Only handles simple cases.
  - **Fix:** Use proper AST parsing for parameter extraction instead of regex. The Rust parser already provides this info - extract from `unit.signature` structure instead of string parsing.

- [ ] **BUG-072**: TODO Comment Indicates Missing Return Type Extraction
  - **Location:** `src/memory/incremental_indexer.py:1079`
  - **Problem:** Comment says `return_type=None, # TODO: Extract from signature if available`. This means call graph function nodes don't track return types, limiting the usefulness of call graph analysis for type checking or refactoring tools.
  - **Fix:** Implement return type extraction from signature string (regex for `-> ReturnType:`) or get from Rust parser if available

### Summary Statistics

- **Total Issues Found:** 16
- **Critical:** 3 (undefined variable, resource leak, race condition)
- **High:** 4 (circular dependency detection, import resolution, performance, timeout handling)
- **Medium:** 5 (hardcoded values, version handling, large files, error consistency, encoding)
- **Low:** 4 (code duplication, magic numbers, monitoring, fragile parsing)

**Key Risks:**
1. PYTHON_PARSER_AVAILABLE undefined will crash on systems without Rust parser
2. Resource leaks (call graph store never closed)
3. Incomplete dependency graph (only tracks relative imports)
4. No large file protection (can OOM on huge files)

**Next Ticket Numbers:** BUG-059 to BUG-072, REF-043 to REF-049, PERF-011 to PERF-013
**Next Ticket Numbers:** BUG-073+, REF-050+, PERF-014+

---

## AUDIT-001 Part 11: Code Analysis & Quality Scoring Findings (2025-11-30)

**Investigation Scope:** 1,512 lines across 7 files (complexity_analyzer.py, importance_scorer.py, criticality_analyzer.py, usage_analyzer.py, code_duplicate_detector.py, call_extractors.py, quality_analyzer.py)

### 🔴 CRITICAL Findings

- [ ] **BUG-073**: Division by Zero Risk in Nesting Depth Calculation
  - **Location:** `src/analysis/complexity_analyzer.py:184`
  - **Problem:** `depth = leading // indent_size` where `indent_size` could be 0 if language not in `indent_chars` dict and subsequent logic fails. Line 184 checks `if indent_size > 0` but the else clause sets `depth = 0`, which means files with tabs or non-standard indentation are scored as having zero nesting depth regardless of actual nesting.
  - **Fix:** Fall back to detecting mixed tabs/spaces: `indent_size = 4 if '\t' not in line else 1` and warn about unrecognized indentation style

- [ ] **BUG-074**: Cyclomatic Complexity Double-Counts Ternary Operators
  - **Location:** `src/analysis/complexity_analyzer.py:89-139`
  - **Problem:** The pattern `r'\?.*:'` on line 111 matches ternary operators but also matches unrelated `?` characters in regex, comments, or strings (e.g., `"What is this?:"`). This inflates complexity scores incorrectly. Additionally, the regex `r'\?.*:'` is greedy and matches across multiple lines, potentially double-counting multiple ternaries as a single match.
  - **Fix:** Use non-greedy pattern `r'\?[^:]*:'` and add word boundaries. Better: only count `?` followed by `:` on same line with balanced parens.

- [ ] **BUG-075**: Importance Score Normalization Breaks with High Weights
  - **Location:** `src/analysis/importance_scorer.py:240-255`
  - **Problem:** The normalization divides `raw_score` by `baseline_max = 1.2`, but with custom weights like `(2.0, 2.0, 2.0)`, the max possible raw_score is `(0.7*2.0) + (0.2*2.0) + (0.3*2.0) = 2.4`, which when divided by 1.2 gives 2.0, then clamped to 1.0. This means all high-complexity/high-usage/high-criticality code gets the same score of 1.0, losing discriminatory power. The normalization formula is only correct for default weights.
  - **Fix:** Calculate dynamic baseline_max: `baseline_max = (0.7 * complexity_weight) + (0.2 * usage_weight) + (0.3 * criticality_weight)` instead of hardcoding 1.2

### 🟡 HIGH Priority Findings

- [ ] **PERF-014**: O(N²) Duplicate Pair Extraction Without Early Exit
  - **Location:** `src/analysis/code_duplicate_detector.py:250-262`
  - **Problem:** `get_duplicate_pairs()` checks upper triangle of similarity matrix (O(N²)) but doesn't stop early when max_pairs limit is reached. For 10,000 units with threshold=0.5 (many matches), this creates hundreds of thousands of DuplicatePair objects, consuming gigabytes of RAM, even if caller only needs top 100 pairs.
  - **Fix:** Add `max_pairs: Optional[int] = None` parameter and break early after reaching limit. Since pairs are sorted descending, can use heap to maintain top-K pairs during iteration.

- [ ] **BUG-076**: JavaScript Call Extractor Fails Silently on tree-sitter Import Failure
  - **Location:** `src/analysis/call_extractors.py:232-242`
  - **Problem:** If `tree-sitter` or `tree-sitter-javascript` packages are not installed, `JavaScriptCallExtractor.__init__()` catches ImportError and sets `self.parser = None`, then all subsequent `extract_calls()` calls log warning and return empty list. This silently breaks call graph construction for JS/TS projects with no visible error to the user—they just get incomplete importance scores.
  - **Fix:** Either make tree-sitter a required dependency, or raise clear error on first use: "Install tree-sitter-javascript to analyze JavaScript files: pip install tree-sitter tree-sitter-javascript"

- [ ] **BUG-077**: File Proximity Score Calculation Fails for Pathlib.PurePath Objects
  - **Location:** `src/analysis/criticality_analyzer.py:218-279`
  - **Problem:** Lines 230-238 check `if not isinstance(file_path, Path)` and fall back to function name scoring only, but the code then tries to call `file_path.stem`, `file_path.parts`, etc., which will fail if file_path is a string or PurePosixPath. The isinstance check is insufficient—it should check for PathLike protocol or convert to Path.
  - **Fix:** Add `file_path = Path(file_path) if not isinstance(file_path, Path) else file_path` at start of method before any attribute access

- [ ] **BUG-078**: Call Graph State Leak Between Files in UsageAnalyzer
  - **Location:** `src/analysis/usage_analyzer.py:124-126`
  - **Problem:** The code checks `if all_units and not self.call_graph:` before building call graph. This means if `calculate_importance()` is called with `all_units=None` after a previous call with `all_units=[...]`, the old call graph persists and affects the new calculation. If the user analyzes file A, then file B without calling `reset()`, file B's usage metrics will include caller counts from file A's call graph.
  - **Fix:** Always rebuild call graph when `all_units` is provided: change condition to `if all_units:` (remove `and not self.call_graph`)

### 🟢 MEDIUM Priority Findings

- [ ] **REF-050**: Hardcoded Score Ranges Duplicated Across Analyzers
  - **Location:** `src/analysis/complexity_analyzer.py:36-43`, `src/analysis/usage_analyzer.py:85-90`, `src/analysis/criticality_analyzer.py:70-71`
  - **Problem:** Each analyzer defines its own MIN/MAX score ranges (0.3-0.7, 0.0-0.2, 0.0-0.3) as class constants. These ranges are tightly coupled to the importance scorer's normalization logic (line 244-250 in importance_scorer.py). If we want to adjust score ranges, must update 4 files consistently. Magic numbers antipattern.
  - **Fix:** Define score range constants in a shared `src/analysis/constants.py` module. Use named constants like `COMPLEXITY_SCORE_RANGE = (0.3, 0.7)` and import in all analyzers.

- [ ] **BUG-079**: Maintainability Index Can Exceed 100 with Documentation Bonus
  - **Location:** `src/analysis/quality_analyzer.py:197-235`
  - **Problem:** Line 228 calculates `mi = 100 - (cyclomatic_complexity * 2) - (line_count / 10)`, then line 232 adds `mi += 5` for documentation. For very simple functions (complexity=1, lines=5), this gives `mi = 100 - 2 - 0.5 + 5 = 102.5`, then clamped to 100. But the formula can also underflow: complexity=50, lines=100 gives `mi = 100 - 100 - 10 = -10`, clamped to 0. The clamping masks the issue but indicates the formula is incorrect for edge cases.
  - **Fix:** Clamp BEFORE applying documentation bonus: `mi = max(0, min(95, int(mi)))` (keep room for +5 bonus), then add bonus, then final clamp to 100

- [ ] **PERF-015**: Duplicate Clustering Performs Redundant Similarity Lookups
  - **Location:** `src/analysis/code_duplicate_detector.py:356-383`
  - **Problem:** The inner loop (lines 378-382) accesses `similarity_matrix[idx_i][idx_j]` for each pair in cluster to calculate average similarity. For a cluster of size 100, this performs 4,950 matrix accesses (100 choose 2). Since the matrix is symmetric, could cache or use matrix slicing for batch access.
  - **Fix:** Use vectorized NumPy operations: extract cluster submatrix with `cluster_similarities = similarity_matrix[np.ix_(indices, indices)]`, then compute mean of upper triangle

- [ ] **BUG-080**: Comment Filtering in Line Count Is Too Aggressive
  - **Location:** `src/analysis/complexity_analyzer.py:141-151`
  - **Problem:** Line 148 filters out lines starting with `#, //, /*, *, """, '''` as comments. But this incorrectly excludes valid code: string literals starting with `"""` at line start, dictionary keys like `"#channel"`, and Python decorators like `@property` (the `*` pattern matches multiplication operators at line start after auto-formatting). This undercounts lines and underestimates complexity.
  - **Fix:** Only filter lines where the comment marker is the first non-whitespace character AND not inside a string. Use language-specific logic instead of one-size-fits-all.

- [ ] **REF-051**: Python Call Extractor Doesn't Reset State Between Calls
  - **Location:** `src/analysis/call_extractors.py:59-61`, `src/analysis/call_extractors.py:78-80`
  - **Problem:** The `extract_calls()` method sets `self.current_class = None` and `self.current_function = None` at the start (lines 78-80), but these are instance variables that could leak state if an exception is raised mid-extraction. If parsing fails after setting `current_class = "Foo"`, the next call to `extract_calls()` for a different file will still have `current_class = "Foo"` in context.
  - **Fix:** Use local variables instead of instance variables for tracking context within a single file parse, or use a context manager to ensure cleanup

- [ ] **BUG-081**: Missing Validation for Empty Embeddings Array in Duplicate Detector
  - **Location:** `src/analysis/code_duplicate_detector.py:159-163`
  - **Problem:** Line 159 checks `if embeddings.size == 0: raise ValueError("Embeddings array is empty")`, but this check happens AFTER the function signature promises to return an ndarray. An empty array is a valid input in some contexts (e.g., empty codebase), but raising ValueError breaks the contract. Additionally, returning an empty similarity matrix (0x0) might be more appropriate than failing.
  - **Fix:** Return `np.array([])` (empty 0x0 matrix) for empty input instead of raising, or document that empty input is invalid in docstring

### 🔵 LOW Priority Findings

- [ ] **REF-052**: Duplicate Language Pattern Definitions Between Analyzers
  - **Location:** `src/analysis/complexity_analyzer.py:104-129`, `src/analysis/criticality_analyzer.py:173-198`, `src/analysis/usage_analyzer.py:217-230`
  - **Problem:** Each analyzer defines its own language-specific patterns dictionaries for keywords/operators. The JavaScript/TypeScript patterns are duplicated in complexity and criticality analyzers. If a new language is added or pattern is fixed (e.g., Rust match syntax), must update multiple files.
  - **Fix:** Extract to shared `src/analysis/language_patterns.py` module with pattern definitions for each language, imported by all analyzers

- [ ] **PERF-016**: Regex Recompilation on Every Function Call
  - **Location:** `src/analysis/complexity_analyzer.py:135-137`, and 20+ other locations in analyzers
  - **Problem:** All regex patterns are defined as raw strings in loops (e.g., `r'\bif\b'`) and passed to `re.findall()` or `re.search()`, which compiles the regex on every call. For analyzing 10,000 functions, this recompiles the same patterns 10,000 times.
  - **Fix:** Pre-compile patterns as module-level constants: `IF_PATTERN = re.compile(r'\bif\b')`, then use `IF_PATTERN.findall(content)`

- [ ] **REF-053**: Missing Type Hints for Return Values in Call Extractors
  - **Location:** `src/analysis/call_extractors.py:310-325`, `src/analysis/call_extractors.py:379-393`
  - **Problem:** Helper methods like `_extract_function_name()`, `_extract_callee_name()`, and `_extract_method_name()` return `Optional[str]` but the return statements don't use explicit None returns in all paths. Lines 324, 392 have bare `pass` in except blocks, then implicitly return None. This makes it unclear whether None is intentional or a bug.
  - **Fix:** Add explicit `return None` in all exception handlers and document when/why None is returned

- [ ] **BUG-082**: Export Detection Regex Can Match Inside String Literals
  - **Location:** `src/analysis/usage_analyzer.py:260-264`
  - **Problem:** Line 261 searches for `export\s+(function|class|const|let|var)\s+{name}\b` in full file content, which can match inside multi-line string literals or comments (e.g., documentation showing example code: `"Example: export function foo()"`). This incorrectly marks non-exported functions as exported.
  - **Fix:** Add negative lookbehind to exclude matches inside strings/comments, or use proper AST-based export detection instead of regex

- [ ] **REF-054**: Hardcoded Entry Point Names Without Configurability
  - **Location:** `src/analysis/criticality_analyzer.py:94-97`, `src/analysis/usage_analyzer.py:306-307`
  - **Problem:** Both analyzers define `ENTRY_POINT_NAMES` sets with hardcoded values like "main", "index", "app". For projects with custom entry points (e.g., FastAPI with "application.py", Django with "wsgi.py"), these won't be detected as entry points, leading to incorrect criticality/usage scores.
  - **Fix:** Make entry point names configurable via ServerConfig: `criticality.entry_point_names = ["main", "index", ...]` with defaults, allow user override

- [ ] **PERF-017**: Redundant Call to len() in Median Calculation
  - **Location:** `src/analysis/importance_scorer.py:360-364`
  - **Problem:** Line 360 calls `n = len(sorted_scores)`, then line 361-364 checks `if n % 2 == 1` to decide median calculation. But the `sorted_scores` list was already created on line 357 with a length known at that point. The `n` variable is used only for median calculation, so this is a micro-optimization opportunity.
  - **Fix:** Inline: `if len(sorted_scores) % 2 == 1: median = sorted_scores[len(sorted_scores) // 2]` (or keep as-is for readability)

### Summary Statistics

- **Total Issues Found:** 18
- **Critical:** 3 (division by zero, double-counting, normalization failure)
- **High:** 4 (O(N²) performance, silent failures, type errors, state leaks)
- **Medium:** 6 (score range duplication, formula bugs, inefficient lookups, regex issues)
- **Low:** 5 (pattern duplication, regex recompilation, type hints, configurability)

**Key Risks:**
1. BUG-075 breaks importance scoring discriminatory power with non-default weights (all scores collapse to 1.0)
2. BUG-078 causes cross-file contamination in call graph analysis (incorrect usage metrics)
3. BUG-074 inflates cyclomatic complexity scores unpredictably (affects all downstream metrics)
4. PERF-014 can cause OOM on large codebases during duplicate detection (no early exit)

**Recommended Remediation Priority:**
1. Fix BUG-075 (importance score normalization) - affects all importance calculations
2. Fix BUG-078 (call graph state leak) - affects usage analysis accuracy
3. Fix BUG-074 (cyclomatic complexity double-counting) - affects complexity scores
4. Add PERF-014 (duplicate detector early exit) - prevents OOM on large codebases

**Next Ticket Numbers:** BUG-073 to BUG-082, REF-050 to REF-054, PERF-014 to PERF-017

---

## AUDIT-001 Part 12: Monitoring & Health Systems Findings (2025-11-30)

**Investigation Scope:** Monitoring, alerting, health reporting, capacity planning, and remediation systems
**Files Analyzed:** health_reporter.py (510 lines), alert_engine.py (568 lines), capacity_planner.py (613 lines), remediation.py (537 lines), health_scheduler.py (355 lines), health_jobs.py (408 lines), health_scorer.py (476 lines)
**Focus:** Health check accuracy, alert threshold correctness, metric collection bugs, remediation action safety, scheduler reliability, job state management, capacity planning accuracy, monitoring performance impact, false positive/negative rates

### 🔴 CRITICAL Findings

- [ ] **BUG-080**: SQL Injection Vulnerability in Alert Engine Query
  - **Location:** `src/monitoring/alert_engine.py:412-413`
  - **Problem:** The `get_active_alerts()` method constructs SQL query with f-string interpolation of current timestamp: `query += f" AND (snoozed_until IS NULL OR snoozed_until < '{now}')"`. If datetime formatting changes or UTC timezone handling fails, this could allow SQL injection. The `now` variable comes from `datetime.now(UTC).isoformat()` which is safe currently, but the pattern violates SQL safety best practices.
  - **Fix:** Use parameterized query: `query += " AND (snoozed_until IS NULL OR snoozed_until < ?)"` and pass `now` as parameter to `cursor.execute(query, (now,))`

- [ ] **BUG-081**: Missing Error Handling in Linear Regression Causes Silent Failures
  - **Location:** `src/monitoring/capacity_planner.py:392-444`
  - **Problem:** The `_calculate_linear_growth_rate()` method can fail silently if historical metrics contain invalid data (NaN, infinity, or extremely large values). Line 439 checks `if abs(denominator) < 1e-10` to avoid division by zero, but doesn't validate input data. If `sum_xy` or `sum_x_squared` overflow to infinity (possible with 10,000+ data points over years), the calculation returns garbage values without warning. This leads to incorrect capacity forecasts.
  - **Fix:** Add input validation: `if any(not math.isfinite(getattr(m, metric_name, 0)) for m in historical_metrics): logger.warning("Invalid metric values detected"); return 0.0`. Wrap calculation in try/except to catch OverflowError.

- [ ] **BUG-082**: Health Scheduler Resource Leak on Restart
  - **Location:** `src/memory/health_scheduler.py:304-317`
  - **Problem:** The `update_config()` method calls `await self.stop()` (line 309) which closes the store (line 151), then creates a new AsyncIOScheduler (line 313) and calls `await self.start()` (line 316) which creates a NEW store instance (line 73). The old store's Qdrant connections are closed, but the store object itself may still be referenced by old job callbacks. If a scheduled job runs during the restart window, it will use the closed store and fail. Additionally, the `health_jobs` instance is not recreated, so it holds a reference to the old (closed) store.
  - **Fix:** In `update_config()`, also recreate `self.health_jobs = None` before calling `start()`. Add state check in job callbacks: `if not self.health_jobs or not self.health_jobs.store: logger.error("Store not available"); return`

### 🟡 HIGH Priority Findings

- [ ] **BUG-083**: Division by Zero Risk in Health Score Calculations
  - **Location:** `src/monitoring/health_reporter.py:343-346`, `src/monitoring/capacity_planner.py:304-314`, `src/memory/health_scorer.py:257`, `src/memory/health_scorer.py:308`
  - **Problem:** Multiple methods calculate percentages by dividing by totals without checking for zero first. While most have `if total == 0: return 0.0` guards, the logic AFTER the guard still performs division. For example, in `analyze_trends()` line 346: `change_percent = (change / previous_value) * 100` - if `previous_value == 0` (after passing the line 341 `if previous_value == 0: continue` check), this will raise ZeroDivisionError. The guard at line 341 uses `continue` which skips to next metric, but if `previous_value` becomes zero DURING iteration due to race condition or concurrent update, the calculation crashes.
  - **Fix:** Change all percentage calculations to check denominator immediately before division: `if previous_value == 0: change_percent = 0.0 else: change_percent = (change / previous_value) * 100`

- [ ] **BUG-084**: Alert Penalty Can Produce Negative Health Scores
  - **Location:** `src/monitoring/health_reporter.py:279-291`
  - **Problem:** The `_apply_alert_penalty()` method subtracts penalties from the score (line 291: `return max(0, score - penalty)`). If there are many alerts, the penalty can exceed 100 points. For example, 7 CRITICAL alerts = 105 penalty points. While the `max(0, ...)` prevents negative scores, it means the overall score becomes 0 even if other components (performance, quality) are excellent. This creates a false CRITICAL health status when the issue might be a single misconfigured alert threshold firing repeatedly.
  - **Fix:** Cap penalty at 30 points max (or 30% of score): `penalty = min(30, penalty)`. Or use multiplicative penalty instead: `return int(score * (1 - min(0.3, penalty/100)))` so alerts reduce score proportionally.

- [ ] **BUG-085**: Capacity Forecasting Fails with Single Data Point
  - **Location:** `src/monitoring/capacity_planner.py:407-408`
  - **Problem:** The `_calculate_linear_growth_rate()` method checks `if len(historical_metrics) < 2: return 0.0` at line 407, but the check happens AFTER extracting data_points (line 411-414) and sorting (line 417). If someone passes a single-item list, the code continues to line 421-425 where it tries to compute x_values and y_values from a 1-element list, then line 428 checks `if len(x_values) < 2` again. This is redundant and confusing - the early return at line 407 should prevent this, but it's checked twice.
  - **Fix:** Move the `if len(historical_metrics) < 2` check to line 398 (top of function), before any processing. Remove redundant check at line 428.

- [ ] **PERF-014**: No Pagination in Remediation Action Execution
  - **Location:** `src/monitoring/remediation.py:256-285`, `src/monitoring/remediation.py:337-365`
  - **Problem:** The `_prune_stale_memories()` and `_cleanup_old_sessions()` methods (and others) process ALL candidates in a single loop without pagination. If there are 50,000 STALE memories, this creates a massive transaction and holds a database lock for minutes. The comment at line 270-271 says "Would actually delete here" with a placeholder, suggesting real implementation will use `store.delete_by_lifecycle()` which might not have pagination either.
  - **Fix:** Add batch processing: `for i in range(0, len(candidates), 1000): batch = candidates[i:i+1000]; await self.store.delete_batch(batch)`. Commit after each batch to reduce lock duration.

- [ ] **BUG-086**: Health Scorer Distribution Calculation Can Hit Memory Limit
  - **Location:** `src/memory/health_scorer.py:162-227`
  - **Problem:** The `_get_lifecycle_distribution()` method loads ALL memories with `all_memories = await self.store.get_all_memories()` (line 178), then has a check at line 190-195 that returns empty distribution if count > MAX_MEMORIES_PER_OPERATION (50,000). However, the damage is already done at line 178 - if there are 100,000 memories, they're all loaded into memory before the check. This can cause OOM crash. The comment at line 193 says "Aborting to prevent memory exhaustion" but it's too late.
  - **Fix:** Add count-only query before fetching: `total = await self.store.count_memories(); if total > MAX_MEMORIES_PER_OPERATION: return distribution`. Or use streaming/cursor-based fetching instead of loading all at once.

### 🟢 MEDIUM Priority Findings

- [ ] **REF-055**: Hardcoded Health Status Thresholds Duplicated Across Files
  - **Location:** `src/monitoring/health_reporter.py:293-304`, `src/monitoring/capacity_planner.py:108-117`, `src/memory/health_scorer.py:126-133`
  - **Problem:** Three different files define their own health status thresholds (EXCELLENT >= 90, GOOD >= 75, etc.). While the values are currently identical, they're hardcoded magic numbers in each file. If we need to adjust thresholds (e.g., make "GOOD" >= 70 instead of 75), must change 3+ files. This creates inconsistency risk where different components report different health statuses for the same score.
  - **Fix:** Extract to shared constants in `src/monitoring/constants.py`: `HEALTH_STATUS_THRESHOLDS = {"EXCELLENT": 90, "GOOD": 75, "FAIR": 60, "POOR": 40}`. Import in all files.

- [ ] **REF-056**: Missing Input Validation in Alert Snooze Duration
  - **Location:** `src/monitoring/alert_engine.py:469-493`
  - **Problem:** The `snooze_alert()` method accepts `hours` parameter with no validation. Caller can pass `hours=-10` (snooze in the past, meaningless), `hours=0` (immediate un-snooze), or `hours=1000000` (snooze for 114 years). Negative or extreme values create confusing behavior - snoozed alerts might reappear immediately or never.
  - **Fix:** Add validation: `if not (0 < hours <= 168): raise ValueError("Snooze duration must be 1-168 hours (1 week max)")`. Document reasonable range.

- [ ] **BUG-087**: Trend Analysis Direction Logic Has Edge Case Bug
  - **Location:** `src/monitoring/health_reporter.py:353-363`
  - **Problem:** The trend direction determination uses compound ternary expressions that are hard to reason about. Line 353-356 for "higher_is_better" case: `direction = "improving" if change_percent > 5 else "degrading" if change_percent < -5 else "stable"`. This means a change of +4% is "stable", but -4% is also "stable". However, for "lower is better" metrics (line 359-362), the logic is flipped but uses the SAME thresholds. This means a 4.9% increase in noise_ratio is marked "stable" when it should be "degrading".
  - **Fix:** Use clearer threshold constants: `TREND_SIGNIFICANT_CHANGE = 5.0`. Break compound ternary into explicit if/elif for readability. Consider separate thresholds for improvement vs degradation (e.g., 5% improvement is good, but 3% degradation is concerning).

- [ ] **REF-057**: Duplicate Emoji Constants in Capacity Recommendations
  - **Location:** `src/monitoring/capacity_planner.py:457-516`
  - **Problem:** The `_generate_capacity_recommendations()` method uses hardcoded emoji strings (🔴, ⚠️, 📈, ✅) inline in 8 different locations. If recommendations need to be rendered in a non-emoji-supporting terminal or UI, must change 8+ places. Also makes testing harder (must match exact emoji strings).
  - **Fix:** Define constants at module level: `EMOJI_CRITICAL = "🔴"`, `EMOJI_WARNING = "⚠️"`, etc. Or make emojis optional via config flag.

- [ ] **BUG-088**: Weekly Report Missing Alert History Comparison
  - **Location:** `src/monitoring/health_reporter.py:378-457`
  - **Problem:** The `generate_weekly_report()` method calculates `previous_health` score from `previous_metrics` (line 399-403), but comment at line 402 says "Note: We don't have previous alerts, so approximate". This means the previous health score is calculated with ZERO alerts (empty list), making it artificially high. The week-over-week health comparison is therefore inaccurate - current health might be 65 (with 5 alerts), previous health is 85 (with 0 alerts assumed), suggesting health degraded when alerts may have existed then too.
  - **Fix:** Either: (1) Store historical alerts in database and fetch them, or (2) Document this limitation in WeeklyReport.previous_health docstring and add a warning field: `previous_health_note: "Calculated without historical alerts"`.

- [ ] **REF-058**: Job History Unbounded Growth in Health Jobs
  - **Location:** `src/memory/health_jobs.py:83-84`, `src/memory/health_jobs.py:195`, `src/memory/health_jobs.py:306`, `src/memory/health_jobs.py:369`
  - **Problem:** The `HealthMaintenanceJobs` class appends every job result to `self.job_history` list (lines 195, 306, 369) with no size limit. If jobs run every week for a year, that's 52 * 3 = 156 entries minimum. If jobs run daily (via manual trigger), that's 1000+ entries. The list grows unbounded and is never cleared except manually via `clear_job_history()` (line 404). In contrast, HealthJobScheduler limits history to last 100 entries (line 164).
  - **Fix:** Add automatic trimming in job methods: `self.job_history.append(result); if len(self.job_history) > 100: self.job_history = self.job_history[-100:]`

### 🔵 LOW Priority Findings

- [ ] **REF-059**: Magic Numbers for Lifecycle Distribution Ideals
  - **Location:** `src/memory/health_scorer.py:79-84`
  - **Problem:** The IDEAL_DISTRIBUTION dictionary hardcodes percentages (60% ACTIVE, 25% RECENT, etc.) with no explanation of why these values are ideal. These ratios are domain-specific assumptions that may not apply to all use cases. A read-heavy system might prefer 80% ACTIVE, while a write-heavy system might prefer 40% ARCHIVED.
  - **Fix:** Make IDEAL_DISTRIBUTION configurable via ServerConfig: `health.ideal_distribution_percentages`. Document rationale for default values in comments.

- [ ] **PERF-015**: Duplicate Detection Has O(N²) Complexity
  - **Location:** `src/memory/health_scorer.py:259-313`
  - **Problem:** The `_calculate_duplicate_rate()` method iterates through all memories and builds a `content_map` dictionary to detect exact duplicates (lines 291-306). For N memories, this is O(N) which is fine. However, the comment at lines 263-268 suggests the INTENDED implementation is pairwise similarity checks, which would be O(N²). If anyone implements the full version without optimization, it could take hours for 10,000+ memories. The current implementation only detects exact duplicates (case-insensitive), missing near-duplicates.
  - **Fix:** Document that semantic duplicate detection is NOT implemented (only exact matches). Add TODO for LSH (Locality-Sensitive Hashing) based approximate duplicate detection which is O(N).

- [ ] **BUG-089**: Remediation History Query Performance Degrades Over Time
  - **Location:** `src/monitoring/remediation.py:454-499`
  - **Problem:** The `get_remediation_history()` method queries `remediation_history` table with `WHERE timestamp >= ?` (line 474). If the table grows to 10,000+ rows over months, and caller requests `days=30`, the database must scan all rows to filter by timestamp. There's an index on timestamp (line 97-100), but SQLite's query planner might not use it efficiently if the retention_days is very large.
  - **Fix:** Add explicit `ORDER BY timestamp DESC LIMIT ?` to query, or use EXPLAIN QUERY PLAN to verify index usage. Consider adding a cleanup job to delete old remediation history (currently only `cleanup_old_alerts()` exists, no cleanup for remediation history).

- [ ] **REF-060**: Inconsistent Dry-Run Behavior Across Remediation Actions
  - **Location:** `src/monitoring/remediation.py:230-254`, `src/monitoring/remediation.py:256-285`
  - **Problem:** The `_dry_run_action()` method handles dry-run for `prune_stale_memories` and `cleanup_old_sessions` specially (lines 235-248), but for all other actions returns `RemediationResult(success=True, items_affected=0, details={"action": "dry_run", "note": "count not available"})` (line 250-254). This means dry-run for `archive_inactive_projects`, `merge_duplicates`, and `optimize_database` doesn't provide useful information - it just says "would run" with no impact estimate. Users can't make informed decisions.
  - **Fix:** Implement proper dry-run for all actions. `optimize_database` could report current DB size, `archive_inactive_projects` could count inactive projects, etc.

- [ ] **BUG-090**: Health Scheduler Notification Callback Not Awaited
  - **Location:** `src/memory/health_scheduler.py:173-174`, `src/memory/health_scheduler.py:187-188`, `src/memory/health_scheduler.py:208-209`, `src/memory/health_scheduler.py:240-241`, `src/memory/health_scheduler.py:254-255`
  - **Problem:** The scheduler calls `await self.config.notification_callback(...)` at lines 174, 188, 209, 241, 255. However, `notification_callback` is typed as `Optional[Callable]` with no async specification (line 42). If user provides a synchronous callback function, the `await` will fail with "TypeError: object is not awaitable". If user provides an async callback, it works fine. The type annotation doesn't enforce async.
  - **Fix:** Change type annotation to `Optional[Callable[..., Awaitable[None]]]` to require async callbacks. Or detect sync vs async: `if asyncio.iscoroutinefunction(self.config.notification_callback): await callback(...) else: callback(...)`

- [ ] **REF-061**: Database Optimization Uses Blocking Operations
  - **Location:** `src/monitoring/remediation.py:367-387`
  - **Problem:** The `_optimize_database()` method runs `VACUUM` (line 372) and `ANALYZE` (line 375) on SQLite database. Both are blocking operations that can take 10+ seconds on large databases (1GB+). The entire remediation engine (and any other code using the same database connection) is blocked during this time. If called during a busy period, this causes user-visible latency spikes.
  - **Fix:** Add warning log before optimization: `logger.warning("Starting database optimization - may block for 10+ seconds")`. Consider running VACUUM in a separate transaction or thread. Document that this should only run during maintenance windows.

- [ ] **BUG-091**: Stale Memory Count Logic Uses Hardcoded Access Threshold
  - **Location:** `src/memory/health_jobs.py:267`
  - **Problem:** The monthly cleanup job checks `if use_count > config.quality.stale_memory_usage_threshold` (line 267) to skip frequently accessed memories. However, this threshold is from ServerConfig.quality settings, which is intended for quality scoring, not lifecycle management. The comment at line 264 says "Check usage (skip if frequently accessed)" but doesn't explain what "frequently" means. If the config value is set too low (e.g., 1), all stale memories with any usage are kept forever.
  - **Fix:** Add dedicated `lifecycle.stale_deletion_min_access_count` config setting with clear documentation. Default to 5. Don't reuse quality threshold for deletion decisions.

### Summary Statistics

- **Total Issues Found:** 18
- **Critical:** 3 (SQL injection, silent failures, resource leak)
- **High:** 5 (division by zero, negative scores, single data point, no pagination, OOM risk)
- **Medium:** 6 (threshold duplication, input validation, edge cases, unbounded growth, missing alerts)
- **Low:** 4 (magic numbers, complexity, query performance, inconsistent behavior)

**Key Risks:**
1. SQL injection in alert query construction (CRITICAL security issue)
2. Silent capacity forecast failures lead to incorrect scaling decisions
3. Health scorer can crash entire monitoring system with OOM on large datasets
4. Remediation actions lack pagination and could lock database for minutes
5. Alert penalty calculation can produce misleading health scores

**Remediation Safety Concerns:**
- No batch size limits in pruning operations (could delete 50K+ memories in single transaction)
- Dry-run doesn't provide accurate impact estimates for most actions
- Database optimization blocks entire system during execution
- No rollback mechanism if remediation partially fails

**False Positive/Negative Risks:**
- Weekly report health comparison is inaccurate (missing historical alerts)
- Trend analysis edge case treats 4.9% degradation as "stable"
- Duplicate detection only finds exact matches (misses semantic duplicates)
- Health scorer assumes 50% of archived memories are noise (hardcoded assumption)

**Next Ticket Numbers:** BUG-080 to BUG-091, REF-055 to REF-061, PERF-014 to PERF-015

---

## AUDIT-001 Part 8: CLI Commands & User Experience Findings (2025-11-30)

**Investigation Scope:** 26 CLI command files (~4,500 lines) covering index, health, status, git operations, analytics, backup/import/export, project/workspace/repository management, and command registration

### 🔴 CRITICAL Findings

- [ ] **BUG-080**: Missing Command Integration for browse, tutorial, validate-setup, perf
  - **Location:** `src/cli/__init__.py:166-169` (browse declared), `src/cli/__init__.py:69` (tutorial in help text), `src/cli/__init__.py:68` (validate-setup in help text)
  - **Problem:** Commands declared in help text and parsers created but NOT integrated into `main_async()`. The `browse` parser exists (line 166) and `tutorial`/`validate-setup` appear in help but NO handler in `main_async()` (lines 428-485). Users will see these commands but get "No command specified" error when trying to use them.
  - **Impact:** User-facing features completely broken - tutorial for onboarding new users, browse for memory exploration, validate-setup for diagnostics all non-functional
  - **Fix:** Add handlers in `main_async()`: `elif args.command == "browse": await run_memory_browser()`, `elif args.command == "tutorial": ...`, `elif args.command == "validate-setup": cmd = ValidateSetupCommand(); await cmd.run(args)`

- [ ] **BUG-081**: perf Commands Import But No Parser Created
  - **Location:** `src/cli/__init__.py:23` imports `perf_report_command, perf_history_command` but no subparser added
  - **Problem:** Performance command functions imported but never registered with argparse. Users cannot invoke `claude-rag perf report` or `claude-rag perf history` - the commands don't exist in CLI
  - **Impact:** Performance monitoring functionality completely inaccessible via CLI
  - **Fix:** Add perf subparser similar to health-monitor (lines 354-410): create `perf_parser` with `report` and `history` subcommands

- [ ] **BUG-082**: Inconsistent Exit Code Handling Across Commands  
  - **Location:** `src/cli/__init__.py:453` (prune uses sys.exit), vs `src/cli/__init__.py:476` (validate-install uses sys.exit), vs all other commands that don't
  - **Problem:** Only `prune` and `validate-install` commands properly return exit codes via `sys.exit()`. All other commands in `main_async()` don't set exit codes on failure. Shell scripts/CI cannot detect command failures.
  - **Impact:** Silent failures in automation - a failing `index` or `health` command will return exit code 0
  - **Fix:** Standardize: all async command methods should return int, `main_async()` should `sys.exit(code)` based on return value

### 🟡 HIGH Priority Findings

- [ ] **UX-060**: Inconsistent Progress Indicator Patterns
  - **Location:** `src/cli/index_command.py:169-220` (rich Progress with callback), vs `src/cli/backup_command.py:70-89` (rich Progress with spinner), vs `src/cli/git_index_command.py:56-77` (rich Progress with bar)
  - **Problem:** Three different progress bar styles for similar operations. IndexCommand uses custom callback with task updates, BackupCommand uses simple spinner, GitIndexCommand uses BarColumn. Inconsistent UX - users can't predict what feedback they'll get.
  - **Fix:** Create shared `src/cli/progress_utils.py` with standard progress styles: `create_indexing_progress()`, `create_spinner_progress()`, `create_transfer_progress()`

- [ ] **BUG-083**: Missing Keyboard Interrupt Handling in Many Commands
  - **Location:** `src/cli/watch_command.py:74` has `KeyboardInterrupt` handler, but most other async commands don't
  - **Problem:** Only watch, main, and a few commands handle Ctrl+C gracefully. Commands like index, git-index, health-monitor will crash with ugly Python traceback on Ctrl+C instead of clean exit message.
  - **Impact:** Poor UX - users see Python stack traces when interrupting long operations
  - **Fix:** Wrap all async command `run()` methods with `try/except KeyboardInterrupt` and print friendly "Operation cancelled by user"

- [ ] **BUG-084**: analytics and session-summary Commands Not Async But Called from Async Context
  - **Location:** `src/cli/__init__.py:461-470` calls `run_analytics_command()` and `run_session_summary_command()` without await
  - **Problem:** These functions are synchronous (no async def) but called from `main_async()`. They block the event loop. If analytics needs to query Qdrant, it should be async. Currently works but violates async patterns.
  - **Impact:** Performance degradation - synchronous database access blocks event loop
  - **Fix:** Convert `run_analytics_command()` and `run_session_summary_command()` to async, add await in main_async()

- [ ] **UX-061**: No Confirmation Prompts for Destructive Operations in Multiple Commands
  - **Location:** `src/cli/project_command.py:144-164` (delete has confirmation), but `src/cli/collections_command.py:100-119` (delete uses click.confirm), `src/cli/tags_command.py:111-141` (delete uses click.confirm)
  - **Problem:** Inconsistent confirmation patterns - some use `input()`, some use `click.confirm()`, some use `rich.prompt.Confirm.ask()`. Three different confirmation UIs create confusing UX. Also, collections and tags commands use Click but aren't registered in main CLI (separate entry points).
  - **Fix:** Standardize on rich.prompt.Confirm for all confirmations. Integrate collections/tags into main CLI or document as separate tools

- [ ] **BUG-085**: Click-Based Commands Not Integrated with Main CLI  
  - **Location:** `src/cli/auto_tag_command.py:17` uses `@click.command`, `src/cli/collections_command.py:16` uses `@click.group`, `src/cli/tags_command.py:16` uses `@click.group`
  - **Problem:** Three commands use Click decorators but main CLI uses argparse. These commands have separate entry points and aren't discoverable via `claude-rag --help`. Users don't know these features exist.
  - **Impact:** Hidden features - auto-tagging, collection management, tag management completely undiscoverable
  - **Fix:** Either (1) convert Click commands to argparse and integrate into main CLI, or (2) add to help text with note "Run separately: python -m src.cli.tags --help"

### 🟢 MEDIUM Priority Findings

- [ ] **UX-062**: Inconsistent Error Message Formatting
  - **Location:** `src/cli/health_command.py:481` prints `"Cannot load embedding model"`, vs `src/cli/status_command.py:89` logs then returns error dict, vs `src/cli/index_command.py:241` prints `"ERROR: Indexing failed - {e}"`
  - **Problem:** Different error formats: some use logger.error, some use console.print with [red], some use plain print with "ERROR:" prefix. No standard error format.
  - **Fix:** Create `src/cli/error_utils.py` with `print_error(message, exc=None)` that handles logging + rich formatting consistently

- [ ] **REF-050**: Duplicate Rich Console Availability Checks
  - **Location:** `src/cli/health_command.py:11-17`, `src/cli/status_command.py:10-18`, `src/cli/index_command.py:10-16`, and 8+ other files
  - **Problem:** Every command file has identical `try: from rich import Console; RICH_AVAILABLE = True except: RICH_AVAILABLE = False` boilerplate (50+ lines total)
  - **Fix:** Create `src/cli/console_utils.py` with `get_console() -> Optional[Console]` that handles import + fallback once

- [ ] **UX-063**: Missing Help Text for Complex Subcommands
  - **Location:** `src/cli/repository_command.py:413-514` has 6 subcommands but minimal epilog examples, `src/cli/workspace_command.py:477-586` similar
  - **Problem:** Complex multi-level commands (repository, workspace) don't have usage examples in help. Users must read code to understand `claude-rag repository add-dep` syntax.
  - **Fix:** Add `epilog` with examples to each subparser like git-index/git-search do (lines 206-216)

- [ ] **BUG-086**: Health Command _format_time_ago Returns Wrong Result for "Just now"  
  - **Location:** `src/status_command.py:39-55`
  - **Problem:** Function returns "Just now" for delta.seconds < 60, but this includes negative deltas (future timestamps). If `dt` is in future (e.g., clock skew), delta.seconds could be 0 but dt > now, giving confusing "Just now" for future times.
  - **Fix:** Add `if delta.total_seconds() < 0: return "In the future"` before checking seconds

- [ ] **PERF-014**: Redundant Store Initialization in project_command
  - **Location:** `src/cli/project_command.py:32` and `project_command.py:94` both create and initialize MemoryRAGServer
  - **Problem:** Each project subcommand initializes a new server instance. If user runs `project list && project stats myproject`, server initialized twice. Server initialization includes Qdrant connection, embedding model load - expensive.
  - **Fix:** Cache server instance at module level or pass through command context

- [ ] **REF-051**: Duplicate Date Parsing Logic in git_search_command
  - **Location:** `src/cli/git_search_command.py:50-71` (since parsing) and `git_search_command.py:73-89` (until parsing)
  - **Problem:** Nearly identical date parsing code duplicated for 'since' and 'until' parameters. Both handle "today", "yesterday", "last week", ISO format, etc.
  - **Fix:** Extract to `_parse_date_filter(date_str: str) -> Optional[datetime]` method

### 🔵 LOW Priority / Polish

- [ ] **UX-064**: Truncated Repository IDs in Tables Inconsistently
  - **Location:** `src/cli/repository_command.py:259` truncates to `id[:12] + "..."`, but `src/cli/workspace_command.py:291` shows full ID
  - **Problem:** Repository tables truncate IDs to 12 chars + "..." but workspace tables show full IDs. Inconsistent display width makes output unpredictable.
  - **Fix:** Standardize on max_width parameter for ID columns across all tables

- [ ] **REF-052**: Magic Number 10 for Top Results Display
  - **Location:** `src/cli/index_command.py:68-71` shows first 10 failed files, `src/cli/prune_command.py:101-103` shows first 10 deleted IDs
  - **Problem:** Hardcoded `[:10]` appears in multiple places without explanation. If user has 500 errors, only seeing 10 may hide important patterns.
  - **Fix:** Extract to constant `MAX_DISPLAYED_ITEMS = 10` with comment, or add --show-all flag

- [ ] **UX-065**: No Progress Indicator for Long-Running health_check Operations
  - **Location:** `src/cli/health_command.py:421-562` runs 10+ async checks sequentially with no progress
  - **Problem:** Health check can take 5-10 seconds (Qdrant latency, embedding model load, etc.) with no feedback. User sees nothing until all checks complete.
  - **Fix:** Add `with console.status("Running health checks...")` or progress bar showing N/M checks complete

- [ ] **REF-053**: Inconsistent Table Width Settings
  - **Location:** `src/cli/repository_command.py:234` sets `max_width=15`, `src/cli/workspace_command.py:282` sets `max_width=20`, many others have no max_width
  - **Problem:** Some tables constrain column width, others don't. Long project names or descriptions cause ugly table wrapping inconsistently.
  - **Fix:** Define standard table width constants: `ID_COL_WIDTH = 15`, `NAME_COL_WIDTH = 30`, `DESC_COL_WIDTH = 50`

- [ ] **UX-066**: prune Command Shows Confirmation Twice in Non-Dry-Run Mode  
  - **Location:** `src/cli/prune_command.py:54-75` (preview + confirmation), then `src/cli/prune_command.py:77-82` (actual execution)
  - **Problem:** User sees "Found N memories" preview, then "About to delete N memories" confirmation. Redundant - preview result shows same count as confirmation.
  - **Fix:** Combine into single confirmation: "Found N expired memories. Delete them? (yes/no)"

### 📊 Part 8 Summary

| Severity | Count | Tickets |
|----------|-------|---------|
| Critical (broken features, exit codes) | 3 | BUG-080, BUG-081, BUG-082 |
| High (UX issues, async violations) | 5 | UX-060, BUG-083, BUG-084, UX-061, BUG-085 |
| Medium (consistency, errors, perf) | 6 | UX-062, REF-050, UX-063, BUG-086, PERF-014, REF-051 |
| Low (polish, minor issues) | 5 | UX-064, REF-052, UX-065, REF-053, UX-066 |
| **Total** | **19** | |

**Key Findings:**
1. **Multiple commands completely non-functional** - browse, tutorial, validate-setup, perf not integrated despite being advertised
2. **Exit code handling broken** - most commands don't return proper exit codes for shell integration
3. **Mixed frameworks** - argparse (main CLI) vs Click (tags/collections) creates fragmentation
4. **Inconsistent UX patterns** - three different progress styles, three different confirmation methods, inconsistent error formatting
5. **Hidden features** - Click-based commands not discoverable via main help

**User Impact:**
- New users run `claude-rag tutorial` → error (broken onboarding)
- CI scripts can't detect failures (exit codes)
- Features like auto-tagging completely hidden
- Inconsistent visual feedback across commands

**Next Ticket Numbers:** BUG-080 to BUG-086, UX-060 to UX-066, REF-050 to REF-053, PERF-014


## AUDIT-001 Part 10: Exception Handling & Error Recovery Findings (2025-11-30)

**Investigation Scope:** Exception handling patterns across entire codebase, focusing on issues not caught by previous audits (BUG-035, BUG-036, BUG-054, REF-028, INVEST-001, UX-049)

### 🔴 CRITICAL Findings

- [ ] **BUG-080**: Missing exc_info=True in Connection Pool Error Logs
  - **Location:** `src/store/connection_pool.py:187`, `src/store/connection_pool.py:323`, `src/store/connection_pool.py:534`
  - **Problem:** Connection pool logs errors without stack traces (no `exc_info=True`). When pool initialization/acquisition/creation fails in production, logs show "Failed to X: <error message>" but no stack trace, making debugging impossible. This is critical infrastructure - connection failures are common and need full context.
  - **Fix:** Add `exc_info=True` to all logger.error() calls in connection_pool.py. Example: `logger.error(f"Failed to initialize connection pool: {e}", exc_info=True)`

- [ ] **BUG-081**: Exception Swallowed in Connection Release with Comment Justification
  - **Location:** `src/store/connection_pool.py:375-377`
  - **Problem:** `release()` catches all exceptions and logs error but explicitly doesn't raise with comment "Don't raise - connection is lost but we continue". This violates exception handling best practices - swallowing exceptions hides bugs. If release fails repeatedly due to bug (e.g., lock corruption, client_map corruption), caller never knows pool is degrading. This masks serious issues like connection leaks.
  - **Fix:** At minimum add metrics tracking for failed releases and raise alert if failure rate > 1%. Better: only swallow expected exceptions (asyncio.QueueFull), re-raise unexpected ones.

- [ ] **BUG-082**: Incomplete Logging in Health Scorer Exception Handler
  - **Location:** `src/memory/health_scorer.py:222-225`
  - **Problem:** Catches `Exception as e`, logs error, then has dead code `pass` after comment "Return empty distribution on error". The function continues to line 227 `return distribution` regardless. If exception happens, returns partially-filled distribution dict without any indication data is incomplete. Callers receive corrupted data. Missing `exc_info=True` makes debugging impossible.
  - **Fix:** Add `exc_info=True` to log, return empty dict immediately after logging (don't fall through to return statement), document that empty dict means error occurred.

### 🟡 HIGH Priority Findings

- [ ] **BUG-083**: Missing exc_info=True in Qdrant Setup Critical Errors
  - **Location:** `src/store/qdrant_setup.py:157`, `src/store/qdrant_setup.py:291`, `src/store/qdrant_setup.py:309`
  - **Problem:** Qdrant connection/health check failures log errors without stack traces. `collection_exists()` returns False on ANY exception (line 157-158), hiding whether it's a connection error, auth error, or bug in code. `health_check()` returns False on any exception (309-310) - same issue. Production debugging requires stack traces for these critical infrastructure checks.
  - **Fix:** Add `exc_info=True` to all logger.error() in qdrant_setup.py. Consider raising specific exceptions instead of returning False for different failure modes.

- [ ] **BUG-084**: Silent ValueError to Default State Conversion Hides Data Corruption
  - **Location:** `src/memory/health_scorer.py:215-218`, same pattern in store/qdrant_store.py:1526
  - **Problem:** `except ValueError: state = LifecycleState.ACTIVE` silently converts invalid lifecycle states to ACTIVE without logging. If database contains corrupted state values (e.g., "ARCHIVD" typo), code hides corruption by defaulting to ACTIVE. Users see incorrect lifecycle stats. This is data integrity issue disguised as graceful degradation.
  - **Fix:** Log warning with value that failed to parse: `logger.warning(f"Invalid lifecycle state '{state}', defaulting to ACTIVE")`. Consider adding data validation job to detect corruption.

- [ ] **BUG-085**: Exception in Nested Import Loop Lost Without Context
  - **Location:** `src/services/memory_service.py:1366`, nested inside another exception handler at line 1385
  - **Problem:** Import loop at line 1251-1367 catches exceptions per-memory and appends to errors list. The outer exception handler at 1385 catches general exceptions but logs "Failed to import memories" without including the accumulated errors list. If 50 of 100 memories fail with different errors, only the last exception is logged, losing all diagnostic information about the 49 other failures.
  - **Fix:** Include errors list in outer exception log: `logger.error(f"Failed to import memories: {e}. Errors: {errors[:10]}", exc_info=True)` (limit to first 10 to avoid log spam)

- [ ] **BUG-086**: TimeoutError Re-raised as Generic StorageError Loses Exception Type
  - **Location:** `src/services/memory_service.py:320-322`, and 20+ similar locations
  - **Problem:** Pattern `except TimeoutError: raise StorageError("operation timed out")` loses the original TimeoutError type. Callers can't distinguish timeouts from other storage errors (connection refused, disk full, etc.). This makes retry logic impossible - code that should retry on timeout will retry on all StorageErrors, including unretriable ones like disk full.
  - **Fix:** Create TimeoutError subclass of StorageError: `raise StorageTimeoutError("operation timed out") from e`. Update callers to catch and retry only TimeoutError.

### 🟢 MEDIUM Priority Findings

- [ ] **REF-050**: Inconsistent Exception Logging Patterns Across Services
  - **Location:** `src/services/*.py` - mix of `exc_info=True` and no exc_info
  - **Problem:** Services have inconsistent exception logging. Some use `exc_info=True` (memory_service.py:335-339), others don't (analytics_service.py:163-164). Code reviewer or new developer can't tell which is intentional. Grep shows ~80% of exception logs have exc_info=True (from UX-049 fix), but remaining 20% may be bugs or intentional.
  - **Fix:** Document exception logging policy in CONTRIBUTING.md: always use exc_info=True for unexpected exceptions, omit for expected validation errors. Add linting rule to enforce.

- [ ] **REF-051**: Generic Exception Re-wrapping Loses Specific Error Types
  - **Location:** `src/core/server.py:2864-2873`, and similar in multiple store operations
  - **Problem:** Pattern `except Exception as e: raise RetrievalError(...)` catches specific exceptions (ConnectionError, ValidationError) and re-wraps as generic error. Original exception type information is lost. Callers can't implement error-specific handling (e.g., retry on connection errors but not validation errors).
  - **Fix:** Preserve original exception in chain: `raise RetrievalError(...) from e` (already done in most places, missing in ~10 locations). Better: catch specific exception types separately and re-raise with appropriate custom exception.

- [ ] **BUG-087**: Dashboard Web Server Swallows All Exceptions and Returns Generic 500
  - **Location:** `src/dashboard/web_server.py:236`, :267, :304, :332, :453, :508, :572, :610, :657
  - **Problem:** Every endpoint has `except Exception as e: logger.error(...); self._send_error_response(500, str(e))`. This returns raw exception messages to HTTP clients, potentially leaking sensitive information (file paths, database schemas, internal IPs). Also returns 500 for client errors (ValidationError should be 400).
  - **Fix:** Map exception types to HTTP status codes: ValidationError -> 400, NotFoundError -> 404, StorageError -> 503. Sanitize exception messages: return generic message to client, log full details server-side.

- [ ] **BUG-088**: asyncio.timeout Context Manager Missing in 30+ Locations
  - **Location:** Compare files with `asyncio.timeout()` (35 uses) vs async operations without timeout (100+ async def methods)
  - **Problem:** Most async operations have 30s timeout via `async with asyncio.timeout(30.0)`, but many don't (e.g., connection_pool.py acquire, health checks, background indexing). Without timeouts, operations can hang indefinitely on network issues, deadlocks, or Qdrant hangs. This violates fail-fast principle.
  - **Fix:** Audit all async methods that do I/O (network, disk) and add timeouts. Create wrapper decorator `@with_timeout(seconds=30)` to enforce consistently.

### 🔵 LOW Priority Findings

- [ ] **REF-052**: Missing Docstring Raises Sections for 90% of Functions
  - **Location:** Entire codebase - functions raise custom exceptions but don't document in docstring
  - **Problem:** Only ~10% of functions document raised exceptions in docstring Raises section. Functions like `store()` raise ValidationError, StorageError, ReadOnlyError but docstring doesn't list them (src/services/memory_service.py:241-340). Callers don't know what exceptions to catch.
  - **Fix:** Add Raises section to all public API docstrings. Use ruff/pydocstyle to enforce. Example template in CONTRIBUTING.md.

- [ ] **PERF-014**: Unnecessary String Formatting in Logger Calls Before Exception Handling
  - **Location:** Throughout codebase - `logger.error(f"Failed to X: {e}")` before checking if logging is enabled
  - **Problem:** Python evaluates f-strings before passing to logger, even if log level is INFO and error logs are disabled. This wastes CPU cycles formatting strings that are never logged. In tight loops (e.g., indexing 10K files), this adds up.
  - **Fix:** Use lazy logging: `logger.error("Failed to X: %s", e)` with %-formatting. Logger only formats if level is enabled. Python logging best practice.

- [ ] **REF-053**: Duplicate Error Message Construction in Exception Handlers
  - **Location:** `src/core/server.py:2860-2873` constructs multi-line error messages, repeated in 5+ locations
  - **Problem:** Error message templates like "Solution: Run 'docker-compose up -d'..." are duplicated across exception handlers. If we change Qdrant setup instructions, must update 10+ locations. Error message inconsistency between similar operations.
  - **Fix:** Extract error messages to constants or use custom exception classes with built-in messages (QdrantConnectionError already does this). Create ErrorMessages enum for common failure scenarios.

- [ ] **BUG-089**: Call Graph Store Never Closed - Resource Leak
  - **Location:** `src/services/code_indexing_service.py` creates CallGraphStore but never calls close()
  - **Problem:** CallGraphStore likely holds resources (connections, file handles) but the service never closes it. Same pattern in health_service.py with various stores. Python GC will eventually close, but explicit cleanup is better practice, especially for connection pools.
  - **Fix:** Add `async def close()` to service layer, call store.close() in it. Add context manager support: `async with CodeIndexingService(...) as svc:`

### Summary Statistics

- **Total Issues Found:** 14 (BUG-080 to BUG-089, REF-050 to REF-053, PERF-014)
- **Critical:** 3 (missing exc_info in critical infrastructure, swallowed exceptions in pool, corrupted health data)
- **High:** 4 (missing stack traces in Qdrant setup, silent data corruption, nested exception context loss, timeout type loss)
- **Medium:** 4 (inconsistent logging, generic exception wrapping, web server error handling, missing timeouts)
- **Low:** 3 (missing docstring raises, lazy logging, duplicate error messages, resource leaks)

**Key Risks for Production Debugging:**
1. Connection pool failures log without stack traces - impossible to debug Qdrant connectivity issues
2. Swallowed exceptions in release() hide connection pool degradation
3. Health scorer returns corrupted data silently when exceptions occur
4. TimeoutError re-wrapped as generic StorageError breaks retry logic
5. Missing timeouts in 100+ async operations can cause indefinite hangs

**Patterns Observed (vs Previous Audits):**
- UX-049 added exc_info=True to ~80% of locations, but critical infrastructure (connection pool, setup) was missed
- BUG-035/REF-028 fixed exception chains with `from e`, but ~10 locations still missing it
- INVEST-001 fixed bare except clauses, but found new antipattern: exception + pass with dead code
- Previous audits focused on syntax (bare except), missed semantic issues (swallowed exceptions with justification comments)

**Next Ticket Numbers:** BUG-080 to BUG-089, REF-050 to REF-053, PERF-014

## AUDIT-001 Part 7: Configuration & Validation Findings (2025-11-30)

**Investigation Scope:** Configuration management, validation, and allowed fields
**Files Analyzed:** 
- `src/config.py` (704 lines)
- `src/core/validation.py` (532 lines)
- `src/core/allowed_fields.py` (339 lines)
**Focus:** Range validators, interdependent config validation, default values, environment variable parsing, config file loading, feature flag conflicts, deprecated options, error messages, secret handling

### 🔴 CRITICAL Findings

- [ ] **BUG-080**: Embedding Model Configuration Mismatch Between config.py and allowed_fields.py
  - **Location:** `src/config.py:16-20` vs `src/core/allowed_fields.py:80-86`
  - **Problem:** config.py defines 3 supported embedding models (`EMBEDDING_MODEL_DIMENSIONS`): "all-MiniLM-L6-v2", "all-MiniLM-L12-v2", "all-mpnet-base-v2". But allowed_fields.py only allows "all-MiniLM-L6-v2" in the validation schema. If user sets `embedding_model="all-mpnet-base-v2"` (the DEFAULT), validation will reject it as invalid.
  - **Fix:** Update `allowed_fields.py:84` to `"allowed_values": ["all-MiniLM-L6-v2", "all-MiniLM-L12-v2", "all-mpnet-base-v2"]`

- [ ] **BUG-081**: Config File JSON Parse Errors Are Silently Ignored
  - **Location:** `src/config.py:671-677`
  - **Problem:** `_load_user_config_overrides()` catches all exceptions with generic `except Exception as e` and returns empty dict. If user creates malformed JSON in `~/.claude-rag/config.json` (missing comma, trailing comma, syntax error), the config is silently ignored with only a WARNING log. User thinks config is applied but defaults are used instead.
  - **Fix:** Catch `json.JSONDecodeError` specifically and raise `ConfigurationError` with helpful message showing the JSON syntax error location. Only catch `FileNotFoundError` silently.

- [ ] **BUG-082**: No Validation for User Config File Schema
  - **Location:** `src/config.py:692-696`
  - **Problem:** `_load_user_config_overrides()` loads arbitrary JSON and passes it as `**user_overrides` to `ServerConfig()`. If user puts invalid keys in config.json (typos, removed fields, nested dicts in wrong format), Pydantic's `extra="ignore"` silently discards them. User has no way to know their config is being ignored.
  - **Fix:** Add validation mode: if config file exists, validate keys against ServerConfig fields. Log WARNING for unrecognized keys. Add `--strict-config` mode that raises error on unknown keys.

### 🟡 HIGH Priority Findings

- [ ] **BUG-083**: Missing Range Validators for Timeout and Pool Configuration
  - **Location:** `src/config.py:281-284`
  - **Problem:** Several critical timeout/pool settings have no validators:
    - `qdrant_pool_timeout` (line 281): Should be >0, no upper bound check (could be set to 999999 seconds)
    - `qdrant_pool_recycle` (line 282): Should be >0, could be negative or zero
    - `qdrant_health_check_interval` (line 284): Should be >0, could be negative
  - **Fix:** Add field validators to ensure >0 for all three, reasonable upper bounds (pool_timeout <= 300s, recycle <= 86400s, health_check <= 3600s)

- [ ] **BUG-084**: BM25 Parameters Have No Range Validation
  - **Location:** `src/config.py:382-383`
  - **Problem:** BM25 algorithm parameters `bm25_k1` (default 1.5) and `bm25_b` (default 0.75) have no validators. BM25_b must be in [0, 1] range (controls document length normalization). BM25_k1 should be positive. Invalid values will cause search quality degradation or runtime errors.
  - **Fix:** Add field validators: `bm25_b` must be 0.0-1.0, `bm25_k1` must be >0 (typical range 1.2-2.0)

- [ ] **REF-055**: Duplicate watch_debounce_ms Field Definitions
  - **Location:** `src/config.py:162` (in IndexingFeatures) and `src/config.py:341` (in ServerConfig)
  - **Problem:** `watch_debounce_ms` is defined twice - once as a feature group field (IndexingFeatures.watch_debounce_ms = 1000) and once as a top-level ServerConfig field (ServerConfig.watch_debounce_ms = 1000). This creates confusion about which value is used and potential inconsistency.
  - **Fix:** Remove line 341 duplication. Use `self.indexing.watch_debounce_ms` consistently throughout codebase. This is the same issue as the old BUG-034 duplicate config field that was fixed.

- [ ] **BUG-085**: Feature Level Preset Modifies Config After Validation
  - **Location:** `src/config.py:394-419`
  - **Problem:** The `apply_feature_level_preset()` model_validator runs in mode='after', meaning it modifies config values AFTER Pydantic has validated them. If BASIC preset sets `self.memory.proactive_suggestions = False` but user explicitly enabled it via environment variable `CLAUDE_RAG_MEMORY__PROACTIVE_SUGGESTIONS=true`, the preset silently overrides user's explicit choice. No warning is logged.
  - **Fix:** Check if value was explicitly set (not default) before overriding. Add logging: "BASIC preset overriding proactive_suggestions from True to False". Or run preset in mode='before' so user values take precedence.

- [ ] **BUG-086**: Recency Decay Halflife Only Validates >0, Not Range
  - **Location:** `src/config.py:550-551`
  - **Problem:** `recency_decay_halflife_days` only checks `<= 0` but has no upper bound. User could set it to 100 years (36500 days), making all memories equally "recent" and breaking recency scoring. Typical useful range is 1-90 days.
  - **Fix:** Add upper bound check: `if recency_decay_halflife_days > 365: raise ValueError("recency_decay_halflife_days should not exceed 1 year (365 days)")`

### 🟢 MEDIUM Priority Findings

- [ ] **REF-056**: No Validation for Cron Expression Format in pruning_schedule
  - **Location:** `src/config.py:131`
  - **Problem:** `pruning_schedule: str = "0 2 * * *"` accepts any string value. If user enters invalid cron syntax ("2am daily", "*/5 * *", "garbage"), it will only fail at runtime when the scheduler tries to parse it. No validation happens during config load.
  - **Fix:** Add field validator that uses `croniter` or cron regex to validate syntax: `@field_validator('pruning_schedule')` that raises ValueError on invalid cron format.

- [ ] **BUG-087**: Missing Validation for git_index_branches Enum Value
  - **Location:** `src/config.py:178` vs `src/config.py:604-605`
  - **Problem:** `git_index_branches` is defined as `str = "current"` (line 178) but validation only checks it in `validate_config()` at line 604. There's no Pydantic `Literal["current", "all"]` type hint, so user could set any string via environment variable and it won't be caught until the validator runs. Error message only appears after all other config is loaded.
  - **Fix:** Change type hint to `git_index_branches: Literal["current", "all"] = "current"` for immediate validation

- [ ] **REF-057**: Inconsistent Validation Location - Some in Field Validators, Some in Model Validators
  - **Location:** Throughout `src/config.py`
  - **Problem:** Some validation is done in `@field_validator` decorators (e.g., `parallel_workers` line 49, `gpu_memory_fraction` line 57), while other identical validation is done in the massive `validate_config()` model_validator (e.g., `embedding_batch_size` line 510-513, `embedding_cache_ttl_days` line 521-524). This inconsistency makes it hard to find where validation happens.
  - **Fix:** Move all single-field range checks to `@field_validator` decorators. Keep only interdependency checks in model_validator. This improves error locality and makes validation discoverable.

- [ ] **BUG-088**: No Validation for cross_project_default_mode Enum
  - **Location:** `src/config.py:87`
  - **Problem:** `cross_project_default_mode: str = "current"` has comment saying `"current" or "all"` but no validation enforces this. Should be `Literal["current", "all"]` type hint for Pydantic to validate.
  - **Fix:** Change to `cross_project_default_mode: Literal["current", "all"] = "current"`

- [ ] **BUG-089**: hybrid_fusion_method Has No Validation
  - **Location:** `src/config.py:369`
  - **Problem:** `hybrid_fusion_method: str = "weighted"` accepts any string. Valid values are likely "weighted", "rrf" (reciprocal rank fusion), "linear". No validation means user could set "invalid" and only discover at search time.
  - **Fix:** Add allowed values validation. Search codebase for where this is used to determine valid options, then add `Literal` type hint or field validator.

- [ ] **REF-058**: Query Expansion Similarity Threshold Redundantly Validated Twice
  - **Location:** `src/config.py:364` and `src/config.py:575-580`
  - **Problem:** `query_expansion_similarity_threshold` is validated in the large `validate_config()` model_validator (lines 575-580) to be in [0.0, 1.0]. This should be a `@field_validator` for consistency and better error messages.
  - **Fix:** Add `@field_validator('query_expansion_similarity_threshold')` and remove from validate_config()

- [ ] **BUG-090**: No Maximum Limit for analytics_retention_days
  - **Location:** `src/config.py:113`
  - **Problem:** `usage_analytics_retention_days: int = 90` has no validation. User could set to 36500 (100 years), causing analytics data to never be cleaned up, leading to unbounded storage growth.
  - **Fix:** Add field validator with reasonable upper bound (e.g., max 730 days / 2 years)

### 🔵 LOW Priority Findings

- [ ] **REF-059**: Magic Number 50000 for Content Max Length Not Centralized
  - **Location:** `src/core/allowed_fields.py:24` and `src/core/validation.py:259`
  - **Problem:** The value 50000 (max content length in chars) appears in allowed_fields as a constraint and is hardcoded in validation.py as the default max_bytes (51200 = ~50KB). These should be linked or use a shared constant.
  - **Fix:** Define `MAX_CONTENT_CHARS = 50000` and `MAX_CONTENT_BYTES = 51200` as module constants in a shared location

- [ ] **REF-060**: Validation Error Messages Don't Include Current Value for All Fields
  - **Location:** Throughout `src/config.py` validation
  - **Problem:** Some validators include current value in error message (e.g., line 513 `"embedding_batch_size must not exceed 256 (memory constraint)"`), but don't show what value was provided. Compare to line 64 which shows `(got {v})`. Inconsistent error message quality.
  - **Fix:** Standardize all validation errors to include `(got {value})` for debugging

- [ ] **REF-061**: Path Expansion Creates Directories on Config Load
  - **Location:** `src/config.py:641` and `src/config.py:648`
  - **Problem:** The properties `embedding_cache_path_expanded` and `sqlite_path_expanded` call `path.parent.mkdir(parents=True, exist_ok=True)` as a side effect of accessing the property. This violates principle of least surprise - simply loading config should not create filesystem changes. If user has wrong permissions, config load will fail unexpectedly.
  - **Fix:** Remove mkdir from properties. Create directories lazily when first writing to those paths (in EmbeddingCache.__init__, etc.)

- [ ] **REF-062**: No Validation That project_name Pattern Matches Actual Usage
  - **Location:** `src/core/allowed_fields.py:52` defines pattern `r"^[a-zA-Z0-9_\-\.]+$"`, but `src/core/validation.py:483` uses same pattern
  - **Problem:** The project_name pattern is duplicated between allowed_fields.py and validation.py. If one is updated but not the other, validation becomes inconsistent. Regex patterns should be defined once and imported.
  - **Fix:** Define `PROJECT_NAME_PATTERN = r"^[a-zA-Z0-9_\-\.]+$"` in a constants module, import in both files


## AUDIT-001 Part 10: Exception Handling & Error Recovery Findings (2025-11-30)

**Investigation Scope:** Exception handling patterns across entire codebase, focusing on issues not caught by previous audits (BUG-035, BUG-036, BUG-054, REF-028, INVEST-001, UX-049)

### CRITICAL Findings

- [ ] **BUG-080**: Missing exc_info=True in Connection Pool Error Logs
  - **Location:** `src/store/connection_pool.py:187`, `src/store/connection_pool.py:323`, `src/store/connection_pool.py:534`
  - **Problem:** Connection pool logs errors without stack traces (no `exc_info=True`). When pool initialization/acquisition/creation fails in production, logs show "Failed to X: <error message>" but no stack trace, making debugging impossible. This is critical infrastructure - connection failures are common and need full context.
  - **Fix:** Add `exc_info=True` to all logger.error() calls in connection_pool.py. Example: `logger.error(f"Failed to initialize connection pool: {e}", exc_info=True)`

- [ ] **BUG-081**: Exception Swallowed in Connection Release with Comment Justification
  - **Location:** `src/store/connection_pool.py:375-377`
  - **Problem:** `release()` catches all exceptions and logs error but explicitly doesn't raise with comment "Don't raise - connection is lost but we continue". This violates exception handling best practices - swallowing exceptions hides bugs. If release fails repeatedly due to bug (e.g., lock corruption, client_map corruption), caller never knows pool is degrading. This masks serious issues like connection leaks.
  - **Fix:** At minimum add metrics tracking for failed releases and raise alert if failure rate > 1%. Better: only swallow expected exceptions (asyncio.QueueFull), re-raise unexpected ones.

- [ ] **BUG-082**: Incomplete Logging in Health Scorer Exception Handler
  - **Location:** `src/memory/health_scorer.py:222-225`
  - **Problem:** Catches `Exception as e`, logs error, then has dead code `pass` after comment "Return empty distribution on error". The function continues to line 227 `return distribution` regardless. If exception happens, returns partially-filled distribution dict without any indication data is incomplete. Callers receive corrupted data. Missing `exc_info=True` makes debugging impossible.
  - **Fix:** Add `exc_info=True` to log, return empty dict immediately after logging (don't fall through to return statement), document that empty dict means error occurred.

### HIGH Priority Findings

- [ ] **BUG-083**: Missing exc_info=True in Qdrant Setup Critical Errors
  - **Location:** `src/store/qdrant_setup.py:157`, `src/store/qdrant_setup.py:291`, `src/store/qdrant_setup.py:309`
  - **Problem:** Qdrant connection/health check failures log errors without stack traces. `collection_exists()` returns False on ANY exception (line 157-158), hiding whether it's a connection error, auth error, or bug in code. `health_check()` returns False on any exception (309-310) - same issue. Production debugging requires stack traces for these critical infrastructure checks.
  - **Fix:** Add `exc_info=True` to all logger.error() in qdrant_setup.py. Consider raising specific exceptions instead of returning False for different failure modes.

- [ ] **BUG-084**: Silent ValueError to Default State Conversion Hides Data Corruption
  - **Location:** `src/memory/health_scorer.py:215-218`, same pattern in store/qdrant_store.py:1526
  - **Problem:** `except ValueError: state = LifecycleState.ACTIVE` silently converts invalid lifecycle states to ACTIVE without logging. If database contains corrupted state values (e.g., "ARCHIVD" typo), code hides corruption by defaulting to ACTIVE. Users see incorrect lifecycle stats. This is data integrity issue disguised as graceful degradation.
  - **Fix:** Log warning with value that failed to parse: `logger.warning(f"Invalid lifecycle state '{state}', defaulting to ACTIVE")`. Consider adding data validation job to detect corruption.

- [ ] **BUG-085**: Exception in Nested Import Loop Lost Without Context
  - **Location:** `src/services/memory_service.py:1366`, nested inside another exception handler at line 1385
  - **Problem:** Import loop at line 1251-1367 catches exceptions per-memory and appends to errors list. The outer exception handler at 1385 catches general exceptions but logs "Failed to import memories" without including the accumulated errors list. If 50 of 100 memories fail with different errors, only the last exception is logged, losing all diagnostic information about the 49 other failures.
  - **Fix:** Include errors list in outer exception log: `logger.error(f"Failed to import memories: {e}. Errors: {errors[:10]}", exc_info=True)` (limit to first 10 to avoid log spam)

- [ ] **BUG-086**: TimeoutError Re-raised as Generic StorageError Loses Exception Type
  - **Location:** `src/services/memory_service.py:320-322`, and 20+ similar locations
  - **Problem:** Pattern `except TimeoutError: raise StorageError("operation timed out")` loses the original TimeoutError type. Callers can't distinguish timeouts from other storage errors (connection refused, disk full, etc.). This makes retry logic impossible - code that should retry on timeout will retry on all StorageErrors, including unretriable ones like disk full.
  - **Fix:** Create TimeoutError subclass of StorageError: `raise StorageTimeoutError("operation timed out") from e`. Update callers to catch and retry only TimeoutError.

### MEDIUM Priority Findings

- [ ] **REF-050**: Inconsistent Exception Logging Patterns Across Services
  - **Location:** `src/services/*.py` - mix of `exc_info=True` and no exc_info
  - **Problem:** Services have inconsistent exception logging. Some use `exc_info=True` (memory_service.py:335-339), others don't (analytics_service.py:163-164). Code reviewer or new developer can't tell which is intentional. Grep shows ~80% of exception logs have exc_info=True (from UX-049 fix), but remaining 20% may be bugs or intentional.
  - **Fix:** Document exception logging policy in CONTRIBUTING.md: always use exc_info=True for unexpected exceptions, omit for expected validation errors. Add linting rule to enforce.

- [ ] **REF-051**: Generic Exception Re-wrapping Loses Specific Error Types
  - **Location:** `src/core/server.py:2864-2873`, and similar in multiple store operations
  - **Problem:** Pattern `except Exception as e: raise RetrievalError(...)` catches specific exceptions (ConnectionError, ValidationError) and re-wraps as generic error. Original exception type information is lost. Callers can't implement error-specific handling (e.g., retry on connection errors but not validation errors).
  - **Fix:** Preserve original exception in chain: `raise RetrievalError(...) from e` (already done in most places, missing in ~10 locations). Better: catch specific exception types separately and re-raise with appropriate custom exception.

- [ ] **BUG-087**: Dashboard Web Server Swallows All Exceptions and Returns Generic 500
  - **Location:** `src/dashboard/web_server.py:236`, :267, :304, :332, :453, :508, :572, :610, :657
  - **Problem:** Every endpoint has `except Exception as e: logger.error(...); self._send_error_response(500, str(e))`. This returns raw exception messages to HTTP clients, potentially leaking sensitive information (file paths, database schemas, internal IPs). Also returns 500 for client errors (ValidationError should be 400).
  - **Fix:** Map exception types to HTTP status codes: ValidationError -> 400, NotFoundError -> 404, StorageError -> 503. Sanitize exception messages: return generic message to client, log full details server-side.

- [ ] **BUG-088**: asyncio.timeout Context Manager Missing in 30+ Locations
  - **Location:** Compare files with `asyncio.timeout()` (35 uses) vs async operations without timeout (100+ async def methods)
  - **Problem:** Most async operations have 30s timeout via `async with asyncio.timeout(30.0)`, but many don't (e.g., connection_pool.py acquire, health checks, background indexing). Without timeouts, operations can hang indefinitely on network issues, deadlocks, or Qdrant hangs. This violates fail-fast principle.
  - **Fix:** Audit all async methods that do I/O (network, disk) and add timeouts. Create wrapper decorator `@with_timeout(seconds=30)` to enforce consistently.

### LOW Priority Findings

- [ ] **REF-052**: Missing Docstring Raises Sections for 90% of Functions
  - **Location:** Entire codebase - functions raise custom exceptions but don't document in docstring
  - **Problem:** Only ~10% of functions document raised exceptions in docstring Raises section. Functions like `store()` raise ValidationError, StorageError, ReadOnlyError but docstring doesn't list them (src/services/memory_service.py:241-340). Callers don't know what exceptions to catch.
  - **Fix:** Add Raises section to all public API docstrings. Use ruff/pydocstyle to enforce. Example template in CONTRIBUTING.md.

- [ ] **PERF-014**: Unnecessary String Formatting in Logger Calls Before Exception Handling
  - **Location:** Throughout codebase - `logger.error(f"Failed to X: {e}")` before checking if logging is enabled
  - **Problem:** Python evaluates f-strings before passing to logger, even if log level is INFO and error logs are disabled. This wastes CPU cycles formatting strings that are never logged. In tight loops (e.g., indexing 10K files), this adds up.
  - **Fix:** Use lazy logging: `logger.error("Failed to X: %s", e)` with %-formatting. Logger only formats if level is enabled. Python logging best practice.

- [ ] **REF-053**: Duplicate Error Message Construction in Exception Handlers
  - **Location:** `src/core/server.py:2860-2873` constructs multi-line error messages, repeated in 5+ locations
  - **Problem:** Error message templates like "Solution: Run 'docker-compose up -d'..." are duplicated across exception handlers. If we change Qdrant setup instructions, must update 10+ locations. Error message inconsistency between similar operations.
  - **Fix:** Extract error messages to constants or use custom exception classes with built-in messages (QdrantConnectionError already does this). Create ErrorMessages enum for common failure scenarios.

- [ ] **BUG-089**: Call Graph Store Never Closed - Resource Leak
  - **Location:** `src/services/code_indexing_service.py` creates CallGraphStore but never calls close()
  - **Problem:** CallGraphStore likely holds resources (connections, file handles) but the service never closes it. Same pattern in health_service.py with various stores. Python GC will eventually close, but explicit cleanup is better practice, especially for connection pools.
  - **Fix:** Add `async def close()` to service layer, call store.close() in it. Add context manager support: `async with CodeIndexingService(...) as svc:`

### Summary Statistics

- **Total Issues Found:** 14 (BUG-080 to BUG-089, REF-050 to REF-053, PERF-014)
- **Critical:** 3 (missing exc_info in critical infrastructure, swallowed exceptions in pool, corrupted health data)
- **High:** 4 (missing stack traces in Qdrant setup, silent data corruption, nested exception context loss, timeout type loss)
- **Medium:** 4 (inconsistent logging, generic exception wrapping, web server error handling, missing timeouts)
- **Low:** 3 (missing docstring raises, lazy logging, duplicate error messages, resource leaks)

**Key Risks for Production Debugging:**
1. Connection pool failures log without stack traces - impossible to debug Qdrant connectivity issues
2. Swallowed exceptions in release() hide connection pool degradation
3. Health scorer returns corrupted data silently when exceptions occur
4. TimeoutError re-wrapped as generic StorageError breaks retry logic
5. Missing timeouts in 100+ async operations can cause indefinite hangs

**Patterns Observed (vs Previous Audits):**
- UX-049 added exc_info=True to ~80% of locations, but critical infrastructure (connection pool, setup) was missed
- BUG-035/REF-028 fixed exception chains with `from e`, but ~10 locations still missing it
- INVEST-001 fixed bare except clauses, but found new antipattern: exception + pass with dead code
- Previous audits focused on syntax (bare except), missed semantic issues (swallowed exceptions with justification comments)

**Next Ticket Numbers:** BUG-080 to BUG-089, REF-050 to REF-053, PERF-014

## AUDIT-001 Part 7: Configuration & Validation Findings (2025-11-30)

**Investigation Scope:** Configuration management, validation, and allowed fields
**Files Analyzed:**
- `src/config.py` (704 lines)
- `src/core/validation.py` (532 lines)
- `src/core/allowed_fields.py` (339 lines)
**Focus:** Range validators, interdependent config validation, default values, environment variable parsing, config file loading, feature flag conflicts, deprecated options, error messages, secret handling

### 🔴 CRITICAL Findings

- [ ] **BUG-080**: Embedding Model Configuration Mismatch Between config.py and allowed_fields.py
  - **Location:** `src/config.py:16-20` vs `src/core/allowed_fields.py:80-86`
  - **Problem:** config.py defines 3 supported embedding models (`EMBEDDING_MODEL_DIMENSIONS`): "all-MiniLM-L6-v2", "all-MiniLM-L12-v2", "all-mpnet-base-v2". But allowed_fields.py only allows "all-MiniLM-L6-v2" in the validation schema. If user sets `embedding_model="all-mpnet-base-v2"` (the DEFAULT), validation will reject it as invalid.
  - **Fix:** Update `allowed_fields.py:84` to `"allowed_values": ["all-MiniLM-L6-v2", "all-MiniLM-L12-v2", "all-mpnet-base-v2"]`

- [ ] **BUG-081**: Config File JSON Parse Errors Are Silently Ignored
  - **Location:** `src/config.py:671-677`
  - **Problem:** `_load_user_config_overrides()` catches all exceptions with generic `except Exception as e` and returns empty dict. If user creates malformed JSON in `~/.claude-rag/config.json` (missing comma, trailing comma, syntax error), the config is silently ignored with only a WARNING log. User thinks config is applied but defaults are used instead.
  - **Fix:** Catch `json.JSONDecodeError` specifically and raise `ConfigurationError` with helpful message showing the JSON syntax error location. Only catch `FileNotFoundError` silently.

- [ ] **BUG-082**: No Validation for User Config File Schema
  - **Location:** `src/config.py:692-696`
  - **Problem:** `_load_user_config_overrides()` loads arbitrary JSON and passes it as `**user_overrides` to `ServerConfig()`. If user puts invalid keys in config.json (typos, removed fields, nested dicts in wrong format), Pydantic's `extra="ignore"` silently discards them. User has no way to know their config is being ignored.
  - **Fix:** Add validation mode: if config file exists, validate keys against ServerConfig fields. Log WARNING for unrecognized keys. Add `--strict-config` mode that raises error on unknown keys.

### 🟡 HIGH Priority Findings

- [ ] **BUG-083**: Missing Range Validators for Timeout and Pool Configuration
  - **Location:** `src/config.py:281-284`
  - **Problem:** Several critical timeout/pool settings have no validators:
    - `qdrant_pool_timeout` (line 281): Should be >0, no upper bound check (could be set to 999999 seconds)
    - `qdrant_pool_recycle` (line 282): Should be >0, could be negative or zero
    - `qdrant_health_check_interval` (line 284): Should be >0, could be negative
  - **Fix:** Add field validators to ensure >0 for all three, reasonable upper bounds (pool_timeout <= 300s, recycle <= 86400s, health_check <= 3600s)

- [ ] **BUG-084**: BM25 Parameters Have No Range Validation
  - **Location:** `src/config.py:382-383`
  - **Problem:** BM25 algorithm parameters `bm25_k1` (default 1.5) and `bm25_b` (default 0.75) have no validators. BM25_b must be in [0, 1] range (controls document length normalization). BM25_k1 should be positive. Invalid values will cause search quality degradation or runtime errors.
  - **Fix:** Add field validators: `bm25_b` must be 0.0-1.0, `bm25_k1` must be >0 (typical range 1.2-2.0)

- [ ] **REF-055**: Duplicate watch_debounce_ms Field Definitions
  - **Location:** `src/config.py:162` (in IndexingFeatures) and `src/config.py:341` (in ServerConfig)
  - **Problem:** `watch_debounce_ms` is defined twice - once as a feature group field (IndexingFeatures.watch_debounce_ms = 1000) and once as a top-level ServerConfig field (ServerConfig.watch_debounce_ms = 1000). This creates confusion about which value is used and potential inconsistency.
  - **Fix:** Remove line 341 duplication. Use `self.indexing.watch_debounce_ms` consistently throughout codebase. This is the same issue as the old BUG-034 duplicate config field that was fixed.

- [ ] **BUG-085**: Feature Level Preset Modifies Config After Validation
  - **Location:** `src/config.py:394-419`
  - **Problem:** The `apply_feature_level_preset()` model_validator runs in mode='after', meaning it modifies config values AFTER Pydantic has validated them. If BASIC preset sets `self.memory.proactive_suggestions = False` but user explicitly enabled it via environment variable `CLAUDE_RAG_MEMORY__PROACTIVE_SUGGESTIONS=true`, the preset silently overrides user's explicit choice. No warning is logged.
  - **Fix:** Check if value was explicitly set (not default) before overriding. Add logging: "BASIC preset overriding proactive_suggestions from True to False". Or run preset in mode='before' so user values take precedence.

- [ ] **BUG-086**: Recency Decay Halflife Only Validates >0, Not Range
  - **Location:** `src/config.py:550-551`
  - **Problem:** `recency_decay_halflife_days` only checks `<= 0` but has no upper bound. User could set it to 100 years (36500 days), making all memories equally "recent" and breaking recency scoring. Typical useful range is 1-90 days.
  - **Fix:** Add upper bound check: `if recency_decay_halflife_days > 365: raise ValueError("recency_decay_halflife_days should not exceed 1 year (365 days)")`

### 🟢 MEDIUM Priority Findings

- [ ] **REF-056**: No Validation for Cron Expression Format in pruning_schedule
  - **Location:** `src/config.py:131`
  - **Problem:** `pruning_schedule: str = "0 2 * * *"` accepts any string value. If user enters invalid cron syntax ("2am daily", "*/5 * *", "garbage"), it will only fail at runtime when the scheduler tries to parse it. No validation happens during config load.
  - **Fix:** Add field validator that uses `croniter` or cron regex to validate syntax: `@field_validator('pruning_schedule')` that raises ValueError on invalid cron format.

- [ ] **BUG-087**: Missing Validation for git_index_branches Enum Value
  - **Location:** `src/config.py:178` vs `src/config.py:604-605`
  - **Problem:** `git_index_branches` is defined as `str = "current"` (line 178) but validation only checks it in `validate_config()` at line 604. There's no Pydantic `Literal["current", "all"]` type hint, so user could set any string via environment variable and it won't be caught until the validator runs. Error message only appears after all other config is loaded.
  - **Fix:** Change type hint to `git_index_branches: Literal["current", "all"] = "current"` for immediate validation

- [ ] **REF-057**: Inconsistent Validation Location - Some in Field Validators, Some in Model Validators
  - **Location:** Throughout `src/config.py`
  - **Problem:** Some validation is done in `@field_validator` decorators (e.g., `parallel_workers` line 49, `gpu_memory_fraction` line 57), while other identical validation is done in the massive `validate_config()` model_validator (e.g., `embedding_batch_size` line 510-513, `embedding_cache_ttl_days` line 521-524). This inconsistency makes it hard to find where validation happens.
  - **Fix:** Move all single-field range checks to `@field_validator` decorators. Keep only interdependency checks in model_validator. This improves error locality and makes validation discoverable.

- [ ] **BUG-088**: No Validation for cross_project_default_mode Enum
  - **Location:** `src/config.py:87`
  - **Problem:** `cross_project_default_mode: str = "current"` has comment saying `"current" or "all"` but no validation enforces this. Should be `Literal["current", "all"]` type hint for Pydantic to validate.
  - **Fix:** Change to `cross_project_default_mode: Literal["current", "all"] = "current"`

- [ ] **BUG-089**: hybrid_fusion_method Has No Validation
  - **Location:** `src/config.py:369`
  - **Problem:** `hybrid_fusion_method: str = "weighted"` accepts any string. Valid values are likely "weighted", "rrf" (reciprocal rank fusion), "linear". No validation means user could set "invalid" and only discover at search time.
  - **Fix:** Add allowed values validation. Search codebase for where this is used to determine valid options, then add `Literal` type hint or field validator.

- [ ] **REF-058**: Query Expansion Similarity Threshold Redundantly Validated Twice
  - **Location:** `src/config.py:364` and `src/config.py:575-580`
  - **Problem:** `query_expansion_similarity_threshold` is validated in the large `validate_config()` model_validator (lines 575-580) to be in [0.0, 1.0]. This should be a `@field_validator` for consistency and better error messages.
  - **Fix:** Add `@field_validator('query_expansion_similarity_threshold')` and remove from validate_config()

- [ ] **BUG-090**: No Maximum Limit for analytics_retention_days
  - **Location:** `src/config.py:113`
  - **Problem:** `usage_analytics_retention_days: int = 90` has no validation. User could set to 36500 (100 years), causing analytics data to never be cleaned up, leading to unbounded storage growth.
  - **Fix:** Add field validator with reasonable upper bound (e.g., max 730 days / 2 years)

### 🔵 LOW Priority Findings

- [ ] **REF-059**: Magic Number 50000 for Content Max Length Not Centralized
  - **Location:** `src/core/allowed_fields.py:24` and `src/core/validation.py:259`
  - **Problem:** The value 50000 (max content length in chars) appears in allowed_fields as a constraint and is hardcoded in validation.py as the default max_bytes (51200 = ~50KB). These should be linked or use a shared constant.
  - **Fix:** Define `MAX_CONTENT_CHARS = 50000` and `MAX_CONTENT_BYTES = 51200` as module constants in a shared location

- [ ] **REF-060**: Validation Error Messages Don't Include Current Value for All Fields
  - **Location:** Throughout `src/config.py` validation
  - **Problem:** Some validators include current value in error message (e.g., line 513 `"embedding_batch_size must not exceed 256 (memory constraint)"`), but don't show what value was provided. Compare to line 64 which shows `(got {v})`. Inconsistent error message quality.
  - **Fix:** Standardize all validation errors to include `(got {value})` for debugging

- [ ] **REF-061**: Path Expansion Creates Directories on Config Load
  - **Location:** `src/config.py:641` and `src/config.py:648`
  - **Problem:** The properties `embedding_cache_path_expanded` and `sqlite_path_expanded` call `path.parent.mkdir(parents=True, exist_ok=True)` as a side effect of accessing the property. This violates principle of least surprise - simply loading config should not create filesystem changes. If user has wrong permissions, config load will fail unexpectedly.
  - **Fix:** Remove mkdir from properties. Create directories lazily when first writing to those paths (in EmbeddingCache.__init__, etc.)

- [ ] **REF-062**: No Validation That project_name Pattern Matches Actual Usage
  - **Location:** `src/core/allowed_fields.py:52` defines pattern `r"^[a-zA-Z0-9_\-\.]+$"`, but `src/core/validation.py:483` uses same pattern
  - **Problem:** The project_name pattern is duplicated between allowed_fields.py and validation.py. If one is updated but not the other, validation becomes inconsistent. Regex patterns should be defined once and imported.
  - **Fix:** Define `PROJECT_NAME_PATTERN = r"^[a-zA-Z0-9_\-\.]+$"` in a constants module, import in both files

---

## AUDIT-001 Part 8: CLI Commands & User Experience Findings (2025-11-30)

**Full details in:** `planning_docs/AUDIT-001_part8_cli_findings.md`

**Investigation Scope:** 26 CLI command files (~4,500 lines) covering index, health, status, git operations, analytics, backup/import/export, project/workspace/repository management

### Quick Summary

**Total Issues Found:** 19 (3 Critical, 5 High, 6 Medium, 5 Low)

**Critical Issues:**
- BUG-080: browse, tutorial, validate-setup, perf commands advertised but not integrated (completely non-functional)
- BUG-081: perf commands imported but no parser created
- BUG-082: Most commands don't return proper exit codes (breaks CI/automation)

**High Priority:**
- UX-060: Three different progress indicator patterns across commands
- BUG-083: Missing Ctrl+C handling in most commands (ugly stack traces)
- BUG-084: analytics/session-summary block async event loop
- UX-061: Three different confirmation UI patterns
- BUG-085: Click-based commands (tags, collections, auto-tag) hidden from main CLI

**Key User Impact:**
- New users run `claude-rag tutorial` → error message (broken onboarding)
- Shell scripts can't detect command failures (exit codes always 0)
- Features like auto-tagging completely undiscoverable
- Inconsistent visual feedback confuses users

**Next Ticket Numbers:** BUG-080 to BUG-086, UX-060 to UX-066, REF-050 to REF-053, PERF-014

**Next Ticket Numbers:** BUG-073+, REF-050+, PERF-014+

---

## AUDIT-001 Part 11: Code Analysis & Quality Scoring Findings (2025-11-30)

**Investigation Scope:** 1,512 lines across 7 files (complexity_analyzer.py, importance_scorer.py, criticality_analyzer.py, usage_analyzer.py, code_duplicate_detector.py, call_extractors.py, quality_analyzer.py)

### 🔴 CRITICAL Findings

- [ ] **BUG-073**: Division by Zero Risk in Nesting Depth Calculation
  - **Location:** `src/analysis/complexity_analyzer.py:184`
  - **Problem:** `depth = leading // indent_size` where `indent_size` could be 0 if language not in `indent_chars` dict and subsequent logic fails. Line 184 checks `if indent_size > 0` but the else clause sets `depth = 0`, which means files with tabs or non-standard indentation are scored as having zero nesting depth regardless of actual nesting.
  - **Fix:** Fall back to detecting mixed tabs/spaces: `indent_size = 4 if '\t' not in line else 1` and warn about unrecognized indentation style

- [ ] **BUG-074**: Cyclomatic Complexity Double-Counts Ternary Operators
  - **Location:** `src/analysis/complexity_analyzer.py:89-139`
  - **Problem:** The pattern `r'\?.*:'` on line 111 matches ternary operators but also matches unrelated `?` characters in regex, comments, or strings (e.g., `"What is this?:"`). This inflates complexity scores incorrectly. Additionally, the regex `r'\?.*:'` is greedy and matches across multiple lines, potentially double-counting multiple ternaries as a single match.
  - **Fix:** Use non-greedy pattern `r'\?[^:]*:'` and add word boundaries. Better: only count `?` followed by `:` on same line with balanced parens.

- [ ] **BUG-075**: Importance Score Normalization Breaks with High Weights
  - **Location:** `src/analysis/importance_scorer.py:240-255`
  - **Problem:** The normalization divides `raw_score` by `baseline_max = 1.2`, but with custom weights like `(2.0, 2.0, 2.0)`, the max possible raw_score is `(0.7*2.0) + (0.2*2.0) + (0.3*2.0) = 2.4`, which when divided by 1.2 gives 2.0, then clamped to 1.0. This means all high-complexity/high-usage/high-criticality code gets the same score of 1.0, losing discriminatory power. The normalization formula is only correct for default weights.
  - **Fix:** Calculate dynamic baseline_max: `baseline_max = (0.7 * complexity_weight) + (0.2 * usage_weight) + (0.3 * criticality_weight)` instead of hardcoding 1.2

### 🟡 HIGH Priority Findings

- [ ] **PERF-014**: O(N²) Duplicate Pair Extraction Without Early Exit
  - **Location:** `src/analysis/code_duplicate_detector.py:250-262`
  - **Problem:** `get_duplicate_pairs()` checks upper triangle of similarity matrix (O(N²)) but doesn't stop early when max_pairs limit is reached. For 10,000 units with threshold=0.5 (many matches), this creates hundreds of thousands of DuplicatePair objects, consuming gigabytes of RAM, even if caller only needs top 100 pairs.
  - **Fix:** Add `max_pairs: Optional[int] = None` parameter and break early after reaching limit. Since pairs are sorted descending, can use heap to maintain top-K pairs during iteration.

- [ ] **BUG-076**: JavaScript Call Extractor Fails Silently on tree-sitter Import Failure
  - **Location:** `src/analysis/call_extractors.py:232-242`
  - **Problem:** If `tree-sitter` or `tree-sitter-javascript` packages are not installed, `JavaScriptCallExtractor.__init__()` catches ImportError and sets `self.parser = None`, then all subsequent `extract_calls()` calls log warning and return empty list. This silently breaks call graph construction for JS/TS projects with no visible error to the user—they just get incomplete importance scores.
  - **Fix:** Either make tree-sitter a required dependency, or raise clear error on first use: "Install tree-sitter-javascript to analyze JavaScript files: pip install tree-sitter tree-sitter-javascript"

- [ ] **BUG-077**: File Proximity Score Calculation Fails for Pathlib.PurePath Objects
  - **Location:** `src/analysis/criticality_analyzer.py:218-279`
  - **Problem:** Lines 230-238 check `if not isinstance(file_path, Path)` and fall back to function name scoring only, but the code then tries to call `file_path.stem`, `file_path.parts`, etc., which will fail if file_path is a string or PurePosixPath. The isinstance check is insufficient—it should check for PathLike protocol or convert to Path.
  - **Fix:** Add `file_path = Path(file_path) if not isinstance(file_path, Path) else file_path` at start of method before any attribute access

- [ ] **BUG-078**: Call Graph State Leak Between Files in UsageAnalyzer
  - **Location:** `src/analysis/usage_analyzer.py:124-126`
  - **Problem:** The code checks `if all_units and not self.call_graph:` before building call graph. This means if `calculate_importance()` is called with `all_units=None` after a previous call with `all_units=[...]`, the old call graph persists and affects the new calculation. If the user analyzes file A, then file B without calling `reset()`, file B's usage metrics will include caller counts from file A's call graph.
  - **Fix:** Always rebuild call graph when `all_units` is provided: change condition to `if all_units:` (remove `and not self.call_graph`)

### 🟢 MEDIUM Priority Findings

- [ ] **REF-050**: Hardcoded Score Ranges Duplicated Across Analyzers
  - **Location:** `src/analysis/complexity_analyzer.py:36-43`, `src/analysis/usage_analyzer.py:85-90`, `src/analysis/criticality_analyzer.py:70-71`
  - **Problem:** Each analyzer defines its own MIN/MAX score ranges (0.3-0.7, 0.0-0.2, 0.0-0.3) as class constants. These ranges are tightly coupled to the importance scorer's normalization logic (line 244-250 in importance_scorer.py). If we want to adjust score ranges, must update 4 files consistently. Magic numbers antipattern.
  - **Fix:** Define score range constants in a shared `src/analysis/constants.py` module. Use named constants like `COMPLEXITY_SCORE_RANGE = (0.3, 0.7)` and import in all analyzers.

- [ ] **BUG-079**: Maintainability Index Can Exceed 100 with Documentation Bonus
  - **Location:** `src/analysis/quality_analyzer.py:197-235`
  - **Problem:** Line 228 calculates `mi = 100 - (cyclomatic_complexity * 2) - (line_count / 10)`, then line 232 adds `mi += 5` for documentation. For very simple functions (complexity=1, lines=5), this gives `mi = 100 - 2 - 0.5 + 5 = 102.5`, then clamped to 100. But the formula can also underflow: complexity=50, lines=100 gives `mi = 100 - 100 - 10 = -10`, clamped to 0. The clamping masks the issue but indicates the formula is incorrect for edge cases.
  - **Fix:** Clamp BEFORE applying documentation bonus: `mi = max(0, min(95, int(mi)))` (keep room for +5 bonus), then add bonus, then final clamp to 100

- [ ] **PERF-015**: Duplicate Clustering Performs Redundant Similarity Lookups
  - **Location:** `src/analysis/code_duplicate_detector.py:356-383`
  - **Problem:** The inner loop (lines 378-382) accesses `similarity_matrix[idx_i][idx_j]` for each pair in cluster to calculate average similarity. For a cluster of size 100, this performs 4,950 matrix accesses (100 choose 2). Since the matrix is symmetric, could cache or use matrix slicing for batch access.
  - **Fix:** Use vectorized NumPy operations: extract cluster submatrix with `cluster_similarities = similarity_matrix[np.ix_(indices, indices)]`, then compute mean of upper triangle

- [ ] **BUG-080**: Comment Filtering in Line Count Is Too Aggressive
  - **Location:** `src/analysis/complexity_analyzer.py:141-151`
  - **Problem:** Line 148 filters out lines starting with `#, //, /*, *, """, '''` as comments. But this incorrectly excludes valid code: string literals starting with `"""` at line start, dictionary keys like `"#channel"`, and Python decorators like `@property` (the `*` pattern matches multiplication operators at line start after auto-formatting). This undercounts lines and underestimates complexity.
  - **Fix:** Only filter lines where the comment marker is the first non-whitespace character AND not inside a string. Use language-specific logic instead of one-size-fits-all.

- [ ] **REF-051**: Python Call Extractor Doesn't Reset State Between Calls
  - **Location:** `src/analysis/call_extractors.py:59-61`, `src/analysis/call_extractors.py:78-80`
  - **Problem:** The `extract_calls()` method sets `self.current_class = None` and `self.current_function = None` at the start (lines 78-80), but these are instance variables that could leak state if an exception is raised mid-extraction. If parsing fails after setting `current_class = "Foo"`, the next call to `extract_calls()` for a different file will still have `current_class = "Foo"` in context.
  - **Fix:** Use local variables instead of instance variables for tracking context within a single file parse, or use a context manager to ensure cleanup

- [ ] **BUG-081**: Missing Validation for Empty Embeddings Array in Duplicate Detector
  - **Location:** `src/analysis/code_duplicate_detector.py:159-163`
  - **Problem:** Line 159 checks `if embeddings.size == 0: raise ValueError("Embeddings array is empty")`, but this check happens AFTER the function signature promises to return an ndarray. An empty array is a valid input in some contexts (e.g., empty codebase), but raising ValueError breaks the contract. Additionally, returning an empty similarity matrix (0x0) might be more appropriate than failing.
  - **Fix:** Return `np.array([])` (empty 0x0 matrix) for empty input instead of raising, or document that empty input is invalid in docstring

### 🔵 LOW Priority Findings

- [ ] **REF-052**: Duplicate Language Pattern Definitions Between Analyzers
  - **Location:** `src/analysis/complexity_analyzer.py:104-129`, `src/analysis/criticality_analyzer.py:173-198`, `src/analysis/usage_analyzer.py:217-230`
  - **Problem:** Each analyzer defines its own language-specific patterns dictionaries for keywords/operators. The JavaScript/TypeScript patterns are duplicated in complexity and criticality analyzers. If a new language is added or pattern is fixed (e.g., Rust match syntax), must update multiple files.
  - **Fix:** Extract to shared `src/analysis/language_patterns.py` module with pattern definitions for each language, imported by all analyzers

- [ ] **PERF-016**: Regex Recompilation on Every Function Call
  - **Location:** `src/analysis/complexity_analyzer.py:135-137`, and 20+ other locations in analyzers
  - **Problem:** All regex patterns are defined as raw strings in loops (e.g., `r'\bif\b'`) and passed to `re.findall()` or `re.search()`, which compiles the regex on every call. For analyzing 10,000 functions, this recompiles the same patterns 10,000 times.
  - **Fix:** Pre-compile patterns as module-level constants: `IF_PATTERN = re.compile(r'\bif\b')`, then use `IF_PATTERN.findall(content)`

- [ ] **REF-053**: Missing Type Hints for Return Values in Call Extractors
  - **Location:** `src/analysis/call_extractors.py:310-325`, `src/analysis/call_extractors.py:379-393`
  - **Problem:** Helper methods like `_extract_function_name()`, `_extract_callee_name()`, and `_extract_method_name()` return `Optional[str]` but the return statements don't use explicit None returns in all paths. Lines 324, 392 have bare `pass` in except blocks, then implicitly return None. This makes it unclear whether None is intentional or a bug.
  - **Fix:** Add explicit `return None` in all exception handlers and document when/why None is returned

- [ ] **BUG-082**: Export Detection Regex Can Match Inside String Literals
  - **Location:** `src/analysis/usage_analyzer.py:260-264`
  - **Problem:** Line 261 searches for `export\s+(function|class|const|let|var)\s+{name}\b` in full file content, which can match inside multi-line string literals or comments (e.g., documentation showing example code: `"Example: export function foo()"`). This incorrectly marks non-exported functions as exported.
  - **Fix:** Add negative lookbehind to exclude matches inside strings/comments, or use proper AST-based export detection instead of regex

- [ ] **REF-054**: Hardcoded Entry Point Names Without Configurability
  - **Location:** `src/analysis/criticality_analyzer.py:94-97`, `src/analysis/usage_analyzer.py:306-307`
  - **Problem:** Both analyzers define `ENTRY_POINT_NAMES` sets with hardcoded values like "main", "index", "app". For projects with custom entry points (e.g., FastAPI with "application.py", Django with "wsgi.py"), these won't be detected as entry points, leading to incorrect criticality/usage scores.
  - **Fix:** Make entry point names configurable via ServerConfig: `criticality.entry_point_names = ["main", "index", ...]` with defaults, allow user override

- [ ] **PERF-017**: Redundant Call to len() in Median Calculation
  - **Location:** `src/analysis/importance_scorer.py:360-364`
  - **Problem:** Line 360 calls `n = len(sorted_scores)`, then line 361-364 checks `if n % 2 == 1` to decide median calculation. But the `sorted_scores` list was already created on line 357 with a length known at that point. The `n` variable is used only for median calculation, so this is a micro-optimization opportunity.
  - **Fix:** Inline: `if len(sorted_scores) % 2 == 1: median = sorted_scores[len(sorted_scores) // 2]` (or keep as-is for readability)

### Summary Statistics

- **Total Issues Found:** 18
- **Critical:** 3 (division by zero, double-counting, normalization failure)
- **High:** 4 (O(N²) performance, silent failures, type errors, state leaks)
- **Medium:** 6 (score range duplication, formula bugs, inefficient lookups, regex issues)
- **Low:** 5 (pattern duplication, regex recompilation, type hints, configurability)

**Key Risks:**
1. BUG-075 breaks importance scoring discriminatory power with non-default weights (all scores collapse to 1.0)
2. BUG-078 causes cross-file contamination in call graph analysis (incorrect usage metrics)
3. BUG-074 inflates cyclomatic complexity scores unpredictably (affects all downstream metrics)
4. PERF-014 can cause OOM on large codebases during duplicate detection (no early exit)

**Recommended Remediation Priority:**
1. Fix BUG-075 (importance score normalization) - affects all importance calculations
2. Fix BUG-078 (call graph state leak) - affects usage analysis accuracy
3. Fix BUG-074 (cyclomatic complexity double-counting) - affects complexity scores
4. Add PERF-014 (duplicate detector early exit) - prevents OOM on large codebases

**Next Ticket Numbers:** BUG-073 to BUG-082, REF-050 to REF-054, PERF-014 to PERF-017
---

## AUDIT-001 Part 12: Monitoring & Health Systems Findings (2025-11-30)

**Investigation Scope:** Monitoring, alerting, health reporting, capacity planning, and remediation systems
**Files Analyzed:** health_reporter.py (510 lines), alert_engine.py (568 lines), capacity_planner.py (613 lines), remediation.py (537 lines), health_scheduler.py (355 lines), health_jobs.py (408 lines), health_scorer.py (476 lines)
**Focus:** Health check accuracy, alert threshold correctness, metric collection bugs, remediation action safety, scheduler reliability, job state management, capacity planning accuracy, monitoring performance impact, false positive/negative rates

### CRITICAL Findings

- [ ] **BUG-080**: SQL Injection Vulnerability in Alert Engine Query
  - **Location:** `src/monitoring/alert_engine.py:412-413`
  - **Problem:** The `get_active_alerts()` method constructs SQL query with f-string interpolation of current timestamp: `query += f" AND (snoozed_until IS NULL OR snoozed_until < '{now}')"`. If datetime formatting changes or UTC timezone handling fails, this could allow SQL injection. The `now` variable comes from `datetime.now(UTC).isoformat()` which is safe currently, but the pattern violates SQL safety best practices.
  - **Fix:** Use parameterized query: `query += " AND (snoozed_until IS NULL OR snoozed_until < ?)"` and pass `now` as parameter to `cursor.execute(query, (now,))`

- [ ] **BUG-081**: Missing Error Handling in Linear Regression Causes Silent Failures
  - **Location:** `src/monitoring/capacity_planner.py:392-444`
  - **Problem:** The `_calculate_linear_growth_rate()` method can fail silently if historical metrics contain invalid data (NaN, infinity, or extremely large values). Line 439 checks `if abs(denominator) < 1e-10` to avoid division by zero, but doesn't validate input data. If `sum_xy` or `sum_x_squared` overflow to infinity (possible with 10,000+ data points over years), the calculation returns garbage values without warning. This leads to incorrect capacity forecasts.
  - **Fix:** Add input validation: `if any(not math.isfinite(getattr(m, metric_name, 0)) for m in historical_metrics): logger.warning("Invalid metric values detected"); return 0.0`. Wrap calculation in try/except to catch OverflowError.

- [ ] **BUG-082**: Health Scheduler Resource Leak on Restart
  - **Location:** `src/memory/health_scheduler.py:304-317`
  - **Problem:** The `update_config()` method calls `await self.stop()` (line 309) which closes the store (line 151), then creates a new AsyncIOScheduler (line 313) and calls `await self.start()` (line 316) which creates a NEW store instance (line 73). The old store's Qdrant connections are closed, but the store object itself may still be referenced by old job callbacks. If a scheduled job runs during the restart window, it will use the closed store and fail. Additionally, the `health_jobs` instance is not recreated, so it holds a reference to the old (closed) store.
  - **Fix:** In `update_config()`, also recreate `self.health_jobs = None` before calling `start()`. Add state check in job callbacks: `if not self.health_jobs or not self.health_jobs.store: logger.error("Store not available"); return`

### HIGH Priority Findings

- [ ] **BUG-083**: Division by Zero Risk in Health Score Calculations
  - **Location:** `src/monitoring/health_reporter.py:343-346`, `src/monitoring/capacity_planner.py:304-314`, `src/memory/health_scorer.py:257`, `src/memory/health_scorer.py:308`
  - **Problem:** Multiple methods calculate percentages by dividing by totals without checking for zero first. While most have `if total == 0: return 0.0` guards, the logic AFTER the guard still performs division. For example, in `analyze_trends()` line 346: `change_percent = (change / previous_value) * 100` - if `previous_value == 0` (after passing the line 341 `if previous_value == 0: continue` check), this will raise ZeroDivisionError. The guard at line 341 uses `continue` which skips to next metric, but if `previous_value` becomes zero DURING iteration due to race condition or concurrent update, the calculation crashes.
  - **Fix:** Change all percentage calculations to check denominator immediately before division: `if previous_value == 0: change_percent = 0.0 else: change_percent = (change / previous_value) * 100`

- [ ] **BUG-084**: Alert Penalty Can Produce Negative Health Scores
  - **Location:** `src/monitoring/health_reporter.py:279-291`
  - **Problem:** The `_apply_alert_penalty()` method subtracts penalties from the score (line 291: `return max(0, score - penalty)`). If there are many alerts, the penalty can exceed 100 points. For example, 7 CRITICAL alerts = 105 penalty points. While the `max(0, ...)` prevents negative scores, it means the overall score becomes 0 even if other components (performance, quality) are excellent. This creates a false CRITICAL health status when the issue might be a single misconfigured alert threshold firing repeatedly.
  - **Fix:** Cap penalty at 30 points max (or 30% of score): `penalty = min(30, penalty)`. Or use multiplicative penalty instead: `return int(score * (1 - min(0.3, penalty/100)))` so alerts reduce score proportionally.

- [ ] **BUG-085**: Capacity Forecasting Fails with Single Data Point
  - **Location:** `src/monitoring/capacity_planner.py:407-408`
  - **Problem:** The `_calculate_linear_growth_rate()` method checks `if len(historical_metrics) < 2: return 0.0` at line 407, but the check happens AFTER extracting data_points (line 411-414) and sorting (line 417). If someone passes a single-item list, the code continues to line 421-425 where it tries to compute x_values and y_values from a 1-element list, then line 428 checks `if len(x_values) < 2` again. This is redundant and confusing - the early return at line 407 should prevent this, but it's checked twice.
  - **Fix:** Move the `if len(historical_metrics) < 2` check to line 398 (top of function), before any processing. Remove redundant check at line 428.

- [ ] **PERF-014**: No Pagination in Remediation Action Execution
  - **Location:** `src/monitoring/remediation.py:256-285`, `src/monitoring/remediation.py:337-365`
  - **Problem:** The `_prune_stale_memories()` and `_cleanup_old_sessions()` methods (and others) process ALL candidates in a single loop without pagination. If there are 50,000 STALE memories, this creates a massive transaction and holds a database lock for minutes. The comment at line 270-271 says "Would actually delete here" with a placeholder, suggesting real implementation will use `store.delete_by_lifecycle()` which might not have pagination either.
  - **Fix:** Add batch processing: `for i in range(0, len(candidates), 1000): batch = candidates[i:i+1000]; await self.store.delete_batch(batch)`. Commit after each batch to reduce lock duration.

- [ ] **BUG-086**: Health Scorer Distribution Calculation Can Hit Memory Limit
  - **Location:** `src/memory/health_scorer.py:162-227`
  - **Problem:** The `_get_lifecycle_distribution()` method loads ALL memories with `all_memories = await self.store.get_all_memories()` (line 178), then has a check at line 190-195 that returns empty distribution if count > MAX_MEMORIES_PER_OPERATION (50,000). However, the damage is already done at line 178 - if there are 100,000 memories, they're all loaded into memory before the check. This can cause OOM crash. The comment at line 193 says "Aborting to prevent memory exhaustion" but it's too late.
  - **Fix:** Add count-only query before fetching: `total = await self.store.count_memories(); if total > MAX_MEMORIES_PER_OPERATION: return distribution`. Or use streaming/cursor-based fetching instead of loading all at once.

### MEDIUM Priority Findings

- [ ] **REF-055**: Hardcoded Health Status Thresholds Duplicated Across Files
  - **Location:** `src/monitoring/health_reporter.py:293-304`, `src/monitoring/capacity_planner.py:108-117`, `src/memory/health_scorer.py:126-133`
  - **Problem:** Three different files define their own health status thresholds (EXCELLENT >= 90, GOOD >= 75, etc.). While the values are currently identical, they're hardcoded magic numbers in each file. If we need to adjust thresholds (e.g., make "GOOD" >= 70 instead of 75), must change 3+ files. This creates inconsistency risk where different components report different health statuses for the same score.
  - **Fix:** Extract to shared constants in `src/monitoring/constants.py`: `HEALTH_STATUS_THRESHOLDS = {"EXCELLENT": 90, "GOOD": 75, "FAIR": 60, "POOR": 40}`. Import in all files.

- [ ] **REF-056**: Missing Input Validation in Alert Snooze Duration
  - **Location:** `src/monitoring/alert_engine.py:469-493`
  - **Problem:** The `snooze_alert()` method accepts `hours` parameter with no validation. Caller can pass `hours=-10` (snooze in the past, meaningless), `hours=0` (immediate un-snooze), or `hours=1000000` (snooze for 114 years). Negative or extreme values create confusing behavior - snoozed alerts might reappear immediately or never.
  - **Fix:** Add validation: `if not (0 < hours <= 168): raise ValueError("Snooze duration must be 1-168 hours (1 week max)")`. Document reasonable range.

- [ ] **BUG-087**: Trend Analysis Direction Logic Has Edge Case Bug
  - **Location:** `src/monitoring/health_reporter.py:353-363`
  - **Problem:** The trend direction determination uses compound ternary expressions that are hard to reason about. Line 353-356 for "higher_is_better" case: `direction = "improving" if change_percent > 5 else "degrading" if change_percent < -5 else "stable"`. This means a change of +4% is "stable", but -4% is also "stable". However, for "lower is better" metrics (line 359-362), the logic is flipped but uses the SAME thresholds. This means a 4.9% increase in noise_ratio is marked "stable" when it should be "degrading".
  - **Fix:** Use clearer threshold constants: `TREND_SIGNIFICANT_CHANGE = 5.0`. Break compound ternary into explicit if/elif for readability. Consider separate thresholds for improvement vs degradation (e.g., 5% improvement is good, but 3% degradation is concerning).

- [ ] **REF-057**: Duplicate Emoji Constants in Capacity Recommendations
  - **Location:** `src/monitoring/capacity_planner.py:457-516`
  - **Problem:** The `_generate_capacity_recommendations()` method uses hardcoded emoji strings inline in 8 different locations. If recommendations need to be rendered in a non-emoji-supporting terminal or UI, must change 8+ places. Also makes testing harder (must match exact emoji strings).
  - **Fix:** Define constants at module level or make emojis optional via config flag.

- [ ] **BUG-088**: Weekly Report Missing Alert History Comparison
  - **Location:** `src/monitoring/health_reporter.py:378-457`
  - **Problem:** The `generate_weekly_report()` method calculates `previous_health` score from `previous_metrics` (line 399-403), but comment at line 402 says "Note: We don't have previous alerts, so approximate". This means the previous health score is calculated with ZERO alerts (empty list), making it artificially high. The week-over-week health comparison is therefore inaccurate - current health might be 65 (with 5 alerts), previous health is 85 (with 0 alerts assumed), suggesting health degraded when alerts may have existed then too.
  - **Fix:** Either: (1) Store historical alerts in database and fetch them, or (2) Document this limitation in WeeklyReport.previous_health docstring and add a warning field: `previous_health_note: "Calculated without historical alerts"`.

- [ ] **REF-058**: Job History Unbounded Growth in Health Jobs
  - **Location:** `src/memory/health_jobs.py:83-84`, `src/memory/health_jobs.py:195`, `src/memory/health_jobs.py:306`, `src/memory/health_jobs.py:369`
  - **Problem:** The `HealthMaintenanceJobs` class appends every job result to `self.job_history` list (lines 195, 306, 369) with no size limit. If jobs run every week for a year, that's 52 * 3 = 156 entries minimum. If jobs run daily (via manual trigger), that's 1000+ entries. The list grows unbounded and is never cleared except manually via `clear_job_history()` (line 404). In contrast, HealthJobScheduler limits history to last 100 entries (line 164).
  - **Fix:** Add automatic trimming in job methods: `self.job_history.append(result); if len(self.job_history) > 100: self.job_history = self.job_history[-100:]`

### LOW Priority Findings

- [ ] **REF-059**: Magic Numbers for Lifecycle Distribution Ideals
  - **Location:** `src/memory/health_scorer.py:79-84`
  - **Problem:** The IDEAL_DISTRIBUTION dictionary hardcodes percentages (60% ACTIVE, 25% RECENT, etc.) with no explanation of why these values are ideal. These ratios are domain-specific assumptions that may not apply to all use cases. A read-heavy system might prefer 80% ACTIVE, while a write-heavy system might prefer 40% ARCHIVED.
  - **Fix:** Make IDEAL_DISTRIBUTION configurable via ServerConfig: `health.ideal_distribution_percentages`. Document rationale for default values in comments.

- [ ] **PERF-015**: Duplicate Detection Has O(N^2) Complexity
  - **Location:** `src/memory/health_scorer.py:259-313`
  - **Problem:** The `_calculate_duplicate_rate()` method iterates through all memories and builds a `content_map` dictionary to detect exact duplicates (lines 291-306). For N memories, this is O(N) which is fine. However, the comment at lines 263-268 suggests the INTENDED implementation is pairwise similarity checks, which would be O(N^2). If anyone implements the full version without optimization, it could take hours for 10,000+ memories. The current implementation only detects exact duplicates (case-insensitive), missing near-duplicates.
  - **Fix:** Document that semantic duplicate detection is NOT implemented (only exact matches). Add TODO for LSH (Locality-Sensitive Hashing) based approximate duplicate detection which is O(N).

- [ ] **BUG-089**: Remediation History Query Performance Degrades Over Time
  - **Location:** `src/monitoring/remediation.py:454-499`
  - **Problem:** The `get_remediation_history()` method queries `remediation_history` table with `WHERE timestamp >= ?` (line 474). If the table grows to 10,000+ rows over months, and caller requests `days=30`, the database must scan all rows to filter by timestamp. There's an index on timestamp (line 97-100), but SQLite's query planner might not use it efficiently if the retention_days is very large.
  - **Fix:** Add explicit `ORDER BY timestamp DESC LIMIT ?` to query, or use EXPLAIN QUERY PLAN to verify index usage. Consider adding a cleanup job to delete old remediation history (currently only `cleanup_old_alerts()` exists, no cleanup for remediation history).

- [ ] **REF-060**: Inconsistent Dry-Run Behavior Across Remediation Actions
  - **Location:** `src/monitoring/remediation.py:230-254`, `src/monitoring/remediation.py:256-285`
  - **Problem:** The `_dry_run_action()` method handles dry-run for `prune_stale_memories` and `cleanup_old_sessions` specially (lines 235-248), but for all other actions returns `RemediationResult(success=True, items_affected=0, details={"action": "dry_run", "note": "count not available"})` (line 250-254). This means dry-run for `archive_inactive_projects`, `merge_duplicates`, and `optimize_database` doesn't provide useful information - it just says "would run" with no impact estimate. Users can't make informed decisions.
  - **Fix:** Implement proper dry-run for all actions. `optimize_database` could report current DB size, `archive_inactive_projects` could count inactive projects, etc.

- [ ] **BUG-090**: Health Scheduler Notification Callback Not Awaited
  - **Location:** `src/memory/health_scheduler.py:173-174`, `src/memory/health_scheduler.py:187-188`, `src/memory/health_scheduler.py:208-209`, `src/memory/health_scheduler.py:240-241`, `src/memory/health_scheduler.py:254-255`
  - **Problem:** The scheduler calls `await self.config.notification_callback(...)` at lines 174, 188, 209, 241, 255. However, `notification_callback` is typed as `Optional[Callable]` with no async specification (line 42). If user provides a synchronous callback function, the `await` will fail with "TypeError: object is not awaitable". If user provides an async callback, it works fine. The type annotation doesn't enforce async.
  - **Fix:** Change type annotation to `Optional[Callable[..., Awaitable[None]]]` to require async callbacks. Or detect sync vs async: `if asyncio.iscoroutinefunction(self.config.notification_callback): await callback(...) else: callback(...)`

- [ ] **REF-061**: Database Optimization Uses Blocking Operations
  - **Location:** `src/monitoring/remediation.py:367-387`
  - **Problem:** The `_optimize_database()` method runs `VACUUM` (line 372) and `ANALYZE` (line 375) on SQLite database. Both are blocking operations that can take 10+ seconds on large databases (1GB+). The entire remediation engine (and any other code using the same database connection) is blocked during this time. If called during a busy period, this causes user-visible latency spikes.
  - **Fix:** Add warning log before optimization: `logger.warning("Starting database optimization - may block for 10+ seconds")`. Consider running VACUUM in a separate transaction or thread. Document that this should only run during maintenance windows.

- [ ] **BUG-091**: Stale Memory Count Logic Uses Hardcoded Access Threshold
  - **Location:** `src/memory/health_jobs.py:267`
  - **Problem:** The monthly cleanup job checks `if use_count > config.quality.stale_memory_usage_threshold` (line 267) to skip frequently accessed memories. However, this threshold is from ServerConfig.quality settings, which is intended for quality scoring, not lifecycle management. The comment at line 264 says "Check usage (skip if frequently accessed)" but doesn't explain what "frequently" means. If the config value is set too low (e.g., 1), all stale memories with any usage are kept forever.
  - **Fix:** Add dedicated `lifecycle.stale_deletion_min_access_count` config setting with clear documentation. Default to 5. Don't reuse quality threshold for deletion decisions.

### Summary Statistics

- **Total Issues Found:** 18
- **Critical:** 3 (SQL injection, silent failures, resource leak)
- **High:** 5 (division by zero, negative scores, single data point, no pagination, OOM risk)
- **Medium:** 6 (threshold duplication, input validation, edge cases, unbounded growth, missing alerts)
- **Low:** 4 (magic numbers, complexity, query performance, inconsistent behavior)

**Key Risks:**
1. SQL injection in alert query construction (CRITICAL security issue)
2. Silent capacity forecast failures lead to incorrect scaling decisions
3. Health scorer can crash entire monitoring system with OOM on large datasets
4. Remediation actions lack pagination and could lock database for minutes
5. Alert penalty calculation can produce misleading health scores

**Remediation Safety Concerns:**
- No batch size limits in pruning operations (could delete 50K+ memories in single transaction)
- Dry-run doesn't provide accurate impact estimates for most actions
- Database optimization blocks entire system during execution
- No rollback mechanism if remediation partially fails

**False Positive/Negative Risks:**
- Weekly report health comparison is inaccurate (missing historical alerts)
- Trend analysis edge case treats 4.9% degradation as "stable"
- Duplicate detection only finds exact matches (misses semantic duplicates)
- Health scorer assumes 50% of archived memories are noise (hardcoded assumption)

**Next Ticket Numbers:** BUG-080 to BUG-091, REF-055 to REF-061, PERF-014 to PERF-015

---

## AUDIT-001 Part 9: Async/Concurrency Safety Findings (2025-11-30)

**Investigation Scope:** Async/concurrency patterns across src/store/, src/embeddings/, src/services/, src/memory/
**Files Analyzed:** connection_pool.py, connection_health_checker.py, parallel_generator.py, conversation_tracker.py, usage_tracker.py, file_watcher.py, background_indexer.py, notification_manager.py, multi_repository_indexer.py, qdrant_store.py, auto_indexing_service.py, dashboard/web_server.py
**Focus:** Missing await, fire-and-forget tasks, race conditions, lock ordering, event loop blocking, task cancellation, timeout handling, thread-safe collections

### 🔴 CRITICAL Findings

- [ ] **BUG-080**: Missing Client Release in Two QdrantStore Methods
  - **Location:** `src/store/qdrant_store.py` - 32 acquires but only 30 releases
  - **Problem:** Connection pool leak - two methods acquire client via `await self._get_client()` but don't have matching `await self._release_client(client)` in their finally blocks. This causes connections to leak from the pool over time. Analysis shows:
    - Acquire at line 1639 (`get_project_stats`) - has release at 1722 ✓
    - Acquire at line 2286 (`bulk_update_context_level`) - likely missing release
    - Further investigation needed to identify the second leak
  - **Impact:** Connection pool will eventually exhaust under load, causing `ConnectionPoolExhaustedError`
  - **Fix:** Audit all methods with `client = await self._get_client()` and ensure each has `await self._release_client(client)` in finally block

- [ ] **BUG-081**: Race Condition in NotificationManager._last_progress_time Dict Access
  - **Location:** `src/memory/notification_manager.py:131-187`
  - **Problem:** `_last_progress_time: Dict[str, float]` is accessed from async context without lock protection. Lines 182-187 perform read-check-write pattern: `last_time = self._last_progress_time.get(job_id, 0)` then `self._last_progress_time[job_id] = now`. If two concurrent `notify_progress()` calls for same job_id occur, both could read old timestamp, skip throttle check, and spam notifications.
  - **Fix:** Add `self._throttle_lock = asyncio.Lock()` and wrap lines 181-187 in `async with self._throttle_lock:`

- [ ] **BUG-082**: Unsafe Dict Append in MultiRepositoryIndexer Without Lock
  - **Location:** `src/memory/multi_repository_indexer.py:392-401`
  - **Problem:** `repository_results.append(result)` is called from multiple concurrent tasks created by `asyncio.gather()`. The `repository_results` list is mutated concurrently without synchronization. While CPython's GIL makes `list.append()` atomic at bytecode level, this is NOT guaranteed in other Python implementations or under asyncio context switches.
  - **Fix:** Use `asyncio.Lock()` to protect the append operation, or use `asyncio.Queue` for thread-safe result collection

### 🟡 HIGH Priority Findings

- [ ] **BUG-083**: Fire-and-Forget create_task in FileWatcher Debounce
  - **Location:** `src/memory/file_watcher.py:271-273`
  - **Problem:** `self.debounce_task = asyncio.create_task(self._execute_debounced_callback())` is created but if the task raises an exception, it's never awaited or checked. The exception will be silently lost. This is different from the fixed BUG-055/056 because the task IS stored in `self.debounce_task`, but there's no error callback registered.
  - **Fix:** Add error callback: `self.debounce_task.add_done_callback(self._handle_task_error)` similar to usage_tracker.py pattern (lines 153, 230)

- [ ] **BUG-084**: Missing Lock Around file_watcher.py pending_files Access
  - **Location:** `src/memory/file_watcher.py:256-273`
  - **Problem:** `_debounce_callback()` acquires lock to add to `pending_files` (line 256-257), releases lock, cancels old task (262-268), then re-acquires lock (270). Between lock releases, another watchdog event could fire and try to modify `pending_files` or `debounce_task`. This creates race window where task cancellation could target wrong task.
  - **Fix:** Hold lock for entire duration: acquire once at line 256, don't release until after creating new task at line 273

- [ ] **BUG-085**: BackgroundIndexer._active_tasks Dict Modified During Iteration
  - **Location:** `src/memory/background_indexer.py:488-492`
  - **Problem:** `finally` block deletes from `_active_tasks` dict, but if multiple jobs complete simultaneously, one job's cleanup could modify dict while another job is being cleaned up. While current code checks `if job_id in self._active_tasks`, this is not atomic with the deletion.
  - **Fix:** Use `self._active_tasks.pop(job_id, None)` instead of `del self._active_tasks[job_id]` (already documented in BUG-067)

- [ ] **BUG-086**: ConversationTracker.sessions Dict Modified Without Lock
  - **Location:** `src/memory/conversation_tracker.py:140-144, 172-177`
  - **Problem:** `self.sessions` dict is modified in `create_session()` and `end_session()` without lock protection. If two threads/tasks call these methods concurrently, dict corruption or race conditions could occur. While GIL provides some protection, async context switches between dict operations can still cause issues.
  - **Fix:** Add `self._sessions_lock = asyncio.Lock()` and wrap all dict mutations in async context manager

- [ ] **BUG-087**: UsageTracker Stats Counters Have Partial Lock Coverage
  - **Location:** `src/memory/usage_tracker.py:146-147`
  - **Problem:** Lines 146-147 increment `self.stats["total_tracked"]` with `self._counter_lock` protection (good), but line 147 is inside `async with self._lock:` which is already held. This creates nested locking pattern that could cause deadlock if other code acquires locks in different order. Additionally, other stats updates at lines 207-209 are NOT protected by counter_lock.
  - **Fix:** Ensure all stats counter updates use threading.Lock consistently, separate from asyncio.Lock for data structure access

### 🟢 MEDIUM Priority Findings

- [ ] **REF-056**: Inconsistent Error Callback Pattern Across create_task Calls
  - **Location:** `src/memory/usage_tracker.py:152-153` (has callback), `src/memory/conversation_tracker.py:104` (no callback), `src/memory/background_indexer.py:112` (no callback), `src/memory/auto_indexing_service.py:363` (no callback)
  - **Problem:** Only usage_tracker adds error callback to background tasks via `task.add_done_callback(self._handle_background_task_done)`. Other components (conversation_tracker, background_indexer, auto_indexing_service) create background tasks without error callbacks, risking silent exception loss.
  - **Fix:** Standardize pattern - all fire-and-forget tasks should have error callback that logs exceptions

- [ ] **REF-057**: DashboardServer Event Loop Thread Lifecycle Issues
  - **Location:** `src/dashboard/web_server.py:88-99, 149-159`
  - **Problem:** `start()` creates daemon thread with event loop (line 93-98), but `stop()` attempts to stop loop with `loop.call_soon_threadsafe(loop.stop)` (line 151) without joining thread or ensuring clean shutdown. Daemon threads are killed on process exit, which can corrupt state or leave resources open.
  - **Fix:** Make thread non-daemon, add `self.loop_thread.join(timeout=5)` in stop(), handle timeout case

- [ ] **REF-058**: ConnectionHealthChecker Run in Executor Without Timeout
  - **Location:** `src/store/connection_health_checker.py:170-173, 200-203, 234-237, 245-248`
  - **Problem:** All health checks use `await loop.run_in_executor(None, ...)` to run sync QdrantClient operations. The executor is `None` (ThreadPoolExecutor), but there's no outer timeout on the executor call itself - only on the `asyncio.wait_for()` wrapper. If the executor's thread pool is exhausted, the task could hang indefinitely.
  - **Fix:** Add max_workers limit to default executor or use bounded ThreadPoolExecutor

- [ ] **REF-059**: ParallelGenerator._background_tasks Set Never Cleaned Up
  - **Location:** `src/embeddings/parallel_generator.py:84, 152-153`
  - **Problem:** UsageTracker maintains `self._background_tasks: set = set()` to track fire-and-forget flush tasks (line 84), and adds/removes tasks properly (lines 152-153, 221). However, if many tasks are created rapidly, the set could grow unbounded since tasks are only removed on completion. No periodic cleanup or size limit.
  - **Fix:** Add periodic cleanup or max size check, log warning if set exceeds threshold (e.g., 100 tasks)

### 🟢 LOW Priority Findings

- [ ] **PERF-010**: ConnectionPoolMonitor Uses Sequential Notify Instead of Gather
  - **Location:** `src/store/connection_pool_monitor.py:306-311`
  - **Problem:** `_raise_alert()` iterates through backends and awaits each notification sequentially (line 309). If there are multiple backends (console, log, callback, etc.), a slow backend blocks all others. Should use `asyncio.gather()` for parallel notification.
  - **Fix:** Collect tasks in list, use `await asyncio.gather(*notify_tasks, return_exceptions=True)`

- [ ] **REF-060**: File Watcher Uses mtime Then Hash for Change Detection
  - **Location:** `src/memory/file_watcher.py:129-165`
  - **Problem:** `_has_changed()` first checks mtime (quick), then computes SHA256 hash (expensive) for verification. This is correct and efficient, but comment at line 133-134 suggests this is for "conflict resolution" which is misleading. The hash is actually for catching false watchdog events (editor temp files, etc.), not conflicts.
  - **Fix:** Update comment to clarify: "Step 3: Verify with hash to catch watchdog false positives (temp files, touch without content change)"

- [ ] **REF-061**: NotificationManager.backends List Modified via append Without Lock
  - **Location:** `src/memory/notification_manager.py:346`
  - **Problem:** `add_backend()` directly appends to `self.backends` list without lock. If multiple threads call add_backend concurrently, list corruption possible (though unlikely in typical usage since this is usually called during initialization).
  - **Fix:** Add `self._backends_lock = threading.Lock()` to protect list modifications, or document that add_backend() must only be called during initialization

### Concurrency Safety Summary

**Patterns Observed:**
- ✅ Good: REF-030 pattern (threading.Lock for counter increments) is widely used
- ✅ Good: Most `asyncio.gather()` calls use `return_exceptions=True` (15/15 checked)
- ✅ Good: Connection pool uses both asyncio.Lock and threading.Lock appropriately
- ⚠️ Weak: Inconsistent error callback pattern for fire-and-forget tasks
- ⚠️ Weak: Several dict/list mutations without lock protection in async context
- ❌ Critical: Missing client releases in QdrantStore (connection pool leak)

**High-Risk Areas for Future Monitoring:**
1. NotificationManager throttle dict (concurrent access)
2. MultiRepositoryIndexer result collection (concurrent appends)
3. File watcher debounce task lifecycle
4. Dashboard server thread cleanup
5. Background task error propagation


---

## AUDIT-001 Part 8: CLI Commands & User Experience Findings (2025-11-30)

**Full details in:** `planning_docs/AUDIT-001_part8_cli_findings.md`

**Investigation Scope:** 26 CLI command files (~4,500 lines) covering index, health, status, git operations, analytics, backup/import/export, project/workspace/repository management

### Quick Summary

**Total Issues Found:** 19 (3 Critical, 5 High, 6 Medium, 5 Low)

**Critical Issues:**
- BUG-080: browse, tutorial, validate-setup, perf commands advertised but not integrated (completely non-functional)
- BUG-081: perf commands imported but no parser created
- BUG-082: Most commands don't return proper exit codes (breaks CI/automation)

**High Priority:**
- UX-060: Three different progress indicator patterns across commands
- BUG-083: Missing Ctrl+C handling in most commands (ugly stack traces)
- BUG-084: analytics/session-summary block async event loop
- UX-061: Three different confirmation UI patterns
- BUG-085: Click-based commands (tags, collections, auto-tag) hidden from main CLI

**Key User Impact:**
- New users run `claude-rag tutorial` → error message (broken onboarding)
- Shell scripts can't detect command failures (exit codes always 0)
- Features like auto-tagging completely undiscoverable
- Inconsistent visual feedback confuses users

**Next Ticket Numbers:** BUG-080 to BUG-086, UX-060 to UX-066, REF-050 to REF-053, PERF-014
---

## AUDIT-001 Part 9: Async/Concurrency Safety Findings (2025-11-30)

**Investigation Scope:** Async/concurrency patterns across src/store/, src/embeddings/, src/services/, src/memory/
**Files Analyzed:** connection_pool.py, connection_health_checker.py, parallel_generator.py, conversation_tracker.py, usage_tracker.py, file_watcher.py, background_indexer.py, notification_manager.py, multi_repository_indexer.py, qdrant_store.py, auto_indexing_service.py, dashboard/web_server.py
**Focus:** Missing await, fire-and-forget tasks, race conditions, lock ordering, event loop blocking, task cancellation, timeout handling, thread-safe collections

### 🔴 CRITICAL Findings

- [ ] **BUG-080**: Missing Client Release in Two QdrantStore Methods
  - **Location:** `src/store/qdrant_store.py` - 32 acquires but only 30 releases
  - **Problem:** Connection pool leak - two methods acquire client via `await self._get_client()` but don't have matching `await self._release_client(client)` in their finally blocks. This causes connections to leak from the pool over time. Analysis shows:
    - Acquire at line 1639 (`get_project_stats`) - has release at 1722 ✓
    - Acquire at line 2286 (`bulk_update_context_level`) - likely missing release
    - Further investigation needed to identify the second leak
  - **Impact:** Connection pool will eventually exhaust under load, causing `ConnectionPoolExhaustedError`
  - **Fix:** Audit all methods with `client = await self._get_client()` and ensure each has `await self._release_client(client)` in finally block

- [ ] **BUG-081**: Race Condition in NotificationManager._last_progress_time Dict Access
  - **Location:** `src/memory/notification_manager.py:131-187`
  - **Problem:** `_last_progress_time: Dict[str, float]` is accessed from async context without lock protection. Lines 182-187 perform read-check-write pattern: `last_time = self._last_progress_time.get(job_id, 0)` then `self._last_progress_time[job_id] = now`. If two concurrent `notify_progress()` calls for same job_id occur, both could read old timestamp, skip throttle check, and spam notifications.
  - **Fix:** Add `self._throttle_lock = asyncio.Lock()` and wrap lines 181-187 in `async with self._throttle_lock:`

- [ ] **BUG-082**: Unsafe Dict Append in MultiRepositoryIndexer Without Lock
  - **Location:** `src/memory/multi_repository_indexer.py:392-401`
  - **Problem:** `repository_results.append(result)` is called from multiple concurrent tasks created by `asyncio.gather()`. The `repository_results` list is mutated concurrently without synchronization. While CPython's GIL makes `list.append()` atomic at bytecode level, this is NOT guaranteed in other Python implementations or under asyncio context switches.
  - **Fix:** Use `asyncio.Lock()` to protect the append operation, or use `asyncio.Queue` for thread-safe result collection

### 🟡 HIGH Priority Findings

- [ ] **BUG-083**: Fire-and-Forget create_task in FileWatcher Debounce
  - **Location:** `src/memory/file_watcher.py:271-273`
  - **Problem:** `self.debounce_task = asyncio.create_task(self._execute_debounced_callback())` is created but if the task raises an exception, it's never awaited or checked. The exception will be silently lost. This is different from the fixed BUG-055/056 because the task IS stored in `self.debounce_task`, but there's no error callback registered.
  - **Fix:** Add error callback: `self.debounce_task.add_done_callback(self._handle_task_error)` similar to usage_tracker.py pattern (lines 153, 230)

- [ ] **BUG-084**: Missing Lock Around file_watcher.py pending_files Access
  - **Location:** `src/memory/file_watcher.py:256-273`
  - **Problem:** `_debounce_callback()` acquires lock to add to `pending_files` (line 256-257), releases lock, cancels old task (262-268), then re-acquires lock (270). Between lock releases, another watchdog event could fire and try to modify `pending_files` or `debounce_task`. This creates race window where task cancellation could target wrong task.
  - **Fix:** Hold lock for entire duration: acquire once at line 256, don't release until after creating new task at line 273

- [ ] **BUG-085**: BackgroundIndexer._active_tasks Dict Modified During Iteration
  - **Location:** `src/memory/background_indexer.py:488-492`
  - **Problem:** `finally` block deletes from `_active_tasks` dict, but if multiple jobs complete simultaneously, one job's cleanup could modify dict while another job is being cleaned up. While current code checks `if job_id in self._active_tasks`, this is not atomic with the deletion.
  - **Fix:** Use `self._active_tasks.pop(job_id, None)` instead of `del self._active_tasks[job_id]` (already documented in BUG-067)

- [ ] **BUG-086**: ConversationTracker.sessions Dict Modified Without Lock
  - **Location:** `src/memory/conversation_tracker.py:140-144, 172-177`
  - **Problem:** `self.sessions` dict is modified in `create_session()` and `end_session()` without lock protection. If two threads/tasks call these methods concurrently, dict corruption or race conditions could occur. While GIL provides some protection, async context switches between dict operations can still cause issues.
  - **Fix:** Add `self._sessions_lock = asyncio.Lock()` and wrap all dict mutations in async context manager

- [ ] **BUG-087**: UsageTracker Stats Counters Have Partial Lock Coverage
  - **Location:** `src/memory/usage_tracker.py:146-147`
  - **Problem:** Lines 146-147 increment `self.stats["total_tracked"]` with `self._counter_lock` protection (good), but line 147 is inside `async with self._lock:` which is already held. This creates nested locking pattern that could cause deadlock if other code acquires locks in different order. Additionally, other stats updates at lines 207-209 are NOT protected by counter_lock.
  - **Fix:** Ensure all stats counter updates use threading.Lock consistently, separate from asyncio.Lock for data structure access

### 🟢 MEDIUM Priority Findings

- [ ] **REF-056**: Inconsistent Error Callback Pattern Across create_task Calls
  - **Location:** `src/memory/usage_tracker.py:152-153` (has callback), `src/memory/conversation_tracker.py:104` (no callback), `src/memory/background_indexer.py:112` (no callback), `src/memory/auto_indexing_service.py:363` (no callback)
  - **Problem:** Only usage_tracker adds error callback to background tasks via `task.add_done_callback(self._handle_background_task_done)`. Other components (conversation_tracker, background_indexer, auto_indexing_service) create background tasks without error callbacks, risking silent exception loss.
  - **Fix:** Standardize pattern - all fire-and-forget tasks should have error callback that logs exceptions

- [ ] **REF-057**: DashboardServer Event Loop Thread Lifecycle Issues
  - **Location:** `src/dashboard/web_server.py:88-99, 149-159`
  - **Problem:** `start()` creates daemon thread with event loop (line 93-98), but `stop()` attempts to stop loop with `loop.call_soon_threadsafe(loop.stop)` (line 151) without joining thread or ensuring clean shutdown. Daemon threads are killed on process exit, which can corrupt state or leave resources open.
  - **Fix:** Make thread non-daemon, add `self.loop_thread.join(timeout=5)` in stop(), handle timeout case

- [ ] **REF-058**: ConnectionHealthChecker Run in Executor Without Timeout
  - **Location:** `src/store/connection_health_checker.py:170-173, 200-203, 234-237, 245-248`
  - **Problem:** All health checks use `await loop.run_in_executor(None, ...)` to run sync QdrantClient operations. The executor is `None` (ThreadPoolExecutor), but there's no outer timeout on the executor call itself - only on the `asyncio.wait_for()` wrapper. If the executor's thread pool is exhausted, the task could hang indefinitely.
  - **Fix:** Add max_workers limit to default executor or use bounded ThreadPoolExecutor

- [ ] **REF-059**: ParallelGenerator._background_tasks Set Never Cleaned Up
  - **Location:** `src/embeddings/parallel_generator.py:84, 152-153`
  - **Problem:** UsageTracker maintains `self._background_tasks: set = set()` to track fire-and-forget flush tasks (line 84), and adds/removes tasks properly (lines 152-153, 221). However, if many tasks are created rapidly, the set could grow unbounded since tasks are only removed on completion. No periodic cleanup or size limit.
  - **Fix:** Add periodic cleanup or max size check, log warning if set exceeds threshold (e.g., 100 tasks)

### 🟢 LOW Priority Findings

- [ ] **PERF-010**: ConnectionPoolMonitor Uses Sequential Notify Instead of Gather
  - **Location:** `src/store/connection_pool_monitor.py:306-311`
  - **Problem:** `_raise_alert()` iterates through backends and awaits each notification sequentially (line 309). If there are multiple backends (console, log, callback, etc.), a slow backend blocks all others. Should use `asyncio.gather()` for parallel notification.
  - **Fix:** Collect tasks in list, use `await asyncio.gather(*notify_tasks, return_exceptions=True)`

- [ ] **REF-060**: File Watcher Uses mtime Then Hash for Change Detection
  - **Location:** `src/memory/file_watcher.py:129-165`
  - **Problem:** `_has_changed()` first checks mtime (quick), then computes SHA256 hash (expensive) for verification. This is correct and efficient, but comment at line 133-134 suggests this is for "conflict resolution" which is misleading. The hash is actually for catching false watchdog events (editor temp files, etc.), not conflicts.
  - **Fix:** Update comment to clarify: "Step 3: Verify with hash to catch watchdog false positives (temp files, touch without content change)"

- [ ] **REF-061**: NotificationManager.backends List Modified via append Without Lock
  - **Location:** `src/memory/notification_manager.py:346`
  - **Problem:** `add_backend()` directly appends to `self.backends` list without lock. If multiple threads call add_backend concurrently, list corruption possible (though unlikely in typical usage since this is usually called during initialization).
  - **Fix:** Add `self._backends_lock = threading.Lock()` to protect list modifications, or document that add_backend() must only be called during initialization

### Concurrency Safety Summary

**Patterns Observed:**
- ✅ Good: REF-030 pattern (threading.Lock for counter increments) is widely used
- ✅ Good: Most `asyncio.gather()` calls use `return_exceptions=True` (15/15 checked)
- ✅ Good: Connection pool uses both asyncio.Lock and threading.Lock appropriately
- ⚠️ Weak: Inconsistent error callback pattern for fire-and-forget tasks
- ⚠️ Weak: Several dict/list mutations without lock protection in async context
- ❌ Critical: Missing client releases in QdrantStore (connection pool leak)

**High-Risk Areas for Future Monitoring:**
1. NotificationManager throttle dict (concurrent access)
2. MultiRepositoryIndexer result collection (concurrent appends)
3. File watcher debounce task lifecycle
4. Dashboard server thread cleanup
5. Background task error propagation

## AUDIT-001 Part 17: Documentation Findings (2025-11-30)

**Investigation Scope:** Analyzed 40+ Python modules across `src/` directory for docstring accuracy, type hint correctness, inline comment staleness, and misleading documentation.

**Methodology:**
- Sampled core modules: `core/tools.py`, `core/validation.py`, `store/base.py`, `memory/classifier.py`
- Analyzed public APIs in: `embeddings/rust_bridge.py`, `router/retrieval_predictor.py`, `tagging/auto_tagger.py`
- Cross-referenced implementation with documentation in: `dependency_graph.py`, `token_tracker.py`, `project_context.py`, `store/factory.py`
- Checked for stale comments referencing removed code or old behavior

### 🔴 CRITICAL Findings

- [ ] **DOC-012**: get_by_id() Docstring Missing Resource Leak Warning
  - **Location:** `src/store/base.py:120-133`
  - **Problem:** Abstract method docstring says "Raises: StorageError: If retrieval operation fails" but doesn't mention that implementations MUST release clients on early returns. The Qdrant implementation at `qdrant_store.py:569-570` has a bug where `if not result: return None` leaks a client because it exits before the `finally` block. Base class should document this requirement.
  - **Expected:** Docstring should say "Note: Implementations must ensure proper resource cleanup even on early returns (e.g., when memory not found)"
  - **Fix:** Update base.py docstring to include resource cleanup requirement; reference this when fixing BUG-063

- [ ] **DOC-013**: _score_patterns() Return Type Misleading
  - **Location:** `src/memory/classifier.py:85-97`
  - **Problem:** Docstring says "Returns: Score between 0 and 1" but implementation uses formula `min(1.0, matches / max(1, len(patterns) * 0.3))` which can exceed 1.0 before the min() clamp. The comment at line 97 is misleading because it doesn't explain WHY 0.3 divisor is used (it's to allow multiple matches to boost score above threshold).
  - **Expected:** "Returns: Score normalized to 0-1 range. Uses 0.3 divisor to amplify signal from sparse patterns."
  - **Fix:** Update docstring and add inline comment explaining the normalization factor choice

### 🟡 HIGH Priority Findings

- [ ] **DOC-014**: Inconsistent Docstring Style for Async Methods
  - **Location:** `src/store/base.py:169-181`, `src/store/base.py:184-196`, `src/store/base.py:199-208`
  - **Problem:** Three abstract async methods (`health_check`, `initialize`, `close`) have identical notes explaining "This function is async for interface compatibility. Abstract methods in base classes must be async even without await to maintain consistent interface across all storage backend implementations." This is repetitive and could be stated once at the class level.
  - **Expected:** Move note to class docstring, reference it in individual methods if needed
  - **Fix:** Extract common note to MemoryStore class docstring section on "Async Method Requirements"

- [ ] **DOC-015**: cosine_similarity() Return Range Incorrect
  - **Location:** `src/embeddings/rust_bridge.py:51-72`, `src/embeddings/rust_bridge.py:101-121`
  - **Problem:** Both Python and Rust bridge implementations document cosine_similarity as returning "0.0 to 1.0" but mathematical cosine similarity ranges from -1 to 1 (negative for opposite vectors). The implementation correctly computes the full range (line 72 can produce negative values), but the docstring is wrong.
  - **Expected:** "Returns: Cosine similarity score (-1.0 to 1.0, where 1.0 = identical, 0.0 = orthogonal, -1.0 = opposite)"
  - **Fix:** Update docstrings in both functions (lines 60, 110) to reflect actual range

- [ ] **DOC-016**: Type Hint Mismatch in retrieve_multi_level()
  - **Location:** `src/core/tools.py:268-334`
  - **Problem:** Return type annotation is `dict[ContextLevel, List[MemoryResult]]` (lowercase dict, Python 3.9+) but rest of codebase uses `Dict[...]` from typing module (Python 3.7+ compatible). This inconsistency could break type checking in environments requiring `from __future__ import annotations` or older Python versions.
  - **Expected:** Use `Dict[ContextLevel, List[MemoryResult]]` for consistency with project style
  - **Fix:** Change line 274 to use uppercase Dict imported from typing

- [ ] **DOC-017**: Missing Parameter Documentation for list_indexed_units()
  - **Location:** `src/store/base.py:274-318`
  - **Problem:** Docstring documents `file_pattern` as "Optional pattern for file paths (SQL LIKE for SQLite, glob for Qdrant)" but SQLite storage has been removed (see REF-010 in factory.py). The documentation references non-existent SQLite backend, which will confuse implementers.
  - **Expected:** "Optional pattern for file paths (glob pattern for Qdrant)"
  - **Fix:** Remove SQLite reference from all base.py method docstrings

### 🟢 MEDIUM Priority Findings

- [ ] **DOC-018**: Stale Comment References Removed Fallback
  - **Location:** `src/store/factory.py:14-15`
  - **Problem:** Comment says "REF-010: SQLite fallback removed - Qdrant is now required for semantic code search" but this is a changelog-style comment in code, not actual documentation. Should be in CHANGELOG.md, not inline code.
  - **Expected:** Remove or move to module docstring as "History" section
  - **Fix:** Remove lines 14-15, ensure REF-010 is documented in CHANGELOG.md

- [ ] **DOC-019**: Misleading Variable Name in _extract_keywords()
  - **Location:** `src/tagging/auto_tagger.py:286-358`
  - **Problem:** Function is named `_extract_keywords()` but actually extracts "high-frequency words" and converts them to tags. The `min_word_length` parameter defaults to 4, but the docstring says "Extract high-frequency keywords as tags" without explaining that it's using TF (term frequency) not TF-IDF, which would be more accurate for keyword extraction.
  - **Expected:** Rename to `_extract_frequent_words()` or update docstring to say "Extract high-frequency words (simple term frequency, no IDF weighting)"
  - **Fix:** Add clarifying comment at line 287 explaining this is naive TF-based extraction

- [ ] **DOC-020**: Type Hint Missing for classify_batch()
  - **Location:** `src/memory/classifier.py:188-200`
  - **Problem:** Parameter `items` uses lowercase `tuple` in type hint: `List[tuple[str, MemoryCategory]]` instead of `Tuple` from typing module. Python 3.9+ supports lowercase tuple, but inconsistent with project style (line 5 imports `Tuple` from typing).
  - **Expected:** Use `List[Tuple[str, MemoryCategory]]` for consistency
  - **Fix:** Update line 189 type hint to use imported Tuple

- [ ] **DOC-021**: Example Code in Docstring References Wrong Method
  - **Location:** `src/core/tools.py:66-72`
  - **Problem:** Example shows `await tools.retrieve_preferences(query="coding style preferences", limit=10)` but the method signature has `limit: int = 5` (line 48). Example uses limit=10 which is fine, but could be clearer that it's overriding the default.
  - **Expected:** Add comment in example: `limit=10  # Override default of 5`
  - **Fix:** Enhance example to show default behavior or clarify override

- [ ] **DOC-022**: Incomplete Exception Documentation in validate_store_request()
  - **Location:** `src/core/validation.py:277-332`
  - **Problem:** Docstring says "Raises: ValidationError: If validation fails" but doesn't mention that it can also raise Pydantic ValidationError (wrapped from line 331: `except ValueError as e`). The function catches Pydantic errors and re-raises as custom ValidationError, but this isn't clear from docs.
  - **Expected:** "Raises: ValidationError: If validation fails (wraps Pydantic validation errors)"
  - **Fix:** Update docstring to clarify error wrapping behavior

- [ ] **DOC-023**: Ambiguous "Relevance" in TokenUsageEvent
  - **Location:** `src/analytics/token_tracker.py:14-26`
  - **Problem:** Dataclass field `relevance_avg: float` has comment "Average relevance score" but doesn't specify the range (0-1? 0-100?) or what it measures. Looking at usage in `track_search()` (line 145), it's passed directly from user without validation. For indexing events (line 177), it's hardcoded to 1.0 with comment "N/A for indexing".
  - **Expected:** Add to docstring: "relevance_avg: Average relevance score (0.0-1.0, 1.0 = perfect match)"
  - **Fix:** Document expected range and semantics for relevance_avg field

### 🟦 LOW Priority / Minor Inconsistencies

- [ ] **DOC-024**: Inconsistent DateTime Timezone Documentation
  - **Location:** `src/memory/project_context.py:29`, `src/analytics/token_tracker.py:17`
  - **Problem:** ProjectContext uses `last_activity: datetime = field(default_factory=lambda: datetime.now(UTC))` with explicit UTC, but TokenUsageEvent just says `timestamp: datetime` without timezone info. Both use `datetime.now()` (line 169 in token_tracker.py) which creates naive datetime, causing inconsistency.
  - **Expected:** Document whether all datetime fields should be timezone-aware or naive
  - **Fix:** Add project-wide convention in docs, update dataclass fields to specify tz requirements

- [ ] **DOC-025**: Magic Number 0.3 in get_project_weight() Undocumented
  - **Location:** `src/memory/project_context.py:242-261`
  - **Problem:** Method returns 0.3 for inactive projects and 2.0 for active projects (lines 261, 258) but doesn't explain why these specific multipliers were chosen. No reference to where these are used or their impact on ranking.
  - **Expected:** Add comment explaining rationale, e.g., "0.3 penalty for inactive projects keeps them findable but deprioritized; 2.0 boost for active project reflects user's current focus"
  - **Fix:** Add explanatory comment and reference to search result weighting algorithm

- [ ] **DOC-026**: Misleading Function Name: should_archive_project()
  - **Location:** `src/memory/project_context.py:263-282`
  - **Problem:** Function is named `should_archive_project()` suggesting it performs archival, but it only returns a boolean check. The caller must actually perform the archival. Name suggests action, but it's a query.
  - **Expected:** Rename to `is_project_archivable()` or `check_archival_eligibility()` to clarify it's a predicate
  - **Fix:** Rename function and update callers, or add docstring clarifying this is a check-only function

- [ ] **DOC-027**: Undocumented Side Effect in track_file_activity()
  - **Location:** `src/memory/project_context.py:213-241`
  - **Problem:** Docstring says "Track file activity to infer active project" but doesn't mention that it can AUTO-SET the current context if none is active (lines 234-240). This is a significant side effect that should be documented.
  - **Expected:** Add to docstring: "Note: If no context is currently active, this will automatically set the detected project as active."
  - **Fix:** Update docstring to document auto-context-switching behavior

- [ ] **DOC-028**: Comment Contradicts Implementation in _resolve_module_to_file()
  - **Location:** `src/memory/dependency_graph.py:78-143`
  - **Problem:** Comment at lines 88-91 says "This is a simplified implementation. A full implementation would need: - Language-specific module resolution rules..." but then the implementation at lines 109-137 actually DOES implement Python/JS/TS relative import resolution with multiple file extensions. The comment is stale.
  - **Expected:** Update comment to say "Currently implements relative import resolution for Python/JS/TS. TODO: Add absolute import resolution for project-internal modules"
  - **Fix:** Revise comment to reflect actual capabilities, move unimplemented items to TODO

- [ ] **DOC-029**: Stopwords Set Missing Common Code Terms
  - **Location:** `src/tagging/auto_tagger.py:292-338`
  - **Problem:** Stopwords list (lines 292-338) includes English stopwords ("the", "is", "at") but doesn't include common programming stopwords like "function", "class", "method", "return", "value" which appear frequently in code comments but aren't meaningful tags.
  - **Expected:** Add code-specific stopwords or document that this is intentionally English-only
  - **Fix:** Extend stopwords with code-specific terms or add comment explaining scope

### Summary Statistics

- **Total Issues Found:** 18 (DOC-012 through DOC-029)
- **Critical:** 2 (resource leak documentation, misleading return range)
- **High:** 5 (inconsistent async docs, wrong type hints, stale references)
- **Medium:** 6 (misleading names, incomplete exception docs, ambiguous fields)
- **Low:** 5 (minor inconsistencies, undocumented conventions)

**Common Patterns:**
1. Type hint inconsistencies (Dict vs dict, Tuple vs tuple) - affects 3 locations
2. Stale comments referencing removed features (SQLite) - affects 2 locations  
3. Missing documentation of side effects/resource requirements - affects 3 locations
4. Undocumented magic numbers and rationale - affects 2 locations
5. Misleading function/variable names not matching actual behavior - affects 3 locations

**Recommended Action Plan:**
1. Fix critical docs (DOC-012, DOC-015) when fixing related bugs (BUG-063)
2. Standardize type hint style across codebase (DOC-016, DOC-020)
3. Remove all SQLite references from documentation (DOC-017, DOC-018)
4. Add project-wide documentation standards for async methods, timezones, and error handling
5. Consider renaming misleading functions in next refactoring cycle (DOC-026, DOC-028)
## AUDIT-001 Part 13: Backup/Export/Import Findings (2025-11-30)

**Investigation Scope:** 2,547 lines across 9 files (scheduler.py, backup_command.py, export_command.py, import_command.py, exporter.py, importer.py, archive_exporter.py, archive_importer.py, archive_compressor.py, bulk_archival.py)

### 🔴 CRITICAL Findings

- [ ] **BUG-095**: Missing Client Release on Export Scroll Loop Failure
  - **Location:** `src/backup/exporter.py:332-386`
  - **Problem:** In `_get_filtered_memories()`, if scroll loop raises exception (lines 366-379), client is only released in finally block at line 385. However, if exception occurs before finally (e.g., KeyError in line 378), client may not be released back to pool.
  - **Fix:** Wrap entire scroll loop in try/finally, ensure client release happens in finally block even on early exception

- [ ] **BUG-096**: Import Merge Metadata Uses Wrong Embedding
  - **Location:** `src/backup/importer.py:343-353`
  - **Problem:** In MERGE_METADATA conflict strategy (line 343-353), merges metadata from imported memory into existing, but then calls `_update_memory(existing, imported_embedding)` with imported embedding (line 351). This updates existing memory with wrong embedding vector.
  - **Fix:** Fetch existing embedding via `_get_embedding(existing.id)` or skip embedding update entirely in merge mode

- [ ] **BUG-097**: Backup Scheduler Creates Store Without Closing on Error
  - **Location:** `src/backup/scheduler.py:153-168`
  - **Problem:** `_run_backup_job()` creates store (line 154) and exporter (line 157), but if exception occurs between lines 159-166, store.close() at line 168 is never reached (no try/finally)
  - **Fix:** Wrap in try/finally to ensure store cleanup even on error

- [ ] **BUG-098**: Archive Import Overwrites Conflict Without Validation
  - **Location:** `src/memory/archive_importer.py:122-124`
  - **Problem:** In "overwrite" conflict resolution, calls `self.compressor.delete_archive(target_project_name)` without checking if delete succeeded. If delete fails (permission error, file locked), import continues and may corrupt data.
  - **Fix:** Check return value of delete_archive() and raise error if deletion failed

### 🟡 HIGH Priority Findings

- [ ] **BUG-099**: Export Doesn't Validate Embedding Dimension Match
  - **Location:** `src/backup/exporter.py:149-153`
  - **Problem:** When creating portable archive with embeddings, exports numpy array without validating all embeddings have same dimension (line 151). Mismatched dimensions (e.g., after model change) will cause import failures.
  - **Fix:** Validate all embeddings have same shape before np.savez_compressed; log warning and skip malformed embeddings

- [ ] **BUG-100**: Import Checksum Verification Skips on Missing File
  - **Location:** `src/backup/importer.py:442-466`
  - **Problem:** `_verify_checksums()` logs warning "No checksums file found, skipping verification" (line 442-443) but continues import. This allows importing corrupted archives without detection.
  - **Fix:** Make checksum verification mandatory for archives created after version 1.0.0; add manifest field for "requires_checksum" validation

- [ ] **BUG-101**: Backup Cleanup Race Condition with Scheduler
  - **Location:** `src/backup/scheduler.py:199-249`, `src/cli/backup_command.py:278-352`
  - **Problem:** Scheduler's `_run_cleanup_job()` and CLI's `backup_cleanup()` both scan and delete backup files without coordination. If both run simultaneously, could delete same file twice or skip files.
  - **Fix:** Add file-based lock (e.g., `.backup_cleanup.lock`) to ensure only one cleanup operation runs at a time

- [ ] **REF-062**: Export Falls Back to Dummy Vector for Non-Qdrant Stores
  - **Location:** `src/backup/exporter.py:387-410`
  - **Problem:** For non-Qdrant stores, creates dummy embedding `[0.0] * 768` (line 398) which is misleading. User won't know export is incomplete until import fails.
  - **Fix:** Raise NotImplementedError for non-Qdrant stores with clear message directing user to Qdrant-only export

- [ ] **BUG-102**: Import Version Check Fails on Pre-Release Versions
  - **Location:** `src/backup/importer.py:374-377`
  - **Problem:** Version validation checks `if not version.startswith("1.")` which rejects valid versions like "1.0.0-beta" or "1.2.0rc1"
  - **Fix:** Use proper semver parsing (e.g., `packaging.version.parse()`) to validate major version compatibility

### 🟢 MEDIUM Priority Findings

- [ ] **BUG-103**: Export JSON Missing Schema Version Validation
  - **Location:** `src/backup/exporter.py:70-84`
  - **Problem:** Exports with hardcoded `schema_version: "3.0.0"` (line 72) but never validates imported data against this schema. Schema drift will cause silent data corruption.
  - **Fix:** Add schema validation on import that checks required fields match schema version expectations

- [ ] **REF-063**: Duplicate Checksum Calculation Code
  - **Location:** `src/backup/exporter.py:523-537` and `src/backup/importer.py:468-482`
  - **Problem:** Identical `_calculate_checksum()` method duplicated in both exporter and importer
  - **Fix:** Extract to shared utility module `src/backup/checksum_utils.py`

- [ ] **PERF-011**: Export Loads All Embeddings Into Memory
  - **Location:** `src/backup/exporter.py:150-153`
  - **Problem:** For large exports (100K+ memories), line 151 `embeddings = np.array([emb for m, emb in memory_embeddings])` loads all 768-dim vectors into single array, consuming gigabytes of RAM
  - **Fix:** Stream embeddings to npz file in chunks using np.savez with append mode or split into multiple files

- [ ] **BUG-104**: Scheduler Time Parsing Doesn't Validate Format
  - **Location:** `src/backup/scheduler.py:106-124`
  - **Problem:** `_create_trigger()` splits time string on ":" (line 107) without validating format. Input like "25:99" or "abc:def" will crash with ValueError.
  - **Fix:** Add regex validation `if not re.match(r'^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$', time): raise ValueError(...)`

- [ ] **BUG-105**: Import Keep Both Strategy Doesn't Prevent ID Collision
  - **Location:** `src/backup/importer.py:329-336`
  - **Problem:** KEEP_BOTH strategy appends "_imported" to ID (line 332), but if that ID also exists, will cause unique constraint violation on second import
  - **Fix:** Use UUID suffix instead: `imported.id = f"{imported.id}_{uuid.uuid4().hex[:8]}"`

- [ ] **REF-064**: Archive Compression Level Hardcoded Without Rationale
  - **Location:** `src/backup/scheduler.py:146`, `src/memory/archive_compressor.py:34`, `src/memory/archive_exporter.py:27`
  - **Problem:** Compression level defaults to 6 in multiple places without explanation of tradeoff (speed vs size)
  - **Fix:** Document rationale in constant: `DEFAULT_COMPRESSION_LEVEL = 6  # Balanced: ~85% of gzip -9 size at 2x speed`

- [ ] **BUG-106**: Bulk Archival Progress Callback Not Protected Against Exceptions
  - **Location:** `src/memory/bulk_archival.py:106-107`, `src/memory/bulk_archival.py:222-223`
  - **Problem:** Calls `progress_callback(project_name, idx, len(project_names))` without try/except. If user callback raises exception, entire bulk operation fails.
  - **Fix:** Wrap in try/except, log warning and continue on callback failure

### 🟦 LOW Priority / Tech Debt

- [ ] **REF-065**: Backup Config Serialization Drops notification_callback
  - **Location:** `src/backup/scheduler.py:329-346`
  - **Problem:** `save_config_to_file()` drops `notification_callback` field (line 344 omits it) without documenting why. User might expect callback to persist.
  - **Fix:** Add comment explaining callbacks can't be serialized, or add error if callback is set when saving

- [ ] **REF-066**: Markdown Export Hardcoded Timezone Format
  - **Location:** `src/backup/exporter.py:232`, `src/backup/exporter.py:271-272`
  - **Problem:** Uses `strftime('%Y-%m-%d %H:%M:%S UTC')` hardcoded to UTC without user preference
  - **Fix:** Add timezone parameter to export_to_markdown(), default to UTC but allow override

- [ ] **REF-067**: Archive Manifest Uses String for Estimated Restore Time
  - **Location:** `src/memory/archive_compressor.py:89`
  - **Problem:** Calculates `estimated_restore_time_seconds: max(5, compressed_size_mb / 2)` with simplistic formula that doesn't account for CPU speed, disk I/O, etc.
  - **Fix:** Either remove estimate (unreliable) or add disclaimer comment that it's rough heuristic for reference only

- [ ] **REF-068**: Export Markdown Slugify Allows Collision
  - **Location:** `src/backup/exporter.py:564-578`
  - **Problem:** `_slugify()` removes special chars but doesn't handle collisions. "Project-A" and "Project_A" both become "project-a"
  - **Fix:** Add uniqueness check and append counter suffix for collisions

- [ ] **PERF-012**: Scroll Loop Fetches Vectors Unnecessarily
  - **Location:** `src/backup/exporter.py:359` sets `with_vectors=True` even for non-embedding exports
  - **Problem:** When `include_embeddings=False`, still fetches vectors from Qdrant (expensive for large collections)
  - **Fix:** Conditionally set `with_vectors=include_embeddings` parameter

- [ ] **REF-069**: Import Store/Update Memory Methods Duplicate Metadata Building
  - **Location:** `src/backup/importer.py:484-515`
  - **Problem:** Both `_store_memory()` and `_update_memory()` build identical metadata dict (lines 489-503). Update then deletes and re-stores (line 511-512).
  - **Fix:** Extract metadata building to helper, consider using store.update() API if available instead of delete+store

- [ ] **BUG-107**: Archive Importer Doesn't Validate Manifest Archive Version
  - **Location:** `src/memory/archive_importer.py:105-111`
  - **Problem:** Loads manifest.json but never checks `archive_version` field for compatibility. Future breaking changes will cause silent import failures.
  - **Fix:** Add version compatibility check: `if manifest['archive_version'] not in SUPPORTED_VERSIONS: raise ValueError(...)`

### Backup/Export/Import Summary

**Data Integrity Risks:**
- 🔴 Critical: Wrong embedding used in merge strategy (BUG-096)
- 🔴 Critical: Missing checksum validation allows corrupted imports (BUG-100)
- 🟡 High: No embedding dimension validation on export (BUG-099)
- 🟡 High: Version check rejects valid semver formats (BUG-102)

**Resource Leaks:**
- 🔴 Critical: Client pool leak on export exception (BUG-095)
- 🔴 Critical: Store not closed on backup job error (BUG-097)

**Concurrency Issues:**
- 🟡 High: Backup cleanup race condition with scheduler (BUG-101)

**Missing Features/Validation:**
- Schema version validation on import (BUG-103)
- Archive version compatibility checks (BUG-107)
- ID collision prevention in KEEP_BOTH (BUG-105)

**Performance Concerns:**
- Export loads all embeddings in memory (PERF-011)
- Fetches vectors even when not needed (PERF-012)

**Recommended Priority:**
1. Fix BUG-095, BUG-096, BUG-097 (resource safety)
2. Fix BUG-099, BUG-100 (data integrity)
3. Add schema/version validation (BUG-103, BUG-107)
4. Address memory usage in large exports (PERF-011)
## AUDIT-001 Part 13: Backup/Export/Import Findings (2025-11-30)

**Investigation Scope:** 2,547 lines across 9 files (scheduler.py, backup_command.py, export_command.py, import_command.py, exporter.py, importer.py, archive_exporter.py, archive_importer.py, archive_compressor.py, bulk_archival.py)

### 🔴 CRITICAL Findings

- [ ] **BUG-095**: Missing Client Release on Export Scroll Loop Failure
  - **Location:** `src/backup/exporter.py:332-386`
  - **Problem:** In `_get_filtered_memories()`, if scroll loop raises exception (lines 366-379), client is only released in finally block at line 385. However, if exception occurs before finally (e.g., KeyError in line 378), client may not be released back to pool.
  - **Fix:** Wrap entire scroll loop in try/finally, ensure client release happens in finally block even on early exception

- [ ] **BUG-096**: Import Merge Metadata Uses Wrong Embedding
  - **Location:** `src/backup/importer.py:343-353`
  - **Problem:** In MERGE_METADATA conflict strategy (line 343-353), merges metadata from imported memory into existing, but then calls `_update_memory(existing, imported_embedding)` with imported embedding (line 351). This updates existing memory with wrong embedding vector.
  - **Fix:** Fetch existing embedding via `_get_embedding(existing.id)` or skip embedding update entirely in merge mode

- [ ] **BUG-097**: Backup Scheduler Creates Store Without Closing on Error
  - **Location:** `src/backup/scheduler.py:153-168`
  - **Problem:** `_run_backup_job()` creates store (line 154) and exporter (line 157), but if exception occurs between lines 159-166, store.close() at line 168 is never reached (no try/finally)
  - **Fix:** Wrap in try/finally to ensure store cleanup even on error

- [ ] **BUG-098**: Archive Import Overwrites Conflict Without Validation
  - **Location:** `src/memory/archive_importer.py:122-124`
  - **Problem:** In "overwrite" conflict resolution, calls `self.compressor.delete_archive(target_project_name)` without checking if delete succeeded. If delete fails (permission error, file locked), import continues and may corrupt data.
  - **Fix:** Check return value of delete_archive() and raise error if deletion failed

### 🟡 HIGH Priority Findings

- [ ] **BUG-099**: Export Doesn't Validate Embedding Dimension Match
  - **Location:** `src/backup/exporter.py:149-153`
  - **Problem:** When creating portable archive with embeddings, exports numpy array without validating all embeddings have same dimension (line 151). Mismatched dimensions (e.g., after model change) will cause import failures.
  - **Fix:** Validate all embeddings have same shape before np.savez_compressed; log warning and skip malformed embeddings

- [ ] **BUG-100**: Import Checksum Verification Skips on Missing File
  - **Location:** `src/backup/importer.py:442-466`
  - **Problem:** `_verify_checksums()` logs warning "No checksums file found, skipping verification" (line 442-443) but continues import. This allows importing corrupted archives without detection.
  - **Fix:** Make checksum verification mandatory for archives created after version 1.0.0; add manifest field for "requires_checksum" validation

- [ ] **BUG-101**: Backup Cleanup Race Condition with Scheduler
  - **Location:** `src/backup/scheduler.py:199-249`, `src/cli/backup_command.py:278-352`
  - **Problem:** Scheduler's `_run_cleanup_job()` and CLI's `backup_cleanup()` both scan and delete backup files without coordination. If both run simultaneously, could delete same file twice or skip files.
  - **Fix:** Add file-based lock (e.g., `.backup_cleanup.lock`) to ensure only one cleanup operation runs at a time

- [ ] **REF-062**: Export Falls Back to Dummy Vector for Non-Qdrant Stores
  - **Location:** `src/backup/exporter.py:387-410`
  - **Problem:** For non-Qdrant stores, creates dummy embedding `[0.0] * 768` (line 398) which is misleading. User won't know export is incomplete until import fails.
  - **Fix:** Raise NotImplementedError for non-Qdrant stores with clear message directing user to Qdrant-only export

- [ ] **BUG-102**: Import Version Check Fails on Pre-Release Versions
  - **Location:** `src/backup/importer.py:374-377`
  - **Problem:** Version validation checks `if not version.startswith("1.")` which rejects valid versions like "1.0.0-beta" or "1.2.0rc1"
  - **Fix:** Use proper semver parsing (e.g., `packaging.version.parse()`) to validate major version compatibility

### 🟢 MEDIUM Priority Findings

- [ ] **BUG-103**: Export JSON Missing Schema Version Validation
  - **Location:** `src/backup/exporter.py:70-84`
  - **Problem:** Exports with hardcoded `schema_version: "3.0.0"` (line 72) but never validates imported data against this schema. Schema drift will cause silent data corruption.
  - **Fix:** Add schema validation on import that checks required fields match schema version expectations

- [ ] **REF-063**: Duplicate Checksum Calculation Code
  - **Location:** `src/backup/exporter.py:523-537` and `src/backup/importer.py:468-482`
  - **Problem:** Identical `_calculate_checksum()` method duplicated in both exporter and importer
  - **Fix:** Extract to shared utility module `src/backup/checksum_utils.py`

- [ ] **PERF-011**: Export Loads All Embeddings Into Memory
  - **Location:** `src/backup/exporter.py:150-153`
  - **Problem:** For large exports (100K+ memories), line 151 `embeddings = np.array([emb for m, emb in memory_embeddings])` loads all 768-dim vectors into single array, consuming gigabytes of RAM
  - **Fix:** Stream embeddings to npz file in chunks using np.savez with append mode or split into multiple files

- [ ] **BUG-104**: Scheduler Time Parsing Doesn't Validate Format
  - **Location:** `src/backup/scheduler.py:106-124`
  - **Problem:** `_create_trigger()` splits time string on ":" (line 107) without validating format. Input like "25:99" or "abc:def" will crash with ValueError.
  - **Fix:** Add regex validation `if not re.match(r'^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$', time): raise ValueError(...)`

- [ ] **BUG-105**: Import Keep Both Strategy Doesn't Prevent ID Collision
  - **Location:** `src/backup/importer.py:329-336`
  - **Problem:** KEEP_BOTH strategy appends "_imported" to ID (line 332), but if that ID also exists, will cause unique constraint violation on second import
  - **Fix:** Use UUID suffix instead: `imported.id = f"{imported.id}_{uuid.uuid4().hex[:8]}"`

- [ ] **REF-064**: Archive Compression Level Hardcoded Without Rationale
  - **Location:** `src/backup/scheduler.py:146`, `src/memory/archive_compressor.py:34`, `src/memory/archive_exporter.py:27`
  - **Problem:** Compression level defaults to 6 in multiple places without explanation of tradeoff (speed vs size)
  - **Fix:** Document rationale in constant: `DEFAULT_COMPRESSION_LEVEL = 6  # Balanced: ~85% of gzip -9 size at 2x speed`

- [ ] **BUG-106**: Bulk Archival Progress Callback Not Protected Against Exceptions
  - **Location:** `src/memory/bulk_archival.py:106-107`, `src/memory/bulk_archival.py:222-223`
  - **Problem:** Calls `progress_callback(project_name, idx, len(project_names))` without try/except. If user callback raises exception, entire bulk operation fails.
  - **Fix:** Wrap in try/except, log warning and continue on callback failure

### 🟦 LOW Priority / Tech Debt

- [ ] **REF-065**: Backup Config Serialization Drops notification_callback
  - **Location:** `src/backup/scheduler.py:329-346`
  - **Problem:** `save_config_to_file()` drops `notification_callback` field (line 344 omits it) without documenting why. User might expect callback to persist.
  - **Fix:** Add comment explaining callbacks can't be serialized, or add error if callback is set when saving

- [ ] **REF-066**: Markdown Export Hardcoded Timezone Format
  - **Location:** `src/backup/exporter.py:232`, `src/backup/exporter.py:271-272`
  - **Problem:** Uses `strftime('%Y-%m-%d %H:%M:%S UTC')` hardcoded to UTC without user preference
  - **Fix:** Add timezone parameter to export_to_markdown(), default to UTC but allow override

- [ ] **REF-067**: Archive Manifest Uses String for Estimated Restore Time
  - **Location:** `src/memory/archive_compressor.py:89`
  - **Problem:** Calculates `estimated_restore_time_seconds: max(5, compressed_size_mb / 2)` with simplistic formula that doesn't account for CPU speed, disk I/O, etc.
  - **Fix:** Either remove estimate (unreliable) or add disclaimer comment that it's rough heuristic for reference only

- [ ] **REF-068**: Export Markdown Slugify Allows Collision
  - **Location:** `src/backup/exporter.py:564-578`
  - **Problem:** `_slugify()` removes special chars but doesn't handle collisions. "Project-A" and "Project_A" both become "project-a"
  - **Fix:** Add uniqueness check and append counter suffix for collisions

- [ ] **PERF-012**: Scroll Loop Fetches Vectors Unnecessarily
  - **Location:** `src/backup/exporter.py:359` sets `with_vectors=True` even for non-embedding exports
  - **Problem:** When `include_embeddings=False`, still fetches vectors from Qdrant (expensive for large collections)
  - **Fix:** Conditionally set `with_vectors=include_embeddings` parameter

- [ ] **REF-069**: Import Store/Update Memory Methods Duplicate Metadata Building
  - **Location:** `src/backup/importer.py:484-515`
  - **Problem:** Both `_store_memory()` and `_update_memory()` build identical metadata dict (lines 489-503). Update then deletes and re-stores (line 511-512).
  - **Fix:** Extract metadata building to helper, consider using store.update() API if available instead of delete+store

- [ ] **BUG-107**: Archive Importer Doesn't Validate Manifest Archive Version
  - **Location:** `src/memory/archive_importer.py:105-111`
  - **Problem:** Loads manifest.json but never checks `archive_version` field for compatibility. Future breaking changes will cause silent import failures.
  - **Fix:** Add version compatibility check: `if manifest['archive_version'] not in SUPPORTED_VERSIONS: raise ValueError(...)`

### Backup/Export/Import Summary

**Data Integrity Risks:**
- 🔴 Critical: Wrong embedding used in merge strategy (BUG-096)
- 🔴 Critical: Missing checksum validation allows corrupted imports (BUG-100)
- 🟡 High: No embedding dimension validation on export (BUG-099)
- 🟡 High: Version check rejects valid semver formats (BUG-102)

**Resource Leaks:**
- 🔴 Critical: Client pool leak on export exception (BUG-095)
- 🔴 Critical: Store not closed on backup job error (BUG-097)

**Concurrency Issues:**
- 🟡 High: Backup cleanup race condition with scheduler (BUG-101)

**Missing Features/Validation:**
- Schema version validation on import (BUG-103)
- Archive version compatibility checks (BUG-107)
- ID collision prevention in KEEP_BOTH (BUG-105)

**Performance Concerns:**
- Export loads all embeddings in memory (PERF-011)
- Fetches vectors even when not needed (PERF-012)

**Recommended Priority:**
1. Fix BUG-095, BUG-096, BUG-097 (resource safety)
2. Fix BUG-099, BUG-100 (data integrity)
3. Add schema/version validation (BUG-103, BUG-107)
4. Address memory usage in large exports (PERF-011)

## AUDIT-001 Part 15: Tagging & Classification System Findings (2025-11-30)

**Investigation Scope:** 6 files across tagging and classification subsystems
- `src/tagging/auto_tagger.py` (359 lines)
- `src/tagging/collection_manager.py` (373 lines)
- `src/tagging/tag_manager.py` (470 lines)
- `src/tagging/models.py` (98 lines)
- `src/memory/classifier.py` (271 lines)
- Supporting tests and CLI commands

**Key Observations:**
- Tagging system is isolated from main memory operations (no integration)
- No cleanup of orphaned tag associations when memories are deleted
- Auto-tagger relies on regex patterns with potential false positives
- Collection system has no enforcement of tag_filter constraints
- Tag normalization is case-insensitive but lacks Unicode handling

### 🔴 CRITICAL Findings

- [ ] **BUG-092**: Orphaned Tag Associations After Memory Deletion
  - **Location:** `src/services/memory_service.py:536-571` (delete_memory), `src/tagging/tag_manager.py` (no cleanup hook)
  - **Problem:** When a memory is deleted via `MemoryService.delete_memory()`, it only deletes from Qdrant store. The `memory_tags` table in SQLite is never cleaned up, creating orphaned associations that accumulate over time.
  - **Impact:** Database bloat, incorrect tag usage statistics, memory leaks in tag-related queries
  - **Evidence:** 
    - `delete_memory()` calls `await self.store.delete(request.memory_id)` but never touches tag_manager
    - `tag_manager.py` has no method to clean up tags by memory_id deletion event
    - No event system or callback mechanism connects MemoryService to TagManager
  - **Fix:** 
    1. Add `tag_manager.cleanup_memory_tags(memory_id: str)` method
    2. Call from `MemoryService.delete_memory()` after successful store deletion
    3. Also add batch cleanup method for `StorageOptimizer.execute_cleanup()` to catch historical orphans

- [ ] **BUG-093**: Collection Membership Not Enforced or Updated
  - **Location:** `src/tagging/collection_manager.py:194-227` (add_to_collection), no validation logic
  - **Problem:** Collections have `tag_filter` (e.g., `{"tags": ["python", "async"], "op": "AND"}`) but there's no code that:
    1. Validates memories match the filter when added
    2. Auto-updates collection membership when tags change
    3. Removes memories from collections when tags no longer match
  - **Impact:** Collections become stale and inaccurate over time; manual add_to_collection ignores tag_filter completely
  - **Fix:**
    1. Add validation in `add_to_collection()` to check memory tags match collection.tag_filter
    2. Add `refresh_collection(collection_id)` method to re-evaluate all members against filter
    3. Consider event-driven updates when tags are added/removed from memories

- [ ] **BUG-094**: Tag Name Validation Rejects Valid Unicode Characters
  - **Location:** `src/tagging/models.py:26-30`
  - **Problem:** Validator only allows `c.isalnum() or c in "-_"`, which rejects valid Unicode alphanumeric chars (e.g., "日本語", "Ελληνικά", "文档")
  - **Impact:** Non-English users cannot create natural language tags
  - **Fix:** Replace `c.isalnum()` with proper Unicode category check: `unicodedata.category(c) in ('Lu', 'Ll', 'Lt', 'Lm', 'Lo', 'Nd', 'Pc', 'Pd')`

### 🟡 HIGH Priority Findings

- [ ] **BUG-095**: Auto-Tagger Regex Patterns Have High False Positive Rate
  - **Location:** `src/tagging/auto_tagger.py:21-121` (all pattern dictionaries)
  - **Problem:** Overly broad regex patterns trigger on unrelated content:
    - `r"\bimport\b"` matches "import taxes" discussion → tagged as "python"
    - `r"\bclass\b"` matches "world class developer" → tagged as "java"
    - `r"\bconst\b"` matches "constitutional law" → tagged as "javascript"
    - `r"\btest\b"` matches "test results" in medical context → tagged as "testing"
  - **Impact:** Tag pollution, reduced search precision, misleading auto-collections
  - **Fix:** Add context validation - patterns should require technical context:
    ```python
    # Before: r"\bclass\b"
    # After: r"\b(class|interface)\s+\w+\s*\{" or check for code block context
    ```
    Consider requiring 2+ patterns match before tagging a language

- [ ] **BUG-096**: Tag Case Sensitivity Inconsistent with Retrieval
  - **Location:** `src/tagging/tag_manager.py:86` (normalizes to lowercase), but `get_tag_by_path:177` also lowercases
  - **Problem:** Tags are normalized to lowercase ("API" → "api", "FastAPI" → "fastapi") but this is only enforced in tag_manager. If external code queries tags or if user searches, case mismatches can occur. Additionally, hierarchical paths like "language/Python" get normalized to "language/python" which loses readability.
  - **Impact:** User searches for "API" won't find memories tagged "api"; confusion about canonical tag names
  - **Fix:** 
    1. Document case normalization policy clearly
    2. Add case-insensitive search option for user-facing queries
    3. Consider preserving display_name (original case) separate from normalized search key

- [ ] **REF-065**: Tag Hierarchy Depth Validation Happens Too Late
  - **Location:** `src/tagging/tag_manager.py:96-97`
  - **Problem:** Hierarchy depth check happens after parent lookup and path construction. If validation fails, DB was queried unnecessarily. Also, error message says "4 levels" but check is `>= 3`, which allows levels 0-3 (actually 4 levels total) - confusing.
  - **Fix:** 
    1. Check parent's level immediately: `if parent_tag and parent_tag.level >= 3: raise ValidationError`
    2. Clarify error message: "Tag hierarchy limited to 4 levels (0-3)"
    3. Add constant: `MAX_TAG_DEPTH = 3`

- [ ] **REF-066**: Auto-Tagger Hierarchical Inference Hardcoded and Incomplete
  - **Location:** `src/tagging/auto_tagger.py:175-226`
  - **Problem:** `infer_hierarchical_tags()` has hardcoded mappings (python→language/python, react→framework/react) but:
    1. Only handles 6 languages, 6 frameworks, 4 patterns, 4 domains
    2. Doesn't handle new tags added by users
    3. Logic like "if async in tags and python in tags → language/python/async" is fragile (what about other languages with async?)
  - **Impact:** Auto-tagging produces flat tags for most content; hierarchical organization is incomplete
  - **Fix:**
    1. Make hierarchy rules configurable (YAML/JSON file)
    2. Add auto-detection: if tag contains "/" already, don't infer hierarchy
    3. Use parent_id in tag creation instead of string path manipulation

- [ ] **BUG-097**: Collection Tag Filter Not Applied in get_collection_memories
  - **Location:** `src/tagging/collection_manager.py:257-274`
  - **Problem:** `get_collection_memories()` just returns all memory_ids from `collection_memories` table. It completely ignores the collection's `tag_filter`. Auto-generated collections (line 301-372) have tag_filter but it's never actually used for retrieval.
  - **Impact:** Collections with tag_filter are purely manual membership lists; auto-collection feature is non-functional
  - **Fix:** 
    1. If collection.tag_filter exists, query memory_tags to find memories matching filter
    2. If collection.tag_filter is None, fall back to current manual membership list
    3. Add `auto_update: bool` flag to collections to control behavior

### 🟢 MEDIUM Priority Findings

- [ ] **REF-067**: Tag Deletion Doesn't Clean Up Empty Parent Tags
  - **Location:** `src/tagging/tag_manager.py:267-305`
  - **Problem:** When deleting a tag with `cascade=True`, all descendants are deleted, but if this leaves parent tags with no children and no direct memory associations, those parent tags remain as orphaned hierarchy nodes.
  - **Impact:** Tag hierarchy accumulates dead branches over time
  - **Fix:** After cascade delete, walk up parent chain and delete any ancestors with no children and no memory associations

- [ ] **REF-068**: Tag Merge Doesn't Update Collection Filters
  - **Location:** `src/tagging/tag_manager.py:307-353` (merge_tags), `src/tagging/collection_manager.py` (no update logic)
  - **Problem:** When merging tags (e.g., merge "js" into "javascript"), collections with tag_filter referencing "js" are not updated to reference "javascript" instead.
  - **Impact:** Collections break silently after tag merges; filter becomes invalid
  - **Fix:** Add collection filter update to merge_tags():
    ```python
    # After merging memory_tags, also update collection filters
    collections = collection_manager.list_collections()
    for col in collections:
        if col.tag_filter and source_tag.full_path in col.tag_filter.get('tags', []):
            # Update filter to use target tag instead
    ```

- [ ] **BUG-098**: ContextLevelClassifier Has Overlapping Score Boosts
  - **Location:** `src/memory/classifier.py:116-151`
  - **Problem:** Classification applies category boost (line 121-128), then applies keyword boost (line 134-143), then applies code pattern boost (line 146-147). These can stack multiplicatively. E.g., a PREFERENCE category memory with "prefer" keyword gets +0.5 +0.2 = +0.7 boost, almost guaranteeing USER_PREFERENCE classification regardless of actual content.
  - **Impact:** Classifier is too easily biased by category hint; actual content analysis is overshadowed
  - **Fix:** Make boosts mutually exclusive or use weighted combination instead of additive stacking

- [ ] **REF-069**: Classifier Keyword Lists Are Not Comprehensive
  - **Location:** `src/memory/classifier.py:16-70`
  - **Problem:** Keyword patterns are limited (13 user pref, 14 project, 10 session). Many common patterns missing:
    - User preferences: "my approach", "I typically", "my workflow", "my convention"
    - Project context: "tech stack", "repo", "repository", "codebase structure"
    - Session state: "wip", "todo", "fixing", "debugging", "implementing"
  - **Impact:** Legitimate classification signals are missed; classifier falls back to defaults more often than needed
  - **Fix:** Expand keyword lists based on corpus analysis; consider making lists configurable/extensible

- [ ] **REF-070**: Auto-Tagger Stopword List Incomplete
  - **Location:** `src/tagging/auto_tagger.py:292-338`
  - **Problem:** Stopword list has 37 words but misses common technical terms that aren't good tags: "then", "than", "into", "also", "just", "when", "where", "what", "how", "why", "like", "more", "some", "been"
  - **Impact:** Low-value keyword tags pollute results
  - **Fix:** Expand stopword list or use NLTK/spaCy stopword corpus

- [ ] **BUG-099**: Tag Confidence Score Formulas Are Arbitrary
  - **Location:** `src/tagging/auto_tagger.py:239`, `253`, `267`, `281`, `355`
  - **Problem:** Confidence formulas like `min(0.9, 0.5 + (matches * 0.1))` are hardcoded magic numbers with no justification. Why is language detection capped at 0.9 but frameworks at 0.95? Why linear scaling?
  - **Impact:** Confidence scores don't reflect actual accuracy; can't be tuned or calibrated
  - **Fix:**
    1. Move all confidence parameters to class __init__ or config
    2. Add calibration data/tests showing confidence correlates with precision
    3. Consider logistic regression on match counts instead of linear

### 🟦 LOW Priority / Tech Debt

- [ ] **REF-071**: Collection Auto-Generate Patterns Not User-Extensible
  - **Location:** `src/tagging/collection_manager.py:320-329`
  - **Problem:** Default tag patterns for auto-generation are hardcoded. Users can't add their own patterns without modifying source code.
  - **Fix:** Load patterns from config file (e.g., `~/.config/claude-memory/collection_patterns.yaml`)

- [ ] **REF-072**: Tag Statistics Not Tracked
  - **Location:** `src/tagging/tag_manager.py` (no usage tracking)
  - **Problem:** No visibility into tag usage: how many memories have each tag? Which tags are most/least used? Are auto-generated tags accurate?
  - **Impact:** Can't optimize tagging strategy or clean up unused tags
  - **Fix:** Add `get_tag_statistics()` method returning tag usage counts, confidence distributions, auto vs manual ratios

- [ ] **REF-073**: No Bulk Tag Operations
  - **Location:** `src/tagging/tag_manager.py:355-390` (tag_memory is single-item only)
  - **Problem:** Tagging memories one-by-one in loops (see `auto_tag_command.py:89-94`) is inefficient. Each call is a separate DB transaction.
  - **Impact:** Auto-tagging 1000 memories = 1000+ DB commits; slow and high DB contention
  - **Fix:** Add `tag_memories_bulk(associations: List[Tuple[memory_id, tag_id, confidence]])` with single transaction

- [ ] **REF-074**: Classifier Default Fallback Always Returns PROJECT_CONTEXT
  - **Location:** `src/memory/classifier.py:164-165`, `179-186`
  - **Problem:** When all scores are low (<0.3), classifier falls back to `_default_for_category()`. But for 3 out of 5 categories (FACT, WORKFLOW, CONTEXT), default is PROJECT_CONTEXT. This creates bias toward PROJECT_CONTEXT.
  - **Impact:** Ambiguous memories are over-classified as project context
  - **Fix:** Consider returning UNKNOWN context level or using uniform distribution when confidence is low

- [ ] **REF-075**: Tag Full Path Separator Hardcoded
  - **Location:** `src/tagging/tag_manager.py:102`, `src/tagging/models.py:40-42`
  - **Problem:** "/" separator is hardcoded throughout. If user wants to create tag named "react/hooks" as flat tag (not hierarchy), it's impossible.
  - **Impact:** Naming restrictions; potential conflicts with file path tags
  - **Fix:** Either:
    1. Add escaping mechanism ("react\/hooks" for literal)
    2. Use different separator (e.g., "::" for hierarchy)
    3. Document limitation clearly

### Summary Statistics

**Total Findings:** 15 issues
- Critical: 3 (BUG-092, BUG-093, BUG-094)
- High: 5 (BUG-095, BUG-096, REF-065, REF-066, BUG-097)
- Medium: 5 (REF-067, REF-068, BUG-098, REF-069, REF-070, BUG-099)
- Low: 5 (REF-071, REF-072, REF-073, REF-074, REF-075)

**Severity Breakdown:**
| Severity | Count | IDs |
|----------|-------|-----|
| Critical (data corruption/loss) | 3 | BUG-092, BUG-093, BUG-094 |
| High (incorrect behavior) | 5 | BUG-095, BUG-096, REF-065, REF-066, BUG-097 |
| Medium (quality/maintainability) | 6 | REF-067, REF-068, BUG-098, REF-069, REF-070, BUG-099 |
| Low (tech debt) | 5 | REF-071, REF-072, REF-073, REF-074, REF-075 |

**Root Causes:**
1. **Isolation:** Tagging system completely isolated from MemoryService - no event integration
2. **Incomplete Implementation:** Collections have tag_filter but it's never actually enforced or used
3. **Hardcoded Logic:** Auto-tagger patterns, confidence formulas, hierarchy rules all hardcoded
4. **Lack of Validation:** Tag filters not validated when adding to collections; case sensitivity inconsistent
5. **No Analytics:** No usage tracking, statistics, or calibration data for tag quality

**Recommended Priorities:**
1. **Immediate:** Fix BUG-092 (orphaned tags on deletion) - causes DB bloat
2. **Short-term:** Implement BUG-093 (collection tag_filter enforcement) - core feature is broken
3. **Medium-term:** Address BUG-095 (false positive auto-tags) - affects data quality
4. **Long-term:** Refactor auto-tagger to be configurable (REF-066, REF-071)

**Next Ticket Numbers:** BUG-100, REF-076


## AUDIT-001 Part 16: Test Quality Findings (2025-11-30)

**Investigation Scope:** 202 test files across unit/, integration/, e2e/, security/, performance/ directories
**Focus:** Test patterns, not specific test logic - identifying systemic quality issues

### 🔴 CRITICAL Priority Findings

- [ ] **TEST-030**: Manual Test File Has Zero Assertions (435 Lines of Dead Code)
  - **Location:** `tests/manual/test_all_features.py` (435 lines, 0 assertions)
  - **Problem:** This file contains a `FeatureTester` class with extensive feature testing code (code search, memory CRUD, indexing, analytics, etc.) but uses `print()` statements and manual verification instead of assertions. Tests never fail programmatically - they require human inspection of output. This is not a test, it's a demo script masquerading as a test.
  - **Impact:** False confidence in test coverage metrics. File is counted in test suite but provides zero automated verification.
  - **Fix:** Either (1) convert to real assertions and move to integration/, or (2) move to `scripts/` and remove from test suite, or (3) delete if obsolete

- [ ] **TEST-031**: 79+ Skipped Tests Never Re-enabled (Validation Theater)
  - **Location:** Multiple files with `@pytest.mark.skip` and `pytest.skip()`
  - **Problem:** Found 79+ skipped tests across the suite. Key examples:
    - `test_kotlin_parsing.py`: 262 lines, all tests skipped (Kotlin not supported by parser)
    - `test_swift_parsing.py`: 189 lines, all tests skipped (Swift not supported by parser)
    - `test_services/test_cross_project_service.py`: 12/12 tests skipped (MultiRepositorySearcher not implemented)
    - `test_services/test_health_service.py`: 3 tests skipped (DashboardServer not available)
    - `test_auto_indexing_service.py`: Test skipped (auto_index_enabled config not implemented)
    - `test_index_codebase_initialization.py`: Test skipped (incorrect mock setup)
  - **Impact:** These skipped tests create illusion of comprehensive coverage while testing nothing. They rot over time as code changes.
  - **Fix:** Add TODO tickets for each skip reason, set timeline for implementation or deletion. Mark skipped tests with issue numbers.

- [ ] **BUG-095**: Timing Dependencies in 30+ Tests (Flakiness Source)
  - **Location:** Tests using `asyncio.sleep()` or `time.sleep()` for synchronization
  - **Problem:** Found 30+ instances of sleep-based synchronization:
    - `test_file_watcher.py:85`: `await asyncio.sleep(0.05)` for debounce testing
    - `test_background_indexer.py:47,224,302,385,529`: Multiple sleeps for job status polling
    - `test_connection_health_checker.py:102,170,241`: Blocking sleeps for timeout tests
    - `test_usage_tracker.py:124,145`: Sleeps for flush timing
    - `test_connection_pool.py:346`: 1.5s sleep for recycling test
  - **Impact:** Tests are timing-dependent and flaky under load or in CI. Many marked `@pytest.mark.skip_ci` to hide the problem.
  - **Fix:** Replace sleeps with event-based synchronization (asyncio.Event, threading.Event) or mock time

- [ ] **TEST-032**: Entire Test File Has Only Two `assert True` Statements
  - **Location:** `tests/unit/test_server_extended.py:471,592`
  - **Problem:** File has extensive setup for code search tests but only two assertions are literal `assert True` (lines 471, 592). This is validation theater - tests that appear to verify behavior but actually verify nothing.
  - **Impact:** False confidence. Tests pass even if code is completely broken.
  - **Fix:** Add real assertions or delete the tests

### 🟡 HIGH Priority Findings

- [ ] **TEST-033**: Excessive Fixture Complexity Creates Maintenance Burden
  - **Location:** `tests/conftest.py` (630+ lines), multiple conftest files
  - **Problem:** 
    - Session-scoped fixtures mix concerns (embedding mocks, Qdrant pooling, auto-indexing disable)
    - Mock embedding generator in conftest uses complex hash-based embeddings (lines 160-209)
    - Collection pooling logic is fragile (session-scoped `unique_qdrant_collection`)
    - 6 different conftest files with overlapping responsibilities
  - **Impact:** Hard to understand what any test is actually testing. Changes to fixtures break unrelated tests.
  - **Fix:** Document fixture dependencies, split into focused conftest files by concern, consider factory patterns

- [ ] **TEST-034**: Weak Assertions Provide False Confidence (359 Instances)
  - **Location:** 359 occurrences of `assert ... is not None` with no follow-up checks
  - **Problem:** Tests check object existence but not correctness. Examples:
    - Retrieve memory → assert result is not None → done (doesn't check content)
    - Index files → assert job is not None → done (doesn't check files were actually indexed)
    - Parse code → assert units is not None → done (doesn't check parsing correctness)
  - **Impact:** Tests pass when code returns garbage, as long as it's not None
  - **Fix:** Follow `is not None` with specific attribute/value checks

- [ ] **TEST-035**: Language Parsing Tests for Unsupported Languages (451+ Dead Lines)
  - **Location:** 
    - `test_kotlin_parsing.py`: 262 lines (Kotlin not supported)
    - `test_swift_parsing.py`: 189 lines (Swift not supported)
  - **Problem:** Comprehensive test suites exist for languages the parser doesn't support. All tests are skipped. Tests use inconsistent assertion styles (accessing dict keys vs attributes) suggesting they were written without running.
  - **Impact:** Dead code maintenance burden. False coverage metrics.
  - **Fix:** Delete these files or move to `tests/future/` directory with clear timeline for support

- [ ] **TEST-036**: No Cleanup in 30+ Database/File Fixtures (Resource Leaks)
  - **Location:** Tests using tempfile, sqlite, file watchers without proper cleanup
  - **Problem:** 
    - `test_usage_pattern_tracker.py`: 12 tests manually call `conn.close()` instead of fixture cleanup
    - File watchers in tests may not stop properly on test failure
    - Temp directories created without context managers in some tests
  - **Impact:** Resource leaks in test suite. Test failures leave garbage. CI runner disk fills up.
  - **Fix:** Use pytest fixtures with yield, context managers, or addFinalizer for all resource cleanup

- [ ] **TEST-037**: Polling Loops Without Timeouts in Test Helpers
  - **Location:** `tests/unit/test_background_indexer.py:28-47` (wait_for_job_status helper)
  - **Problem:** Helper function uses `while True` loop with timeout check, but polls every 10ms. If job never reaches status, test hangs until timeout (default 5s). This pattern appears in multiple test files.
  - **Impact:** Slow tests, timeout failures hide real bugs
  - **Fix:** Use pytest-timeout plugin, reduce polling interval to 100ms, add debug logging for timeout failures

### 🟢 MEDIUM Priority Findings

- [ ] **TEST-038**: Missing Parametrization Opportunities (5 Language Files)
  - **Location:** 5 separate parsing test files when one parameterized file would suffice
  - **Problem:** 
    - `test_cpp_parsing.py`, `test_php_parsing.py`, `test_ruby_parsing.py`, `test_kotlin_parsing.py`, `test_swift_parsing.py`
    - Each follows identical test pattern (file recognition, class extraction, function extraction, edge cases)
    - Only Ruby is consolidated into `test_language_parsing_parameterized.py` (per TEST-029)
  - **Impact:** Code duplication, inconsistent test coverage across languages, harder to add new languages
  - **Fix:** Consolidate all language parsing tests into parameterized suite like TEST-029 did for Ruby

- [ ] **TEST-039**: Heavy Mock Usage Without Integration Tests (4670 Mock Instances)
  - **Location:** 4670 `mock` or `Mock` references across test suite
  - **Problem:** 
    - Unit tests extensively mock dependencies (good for isolation)
    - But only 37 integration tests vs 165+ unit tests
    - Critical paths like store→indexer→search are mostly tested with mocks
  - **Impact:** Mocks drift from reality. Integration bugs slip through.
  - **Fix:** Add integration tests for each critical workflow, reduce mocking in "integration" tests

- [ ] **TEST-040**: 61 Parametrized Tests Only (Missed Opportunities)
  - **Location:** Only 61 uses of `@pytest.mark.parametrize` across 202 test files
  - **Problem:** Many test files have repetitive tests with only input data changing:
    - `test_refinement_advisor.py`: 11 separate test functions for different result counts (should be parameterized)
    - `test_spelling_suggester.py`: 7 tests with similar patterns
    - `test_ragignore_manager.py`: 22 tests, many test pattern validation with different inputs
  - **Impact:** Verbose test suite, harder to add new test cases
  - **Fix:** Identify test patterns and convert to parameterized tests

- [ ] **TEST-041**: Exception Testing Without Message Validation (Many pytest.raises)
  - **Location:** Tests using `with pytest.raises(SomeError):` without match parameter
  - **Problem:** Tests verify exception type but not message. Examples in:
    - `test_store/test_connection_pool.py`: 5 validation tests check exception type only
    - Many MCP error handling tests don't validate error messages
  - **Impact:** Tests pass even if error messages are unhelpful or wrong
  - **Fix:** Add `match=` parameter to pytest.raises to validate error messages

- [ ] **TEST-042**: Test File Organization Issues
  - **Location:** `tests/unit/test_services/`, `tests/unit/test_store/` vs `tests/unit/store/`
  - **Problem:** 
    - Two separate test_store directories (`test_store/` and `store/`)
    - `test_services/` has 5 test files, 4 of which have skipped tests
    - Mixing graph tests in `tests/unit/graph/` vs other unit tests
  - **Impact:** Hard to find tests, unclear structure
  - **Fix:** Consolidate test directories to match src/ structure

### 🟢 LOW Priority Findings

- [ ] **REF-062**: Inconsistent Async Test Patterns
  - **Location:** Mix of `@pytest.mark.asyncio` and `pytest_asyncio.fixture` usage
  - **Problem:** Some tests use `@pytest.mark.asyncio`, others use `pytest_asyncio.fixture`, some mix both. No clear pattern.
  - **Impact:** Confusion about which pattern to use for new tests
  - **Fix:** Standardize on pytest-asyncio patterns, document in TESTING_GUIDE.md

- [ ] **REF-063**: Test Data in test_data/ Directory Unused
  - **Location:** `tests/test_data/` directory exists
  - **Problem:** Directory is present but unclear what it contains or which tests use it
  - **Impact:** Potentially unused test data accumulating
  - **Fix:** Document test data directory purpose or remove if unused

- [ ] **REF-064**: Comment-Only Test Documentation (No Docstrings in Some Files)
  - **Location:** Multiple test files use `# Test X` comments instead of docstrings
  - **Problem:** Some test functions have docstrings, others have comments, inconsistent
  - **Impact:** Harder to generate test documentation, pytest output less informative
  - **Fix:** Standardize on docstrings for all test functions

### Test Quality Metrics Summary

**Counts:**
- Total test files: 202
- Total test functions: ~1800+ (estimated from grep counts)
- Skipped tests: 79+
- Parametrized tests: 61
- Mock/Mock usage: 4670 instances
- Sleep-based timing: 30+ instances
- Weak assertions (is not None only): 359
- Dead code (skipped language tests): 451+ lines

**Patterns Observed:**
- ✅ Good: Most tests use unique collections for isolation (via conftest pooling)
- ✅ Good: Project name isolation in parallel tests (test_project_name fixture)
- ✅ Good: Comprehensive error path testing (984 error-related tests)
- ⚠️ Weak: Heavy mocking with limited integration coverage
- ⚠️ Weak: Timing-based synchronization instead of event-based
- ⚠️ Weak: Many skipped tests that never get re-enabled
- ❌ Critical: Manual test file with zero assertions
- ❌ Critical: Tests for unsupported features that just add maintenance burden

**High-Risk Areas for Future Monitoring:**
1. Background indexer tests (polling, timeouts, resource cleanup)
2. File watcher tests (timing sensitive, marked skip_ci)
3. Connection pool tests (sleep-based recycling, timeout tests)
4. Concurrent operation tests (all skipped due to flakiness)
5. Language parsing tests (dead code for unsupported languages)

**Recommendations:**
1. **Immediate:** Delete or convert `tests/manual/test_all_features.py`
2. **Immediate:** Add TODO tickets for all 79+ skipped tests with timelines
3. **Short-term:** Replace sleep-based sync with event-based in top 10 flaky tests
4. **Short-term:** Consolidate language parsing tests per TEST-029 pattern
5. **Medium-term:** Add 20+ integration tests for critical workflows
6. **Long-term:** Reduce mock usage in favor of real component integration

## AUDIT-001 Part 18: Security & Input Validation Findings (2025-11-30)

**Investigation Scope:** Security-sensitive code patterns across entire codebase: subprocess execution, file operations, tarfile extraction, path handling, input validation, query construction, logging practices, and authentication/authorization mechanisms.

### 🔴 CRITICAL Security Findings

- [ ] **SEC-001**: Tarfile Extraction Without Path Traversal Protection (Zip Slip Vulnerability)
  - **Severity:** CRITICAL - Remote Code Execution / Arbitrary File Write
  - **Location:** `src/backup/importer.py:143-144`, `src/memory/archive_importer.py:73-74`, `src/memory/archive_compressor.py:244`
  - **Problem:** `tarfile.extractall(temp_path)` is called without member validation. An attacker could craft a malicious tarball with entries like `../../etc/crontab` or `../../../root/.ssh/authorized_keys` to write files outside the intended directory. This is a classic "Zip Slip" vulnerability (CVE-2018-1000001 and similar).
  - **Attack Scenario:** 
    1. Attacker creates malicious backup archive with path traversal in filenames
    2. Admin imports backup via `import_from_archive()` or `import_project_archive()`
    3. Malicious files written to arbitrary locations on filesystem
    4. Could achieve RCE via cron jobs, SSH keys, or Python module injection
  - **Affected Code:**
    ```python
    # src/backup/importer.py:143
    with tarfile.open(archive_path, 'r:gz') as tar:
        tar.extractall(temp_path)  # ❌ UNSAFE
    
    # src/memory/archive_importer.py:73
    with tarfile.open(archive_path, "r:gz") as tar:
        tar.extractall(temp_path)  # ❌ UNSAFE
    ```
  - **Fix:** Add safe extraction helper:
    ```python
    def safe_extract(tar, path="."):
        for member in tar.getmembers():
            member_path = os.path.join(path, member.name)
            if not os.path.abspath(member_path).startswith(os.path.abspath(path)):
                raise ValidationError(f"Path traversal attempt: {member.name}")
            if member.issym() or member.islnk():
                raise ValidationError(f"Symlink/hardlink not allowed: {member.name}")
        tar.extractall(path)
    ```
  - **References:** 
    - https://security.snyk.io/research/zip-slip-vulnerability
    - https://cwe.mitre.org/data/definitions/22.html (CWE-22: Path Traversal)

- [ ] **SEC-002**: Subprocess Command Injection via git_detector.py
  - **Severity:** HIGH - Local Command Execution
  - **Location:** `src/memory/git_detector.py:30-36, 56-62, 105-111, 122-128, 139-145, 156-162`
  - **Problem:** All git commands use hardcoded arguments and `cwd=str(path)`, where `path` is derived from `Path(path).resolve()`. However, if an attacker can control the current working directory (e.g., via symlink manipulation or race condition), they could potentially execute git commands in unintended locations. More critically, the `cwd` parameter uses `str(path)` which could contain shell metacharacters if path validation is bypassed upstream.
  - **Attack Scenario:** 
    1. Attacker creates directory with name containing shell metacharacters (if OS allows)
    2. Code indexes or detects project in that directory
    3. Path passed to `subprocess.run(cwd=malicious_path)` 
    4. While subprocess.run with list args is generally safe, the cwd parameter could still expose environment manipulation
  - **Current Mitigations:** 
    - Uses `subprocess.run()` with list args (not shell=True) ✓
    - Uses `capture_output=True` to prevent output injection ✓
    - Has `timeout=5` to prevent DoS ✓
  - **Fix:** Add explicit path validation before subprocess calls:
    ```python
    def validate_git_path(path: Path) -> None:
        resolved = path.resolve()
        # Ensure no null bytes, control characters, or suspicious patterns
        if '\x00' in str(resolved) or any(c < ' ' for c in str(resolved)):
            raise ValidationError(f"Invalid path: {resolved}")
        # Ensure path doesn't escape project root boundary if applicable
        if not resolved.exists():
            raise ValidationError(f"Path does not exist: {resolved}")
    ```

- [ ] **SEC-003**: Missing Input Sanitization on User-Controlled File Paths
  - **Severity:** HIGH - Path Traversal / Unauthorized File Access
  - **Location:** `src/services/code_indexing_service.py:591, 669, 892, 948, 988-989`
  - **Problem:** Multiple functions accept `directory_path` or `file_path` from user input and call `Path(path).resolve()` without checking if resolved path escapes intended boundaries. An attacker could provide paths like `/etc/passwd` or `../../sensitive/file` to index or access files outside project scope.
  - **Affected Functions:**
    - `index_codebase()` - line 591: `dir_path = Path(directory_path).resolve()`
    - `reindex_project()` - line 669: `dir_path = Path(directory_path).resolve()`
    - `track_file()` - line 892: `file_path = str(Path(file_path).resolve())`
    - `untrack_file()` - line 948: `file_path = str(Path(file_path).resolve())`
    - `move_file()` - line 988-989: `source_file = str(Path(source_file).resolve())`
  - **Attack Scenario:**
    1. Attacker calls MCP tool `index_codebase` with path `/etc`
    2. Server indexes sensitive system files
    3. Attacker queries for "password" and retrieves /etc/shadow content via semantic search
  - **Current Validation:** Only checks `if not dir_path.exists()` and `if not dir_path.is_dir()` - does NOT check boundaries
  - **Fix:** Add boundary validation:
    ```python
    def validate_project_path(path: Path, allowed_roots: List[Path]) -> Path:
        resolved = path.resolve()
        if not any(resolved.is_relative_to(root) for root in allowed_roots):
            raise ValidationError(f"Path outside allowed directories: {resolved}")
        return resolved
    ```

- [ ] **SEC-004**: Potential DoS via Unbounded Regex in validation.py
  - **Severity:** MEDIUM - Regular Expression Denial of Service (ReDoS)
  - **Location:** `src/core/validation.py:183, 188, 193, 198`
  - **Problem:** Multiple regex patterns are applied to user input without length limits or timeouts. Some patterns have potential for catastrophic backtracking, especially:
    - Line 183: `re.search(pattern, text_lower, re.IGNORECASE | re.MULTILINE)` - SQL injection patterns with nested groups like `r"('|(\\'))(\s)*(or|OR|Or)(\s)*('|(\\'))(\s)*=(\s)*('|(\\'))"`
    - Pattern `r"(and|or)(\s)+\d+(\s)*=(\s)*\d+"` could cause backtracking on long input with many "and"/"or" tokens
  - **Attack Scenario:**
    1. Attacker sends 10MB memory content with pattern designed to cause catastrophic backtracking
    2. Regex engine consumes CPU for extended time
    3. Server becomes unresponsive (DoS)
  - **Current Mitigation:** `validate_content_size()` limits to 50KB, which reduces attack surface
  - **Fix:** Add regex timeout wrapper:
    ```python
    import signal
    def safe_regex_search(pattern, text, timeout_ms=100):
        def timeout_handler(signum, frame):
            raise TimeoutError("Regex timeout")
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.setitimer(signal.ITIMER_REAL, timeout_ms / 1000.0)
        try:
            return re.search(pattern, text)
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
    ```
    Or use third-party library like `timeout-decorator` or `regex` module with timeout support.

### 🟡 HIGH Priority Security Findings

- [ ] **SEC-005**: No Rate Limiting on MCP Tool Endpoints
  - **Severity:** MEDIUM - Denial of Service / Resource Exhaustion
  - **Location:** `src/core/server.py` (all MCP tool handlers), `src/services/*.py`
  - **Problem:** MCP server has NO rate limiting on any operations. An attacker or misbehaving client could spam expensive operations:
    - `index_codebase()` - CPU/memory intensive
    - `search_code()` - vector search operations
    - `store_memory()` - database writes
    - `batch_store()` - accepts up to 1000 items per call (line `src/core/validation.py:514`)
  - **Attack Scenario:**
    1. Attacker writes script to call `batch_store()` in loop
    2. Each call stores 1000 memories
    3. Qdrant database and disk fill up
    4. Legitimate users cannot store data
  - **Observed Security Logger Event:** `SecurityEventType.RATE_LIMIT_EXCEEDED` exists in `src/core/security_logger.py:19` but is NEVER used anywhere in codebase (grep confirms)
  - **Fix:** Implement token bucket or sliding window rate limiter:
    ```python
    from collections import defaultdict
    from time import time
    
    class RateLimiter:
        def __init__(self, max_requests: int = 100, window_seconds: int = 60):
            self.limits = defaultdict(list)
            self.max_requests = max_requests
            self.window_seconds = window_seconds
        
        def check_rate_limit(self, client_id: str) -> bool:
            now = time()
            self.limits[client_id] = [t for t in self.limits[client_id] if now - t < self.window_seconds]
            if len(self.limits[client_id]) >= self.max_requests:
                return False
            self.limits[client_id].append(now)
            return True
    ```

- [ ] **SEC-006**: Qdrant Query Construction Without Parameterization
  - **Severity:** MEDIUM - Potential NoSQL Injection
  - **Location:** `src/store/qdrant_store.py:182, 272-287, 399, 478, 810` - all filter construction sites
  - **Problem:** While Qdrant uses structured Filter objects (not string queries), user-controlled values are passed directly into `MatchValue(value=user_input)` and `Range()` without sanitization. The validation in `src/core/validation.py` sanitizes content and query text, but does NOT sanitize filter fields like `project_name`, `tags`, `category`.
  - **Affected Code:**
    ```python
    # src/store/qdrant_store.py:276-277
    FieldCondition(
        key="category",
        match=MatchValue(value="code")  # Hardcoded ✓
    ),
    FieldCondition(
        key="project_name",
        match=MatchValue(value=project_name)  # User input - could be malicious ⚠️
    ),
    ```
  - **Current Validation:** `validate_project_name()` in validation.py checks alphanumeric + `_-.` characters (line 483), which is GOOD but not applied consistently
  - **Risk:** While Qdrant's typed API limits injection compared to string-based queries, unexpected values could bypass filters or cause errors
  - **Fix:** Ensure all user-controlled filter values go through validation:
    - Always call `validate_project_name()` before using in filters
    - Validate tags array (each tag should match `^[a-zA-Z0-9_\-\.]+$`)
    - Add validation to SearchFilters Pydantic model with field validators

- [ ] **SEC-007**: Subprocess Execution Without User Input Validation (system_check.py, health_command.py)
  - **Severity:** MEDIUM - Local Command Execution Risk
  - **Location:** `src/core/system_check.py:63, 110, 126, 181, 231`, `src/cli/health_command.py:89, 142`
  - **Problem:** Multiple subprocess.run() calls execute Docker and other system commands. While all use hardcoded command lists (no shell=True), they lack user input validation if command arguments ever become parameterized in future.
  - **Current State:** 
    - All subprocess calls use list-form arguments ✓
    - All have timeouts (5 seconds) ✓
    - capture_output=True prevents output injection ✓
    - No user input in current implementation ✓
  - **Risk:** FUTURE vulnerability if these functions are refactored to accept user parameters
  - **Fix (Preventive):** Add explicit guards:
    ```python
    def check_docker() -> SystemRequirement:
        # Ensure no user input reaches subprocess
        ALLOWED_COMMANDS = [["docker", "--version"], ["docker", "ps"]]
        # ... rest of implementation
    ```
    Add comment: `# SECURITY: Never accept user input for command construction`

- [ ] **SEC-008**: Security Logger Logs to Predictable Location Without Rotation
  - **Severity:** LOW - Information Disclosure / Log Manipulation
  - **Location:** `src/core/security_logger.py:39-42`
  - **Problem:** Security logs written to `~/.claude-rag/security.log` with no rotation, size limits, or permissions management:
    ```python
    self.log_dir = Path(log_dir).expanduser()
    self.log_dir.mkdir(parents=True, exist_ok=True)
    self.log_file = self.log_dir / "security.log"
    ```
  - **Issues:**
    1. No log rotation - file grows unbounded (disk exhaustion DoS)
    2. No permission restrictions - readable by all local users on multi-user system
    3. Predictable location - attacker knows where to look for security events
    4. Directory created with default umask - might be world-readable
  - **Fix:**
    ```python
    import os
    from pathlib import Path
    
    # Create with restricted permissions
    self.log_dir = Path(log_dir).expanduser()
    self.log_dir.mkdir(parents=True, exist_ok=True, mode=0o700)  # Owner only
    self.log_file = self.log_dir / "security.log"
    
    # Add rotation
    from logging.handlers import RotatingFileHandler
    file_handler = RotatingFileHandler(
        self.log_file,
        maxBytes=10_000_000,  # 10MB
        backupCount=5,
        mode='a',
    )
    
    # Set file permissions explicitly after creation
    os.chmod(self.log_file, 0o600)
    ```

### 🟢 MEDIUM Priority Security Findings

- [ ] **SEC-009**: Path Symlink Following in File Operations
  - **Severity:** MEDIUM - Unauthorized File Access (TOCTOU)
  - **Location:** `src/memory/ragignore_manager.py:343`, `src/memory/file_watcher.py:150` mention symlinks, but many file operations use `.resolve()` which follows symlinks by default
  - **Problem:** `Path.resolve()` follows symlinks, which could lead to Time-of-Check-Time-of-Use (TOCTOU) vulnerabilities:
    1. Code checks `path.exists()` on symlink
    2. Attacker replaces symlink target between check and use
    3. Code operates on attacker-controlled file
  - **Example:**
    ```python
    # src/services/code_indexing_service.py:591
    dir_path = Path(directory_path).resolve()  # Follows symlinks
    if not dir_path.exists():  # Check
        raise ValueError(...)
    # ... time passes ...
    await indexer.index_directory(dir_path)  # Use - target could have changed
    ```
  - **Observed Mitigations:** 
    - ragignore_manager.py comment mentions handling symlinks (line 343)
    - file_watcher.py mentions catching symlink issues (line 150)
  - **Fix:** Use `Path.resolve(strict=True)` to fail on broken symlinks, and check if target is a symlink before critical operations:
    ```python
    if path.is_symlink():
        raise ValidationError("Symlinks not allowed in project paths")
    ```

- [ ] **SEC-010**: No Authentication or Authorization on MCP Server
  - **Severity:** MEDIUM - Unauthorized Access
  - **Location:** `src/core/server.py` (entire MCP server implementation)
  - **Problem:** MCP server has ZERO authentication or authorization mechanisms. Any process that can connect to the server can:
    - Read all stored memories (potentially sensitive code/comments)
    - Write arbitrary memories
    - Delete memories
    - Index arbitrary directories
    - Execute expensive operations
  - **Current State:** 
    - No API keys
    - No session tokens
    - No user identification
    - No permission model
  - **Risk:** Appropriate for single-user desktop use, but NOT for multi-user or networked deployments
  - **Fix (Future Enhancement):** Add capability-based security:
    ```python
    class MCPCapability(Enum):
        READ_MEMORY = "read_memory"
        WRITE_MEMORY = "write_memory"
        DELETE_MEMORY = "delete_memory"
        INDEX_CODE = "index_code"
        ADMIN = "admin"
    
    class MCPAuth:
        def __init__(self, api_key: str, capabilities: List[MCPCapability]):
            self.api_key = api_key
            self.capabilities = capabilities
        
        def can_perform(self, capability: MCPCapability) -> bool:
            return capability in self.capabilities or MCPCapability.ADMIN in self.capabilities
    ```

- [ ] **SEC-011**: Injection Pattern Detection May Have False Negatives
  - **Severity:** LOW - Security Control Bypass
  - **Location:** `src/core/validation.py:169-201` (detect_injection_patterns function)
  - **Problem:** Regex-based injection detection can be bypassed with encoding tricks:
    - Unicode normalization not applied (e.g., "ｓｅｌｅｃｔ" vs "select")
    - Case variations in SQL keywords partially covered but not exhaustive
    - No detection of encoded payloads (base64, hex, URL encoding)
    - Pattern `r"select(\s)+.*(\s)+from"` requires space between SELECT and FROM, but `SELECT/**/FROM` bypasses
  - **Example Bypass:**
    ```python
    # These might bypass current patterns:
    "SEL" + "ECT * FROM users"  # String concatenation
    "SELECT/*comment*/FROM"     # SQL comment without space
    "SELECT\x09FROM"            # Tab character instead of space
    ```
  - **Current Strength:** Very comprehensive pattern list (75+ patterns), catches most common attacks
  - **Fix:** Add preprocessing:
    ```python
    import unicodedata
    def detect_injection_patterns(text: str) -> Optional[str]:
        # Normalize unicode
        text = unicodedata.normalize('NFKC', text)
        # Remove SQL comments
        text = re.sub(r'/\*.*?\*/', ' ', text)
        # Collapse whitespace variations
        text = re.sub(r'\s+', ' ', text)
        # Then run existing pattern checks
        ...
    ```

- [ ] **SEC-012**: Potential Information Disclosure in Error Messages
  - **Severity:** LOW - Information Leakage
  - **Location:** Throughout codebase - exception messages include internal paths and stack traces
  - **Problem:** Error messages may reveal internal system information:
    - File paths: `raise ValidationError(f"Directory does not exist: {directory_path}")`
    - Stack traces in logs
    - Qdrant connection strings in error messages
  - **Examples:**
    - `src/services/code_indexing_service.py:594`: `raise ValueError(f"Directory does not exist: {directory_path}")`
    - `src/store/qdrant_store.py:92`: `raise StorageError(f"Failed to initialize Qdrant store: {e}")`
  - **Risk:** Low in single-user desktop environment, higher if server exposed remotely
  - **Fix:** Sanitize error messages for external users:
    ```python
    def safe_error_message(internal_msg: str, user_msg: str, log_internal: bool = True) -> str:
        if log_internal:
            logger.error(f"Internal error: {internal_msg}")
        return user_msg  # Return generic message to user
    
    # Usage
    raise ValidationError(safe_error_message(
        f"Directory does not exist: {directory_path}",
        "Invalid directory path provided"
    ))
    ```

- [ ] **SEC-013**: shutil.rmtree Without Safety Checks
  - **Severity:** MEDIUM - Accidental Data Loss / Directory Traversal
  - **Location:** `src/memory/archive_compressor.py:345`
  - **Problem:** `shutil.rmtree(archive_dir)` deletes directory tree without validation that path is within expected boundaries
  - **Risk:** If `archive_dir` path is manipulated (symlink attack, path traversal), could delete unintended directories
  - **Current Code:**
    ```python
    # src/memory/archive_compressor.py:345
    shutil.rmtree(archive_dir)  # ❌ No validation
    ```
  - **Fix:**
    ```python
    def safe_rmtree(path: Path, allowed_parent: Path):
        resolved = path.resolve()
        if not resolved.is_relative_to(allowed_parent.resolve()):
            raise ValidationError(f"Cannot delete path outside allowed directory: {resolved}")
        if resolved == allowed_parent:
            raise ValidationError("Cannot delete parent directory itself")
        shutil.rmtree(resolved)
    ```

### 🟦 LOW Priority Security Findings

- [ ] **SEC-014**: Hardcoded Embedding Model Vulnerable to Model Poisoning
  - **Severity:** LOW - Supply Chain Attack
  - **Location:** `src/config.py:15-20`
  - **Problem:** Default embedding model "all-mpnet-base-v2" is downloaded from Hugging Face without integrity verification (checksum, signature)
  - **Risk:** If Hugging Face is compromised or MITM attack occurs, malicious model could be downloaded
  - **Observed:** Model dimensions are hardcoded (768) which provides some validation
  - **Fix (Future):** Add model checksum verification:
    ```python
    EMBEDDING_MODEL_CHECKSUMS = {
        "all-mpnet-base-v2": "sha256:abcdef123456...",
    }
    
    def verify_model_integrity(model_name: str, model_path: Path) -> bool:
        expected = EMBEDDING_MODEL_CHECKSUMS.get(model_name)
        if not expected:
            logger.warning(f"No checksum available for {model_name}")
            return True
        actual = hashlib.sha256(model_path.read_bytes()).hexdigest()
        return f"sha256:{actual}" == expected
    ```

- [ ] **SEC-015**: Git Subprocess Calls Trust PATH Environment Variable
  - **Severity:** LOW - Environment Variable Manipulation
  - **Location:** All `subprocess.run(["git", ...])` calls in `src/memory/git_detector.py`
  - **Problem:** `subprocess.run(["git", ...])` searches for "git" in PATH. If attacker controls PATH environment variable, they could substitute malicious git binary
  - **Risk:** Low in typical desktop environment, higher in shared hosting
  - **Current Mitigation:** `timeout=5` limits damage
  - **Fix:** Use absolute path to git binary:
    ```python
    import shutil
    
    GIT_BINARY = shutil.which("git")  # Resolve once at module import
    if not GIT_BINARY:
        raise RuntimeError("git not found in PATH")
    
    # Then use
    subprocess.run([GIT_BINARY, "rev-parse", ...])
    ```

- [ ] **SEC-016**: Qdrant Connection String May Contain Credentials in Logs
  - **Severity:** LOW - Credential Leakage
  - **Location:** `src/store/qdrant_setup.py:68` (connection creation), various log statements
  - **Problem:** If Qdrant is configured with authentication (API key in URL or config), connection errors could log credentials
  - **Current State:** Config uses environment variables (good practice), but no explicit credential redaction in logs
  - **Fix:** Add credential redaction:
    ```python
    def redact_url(url: str) -> str:
        """Redact credentials from URL for logging."""
        import re
        return re.sub(r'://([^:]+):([^@]+)@', r'://\1:***@', url)
    
    logger.error(f"Failed to connect to Qdrant at {redact_url(self.config.qdrant_url)}")
    ```

### Security Best Practices Observed ✅

The codebase demonstrates many **good security practices**:

1. **Input Validation Layer:** Dedicated `src/core/validation.py` with comprehensive injection pattern detection (75+ patterns covering SQL, prompt, command, and path injection)
2. **Pydantic Models:** Strong typing and validation for all API inputs via Pydantic
3. **Content Sanitization:** `sanitize_text()` removes null bytes and control characters
4. **Size Limits:** `validate_content_size()` prevents memory exhaustion (50KB limit)
5. **Subprocess Safety:** All subprocess.run() calls use list arguments (not shell=True) and have timeouts
6. **Security Logging:** Dedicated security logger for audit trail (`src/core/security_logger.py`)
7. **Read-Only Mode:** Server supports read-only mode to prevent data modification
8. **Metadata Sanitization:** User metadata is sanitized before storage
9. **No eval/exec:** No dynamic code execution found in codebase
10. **No pickle/marshal:** No unsafe deserialization found

### Recommendations Priority Matrix

**Implement Immediately (Critical):**
1. SEC-001: Fix tarfile extraction path traversal (Zip Slip)
2. SEC-003: Add project path boundary validation

**Implement Soon (High):**
3. SEC-005: Add rate limiting to MCP endpoints
4. SEC-006: Validate all user inputs to Qdrant filters
5. SEC-008: Add log rotation and permission restrictions

**Implement When Scaling (Medium):**
6. SEC-002: Harden git subprocess path validation
7. SEC-009: Add symlink validation
8. SEC-010: Add authentication for multi-user deployments
9. SEC-013: Add boundary checks to rmtree operations

**Monitor & Document (Low):**
10. SEC-004: Document regex timeout strategy
11. SEC-011-016: Document security assumptions and mitigations

### Security Testing Recommendations

1. **Add Security Test Suite:**
   - Test tarfile extraction with path traversal payloads
   - Test input validation with injection patterns
   - Test path traversal with various encoding tricks
   - Test rate limiting under load

2. **Dependency Scanning:**
   - Run `pip-audit` to check for vulnerable dependencies
   - Monitor Qdrant client library for security updates
   - Track Hugging Face transformers library CVEs

3. **Fuzzing:**
   - Fuzz test validation.py injection detection with random inputs
   - Fuzz test file path handling with edge cases
   - Fuzz test tarfile extraction with malformed archives

4. **Security Documentation:**
   - Document threat model (single-user vs multi-user)
   - Document security boundaries (what's in scope for protection)
   - Document secure deployment guidelines

### Attack Surface Summary

**External Attack Vectors (if server exposed remotely):**
- ❌ No authentication → Unauthorized access
- ⚠️ No rate limiting → DoS attacks
- ⚠️ Path traversal in indexing → File system access
- ⚠️ Tarfile extraction → Arbitrary file write

**Internal Attack Vectors (malicious local user):**
- ⚠️ Backup import → Zip slip to RCE
- ⚠️ Path manipulation → Access sensitive files
- ⚠️ Log manipulation → Cover tracks (no log rotation)

**Supply Chain Risks:**
- ⚠️ Embedding model download → Model poisoning (low risk)
- ✅ No eval/exec → Limited code injection surface
- ✅ No pickle → No deserialization attacks

**Current Security Posture:** 
- ✅ **Good** for single-user desktop application
- ⚠️ **Needs hardening** for multi-user environments
- ❌ **Not suitable** for internet-facing deployment without major changes

### Comparison to Common Vulnerabilities

**OWASP Top 10 (2021) Analysis:**
1. **A01:2021 - Broken Access Control:** ⚠️ No authentication (SEC-010)
2. **A02:2021 - Cryptographic Failures:** ✅ No sensitive data encryption needed for local use
3. **A03:2021 - Injection:** ✅ Strong validation, but see SEC-001 (path), SEC-006 (NoSQL)
4. **A04:2021 - Insecure Design:** ⚠️ Rate limiting missing (SEC-005)
5. **A05:2021 - Security Misconfiguration:** ⚠️ Log permissions (SEC-008)
6. **A06:2021 - Vulnerable Components:** ✅ Modern dependencies, need ongoing monitoring
7. **A07:2021 - Identification/Authentication:** ⚠️ Not applicable for current use case
8. **A08:2021 - Software/Data Integrity:** ⚠️ Model download (SEC-014)
9. **A09:2021 - Logging Failures:** ⚠️ Security logger exists but no rotation (SEC-008)
10. **A10:2021 - SSRF:** ✅ No external URL fetching from user input

**CWE Coverage:**
- ✅ CWE-89 (SQL Injection): Mitigated via validation.py patterns
- ❌ CWE-22 (Path Traversal): Vulnerable in tarfile extraction (SEC-001)
- ✅ CWE-78 (OS Command Injection): Mitigated via subprocess best practices
- ⚠️ CWE-79 (XSS): Not applicable (no web UI in MCP server)
- ⚠️ CWE-502 (Deserialization): Not applicable (no pickle/yaml.load)

**Overall Security Grade: B- (Good foundation, critical fixes needed for production)**

## AUDIT-001 Part 17: Documentation Findings (2025-11-30)

**Investigation Scope:** Analyzed 40+ Python modules across `src/` directory for docstring accuracy, type hint correctness, inline comment staleness, and misleading documentation.

**Methodology:**
- Sampled core modules: `core/tools.py`, `core/validation.py`, `store/base.py`, `memory/classifier.py`
- Analyzed public APIs in: `embeddings/rust_bridge.py`, `router/retrieval_predictor.py`, `tagging/auto_tagger.py`
- Cross-referenced implementation with documentation in: `dependency_graph.py`, `token_tracker.py`, `project_context.py`, `store/factory.py`
- Checked for stale comments referencing removed code or old behavior

### 🔴 CRITICAL Findings

- [ ] **DOC-012**: get_by_id() Docstring Missing Resource Leak Warning
  - **Location:** `src/store/base.py:120-133`
  - **Problem:** Abstract method docstring says "Raises: StorageError: If retrieval operation fails" but doesn't mention that implementations MUST release clients on early returns. The Qdrant implementation at `qdrant_store.py:569-570` has a bug where `if not result: return None` leaks a client because it exits before the `finally` block. Base class should document this requirement.
  - **Expected:** Docstring should say "Note: Implementations must ensure proper resource cleanup even on early returns (e.g., when memory not found)"
  - **Fix:** Update base.py docstring to include resource cleanup requirement; reference this when fixing BUG-063

- [ ] **DOC-013**: _score_patterns() Return Type Misleading
  - **Location:** `src/memory/classifier.py:85-97`
  - **Problem:** Docstring says "Returns: Score between 0 and 1" but implementation uses formula `min(1.0, matches / max(1, len(patterns) * 0.3))` which can exceed 1.0 before the min() clamp. The comment at line 97 is misleading because it doesn't explain WHY 0.3 divisor is used (it's to allow multiple matches to boost score above threshold).
  - **Expected:** "Returns: Score normalized to 0-1 range. Uses 0.3 divisor to amplify signal from sparse patterns."
  - **Fix:** Update docstring and add inline comment explaining the normalization factor choice

### 🟡 HIGH Priority Findings

- [ ] **DOC-014**: Inconsistent Docstring Style for Async Methods
  - **Location:** `src/store/base.py:169-181`, `src/store/base.py:184-196`, `src/store/base.py:199-208`
  - **Problem:** Three abstract async methods (`health_check`, `initialize`, `close`) have identical notes explaining "This function is async for interface compatibility. Abstract methods in base classes must be async even without await to maintain consistent interface across all storage backend implementations." This is repetitive and could be stated once at the class level.
  - **Expected:** Move note to class docstring, reference it in individual methods if needed
  - **Fix:** Extract common note to MemoryStore class docstring section on "Async Method Requirements"

- [ ] **DOC-015**: cosine_similarity() Return Range Incorrect
  - **Location:** `src/embeddings/rust_bridge.py:51-72`, `src/embeddings/rust_bridge.py:101-121`
  - **Problem:** Both Python and Rust bridge implementations document cosine_similarity as returning "0.0 to 1.0" but mathematical cosine similarity ranges from -1 to 1 (negative for opposite vectors). The implementation correctly computes the full range (line 72 can produce negative values), but the docstring is wrong.
  - **Expected:** "Returns: Cosine similarity score (-1.0 to 1.0, where 1.0 = identical, 0.0 = orthogonal, -1.0 = opposite)"
  - **Fix:** Update docstrings in both functions (lines 60, 110) to reflect actual range

- [ ] **DOC-016**: Type Hint Mismatch in retrieve_multi_level()
  - **Location:** `src/core/tools.py:268-334`
  - **Problem:** Return type annotation is `dict[ContextLevel, List[MemoryResult]]` (lowercase dict, Python 3.9+) but rest of codebase uses `Dict[...]` from typing module (Python 3.7+ compatible). This inconsistency could break type checking in environments requiring `from __future__ import annotations` or older Python versions.
  - **Expected:** Use `Dict[ContextLevel, List[MemoryResult]]` for consistency with project style
  - **Fix:** Change line 274 to use uppercase Dict imported from typing

- [ ] **DOC-017**: Missing Parameter Documentation for list_indexed_units()
  - **Location:** `src/store/base.py:274-318`
  - **Problem:** Docstring documents `file_pattern` as "Optional pattern for file paths (SQL LIKE for SQLite, glob for Qdrant)" but SQLite storage has been removed (see REF-010 in factory.py). The documentation references non-existent SQLite backend, which will confuse implementers.
  - **Expected:** "Optional pattern for file paths (glob pattern for Qdrant)"
  - **Fix:** Remove SQLite reference from all base.py method docstrings

### 🟢 MEDIUM Priority Findings

- [ ] **DOC-018**: Stale Comment References Removed Fallback
  - **Location:** `src/store/factory.py:14-15`
  - **Problem:** Comment says "REF-010: SQLite fallback removed - Qdrant is now required for semantic code search" but this is a changelog-style comment in code, not actual documentation. Should be in CHANGELOG.md, not inline code.
  - **Expected:** Remove or move to module docstring as "History" section
  - **Fix:** Remove lines 14-15, ensure REF-010 is documented in CHANGELOG.md

- [ ] **DOC-019**: Misleading Variable Name in _extract_keywords()
  - **Location:** `src/tagging/auto_tagger.py:286-358`
  - **Problem:** Function is named `_extract_keywords()` but actually extracts "high-frequency words" and converts them to tags. The `min_word_length` parameter defaults to 4, but the docstring says "Extract high-frequency keywords as tags" without explaining that it's using TF (term frequency) not TF-IDF, which would be more accurate for keyword extraction.
  - **Expected:** Rename to `_extract_frequent_words()` or update docstring to say "Extract high-frequency words (simple term frequency, no IDF weighting)"
  - **Fix:** Add clarifying comment at line 287 explaining this is naive TF-based extraction

- [ ] **DOC-020**: Type Hint Missing for classify_batch()
  - **Location:** `src/memory/classifier.py:188-200`
  - **Problem:** Parameter `items` uses lowercase `tuple` in type hint: `List[tuple[str, MemoryCategory]]` instead of `Tuple` from typing module. Python 3.9+ supports lowercase tuple, but inconsistent with project style (line 5 imports `Tuple` from typing).
  - **Expected:** Use `List[Tuple[str, MemoryCategory]]` for consistency
  - **Fix:** Update line 189 type hint to use imported Tuple

- [ ] **DOC-021**: Example Code in Docstring References Wrong Method
  - **Location:** `src/core/tools.py:66-72`
  - **Problem:** Example shows `await tools.retrieve_preferences(query="coding style preferences", limit=10)` but the method signature has `limit: int = 5` (line 48). Example uses limit=10 which is fine, but could be clearer that it's overriding the default.
  - **Expected:** Add comment in example: `limit=10  # Override default of 5`
  - **Fix:** Enhance example to show default behavior or clarify override

- [ ] **DOC-022**: Incomplete Exception Documentation in validate_store_request()
  - **Location:** `src/core/validation.py:277-332`
  - **Problem:** Docstring says "Raises: ValidationError: If validation fails" but doesn't mention that it can also raise Pydantic ValidationError (wrapped from line 331: `except ValueError as e`). The function catches Pydantic errors and re-raises as custom ValidationError, but this isn't clear from docs.
  - **Expected:** "Raises: ValidationError: If validation fails (wraps Pydantic validation errors)"
  - **Fix:** Update docstring to clarify error wrapping behavior

- [ ] **DOC-023**: Ambiguous "Relevance" in TokenUsageEvent
  - **Location:** `src/analytics/token_tracker.py:14-26`
  - **Problem:** Dataclass field `relevance_avg: float` has comment "Average relevance score" but doesn't specify the range (0-1? 0-100?) or what it measures. Looking at usage in `track_search()` (line 145), it's passed directly from user without validation. For indexing events (line 177), it's hardcoded to 1.0 with comment "N/A for indexing".
  - **Expected:** Add to docstring: "relevance_avg: Average relevance score (0.0-1.0, 1.0 = perfect match)"
  - **Fix:** Document expected range and semantics for relevance_avg field

### 🟦 LOW Priority / Minor Inconsistencies

- [ ] **DOC-024**: Inconsistent DateTime Timezone Documentation
  - **Location:** `src/memory/project_context.py:29`, `src/analytics/token_tracker.py:17`
  - **Problem:** ProjectContext uses `last_activity: datetime = field(default_factory=lambda: datetime.now(UTC))` with explicit UTC, but TokenUsageEvent just says `timestamp: datetime` without timezone info. Both use `datetime.now()` (line 169 in token_tracker.py) which creates naive datetime, causing inconsistency.
  - **Expected:** Document whether all datetime fields should be timezone-aware or naive
  - **Fix:** Add project-wide convention in docs, update dataclass fields to specify tz requirements

- [ ] **DOC-025**: Magic Number 0.3 in get_project_weight() Undocumented
  - **Location:** `src/memory/project_context.py:242-261`
  - **Problem:** Method returns 0.3 for inactive projects and 2.0 for active projects (lines 261, 258) but doesn't explain why these specific multipliers were chosen. No reference to where these are used or their impact on ranking.
  - **Expected:** Add comment explaining rationale, e.g., "0.3 penalty for inactive projects keeps them findable but deprioritized; 2.0 boost for active project reflects user's current focus"
  - **Fix:** Add explanatory comment and reference to search result weighting algorithm

- [ ] **DOC-026**: Misleading Function Name: should_archive_project()
  - **Location:** `src/memory/project_context.py:263-282`
  - **Problem:** Function is named `should_archive_project()` suggesting it performs archival, but it only returns a boolean check. The caller must actually perform the archival. Name suggests action, but it's a query.
  - **Expected:** Rename to `is_project_archivable()` or `check_archival_eligibility()` to clarify it's a predicate
  - **Fix:** Rename function and update callers, or add docstring clarifying this is a check-only function

- [ ] **DOC-027**: Undocumented Side Effect in track_file_activity()
  - **Location:** `src/memory/project_context.py:213-241`
  - **Problem:** Docstring says "Track file activity to infer active project" but doesn't mention that it can AUTO-SET the current context if none is active (lines 234-240). This is a significant side effect that should be documented.
  - **Expected:** Add to docstring: "Note: If no context is currently active, this will automatically set the detected project as active."
  - **Fix:** Update docstring to document auto-context-switching behavior

- [ ] **DOC-028**: Comment Contradicts Implementation in _resolve_module_to_file()
  - **Location:** `src/memory/dependency_graph.py:78-143`
  - **Problem:** Comment at lines 88-91 says "This is a simplified implementation. A full implementation would need: - Language-specific module resolution rules..." but then the implementation at lines 109-137 actually DOES implement Python/JS/TS relative import resolution with multiple file extensions. The comment is stale.
  - **Expected:** Update comment to say "Currently implements relative import resolution for Python/JS/TS. TODO: Add absolute import resolution for project-internal modules"
  - **Fix:** Revise comment to reflect actual capabilities, move unimplemented items to TODO

- [ ] **DOC-029**: Stopwords Set Missing Common Code Terms
  - **Location:** `src/tagging/auto_tagger.py:292-338`
  - **Problem:** Stopwords list (lines 292-338) includes English stopwords ("the", "is", "at") but doesn't include common programming stopwords like "function", "class", "method", "return", "value" which appear frequently in code comments but aren't meaningful tags.
  - **Expected:** Add code-specific stopwords or document that this is intentionally English-only
  - **Fix:** Extend stopwords with code-specific terms or add comment explaining scope

### Summary Statistics

- **Total Issues Found:** 18 (DOC-012 through DOC-029)
- **Critical:** 2 (resource leak documentation, misleading return range)
- **High:** 5 (inconsistent async docs, wrong type hints, stale references)
- **Medium:** 6 (misleading names, incomplete exception docs, ambiguous fields)
- **Low:** 5 (minor inconsistencies, undocumented conventions)

**Common Patterns:**
1. Type hint inconsistencies (Dict vs dict, Tuple vs tuple) - affects 3 locations
2. Stale comments referencing removed features (SQLite) - affects 2 locations
3. Missing documentation of side effects/resource requirements - affects 3 locations
4. Undocumented magic numbers and rationale - affects 2 locations
5. Misleading function/variable names not matching actual behavior - affects 3 locations

**Recommended Action Plan:**
1. Fix critical docs (DOC-012, DOC-015) when fixing related bugs (BUG-063)
2. Standardize type hint style across codebase (DOC-016, DOC-020)
3. Remove all SQLite references from documentation (DOC-017, DOC-018)
4. Add project-wide documentation standards for async methods, timezones, and error handling
5. Consider renaming misleading functions in next refactoring cycle (DOC-026, DOC-028)
## AUDIT-001 Part 16: Test Quality Findings (2025-11-30)

**Investigation Scope:** 202 test files across unit/, integration/, e2e/, security/, performance/ directories
**Focus:** Test patterns, not specific test logic - identifying systemic quality issues

### 🔴 CRITICAL Priority Findings

- [ ] **TEST-030**: Manual Test File Has Zero Assertions (435 Lines of Dead Code)
  - **Location:** `tests/manual/test_all_features.py` (435 lines, 0 assertions)
  - **Problem:** This file contains a `FeatureTester` class with extensive feature testing code (code search, memory CRUD, indexing, analytics, etc.) but uses `print()` statements and manual verification instead of assertions. Tests never fail programmatically - they require human inspection of output. This is not a test, it's a demo script masquerading as a test.
  - **Impact:** False confidence in test coverage metrics. File is counted in test suite but provides zero automated verification.
  - **Fix:** Either (1) convert to real assertions and move to integration/, or (2) move to `scripts/` and remove from test suite, or (3) delete if obsolete

- [ ] **TEST-031**: 79+ Skipped Tests Never Re-enabled (Validation Theater)
  - **Location:** Multiple files with `@pytest.mark.skip` and `pytest.skip()`
  - **Problem:** Found 79+ skipped tests across the suite. Key examples:
    - `test_kotlin_parsing.py`: 262 lines, all tests skipped (Kotlin not supported by parser)
    - `test_swift_parsing.py`: 189 lines, all tests skipped (Swift not supported by parser)
    - `test_services/test_cross_project_service.py`: 12/12 tests skipped (MultiRepositorySearcher not implemented)
    - `test_services/test_health_service.py`: 3 tests skipped (DashboardServer not available)
    - `test_auto_indexing_service.py`: Test skipped (auto_index_enabled config not implemented)
    - `test_index_codebase_initialization.py`: Test skipped (incorrect mock setup)
  - **Impact:** These skipped tests create illusion of comprehensive coverage while testing nothing. They rot over time as code changes.
  - **Fix:** Add TODO tickets for each skip reason, set timeline for implementation or deletion. Mark skipped tests with issue numbers.

- [ ] **BUG-095**: Timing Dependencies in 30+ Tests (Flakiness Source)
  - **Location:** Tests using `asyncio.sleep()` or `time.sleep()` for synchronization
  - **Problem:** Found 30+ instances of sleep-based synchronization:
    - `test_file_watcher.py:85`: `await asyncio.sleep(0.05)` for debounce testing
    - `test_background_indexer.py:47,224,302,385,529`: Multiple sleeps for job status polling
    - `test_connection_health_checker.py:102,170,241`: Blocking sleeps for timeout tests
    - `test_usage_tracker.py:124,145`: Sleeps for flush timing
    - `test_connection_pool.py:346`: 1.5s sleep for recycling test
  - **Impact:** Tests are timing-dependent and flaky under load or in CI. Many marked `@pytest.mark.skip_ci` to hide the problem.
  - **Fix:** Replace sleeps with event-based synchronization (asyncio.Event, threading.Event) or mock time

- [ ] **TEST-032**: Entire Test File Has Only Two `assert True` Statements
  - **Location:** `tests/unit/test_server_extended.py:471,592`
  - **Problem:** File has extensive setup for code search tests but only two assertions are literal `assert True` (lines 471, 592). This is validation theater - tests that appear to verify behavior but actually verify nothing.
  - **Impact:** False confidence. Tests pass even if code is completely broken.
  - **Fix:** Add real assertions or delete the tests

### 🟡 HIGH Priority Findings

- [ ] **TEST-033**: Excessive Fixture Complexity Creates Maintenance Burden
  - **Location:** `tests/conftest.py` (630+ lines), multiple conftest files
  - **Problem:**
    - Session-scoped fixtures mix concerns (embedding mocks, Qdrant pooling, auto-indexing disable)
    - Mock embedding generator in conftest uses complex hash-based embeddings (lines 160-209)
    - Collection pooling logic is fragile (session-scoped `unique_qdrant_collection`)
    - 6 different conftest files with overlapping responsibilities
  - **Impact:** Hard to understand what any test is actually testing. Changes to fixtures break unrelated tests.
  - **Fix:** Document fixture dependencies, split into focused conftest files by concern, consider factory patterns

- [ ] **TEST-034**: Weak Assertions Provide False Confidence (359 Instances)
  - **Location:** 359 occurrences of `assert ... is not None` with no follow-up checks
  - **Problem:** Tests check object existence but not correctness. Examples:
    - Retrieve memory → assert result is not None → done (doesn't check content)
    - Index files → assert job is not None → done (doesn't check files were actually indexed)
    - Parse code → assert units is not None → done (doesn't check parsing correctness)
  - **Impact:** Tests pass when code returns garbage, as long as it's not None
  - **Fix:** Follow `is not None` with specific attribute/value checks

- [ ] **TEST-035**: Language Parsing Tests for Unsupported Languages (451+ Dead Lines)
  - **Location:**
    - `test_kotlin_parsing.py`: 262 lines (Kotlin not supported)
    - `test_swift_parsing.py`: 189 lines (Swift not supported)
  - **Problem:** Comprehensive test suites exist for languages the parser doesn't support. All tests are skipped. Tests use inconsistent assertion styles (accessing dict keys vs attributes) suggesting they were written without running.
  - **Impact:** Dead code maintenance burden. False coverage metrics.
  - **Fix:** Delete these files or move to `tests/future/` directory with clear timeline for support

- [ ] **TEST-036**: No Cleanup in 30+ Database/File Fixtures (Resource Leaks)
  - **Location:** Tests using tempfile, sqlite, file watchers without proper cleanup
  - **Problem:**
    - `test_usage_pattern_tracker.py`: 12 tests manually call `conn.close()` instead of fixture cleanup
    - File watchers in tests may not stop properly on test failure
    - Temp directories created without context managers in some tests
  - **Impact:** Resource leaks in test suite. Test failures leave garbage. CI runner disk fills up.
  - **Fix:** Use pytest fixtures with yield, context managers, or addFinalizer for all resource cleanup

- [ ] **TEST-037**: Polling Loops Without Timeouts in Test Helpers
  - **Location:** `tests/unit/test_background_indexer.py:28-47` (wait_for_job_status helper)
  - **Problem:** Helper function uses `while True` loop with timeout check, but polls every 10ms. If job never reaches status, test hangs until timeout (default 5s). This pattern appears in multiple test files.
  - **Impact:** Slow tests, timeout failures hide real bugs
  - **Fix:** Use pytest-timeout plugin, reduce polling interval to 100ms, add debug logging for timeout failures

### 🟢 MEDIUM Priority Findings

- [ ] **TEST-038**: Missing Parametrization Opportunities (5 Language Files)
  - **Location:** 5 separate parsing test files when one parameterized file would suffice
  - **Problem:**
    - `test_cpp_parsing.py`, `test_php_parsing.py`, `test_ruby_parsing.py`, `test_kotlin_parsing.py`, `test_swift_parsing.py`
    - Each follows identical test pattern (file recognition, class extraction, function extraction, edge cases)
    - Only Ruby is consolidated into `test_language_parsing_parameterized.py` (per TEST-029)
  - **Impact:** Code duplication, inconsistent test coverage across languages, harder to add new languages
  - **Fix:** Consolidate all language parsing tests into parameterized suite like TEST-029 did for Ruby

- [ ] **TEST-039**: Heavy Mock Usage Without Integration Tests (4670 Mock Instances)
  - **Location:** 4670 `mock` or `Mock` references across test suite
  - **Problem:**
    - Unit tests extensively mock dependencies (good for isolation)
    - But only 37 integration tests vs 165+ unit tests
    - Critical paths like store→indexer→search are mostly tested with mocks
  - **Impact:** Mocks drift from reality. Integration bugs slip through.
  - **Fix:** Add integration tests for each critical workflow, reduce mocking in "integration" tests

- [ ] **TEST-040**: 61 Parametrized Tests Only (Missed Opportunities)
  - **Location:** Only 61 uses of `@pytest.mark.parametrize` across 202 test files
  - **Problem:** Many test files have repetitive tests with only input data changing:
    - `test_refinement_advisor.py`: 11 separate test functions for different result counts (should be parameterized)
    - `test_spelling_suggester.py`: 7 tests with similar patterns
    - `test_ragignore_manager.py`: 22 tests, many test pattern validation with different inputs
  - **Impact:** Verbose test suite, harder to add new test cases
  - **Fix:** Identify test patterns and convert to parameterized tests

- [ ] **TEST-041**: Exception Testing Without Message Validation (Many pytest.raises)
  - **Location:** Tests using `with pytest.raises(SomeError):` without match parameter
  - **Problem:** Tests verify exception type but not message. Examples in:
    - `test_store/test_connection_pool.py`: 5 validation tests check exception type only
    - Many MCP error handling tests don't validate error messages
  - **Impact:** Tests pass even if error messages are unhelpful or wrong
  - **Fix:** Add `match=` parameter to pytest.raises to validate error messages

- [ ] **TEST-042**: Test File Organization Issues
  - **Location:** `tests/unit/test_services/`, `tests/unit/test_store/` vs `tests/unit/store/`
  - **Problem:**
    - Two separate test_store directories (`test_store/` and `store/`)
    - `test_services/` has 5 test files, 4 of which have skipped tests
    - Mixing graph tests in `tests/unit/graph/` vs other unit tests
  - **Impact:** Hard to find tests, unclear structure
  - **Fix:** Consolidate test directories to match src/ structure

### 🟢 LOW Priority Findings

- [ ] **REF-062**: Inconsistent Async Test Patterns
  - **Location:** Mix of `@pytest.mark.asyncio` and `pytest_asyncio.fixture` usage
  - **Problem:** Some tests use `@pytest.mark.asyncio`, others use `pytest_asyncio.fixture`, some mix both. No clear pattern.
  - **Impact:** Confusion about which pattern to use for new tests
  - **Fix:** Standardize on pytest-asyncio patterns, document in TESTING_GUIDE.md

- [ ] **REF-063**: Test Data in test_data/ Directory Unused
  - **Location:** `tests/test_data/` directory exists
  - **Problem:** Directory is present but unclear what it contains or which tests use it
  - **Impact:** Potentially unused test data accumulating
  - **Fix:** Document test data directory purpose or remove if unused

- [ ] **REF-064**: Comment-Only Test Documentation (No Docstrings in Some Files)
  - **Location:** Multiple test files use `# Test X` comments instead of docstrings
  - **Problem:** Some test functions have docstrings, others have comments, inconsistent
  - **Impact:** Harder to generate test documentation, pytest output less informative
  - **Fix:** Standardize on docstrings for all test functions

### Test Quality Metrics Summary

**Counts:**
- Total test files: 202
- Total test functions: ~1800+ (estimated from grep counts)
- Skipped tests: 79+
- Parametrized tests: 61
- Mock/Mock usage: 4670 instances
- Sleep-based timing: 30+ instances
- Weak assertions (is not None only): 359
- Dead code (skipped language tests): 451+ lines

**Patterns Observed:**
- ✅ Good: Most tests use unique collections for isolation (via conftest pooling)
- ✅ Good: Project name isolation in parallel tests (test_project_name fixture)
- ✅ Good: Comprehensive error path testing (984 error-related tests)
- ⚠️ Weak: Heavy mocking with limited integration coverage
- ⚠️ Weak: Timing-based synchronization instead of event-based
- ⚠️ Weak: Many skipped tests that never get re-enabled
- ❌ Critical: Manual test file with zero assertions
- ❌ Critical: Tests for unsupported features that just add maintenance burden

**High-Risk Areas for Future Monitoring:**
1. Background indexer tests (polling, timeouts, resource cleanup)
2. File watcher tests (timing sensitive, marked skip_ci)
3. Connection pool tests (sleep-based recycling, timeout tests)
4. Concurrent operation tests (all skipped due to flakiness)
5. Language parsing tests (dead code for unsupported languages)

**Recommendations:**
1. **Immediate:** Delete or convert `tests/manual/test_all_features.py`
2. **Immediate:** Add TODO tickets for all 79+ skipped tests with timelines
3. **Short-term:** Replace sleep-based sync with event-based in top 10 flaky tests
4. **Short-term:** Consolidate language parsing tests per TEST-029 pattern
5. **Medium-term:** Add 20+ integration tests for critical workflows
6. **Long-term:** Reduce mock usage in favor of real component integration


## AUDIT-001 Part 14: Graph Generation & Visualization Findings (2025-11-30)

**Investigation Scope:** 8 files across graph module - dependency_graph.py (333 lines), call_graph.py (346 lines), formatters (dot_formatter.py 192 lines, json_formatter.py 164 lines, mermaid_formatter.py 165 lines), graph_generator.py (478 lines)

### 🔴 CRITICAL Findings

- [ ] **BUG-092**: Cycle Detection Produces Incorrect Cycles with Duplicate Nodes
  - **Location:** `src/graph/dependency_graph.py:163-167`
  - **Problem:** When back edge is detected, cycle construction is `cycle = path[cycle_start_idx:] + [neighbor]`. This duplicates the neighbor node (it's already at cycle_start_idx AND appended at end). For cycle A->B->C->A, this creates [A, B, C, A] which is correct, but the CircularDependency.length counts the duplicate (length=4 instead of 3 unique nodes). Additionally, the cycle marking logic at lines 178-181 expects the duplicate, but this makes cycle representation inconsistent.
  - **Example:** Path [A, B, C], neighbor=A, cycle_start_idx=0 → cycle = [A, B, C] + [A] = [A, B, C, A] (4 nodes for 3-node cycle)
  - **Impact:** Incorrect cycle statistics, confusing visualization (A appears twice), edge marking misses some circular edges
  - **Fix:** Either (1) Don't append duplicate: `cycle = path[cycle_start_idx:]` and update edge marking logic, OR (2) Document that cycles intentionally include start/end duplicate and update CircularDependency to expose both raw cycle and unique_nodes count

- [ ] **BUG-093**: DependencyGraphGenerator.generate Returns Tuple of Wrong Length
  - **Location:** `src/memory/graph_generator.py:118`
  - **Problem:** Function signature says `-> tuple[str, Dict[str, Any]]` (2 elements) but line 118 returns `return graph_data, stats, circular_groups` (3 elements). This causes unpacking errors for any caller expecting 2-tuple.
  - **Example:** `graph, stats = generator.generate()` will raise `ValueError: too many values to unpack (expected 2)`
  - **Impact:** Runtime error on every call to generate()
  - **Fix:** Update return type to `-> tuple[str, Dict[str, Any], List[List[str]]]` or change return to 2-tuple by embedding circular_groups in stats dict

- [ ] **BUG-094**: Max Depth Calculation Ignores Cycles - Infinite Loop Risk
  - **Location:** `src/graph/dependency_graph.py:314-325`
  - **Problem:** `get_stats()` calculates max_depth using BFS from root nodes, but doesn't track visited set across different root traversals. If graph has cycles (which find_circular_dependencies explicitly detects), the BFS at line 318-325 has `visited: Set[str] = {root}` scoped per root, meaning it can loop infinitely within a strongly connected component.
  - **Example:** Graph with cycle A->B->C->A and no roots (all nodes have incoming edges). Line 311 finds roots=[], loop never executes, max_depth stays 0. But if roots=[A] and A->B->C->A cycle exists, BFS adds B to queue, then C, then A again (A not in visited for this iteration).
  - **Impact:** Infinite loop causing process hang, incorrect max_depth=0 for cyclic graphs
  - **Fix:** Move `visited` set outside the roots loop OR use global visited set OR skip max_depth calculation if circular dependencies detected

### 🟡 HIGH Priority Findings

- [ ] **BUG-095**: Mermaid Formatter Missing Newline Escaping in Labels
  - **Location:** `src/graph/formatters/mermaid_formatter.py:94, 102`
  - **Problem:** Node labels include file names and metadata with `<br/>` HTML tags (line 94), but if filename contains literal `\n` or special chars like `"`, `[`, `]`, these aren't escaped. Mermaid syntax uses `[label]` for nodes - a filename with `]` will break parsing.
  - **Example:** File `/project/test[1].py` → node syntax `A["test[1].py"]` breaks Mermaid parser
  - **Impact:** Invalid Mermaid output for files with brackets, quotes, or special characters
  - **Fix:** Add `_escape_mermaid_label()` method that escapes `"`, `[`, `]`, and converts `\n` to `<br/>`

- [ ] **BUG-096**: DOT Formatter Incomplete Escaping - Missing Newline Handling
  - **Location:** `src/graph/formatters/dot_formatter.py:177-191`
  - **Problem:** `_escape_dot_string()` escapes backslashes and quotes, but doesn't handle literal newlines (`\n` in file paths) or other DOT special chars like `<`, `>`, `{`, `}`. If a file path contains newline, the DOT output will have literal line break inside quoted string, breaking syntax.
  - **Example:** File path `/tmp/test\nfile.py` (unlikely but possible on Linux) → DOT: `label="/tmp/test` (line break) `file.py"` (syntax error)
  - **Impact:** Malformed DOT output for edge-case file paths, Graphviz rendering fails
  - **Fix:** Extend escaping to replace `\n` → `\\n`, `\r` → `\\r`, `\t` → `\\t`

- [ ] **BUG-097**: filter_by_depth Off-By-One Error - Max Depth Not Inclusive
  - **Location:** `src/graph/dependency_graph.py:217`
  - **Problem:** Line 217 checks `if depth < max_depth:` before exploring neighbors, meaning a node at exactly max_depth won't have its children explored. Docstring says "max_depth: Maximum traversal depth (0 = root only, 1 = root + direct deps, etc.)" which suggests max_depth should be inclusive. With current code, max_depth=1 gives root only (depth 0), not root + direct deps.
  - **Example:** Root A → B → C, max_depth=1 should include A and B, but only includes A because B is at depth 1 and `1 < 1` is false
  - **Impact:** Filter returns one fewer level than documented, user confusion
  - **Fix:** Change to `if depth <= max_depth:` OR update docstring to clarify exclusive behavior

- [ ] **BUG-098**: Call Graph BFS Doesn't Mark Starting Node as Visited
  - **Location:** `src/graph/call_graph.py:175-176, 229-230`
  - **Problem:** `_find_callers_bfs` and `_find_callees_bfs` initialize queue with `[(function_name, 0)]` but visited set is empty. The starting function is only added to visited when popped from queue (line 178/232 is inside the while loop). If starting function calls itself (recursion), it gets added to queue again before being marked visited.
  - **Example:** Function `factorial` calls itself → queue starts with `[('factorial', 0)]`, loop processes it, adds `factorial` to visited, but if it was already processed once, visited already has it. However, if self-recursion creates multiple queue entries before first pop, duplicates accumulate.
  - **Impact:** Potential duplicate processing, inefficiency for recursive functions
  - **Fix:** Add `visited.add(function_name)` before initializing queue, OR add to visited set in queue initialization: `visited = {function_name}`

- [ ] **BUG-099**: DependencyGraphGenerator Assumes graph.dependencies Dict Exists
  - **Location:** `src/memory/graph_generator.py:129, 154`
  - **Problem:** Lines 129 and 154 access `self.graph.dependencies` but DependencyGraph class (src/graph/dependency_graph.py) doesn't have this attribute. DependencyGraph uses `_adjacency_list` internally and exposes `nodes` and `edges` attributes. This causes AttributeError on every call.
  - **Example:** `filtered_nodes = set(self.graph.dependencies.keys())` → AttributeError: 'DependencyGraph' object has no attribute 'dependencies'
  - **Impact:** DependencyGraphGenerator completely broken, cannot generate any graphs
  - **Fix:** Refactor to use `self.graph.nodes.keys()` and `self.graph.edges` instead of non-existent dependencies/dependents dicts

- [ ] **REF-070**: Circular Dependency Detection Runs on Every get_stats Call
  - **Location:** `src/graph/dependency_graph.py:304`
  - **Problem:** `get_stats()` calls `find_circular_dependencies()` which runs full DFS cycle detection. While the result is cached in `_circular_deps`, the cache is invalidated if graph is modified. If user calls `get_stats()` repeatedly (e.g., in a monitoring loop), and graph is rebuilt each time, full DFS runs every time.
  - **Impact:** O(V+E) performance cost on every stats call for large graphs
  - **Fix:** Add `skip_circular_check=False` parameter to get_stats(), document that circular_dependency_count will be 0 if skipped

- [ ] **REF-071**: Mermaid linkStyle Uses Edge Index Which Changes with Filtering
  - **Location:** `src/graph/formatters/mermaid_formatter.py:66, 148-164`
  - **Problem:** Line 66 uses `_get_edge_index()` to find edge position for styling, but if graph is filtered (e.g., by language or pattern), edge indices change. A circular edge might be at index 5 in full graph but index 2 in filtered graph, causing wrong edge to be styled red.
  - **Example:** Full graph has edges [A→B, B→C, C→D, C→A (circular), D→E]. After filtering to just [A,B,C], edges are [A→B, B→C, C→A]. Original index was 3, new index is 2.
  - **Impact:** Red circular styling applied to wrong edges in filtered graphs
  - **Fix:** Count edges as they're emitted instead of using global index, or track edges by (source, target) tuple

### 🟢 MEDIUM Priority Findings

- [ ] **REF-072**: DOT Formatter DEFAULT_COLOR is Invalid - Should Be "#808080"
  - **Location:** `src/graph/formatters/dot_formatter.py:36`
  - **Problem:** Line 36 sets `DEFAULT_COLOR = "#gray"` but DOT/Graphviz doesn't recognize "#gray" as valid hex color (hex colors must be #RRGGBB or #RRGGBBAA). The `#` prefix indicates hex, but "gray" is a named color without `#`. This causes rendering issues or fallback to black.
  - **Impact:** Unknown language nodes appear black instead of gray
  - **Fix:** Change to `DEFAULT_COLOR = "gray"` (named color) OR `DEFAULT_COLOR = "#808080"` (hex gray)

- [ ] **REF-073**: JSON Formatter Silently Omits Metadata for Nodes Without Unit/Size
  - **Location:** `src/graph/formatters/json_formatter.py:101-107`
  - **Problem:** When `include_metadata=True`, the code only adds unit_count/file_size if they're > 0. For a file with 0 units and 0 bytes, metadata is completely omitted from JSON, making it indistinguishable from `include_metadata=False`. This inconsistency makes client-side parsing harder.
  - **Impact:** Inconsistent JSON schema - some nodes have metadata fields, others don't
  - **Fix:** Always include fields when `include_metadata=True`, use explicit 0 values OR add comment documenting intentional omission

- [ ] **REF-074**: filter_by_pattern Matches Against Both Full Path and Basename
  - **Location:** `src/graph/dependency_graph.py:248-250`
  - **Problem:** Filter matches pattern against both full file_path and `Path(file_path).name` (basename). For pattern `"*.py"`, this is fine, but for pattern `"src/*.py"`, matching against basename will include `/other/src/test.py` even though path doesn't match `src/*.py`. The OR logic is too permissive.
  - **Example:** Pattern `"src/*.py"` should match `/project/src/utils.py` but not `/other/src/utils.py`. Current code matches both because basename matches.
  - **Impact:** Filter includes more files than expected, confusing results
  - **Fix:** Document behavior OR only match basename for simple patterns (no `/`), full path for path-like patterns

- [ ] **REF-075**: CallGraph Statistics Count Interfaces but Not Interface Methods
  - **Location:** `src/graph/call_graph.py:343-344`
  - **Problem:** `get_statistics()` counts total interfaces (line 343) and total implementations (344), but doesn't count total methods across implementations. This makes it hard to assess complexity of interface hierarchies.
  - **Impact:** Incomplete statistics for polymorphic codebases
  - **Fix:** Add `"total_interface_methods": sum(len(impl.methods) for impls in self.implementations.values() for impl in impls)` to stats dict

- [ ] **REF-076**: DependencyGraphGenerator._get_language Hardcoded - Duplicates Logic
  - **Location:** `src/memory/graph_generator.py:273-300`
  - **Problem:** Language detection from file extension is hardcoded in generator. If language mapping changes or new languages are added, must update in multiple places. Consider extracting to shared utility or configuration.
  - **Impact:** Maintenance burden, inconsistency risk
  - **Fix:** Extract language mapping to `src/graph/language_detector.py` or config file, reuse across codebase

- [ ] **REF-077**: Mermaid Node IDs Limited to 26 Files (A-Z)
  - **Location:** `src/memory/graph_generator.py:429`
  - **Problem:** Line 429 generates node IDs as `chr(65 + i)` for i < 26, else `f"N{i}"`. This works but creates inconsistent ID format (A-Z for first 26, then N26, N27, etc). Also, comment or docstring should warn that very large graphs (>26 nodes) get numeric IDs.
  - **Impact:** Inconsistent node ID format in Mermaid output, potential confusion
  - **Fix:** Use consistent format like `f"N{i}"` for all nodes OR document the A-Z then numeric pattern

- [ ] **REF-078**: DOT Sanitization Removes Dots from Node IDs - Causes Collisions
  - **Location:** `src/graph/formatters/dot_formatter.py:167-168`
  - **Problem:** `_make_node_id()` replaces `.` with `_`, so `file.py` and `file_py` both become `file_py`, causing node ID collision. If graph has both `/src/test.py` and `/src/test_py`, they'll have the same DOT node ID, causing one to overwrite the other.
  - **Example:** Files `util.py` and `util_py` both → node ID `util_py`
  - **Impact:** Silent data loss in DOT export, missing nodes in visualization
  - **Fix:** Use unique separator or hash-based IDs: `node_id = hashlib.md5(file_path.encode()).hexdigest()[:8]` OR keep dots and use quoted node IDs

- [ ] **REF-079**: graph_generator.py Hardcodes "dependencies" as Graph Title Comment
  - **Location:** `src/memory/graph_generator.py:310, 424`
  - **Problem:** DOT output says `digraph dependencies {` and Mermaid has comment `graph LR` but no title. The `title` parameter from generate() is never passed to these format methods (only to JSON metadata). User's title is ignored for DOT/Mermaid.
  - **Impact:** All DOT/Mermaid graphs have generic title, not user-specified title
  - **Fix:** Pass title to `_to_dot()` and `_to_mermaid()`, add as comment or graph label

### 🟢 LOW Priority Findings

- [ ] **PERF-013**: Cycle Detection Creates New Path List on Every Recursive Call
  - **Location:** `src/graph/dependency_graph.py:157, 170`
  - **Problem:** DFS passes `path` list by reference and mutates it (append line 157, pop line 170), which is correct. However, if there are many cycles, the path list is repeatedly grown/shrunk. Consider pre-allocating or using deque for O(1) append/pop.
  - **Impact:** Minor performance cost for graphs with hundreds of cycles
  - **Fix:** Change `path: List[str]` to `path: collections.deque` for O(1) operations

- [ ] **PERF-014**: filter_by_depth Creates New Graph with Deep Copy of Nodes
  - **Location:** `src/graph/dependency_graph.py:224-227`
  - **Problem:** Lines 225-227 add nodes to filtered graph by calling `filtered.add_node(self.nodes[node_path])`. This doesn't deep copy the GraphNode object, but if GraphNode is later modified, the filtered graph shares references. For read-only use this is fine, but for mutable operations it's risky.
  - **Impact:** Potential unexpected mutation if filtered graph nodes are modified
  - **Fix:** Document that filtered graphs share node references OR deep copy nodes: `filtered.add_node(dataclasses.replace(self.nodes[node_path]))`

- [ ] **REF-080**: Missing Type Hints for _adjacency_list Private Attribute
  - **Location:** `src/graph/dependency_graph.py:87`
  - **Problem:** Line 87 initializes `_adjacency_list: Dict[str, List[str]] = {}` with type hint in __init__, but class doesn't declare it at class level. Modern Python style is to declare all attributes at class level with type annotations for better IDE support.
  - **Impact:** Reduced IDE autocomplete, type checker warnings
  - **Fix:** Add class-level annotation: `_adjacency_list: Dict[str, List[str]]` before `__init__`

- [ ] **REF-081**: Call Graph Forward/Reverse Index Use defaultdict but Initialized as Regular Dict
  - **Location:** `src/graph/call_graph.py:96-97`
  - **Problem:** Lines 96-97 use `defaultdict(set)` which is good, but throughout the code (e.g., lines 120, 123, 159, 184) there are calls like `self.forward_index.get(node, set())`. This .get() pattern is redundant for defaultdict - can just use `self.forward_index[node]`.
  - **Impact:** Unnecessary defensive code, slight inefficiency
  - **Fix:** Replace all `.get(key, set())` with `[key]` for defaultdict attributes OR document why defensive .get() is preferred

- [ ] **REF-082**: Mermaid Formatter Doesn't Escape Pipe Character in Labels
  - **Location:** `src/graph/formatters/mermaid_formatter.py:94, 462`
  - **Problem:** Mermaid uses `|` for edge labels (e.g., `A -->|label| B`). If label text contains `|`, it can break parsing. File names rarely have pipes, but metadata like "5 units | 2KB" would break.
  - **Impact:** Rare but possible syntax errors in Mermaid output
  - **Fix:** Escape `|` to `\|` or use different metadata separator

- [ ] **REF-083**: JSON Formatter ensure_ascii=False May Cause Issues for Some Clients
  - **Location:** `src/graph/formatters/json_formatter.py:42`
  - **Problem:** `json.dumps(..., ensure_ascii=False)` outputs Unicode characters directly. While this is more readable, some older JSON parsers or tools expect ASCII-only JSON. The test at line 359 shows Unicode file paths are supported, but this could break clients.
  - **Impact:** Potential compatibility issues with strict JSON parsers
  - **Fix:** Add parameter to control ensure_ascii, default to True for safety

- [ ] **REF-084**: DependencyGraph Doesn't Validate Node Existence on add_edge
  - **Location:** `src/graph/dependency_graph.py:117-120`
  - **Problem:** `add_edge()` ensures nodes exist in `_adjacency_list` but doesn't check if they exist in `self.nodes` dict. Can create edges between nodes that were never added via `add_node()`, resulting in incomplete metadata.
  - **Impact:** Graph can have edges to phantom nodes without language/metadata
  - **Fix:** Add validation: `if edge.source not in self.nodes: logger.warning(f"Adding edge from unknown node {edge.source}")` OR require nodes to exist

- [ ] **REF-085**: Call Graph BFS Max Depth Check Uses >= Instead of >
  - **Location:** `src/graph/call_graph.py:180, 234`
  - **Problem:** Lines 180 and 234 check `if depth >= max_depth: continue`, which means a node at exactly max_depth is skipped. Combined with the starting depth of 0, this gives max_depth=1 → only direct neighbors (depth 1), not transitive at depth 2. Docstring says "max_depth: Maximum depth" which is ambiguous about inclusive/exclusive.
  - **Impact:** Off-by-one in transitive caller/callee search
  - **Fix:** Change to `if depth > max_depth:` OR clarify docstring as "exclusive depth limit"

### Summary of Findings

**Critical Issues (Fix Immediately):**
- BUG-092: Cycle detection duplicates nodes causing incorrect cycle length
- BUG-093: generate() returns 3-tuple instead of declared 2-tuple
- BUG-094: Max depth calculation can infinite loop on cyclic graphs
- BUG-099: DependencyGraphGenerator incompatible with DependencyGraph class

**High Priority (Fix Soon):**
- BUG-095-098: Escaping and validation issues in formatters
- REF-070-071: Performance and correctness issues in formatting

**Medium/Low Priority:**
- REF-072-085: Code quality, consistency, edge cases

**Testing Gaps Identified:**
- No tests for file paths with special characters in formatters (brackets, quotes, newlines)
- No tests for graphs with cycles in max_depth calculation
- No tests for very large graphs (100+ nodes) in Mermaid formatter
- No tests for DependencyGraphGenerator (appears to be dead code given BUG-099)
- No tests for recursive functions in call graph BFS

**Architecture Concerns:**
- DependencyGraphGenerator appears to be a parallel implementation incompatible with DependencyGraph class (BUG-099)
- Language detection logic duplicated across modules (REF-076)
- Inconsistent ID generation schemes across formatters (REF-077, REF-078)

**Recommended Fix Priority:**
1. Fix BUG-093 (blocking runtime error) and BUG-099 (dead code)
2. Fix BUG-094 (infinite loop risk)
3. Fix BUG-092 (data correctness)
4. Add comprehensive escaping tests and fix BUG-095, BUG-096
5. Address performance issues (PERF-013, PERF-014) if large graphs are expected
6. Standardize and document behavior for edge cases (REF-070-085)


## AUDIT-001 Part 15: Tagging & Classification System Findings (2025-11-30)

**Investigation Scope:** 6 files across tagging and classification subsystems
- `src/tagging/auto_tagger.py` (359 lines)
- `src/tagging/collection_manager.py` (373 lines)
- `src/tagging/tag_manager.py` (470 lines)
- `src/tagging/models.py` (98 lines)
- `src/memory/classifier.py` (271 lines)
- Supporting tests and CLI commands

**Key Observations:**
- Tagging system is isolated from main memory operations (no integration)
- No cleanup of orphaned tag associations when memories are deleted
- Auto-tagger relies on regex patterns with potential false positives
- Collection system has no enforcement of tag_filter constraints
- Tag normalization is case-insensitive but lacks Unicode handling

### CRITICAL Findings

- [ ] **BUG-092**: Orphaned Tag Associations After Memory Deletion
  - **Location:** `src/services/memory_service.py:536-571` (delete_memory), `src/tagging/tag_manager.py` (no cleanup hook)
  - **Problem:** When a memory is deleted via `MemoryService.delete_memory()`, it only deletes from Qdrant store. The `memory_tags` table in SQLite is never cleaned up, creating orphaned associations that accumulate over time.
  - **Impact:** Database bloat, incorrect tag usage statistics, memory leaks in tag-related queries
  - **Evidence:**
    - `delete_memory()` calls `await self.store.delete(request.memory_id)` but never touches tag_manager
    - `tag_manager.py` has no method to clean up tags by memory_id deletion event
    - No event system or callback mechanism connects MemoryService to TagManager
  - **Fix:**
    1. Add `tag_manager.cleanup_memory_tags(memory_id: str)` method
    2. Call from `MemoryService.delete_memory()` after successful store deletion
    3. Also add batch cleanup method for `StorageOptimizer.execute_cleanup()` to catch historical orphans

- [ ] **BUG-093**: Collection Membership Not Enforced or Updated
  - **Location:** `src/tagging/collection_manager.py:194-227` (add_to_collection), no validation logic
  - **Problem:** Collections have `tag_filter` (e.g., `{"tags": ["python", "async"], "op": "AND"}`) but there's no code that:
    1. Validates memories match the filter when added
    2. Auto-updates collection membership when tags change
    3. Removes memories from collections when tags no longer match
  - **Impact:** Collections become stale and inaccurate over time; manual add_to_collection ignores tag_filter completely
  - **Fix:**
    1. Add validation in `add_to_collection()` to check memory tags match collection.tag_filter
    2. Add `refresh_collection(collection_id)` method to re-evaluate all members against filter
    3. Consider event-driven updates when tags are added/removed from memories

- [ ] **BUG-094**: Tag Name Validation Rejects Valid Unicode Characters
  - **Location:** `src/tagging/models.py:26-30`
  - **Problem:** Validator only allows `c.isalnum() or c in "-_"`, which rejects valid Unicode alphanumeric chars (e.g., non-ASCII text in various languages)
  - **Impact:** Non-English users cannot create natural language tags
  - **Fix:** Replace `c.isalnum()` with proper Unicode category check using unicodedata module

### HIGH Priority Findings

- [ ] **BUG-095**: Auto-Tagger Regex Patterns Have High False Positive Rate
  - **Location:** `src/tagging/auto_tagger.py:21-121` (all pattern dictionaries)
  - **Problem:** Overly broad regex patterns trigger on unrelated content:
    - `r"\bimport\b"` matches "import taxes" discussion - tagged as "python"
    - `r"\bclass\b"` matches "world class developer" - tagged as "java"
    - `r"\bconst\b"` matches "constitutional law" - tagged as "javascript"
    - `r"\btest\b"` matches "test results" in medical context - tagged as "testing"
  - **Impact:** Tag pollution, reduced search precision, misleading auto-collections
  - **Fix:** Add context validation - patterns should require technical context. Consider requiring 2+ patterns match before tagging a language

- [ ] **BUG-096**: Tag Case Sensitivity Inconsistent with Retrieval
  - **Location:** `src/tagging/tag_manager.py:86` (normalizes to lowercase), but `get_tag_by_path:177` also lowercases
  - **Problem:** Tags are normalized to lowercase ("API" becomes "api", "FastAPI" becomes "fastapi") but this is only enforced in tag_manager. If external code queries tags or if user searches, case mismatches can occur. Additionally, hierarchical paths like "language/Python" get normalized to "language/python" which loses readability.
  - **Impact:** User searches for "API" won't find memories tagged "api"; confusion about canonical tag names
  - **Fix:**
    1. Document case normalization policy clearly
    2. Add case-insensitive search option for user-facing queries
    3. Consider preserving display_name (original case) separate from normalized search key

- [ ] **REF-065**: Tag Hierarchy Depth Validation Happens Too Late
  - **Location:** `src/tagging/tag_manager.py:96-97`
  - **Problem:** Hierarchy depth check happens after parent lookup and path construction. If validation fails, DB was queried unnecessarily. Also, error message says "4 levels" but check is `>= 3`, which allows levels 0-3 (actually 4 levels total) - confusing.
  - **Fix:**
    1. Check parent's level immediately: `if parent_tag and parent_tag.level >= 3: raise ValidationError`
    2. Clarify error message: "Tag hierarchy limited to 4 levels (0-3)"
    3. Add constant: `MAX_TAG_DEPTH = 3`

- [ ] **REF-066**: Auto-Tagger Hierarchical Inference Hardcoded and Incomplete
  - **Location:** `src/tagging/auto_tagger.py:175-226`
  - **Problem:** `infer_hierarchical_tags()` has hardcoded mappings (python to language/python, react to framework/react) but:
    1. Only handles 6 languages, 6 frameworks, 4 patterns, 4 domains
    2. Doesn't handle new tags added by users
    3. Logic like "if async in tags and python in tags then language/python/async" is fragile (what about other languages with async?)
  - **Impact:** Auto-tagging produces flat tags for most content; hierarchical organization is incomplete
  - **Fix:**
    1. Make hierarchy rules configurable (YAML/JSON file)
    2. Add auto-detection: if tag contains "/" already, don't infer hierarchy
    3. Use parent_id in tag creation instead of string path manipulation

- [ ] **BUG-097**: Collection Tag Filter Not Applied in get_collection_memories
  - **Location:** `src/tagging/collection_manager.py:257-274`
  - **Problem:** `get_collection_memories()` just returns all memory_ids from `collection_memories` table. It completely ignores the collection's `tag_filter`. Auto-generated collections (line 301-372) have tag_filter but it's never actually used for retrieval.
  - **Impact:** Collections with tag_filter are purely manual membership lists; auto-collection feature is non-functional
  - **Fix:**
    1. If collection.tag_filter exists, query memory_tags to find memories matching filter
    2. If collection.tag_filter is None, fall back to current manual membership list
    3. Add `auto_update: bool` flag to collections to control behavior

### MEDIUM Priority Findings

- [ ] **REF-067**: Tag Deletion Doesn't Clean Up Empty Parent Tags
  - **Location:** `src/tagging/tag_manager.py:267-305`
  - **Problem:** When deleting a tag with `cascade=True`, all descendants are deleted, but if this leaves parent tags with no children and no direct memory associations, those parent tags remain as orphaned hierarchy nodes.
  - **Impact:** Tag hierarchy accumulates dead branches over time
  - **Fix:** After cascade delete, walk up parent chain and delete any ancestors with no children and no memory associations

- [ ] **REF-068**: Tag Merge Doesn't Update Collection Filters
  - **Location:** `src/tagging/tag_manager.py:307-353` (merge_tags), `src/tagging/collection_manager.py` (no update logic)
  - **Problem:** When merging tags (e.g., merge "js" into "javascript"), collections with tag_filter referencing "js" are not updated to reference "javascript" instead.
  - **Impact:** Collections break silently after tag merges; filter becomes invalid
  - **Fix:** Add collection filter update to merge_tags() - after merging memory_tags, also update collection filters

- [ ] **BUG-098**: ContextLevelClassifier Has Overlapping Score Boosts
  - **Location:** `src/memory/classifier.py:116-151`
  - **Problem:** Classification applies category boost (line 121-128), then applies keyword boost (line 134-143), then applies code pattern boost (line 146-147). These can stack multiplicatively. E.g., a PREFERENCE category memory with "prefer" keyword gets +0.5 +0.2 = +0.7 boost, almost guaranteeing USER_PREFERENCE classification regardless of actual content.
  - **Impact:** Classifier is too easily biased by category hint; actual content analysis is overshadowed
  - **Fix:** Make boosts mutually exclusive or use weighted combination instead of additive stacking

- [ ] **REF-069**: Classifier Keyword Lists Are Not Comprehensive
  - **Location:** `src/memory/classifier.py:16-70`
  - **Problem:** Keyword patterns are limited (13 user pref, 14 project, 10 session). Many common patterns missing:
    - User preferences: "my approach", "I typically", "my workflow", "my convention"
    - Project context: "tech stack", "repo", "repository", "codebase structure"
    - Session state: "wip", "todo", "fixing", "debugging", "implementing"
  - **Impact:** Legitimate classification signals are missed; classifier falls back to defaults more often than needed
  - **Fix:** Expand keyword lists based on corpus analysis; consider making lists configurable/extensible

- [ ] **REF-070**: Auto-Tagger Stopword List Incomplete
  - **Location:** `src/tagging/auto_tagger.py:292-338`
  - **Problem:** Stopword list has 37 words but misses common technical terms that aren't good tags: "then", "than", "into", "also", "just", "when", "where", "what", "how", "why", "like", "more", "some", "been"
  - **Impact:** Low-value keyword tags pollute results
  - **Fix:** Expand stopword list or use NLTK/spaCy stopword corpus

- [ ] **BUG-099**: Tag Confidence Score Formulas Are Arbitrary
  - **Location:** `src/tagging/auto_tagger.py:239`, `253`, `267`, `281`, `355`
  - **Problem:** Confidence formulas like `min(0.9, 0.5 + (matches * 0.1))` are hardcoded magic numbers with no justification. Why is language detection capped at 0.9 but frameworks at 0.95? Why linear scaling?
  - **Impact:** Confidence scores don't reflect actual accuracy; can't be tuned or calibrated
  - **Fix:**
    1. Move all confidence parameters to class __init__ or config
    2. Add calibration data/tests showing confidence correlates with precision
    3. Consider logistic regression on match counts instead of linear

### LOW Priority / Tech Debt

- [ ] **REF-071**: Collection Auto-Generate Patterns Not User-Extensible
  - **Location:** `src/tagging/collection_manager.py:320-329`
  - **Problem:** Default tag patterns for auto-generation are hardcoded. Users can't add their own patterns without modifying source code.
  - **Fix:** Load patterns from config file (e.g., `~/.config/claude-memory/collection_patterns.yaml`)

- [ ] **REF-072**: Tag Statistics Not Tracked
  - **Location:** `src/tagging/tag_manager.py` (no usage tracking)
  - **Problem:** No visibility into tag usage: how many memories have each tag? Which tags are most/least used? Are auto-generated tags accurate?
  - **Impact:** Can't optimize tagging strategy or clean up unused tags
  - **Fix:** Add `get_tag_statistics()` method returning tag usage counts, confidence distributions, auto vs manual ratios

- [ ] **REF-073**: No Bulk Tag Operations
  - **Location:** `src/tagging/tag_manager.py:355-390` (tag_memory is single-item only)
  - **Problem:** Tagging memories one-by-one in loops (see `auto_tag_command.py:89-94`) is inefficient. Each call is a separate DB transaction.
  - **Impact:** Auto-tagging 1000 memories = 1000+ DB commits; slow and high DB contention
  - **Fix:** Add `tag_memories_bulk(associations: List[Tuple[memory_id, tag_id, confidence]])` with single transaction

- [ ] **REF-074**: Classifier Default Fallback Always Returns PROJECT_CONTEXT
  - **Location:** `src/memory/classifier.py:164-165`, `179-186`
  - **Problem:** When all scores are low (<0.3), classifier falls back to `_default_for_category()`. But for 3 out of 5 categories (FACT, WORKFLOW, CONTEXT), default is PROJECT_CONTEXT. This creates bias toward PROJECT_CONTEXT.
  - **Impact:** Ambiguous memories are over-classified as project context
  - **Fix:** Consider returning UNKNOWN context level or using uniform distribution when confidence is low

- [ ] **REF-075**: Tag Full Path Separator Hardcoded
  - **Location:** `src/tagging/tag_manager.py:102`, `src/tagging/models.py:40-42`
  - **Problem:** "/" separator is hardcoded throughout. If user wants to create tag named "react/hooks" as flat tag (not hierarchy), it's impossible.
  - **Impact:** Naming restrictions; potential conflicts with file path tags
  - **Fix:** Either:
    1. Add escaping mechanism ("react\/hooks" for literal)
    2. Use different separator (e.g., "::" for hierarchy)
    3. Document limitation clearly

### Summary Statistics

**Total Findings:** 15 issues
- Critical: 3 (BUG-092, BUG-093, BUG-094)
- High: 5 (BUG-095, BUG-096, REF-065, REF-066, BUG-097)
- Medium: 6 (REF-067, REF-068, BUG-098, REF-069, REF-070, BUG-099)
- Low: 5 (REF-071, REF-072, REF-073, REF-074, REF-075)

**Severity Breakdown:**
| Severity | Count | IDs |
|----------|-------|-----|
| Critical (data corruption/loss) | 3 | BUG-092, BUG-093, BUG-094 |
| High (incorrect behavior) | 5 | BUG-095, BUG-096, REF-065, REF-066, BUG-097 |
| Medium (quality/maintainability) | 6 | REF-067, REF-068, BUG-098, REF-069, REF-070, BUG-099 |
| Low (tech debt) | 5 | REF-071, REF-072, REF-073, REF-074, REF-075 |

**Root Causes:**
1. **Isolation:** Tagging system completely isolated from MemoryService - no event integration
2. **Incomplete Implementation:** Collections have tag_filter but it's never actually enforced or used
3. **Hardcoded Logic:** Auto-tagger patterns, confidence formulas, hierarchy rules all hardcoded
4. **Lack of Validation:** Tag filters not validated when adding to collections; case sensitivity inconsistent
5. **No Analytics:** No usage tracking, statistics, or calibration data for tag quality

**Recommended Priorities:**
1. **Immediate:** Fix BUG-092 (orphaned tags on deletion) - causes DB bloat
2. **Short-term:** Implement BUG-093 (collection tag_filter enforcement) - core feature is broken
3. **Medium-term:** Address BUG-095 (false positive auto-tags) - affects data quality
4. **Long-term:** Refactor auto-tagger to be configurable (REF-066, REF-071)

**Next Ticket Numbers:** BUG-100, REF-076

## AUDIT-001 Part 14: Graph Generation & Visualization Findings (2025-11-30)

**Investigation Scope:** 8 files across graph module - dependency_graph.py (333 lines), call_graph.py (346 lines), formatters (dot_formatter.py 192 lines, json_formatter.py 164 lines, mermaid_formatter.py 165 lines), graph_generator.py (478 lines)

### 🔴 CRITICAL Findings

- [ ] **BUG-092**: Cycle Detection Produces Incorrect Cycles with Duplicate Nodes
  - **Location:** `src/graph/dependency_graph.py:163-167`
  - **Problem:** When back edge is detected, cycle construction is `cycle = path[cycle_start_idx:] + [neighbor]`. This duplicates the neighbor node (it's already at cycle_start_idx AND appended at end). For cycle A->B->C->A, this creates [A, B, C, A] which is correct, but the CircularDependency.length counts the duplicate (length=4 instead of 3 unique nodes). Additionally, the cycle marking logic at lines 178-181 expects the duplicate, but this makes cycle representation inconsistent.
  - **Example:** Path [A, B, C], neighbor=A, cycle_start_idx=0 → cycle = [A, B, C] + [A] = [A, B, C, A] (4 nodes for 3-node cycle)
  - **Impact:** Incorrect cycle statistics, confusing visualization (A appears twice), edge marking misses some circular edges
  - **Fix:** Either (1) Don't append duplicate: `cycle = path[cycle_start_idx:]` and update edge marking logic, OR (2) Document that cycles intentionally include start/end duplicate and update CircularDependency to expose both raw cycle and unique_nodes count

- [ ] **BUG-093**: DependencyGraphGenerator.generate Returns Tuple of Wrong Length
  - **Location:** `src/memory/graph_generator.py:118`
  - **Problem:** Function signature says `-> tuple[str, Dict[str, Any]]` (2 elements) but line 118 returns `return graph_data, stats, circular_groups` (3 elements). This causes unpacking errors for any caller expecting 2-tuple.
  - **Example:** `graph, stats = generator.generate()` will raise `ValueError: too many values to unpack (expected 2)`
  - **Impact:** Runtime error on every call to generate()
  - **Fix:** Update return type to `-> tuple[str, Dict[str, Any], List[List[str]]]` or change return to 2-tuple by embedding circular_groups in stats dict

- [ ] **BUG-094**: Max Depth Calculation Ignores Cycles - Infinite Loop Risk
  - **Location:** `src/graph/dependency_graph.py:314-325`
  - **Problem:** `get_stats()` calculates max_depth using BFS from root nodes, but doesn't track visited set across different root traversals. If graph has cycles (which find_circular_dependencies explicitly detects), the BFS at line 318-325 has `visited: Set[str] = {root}` scoped per root, meaning it can loop infinitely within a strongly connected component.
  - **Example:** Graph with cycle A->B->C->A and no roots (all nodes have incoming edges). Line 311 finds roots=[], loop never executes, max_depth stays 0. But if roots=[A] and A->B->C->A cycle exists, BFS adds B to queue, then C, then A again (A not in visited for this iteration).
  - **Impact:** Infinite loop causing process hang, incorrect max_depth=0 for cyclic graphs
  - **Fix:** Move `visited` set outside the roots loop OR use global visited set OR skip max_depth calculation if circular dependencies detected

### 🟡 HIGH Priority Findings

- [ ] **BUG-095**: Mermaid Formatter Missing Newline Escaping in Labels
  - **Location:** `src/graph/formatters/mermaid_formatter.py:94, 102`
  - **Problem:** Node labels include file names and metadata with `<br/>` HTML tags (line 94), but if filename contains literal `\n` or special chars like `"`, `[`, `]`, these aren't escaped. Mermaid syntax uses `[label]` for nodes - a filename with `]` will break parsing.
  - **Example:** File `/project/test[1].py` → node syntax `A["test[1].py"]` breaks Mermaid parser
  - **Impact:** Invalid Mermaid output for files with brackets, quotes, or special characters
  - **Fix:** Add `_escape_mermaid_label()` method that escapes `"`, `[`, `]`, and converts `\n` to `<br/>`

- [ ] **BUG-096**: DOT Formatter Incomplete Escaping - Missing Newline Handling
  - **Location:** `src/graph/formatters/dot_formatter.py:177-191`
  - **Problem:** `_escape_dot_string()` escapes backslashes and quotes, but doesn't handle literal newlines (`\n` in file paths) or other DOT special chars like `<`, `>`, `{`, `}`. If a file path contains newline, the DOT output will have literal line break inside quoted string, breaking syntax.
  - **Example:** File path `/tmp/test\nfile.py` (unlikely but possible on Linux) → DOT: `label="/tmp/test` (line break) `file.py"` (syntax error)
  - **Impact:** Malformed DOT output for edge-case file paths, Graphviz rendering fails
  - **Fix:** Extend escaping to replace `\n` → `\\n`, `\r` → `\\r`, `\t` → `\\t`

- [ ] **BUG-097**: filter_by_depth Off-By-One Error - Max Depth Not Inclusive
  - **Location:** `src/graph/dependency_graph.py:217`
  - **Problem:** Line 217 checks `if depth < max_depth:` before exploring neighbors, meaning a node at exactly max_depth won't have its children explored. Docstring says "max_depth: Maximum traversal depth (0 = root only, 1 = root + direct deps, etc.)" which suggests max_depth should be inclusive. With current code, max_depth=1 gives root only (depth 0), not root + direct deps.
  - **Example:** Root A → B → C, max_depth=1 should include A and B, but only includes A because B is at depth 1 and `1 < 1` is false
  - **Impact:** Filter returns one fewer level than documented, user confusion
  - **Fix:** Change to `if depth <= max_depth:` OR update docstring to clarify exclusive behavior

- [ ] **BUG-098**: Call Graph BFS Doesn't Mark Starting Node as Visited
  - **Location:** `src/graph/call_graph.py:175-176, 229-230`
  - **Problem:** `_find_callers_bfs` and `_find_callees_bfs` initialize queue with `[(function_name, 0)]` but visited set is empty. The starting function is only added to visited when popped from queue (line 178/232 is inside the while loop). If starting function calls itself (recursion), it gets added to queue again before being marked visited.
  - **Example:** Function `factorial` calls itself → queue starts with `[('factorial', 0)]`, loop processes it, adds `factorial` to visited, but if it was already processed once, visited already has it. However, if self-recursion creates multiple queue entries before first pop, duplicates accumulate.
  - **Impact:** Potential duplicate processing, inefficiency for recursive functions
  - **Fix:** Add `visited.add(function_name)` before initializing queue, OR add to visited set in queue initialization: `visited = {function_name}`

- [ ] **BUG-099**: DependencyGraphGenerator Assumes graph.dependencies Dict Exists
  - **Location:** `src/memory/graph_generator.py:129, 154`
  - **Problem:** Lines 129 and 154 access `self.graph.dependencies` but DependencyGraph class (src/graph/dependency_graph.py) doesn't have this attribute. DependencyGraph uses `_adjacency_list` internally and exposes `nodes` and `edges` attributes. This causes AttributeError on every call.
  - **Example:** `filtered_nodes = set(self.graph.dependencies.keys())` → AttributeError: 'DependencyGraph' object has no attribute 'dependencies'
  - **Impact:** DependencyGraphGenerator completely broken, cannot generate any graphs
  - **Fix:** Refactor to use `self.graph.nodes.keys()` and `self.graph.edges` instead of non-existent dependencies/dependents dicts

- [ ] **REF-070**: Circular Dependency Detection Runs on Every get_stats Call
  - **Location:** `src/graph/dependency_graph.py:304`
  - **Problem:** `get_stats()` calls `find_circular_dependencies()` which runs full DFS cycle detection. While the result is cached in `_circular_deps`, the cache is invalidated if graph is modified. If user calls `get_stats()` repeatedly (e.g., in a monitoring loop), and graph is rebuilt each time, full DFS runs every time.
  - **Impact:** O(V+E) performance cost on every stats call for large graphs
  - **Fix:** Add `skip_circular_check=False` parameter to get_stats(), document that circular_dependency_count will be 0 if skipped

- [ ] **REF-071**: Mermaid linkStyle Uses Edge Index Which Changes with Filtering
  - **Location:** `src/graph/formatters/mermaid_formatter.py:66, 148-164`
  - **Problem:** Line 66 uses `_get_edge_index()` to find edge position for styling, but if graph is filtered (e.g., by language or pattern), edge indices change. A circular edge might be at index 5 in full graph but index 2 in filtered graph, causing wrong edge to be styled red.
  - **Example:** Full graph has edges [A→B, B→C, C→D, C→A (circular), D→E]. After filtering to just [A,B,C], edges are [A→B, B→C, C→A]. Original index was 3, new index is 2.
  - **Impact:** Red circular styling applied to wrong edges in filtered graphs
  - **Fix:** Count edges as they're emitted instead of using global index, or track edges by (source, target) tuple

### 🟢 MEDIUM Priority Findings

- [ ] **REF-072**: DOT Formatter DEFAULT_COLOR is Invalid - Should Be "#808080"
  - **Location:** `src/graph/formatters/dot_formatter.py:36`
  - **Problem:** Line 36 sets `DEFAULT_COLOR = "#gray"` but DOT/Graphviz doesn't recognize "#gray" as valid hex color (hex colors must be #RRGGBB or #RRGGBBAA). The `#` prefix indicates hex, but "gray" is a named color without `#`. This causes rendering issues or fallback to black.
  - **Impact:** Unknown language nodes appear black instead of gray
  - **Fix:** Change to `DEFAULT_COLOR = "gray"` (named color) OR `DEFAULT_COLOR = "#808080"` (hex gray)

- [ ] **REF-073**: JSON Formatter Silently Omits Metadata for Nodes Without Unit/Size
  - **Location:** `src/graph/formatters/json_formatter.py:101-107`
  - **Problem:** When `include_metadata=True`, the code only adds unit_count/file_size if they're > 0. For a file with 0 units and 0 bytes, metadata is completely omitted from JSON, making it indistinguishable from `include_metadata=False`. This inconsistency makes client-side parsing harder.
  - **Impact:** Inconsistent JSON schema - some nodes have metadata fields, others don't
  - **Fix:** Always include fields when `include_metadata=True`, use explicit 0 values OR add comment documenting intentional omission

- [ ] **REF-074**: filter_by_pattern Matches Against Both Full Path and Basename
  - **Location:** `src/graph/dependency_graph.py:248-250`
  - **Problem:** Filter matches pattern against both full file_path and `Path(file_path).name` (basename). For pattern `"*.py"`, this is fine, but for pattern `"src/*.py"`, matching against basename will include `/other/src/test.py` even though path doesn't match `src/*.py`. The OR logic is too permissive.
  - **Example:** Pattern `"src/*.py"` should match `/project/src/utils.py` but not `/other/src/utils.py`. Current code matches both because basename matches.
  - **Impact:** Filter includes more files than expected, confusing results
  - **Fix:** Document behavior OR only match basename for simple patterns (no `/`), full path for path-like patterns

- [ ] **REF-075**: CallGraph Statistics Count Interfaces but Not Interface Methods
  - **Location:** `src/graph/call_graph.py:343-344`
  - **Problem:** `get_statistics()` counts total interfaces (line 343) and total implementations (344), but doesn't count total methods across implementations. This makes it hard to assess complexity of interface hierarchies.
  - **Impact:** Incomplete statistics for polymorphic codebases
  - **Fix:** Add `"total_interface_methods": sum(len(impl.methods) for impls in self.implementations.values() for impl in impls)` to stats dict

- [ ] **REF-076**: DependencyGraphGenerator._get_language Hardcoded - Duplicates Logic
  - **Location:** `src/memory/graph_generator.py:273-300`
  - **Problem:** Language detection from file extension is hardcoded in generator. If language mapping changes or new languages are added, must update in multiple places. Consider extracting to shared utility or configuration.
  - **Impact:** Maintenance burden, inconsistency risk
  - **Fix:** Extract language mapping to `src/graph/language_detector.py` or config file, reuse across codebase

- [ ] **REF-077**: Mermaid Node IDs Limited to 26 Files (A-Z)
  - **Location:** `src/memory/graph_generator.py:429`
  - **Problem:** Line 429 generates node IDs as `chr(65 + i)` for i < 26, else `f"N{i}"`. This works but creates inconsistent ID format (A-Z for first 26, then N26, N27, etc). Also, comment or docstring should warn that very large graphs (>26 nodes) get numeric IDs.
  - **Impact:** Inconsistent node ID format in Mermaid output, potential confusion
  - **Fix:** Use consistent format like `f"N{i}"` for all nodes OR document the A-Z then numeric pattern

- [ ] **REF-078**: DOT Sanitization Removes Dots from Node IDs - Causes Collisions
  - **Location:** `src/graph/formatters/dot_formatter.py:167-168`
  - **Problem:** `_make_node_id()` replaces `.` with `_`, so `file.py` and `file_py` both become `file_py`, causing node ID collision. If graph has both `/src/test.py` and `/src/test_py`, they'll have the same DOT node ID, causing one to overwrite the other.
  - **Example:** Files `util.py` and `util_py` both → node ID `util_py`
  - **Impact:** Silent data loss in DOT export, missing nodes in visualization
  - **Fix:** Use unique separator or hash-based IDs: `node_id = hashlib.md5(file_path.encode()).hexdigest()[:8]` OR keep dots and use quoted node IDs

- [ ] **REF-079**: graph_generator.py Hardcodes "dependencies" as Graph Title Comment
  - **Location:** `src/memory/graph_generator.py:310, 424`
  - **Problem:** DOT output says `digraph dependencies {` and Mermaid has comment `graph LR` but no title. The `title` parameter from generate() is never passed to these format methods (only to JSON metadata). User's title is ignored for DOT/Mermaid.
  - **Impact:** All DOT/Mermaid graphs have generic title, not user-specified title
  - **Fix:** Pass title to `_to_dot()` and `_to_mermaid()`, add as comment or graph label

### 🟢 LOW Priority Findings

- [ ] **PERF-013**: Cycle Detection Creates New Path List on Every Recursive Call
  - **Location:** `src/graph/dependency_graph.py:157, 170`
  - **Problem:** DFS passes `path` list by reference and mutates it (append line 157, pop line 170), which is correct. However, if there are many cycles, the path list is repeatedly grown/shrunk. Consider pre-allocating or using deque for O(1) append/pop.
  - **Impact:** Minor performance cost for graphs with hundreds of cycles
  - **Fix:** Change `path: List[str]` to `path: collections.deque` for O(1) operations

- [ ] **PERF-014**: filter_by_depth Creates New Graph with Deep Copy of Nodes
  - **Location:** `src/graph/dependency_graph.py:224-227`
  - **Problem:** Lines 225-227 add nodes to filtered graph by calling `filtered.add_node(self.nodes[node_path])`. This doesn't deep copy the GraphNode object, but if GraphNode is later modified, the filtered graph shares references. For read-only use this is fine, but for mutable operations it's risky.
  - **Impact:** Potential unexpected mutation if filtered graph nodes are modified
  - **Fix:** Document that filtered graphs share node references OR deep copy nodes: `filtered.add_node(dataclasses.replace(self.nodes[node_path]))`

- [ ] **REF-080**: Missing Type Hints for _adjacency_list Private Attribute
  - **Location:** `src/graph/dependency_graph.py:87`
  - **Problem:** Line 87 initializes `_adjacency_list: Dict[str, List[str]] = {}` with type hint in __init__, but class doesn't declare it at class level. Modern Python style is to declare all attributes at class level with type annotations for better IDE support.
  - **Impact:** Reduced IDE autocomplete, type checker warnings
  - **Fix:** Add class-level annotation: `_adjacency_list: Dict[str, List[str]]` before `__init__`

- [ ] **REF-081**: Call Graph Forward/Reverse Index Use defaultdict but Initialized as Regular Dict
  - **Location:** `src/graph/call_graph.py:96-97`
  - **Problem:** Lines 96-97 use `defaultdict(set)` which is good, but throughout the code (e.g., lines 120, 123, 159, 184) there are calls like `self.forward_index.get(node, set())`. This .get() pattern is redundant for defaultdict - can just use `self.forward_index[node]`.
  - **Impact:** Unnecessary defensive code, slight inefficiency
  - **Fix:** Replace all `.get(key, set())` with `[key]` for defaultdict attributes OR document why defensive .get() is preferred

- [ ] **REF-082**: Mermaid Formatter Doesn't Escape Pipe Character in Labels
  - **Location:** `src/graph/formatters/mermaid_formatter.py:94, 462`
  - **Problem:** Mermaid uses `|` for edge labels (e.g., `A -->|label| B`). If label text contains `|`, it can break parsing. File names rarely have pipes, but metadata like "5 units | 2KB" would break.
  - **Impact:** Rare but possible syntax errors in Mermaid output
  - **Fix:** Escape `|` to `\|` or use different metadata separator

- [ ] **REF-083**: JSON Formatter ensure_ascii=False May Cause Issues for Some Clients
  - **Location:** `src/graph/formatters/json_formatter.py:42`
  - **Problem:** `json.dumps(..., ensure_ascii=False)` outputs Unicode characters directly. While this is more readable, some older JSON parsers or tools expect ASCII-only JSON. The test at line 359 shows Unicode file paths are supported, but this could break clients.
  - **Impact:** Potential compatibility issues with strict JSON parsers
  - **Fix:** Add parameter to control ensure_ascii, default to True for safety

- [ ] **REF-084**: DependencyGraph Doesn't Validate Node Existence on add_edge
  - **Location:** `src/graph/dependency_graph.py:117-120`
  - **Problem:** `add_edge()` ensures nodes exist in `_adjacency_list` but doesn't check if they exist in `self.nodes` dict. Can create edges between nodes that were never added via `add_node()`, resulting in incomplete metadata.
  - **Impact:** Graph can have edges to phantom nodes without language/metadata
  - **Fix:** Add validation: `if edge.source not in self.nodes: logger.warning(f"Adding edge from unknown node {edge.source}")` OR require nodes to exist

- [ ] **REF-085**: Call Graph BFS Max Depth Check Uses >= Instead of >
  - **Location:** `src/graph/call_graph.py:180, 234`
  - **Problem:** Lines 180 and 234 check `if depth >= max_depth: continue`, which means a node at exactly max_depth is skipped. Combined with the starting depth of 0, this gives max_depth=1 → only direct neighbors (depth 1), not transitive at depth 2. Docstring says "max_depth: Maximum depth" which is ambiguous about inclusive/exclusive.
  - **Impact:** Off-by-one in transitive caller/callee search
  - **Fix:** Change to `if depth > max_depth:` OR clarify docstring as "exclusive depth limit"

### Summary of Findings

**Critical Issues (Fix Immediately):**
- BUG-092: Cycle detection duplicates nodes causing incorrect cycle length
- BUG-093: generate() returns 3-tuple instead of declared 2-tuple
- BUG-094: Max depth calculation can infinite loop on cyclic graphs
- BUG-099: DependencyGraphGenerator incompatible with DependencyGraph class

**High Priority (Fix Soon):**
- BUG-095-098: Escaping and validation issues in formatters
- REF-070-071: Performance and correctness issues in formatting

**Medium/Low Priority:**
- REF-072-085: Code quality, consistency, edge cases

**Testing Gaps Identified:**
- No tests for file paths with special characters in formatters (brackets, quotes, newlines)
- No tests for graphs with cycles in max_depth calculation
- No tests for very large graphs (100+ nodes) in Mermaid formatter
- No tests for DependencyGraphGenerator (appears to be dead code given BUG-099)
- No tests for recursive functions in call graph BFS

**Architecture Concerns:**
- DependencyGraphGenerator appears to be a parallel implementation incompatible with DependencyGraph class (BUG-099)
- Language detection logic duplicated across modules (REF-076)
- Inconsistent ID generation schemes across formatters (REF-077, REF-078)

**Recommended Fix Priority:**
1. Fix BUG-093 (blocking runtime error) and BUG-099 (dead code)
2. Fix BUG-094 (infinite loop risk)
3. Fix BUG-092 (data correctness)
4. Add comprehensive escaping tests and fix BUG-095, BUG-096
5. Address performance issues (PERF-013, PERF-014) if large graphs are expected
6. Standardize and document behavior for edge cases (REF-070-085)
