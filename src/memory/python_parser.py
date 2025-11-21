"""
Python-based parser fallback using tree-sitter Python bindings.

This module provides the same interface as the Rust parser but uses
pure Python implementation. It's slower (10-20x) but has no Rust dependency.

Use this when:
- Rust is not installed
- Rust build fails
- Quick setup is prioritized over performance
"""

import logging
from typing import List, Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

# Try to import core tree-sitter only
try:
    from tree_sitter import Language, Parser
    TREE_SITTER_AVAILABLE = True
except ImportError:
    TREE_SITTER_AVAILABLE = False
    Language = None  # type: ignore
    Parser = None  # type: ignore
    logger.warning(
        "tree-sitter Python bindings not available. "
        "Install with: pip install tree-sitter tree-sitter-languages"
    )


class PythonParser:
    """Pure Python parser using tree-sitter bindings."""

    # Language mappings - module name and language function name
    # Modules are imported lazily to avoid failures if optional languages are missing
    LANGUAGE_MODULES = {
        "python": ("tree_sitter_python", "language"),
        "javascript": ("tree_sitter_javascript", "language"),
        "typescript": ("tree_sitter_typescript", "language_typescript"),
        "java": ("tree_sitter_java", "language"),
        "go": ("tree_sitter_go", "language"),
        "rust": ("tree_sitter_rust", "language"),
        "php": ("tree_sitter_php", "language_php"),  # Fixed: use language_php not language
        "ruby": ("tree_sitter_ruby", "language"),
        "swift": ("tree_sitter_swift", "language"),
        "kotlin": ("tree_sitter_kotlin", "language"),
    }

    # Node types to extract by language
    FUNCTION_NODES = {
        "python": ["function_definition", "async_function_definition"],
        "javascript": ["function_declaration", "arrow_function", "function", "method_definition"],
        "typescript": ["function_declaration", "arrow_function", "function", "method_definition"],
        "java": ["method_declaration"],
        "go": ["function_declaration", "method_declaration"],
        "rust": ["function_item"],
        "php": ["function_definition", "method_declaration"],
        "ruby": ["method", "singleton_method"],
        "swift": ["function_declaration"],
        "kotlin": ["function_declaration"],
    }

    CLASS_NODES = {
        "python": ["class_definition"],
        "javascript": ["class_declaration"],
        "typescript": ["class_declaration", "interface_declaration"],
        "java": ["class_declaration", "interface_declaration"],
        "go": ["type_declaration"],
        "rust": ["struct_item", "impl_item", "trait_item"],
        "php": ["class_declaration", "interface_declaration", "trait_declaration"],
        "ruby": ["class", "module"],
        "swift": ["class_declaration", "struct_declaration", "protocol_declaration"],
        "kotlin": ["class_declaration", "object_declaration", "interface_declaration"],
    }

    def __init__(self):
        """Initialize parser with language support."""
        if not TREE_SITTER_AVAILABLE:
            raise ImportError(
                "tree-sitter Python bindings not installed. "
                "Install with: pip install tree-sitter tree-sitter-languages"
            )

        self.parsers = {}
        self.languages = {}

        # Initialize parsers for each language - import lazily
        for lang_name, (module_name, func_name) in self.LANGUAGE_MODULES.items():
            try:
                # Lazy import the language module
                import importlib
                lang_module = importlib.import_module(module_name)
                lang_func = getattr(lang_module, func_name)
                language = Language(lang_func())
                parser = Parser(language)

                self.parsers[lang_name] = parser
                self.languages[lang_name] = language

                logger.debug(f"Initialized {lang_name} parser")
            except ImportError as e:
                # Language module not installed - skip it (not an error)
                logger.debug(f"Skipping {lang_name} parser (module not installed): {e}")
            except Exception as e:
                # Other errors - warn but continue
                logger.warning(f"Failed to initialize {lang_name} parser: {e}")

    def parse_file(self, file_path: str, language: str) -> List[Dict[str, Any]]:
        """
        Parse a code file and extract semantic units.

        Args:
            file_path: Path to file
            language: Programming language (python, javascript, etc.)

        Returns:
            List of semantic units (functions, classes, methods)
        """
        if language not in self.parsers:
            logger.warning(f"No parser available for {language}")
            return []

        try:
            # Read file
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()

            return self.parse_content(content, language, file_path)

        except Exception as e:
            logger.error(f"Error parsing {file_path}: {e}")
            return []

    def parse_content(
        self, content: str, language: str, file_path: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Parse code content and extract semantic units.

        Args:
            content: Source code content
            language: Programming language
            file_path: Optional file path for metadata

        Returns:
            List of semantic units
        """
        if language not in self.parsers:
            return []

        try:
            parser = self.parsers[language]

            # Parse the code
            tree = parser.parse(bytes(content, "utf8"))
            root_node = tree.root_node

            # Extract semantic units
            units = []

            # Extract functions
            function_nodes = self._find_nodes(
                root_node, self.FUNCTION_NODES.get(language, [])
            )
            for node in function_nodes:
                unit = self._extract_function(node, content, language, file_path)
                if unit:
                    units.append(unit)

            # Extract classes
            class_nodes = self._find_nodes(
                root_node, self.CLASS_NODES.get(language, [])
            )
            for node in class_nodes:
                unit = self._extract_class(node, content, language, file_path)
                if unit:
                    units.append(unit)

                # Extract methods from class
                method_units = self._extract_methods_from_class(
                    node, content, language, file_path
                )
                units.extend(method_units)

            return units

        except Exception as e:
            logger.error(f"Error parsing content: {e}")
            return []

    def _find_nodes(self, root_node, node_types: List[str]) -> List:
        """Find all nodes of given types."""
        nodes = []

        def traverse(node):
            if node.type in node_types:
                nodes.append(node)
            for child in node.children:
                traverse(child)

        traverse(root_node)
        return nodes

    def _extract_function(
        self, node, content: str, language: str, file_path: Optional[str]
    ) -> Optional[Dict[str, Any]]:
        """Extract function information."""
        try:
            # Get function name
            name = self._get_function_name(node, language)
            if not name:
                return None

            # Get signature
            signature = self._get_node_text(node, content)[:200]  # First 200 chars

            # Get line numbers
            start_line = node.start_point[0] + 1
            end_line = node.end_point[0] + 1

            # Get byte positions
            start_byte = node.start_byte
            end_byte = node.end_byte

            # Get full content
            full_content = self._get_node_text(node, content)

            return {
                "unit_type": "function",
                "name": name,
                "signature": signature,
                "start_line": start_line,
                "end_line": end_line,
                "start_byte": start_byte,
                "end_byte": end_byte,
                "content": full_content,
                "language": language,
                "file_path": file_path or "unknown",
            }

        except Exception as e:
            logger.debug(f"Error extracting function: {e}")
            return None

    def _extract_class(
        self, node, content: str, language: str, file_path: Optional[str]
    ) -> Optional[Dict[str, Any]]:
        """Extract class information."""
        try:
            # Get class name
            name = self._get_class_name(node, language)
            if not name:
                return None

            # Get signature (class declaration line)
            signature = self._get_node_text(node, content).split("\n")[0][:200]

            # Get line numbers
            start_line = node.start_point[0] + 1
            end_line = node.end_point[0] + 1

            # Get byte positions
            start_byte = node.start_byte
            end_byte = node.end_byte

            # Get full content
            full_content = self._get_node_text(node, content)

            return {
                "unit_type": "class",
                "name": name,
                "signature": signature,
                "start_line": start_line,
                "end_line": end_line,
                "start_byte": start_byte,
                "end_byte": end_byte,
                "content": full_content,
                "language": language,
                "file_path": file_path or "unknown",
            }

        except Exception as e:
            logger.debug(f"Error extracting class: {e}")
            return None

    def _extract_methods_from_class(
        self, class_node, content: str, language: str, file_path: Optional[str]
    ) -> List[Dict[str, Any]]:
        """Extract methods from a class."""
        methods = []

        # Find method nodes within the class
        method_types = self.FUNCTION_NODES.get(language, [])
        method_nodes = self._find_nodes(class_node, method_types)

        for node in method_nodes:
            method = self._extract_function(node, content, language, file_path)
            if method:
                method["unit_type"] = "method"
                methods.append(method)

        return methods

    def _get_function_name(self, node, language: str) -> Optional[str]:
        """Extract function name from node."""
        # Try to find identifier node
        for child in node.children:
            if child.type == "identifier":
                return child.text.decode("utf8") if child.text else None

        # Language-specific fallbacks
        if language == "python":
            for child in node.children:
                if child.type == "identifier":
                    return child.text.decode("utf8") if child.text else None

        return None

    def _get_class_name(self, node, language: str) -> Optional[str]:
        """Extract class name from node."""
        # Try to find identifier node
        for child in node.children:
            if child.type == "identifier" or child.type == "type_identifier":
                return child.text.decode("utf8") if child.text else None

        return None

    def _get_node_text(self, node, content: str) -> str:
        """Extract text content of a node."""
        start_byte = node.start_byte
        end_byte = node.end_byte
        return content[start_byte:end_byte]


# Singleton instance
_parser_instance = None


def get_parser() -> PythonParser:
    """Get or create singleton parser instance."""
    global _parser_instance
    if _parser_instance is None:
        _parser_instance = PythonParser()
    return _parser_instance


def parse_code_file(file_path: str, language: str) -> List[Dict[str, Any]]:
    """
    Parse a code file using Python fallback parser.

    This function provides the same interface as the Rust parser.

    Args:
        file_path: Path to file
        language: Programming language

    Returns:
        List of semantic units
    """
    parser = get_parser()
    return parser.parse_file(file_path, language)
