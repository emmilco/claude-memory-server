# TEST-010: Reduce Excessive Mocking in Test Suite

**Task ID:** TEST-010
**Type:** Testing Quality Improvement
**Priority:** High
**Estimated Effort:** ~3 days
**Status:** Planning
**Created:** 2025-11-25

---

## 1. Overview

### Problem Summary
The current test suite exhibits "testing theater" - tests verify that mocks were called but don't validate actual behavior. With 1,112 Mock/MagicMock instances across 47 test files and only 9 uses of `@pytest.mark.parametrize`, we have:

- **False confidence**: 59.6% coverage metric is misleading
- **Fragile tests**: Refactors break mocks, not business logic
- **Poor bug detection**: Unit tests pass but integration tests fail (40+ recent failures)
- **Maintenance burden**: One code change requires updating dozens of mock assertions

### Impact Assessment
**Current State:**
- 47 test files with excessive mocking (30+ files critically affected)
- `test_qdrant_setup_coverage.py`: Tests only verify `mock.assert_called_once()`
- `test_indexing_progress.py`: Mock store, mock embeddings, but never test real indexing behavior
- Integration test coverage: Only 0.7% (20 integration tests / 2,851 total)

**Business Impact:**
- Production bugs slip through despite "passing" tests
- Developer time wasted maintaining brittle mock assertions
- False sense of code quality prevents addressing real issues
- Onboarding difficulty: New developers confused by mock-heavy tests

**Risk Level:** **HIGH** - Tests provide false confidence while masking real bugs

---

## 2. Current State Analysis

### Worst Offenders (Top 10 Files by Mock Density)

| File | Mock Count | Lines | Mock Density | Primary Issue |
|------|-----------|-------|--------------|---------------|
| `test_qdrant_setup_coverage.py` | 15+ | 200 | 7.5% | Only tests mock calls, not behavior |
| `test_indexing_progress.py` | 78+ | 400 | 19.5% | Mocks entire indexing pipeline |
| `test_status_command.py` | 80+ | 600 | 13.3% | Mocks statistics instead of calculating |
| `test_auto_indexing_service.py` | 34+ | 500 | 6.8% | Mocks file watcher, indexer, tracker |
| `test_connection_pool.py` | 46+ | 400 | 11.5% | Mocks QdrantClient instead of using fake |
| `test_background_indexer.py` | 56+ | 450 | 12.4% | Mocks async operations heavily |
| `test_web_server.py` | 83+ | 700 | 11.9% | Mocks HTTP requests instead of test client |
| `test_health_command.py` | 85+ | 650 | 13.1% | Mocks entire health check system |
| `test_indexing_service.py` | 38+ | 450 | 8.4% | Mocks storage, embeddings, file I/O |
| `test_file_watcher_coverage.py` | 26+ | 300 | 8.7% | Mocks file system events |

**Total Problematic Lines:** ~4,650 lines of mock-heavy test code

### Categories of Problematic Mocking Patterns

#### Pattern 1: Mock-Only Assertions (Worst)
```python
# test_qdrant_setup_coverage.py:37-65
def test_collection_exists_auto_connect(self):
    """Test collection_exists auto-connects if client is None (line 76)."""
    with patch.object(setup, 'connect') as mock_connect:
        result = setup.collection_exists()
        mock_connect.assert_called_once()  # ❌ ONLY assertion - doesn't test behavior!
```

**Problems:**
- Doesn't verify return value correctness
- Doesn't test actual connection logic
- Refactoring method calls breaks test (but not functionality)

#### Pattern 2: Deep Mock Hierarchies
```python
# test_indexing_progress.py:19-31
mock_store = MagicMock()
mock_store.initialize = AsyncMock()
mock_store.batch_store = AsyncMock(return_value=["id1", "id2"])
mock_store.client = MagicMock()
mock_store.client.scroll = MagicMock(return_value=([], None))
mock_store.collection_name = "test"
mock_store.close = AsyncMock()

mock_embeddings = MagicMock()
mock_embeddings.initialize = AsyncMock()
mock_embeddings.batch_generate = AsyncMock(return_value=[[0.1] * 384, [0.2] * 384])
mock_embeddings.close = AsyncMock()
```

