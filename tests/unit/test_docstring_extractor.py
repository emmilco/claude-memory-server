"""Unit tests for docstring extraction."""

import pytest
from dataclasses import dataclass

from src.memory.docstring_extractor import (
    DocstringExtractor,
    Docstring,
    DocstringStyle,
    format_docstring_for_search,
    extract_summary,
)


# Mock SemanticUnit for testing
@dataclass
class MockSemanticUnit:
    """Mock semantic unit for testing."""
    name: str
    unit_type: str
    start_line: int
    end_line: int
    content: str = ""
    signature: str = ""
    language: str = "python"
    file_path: str = "test.py"


@pytest.fixture
def extractor():
    """Create docstring extractor instance."""
    return DocstringExtractor()


class TestPythonDocstrings:
    """Test Python docstring extraction."""

    def test_single_line_triple_quote(self, extractor):
        """Test single-line triple-quoted docstring."""
        code = '''
def foo():
    """This is a simple docstring."""
    pass
'''
        docstrings = extractor.extract_from_code(code, "python")

        assert len(docstrings) == 1
        assert docstrings[0].content == "This is a simple docstring."
        assert docstrings[0].style == DocstringStyle.PYTHON

    def test_multiline_triple_quote(self, extractor):
        """Test multi-line triple-quoted docstring."""
        code = '''
def foo():
    """
    This is a multi-line docstring.

    It has multiple paragraphs.
    """
    pass
'''
        docstrings = extractor.extract_from_code(code, "python")

        assert len(docstrings) == 1
        assert "multi-line docstring" in docstrings[0].content
        assert "multiple paragraphs" in docstrings[0].content

    def test_single_quote_docstring(self, extractor):
        """Test single-quote (''') docstring."""
        code = """
def foo():
    '''Single quote docstring.'''
    pass
"""
        docstrings = extractor.extract_from_code(code, "python")

        assert len(docstrings) == 1
        assert docstrings[0].content == "Single quote docstring."

    def test_class_and_method_docstrings(self, extractor):
        """Test extraction from class and methods."""
        code = '''
class MyClass:
    """Class docstring."""

    def method1(self):
        """Method 1 docstring."""
        pass

    def method2(self):
        """Method 2 docstring."""
        pass
'''
        docstrings = extractor.extract_from_code(code, "python")

        assert len(docstrings) == 3
        contents = [d.content for d in docstrings]
        assert "Class docstring." in contents
        assert "Method 1 docstring." in contents
        assert "Method 2 docstring." in contents

    def test_module_docstring(self, extractor):
        """Test module-level docstring."""
        code = '''"""Module-level docstring."""

import os

def foo():
    pass
'''
        docstrings = extractor.extract_from_code(code, "python")

        assert len(docstrings) >= 1
        assert docstrings[0].content == "Module-level docstring."

    def test_empty_docstring_ignored(self, extractor):
        """Test that empty docstrings are ignored."""
        code = '''
def foo():
    """"""
    pass
'''
        docstrings = extractor.extract_from_code(code, "python")

        assert len(docstrings) == 0


class TestJSDocDocstrings:
    """Test JSDoc extraction."""

    def test_basic_jsdoc(self, extractor):
        """Test basic JSDoc comment."""
        code = '''
/**
 * This is a JSDoc comment.
 * @param {string} name - The name parameter
 */
function greet(name) {
    return "Hello " + name;
}
'''
        docstrings = extractor.extract_from_code(code, "javascript")

        assert len(docstrings) == 1
        assert "JSDoc comment" in docstrings[0].content
        assert "@param" in docstrings[0].content
        assert docstrings[0].style == DocstringStyle.JSDOC

    def test_multiline_jsdoc(self, extractor):
        """Test multi-line JSDoc."""
        code = '''
/**
 * Calculate the sum of two numbers.
 *
 * This function takes two numbers and returns their sum.
 *
 * @param {number} a - First number
 * @param {number} b - Second number
 * @returns {number} The sum
 */
function add(a, b) {
    return a + b;
}
'''
        docstrings = extractor.extract_from_code(code, "javascript")

        assert len(docstrings) == 1
        content = docstrings[0].content
        assert "Calculate the sum" in content
        assert "@param" in content
        assert "@returns" in content

    def test_typescript_jsdoc(self, extractor):
        """Test JSDoc extraction from TypeScript."""
        code = '''
/**
 * User interface
 */
interface User {
    name: string;
    email: string;
}

/**
 * Get user by ID
 */
function getUser(id: number): User {
    return { name: "Test", email: "test@example.com" };
}
'''
        docstrings = extractor.extract_from_code(code, "typescript")

        assert len(docstrings) == 2
        contents = [d.content for d in docstrings]
        assert "User interface" in contents
        assert "Get user by ID" in contents


