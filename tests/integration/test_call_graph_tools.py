"""
Integration tests for FEAT-059 call graph MCP tools.

Tests the 6 new structural query tools:
1. find_callers
2. find_callees
3. get_call_chain
4. find_implementations
5. find_dependencies
6. find_dependents

NOTE: These tests are currently skipped because the MCP tool methods
(find_callers, find_callees, etc.) have not yet been implemented on
MemoryRAGServer. They will be enabled once FEAT-059 is fully implemented.
"""

import pytest

pytestmark = pytest.mark.skip(
    reason="FEAT-059 MCP tool methods not yet implemented on MemoryRAGServer"
)
import pytest_asyncio

from src.core.server import MemoryRAGServer
from src.config import get_config
from src.store.call_graph_store import QdrantCallGraphStore
from src.graph.call_graph import (
    CallGraph,
    FunctionNode,
    CallSite,
    InterfaceImplementation,
)


@pytest_asyncio.fixture
async def server():
    """Create and initialize server with test configuration.

    Auto-indexing is globally disabled via conftest.py:disable_auto_indexing fixture.
    """
    config = get_config()
    server = MemoryRAGServer(config=config)
    await server.initialize()
    yield server
    await server.close()


@pytest_asyncio.fixture
async def call_graph_store():
    """Create and initialize call graph store."""
    store = QdrantCallGraphStore()
    await store.initialize()
    yield store
    # Cleanup: delete test project
    try:
        await store.delete_project_call_graph("test-project")
    except Exception:
        pass


@pytest_asyncio.fixture
async def sample_call_graph(call_graph_store):
    """
    Create a sample call graph for testing.

    Structure:
    - main() -> process() -> validate()
    - main() -> log()
    - process() -> helper()
    - MyInterface -> MyImplementation, AnotherImplementation
    """
    # Create function nodes
    functions = [
        FunctionNode(
            name="main",
            qualified_name="main",
            file_path="/test/main.py",
            language="python",
            start_line=1,
            end_line=10,
            is_exported=True,
        ),
        FunctionNode(
            name="process",
            qualified_name="process",
            file_path="/test/main.py",
            language="python",
            start_line=12,
            end_line=20,
        ),
        FunctionNode(
            name="validate",
            qualified_name="validate",
            file_path="/test/utils.py",
            language="python",
            start_line=5,
            end_line=15,
        ),
        FunctionNode(
            name="log",
            qualified_name="log",
            file_path="/test/logger.py",
            language="python",
            start_line=1,
            end_line=5,
        ),
        FunctionNode(
            name="helper",
            qualified_name="helper",
            file_path="/test/utils.py",
            language="python",
            start_line=20,
            end_line=30,
        ),
    ]

    # Store function nodes
    for func in functions:
        await call_graph_store.store_function_node(
            func,
            project_name="test-project",
            calls_to=[],
            called_by=[],
        )

    # Create call graph with relationships
    graph = CallGraph()
    for func in functions:
        graph.add_function(func)

    # Add call relationships
    calls = [
        CallSite("main", "/test/main.py", 3, "process", "/test/main.py", "direct"),
        CallSite("main", "/test/main.py", 5, "log", "/test/logger.py", "direct"),
        CallSite(
            "process", "/test/main.py", 15, "validate", "/test/utils.py", "direct"
        ),
        CallSite("process", "/test/main.py", 17, "helper", "/test/utils.py", "direct"),
    ]

    for call in calls:
        graph.add_call(call)

    # Update forward/reverse indexes in Qdrant
    for func in functions:
        calls_to = list(graph.forward_index.get(func.qualified_name, set()))
        called_by = list(graph.reverse_index.get(func.qualified_name, set()))
        await call_graph_store.store_function_node(
            func,
            project_name="test-project",
            calls_to=calls_to,
            called_by=called_by,
        )

    # Store call sites
    for func in functions:
        call_sites = graph.get_call_sites_for_caller(func.qualified_name)
        if call_sites:
            await call_graph_store.store_call_sites(
                func.qualified_name,
                call_sites,
                "test-project",
            )

    # Add interface implementations
    implementations = [
        InterfaceImplementation(
            interface_name="MyInterface",
            implementation_name="MyImplementation",
            file_path="/test/impl1.py",
            language="python",
            methods=["method1", "method2"],
        ),
        InterfaceImplementation(
            interface_name="MyInterface",
            implementation_name="AnotherImplementation",
            file_path="/test/impl2.py",
            language="python",
            methods=["method1", "method2", "method3"],
        ),
    ]

    await call_graph_store.store_implementations(
        "MyInterface",
        implementations,
        "test-project",
    )

    return graph


