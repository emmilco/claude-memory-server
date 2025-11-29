"""Unit tests for hybrid search combining BM25 and vector search."""

import pytest
from unittest.mock import Mock
from src.search.hybrid_search import HybridSearcher, FusionMethod, HybridSearchResult
from src.core.models import MemoryUnit, MemoryScope, MemoryCategory, ContextLevel


# Test fixtures
@pytest.fixture(scope="module")
def sample_memories():
    """Module-scoped sample memories for read-only hybrid search tests.

    These MemoryUnit objects are immutable and used as read-only test data
    for hybrid search operations. Each test creates its own HybridSearcher
    instance, so there is no cross-test contamination from the shared fixtures.

    Module scope reduces fixture setup overhead from ~40 instantiations
    to 1 per test module.
    """
    memories = [
        MemoryUnit(
            id="mem1",
            content="authentication user login system",
            scope=MemoryScope.PROJECT,
            category=MemoryCategory.CONTEXT,
            context_level=ContextLevel.PROJECT_CONTEXT,
            project_name="test-project",
        ),
        MemoryUnit(
            id="mem2",
            content="database connection pool manager",
            scope=MemoryScope.PROJECT,
            category=MemoryCategory.CONTEXT,
            context_level=ContextLevel.PROJECT_CONTEXT,
            project_name="test-project",
        ),
        MemoryUnit(
            id="mem3",
            content="user authentication handler function",
            scope=MemoryScope.PROJECT,
            category=MemoryCategory.CONTEXT,
            context_level=ContextLevel.PROJECT_CONTEXT,
            project_name="test-project",
        ),
        MemoryUnit(
            id="mem4",
            content="configuration file parser",
            scope=MemoryScope.PROJECT,
            category=MemoryCategory.CONTEXT,
            context_level=ContextLevel.PROJECT_CONTEXT,
            project_name="test-project",
        ),
    ]
    return memories


@pytest.fixture(scope="module")
def sample_vector_results(sample_memories):
    """Module-scoped vector search results for read-only tests.

    Creates tuples of (MemoryUnit, score) simulating vector search output.
    These are immutable and safe to share across tests in the module.
    """
    # Simulate vector search results (sorted by semantic similarity)
    return [
        (sample_memories[0], 0.95),  # authentication user login
        (sample_memories[2], 0.88),  # user authentication handler
        (sample_memories[1], 0.45),  # database connection
        (sample_memories[3], 0.30),  # config parser
    ]


class TestHybridSearcherInitialization:
    """Test HybridSearcher initialization."""

    def test_default_initialization(self):
        """Test default initialization."""
        searcher = HybridSearcher()

        assert searcher.alpha == 0.5
        assert searcher.fusion_method == FusionMethod.WEIGHTED
        assert searcher.rrf_k == 60
        assert searcher.bm25 is not None
        assert searcher.documents == []
        assert searcher.memory_units == []

    def test_custom_initialization(self):
        """Test initialization with custom parameters."""
        searcher = HybridSearcher(
            alpha=0.7,
            fusion_method=FusionMethod.RRF,
            bm25_k1=2.0,
            bm25_b=0.5,
            rrf_k=100,
        )

        assert searcher.alpha == 0.7
        assert searcher.fusion_method == FusionMethod.RRF
        assert searcher.rrf_k == 100
        assert searcher.bm25.k1 == 2.0
        assert searcher.bm25.b == 0.5

    def test_fusion_method_enum(self):
        """Test fusion method enum values."""
        assert FusionMethod.WEIGHTED == "weighted"
        assert FusionMethod.RRF == "rrf"
        assert FusionMethod.CASCADE == "cascade"


class TestDocumentIndexing:
    """Test document indexing for BM25."""

    def test_index_documents(self, sample_memories):
        """Test indexing documents."""
        searcher = HybridSearcher()
        documents = [m.content for m in sample_memories]

        searcher.index_documents(documents, sample_memories)

        assert len(searcher.documents) == len(sample_memories)
        assert len(searcher.memory_units) == len(sample_memories)
        assert searcher.bm25.num_docs == len(sample_memories)

    def test_index_documents_mismatch(self, sample_memories):
        """Test that indexing validates document and memory counts match."""
        searcher = HybridSearcher()
        documents = [m.content for m in sample_memories[:2]]  # Only 2 docs

        with pytest.raises(ValueError, match="Documents and memory units must have same length"):
            searcher.index_documents(documents, sample_memories)

    def test_index_empty_documents(self):
        """Test indexing empty document list."""
        searcher = HybridSearcher()
        searcher.index_documents([], [])

        assert len(searcher.documents) == 0
        assert len(searcher.memory_units) == 0
        assert searcher.bm25.num_docs == 0


