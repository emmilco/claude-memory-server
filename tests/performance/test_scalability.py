"""Performance tests for scalability (SPEC F007-R007).

NOTE: These tests are currently skipped pending async fixture fixes.
See TEST-028 for tracking.
"""

import pytest
import time
import asyncio

# Skip all tests in this module - async fixture issues need fixing
pytestmark = pytest.mark.skip(reason="Performance tests need async fixture fixes (TEST-028)")


@pytest.mark.performance
@pytest.mark.slow
@pytest.mark.asyncio
async def test_search_scales_with_index_size(tmp_path, fresh_server):
    """Search latency should scale sub-linearly with index size.

    Test with 50, 100, and 200 files to verify scalability.
    """
    server = fresh_server

    results = []

    for file_count in [50, 100, 200]:
        # Create project with N files
        project_dir = tmp_path / f"scale_{file_count}"
        project_dir.mkdir(exist_ok=True)

        for i in range(file_count):
            (project_dir / f"file_{i}.py").write_text(
                f"def function_{i}():\n    return {i}"
            )

        # Index project
        await server.index_codebase(
            directory_path=str(project_dir),
            project_name=f"scale_{file_count}",
            recursive=False
        )

        # Measure search latency (average of 20 searches)
        latencies = []
        for _ in range(20):
            start = time.perf_counter()
            await server.search_code(
                query="function test",
                project_name=f"scale_{file_count}",
                limit=10
            )
            latency_ms = (time.perf_counter() - start) * 1000
            latencies.append(latency_ms)

        avg_latency = sum(latencies) / len(latencies)
        results.append((file_count, avg_latency))

    print(f"\n{'='*50}")
    print(f"SEARCH SCALABILITY RESULTS")
    print(f"{'='*50}")
    for files, latency in results:
        print(f"  {files} files: {latency:.2f}ms avg search latency")

    # Calculate scaling factor
    # Ideally, 4x files should be <2x latency (sub-linear)
    latency_50 = results[0][1]
    latency_200 = results[2][1]
    scaling_factor = latency_200 / latency_50
    file_scaling_factor = 200 / 50  # 4x

    print(f"\nScaling Analysis:")
    print(f"  50 files: {latency_50:.2f}ms")
    print(f"  200 files: {latency_200:.2f}ms")
    print(f"  File count increased: {file_scaling_factor:.1f}x")
    print(f"  Latency increased: {scaling_factor:.2f}x")
    print(f"  Scaling efficiency: {file_scaling_factor / scaling_factor:.2f}x")
    print(f"{'='*50}")

    # Latency should not increase linearly with file count
    # 4x files should result in <3x latency increase
    assert scaling_factor < 3.0, (
        f"Search latency scaling {scaling_factor:.2f}x for 4x files is too high "
        f"(should be <3x, ideally <2x)"
    )


@pytest.mark.performance
@pytest.mark.asyncio
async def test_memory_count_scaling(fresh_server):
    """Performance with 1000, 2000, 3000 memories.

    Verify retrieval performance scales acceptably.
    """
    server = fresh_server

    results = []

    for memory_count in [1000, 2000, 3000]:
        # Store memories
        for i in range(memory_count):
            await server.store_memory(
                content=f"Test memory {i}: preference for setting_{i % 100}",
                category="preference",
                importance=0.5
            )

        # Measure retrieval latency (average of 10 queries)
        latencies = []
        for _ in range(10):
            start = time.perf_counter()
            await server.retrieve_memories(
                query="preference setting",
                limit=10
            )
            latency_ms = (time.perf_counter() - start) * 1000
            latencies.append(latency_ms)

        avg_latency = sum(latencies) / len(latencies)
        results.append((memory_count, avg_latency))

    print(f"\nMemory Count Scalability:")
    for count, latency in results:
        print(f"  {count} memories: {latency:.2f}ms avg retrieval")

    # 3x memories should not cause >2x latency increase
    latency_1000 = results[0][1]
    latency_3000 = results[2][1]
    scaling_factor = latency_3000 / latency_1000

    print(f"\n  1000 memories: {latency_1000:.2f}ms")
    print(f"  3000 memories: {latency_3000:.2f}ms")
    print(f"  Scaling factor: {scaling_factor:.2f}x")

    assert scaling_factor < 2.0, (
        f"Memory retrieval scaling {scaling_factor:.2f}x for 3x memories is too high"
    )


