"""
Parameterized tests for language parsing support (TEST-029).

This module consolidates common parsing test patterns for Ruby into parameterized
tests, demonstrating the pattern for future language additions.

IMPORTANT: Kotlin and Swift are NOT currently supported by the Rust parser.
The original test files (test_kotlin_parsing.py, test_swift_parsing.py) contain
tests for unsupported languages and are marked to skip. When/if Kotlin and Swift
support is added to rust_core/src/parsing.rs, those tests should be enabled
and consolidated here.

Currently supported languages (see rust_core/src/parsing.rs):
- Python (.py)
- JavaScript (.js, .jsx, .mjs)
- TypeScript (.ts, .tsx)
- Java (.java)
- Go (.go)
- Rust (.rs)
- Ruby (.rb)
- C (.c)
- C++ (.cpp, .cc, .cxx, .hpp, .h, .hxx, .hh)
- C# (.cs)
- SQL (.sql)
- PHP (.php)

NOT supported (despite having test files):
- Kotlin (.kt, .kts)
- Swift (.swift)

Test patterns covered for Ruby:
- File extension recognition
- Class extraction
- Function/method extraction
- Multiple semantic units extraction
- Unit metadata validation
- Edge cases (empty files, comments-only files)
"""

import pytest
from mcp_performance_core import parse_source_file


# =============================================================================
# Sample Code Constants
# =============================================================================

RUBY_SAMPLE = '''
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
'''

# Additional sample code for other supported languages that could be consolidated
# in future phases. These are provided as a template for expansion.

PYTHON_SAMPLE = '''
class Calculator:
    """A simple calculator class."""

    def __init__(self, name: str):
        self.name = name

    def add(self, a: int, b: int) -> int:
        return a + b

    def multiply(self, a: int, b: int = 2) -> int:
        return a * b

def greet(person: str) -> None:
    print(f"Hello, {person}!")
'''

JAVASCRIPT_SAMPLE = '''
class Calculator {
    constructor(name) {
        this.name = name;
    }

    add(a, b) {
        return a + b;
    }

    multiply(a, b = 2) {
        return a * b;
    }
}

function greet(person) {
    console.log(`Hello, ${person}!`);
}
'''


# =============================================================================
# Helper Functions
# =============================================================================

def get_unit_attr(unit, attr_name: str):
    """Get attribute from unit, handling both dict and object access patterns.

    The Rust parser returns objects with attribute access, but some code
    treats them as dicts. This helper handles both patterns.
    """
    if hasattr(unit, attr_name):
        return getattr(unit, attr_name)
    elif isinstance(unit, dict) and attr_name in unit:
        return unit[attr_name]
    # Handle common attribute name variations
    attr_mappings = {
        "type": ["unit_type", "type"],
        "unit_type": ["unit_type", "type"],
    }
    if attr_name in attr_mappings:
        for alt_name in attr_mappings[attr_name]:
            if hasattr(unit, alt_name):
                return getattr(unit, alt_name)
            elif isinstance(unit, dict) and alt_name in unit:
                return unit[alt_name]
    raise AttributeError(f"Unit has no attribute '{attr_name}'")


def parse_and_get_units(file_path: str, content: str) -> list:
    """Parse a source file and return the units list."""
    result = parse_source_file(file_path, content)
    return result.units if hasattr(result, 'units') else result


# =============================================================================
# Parameterized Tests: Multi-Language File Extension Recognition
# =============================================================================

class TestFileExtensionRecognition:
    """Test that supported language file extensions are correctly recognized.

    This tests languages that are actually supported by the Rust parser.
    """

    @pytest.mark.parametrize("extension,sample_code,expected_lang", [
        pytest.param(".rb", RUBY_SAMPLE, "Ruby", id="ruby-ext"),
        pytest.param(".py", PYTHON_SAMPLE, "Python", id="python-ext"),
        pytest.param(".js", JAVASCRIPT_SAMPLE, "JavaScript", id="javascript-ext"),
    ])
    def test_extension_recognized(self, tmp_path, extension, sample_code, expected_lang):
        """Test that file extension is recognized and parsed correctly."""
        test_file = tmp_path / f"test{extension}"
        test_file.write_text(sample_code)

        units = parse_and_get_units(str(test_file), sample_code)

        assert units is not None, f"Should parse {extension} files"
        assert len(units) > 0, f"Should extract units from {extension} files"


# =============================================================================
# Parameterized Tests: Multi-Language Class Extraction
# =============================================================================

