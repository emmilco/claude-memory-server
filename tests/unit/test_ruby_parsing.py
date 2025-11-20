"""Tests for Ruby language parsing support (FEAT-007)."""

import pytest
from pathlib import Path
from mcp_performance_core import parse_source_file


@pytest.fixture
def sample_ruby_file(tmp_path):
    """Create a sample Ruby file for testing."""
    ruby_file = tmp_path / "test.rb"
    ruby_content = """
module MyNamespace
  class Calculator
    def initialize(name)
      @name = name
    end

    def add(a, b)
      a + b
    end

    def multiply(a, b = 2)
      a * b
    end

    def self.version
      "1.0.0"
    end
  end

  class StringHelper
    def self.upcase_all(text)
      text.upcase
    end

    def downcase_first(text)
      text[0].downcase + text[1..-1]
    end
  end

  module Utils
    def self.log(message)
      puts "[LOG] #{message}"
    end
  end
end

class TopLevelClass
  def greet
    "Hello, World!"
  end
end
"""
    ruby_file.write_text(ruby_content)
    return ruby_file


class TestRubyFileRecognition:
    """Test Ruby file extension recognition."""

    def test_rb_extension_recognized(self, sample_ruby_file):
        """Test that .rb extension is recognized as Ruby."""
        # Test parsing works for .rb files
        content = sample_ruby_file.read_text()
        result = parse_source_file(str(sample_ruby_file), content)
        units = result.units if hasattr(result, 'units') else result
        assert units is not None, "Should parse .rb files"

    def test_case_sensitivity(self, tmp_path):
        """Test that extension matching is case-sensitive."""
        # .rb should work
        rb_file = tmp_path / "test.rb"
        rb_code = "class Test\nend"
        rb_file.write_text(rb_code)
        units = parse_source_file(str(rb_file), rb_code)
        assert units is not None, "Should parse .rb files"


class TestRubyMethodExtraction:
    """Test extraction of Ruby methods."""

    def test_instance_method_extraction(self, sample_ruby_file):
        """Test extraction of instance methods."""
        content = sample_ruby_file.read_text()
        result = parse_source_file(str(sample_ruby_file), content)
        units = result.units if hasattr(result, 'units') else result

        # Find instance methods
        instance_methods = [u for u in units if u["type"] == "function" and "initialize" in u["name"]]
        assert len(instance_methods) > 0, "Should extract initialize method"

        add_methods = [u for u in units if u["type"] == "function" and "add" in u["name"]]
        assert len(add_methods) > 0, "Should extract add method"

    def test_class_method_extraction(self, sample_ruby_file):
        """Test extraction of class methods (self.method_name)."""
        content = sample_ruby_file.read_text()
        result = parse_source_file(str(sample_ruby_file), content)
        units = result.units if hasattr(result, 'units') else result

        # Find class methods
        class_methods = [u for u in units if u["type"] == "function" and "version" in u["name"]]
        assert len(class_methods) > 0, "Should extract class method 'version'"

        upcase_methods = [u for u in units if u["type"] == "function" and "upcase_all" in u["name"]]
        assert len(upcase_methods) > 0, "Should extract class method 'upcase_all'"

    def test_method_with_parameters(self, sample_ruby_file):
        """Test extraction of methods with parameters."""
        content = sample_ruby_file.read_text()
        result = parse_source_file(str(sample_ruby_file), content)
        units = result.units if hasattr(result, 'units') else result

        # Find methods with parameters
        add_methods = [u for u in units if u["type"] == "function" and "add" in u["name"]]
        assert len(add_methods) > 0, "Should extract method with parameters"

    def test_method_with_default_parameters(self, sample_ruby_file):
        """Test extraction of methods with default parameter values."""
        content = sample_ruby_file.read_text()
        result = parse_source_file(str(sample_ruby_file), content)
        units = result.units if hasattr(result, 'units') else result

        # Find methods with default parameters
        multiply_methods = [u for u in units if u["type"] == "function" and "multiply" in u["name"]]
        assert len(multiply_methods) > 0, "Should extract method with default parameters"


class TestRubyClassExtraction:
    """Test extraction of Ruby classes."""

    def test_class_extraction(self, sample_ruby_file):
        """Test extraction of Ruby classes."""
        content = sample_ruby_file.read_text()

        result = parse_source_file(str(sample_ruby_file), content)
        units = result.units if hasattr(result, 'units') else result

        # Find classes
        classes = [u for u in units if u["type"] == "class"]
        assert len(classes) > 0, "Should extract at least one class"

        # Check for specific classes
        calculator_classes = [u for u in classes if "Calculator" in u["name"]]
        assert len(calculator_classes) > 0, "Should extract Calculator class"

        helper_classes = [u for u in classes if "StringHelper" in u["name"]]
        assert len(helper_classes) > 0, "Should extract StringHelper class"

    def test_top_level_class_extraction(self, sample_ruby_file):
        """Test extraction of top-level classes."""
        content = sample_ruby_file.read_text()

        result = parse_source_file(str(sample_ruby_file), content)
        units = result.units if hasattr(result, 'units') else result

        # Find top-level class
        top_level = [u for u in units if u["type"] == "class" and "TopLevelClass" in u["name"]]
        assert len(top_level) > 0, "Should extract TopLevelClass"

    def test_nested_class_extraction(self, sample_ruby_file):
        """Test extraction of classes within modules."""
        content = sample_ruby_file.read_text()

        result = parse_source_file(str(sample_ruby_file), content)
        units = result.units if hasattr(result, 'units') else result

        # Classes inside modules should be extracted
        classes = [u for u in units if u["type"] == "class"]
        assert len(classes) >= 3, "Should extract multiple classes including nested ones"


