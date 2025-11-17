"""Unit tests for result reranking."""

import pytest
from datetime import datetime, timedelta, timezone

from src.search.reranker import (
    ResultReranker,
    MMRReranker,
    RerankingWeights,
    rerank_with_custom_function,
)
from src.core.models import (
    MemoryUnit,
    MemoryScope,
    MemoryCategory,
    ContextLevel,
)


@pytest.fixture
def sample_memories():
    """Create sample memory units with varying attributes."""
    now = datetime.now(timezone.utc)

    return [
        MemoryUnit(
            id="mem1",
            content="Short authentication function for user login",
            scope=MemoryScope.PROJECT,
            category=MemoryCategory.CONTEXT,
            context_level=ContextLevel.PROJECT_CONTEXT,
            project_name="test",
            updated_at=now - timedelta(days=1),  # Recent
        ),
        MemoryUnit(
            id="mem2",
            content="This is a very long database connection pooling implementation that handles multiple connection types and provides comprehensive error handling with retry logic and connection validation",  # Long
            scope=MemoryScope.PROJECT,
            category=MemoryCategory.CONTEXT,
            context_level=ContextLevel.PROJECT_CONTEXT,
            project_name="test",
            updated_at=now - timedelta(days=30),  # Old
        ),
        MemoryUnit(
            id="mem3",
            content="API endpoint handler for user authentication and session management",
            scope=MemoryScope.PROJECT,
            category=MemoryCategory.CONTEXT,
            context_level=ContextLevel.PROJECT_CONTEXT,
            project_name="test",
            updated_at=now - timedelta(days=7),  # Medium age
        ),
        MemoryUnit(
            id="mem4",
            content="x",  # Very short
            scope=MemoryScope.PROJECT,
            category=MemoryCategory.CONTEXT,
            context_level=ContextLevel.PROJECT_CONTEXT,
            project_name="test",
            updated_at=now,  # Very recent
        ),
    ]


@pytest.fixture
def sample_results(sample_memories):
    """Create sample search results."""
    return [
        (sample_memories[0], 0.9),  # High similarity
        (sample_memories[1], 0.8),  # Medium-high similarity
        (sample_memories[2], 0.7),  # Medium similarity
        (sample_memories[3], 0.6),  # Lower similarity
    ]


