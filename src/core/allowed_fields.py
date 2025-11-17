"""Allowlist configuration for memory fields and filters."""

from typing import Dict, Any, List, Set
from src.core.models import MemoryCategory, MemoryScope, ContextLevel


# ============================================================================
# Field Allowlists
# ============================================================================

# Fields allowed in MemoryUnit
ALLOWED_MEMORY_FIELDS: Dict[str, Dict[str, Any]] = {
    "id": {
        "type": str,
        "required": False,
        "description": "Unique identifier (auto-generated)",
        "max_length": 100,
    },
    "content": {
        "type": str,
        "required": True,
        "description": "Memory content",
        "min_length": 1,
        "max_length": 50000,
        "max_bytes": 51200,  # 50KB
    },
    "category": {
        "type": str,
        "required": True,
        "description": "Memory category",
        "allowed_values": [c.value for c in MemoryCategory],
    },
    "context_level": {
        "type": str,
        "required": False,
        "description": "Context stratification level",
        "allowed_values": [c.value for c in ContextLevel],
        "default": ContextLevel.PROJECT_CONTEXT.value,
    },
    "scope": {
        "type": str,
        "required": False,
        "description": "Memory scope (global or project)",
        "allowed_values": [s.value for s in MemoryScope],
        "default": MemoryScope.GLOBAL.value,
    },
    "project_name": {
        "type": str,
        "required": False,
        "description": "Project name (required if scope=project)",
        "max_length": 100,
        "pattern": r"^[a-zA-Z0-9_\-\.]+$",
    },
    "importance": {
        "type": float,
        "required": False,
        "description": "Importance score",
        "min_value": 0.0,
        "max_value": 1.0,
        "default": 0.5,
    },
    "tags": {
        "type": list,
        "required": False,
        "description": "Tags for categorization",
        "max_items": 20,
        "item_type": str,
        "item_max_length": 50,
        "default": [],
    },
    "metadata": {
        "type": dict,
        "required": False,
        "description": "Additional metadata",
        "max_items": 50,
        "key_max_length": 100,
        "value_max_length": 1000,
        "default": {},
    },
    "embedding_model": {
        "type": str,
        "required": False,
        "description": "Embedding model used",
        "allowed_values": ["all-MiniLM-L6-v2"],  # Can add more models later
        "default": "all-MiniLM-L6-v2",
    },
    "created_at": {
        "type": "datetime",
        "required": False,
        "description": "Creation timestamp (auto-generated)",
    },
    "updated_at": {
        "type": "datetime",
        "required": False,
        "description": "Update timestamp (auto-generated)",
    },
}

# Fields allowed for filtering/searching
ALLOWED_FILTER_FIELDS: Set[str] = {
    "category",
    "context_level",
    "scope",
    "project_name",
    "importance",
    "tags",
    "embedding_model",
}

# Fields allowed for sorting
ALLOWED_SORT_FIELDS: Set[str] = {
    "created_at",
    "updated_at",
    "importance",
}

# Alias for ALLOWED_SORT_FIELDS (for backward compatibility and tests)
ALLOWED_SORTABLE_FIELDS: Set[str] = ALLOWED_SORT_FIELDS

# Metadata fields that are allowed for code search
ALLOWED_CODE_METADATA_FIELDS: Set[str] = {
    "file_path",
    "unit_type",
    "unit_name",
    "start_line",
    "end_line",
    "signature",
    "language",
    "project_name",
}

# Common SQL injection and malicious patterns for security validation
INJECTION_PATTERNS = [
    # SQL keywords
    r"(?i)(\bSELECT\b|\bUNION\b|\bDROP\b|\bDELETE\b|\bINSERT\b|\bUPDATE\b)",
    r"(?i)(\bFROM\b|\bWHERE\b|\bJOIN\b|\bGROUP\s+BY\b|\bORDER\s+BY\b)",
    r"(?i)(\bEXEC\b|\bEXECUTE\b|\bSCRIPT\b|\bJAVASCRIPT\b)",
    
    # SQL operators and functions
    r"(?i)(\bOR\b\s+\d+=\d+|\bAND\b\s+\d+=\d+)",
    r"(?i)(--|\#|\/\*|\*\/|;|\|{2})",
    
    # Common injection attempts
    r"('|\")\s*;\s*DROP",
    r"('|\")\s*OR\s*('|\")\s*=\s*('|\")",
    r"admin.*?'.*?--",
    r"\bor\b.*?\d+=\d+",
    
    # Command injection patterns
    r"[;&|`$(){}[\]<>]",  # Shell metacharacters
    r"\$\{.*?\}",  # Template injection
    r"\$\(.*?\)",  # Command substitution
    
    # Path traversal
    r"\.\./",
    r"\.\.\\",
    r"%2e%2e",
    
    # XSS patterns
    r"<script[^>]*>",
    r"javascript:",
    r"on\w+\s*=",
]


