"""
Unit tests for ImportanceScorer (FEAT-049).

Tests importance scoring integration including:
- Combining all three analyzers
- Configurable weights
- Batch processing
- Summary statistics
- Error handling
"""

import pytest
from pathlib import Path
from src.analysis.importance_scorer import ImportanceScorer


@pytest.fixture
def scorer():
    """Create an ImportanceScorer instance with default weights."""
    return ImportanceScorer()


@pytest.fixture
def custom_scorer():
    """Create an ImportanceScorer with custom weights."""
    return ImportanceScorer(
        complexity_weight=0.5,
        usage_weight=1.5,
        criticality_weight=2.0,
    )


class TestBasicScoring:
    """Tests for basic importance scoring."""

    def test_simple_function(self, scorer):
        """Score a simple function."""
        code_unit = {
            "name": "simple_func",
            "content": "def simple_func():\n    return 42",
            "signature": "def simple_func():",
            "unit_type": "function",
            "language": "python",
        }
        score = scorer.calculate_importance(code_unit)
        assert 0.0 <= score.importance <= 1.0
        assert score.complexity_score > 0.0
        assert score.usage_boost >= 0.0
        assert score.criticality_boost >= 0.0

    def test_complex_function(self, scorer):
        """Complex function gets higher score."""
        complex_code = {
            "name": "complex_func",
            "content": """
def complex_func(a, b, c, d, e):
    '''Documentation'''
    if a > 0:
        for i in range(100):
            while i < 50:
                if b > i:
                    try:
                        process()
                    except:
                        handle()
""",
            "signature": "def complex_func(a, b, c, d, e):",
            "unit_type": "function",
            "language": "python",
        }
        simple_code = {
            "name": "simple",
            "content": "def simple():\n    return 1",
            "signature": "def simple():",
            "unit_type": "function",
            "language": "python",
        }
        complex_score = scorer.calculate_importance(complex_code)
        simple_score = scorer.calculate_importance(simple_code)
        assert complex_score.importance > simple_score.importance

    def test_security_function(self, scorer):
        """Security function gets criticality boost."""
        security_code = {
            "name": "authenticate_user",
            "content": """
def authenticate_user(username, password):
    try:
        token = generate_jwt_token(username)
        if verify_credentials(password):
            return token
    except AuthError:
        log_security_event()
""",
            "signature": "def authenticate_user(username, password):",
            "unit_type": "function",
            "language": "python",
        }
        score = scorer.calculate_importance(security_code)
        assert score.criticality_boost > 0.0
        assert len(score.security_keywords) > 0


class TestConfigurableWeights:
    """Tests for configurable weight system."""

    def test_default_weights(self, scorer):
        """Default weights are 1.0."""
        assert scorer.complexity_weight == 1.0
        assert scorer.usage_weight == 1.0
        assert scorer.criticality_weight == 1.0

    def test_custom_weights(self, custom_scorer):
        """Custom weights are applied."""
        assert custom_scorer.complexity_weight == 0.5
        assert custom_scorer.usage_weight == 1.5
        assert custom_scorer.criticality_weight == 2.0

    def test_weight_affects_score(self):
        """Changing weights affects final score."""
        code_unit = {
            "name": "func",
            "content": "def func():\n    if True:\n        return 1",
            "signature": "def func():",
            "unit_type": "function",
            "language": "python",
        }

        scorer_default = ImportanceScorer(1.0, 1.0, 1.0)
        scorer_complexity = ImportanceScorer(2.0, 1.0, 1.0)

        score_default = scorer_default.calculate_importance(code_unit)
        score_complexity = scorer_complexity.calculate_importance(code_unit)

        # Higher complexity weight should increase score
        assert score_complexity.importance >= score_default.importance

    def test_zero_weight(self):
        """Zero weight disables that factor."""
        code_unit = {
            "name": "complex",
            "content": "def complex(a,b,c):\n" + "    if a:\n" * 10 + "        pass",
            "signature": "def complex(a,b,c):",
            "unit_type": "function",
            "language": "python",
        }

        scorer_no_complexity = ImportanceScorer(0.0, 1.0, 1.0)
        score = scorer_no_complexity.calculate_importance(code_unit)

        # With 0 complexity weight, score should be lower
        assert score.importance < 0.7


