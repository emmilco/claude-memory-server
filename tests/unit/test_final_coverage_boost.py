"""Final tests to push coverage to 85%."""

import pytest
from pydantic import ValidationError

from src.core.models import MemoryUnit, MemoryCategory, MemoryScope, ContextLevel, QueryRequest
from src.core.exceptions import CollectionNotFoundError, MemoryNotFoundError


class TestModelsUncovered:
    """Test uncovered lines in models.py."""

    def test_content_exceeds_50kb(self):
        """Test content size limit validation (line 59)."""
        # Create content > 50KB
        large_content = "x" * 52000  # > 50KB

        with pytest.raises(ValidationError) as exc_info:
            MemoryUnit(
                content=large_content,
                category=MemoryCategory.FACT,
                scope=MemoryScope.GLOBAL,
            )

        # Pydantic's validation message
        assert "50000" in str(exc_info.value) or "too" in str(exc_info.value).lower()

    def test_query_request_empty_query(self):
        """Test QueryRequest with empty query (line 110)."""
        with pytest.raises(ValidationError) as exc_info:
            QueryRequest(
                query="   "  # Empty after strip
            )

        # Should trigger "cannot be empty" validation
        assert "cannot be empty" in str(exc_info.value).lower()


class TestExceptionsUncovered:
    """Test uncovered lines in exceptions.py."""

    def test_collection_not_found_error(self):
        """Test CollectionNotFoundError initialization (lines 81-82)."""
        error = CollectionNotFoundError("my_collection")

        assert error.collection_name == "my_collection"
        assert "my_collection" in str(error)
        assert "not found" in str(error).lower()

    def test_memory_not_found_error(self):
        """Test MemoryNotFoundError initialization (lines 89-90)."""
        error = MemoryNotFoundError("mem-123")

        assert error.memory_id == "mem-123"
        assert "mem-123" in str(error)
        assert "not found" in str(error).lower()


class TestValidationUncovered:
    """Test uncovered lines in validation.py."""

    def test_sanitize_metadata_else_branch(self):
        """Test sanitize_metadata with None value (line 252)."""
        from src.core.validation import sanitize_metadata

        metadata = {"key": None}  # None is not str, int, float, bool, list, or dict
        result = sanitize_metadata(metadata)

        assert "key" in result

    def test_validate_filter_params_value_error(self):
        """Test validate_filter_params ValueError handling (line 416)."""
        from src.core.validation import validate_filter_params
        from src.core.exceptions import ValidationError

        # Pass invalid min_importance that causes ValueError
        with pytest.raises(ValidationError) as exc_info:
            validate_filter_params({"min_importance": "invalid_value"})

        assert "filter validation failed" in str(exc_info.value).lower()

    def test_validate_memory_id_empty_after_sanitization(self):
        """Test validate_memory_id with ID that becomes empty (line 439)."""
        from src.core.validation import validate_memory_id
        from src.core.exceptions import ValidationError

        # Pass ID with only non-printable control characters
        with pytest.raises(ValidationError) as exc_info:
            validate_memory_id("\x01\x02\x03\x00")

        assert "cannot be empty after sanitization" in str(exc_info.value).lower()

    def test_validate_project_name_empty_after_sanitization(self):
        """Test validate_project_name returning None (line 473)."""
        from src.core.validation import validate_project_name

        # Pass project name with only non-printable control characters
        result = validate_project_name("\x01\x02\x03\x00")

        assert result is None
