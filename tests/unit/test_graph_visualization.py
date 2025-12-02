"""Tests for dependency graph visualization module (src/graph/dependency_graph.py)."""

import pytest
from src.graph import DependencyGraph, GraphNode, GraphEdge, CircularDependency


class TestGraphNode:
    """Test GraphNode dataclass."""

    def test_create_node_minimal(self):
        """Test creating node with minimal attributes."""
        node = GraphNode(file_path="/project/main.py", language="python")

        assert node.file_path == "/project/main.py"
        assert node.language == "python"
        assert node.unit_count == 0
        assert node.file_size == 0
        assert node.last_modified == ""

    def test_create_node_full(self):
        """Test creating node with all attributes."""
        node = GraphNode(
            file_path="/project/utils.py",
            language="python",
            unit_count=5,
            file_size=1024,
            last_modified="2025-11-18T10:00:00",
        )

        assert node.file_path == "/project/utils.py"
        assert node.language == "python"
        assert node.unit_count == 5
        assert node.file_size == 1024
        assert node.last_modified == "2025-11-18T10:00:00"


class TestGraphEdge:
    """Test GraphEdge dataclass."""

    def test_create_edge_minimal(self):
        """Test creating edge with minimal attributes."""
        edge = GraphEdge(source="/a.py", target="/b.py")

        assert edge.source == "/a.py"
        assert edge.target == "/b.py"
        assert edge.import_type is None
        assert edge.circular is False

    def test_create_edge_full(self):
        """Test creating edge with all attributes."""
        edge = GraphEdge(
            source="/a.py",
            target="/b.py",
            import_type="relative",
            circular=True,
        )

        assert edge.source == "/a.py"
        assert edge.target == "/b.py"
        assert edge.import_type == "relative"
        assert edge.circular is True


class TestCircularDependency:
    """Test CircularDependency dataclass."""

    def test_create_circular_dependency(self):
        """Test creating circular dependency."""
        cycle = CircularDependency(cycle=["/a.py", "/b.py", "/a.py"])

        assert cycle.cycle == ["/a.py", "/b.py", "/a.py"]
        assert cycle.length == 3

    def test_length_auto_calculated(self):
        """Test that length is automatically calculated."""
        cycle = CircularDependency(cycle=["/a.py", "/b.py", "/c.py", "/a.py"])

        assert cycle.length == 4


class TestDependencyGraphBasics:
    """Test basic dependency graph operations."""

    def test_create_empty_graph(self):
        """Test creating empty graph."""
        graph = DependencyGraph()

        assert len(graph.nodes) == 0
        assert len(graph.edges) == 0
        assert len(graph._adjacency_list) == 0

    def test_add_single_node(self):
        """Test adding single node."""
        graph = DependencyGraph()
        node = GraphNode(file_path="/main.py", language="python")

        graph.add_node(node)

        assert len(graph.nodes) == 1
        assert "/main.py" in graph.nodes
        assert graph.nodes["/main.py"] == node
        assert "/main.py" in graph._adjacency_list
        assert graph._adjacency_list["/main.py"] == []

    def test_add_multiple_nodes(self):
        """Test adding multiple nodes."""
        graph = DependencyGraph()
        node1 = GraphNode(file_path="/a.py", language="python")
        node2 = GraphNode(file_path="/b.py", language="python")

        graph.add_node(node1)
        graph.add_node(node2)

        assert len(graph.nodes) == 2
        assert "/a.py" in graph.nodes
        assert "/b.py" in graph.nodes

    def test_replace_existing_node(self):
        """Test that adding node with same path replaces existing."""
        graph = DependencyGraph()
        node1 = GraphNode(file_path="/main.py", language="python", unit_count=5)
        node2 = GraphNode(file_path="/main.py", language="python", unit_count=10)

        graph.add_node(node1)
        graph.add_node(node2)

        assert len(graph.nodes) == 1
        assert graph.nodes["/main.py"].unit_count == 10

    def test_add_single_edge(self):
        """Test adding single edge."""
        graph = DependencyGraph()
        edge = GraphEdge(source="/a.py", target="/b.py")

        graph.add_edge(edge)

        assert len(graph.edges) == 1
        assert edge in graph.edges
        assert "/a.py" in graph._adjacency_list
        assert "/b.py" in graph._adjacency_list
        assert "/b.py" in graph._adjacency_list["/a.py"]

    def test_add_multiple_edges(self):
        """Test adding multiple edges."""
        graph = DependencyGraph()
        edge1 = GraphEdge(source="/a.py", target="/b.py")
        edge2 = GraphEdge(source="/a.py", target="/c.py")
        edge3 = GraphEdge(source="/b.py", target="/c.py")

        graph.add_edge(edge1)
        graph.add_edge(edge2)
        graph.add_edge(edge3)

        assert len(graph.edges) == 3
        assert len(graph._adjacency_list["/a.py"]) == 2
        assert "/b.py" in graph._adjacency_list["/a.py"]
        assert "/c.py" in graph._adjacency_list["/a.py"]
        assert "/c.py" in graph._adjacency_list["/b.py"]

    def test_duplicate_edges_not_added(self):
        """Test that duplicate edges are not added to adjacency list."""
        graph = DependencyGraph()
        edge1 = GraphEdge(source="/a.py", target="/b.py")
        edge2 = GraphEdge(source="/a.py", target="/b.py")

        graph.add_edge(edge1)
        graph.add_edge(edge2)

        # Both edges are in edges list (no dedup)
        assert len(graph.edges) == 2
        # But adjacency list only has one entry
        assert graph._adjacency_list["/a.py"].count("/b.py") == 1


