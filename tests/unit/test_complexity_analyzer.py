"""
Unit tests for ComplexityAnalyzer (FEAT-049).

Tests complexity metrics calculation including:
- Cyclomatic complexity
- Line count
- Nesting depth
- Parameter count
- Documentation detection
- Overall complexity scoring
"""

import pytest
from src.analysis.complexity_analyzer import ComplexityAnalyzer


@pytest.fixture
def analyzer():
    """Create a ComplexityAnalyzer instance."""
    return ComplexityAnalyzer()


class TestCyclomaticComplexity:
    """Tests for cyclomatic complexity calculation."""

    def test_simple_function(self, analyzer):
        """Simple function with no branching has complexity 1."""
        code = """
def simple_function():
    return 42
"""
        complexity = analyzer._calculate_cyclomatic_complexity(code, "python")
        assert complexity == 1

    def test_single_if(self, analyzer):
        """Single if statement increases complexity by 1."""
        code = """
def func_with_if(x):
    if x > 0:
        return x
    return 0
"""
        complexity = analyzer._calculate_cyclomatic_complexity(code, "python")
        assert complexity == 2  # 1 base + 1 if

    def test_if_elif_else(self, analyzer):
        """If-elif-else chain increases complexity by number of conditions."""
        code = """
def func_with_elif(x):
    if x > 0:
        return "positive"
    elif x < 0:
        return "negative"
    else:
        return "zero"
"""
        complexity = analyzer._calculate_cyclomatic_complexity(code, "python")
        assert complexity == 3  # 1 base + 1 if + 1 elif

    def test_for_loop(self, analyzer):
        """For loop increases complexity by 1."""
        code = """
def func_with_loop(items):
    result = []
    for item in items:
        result.append(item * 2)
    return result
"""
        complexity = analyzer._calculate_cyclomatic_complexity(code, "python")
        assert complexity == 2  # 1 base + 1 for

    def test_while_loop(self, analyzer):
        """While loop increases complexity by 1."""
        code = """
def func_with_while(n):
    i = 0
    while i < n:
        i += 1
    return i
"""
        complexity = analyzer._calculate_cyclomatic_complexity(code, "python")
        assert complexity == 2  # 1 base + 1 while

    def test_logical_operators(self, analyzer):
        """Logical operators (and/or) increase complexity."""
        code = """
def func_with_logic(x, y):
    if x > 0 and y > 0:
        return True
    if x < 0 or y < 0:
        return False
    return None
"""
        complexity = analyzer._calculate_cyclomatic_complexity(code, "python")
        assert complexity >= 4  # 1 base + 1 if + 1 and + 1 if + 1 or

    def test_try_except(self, analyzer):
        """Try-except blocks increase complexity."""
        code = """
def func_with_exception():
    try:
        risky_operation()
    except ValueError:
        handle_error()
    except KeyError:
        handle_key_error()
"""
        complexity = analyzer._calculate_cyclomatic_complexity(code, "python")
        assert complexity >= 3  # 1 base + 2 except

    def test_complex_function(self, analyzer):
        """Complex function with multiple decision points."""
        code = """
def complex_function(x, y, z):
    if x > 0:
        for i in range(10):
            if y > i:
                while z < 100:
                    z += 1
                    if z % 2 == 0:
                        break
    elif x < 0:
        try:
            process()
        except Exception:
            handle()
    return z
"""
        complexity = analyzer._calculate_cyclomatic_complexity(code, "python")
        assert complexity >= 7  # Many decision points


class TestLineCount:
    """Tests for line counting."""

    def test_empty_content(self, analyzer):
        """Empty content has 0 lines."""
        assert analyzer._count_lines("") == 0

    def test_single_line(self, analyzer):
        """Single line of code."""
        code = "def simple(): pass"
        assert analyzer._count_lines(code) == 1

    def test_ignore_empty_lines(self, analyzer):
        """Empty lines are not counted."""
        code = """
def func():

    return 42

"""
        count = analyzer._count_lines(code)
        assert count == 2  # Only 'def func():' and 'return 42'

    def test_ignore_comments(self, analyzer):
        """Comment lines are filtered out."""
        code = """
# This is a comment
def func():
    # Another comment
    return 42  # Inline comment (line still counted)
"""
        count = analyzer._count_lines(code)
        assert count == 2  # 'def func():' and 'return 42'

    def test_multiline_function(self, analyzer):
        """Count lines in multiline function."""
        code = """
def multiline(a, b, c):
    x = a + b
    y = b + c
    z = a + c
    return x + y + z
"""
        count = analyzer._count_lines(code)
        assert count == 5


