# Troubleshooting Guide

**Last Updated:** November 17, 2025
**Version:** 4.0 (Production-Ready)

---

## Common Issues

### Installation Issues

#### Qdrant Won't Start

**Symptoms:**
```
ERROR: Cannot connect to Qdrant at localhost:6333
```

**Solutions:**

1. **Check if Qdrant is running**
   ```bash
   docker-compose ps
   # Should show qdrant as "Up"
   ```

2. **Start Qdrant**
   ```bash
   docker-compose up -d
   ```

3. **Check for port conflicts**
   ```bash
   lsof -i :6333
   # If another process is using 6333, stop it or change port
   ```

4. **Remove old volumes and restart**
   ```bash
   docker-compose down -v
   docker-compose up -d
   ```

5. **Check Docker is running**
   ```bash
   docker ps
   # Should list running containers
   ```

---

#### Rust Module Won't Build

**Symptoms:**
```
ERROR: Command 'maturin develop' failed
```

**Solutions:**

1. **Use Python parser fallback** (recommended for quick start)
   ```bash
   # Skip Rust build entirely - Python parser works automatically
   # Performance: 10-20x slower but fully functional
   # Just run: python -m src.cli health
   # It will detect and use Python parser
   ```

2. **Ensure Rust is installed**
   ```bash
   rustc --version
   # Should show: rustc 1.91+
   ```

3. **Update Rust**
   ```bash
   rustup update
   ```

4. **Add Rust to PATH**
   ```bash
   source $HOME/.cargo/env
   ```

5. **Clean and rebuild**
   ```bash
   cd rust_core
   cargo clean
   maturin develop
   ```

6. **Install build dependencies (Linux)**
   ```bash
   sudo apt install build-essential
   ```

---

#### Import Errors

**Symptoms:**
```python
ImportError: No module named 'mcp_performance_core'
```

**Solutions:**

1. **Build Rust module**
   ```bash
   cd rust_core && maturin develop && cd ..
   ```

2. **Reinstall Python dependencies**
   ```bash
   pip install --force-reinstall -r requirements.txt
   ```

3. **Check virtual environment**
   ```bash
   which python  # Should point to venv
   source venv/bin/activate
   ```

4. **Verify Python version**
   ```bash
   python --version  # Should be 3.13+
   ```

---

### Runtime Issues

#### Slow Indexing

**Symptoms:**
- Indexing takes >10 minutes for small projects
- Parse times >100ms per file

**Solutions:**

1. **Check Rust module is being used**
   ```python
   import mcp_performance_core
   print("Rust module loaded")
   # If ImportError, rebuild Rust module
   ```

2. **Enable incremental indexing**
   ```bash
   # First index will be slow
   python -m src.cli index ./src
   
   # Subsequent indexes should be fast
   python -m src.cli index ./src
   ```

3. **Check Qdrant connection**
   ```bash
   curl http://localhost:6333/health
   ```

4. **Reduce batch size** (if memory limited)
   ```python
   # In config.py
   EMBEDDING_BATCH_SIZE = 16  # Default: 32
   ```

---

#### Slow Search

**Symptoms:**
- Search takes >100ms
- Queries time out

**Solutions:**

1. **Use filters to reduce search space**
   ```python
   # Add project_name or language filters
   results = await server.search_code(
       query="auth",
       project_name="my-app"  # Reduces search space
   )
   ```

2. **Reduce limit**
   ```python
   results = await server.search_code(
       query="auth",
       limit=5  # Default: 10
   )
   ```

3. **Check embedding cache**
   ```python
   # Cache should have high hit rate
   stats = cache.get_stats()
   print(f"Hit rate: {stats['hit_rate']}")  # Should be >80%
   ```

4. **Optimize Qdrant**
   ```bash
   # Restart Qdrant to clear memory
   docker-compose restart qdrant
   ```

---

#### Memory Errors

