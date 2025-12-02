"""Performance tests for search latency (SPEC F007-R001)."""

import pytest
import time


@pytest.mark.performance
@pytest.mark.asyncio
async def test_search_latency_p95_under_50ms(indexed_test_project, performance_tracker):
    """SPEC F007-R001: P95 search latency must be <50ms.

    Target: <50ms
    Current baseline: 3.96ms (12.6x better than target)
    """
    server = indexed_test_project

    # Run 100 searches with varying queries
    queries = [
        "authenticate user",
        "process data",
        "execute request",
        "function test",
        "class Service",
        "validate credentials",
        "handle request",
        "compute result",
        "module function",
        "service class",
    ]

    for i in range(100):
        query = queries[i % len(queries)]

        start = time.perf_counter()
        await server.search_code(query=query, project_name="perf_test", limit=10)
        elapsed_ms = (time.perf_counter() - start) * 1000
        performance_tracker.record(elapsed_ms)

    # Print detailed stats
    print(f"\n{'='*50}")
    print("SEARCH LATENCY PERFORMANCE RESULTS")
    print(f"{'='*50}")
    print(f"P50: {performance_tracker.p50:.2f}ms")
    print(f"P95: {performance_tracker.p95:.2f}ms")
    print(f"P99: {performance_tracker.p99:.2f}ms")
    print(f"Mean: {performance_tracker.mean:.2f}ms")
    print(f"Min: {performance_tracker.min:.2f}ms")
    print(f"Max: {performance_tracker.max:.2f}ms")
    print(f"{'='*50}")

    # Verify SPEC requirement
    assert performance_tracker.p95 < 50, (
        f"P95 latency {performance_tracker.p95:.2f}ms exceeds 50ms target "
        f"(SPEC F007-R001 violation)"
    )


@pytest.mark.performance
@pytest.mark.asyncio
async def test_search_latency_p50_under_20ms(indexed_test_project, performance_tracker):
    """Median search latency should be well under threshold.

    Target: <20ms (internal goal, not SPEC requirement)
    Current baseline: ~2ms
    """
    server = indexed_test_project

    # Run 50 searches
    for i in range(50):
        query = f"function_{i % 10}"

        start = time.perf_counter()
        await server.search_code(query=query, project_name="perf_test", limit=5)
        elapsed_ms = (time.perf_counter() - start) * 1000
        performance_tracker.record(elapsed_ms)

    print(f"\nP50 Search Latency: {performance_tracker.p50:.2f}ms")
    print(f"P95 Search Latency: {performance_tracker.p95:.2f}ms")

    # Internal performance goal
    assert (
        performance_tracker.p50 < 20
    ), f"P50 latency {performance_tracker.p50:.2f}ms exceeds 20ms internal goal"


@pytest.mark.performance
@pytest.mark.asyncio
async def test_memory_retrieve_latency(server_with_memories, performance_tracker):
    """Memory retrieval should be fast.

    Target: <30ms P95
    """
    server = server_with_memories

    # Run 50 memory retrievals
    queries = [
        "vim editor preference",
        "emacs settings",
        "vscode configuration",
        "user preferences",
        "editor choice",
    ]

    for i in range(50):
        query = queries[i % len(queries)]

        start = time.perf_counter()
        await server.retrieve_memories(query=query, limit=10)
        elapsed_ms = (time.perf_counter() - start) * 1000
        performance_tracker.record(elapsed_ms)

    print("\nMemory Retrieval Latency:")
    print(f"  P50: {performance_tracker.p50:.2f}ms")
    print(f"  P95: {performance_tracker.p95:.2f}ms")
    print(f"  P99: {performance_tracker.p99:.2f}ms")

    assert (
        performance_tracker.p95 < 30
    ), f"Memory retrieval P95 latency {performance_tracker.p95:.2f}ms exceeds 30ms"


@pytest.mark.performance
@pytest.mark.asyncio
async def test_latency_stable_under_load(indexed_test_project, performance_tracker):
    """Latency should not spike during sustained load.

    Verify that P99 is within 3x of P50 (no major outliers).
    """
    server = indexed_test_project

    # Sustained load: 200 consecutive searches
    for i in range(200):
        query = "function authenticate process execute"

        start = time.perf_counter()
        await server.search_code(query=query, project_name="perf_test", limit=5)
        elapsed_ms = (time.perf_counter() - start) * 1000
        performance_tracker.record(elapsed_ms)

    print("\nLatency Stability under Load (200 requests):")
    print(f"  P50: {performance_tracker.p50:.2f}ms")
    print(f"  P95: {performance_tracker.p95:.2f}ms")
    print(f"  P99: {performance_tracker.p99:.2f}ms")
    print(f"  P99/P50 ratio: {performance_tracker.p99 / performance_tracker.p50:.2f}x")

    # Verify stability: P99 should be < 3x P50
    ratio = performance_tracker.p99 / performance_tracker.p50
    assert ratio < 3.0, (
        f"Latency instability detected: P99/P50 ratio {ratio:.2f}x exceeds 3x "
        f"(indicates performance spikes)"
    )


@pytest.mark.performance
@pytest.mark.asyncio
async def test_cold_vs_warm_search_latency(indexed_test_project):
    """First search may be slower, subsequent should be fast.

    Tests cache warming behavior.
    """
    server = indexed_test_project
    query = "authenticate user credentials"

    # Cold search (first query)
    start = time.perf_counter()
    await server.search_code(query=query, project_name="perf_test", limit=5)
    cold_latency_ms = (time.perf_counter() - start) * 1000

    # Warm searches (subsequent queries)
    warm_latencies = []
    for _ in range(10):
        start = time.perf_counter()
        await server.search_code(query=query, project_name="perf_test", limit=5)
        warm_latency_ms = (time.perf_counter() - start) * 1000
        warm_latencies.append(warm_latency_ms)

    avg_warm_latency = sum(warm_latencies) / len(warm_latencies)

    print("\nCold vs Warm Search Latency:")
    print(f"  Cold (first): {cold_latency_ms:.2f}ms")
    print(f"  Warm (avg of 10): {avg_warm_latency:.2f}ms")
    print(f"  Speedup: {cold_latency_ms / avg_warm_latency:.2f}x")

    # Warm searches should be reasonably fast
    assert (
        avg_warm_latency < 50
    ), f"Warm search latency {avg_warm_latency:.2f}ms exceeds 50ms"
