"""Call extraction from source code using language-specific parsers."""

import ast
import logging
from abc import ABC, abstractmethod
from typing import List, Optional, Set, Dict, Any
from pathlib import Path

from src.graph.call_graph import CallSite, InterfaceImplementation

logger = logging.getLogger(__name__)


class BaseCallExtractor(ABC):
    """Abstract base class for language-specific call extraction."""
    
    @abstractmethod
    def extract_calls(
        self, 
        file_path: str, 
        source_code: str,
        parse_result: Optional[Any] = None
    ) -> List[CallSite]:
        """
        Extract function calls from source code.
        
        Args:
            file_path: Path to source file
            source_code: Source code content
            parse_result: Optional pre-parsed result (from incremental_indexer)
            
        Returns:
            List of CallSite objects
        """
        pass
        
    @abstractmethod
    def extract_implementations(
        self, 
        file_path: str, 
        source_code: str
    ) -> List[InterfaceImplementation]:
        """
        Extract interface/trait implementations.
        
        Args:
            file_path: Path to source file
            source_code: Source code content
            
        Returns:
            List of InterfaceImplementation objects
        """
        pass


class PythonCallExtractor(BaseCallExtractor):
    """Extract calls from Python code using AST."""
    
    def __init__(self):
        self.current_function: Optional[str] = None
        self.current_class: Optional[str] = None
        
    def extract_calls(
        self, 
        file_path: str, 
        source_code: str,
        parse_result: Optional[Any] = None
    ) -> List[CallSite]:
        """
        Extract function calls using Python AST.
        
        Handles:
            - Direct calls: func(arg)
            - Method calls: obj.method(arg)
            - Constructor calls: MyClass(arg)
            - Async calls: await func(arg)
        """
        try:
            tree = ast.parse(source_code)
        except SyntaxError as e:
            logger.warning(f"Syntax error parsing {file_path}: {e}")
            return []
            
        calls = []
        
        # Visit all nodes in AST
        for node in ast.walk(tree):
            # Track current function/class context
            if isinstance(node, ast.FunctionDef):
                caller_name = self._get_qualified_name(node.name)
                
                # Find all Call nodes within this function
                for child in ast.walk(node):
                    if isinstance(child, ast.Call):
                        call_site = self._extract_call_site(
                            child, 
                            caller_name, 
                            file_path
                        )
                        if call_site:
                            calls.append(call_site)
            elif isinstance(node, ast.ClassDef):
                self.current_class = node.name
                
        return calls
        
    def _extract_call_site(
        self, 
        call_node: ast.Call, 
        caller_function: str, 
        file_path: str
    ) -> Optional[CallSite]:
        """Extract call site from AST Call node."""
        callee_name = self._extract_callee_name(call_node.func)
        
        if not callee_name:
            return None
            
        call_type = self._determine_call_type(call_node.func)
        
        return CallSite(
            caller_function=caller_function,
            caller_file=file_path,
            caller_line=call_node.lineno,
            callee_function=callee_name,
            callee_file=None,  # Resolved later during indexing
            call_type=call_type
        )
        
    def _extract_callee_name(self, func_node: ast.expr) -> Optional[str]:
        """Extract function name from call expression."""
        if isinstance(func_node, ast.Name):
            # Direct call: func()
            return func_node.id
        elif isinstance(func_node, ast.Attribute):
            # Method call: obj.method()
            if isinstance(func_node.value, ast.Name):
                # Simple: obj.method()
                return f"{func_node.value.id}.{func_node.attr}"
            else:
                # Chained: obj.foo.method()
                return func_node.attr
        elif isinstance(func_node, ast.Call):
            # Nested call: func()()
            return self._extract_callee_name(func_node.func)
        else:
            return None
            
    def _determine_call_type(self, func_node: ast.expr) -> str:
        """Determine the type of function call."""
        if isinstance(func_node, ast.Name):
            # Check if it's a class (constructor call)
            if func_node.id[0].isupper():
                return "constructor"
            return "direct"
        elif isinstance(func_node, ast.Attribute):
            return "method"
        elif isinstance(func_node, ast.Lambda):
            return "lambda"
        else:
            return "direct"
            
    def _get_qualified_name(self, function_name: str) -> str:
        """Get qualified function name (with class prefix if applicable)."""
        if self.current_class:
            return f"{self.current_class}.{function_name}"
        return function_name
        
    def extract_implementations(
        self, 
        file_path: str, 
        source_code: str
    ) -> List[InterfaceImplementation]:
        """
        Extract class inheritance relationships.
        
        Handles:
            - ABC inheritance: class Concrete(Abstract)
            - Multiple inheritance: class Impl(Interface1, Interface2)
            - Protocol implementations (Python 3.8+)
        """
        try:
            tree = ast.parse(source_code)
        except SyntaxError as e:
            logger.warning(f"Syntax error parsing {file_path}: {e}")
            return []
            
        implementations = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                # Get all base classes
                for base in node.bases:
                    base_name = self._extract_base_name(base)
                    if base_name:
                        # Collect all method names
                        methods = [
                            m.name for m in node.body 
                            if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))
                        ]
                        
                        implementations.append(InterfaceImplementation(
                            interface_name=base_name,
                            implementation_name=node.name,
                            file_path=file_path,
                            language="python",
                            methods=methods
                        ))
                        
        return implementations
        
    def _extract_base_name(self, base_node: ast.expr) -> Optional[str]:
        """Extract base class name from inheritance expression."""
        if isinstance(base_node, ast.Name):
            return base_node.id
        elif isinstance(base_node, ast.Attribute):
            # Handle qualified names like abc.ABC
            return base_node.attr
        else:
            return None


class JavaScriptCallExtractor(BaseCallExtractor):
    """Extract calls from JavaScript/TypeScript code."""
    
    def extract_calls(
        self, 
        file_path: str, 
        source_code: str,
        parse_result: Optional[Any] = None
    ) -> List[CallSite]:
        """Extract calls from JavaScript (placeholder for tree-sitter implementation)."""
        # TODO: Implement using tree-sitter-javascript
        logger.warning(f"JavaScript call extraction not yet implemented for {file_path}")
        return []
        
    def extract_implementations(
        self, 
        file_path: str, 
        source_code: str
    ) -> List[InterfaceImplementation]:
        """Extract class implementations from JavaScript."""
        # TODO: Implement using tree-sitter-javascript
        logger.warning(f"JavaScript implementation extraction not yet implemented for {file_path}")
        return []


def get_call_extractor(language: str) -> Optional[BaseCallExtractor]:
    """
    Get call extractor for a given language.
    
    Args:
        language: Programming language (python, javascript, typescript, etc.)
        
    Returns:
        CallExtractor instance or None if language not supported
    """
    extractors = {
        "python": PythonCallExtractor,
        "javascript": JavaScriptCallExtractor,
        "typescript": JavaScriptCallExtractor,  # Use same extractor
    }
    
    extractor_class = extractors.get(language.lower())
    if extractor_class:
        return extractor_class()
    else:
        logger.debug(f"No call extractor available for language: {language}")
        return None
