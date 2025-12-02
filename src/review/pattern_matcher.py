"""Pattern matching for code review."""

from dataclasses import dataclass
from typing import List, Dict
import logging

from .patterns import CodeSmellPattern
from ..embeddings.generator import EmbeddingGenerator

logger = logging.getLogger(__name__)


@dataclass
class PatternMatch:
    """Represents a match between code and a pattern."""

    pattern: CodeSmellPattern
    similarity_score: float
    matched_code: str
    confidence: str  # 'low' | 'medium' | 'high'


class PatternMatcher:
    """Match code against code smell patterns using semantic similarity."""

    def __init__(self, embedding_generator: EmbeddingGenerator):
        """
        Initialize pattern matcher.

        Args:
            embedding_generator: Generator for creating embeddings
        """
        self.embedding_generator = embedding_generator
        self._pattern_embeddings_cache: Dict[str, List[float]] = {}

    async def _get_pattern_embedding(self, pattern: CodeSmellPattern) -> List[float]:
        """
        Get or generate embedding for a pattern.

        Args:
            pattern: The pattern to embed

        Returns:
            Embedding vector for the pattern's example code
        """
        # Check cache first
        if pattern.id in self._pattern_embeddings_cache:
            return self._pattern_embeddings_cache[pattern.id]

        # Generate embedding from example code
        embedding = await self.embedding_generator.generate_embedding(
            pattern.example_code
        )

        # Cache it
        self._pattern_embeddings_cache[pattern.id] = embedding

        return embedding

    async def find_matches(
        self,
        code: str,
        language: str,
        patterns: List[CodeSmellPattern],
        threshold: float = 0.75,
    ) -> List[PatternMatch]:
        """
        Find patterns that match the given code.

        Args:
            code: The code to analyze
            language: Programming language of the code
            patterns: List of patterns to check against
            threshold: Minimum similarity score (0-1) to consider a match

        Returns:
            List of pattern matches sorted by similarity (highest first)
        """
        # Filter patterns by language
        applicable_patterns = [
            p
            for p in patterns
            if language.lower() in [lang.lower() for lang in p.languages]
        ]

        if not applicable_patterns:
            logger.debug(f"No applicable patterns for language: {language}")
            return []

        # Generate embedding for the code
        try:
            code_embedding = await self.embedding_generator.generate_embedding(code)
        except Exception as e:
            logger.error(f"Failed to generate code embedding: {e}")
            return []

        # Compare code against each pattern
        matches = []
        for pattern in applicable_patterns:
            try:
                # Get pattern embedding
                pattern_embedding = await self._get_pattern_embedding(pattern)

                # Calculate cosine similarity
                similarity = self._cosine_similarity(code_embedding, pattern_embedding)

                # Check if similarity exceeds threshold
                if similarity >= threshold:
                    # Determine confidence based on similarity
                    if similarity >= 0.90:
                        confidence = "high"
                    elif similarity >= 0.80:
                        confidence = "medium"
                    else:
                        confidence = "low"

                    matches.append(
                        PatternMatch(
                            pattern=pattern,
                            similarity_score=similarity,
                            matched_code=code,
                            confidence=confidence,
                        )
                    )

            except Exception as e:
                logger.error(f"Error matching pattern {pattern.id}: {e}")
                continue

        # Sort by similarity (highest first)
        matches.sort(key=lambda m: m.similarity_score, reverse=True)

        return matches

    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """
        Calculate cosine similarity between two vectors.

        Args:
            vec1: First vector
            vec2: Second vector

        Returns:
            Cosine similarity score (0-1)
        """
        if len(vec1) != len(vec2):
            raise ValueError("Vectors must have the same dimension")

        # Dot product
        dot_product = sum(a * b for a, b in zip(vec1, vec2))

        # Magnitudes
        mag1 = sum(a * a for a in vec1) ** 0.5
        mag2 = sum(b * b for b in vec2) ** 0.5

        # Handle zero vectors
        if mag1 == 0 or mag2 == 0:
            return 0.0

        # Cosine similarity
        similarity = dot_product / (mag1 * mag2)

        # Clamp to [0, 1] range (similarity should be positive)
        return max(0.0, min(1.0, similarity))

    async def clear_cache(self):
        """Clear the pattern embeddings cache.

        Note: This function is async for framework/interface compatibility, even
        though it doesn't currently use await. Future changes may add async operations.
        """
        self._pattern_embeddings_cache.clear()
        logger.info("Pattern embeddings cache cleared")