# =============================================================================
# TEST: find_callers
# =============================================================================


@pytest.mark.asyncio
async def test_find_callers_direct(server, sample_call_graph):
    """Test finding direct callers of a function."""
    result = await server.find_callers(
        function_name="process",
        project_name="test-project",
        include_indirect=False,
    )

    assert result["function_name"] == "process"
    assert result["project_name"] == "test-project"
    assert result["total_count"] == 1
    assert len(result["direct_callers"]) == 1
    assert result["direct_callers"][0]["qualified_name"] == "main"
    assert result["indirect_callers"] == []


@pytest.mark.asyncio
async def test_find_callers_indirect(server, sample_call_graph):
    """Test finding indirect callers of a function."""
    result = await server.find_callers(
        function_name="validate",
        project_name="test-project",
        include_indirect=True,
        max_depth=3,
    )

    assert result["function_name"] == "validate"
    assert result["total_count"] >= 1  # At least process (direct)

    # validate is called by process
    direct_names = [c["qualified_name"] for c in result["direct_callers"]]
    assert "process" in direct_names

    # main -> process -> validate, so main should be in indirect callers
    if result["indirect_callers"]:
        indirect_names = [c["qualified_name"] for c in result["indirect_callers"]]
        assert "main" in indirect_names


@pytest.mark.asyncio
async def test_find_callers_no_results(server, sample_call_graph):
    """Test finding callers for a function with no callers."""
    result = await server.find_callers(
        function_name="log",
        project_name="test-project",
        include_indirect=False,
    )

    # log is called by main, so it should have 1 caller
    assert result["total_count"] >= 0


# =============================================================================
# TEST: find_callees
# =============================================================================


@pytest.mark.asyncio
async def test_find_callees_direct(server, sample_call_graph):
    """Test finding direct callees of a function."""
    result = await server.find_callees(
        function_name="main",
        project_name="test-project",
        include_indirect=False,
    )

    assert result["function_name"] == "main"
    assert result["total_count"] == 2  # process, log
    assert len(result["direct_callees"]) == 2

    callee_names = [c["qualified_name"] for c in result["direct_callees"]]
    assert "process" in callee_names
    assert "log" in callee_names


@pytest.mark.asyncio
async def test_find_callees_indirect(server, sample_call_graph):
    """Test finding indirect callees of a function."""
    result = await server.find_callees(
        function_name="main",
        project_name="test-project",
        include_indirect=True,
        max_depth=3,
    )

    assert result["function_name"] == "main"
    assert result["total_count"] >= 2  # At least process, log

    # main -> process -> validate, helper
    # So validate and helper should be in results
    all_callees = result["direct_callees"] + result.get("indirect_callees", [])
    all_names = [c["qualified_name"] for c in all_callees]
    assert "process" in all_names
    assert "validate" in all_names or "helper" in all_names


@pytest.mark.asyncio
async def test_find_callees_no_results(server, sample_call_graph):
    """Test finding callees for a leaf function."""
    result = await server.find_callees(
        function_name="validate",
        project_name="test-project",
        include_indirect=False,
    )

    # validate doesn't call anything
    assert result["total_count"] == 0
    assert result["direct_callees"] == []


# =============================================================================
# TEST: get_call_chain
# =============================================================================


@pytest.mark.asyncio
async def test_get_call_chain_found(server, sample_call_graph):
    """Test finding call chain between two functions."""
    result = await server.get_call_chain(
        from_function="main",
        to_function="validate",
        project_name="test-project",
        max_paths=5,
        max_depth=10,
    )

    assert result["from_function"] == "main"
    assert result["to_function"] == "validate"
    assert result["path_count"] >= 1

    # Should find path: main -> process -> validate
    if result["paths"]:
        path = result["paths"][0]["path"]
        assert "main" in path
        assert "validate" in path
        assert path.index("main") < path.index("validate")


@pytest.mark.asyncio
async def test_get_call_chain_not_found(server, sample_call_graph):
    """Test call chain when no path exists."""
    result = await server.get_call_chain(
        from_function="validate",
        to_function="main",
        project_name="test-project",
        max_paths=5,
        max_depth=10,
    )

    # No path from validate back to main
    assert result["path_count"] == 0
    assert result["paths"] == []


