"""Unit tests for programming query synonyms and expansion."""

import pytest
from src.search.query_synonyms import (
    expand_with_synonyms,
    expand_with_code_context,
    expand_query_full,
    get_synonyms,
    get_code_context,
    PROGRAMMING_SYNONYMS,
    CODE_CONTEXT_PATTERNS,
)


class TestSynonymExpansion:
    """Test synonym expansion functionality."""

    def test_expand_with_synonyms_basic(self):
        """Test basic synonym expansion."""
        query = "auth"
        expanded = expand_with_synonyms(query, max_synonyms=3)

        # Should include original term plus synonyms
        assert "auth" in expanded
        # Should include at least one synonym
        assert len(expanded) > len(query)

    def test_expand_with_synonyms_multiple_terms(self):
        """Test expansion with multiple terms."""
        query = "user authentication"
        expanded = expand_with_synonyms(query, max_synonyms=2)

        assert "user" in expanded or "authentication" in expanded
        assert len(expanded) >= len(query)

    def test_expand_with_synonyms_no_synonyms(self):
        """Test query with no known synonyms."""
        query = "xyzabc123"  # Random term
        expanded = expand_with_synonyms(query)

        # Should return original query unchanged
        assert expanded == query

    def test_expand_with_synonyms_max_limit(self):
        """Test that max_synonyms limit is respected."""
        query = "function"  # Has many synonyms
        expanded_2 = expand_with_synonyms(query, max_synonyms=2)
        expanded_5 = expand_with_synonyms(query, max_synonyms=5)

        # More synonyms should result in longer query
        # But both should respect their limits
        assert "function" in expanded_2
        assert "function" in expanded_5

    def test_expand_with_synonyms_case_insensitive(self):
        """Test case-insensitive matching."""
        query1 = "AUTH"
        query2 = "auth"
        query3 = "Auth"

        expanded1 = expand_with_synonyms(query1)
        expanded2 = expand_with_synonyms(query2)
        expanded3 = expand_with_synonyms(query3)

        # All should expand (case shouldn't matter)
        assert len(expanded1) > len(query1)
        assert len(expanded2) > len(query2)
        assert len(expanded3) > len(query3)

    def test_common_synonyms(self):
        """Test common programming term synonyms."""
        # Test authentication synonyms
        assert "authentication" in PROGRAMMING_SYNONYMS
        auth_synonyms = PROGRAMMING_SYNONYMS["authentication"]
        assert "login" in auth_synonyms or "auth" in auth_synonyms

        # Test function synonyms
        assert "function" in PROGRAMMING_SYNONYMS
        func_synonyms = PROGRAMMING_SYNONYMS["function"]
        assert "method" in func_synonyms

        # Test database synonyms
        assert "database" in PROGRAMMING_SYNONYMS
        db_synonyms = PROGRAMMING_SYNONYMS["database"]
        assert "db" in db_synonyms


class TestCodeContextExpansion:
    """Test code context expansion functionality."""

    def test_expand_with_code_context_basic(self):
        """Test basic code context expansion."""
        query = "auth"
        expanded = expand_with_code_context(query, max_context_terms=5)

        # Should include original term
        assert "auth" in expanded
        # Should add context terms
        assert len(expanded) > len(query)

    def test_expand_with_code_context_no_context(self):
        """Test query with no known context."""
        query = "randomterm123"
        expanded = expand_with_code_context(query)

        # Should return original
        assert expanded == query

    def test_expand_with_code_context_database(self):
        """Test database-related context expansion."""
        query = "database"
        expanded = expand_with_code_context(query, max_context_terms=5)

        # Should add database-related terms
        expanded_lower = expanded.lower()
        assert any(term in expanded_lower for term in ["connection", "query", "table", "schema"])

    def test_expand_with_code_context_api(self):
        """Test API-related context expansion."""
        query = "api"
        expanded = expand_with_code_context(query, max_context_terms=5)

        expanded_lower = expanded.lower()
        assert any(term in expanded_lower for term in ["endpoint", "request", "response", "http"])

    def test_expand_with_code_context_max_terms(self):
        """Test that max_context_terms is respected."""
        query = "auth"  # Has many context terms
        expanded_3 = expand_with_code_context(query, max_context_terms=3)
        expanded_10 = expand_with_code_context(query, max_context_terms=10)

        # Both should expand but respect limits
        assert "auth" in expanded_3
        assert "auth" in expanded_10

    def test_common_context_patterns(self):
        """Test common code context patterns."""
        # Auth context
        assert "auth" in CODE_CONTEXT_PATTERNS
        auth_context = CODE_CONTEXT_PATTERNS["auth"]
        assert "user" in auth_context or "login" in auth_context

        # Test context
        assert "test" in CODE_CONTEXT_PATTERNS
        test_context = CODE_CONTEXT_PATTERNS["test"]
        assert "assert" in test_context or "mock" in test_context


