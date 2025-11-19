"""Dependency graph module for visualizing code dependencies."""

from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional, Tuple
from pathlib import Path
from enum import Enum
import fnmatch


class NodeColor(str, Enum):
    """Node colors based on state."""
    WHITE = "white"  # Not visited
    GRAY = "gray"    # Currently visiting (in recursion stack)
    BLACK = "black"  # Fully processed


@dataclass
class GraphNode:
    """
    Node in dependency graph representing a source file.

    Attributes:
        file_path: Path to the source file
        language: Programming language (Python, JavaScript, etc.)
        unit_count: Number of code units (functions, classes)
        file_size: File size in bytes
        last_modified: Last modification timestamp (ISO format)
    """
    file_path: str
    language: str
    unit_count: int = 0
    file_size: int = 0
    last_modified: str = ""


@dataclass
class GraphEdge:
    """
    Edge in dependency graph representing an import relationship.

    Attributes:
        source: Importing file path
        target: Imported file path
        import_type: Type of import (optional, e.g., "standard", "relative")
        circular: Flag indicating if this edge is part of a circular dependency
    """
    source: str
    target: str
    import_type: Optional[str] = None
    circular: bool = False


@dataclass
class CircularDependency:
    """
    Represents a circular dependency cycle.

    Attributes:
        cycle: List of file paths forming the cycle
        length: Number of files in the cycle
    """
    cycle: List[str]
    length: int = field(init=False)

    def __post_init__(self):
        self.length = len(self.cycle)


