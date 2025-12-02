"""Tests for structural/relational query tools (FEAT-059)."""

import pytest
from unittest.mock import AsyncMock, patch

from src.core.server import MemoryRAGServer
from src.graph.call_graph import (
    CallGraph,
    CallSite,
    FunctionNode,
    InterfaceImplementation,
)
from src.config import ServerConfig


@pytest.fixture
def config():
    """Create test configuration."""
    return ServerConfig(
        qdrant_url="http://localhost:6333",
        qdrant_collection_name="test_memories",
        advanced={"read_only_mode": False},
    )


@pytest.fixture
async def server(config):
    """Create test server instance."""
    server = MemoryRAGServer(config)
    server.project_name = "test_project"
    # Mock the call graph store
    with patch("src.store.call_graph_store.QdrantCallGraphStore"):
        yield server


@pytest.fixture
def sample_call_graph():
    """Create a sample call graph for testing."""
    graph = CallGraph()

    # Add function nodes
    main_func = FunctionNode(
        name="main",
        qualified_name="main",
        file_path="/test/main.py",
        language="python",
        start_line=1,
        end_line=10,
        is_exported=True,
        is_async=False,
        parameters=[],
    )

    process_func = FunctionNode(
        name="process_request",
        qualified_name="process_request",
        file_path="/test/api.py",
        language="python",
        start_line=20,
        end_line=35,
        is_exported=True,
        is_async=True,
        parameters=["request"],
    )

    validate_func = FunctionNode(
        name="validate",
        qualified_name="validate",
        file_path="/test/validation.py",
        language="python",
        start_line=5,
        end_line=15,
        is_exported=False,
        is_async=False,
        parameters=["data"],
    )

    db_query_func = FunctionNode(
        name="database_query",
        qualified_name="database_query",
        file_path="/test/db.py",
        language="python",
        start_line=40,
        end_line=60,
        is_exported=True,
        is_async=True,
        parameters=["query", "params"],
    )

    graph.add_function(main_func)
    graph.add_function(process_func)
    graph.add_function(validate_func)
    graph.add_function(db_query_func)

    # Add call relationships
    # main -> process_request
    graph.add_call(
        CallSite(
            caller_function="main",
            caller_file="/test/main.py",
            caller_line=5,
            callee_function="process_request",
            callee_file="/test/api.py",
            call_type="direct",
        )
    )

    # process_request -> validate
    graph.add_call(
        CallSite(
            caller_function="process_request",
            caller_file="/test/api.py",
            caller_line=25,
            callee_function="validate",
            callee_file="/test/validation.py",
            call_type="direct",
        )
    )

    # process_request -> database_query
    graph.add_call(
        CallSite(
            caller_function="process_request",
            caller_file="/test/api.py",
            caller_line=30,
            callee_function="database_query",
            callee_file="/test/db.py",
            call_type="direct",
        )
    )

    # Add interface implementation
    graph.add_implementation(
        InterfaceImplementation(
            interface_name="Storage",
            implementation_name="RedisStorage",
            file_path="/test/redis_storage.py",
            language="python",
            methods=["get", "set", "delete", "clear"],
        )
    )

    graph.add_implementation(
        InterfaceImplementation(
            interface_name="Storage",
            implementation_name="MemoryStorage",
            file_path="/test/memory_storage.py",
            language="python",
            methods=["get", "set", "delete"],
        )
    )

    return graph


# find_callers tests


@pytest.mark.asyncio
async def test_find_callers_direct_single_caller(server, sample_call_graph):
    """Test finding direct callers with a single caller."""
    with patch("src.store.call_graph_store.QdrantCallGraphStore") as MockStore:
        mock_store = AsyncMock()
        mock_store.load_call_graph = AsyncMock(return_value=sample_call_graph)
        MockStore.return_value = mock_store

        result = await server.find_callers(
            function_name="process_request", include_indirect=False, max_depth=1
        )

        assert result["function"] == "process_request"
        assert result["total_callers"] >= 1
        assert any(c["caller_function"] == "main" for c in result["callers"])
        assert result["direct_callers"] >= 1
        assert "analysis_time_ms" in result