# ============================================================================
# Validation Functions
# ============================================================================


def is_allowed_field(field_name: str) -> bool:
    """
    Check if a field is allowed in MemoryUnit.

    Args:
        field_name: Field name to check

    Returns:
        True if allowed, False otherwise
    """
    return field_name in ALLOWED_MEMORY_FIELDS


def is_filterable_field(field_name: str) -> bool:
    """
    Check if a field can be used for filtering.

    Args:
        field_name: Field name to check

    Returns:
        True if filterable, False otherwise
    """
    return field_name in ALLOWED_FILTER_FIELDS


def is_sortable_field(field_name: str) -> bool:
    """
    Check if a field can be used for sorting.

    Args:
        field_name: Field name to check

    Returns:
        True if sortable, False otherwise
    """
    return field_name in ALLOWED_SORT_FIELDS


def get_field_constraints(field_name: str) -> Dict[str, Any]:
    """
    Get constraints for a field.

    Args:
        field_name: Field name

    Returns:
        Dictionary of constraints
    """
    return ALLOWED_MEMORY_FIELDS.get(field_name, {})


def validate_field_value(field_name: str, value: Any) -> tuple[bool, str]:
    """
    Validate a field value against constraints.

    Args:
        field_name: Field name
        value: Value to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not is_allowed_field(field_name):
        return False, f"Field '{field_name}' is not allowed"

    constraints = get_field_constraints(field_name)

    # Check type
    expected_type = constraints.get("type")
    if expected_type and not isinstance(value, expected_type):
        if expected_type == str and not isinstance(value, str):
            return False, f"Field '{field_name}' must be a string"
        elif expected_type == float and not isinstance(value, (int, float)):
            return False, f"Field '{field_name}' must be a number"
        elif expected_type == list and not isinstance(value, list):
            return False, f"Field '{field_name}' must be a list"
        elif expected_type == dict and not isinstance(value, dict):
            return False, f"Field '{field_name}' must be a dictionary"

    # Check allowed values
    if "allowed_values" in constraints:
        if value not in constraints["allowed_values"]:
            return (
                False,
                f"Field '{field_name}' must be one of: {constraints['allowed_values']}",
            )

    # Check string length
    if isinstance(value, str):
        if "min_length" in constraints and len(value) < constraints["min_length"]:
            return (
                False,
                f"Field '{field_name}' must be at least {constraints['min_length']} characters",
            )
        if "max_length" in constraints and len(value) > constraints["max_length"]:
            return (
                False,
                f"Field '{field_name}' exceeds maximum length of {constraints['max_length']}",
            )

    # Check numeric range
    if isinstance(value, (int, float)):
        if "min_value" in constraints and value < constraints["min_value"]:
            return (
                False,
                f"Field '{field_name}' must be >= {constraints['min_value']}",
            )
        if "max_value" in constraints and value > constraints["max_value"]:
            return (
                False,
                f"Field '{field_name}' must be <= {constraints['max_value']}",
            )

    # Check list constraints
    if isinstance(value, list):
        if "max_items" in constraints and len(value) > constraints["max_items"]:
            return (
                False,
                f"Field '{field_name}' exceeds maximum of {constraints['max_items']} items",
            )

    # Check dict constraints
    if isinstance(value, dict):
        if "max_items" in constraints and len(value) > constraints["max_items"]:
            return (
                False,
                f"Field '{field_name}' exceeds maximum of {constraints['max_items']} items",
            )

    return True, ""


def get_allowed_categories() -> List[str]:
    """Get list of allowed memory categories."""
    return [c.value for c in MemoryCategory]


def get_allowed_context_levels() -> List[str]:
    """Get list of allowed context levels."""
    return [c.value for c in ContextLevel]


def get_allowed_scopes() -> List[str]:
    """Get list of allowed memory scopes."""
    return [s.value for s in MemoryScope]


def validate_against_allowlist(data: Dict[str, Any]) -> Dict[str, List[str]]:
    """
    Validate a data dictionary against field allowlists.

    Args:
        data: Dictionary to validate

    Returns:
        Dictionary mapping field names to error messages (empty if valid)
    """
    errors = {}

    for field_name, value in data.items():
        is_valid, error_msg = validate_field_value(field_name, value)
        if not is_valid:
            if field_name not in errors:
                errors[field_name] = []
            errors[field_name].append(error_msg)

    return errors
