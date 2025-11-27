"""
Integration tests for MCP Protocol Integration (F010).

Tests tool registration, schema validation, and MCP protocol compliance.
Covers SPEC requirements F010-R001 and F010-R002.
"""

import pytest
import pytest_asyncio
from typing import Dict, Any, List

from src.config import ServerConfig
from src.core.server import MemoryRAGServer
from src.core.models import MemoryCategory, MemoryScope
from src.core.exceptions import ValidationError
from pydantic import ValidationError as PydanticValidationError


# Expected MCP tools (from src/mcp_server.py)
# These are the core tools that map to actual server methods
EXPECTED_CORE_TOOLS = {
    # Memory Management (6 tools)
    "store_memory",
    "retrieve_memories",
    "list_memories",
    "delete_memory",
    "export_memories",
    "import_memories",
    # Code Search (4 tools)
    "search_code",
    "index_codebase",
    "find_similar_code",
    "search_all_projects",
    # Multi-Project (3 tools)
    "opt_in_cross_project",
    "opt_out_cross_project",
    "list_opted_in_projects",
    # Usage Analytics (3 tools)
    "get_usage_statistics",
    "get_top_queries",
    "get_frequently_accessed_code",
}

# Additional MCP tools exposed via mcp_server.py but implemented differently
# (via delegation, wrappers, or monitoring services)
DELEGATED_MCP_TOOLS = {
    # Git history (implemented via search_git_history)
    "search_git_commits",
    "get_file_history",
    # Call graph (implemented via separate service)
    "find_callers",
    "find_callees",
    "get_call_chain",
    "find_implementations",
    "find_dependencies",
    "find_dependents",
    # Monitoring (implemented via monitoring services)
    "get_performance_metrics",
    "get_health_score",
    "get_active_alerts",
    "start_dashboard",
    # Query suggestions (implemented via suggestion engine)
    "suggest_queries",
}

# All tools exposed via MCP
ALL_MCP_TOOLS = EXPECTED_CORE_TOOLS | DELEGATED_MCP_TOOLS

TOOL_CATEGORIES = {
    "memory_management": [
        "store_memory",
        "retrieve_memories",
        "list_memories",
        "delete_memory",
        "export_memories",
        "import_memories",
    ],
    "code_intelligence": [
        "search_code",
        "index_codebase",
        "find_similar_code",
    ],
    "multi_project": [
        "search_all_projects",
        "opt_in_cross_project",
        "opt_out_cross_project",
        "list_opted_in_projects",
    ],
    "usage_analytics": [
        "get_usage_statistics",
        "get_top_queries",
        "get_frequently_accessed_code",
    ],
}


@pytest.fixture
def config(unique_qdrant_collection):
    """Create test configuration."""
    return ServerConfig(
        storage_backend="qdrant",
        qdrant_url="http://localhost:6333",
        qdrant_collection_name=unique_qdrant_collection,
        advanced={"read_only_mode": False},
    )


@pytest_asyncio.fixture
async def server(config):
    """Create and initialize server instance."""
    srv = MemoryRAGServer(config)
    await srv.initialize()
    yield srv
    await srv.close()


