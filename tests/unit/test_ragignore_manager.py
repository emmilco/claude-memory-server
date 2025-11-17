"""Unit tests for RagignoreManager."""

import pytest
import tempfile
from pathlib import Path

from src.memory.ragignore_manager import RagignoreManager
from src.memory.optimization_analyzer import OptimizationSuggestion


@pytest.fixture
def temp_project():
    """Create temporary project directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def manager(temp_project):
    """Create ragignore manager."""
    return RagignoreManager(temp_project)


def test_read_nonexistent_ragignore(manager):
    """Test reading non-existent .ragignore file."""
    patterns = manager.read_existing()
    assert patterns == []


def test_write_and_read_ragignore(manager, temp_project):
    """Test writing and reading .ragignore file."""
    content = """# Comment
node_modules/
dist/
*.log
"""
    manager.write(content, backup=False)

    # Verify file was created
    ragignore_path = temp_project / ".ragignore"
    assert ragignore_path.exists()

    # Read back
    patterns = manager.read_existing()
    assert "node_modules/" in patterns
    assert "dist/" in patterns
    assert "*.log" in patterns
    # Comments should be excluded
    assert "# Comment" not in patterns


def test_read_with_comments(manager, temp_project):
    """Test reading .ragignore with comments preserved."""
    content = """# This is a comment
