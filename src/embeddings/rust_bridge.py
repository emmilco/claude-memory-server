"""Python wrapper for Rust performance functions with pure Python fallbacks."""

from typing import List
import logging

logger = logging.getLogger(__name__)

# Try to import Rust module
RUST_AVAILABLE = False
try:
    from mcp_performance_core import batch_normalize_embeddings as rust_batch_normalize
    from mcp_performance_core import cosine_similarity as rust_cosine_similarity

    RUST_AVAILABLE = True
    logger.info("Rust performance core loaded successfully")
except ImportError as e:
    logger.info(f"Rust performance core not available, using Python fallbacks: {e}")
    rust_batch_normalize = None
    rust_cosine_similarity = None


def normalize_vector(vector: List[float]) -> List[float]:
    """
    Normalize a single vector to unit length (pure Python).

    Args:
        vector: Input vector

    Returns:
        Normalized vector
    """
    norm = sum(x * x for x in vector) ** 0.5
    if norm > 0:
        return [x / norm for x in vector]
    return [0.0] * len(vector)


def batch_normalize_embeddings_python(
    embeddings: List[List[float]],
) -> List[List[float]]:
    """
    Normalize a batch of embeddings (pure Python fallback).

    Args:
        embeddings: List of embedding vectors

    Returns:
        List of normalized embedding vectors
    """
    return [normalize_vector(emb) for emb in embeddings]


def cosine_similarity_python(vec_a: List[float], vec_b: List[float]) -> float:
    """
    Calculate cosine similarity between two vectors (pure Python fallback).

    Args:
        vec_a: First vector
        vec_b: Second vector

    Returns:
        Cosine similarity score (0.0 to 1.0)
    """
    if len(vec_a) != len(vec_b):
        raise ValueError("Vectors must have the same length")

    dot_product = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = sum(x * x for x in vec_a) ** 0.5
    norm_b = sum(x * x for x in vec_b) ** 0.5

    if norm_a == 0 or norm_b == 0:
        return 0.0

    return dot_product / (norm_a * norm_b)


class RustBridge:
    """Bridge to Rust performance functions with automatic fallback."""

    @staticmethod
    def batch_normalize(embeddings: List[List[float]]) -> List[List[float]]:
        """
        Normalize a batch of embeddings using Rust if available, else Python.

        Args:
            embeddings: List of embedding vectors

        Returns:
            List of normalized embedding vectors
        """
        if RUST_AVAILABLE and rust_batch_normalize is not None:
            try:
                # Convert to list of lists of floats for Rust
                embeddings_f32 = [[float(x) for x in emb] for emb in embeddings]
                return rust_batch_normalize(embeddings_f32)
            except Exception as e:
                logger.warning(f"Rust normalization failed, using Python fallback: {e}")
                return batch_normalize_embeddings_python(embeddings)
        else:
            return batch_normalize_embeddings_python(embeddings)

    @staticmethod
    def cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
        """
        Calculate cosine similarity using Rust if available, else Python.

        Args:
            vec_a: First vector
            vec_b: Second vector

        Returns:
            Cosine similarity score (0.0 to 1.0)
        """
        if RUST_AVAILABLE and rust_cosine_similarity is not None:
            try:
                vec_a_f32 = [float(x) for x in vec_a]
                vec_b_f32 = [float(x) for x in vec_b]
                return float(rust_cosine_similarity(vec_a_f32, vec_b_f32))
            except Exception as e:
                logger.warning(f"Rust similarity failed, using Python fallback: {e}")
                return cosine_similarity_python(vec_a, vec_b)
        else:
            return cosine_similarity_python(vec_a, vec_b)

    @staticmethod
    def is_rust_available() -> bool:
        """Check if Rust acceleration is available."""
        return RUST_AVAILABLE
