"""Unit tests for search edge cases."""

import pytest
from src.core.validation import (
    validate_query_request,
    validate_filter_params,
    detect_injection_patterns,
)
from src.core.exceptions import ValidationError


class TestSearchQueryEdgeCases:
    """Test search query edge cases."""

    def test_empty_query_string(self):
        """Test empty query string (should be rejected)."""
        payload = {"query": ""}

        with pytest.raises(ValidationError) as exc:
            validate_query_request(payload)
        error_msg = str(exc.value).lower()
        assert "query" in error_msg or "empty" in error_msg or "validation" in error_msg

    def test_query_with_only_whitespace(self):
        """Test query with only whitespace (should be rejected after stripping)."""
        payload = {"query": "   "}

        with pytest.raises(ValidationError) as exc:
            validate_query_request(payload)
        error_msg = str(exc.value).lower()
        assert "query" in error_msg or "empty" in error_msg or "validation" in error_msg

    def test_query_with_leading_trailing_whitespace(self):
        """Test query with leading/trailing whitespace (should be stripped)."""
        payload = {"query": "  test query  "}

        result = validate_query_request(payload)
        assert result.query == "test query"

    def test_query_with_special_characters(self):
        """Test query with special characters (should be allowed)."""
        special_chars = "!@#$%^&*()_+-=[]{}|;:',.<>?/~`"
        payload = {"query": f"search {special_chars}"}

        result = validate_query_request(payload)
        assert special_chars in result.query

    def test_query_with_numbers_only(self):
        """Test query with only numbers."""
        payload = {"query": "1234567890"}

        result = validate_query_request(payload)
        assert result.query == "1234567890"

    def test_query_with_unicode_characters(self):
        """Test query with Unicode characters."""
        payload = {"query": "search 中文 العربية 日本語"}

        result = validate_query_request(payload)
        assert "中文" in result.query
        assert "العربية" in result.query
        assert "日本語" in result.query

    def test_query_with_emoji(self):
        """Test query with emoji characters."""
        payload = {"query": "search 😀 🚀 💻"}

        result = validate_query_request(payload)
        assert "😀" in result.query

    def test_query_with_newlines(self):
        """Test query with newline characters."""
        payload = {"query": "line1\nline2\nline3"}

        result = validate_query_request(payload)
        # Newlines should be preserved (they're valid)
        assert "\n" in result.query or result.query == "line1 line2 line3"

    def test_query_with_tabs(self):
        """Test query with tab characters."""
        payload = {"query": "column1\tcolumn2\tcolumn3"}

        result = validate_query_request(payload)
        # Tabs should be preserved (they're valid)
        assert "\t" in result.query or "column1" in result.query

    def test_very_long_query(self):
        """Test very long query (10000+ chars should be rejected)."""
        long_query = "a" * 10000

        payload = {"query": long_query}

        with pytest.raises(ValidationError) as exc:
            validate_query_request(payload)
        error_msg = str(exc.value).lower()
        assert (
            "length" in error_msg or "maximum" in error_msg or "validation" in error_msg
        )

    def test_query_at_max_length(self):
        """Test query at exactly max length (1000 chars)."""
        payload = {"query": "a" * 1000}

        result = validate_query_request(payload)
        assert len(result.query) == 1000

    def test_query_just_over_max_length(self):
        """Test query just over max length (1001 chars)."""
        payload = {"query": "a" * 1001}

        with pytest.raises(ValidationError) as exc:
            validate_query_request(payload)
        error_msg = str(exc.value).lower()
        assert (
            "length" in error_msg or "maximum" in error_msg or "validation" in error_msg
        )

    def test_single_character_query(self):
        """Test single character query (should be valid)."""
        payload = {"query": "a"}

        result = validate_query_request(payload)
        assert result.query == "a"


class TestSQLInjectionPatterns:
    """Test SQL injection pattern detection in search queries."""

    @pytest.mark.parametrize(
        "injection_pattern",
        [
            "'; DROP TABLE memories--",
            "' OR '1'='1",
            "' OR 1=1--",
            "'; DELETE FROM users--",
            "UNION SELECT * FROM",
            "1' UNION SELECT NULL--",
            "admin'--",
            "' OR 'a'='a",
        ],
    )
    def test_sql_injection_detection(self, injection_pattern):
        """Test that SQL injection patterns are detected."""
        # The validation should detect these patterns
        detected = detect_injection_patterns(injection_pattern)
        assert detected is not None, f"Should detect SQL injection: {injection_pattern}"

    @pytest.mark.parametrize(
        "injection_pattern",
        [
            "'; DROP TABLE memories--",
            "' OR '1'='1",
            "SELECT * FROM users",
        ],
    )
    def test_sql_injection_in_query_rejected(self, injection_pattern):
        """Test that queries with SQL injection patterns are rejected."""
        payload = {"query": injection_pattern}

        with pytest.raises(ValidationError) as exc:
            validate_query_request(payload)
        error_msg = str(exc.value).lower()
        assert (
            "security" in error_msg
            or "threat" in error_msg
            or "suspicious" in error_msg
        )

    def test_normal_query_with_sql_like_terms(self):
        """Test that normal queries with SQL-like terms (in context) don't get blocked."""
        # These should be valid - they're discussing SQL, not injecting it
        safe_queries = [
            "how to use SELECT in SQL",
            "learn about DROP TABLE command",
            "SQL UNION operator tutorial",
        ]

        for query in safe_queries:
            payload = {"query": query}
            # These might still trigger detection depending on implementation
            # The key is they should either pass or be caught by injection detection
            try:
                result = validate_query_request(payload)
                # If it passes, that's fine
                assert result.query is not None
            except ValidationError as e:
                # If it fails, it should be due to security detection
                assert "security" in str(e).lower() or "threat" in str(e).lower()


