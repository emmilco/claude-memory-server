#!/usr/bin/env python3
"""Performance benchmarks for large-scale database operations."""

import asyncio
import sys
import time
import statistics
from pathlib import Path
from typing import List, Dict, Any
import random

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import ServerConfig
from src.core.server import MemoryRAGServer
from src.core.models import MemoryCategory


class PerformanceBenchmark:
    """Performance benchmarking suite for scale testing."""

    def __init__(self):
        self.config = ServerConfig()
        self.server = None
        self.results = []

    async def initialize(self):
        """Initialize server."""
        self.server = MemoryRAGServer(self.config)
        await self.server.initialize()

    async def close(self):
        """Close server."""
        if self.server:
            await self.server.close()

    async def benchmark_search_latency(
        self,
        queries: List[str],
        iterations: int = 10,
        limit: int = 5
    ) -> Dict[str, Any]:
        """
        Benchmark search latency with various query types.

        Args:
            queries: List of search queries to test
            iterations: Number of times to run each query
            limit: Number of results to retrieve per query

        Returns:
            Dict with latency statistics
        """
        print(f"\n{'='*70}")
        print("BENCHMARK: Search Latency at Scale")
        print(f"{'='*70}")
        print(f"Queries: {len(queries)}")
        print(f"Iterations per query: {iterations}")
        print(f"Limit: {limit}")
        print(f"{'='*70}\n")

        all_latencies = []

        for i, query in enumerate(queries, 1):
            query_latencies = []

            print(f"Query {i}/{len(queries)}: '{query[:50]}...'")

            for _ in range(iterations):
                start = time.time()
                await self.server.retrieve_memories(query, limit=limit)
                latency = (time.time() - start) * 1000  # Convert to ms
                query_latencies.append(latency)
                all_latencies.append(latency)

            # Query-specific stats
            avg = statistics.mean(query_latencies)
            p50 = statistics.median(query_latencies)
            p95 = statistics.quantiles(query_latencies, n=20)[18] if len(query_latencies) >= 20 else max(query_latencies)

            print(f"  Avg: {avg:.2f}ms | P50: {p50:.2f}ms | P95: {p95:.2f}ms")

        # Overall stats
        print(f"\n{'='*70}")
        print("Overall Search Latency Statistics")
        print(f"{'='*70}")

        avg_latency = statistics.mean(all_latencies)
        median_latency = statistics.median(all_latencies)
        min_latency = min(all_latencies)
        max_latency = max(all_latencies)
        p95_latency = statistics.quantiles(all_latencies, n=20)[18] if len(all_latencies) >= 20 else max(all_latencies)
        p99_latency = statistics.quantiles(all_latencies, n=100)[98] if len(all_latencies) >= 100 else max(all_latencies)

        print(f"Total Queries: {len(all_latencies)}")
        print(f"Average:  {avg_latency:.2f}ms")
        print(f"Median:   {median_latency:.2f}ms")
        print(f"Min:      {min_latency:.2f}ms")
        print(f"Max:      {max_latency:.2f}ms")
        print(f"P95:      {p95_latency:.2f}ms")
        print(f"P99:      {p99_latency:.2f}ms")

        # Check against target (<50ms p95)
        target_p95 = 50.0
        status = "✅ PASS" if p95_latency < target_p95 else "❌ FAIL"
        print(f"\nTarget P95: <{target_p95}ms")
        print(f"Actual P95: {p95_latency:.2f}ms")
        print(f"Status: {status}")
        print(f"{'='*70}\n")

        return {
            "total_queries": len(all_latencies),
            "avg_ms": avg_latency,
            "median_ms": median_latency,
            "min_ms": min_latency,
            "max_ms": max_latency,
            "p95_ms": p95_latency,
            "p99_ms": p99_latency,
            "target_p95_ms": target_p95,
            "passes_target": p95_latency < target_p95,
        }

    async def benchmark_memory_retrieval_types(self) -> Dict[str, Any]:
        """
        Benchmark different types of memory retrieval operations.

        Returns:
            Dict with performance stats for each retrieval type
        """
        print(f"\n{'='*70}")
        print("BENCHMARK: Memory Retrieval Operations")
        print(f"{'='*70}\n")

        results = {}

        # Test different retrieval patterns
        tests = [
            ("retrieve_preferences", lambda: self.server.retrieve_preferences("code style")),
            ("retrieve_project_context", lambda: self.server.retrieve_project_context("api-server")),
            ("retrieve_session_state", lambda: self.server.retrieve_session_state("current task")),
            ("list_memories", lambda: self.server.list_memories(limit=20)),
            ("list_memories_filtered", lambda: self.server.list_memories(
                category=MemoryCategory.PREFERENCE.value, min_importance=0.7, limit=20
            )),
        ]

        for test_name, test_func in tests:
            latencies = []

            print(f"Testing: {test_name}")

            for _ in range(20):
                start = time.time()
                await test_func()
                latency = (time.time() - start) * 1000
                latencies.append(latency)

            avg = statistics.mean(latencies)
            p95 = statistics.quantiles(latencies, n=20)[18] if len(latencies) >= 20 else max(latencies)

            print(f"  Avg: {avg:.2f}ms | P95: {p95:.2f}ms")

            results[test_name] = {
                "avg_ms": avg,
                "p95_ms": p95,
            }

        print(f"{'='*70}\n")
        return results

    async def benchmark_concurrent_load(
        self,
        num_concurrent: int = 10,
        operations_per_client: int = 5
    ) -> Dict[str, Any]:
        """
        Benchmark performance under concurrent load.

        Args:
            num_concurrent: Number of concurrent clients
            operations_per_client: Operations per client

        Returns:
            Dict with concurrency performance stats
        """
        print(f"\n{'='*70}")
        print("BENCHMARK: Concurrent Load Performance")
        print(f"{'='*70}")
        print(f"Concurrent Clients: {num_concurrent}")
        print(f"Operations per Client: {operations_per_client}")
        print(f"Total Operations: {num_concurrent * operations_per_client}")
        print(f"{'='*70}\n")

        queries = [
            "authentication system",
            "database optimization",
            "error handling",
            "testing strategy",
            "deployment process",
        ]

        async def client_workload():
            """Simulate a client performing multiple operations."""
            client_latencies = []
            for _ in range(operations_per_client):
                query = random.choice(queries)
                start = time.time()
                await self.server.retrieve_memories(query, limit=5)
                latency = (time.time() - start) * 1000
                client_latencies.append(latency)
            return client_latencies

        # Run concurrent clients
        start = time.time()
        results = await asyncio.gather(*[client_workload() for _ in range(num_concurrent)])
        total_time = time.time() - start

        # Flatten results
        all_latencies = [lat for client_lats in results for lat in client_lats]

        avg_latency = statistics.mean(all_latencies)
        p95_latency = statistics.quantiles(all_latencies, n=20)[18] if len(all_latencies) >= 20 else max(all_latencies)
        throughput = len(all_latencies) / total_time

        print(f"Results:")
        print(f"  Total Time: {total_time:.2f}s")
        print(f"  Total Operations: {len(all_latencies)}")
        print(f"  Average Latency: {avg_latency:.2f}ms")
        print(f"  P95 Latency: {p95_latency:.2f}ms")
        print(f"  Throughput: {throughput:.1f} ops/sec")
        print(f"{'='*70}\n")

        return {
            "num_concurrent": num_concurrent,
            "total_operations": len(all_latencies),
            "total_time_s": total_time,
            "avg_latency_ms": avg_latency,
            "p95_latency_ms": p95_latency,
            "throughput_ops_per_sec": throughput,
        }

    async def get_database_stats(self) -> Dict[str, Any]:
        """Get current database statistics."""
        # Get total count from store
        total = await self.server.store.count()

        # Get operation stats from server
        server_stats = self.server.stats

        stats = {
            'total_memories': total,
            'operations': server_stats,
        }

        print(f"\n{'='*70}")
        print("Database Statistics")
        print(f"{'='*70}")
        print(f"Total Memories: {total:,}")
        print(f"\nOperation Stats:")
        print(f"  Stored: {server_stats.get('memories_stored', 0):,}")
        print(f"  Retrieved: {server_stats.get('memories_retrieved', 0):,}")
        print(f"  Deleted: {server_stats.get('memories_deleted', 0):,}")
        print(f"  Queries: {server_stats.get('queries_processed', 0):,}")
        print(f"{'='*70}\n")

        return stats