class TestCircularDependencyDetection:
    """Test circular dependency detection."""

    def test_no_cycles_empty_graph(self):
        """Test no cycles in empty graph."""
        graph = DependencyGraph()

        cycles = graph.find_circular_dependencies()

        assert cycles == []

    def test_no_cycles_single_node(self):
        """Test no cycles with single node."""
        graph = DependencyGraph()
        graph.add_node(GraphNode(file_path="/a.py", language="python"))

        cycles = graph.find_circular_dependencies()

        assert cycles == []

    def test_no_cycles_linear_chain(self):
        """Test no cycles in linear dependency chain."""
        graph = DependencyGraph()
        graph.add_node(GraphNode(file_path="/a.py", language="python"))
        graph.add_node(GraphNode(file_path="/b.py", language="python"))
        graph.add_node(GraphNode(file_path="/c.py", language="python"))
        graph.add_edge(GraphEdge(source="/a.py", target="/b.py"))
        graph.add_edge(GraphEdge(source="/b.py", target="/c.py"))

        cycles = graph.find_circular_dependencies()

        assert cycles == []

    def test_simple_two_node_cycle(self):
        """Test detecting simple two-node cycle."""
        graph = DependencyGraph()
        graph.add_node(GraphNode(file_path="/a.py", language="python"))
        graph.add_node(GraphNode(file_path="/b.py", language="python"))
        graph.add_edge(GraphEdge(source="/a.py", target="/b.py"))
        graph.add_edge(GraphEdge(source="/b.py", target="/a.py"))

        cycles = graph.find_circular_dependencies()

        assert len(cycles) == 1
        assert "/a.py" in cycles[0].cycle
        assert "/b.py" in cycles[0].cycle

    def test_three_node_cycle(self):
        """Test detecting three-node cycle."""
        graph = DependencyGraph()
        graph.add_node(GraphNode(file_path="/a.py", language="python"))
        graph.add_node(GraphNode(file_path="/b.py", language="python"))
        graph.add_node(GraphNode(file_path="/c.py", language="python"))
        graph.add_edge(GraphEdge(source="/a.py", target="/b.py"))
        graph.add_edge(GraphEdge(source="/b.py", target="/c.py"))
        graph.add_edge(GraphEdge(source="/c.py", target="/a.py"))

        cycles = graph.find_circular_dependencies()

        assert len(cycles) == 1
        assert "/a.py" in cycles[0].cycle
        assert "/b.py" in cycles[0].cycle
        assert "/c.py" in cycles[0].cycle

    def test_self_loop(self):
        """Test detecting self-loop."""
        graph = DependencyGraph()
        graph.add_node(GraphNode(file_path="/a.py", language="python"))
        graph.add_edge(GraphEdge(source="/a.py", target="/a.py"))

        cycles = graph.find_circular_dependencies()

        assert len(cycles) == 1
        assert cycles[0].cycle == ["/a.py", "/a.py"]

    def test_edges_marked_circular(self):
        """Test that edges in cycles are marked as circular."""
        graph = DependencyGraph()
        edge1 = GraphEdge(source="/a.py", target="/b.py")
        edge2 = GraphEdge(source="/b.py", target="/a.py")
        edge3 = GraphEdge(source="/a.py", target="/c.py")  # Not in cycle

        graph.add_edge(edge1)
        graph.add_edge(edge2)
        graph.add_edge(edge3)

        graph.find_circular_dependencies()

        assert edge1.circular is True
        assert edge2.circular is True
        assert edge3.circular is False

    def test_cached_circular_dependencies(self):
        """Test that circular dependencies are cached."""
        graph = DependencyGraph()
        graph.add_edge(GraphEdge(source="/a.py", target="/b.py"))
        graph.add_edge(GraphEdge(source="/b.py", target="/a.py"))

        cycles1 = graph.find_circular_dependencies()
        cycles2 = graph.find_circular_dependencies()

        # Should return same object (cached)
        assert cycles1 is cycles2


