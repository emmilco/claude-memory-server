"""
Tests for C++ code parsing.

This test suite verifies comprehensive C++ support including:
- Basic classes and functions
- Template classes and functions
- Structs
- Namespaces
- Operator overloads
- Performance requirements
"""

import pytest
from mcp_performance_core import parse_source_file


# Sample C++ code with various constructs
SAMPLE_CPP = '''
#include <iostream>
#include <string>

// Basic class
class Calculator {
private:
    int value;
public:
    Calculator() : value(0) {}
    int add(int a, int b) { return a + b; }
    int subtract(int a, int b) { return a - b; }
};

// Struct
struct Point {
    int x, y;
    double distance() const {
        return sqrt(x*x + y*y);
    }
};

// Template class
template<typename T>
class Container {
    T data;
public:
    void set(T value) { data = value; }
    T get() const { return data; }
};

// Template function
template<typename T>
T max(T a, T b) {
    return (a > b) ? a : b;
}

// Namespace
namespace Math {
    class Vector {
    public:
        double x, y;
        Vector operator+(const Vector& other) {
            return {x + other.x, y + other.y};
        }
    };
}

// Free function
void printHello() {
    std::cout << "Hello" << std::endl;
}
'''


TEMPLATE_CLASS_CPP = '''
template<typename T, typename U>
class Pair {
    T first;
    U second;
public:
    Pair(T a, U b) : first(a), second(b) {}
    T getFirst() const { return first; }
    U getSecond() const { return second; }
};
'''


TEMPLATE_FUNCTION_CPP = '''
template<typename T>
T clamp(T value, T min, T max) {
    if (value < min) return min;
    if (value > max) return max;
    return value;
}
'''


NAMESPACE_CPP = '''
namespace Math {
    namespace Geometry {
        class Circle {
            double radius;
        public:
            double area() const {
                return 3.14159 * radius * radius;
            }
        };
    }
}
'''


OPERATOR_OVERLOAD_CPP = '''
class Complex {
    double real, imag;
public:
    Complex operator+(const Complex& other) {
        return {real + other.real, imag + other.imag};
    }
    Complex operator*(const Complex& other) {
        return {
            real * other.real - imag * other.imag,
            real * other.imag + imag * other.real
        };
    }
    bool operator==(const Complex& other) {
        return real == other.real && imag == other.imag;
    }
};
'''


class TestCppFileParsing:
    """Test basic C++ file parsing."""

    def test_cpp_file_parsing(self):
        """Test that C++ files are parsed successfully."""
        result = parse_source_file("test.cpp", SAMPLE_CPP)
        assert result.language == "Cpp"
        assert result.file_path == "test.cpp"
        assert result.parse_time_ms > 0

    def test_cc_extension(self):
        """Test .cc file extension."""
        result = parse_source_file("test.cc", SAMPLE_CPP)
        assert result.language == "Cpp"

    def test_cxx_extension(self):
        """Test .cxx file extension."""
        result = parse_source_file("test.cxx", SAMPLE_CPP)
        assert result.language == "Cpp"

    def test_hpp_extension(self):
        """Test .hpp header extension."""
        result = parse_source_file("test.hpp", SAMPLE_CPP)
        assert result.language == "Cpp"

    def test_h_extension(self):
        """Test .h header extension."""
        result = parse_source_file("test.h", SAMPLE_CPP)
        assert result.language == "Cpp"


class TestCppUnitExtraction:
    """Test extraction of semantic units from C++ code."""

    def test_extracts_semantic_units(self):
        """Test that semantic units are extracted from C++ code."""
        result = parse_source_file("test.cpp", SAMPLE_CPP)
        assert len(result.units) > 0

    def test_unit_has_required_fields(self):
        """Test that extracted units have all required fields."""
        result = parse_source_file("test.cpp", SAMPLE_CPP)
        if len(result.units) > 0:
            unit = result.units[0]
            assert hasattr(unit, 'unit_type')
            assert hasattr(unit, 'name')
            assert hasattr(unit, 'start_line')
            assert hasattr(unit, 'end_line')
            assert hasattr(unit, 'content')
            assert hasattr(unit, 'language')
            assert unit.language == "Cpp"


class TestCppClassExtraction:
    """Test C++ class extraction."""

    def test_extracts_classes(self):
        """Test that classes are extracted."""
        result = parse_source_file("test.cpp", SAMPLE_CPP)
        class_units = [u for u in result.units if u.unit_type == "class"]
        assert len(class_units) > 0

    def test_class_has_name(self):
        """Test that extracted classes have names."""
        result = parse_source_file("test.cpp", SAMPLE_CPP)
        class_units = [u for u in result.units if u.unit_type == "class"]
        if len(class_units) > 0:
            assert len(class_units[0].name) > 0

    def test_class_has_content(self):
        """Test that extracted classes have content."""
        result = parse_source_file("test.cpp", SAMPLE_CPP)
        class_units = [u for u in result.units if u.unit_type == "class"]
        if len(class_units) > 0:
            assert len(class_units[0].content) > 0

    def test_class_line_numbers(self):
        """Test that classes have valid line numbers."""
        result = parse_source_file("test.cpp", SAMPLE_CPP)
        class_units = [u for u in result.units if u.unit_type == "class"]
        if len(class_units) > 0:
            unit = class_units[0]
            assert unit.start_line > 0
            assert unit.end_line >= unit.start_line


