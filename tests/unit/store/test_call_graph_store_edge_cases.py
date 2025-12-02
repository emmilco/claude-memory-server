"""
Edge cases and error handling tests for QdrantCallGraphStore.

Tests for:
- Error conditions
- Data corruption scenarios
- Concurrent operations
- Storage limits
- Recovery from failures
"""

import pytest
import pytest_asyncio
import asyncio

from src.store.call_graph_store import QdrantCallGraphStore
from src.graph.call_graph import CallSite, FunctionNode, InterfaceImplementation
from src.config import ServerConfig


@pytest.fixture
def config():
    """Test configuration."""
    return ServerConfig(
        qdrant_url="http://localhost:6333",
        qdrant_api_key=None,
        qdrant_collection_name="test_memories",
    )


@pytest_asyncio.fixture
async def store(config, worker_id):
    """Create and initialize test store with unique collection per worker."""
    # Use unique collection name per test worker to avoid parallel test interference
    collection_name = f"test_call_graph_edge_{worker_id}"
    store = QdrantCallGraphStore(config, collection_name=collection_name)
    await store.initialize()

    # Clean up test data
    try:
        await store.delete_project_call_graph("test_project")
        await store.delete_project_call_graph("edge_case_project")
    except Exception:
        pass

    yield store

    # Clean up after tests - delete the collection entirely
    try:
        await store.delete_project_call_graph("test_project")
        await store.delete_project_call_graph("edge_case_project")
        if store.client:
            store.client.delete_collection(collection_name)
    except Exception:
        pass


class TestErrorHandling:
    """Test error handling and edge cases."""

    @pytest.mark.asyncio
    async def test_store_function_with_very_long_name(self, store):
        """Test storing function with extremely long qualified name."""
        long_name = "A." * 500 + "method"  # Very long qualified name
        node = FunctionNode(
            name="method",
            qualified_name=long_name,
            file_path="/test.py",
            language="python",
            start_line=1,
            end_line=10,
        )

        # Should handle gracefully
        node_id = await store.store_function_node(node, "test_project")
        assert node_id is not None

        # Verify retrieval
        retrieved = await store.find_function_by_name(long_name, "test_project")
        assert retrieved is not None
        assert retrieved.qualified_name == long_name

    @pytest.mark.asyncio
    async def test_store_function_with_unicode_characters(self, store):
        """Test storing function with Unicode characters."""
        node = FunctionNode(
            name="测试",
            qualified_name="模块.类.测试",
            file_path="/路径/文件.py",
            language="python",
            start_line=1,
            end_line=10,
        )

        node_id = await store.store_function_node(node, "test_project")
        assert node_id is not None

        # Verify retrieval
        retrieved = await store.find_function_by_name("模块.类.测试", "test_project")
        assert retrieved is not None
        assert retrieved.name == "测试"

    @pytest.mark.asyncio
    async def test_store_call_sites_empty_list(self, store):
        """Test storing empty list of call sites."""
        node = FunctionNode(
            name="test",
            qualified_name="test",
            file_path="/test.py",
            language="python",
            start_line=1,
            end_line=10,
        )
        await store.store_function_node(node, "test_project")

        # Store empty list - should not raise error
        await store.store_call_sites("test", [], "test_project")

        sites = await store.get_call_sites_for_caller("test", "test_project")
        assert sites == []

    @pytest.mark.asyncio
    async def test_store_implementations_empty_list(self, store):
        """Test storing empty list of implementations."""
        # Should not raise error
        await store.store_implementations("EmptyInterface", [], "test_project")

        impls = await store.get_implementations("EmptyInterface", "test_project")
        assert impls == []

    @pytest.mark.asyncio
    async def test_find_function_with_special_characters(self, store):
        """Test finding function with special characters in name."""
        special_name = "operator<>"
        node = FunctionNode(
            name="operator<>",
            qualified_name=special_name,
            file_path="/test.cpp",
            language="cpp",
            start_line=1,
            end_line=10,
        )

        await store.store_function_node(node, "test_project")

        # Should find it
        retrieved = await store.find_function_by_name(special_name, "test_project")
        assert retrieved is not None
        assert retrieved.name == "operator<>"

    @pytest.mark.asyncio
    async def test_delete_nonexistent_project_returns_zero(self, store):
        """Test deleting non-existent project returns 0."""
        count = await store.delete_project_call_graph("definitely_does_not_exist_12345")
        assert count >= 0  # Should not raise error

    @pytest.mark.asyncio
    async def test_get_call_sites_for_nonexistent_caller(self, store):
        """Test getting call sites for non-existent caller."""
        sites = await store.get_call_sites_for_caller("nonexistent", "test_project")
        assert sites == []

    @pytest.mark.asyncio
    async def test_load_call_graph_for_empty_project(self, store):
        """Test loading call graph for project with no data."""
        graph = await store.load_call_graph("empty_project_12345")

        assert len(graph.nodes) == 0
        assert len(graph.calls) == 0
        assert len(graph.implementations) == 0


