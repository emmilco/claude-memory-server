"""
Importance scorer - integrates complexity, usage, and criticality analyzers.

This is the main entry point for calculating code unit importance scores.
Combines three independent analyzers with configurable weights to produce
final importance scores (0.0-1.0) that rank code by significance.

Scoring Architecture:
1. ComplexityAnalyzer: Base score (0.3-0.7) from code metrics
   - Cyclomatic complexity, line count, nesting, parameters
   - Documentation presence bonus

2. UsageAnalyzer: Boost (+0.0 to +0.2) from usage patterns
   - Call graph centrality, public API, exports, entry points

3. CriticalityAnalyzer: Boost (+0.0 to +0.3) from critical indicators
   - Security keywords, error handling, decorators, file proximity

Final Formula:
    raw_score = (complexity_score * complexity_weight) +
                (usage_boost * usage_weight) +
                (criticality_boost * criticality_weight)

    baseline_max = (0.7 * complexity_weight) +
                   (0.2 * usage_weight) +
                   (0.3 * criticality_weight)

    importance = clamp(raw_score / baseline_max, 0.0, 1.0)

Weight System:
- Default weights: (1.0, 1.0, 1.0) - balanced scoring
- Weight range: 0.0-2.0 per factor
- Higher weight = greater emphasis on that factor
- Independent amplification (not zero-sum)

Presets:
- "balanced": (1.0, 1.0, 1.0) - Equal weights (default)
- "security": (0.8, 0.5, 2.0) - Emphasize security-critical code
- "complexity": (2.0, 0.5, 0.8) - Emphasize complex code
- "api": (1.0, 2.0, 1.0) - Emphasize public APIs

Typical Score Ranges:
- 0.2-0.4: Trivial utilities, getters/setters, constants
- 0.4-0.6: Standard functions, moderate complexity
- 0.6-0.8: Important functions, public APIs, moderate centrality
- 0.8-1.0: Critical functions (auth, crypto, high centrality)

Performance:
- Per-unit calculation: ~1-2ms (dominated by AST parsing)
- Batch optimization: Build call graph once per file
- Memory: O(N) for call graph, cleared between files

Example:
    ```python
    # Basic usage
    scorer = ImportanceScorer()
    score = scorer.calculate_importance(
        code_unit={'name': 'authenticate', 'content': code, 'language': 'python'},
        all_units=[...],  # For call graph
        file_path=Path('src/auth/login.py'),
        file_content=full_file_text
    )
    print(f"Importance: {score.importance:.2f}")  # 0.87
    print(f"Breakdown: complexity={score.complexity_score:.2f}, "
          f"usage={score.usage_boost:.2f}, criticality={score.criticality_boost:.2f}")

    # With preset
    security_scorer = ImportanceScorer.from_preset("security")

    # Batch processing (optimized)
    scores = scorer.calculate_batch(all_units, file_path, file_content)
    stats = scorer.get_summary_statistics(scores)
    print(f"Score distribution: {stats['distribution']}")
    ```

Integration:
- Called by IncrementalIndexer during code indexing
- Replaces fixed importance score of 0.7
- Configurable via ServerConfig importance_*_weight settings
- Error handling: Falls back to 0.5 on calculation failure

Part of FEAT-049: Intelligent Code Importance Scoring
"""

import logging
from typing import Dict, Any, List, Optional
from pathlib import Path
from dataclasses import dataclass

from src.analysis.complexity_analyzer import ComplexityAnalyzer
from src.analysis.usage_analyzer import UsageAnalyzer
from src.analysis.criticality_analyzer import CriticalityAnalyzer

logger = logging.getLogger(__name__)


@dataclass
class ImportanceScore:
    """Container for final importance score and breakdown."""

    importance: float  # Final score (0.0-1.0)
    complexity_score: float  # Base complexity (0.3-0.7)
    usage_boost: float  # Usage boost (0.0-0.2)
    criticality_boost: float  # Criticality boost (0.0-0.3)

    # Individual metrics (for debugging/analysis)
    cyclomatic_complexity: int
    line_count: int
    nesting_depth: int
    parameter_count: int
    has_documentation: bool
    caller_count: int
    is_public: bool
    is_exported: bool
    is_entry_point: bool
    security_keywords: List[str]
    has_error_handling: bool


