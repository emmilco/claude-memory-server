"""
Complexity analyzer for code importance scoring.

Calculates complexity metrics including:
- Cyclomatic complexity (branching/loops)
- Line count (normalized)
- Nesting depth
- Parameter count
- Documentation presence
"""

import re
import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ComplexityMetrics:
    """Container for complexity analysis results."""

    cyclomatic_complexity: int
    line_count: int
    nesting_depth: int
    parameter_count: int
    has_documentation: bool
    complexity_score: float  # Normalized 0.0-1.0


class ComplexityAnalyzer:
    """Analyzes code complexity to estimate importance."""

    # Complexity score ranges (normalized to 0.3-0.7 for base score)
    MIN_COMPLEXITY_SCORE = 0.3
    MAX_COMPLEXITY_SCORE = 0.7

    # Thresholds for normalization
    MAX_CYCLOMATIC = 20  # Above this is very complex
    MAX_LINES = 100      # Above this is very long
    MAX_NESTING = 5      # Above this is deeply nested
    MAX_PARAMS = 5       # Above this is many parameters

    def __init__(self):
        """Initialize complexity analyzer."""
        pass

    def analyze(self, code_unit: Dict[str, Any]) -> ComplexityMetrics:
        """
        Analyze complexity of a code unit.

        Args:
            code_unit: Dictionary with keys:
                - content: Full code content
                - signature: Function/class signature
                - unit_type: "function", "class", or "method"
                - language: Programming language

        Returns:
            ComplexityMetrics with calculated metrics and score
        """
        content = code_unit.get("content", "")
        signature = code_unit.get("signature", "")
        unit_type = code_unit.get("unit_type", "function")
        language = code_unit.get("language", "python")

        # Calculate individual metrics
        cyclomatic = self._calculate_cyclomatic_complexity(content, language)
        line_count = self._count_lines(content)
        nesting = self._calculate_nesting_depth(content, language)
        params = self._count_parameters(signature, language)
        has_docs = self._has_documentation(content, language)

        # Calculate normalized complexity score
        score = self._calculate_complexity_score(
            cyclomatic, line_count, nesting, params, has_docs, unit_type
        )

        return ComplexityMetrics(
            cyclomatic_complexity=cyclomatic,
            line_count=line_count,
            nesting_depth=nesting,
            parameter_count=params,
            has_documentation=has_docs,
            complexity_score=score,
        )

    def _calculate_cyclomatic_complexity(self, content: str, language: str) -> int:
        """
        Calculate cyclomatic complexity (decision points + 1).

        Counts:
        - if/else statements
        - loops (for, while, do-while)
        - case/switch statements
        - try/catch blocks
        - logical operators (&&, ||, and, or)
        - ternary operators
        """
        complexity = 1  # Base complexity

        # Language-specific decision point patterns
        patterns = {
            "python": [
                r'\bif\b', r'\belif\b', r'\bfor\b', r'\bwhile\b',
                r'\band\b', r'\bor\b', r'\bexcept\b', r'\bcase\b',
            ],
            "javascript": [
                r'\bif\b', r'\belse if\b', r'\bfor\b', r'\bwhile\b', r'\bdo\b',
                r'\bcase\b', r'\bcatch\b', r'&&', r'\|\|', r'\?.*:',
            ],
            "typescript": [
                r'\bif\b', r'\belse if\b', r'\bfor\b', r'\bwhile\b', r'\bdo\b',
                r'\bcase\b', r'\bcatch\b', r'&&', r'\|\|', r'\?.*:',
            ],
            "java": [
                r'\bif\b', r'\belse if\b', r'\bfor\b', r'\bwhile\b', r'\bdo\b',
                r'\bcase\b', r'\bcatch\b', r'&&', r'\|\|', r'\?.*:',
            ],
            "go": [
                r'\bif\b', r'\belse if\b', r'\bfor\b', r'\bselect\b',
                r'\bcase\b', r'&&', r'\|\|',
            ],
            "rust": [
                r'\bif\b', r'\belse if\b', r'\bfor\b', r'\bwhile\b', r'\bloop\b',
                r'\bmatch\b', r'&&', r'\|\|',
            ],
        }

        # Get patterns for language (default to Python patterns)
        lang_patterns = patterns.get(language.lower(), patterns["python"])

        # Count decision points
        for pattern in lang_patterns:
            matches = re.findall(pattern, content)
            complexity += len(matches)

        return min(complexity, self.MAX_CYCLOMATIC * 2)  # Cap at 2x max

    def _count_lines(self, content: str) -> int:
        """Count non-empty, non-comment lines."""
        lines = content.split('\n')

        # Count non-empty lines (simple heuristic)
        non_empty = [
            line for line in lines
            if line.strip() and not line.strip().startswith(('#', '//', '/*', '*', '"""', "'''"))
        ]

        return len(non_empty)

    def _calculate_nesting_depth(self, content: str, language: str) -> int:
        """
        Calculate maximum nesting depth.

        Tracks indentation levels (simple heuristic).
        """
        lines = content.split('\n')
        max_depth = 0
        current_depth = 0

        # Language-specific indentation and block patterns
        indent_chars = {
            "python": "    ",  # 4 spaces
            "javascript": "  ",  # 2 spaces (common)
            "typescript": "  ",
            "java": "    ",
            "go": "\t",  # Tabs
            "rust": "    ",
        }

        indent_unit = indent_chars.get(language.lower(), "    ")
        indent_size = len(indent_unit)

        for line in lines:
            if not line.strip():
                continue

            # Count leading whitespace
            leading = len(line) - len(line.lstrip())

            # Estimate depth (accounting for different indent styles)
            if indent_size > 0:
                depth = leading // indent_size
            else:
                depth = 0

            # Track brace-based nesting for C-style languages
            if language.lower() in ["javascript", "typescript", "java", "go", "rust"]:
                depth += line.count('{') - line.count('}')

            current_depth = max(0, depth)
            max_depth = max(max_depth, current_depth)

        return min(max_depth, self.MAX_NESTING * 2)  # Cap at 2x max

    def _count_parameters(self, signature: str, language: str) -> int:
        """Count function parameters from signature."""
        if not signature:
            return 0

        # Extract parameter list from signature
        # Look for content between parentheses
        match = re.search(r'\((.*?)\)', signature)
        if not match:
            return 0

        params_str = match.group(1).strip()
        if not params_str:
            return 0

        # Split by commas (simple heuristic, doesn't handle nested parens perfectly)
        params = [p.strip() for p in params_str.split(',')]

        # Filter out 'self', 'cls', 'this' (not real parameters)
        filtered = [
            p for p in params
            if p and p.lower() not in ['self', 'cls', 'this']
        ]

        return min(len(filtered), self.MAX_PARAMS * 2)  # Cap at 2x max

    def _has_documentation(self, content: str, language: str) -> bool:
        """Check if code has documentation (docstring or comments)."""
        # Language-specific doc patterns
        doc_patterns = {
            "python": [r'""".*?"""', r"'''.*?'''"],  # Docstrings
            "javascript": [r'/\*\*.*?\*/', r'//.*'],  # JSDoc or comments
            "typescript": [r'/\*\*.*?\*/', r'//.*'],
            "java": [r'/\*\*.*?\*/', r'//.*'],  # Javadoc
            "go": [r'//.*'],  # Go doc comments
            "rust": [r'///.*', r'//!.*'],  # Rust doc comments
        }

        patterns = doc_patterns.get(language.lower(), doc_patterns["python"])

        # Check for documentation patterns
        for pattern in patterns:
            if re.search(pattern, content, re.DOTALL):
                # Verify it's substantial (>10 chars)
                match = re.search(pattern, content, re.DOTALL)
                if match and len(match.group(0)) > 10:
                    return True

        return False

    def _calculate_complexity_score(
        self,
        cyclomatic: int,
        line_count: int,
        nesting: int,
        params: int,
        has_docs: bool,
        unit_type: str,
    ) -> float:
        """
        Calculate normalized complexity score (0.3-0.7 range).

        Formula:
        - Cyclomatic complexity: 40% weight
        - Line count: 30% weight
        - Nesting depth: 20% weight
        - Parameter count: 10% weight
        - Documentation boost: +0.05
        """
        # Normalize each metric to 0.0-1.0
        cyclomatic_norm = min(cyclomatic / self.MAX_CYCLOMATIC, 1.0)
        lines_norm = min(line_count / self.MAX_LINES, 1.0)
        nesting_norm = min(nesting / self.MAX_NESTING, 1.0)
        params_norm = min(params / self.MAX_PARAMS, 1.0)

        # Weighted average
        weighted_score = (
            cyclomatic_norm * 0.40 +
            lines_norm * 0.30 +
            nesting_norm * 0.20 +
            params_norm * 0.10
        )

        # Scale to 0.3-0.7 range (base complexity score)
        score_range = self.MAX_COMPLEXITY_SCORE - self.MIN_COMPLEXITY_SCORE
        base_score = self.MIN_COMPLEXITY_SCORE + (weighted_score * score_range)

        # Documentation boost (small)
        if has_docs:
            base_score += 0.05

        # Ensure within range
        return max(self.MIN_COMPLEXITY_SCORE, min(self.MAX_COMPLEXITY_SCORE, base_score))
