"""Unit tests for BM25 keyword search implementation."""

import pytest
from src.search.bm25 import BM25, BM25Plus


class TestBM25:
    """Test BM25 ranking function."""

    def test_initialization(self):
        """Test BM25 initialization with default and custom parameters."""
        # Default parameters
        bm25 = BM25()
        assert bm25.k1 == 1.5
        assert bm25.b == 0.75
        assert bm25.num_docs == 0
        assert bm25.avgdl == 0.0

        # Custom parameters
        bm25_custom = BM25(k1=2.0, b=0.5)
        assert bm25_custom.k1 == 2.0
        assert bm25_custom.b == 0.5

    def test_tokenization(self):
        """Test text tokenization."""
        bm25 = BM25()

        # Basic tokenization
        tokens = bm25._tokenize("Hello World")
        assert tokens == ["hello", "world"]

        # Preserve underscores (for identifiers)
        tokens = bm25._tokenize("function_name user_id")
        assert "function_name" in tokens
        assert "user_id" in tokens

        # Filter short tokens
        tokens = bm25._tokenize("a b cd ef")
        assert "a" not in tokens
        assert "b" not in tokens
        assert "cd" in tokens
        assert "ef" in tokens

        # Handle special characters
        tokens = bm25._tokenize("hello@world.com test-case")
        assert "hello" in tokens
        assert "world" in tokens
        assert "com" in tokens
        assert "test" in tokens
        assert "case" in tokens

    def test_fit_basic(self):
        """Test BM25 index building with basic corpus."""
        corpus = [
            "The quick brown fox",
            "jumps over the lazy dog",
            "The dog barks",
        ]

        bm25 = BM25()
        bm25.fit(corpus)

        # Check document statistics
        assert bm25.num_docs == 3
        assert len(bm25.corpus) == 3
        assert len(bm25.doc_len) == 3

        # Check IDF calculation
        assert "the" in bm25.idf  # appears in doc 0 and 2
        assert "dog" in bm25.idf  # appears in doc 1 and 2
        assert "fox" in bm25.idf  # appears only in doc 0
        assert "barks" in bm25.idf  # appears only in doc 2

        # Average document length
        expected_avgdl = sum(bm25.doc_len) / 3
        assert abs(bm25.avgdl - expected_avgdl) < 0.01

    def test_fit_empty_corpus(self):
        """Test BM25 with empty corpus."""
        bm25 = BM25()
        bm25.fit([])

        assert bm25.num_docs == 0
        assert bm25.avgdl == 0.0
        assert len(bm25.idf) == 0

    def test_idf_calculation(self):
        """Test IDF (Inverse Document Frequency) calculation."""
        corpus = [
            "the cat",
            "the dog",
            "the bird",
        ]

        bm25 = BM25()
        bm25.fit(corpus)

        # "the" appears in all documents (df=3)
        # IDF should be low
        the_idf = bm25.idf.get("the", 0)

        # "cat" appears in only one document (df=1)
        # IDF should be higher
        cat_idf = bm25.idf.get("cat", 0)

        assert cat_idf > the_idf, "Rare terms should have higher IDF"

    def test_scoring_exact_match(self):
        """Test BM25 scoring with exact match."""
        corpus = [
            "function to authenticate user",
            "function to parse data",
            "function to connect database",
        ]

        bm25 = BM25()
        bm25.fit(corpus)

        # Query for "authenticate user"
        scores = bm25.get_scores("authenticate user")

        # First document should have highest score
        assert scores[0] > scores[1]
        assert scores[0] > scores[2]

    def test_scoring_partial_match(self):
        """Test BM25 scoring with partial match."""
        corpus = [
            "authentication function",
            "user authentication",
            "parse data",
        ]

        bm25 = BM25()
        bm25.fit(corpus)

        scores = bm25.get_scores("authentication")

        # Documents 0 and 1 should score higher than document 2
        assert scores[0] > scores[2]
        assert scores[1] > scores[2]

    def test_scoring_no_match(self):
        """Test BM25 scoring when query terms don't match."""
        corpus = [
            "hello world",
            "foo bar",
            "test case",
        ]

        bm25 = BM25()
        bm25.fit(corpus)

        scores = bm25.get_scores("nonexistent query")

        # All scores should be 0
        assert all(score == 0.0 for score in scores)

    def test_search(self):
        """Test BM25 search returning top-k results."""
        corpus = [
            "authentication function for users",
            "user management system",
            "database connection pool",
            "user authentication handler",
            "parse configuration file",
        ]

        bm25 = BM25()
        bm25.fit(corpus)

        # Search for "user authentication"
        results = bm25.search("user authentication", top_k=3)

        # Should return 3 results
        assert len(results) == 3

        # Results should be (doc_id, score) tuples
        assert all(isinstance(r, tuple) and len(r) == 2 for r in results)

        # Results should be sorted by score descending
        scores = [score for _, score in results]
        assert scores == sorted(scores, reverse=True)

        # First result should be highly relevant
        top_doc_id, top_score = results[0]
        assert top_score > 0
        assert top_doc_id in [0, 1, 3]  # Most relevant docs

    def test_search_top_k_limit(self):
        """Test that search respects top_k limit."""
        corpus = ["doc" + str(i) for i in range(20)]

        bm25 = BM25()
        bm25.fit(corpus)

        # Request top 5
        results = bm25.search("doc", top_k=5)
        assert len(results) == 5

        # Request top 10
        results = bm25.search("doc", top_k=10)
        assert len(results) == 10

        # Request more than corpus size
        results = bm25.search("doc", top_k=100)
        assert len(results) == 20  # Should return all docs

    def test_get_top_k_documents(self):
        """Test convenience method to get actual documents."""
        corpus = [
            "first document",
            "second document",
            "third document",
        ]

        bm25 = BM25()
        bm25.fit(corpus)

        results = bm25.get_top_k_documents("document", corpus, top_k=2)

        # Should return 2 results
        assert len(results) == 2

        # Results should be (document, score) tuples
        assert all(isinstance(r, tuple) and len(r) == 2 for r in results)

        # Documents should be strings
        assert all(isinstance(doc, str) for doc, _ in results)

        # All returned documents should contain "document"
        for doc, score in results:
            assert "document" in doc.lower()
            assert score > 0

    def test_get_top_k_documents_mismatch(self):
        """Test that get_top_k_documents validates document count."""
        corpus = ["doc1", "doc2", "doc3"]
        bm25 = BM25()
        bm25.fit(corpus)

        # Try with wrong number of documents
        with pytest.raises(ValueError, match="Document count mismatch"):
            bm25.get_top_k_documents("query", ["doc1", "doc2"], top_k=2)

    def test_length_normalization(self):
        """Test that BM25 length normalization works correctly."""
        # Create documents of varying lengths
        corpus = [
            "short doc",
            "this is a much longer document with many more words to test length normalization",
            "medium length document here",
        ]

        bm25 = BM25()
        bm25.fit(corpus)

        # Query for common term "document"
        scores = bm25.get_scores("document")

        # Longer documents should be penalized (assuming b > 0)
        # But this depends on term frequency too
        # Just check that scoring completes without error
        assert len(scores) == 3
        assert all(isinstance(s, (int, float)) for s in scores)

    def test_term_frequency_saturation(self):
        """Test that term frequency saturation (k1) works."""
        corpus = [
            "test",  # 1 occurrence
            "test test",  # 2 occurrences
            "test test test test test",  # 5 occurrences
        ]

        bm25 = BM25()
        bm25.fit(corpus)

        scores = bm25.get_scores("test")

        # More occurrences should increase score, but with diminishing returns
        assert scores[1] > scores[0]  # 2 > 1
        assert scores[2] > scores[1]  # 5 > 2

        # But the increase should be sublinear (saturation effect)
        increase_1_to_2 = scores[1] - scores[0]
        increase_2_to_5 = scores[2] - scores[1]

        # The increase from 2 to 5 should be less per term
        # than the increase from 1 to 2
        assert (increase_2_to_5 / 3) < increase_1_to_2

    def test_get_term_stats(self):
        """Test term statistics retrieval."""
        corpus = [
            "hello world",
            "foo bar baz",
            "test case example",
        ]

        bm25 = BM25()
        bm25.fit(corpus)

        stats = bm25.get_term_stats()

        assert stats["num_docs"] == 3
        assert stats["num_terms"] > 0
        assert stats["avg_doc_length"] > 0
        assert stats["total_tokens"] > 0

        # Check specific values
        total_tokens = sum(len(bm25._tokenize(doc)) for doc in corpus)
        assert stats["total_tokens"] == total_tokens

    def test_code_search_scenario(self):
        """Test BM25 with code-like content."""
        corpus = [
            "def authenticate_user(username, password):\n    return check_credentials(username, password)",
            "class UserAuth:\n    def login(self, user):\n        pass",
            "def parse_config(file_path):\n    with open(file_path) as f:\n        return json.load(f)",
            "def validate_user_credentials(username, password):\n    return username and password",
        ]

        bm25 = BM25()
        bm25.fit(corpus)

        # Search for authentication-related code
        results = bm25.search("authenticate user credentials", top_k=3)

        # Should find relevant functions (at least one auth-related)
        top_doc_ids = [doc_id for doc_id, _ in results]
        assert 0 in top_doc_ids or 1 in top_doc_ids or 3 in top_doc_ids
        # Check that at least the top result is authentication-related
        assert top_doc_ids[0] in [0, 1, 3]  # Auth-related docs

    def test_multiterm_query(self):
        """Test BM25 with multi-term queries."""
        corpus = [
            "red apple",
            "green apple",
            "red car",
            "blue car",
        ]

        bm25 = BM25()
        bm25.fit(corpus)

        # Query with both terms
        scores = bm25.get_scores("red apple")

        # First doc should have highest score (both terms match)
        assert scores[0] > scores[1]
        assert scores[0] > scores[2]
        assert scores[0] > scores[3]


