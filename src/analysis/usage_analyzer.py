"""
Usage analyzer for code importance scoring.

Analyzes usage patterns to identify highly-used, public-facing, and entry-point
code. Builds lightweight call graphs to measure centrality and provides boost
scores (0.0-0.2) that amplify importance for frequently-used code.

Usage Patterns Analyzed:
- Call graph centrality: Number of callers (0-10+)
- Public API detection: Naming conventions (_private vs public)
- Export status: Explicit exports (__all__, export keyword)
- Entry point detection: main files, API files, __init__ modules

Boost Calculation:
- Caller count (0-2): +0.00 to +0.03
- Caller count (3-9): +0.03 to +0.10 (scaled)
- Caller count (10+): +0.10 (maximum)
- Public API: +0.03
- Explicitly exported: +0.03
- Entry point file: +0.04
- Maximum total boost: 0.2 (20% importance increase)

Call Graph Construction:
- Lightweight static analysis (no execution)
- Simple pattern matching for function calls
- File-scoped only (no cross-file analysis)
- Reset between files to manage memory

Language-Specific Rules:
- Python: _private, __private = private; __all__ = exports
- JavaScript/TypeScript: _private, #private = private; export keyword
- Java: Limited name-based detection; public keyword for exports
- Go: Lowercase = private; uppercase = exported
- Rust: Similar to Go naming conventions

Thresholds:
- HIGH_USAGE_THRESHOLD = 10 callers (highly central)
- MEDIUM_USAGE_THRESHOLD = 3 callers (moderately used)

Architecture:
- Stateful analyzer (maintains call_graph dictionary)
- Must call reset() between files to clear state
- Used by ImportanceScorer for batch processing
- Integrates with ComplexityAnalyzer and CriticalityAnalyzer

Example:
    ```python
    analyzer = UsageAnalyzer()
    metrics = analyzer.analyze(
        code_unit={'name': 'process_request', 'content': code},
        all_units=all_file_units,  # For call graph
        file_content=full_file_text,  # For export detection
        file_path=Path('src/api/handler.py')
    )
    # metrics.usage_boost = 0.17 (10+ callers + public + exported + entry point)
    analyzer.reset()  # Clear call graph before next file
    ```

Part of FEAT-049: Intelligent Code Importance Scoring
"""