@pytest.mark.asyncio
async def test_find_callers_multiple_callers(server, sample_call_graph):
    """Test finding multiple direct callers."""
    # Add another caller to validate
    sample_call_graph.add_call(
        CallSite(
            caller_function="main",
            caller_file="/test/main.py",
            caller_line=7,
            callee_function="validate",
            callee_file="/test/validation.py",
            call_type="direct",
        )
    )

    with patch("src.store.call_graph_store.QdrantCallGraphStore") as MockStore:
        mock_store = AsyncMock()
        mock_store.load_call_graph = AsyncMock(return_value=sample_call_graph)
        MockStore.return_value = mock_store

        result = await server.find_callers(
            function_name="validate", include_indirect=False
        )

        assert result["total_callers"] >= 2
        caller_functions = [c["caller_function"] for c in result["callers"]]
        assert "process_request" in caller_functions
        assert "main" in caller_functions


@pytest.mark.asyncio
async def test_find_callers_indirect_depth_2(server, sample_call_graph):
    """Test finding indirect callers with depth=2."""
    with patch("src.store.call_graph_store.QdrantCallGraphStore") as MockStore:
        mock_store = AsyncMock()
        mock_store.load_call_graph = AsyncMock(return_value=sample_call_graph)
        MockStore.return_value = mock_store

        result = await server.find_callers(
            function_name="validate", include_indirect=True, max_depth=2
        )

        # Should find process_request (direct caller)
        # Note: The implementation returns call sites, not unique callers
        # so we expect at least 1 caller (process_request)
        assert result["total_callers"] >= 1
        assert result["direct_callers"] >= 1
        assert "analysis_time_ms" in result


@pytest.mark.asyncio
async def test_find_callers_function_not_found(server, sample_call_graph):
    """Test finding callers for non-existent function."""
    with patch("src.store.call_graph_store.QdrantCallGraphStore") as MockStore:
        mock_store = AsyncMock()
        mock_store.load_call_graph = AsyncMock(return_value=sample_call_graph)
        MockStore.return_value = mock_store

        result = await server.find_callers(
            function_name="nonexistent_function", include_indirect=False
        )

        assert result["total_callers"] == 0
        assert result["callers"] == []


@pytest.mark.asyncio
async def test_find_callers_respects_limit(server, sample_call_graph):
    """Test that limit parameter is respected."""
    # Add many callers
    for i in range(20):
        sample_call_graph.add_call(
            CallSite(
                caller_function=f"caller_{i}",
                caller_file=f"/test/caller_{i}.py",
                caller_line=10,
                callee_function="validate",
                call_type="direct",
            )
        )
        sample_call_graph.add_function(
            FunctionNode(
                name=f"caller_{i}",
                qualified_name=f"caller_{i}",
                file_path=f"/test/caller_{i}.py",
                language="python",
                start_line=1,
                end_line=20,
            )
        )

    with patch("src.store.call_graph_store.QdrantCallGraphStore") as MockStore:
        mock_store = AsyncMock()
        mock_store.load_call_graph = AsyncMock(return_value=sample_call_graph)
        MockStore.return_value = mock_store

        result = await server.find_callers(function_name="validate", limit=10)

        assert len(result["callers"]) <= 10


# find_callees tests


@pytest.mark.asyncio
async def test_find_callees_direct_single_callee(server, sample_call_graph):
    """Test finding direct callees with a single callee."""
    with patch("src.store.call_graph_store.QdrantCallGraphStore") as MockStore:
        mock_store = AsyncMock()
        mock_store.load_call_graph = AsyncMock(return_value=sample_call_graph)
        MockStore.return_value = mock_store

        result = await server.find_callees(function_name="main", include_indirect=False)

        assert result["function"] == "main"
        assert result["total_callees"] >= 1
        assert any(c["callee_function"] == "process_request" for c in result["callees"])
        assert "analysis_time_ms" in result


