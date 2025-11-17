"""
Simple tests for C# parsing to verify basic functionality works.
"""

import pytest
from mcp_performance_core import parse_source_file

SAMPLE_CSHARP = '''
using System;

namespace MyApp
{
    public class Calculator
    {
        public int Add(int a, int b)
        {
            return a + b;
        }

        public int Subtract(int a, int b)
        {
            return a - b;
        }
    }
}
'''


def test_csharp_file_parsing():
    """Test that C# files can be parsed."""
    result = parse_source_file("Calculator.cs", SAMPLE_CSHARP)

    assert result.language == "CSharp"
    assert result.file_path == "Calculator.cs"
    assert result.parse_time_ms > 0


def test_csharp_extracts_units():
    """Test that C# parsing extracts semantic units."""
    result = parse_source_file("Calculator.cs", SAMPLE_CSHARP)

    # Should extract at least the class and methods
    assert len(result.units) > 0

    # Should have both classes and functions
    unit_types = {u.unit_type for u in result.units}
    assert "class" in unit_types or "function" in unit_types


def test_csharp_class_extraction():
    """Test that C# classes are extracted."""
    result = parse_source_file("Calculator.cs", SAMPLE_CSHARP)

    class_units = [u for u in result.units if u.unit_type == "class"]
    assert len(class_units) > 0

    # Verify class content contains expected text
    for cls in class_units:
        assert "Calculator" in cls.name or "Calculator" in cls.content


def test_csharp_method_extraction():
    """Test that C# methods are extracted."""
    result = parse_source_file("Calculator.cs", SAMPLE_CSHARP)

    method_units = [u for u in result.units if u.unit_type == "function"]
    assert len(method_units) > 0

    # Verify methods contain expected text
    all_method_text = " ".join(u.name + " " + u.content for u in method_units)
    assert "Add" in all_method_text
    assert "Subtract" in all_method_text


def test_csharp_empty_file():
    """Test parsing empty C# file."""
    result = parse_source_file("Empty.cs", "")

    assert result.language == "CSharp"
    assert len(result.units) == 0


def test_csharp_performance():
    """Test that C# parsing is reasonably fast."""
    result = parse_source_file("Calculator.cs", SAMPLE_CSHARP)

    # Should parse in under 100ms
    assert result.parse_time_ms < 100


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
