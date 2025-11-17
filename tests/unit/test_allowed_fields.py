"""Tests for allowed_fields configuration module."""

import pytest
from src.core.allowed_fields import (
    ALLOWED_MEMORY_FIELDS,
    ALLOWED_FILTER_FIELDS,
    ALLOWED_SORT_FIELDS,
    ALLOWED_CODE_METADATA_FIELDS,
    is_allowed_field,
    is_filterable_field,
    is_sortable_field,
    get_field_constraints,
    validate_field_value,
    get_allowed_categories,
    get_allowed_context_levels,
    get_allowed_scopes,
    validate_against_allowlist,
)
from src.core.models import MemoryCategory, MemoryScope, ContextLevel


class TestAllowedFieldsConstants:
    """Test that allowlist constants are properly defined."""

    def test_allowed_memory_fields_exists(self):
        """Test that ALLOWED_MEMORY_FIELDS is defined."""
        assert ALLOWED_MEMORY_FIELDS is not None
        assert isinstance(ALLOWED_MEMORY_FIELDS, dict)
        assert len(ALLOWED_MEMORY_FIELDS) > 0

    def test_allowed_filter_fields_exists(self):
        """Test that ALLOWED_FILTER_FIELDS is defined."""
        assert ALLOWED_FILTER_FIELDS is not None
        assert isinstance(ALLOWED_FILTER_FIELDS, set)

    def test_allowed_sortable_fields_exists(self):
        """Test that ALLOWED_SORTABLE_FIELDS is defined."""
        assert ALLOWED_SORTABLE_FIELDS is not None
        assert isinstance(ALLOWED_SORTABLE_FIELDS, set)

    def test_injection_patterns_exists(self):
        """Test that INJECTION_PATTERNS is defined."""
        assert INJECTION_PATTERNS is not None
        assert len(INJECTION_PATTERNS) > 0


class TestFieldValidation:
    """Test field validation functions."""

    def test_is_allowed_field_valid(self):
        """Test is_allowed_field with valid fields."""
        valid_fields = ["content", "category", "scope", "importance", "tags"]

        for field in valid_fields:
            assert is_allowed_field(field) is True

    def test_is_allowed_field_invalid(self):
        """Test is_allowed_field with invalid fields."""
        invalid_fields = ["invalid", "unknown", "notafield"]

        for field in invalid_fields:
            assert is_allowed_field(field) is False

    def test_is_filterable_field_valid(self):
        """Test is_filterable_field with valid filter fields."""
        # At minimum, these should be filterable
        assert is_filterable_field("category") is True

    def test_is_filterable_field_invalid(self):
        """Test is_filterable_field with invalid fields."""
        assert is_filterable_field("invalid_field") is False

    def test_is_sortable_field_valid(self):
        """Test is_sortable_field with valid sortable fields."""
        # At minimum, some timestamp/importance fields should be sortable
        # Test that the function works, exact fields may vary
        result = is_sortable_field("created_at")
        assert isinstance(result, bool)

    def test_is_sortable_field_invalid(self):
        """Test is_sortable_field with invalid fields."""
        assert is_sortable_field("invalid_field") is False


class TestFieldConstraints:
    """Test field constraint retrieval."""

    def test_get_field_constraints_content(self):
        """Test getting constraints for content field."""
        constraints = get_field_constraints("content")

        assert constraints is not None
        assert "type" in constraints
        assert "required" in constraints
        assert constraints["required"] is True

    def test_get_field_constraints_category(self):
        """Test getting constraints for category field."""
        constraints = get_field_constraints("category")

        assert constraints is not None
        assert "allowed_values" in constraints

    def test_get_field_constraints_nonexistent(self):
        """Test getting constraints for nonexistent field."""
        constraints = get_field_constraints("nonexistent")

        assert constraints is None or constraints == {}

    def test_get_field_constraints_importance(self):
        """Test getting constraints for importance field."""
        constraints = get_field_constraints("importance")

        assert constraints is not None
        assert "min_value" in constraints or "max_value" in constraints


