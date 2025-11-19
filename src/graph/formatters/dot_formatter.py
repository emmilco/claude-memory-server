"""DOT (Graphviz) formatter for dependency graphs."""

from typing import Dict
from pathlib import Path
from ..dependency_graph import DependencyGraph, GraphNode, GraphEdge


class DOTFormatter:
    """
    Format dependency graph as Graphviz DOT language.

    DOT format is used by Graphviz tools for graph visualization.
    Supports:
    - Node metadata in tooltips and labels
    - Circular dependencies highlighted in red
    - Language-based node colors
    - File size and unit count in labels
    """

    LANGUAGE_COLORS = {
        "python": "#3776ab",
        "javascript": "#f7df1e",
        "typescript": "#3178c6",
        "java": "#007396",
        "go": "#00add8",
        "rust": "#dea584",
        "ruby": "#cc342d",
        "c": "#a8b9cc",
        "c++": "#f34b7d",
        "c#": "#68217a",
        "php": "#777bb4",
        "swift": "#ffac45",
        "kotlin": "#a97bff",
    }

    DEFAULT_COLOR = "#gray"

    def __init__(self, include_metadata: bool = True):
        """
        Initialize DOT formatter.

        Args:
            include_metadata: Include file size, unit count in node labels
        """
        self.include_metadata = include_metadata

    def format(self, graph: DependencyGraph, title: str = "Dependency Graph") -> str:
        """
        Format graph as DOT syntax.

        Args:
            graph: DependencyGraph to format
            title: Graph title for label

        Returns:
            String containing valid DOT syntax
        """
        lines = [
            f'digraph "{title}" {{',
            '  // Graph settings',
            '  rankdir=LR;',  # Left to right layout
            '  node [shape=box, style=filled, fontname="Arial"];',
            '  edge [fontname="Arial", fontsize=10];',
            '',
            '  // Nodes',
        ]

        # Add nodes
        for file_path, node in graph.nodes.items():
            lines.append(self._format_node(file_path, node))

        lines.append('')
        lines.append('  // Edges')

        # Add edges
        for edge in graph.edges:
            lines.append(self._format_edge(edge))

        lines.append('}')
        return '\n'.join(lines)

    def _format_node(self, file_path: str, node: GraphNode) -> str:
        """
        Format a single node in DOT syntax.

        Args:
            file_path: File path (used as node ID)
            node: GraphNode with metadata

        Returns:
            DOT node definition string
        """
        # Use filename for display
        filename = Path(file_path).name

        # Build label
        if self.include_metadata and node.unit_count > 0:
            # Format file size
            if node.file_size < 1024:
                size_str = f"{node.file_size}B"
            elif node.file_size < 1024 * 1024:
                size_str = f"{node.file_size / 1024:.1f}KB"
            else:
                size_str = f"{node.file_size / (1024 * 1024):.1f}MB"

            label = f"{filename}\\n{node.unit_count} units, {size_str}"
        else:
            label = filename

        # Get color for language
        color = self.LANGUAGE_COLORS.get(
            node.language.lower(), self.DEFAULT_COLOR
        )

        # Build tooltip with full info
        tooltip = self._escape_dot_string(file_path)
        if self.include_metadata:
            tooltip += f"\\nLanguage: {node.language}"
            if node.unit_count > 0:
                tooltip += f"\\nUnits: {node.unit_count}"
            if node.file_size > 0:
                tooltip += f"\\nSize: {node.file_size} bytes"
            if node.last_modified:
                tooltip += f"\\nModified: {node.last_modified}"

        # Use simplified file path as ID (replace slashes and dots)
        node_id = self._make_node_id(file_path)

        return (
            f'  {node_id} [label="{self._escape_dot_string(label)}", '
            f'fillcolor="{color}", tooltip="{tooltip}"];'
        )

    def _format_edge(self, edge: GraphEdge) -> str:
        """
        Format a single edge in DOT syntax.

        Args:
            edge: GraphEdge with source, target, and circular flag

        Returns:
            DOT edge definition string
        """
        source_id = self._make_node_id(edge.source)
        target_id = self._make_node_id(edge.target)

        if edge.circular:
            # Highlight circular dependencies in red with label
            return (
                f'  {source_id} -> {target_id} '
                f'[color=red, penwidth=2.0, label="circular"];'
            )
        else:
            return f'  {source_id} -> {target_id};'

    def _make_node_id(self, file_path: str) -> str:
        """
        Create a valid DOT node ID from file path.

        Args:
            file_path: File path

        Returns:
            Valid DOT identifier (alphanumeric with underscores)
        """
        # Replace special characters with underscores
        node_id = file_path.replace('/', '_').replace('\\', '_')
        node_id = node_id.replace('.', '_').replace('-', '_')
        node_id = node_id.replace(' ', '_')

        # Ensure it starts with a letter or underscore
        if node_id and not (node_id[0].isalpha() or node_id[0] == '_'):
            node_id = 'n_' + node_id

        return node_id

    def _escape_dot_string(self, text: str) -> str:
        """
        Escape special characters in DOT strings.

        Args:
            text: Text to escape

        Returns:
            Escaped text safe for DOT syntax
        """
        # Escape backslashes first
        text = text.replace('\\', '\\\\')
        # Escape quotes
        text = text.replace('"', '\\"')
        return text
