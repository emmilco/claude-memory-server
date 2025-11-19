"""Dependency graph visualization and export."""

import json
import logging
from pathlib import Path
from typing import Dict, List, Set, Optional, Any, Literal
import fnmatch
import os
from datetime import datetime

from .dependency_graph import DependencyGraph

logger = logging.getLogger(__name__)


class DependencyGraphGenerator:
    """
    Generate dependency graphs in multiple export formats.

    Supports:
    - DOT (Graphviz)
    - JSON (D3.js compatible)
    - Mermaid diagram

    Features:
    - Filtering by depth, file pattern, language
    - Circular dependency highlighting
    - Node metadata enrichment
    """

    def __init__(self, dependency_graph: DependencyGraph):
        """
        Initialize generator with a dependency graph.

        Args:
            dependency_graph: DependencyGraph instance to export
        """
        self.graph = dependency_graph

    def generate(
        self,
        format: Literal["dot", "json", "mermaid"] = "dot",
        max_depth: Optional[int] = None,
        file_pattern: Optional[str] = None,
        language: Optional[str] = None,
        include_metadata: bool = True,
        highlight_circular: bool = True,
        project_root: Optional[Path] = None
    ) -> tuple[str, Dict[str, Any]]:
        """
        Generate dependency graph in specified format.

        Args:
            format: Export format ('dot', 'json', or 'mermaid')
            max_depth: Maximum depth to include (None = unlimited)
            file_pattern: Glob pattern to filter files (e.g., "*.py")
            language: Filter by language (e.g., "python")
            include_metadata: Include file metadata (size, units, etc.)
            highlight_circular: Highlight circular dependencies
            project_root: Project root for resolving relative paths

        Returns:
            Tuple of (graph_data, stats)
        """
        # Apply filters to get subgraph
        filtered_nodes, filtered_edges = self._apply_filters(
            max_depth=max_depth,
            file_pattern=file_pattern,
            language=language,
            project_root=project_root
        )

        # Detect circular dependencies if needed
        circular_groups = []
        if highlight_circular:
            circular_groups = self._detect_circular_in_subgraph(
                filtered_nodes,
                filtered_edges
            )

        # Enrich with metadata if requested
        node_metadata = {}
        if include_metadata:
            node_metadata = self._enrich_metadata(filtered_nodes)

        # Generate in requested format
        if format == "dot":
            graph_data = self._to_dot(
                filtered_nodes,
                filtered_edges,
                node_metadata,
                circular_groups
            )
        elif format == "json":
            graph_data = self._to_json(
                filtered_nodes,
                filtered_edges,
                node_metadata,
                circular_groups
            )
        elif format == "mermaid":
            graph_data = self._to_mermaid(
                filtered_nodes,
                filtered_edges,
                node_metadata,
                circular_groups
            )
        else:
            raise ValueError(f"Unsupported format: {format}")

        # Generate statistics
        stats = {
            "node_count": len(filtered_nodes),
            "edge_count": len(filtered_edges),
            "circular_dependency_count": len(circular_groups)
        }

        return graph_data, stats, circular_groups

    def _apply_filters(
        self,
        max_depth: Optional[int],
        file_pattern: Optional[str],
        language: Optional[str],
        project_root: Optional[Path]
    ) -> tuple[Set[str], Set[tuple[str, str]]]:
        """Apply filters to get a subgraph."""
        # Start with all nodes
        all_nodes = set(self.graph.dependencies.keys()) | set(self.graph.dependents.keys())
        filtered_nodes = all_nodes.copy()

        # Apply file pattern filter
        if file_pattern:
            filtered_nodes = {
                node for node in filtered_nodes
                if fnmatch.fnmatch(Path(node).name, file_pattern) or
                   fnmatch.fnmatch(node, file_pattern)
            }

        # Apply language filter
        if language:
            filtered_nodes = {
                node for node in filtered_nodes
                if self._get_language(node) == language.lower()
            }

        # Apply depth filter (BFS from entry points)
        if max_depth is not None:
            filtered_nodes = self._filter_by_depth(filtered_nodes, max_depth)

        # Get edges for filtered nodes
        filtered_edges = set()
        for source in filtered_nodes:
            for target in self.graph.dependencies.get(source, set()):
                if target in filtered_nodes:
                    filtered_edges.add((source, target))

        return filtered_nodes, filtered_edges

    def _filter_by_depth(self, nodes: Set[str], max_depth: int) -> Set[str]:
        """
        Filter nodes by depth using BFS from entry points.

        Entry points are nodes with no dependencies (imports nothing).
        """
        from collections import deque

        # Find entry points (files with no dependencies)
        entry_points = {
            node for node in nodes
            if not self.graph.dependencies.get(node, set())
        }

        # If no entry points, use all nodes as entry points
        if not entry_points:
            entry_points = nodes

        # BFS from entry points
        visited = set()
        queue = deque([(node, 0) for node in entry_points])

        while queue:
            current, depth = queue.popleft()

            if current in visited or depth > max_depth:
                continue

            visited.add(current)

            # Add dependents (files that import this one)
            for dependent in self.graph.dependents.get(current, set()):
                if dependent in nodes and dependent not in visited:
                    queue.append((dependent, depth + 1))

        return visited

    def _detect_circular_in_subgraph(
        self,
        nodes: Set[str],
        edges: Set[tuple[str, str]]
    ) -> List[List[str]]:
        """Detect circular dependencies in filtered subgraph."""
        # Build adjacency list for subgraph
        adj = {node: set() for node in nodes}
        for source, target in edges:
            adj[source].add(target)

        # DFS to find cycles
        cycles = []
        visited = set()
        rec_stack = set()

        def dfs(node: str, path: List[str]) -> None:
            """DFS to detect cycles."""
            visited.add(node)
            rec_stack.add(node)
            path.append(node)

            for neighbor in adj.get(node, set()):
                if neighbor not in visited:
                    dfs(neighbor, path.copy())
                elif neighbor in rec_stack:
                    # Found cycle
                    cycle_start = path.index(neighbor)
                    cycle = path[cycle_start:]
                    if cycle not in cycles and len(cycle) > 1:
                        cycles.append(cycle)

            rec_stack.discard(node)

        for node in nodes:
            if node not in visited:
                dfs(node, [])

        return cycles

    def _enrich_metadata(self, nodes: Set[str]) -> Dict[str, Dict[str, Any]]:
        """Enrich nodes with metadata."""
        metadata = {}

        for node in nodes:
            node_meta = {}

            # File size
            try:
                if os.path.exists(node):
                    node_meta["size"] = os.path.getsize(node)
                else:
                    node_meta["size"] = 0
            except Exception:
                node_meta["size"] = 0

            # Language
            node_meta["language"] = self._get_language(node)

            # File name
            node_meta["name"] = Path(node).name

            # Last modified
            try:
                if os.path.exists(node):
                    mtime = os.path.getmtime(node)
                    node_meta["last_modified"] = datetime.fromtimestamp(mtime).isoformat()
                else:
                    node_meta["last_modified"] = None
            except Exception:
                node_meta["last_modified"] = None

            metadata[node] = node_meta

        return metadata

    def _get_language(self, file_path: str) -> str:
        """Detect language from file extension."""
        ext = Path(file_path).suffix.lower()

        language_map = {
            ".py": "python",
            ".js": "javascript",
            ".jsx": "javascript",
            ".ts": "typescript",
            ".tsx": "typescript",
            ".java": "java",
            ".go": "go",
            ".rs": "rust",
            ".c": "c",
            ".h": "c",
            ".cpp": "cpp",
            ".cxx": "cpp",
            ".cc": "cpp",
            ".hpp": "cpp",
            ".cs": "csharp",
            ".sql": "sql",
            ".json": "json",
            ".yaml": "yaml",
            ".yml": "yaml",
            ".toml": "toml",
        }

        return language_map.get(ext, "unknown")

    def _to_dot(
        self,
        nodes: Set[str],
        edges: Set[tuple[str, str]],
        metadata: Dict[str, Dict[str, Any]],
        circular_groups: List[List[str]]
    ) -> str:
        """Export to DOT format (Graphviz)."""
        lines = ["digraph dependencies {"]
        lines.append("    rankdir=LR;")
        lines.append("    node [shape=box];")
        lines.append("")

        # Identify nodes in circular dependencies
        circular_nodes = set()
        for group in circular_groups:
            circular_nodes.update(group)

        # Add nodes
        for node in sorted(nodes):
            name = Path(node).name
            meta = metadata.get(node, {})

            # Build label
            label_parts = [name]
            if meta.get("size"):
                size_kb = meta["size"] / 1024
                label_parts.append(f"{size_kb:.1f}KB")

            label = "\\n".join(label_parts)

            # Styling
            attrs = [f'label="{label}"']
            if node in circular_nodes:
                attrs.append('style=filled')
                attrs.append('fillcolor="#ff9999"')
            else:
                attrs.append('style=filled')
                attrs.append('fillcolor=lightblue')

            node_id = self._sanitize_dot_id(node)
            lines.append(f'    "{node_id}" [{", ".join(attrs)}];')

        lines.append("")

        # Add edges
        circular_edges = set()
        for group in circular_groups:
            for i, node in enumerate(group):
                next_node = group[(i + 1) % len(group)]
                circular_edges.add((node, next_node))

        for source, target in sorted(edges):
            source_id = self._sanitize_dot_id(source)
            target_id = self._sanitize_dot_id(target)

            if (source, target) in circular_edges:
                lines.append(f'    "{source_id}" -> "{target_id}" [color=red, penwidth=2];')
            else:
                lines.append(f'    "{source_id}" -> "{target_id}";')

        lines.append("}")

        return "\n".join(lines)

    def _sanitize_dot_id(self, path: str) -> str:
        """Sanitize path for DOT format."""
        # Use file name for shorter IDs
        return Path(path).name

    def _to_json(
        self,
        nodes: Set[str],
        edges: Set[tuple[str, str]],
        metadata: Dict[str, Dict[str, Any]],
        circular_groups: List[List[str]]
    ) -> str:
        """Export to JSON format (D3.js compatible)."""
        # Build nodes array
        nodes_array = []
        for node in sorted(nodes):
            meta = metadata.get(node, {})
            nodes_array.append({
                "id": node,
                "label": Path(node).name,
                "size": meta.get("size", 0),
                "language": meta.get("language", "unknown"),
                "last_modified": meta.get("last_modified"),
            })

        # Build links array
        links_array = []
        for source, target in sorted(edges):
            links_array.append({
                "source": source,
                "target": target,
                "type": "import"
            })

        # Build circular groups
        circular_array = [
            [node for node in group]
            for group in circular_groups
        ]

        # Combine into graph
        graph = {
            "nodes": nodes_array,
            "links": links_array,
            "circular_groups": circular_array
        }

        return json.dumps(graph, indent=2)

    def _to_mermaid(
        self,
        nodes: Set[str],
        edges: Set[tuple[str, str]],
        metadata: Dict[str, Dict[str, Any]],
        circular_groups: List[List[str]]
    ) -> str:
        """Export to Mermaid diagram format."""
        lines = ["graph LR"]

        # Create node ID mapping (A, B, C, etc.)
        node_ids = {}
        for i, node in enumerate(sorted(nodes)):
            node_ids[node] = chr(65 + i) if i < 26 else f"N{i}"

        # Identify circular nodes
        circular_nodes = set()
        for group in circular_groups:
            circular_nodes.update(group)

        # Add edges (this also defines nodes)
        circular_edges = set()
        for group in circular_groups:
            for i, node in enumerate(group):
                next_node = group[(i + 1) % len(group)]
                circular_edges.add((node, next_node))

        for source, target in sorted(edges):
            source_id = node_ids[source]
            target_id = node_ids[target]
            source_name = Path(source).name
            target_name = Path(target).name

            # Get metadata for labels
            source_meta = metadata.get(source, {})
            target_meta = metadata.get(target, {})

            # Build labels with metadata
            source_label = source_name
            if source_meta.get("size"):
                size_kb = source_meta["size"] / 1024
                source_label += f"<br/>{size_kb:.1f}KB"

            target_label = target_name
            if target_meta.get("size"):
                size_kb = target_meta["size"] / 1024
                target_label += f"<br/>{size_kb:.1f}KB"

            # Use dashed line for circular dependencies
            if (source, target) in circular_edges:
                lines.append(f"    {source_id}[{source_label}] -.-> {target_id}[{target_label}]")
            else:
                lines.append(f"    {source_id}[{source_label}] --> {target_id}[{target_label}]")

        # Add styling for circular nodes
        lines.append("")
        lines.append("    %% Circular dependency styling")
        for node in sorted(circular_nodes):
            node_id = node_ids[node]
            lines.append(f"    style {node_id} fill:#ff9999")

        return "\n".join(lines)
