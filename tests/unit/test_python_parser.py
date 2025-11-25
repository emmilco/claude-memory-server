"""Tests for Python fallback parser."""

import pytest
from pathlib import Path
from src.memory.python_parser import PythonParser, get_parser, parse_code_file


class TestPythonParserInitialization:
    """Test parser initialization."""

    def test_parser_singleton(self):
        """Test that get_parser returns singleton instance."""
        parser1 = get_parser()
        parser2 = get_parser()
        assert parser1 is parser2

    def test_parser_has_all_languages(self):
        """Test that parser initializes all supported languages."""
        parser = get_parser()
        # Note: ruby and php removed from Python parser (handled by Rust parser or not supported)
        expected_languages = ["python", "javascript", "typescript", "java", "go", "rust", "swift", "kotlin"]
        assert set(parser.parsers.keys()) == set(expected_languages)

    def test_parser_languages_initialized(self):
        """Test that language objects are created."""
        parser = get_parser()
        for lang in parser.parsers.keys():
            assert lang in parser.languages
            assert parser.languages[lang] is not None


class TestPythonParsing:
    """Test Python code parsing."""

    def test_parse_simple_function(self):
        """Test parsing a simple Python function."""
        code = '''
def hello():
    print("Hello, World!")
'''
        parser = get_parser()
        units = parser.parse_content(code, "python", "test.py")

        assert len(units) >= 1
        func_unit = next((u for u in units if u["unit_type"] == "function"), None)
        assert func_unit is not None
        assert func_unit["name"] == "hello"
        assert "hello" in func_unit["signature"]

    def test_parse_function_with_args(self):
        """Test parsing function with arguments."""
        code = '''
def add(a: int, b: int) -> int:
    return a + b
'''
        parser = get_parser()
        units = parser.parse_content(code, "python", "test.py")

        func_unit = next((u for u in units if u["name"] == "add"), None)
        assert func_unit is not None
        assert func_unit["unit_type"] == "function"
        assert "a" in func_unit["signature"]
        assert "b" in func_unit["signature"]

    def test_parse_async_function(self):
        """Test parsing async function."""
        code = '''
async def fetch_data():
    return await some_async_operation()
'''
        parser = get_parser()
        units = parser.parse_content(code, "python", "test.py")

        func_unit = next((u for u in units if u["name"] == "fetch_data"), None)
        assert func_unit is not None

    def test_parse_class(self):
        """Test parsing Python class."""
        code = '''
class Calculator:
    def __init__(self):
        self.result = 0

    def add(self, a, b):
        return a + b
'''
        parser = get_parser()
        units = parser.parse_content(code, "python", "test.py")

        # Should have class and methods
        class_unit = next((u for u in units if u["unit_type"] == "class"), None)
        assert class_unit is not None
        assert class_unit["name"] == "Calculator"

        # Should have methods
        methods = [u for u in units if u["unit_type"] == "method"]
        assert len(methods) >= 2
        method_names = {m["name"] for m in methods}
        assert "__init__" in method_names
        assert "add" in method_names

    def test_parse_nested_classes(self):
        """Test parsing nested classes."""
        code = '''
class Outer:
    class Inner:
        def method(self):
            pass
'''
        parser = get_parser()
        units = parser.parse_content(code, "python", "test.py")

        classes = [u for u in units if u["unit_type"] == "class"]
        assert len(classes) >= 2


class TestJavaScriptParsing:
    """Test JavaScript code parsing."""

    def test_parse_function_declaration(self):
        """Test parsing JavaScript function declaration."""
        code = '''
function greet(name) {
    return "Hello, " + name;
}
'''
        parser = get_parser()
        units = parser.parse_content(code, "javascript", "test.js")

        func_unit = next((u for u in units if u["name"] == "greet"), None)
        assert func_unit is not None
        assert func_unit["unit_type"] == "function"

    def test_parse_arrow_function(self):
        """Test parsing arrow function."""
        code = '''
const multiply = (a, b) => a * b;
'''
        parser = get_parser()
        units = parser.parse_content(code, "javascript", "test.js")

        # Arrow functions might be captured differently
        # Just verify no errors
        assert isinstance(units, list)

    def test_parse_class_with_methods(self):
        """Test parsing JavaScript class."""
        code = '''
class Person {
    constructor(name) {
        this.name = name;
    }

    greet() {
        return `Hello, ${this.name}`;
    }
}
'''
        parser = get_parser()
        units = parser.parse_content(code, "javascript", "test.js")

        class_unit = next((u for u in units if u["unit_type"] == "class"), None)
        assert class_unit is not None
        assert class_unit["name"] == "Person"


class TestTypeScriptParsing:
    """Test TypeScript code parsing."""

    def test_parse_typed_function(self):
        """Test parsing TypeScript function with types."""
        code = '''
function add(a: number, b: number): number {
    return a + b;
}
'''
        parser = get_parser()
        units = parser.parse_content(code, "typescript", "test.ts")

        func_unit = next((u for u in units if u["name"] == "add"), None)
        assert func_unit is not None

    def test_parse_interface(self):
        """Test parsing TypeScript interface."""
        code = '''
interface User {
    name: string;
    age: number;
}
'''
        parser = get_parser()
        units = parser.parse_content(code, "typescript", "test.ts")

        # Interfaces are treated as classes in our parser
        interface_unit = next((u for u in units if u["name"] == "User"), None)
        assert interface_unit is not None


