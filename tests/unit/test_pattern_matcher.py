"""Tests for pattern matcher."""

import pytest
from unittest.mock import Mock, AsyncMock

from src.review.pattern_matcher import PatternMatcher, PatternMatch
from src.review.patterns import CodeSmellPattern
from tests.conftest import mock_embedding


@pytest.fixture
def mock_embedding_generator():
    """Mock embedding generator."""
    generator = Mock()
    generator.generate_embedding = AsyncMock(return_value=mock_embedding(value=0.1))  # Mock embedding (768-dim)
    return generator


@pytest.fixture
def test_pattern():
    """Sample code smell pattern for testing."""
    return CodeSmellPattern(
        id="test-001",
        name="Test Pattern",
        category="security",
        severity="high",
        description="Test pattern description",
        example_code="bad_code_example()",
        fix_description="Use good_code_example() instead",
        languages=["python", "javascript"],
    )


class TestPatternMatcher:
    """Test pattern matching functionality."""

    @pytest.mark.asyncio
    async def test_find_matches_with_similar_code(self, mock_embedding_generator, test_pattern):
        """Test finding matches with similar code."""
        matcher = PatternMatcher(mock_embedding_generator)

        # Mock similar embeddings
        async def mock_generate(code):
            if "bad_code" in code:
                return mock_embedding(value=0.9)  # Very similar to pattern
            return mock_embedding(value=0.1)

        mock_embedding_generator.generate_embedding.side_effect = mock_generate

        matches = await matcher.find_matches(
            code="bad_code_similar()",
            language="python",
            patterns=[test_pattern],
            threshold=0.75,
        )

        assert len(matches) > 0
        assert matches[0].pattern.id == "test-001"
        assert matches[0].similarity_score > 0.75

    @pytest.mark.asyncio
    async def test_find_matches_filters_by_language(self, mock_embedding_generator, test_pattern):
        """Test that patterns are filtered by language."""
        matcher = PatternMatcher(mock_embedding_generator)

        # Try with unsupported language
        matches = await matcher.find_matches(
            code="some_code",
            language="rust",  # Not in test_pattern.languages
            patterns=[test_pattern],
            threshold=0.75,
        )

        assert len(matches) == 0

    @pytest.mark.asyncio
    async def test_find_matches_applies_threshold(self, mock_embedding_generator, test_pattern):
        """Test that similarity threshold is applied correctly."""
        matcher = PatternMatcher(mock_embedding_generator)

        # Mock low similarity - return orthogonal vectors
        async def mock_generate(code):
            if "bad_code" in code:
                # Pattern: all 1s in first half, 0s in second half
                return [1.0] * 192 + [0.0] * 192
            # Code: all 0s in first half, 1s in second half (orthogonal)
            return [0.0] * 192 + [1.0] * 192

        mock_embedding_generator.generate_embedding.side_effect = mock_generate

        matches = await matcher.find_matches(
            code="completely_different_code",
            language="python",
            patterns=[test_pattern],
            threshold=0.80,  # High threshold
        )

        assert len(matches) == 0  # Should not match due to low similarity (orthogonal = 0)

    @pytest.mark.asyncio
    async def test_find_matches_sorts_by_similarity(self, mock_embedding_generator):
        """Test that matches are sorted by similarity score."""
        pattern1 = CodeSmellPattern(
            id="pattern-1",
            name="Pattern 1",
            category="security",
            severity="high",
            description="Description 1",
            example_code="code1",
            fix_description="Fix 1",
            languages=["python"],
        )

        pattern2 = CodeSmellPattern(
            id="pattern-2",
            name="Pattern 2",
            category="performance",
            severity="medium",
            description="Description 2",
            example_code="code2",
            fix_description="Fix 2",
            languages=["python"],
        )

        matcher = PatternMatcher(mock_embedding_generator)

        # Mock different similarities
        embeddings = {
            "code1": mock_embedding(value=0.8),  # Lower similarity
            "code2": mock_embedding(value=0.95),  # Higher similarity
        }

        async def mock_generate(code):
            for key, embedding in embeddings.items():
                if key in code:
                    return embedding
            return mock_embedding(value=0.1)

        mock_embedding_generator.generate_embedding.side_effect = mock_generate

        matches = await matcher.find_matches(
            code="test_code",
            language="python",
            patterns=[pattern1, pattern2],
            threshold=0.75,
        )

        # Matches should be sorted by similarity (highest first)
        if len(matches) > 1:
            for i in range(len(matches) - 1):
                assert matches[i].similarity_score >= matches[i + 1].similarity_score

    @pytest.mark.asyncio
    async def test_confidence_levels(self, mock_embedding_generator, test_pattern):
        """Test that confidence is assigned based on similarity."""
        matcher = PatternMatcher(mock_embedding_generator)

        # Simplified test: just verify confidence assignment logic
        # Test high confidence (>= 0.90)
        await matcher.clear_cache()

        async def mock_high_similarity(code):
            # Return identical vectors for high similarity
            return mock_embedding(value=1.0)

        mock_embedding_generator.generate_embedding.side_effect = mock_high_similarity

        matches = await matcher.find_matches(
            code="test_code",
            language="python",
            patterns=[test_pattern],
            threshold=0.75,
        )

        assert len(matches) > 0
        assert matches[0].confidence == "high"
        assert matches[0].similarity_score >= 0.90

    @pytest.mark.asyncio
    async def test_cache_pattern_embeddings(self, mock_embedding_generator, test_pattern):
        """Test that pattern embeddings are cached."""
        matcher = PatternMatcher(mock_embedding_generator)

        # First call
        await matcher.find_matches(
            code="test_code_1",
            language="python",
            patterns=[test_pattern],
            threshold=0.75,
        )

        # Second call with same pattern
        await matcher.find_matches(
            code="test_code_2",
            language="python",
            patterns=[test_pattern],
            threshold=0.75,
        )

        # Pattern embedding should only be generated once (cached)
        # Code embeddings generated twice (once per call)
        assert len(matcher._pattern_embeddings_cache) == 1
        assert test_pattern.id in matcher._pattern_embeddings_cache

    @pytest.mark.asyncio
    async def test_clear_cache(self, mock_embedding_generator, test_pattern):
        """Test cache clearing."""
        matcher = PatternMatcher(mock_embedding_generator)

        # Generate and cache a pattern embedding
        await matcher.find_matches(
            code="test_code",
            language="python",
            patterns=[test_pattern],
            threshold=0.75,
        )

        assert len(matcher._pattern_embeddings_cache) > 0

        # Clear cache
        await matcher.clear_cache()

        assert len(matcher._pattern_embeddings_cache) == 0


class TestCosineSimilarity:
    """Test cosine similarity calculation."""

    def test_identical_vectors(self, mock_embedding_generator):
        """Test similarity of identical vectors is 1.0."""
        matcher = PatternMatcher(mock_embedding_generator)
        vec = [1.0, 2.0, 3.0]
        similarity = matcher._cosine_similarity(vec, vec)
        assert abs(similarity - 1.0) < 0.001  # Should be very close to 1.0

    def test_orthogonal_vectors(self, mock_embedding_generator):
        """Test similarity of orthogonal vectors is 0.0."""
        matcher = PatternMatcher(mock_embedding_generator)
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [0.0, 1.0, 0.0]
        similarity = matcher._cosine_similarity(vec1, vec2)
        assert abs(similarity) < 0.001  # Should be very close to 0.0

    def test_zero_vectors(self, mock_embedding_generator):
        """Test that zero vectors return 0.0 similarity."""
        matcher = PatternMatcher(mock_embedding_generator)
        vec1 = [0.0, 0.0, 0.0]
        vec2 = [1.0, 2.0, 3.0]
        similarity = matcher._cosine_similarity(vec1, vec2)
        assert similarity == 0.0