class DependencyGraph:
    """
    Dependency graph for codebase visualization.

    This class represents a directed graph where:
    - Nodes are source files
    - Edges are import/dependency relationships

    Supports:
    - Circular dependency detection
    - Filtering by depth, file pattern, language
    - Export to various formats (DOT, JSON, Mermaid)
    """

    def __init__(self):
        """Initialize empty dependency graph."""
        self.nodes: Dict[str, GraphNode] = {}
        self.edges: List[GraphEdge] = []
        self._adjacency_list: Dict[str, List[str]] = {}  # file_path -> [imported files]
        self._circular_deps: Optional[List[CircularDependency]] = None

    def add_node(self, node: GraphNode) -> None:
        """
        Add a node to the graph.

        Args:
            node: GraphNode to add

        Note:
            If a node with the same file_path already exists, it will be replaced.
        """
        self.nodes[node.file_path] = node
        if node.file_path not in self._adjacency_list:
            self._adjacency_list[node.file_path] = []

    def add_edge(self, edge: GraphEdge) -> None:
        """
        Add an edge to the graph.

        Args:
            edge: GraphEdge to add

        Note:
            Automatically ensures both source and target nodes exist in adjacency list.
        """
        self.edges.append(edge)

        # Ensure nodes exist in adjacency list
        if edge.source not in self._adjacency_list:
            self._adjacency_list[edge.source] = []
        if edge.target not in self._adjacency_list:
            self._adjacency_list[edge.target] = []

        # Add edge to adjacency list
        if edge.target not in self._adjacency_list[edge.source]:
            self._adjacency_list[edge.source].append(edge.target)

    def find_circular_dependencies(self) -> List[CircularDependency]:
        """
        Find all circular dependencies using depth-first search.

        Uses the white-gray-black algorithm:
        - White: not visited
        - Gray: currently visiting (in recursion stack)
        - Black: fully processed

        Returns:
            List of CircularDependency objects, each representing a cycle.
            Empty list if no cycles found.
        """
        if self._circular_deps is not None:
            return self._circular_deps

        color: Dict[str, NodeColor] = {
            node: NodeColor.WHITE for node in self._adjacency_list
        }
        parent: Dict[str, Optional[str]] = {node: None for node in self._adjacency_list}
        cycles: List[CircularDependency] = []

        def dfs(node: str, path: List[str]) -> None:
            """
            DFS helper to detect cycles.

            Args:
                node: Current node being visited
                path: Current path from root to this node
            """
            color[node] = NodeColor.GRAY
            path.append(node)

            for neighbor in self._adjacency_list.get(node, []):
                if color[neighbor] == NodeColor.WHITE:
                    parent[neighbor] = node
                    dfs(neighbor, path)
                elif color[neighbor] == NodeColor.GRAY:
                    # Back edge detected - cycle found
                    cycle_start_idx = path.index(neighbor)
                    cycle = path[cycle_start_idx:] + [neighbor]
                    cycles.append(CircularDependency(cycle=cycle))

            color[node] = NodeColor.BLACK
            path.pop()

        # Run DFS from each unvisited node
        for node in self._adjacency_list:
            if color[node] == NodeColor.WHITE:
                dfs(node, [])

        # Mark edges that are part of cycles
        cycle_edges: Set[Tuple[str, str]] = set()
        for cycle_obj in cycles:
            for i in range(len(cycle_obj.cycle) - 1):
                cycle_edges.add((cycle_obj.cycle[i], cycle_obj.cycle[i + 1]))

        for edge in self.edges:
            if (edge.source, edge.target) in cycle_edges:
                edge.circular = True

        self._circular_deps = cycles
        return cycles

    def filter_by_depth(self, root: str, max_depth: int) -> 'DependencyGraph':
        """
        Create subgraph with limited depth from root node.

        Uses breadth-first search to explore dependencies up to max_depth.

        Args:
            root: Root file path to start from
            max_depth: Maximum traversal depth (0 = root only, 1 = root + direct deps, etc.)

        Returns:
            New DependencyGraph containing only nodes within max_depth from root

        Raises:
            ValueError: If root node doesn't exist in graph
        """
        if root not in self.nodes:
            raise ValueError(f"Root node '{root}' not found in graph")

        # BFS to find all nodes within max_depth
        visited: Set[str] = set()
        queue: List[Tuple[str, int]] = [(root, 0)]  # (node, depth)
        visited.add(root)

        while queue:
            node, depth = queue.pop(0)

            if depth < max_depth:
                for neighbor in self._adjacency_list.get(node, []):
                    if neighbor not in visited:
                        visited.add(neighbor)
                        queue.append((neighbor, depth + 1))

        # Create filtered graph
        filtered = DependencyGraph()
        for node_path in visited:
            if node_path in self.nodes:
                filtered.add_node(self.nodes[node_path])

        for edge in self.edges:
            if edge.source in visited and edge.target in visited:
                filtered.add_edge(edge)

        return filtered

    def filter_by_pattern(self, pattern: str) -> 'DependencyGraph':
        """
        Filter graph to include only files matching pattern.

        Args:
            pattern: File pattern (supports wildcards like *.py, src/*/test.js)

        Returns:
            New DependencyGraph containing only matching nodes and their edges
        """
        # Find matching nodes
        matching_nodes: Set[str] = set()
        for file_path in self.nodes:
            if fnmatch.fnmatch(file_path, pattern) or fnmatch.fnmatch(
                Path(file_path).name, pattern
            ):
                matching_nodes.add(file_path)

        # Create filtered graph
        filtered = DependencyGraph()
        for node_path in matching_nodes:
            filtered.add_node(self.nodes[node_path])

        for edge in self.edges:
            if edge.source in matching_nodes and edge.target in matching_nodes:
                filtered.add_edge(edge)

        return filtered

    def filter_by_language(self, language: str) -> 'DependencyGraph':
        """
        Filter graph to include only files of specific language.

        Args:
            language: Programming language (case-insensitive)

        Returns:
            New DependencyGraph containing only nodes of the specified language
        """
        language_lower = language.lower()

        # Find matching nodes
        matching_nodes: Set[str] = set()
        for file_path, node in self.nodes.items():
            if node.language.lower() == language_lower:
                matching_nodes.add(file_path)

        # Create filtered graph
        filtered = DependencyGraph()
        for node_path in matching_nodes:
            filtered.add_node(self.nodes[node_path])

        for edge in self.edges:
            if edge.source in matching_nodes and edge.target in matching_nodes:
                filtered.add_edge(edge)

        return filtered

    def get_stats(self) -> Dict[str, int]:
        """
        Get graph statistics.

        Returns:
            Dictionary with:
            - node_count: Total number of nodes
            - edge_count: Total number of edges
            - circular_dependency_count: Number of circular dependencies
            - max_depth: Maximum dependency depth
        """
        circular_deps = self.find_circular_dependencies()

        # Calculate max depth using BFS from nodes with no incoming edges
        incoming_edges: Dict[str, int] = {node: 0 for node in self.nodes}
        for edge in self.edges:
            incoming_edges[edge.target] = incoming_edges.get(edge.target, 0) + 1

        roots = [node for node, count in incoming_edges.items() if count == 0]
        max_depth = 0

        for root in roots:
            queue: List[Tuple[str, int]] = [(root, 0)]
            visited: Set[str] = {root}

            while queue:
                node, depth = queue.pop(0)
                max_depth = max(max_depth, depth)

                for neighbor in self._adjacency_list.get(node, []):
                    if neighbor not in visited:
                        visited.add(neighbor)
                        queue.append((neighbor, depth + 1))

        return {
            "node_count": len(self.nodes),
            "edge_count": len(self.edges),
            "circular_dependency_count": len(circular_deps),
            "max_depth": max_depth,
        }
