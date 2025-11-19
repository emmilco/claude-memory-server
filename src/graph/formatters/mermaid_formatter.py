"""Mermaid diagram formatter for dependency graphs."""

from typing import Dict
from pathlib import Path
from ..dependency_graph import DependencyGraph, GraphNode, GraphEdge


class MermaidFormatter:
    """
    Format dependency graph as Mermaid flowchart.

    Mermaid is a JavaScript-based diagramming and charting tool that
    renders Markdown-inspired text definitions.

    Supports:
    - Flowchart LR (left-to-right) layout
    - Node metadata in labels
    - Circular dependencies with dotted lines
    - Language-based node styling
    """

    def __init__(self, include_metadata: bool = True):
        """
        Initialize Mermaid formatter.

        Args:
            include_metadata: Include file size, unit count in node labels
        """
        self.include_metadata = include_metadata

    def format(self, graph: DependencyGraph, title: str = "Dependency Graph") -> str:
        """
        Format graph as Mermaid flowchart.

        Args:
            graph: DependencyGraph to format
            title: Graph title (added as comment)

        Returns:
            String containing valid Mermaid syntax
        """
        lines = [
            f'%% {title}',
            'graph LR',  # Left-to-right flowchart
            '',
        ]

        # Add nodes with labels
        for file_path, node in graph.nodes.items():
            lines.append(self._format_node(file_path, node))

        lines.append('')

        # Add edges
        for edge in graph.edges:
            lines.append(self._format_edge(edge))

        lines.append('')

        # Add styling for circular dependencies
        lines.append('%% Styling')
        for edge in graph.edges:
            if edge.circular:
                source_id = self._make_node_id(edge.source)
                target_id = self._make_node_id(edge.target)
                lines.append(f'linkStyle {self._get_edge_index(graph, edge)} stroke:red,stroke-width:2px')

        return '\n'.join(lines)

    def _format_node(self, file_path: str, node: GraphNode) -> str:
        """
        Format a single node in Mermaid syntax.

        Args:
            file_path: File path (used as node ID)
            node: GraphNode with metadata

        Returns:
            Mermaid node definition string
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

            label = f"{filename}<br/>{node.unit_count} units, {size_str}"
        else:
            label = filename

        # Create node ID
        node_id = self._make_node_id(file_path)

        # Node with rounded box and label
        return f'  {node_id}["{label}"]'

    def _format_edge(self, edge: GraphEdge) -> str:
        """
        Format a single edge in Mermaid syntax.

        Args:
            edge: GraphEdge with source, target, and circular flag

        Returns:
            Mermaid edge definition string
        """
        source_id = self._make_node_id(edge.source)
        target_id = self._make_node_id(edge.target)

        if edge.circular:
            # Use dotted line for circular dependencies
            return f'  {source_id} -.->|circular| {target_id}'
        else:
            # Regular solid arrow
            if edge.import_type:
                return f'  {source_id} -->|{edge.import_type}| {target_id}'
            else:
                return f'  {source_id} --> {target_id}'

    def _make_node_id(self, file_path: str) -> str:
        """
        Create a valid Mermaid node ID from file path.

        Args:
            file_path: File path

        Returns:
            Valid Mermaid identifier
        """
        # Replace special characters with underscores
        node_id = file_path.replace('/', '_').replace('\\', '_')
        node_id = node_id.replace('.', '_').replace('-', '_')
        node_id = node_id.replace(' ', '_').replace('(', '_').replace(')', '_')

        # Ensure it starts with a letter
        if node_id and not node_id[0].isalpha():
            node_id = 'n' + node_id

        return node_id

    def _get_edge_index(self, graph: DependencyGraph, target_edge: GraphEdge) -> int:
        """
        Get the index of an edge in the graph's edge list.

        This is used for styling specific edges in Mermaid.

        Args:
            graph: DependencyGraph containing the edge
            target_edge: Edge to find index for

        Returns:
            Zero-based index of the edge
        """
        for i, edge in enumerate(graph.edges):
            if edge.source == target_edge.source and edge.target == target_edge.target:
                return i
        return 0