**Problems:**
- 12 lines of setup just to create test doubles
- Mock behavior hardcoded (doesn't test edge cases)
- Doesn't validate interaction correctness (order, parameters)

#### Pattern 3: Mocking I/O Instead of Using Fakes
```python
# test_connection_pool.py (pattern repeated 46+ times)
with patch('qdrant_client.QdrantClient') as mock_client:
    mock_client.return_value.get_collections.return_value = [...]
```

**Problems:**
- Should use in-memory Qdrant or Docker container for integration tests
- Unit tests should use FakeQdrantClient implementing same interface
- Misses real connection errors, timeout handling, resource cleanup

#### Pattern 4: Mocking Time and Random Functions
```python
# Multiple test files
with patch('time.time', return_value=1234567890):
    # Test code
```

**Problems:**
- Makes tests non-deterministic when time mocks accidentally removed
- Better to inject clock dependency or use `freezegun` library

#### Pattern 5: Excessive Patching Scope
```python
@patch('src.store.qdrant_store.QdrantClient')
@patch('src.embeddings.generator.EmbeddingGenerator')
@patch('src.memory.incremental_indexer.FileParser')
class TestIndexingWorkflow:
    # All 20 methods use these patches
```

**Problems:**
- Class-level patches applied even when not needed
- Hard to understand which tests need which mocks
- Encourages lazy testing (just add another patch)

### Why Excessive Mocking is Harmful

1. **False Positives**: Tests pass but code is broken
2. **Missed Integration Issues**: Components work alone but fail together
3. **Tight Coupling to Implementation**: Tests break when refactoring (even if behavior unchanged)
4. **Poor Documentation**: Mocks obscure what code actually does
5. **Maintenance Burden**: Mock setup often longer than actual test logic

### Current Coverage Breakdown
```
Overall Coverage:     59.6%
Core Module Coverage: 71.2%
Integration Coverage: 0.7% (20 tests)
Mock-Heavy Tests:     ~1,650 tests (~58% of suite)
Behavior Tests:       ~1,200 tests (~42% of suite)
```

**The 59.6% coverage is misleading** - much of it tests mock interactions, not real behavior.

---

## 3. Proposed Solution

### Strategy: Three-Tier Testing Approach

#### Tier 1: True Unit Tests (Fast, Isolated, No I/O)
- Test pure functions and business logic
- Use fakes/stubs instead of mocks for dependencies
- Run in milliseconds
- **Coverage Goal:** 80% of business logic modules

#### Tier 2: Integration Tests (Slower, Real Dependencies)
- Use Docker containers (Qdrant, SQLite in-memory)
- Test component interactions
- Run in seconds
- **Coverage Goal:** 50% of critical workflows

#### Tier 3: End-to-End Tests (Slowest, Full System)
- Test complete user workflows
- Use production-like environment
- Run in minutes
- **Coverage Goal:** 20% of user-facing features

### Refactoring Strategies by Pattern

#### Strategy A: Replace Mock-Only Assertions with Behavior Tests

**Before:**
```python
def test_collection_exists_auto_connect(self):
    with patch.object(setup, 'connect') as mock_connect:
        result = setup.collection_exists()
        mock_connect.assert_called_once()  # ❌ Only mock assertion
```

**After:**
```python
def test_collection_exists_auto_connect(self):
    setup = QdrantSetup(config=test_config)
    assert setup.client is None  # Verify precondition

    result = setup.collection_exists()

    assert result is True  # ✅ Verify actual behavior
    assert setup.client is not None  # ✅ Verify side effect
    assert isinstance(setup.client, QdrantClient)  # ✅ Verify type
```

**Benefits:**
- Tests real behavior, not implementation details
- Will catch actual bugs (e.g., connection failures)
- Survives refactoring (method names can change)

#### Strategy B: Use Fakes Instead of Mocks for Complex Dependencies

**Create Fake Implementation:**
```python
# tests/fixtures/fake_qdrant.py
class FakeQdrantStore(MemoryStore):
    """In-memory implementation for testing."""

    def __init__(self):
        self._storage: Dict[str, MemoryUnit] = {}
        self._initialized = False

    async def initialize(self) -> None:
        self._initialized = True

    async def store(self, memory: MemoryUnit) -> str:
        memory_id = str(uuid4())
        self._storage[memory_id] = memory
        return memory_id

    async def retrieve(self, memory_id: str) -> MemoryUnit:
        if memory_id not in self._storage:
            raise MemoryNotFoundError(f"Memory {memory_id} not found")
        return self._storage[memory_id]

    async def search(self, query: str, limit: int = 10) -> List[SearchResult]:
        # Simple keyword search for testing
        results = []
        for mem_id, memory in self._storage.items():
            if query.lower() in memory.content.lower():
                results.append(SearchResult(
                    memory=memory,
                    score=0.9,
                    retrieval_context={},
                ))
        return results[:limit]
```

**Usage in Tests:**
```python
# Before: 30 lines of mock setup
mock_store = MagicMock()
mock_store.initialize = AsyncMock()
mock_store.batch_store = AsyncMock(return_value=["id1", "id2"])
mock_store.client = MagicMock()
mock_store.client.scroll = MagicMock(return_value=([], None))
# ... 25 more lines ...

# After: 1 line
fake_store = FakeQdrantStore()
```

**Benefits:**
- Reusable across many tests
- Tests real logic (search, filtering, etc.)
- Easier to understand than mock hierarchies
- Can be extended to test edge cases

#### Strategy C: Use Docker Containers for Integration Tests

**Setup Qdrant Test Container:**
```python
# tests/integration/conftest.py
import pytest
import docker
from qdrant_client import QdrantClient

@pytest.fixture(scope="session")
async def qdrant_container():
    """Start Qdrant container for integration tests."""
    client = docker.from_env()
    container = client.containers.run(
        "qdrant/qdrant:v1.7.4",
        ports={'6333/tcp': 6334},  # Different port to avoid conflicts
        detach=True,
        remove=True,
    )

    # Wait for Qdrant to be ready
    qdrant_client = QdrantClient(url="http://localhost:6334")
    for _ in range(30):  # 30 second timeout
        try:
            qdrant_client.get_collections()
            break
        except Exception:
            await asyncio.sleep(1)

    yield container

    container.stop()

@pytest.fixture
async def clean_qdrant_store(qdrant_container):
    """Provide clean QdrantStore for each test."""
    config = ServerConfig(qdrant_url="http://localhost:6334")
    store = QdrantMemoryStore(config)
    await store.initialize()

    yield store

    # Cleanup: delete all collections
    client = await store._get_client()
    collections = client.get_collections().collections
    for collection in collections:
        client.delete_collection(collection.name)
    await store.close()
```

**Usage:**
```python
@pytest.mark.integration
async def test_batch_store_retrieval(clean_qdrant_store):
    """Test storing and retrieving multiple memories."""
    store = clean_qdrant_store

    # Create test memories
    memories = [
        MemoryUnit(content=f"Test memory {i}", category=MemoryCategory.SYSTEM)
        for i in range(100)
    ]

    # Store memories
    memory_ids = await store.batch_store(memories)
    assert len(memory_ids) == 100

    # Retrieve memories
    for memory_id in memory_ids:
        retrieved = await store.retrieve(memory_id)
        assert retrieved.content in [m.content for m in memories]
```

**Benefits:**
- Tests real Qdrant behavior (vector search, filters, etc.)
- Catches connection pooling bugs, timeout issues
- Validates schema compatibility
- Provides confidence for production deployment

#### Strategy D: Parametrize Duplicate Tests

**Before (50+ duplicate test methods):**
```python
def test_pool_creation_min_2_max_10(self):
    pool = QdrantConnectionPool(config, min_size=2, max_size=10)
    assert pool.min_size == 2
    assert pool.max_size == 10

def test_pool_creation_min_4_max_20(self):
    pool = QdrantConnectionPool(config, min_size=4, max_size=20)
    assert pool.min_size == 4
    assert pool.max_size == 20

# ... 48 more duplicate methods
```

**After (1 parametrized test):**
```python
@pytest.mark.parametrize("min_size,max_size,expected_min,expected_max", [
    (2, 10, 2, 10),
    (4, 20, 4, 20),
    (1, 5, 1, 5),
    (8, 16, 8, 16),
    # ... 46 more parameter sets
])
def test_pool_creation_parameters(min_size, max_size, expected_min, expected_max):
    pool = QdrantConnectionPool(config, min_size=min_size, max_size=max_size)
    assert pool.min_size == expected_min
    assert pool.max_size == expected_max
```

**Benefits:**
- 50 test methods → 1 parametrized test (98% reduction)
- Easier to add new test cases (just add tuple)
- Clearer test intent (shows variation being tested)
- Faster test suite (shared setup/teardown)

### Test Infrastructure Changes Needed

#### 1. Create Test Fixtures Library
```
tests/
├── fixtures/
│   ├── __init__.py
│   ├── fake_qdrant.py      # In-memory QdrantStore
│   ├── fake_embeddings.py  # Deterministic embedding generator
│   ├── fake_file_system.py # Virtual file system for indexing tests
│   ├── test_data.py        # Reusable test data builders
│   └── docker_containers.py # Docker container fixtures
```

#### 2. Add pytest Configuration
```ini
# pytest.ini
[pytest]
markers =
    unit: Fast unit tests with no I/O (deselect with '-m "not unit"')
    integration: Integration tests using Docker containers (deselect with '-m "not integration"')
    slow: Slow tests (>1 second) (deselect with '-m "not slow"')
    e2e: End-to-end tests (full system) (deselect with '-m "not e2e"')

# Run fast tests first, fail fast
addopts =
    --strict-markers
    --tb=short
    -v
    --maxfail=5

# Integration tests need Docker
integration_opts = --docker-compose=tests/docker-compose.test.yml
```

#### 3. Create Docker Compose for Tests
```yaml
# tests/docker-compose.test.yml
version: '3.8'
services:
  qdrant-test:
    image: qdrant/qdrant:v1.7.4
    ports:
      - "6334:6333"
    environment:
      - QDRANT_ALLOW_RECOVERY_MODE=true
```

#### 4. Add Test Data Builders
```python
# tests/fixtures/test_data.py
from dataclasses import dataclass
from typing import Optional

@dataclass
class MemoryBuilder:
    """Builder for test MemoryUnit instances."""

    content: str = "Test memory"
    category: MemoryCategory = MemoryCategory.SYSTEM
    importance: float = 0.5

    def with_content(self, content: str) -> 'MemoryBuilder':
        self.content = content
        return self

    def with_category(self, category: MemoryCategory) -> 'MemoryBuilder':
        self.category = category
        return self

    def build(self) -> MemoryUnit:
        return MemoryUnit(
            content=self.content,
            category=self.category,
            importance=self.importance,
        )

# Usage in tests
memory = MemoryBuilder().with_content("Custom content").with_category(MemoryCategory.USER).build()
```

---

## 4. Implementation Plan

### Phase 1: Foundation (Days 1-2)

#### Day 1 Morning: Audit and Categorize
- [ ] Run analysis script to identify all files with >50 mocks
- [ ] Categorize tests by pattern (Mock-Only, Deep Hierarchies, etc.)
- [ ] Create spreadsheet tracking refactoring progress
- [ ] Identify 10 highest-value files to refactor first

**Deliverable:** `planning_docs/TEST-010_audit_results.csv`

#### Day 1 Afternoon: Create Test Infrastructure
- [ ] Create `tests/fixtures/` directory structure
- [ ] Implement `FakeQdrantStore` with in-memory storage
- [ ] Implement `FakeEmbeddingGenerator` with deterministic outputs
- [ ] Add pytest.ini with markers configuration
- [ ] Create `tests/docker-compose.test.yml`

**Deliverable:** Test fixture library, pytest configuration

#### Day 2 Morning: Refactor Top 3 Worst Files
- [ ] Refactor `test_qdrant_setup_coverage.py` (15 mocks → fakes)
- [ ] Refactor `test_indexing_progress.py` (78 mocks → integration tests)
- [ ] Refactor `test_status_command.py` (80 mocks → behavior tests)

**Acceptance Criteria:**
- Each file: <10 mock instances remaining
- All tests pass (100% pass rate)
- Coverage maintained or improved

#### Day 2 Afternoon: Add Integration Test Suite
- [ ] Create `tests/integration/test_memory_workflow.py`
- [ ] Add Docker container fixtures
- [ ] Implement 5 critical workflow tests:
  - Store → Retrieve → Search
  - Batch operations
  - Connection pool under load
  - Error recovery
  - Multi-project isolation

**Acceptance Criteria:**
- 5 integration tests passing
- Tests use real Qdrant container
- Tests complete in <30 seconds

### Phase 2: Systematic Refactoring (Day 3)

#### Day 3 Morning: Batch Refactor Remaining Files (Files 4-10)
- [ ] Refactor `test_connection_pool.py` (46 mocks)
- [ ] Refactor `test_auto_indexing_service.py` (34 mocks)
- [ ] Refactor `test_background_indexer.py` (56 mocks)
- [ ] Refactor `test_web_server.py` (83 mocks)
- [ ] Refactor `test_health_command.py` (85 mocks)
- [ ] Refactor `test_indexing_service.py` (38 mocks)
- [ ] Refactor `test_file_watcher_coverage.py` (26 mocks)

**Strategy:**
- Use search/replace for common patterns
- Extract common setup to fixtures
- Parametrize duplicate tests

#### Day 3 Afternoon: Validation and Documentation
- [ ] Run full test suite: `pytest tests/ -n auto -v`
- [ ] Verify coverage ≥80% on core modules
- [ ] Run integration tests: `pytest -m integration -v`
- [ ] Update TESTING_GUIDE.md with new patterns
- [ ] Create before/after metrics report

**Final Metrics:**
- Mock count: 1,112 → <300 (73% reduction)
- Integration tests: 20 → 50+ (150% increase)
- Test runtime: Measure improvement from parametrization

---

## 5. Testing Strategy

### How to Verify Improvements

#### Metric 1: Mock Density Reduction
**Before:**
```bash
# Count mocks per file
grep -r "Mock(|MagicMock(|patch(" tests/unit/ | wc -l
# Result: 1,112 mocks
```

**After:**
```bash
# Should be <300 mocks
grep -r "Mock(|MagicMock(|patch(" tests/unit/ | wc -l
# Target: <300 mocks (73% reduction)
```

#### Metric 2: Behavior Assertion Ratio
**Before:**
```bash
# Count mock assertions vs behavior assertions
grep -r "assert_called" tests/ | wc -l  # ~800
grep -r "assert.*==" tests/ | wc -l     # ~1,200
# Ratio: 1:1.5 (too many mock assertions)
```

**After:**
```bash
# Should have 10x more behavior assertions
grep -r "assert_called" tests/ | wc -l  # <100
grep -r "assert.*==" tests/ | wc -l     # ~3,000
# Target Ratio: 1:30
```

#### Metric 3: Integration Test Coverage
**Before:** 20 integration tests (0.7%)
**After:** 50+ integration tests (2-3%)

#### Metric 4: Bug Detection Rate
**Measure:** Introduce intentional bugs, verify tests catch them

**Test Cases:**
1. Break connection pool cleanup → Should fail integration test
2. Remove error handling → Should fail behavior test
3. Change search algorithm → Should fail integration test
4. Break transaction rollback → Should fail integration test

**Success Criteria:** All 4 bugs caught by refactored tests

### Regression Prevention

#### Before Merging:
```bash
# Run full test suite
pytest tests/ -n auto -v

# Run integration tests separately
pytest tests/integration/ -v --docker-compose=tests/docker-compose.test.yml

# Verify coverage
pytest tests/ --cov=src --cov-report=term-missing
# Target: ≥80% on core modules

# Run verify script
python scripts/verify-complete.py
```

#### CI/CD Integration:
```yaml
# .github/workflows/test.yml
jobs:
  fast-tests:
    runs-on: ubuntu-latest
    steps:
      - run: pytest -m "not slow and not integration" -n auto

  integration-tests:
    runs-on: ubuntu-latest
    services:
      qdrant:
        image: qdrant/qdrant:v1.7.4
        ports:
          - 6334:6333
    steps:
      - run: pytest -m integration -v
```

---

## 6. Risk Assessment

### High Risks

#### Risk 1: Breaking Existing Tests During Refactoring
**Likelihood:** High
**Impact:** High
**Mitigation:**
- Refactor one file at a time
- Run tests after each file
- Use git worktree for isolation
- Create backup branch before starting

#### Risk 2: Integration Tests Flaky on CI
**Likelihood:** Medium
**Impact:** High
**Mitigation:**
- Use Docker container health checks
- Add retry logic for container startup
- Increase timeouts for CI (slower than local)
- Use pytest-xdist carefully (resource conflicts)

#### Risk 3: Test Runtime Increases (Docker Startup)
**Likelihood:** Medium
**Impact:** Medium
**Mitigation:**
- Use session-scoped fixtures (start container once)
- Run integration tests separately in CI
- Cache Docker images
- Measure and optimize slow tests

### Medium Risks

#### Risk 4: Fake Implementations Diverge from Real Ones
**Likelihood:** Medium
**Impact:** Medium
**Mitigation:**
- Share interface definitions (Protocol classes)
- Run integration tests against both fake and real
- Document fake limitations clearly
- Periodic audits (monthly)

#### Risk 5: Developers Continue Using Mocks
**Likelihood:** High
**Impact:** Low
**Mitigation:**
- Update TESTING_GUIDE.md with examples
- Add pre-commit hook warning on excessive mocks
- Code review checklist item
- Provide test templates

### Low Risks

#### Risk 6: Increased Test Complexity
**Likelihood:** Low
**Impact:** Low
**Mitigation:**
- Document fixtures thoroughly
- Provide examples in TESTING_GUIDE.md
- Offer to help during code reviews

---

## 7. Success Criteria

### Quantitative Metrics

| Metric | Current | Target | Measurement |
|--------|---------|--------|-------------|
| Mock instances | 1,112 | <300 | `grep -c` count |
| Integration tests | 20 | 50+ | Test count by marker |
| Mock assertions | ~800 | <100 | `assert_called` count |
| Behavior assertions | ~1,200 | ~3,000 | `assert.*==` count |
| Files with >50 mocks | 10 | 0 | Manual audit |
| Test runtime (unit) | ~45s | ~30s | `pytest --durations=0` |
| Test runtime (integration) | N/A | <120s | New metric |
| Bug detection rate | Unknown | 100% | Inject 4 bugs, all caught |

### Qualitative Metrics

#### Code Review Feedback
- [ ] Tests read more clearly (business logic obvious)
- [ ] Easier to understand test failures
- [ ] Fewer test changes needed during refactors
- [ ] New developers can write tests without help

#### Stability Metrics
- [ ] Fewer flaky test failures in CI
- [ ] Integration tests catch real bugs (vs. mock bugs)
- [ ] Confidence in test suite increases

### Definition of Done

**This task is complete when:**

1. **All 10 worst offender files refactored** (<10 mocks each)
2. **50+ integration tests created** (using real Qdrant)
3. **Test fixture library established** (FakeQdrantStore, etc.)
4. **Pytest markers configured** (`@pytest.mark.integration`)
5. **Docker test containers working** (in CI and locally)
6. **All tests passing** (100% pass rate)
7. **Coverage maintained** (≥80% core modules)
8. **Documentation updated** (TESTING_GUIDE.md, examples)
9. **Metrics report generated** (before/after comparison)
10. **verify-complete.py passes** (all 6 gates)

**Approval Required From:**
- Lead developer (code review)
- QA engineer (test strategy review)

---

## 8. Before/After Examples

### Example 1: test_qdrant_setup_coverage.py

#### Before (Mock-Only Assertion)
```python
def test_collection_exists_auto_connect(self):
    """Test collection_exists auto-connects if client is None (line 76)."""
    config = ServerConfig(qdrant_url="http://localhost:6333")
    setup = QdrantSetup(config)

    assert setup.client is None

    with patch.object(setup, 'connect') as mock_connect:
        mock_client = MagicMock()
        setup.client = mock_client

        # Mock get_collections response
        mock_collection = MagicMock()
        mock_collection.name = "test_collection"
        mock_collections = MagicMock()
        mock_collections.collections = [mock_collection]
        mock_client.get_collections.return_value = mock_collections

        # Reset client to None to trigger auto-connect
        setup.client = None

        def connect_side_effect():
            setup.client = mock_client

        mock_connect.side_effect = connect_side_effect

        result = setup.collection_exists()

        mock_connect.assert_called_once()  # ❌ ONLY ASSERTION
```

**Problems:**
- 22 lines of mock setup
- Only tests that `connect()` was called
- Doesn't verify collection_exists() logic
- Fragile (breaks if implementation changes)

#### After (Behavior Test with Fake)
```python
@pytest.mark.unit
def test_collection_exists_auto_connect(fake_qdrant_client):
    """Test that collection_exists auto-connects when client is None."""
    config = ServerConfig(qdrant_url="http://localhost:6333")
    setup = QdrantSetup(config)

    # Verify precondition
    assert setup.client is None

    # Call method - should auto-connect
    result = setup.collection_exists()

    # Verify behavior (not implementation)
    assert result is True  # ✅ Collection exists
    assert setup.client is not None  # ✅ Client was created
    assert isinstance(setup.client, QdrantClient)  # ✅ Correct type

    # Verify connection is usable
    collections = setup.client.get_collections()
    assert len(collections.collections) > 0  # ✅ Can fetch data
```

**Improvements:**
- 15 lines (vs 22)
- Tests actual behavior
- Uses fake client fixture (reusable)
- Survives refactoring

### Example 2: test_indexing_progress.py

#### Before (Deep Mock Hierarchies)
```python
@pytest.mark.asyncio
async def test_progress_callback_called_with_total(self, tmp_path):
    """Test that progress callback receives total file count."""
    # Create test files
    (tmp_path / "file1.py").write_text("def foo(): pass")
    (tmp_path / "file2.py").write_text("def bar(): pass")

    # Mock store and embedding generator (12 lines!)
    mock_store = MagicMock()
    mock_store.initialize = AsyncMock()
    mock_store.batch_store = AsyncMock(return_value=["id1", "id2"])
    mock_store.client = MagicMock()
    mock_store.client.scroll = MagicMock(return_value=([], None))
    mock_store.collection_name = "test"
    mock_store.close = AsyncMock()

    mock_embeddings = MagicMock()
    mock_embeddings.initialize = AsyncMock()
    mock_embeddings.batch_generate = AsyncMock(return_value=[[0.1] * 384, [0.2] * 384])
    mock_embeddings.close = AsyncMock()

    indexer = IncrementalIndexer(
        store=mock_store,
        embedding_generator=mock_embeddings,
        project_name="test-project"
    )
    await indexer.initialize()

    # Track progress callbacks
    callback_calls = []

    def progress_callback(current, total, current_file, error_info):
        callback_calls.append({
            "current": current,
            "total": total,
            "current_file": current_file,
            "error_info": error_info,
        })

    # Index directory with callback
    result = await indexer.index_directory(
        tmp_path,
        recursive=False,
        show_progress=False,
        progress_callback=progress_callback,
    )

    # Verify callbacks were made
    assert len(callback_calls) > 0

    # First callback should have total count
    first_call = callback_calls[0]
    assert first_call["total"] == 2  # ❌ Weak assertion
    assert first_call["current"] == 0
```

**Problems:**
- 12 lines just to create mocks
- Hardcoded mock return values
- Doesn't test actual indexing behavior
- Can't catch real embedding/storage bugs

#### After (Integration Test with Real Dependencies)
```python
@pytest.mark.integration
async def test_progress_callback_with_real_indexing(tmp_path, clean_qdrant_store, fake_embeddings):
    """Test progress callbacks during actual indexing workflow."""
    # Create test files
    (tmp_path / "file1.py").write_text("def foo(): pass")
    (tmp_path / "file2.py").write_text("def bar(): pass")

    # Use real store, fake embeddings (2 lines!)
    indexer = IncrementalIndexer(
        store=clean_qdrant_store,
        embedding_generator=fake_embeddings,
        project_name="test-project"
    )
    await indexer.initialize()

    # Track progress
    progress_events = []

    def progress_callback(current, total, current_file, error_info):
        progress_events.append({
            "current": current,
            "total": total,
            "file": current_file,
            "error": error_info,
        })

    # Index directory
    result = await indexer.index_directory(
        tmp_path,
        recursive=False,
        progress_callback=progress_callback,
    )

    # Verify complete workflow
    assert result["files_indexed"] == 2  # ✅ Files actually indexed
    assert result["chunks_stored"] > 0  # ✅ Chunks stored in Qdrant

    # Verify progress events
    assert len(progress_events) == 3  # initial + 2 files
    assert progress_events[0]["total"] == 2
    assert progress_events[1]["file"] == "file1.py"
    assert progress_events[2]["file"] == "file2.py"
    assert all(e["error"] is None for e in progress_events)

    # Verify stored data is searchable
    results = await clean_qdrant_store.search("foo", limit=10)
    assert len(results) > 0  # ✅ Data actually stored and searchable
    assert "foo" in results[0].memory.content
```

**Improvements:**
- Tests real indexing (catches actual bugs)
- Uses fixtures (2 lines vs 12)
- Verifies end-to-end workflow
- Tests search integration

---

## 9. Documentation Updates Required

### Files to Update

1. **TESTING_GUIDE.md**
   - Add "When to Use Mocks vs Fakes" section
   - Add "Test Fixture Library" reference
   - Add "Writing Integration Tests" guide
   - Add before/after examples

2. **CLAUDE.md**
   - Update testing metrics
   - Add integration test section
   - Reference new test markers

3. **CONTRIBUTING.md** (if exists)
   - Add testing best practices
   - Link to TESTING_GUIDE.md

4. **README.md**
   - Update test coverage metrics
   - Add "Running Integration Tests" section

### New Documentation

1. **tests/fixtures/README.md**
   - Document available fixtures
   - Usage examples
   - When to use each fixture

2. **tests/integration/README.md**
   - Docker container setup
   - Running integration tests locally
   - Debugging integration test failures

---

## 10. Appendix

### Audit Script (Generate Mock Count Report)

```python
#!/usr/bin/env python3
"""Generate mock usage report for test files."""

import re
from pathlib import Path
from collections import defaultdict

def count_mocks(file_path: Path) -> int:
    """Count mock instances in a file."""
    content = file_path.read_text()
    patterns = [
        r'\bMock\(',
        r'\bMagicMock\(',
        r'\bAsyncMock\(',
        r'@patch\(',
        r'@patch\.object\(',
    ]
    total = 0
    for pattern in patterns:
        total += len(re.findall(pattern, content))
    return total

def main():
    test_dir = Path("tests/unit")
    results = []

    for test_file in test_dir.rglob("test_*.py"):
        mock_count = count_mocks(test_file)
        line_count = len(test_file.read_text().splitlines())
        results.append({
            "file": str(test_file.relative_to(test_dir)),
            "mocks": mock_count,
            "lines": line_count,
            "density": mock_count / line_count if line_count > 0 else 0,
        })

    # Sort by mock count
    results.sort(key=lambda x: x["mocks"], reverse=True)

    # Print report
    print(f"{'File':<60} {'Mocks':<8} {'Lines':<8} {'Density':<8}")
    print("-" * 90)
    for r in results[:20]:  # Top 20
        print(f"{r['file']:<60} {r['mocks']:<8} {r['lines']:<8} {r['density']:<8.1%}")

    print(f"\nTotal mocks: {sum(r['mocks'] for r in results)}")
    print(f"Total files: {len(results)}")
    print(f"Average mocks per file: {sum(r['mocks'] for r in results) / len(results):.1f}")

if __name__ == "__main__":
    main()
```

**Usage:**
```bash
python scripts/audit_mocks.py > planning_docs/TEST-010_audit_results.txt
```

---

**Next Steps:**
1. Review this plan with team
2. Get approval to proceed
3. Create git worktree: `git worktree add .worktrees/TEST-010 -b TEST-010`
4. Begin Phase 1 implementation
5. Update this document with progress notes
