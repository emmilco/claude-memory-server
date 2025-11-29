"""Tests for retrieval utility predictor.

This module tests the RetrievalPredictor class which implements heuristic-based
prediction of whether retrieval (vector search) will be useful for a given query.
The predictor enables intelligent skipping of unnecessary vector searches,
targeting 30-40% skip rate for queries unlikely to benefit from retrieval.
"""

import pytest
from src.router.retrieval_predictor import RetrievalPredictor


class TestRetrievalPredictorInitialization:
    """Tests for RetrievalPredictor initialization and configuration."""

    def test_default_initialization(self):
        """Test predictor initializes with default parameters."""
        predictor = RetrievalPredictor()

        assert predictor.min_query_length == 10
        assert predictor.max_small_talk_length == 30
        assert predictor._small_talk_regex is not None
        assert predictor._needs_retrieval_regex is not None

    def test_custom_parameters(self):
        """Test predictor accepts custom configuration parameters."""
        predictor = RetrievalPredictor(
            min_query_length=5,
            max_small_talk_length=50
        )

        assert predictor.min_query_length == 5
        assert predictor.max_small_talk_length == 50

    def test_regex_patterns_compiled(self):
        """Test that regex patterns are compiled during initialization."""
        predictor = RetrievalPredictor()

        # Verify patterns are compiled regex objects
        import re
        assert isinstance(predictor._small_talk_regex, re.Pattern)
        assert isinstance(predictor._needs_retrieval_regex, re.Pattern)


class TestPredictUtilityEmptyInputs:
    """Tests for edge cases with empty or invalid inputs."""

    @pytest.fixture
    def predictor(self):
        """Create predictor instance for tests."""
        return RetrievalPredictor()

    def test_empty_string(self, predictor):
        """Test empty string returns zero utility."""
        utility = predictor.predict_utility("")

        assert utility == 0.0

    def test_none_input(self, predictor):
        """Test None input returns zero utility."""
        utility = predictor.predict_utility(None)

        assert utility == 0.0

    def test_whitespace_only(self, predictor):
        """Test whitespace-only input returns zero utility."""
        utility = predictor.predict_utility("   ")

        assert utility == 0.0

    def test_newlines_and_tabs(self, predictor):
        """Test newlines and tabs treated as whitespace."""
        utility = predictor.predict_utility("\n\t  \n")

        assert utility == 0.0


class TestSmallTalkDetection:
    """Tests for small talk pattern detection (should have low utility)."""

    @pytest.fixture
    def predictor(self):
        """Create predictor instance for tests."""
        return RetrievalPredictor()

    @pytest.mark.parametrize("query", [
        "hi",
        "hello",
        "hey",
        "thanks",
        "thank you",
        "ok",
        "okay",
        "sure",
        "yes",
        "no",
        "got it",
    ])
    def test_short_greetings_low_utility(self, predictor, query):
        """Test short greetings and acknowledgments have very low utility."""
        utility = predictor.predict_utility(query)

        assert utility <= 0.1, f"Query '{query}' should have low utility, got {utility}"

    @pytest.mark.parametrize("query", [
        "great",
        "cool",
        "nice",
        "awesome",
        "perfect",
        "great!",
        "cool.",
        "nice!",
    ])
    def test_positive_acknowledgments_low_utility(self, predictor, query):
        """Test positive acknowledgments have very low utility."""
        utility = predictor.predict_utility(query)

        assert utility <= 0.2, f"Query '{query}' should have low utility, got {utility}"

    @pytest.mark.parametrize("query", [
        "bye",
        "goodbye",
        "see you",
        "ttyl",
    ])
    def test_farewells_low_utility(self, predictor, query):
        """Test farewell messages have low utility."""
        utility = predictor.predict_utility(query)

        assert utility < 0.5, f"Query '{query}' should have low utility, got {utility}"

    def test_combined_small_talk(self, predictor):
        """Test combined small talk phrases."""
        utility = predictor.predict_utility("ok thanks!")

        assert utility <= 0.2


