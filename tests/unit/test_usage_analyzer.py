"""
Unit tests for UsageAnalyzer (FEAT-049).

Tests usage pattern analysis including:
- Call graph construction
- Caller counting
- Public vs private API detection
- Export detection
- Usage boost calculation
"""

import pytest
from pathlib import Path
from src.analysis.usage_analyzer import UsageAnalyzer


@pytest.fixture
def analyzer():
    """Create a UsageAnalyzer instance."""
    return UsageAnalyzer()


class TestCallGraphConstruction:
    """Tests for call graph construction."""

    def test_empty_units(self, analyzer):
        """Empty unit list produces empty call graph."""
        analyzer._build_call_graph([], "python")
        assert len(analyzer.call_graph) == 0

    def test_single_function_no_calls(self, analyzer):
        """Single function with no calls."""
        units = [
            {
                "name": "simple_func",
                "content": "def simple_func():\n    return 42",
                "unit_type": "function",
                "language": "python",
            }
        ]
        analyzer._build_call_graph(units, "python")
        assert "simple_func" not in analyzer.call_graph or len(analyzer.call_graph.get("simple_func", set())) == 0

    def test_function_calls_another(self, analyzer):
        """Function calling another function."""
        units = [
            {
                "name": "caller",
                "content": "def caller():\n    return callee()",
                "unit_type": "function",
                "language": "python",
            },
            {
                "name": "callee",
                "content": "def callee():\n    return 42",
                "unit_type": "function",
                "language": "python",
            },
        ]
        analyzer._build_call_graph(units, "python")
        assert "callee" in analyzer.call_graph
        assert "caller" in analyzer.call_graph["callee"]

    def test_multiple_callers(self, analyzer):
        """Multiple functions calling the same function."""
        units = [
            {"name": "caller1", "content": "def caller1():\n    return target()", "unit_type": "function", "language": "python"},
            {"name": "caller2", "content": "def caller2():\n    return target()", "unit_type": "function", "language": "python"},
            {"name": "caller3", "content": "def caller3():\n    return target()", "unit_type": "function", "language": "python"},
            {"name": "target", "content": "def target():\n    return 42", "unit_type": "function", "language": "python"},
        ]
        analyzer._build_call_graph(units, "python")
        assert len(analyzer.call_graph["target"]) == 3

    def test_no_self_calls(self, analyzer):
        """Functions don't register as calling themselves."""
        units = [
            {
                "name": "recursive",
                "content": "def recursive(n):\n    if n > 0:\n        return recursive(n-1)\n    return 0",
                "unit_type": "function",
                "language": "python",
            }
        ]
        analyzer._build_call_graph(units, "python")
        # Self-calls should be filtered out
        assert "recursive" not in analyzer.call_graph.get("recursive", set())


class TestFunctionCallExtraction:
    """Tests for extracting function calls from code."""

    def test_python_function_calls(self, analyzer):
        """Extract function calls from Python code."""
        code = "result = func1(x) + func2(y)"
        calls = analyzer._extract_function_calls(code, "python")
        assert "func1" in calls
        assert "func2" in calls

    def test_javascript_function_calls(self, analyzer):
        """Extract function calls from JavaScript code."""
        code = "const result = func1(x) + func2(y);"
        calls = analyzer._extract_function_calls(code, "javascript")
        assert "func1" in calls
        assert "func2" in calls

    def test_method_calls(self, analyzer):
        """Extract method calls."""
        code = "obj.method1(x)\nobj.method2(y)"
        calls = analyzer._extract_function_calls(code, "python")
        assert "method1" in calls
        assert "method2" in calls

    def test_nested_calls(self, analyzer):
        """Extract nested function calls."""
        code = "outer(inner(x))"
        calls = analyzer._extract_function_calls(code, "python")
        assert "outer" in calls
        assert "inner" in calls


class TestCallerCounting:
    """Tests for counting callers."""

    def test_no_callers(self, analyzer):
        """Function with no callers returns 0."""
        assert analyzer._count_callers("unused_func") == 0

    def test_single_caller(self, analyzer):
        """Function with one caller."""
        analyzer.call_graph = {"target": {"caller1"}}
        assert analyzer._count_callers("target") == 1

    def test_multiple_callers(self, analyzer):
        """Function with multiple callers."""
        analyzer.call_graph = {"target": {"caller1", "caller2", "caller3"}}
        assert analyzer._count_callers("target") == 3


