"""Embedding generation with async support and caching."""

import asyncio
import logging
from typing import List, Optional, Union
from concurrent.futures import ThreadPoolExecutor
import time

from sentence_transformers import SentenceTransformer

from src.config import ServerConfig
from src.core.exceptions import EmbeddingError
from src.embeddings.rust_bridge import RustBridge
from src.embeddings.cache import EmbeddingCache

logger = logging.getLogger(__name__)


class EmbeddingGenerator:
    """
    High-performance embedding generator with async support.

    Features:
    - Async embedding generation using thread pool
    - Batch processing with configurable batch size
    - Multiple model support
    - Automatic normalization using Rust (or Python fallback)
    - Thread-safe singleton model loading
    """

    # Supported models and their dimensions
    MODELS = {
        "all-MiniLM-L6-v2": 384,
        "all-MiniLM-L12-v2": 384,
        "all-mpnet-base-v2": 768,
    }

    def __init__(self, config: Optional[ServerConfig] = None):
        """
        Initialize embedding generator.

        Args:
            config: Server configuration. If None, uses global config.
        """
        if config is None:
            from src.config import get_config
            config = get_config()

        self.config = config
        self.model_name = config.embedding_model
        self.batch_size = config.embedding_batch_size

        # Validate model
        if self.model_name not in self.MODELS:
            raise EmbeddingError(
                f"Unsupported model: {self.model_name}. "
                f"Supported models: {list(self.MODELS.keys())}"
            )

        self.embedding_dim = self.MODELS[self.model_name]
        self.model: Optional[SentenceTransformer] = None
        self.executor = ThreadPoolExecutor(max_workers=2)
        
        # Initialize cache (if enabled)
        self.cache = EmbeddingCache(config) if config.embedding_cache_enabled else None

        logger.info(f"Embedding generator initialized with model: {self.model_name}")
        if self.cache and self.cache.enabled:
            logger.info("Embedding cache enabled")

    async def initialize(self) -> None:
        """
        Preload the embedding model on startup.

        Prevents 2-second hang on first query. Should be called during server initialization.
        Runs the model loading in a thread pool to avoid blocking the event loop.
        """
        try:
            logger.info(f"Preloading embedding model: {self.model_name}")
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(self.executor, self._load_model)
            logger.info("Embedding model preloaded and ready")
        except Exception as e:
            logger.error(f"Failed to preload embedding model: {e}")
            raise

    def _load_model(self) -> SentenceTransformer:
        """
        Load the sentence transformer model (lazy loading).

        Returns:
            SentenceTransformer: Loaded model.
        """
        if self.model is None:
            logger.info(f"Loading embedding model: {self.model_name}")
            start_time = time.time()

            self.model = SentenceTransformer(self.model_name)

            # Set to CPU only for consistency (no CUDA randomness)
            self.model.to("cpu")

            load_time = time.time() - start_time
            logger.info(f"Model loaded in {load_time:.2f}s")

        return self.model

    async def generate(self, text: str) -> List[float]:
        """
        Generate embedding for a single text.

        First checks the cache, then generates if not cached.

        Args:
            text: Input text to embed.

        Returns:
            List[float]: Embedding vector.

        Raises:
            EmbeddingError: If embedding generation fails.
        """
        if not text or not text.strip():
            raise EmbeddingError("Cannot generate embedding for empty text")

        try:
            # Try cache first
            if self.cache and self.cache.enabled:
                cached = await self.cache.get(text, self.model_name)
                if cached is not None:
                    return cached

            # Run generation in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            embedding = await loop.run_in_executor(
                self.executor,
                self._generate_sync,
                text
            )

            # Cache the result
            if self.cache and self.cache.enabled:
                await self.cache.set(text, self.model_name, embedding)

            return embedding

        except Exception as e:
            raise EmbeddingError(f"Failed to generate embedding: {e}")

    def _generate_sync(self, text: str) -> List[float]:
        """
        Synchronous embedding generation (runs in thread pool).

        Args:
            text: Input text.

        Returns:
            List[float]: Embedding vector.
        """
        model = self._load_model()

        # Generate embedding
        embedding = model.encode(
            text,
            convert_to_numpy=True,
            normalize_embeddings=False,  # We'll normalize with Rust
        )

        # Convert to list and normalize
        embedding_list = embedding.tolist()
        normalized = RustBridge.batch_normalize([embedding_list])[0]

        return normalized

    async def batch_generate(
        self,
        texts: List[str],
        batch_size: Optional[int] = None,
        show_progress: bool = False,
    ) -> List[List[float]]:
        """
        Generate embeddings for multiple texts in batches.

        Checks cache first for each text, generating only uncached items.

        Args:
            texts: List of texts to embed.
            batch_size: Batch size (defaults to config value).
            show_progress: Whether to log progress.

        Returns:
            List[List[float]]: List of embedding vectors.

        Raises:
            EmbeddingError: If batch generation fails.
        """
        if not texts:
            return []

        batch_size = batch_size or self.batch_size

        try:
            # Check cache for all texts (if enabled)
            cache_results = None
            texts_to_generate = texts
            indices_to_generate = list(range(len(texts)))
            
            if self.cache and self.cache.enabled:
                cache_results = await self.cache.batch_get(texts, self.model_name)
                
                # Find which texts need generation
                texts_to_generate = []
                indices_to_generate = []
                for i, cached in enumerate(cache_results):
                    if cached is None:
                        texts_to_generate.append(texts[i])
                        indices_to_generate.append(i)
                
                if not texts_to_generate:
                    # All texts were cached
                    return cache_results

            # Run batch generation in thread pool for uncached texts
            loop = asyncio.get_event_loop()
            generated_embeddings = await loop.run_in_executor(
                self.executor,
                self._batch_generate_sync,
                texts_to_generate,
                batch_size,
                show_progress
            )
            
            # Cache generated embeddings
            if self.cache and self.cache.enabled:
                for text, embedding in zip(texts_to_generate, generated_embeddings):
                    await self.cache.set(text, self.model_name, embedding)
            
            # Merge results back into original order
            if cache_results is not None:
                for i, generated in zip(indices_to_generate, generated_embeddings):
                    cache_results[i] = generated
                return cache_results
            else:
                return generated_embeddings

        except Exception as e:
            raise EmbeddingError(f"Failed to batch generate embeddings: {e}")

    def _batch_generate_sync(
        self,
        texts: List[str],
        batch_size: int,
        show_progress: bool,
    ) -> List[List[float]]:
        """
        Synchronous batch embedding generation.

        Args:
            texts: List of texts.
            batch_size: Batch size.
            show_progress: Show progress logging.

        Returns:
            List[List[float]]: Embedding vectors.
        """
        model = self._load_model()

        all_embeddings = []
        total_batches = (len(texts) + batch_size - 1) // batch_size

        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            batch_num = i // batch_size + 1

            if show_progress:
                logger.info(f"Processing batch {batch_num}/{total_batches} ({len(batch)} texts)")

            # Generate embeddings for batch
            embeddings = model.encode(
                batch,
                convert_to_numpy=True,
                normalize_embeddings=False,
                batch_size=batch_size,
            )

            # Convert to list of lists
            embeddings_list = [emb.tolist() for emb in embeddings]

            # Normalize batch using Rust (or Python fallback)
            normalized = RustBridge.batch_normalize(embeddings_list)
            all_embeddings.extend(normalized)

        return all_embeddings

    def get_embedding_dim(self) -> int:
        """
        Get the dimension of embeddings produced by this generator.

        Returns:
            int: Embedding dimension.
        """
        return self.embedding_dim

    async def benchmark(self, num_texts: int = 100) -> dict:
        """
        Run a benchmark to measure embedding generation performance.

        Args:
            num_texts: Number of test texts to generate.

        Returns:
            dict: Benchmark results with timing and throughput metrics.
        """
        # Generate sample texts
        sample_texts = [f"This is sample text number {i} for benchmarking." for i in range(num_texts)]

        # Single embedding benchmark
        start = time.time()
        await self.generate(sample_texts[0])
        single_time = time.time() - start

        # Batch embedding benchmark
        start = time.time()
        await self.batch_generate(sample_texts)
        batch_time = time.time() - start

        throughput = num_texts / batch_time

        return {
            "model": self.model_name,
            "num_texts": num_texts,
            "single_embedding_ms": single_time * 1000,
            "batch_total_s": batch_time,
            "batch_avg_ms": (batch_time / num_texts) * 1000,
            "throughput_docs_per_sec": throughput,
            "rust_available": RustBridge.is_rust_available(),
        }

    async def close(self) -> None:
        """
        Clean up resources.
        
        Should be called when the generator is no longer needed.
        Shuts down the thread pool executor, closes the cache, and unloads the model.
        """
        self.executor.shutdown(wait=True)
        if self.cache:
            self.cache.close()
        if self.model is not None:
            # Unload model from memory
            del self.model
            self.model = None
        logger.info("Embedding generator closed")

    def __del__(self):
        """Fallback cleanup if close() not called."""
        try:
            self.executor.shutdown(wait=False)
        except:
            pass

