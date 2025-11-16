"""Embedding generation using sentence-transformers."""

import logging
from sentence_transformers import SentenceTransformer
import numpy as np
from typing import List, Union

logger = logging.getLogger(__name__)


class EmbeddingGenerator:
    """Generates embeddings for text using local sentence-transformers model."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        """
        Initialize the embedding generator.

        Args:
            model_name: Name of the sentence-transformers model to use.
                       Default is 'all-MiniLM-L6-v2' (fast, ~80MB, good quality)
        """
        logger.info(f"Loading embedding model '{model_name}'...")
        self.model = SentenceTransformer(model_name)
        logger.info(f"Model loaded! Embedding dimension: {self.model.get_sentence_embedding_dimension()}")

    def generate(self, text: Union[str, List[str]]) -> Union[np.ndarray, List[np.ndarray]]:
        """
        Generate embeddings for text.

        Args:
            text: Single string or list of strings to embed

        Returns:
            Numpy array (single text) or list of numpy arrays (multiple texts)
        """
        embeddings = self.model.encode(text, convert_to_numpy=True)
        return embeddings

    def generate_batch(self, texts: List[str]) -> np.ndarray:
        """
        Generate embeddings for multiple texts efficiently.

        Args:
            texts: List of strings to embed

        Returns:
            2D numpy array where each row is an embedding
        """
        return self.model.encode(texts, convert_to_numpy=True, show_progress_bar=False)

    @property
    def dimension(self) -> int:
        """Get the embedding dimension."""
        return self.model.get_sentence_embedding_dimension()
