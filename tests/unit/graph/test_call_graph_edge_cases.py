"""
Edge case and stress tests for CallGraph.

Comprehensive testing for:
- Edge cases (empty, None, invalid)
- Performance (large graphs, deep chains)
- Complex scenarios (diamonds, cycles, large fanout)
- Boundary conditions
"""

from src.graph.call_graph import (
    CallGraph,
    CallSite,
    FunctionNode,
    InterfaceImplementation,
)


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_add_function_with_none_name(self):
        """Test that adding function with None name stores it (Python allows None as dict key)."""
        graph = CallGraph()
        node = FunctionNode(
            name=None,  # Unusual but valid
            qualified_name=None,
            file_path="/test.py",
            language="python",
            start_line=1,
            end_line=5,
        )
        graph.add_function(node)
        assert None in graph.nodes

    def test_add_function_with_empty_name(self):
        """Test adding function with empty name."""
        graph = CallGraph()
        node = FunctionNode(
            name="",
            qualified_name="",
            file_path="/test.py",
            language="python",
            start_line=1,
            end_line=5,
        )
        graph.add_function(node)
        assert "" in graph.nodes

    def test_add_duplicate_function_overwrites(self):
        """Test that adding duplicate function overwrites previous."""
        graph = CallGraph()
        node1 = FunctionNode("func", "func", "/test.py", "python", 1, 10)
        node2 = FunctionNode(
            "func", "func", "/test.py", "python", 1, 20
        )  # Different end_line

        graph.add_function(node1)
        graph.add_function(node2)

        assert graph.nodes["func"].end_line == 20

    def test_find_callers_nonexistent_function(self):
        """Test finding callers for non-existent function."""
        graph = CallGraph()
        callers = graph.find_callers("nonexistent")
        assert len(callers) == 0

    def test_find_callees_nonexistent_function(self):
        """Test finding callees for non-existent function."""
        graph = CallGraph()
        callees = graph.find_callees("nonexistent")
        assert len(callees) == 0

    def test_negative_line_numbers(self):
        """Test handling of negative line numbers."""
        graph = CallGraph()
        node = FunctionNode(
            name="test",
            qualified_name="test",
            file_path="/test.py",
            language="python",
            start_line=-1,
            end_line=-1,
        )
        graph.add_function(node)
        assert graph.nodes["test"].start_line == -1

    def test_very_long_qualified_name(self):
        """Test handling of very long qualified names."""
        graph = CallGraph()
        long_name = "Module." + ".".join([f"Class{i}" for i in range(100)]) + ".method"
        node = FunctionNode(
            name="method",
            qualified_name=long_name,
            file_path="/test.py",
            language="python",
            start_line=1,
            end_line=5,
        )
        graph.add_function(node)
        assert long_name in graph.nodes

    def test_unicode_function_names(self):
        """Test handling of Unicode function names."""
        graph = CallGraph()
        node = FunctionNode(
            name="测试函数",
            qualified_name="模块.测试函数",
            file_path="/test.py",
            language="python",
            start_line=1,
            end_line=5,
        )
        graph.add_function(node)
        assert "模块.测试函数" in graph.nodes

    def test_special_characters_in_file_path(self):
        """Test handling of special characters in file paths."""
        graph = CallGraph()
        special_path = "/path/with spaces/and-dashes/file@2.0.py"
        node = FunctionNode(
            name="test",
            qualified_name="test",
            file_path=special_path,
            language="python",
            start_line=1,
            end_line=5,
        )
        graph.add_function(node)
        assert graph.nodes["test"].file_path == special_path

    def test_zero_depth_find_callers(self):
        """Test find_callers with max_depth=0."""
        graph = CallGraph()

        for name in ["a", "b"]:
            graph.add_function(FunctionNode(name, name, f"/{name}.py", "python", 1, 5))

        graph.add_call(CallSite("a", "/a.py", 1, "b", "/b.py"))

        # Depth 0 should return empty
        callers = graph.find_callers("b", include_indirect=True, max_depth=0)
        assert len(callers) == 0


