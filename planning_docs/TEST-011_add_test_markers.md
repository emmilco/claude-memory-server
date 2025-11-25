# TEST-011: Add Test Markers and Categorization

**Task ID:** TEST-011
**Type:** Testing Infrastructure
**Priority:** Medium
**Estimated Effort:** ~1 day
**Status:** Planning
**Created:** 2025-11-25

---

## 1. Overview

### Problem Summary
The current test suite lacks categorization and filtering capabilities. With ~2,740 tests running on every commit, developers cannot:

- Run only fast tests during development
- Skip slow integration tests for quick feedback
- Filter by test type (unit vs integration vs e2e)
- Identify which tests require Docker/Qdrant/external services
- Parallelize appropriately (some tests can't run in parallel)

**Current Situation:**
- **ZERO** test files use `@pytest.mark` for categorization
- All tests run together (unit, integration, slow, fast)
- CI runs entire suite (~2-5 minutes per run)
- Developers wait for slow tests even when editing docs
- No way to run "smoke tests" subset

### Impact Assessment

**Developer Experience:**
- Average test run: 45 seconds (unit) + unknown (integration)
- Wasted time: 30-40 seconds per run when only unit tests needed
- Context switching: Developers lose focus waiting for tests
- CI costs: Running all tests on every commit wastes compute

**Business Impact:**
- Slower development velocity
- Higher CI/CD costs
- Reduced test-driven development adoption (too slow)
- Harder to diagnose test failures (no categories in output)

**Risk Level:** **MEDIUM** - Slows development but doesn't break functionality

---

## 2. Current State Analysis

### Test Distribution Analysis

#### By Speed (Estimated)
```
Fast tests (<0.1s):      ~2,200 tests (80%)  - Pure unit tests
Medium tests (0.1-1s):   ~500 tests (18%)    - Unit tests with I/O
Slow tests (>1s):        ~40 tests (2%)      - Integration tests
Very slow tests (>5s):   ~20 tests (~1%)     - E2E tests
```

#### By Type (Inferred from file structure)
```
tests/unit/              ~2,677 tests (97%)
tests/integration/       ~20 tests (0.7%)
tests/security/          ~43 tests (1.6%)
tests/ (root)            ~20 tests (0.7%)
```

#### By External Dependencies
```
No dependencies:         ~2,200 tests (80%)  - Pure Python
Needs Qdrant:            ~400 tests (15%)    - Qdrant operations
Needs Docker:            ~20 tests (1%)      - Integration tests
Needs network:           ~43 tests (1.6%)    - Security tests
Needs file system:       ~77 tests (3%)      - Indexing tests
```

### Current Test Execution Patterns

#### Local Development
```bash
# Developer wants to run only fast tests
pytest tests/  # ❌ Runs ALL 2,740 tests (~45 seconds)

# Developer wants to test only unit tests
pytest tests/unit/  # ✅ Works but still includes slow unit tests

# Developer wants to skip integration tests
# ❌ NO WAY TO DO THIS - must manually exclude directories
```

#### CI/CD Pipeline
```yaml
# .github/workflows/test.yml
- name: Run tests
  run: pytest tests/ -n auto -v

# ❌ Problems:
# - Runs all tests on every commit
# - No fast/slow separation
# - Can't run smoke tests first
# - All tests fail if Qdrant not running
```

### Pain Points

1. **No Fast Feedback Loop**
   - Can't run "smoke tests" (critical path only)
   - Must wait for all tests even for trivial changes

2. **Resource Waste**
   - CI runs integration tests for documentation changes
   - Developers run Docker-dependent tests unnecessarily

3. **Poor Test Organization**
   - Can't identify which tests require setup
   - Hard to debug flaky tests (no categorization)

4. **Parallel Execution Issues**
   - Some tests can't run in parallel (file system conflicts)
   - No markers to prevent parallel execution

5. **Documentation Gap**
   - New developers don't know which tests to run
   - No guidance on test categories

---

## 3. Proposed Solution

### Marker Definitions and Criteria

#### Primary Markers (Test Type)

##### 1. `@pytest.mark.unit`
**Definition:** Isolated tests with no external dependencies

**Criteria:**
- No network I/O
- No file system I/O (except in-memory or tmp_path)
- No Docker containers
- No subprocess calls
- Execution time: <100ms (typically <10ms)
- Fully isolated (can run in parallel)

**Examples:**
```python
@pytest.mark.unit
def test_parse_query_string():
    """Test query string parsing (pure function)."""
    result = parse_query("test query")
    assert result == ["test", "query"]

@pytest.mark.unit
def test_memory_category_enum():
    """Test MemoryCategory enum values."""
    assert MemoryCategory.SYSTEM.value == "system"
```

**Auto-Applied To:**
- All tests in `tests/unit/` by default (unless overridden)

##### 2. `@pytest.mark.integration`
**Definition:** Tests that verify component interactions

**Criteria:**
- Uses real external services (Qdrant, Docker, etc.)
- May use network I/O
- Tests multiple components together
- Execution time: 0.1s - 5s
- May require setup/teardown

**Examples:**
```python
@pytest.mark.integration
async def test_end_to_end_memory_workflow(clean_qdrant_store):
    """Test complete memory store/retrieve/search workflow."""
    store = clean_qdrant_store

    # Store memory
    memory_id = await store.store(memory)

    # Retrieve memory
    retrieved = await store.retrieve(memory_id)
    assert retrieved.content == memory.content

    # Search for memory
    results = await store.search("test query")
    assert len(results) > 0
```

**Auto-Applied To:**
- All tests in `tests/integration/`

##### 3. `@pytest.mark.e2e`
**Definition:** End-to-end tests covering full user workflows

**Criteria:**
- Tests complete user scenarios
- Uses production-like environment
- May involve multiple services
- Execution time: >5s
- Comprehensive validation

**Examples:**
```python
@pytest.mark.e2e
async def test_complete_indexing_workflow(tmp_path):
    """Test complete codebase indexing and search."""
    # Create sample codebase
    create_test_repository(tmp_path)

    # Index codebase
    indexer = IncrementalIndexer(...)
    await indexer.index_directory(tmp_path)

    # Search indexed code
    results = await indexer.search("function definition")

    # Verify results
    assert len(results) > 0
```

#### Secondary Markers (Execution Characteristics)

##### 4. `@pytest.mark.slow`
**Definition:** Tests that take >1 second to execute

**Criteria:**
- Execution time: >1s
- Often involves I/O, network, or computation
- Should be run less frequently

**Usage:**
```python
@pytest.mark.unit
@pytest.mark.slow
def test_large_dataset_processing():
    """Test processing 10,000 records."""
    # ... slow computation ...
```

**Note:** Can be combined with other markers

##### 5. `@pytest.mark.requires_docker`
**Definition:** Tests requiring Docker containers

**Criteria:**
- Needs Docker daemon running
- Uses Docker containers (Qdrant, etc.)
- May fail if Docker not available

**Usage:**
```python
@pytest.mark.integration
@pytest.mark.requires_docker
async def test_qdrant_connection_pool(qdrant_container):
    """Test connection pooling with real Qdrant."""
```

##### 6. `@pytest.mark.requires_gpu`
**Definition:** Tests requiring GPU hardware

**Criteria:**
- Needs CUDA/GPU available
- Tests GPU-accelerated embeddings
- Should skip gracefully if GPU unavailable

**Usage:**
```python
@pytest.mark.unit
@pytest.mark.requires_gpu
def test_gpu_embedding_generation():
    """Test GPU-accelerated embedding generation."""
    if not torch.cuda.is_available():
        pytest.skip("GPU not available")
```

##### 7. `@pytest.mark.no_parallel`
**Definition:** Tests that cannot run in parallel

**Criteria:**
- Uses global state
- File system conflicts
- Port conflicts
- Requires exclusive access

**Usage:**
```python
@pytest.mark.integration
@pytest.mark.no_parallel
async def test_file_watcher_exclusive():
    """Test file watcher (requires exclusive file access)."""
```

#### Tertiary Markers (Functional Categories)

##### 8. `@pytest.mark.security`
**Definition:** Security-related tests

**Auto-Applied To:**
- All tests in `tests/security/`

##### 9. `@pytest.mark.smoke`
**Definition:** Critical path tests (must pass for basic functionality)

**Criteria:**
- Tests core functionality
- Should run first in CI
- Fast execution (<1s)
- High value (catch most regressions)

**Usage:**
```python
@pytest.mark.unit
@pytest.mark.smoke
def test_server_initialization():
    """Test that server can initialize."""
    server = MemoryRAGServer(config)
    assert server is not None
```

---

## 4. Implementation Plan

### Phase 1: Setup and Configuration (Hour 1)

#### Step 1.1: Create pytest.ini Configuration
```ini
# pytest.ini
[pytest]
markers =
    unit: Fast unit tests with no I/O (deselect with '-m "not unit"')
    integration: Integration tests using real services (deselect with '-m "not integration"')
    e2e: End-to-end tests covering full workflows (deselect with '-m "not e2e"')
    slow: Slow tests (>1 second) (deselect with '-m "not slow"')
    smoke: Critical path tests that must pass (select with '-m smoke')
    requires_docker: Tests requiring Docker containers (deselect with '-m "not requires_docker"')
    requires_gpu: Tests requiring GPU hardware (deselect with '-m "not requires_gpu"')
    no_parallel: Tests that cannot run in parallel (run with '-n 0')
    security: Security-focused tests (select with '-m security')

# Default options
addopts =
    --strict-markers          # Fail on unknown markers
    --tb=short                # Short traceback format
    -v                        # Verbose output
    --maxfail=5               # Stop after 5 failures

# Parallel execution
# Run unit tests in parallel by default, skip no_parallel tests
parallel_exclude = no_parallel
```

**Validation:**
```bash
pytest --markers  # List all markers
pytest --strict-markers tests/  # Verify no unknown markers
```

#### Step 1.2: Create conftest.py with Auto-Marker Application
```python
# tests/conftest.py
import pytest

def pytest_collection_modifyitems(config, items):
    """Auto-apply markers based on test location."""
    for item in items:
        # Auto-apply markers based on directory
        if "tests/unit/" in str(item.fspath):
            item.add_marker(pytest.mark.unit)
        elif "tests/integration/" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
            item.add_marker(pytest.mark.requires_docker)  # Most integration tests need Docker
        elif "tests/security/" in str(item.fspath):
            item.add_marker(pytest.mark.security)

        # Auto-mark slow tests based on execution time (can be refined later)
        # This requires pytest-timeout plugin

        # Skip GPU tests if GPU not available
        if "requires_gpu" in item.keywords:
            import torch
            if not torch.cuda.is_available():
                item.add_marker(pytest.mark.skip(reason="GPU not available"))

        # Skip Docker tests if Docker not running
        if "requires_docker" in item.keywords:
            import docker
            try:
                client = docker.from_env()
                client.ping()
            except Exception:
                item.add_marker(pytest.mark.skip(reason="Docker not available"))
```

### Phase 2: Categorize Existing Tests (Hours 2-5)

#### Strategy: File-by-File Categorization

##### Step 2.1: Auto-Mark Unit Tests (Hour 2)
Since most tests in `tests/unit/` are already unit tests, they'll be auto-marked by `conftest.py`.

**Manual Review Required For:**
- Tests using `tmp_path` (legitimate for unit tests)
- Tests using `AsyncMock` with I/O
- Tests with Docker/Qdrant dependencies

**Action Items:**
```bash
# Find unit tests that might need `@pytest.mark.slow`
grep -r "sleep(" tests/unit/  # Likely slow
grep -r "docker" tests/unit/  # Might be integration
grep -r "QdrantClient" tests/unit/  # Might need requires_docker
```

**Estimate:** ~2,200 tests auto-marked, ~100 tests need manual review

##### Step 2.2: Mark Integration Tests (Hour 3)
Review `tests/integration/` and add appropriate markers.

**Template:**
```python
@pytest.mark.integration
@pytest.mark.requires_docker
async def test_integration_workflow():
    """Integration test description."""
```

**Estimate:** ~20 tests (most in this directory)

##### Step 2.3: Mark Slow Tests (Hour 4)

**Automated Detection:**
```python
# scripts/detect_slow_tests.py
"""Detect slow tests by running them and measuring execution time."""

import subprocess
import json
from pathlib import Path

# Run tests with duration reporting
result = subprocess.run(
    ["pytest", "tests/", "--durations=0", "--json-report", "--json-report-file=test_times.json"],
    capture_output=True,
)

# Parse results
with open("test_times.json") as f:
    data = json.load(f)

slow_tests = []
for test in data["tests"]:
    if test["duration"] > 1.0:  # >1 second
        slow_tests.append({
            "name": test["nodeid"],
            "duration": test["duration"],
        })

# Sort by duration
slow_tests.sort(key=lambda x: x["duration"], reverse=True)

# Print report
print("Slow tests (>1s):")
for test in slow_tests:
    print(f"  {test['name']}: {test['duration']:.2f}s")

print(f"\nTotal slow tests: {len(slow_tests)}")
```

**Manual Marking:**
```bash
# Run detection script
python scripts/detect_slow_tests.py > planning_docs/TEST-011_slow_tests.txt

# Add markers to identified tests
# Example: tests/unit/test_indexing_service.py
@pytest.mark.unit
@pytest.mark.slow  # ← Add this marker
async def test_large_codebase_indexing():
    """Test indexing 1,000 files."""
```

**Estimate:** ~40-60 tests

##### Step 2.4: Mark Smoke Tests (Hour 5)

**Criteria for Smoke Tests:**
- Tests core initialization
- Tests critical workflows
- Fast execution (<1s)
- High regression detection value

**Examples:**
```python
# tests/unit/test_server.py
@pytest.mark.unit
@pytest.mark.smoke
def test_server_initialization():
    """Test server can initialize with default config."""

# tests/unit/test_store/test_qdrant_store.py
@pytest.mark.integration
@pytest.mark.smoke
async def test_basic_store_retrieve():
    """Test basic store and retrieve operations."""
```

**Estimate:** ~50 tests identified as smoke tests

##### Step 2.5: Mark Special Cases (Hour 5)

**No Parallel Tests:**
```bash
# Find tests using file system exclusively
grep -r "NamedTemporaryFile\|test_output" tests/

# Find tests binding to ports
grep -r "bind\|listen\|port" tests/
```

**GPU Tests:**
```bash
# Find GPU-related tests
grep -r "cuda\|gpu\|torch.device" tests/
```

**Estimate:** ~20 tests

### Phase 3: CI/CD Integration (Hours 6-7)

#### Step 3.1: Update GitHub Actions Workflow

**Current:**
```yaml
# .github/workflows/test.yml
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - name: Run tests
        run: pytest tests/ -n auto -v
```

**After:**
```yaml
# .github/workflows/test.yml
jobs:
  smoke-tests:
    name: Smoke Tests (Fast Feedback)
    runs-on: ubuntu-latest
    timeout-minutes: 2
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.13'
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Run smoke tests
        run: pytest -m smoke -v --tb=short

  unit-tests:
    name: Unit Tests
    runs-on: ubuntu-latest
    timeout-minutes: 5
    needs: smoke-tests  # Only run if smoke tests pass
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.13'
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Run unit tests
        run: pytest -m "unit and not slow" -n auto -v

  integration-tests:
    name: Integration Tests
    runs-on: ubuntu-latest
    timeout-minutes: 10
    needs: unit-tests  # Only run if unit tests pass
    services:
      qdrant:
        image: qdrant/qdrant:v1.7.4
        ports:
          - 6334:6333
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.13'
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Wait for Qdrant
        run: |
          timeout 30 bash -c 'until curl -f http://localhost:6334; do sleep 1; done'
      - name: Run integration tests
        run: pytest -m integration -v
        env:
          QDRANT_URL: http://localhost:6334

  slow-tests:
    name: Slow Tests
    runs-on: ubuntu-latest
    timeout-minutes: 15
    needs: unit-tests
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.13'
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Run slow tests
        run: pytest -m slow -v
```

**Benefits:**
- Smoke tests run first (fast feedback)
- Fail fast (stop if smoke tests fail)
- Parallel jobs (smoke + unit run together after smoke passes)
- Integration tests only if unit tests pass
- Clear job names in GitHub UI

#### Step 3.2: Create Makefile Shortcuts

```makefile
# Makefile
.PHONY: test test-fast test-unit test-integration test-smoke test-slow test-all

# Default: run fast tests only
test: test-fast

# Fast tests (unit, no slow)
test-fast:
	pytest -m "unit and not slow" -n auto -v

# All unit tests (including slow)
test-unit:
	pytest -m unit -n auto -v

# Integration tests (requires Docker)
test-integration:
	pytest -m integration -v

# Smoke tests only
test-smoke:
	pytest -m smoke -v

# Slow tests only
test-slow:
	pytest -m slow -v

# Security tests only
test-security:
	pytest -m security -v

# All tests (full suite)
test-all:
	pytest tests/ -n auto -v

# Watch mode (re-run on changes)
test-watch:
	pytest-watch -m "unit and not slow" -n auto -v
```

**Usage:**
```bash
make test           # Fast tests (default for development)
make test-smoke     # Smoke tests only
make test-integration  # Integration tests
make test-all       # Full suite (before commit)
```

### Phase 4: Documentation (Hour 8)

#### Step 4.1: Update TESTING_GUIDE.md

**Add Section: "Test Markers and Categories"**

```markdown
## Test Markers and Categories

### Available Markers

| Marker | Usage | Description |
|--------|-------|-------------|
| `@pytest.mark.unit` | Auto-applied | Fast, isolated unit tests |
| `@pytest.mark.integration` | Manual | Tests with real services |
| `@pytest.mark.e2e` | Manual | Full workflow tests |
| `@pytest.mark.slow` | Manual | Tests >1 second |
| `@pytest.mark.smoke` | Manual | Critical path tests |
| `@pytest.mark.requires_docker` | Manual | Needs Docker running |
| `@pytest.mark.requires_gpu` | Manual | Needs GPU hardware |
| `@pytest.mark.no_parallel` | Manual | Can't run in parallel |
| `@pytest.mark.security` | Auto-applied | Security tests |

### Running Tests by Category

```bash
# Fast unit tests (default for development)
pytest -m "unit and not slow"

# Smoke tests only (fastest feedback)
pytest -m smoke

# Integration tests (requires Docker)
pytest -m integration

# All tests except slow
pytest -m "not slow"

# Specific category
pytest -m security
```

### Writing New Tests

**Unit Test Template:**
```python
import pytest

@pytest.mark.unit
def test_function_name():
    """Test description."""
    # Arrange
    input_data = ...

    # Act
    result = function_under_test(input_data)

    # Assert
    assert result == expected_output
```

**Integration Test Template:**
```python
import pytest

@pytest.mark.integration
@pytest.mark.requires_docker
async def test_integration_workflow(clean_qdrant_store):
    """Test end-to-end workflow."""
    # Test code...
```

**When to Mark as Slow:**
- Test execution time >1 second
- Heavy computation or I/O
- Processing large datasets

**When to Mark as Smoke:**
- Tests core initialization
- Tests critical workflows
- High regression detection value
- Fast execution (<1s)
```

#### Step 4.2: Update CLAUDE.md

**Update Testing Section:**
```markdown
### Testing

**Run tests by category:**
```bash
# Fast feedback (recommended for development)
make test  # or: pytest -m "unit and not slow" -n auto

# Smoke tests (critical path only)
pytest -m smoke

# Full suite (before committing)
make test-all

# Integration tests (requires Docker)
make test-integration
```

**Test markers:**
- `@pytest.mark.unit` - Fast, isolated tests
- `@pytest.mark.integration` - Tests with real services
- `@pytest.mark.slow` - Tests >1 second
- `@pytest.mark.smoke` - Critical path tests

See TESTING_GUIDE.md for complete marker reference.
```

#### Step 4.3: Create tests/README.md

```markdown
# Test Suite Organization

## Structure

```
tests/
├── unit/              # Fast, isolated unit tests (~2,200 tests)
├── integration/       # Integration tests with real services (~20 tests)
├── security/          # Security-focused tests (~43 tests)
├── conftest.py        # Shared fixtures and marker configuration
└── docker-compose.test.yml  # Docker services for integration tests
```

## Quick Start

**Development (fast feedback):**
```bash
make test  # Runs unit tests (excluding slow)
```

**Before committing:**
```bash
make test-all  # Runs full suite
python scripts/verify-complete.py  # Quality gates
```

**Integration tests:**
```bash
# Start Docker containers
docker-compose -f tests/docker-compose.test.yml up -d

# Run integration tests
make test-integration

# Stop containers
docker-compose -f tests/docker-compose.test.yml down
```

## Test Categories

See TESTING_GUIDE.md for complete documentation.
```

---

## 5. Testing Strategy

### Validation Steps

#### Step 1: Verify Markers Work
```bash
# Test smoke marker
pytest -m smoke -v
# Expected: ~50 tests run

# Test unit marker (auto-applied)
pytest -m unit -v
# Expected: ~2,200 tests run

# Test integration marker
pytest -m integration -v
# Expected: ~20 tests run

# Test slow marker
pytest -m slow -v
# Expected: ~40-60 tests run

# Test marker combinations
pytest -m "unit and not slow" -v
# Expected: ~2,140 tests run (2,200 - 60 slow)
```

#### Step 2: Verify CI Workflow
```bash
# Push to branch, verify GitHub Actions runs:
# 1. Smoke tests (should complete in <2 min)
# 2. Unit tests (should complete in <5 min)
# 3. Integration tests (should complete in <10 min)
# 4. Slow tests (should complete in <15 min)
```

#### Step 3: Verify Makefile Shortcuts
```bash
make test-smoke      # Should run only smoke tests
make test-fast       # Should run unit tests (no slow)
make test-integration # Should require Docker
make test-all        # Should run all tests
```

#### Step 4: Verify Auto-Skip Logic
```bash
# Without Docker running
pytest -m requires_docker -v
# Expected: Tests skipped with "Docker not available" message

# Without GPU
pytest -m requires_gpu -v
# Expected: Tests skipped with "GPU not available" message
```

### Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Smoke test runtime | <30s | `pytest -m smoke --durations=0` |
| Unit test runtime (no slow) | <30s | `pytest -m "unit and not slow" --durations=0` |
| Integration test runtime | <2 min | `pytest -m integration --durations=0` |
| Full suite runtime | <5 min | `pytest tests/ --durations=0` |
| Marker coverage | 100% | All tests have at least one marker |
| CI feedback time | <2 min | Smoke tests complete |

---

## 6. Risk Assessment

### Low Risks

#### Risk 1: Auto-Marker Logic Incorrect
**Likelihood:** Low
**Impact:** Low
**Mitigation:**
- Test conftest.py logic separately
- Verify markers applied correctly: `pytest --collect-only`
- Manual review of auto-marked tests

#### Risk 2: Developers Forget to Add Markers
**Likelihood:** Medium
**Impact:** Low
**Mitigation:**
- conftest.py auto-applies directory-based markers
- Pre-commit hook can check for markers
- Code review checklist

#### Risk 3: Marker Confusion (Too Many Categories)
**Likelihood:** Low
**Impact:** Low
**Mitigation:**
- Keep markers simple (primary: unit/integration/e2e)
- Document clearly in TESTING_GUIDE.md
- Provide examples

### Very Low Risks

#### Risk 4: CI Configuration Errors
**Likelihood:** Low
**Impact:** Low
**Mitigation:**
- Test locally first: `act` (GitHub Actions locally)
- Review workflow changes carefully
- Monitor first few CI runs

---

## 7. Success Criteria

### Quantitative Metrics

| Metric | Current | Target | Measurement |
|--------|---------|--------|-------------|
| Tests with markers | 0% | 100% | `pytest --collect-only` count |
| Smoke test runtime | N/A | <30s | `pytest -m smoke --durations=0` |
| Fast test runtime | ~45s | <30s | `pytest -m "unit and not slow"` |
| CI feedback time | ~5 min | <2 min | GitHub Actions smoke test job |
| Marker types defined | 0 | 9 | Count in pytest.ini |
| Developer docs | 0 | 3 | README, TESTING_GUIDE, CLAUDE updates |

### Qualitative Metrics

#### Code Review Feedback
- [ ] Developers can run appropriate test subset
- [ ] CI provides faster feedback
- [ ] Test failures easier to categorize
- [ ] Clear guidance on which tests to run when

#### Developer Experience
- [ ] `make test` provides fast feedback (<30s)
- [ ] Integration tests skipped when Docker not available
- [ ] Smoke tests catch most regressions quickly

### Definition of Done

**This task is complete when:**

1. **pytest.ini configured** with all 9 markers defined
2. **conftest.py created** with auto-marker logic
3. **All tests categorized** (100% have at least one marker)
4. **Smoke tests identified** (~50 critical tests marked)
5. **Slow tests identified** (~40-60 tests marked)
6. **Integration tests marked** (all require Docker)
7. **CI workflow updated** (smoke → unit → integration → slow)
8. **Makefile created** with test shortcuts
9. **Documentation updated** (TESTING_GUIDE.md, CLAUDE.md, tests/README.md)
10. **Verification complete** (all marker queries work correctly)
11. **verify-complete.py passes** (all 6 gates)

**Approval Required From:**
- Lead developer (marker strategy review)
- DevOps (CI/CD workflow approval)

---

## 8. File-by-File Categorization Approach

### Directory-Based Auto-Marking (via conftest.py)

```
tests/unit/          → @pytest.mark.unit (auto-applied)
tests/integration/   → @pytest.mark.integration + @pytest.mark.requires_docker (auto-applied)
tests/security/      → @pytest.mark.security (auto-applied)
tests/e2e/           → @pytest.mark.e2e (auto-applied, if created)
```

### Manual Marking Required For

#### Slow Unit Tests (~40-60 tests)
**Detection:** Run `python scripts/detect_slow_tests.py`
**Action:** Add `@pytest.mark.slow` to tests >1s

**Examples:**
- `test_indexing_service.py::test_large_codebase_indexing`
- `test_background_indexer.py::test_full_repository_scan`
- `test_embedding_cache.py::test_cache_with_10k_entries`

#### Smoke Tests (~50 tests)
**Criteria:** Critical functionality + fast execution
**Action:** Add `@pytest.mark.smoke` to selected tests

**Examples:**
- `test_server.py::test_server_initialization`
- `test_qdrant_store.py::test_basic_store_retrieve`
- `test_embedding_generator.py::test_generate_single_embedding`
- `test_config.py::test_config_loading`

#### No-Parallel Tests (~10-20 tests)
**Detection:** Tests using:
- File system (NamedTemporaryFile, test output files)
- Ports (web server, Qdrant)
- Global state

**Examples:**
- `test_file_watcher.py::test_watch_directory_events`
- `test_web_server.py::test_server_startup`
- `test_health_scheduler.py::test_background_jobs`

#### GPU Tests (~5 tests)
**Detection:** `grep -r "cuda\|gpu\|torch.device" tests/`
**Action:** Add `@pytest.mark.requires_gpu`

**Examples:**
- `test_generator_gpu.py::test_gpu_acceleration`
- `test_embedding_performance.py::test_gpu_vs_cpu_speed`

---

## 9. Example Marker Usage

### Example 1: Simple Unit Test
```python
import pytest
from src.core.models import MemoryCategory

@pytest.mark.unit
def test_memory_category_values():
    """Test MemoryCategory enum has correct values."""
    assert MemoryCategory.SYSTEM.value == "system"
    assert MemoryCategory.USER.value == "user"
    assert MemoryCategory.AGENT.value == "agent"
```

### Example 2: Slow Unit Test
```python
import pytest

@pytest.mark.unit
@pytest.mark.slow
async def test_process_large_dataset():
    """Test processing 10,000 records."""
    records = [generate_record(i) for i in range(10000)]
    result = await process_batch(records)
    assert len(result) == 10000
```

### Example 3: Integration Test
```python
import pytest

@pytest.mark.integration
@pytest.mark.requires_docker
async def test_qdrant_connection_pool(clean_qdrant_store):
    """Test connection pool with real Qdrant instance."""
    store = clean_qdrant_store

    # Test concurrent operations
    tasks = [store.store(MemoryUnit(content=f"Memory {i}")) for i in range(100)]
    memory_ids = await asyncio.gather(*tasks)

    assert len(memory_ids) == 100
```

### Example 4: Smoke Test
```python
import pytest

@pytest.mark.unit
@pytest.mark.smoke
def test_server_can_initialize():
    """Test server initializes with default config (smoke test)."""
    config = ServerConfig()
    server = MemoryRAGServer(config)
    assert server is not None
    assert server.config == config
```

### Example 5: No-Parallel Test
```python
import pytest

@pytest.mark.integration
@pytest.mark.no_parallel
async def test_file_watcher_monitors_changes(tmp_path):
    """Test file watcher detects file changes (exclusive access needed)."""
    watcher = FileWatcher(tmp_path)
    await watcher.start()

    # Create file
    (tmp_path / "test.py").write_text("print('hello')")

    # Wait for event
    events = await watcher.get_events(timeout=1.0)
    assert len(events) == 1
```

### Example 6: Security Test
```python
import pytest

@pytest.mark.security
def test_sql_injection_prevention():
    """Test that SQL injection attempts are prevented."""
    malicious_input = "'; DROP TABLE memories; --"
    result = sanitize_input(malicious_input)
    assert "DROP TABLE" not in result
```

---

## 10. Appendix

### Detection Scripts

#### detect_slow_tests.py
```python
#!/usr/bin/env python3
"""Detect slow tests by measuring execution time."""

import subprocess
import json
import sys
from pathlib import Path

def run_tests_with_timing():
    """Run tests and collect timing data."""
    print("Running tests to detect slow ones...")
    result = subprocess.run(
        [
            "pytest",
            "tests/",
            "--durations=0",
            "--json-report",
            "--json-report-file=.test_times.json",
            "-v",
        ],
        capture_output=True,
        text=True,
    )
    return result.returncode

def analyze_timing():
    """Analyze test timing data."""
    with open(".test_times.json") as f:
        data = json.load(f)

    slow_tests = []
    for test in data.get("tests", []):
        duration = test.get("duration", 0)
        if duration > 1.0:  # >1 second
            slow_tests.append({
                "name": test["nodeid"],
                "duration": duration,
                "file": test["nodeid"].split("::")[0],
            })

    return sorted(slow_tests, key=lambda x: x["duration"], reverse=True)

def main():
    """Main entry point."""
    # Run tests
    returncode = run_tests_with_timing()

    if not Path(".test_times.json").exists():
        print("ERROR: Test timing data not generated")
        sys.exit(1)

    # Analyze
    slow_tests = analyze_timing()

    # Report
    print(f"\nSlow tests (>{1.0}s):")
    print(f"{'Test':<80} {'Duration':<10}")
    print("-" * 90)

    for test in slow_tests:
        print(f"{test['name']:<80} {test['duration']:>8.2f}s")

    print(f"\nTotal slow tests: {len(slow_tests)}")
    print(f"\nFiles to review:")
    files = sorted(set(t["file"] for t in slow_tests))
    for file in files:
        count = sum(1 for t in slow_tests if t["file"] == file)
        print(f"  {file}: {count} slow tests")

    # Generate marker suggestions
    print("\n\nSuggested markers to add:")
    for test in slow_tests:
        print(f"# {test['name']} ({test['duration']:.2f}s)")
        print(f"@pytest.mark.slow")
        print()

if __name__ == "__main__":
    main()
```

**Usage:**
```bash
python scripts/detect_slow_tests.py > planning_docs/TEST-011_slow_tests_report.txt
```

### Verification Checklist

```bash
# 1. Verify markers defined
pytest --markers | grep -E "unit|integration|slow|smoke"

# 2. Verify auto-marking works
pytest --collect-only tests/unit/ | grep "unit"
pytest --collect-only tests/integration/ | grep "integration"

# 3. Test marker filtering
pytest -m smoke --collect-only  # Should show ~50 tests
pytest -m "unit and not slow" --collect-only  # Should show ~2,140 tests

# 4. Test Makefile shortcuts
make test-smoke
make test-fast
make test-integration

# 5. Test CI workflow locally (if using act)
act -j smoke-tests

# 6. Verify documentation
ls -l tests/README.md
grep -A 10 "Test Markers" TESTING_GUIDE.md
```

---

**Next Steps:**
1. Review this plan with team
2. Get approval to proceed
3. Create git worktree: `git worktree add .worktrees/TEST-011 -b TEST-011`
4. Begin Phase 1 implementation (Hour 1: Setup)
5. Progress through phases systematically
6. Update this document with completion notes