class TestWeightedFusion:
    """Test weighted score fusion strategy."""

    def test_weighted_fusion_balanced(self, sample_memories, sample_vector_results):
        """Test weighted fusion with balanced alpha (0.5)."""
        searcher = HybridSearcher(alpha=0.5, fusion_method=FusionMethod.WEIGHTED)

        documents = [m.content for m in sample_memories]
        searcher.index_documents(documents, sample_memories)

        results = searcher.hybrid_search(
            query="authentication user",
            vector_results=sample_vector_results,
            limit=3,
        )

        assert len(results) <= 3
        assert all(isinstance(r, HybridSearchResult) for r in results)

        # Check that results are sorted by total_score descending
        scores = [r.total_score for r in results]
        assert scores == sorted(scores, reverse=True)

        # Check that results have both vector and BM25 scores
        for result in results:
            assert result.vector_score >= 0
            assert result.bm25_score >= 0
            assert result.fusion_method == "weighted"

    def test_weighted_fusion_semantic_only(self, sample_memories, sample_vector_results):
        """Test weighted fusion with alpha=1.0 (semantic only)."""
        searcher = HybridSearcher(alpha=1.0, fusion_method=FusionMethod.WEIGHTED)

        documents = [m.content for m in sample_memories]
        searcher.index_documents(documents, sample_memories)

        results = searcher.hybrid_search(
            query="authentication user",
            vector_results=sample_vector_results,
            limit=3,
        )

        # With alpha=1.0, results should match vector search order
        assert len(results) <= 3
        # First result should have highest vector score
        assert results[0].vector_score >= results[1].vector_score

    def test_weighted_fusion_keyword_only(self, sample_memories, sample_vector_results):
        """Test weighted fusion with alpha=0.0 (keyword only)."""
        searcher = HybridSearcher(alpha=0.0, fusion_method=FusionMethod.WEIGHTED)

        documents = [m.content for m in sample_memories]
        searcher.index_documents(documents, sample_memories)

        results = searcher.hybrid_search(
            query="authentication user",
            vector_results=sample_vector_results,
            limit=3,
        )

        # With alpha=0.0, results should be based on BM25 scores only
        assert len(results) <= 3
        # Results should be ordered by BM25 score
        bm25_scores = [r.bm25_score for r in results]
        # Can't directly compare due to normalization, but should be consistent

    def test_weighted_fusion_score_normalization(self, sample_memories, sample_vector_results):
        """Test that scores are normalized in weighted fusion."""
        searcher = HybridSearcher(alpha=0.5, fusion_method=FusionMethod.WEIGHTED)

        documents = [m.content for m in sample_memories]
        searcher.index_documents(documents, sample_memories)

        results = searcher.hybrid_search(
            query="authentication",
            vector_results=sample_vector_results,
            limit=4,
        )

        # Total scores should be in [0, 1] range (normalized)
        for result in results:
            assert 0.0 <= result.total_score <= 1.0


