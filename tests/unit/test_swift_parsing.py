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
        content = test_file.read_text()
        result = parse_source_file(str(test_file), content)
        units = result.units if hasattr(result, 'units') else result
        assert units is not None


# NOTE: Function/method extraction is not currently supported for Swift
# The Swift parser only extracts class/struct/protocol declarations, not standalone functions or methods
# This would require implementing Swift-specific function query patterns in the parser


class TestSwiftStructExtraction:
    """Test extraction of Swift structs."""

    def test_struct_extraction(self, sample_swift_file):
        """Test extraction of Swift structs."""
        content = sample_swift_file.read_text()
        result = parse_source_file(str(sample_swift_file), content)
        units = result.units if hasattr(result, 'units') else result

        # Find structs
        structs = [u for u in units if u.unit_type == "class" and "Point" in u.name]
        assert len(structs) > 0, "Should extract Point struct"


class TestSwiftClassExtraction:
    """Test extraction of Swift classes."""

    def test_class_extraction(self, sample_swift_file):
        """Test extraction of Swift classes."""
        content = sample_swift_file.read_text()
        result = parse_source_file(str(sample_swift_file), content)
        units = result.units if hasattr(result, 'units') else result

        # Find classes
        classes = [u for u in units if u.unit_type == "class" and "Shape" in u.name]
        assert len(classes) > 0, "Should extract Shape class"


class TestSwiftProtocolExtraction:
    """Test extraction of Swift protocols."""

    def test_protocol_extraction(self, sample_swift_file):
        """Test extraction of Swift protocols."""
        content = sample_swift_file.read_text()
        result = parse_source_file(str(sample_swift_file), content)
        units = result.units if hasattr(result, 'units') else result

        # Find protocols
        protocols = [u for u in units if u.unit_type == "class" and "Drawable" in u.name]
        assert len(protocols) > 0, "Should extract Drawable protocol"


class TestSwiftComplexScenarios:
    """Test complex Swift parsing scenarios."""

    def test_multiple_semantic_units(self, sample_swift_file):
        """Test that multiple semantic units are extracted."""
        content = sample_swift_file.read_text()
        result = parse_source_file(str(sample_swift_file), content)
        units = result.units if hasattr(result, 'units') else result

        # Should extract protocols, structs, classes, and functions
        assert len(units) >= 3, "Should extract multiple semantic units (classes/structs/protocols)"

    def test_unit_metadata(self, sample_swift_file):
        """Test that unit metadata is correctly populated."""
        content = sample_swift_file.read_text()
        result = parse_source_file(str(sample_swift_file), content)
        units = result.units if hasattr(result, 'units') else result

        # Check that units have required metadata
        for unit in units:
            assert unit["file_path"] == str(sample_swift_file)
            assert unit.language == "Swift"
            assert unit["start_line"] > 0
            assert unit["end_line"] >= unit["start_line"]
            assert len(unit["content"]) > 0


class TestSwiftEdgeCases:
    """Test edge cases in Swift parsing."""

    def test_empty_swift_file(self, tmp_path):
        """Test parsing of an empty Swift file."""
        empty_file = tmp_path / "empty.swift"
        content = ""
        empty_file.write_text(content)
        result = parse_source_file(str(empty_file), content)
        units = result.units if hasattr(result, 'units') else result
        assert units == [] or len(units) == 0, "Empty file should produce no units"

    def test_swift_file_with_only_comments(self, tmp_path):
        """Test parsing of a Swift file with only comments."""
        comment_file = tmp_path / "comments.swift"
        content = """
// This is a comment
// Another comment
/* Multi-line
   comment */
"""
        comment_file.write_text(content)
        result = parse_source_file(str(comment_file), content)
        units = result.units if hasattr(result, 'units') else result
        assert len(units) == 0, "File with only comments should produce no units"
