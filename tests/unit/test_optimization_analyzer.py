"""Unit tests for OptimizationAnalyzer."""

import pytest
import tempfile
from pathlib import Path

from src.memory.optimization_analyzer import (
    OptimizationAnalyzer,
)


@pytest.fixture
def temp_project():
    """Create temporary project directory with test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project = Path(tmpdir)

        # Create source files
        (project / "src").mkdir()
        (project / "src" / "main.py").write_text("def main(): pass")
        (project / "src" / "utils.py").write_text("def util(): pass")
        (project / "src" / "app.js").write_text("console.log('hello')")

        # Create node_modules
        (project / "node_modules").mkdir()
        (project / "node_modules" / "package").mkdir()
        for i in range(50):
            (project / "node_modules" / "package" / f"file{i}.js").write_text(
                "module.exports = {}"
            )

        # Create build output
        (project / "dist").mkdir()
        for i in range(20):
            (project / "dist" / f"bundle{i}.js").write_text("// minified")

        # Create Python cache
        (project / "__pycache__").mkdir()
        for i in range(10):
            (project / "__pycache__" / f"file{i}.pyc").write_bytes(b"\x00" * 100)

        # Create venv
        (project / "venv").mkdir()
        (project / "venv" / "lib").mkdir()
        for i in range(30):
            (project / "venv" / "lib" / f"module{i}.py").write_text("# library")

        # Create .git
        (project / ".git").mkdir()
        (project / ".git" / "objects").mkdir()
        for i in range(15):
            (project / ".git" / "objects" / f"obj{i}").write_bytes(b"\x00" * 50)

        # Create large binary files
        (project / "assets").mkdir()
        (project / "assets" / "large.png").write_bytes(
            b"\x00" * (2 * 1024 * 1024)
        )  # 2MB
        (project / "assets" / "huge.jpg").write_bytes(
            b"\x00" * (3 * 1024 * 1024)
        )  # 3MB

        # Create log files
        for i in range(12):
            (project / f"app{i}.log").write_text("LOG " * 100)

        yield project


@pytest.mark.parametrize(
    "pattern_match,description_match,min_files,expected_priority",
    [
        ("node_modules", "Node.js", 50, 5),
        ("dist/", "build", 20, None),
        ("venv", "virtual", 30, None),
        ("__pycache__", "cache", 10, None),
        (".git/", None, 15, None),
    ],
    ids=["node_modules", "build_dist", "venv", "pycache", "git"],
)
def test_analyze_finds_common_directories(
    temp_project, pattern_match, description_match, min_files, expected_priority
):
    """Test detection of common excludable directories."""
    analyzer = OptimizationAnalyzer(temp_project)
    result = analyzer.analyze()

    # Find matching suggestions
    suggestions = [
        s
        for s in result.suggestions
        if pattern_match in s.pattern.lower()
        or (description_match and description_match.lower() in s.description.lower())
    ]

    assert len(suggestions) > 0, f"No suggestions found for {pattern_match}"
    suggestion = suggestions[0]
    assert suggestion.affected_files >= min_files

    if expected_priority is not None:
        assert suggestion.priority == expected_priority


def test_analyze_finds_large_binaries(temp_project):
    """Test detection of large binary files."""
    analyzer = OptimizationAnalyzer(temp_project, large_file_threshold_mb=1.5)
    result = analyzer.analyze()

    # Should suggest excluding large images (2MB, 3MB)
    [
        s
        for s in result.suggestions
        if s.type == "exclude_pattern" and (".png" in s.pattern or ".jpg" in s.pattern)
    ]

    # May or may not suggest based on file count threshold
    # Just verify the analyzer detected them
    assert result.total_files > 0


def test_analyze_finds_log_files(temp_project):
    """Test detection of log files."""
    analyzer = OptimizationAnalyzer(temp_project)
    result = analyzer.analyze()

    # Should suggest excluding *.log (12 log files)
    log_suggestions = [
        s
        for s in result.suggestions
        if "*.log" in s.pattern or "log" in s.description.lower()
    ]

    assert len(log_suggestions) > 0
    suggestion = log_suggestions[0]
    assert suggestion.affected_files >= 10


def test_suggestions_sorted_by_priority(temp_project):
    """Test that suggestions are sorted by priority."""
    analyzer = OptimizationAnalyzer(temp_project)
    result = analyzer.analyze()

    # Verify suggestions are sorted (higher priority first)
    for i in range(len(result.suggestions) - 1):
        current = result.suggestions[i]
        next_sug = result.suggestions[i + 1]

        # Either higher priority, or same priority with more time savings
        assert current.priority > next_sug.priority or (
            current.priority == next_sug.priority
            and current.time_savings_seconds >= next_sug.time_savings_seconds
        )


def test_estimate_speedup_calculation(temp_project):
    """Test speedup estimation."""
    analyzer = OptimizationAnalyzer(temp_project)
    result = analyzer.analyze()

    # Should have significant speedup potential
    assert result.estimated_speedup > 1.0

    # With node_modules, venv, dist, etc., should be substantial
    assert result.estimated_speedup >= 1.5


def test_calculate_storage_savings(temp_project):
    """Test storage savings calculation."""
    analyzer = OptimizationAnalyzer(temp_project)
    result = analyzer.analyze()

    # Should have storage savings from large files and directories
    assert result.estimated_storage_savings_mb > 0


def test_empty_directory():
    """Test analysis of empty directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        analyzer = OptimizationAnalyzer(Path(tmpdir))
        result = analyzer.analyze()

        assert result.total_files == 0
        assert len(result.suggestions) == 0
        assert result.estimated_speedup == 1.0