class TestRetrievalKeywordDetection:
    """Tests for retrieval keyword pattern detection (should have high utility)."""

    @pytest.fixture
    def predictor(self):
        """Create predictor instance for tests."""
        return RetrievalPredictor()

    @pytest.mark.parametrize("query", [
        "how do I implement authentication?",
        "what is the best way to do this?",
        "where is the database connection code?",
        "when was this function last modified?",
        "why is this returning null?",
        "who wrote this module?",
        "which implementation should I use?",
    ])
    def test_question_words_high_utility(self, predictor, query):
        """Test queries with question words have high utility."""
        utility = predictor.predict_utility(query)

        assert utility > 0.7, f"Query '{query}' should have high utility, got {utility}"

    @pytest.mark.parametrize("query", [
        "find the authentication module",
        "search for database connections",
        "show me the API endpoints",
        "get the user model",
        "retrieve previous implementation",
        "look up the config settings",
    ])
    def test_action_verbs_high_utility(self, predictor, query):
        """Test queries with action verbs have high utility."""
        utility = predictor.predict_utility(query)

        assert utility > 0.7, f"Query '{query}' should have high utility, got {utility}"

    @pytest.mark.parametrize("query", [
        "code for authentication",
        "function to validate input",
        "class for user management",
        "method to process requests",
        "file containing config",
        "implementation of the parser",
    ])
    def test_code_terms_high_utility(self, predictor, query):
        """Test queries with code-related terms have high utility."""
        utility = predictor.predict_utility(query)

        assert utility > 0.6, f"Query '{query}' should have high utility, got {utility}"

    @pytest.mark.parametrize("query", [
        "error in the login function",
        "bug in authentication",
        "issue with database",
        "problem with API",
        "fix for the parser",
    ])
    def test_issue_terms_high_utility(self, predictor, query):
        """Test queries about issues/errors have high utility."""
        utility = predictor.predict_utility(query)

        assert utility > 0.7, f"Query '{query}' should have high utility, got {utility}"

    @pytest.mark.parametrize("query", [
        "remember the previous implementation",
        "recall the stored configuration",
        "what was saved earlier",
        "previous conversation context",
    ])
    def test_memory_terms_high_utility(self, predictor, query):
        """Test queries about memory/stored content have high utility."""
        utility = predictor.predict_utility(query)

        assert utility > 0.6, f"Query '{query}' should have high utility, got {utility}"


class TestTechnicalKeywords:
    """Tests for technical keyword detection."""

    @pytest.fixture
    def predictor(self):
        """Create predictor instance for tests."""
        return RetrievalPredictor()

    @pytest.mark.parametrize("keyword", [
        "api", "endpoint", "database", "query", "authentication",
        "test", "config", "deployment", "server", "client",
        "middleware", "model", "controller", "service", "repository",
    ])
    def test_single_technical_keyword(self, predictor, keyword):
        """Test queries with single technical keyword have increased utility."""
        query = f"need help with {keyword}"
        utility = predictor.predict_utility(query)

        assert utility >= 0.5, f"Query with '{keyword}' should have moderate+ utility"

    def test_multiple_technical_keywords_boost(self, predictor):
        """Test that multiple technical keywords increase utility."""
        query_one_kw = "help with database"
        query_many_kw = "api endpoint database query authentication middleware"

        utility_one = predictor.predict_utility(query_one_kw)
        utility_many = predictor.predict_utility(query_many_kw)

        assert utility_many > utility_one, "More technical keywords should increase utility"

    def test_three_or_more_technical_keywords(self, predictor):
        """Test that 3+ technical keywords give substantial boost."""
        query = "api endpoint database query authentication service"
        utility = predictor.predict_utility(query)

        # Should have high utility due to multiple technical terms
        assert utility > 0.8