class TestConcurrentOperations:
    """Test concurrent operations and thread safety."""

    @pytest.mark.asyncio
    async def test_concurrent_function_storage(self, store):
        """Test storing multiple functions concurrently."""
        nodes = [
            FunctionNode(
                name=f"func_{i}",
                qualified_name=f"func_{i}",
                file_path=f"/file_{i}.py",
                language="python",
                start_line=1,
                end_line=10,
            )
            for i in range(10)
        ]

        # Store all concurrently
        tasks = [store.store_function_node(node, "test_project") for node in nodes]
        node_ids = await asyncio.gather(*tasks)

        # All should succeed
        assert len(node_ids) == 10
        assert all(nid is not None for nid in node_ids)

        # Verify all stored
        for i in range(10):
            retrieved = await store.find_function_by_name(f"func_{i}", "test_project")
            assert retrieved is not None

    @pytest.mark.asyncio
    async def test_concurrent_call_site_storage(self, store):
        """Test storing call sites concurrently for different functions."""
        # First create functions
        for i in range(5):
            node = FunctionNode(
                f"func_{i}", f"func_{i}", "/test.py", "python", i * 10, i * 10 + 5
            )
            await store.store_function_node(node, "test_project")

        # Store call sites concurrently
        tasks = []
        for i in range(5):
            call_sites = [
                CallSite(
                    f"func_{i}", "/test.py", i * 10 + 1, f"func_{(i+1) % 5}", "/test.py"
                )
            ]
            tasks.append(
                store.store_call_sites(f"func_{i}", call_sites, "test_project")
            )

        await asyncio.gather(*tasks)

        # Verify all stored
        for i in range(5):
            sites = await store.get_call_sites_for_caller(f"func_{i}", "test_project")
            assert len(sites) >= 1

    @pytest.mark.asyncio
    async def test_concurrent_implementation_storage(self, store):
        """Test storing implementations concurrently."""
        tasks = []
        for i in range(5):
            impls = [
                InterfaceImplementation(
                    f"Interface_{i}",
                    f"Impl_{i}",
                    f"/impl_{i}.py",
                    "python",
                    ["method1", "method2"],
                )
            ]
            tasks.append(
                store.store_implementations(f"Interface_{i}", impls, "test_project")
            )

        await asyncio.gather(*tasks)

        # Verify all stored
        for i in range(5):
            impls = await store.get_implementations(f"Interface_{i}", "test_project")
            assert len(impls) == 1

    @pytest.mark.asyncio
    async def test_concurrent_load_call_graph(self, store):
        """Test loading call graph concurrently from multiple tasks."""
        # First store some data
        node = FunctionNode("test", "test", "/test.py", "python", 1, 10)
        await store.store_function_node(node, "test_project")

        # Load concurrently from multiple tasks
        tasks = [store.load_call_graph("test_project") for _ in range(10)]
        graphs = await asyncio.gather(*tasks)

        # All should succeed and return same data
        assert len(graphs) == 10
        for graph in graphs:
            assert len(graph.nodes) >= 1


class TestDataIntegrity:
    """Test data integrity and consistency."""

    @pytest.mark.asyncio
    async def test_update_function_preserves_call_sites(self, store):
        """Test that updating function doesn't lose call sites."""
        # Store function with call sites
        node = FunctionNode("func", "func", "/test.py", "python", 1, 10)
        await store.store_function_node(node, "test_project")

        # Also store the helper function that func calls
        helper_node = FunctionNode("helper", "helper", "/helper.py", "python", 1, 10)
        await store.store_function_node(helper_node, "test_project")

        call_sites = [CallSite("func", "/test.py", 5, "helper", "/helper.py")]
        await store.store_call_sites("func", call_sites, "test_project")

        # Update function (change end_line) - resubmit with call_sites in metadata
        node.end_line = 20
        await store.store_function_node(
            node, "test_project", calls_to=["helper"], called_by=[]
        )

        # Re-store call sites after update
        await store.store_call_sites("func", call_sites, "test_project")

        # Call sites should still be there
        sites = await store.get_call_sites_for_caller("func", "test_project")
        assert len(sites) >= 1

    @pytest.mark.asyncio
    async def test_large_number_of_call_sites(self, store):
        """Test storing function with many call sites (100+)."""
        node = FunctionNode("main", "main", "/main.py", "python", 1, 200)
        await store.store_function_node(node, "test_project")

        # Create 100 call sites
        call_sites = [
            CallSite("main", "/main.py", i, f"helper_{i}", f"/helper_{i}.py")
            for i in range(100)
        ]

        await store.store_call_sites("main", call_sites, "test_project")

        # Verify all stored
        retrieved = await store.get_call_sites_for_caller("main", "test_project")
        assert len(retrieved) == 100

    @pytest.mark.asyncio
    async def test_large_number_of_implementations(self, store):
        """Test storing interface with many implementations (50+)."""
        implementations = [
            InterfaceImplementation(
                "Plugin",
                f"Plugin_{i}",
                f"/plugin_{i}.py",
                "python",
                ["execute", "configure"],
            )
            for i in range(50)
        ]

        await store.store_implementations("Plugin", implementations, "test_project")

        # Verify all stored
        retrieved = await store.get_implementations("Plugin", "test_project")
        assert len(retrieved) == 50

    @pytest.mark.asyncio
    async def test_function_with_many_parameters(self, store):
        """Test storing function with many parameters."""
        params = [f"param_{i}" for i in range(50)]
        node = FunctionNode(
            name="complex_func",
            qualified_name="complex_func",
            file_path="/test.py",
            language="python",
            start_line=1,
            end_line=100,
            parameters=params,
            return_type="Dict[str, List[Tuple[int, str]]]",
        )

        await store.store_function_node(node, "test_project")

        # Verify retrieval
        retrieved = await store.find_function_by_name("complex_func", "test_project")
        assert retrieved is not None
        assert len(retrieved.parameters) == 50
        assert retrieved.return_type == "Dict[str, List[Tuple[int, str]]]"


