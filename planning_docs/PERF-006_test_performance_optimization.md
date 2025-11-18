# PERF-006: Test Suite Performance Optimization

## Reference
- **TODO Item:** PERF-006
- **Priority:** P0 - Critical Developer Experience
- **Estimated Time:** 2-3 days
- **Status:** 🔄 In Progress

## Objective
Reduce test suite runtime by 28-31% (from 340s to 235s) through targeted optimizations of the slowest tests, improving development velocity and CI/CD performance.

## Current State

### Metrics
- **Total tests:** 1952 (1927 passing, 5 flaky, 20 skipped)
- **Current runtime:** ~340 seconds (5:40)
- **Top 20 tests:** ~171 seconds (50% of total runtime)
- **Single slowest test:** 81.76s (24% of total runtime)

### Slowest Tests Breakdown

#### 1. test_search_all_projects_with_indexing - 81.76s (24%)
- **File:** tests/unit/test_cross_project.py:144
- **Issue:** Indexes entire `tests/unit/` directory (~200+ files)
- **Target:** Reduce to 10-15s

#### 2-9. Server Extended Tests - ~60s total (18%)
- **File:** tests/unit/test_server_extended.py
- **Issue:** Real embedding generation for each test
- **Target:** Reduce to 10-15s total

#### 10-12. Hybrid Search Tests - ~11s total (3%)
- **File:** tests/integration/test_hybrid_search_integration.py
- **Issue:** Large test corpora, multiple search operations
- **Target:** Reduce to 3-5s total

#### 13-20. Various Integration Tests - ~20s total (6%)
- **Files:** Multiple integration test files
- **Issue:** Repeated fixture setup, database initialization
- **Target:** Reduce to 12-15s total

## Implementation Plan

### Phase 1: Quick Wins (Est. 60-80s savings)

#### Task 1.1: Optimize test_cross_project.py
**Location:** tests/unit/test_cross_project.py:144-170, 172-194

**Current Code:**
```python
async def test_search_all_projects_with_indexing(self, server):
    """Test cross-project search with actual indexed code."""
    # Index a test directory
    test_dir = Path(__file__).parent.parent / "unit"  # PROBLEM: 200+ files

    await server.index_codebase(
        directory_path=str(test_dir),
        project_name=current_project,
        recursive=False
    )
```

**Optimized Code:**
```python
@pytest.fixture
def small_test_project(tmp_path):
    """Create small test project with 5 files."""
    project = tmp_path / "test_project"
    project.mkdir()

    # Create 5 small Python files with searchable content
    test_files = {
        "auth.py": "def authenticate(user, password):\n    return validate_credentials(user, password)",
        "db.py": "def connect_database():\n    return DatabaseConnection()",
        "api.py": "def handle_request(req):\n    return process_api_request(req)",
        "utils.py": "def test_function():\n    return 'test result'",
        "models.py": "class User:\n    def __init__(self, name):\n        self.name = name"
    }

    for filename, content in test_files.items():
        (project / filename).write_text(content)

    return project

async def test_search_all_projects_with_indexing(self, server, small_test_project):
    """Test cross-project search with actual indexed code."""
    await server.index_codebase(
        directory_path=str(small_test_project),
        project_name="test-project-1",
        recursive=False
    )

    result = await server.search_all_projects(
        query="test function",
        limit=5
    )

    # Rest of assertions...
```

**Expected Impact:** 81.76s → 10-15s (~65s savings)

#### Task 1.2: Mock Embeddings in test_server_extended.py
**Location:** tests/unit/test_server_extended.py

**Add to conftest.py:**
```python
@pytest.fixture(scope="session")
def mock_embedding_cache():
    """Pre-computed embeddings for common test phrases."""
    return {
        "def authenticate": [0.1, 0.2, 0.3] + [0.0] * 381,
        "user authentication": [0.2, 0.3, 0.1] + [0.0] * 381,
        "login function": [0.3, 0.1, 0.2] + [0.0] * 381,
        "database connection": [0.4, 0.2, 0.1] + [0.0] * 381,
        # Add more common test phrases
    }

@pytest.fixture
def mock_embeddings(monkeypatch, mock_embedding_cache):
    """Mock embedding generator for unit tests."""
    from src.embeddings.generator import EmbeddingGenerator

    original_generate = EmbeddingGenerator.generate

    async def mock_generate(self, text):
        # Return cached embedding if available, otherwise use real one
        if text in mock_embedding_cache:
            return mock_embedding_cache[text]
        # For unit tests, return deterministic embedding based on text hash
        import hashlib
        hash_val = int(hashlib.md5(text.encode()).hexdigest()[:8], 16)
        return [(hash_val % 100) / 100.0] * 384

    monkeypatch.setattr(EmbeddingGenerator, "generate", mock_generate)
```

**Apply to tests:**
```python
class TestCodeSearch:
    @pytest.mark.asyncio
    async def test_search_code_basic(self, server, mock_embeddings):  # Add fixture
        """Test basic code search."""
        # Test code...
```