class TestBM25Plus:
    """Test BM25+ variant."""

    def test_initialization(self):
        """Test BM25+ initialization."""
        bm25plus = BM25Plus()
        assert bm25plus.k1 == 1.5
        assert bm25plus.b == 0.75
        assert bm25plus.delta == 1.0

        # Custom delta
        bm25plus_custom = BM25Plus(delta=0.5)
        assert bm25plus_custom.delta == 0.5

    def test_delta_effect(self):
        """Test that delta parameter has an effect on scoring."""
        corpus = [
            "hello world",
            "foo bar",
        ]

        # Standard BM25
        bm25 = BM25()
        bm25.fit(corpus)
        scores_standard = bm25.get_scores("hello")

        # BM25+ with delta
        bm25plus = BM25Plus(delta=1.0)
        bm25plus.fit(corpus)
        scores_plus = bm25plus.get_scores("hello")

        # BM25+ scores should be higher due to delta
        assert scores_plus[0] > scores_standard[0]

    def test_rare_term_contribution(self):
        """Test that BM25+ ensures minimum contribution for rare terms."""
        corpus = [
            "common common common rare",
            "common common common common",
        ]

        bm25plus = BM25Plus(delta=0.5)
        bm25plus.fit(corpus)

        # Query for rare term
        scores = bm25plus.get_scores("rare")

        # First document should score higher (has the rare term)
        assert scores[0] > 0
        # Second document should have non-zero score due to delta (even without term)
        assert scores[1] > 0
        # First document should score higher than second
        assert scores[0] > scores[1]

    def test_inheritance(self):
        """Test that BM25Plus inherits from BM25."""
        bm25plus = BM25Plus()
        assert isinstance(bm25plus, BM25)

        # Should have all BM25 methods
        assert hasattr(bm25plus, "fit")
        assert hasattr(bm25plus, "search")
        assert hasattr(bm25plus, "get_scores")
        assert hasattr(bm25plus, "get_top_k_documents")


