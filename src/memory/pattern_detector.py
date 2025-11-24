"""Pattern detection for proactive context suggestions.

This module analyzes conversation messages to detect patterns that suggest
the user would benefit from relevant code or memory context.
"""

import re
import logging
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class PatternType(Enum):
    """Types of conversation patterns we detect."""

    IMPLEMENTATION_REQUEST = "implementation_request"
    ERROR_DEBUGGING = "error_debugging"
    CODE_QUESTION = "code_question"
    REFACTORING_CHANGE = "refactoring_change"


@dataclass
class DetectedPattern:
    """A detected conversation pattern."""

    pattern_type: PatternType
    confidence: float  # 0-1
    entities: List[str]  # Extracted entities (e.g., "authentication", "login")
    trigger_text: str  # The text that triggered the pattern
    search_query: str  # Suggested search query
    search_strategy: str  # How to search (e.g., "find_similar_code", "search_code")

    def __repr__(self) -> str:
        return (
            f"DetectedPattern(type={self.pattern_type.value}, "
            f"confidence={self.confidence:.2f}, "
            f"query='{self.search_query}')"
        )


class PatternDetector:
    """
    Detect conversation patterns that suggest relevant context.

    Analyzes user messages to identify:
    - Implementation requests ("I need to add X")
    - Error debugging ("Why isn't X working?")
    - Code questions ("How does X work?")
    - Refactoring changes ("Change X to Y")

    Each pattern has associated:
    - Confidence score (0-1)
    - Extracted entities
    - Suggested search query
    - Search strategy
    """

    # Pattern definitions with triggers and base confidence
    PATTERNS: Dict[PatternType, Dict] = {
        PatternType.IMPLEMENTATION_REQUEST: {
            "triggers": [
                r"\b(I|we|let\'s|need to|want to|should) (add|implement|create|build|make|write)\b",
                r"\bhow (do|can|should) (I|we) (add|implement|create|build)\b",
                r"\b(add|implement|create|build) (a|an|the|new)\b",
                r"\bI\'m (adding|implementing|creating|building|writing)\b",
            ],
            "confidence_base": 0.85,
            "confidence_boost": {
                "feature": 0.05,
                "function": 0.05,
                "class": 0.05,
                "api": 0.03,
                "endpoint": 0.03,
            },
            "search_strategy": "find_similar_code",
        },
        PatternType.ERROR_DEBUGGING: {
            "triggers": [
                r"\b(why|when) (is|isn\'t|does|doesn\'t|are|aren\'t|do|don\'t)\b",
                r"\b(error|exception|fail|failing|failed|broken|bug|issue)\b",
                r"\b(not working|doesn\'t work|won\'t work|can\'t get|isn\'t working|aren\'t working)\b",
                r"\b(getting|receiving|seeing) (an?|the) (error|exception)\b",
                r"\bthrows? (an?|the)? (error|exception)\b",
            ],
            "confidence_base": 0.90,
            "confidence_boost": {
                "error": 0.05,
                "exception": 0.05,
                "stack": 0.03,
                "trace": 0.03,
            },
            "search_strategy": "search_code",
        },
        PatternType.CODE_QUESTION: {
            "triggers": [
                r"\b(how does|how do|what does|what do|what is|what are)\b",
                r"\b(explain|understand|tell me about|show me)\b",
                r"\b(where is|where are|find)\b",
                r"\bwhat\'s (the|this)\b",
                r"\bcan you (explain|show|tell)\b",
            ],
            "confidence_base": 0.75,
            "confidence_boost": {
                "function": 0.05,
                "class": 0.05,
                "method": 0.05,
                "module": 0.03,
                "work": 0.02,
            },
            "search_strategy": "search_code",
        },
        PatternType.REFACTORING_CHANGE: {
            "triggers": [
                r"\b(change|modify|update|alter|edit|fix)\b",
                r"\b(refactor|reorganize|restructure|rewrite)\b",
                r"\b(replace|swap|substitute) .+ (with|to|for)\b",
                r"\b(rename|move|delete|remove)\b",
                r"\blet\'s (change|modify|update|refactor)\b",
            ],
            "confidence_base": 0.80,
            "confidence_boost": {
                "all": 0.05,  # "change all X to Y"
                "everywhere": 0.05,
                "function": 0.03,
                "class": 0.03,
            },
            "search_strategy": "search_code",
        },
    }

    def __init__(self):
        """Initialize the pattern detector."""
        # Compile regex patterns for efficiency
        self._compiled_patterns: Dict[PatternType, List[re.Pattern]] = {}
        for pattern_type, config in self.PATTERNS.items():
            self._compiled_patterns[pattern_type] = [
                re.compile(trigger, re.IGNORECASE) for trigger in config["triggers"]
            ]

        logger.info("Initialized PatternDetector with 4 pattern types")

    def detect_patterns(self, message: str) -> List[DetectedPattern]:
        """
        Detect patterns in a user message.

        Args:
            message: The user's message to analyze

        Returns:
            List of detected patterns with confidence scores (may be empty)
        """
        if not message or not message.strip():
            return []

        detected: List[DetectedPattern] = []

        for pattern_type in PatternType:
            pattern = self._detect_pattern_type(message, pattern_type)
            if pattern:
                detected.append(pattern)

        # Sort by confidence (highest first)
        detected.sort(key=lambda p: p.confidence, reverse=True)

        if detected:
            logger.info(
                f"Detected {len(detected)} patterns in message: "
                f"{[p.pattern_type.value for p in detected]}"
            )
        else:
            logger.debug("No patterns detected in message")

        return detected

    def _detect_pattern_type(
        self, message: str, pattern_type: PatternType
    ) -> Optional[DetectedPattern]:
        """
        Check if a specific pattern type matches the message.

        Args:
            message: The user's message
            pattern_type: The pattern type to check

        Returns:
            DetectedPattern if matched, None otherwise
        """
        config = self.PATTERNS[pattern_type]
        compiled_patterns = self._compiled_patterns[pattern_type]

        # Check if any trigger matches
        matched_trigger = None
        trigger_text = ""

        for pattern in compiled_patterns:
            match = pattern.search(message)
            if match:
                matched_trigger = pattern
                trigger_text = match.group(0)
                break

        if not matched_trigger:
            return None

        # Calculate confidence
        base_confidence = config["confidence_base"]
        confidence_boost = 0.0

        # Apply confidence boosts for relevant keywords
        message_lower = message.lower()
        for keyword, boost in config.get("confidence_boost", {}).items():
            if keyword in message_lower:
                confidence_boost += boost

        # Final confidence (capped at 0.99)
        confidence = min(0.99, base_confidence + confidence_boost)

        # Extract entities (potential search terms)
        entities = self._extract_entities(message, pattern_type)

        # Generate search query
        search_query = self._generate_search_query(message, pattern_type, entities)

        # Get search strategy
        search_strategy = config["search_strategy"]

        return DetectedPattern(
            pattern_type=pattern_type,
            confidence=confidence,
            entities=entities,
            trigger_text=trigger_text,
            search_query=search_query,
            search_strategy=search_strategy,
        )

    def _extract_entities(
        self, message: str, pattern_type: PatternType
    ) -> List[str]:
        """
        Extract relevant entities from the message.

        Args:
            message: The user's message
            pattern_type: The detected pattern type

        Returns:
            List of extracted entity strings
        """
        entities = []

        # Common technical terms to extract
        tech_terms = [
            # Programming concepts
            r"\b(function|method|class|interface|type|struct|enum)\b",
            r"\b(api|endpoint|route|handler|controller)\b",
            r"\b(database|db|table|model|schema|query)\b",
            r"\b(authentication|auth|authorization|login|logout)\b",
            r"\b(error|exception|validation|parsing|serialization)\b",
            r"\b(cache|session|token|cookie|storage)\b",
            r"\b(test|testing|mock|fixture|assert)\b",
            r"\b(config|configuration|settings|environment)\b",
            # Specific implementations
            r"\b[A-Z][a-z]+(?:[A-Z][a-z]+)+\b",  # CamelCase identifiers
            r"\b[a-z_]+[a-z0-9_]*\b(?=\(\))",  # function_name()
        ]

        # Extract matches
        for pattern in tech_terms:
            matches = re.findall(pattern, message, re.IGNORECASE)
            entities.extend(matches)

        # Deduplicate and clean (preserve order using dict)
        cleaned = [e.strip().lower() for e in entities if e.strip()]
        entities = list(dict.fromkeys(cleaned))  # Preserves insertion order (Python 3.7+)

        return entities[:10]  # Limit to top 10 entities

    def _generate_search_query(
        self, message: str, pattern_type: PatternType, entities: List[str]
    ) -> str:
        """
        Generate a search query based on the message and detected pattern.

        Args:
            message: The user's message
            pattern_type: The detected pattern type
            entities: Extracted entities

        Returns:
            Search query string
        """
        # Start with entities
        if entities:
            query_parts = entities[:3]  # Use top 3 entities
        else:
            # Fallback: extract nouns from message
            # Simple approach: get words that aren't common stop words
            stop_words = {
                "i",
                "we",
                "the",
                "a",
                "an",
                "to",
                "of",
                "in",
                "on",
                "at",
                "for",
                "with",
                "by",
                "is",
                "are",
                "was",
                "were",
                "be",
                "been",
                "being",
                "have",
                "has",
                "had",
                "do",
                "does",
                "did",
                "will",
                "would",
                "should",
                "can",
                "could",
                "may",
                "might",
                "must",
                "how",
                "what",
                "why",
                "when",
                "where",
                "who",
            }

            words = message.lower().split()
            query_parts = [w for w in words if w not in stop_words and len(w) > 2][:5]

        # Pattern-specific adjustments
        if pattern_type == PatternType.IMPLEMENTATION_REQUEST:
            # Focus on implementation details
            if "add" in message.lower():
                query_parts.insert(0, "implementation")
            elif "create" in message.lower():
                query_parts.insert(0, "create")

        elif pattern_type == PatternType.ERROR_DEBUGGING:
            # Include error-related terms
            if "error" in message.lower():
                query_parts.append("error")
            if "exception" in message.lower():
                query_parts.append("exception")

        # Join into query
        search_query = " ".join(query_parts[:5])  # Limit to 5 terms

        return search_query.strip()

    def get_explanation(self, message: str) -> str:
        """
        Get human-readable explanation of detected patterns.

        Args:
            message: The message to analyze

        Returns:
            Explanation string
        """
        patterns = self.detect_patterns(message)

        if not patterns:
            return "No patterns detected in this message."

        explanation = f"Detected {len(patterns)} pattern(s):\n\n"

        for i, pattern in enumerate(patterns, 1):
            explanation += f"{i}. {pattern.pattern_type.value.replace('_', ' ').title()}\n"
            explanation += f"   Confidence: {pattern.confidence:.2%}\n"
            explanation += f"   Trigger: \"{pattern.trigger_text}\"\n"
            explanation += f"   Search query: \"{pattern.search_query}\"\n"
            explanation += f"   Strategy: {pattern.search_strategy}\n"
            if pattern.entities:
                explanation += f"   Entities: {', '.join(pattern.entities[:5])}\n"
            explanation += "\n"

        return explanation
