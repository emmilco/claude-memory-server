"""Manage .ragignore files for excluding files from indexing."""

import logging
import re
from pathlib import Path
from typing import List, Set, Optional

logger = logging.getLogger(__name__)


class RagignoreManager:
    """
    Manage .ragignore files.

    .ragignore uses gitignore syntax:
    - # for comments
    - / at start means root directory
    - / at end means directory only
    - * for wildcards
    - ! to negate patterns
    """

    RAGIGNORE_FILENAME = ".ragignore"

    def __init__(self, directory: Path):
        """
        Initialize ragignore manager.

        Args:
            directory: Project root directory
        """
        self.directory = Path(directory).resolve()
        self.ragignore_path = self.directory / self.RAGIGNORE_FILENAME

    def read_existing(self) -> List[str]:
        """
        Read existing .ragignore file.

        Returns:
            List of patterns (excluding comments and empty lines)
        """
        if not self.ragignore_path.exists():
            return []

        try:
            with open(self.ragignore_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            # Extract patterns (skip comments and empty lines)
            patterns = []
            for line in lines:
                line = line.strip()
                if line and not line.startswith("#"):
                    patterns.append(line)

            logger.info(f"Read {len(patterns)} existing patterns from .ragignore")
            return patterns

        except Exception as e:
            logger.error(f"Error reading .ragignore: {e}")
            return []

    def read_with_comments(self) -> str:
        """
        Read existing .ragignore file with comments preserved.

        Returns:
            Full file content
        """
        if not self.ragignore_path.exists():
            return ""

        try:
            with open(self.ragignore_path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            logger.error(f"Error reading .ragignore: {e}")
            return ""

    def write(self, content: str, backup: bool = True) -> bool:
        """
        Write .ragignore file.

        Args:
            content: File content to write
            backup: Create backup of existing file

        Returns:
            True if successful
        """
        try:
            # Backup existing file
            if backup and self.ragignore_path.exists():
                backup_path = self.ragignore_path.with_suffix(".ragignore.bak")
                self.ragignore_path.rename(backup_path)
                logger.info(f"Created backup: {backup_path}")

            # Write new content
            with open(self.ragignore_path, "w", encoding="utf-8") as f:
                f.write(content)

            logger.info(f"Wrote .ragignore to {self.ragignore_path}")
            return True

        except Exception as e:
            logger.error(f"Error writing .ragignore: {e}")
            return False

    def merge_patterns(
        self,
        existing: List[str],
        new: List[str],
        preserve_existing: bool = True,
    ) -> List[str]:
        """
        Merge new patterns with existing ones.

        Args:
            existing: Existing patterns
            new: New patterns to add
            preserve_existing: Keep existing patterns even if similar

        Returns:
            Merged pattern list
        """
        if not existing:
            return new

        # Use set for deduplication
        pattern_set: Set[str] = set(existing) if preserve_existing else set()

        for pattern in new:
            # Normalize pattern
            normalized = pattern.strip()

            # Check if pattern already exists (exact match)
            if normalized in pattern_set:
                continue

            # Check if a more general pattern already exists
            if self._has_general_pattern(pattern_set, normalized):
                logger.debug(f"Skipping {normalized} (covered by existing pattern)")
                continue

            pattern_set.add(normalized)

        # Convert back to list and sort
        merged = sorted(pattern_set)
        logger.info(f"Merged patterns: {len(existing)} existing + {len(new)} new = {len(merged)} total")
        return merged

    def _has_general_pattern(self, existing: Set[str], pattern: str) -> bool:
        """Check if a more general pattern already exists."""
        # Check for directory patterns that would cover this
        if "/" in pattern:
            # e.g., "node_modules/foo" is covered by "node_modules/"
            parts = pattern.split("/")
            if len(parts) > 1:
                parent_pattern = parts[0] + "/"
                if parent_pattern in existing:
                    return True

        return False

    def validate_pattern(self, pattern: str) -> bool:
        """
        Validate gitignore-style pattern.

        Args:
            pattern: Pattern to validate

        Returns:
            True if valid
        """
        if not pattern or pattern.startswith("#"):
            return False

        # Check for invalid characters
        invalid_chars = ["\x00", "\r", "\n"]
        if any(char in pattern for char in invalid_chars):
            return False

        # Check for basic syntax errors
        try:
            # Convert gitignore pattern to regex (basic validation)
            self._pattern_to_regex(pattern)
            return True
        except Exception:
            return False

    def _pattern_to_regex(self, pattern: str) -> str:
        """
        Convert gitignore pattern to regex (simplified).

        Args:
            pattern: Gitignore pattern

        Returns:
            Regex pattern string
        """
        # This is a simplified conversion, not full gitignore semantics
        regex = pattern

        # Escape special regex characters (except * and ?)
        for char in [".  ", "+", "^", "$", "(", ")", "[", "]", "{", "}", "|", "\\"]:
            regex = regex.replace(char, "\\" + char)

        # Convert gitignore wildcards to regex
        regex = regex.replace("**", ".*")  # ** matches any path
        regex = regex.replace("*", "[^/]*")  # * matches within path segment
        regex = regex.replace("?", ".")  # ? matches single character

        # Handle directory patterns (ending with /)
        if regex.endswith("/"):
            regex = regex[:-1] + "($|/)"

        # Handle root patterns (starting with /)
        if regex.startswith("/"):
            regex = "^" + regex[1:]
        else:
            regex = "(^|/)" + regex

        return regex

    def generate_default(self) -> str:
        """
        Generate default .ragignore content.

        Returns:
            Default .ragignore content
        """
        return """# .ragignore - Patterns to exclude from indexing
# Uses gitignore syntax

# Dependencies
node_modules/
bower_components/
vendor/

# Python virtual environments
venv/
.venv/
env/
.env/
virtualenv/
__pycache__/

# Build outputs
dist/
build/
out/
target/
bin/
obj/
.next/
.nuxt/

# Caches
.cache/
.pytest_cache/
.mypy_cache/
.ruff_cache/
.turbo/
.parcel-cache/

# Version control
.git/
.svn/
.hg/

# IDE
.idea/
.vscode/
.vs/

# Binary files
*.exe
*.dll
*.so
*.dylib
*.bin

# Images
*.jpg
*.jpeg
*.png
*.gif
*.ico

# Archives
*.zip
*.tar
*.gz
*.bz2

# Logs
*.log

# OS files
.DS_Store
Thumbs.db
"""

    def apply_patterns(self, file_paths: List[Path]) -> List[Path]:
        """
        Filter file list using .ragignore patterns.

        Args:
            file_paths: List of file paths to filter

        Returns:
            Filtered list (excluded files removed)
        """
        patterns = self.read_existing()
        if not patterns:
            return file_paths

        # Convert patterns to regexes
        regexes = []
        for pattern in patterns:
            if pattern.startswith("!"):
                # Negation patterns not supported yet
                continue

            try:
                regex_pattern = self._pattern_to_regex(pattern)
                regexes.append(re.compile(regex_pattern))
            except Exception as e:
                logger.warning(f"Invalid pattern '{pattern}': {e}")
                continue

        # Filter files
        filtered = []
        for file_path in file_paths:
            # Convert to relative path from directory
            try:
                rel_path = file_path.relative_to(self.directory)
                path_str = str(rel_path)

                # Check if any pattern matches
                excluded = False
                for regex in regexes:
                    if regex.search(path_str):
                        excluded = True
                        break

                if not excluded:
                    filtered.append(file_path)

            except ValueError:
                # File not relative to directory, include it
                filtered.append(file_path)

        logger.info(f"Filtered {len(file_paths)} files -> {len(filtered)} (excluded {len(file_paths) - len(filtered)})")
        return filtered

    def create_from_suggestions(
        self,
        suggestions: List,  # List[OptimizationSuggestion]
        merge_existing: bool = True,
    ) -> str:
        """
        Create .ragignore content from optimization suggestions.

        Args:
            suggestions: List of OptimizationSuggestion objects
            merge_existing: Merge with existing patterns

        Returns:
            .ragignore file content
        """
        # Extract patterns from suggestions
        new_patterns = [s.pattern for s in suggestions]

        if merge_existing:
            existing_patterns = self.read_existing()
            merged_patterns = self.merge_patterns(existing_patterns, new_patterns)
        else:
            merged_patterns = new_patterns

        # Generate content with header
        lines = [
            "# .ragignore - Generated by Claude Memory RAG Server",
            "# Patterns to exclude from indexing (gitignore syntax)",
            "",
        ]

        # Add patterns with descriptions from suggestions
        for suggestion in suggestions:
            if suggestion.pattern in merged_patterns:
                lines.append(f"# {suggestion.description}")
                lines.append(f"# Saves: {suggestion.affected_files} files, {suggestion.size_savings_mb:.1f}MB, {suggestion.time_savings_seconds:.1f}s")
                lines.append(suggestion.pattern)
                lines.append("")

        return "\n".join(lines)
