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

        logger.info(f"Embedding generator initialized with model: {self.model_name}")

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
            # Run in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            embedding = await loop.run_in_executor(
                self.executor,
                self._generate_sync,
                text
            )
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
            # Run batch generation in thread pool
            loop = asyncio.get_event_loop()
            embeddings = await loop.run_in_executor(
                self.executor,
                self._batch_generate_sync,
                texts,
                batch_size,
                show_progress
            )
            return embeddings

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
        """Clean up resources."""
        self.executor.shutdown(wait=True)
        logger.info("Embedding generator closed")
