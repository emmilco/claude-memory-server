"""JSON formatter for dependency graphs (D3.js compatible)."""

import json
from typing import Dict, List, Any
from ..dependency_graph import DependencyGraph, GraphNode, GraphEdge


class JSONFormatter:
    """
    Format dependency graph as JSON for D3.js visualization.

    Output structure:
    {
        "nodes": [{"id": "file.py", "language": "Python", ...}],
        "links": [{"source": "file1.py", "target": "file2.py", ...}]
    }

    This format is compatible with D3.js force-directed graph layouts.
    """

    def __init__(self, include_metadata: bool = True):
        """
        Initialize JSON formatter.

        Args:
            include_metadata: Include full metadata in nodes
        """
        self.include_metadata = include_metadata

    def format(self, graph: DependencyGraph, title: str = "Dependency Graph") -> str:
        """
        Format graph as JSON.

        Args:
            graph: DependencyGraph to format
            title: Graph title (included in output metadata)

        Returns:
            JSON string with nodes and links
        """
        data = self._build_json_structure(graph, title)
        return json.dumps(data, indent=2, ensure_ascii=False)

    def _build_json_structure(
        self, graph: DependencyGraph, title: str
    ) -> Dict[str, Any]:
        """
        Build JSON data structure.

        Args:
            graph: DependencyGraph to convert
            title: Graph title

        Returns:
            Dictionary with nodes, links, and metadata
        """
        # Build nodes array
        nodes = []
        for file_path, node in graph.nodes.items():
            node_data = self._format_node(file_path, node)
            nodes.append(node_data)

        # Build links array
        links = []
        for edge in graph.edges:
            link_data = self._format_edge(edge)
            links.append(link_data)

        # Get graph statistics
        stats = graph.get_stats()

        # Build complete structure
        return {
            "metadata": {
                "title": title,
                "node_count": stats["node_count"],
                "edge_count": stats["edge_count"],
                "circular_dependencies": stats["circular_dependency_count"],
                "max_depth": stats["max_depth"],
            },
            "nodes": nodes,
            "links": links,
        }

    def _format_node(self, file_path: str, node: GraphNode) -> Dict[str, Any]:
        """
        Format a single node as JSON object.

        Args:
            file_path: File path (used as node ID)
            node: GraphNode with metadata

        Returns:
            Dictionary with node properties
        """
        node_data: Dict[str, Any] = {
            "id": file_path,
            "language": node.language,
        }

        if self.include_metadata:
            if node.unit_count > 0:
                node_data["unit_count"] = node.unit_count
            if node.file_size > 0:
                node_data["file_size"] = node.file_size
            if node.last_modified:
                node_data["last_modified"] = node.last_modified

        return node_data

    def _format_edge(self, edge: GraphEdge) -> Dict[str, Any]:
        """
        Format a single edge as JSON object.

        Args:
            edge: GraphEdge with source, target, and flags

        Returns:
            Dictionary with edge properties
        """
        link_data: Dict[str, Any] = {
            "source": edge.source,
            "target": edge.target,
        }

        if edge.circular:
            link_data["circular"] = True

        if edge.import_type:
            link_data["type"] = edge.import_type

        return link_data

    def format_with_positions(
        self,
        graph: DependencyGraph,
        positions: Dict[str, Dict[str, float]],
        title: str = "Dependency Graph",
    ) -> str:
        """
        Format graph with pre-computed positions.

        This is useful for static layouts where node positions
        have been calculated by an external tool.

        Args:
            graph: DependencyGraph to format
            positions: Dictionary mapping file_path to {x: float, y: float}
            title: Graph title

        Returns:
            JSON string with nodes (including x, y), links, and metadata
        """
        data = self._build_json_structure(graph, title)

        # Add positions to nodes
        for node in data["nodes"]:
            file_path = node["id"]
            if file_path in positions:
                node["x"] = positions[file_path]["x"]
                node["y"] = positions[file_path]["y"]

        return json.dumps(data, indent=2, ensure_ascii=False)
