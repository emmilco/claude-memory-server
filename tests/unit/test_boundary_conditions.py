"""Unit tests for boundary conditions across the system."""

import pytest
from src.core.validation import (
    validate_store_request,
    validate_query_request,
    validate_filter_params,
)
from src.core.exceptions import ValidationError
from src.core.models import MemoryCategory, MemoryScope


class TestNumericBoundaries:
    """Test numeric boundary conditions."""

    @pytest.mark.parametrize("importance,should_pass", [
        (-0.1, False),  # Below minimum
        (0.0, True),    # Minimum valid
        (0.5, True),    # Middle
        (1.0, True),    # Maximum valid
        (1.1, False),   # Above maximum
        (None, True),   # None should use default
    ])
    def test_importance_boundaries(self, importance, should_pass):
        """Test importance value boundaries (0.0-1.0)."""
        payload = {
            "content": "Test memory",
            "category": "preference",
            "scope": "global",
        }

        if importance is not None:
            payload["importance"] = importance

        if should_pass:
            result = validate_store_request(payload)
            if importance is None:
                assert result.importance == 0.5  # Default value
            else:
                assert result.importance == importance
        else:
            with pytest.raises(ValidationError) as exc:
                validate_store_request(payload)
            assert "importance" in str(exc.value).lower() or "greater" in str(exc.value).lower()

    @pytest.mark.parametrize("limit,should_pass", [
        (-1, False),   # Negative
        (0, False),    # Zero (minimum is 1)
        (1, True),     # Minimum valid
        (50, True),    # Middle
        (100, True),   # Maximum valid
        (101, False),  # Above maximum
    ])
    def test_limit_boundaries(self, limit, should_pass):
        """Test limit parameter boundaries (1-100)."""
        payload = {
            "query": "test query",
            "limit": limit,
        }

        if should_pass:
            result = validate_query_request(payload)
            assert result.limit == limit
        else:
            with pytest.raises(ValidationError) as exc:
                validate_query_request(payload)
            # Pydantic will raise validation error for out of range
            assert "validation" in str(exc.value).lower() or "limit" in str(exc.value).lower()

    def test_offset_boundaries_note(self):
        """Note: offset is not part of QueryRequest model.

        The offset parameter is validated at the server method level,
        not in the Pydantic model. See test_pagination_edge_cases.py
        for offset validation tests that test the server methods directly.

        This test documents that QueryRequest doesn't have an offset field.
        """
        payload = {
            "query": "test query",
            "limit": 10,
        }

        result = validate_query_request(payload)
        # QueryRequest doesn't have offset field - it's in server methods
        assert not hasattr(result, 'offset')


class TestStringBoundaries:
    """Test string boundary conditions."""

    @pytest.mark.parametrize("content,should_pass,reason", [
        ("", False, "empty string"),
        (" ", False, "whitespace only"),
        ("a", True, "single character"),
        ("a" * 50000, True, "exactly at max length"),
        ("a" * 50001, False, "exceeds max length"),
    ])
    def test_content_boundaries(self, content, should_pass, reason):
        """Test content string boundaries."""
        payload = {
            "content": content,
            "category": "preference",
            "scope": "global",
        }

        if should_pass:
            result = validate_store_request(payload)
            assert result.content == content.strip()
        else:
            with pytest.raises(ValidationError) as exc:
                validate_store_request(payload)
            # Check for relevant error message
            error_msg = str(exc.value).lower()
            assert any(keyword in error_msg for keyword in ["empty", "length", "maximum", "validation"])

    def test_content_exactly_50kb_bytes(self):
        """Test content at exactly 50KB (51200 bytes) - should fail character limit."""
        # Create content that's exactly 51200 bytes (51200 characters in ASCII)
        content = "a" * 51200

        payload = {
            "content": content,
            "category": "preference",
            "scope": "global",
        }

        # This exceeds the character limit (50000), so should fail
        with pytest.raises(ValidationError) as exc:
            validate_store_request(payload)
        error_msg = str(exc.value).lower()
        # Check that the error mentions the issue
        assert "string" in error_msg or "character" in error_msg or "50000" in error_msg

    def test_content_50kb_plus_one_byte(self):
        """Test content at 50KB + 1 byte - should reject."""
        # Using multi-byte UTF-8 character (emoji = 4 bytes)
        # 12800 emojis = 51200 bytes, +1 emoji = 51204 bytes
        content = "😀" * 12801

        payload = {
            "content": content,
            "category": "preference",
            "scope": "global",
        }

        with pytest.raises(ValidationError) as exc:
            validate_store_request(payload)
        assert "length" in str(exc.value).lower() or "maximum" in str(exc.value).lower()

    @pytest.mark.parametrize("query,should_pass,reason", [
        ("", False, "empty string"),
        (" ", False, "whitespace only"),
        ("a", True, "single character"),
        ("a" * 1000, True, "exactly at max length"),
        ("a" * 1001, False, "exceeds max length"),
        ("a" * 10000, False, "very long query"),
    ])
    def test_query_boundaries(self, query, should_pass, reason):
        """Test query string boundaries (max 1000 chars)."""
        payload = {"query": query}

        if should_pass:
            result = validate_query_request(payload)
            assert result.query == query.strip()
        else:
            with pytest.raises(ValidationError) as exc:
                validate_query_request(payload)
            error_msg = str(exc.value).lower()
            assert any(keyword in error_msg for keyword in ["empty", "length", "maximum", "validation"])