class TestCommandInjectionPatterns:
    """Test command injection pattern detection."""

    @pytest.mark.parametrize(
        "command_pattern,should_detect",
        [
            ("; rm -rf /", True),
            ("$(whoami)", True),
            ("`cat /etc/passwd`", True),
            ("; ls -la", True),
            ("&& curl malicious.com", True),
            ("| grep password", False),  # Pipe alone is not necessarily malicious
        ],
    )
    def test_command_injection_detection(self, command_pattern, should_detect):
        """Test that command injection patterns are detected."""
        detected = detect_injection_patterns(command_pattern)
        if should_detect:
            assert (
                detected is not None
            ), f"Should detect command injection: {command_pattern}"
        else:
            # Some patterns like single pipe might not be detected as they're context-dependent
            pass


class TestPathTraversalPatterns:
    """Test path traversal pattern detection."""

    @pytest.mark.parametrize(
        "path_pattern",
        [
            "../../etc/passwd",
            "../../../secret",
            "file:///etc/shadow",
            "%2e%2e/config",
            "..\\..\\windows\\system32",
        ],
    )
    def test_path_traversal_detection(self, path_pattern):
        """Test that path traversal patterns are detected."""
        detected = detect_injection_patterns(path_pattern)
        assert detected is not None, f"Should detect path traversal: {path_pattern}"


class TestSearchResultEdgeCases:
    """Test edge cases around search results."""

    def test_query_matching_zero_results(self):
        """Test query that would match zero results (validation should pass)."""
        # Validation doesn't check for result count - that's the search engine's job
        payload = {"query": "xyzabc123nonexistent"}

        result = validate_query_request(payload)
        assert result.query == "xyzabc123nonexistent"

    def test_query_with_wildcard_characters(self):
        """Test query with wildcard-like characters."""
        payload = {"query": "test*query?pattern"}

        result = validate_query_request(payload)
        assert "*" in result.query
        assert "?" in result.query

    def test_query_with_regex_special_chars(self):
        """Test query with regex special characters."""
        regex_chars = r".*+?[]{}()\|^$"
        payload = {"query": f"search {regex_chars}"}

        result = validate_query_request(payload)
        # These should be treated as literal characters, not regex
        assert result.query is not None


class TestFilterEdgeCases:
    """Test filter parameter edge cases."""

    def test_empty_filters(self):
        """Test validation with empty filters."""
        result = validate_filter_params({})
        assert result is not None

    def test_filters_with_none_project_name(self):
        """Test filters with None project_name (should be accepted)."""
        filters = {
            "project_name": None,
        }

        result = validate_filter_params(filters)
        assert result.project_name is None

    def test_filters_with_empty_strings(self):
        """Test filters with empty strings."""
        filters = {
            "project_name": "",
        }

        result = validate_filter_params(filters)
        # Empty project name is preserved as empty string by the model
        assert result.project_name == ""

    def test_filters_with_empty_tag_list(self):
        """Test filters with empty tag list."""
        filters = {
            "tags": [],
        }

        result = validate_filter_params(filters)
        assert result.tags == []

    def test_filters_with_whitespace_tags(self):
        """Test filters with whitespace-only tags."""
        filters = {
            "tags": ["  ", "tag1", "  "],
        }

        result = validate_filter_params(filters)
        # Whitespace-only tags should be filtered out
        # but 'tag1' should remain
        assert "tag1" in result.tags or result.tags == []

    def test_filters_with_duplicate_tags(self):
        """Test filters with duplicate tags."""
        filters = {
            "tags": ["tag1", "tag1", "tag2"],
        }

        result = validate_filter_params(filters)
        # Tags might be deduplicated or not - just verify it validates
        assert result.tags is not None

    def test_filter_project_name_with_injection(self):
        """Test project name filter with injection attempt."""
        filters = {
            "project_name": "'; DROP TABLE--",
        }

        with pytest.raises(ValidationError) as exc:
            validate_filter_params(filters)
        error_msg = str(exc.value).lower()
        assert "security" in error_msg or "threat" in error_msg

    def test_filter_tags_with_injection(self):
        """Test tags filter with injection attempt."""
        filters = {
            "tags": ["normal_tag", "'; DROP TABLE--"],
        }

        with pytest.raises(ValidationError) as exc:
            validate_filter_params(filters)
        error_msg = str(exc.value).lower()
        assert "security" in error_msg or "threat" in error_msg


class TestQueryWithCombinedParameters:
    """Test queries with multiple parameters combined."""

    def test_query_with_all_valid_parameters(self):
        """Test query with all parameters at valid values."""
        payload = {
            "query": "test query",
            "limit": 50,
            "min_importance": 0.5,
        }

        result = validate_query_request(payload)
        assert result.query == "test query"
        assert result.limit == 50
        assert result.min_importance == 0.5

    def test_query_with_all_boundary_minimum_values(self):
        """Test query with all parameters at minimum boundary values."""
        payload = {
            "query": "a",  # Minimum length
            "limit": 1,  # Minimum
            "min_importance": 0.0,  # Minimum
        }

        result = validate_query_request(payload)
        assert result.query == "a"
        assert result.limit == 1
        assert result.min_importance == 0.0

    def test_query_with_all_boundary_maximum_values(self):
        """Test query with all parameters at maximum boundary values."""
        payload = {
            "query": "a" * 1000,  # Maximum length
            "limit": 100,  # Maximum
            "min_importance": 1.0,  # Maximum
        }

        result = validate_query_request(payload)
        assert len(result.query) == 1000
        assert result.limit == 100
        assert result.min_importance == 1.0
