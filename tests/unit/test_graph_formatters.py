"""Tests for dependency graph formatters."""

import pytest
import json
from src.graph import DependencyGraph, GraphNode, GraphEdge
from src.graph.formatters import DOTFormatter, JSONFormatter, MermaidFormatter


class TestDOTFormatter:
    """Test DOT (Graphviz) formatter."""

    def test_empty_graph(self):
        """Test formatting empty graph."""
        graph = DependencyGraph()
        formatter = DOTFormatter()

        output = formatter.format(graph, title="Test Graph")

        assert 'digraph "Test Graph"' in output
        assert 'rankdir=LR' in output
        assert output.count('node [') == 1  # Only graph-level node settings
        assert output.endswith('}')

    def test_single_node(self):
        """Test formatting graph with single node."""
        graph = DependencyGraph()
        graph.add_node(GraphNode(file_path="/project/main.py", language="python"))
        formatter = DOTFormatter()

        output = formatter.format(graph)

        assert "main.py" in output
        assert "python" in output.lower() or "#3776ab" in output  # Python color

    def test_node_with_metadata(self):
        """Test node formatting includes metadata."""
        graph = DependencyGraph()
        graph.add_node(
            GraphNode(
                file_path="/project/utils.py",
                language="python",
                unit_count=5,
                file_size=2048,
                last_modified="2025-11-18T10:00:00",
            )
        )
        formatter = DOTFormatter(include_metadata=True)

        output = formatter.format(graph)

        assert "utils.py" in output
        assert "5 units" in output
        assert "2.0KB" in output  # File size formatted

    def test_node_without_metadata(self):
        """Test node formatting without metadata."""
        graph = DependencyGraph()
        graph.add_node(
            GraphNode(
                file_path="/project/utils.py",
                language="python",
                unit_count=5,
                file_size=2048,
            )
        )
        formatter = DOTFormatter(include_metadata=False)

        output = formatter.format(graph)

        assert "utils.py" in output
        assert "units" not in output
        assert "KB" not in output

    def test_language_colors(self):
        """Test different language colors."""
        graph = DependencyGraph()
        graph.add_node(GraphNode(file_path="/a.py", language="python"))
        graph.add_node(GraphNode(file_path="/b.js", language="javascript"))
        graph.add_node(GraphNode(file_path="/c.rs", language="rust"))
        formatter = DOTFormatter()

        output = formatter.format(graph)

        # Check that different colors are used
        assert "#3776ab" in output  # Python
        assert "#f7df1e" in output  # JavaScript
        assert "#dea584" in output  # Rust

    def test_unknown_language_color(self):
        """Test unknown language gets default color."""
        graph = DependencyGraph()
        graph.add_node(GraphNode(file_path="/test.xyz", language="unknown"))
        formatter = DOTFormatter()

        output = formatter.format(graph)

        assert "#gray" in output  # Default color

    def test_simple_edge(self):
        """Test formatting simple edge."""
        graph = DependencyGraph()
        graph.add_node(GraphNode(file_path="/a.py", language="python"))
        graph.add_node(GraphNode(file_path="/b.py", language="python"))
        graph.add_edge(GraphEdge(source="/a.py", target="/b.py"))
        formatter = DOTFormatter()

        output = formatter.format(graph)

        # Check edge exists (node IDs will have underscores)
        assert "->" in output

    def test_circular_edge_highlighted(self):
        """Test circular dependency edges are highlighted."""
        graph = DependencyGraph()
        graph.add_node(GraphNode(file_path="/a.py", language="python"))
        graph.add_node(GraphNode(file_path="/b.py", language="python"))
        graph.add_edge(GraphEdge(source="/a.py", target="/b.py"))
        graph.add_edge(GraphEdge(source="/b.py", target="/a.py"))

        # Detect circular dependencies (marks edges as circular)
        graph.find_circular_dependencies()

        formatter = DOTFormatter()
        output = formatter.format(graph)

        assert "color=red" in output
        assert "circular" in output

    def test_node_id_sanitization(self):
        """Test file paths are converted to valid node IDs."""
        graph = DependencyGraph()
        graph.add_node(GraphNode(file_path="/project/src/utils.py", language="python"))
        formatter = DOTFormatter()

        output = formatter.format(graph)

        # Path should be converted to valid ID (slashes to underscores)
        assert "_project_src_utils_py" in output

    def test_string_escaping(self):
        """Test special characters are escaped."""
        graph = DependencyGraph()
        # File with quotes in path (edge case)
        graph.add_node(GraphNode(file_path='/project/"test".py', language="python"))
        formatter = DOTFormatter()

        output = formatter.format(graph)

        # Should not break DOT syntax
        assert 'digraph' in output
        assert output.endswith('}')

    def test_file_size_formatting(self):
        """Test file size formatting in different ranges."""
        graph = DependencyGraph()
        # Bytes
        graph.add_node(
            GraphNode(
                file_path="/tiny.py",
                language="python",
                unit_count=1,
                file_size=500,
            )
        )
        # Kilobytes
        graph.add_node(
            GraphNode(
                file_path="/medium.py",
                language="python",
                unit_count=1,
                file_size=5000,
            )
        )
        # Megabytes
        graph.add_node(
            GraphNode(
                file_path="/large.py",
                language="python",
                unit_count=1,
                file_size=2000000,
            )
        )
        formatter = DOTFormatter(include_metadata=True)

        output = formatter.format(graph)

        assert "500B" in output
        assert "4.9KB" in output
        assert "1.9MB" in output