**Symptoms:**
```
MemoryError: Cannot allocate memory
```

**Solutions:**

1. **Enable quantization** (saves 75% memory)
   ```python
   # In qdrant_setup.py, ensure quantization enabled
   quantization_config={"scalar": {"type": "int8"}}
   ```

2. **Reduce batch size**
   ```python
   # In config.py
   EMBEDDING_BATCH_SIZE = 16  # Reduce from 32
   ```

3. **Limit concurrent operations**
   ```bash
   # Index fewer files at once
   python -m src.cli index ./src/core  # Not entire src/
   ```

4. **Clear embedding cache**
   ```bash
   rm ~/.claude-rag/embedding_cache.db
   ```

---

### Test Failures

#### Tests Fail to Start

**Symptoms:**
```
ERROR: Qdrant not available
```

**Solutions:**

1. **Start Qdrant before tests**
   ```bash
   docker-compose up -d
   pytest tests/
   ```

2. **Check test configuration**
   ```bash
   # Ensure test database is accessible
   ls ~/.claude-rag/
   ```

---

#### Security Tests Fail

**Symptoms:**
```
FAILED tests/security/test_injection_attacks.py
```

**Solutions:**

1. **This is actually good!** Security tests verify that attacks are blocked.
   - Tests SHOULD pass (meaning attacks were blocked)
   - Tests FAILING means attacks got through (bad)

2. **Check validation module**
   ```python
   from src.core.validation import detect_injection_patterns
   result = detect_injection_patterns("'; DROP TABLE--")
   assert result is not None  # Should detect pattern
   ```

---

### Search Quality Issues

#### No Results Found

**Symptoms:**
- Search returns empty results
- Known code not found

**Solutions:**

1. **Check status first**
   ```bash
   python -m src.cli status
   # Verify project is indexed with files
   ```

2. **Verify indexing completed**
   ```bash
   # Re-index with verbose output
   python -m src.cli index ./src
   ```

3. **Check collection exists**
   ```bash
   curl http://localhost:6333/collections/memory
   # Should show points_count > 0
   ```

4. **Try different search modes**
   ```python
   # Try semantic search
   results = await server.search_code(
       query="authentication",
       search_mode="semantic"
   )

   # Try keyword search
   results = await server.search_code(
       query="authenticate",
       search_mode="keyword"
   )

   # Try hybrid search
   results = await server.search_code(
       query="authenticate user",
       search_mode="hybrid"
   )
   ```

5. **Try broader query**
   ```python
   # Instead of: "JWT token validation function"
   # Try: "token validation"
   ```

6. **Remove filters temporarily**
   ```python
   # Remove project_name, language filters to test
   results = await server.search_code(query="auth")
   ```

---

#### Irrelevant Results

**Symptoms:**
- Search returns wrong results
- Low relevance scores

**Solutions:**

1. **Be more specific**
   ```python
   # Instead of: "function"
   # Use: "user authentication function"
   ```

2. **Use filters**
   ```python
   results = await server.search_code(
       query="parse function",
       language="python",  # Narrow by language
       file_pattern="*/parsers/*"  # Narrow by path
   )
   ```

3. **Check score threshold**
   ```python
   # Filter out low-confidence results
   results = [r for r in results if r['score'] > 0.7]
   ```

---

### Configuration Issues

#### Environment Variables Not Loaded

**Symptoms:**
```
Using default settings instead of .env values
```

**Solutions:**

1. **Create .env file in project root**
   ```bash
   touch .env
   # Add your variables
   ```

2. **Load .env explicitly**
   ```python
   from dotenv import load_dotenv
   load_dotenv()
   ```

3. **Export manually**
   ```bash
   export CLAUDE_RAG_QDRANT_URL=http://localhost:6333
   python -m src.mcp_server
   ```

---

## Error Messages

### ValidationError

**Message:**
```
ValidationError: Potential security threat detected: SQL injection pattern
```

