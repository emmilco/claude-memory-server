#!/usr/bin/env python3
"""Performance benchmark script for Claude Memory RAG server."""

import asyncio
import time
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import ServerConfig
from src.core.server import MemoryRAGServer
from src.embeddings.generator import EmbeddingGenerator


async def benchmark_embedding_generation():
    """Benchmark embedding generation throughput."""
    print("\n" + "=" * 60)
    print("BENCHMARK: Embedding Generation")
    print("=" * 60)

    config = ServerConfig()
    generator = EmbeddingGenerator(config)

    # Test texts
    test_texts = [
        f"This is test document number {i} for benchmarking embedding generation."
        for i in range(200)
    ]

    # Warm up
    print("Warming up...")
    await generator.generate(test_texts[0])

    # Benchmark single embedding
    print("\n1. Single Embedding Generation:")
    start = time.time()
    await generator.generate(test_texts[0])
    single_time = time.time() - start
    print(f"   Time: {single_time * 1000:.2f}ms")

    # Benchmark batch generation
    print("\n2. Batch Embedding Generation (200 docs):")
    start = time.time()
    await generator.batch_generate(test_texts)
    batch_time = time.time() - start

    throughput = len(test_texts) / batch_time
    avg_time = (batch_time / len(test_texts)) * 1000

    print(f"   Total time: {batch_time:.2f}s")
    print(f"   Average per doc: {avg_time:.2f}ms")
    print(f"   Throughput: {throughput:.1f} docs/sec")
    print("   Target: 100+ docs/sec")
    print(f"   Status: {'✅ PASS' if throughput >= 100 else '❌ FAIL'}")

    # Test with Rust
    print("\n3. Rust Acceleration:")
    from src.embeddings.rust_bridge import RustBridge

    if RustBridge.is_rust_available():
        print("   Rust module: ✅ Available")

        # Benchmark normalization
        test_vectors = [[float(i) for i in range(384)] for _ in range(1000)]

        # Python baseline
        start = time.time()
        for _ in range(10):
            from src.embeddings.rust_bridge import batch_normalize_embeddings_python

            batch_normalize_embeddings_python(test_vectors)
        python_time = time.time() - start

        # Rust version
        start = time.time()
        for _ in range(10):
            RustBridge.batch_normalize(test_vectors)
        rust_time = time.time() - start

        speedup = python_time / rust_time
        print(f"   Python time: {python_time * 1000:.2f}ms")
        print(f"   Rust time: {rust_time * 1000:.2f}ms")
        print(f"   Speedup: {speedup:.1f}x")
        print("   Target: 10-50x speedup")
        print(f"   Status: {'✅ PASS' if speedup >= 10 else '❌ FAIL'}")
    else:
        print("   Rust module: ❌ Not available (using Python fallback)")

    await generator.close()
    return {
        "throughput": throughput,
        "avg_time_ms": avg_time,
        "rust_available": RustBridge.is_rust_available(),
    }


async def benchmark_vector_search():
    """Benchmark vector search performance."""
    print("\n" + "=" * 60)
    print("BENCHMARK: Vector Search (Qdrant)")
    print("=" * 60)

    config = ServerConfig(storage_backend="qdrant")
    server = MemoryRAGServer(config)
    await server.initialize()

    # Store test memories
    print("\n1. Storing test dataset...")
    num_docs = 1000
    print(f"   Storing {num_docs} test documents...")

    start = time.time()
    for i in range(num_docs):
        await server.store_memory(
            content=f"Test document {i}: This document contains information about topic {i % 10}.",
            category="fact",
            scope="global",
            importance=0.5 + (i % 5) * 0.1,
        )

        if (i + 1) % 100 == 0:
            print(f"   Stored {i + 1}/{num_docs}...")

    store_time = time.time() - start
    store_throughput = num_docs / store_time

    print(f"\n   Total storage time: {store_time:.2f}s")
    print(f"   Storage throughput: {store_throughput:.1f} docs/sec")

    # Benchmark queries
    print("\n2. Query Performance:")

    # Warm up
    await server.retrieve_memories("test query", limit=5)

    # Test various query sizes
    test_queries = [
        ("topic 5", 5),
        ("document information", 10),
        ("test", 20),
    ]

    query_times = []
    for query, limit in test_queries:
        start = time.time()
        results = await server.retrieve_memories(query, limit=limit)
        query_time = (time.time() - start) * 1000  # Convert to ms

        query_times.append(query_time)
        print(f"   Query: '{query}' (limit={limit})")
        print(f"     Time: {query_time:.2f}ms")
        print(f"     Results: {results['total_found']}")

    avg_query_time = sum(query_times) / len(query_times)
    print(f"\n   Average query time: {avg_query_time:.2f}ms")
    print("   Target: <50ms for 10K docs")
    print(f"   Dataset size: {num_docs} docs (1K)")
    print(f"   Status: {'✅ PASS' if avg_query_time < 50 else '❌ FAIL'}")

    # Benchmark filtered search
    print("\n3. Filtered Search Performance:")
    start = time.time()
    results = await server.retrieve_memories(
        "topic",
        limit=10,
        min_importance=0.7,
        category="fact",
    )
    filtered_time = (time.time() - start) * 1000

    print(f"   Time with filters: {filtered_time:.2f}ms")
    print(f"   Results: {results['total_found']}")

    await server.close()
    return {
        "store_throughput": store_throughput,
        "avg_query_time_ms": avg_query_time,
        "dataset_size": num_docs,
    }