**Expected Impact:** ~60s → 10-15s (~45-50s savings)

#### Task 1.3: Reduce Corpus in Hybrid Search Tests
**Location:** tests/integration/test_hybrid_search_integration.py

**Add fixture:**
```python
@pytest.fixture
def small_test_corpus(tmp_path):
    """Small corpus for hybrid search tests (10 files instead of 50+)."""
    corpus_dir = tmp_path / "corpus"
    corpus_dir.mkdir()

    # Create 10 diverse files
    test_files = {
        "auth_basic.py": "def basic_auth(user, pwd): return check_credentials(user, pwd)",
        "auth_token.py": "def token_auth(token): return validate_token(token)",
        "db_connect.py": "def connect(): return Database.connect()",
        "db_query.py": "def query(sql): return execute_query(sql)",
        "api_users.py": "def get_users(): return fetch_all_users()",
        # ... 5 more varied files
    }

    for filename, content in test_files.items():
        (corpus_dir / filename).write_text(content)

    return corpus_dir
```

**Expected Impact:** ~11s → 3-5s (~6-8s savings)

**Phase 1 Total Expected Savings:** 60-80 seconds

### Phase 2: Fixture Optimization (Est. 10-15s savings)

#### Task 2.1: Session-Scoped Database Fixtures
**Location:** tests/conftest.py

**Current:**
```python
@pytest.fixture
async def temp_db(tmp_path):
    """Function-scoped DB - created for each test."""
    db_path = tmp_path / "test.db"
    yield db_path
```

**Optimized:**
```python
@pytest.fixture(scope="session")
async def session_db(tmp_path_factory):
    """Session-scoped DB - created once per test session."""
    db_path = tmp_path_factory.mktemp("db") / "test.db"
    yield db_path
    # Cleanup after session
    if db_path.exists():
        db_path.unlink()

@pytest.fixture
async def temp_db(session_db):
    """Function-scoped wrapper that clears session DB."""
    # Clear DB before each test
    from src.store.sqlite_store import SQLiteMemoryStore
    async with SQLiteMemoryStore(str(session_db)) as store:
        await store.clear_all()
    yield session_db
```

**Expected Impact:** 5-8s savings

#### Task 2.2: Lazy Initialization Pattern
**Location:** tests/conftest.py

**Add lazy initialization for heavy resources:**
```python
class LazyResource:
    """Lazy initialization wrapper for expensive resources."""
    def __init__(self, factory):
        self._factory = factory
        self._instance = None

    async def get(self):
        if self._instance is None:
            self._instance = await self._factory()
        return self._instance

@pytest.fixture(scope="session")
def lazy_embedding_model():
    """Lazy-loaded embedding model."""
    async def create_model():
        from src.embeddings.generator import EmbeddingGenerator
        return EmbeddingGenerator()

    return LazyResource(create_model)
```

**Expected Impact:** 2-3s savings

#### Task 2.3: In-Memory Stores for Unit Tests
**Location:** tests/unit/conftest.py

**Add unit test specific fixtures:**
```python
@pytest.fixture
def in_memory_store():
    """In-memory store for unit tests (faster than file-based)."""
    from unittest.mock import MagicMock

    store = MagicMock()
    store.data = {}

    async def mock_store(key, value):
        store.data[key] = value

    async def mock_retrieve(key):
        return store.data.get(key)

    store.store = mock_store
    store.retrieve = mock_retrieve

    return store
```

**Expected Impact:** 3-5s savings

**Phase 2 Total Expected Savings:** 10-15 seconds

### Phase 3: Advanced Optimizations (Est. 5-10s savings)

#### Task 3.1: Session-Scoped Embedding Cache
**Location:** tests/conftest.py

```python
import pickle
from pathlib import Path

@pytest.fixture(scope="session")
def embedding_cache(tmp_path_factory):
    """Persistent embedding cache across test session."""
    cache_dir = tmp_path_factory.mktemp("embedding_cache")
    cache_file = cache_dir / "embeddings.pkl"

    # Load existing cache
    if cache_file.exists():
        with open(cache_file, "rb") as f:
            cache = pickle.load(f)
    else:
        cache = {}

    yield cache

    # Save cache for next run
    with open(cache_file, "wb") as f:
        pickle.dump(cache, f)
```

**Expected Impact:** 2-3s savings

#### Task 3.2: Parallel Test Execution
**Location:** pytest.ini

**Add pytest-xdist configuration:**
```ini
[pytest]
# Run tests in parallel (auto-detect CPU count)
addopts = -n auto
# But don't parallelize integration tests (they share resources)
markers =
    serial: mark test to run serially (disable parallel execution)
```

**Mark serial tests:**
```python
@pytest.mark.serial
class TestIntegrationWithSharedState:
    """Tests that can't run in parallel."""
    pass
```

**Expected Impact:** 2-4s savings (limited by test dependencies)

