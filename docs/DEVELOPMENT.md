# Developer Guide

**Last Updated:** November 17, 2025

---

## Development Setup

### 1. Clone and Install

```bash
git clone https://github.com/yourorg/claude-memory-server.git
cd claude-memory-server
pip install -r requirements.txt
cd rust_core && maturin develop && cd ..
docker-compose up -d
```

### 2. Development Tools

```bash
# Install development dependencies
pip install pytest pytest-cov pytest-asyncio black mypy pylint

# Git hooks are installed in .git/hooks/
# - pre-commit: Enforces CHANGELOG.md updates before commits
#   - Validates CHANGELOG.md is in staged files
#   - Prompts review of CLAUDE.md, TODO.md
#   - Use --no-verify to bypass (sparingly)
```

### 3. Run Tests

```bash
# All tests
pytest tests/ -v

# With coverage
pytest tests/ --cov=src --cov-report=html

# Specific suite
pytest tests/unit/ -v
pytest tests/integration/ -v
pytest tests/security/ -v
```

---

## Project Structure

```
claude-memory-server/
├── src/                      # Main source code
│   ├── core/                # Core server logic
│   │   ├── server.py       # Main MCP server
│   │   ├── models.py       # Pydantic models
│   │   ├── validation.py   # Input validation
│   │   └── exceptions.py   # Custom exceptions
│   ├── memory/              # Code indexing & tracking
│   │   ├── incremental_indexer.py    # Code indexing
│   │   ├── file_watcher.py           # File watching
│   │   ├── classifier.py             # Context classification
│   │   ├── import_extractor.py       # Import extraction (NEW)
│   │   ├── dependency_graph.py       # Dependency analysis (NEW)
│   │   ├── git_indexer.py            # Git history indexing (NEW)
│   │   ├── usage_tracker.py          # Memory usage tracking (NEW)
│   │   ├── pruner.py                 # Auto-expiration (NEW)
│   │   ├── conversation_tracker.py   # Session management (NEW)
│   │   ├── query_expander.py         # Query expansion (NEW)
│   │   └── python_parser.py          # Python fallback parser (NEW)
│   ├── store/               # Storage backends
│   │   ├── qdrant_store.py
│   │   └── sqlite_store.py
│   ├── embeddings/          # Embedding generation
│   │   ├── generator.py
│   │   └── cache.py
│   ├── search/              # Search algorithms (NEW)
│   │   ├── bm25.py         # BM25 keyword search
│   │   └── hybrid_search.py # Hybrid fusion strategies
│   └── cli/                 # CLI commands
│       ├── index_command.py
│       ├── watch_command.py
│       ├── status_command.py         # (NEW)
│       ├── health_command.py         # (NEW)
│       └── git_index_command.py      # (NEW)
├── rust_core/               # Rust parsing module
│   ├── src/
│   │   ├── lib.rs
│   │   └── parsing.rs
│   └── Cargo.toml
├── tests/                   # Test suite
│   ├── unit/
│   ├── integration/
│   └── security/
└── docs/                    # Documentation
```

---

## Development Workflow

### Making Changes

1. **Create a Branch**
   ```bash
   git checkout -b feature/my-feature
   ```

2. **Make Changes**
   - Follow existing code style
   - Add type hints
   - Write docstrings

3. **Write Tests**
   ```python
   # tests/unit/test_my_feature.py
   def test_my_feature():
       assert my_function() == expected_result
   ```

4. **Run Tests**
   ```bash
   pytest tests/unit/test_my_feature.py -v
   pytest tests/ -v  # All tests
   ```

5. **Check Coverage**
   ```bash
   pytest tests/ --cov=src --cov-report=term
   # Target: >85% coverage
   ```

6. **Format Code**
   ```bash
   black src/ tests/
   ```

7. **Type Check**
   ```bash
   mypy src/
   ```

