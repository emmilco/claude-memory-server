"""Tests for intent detection."""

import pytest
from src.memory.intent_detector import IntentDetector, DetectedIntent


class TestIntentDetector:
    """Test IntentDetector class."""

    @pytest.fixture
    def detector(self):
        """Create detector instance."""
        return IntentDetector(context_window=5)

    def test_empty_queries(self, detector):
        """Test with empty query list."""
        result = detector.detect_intent([])

        assert result.intent_type == 'general'
        assert result.keywords == []
        assert result.confidence == 0.0
        assert result.search_query == ''

    def test_implementation_intent(self, detector):
        """Test implementation intent detection."""
        queries = [
            "I need to implement user authentication",
            "How do I add JWT token validation?"
        ]

        result = detector.detect_intent(queries)

        assert result.intent_type == 'implementation'
        assert result.confidence > 0.5
        assert 'jwt' in result.keywords or 'token' in result.keywords
        assert 'implement' in result.search_query

    def test_debugging_intent(self, detector):
        """Test debugging intent detection."""
        queries = [
            "Why is my API returning 401 errors?",
            "Authentication middleware not working"
        ]

        result = detector.detect_intent(queries)

        assert result.intent_type == 'debugging'
        assert result.confidence > 0.5
        assert any(kw in result.keywords for kw in ['api', 'authentication', 'middleware'])

    def test_learning_intent(self, detector):
        """Test learning intent detection."""
        queries = [
            "What are Python decorators?",
            "Show me examples of async functions"
        ]

        result = detector.detect_intent(queries)

        assert result.intent_type == 'learning'
        assert result.confidence > 0.5
        assert 'async' in result.keywords or 'decorators' in result.keywords

    def test_exploration_intent(self, detector):
        """Test exploration intent detection."""
        queries = [
            "Find all database models",
            "Where are the API endpoints defined?"
        ]

        result = detector.detect_intent(queries)

        assert result.intent_type == 'exploration'
        assert result.confidence > 0.3
        assert any(kw in result.keywords for kw in ['database', 'api', 'endpoint'])

    def test_keyword_extraction_technical_terms(self, detector):
        """Test extraction of technical terms."""
        queries = ["I need to add JWT authentication to my API"]

        result = detector.detect_intent(queries)

        # Should extract technical terms
        assert 'jwt' in result.keywords
        assert 'authentication' in result.keywords
        assert 'api' in result.keywords

    def test_keyword_extraction_pascal_case(self, detector):
        """Test extraction of PascalCase class names."""
        queries = ["How do I use the UserAuthenticator class?"]

        result = detector.detect_intent(queries)

        # Should extract PascalCase
        assert 'userauthenticator' in result.keywords

    def test_keyword_extraction_snake_case(self, detector):
        """Test extraction of snake_case identifiers."""
        queries = ["The validate_token function is failing"]

        result = detector.detect_intent(queries)

        # Should extract snake_case
        assert 'validate_token' in result.keywords

    def test_keyword_extraction_function_calls(self, detector):
        """Test extraction of function calls."""
        queries = ["How does authenticate() work?"]

        result = detector.detect_intent(queries)

        # Should extract function name
        assert 'authenticate' in result.keywords

    def test_stop_words_filtered(self, detector):
        """Test that stop words are filtered out."""
        queries = ["I am trying to implement this feature"]

        result = detector.detect_intent(queries)

        # Stop words should be filtered
        stop_words = {'i', 'am', 'to', 'this'}
        for word in stop_words:
            assert word not in result.keywords

    def test_context_window_limit(self, detector):
        """Test that context window is respected."""
        queries = [
            "Old query 1",
            "Old query 2",
            "Old query 3",
            "Old query 4",
            "Old query 5",
            "Recent query with JWT authentication",
        ]

        result = detector.detect_intent(queries)

        # Should only analyze last 5 queries
        assert len(result.original_queries) == 5
        assert "Old query 1" not in result.original_queries
        assert "Recent query with JWT authentication" in result.original_queries

    def test_search_query_synthesis_implementation(self, detector):
        """Test search query synthesis for implementation intent."""
        queries = ["I need to implement OAuth2 authentication"]

        result = detector.detect_intent(queries)

        # Should synthesize implementation-focused query
        assert 'implement' in result.search_query.lower()
        assert any(kw in result.search_query for kw in ['oauth', 'authentication'])

    def test_search_query_synthesis_debugging(self, detector):
        """Test search query synthesis for debugging intent."""
        queries = ["Why does the login validation fail?"]

        result = detector.detect_intent(queries)

        # Should synthesize debugging-focused query
        query_lower = result.search_query.lower()
        assert 'fix' in query_lower or 'debug' in query_lower

    def test_search_query_synthesis_learning(self, detector):
        """Test search query synthesis for learning intent."""
        queries = ["Show me examples of middleware patterns"]

        result = detector.detect_intent(queries)

        # Should synthesize learning-focused query
        assert 'example' in result.search_query.lower()

    def test_multiple_intents_highest_wins(self, detector):
        """Test that highest scoring intent wins."""
        queries = [
            "What is JWT?",  # Learning
            "I need to implement JWT authentication",  # Implementation
            "How do I add token validation?",  # Implementation
        ]

        result = detector.detect_intent(queries)

        # Implementation should win (appears more)
        assert result.intent_type == 'implementation'

    def test_confidence_with_many_keywords(self, detector):
        """Test that more keywords increase confidence."""
        queries_few_keywords = ["implement feature"]
        queries_many_keywords = [
            "implement JWT token authentication with OAuth2 middleware validation"
        ]

        result_few = detector.detect_intent(queries_few_keywords)
        result_many = detector.detect_intent(queries_many_keywords)

        # More keywords should give higher confidence
        assert result_many.confidence > result_few.confidence

    def test_single_query(self, detector):
        """Test with single query."""
        queries = ["How do I implement authentication?"]

        result = detector.detect_intent(queries)

        assert result.intent_type == 'implementation'
        assert len(result.original_queries) == 1
        assert result.keywords  # Should extract some keywords

    def test_repeated_keywords_ranked_higher(self, detector):
        """Test that repeated keywords are ranked higher."""
        queries = [
            "I need authentication help",
            "How does authentication work?",
            "Show me authentication examples"
        ]

        result = detector.detect_intent(queries)

        # 'authentication' appears 3 times, should be top keyword
        assert result.keywords[0] == 'authentication'

    def test_general_intent_fallback(self, detector):
        """Test fallback to general intent."""
        queries = ["Hello there"]

        result = detector.detect_intent(queries)

        # Should fall back to general
        assert result.intent_type in ['general', 'learning']
        assert result.confidence < 0.5

    def test_case_insensitive_matching(self, detector):
        """Test case-insensitive pattern matching."""
        queries = ["I NEED TO IMPLEMENT JWT AUTHENTICATION"]

        result = detector.detect_intent(queries)

        assert result.intent_type == 'implementation'
        assert 'jwt' in result.keywords
        assert 'authentication' in result.keywords

    def test_special_characters_handled(self, detector):
        """Test handling of special characters."""
        queries = ["How do I fix the @authenticate() decorator?"]

        result = detector.detect_intent(queries)

        assert result.intent_type == 'debugging'
        # Should extract decorator name without special chars
        assert 'authenticate' in result.keywords

    def test_multiple_technical_terms(self, detector):
        """Test extraction of multiple technical terms."""
        queries = [
            "I need to add database caching to my API endpoints with Redis"
        ]

        result = detector.detect_intent(queries)

        # Should extract multiple technical terms
        technical_terms = ['database', 'cache', 'api', 'endpoint']
        found_terms = [term for term in technical_terms if term in result.keywords]
        assert len(found_terms) >= 2

    def test_empty_query_string(self, detector):
        """Test with empty string in query list."""
        queries = ["", "implement authentication", ""]

        result = detector.detect_intent(queries)

        # Should still work with empty strings
        assert result.intent_type == 'implementation'
        assert 'authentication' in result.keywords

    def test_very_short_query(self, detector):
        """Test with very short query."""
        queries = ["API"]

        result = detector.detect_intent(queries)

        # Should extract the keyword
        assert 'api' in result.keywords
        assert result.search_query  # Should still generate query