class TestJavadocDocstrings:
    """Test Javadoc extraction."""

    def test_basic_javadoc(self, extractor):
        """Test basic Javadoc comment."""
        code = '''
/**
 * This is a Javadoc comment.
 * @param name The name parameter
 * @return greeting string
 */
public String greet(String name) {
    return "Hello " + name;
}
'''
        docstrings = extractor.extract_from_code(code, "java")

        assert len(docstrings) == 1
        assert "Javadoc comment" in docstrings[0].content
        assert docstrings[0].style == DocstringStyle.JAVADOC

    def test_class_javadoc(self, extractor):
        """Test class-level Javadoc."""
        code = '''
/**
 * Represents a user in the system.
 *
 * @author John Doe
 * @version 1.0
 */
public class User {
    private String name;

    /**
     * Get the user's name.
     * @return the name
     */
    public String getName() {
        return name;
    }
}
'''
        docstrings = extractor.extract_from_code(code, "java")

        assert len(docstrings) == 2
        contents = [d.content for d in docstrings]
        assert any("Represents a user" in c for c in contents)
        assert any("Get the user's name" in c for c in contents)


class TestGoDocDocstrings:
    """Test GoDoc extraction."""

    def test_basic_godoc(self, extractor):
        """Test basic GoDoc comment."""
        code = '''
// Add returns the sum of a and b.
// This is a multi-line comment.
func Add(a, b int) int {
    return a + b
}
'''
        docstrings = extractor.extract_from_code(code, "go")

        assert len(docstrings) == 1
        content = docstrings[0].content
        assert "Add returns the sum" in content
        assert "multi-line comment" in content
        assert docstrings[0].style == DocstringStyle.GODOC

    def test_package_godoc(self, extractor):
        """Test package-level GoDoc."""
        code = '''
// Package utils provides utility functions.
// It includes various helpers for common tasks.
package utils

import "fmt"
'''
        docstrings = extractor.extract_from_code(code, "go")

        assert len(docstrings) >= 1
        assert "Package utils" in docstrings[0].content


class TestRustDocDocstrings:
    """Test RustDoc extraction."""

    def test_triple_slash_rustdoc(self, extractor):
        """Test /// style RustDoc."""
        code = '''
/// Adds two numbers together.
///
/// # Examples
///
/// ```
/// let result = add(2, 3);
/// assert_eq!(result, 5);
/// ```
fn add(a: i32, b: i32) -> i32 {
    a + b
}
'''
        docstrings = extractor.extract_from_code(code, "rust")

        assert len(docstrings) == 1
        content = docstrings[0].content
        assert "Adds two numbers" in content
        assert "Examples" in content
        assert docstrings[0].style == DocstringStyle.RUSTDOC

    def test_inner_rustdoc(self, extractor):
        """Test //! style RustDoc."""
        code = '''
//! This module provides math utilities.
//!
//! It includes basic arithmetic operations.

pub fn multiply(a: i32, b: i32) -> i32 {
    a * b
}
'''
        docstrings = extractor.extract_from_code(code, "rust")

        assert len(docstrings) >= 1
        assert "math utilities" in docstrings[0].content


