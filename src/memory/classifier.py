"""Context level classification for memory stratification."""

import re
from typing import Dict, List
from src.core.models import ContextLevel, MemoryCategory


class ContextLevelClassifier:
    """
    Classifier for automatically determining the context level of memories.

    This classifier uses heuristic rules and pattern matching to determine
    whether a memory is a user preference, project context, or session state.
    """

    # Keywords that indicate user preferences
    USER_PREFERENCE_KEYWORDS = [
        r"\bprefer(s|red|ence)?\b",
        r"\blike(s)?\b",
        r"\bdislike(s)?\b",
        r"\bfavorite\b",
        r"\balways\b",
        r"\bnever\b",
        r"\busually\b",
        r"\bmy style\b",
        r"\bmy way\b",
        r"\bhow I (do|work|code|write)\b",
        r"\bI (prefer|like|love|hate|want)\b",
        r"\bshould (always|never)\b",
        r"\bdefault to\b",
        r"\bguideline(s)?\b",
        r"\bconvention(s)?\b",
    ]

    # Keywords that indicate project context
    PROJECT_CONTEXT_KEYWORDS = [
        r"\bthis project\b",
        r"\bour project\b",
        r"\bthis codebase\b",
        r"\bour codebase\b",
        r"\barchitecture\b",
        r"\bframework\b",
        r"\blibrary\b",
        r"\bdependenc(y|ies)\b",
        r"\bfile structure\b",
        r"\bproject (uses|has|contains)\b",
        r"\bwe (use|have|are using)\b",
        r"\bconfigured (to|with)\b",
        r"\bsetup\b",
        r"\benvironment\b",
        r"\bdeployment\b",
        r"\bCI/CD\b",
        r"\bversion\b",
    ]

    # Keywords that indicate session state
    SESSION_STATE_KEYWORDS = [
        r"\bcurrently\b",
        r"\bworking on\b",
        r"\btoday\b",
        r"\bright now\b",
        r"\bat the moment\b",
        r"\bin progress\b",
        r"\btemporar(y|ily)\b",
        r"\bnext (step|task)\b",
        r"\bjust (did|finished|completed)\b",
        r"\babout to\b",
        r"\bthis (session|conversation)\b",
        r"\bfor now\b",
    ]

    def __init__(self):
        """Initialize the classifier."""
        # Compile regex patterns for efficiency
        self.user_patterns = [
            re.compile(pattern, re.IGNORECASE) for pattern in self.USER_PREFERENCE_KEYWORDS
        ]
        self.project_patterns = [
            re.compile(pattern, re.IGNORECASE) for pattern in self.PROJECT_CONTEXT_KEYWORDS
        ]
        self.session_patterns = [
            re.compile(pattern, re.IGNORECASE) for pattern in self.SESSION_STATE_KEYWORDS
        ]

    def _score_patterns(self, content: str, patterns: List[re.Pattern]) -> float:
        """
        Score content based on how many patterns match.

        Args:
            content: Content to score
            patterns: List of compiled regex patterns

        Returns:
            Score between 0 and 1
        """
        matches = sum(1 for pattern in patterns if pattern.search(content))
        return min(1.0, matches / max(1, len(patterns) * 0.3))  # Normalize to 0-1

    def classify(self, content: str, category: MemoryCategory) -> ContextLevel:
        """
        Classify content into a context level.

        This method uses a combination of:
        1. Content pattern matching
        2. Memory category heuristics
        3. Weighted scoring

        Args:
            content: Memory content to classify
            category: Memory category

        Returns:
            Classified ContextLevel
        """
        # Score against each pattern set
        user_score = self._score_patterns(content, self.user_patterns)
        project_score = self._score_patterns(content, self.project_patterns)
        session_score = self._score_patterns(content, self.session_patterns)

        # Apply category-based boosts
        if category == MemoryCategory.PREFERENCE:
            user_score += 0.5
        elif category == MemoryCategory.CONTEXT:
            project_score += 0.3
        elif category == MemoryCategory.EVENT:
            session_score += 0.3
        elif category == MemoryCategory.WORKFLOW:
            project_score += 0.2

        # Additional heuristics
        content_lower = content.lower()

        # User preference indicators
        if any(word in content_lower for word in ["prefer", "always", "never", "like", "dislike"]):
            user_score += 0.2

        # Project context indicators
        if any(word in content_lower for word in ["project", "codebase", "architecture", "framework"]):
            project_score += 0.2

        # Session state indicators
        if any(word in content_lower for word in ["currently", "working on", "today", "right now"]):
            session_score += 0.2

        # Code-related content often belongs to project context
        if re.search(r"(class|function|method|variable|import|package|module)\s+\w+", content_lower):
            project_score += 0.3

        # Commands or immediate actions suggest session state
        if re.search(r"^(let's|please|can you|could you|would you)", content_lower):
            session_score += 0.2

        # Determine the highest scoring category
        scores = {
            ContextLevel.USER_PREFERENCE: user_score,
            ContextLevel.PROJECT_CONTEXT: project_score,
            ContextLevel.SESSION_STATE: session_score,
        }

        # Return the context level with the highest score
        max_level = max(scores, key=scores.get)

        # If all scores are low, default based on category
        if scores[max_level] < 0.3:
            return self._default_for_category(category)

        return max_level

    def _default_for_category(self, category: MemoryCategory) -> ContextLevel:
        """
        Get default context level for a category.

        Args:
            category: Memory category

        Returns:
            Default ContextLevel for the category
        """
        defaults = {
            MemoryCategory.PREFERENCE: ContextLevel.USER_PREFERENCE,
            MemoryCategory.FACT: ContextLevel.PROJECT_CONTEXT,
            MemoryCategory.EVENT: ContextLevel.SESSION_STATE,
            MemoryCategory.WORKFLOW: ContextLevel.PROJECT_CONTEXT,
            MemoryCategory.CONTEXT: ContextLevel.PROJECT_CONTEXT,
        }
        return defaults.get(category, ContextLevel.PROJECT_CONTEXT)

    def classify_batch(
        self, items: List[tuple[str, MemoryCategory]]
    ) -> List[ContextLevel]:
        """
        Classify multiple items in batch.

        Args:
            items: List of (content, category) tuples

        Returns:
            List of ContextLevels
        """
        return [self.classify(content, category) for content, category in items]

    def get_classification_confidence(
        self, content: str, category: MemoryCategory
    ) -> Dict[ContextLevel, float]:
        """
        Get confidence scores for all context levels.

        Args:
            content: Content to classify
            category: Memory category

        Returns:
            Dictionary mapping ContextLevel to confidence score (0-1)
        """
        user_score = self._score_patterns(content, self.user_patterns)
        project_score = self._score_patterns(content, self.project_patterns)
        session_score = self._score_patterns(content, self.session_patterns)

        # Apply category boosts
        if category == MemoryCategory.PREFERENCE:
            user_score += 0.5
        elif category == MemoryCategory.CONTEXT:
            project_score += 0.3
        elif category == MemoryCategory.EVENT:
            session_score += 0.3

        # Normalize scores to sum to 1.0
        total = user_score + project_score + session_score
        if total > 0:
            user_score /= total
            project_score /= total
            session_score /= total

        return {
            ContextLevel.USER_PREFERENCE: user_score,
            ContextLevel.PROJECT_CONTEXT: project_score,
            ContextLevel.SESSION_STATE: session_score,
        }


# Global classifier instance
_classifier: ContextLevelClassifier = None


def get_classifier() -> ContextLevelClassifier:
    """
    Get or create the global classifier instance.

    Returns:
        ContextLevelClassifier instance
    """
    global _classifier
    if _classifier is None:
        _classifier = ContextLevelClassifier()
    return _classifier


def classify_content(content: str, category: MemoryCategory) -> ContextLevel:
    """
    Convenience function to classify content.

    Args:
        content: Content to classify
        category: Memory category

    Returns:
        Classified ContextLevel
    """
    classifier = get_classifier()
    return classifier.classify(content, category)
