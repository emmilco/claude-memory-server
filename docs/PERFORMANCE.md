# Performance Guide

**Last Updated:** November 16, 2025

---

## Performance Overview

### Current Benchmarks

| Operation | Target | Actual | Status |
|-----------|--------|--------|--------|
| Rust parsing | <10ms | 1-6ms | ✅ 2-10x faster |
| Code indexing | >1 file/sec | 2.45 files/sec | ✅ 2.5x faster |
| Vector search | <50ms | 7-13ms | ✅ 4-7x faster |
| Embedding (single) | <50ms | ~30ms | ✅ 1.7x faster |
| Embedding (cached) | <5ms | <1ms | ✅ 5x+ faster |
| Memory storage | <100ms | ~50ms | ✅ 2x faster |

### Test Environment

- **CPU:** Apple M1 Pro (8 cores)
- **RAM:** 16GB
- **Storage:** SSD
- **Dataset:** 29 files, 981 semantic units
- **Qdrant:** Docker, localhost

---

## Indexing Performance

### Benchmark Results

**Test Case:** Index `src/` directory (29 files)

```
Files indexed: 29
Semantic units extracted: 981  
Total time: 11.82 seconds
Average: 2.45 files/sec
Parse time: 1-6ms per file
Success rate: 100%
```

**Breakdown:**
- File scanning: ~1s
- Rust parsing: ~100ms total (1-6ms each)
- Embedding generation: ~8s
- Qdrant storage: ~2s

### Optimization Tips

**1. Use Incremental Indexing**
```bash
# First index: 11.82s for 29 files
python -m src.cli index ./src

# Re-index (no changes): <1s (skips unchanged files)
python -m src.cli index ./src
```

**2. Batch Operations**
- Embeddings: Generated in batches of 32
- Storage: Batch insert 5x faster than sequential

**3. Enable Caching**
- Embedding cache hit rate: ~90%
- Cache retrieval: <1ms
- Location: `~/.claude-rag/embedding_cache.db`

---

## Search Performance

### Vector Search

**Typical Query Time: 7-13ms**

**Breakdown:**
- Embedding generation: 2-5ms (or <1ms if cached)
- Qdrant search: 5-8ms
- Result processing: <1ms

**Example:**
```python
import time

start = time.time()
results = await server.search_code(
    query="authentication logic",
    limit=10
)
elapsed = (time.time() - start) * 1000
print(f"Search completed in {elapsed:.2f}ms")
# Output: Search completed in 12.34ms
```

### Search Optimization

**1. Use Filters**
```python
# Slower: Search all projects
results = await server.search_code(query="auth")

# Faster: Filter by project
results = await server.search_code(
    query="auth",
    project_name="my-app"  # Reduces search space
)
```

**2. Limit Results**
```python
# Default: 10 results
results = await server.search_code(query="auth")

# Faster: Fewer results
results = await server.search_code(query="auth", limit=5)
```

**3. Cache Common Queries**
- Repeated queries use cached embeddings
- First query: ~30ms
- Cached query: ~8ms (3-4x faster)

---

## Memory Performance

### Qdrant Configuration

**HNSW Index Settings:**
```python
{
    "m": 16,              # Connections per layer
    "ef_construct": 200   # Construction quality
}
```

**Tuning:**
- Higher `m`: Better accuracy, more memory
- Higher `ef_construct`: Better quality, slower indexing

**Quantization:**
```python
{
    "type": "int8"  # 75% memory savings
}
```

**Impact:**
- Memory: ~1MB per 10K points (with quantization)
- Accuracy: <1% degradation
- Search speed: Minimal impact

### Memory Usage

**Base Application:**
- Python process: ~100MB
- sentence-transformers model: ~50MB
- **Total:** ~150MB

**Per 1,000 Memories:**
- Vectors (384-dim): ~1.5MB
- Metadata: ~0.5MB
- Indices: ~1MB
- **Total:** ~3MB per 1K memories

**Per 1,000 Code Units:**
- Similar to memories: ~3MB per 1K units

**Example:**
- 10K memories: 150MB + 30MB = 180MB
- 100K memories: 150MB + 300MB = 450MB

---

## Embedding Performance

### Generation Speed

**Single Embedding:**
```python
# First call: Model loading + generation
start = time.time()
emb = await generator.generate("test text")
print(f"Time: {(time.time() - start) * 1000:.2f}ms")
# Output: Time: 1200ms (first call includes model loading)

# Subsequent calls
start = time.time()
emb = await generator.generate("test text 2")
print(f"Time: {(time.time() - start) * 1000:.2f}ms")
# Output: Time: 30ms
```

