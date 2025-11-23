# Debugging Guide

Comprehensive debugging strategies and solutions for common issues in the Claude Memory RAG Server.

---

## Table of Contents

1. [Quick Diagnostics](#quick-diagnostics)
2. [Common Issues](#common-issues)
3. [Debugging Tools](#debugging-tools)
4. [Component-Specific Issues](#component-specific-issues)
5. [Performance Debugging](#performance-debugging)
6. [Test Debugging](#test-debugging)

---

## Quick Diagnostics

### Health Check

```bash
# Check overall system health
python -m src.cli health

# Check Qdrant connectivity
curl http://localhost:6333/

# Check Python environment
python --version  # Should be 3.8+
pip list | grep qdrant-client
pip list | grep sentence-transformers

# Run validation
python scripts/validate_installation.py
```

### Common Quick Fixes

```bash
# Restart Qdrant
docker-compose restart

# Clear Python cache
find . -type d -name __pycache__ -exec rm -rf {} +
find . -type f -name "*.pyc" -delete

# Reinstall dependencies
pip install -r requirements.txt --force-reinstall

# Rebuild Rust module (if using)
cd rust_core && maturin develop --release && cd ..
```

---

## Common Issues

### 1. Qdrant Connection Failures

**Symptom:**
```
QdrantConnectionError: Could not connect to Qdrant at http://localhost:6333
```

**Diagnosis:**
```bash
# Check if Qdrant is running
docker ps | grep qdrant

# Check Qdrant logs
docker logs $(docker ps -q --filter name=qdrant)

# Test connectivity
curl http://localhost:6333/
```

**Solutions:**

**A. Qdrant not running:**
```bash
docker-compose up -d
```

**B. Wrong port:**
```bash
# Check docker-compose.yml for port mapping
# Default should be 6333:6333

# Update .env if needed
QDRANT_URL=http://localhost:6333
```

**C. Docker issues:**
```bash
# Restart Docker
# macOS: Restart Docker Desktop
# Linux: sudo systemctl restart docker

# Rebuild Qdrant container
docker-compose down
docker-compose up -d
```

### 2. Import Errors / Module Not Found

**Symptom:**
```
ModuleNotFoundError: No module named 'src'
```

**Diagnosis:**
```bash
# Check current directory
pwd  # Should be project root

# Check PYTHONPATH
echo $PYTHONPATH
```

**Solutions:**

**A. Wrong directory:**
```bash
# Navigate to project root
cd /path/to/claude-memory-server
```

**B. Missing PYTHONPATH:**
```bash
# Add to current session
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

# Or run with python -m
python -m src.cli index /path/to/code
```

**C. Missing dependencies:**
```bash
pip install -r requirements.txt
```

### 3. No Code Units Extracted During Indexing

**Symptom:**
```
Indexed 50 files, but 0 semantic units extracted
```

**Diagnosis:**
```bash
# Check parser status
python -c "from src.memory.incremental_indexer import IncrementalCodeIndexer; print('Parser OK')"

# Check specific file
python -m src.cli index /path/to/single/file.py --project test -v
```

**Solutions:**

**A. Parser initialization failed:**
```python
# Check if optional tree-sitter languages are installed
pip install tree-sitter-python tree-sitter-javascript tree-sitter-typescript

# Or use Python fallback parser (slower but always works)
# Already automatically falls back if tree-sitter unavailable
```

**B. Unsupported file types:**
```bash
# Check supported languages
# Python, JS, TS, Java, Go, Rust, Ruby, Swift, Kotlin, PHP, C, C++, C#, SQL
# Plus: JSON, YAML, TOML (config files)

# Verify file extensions match
ls /path/to/code/*.py  # Should exist
```

**C. Syntax errors in source files:**
```bash
# Check file for syntax errors
python -m py_compile /path/to/file.py

# Parser will skip files with syntax errors
# Check indexing logs for "Skipped" messages
```

### 4. Search Returns No Results

**Symptom:**
```
search_code("authentication") returns []
```

**Diagnosis:**
```bash
# Check if project is indexed
python -m src.cli status

# Check collection exists in Qdrant
curl http://localhost:6333/collections
```

**Solutions:**

**A. Project not indexed:**
```bash
python -m src.cli index /path/to/code --project-name my-project
```

**B. Wrong project name:**
```python
# List all indexed projects
from src.store.qdrant_store import QdrantMemoryStore
store = QdrantMemoryStore()
projects = store.list_projects()
print(projects)  # Use exact name from this list
```

**C. Wrong category filter:**
```python
# Code is indexed with category=CODE
# Search must use category=CODE or no filter
results = await server.search_code(query="auth", category="CODE")
```

**D. Stale index:**
```bash
# Re-index to refresh
python -m src.cli index /path/to/code --project-name my-project --force
```

### 5. Tests Failing

**Symptom:**
```
FAILED tests/unit/test_indexing.py::test_index_extracts_functions
```

**Diagnosis:**
```bash
# Run single test with verbose output
pytest tests/unit/test_indexing.py::test_index_extracts_functions -v -s

# Show local variables on failure
pytest tests/unit/test_indexing.py::test_index_extracts_functions -v -l

# Drop into debugger
pytest tests/unit/test_indexing.py::test_index_extracts_functions -v --pdb
```

**Solutions:**

**See TESTING_GUIDE.md** for comprehensive test debugging strategies.

Quick fixes:
```bash
# Ensure Qdrant is running for integration tests
docker-compose up -d

# Clear test cache
pytest --cache-clear

# Update fixtures
# Check if fixtures in tests/conftest.py are up to date
```

### 6. Slow Indexing Performance

**Symptom:**
```
Indexing takes 10+ minutes for small projects
```

**Diagnosis:**
```bash
# Check if parallel embeddings enabled
python -c "from src.config import get_config; print(get_config().enable_parallel_embeddings)"

# Check embedding cache
ls -lh ~/.claude-rag/embedding_cache.pkl

# Check Qdrant performance
curl http://localhost:6333/collections/code_memories/points/count
```

**Solutions:**

**A. Enable parallel embeddings:**
```bash
# Set in .env
CLAUDE_RAG_ENABLE_PARALLEL_EMBEDDINGS=true

# Or export
export CLAUDE_RAG_ENABLE_PARALLEL_EMBEDDINGS=true
```

**B. Use Rust parser:**
```bash
cd rust_core
maturin develop --release
cd ..

# Verify Rust parser available
python -c "from src.memory.rust_parser import RustParser; print('Rust OK')"
```

**C. Optimize Qdrant:**
```bash
# Increase Qdrant memory limit in docker-compose.yml
# Default: 2GB, increase to 4GB or 8GB for large projects
```

**D. Use incremental indexing:**
```bash
# Only re-index changed files
python -m src.cli index /path/to/code --project-name my-project
# Automatically uses cache for unchanged files
```

---

## Debugging Tools

### 1. Python Debugger (pdb)

```python
# Add breakpoint in code
import pdb; pdb.set_trace()

# Or use Python 3.7+ built-in
breakpoint()
```

**Common pdb commands:**
```
l       # List source code around current line
n       # Next line
s       # Step into function
c       # Continue execution
p var   # Print variable
pp var  # Pretty-print variable
q       # Quit debugger
```

### 2. Logging

```python
# Enable debug logging
import logging
logging.basicConfig(level=logging.DEBUG)

# Or set in environment
export LOG_LEVEL=DEBUG
python -m src.cli index /path/to/code
```

### 3. pytest Debugging

```bash
# Show print statements
pytest tests/ -v -s

# Stop on first failure
pytest tests/ -v -x

# Show local variables on failure
pytest tests/ -v -l

# Drop into pdb on failure
pytest tests/ -v --pdb

# Run last failed tests only
pytest tests/ --lf -v
```

### 4. Memory Profiling

```bash
# Install memory-profiler
pip install memory-profiler

# Profile a function
python -m memory_profiler script.py

# Or use @profile decorator
@profile
def my_function():
    # ... code
```

### 5. Performance Profiling

```python
# Use cProfile
python -m cProfile -o output.prof script.py

# Analyze with snakeviz
pip install snakeviz
snakeviz output.prof
```

---

## Component-Specific Issues

### Code Indexing

**Issue**: Files skipped during indexing

**Debug:**
```bash
# Run with verbose logging
python -m src.cli index /path/to/code --project test -v

# Check skipped files log
# Parser skips files with:
# - Syntax errors
# - Binary files
# - Very large files (>1MB)
# - Unsupported extensions
```

**Solution:**
```bash
# Fix syntax errors in source files
python -m py_compile file.py

# For large files, increase limit in config
export CLAUDE_RAG_MAX_FILE_SIZE=2097152  # 2MB
```

### Semantic Search

**Issue**: Search results not relevant

**Debug:**
```python
# Check embedding quality
from src.embeddings.generator import EmbeddingGenerator
gen = EmbeddingGenerator()
embedding = gen.generate("test query")
print(f"Embedding dimensions: {len(embedding)}")  # Should be 384
print(f"Embedding norm: {sum(x**2 for x in embedding)**0.5}")  # Should be ~1.0
```

**Solution:**
```bash
# Try different search modes
python -m src.cli search "query" --project test --search-mode hybrid

# Adjust similarity threshold
# Lower threshold = more results (less strict)
# Higher threshold = fewer results (more strict)
```

### MCP Server

**Issue**: MCP tools not responding

**Debug:**
```bash
# Test MCP server manually
python -m src.mcp_server

# In another terminal, test with MCP inspector
npx @modelcontextprotocol/inspector python -m src.mcp_server
```

**Solution:**
```bash
# Check server logs for errors
# Ensure Qdrant is running
# Restart MCP server
```

---

## Performance Debugging

### Slow Searches

**Diagnosis:**
```python
import time
start = time.time()
results = await server.search_code("query")
print(f"Search took {time.time() - start:.2f}s")
```

**Solutions:**

**A. Too many results:**
```python
# Limit results
results = await server.search_code("query", limit=10)
```

**B. Collection too large:**
```bash
# Check collection size
curl http://localhost:6333/collections/code_memories

# Consider archiving old projects
python -m src.cli project archive old-project
```

**C. Qdrant performance:**
```bash
# Optimize Qdrant (in docker-compose.yml)
# Increase memory limit
# Enable quantization
# Use SSD storage
```

### High Memory Usage

**Diagnosis:**
```bash
# Monitor during indexing
top  # Watch Python process memory
htop  # Better visualization

# Or use memory-profiler
python -m memory_profiler -m src.cli index /path/to/code
```

**Solutions:**

**A. Reduce batch size:**
```python
# In .env or environment
CLAUDE_RAG_EMBEDDING_BATCH_SIZE=32  # Default is 100
```

**B. Disable parallel embeddings:**
```bash
export CLAUDE_RAG_ENABLE_PARALLEL_EMBEDDINGS=false
```

**C. Process in chunks:**
```bash
# Index subdirectories separately
python -m src.cli index /path/to/code/src --project my-project
python -m src.cli index /path/to/code/tests --project my-project
```

---

## Test Debugging

See `TESTING_GUIDE.md` for comprehensive test debugging.

**Quick reference:**

```bash
# Debug single test
pytest tests/unit/test_module.py::test_function -v -s --pdb

# Show why test was skipped
pytest tests/ -v -rs

# Show test durations (find slow tests)
pytest tests/ --durations=10

# Disable warnings
pytest tests/ --disable-warnings
```

---

## Getting Help

If you're still stuck after trying these solutions:

1. **Check existing issues**: Look in GitHub issues for similar problems
2. **Review planning docs**: Check `planning_docs/` for feature-specific notes
3. **Ask in discussions**: Post in GitHub discussions
4. **Create detailed bug report**:
   - Steps to reproduce
   - Expected vs actual behavior
   - Error messages (full stack trace)
   - Environment details (Python version, OS, etc.)

**Include in bug reports:**
```bash
# System info
python --version
pip list
docker --version
uname -a  # Linux/macOS
```

---

## Next Steps

After resolving your issue:

1. **Document the solution** - Add to this file if not already covered
2. **Create a test** - Prevent regression
3. **Update planning docs** - If feature-specific issue
4. **Share knowledge** - Help others avoid the same issue
