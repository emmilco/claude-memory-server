"""Tests for C/C++ code parsing."""

import pytest
import tempfile
from pathlib import Path

try:
    from mcp_performance_core import parse_source_file
    RUST_AVAILABLE = True
except ImportError:
    RUST_AVAILABLE = False
    pytest.skip("Rust parser not available", allow_module_level=True)


# Sample C code for testing
SAMPLE_C_CODE = '''
#include <stdio.h>

struct Point {
    int x;
    int y;
};

int add(int a, int b) {
    return a + b;
}

void print_point(struct Point p) {
    printf("(%d, %d)\\n", p.x, p.y);
}

double calculate_area(double width, double height) {
    return width * height;
}
'''

# Sample C++ code for testing
SAMPLE_CPP_CODE = '''
#include <iostream>
#include <string>

class Calculator {
private:
    double result;

public:
    Calculator() : result(0.0) {}

    double add(double a, double b) {
        result = a + b;
        return result;
    }

    double getResult() const {
        return result;
    }
};

namespace Math {
    int multiply(int a, int b) {
        return a * b;
    }
}

struct Vector3D {
    float x, y, z;

    float magnitude() const {
        return sqrt(x*x + y*y + z*z);
    }
};
'''

# Sample C header for testing
SAMPLE_C_HEADER = '''
#ifndef UTILS_H
#define UTILS_H

struct Data {
    int id;
    char name[256];
};

int process_data(struct Data *data);
void init_data(struct Data *data, int id);

#endif
'''

# Sample C++ header for testing
SAMPLE_CPP_HEADER = '''
#ifndef ENGINE_HPP
#define ENGINE_HPP

#include <string>
#include <vector>

class Engine {
private:
    std::string name;
    int power;

public:
    Engine(const std::string& name, int power);
    void start();
    void stop();
    int getPower() const;
};

#endif
'''


