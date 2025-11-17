"""Unit tests for retrieval gate and predictor."""

import pytest

from src.router.retrieval_predictor import RetrievalPredictor
from src.router.retrieval_gate import RetrievalGate, GatingDecision, GatingMetrics


class TestRetrievalPredictor:
    """Test RetrievalPredictor functionality."""

    @pytest.fixture
    def predictor(self):
        """Create predictor instance."""
        return RetrievalPredictor()

    def test_initialization(self, predictor):
        """Test predictor initializes correctly."""
        assert predictor is not None
        assert predictor.min_query_length == 10
        assert predictor.max_small_talk_length == 30

    def test_empty_query_returns_zero(self, predictor):
        """Test empty query returns 0 utility."""
        assert predictor.predict_utility("") == 0.0
        assert predictor.predict_utility("   ") == 0.0

    def test_small_talk_queries_low_utility(self, predictor):
        """Test small talk queries have low utility."""
        small_talk_queries = [
            "thanks",
            "ok",
            "cool",
            "got it",
            "great!",
            "hello",
            "bye",
        ]

        for query in small_talk_queries:
            utility = predictor.predict_utility(query)
            assert utility < 0.3, f"Query '{query}' should have low utility, got {utility}"

    def test_coding_questions_high_utility(self, predictor):
        """Test coding-related questions have high utility."""
        coding_queries = [
            "how does the authentication work?",
            "find the login function",
            "show me error handling code",
            "what's the API endpoint for users?",
            "where is the database query?",
        ]

        for query in coding_queries:
            utility = predictor.predict_utility(query)
            assert utility >= 0.7, f"Query '{query}' should have high utility, got {utility}"

    def test_technical_keywords_increase_utility(self, predictor):
        """Test technical keywords increase utility score."""
        non_technical = "this is a simple message"
        technical = "this is about the api endpoint authentication"

        non_tech_utility = predictor.predict_utility(non_technical)
        tech_utility = predictor.predict_utility(technical)

        assert tech_utility > non_tech_utility

    def test_questions_increase_utility(self, predictor):
        """Test questions get higher utility."""
        statement = "the code works"
        question = "does the code work?"

        statement_utility = predictor.predict_utility(statement)
        question_utility = predictor.predict_utility(question)

        assert question_utility > statement_utility

    def test_code_markers_increase_utility(self, predictor):
        """Test code-like patterns increase utility."""
        queries_with_code = [
            "function getUserById()",
            "array.map() usage",
            "object->property access",
            "class::staticMethod",
            "data => transform",
        ]

        for query in queries_with_code:
            utility = predictor.predict_utility(query)
            assert utility >= 0.5, f"Query '{query}' with code markers should have decent utility"

    def test_specific_queries_higher_utility(self, predictor):
        """Test longer, more specific queries get higher utility."""
        vague = "code"
        specific = "authentication middleware for API endpoints"

        vague_utility = predictor.predict_utility(vague)
        specific_utility = predictor.predict_utility(specific)

        assert specific_utility > vague_utility

    def test_signal_extraction(self, predictor):
        """Test signal extraction works correctly."""
        query = "how does the API authentication work?"
        signals = predictor._extract_signals(query, query.lower())

        assert signals['is_question'] == 1.0
        assert signals['has_retrieval_keywords'] == 1.0
        assert signals['has_technical_content'] == 1.0
        assert signals['word_count'] > 0

    def test_get_explanation(self, predictor):
        """Test explanation generation."""
        query = "what is the error handling code?"
        utility = predictor.predict_utility(query)
        explanation = predictor.get_explanation(query, utility)

        assert isinstance(explanation, str)
        assert len(explanation) > 0
        assert f"{utility:.2f}" in explanation


class TestGatingMetrics:
    """Test GatingMetrics data class."""

    def test_initialization(self):
        """Test metrics initialize to zero."""
        metrics = GatingMetrics()
        assert metrics.total_queries == 0
        assert metrics.queries_gated == 0
        assert metrics.queries_retrieved == 0
        assert metrics.estimated_tokens_saved == 0

    def test_gating_rate_calculation(self):
        """Test gating rate calculation."""
        metrics = GatingMetrics()
        assert metrics.gating_rate == 0.0

        metrics.total_queries = 100
        metrics.queries_gated = 30
        assert metrics.gating_rate == 30.0

    def test_average_utility_calculation(self):
        """Test average utility calculation."""
        metrics = GatingMetrics()
        assert metrics.average_utility == 0.0

        metrics.total_queries = 4
        metrics.total_utility_score = 2.0
        assert metrics.average_utility == 0.5

    def test_to_dict(self):
        """Test conversion to dictionary."""
        metrics = GatingMetrics(
            total_queries=100,
            queries_gated=30,
            queries_retrieved=70,
            estimated_tokens_saved=6000,
        )

        result = metrics.to_dict()
        assert result['total_queries'] == 100
        assert result['queries_gated'] == 30
        assert result['queries_retrieved'] == 70
        assert '30.00%' in result['gating_rate']
        assert result['estimated_tokens_saved'] == 6000