class TestPublicAPIDetection:
    """Tests for public vs private API detection."""

    def test_python_public_function(self, analyzer):
        """Python function without underscore is public."""
        assert analyzer._is_public_api("public_function", "function", "python") is True

    def test_python_private_function(self, analyzer):
        """Python function with single underscore is private."""
        assert analyzer._is_public_api("_private_function", "function", "python") is False

    def test_python_dunder_function(self, analyzer):
        """Python function with double underscore is private."""
        assert analyzer._is_public_api("__private_function", "function", "python") is False

    def test_javascript_public_function(self, analyzer):
        """JavaScript function without underscore is public."""
        assert analyzer._is_public_api("publicFunction", "function", "javascript") is True

    def test_javascript_private_function(self, analyzer):
        """JavaScript function with underscore is private."""
        assert analyzer._is_public_api("_privateFunction", "function", "javascript") is False

    def test_go_exported_function(self, analyzer):
        """Go function with uppercase first letter is exported."""
        assert analyzer._is_public_api("ExportedFunc", "function", "go") is True

    def test_go_unexported_function(self, analyzer):
        """Go function with lowercase first letter is unexported."""
        assert analyzer._is_public_api("unexportedFunc", "function", "go") is False

    def test_empty_name(self, analyzer):
        """Empty name is not public."""
        assert analyzer._is_public_api("", "function", "python") is False


class TestExportDetection:
    """Tests for export detection."""

    def test_python_no_all_list(self, analyzer):
        """Python without __all__ assumes public functions are exported."""
        file_content = """
def public_func():
    pass

def _private_func():
    pass
"""
        assert analyzer._is_exported("public_func", file_content, "python") is True
        assert analyzer._is_exported("_private_func", file_content, "python") is False

    def test_python_all_list(self, analyzer):
        """Python with __all__ list."""
        file_content = """
__all__ = ['exported_func', 'another_func']

def exported_func():
    pass

def not_exported():
    pass
"""
        assert analyzer._is_exported("exported_func", file_content, "python") is True
        assert analyzer._is_exported("not_exported", file_content, "python") is False

    def test_javascript_export_keyword(self, analyzer):
        """JavaScript export keyword detection."""
        file_content = """
export function exportedFunc() {
    return 42;
}

function notExported() {
    return 0;
}
"""
        assert analyzer._is_exported("exportedFunc", file_content, "javascript") is True
        assert analyzer._is_exported("notExported", file_content, "javascript") is False

    def test_javascript_export_block(self, analyzer):
        """JavaScript export block detection."""
        file_content = """
function func1() {}
function func2() {}

export { func1, func2 };
"""
        assert analyzer._is_exported("func1", file_content, "javascript") is True
        assert analyzer._is_exported("func2", file_content, "javascript") is True

    def test_javascript_default_export(self, analyzer):
        """JavaScript default export detection."""
        file_content = """
function MainComponent() {}

export default MainComponent;
"""
        assert analyzer._is_exported("MainComponent", file_content, "javascript") is True

    def test_java_public_method(self, analyzer):
        """Java public method detection."""
        file_content = """
public class MyClass {
    public void publicMethod() {}
    private void privateMethod() {}
}
"""
        assert analyzer._is_exported("publicMethod", file_content, "java") is True
        assert analyzer._is_exported("privateMethod", file_content, "java") is False

    def test_go_exported_func(self, analyzer):
        """Go exported function (uppercase)."""
        file_content = """
func ExportedFunc() {}
func unexportedFunc() {}
"""
        assert analyzer._is_exported("ExportedFunc", file_content, "go") is True
        assert analyzer._is_exported("unexportedFunc", file_content, "go") is False

    def test_no_file_content(self, analyzer):
        """No file content returns False."""
        assert analyzer._is_exported("func", None, "python") is False
        assert analyzer._is_exported("func", "", "python") is False