class TestCollectionBoundaries:
    """Test collection boundary conditions."""

    @pytest.mark.parametrize("tags,should_pass,reason", [
        ([], True, "empty list"),
        ([""], True, "list with empty string (filtered out)"),
        (["tag"], True, "single tag"),
        (["tag" + str(i) for i in range(20)], True, "exactly 20 tags (max)"),
        (["tag" + str(i) for i in range(21)], False, "21 tags (exceeds max)"),
        (["tag" + str(i) for i in range(1000)], False, "1000 tags"),
    ])
    def test_tags_boundaries(self, tags, should_pass, reason):
        """Test tags list boundaries (max 20)."""
        payload = {
            "content": "Test memory",
            "category": "preference",
            "scope": "global",
            "tags": tags,
        }

        if should_pass:
            result = validate_store_request(payload)
            # Empty strings are filtered out
            expected_tags = [tag.strip().lower() for tag in tags if tag.strip()]
            assert result.tags == expected_tags
        else:
            with pytest.raises(ValidationError) as exc:
                validate_store_request(payload)
            assert "tag" in str(exc.value).lower() or "maximum" in str(exc.value).lower()

    @pytest.mark.parametrize("metadata,should_pass,reason", [
        ({}, True, "empty dict"),
        (None, True, "None (becomes empty dict)"),
        ({"key": "value"}, True, "single key-value"),
        ({"nested": {"level1": {"level2": "value"}}}, True, "nested dict (3 levels)"),
        # Create 10-level nested dict
        ({"l1": {"l2": {"l3": {"l4": {"l5": {"l6": {"l7": {"l8": {"l9": {"l10": "deep"}}}}}}}}}}, True, "deeply nested (10 levels)"),
    ])
    def test_metadata_boundaries(self, metadata, should_pass, reason):
        """Test metadata structure boundaries."""
        payload = {
            "content": "Test memory",
            "category": "preference",
            "scope": "global",
        }

        if metadata is not None:
            payload["metadata"] = metadata

        if should_pass:
            result = validate_store_request(payload)
            if metadata is None:
                assert result.metadata == {}
            else:
                # Metadata is sanitized (complex types converted to strings)
                assert result.metadata is not None
        else:
            with pytest.raises(ValidationError):
                validate_store_request(payload)

    def test_metadata_with_very_large_values(self):
        """Test metadata with extremely large values."""
        # Create metadata with 1000+ character value
        large_value = "v" * 2000

        payload = {
            "content": "Test memory",
            "category": "preference",
            "scope": "global",
            "metadata": {"large_key": large_value},
        }

        # Should pass but value will be truncated to 1000 chars
        result = validate_store_request(payload)
        assert len(result.metadata["large_key"]) <= 1000


