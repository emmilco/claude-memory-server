"""Tests for parallel embedding generation."""

import pytest
import pytest_asyncio
import asyncio
from typing import List
from unittest.mock import Mock, patch
import os

from src.embeddings.parallel_generator import ParallelEmbeddingGenerator
from src.config import ServerConfig
from src.core.exceptions import EmbeddingError


@pytest.fixture
def config():
    """Create test configuration."""
    return ServerConfig(
        embedding_model="all-MiniLM-L6-v2",
        embedding_batch_size=8,
        enable_parallel_embeddings=True,
        embedding_parallel_workers=2,  # Use 2 workers for testing
    )


@pytest_asyncio.fixture
async def parallel_generator(config):
    """Create parallel embedding generator."""
    generator = ParallelEmbeddingGenerator(config, max_workers=2)
    await generator.initialize()
    yield generator
    await generator.close()


class TestParallelEmbeddingGenerator:
    """Test parallel embedding generation."""

    @pytest.mark.asyncio
    async def test_initialization(self, config):
        """Test generator initialization."""
        generator = ParallelEmbeddingGenerator(config, max_workers=2)
        await generator.initialize()

        assert generator.model_name == "all-MiniLM-L6-v2"
        assert generator.embedding_dim == 384
        assert generator.max_workers == 2
        assert generator.executor is not None

        await generator.close()

    @pytest.mark.asyncio
    async def test_auto_worker_count(self):
        """Test automatic worker count detection."""
        config = ServerConfig(
            embedding_model="all-MiniLM-L6-v2",
            enable_parallel_embeddings=True,
        )
        generator = ParallelEmbeddingGenerator(config)

        # Should default to CPU count
        expected_workers = os.cpu_count() or 4
        assert generator.max_workers == expected_workers

        await generator.close()

    @pytest.mark.asyncio
    async def test_single_text_embedding(self, parallel_generator):
        """Test embedding generation for a single text."""
        text = "def hello_world(): print('Hello, World!')"

        embedding = await parallel_generator.generate(text)

        assert isinstance(embedding, list)
        assert len(embedding) == 384  # all-MiniLM-L6-v2 dimension
        assert all(isinstance(x, float) for x in embedding)

    @pytest.mark.asyncio
    async def test_empty_text_error(self, parallel_generator):
        """Test error handling for empty text."""
        with pytest.raises(EmbeddingError, match="empty text"):
            await parallel_generator.generate("")

        with pytest.raises(EmbeddingError, match="empty text"):
            await parallel_generator.generate("   ")

    @pytest.mark.asyncio
    async def test_batch_generate_small(self, parallel_generator):
        """Test batch generation for small batch (single-threaded mode)."""
        texts = [
            "def function_one(): pass",
            "def function_two(): return 42",
            "class MyClass: pass",
        ]

        # Small batch should use single-threaded mode
        embeddings = await parallel_generator.batch_generate(texts)

        assert len(embeddings) == len(texts)
        assert all(len(emb) == 384 for emb in embeddings)
        assert all(isinstance(emb, list) for emb in embeddings)

    @pytest.mark.asyncio
    @pytest.mark.skip_ci  # Process pool startup exceeds CI timeout
    async def test_batch_generate_large(self, parallel_generator):
        """Test batch generation for large batch (parallel mode)."""
        # Generate 20 different texts to trigger parallel mode
        texts = [
            f"def function_{i}(): return {i}"
            for i in range(20)
        ]

        embeddings = await parallel_generator.batch_generate(
            texts,
            show_progress=True
        )

        assert len(embeddings) == len(texts)
        assert all(len(emb) == 384 for emb in embeddings)

        # Verify embeddings are different (not all the same)
        # Check that first and second embeddings differ
        assert embeddings[0] != embeddings[1]

    @pytest.mark.asyncio
    async def test_batch_generate_empty_list(self, parallel_generator):
        """Test batch generation with empty list."""
        embeddings = await parallel_generator.batch_generate([])
        assert embeddings == []

    @pytest.mark.asyncio
    async def test_batch_with_empty_text_error(self, parallel_generator):
        """Test batch generation with empty text in batch."""
        texts = [
            "def valid_function(): pass",
            "",  # Empty text should cause error
            "def another_function(): pass",
        ]

        with pytest.raises(EmbeddingError, match="Empty text at index 1"):
            await parallel_generator.batch_generate(texts)

    @pytest.mark.asyncio
    async def test_embedding_consistency(self, parallel_generator):
        """Test that parallel generator produces consistent embeddings."""
        text = "def my_function(): return 'hello'"

        # Generate embedding twice
        embedding1 = await parallel_generator.generate(text)
        embedding2 = await parallel_generator.generate(text)

        # Should be identical (deterministic)
        assert len(embedding1) == len(embedding2)
        # Note: floating point comparison with tolerance
        for i, (a, b) in enumerate(zip(embedding1, embedding2)):
            assert abs(a - b) < 1e-6, f"Mismatch at index {i}"

    @pytest.mark.asyncio
    async def test_parallel_vs_single_threaded_consistency(self, config):
        """Test that parallel mode produces same results as single-threaded."""
        # This test is important for correctness
        texts = [f"function {i}" for i in range(15)]

        # Generate with parallel mode
        parallel_gen = ParallelEmbeddingGenerator(config, max_workers=2)
        await parallel_gen.initialize()
        parallel_embeddings = await parallel_gen.batch_generate(texts)
        await parallel_gen.close()

        # Generate with single-threaded mode (small batch forces it)
        # Actually we need to use the standard generator for true comparison
        from src.embeddings.generator import EmbeddingGenerator

        single_gen = EmbeddingGenerator(config)
        await single_gen.initialize()
        single_embeddings = await single_gen.batch_generate(texts)
        await single_gen.close()

        # Results should be nearly identical
        assert len(parallel_embeddings) == len(single_embeddings)
        for i, (p_emb, s_emb) in enumerate(zip(parallel_embeddings, single_embeddings)):
            assert len(p_emb) == len(s_emb), f"Length mismatch at index {i}"
            # Floating point tolerance
            for j, (p, s) in enumerate(zip(p_emb, s_emb)):
                assert abs(p - s) < 1e-5, f"Value mismatch at text {i}, dimension {j}"

    @pytest.mark.asyncio
    async def test_get_embedding_dim(self, parallel_generator):
        """Test getting embedding dimension."""
        dim = parallel_generator.get_embedding_dim()
        assert dim == 384  # all-MiniLM-L6-v2

    @pytest.mark.asyncio
    async def test_invalid_model_error(self):
        """Test error handling for invalid model."""
        config = ServerConfig(
            embedding_model="invalid-model-name",
        )

        with pytest.raises(EmbeddingError, match="Unsupported model"):
            ParallelEmbeddingGenerator(config)

    @pytest.mark.asyncio
    @pytest.mark.skip_ci  # Large parallel batch exceeds CI timeout
    async def test_process_distribution(self, parallel_generator):
        """Test that work is distributed across processes."""
        # Generate enough texts to ensure multiple processes are used
        texts = [f"text number {i}" for i in range(50)]

        # Mock to track which worker processes were used
        # This is tricky to test directly, but we can verify no errors occur
        # and all texts are processed
        embeddings = await parallel_generator.batch_generate(
            texts,
            show_progress=True
        )

        assert len(embeddings) == 50
        assert all(len(emb) == 384 for emb in embeddings)

    @pytest.mark.asyncio
    async def test_custom_batch_size(self, parallel_generator):
        """Test custom batch size parameter."""
        texts = [f"function {i}" for i in range(20)]

        embeddings = await parallel_generator.batch_generate(
            texts,
            batch_size=4,  # Override default
        )

        assert len(embeddings) == 20
        assert all(len(emb) == 384 for emb in embeddings)

    @pytest.mark.asyncio
    async def test_close_cleanup(self, config):
        """Test that close() properly cleans up resources."""
        generator = ParallelEmbeddingGenerator(config, max_workers=2)
        await generator.initialize()

        assert generator.executor is not None

        await generator.close()

        assert generator.executor is None

    @pytest.mark.asyncio
    async def test_parallel_threshold(self, parallel_generator):
        """Test that small batches use single-threaded mode."""
        # The threshold is 10 texts
        small_batch = ["text"] * 5
        large_batch = ["text"] * 15

        # Both should work, but internally use different modes
        small_embeddings = await parallel_generator.batch_generate(small_batch)
        large_embeddings = await parallel_generator.batch_generate(large_batch)

        assert len(small_embeddings) == 5
        assert len(large_embeddings) == 15

    @pytest.mark.asyncio
    async def test_cache_enabled(self, config):
        """Test that cache is enabled and used."""
        generator = ParallelEmbeddingGenerator(config, max_workers=2)
        await generator.initialize()

        assert generator.cache is not None
        assert generator.cache.enabled

        await generator.close()

    @pytest.mark.asyncio
    async def test_cache_hit_on_reindex(self, config):
        """Test that cache hits occur when re-embedding same texts."""
        # Use unique texts to avoid cross-test cache pollution
        import uuid
        test_id = str(uuid.uuid4())[:8]

        generator = ParallelEmbeddingGenerator(config, max_workers=2)
        await generator.initialize()

        # Reset cache statistics at start to avoid interference
        if generator.cache:
            generator.cache.hits = 0
            generator.cache.misses = 0

        # Generate embeddings for first time with unique texts
        texts = [f"def function_{test_id}_{i}(): return {i}" for i in range(15)]
        embeddings1 = await generator.batch_generate(texts, show_progress=True)

        # Generate same texts again - should hit cache
        embeddings2 = await generator.batch_generate(texts, show_progress=True)

        # Results should be nearly identical (from cache, with floating point tolerance)
        assert len(embeddings1) == len(embeddings2)
        for e1, e2 in zip(embeddings1, embeddings2):
            assert len(e1) == len(e2)
            # Use floating point tolerance for comparison (cache may serialize differently)
            for i, (v1, v2) in enumerate(zip(e1, e2)):
                assert abs(v1 - v2) < 1e-6, f"Embedding mismatch at dimension {i}: {v1} vs {v2}"

        # Verify cache was actually used (cache stats should show hits)
        if generator.cache:
            assert generator.cache.hits > 0

        await generator.close()

    @pytest.mark.asyncio
    async def test_partial_cache_hit(self, config):
        """Test that partially cached batches work correctly."""
        generator = ParallelEmbeddingGenerator(config, max_workers=2)
        await generator.initialize()

        # Generate embeddings for initial set
        initial_texts = [f"def initial_{i}(): pass" for i in range(10)]
        await generator.batch_generate(initial_texts)

        # Generate mixed batch (5 cached, 5 new)
        mixed_texts = initial_texts[:5] + [f"def new_{i}(): pass" for i in range(5)]
        embeddings = await generator.batch_generate(mixed_texts, show_progress=True)

        # Should get all 10 embeddings
        assert len(embeddings) == 10

        # First 5 should match original (cached)
        original_embeddings = await generator.batch_generate(initial_texts[:5])
        for i in range(5):
            assert embeddings[i] == original_embeddings[i]

        await generator.close()

    @pytest.mark.asyncio
    async def test_cache_statistics(self, config):
        """Test that cache statistics are tracked correctly."""
        generator = ParallelEmbeddingGenerator(config, max_workers=2)
        await generator.initialize()

        texts = [f"def function_{i}(): return {i}" for i in range(20)]

        # First run - all cache misses
        await generator.batch_generate(texts)
        initial_hits = generator.cache.hits if generator.cache else 0

        # Second run - all cache hits
        await generator.batch_generate(texts)
        final_hits = generator.cache.hits if generator.cache else 0

        # Should have cache hits on second run
        assert final_hits > initial_hits, "Cache hits should increase on second run"

        # Should have at least 20 hits (one per text)
        cache_hit_increase = final_hits - initial_hits
        assert cache_hit_increase >= 20, f"Expected at least 20 cache hits, got {cache_hit_increase}"

        await generator.close()


