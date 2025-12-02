"""Tests for Query DSL Parser (FEAT-018)."""

import pytest
from src.search.query_dsl_parser import QueryDSLParser


@pytest.fixture
def parser():
    """Create parser instance."""
    return QueryDSLParser()


class TestBasicParsing:
    """Test basic query parsing."""

    def test_empty_query(self, parser):
        """Test empty query."""
        result = parser.parse("")
        assert result.semantic_query == ""
        assert result.filters == {}
        assert result.exclusions == []

    def test_simple_semantic_query(self, parser):
        """Test simple semantic query without filters."""
        result = parser.parse("error handling")
        assert result.semantic_query == "error handling"
        assert result.filters == {}

    def test_query_with_single_filter(self, parser):
        """Test query with one filter."""
        result = parser.parse("error handling language:python")
        assert result.semantic_query == "error handling"
        assert result.filters == {"language": "python"}

    def test_query_with_multiple_filters(self, parser):
        """Test query with multiple filters."""
        result = parser.parse("authentication language:python file:src/**/*.py")
        assert result.semantic_query == "authentication"
        assert result.filters["language"] == "python"
        assert result.filters["file"] == "src/**/*.py"


class TestFilterAliases:
    """Test filter aliases."""

    def test_lang_alias(self, parser):
        """Test lang: alias for language:."""
        result = parser.parse("test lang:python")
        assert result.filters["language"] == "python"

    def test_path_alias(self, parser):
        """Test path: alias for file:."""
        result = parser.parse("test path:src/**/*.py")
        assert result.filters["file"] == "src/**/*.py"

    def test_proj_alias(self, parser):
        """Test proj: alias for project:."""
        result = parser.parse("test proj:web-app")
        assert result.filters["project"] == "web-app"


class TestDateFilters:
    """Test date filtering."""

    def test_created_after_date(self, parser):
        """Test created:> filter."""
        result = parser.parse("login created:>2024-01-01")
        assert result.semantic_query == "login"
        assert result.filters["created"] == {"gt": "2024-01-01"}

    def test_created_before_date(self, parser):
        """Test created:< filter."""
        result = parser.parse("login created:<2024-12-31")
        assert result.filters["created"] == {"lt": "2024-12-31"}

    def test_created_on_or_after(self, parser):
        """Test created:>= filter."""
        result = parser.parse("login created:>=2024-01-01")
        assert result.filters["created"] == {"gte": "2024-01-01"}

    def test_created_date_range(self, parser):
        """Test created date range."""
        result = parser.parse("login created:2024-01-01..2024-12-31")
        assert result.filters["created"] == {"gte": "2024-01-01", "lte": "2024-12-31"}

    def test_modified_filter(self, parser):
        """Test modified date filter."""
        result = parser.parse("code modified:>2024-06-01")
        assert result.filters["modified"] == {"gt": "2024-06-01"}


class TestExclusions:
    """Test exclusion filters."""

    def test_file_exclusion(self, parser):
        """Test -file: exclusion."""
        result = parser.parse("testing -file:test")
        assert result.semantic_query == "testing"
        assert "test" in result.exclusions

    def test_multiple_exclusions(self, parser):
        """Test multiple exclusions."""
        result = parser.parse("code -file:test -file:spec")
        assert "test" in result.exclusions
        assert "spec" in result.exclusions


class TestComplexQueries:
    """Test complex query combinations."""

    def test_kitchen_sink_query(self, parser):
        """Test query with all filter types."""
        result = parser.parse(
            "authentication language:python file:src/**/*.py "
            "project:web-app created:>2024-01-01 -file:test"
        )
        assert result.semantic_query == "authentication"
        assert result.filters["language"] == "python"
        assert result.filters["file"] == "src/**/*.py"
        assert result.filters["project"] == "web-app"
        assert result.filters["created"] == {"gt": "2024-01-01"}
        assert "test" in result.exclusions

    def test_quoted_filter_values(self, parser):
        """Test quoted filter values."""
        result = parser.parse('error file:"path with spaces/file.py"')
        assert result.filters["file"] == "path with spaces/file.py"


class TestInvalidInputs:
    """Test handling of invalid inputs."""

    def test_invalid_date_format(self, parser):
        """Test invalid date format raises error."""
        with pytest.raises(ValueError, match="Invalid date format"):
            parser.parse("test created:>invalid-date")

    def test_unknown_filter_treated_as_semantic(self, parser):
        """Test unknown filters are treated as semantic terms."""
        result = parser.parse("error unknownfilter:value")
        assert "unknownfilter:value" in result.semantic_query

    def test_whitespace_handling(self, parser):
        """Test whitespace is handled correctly."""
        result = parser.parse("  error   handling   language:python  ")
        assert "error" in result.semantic_query
        assert "handling" in result.semantic_query
        assert result.filters["language"] == "python"


class TestGetFilterHelp:
    """Test filter help output."""

    def test_get_filter_help(self, parser):
        """Test get_filter_help returns help text."""
        help_text = parser.get_filter_help()
        assert "language:" in help_text
        assert "file:" in help_text
        assert "created:" in help_text
        assert "Examples:" in help_text