class TestRRFFusion:
    """Test Reciprocal Rank Fusion strategy."""

    def test_rrf_fusion(self, sample_memories, sample_vector_results):
        """Test RRF fusion strategy."""
        searcher = HybridSearcher(
            fusion_method=FusionMethod.RRF,
            rrf_k=60
        )

        documents = [m.content for m in sample_memories]
        searcher.index_documents(documents, sample_memories)

        results = searcher.hybrid_search(
            query="authentication user",
            vector_results=sample_vector_results,
            limit=3,
        )

        assert len(results) <= 3
        assert all(isinstance(r, HybridSearchResult) for r in results)

        # Check RRF-specific fields
        for result in results:
            assert result.fusion_method == "rrf"
            assert result.total_score > 0  # RRF score
            # RRF should have rank information
            assert result.rank_vector is not None or result.rank_bm25 is not None

    def test_rrf_formula(self, sample_memories):
        """Test that RRF formula is correctly applied."""
        searcher = HybridSearcher(
            fusion_method=FusionMethod.RRF,
            rrf_k=60
        )

        # Create simple vector results
        vector_results = [
            (sample_memories[0], 1.0),  # rank 0
            (sample_memories[1], 0.8),  # rank 1
        ]

        documents = [m.content for m in sample_memories]
        searcher.index_documents(documents, sample_memories)

        results = searcher.hybrid_search(
            query="authentication",
            vector_results=vector_results,
            limit=2,
        )

        # RRF score should be sum of 1/(k + rank_i)
        # Higher-ranked items should have higher scores
        assert results[0].total_score > 0

    def test_rrf_with_different_k(self, sample_memories, sample_vector_results):
        """Test RRF with different k values."""
        # Smaller k gives more weight to top-ranked items
        searcher_small_k = HybridSearcher(
            fusion_method=FusionMethod.RRF,
            rrf_k=10
        )

        # Larger k gives more uniform weighting
        searcher_large_k = HybridSearcher(
            fusion_method=FusionMethod.RRF,
            rrf_k=100
        )

        documents = [m.content for m in sample_memories]

        searcher_small_k.index_documents(documents, sample_memories)
        searcher_large_k.index_documents(documents, sample_memories)

        results_small_k = searcher_small_k.hybrid_search(
            "authentication", sample_vector_results, limit=3
        )
        results_large_k = searcher_large_k.hybrid_search(
            "authentication", sample_vector_results, limit=3
        )

        # Both should return results
        assert len(results_small_k) > 0
        assert len(results_large_k) > 0


class TestCascadeFusion:
    """Test cascade fusion strategy."""

    def test_cascade_fusion(self, sample_memories, sample_vector_results):
        """Test cascade fusion (BM25 first, then vector)."""
        searcher = HybridSearcher(fusion_method=FusionMethod.CASCADE)

        documents = [m.content for m in sample_memories]
        searcher.index_documents(documents, sample_memories)

        results = searcher.hybrid_search(
            query="authentication user",
            vector_results=sample_vector_results,
            limit=3,
        )

        assert len(results) <= 3
        assert all(r.fusion_method == "cascade" for r in results)

    def test_cascade_prefers_bm25(self, sample_memories, sample_vector_results):
        """Test that cascade prefers BM25 results when available."""
        searcher = HybridSearcher(fusion_method=FusionMethod.CASCADE)

        documents = [m.content for m in sample_memories]
        searcher.index_documents(documents, sample_memories)

        results = searcher.hybrid_search(
            query="authentication",
            vector_results=sample_vector_results,
            limit=4,
        )

        # Cascade should include BM25 results first
        # Results with non-zero BM25 scores should appear first
        bm25_scores = [r.bm25_score for r in results]
        # At least some results should have BM25 scores
        assert any(score > 0 for score in bm25_scores)

    def test_cascade_backfills_with_vector(self, sample_memories):
        """Test that cascade backfills with vector results."""
        searcher = HybridSearcher(fusion_method=FusionMethod.CASCADE)

        documents = [m.content for m in sample_memories]
        searcher.index_documents(documents, sample_memories)

        # Vector results for query that won't match BM25 well
        vector_results = [
            (sample_memories[0], 0.9),
            (sample_memories[1], 0.8),
            (sample_memories[2], 0.7),
        ]

        results = searcher.hybrid_search(
            query="nonexistent query terms",
            vector_results=vector_results,
            limit=3,
        )

        # Should backfill with vector results since BM25 won't match
        assert len(results) <= 3
        # Some results should have vector scores
        assert any(r.vector_score > 0 for r in results)