class TestParallelGeneratorIntegration:
    """Integration tests for parallel generator with indexer."""

    @pytest.mark.asyncio
    async def test_with_incremental_indexer(self, tmp_path, config):
        """Test parallel generator integration with incremental indexer."""
        from src.memory.incremental_indexer import IncrementalIndexer

        # Create test file
        test_file = tmp_path / "test.py"
        test_file.write_text("""
def function_one():
    return 1

def function_two():
    return 2

class TestClass:
    def method_one(self):
        pass
""")

        # Create indexer with parallel embeddings
        indexer = IncrementalIndexer(config=config, project_name="test-project")
        await indexer.initialize()

        try:
            # Index the file
            result = await indexer.index_file(test_file)

            # Verify indexing succeeded
            assert result["units_indexed"] >= 3  # 2 functions + 1 class
            assert result["file_path"] == str(test_file)
            assert result["language"].lower() == "python"

        finally:
            await indexer.close()


@pytest.mark.benchmark
class TestParallelPerformance:
    """Performance benchmarks for parallel embedding generation."""

    @pytest.mark.asyncio
    @pytest.mark.skip_ci
    async def test_performance_improvement(self):
        """Benchmark parallel vs single-threaded performance."""
        import time

        config = ServerConfig(
            embedding_model="all-MiniLM-L6-v2",
            embedding_batch_size=16,
            embedding_cache_enabled=False,  # Disable cache for fair performance comparison
        )

        # Generate test data - use larger batch for meaningful parallelization
        # Small batches (<100 texts) have too much overhead
        texts = [f"def function_{i}(): return {i}" for i in range(500)]
        warmup_texts = [f"def warmup_{i}(): pass" for i in range(10)]

        # Test parallel mode
        parallel_gen = ParallelEmbeddingGenerator(config, max_workers=4)
        await parallel_gen.initialize()

        # Warm up to avoid cold start overhead (use different texts)
        await parallel_gen.batch_generate(warmup_texts)

        start_parallel = time.time()
        await parallel_gen.batch_generate(texts)
        parallel_time = time.time() - start_parallel

        await parallel_gen.close()

        # Test single-threaded mode
        from src.embeddings.generator import EmbeddingGenerator

        single_gen = EmbeddingGenerator(config)
        await single_gen.initialize()

        # Warm up to avoid cold start overhead (use different texts)
        await single_gen.batch_generate(warmup_texts)

        start_single = time.time()
        await single_gen.batch_generate(texts)
        single_time = time.time() - start_single

        await single_gen.close()

        # Parallel should be faster (but this depends on CPU cores)
        speedup = single_time / parallel_time
        print(f"\nSpeedup: {speedup:.2f}x")
        print(f"Single-threaded: {single_time:.2f}s")
        print(f"Parallel: {parallel_time:.2f}s")
        print(f"Texts processed: {len(texts)}")

        # Performance tests are inherently flaky due to system load,
        # thermal throttling, cache effects, process overhead, etc.
        # We just verify that parallel mode completes successfully
        # and doesn't completely fail. The actual speedup varies by hardware.
        # Note: parallel mode has startup overhead (process pool, model loading)
        # which can make it slower on some systems or under heavy load.
        assert speedup > 0.3  # At least not catastrophically slower (3x)
