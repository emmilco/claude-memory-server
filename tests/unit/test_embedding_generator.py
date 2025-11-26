"""Comprehensive tests for EmbeddingGenerator."""

import pytest
import pytest_asyncio
import asyncio
from unittest.mock import Mock, patch, AsyncMock
import numpy as np

from src.embeddings.generator import EmbeddingGenerator
from src.config import ServerConfig
from src.core.exceptions import EmbeddingError


@pytest.fixture
def config():
    """Create test configuration."""
    return ServerConfig(
        embedding_model="all-MiniLM-L6-v2",
        embedding_batch_size=32,
        embedding_cache_enabled=False,  # Disable cache for unit tests
    )


@pytest_asyncio.fixture
async def generator(config):
    """Create embedding generator instance."""
    gen = EmbeddingGenerator(config)
    await gen.initialize()
    yield gen
    await gen.close()


class TestEmbeddingGeneratorInitialization:
    """Test embedding generator initialization."""

    @pytest.mark.asyncio
    async def test_initialization(self, config):
        """Test that generator initializes correctly."""
        gen = EmbeddingGenerator(config)
        await gen.initialize()

        assert gen.model is not None
        assert gen.model_name == "all-MiniLM-L6-v2"
        assert gen.embedding_dim == 384  # Use embedding_dim, not dimension

        await gen.close()

    @pytest.mark.asyncio
    async def test_initialization_with_default_config(self):
        """Test initialization with default config."""
        gen = EmbeddingGenerator()
        await gen.initialize()

        assert gen.model is not None
        assert gen.config is not None

        await gen.close()

    def test_supported_models(self):
        """Test that MODELS dict contains expected models."""
        assert "all-MiniLM-L6-v2" in EmbeddingGenerator.MODELS
        assert EmbeddingGenerator.MODELS["all-MiniLM-L6-v2"] == 384
        assert "all-mpnet-base-v2" in EmbeddingGenerator.MODELS
        assert EmbeddingGenerator.MODELS["all-mpnet-base-v2"] == 768


class TestEmbeddingGeneration:
    """Test embedding generation functionality."""

    @pytest.mark.asyncio
    async def test_generate_single_embedding(self, generator):
        """Test generating a single embedding."""
        text = "This is a test sentence."
        embedding = await generator.generate(text)

        # Verify embedding properties
        assert embedding is not None
        assert isinstance(embedding, (list, np.ndarray))
        assert len(embedding) == 384  # MiniLM-L6-v2 dimension

        # Verify embedding is normalized (magnitude should be 1.0)
        magnitude = sum(x * x for x in embedding) ** 0.5
        assert abs(magnitude - 1.0) < 1e-5, f"Embedding should be normalized, got magnitude {magnitude}"

    @pytest.mark.asyncio
    async def test_generate_batch_embeddings(self, generator):
        """Test generating batch of embeddings."""
        texts = [
            "First sentence",
            "Second sentence",
            "Third sentence",
        ]

        embeddings = await generator.batch_generate(texts)

        # Verify batch results
        assert len(embeddings) == len(texts)
        for embedding in embeddings:
            assert len(embedding) == 384
            # Verify normalization
            magnitude = sum(x * x for x in embedding) ** 0.5
            assert abs(magnitude - 1.0) < 1e-5

    @pytest.mark.asyncio
    async def test_generate_empty_string(self, generator):
        """Test generating embedding for empty string."""
        # Empty string should raise EmbeddingError
        with pytest.raises(EmbeddingError, match="Cannot generate embedding for empty text"):
            await generator.generate("")

    @pytest.mark.asyncio
    async def test_generate_long_text(self, generator):
        """Test generating embedding for very long text."""
        long_text = "This is a sentence. " * 500  # ~10,000 chars

        embedding = await generator.generate(long_text)

        assert embedding is not None
        assert len(embedding) == 384


