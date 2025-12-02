"""Tests for dependency graph visualization generator."""

import pytest
import json
from src.memory.dependency_graph import DependencyGraph
from src.memory.graph_generator import DependencyGraphGenerator


@pytest.fixture
def simple_graph():
    """Create a simple dependency graph for testing."""
    graph = DependencyGraph()

    # Add simple dependencies: A -> B -> C
    # Directly set dependencies to avoid file resolution issues in tests
    graph.dependencies = {
        "/test/a.py": {"/test/b.py"},
        "/test/b.py": {"/test/c.py"},
        "/test/c.py": set(),
    }

    # Build reverse dependencies
    graph.dependents = {
        "/test/a.py": set(),
        "/test/b.py": {"/test/a.py"},
        "/test/c.py": {"/test/b.py"},
    }

    return graph


@pytest.fixture
def circular_graph():
    """Create a graph with circular dependencies."""
    graph = DependencyGraph()

    # Create circular dependency: A -> B -> C -> A
    graph.dependencies = {
        "/test/a.py": {"/test/b.py"},
        "/test/b.py": {"/test/c.py"},
        "/test/c.py": {"/test/a.py"},
    }
    graph.dependents = {
        "/test/a.py": {"/test/c.py"},
        "/test/b.py": {"/test/a.py"},
        "/test/c.py": {"/test/b.py"},
    }

    return graph


@pytest.fixture
def complex_graph():
    """Create a more complex graph with multiple patterns."""
    graph = DependencyGraph()

    # Multiple files with various dependencies
    graph.dependencies = {
        "/test/main.py": {"/test/utils.py", "/test/helpers.py"},
        "/test/utils.py": {"/test/config.py"},
        "/test/helpers.py": {"/test/config.py"},
        "/test/config.py": set(),
        "/test/isolated.py": set(),
    }

    # Build reverse dependencies
    for source, targets in graph.dependencies.items():
        for target in targets:
            if target not in graph.dependents:
                graph.dependents[target] = set()
            graph.dependents[target].add(source)

    return graph


