"""Performance tests for throughput (SPEC F007-R003, F007-R006)."""

import pytest
import time
import asyncio


@pytest.mark.performance
@pytest.mark.asyncio
async def test_indexing_throughput_above_1_file_per_sec(
    temp_code_directory, fresh_server
):
    """SPEC F007-R003: Indexing throughput must be >1 file/sec.

    Target: >1 file/sec
    Current baseline: 2.45 files/sec (sequential)
    """
    # Create 100 test files
    code_dir = temp_code_directory(count=100)

    server = fresh_server

    # Measure indexing throughput
    start = time.perf_counter()
    result = await server.index_codebase(
        directory_path=str(code_dir), project_name="throughput_test", recursive=False
    )
    elapsed = time.perf_counter() - start

    files_indexed = result.get("files_indexed", 100)
    files_per_sec = files_indexed / elapsed

    print(f"\n{'='*50}")
    print("INDEXING THROUGHPUT PERFORMANCE RESULTS")
    print(f"{'='*50}")
    print(f"Files indexed: {files_indexed}")
    print(f"Time elapsed: {elapsed:.2f}s")
    print(f"Throughput: {files_per_sec:.2f} files/sec")
    print(f"{'='*50}")

    # Verify SPEC requirement
    assert files_per_sec > 1.0, (
        f"Indexing throughput {files_per_sec:.2f} files/sec below 1.0 "
        f"(SPEC F007-R003 violation)"
    )


@pytest.mark.performance
@pytest.mark.asyncio
async def test_concurrent_request_throughput(indexed_test_project):
    """SPEC F007-R006: Concurrent throughput must be >10 req/sec.

    Target: >10 req/sec
    Current baseline: 55,246 ops/sec
    """
    server = indexed_test_project

    # Run 100 concurrent searches
    async def search_task(i: int):
        """Single search task."""
        query = f"function_{i % 10}"
        return await server.search_code(query=query, project_name="perf_test", limit=5)

    start = time.perf_counter()
    tasks = [search_task(i) for i in range(100)]
    await asyncio.gather(*tasks)
    elapsed = time.perf_counter() - start

    req_per_sec = 100 / elapsed

    print(f"\n{'='*50}")
    print("CONCURRENT REQUEST THROUGHPUT")
    print(f"{'='*50}")
    print("Requests: 100")
    print(f"Time elapsed: {elapsed:.2f}s")
    print(f"Throughput: {req_per_sec:.2f} req/sec")
    print(f"Avg latency per request: {(elapsed / 100) * 1000:.2f}ms")
    print(f"{'='*50}")

    # Verify SPEC requirement
    assert req_per_sec > 10, (
        f"Concurrent throughput {req_per_sec:.2f} req/sec below 10 "
        f"(SPEC F007-R006 violation)"
    )


@pytest.mark.performance
@pytest.mark.asyncio
async def test_memory_store_throughput(fresh_server):
    """Memory storage should handle reasonable throughput.

    Target: >20 memories/sec
    """
    server = fresh_server

    # Store 100 memories and measure throughput
    start = time.perf_counter()

    for i in range(100):
        await server.store_memory(
            content=f"Performance test memory {i}",
            category="fact",
            importance=0.5,
            tags=[f"tag_{i % 5}"],
        )

    elapsed = time.perf_counter() - start
    memories_per_sec = 100 / elapsed

    print("\nMemory Storage Throughput:")
    print("  Memories stored: 100")
    print(f"  Time elapsed: {elapsed:.2f}s")
    print(f"  Throughput: {memories_per_sec:.2f} memories/sec")

    assert (
        memories_per_sec > 20
    ), f"Memory storage throughput {memories_per_sec:.2f} memories/sec below 20"


@pytest.mark.performance
@pytest.mark.asyncio
async def test_batch_operation_throughput(fresh_server):
    """Batch operations should be faster than individual.

    Compare individual vs batch memory storage.
    """
    server = fresh_server

    # Individual storage (10 memories)
    start = time.perf_counter()
    for i in range(10):
        await server.store_memory(
            content=f"Individual memory {i}", category="fact", importance=0.5
        )
    individual_elapsed = time.perf_counter() - start

    # Batch-style concurrent storage (10 memories)
    start = time.perf_counter()
    tasks = [
        server.store_memory(
            content=f"Batch memory {i}", category="fact", importance=0.5
        )
        for i in range(10)
    ]
    await asyncio.gather(*tasks)
    batch_elapsed = time.perf_counter() - start

    speedup = individual_elapsed / batch_elapsed

    print("\nBatch Operation Performance:")
    print(f"  Individual (sequential): {individual_elapsed:.2f}s")
    print(f"  Concurrent (parallel): {batch_elapsed:.2f}s")
    print(f"  Speedup: {speedup:.2f}x")

    # Batch should be at least 1.5x faster
    assert (
        speedup > 1.5
    ), f"Batch operations only {speedup:.2f}x faster, expected >1.5x speedup"


@pytest.mark.performance
@pytest.mark.asyncio
async def test_throughput_degradation_over_time(
    indexed_test_project, performance_tracker
):
    """Throughput should remain stable over extended operation.

    Run searches in 5 batches and verify throughput doesn't degrade.
    """
    server = indexed_test_project

    # Run 5 batches of 50 searches each
    batch_throughputs = []

    for batch in range(5):
        start = time.perf_counter()

        for i in range(50):
            await server.search_code(
                query=f"function_{i % 10}", project_name="perf_test", limit=5
            )

        elapsed = time.perf_counter() - start
        throughput = 50 / elapsed
        batch_throughputs.append(throughput)

    print("\nThroughput over Time (5 batches of 50 requests):")
    for i, throughput in enumerate(batch_throughputs, 1):
        print(f"  Batch {i}: {throughput:.2f} req/sec")

    # Calculate degradation
    first_batch = batch_throughputs[0]
    last_batch = batch_throughputs[-1]
    degradation = (first_batch - last_batch) / first_batch

    print(f"\n  First batch: {first_batch:.2f} req/sec")
    print(f"  Last batch: {last_batch:.2f} req/sec")
    print(f"  Degradation: {degradation * 100:.1f}%")

    # Throughput should not degrade by more than 20%
    assert (
        degradation < 0.20
    ), f"Throughput degraded by {degradation * 100:.1f}% over time, exceeds 20% threshold"