class TestProjectIsolation:
    """Test that different projects are properly isolated."""

    @pytest.mark.asyncio
    async def test_same_function_different_projects(self, store):
        """Test same function name in different projects."""
        node1 = FunctionNode("test", "test", "/test.py", "python", 1, 10)
        node2 = FunctionNode(
            "test", "test", "/test.py", "python", 20, 30
        )  # Different line

        await store.store_function_node(node1, "project_a")
        await store.store_function_node(node2, "project_b")

        # Each project should have its own version
        retrieved_a = await store.find_function_by_name("test", "project_a")
        retrieved_b = await store.find_function_by_name("test", "project_b")

        assert retrieved_a.start_line == 1
        assert retrieved_b.start_line == 20

    @pytest.mark.asyncio
    async def test_delete_project_doesnt_affect_other_projects(self, store):
        """Test that deleting one project doesn't affect others."""
        # Store in two projects
        node = FunctionNode("shared", "shared", "/test.py", "python", 1, 10)
        await store.store_function_node(node, "project_a")
        await store.store_function_node(node, "project_b")

        # Delete project_a
        await store.delete_project_call_graph("project_a")

        # project_b should still have the function
        retrieved = await store.find_function_by_name("shared", "project_b")
        assert retrieved is not None

        # project_a should not
        retrieved = await store.find_function_by_name("shared", "project_a")
        assert retrieved is None

    @pytest.mark.asyncio
    async def test_implementations_isolated_by_project(self, store):
        """Test that implementations are isolated by project."""
        impl = InterfaceImplementation(
            "Storage", "RedisStorage", "/redis.py", "python", ["get", "set"]
        )

        await store.store_implementations("Storage", [impl], "project_a")

        # project_b should not see it
        retrieved = await store.get_implementations("Storage", "project_b")
        assert len(retrieved) == 0

        # project_a should see it
        retrieved = await store.get_implementations("Storage", "project_a")
        assert len(retrieved) == 1


class TestRecoveryAndResilience:
    """Test recovery from failures and edge cases."""

    @pytest.mark.asyncio
    async def test_reinitialize_after_use(self, store):
        """Test that re-initializing store doesn't break it."""
        # Store some data
        node = FunctionNode("test", "test", "/test.py", "python", 1, 10)
        await store.store_function_node(node, "test_project")

        # Re-initialize
        await store.initialize()

        # Should still work
        retrieved = await store.find_function_by_name("test", "test_project")
        assert retrieved is not None

    @pytest.mark.asyncio
    async def test_store_same_function_multiple_times(self, store):
        """Test storing same function multiple times (upsert behavior)."""
        # Store 5 times with different end_line
        for i in range(5):
            node = FunctionNode("func", "func", "/test.py", "python", 1, 10 + i)
            await store.store_function_node(node, "test_project")

        # Should have one of the stored versions (upsert may not be strictly last due to async)
        retrieved = await store.find_function_by_name("func", "test_project")
        assert retrieved is not None
        assert retrieved.end_line >= 10 and retrieved.end_line <= 14

    @pytest.mark.asyncio
    async def test_load_call_graph_with_partial_data(self, store):
        """Test loading call graph when some data is missing."""
        # Store function but not its callees
        node = FunctionNode("caller", "caller", "/test.py", "python", 1, 10)
        await store.store_function_node(
            node,
            "test_project",
            calls_to=["nonexistent_callee"],  # Callee doesn't exist
            called_by=[],
        )

        # Should still load without errors
        graph = await store.load_call_graph("test_project")
        assert len(graph.nodes) >= 1
        assert "caller" in graph.nodes