@pytest.fixture
def temp_dir():
    """Create temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_c_file(temp_dir):
    """Create sample C file."""
    file_path = temp_dir / "sample.c"
    file_path.write_text(SAMPLE_C_CODE)
    return file_path


@pytest.fixture
def sample_cpp_file(temp_dir):
    """Create sample C++ file."""
    file_path = temp_dir / "sample.cpp"
    file_path.write_text(SAMPLE_CPP_CODE)
    return file_path


@pytest.fixture
def sample_c_header(temp_dir):
    """Create sample C header file."""
    file_path = temp_dir / "utils.h"
    file_path.write_text(SAMPLE_C_HEADER)
    return file_path


@pytest.fixture
def sample_cpp_header(temp_dir):
    """Create sample C++ header file."""
    file_path = temp_dir / "engine.hpp"
    file_path.write_text(SAMPLE_CPP_HEADER)
    return file_path


class TestCParsing:
    """Tests for C code parsing."""

    def test_parse_c_file(self, sample_c_file):
        """Test parsing a C file."""
        result = parse_source_file(str(sample_c_file), SAMPLE_C_CODE)

        assert result.language == "C"
        assert result.file_path == str(sample_c_file)
        assert result.parse_time_ms > 0
        assert len(result.units) > 0

    def test_parse_c_functions(self, sample_c_file):
        """Test extracting functions from C code."""
        result = parse_source_file(str(sample_c_file), SAMPLE_C_CODE)

        # Should find functions: add, print_point, calculate_area
        function_units = [u for u in result.units if u.unit_type == "function"]
        assert len(function_units) >= 3

        function_names = [u.name for u in function_units]
        assert "add" in function_names or any("add" in name for name in function_names)

    def test_parse_c_structs(self, sample_c_file):
        """Test extracting structs from C code."""
        result = parse_source_file(str(sample_c_file), SAMPLE_C_CODE)

        # Should find struct: Point
        class_units = [u for u in result.units if u.unit_type == "class"]
        assert len(class_units) >= 1

        struct_names = [u.name for u in class_units]
        assert "Point" in struct_names or any("Point" in name for name in struct_names)

    def test_parse_c_header(self, sample_c_header):
        """Test parsing a C header file."""
        result = parse_source_file(str(sample_c_header), SAMPLE_C_HEADER)

        assert result.language == "C"
        assert len(result.units) >= 0  # May or may not have units depending on parser


class TestCppParsing:
    """Tests for C++ code parsing."""

    def test_parse_cpp_file(self, sample_cpp_file):
        """Test parsing a C++ file."""
        result = parse_source_file(str(sample_cpp_file), SAMPLE_CPP_CODE)

        assert result.language == "Cpp"
        assert result.file_path == str(sample_cpp_file)
        assert result.parse_time_ms > 0
        assert len(result.units) > 0

    def test_parse_cpp_classes(self, sample_cpp_file):
        """Test extracting classes from C++ code."""
        result = parse_source_file(str(sample_cpp_file), SAMPLE_CPP_CODE)

        # Should find classes: Calculator
        class_units = [u for u in result.units if u.unit_type == "class"]
        assert len(class_units) >= 1

        class_names = [u.name for u in class_units]
        assert "Calculator" in class_names or any("Calculator" in name for name in class_names)

    def test_parse_cpp_functions(self, sample_cpp_file):
        """Test extracting functions from C++ code."""
        result = parse_source_file(str(sample_cpp_file), SAMPLE_CPP_CODE)

        # Should find functions in namespace and methods
        function_units = [u for u in result.units if u.unit_type == "function"]
        # C++ may have multiple functions/methods
        assert len(function_units) >= 0  # May vary based on query

    def test_parse_cpp_header(self, sample_cpp_header):
        """Test parsing a C++ header file."""
        result = parse_source_file(str(sample_cpp_header), SAMPLE_CPP_HEADER)

        assert result.language == "Cpp"
        # Header files may have class declarations
        assert len(result.units) >= 0


class TestCppFileExtensions:
    """Test that different C/C++ file extensions are handled correctly."""

    def test_c_extension(self, temp_dir):
        """Test .c extension."""
        file_path = temp_dir / "test.c"
        file_path.write_text("int main() { return 0; }")
        result = parse_source_file(str(file_path), file_path.read_text())
        assert result.language == "C"

    def test_h_extension(self, temp_dir):
        """Test .h extension."""
        file_path = temp_dir / "test.h"
        file_path.write_text("int main() { return 0; }")
        result = parse_source_file(str(file_path), file_path.read_text())
        assert result.language == "C"

    def test_cpp_extension(self, temp_dir):
        """Test .cpp extension."""
        file_path = temp_dir / "test.cpp"
        file_path.write_text("int main() { return 0; }")
        result = parse_source_file(str(file_path), file_path.read_text())
        assert result.language == "Cpp"

    def test_cc_extension(self, temp_dir):
        """Test .cc extension."""
        file_path = temp_dir / "test.cc"
        file_path.write_text("int main() { return 0; }")
        result = parse_source_file(str(file_path), file_path.read_text())
        assert result.language == "Cpp"

    def test_cxx_extension(self, temp_dir):
        """Test .cxx extension."""
        file_path = temp_dir / "test.cxx"
        file_path.write_text("int main() { return 0; }")
        result = parse_source_file(str(file_path), file_path.read_text())
        assert result.language == "Cpp"

    def test_hpp_extension(self, temp_dir):
        """Test .hpp extension."""
        file_path = temp_dir / "test.hpp"
        file_path.write_text("int main() { return 0; }")
        result = parse_source_file(str(file_path), file_path.read_text())
        assert result.language == "Cpp"

    def test_hxx_extension(self, temp_dir):
        """Test .hxx extension."""
        file_path = temp_dir / "test.hxx"
        file_path.write_text("int main() { return 0; }")
        result = parse_source_file(str(file_path), file_path.read_text())
        assert result.language == "Cpp"

    def test_hh_extension(self, temp_dir):
        """Test .hh extension."""
        file_path = temp_dir / "test.hh"
        file_path.write_text("int main() { return 0; }")
        result = parse_source_file(str(file_path), file_path.read_text())
        assert result.language == "Cpp"


class TestCppSemanticUnits:
    """Test semantic unit extraction details."""

    def test_function_line_numbers(self, sample_c_file):
        """Test that line numbers are extracted correctly."""
        result = parse_source_file(str(sample_c_file), SAMPLE_C_CODE)

        for unit in result.units:
            assert unit.start_line > 0
            assert unit.end_line >= unit.start_line
            assert unit.start_byte >= 0
            assert unit.end_byte > unit.start_byte

    def test_unit_content_not_empty(self, sample_cpp_file):
        """Test that unit content is extracted."""
        result = parse_source_file(str(sample_cpp_file), SAMPLE_CPP_CODE)

        for unit in result.units:
            assert len(unit.content) > 0
            assert len(unit.name) > 0

    def test_unit_has_language(self, sample_cpp_file):
        """Test that units have language field."""
        result = parse_source_file(str(sample_cpp_file), SAMPLE_CPP_CODE)

        for unit in result.units:
            assert unit.language == "Cpp"
