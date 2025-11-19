"""Tests for Kotlin language parsing support (FEAT-010)."""

import pytest
from pathlib import Path
from mcp_performance_core import parse_source_file


@pytest.fixture
def sample_kotlin_file(tmp_path):
    """Create a sample Kotlin file for testing."""
    kotlin_file = tmp_path / "test.kt"
    kotlin_content = """
package com.example.test

import kotlin.math.sqrt

interface Drawable {
    fun draw()
    var color: String
}

data class Point(var x: Double, var y: Double) {
    fun distance(to: Point): Double {
        val dx = x - to.x
        val dy = y - to.y
        return sqrt(dx * dx + dy * dy)
    }
}

class Shape(var color: String, var name: String) : Drawable {
    override fun draw() {
        println("Drawing $name in $color")
    }

    companion object {
        fun createDefault(): Shape {
            return Shape("black", "default")
        }
    }
}

object MathUtils {
    fun calculateArea(width: Double, height: Double): Double {
        return width * height
    }
}

fun greet(person: String) {
    println("Hello, $person!")
}

fun processNumbers(numbers: List<Int>, operation: (Int) -> Int): List<Int> {
    return numbers.map(operation)
}
"""
    kotlin_file.write_text(kotlin_content)
    return kotlin_file


class TestKotlinFileRecognition:
    """Test Kotlin file extension recognition."""

    def test_kotlin_extension_recognized(self, sample_kotlin_file):
        """Test that .kt extension is recognized as Kotlin."""
        # Test parsing works for .kt files
        content = sample_kotlin_file.read_text()

        result = parse_source_file(str(sample_kotlin_file), content)
        units = result.units if hasattr(result, 'units') else result
        assert units is not None, "Should parse .kt files"

    def test_kotlin_script_extension_recognized(self, tmp_path):
        """Test that .kts extension is recognized as Kotlin."""
        # Create a .kts file
        kts_file = tmp_path / "script.kts"
        kts_file.write_text("fun main() { println(\"Hello\") }")
        content = kts_file.read_text()

        result = parse_source_file(str(kts_file), content)
        units = result.units if hasattr(result, 'units') else result
        assert units is not None, "Should parse .kts files"


class TestKotlinFunctionExtraction:
    """Test extraction of Kotlin functions."""

    def test_function_extraction(self, sample_kotlin_file):
        """Test extraction of top-level functions."""
        content = sample_kotlin_file.read_text()

        result = parse_source_file(str(sample_kotlin_file), content)
        units = result.units if hasattr(result, 'units') else result

        # Find functions
        functions = [u for u in units if u["type"] == "function" and "greet" in u["name"].lower()]
        assert len(functions) > 0, "Should extract greet function"

    def test_method_extraction(self, sample_kotlin_file):
        """Test extraction of methods from classes."""
        content = sample_kotlin_file.read_text()

        result = parse_source_file(str(sample_kotlin_file), content)
        units = result.units if hasattr(result, 'units') else result

        # Find methods
        draw_methods = [u for u in units if u["type"] == "function" and "draw" in u["name"].lower()]
        assert len(draw_methods) > 0, "Should extract draw method"

    def test_companion_object_method_extraction(self, sample_kotlin_file):
        """Test extraction of companion object methods."""
        content = sample_kotlin_file.read_text()

        result = parse_source_file(str(sample_kotlin_file), content)
        units = result.units if hasattr(result, 'units') else result

        # Find companion object methods
        create_methods = [u for u in units if u["type"] == "function" and "createDefault" in u["name"]]
        assert len(create_methods) > 0, "Should extract companion object method"


class TestKotlinDataClassExtraction:
    """Test extraction of Kotlin data classes."""

    def test_data_class_extraction(self, sample_kotlin_file):
        """Test extraction of Kotlin data classes."""
        content = sample_kotlin_file.read_text()

        result = parse_source_file(str(sample_kotlin_file), content)
        units = result.units if hasattr(result, 'units') else result

        # Find data classes
        data_classes = [u for u in units if u["type"] == "class" and "Point" in u["name"]]
        assert len(data_classes) > 0, "Should extract Point data class"