class TestBatchProcessing:
    """Tests for batch processing."""

    def test_calculate_batch_empty(self, scorer):
        """Batch processing with empty list."""
        scores = scorer.calculate_batch([])
        assert len(scores) == 0

    def test_calculate_batch_single(self, scorer):
        """Batch processing with single unit."""
        units = [
            {
                "name": "func",
                "content": "def func():\n    return 42",
                "signature": "def func():",
                "unit_type": "function",
                "language": "python",
            }
        ]
        scores = scorer.calculate_batch(units)
        assert len(scores) == 1
        assert 0.0 <= scores[0].importance <= 1.0

    def test_calculate_batch_multiple(self, scorer):
        """Batch processing with multiple units."""
        units = [
            {
                "name": f"func{i}",
                "content": f"def func{i}(): return {i}",
                "signature": f"def func{i}():",
                "unit_type": "function",
                "language": "python",
            }
            for i in range(5)
        ]
        scores = scorer.calculate_batch(units)
        assert len(scores) == 5
        for score in scores:
            assert 0.0 <= score.importance <= 1.0

    def test_batch_builds_call_graph(self, scorer):
        """Batch processing builds call graph for usage analysis."""
        units = [
            {
                "name": "caller",
                "content": "def caller():\n    return callee()",
                "signature": "def caller():",
                "unit_type": "function",
                "language": "python",
            },
            {
                "name": "callee",
                "content": "def callee():\n    return 42",
                "signature": "def callee():",
                "unit_type": "function",
                "language": "python",
            },
        ]
        scores = scorer.calculate_batch(units)

        # Callee should have higher usage boost (it's called)
        callee_score = scores[1]
        assert callee_score.caller_count >= 1

    def test_batch_resets_call_graph(self, scorer):
        """Batch processing resets call graph between calls."""
        units1 = [
            {
                "name": "func1",
                "content": "def func1(): return func2()",
                "signature": "def func1():",
                "unit_type": "function",
                "language": "python",
            },
            {
                "name": "func2",
                "content": "def func2(): return 1",
                "signature": "def func2():",
                "unit_type": "function",
                "language": "python",
            },
        ]
        units2 = [
            {
                "name": "func3",
                "content": "def func3(): return 3",
                "signature": "def func3():",
                "unit_type": "function",
                "language": "python",
            },
        ]

        scorer.calculate_batch(units1)
        scores2 = scorer.calculate_batch(units2)

        # func3 should not be affected by previous call graph
        assert scores2[0].caller_count == 0


class TestSummaryStatistics:
    """Tests for summary statistics generation."""

    def test_summary_empty_list(self, scorer):
        """Summary statistics for empty list."""
        stats = scorer.get_summary_statistics([])
        assert stats == {}

    def test_summary_basic_stats(self, scorer):
        """Summary includes basic statistics."""
        units = [
            {
                "name": f"func{i}",
                "content": f"def func{i}(): return {i}",
                "signature": f"def func{i}():",
                "unit_type": "function",
                "language": "python",
            }
            for i in range(10)
        ]
        scores = scorer.calculate_batch(units)
        stats = scorer.get_summary_statistics(scores)

        assert "count" in stats
        assert "mean" in stats
        assert "median" in stats
        assert "min" in stats
        assert "max" in stats
        assert stats["count"] == 10

    def test_summary_distribution(self, scorer):
        """Summary includes distribution."""
        units = [
            {
                "name": f"func{i}",
                "content": f"def func{i}(): return {i}",
                "signature": f"def func{i}():",
                "unit_type": "function",
                "language": "python",
            }
            for i in range(10)
        ]
        scores = scorer.calculate_batch(units)
        stats = scorer.get_summary_statistics(scores)

        assert "distribution" in stats
        dist = stats["distribution"]
        assert "0.0-0.3" in dist
        assert "0.3-0.5" in dist
        assert "0.5-0.7" in dist
        assert "0.7-0.9" in dist
        assert "0.9-1.0" in dist

        # Sum of distribution should equal count
        assert sum(dist.values()) == 10

    def test_summary_top_features(self, scorer):
        """Summary includes top features."""
        units = [
            {
                "name": "complex",
                "content": "def complex(a,b,c,d,e):\n"
                + "    if a:\n" * 20
                + "        pass",
                "signature": "def complex(a,b,c,d,e):",
                "unit_type": "function",
                "language": "python",
            },
            {
                "name": "simple",
                "content": "def simple(): return 1",
                "signature": "def simple():",
                "unit_type": "function",
                "language": "python",
            },
        ]
        scores = scorer.calculate_batch(units)
        stats = scorer.get_summary_statistics(scores)

        assert "top_complex_cyclomatic" in stats
        assert "top_used_callers" in stats
        assert "top_critical_keywords" in stats


