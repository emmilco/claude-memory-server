"""Tests for refinement advisor."""

import pytest
from src.memory.refinement_advisor import RefinementAdvisor
from src.memory.result_summarizer import SearchFacets


def test_too_many_results_hint():
    """Test hint for too many results."""
    results = [{"file_path": f"/app/file{i}.py", "language": "python", "unit_type": "function"} for i in range(60)]
    facets = SearchFacets(
        languages={"python": 60},
        unit_types={"function": 60},
        files={f"/app/file{i}.py": 1 for i in range(60)},
        directories={},
        projects={},
    )

    hints = RefinementAdvisor.analyze_and_suggest(
        results, facets, "code", {"search_mode": "semantic"}
    )

    # Should suggest narrowing
    assert any("file_pattern" in h for h in hints)


def test_too_few_results_hint():
    """Test hint for too few results."""
    results = [{"file_path": "/app/auth.py", "language": "python", "unit_type": "function"}]
    facets = SearchFacets(
        languages={"python": 1},
        unit_types={"function": 1},
        files={"/app/auth.py": 1},
        directories={},
        projects={},
    )

    hints = RefinementAdvisor.analyze_and_suggest(
        results, facets, "authentication", {"search_mode": "semantic"}
    )

    # Should suggest broadening
    assert any("broaden" in h.lower() for h in hints)


def test_hybrid_search_suggestion():
    """Test suggestion to try hybrid search."""
    results = [{"file_path": "/app/auth.py", "language": "python", "unit_type": "function"}]
    facets = SearchFacets(
        languages={"python": 1},
        unit_types={"function": 1},
        files={"/app/auth.py": 1},
        directories={},
        projects={},
    )

    hints = RefinementAdvisor.analyze_and_suggest(
        results, facets, "authentication", {"search_mode": "semantic"}
    )

    # Should suggest hybrid search for better recall
    assert any("hybrid" in h for h in hints)


def test_scattered_results_hint():
    """Test hint for scattered results across many files."""
    results = [
        {"file_path": f"/app/dir{i}/file.py", "language": "python", "unit_type": "function"}
        for i in range(15)
    ]
    facets = SearchFacets(
        languages={"python": 15},
        unit_types={"function": 15},
        files={f"/app/dir{i}/file.py": 1 for i in range(15)},
        directories={f"/app/dir{i}": 1 for i in range(15)},
        projects={},
    )

    hints = RefinementAdvisor.analyze_and_suggest(
        results, facets, "utils", {"search_mode": "semantic"}
    )

    # Should suggest focusing on main directory
    assert any("scattered" in h.lower() or "focus" in h.lower() for h in hints)


def test_concentrated_directory_hint():
    """Test hint when most results are in one directory."""
    results = [
        {"file_path": "/app/auth/file1.py", "language": "python", "unit_type": "function"},
        {"file_path": "/app/auth/file2.py", "language": "python", "unit_type": "function"},
        {"file_path": "/app/auth/file3.py", "language": "python", "unit_type": "function"},
        {"file_path": "/app/auth/file4.py", "language": "python", "unit_type": "function"},
        {"file_path": "/app/user/file1.py", "language": "python", "unit_type": "function"},
        {"file_path": "/app/api/handler.py", "language": "python", "unit_type": "function"},
    ]
    facets = SearchFacets(
        languages={"python": 6},
        unit_types={"function": 6},
        files={
            "/app/auth/file1.py": 1,
            "/app/auth/file2.py": 1,
            "/app/auth/file3.py": 1,
            "/app/auth/file4.py": 1,
            "/app/user/file1.py": 1,
            "/app/api/handler.py": 1,
        },
        directories={"/app/auth": 4, "/app/user": 1, "/app/api": 1},
        projects={},
    )

    hints = RefinementAdvisor.analyze_and_suggest(
        results, facets, "auth", {"search_mode": "semantic"}
    )

    # Should suggest focusing on /app/auth
    assert any("/app/auth" in h for h in hints)


