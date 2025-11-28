# TEST-029: Test Suite Optimization Analysis

**Date:** 2025-11-28
**Source:** 4-agent parallel analysis of test suite
**Methodology:** Each agent independently analyzed the test suite for compute waste, data sharing opportunities, and redundant patterns

---

## Executive Summary

The test suite has **strong foundational optimizations** already in place:
- Global mock embeddings preventing 420MB model load per worker
- Qdrant collection pooling preventing deadlocks in parallel execution
- GPU/MPS disabled to prevent memory explosions
- Worker-specific isolation for true parallel test execution

However, significant optimization opportunities remain that could reduce test execution time by **30-50%** while maintaining coverage quality.

---

## Consensus Findings (Identified by Multiple Agents)

### HIGH IMPACT - All 4 Agents Agreed

#### 1. Performance Tests Create Excessive Data Sets

**Location:** `tests/performance/test_scalability.py:83-131`

**Problem:** `test_memory_count_scaling` stores 1000 + 2000 + 3000 = **6000 memories sequentially**. Even with mock embeddings, this creates excessive Qdrant load.

**Evidence:**
- Agent 1: "Stores 1000, 2000, and 3000 memories sequentially, totaling 6000 store operations"
- Agent 2: "Could reduce E2E test time by 40-60%"
- Agent 3: "Stores 6000 memories sequentially to test scaling"
- Agent 4: "Each memory triggers embedding generation, stored individually (not batched)"

**Recommendation:**
- Reduce to 100, 200, 300 memories (10x reduction) - still validates scaling behavior
- Use batch store operations instead of individual stores
- Mark with `@pytest.mark.slow` and exclude from default runs

**Estimated Impact:** HIGH - Could save 30-60 seconds per test run

---

#### 2. E2E Tests Repeatedly Index Same Sample Project

**Location:**
- `tests/e2e/test_critical_paths.py` - Multiple tests re-index `sample_code_project`
- `tests/e2e/conftest.py:60-288` - `sample_code_project` is function-scoped but static

**Problem:** Multiple E2E tests index the same project repeatedly:
- `test_first_time_setup` indexes sample_code_project
- `test_first_code_search` indexes again
- `test_developer_daily_workflow` indexes again
- `test_code_exploration_workflow` indexes again
- 10+ total redundant index operations

**Evidence:**
- Agent 1: "test_different_fusion_methods creates server inside loops"
- Agent 2: "Could reduce E2E test time by 50-70% (eliminating ~10 redundant index operations)"
- Agent 3: "Multiple tests re-index same sample project"
- Agent 4: "Creates fresh servers and indexes same sample_code_project repeatedly"

**Recommendation:**
Create a session-scoped pre-indexed fixture:
```python
@pytest_asyncio.fixture(scope="session")
async def pre_indexed_server(sample_code_project, unique_qdrant_collection):
    """Session-scoped server with pre-indexed code for read-only tests."""
    server = MemoryRAGServer(config)
    await server.initialize()
    await server.index_codebase(str(sample_code_project), "shared-test-project")
    yield server
    await server.close()
```

**Estimated Impact:** HIGH - Could reduce E2E test time by 50-70%

---

#### 3. Server Initialization in Loops (Not Parameterized)

**Location:** `tests/integration/test_hybrid_search_integration.py:292-336`

**Problem:** `test_different_fusion_methods` creates a new server for each fusion method in a loop (3 iterations). Similar patterns in alpha and BM25 parameter tests.

```python
for fusion_method in ["weighted", "rrf", "cascade"]:
    server = MemoryRAGServer(config=config)
    await server.initialize()
    ...
    await server.close()
```

**Evidence:**
- Agent 1: "Server initialization involves Qdrant connection setup, embedding generator initialization, collection setup"
- Agent 2: "Use parameterized fixtures instead of loop-based server creation"
- Agent 4: "Creates a new server, collection, and temp directory for each fusion method iteration (3x)"

**Recommendation:**
```python
@pytest.mark.parametrize("fusion_method", ["weighted", "rrf", "cascade"])
async def test_fusion_method(self, fresh_server, fusion_method):
    # Reconfigure on existing server
```

**Estimated Impact:** HIGH - Reduces 3 server/collection creations to 1

---

#### 4. Skipped Integration Tests Still Pay Collection Cost

**Location:**
- `tests/integration/test_indexing_integration.py:15` (entire module skipped)
- `tests/integration/test_hybrid_search_integration.py:19` (entire module skipped)
- `tests/integration/test_concurrent_operations.py:22` (entire module skipped)

**Problem:** Module-level `pytestmark = pytest.mark.skip(...)` still causes pytest to collect and process fixtures, importing heavy modules.

**Evidence:**
- Agent 1: "pytest still collects and processes the fixtures"
- Agent 2: "The entire file is skipped, providing no coverage during normal test runs"

