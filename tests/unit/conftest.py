"""Unit test fixtures with optimized scopes.

This module provides shared fixtures for unit tests with appropriate scoping:
- Module-scoped fixtures for read-only resources (configs, static data)
- Function-scoped fixtures for mutable resources

Scope Guidelines:
- Use module scope for fixtures that create immutable objects
- Use function scope for fixtures that create mutable objects or have side effects
- Never use session scope in unit tests (isolation is critical)
"""

import pytest
from src.config import ServerConfig
from src.core.models import MemoryUnit, MemoryScope, MemoryCategory, ContextLevel


@pytest.fixture(scope="module")
def module_config():
    """Module-scoped config for read-only tests.

    This fixture creates a ServerConfig instance that can be shared across
    all tests in a module. Use this for tests that only read config values
    and do not modify the config object.

    For tests that modify config or need isolated config, use a function-scoped
    fixture instead.
    """
    return ServerConfig(
        qdrant_collection_name="test-collection",
        storage_backend="qdrant",
    )


@pytest.fixture(scope="module")
def module_sample_memories():
    """Module-scoped sample memories for read-only tests.

    These MemoryUnit objects are immutable (frozen dataclasses) and can be
    safely shared across all tests in a module without risk of cross-test
    contamination.

    Use this fixture when tests only need to read memory content, not modify it.
    For tests that mutate memories or need fresh instances, use a function-scoped
    fixture instead.
    """
    return [
        MemoryUnit(
            id="mem1",
            content="authentication user login system",
            scope=MemoryScope.PROJECT,
            category=MemoryCategory.CONTEXT,
            context_level=ContextLevel.PROJECT_CONTEXT,
            project_name="test-project",
        ),
        MemoryUnit(
            id="mem2",
            content="database connection pool manager",
            scope=MemoryScope.PROJECT,
            category=MemoryCategory.CONTEXT,
            context_level=ContextLevel.PROJECT_CONTEXT,
            project_name="test-project",
        ),
        MemoryUnit(
            id="mem3",
            content="user authentication handler function",
            scope=MemoryScope.PROJECT,
            category=MemoryCategory.CONTEXT,
            context_level=ContextLevel.PROJECT_CONTEXT,
            project_name="test-project",
        ),
        MemoryUnit(
            id="mem4",
            content="configuration file parser",
            scope=MemoryScope.PROJECT,
            category=MemoryCategory.CONTEXT,
            context_level=ContextLevel.PROJECT_CONTEXT,
            project_name="test-project",
        ),
    ]
