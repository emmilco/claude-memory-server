"""Tests for pattern matcher in code search."""

import pytest
import re

from src.search.pattern_matcher import PatternMatcher, MatchLocation, PATTERN_PRESETS
from src.core.exceptions import ValidationError


class TestPatternCompilation:
    """Test pattern compilation and caching."""

    def test_compile_basic_pattern(self):
        """Test basic pattern compilation."""
        matcher = PatternMatcher()
        pattern = matcher.compile_pattern(r"except\s*:")
        assert isinstance(pattern, re.Pattern)

    def test_compile_pattern_cache(self):
        """Test that patterns are cached."""
        matcher = PatternMatcher()
        p1 = matcher.compile_pattern(r"test")
        p2 = matcher.compile_pattern(r"test")
        assert p1 is p2  # Same object from cache

    def test_compile_invalid_pattern(self):
        """Test that invalid patterns raise ValidationError."""
        matcher = PatternMatcher()
        with pytest.raises(ValidationError, match="Invalid regex pattern"):
            matcher.compile_pattern(r"(?P<invalid")

    def test_compile_preset_pattern(self):
        """Test preset pattern resolution."""
        matcher = PatternMatcher()
        pattern = matcher.compile_pattern("@preset:bare_except")
        assert isinstance(pattern, re.Pattern)
        # Verify it compiles to the expected pattern
        assert pattern.pattern == PATTERN_PRESETS["bare_except"]

    def test_compile_unknown_preset(self):
        """Test that unknown preset raises ValidationError."""
        matcher = PatternMatcher()
        with pytest.raises(ValidationError, match="Unknown pattern preset"):
            matcher.compile_pattern("@preset:nonexistent")

    def test_compile_preset_cached_with_name(self):
        """Test that preset patterns are cached with @preset:name as key."""
        matcher = PatternMatcher()
        p1 = matcher.compile_pattern("@preset:bare_except")
        p2 = matcher.compile_pattern("@preset:bare_except")
        assert p1 is p2  # Same object from cache


class TestPatternMatching:
    """Test pattern matching functionality."""

    def test_match_simple_pattern(self):
        """Test simple pattern matching."""
        matcher = PatternMatcher()
        content = "try:\n    pass\nexcept:\n    log()"
        assert matcher.match(r"except:", content)

    def test_match_no_match(self):
        """Test pattern that doesn't match."""
        matcher = PatternMatcher()
        content = "def foo():\n    return True"
        assert not matcher.match(r"except:", content)

    def test_match_complex_pattern(self):
        """Test complex regex pattern."""
        matcher = PatternMatcher()
        content = "TODO: Fix this later\nFIXME: Urgent issue"
        assert matcher.match(r"(TODO|FIXME):", content)

    def test_match_preset_pattern(self):
        """Test matching with preset pattern."""
        matcher = PatternMatcher()
        content = "password = 'secret123'\napi_key = 'xyz'"
        assert matcher.match("@preset:security_keywords", content)

    def test_find_matches_single(self):
        """Test finding single match."""
        matcher = PatternMatcher()
        content = "except:\n    pass"
        matches = matcher.find_matches(r"except:", content)
        assert len(matches) == 1
        assert matches[0].group(0) == "except:"

    def test_find_matches_multiple(self):
        """Test finding multiple matches."""
        matcher = PatternMatcher()
        content = "except:\n    pass\nexcept Error:\n    log()\nexcept:\n    raise"
        matches = matcher.find_matches(r"except:", content)
        assert len(matches) == 2  # Only bare except blocks

    def test_find_matches_none(self):
        """Test finding no matches."""
        matcher = PatternMatcher()
        content = "def foo():\n    return True"
        matches = matcher.find_matches(r"except:", content)
        assert len(matches) == 0

    def test_get_match_count(self):
        """Test match counting."""
        matcher = PatternMatcher()
        content = "TODO: Fix\nFIXME: Bug\nHACK: Workaround"
        count = matcher.get_match_count(r"(TODO|FIXME|HACK):", content)
        assert count == 3