class TestQuestionDetection:
    """Tests for question mark detection."""

    @pytest.fixture
    def predictor(self):
        """Create predictor instance for tests."""
        return RetrievalPredictor()

    def test_question_mark_increases_utility(self, predictor):
        """Test that question marks increase utility."""
        # Use shorter queries that won't hit the 1.0 cap to see the difference
        query_no_question = "config setup"
        query_with_question = "config setup?"

        utility_no = predictor.predict_utility(query_no_question)
        utility_with = predictor.predict_utility(query_with_question)

        assert utility_with > utility_no

    def test_question_alone_not_enough(self, predictor):
        """Test that question mark alone without content doesn't give high utility."""
        utility = predictor.predict_utility("?")

        assert utility < 0.5


class TestCodeMarkerDetection:
    """Tests for code-like pattern detection."""

    @pytest.fixture
    def predictor(self):
        """Create predictor instance for tests."""
        return RetrievalPredictor()

    @pytest.mark.parametrize("code_marker,query", [
        ("()", "find authenticate() function"),
        ("{}", "show me the object {} structure"),
        ("[]", "array[] indexing code"),
        ("->", "pointer-> access pattern"),
        ("=>", "arrow => function implementation"),
        ("::", "namespace::function call"),
    ])
    def test_code_markers_increase_utility(self, predictor, code_marker, query):
        """Test that code markers increase utility."""
        utility = predictor.predict_utility(query)

        assert utility > 0.5, f"Query with '{code_marker}' should have moderate+ utility"

    def test_code_marker_without_context(self, predictor):
        """Test code marker in short query."""
        # Even short queries with code markers should get some boost
        utility = predictor.predict_utility("()")

        # Code markers alone won't make utility high, but prevent very low scores
        assert utility >= 0.3


class TestQueryLength:
    """Tests for query length effects on utility."""

    @pytest.fixture
    def predictor(self):
        """Create predictor instance for tests."""
        return RetrievalPredictor()

    def test_very_short_query_low_utility(self, predictor):
        """Test very short queries have reduced utility."""
        utility = predictor.predict_utility("ab")

        assert utility < 0.5

    def test_short_query_without_keywords(self, predictor):
        """Test short queries without keywords have low utility."""
        utility = predictor.predict_utility("stuff")

        assert utility < 0.5

    def test_long_query_increases_utility(self, predictor):
        """Test that longer queries (>50 chars) get utility boost."""
        short_query = "database code"
        long_query = "I need to find the database connection code for the authentication module"

        utility_short = predictor.predict_utility(short_query)
        utility_long = predictor.predict_utility(long_query)

        assert utility_long > utility_short

    def test_word_count_affects_utility(self, predictor):
        """Test that more words indicate more specific queries."""
        two_words = "database code"
        many_words = "find the database connection code for user auth module"

        utility_few = predictor.predict_utility(two_words)
        utility_many = predictor.predict_utility(many_words)

        assert utility_many > utility_few


class TestExtractSignals:
    """Tests for the internal _extract_signals method."""

    @pytest.fixture
    def predictor(self):
        """Create predictor instance for tests."""
        return RetrievalPredictor()

    def test_signals_length_captured(self, predictor):
        """Test that query length is captured in signals."""
        query = "test query"
        signals = predictor._extract_signals(query, query.lower())

        assert signals['length'] == len(query)

    def test_signals_is_very_short(self, predictor):
        """Test is_very_short signal detection."""
        short = predictor._extract_signals("hi", "hi")
        long = predictor._extract_signals("this is a longer query", "this is a longer query")

        assert short['is_very_short'] == 1.0
        assert long['is_very_short'] == 0.0

    def test_signals_word_count(self, predictor):
        """Test word count signal."""
        query = "one two three four five"
        signals = predictor._extract_signals(query, query.lower())

        assert signals['word_count'] == 5

    def test_signals_is_specific(self, predictor):
        """Test is_specific signal (4+ words)."""
        short = predictor._extract_signals("one two", "one two")
        long = predictor._extract_signals("one two three four", "one two three four")

        assert short['is_specific'] == 0.0
        assert long['is_specific'] == 1.0

    def test_signals_technical_keyword_count(self, predictor):
        """Test technical keyword count signal."""
        query = "api endpoint database"
        signals = predictor._extract_signals(query, query.lower())

        assert signals['technical_keyword_count'] >= 3

    def test_signals_has_code_markers(self, predictor):
        """Test has_code_markers signal."""
        with_marker = predictor._extract_signals("func()", "func()")
        without_marker = predictor._extract_signals("func", "func")

        assert with_marker['has_code_markers'] == 1.0
        assert without_marker['has_code_markers'] == 0.0


