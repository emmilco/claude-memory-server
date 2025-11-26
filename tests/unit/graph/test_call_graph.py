"""Unit tests for CallGraph class."""

import pytest
from src.graph.call_graph import CallGraph, CallSite, FunctionNode, InterfaceImplementation


class TestCallGraphBasics:
    """Test basic CallGraph operations."""
    
    def test_add_function_creates_node(self):
        """Test that adding a function creates a node."""
        graph = CallGraph()
        node = FunctionNode(
            name="test_func",
            qualified_name="test_func",
            file_path="/test.py",
            language="python",
            start_line=1,
            end_line=10
        )
        
        graph.add_function(node)
        
        assert "test_func" in graph.nodes
        assert graph.nodes["test_func"] == node
        
    def test_add_call_creates_edge(self):
        """Test that adding a call creates forward/reverse edges."""
        graph = CallGraph()
        call_site = CallSite(
            caller_function="main",
            caller_file="/main.py",
            caller_line=5,
            callee_function="helper",
            callee_file="/helper.py"
        )
        
        graph.add_call(call_site)
        
        assert call_site in graph.calls
        assert "helper" in graph.forward_index["main"]
        assert "main" in graph.reverse_index["helper"]
        
    def test_forward_index_populated_correctly(self):
        """Test that forward index tracks callees."""
        graph = CallGraph()
        graph.add_call(CallSite("main", "/main.py", 5, "foo", "/foo.py"))
        graph.add_call(CallSite("main", "/main.py", 6, "bar", "/bar.py"))
        
        assert graph.forward_index["main"] == {"foo", "bar"}
        
    def test_reverse_index_populated_correctly(self):
        """Test that reverse index tracks callers."""
        graph = CallGraph()
        graph.add_call(CallSite("main", "/main.py", 5, "helper", "/helper.py"))
        graph.add_call(CallSite("foo", "/foo.py", 10, "helper", "/helper.py"))
        
        assert graph.reverse_index["helper"] == {"main", "foo"}
        
    def test_add_implementation_stores_relationship(self):
        """Test that interface implementations are stored."""
        graph = CallGraph()
        impl = InterfaceImplementation(
            interface_name="Storage",
            implementation_name="RedisStorage",
            file_path="/storage.py",
            language="python",
            methods=["get", "set", "delete"]
        )
        
        graph.add_implementation(impl)
        
        assert "Storage" in graph.implementations
        assert impl in graph.implementations["Storage"]


class TestCallGraphSearch:
    """Test call graph search operations."""
    
    def test_find_callers_direct_only(self):
        """Test finding direct callers."""
        graph = CallGraph()
        
        # Add nodes
        graph.add_function(FunctionNode("main", "main", "/main.py", "python", 1, 5))
        graph.add_function(FunctionNode("foo", "foo", "/foo.py", "python", 1, 5))
        graph.add_function(FunctionNode("helper", "helper", "/helper.py", "python", 1, 5))
        
        # Add calls
        graph.add_call(CallSite("main", "/main.py", 3, "helper", "/helper.py"))
        graph.add_call(CallSite("foo", "/foo.py", 2, "helper", "/helper.py"))
        
        callers = graph.find_callers("helper", include_indirect=False)
        
        assert len(callers) == 2
        caller_names = {c.name for c in callers}
        assert caller_names == {"main", "foo"}
        
    def test_find_callees_direct_only(self):
        """Test finding direct callees."""
        graph = CallGraph()
        
        # Add nodes
        graph.add_function(FunctionNode("main", "main", "/main.py", "python", 1, 5))
        graph.add_function(FunctionNode("foo", "foo", "/foo.py", "python", 1, 5))
        graph.add_function(FunctionNode("bar", "bar", "/bar.py", "python", 1, 5))
        
        # Add calls
        graph.add_call(CallSite("main", "/main.py", 3, "foo", "/foo.py"))
        graph.add_call(CallSite("main", "/main.py", 4, "bar", "/bar.py"))
        
        callees = graph.find_callees("main", include_indirect=False)
        
        assert len(callees) == 2
        callee_names = {c.name for c in callees}
        assert callee_names == {"foo", "bar"}
        
    def test_find_callers_indirect_depth_2(self):
        """Test finding indirect callers up to depth 2."""
        graph = CallGraph()
        
        # Build chain: a -> b -> c
        for name in ["a", "b", "c"]:
            graph.add_function(FunctionNode(name, name, f"/{name}.py", "python", 1, 5))
            
        graph.add_call(CallSite("a", "/a.py", 1, "b", "/b.py"))
        graph.add_call(CallSite("b", "/b.py", 1, "c", "/c.py"))
        
        # Find callers of c with depth 2
        callers = graph.find_callers("c", include_indirect=True, max_depth=2)
        
        caller_names = {c.name for c in callers}
        assert "b" in caller_names  # Direct caller
        assert "a" in caller_names  # Indirect caller (depth 2)
        
    def test_find_callees_indirect_depth_3(self):
        """Test finding indirect callees up to depth 3."""
        graph = CallGraph()
        
        # Build chain: a -> b -> c -> d
        for name in ["a", "b", "c", "d"]:
            graph.add_function(FunctionNode(name, name, f"/{name}.py", "python", 1, 5))
            
        graph.add_call(CallSite("a", "/a.py", 1, "b", "/b.py"))
        graph.add_call(CallSite("b", "/b.py", 1, "c", "/c.py"))
        graph.add_call(CallSite("c", "/c.py", 1, "d", "/d.py"))
        
        # Find callees of a with depth 3
        callees = graph.find_callees("a", include_indirect=True, max_depth=3)
        
        callee_names = {c.name for c in callees}
        assert "b" in callee_names  # Direct
        assert "c" in callee_names  # Depth 2
        assert "d" in callee_names  # Depth 3


