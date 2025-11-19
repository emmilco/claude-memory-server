"""Tests for Swift language parsing support (FEAT-009)."""

import pytest
from pathlib import Path
from mcp_performance_core import parse_source_file


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

    def test_swift_extension_recognized(self, tmp_path):
        """Test that .swift extension is recognized as Swift."""
        test_file = tmp_path / "test.swift"
        test_file.write_text("func test() {}")
        units = parse_source_file(str(test_file), "swift")
        assert units is not None


class TestSwiftFunctionExtraction:
    """Test extraction of Swift functions."""

    def test_function_extraction(self, sample_swift_file):
        """Test extraction of functions."""
        units = parse_source_file(str(sample_swift_file), "swift")

        # Find functions
        functions = [u for u in units if u["unit_type"] == "function" and "calculate" in u["name"].lower()]
        assert len(functions) > 0, "Should extract calculateArea function"

    def test_method_extraction(self, sample_swift_file):
        """Test extraction of methods from classes and structs."""
        units = parse_source_file(str(sample_swift_file), "swift")

        # Find methods
        draw_methods = [u for u in units if u["unit_type"] in ["function", "method"] and "draw" in u["name"].lower()]
        assert len(draw_methods) > 0, "Should extract draw method"

    def test_class_method_extraction(self, sample_swift_file):
        """Test extraction of class methods."""
        units = parse_source_file(str(sample_swift_file), "swift")

        # Find class methods
        class_methods = [u for u in units if u["unit_type"] in ["function", "method"] and "createDefault" in u["name"]]
        assert len(class_methods) > 0, "Should extract class method"


class TestSwiftStructExtraction:
    """Test extraction of Swift structs."""

    def test_struct_extraction(self, sample_swift_file):
        """Test extraction of Swift structs."""
        units = parse_source_file(str(sample_swift_file), "swift")

        # Find structs
        structs = [u for u in units if u["unit_type"] == "class" and "Point" in u["name"]]
        assert len(structs) > 0, "Should extract Point struct"


class TestSwiftClassExtraction:
    """Test extraction of Swift classes."""

    def test_class_extraction(self, sample_swift_file):
        """Test extraction of Swift classes."""
        units = parse_source_file(str(sample_swift_file), "swift")

        # Find classes
        classes = [u for u in units if u["unit_type"] == "class" and "Shape" in u["name"]]
        assert len(classes) > 0, "Should extract Shape class"


class TestSwiftProtocolExtraction:
    """Test extraction of Swift protocols."""

    def test_protocol_extraction(self, sample_swift_file):
        """Test extraction of Swift protocols."""
        units = parse_source_file(str(sample_swift_file), "swift")

        # Find protocols
        protocols = [u for u in units if u["unit_type"] == "class" and "Drawable" in u["name"]]
        assert len(protocols) > 0, "Should extract Drawable protocol"


class TestSwiftComplexScenarios:
    """Test complex Swift parsing scenarios."""

    def test_multiple_semantic_units(self, sample_swift_file):
        """Test that multiple semantic units are extracted."""
        units = parse_source_file(str(sample_swift_file), "swift")

        # Should extract protocols, structs, classes, and functions
        assert len(units) > 3, "Should extract multiple semantic units"

    def test_unit_metadata(self, sample_swift_file):
        """Test that unit metadata is correctly populated."""
        units = parse_source_file(str(sample_swift_file), "swift")

        # Check that units have required metadata
        for unit in units:
            assert unit["file_path"] == str(sample_swift_file)
            assert unit["language"] == "swift"
            assert unit["start_line"] > 0
            assert unit["end_line"] >= unit["start_line"]
            assert len(unit["content"]) > 0


class TestSwiftEdgeCases:
    """Test edge cases in Swift parsing."""

    def test_empty_swift_file(self, tmp_path):
        """Test parsing of an empty Swift file."""
        empty_file = tmp_path / "empty.swift"
        empty_file.write_text("")

        units = parse_source_file(str(empty_file), "swift")
        assert units == [] or len(units) == 0, "Empty file should produce no units"

    def test_swift_file_with_only_comments(self, tmp_path):
        """Test parsing of a Swift file with only comments."""
        comment_file = tmp_path / "comments.swift"
        comment_file.write_text("""
// This is a comment
// Another comment
/* Multi-line
   comment */
""")

        units = parse_source_file(str(comment_file), "swift")
        assert len(units) == 0, "File with only comments should produce no units"
