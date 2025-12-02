"""Tests for result summarizer."""

from src.memory.result_summarizer import ResultSummarizer, SearchFacets


def test_build_facets_empty():
    """Test facet building with empty results."""
    facets = ResultSummarizer.build_facets([])

    assert facets.languages == {}
    assert facets.unit_types == {}
    assert facets.files == {}
    assert facets.directories == {}


def test_build_facets_single_language():
    """Test facet building with single language."""
    results = [
        {
            "language": "python",
            "unit_type": "function",
            "file_path": "/app/auth.py",
        },
        {
            "language": "python",
            "unit_type": "function",
            "file_path": "/app/user.py",
        },
    ]

    facets = ResultSummarizer.build_facets(results)

    assert facets.languages == {"python": 2}
    assert facets.unit_types == {"function": 2}
    assert len(facets.files) == 2


def test_build_facets_multi_language():
    """Test facet building with multiple languages."""
    results = [
        {"language": "python", "unit_type": "function", "file_path": "/app/auth.py"},
        {"language": "python", "unit_type": "class", "file_path": "/app/user.py"},
        {
            "language": "typescript",
            "unit_type": "function",
            "file_path": "/client/api.ts",
        },
        {
            "language": "typescript",
            "unit_type": "interface",
            "file_path": "/client/types.ts",
        },
    ]

    facets = ResultSummarizer.build_facets(results)

    assert facets.languages == {"python": 2, "typescript": 2}
    assert "function" in facets.unit_types
    assert "class" in facets.unit_types


def test_build_facets_directories():
    """Test directory facet extraction."""
    results = [
        {
            "language": "python",
            "unit_type": "function",
            "file_path": "/app/auth/jwt.py",
        },
        {
            "language": "python",
            "unit_type": "function",
            "file_path": "/app/auth/session.py",
        },
        {
            "language": "python",
            "unit_type": "function",
            "file_path": "/app/user/profile.py",
        },
    ]

    facets = ResultSummarizer.build_facets(results)

    assert "/app/auth" in facets.directories
    assert facets.directories["/app/auth"] == 2
    assert facets.directories["/app/user"] == 1


def test_summarize_empty():
    """Test summary generation for empty results."""
    facets = SearchFacets(
        languages={},
        unit_types={},
        files={},
        directories={},
        projects={},
    )

    summary = ResultSummarizer.summarize([], facets, "test query")

    assert "No results found" in summary


def test_summarize_single_language():
    """Test summary with single language."""
    results = [
        {"language": "python", "unit_type": "function", "file_path": "/app/auth.py"},
        {"language": "python", "unit_type": "function", "file_path": "/app/user.py"},
        {"language": "python", "unit_type": "function", "file_path": "/app/api.py"},
    ]

    facets = ResultSummarizer.build_facets(results)
    summary = ResultSummarizer.summarize(results, facets, "authentication")

    assert "Found 3" in summary
    assert "functions" in summary
    assert "in Python" in summary


def test_summarize_multi_language():
    """Test summary with multiple languages."""
    results = [
        {"language": "python", "unit_type": "function", "file_path": "/app/auth.py"},
        {
            "language": "typescript",
            "unit_type": "function",
            "file_path": "/client/auth.ts",
        },
    ]

    facets = ResultSummarizer.build_facets(results)
    summary = ResultSummarizer.summarize(results, facets, "authentication")

    assert "Found 2" in summary
    assert "across" in summary.lower()
    assert "python" in summary.lower() or "typescript" in summary.lower()


def test_summarize_mixed_unit_types():
    """Test summary with mixed unit types."""
    results = [
        {"language": "python", "unit_type": "function", "file_path": "/app/auth.py"},
        {"language": "python", "unit_type": "function", "file_path": "/app/user.py"},
        {"language": "python", "unit_type": "class", "file_path": "/app/models.py"},
    ]

    facets = ResultSummarizer.build_facets(results)
    summary = ResultSummarizer.summarize(results, facets, "code")

    assert "Found 3" in summary
    assert "function" in summary.lower() or "class" in summary.lower()


def test_summarize_many_languages():
    """Test summary with >2 languages."""
    results = [
        {"language": "python", "unit_type": "function", "file_path": "/app/auth.py"},
        {
            "language": "typescript",
            "unit_type": "function",
            "file_path": "/client/auth.ts",
        },
        {"language": "java", "unit_type": "method", "file_path": "/service/Auth.java"},
        {"language": "go", "unit_type": "function", "file_path": "/api/auth.go"},
    ]

    facets = ResultSummarizer.build_facets(results)
    summary = ResultSummarizer.summarize(results, facets, "authentication")

    assert "Found 4" in summary
    assert "other language" in summary.lower()


def test_format_unit_types_single():
    """Test unit type formatting with single type."""
    types = {"function": 5}
    formatted = ResultSummarizer._format_unit_types(types)

    assert formatted == "functions"


def test_format_unit_types_single_one_item():
    """Test unit type formatting with single item."""
    types = {"class": 1}
    formatted = ResultSummarizer._format_unit_types(types)

    assert formatted == "class"


def test_format_unit_types_mixed():
    """Test unit type formatting with mixed types."""
    types = {"function": 3, "class": 2}
    formatted = ResultSummarizer._format_unit_types(types)

    assert "3 functions" in formatted
    assert "2 classes" in formatted
    assert "and" in formatted


def test_build_facets_ignore_unknown():
    """Test that unknown values are ignored."""
    results = [
        {
            "language": "(unknown language)",
            "unit_type": "(unknown type)",
            "file_path": "(no path)",
        },
        {"language": "python", "unit_type": "function", "file_path": "/app/test.py"},
    ]

    facets = ResultSummarizer.build_facets(results)

    # Unknown values should be filtered out
    assert "(unknown language)" not in facets.languages
    assert "(unknown type)" not in facets.unit_types
    assert "(no path)" not in facets.files
    assert facets.languages == {"python": 1}


def test_build_facets_top_files_limit():
    """Test that files facet is limited to top 5."""
    results = [
        {"language": "python", "unit_type": "function", "file_path": f"/app/file{i}.py"}
        for i in range(10)
    ]

    facets = ResultSummarizer.build_facets(results)

    # Should only return top 5 files
    assert len(facets.files) == 5