class TestNestingDepth:
    """Tests for nesting depth calculation."""

    def test_no_nesting(self, analyzer):
        """No nesting = depth 0."""
        code = """
def simple():
    x = 1
    return x
"""
        depth = analyzer._calculate_nesting_depth(code, "python")
        assert depth >= 0

    def test_single_nesting(self, analyzer):
        """Single level of nesting."""
        code = """
def single_nest():
    if True:
        return 1
"""
        depth = analyzer._calculate_nesting_depth(code, "python")
        assert depth >= 1

    def test_double_nesting(self, analyzer):
        """Two levels of nesting."""
        code = """
def double_nest():
    if True:
        for i in range(10):
            print(i)
"""
        depth = analyzer._calculate_nesting_depth(code, "python")
        assert depth >= 2

    def test_deep_nesting(self, analyzer):
        """Deep nesting (4+ levels)."""
        code = """
def deep_nest():
    if True:
        for i in range(10):
            while i < 5:
                if i % 2 == 0:
                    print(i)
"""
        depth = analyzer._calculate_nesting_depth(code, "python")
        assert depth >= 3


class TestParameterCount:
    """Tests for parameter counting."""

    def test_no_parameters(self, analyzer):
        """Function with no parameters."""
        assert analyzer._count_parameters("def func():", "python") == 0

    def test_single_parameter(self, analyzer):
        """Function with one parameter."""
        assert analyzer._count_parameters("def func(x):", "python") == 1

    def test_multiple_parameters(self, analyzer):
        """Function with multiple parameters."""
        assert analyzer._count_parameters("def func(a, b, c):", "python") == 3

    def test_ignore_self(self, analyzer):
        """Ignore 'self' parameter in methods."""
        assert analyzer._count_parameters("def method(self, x, y):", "python") == 2

    def test_ignore_cls(self, analyzer):
        """Ignore 'cls' parameter in class methods."""
        assert analyzer._count_parameters("def classmethod(cls, x):", "python") == 1

    def test_typed_parameters(self, analyzer):
        """Handle typed parameters (Python 3.5+)."""
        sig = "def func(x: int, y: str, z: List[int]):"
        assert analyzer._count_parameters(sig, "python") == 3

    def test_default_parameters(self, analyzer):
        """Handle parameters with defaults."""
        sig = "def func(x, y=10, z='hello'):"
        assert analyzer._count_parameters(sig, "python") == 3


class TestDocumentationDetection:
    """Tests for documentation detection."""

    def test_no_documentation(self, analyzer):
        """Code without documentation."""
        code = """
def func():
    return 42
"""
        assert analyzer._has_documentation(code, "python") is False

    def test_python_docstring(self, analyzer):
        """Python docstring detection."""
        code = '''
def func():
    """This is a docstring."""
    return 42
'''
        assert analyzer._has_documentation(code, "python") is True

    def test_python_single_quote_docstring(self, analyzer):
        """Python single-quote docstring detection."""
        code = """
def func():
    '''This is also a docstring.'''
    return 42
"""
        assert analyzer._has_documentation(code, "python") is True

    def test_javascript_jsdoc(self, analyzer):
        """JavaScript JSDoc comment detection."""
        code = """
/**
 * This function does something
 * @param {number} x
 */
function func(x) {
    return x * 2;
}
"""
        assert analyzer._has_documentation(code, "javascript") is True

    def test_minimal_doc_ignored(self, analyzer):
        """Very short documentation is ignored."""
        code = """
def func():
    '''X'''
    return 42
"""
        assert analyzer._has_documentation(code, "python") is False


