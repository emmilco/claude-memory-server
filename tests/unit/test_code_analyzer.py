"""Tests for code analyzer module."""

from src.refactoring.code_analyzer import (
    CodeAnalyzer,
    CodeMetrics,
)


class TestCodeMetricsCalculation:
    """Test code metrics calculation."""

    def test_simple_function_metrics(self):
        """Test metrics for a simple function."""
        analyzer = CodeAnalyzer()
        code = """
def simple_function(a, b):
    result = a + b
    return result
"""
        metrics_list = analyzer.calculate_metrics(code, "python")
        assert len(metrics_list) == 1
        metrics = metrics_list[0]

        assert metrics.lines_of_code == 3  # Excludes empty lines and comments
        assert metrics.parameter_count == 2
        assert metrics.return_count == 1

    def test_complex_function_metrics(self):
        """Test metrics for a complex function."""
        analyzer = CodeAnalyzer()
        code = """
def complex_function(a, b, c, d, e, f, g):
    if a > 0:
        if b > 0:
            if c > 0:
                if d > 0:
                    if e > 0:
                        return f + g
    elif a < 0:
        for i in range(b):
            while c > 0:
                try:
                    result = d / e
                except ZeroDivisionError:
                    result = 0
                c -= 1
    return result
"""
        metrics_list = analyzer.calculate_metrics(code, "python")
        assert len(metrics_list) == 1
        metrics = metrics_list[0]

        assert metrics.parameter_count == 7  # 7 parameters
        assert metrics.cyclomatic_complexity > 5  # Multiple decision points
        assert metrics.nesting_depth >= 4  # Deep nesting

    def test_javascript_function_metrics(self):
        """Test metrics for JavaScript function."""
        analyzer = CodeAnalyzer()
        code = """
function calculateTotal(items, discount, tax) {
    let total = 0;
    for (const item of items) {
        total += item.price;
    }
    if (discount) {
        total -= discount;
    }
    if (tax) {
        total += total * tax;
    }
    return total;
}
"""
        metrics_list = analyzer.calculate_metrics(code, "javascript")
        assert len(metrics_list) == 1
        metrics = metrics_list[0]

        assert metrics.parameter_count == 3
        assert metrics.cyclomatic_complexity >= 3  # for + 2 ifs
        assert metrics.lines_of_code > 5

    def test_empty_code(self):
        """Test metrics for empty code."""
        analyzer = CodeAnalyzer()
        code = ""
        metrics_list = analyzer.calculate_metrics(code, "python")
        assert len(metrics_list) == 1
        metrics = metrics_list[0]

        assert metrics.lines_of_code == 0
        assert metrics.parameter_count == 0
        assert metrics.cyclomatic_complexity == 1  # Base complexity


class TestLongParameterListDetection:
    """Test detection of long parameter lists."""

    def test_detects_long_parameter_list(self):
        """Test detection of function with too many parameters."""
        analyzer = CodeAnalyzer()
        metrics = CodeMetrics(
            name="test_function",
            lines_of_code=10,
            cyclomatic_complexity=5,
            parameter_count=8,  # More than MAX_PARAMETERS (5)
            nesting_depth=2,
            return_count=1,
        )

        suggestion = analyzer.detect_long_parameter_list(metrics, "/test/file.py", 10)

        assert suggestion is not None
        assert suggestion.issue_type == "Long Parameter List"
        assert suggestion.severity in ["medium", "high"]
        assert "8 parameters" in suggestion.description
        assert "configuration object" in suggestion.suggested_fix.lower()

    def test_accepts_reasonable_parameter_count(self):
        """Test that functions with reasonable parameter counts pass."""
        analyzer = CodeAnalyzer()
        metrics = CodeMetrics(
            name="test_function",
            lines_of_code=10,
            cyclomatic_complexity=3,
            parameter_count=3,  # Within limit
            nesting_depth=2,
            return_count=1,
        )

        suggestion = analyzer.detect_long_parameter_list(metrics, "/test/file.py", 10)

        assert suggestion is None

    def test_severity_scales_with_parameter_count(self):
        """Test that severity increases with parameter count."""
        analyzer = CodeAnalyzer()

        # 6 parameters - medium severity
        metrics_medium = CodeMetrics(
            name="test_function",
            lines_of_code=10,
            cyclomatic_complexity=3,
            parameter_count=6,
            nesting_depth=2,
            return_count=1,
        )
        suggestion_medium = analyzer.detect_long_parameter_list(
            metrics_medium, "/test/file.py", 10
        )

        # 10 parameters - high severity
        metrics_high = CodeMetrics(
            name="test_function",
            lines_of_code=10,
            cyclomatic_complexity=3,
            parameter_count=10,
            nesting_depth=2,
            return_count=1,
        )
        suggestion_high = analyzer.detect_long_parameter_list(
            metrics_high, "/test/file.py", 10
        )

        assert suggestion_medium.severity == "medium"
        assert suggestion_high.severity == "high"