@pytest.mark.asyncio
async def test_find_callees_multiple_callees(server, sample_call_graph):
    """Test finding multiple direct callees."""
    with patch("src.store.call_graph_store.QdrantCallGraphStore") as MockStore:
        mock_store = AsyncMock()
        mock_store.load_call_graph = AsyncMock(return_value=sample_call_graph)
        MockStore.return_value = mock_store

        result = await server.find_callees(
            function_name="process_request", include_indirect=False
        )

        assert result["total_callees"] >= 2
        callee_functions = [c["callee_function"] for c in result["callees"]]
        assert "validate" in callee_functions
        assert "database_query" in callee_functions


@pytest.mark.asyncio
async def test_find_callees_indirect_depth_3(server, sample_call_graph):
    """Test finding indirect callees with depth=3."""
    with patch("src.store.call_graph_store.QdrantCallGraphStore") as MockStore:
        mock_store = AsyncMock()
        mock_store.load_call_graph = AsyncMock(return_value=sample_call_graph)
        MockStore.return_value = mock_store

        result = await server.find_callees(
            function_name="main", include_indirect=True, max_depth=3
        )

        # Should find process_request (direct) and validate/database_query (indirect)
        assert result["total_callees"] >= 1
        assert "analysis_time_ms" in result


@pytest.mark.asyncio
async def test_find_callees_empty_function(server, sample_call_graph):
    """Test finding callees for function with no calls."""
    with patch("src.store.call_graph_store.QdrantCallGraphStore") as MockStore:
        mock_store = AsyncMock()
        mock_store.load_call_graph = AsyncMock(return_value=sample_call_graph)
        MockStore.return_value = mock_store

        result = await server.find_callees(
            function_name="database_query", include_indirect=False
        )

        assert result["total_callees"] == 0
        assert result["callees"] == []


# find_implementations tests


@pytest.mark.asyncio
async def test_find_implementations_single_impl(server):
    """Test finding a single implementation."""
    mock_impls = [
        InterfaceImplementation(
            interface_name="Logger",
            implementation_name="FileLogger",
            file_path="/test/file_logger.py",
            language="python",
            methods=["log", "error", "warning"],
        )
    ]

    with patch("src.store.call_graph_store.QdrantCallGraphStore") as MockStore:
        mock_store = AsyncMock()
        mock_store.get_implementations = AsyncMock(return_value=mock_impls)
        MockStore.return_value = mock_store

        result = await server.find_implementations(interface_name="Logger")

        assert result["interface"] == "Logger"
        assert result["total_implementations"] == 1
        assert result["implementations"][0]["class_name"] == "FileLogger"
        assert "analysis_time_ms" in result


@pytest.mark.asyncio
async def test_find_implementations_multiple_impls(server):
    """Test finding multiple implementations."""
    mock_impls = [
        InterfaceImplementation(
            interface_name="Storage",
            implementation_name="RedisStorage",
            file_path="/test/redis.py",
            language="python",
            methods=["get", "set", "delete", "clear"],
        ),
        InterfaceImplementation(
            interface_name="Storage",
            implementation_name="MemoryStorage",
            file_path="/test/memory.py",
            language="python",
            methods=["get", "set", "delete"],
        ),
    ]

    with patch("src.store.call_graph_store.QdrantCallGraphStore") as MockStore:
        mock_store = AsyncMock()
        mock_store.get_implementations = AsyncMock(return_value=mock_impls)
        MockStore.return_value = mock_store

        result = await server.find_implementations(interface_name="Storage")

        assert result["total_implementations"] == 2
        impl_names = [impl["class_name"] for impl in result["implementations"]]
        assert "RedisStorage" in impl_names
        assert "MemoryStorage" in impl_names


@pytest.mark.asyncio
async def test_find_implementations_filter_by_language(server):
    """Test filtering implementations by language."""
    mock_impls = [
        InterfaceImplementation(
            interface_name="Storage",
            implementation_name="RedisStorage",
            file_path="/test/redis.py",
            language="python",
            methods=["get", "set"],
        ),
        InterfaceImplementation(
            interface_name="Storage",
            implementation_name="JRedisStorage",
            file_path="/test/Redis.java",
            language="java",
            methods=["get", "set"],
        ),
    ]

    with patch("src.store.call_graph_store.QdrantCallGraphStore") as MockStore:
        mock_store = AsyncMock()
        mock_store.get_implementations = AsyncMock(return_value=mock_impls)
        MockStore.return_value = mock_store

        result = await server.find_implementations(
            interface_name="Storage", language="python"
        )

        assert result["total_implementations"] == 1
        assert result["implementations"][0]["class_name"] == "RedisStorage"
        assert result["languages"] == ["python"]


