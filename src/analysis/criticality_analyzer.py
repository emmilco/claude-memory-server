"""
Criticality analyzer for code importance scoring.

Analyzes criticality indicators to identify security-sensitive, error-critical,
and infrastructure-essential code. Provides boost scores (0.0-0.3) that amplify
importance for code with critical characteristics.

Criticality Indicators:
- Security keywords: auth, crypto, token, permission, session (40+ patterns)
- Error handling: try/catch/except, assertions, validation checks
- Critical decorators: @security, @auth, @permission, @critical
- File proximity: Distance from entry points (main, __init__, api)

Boost Calculation:
- Security keywords (1-3+): +0.02 to +0.10
- Error handling present: +0.03
- Critical decorator present: +0.05
- File proximity (0.0-1.0): +0.00 to +0.02
- Maximum total boost: 0.3 (30% importance increase)

Language Support:
- Python: try/except, @decorator, if not/assert patterns
- JavaScript/TypeScript: try/catch, decorators, null checks
- Java: try/catch, @annotations, throws declarations
- Go: if err != nil, defer, panic patterns
- Rust: Result<>, Option<>, match, ? operator

Architecture:
- Independent analyzer with no external dependencies
- Configurable via MAX_CRITICALITY_BOOST constant
- Thread-safe (stateless design)
- Used by ImportanceScorer to calculate final importance

Example:
    ```python
    analyzer = CriticalityAnalyzer()
    metrics = analyzer.analyze(
        code_unit={'name': 'authenticate', 'content': code, 'language': 'python'},
        file_path=Path('src/auth/login.py')
    )
    # metrics.criticality_boost = 0.15 (security keywords + error handling)
    ```

Part of FEAT-049: Intelligent Code Importance Scoring
"""

import re
import logging
from typing import Dict, Any, List, Optional, Set
from pathlib import Path
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class CriticalityMetrics:
    """Container for criticality analysis results."""

    security_keywords: List[str]
    has_error_handling: bool
    has_critical_decorator: bool
    file_proximity_score: float
    criticality_boost: float  # Boost to add to base score (0.0-0.3)