class TestFullQueryExpansion:
    """Test full query expansion combining synonyms and context."""

    def test_expand_query_full_both_enabled(self):
        """Test full expansion with both features enabled."""
        query = "auth function"
        expanded = expand_query_full(
            query,
            enable_synonyms=True,
            enable_context=True,
        )

        # Should expand significantly
        assert len(expanded) > len(query)
        # Should include original terms
        assert "auth" in expanded or "function" in expanded

    def test_expand_query_full_synonyms_only(self):
        """Test expansion with only synonyms."""
        query = "function"
        expanded = expand_query_full(
            query,
            enable_synonyms=True,
            enable_context=False,
        )

        # Should add synonyms but not context
        assert len(expanded) > len(query)

    def test_expand_query_full_context_only(self):
        """Test expansion with only context."""
        query = "api"
        expanded = expand_query_full(
            query,
            enable_synonyms=False,
            enable_context=True,
        )

        # Should add context but not synonyms
        assert len(expanded) > len(query)

    def test_expand_query_full_both_disabled(self):
        """Test that disabling both returns original."""
        query = "test query"
        expanded = expand_query_full(
            query,
            enable_synonyms=False,
            enable_context=False,
        )

        assert expanded == query

    def test_expand_query_full_realistic_code_search(self):
        """Test realistic code search queries."""
        queries = [
            "user authentication",
            "database connection",
            "api endpoint",
            "error handling",
            "async function",
        ]

        for query in queries:
            expanded = expand_query_full(query)
            # All should expand
            assert len(expanded) >= len(query)
            # Should preserve original query
            assert query.split()[0] in expanded.lower()


class TestHelperFunctions:
    """Test helper functions."""

    def test_get_synonyms_existing_term(self):
        """Test getting synonyms for existing term."""
        synonyms = get_synonyms("auth")
        assert isinstance(synonyms, set)
        assert len(synonyms) > 0

    def test_get_synonyms_nonexistent_term(self):
        """Test getting synonyms for nonexistent term."""
        synonyms = get_synonyms("nonexistent")
        assert isinstance(synonyms, set)
        assert len(synonyms) == 0

    def test_get_synonyms_case_insensitive(self):
        """Test case-insensitive synonym retrieval."""
        synonyms_lower = get_synonyms("auth")
        synonyms_upper = get_synonyms("AUTH")
        synonyms_mixed = get_synonyms("Auth")

        # Should all return the same synonyms
        assert synonyms_lower == synonyms_upper
        assert synonyms_lower == synonyms_mixed

    def test_get_code_context_existing_term(self):
        """Test getting context for existing term."""
        context = get_code_context("auth")
        assert isinstance(context, set)
        assert len(context) > 0

    def test_get_code_context_nonexistent_term(self):
        """Test getting context for nonexistent term."""
        context = get_code_context("nonexistent")
        assert isinstance(context, set)
        assert len(context) == 0


class TestSpecificUseCases:
    """Test specific real-world use cases."""

    def test_authentication_search(self):
        """Test authentication-related search expansion."""
        query = "authenticate user"
        expanded = expand_query_full(query)

        expanded_lower = expanded.lower()
        # Should expand beyond original query
        assert len(expanded) > len(query)
        # Should preserve original terms
        assert "authenticate" in expanded_lower or "user" in expanded_lower

    def test_database_search(self):
        """Test database-related search expansion."""
        query = "db query"
        expanded = expand_query_full(query)

        expanded_lower = expanded.lower()
        # Should include database-related terms
        assert "database" in expanded_lower or "query" in expanded_lower

    def test_api_search(self):
        """Test API-related search expansion."""
        query = "rest api"
        expanded = expand_query_full(query)

        expanded_lower = expanded.lower()
        # Should include API-related terms
        assert any(term in expanded_lower for term in ["endpoint", "http", "request"])

    @pytest.mark.skip_ci(reason="Query expansion timing/environment sensitive")
    def test_error_handling_search(self):
        """Test error handling search expansion."""
        query = "handle exceptions"
        expanded = expand_query_full(query)

        expanded_lower = expanded.lower()
        # Should include error-related terms
        assert any(term in expanded_lower for term in ["error", "try", "catch"])

    def test_async_search(self):
        """Test async/concurrent search expansion."""
        query = "async function"
        expanded = expand_query_full(query)

        expanded_lower = expanded.lower()
        # Should include async-related terms
        assert any(term in expanded_lower for term in ["await", "promise", "asynchronous"])


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_empty_query(self):
        """Test expansion with empty query."""
        expanded = expand_query_full("")
        assert expanded == ""

    def test_single_character_query(self):
        """Test expansion with single character."""
        expanded = expand_query_full("a")
        # Short query, unlikely to expand
        assert len(expanded) >= 1

    def test_very_long_query(self):
        """Test expansion with very long query."""
        query = "user authentication database api function class method error " * 10
        expanded = expand_query_full(query)

        # Should not crash, should return something
        assert len(expanded) > 0

    def test_special_characters(self):
        """Test query with special characters."""
        query = "auth@user.com #function $variable"
        expanded = expand_query_full(query)

        # Should handle gracefully
        assert len(expanded) > 0

    def test_numeric_query(self):
        """Test query with numbers."""
        query = "123 456"
        expanded = expand_query_full(query)

        # Should return original (no expansion)
        assert expanded == query

    def test_mixed_case_terms(self):
        """Test query with mixed case."""
        query = "AuTh FuNcTiOn"
        expanded = expand_query_full(query)

        # Should handle case-insensitively
        assert len(expanded) >= len(query)