class TestCppFunctionExtraction:
    """Test C++ function extraction."""

    def test_extracts_functions(self):
        """Test that functions are extracted."""
        result = parse_source_file("test.cpp", SAMPLE_CPP)
        func_units = [u for u in result.units if u.unit_type == "function"]
        assert len(func_units) > 0

    def test_function_has_name(self):
        """Test that extracted functions have names."""
        result = parse_source_file("test.cpp", SAMPLE_CPP)
        func_units = [u for u in result.units if u.unit_type == "function"]
        if len(func_units) > 0:
            assert len(func_units[0].name) > 0

    def test_function_has_content(self):
        """Test that extracted functions have content."""
        result = parse_source_file("test.cpp", SAMPLE_CPP)
        func_units = [u for u in result.units if u.unit_type == "function"]
        if len(func_units) > 0:
            assert len(func_units[0].content) > 0


class TestCppStructs:
    """Test C++ struct extraction."""

    def test_extracts_structs(self):
        """Test that structs are extracted as classes."""
        result = parse_source_file("test.cpp", SAMPLE_CPP)
        # Structs should be extracted as "class" type (semantically similar in C++)
        class_units = [u for u in result.units if u.unit_type == "class"]
        # Check if we can find "Point" which is defined as a struct
        struct_names = [u.name for u in class_units]
        # Note: The name might include more than just "Point" depending on tree-sitter capture
        assert any("Point" in name for name in struct_names)


class TestCppTemplates:
    """Test C++ template support."""

    def test_template_class_extraction(self):
        """Test that template classes are extracted."""
        result = parse_source_file("template.cpp", TEMPLATE_CLASS_CPP)
        assert len(result.units) > 0
        # Template classes should be extracted (may include template parameters in capture)

    def test_template_function_extraction(self):
        """Test that template functions are extracted."""
        result = parse_source_file("template_func.cpp", TEMPLATE_FUNCTION_CPP)
        assert len(result.units) > 0


class TestCppNamespaces:
    """Test C++ namespace handling."""

    def test_parses_code_with_namespaces(self):
        """Test that code with namespaces parses successfully."""
        result = parse_source_file("namespace.cpp", NAMESPACE_CPP)
        assert result.language == "Cpp"
        assert len(result.units) > 0

    def test_nested_namespaces(self):
        """Test that nested namespaces don't prevent parsing."""
        result = parse_source_file("namespace.cpp", NAMESPACE_CPP)
        # Should extract Circle class inside nested namespace
        class_units = [u for u in result.units if u.unit_type == "class"]
        assert len(class_units) > 0


class TestCppOperatorOverloads:
    """Test C++ operator overload extraction."""

    def test_parses_operator_overloads(self):
        """Test that operator overloads are parsed."""
        result = parse_source_file("operators.cpp", OPERATOR_OVERLOAD_CPP)
        assert result.language == "Cpp"
        assert len(result.units) > 0


class TestCppPerformance:
    """Test C++ parsing performance."""

    def test_parse_time_under_100ms(self):
        """Test that parsing completes in under 100ms."""
        result = parse_source_file("test.cpp", SAMPLE_CPP)
        assert result.parse_time_ms < 100

    def test_large_file_performance(self):
        """Test performance with larger C++ file."""
        # Create a larger file by repeating classes
        large_cpp = SAMPLE_CPP * 10
        result = parse_source_file("large.cpp", large_cpp)
        assert result.parse_time_ms < 500  # Allow more time for larger file


class TestCppEdgeCases:
    """Test edge cases in C++ parsing."""

    def test_empty_file(self):
        """Test parsing empty C++ file."""
        result = parse_source_file("empty.cpp", "")
        assert result.language == "Cpp"
        assert len(result.units) == 0

    def test_comments_only(self):
        """Test parsing file with only comments."""
        cpp_code = "// This is a comment\n/* Block comment */"
        result = parse_source_file("comments.cpp", cpp_code)
        assert result.language == "Cpp"

    def test_preprocessor_directives(self):
        """Test that preprocessor directives don't break parsing."""
        cpp_code = '''
#include <iostream>
#define MAX 100
#ifdef DEBUG
#endif

class Test {
public:
    void method() {}
};
'''
        result = parse_source_file("preprocessor.cpp", cpp_code)
        assert result.language == "Cpp"
        assert len(result.units) > 0