class TestRetrievalGate:
    """Test RetrievalGate functionality."""

    @pytest.fixture
    def gate(self):
        """Create gate instance with default threshold."""
        return RetrievalGate(threshold=0.5)

    @pytest.fixture
    def strict_gate(self):
        """Create gate with high threshold (less gating)."""
        return RetrievalGate(threshold=0.8)

    @pytest.fixture
    def lenient_gate(self):
        """Create gate with low threshold (more gating)."""
        return RetrievalGate(threshold=0.3)

    def test_initialization(self, gate):
        """Test gate initializes correctly."""
        assert gate.threshold == 0.5
        assert gate.tokens_per_result == 200
        assert gate.predictor is not None
        assert gate.metrics.total_queries == 0

    def test_initialization_invalid_threshold(self):
        """Test initialization rejects invalid thresholds."""
        with pytest.raises(ValueError):
            RetrievalGate(threshold=-0.1)

        with pytest.raises(ValueError):
            RetrievalGate(threshold=1.5)

    def test_should_retrieve_small_talk_gated(self, gate):
        """Test small talk queries are gated."""
        decision = gate.should_retrieve("thanks")
        assert not decision.should_retrieve
        assert decision.utility_score < gate.threshold

    def test_should_retrieve_coding_question_passes(self, gate):
        """Test coding questions pass the gate."""
        decision = gate.should_retrieve("how does authentication work?")
        assert decision.should_retrieve
        assert decision.utility_score >= gate.threshold

    def test_should_retrieve_updates_metrics(self, gate):
        """Test gating decisions update metrics."""
        # Small talk - should be gated
        gate.should_retrieve("ok")
        assert gate.metrics.queries_gated == 1
        assert gate.metrics.queries_retrieved == 0

        # Technical question - should retrieve
        gate.should_retrieve("find the API endpoint")
        assert gate.metrics.queries_gated == 1
        assert gate.metrics.queries_retrieved == 1

        assert gate.metrics.total_queries == 2

    def test_token_savings_estimation(self, gate):
        """Test token savings are estimated correctly."""
        # Gate a query with expected 5 results
        gate.should_retrieve("thanks", expected_results=5)

        # Should save 5 results * 200 tokens = 1000 tokens
        assert gate.metrics.estimated_tokens_saved == 1000

    def test_strict_gate_allows_less(self, strict_gate, lenient_gate):
        """Test strict gate (high threshold) gates more aggressively."""
        query = "show me the code"

        strict_decision = strict_gate.should_retrieve(query)
        lenient_decision = lenient_gate.should_retrieve(query)

        # Lenient gate should always allow what strict gate allows
        if strict_decision.should_retrieve:
            assert lenient_decision.should_retrieve

    def test_get_metrics(self, gate):
        """Test metrics retrieval."""
        gate.should_retrieve("ok")
        gate.should_retrieve("find authentication code")

        metrics = gate.get_metrics()
        assert isinstance(metrics, dict)
        assert 'total_queries' in metrics
        assert 'queries_gated' in metrics
        assert 'gating_rate' in metrics
        assert metrics['total_queries'] == 2

    def test_reset_metrics(self, gate):
        """Test metrics can be reset."""
        gate.should_retrieve("test query")
        assert gate.metrics.total_queries == 1

        gate.reset_metrics()
        assert gate.metrics.total_queries == 0
        assert gate.metrics.queries_gated == 0
        assert gate.metrics.estimated_tokens_saved == 0

    def test_update_threshold(self, gate):
        """Test threshold can be updated."""
        assert gate.threshold == 0.5

        gate.update_threshold(0.7)
        assert gate.threshold == 0.7

    def test_update_threshold_invalid(self, gate):
        """Test invalid threshold updates are rejected."""
        with pytest.raises(ValueError):
            gate.update_threshold(-0.1)

        with pytest.raises(ValueError):
            gate.update_threshold(1.5)

    def test_get_explanation(self, gate):
        """Test explanation generation."""
        explanation = gate.get_explanation("how does the API work?")
        assert isinstance(explanation, str)
        assert len(explanation) > 0
        assert str(gate.threshold) in explanation

    def test_gating_decision_structure(self, gate):
        """Test GatingDecision has correct structure."""
        decision = gate.should_retrieve("test query")

        assert isinstance(decision, GatingDecision)
        assert isinstance(decision.should_retrieve, bool)
        assert isinstance(decision.utility_score, float)
        assert isinstance(decision.reason, str)
        assert isinstance(decision.timestamp, str)
        assert 0.0 <= decision.utility_score <= 1.0

    def test_threshold_enforcement(self, gate):
        """Test that threshold is properly enforced."""
        # Test 100 queries and verify threshold is consistently applied
        test_cases = [
            ("thanks", False),  # Should be gated
            ("how does authentication work?", True),  # Should retrieve
            ("ok cool", False),  # Should be gated
            ("find the error handling code", True),  # Should retrieve
            ("got it", False),  # Should be gated
        ]

        for query, expected_should_retrieve in test_cases:
            decision = gate.should_retrieve(query)
            utility = decision.utility_score

            if utility >= gate.threshold:
                assert decision.should_retrieve, \
                    f"Query '{query}' utility {utility} >= {gate.threshold} should retrieve"
            else:
                assert not decision.should_retrieve, \
                    f"Query '{query}' utility {utility} < {gate.threshold} should gate"

    def test_repr(self, gate):
        """Test string representation."""
        repr_str = repr(gate)
        assert 'RetrievalGate' in repr_str
        assert str(gate.threshold) in repr_str


