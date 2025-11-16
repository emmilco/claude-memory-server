"""Comprehensive input validation and security checks for Claude Memory RAG Server."""

import re
import logging
from typing import Dict, Any, Optional, List
from src.core.models import (
    MemoryUnit,
    MemoryCategory,
    MemoryScope,
    ContextLevel,
    StoreMemoryRequest,
    QueryRequest,
    SearchFilters,
)
from src.core.exceptions import ValidationError

logger = logging.getLogger(__name__)


# ============================================================================
# SQL Injection Patterns
# ============================================================================

SQL_INJECTION_PATTERNS = [
    # Classic SQL injection - enhanced patterns
    r"'(\s)*(or|OR)(\s)*'",  # ' OR ' or ' or '
    r"'(\s)*(and|AND)(\s)*'",  # ' AND ' or ' and '
    r"'\s*=\s*'",  # '='
    r"('|(\\'))(\s)*(or|OR|Or)(\s)*('|(\\'))(\s)*=(\s)*('|(\\'))",  # ' or '1'='1
    r"('|(\\'))(\s)*(;|;)(\s)*(drop|DROP|Drop)",  # '; DROP
    r"'\s*(#|--|/\*)",  # SQL comments after quote
    # Union-based
    r"union(\s)+select",  # UNION SELECT
    r"union(\s)+all(\s)+select",  # UNION ALL SELECT
    # DML statements
    r"select(\s)+.*(\s)+from",  # SELECT ... FROM
    r"insert(\s)+into",  # INSERT INTO
    r"delete(\s)+from",  # DELETE FROM
    r"update(\s)+.*(\s)+set",  # UPDATE ... SET
    # DDL statements
    r"drop(\s)+(table|database|schema|if\s+exists)",  # DROP TABLE/DATABASE
    r"create(\s)+(table|database|schema)",  # CREATE TABLE/DATABASE
    r"alter(\s)+table",  # ALTER TABLE
    r"truncate(\s)+table",  # TRUNCATE
    # System commands
    r"exec(\s)*\(",  # EXEC(
    r"execute(\s)*\(",  # EXECUTE(
    r"sp_executesql",  # sp_executesql
    r"xp_cmdshell",  # xp_cmdshell
    r"xp_dirtree",  # xp_dirtree
    # Comments
    r"--(\s)*$",  # SQL comment at end
    r"/\*",  # SQL block comment start
    r"\*/",  # SQL block comment end
    # Functions
    r"char\(.*\)",  # CHAR() function
    r"concat\(.*\)",  # CONCAT() function
    r"0x[0-9a-f]{6,}",  # Hex literals (longer ones)
    r"benchmark\(.*\)",  # BENCHMARK() - timing attacks
    r"sleep\(\d+\)",  # SLEEP() - timing attacks
    r"waitfor(\s)+delay",  # WAITFOR DELAY
    r"pg_sleep\(\d+\)",  # PostgreSQL sleep
    # Schema exploration
    r"information_schema",  # information_schema access
    r"sys\.",  # System table access
    r"table_name",  # Common in schema enum
    r"column_name",  # Common in schema enum
    # Stacked queries
    r";(\s)*(select|insert|update|delete|drop|create|alter)",
    # Boolean-based blind injection
    r"(and|or)(\s)+\d+(\s)*=(\s)*\d+",  # and 1=1, or 1=1
    # Additional patterns
    r"\)\s*(or|OR)\s*\(",  # ) OR (
    r"where(\s)+(''|1)(\s)*=",  # WHERE tricks
]

# ============================================================================
# Prompt Injection Patterns
# ============================================================================

