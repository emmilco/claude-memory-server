"""
Code analysis modules for importance scoring.

This package provides analyzers for calculating code unit importance based on:
- Complexity metrics (cyclomatic complexity, lines, nesting)
- Usage patterns (call graph centrality, public/private API)
- Criticality indicators (security keywords, error handling)
- Code duplication detection (semantic similarity)
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