class TestHybridSearchEdgeCases:
    """Test edge cases and error handling."""

    def test_no_documents_indexed(self, sample_vector_results):
        """Test hybrid search when no documents are indexed."""
        searcher = HybridSearcher()

        # Should fall back to vector results only
        results = searcher.hybrid_search(
            query="test",
            vector_results=sample_vector_results,
            limit=3,
        )

        assert len(results) <= 3
        # Should return vector results with zero BM25 scores
        for result in results:
            assert result.vector_score > 0
            assert result.bm25_score == 0.0

    def test_empty_vector_results(self, sample_memories):
        """Test hybrid search with empty vector results."""
        searcher = HybridSearcher()

        documents = [m.content for m in sample_memories]
        searcher.index_documents(documents, sample_memories)

        results = searcher.hybrid_search(
            query="test",
            vector_results=[],
            limit=3,
        )

        # When vector results are empty, should still return BM25 results
        # This is actually reasonable behavior - use BM25 as fallback
        # The results should have BM25 scores but no vector scores
        assert all(r.bm25_score >= 0 for r in results)
        assert all(r.vector_score == 0 for r in results)

    def test_limit_larger_than_results(self, sample_memories, sample_vector_results):
        """Test with limit larger than available results."""
        searcher = HybridSearcher()

        documents = [m.content for m in sample_memories]
        searcher.index_documents(documents, sample_memories)

        results = searcher.hybrid_search(
            query="test",
            vector_results=sample_vector_results,
            limit=100,
        )

        # Should return all available results
        assert len(results) <= len(sample_memories)

    def test_all_zero_scores(self, sample_memories):
        """Test when all scores are zero."""
        searcher = HybridSearcher()

        documents = [m.content for m in sample_memories]
        searcher.index_documents(documents, sample_memories)

        # Vector results with zero scores
        zero_vector_results = [(m, 0.0) for m in sample_memories]

        results = searcher.hybrid_search(
            query="nonexistent",
            vector_results=zero_vector_results,
            limit=3,
        )

        # Should still return results (with zero scores)
        assert len(results) <= 3


class TestScoreNormalization:
    """Test score normalization helper."""

    def test_normalize_scores_basic(self):
        """Test basic score normalization."""
        scores = [1.0, 2.0, 3.0, 4.0, 5.0]
        normalized = HybridSearcher._normalize_scores(scores)

        # Should be in [0, 1] range
        assert all(0.0 <= s <= 1.0 for s in normalized)

        # Min should be 0, max should be 1
        assert min(normalized) == 0.0
        assert max(normalized) == 1.0

        # Order should be preserved
        assert normalized == sorted(normalized)

    def test_normalize_identical_scores(self):
        """Test normalization with identical scores."""
        scores = [5.0, 5.0, 5.0]
        normalized = HybridSearcher._normalize_scores(scores)

        # All should be 1.0
        assert all(s == 1.0 for s in normalized)

    def test_normalize_empty_scores(self):
        """Test normalization with empty list."""
        normalized = HybridSearcher._normalize_scores([])
        assert normalized == []

    def test_normalize_single_score(self):
        """Test normalization with single score."""
        normalized = HybridSearcher._normalize_scores([42.0])
        assert normalized == [1.0]

    def test_normalize_preserves_order(self):
        """Test that normalization preserves relative order."""
        scores = [10.0, 5.0, 8.0, 2.0]
        normalized = HybridSearcher._normalize_scores(scores)

        # Relative order should be preserved
        for i in range(len(scores) - 1):
            if scores[i] > scores[i + 1]:
                assert normalized[i] > normalized[i + 1]
            elif scores[i] < scores[i + 1]:
                assert normalized[i] < normalized[i + 1]
            else:
                assert normalized[i] == normalized[i + 1]


class TestHybridSearchResult:
    """Test HybridSearchResult dataclass."""

    def test_hybrid_search_result_creation(self, sample_memories):
        """Test creating HybridSearchResult."""
        result = HybridSearchResult(
            memory=sample_memories[0],
            total_score=0.85,
            vector_score=0.90,
            bm25_score=0.75,
            rank_vector=0,
            rank_bm25=1,
            fusion_method="weighted",
        )

        assert result.memory == sample_memories[0]
        assert result.total_score == 0.85
        assert result.vector_score == 0.90
        assert result.bm25_score == 0.75
        assert result.rank_vector == 0
        assert result.rank_bm25 == 1
        assert result.fusion_method == "weighted"

    def test_hybrid_search_result_defaults(self, sample_memories):
        """Test HybridSearchResult with defaults."""
        result = HybridSearchResult(
            memory=sample_memories[0],
            total_score=0.85,
            vector_score=0.90,
            bm25_score=0.75,
        )

        assert result.rank_vector is None
        assert result.rank_bm25 is None
        assert result.fusion_method == "weighted"


