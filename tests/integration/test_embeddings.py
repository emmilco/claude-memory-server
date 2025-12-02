"""Integration tests for embedding generation."""

import pytest
import pytest_asyncio

from src.config import ServerConfig
from src.embeddings.generator import EmbeddingGenerator
from src.embeddings.cache import EmbeddingCache


@pytest.fixture
def config():
    """Create test configuration."""
    return ServerConfig(
        embedding_model="all-MiniLM-L6-v2",
        embedding_batch_size=32,
        embedding_cache_enabled=True,
    )


@pytest_asyncio.fixture
async def generator(config):
    """Create embedding generator."""
    gen = EmbeddingGenerator(config)
    yield gen
    await gen.close()


@pytest_asyncio.fixture
async def cache(config):
    """Create embedding cache."""
    cache = EmbeddingCache(config)
    # Clear cache before test
    await cache.clear()
    yield cache
    cache.close()


@pytest.mark.asyncio
async def test_generate_single_embedding(generator):
    """Test generating a single embedding."""
    text = "This is a test sentence for embedding generation."
    embedding = await generator.generate(text)

    # Check embedding properties
    assert isinstance(embedding, list)
    assert len(embedding) == 384  # MiniLM-L6-v2 dimension
    assert all(isinstance(x, float) for x in embedding)

    # Check normalization (L2 norm should be close to 1)
    import math

    norm = math.sqrt(sum(x * x for x in embedding))
    assert abs(norm - 1.0) < 0.01  # Should be normalized


@pytest.mark.asyncio
async def test_batch_generate_embeddings(generator):
    """Test batch embedding generation."""
    texts = [
        "First test sentence.",
        "Second test sentence about Python.",
        "Third sentence discussing machine learning.",
    ]

    embeddings = await generator.batch_generate(texts)

    assert len(embeddings) == len(texts)
    assert all(len(emb) == 384 for emb in embeddings)

    # Different texts should have different embeddings
    assert embeddings[0] != embeddings[1]
    assert embeddings[1] != embeddings[2]


@pytest.mark.asyncio
async def test_embedding_deterministic(generator):
    """Test that same text produces same embedding."""
    text = "Deterministic test sentence."

    embedding1 = await generator.generate(text)
    embedding2 = await generator.generate(text)

    # Should be identical (or very close due to floating point)
    for v1, v2 in zip(embedding1, embedding2):
        assert abs(v1 - v2) < 1e-6


@pytest.mark.asyncio
async def test_cache_functionality(cache, generator):
    """Test embedding cache stores and retrieves."""
    text = "Test sentence for caching."
    model_name = "all-MiniLM-L6-v2"

    # First request - cache miss
    cached = await cache.get(text, model_name)
    assert cached is None

    # Generate and cache
    embedding = await generator.generate(text)
    await cache.set(text, model_name, embedding)

    # Second request - cache hit
    cached = await cache.get(text, model_name)
    assert cached is not None
    assert len(cached) == 384
    assert cached == embedding


@pytest.mark.asyncio
async def test_cache_statistics(cache, generator):
    """Test cache statistics tracking."""
    texts = ["Sentence one.", "Sentence two.", "Sentence one."]  # Repeat first
    model_name = "all-MiniLM-L6-v2"

    for text in texts:
        cached = await cache.get(text, model_name)
        if cached is None:
            embedding = await generator.generate(text)
            await cache.set(text, model_name, embedding)

    stats = cache.get_stats()
    assert stats["enabled"] is True
    assert stats["hits"] == 1  # Third request was a hit
    assert stats["misses"] == 2  # First two were misses
    assert stats["total_entries"] >= 2


@pytest.mark.asyncio
async def test_large_batch_processing(generator):
    """Test processing a larger batch of texts."""
    # Generate 100 test sentences
    texts = [f"Test sentence number {i} about various topics." for i in range(100)]

    embeddings = await generator.batch_generate(texts, show_progress=False)

    assert len(embeddings) == 100
    assert all(len(emb) == 384 for emb in embeddings)


@pytest.mark.asyncio
async def test_empty_text_handling(generator):
    """Test that empty text raises appropriate error."""
    from src.core.exceptions import EmbeddingError

    with pytest.raises(EmbeddingError, match="empty text"):
        await generator.generate("")

    with pytest.raises(EmbeddingError, match="empty text"):
        await generator.generate("   ")


@pytest.mark.asyncio
async def test_benchmark(generator):
    """Test benchmark functionality."""
    results = await generator.benchmark(num_texts=10)

    assert "model" in results
    assert results["model"] == "all-MiniLM-L6-v2"
    assert results["num_texts"] == 10
    assert results["single_embedding_ms"] > 0
    assert results["batch_total_s"] > 0
    assert results["throughput_docs_per_sec"] > 0

    print("\nBenchmark Results:")
    print(f"  Model: {results['model']}")
    print(f"  Single embedding: {results['single_embedding_ms']:.2f}ms")
    print(f"  Batch throughput: {results['throughput_docs_per_sec']:.1f} docs/sec")
    print(f"  Rust available: {results['rust_available']}")
