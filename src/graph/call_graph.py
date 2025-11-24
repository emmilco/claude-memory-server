"""Call graph module for analyzing function relationships and call chains."""

from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional, Tuple, Deque
from collections import deque, defaultdict
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


@dataclass
class CallSite:
    """
    Represents a function call location.
    
    Attributes:
        caller_function: Function making the call
        caller_file: File containing caller
        caller_line: Line number of call
        callee_function: Function being called
        callee_file: File containing callee (if resolved)
        call_type: Type of call (direct, method, constructor, lambda)
    """
    caller_function: str
    caller_file: str
    caller_line: int
    callee_function: str
    callee_file: Optional[str] = None
    call_type: str = "direct"


@dataclass
class FunctionNode:
    """
    Node in call graph representing a function.
    
    Attributes:
        name: Function/method name
        qualified_name: Full path (e.g., "MyClass.method")
        file_path: Source file
        language: Programming language
        start_line: Function start line
        end_line: Function end line
        is_exported: Whether function is exported/public
        is_async: Async/coroutine function
        parameters: Parameter names
        return_type: Return type hint (if available)
    """
    name: str
    qualified_name: str
    file_path: str
    language: str
    start_line: int
    end_line: int
    is_exported: bool = False
    is_async: bool = False
    parameters: List[str] = field(default_factory=list)
    return_type: Optional[str] = None


@dataclass
class InterfaceImplementation:
    """
    Tracks interface/trait/abstract class implementations.
    
    Attributes:
        interface_name: Interface/trait/abstract class name
        implementation_name: Concrete implementation class name
        file_path: File containing implementation
        language: Programming language
        methods: Implemented method names
    """
    interface_name: str
    implementation_name: str
    file_path: str
    language: str
    methods: List[str] = field(default_factory=list)