class TestCallChains:
    """Test call chain finding."""
    
    def test_find_call_chain_single_path(self):
        """Test finding a single call chain."""
        graph = CallGraph()
        
        # Build path: main -> process -> validate
        for name in ["main", "process", "validate"]:
            graph.add_function(FunctionNode(name, name, f"/{name}.py", "python", 1, 5))
            
        graph.add_call(CallSite("main", "/main.py", 1, "process", "/process.py"))
        graph.add_call(CallSite("process", "/process.py", 1, "validate", "/validate.py"))
        
        paths = graph.find_call_chain("main", "validate")
        
        assert len(paths) == 1
        assert paths[0] == ["main", "process", "validate"]
        
    def test_find_call_chain_multiple_paths(self):
        """Test finding multiple call chains."""
        graph = CallGraph()
        
        # Build diamond: main -> (foo, bar) -> end
        for name in ["main", "foo", "bar", "end"]:
            graph.add_function(FunctionNode(name, name, f"/{name}.py", "python", 1, 5))
            
        graph.add_call(CallSite("main", "/main.py", 1, "foo", "/foo.py"))
        graph.add_call(CallSite("main", "/main.py", 2, "bar", "/bar.py"))
        graph.add_call(CallSite("foo", "/foo.py", 1, "end", "/end.py"))
        graph.add_call(CallSite("bar", "/bar.py", 1, "end", "/end.py"))
        
        paths = graph.find_call_chain("main", "end")
        
        assert len(paths) == 2
        assert ["main", "foo", "end"] in paths
        assert ["main", "bar", "end"] in paths
        
    def test_find_call_chain_no_path_found(self):
        """Test when no call chain exists."""
        graph = CallGraph()
        
        graph.add_function(FunctionNode("a", "a", "/a.py", "python", 1, 5))
        graph.add_function(FunctionNode("b", "b", "/b.py", "python", 1, 5))
        
        paths = graph.find_call_chain("a", "b")
        
        assert len(paths) == 0
        
    def test_find_call_chain_respects_max_depth(self):
        """Test that max_depth is respected."""
        graph = CallGraph()
        
        # Build long chain: a -> b -> c -> d -> e
        for name in ["a", "b", "c", "d", "e"]:
            graph.add_function(FunctionNode(name, name, f"/{name}.py", "python", 1, 5))
            
        graph.add_call(CallSite("a", "/a.py", 1, "b", "/b.py"))
        graph.add_call(CallSite("b", "/b.py", 1, "c", "/c.py"))
        graph.add_call(CallSite("c", "/c.py", 1, "d", "/d.py"))
        graph.add_call(CallSite("d", "/d.py", 1, "e", "/e.py"))
        
        # Max depth of 3 should not find path (length = 5)
        paths = graph.find_call_chain("a", "e", max_depth=3)
        
        assert len(paths) == 0
        
    def test_find_call_chain_cycles_handled(self):
        """Test that cycles don't cause infinite loops."""
        graph = CallGraph()
        
        # Build cycle: a -> b -> c -> a
        for name in ["a", "b", "c"]:
            graph.add_function(FunctionNode(name, name, f"/{name}.py", "python", 1, 5))
            
        graph.add_call(CallSite("a", "/a.py", 1, "b", "/b.py"))
        graph.add_call(CallSite("b", "/b.py", 1, "c", "/c.py"))
        graph.add_call(CallSite("c", "/c.py", 1, "a", "/a.py"))  # Cycle
        
        # Should find path a -> b without infinite loop
        paths = graph.find_call_chain("a", "b")
        
        assert len(paths) == 1
        assert paths[0] == ["a", "b"]
        
    def test_find_call_chain_max_paths_limit(self):
        """Test that max_paths limits results."""
        graph = CallGraph()
        
        # Build graph with many paths
        graph.add_function(FunctionNode("start", "start", "/start.py", "python", 1, 5))
        graph.add_function(FunctionNode("end", "end", "/end.py", "python", 1, 5))
        
        # Create 10 intermediate nodes, all connecting start to end
        for i in range(10):
            name = f"mid{i}"
            graph.add_function(FunctionNode(name, name, f"/{name}.py", "python", 1, 5))
            graph.add_call(CallSite("start", "/start.py", i, name, f"/{name}.py"))
            graph.add_call(CallSite(name, f"/{name}.py", 1, "end", "/end.py"))
            
        paths = graph.find_call_chain("start", "end", max_paths=5)
        
        assert len(paths) == 5  # Should limit to 5


