"""Semantic query expansion using conversation context, synonyms, and code patterns."""

import logging
import re
from typing import List, Set, Optional
import numpy as np

from src.config import ServerConfig
from src.embeddings.generator import EmbeddingGenerator
from src.memory.conversation_tracker import QueryRecord
from src.search.query_synonyms import expand_with_synonyms, expand_with_code_context

logger = logging.getLogger(__name__)


def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """
    Calculate cosine similarity between two vectors.

    Args:
        vec1: First vector
        vec2: Second vector

    Returns:
        Similarity score (0-1)
    """
    arr1 = np.array(vec1)
    arr2 = np.array(vec2)

    # Handle edge cases
    if len(arr1) == 0 or len(arr2) == 0:
        return 0.0

    # Normalize
    norm1 = np.linalg.norm(arr1)
    norm2 = np.linalg.norm(arr2)

    if norm1 == 0 or norm2 == 0:
        return 0.0

    # Cosine similarity
    similarity = np.dot(arr1, arr2) / (norm1 * norm2)

    # Clamp to [0, 1]
    return float(max(0.0, min(1.0, similarity)))


def extract_key_terms(text: str, min_length: int = 3) -> Set[str]:
    """
    Extract key terms from text.

    Args:
        text: Input text
        min_length: Minimum term length

    Returns:
        Set of key terms
    """
    # Remove punctuation and convert to lowercase
    text = re.sub(r"[^\w\s]", " ", text.lower())

    # Split into words
    words = text.split()

    # Common stop words to exclude
    stop_words = {
        "the",
        "a",
        "an",
        "and",
        "or",
        "but",
        "in",
        "on",
        "at",
        "to",
        "for",
        "of",
        "with",
        "by",
        "from",
        "up",
        "about",
        "into",
        "through",
        "during",
        "before",
        "after",
        "above",
        "below",
        "between",
        "under",
        "again",
        "further",
        "then",
        "once",
        "here",
        "there",
        "when",
        "where",
        "why",
        "how",
        "all",
        "both",
        "each",
        "few",
        "more",
        "most",
        "other",
        "some",
        "such",
        "no",
        "nor",
        "not",
        "only",
        "own",
        "same",
        "so",
        "than",
        "too",
        "very",
        "can",
        "will",
        "just",
        "should",
        "now",
        "what",
        "does",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "have",
        "has",
        "had",
        "having",
        "do",
        "did",
        "doing",
    }

    # Filter and return
    return {
        word for word in words if len(word) >= min_length and word not in stop_words
    }


