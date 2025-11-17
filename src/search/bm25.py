"""BM25 keyword search implementation."""

import math
import re
from collections import defaultdict, Counter
from typing import List, Dict, Tuple, Set
import logging

logger = logging.getLogger(__name__)


class BM25:
    """
    BM25 (Best Matching 25) ranking function for keyword search.

    BM25 is a probabilistic ranking function that scores documents based on
    the query terms appearing in each document, regardless of their proximity.
    It's particularly effective for technical terms and exact matches.

    Parameters:
        k1: Controls term frequency saturation (default 1.5)
            - Higher values give more weight to term frequency
            - Typical range: 1.2 to 2.0
        b: Controls length normalization (default 0.75)
            - 0 = no normalization, 1 = full normalization
            - Penalizes longer documents
    """

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        """
        Initialize BM25 scorer.

        Args:
            k1: Term frequency saturation parameter
            b: Length normalization parameter
        """
        self.k1 = k1
        self.b = b

        # Document statistics
        self.corpus: List[List[str]] = []
        self.doc_freqs: Dict[str, int] = defaultdict(int)
        self.idf: Dict[str, float] = {}
        self.doc_len: List[int] = []
        self.avgdl: float = 0.0
        self.num_docs: int = 0

    def fit(self, corpus: List[str]) -> None:
        """
        Build BM25 index from corpus.

        Args:
            corpus: List of documents (strings) to index
        """
        self.corpus = []
        self.doc_freqs = defaultdict(int)
        self.doc_len = []

        # Tokenize and build statistics
        for doc in corpus:
            tokens = self._tokenize(doc)
            self.corpus.append(tokens)
            self.doc_len.append(len(tokens))

            # Count document frequency for each term
            unique_tokens = set(tokens)
            for token in unique_tokens:
                self.doc_freqs[token] += 1

        self.num_docs = len(corpus)
        self.avgdl = sum(self.doc_len) / self.num_docs if self.num_docs > 0 else 0.0

        # Calculate IDF for each term
        self._calculate_idf()

    def _tokenize(self, text: str) -> List[str]:
        """
        Tokenize text into terms.

        Simple tokenization that:
        - Lowercases text
        - Splits on non-alphanumeric characters
        - Preserves underscores (for identifiers like function_name)
        - Filters out very short tokens (< 2 chars)

        Args:
            text: Text to tokenize

        Returns:
            List of tokens
        """
        # Lowercase
        text = text.lower()

        # Split on non-alphanumeric (but preserve underscores)
        tokens = re.findall(r'[a-z0-9_]+', text)

        # Filter very short tokens
        tokens = [t for t in tokens if len(t) >= 2]

        return tokens

    def _calculate_idf(self) -> None:
        """Calculate IDF (Inverse Document Frequency) for all terms."""
        self.idf = {}

        for term, df in self.doc_freqs.items():
            # BM25 IDF formula: log((N - df + 0.5) / (df + 0.5))
            # Add 1 to avoid log(0)
            self.idf[term] = math.log(
                (self.num_docs - df + 0.5) / (df + 0.5) + 1.0
            )

    def get_scores(self, query: str) -> List[float]:
        """
        Calculate BM25 scores for all documents given a query.

        Args:
            query: Search query string

        Returns:
            List of scores (one per document)
        """
        query_tokens = self._tokenize(query)
        scores = [0.0] * self.num_docs

        # Calculate score for each document
        for doc_id in range(self.num_docs):
            score = self._score_document(doc_id, query_tokens)
            scores[doc_id] = score

        return scores

    def _score_document(self, doc_id: int, query_tokens: List[str]) -> float:
        """
        Calculate BM25 score for a specific document.

        Args:
            doc_id: Document index
            query_tokens: Tokenized query

        Returns:
            BM25 score
        """
        score = 0.0
        doc_tokens = self.corpus[doc_id]
        doc_len = self.doc_len[doc_id]

        # Count term frequencies in document
        doc_term_freqs = Counter(doc_tokens)

        # Score each query term
        for term in query_tokens:
            if term not in self.idf:
                continue  # Term not in corpus

            # Term frequency in document
            tf = doc_term_freqs.get(term, 0)

            # BM25 formula
            idf = self.idf[term]
            numerator = tf * (self.k1 + 1)
            denominator = tf + self.k1 * (
                1 - self.b + self.b * (doc_len / self.avgdl)
            )

            score += idf * (numerator / denominator)

        return score

    def search(
        self,
        query: str,
        top_k: int = 10
    ) -> List[Tuple[int, float]]:
        """
        Search for documents matching query.

        Args:
            query: Search query
            top_k: Number of top results to return

        Returns:
            List of (doc_id, score) tuples, sorted by score descending
        """
        scores = self.get_scores(query)

        # Create (doc_id, score) pairs
        doc_scores = [(i, score) for i, score in enumerate(scores)]

        # Sort by score descending
        doc_scores.sort(key=lambda x: x[1], reverse=True)

        # Return top k
        return doc_scores[:top_k]

    def get_top_k_documents(
        self,
        query: str,
        documents: List[str],
        top_k: int = 10
    ) -> List[Tuple[str, float]]:
        """
        Convenience method to search and return actual documents.

        Args:
            query: Search query
            documents: Original documents (must match corpus length)
            top_k: Number of results

        Returns:
            List of (document, score) tuples
        """
        if len(documents) != self.num_docs:
            raise ValueError(
                f"Document count mismatch: {len(documents)} vs {self.num_docs}"
            )

        results = self.search(query, top_k)
        return [(documents[doc_id], score) for doc_id, score in results]

    def get_term_stats(self) -> Dict[str, any]:
        """
        Get statistics about indexed terms.

        Returns:
            Dictionary with term statistics
        """
        return {
            "num_docs": self.num_docs,
            "num_terms": len(self.idf),
            "avg_doc_length": self.avgdl,
            "total_tokens": sum(self.doc_len),
        }


class BM25Plus(BM25):
    """
    BM25+ variant that addresses issues with long documents.

    BM25+ adds a small constant (delta) to the term frequency component
    to ensure that even rare terms contribute to the score.
    """

    def __init__(self, k1: float = 1.5, b: float = 0.75, delta: float = 1.0):
        """
        Initialize BM25+ scorer.

        Args:
            k1: Term frequency saturation parameter
            b: Length normalization parameter
            delta: Floor value for term frequency component
        """
        super().__init__(k1, b)
        self.delta = delta

    def _score_document(self, doc_id: int, query_tokens: List[str]) -> float:
        """Calculate BM25+ score (with delta adjustment)."""
        score = 0.0
        doc_tokens = self.corpus[doc_id]
        doc_len = self.doc_len[doc_id]

        doc_term_freqs = Counter(doc_tokens)

        for term in query_tokens:
            if term not in self.idf:
                continue

            tf = doc_term_freqs.get(term, 0)
            idf = self.idf[term]

            # BM25+ formula: adds delta to ensure minimum contribution
            numerator = tf * (self.k1 + 1)
            denominator = tf + self.k1 * (
                1 - self.b + self.b * (doc_len / self.avgdl)
            )

            score += idf * ((numerator / denominator) + self.delta)

        return score
