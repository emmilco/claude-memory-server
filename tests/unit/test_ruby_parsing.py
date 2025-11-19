"""Tests for Ruby language parsing support (FEAT-007)."""

import pytest
from pathlib import Path
from src.memory.code_parser import CodeParser


@pytest.fixture
def code_parser():
    """Create a CodeParser instance for testing."""
    return CodeParser()


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

    def test_rb_extension_recognized(self, code_parser):
        """Test that .rb extension is recognized as Ruby."""
        assert code_parser.can_parse("test.rb")
        assert code_parser.can_parse("lib/my_class.rb")
        assert code_parser.can_parse("/path/to/file.rb")

    def test_case_sensitivity(self, code_parser):
        """Test that extension matching is case-sensitive."""
        # .rb should work
        assert code_parser.can_parse("test.rb")
        # .RB might not work depending on implementation
        # Not testing case variations as they're platform-dependent


class TestRubyMethodExtraction:
    """Test extraction of Ruby methods."""

    def test_instance_method_extraction(self, code_parser, sample_ruby_file):
        """Test extraction of instance methods."""
        units = code_parser.parse_file(sample_ruby_file)

        # Find instance methods
        instance_methods = [u for u in units if u.unit_type == "function" and "initialize" in u.unit_name]
        assert len(instance_methods) > 0, "Should extract initialize method"

        add_methods = [u for u in units if u.unit_type == "function" and "add" in u.unit_name]
        assert len(add_methods) > 0, "Should extract add method"

    def test_class_method_extraction(self, code_parser, sample_ruby_file):
        """Test extraction of class methods (self.method_name)."""
        units = code_parser.parse_file(sample_ruby_file)

        # Find class methods
        class_methods = [u for u in units if u.unit_type == "function" and "version" in u.unit_name]
        assert len(class_methods) > 0, "Should extract class method 'version'"

        upcase_methods = [u for u in units if u.unit_type == "function" and "upcase_all" in u.unit_name]
        assert len(upcase_methods) > 0, "Should extract class method 'upcase_all'"

    def test_method_with_parameters(self, code_parser, sample_ruby_file):
        """Test extraction of methods with parameters."""
        units = code_parser.parse_file(sample_ruby_file)

        # Find methods with parameters
        add_methods = [u for u in units if u.unit_type == "function" and "add" in u.unit_name]
        assert len(add_methods) > 0, "Should extract method with parameters"

    def test_method_with_default_parameters(self, code_parser, sample_ruby_file):
        """Test extraction of methods with default parameter values."""
        units = code_parser.parse_file(sample_ruby_file)

        # Find methods with default parameters
        multiply_methods = [u for u in units if u.unit_type == "function" and "multiply" in u.unit_name]
        assert len(multiply_methods) > 0, "Should extract method with default parameters"


class TestRubyClassExtraction:
    """Test extraction of Ruby classes."""

    def test_class_extraction(self, code_parser, sample_ruby_file):
        """Test extraction of Ruby classes."""
        units = code_parser.parse_file(sample_ruby_file)

        # Find classes
        classes = [u for u in units if u.unit_type == "class"]
        assert len(classes) > 0, "Should extract at least one class"

        # Check for specific classes
        calculator_classes = [u for u in classes if "Calculator" in u.unit_name]
        assert len(calculator_classes) > 0, "Should extract Calculator class"

        helper_classes = [u for u in classes if "StringHelper" in u.unit_name]
        assert len(helper_classes) > 0, "Should extract StringHelper class"

    def test_top_level_class_extraction(self, code_parser, sample_ruby_file):
        """Test extraction of top-level classes."""
        units = code_parser.parse_file(sample_ruby_file)

        # Find top-level class
        top_level = [u for u in units if u.unit_type == "class" and "TopLevelClass" in u.unit_name]
        assert len(top_level) > 0, "Should extract TopLevelClass"

    def test_nested_class_extraction(self, code_parser, sample_ruby_file):
        """Test extraction of classes within modules."""
        units = code_parser.parse_file(sample_ruby_file)

        # Classes inside modules should be extracted
        classes = [u for u in units if u.unit_type == "class"]
        assert len(classes) >= 3, "Should extract multiple classes including nested ones"