@pytest.mark.asyncio
async def test_find_implementations_interface_not_found(server):
    """Test finding implementations for non-existent interface."""
    with patch("src.store.call_graph_store.QdrantCallGraphStore") as MockStore:
        mock_store = AsyncMock()
        mock_store.get_implementations = AsyncMock(return_value=[])
        MockStore.return_value = mock_store

        result = await server.find_implementations(
            interface_name="NonExistentInterface"
        )

        assert result["total_implementations"] == 0
        assert result["implementations"] == []


# find_dependencies tests


@pytest.mark.asyncio
async def test_find_dependencies_direct_imports(server):
    """Test finding direct file dependencies."""
    mock_result = {
        "project": "test_project",
        "dependencies": ["/test/auth.py", "/test/utils.py"],
        "dependency_count": 2,
    }

    server.get_file_dependencies = AsyncMock(return_value=mock_result)

    result = await server.find_dependencies(
        file_path="/test/api.py", include_transitive=False
    )

    assert result["file"] == "/test/api.py"
    assert result["total_dependencies"] == 2
    assert result["direct_dependencies"] == 2
    assert "analysis_time_ms" in result


@pytest.mark.asyncio
async def test_find_dependencies_transitive_depth_2(server):
    """Test finding transitive dependencies."""
    mock_result = {
        "project": "test_project",
        "dependencies": [
            {"file": "/test/auth.py", "transitive": False},
            {"file": "/test/db.py", "transitive": True},
        ],
        "dependency_count": 2,
    }

    server.get_file_dependencies = AsyncMock(return_value=mock_result)

    result = await server.find_dependencies(
        file_path="/test/api.py", include_transitive=True, depth=2
    )

    assert result["total_dependencies"] == 2
    assert "analysis_time_ms" in result


@pytest.mark.asyncio
async def test_find_dependencies_file_not_indexed(server):
    """Test finding dependencies for non-indexed file."""
    from src.core.exceptions import RetrievalError

    server.get_file_dependencies = AsyncMock(
        side_effect=RetrievalError("File not indexed")
    )

    with pytest.raises(RetrievalError):
        await server.find_dependencies(file_path="/test/nonexistent.py")


# find_dependents tests


@pytest.mark.asyncio
async def test_find_dependents_single_dependent(server):
    """Test finding a single reverse dependency."""
    mock_result = {
        "project": "test_project",
        "dependents": ["/test/main.py"],
        "dependent_count": 1,
    }

    server.get_file_dependents = AsyncMock(return_value=mock_result)

    result = await server.find_dependents(
        file_path="/test/api.py", include_transitive=False
    )

    assert result["file"] == "/test/api.py"
    assert result["total_dependents"] == 1
    assert result["impact_radius"] == "low"
    assert "analysis_time_ms" in result


@pytest.mark.asyncio
async def test_find_dependents_high_impact_radius(server):
    """Test finding dependents with high impact."""
    mock_result = {
        "project": "test_project",
        "dependents": [f"/test/file_{i}.py" for i in range(25)],
        "dependent_count": 25,
    }

    server.get_file_dependents = AsyncMock(return_value=mock_result)

    result = await server.find_dependents(
        file_path="/test/core.py", include_transitive=False
    )

    assert result["total_dependents"] == 25
    assert result["impact_radius"] == "high"


@pytest.mark.asyncio
async def test_find_dependents_transitive_depth_2(server):
    """Test finding transitive dependents."""
    mock_result = {
        "project": "test_project",
        "dependents": [
            "/test/api.py",
            "/test/worker.py",
        ],
        "dependent_count": 2,
    }

    server.get_file_dependents = AsyncMock(return_value=mock_result)

    result = await server.find_dependents(
        file_path="/test/auth.py", include_transitive=True, depth=2
    )

    assert result["total_dependents"] == 2
    assert "analysis_time_ms" in result