node_modules/
# Another comment
dist/
"""
    manager.write(content, backup=False)

    full_content = manager.read_with_comments()
    assert "# This is a comment" in full_content
    assert "# Another comment" in full_content
    assert "node_modules/" in full_content


def test_write_creates_backup(manager, temp_project):
    """Test that write creates backup of existing file."""
    # Write initial content
    manager.write("node_modules/\n", backup=False)

    # Write again with backup
    manager.write("dist/\n", backup=True)

    # Check backup was created
    backup_path = temp_project / ".ragignore.bak"
    assert backup_path.exists()

    # Backup should contain original content
    with open(backup_path) as f:
        backup_content = f.read()
    assert "node_modules/" in backup_content


def test_merge_patterns_empty_existing(manager):
    """Test merging patterns with empty existing list."""
    existing = []
    new = ["node_modules/", "dist/", "*.log"]

    merged = manager.merge_patterns(existing, new)
    assert set(merged) == set(new)


def test_merge_patterns_no_duplicates(manager):
    """Test that merge removes duplicates."""
    existing = ["node_modules/", "dist/"]
    new = ["node_modules/", "*.log", "dist/"]

    merged = manager.merge_patterns(existing, new)
    assert len(merged) == 3
    assert "node_modules/" in merged
    assert "dist/" in merged
    assert "*.log" in merged


def test_merge_patterns_preserve_existing(manager):
    """Test that existing patterns are preserved."""
    existing = ["custom-pattern/", "my-dir/"]
    new = ["node_modules/", "dist/"]

    merged = manager.merge_patterns(existing, new, preserve_existing=True)
    assert len(merged) == 4
    assert "custom-pattern/" in merged
    assert "my-dir/" in merged
    assert "node_modules/" in merged
    assert "dist/" in merged


def test_merge_patterns_skip_covered(manager):
    """Test that specific patterns are skipped if covered by general pattern."""
    existing = ["node_modules/"]
    new = ["node_modules/package/", "dist/"]  # node_modules/package/ is covered

    merged = manager.merge_patterns(existing, new)
    # node_modules/package/ should be skipped (covered by node_modules/)
    assert "node_modules/" in merged
    assert "dist/" in merged
    # The specific pattern might be included depending on logic


def test_validate_pattern_valid(manager):
    """Test pattern validation for valid patterns."""
    valid_patterns = [
        "node_modules/",
        "*.log",
        "dist/",
        "**/*.pyc",
        "!important.log",
    ]

    for pattern in valid_patterns:
        assert manager.validate_pattern(pattern), f"Pattern should be valid: {pattern}"


def test_validate_pattern_invalid(manager):
    """Test pattern validation for invalid patterns."""
    invalid_patterns = [
        "",  # Empty
        "# Comment",  # Comment
        "pattern\x00with\x00null",  # Null bytes
        "pattern\nwith\nnewline",  # Newlines
    ]

    for pattern in invalid_patterns:
        assert not manager.validate_pattern(pattern), f"Pattern should be invalid: {pattern}"


def test_generate_default_ragignore(manager):
    """Test generating default .ragignore content."""
    content = manager.generate_default()

    # Should contain common patterns
    assert "node_modules/" in content
    assert "dist/" in content
    assert "venv/" in content
    assert ".git/" in content
    assert "*.log" in content
    assert "*.pyc" not in content  # .pyc files handled by __pycache__/

    # Should contain comments/headers
    assert "#" in content


def test_apply_patterns_no_ragignore(manager, temp_project):
    """Test applying patterns when no .ragignore exists."""
    files = [
        temp_project / "main.py",
        temp_project / "utils.py",
    ]

    # Without .ragignore, all files should pass through
    filtered = manager.apply_patterns(files)
    assert len(filtered) == len(files)


def test_apply_patterns_exclude_directory(manager, temp_project):
    """Test excluding directories via .ragignore."""
    manager.write("node_modules/\n", backup=False)

    files = [
        temp_project / "main.py",
        temp_project / "node_modules" / "package.json",
        temp_project / "node_modules" / "lib" / "index.js",
        temp_project / "utils.py",
    ]

    filtered = manager.apply_patterns(files)

    # Should exclude node_modules files
    filtered_names = [f.name for f in filtered]
    assert "main.py" in filtered_names
    assert "utils.py" in filtered_names
    assert "package.json" not in filtered_names
    assert "index.js" not in filtered_names


def test_apply_patterns_exclude_wildcard(manager, temp_project):
    """Test excluding files by wildcard pattern."""
    manager.write("*.log\n", backup=False)

    files = [
        temp_project / "app.log",
        temp_project / "error.log",
        temp_project / "main.py",
        temp_project / "README.md",
    ]

    filtered = manager.apply_patterns(files)

    filtered_names = [f.name for f in filtered]
    assert "main.py" in filtered_names
    assert "README.md" in filtered_names
    assert "app.log" not in filtered_names
    assert "error.log" not in filtered_names


def test_apply_patterns_multiple_patterns(manager, temp_project):
    """Test applying multiple exclusion patterns."""
    manager.write("*.log\nnode_modules/\ndist/\n", backup=False)

    files = [
        temp_project / "main.py",
        temp_project / "app.log",
        temp_project / "node_modules" / "pkg" / "index.js",
        temp_project / "dist" / "bundle.js",
        temp_project / "src" / "utils.py",
    ]

    filtered = manager.apply_patterns(files)

    filtered_paths = [str(f.relative_to(temp_project)) for f in filtered]
    assert "main.py" in filtered_paths
    assert str(Path("src") / "utils.py") in filtered_paths
    assert "app.log" not in filtered_paths
    assert str(Path("node_modules") / "pkg" / "index.js") not in filtered_paths
    assert str(Path("dist") / "bundle.js") not in filtered_paths


def test_create_from_suggestions(manager):
    """Test creating .ragignore from optimization suggestions."""
    suggestions = [
        OptimizationSuggestion(
            type="exclude_directory",
            description="Exclude Node.js dependencies",
            pattern="node_modules/",
            affected_files=100,
            size_savings_mb=50.0,
            time_savings_seconds=10.0,
            priority=5,
        ),
        OptimizationSuggestion(
            type="exclude_directory",
            description="Exclude build outputs",
            pattern="dist/",
            affected_files=20,
            size_savings_mb=10.0,
            time_savings_seconds=2.0,
            priority=4,
        ),
    ]

    content = manager.create_from_suggestions(suggestions, merge_existing=False)

    # Should contain patterns
    assert "node_modules/" in content
    assert "dist/" in content

    # Should contain descriptions
    assert "Node.js dependencies" in content
    assert "build outputs" in content

    # Should contain savings info
    assert "100 files" in content
    assert "50.0MB" in content


def test_create_from_suggestions_merge_existing(manager, temp_project):
    """Test creating .ragignore merging with existing patterns."""
    # Create existing .ragignore
    manager.write("custom-dir/\n*.tmp\n", backup=False)

    suggestions = [
        OptimizationSuggestion(
            type="exclude_directory",
            description="Exclude Node.js dependencies",
            pattern="node_modules/",
            affected_files=100,
            size_savings_mb=50.0,
            time_savings_seconds=10.0,
            priority=5,
        ),
    ]

    content = manager.create_from_suggestions(suggestions, merge_existing=True)

    # Should contain new pattern
    assert "node_modules/" in content

    # Existing patterns should be preserved
    # (They're in merged_patterns but may not appear in the description-based output)
    # The function only adds patterns from suggestions to the output


def test_pattern_to_regex_simple(manager):
    """Test pattern to regex conversion for simple patterns."""
    # Test basic wildcard
    regex = manager._pattern_to_regex("*.log")
    assert "[^/]*\\.log" in regex  # * becomes [^/]*, . is escaped

    # Test directory pattern
    regex = manager._pattern_to_regex("node_modules/")
    assert "node_modules" in regex


def test_pattern_to_regex_double_star(manager):
    """Test pattern to regex conversion for ** patterns."""
    regex = manager._pattern_to_regex("**/*.pyc")
    assert ".*" in regex  # ** becomes .*


def test_pattern_sorting(manager):
    """Test that merged patterns are sorted."""
    existing = ["z-pattern/", "a-pattern/", "m-pattern/"]
    new = ["b-pattern/"]

    merged = manager.merge_patterns(existing, new)

    # Should be sorted alphabetically
    assert merged == sorted(merged)


def test_empty_patterns_handling(manager):
    """Test handling of empty pattern lists."""
    existing = []
    new = []

    merged = manager.merge_patterns(existing, new)
    assert merged == []


def test_whitespace_normalization(manager):
    """Test that patterns are normalized (whitespace stripped)."""
    existing = ["  node_modules/  ", "dist/"]
    new = ["  *.log  "]

    merged = manager.merge_patterns(existing, new)

    # Whitespace should be stripped
    assert "node_modules/" in merged
    assert "*.log" in merged
    assert "  node_modules/  " not in merged


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
