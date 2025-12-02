# E2E Test CI Integration Guide

This document provides instructions for integrating the automated E2E tests into CI/CD pipelines.

## Overview

The E2E test suite consists of **18 automated tests** covering:
- **10 critical workflow tests** (test_critical_paths.py)
- **8 first-run experience tests** (test_first_run.py)

These tests simulate real user workflows from installation through daily development tasks.

## Running E2E Tests

### Local Development

```bash
# Run all E2E tests
pytest tests/e2e/ -v

# Run specific test file
pytest tests/e2e/test_critical_paths.py -v

# Run with specific marker
pytest -m e2e -v

# Run with SQLite backend (faster, no Qdrant needed)
CLAUDE_RAG_STORAGE_BACKEND=sqlite pytest tests/e2e/ -v
```

### Test Selection

```bash
# Run only first-time user tests
pytest tests/e2e/test_critical_paths.py::test_first_time_setup -v
pytest tests/e2e/test_critical_paths.py::test_first_memory_storage -v
pytest tests/e2e/test_critical_paths.py::test_first_code_search -v

# Run only installation verification tests
pytest tests/e2e/test_first_run.py -v

# Run daily workflow tests
pytest tests/e2e/test_critical_paths.py::test_developer_daily_workflow -v
pytest tests/e2e/test_critical_paths.py::test_code_exploration_workflow -v
```

## CI/CD Integration

### GitHub Actions

Create `.github/workflows/e2e.yml`:

```yaml
name: E2E Tests

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  e2e-tests:
    runs-on: ubuntu-latest

    services:
      qdrant:
        image: qdrant/qdrant:v1.15.5
        ports:
          - 6333:6333
        options: >-
          --health-cmd "curl -f http://localhost:6333/ || exit 1"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.13'

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt

      - name: Wait for Qdrant
        run: |
          timeout 30 bash -c 'until curl -f http://localhost:6333/; do sleep 1; done'

      - name: Run E2E tests
        env:
          CLAUDE_RAG_QDRANT_URL: http://localhost:6333
        run: |
          pytest tests/e2e/ -v --tb=short --maxfail=3
        timeout-minutes: 30

      - name: Upload test results
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: e2e-test-results
          path: |
            pytest-report.xml
            htmlcov/
```

### Alternative: SQLite-Only E2E Tests

For faster CI runs that don't require Qdrant:

```yaml
name: E2E Tests (SQLite)

on:
  pull_request:
    branches: [main]

jobs:
  e2e-sqlite:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.13'

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt

      - name: Run E2E tests with SQLite
        env:
          CLAUDE_RAG_STORAGE_BACKEND: sqlite
        run: |
          pytest tests/e2e/ -v --tb=short
        timeout-minutes: 20
```

### GitLab CI

Add to `.gitlab-ci.yml`:

```yaml
e2e-tests:
  stage: test
  image: python:3.13
  services:
    - name: qdrant/qdrant:v1.15.5
      alias: qdrant
  variables:
    CLAUDE_RAG_QDRANT_URL: http://qdrant:6333
  before_script:
    - pip install -r requirements.txt
    - apt-get update && apt-get install -y curl
    - timeout 30 bash -c 'until curl -f http://qdrant:6333/; do sleep 1; done'
  script:
    - pytest tests/e2e/ -v --tb=short --maxfail=3
  timeout: 30m
  artifacts:
    when: always
    reports:
      junit: pytest-report.xml
```

## Test Requirements

### System Requirements

- **Python:** 3.13+
- **Storage Backend:** Qdrant (Docker) OR SQLite
- **Memory:** Minimum 2GB RAM (for embedding model)
- **Disk:** Minimum 500MB (for model cache)

### Dependencies

All dependencies are in `requirements.txt`:
- pytest >= 8.4.2
- pytest-asyncio >= 1.2.0
- sentence-transformers
- qdrant-client (for Qdrant backend)

### Environment Variables

Optional configuration:

```bash
# Storage backend (default: qdrant)
CLAUDE_RAG_STORAGE_BACKEND=sqlite  # or qdrant

# Qdrant connection
CLAUDE_RAG_QDRANT_URL=http://localhost:6333
CLAUDE_RAG_QDRANT_COLLECTION_NAME=test_collection

# SQLite path
CLAUDE_RAG_SQLITE_PATH=/tmp/test.db

# Performance tuning
CLAUDE_RAG_EMBEDDING_CACHE_SIZE=500
CLAUDE_RAG_SEARCH_DEFAULT_LIMIT=10
```

## Test Coverage

### First-Time User Tests (3 tests)

| Test | Coverage | Duration |
|------|----------|----------|
| test_first_time_setup | Complete setup flow | ~15s |
| test_first_memory_storage | Memory storage/retrieval | ~5s |
| test_first_code_search | Code indexing and search | ~10s |

### Daily Workflow Tests (4 tests)

| Test | Coverage | Duration |
|------|----------|----------|
| test_developer_daily_workflow | Search → Store → Retrieve | ~12s |
| test_code_exploration_workflow | Index → Search → Navigate | ~15s |
| test_memory_organization_workflow | Tag → Filter → Export | ~8s |
| test_project_switch_workflow | Multi-project isolation | ~18s |

### Data Management Tests (3 tests)

| Test | Coverage | Duration |
|------|----------|----------|
| test_project_backup_restore | Backup and restore flow | ~12s |
| test_memory_bulk_operations | Bulk create/delete | ~10s |
| test_cross_project_data_isolation | Project isolation | ~15s |

