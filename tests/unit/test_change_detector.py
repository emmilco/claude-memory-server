"""Unit tests for change detection."""

import pytest
from dataclasses import dataclass
from src.memory.change_detector import ChangeDetector, FileChange, quick_file_hash


# Mock SemanticUnit for testing (matches the structure used by ChangeDetector)
@dataclass
class MockSemanticUnit:
    """Mock semantic unit for testing."""
    name: str
    unit_type: str
    content: str
    signature: str
    start_line: int
    end_line: int
    language: str = "python"
    file_path: str = "test.py"


@pytest.fixture
def detector():
    """Create change detector instance."""
    return ChangeDetector()


@pytest.fixture
def sample_units_old():
    """Sample old semantic units."""
    return [
        MockSemanticUnit(
            name="function1",
            unit_type="function",
            content="def function1():\n    return 1",
            signature="def function1()",
            start_line=1,
            end_line=2,
        ),
        MockSemanticUnit(
            name="function2",
            unit_type="function",
            content="def function2():\n    return 2",
            signature="def function2()",
            start_line=4,
            end_line=5,
        ),
    ]


@pytest.fixture
def sample_units_new():
    """Sample new semantic units."""
    return [
        MockSemanticUnit(
            name="function1",
            unit_type="function",
            content="def function1():\n    return 1",  # Unchanged
            signature="def function1()",
            start_line=1,
            end_line=2,
        ),
        MockSemanticUnit(
            name="function2",
            unit_type="function",
            content="def function2():\n    return 42",  # Modified
            signature="def function2()",
            start_line=4,
            end_line=5,
        ),
        MockSemanticUnit(
            name="function3",
            unit_type="function",
            content="def function3():\n    return 3",  # Added
            signature="def function3()",
            start_line=7,
            end_line=8,
        ),
    ]


class TestFileChanges:
    """Test file-level change detection."""

    def test_detect_added_files(self, detector):
        """Test detection of added files."""
        old_files = {}
        new_files = {"file1.py": "content"}

        changes = detector.detect_file_changes(old_files, new_files)

        assert len(changes) == 1
        assert changes[0].change_type == "added"
        assert changes[0].file_path == "file1.py"

    def test_detect_deleted_files(self, detector):
        """Test detection of deleted files."""
        old_files = {"file1.py": "content"}
        new_files = {}

        changes = detector.detect_file_changes(old_files, new_files)

        assert len(changes) == 1
        assert changes[0].change_type == "deleted"
        assert changes[0].file_path == "file1.py"

    def test_detect_modified_files(self, detector):
        """Test detection of modified files."""
        old_files = {"file1.py": "old content"}
        new_files = {"file1.py": "new content"}

        changes = detector.detect_file_changes(old_files, new_files)

        assert len(changes) == 1
        assert changes[0].change_type == "modified"
        assert changes[0].file_path == "file1.py"

    def test_detect_no_changes(self, detector):
        """Test when files are unchanged."""
        files = {"file1.py": "content"}

        changes = detector.detect_file_changes(files, files)

        assert len(changes) == 0

    def test_detect_renamed_files(self, detector):
        """Test detection of renamed files."""
        old_files = {"old_name.py": "same content here"}
        new_files = {"new_name.py": "same content here"}

        changes = detector.detect_file_changes(old_files, new_files)

        # Should detect as rename (high similarity)
        rename_changes = [c for c in changes if c.change_type == "renamed"]
        assert len(rename_changes) == 1
        assert rename_changes[0].old_path == "old_name.py"
        assert rename_changes[0].file_path == "new_name.py"

    def test_multiple_changes(self, detector):
        """Test detection of multiple types of changes."""
        old_files = {
            "deleted.py": "old",
            "modified.py": "old content",
            "unchanged.py": "same",
        }
        new_files = {
            "added.py": "new",
            "modified.py": "new content",
            "unchanged.py": "same",
        }

        changes = detector.detect_file_changes(old_files, new_files)

        change_types = {c.change_type for c in changes}
        assert "added" in change_types
        assert "deleted" in change_types
        assert "modified" in change_types