PROMPT_INJECTION_PATTERNS = [
    # System prompt manipulation
    r"ignore(\s)+(all(\s)+)?(previous|prior)(\s)+(instructions|commands)",
    r"disregard(\s)+(all(\s)+)?(previous|prior)(\s)+(commands|instructions)",
    r"forget(\s)+(everything|all|previous)",
    r"new(\s)+instructions(\s)*:",
    r"system(\s)*:(\s)*you(\s)+are",
    r"<\|system\|>",
    r"<\|assistant\|>",
    r"<\|user\|>",
    # Role manipulation
    r"you(\s)+are(\s)+now",
    r"act(\s)+as(\s)+(a|an)",
    r"pretend(\s)+to(\s)+be",
    r"roleplay(\s)+as",
    # Instruction override
    r"override(\s)+your(\s)+instructions",
    r"bypass(\s)+your(\s)+restrictions",
    r"ignore(\s)+your(\s)+rules",
    r"(reset|override|bypass|context)(\s)+(context|instructions|rules|override)",
    # Jailbreak attempts
    r"DAN(\s)+mode",
    r"developer(\s)+mode",
    r"jailbreak",
    r"do(\s)+anything(\s)+now",
    r"without(\s)+restrictions",
    r"no(\s)+restrictions",
    r"have(\s)+no(\s)+restrictions",
    # Payload injection
    r"\[SYSTEM\]",
    r"\[INST\]",
    r"###(\s)*Instruction",
    # Data exfiltration attempts
    r"repeat(\s)+(the|your)(\s)+system(\s)+prompt",
    r"what(\s)+are(\s)+your(\s)+instructions",
    r"show(\s)+me(\s)+your(\s)+(prompt|instructions|configuration|initial)",
    r"print(\s)+your(\s)+(prompt|config|instructions)",
    # Multi-turn attacks
    r"(in|for)(\s)+the(\s)+(next|following)",
    r"new(\s)+session(\s)*:",
    # Additional patterns
    r"disregard(\s)+all(\s)+prior",
    r"allow(\s)+all(\s)+actions",
]

# ============================================================================
# Command Injection Patterns
# ============================================================================

COMMAND_INJECTION_PATTERNS = [
    r";\s*(rm|cat|ls|pwd|whoami|id)",  # Common shell commands
    r"\$\(.*\)",  # $() command substitution
    r"`[^`]+`",  # `` command substitution
    r"&&\s*\w+",  # Command chaining with command
    r"\|\|\s*\w+",  # Command chaining OR
    r"\|\s*(nc|netcat|bash|sh|curl|wget)",  # Piping to dangerous commands
    r">\s*/",  # Output redirection to path
    r"2>&1",  # Error redirection
    r";\s*(wget|curl)\s+",  # wget/curl command
    r";\s*(nc|netcat)\s+",  # netcat
    r";\s*(bash|sh)\s*",  # bash/sh invocation
    r"/bin/(bash|sh|nc|cat|ls)",  # Binary paths to common commands
    r"/usr/bin/(python|perl|ruby)",  # Script interpreter paths
    r"eval\(.*\)",  # eval()
    r"exec\(.*\)",  # exec()
]

# ============================================================================
# Path Traversal Patterns
# ============================================================================

PATH_TRAVERSAL_PATTERNS = [
    r"\.\./",  # ../
    r"\.\.",  # ..
    r"%2e%2e",  # URL encoded ..
    r"\.\.\\",  # ..\
    r"/etc/passwd",  # Common target
    r"/etc/shadow",  # Common target
    r"c:\\windows",  # Windows paths
    r"file://",  # File protocol
]


# ============================================================================
# Validation Functions
# ============================================================================


def detect_injection_patterns(text: str) -> Optional[str]:
    """
    Detect injection attack patterns in text.

    Args:
        text: Text to check

    Returns:
        Pattern name if detected, None otherwise
    """
    text_lower = text.lower()

    # Check SQL injection
    for pattern in SQL_INJECTION_PATTERNS:
        if re.search(pattern, text_lower, re.IGNORECASE | re.MULTILINE):
            return f"SQL injection pattern: {pattern}"

    # Check prompt injection
    for pattern in PROMPT_INJECTION_PATTERNS:
        if re.search(pattern, text_lower, re.IGNORECASE | re.MULTILINE):
            return f"Prompt injection pattern: {pattern}"

    # Check command injection
    for pattern in COMMAND_INJECTION_PATTERNS:
        if re.search(pattern, text, re.MULTILINE):  # Case-sensitive for commands
            return f"Command injection pattern: {pattern}"

    # Check path traversal
    for pattern in PATH_TRAVERSAL_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE | re.MULTILINE):
            return f"Path traversal pattern: {pattern}"

    return None


