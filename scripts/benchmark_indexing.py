#!/usr/bin/env python3
"""Comprehensive performance benchmark for code indexing system."""

import asyncio
import logging
import time
from pathlib import Path
from collections import defaultdict
import json

from src.memory.incremental_indexer import IncrementalIndexer
from src.store.qdrant_store import QdrantMemoryStore
from src.embeddings.generator import EmbeddingGenerator
from src.config import ServerConfig
from src.core.models import SearchFilters, MemoryScope

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class PerformanceBenchmark:
    """Benchmark suite for code indexing system."""

    def __init__(self, project_name: str = "claude-memory-benchmark"):
        """Initialize benchmark."""
        self.project_name = project_name
        self.config = ServerConfig(
            qdrant_collection_name=f"benchmark_{int(time.time())}",
            embedding_model="all-MiniLM-L6-v2",
        )

        self.store = QdrantMemoryStore(self.config)
        self.embedding_gen = EmbeddingGenerator(self.config)
        self.indexer = IncrementalIndexer(
            store=self.store,
            embedding_generator=self.embedding_gen,
            config=self.config,
            project_name=self.project_name,
        )

        self.metrics = {
            "indexing": {},
            "search": {},
            "files": {},
        }

    async def initialize(self):
        """Initialize components."""
        await self.indexer.initialize()
        logger.info("Benchmark initialized")

    async def benchmark_indexing(self, directory: Path) -> dict:
        """Benchmark indexing performance."""
        logger.info(f"\n{'='*60}")
        logger.info("BENCHMARKING: Full Directory Indexing")
        logger.info(f"{'='*60}\n")

        start_time = time.time()

        # Index entire directory
        result = await self.indexer.index_directory(
            directory,
            recursive=True,
            show_progress=True,
        )

        total_time = time.time() - start_time

        # Calculate metrics
        metrics = {
            "total_files": result["total_files"],
            "indexed_files": result["indexed_files"],
            "skipped_files": result["skipped_files"],
            "failed_files": len(result.get("failed_files", [])),
            "total_units": result["total_units"],
            "total_time_sec": total_time,
            "files_per_sec": result["indexed_files"] / total_time
            if total_time > 0
            else 0,
            "units_per_sec": result["total_units"] / total_time
            if total_time > 0
            else 0,
            "avg_time_per_file_ms": (total_time * 1000) / result["indexed_files"]
            if result["indexed_files"] > 0
            else 0,
        }

        self.metrics["indexing"] = metrics

        # Print summary
        print(f"\n{'='*60}")
        print("INDEXING BENCHMARK RESULTS")
        print(f"{'='*60}")
        print(f"Total files found:      {metrics['total_files']}")
        print(f"Files indexed:          {metrics['indexed_files']}")
        print(f"Files skipped:          {metrics['skipped_files']}")
        print(f"Files failed:           {metrics['failed_files']}")
        print(f"Semantic units:         {metrics['total_units']}")
        print(f"Total time:             {metrics['total_time_sec']:.2f}s")
        print(f"Throughput:             {metrics['files_per_sec']:.2f} files/sec")
        print(f"                        {metrics['units_per_sec']:.2f} units/sec")
        print(f"Avg per file:           {metrics['avg_time_per_file_ms']:.2f}ms")
        print(f"{'='*60}\n")

        return metrics

    async def benchmark_search(self, queries: list[str]) -> dict:
        """Benchmark search performance."""
        logger.info(f"\n{'='*60}")
        logger.info("BENCHMARKING: Semantic Search")
        logger.info(f"{'='*60}\n")

        search_results = []
        total_search_time = 0

        for query in queries:
            print(f"\nQuery: '{query}'")
            print("-" * 60)

            # Time embedding generation
            embed_start = time.time()
            query_embedding = await self.embedding_gen.generate(query)
            embed_time = time.time() - embed_start

            # Time search
            search_start = time.time()
            filters = SearchFilters(
                scope=MemoryScope.PROJECT,
                project_name=self.project_name,
            )
            results = await self.store.retrieve(
                query_embedding=query_embedding,
                filters=filters,
                limit=5,
            )
            search_time = time.time() - search_start
            total_time = embed_time + search_time

            total_search_time += total_time

            # Display results
            print(f"Found {len(results)} results in {total_time*1000:.2f}ms")
            print(
                f"  (Embed: {embed_time*1000:.2f}ms, Search: {search_time*1000:.2f}ms)\n"
            )

            for i, (memory, score) in enumerate(results[:3], 1):
                meta = memory.metadata if hasattr(memory, "metadata") else {}
                unit_name = meta.get("unit_name", "unknown")
                unit_type = meta.get("unit_type", "unknown")
                file_path = meta.get("file_path", "unknown")
                start_line = meta.get("start_line", 0)

                print(f"  {i}. {unit_name} ({unit_type}) - Score: {score:.4f}")
                print(f"     {Path(file_path).name}:{start_line}")

            print()

            search_results.append(
                {
                    "query": query,
                    "results_count": len(results),
                    "embed_time_ms": embed_time * 1000,
                    "search_time_ms": search_time * 1000,
                    "total_time_ms": total_time * 1000,
                    "top_score": results[0][1] if results else 0.0,
                }
            )

        # Calculate metrics
        metrics = {
            "num_queries": len(queries),
            "total_search_time_sec": total_search_time,
            "avg_search_time_ms": (total_search_time * 1000) / len(queries),
            "queries": search_results,
        }

        self.metrics["search"] = metrics

        print(f"\n{'='*60}")
        print("SEARCH BENCHMARK RESULTS")
        print(f"{'='*60}")
        print(f"Total queries:          {metrics['num_queries']}")
        print(f"Total time:             {metrics['total_search_time_sec']:.3f}s")
        print(f"Avg per query:          {metrics['avg_search_time_ms']:.2f}ms")
        print(f"{'='*60}\n")

        return metrics

    async def analyze_indexed_code(self) -> dict:
        """Analyze what was indexed."""
        logger.info(f"\n{'='*60}")
        logger.info("ANALYZING: Indexed Code")
        logger.info(f"{'='*60}\n")

        # Get all indexed points
        # Note: This is just for analysis, not production-scale retrieval
        zero_vector = [0.0] * 384
        filters = SearchFilters(
            scope=MemoryScope.PROJECT,
            project_name=self.project_name,
        )

        # Get a sample
        results = await self.store.retrieve(
            query_embedding=zero_vector,
            filters=filters,
            limit=100,  # Sample size
        )

        # Analyze by language, type, etc.
        by_language = defaultdict(int)
        by_type = defaultdict(int)
        by_file = defaultdict(int)

        for memory, _ in results:
            meta = memory.metadata if hasattr(memory, "metadata") else {}
            language = meta.get("language", "unknown")
            unit_type = meta.get("unit_type", "unknown")
            file_path = meta.get("file_path", "unknown")

            by_language[language] += 1
            by_type[unit_type] += 1
            by_file[Path(file_path).name] += 1

        metrics = {
            "by_language": dict(by_language),
            "by_type": dict(by_type),
            "top_files": dict(
                sorted(by_file.items(), key=lambda x: x[1], reverse=True)[:10]
            ),
        }

        self.metrics["files"] = metrics

        print("Code Distribution:")
        print("\nBy Language:")
        for lang, count in sorted(
            by_language.items(), key=lambda x: x[1], reverse=True
        ):
            print(f"  {lang}: {count}")

        print("\nBy Type:")
        for utype, count in sorted(by_type.items(), key=lambda x: x[1], reverse=True):
            print(f"  {utype}: {count}")

        print("\nTop 10 Files by Unit Count:")
        for fname, count in list(
            sorted(by_file.items(), key=lambda x: x[1], reverse=True)
        )[:10]:
            print(f"  {fname}: {count}")

        print()

        return metrics

    async def cleanup(self):
        """Clean up resources."""
        await self.indexer.close()

        # Delete benchmark collection
        if self.store.client:
            try:
                self.store.client.delete_collection(self.config.qdrant_collection_name)
                logger.info(
                    f"Deleted benchmark collection: {self.config.qdrant_collection_name}"
                )
            except Exception as e:
                logger.warning(f"Failed to delete collection: {e}")

    def save_report(self, filename: str = "benchmark_report.json"):
        """Save benchmark report to file."""
        with open(filename, "w") as f:
            json.dump(self.metrics, f, indent=2)
        logger.info(f"Benchmark report saved to {filename}")


async def main():
    """Run benchmark suite."""
    print("\n" + "=" * 60)
    print("CODE INDEXING PERFORMANCE BENCHMARK")
    print("=" * 60 + "\n")

    # Directory to index
    index_dir = Path("src")

    if not index_dir.exists():
        print(f"Error: Directory {index_dir} does not exist")
        return

    benchmark = PerformanceBenchmark()

    try:
        # Initialize
        await benchmark.initialize()

        # 1. Benchmark indexing
        await benchmark.benchmark_indexing(index_dir)

        # 2. Benchmark search
        test_queries = [
            "memory storage and retrieval",
            "embedding generation",
            "vector database connection",
            "configuration settings",
            "error handling and exceptions",
            "file watcher and monitoring",
            "parse source code",
            "batch processing",
            "authentication and security",
            "data validation",
        ]

        await benchmark.benchmark_search(test_queries)

        # 3. Analyze indexed code
        await benchmark.analyze_indexed_code()

        # Save report
        benchmark.save_report("benchmark_report.json")

        print(f"\n{'='*60}")
        print("BENCHMARK COMPLETE")
        print(f"{'='*60}")
        print("\nDetailed results saved to: benchmark_report.json\n")

    finally:
        await benchmark.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
