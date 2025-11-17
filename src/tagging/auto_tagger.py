"""Auto-tagging engine for extracting tags from memory content."""

import re
from typing import List, Dict, Tuple
from collections import Counter


class AutoTagger:
    """
    Automatic tag extraction from memory content.

    Features:
    - Keyword extraction using word frequency
    - Language detection
    - Framework and technology detection
    - Pattern recognition
    - Hierarchical tag inference
    """

    # Language indicators
    LANGUAGE_PATTERNS = {
        "python": [
            r"\bimport\b",
            r"\bdef\b",
            r"\bclass\b",
            r"\basync\b",
            r"\bawait\b",
            r"\.py\b",
            r"\bdjango\b",
            r"\bflask\b",
            r"\bfastapi\b",
        ],
        "javascript": [
            r"\bconst\b",
            r"\blet\b",
            r"\bvar\b",
            r"\bfunction\b",
            r"=>",
            r"\.js\b",
            r"\.jsx\b",
            r"\bnode\b",
        ],
        "typescript": [
            r"\binterface\b",
            r"\btype\b",
            r":\s*(string|number|boolean)",
            r"\.ts\b",
            r"\.tsx\b",
        ],
        "java": [r"\bpublic\s+class\b", r"\bprivate\b", r"\bstatic\b", r"\.java\b"],
        "go": [r"\bfunc\b", r"\bpackage\b", r"\.go\b", r"\bgoroutine\b"],
        "rust": [r"\bfn\b", r"\bimpl\b", r"\btrait\b", r"\.rs\b", r"\bcargo\b"],
    }

    # Framework indicators
    FRAMEWORK_PATTERNS = {
        "react": [
            r"\bReact\b",
            r"\buseState\b",
            r"\buseEffect\b",
            r"\bjsx\b",
            r"\bcomponent\b",
        ],
        "fastapi": [r"\bFastAPI\b", r"@app\.", r"\bDepends\b", r"\bAPIRouter\b"],
        "django": [r"\bdjango\.", r"\bmodels\.Model\b", r"\bviews\b"],
        "express": [r"\bexpress\(\)", r"\bapp\.get\b", r"\breq\.", r"\bres\."],
        "flask": [r"\bFlask\b", r"@app\.route", r"\brender_template\b"],
        "nextjs": [r"\bNext\.js\b", r"\bgetServerSideProps\b", r"\bgetStaticProps\b"],
    }

    # Pattern indicators
    PATTERN_KEYWORDS = {
        "async": [
            r"\basync\b",
            r"\bawait\b",
            r"\bPromise\b",
            r"\basyncio\b",
            r"\bcoroutine\b",
        ],
        "singleton": [r"\bsingleton\b", r"\b__instance\b", r"\bgetInstance\b"],
        "factory": [r"\bfactory\b", r"\bcreate\b", r"\bmake\b", r"\bbuilder\b"],
        "observer": [r"\bobserver\b", r"\bsubscribe\b", r"\bnotify\b", r"\bevent\b"],
    }

    # Domain indicators
    DOMAIN_KEYWORDS = {
        "database": [
            r"\bsql\b",
            r"\bquery\b",
            r"\bdatabase\b",
            r"\btable\b",
            r"\bindex\b",
            r"\bpostgres\b",
            r"\bmongo\b",
        ],
        "api": [
            r"\bendpoint\b",
            r"\brequest\b",
            r"\bresponse\b",
            r"\broute\b",
            r"\bhandler\b",
            r"\brest\b",
            r"\bgraphql\b",
        ],
        "auth": [
            r"\blogin\b",
            r"\bauth\b",
            r"\btoken\b",
            r"\bsession\b",
            r"\bpassword\b",
            r"\bjwt\b",
        ],
        "testing": [
            r"\btest\b",
            r"\bmock\b",
            r"\bassert\b",
            r"\bpytest\b",
            r"\bjest\b",
            r"\bunit\b",
        ],
    }

    def __init__(self, min_confidence: float = 0.6):
        """
        Initialize auto-tagger.

        Args:
            min_confidence: Minimum confidence threshold for auto-tags (0-1)
        """
        self.min_confidence = min_confidence

    def extract_tags(
        self, content: str, max_tags: int = 10
    ) -> List[Tuple[str, float]]:
        """
        Extract tags from content with confidence scores.

        Args:
            content: Memory content to analyze
            max_tags: Maximum number of tags to return

        Returns:
            List of (tag, confidence) tuples, sorted by confidence
        """
        tags: Dict[str, float] = {}

        # Extract language tags
        language_tags = self._detect_languages(content)
        tags.update(language_tags)

        # Extract framework tags
        framework_tags = self._detect_frameworks(content)
        tags.update(framework_tags)

        # Extract pattern tags
        pattern_tags = self._detect_patterns(content)
        tags.update(pattern_tags)

        # Extract domain tags
        domain_tags = self._detect_domains(content)
        tags.update(domain_tags)

        # Extract keyword tags
        keyword_tags = self._extract_keywords(content)
        tags.update(keyword_tags)

        # Filter by confidence and sort
        filtered_tags = [
            (tag, conf) for tag, conf in tags.items() if conf >= self.min_confidence
        ]
        filtered_tags.sort(key=lambda x: x[1], reverse=True)

        return filtered_tags[:max_tags]

    def infer_hierarchical_tags(self, tags: List[str]) -> List[str]:
        """
        Infer hierarchical tags from flat tag list.

        Args:
            tags: List of flat tags

        Returns:
            List of hierarchical tags (e.g., "language/python", "language/python/async")
        """
        hierarchical = []

        for tag in tags:
            # Language hierarchies
            if tag in ["python", "javascript", "typescript", "java", "go", "rust"]:
                hierarchical.append(f"language/{tag}")

                # Add sub-tags if found
                if "async" in tags:
                    hierarchical.append(f"language/{tag}/async")
                if "decorators" in tags and tag == "python":
                    hierarchical.append(f"language/python/decorators")
                if "promises" in tags and tag == "javascript":
                    hierarchical.append(f"language/javascript/promises")
                if "types" in tags and tag == "typescript":
                    hierarchical.append(f"language/typescript/types")

            # Framework hierarchies
            elif tag in [
                "react",
                "fastapi",
                "django",
                "express",
                "flask",
                "nextjs",
            ]:
                hierarchical.append(f"framework/{tag}")

            # Pattern hierarchies
            elif tag in ["singleton", "factory", "observer"]:
                hierarchical.append(f"pattern/{tag}")
            elif tag == "async":
                hierarchical.append("pattern/async")

            # Domain hierarchies
            elif tag in ["database", "api", "auth", "testing"]:
                hierarchical.append(f"domain/{tag}")

            # Keep flat tag as well
            hierarchical.append(tag)

        return list(set(hierarchical))  # Remove duplicates

    def _detect_languages(self, content: str) -> Dict[str, float]:
        """Detect programming languages in content."""
        content_lower = content.lower()
        detected = {}

        for lang, patterns in self.LANGUAGE_PATTERNS.items():
            matches = sum(
                1 for pattern in patterns if re.search(pattern, content, re.IGNORECASE)
            )
            if matches > 0:
                # Confidence based on number of pattern matches
                confidence = min(0.9, 0.5 + (matches * 0.1))
                detected[lang] = confidence

        return detected

    def _detect_frameworks(self, content: str) -> Dict[str, float]:
        """Detect frameworks in content."""
        detected = {}

        for framework, patterns in self.FRAMEWORK_PATTERNS.items():
            matches = sum(
                1 for pattern in patterns if re.search(pattern, content, re.IGNORECASE)
            )
            if matches > 0:
                confidence = min(0.95, 0.6 + (matches * 0.15))
                detected[framework] = confidence

        return detected

    def _detect_patterns(self, content: str) -> Dict[str, float]:
        """Detect design patterns in content."""
        detected = {}

        for pattern, keywords in self.PATTERN_KEYWORDS.items():
            matches = sum(
                1 for keyword in keywords if re.search(keyword, content, re.IGNORECASE)
            )
            if matches > 0:
                confidence = min(0.85, 0.5 + (matches * 0.15))
                detected[pattern] = confidence

        return detected

    def _detect_domains(self, content: str) -> Dict[str, float]:
        """Detect technical domains in content."""
        detected = {}

        for domain, keywords in self.DOMAIN_KEYWORDS.items():
            matches = sum(
                1 for keyword in keywords if re.search(keyword, content, re.IGNORECASE)
            )
            if matches > 0:
                confidence = min(0.8, 0.5 + (matches * 0.1))
                detected[domain] = confidence

        return detected

    def _extract_keywords(self, content: str, min_word_length: int = 4) -> Dict[str, float]:
        """Extract high-frequency keywords as tags."""
        # Tokenize content
        words = re.findall(r"\b[a-z_][a-z0-9_]*\b", content.lower())

        # Filter out very common words and short words
        stopwords = {
            "the",
            "is",
            "at",
            "which",
            "on",
            "a",
            "an",
            "as",
            "are",
            "was",
            "were",
            "been",
            "be",
            "have",
            "has",
            "had",
            "do",
            "does",
            "did",
            "will",
            "would",
            "should",
            "could",
            "can",
            "may",
            "might",
            "must",
            "this",
            "that",
            "these",
            "those",
            "and",
            "but",
            "or",
            "for",
            "nor",
            "so",
            "yet",
            "to",
            "from",
            "in",
            "out",
            "with",
            "by",
            "about",
        }

        filtered_words = [
            w for w in words if len(w) >= min_word_length and w not in stopwords
        ]

        # Count frequencies
        word_counts = Counter(filtered_words)

        # Convert to tags with confidence based on frequency
        total_words = len(filtered_words)
        if total_words == 0:
            return {}

        keyword_tags = {}
        for word, count in word_counts.most_common(5):  # Top 5 keywords
            # Confidence based on frequency (normalized)
            confidence = min(0.7, 0.4 + (count / total_words) * 2)
            keyword_tags[word] = confidence

        return keyword_tags