def sanitize_text(text: str, max_length: Optional[int] = None) -> str:
    """
    Sanitize text by removing dangerous characters and patterns.

    Args:
        text: Text to sanitize
        max_length: Optional maximum length

    Returns:
        Sanitized text
    """
    # Remove null bytes
    text = text.replace("\x00", "")

    # Remove other control characters except newlines and tabs
    text = "".join(char for char in text if char.isprintable() or char in "\n\t")

    # Truncate if needed
    if max_length and len(text) > max_length:
        text = text[:max_length]

    return text.strip()


def sanitize_metadata(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """
    Sanitize metadata dictionary.

    Args:
        metadata: Metadata to sanitize

    Returns:
        Sanitized metadata
    """
    sanitized = {}
    for key, value in metadata.items():
        # Sanitize key
        clean_key = sanitize_text(str(key), max_length=100)

        # Sanitize value
        if isinstance(value, str):
            clean_value = sanitize_text(value, max_length=1000)
        elif isinstance(value, (int, float, bool)):
            clean_value = value
        elif isinstance(value, (list, dict)):
            # For complex types, convert to string and sanitize
            clean_value = sanitize_text(str(value), max_length=1000)
        else:
            clean_value = sanitize_text(str(value), max_length=1000)

        sanitized[clean_key] = clean_value

    return sanitized


def validate_content_size(content: str, max_bytes: int = 51200) -> None:
    """
    Validate content size.

    Args:
        content: Content to validate
        max_bytes: Maximum size in bytes (default 50KB)

    Raises:
        ValidationError: If content exceeds size limit
    """
    size = len(content.encode("utf-8"))
    if size > max_bytes:
        raise ValidationError(
            f"Content size ({size} bytes) exceeds maximum of {max_bytes} bytes"
        )


def validate_store_request(payload: Dict[str, Any]) -> MemoryUnit:
    """
    Validate and create a MemoryUnit from a store request payload.

    This function performs comprehensive validation including:
    - Injection pattern detection
    - Content size limits
    - Field validation
    - Metadata sanitization

    Args:
        payload: Request payload dictionary

    Returns:
        Validated MemoryUnit

    Raises:
        ValidationError: If validation fails
    """
    try:
        # First, create a StoreMemoryRequest to leverage Pydantic validation
        request = StoreMemoryRequest(**payload)

        # Additional injection detection
        injection_pattern = detect_injection_patterns(request.content)
        if injection_pattern:
            raise ValidationError(
                f"Potential security threat detected: {injection_pattern}"
            )

        # Sanitize content
        sanitized_content = sanitize_text(request.content)

        # Validate content size
        validate_content_size(sanitized_content)

        # Sanitize metadata
        sanitized_metadata = sanitize_metadata(request.metadata)

        # Create MemoryUnit
        memory_unit = MemoryUnit(
            content=sanitized_content,
            category=request.category,
            scope=request.scope,
            project_name=request.project_name,
            importance=request.importance,
            tags=request.tags,
            metadata=sanitized_metadata,
            context_level=request.context_level or ContextLevel.PROJECT_CONTEXT,
        )

        logger.debug(f"Validated store request: {len(sanitized_content)} chars")
        return memory_unit

    except ValueError as e:
        raise ValidationError(f"Validation failed: {str(e)}") from e


def validate_query_request(payload: Dict[str, Any]) -> QueryRequest:
    """
    Validate and create a QueryRequest from a query payload.

    Args:
        payload: Query payload dictionary

    Returns:
        Validated QueryRequest

    Raises:
        ValidationError: If validation fails
    """
    try:
        # Create QueryRequest (Pydantic handles basic validation)
        request = QueryRequest(**payload)

        # Additional injection detection on query
        injection_pattern = detect_injection_patterns(request.query)
        if injection_pattern:
            raise ValidationError(
                f"Potential security threat in query: {injection_pattern}"
            )

        # Sanitize query
        sanitized_query = sanitize_text(request.query, max_length=1000)

        # Create new request with sanitized query
        sanitized_request = QueryRequest(
            query=sanitized_query,
            limit=request.limit,
            context_level=request.context_level,
            scope=request.scope,
            project_name=request.project_name,
            category=request.category,
            min_importance=request.min_importance,
            tags=request.tags,
        )

        logger.debug(f"Validated query request: {sanitized_query[:50]}...")
        return sanitized_request

    except ValueError as e:
        raise ValidationError(f"Query validation failed: {str(e)}") from e


def validate_filter_params(filters: Dict[str, Any]) -> SearchFilters:
    """
    Validate filter parameters using allowlist.

    Args:
        filters: Filter parameters dictionary

    Returns:
        Validated SearchFilters

    Raises:
        ValidationError: If validation fails
    """
    try:
        # Use SearchFilters model for validation
        search_filters = SearchFilters(**filters)

        # Check for injection in project_name if provided
        if search_filters.project_name:
            injection_pattern = detect_injection_patterns(search_filters.project_name)
            if injection_pattern:
                raise ValidationError(
                    f"Security threat in project_name: {injection_pattern}"
                )

        # Check for injection in tags
        for tag in search_filters.tags:
            injection_pattern = detect_injection_patterns(tag)
            if injection_pattern:
                raise ValidationError(f"Security threat in tag: {injection_pattern}")

        logger.debug(f"Validated filter params: {search_filters}")
        return search_filters

    except ValueError as e:
        raise ValidationError(f"Filter validation failed: {str(e)}") from e


def validate_memory_id(memory_id: str) -> str:
    """
    Validate memory ID format.

    Args:
        memory_id: Memory ID to validate

    Returns:
        Validated memory ID

    Raises:
        ValidationError: If ID is invalid
    """
    if not memory_id or not isinstance(memory_id, str):
        raise ValidationError("Memory ID must be a non-empty string")

    # Sanitize
    sanitized_id = sanitize_text(memory_id, max_length=100)

    if not sanitized_id:
        raise ValidationError("Memory ID cannot be empty after sanitization")

    # Check for injection patterns
    injection_pattern = detect_injection_patterns(sanitized_id)
    if injection_pattern:
        raise ValidationError(f"Invalid memory ID format: {injection_pattern}")

    # UUID format check (optional, since we use UUID4)
    if not re.match(r"^[a-f0-9\-]{36}$", sanitized_id, re.IGNORECASE):
        logger.warning(f"Memory ID doesn't match UUID format: {sanitized_id}")

    return sanitized_id


def validate_project_name(project_name: Optional[str]) -> Optional[str]:
    """
    Validate project name.

    Args:
        project_name: Project name to validate

    Returns:
        Validated project name or None

    Raises:
        ValidationError: If validation fails
    """
    if not project_name:
        return None

    # Sanitize
    sanitized = sanitize_text(project_name, max_length=100)

    if not sanitized:
        return None

    # Check for injection patterns
    injection_pattern = detect_injection_patterns(sanitized)
    if injection_pattern:
        raise ValidationError(
            f"Invalid project name (security threat): {injection_pattern}"
        )

    # Alphanumeric, underscore, hyphen only
    if not re.match(r"^[a-zA-Z0-9_\-\.]+$", sanitized):
        raise ValidationError(
            "Project name must contain only letters, numbers, hyphens, underscores, and periods"
        )

    return sanitized


# ============================================================================
# Batch Validation
# ============================================================================


def validate_batch_store_requests(
    payloads: List[Dict[str, Any]]
) -> List[MemoryUnit]:
    """
    Validate a batch of store requests.

    Args:
        payloads: List of request payloads

    Returns:
        List of validated MemoryUnits

    Raises:
        ValidationError: If any validation fails
    """
    if not payloads:
        raise ValidationError("Batch request cannot be empty")

    if len(payloads) > 1000:
        raise ValidationError("Batch size exceeds maximum of 1000 items")

    validated = []
    errors = []

    for i, payload in enumerate(payloads):
        try:
            memory_unit = validate_store_request(payload)
            validated.append(memory_unit)
        except ValidationError as e:
            errors.append(f"Item {i}: {str(e)}")

    if errors:
        raise ValidationError(f"Batch validation failed:\n" + "\n".join(errors[:10]))

    logger.info(f"Validated batch of {len(validated)} memory units")
    return validated