class TestScoreBreakdown:
    """Tests for score breakdown and components."""

    def test_score_has_all_components(self, scorer):
        """Score object includes all component scores."""
        code_unit = {
            "name": "func",
            "content": "def func(): return 1",
            "signature": "def func():",
            "unit_type": "function",
            "language": "python",
        }
        score = scorer.calculate_importance(code_unit)

        assert hasattr(score, "importance")
        assert hasattr(score, "complexity_score")
        assert hasattr(score, "usage_boost")
        assert hasattr(score, "criticality_boost")
        assert hasattr(score, "cyclomatic_complexity")
        assert hasattr(score, "line_count")
        assert hasattr(score, "nesting_depth")
        assert hasattr(score, "parameter_count")
        assert hasattr(score, "has_documentation")
        assert hasattr(score, "caller_count")
        assert hasattr(score, "is_public")
        assert hasattr(score, "is_exported")
        assert hasattr(score, "security_keywords")
        assert hasattr(score, "has_error_handling")

    def test_score_calculation_formula(self, scorer):
        """Final score is sum of weighted components divided by baseline max (1.2)."""
        code_unit = {
            "name": "func",
            "content": "def func(): return 1",
            "signature": "def func():",
            "unit_type": "function",
            "language": "python",
        }
        score = scorer.calculate_importance(code_unit)

        # Manual calculation with new normalization formula
        # With default weights (1.0, 1.0, 1.0), raw score is summed then divided by 1.2
        raw_score = score.complexity_score + score.usage_boost + score.criticality_boost
        expected = min(1.0, raw_score / 1.2)  # Normalize by baseline max

        assert (
            abs(score.importance - expected) < 0.01
        )  # Allow small floating point error


class TestErrorHandling:
    """Tests for error handling and edge cases."""

    def test_missing_fields(self, scorer):
        """Missing fields in code unit are handled gracefully."""
        code_unit = {
            "name": "func",
            # Missing content, signature, etc.
        }
        score = scorer.calculate_importance(code_unit)
        # Should return default/fallback score
        assert 0.0 <= score.importance <= 1.0

    def test_error_returns_default_score(self, scorer):
        """Errors return default mid-range score (0.5)."""
        # Create a code unit that might cause issues
        code_unit = {
            "name": None,  # Invalid name
            "content": None,  # Invalid content
            "signature": None,
            "unit_type": "function",
            "language": "python",
        }
        score = scorer.calculate_importance(code_unit)
        assert score.importance == 0.5  # Default fallback

    def test_very_large_complexity(self, scorer):
        """Very large complexity values are handled."""
        code_unit = {
            "name": "huge",
            "content": "def huge():\n" + "    if True:\n" * 1000 + "        pass",
            "signature": "def huge():",
            "unit_type": "function",
            "language": "python",
        }
        score = scorer.calculate_importance(code_unit)
        # Should be capped at 1.0
        assert score.importance <= 1.0

    def test_score_never_exceeds_one(self, scorer):
        """Score is always capped at 1.0, even with high weights."""
        scorer_high = ImportanceScorer(10.0, 10.0, 10.0)
        code_unit = {
            "name": "func",
            "content": "def func(): return 1",
            "signature": "def func():",
            "unit_type": "function",
            "language": "python",
        }
        score = scorer_high.calculate_importance(code_unit)
        assert score.importance <= 1.0

    def test_score_never_below_zero(self, scorer):
        """Score is always at least 0.0."""
        scorer_zero = ImportanceScorer(0.0, 0.0, 0.0)
        code_unit = {
            "name": "func",
            "content": "def func(): return 1",
            "signature": "def func():",
            "unit_type": "function",
            "language": "python",
        }
        score = scorer_zero.calculate_importance(code_unit)
        assert score.importance >= 0.0


class TestIntegrationScenarios:
    """Integration tests for realistic scenarios."""

    def test_typical_project_distribution(self, scorer):
        """Typical project should have varied distribution."""
        units = [
            # Simple utilities (should score low)
            {
                "name": "get_name",
                "content": "def get_name(): return self.name",
                "signature": "def get_name():",
                "unit_type": "function",
                "language": "python",
            },
            {
                "name": "is_empty",
                "content": "def is_empty(x): return len(x) == 0",
                "signature": "def is_empty(x):",
                "unit_type": "function",
                "language": "python",
            },
            # Moderate complexity (should score mid)
            {
                "name": "process",
                "content": "def process(data):\n    if data:\n        for item in data:\n            yield item",
                "signature": "def process(data):",
                "unit_type": "function",
                "language": "python",
            },
            # High complexity + security (should score high)
            {
                "name": "auth",
                "content": "def authenticate(user, password):\n    try:\n        if verify_password(password):\n            return generate_token(user)\n    except AuthError:\n        log_error()\n        raise",
                "signature": "def authenticate(user, password):",
                "unit_type": "function",
                "language": "python",
            },
        ]

        scores = scorer.calculate_batch(units)
        importances = [s.importance for s in scores]

        # Should have variety
        assert max(importances) > min(importances)

        # Auth function should score highest
        assert scores[3].importance > scores[0].importance