class TestMatchLocations:
    """Test match location tracking."""

    def test_get_match_locations_single(self):
        """Test getting single match location."""
        matcher = PatternMatcher()
        content = "try:\n    pass\nexcept:\n    log()"
        locations = matcher.get_match_locations(r"except:", content)

        assert len(locations) == 1
        assert isinstance(locations[0], MatchLocation)
        assert locations[0].line == 3  # Line 3 (0-indexed)
        assert locations[0].text == "except:"

    def test_get_match_locations_multiple(self):
        """Test getting multiple match locations."""
        matcher = PatternMatcher()
        content = "TODO: First\nSome code\nFIXME: Second\nMore code\nHACK: Third"
        locations = matcher.get_match_locations(r"(TODO|FIXME|HACK):", content)

        assert len(locations) == 3
        assert locations[0].text == "TODO:"
        assert locations[1].text == "FIXME:"
        assert locations[2].text == "HACK:"

    def test_get_match_locations_line_numbers(self):
        """Test that line numbers are correct."""
        matcher = PatternMatcher()
        content = "line 1\nline 2\nexcept:\nline 4"
        locations = matcher.get_match_locations(r"except:", content)

        assert len(locations) == 1
        assert locations[0].line == 3  # Third line (0-indexed)

    def test_get_match_locations_columns(self):
        """Test that column numbers are correct."""
        matcher = PatternMatcher()
        content = "    except:"  # Indented
        locations = matcher.get_match_locations(r"except:", content)

        assert len(locations) == 1
        assert locations[0].column == 4  # After 4 spaces


class TestPatternScoring:
    """Test pattern match quality scoring."""

    def test_pattern_score_no_match(self):
        """Test score is 0.0 for no match."""
        matcher = PatternMatcher()
        content = "def foo():\n    return True"
        score = matcher.calculate_pattern_score(content, r"except:")
        assert score == 0.0

    def test_pattern_score_single_match(self):
        """Test score for single match."""
        matcher = PatternMatcher()
        content = "try:\n    pass\nexcept:\n    log()"
        score = matcher.calculate_pattern_score(content, r"except:")
        assert 0.5 <= score <= 1.0  # Should have base score + bonuses

    def test_pattern_score_multiple_matches(self):
        """Test higher score for multiple matches."""
        matcher = PatternMatcher()
        single_match = "try:\n    pass\nexcept:\n    log()"
        multiple_match = "try:\n    pass\nexcept:\n    log()\nexcept:\n    raise"

        score_single = matcher.calculate_pattern_score(single_match, r"except:")
        score_multiple = matcher.calculate_pattern_score(multiple_match, r"except:")

        assert score_multiple > score_single  # More matches = higher score

    def test_pattern_score_signature_bonus(self):
        """Test bonus for matches in signature (first 2 lines)."""
        matcher = PatternMatcher()
        # Match in signature (line 1)
        sig_match = "async def foo():\n    return True"
        # Match in body (line 3)
        body_match = "def foo():\n    x = 1\n    async with db:\n        pass"

        score_sig = matcher.calculate_pattern_score(sig_match, r"async")
        score_body = matcher.calculate_pattern_score(body_match, r"async")

        assert score_sig >= score_body  # Signature match should score higher or equal

    def test_pattern_score_capped_at_one(self):
        """Test that score is capped at 1.0."""
        matcher = PatternMatcher()
        # Many matches to potentially exceed 1.0
        content = "\n".join(["except:" for _ in range(100)])
        score = matcher.calculate_pattern_score(content, r"except:")
        assert score <= 1.0