8. **Update Documentation**
   ```bash
   # REQUIRED: Update CHANGELOG.md with your changes
   # - Add entry under "Unreleased" section
   # - Describe what changed and why
   # - Include file paths and function names

   # Optional but recommended:
   # - Update TODO.md if completing a task
   # - Update CLAUDE.md if discovering important patterns
   # - Update relevant docs/ files
   ```

9. **Commit** (Pre-commit Hook Enforced)
   ```bash
   git add .
   git commit -m "feat: add my feature"

   # Pre-commit hook automatically:
   # - Checks CHANGELOG.md is in staged files
   # - Prompts review of CLAUDE.md, TODO.md
   # - Blocks commit if CHANGELOG not updated

   # To bypass (use sparingly):
   git commit -m "feat: add my feature" --no-verify

   # Commit message format (recommended):
   # - feat: new feature
   # - fix: bug fix
   # - docs: documentation update
   # - test: add tests
   # - refactor: code refactoring
   ```

---

## Code Style

### Python

- **Formatter:** Black (default settings)
- **Style Guide:** PEP 8
- **Type Hints:** Required for public functions
- **Docstrings:** Google style
- **Line Length:** 88 characters (Black default)

**Example:**
```python
async def my_function(param: str, option: int = 5) -> dict[str, Any]:
    """Short description.
    
    Longer description if needed.
    
    Args:
        param: Description of param
        option: Description of option
        
    Returns:
        Dictionary with results
        
    Raises:
        ValidationError: If param is invalid
    """
    pass
```

### Rust

- **Formatter:** rustfmt
- **Style:** Default Rust conventions
- **Documentation:** rustdoc comments

```rust
/// Parse a source file into semantic units.
///
/// # Arguments
/// * `path` - File path
/// * `source` - Source code content
///
/// # Returns
/// Vector of semantic units
pub fn parse_source_file(path: &str, source: &str) -> PyResult<Vec<SemanticUnit>> {
    // Implementation
}
```

---

## Testing

### Unit Tests

Located in `tests/unit/`. Test individual functions/classes.

```python
# tests/unit/test_validation.py
def test_sanitize_text():
    result = sanitize_text("test\x00string")
    assert "\x00" not in result
    assert result == "teststring"
```

### Integration Tests

Located in `tests/integration/`. Test complete workflows.

```python
# tests/integration/test_indexing.py
async def test_index_and_search_workflow():
    indexer = IncrementalIndexer()
    await indexer.index_file("test.py")
    
    results = await server.search_code("test function")
    assert len(results) > 0
```

### Security Tests

Located in `tests/security/`. Test injection prevention.

```python
# tests/security/test_injection_attacks.py
def test_blocks_sql_injection():
    with pytest.raises(ValidationError):
        validate_store_request({
            "content": "'; DROP TABLE users--"
        })
```

### Running Specific Tests

```bash
# Single test file
pytest tests/unit/test_validation.py

# Single test function
pytest tests/unit/test_validation.py::test_sanitize_text

# Tests matching pattern
pytest -k "validation"

# With verbose output
pytest tests/ -v

# Stop on first failure
pytest tests/ -x
```

---

## Adding New Features

### 1. New MCP Tool

**Step 1:** Add method to `src/core/server.py`
```python
async def my_new_tool(self, param: str) -> dict:
    """Tool description."""
    # Implementation
    return {"result": "success"}
```

**Step 2:** Register in `src/mcp_server.py`
```python
@server.tool()
async def my_new_tool(param: str) -> dict:
    return await memory_server.my_new_tool(param)
```

**Step 3:** Add tests
```python
# tests/unit/test_server.py
async def test_my_new_tool():
    result = await server.my_new_tool("test")
    assert result["result"] == "success"
```

### 2. New Storage Backend

**Step 1:** Implement `src/store/base.py` interface
```python
class MyStore(MemoryStore):
    async def store(self, memory_unit, embedding):
        # Implementation
        pass
    # ... implement all abstract methods
```

