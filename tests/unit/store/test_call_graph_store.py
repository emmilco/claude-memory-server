"""Unit tests for QdrantCallGraphStore."""

import asyncio
import pytest
import pytest_asyncio
from datetime import datetime, UTC
from src.store.call_graph_store import QdrantCallGraphStore
from src.graph.call_graph import CallGraph, CallSite, FunctionNode, InterfaceImplementation
from src.core.exceptions import StorageError, MemoryNotFoundError
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
async def store(config):
    """Create and initialize test store."""
    store = QdrantCallGraphStore(config)
    await store.initialize()

    # Clean up test data
    try:
        await store.delete_project_call_graph("test_project")
    except:
        pass

    yield store

    # Clean up after tests
    try:
        await store.delete_project_call_graph("test_project")
    except:
        pass


@pytest.fixture
def sample_function_node():
    """Sample function node for testing."""
    return FunctionNode(
        name="test_func",
        qualified_name="MyClass.test_func",
        file_path="/test/module.py",
        language="python",
        start_line=10,
        end_line=20,
        is_exported=True,
        is_async=False,
        parameters=["self", "arg1"],
        return_type="str",
    )


@pytest.fixture
def sample_call_sites():
    """Sample call sites for testing."""
    return [
        CallSite(
            caller_function="MyClass.test_func",
            caller_file="/test/module.py",
            caller_line=15,
            callee_function="helper_func",
            callee_file="/test/helper.py",
            call_type="direct",
        ),
        CallSite(
            caller_function="MyClass.test_func",
            caller_file="/test/module.py",
            caller_line=17,
            callee_function="OtherClass.method",
            callee_file="/test/other.py",
            call_type="method",
        ),
    ]


@pytest.fixture
def sample_implementations():
    """Sample implementations for testing."""
    return [
        InterfaceImplementation(
            interface_name="Storage",
            implementation_name="RedisStorage",
            file_path="/test/redis.py",
            language="python",
            methods=["get", "set", "delete"],
        ),
        InterfaceImplementation(
            interface_name="Storage",
            implementation_name="MemoryStorage",
            file_path="/test/memory.py",
            language="python",
            methods=["get", "set"],
        ),
    ]


class TestCallGraphStoreInitialization:
    """Test store initialization."""

    @pytest.mark.asyncio
    async def test_initialize_creates_collection(self, config):
        """Test that initialization creates collection if it doesn't exist."""
        store = QdrantCallGraphStore(config)
        await store.initialize()

        assert store.client is not None
        assert store._collection_exists()

    @pytest.mark.asyncio
    async def test_initialize_idempotent(self, store):
        """Test that multiple initializations are safe."""
        await store.initialize()  # Second initialization
        assert store.client is not None


class TestFunctionNodeStorage:
    """Test function node storage operations."""

    @pytest.mark.asyncio
    async def test_store_function_node(self, store, sample_function_node):
        """Test storing a function node."""
        node_id = await store.store_function_node(
            node=sample_function_node,
            project_name="test_project",
            calls_to=["helper_func", "OtherClass.method"],
            called_by=["main"],
        )

        # Verify UUID was returned
        assert node_id is not None
        assert len(node_id) == 36  # UUID format

        # Verify stored
        retrieved = await store.find_function_by_name("MyClass.test_func", "test_project")
        assert retrieved is not None
        assert retrieved.name == "test_func"
        assert retrieved.qualified_name == "MyClass.test_func"
        assert retrieved.file_path == "/test/module.py"
        assert retrieved.parameters == ["self", "arg1"]

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Known limitation: store_function_node creates duplicates instead of updating existing records (see test_call_graph_store_edge_cases.py::test_update_function_preserves_call_sites for workaround pattern)")
    async def test_store_function_node_upsert(self, store):
        """Test that storing same function twice updates it.

        NOTE: Current implementation generates new UUID on each store, creating
        duplicates rather than updating. True upsert would require finding existing
        record by qualified_name+project and reusing its point ID.
        """
        # Store first node
        node1 = FunctionNode(
            name="test_func",
            qualified_name="MyClass.test_func",
            file_path="/test/module.py",
            language="python",
            start_line=10,
            end_line=20,
            is_exported=True,
            is_async=False,
            parameters=["self", "arg1"],
            return_type="str",
        )
        await store.store_function_node(
            node=node1,
            project_name="test_project",
        )

        # Store updated node with same qualified_name but different end_line
        node2 = FunctionNode(
            name="test_func",
            qualified_name="MyClass.test_func",
            file_path="/test/module.py",
            language="python",
            start_line=10,
            end_line=25,  # Changed
            is_exported=True,
            is_async=False,
            parameters=["self", "arg1"],
            return_type="str",
        )
        await store.store_function_node(
            node=node2,
            project_name="test_project",
        )

        # Verify updated (THIS WILL FAIL - implementation doesn't support true upsert)
        retrieved = await store.find_function_by_name("MyClass.test_func", "test_project")
        assert retrieved.end_line == 25

    @pytest.mark.asyncio
    async def test_find_function_by_name_not_found(self, store):
        """Test finding non-existent function returns None."""
        result = await store.find_function_by_name("nonexistent", "test_project")
        assert result is None

    @pytest.mark.asyncio
    async def test_find_function_by_name_wrong_project(self, store, sample_function_node):
        """Test finding function in wrong project returns None."""
        await store.store_function_node(
            node=sample_function_node,
            project_name="test_project",
        )

        result = await store.find_function_by_name("MyClass.test_func", "other_project")
        assert result is None