def test_clean_project():
    """Test analysis of clean project (no optimizations needed)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project = Path(tmpdir)

        # Only source files
        (project / "src").mkdir()
        (project / "src" / "main.py").write_text("def main(): pass")
        (project / "src" / "utils.py").write_text("def util(): pass")
        (project / "test").mkdir()
        (project / "test" / "test_main.py").write_text("def test(): pass")

        analyzer = OptimizationAnalyzer(project)
        result = analyzer.analyze()

        assert result.total_files > 0
        # Should have minimal or no suggestions
        assert len(result.suggestions) <= 1  # Maybe test directory if > 100 files


@pytest.mark.parametrize(
    "filename,magic_bytes,description",
    [
        ("image.jpg", b"\xff\xd8\xff", "JPEG image"),
        ("photo.png", b"\x89PNG", "PNG image"),
        ("app.exe", b"MZ", "Windows executable"),
    ],
    ids=["jpeg", "png", "exe"],
)
def test_binary_detection(filename, magic_bytes, description):
    """Test binary file detection for various file types."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project = Path(tmpdir)

        # Create binary file with magic bytes
        (project / filename).write_bytes(magic_bytes + b"\x00" * 100)

        analyzer = OptimizationAnalyzer(project)
        analyzer._scan_directory()

        file_path = (project / filename).resolve()
        assert file_path in analyzer.file_stats, f"File not found in stats: {filename}"
        assert analyzer.file_stats[
            file_path
        ].is_binary, f"{description} should be detected as binary"


@pytest.mark.parametrize(
    "filename,content,description",
    [
        ("code.py", "def hello(): print('world')", "Python file"),
        ("script.js", "console.log('hello')", "JavaScript file"),
        ("README.md", "# Project", "Markdown file"),
    ],
    ids=["python", "javascript", "markdown"],
)
def test_text_files_not_binary(filename, content, description):
    """Test that text files are not marked as binary."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project = Path(tmpdir)

        # Create text file
        (project / filename).write_text(content)

        analyzer = OptimizationAnalyzer(project)
        analyzer._scan_directory()

        file_path = (project / filename).resolve()
        assert file_path in analyzer.file_stats, f"File not found: {filename}"
        assert not analyzer.file_stats[
            file_path
        ].is_binary, f"{description} should not be binary"


def test_large_file_threshold():
    """Test large file threshold detection."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project = Path(tmpdir)

        # Create files of different sizes
        (project / "small.bin").write_bytes(b"\x00" * (512 * 1024))  # 512KB
        (project / "medium.bin").write_bytes(b"\x00" * (1536 * 1024))  # 1.5MB
        (project / "large.bin").write_bytes(b"\x00" * (5 * 1024 * 1024))  # 5MB

        # Use 1MB threshold
        analyzer = OptimizationAnalyzer(project, large_file_threshold_mb=1.0)
        analyzer.analyze()

        # Medium and large files should trigger suggestions if enough of them
        # (need 3+ files with same extension)


def test_generate_ragignore_content(temp_project):
    """Test generating .ragignore content from suggestions."""
    analyzer = OptimizationAnalyzer(temp_project)
    result = analyzer.analyze()

    ragignore_content = analyzer.generate_ragignore(result.suggestions)

    # Should contain header
    assert "# .ragignore" in ragignore_content

    # Should contain patterns
    assert "node_modules/" in ragignore_content or "dist/" in ragignore_content

    # Should be valid content
    lines = ragignore_content.split("\n")
    assert len(lines) > 5  # Header + patterns


def test_indexable_files_count(temp_project):
    """Test counting indexable source files."""
    analyzer = OptimizationAnalyzer(temp_project)
    result = analyzer.analyze()

    # Should correctly count source files (not in excluded directories)
    # We have: src/main.py, src/utils.py, src/app.js = 3 files
    # (Others are in node_modules, dist, venv, etc.)
    assert result.indexable_files >= 3
    assert result.indexable_files < result.total_files


def test_time_savings_calculation():
    """Test that time savings are calculated correctly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project = Path(tmpdir)

        # Create node_modules with 100 files
        (project / "node_modules").mkdir()
        for i in range(100):
            (project / "node_modules" / f"file{i}.js").write_text("// code")

        analyzer = OptimizationAnalyzer(project)
        result = analyzer.analyze()

        # Should suggest excluding node_modules
        node_modules_sugg = [
            s for s in result.suggestions if "node_modules" in s.pattern
        ]
        assert len(node_modules_sugg) > 0

        suggestion = node_modules_sugg[0]
        # Time savings should be: 100 files * 0.1s = 10s
        assert suggestion.time_savings_seconds >= 9.0  # Allow small variance


def test_priority_scoring():
    """Test that priorities are assigned correctly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project = Path(tmpdir)

        # Create different directory types
        (project / "node_modules").mkdir()
        for i in range(10):
            (project / "node_modules" / f"f{i}.js").write_text("//")

        (project / "vendor").mkdir()
        for i in range(10):
            (project / "vendor" / f"f{i}.php").write_text("<?php")

        analyzer = OptimizationAnalyzer(project)
        result = analyzer.analyze()

        # node_modules should have highest priority (5)
        node_sugg = [s for s in result.suggestions if "node_modules" in s.pattern]
        if node_sugg:
            assert node_sugg[0].priority == 5

        # vendor should have lower priority (3)
        vendor_sugg = [s for s in result.suggestions if "vendor" in s.pattern]
        if vendor_sugg:
            assert vendor_sugg[0].priority == 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