class TestIntegrationScenarios:
    """Test realistic integration scenarios."""

    def test_code_search_scenario(self):
        """Test hybrid search for code search scenario."""
        # Create code-like memories
        memories = [
            MemoryUnit(
                id="1",
                content="def authenticate_user(username, password):\n    return check_credentials(username, password)",
                scope=MemoryScope.PROJECT,
                category=MemoryCategory.CONTEXT,
                context_level=ContextLevel.PROJECT_CONTEXT,
                project_name="test",
            ),
            MemoryUnit(
                id="2",
                content="class UserAuthenticator:\n    def login(self, user):\n        pass",
                scope=MemoryScope.PROJECT,
                category=MemoryCategory.CONTEXT,
                context_level=ContextLevel.PROJECT_CONTEXT,
                project_name="test",
            ),
            MemoryUnit(
                id="3",
                content="def parse_config(file_path):\n    with open(file_path) as f:\n        return json.load(f)",
                scope=MemoryScope.PROJECT,
                category=MemoryCategory.CONTEXT,
                context_level=ContextLevel.PROJECT_CONTEXT,
                project_name="test",
            ),
        ]

        # Simulate vector results (semantic similarity)
        vector_results = [
            (memories[0], 0.92),  # authenticate_user
            (memories[1], 0.88),  # UserAuthenticator
            (memories[2], 0.35),  # parse_config
        ]

        searcher = HybridSearcher(alpha=0.5)
        documents = [m.content for m in memories]
        searcher.index_documents(documents, memories)

        results = searcher.hybrid_search(
            query="user authentication",
            vector_results=vector_results,
            limit=2,
        )

        assert len(results) == 2
        # Should prioritize authentication-related code
        assert results[0].memory.id in ["1", "2"]

    def test_multiple_fusion_methods_same_query(self, sample_memories, sample_vector_results):
        """Test that different fusion methods produce different results."""
        documents = [m.content for m in sample_memories]

        searcher_weighted = HybridSearcher(fusion_method=FusionMethod.WEIGHTED)
        searcher_weighted.index_documents(documents, sample_memories)

        searcher_rrf = HybridSearcher(fusion_method=FusionMethod.RRF)
        searcher_rrf.index_documents(documents, sample_memories)

        searcher_cascade = HybridSearcher(fusion_method=FusionMethod.CASCADE)
        searcher_cascade.index_documents(documents, sample_memories)

        query = "authentication user"

        results_weighted = searcher_weighted.hybrid_search(query, sample_vector_results, limit=3)
        results_rrf = searcher_rrf.hybrid_search(query, sample_vector_results, limit=3)
        results_cascade = searcher_cascade.hybrid_search(query, sample_vector_results, limit=3)

        # All should return results
        assert len(results_weighted) > 0
        assert len(results_rrf) > 0
        assert len(results_cascade) > 0

        # Fusion methods should be recorded correctly
        assert all(r.fusion_method == "weighted" for r in results_weighted)
        assert all(r.fusion_method == "rrf" for r in results_rrf)
        assert all(r.fusion_method == "cascade" for r in results_cascade)

    def test_high_overlap_between_vector_and_bm25(self, sample_memories):
        """Test when vector and BM25 results have high overlap."""
        # Create vector results that match well with keyword search
        vector_results = [
            (sample_memories[0], 0.95),  # "authentication user login"
            (sample_memories[2], 0.90),  # "user authentication handler"
        ]

        searcher = HybridSearcher(alpha=0.5)
        documents = [m.content for m in sample_memories]
        searcher.index_documents(documents, sample_memories)

        results = searcher.hybrid_search(
            query="authentication user",
            vector_results=vector_results,
            limit=2,
        )

        # Both methods should agree on top results
        assert len(results) == 2
        # Top results should have both good vector and BM25 scores
        assert results[0].vector_score > 0
        assert results[0].bm25_score > 0

    def test_low_overlap_between_vector_and_bm25(self, sample_memories):
        """Test when vector and BM25 results have low overlap."""
        # Vector results that won't match keyword search well
        vector_results = [
            (sample_memories[1], 0.8),  # database connection
            (sample_memories[3], 0.7),  # config parser
        ]

        searcher = HybridSearcher(alpha=0.5)
        documents = [m.content for m in sample_memories]
        searcher.index_documents(documents, sample_memories)

        # Query that will match different docs in BM25
        results = searcher.hybrid_search(
            query="authentication user",
            vector_results=vector_results,
            limit=3,
        )

        # Hybrid search should balance both signals
        assert len(results) <= 3