class TestUsageBoostCalculation:
    """Tests for usage boost calculation."""

    def test_no_usage(self, analyzer):
        """No usage = 0 boost."""
        boost = analyzer._calculate_usage_boost(0, False, False)
        assert boost == 0.0

    def test_single_caller(self, analyzer):
        """Single caller gets small boost."""
        boost = analyzer._calculate_usage_boost(1, False, False)
        assert 0.0 < boost < 0.05

    def test_many_callers(self, analyzer):
        """Many callers get high boost."""
        boost = analyzer._calculate_usage_boost(10, False, False)
        assert boost >= 0.12

    def test_public_api_boost(self, analyzer):
        """Public API gets boost."""
        boost_private = analyzer._calculate_usage_boost(0, False, False)
        boost_public = analyzer._calculate_usage_boost(0, True, False)
        assert boost_public > boost_private
        assert boost_public >= 0.04

    def test_exported_boost(self, analyzer):
        """Exported function gets boost."""
        boost_not_exported = analyzer._calculate_usage_boost(0, False, False)
        boost_exported = analyzer._calculate_usage_boost(0, False, True)
        assert boost_exported > boost_not_exported
        assert boost_exported >= 0.04

    def test_combined_boost(self, analyzer):
        """All factors combined."""
        boost = analyzer._calculate_usage_boost(10, True, True)
        assert boost >= 0.20  # High usage + public + exported

    def test_boost_capped(self, analyzer):
        """Boost is capped at MAX_USAGE_BOOST."""
        boost = analyzer._calculate_usage_boost(1000, True, True)
        assert boost <= 0.2


class TestUsageAnalysis:
    """Tests for complete usage analysis."""

    def test_analyze_simple_function(self, analyzer):
        """Analyze a simple function."""
        code_unit = {
            "name": "simple_func",
            "content": "def simple_func():\n    return 42",
            "unit_type": "function",
            "language": "python",
        }
        metrics = analyzer.analyze(code_unit)
        assert metrics.caller_count == 0
        assert metrics.is_public is True  # No underscore
        assert metrics.usage_boost >= 0.0

    def test_analyze_private_function(self, analyzer):
        """Analyze a private function."""
        code_unit = {
            "name": "_private_func",
            "content": "def _private_func():\n    return 42",
            "unit_type": "function",
            "language": "python",
        }
        metrics = analyzer.analyze(code_unit)
        assert metrics.is_public is False

    def test_analyze_with_all_units(self, analyzer):
        """Analyze with full unit list (builds call graph)."""
        all_units = [
            {"name": "caller", "content": "def caller():\n    return callee()", "unit_type": "function", "language": "python"},
            {"name": "callee", "content": "def callee():\n    return 42", "unit_type": "function", "language": "python"},
        ]
        code_unit = all_units[1]  # Analyze callee
        metrics = analyzer.analyze(code_unit, all_units=all_units)
        assert metrics.caller_count >= 1  # Called by 'caller'

    def test_analyze_with_file_content(self, analyzer):
        """Analyze with file content (for export detection)."""
        file_content = """
__all__ = ['exported_func']

def exported_func():
    return 42
"""
        code_unit = {
            "name": "exported_func",
            "content": "def exported_func():\n    return 42",
            "unit_type": "function",
            "language": "python",
        }
        metrics = analyzer.analyze(code_unit, file_content=file_content)
        assert metrics.is_exported is True


class TestResetFunctionality:
    """Tests for resetting call graph."""

    def test_reset_clears_call_graph(self, analyzer):
        """Reset clears the call graph."""
        analyzer.call_graph = {"func1": {"caller1", "caller2"}}
        analyzer.reset()
        assert len(analyzer.call_graph) == 0


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_missing_name(self, analyzer):
        """Missing name doesn't crash."""
        code_unit = {
            "name": "",
            "content": "def func(): pass",
            "unit_type": "function",
            "language": "python",
        }
        metrics = analyzer.analyze(code_unit)
        assert metrics.caller_count == 0
        assert metrics.is_public is False  # Empty name = not public

    def test_empty_content(self, analyzer):
        """Empty content doesn't crash."""
        code_unit = {
            "name": "empty_func",
            "content": "",
            "unit_type": "function",
            "language": "python",
        }
        metrics = analyzer.analyze(code_unit)
        assert metrics.usage_boost >= 0.0

    def test_malformed_units(self, analyzer):
        """Malformed units don't crash call graph construction."""
        units = [
            {"name": "valid", "content": "def valid(): pass", "unit_type": "function", "language": "python"},
            {"name": None, "content": "", "unit_type": "function", "language": "python"},  # Malformed
        ]
        analyzer._build_call_graph(units, "python")
        # Should complete without error
        assert isinstance(analyzer.call_graph, dict)