class TestComputeUtility:
    """Tests for the internal _compute_utility method."""

    @pytest.fixture
    def predictor(self):
        """Create predictor instance for tests."""
        return RetrievalPredictor()

    def test_utility_clamped_to_zero_one(self, predictor):
        """Test that utility is always between 0 and 1."""
        # Test many positive signals
        signals_high = {
            'is_very_short': 0.0,
            'is_small_talk_length': 0.0,
            'has_small_talk': 0.0,
            'has_retrieval_keywords': 1.0,
            'has_technical_content': 1.0,
            'is_question': 1.0,
            'has_code_markers': 1.0,
            'is_specific': 1.0,
            'length': 100,
            'technical_keyword_count': 5,
            'word_count': 10,
        }

        utility = predictor._compute_utility(signals_high)
        assert 0.0 <= utility <= 1.0

        # Test many negative signals
        signals_low = {
            'is_very_short': 1.0,
            'is_small_talk_length': 1.0,
            'has_small_talk': 1.0,
            'has_retrieval_keywords': 0.0,
            'has_technical_content': 0.0,
            'is_question': 0.0,
            'has_code_markers': 0.0,
            'is_specific': 0.0,
            'length': 2,
            'technical_keyword_count': 0,
            'word_count': 1,
        }

        utility = predictor._compute_utility(signals_low)
        assert 0.0 <= utility <= 1.0

    def test_small_talk_with_short_query_returns_zero(self, predictor):
        """Test definite skip for short small talk."""
        signals = {
            'is_very_short': 1.0,
            'is_small_talk_length': 1.0,
            'has_small_talk': 1.0,
            'has_retrieval_keywords': 0.0,
            'has_technical_content': 0.0,
            'is_question': 0.0,
            'has_code_markers': 0.0,
            'is_specific': 0.0,
            'length': 5,
            'technical_keyword_count': 0,
            'word_count': 1,
        }

        utility = predictor._compute_utility(signals)
        assert utility == 0.0

    def test_small_talk_length_without_keywords_returns_low(self, predictor):
        """Test very low utility for small talk without retrieval keywords."""
        signals = {
            'is_very_short': 0.0,
            'is_small_talk_length': 1.0,
            'has_small_talk': 1.0,
            'has_retrieval_keywords': 0.0,
            'has_technical_content': 0.0,
            'is_question': 0.0,
            'has_code_markers': 0.0,
            'is_specific': 0.0,
            'length': 20,
            'technical_keyword_count': 0,
            'word_count': 3,
        }

        utility = predictor._compute_utility(signals)
        assert utility == 0.1


