"""
Unit tests for QualityAnalyzer (FEAT-060 Phase 4).

Tests cover:
- Maintainability index calculation
- Complexity classification
- Quality flag detection
- Hotspot creation and analysis
"""

import pytest
from src.analysis.quality_analyzer import (
    QualityAnalyzer,
    CodeQualityMetrics,
    QualityHotspot,
    QualitySeverity,
    QualityCategory,
)
from src.analysis.complexity_analyzer import ComplexityAnalyzer, ComplexityMetrics


class TestQualityAnalyzer:
    """Test QualityAnalyzer class."""

    @pytest.fixture
    def analyzer(self):
        """Create analyzer instance."""
        return QualityAnalyzer()

    @pytest.fixture
    def simple_code_unit(self):
        """Simple code unit with low complexity."""
        return {
            "content": "def simple():\n    return True",
            "signature": "simple()",
            "unit_type": "function",
            "language": "python",
            "file_path": "test.py",
            "unit_name": "simple",
            "start_line": 1,
            "end_line": 2,
        }

    @pytest.fixture
    def complex_code_unit(self):
        """Complex code unit with high complexity."""
        code = """
def complex_func(a, b, c, d, e, f):
    if a:
        if b:
            if c:
                if d:
                    if e:
                        return f
    elif a or b or c:
        for i in range(10):
            if i > 5:
                return i
    return 0
"""
        return {
            "content": code,
            "signature": "complex_func(a, b, c, d, e, f)",
            "unit_type": "function",
            "language": "python",
            "file_path": "test.py",
            "unit_name": "complex_func",
            "start_line": 1,
            "end_line": 14,
        }

    # Maintainability Index Tests
    def test_maintainability_index_excellent(self, analyzer):
        """Test MI calculation for excellent code."""
        mi = analyzer.calculate_maintainability_index(
            cyclomatic_complexity=2,
            line_count=10,
            has_documentation=True,
        )
        assert mi >= 85, "Excellent code should have MI >= 85"
        assert mi <= 100, "MI should not exceed 100"

    def test_maintainability_index_moderate(self, analyzer):
        """Test MI calculation for moderate code."""
        mi = analyzer.calculate_maintainability_index(
            cyclomatic_complexity=10,
            line_count=50,
            has_documentation=False,
        )
        assert 65 <= mi < 85, "Moderate code should have 65 <= MI < 85"

    def test_maintainability_index_poor(self, analyzer):
        """Test MI calculation for poor code."""
        mi = analyzer.calculate_maintainability_index(
            cyclomatic_complexity=25,
            line_count=200,
            has_documentation=False,
        )
        assert mi < 65, "Poor code should have MI < 65"

    def test_maintainability_index_with_docs_bonus(self, analyzer):
        """Test MI bonus for documentation."""
        mi_without_docs = analyzer.calculate_maintainability_index(
            cyclomatic_complexity=5,
            line_count=30,
            has_documentation=False,
        )
        mi_with_docs = analyzer.calculate_maintainability_index(
            cyclomatic_complexity=5,
            line_count=30,
            has_documentation=True,
        )
        assert mi_with_docs > mi_without_docs, "Documentation should increase MI"
        assert mi_with_docs - mi_without_docs == 5, "Documentation bonus should be +5"

    def test_maintainability_index_clamped(self, analyzer):
        """Test MI is clamped to 0-100 range."""
        # Very good code
        mi_high = analyzer.calculate_maintainability_index(
            cyclomatic_complexity=1,
            line_count=5,
            has_documentation=True,
        )
        assert mi_high <= 100, "MI should be clamped at 100"

        # Very bad code
        mi_low = analyzer.calculate_maintainability_index(
            cyclomatic_complexity=50,
            line_count=500,
            has_documentation=False,
        )
        assert mi_low >= 0, "MI should be clamped at 0"

    # Complexity Classification Tests
    def test_classify_complexity_low(self, analyzer):
        """Test low complexity classification."""
        severity, desc = analyzer.classify_complexity(3)
        assert severity == QualitySeverity.LOW
        assert "simple" in desc.lower() or "easy" in desc.lower()

    def test_classify_complexity_medium(self, analyzer):
        """Test medium complexity classification."""
        severity, desc = analyzer.classify_complexity(7)
        assert severity == QualitySeverity.MEDIUM
        assert "moderate" in desc.lower()

    def test_classify_complexity_high(self, analyzer):
        """Test high complexity classification."""
        severity, desc = analyzer.classify_complexity(15)
        assert severity == QualitySeverity.HIGH
        assert "complex" in desc.lower()

    def test_classify_complexity_critical(self, analyzer):
        """Test critical complexity classification."""
        severity, desc = analyzer.classify_complexity(25)
        assert severity == QualitySeverity.CRITICAL
        assert "very complex" in desc.lower() or "refactor" in desc.lower()

    # Maintainability Classification Tests
    def test_classify_maintainability_excellent(self, analyzer):
        """Test excellent maintainability classification."""
        severity, desc = analyzer.classify_maintainability(90)
        assert severity == QualitySeverity.LOW
        assert "highly maintainable" in desc.lower()

    def test_classify_maintainability_good(self, analyzer):
        """Test good maintainability classification."""
        severity, desc = analyzer.classify_maintainability(70)
        assert severity == QualitySeverity.MEDIUM
        assert "moderately maintainable" in desc.lower()

    def test_classify_maintainability_difficult(self, analyzer):
        """Test difficult maintainability classification."""
        severity, desc = analyzer.classify_maintainability(55)
        assert severity == QualitySeverity.HIGH
        assert "difficult" in desc.lower()

    def test_classify_maintainability_critical(self, analyzer):
        """Test critical maintainability classification."""
        severity, desc = analyzer.classify_maintainability(30)
        assert severity == QualitySeverity.CRITICAL
        assert "very difficult" in desc.lower()

    # Quality Metrics Calculation Tests
    def test_calculate_quality_metrics_simple(self, analyzer, simple_code_unit):
        """Test quality metrics for simple code."""
        metrics = analyzer.calculate_quality_metrics(
            code_unit=simple_code_unit,
            duplication_score=0.0,
        )
        assert isinstance(metrics, CodeQualityMetrics)
        assert metrics.cyclomatic_complexity <= 5
        assert metrics.line_count <= 10
        assert metrics.maintainability_index >= 80
        assert metrics.duplication_score == 0.0
        assert len(metrics.quality_flags) == 0 or "missing_docs" in metrics.quality_flags

    def test_calculate_quality_metrics_complex(self, analyzer, complex_code_unit):
        """Test quality metrics for complex code."""
        metrics = analyzer.calculate_quality_metrics(
            code_unit=complex_code_unit,
            duplication_score=0.0,
        )
        assert metrics.cyclomatic_complexity > 10
        assert "high_complexity" in metrics.quality_flags or "critical_complexity" in metrics.quality_flags
        assert metrics.maintainability_index < 80

    def test_quality_flags_high_complexity(self, analyzer, complex_code_unit):
        """Test quality flags for high complexity."""
        metrics = analyzer.calculate_quality_metrics(
            code_unit=complex_code_unit,
            duplication_score=0.0,
        )
        assert any("complexity" in flag for flag in metrics.quality_flags)

    def test_quality_flags_duplicate(self, analyzer, simple_code_unit):
        """Test quality flags for duplicates."""
        metrics = analyzer.calculate_quality_metrics(
            code_unit=simple_code_unit,
            duplication_score=0.96,  # Need >0.95 for exact_duplicate
        )
        assert "exact_duplicate" in metrics.quality_flags

    def test_quality_flags_partial_duplicate(self, analyzer, simple_code_unit):
        """Test quality flags for partial duplicates."""
        metrics = analyzer.calculate_quality_metrics(
            code_unit=simple_code_unit,
            duplication_score=0.88,
        )
        assert "duplicate" in metrics.quality_flags

    # Hotspot Analysis Tests
    def test_analyze_for_hotspots_clean_code(self, analyzer, simple_code_unit):
        """Test hotspot analysis for clean code."""
        metrics = analyzer.calculate_quality_metrics(
            code_unit=simple_code_unit,
            duplication_score=0.0,
        )
        hotspots = analyzer.analyze_for_hotspots(
            code_unit=simple_code_unit,
            quality_metrics=metrics,
        )
        # Clean code may have doc hotspot but no critical issues
        assert all(h.severity != QualitySeverity.CRITICAL for h in hotspots)

    def test_analyze_for_hotspots_complex_code(self, analyzer, complex_code_unit):
        """Test hotspot analysis for complex code."""
        metrics = analyzer.calculate_quality_metrics(
            code_unit=complex_code_unit,
            duplication_score=0.0,
        )
        hotspots = analyzer.analyze_for_hotspots(
            code_unit=complex_code_unit,
            quality_metrics=metrics,
        )
        # Complex code should have complexity hotspots
        assert len(hotspots) > 0
        assert any(h.category == QualityCategory.COMPLEXITY for h in hotspots)

    def test_hotspot_critical_complexity(self, analyzer):
        """Test critical complexity hotspot creation."""
        code_unit = {
            "content": "def test(): pass",
            "file_path": "test.py",
            "unit_name": "test",
            "start_line": 1,
            "end_line": 1,
        }
        # Create quality metrics with critical complexity
        quality_metrics = CodeQualityMetrics(
            cyclomatic_complexity=25,
            line_count=50,
            nesting_depth=3,
            parameter_count=2,
            has_documentation=False,
            duplication_score=0.0,
            maintainability_index=40,
            quality_flags=["critical_complexity"],
        )
        hotspots = analyzer.analyze_for_hotspots(code_unit, quality_metrics)
        assert any(
            h.category == QualityCategory.COMPLEXITY and h.severity == QualitySeverity.CRITICAL
            for h in hotspots
        )

    def test_hotspot_long_function(self, analyzer):
        """Test long function hotspot creation."""
        code_unit = {
            "content": "def test(): pass",
            "file_path": "test.py",
            "unit_name": "test",
            "start_line": 1,
            "end_line": 150,
        }
        quality_metrics = CodeQualityMetrics(
            cyclomatic_complexity=5,
            line_count=150,
            nesting_depth=2,
            parameter_count=2,
            has_documentation=True,
            duplication_score=0.0,
            maintainability_index=70,
            quality_flags=["long_function"],
        )
        hotspots = analyzer.analyze_for_hotspots(code_unit, quality_metrics)
        assert any(h.category == QualityCategory.LENGTH for h in hotspots)

    def test_hotspot_to_dict(self, analyzer):
        """Test hotspot serialization to dict."""
        hotspot = QualityHotspot(
            severity=QualitySeverity.HIGH,
            category=QualityCategory.COMPLEXITY,
            file_path="test.py",
            unit_name="test_func",
            start_line=10,
            end_line=50,
            metric_value=15,
            threshold=10,
            recommendation="Refactor into smaller functions",
        )
        result = hotspot.to_dict()
        assert result["severity"] == "high"
        assert result["category"] == "complexity"
        assert result["file_path"] == "test.py"
        assert result["metric_value"] == 15
        assert "refactor" in result["recommendation"].lower()