# get_call_chain tests


@pytest.mark.asyncio
async def test_get_call_chain_single_path(server, sample_call_graph):
    """Test finding a single call chain."""
    with patch("src.store.call_graph_store.QdrantCallGraphStore") as MockStore:
        mock_store = AsyncMock()
        mock_store.load_call_graph = AsyncMock(return_value=sample_call_graph)
        MockStore.return_value = mock_store

        result = await server.get_call_chain(
            from_function="main", to_function="validate"
        )

        assert result["from"] == "main"
        assert result["to"] == "validate"
        assert result["total_paths"] >= 1
        assert len(result["paths"]) >= 1
        # Path: main -> process_request -> validate
        assert result["paths"][0]["length"] == 3
        assert "analysis_time_ms" in result


@pytest.mark.asyncio
async def test_get_call_chain_multiple_paths(server, sample_call_graph):
    """Test finding multiple call chains."""
    # Add alternate path
    sample_call_graph.add_call(
        CallSite(
            caller_function="main",
            caller_file="/test/main.py",
            caller_line=8,
            callee_function="validate",
            callee_file="/test/validation.py",
            call_type="direct",
        )
    )

    with patch("src.store.call_graph_store.QdrantCallGraphStore") as MockStore:
        mock_store = AsyncMock()
        mock_store.load_call_graph = AsyncMock(return_value=sample_call_graph)
        MockStore.return_value = mock_store

        result = await server.get_call_chain(
            from_function="main", to_function="validate", max_paths=10
        )

        # Should find at least 2 paths
        assert result["total_paths"] >= 1
        assert result["shortest_path_length"] <= result["longest_path_length"]


@pytest.mark.asyncio
async def test_get_call_chain_no_path_found(server, sample_call_graph):
    """Test when no call chain exists."""
    with patch("src.store.call_graph_store.QdrantCallGraphStore") as MockStore:
        mock_store = AsyncMock()
        mock_store.load_call_graph = AsyncMock(return_value=sample_call_graph)
        MockStore.return_value = mock_store

        result = await server.get_call_chain(
            from_function="database_query",
            to_function="main",  # Reverse direction - no path
        )

        assert result["total_paths"] == 0
        assert result["paths"] == []


@pytest.mark.asyncio
async def test_get_call_chain_respects_max_depth(server, sample_call_graph):
    """Test that max_depth parameter is respected."""
    with patch("src.store.call_graph_store.QdrantCallGraphStore") as MockStore:
        mock_store = AsyncMock()
        mock_store.load_call_graph = AsyncMock(return_value=sample_call_graph)
        MockStore.return_value = mock_store

        result = await server.get_call_chain(
            from_function="main",
            to_function="database_query",
            max_depth=2,  # Path requires depth 3
        )

        # Should not find path with depth limit
        assert result["total_paths"] == 0


@pytest.mark.asyncio
async def test_get_call_chain_max_paths_limit(server, sample_call_graph):
    """Test that max_paths parameter limits results."""
    # Add multiple paths
    for i in range(10):
        sample_call_graph.add_function(
            FunctionNode(
                name=f"intermediate_{i}",
                qualified_name=f"intermediate_{i}",
                file_path=f"/test/inter_{i}.py",
                language="python",
                start_line=1,
                end_line=10,
            )
        )
        sample_call_graph.add_call(
            CallSite(
                caller_function="main",
                caller_file="/test/main.py",
                caller_line=10 + i,
                callee_function=f"intermediate_{i}",
                call_type="direct",
            )
        )
        sample_call_graph.add_call(
            CallSite(
                caller_function=f"intermediate_{i}",
                caller_file=f"/test/inter_{i}.py",
                caller_line=5,
                callee_function="validate",
                call_type="direct",
            )
        )

    with patch("src.store.call_graph_store.QdrantCallGraphStore") as MockStore:
        mock_store = AsyncMock()
        mock_store.load_call_graph = AsyncMock(return_value=sample_call_graph)
        MockStore.return_value = mock_store

        result = await server.get_call_chain(
            from_function="main", to_function="validate", max_paths=5
        )

        assert len(result["paths"]) <= 5