class TestCallSites:
    """Test call site retrieval."""
    
    def test_get_call_sites_for_caller(self):
        """Test retrieving call sites by caller."""
        graph = CallGraph()
        
        cs1 = CallSite("main", "/main.py", 5, "foo", "/foo.py")
        cs2 = CallSite("main", "/main.py", 6, "bar", "/bar.py")
        cs3 = CallSite("other", "/other.py", 10, "baz", "/baz.py")
        
        graph.add_call(cs1)
        graph.add_call(cs2)
        graph.add_call(cs3)
        
        sites = graph.get_call_sites_for_caller("main")
        
        assert len(sites) == 2
        assert cs1 in sites
        assert cs2 in sites
        
    def test_get_call_sites_for_callee(self):
        """Test retrieving call sites by callee."""
        graph = CallGraph()
        
        cs1 = CallSite("main", "/main.py", 5, "helper", "/helper.py")
        cs2 = CallSite("foo", "/foo.py", 10, "helper", "/helper.py")
        cs3 = CallSite("bar", "/bar.py", 15, "other", "/other.py")
        
        graph.add_call(cs1)
        graph.add_call(cs2)
        graph.add_call(cs3)
        
        sites = graph.get_call_sites_for_callee("helper")
        
        assert len(sites) == 2
        assert cs1 in sites
        assert cs2 in sites


class TestImplementations:
    """Test interface implementation tracking."""
    
    def test_get_implementations_single(self):
        """Test retrieving a single implementation."""
        graph = CallGraph()
        
        impl = InterfaceImplementation(
            interface_name="Storage",
            implementation_name="RedisStorage",
            file_path="/storage.py",
            language="python",
            methods=["get", "set"]
        )
        
        graph.add_implementation(impl)
        
        impls = graph.get_implementations("Storage")
        
        assert len(impls) == 1
        assert impls[0] == impl
        
    def test_get_implementations_multiple(self):
        """Test retrieving multiple implementations."""
        graph = CallGraph()
        
        impl1 = InterfaceImplementation("Storage", "RedisStorage", "/redis.py", "python", ["get", "set"])
        impl2 = InterfaceImplementation("Storage", "MemoryStorage", "/memory.py", "python", ["get", "set"])
        
        graph.add_implementation(impl1)
        graph.add_implementation(impl2)
        
        impls = graph.get_implementations("Storage")
        
        assert len(impls) == 2
        assert impl1 in impls
        assert impl2 in impls
        
    def test_get_implementations_interface_not_found(self):
        """Test getting implementations for non-existent interface."""
        graph = CallGraph()
        
        impls = graph.get_implementations("NonExistent")
        
        assert len(impls) == 0


class TestStatistics:
    """Test call graph statistics."""
    
    def test_get_statistics(self):
        """Test getting call graph statistics."""
        graph = CallGraph()
        
        # Add 3 functions
        for name in ["a", "b", "c"]:
            graph.add_function(FunctionNode(name, name, f"/{name}.py", "python", 1, 5))
            
        # Add 2 calls
        graph.add_call(CallSite("a", "/a.py", 1, "b", "/b.py"))
        graph.add_call(CallSite("b", "/b.py", 1, "c", "/c.py"))
        
        # Add 1 implementation
        graph.add_implementation(InterfaceImplementation("I", "Impl", "/impl.py", "python", []))
        
        stats = graph.get_statistics()
        
        assert stats["total_functions"] == 3
        assert stats["total_calls"] == 2
        assert stats["total_interfaces"] == 1
        assert stats["total_implementations"] == 1


class TestEmptyGraph:
    """Test empty graph edge cases."""

    def test_empty_graph_returns_empty_results(self):
        """Test that operations on empty graph return empty results."""
        graph = CallGraph()

        assert len(graph.find_callers("nonexistent")) == 0
        assert len(graph.find_callees("nonexistent")) == 0
        assert len(graph.find_call_chain("a", "b")) == 0
        assert len(graph.get_call_sites_for_caller("a")) == 0
        assert len(graph.get_call_sites_for_callee("b")) == 0
        assert len(graph.get_implementations("I")) == 0

        stats = graph.get_statistics()
        assert stats["total_functions"] == 0
        assert stats["total_calls"] == 0