### Installation Tests (5 tests)

| Test | Coverage | Duration |
|------|----------|----------|
| test_dependencies_available | Dependency verification | <1s |
| test_qdrant_connectable | Qdrant connectivity | <1s |
| test_embedding_model_loadable | Model loading | ~5s |
| test_default_config_valid | Default configuration | ~8s |
| test_custom_config_applied | Custom configuration | ~8s |

### Additional Tests (3 tests)

| Test | Coverage | Duration |
|------|----------|----------|
| test_first_index_performance | Indexing performance | ~15s |
| test_error_messages_helpful | Error handling UX | ~5s |
| test_readme_quick_start_works | Documentation accuracy | ~12s |

**Total:** 18 tests, ~3-5 minutes total runtime

## Troubleshooting

### Common Issues

#### 1. Docker/Qdrant Not Available

**Error:** `Docker not available` or `Cannot connect to Qdrant`

**Solutions:**
- Use SQLite backend: `CLAUDE_RAG_STORAGE_BACKEND=sqlite pytest tests/e2e/`
- Check Docker is running: `docker ps`
- Check Qdrant health: `curl http://localhost:6333/`
- Start Qdrant: `docker-compose up -d`

#### 2. Embedding Model Download

**Error:** Model download fails or times out

**Solutions:**
- Pre-download model in CI setup:
  ```bash
  python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-mpnet-base-v2')"
  ```
- Cache model directory:
  ```yaml
  - uses: actions/cache@v4
    with:
      path: ~/.cache/torch/sentence_transformers
      key: sentence-transformers-${{ hashFiles('requirements.txt') }}
  ```

#### 3. Tests Timeout

**Error:** Tests exceed time limits

**Solutions:**
- Increase timeout: `pytest tests/e2e/ --timeout=300`
- Run fewer tests in parallel
- Use SQLite backend (faster than Qdrant for small datasets)
- Skip slow tests: `pytest tests/e2e/ -m "e2e and not slow"`

#### 4. Memory Issues

**Error:** OOM or model loading fails

**Solutions:**
- Increase runner memory
- Run tests sequentially: `pytest tests/e2e/ -n 0`
- Use smaller batch size: `CLAUDE_RAG_EMBEDDING_BATCH_SIZE=8`

## Performance Optimization

### Parallel Execution

```bash
# Run E2E tests in parallel (2-4 workers recommended)
pytest tests/e2e/ -n 4 -v
```

### Caching

```bash
# Cache embedding model
export HF_HOME=/path/to/cache
export TRANSFORMERS_CACHE=/path/to/cache/transformers
```

### Test Selection Strategies

```bash
# Smoke tests only (fastest, ~1 minute)
pytest tests/e2e/test_first_run.py::test_dependencies_available \
       tests/e2e/test_first_run.py::test_qdrant_connectable \
       tests/e2e/test_critical_paths.py::test_first_time_setup -v

# Critical path only (~2 minutes)
pytest tests/e2e/test_critical_paths.py::test_first_time_setup \
       tests/e2e/test_critical_paths.py::test_developer_daily_workflow \
       tests/e2e/test_critical_paths.py::test_first_memory_storage -v

# Full suite (~3-5 minutes)
pytest tests/e2e/ -v
```

## Integration with Existing CI

### Add to Existing pytest Workflow

If you already have a pytest workflow, add E2E tests as a separate job:

```yaml
jobs:
  unit-tests:
    # ... existing unit tests ...

  integration-tests:
    # ... existing integration tests ...

  e2e-tests:
    needs: [unit-tests]  # Run after unit tests pass
    runs-on: ubuntu-latest
    services:
      qdrant:
        image: qdrant/qdrant:v1.15.5
        # ... (see full config above)
    steps:
      # ... (see full config above)
```

### Matrix Testing

Test across multiple configurations:

```yaml
strategy:
  matrix:
    backend: [sqlite, qdrant]
    python-version: ['3.11', '3.12', '3.13']
  fail-fast: false

steps:
  - name: Run E2E tests
    env:
      CLAUDE_RAG_STORAGE_BACKEND: ${{ matrix.backend }}
    run: |
      pytest tests/e2e/ -v
```

## Reporting

### JUnit XML Report

```bash
pytest tests/e2e/ --junitxml=e2e-report.xml
```

### Coverage Report

```bash
pytest tests/e2e/ --cov=src --cov-report=html --cov-report=term
```

### HTML Report

```bash
pytest tests/e2e/ --html=e2e-report.html --self-contained-html
```

## Maintenance

### Adding New E2E Tests

1. Add test to appropriate file:
   - User workflows → `test_critical_paths.py`
   - Installation/setup → `test_first_run.py`
   - New categories → Create new file in `tests/e2e/`

2. Follow naming convention:
   ```python
   @pytest.mark.e2e
   @pytest.mark.asyncio
   async def test_descriptive_name(fresh_server, ...):
       """Test: Brief description of user workflow.

       Step-by-step explanation of what this test simulates.
       """
   ```

3. Update this document with new test details

### Updating Test Data

Sample code project is defined in `tests/e2e/conftest.py`:
- Modify `sample_code_project` fixture to change test data
- Keep realistic but minimal (5 files, ~200 LOC total)
- Include diverse code patterns (classes, functions, imports)

## Contact

For questions or issues with E2E tests:
- Check existing tests in `tests/e2e/` for examples
- See `tests/e2e/conftest.py` for fixture definitions
- Refer to main testing guide: `TESTING_GUIDE.md`