class TestDocstringLinking:
    """Test linking docstrings to semantic units."""

    def test_link_python_docstring_to_function(self, extractor):
        """Test linking Python docstring to function."""
        code = '''
def foo():
    """Foo function."""
    pass
'''
        units = [
            MockSemanticUnit(
                name="foo",
                unit_type="function",
                start_line=2,
                end_line=4,
            )
        ]

        linked = extractor.extract_and_link(code, "python", units)

        assert len(linked) == 1
        docstring, unit = linked[0]
        assert docstring.content == "Foo function."
        assert unit is not None
        assert unit.name == "foo"
        assert docstring.unit_name == "foo"
        assert docstring.unit_type == "function"

    def test_link_jsdoc_before_function(self, extractor):
        """Test linking JSDoc comment before function."""
        code = '''
/**
 * Bar function description.
 */
function bar() {
    return 42;
}
'''
        # JSDoc is before function (lines 2-4), function starts at line 5
        units = [
            MockSemanticUnit(
                name="bar",
                unit_type="function",
                start_line=5,
                end_line=7,
            )
        ]

        docstrings = extractor.extract_from_code(code, "javascript")
        linked = extractor.link_docstrings_to_units(docstrings, units)

        assert len(linked) == 1
        _, unit = linked[0]
        assert unit is not None
        assert unit.name == "bar"

    def test_unlinked_docstring(self, extractor):
        """Test docstring without matching unit."""
        code = '''
"""Orphan docstring."""

x = 42
'''
        units = []

        linked = extractor.extract_and_link(code, "python", units)

        assert len(linked) == 1
        docstring, unit = linked[0]
        assert docstring.content == "Orphan docstring."
        assert unit is None


class TestMultipleLanguages:
    """Test extraction across multiple languages."""

    def test_stats_tracking(self, extractor):
        """Test statistics tracking across languages."""
        extractor.extract_from_code('"""Test."""', "python")
        extractor.extract_from_code('/** Test */', "javascript")
        extractor.extract_from_code('// Test', "go")

        stats = extractor.get_stats()

        assert stats["docstrings_extracted"] >= 3
        assert "python" in stats["languages_processed"]
        assert "javascript" in stats["languages_processed"]
        assert "go" in stats["languages_processed"]

    def test_unsupported_language(self, extractor):
        """Test handling of unsupported language."""
        docstrings = extractor.extract_from_code("code", "unknown_lang")

        assert len(docstrings) == 0


class TestUtilityFunctions:
    """Test utility functions."""

    def test_format_docstring_for_search(self):
        """Test docstring formatting for search."""
        docstring = Docstring(
            content="This is a docstring.",
            style=DocstringStyle.PYTHON,
            start_line=1,
            end_line=1,
        )

        formatted = format_docstring_for_search(docstring, "my_function")

        assert "Documentation for my_function:" in formatted
        assert "This is a docstring." in formatted

    def test_extract_summary_short(self):
        """Test summary extraction from short docstring."""
        content = "This is a short docstring."
        summary = extract_summary(content)

        assert summary == "This is a short docstring."

    def test_extract_summary_long(self):
        """Test summary extraction from long docstring."""
        content = """
        This is the first sentence. This is the second sentence.

        This is a second paragraph with more details.
        """
        summary = extract_summary(content, max_length=50)

        assert "This is the first sentence" in summary
        assert len(summary) <= 53  # 50 + "..."

    def test_extract_summary_multi_paragraph(self):
        """Test summary from multi-paragraph docstring."""
        content = """
        First paragraph is here.

        Second paragraph should not be included.
        """
        summary = extract_summary(content)

        assert "First paragraph" in summary
        assert "Second paragraph" not in summary


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_source_code(self, extractor):
        """Test extraction from empty source."""
        docstrings = extractor.extract_from_code("", "python")

        assert len(docstrings) == 0

    def test_code_without_docstrings(self, extractor):
        """Test code with no docstrings."""
        code = '''
def foo():
    x = 42
    return x
'''
        docstrings = extractor.extract_from_code(code, "python")

        assert len(docstrings) == 0

    def test_nested_quotes_in_docstring(self, extractor):
        """Test docstring containing quotes."""
        code = '''
def foo():
    """This has a "quoted" word."""
    pass
'''
        docstrings = extractor.extract_from_code(code, "python")

        assert len(docstrings) == 1
        assert '"quoted"' in docstrings[0].content

    def test_line_numbers_accuracy(self, extractor):
        """Test that line numbers are accurate."""
        code = '''
# Line 1
# Line 2
def foo():
    """Docstring on line 5."""
    pass
'''
        docstrings = extractor.extract_from_code(code, "python")

        assert len(docstrings) == 1
        # Docstring starts on line 5 (1-indexed)
        assert docstrings[0].start_line == 5

    def test_clean_content_method(self):
        """Test Docstring.clean_content() method."""
        docstring = Docstring(
            content="  Content with spaces  ",
            style=DocstringStyle.PYTHON,
            start_line=1,
            end_line=1,
        )

        cleaned = docstring.clean_content()

        assert cleaned == "Content with spaces"
        assert not cleaned.startswith(" ")
        assert not cleaned.endswith(" ")