class CallGraph:
    """
    Call graph for analyzing function relationships.
    
    Data Structures:
        nodes: Dict[str, FunctionNode] - All functions indexed by qualified name
        calls: List[CallSite] - All function calls
        forward_index: Dict[str, Set[str]] - function -> {functions it calls}
        reverse_index: Dict[str, Set[str]] - function -> {functions calling it}
        implementations: Dict[str, List[InterfaceImplementation]] - interface -> implementations
    """
    
    def __init__(self):
        self.nodes: Dict[str, FunctionNode] = {}
        self.calls: List[CallSite] = []
        self.forward_index: Dict[str, Set[str]] = defaultdict(set)  # caller -> callees
        self.reverse_index: Dict[str, Set[str]] = defaultdict(set)  # callee -> callers
        self.implementations: Dict[str, List[InterfaceImplementation]] = defaultdict(list)
        
    def add_function(self, node: FunctionNode) -> None:
        """
        Add function to call graph.
        
        Args:
            node: Function node to add
        """
        self.nodes[node.qualified_name] = node
        logger.debug(f"Added function node: {node.qualified_name}")
        
    def add_call(self, call_site: CallSite) -> None:
        """
        Add function call relationship.
        
        Args:
            call_site: Call site to add
        """
        self.calls.append(call_site)
        
        # Update forward index (caller -> callee)
        self.forward_index[call_site.caller_function].add(call_site.callee_function)
        
        # Update reverse index (callee -> caller)
        self.reverse_index[call_site.callee_function].add(call_site.caller_function)
        
        logger.debug(f"Added call: {call_site.caller_function} -> {call_site.callee_function}")
        
    def add_implementation(self, impl: InterfaceImplementation) -> None:
        """
        Add interface implementation relationship.
        
        Args:
            impl: Interface implementation to add
        """
        self.implementations[impl.interface_name].append(impl)
        logger.debug(f"Added implementation: {impl.implementation_name} implements {impl.interface_name}")
        
    def find_callers(
        self, 
        function_name: str, 
        include_indirect: bool = False, 
        max_depth: int = 1
    ) -> List[FunctionNode]:
        """
        Find all functions calling the given function.
        
        Args:
            function_name: Function name to search for
            include_indirect: If True, include transitive callers
            max_depth: Maximum depth for indirect callers
            
        Returns:
            List of FunctionNode objects that call this function
        """
        if not include_indirect or max_depth == 1:
            # Direct callers only
            caller_names = self.reverse_index.get(function_name, set())
            return [self.nodes[name] for name in caller_names if name in self.nodes]
        else:
            # Transitive callers using BFS
            all_callers = self._find_callers_bfs(function_name, max_depth)
            return [self.nodes[name] for name in all_callers if name in self.nodes]
            
    def _find_callers_bfs(self, function_name: str, max_depth: int) -> Set[str]:
        """
        Find all transitive callers using BFS.
        
        Args:
            function_name: Starting function
            max_depth: Maximum depth to traverse
            
        Returns:
            Set of caller function names
        """
        visited = set()
        queue: Deque[Tuple[str, int]] = deque([(function_name, 0)])
        
        while queue:
            current, depth = queue.popleft()
            
            if depth >= max_depth:
                continue
                
            for caller in self.reverse_index.get(current, set()):
                if caller not in visited:
                    visited.add(caller)
                    queue.append((caller, depth + 1))
                    
        visited.discard(function_name)  # Remove the original function
        return visited
        
    def find_callees(
        self, 
        function_name: str, 
        include_indirect: bool = False, 
        max_depth: int = 1
    ) -> List[FunctionNode]:
        """
        Find all functions called by the given function.
        
        Args:
            function_name: Function name to analyze
            include_indirect: If True, include transitive callees
            max_depth: Maximum depth for indirect callees
            
        Returns:
            List of FunctionNode objects called by this function
        """
        if not include_indirect or max_depth == 1:
            # Direct callees only
            callee_names = self.forward_index.get(function_name, set())
            return [self.nodes[name] for name in callee_names if name in self.nodes]
        else:
            # Transitive callees using BFS
            all_callees = self._find_callees_bfs(function_name, max_depth)
            return [self.nodes[name] for name in all_callees if name in self.nodes]
            
    def _find_callees_bfs(self, function_name: str, max_depth: int) -> Set[str]:
        """
        Find all transitive callees using BFS.
        
        Args:
            function_name: Starting function
            max_depth: Maximum depth to traverse
            
        Returns:
            Set of callee function names
        """
        visited = set()
        queue: Deque[Tuple[str, int]] = deque([(function_name, 0)])
        
        while queue:
            current, depth = queue.popleft()
            
            if depth >= max_depth:
                continue
                
            for callee in self.forward_index.get(current, set()):
                if callee not in visited:
                    visited.add(callee)
                    queue.append((callee, depth + 1))
                    
        visited.discard(function_name)  # Remove the original function
        return visited
        
    def find_call_chain(
        self, 
        from_func: str, 
        to_func: str, 
        max_depth: int = 10,
        max_paths: int = 5
    ) -> List[List[str]]:
        """
        Find all call paths from from_func to to_func using BFS.
        
        Args:
            from_func: Starting function name
            to_func: Target function name
            max_depth: Maximum path length (prevent infinite loops)
            max_paths: Maximum number of paths to return
            
        Returns:
            List of paths, where each path is a list of function names.
            Example: [["main", "process", "validate"], ["main", "handle", "validate"]]
            
        Algorithm:
            1. Initialize queue with starting node
            2. BFS to find all paths
            3. Return up to max_paths shortest paths
        """
        if from_func not in self.nodes or to_func not in self.nodes:
            logger.warning(f"Cannot find call chain: {from_func} or {to_func} not in graph")
            return []
            
        paths = []
        queue: Deque[Tuple[str, List[str]]] = deque([(from_func, [from_func])])
        
        while queue and len(paths) < max_paths:
            current_func, path = queue.popleft()
            
            # Found target
            if current_func == to_func:
                paths.append(path)
                continue
                
            # Depth limit
            if len(path) >= max_depth:
                continue
                
            # Explore callees
            for callee in self.forward_index.get(current_func, set()):
                # Avoid cycles
                if callee not in path:
                    queue.append((callee, path + [callee]))
                    
        return paths
        
    def get_call_sites_for_caller(self, caller_function: str) -> List[CallSite]:
        """
        Get all call sites from a specific caller function.
        
        Args:
            caller_function: Caller function name
            
        Returns:
            List of CallSite objects
        """
        return [cs for cs in self.calls if cs.caller_function == caller_function]
        
    def get_call_sites_for_callee(self, callee_function: str) -> List[CallSite]:
        """
        Get all call sites to a specific callee function.
        
        Args:
            callee_function: Callee function name
            
        Returns:
            List of CallSite objects
        """
        return [cs for cs in self.calls if cs.callee_function == callee_function]
        
    def get_implementations(self, interface_name: str) -> List[InterfaceImplementation]:
        """
        Get all implementations of an interface.
        
        Args:
            interface_name: Interface name
            
        Returns:
            List of InterfaceImplementation objects
        """
        return self.implementations.get(interface_name, [])
        
    def get_statistics(self) -> Dict[str, int]:
        """
        Get call graph statistics.
        
        Returns:
            Dictionary with statistics
        """
        return {
            "total_functions": len(self.nodes),
            "total_calls": len(self.calls),
            "total_interfaces": len(self.implementations),
            "total_implementations": sum(len(impls) for impls in self.implementations.values()),
        }