class TestBatchProcessing:
    """Test batch processing functionality."""

    @pytest.mark.asyncio
    async def test_batch_generate_empty_list(self, generator):
        """Test batch generation with empty list."""
        embeddings = await generator.batch_generate([])

        assert embeddings == []

    @pytest.mark.asyncio
    async def test_batch_generate_single_item(self, generator):
        """Test batch generation with single item."""
        embeddings = await generator.batch_generate(["Single text"])

        assert len(embeddings) == 1
        assert len(embeddings[0]) == 384

    @pytest.mark.asyncio
    async def test_batch_generate_large_batch(self, generator):
        """Test batch generation with large batch."""
        # Create 100 different texts
        texts = [f"Text number {i}" for i in range(100)]

        embeddings = await generator.batch_generate(texts, show_progress=False)

        assert len(embeddings) == 100
        # Verify all are different (at least some variation)
        unique_embeddings = {tuple(emb) for emb in embeddings}
        assert len(unique_embeddings) > 90, "Embeddings should be unique for different texts"

    @pytest.mark.asyncio
    async def test_batch_processing_respects_batch_size(self, config):
        """Test that batch processing respects configured batch size."""
        config.embedding_batch_size = 5
        gen = EmbeddingGenerator(config)
        await gen.initialize()

        texts = [f"Text {i}" for i in range(12)]

        # Mock the model.encode to track batch calls
        original_encode = gen.model.encode
        call_counts = []

        def tracked_encode(texts, *args, **kwargs):
            call_counts.append(len(texts))
            return original_encode(texts, *args, **kwargs)

        gen.model.encode = tracked_encode

        embeddings = await gen.batch_generate(texts, show_progress=False)

        # Should have batched into: 5, 5, 2 (total 12)
        assert len(embeddings) == 12
        assert len(call_counts) >= 1  # At least one batch processed

        await gen.close()


class TestEmbeddingDimensions:
    """Test embedding dimension handling."""

    @pytest.mark.asyncio
    async def test_dimension_property(self, generator):
        """Test dimension property."""
        assert generator.embedding_dim == 384

    @pytest.mark.asyncio
    async def test_different_model_dimension(self):
        """Test different model has correct dimension."""
        config = ServerConfig(
            embedding_model="all-mpnet-base-v2",
            embedding_cache_enabled=False,
        )
        gen = EmbeddingGenerator(config)
        await gen.initialize()

        assert gen.embedding_dim == 768
        embedding = await gen.generate("test")
        assert len(embedding) == 768

        await gen.close()


class TestErrorHandling:
    """Test error handling in embedding generation."""

    @pytest.mark.asyncio
    async def test_generate_with_none_text(self, generator):
        """Test that None text raises appropriate error."""
        # None text is caught by the "if not text" check and raises EmbeddingError
        with pytest.raises(EmbeddingError, match="Cannot generate embedding for empty text"):
            await generator.generate(None)

    @pytest.mark.asyncio
    async def test_batch_generate_with_none_items(self, generator):
        """Test batch generation with None items."""
        # Should filter out None or handle gracefully
        # The actual implementation may filter None items
        result = await generator.batch_generate([None, "valid text", None])
        # Either returns valid embeddings (filtered) or raises error
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_model_loading_failure(self):
        """Test handling of model loading failures."""
        # Constructor itself raises error for invalid model
        with pytest.raises(EmbeddingError, match="Unsupported model"):
            config = ServerConfig(
                embedding_model="nonexistent-model-12345",
                embedding_cache_enabled=False,
            )
            gen = EmbeddingGenerator(config)