**Step 2:** Add to factory (`src/store/__init__.py`)
```python
def create_memory_store(backend: str):
    if backend == "mystore":
        return MyStore()
```

**Step 3:** Add tests
```python
# tests/unit/test_mystore.py
```

### 3. New Language Support (Rust)

**Step 1:** Add tree-sitter parser (`rust_core/Cargo.toml`)
```toml
[dependencies]
tree-sitter-mylang = "0.1"
```

**Step 2:** Add parser logic (`rust_core/src/parsing.rs`)
```rust
fn parse_mylang(source: &str) -> Vec<SemanticUnit> {
    // Implementation
}
```

**Step 3:** Update language detection
```rust
match language {
    "mylang" => parse_mylang(source),
    // ...
}
```

**Step 4:** Add to import extractor (`src/memory/import_extractor.py`)
```python
def extract_mylang_imports(source: str) -> List[str]:
    # Extract imports specific to this language
    pass
```

### 4. New Search Mode or Fusion Strategy

**Step 1:** Add to `src/search/hybrid_search.py`
```python
def my_fusion_strategy(
    bm25_results: List[dict],
    vector_results: List[dict],
    alpha: float = 0.5
) -> List[dict]:
    # Implement fusion logic
    pass
```

**Step 2:** Register in config
```python
# src/config.py
HYBRID_FUSION_METHOD = "my_fusion"  # weighted|rrf|cascade|my_fusion
```

**Step 3:** Add tests
```python
# tests/unit/test_hybrid_search.py
def test_my_fusion_strategy():
    results = my_fusion_strategy(bm25_results, vector_results)
    assert len(results) > 0
```

---

## Debugging

### Enable Debug Logging

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

Or via environment:
```bash
export CLAUDE_RAG_LOG_LEVEL=DEBUG
```

### Debug MCP Calls

Add logging to tools:
```python
import logging
logger = logging.getLogger(__name__)

async def my_tool(self, param: str):
    logger.debug(f"my_tool called with: {param}")
    # ...
```

### Debug Qdrant

```bash
# Check collections
curl http://localhost:6333/collections

# Check collection details
curl http://localhost:6333/collections/memory

# View points
curl http://localhost:6333/collections/memory/points
```

### Debug Rust

```rust
// Add debug prints
eprintln!("Debug: value = {:?}", value);

// Or use dbg! macro
dbg!(my_variable);
```

---

## Performance Profiling

### Python Profiling

```python
import cProfile
import pstats

cProfile.run('my_function()', 'profile.stats')
stats = pstats.Stats('profile.stats')
stats.sort_stats('cumtime')
stats.print_stats(20)
```

### Memory Profiling

```python
from memory_profiler import profile

@profile
def my_function():
    # ...
```

### Benchmarking

```bash
python benchmark_indexing.py
```

---

## Release Process

1. **Update Version**
   - Update version in `__init__.py`
   - Update CHANGELOG.md

2. **Run Full Test Suite**
   ```bash
   pytest tests/ -v
   pytest tests/ --cov=src
   # Ensure coverage >85%
   ```

3. **Build Rust Module**
   ```bash
   cd rust_core
   maturin build --release
   ```

4. **Tag Release**
   ```bash
   git tag v1.0.0
   git push origin v1.0.0
   ```

5. **Build Distribution**
   ```bash
   python setup.py sdist bdist_wheel
   ```

---

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make changes with tests
4. Ensure all tests pass
5. Submit a pull request

**PR Requirements:**
- All tests passing
- Coverage >85%
- Documentation updated
- Follows code style
- Includes tests for new features

---

## Resources

- **MCP Protocol:** https://modelcontextprotocol.io/
- **Qdrant Docs:** https://qdrant.tech/documentation/
- **PyO3 Guide:** https://pyo3.rs/
- **tree-sitter:** https://tree-sitter.github.io/