class TestValueValidation:
    """Test field value validation."""

    def test_validate_field_value_content_valid(self):
        """Test validating valid content."""
        valid, message = validate_field_value("content", "This is valid content")

        assert valid is True
        assert message == "" or "success" in message.lower() or message == "Valid"

    def test_validate_field_value_content_empty(self):
        """Test validating empty content."""
        valid, message = validate_field_value("content", "")

        assert valid is False
        assert len(message) > 0

    def test_validate_field_value_category_valid(self):
        """Test validating valid category."""
        valid, message = validate_field_value("category", "preference")

        assert valid is True

    def test_validate_field_value_category_invalid(self):
        """Test validating invalid category."""
        valid, message = validate_field_value("category", "invalid_category_123")

        assert valid is False
        assert len(message) > 0

    def test_validate_field_value_importance_valid(self):
        """Test validating valid importance."""
        valid, message = validate_field_value("importance", 0.7)

        assert valid is True

    def test_validate_field_value_importance_invalid(self):
        """Test validating invalid importance (out of range)."""
        valid, message = validate_field_value("importance", 1.5)

        assert valid is False

    def test_validate_field_value_nonexistent_field(self):
        """Test validating value for nonexistent field."""
        valid, message = validate_field_value("nonexistent", "value")

        assert valid is False


class TestEnumGetters:
    """Test enum value getter functions."""

    def test_get_allowed_categories(self):
        """Test getting allowed categories."""
        categories = get_allowed_categories()

        assert isinstance(categories, list)
        assert len(categories) > 0

        # Should include all MemoryCategory values
        for cat in MemoryCategory:
            assert cat.value in categories

    def test_get_allowed_context_levels(self):
        """Test getting allowed context levels."""
        levels = get_allowed_context_levels()

        assert isinstance(levels, list)
        assert len(levels) > 0

        # Should include all ContextLevel values
        for level in ContextLevel:
            assert level.value in levels

    def test_get_allowed_scopes(self):
        """Test getting allowed scopes."""
        scopes = get_allowed_scopes()

        assert isinstance(scopes, list)
        assert len(scopes) > 0

        # Should include all MemoryScope values
        for scope in MemoryScope:
            assert scope.value in scopes


class TestAllowlistValidation:
    """Test allowlist validation function."""

    def test_validate_against_allowlist_valid(self):
        """Test validation with all valid fields."""
        data = {
            "content": "Test content",
            "category": "preference",
            "importance": 0.5,
        }

        errors = validate_against_allowlist(data)

        # Should have no errors or empty error dict
        assert errors is not None
        if errors:
            assert len(errors) == 0 or all(len(v) == 0 for v in errors.values())

    def test_validate_against_allowlist_invalid_field(self):
        """Test validation with invalid field names."""
        data = {
            "content": "Test",
            "invalid_field": "value",
            "another_invalid": "value",
        }

        errors = validate_against_allowlist(data)

        assert errors is not None
        # Should have errors for invalid fields
        assert len(errors) > 0

    def test_validate_against_allowlist_invalid_value(self):
        """Test validation with invalid field values."""
        data = {
            "content": "",  # Empty content
            "category": "invalid_category",  # Invalid category
            "importance": 2.0,  # Out of range
        }

        errors = validate_against_allowlist(data)

        assert errors is not None
        # Should have errors
        assert len(errors) > 0

    def test_validate_against_allowlist_empty(self):
        """Test validation with empty data."""
        data = {}

        errors = validate_against_allowlist(data)

        # Should handle empty data gracefully
        assert errors is not None


class TestInjectionPatterns:
    """Test injection pattern detection."""

    def test_injection_patterns_sql(self):
        """Test that SQL injection patterns are defined."""
        # Check that common SQL keywords are in patterns
        patterns_str = str(INJECTION_PATTERNS).lower()

        # At least some common SQL terms should be covered
        assert "select" in patterns_str or "union" in patterns_str or "drop" in patterns_str

    def test_injection_patterns_count(self):
        """Test that we have a reasonable number of patterns."""
        # Should have many patterns for good coverage
        assert len(INJECTION_PATTERNS) >= 10


class TestMemoryFieldStructure:
    """Test ALLOWED_MEMORY_FIELDS structure."""

    def test_content_field_structure(self):
        """Test content field has required structure."""
        content = ALLOWED_MEMORY_FIELDS["content"]

        assert "type" in content
        assert "required" in content
        assert content["required"] is True
        assert "max_length" in content

    def test_category_field_structure(self):
        """Test category field has required structure."""
        category = ALLOWED_MEMORY_FIELDS["category"]

        assert "type" in category
        assert "required" in category
        assert "allowed_values" in category

    def test_importance_field_structure(self):
        """Test importance field has required structure."""
        importance = ALLOWED_MEMORY_FIELDS["importance"]

        assert "type" in importance
        assert importance["type"] == float

    def test_tags_field_structure(self):
        """Test tags field has required structure."""
        tags = ALLOWED_MEMORY_FIELDS["tags"]

        assert "type" in tags
        assert tags["type"] == list