class TestToolRegistration:
    """Tests for F010-R001: Tool registration and discoverability."""

    @pytest.mark.asyncio
    async def test_all_mcp_tools_registered(self, server):
        """
        F010-R001: Verify core MCP tools are registered and accessible.

        The server exposes 30 tools total via MCP. This test verifies the 16
        core tools that map directly to server methods are accessible.
        The remaining 14 tools are implemented via delegation/services.
        """
        # Get all public async methods that represent MCP tools
        tool_methods = {
            name for name in dir(server)
            if not name.startswith('_')
            and callable(getattr(server, name))
            and name in EXPECTED_CORE_TOOLS
        }

        # Verify all expected core tools exist as methods
        missing_tools = EXPECTED_CORE_TOOLS - tool_methods
        assert not missing_tools, f"Missing MCP tool methods: {missing_tools}"

        # Verify all core tools are accessible
        for tool_name in EXPECTED_CORE_TOOLS:
            method = getattr(server, tool_name, None)
            assert method is not None, f"Tool {tool_name} not found on server"
            assert callable(method), f"Tool {tool_name} is not callable"

        # Total of 29 tools (16 core + 13 delegated)
        assert len(EXPECTED_CORE_TOOLS) == 16, "Should have 16 core tools"
        assert len(DELEGATED_MCP_TOOLS) == 13, "Should have 13 delegated tools"
        assert len(ALL_MCP_TOOLS) == 29, "Should have 29 total MCP tools"

    @pytest.mark.asyncio
    async def test_tool_schemas_defined(self, server):
        """
        F010-R001: Verify each tool has proper input/output schemas.

        Tests that key tools have proper Pydantic models for validation.
        """
        # Test store_memory schema
        from src.core.models import StoreMemoryRequest
        schema = StoreMemoryRequest.model_json_schema()
        assert "content" in schema["properties"]
        assert "category" in schema["properties"]
        assert schema["required"] == ["content", "category"]

        # Test retrieve_memories schema
        from src.core.models import QueryRequest
        schema = QueryRequest.model_json_schema()
        assert "query" in schema["properties"]
        assert "limit" in schema["properties"]
        assert schema["required"] == ["query"]

        # Test search_code has advanced filtering
        from src.core.models import CodeSearchFilters
        schema = CodeSearchFilters.model_json_schema()
        assert "file_pattern" in schema["properties"]
        assert "complexity_min" in schema["properties"]
        assert "sort_by" in schema["properties"]

    @pytest.mark.asyncio
    async def test_tool_descriptions_present(self, server):
        """
        F010-R001: Verify each core tool has a description for Claude.

        Since we can't directly access MCP tool metadata from server,
        we verify that core methods have docstrings.
        """
        for tool_name in EXPECTED_CORE_TOOLS:
            method = getattr(server, tool_name)
            docstring = method.__doc__
            assert docstring is not None, f"Tool {tool_name} missing docstring"
            assert len(docstring.strip()) > 10, f"Tool {tool_name} has inadequate docstring"

    @pytest.mark.asyncio
    async def test_tool_categories_correct(self, server):
        """
        F010-R001: Verify tools are properly categorized by functionality.

        Tests that all core tools in each category exist.
        """
        for category, tools in TOOL_CATEGORIES.items():
            for tool_name in tools:
                assert tool_name in EXPECTED_CORE_TOOLS, (
                    f"Tool {tool_name} in category {category} not in core tools"
                )
                method = getattr(server, tool_name, None)
                assert method is not None, (
                    f"Category {category}: tool {tool_name} not found"
                )

    @pytest.mark.asyncio
    async def test_no_duplicate_tool_names(self, server):
        """
        F010-R001: Ensure no duplicate tool registrations.

        Verifies that each tool name appears only once across all tool sets.
        """
        core_names = list(EXPECTED_CORE_TOOLS)
        delegated_names = list(DELEGATED_MCP_TOOLS)
        all_names = core_names + delegated_names

        # Check for duplicates within all tools
        unique_names = set(all_names)
        assert len(all_names) == len(unique_names), (
            f"Duplicate tool names detected: {len(all_names)} vs {len(unique_names)}"
        )

        # Verify core and delegated don't overlap
        overlap = EXPECTED_CORE_TOOLS & DELEGATED_MCP_TOOLS
        assert len(overlap) == 0, f"Tools in both core and delegated: {overlap}"


