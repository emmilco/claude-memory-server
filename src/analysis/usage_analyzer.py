"""
Usage analyzer for code importance scoring.

Analyzes usage patterns including:
- Call graph centrality (number of callers)
- Public vs private API status
- Export status (explicitly exported vs internal)
"""

import re
import logging
from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class UsageMetrics:
    """Container for usage analysis results."""

    caller_count: int
    is_public: bool
    is_exported: bool
    usage_boost: float  # Boost to add to base score (0.0-0.2)


class UsageAnalyzer:
    """Analyzes usage patterns to estimate code importance."""

    # Usage boost ranges
    MAX_USAGE_BOOST = 0.2

    # Thresholds for caller centrality
    HIGH_USAGE_THRESHOLD = 10  # 10+ callers = highly used
    MEDIUM_USAGE_THRESHOLD = 3  # 3-9 callers = medium usage

    def __init__(self):
        """Initialize usage analyzer."""
        self.call_graph: Dict[str, Set[str]] = {}  # function_name -> set of callers

    def analyze(
        self,
        code_unit: Dict[str, Any],
        all_units: Optional[List[Dict[str, Any]]] = None,
        file_content: Optional[str] = None,
    ) -> UsageMetrics:
        """
        Analyze usage patterns of a code unit.

        Args:
            code_unit: Dictionary with keys:
                - name: Function/class name
                - content: Full code content
                - unit_type: "function", "class", or "method"
                - language: Programming language
            all_units: List of all code units in the file (for call graph)
            file_content: Full file content (for export detection)

        Returns:
            UsageMetrics with calculated metrics and boost
        """
        name = code_unit.get("name", "")
        content = code_unit.get("content", "")
        unit_type = code_unit.get("unit_type", "function")
        language = code_unit.get("language", "python")

        # Build lightweight call graph if not already done
        if all_units and not self.call_graph:
            self._build_call_graph(all_units, language)

        # Calculate metrics
        caller_count = self._count_callers(name)
        is_public = self._is_public_api(name, unit_type, language)
        is_exported = self._is_exported(name, file_content, language)

        # Calculate usage boost
        boost = self._calculate_usage_boost(caller_count, is_public, is_exported)

        return UsageMetrics(
            caller_count=caller_count,
            is_public=is_public,
            is_exported=is_exported,
            usage_boost=boost,
        )

    def _build_call_graph(self, all_units: List[Dict[str, Any]], language: str) -> None:
        """
        Build lightweight call graph from code units.

        For each function, identifies which other functions call it.
        """
        # Initialize call graph
        self.call_graph = {}

        # Create mapping of function names to their content
        unit_map = {unit.get("name", ""): unit for unit in all_units}

        # For each function, scan for calls to other functions
        for unit in all_units:
            caller_name = unit.get("name", "")
            caller_content = unit.get("content", "")

            # Find function calls in the content
            called_functions = self._extract_function_calls(caller_content, language)

            # Update call graph
            for called_func in called_functions:
                if called_func in unit_map and called_func != caller_name:
                    if called_func not in self.call_graph:
                        self.call_graph[called_func] = set()
                    self.call_graph[called_func].add(caller_name)

    def _extract_function_calls(self, content: str, language: str) -> Set[str]:
        """
        Extract function calls from code content.

        Uses simple pattern matching for common call patterns.
        """
        calls = set()

        # Language-specific call patterns
        if language.lower() in ["python"]:
            # Match: function_name( or function_name (
            pattern = r'\b([a-zA-Z_][a-zA-Z0-9_]*)\s*\('
        elif language.lower() in ["javascript", "typescript"]:
            # Match: functionName( or object.method(
            pattern = r'\b([a-zA-Z_$][a-zA-Z0-9_$]*)\s*\('
        elif language.lower() in ["java", "go", "rust"]:
            # Match: functionName( or object.method(
            pattern = r'\b([a-zA-Z_][a-zA-Z0-9_]*)\s*\('
        else:
            pattern = r'\b([a-zA-Z_][a-zA-Z0-9_]*)\s*\('

        matches = re.findall(pattern, content)
        calls.update(matches)

        return calls

    def _count_callers(self, function_name: str) -> int:
        """Count how many functions call this function."""
        if not self.call_graph:
            return 0

        return len(self.call_graph.get(function_name, set()))

    def _is_public_api(self, name: str, unit_type: str, language: str) -> bool:
        """
        Determine if this is a public API based on naming conventions.

        Private indicators:
        - Python: _private, __private
        - JavaScript/TypeScript: _private, #private
        - Java: private modifier (can't detect from name alone)
        - Go: unexported (lowercase first letter)
        """
        if not name:
            return False

        # Language-specific private naming conventions
        if language.lower() == "python":
            # Single or double underscore prefix = private
            return not name.startswith('_')
        elif language.lower() in ["javascript", "typescript"]:
            # Underscore or hash prefix = private
            return not name.startswith('_') and not name.startswith('#')
        elif language.lower() == "go":
            # Lowercase first letter = unexported (private)
            return name[0].isupper() if name else False
        else:
            # Default: assume underscore prefix = private
            return not name.startswith('_')

    def _is_exported(
        self, name: str, file_content: Optional[str], language: str
    ) -> bool:
        """
        Determine if this function/class is explicitly exported.

        Checks for:
        - Python: __all__ list
        - JavaScript/TypeScript: export keyword
        - Java: public modifier
        - Go: exported (uppercase first letter)
        """
        if not file_content or not name:
            return False

        # Language-specific export patterns
        if language.lower() == "python":
            # Check for __all__ export list
            all_match = re.search(r'__all__\s*=\s*\[(.*?)\]', file_content, re.DOTALL)
            if all_match:
                exports = all_match.group(1)
                # Check if name is in the list
                return f'"{name}"' in exports or f"'{name}'" in exports
            # If no __all__, assume public functions are exported
            return not name.startswith('_')

        elif language.lower() in ["javascript", "typescript"]:
            # Check for export keyword
            export_patterns = [
                rf'export\s+(function|class|const|let|var)\s+{re.escape(name)}\b',
                rf'export\s+\{{[^}}]*\b{re.escape(name)}\b[^}}]*\}}',  # export { func1, func2 }
                rf'export\s+default\s+{re.escape(name)}\b',
            ]
            for pattern in export_patterns:
                if re.search(pattern, file_content):
                    return True
            return False

        elif language.lower() == "java":
            # Check for public modifier in class/method declaration
            # More flexible pattern to match methods: public void methodName()
            pattern = rf'\bpublic\s+(\w+\s+)*{re.escape(name)}\s*\('
            return bool(re.search(pattern, file_content))

        elif language.lower() == "go":
            # Exported = uppercase first letter
            return name[0].isupper() if name else False

        else:
            # Default: assume not exported unless we can detect it
            return False

    def _calculate_usage_boost(
        self, caller_count: int, is_public: bool, is_exported: bool
    ) -> float:
        """
        Calculate usage boost (0.0-0.2 range).

        Formula:
        - Caller count: 0-10+ callers = 0.0-0.12 boost
        - Public API: +0.04 boost
        - Explicitly exported: +0.04 boost
        """
        boost = 0.0

        # Caller count boost (0.0-0.12)
        if caller_count >= self.HIGH_USAGE_THRESHOLD:
            boost += 0.12
        elif caller_count >= self.MEDIUM_USAGE_THRESHOLD:
            # Scale from 0.04 to 0.12
            ratio = (caller_count - self.MEDIUM_USAGE_THRESHOLD) / (
                self.HIGH_USAGE_THRESHOLD - self.MEDIUM_USAGE_THRESHOLD
            )
            boost += 0.04 + (ratio * 0.08)
        elif caller_count > 0:
            # Scale from 0.0 to 0.04
            ratio = caller_count / self.MEDIUM_USAGE_THRESHOLD
            boost += ratio * 0.04

        # Public API boost
        if is_public:
            boost += 0.04

        # Export boost
        if is_exported:
            boost += 0.04

        return min(boost, self.MAX_USAGE_BOOST)

    def reset(self) -> None:
        """Reset call graph (call between files)."""
        self.call_graph = {}