class TestJSONFormatter:
    """Test JSON formatter."""

    def test_empty_graph(self):
        """Test formatting empty graph."""
        graph = DependencyGraph()
        formatter = JSONFormatter()

        output = formatter.format(graph, title="Test Graph")
        data = json.loads(output)

        assert data["metadata"]["title"] == "Test Graph"
        assert data["metadata"]["node_count"] == 0
        assert data["metadata"]["edge_count"] == 0
        assert data["nodes"] == []
        assert data["links"] == []

    def test_single_node(self):
        """Test formatting graph with single node."""
        graph = DependencyGraph()
        graph.add_node(GraphNode(file_path="/project/main.py", language="python"))
        formatter = JSONFormatter()

        output = formatter.format(graph)
        data = json.loads(output)

        assert len(data["nodes"]) == 1
        assert data["nodes"][0]["id"] == "/project/main.py"
        assert data["nodes"][0]["language"] == "python"

    def test_node_with_metadata(self):
        """Test node includes metadata."""
        graph = DependencyGraph()
        graph.add_node(
            GraphNode(
                file_path="/utils.py",
                language="python",
                unit_count=5,
                file_size=2048,
                last_modified="2025-11-18T10:00:00",
            )
        )
        formatter = JSONFormatter(include_metadata=True)

        output = formatter.format(graph)
        data = json.loads(output)

        node = data["nodes"][0]
        assert node["unit_count"] == 5
        assert node["file_size"] == 2048
        assert node["last_modified"] == "2025-11-18T10:00:00"

    def test_node_without_metadata(self):
        """Test node without metadata."""
        graph = DependencyGraph()
        graph.add_node(
            GraphNode(
                file_path="/utils.py",
                language="python",
                unit_count=5,
                file_size=2048,
            )
        )
        formatter = JSONFormatter(include_metadata=False)

        output = formatter.format(graph)
        data = json.loads(output)

        node = data["nodes"][0]
        assert "unit_count" not in node
        assert "file_size" not in node
        assert node["language"] == "python"  # Always included

    def test_simple_edge(self):
        """Test formatting simple edge."""
        graph = DependencyGraph()
        graph.add_node(GraphNode(file_path="/a.py", language="python"))
        graph.add_node(GraphNode(file_path="/b.py", language="python"))
        graph.add_edge(GraphEdge(source="/a.py", target="/b.py"))
        formatter = JSONFormatter()

        output = formatter.format(graph)
        data = json.loads(output)

        assert len(data["links"]) == 1
        assert data["links"][0]["source"] == "/a.py"
        assert data["links"][0]["target"] == "/b.py"

    def test_circular_edge_flagged(self):
        """Test circular edge has circular flag."""
        graph = DependencyGraph()
        graph.add_node(GraphNode(file_path="/a.py", language="python"))
        graph.add_node(GraphNode(file_path="/b.py", language="python"))
        graph.add_edge(GraphEdge(source="/a.py", target="/b.py"))
        graph.add_edge(GraphEdge(source="/b.py", target="/a.py"))

        graph.find_circular_dependencies()

        formatter = JSONFormatter()
        output = formatter.format(graph)
        data = json.loads(output)

        # Both edges should be marked circular
        circular_count = sum(1 for link in data["links"] if link.get("circular"))
        assert circular_count == 2

    def test_edge_with_import_type(self):
        """Test edge includes import type."""
        graph = DependencyGraph()
        graph.add_edge(
            GraphEdge(source="/a.py", target="/b.py", import_type="relative")
        )
        formatter = JSONFormatter()

        output = formatter.format(graph)
        data = json.loads(output)

        assert data["links"][0]["type"] == "relative"

    def test_metadata_includes_stats(self):
        """Test metadata includes graph statistics."""
        graph = DependencyGraph()
        graph.add_node(GraphNode(file_path="/a.py", language="python"))
        graph.add_node(GraphNode(file_path="/b.py", language="python"))
        graph.add_edge(GraphEdge(source="/a.py", target="/b.py"))
        formatter = JSONFormatter()

        output = formatter.format(graph)
        data = json.loads(output)

        assert data["metadata"]["node_count"] == 2
        assert data["metadata"]["edge_count"] == 1
        assert "circular_dependencies" in data["metadata"]

    def test_format_with_positions(self):
        """Test formatting with pre-computed positions."""
        graph = DependencyGraph()
        graph.add_node(GraphNode(file_path="/a.py", language="python"))
        graph.add_node(GraphNode(file_path="/b.py", language="python"))

        positions = {
            "/a.py": {"x": 100.0, "y": 50.0},
            "/b.py": {"x": 200.0, "y": 150.0},
        }

        formatter = JSONFormatter()
        output = formatter.format_with_positions(graph, positions)
        data = json.loads(output)

        # Find nodes and check positions
        node_a = next(n for n in data["nodes"] if n["id"] == "/a.py")
        node_b = next(n for n in data["nodes"] if n["id"] == "/b.py")

        assert node_a["x"] == 100.0
        assert node_a["y"] == 50.0
        assert node_b["x"] == 200.0
        assert node_b["y"] == 150.0

    def test_unicode_support(self):
        """Test JSON supports Unicode characters."""
        graph = DependencyGraph()
        graph.add_node(GraphNode(file_path="/?@>5:B/D09;.py", language="python"))
        formatter = JSONFormatter()

        output = formatter.format(graph)
        data = json.loads(output)

        assert data["nodes"][0]["id"] == "/?@>5:B/D09;.py"


