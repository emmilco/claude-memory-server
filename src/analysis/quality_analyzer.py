"""
Quality analyzer for code quality metrics and hotspot detection.

Provides comprehensive code quality analysis including:
- Maintainability index calculation
- Quality flag detection (high complexity, long functions, etc.)
- Integration with complexity and duplication analysis
- Quality hotspot detection

Part of FEAT-060: Code Quality Metrics & Hotspots
"""

import logging
import math
from typing import Dict, Any, List, Optional, Tuple, Literal
from dataclasses import dataclass
from enum import Enum

from src.analysis.complexity_analyzer import ComplexityAnalyzer, ComplexityMetrics
from src.config import get_config

logger = logging.getLogger(__name__)


class QualitySeverity(str, Enum):
    """Quality issue severity levels."""
    CRITICAL = "critical"  # Requires immediate attention
    HIGH = "high"          # Should be addressed soon
    MEDIUM = "medium"      # Should be monitored
    LOW = "low"            # Nice to fix


class QualityCategory(str, Enum):
    """Quality issue categories."""
    COMPLEXITY = "complexity"
    DUPLICATION = "duplication"
    LENGTH = "length"
    NESTING = "nesting"
    DOCUMENTATION = "documentation"
    PARAMETERS = "parameters"


@dataclass
class CodeQualityMetrics:
    """
    Quality metrics for a code unit.

    Extended from ComplexityMetrics with additional quality indicators.
    """
    # Base complexity metrics
    cyclomatic_complexity: int
    line_count: int
    nesting_depth: int
    parameter_count: int
    has_documentation: bool

    # Quality scores
    duplication_score: float  # 0-1, similarity to closest duplicate
    maintainability_index: int  # 0-100, Microsoft formula

    # Quality flags
    quality_flags: List[str]  # ["high_complexity", "long_function", etc.]


@dataclass
class QualityHotspot:
    """
    A code quality issue requiring attention.

    Represents a specific quality problem with metadata for prioritization
    and actionable recommendations.
    """
    severity: QualitySeverity
    category: QualityCategory
    file_path: str
    unit_name: str
    start_line: int
    end_line: int
    metric_value: float  # The actual metric (complexity=15, similarity=0.92, etc.)
    threshold: float  # The threshold exceeded
    recommendation: str  # Specific refactoring suggestion

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "severity": self.severity.value,
            "category": self.category.value,
            "file_path": self.file_path,
            "unit_name": self.unit_name,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "metric_value": self.metric_value,
            "threshold": self.threshold,
            "recommendation": self.recommendation,
        }


