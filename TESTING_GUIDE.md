# Testing Guide

Comprehensive testing strategies and best practices for the Claude Memory RAG Server.

---

## Table of Contents

1. [Testing Philosophy](#testing-philosophy)
2. [Test Structure](#test-structure)
3. [Running Tests](#running-tests)
4. [Writing Tests](#writing-tests)
5. [Test Fixtures](#test-fixtures)
6. [Coverage Requirements](#coverage-requirements)
7. [Common Patterns](#common-patterns)
8. [Debugging Tests](#debugging-tests)

---

## Testing Philosophy

### Quality Standards

- **Minimum Coverage**: 80% for core modules (src/core, src/store, src/memory, src/embeddings)
- **Current Coverage**: 59.6% overall, 71.2% core modules
- **Test Count**: ~2,740 tests (varies by environment: 2,677-2,744 range)
- **Pass Rate**: 100% required before merging

### Test Pyramid

```
       /\
      /  \  E2E Tests (Integration)
     /----\
    /      \ Integration Tests
   /--------\
  /          \ Unit Tests (Majority)
 /------------\
```

**Focus:**
- 70% Unit tests (fast, isolated)
- 25% Integration tests (realistic scenarios)
- 5% E2E tests (complete workflows)

---

## Test Structure

### Directory Layout

```
tests/
├── unit/              # Unit tests (isolated components)
│   ├── test_config.py
│   ├── test_server.py
│   ├── test_indexing.py
│   └── ...
├── integration/       # Integration tests (multiple components)
│   ├── test_indexing_integration.py
│   ├── test_search_integration.py
│   └── ...
└── security/          # Security validation
    ├── test_sanitization.py
    └── test_injection.py
```

### Naming Conventions

**Test Files**: `test_<module_name>.py`
**Test Classes**: `Test<FeatureName>` (optional, for grouping)
**Test Functions**: `test_<what_it_tests>_<expected_behavior>`

**Examples:**
```python
def test_index_codebase_extracts_functions()
def test_search_code_returns_relevant_results()
def test_parallel_embeddings_handles_errors()
```

---

## Running Tests

### Basic Commands

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=src --cov-report=html

# Run specific test file
pytest tests/unit/test_config.py -v

# Run specific test function
pytest tests/unit/test_config.py::test_config_loads_defaults -v

# Run tests matching pattern
pytest tests/ -k "indexing" -v
```

### Parallel Execution (2.55x Faster!)

```bash
# Automatically detect CPU cores and run in parallel
pytest tests/ -n auto -v

# Specify number of workers
pytest tests/ -n 8 -v

# Parallel with coverage
pytest tests/ -n auto --cov=src --cov-report=html
```

**Performance:**
- Sequential: ~215 seconds
- Parallel (8 workers): ~84 seconds
- Speedup: 2.55x

### Debugging Tests

```bash
# Show print statements
pytest tests/ -v -s

# Stop on first failure
pytest tests/ -v -x

# Show local variables on failure
pytest tests/ -v -l

# Run last failed tests only
pytest tests/ --lf -v

# Drop into debugger on failure
pytest tests/ -v --pdb
```

### Coverage Analysis

```bash
# Generate HTML coverage report
pytest tests/ --cov=src --cov-report=html
open htmlcov/index.html  # View in browser

# Show missing lines
pytest tests/ --cov=src --cov-report=term-missing

# Coverage for specific module
pytest tests/unit/test_indexing.py --cov=src.memory.incremental_indexer
```

---

## Writing Tests

### Unit Test Template

```python
import pytest
from src.module import FeatureClass

@pytest.fixture
def feature():
    """Create a test instance of FeatureClass."""
    return FeatureClass(config_param="test")

def test_feature_does_something_correctly(feature):
    """Test that feature performs expected behavior."""
    # Arrange
    input_data = "test input"

    # Act
    result = feature.process(input_data)

    # Assert
    assert result == "expected output"
    assert feature.state == "valid"
```

### Integration Test Template

```python
import pytest
from src.core.server import MemoryRAGServer
from src.config import ServerConfig

@pytest.fixture
async def server():
    """Create a test server with Qdrant."""
    config = ServerConfig(
        storage_backend="qdrant",
        qdrant_url="http://localhost:6333"
    )
    server = MemoryRAGServer(config)
    await server.initialize()
    yield server
    # Cleanup after test
    await server.cleanup()

@pytest.mark.asyncio
async def test_index_and_search_workflow(server, small_test_project):
    """Test complete index → search workflow."""
    # Index codebase
    result = await server.index_codebase(
        directory=small_test_project,
        project_name="test-project"
    )
    assert result["indexed_count"] > 0

    # Search indexed code
    results = await server.search_code(
        query="function definition",
        project_name="test-project"
    )
    assert len(results) > 0
    assert results[0]["score"] > 0.5
```

---

## Test Fixtures

### Common Fixtures

**Project-Level Fixtures** (in `tests/conftest.py`):

```python
@pytest.fixture
def mock_embeddings():
    """Mock embedding generator for faster tests."""
    with patch('src.embeddings.generator.EmbeddingGenerator.generate') as mock:
        mock.return_value = [0.1] * 384  # Mock 384-dim embedding
        yield mock

@pytest.fixture
def small_test_project(tmp_path):
    """Create a small test project with known structure."""
    project_dir = tmp_path / "test_project"
    project_dir.mkdir()

    # Create test files
    (project_dir / "main.py").write_text("""
def hello_world():
    print("Hello, World!")
""")

    return str(project_dir)

@pytest.fixture
def qdrant_store():
    """Create a test Qdrant store."""
    from src.store.qdrant_store import QdrantMemoryStore
    store = QdrantMemoryStore(url="http://localhost:6333")
    yield store
    # Cleanup test collections
    store.cleanup_test_data()
```

### Using Fixtures

```python
def test_with_fixtures(mock_embeddings, small_test_project, qdrant_store):
    """Test using multiple fixtures."""
    # Fixtures are automatically injected by pytest
    assert mock_embeddings.called == False  # Not called yet

    # Use the fixtures
    result = index_project(small_test_project, store=qdrant_store)

    assert mock_embeddings.called == True  # Now called
```

---

## Coverage Requirements

### Coverage Configuration

See `.coveragerc` for exclusions:

```ini
[run]
omit =
    */tests/*
    */test_*.py
    src/cli/*           # CLI commands (interactive)
    src/dashboard/*     # Web dashboard (interactive)
    src/memory/health_scheduler.py  # Schedulers (long-running)
    # ... 14 total exclusions
```

**Why Excluded:**
- CLI/TUI tools are interactive (impractical to test)
- Schedulers run indefinitely (integration test only)
- Some modules are deprecated placeholders

### Coverage Targets

**Core Modules (80%+ required):**
- `src/core/` - Core server logic
- `src/store/` - Storage backends
- `src/memory/` - Indexing and memory management
- `src/embeddings/` - Embedding generation

**Other Modules (60%+ acceptable):**
- `src/analytics/` - Analytics and tracking
- `src/monitoring/` - Health monitoring
- `src/backup/` - Backup and restore

**Excluded Modules:**
- CLI commands, TUI dashboards, schedulers (see `.coveragerc`)

### Checking Coverage

```bash
# View overall coverage
pytest tests/ --cov=src --cov-report=term

# View core module coverage specifically
pytest tests/ --cov=src.core --cov=src.store --cov=src.memory --cov=src.embeddings --cov-report=term-missing
```

---

## Common Patterns

### Testing Async Functions

```python
import pytest

@pytest.mark.asyncio
async def test_async_function():
    """Test async function with @pytest.mark.asyncio."""
    result = await async_function()
    assert result == expected
```

### Mocking External Dependencies

```python
from unittest.mock import patch, MagicMock

@patch('src.module.ExternalDependency')
def test_with_mock(mock_dependency):
    """Test with mocked external dependency."""
    mock_dependency.return_value.method.return_value = "mocked"

    result = function_using_dependency()

    assert result == "expected"
    mock_dependency.return_value.method.assert_called_once()
```

### Parametrized Tests

```python
@pytest.mark.parametrize("input,expected", [
    ("hello", "HELLO"),
    ("world", "WORLD"),
    ("", ""),
])
def test_uppercase(input, expected):
    """Test uppercase function with multiple inputs."""
    assert uppercase(input) == expected
```

### Testing Exceptions

```python
def test_raises_error_on_invalid_input():
    """Test that function raises expected error."""
    with pytest.raises(ValueError, match="Invalid input"):
        function_with_validation(invalid_input)
```

### Temporary Files

```python
def test_with_temp_file(tmp_path):
    """Test with temporary file (pytest built-in fixture)."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("test content")

    result = process_file(test_file)

    assert result == expected
```

---

## Debugging Tests

### Common Issues

**1. Import Errors**

```bash
# Problem: ModuleNotFoundError
# Solution: Ensure PYTHONPATH includes src/
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
pytest tests/
```

**2. Qdrant Connection Failures**

```bash
# Problem: Connection refused to Qdrant
# Solution: Start Qdrant with Docker
docker-compose up -d
curl http://localhost:6333/  # Verify it's running
```

**3. Async Test Not Running**

```python
# Problem: async test doesn't run
# Missing: @pytest.mark.asyncio decorator

# Correct:
@pytest.mark.asyncio
async def test_async_function():
    result = await async_function()
    assert result == expected
```

**4. Flaky Tests**

```bash
# Problem: Tests pass sometimes, fail other times
# Debug: Run test multiple times
pytest tests/unit/test_flaky.py --count=10 -v

# Solution: Use proper test isolation (fixtures, cleanup)
```

### Debug Workflow

1. **Run single test** with verbose output:
   ```bash
   pytest tests/unit/test_module.py::test_function -v -s
   ```

2. **Show local variables** on failure:
   ```bash
   pytest tests/unit/test_module.py::test_function -v -l
   ```

3. **Drop into debugger**:
   ```bash
   pytest tests/unit/test_module.py::test_function -v --pdb
   ```

4. **Add print statements** (temporary debugging):
   ```python
   def test_something():
       result = function()
       print(f"DEBUG: result = {result}")  # Will show with -s flag
       assert result == expected
   ```

---

## Best Practices

### Do's

✅ **Isolate tests** - Each test should be independent
✅ **Use fixtures** - Share setup code via pytest fixtures
✅ **Test edge cases** - Empty inputs, None, large values
✅ **Test error paths** - Not just happy paths
✅ **Mock expensive operations** - Use mock_embeddings fixture
✅ **Clean up resources** - Use yield fixtures for cleanup
✅ **Use descriptive names** - `test_what_when_then` format
✅ **Keep tests fast** - Unit tests should run in milliseconds

### Don'ts

❌ **Don't test implementation details** - Test behavior, not internals
❌ **Don't share state between tests** - Use fixtures, not globals
❌ **Don't skip tests without reason** - Fix or document why skipped
❌ **Don't hardcode paths** - Use tmp_path fixture
❌ **Don't test external services** - Mock them or use test doubles
❌ **Don't write brittle tests** - Avoid exact string matching
❌ **Don't ignore test failures** - Fix them immediately

---

## Performance Optimization

### Speed Up Tests

1. **Use parallel execution**:
   ```bash
   pytest tests/ -n auto  # 2.55x faster
   ```

2. **Mock embeddings**:
   ```python
   @pytest.fixture
   def mock_embeddings():
       """Avoid actual embedding generation in tests."""
       with patch('src.embeddings.generator.generate') as mock:
           mock.return_value = [0.1] * 384
           yield mock
   ```

3. **Use small test data**:
   ```python
   # Instead of indexing 1000 files:
   small_project = create_project_with_3_files()
   ```

4. **Skip slow tests in development**:
   ```bash
   # Mark slow tests
   @pytest.mark.slow
   def test_large_scale_indexing():
       ...

   # Skip them during development
   pytest tests/ -v -m "not slow"
   ```

---

## Continuous Integration

### Pre-Commit Checks

```bash
# Run before committing
python scripts/verify-complete.py
```

This runs:
- All tests
- Coverage check
- Linting (if configured)
- Type checking (if configured)

### CI/CD Pipeline

Typical CI workflow:
1. Install dependencies
2. Start Qdrant (Docker)
3. Run tests with coverage: `pytest tests/ -n auto --cov=src`
4. Check coverage threshold (80% for core)
5. Upload coverage reports

---

## Next Steps

After reading this guide:

1. **Write your first test** - Follow the unit test template
2. **Run the test suite** - `pytest tests/ -v`
3. **Check coverage** - `pytest tests/ --cov=src --cov-report=html`
4. **Debug a failing test** - Use `-v -l --pdb`
5. **Review existing tests** - Learn from `tests/unit/` examples

**Questions?** See `DEBUGGING.md` for troubleshooting or ask in project discussions.