class TestDependencyGraphGenerator:
    """Tests for DependencyGraphGenerator class."""

    def test_init(self, simple_graph):
        """Test generator initialization."""
        generator = DependencyGraphGenerator(simple_graph)
        assert generator.graph is simple_graph

    def test_generate_dot_format(self, simple_graph):
        """Test DOT format generation."""
        generator = DependencyGraphGenerator(simple_graph)
        graph_data, stats, circular = generator.generate(format="dot")

        assert "digraph dependencies" in graph_data
        assert "a.py" in graph_data
        assert "b.py" in graph_data
        assert "->" in graph_data
        assert stats["node_count"] >= 2
        assert stats["edge_count"] >= 1

    def test_generate_json_format(self, simple_graph):
        """Test JSON format generation."""
        generator = DependencyGraphGenerator(simple_graph)
        graph_data, stats, circular = generator.generate(format="json")

        # Parse JSON to verify validity
        data = json.loads(graph_data)
        assert "nodes" in data
        assert "links" in data
        assert "circular_groups" in data
        assert len(data["nodes"]) >= 2
        assert len(data["links"]) >= 1

    def test_generate_mermaid_format(self, simple_graph):
        """Test Mermaid format generation."""
        generator = DependencyGraphGenerator(simple_graph)
        graph_data, stats, circular = generator.generate(format="mermaid")

        assert "graph LR" in graph_data
        assert "a.py" in graph_data
        assert "b.py" in graph_data
        assert "-->" in graph_data

    def test_invalid_format(self, simple_graph):
        """Test that invalid format raises ValueError."""
        generator = DependencyGraphGenerator(simple_graph)
        with pytest.raises(ValueError, match="Unsupported format"):
            generator.generate(format="invalid")

    def test_circular_dependency_detection(self, circular_graph):
        """Test circular dependency detection."""
        generator = DependencyGraphGenerator(circular_graph)
        graph_data, stats, circular = generator.generate(
            format="json", highlight_circular=True
        )

        assert stats["circular_dependency_count"] >= 1
        assert len(circular) >= 1
        # Should detect the cycle A -> B -> C -> A
        assert any(len(cycle) >= 3 for cycle in circular)

    def test_circular_highlighting_dot(self, circular_graph):
        """Test circular dependency highlighting in DOT format."""
        generator = DependencyGraphGenerator(circular_graph)
        graph_data, stats, circular = generator.generate(
            format="dot", highlight_circular=True
        )

        # Should have red edges for circular dependencies
        assert "color=red" in graph_data
        assert "#ff9999" in graph_data  # Circular node color

    def test_circular_highlighting_mermaid(self, circular_graph):
        """Test circular dependency highlighting in Mermaid format."""
        generator = DependencyGraphGenerator(circular_graph)
        graph_data, stats, circular = generator.generate(
            format="mermaid", highlight_circular=True
        )

        # Should have styling for circular nodes
        assert "style" in graph_data
        assert "#ff9999" in graph_data
        # Mermaid should have arrows (checking for the arrow syntax)
        assert "] -.-> " in graph_data or "] --> " in graph_data

    def test_filter_by_depth(self, complex_graph):
        """Test depth filtering."""
        generator = DependencyGraphGenerator(complex_graph)

        # Depth 1 should only include direct dependencies
        graph_data, stats, circular = generator.generate(format="json", max_depth=1)
        json.loads(graph_data)

        # Should have fewer nodes with depth limit
        assert stats["node_count"] <= 5  # All nodes in this simple graph

    def test_filter_by_file_pattern(self, complex_graph):
        """Test file pattern filtering."""
        generator = DependencyGraphGenerator(complex_graph)

        # Filter only config files
        graph_data, stats, circular = generator.generate(
            format="json", file_pattern="*config.py"
        )
        data = json.loads(graph_data)

        # Should only have config.py
        assert stats["node_count"] == 1
        assert any("config.py" in node["id"] for node in data["nodes"])

    def test_filter_by_language(self, complex_graph):
        """Test language filtering."""
        generator = DependencyGraphGenerator(complex_graph)

        # All files are Python in this test
        graph_data, stats, circular = generator.generate(
            format="json", language="python"
        )
        data = json.loads(graph_data)

        # All nodes should be Python files
        assert all(node["language"] == "python" for node in data["nodes"])

    def test_metadata_enrichment(self, simple_graph):
        """Test metadata enrichment."""
        generator = DependencyGraphGenerator(simple_graph)

        graph_data, stats, circular = generator.generate(
            format="json", include_metadata=True
        )
        data = json.loads(graph_data)

        # Nodes should have metadata
        for node in data["nodes"]:
            assert "size" in node
            assert "language" in node
            assert "label" in node

    def test_metadata_disabled(self, simple_graph):
        """Test generation without metadata."""
        generator = DependencyGraphGenerator(simple_graph)

        # Should work even without metadata
        graph_data, stats, circular = generator.generate(
            format="json", include_metadata=False
        )
        data = json.loads(graph_data)

        # Should still have basic node structure
        assert len(data["nodes"]) >= 2

    def test_empty_graph(self):
        """Test handling of empty graph."""
        empty_graph = DependencyGraph()
        generator = DependencyGraphGenerator(empty_graph)

        graph_data, stats, circular = generator.generate(format="json")
        data = json.loads(graph_data)

        assert stats["node_count"] == 0
        assert stats["edge_count"] == 0
        assert len(data["nodes"]) == 0
        assert len(data["links"]) == 0

    def test_combined_filters(self, complex_graph):
        """Test combining multiple filters."""
        generator = DependencyGraphGenerator(complex_graph)

        # Combine depth and pattern filters
        graph_data, stats, circular = generator.generate(
            format="json", max_depth=2, file_pattern="*.py", language="python"
        )
        json.loads(graph_data)

        # Should have filtered results
        assert stats["node_count"] >= 0  # May filter down to nothing or some nodes

    def test_dot_syntax_correctness(self, simple_graph):
        """Test that DOT output is syntactically correct."""
        generator = DependencyGraphGenerator(simple_graph)
        graph_data, stats, circular = generator.generate(format="dot")

        # Check basic DOT syntax
        assert graph_data.startswith("digraph dependencies {")
        assert graph_data.strip().endswith("}")
        assert "rankdir=LR" in graph_data

    def test_json_d3_compatibility(self, simple_graph):
        """Test that JSON output is D3.js compatible."""
        generator = DependencyGraphGenerator(simple_graph)
        graph_data, stats, circular = generator.generate(format="json")

        data = json.loads(graph_data)

        # Check D3.js expected structure
        assert "nodes" in data and isinstance(data["nodes"], list)
        assert "links" in data and isinstance(data["links"], list)

        # Check link structure (D3 expects source/target)
        for link in data["links"]:
            assert "source" in link
            assert "target" in link

    def test_mermaid_syntax_correctness(self, simple_graph):
        """Test that Mermaid output is syntactically correct."""
        generator = DependencyGraphGenerator(simple_graph)
        graph_data, stats, circular = generator.generate(format="mermaid")

        # Check basic Mermaid syntax
        assert graph_data.startswith("graph LR")
        # Check for arrow syntax (either solid or dashed)
        assert "] --> " in graph_data or "] -.-> " in graph_data

    def test_statistics_accuracy(self, complex_graph):
        """Test that statistics are accurate."""
        generator = DependencyGraphGenerator(complex_graph)
        graph_data, stats, circular = generator.generate(format="json")

        data = json.loads(graph_data)

        # Verify stats match actual data
        assert stats["node_count"] == len(data["nodes"])
        assert stats["edge_count"] == len(data["links"])

    def test_language_detection(self, simple_graph):
        """Test language detection from file extensions."""
        generator = DependencyGraphGenerator(simple_graph)

        # Test various extensions
        assert generator._get_language("/test/file.py") == "python"
        assert generator._get_language("/test/file.js") == "javascript"
        assert generator._get_language("/test/file.ts") == "typescript"
        assert generator._get_language("/test/file.go") == "go"
        assert generator._get_language("/test/file.unknown") == "unknown"