class TestLargeFunctionDetection:
    """Test detection of large functions."""

    def test_detects_large_function(self):
        """Test detection of overly long function."""
        analyzer = CodeAnalyzer()
        metrics = CodeMetrics(
            name="big_function",
            lines_of_code=80,  # More than MAX_LINES_OF_CODE (50)
            cyclomatic_complexity=5,
            parameter_count=3,
            nesting_depth=2,
            return_count=1,
        )

        suggestion = analyzer.detect_large_function(metrics, "/test/file.py", 10)

        assert suggestion is not None
        assert suggestion.issue_type == "Large Function"
        assert "80 lines" in suggestion.description
        assert "Extract Method" in suggestion.suggested_fix

    def test_accepts_reasonable_function_size(self):
        """Test that reasonably-sized functions pass."""
        analyzer = CodeAnalyzer()
        metrics = CodeMetrics(
            name="small_function",
            lines_of_code=30,  # Within limit
            cyclomatic_complexity=3,
            parameter_count=2,
            nesting_depth=1,
            return_count=1,
        )

        suggestion = analyzer.detect_large_function(metrics, "/test/file.py", 10)

        assert suggestion is None


class TestDeepNestingDetection:
    """Test detection of deep nesting."""

    def test_detects_deep_nesting(self):
        """Test detection of excessive nesting."""
        analyzer = CodeAnalyzer()
        metrics = CodeMetrics(
            name="nested_function",
            lines_of_code=20,
            cyclomatic_complexity=8,
            parameter_count=2,
            nesting_depth=6,  # More than MAX_NESTING_DEPTH (4)
            return_count=1,
        )

        suggestion = analyzer.detect_deep_nesting(metrics, "/test/file.py", 10)

        assert suggestion is not None
        assert suggestion.issue_type == "Deep Nesting"
        assert "nesting depth of 6" in suggestion.description.lower()
        assert (
            "early return" in suggestion.suggested_fix.lower()
            or "guard clause" in suggestion.suggested_fix.lower()
        )

    def test_accepts_reasonable_nesting(self):
        """Test that reasonable nesting passes."""
        analyzer = CodeAnalyzer()
        metrics = CodeMetrics(
            name="flat_function",
            lines_of_code=20,
            cyclomatic_complexity=3,
            parameter_count=2,
            nesting_depth=2,  # Within limit
            return_count=1,
        )

        suggestion = analyzer.detect_deep_nesting(metrics, "/test/file.py", 10)

        assert suggestion is None


class TestHighComplexityDetection:
    """Test detection of high cyclomatic complexity."""

    def test_detects_high_complexity(self):
        """Test detection of high complexity."""
        analyzer = CodeAnalyzer()
        metrics = CodeMetrics(
            name="complex_function",
            lines_of_code=30,
            cyclomatic_complexity=15,  # More than HIGH_COMPLEXITY_THRESHOLD (10)
            parameter_count=3,
            nesting_depth=3,
            return_count=5,
        )

        suggestion = analyzer.detect_high_complexity(metrics, "/test/file.py", 10)

        assert suggestion is not None
        assert suggestion.issue_type == "High Complexity"
        assert "complexity of 15" in suggestion.description.lower()
        assert "simplifying" in suggestion.suggested_fix.lower()

    def test_accepts_reasonable_complexity(self):
        """Test that reasonable complexity passes."""
        analyzer = CodeAnalyzer()
        metrics = CodeMetrics(
            name="simple_function",
            lines_of_code=20,
            cyclomatic_complexity=5,  # Within limit
            parameter_count=2,
            nesting_depth=2,
            return_count=1,
        )

        suggestion = analyzer.detect_high_complexity(metrics, "/test/file.py", 10)

        assert suggestion is None


class TestAnalyzeCode:
    """Test full code analysis."""

    def test_analyzes_good_code(self):
        """Test that clean code produces no suggestions."""
        analyzer = CodeAnalyzer()
        code = """
def clean_function(a, b):
    result = a + b
    return result
"""
        suggestions = analyzer.analyze_code(
            code=code,
            language="python",
            file_path="/test/clean.py",
            line_number=1,
        )

        assert len(suggestions) == 0

    def test_analyzes_problematic_code(self):
        """Test that problematic code produces suggestions."""
        analyzer = CodeAnalyzer()
        code = """
def problematic_function(a, b, c, d, e, f, g, h):
    if a > 0:
        if b > 0:
            if c > 0:
                if d > 0:
                    if e > 0:
                        result = f + g + h
                        # ... many more lines ...
""" + "\n".join([f"        line_{i} = {i}" for i in range(60)])  # Add 60 lines

        suggestions = analyzer.analyze_code(
            code=code,
            language="python",
            file_path="/test/bad.py",
            line_number=1,
        )

        # Should detect multiple issues: long parameter list, large function,
        # deep nesting, high complexity
        assert len(suggestions) > 0

        # Check that at least one of each type is detected
        issue_types = {s.issue_type for s in suggestions}
        assert "Long Parameter List" in issue_types
        assert "Large Function" in issue_types or "Deep Nesting" in issue_types

    def test_includes_metrics_in_suggestions(self):
        """Test that suggestions include metrics."""
        analyzer = CodeAnalyzer()
        code = """
def function_with_many_params(a, b, c, d, e, f, g):
    return a + b + c + d + e + f + g
"""
        suggestions = analyzer.analyze_code(
            code=code,
            language="python",
            file_path="/test/metrics.py",
            line_number=1,
        )

        assert len(suggestions) > 0
        suggestion = suggestions[0]
        assert suggestion.metrics is not None
        assert suggestion.metrics.parameter_count == 7