def test_mixed_unit_types_hint():
    """Test hint for mixed unit types."""
    results = [
        {"file_path": "/app/auth.py", "language": "python", "unit_type": "function"},
        {"file_path": "/app/auth.py", "language": "python", "unit_type": "function"},
        {"file_path": "/app/user.py", "language": "python", "unit_type": "class"},
    ]
    facets = SearchFacets(
        languages={"python": 3},
        unit_types={"function": 2, "class": 1},
        files={"/app/auth.py": 2, "/app/user.py": 1},
        directories={},
        projects={},
    )

    hints = RefinementAdvisor.analyze_and_suggest(
        results, facets, "code", {"search_mode": "semantic"}
    )

    # Should suggest focusing on functions
    assert any("function" in h for h in hints)


def test_short_query_hint():
    """Test hint for short query."""
    results = [{"file_path": "/app/auth.py", "language": "python", "unit_type": "function"}] * 10
    facets = SearchFacets(
        languages={"python": 10},
        unit_types={"function": 10},
        files={"/app/auth.py": 10},
        directories={},
        projects={},
    )

    hints = RefinementAdvisor.analyze_and_suggest(
        results, facets, "auth", {"search_mode": "semantic"}
    )

    # Should suggest adding more context
    assert any("context" in h.lower() or "specific" in h.lower() for h in hints)


def test_identifier_search_hint():
    """Test hint for searching specific identifiers."""
    results = [{"file_path": "/app/auth.py", "language": "python", "unit_type": "function"}] * 5
    facets = SearchFacets(
        languages={"python": 5},
        unit_types={"function": 5},
        files={"/app/auth.py": 5},
        directories={},
        projects={},
    )

    # CamelCase identifier
    hints = RefinementAdvisor.analyze_and_suggest(
        results, facets, "UserRepository", {"search_mode": "semantic"}
    )

    # Should suggest keyword search for specific names
    assert any("keyword" in h for h in hints)

    # snake_case identifier
    hints = RefinementAdvisor.analyze_and_suggest(
        results, facets, "validate_token", {"search_mode": "semantic"}
    )

    assert any("keyword" in h for h in hints)


def test_multi_language_hint():
    """Test hint for multi-language results."""
    results = [
        {"file_path": "/app/auth.py", "language": "python", "unit_type": "function"},
    ] * 30 + [
        {"file_path": "/client/auth.ts", "language": "typescript", "unit_type": "function"},
    ] * 25

    facets = SearchFacets(
        languages={"python": 30, "typescript": 25},
        unit_types={"function": 55},
        files={"/app/auth.py": 30, "/client/auth.ts": 25},
        directories={},
        projects={},
    )

    hints = RefinementAdvisor.analyze_and_suggest(
        results, facets, "auth", {"search_mode": "semantic"}
    )

    # Should suggest filtering by language
    assert any("language" in h.lower() for h in hints)


def test_max_three_hints():
    """Test that maximum 3 hints are returned."""
    # Create scenario that could generate many hints
    results = [{"file_path": f"/app/dir{i}/file.py", "language": "python", "unit_type": "function"} for i in range(60)]
    facets = SearchFacets(
        languages={"python": 40, "typescript": 20},
        unit_types={"function": 50, "class": 10},
        files={f"/app/dir{i}/file.py": 1 for i in range(60)},
        directories={f"/app/dir{i}": 1 for i in range(60)},
        projects={},
    )

    hints = RefinementAdvisor.analyze_and_suggest(
        results, facets, "x", {"search_mode": "semantic"}
    )

    # Should return max 3 hints
    assert len(hints) <= 3


def test_remove_file_pattern_hint():
    """Test hint to remove file_pattern filter."""
    results = [{"file_path": "/app/auth.py", "language": "python", "unit_type": "function"}]
    facets = SearchFacets(
        languages={"python": 1},
        unit_types={"function": 1},
        files={"/app/auth.py": 1},
        directories={},
        projects={},
    )

    hints = RefinementAdvisor.analyze_and_suggest(
        results,
        facets,
        "authentication",
        {"search_mode": "semantic", "file_pattern": "*/auth/*"},
    )

    # Should suggest removing file_pattern
    assert any("removing file_pattern" in h.lower() for h in hints)