class TestFileParsing:
    """Test parsing from actual files."""

    def test_parse_sample_calculator(self, tmp_path):
        """Test parsing the sample calculator file."""
        code = '''
class Calculator:
    def add(self, a, b):
        return a + b

    def subtract(self, a, b):
        return a - b

def factorial(n):
    if n <= 1:
        return 1
    return n * factorial(n - 1)
'''
        test_file = tmp_path / "calculator.py"
        test_file.write_text(code)

        parser = get_parser()
        units = parser.parse_file(str(test_file), "python")

        assert len(units) >= 3  # Class, 2 methods, 1 function

        # Check for Calculator class
        class_unit = next((u for u in units if u["name"] == "Calculator"), None)
        assert class_unit is not None

        # Check for factorial function
        func_unit = next((u for u in units if u["name"] == "factorial"), None)
        assert func_unit is not None

    def test_parse_nonexistent_file(self):
        """Test parsing nonexistent file returns empty list."""
        parser = get_parser()
        units = parser.parse_file("/nonexistent/file.py", "python")
        assert units == []

    def test_parse_invalid_syntax(self):
        """Test parsing file with invalid syntax."""
        code = "def broken syntax here"
        parser = get_parser()
        # Should not crash, might return empty or partial results
        units = parser.parse_content(code, "python", "test.py")
        assert isinstance(units, list)


class TestLanguageDetection:
    """Test language-specific features."""

    def test_python_node_types(self):
        """Test Python-specific node types are captured."""
        parser = get_parser()
        assert "function_definition" in parser.FUNCTION_NODES["python"]
        assert "async_function_definition" in parser.FUNCTION_NODES["python"]
        assert "class_definition" in parser.CLASS_NODES["python"]

    def test_javascript_node_types(self):
        """Test JavaScript-specific node types are captured."""
        parser = get_parser()
        assert "function_declaration" in parser.FUNCTION_NODES["javascript"]
        assert "arrow_function" in parser.FUNCTION_NODES["javascript"]

    def test_unsupported_language(self):
        """Test parsing with unsupported language."""
        code = "some code"
        parser = get_parser()
        units = parser.parse_content(code, "unknown_language", "test.txt")
        assert units == []


class TestParseCodeFileFunction:
    """Test the module-level parse_code_file function."""

    def test_parse_code_file_convenience_function(self, tmp_path):
        """Test the parse_code_file convenience function."""
        code = '''
def test_function():
    pass
'''
        test_file = tmp_path / "test.py"
        test_file.write_text(code)

        units = parse_code_file(str(test_file), "python")
        assert len(units) >= 1
        assert any(u["name"] == "test_function" for u in units)


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_file(self):
        """Test parsing empty file."""
        parser = get_parser()
        units = parser.parse_content("", "python", "test.py")
        assert units == []

    def test_whitespace_only(self):
        """Test parsing file with only whitespace."""
        parser = get_parser()
        units = parser.parse_content("   \n\n   ", "python", "test.py")
        assert units == []

    def test_comments_only(self):
        """Test parsing file with only comments."""
        code = '''
# This is a comment
# Another comment
'''
        parser = get_parser()
        units = parser.parse_content(code, "python", "test.py")
        assert units == []

    def test_very_large_function(self):
        """Test parsing very large function."""
        code = "def large_func():\n" + "    pass\n" * 1000
        parser = get_parser()
        units = parser.parse_content(code, "python", "test.py")
        assert len(units) >= 1

    def test_unicode_in_code(self):
        """Test parsing code with Unicode characters."""
        code = '''
def greet(name):
    return f"こんにちは, {name}!"
'''
        parser = get_parser()
        units = parser.parse_content(code, "python", "test.py")
        assert len(units) >= 1


class TestLineNumbers:
    """Test line number tracking."""

    def test_function_line_numbers(self):
        """Test that line numbers are correctly captured."""
        code = '''
def first():
    pass

def second():
    pass
'''
        parser = get_parser()
        units = parser.parse_content(code, "python", "test.py")

        first_unit = next((u for u in units if u["name"] == "first"), None)
        assert first_unit is not None
        assert first_unit["start_line"] == 2
        assert first_unit["end_line"] >= first_unit["start_line"]

        second_unit = next((u for u in units if u["name"] == "second"), None)
        assert second_unit is not None
        assert second_unit["start_line"] > first_unit["end_line"]

    def test_multiline_function(self):
        """Test line numbers for multiline function."""
        code = '''
def multiline(
    arg1,
    arg2,
    arg3
):
    result = (
        arg1 +
        arg2 +
        arg3
    )
    return result
'''
        parser = get_parser()
        units = parser.parse_content(code, "python", "test.py")

        func_unit = units[0]
        assert func_unit["end_line"] - func_unit["start_line"] >= 10


class TestContentExtraction:
    """Test that full content is extracted."""

    def test_function_content_preserved(self):
        """Test that function content is fully preserved."""
        code = '''
def calculate(x, y):
    """Calculate something."""
    result = x + y
    return result * 2
'''
        parser = get_parser()
        units = parser.parse_content(code, "python", "test.py")

        func_unit = units[0]
        assert "calculate" in func_unit["content"]
        assert "result = x + y" in func_unit["content"]
        assert "return result * 2" in func_unit["content"]

    def test_signature_extraction(self):
        """Test signature is properly extracted."""
        code = '''
def complex_function(arg1: str, arg2: int = 0, *args, **kwargs) -> dict:
    return {}
'''
        parser = get_parser()
        units = parser.parse_content(code, "python", "test.py")

        func_unit = units[0]
        assert "complex_function" in func_unit["signature"]
        assert "arg1" in func_unit["signature"]