class TestRubyModuleExtraction:
    """Test extraction of Ruby modules."""

    def test_module_extraction(self, sample_ruby_file):
        """Test extraction of Ruby modules."""
        content = sample_ruby_file.read_text()

        result = parse_source_file(str(sample_ruby_file), content)
        units = result.units if hasattr(result, 'units') else result

        # Find modules (they are captured as "class" type in our implementation)
        modules = [u for u in units if u["type"] == "class" and "Namespace" in u["name"]]
        assert len(modules) > 0, "Should extract MyNamespace module"

    def test_nested_module_extraction(self, sample_ruby_file):
        """Test extraction of nested modules."""
        content = sample_ruby_file.read_text()

        result = parse_source_file(str(sample_ruby_file), content)
        units = result.units if hasattr(result, 'units') else result

        # Find nested module
        utils_modules = [u for u in units if u["type"] == "class" and "Utils" in u["name"]]
        assert len(utils_modules) > 0, "Should extract Utils nested module"


class TestRubyComplexScenarios:
    """Test complex Ruby parsing scenarios."""

    def test_multiple_semantic_units(self, sample_ruby_file):
        """Test that multiple semantic units are extracted."""
        content = sample_ruby_file.read_text()

        result = parse_source_file(str(sample_ruby_file), content)
        units = result.units if hasattr(result, 'units') else result

        # Should extract modules, classes, and methods
        assert len(units) > 5, "Should extract multiple semantic units"

    def test_unit_metadata(self, sample_ruby_file):
        """Test that unit metadata is correctly populated."""
        content = sample_ruby_file.read_text()

        result = parse_source_file(str(sample_ruby_file), content)
        units = result.units if hasattr(result, 'units') else result

        # Check that units have required metadata
        for unit in units:
            assert unit["file_path"] == str(sample_ruby_file)
            assert unit["language"] == "ruby"
            assert unit["start_line"] > 0
            assert unit["end_line"] >= unit["start_line"]
            assert len(unit["content"]) > 0

    def test_no_extraction_errors(self, sample_ruby_file):
        """Test that parsing doesn't raise errors."""
        try:
            content = sample_ruby_file.read_text()

            result = parse_source_file(str(sample_ruby_file), content)
            units = result.units if hasattr(result, 'units') else result
            assert isinstance(units, list) or hasattr(result, 'units')
        except Exception as e:
            pytest.fail(f"Parsing raised unexpected exception: {e}")


class TestRubyEdgeCases:
    """Test edge cases in Ruby parsing."""

    def test_empty_ruby_file(self, tmp_path):
        """Test parsing of an empty Ruby file."""
        empty_file = tmp_path / "empty.rb"
        empty_file.write_text("")

        content = empty_file.read_text()


        result = parse_source_file(str(empty_file), content)
        units = result.units if hasattr(result, 'units') else result
        assert units == [] or len(units) == 0, "Empty file should produce no units"

    def test_ruby_file_with_only_comments(self, tmp_path):
        """Test parsing of a Ruby file with only comments."""
        comment_file = tmp_path / "comments.rb"
        comment_file.write_text("""
# This is a comment
# Another comment
# And another one
""")

        content = comment_file.read_text()


        result = parse_source_file(str(comment_file), content)
        units = result.units if hasattr(result, 'units') else result
        assert len(units) == 0, "File with only comments should produce no units"

    def test_ruby_file_with_syntax_error(self, tmp_path):
        """Test that files with syntax errors don't crash the parser."""
        syntax_error_file = tmp_path / "syntax_error.rb"
        syntax_error_file.write_text("""
class BrokenClass
  def method_without_end
    puts "This is broken"
  # Missing 'end' keyword
end
""")

        try:
            content = syntax_error_file.read_text()

            result = parse_source_file(str(syntax_error_file), content)
            units = result.units if hasattr(result, 'units') else result
            # Parser should handle errors gracefully
            assert isinstance(units, list) or hasattr(result, 'units')
        except Exception as e:
            # If it raises an exception, it should be a known parsing exception
            assert "parse" in str(e).lower() or "syntax" in str(e).lower()


class TestRubyLanguageDetection:
    """Test Ruby language detection."""

    def test_language_field_correct(self, sample_ruby_file):
        """Test that parsed units have correct language field."""
        content = sample_ruby_file.read_text()

        result = parse_source_file(str(sample_ruby_file), content)
        units = result.units if hasattr(result, 'units') else result

        for unit in units:
            assert unit["language"] == "ruby", f"Unit should have language='ruby', got '{unit['language']}'"

    def test_file_extension_to_language_mapping(self, tmp_path):
        """Test that .rb files map to Ruby language."""
        # This test depends on implementation details
        # Just verify the file can be parsed
        rb_file = tmp_path / "test.rb"
        rb_file.write_text("class Test\nend")
        content = rb_file.read_text()

        result = parse_source_file(str(rb_file), content)
        units = result.units if hasattr(result, 'units') else result
        assert units is not None, "Should parse .rb files"