async def run_all_benchmarks():
    """Run comprehensive performance benchmark suite."""
    print("\n" + "="*70)
    print("PERFORMANCE BENCHMARK SUITE - SCALE TESTING")
    print("="*70)

    benchmark = PerformanceBenchmark()

    try:
        await benchmark.initialize()

        # Get database stats first
        db_stats = await benchmark.get_database_stats()
        total_memories = db_stats.get('total_memories', 0)

        if total_memories < 1000:
            print("\n⚠️  WARNING: Database has fewer than 1,000 memories.")
            print("For meaningful scale testing, generate a larger test database:")
            print("  python scripts/generate_test_data.py 10000")
            print("  python scripts/generate_test_data.py 50000")
            print("\nProceeding with available data...\n")

        # Define test queries
        test_queries = [
            "authentication and authorization",
            "database connection pooling",
            "error handling best practices",
            "testing strategies for APIs",
            "deployment configuration",
            "caching mechanisms",
            "security vulnerabilities",
            "performance optimization",
            "code review process",
            "documentation standards",
        ]

        # Run benchmarks
        results = {}

        results['search_latency'] = await benchmark.benchmark_search_latency(
            test_queries, iterations=5
        )

        results['retrieval_operations'] = await benchmark.benchmark_memory_retrieval_types()

        results['concurrent_load'] = await benchmark.benchmark_concurrent_load(
            num_concurrent=10, operations_per_client=5
        )

        # Summary
        print(f"\n{'='*70}")
        print("BENCHMARK SUMMARY")
        print(f"{'='*70}")
        print(f"Database Size: {total_memories:,} memories")
        print(f"\nSearch Performance:")
        print(f"  Average Latency: {results['search_latency']['avg_ms']:.2f}ms")
        print(f"  P95 Latency: {results['search_latency']['p95_ms']:.2f}ms")
        print(f"  Target: <50ms P95 ({'✅ PASS' if results['search_latency']['passes_target'] else '❌ FAIL'})")
        print(f"\nConcurrent Performance:")
        print(f"  Throughput: {results['concurrent_load']['throughput_ops_per_sec']:.1f} ops/sec")
        print(f"  P95 under load: {results['concurrent_load']['p95_latency_ms']:.2f}ms")
        print(f"{'='*70}\n")

    finally:
        await benchmark.close()


if __name__ == "__main__":
    asyncio.run(run_all_benchmarks())