import re
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class UsageMetrics:
    """Container for usage analysis results."""

    caller_count: int
    is_public: bool
    is_exported: bool
    is_entry_point: bool  # In entry point file (main, api, __init__)
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
        file_path: Optional[Path] = None,
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
            file_path: Path to the file (for entry point detection)

        Returns:
            UsageMetrics with calculated metrics and boost
        """
        name = code_unit.get("name", "")
        code_unit.get("content", "")
        unit_type = code_unit.get("unit_type", "function")
        language = code_unit.get("language", "python")

        # Build lightweight call graph if not already done
        if all_units and not self.call_graph:
            self._build_call_graph(all_units, language)

        # Calculate metrics
        caller_count = self._count_callers(name)
        is_public = self._is_public_api(name, unit_type, language)
        is_exported = self._is_exported(name, file_content, language)
        is_entry_point = self._is_entry_point(file_path)

        # Calculate usage boost
        boost = self._calculate_usage_boost(
            caller_count, is_public, is_exported, is_entry_point
        )

        return UsageMetrics(
            caller_count=caller_count,
            is_public=is_public,
            is_exported=is_exported,
            is_entry_point=is_entry_point,
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
            pattern = r"\b([a-zA-Z_][a-zA-Z0-9_]*)\s*\("
        elif language.lower() in ["javascript", "typescript"]:
            # Match: functionName( or object.method(
            pattern = r"\b([a-zA-Z_$][a-zA-Z0-9_$]*)\s*\("
        elif language.lower() in ["java", "go", "rust"]:
            # Match: functionName( or object.method(
            pattern = r"\b([a-zA-Z_][a-zA-Z0-9_]*)\s*\("
        else:
            pattern = r"\b([a-zA-Z_][a-zA-Z0-9_]*)\s*\("

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
            return not name.startswith("_")
        elif language.lower() in ["javascript", "typescript"]:
            # Underscore or hash prefix = private
            return not name.startswith("_") and not name.startswith("#")
        elif language.lower() == "go":
            # Lowercase first letter = unexported (private)
            return name[0].isupper() if name else False
        else:
            # Default: assume underscore prefix = private
            return not name.startswith("_")

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
            all_match = re.search(r"__all__\s*=\s*\[(.*?)\]", file_content, re.DOTALL)
            if all_match:
                exports = all_match.group(1)
                # Check if name is in the list
                return f'"{name}"' in exports or f"'{name}'" in exports
            # If no __all__, assume public functions are exported
            return not name.startswith("_")

        elif language.lower() in ["javascript", "typescript"]:
            # Check for export keyword
            export_patterns = [
                rf"export\s+(function|class|const|let|var)\s+{re.escape(name)}\b",
                rf"export\s+\{{[^}}]*\b{re.escape(name)}\b[^}}]*\}}",  # export { func1, func2 }
                rf"export\s+default\s+{re.escape(name)}\b",
            ]
            for pattern in export_patterns:
                if re.search(pattern, file_content):
                    return True
            return False

        elif language.lower() == "java":
            # Check for public modifier in class/method declaration
            # More flexible pattern to match methods: public void methodName()
            pattern = rf"\bpublic\s+(\w+\s+)*{re.escape(name)}\s*\("
            return bool(re.search(pattern, file_content))

        elif language.lower() == "go":
            # Exported = uppercase first letter
            return name[0].isupper() if name else False

        else:
            # Default: assume not exported unless we can detect it
            return False

    def _is_entry_point(self, file_path: Optional[Path]) -> bool:
        """
        Determine if code is in an entry point file.

        Entry point files:
        - __init__.py (package initialization)
        - main.py, app.py, api.py (application entry points)
        - Files in 'api', 'core', 'routes' directories

        Args:
            file_path: Path to the file containing this code unit

        Returns:
            True if in an entry point file, False otherwise
        """
        if not file_path:
            return False

        filename = file_path.name.lower()
        path_parts = [p.lower() for p in file_path.parts]

        # Entry point filenames
        entry_point_files = [
            "__init__.py",
            "main.py",
            "app.py",
            "api.py",
            "server.py",
            "cli.py",
        ]
        if filename in entry_point_files:
            return True

        # Entry point directories
        entry_point_dirs = ["api", "core", "routes", "endpoints", "handlers"]
        if any(dir_name in path_parts for dir_name in entry_point_dirs):
            return True

        return False

    def _calculate_usage_boost(
        self,
        caller_count: int,
        is_public: bool,
        is_exported: bool,
        is_entry_point: bool,
    ) -> float:
        """
        Calculate usage boost (0.0-0.2 range).

        Formula:
        - Caller count: 0-10+ callers = 0.0-0.10 boost
        - Public API: +0.03 boost
        - Explicitly exported: +0.03 boost
        - Entry point file: +0.04 boost
        """
        boost = 0.0

        # Caller count boost (0.0-0.10, reduced from 0.12 to make room for entry point)
        if caller_count >= self.HIGH_USAGE_THRESHOLD:
            boost += 0.10
        elif caller_count >= self.MEDIUM_USAGE_THRESHOLD:
            # Scale from 0.03 to 0.10
            ratio = (caller_count - self.MEDIUM_USAGE_THRESHOLD) / (
                self.HIGH_USAGE_THRESHOLD - self.MEDIUM_USAGE_THRESHOLD
            )
            boost += 0.03 + (ratio * 0.07)
        elif caller_count > 0:
            # Scale from 0.0 to 0.03
            ratio = caller_count / self.MEDIUM_USAGE_THRESHOLD
            boost += ratio * 0.03

        # Public API boost
        if is_public:
            boost += 0.03

        # Export boost
        if is_exported:
            boost += 0.03

        # Entry point boost (new!)
        if is_entry_point:
            boost += 0.04

        return min(boost, self.MAX_USAGE_BOOST)

    def reset(self) -> None:
        """Reset call graph (call between files)."""
        self.call_graph = {}