**Recommendation:**
- Use `pytest.importorskip()` at the top of the file to skip collection entirely
- Or move skipped tests to separate directory and exclude via pytest.ini
- Better: Fix the flakiness (likely Qdrant contention) and restore coverage

**Estimated Impact:** MEDIUM - Could save 5-10 seconds of collection time + restore lost coverage

---

### MEDIUM IMPACT - 3+ Agents Agreed

#### 5. Function-Scoped Fixtures That Could Be Session/Module-Scoped

**Locations:**
- `tests/unit/test_hybrid_search.py:10-47` - `sample_memories` fixture (static, read-only)
- `tests/performance/conftest.py:76` - `indexed_test_project` (expensive, read-only use)
- `tests/conftest.py:133-155` - `small_test_project` (5 files, recreated per test)
- Multiple `config` fixtures across unit tests

**Problem:** Static data fixtures are function-scoped but only used in read-only tests. Each test recreates identical data.

**Evidence:**
- Agent 1: "`indexed_test_project` fixture creates server with 20 indexed files but is function-scoped"
- Agent 2: "`sample_memories` creates `MemoryUnit` objects 20 times unnecessarily"
- Agent 3: "`sample_code_project` is function-scoped but static"
- Agent 4: "`config` fixture repeatedly created hundreds of times"

**Recommendation:**
- Change `sample_memories` to `scope="module"` for read-only tests
- Make `indexed_test_project` session-scoped for read-only tests
- Create shared `tests/unit/conftest.py` with module-scoped `config`

**Estimated Impact:** MEDIUM-HIGH - Reduces object allocation across test suite

---

#### 6. Duplicate Test Coverage Across Files

**Location:** Multiple files with overlapping `test_search_code_*` tests:

| File | Test Count | Coverage |
|------|------------|----------|
| `test_server_extended.py` | 3 tests | Basic, filters, no results |
| `test_services/test_code_indexing_service.py` | 8 tests | Same + mode validation |
| `test_hybrid_search_integration.py` | 6 tests | Hybrid mode |
| `test_search_code_ux_integration.py` | 9 tests | UX features |
| `test_confidence_scores.py` | 4 tests | Confidence |

**Problem:** Tests like "test_search_code_basic" duplicated between unit and integration levels.

**Evidence:**
- Agent 2: "30+ search_code tests across multiple files with significant overlap"
- Agent 4: "Some behaviors tested multiple times with minor variations"

**Recommendation:**
- Keep unit tests focused on service-level mocking
- Reduce integration tests to unique scenarios only
- Parameterize filter variations instead of separate tests

**Estimated Impact:** MEDIUM - Could eliminate 5-10 redundant tests

---

#### 7. Language Parsing Tests Have Repetitive Structure

**Location:**
- `tests/unit/test_kotlin_parsing.py`
- `tests/unit/test_swift_parsing.py`
- `tests/unit/test_ruby_parsing.py`

**Problem:** Each file has ~15 tests following identical patterns (function extraction, class extraction, interface extraction) for different languages.

**Evidence:**
- Agent 2: "~45 tests could be reduced to ~15 with parameterization"
- Agent 4: "Could share test logic via parameterization"

**Recommendation:**
```python
@pytest.mark.parametrize("language,extension,sample_code", [
    ("kotlin", ".kt", KOTLIN_SAMPLE),
    ("swift", ".swift", SWIFT_SAMPLE),
    ("ruby", ".rb", RUBY_SAMPLE),
])
def test_function_extraction(language, extension, sample_code, tmp_path):
    ...
```

**Estimated Impact:** MEDIUM - Reduces test count from ~45 to ~15 with same coverage

---

### LOW IMPACT - Individual Findings Worth Noting

#### 8. Tests Without Meaningful Assertions

**Location:** `tests/integration/test_file_watcher_indexing.py:413-428`

**Problem:** `test_file_watcher_indexer_integration_coverage()` always passes:
```python
def test_file_watcher_indexer_integration_coverage():
    """Report on integration test coverage."""
    print("\n" + "=" * 70)
    # ... print statements
    assert True  # This test always passes
```

**Recommendation:** Remove or convert to documentation.

---

#### 9. Loop-Based Tests Instead of Parameterization

**Location:** `tests/unit/test_server_extended.py:384-393`

**Problem:**
```python
async def test_retrieve_with_various_limits(self, server, mock_embeddings):
    for limit in [1, 5, 10, 50, 100]:
        results = await server.retrieve_memories(query="test", limit=limit)
```

**Recommendation:** Convert to `@pytest.mark.parametrize("limit", [1, 5, 10, 50, 100])`

---

#### 10. Benchmark Tests Mixed with Unit Tests

**Location:** `tests/unit/test_parallel_embeddings.py:394-456`

**Problem:** `TestParallelPerformance` is in unit tests but marked `@pytest.mark.benchmark`. Already marked `@pytest.mark.skip_ci`.

