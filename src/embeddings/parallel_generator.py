"""Parallel embedding generation using multiprocessing for improved throughput."""

import asyncio
import atexit
import logging
import os
import multiprocessing
import signal
import weakref
from concurrent.futures import ProcessPoolExecutor
from functools import lru_cache
from typing import List, Optional, Dict, Any
import time

from src.config import ServerConfig
from src.core.exceptions import EmbeddingError
from src.embeddings.cache import EmbeddingCache

logger = logging.getLogger(__name__)

# BUG-272: Module-level registry using WeakSet to avoid circular references
# This allows atexit and signal handlers to cleanup all instances without
# holding strong references that would prevent garbage collection
_instances: weakref.WeakSet = weakref.WeakSet()


def _cleanup_all_instances() -> None:
    """
    Module-level cleanup handler for atexit.

    BUG-272: This function is registered with atexit instead of bound methods,
    avoiding circular references. It iterates through the weak set and cleans
    up any remaining instances.
    """
    # Create a list to avoid issues with set changing during iteration
    instances_to_cleanup = list(_instances)
    if instances_to_cleanup:
        logger.info(f"Cleaning up {len(instances_to_cleanup)} ParallelEmbeddingGenerator instance(s)")
        for instance in instances_to_cleanup:
            try:
                instance._cleanup_sync_fallback()
            except Exception as e:
                logger.warning(f"Error during instance cleanup: {e}")


def _signal_handler_module(signum: int, frame) -> None:
    """
    Module-level signal handler.

    BUG-272: This function is registered with signal handlers instead of bound methods,
    avoiding circular references. It cleans up all instances and then re-raises the signal.
    """
    logger.info(f"Received signal {signum}, cleaning up all instances...")
    _cleanup_all_instances()
    # Re-raise the signal to allow normal termination
    signal.signal(signum, signal.SIG_DFL)
    os.kill(os.getpid(), signum)


# BUG-272: Register module-level handlers once at import time
# This prevents memory leaks from registering bound methods
_cleanup_handlers_registered = False


def _register_module_cleanup_handlers() -> None:
    """Register module-level cleanup handlers once at import time."""
    global _cleanup_handlers_registered
    if _cleanup_handlers_registered:
        return

    # Register atexit handler
    atexit.register(_cleanup_all_instances)

    # Register signal handlers
    try:
        signal.signal(signal.SIGTERM, _signal_handler_module)
        signal.signal(signal.SIGINT, _signal_handler_module)
        logger.debug("Registered module-level cleanup handlers")
    except (ValueError, OSError) as e:
        logger.debug(f"Could not register signal handlers: {e}")

    _cleanup_handlers_registered = True


# Register handlers at module import time
_register_module_cleanup_handlers()

# Set multiprocessing start method to 'spawn' to avoid fork issues with transformers/tokenizers
# 'spawn' creates fresh processes without copying memory, preventing tokenizers fork conflicts
# This must be done before creating any processes
if hasattr(multiprocessing, 'set_start_method'):
    try:
        # Only set if not already set
        current_method = multiprocessing.get_start_method(allow_none=True)
        if current_method is None:
            multiprocessing.set_start_method('spawn', force=False)
            logger.info("Set multiprocessing start method to 'spawn' (safe for transformers)")
        elif current_method == 'fork':
            logger.warning(
                f"Multiprocessing start method is 'fork'. This may cause issues with "
                f"tokenizers library. Consider using 'spawn' instead."
            )
    except RuntimeError as e:
        logger.debug(f"Could not set multiprocessing start method: {e}")

