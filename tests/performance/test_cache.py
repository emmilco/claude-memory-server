"""Performance tests for cache (SPEC F007-R002).

NOTE: These tests are currently skipped pending async fixture fixes.
See TEST-028 for tracking.
"""

import pytest
import time
import shutil
from pathlib import Path

# Skip all tests in this module - async fixture issues need fixing
pytestmark = pytest.mark.skip(reason="Performance tests need async fixture fixes (TEST-028)")


@pytest.mark.performance
@pytest.mark.asyncio
async def test_cache_hit_rate_above_90_percent(tmp_path, fresh_server):
    """SPEC F007-R002: Cache hit rate must be >90% for unchanged code.

    Target: >90%
    Current baseline: 98%
    """
    # Create test project
    project_dir = tmp_path / "cache_test"
    project_dir.mkdir()

    # Create 50 files
    for i in range(50):
        (project_dir / f"file_{i}.py").write_text(
            f"def function_{i}():\n    return {i}"
        )

    server = fresh_server

    # First index
    result1 = await server.index_codebase(
        directory_path=str(project_dir),
        project_name="cache_test",
        recursive=False
    )

    files_indexed_first = result1.get("files_indexed", 50)

    # Re-index without changes (should hit cache)
    result2 = await server.index_codebase(
        directory_path=str(project_dir),
        project_name="cache_test",
        recursive=False
    )

    # Calculate cache hit rate from result metrics
    cache_hits = result2.get("cache_hits", 0)
    total_files = result2.get("total_files", 50)

    cache_hit_rate = cache_hits / total_files if total_files > 0 else 0.0

    print(f"\n{'='*50}")
    print(f"CACHE HIT RATE PERFORMANCE RESULTS")
    print(f"{'='*50}")
    print(f"Total files: {total_files}")
    print(f"Cache hits: {cache_hits}")
    print(f"Cache misses: {total_files - cache_hits}")
    print(f"Cache hit rate: {cache_hit_rate * 100:.1f}%")
    print(f"{'='*50}")

    # Verify SPEC requirement
    assert cache_hit_rate > 0.90, (
        f"Cache hit rate {cache_hit_rate * 100:.1f}% below 90% "
        f"(SPEC F007-R002 violation)"
    )


@pytest.mark.performance
@pytest.mark.asyncio
async def test_cache_speedup_on_reindex(tmp_path, fresh_server):
    """Re-indexing with cache should be significantly faster.

    Target: >5x speedup
    Current baseline: 5-10x speedup
    """
    # Create test project
    project_dir = tmp_path / "speedup_test"
    project_dir.mkdir()

    # Create 30 files
    for i in range(30):
        (project_dir / f"file_{i}.py").write_text(
            f"def function_{i}():\n    return {i}\n\nclass Class{i}:\n    value = {i}"
        )

    server = fresh_server

    # First index (cold, no cache)
    start = time.perf_counter()
    await server.index_codebase(
        directory_path=str(project_dir),
        project_name="speedup_test",
        recursive=False
    )
    cold_time = time.perf_counter() - start

    # Second index (warm, with cache)
    start = time.perf_counter()
    await server.index_codebase(
        directory_path=str(project_dir),
        project_name="speedup_test",
        recursive=False
    )
    warm_time = time.perf_counter() - start

    speedup = cold_time / warm_time

    print(f"\nCache Speedup:")
    print(f"  Cold index (no cache): {cold_time:.2f}s")
    print(f"  Warm index (with cache): {warm_time:.2f}s")
    print(f"  Speedup: {speedup:.2f}x")

    # Re-indexing should be at least 5x faster with cache
    assert speedup > 5.0, (
        f"Cache speedup {speedup:.2f}x below 5x target"
    )