class TestKotlinClassExtraction:
    """Test extraction of Kotlin classes."""

    def test_class_extraction(self, sample_kotlin_file):
        """Test extraction of Kotlin classes."""
        content = sample_kotlin_file.read_text()

        result = parse_source_file(str(sample_kotlin_file), content)
        units = result.units if hasattr(result, 'units') else result

        # Find classes
        classes = [u for u in units if u["type"] == "class" and "Shape" in u["name"]]
        assert len(classes) > 0, "Should extract Shape class"


class TestKotlinObjectExtraction:
    """Test extraction of Kotlin objects (singletons)."""

    def test_object_extraction(self, sample_kotlin_file):
        """Test extraction of Kotlin object declarations."""
        content = sample_kotlin_file.read_text()

        result = parse_source_file(str(sample_kotlin_file), content)
        units = result.units if hasattr(result, 'units') else result

        # Find objects
        objects = [u for u in units if u["type"] == "class" and "MathUtils" in u["name"]]
        assert len(objects) > 0, "Should extract MathUtils object"


class TestKotlinInterfaceExtraction:
    """Test extraction of Kotlin interfaces."""

    def test_interface_extraction(self, sample_kotlin_file):
        """Test extraction of Kotlin interfaces."""
        content = sample_kotlin_file.read_text()

        result = parse_source_file(str(sample_kotlin_file), content)
        units = result.units if hasattr(result, 'units') else result

        # Find interfaces
        interfaces = [u for u in units if u["type"] == "class" and "Drawable" in u["name"]]
        assert len(interfaces) > 0, "Should extract Drawable interface"


class TestKotlinComplexScenarios:
    """Test complex Kotlin parsing scenarios."""

    def test_multiple_semantic_units(self, sample_kotlin_file):
        """Test that multiple semantic units are extracted."""
        content = sample_kotlin_file.read_text()

        result = parse_source_file(str(sample_kotlin_file), content)
        units = result.units if hasattr(result, 'units') else result

        # Should extract interfaces, classes, data classes, objects, and functions
        assert len(units) > 3, "Should extract multiple semantic units"

    def test_unit_metadata(self, sample_kotlin_file):
        """Test that unit metadata is correctly populated."""
        content = sample_kotlin_file.read_text()

        result = parse_source_file(str(sample_kotlin_file), content)
        units = result.units if hasattr(result, 'units') else result

        # Check that units have required metadata
        for unit in units:
            assert unit["file_path"] == str(sample_kotlin_file)
            assert unit["language"] == "Kotlin"
            assert unit["start_line"] > 0
            assert unit["end_line"] >= unit["start_line"]
            assert len(unit["content"]) > 0


class TestKotlinEdgeCases:
    """Test edge cases in Kotlin parsing."""

    def test_empty_kotlin_file(self, tmp_path):
        """Test parsing of an empty Kotlin file."""
        empty_file = tmp_path / "empty.kt"
        empty_file.write_text("")

        content = empty_file.read_text()


        result = parse_source_file(str(empty_file), content)
        units = result.units if hasattr(result, 'units') else result
        assert units == [] or len(units) == 0, "Empty file should produce no units"

    def test_kotlin_file_with_only_comments(self, tmp_path):
        """Test parsing of a Kotlin file with only comments."""
        comment_file = tmp_path / "comments.kt"
        comment_file.write_text("""
// This is a comment
// Another comment
/* Multi-line
   comment */
""")

        content = comment_file.read_text()


        result = parse_source_file(str(comment_file), content)
        units = result.units if hasattr(result, 'units') else result
        assert len(units) == 0, "File with only comments should produce no units"