class TestEdgeCaseInputs:
    """Test edge case inputs that might cause issues."""

    def test_content_with_null_bytes(self):
        """Test content with null bytes (should be sanitized)."""
        payload = {
            "content": "test\x00content",
            "category": "preference",
            "scope": "global",
        }

        result = validate_store_request(payload)
        assert "\x00" not in result.content

    def test_content_with_control_characters(self):
        """Test content with control characters (should be sanitized)."""
        payload = {
            "content": "test\x01\x02content",
            "category": "preference",
            "scope": "global",
        }

        result = validate_store_request(payload)
        # Control chars should be removed but newlines/tabs preserved
        assert "\x01" not in result.content
        assert "\x02" not in result.content

    def test_content_with_unicode_edge_cases(self):
        """Test content with various Unicode edge cases."""
        # Test with various Unicode characters
        content = "Test with emoji 😀, Chinese 中文, Arabic العربية, and symbols ∑∫∂"

        payload = {
            "content": content,
            "category": "preference",
            "scope": "global",
        }

        result = validate_store_request(payload)
        assert "😀" in result.content
        assert "中文" in result.content

    def test_query_with_special_characters(self):
        """Test query with special characters."""
        special_chars = "!@#$%^&*()_+-=[]{}|;:',.<>?/~`"

        payload = {"query": f"search {special_chars}"}

        result = validate_query_request(payload)
        # Special characters should be preserved (not SQL injection patterns)
        assert result.query is not None

    def test_tags_with_mixed_case(self):
        """Test that tags are normalized to lowercase."""
        payload = {
            "content": "Test memory",
            "category": "preference",
            "scope": "global",
            "tags": ["TAG1", "Tag2", "tag3"],
        }

        result = validate_store_request(payload)
        assert result.tags == ["tag1", "tag2", "tag3"]

    def test_tags_with_whitespace(self):
        """Test that tag whitespace is handled correctly."""
        payload = {
            "content": "Test memory",
            "category": "preference",
            "scope": "global",
            "tags": ["  tag1  ", "tag2", "  ", "tag3"],
        }

        result = validate_store_request(payload)
        # Empty tags (whitespace only) should be filtered out
        assert result.tags == ["tag1", "tag2", "tag3"]


class TestProjectNameBoundaries:
    """Test project name boundary conditions."""

    @pytest.mark.parametrize("project_name,should_pass", [
        ("", True),              # Empty (returns None)
        (None, True),            # None
        ("a", True),             # Single character
        ("project-name", True),  # Valid with hyphen
        ("project_name", True),  # Valid with underscore
        ("project.v1", True),    # Valid with dot
        ("project123", True),    # Valid with numbers
        ("a" * 100, True),       # Long name
    ])
    def test_project_name_valid_cases(self, project_name, should_pass):
        """Test valid project name cases."""
        filters = {}
        if project_name is not None and project_name != "":
            filters["project_name"] = project_name

        if should_pass:
            result = validate_filter_params(filters)
            if not project_name:
                assert result.project_name is None
            else:
                assert result.project_name == project_name


class TestMinImportanceBoundaries:
    """Test min_importance parameter boundaries."""

    @pytest.mark.parametrize("min_importance,should_pass", [
        (-0.1, False),  # Below minimum
        (0.0, True),    # Minimum valid
        (0.5, True),    # Middle
        (1.0, True),    # Maximum valid
        (1.1, False),   # Above maximum
        (None, True),   # None should use default (0.0)
    ])
    def test_min_importance_boundaries(self, min_importance, should_pass):
        """Test min_importance boundaries in query requests."""
        payload = {"query": "test query"}

        if min_importance is not None:
            payload["min_importance"] = min_importance

        if should_pass:
            result = validate_query_request(payload)
            if min_importance is None:
                assert result.min_importance == 0.0  # Default
            else:
                assert result.min_importance == min_importance
        else:
            with pytest.raises(ValidationError) as exc:
                validate_query_request(payload)
            error_msg = str(exc.value).lower()
            assert "importance" in error_msg or "greater" in error_msg or "validation" in error_msg