class TestPerformance:
    """Performance and stress tests."""

    def test_large_graph_with_1000_nodes(self):
        """Test performance with 1000 function nodes."""
        graph = CallGraph()

        # Add 1000 functions
        for i in range(1000):
            node = FunctionNode(
                name=f"func_{i}",
                qualified_name=f"func_{i}",
                file_path=f"/file_{i // 100}.py",
                language="python",
                start_line=i,
                end_line=i + 10,
            )
            graph.add_function(node)

        assert len(graph.nodes) == 1000
        stats = graph.get_statistics()
        assert stats["total_functions"] == 1000

    def test_deep_call_chain_100_levels(self):
        """Test very deep call chain (100 levels)."""
        graph = CallGraph()

        # Build chain: func_0 -> func_1 -> ... -> func_99
        for i in range(100):
            graph.add_function(
                FunctionNode(f"func_{i}", f"func_{i}", "/test.py", "python", i, i + 1)
            )

        for i in range(99):
            graph.add_call(
                CallSite(f"func_{i}", "/test.py", i, f"func_{i+1}", "/test.py")
            )

        # Find call chain from start to end
        paths = graph.find_call_chain("func_0", "func_99", max_depth=100)

        assert len(paths) >= 1
        if paths:
            assert len(paths[0]) == 100

    def test_wide_fanout_100_callees(self):
        """Test function calling 100 different functions."""
        graph = CallGraph()

        # Main function
        graph.add_function(FunctionNode("main", "main", "/main.py", "python", 1, 200))

        # 100 helper functions
        for i in range(100):
            graph.add_function(
                FunctionNode(
                    f"helper_{i}", f"helper_{i}", f"/helper_{i}.py", "python", 1, 10
                )
            )
            graph.add_call(
                CallSite("main", "/main.py", i + 10, f"helper_{i}", f"/helper_{i}.py")
            )

        callees = graph.find_callees("main", include_indirect=False)
        assert len(callees) == 100

    def test_many_callers_100_functions(self):
        """Test function called by 100 different functions."""
        graph = CallGraph()

        # Shared utility function
        graph.add_function(
            FunctionNode("utility", "utility", "/util.py", "python", 1, 10)
        )

        # 100 callers
        for i in range(100):
            graph.add_function(
                FunctionNode(
                    f"caller_{i}", f"caller_{i}", f"/caller_{i}.py", "python", 1, 20
                )
            )
            graph.add_call(
                CallSite(f"caller_{i}", f"/caller_{i}.py", 10, "utility", "/util.py")
            )

        callers = graph.find_callers("utility", include_indirect=False)
        assert len(callers) == 100

    def test_find_call_chain_with_many_paths(self):
        """Test finding call chains when many paths exist."""
        graph = CallGraph()

        # Create start and end
        graph.add_function(FunctionNode("start", "start", "/start.py", "python", 1, 5))
        graph.add_function(FunctionNode("end", "end", "/end.py", "python", 1, 5))

        # Create 50 intermediate nodes, each providing a path
        for i in range(50):
            mid_name = f"mid_{i}"
            graph.add_function(
                FunctionNode(mid_name, mid_name, f"/{mid_name}.py", "python", 1, 5)
            )
            graph.add_call(
                CallSite("start", "/start.py", i, mid_name, f"/{mid_name}.py")
            )
            graph.add_call(CallSite(mid_name, f"/{mid_name}.py", 1, "end", "/end.py"))

        # Find limited number of paths
        paths = graph.find_call_chain("start", "end", max_paths=10)

        assert len(paths) == 10  # Should respect max_paths

    def test_complex_graph_statistics(self):
        """Test statistics on complex graph."""
        graph = CallGraph()

        # Add 50 functions
        for i in range(50):
            graph.add_function(
                FunctionNode(f"f{i}", f"f{i}", "/test.py", "python", i, i + 1)
            )

        # Add 200 calls (random connections)
        for i in range(200):
            caller = f"f{i % 50}"
            callee = f"f{(i + 1) % 50}"
            graph.add_call(CallSite(caller, "/test.py", i, callee, "/test.py"))

        # Add 10 implementations
        for i in range(10):
            graph.add_implementation(
                InterfaceImplementation(
                    f"Interface{i % 3}",
                    f"Impl{i}",
                    "/test.py",
                    "python",
                    ["method1", "method2"],
                )
            )

        stats = graph.get_statistics()
        assert stats["total_functions"] == 50
        assert stats["total_calls"] == 200
        assert stats["total_interfaces"] == 3
        assert stats["total_implementations"] == 10


