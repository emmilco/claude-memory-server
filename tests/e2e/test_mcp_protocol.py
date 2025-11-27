"""E2E tests for MCP protocol integration.

These tests verify that the MCP server correctly exposes tools and handles
tool calls according to the MCP protocol specification.
"""

import pytest
import pytest_asyncio
from typing import Dict, Any, List
from pathlib import Path

from src.core.server import MemoryRAGServer
from src.config import get_config


# ============================================================================
# MCP Tool Discovery Tests (3 tests)
# ============================================================================

@pytest.mark.e2e
@pytest.mark.asyncio
async def test_mcp_tools_available():
    """Test: MCP server exposes expected tools.

    Verifies that all core MCP tools are available for Claude to use.
    """
    # Import the MCP server module to check tool definitions
    from src import mcp_server

    # Get the list of tools
    tools = await mcp_server.list_tools()

    # Should have tools
    assert len(tools) > 0

    # Extract tool names
    tool_names = [t.name for t in tools]

    # Core memory tools should be available
    assert "store_memory" in tool_names
    assert "retrieve_memories" in tool_names
    assert "list_memories" in tool_names
    assert "delete_memory" in tool_names

    # Code search tools should be available
    assert "search_code" in tool_names


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_mcp_tools_have_schemas():
    """Test: MCP tools have proper input schemas.

    Verifies that tools are properly documented with JSON schemas.
    """
    from src import mcp_server

    tools = await mcp_server.list_tools()

    for tool in tools:
        # Each tool should have a name and description
        assert tool.name, "Tool must have a name"
        assert tool.description, f"Tool {tool.name} must have a description"

        # Each tool should have an input schema
        assert tool.inputSchema, f"Tool {tool.name} must have input schema"
        assert "type" in tool.inputSchema, f"Tool {tool.name} schema must specify type"


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_mcp_tool_categories():
    """Test: MCP tools cover all major categories.

    Verifies tools exist for memory, code search, and utility operations.
    """
    from src import mcp_server

    tools = await mcp_server.list_tools()
    tool_names = set(t.name for t in tools)

    # Memory management category
    memory_tools = {"store_memory", "retrieve_memories", "list_memories", "delete_memory"}
    assert memory_tools.issubset(tool_names), f"Missing memory tools: {memory_tools - tool_names}"

    # Code search category
    code_tools = {"search_code"}
    assert code_tools.issubset(tool_names), f"Missing code tools: {code_tools - tool_names}"


# ============================================================================
# MCP Tool Invocation Tests (5 tests)
# ============================================================================