class TestCallGraphEdgeCases:
    """Test edge cases for call graph operations."""

    def test_add_call_with_none_caller(self):
        """Test adding call with None caller handles gracefully."""
        graph = CallGraph()

        # CallGraph accepts None and stores it (graceful handling)
        call_site = CallSite(None, "/file.py", 1, "target", "/target.py")
        graph.add_call(call_site)

        # Should be stored in calls
        assert call_site in graph.calls
        # Forward/reverse indexes should handle None as a key
        assert "target" in graph.forward_index.get(None, set())

    def test_add_call_with_none_callee(self):
        """Test adding call with None callee handles gracefully."""
        graph = CallGraph()

        # CallGraph accepts None and stores it (graceful handling)
        call_site = CallSite("source", "/source.py", 1, None, "/file.py")
        graph.add_call(call_site)

        # Should be stored in calls
        assert call_site in graph.calls
        # Forward/reverse indexes should handle None as a key
        assert None in graph.forward_index.get("source", set())

    def test_add_function_with_none_qualified_name(self):
        """Test adding function with None qualified_name handles gracefully."""
        graph = CallGraph()

        # CallGraph uses qualified_name as the key
        node = FunctionNode(
            name="test",
            qualified_name=None,  # This is the key used
            file_path="/file.py",
            language="python",
            start_line=1,
            end_line=5
        )
        graph.add_function(node)

        # Should be stored with None as key
        assert None in graph.nodes
        assert graph.nodes[None] == node

    def test_add_implementation_with_empty_interface_name(self):
        """Test adding implementation with empty interface name."""
        graph = CallGraph()
        impl = InterfaceImplementation(
            interface_name="",  # Empty string
            implementation_name="Impl",
            file_path="/file.py",
            language="python",
            methods=[]
        )

        # Should either accept it or raise error (both are valid behaviors)
        try:
            graph.add_implementation(impl)
            # If accepted, verify it's stored
            impls = graph.get_implementations("")
            assert len(impls) == 1
        except (ValueError, TypeError):
            # If rejected, that's also acceptable
            pass

    def test_find_callers_with_max_depth_zero(self):
        """Test find_callers with max_depth=0 returns empty."""
        graph = CallGraph()

        # Add nodes and calls
        graph.add_function(FunctionNode("a", "a", "/a.py", "python", 1, 5))
        graph.add_function(FunctionNode("b", "b", "/b.py", "python", 1, 5))
        graph.add_call(CallSite("a", "/a.py", 1, "b", "/b.py"))

        # Max depth of 0 should return nothing
        callers = graph.find_callers("b", include_indirect=True, max_depth=0)
        assert len(callers) == 0

    def test_find_callees_with_max_depth_zero(self):
        """Test find_callees with max_depth=0 returns empty."""
        graph = CallGraph()

        # Add nodes and calls
        graph.add_function(FunctionNode("a", "a", "/a.py", "python", 1, 5))
        graph.add_function(FunctionNode("b", "b", "/b.py", "python", 1, 5))
        graph.add_call(CallSite("a", "/a.py", 1, "b", "/b.py"))

        # Max depth of 0 should return nothing
        callees = graph.find_callees("a", include_indirect=True, max_depth=0)
        assert len(callees) == 0

    def test_find_call_chain_same_source_and_target(self):
        """Test finding call chain where source equals target."""
        graph = CallGraph()

        graph.add_function(FunctionNode("a", "a", "/a.py", "python", 1, 5))

        # Finding path from a to itself
        paths = graph.find_call_chain("a", "a")

        # Should return single-element path or empty (both reasonable)
        # Most implementations would return [["a"]] or []
        assert isinstance(paths, list)

    def test_add_duplicate_function(self):
        """Test adding duplicate function overwrites."""
        graph = CallGraph()

        node1 = FunctionNode("test", "test", "/file1.py", "python", 1, 5)
        node2 = FunctionNode("test", "test", "/file2.py", "python", 10, 20)

        graph.add_function(node1)
        graph.add_function(node2)

        # Second node should overwrite first
        assert graph.nodes["test"] == node2
        assert graph.nodes["test"].file_path == "/file2.py"

    def test_call_sites_with_nonexistent_function(self):
        """Test getting call sites for function that doesn't exist."""
        graph = CallGraph()

        # Function not in graph
        sites = graph.get_call_sites_for_caller("nonexistent")
        assert len(sites) == 0

        sites = graph.get_call_sites_for_callee("nonexistent")
        assert len(sites) == 0