class TestPatternPresets:
    """Test pattern preset functionality."""

    def test_get_available_presets(self):
        """Test listing available presets."""
        matcher = PatternMatcher()
        presets = matcher.get_available_presets()

        assert isinstance(presets, list)
        assert len(presets) > 0
        assert "bare_except" in presets
        assert "TODO_comments" in presets
        assert "security_keywords" in presets

    def test_get_available_presets_sorted(self):
        """Test that presets are sorted alphabetically."""
        matcher = PatternMatcher()
        presets = matcher.get_available_presets()
        assert presets == sorted(presets)

    def test_get_preset_pattern(self):
        """Test getting pattern for preset."""
        matcher = PatternMatcher()
        pattern = matcher.get_preset_pattern("bare_except")
        assert pattern == r"except\s*:"

    def test_get_preset_pattern_unknown(self):
        """Test getting pattern for unknown preset returns None."""
        matcher = PatternMatcher()
        pattern = matcher.get_preset_pattern("nonexistent")
        assert pattern is None

    def test_preset_bare_except(self):
        """Test bare_except preset."""
        matcher = PatternMatcher()
        bare = "try:\n    pass\nexcept:\n    log()"
        named = "try:\n    pass\nexcept Exception:\n    log()"

        assert matcher.match("@preset:bare_except", bare)
        assert not matcher.match("@preset:bare_except", named)

    def test_preset_TODO_comments(self):
        """Test TODO_comments preset."""
        matcher = PatternMatcher()
        content = "# TODO: Fix this\n# FIXME: Urgent\n# HACK: Workaround"
        matches = matcher.find_matches("@preset:TODO_comments", content)
        assert len(matches) == 3

    def test_preset_security_keywords(self):
        """Test security_keywords preset."""
        matcher = PatternMatcher()
        content = "password = 'test'\napi_key = 'xyz'\nsecret = 'abc'"
        matches = matcher.find_matches("@preset:security_keywords", content)
        assert len(matches) >= 3  # At least password, api_key, secret

    def test_preset_error_handlers(self):
        """Test error_handlers preset."""
        matcher = PatternMatcher()
        python = "try:\n    pass\nexcept:\n    log()"
        java = "try {\n    code();\n} catch (Exception e) {\n    log();\n}"

        assert matcher.match("@preset:error_handlers", python)
        assert matcher.match("@preset:error_handlers", java)


class TestCacheManagement:
    """Test cache management."""

    def test_clear_cache(self):
        """Test cache clearing."""
        matcher = PatternMatcher()

        # Populate cache
        matcher.compile_pattern(r"test1")
        matcher.compile_pattern(r"test2")
        matcher.compile_pattern("@preset:bare_except")

        assert len(matcher._pattern_cache) > 0

        # Clear cache
        matcher.clear_cache()

        assert len(matcher._pattern_cache) == 0

    def test_cache_after_clear(self):
        """Test that patterns can be compiled after cache clear."""
        matcher = PatternMatcher()

        # Populate and clear
        matcher.compile_pattern(r"test")
        matcher.clear_cache()

        # Should work after clear
        pattern = matcher.compile_pattern(r"test")
        assert isinstance(pattern, re.Pattern)


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_empty_content(self):
        """Test matching against empty content."""
        matcher = PatternMatcher()
        assert not matcher.match(r"test", "")
        assert matcher.get_match_count(r"test", "") == 0

    def test_empty_pattern(self):
        """Test empty pattern (should match everything)."""
        matcher = PatternMatcher()
        # Empty pattern matches empty string in regex
        assert matcher.match(r"", "some content")

    def test_multiline_pattern(self):
        """Test multiline pattern matching."""
        matcher = PatternMatcher()
        content = "def foo():\n    return True"
        # Pattern spanning multiple lines
        assert matcher.match(r"def.*return", content)

    def test_special_regex_chars(self):
        """Test pattern with special regex characters."""
        matcher = PatternMatcher()
        content = "result = foo(bar, baz)"
        # Escaped parentheses
        assert matcher.match(r"foo\(", content)

    def test_case_sensitivity(self):
        """Test that patterns are case-sensitive by default."""
        matcher = PatternMatcher()
        content = "TODO: Fix this"
        assert matcher.match(r"TODO", content)
        assert not matcher.match(r"todo", content)

    def test_very_long_content(self):
        """Test pattern matching on very long content."""
        matcher = PatternMatcher()
        # 10000 lines
        content = "\n".join([f"line {i}" for i in range(10000)])
        content += "\nexcept:\n    pass"

        matches = matcher.find_matches(r"except:", content)
        assert len(matches) == 1

    def test_many_matches(self):
        """Test pattern with many matches."""
        matcher = PatternMatcher()
        # 1000 TODOs
        content = "\n".join(["# TODO: Fix" for _ in range(1000)])
        matches = matcher.find_matches(r"TODO", content)
        assert len(matches) == 1000
