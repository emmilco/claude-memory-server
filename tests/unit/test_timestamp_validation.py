"""Unit tests for Unix timestamp validation in Qdrant store.

Tests for BUG-064: Integer Overflow in Unix Timestamp Conversion
"""

import pytest
from datetime import datetime, UTC

from src.store.qdrant_store import _validate_timestamp, MIN_UNIX_TIMESTAMP, MAX_UNIX_TIMESTAMP
from src.core.exceptions import ValidationError


class TestTimestampValidation:
    """Test timestamp validation for Qdrant compatibility."""

    def test_validate_timestamp_within_range(self):
        """Valid timestamps within range should not raise errors."""
        # Test various valid timestamps
        _validate_timestamp(0)  # Epoch
        _validate_timestamp(1234567890)  # 2009-02-13
        _validate_timestamp(MIN_UNIX_TIMESTAMP)  # Minimum allowed
        _validate_timestamp(MAX_UNIX_TIMESTAMP)  # Maximum allowed
        _validate_timestamp(-1000000)  # Negative timestamp (before 1970)

    def test_validate_timestamp_too_far_past(self):
        """Timestamps before 1901 should raise ValidationError."""
        # Just below minimum
        with pytest.raises(ValidationError) as exc_info:
            _validate_timestamp(MIN_UNIX_TIMESTAMP - 1)

        assert "too far in past" in str(exc_info.value)
        assert "1901" in str(exc_info.value)

    def test_validate_timestamp_too_far_future(self):
        """Timestamps after 2038 should raise ValidationError."""
        # Just above maximum
        with pytest.raises(ValidationError) as exc_info:
            _validate_timestamp(MAX_UNIX_TIMESTAMP + 1)

        assert "too far in future" in str(exc_info.value)
        assert "2038" in str(exc_info.value)

    def test_validate_timestamp_custom_field_name(self):
        """Error message should include custom field name."""
        with pytest.raises(ValidationError) as exc_info:
            _validate_timestamp(MAX_UNIX_TIMESTAMP + 1, "author_date")

        assert "author_date" in str(exc_info.value)

    def test_validate_timestamp_edge_cases(self):
        """Test exact boundary values."""
        # Minimum boundary (should pass)
        _validate_timestamp(MIN_UNIX_TIMESTAMP)

        # Maximum boundary (should pass)
        _validate_timestamp(MAX_UNIX_TIMESTAMP)

        # Just below minimum (should fail)
        with pytest.raises(ValidationError):
            _validate_timestamp(MIN_UNIX_TIMESTAMP - 1)

        # Just above maximum (should fail)
        with pytest.raises(ValidationError):
            _validate_timestamp(MAX_UNIX_TIMESTAMP + 1)

    def test_validate_timestamp_extreme_values(self):
        """Test with extreme timestamp values."""
        # Very far in past
        with pytest.raises(ValidationError):
            _validate_timestamp(-9999999999)  # ~1653 BC

        # Very far in future
        with pytest.raises(ValidationError):
            _validate_timestamp(9999999999)  # Year 2286