class QualityAnalyzer:
    """
    Analyzes code quality and generates quality metrics.

    Integrates complexity analysis, duplication detection, and quality scoring
    to provide comprehensive quality assessment.
    """

    # Default thresholds (used if config not available)
    COMPLEXITY_HIGH = 10
    COMPLEXITY_CRITICAL = 20
    LONG_FUNCTION_LINES = 100
    DEEP_NESTING = 4
    MANY_PARAMETERS = 5

    # Maintainability index thresholds
    MI_EXCELLENT = 85
    MI_GOOD = 65
    MI_POOR = 50

    def __init__(
        self,
        complexity_analyzer: Optional[ComplexityAnalyzer] = None,
        complexity_high: Optional[int] = None,
        complexity_critical: Optional[int] = None,
        long_function_lines: Optional[int] = None,
        deep_nesting: Optional[int] = None,
        many_parameters: Optional[int] = None,
    ):
        """
        Initialize quality analyzer.

        Args:
            complexity_analyzer: Optional analyzer (creates default if None)
            complexity_high: Threshold for high complexity warning (uses config if None)
            complexity_critical: Threshold for critical complexity alert (uses config if None)
            long_function_lines: Threshold for long function warning (uses config if None)
            deep_nesting: Threshold for deep nesting warning (uses config if None)
            many_parameters: Threshold for parameter count warning (uses config if None)
        """
        # Load defaults from config (REF-021)
        config = get_config()
        self.complexity_high = complexity_high if complexity_high is not None else config.quality.complexity_high
        self.complexity_critical = complexity_critical if complexity_critical is not None else config.quality.complexity_critical
        self.long_function_lines = long_function_lines if long_function_lines is not None else config.quality.long_function_lines
        self.deep_nesting = deep_nesting if deep_nesting is not None else config.quality.deep_nesting
        self.many_parameters = many_parameters if many_parameters is not None else config.quality.many_parameters
        self.mi_excellent = config.quality.maintainability_excellent
        self.mi_good = config.quality.maintainability_good
        self.mi_poor = config.quality.maintainability_poor

        self.complexity_analyzer = complexity_analyzer or ComplexityAnalyzer()

        logger.info(
            f"QualityAnalyzer initialized (complexity_high={self.complexity_high}, "
            f"complexity_critical={self.complexity_critical}, long_function_lines={self.long_function_lines}) (REF-021)"
        )

    def calculate_quality_metrics(
        self,
        code_unit: Dict[str, Any],
        duplication_score: float = 0.0,
    ) -> CodeQualityMetrics:
        """
        Calculate comprehensive quality metrics for a code unit.

        Args:
            code_unit: Dictionary with code content and metadata
            duplication_score: Pre-calculated duplication score (0-1)

        Returns:
            CodeQualityMetrics with all quality indicators
        """
        # Calculate base complexity metrics
        complexity_metrics = self.complexity_analyzer.analyze(code_unit)

        # Calculate maintainability index
        mi = self.calculate_maintainability_index(
            complexity_metrics.cyclomatic_complexity,
            complexity_metrics.line_count,
            complexity_metrics.has_documentation,
        )

        # Determine quality flags
        quality_flags = self._determine_quality_flags(
            complexity_metrics, duplication_score
        )

        return CodeQualityMetrics(
            cyclomatic_complexity=complexity_metrics.cyclomatic_complexity,
            line_count=complexity_metrics.line_count,
            nesting_depth=complexity_metrics.nesting_depth,
            parameter_count=complexity_metrics.parameter_count,
            has_documentation=complexity_metrics.has_documentation,
            duplication_score=duplication_score,
            maintainability_index=mi,
            quality_flags=quality_flags,
        )

    def calculate_maintainability_index(
        self,
        cyclomatic_complexity: int,
        line_count: int,
        has_documentation: bool = False,
    ) -> int:
        """
        Calculate Microsoft Maintainability Index (0-100).

        Uses simplified formula based on cyclomatic complexity and line count.
        Full formula: MI = max(0, (171 - 5.2 * ln(V) - 0.23 * G - 16.2 * ln(L)) * 100 / 171)

        Simplified approximation (good enough for ranking):
        MI = 100 - (G * 2) - (L / 10) + documentation_bonus

        Where:
        - G = Cyclomatic Complexity
        - L = Lines of Code

        Args:
            cyclomatic_complexity: Cyclomatic complexity score
            line_count: Number of code lines
            has_documentation: Whether the code has documentation

        Returns:
            Maintainability index (0-100)
            - 85-100: Highly maintainable (green)
            - 65-84: Moderately maintainable (yellow)
            - <65: Difficult to maintain (red)
        """
        # Simplified formula
        mi = 100 - (cyclomatic_complexity * 2) - (line_count / 10)

        # Documentation bonus (well-documented code is more maintainable)
        if has_documentation:
            mi += 5

        # Clamp to 0-100 range
        return max(0, min(100, int(mi)))

    def classify_complexity(
        self,
        complexity: int,
    ) -> Tuple[QualitySeverity, str]:
        """
        Classify cyclomatic complexity into severity levels.

        Args:
            complexity: Cyclomatic complexity score

        Returns:
            Tuple of (severity, description)
        """
        if complexity <= 5:
            return QualitySeverity.LOW, "Simple function, easy to maintain"
        elif complexity <= self.complexity_high:
            return QualitySeverity.MEDIUM, "Moderate complexity, acceptable"
        elif complexity <= self.complexity_critical:
            return QualitySeverity.HIGH, "Complex, consider refactoring"
        else:
            return QualitySeverity.CRITICAL, "Very complex, refactor immediately"

    def classify_maintainability(
        self,
        mi: int,
    ) -> Tuple[QualitySeverity, str]:
        """
        Classify maintainability index into severity levels.

        Args:
            mi: Maintainability index (0-100)

        Returns:
            Tuple of (severity, description)
        """
        if mi >= self.mi_excellent:
            return QualitySeverity.LOW, "Highly maintainable"
        elif mi >= self.mi_good:
            return QualitySeverity.MEDIUM, "Moderately maintainable"
        elif mi >= self.mi_poor:
            return QualitySeverity.HIGH, "Difficult to maintain"
        else:
            return QualitySeverity.CRITICAL, "Very difficult to maintain"

    def create_quality_hotspot(
        self,
        category: QualityCategory,
        severity: QualitySeverity,
        file_path: str,
        unit_name: str,
        start_line: int,
        end_line: int,
        metric_value: float,
        threshold: float,
        recommendation: str,
    ) -> QualityHotspot:
        """
        Create a quality hotspot instance.

        Args:
            category: Type of quality issue
            severity: Severity level
            file_path: Path to the file
            unit_name: Name of the code unit
            start_line: Starting line number
            end_line: Ending line number
            metric_value: The actual metric value
            threshold: The threshold that was exceeded
            recommendation: Specific refactoring suggestion

        Returns:
            QualityHotspot instance
        """
        return QualityHotspot(
            severity=severity,
            category=category,
            file_path=file_path,
            unit_name=unit_name,
            start_line=start_line,
            end_line=end_line,
            metric_value=metric_value,
            threshold=threshold,
            recommendation=recommendation,
        )

    def analyze_for_hotspots(
        self,
        code_unit: Dict[str, Any],
        quality_metrics: CodeQualityMetrics,
    ) -> List[QualityHotspot]:
        """
        Analyze code unit for quality hotspots.

        Checks multiple quality dimensions and generates hotspots for issues.

        Args:
            code_unit: Code unit metadata
            quality_metrics: Pre-calculated quality metrics

        Returns:
            List of quality hotspots found
        """
        hotspots = []
        file_path = code_unit.get("file_path", "unknown")
        unit_name = code_unit.get("unit_name", "unknown")
        start_line = code_unit.get("start_line", 0)
        end_line = code_unit.get("end_line", 0)

        # Check cyclomatic complexity
        if quality_metrics.cyclomatic_complexity > self.complexity_critical:
            severity, _ = self.classify_complexity(quality_metrics.cyclomatic_complexity)
            hotspots.append(self.create_quality_hotspot(
                category=QualityCategory.COMPLEXITY,
                severity=severity,
                file_path=file_path,
                unit_name=unit_name,
                start_line=start_line,
                end_line=end_line,
                metric_value=quality_metrics.cyclomatic_complexity,
                threshold=self.complexity_critical,
                recommendation=f"Refactor into smaller functions (target: <{self.complexity_high})",
            ))
        elif quality_metrics.cyclomatic_complexity > self.complexity_high:
            hotspots.append(self.create_quality_hotspot(
                category=QualityCategory.COMPLEXITY,
                severity=QualitySeverity.HIGH,
                file_path=file_path,
                unit_name=unit_name,
                start_line=start_line,
                end_line=end_line,
                metric_value=quality_metrics.cyclomatic_complexity,
                threshold=self.complexity_high,
                recommendation=f"Consider simplifying logic (target: <{self.complexity_high})",
            ))

        # Check function length
        if quality_metrics.line_count > self.long_function_lines:
            severity = QualitySeverity.CRITICAL if quality_metrics.line_count > self.long_function_lines * 2 else QualitySeverity.HIGH
            hotspots.append(self.create_quality_hotspot(
                category=QualityCategory.LENGTH,
                severity=severity,
                file_path=file_path,
                unit_name=unit_name,
                start_line=start_line,
                end_line=end_line,
                metric_value=quality_metrics.line_count,
                threshold=self.long_function_lines,
                recommendation=f"Extract into smaller functions (target: <{self.long_function_lines} lines)",
            ))

        # Check nesting depth
        if quality_metrics.nesting_depth > self.deep_nesting:
            severity = QualitySeverity.CRITICAL if quality_metrics.nesting_depth > self.deep_nesting + 2 else QualitySeverity.HIGH
            hotspots.append(self.create_quality_hotspot(
                category=QualityCategory.NESTING,
                severity=severity,
                file_path=file_path,
                unit_name=unit_name,
                start_line=start_line,
                end_line=end_line,
                metric_value=quality_metrics.nesting_depth,
                threshold=self.deep_nesting,
                recommendation=f"Reduce nesting with early returns or helper functions (target: <{self.deep_nesting})",
            ))

        # Check parameter count
        if quality_metrics.parameter_count > self.many_parameters:
            severity = QualitySeverity.HIGH if quality_metrics.parameter_count > self.many_parameters + 2 else QualitySeverity.MEDIUM
            hotspots.append(self.create_quality_hotspot(
                category=QualityCategory.PARAMETERS,
                severity=severity,
                file_path=file_path,
                unit_name=unit_name,
                start_line=start_line,
                end_line=end_line,
                metric_value=quality_metrics.parameter_count,
                threshold=self.many_parameters,
                recommendation=f"Consider parameter object or builder pattern (target: <{self.many_parameters} parameters)",
            ))

        # Check duplication
        if quality_metrics.duplication_score > 0.95:
            hotspots.append(self.create_quality_hotspot(
                category=QualityCategory.DUPLICATION,
                severity=QualitySeverity.CRITICAL,
                file_path=file_path,
                unit_name=unit_name,
                start_line=start_line,
                end_line=end_line,
                metric_value=quality_metrics.duplication_score,
                threshold=0.95,
                recommendation="Extract common logic into shared utility (near-exact duplicate detected)",
            ))
        elif quality_metrics.duplication_score > 0.85:
            hotspots.append(self.create_quality_hotspot(
                category=QualityCategory.DUPLICATION,
                severity=QualitySeverity.HIGH,
                file_path=file_path,
                unit_name=unit_name,
                start_line=start_line,
                end_line=end_line,
                metric_value=quality_metrics.duplication_score,
                threshold=0.85,
                recommendation="Consider consolidating similar logic (high similarity detected)",
            ))

        # Check documentation
        if not quality_metrics.has_documentation:
            # Only flag complex functions without docs as medium severity
            if quality_metrics.cyclomatic_complexity > 5 or quality_metrics.line_count > 50:
                hotspots.append(self.create_quality_hotspot(
                    category=QualityCategory.DOCUMENTATION,
                    severity=QualitySeverity.MEDIUM,
                    file_path=file_path,
                    unit_name=unit_name,
                    start_line=start_line,
                    end_line=end_line,
                    metric_value=0.0,
                    threshold=1.0,
                    recommendation="Add documentation explaining purpose and usage",
                ))

        return hotspots

    def _determine_quality_flags(
        self,
        complexity_metrics: ComplexityMetrics,
        duplication_score: float,
    ) -> List[str]:
        """
        Determine quality flags based on metrics.

        Args:
            complexity_metrics: Complexity metrics
            duplication_score: Duplication score (0-1)

        Returns:
            List of quality flag strings
        """
        flags = []

        if complexity_metrics.cyclomatic_complexity > self.complexity_critical:
            flags.append("critical_complexity")
        elif complexity_metrics.cyclomatic_complexity > self.complexity_high:
            flags.append("high_complexity")

        if complexity_metrics.line_count > self.long_function_lines:
            flags.append("long_function")

        if complexity_metrics.nesting_depth > self.deep_nesting:
            flags.append("deep_nesting")

        if complexity_metrics.parameter_count > self.many_parameters:
            flags.append("many_parameters")

        if duplication_score > 0.95:
            flags.append("exact_duplicate")
        elif duplication_score > 0.85:
            flags.append("duplicate")

        if not complexity_metrics.has_documentation:
            flags.append("missing_docs")

        return flags
