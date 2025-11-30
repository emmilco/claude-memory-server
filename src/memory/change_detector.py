"""Change detection for incremental code indexing."""

import logging
import difflib
import hashlib
from typing import List, Dict, Set, Tuple, Optional, Any
from dataclasses import dataclass
from pathlib import Path

from src.memory.incremental_indexer import SemanticUnit

logger = logging.getLogger(__name__)


@dataclass
class FileChange:
    """Represents changes to a file."""
    file_path: str
    change_type: str  # "added", "modified", "deleted", "renamed"
    old_path: Optional[str] = None  # For renamed files
    old_content: Optional[str] = None
    new_content: Optional[str] = None
    units_added: List[str] = None  # Unit names
    units_modified: List[str] = None
    units_deleted: List[str] = None
    similarity_ratio: float = 0.0  # For renamed files

    def __post_init__(self):
        if self.units_added is None:
            self.units_added = []
        if self.units_modified is None:
            self.units_modified = []
        if self.units_deleted is None:
            self.units_deleted = []


class ChangeDetector:
    """
    Detect changes in code files for incremental indexing.

    Tracks changes at both file and function/class level to enable
    efficient re-indexing of only what changed.
    """

    def __init__(self, similarity_threshold: float = 0.8):
        """
        Initialize change detector.

        Args:
            similarity_threshold: Threshold for detecting renamed files (0-1)
        """
        self.similarity_threshold = similarity_threshold

        # Statistics
        self.stats = {
            "files_compared": 0,
            "units_compared": 0,
            "changes_detected": 0,
        }

    def detect_file_changes(
        self,
        old_files: Dict[str, str],
        new_files: Dict[str, str],
    ) -> List[FileChange]:
        """
        Detect changes between old and new file sets.

        Args:
            old_files: Dict mapping file_path -> content (old state)
            new_files: Dict mapping file_path -> content (new state)

        Returns:
            List of FileChange objects
        """
        changes = []

        old_paths = set(old_files.keys())
        new_paths = set(new_files.keys())

        # Detect added files
        added_paths = new_paths - old_paths
        for path in added_paths:
            changes.append(FileChange(
                file_path=path,
                change_type="added",
                new_content=new_files[path],
            ))
            self.stats["changes_detected"] += 1

        # Detect deleted files
        deleted_paths = old_paths - new_paths
        for path in deleted_paths:
            changes.append(FileChange(
                file_path=path,
                change_type="deleted",
                old_content=old_files[path],
            ))
            self.stats["changes_detected"] += 1

        # Detect modified files
        common_paths = old_paths & new_paths
        for path in common_paths:
            self.stats["files_compared"] += 1

            old_content = old_files[path]
            new_content = new_files[path]

            if old_content != new_content:
                changes.append(FileChange(
                    file_path=path,
                    change_type="modified",
                    old_content=old_content,
                    new_content=new_content,
                ))
                self.stats["changes_detected"] += 1

        # Detect renamed files (optional heuristic)
        changes = self._detect_renames(changes, old_files, new_files)

        return changes

    def _detect_renames(
        self,
        changes: List[FileChange],
        old_files: Dict[str, str],
        new_files: Dict[str, str],
    ) -> List[FileChange]:
        """
        Detect renamed files by comparing content similarity.

        Args:
            changes: Current list of changes
            old_files: Old file contents
            new_files: New file contents

        Returns:
            Updated changes list with renames detected
        """
        # Separate added and deleted files
        added = [c for c in changes if c.change_type == "added"]
        deleted = [c for c in changes if c.change_type == "deleted"]

        if not added or not deleted:
            return changes

        # Try to match deleted files with added files
        matched_pairs = []

        for deleted_change in deleted:
            deleted_content = old_files[deleted_change.file_path]

            best_match = None
            best_ratio = 0.0

            for added_change in added:
                added_content = new_files[added_change.file_path]

                # Quick check: compare file sizes
                size_ratio = min(len(deleted_content), len(added_content)) / max(
                    len(deleted_content), len(added_content), 1
                )

                if size_ratio < 0.5:  # Too different in size
                    continue

                # Calculate similarity
                ratio = self._content_similarity(deleted_content, added_content)

                if ratio > best_ratio and ratio >= self.similarity_threshold:
                    best_ratio = ratio
                    best_match = added_change

            if best_match:
                matched_pairs.append((deleted_change, best_match, best_ratio))

        # Create rename changes and remove matched added/deleted
        updated_changes = []
        matched_deleted = set()
        matched_added = set()

        for deleted_change, added_change, ratio in matched_pairs:
            updated_changes.append(FileChange(
                file_path=added_change.file_path,
                change_type="renamed",
                old_path=deleted_change.file_path,
                old_content=deleted_change.old_content,
                new_content=added_change.new_content,
                similarity_ratio=ratio,
            ))
            matched_deleted.add(deleted_change.file_path)
            matched_added.add(added_change.file_path)

        # Add unmatched changes
        for change in changes:
            if change.change_type == "deleted" and change.file_path in matched_deleted:
                continue
            if change.change_type == "added" and change.file_path in matched_added:
                continue
            updated_changes.append(change)

        return updated_changes

    @staticmethod
    def _content_similarity(content1: str, content2: str) -> float:
        """
        Calculate content similarity using difflib.

        Args:
            content1: First content
            content2: Second content

        Returns:
            Similarity ratio (0-1)
        """
        seq_matcher = difflib.SequenceMatcher(None, content1, content2)
        return seq_matcher.ratio()

    def detect_unit_changes(
        self,
        old_units: List[SemanticUnit],
        new_units: List[SemanticUnit],
    ) -> Tuple[Set[str], Set[str], Set[str]]:
        """
        Detect changes at semantic unit (function/class) level.

        Args:
            old_units: Semantic units from old version
            new_units: Semantic units from new version

        Returns:
            Tuple of (added_unit_names, modified_unit_names, deleted_unit_names)
        """
        # Build unit maps by name
        old_unit_map = {unit.name: unit for unit in old_units}
        new_unit_map = {unit.name: unit for unit in new_units}

        old_names = set(old_unit_map.keys())
        new_names = set(new_unit_map.keys())

        # Detect changes
        added = new_names - old_names
        deleted = old_names - new_names
        common = old_names & new_names

        # Check for modifications in common units
        modified = set()
        for name in common:
            self.stats["units_compared"] += 1

            old_unit = old_unit_map[name]
            new_unit = new_unit_map[name]

            # Compare content hash
            if self._unit_hash(old_unit) != self._unit_hash(new_unit):
                modified.add(name)

        return added, modified, deleted

    @staticmethod
    def _unit_hash(unit: SemanticUnit) -> str:
        """
        Calculate hash of semantic unit content.

        Args:
            unit: Semantic unit

        Returns:
            Content hash
        """
        # Hash the content (normalized)
        content = unit.content.strip()
        return hashlib.sha256(content.encode()).hexdigest()

    def get_incremental_index_plan(
        self,
        file_change: FileChange,
        old_units: List[SemanticUnit],
        new_units: List[SemanticUnit],
    ) -> Dict[str, Any]:
        """
        Create an incremental indexing plan for a changed file.

        Args:
            file_change: File change information
            old_units: Units from old version
            new_units: Units from new version

        Returns:
            Indexing plan with actions to take
        """
        plan = {
            "file_path": file_change.file_path,
            "change_type": file_change.change_type,
            "units_to_delete": [],
            "units_to_add": [],
            "units_to_update": [],
            "full_reindex_needed": False,
        }

        if file_change.change_type == "added":
            # Add all new units
            plan["units_to_add"] = [unit.name for unit in new_units]

        elif file_change.change_type == "deleted":
            # Delete all old units
            plan["units_to_delete"] = [unit.name for unit in old_units]

        elif file_change.change_type in ("modified", "renamed"):
            # Incremental update
            added, modified, deleted = self.detect_unit_changes(old_units, new_units)

            plan["units_to_add"] = list(added)
            plan["units_to_update"] = list(modified)
            plan["units_to_delete"] = list(deleted)

            file_change.units_added = list(added)
            file_change.units_modified = list(modified)
            file_change.units_deleted = list(deleted)

            # If too many changes, might be faster to full reindex
            total_changes = len(added) + len(modified) + len(deleted)
            if total_changes > len(new_units) * 0.7:  # 70% threshold
                plan["full_reindex_needed"] = True
                logger.info(
                    f"Full reindex recommended for {file_change.file_path} "
                    f"({total_changes} changes out of {len(new_units)} units)"
                )

        return plan

    def get_stats(self) -> dict:
        """Get change detection statistics."""
        return self.stats.copy()


def quick_file_hash(file_path: str) -> str:
    """
    Calculate quick hash of file content.

    Args:
        file_path: Path to file

    Returns:
        SHA-256 hash
    """
    try:
        with open(file_path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()
    except Exception as e:
        logger.error(f"Error hashing file {file_path}: {e}")
        return ""


def build_file_hash_index(directory: Path, extensions: Set[str]) -> Dict[str, str]:
    """
    Build index of file hashes for quick change detection.

    Args:
        directory: Directory to scan
        extensions: File extensions to include (e.g., {".py", ".js"})

    Returns:
        Dict mapping file_path -> hash
    """
    hash_index = {}

    for ext in extensions:
        for file_path in directory.rglob(f"*{ext}"):
            if file_path.is_file():
                file_hash = quick_file_hash(str(file_path))
                if file_hash:
                    hash_index[str(file_path)] = file_hash

    return hash_index