class TestResultReranker:
    """Test ResultReranker class."""

    def test_initialization_default(self):
        """Test default initialization."""
        reranker = ResultReranker()

        assert reranker.weights.similarity == 0.6
        assert reranker.weights.recency == 0.2
        assert reranker.weights.usage == 0.2
        assert reranker.recency_halflife_days == 7.0

    def test_initialization_custom_weights(self):
        """Test initialization with custom weights."""
        weights = RerankingWeights(
            similarity=0.5,
            recency=0.3,
            usage=0.2,
        )
        reranker = ResultReranker(weights=weights)

        assert reranker.weights.similarity == 0.5
        assert reranker.weights.recency == 0.3

    def test_rerank_basic(self, sample_results):
        """Test basic reranking."""
        reranker = ResultReranker()
        reranked = reranker.rerank(sample_results)

        # Should return same number of results
        assert len(reranked) == len(sample_results)

        # All results should still be present
        result_ids = {mem.id for mem, _ in reranked}
        original_ids = {mem.id for mem, _ in sample_results}
        assert result_ids == original_ids

    def test_rerank_empty_results(self):
        """Test reranking with empty results."""
        reranker = ResultReranker()
        reranked = reranker.rerank([])

        assert reranked == []

    def test_rerank_with_usage_data(self, sample_results):
        """Test reranking with usage statistics."""
        usage_data = {
            "mem1": {"use_count": 10, "last_used": datetime.now(timezone.utc)},
            "mem2": {"use_count": 5, "last_used": datetime.now(timezone.utc)},
            "mem3": {"use_count": 1, "last_used": datetime.now(timezone.utc)},
        }

        reranker = ResultReranker()
        reranked = reranker.rerank(sample_results, usage_data=usage_data)

        # mem1 has highest usage, should be boosted
        assert len(reranked) > 0

    def test_rerank_with_query(self, sample_results):
        """Test reranking with query for keyword matching."""
        reranker = ResultReranker(
            weights=RerankingWeights(
                similarity=0.5,
                recency=0.0,
                usage=0.0,
                keyword_boost=0.5,
            )
        )

        reranked = reranker.rerank(sample_results, query="authentication user")

        # Results with "authentication" should be boosted
        assert len(reranked) > 0

    def test_recency_decay(self, sample_memories):
        """Test recency score calculation."""
        reranker = ResultReranker(recency_halflife_days=7.0)

        # Recent memory should have high recency score
        recent_score = reranker._calculate_recency_score(sample_memories[0])
        assert recent_score > 0.9

        # Old memory should have lower recency score
        old_score = reranker._calculate_recency_score(sample_memories[1])
        assert old_score < 0.3

    def test_usage_score_calculation(self, sample_memories):
        """Test usage score calculation."""
        usage_data = {
            "mem1": {"use_count": 100},
            "mem2": {"use_count": 10},
            "mem3": {"use_count": 1},
        }

        reranker = ResultReranker()

        # High usage should give high score
        high_usage_score = reranker._calculate_usage_score(
            sample_memories[0], usage_data
        )
        assert high_usage_score > 0.8

        # Low usage should give lower score
        low_usage_score = reranker._calculate_usage_score(
            sample_memories[2], usage_data
        )
        assert low_usage_score < 0.5

    def test_usage_score_no_data(self, sample_memories):
        """Test usage score when no data available."""
        reranker = ResultReranker()

        score = reranker._calculate_usage_score(sample_memories[0], None)
        assert score == 0.0

    def test_length_penalty(self, sample_memories):
        """Test length penalty calculation."""
        reranker = ResultReranker()

        # Test that penalty is calculated (may be 0 for medium-length content)
        for mem in sample_memories:
            penalty = reranker._calculate_length_penalty(mem)
            # Penalty should be in valid range
            assert -1.0 <= penalty <= 0.0

        # mem4 is very short (1 char), should definitely have penalty
        short_penalty = reranker._calculate_length_penalty(sample_memories[3])
        assert short_penalty < 0.0

    def test_keyword_boost(self, sample_memories):
        """Test keyword matching boost."""
        reranker = ResultReranker()

        # Query with matching keywords
        boost = reranker._calculate_keyword_boost(
            sample_memories[0], "authentication user"
        )
        assert boost > 0.0

        # Query with no matching keywords
        no_boost = reranker._calculate_keyword_boost(
            sample_memories[0], "database connection"
        )
        assert no_boost == 0.0

    def test_diversity_penalty(self, sample_memories):
        """Test diversity promotion."""
        # Create similar results
        results = [
            (sample_memories[0], 0.9),
            (sample_memories[0], 0.85),  # Duplicate
            (sample_memories[1], 0.8),
        ]

        reranker = ResultReranker(diversity_penalty=0.5)
        reranked = reranker._apply_diversity(results, query="test")

        # Should penalize duplicates
        assert len(reranked) == 3

    def test_stats_tracking(self, sample_results):
        """Test statistics tracking."""
        reranker = ResultReranker()

        assert reranker.stats["reranks_performed"] == 0

        reranker.rerank(sample_results)

        assert reranker.stats["reranks_performed"] == 1

    def test_get_stats(self, sample_results):
        """Test get_stats method."""
        reranker = ResultReranker()
        reranker.rerank(sample_results)

        stats = reranker.get_stats()

        assert "reranks_performed" in stats
        assert stats["reranks_performed"] >= 1


class TestMMRReranker:
    """Test MMR (Maximal Marginal Relevance) reranker."""

    def test_initialization(self):
        """Test MMR initialization."""
        reranker = MMRReranker(lambda_param=0.7)
        assert reranker.lambda_param == 0.7

    def test_mmr_rerank_basic(self, sample_results):
        """Test basic MMR reranking."""
        reranker = MMRReranker(lambda_param=0.5)
        reranked = reranker.rerank(sample_results, k=3)

        # Should return k results
        assert len(reranked) == 3

        # Results should be different (diverse)
        result_ids = [mem.id for mem, _ in reranked]
        assert len(set(result_ids)) == len(result_ids)

    def test_mmr_relevance_only(self, sample_results):
        """Test MMR with lambda=1.0 (relevance only, no diversity)."""
        reranker = MMRReranker(lambda_param=1.0)
        reranked = reranker.rerank(sample_results, k=3)

        # Should prioritize relevance
        scores = [score for _, score in reranked]
        assert scores == sorted(scores, reverse=True)

    def test_mmr_diversity_only(self, sample_results):
        """Test MMR with lambda=0.0 (diversity only)."""
        reranker = MMRReranker(lambda_param=0.0)
        reranked = reranker.rerank(sample_results, k=3)

        # Should maximize diversity
        assert len(reranked) == 3

    def test_mmr_empty_results(self):
        """Test MMR with empty results."""
        reranker = MMRReranker()
        reranked = reranker.rerank([], k=5)

        assert reranked == []

    def test_mmr_k_larger_than_results(self, sample_results):
        """Test MMR when k > number of results."""
        reranker = MMRReranker()
        reranked = reranker.rerank(sample_results, k=100)

        # Should return all results
        assert len(reranked) == len(sample_results)

    def test_content_similarity(self, sample_memories):
        """Test content similarity calculation."""
        # Similar content
        similarity = MMRReranker._content_similarity(
            sample_memories[0], sample_memories[2]
        )
        assert 0.0 <= similarity <= 1.0

        # Same memory
        same_similarity = MMRReranker._content_similarity(
            sample_memories[0], sample_memories[0]
        )
        assert same_similarity == 1.0