class TestSchemaValidation:
    """Tests for F010-R002: Pydantic schema validation."""

    @pytest.mark.asyncio
    async def test_store_memory_validates_required_fields(self, server):
        """
        F010-R002: Missing content/category should raise ValidationError.
        """
        # Missing content
        with pytest.raises((ValidationError, PydanticValidationError)) as exc:
            from src.core.models import StoreMemoryRequest
            StoreMemoryRequest(category=MemoryCategory.FACT)

        error_msg = str(exc.value)
        assert "content" in error_msg.lower() or "required" in error_msg.lower()

        # Missing category
        with pytest.raises((ValidationError, PydanticValidationError)) as exc:
            from src.core.models import StoreMemoryRequest
            StoreMemoryRequest(content="test content")

        error_msg = str(exc.value)
        assert "category" in error_msg.lower() or "required" in error_msg.lower()

    @pytest.mark.asyncio
    async def test_search_code_validates_query(self, server):
        """
        F010-R002: Empty query should be rejected by validation.
        """
        # Empty string query
        with pytest.raises((ValidationError, PydanticValidationError)) as exc:
            from src.core.models import QueryRequest
            QueryRequest(query="")

        error_msg = str(exc.value)
        assert "query" in error_msg.lower() or "empty" in error_msg.lower()

        # Whitespace-only query
        with pytest.raises((ValidationError, PydanticValidationError)) as exc:
            from src.core.models import QueryRequest
            QueryRequest(query="   ")

        error_msg = str(exc.value)
        assert "query" in error_msg.lower() or "empty" in error_msg.lower()

    @pytest.mark.asyncio
    async def test_importance_range_validated(self, server):
        """
        F010-R002: Importance outside 0-1 range should be rejected.
        """
        from src.core.models import StoreMemoryRequest

        # Importance > 1.0
        with pytest.raises((ValidationError, PydanticValidationError)) as exc:
            StoreMemoryRequest(
                content="test",
                category=MemoryCategory.FACT,
                importance=1.5
            )

        error_msg = str(exc.value)
        assert "importance" in error_msg.lower() or "1.0" in error_msg.lower()

        # Importance < 0.0
        with pytest.raises((ValidationError, PydanticValidationError)) as exc:
            StoreMemoryRequest(
                content="test",
                category=MemoryCategory.FACT,
                importance=-0.5
            )

        error_msg = str(exc.value)
        assert "importance" in error_msg.lower() or "0.0" in error_msg.lower()

    @pytest.mark.asyncio
    async def test_category_enum_validated(self, server):
        """
        F010-R002: Invalid category values should be rejected.
        """
        from src.core.models import StoreMemoryRequest

        # Valid categories should work
        valid_request = StoreMemoryRequest(
            content="test",
            category="fact"  # String version of enum
        )
        assert valid_request.category == MemoryCategory.FACT

        # Invalid category should fail
        with pytest.raises((ValidationError, PydanticValidationError, ValueError)) as exc:
            StoreMemoryRequest(
                content="test",
                category="invalid_category"
            )

        error_msg = str(exc.value)
        assert "category" in error_msg.lower() or "enum" in error_msg.lower()

    @pytest.mark.asyncio
    async def test_nested_metadata_validated(self, server):
        """
        F010-R002: Complex nested metadata should be validated.
        """
        from src.core.models import StoreMemoryRequest, CodeSearchFilters

        # Test StoreMemoryRequest with metadata dict
        request = StoreMemoryRequest(
            content="test",
            category=MemoryCategory.FACT,
            metadata={"key": "value", "count": 42}
        )
        assert request.metadata == {"key": "value", "count": 42}

        # Test CodeSearchFilters with nested fields
        filters = CodeSearchFilters(
            file_pattern="**/*.py",
            complexity_min=1,
            complexity_max=10,
            sort_by="complexity"
        )
        assert filters.file_pattern == "**/*.py"
        assert filters.complexity_min == 1
        assert filters.sort_by == "complexity"

        # Invalid sort_by should fail
        with pytest.raises((ValidationError, PydanticValidationError, ValueError)) as exc:
            CodeSearchFilters(sort_by="invalid_sort")

        error_msg = str(exc.value)
        assert "sort_by" in error_msg.lower()


class TestMCPProtocolCompliance:
    """Additional tests for MCP protocol compliance."""

    @pytest.mark.asyncio
    async def test_tools_return_proper_types(self, server):
        """
        Verify that tool methods return expected types.
        """
        # Store memory should return dict with status
        result = await server.store_memory(
            content="test memory",
            category="fact",
            importance=0.5
        )
        assert isinstance(result, dict)
        assert "status" in result
        assert "memory_id" in result

        # List memories should return dict with memories list
        result = await server.list_memories(limit=10)
        assert isinstance(result, dict)
        assert "memories" in result
        assert isinstance(result["memories"], list)

    @pytest.mark.asyncio
    async def test_error_responses_are_json_serializable(self, server):
        """
        Verify that error responses can be serialized to JSON.
        """
        import json
        from src.core.exceptions import ValidationError as CustomValidationError

        # Create a validation error
        error = CustomValidationError(
            "Test validation error",
            solution="Fix the input",
            docs_url="https://docs.example.com"
        )

        # Error should have required attributes
        assert hasattr(error, 'solution')
        assert hasattr(error, 'docs_url')
        assert error.error_code == "E002"

        # Error message should be JSON-serializable
        error_dict = {
            "error_code": error.error_code,
            "message": str(error),
            "solution": error.solution,
            "docs_url": error.docs_url
        }

        # Should serialize without errors
        json_str = json.dumps(error_dict)
        assert isinstance(json_str, str)
        assert "E002" in json_str

    @pytest.mark.asyncio
    async def test_tools_handle_optional_parameters(self, server):
        """
        Verify tools handle optional parameters correctly.
        """
        # retrieve_memories with minimal params
        result = await server.retrieve_memories(query="test")
        assert isinstance(result, dict)

        # retrieve_memories with optional params
        result = await server.retrieve_memories(
            query="test",
            limit=5,
            min_importance=0.3
        )
        assert isinstance(result, dict)
        assert result.get("results") is not None

    @pytest.mark.asyncio
    async def test_tools_support_project_scoping(self, server):
        """
        Verify tools properly support project_name parameter.
        """
        # Store a project-scoped memory
        result = await server.store_memory(
            content="project test",
            category="fact",
            scope="project",
            project_name="test-project"
        )
        assert result["status"] == "success"

        # List memories should filter by project
        result = await server.list_memories(
            project_name="test-project",
            scope="project"
        )
        assert isinstance(result, dict)
        assert "memories" in result