class TestFilesystemIntegration:
    """Tests with file paths and file content."""

    def test_with_file_path(self, scorer):
        """Score with file path for proximity."""
        code_unit = {
            "name": "main",
            "content": "def main(): pass",
            "signature": "def main():",
            "unit_type": "function",
            "language": "python",
        }
        file_path = Path("/project/main.py")

        score = scorer.calculate_importance(code_unit, file_path=file_path)
        # Main function in main.py should get proximity boost
        assert score.criticality_boost > 0.0

    def test_with_file_content(self, scorer):
        """Score with file content for export detection."""
        code_unit = {
            "name": "exported_func",
            "content": "def exported_func(): return 42",
            "signature": "def exported_func():",
            "unit_type": "function",
            "language": "python",
        }
        file_content = "__all__ = ['exported_func']\n\ndef exported_func(): return 42"

        score = scorer.calculate_importance(code_unit, file_content=file_content)
        assert score.is_exported is True


class TestEntryPointDetection:
    """Tests for entry point file detection."""

    def test_entry_point_boost(self, scorer):
        """Entry point files receive usage boost."""
        code_unit = {
            "name": "handler",
            "content": "def handler(): pass",
            "signature": "def handler():",
            "unit_type": "function",
            "language": "python",
        }

        # Non-entry point file
        score1 = scorer.calculate_importance(
            code_unit, file_path=Path("src/utils/helpers.py")
        )

        # Entry point file (api directory)
        score2 = scorer.calculate_importance(
            code_unit, file_path=Path("src/api/handlers.py")
        )

        # Entry point should have higher score
        assert score2.is_entry_point
        assert not score1.is_entry_point
        assert score2.usage_boost > score1.usage_boost
        assert score2.importance > score1.importance


class TestScoringPresets:
    """Tests for scoring presets."""

    def test_from_preset_balanced(self):
        """Balanced preset creates scorer with equal weights."""
        scorer = ImportanceScorer.from_preset("balanced")
        assert scorer.complexity_weight == 1.0
        assert scorer.usage_weight == 1.0
        assert scorer.criticality_weight == 1.0

    def test_from_preset_security(self):
        """Security preset emphasizes criticality."""
        scorer = ImportanceScorer.from_preset("security")
        assert scorer.complexity_weight == 0.8
        assert scorer.usage_weight == 0.5
        assert scorer.criticality_weight == 2.0

    def test_from_preset_complexity(self):
        """Complexity preset emphasizes code complexity."""
        scorer = ImportanceScorer.from_preset("complexity")
        assert scorer.complexity_weight == 2.0
        assert scorer.usage_weight == 0.5
        assert scorer.criticality_weight == 0.8

    def test_from_preset_api(self):
        """API preset emphasizes usage patterns."""
        scorer = ImportanceScorer.from_preset("api")
        assert scorer.complexity_weight == 1.0
        assert scorer.usage_weight == 2.0
        assert scorer.criticality_weight == 1.0

    def test_from_preset_unknown(self):
        """Unknown preset raises ValueError."""
        with pytest.raises(ValueError, match="Unknown preset"):
            ImportanceScorer.from_preset("nonexistent")

    def test_preset_affects_scoring(self):
        """Security preset increases scores for security functions."""
        security_func = {
            "name": "authenticate",
            "content": "def authenticate(password): return validate(password)",
            "signature": "def authenticate(password):",
            "unit_type": "function",
            "language": "python",
        }

        # Compare balanced vs security preset
        balanced = ImportanceScorer.from_preset("balanced")
        security = ImportanceScorer.from_preset("security")

        score_balanced = balanced.calculate_importance(
            security_func, file_path=Path("src/auth.py")
        )
        score_security = security.calculate_importance(
            security_func, file_path=Path("src/auth.py")
        )

        # Security preset should increase score for functions with security keywords
        # (if the function has any criticality boost)
        if score_balanced.criticality_boost > 0:
            assert score_security.importance > score_balanced.importance