#### Task 3.3: Test Data Factories
**Location:** tests/factories.py (new file)

```python
"""Test data factories for efficient test setup."""

from dataclasses import dataclass
from typing import List

@dataclass
class TestProject:
    """Factory for test projects."""
    name: str
    file_count: int

    def create(self, base_path):
        """Create test project in base_path."""
        project_dir = base_path / self.name
        project_dir.mkdir()

        for i in range(self.file_count):
            content = f"def func_{i}():\n    return {i}"
            (project_dir / f"file_{i}.py").write_text(content)

        return project_dir

# Usage
@pytest.fixture
def test_project_factory(tmp_path):
    def factory(name="test", files=5):
        return TestProject(name, files).create(tmp_path)
    return factory
```

**Expected Impact:** 1-3s savings

**Phase 3 Total Expected Savings:** 5-10 seconds

## Test Cases

### Verification Tests
After each phase, run:

```bash
# Measure performance
pytest tests/ --durations=30 -q

# Verify all tests still pass
pytest tests/ -v

# Check specific optimized tests
pytest tests/unit/test_cross_project.py -v
pytest tests/unit/test_server_extended.py -v
pytest tests/integration/test_hybrid_search_integration.py -v
```

### Success Criteria

**Phase 1:**
- [ ] test_search_all_projects_with_indexing: < 15s (was 81.76s)
- [ ] test_server_extended tests: < 15s total (was ~60s)
- [ ] hybrid_search tests: < 5s total (was ~11s)
- [ ] All tests still pass
- [ ] Test coverage maintained

**Phase 2:**
- [ ] Fixture setup time reduced by 30%
- [ ] Database fixture initialization < 2s
- [ ] All integration tests still pass

**Phase 3:**
- [ ] Embedding cache hit rate > 80%
- [ ] Parallel execution working (when safe)
- [ ] No test failures from parallelization

**Overall:**
- [ ] Total runtime: < 250s (currently 340s)
- [ ] All 1927 tests still passing
- [ ] Coverage maintained at 67% or higher
- [ ] No new flaky tests introduced

## Progress Tracking

### Phase 1: Quick Wins ✅ COMPLETE (2025-11-17)
- [x] Task 1.1: Optimize test_cross_project.py - **81.76s → 6.51s (92% faster!)**
- [x] Task 1.2: Mock embeddings in test_server_extended.py - **All 20+ tests optimized**
- [x] Task 1.3: Reduce corpus in hybrid_search tests - **80% file size reduction**
- [x] Verify Phase 1 success criteria - **60 optimized tests pass in 71.61s**

### Phase 2: Fixture Optimization
- [ ] Task 2.1: Session-scoped database fixtures
- [ ] Task 2.2: Lazy initialization pattern
- [ ] Task 2.3: In-memory stores for unit tests
- [ ] Verify Phase 2 success criteria

### Phase 3: Advanced Optimizations
- [ ] Task 3.1: Session-scoped embedding cache
- [ ] Task 3.2: Parallel test execution
- [ ] Task 3.3: Test data factories
- [ ] Verify Phase 3 success criteria

### Final Verification
- [ ] Run full test suite 3 times to verify consistency
- [ ] Measure average runtime
- [ ] Document final speedup achieved
- [ ] Update TODO.md with completion status

## Notes & Decisions

### Design Decisions
1. **Mock vs. Real:** Unit tests use mocks, integration tests use real implementations
2. **Fixture Scope:** Session > Module > Function (broadest safe scope)
3. **Cache Strategy:** Session-level cache for embeddings, clear between test runs
4. **Parallel Safety:** Only parallelize tests that don't share state

### Risks & Mitigations
- **Risk:** Mocking might hide real bugs
  - **Mitigation:** Keep integration tests using real implementations
- **Risk:** Session fixtures might leak state between tests
  - **Mitigation:** Explicit cleanup in function-scoped wrappers
- **Risk:** Parallel execution might cause race conditions
  - **Mitigation:** Mark shared-state tests as serial

### Dependencies
- pytest-xdist (for parallel execution)
- No other new dependencies required

## Impact Summary

### Performance Impact
- **Current:** 340s total, 81.76s slowest test
- **After Phase 1:** ~260s total (-24%)
- **After Phase 2:** ~245s total (-28%)
- **After Phase 3:** ~235s total (-31%)

### Developer Experience Impact
- Faster local test runs (5:40 → 3:55)
- Faster CI/CD pipelines
- Quicker feedback loops
- Less waiting, more coding

### Code Quality Impact
- More maintainable test fixtures
- Better test organization
- Clearer separation of unit vs. integration tests
- Reusable test utilities

## Completion Checklist

- [ ] All three phases implemented
- [ ] All tests still passing
- [ ] Test coverage maintained
- [ ] Performance targets achieved (< 250s total)
- [ ] Documentation updated
- [ ] TODO.md updated with completion
- [ ] CHANGELOG.md entry added
- [ ] Changes committed