class TestComplexityScore:
    """Tests for overall complexity scoring."""

    def test_simple_function_low_score(self, analyzer):
        """Simple function gets low complexity score."""
        code_unit = {
            "content": "def simple():\n    return 42",
            "signature": "def simple():",
            "unit_type": "function",
            "language": "python",
        }
        metrics = analyzer.analyze(code_unit)
        assert 0.3 <= metrics.complexity_score < 0.5

    def test_complex_function_high_score(self, analyzer):
        """Complex function gets high complexity score."""
        code_unit = {
            "content": """
def complex(a, b, c, d, e):
    '''Documentation'''
    if a > 0:
        for i in range(100):
            while i < 50:
                if b > i:
                    try:
                        process()
                    except:
                        handle()
                elif c > i:
                    nested()
    return d + e
""",
            "signature": "def complex(a, b, c, d, e):",
            "unit_type": "function",
            "language": "python",
        }
        metrics = analyzer.analyze(code_unit)
        assert metrics.complexity_score > 0.5
        assert metrics.cyclomatic_complexity > 5
        assert metrics.has_documentation is True

    def test_documented_function_gets_boost(self, analyzer):
        """Documented function gets slight complexity boost."""
        code_with_docs = {
            "content": '''
def func():
    """This is documented."""
    if True:
        return 1
''',
            "signature": "def func():",
            "unit_type": "function",
            "language": "python",
        }
        code_without_docs = {
            "content": """
def func():
    if True:
        return 1
""",
            "signature": "def func():",
            "unit_type": "function",
            "language": "python",
        }
        metrics_with = analyzer.analyze(code_with_docs)
        metrics_without = analyzer.analyze(code_without_docs)
        assert metrics_with.complexity_score > metrics_without.complexity_score

    def test_score_in_valid_range(self, analyzer):
        """All scores are in valid range (0.3-0.7)."""
        test_cases = [
            {"content": "def f(): pass", "signature": "def f():", "unit_type": "function", "language": "python"},
            {"content": "def f(x):\n    if x: return 1\n    return 0", "signature": "def f(x):", "unit_type": "function", "language": "python"},
            {"content": "def f(a,b,c):\n" + "    if a:\n" * 10 + "        pass", "signature": "def f(a,b,c):", "unit_type": "function", "language": "python"},
        ]
        for code_unit in test_cases:
            metrics = analyzer.analyze(code_unit)
            assert 0.3 <= metrics.complexity_score <= 0.7, f"Score {metrics.complexity_score} out of range"


class TestLanguageSupport:
    """Tests for multiple language support."""

    def test_python_support(self, analyzer):
        """Python code analysis works."""
        code_unit = {
            "content": "def func(x):\n    if x > 0:\n        return x",
            "signature": "def func(x):",
            "unit_type": "function",
            "language": "python",
        }
        metrics = analyzer.analyze(code_unit)
        assert metrics.cyclomatic_complexity >= 2

    def test_javascript_support(self, analyzer):
        """JavaScript code analysis works."""
        code_unit = {
            "content": "function func(x) {\n    if (x > 0) {\n        return x;\n    }\n}",
            "signature": "function func(x)",
            "unit_type": "function",
            "language": "javascript",
        }
        metrics = analyzer.analyze(code_unit)
        assert metrics.cyclomatic_complexity >= 2

    def test_java_support(self, analyzer):
        """Java code analysis works."""
        code_unit = {
            "content": "public int func(int x) {\n    if (x > 0) {\n        return x;\n    }\n    return 0;\n}",
            "signature": "public int func(int x)",
            "unit_type": "function",
            "language": "java",
        }
        metrics = analyzer.analyze(code_unit)
        assert metrics.cyclomatic_complexity >= 2

    def test_go_support(self, analyzer):
        """Go code analysis works."""
        code_unit = {
            "content": "func process(x int) int {\n    if x > 0 {\n        return x\n    }\n    return 0\n}",
            "signature": "func process(x int) int",
            "unit_type": "function",
            "language": "go",
        }
        metrics = analyzer.analyze(code_unit)
        assert metrics.cyclomatic_complexity >= 2


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_code(self, analyzer):
        """Empty code is handled gracefully."""
        code_unit = {
            "content": "",
            "signature": "",
            "unit_type": "function",
            "language": "python",
        }
        metrics = analyzer.analyze(code_unit)
        assert metrics.complexity_score == 0.3  # Minimum score

    def test_malformed_signature(self, analyzer):
        """Malformed signature doesn't crash."""
        code_unit = {
            "content": "def func(): pass",
            "signature": "not a valid signature",
            "unit_type": "function",
            "language": "python",
        }
        metrics = analyzer.analyze(code_unit)
        assert metrics.parameter_count == 0

    def test_unknown_language(self, analyzer):
        """Unknown language uses default patterns."""
        code_unit = {
            "content": "def func():\n    if True:\n        return 1",
            "signature": "def func():",
            "unit_type": "function",
            "language": "unknown_lang",
        }
        metrics = analyzer.analyze(code_unit)
        # Should still analyze using default patterns
        assert metrics.complexity_score > 0