class TestGraphFiltering:
    """Test graph filtering operations."""

    def test_filter_by_depth_root_only(self):
        """Test filtering with depth=0 (root only)."""
        graph = DependencyGraph()
        graph.add_node(GraphNode(file_path="/a.py", language="python"))
        graph.add_node(GraphNode(file_path="/b.py", language="python"))
        graph.add_edge(GraphEdge(source="/a.py", target="/b.py"))

        filtered = graph.filter_by_depth("/a.py", 0)

        assert len(filtered.nodes) == 1
        assert "/a.py" in filtered.nodes
        assert len(filtered.edges) == 0

    def test_filter_by_depth_one_level(self):
        """Test filtering with depth=1 (direct dependencies)."""
        graph = DependencyGraph()
        graph.add_node(GraphNode(file_path="/a.py", language="python"))
        graph.add_node(GraphNode(file_path="/b.py", language="python"))
        graph.add_node(GraphNode(file_path="/c.py", language="python"))
        graph.add_edge(GraphEdge(source="/a.py", target="/b.py"))
        graph.add_edge(GraphEdge(source="/b.py", target="/c.py"))

        filtered = graph.filter_by_depth("/a.py", 1)

        assert len(filtered.nodes) == 2
        assert "/a.py" in filtered.nodes
        assert "/b.py" in filtered.nodes
        assert "/c.py" not in filtered.nodes
        assert len(filtered.edges) == 1

    def test_filter_by_depth_two_levels(self):
        """Test filtering with depth=2."""
        graph = DependencyGraph()
        graph.add_node(GraphNode(file_path="/a.py", language="python"))
        graph.add_node(GraphNode(file_path="/b.py", language="python"))
        graph.add_node(GraphNode(file_path="/c.py", language="python"))
        graph.add_edge(GraphEdge(source="/a.py", target="/b.py"))
        graph.add_edge(GraphEdge(source="/b.py", target="/c.py"))

        filtered = graph.filter_by_depth("/a.py", 2)

        assert len(filtered.nodes) == 3
        assert len(filtered.edges) == 2

    def test_filter_by_depth_nonexistent_root(self):
        """Test filtering with nonexistent root raises error."""
        graph = DependencyGraph()
        graph.add_node(GraphNode(file_path="/a.py", language="python"))

        with pytest.raises(ValueError, match="Root node '/nonexistent.py' not found"):
            graph.filter_by_depth("/nonexistent.py", 1)

    def test_filter_by_pattern_exact_match(self):
        """Test filtering by exact file pattern."""
        graph = DependencyGraph()
        graph.add_node(GraphNode(file_path="/project/main.py", language="python"))
        graph.add_node(GraphNode(file_path="/project/utils.py", language="python"))
        graph.add_node(GraphNode(file_path="/project/test.js", language="javascript"))

        filtered = graph.filter_by_pattern("*.py")

        assert len(filtered.nodes) == 2
        assert "/project/main.py" in filtered.nodes
        assert "/project/utils.py" in filtered.nodes
        assert "/project/test.js" not in filtered.nodes

    def test_filter_by_pattern_wildcard(self):
        """Test filtering by wildcard pattern."""
        graph = DependencyGraph()
        graph.add_node(GraphNode(file_path="/project/src/main.py", language="python"))
        graph.add_node(
            GraphNode(file_path="/project/tests/test_main.py", language="python")
        )
        graph.add_node(GraphNode(file_path="/project/README.md", language="markdown"))

        filtered = graph.filter_by_pattern("/project/src/*")

        assert len(filtered.nodes) == 1
        assert "/project/src/main.py" in filtered.nodes

    def test_filter_by_pattern_filename_only(self):
        """Test filtering by filename only (ignores path)."""
        graph = DependencyGraph()
        graph.add_node(GraphNode(file_path="/a/main.py", language="python"))
        graph.add_node(GraphNode(file_path="/b/main.py", language="python"))
        graph.add_node(GraphNode(file_path="/c/utils.py", language="python"))

        filtered = graph.filter_by_pattern("main.py")

        assert len(filtered.nodes) == 2
        assert "/a/main.py" in filtered.nodes
        assert "/b/main.py" in filtered.nodes

    def test_filter_by_pattern_preserves_edges(self):
        """Test that filtering preserves edges between matching nodes."""
        graph = DependencyGraph()
        graph.add_node(GraphNode(file_path="/a.py", language="python"))
        graph.add_node(GraphNode(file_path="/b.py", language="python"))
        graph.add_node(GraphNode(file_path="/c.js", language="javascript"))
        graph.add_edge(GraphEdge(source="/a.py", target="/b.py"))
        graph.add_edge(GraphEdge(source="/a.py", target="/c.js"))

        filtered = graph.filter_by_pattern("*.py")

        assert len(filtered.edges) == 1
        assert filtered.edges[0].source == "/a.py"
        assert filtered.edges[0].target == "/b.py"

    def test_filter_by_language_python(self):
        """Test filtering by Python language."""
        graph = DependencyGraph()
        graph.add_node(GraphNode(file_path="/a.py", language="python"))
        graph.add_node(
            GraphNode(file_path="/b.py", language="Python")
        )  # Different case
        graph.add_node(GraphNode(file_path="/c.js", language="javascript"))

        filtered = graph.filter_by_language("python")

        assert len(filtered.nodes) == 2
        assert "/a.py" in filtered.nodes
        assert "/b.py" in filtered.nodes

    def test_filter_by_language_case_insensitive(self):
        """Test language filtering is case-insensitive."""
        graph = DependencyGraph()
        graph.add_node(GraphNode(file_path="/a.js", language="JavaScript"))
        graph.add_node(GraphNode(file_path="/b.js", language="javascript"))

        filtered = graph.filter_by_language("JAVASCRIPT")

        assert len(filtered.nodes) == 2

    def test_filter_by_language_no_matches(self):
        """Test filtering with no matching language."""
        graph = DependencyGraph()
        graph.add_node(GraphNode(file_path="/a.py", language="python"))

        filtered = graph.filter_by_language("rust")

        assert len(filtered.nodes) == 0


