"""Unit tests for call extractors."""

from src.analysis.call_extractors import PythonCallExtractor, get_call_extractor


class TestPythonCallExtractor:
    """Test Python call extraction."""

    def test_extract_direct_calls(self):
        """Test extracting direct function calls."""
        code = """
def main():
    foo()
    bar()
"""
        extractor = PythonCallExtractor()
        calls = extractor.extract_calls("/test.py", code)

        assert len(calls) == 2
        callee_names = {c.callee_function for c in calls}
        assert "foo" in callee_names
        assert "bar" in callee_names

    def test_extract_method_calls(self):
        """Test extracting method calls."""
        code = """
def process():
    obj.method()
    self.helper()
"""
        extractor = PythonCallExtractor()
        calls = extractor.extract_calls("/test.py", code)

        assert len(calls) == 2
        # Should extract method names
        callee_names = [c.callee_function for c in calls]
        assert any("method" in name for name in callee_names)
        assert any("helper" in name for name in callee_names)

    def test_extract_constructor_calls(self):
        """Test extracting constructor calls."""
        code = """
def create():
    obj = MyClass()
    return AnotherClass(arg)
"""
        extractor = PythonCallExtractor()
        calls = extractor.extract_calls("/test.py", code)

        assert len(calls) == 2
        # Constructor calls should be detected
        call_types = {c.call_type for c in calls}
        assert "constructor" in call_types

    def test_extract_calls_with_line_numbers(self):
        """Test that line numbers are captured."""
        code = """
def main():
    foo()  # Line 3
    bar()  # Line 4
"""
        extractor = PythonCallExtractor()
        calls = extractor.extract_calls("/test.py", code)

        assert len(calls) == 2
        lines = {c.caller_line for c in calls}
        assert 3 in lines
        assert 4 in lines

    def test_extract_implementations_single(self):
        """Test extracting single inheritance."""
        code = """
class ConcreteStorage(AbstractStorage):
    def get(self):
        pass
    def set(self, value):
        pass
"""
        extractor = PythonCallExtractor()
        impls = extractor.extract_implementations("/test.py", code)

        assert len(impls) == 1
        assert impls[0].interface_name == "AbstractStorage"
        assert impls[0].implementation_name == "ConcreteStorage"
        assert "get" in impls[0].methods
        assert "set" in impls[0].methods

    def test_extract_implementations_multiple(self):
        """Test extracting multiple inheritance."""
        code = """
class MultiImpl(Interface1, Interface2):
    def method1(self):
        pass
    def method2(self):
        pass
"""
        extractor = PythonCallExtractor()
        impls = extractor.extract_implementations("/test.py", code)

        assert len(impls) == 2
        interface_names = {impl.interface_name for impl in impls}
        assert "Interface1" in interface_names
        assert "Interface2" in interface_names

    def test_extract_implementations_with_qualified_base(self):
        """Test extracting implementations with qualified base names."""
        code = """
import abc

class MyClass(abc.ABC):
    def method(self):
        pass
"""
        extractor = PythonCallExtractor()
        impls = extractor.extract_implementations("/test.py", code)

        assert len(impls) == 1
        # Should extract just "ABC" from "abc.ABC"
        assert impls[0].interface_name == "ABC"

    def test_extract_calls_handles_syntax_error(self):
        """Test that syntax errors are handled gracefully."""
        code = """
def broken(
    # Unclosed parenthesis
"""
        extractor = PythonCallExtractor()
        calls = extractor.extract_calls("/test.py", code)

        # Should return empty list, not raise exception
        assert len(calls) == 0

    def test_extract_implementations_handles_syntax_error(self):
        """Test that syntax errors in implementations are handled."""
        code = """
class Broken(Base
    # Unclosed parenthesis
"""
        extractor = PythonCallExtractor()
        impls = extractor.extract_implementations("/test.py", code)

        # Should return empty list, not raise exception
        assert len(impls) == 0

    def test_extract_calls_with_class_context(self):
        """Test extracting calls within class methods."""
        code = """
class MyClass:
    def method(self):
        self.helper()
        external_func()
"""
        extractor = PythonCallExtractor()
        calls = extractor.extract_calls("/test.py", code)

        assert len(calls) == 2
        # Should track that calls are from MyClass.method
        assert all(c.caller_function == "MyClass.method" for c in calls)

    def test_extract_nested_calls(self):
        """Test extracting nested function calls."""
        code = """
def outer():
    result = foo(bar(baz()))
"""
        extractor = PythonCallExtractor()
        calls = extractor.extract_calls("/test.py", code)

        # Should extract all three calls
        assert len(calls) >= 3
        callee_names = {c.callee_function for c in calls}
        assert "foo" in callee_names
        assert "bar" in callee_names
        assert "baz" in callee_names


class TestGetCallExtractor:
    """Test call extractor factory function."""

    def test_get_python_extractor(self):
        """Test getting Python extractor."""
        extractor = get_call_extractor("python")

        assert extractor is not None
        assert isinstance(extractor, PythonCallExtractor)

    def test_get_javascript_extractor(self):
        """Test getting JavaScript extractor (placeholder)."""
        extractor = get_call_extractor("javascript")

        # Should return an extractor even if not fully implemented
        assert extractor is not None

    def test_get_typescript_extractor(self):
        """Test getting TypeScript extractor."""
        extractor = get_call_extractor("typescript")

        # Should return same as JavaScript
        assert extractor is not None

    def test_get_unsupported_extractor(self):
        """Test getting extractor for unsupported language."""
        extractor = get_call_extractor("cobol")

        # Should return None for unsupported languages
        assert extractor is None

    def test_get_extractor_case_insensitive(self):
        """Test that language matching is case-insensitive."""
        extractor1 = get_call_extractor("Python")
        extractor2 = get_call_extractor("PYTHON")

        assert extractor1 is not None
        assert extractor2 is not None