class TestComplexScenarios:
    """Test complex real-world scenarios."""

    def test_diamond_dependency(self):
        """Test diamond dependency pattern: A -> (B, C) -> D."""
        graph = CallGraph()

        for name in ["A", "B", "C", "D"]:
            graph.add_function(FunctionNode(name, name, f"/{name}.py", "python", 1, 5))

        # A calls both B and C
        graph.add_call(CallSite("A", "/A.py", 1, "B", "/B.py"))
        graph.add_call(CallSite("A", "/A.py", 2, "C", "/C.py"))

        # Both B and C call D
        graph.add_call(CallSite("B", "/B.py", 1, "D", "/D.py"))
        graph.add_call(CallSite("C", "/C.py", 1, "D", "/D.py"))

        # Find all paths from A to D
        paths = graph.find_call_chain("A", "D")

        # Should find 2 paths: A->B->D and A->C->D
        assert len(paths) == 2
        [str(p) for p in paths]
        assert ["A", "B", "D"] in paths
        assert ["A", "C", "D"] in paths

    def test_cycle_in_graph(self):
        """Test handling of cycles: A -> B -> C -> A."""
        graph = CallGraph()

        for name in ["A", "B", "C"]:
            graph.add_function(FunctionNode(name, name, f"/{name}.py", "python", 1, 5))

        # Create cycle
        graph.add_call(CallSite("A", "/A.py", 1, "B", "/B.py"))
        graph.add_call(CallSite("B", "/B.py", 1, "C", "/C.py"))
        graph.add_call(CallSite("C", "/C.py", 1, "A", "/A.py"))  # Cycle back

        # Should handle cycles without infinite loop
        callees = graph.find_callees("A", include_indirect=True, max_depth=10)

        # Should find B and C
        callee_names = {c.name for c in callees}
        assert "B" in callee_names
        assert "C" in callee_names

    def test_self_referential_function(self):
        """Test function that calls itself (recursion)."""
        graph = CallGraph()

        graph.add_function(
            FunctionNode("factorial", "factorial", "/math.py", "python", 1, 5)
        )
        graph.add_call(CallSite("factorial", "/math.py", 3, "factorial", "/math.py"))

        # Should not cause infinite loop
        callees = graph.find_callees("factorial", include_indirect=False)
        assert len(callees) == 1
        assert callees[0].name == "factorial"

    def test_multiple_implementations_same_interface(self):
        """Test tracking multiple implementations of same interface."""
        graph = CallGraph()

        implementations = []
        for i in range(5):
            impl = InterfaceImplementation(
                interface_name="Storage",
                implementation_name=f"Storage{i}",
                file_path=f"/storage{i}.py",
                language="python",
                methods=["get", "set", "delete"],
            )
            graph.add_implementation(impl)
            implementations.append(impl)

        retrieved = graph.get_implementations("Storage")
        assert len(retrieved) == 5

        # All should be present
        retrieved_names = {impl.implementation_name for impl in retrieved}
        expected_names = {f"Storage{i}" for i in range(5)}
        assert retrieved_names == expected_names

    def test_mixed_language_graph(self):
        """Test graph with mixed languages (Python, JavaScript, etc.)."""
        graph = CallGraph()

        # Python function
        graph.add_function(
            FunctionNode("py_func", "py_func", "/main.py", "python", 1, 10)
        )

        # JavaScript function
        graph.add_function(
            FunctionNode("jsFunc", "jsFunc", "/main.js", "javascript", 1, 10)
        )

        # Python calls JavaScript (e.g., via API)
        graph.add_call(CallSite("py_func", "/main.py", 5, "jsFunc", "/main.js"))

        callees = graph.find_callees("py_func")
        assert len(callees) == 1
        assert callees[0].language == "javascript"

    def test_layered_architecture(self):
        """Test typical layered architecture: Controller -> Service -> Repository."""
        graph = CallGraph()

        # Build 3-layer architecture
        layers = {
            "controller": ["UserController.get_user", "UserController.create_user"],
            "service": ["UserService.find_user", "UserService.save_user"],
            "repository": ["UserRepository.query", "UserRepository.insert"],
        }

        for layer, functions in layers.items():
            for func in functions:
                graph.add_function(
                    FunctionNode(
                        func.split(".")[-1], func, f"/{layer}.py", "python", 1, 10
                    )
                )

        # Connect layers
        graph.add_call(
            CallSite(
                "UserController.get_user",
                "/controller.py",
                5,
                "UserService.find_user",
                "/service.py",
            )
        )
        graph.add_call(
            CallSite(
                "UserController.create_user",
                "/controller.py",
                5,
                "UserService.save_user",
                "/service.py",
            )
        )
        graph.add_call(
            CallSite(
                "UserService.find_user",
                "/service.py",
                5,
                "UserRepository.query",
                "/repository.py",
            )
        )
        graph.add_call(
            CallSite(
                "UserService.save_user",
                "/service.py",
                5,
                "UserRepository.insert",
                "/repository.py",
            )
        )

        # Verify layered call chain
        paths = graph.find_call_chain("UserController.get_user", "UserRepository.query")
        assert len(paths) >= 1
        assert paths[0] == [
            "UserController.get_user",
            "UserService.find_user",
            "UserRepository.query",
        ]


