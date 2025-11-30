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
        # Reset state for this file (prevents state leak between files)
        self.current_class = None
        self.current_function = None

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
    """Extract calls from JavaScript/TypeScript code using tree-sitter."""

    def __init__(self):
        """Initialize tree-sitter parser for JavaScript."""
        try:
            from tree_sitter import Language, Parser
            from tree_sitter_javascript import language as js_language

            self.language = Language(js_language)
            self.parser = Parser()
            self.parser.set_language(self.language)
        except ImportError as e:
            logger.error(f"Failed to initialize tree-sitter-javascript: {e}")
            self.language = None
            self.parser = None

    def extract_calls(
        self,
        file_path: str,
        source_code: str,
        parse_result: Optional[Any] = None
    ) -> List[CallSite]:
        """
        Extract function calls from JavaScript/TypeScript code using tree-sitter.

        Supports:
        - Direct calls: func(args)
        - Method calls: obj.method(args)
        - Constructor calls: new Class(args)
        - Arrow functions and async calls
        """
        if not self.parser:
            logger.warning(f"JavaScript call extraction unavailable for {file_path}: tree-sitter not initialized")
            return []

        try:
            # Parse source code
            tree = self.parser.parse(source_code.encode('utf-8'))
            calls = []

            # Query for call expressions
            self._extract_calls_from_tree(tree.root_node, source_code, file_path, calls)

            return calls
        except Exception as e:
            logger.warning(f"Error parsing JavaScript {file_path}: {e}")
            return []

    def _extract_calls_from_tree(
        self,
        node: Any,
        source_code: str,
        file_path: str,
        calls: List[CallSite],
        current_function: str = "<module>"
    ) -> None:
        """
        Recursively extract call sites from tree-sitter AST.

        Args:
            node: Current tree-sitter node
            source_code: Full source code (for line extraction)
            file_path: Source file path
            calls: List to accumulate call sites
            current_function: Current function context
        """
        # Update function context for nested functions
        if node.type in ("function_declaration", "function", "arrow_function", "method_definition"):
            func_name = self._extract_function_name(node)
            if func_name:
                current_function = func_name

        # Extract call expressions
        if node.type in ("call_expression", "member_expression"):
            call_site = self._extract_call_from_node(node, source_code, file_path, current_function)
            if call_site:
                calls.append(call_site)

        # Recurse to children
        for child in node.children:
            self._extract_calls_from_tree(child, source_code, file_path, calls, current_function)

    def _extract_function_name(self, node: Any) -> Optional[str]:
        """Extract function name from function declaration node."""
        try:
            if node.type == "function_declaration":
                # function foo() { ... }
                for child in node.children:
                    if child.type == "identifier":
                        return child.text.decode('utf-8')
            elif node.type == "method_definition":
                # method_name() { ... }
                for child in node.children:
                    if child.type == "property_identifier" or child.type == "identifier":
                        return child.text.decode('utf-8')
        except Exception:
            pass
        return None

    def _extract_call_from_node(
        self,
        node: Any,
        source_code: str,
        file_path: str,
        caller_function: str
    ) -> Optional[CallSite]:
        """
        Extract call site from call_expression or member_expression node.

        Args:
            node: Tree-sitter node
            source_code: Full source code
            file_path: Source file path
            caller_function: Current function context

        Returns:
            CallSite if extractable, None otherwise
        """
        try:
            if node.type != "call_expression":
                return None

            # Get callee (what's being called)
            callee_node = node.child_by_field_name("function")
            if not callee_node:
                return None

            callee_name = self._extract_callee_name(callee_node)
            if not callee_name:
                return None

            # Line number (1-indexed in tree-sitter)
            line_number = node.start_point[0] + 1

            # Determine call type
            call_type = "direct"
            if callee_node.type == "member_expression":
                call_type = "method"
            elif "new" in source_code[max(0, node.start_byte - 10):node.start_byte]:
                call_type = "constructor"

            return CallSite(
                caller_function=caller_function,
                caller_file=file_path,
                caller_line=line_number,
                callee_function=callee_name,
                call_type=call_type
            )
        except Exception:
            return None

    def _extract_callee_name(self, node: Any) -> Optional[str]:
        """Extract function/method name from callee node."""
        try:
            if node.type == "identifier":
                return node.text.decode('utf-8')
            elif node.type == "member_expression":
                # obj.method or obj.nested.method
                rightmost = node
                while rightmost.child_count > 0:
                    rightmost = rightmost.children[-1]
                if rightmost.type == "property_identifier" or rightmost.type == "identifier":
                    return rightmost.text.decode('utf-8')
        except Exception:
            pass
        return None

    def extract_implementations(
        self,
        file_path: str,
        source_code: str
    ) -> List[InterfaceImplementation]:
        """
        Extract class implementations from JavaScript.

        Tracks class extends relationships (ES6 class inheritance).
        """
        if not self.parser:
            logger.warning(f"JavaScript implementation extraction unavailable for {file_path}: tree-sitter not initialized")
            return []

        try:
            tree = self.parser.parse(source_code.encode('utf-8'))
            implementations = []

            self._extract_implementations_from_tree(tree.root_node, file_path, implementations)

            return implementations
        except Exception as e:
            logger.warning(f"Error parsing JavaScript {file_path}: {e}")
            return []

    def _extract_implementations_from_tree(
        self,
        node: Any,
        file_path: str,
        implementations: List[InterfaceImplementation]
    ) -> None:
        """
        Recursively extract class implementations from tree-sitter AST.

        Args:
            node: Current tree-sitter node
            file_path: Source file path
            implementations: List to accumulate implementations
        """
        if node.type == "class_declaration":
            impl = self._extract_implementation_from_class(node, file_path)
            if impl:
                implementations.append(impl)

        # Recurse to children
        for child in node.children:
            self._extract_implementations_from_tree(child, file_path, implementations)

    def _extract_implementation_from_class(
        self,
        node: Any,
        file_path: str
    ) -> Optional[InterfaceImplementation]:
        """Extract class implementation from class_declaration node."""
        try:
            # Get class name
            class_name = None
            superclass = None
            methods = []

            for child in node.children:
                if child.type == "type_identifier" or child.type == "identifier":
                    if not class_name:
                        class_name = child.text.decode('utf-8')
                elif child.type == "class_heritage":
                    # Handle extends clause
                    for heritage_child in child.children:
                        if heritage_child.type == "type_identifier" or heritage_child.type == "identifier":
                            superclass = heritage_child.text.decode('utf-8')
                elif child.type == "class_body":
                    # Extract method names
                    for body_child in child.children:
                        if body_child.type == "method_definition":
                            method_name = self._extract_method_name(body_child)
                            if method_name:
                                methods.append(method_name)

            if class_name and superclass:
                return InterfaceImplementation(
                    interface_name=superclass,
                    implementation_name=class_name,
                    file_path=file_path,
                    language="javascript",
                    methods=methods
                )
        except Exception:
            pass

        return None

    def _extract_method_name(self, node: Any) -> Optional[str]:
        """Extract method name from method_definition node."""
        try:
            for child in node.children:
                if child.type == "property_identifier" or child.type == "identifier":
                    return child.text.decode('utf-8')
        except Exception:
            pass
        return None


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