class ImportanceScorer:
    """
    Calculates importance scores for code units.

    Combines three analyzers:
    1. ComplexityAnalyzer: Base score (0.3-0.7) from complexity metrics
    2. UsageAnalyzer: Boost (0.0-0.2) from usage patterns
    3. CriticalityAnalyzer: Boost (0.0-0.3) from criticality indicators

    Weights are normalized so increasing a weight increases emphasis on that factor.
    Final score = min(1.0, weighted_sum of all factors)
    """

    def __init__(
        self,
        complexity_weight: float = 1.0,
        usage_weight: float = 1.0,
        criticality_weight: float = 1.0,
    ):
        """
        Initialize importance scorer with configurable weights.

        Weights amplify each factor's contribution independently.
        - Weight 1.0 = normal contribution (default behavior)
        - Weight 2.0 = 2x contribution from that factor
        - Weight 0.5 = half contribution from that factor

        Setting criticality_weight=2.0 will amplify security-related scores
        without reducing other factors.

        Args:
            complexity_weight: Multiplier for complexity contribution (0.0-2.0)
            usage_weight: Multiplier for usage contribution (0.0-2.0)
            criticality_weight: Multiplier for criticality contribution (0.0-2.0)
        """
        self.complexity_weight = complexity_weight
        self.usage_weight = usage_weight
        self.criticality_weight = criticality_weight

        self.complexity_analyzer = ComplexityAnalyzer()
        self.usage_analyzer = UsageAnalyzer()
        self.criticality_analyzer = CriticalityAnalyzer()

    @classmethod
    def from_preset(cls, preset_name: str) -> "ImportanceScorer":
        """
        Create scorer with predefined weight preset.

        Available presets:
        - "balanced": Equal weights (1.0, 1.0, 1.0) - default behavior
        - "security": Emphasize criticality (0.8, 0.5, 2.0)
        - "complexity": Emphasize code complexity (2.0, 0.5, 0.8)
        - "api": Emphasize public API usage (1.0, 2.0, 1.0)

        Args:
            preset_name: Name of the preset configuration

        Returns:
            ImportanceScorer configured with preset weights

        Raises:
            ValueError: If preset_name is not recognized
        """
        presets = {
            "balanced": (1.0, 1.0, 1.0),
            "security": (0.8, 0.5, 2.0),
            "complexity": (2.0, 0.5, 0.8),
            "api": (1.0, 2.0, 1.0),
        }

        if preset_name not in presets:
            available = ", ".join(presets.keys())
            raise ValueError(
                f"Unknown preset: '{preset_name}'. "
                f"Available presets: {available}"
            )

        weights = presets[preset_name]
        return cls(
            complexity_weight=weights[0],
            usage_weight=weights[1],
            criticality_weight=weights[2],
        )

    def calculate_importance(
        self,
        code_unit: Dict[str, Any],
        all_units: Optional[List[Dict[str, Any]]] = None,
        file_path: Optional[Path] = None,
        file_content: Optional[str] = None,
    ) -> ImportanceScore:
        """
        Calculate importance score for a code unit.

        Args:
            code_unit: Dictionary with keys:
                - name: Function/class name
                - content: Full code content
                - signature: Function/class signature
                - unit_type: "function", "class", or "method"
                - language: Programming language
            all_units: List of all code units in the file (for call graph)
            file_path: Path to the file (for proximity scoring)
            file_content: Full file content (for export detection)

        Returns:
            ImportanceScore with final score and breakdown
        """
        try:
            # Run all analyzers
            complexity_metrics = self.complexity_analyzer.analyze(code_unit)
            usage_metrics = self.usage_analyzer.analyze(code_unit, all_units, file_content, file_path)
            criticality_metrics = self.criticality_analyzer.analyze(code_unit, file_path)

            # Apply weights directly to amplify each factor's contribution
            # Higher weight = larger contribution from that factor
            # With default weights (1.0, 1.0, 1.0), this matches original additive behavior
            weighted_complexity = complexity_metrics.complexity_score * self.complexity_weight
            weighted_usage = usage_metrics.usage_boost * self.usage_weight
            weighted_criticality = criticality_metrics.criticality_boost * self.criticality_weight

            # Sum weighted contributions
            raw_score = weighted_complexity + weighted_usage + weighted_criticality

            # Normalize to 0.0-1.0 range
            # With default weights (1.0, 1.0, 1.0):
            #   - Min possible: 0.3 + 0.0 + 0.0 = 0.3
            #   - Max possible: 0.7 + 0.2 + 0.3 = 1.2
            # With custom weights, range expands/contracts proportionally
            #
            # Calculate dynamic baseline_max based on actual weights
            # baseline_max = (max_complexity * complexity_weight) +
            #                (max_usage * usage_weight) +
            #                (max_criticality * criticality_weight)
            baseline_max = (0.7 * self.complexity_weight) + \
                          (0.2 * self.usage_weight) + \
                          (0.3 * self.criticality_weight)

            # Handle edge case: if all weights are 0, baseline_max = 0
            # In this case, return 0.0 to avoid division by zero
            if baseline_max == 0.0:
                final_score = 0.0
            else:
                final_score = raw_score / baseline_max

            # Ensure within valid range (0.0-1.0)
            final_score = max(0.0, min(1.0, final_score))

            return ImportanceScore(
                importance=final_score,
                complexity_score=complexity_metrics.complexity_score,
                usage_boost=usage_metrics.usage_boost,
                criticality_boost=criticality_metrics.criticality_boost,
                cyclomatic_complexity=complexity_metrics.cyclomatic_complexity,
                line_count=complexity_metrics.line_count,
                nesting_depth=complexity_metrics.nesting_depth,
                parameter_count=complexity_metrics.parameter_count,
                has_documentation=complexity_metrics.has_documentation,
                caller_count=usage_metrics.caller_count,
                is_public=usage_metrics.is_public,
                is_exported=usage_metrics.is_exported,
                is_entry_point=usage_metrics.is_entry_point,
                security_keywords=criticality_metrics.security_keywords,
                has_error_handling=criticality_metrics.has_error_handling,
            )

        except Exception as e:
            logger.warning(f"Error calculating importance for {code_unit.get('name', 'unknown')}: {e}")
            # Return default mid-range score on error
            return ImportanceScore(
                importance=0.5,
                complexity_score=0.5,
                usage_boost=0.0,
                criticality_boost=0.0,
                cyclomatic_complexity=0,
                line_count=0,
                nesting_depth=0,
                parameter_count=0,
                has_documentation=False,
                caller_count=0,
                is_public=True,
                is_exported=False,
                is_entry_point=False,
                security_keywords=[],
                has_error_handling=False,
            )

    def calculate_batch(
        self,
        code_units: List[Dict[str, Any]],
        file_path: Optional[Path] = None,
        file_content: Optional[str] = None,
    ) -> List[ImportanceScore]:
        """
        Calculate importance scores for multiple code units (optimized).

        This is more efficient than calling calculate_importance repeatedly
        because it builds the call graph once for all units.

        Args:
            code_units: List of code unit dictionaries
            file_path: Path to the file
            file_content: Full file content

        Returns:
            List of ImportanceScore objects (same order as input)
        """
        if not code_units:
            return []

        # Build call graph once for all units
        if len(code_units) > 1:
            language = code_units[0].get("language", "python")
            self.usage_analyzer._build_call_graph(code_units, language)

        # Calculate importance for each unit
        scores = []
        for unit in code_units:
            score = self.calculate_importance(unit, code_units, file_path, file_content)
            scores.append(score)

        # Reset call graph for next file
        self.usage_analyzer.reset()

        return scores

    def get_summary_statistics(self, scores: List[ImportanceScore]) -> Dict[str, Any]:
        """
        Generate summary statistics for a list of importance scores.

        Useful for validation and debugging.

        Args:
            scores: List of ImportanceScore objects

        Returns:
            Dictionary with statistics:
                - mean, median, min, max
                - distribution (count in each range)
                - top features (most complex, most used, most critical)
        """
        if not scores:
            return {}

        importances = [s.importance for s in scores]

        # Basic statistics (guard against division by zero)
        mean = sum(importances) / len(importances) if importances else 0.0
        sorted_scores = sorted(importances)

        # Calculate median: average of middle two for even-length lists
        n = len(sorted_scores)
        if n % 2 == 1:
            median = sorted_scores[n // 2]
        else:
            median = (sorted_scores[n // 2 - 1] + sorted_scores[n // 2]) / 2

        min_score = min(importances)
        max_score = max(importances)

        # Distribution
        distribution = {
            "0.0-0.3": sum(1 for s in importances if s < 0.3),
            "0.3-0.5": sum(1 for s in importances if 0.3 <= s < 0.5),
            "0.5-0.7": sum(1 for s in importances if 0.5 <= s < 0.7),
            "0.7-0.9": sum(1 for s in importances if 0.7 <= s < 0.9),
            "0.9-1.0": sum(1 for s in importances if s >= 0.9),
        }

        # Top features
        top_complex = max(scores, key=lambda s: s.cyclomatic_complexity)
        top_used = max(scores, key=lambda s: s.caller_count)
        top_critical = max(scores, key=lambda s: len(s.security_keywords))

        return {
            "count": len(scores),
            "mean": round(mean, 3),
            "median": round(median, 3),
            "min": round(min_score, 3),
            "max": round(max_score, 3),
            "distribution": distribution,
            "top_complex_cyclomatic": top_complex.cyclomatic_complexity,
            "top_used_callers": top_used.caller_count,
            "top_critical_keywords": len(top_critical.security_keywords),
        }