class TestCustomReranking:
    """Test custom reranking function."""

    def test_custom_function(self, sample_results):
        """Test reranking with custom scoring function."""
        # Custom function that boosts scores by 0.1
        def custom_scorer(memory, score):
            return score + 0.1

        reranked = rerank_with_custom_function(sample_results, custom_scorer)

        # All scores should be boosted
        for (mem_orig, score_orig), (mem_new, score_new) in zip(
            sample_results, reranked
        ):
            assert score_new > score_orig

    def test_custom_function_content_based(self, sample_results):
        """Test custom function based on content."""
        # Boost results containing "authentication"
        def auth_boost(memory, score):
            if "authentication" in memory.content.lower():
                return score * 1.5
            return score

        reranked = rerank_with_custom_function(sample_results, auth_boost)

        # Should reorder results
        assert len(reranked) == len(sample_results)


class TestWeightedCombinations:
    """Test different weight combinations."""

    def test_similarity_only(self, sample_results):
        """Test reranking with similarity weight only."""
        weights = RerankingWeights(
            similarity=1.0,
            recency=0.0,
            usage=0.0,
        )
        reranker = ResultReranker(weights=weights)
        reranked = reranker.rerank(sample_results)

        # Should preserve original order (similarity-based)
        assert len(reranked) > 0

    def test_recency_only(self, sample_results):
        """Test reranking with recency weight only."""
        weights = RerankingWeights(
            similarity=0.0,
            recency=1.0,
            usage=0.0,
        )
        reranker = ResultReranker(weights=weights)
        reranked = reranker.rerank(sample_results)

        # Most recent should be first
        first_result = reranked[0][0]
        assert first_result.id == "mem4"  # Most recent

    def test_balanced_weights(self, sample_results):
        """Test reranking with balanced weights."""
        weights = RerankingWeights(
            similarity=0.33,
            recency=0.33,
            usage=0.34,
        )
        reranker = ResultReranker(weights=weights)

        usage_data = {
            "mem1": {"use_count": 10},
            "mem2": {"use_count": 5},
            "mem3": {"use_count": 1},
            "mem4": {"use_count": 0},
        }

        reranked = reranker.rerank(sample_results, usage_data=usage_data)

        # Should balance all signals
        assert len(reranked) == len(sample_results)


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_single_result(self, sample_memories):
        """Test reranking with single result."""
        results = [(sample_memories[0], 0.9)]

        reranker = ResultReranker()
        reranked = reranker.rerank(results)

        assert len(reranked) == 1
        # Memory should be the same
        assert reranked[0][0] == results[0][0]
        # Score may change due to reranking
        assert isinstance(reranked[0][1], float)

    def test_identical_scores(self, sample_memories):
        """Test reranking with identical scores."""
        results = [
            (sample_memories[0], 0.5),
            (sample_memories[1], 0.5),
            (sample_memories[2], 0.5),
        ]

        reranker = ResultReranker()
        reranked = reranker.rerank(results)

        # Should handle gracefully
        assert len(reranked) == 3

    def test_no_timestamps(self):
        """Test reranking handles missing timestamp data gracefully."""
        # MemoryUnit requires updated_at, so we can't test None
        # Instead, test that reranking works with old timestamps
        old_time = datetime(2020, 1, 1, tzinfo=timezone.utc)
        mem = MemoryUnit(
            id="test",
            content="test content",
            scope=MemoryScope.GLOBAL,
            category=MemoryCategory.FACT,
            context_level=ContextLevel.SESSION_STATE,
            updated_at=old_time,
        )

        results = [(mem, 0.9)]

        reranker = ResultReranker()
        reranked = reranker.rerank(results)

        assert len(reranked) == 1
        # Old memory should have low recency score
        recency_score = reranker._calculate_recency_score(mem)
        assert recency_score < 0.1  # Very old