class TestGetExplanation:
    """Tests for the get_explanation method."""

    @pytest.fixture
    def predictor(self):
        """Create predictor instance for tests."""
        return RetrievalPredictor()

    def test_low_utility_explanation(self, predictor):
        """Test explanation for low utility queries."""
        query = "thanks"
        utility = predictor.predict_utility(query)
        explanation = predictor.get_explanation(query, utility)

        assert "small talk" in explanation.lower() or "generic" in explanation.lower()
        assert f"{utility:.2f}" in explanation

    def test_high_utility_explanation(self, predictor):
        """Test explanation for high utility queries."""
        query = "how do I implement database authentication?"
        utility = predictor.predict_utility(query)
        explanation = predictor.get_explanation(query, utility)

        assert "likely needs context" in explanation.lower()
        assert f"{utility:.2f}" in explanation

    def test_medium_utility_explanation(self, predictor):
        """Test explanation for medium utility queries."""
        # Craft a query that should be in the middle range
        # "update settings" should produce ~0.3-0.5 utility
        # (not clearly retrieval, not small talk, short and generic)
        query = "update settings"
        utility = predictor.predict_utility(query)

        # Verify utility is actually in medium range before testing explanation
        assert 0.3 <= utility <= 0.7, f"Query should produce medium utility, got {utility}"

        explanation = predictor.get_explanation(query, utility)
        assert "uncertain" in explanation.lower()

    def test_explanation_includes_reasons(self, predictor):
        """Test that high utility explanations include reasons."""
        query = "what is the API endpoint configuration?"
        utility = predictor.predict_utility(query)
        explanation = predictor.get_explanation(query, utility)

        # Should mention at least one reason
        possible_reasons = ["retrieval keywords", "technical content", "question"]
        assert any(reason in explanation.lower() for reason in possible_reasons)


class TestCaseInsensitivity:
    """Tests for case-insensitive pattern matching."""

    @pytest.fixture
    def predictor(self):
        """Create predictor instance for tests."""
        return RetrievalPredictor()

    def test_uppercase_small_talk(self, predictor):
        """Test small talk detection is case insensitive."""
        utility_lower = predictor.predict_utility("thanks")
        utility_upper = predictor.predict_utility("THANKS")
        utility_mixed = predictor.predict_utility("ThAnKs")

        # All should have similar low utility
        assert all(u < 0.3 for u in [utility_lower, utility_upper, utility_mixed])

    def test_uppercase_retrieval_keywords(self, predictor):
        """Test retrieval keyword detection is case insensitive."""
        utility_lower = predictor.predict_utility("how do I implement this?")
        utility_upper = predictor.predict_utility("HOW DO I IMPLEMENT THIS?")
        utility_mixed = predictor.predict_utility("HoW dO i ImPlEmEnT tHiS?")

        # All should have similar high utility
        assert all(u > 0.7 for u in [utility_lower, utility_upper, utility_mixed])

    def test_uppercase_technical_keywords(self, predictor):
        """Test technical keyword detection is case insensitive."""
        utility_lower = predictor.predict_utility("api endpoint database")
        utility_upper = predictor.predict_utility("API ENDPOINT DATABASE")

        # Both should have similar utility
        assert abs(utility_lower - utility_upper) < 0.1


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    @pytest.fixture
    def predictor(self):
        """Create predictor instance for tests."""
        return RetrievalPredictor()

    def test_single_character(self, predictor):
        """Test single character input."""
        utility = predictor.predict_utility("a")

        assert utility < 0.5

    def test_very_long_query(self, predictor):
        """Test very long query handling."""
        query = "database " * 100  # 800+ characters
        utility = predictor.predict_utility(query)

        # Should handle without error and have high utility due to technical keyword
        assert 0.0 <= utility <= 1.0
        assert utility > 0.5

    def test_special_characters_only(self, predictor):
        """Test query with only special characters."""
        utility = predictor.predict_utility("!@#$%^&*")

        assert utility < 0.5

    def test_unicode_characters(self, predictor):
        """Test query with unicode characters."""
        utility = predictor.predict_utility("find the function")

        assert 0.0 <= utility <= 1.0

    def test_numbers_only(self, predictor):
        """Test query with numbers only."""
        utility = predictor.predict_utility("12345678901234567890")

        assert 0.0 <= utility <= 1.0

    def test_mixed_small_talk_and_retrieval(self, predictor):
        """Test query that mixes small talk and retrieval keywords."""
        query = "thanks, but how do I find the database connection code?"

        utility = predictor.predict_utility(query)

        # Retrieval keywords should override small talk
        assert utility > 0.5