class TestGraphStatistics:
    """Test graph statistics."""

    def test_stats_empty_graph(self):
        """Test statistics for empty graph."""
        graph = DependencyGraph()

        stats = graph.get_stats()

        assert stats["node_count"] == 0
        assert stats["edge_count"] == 0
        assert stats["circular_dependency_count"] == 0
        assert stats["max_depth"] == 0

    def test_stats_single_node(self):
        """Test statistics for single node."""
        graph = DependencyGraph()
        graph.add_node(GraphNode(file_path="/a.py", language="python"))

        stats = graph.get_stats()

        assert stats["node_count"] == 1
        assert stats["edge_count"] == 0
        assert stats["circular_dependency_count"] == 0
        assert stats["max_depth"] == 0

    def test_stats_linear_chain(self):
        """Test statistics for linear dependency chain."""
        graph = DependencyGraph()
        graph.add_node(GraphNode(file_path="/a.py", language="python"))
        graph.add_node(GraphNode(file_path="/b.py", language="python"))
        graph.add_node(GraphNode(file_path="/c.py", language="python"))
        graph.add_edge(GraphEdge(source="/a.py", target="/b.py"))
        graph.add_edge(GraphEdge(source="/b.py", target="/c.py"))

        stats = graph.get_stats()

        assert stats["node_count"] == 3
        assert stats["edge_count"] == 2
        assert stats["circular_dependency_count"] == 0
        assert stats["max_depth"] == 2

    def test_stats_with_circular_dependencies(self):
        """Test statistics with circular dependencies."""
        graph = DependencyGraph()
        graph.add_node(GraphNode(file_path="/a.py", language="python"))
        graph.add_node(GraphNode(file_path="/b.py", language="python"))
        graph.add_edge(GraphEdge(source="/a.py", target="/b.py"))
        graph.add_edge(GraphEdge(source="/b.py", target="/a.py"))

        stats = graph.get_stats()

        assert stats["node_count"] == 2
        assert stats["edge_count"] == 2
        assert stats["circular_dependency_count"] == 1

    def test_stats_tree_structure(self):
        """Test statistics for tree structure."""
        graph = DependencyGraph()
        # Root
        graph.add_node(GraphNode(file_path="/root.py", language="python"))
        # Level 1
        graph.add_node(GraphNode(file_path="/a.py", language="python"))
        graph.add_node(GraphNode(file_path="/b.py", language="python"))
        # Level 2
        graph.add_node(GraphNode(file_path="/c.py", language="python"))

        graph.add_edge(GraphEdge(source="/root.py", target="/a.py"))
        graph.add_edge(GraphEdge(source="/root.py", target="/b.py"))
        graph.add_edge(GraphEdge(source="/a.py", target="/c.py"))

        stats = graph.get_stats()

        assert stats["node_count"] == 4
        assert stats["edge_count"] == 3
        assert stats["max_depth"] == 2