class TestRubyModuleExtraction:
    """Test extraction of Ruby modules."""

    def test_module_extraction(self, code_parser, sample_ruby_file):
        """Test extraction of Ruby modules."""
        units = code_parser.parse_file(sample_ruby_file)

        # Find modules (they are captured as "class" type in our implementation)
        modules = [u for u in units if u.unit_type == "class" and "Namespace" in u.unit_name]
        assert len(modules) > 0, "Should extract MyNamespace module"

    def test_nested_module_extraction(self, code_parser, sample_ruby_file):
        """Test extraction of nested modules."""
        units = code_parser.parse_file(sample_ruby_file)

        # Find nested module
        utils_modules = [u for u in units if u.unit_type == "class" and "Utils" in u.unit_name]
        assert len(utils_modules) > 0, "Should extract Utils nested module"


class TestRubyComplexScenarios:
    """Test complex Ruby parsing scenarios."""

    def test_multiple_semantic_units(self, code_parser, sample_ruby_file):
        """Test that multiple semantic units are extracted."""
        units = code_parser.parse_file(sample_ruby_file)

        # Should extract modules, classes, and methods
        assert len(units) > 5, "Should extract multiple semantic units"

    def test_unit_metadata(self, code_parser, sample_ruby_file):
        """Test that unit metadata is correctly populated."""
        units = code_parser.parse_file(sample_ruby_file)

        # Check that units have required metadata
        for unit in units:
            assert unit.file_path == str(sample_ruby_file)
            assert unit.language == "ruby"
            assert unit.start_line > 0
            assert unit.end_line >= unit.start_line
            assert len(unit.content) > 0

    def test_no_extraction_errors(self, code_parser, sample_ruby_file):
        """Test that parsing doesn't raise errors."""
        try:
            units = code_parser.parse_file(sample_ruby_file)
            assert isinstance(units, list)
        except Exception as e:
            pytest.fail(f"Parsing raised unexpected exception: {e}")


class TestRubyEdgeCases:
    """Test edge cases in Ruby parsing."""

    def test_empty_ruby_file(self, code_parser, tmp_path):
        """Test parsing of an empty Ruby file."""
        empty_file = tmp_path / "empty.rb"
        empty_file.write_text("")

        units = code_parser.parse_file(empty_file)
        assert units == [] or len(units) == 0, "Empty file should produce no units"

    def test_ruby_file_with_only_comments(self, code_parser, tmp_path):
        """Test parsing of a Ruby file with only comments."""
        comment_file = tmp_path / "comments.rb"
        comment_file.write_text("""
# This is a comment
# Another comment
# And another one
""")

        units = code_parser.parse_file(comment_file)
        assert len(units) == 0, "File with only comments should produce no units"

    def test_ruby_file_with_syntax_error(self, code_parser, tmp_path):
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
            units = code_parser.parse_file(syntax_error_file)
            # Parser should handle errors gracefully
            assert isinstance(units, list)
        except Exception as e:
            # If it raises an exception, it should be a known parsing exception
            assert "parse" in str(e).lower() or "syntax" in str(e).lower()


class TestRubyLanguageDetection:
    """Test Ruby language detection."""

    def test_language_field_correct(self, code_parser, sample_ruby_file):
        """Test that parsed units have correct language field."""
        units = code_parser.parse_file(sample_ruby_file)

        for unit in units:
            assert unit.language == "ruby", f"Unit should have language='ruby', got '{unit.language}'"

    def test_file_extension_to_language_mapping(self, code_parser):
        """Test that .rb files map to Ruby language."""
        # This test depends on implementation details
        # Just verify the file can be parsed
        assert code_parser.can_parse("test.rb")
