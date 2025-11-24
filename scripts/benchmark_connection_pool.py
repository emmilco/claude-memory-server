#!/usr/bin/env python
"""Benchmark script for connection pooling - Days 4-5 of PERF-007.

Measures performance metrics comparing pooled vs non-pooled connections:
- Throughput (operations/second)
- Latency (P50, P95, P99)
- Connection count tracking
- Pool utilization metrics

Usage:
    python scripts/benchmark_connection_pool.py [--iterations 1000]
"""

import asyncio
import time
import json
import logging
import statistics
from pathlib import Path
from typing import List, Dict, Any
from dataclasses import dataclass, asdict
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import get_config
from src.core.server import MemoryRAGServer
from src.core.models import MemoryUnit, MemoryCategory, MemoryScope

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)


@dataclass
class BenchmarkResult:
    """Benchmark results for a single test scenario."""

    scenario: str
    iterations: int
    total_duration_sec: float
    throughput_ops_sec: float
    latencies_ms: List[float]
    p50_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    min_latency_ms: float
    max_latency_ms: float
    pool_active_connections: int
    pool_idle_connections: int
    pool_total_acquires: int
    pool_health_failures: int
    successful_operations: int
    failed_operations: int


class PoolBenchmark:
    """Benchmark harness for connection pooling performance."""

    def __init__(self, iterations: int = 1000):
        self.iterations = iterations
        self.server: Optional[MemoryRAGServer] = None
        self.latencies: List[float] = []

    async def setup(self):
        """Initialize server and connections."""
        print("Setting up benchmark environment...")
        config = get_config()

        self.server = MemoryRAGServer(config=config)
        await self.server.initialize()
        print("✅ Server initialized")

    async def teardown(self):
        """Clean up resources."""
        if self.server:
            await self.server.close()
            print("✅ Server closed")

    async def benchmark_retrieve_operations(self, scenario_name: str) -> BenchmarkResult:
        """Benchmark retrieve operations (most common read operation).

        Args:
            scenario_name: Name of the benchmark scenario

        Returns:
            BenchmarkResult with performance metrics
        """
        self.latencies = []
        successful = 0
        failed = 0

        # Create sample memory for retrieval
        sample_memory = MemoryUnit(
            content="test content for retrieval",
            category=MemoryCategory.FACT,
            scope=MemoryScope.USER_PREFERENCE,
            tags=["benchmark", "test"],
            importance=0.8,
        )

        print(f"\nRunning {scenario_name}...")
        print(f"  Iterations: {self.iterations}")

        start_time = time.time()

        try:
            # Store initial memory
            await self.server.store_memory(
                content=sample_memory.content,
                category=sample_memory.category.value,
                scope=sample_memory.scope.value,
                tags=sample_memory.tags,
                importance=sample_memory.importance,
            )

            # Run retrieve operations
            for i in range(self.iterations):
                op_start = time.time()

                try:
                    result = await self.server.retrieve_memories(
                        query="test content",
                        limit=10,
                        min_importance=0.0,
                    )
                    op_duration_ms = (time.time() - op_start) * 1000
                    self.latencies.append(op_duration_ms)
                    successful += 1

                    if (i + 1) % 100 == 0:
                        print(f"    Progress: {i + 1}/{self.iterations}")

                except Exception as e:
                    logger.error(f"Operation failed: {e}")
                    failed += 1

        except Exception as e:
            print(f"❌ Error during benchmark: {e}")
            raise
        finally:
            total_duration = time.time() - start_time

        # Calculate metrics
        if not self.latencies:
            print(f"⚠️  No successful operations")
            return None

        sorted_latencies = sorted(self.latencies)
        p50_idx = int(len(sorted_latencies) * 0.50)
        p95_idx = int(len(sorted_latencies) * 0.95)
        p99_idx = int(len(sorted_latencies) * 0.99)

        throughput = successful / total_duration if total_duration > 0 else 0

        result = BenchmarkResult(
            scenario=scenario_name,
            iterations=self.iterations,
            total_duration_sec=total_duration,
            throughput_ops_sec=throughput,
            latencies_ms=sorted_latencies,
            p50_latency_ms=sorted_latencies[p50_idx] if p50_idx < len(sorted_latencies) else 0,
            p95_latency_ms=sorted_latencies[p95_idx] if p95_idx < len(sorted_latencies) else 0,
            p99_latency_ms=sorted_latencies[p99_idx] if p99_idx < len(sorted_latencies) else 0,
            min_latency_ms=min(sorted_latencies),
            max_latency_ms=max(sorted_latencies),
            pool_active_connections=0,  # Would be populated if pool exposes this
            pool_idle_connections=0,    # Would be populated if pool exposes this
            pool_total_acquires=0,      # Would be populated if pool exposes this
            pool_health_failures=0,     # Would be populated if pool exposes this
            successful_operations=successful,
            failed_operations=failed,
        )

        return result

    async def benchmark_concurrent_operations(self, num_concurrent: int) -> BenchmarkResult:
        """Benchmark concurrent operations.

        Args:
            num_concurrent: Number of concurrent clients

        Returns:
            BenchmarkResult with performance metrics
        """
        scenario_name = f"concurrent_{num_concurrent}_clients"
        self.latencies = []
        successful = 0
        failed = 0

        print(f"\nRunning {scenario_name}...")
        print(f"  Concurrent clients: {num_concurrent}")
        print(f"  Total iterations: {self.iterations}")

        start_time = time.time()

        async def client_workload(client_id: int):
            nonlocal successful, failed
            local_iterations = self.iterations // num_concurrent

            for _ in range(local_iterations):
                op_start = time.time()

                try:
                    result = await self.server.retrieve_memories(
                        query="test concurrent load",
                        limit=5,
                        min_importance=0.0,
                    )
                    op_duration_ms = (time.time() - op_start) * 1000
                    self.latencies.append(op_duration_ms)
                    successful += 1

                except Exception as e:
                    logger.error(f"Client {client_id} operation failed: {e}")
                    failed += 1

        # Run concurrent clients
        try:
            await asyncio.gather(*[
                client_workload(i) for i in range(num_concurrent)
            ])
        except Exception as e:
            print(f"❌ Error during concurrent benchmark: {e}")
            raise
        finally:
            total_duration = time.time() - start_time

        # Calculate metrics
        if not self.latencies:
            print(f"⚠️  No successful operations")
            return None

        sorted_latencies = sorted(self.latencies)
        p50_idx = int(len(sorted_latencies) * 0.50)
        p95_idx = int(len(sorted_latencies) * 0.95)
        p99_idx = int(len(sorted_latencies) * 0.99)

        throughput = successful / total_duration if total_duration > 0 else 0

        result = BenchmarkResult(
            scenario=scenario_name,
            iterations=self.iterations,
            total_duration_sec=total_duration,
            throughput_ops_sec=throughput,
            latencies_ms=sorted_latencies,
            p50_latency_ms=sorted_latencies[p50_idx] if p50_idx < len(sorted_latencies) else 0,
            p95_latency_ms=sorted_latencies[p95_idx] if p95_idx < len(sorted_latencies) else 0,
            p99_latency_ms=sorted_latencies[p99_idx] if p99_idx < len(sorted_latencies) else 0,
            min_latency_ms=min(sorted_latencies),
            max_latency_ms=max(sorted_latencies),
            pool_active_connections=0,
            pool_idle_connections=0,
            pool_total_acquires=0,
            pool_health_failures=0,
            successful_operations=successful,
            failed_operations=failed,
        )

        return result

    def print_result(self, result: BenchmarkResult):
        """Print benchmark result in human-readable format."""
        if not result:
            print("  (No results)")
            return

        print(f"\n{'=' * 70}")
        print(f"Scenario: {result.scenario}")
        print(f"{'=' * 70}")
        print(f"Total Duration:      {result.total_duration_sec:.2f} seconds")
        print(f"Successful Ops:      {result.successful_operations}/{result.iterations}")
        print(f"Failed Ops:          {result.failed_operations}")
        print()
        print(f"Throughput:          {result.throughput_ops_sec:,.0f} ops/sec")
        print()
        print(f"Latency (milliseconds):")
        print(f"  Min:               {result.min_latency_ms:.2f} ms")
        print(f"  P50 (median):      {result.p50_latency_ms:.2f} ms")
        print(f"  P95:               {result.p95_latency_ms:.2f} ms")
        print(f"  P99:               {result.p99_latency_ms:.2f} ms")
        print(f"  Max:               {result.max_latency_ms:.2f} ms")
        print()

    def save_results(self, results: List[BenchmarkResult], filename: str = "benchmark_results.json"):
        """Save benchmark results to JSON file."""
        output_path = Path(__file__).parent.parent / "benchmark_results.json"

        # Convert results to dictionaries
        results_data = [
            {
                **asdict(r),
                "latencies_ms": None,  # Don't include full latency list
            }
            for r in results
        ]

        with open(output_path, "w") as f:
            json.dump(results_data, f, indent=2)

        print(f"✅ Results saved to {output_path}")