@pytest.mark.performance
@pytest.mark.asyncio
async def test_project_count_scaling(tmp_path, fresh_server):
    """Performance with multiple projects.

    Test with 5 and 10 projects to verify multi-project scalability.
    """
    server = fresh_server

    results = []

    for project_count in [5, 10]:
        # Create multiple projects
        for p in range(project_count):
            project_dir = tmp_path / f"multi_{project_count}" / f"project_{p}"
            project_dir.mkdir(parents=True, exist_ok=True)

            # 20 files per project
            for i in range(20):
                (project_dir / f"file_{i}.py").write_text(
                    f"def function_{p}_{i}():\n    return {i}"
                )

            await server.index_codebase(
                directory_path=str(project_dir),
                project_name=f"project_{p}",
                recursive=False
            )

        # Measure search latency across all projects
        latencies = []
        for p in range(project_count):
            for _ in range(5):  # 5 searches per project
                start = time.perf_counter()
                await server.search_code(
                    query="function test",
                    project_name=f"project_{p}",
                    limit=5
                )
                latency_ms = (time.perf_counter() - start) * 1000
                latencies.append(latency_ms)

        avg_latency = sum(latencies) / len(latencies)
        results.append((project_count, avg_latency))

    print(f"\nProject Count Scalability:")
    for count, latency in results:
        print(f"  {count} projects: {latency:.2f}ms avg search latency")

    # Latency should remain acceptable with multiple projects
    latency_10 = results[1][1]
    assert latency_10 < 100, (
        f"Search latency {latency_10:.2f}ms too high with 10 projects"
    )


@pytest.mark.performance
@pytest.mark.asyncio
async def test_concurrent_user_simulation(indexed_test_project):
    """Simulate 10 concurrent users.

    Each user performs 10 searches concurrently.
    """
    server = indexed_test_project

    async def user_session(user_id: int):
        """Simulate a single user session."""
        latencies = []
        for i in range(10):
            start = time.perf_counter()
            await server.search_code(
                query=f"function_{i % 5}",
                project_name="perf_test",
                limit=5
            )
            latency_ms = (time.perf_counter() - start) * 1000
            latencies.append(latency_ms)
        return latencies

    # Run 10 concurrent user sessions
    start = time.perf_counter()
    user_tasks = [user_session(i) for i in range(10)]
    all_latencies_nested = await asyncio.gather(*user_tasks)
    total_elapsed = time.perf_counter() - start

    # Flatten latencies
    all_latencies = [lat for user_lats in all_latencies_nested for lat in user_lats]

    # Calculate statistics
    avg_latency = sum(all_latencies) / len(all_latencies)
    sorted_lats = sorted(all_latencies)
    p95_latency = sorted_lats[int(len(sorted_lats) * 0.95)]

    total_requests = 10 * 10  # 10 users * 10 requests
    throughput = total_requests / total_elapsed

    print(f"\n{'='*50}")
    print(f"CONCURRENT USER SIMULATION (10 users)")
    print(f"{'='*50}")
    print(f"Total requests: {total_requests}")
    print(f"Total time: {total_elapsed:.2f}s")
    print(f"Throughput: {throughput:.2f} req/sec")
    print(f"Avg latency: {avg_latency:.2f}ms")
    print(f"P95 latency: {p95_latency:.2f}ms")
    print(f"{'='*50}")

    # P95 should remain under 100ms even with concurrent load
    assert p95_latency < 100, (
        f"P95 latency {p95_latency:.2f}ms too high under concurrent load"
    )


@pytest.mark.performance
@pytest.mark.asyncio
async def test_large_file_handling(tmp_path, fresh_server):
    """Performance with files >1KB.

    Verify that larger files don't cause excessive latency.
    """
    # Create test files of varying sizes
    project_dir = tmp_path / "large_files"
    project_dir.mkdir()

    file_sizes = []

    # Create 20 files with increasing size
    for i in range(20):
        # Each file has 50-500 lines
        lines = 50 + (i * 25)
        content = "\n".join([f"def function_{i}_{j}():\n    return {j}" for j in range(lines)])
        file_path = project_dir / f"file_{i}.py"
        file_path.write_text(content)
        file_sizes.append(len(content))

    server = fresh_server

    # Measure indexing time
    start = time.perf_counter()
    result = await server.index_codebase(
        directory_path=str(project_dir),
        project_name="large_files",
        recursive=False
    )
    indexing_time = time.perf_counter() - start

    files_indexed = result.get("files_indexed", 20)
    throughput = files_indexed / indexing_time
    avg_file_size = sum(file_sizes) / len(file_sizes)

    print(f"\nLarge File Handling:")
    print(f"  Files indexed: {files_indexed}")
    print(f"  Avg file size: {avg_file_size / 1024:.2f} KB")
    print(f"  Total time: {indexing_time:.2f}s")
    print(f"  Throughput: {throughput:.2f} files/sec")

    # Should still maintain >1 file/sec even with larger files
    assert throughput > 1.0, (
        f"Throughput {throughput:.2f} files/sec below 1.0 with larger files"
    )