class TestBoundaryConditions:
    """Test boundary conditions and limits."""

    def test_max_depth_exactly_at_limit(self):
        """Test max_depth when path length equals limit."""
        graph = CallGraph()

        # Build chain of exactly 5 functions
        for i in range(5):
            graph.add_function(
                FunctionNode(f"f{i}", f"f{i}", "/test.py", "python", i, i + 1)
            )

        for i in range(4):
            graph.add_call(CallSite(f"f{i}", "/test.py", i, f"f{i+1}", "/test.py"))

        # Path length is 5, max_depth=5 should find it
        paths = graph.find_call_chain("f0", "f4", max_depth=5)
        assert len(paths) == 1

    def test_max_depth_one_below_limit(self):
        """Test max_depth when path length is one more than limit."""
        graph = CallGraph()

        # Build chain of 5 functions
        for i in range(5):
            graph.add_function(
                FunctionNode(f"f{i}", f"f{i}", "/test.py", "python", i, i + 1)
            )

        for i in range(4):
            graph.add_call(CallSite(f"f{i}", "/test.py", i, f"f{i+1}", "/test.py"))

        # Path length is 5, max_depth=4 should NOT find it
        paths = graph.find_call_chain("f0", "f4", max_depth=4)
        assert len(paths) == 0

    def test_empty_parameters_list(self):
        """Test function with empty parameters list."""
        graph = CallGraph()
        node = FunctionNode(
            name="no_params",
            qualified_name="no_params",
            file_path="/test.py",
            language="python",
            start_line=1,
            end_line=5,
            parameters=[],
        )
        graph.add_function(node)
        assert graph.nodes["no_params"].parameters == []

    def test_many_parameters_100_args(self):
        """Test function with many parameters."""
        graph = CallGraph()
        params = [f"arg{i}" for i in range(100)]
        node = FunctionNode(
            name="many_params",
            qualified_name="many_params",
            file_path="/test.py",
            language="python",
            start_line=1,
            end_line=5,
            parameters=params,
        )
        graph.add_function(node)
        assert len(graph.nodes["many_params"].parameters) == 100

    def test_empty_methods_in_implementation(self):
        """Test interface implementation with no methods."""
        graph = CallGraph()
        impl = InterfaceImplementation(
            interface_name="Marker",
            implementation_name="MarkerImpl",
            file_path="/test.py",
            language="python",
            methods=[],
        )
        graph.add_implementation(impl)

        retrieved = graph.get_implementations("Marker")
        assert len(retrieved) == 1
        assert retrieved[0].methods == []

    def test_call_sites_with_same_caller_and_callee(self):
        """Test multiple call sites between same caller and callee."""
        graph = CallGraph()

        graph.add_function(FunctionNode("A", "A", "/test.py", "python", 1, 20))
        graph.add_function(FunctionNode("B", "B", "/test.py", "python", 30, 40))

        # A calls B multiple times at different lines
        for line in [5, 10, 15]:
            graph.add_call(CallSite("A", "/test.py", line, "B", "/test.py"))

        sites = graph.get_call_sites_for_caller("A")
        assert len(sites) == 3

        lines = {site.caller_line for site in sites}
        assert lines == {5, 10, 15}
