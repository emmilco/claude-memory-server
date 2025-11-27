"""Structural query tools for call graph analysis (FEAT-059)."""

import logging
import time
from typing import Dict, Any, List, Optional
from src.core.exceptions import RetrievalError, ValidationError

logger = logging.getLogger(__name__)


class StructuralQueryMixin:
    """
    Mixin class providing structural/relational query methods for MCP server.

    These tools enable code structure analysis:
    - find_callers: Find all functions calling a given function
    - find_callees: Find all functions called by a given function
    - find_implementations: Find all implementations of an interface/trait
    - find_dependencies: Get file dependencies (what it imports)
    - find_dependents: Get reverse dependencies (what imports it)
    - get_call_chain: Show call path between two functions
    """

    async def find_callers(
        self,
        function_name: str,
        project_name: Optional[str] = None,
        include_indirect: bool = False,
        max_depth: int = 1,
        limit: int = 50,
    ) -> Dict[str, Any]:
        """
        Find all functions calling the specified function.

        **Use when:**
        - Assessing impact of changing a function
        - Understanding function usage patterns
        - Finding all entry points that lead to a function
        - Refactoring analysis (what will break if I change this?)

        Args:
            function_name: Function name to search for (qualified name like "MyClass.method")
            project_name: Project to search in (defaults to current project)
            include_indirect: If True, include transitive callers (callers of callers)
            max_depth: Maximum depth for indirect callers (default: 1=direct only)
            limit: Maximum results to return (default: 50)

        Returns:
            Dict containing:
            - function: Function name searched
            - callers: List of caller details (function, file, line, distance)
            - total_callers: Total count
            - direct_callers: Count of direct callers
            - indirect_callers: Count of indirect callers
            - analysis_time_ms: Time taken

        Example:
            ```
            result = await find_callers(
                function_name="authenticate",
                include_indirect=True,
                max_depth=3
            )
            # Returns: {"callers": [{"caller_function": "login", ...}], ...}
            ```
        """
        try:
            start_time = time.time()
            project = project_name or self.project_name

            # Load call graph from store
            from src.store.call_graph_store import QdrantCallGraphStore

            call_graph_store = QdrantCallGraphStore(self.config)
            await call_graph_store.initialize()

            # Load entire call graph for project
            call_graph = await call_graph_store.load_call_graph(project)

            # Find callers using call graph
            caller_nodes = call_graph.find_callers(
                function_name=function_name,
                include_indirect=include_indirect,
                max_depth=max_depth
            )

            # Build response with caller details
            callers = []
            for caller in caller_nodes[:limit]:
                # Get call sites for this caller
                call_sites = call_graph.get_call_sites_for_caller(caller.qualified_name)

                # Filter to sites that call our target function
                relevant_sites = [
                    cs for cs in call_sites
                    if cs.callee_function == function_name
                ]

                for site in relevant_sites:
                    callers.append({
                        "caller_function": caller.qualified_name,
                        "caller_file": caller.file_path,
                        "caller_line": site.caller_line,
                        "call_type": site.call_type,
                        "language": caller.language,
                        "is_async": caller.is_async,
                    })

            # Count direct vs indirect
            direct_count = len([
                c for c in callers
                if call_graph.reverse_index.get(function_name, set()).intersection(
                    {c["caller_function"]}
                )
            ])
            indirect_count = len(callers) - direct_count

            analysis_time_ms = (time.time() - start_time) * 1000

            logger.info(
                f"Found {len(callers)} callers for {function_name} "
                f"(direct: {direct_count}, indirect: {indirect_count}, {analysis_time_ms:.2f}ms)"
            )

            return {
                "function": function_name,
                "project": project,
                "callers": callers[:limit],
                "total_callers": len(callers),
                "direct_callers": direct_count,
                "indirect_callers": indirect_count,
                "analysis_time_ms": round(analysis_time_ms, 2),
            }

        except Exception as e:
            logger.error(f"Failed to find callers for {function_name}: {e}", exc_info=True)
            raise RetrievalError(f"Failed to find callers: {e}")

    async def find_callees(
        self,
        function_name: str,
        project_name: Optional[str] = None,
        include_indirect: bool = False,
        max_depth: int = 1,
        limit: int = 50,
    ) -> Dict[str, Any]:
        """
        Find all functions called by the specified function.

        **Use when:**
        - Understanding what a function depends on
        - Analyzing function complexity (too many calls?)
        - Finding all downstream effects of a function
        - Tracing execution flow from a starting point

        Args:
            function_name: Function name to analyze (qualified name)
            project_name: Project to search in (defaults to current project)
            include_indirect: If True, include transitive callees (callees of callees)
            max_depth: Maximum depth for indirect callees (default: 1=direct only)
            limit: Maximum results to return (default: 50)

        Returns:
            Dict containing:
            - function: Function name analyzed
            - callees: List of callee details (function, file, line, call_site_line)
            - total_callees: Total count
            - direct_callees: Count of direct callees
            - indirect_callees: Count of indirect callees
            - analysis_time_ms: Time taken

        Example:
            ```
            result = await find_callees(
                function_name="process_payment",
                include_indirect=True,
                max_depth=2
            )
            # Returns: {"callees": [{"callee_function": "validate_card", ...}], ...}
            ```
        """
        try:
            start_time = time.time()
            project = project_name or self.project_name

            # Load call graph from store
            from src.store.call_graph_store import QdrantCallGraphStore

            call_graph_store = QdrantCallGraphStore(self.config)
            await call_graph_store.initialize()

            # Load entire call graph for project
            call_graph = await call_graph_store.load_call_graph(project)

            # Find callees using call graph
            callee_nodes = call_graph.find_callees(
                function_name=function_name,
                include_indirect=include_indirect,
                max_depth=max_depth
            )

            # Get call sites from this function
            call_sites = call_graph.get_call_sites_for_caller(function_name)

            # Build response with callee details
            callees = []
            for site in call_sites[:limit]:
                # Find the callee node
                callee = call_graph.nodes.get(site.callee_function)
                if callee:
                    callees.append({
                        "callee_function": callee.qualified_name,
                        "callee_file": callee.file_path,
                        "callee_line": callee.start_line,
                        "call_site_line": site.caller_line,
                        "call_type": site.call_type,
                        "language": callee.language,
                        "is_async": callee.is_async,
                    })

            # If indirect, include transitive callees
            if include_indirect:
                for callee_node in callee_nodes:
                    if callee_node.qualified_name not in [c["callee_function"] for c in callees]:
                        callees.append({
                            "callee_function": callee_node.qualified_name,
                            "callee_file": callee_node.file_path,
                            "callee_line": callee_node.start_line,
                            "call_site_line": 0,  # Indirect call
                            "call_type": "indirect",
                            "language": callee_node.language,
                            "is_async": callee_node.is_async,
                        })

            # Count direct vs indirect
            direct_count = len([c for c in callees if c["call_type"] != "indirect"])
            indirect_count = len(callees) - direct_count

            analysis_time_ms = (time.time() - start_time) * 1000

            logger.info(
                f"Found {len(callees)} callees for {function_name} "
                f"(direct: {direct_count}, indirect: {indirect_count}, {analysis_time_ms:.2f}ms)"
            )

            return {
                "function": function_name,
                "project": project,
                "callees": callees[:limit],
                "total_callees": len(callees),
                "direct_callees": direct_count,
                "indirect_callees": indirect_count,
                "analysis_time_ms": round(analysis_time_ms, 2),
            }

        except Exception as e:
            logger.error(f"Failed to find callees for {function_name}: {e}", exc_info=True)
            raise RetrievalError(f"Failed to find callees: {e}")

    async def find_implementations(
        self,
        interface_name: str,
        project_name: Optional[str] = None,
        language: Optional[str] = None,
        limit: int = 50,
    ) -> Dict[str, Any]:
        """
        Find all implementations of an interface/trait/abstract class.

        **Use when:**
        - Finding all concrete implementations of an abstraction
        - Understanding polymorphic behavior
        - Checking interface coverage
        - Refactoring interfaces (what will be affected?)

        Args:
            interface_name: Interface, trait, or abstract class name
            project_name: Optional project filter (None = all projects)
            language: Optional language filter (python, java, rust, etc.)
            limit: Maximum results to return (default: 50)

        Returns:
            Dict containing:
            - interface: Interface name searched
            - implementations: List of implementation details
            - total_implementations: Total count
            - languages: Languages represented
            - analysis_time_ms: Time taken

        Example:
            ```
            result = await find_implementations(
                interface_name="Storage",
                language="python"
            )
            # Returns: {"implementations": [{"class_name": "RedisStorage", ...}], ...}
            ```
        """
        try:
            start_time = time.time()
            project = project_name or self.project_name

            # Load call graph from store
            from src.store.call_graph_store import QdrantCallGraphStore

            call_graph_store = QdrantCallGraphStore(self.config)
            await call_graph_store.initialize()

            # Get implementations from store
            implementations = await call_graph_store.get_implementations(
                interface_name=interface_name,
                project_name=project if project != "global" else None
            )

            # Filter by language if specified
            if language:
                implementations = [
                    impl for impl in implementations
                    if impl.language.lower() == language.lower()
                ]

            # Build response
            impl_list = []
            languages_set = set()

            for impl in implementations[:limit]:
                languages_set.add(impl.language)
                impl_list.append({
                    "class_name": impl.implementation_name,
                    "file_path": impl.file_path,
                    "language": impl.language,
                    "methods": impl.methods,
                    "method_count": len(impl.methods),
                })

            analysis_time_ms = (time.time() - start_time) * 1000

            logger.info(
                f"Found {len(impl_list)} implementations for {interface_name} "
                f"({analysis_time_ms:.2f}ms)"
            )

            return {
                "interface": interface_name,
                "project": project,
                "implementations": impl_list,
                "total_implementations": len(impl_list),
                "languages": sorted(list(languages_set)),
                "analysis_time_ms": round(analysis_time_ms, 2),
            }

        except Exception as e:
            logger.error(f"Failed to find implementations for {interface_name}: {e}", exc_info=True)
            raise RetrievalError(f"Failed to find implementations: {e}")

    async def find_dependencies(
        self,
        file_path: str,
        project_name: Optional[str] = None,
        depth: int = 1,
        include_transitive: bool = False,
    ) -> Dict[str, Any]:
        """
        Get dependency graph for a file (what it imports).

        **Use when:**
        - Understanding file dependencies
        - Checking for circular dependencies
        - Analyzing coupling
        - Planning refactoring

        Args:
            file_path: File to analyze
            project_name: Project name (defaults to current project)
            depth: Depth of dependency tree to return
            include_transitive: If True, include dependencies of dependencies

        Returns:
            Dict containing:
            - file: File path analyzed
            - dependencies: List of dependency details
            - total_dependencies: Total count
            - direct_dependencies: Count of direct dependencies
            - transitive_dependencies: Count of transitive dependencies
            - analysis_time_ms: Time taken

        Example:
            ```
            result = await find_dependencies(
                file_path="/path/to/api.py",
                include_transitive=True,
                depth=2
            )
            # Returns: {"dependencies": [{"file": "/path/to/auth.py", ...}], ...}
            ```
        """
        try:
            start_time = time.time()

            # Use existing get_file_dependencies method
            result = await self.get_file_dependencies(
                file_path=file_path,
                project_name=project_name,
                include_transitive=include_transitive
            )

            analysis_time_ms = (time.time() - start_time) * 1000

            return {
                "file": file_path,
                "project": result.get("project", project_name or self.project_name),
                "dependencies": result.get("dependencies", []),
                "total_dependencies": result.get("dependency_count", 0),
                "direct_dependencies": result.get("dependency_count", 0) if not include_transitive else len(
                    [d for d in result.get("dependencies", []) if not d.get("transitive", False)]
                ),
                "transitive_dependencies": len(
                    [d for d in result.get("dependencies", []) if d.get("transitive", False)]
                ) if include_transitive else 0,
                "analysis_time_ms": round(analysis_time_ms, 2),
            }

        except Exception as e:
            logger.error(f"Failed to find dependencies for {file_path}: {e}", exc_info=True)
            raise RetrievalError(f"Failed to find dependencies: {e}")

    async def find_dependents(
        self,
        file_path: str,
        project_name: Optional[str] = None,
        depth: int = 1,
        include_transitive: bool = False,
    ) -> Dict[str, Any]:
        """
        Get reverse dependencies for a file (what imports it).

        **Use when:**
        - Assessing impact of changing a file
        - Understanding file usage patterns
        - Finding all modules that depend on this file
        - Refactoring analysis

        Args:
            file_path: File to analyze
            project_name: Project name (defaults to current project)
            depth: Depth of dependent tree to return
            include_transitive: If True, include dependents of dependents

        Returns:
            Dict containing:
            - file: File path analyzed
            - dependents: List of dependent details
            - total_dependents: Total count
            - direct_dependents: Count of direct dependents
            - transitive_dependents: Count of transitive dependents
            - impact_radius: Impact assessment (high/medium/low)
            - analysis_time_ms: Time taken

        Example:
            ```
            result = await find_dependents(
                file_path="/path/to/auth.py",
                include_transitive=True
            )
            # Returns: {"dependents": [{"file": "/path/to/api.py", ...}], ...}
            ```
        """
        try:
            start_time = time.time()

            # Use existing get_file_dependents method
            result = await self.get_file_dependents(
                file_path=file_path,
                project_name=project_name,
                include_transitive=include_transitive
            )

            total = result.get("dependent_count", 0)

            # Determine impact radius
            if total > 20:
                impact_radius = "high"
            elif total >= 10:
                impact_radius = "medium"
            else:
                impact_radius = "low"

            analysis_time_ms = (time.time() - start_time) * 1000

            return {
                "file": file_path,
                "project": result.get("project", project_name or self.project_name),
                "dependents": result.get("dependents", []),
                "total_dependents": total,
                "direct_dependents": total if not include_transitive else len(
                    [d for d in result.get("dependents", []) if isinstance(d, str)]
                ),
                "transitive_dependents": 0 if not include_transitive else total - len(
                    [d for d in result.get("dependents", []) if isinstance(d, str)]
                ),
                "impact_radius": impact_radius,
                "analysis_time_ms": round(analysis_time_ms, 2),
            }

        except Exception as e:
            logger.error(f"Failed to find dependents for {file_path}: {e}", exc_info=True)
            raise RetrievalError(f"Failed to find dependents: {e}")

    async def get_call_chain(
        self,
        from_function: str,
        to_function: str,
        project_name: Optional[str] = None,
        max_paths: int = 5,
        max_depth: int = 10,
    ) -> Dict[str, Any]:
        """
        Show all call paths from from_function to to_function.

        **Use when:**
        - Understanding execution flow
        - Finding how one function reaches another
        - Debugging complex call chains
        - Analyzing architectural dependencies

        Args:
            from_function: Starting function name (qualified name)
            to_function: Target function name (qualified name)
            project_name: Project to search in (defaults to current project)
            max_paths: Maximum number of paths to return (default: 5)
            max_depth: Maximum path length to prevent infinite loops (default: 10)

        Returns:
            Dict containing:
            - from: Starting function
            - to: Target function
            - paths: List of call paths with details
            - total_paths: Total paths found
            - shortest_path_length: Length of shortest path
            - longest_path_length: Length of longest path
            - analysis_time_ms: Time taken

        Example:
            ```
            result = await get_call_chain(
                from_function="main",
                to_function="database_query",
                max_paths=3
            )
            # Returns: {"paths": [{"path": ["main", "process", "query"], ...}], ...}
            ```
        """
        try:
            start_time = time.time()
            project = project_name or self.project_name

            # Load call graph from store
            from src.store.call_graph_store import QdrantCallGraphStore

            call_graph_store = QdrantCallGraphStore(self.config)
            await call_graph_store.initialize()

            # Load entire call graph for project
            call_graph = await call_graph_store.load_call_graph(project)

            # Find call chains using call graph
            paths = call_graph.find_call_chain(
                from_func=from_function,
                to_func=to_function,
                max_depth=max_depth,
                max_paths=max_paths
            )

            # Build detailed path information
            path_details = []
            for path in paths:
                # Get call details for each edge in path
                call_details = []
                for i in range(len(path) - 1):
                    caller = path[i]
                    callee = path[i + 1]

                    # Find call site
                    call_sites = call_graph.get_call_sites_for_caller(caller)
                    site = next((cs for cs in call_sites if cs.callee_function == callee), None)

                    if site:
                        call_details.append({
                            "caller": caller,
                            "callee": callee,
                            "file": site.caller_file,
                            "line": site.caller_line,
                            "call_type": site.call_type,
                        })

                path_details.append({
                    "path": path,
                    "length": len(path),
                    "call_details": call_details,
                })

            # Calculate statistics
            if paths:
                shortest = min(len(p) for p in paths)
                longest = max(len(p) for p in paths)
            else:
                shortest = 0
                longest = 0

            analysis_time_ms = (time.time() - start_time) * 1000

            logger.info(
                f"Found {len(paths)} call chains from {from_function} to {to_function} "
                f"(shortest: {shortest}, longest: {longest}, {analysis_time_ms:.2f}ms)"
            )

            return {
                "from": from_function,
                "to": to_function,
                "project": project,
                "paths": path_details,
                "total_paths": len(paths),
                "shortest_path_length": shortest,
                "longest_path_length": longest,
                "analysis_time_ms": round(analysis_time_ms, 2),
            }

        except Exception as e:
            logger.error(f"Failed to find call chain from {from_function} to {to_function}: {e}", exc_info=True)
            raise RetrievalError(f"Failed to find call chain: {e}")