**Meaning:** Input contains suspicious patterns (SQL, prompt, or command injection)

**Solution:**
- This is working correctly - the input is being blocked for security
- Review input content
- If legitimate, rephrase to avoid trigger patterns

---

### ReadOnlyError

**Message:**
```
ReadOnlyError: Server is in read-only mode
```

**Meaning:** Attempting to write while in read-only mode

**Solution:**
```bash
# Disable read-only mode
export CLAUDE_RAG_READ_ONLY_MODE=false
# or remove --read-only flag
```

---

### StorageError

**Message:**
```
StorageError: Failed to connect to Qdrant
```

**Meaning:** Cannot reach Qdrant database

**Solutions:**
1. Start Qdrant: `docker-compose up -d`
2. Check URL: `curl http://localhost:6333/health`
3. Check firewall settings

---

## Debugging Tips

### Run Health Check

```bash
python -m src.cli health
# Shows comprehensive system status
```

### Check Status

```bash
python -m src.cli status
# Shows indexed projects, storage, file watcher, cache
```

### Enable Debug Logging

```python
import logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
```

Or via environment:
```bash
export CLAUDE_RAG_LOG_LEVEL=DEBUG
```

### Check Qdrant Status

```bash
# Health check
curl http://localhost:6333/health

# Collections list
curl http://localhost:6333/collections

# Collection details
curl http://localhost:6333/collections/memory

# Point count
curl http://localhost:6333/collections/memory | jq '.result.points_count'
```

### Verify Parser

```python
# Test Rust import
try:
    import mcp_performance_core
    print("✓ Rust module available (fast parsing)")
    print(f"Functions: {dir(mcp_performance_core)}")
except ImportError as e:
    print(f"⚠ Using Python parser fallback (slower but works)")
    print(f"Error: {e}")
```

### Test Embedding Generation

```python
from src.embeddings.generator import EmbeddingGenerator

gen = EmbeddingGenerator()
emb = await gen.generate("test text")
print(f"Embedding dimensions: {len(emb)}")  # Should be 384
```

### Test Search Modes

```python
# Test all search modes
for mode in ["semantic", "keyword", "hybrid"]:
    results = await server.search_code(
        query="authenticate",
        search_mode=mode
    )
    print(f"{mode}: {len(results['results'])} results")
```

---

## Getting Help

### Before Asking for Help

1. **Check logs:**
   - Application logs (stdout)
   - Security logs (`~/.claude-rag/security.log`)
   - Qdrant logs (`docker-compose logs qdrant`)

2. **Run diagnostics:**
   ```bash
   # Check versions
   python --version
   rustc --version
   docker --version
   
   # Check services
   docker-compose ps
   curl http://localhost:6333/health
   
   # Run tests
   pytest tests/ -v
   ```

3. **Gather information:**
   - OS and version
   - Python version
   - Error message (full traceback)
   - Steps to reproduce

### Where to Get Help

1. **Documentation:** Check other docs in `docs/`
2. **Issues:** GitHub Issues (if public repo)
3. **Tests:** Look at test files for usage examples
4. **Code:** Read source code comments

---

## Frequently Asked Questions

**Q: Why is the first query slow?**
A: Model loading takes ~1s. Subsequent queries use cached model and are fast.

**Q: Can I use SQLite instead of Qdrant?**
A: Yes, set `CLAUDE_RAG_STORAGE_BACKEND=sqlite`. Note: Slower for large datasets.

**Q: How do I reset everything?**
A: 
```bash
docker-compose down -v
rm -rf ~/.claude-rag/
rm -rf qdrant_storage/
```

**Q: Why are some files not indexed?**
A: Only supported languages are indexed (.py, .js, .ts, .java, .go, .rs). Check file extensions.

**Q: Can I index private repositories?**
A: Yes, everything is local. No data leaves your machine.

---

**Still having issues? Check the documentation or create an issue.**