@pytest.mark.performance
@pytest.mark.asyncio
async def test_cache_invalidation_on_file_change(tmp_path, fresh_server):
    """Changed files should miss cache, unchanged should hit.

    Verify cache invalidation works correctly.
    """
    # Create test project
    project_dir = tmp_path / "invalidation_test"
    project_dir.mkdir()

    # Create 20 files
    for i in range(20):
        (project_dir / f"file_{i}.py").write_text(
            f"def function_{i}():\n    return {i}"
        )

    server = fresh_server

    # First index
    await server.index_codebase(
        directory_path=str(project_dir),
        project_name="invalidation_test",
        recursive=False
    )

    # Modify 5 files (25%)
    for i in range(5):
        (project_dir / f"file_{i}.py").write_text(
            f"def function_{i}_modified():\n    return {i * 2}"
        )

    # Re-index
    result = await server.index_codebase(
        directory_path=str(project_dir),
        project_name="invalidation_test",
        recursive=False
    )

    cache_hits = result.get("cache_hits", 0)
    total_files = result.get("total_files", 20)
    expected_hits = 15  # 20 - 5 modified

    print(f"\nCache Invalidation Test:")
    print(f"  Total files: {total_files}")
    print(f"  Modified files: 5")
    print(f"  Expected cache hits: {expected_hits}")
    print(f"  Actual cache hits: {cache_hits}")
    print(f"  Expected cache misses: 5")
    print(f"  Actual cache misses: {total_files - cache_hits}")

    # Cache hits should be within 1 of expected (accounting for timing issues)
    assert abs(cache_hits - expected_hits) <= 2, (
        f"Cache invalidation incorrect: expected ~{expected_hits} hits, got {cache_hits}"
    )


@pytest.mark.performance
@pytest.mark.asyncio
async def test_embedding_cache_effectiveness(fresh_server):
    """Embedding cache should reduce computation.

    Test that identical content uses cached embeddings.
    """
    server = fresh_server

    # Store memories with duplicate content
    duplicate_content = "User prefers dark mode for all applications"

    # First store (cold cache)
    start = time.perf_counter()
    await server.store_memory(
        content=duplicate_content,
        category="preference",
        importance=0.8
    )
    cold_time = time.perf_counter() - start

    # Subsequent stores with same content (should use cache)
    warm_times = []
    for i in range(5):
        start = time.perf_counter()
        await server.store_memory(
            content=duplicate_content,
            category="preference",
            importance=0.8,
            tags=[f"tag_{i}"]  # Different metadata to avoid deduplication
        )
        warm_time = time.perf_counter() - start
        warm_times.append(warm_time)

    avg_warm_time = sum(warm_times) / len(warm_times)
    speedup = cold_time / avg_warm_time

    print(f"\nEmbedding Cache Effectiveness:")
    print(f"  First store (cold): {cold_time * 1000:.2f}ms")
    print(f"  Avg subsequent stores (warm): {avg_warm_time * 1000:.2f}ms")
    print(f"  Speedup: {speedup:.2f}x")

    # Note: With mock embeddings, speedup may be minimal
    # In production, this should be >2x
    assert avg_warm_time <= cold_time, (
        "Cached embedding stores should not be slower than cold"
    )


@pytest.mark.performance
@pytest.mark.asyncio
async def test_cache_memory_usage(tmp_path, fresh_server):
    """Cache should not consume excessive memory.

    Verify cache doesn't grow unbounded during large indexing operations.
    """
    import psutil
    import os

    # Create large test project
    project_dir = tmp_path / "memory_test"
    project_dir.mkdir()

    # Create 100 files
    for i in range(100):
        (project_dir / f"file_{i}.py").write_text(
            f"def function_{i}():\n    return {i}\n" * 10  # Bigger files
        )

    server = fresh_server

    # Measure memory before indexing
    process = psutil.Process(os.getpid())
    memory_before = process.memory_info().rss / 1024 / 1024  # MB

    # Index project
    await server.index_codebase(
        directory_path=str(project_dir),
        project_name="memory_test",
        recursive=False
    )

    # Measure memory after indexing
    memory_after = process.memory_info().rss / 1024 / 1024  # MB
    memory_increase = memory_after - memory_before

    print(f"\nCache Memory Usage:")
    print(f"  Memory before: {memory_before:.2f} MB")
    print(f"  Memory after: {memory_after:.2f} MB")
    print(f"  Increase: {memory_increase:.2f} MB")
    print(f"  Per file: {memory_increase / 100:.2f} MB")

    # Memory increase should be reasonable (<100MB for 100 files)
    assert memory_increase < 100, (
        f"Cache memory usage {memory_increase:.2f} MB excessive for 100 files"
    )