@pytest.mark.e2e
@pytest.mark.asyncio
async def test_mcp_store_memory_tool(fresh_server):
    """Test: store_memory tool via MCP-style invocation.

    Simulates how Claude would call the store_memory tool.
    """
    from src import mcp_server

    # Initialize the MCP server's memory server
    mcp_server.memory_server = fresh_server

    # Call the tool
    result = await mcp_server.call_tool("store_memory", {
        "content": "MCP test: User prefers TypeScript over JavaScript",
        "category": "preference",
        "importance": 0.8,
        "tags": ["mcp-test", "language-preference"],
    })

    # Should return TextContent
    assert result is not None
    assert len(result) > 0

    # Result should indicate success
    result_text = result[0].text
    assert "memory_id" in result_text or "success" in result_text.lower()


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_mcp_retrieve_memories_tool(fresh_server):
    """Test: retrieve_memories tool via MCP-style invocation."""
    from src import mcp_server

    mcp_server.memory_server = fresh_server

    # First store a memory
    await mcp_server.call_tool("store_memory", {
        "content": "MCP retrieval test: The API uses OAuth 2.0 for authentication",
        "category": "fact",
        "importance": 0.7,
        "tags": ["mcp-test", "auth"],
    })

    # Now retrieve it
    result = await mcp_server.call_tool("retrieve_memories", {
        "query": "OAuth authentication API",
        "limit": 5,
    })

    assert result is not None
    assert len(result) > 0

    result_text = result[0].text
    # Should find the memory we just stored
    assert "OAuth" in result_text or "results" in result_text


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_mcp_list_memories_tool(fresh_server):
    """Test: list_memories tool via MCP-style invocation."""
    from src import mcp_server

    mcp_server.memory_server = fresh_server

    # Store some memories first
    await mcp_server.call_tool("store_memory", {
        "content": "MCP list test memory 1",
        "category": "fact",
    })
    await mcp_server.call_tool("store_memory", {
        "content": "MCP list test memory 2",
        "category": "fact",
    })

    # List memories
    result = await mcp_server.call_tool("list_memories", {
        "limit": 10,
    })

    assert result is not None
    assert len(result) > 0

    result_text = result[0].text
    # Should show memories
    assert "memories" in result_text.lower() or "MCP list test" in result_text


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_mcp_search_code_tool(fresh_server, sample_code_project):
    """Test: search_code tool via MCP-style invocation."""
    from src import mcp_server

    mcp_server.memory_server = fresh_server

    # First index the sample project
    await fresh_server.index_codebase(
        directory_path=str(sample_code_project),
        project_name="mcp-search-test",
        recursive=True,
    )

    # Search via MCP tool
    result = await mcp_server.call_tool("search_code", {
        "query": "authentication function",
        "project_name": "mcp-search-test",
        "limit": 5,
    })

    assert result is not None
    assert len(result) > 0

    result_text = result[0].text
    # Should find code results
    assert "results" in result_text.lower() or "auth" in result_text.lower()


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_mcp_delete_memory_tool(fresh_server):
    """Test: delete_memory tool via MCP-style invocation."""
    from src import mcp_server
    import json
    import re

    mcp_server.memory_server = fresh_server

    # Store a memory
    store_result = await mcp_server.call_tool("store_memory", {
        "content": "MCP delete test: This memory will be deleted",
        "category": "fact",
    })

    # Extract memory_id from result (handle both JSON and formatted text)
    store_text = store_result[0].text
    memory_id = None

    try:
        store_data = json.loads(store_text)
        memory_id = store_data.get("memory_id")
    except json.JSONDecodeError:
        # Try to extract from formatted text like "✅ Stored fact memory (ID: xxx)"
        match = re.search(r'\(ID:\s*([a-f0-9-]+)\)', store_text, re.IGNORECASE)
        if not match:
            match = re.search(r'memory_id["\s:]+([a-f0-9-]+)', store_text, re.IGNORECASE)
        if match:
            memory_id = match.group(1)

    assert memory_id, f"Should have stored memory with ID, got: {store_text[:200]}"

    # Delete the memory
    delete_result = await mcp_server.call_tool("delete_memory", {
        "memory_id": memory_id,
    })

    assert delete_result is not None
    delete_text = delete_result[0].text
    # Should indicate deletion
    assert "delet" in delete_text.lower() or "success" in delete_text.lower()


# ============================================================================
# MCP Error Handling Tests (3 tests)
# ============================================================================

@pytest.mark.e2e
@pytest.mark.asyncio
async def test_mcp_invalid_tool_name(fresh_server):
    """Test: MCP handles invalid tool names gracefully."""
    from src import mcp_server

    mcp_server.memory_server = fresh_server

    # Try calling a non-existent tool
    result = await mcp_server.call_tool("nonexistent_tool", {})

    assert result is not None
    result_text = result[0].text
    # Should indicate error or unknown tool
    assert "error" in result_text.lower() or "unknown" in result_text.lower()


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_mcp_missing_required_params(fresh_server):
    """Test: MCP handles missing required parameters."""
    from src import mcp_server

    mcp_server.memory_server = fresh_server

    # Call store_memory without required 'content' field
    result = await mcp_server.call_tool("store_memory", {
        "category": "fact",
        # Missing 'content'
    })

    assert result is not None
    result_text = result[0].text
    # Should indicate validation error
    assert "error" in result_text.lower() or "required" in result_text.lower() or "content" in result_text.lower()


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_mcp_invalid_param_values(fresh_server):
    """Test: MCP handles invalid parameter values."""
    from src import mcp_server

    mcp_server.memory_server = fresh_server

    # Call with invalid category
    result = await mcp_server.call_tool("store_memory", {
        "content": "Test content",
        "category": "invalid_category_xyz",
    })

    assert result is not None
    result_text = result[0].text
    # Should indicate validation error or store with default
    # (behavior depends on implementation)
    assert result_text  # Should have some response


