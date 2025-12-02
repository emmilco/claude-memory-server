"""Code analysis for refactoring suggestions."""

import re
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class CodeMetrics:
    """Metrics for a code unit (function, class, method)."""

    name: str
    lines_of_code: int
    cyclomatic_complexity: int
    parameter_count: int
    nesting_depth: int
    return_count: int


@dataclass
class RefactoringSuggestion:
    """A suggested refactoring with context."""

    issue_type: str
    severity: str  # 'low' | 'medium' | 'high'
    file_path: str
    line_number: int
    code_unit_name: str
    description: str
    suggested_fix: str
    metrics: Optional[CodeMetrics] = None


class CodeAnalyzer:
    """Analyzes code for refactoring opportunities."""

    # Thresholds for refactoring suggestions
    MAX_PARAMETERS = 5
    MAX_LINES_OF_CODE = 50
    MAX_NESTING_DEPTH = 4
    HIGH_COMPLEXITY_THRESHOLD = 10
    DUPLICATE_SIMILARITY_THRESHOLD = 0.85

    def __init__(self):
        """Initialize the code analyzer."""
        pass

    def calculate_metrics(
        self, code: str, language: str, function_name: Optional[str] = None
    ) -> List[CodeMetrics]:
        """
        Calculate metrics for code units in a code snippet.

        Args:
            code: The code to analyze
            language: Programming language
            function_name: Optional specific function to analyze

        Returns:
            List of CodeMetrics for each code unit
        """
        metrics_list = []

        # For simple MVP, analyze the whole code as one unit if no AST
        # In production, we'd use tree-sitter to parse and analyze each function
        lines = [
            line
            for line in code.split("\n")
            if line.strip() and not line.strip().startswith("#")
        ]

        # Calculate basic metrics
        loc = len(lines)
        complexity = self._calculate_complexity(code)
        params = self._count_parameters(code, language)
        nesting = self._calculate_nesting_depth(code)
        returns = code.count("return ")

        # Create metrics for the code unit
        name = function_name or "code_snippet"
        metrics = CodeMetrics(
            name=name,
            lines_of_code=loc,
            cyclomatic_complexity=complexity,
            parameter_count=params,
            nesting_depth=nesting,
            return_count=returns,
        )
        metrics_list.append(metrics)

        return metrics_list

    def _calculate_complexity(self, code: str) -> int:
        """
        Calculate cyclomatic complexity (simplified).

        Complexity = 1 + number of decision points (if, while, for, try, etc.)
        """
        complexity = 1
        # Count decision points
        keywords = [
            r"\bif\b",
            r"\bwhile\b",
            r"\bfor\b",
            r"\belif\b",
            r"\bexcept\b",
            r"\band\b",
            r"\bor\b",
        ]
        for keyword in keywords:
            complexity += len(re.findall(keyword, code))
        return complexity

    def _count_parameters(self, code: str, language: str) -> int:
        """
        Count function parameters (simplified).

        Looks for function definitions and counts parameters.
        """
        if language in ["python", "py"]:
            # Match: def function_name(param1, param2, ...)
            match = re.search(r"def\s+\w+\s*\((.*?)\)", code)
            if match:
                params_str = match.group(1).strip()
                if not params_str:
                    return 0
                # Split by comma and count (handle self/cls)
                params = [p.strip() for p in params_str.split(",")]
                params = [p for p in params if p and p not in ["self", "cls"]]
                return len(params)

        elif language in ["javascript", "typescript", "js", "ts"]:
            # Match: function name(param1, param2) or (param1, param2) =>
            match = re.search(r"(?:function\s+\w+\s*|=>\s*)\((.*?)\)", code)
            if match:
                params_str = match.group(1).strip()
                if not params_str:
                    return 0
                params = [p.strip() for p in params_str.split(",")]
                return len(params)

        return 0

    def _calculate_nesting_depth(self, code: str) -> int:
        """
        Calculate maximum nesting depth.

        Counts maximum depth of nested blocks (braces, indentation).
        """
        max_depth = 0

        # For Python, use indentation
        lines = code.split("\n")
        for line in lines:
            if not line.strip():
                continue
            # Count leading spaces/tabs
            indent = len(line) - len(line.lstrip())
            depth = indent // 4  # Assuming 4-space indentation
            max_depth = max(max_depth, depth)

        return max_depth

    def detect_long_parameter_list(
        self, metrics: CodeMetrics, file_path: str, line_number: int
    ) -> Optional[RefactoringSuggestion]:
        """Detect functions with too many parameters."""
        if metrics.parameter_count > self.MAX_PARAMETERS:
            severity = "high" if metrics.parameter_count > 8 else "medium"
            return RefactoringSuggestion(
                issue_type="Long Parameter List",
                severity=severity,
                file_path=file_path,
                line_number=line_number,
                code_unit_name=metrics.name,
                description=f"Function '{metrics.name}' has {metrics.parameter_count} parameters (max recommended: {self.MAX_PARAMETERS})",
                suggested_fix="Consider grouping related parameters into a configuration object or data class",
                metrics=metrics,
            )
        return None

    def detect_large_function(
        self, metrics: CodeMetrics, file_path: str, line_number: int
    ) -> Optional[RefactoringSuggestion]:
        """Detect functions that are too long."""
        if metrics.lines_of_code > self.MAX_LINES_OF_CODE:
            severity = "high" if metrics.lines_of_code > 100 else "medium"
            return RefactoringSuggestion(
                issue_type="Large Function",
                severity=severity,
                file_path=file_path,
                line_number=line_number,
                code_unit_name=metrics.name,
                description=f"Function '{metrics.name}' has {metrics.lines_of_code} lines of code (max recommended: {self.MAX_LINES_OF_CODE})",
                suggested_fix="Consider breaking this function into smaller, focused functions using the Extract Method refactoring",
                metrics=metrics,
            )
        return None

    def detect_deep_nesting(
        self, metrics: CodeMetrics, file_path: str, line_number: int
    ) -> Optional[RefactoringSuggestion]:
        """Detect code with excessive nesting."""
        if metrics.nesting_depth > self.MAX_NESTING_DEPTH:
            return RefactoringSuggestion(
                issue_type="Deep Nesting",
                severity="medium",
                file_path=file_path,
                line_number=line_number,
                code_unit_name=metrics.name,
                description=f"Function '{metrics.name}' has nesting depth of {metrics.nesting_depth} (max recommended: {self.MAX_NESTING_DEPTH})",
                suggested_fix="Consider flattening nested code using early returns, guard clauses, or extracting nested logic into separate functions",
                metrics=metrics,
            )
        return None

    def detect_high_complexity(
        self, metrics: CodeMetrics, file_path: str, line_number: int
    ) -> Optional[RefactoringSuggestion]:
        """Detect functions with high cyclomatic complexity."""
        if metrics.cyclomatic_complexity > self.HIGH_COMPLEXITY_THRESHOLD:
            severity = "high" if metrics.cyclomatic_complexity > 15 else "medium"
            return RefactoringSuggestion(
                issue_type="High Complexity",
                severity=severity,
                file_path=file_path,
                line_number=line_number,
                code_unit_name=metrics.name,
                description=f"Function '{metrics.name}' has cyclomatic complexity of {metrics.cyclomatic_complexity} (max recommended: {self.HIGH_COMPLEXITY_THRESHOLD})",
                suggested_fix="Consider simplifying the logic by extracting complex conditions into well-named functions or using polymorphism",
                metrics=metrics,
            )
        return None

    def analyze_code(
        self, code: str, language: str, file_path: str, line_number: int = 1
    ) -> List[RefactoringSuggestion]:
        """
        Analyze code and return all refactoring suggestions.

        Args:
            code: The code to analyze
            language: Programming language
            file_path: Path to the file
            line_number: Starting line number

        Returns:
            List of refactoring suggestions
        """
        suggestions = []

        # Calculate metrics
        metrics_list = self.calculate_metrics(code, language)

        # Detect issues for each code unit
        for metrics in metrics_list:
            # Check for long parameter lists
            suggestion = self.detect_long_parameter_list(
                metrics, file_path, line_number
            )
            if suggestion:
                suggestions.append(suggestion)

            # Check for large functions
            suggestion = self.detect_large_function(metrics, file_path, line_number)
            if suggestion:
                suggestions.append(suggestion)

            # Check for deep nesting
            suggestion = self.detect_deep_nesting(metrics, file_path, line_number)
            if suggestion:
                suggestions.append(suggestion)

            # Check for high complexity
            suggestion = self.detect_high_complexity(metrics, file_path, line_number)
            if suggestion:
                suggestions.append(suggestion)

        return suggestions