class TestNegativeAdjustments:
    """Tests for negative utility adjustments in _compute_utility."""

    @pytest.fixture
    def predictor(self):
        """Create predictor instance for tests."""
        return RetrievalPredictor()

    def test_small_talk_without_retrieval_keywords_penalty(self, predictor):
        """Test that small talk without retrieval keywords gets a penalty.

        This tests line 184: utility -= 0.3 for small talk without retrieval keywords.
        The query must be long enough to not trigger the early returns (lines 153-157)
        but still have small talk detected without retrieval keywords.
        """
        # "thanks for the explanation of the new system approach" is:
        # - Long enough (>30 chars, so is_small_talk_length=0)
        # - Contains "thanks" (has_small_talk=1)
        # - No retrieval keywords like how/what/where/find/search
        # This should hit line 184
        query = "thanks for the explanation of the new system approach"
        utility = predictor.predict_utility(query)

        # Should have reduced utility due to small talk penalty
        # But not zero since it's not a short query
        assert 0.0 < utility < 0.6

    def test_short_query_without_code_markers_penalty(self, predictor):
        """Test that very short queries without code markers get a penalty.

        This tests line 186-187: utility -= 0.2 for word_count <= 2 without code markers.
        """
        # Two words, no code markers
        query = "hello world"
        utility = predictor.predict_utility(query)

        # Should have low utility (short + small talk)
        assert utility < 0.3


class TestRealisticQueries:
    """Tests with realistic user queries to validate expected behavior."""

    @pytest.fixture
    def predictor(self):
        """Create predictor instance for tests."""
        return RetrievalPredictor()

    @pytest.mark.parametrize("query,expected_min_utility", [
        # Queries that SHOULD need retrieval
        ("How do I implement user authentication?", 0.7),
        ("Find the function that handles API requests", 0.7),
        ("Show me examples of database connection patterns", 0.7),
        ("What code handles error responses?", 0.7),
        ("Where is the middleware configuration?", 0.7),
        ("I need to fix a bug in the authentication module", 0.7),
        ("Search for all async function implementations", 0.7),
        # Queries that should have moderate utility
        ("update the config file", 0.4),
        ("implement new feature", 0.5),
    ])
    def test_queries_needing_retrieval(self, predictor, query, expected_min_utility):
        """Test queries that should have at least expected utility."""
        utility = predictor.predict_utility(query)

        assert utility >= expected_min_utility, f"Query '{query}' expected >= {expected_min_utility}, got {utility}"

    @pytest.mark.parametrize("query,expected_max_utility", [
        # Queries that should NOT need retrieval
        ("ok", 0.2),
        ("thanks!", 0.2),
        ("got it", 0.2),
        ("sure", 0.2),
        ("yes", 0.2),
        ("no", 0.2),
        ("great!", 0.3),
        ("sounds good", 0.3),
    ])
    def test_queries_not_needing_retrieval(self, predictor, query, expected_max_utility):
        """Test queries that should have at most expected utility."""
        utility = predictor.predict_utility(query)

        assert utility <= expected_max_utility, f"Query '{query}' expected <= {expected_max_utility}, got {utility}"


class TestClassConstants:
    """Tests for class-level constants and patterns."""

    def test_small_talk_patterns_defined(self):
        """Test that small talk patterns are defined."""
        assert len(RetrievalPredictor.SMALL_TALK_PATTERNS) > 0

    def test_needs_retrieval_patterns_defined(self):
        """Test that retrieval patterns are defined."""
        assert len(RetrievalPredictor.NEEDS_RETRIEVAL_PATTERNS) > 0

    def test_technical_keywords_defined(self):
        """Test that technical keywords are defined."""
        assert len(RetrievalPredictor.TECHNICAL_KEYWORDS) > 0
        # All keywords should be lowercase for matching
        assert all(kw.islower() for kw in RetrievalPredictor.TECHNICAL_KEYWORDS)

    def test_patterns_are_valid_regex(self):
        """Test that all patterns are valid regex."""
        import re

        for pattern in RetrievalPredictor.SMALL_TALK_PATTERNS:
            # Should compile without error
            re.compile(pattern)

        for pattern in RetrievalPredictor.NEEDS_RETRIEVAL_PATTERNS:
            re.compile(pattern)