class TestMermaidFormatter:
    """Test Mermaid formatter."""

    def test_empty_graph(self):
        """Test formatting empty graph."""
        graph = DependencyGraph()
        formatter = MermaidFormatter()

        output = formatter.format(graph, title="Test Graph")

        assert "%% Test Graph" in output
        assert "graph LR" in output

    def test_single_node(self):
        """Test formatting graph with single node."""
        graph = DependencyGraph()
        graph.add_node(GraphNode(file_path="/project/main.py", language="python"))
        formatter = MermaidFormatter()

        output = formatter.format(graph)

        assert "main.py" in output
        assert "[" in output  # Mermaid node syntax

    def test_node_with_metadata(self):
        """Test node formatting includes metadata."""
        graph = DependencyGraph()
        graph.add_node(
            GraphNode(
                file_path="/utils.py",
                language="python",
                unit_count=5,
                file_size=2048,
            )
        )
        formatter = MermaidFormatter(include_metadata=True)

        output = formatter.format(graph)

        assert "utils.py" in output
        assert "5 units" in output
        assert "2.0KB" in output

    def test_node_without_metadata(self):
        """Test node formatting without metadata."""
        graph = DependencyGraph()
        graph.add_node(
            GraphNode(
                file_path="/utils.py",
                language="python",
                unit_count=5,
                file_size=2048,
            )
        )
        formatter = MermaidFormatter(include_metadata=False)

        output = formatter.format(graph)

        assert "utils.py" in output
        assert "units" not in output
        assert "KB" not in output

    def test_simple_edge(self):
        """Test formatting simple edge."""
        graph = DependencyGraph()
        graph.add_node(GraphNode(file_path="/a.py", language="python"))
        graph.add_node(GraphNode(file_path="/b.py", language="python"))
        graph.add_edge(GraphEdge(source="/a.py", target="/b.py"))
        formatter = MermaidFormatter()

        output = formatter.format(graph)

        assert "-->" in output

    def test_edge_with_import_type(self):
        """Test edge with import type label."""
        graph = DependencyGraph()
        graph.add_node(GraphNode(file_path="/a.py", language="python"))
        graph.add_node(GraphNode(file_path="/b.py", language="python"))
        graph.add_edge(
            GraphEdge(source="/a.py", target="/b.py", import_type="relative")
        )
        formatter = MermaidFormatter()

        output = formatter.format(graph)

        assert "-->|relative|" in output

    def test_circular_edge_dotted(self):
        """Test circular dependency edges use dotted lines."""
        graph = DependencyGraph()
        graph.add_node(GraphNode(file_path="/a.py", language="python"))
        graph.add_node(GraphNode(file_path="/b.py", language="python"))
        graph.add_edge(GraphEdge(source="/a.py", target="/b.py"))
        graph.add_edge(GraphEdge(source="/b.py", target="/a.py"))

        graph.find_circular_dependencies()

        formatter = MermaidFormatter()
        output = formatter.format(graph)

        assert "-.->|circular|" in output

    def test_circular_edge_styling(self):
        """Test circular edges get red styling."""
        graph = DependencyGraph()
        graph.add_node(GraphNode(file_path="/a.py", language="python"))
        graph.add_node(GraphNode(file_path="/b.py", language="python"))
        graph.add_edge(GraphEdge(source="/a.py", target="/b.py"))
        graph.add_edge(GraphEdge(source="/b.py", target="/a.py"))

        graph.find_circular_dependencies()

        formatter = MermaidFormatter()
        output = formatter.format(graph)

        assert "linkStyle" in output
        assert "stroke:red" in output

    def test_node_id_sanitization(self):
        """Test file paths are converted to valid node IDs."""
        graph = DependencyGraph()
        graph.add_node(GraphNode(file_path="/project/src/utils.py", language="python"))
        formatter = MermaidFormatter()

        output = formatter.format(graph)

        # Path should be converted to valid ID
        assert "n_project_src_utils_py" in output or "_project_src_utils_py" in output

    def test_node_id_starts_with_letter(self):
        """Test node IDs starting with numbers get prefix."""
        graph = DependencyGraph()
        graph.add_node(GraphNode(file_path="/123test.py", language="python"))
        formatter = MermaidFormatter()

        output = formatter.format(graph)

        # Should start with 'n'
        assert "n_123test_py" in output or "n123test_py" in output
