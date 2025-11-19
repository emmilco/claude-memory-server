"""Tests for Kotlin language parsing support (FEAT-010)."""

import pytest
from pathlib import Path
from src.memory.code_parser import CodeParser


@pytest.fixture
def code_parser():
    """Create a CodeParser instance for testing."""
    return CodeParser()


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

    def test_kotlin_extension_recognized(self, code_parser):
        """Test that .kt extension is recognized as Kotlin."""
        assert code_parser.can_parse("test.kt")
        assert code_parser.can_parse("lib/MyClass.kt")
        assert code_parser.can_parse("/path/to/file.kt")

    def test_kotlin_script_extension_recognized(self, code_parser):
        """Test that .kts extension is recognized as Kotlin."""
        assert code_parser.can_parse("script.kts")
        assert code_parser.can_parse("build.gradle.kts")


class TestKotlinFunctionExtraction:
    """Test extraction of Kotlin functions."""

    def test_function_extraction(self, code_parser, sample_kotlin_file):
        """Test extraction of top-level functions."""
        units = code_parser.parse_file(sample_kotlin_file)

        # Find functions
        functions = [u for u in units if u.unit_type == "function" and "greet" in u.unit_name.lower()]
        assert len(functions) > 0, "Should extract greet function"

    def test_method_extraction(self, code_parser, sample_kotlin_file):
        """Test extraction of methods from classes."""
        units = code_parser.parse_file(sample_kotlin_file)

        # Find methods
        draw_methods = [u for u in units if u.unit_type == "function" and "draw" in u.unit_name.lower()]
        assert len(draw_methods) > 0, "Should extract draw method"

    def test_companion_object_method_extraction(self, code_parser, sample_kotlin_file):
        """Test extraction of companion object methods."""
        units = code_parser.parse_file(sample_kotlin_file)

        # Find companion object methods
        create_methods = [u for u in units if u.unit_type == "function" and "createDefault" in u.unit_name]
        assert len(create_methods) > 0, "Should extract companion object method"


class TestKotlinDataClassExtraction:
    """Test extraction of Kotlin data classes."""

    def test_data_class_extraction(self, code_parser, sample_kotlin_file):
        """Test extraction of Kotlin data classes."""
        units = code_parser.parse_file(sample_kotlin_file)

        # Find data classes
        data_classes = [u for u in units if u.unit_type == "class" and "Point" in u.unit_name]
        assert len(data_classes) > 0, "Should extract Point data class"


class TestKotlinClassExtraction:
    """Test extraction of Kotlin classes."""

    def test_class_extraction(self, code_parser, sample_kotlin_file):
        """Test extraction of Kotlin classes."""
        units = code_parser.parse_file(sample_kotlin_file)

        # Find classes
        classes = [u for u in units if u.unit_type == "class" and "Shape" in u.unit_name]
        assert len(classes) > 0, "Should extract Shape class"


class TestKotlinObjectExtraction:
    """Test extraction of Kotlin objects (singletons)."""

    def test_object_extraction(self, code_parser, sample_kotlin_file):
        """Test extraction of Kotlin object declarations."""
        units = code_parser.parse_file(sample_kotlin_file)

        # Find objects
        objects = [u for u in units if u.unit_type == "class" and "MathUtils" in u.unit_name]
        assert len(objects) > 0, "Should extract MathUtils object"


class TestKotlinInterfaceExtraction:
    """Test extraction of Kotlin interfaces."""

    def test_interface_extraction(self, code_parser, sample_kotlin_file):
        """Test extraction of Kotlin interfaces."""
        units = code_parser.parse_file(sample_kotlin_file)

        # Find interfaces
        interfaces = [u for u in units if u.unit_type == "class" and "Drawable" in u.unit_name]
        assert len(interfaces) > 0, "Should extract Drawable interface"


class TestKotlinComplexScenarios:
    """Test complex Kotlin parsing scenarios."""

    def test_multiple_semantic_units(self, code_parser, sample_kotlin_file):
        """Test that multiple semantic units are extracted."""
        units = code_parser.parse_file(sample_kotlin_file)

        # Should extract interfaces, classes, data classes, objects, and functions
        assert len(units) > 3, "Should extract multiple semantic units"

    def test_unit_metadata(self, code_parser, sample_kotlin_file):
        """Test that unit metadata is correctly populated."""
        units = code_parser.parse_file(sample_kotlin_file)

        # Check that units have required metadata
        for unit in units:
            assert unit.file_path == str(sample_kotlin_file)
            assert unit.language == "Kotlin"
            assert unit.start_line > 0
            assert unit.end_line >= unit.start_line
            assert len(unit.content) > 0


class TestKotlinEdgeCases:
    """Test edge cases in Kotlin parsing."""

    def test_empty_kotlin_file(self, code_parser, tmp_path):
        """Test parsing of an empty Kotlin file."""
        empty_file = tmp_path / "empty.kt"
        empty_file.write_text("")

        units = code_parser.parse_file(empty_file)
        assert units == [] or len(units) == 0, "Empty file should produce no units"

    def test_kotlin_file_with_only_comments(self, code_parser, tmp_path):
        """Test parsing of a Kotlin file with only comments."""
        comment_file = tmp_path / "comments.kt"
        comment_file.write_text("""
// This is a comment
// Another comment
/* Multi-line
   comment */
""")

        units = code_parser.parse_file(comment_file)
        assert len(units) == 0, "File with only comments should produce no units"