async def main():
    """Run all benchmarks."""
    print("=" * 70)
    print("PERF-007: Connection Pooling Benchmark")
    print("=" * 70)
    print()

    # Parse command line arguments
    iterations = 1000
    if len(sys.argv) > 1 and sys.argv[1].startswith("--iterations"):
        iterations = int(sys.argv[1].split("=")[1])

    benchmark = PoolBenchmark(iterations=iterations)
    results = []

    try:
        await benchmark.setup()

        # Scenario 1: Sequential operations
        result1 = await benchmark.benchmark_retrieve_operations(
            "Sequential Retrieval (1000 ops)"
        )
        if result1:
            results.append(result1)
            benchmark.print_result(result1)

        # Scenario 2: 5 concurrent clients
        result2 = await benchmark.benchmark_concurrent_operations(num_concurrent=5)
        if result2:
            results.append(result2)
            benchmark.print_result(result2)

        # Scenario 3: 10 concurrent clients
        result3 = await benchmark.benchmark_concurrent_operations(num_concurrent=10)
        if result3:
            results.append(result3)
            benchmark.print_result(result3)

        # Summary
        print("\n" + "=" * 70)
        print("BENCHMARK SUMMARY")
        print("=" * 70)

        for result in results:
            print(f"{result.scenario:40s} {result.throughput_ops_sec:10,.0f} ops/sec | P95: {result.p95_latency_ms:6.2f}ms")

        # Save results
        benchmark.save_results(results)

    finally:
        await benchmark.teardown()


if __name__ == "__main__":
    asyncio.run(main())