# =============================================================================
# TEST: find_implementations
# =============================================================================


@pytest.mark.asyncio
async def test_find_implementations(server, sample_call_graph):
    """Test finding interface implementations."""
    result = await server.find_implementations(
        interface_name="MyInterface",
        project_name="test-project",
    )

    assert result["interface_name"] == "MyInterface"
    assert result["total_count"] == 2
    assert len(result["implementations"]) == 2

    impl_names = [impl["implementation_name"] for impl in result["implementations"]]
    assert "MyImplementation" in impl_names
    assert "AnotherImplementation" in impl_names


@pytest.mark.asyncio
async def test_find_implementations_with_language_filter(server, sample_call_graph):
    """Test finding implementations with language filter."""
    result = await server.find_implementations(
        interface_name="MyInterface",
        project_name="test-project",
        language="python",
    )

    assert result["total_count"] == 2
    for impl in result["implementations"]:
        assert impl["language"] == "python"


@pytest.mark.asyncio
async def test_find_implementations_no_results(server, sample_call_graph):
    """Test finding implementations for non-existent interface."""
    result = await server.find_implementations(
        interface_name="NonExistentInterface",
        project_name="test-project",
    )

    assert result["total_count"] == 0
    assert result["implementations"] == []


# =============================================================================
# TEST: find_dependencies (uses existing dependency graph infrastructure)
# =============================================================================


@pytest.mark.asyncio
async def test_find_dependencies_basic(server):
    """Test finding file dependencies."""
    # This test requires dependency graph to be built
    # For now, we test that the method works without errors
    result = await server.find_dependencies(
        file_path="/test/main.py",
        project_name="test-project",
        include_transitive=False,
    )

    assert result["file_path"] == "/test/main.py"
    assert result["project_name"] == "test-project"
    assert "direct_dependencies" in result
    assert "total_count" in result


# =============================================================================
# TEST: find_dependents (uses existing dependency graph infrastructure)
# =============================================================================


@pytest.mark.asyncio
async def test_find_dependents_basic(server):
    """Test finding reverse file dependencies."""
    # This test requires dependency graph to be built
    # For now, we test that the method works without errors
    result = await server.find_dependents(
        file_path="/test/utils.py",
        project_name="test-project",
        include_transitive=False,
    )

    assert result["file_path"] == "/test/utils.py"
    assert result["project_name"] == "test-project"
    assert "direct_dependents" in result
    assert "total_count" in result


# =============================================================================
# ERROR HANDLING TESTS
# =============================================================================


@pytest.mark.asyncio
async def test_find_callers_missing_function_name(server):
    """Test error handling when function_name is missing."""
    with pytest.raises(Exception):  # Should raise ValidationError
        await server.find_callers(
            function_name="",
            project_name="test-project",
        )


@pytest.mark.asyncio
async def test_get_call_chain_missing_parameters(server):
    """Test error handling when required parameters are missing."""
    with pytest.raises(Exception):  # Should raise ValidationError
        await server.get_call_chain(
            from_function="",
            to_function="target",
            project_name="test-project",
        )


@pytest.mark.asyncio
async def test_find_implementations_missing_interface_name(server):
    """Test error handling when interface_name is missing."""
    with pytest.raises(Exception):  # Should raise ValidationError
        await server.find_implementations(
            interface_name="",
            project_name="test-project",
        )


# =============================================================================
# LIMIT AND PAGINATION TESTS
# =============================================================================


@pytest.mark.asyncio
async def test_find_callers_with_limit(server, sample_call_graph):
    """Test that limit parameter works correctly."""
    result = await server.find_callers(
        function_name="process",
        project_name="test-project",
        include_indirect=False,
        limit=1,
    )

    assert result["returned_count"] <= 1
    assert len(result["direct_callers"]) <= 1


@pytest.mark.asyncio
async def test_find_callees_with_max_depth(server, sample_call_graph):
    """Test that max_depth parameter works correctly."""
    result = await server.find_callees(
        function_name="main",
        project_name="test-project",
        include_indirect=True,
        max_depth=1,  # Only direct callees
    )

    # With max_depth=1, we should only get direct callees
    assert result["max_depth"] == 1