@lru_cache(maxsize=4)
def _load_model_in_worker(model_name: str) -> Any:
    """
    Load the sentence transformer model in a worker process.

    This function is cached per worker process using @lru_cache, which provides
    automatic caching without global state. Each worker process maintains its own
    cache (up to 4 models).

    Note: This cache is per-process. Each worker in ProcessPoolExecutor has its
    own independent cache, which is the desired behavior for multiprocessing.

    Args:
        model_name: Name of the model to load.

    Returns:
        SentenceTransformer: Loaded model (cached after first load in this process).
    """
    try:
        import torch
        from sentence_transformers import SentenceTransformer
        from src.embeddings.rust_bridge import RustBridge

        # Disable tokenizers parallelism in worker to prevent conflicts
        # This is the proper way to disable it via the API
        try:
            import tokenizers
            tokenizers.set_parallelism(False)
        except (ImportError, AttributeError):
            # tokenizers may not be available or may not have this method
            pass

        logger.info(f"Worker {os.getpid()}: Loading model {model_name}")

        # COMPLETE FIX: Explicitly disable meta device initialization
        # This prevents the "Cannot copy out of meta tensor" error

        # Load model with explicit CPU device and disable trust_remote_code
        # to avoid lazy initialization on meta device
        model = SentenceTransformer(
            model_name,
            device="cpu",
            trust_remote_code=False,  # Prevents meta device issues
        )

        # Force evaluation mode (disables dropout, etc.)
        model.eval()

        # Ensure all tensors are materialized on CPU
        # This is the key fix for meta tensor issues
        for module in model.modules():
            for param in module.parameters(recurse=False):
                if param.is_meta:
                    # Use to_empty() instead of to() for meta tensors
                    param.data = torch.nn.Parameter(
                        torch.empty_like(param, device='cpu')
                    ).data
                elif param.device.type != 'cpu':
                    param.data = param.data.to('cpu')

            for buffer_name, buffer in module.named_buffers(recurse=False):
                if buffer.is_meta:
                    setattr(module, buffer_name,
                           torch.empty_like(buffer, device='cpu'))
                elif buffer.device.type != 'cpu':
                    setattr(module, buffer_name, buffer.to('cpu'))

        logger.info(f"Worker {os.getpid()}: Model loaded successfully")
        return model
    except Exception as e:
        logger.error(f"Worker {os.getpid()}: Failed to load model: {e}", exc_info=True)
        raise


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
        logger.error(f"Worker {os.getpid()}: Error generating embeddings: {e}", exc_info=True)
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
    - Automatic cleanup on shutdown via signal handlers and atexit

    Performance:
    - 4-8x faster than single-threaded on multi-core systems
    - Target: 10-20 files/sec indexing throughput

    Important:
    - The close() method MUST be called explicitly for proper cleanup
    - Signal handlers (SIGTERM/SIGINT) and atexit are registered as fallback
    - __del__() uses wait=False to avoid blocking, so close() is preferred
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

        # MPS (Apple Silicon) is faster for larger models with large batch sizes
        # Small models like all-MiniLM-L6-v2 are faster on CPU due to GPU transfer overhead
        from src.embeddings.gpu_utils import detect_mps
        large_model = self.model_name in ("all-mpnet-base-v2",)  # Models that benefit from MPS
        self._use_mps_fallback = detect_mps() and large_model and not config.performance.force_cpu
        self._mps_generator = None

        if self._use_mps_fallback:
            logger.info("MPS (Apple Silicon) detected with large model - using GPU acceleration")
            self.max_workers = 1  # Single-threaded for MPS
        else:
            # Determine worker count from config.performance.parallel_workers (default: 3)
            if max_workers is None:
                max_workers = getattr(config.performance, 'parallel_workers', 3)
            self.max_workers = max_workers

        self.executor: Optional[ProcessPoolExecutor] = None

        # Initialize cache (if enabled)
        self.cache = EmbeddingCache(config) if config.embedding_cache_enabled else None

        # Threshold for using parallel processing (avoid overhead for small batches)
        self.parallel_threshold = 10

        # BUG-272: Add this instance to the module-level weak set
        # This allows module-level cleanup handlers to find and clean up instances
        # without creating circular references that prevent garbage collection
        _instances.add(self)

        logger.info(
            f"Parallel embedding generator initialized: "
            f"model={self.model_name}, workers={self.max_workers}"
        )
        if self.cache and self.cache.enabled:
            logger.info("Embedding cache enabled for parallel generator")

    def _cleanup_sync_fallback(self) -> None:
        """
        Synchronous cleanup fallback for atexit and signal handlers.

        This is a best-effort cleanup when close() hasn't been called.
        Uses wait=True to ensure workers terminate properly.
        """
        if hasattr(self, 'executor') and self.executor:
            try:
                logger.info("Running cleanup fallback for ProcessPoolExecutor")
                self.executor.shutdown(wait=True, cancel_futures=True)
                self.executor = None
                logger.info("ProcessPoolExecutor cleanup completed")
            except Exception as e:
                logger.warning(f"Error during cleanup fallback: {e}")

        if hasattr(self, '_mps_generator') and self._mps_generator:
            try:
                if hasattr(self._mps_generator, 'executor'):
                    self._mps_generator.executor.shutdown(wait=True)
            except Exception as e:
                logger.warning(f"Error during MPS cleanup fallback: {e}")

        if hasattr(self, 'cache') and self.cache:
            try:
                self.cache.close()
            except Exception as e:
                logger.warning(f"Error during cache cleanup fallback: {e}")

    async def initialize(self) -> None:
        """
        Initialize the process pool executor (or MPS generator).

        Should be called during server initialization.
        """
        try:
            if self._use_mps_fallback:
                # Use single-threaded MPS generator
                from src.embeddings.generator import EmbeddingGenerator
                logger.info("Initializing MPS embedding generator")
                self._mps_generator = EmbeddingGenerator(self.config)
                await self._mps_generator.initialize()
                logger.info("MPS embedding generator initialized successfully")
            else:
                logger.info(f"Initializing process pool with {self.max_workers} workers")
                self.executor = ProcessPoolExecutor(max_workers=self.max_workers)
                logger.info("Process pool initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize embedding generator: {e}", exc_info=True)
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

        # Use MPS generator if available (GPU-accelerated single-threaded)
        if self._use_mps_fallback and self._mps_generator:
            if show_progress:
                logger.info(f"Using MPS (Apple Silicon) for {len(texts)} texts")
            return await self._mps_generator.batch_generate(texts, batch_size, show_progress)

        # Adaptive batch sizing based on text length (PERF-004)
        if batch_size is None:
            avg_text_length = sum(len(t) for t in texts) / len(texts) if texts else 0
            if avg_text_length < 500:
                batch_size = min(64, self.batch_size * 2)  # Small texts: larger batches
            elif avg_text_length > 2000:
                batch_size = max(16, self.batch_size // 2)  # Large texts: smaller batches
            else:
                batch_size = self.batch_size  # Medium texts: default

            if show_progress and avg_text_length > 0:
                logger.info(f"Adaptive batch size: {batch_size} (avg text length: {avg_text_length:.0f} chars)")
        else:
            batch_size = batch_size

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
                cache_hits = 0
                for i, cached in enumerate(cache_results):
                    if cached is None:
                        texts_to_generate.append(texts[i])
                        indices_to_generate.append(i)
                    else:
                        cache_hits += 1

                if show_progress and cache_hits > 0:
                    hit_rate = (cache_hits / len(texts)) * 100
                    logger.info(f"Cache hits: {cache_hits}/{len(texts)} ({hit_rate:.1f}%)")

                if not texts_to_generate:
                    # All texts were cached
                    if show_progress:
                        logger.info("All embeddings retrieved from cache")
                    return cache_results

            # For small batches, use single-threaded mode (avoid process overhead)
            if len(texts_to_generate) < self.parallel_threshold:
                if show_progress:
                    logger.info(
                        f"Using single-threaded mode for small batch ({len(texts_to_generate)} texts)"
                    )
                generated_embeddings = await self._generate_single_threaded(texts_to_generate, batch_size)
            else:
                # For large batches, use multiprocessing
                if show_progress:
                    logger.info(
                        f"Using parallel mode with {self.max_workers} workers "
                        f"({len(texts_to_generate)} texts)"
                    )
                generated_embeddings = await self._generate_parallel(texts_to_generate, batch_size, show_progress)

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

        # Verify executor is available after initialization
        if self.executor is None:
            raise EmbeddingError(
                "Process pool executor failed to initialize. "
                "Check logs for initialization errors."
            )

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
        """Shutdown the process pool executor and all related resources.

        IMPORTANT: This method MUST be called explicitly for proper cleanup.
        While atexit and signal handlers provide fallback cleanup (BUG-272),
        calling close() explicitly ensures timely resource release.

        PERF-009: Ensures proper cleanup of:
        - ProcessPoolExecutor workers (with model memory)
        - MPS generator (if using Apple Silicon fallback)
        - Embedding cache (SQLite connection)

        BUG-272: Uses wait=True to ensure worker processes fully terminate
        and release model memory, preventing process leaks.
        """
        # Close MPS generator if it was used (BUG-051 fix)
        if self._mps_generator:
            try:
                await self._mps_generator.close()
                logger.info("MPS generator closed")
            except Exception as e:
                logger.warning(f"Error closing MPS generator: {e}")
            self._mps_generator = None

        # Close process pool executor
        if self.executor:
            # Run blocking shutdown in thread pool to avoid blocking event loop
            await asyncio.to_thread(self._close_sync)

        # Close cache (SQLite connection)
        if self.cache:
            try:
                self.cache.close()
                logger.info("Embedding cache closed")
            except Exception as e:
                logger.warning(f"Error closing cache: {e}")

    def _close_sync(self) -> None:
        """Synchronous implementation of close() for thread pool execution."""
        logger.info("Shutting down process pool executor")
        # PERF-009: Use wait=True to ensure worker processes fully terminate
        # and release their memory (including loaded models)
        self.executor.shutdown(wait=True, cancel_futures=True)
        self.executor = None
        logger.info("Process pool shut down successfully")

    def __del__(self):
        """Cleanup on destruction - final fallback if close() and handlers didn't run.

        BUG-272: Uses wait=False to avoid blocking in __del__.
        Proper cleanup is handled by:
        1. Explicit close() call (preferred)
        2. Atexit handler (normal program termination)
        3. Signal handlers (SIGTERM/SIGINT)
        4. This __del__ method (final fallback)
        """
        if hasattr(self, 'executor') and self.executor:
            # PERF-009: Still use wait=False in __del__ to avoid blocking
            # but this is a fallback - close() should be called explicitly
            self.executor.shutdown(wait=False, cancel_futures=True)
        if hasattr(self, '_mps_generator') and self._mps_generator:
            # Can't await in __del__, so just try sync cleanup
            try:
                if hasattr(self._mps_generator, 'executor'):
                    self._mps_generator.executor.shutdown(wait=False)
            except Exception:
                pass
        if hasattr(self, 'cache') and self.cache:
            try:
                self.cache.close()
            except Exception:
                pass