class TestClassExtraction:
    """Test extraction of classes across supported languages."""

    @pytest.mark.parametrize("extension,sample_code,class_name", [
        pytest.param(".rb", RUBY_SAMPLE, "Calculator", id="ruby-class"),
        pytest.param(".py", PYTHON_SAMPLE, "Calculator", id="python-class"),
        pytest.param(".js", JAVASCRIPT_SAMPLE, "Calculator", id="javascript-class"),
    ])
    def test_class_extraction(self, tmp_path, extension, sample_code, class_name):
        """Test that classes are correctly extracted."""
        test_file = tmp_path / f"test{extension}"
        test_file.write_text(sample_code)

        units = parse_and_get_units(str(test_file), sample_code)

        classes = [u for u in units if get_unit_attr(u, "unit_type") == "class"
                   and class_name in get_unit_attr(u, "name")]
        assert len(classes) > 0, f"Should extract {class_name} class for {extension}"


# =============================================================================
# Parameterized Tests: Multi-Language Function Extraction
# =============================================================================

class TestFunctionExtraction:
    """Test extraction of functions across supported languages."""

    @pytest.mark.parametrize("extension,sample_code,function_name", [
        pytest.param(".rb", RUBY_SAMPLE, "add", id="ruby-method"),
        pytest.param(".py", PYTHON_SAMPLE, "greet", id="python-function"),
        pytest.param(".js", JAVASCRIPT_SAMPLE, "greet", id="javascript-function"),
    ])
    def test_function_extraction(self, tmp_path, extension, sample_code, function_name):
        """Test that functions/methods are correctly extracted."""
        test_file = tmp_path / f"test{extension}"
        test_file.write_text(sample_code)

        units = parse_and_get_units(str(test_file), sample_code)

        functions = [u for u in units if get_unit_attr(u, "unit_type") == "function"
                     and function_name in get_unit_attr(u, "name").lower()]
        assert len(functions) > 0, f"Should extract {function_name} function/method for {extension}"


# =============================================================================
# Parameterized Tests: Multi-Language Multiple Units Extraction
# =============================================================================

class TestMultipleSemanticUnits:
    """Test that multiple semantic units are extracted from source files."""

    @pytest.mark.parametrize("extension,sample_code,min_units", [
        pytest.param(".rb", RUBY_SAMPLE, 5, id="ruby-multi-units"),
        pytest.param(".py", PYTHON_SAMPLE, 2, id="python-multi-units"),
        pytest.param(".js", JAVASCRIPT_SAMPLE, 2, id="javascript-multi-units"),
    ])
    def test_multiple_units_extracted(self, tmp_path, extension, sample_code, min_units):
        """Test that multiple semantic units are extracted."""
        test_file = tmp_path / f"test{extension}"
        test_file.write_text(sample_code)

        units = parse_and_get_units(str(test_file), sample_code)

        assert len(units) >= min_units, \
            f"Should extract at least {min_units} semantic units for {extension}, got {len(units)}"


# =============================================================================
# Parameterized Tests: Multi-Language Unit Metadata Validation
# =============================================================================

class TestUnitMetadata:
    """Test that unit metadata is correctly populated."""

    @pytest.mark.parametrize("extension,sample_code,expected_lang", [
        pytest.param(".rb", RUBY_SAMPLE, "Ruby", id="ruby-metadata"),
        pytest.param(".py", PYTHON_SAMPLE, "Python", id="python-metadata"),
        pytest.param(".js", JAVASCRIPT_SAMPLE, "JavaScript", id="javascript-metadata"),
    ])
    def test_unit_metadata_correct(self, tmp_path, extension, sample_code, expected_lang):
        """Test that units have required metadata fields."""
        test_file = tmp_path / f"test{extension}"
        test_file.write_text(sample_code)

        units = parse_and_get_units(str(test_file), sample_code)

        assert len(units) > 0, "Should extract at least one unit"

        for unit in units:
            # Verify language
            unit_lang = get_unit_attr(unit, "language")
            assert unit_lang == expected_lang, \
                f"Unit should have language='{expected_lang}', got '{unit_lang}'"

            # Verify line numbers
            start_line = get_unit_attr(unit, "start_line")
            end_line = get_unit_attr(unit, "end_line")
            assert start_line > 0, "start_line should be positive"
            assert end_line >= start_line, "end_line should be >= start_line"

            # Verify content
            content = get_unit_attr(unit, "content")
            assert len(content) > 0, "content should not be empty"

    @pytest.mark.parametrize("extension,sample_code,expected_lang", [
        pytest.param(".rb", RUBY_SAMPLE, "Ruby", id="ruby-file-path"),
        pytest.param(".py", PYTHON_SAMPLE, "Python", id="python-file-path"),
        pytest.param(".js", JAVASCRIPT_SAMPLE, "JavaScript", id="javascript-file-path"),
    ])
    def test_result_file_path_correct(self, tmp_path, extension, sample_code, expected_lang):
        """Test that parse result has correct file_path metadata.

        Note: file_path is stored on the ParseResult, not individual SemanticUnit objects.
        """
        test_file = tmp_path / f"test{extension}"
        test_file.write_text(sample_code)

        result = parse_source_file(str(test_file), sample_code)

        assert result.file_path == str(test_file), \
            f"file_path should be '{test_file}', got '{result.file_path}'"