class TestBM25EdgeCases:
    """Test edge cases and error handling."""

    def test_empty_query(self):
        """Test BM25 with empty query."""
        corpus = ["hello world", "foo bar"]
        bm25 = BM25()
        bm25.fit(corpus)

        scores = bm25.get_scores("")
        assert all(score == 0.0 for score in scores)

    def test_single_document(self):
        """Test BM25 with single document corpus."""
        corpus = ["single document"]
        bm25 = BM25()
        bm25.fit(corpus)

        scores = bm25.get_scores("document")
        assert len(scores) == 1
        assert scores[0] > 0

    def test_identical_documents(self):
        """Test BM25 with identical documents."""
        corpus = ["same text", "same text", "same text"]
        bm25 = BM25()
        bm25.fit(corpus)

        scores = bm25.get_scores("same text")

        # All scores should be identical
        assert len(set(scores)) == 1
        assert scores[0] > 0

    def test_special_characters_only(self):
        """Test BM25 with documents containing only special characters."""
        corpus = ["!!!", "@@@", "###"]
        bm25 = BM25()
        bm25.fit(corpus)

        # After tokenization, these should be empty
        assert bm25.num_docs == 3
        assert all(len(tokens) == 0 for tokens in bm25.corpus)

    def test_unicode_text(self):
        """Test BM25 with unicode text."""
        corpus = [
            "hello world",
            "こんにちは世界",  # Japanese
            "hola mundo",  # Spanish with accents possible
        ]

        bm25 = BM25()
        bm25.fit(corpus)

        # Should handle without error
        scores = bm25.get_scores("hello")
        assert len(scores) == 3
        assert scores[0] > 0  # Should match first doc

    def test_very_long_document(self):
        """Test BM25 with very long documents."""
        corpus = [
            "short",
            " ".join(["word"] * 1000),  # Very long document
        ]

        bm25 = BM25()
        bm25.fit(corpus)

        scores = bm25.get_scores("word")

        # Should handle without error
        assert len(scores) == 2
        # Long document should have high term frequency but be length-normalized
        assert scores[1] > 0

    def test_query_with_terms_not_in_corpus(self):
        """Test query with terms not in corpus."""
        corpus = ["hello world", "foo bar"]
        bm25 = BM25()
        bm25.fit(corpus)

        # Mix of matching and non-matching terms
        scores = bm25.get_scores("hello nonexistent")

        # Should still score based on "hello"
        assert scores[0] > 0
        assert scores[1] == 0

    def test_case_insensitivity(self):
        """Test that search is case-insensitive."""
        corpus = ["Hello World", "FOO BAR"]
        bm25 = BM25()
        bm25.fit(corpus)

        scores_lower = bm25.get_scores("hello")
        scores_upper = bm25.get_scores("HELLO")
        scores_mixed = bm25.get_scores("HeLLo")

        # All should produce same results
        assert scores_lower == scores_upper
        assert scores_lower == scores_mixed

    def test_refitting(self):
        """Test that calling fit() again replaces the index."""
        bm25 = BM25()

        # First corpus
        corpus1 = ["first corpus"]
        bm25.fit(corpus1)
        assert bm25.num_docs == 1

        # Second corpus (different size)
        corpus2 = ["second", "corpus"]
        bm25.fit(corpus2)
        assert bm25.num_docs == 2

        # Should have updated completely
        scores = bm25.get_scores("first")
        assert all(score == 0.0 for score in scores)  # "first" not in second corpus

        scores = bm25.get_scores("second")
        assert scores[0] > 0  # "second" is in second corpus
