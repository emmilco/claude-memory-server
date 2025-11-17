"""Parallel embedding generation using multiprocessing for improved throughput."""

import asyncio
import logging
import os
from concurrent.futures import ProcessPoolExecutor
from typing import List, Optional, Dict, Any
import time

from src.config import ServerConfig
from src.core.exceptions import EmbeddingError

logger = logging.getLogger(__name__)

# Global model cache for worker processes (one model per process)
_worker_model_cache: Dict[str, Any] = {}


def _load_model_in_worker(model_name: str) -> Any:
    """
    Load the sentence transformer model in a worker process.

    This is called once per worker process and caches the model.

    Args:
        model_name: Name of the model to load.

    Returns:
        SentenceTransformer: Loaded model.
    """
    global _worker_model_cache

    if model_name not in _worker_model_cache:
        try:
            from sentence_transformers import SentenceTransformer
            from src.embeddings.rust_bridge import RustBridge

            logger.info(f"Worker {os.getpid()}: Loading model {model_name}")
            model = SentenceTransformer(model_name)
            model.to("cpu")  # Force CPU for consistency
            _worker_model_cache[model_name] = model
            logger.info(f"Worker {os.getpid()}: Model loaded successfully")
        except Exception as e:
            logger.error(f"Worker {os.getpid()}: Failed to load model: {e}")
            raise

    return _worker_model_cache[model_name]


def _generate_embeddings_batch(
    texts: List[str],
    model_name: str,
    batch_size: int,
) -> List[List[float]]:
    """
    Generate embeddings for a batch of texts in a worker process.

    This function is pickled and sent to worker processes.
    It loads the model (cached per worker) and generates embeddings.

    Args:
        texts: List of texts to embed.
        model_name: Name of the embedding model.
        batch_size: Batch size for encoding.

    Returns:
        List[List[float]]: List of embedding vectors.
    """
    try:
        from src.embeddings.rust_bridge import RustBridge

        # Load model (cached in worker)
        model = _load_model_in_worker(model_name)

        # Generate embeddings
        embeddings = model.encode(
            texts,
            convert_to_numpy=True,
            normalize_embeddings=False,
            batch_size=batch_size,
            show_progress_bar=False,
        )

        # Convert to list of lists
        embeddings_list = [emb.tolist() for emb in embeddings]

        # Normalize using Rust (or Python fallback)
        normalized = RustBridge.batch_normalize(embeddings_list)

        return normalized

    except Exception as e:
        logger.error(f"Worker {os.getpid()}: Error generating embeddings: {e}")
        raise EmbeddingError(f"Embedding generation failed in worker: {e}")