async def benchmark_cache_performance():
    """Benchmark embedding cache hit rate."""
    print("\n" + "=" * 60)
    print("BENCHMARK: Embedding Cache")
    print("=" * 60)

    from src.embeddings.cache import EmbeddingCache

    config = ServerConfig(embedding_cache_enabled=True)
    cache = EmbeddingCache(config)

    # Clear cache
    await cache.clear()

    # Test cache operations
    test_texts = [f"Cache test text {i}" for i in range(50)]

    # First pass - cache misses
    print("\n1. First pass (cache misses):")
    start = time.time()
    for text in test_texts:
        await cache.get(text, "all-MiniLM-L6-v2")
    first_pass_time = time.time() - start

    # Populate cache
    print("\n2. Populating cache...")
    test_embedding = [0.1] * 384
    for text in test_texts:
        await cache.set(text, "all-MiniLM-L6-v2", test_embedding)

    # Second pass - cache hits
    print("\n3. Second pass (cache hits):")
    start = time.time()
    for text in test_texts:
        cached = await cache.get(text, "all-MiniLM-L6-v2")
        assert cached is not None
    second_pass_time = time.time() - start

    speedup = (
        first_pass_time / second_pass_time if second_pass_time > 0 else float("inf")
    )

    stats = cache.get_stats()
    hit_rate = stats["hit_rate"]

    print(f"\n   First pass time: {first_pass_time * 1000:.2f}ms")
    print(f"   Second pass time: {second_pass_time * 1000:.2f}ms")
    print(f"   Speedup: {speedup:.1f}x")
    print(f"   Hit rate: {hit_rate * 100:.1f}%")
    print(f"   Cache entries: {stats['total_entries']}")
    print("   Target hit rate: 90%+")
    print(f"   Status: {'✅ PASS' if hit_rate >= 0.9 else '❌ FAIL'}")

    cache.close()
    return {
        "hit_rate": hit_rate,
        "speedup": speedup,
        "cache_entries": stats["total_entries"],
    }


async def benchmark_specialized_tools():
    """Benchmark specialized retrieval tools."""
    print("\n" + "=" * 60)
    print("BENCHMARK: Specialized Retrieval Tools")
    print("=" * 60)

    config = ServerConfig()
    server = MemoryRAGServer(config)
    await server.initialize()

    # Store diverse memories
    print("\n1. Storing diverse test data...")
    categories = [
        ("preference", "USER_PREFERENCE"),
        ("fact", "PROJECT_CONTEXT"),
        ("context", "SESSION_STATE"),
    ]

    for i in range(30):
        category, _ = categories[i % 3]
        await server.store_memory(
            content=f"Specialized tool test {i}",
            category=category,
            scope="project" if category != "preference" else "global",
            project_name="test-project" if category != "preference" else None,
        )

    # Benchmark specialized retrievals
    print("\n2. Specialized Tool Performance:")

    tools = [
        ("retrieve_preferences", server.retrieve_preferences),
        (
            "retrieve_project_context",
            lambda q, **kw: server.retrieve_project_context(
                q, use_current_project=False, **kw
            ),
        ),
        ("retrieve_session_state", server.retrieve_session_state),
    ]

    for name, tool_func in tools:
        start = time.time()
        results = await tool_func("test", limit=10)
        tool_time = (time.time() - start) * 1000

        print(f"   {name}:")
        print(f"     Time: {tool_time:.2f}ms")
        print(f"     Results: {results['total_found']}")

    await server.close()


async def main():
    """Run all benchmarks."""
    print("\n" + "=" * 60)
    print("CLAUDE MEMORY RAG - PERFORMANCE BENCHMARK SUITE")
    print("=" * 60)

    results = {}

    try:
        # Embedding generation
        results["embeddings"] = await benchmark_embedding_generation()

        # Vector search
        results["search"] = await benchmark_vector_search()

        # Cache performance
        results["cache"] = await benchmark_cache_performance()

        # Specialized tools
        await benchmark_specialized_tools()

        # Summary
        print("\n" + "=" * 60)
        print("BENCHMARK SUMMARY")
        print("=" * 60)

        print("\n✅ Embedding Generation:")
        print(f"   Throughput: {results['embeddings']['throughput']:.1f} docs/sec")
        print(f"   Rust available: {results['embeddings']['rust_available']}")

        print("\n✅ Vector Search:")
        print(f"   Storage: {results['search']['store_throughput']:.1f} docs/sec")
        print(f"   Query latency: {results['search']['avg_query_time_ms']:.2f}ms")

        print("\n✅ Embedding Cache:")
        print(f"   Hit rate: {results['cache']['hit_rate'] * 100:.1f}%")
        print(f"   Speedup: {results['cache']['speedup']:.1f}x")

        print("\n" + "=" * 60)
        print("ALL BENCHMARKS COMPLETED")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ Benchmark failed: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