class CriticalityAnalyzer:
    """Analyzes criticality indicators to estimate code importance."""

    # Criticality boost ranges (expanded from 0.2 to 0.3 to better reward critical code)
    MAX_CRITICALITY_BOOST = 0.3

    # Security-related keywords (context-aware)
    SECURITY_KEYWORDS = {
        "auth", "authenticate", "authorization", "authorize", "login", "logout",
        "password", "credential", "token", "session", "cookie", "jwt",
        "encrypt", "decrypt", "hash", "crypto", "cipher", "sign", "verify",
        "permission", "privilege", "access_control", "role", "grant", "revoke",
        "security", "vulnerable", "exploit", "sanitize", "validate", "escape",
        "sql_injection", "xss", "csrf", "secret", "private_key", "api_key",
    }

    # Critical decorators/annotations
    CRITICAL_DECORATORS = {
        "python": ["@critical", "@security", "@auth", "@permission", "@admin", "@require"],
        "javascript": ["@Critical", "@Security", "@Auth", "@Permission", "@Admin"],
        "typescript": ["@Critical", "@Security", "@Auth", "@Permission", "@Admin"],
        "java": ["@Critical", "@Security", "@Auth", "@Permission", "@Admin", "@Secured"],
        "go": ["// @critical", "// @security", "// @auth"],
        "rust": ["#[critical]", "#[security]", "#[auth]"],
    }

    # Entry point indicators (file-level)
    ENTRY_POINT_NAMES = {
        "main", "__main__", "index", "app", "server", "init", "__init__",
        "bootstrap", "startup", "entry", "run",
    }

    def __init__(self):
        """Initialize criticality analyzer."""
        pass

    def analyze(
        self,
        code_unit: Dict[str, Any],
        file_path: Optional[Path] = None,
    ) -> CriticalityMetrics:
        """
        Analyze criticality indicators of a code unit.

        Args:
            code_unit: Dictionary with keys:
                - name: Function/class name
                - content: Full code content
                - unit_type: "function", "class", or "method"
                - language: Programming language
            file_path: Path to the file (for proximity scoring)

        Returns:
            CriticalityMetrics with calculated metrics and boost
        """
        name = code_unit.get("name", "")
        content = code_unit.get("content", "")
        unit_type = code_unit.get("unit_type", "function")
        language = code_unit.get("language", "python")

        # Calculate metrics
        security_kw = self._find_security_keywords(name, content)
        has_error = self._has_error_handling(content, language)
        has_decorator = self._has_critical_decorator(content, language)
        proximity = self._calculate_file_proximity(file_path, name) if file_path else 0.0

        # Calculate criticality boost
        boost = self._calculate_criticality_boost(
            security_kw, has_error, has_decorator, proximity
        )

        return CriticalityMetrics(
            security_keywords=security_kw,
            has_error_handling=has_error,
            has_critical_decorator=has_decorator,
            file_proximity_score=proximity,
            criticality_boost=boost,
        )

    def _find_security_keywords(self, name: str, content: str) -> List[str]:
        """
        Find security-related keywords in name and content.

        Uses context-aware matching to avoid false positives.
        """
        found = []
        combined_text = (name + " " + content).lower()

        for keyword in self.SECURITY_KEYWORDS:
            # Check if keyword appears as a whole word (not substring)
            pattern = rf'\b{re.escape(keyword)}\b'
            if re.search(pattern, combined_text):
                found.append(keyword)

        return found

    def _has_error_handling(self, content: str, language: str) -> bool:
        """
        Check if code has error handling patterns.

        Detects:
        - try/catch/except blocks
        - Error return patterns
        - Validation checks
        """
        # Language-specific error handling patterns
        patterns = {
            "python": [
                r'\btry\b', r'\bexcept\b', r'\bfinally\b', r'\braise\b',
                r'\bassert\b', r'\bif\s+not\b', r'\bif\s+.*\s+is\s+None\b',
            ],
            "javascript": [
                r'\btry\b', r'\bcatch\b', r'\bfinally\b', r'\bthrow\b',
                r'\.catch\(', r'if\s*\(.*===.*null\)', r'if\s*\(!',
            ],
            "typescript": [
                r'\btry\b', r'\bcatch\b', r'\bfinally\b', r'\bthrow\b',
                r'\.catch\(', r'if\s*\(.*===.*null\)', r'if\s*\(!',
            ],
            "java": [
                r'\btry\b', r'\bcatch\b', r'\bfinally\b', r'\bthrow\b',
                r'\bthrows\b', r'if\s*\(.*==.*null\)', r'if\s*\(!',
            ],
            "go": [
                r'if\s+err\s*!=\s*nil', r'panic\(', r'defer\b',
                r'if\s+.*\s*==\s*nil', r'errors\.New',
            ],
            "rust": [
                r'\bResult<', r'\bOption<', r'\.unwrap\(', r'\.expect\(',
                r'\bmatch\b', r'\bif\s+let\b', r'\?', r'panic!',
            ],
        }

        lang_patterns = patterns.get(language.lower(), patterns["python"])

        for pattern in lang_patterns:
            if re.search(pattern, content):
                return True

        return False

    def _has_critical_decorator(self, content: str, language: str) -> bool:
        """Check if code has critical decorators/annotations."""
        decorators = self.CRITICAL_DECORATORS.get(language.lower(), [])

        for decorator in decorators:
            if decorator in content:
                return True

        return False

    def _calculate_file_proximity(self, file_path: Path, function_name: str) -> float:
        """
        Calculate proximity to entry points (0.0-1.0).

        Higher score for:
        - Files named main, index, app, __init__
        - Functions named main, run, start
        - Files in root or top-level directories
        """
        score = 0.0

        # Validate file_path type early
        if not isinstance(file_path, Path):
            logger.warning(
                f"Expected Path object for proximity calculation, got {type(file_path).__name__}: {file_path}"
            )
            # Can only score function name, skip file-based scoring
            func_name = function_name.lower()
            if func_name in self.ENTRY_POINT_NAMES:
                score += 0.3
            return min(score, 1.0)

        # Check file name
        try:
            file_name = file_path.stem.lower()
            if file_name in self.ENTRY_POINT_NAMES:
                score += 0.5
        except (AttributeError, OSError) as e:
            logger.debug(f"Could not extract file name from {file_path}: {e}")

        # Check function name
        func_name = function_name.lower()
        if func_name in self.ENTRY_POINT_NAMES:
            score += 0.3

        # Check directory depth (lower depth = closer to root = higher score)
        try:
            parts = file_path.parts
            if len(parts) == 0:
                logger.debug(f"Empty path parts for {file_path}, skipping depth scoring")
            else:
                depth = len(parts)
                # Max depth consideration: 10 levels
                depth_score = max(0.0, 1.0 - (depth / 10.0))
                score += depth_score * 0.2
                logger.debug(f"Depth score for {file_path}: {depth_score:.2f} (depth={depth})")
        except (AttributeError, TypeError) as e:
            # Unexpected attribute/type issues
            logger.warning(
                f"Unexpected error calculating depth score for {file_path}: {e}",
                exc_info=True
            )
            # Continue without depth scoring
        except Exception as e:
            # Catch-all for truly unexpected errors - log with full traceback
            logger.error(
                f"Critical error in depth calculation for {file_path}: {e}",
                exc_info=True
            )
            # Don't fail the entire criticality analysis over depth scoring

        return min(score, 1.0)

    def _calculate_criticality_boost(
        self,
        security_keywords: List[str],
        has_error_handling: bool,
        has_critical_decorator: bool,
        file_proximity: float,
    ) -> float:
        """
        Calculate criticality boost (0.0-0.2 range).

        Formula:
        - Security keywords: 1-3+ keywords = 0.02-0.10 boost
        - Error handling: +0.03 boost
        - Critical decorator: +0.05 boost
        - File proximity: 0.0-1.0 = 0.0-0.02 boost
        """
        boost = 0.0

        # Security keywords boost (0.02-0.10)
        kw_count = len(security_keywords)
        if kw_count >= 3:
            boost += 0.10
        elif kw_count == 2:
            boost += 0.06
        elif kw_count == 1:
            boost += 0.02

        # Error handling boost
        if has_error_handling:
            boost += 0.03

        # Critical decorator boost
        if has_critical_decorator:
            boost += 0.05

        # File proximity boost (scaled)
        boost += file_proximity * 0.02

        return min(boost, self.MAX_CRITICALITY_BOOST)