# =============================================================================
# Parameterized Tests: Multi-Language Edge Cases
# =============================================================================

class TestEdgeCases:
    """Test edge cases in language parsing."""

    @pytest.mark.parametrize("extension", [
        pytest.param(".rb", id="ruby-empty"),
        pytest.param(".py", id="python-empty"),
        pytest.param(".js", id="javascript-empty"),
    ])
    def test_empty_file(self, tmp_path, extension):
        """Test parsing of an empty file produces no units."""
        empty_file = tmp_path / f"empty{extension}"
        empty_file.write_text("")

        units = parse_and_get_units(str(empty_file), "")

        assert units == [] or len(units) == 0, \
            f"Empty {extension} file should produce no units"

    @pytest.mark.parametrize("extension,comment_content", [
        pytest.param(".rb", "# Comment\n# Another comment\n# More", id="ruby-comments"),
        pytest.param(".py", "# Comment\n# Another comment\n# More", id="python-comments"),
        pytest.param(".js", "// Comment\n// Another\n/* Multi\nline */", id="javascript-comments"),
    ])
    def test_comments_only_file(self, tmp_path, extension, comment_content):
        """Test parsing of a file with only comments produces no units."""
        comment_file = tmp_path / f"comments{extension}"
        comment_file.write_text(comment_content)

        units = parse_and_get_units(str(comment_file), comment_content)

        assert len(units) == 0, \
            f"{extension} file with only comments should produce no units"


# =============================================================================
# Ruby-Specific Tests (Consolidated from test_ruby_parsing.py patterns)
# =============================================================================

class TestRubySpecificFeatures:
    """Test Ruby-specific parsing features.

    These tests cover Ruby-specific constructs that don't apply to other
    languages and thus cannot be parameterized.
    """

    def test_module_extraction(self, tmp_path):
        """Test extraction of Ruby modules."""
        test_file = tmp_path / "test.rb"
        test_file.write_text(RUBY_SAMPLE)

        units = parse_and_get_units(str(test_file), RUBY_SAMPLE)

        # Modules are captured as "class" type in our implementation
        modules = [u for u in units if get_unit_attr(u, "unit_type") == "class"
                   and "Namespace" in get_unit_attr(u, "name")]
        assert len(modules) > 0, "Should extract MyNamespace module"

    def test_nested_module_extraction(self, tmp_path):
        """Test extraction of nested Ruby modules."""
        test_file = tmp_path / "test.rb"
        test_file.write_text(RUBY_SAMPLE)

        units = parse_and_get_units(str(test_file), RUBY_SAMPLE)

        # Find nested module
        utils_modules = [u for u in units if get_unit_attr(u, "unit_type") == "class"
                         and "Utils" in get_unit_attr(u, "name")]
        assert len(utils_modules) > 0, "Should extract Utils nested module"

    def test_method_with_default_parameters(self, tmp_path):
        """Test extraction of Ruby methods with default parameter values."""
        test_file = tmp_path / "test.rb"
        test_file.write_text(RUBY_SAMPLE)

        units = parse_and_get_units(str(test_file), RUBY_SAMPLE)

        # Find methods with default parameters
        multiply_methods = [u for u in units if get_unit_attr(u, "unit_type") == "function"
                            and "multiply" in get_unit_attr(u, "name")]
        assert len(multiply_methods) > 0, "Should extract method with default parameters"

    def test_nested_class_extraction(self, tmp_path):
        """Test extraction of classes within modules."""
        test_file = tmp_path / "test.rb"
        test_file.write_text(RUBY_SAMPLE)

        units = parse_and_get_units(str(test_file), RUBY_SAMPLE)

        # Classes inside modules should be extracted
        classes = [u for u in units if get_unit_attr(u, "unit_type") == "class"]
        assert len(classes) >= 3, "Should extract multiple classes including nested ones"

    def test_top_level_class_extraction(self, tmp_path):
        """Test extraction of top-level Ruby classes."""
        test_file = tmp_path / "test.rb"
        test_file.write_text(RUBY_SAMPLE)

        units = parse_and_get_units(str(test_file), RUBY_SAMPLE)

        # Find top-level class
        top_level = [u for u in units if get_unit_attr(u, "unit_type") == "class"
                     and "TopLevelClass" in get_unit_attr(u, "name")]
        assert len(top_level) > 0, "Should extract TopLevelClass"