class TestUnitChanges:
    """Test semantic unit-level change detection."""

    def test_detect_added_units(self, detector, sample_units_old, sample_units_new):
        """Test detection of added units."""
        added, modified, deleted = detector.detect_unit_changes(
            sample_units_old, sample_units_new
        )

        assert "function3" in added
        assert len(added) == 1

    def test_detect_modified_units(self, detector, sample_units_old, sample_units_new):
        """Test detection of modified units."""
        added, modified, deleted = detector.detect_unit_changes(
            sample_units_old, sample_units_new
        )

        assert "function2" in modified
        assert len(modified) == 1

    def test_detect_deleted_units(self, detector, sample_units_new):
        """Test detection of deleted units."""
        units_with_extra = sample_units_new + [
            MockSemanticUnit(
                name="old_function",
                unit_type="function",
                content="def old_function(): pass",
                signature="def old_function()",
                start_line=10,
                end_line=10,
            )
        ]

        added, modified, deleted = detector.detect_unit_changes(
            units_with_extra, sample_units_new
        )

        assert "old_function" in deleted
        assert len(deleted) == 1

    def test_detect_no_unit_changes(self, detector, sample_units_old):
        """Test when units are unchanged."""
        added, modified, deleted = detector.detect_unit_changes(
            sample_units_old, sample_units_old
        )

        assert len(added) == 0
        assert len(modified) == 0
        assert len(deleted) == 0

    def test_unit_hash_different_for_changes(self, detector):
        """Test that unit hash changes when content changes."""
        unit1 = MockSemanticUnit(
            name="func", unit_type="function",
            content="def func(): return 1",
            signature="", start_line=1, end_line=1
        )
        unit2 = MockSemanticUnit(
            name="func", unit_type="function",
            content="def func(): return 2",  # Different
            signature="", start_line=1, end_line=1
        )

        hash1 = detector._unit_hash(unit1)
        hash2 = detector._unit_hash(unit2)

        assert hash1 != hash2


class TestIncrementalIndexing:
    """Test incremental indexing plan generation."""

    def test_plan_for_added_file(self, detector, sample_units_new):
        """Test indexing plan for added file."""
        change = FileChange(file_path="new.py", change_type="added")

        plan = detector.get_incremental_index_plan(change, [], sample_units_new)

        assert len(plan["units_to_add"]) == 3
        assert len(plan["units_to_delete"]) == 0
        assert plan["full_reindex_needed"] is False

    def test_plan_for_deleted_file(self, detector, sample_units_old):
        """Test indexing plan for deleted file."""
        change = FileChange(file_path="old.py", change_type="deleted")

        plan = detector.get_incremental_index_plan(change, sample_units_old, [])

        assert len(plan["units_to_delete"]) == 2
        assert len(plan["units_to_add"]) == 0

    def test_plan_for_modified_file(self, detector, sample_units_old, sample_units_new):
        """Test indexing plan for modified file."""
        change = FileChange(file_path="modified.py", change_type="modified")

        plan = detector.get_incremental_index_plan(
            change, sample_units_old, sample_units_new
        )

        assert "function3" in plan["units_to_add"]
        assert "function2" in plan["units_to_update"]
        assert plan["full_reindex_needed"] is False

    def test_plan_recommends_full_reindex(self, detector):
        """Test that plan recommends full reindex for massive changes."""
        # Create many units
        old_units = [
            MockSemanticUnit(
                name=f"func{i}", unit_type="function",
                content=f"def func{i}(): pass",
                signature="", start_line=i, end_line=i
            )
            for i in range(10)
        ]

        # Change most of them
        new_units = [
            MockSemanticUnit(
                name=f"func{i}", unit_type="function",
                content=f"def func{i}(): return {i}",  # Changed
                signature="", start_line=i, end_line=i
            )
            for i in range(10)
        ]

        change = FileChange(file_path="big.py", change_type="modified")
        plan = detector.get_incremental_index_plan(change, old_units, new_units)

        # Should recommend full reindex (>70% changed)
        assert plan["full_reindex_needed"] is True


class TestContentSimilarity:
    """Test content similarity calculation."""

    def test_identical_content(self, detector):
        """Test similarity of identical content."""
        content = "same content"
        ratio = detector._content_similarity(content, content)

        assert ratio == 1.0

    def test_completely_different(self, detector):
        """Test similarity of completely different content."""
        ratio = detector._content_similarity("abc", "xyz")

        assert ratio < 0.5

    def test_similar_content(self, detector):
        """Test similarity of similar content."""
        old = "def func():\n    return 1"
        new = "def func():\n    return 2"

        ratio = detector._content_similarity(old, new)

        assert 0.8 < ratio < 1.0


class TestStatistics:
    """Test statistics tracking."""

    def test_stats_tracking(self, detector):
        """Test that statistics are tracked."""
        old_files = {"file.py": "old"}
        new_files = {"file.py": "new"}

        detector.detect_file_changes(old_files, new_files)

        stats = detector.get_stats()

        assert stats["files_compared"] > 0
        assert stats["changes_detected"] > 0

    def test_unit_stats_tracking(self, detector, sample_units_old, sample_units_new):
        """Test unit comparison stats."""
        detector.detect_unit_changes(sample_units_old, sample_units_new)

        stats = detector.get_stats()

        assert stats["units_compared"] > 0


class TestFileChangeDataclass:
    """Test FileChange dataclass."""

    def test_file_change_creation(self):
        """Test creating FileChange."""
        change = FileChange(
            file_path="test.py",
            change_type="modified",
        )

        assert change.file_path == "test.py"
        assert change.change_type == "modified"
        assert change.units_added == []
        assert change.units_modified == []
        assert change.units_deleted == []