class ParallelEmbeddingGenerator:
    """
    High-performance embedding generator using multiprocessing.

    Features:
    - True parallel processing using ProcessPoolExecutor
    - Automatic load balancing across CPU cores
    - Model caching per worker process
    - Configurable worker count
    - Graceful fallback to single-threaded mode

    Performance:
    - 4-8x faster than single-threaded on multi-core systems
    - Target: 10-20 files/sec indexing throughput
    """

    # Supported models and their dimensions
    MODELS = {
        "all-MiniLM-L6-v2": 384,
        "all-MiniLM-L12-v2": 384,
        "all-mpnet-base-v2": 768,
    }

    def __init__(
        self,
        config: Optional[ServerConfig] = None,
        max_workers: Optional[int] = None,
    ):
        """
        Initialize parallel embedding generator.

        Args:
            config: Server configuration. If None, uses global config.
            max_workers: Maximum worker processes. If None, uses CPU count.
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

        # Determine worker count
        if max_workers is None:
            max_workers = getattr(config, 'embedding_parallel_workers', None)
        if max_workers is None:
            max_workers = os.cpu_count() or 4

        self.max_workers = max_workers
        self.executor: Optional[ProcessPoolExecutor] = None

        # Threshold for using parallel processing (avoid overhead for small batches)
        self.parallel_threshold = 10

        logger.info(
            f"Parallel embedding generator initialized: "
            f"model={self.model_name}, workers={self.max_workers}"
        )

    async def initialize(self) -> None:
        """
        Initialize the process pool executor.

        Should be called during server initialization.
        """
        try:
            logger.info(f"Initializing process pool with {self.max_workers} workers")
            self.executor = ProcessPoolExecutor(max_workers=self.max_workers)
            logger.info("Process pool initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize process pool: {e}")
            raise

    async def generate(self, text: str) -> List[float]:
        """
        Generate embedding for a single text.

        For single texts, uses the internal single-threaded fallback
        to avoid multiprocessing overhead.

        Args:
            text: Input text to embed.

        Returns:
            List[float]: Embedding vector.

        Raises:
            EmbeddingError: If embedding generation fails.
        """
        if not text or not text.strip():
            raise EmbeddingError("Cannot generate embedding for empty text")

        # For single text, use batch_generate with size 1
        results = await self.batch_generate([text], show_progress=False)
        return results[0]

    async def batch_generate(
        self,
        texts: List[str],
        batch_size: Optional[int] = None,
        show_progress: bool = False,
    ) -> List[List[float]]:
        """
        Generate embeddings for multiple texts using parallel processing.

        Distributes work across worker processes for maximum throughput.
        For small batches (<10 texts), falls back to single-threaded mode
        to avoid multiprocessing overhead.

        Args:
            texts: List of texts to embed.
            batch_size: Batch size per worker (defaults to config value).
            show_progress: Whether to log progress.

        Returns:
            List[List[float]]: List of embedding vectors.

        Raises:
            EmbeddingError: If batch generation fails.
        """
        if not texts:
            return []

        # Validate inputs
        for i, text in enumerate(texts):
            if not text or not text.strip():
                raise EmbeddingError(f"Empty text at index {i}")

        batch_size = batch_size or self.batch_size

        try:
            # For small batches, use single-threaded mode (avoid process overhead)
            if len(texts) < self.parallel_threshold:
                if show_progress:
                    logger.info(
                        f"Using single-threaded mode for small batch ({len(texts)} texts)"
                    )
                return await self._generate_single_threaded(texts, batch_size)

            # For large batches, use multiprocessing
            if show_progress:
                logger.info(
                    f"Using parallel mode with {self.max_workers} workers "
                    f"({len(texts)} texts)"
                )

            return await self._generate_parallel(texts, batch_size, show_progress)

        except Exception as e:
            raise EmbeddingError(f"Failed to batch generate embeddings: {e}")

    async def _generate_single_threaded(
        self,
        texts: List[str],
        batch_size: int,
    ) -> List[List[float]]:
        """
        Generate embeddings using single-threaded fallback.

        Used for small batches to avoid multiprocessing overhead.

        Args:
            texts: List of texts to embed.
            batch_size: Batch size.

        Returns:
            List[List[float]]: Embedding vectors.
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,  # Default executor (ThreadPoolExecutor)
            _generate_embeddings_batch,
            texts,
            self.model_name,
            batch_size,
        )

    async def _generate_parallel(
        self,
        texts: List[str],
        batch_size: int,
        show_progress: bool,
    ) -> List[List[float]]:
        """
        Generate embeddings using multiprocessing for parallelism.

        Distributes texts across worker processes for true parallel execution.

        Args:
            texts: List of texts to embed.
            batch_size: Batch size per worker.
            show_progress: Whether to log progress.

        Returns:
            List[List[float]]: Embedding vectors.
        """
        if self.executor is None:
            await self.initialize()

        # Split texts into chunks for workers
        # Each worker gets approximately equal number of texts
        chunk_size = max(1, len(texts) // self.max_workers)
        if len(texts) % self.max_workers != 0:
            chunk_size += 1  # Ensure we don't lose any texts

        chunks = [
            texts[i:i + chunk_size]
            for i in range(0, len(texts), chunk_size)
        ]

        if show_progress:
            logger.info(
                f"Distributing {len(texts)} texts across {len(chunks)} workers "
                f"(~{chunk_size} texts/worker)"
            )

        # Submit tasks to process pool
        loop = asyncio.get_event_loop()
        tasks = [
            loop.run_in_executor(
                self.executor,
                _generate_embeddings_batch,
                chunk,
                self.model_name,
                batch_size,
            )
            for chunk in chunks
        ]

        # Wait for all workers to complete
        start_time = time.time()
        chunk_results = await asyncio.gather(*tasks)
        elapsed = time.time() - start_time

        # Flatten results (maintain order)
        all_embeddings = []
        for chunk_result in chunk_results:
            all_embeddings.extend(chunk_result)

        if show_progress:
            logger.info(
                f"Generated {len(all_embeddings)} embeddings in {elapsed:.2f}s "
                f"({len(all_embeddings) / elapsed:.1f} embeddings/sec)"
            )

        return all_embeddings

    def get_embedding_dim(self) -> int:
        """
        Get the dimension of embeddings produced by this generator.

        Returns:
            int: Embedding dimension.
        """
        return self.embedding_dim

    async def close(self) -> None:
        """Shutdown the process pool executor."""
        if self.executor:
            logger.info("Shutting down process pool executor")
            self.executor.shutdown(wait=True)
            self.executor = None
            logger.info("Process pool shut down successfully")

    def __del__(self):
        """Cleanup on destruction."""
        if self.executor:
            self.executor.shutdown(wait=False)