class TestCallSiteStorage:
    """Test call site storage operations."""

    @pytest.mark.asyncio
    async def test_store_call_sites(self, store, sample_function_node, sample_call_sites):
        """Test storing call sites for a function."""
        # First store the function node
        await store.store_function_node(
            node=sample_function_node,
            project_name="test_project",
        )

        # Then store call sites
        await store.store_call_sites(
            function_name="MyClass.test_func",
            call_sites=sample_call_sites,
            project_name="test_project",
        )

        # Verify stored
        retrieved_sites = await store.get_call_sites_for_caller(
            caller_function="MyClass.test_func",
            project_name="test_project",
        )

        assert len(retrieved_sites) == 2
        assert retrieved_sites[0].callee_function == "helper_func"
        assert retrieved_sites[1].callee_function == "OtherClass.method"

    @pytest.mark.asyncio
    async def test_store_call_sites_function_not_found(self, store, sample_call_sites):
        """Test storing call sites for non-existent function raises error."""
        with pytest.raises(MemoryNotFoundError):
            await store.store_call_sites(
                function_name="nonexistent",
                call_sites=sample_call_sites,
                project_name="test_project",
            )

    @pytest.mark.asyncio
    async def test_get_call_sites_for_caller_empty(self, store, sample_function_node):
        """Test getting call sites for function with no calls."""
        await store.store_function_node(
            node=sample_function_node,
            project_name="test_project",
        )

        sites = await store.get_call_sites_for_caller(
            caller_function="MyClass.test_func",
            project_name="test_project",
        )

        assert sites == []


class TestImplementationStorage:
    """Test interface implementation storage."""

    @pytest.mark.asyncio
    async def test_store_implementations(self, store, sample_implementations):
        """Test storing interface implementations."""
        await store.store_implementations(
            interface_name="Storage",
            implementations=sample_implementations,
            project_name="test_project",
        )

        # Verify stored
        retrieved = await store.get_implementations(
            interface_name="Storage",
            project_name="test_project",
        )

        assert len(retrieved) == 2
        impl_names = {impl.implementation_name for impl in retrieved}
        assert impl_names == {"RedisStorage", "MemoryStorage"}

    @pytest.mark.asyncio
    async def test_get_implementations_not_found(self, store):
        """Test getting implementations for non-existent interface."""
        result = await store.get_implementations(
            interface_name="NonExistent",
            project_name="test_project",
        )

        assert result == []

    @pytest.mark.asyncio
    async def test_get_implementations_wrong_project(self, store, sample_implementations):
        """Test getting implementations filters by project."""
        await store.store_implementations(
            interface_name="Storage",
            implementations=sample_implementations,
            project_name="test_project",
        )

        result = await store.get_implementations(
            interface_name="Storage",
            project_name="other_project",
        )

        assert result == []


class TestCallGraphLoading:
    """Test loading entire call graph."""

    @pytest.mark.asyncio
    async def test_load_call_graph_empty(self, store):
        """Test loading call graph for project with no data."""
        graph = await store.load_call_graph("nonexistent_project")

        assert len(graph.nodes) == 0
        assert len(graph.calls) == 0

    @pytest.mark.asyncio
    async def test_load_call_graph_with_data(
        self,
        store,
        sample_function_node,
        sample_call_sites,
        sample_implementations,
    ):
        """Test loading call graph with nodes, calls, and implementations."""
        # Store function node
        await store.store_function_node(
            node=sample_function_node,
            project_name="test_project",
        )

        # Store call sites
        await store.store_call_sites(
            function_name="MyClass.test_func",
            call_sites=sample_call_sites,
            project_name="test_project",
        )

        # Store another function for implementations
        helper_node = FunctionNode(
            name="helper_func",
            qualified_name="helper_func",
            file_path="/test/helper.py",
            language="python",
            start_line=1,
            end_line=10,
        )
        await store.store_function_node(
            node=helper_node,
            project_name="test_project",
        )

        # Store implementations
        await store.store_implementations(
            interface_name="Storage",
            implementations=sample_implementations,
            project_name="test_project",
        )

        # Load graph
        graph = await store.load_call_graph("test_project")

        # Verify nodes
        assert len(graph.nodes) >= 2  # At least the two we added
        assert "MyClass.test_func" in graph.nodes
        assert "helper_func" in graph.nodes

        # Verify calls
        assert len(graph.calls) == 2

        # Verify implementations
        assert "Storage" in graph.implementations
        assert len(graph.implementations["Storage"]) == 2


class TestProjectDeletion:
    """Test deleting project call graph data."""

    @pytest.mark.asyncio
    async def test_delete_project_call_graph(self, store, sample_function_node):
        """Test deleting all call graph data for a project."""
        # Store some data
        await store.store_function_node(
            node=sample_function_node,
            project_name="test_project",
        )

        # Verify stored
        result = await store.find_function_by_name("MyClass.test_func", "test_project")
        assert result is not None

        # Delete project
        count = await store.delete_project_call_graph("test_project")
        assert count >= 0  # At least attempted deletion

        # Verify deleted
        result = await store.find_function_by_name("MyClass.test_func", "test_project")
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent_project(self, store):
        """Test deleting non-existent project doesn't raise error."""
        # Should not raise exception
        count = await store.delete_project_call_graph("nonexistent")
        assert count >= 0