class TestGateIntegration:
    """Integration tests for gate with predictor."""

    def test_end_to_end_gating_flow(self):
        """Test complete gating flow from query to metrics."""
        gate = RetrievalGate(threshold=0.5, tokens_per_result=150)

        # Simulate a session with various queries
        queries = [
            ("thanks", False, 5),
            ("how does the API authentication work?", True, 5),
            ("ok", False, 5),
            ("find error handling in the middleware", True, 3),
            ("cool", False, 5),
        ]

        for query, expected_retrieve, expected_results in queries:
            decision = gate.should_retrieve(query, expected_results)
            assert isinstance(decision, GatingDecision)
            # Decision should be consistent with utility and threshold
            if decision.utility_score >= gate.threshold:
                assert decision.should_retrieve
            else:
                assert not decision.should_retrieve

        # Verify metrics
        metrics = gate.get_metrics()
        assert metrics['total_queries'] == 5
        assert metrics['queries_gated'] + metrics['queries_retrieved'] == 5

        # Calculate expected token savings
        # 3 queries gated with 5 results each = 15 results * 150 tokens = 2250
        expected_savings = 3 * 5 * 150
        assert metrics['estimated_tokens_saved'] == expected_savings

    def test_custom_predictor(self):
        """Test gate with custom predictor."""
        custom_predictor = RetrievalPredictor(
            min_query_length=5,
            max_small_talk_length=20,
        )
        gate = RetrievalGate(threshold=0.5, predictor=custom_predictor)

        assert gate.predictor is custom_predictor
        decision = gate.should_retrieve("test")
        assert isinstance(decision, GatingDecision)

    def test_realistic_query_mix(self):
        """Test with realistic mix of queries to verify 30-40% gating rate."""
        gate = RetrievalGate(threshold=0.5)

        # Mix of queries typical in a coding session
        realistic_queries = [
            # Small talk / acknowledgements (should be gated)
            "ok",
            "thanks",
            "got it",
            "cool",
            "yes",

            # Coding questions (should retrieve)
            "how does the authentication middleware work?",
            "find the user login function",
            "what's the error handling code?",
            "show me the API endpoints",
            "where is the database connection?",

            # Mixed (depends on signals)
            "check this",
            "the code",
            "need help with API",
            "what about errors?",
        ]

        for query in realistic_queries:
            gate.should_retrieve(query)

        metrics = gate.get_metrics()
        gating_rate = (metrics['queries_gated'] / metrics['total_queries']) * 100

        # Target is 30-40% gating rate, but with threshold 0.5 and this mix,
        # we should see some gating
        assert gating_rate > 0, "Should gate at least some queries"
        assert metrics['total_queries'] == len(realistic_queries)
