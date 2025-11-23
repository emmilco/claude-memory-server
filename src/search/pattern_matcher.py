"""Regex pattern matching for code search.

This module provides hybrid pattern detection combining regex patterns with semantic search.
Supports three modes: filter, boost, and require.
"""

import re
import logging
from typing import List, Dict, Any, Optional, Pattern
from dataclasses import dataclass

from src.core.exceptions import ValidationError

logger = logging.getLogger(__name__)


# Pattern presets for common use cases
PATTERN_PRESETS = {
    # Error Handling
    "error_handlers": r"(try|catch|except|rescue)\s*[:\{]",
    "bare_except": r"except\s*:",  # Python code smell
    "broad_catch": r"catch\s*\(\s*Exception",  # Java/C# code smell
    "empty_catch": r"catch\s*\([^)]+\)\s*\{\s*\}",  # Empty catch blocks

    # Code Comments
    "TODO_comments": r"(TODO|FIXME|HACK|XXX|NOTE)[:|\s]",
    "deprecated_markers": r"@deprecated|@Deprecated|DEPRECATED",

    # Security Keywords
    "security_keywords": r"(password|secret|token|api[_-]?key|private[_-]?key)",
    "auth_patterns": r"(authenticate|authorize|permission|access[_-]?control)",

    # API Patterns
    "deprecated_apis": r"(deprecated\(|@Deprecated|__deprecated__|OBSOLETE)",
    "async_patterns": r"(async\s+def|await\s+|Promise\.|async\s+function)",

    # Code Smells
    "magic_numbers": r"\b\d{3,}\b",  # Numbers > 100 (likely magic numbers)
    "long_lines": r"^.{120,}$",  # Lines > 120 chars
    "multiple_returns": r"return\s+.*\n.*return\s+",  # Multiple returns

    # Configuration
    "config_keys": r"(config\.|env\[|process\.env\.|getenv\()",
    "hardcoded_urls": r"https?://[^\s\"']+",
}


@dataclass
class MatchLocation:
    """Represents a single pattern match location."""

    line: int
    column: int
    text: str
    start: int
    end: int


class PatternMatcher:
    """Handles regex pattern matching on code content."""

    def __init__(self):
        """Initialize pattern matcher with empty cache."""
        self._pattern_cache: Dict[str, Pattern] = {}

    def compile_pattern(self, pattern: str) -> Pattern:
        """
        Compile regex pattern with caching and validation.

        Args:
            pattern: Regex pattern string or @preset:name

        Returns:
            Compiled regex pattern

        Raises:
            ValidationError: If pattern is invalid
        """
        # Resolve preset if pattern starts with @preset:
        original_pattern = pattern
        if pattern.startswith("@preset:"):
            preset_name = pattern[8:]  # Remove "@preset:" prefix
            if preset_name not in PATTERN_PRESETS:
                available = ", ".join(sorted(PATTERN_PRESETS.keys()))
                raise ValidationError(
                    f"Unknown pattern preset: {preset_name}. "
                    f"Available presets: {available}"
                )
            pattern = PATTERN_PRESETS[preset_name]
            logger.debug(f"Resolved preset '{preset_name}' to pattern: {pattern}")

        # Check cache (use original pattern as key to include preset name)
        cache_key = original_pattern
        if cache_key not in self._pattern_cache:
            try:
                self._pattern_cache[cache_key] = re.compile(
                    pattern,
                    re.MULTILINE | re.DOTALL
                )
                logger.debug(f"Compiled and cached pattern: {cache_key}")
            except re.error as e:
                raise ValidationError(f"Invalid regex pattern '{pattern}': {e}")

        return self._pattern_cache[cache_key]

    def match(self, pattern: str, content: str) -> bool:
        """
        Check if pattern matches content.

        Args:
            pattern: Regex pattern or @preset:name
            content: Code content to search

        Returns:
            True if pattern matches, False otherwise
        """
        compiled = self.compile_pattern(pattern)
        return compiled.search(content) is not None

    def find_matches(self, pattern: str, content: str) -> List[re.Match]:
        """
        Find all pattern matches in content.

        Args:
            pattern: Regex pattern or @preset:name
            content: Code content to search

        Returns:
            List of regex match objects
        """
        compiled = self.compile_pattern(pattern)
        return list(compiled.finditer(content))

    def get_match_count(self, pattern: str, content: str) -> int:
        """
        Count number of pattern matches.

        Args:
            pattern: Regex pattern or @preset:name
            content: Code content to search

        Returns:
            Number of matches found
        """
        return len(self.find_matches(pattern, content))

    def get_match_locations(
        self,
        pattern: str,
        content: str
    ) -> List[MatchLocation]:
        """
        Get detailed match locations with line numbers.

        Args:
            pattern: Regex pattern or @preset:name
            content: Code content to search

        Returns:
            List of MatchLocation objects
        """
        matches = self.find_matches(pattern, content)
        locations = []

        # Build line offset map for efficient line number lookup
        lines = content.split("\n")
        line_offsets = [0]
        for line in lines:
            line_offsets.append(line_offsets[-1] + len(line) + 1)  # +1 for newline

        for match in matches:
            # Find line number from byte offset
            start_pos = match.start()
            line_num = 0
            for i, offset in enumerate(line_offsets):
                if offset > start_pos:
                    line_num = i
                    break

            # Find column (offset within line)
            if line_num > 0:
                column = start_pos - line_offsets[line_num - 1]
            else:
                column = start_pos

            locations.append(
                MatchLocation(
                    line=line_num,
                    column=column,
                    text=match.group(0),
                    start=match.start(),
                    end=match.end(),
                )
            )

        return locations

    def calculate_pattern_score(
        self,
        content: str,
        pattern: str,
        unit_type: str = "function",
    ) -> float:
        """
        Calculate pattern match quality score (0.0-1.0).

        Scoring factors:
        - Match exists (binary): +0.5
        - Match count (diminishing): +0.2 max
        - Signature match (first 2 lines): +0.2
        - High density (matches per line): +0.1

        Args:
            content: Code content
            pattern: Regex pattern or @preset:name
            unit_type: Type of code unit (function, class, etc.)

        Returns:
            Quality score between 0.0 and 1.0
        """
        matches = self.find_matches(pattern, content)

        if not matches:
            return 0.0

        # Base score for match existence
        score = 0.5

        # Bonus for multiple matches (diminishing returns)
        match_count = len(matches)
        score += min(0.2, match_count * 0.05)

        # Bonus for matches in signature (first 2 lines)
        lines = content.split("\n")
        if len(lines) >= 2:
            signature_text = "\n".join(lines[:2])
            signature_matches = sum(
                1 for m in matches
                if m.start() < len(signature_text)
            )
            if signature_matches > 0:
                score += 0.2

        # Bonus for high density (matches per line)
        line_count = max(len(lines), 1)
        density = match_count / line_count
        score += min(0.1, density * 10)

        return min(1.0, score)

    def get_available_presets(self) -> List[str]:
        """
        Get list of available pattern presets.

        Returns:
            Sorted list of preset names
        """
        return sorted(PATTERN_PRESETS.keys())

    def get_preset_pattern(self, preset_name: str) -> Optional[str]:
        """
        Get the regex pattern for a preset.

        Args:
            preset_name: Name of the preset

        Returns:
            Regex pattern string or None if preset doesn't exist
        """
        return PATTERN_PRESETS.get(preset_name)

    def clear_cache(self):
        """Clear the pattern compilation cache."""
        self._pattern_cache.clear()
        logger.info("Pattern compilation cache cleared")
