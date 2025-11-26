"""Unit tests for pagination edge cases.

Note: The offset parameter is validated at the server method level,
not in the Pydantic QueryRequest model. These tests focus on limit
validation in the model and document expected offset behavior.
"""

import pytest
from src.core.validation import validate_query_request
from src.core.exceptions import ValidationError


class TestPaginationEdgeCases:
    """Test pagination edge cases and boundary conditions."""

    def test_offset_note(self):
        """Document that offset is handled at server level, not in QueryRequest model.

        The offset parameter is passed directly to server methods like
        list_memories(), list_indexed_files(), etc. and validated there.
        It's not part of the QueryRequest Pydantic model.
        """
        # QueryRequest doesn't have offset field
        payload = {
            "query": "test",
            "limit": 10,
        }

        result = validate_query_request(payload)
        assert not hasattr(result, 'offset')
        assert result.limit == 10

    def test_limit_equals_zero(self):
        """Test limit = 0 (invalid - minimum is 1)."""
        payload = {
            "query": "test",
            "limit": 0,
        }

        with pytest.raises(ValidationError) as exc:
            validate_query_request(payload)
        error_msg = str(exc.value).lower()
        assert "limit" in error_msg or "greater" in error_msg or "validation" in error_msg

    def test_limit_equals_one(self):
        """Test limit = 1 (minimum valid)."""
        payload = {
            "query": "test",
            "limit": 1,
        }

        result = validate_query_request(payload)
        assert result.limit == 1

    def test_limit_equals_maximum(self):
        """Test limit = 100 (maximum allowed)."""
        payload = {
            "query": "test",
            "limit": 100,
        }

        result = validate_query_request(payload)
        assert result.limit == 100

    def test_limit_exceeds_maximum(self):
        """Test limit > 100 (exceeds maximum)."""
        payload = {
            "query": "test",
            "limit": 101,
        }

        with pytest.raises(ValidationError) as exc:
            validate_query_request(payload)
        error_msg = str(exc.value).lower()
        assert "limit" in error_msg or "less" in error_msg or "validation" in error_msg

    def test_limit_default_when_not_provided(self):
        """Test that limit defaults to 5 when not provided."""
        payload = {
            "query": "test",
        }

        result = validate_query_request(payload)
        assert result.limit == 5  # Default value

    def test_offset_validation_at_server_level(self):
        """Document that offset validation happens at server method level.

        Server methods like list_memories() validate that offset >= 0.
        This is not validated in the Pydantic model.
        """
        # QueryRequest model doesn't have offset, so we just verify
        # that the model itself doesn't reject valid queries
        payload = {
            "query": "test",
            "limit": 10,
        }

        result = validate_query_request(payload)
        assert result.query == "test"
        assert result.limit == 10

    def test_negative_limit(self):
        """Test negative limit (should be rejected)."""
        payload = {
            "query": "test",
            "limit": -1,
        }

        with pytest.raises(ValidationError) as exc:
            validate_query_request(payload)
        error_msg = str(exc.value).lower()
        assert "limit" in error_msg or "greater" in error_msg or "validation" in error_msg

    @pytest.mark.parametrize("limit", [
        1,      # Minimum
        50,     # Middle
        100,    # Maximum
    ])
    def test_valid_limit_values(self, limit):
        """Test various valid limit values."""
        payload = {
            "query": "test",
            "limit": limit,
        }

        result = validate_query_request(payload)
        assert result.limit == limit

    @pytest.mark.parametrize("limit,error_keyword", [
        (-1, "limit"),       # Invalid limit
        (0, "limit"),        # Invalid limit
        (101, "limit"),      # Limit too large
    ])
    def test_invalid_limit_values(self, limit, error_keyword):
        """Test various invalid limit values."""
        payload = {
            "query": "test",
            "limit": limit,
        }

        with pytest.raises(ValidationError) as exc:
            validate_query_request(payload)
        error_msg = str(exc.value).lower()
        # Should mention the problematic field
        assert error_keyword in error_msg or "validation" in error_msg or "greater" in error_msg

    def test_pagination_with_empty_query(self):
        """Test limit parameter with empty query (should fail on query, not limit)."""
        payload = {
            "query": "",
            "limit": 10,
        }

        # Should fail because of empty query, not limit
        with pytest.raises(ValidationError) as exc:
            validate_query_request(payload)
        error_msg = str(exc.value).lower()
        assert "query" in error_msg or "empty" in error_msg or "validation" in error_msg

    def test_limit_preserves_other_parameters(self):
        """Test that limit doesn't interfere with other query parameters."""
        payload = {
            "query": "test query",
            "limit": 20,
            "min_importance": 0.5,
        }

        result = validate_query_request(payload)
        assert result.limit == 20
        assert result.min_importance == 0.5
        assert result.query == "test query"
