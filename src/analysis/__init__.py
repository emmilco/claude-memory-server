"""
Code analysis modules for importance scoring and quality metrics.

This package provides a comprehensive suite of analyzers for evaluating
code significance, quality, and duplication. Used by the incremental
indexer to assign meaningful importance scores to indexed code units.

Module Architecture:

Core Analyzers (FEAT-049):
- complexity_analyzer: Calculates cyclomatic complexity, nesting, line count
- usage_analyzer: Builds call graphs, detects public APIs and exports
- criticality_analyzer: Identifies security keywords, error handling patterns
- importance_scorer: Integrates all analyzers with configurable weights

Quality Analysis (FEAT-060):
- quality_analyzer: Calculates maintainability index, detects quality hotspots
- code_duplicate_detector: Detects semantic code duplication using embeddings

Dependency Flow:
    importance_scorer
    ├── complexity_analyzer (no dependencies)
    ├── usage_analyzer (no dependencies)
    └── criticality_analyzer (no dependencies)

    quality_analyzer
    ├── complexity_analyzer (reused)
    └── code_duplicate_detector (requires embeddings)

Typical Usage:
    ```python
    from src.analysis import ImportanceScorer, QualityAnalyzer

    # Calculate importance for code units
    scorer = ImportanceScorer.from_preset("balanced")
    importance = scorer.calculate_importance(code_unit, all_units, file_path, file_content)

    # Analyze code quality
    quality_analyzer = QualityAnalyzer()
    quality_metrics = quality_analyzer.calculate_quality_metrics(code_unit, duplication_score=0.0)
    hotspots = quality_analyzer.analyze_for_hotspots(code_unit, quality_metrics)
    ```

Configuration:
- Importance weights: ServerConfig.importance_*_weight (0.0-2.0)
- Quality thresholds: QualityAnalyzer constructor parameters
- Duplicate threshold: CodeDuplicateDetector(threshold=0.85)

Related Documentation:
- FEAT-049: Intelligent Code Importance Scoring
- FEAT-060: Code Quality Metrics & Hotspots
- See individual module docstrings for detailed API documentation
"""

from src.analysis.complexity_analyzer import ComplexityAnalyzer
from src.analysis.usage_analyzer import UsageAnalyzer
from src.analysis.criticality_analyzer import CriticalityAnalyzer
from src.analysis.importance_scorer import ImportanceScorer
from src.analysis.code_duplicate_detector import (
    CodeDuplicateDetector,
    DuplicateCluster,
    DuplicatePair,
)

__all__ = [
    "ComplexityAnalyzer",
    "UsageAnalyzer",
    "CriticalityAnalyzer",
    "ImportanceScorer",
    "CodeDuplicateDetector",
    "DuplicateCluster",
    "DuplicatePair",
]