class QueryExpander:
    """
    Expand queries using conversation context and semantic similarity.

    Uses embeddings to identify related previous queries and incorporates
    their key terms to improve relevance.
    """

    def __init__(self, config: ServerConfig, embedding_generator: EmbeddingGenerator):
        """
        Initialize query expander.

        Args:
            config: Server configuration
            embedding_generator: Embedding generator for semantic comparison
        """
        self.config = config
        self.embedding_generator = embedding_generator

        # Statistics
        self.stats = {
            "queries_expanded": 0,
            "expansions_applied": 0,
            "avg_expansion_length": 0.0,
            "synonym_expansions": 0,
            "context_expansions": 0,
            "conversation_expansions": 0,
        }

    async def expand_query(
        self,
        query: str,
        recent_queries: List[QueryRecord],
    ) -> str:
        """
        Expand query using conversation context.

        Args:
            query: Current query
            recent_queries: Recent queries from conversation

        Returns:
            Expanded query (or original if no expansion needed)
        """
        if not recent_queries:
            return query  # No context to use

        if not self.config.memory.conversation_tracking:
            return query  # Feature disabled

        try:
            # Generate embedding for current query
            current_embedding = await self.embedding_generator.generate(query)

            # Find related queries
            related_terms = await self._find_related_terms(
                current_embedding, recent_queries
            )

            # Apply expansion if we found related terms
            if related_terms:
                expanded = self._apply_expansion(query, related_terms)
                self.stats["queries_expanded"] += 1
                self.stats["expansions_applied"] += len(related_terms)

                logger.debug(
                    f"Expanded query: '{query}' -> '{expanded}' "
                    f"(added {len(related_terms)} terms)"
                )

                return expanded

            return query

        except Exception as e:
            logger.error(f"Error expanding query: {e}")
            return query  # Fallback to original

    async def _find_related_terms(
        self,
        current_embedding: List[float],
        recent_queries: List[QueryRecord],
    ) -> Set[str]:
        """
        Find key terms from semantically related queries.

        Args:
            current_embedding: Embedding of current query
            recent_queries: Recent query records

        Returns:
            Set of related terms to add
        """
        related_terms = set()

        for record in recent_queries:
            # Get or generate embedding for past query
            if record.query_embedding:
                past_embedding = record.query_embedding
            else:
                past_embedding = await self.embedding_generator.generate(record.query)

            # Calculate similarity
            similarity = cosine_similarity(current_embedding, past_embedding)

            # If similar enough, extract key terms
            if similarity >= self.config.query_expansion_similarity_threshold:
                terms = extract_key_terms(record.query)
                related_terms.update(terms)

                logger.debug(
                    f"Found related query (similarity: {similarity:.3f}): "
                    f"'{record.query}' -> {terms}"
                )

        return related_terms

    def _apply_expansion(self, query: str, related_terms: Set[str]) -> str:
        """
        Apply expansion terms to query.

        Args:
            query: Original query
            related_terms: Terms to add

        Returns:
            Expanded query
        """
        # Extract terms from current query to avoid duplicates
        current_terms = extract_key_terms(query)

        # Only add new terms
        new_terms = related_terms - current_terms

        if not new_terms:
            return query

        # Limit expansion (max 5 additional terms)
        max_expansion_terms = 5
        terms_to_add = list(new_terms)[:max_expansion_terms]

        # Build expanded query
        expansion_str = " ".join(terms_to_add)
        expanded = f"{query} {expansion_str}"

        # Update stats
        expansion_length = len(terms_to_add)
        total_expansions = self.stats["queries_expanded"] + 1
        current_avg = self.stats["avg_expansion_length"]
        self.stats["avg_expansion_length"] = (
            current_avg * (total_expansions - 1) + expansion_length
        ) / total_expansions

        return expanded

    def expand_with_synonyms_and_context(
        self,
        query: str,
        enable_synonyms: bool = True,
        enable_context: bool = True,
    ) -> str:
        """
        Expand query with programming synonyms and code context.

        This is a lightweight expansion that doesn't require embeddings.
        Uses predefined programming term synonyms and code context patterns.

        Args:
            query: Original query
            enable_synonyms: Enable synonym expansion
            enable_context: Enable code context expansion

        Returns:
            Expanded query
        """
        if not enable_synonyms and not enable_context:
            return query

        expanded = query

        try:
            # Apply synonym expansion
            if enable_synonyms:
                expanded_with_synonyms = expand_with_synonyms(expanded, max_synonyms=2)
                if expanded_with_synonyms != expanded:
                    self.stats["synonym_expansions"] += 1
                    logger.debug(
                        f"Added synonyms: '{expanded}' -> '{expanded_with_synonyms}'"
                    )
                    expanded = expanded_with_synonyms

            # Apply code context expansion
            if enable_context:
                expanded_with_context = expand_with_code_context(
                    expanded, max_context_terms=3
                )
                if expanded_with_context != expanded:
                    self.stats["context_expansions"] += 1
                    logger.debug(
                        f"Added context: '{expanded}' -> '{expanded_with_context}'"
                    )
                    expanded = expanded_with_context

            # Update overall stats if query was expanded
            if expanded != query:
                self.stats["queries_expanded"] += 1

            return expanded

        except Exception as e:
            logger.error(f"Error in synonym/context expansion: {e}")
            return query  # Fallback to original

    async def expand_query_full(
        self,
        query: str,
        recent_queries: Optional[List[QueryRecord]] = None,
        enable_synonyms: bool = True,
        enable_context: bool = True,
        enable_conversation: bool = True,
    ) -> str:
        """
        Full query expansion using all available methods.

        Combines:
        1. Synonym expansion (programming terms)
        2. Code context expansion (domain patterns)
        3. Conversation-based expansion (semantic similarity)

        Args:
            query: Original query
            recent_queries: Recent queries from conversation (optional)
            enable_synonyms: Enable synonym expansion
            enable_context: Enable code context expansion
            enable_conversation: Enable conversation-based expansion

        Returns:
            Fully expanded query
        """
        expanded = query

        # Phase 1: Synonym and context expansion (lightweight, no embeddings)
        if enable_synonyms or enable_context:
            expanded = self.expand_with_synonyms_and_context(
                expanded,
                enable_synonyms=enable_synonyms,
                enable_context=enable_context,
            )

        # Phase 2: Conversation-based expansion (requires embeddings)
        if enable_conversation and recent_queries:
            expanded = await self.expand_query(expanded, recent_queries)

            # Track conversation expansion separately
            if expanded != query:
                self.stats["conversation_expansions"] += 1

        return expanded

    def get_stats(self) -> dict:
        """Get expansion statistics."""
        return self.stats.copy()