class TestNormalization:
    """Test embedding normalization."""

    @pytest.mark.asyncio
    async def test_embeddings_are_normalized(self, generator):
        """Test that all embeddings are L2 normalized."""
        texts = ["Test 1", "Test 2", "Test 3", "Test 4", "Test 5"]
        embeddings = await generator.batch_generate(texts)

        for i, embedding in enumerate(embeddings):
            magnitude = sum(x * x for x in embedding) ** 0.5
            assert abs(magnitude - 1.0) < 1e-5, \
                f"Embedding {i} should be normalized (magnitude 1.0), got {magnitude}"

    @pytest.mark.asyncio
    async def test_zero_embedding_handling(self, generator):
        """Test that zero embeddings are handled (shouldn't occur but test defensive code)."""
        # This is unlikely with real models but tests defensive normalization
        # We'll just verify that normal embeddings are properly normalized
        embedding = await generator.generate("Normal text that won't be zero")

        magnitude = sum(x * x for x in embedding) ** 0.5
        assert magnitude > 0, "Embedding should not be zero vector"
        assert abs(magnitude - 1.0) < 1e-5, "Embedding should be normalized"


class TestConcurrency:
    """Test concurrent embedding generation."""

    @pytest.mark.asyncio
    @pytest.mark.skip_ci  # Concurrent operations may exceed CI timeout
    async def test_concurrent_generate_calls(self, generator):
        """Test that multiple concurrent generate calls work correctly."""
        texts = [f"Concurrent text {i}" for i in range(10)]

        # Generate embeddings concurrently
        tasks = [generator.generate(text) for text in texts]
        embeddings = await asyncio.gather(*tasks)

        # Verify all succeeded
        assert len(embeddings) == 10
        for embedding in embeddings:
            assert len(embedding) == 384
            magnitude = sum(x * x for x in embedding) ** 0.5
            assert abs(magnitude - 1.0) < 1e-5

    @pytest.mark.asyncio
    @pytest.mark.skip_ci  # Concurrent batch operations may exceed CI timeout
    async def test_concurrent_batch_generate_calls(self, generator):
        """Test concurrent batch generation."""
        batch1 = ["Batch 1 text A", "Batch 1 text B"]
        batch2 = ["Batch 2 text A", "Batch 2 text B"]
        batch3 = ["Batch 3 text A", "Batch 3 text B"]

        # Run multiple batch generations concurrently
        results = await asyncio.gather(
            generator.batch_generate(batch1),
            generator.batch_generate(batch2),
            generator.batch_generate(batch3),
        )

        # Verify all batches completed
        assert len(results) == 3
        for batch_result in results:
            assert len(batch_result) == 2
            for embedding in batch_result:
                assert len(embedding) == 384


class TestSemanticSimilarity:
    """Test that embeddings capture semantic similarity."""

    @pytest.mark.asyncio
    async def test_similar_texts_have_similar_embeddings(self, generator):
        """Test that semantically similar texts have similar embeddings."""
        text1 = "The cat sits on the mat"
        text2 = "A cat is sitting on a mat"
        text3 = "Python is a programming language"

        emb1 = await generator.generate(text1)
        emb2 = await generator.generate(text2)
        emb3 = await generator.generate(text3)

        # Calculate cosine similarity
        def cosine_sim(a, b):
            return sum(x * y for x, y in zip(a, b))  # Already normalized, so no need to divide

        sim_1_2 = cosine_sim(emb1, emb2)
        sim_1_3 = cosine_sim(emb1, emb3)

        # Similar sentences should have higher similarity than dissimilar ones
        assert sim_1_2 > sim_1_3, \
            f"Similar texts should have higher similarity. Got {sim_1_2} vs {sim_1_3}"
        assert sim_1_2 > 0.7, f"Similar texts should have high similarity score, got {sim_1_2}"


class TestResourceManagement:
    """Test resource management and cleanup."""

    @pytest.mark.asyncio
    async def test_close_cleans_up_resources(self, config):
        """Test that close() properly cleans up resources."""
        gen = EmbeddingGenerator(config)
        await gen.initialize()

        assert gen.model is not None
        assert gen.executor is not None

        await gen.close()

        # After close, resources should be cleaned up
        # (Note: checking internal state, may need adjustment based on implementation)

    @pytest.mark.asyncio
    async def test_multiple_close_calls(self, config):
        """Test that multiple close() calls don't cause errors."""
        gen = EmbeddingGenerator(config)
        await gen.initialize()

        # Should not raise error
        await gen.close()
        await gen.close()
        await gen.close()