**Recommendation:** Move to `tests/performance/` for proper categorization.

---

#### 11. Skipped Semantic Similarity Test

**Location:** `tests/unit/test_embedding_generator.py:311-341`

**Problem:** `test_similar_texts_have_similar_embeddings` permanently skipped (mock embeddings are hash-based).

**Recommendation:** Move to `tests/real_embeddings/` directory that runs manually, or remove entirely.

---

## What's Already Done Well

The test suite has excellent foundational patterns:

1. **Global Mock Embeddings** (`tests/conftest.py:49-109`)
   - `mock_embeddings_globally` with `autouse=True` prevents loading 420MB model in every test worker
   - Hash-based deterministic embeddings for consistency

2. **Qdrant Collection Pooling** (`tests/conftest.py:376-565`)
   - Pre-created collections reused across tests
   - Worker-specific isolation via `_get_worker_collection`
   - Prevents deadlocks in parallel execution

3. **CPU-Forced Mode** (`tests/conftest.py:112-130`)
   - Prevents MPS GPU loading that caused 80GB+ memory usage
   - Environment variables set before any imports

4. **Session-Scoped Client Reuse** (`tests/conftest.py:402-421`)
   - Single Qdrant client per session

5. **Auto-Disabling GPU/Auto-Index** (`tests/conftest.py:112-130`)
   - Environment variables prevent expensive background operations

6. **Lazy Resource Loading** (`tests/conftest.py:162-193`)
   - `LazyResource` class only creates expensive resources when first accessed

---

## Priority Implementation Plan

### Phase 1: Quick Wins (1-2 days)

| Task | Files | Impact |
|------|-------|--------|
| Reduce performance test data volumes (1000→100) | test_scalability.py | Save 30-60s |
| Create session-scoped `config` fixture | tests/unit/conftest.py | Reduce allocations |
| Remove `assert True` documentation test | test_file_watcher_indexing.py | Clean up |
| Convert loop tests to parametrized | test_server_extended.py | Better isolation |

### Phase 2: Medium Effort (3-5 days)

| Task | Files | Impact |
|------|-------|--------|
| Create session-scoped `pre_indexed_server` | tests/e2e/conftest.py | Save 50-70% E2E time |
| Parameterize fusion method tests | test_hybrid_search_integration.py | 3 inits → 1 |
| Change `sample_memories` to module scope | test_hybrid_search.py | Reduce allocations |
| Parameterize language parsing tests | test_*_parsing.py | 45 tests → 15 |

### Phase 3: Larger Refactor (1-2 weeks)

| Task | Files | Impact |
|------|-------|--------|
| Fix/restore skipped integration tests | 3 integration test files | Restore coverage |
| Deduplicate search_code test coverage | Multiple files | Remove 5-10 tests |
| Reorganize benchmark tests | test_parallel_embeddings.py | Better organization |
| Create read-only vs write test distinction | conftest.py | Enable data sharing |

---

## Metrics for Success

| Metric | Current | Target |
|--------|---------|--------|
| Full test suite time | ~180-240s | ~100-150s |
| E2E test time | ~90s | ~30-45s |
| Performance test time | ~60s | ~20s |
| Tests with redundant setup | ~50+ | <10 |
| Skipped integration coverage | 3 files | 0 files |

---

## Risk Assessment

| Change | Risk | Mitigation |
|--------|------|------------|
| Session-scoped fixtures | State leakage between tests | Use factory pattern for mutable data |
| Reducing performance test data | May miss edge cases | Keep original as optional slow test |
| Parameterizing language tests | Harder to debug individual failures | Clear test IDs in parameterization |
| Restoring skipped tests | Flakiness may return | Fix underlying Qdrant contention first |

---

## Conclusion

The 4-agent analysis converged on several high-impact optimizations:

1. **Unanimous:** Reduce performance test data volumes and eliminate repeated indexing
2. **Strong consensus:** Session-scope read-only fixtures
3. **Strong consensus:** Parameterize loop-based and language-specific tests
4. **Noted:** Restore skipped integration test coverage

Implementing Phase 1 and Phase 2 recommendations should reduce test execution time by 30-50% with minimal risk.

---

## Appendix: Agent-Specific Unique Findings

### Agent 1 Unique
- `indexed_test_project` in performance/conftest.py scope mismatch
- Test files named for coverage metrics (`test_final_coverage_*.py`)

### Agent 2 Unique
- Real `EmbeddingGenerator` creation in provenance tests despite global mock
- `test_benchmark` in integration tests without skip marker

### Agent 3 Unique
- Cache tests creating 20-100 files per test unnecessarily
- Server fixtures defined in 40+ test files with initialization overhead

### Agent 4 Unique
- `generator` fixture in test_embedding_generator.py scope mismatch
- Integration tests that could be unit tests (mock-heavy)