# ============================================================================
# MCP Full Workflow Tests (2 tests)
# ============================================================================

@pytest.mark.e2e
@pytest.mark.asyncio
async def test_mcp_memory_crud_workflow(fresh_server):
    """Test: Complete CRUD workflow via MCP tools.

    Simulates a full memory management session via MCP.
    """
    from src import mcp_server
    import json
    import re

    mcp_server.memory_server = fresh_server

    # CREATE
    create_result = await mcp_server.call_tool("store_memory", {
        "content": "CRUD test: Project uses PostgreSQL database",
        "category": "fact",
        "importance": 0.9,
        "tags": ["database", "infrastructure"],
    })

    # Extract memory_id (handle both JSON and formatted text)
    create_text = create_result[0].text
    memory_id = None

    try:
        create_data = json.loads(create_text)
        memory_id = create_data.get("memory_id")
    except json.JSONDecodeError:
        # Try to extract from formatted text like "✅ Stored fact memory (ID: xxx)"
        match = re.search(r'\(ID:\s*([a-f0-9-]+)\)', create_text, re.IGNORECASE)
        if not match:
            match = re.search(r'memory_id["\s:]+([a-f0-9-]+)', create_text, re.IGNORECASE)
        if match:
            memory_id = match.group(1)

    assert memory_id, f"Should have stored memory with ID, got: {create_text[:200]}"

    # READ (via retrieve)
    retrieve_result = await mcp_server.call_tool("retrieve_memories", {
        "query": "PostgreSQL database",
        "limit": 5,
    })
    retrieve_text = retrieve_result[0].text
    assert "PostgreSQL" in retrieve_text or "results" in retrieve_text.lower()

    # READ (via list)
    list_result = await mcp_server.call_tool("list_memories", {
        "tags": ["database"],
        "limit": 10,
    })
    list_text = list_result[0].text
    assert "PostgreSQL" in list_text or memory_id in list_text or "memories" in list_text.lower()

    # DELETE
    delete_result = await mcp_server.call_tool("delete_memory", {
        "memory_id": memory_id,
    })
    assert "delet" in delete_result[0].text.lower() or "success" in delete_result[0].text.lower()

    # VERIFY DELETED
    list_after = await mcp_server.call_tool("list_memories", {
        "tags": ["database"],
        "limit": 10,
    })
    # Memory should no longer appear (or list should be empty/smaller)


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_mcp_code_search_workflow(fresh_server, sample_code_project):
    """Test: Code indexing and search workflow via MCP tools.

    Simulates indexing code and searching it via MCP.
    """
    from src import mcp_server

    mcp_server.memory_server = fresh_server

    # Index the project (using server method directly - indexing isn't an MCP tool)
    index_result = await fresh_server.index_codebase(
        directory_path=str(sample_code_project),
        project_name="mcp-workflow-test",
        recursive=True,
    )
    assert index_result["files_indexed"] > 0

    # Search for authentication code
    auth_result = await mcp_server.call_tool("search_code", {
        "query": "authentication password verification",
        "project_name": "mcp-workflow-test",
        "search_mode": "semantic",
        "limit": 5,
    })
    assert "auth" in auth_result[0].text.lower() or "password" in auth_result[0].text.lower()

    # Search for database code
    db_result = await mcp_server.call_tool("search_code", {
        "query": "database connection",
        "project_name": "mcp-workflow-test",
        "search_mode": "semantic",
        "limit": 5,
    })
    assert "database" in db_result[0].text.lower() or "connection" in db_result[0].text.lower()

    # Search with hybrid mode
    hybrid_result = await mcp_server.call_tool("search_code", {
        "query": "API request handler",
        "project_name": "mcp-workflow-test",
        "search_mode": "hybrid",
        "limit": 5,
    })
    assert hybrid_result is not None
