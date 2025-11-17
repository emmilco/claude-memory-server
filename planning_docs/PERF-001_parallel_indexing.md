# PERF-001: Parallel Indexing

## TODO Reference
- TODO.md: "Parallel indexing - Multi-process embedding generation - Target: 10-20 files/sec - Impact: 5-10x faster indexing"

## Objective
Implement multi-process embedding generation to dramatically increase indexing throughput from ~2.45 files/sec to 10-20 files/sec (4-8x improvement).

## Current State
- File indexing uses asyncio with semaphore (max_concurrent=4)
- Embedding generation is single-threaded using ThreadPoolExecutor(max_workers=2)
- Current performance: ~2.45 files/sec
- Bottleneck: embedding generation runs in a single thread pool

## Architecture Decision
Use **ProcessPoolExecutor** for embedding generation instead of ThreadPoolExecutor:
- Python GIL blocks true parallelism in threads
- sentence-transformers model.encode() is CPU-intensive
- Multiple processes = true parallel embedding generation
- Each process loads its own model instance

## Implementation Plan

### Phase 1: Parallel Embedding Generator
- [x] Create `src/embeddings/parallel_generator.py`
- [x] Implement `ParallelEmbeddingGenerator` class
- [x] Use ProcessPoolExecutor with worker processes
- [x] Implement worker function that loads model once per process
- [x] Batch distribution across workers for load balancing
- [x] Configuration: `embedding_parallel_workers` (default: CPU count)

### Phase 2: Integration
- [x] Add config options to `src/config.py`
- [x] Use ParallelEmbeddingGenerator in IncrementalIndexer
- [x] Maintain backward compatibility with single-threaded mode

### Phase 3: Testing
- [x] Unit tests for ParallelEmbeddingGenerator
- [x] Benchmark tests comparing performance
- [x] Integration tests with indexing workflow

### Phase 4: Documentation
- [x] Update CHANGELOG.md
- [x] Update TODO.md
- [x] Add planning doc completion summary

## Configuration

```python
# Config options to add
embedding_parallel_workers: int = os.cpu_count() or 4  # Number of worker processes
enable_parallel_embeddings: bool = True  # Enable/disable parallel processing
```

## Test Cases
1. Generate embeddings for 100 texts using parallel processing
2. Compare performance: single-threaded vs multi-process
3. Verify embeddings are identical to single-threaded version
4. Test with various batch sizes and worker counts
5. Test graceful fallback if multiprocessing fails

## Performance Target
- Current: ~2.45 files/sec
- Target: 10-20 files/sec
- Required improvement: 4-8x
- Strategy: Parallelize embedding generation across CPU cores

## Implementation Notes
- ProcessPoolExecutor can't pickle the SentenceTransformer model
- Solution: Load model in each worker process (lazy loading)
- Worker function is a module-level function for picklability
- Each worker maintains its own model instance
- Batch distribution ensures efficient load balancing

## Risks & Mitigations
- **Risk**: Memory usage increases (N models loaded)
  - **Mitigation**: Configurable worker count, default to CPU count
- **Risk**: Process startup overhead
  - **Mitigation**: Reuse worker processes, batch tasks
- **Risk**: Slower for small batches
  - **Mitigation**: Use single-threaded mode for <10 texts

## Progress Tracking
- [x] Research multiprocessing approach for sentence-transformers
- [x] Design ParallelEmbeddingGenerator architecture
- [x] Implement parallel embedding generation
- [x] Add configuration options
- [x] Integrate with IncrementalIndexer
- [x] Write comprehensive tests
- [x] Benchmark performance improvement
- [x] Update documentation
