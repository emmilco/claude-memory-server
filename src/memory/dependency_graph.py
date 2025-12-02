"""Dependency graph construction and querying."""

import logging
from pathlib import Path
from typing import Dict, List, Set, Optional, Tuple, Any
from collections import defaultdict, deque

logger = logging.getLogger(__name__)


class DependencyGraph:
    """
    Build and query dependency relationships between files.

    This class provides methods to:
    - Build file-to-file dependency graphs from import metadata
    - Query what a file depends on (dependencies)
    - Query what depends on a file (dependents/reverse dependencies)
    - Find import paths between files
    - Detect circular dependencies
    """

    def __init__(self):
        """Initialize dependency graph."""
        # Forward edges: file -> list of files it depends on
        self.dependencies: Dict[str, Set[str]] = defaultdict(set)

        # Reverse edges: file -> list of files that depend on it
        self.dependents: Dict[str, Set[str]] = defaultdict(set)

        # Import details: (source, target) -> list of import info
        self.import_details: Dict[Tuple[str, str], List[Dict[str, Any]]] = defaultdict(
            list
        )

    def add_file_dependencies(
        self,
        source_file: str,
        imports: List[Dict[str, Any]],
        project_root: Optional[Path] = None,
    ) -> None:
        """
        Add dependencies for a file based on its imports.

        Args:
            source_file: Source file path
            imports: List of import dictionaries with 'module', 'items', 'type', etc.
            project_root: Optional project root for resolving relative imports
        """
        source_file = str(Path(source_file).resolve())

        for imp in imports:
            module = imp.get("module", "")
            is_relative = imp.get("relative", False)

            # Try to resolve module to a file path
            # This is a simplified resolver - could be enhanced
            target_file = self._resolve_module_to_file(
                module, source_file, is_relative, project_root
            )

            if target_file:
                # Add forward dependency
                self.dependencies[source_file].add(target_file)

                # Add reverse dependency
                self.dependents[target_file].add(source_file)

                # Store import details
                self.import_details[(source_file, target_file)].append(
                    {
                        "module": module,
                        "items": imp.get("items", []),
                        "type": imp.get("type", "import"),
                        "line": imp.get("line", 0),
                    }
                )

    def _resolve_module_to_file(
        self,
        module: str,
        source_file: str,
        is_relative: bool,
        project_root: Optional[Path],
    ) -> Optional[str]:
        """
        Resolve a module import to a file path.

        This is a simplified implementation. A full implementation would need:
        - Language-specific module resolution rules
        - Package/library detection (skip external deps)
        - Project structure awareness

        Args:
            module: Module name/path
            source_file: Source file containing the import
            is_relative: Whether import is relative
            project_root: Project root directory

        Returns:
            Resolved file path or None if external/unresolvable
        """
        if not project_root:
            project_root = Path.cwd()

        source_path = Path(source_file)
        source_dir = source_path.parent

        # Handle relative imports (Python, JS, TS)
        if is_relative:
            if module.startswith("."):
                # Relative import: ./module or ../module
                # Remove leading dots and convert to path
                rel_path = module.lstrip(".")
                levels_up = len(module) - len(rel_path) - 1

                # Navigate up the directory tree
                target_dir = source_dir
                for _ in range(levels_up):
                    target_dir = target_dir.parent

                # Build target path
                if rel_path:
                    target_path = target_dir / rel_path.replace(".", "/")
                else:
                    target_path = target_dir

                # Try common extensions
                for ext in [".py", ".js", ".ts", ".tsx", ".jsx"]:
                    file_path = target_path.with_suffix(ext)
                    if file_path.exists() and file_path.is_relative_to(project_root):
                        return str(file_path.resolve())

                # Try as directory with __init__.py or index.js
                for init_file in ["__init__.py", "index.js", "index.ts"]:
                    file_path = target_path / init_file
                    if file_path.exists() and file_path.is_relative_to(project_root):
                        return str(file_path.resolve())

        # For absolute imports, we'd need language-specific resolution
        # For now, skip external packages and only track relative imports
        # This could be enhanced to resolve project-internal absolute imports

        return None

    def get_dependencies(self, file_path: str) -> Set[str]:
        """
        Get all files that the given file depends on (direct dependencies).

        Args:
            file_path: File path

        Returns:
            Set of file paths that this file imports
        """
        file_path = str(Path(file_path).resolve())
        return self.dependencies.get(file_path, set()).copy()

    def get_dependents(self, file_path: str) -> Set[str]:
        """
        Get all files that depend on the given file (reverse dependencies).

        Args:
            file_path: File path

        Returns:
            Set of file paths that import this file
        """
        file_path = str(Path(file_path).resolve())
        return self.dependents.get(file_path, set()).copy()

    def get_all_dependencies(self, file_path: str, max_depth: int = 10) -> Set[str]:
        """
        Get all transitive dependencies (dependencies of dependencies).

        Args:
            file_path: File path
            max_depth: Maximum depth to traverse (prevent infinite loops)

        Returns:
            Set of all files in the dependency tree
        """
        file_path = str(Path(file_path).resolve())
        visited = set()
        queue = deque([(file_path, 0)])

        while queue:
            current, depth = queue.popleft()

            if current in visited or depth > max_depth:
                continue

            visited.add(current)

            # Add direct dependencies to queue
            for dep in self.dependencies.get(current, set()):
                if dep not in visited:
                    queue.append((dep, depth + 1))

        # Remove the source file itself
        visited.discard(file_path)
        return visited

    def get_all_dependents(self, file_path: str, max_depth: int = 10) -> Set[str]:
        """
        Get all transitive dependents (dependents of dependents).

        Args:
            file_path: File path
            max_depth: Maximum depth to traverse

        Returns:
            Set of all files that transitively depend on this file
        """
        file_path = str(Path(file_path).resolve())
        visited = set()
        queue = deque([(file_path, 0)])

        while queue:
            current, depth = queue.popleft()

            if current in visited or depth > max_depth:
                continue

            visited.add(current)

            # Add dependents to queue
            for dep in self.dependents.get(current, set()):
                if dep not in visited:
                    queue.append((dep, depth + 1))

        # Remove the source file itself
        visited.discard(file_path)
        return visited

    def find_path(
        self, source: str, target: str, max_depth: int = 10
    ) -> Optional[List[str]]:
        """
        Find import path from source file to target file.

        Args:
            source: Source file path
            target: Target file path
            max_depth: Maximum path length

        Returns:
            List of file paths representing the import path, or None if no path exists
        """
        source = str(Path(source).resolve())
        target = str(Path(target).resolve())

        if source == target:
            return [source]

        # BFS to find shortest path
        queue = deque([(source, [source])])
        visited = {source}

        while queue:
            current, path = queue.popleft()

            if len(path) > max_depth:
                continue

            # Check direct dependencies
            for dep in self.dependencies.get(current, set()):
                if dep == target:
                    return path + [dep]

                if dep not in visited:
                    visited.add(dep)
                    queue.append((dep, path + [dep]))

        return None

    def detect_circular_dependencies(self) -> List[List[str]]:
        """
        Detect circular dependencies in the graph.

        Returns:
            List of circular dependency chains (cycles)
        """
        cycles = []
        visited = set()
        rec_stack = set()

        def dfs(node: str, path: List[str]) -> None:
            """DFS to detect cycles."""
            visited.add(node)
            rec_stack.add(node)
            path.append(node)

            for neighbor in self.dependencies.get(node, set()):
                if neighbor not in visited:
                    dfs(neighbor, path.copy())
                elif neighbor in rec_stack:
                    # Found cycle
                    cycle_start = path.index(neighbor)
                    cycle = path[cycle_start:] + [neighbor]
                    if cycle not in cycles:
                        cycles.append(cycle)

            rec_stack.discard(node)

        for node in self.dependencies:
            if node not in visited:
                dfs(node, [])

        return cycles

    def get_import_details(self, source: str, target: str) -> List[Dict[str, Any]]:
        """
        Get detailed import information between two files.

        Args:
            source: Source file path
            target: Target file path

        Returns:
            List of import details (what was imported, how, etc.)
        """
        source = str(Path(source).resolve())
        target = str(Path(target).resolve())
        return self.import_details.get((source, target), []).copy()

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get dependency graph statistics.

        Returns:
            Dictionary with graph metrics
        """
        total_files = len(set(self.dependencies.keys()) | set(self.dependents.keys()))
        total_edges = sum(len(deps) for deps in self.dependencies.values())

        # Find most depended-on files
        most_dependents = sorted(
            [(file, len(deps)) for file, deps in self.dependents.items()],
            key=lambda x: x[1],
            reverse=True,
        )[:10]

        # Find files with most dependencies
        most_dependencies = sorted(
            [(file, len(deps)) for file, deps in self.dependencies.items()],
            key=lambda x: x[1],
            reverse=True,
        )[:10]

        return {
            "total_files": total_files,
            "total_dependencies": total_edges,
            "average_dependencies": total_edges / total_files if total_files > 0 else 0,
            "most_depended_on": [
                {"file": Path(f).name, "dependent_count": count}
                for f, count in most_dependents
            ],
            "most_dependencies": [
                {"file": Path(f).name, "dependency_count": count}
                for f, count in most_dependencies
            ],
        }