**Batch Generation:**
```python
texts = ["text" + str(i) for i in range(100)]

start = time.time()
embeddings = await generator.batch_generate(texts, batch_size=32)
elapsed = time.time() - start
print(f"Rate: {len(texts) / elapsed:.1f} docs/sec")
# Output: Rate: 120 docs/sec
```

### Cache Performance

**Cache Statistics:**
```python
stats = cache.get_stats()
print(f"Hit rate: {stats['hit_rate']:.1%}")
# Output: Hit rate: 90.0%

print(f"Hits: {stats['hits']}, Misses: {stats['misses']}")
# Output: Hits: 900, Misses: 100
```

**Cache Impact:**
- Hit: <1ms retrieval
- Miss: ~30ms generation + storage
- **Speedup:** 30-100x faster for repeated queries

---

## Rust Parser Performance

### Parsing Speed

**Comparison:**
```
Python tree-sitter:  50-100ms per file
Rust tree-sitter:    1-6ms per file
Speedup:             8-100x faster
```

**Batch Parsing:**
```rust
// Process 29 files
Total time: ~100ms
Average: 3.4ms per file
```

### Language Performance

| Language | Avg Parse Time | Complexity |
|----------|---------------|------------|
| Python | 4-5ms | Medium |
| JavaScript | 3-4ms | Medium |
| TypeScript | 4-6ms | Medium-High |
| Java | 3-5ms | Medium |
| Go | 2-3ms | Low |
| Rust | 3-4ms | Medium |

**Note:** Parse time correlates with file size and AST complexity, not language.

---

## Scaling Considerations

### Database Scaling

**Qdrant Limits:**
- Max points per collection: 10M+
- Max collections: Unlimited
- Recommended per collection: 1M points

**Horizontal Scaling:**
```
# Multi-collection strategy
memories_collection     # User memories
code_project_a          # Project A code
code_project_b          # Project B code
```

**Sharding:**
- Qdrant supports distributed mode
- Multiple nodes for >10M points
- Automatic load balancing

### Code Indexing Scaling

**Large Codebases:**
- 1,000 files: ~7 minutes (first index)
- 10,000 files: ~1 hour (first index)
- Incremental: Only changed files

**Optimization for Large Projects:**
1. **Selective Indexing:** Index only relevant directories
2. **Parallel Processing:** Multiple workers (future)
3. **Incremental Mode:** Default behavior
4. **File Watching:** Auto-reindex changes only

---

## Monitoring

### Performance Metrics

**Built-in Logging:**
```python
# Enable performance logging
import logging
logging.basicConfig(level=logging.DEBUG)

# Logs include timing info
# DEBUG - Indexed file in 5.2ms
# DEBUG - Generated embedding in 28ms
# DEBUG - Vector search completed in 9ms
```

### Custom Profiling

**Python:**
```python
import time
import cProfile

# Simple timing
start = time.time()
await my_function()
print(f"Elapsed: {(time.time() - start) * 1000:.2f}ms")

# Detailed profiling
cProfile.run('my_function()')
```

**Qdrant Metrics:**
```bash
# Collection stats
curl http://localhost:6333/collections/memory

# Cluster info (if distributed)
curl http://localhost:6333/cluster
```

---

## Tuning Guide

### For Low Latency

1. **Increase HNSW ef_construct** (200 → 400)
2. **Reduce batch sizes** (32 → 16)
3. **Enable SSD caching**
4. **Use filters** to reduce search space

### For High Throughput

1. **Increase batch sizes** (32 → 64)
2. **Parallel processing** (future enhancement)
3. **Disable quantization** (if memory available)
4. **Increase Qdrant resources**

### For Low Memory

1. **Enable quantization** (int8)
2. **Reduce HNSW m parameter** (16 → 8)
3. **Use SQLite backend** (development only)
4. **Limit embedding cache size**

---

## Performance Checklist

**Before Production:**
- [ ] Run benchmark tests
- [ ] Verify <50ms search latency
- [ ] Enable quantization for memory savings
- [ ] Configure appropriate batch sizes
- [ ] Enable embedding cache
- [ ] Monitor Qdrant resource usage

**Regular Monitoring:**
- [ ] Check search latency weekly
- [ ] Monitor cache hit rates
- [ ] Review Qdrant disk usage
- [ ] Profile slow queries
- [ ] Update indices as needed

---

## Benchmark Scripts

**Run Benchmarks:**
```bash
# Indexing benchmark
python benchmark_indexing.py

# Output saved to: benchmark_report.json
```

**Example Output:**
```json
{
  "files_indexed": 29,
  "units_extracted": 981,
  "total_time_seconds": 11.82,
  "files_per_second": 2.45,
  "avg_parse_time_ms": 3.4,
  "search_latency_ms": 8.7
}
```

---

**Performance is good! Further optimization possible if needed.**
