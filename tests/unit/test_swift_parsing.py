"""Tests for Swift language parsing support (FEAT-009)."""

import pytest
from pathlib import Path
from src.memory.code_parser import CodeParser


@pytest.fixture
def code_parser():
    """Create a CodeParser instance for testing."""
    return CodeParser()


@pytest.fixture
def sample_swift_file(tmp_path):
    """Create a sample Swift file for testing."""
    swift_file = tmp_path / "test.swift"
    swift_content = """
import Foundation

protocol Drawable {
    func draw()
}

struct Point {
    var x: Double
    var y: Double

    func distance(to other: Point) -> Double {
        return sqrt((x - other.x) * (x - other.x))
    }
}

class Shape {
    var color: String

    init(color: String) {
        self.color = color
    }

    func draw() {
        print("Drawing in \\(color)")
    }

    class func createDefault() -> Shape {
        return Shape(color: "black")
    }
}

func calculateArea(width: Double, height: Double) -> Double {
    return width * height
}

func greet(_ person: String) {
    print("Hello, \\(person)!")
}
"""
    swift_file.write_text(swift_content)
    return swift_file


class TestSwiftFileRecognition:
    """Test Swift file extension recognition."""

    def test_swift_extension_recognized(self, code_parser):
        """Test that .swift extension is recognized as Swift."""
        assert code_parser.can_parse("test.swift")
        assert code_parser.can_parse("lib/MyClass.swift")
        assert code_parser.can_parse("/path/to/file.swift")


class TestSwiftFunctionExtraction:
    """Test extraction of Swift functions."""

    def test_function_extraction(self, code_parser, sample_swift_file):
        """Test extraction of functions."""
        units = code_parser.parse_file(sample_swift_file)

        # Find functions
        functions = [u for u in units if u.unit_type == "function" and "calculate" in u.unit_name.lower()]
        assert len(functions) > 0, "Should extract calculateArea function"

    def test_method_extraction(self, code_parser, sample_swift_file):
        """Test extraction of methods from classes and structs."""
        units = code_parser.parse_file(sample_swift_file)

        # Find methods
        draw_methods = [u for u in units if u.unit_type == "function" and "draw" in u.unit_name.lower()]
        assert len(draw_methods) > 0, "Should extract draw method"

    def test_class_method_extraction(self, code_parser, sample_swift_file):
        """Test extraction of class methods."""
        units = code_parser.parse_file(sample_swift_file)

        # Find class methods
        class_methods = [u for u in units if u.unit_type == "function" and "createDefault" in u.unit_name]
        assert len(class_methods) > 0, "Should extract class method"


class TestSwiftStructExtraction:
    """Test extraction of Swift structs."""

    def test_struct_extraction(self, code_parser, sample_swift_file):
        """Test extraction of Swift structs."""
        units = code_parser.parse_file(sample_swift_file)

        # Find structs
        structs = [u for u in units if u.unit_type == "class" and "Point" in u.unit_name]
        assert len(structs) > 0, "Should extract Point struct"


class TestSwiftClassExtraction:
    """Test extraction of Swift classes."""

    def test_class_extraction(self, code_parser, sample_swift_file):
        """Test extraction of Swift classes."""
        units = code_parser.parse_file(sample_swift_file)

        # Find classes
        classes = [u for u in units if u.unit_type == "class" and "Shape" in u.unit_name]
        assert len(classes) > 0, "Should extract Shape class"


class TestSwiftProtocolExtraction:
    """Test extraction of Swift protocols."""

    def test_protocol_extraction(self, code_parser, sample_swift_file):
        """Test extraction of Swift protocols."""
        units = code_parser.parse_file(sample_swift_file)

        # Find protocols
        protocols = [u for u in units if u.unit_type == "class" and "Drawable" in u.unit_name]
        assert len(protocols) > 0, "Should extract Drawable protocol"


class TestSwiftComplexScenarios:
    """Test complex Swift parsing scenarios."""

    def test_multiple_semantic_units(self, code_parser, sample_swift_file):
        """Test that multiple semantic units are extracted."""
        units = code_parser.parse_file(sample_swift_file)

        # Should extract protocols, structs, classes, and functions
        assert len(units) > 3, "Should extract multiple semantic units"

    def test_unit_metadata(self, code_parser, sample_swift_file):
        """Test that unit metadata is correctly populated."""
        units = code_parser.parse_file(sample_swift_file)

        # Check that units have required metadata
        for unit in units:
            assert unit.file_path == str(sample_swift_file)
            assert unit.language == "swift"
            assert unit.start_line > 0
            assert unit.end_line >= unit.start_line
            assert len(unit.content) > 0


class TestSwiftEdgeCases:
    """Test edge cases in Swift parsing."""

    def test_empty_swift_file(self, code_parser, tmp_path):
        """Test parsing of an empty Swift file."""
        empty_file = tmp_path / "empty.swift"
        empty_file.write_text("")

        units = code_parser.parse_file(empty_file)
        assert units == [] or len(units) == 0, "Empty file should produce no units"

    def test_swift_file_with_only_comments(self, code_parser, tmp_path):
        """Test parsing of a Swift file with only comments."""
        comment_file = tmp_path / "comments.swift"
        comment_file.write_text("""
// This is a comment
// Another comment
/* Multi-line
   comment */
""")

        units = code_parser.parse_file(comment_file)
        assert len(units) == 0, "File with only comments should produce no units"
