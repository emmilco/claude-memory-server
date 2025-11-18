"""Intent detection for proactive memory suggestions."""

import re
import logging
from typing import List, Dict, Set, Tuple
from dataclasses import dataclass
from collections import Counter

logger = logging.getLogger(__name__)


@dataclass
class DetectedIntent:
    """Result of intent detection analysis."""

    intent_type: str  # "implementation", "learning", "debugging", "exploration", "general"
    keywords: List[str]  # Extracted technical keywords
    confidence: float  # 0-1 confidence score
    search_query: str  # Synthesized query for memory retrieval
    original_queries: List[str]  # Original queries analyzed


class IntentDetector:
    """
    Detect user intent from conversation context.

    Features:
    - Pattern-based intent detection
    - Keyword extraction from queries
    - Search query synthesis
    - Confidence scoring
    """

    # Intent patterns: (regex pattern, intent_type, confidence_boost)
    INTENT_PATTERNS = [
        # Implementation intent
        (r'\b(implement|add|create|build|write|make)\b', 'implementation', 0.3),
        (r'\b(need to|want to|going to|plan to)\s+(add|create|implement|build)', 'implementation', 0.4),
        (r'\bhow\s+(do|can|should)\s+I\s+(implement|add|create|build)', 'implementation', 0.4),

        # Debugging intent
        (r'\b(debug|fix|error|bug|issue|problem|broken|fail)', 'debugging', 0.3),
        (r'\bwhy\s+(is|does|doesn\'t|isn\'t|won\'t)', 'debugging', 0.3),
        (r'\b(not working|doesn\'t work|won\'t work)', 'debugging', 0.4),

        # Learning intent
        (r'\b(what|how|why)\s+(is|are|does)', 'learning', 0.2),
        (r'\b(explain|understand|learn|know about)', 'learning', 0.3),
        (r'\b(show|give|provide)\s+(me\s+)?(example|tutorial|guide)', 'learning', 0.4),
        (r'\bwhat\s+(is|are)\b', 'learning', 0.2),

        # Exploration intent
        (r'\b(find|search|look for|locate)', 'exploration', 0.3),
        (r'\b(where|which|list)\b', 'exploration', 0.2),
        (r'\bshow\s+(me\s+)?(all|every)', 'exploration', 0.3),
    ]

    # Technical keyword patterns (things to extract)
    TECHNICAL_PATTERNS = [
        r'\b[A-Z][a-z]+(?:[A-Z][a-z]+)+\b',  # PascalCase (class names)
        r'\b[a-z]+(?:_[a-z]+)+\b',  # snake_case (functions, variables)
        r'\b[a-z]+(?:[A-Z][a-z]+)+\b',  # camelCase
        r'\b\w+\(\)',  # Function calls
        r'\b(?:def|class|function|method|variable|const|let|var)\s+(\w+)',  # Definitions
    ]

    # Common technical terms to boost
    TECHNICAL_TERMS = {
        'api', 'database', 'auth', 'authentication', 'authorization',
        'token', 'jwt', 'session', 'cookie', 'middleware', 'endpoint',
        'query', 'mutation', 'schema', 'model', 'controller', 'service',
        'component', 'hook', 'state', 'props', 'context', 'redux',
        'async', 'await', 'promise', 'callback', 'event', 'listener',
        'error', 'exception', 'validation', 'sanitization', 'security',
        'performance', 'optimization', 'cache', 'memory', 'storage',
        'test', 'mock', 'fixture', 'assertion', 'coverage',
    }

    # Stop words to filter out
    STOP_WORDS = {
        'i', 'me', 'my', 'myself', 'we', 'our', 'ours', 'ourselves',
        'you', 'your', 'yours', 'yourself', 'yourselves',
        'he', 'him', 'his', 'himself', 'she', 'her', 'hers', 'herself',
        'it', 'its', 'itself', 'they', 'them', 'their', 'theirs', 'themselves',
        'what', 'which', 'who', 'whom', 'this', 'that', 'these', 'those',
        'am', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
        'have', 'has', 'had', 'having', 'do', 'does', 'did', 'doing',
        'a', 'an', 'the', 'and', 'but', 'if', 'or', 'because', 'as',
        'until', 'while', 'of', 'at', 'by', 'for', 'with', 'about',
        'against', 'between', 'into', 'through', 'during', 'before',
        'after', 'above', 'below', 'to', 'from', 'up', 'down', 'in',
        'out', 'on', 'off', 'over', 'under', 'again', 'further', 'then',
        'once', 'here', 'there', 'when', 'where', 'why', 'how', 'all',
        'both', 'each', 'few', 'more', 'most', 'other', 'some', 'such',
        'no', 'nor', 'not', 'only', 'own', 'same', 'so', 'than', 'too',
        'very', 'can', 'will', 'just', 'don', 'should', 'now',
    }

    def __init__(self, context_window: int = 5):
        """
        Initialize intent detector.

        Args:
            context_window: Number of recent queries to analyze
        """
        self.context_window = context_window

    def detect_intent(self, recent_queries: List[str]) -> DetectedIntent:
        """
        Detect intent from recent conversation queries.

        Args:
            recent_queries: List of recent query strings (most recent last)

        Returns:
            DetectedIntent with analysis results
        """
        if not recent_queries:
            return DetectedIntent(
                intent_type='general',
                keywords=[],
                confidence=0.0,
                search_query='',
                original_queries=[],
            )

        # Limit to context window
        queries = recent_queries[-self.context_window:]

        # Detect intent type
        intent_type, intent_confidence = self._detect_intent_type(queries)

        # Extract keywords
        keywords = self._extract_keywords(queries)

        # Synthesize search query
        search_query = self._synthesize_query(queries, keywords, intent_type)

        # Calculate overall confidence
        keyword_confidence = min(len(keywords) / 5.0, 1.0)  # More keywords = higher confidence
        overall_confidence = (intent_confidence * 0.6 + keyword_confidence * 0.4)

        logger.debug(f"Detected intent: {intent_type} (confidence: {overall_confidence:.2f})")
        logger.debug(f"Keywords: {keywords}")
        logger.debug(f"Search query: {search_query}")

        return DetectedIntent(
            intent_type=intent_type,
            keywords=keywords,
            confidence=overall_confidence,
            search_query=search_query,
            original_queries=queries,
        )

    def _detect_intent_type(self, queries: List[str]) -> Tuple[str, float]:
        """
        Detect intent type from queries.

        Args:
            queries: List of query strings

        Returns:
            (intent_type, confidence) tuple
        """
        # Combine queries for analysis (weight recent queries more)
        combined = ' '.join(queries).lower()

        # Score each intent type
        intent_scores: Dict[str, float] = {
            'implementation': 0.0,
            'debugging': 0.0,
            'learning': 0.0,
            'exploration': 0.0,
            'general': 0.1,  # Baseline
        }

        # Check patterns
        for pattern, intent_type, boost in self.INTENT_PATTERNS:
            if re.search(pattern, combined, re.IGNORECASE):
                intent_scores[intent_type] += boost

        # Get highest scoring intent
        best_intent = max(intent_scores.items(), key=lambda x: x[1])
        intent_type, confidence = best_intent

        # Normalize confidence to 0-1
        confidence = min(confidence, 1.0)

        return intent_type, confidence

    def _extract_keywords(self, queries: List[str]) -> List[str]:
        """
        Extract technical keywords from queries.

        Args:
            queries: List of query strings

        Returns:
            List of keywords (deduplicated and ranked)
        """
        keywords: Set[str] = set()

        # Combine queries
        combined = ' '.join(queries)

        # Extract technical patterns
        for pattern in self.TECHNICAL_PATTERNS:
            matches = re.findall(pattern, combined)
            for match in matches:
                # Clean up match
                if isinstance(match, tuple):
                    match = match[0]  # Extract from capture group

                # Remove parentheses, quotes
                cleaned = re.sub(r'[(){}\[\]\'"]', '', match)
                if cleaned and len(cleaned) > 2:
                    keywords.add(cleaned.lower())

        # Extract individual words and check against technical terms
        words = re.findall(r'\b\w+\b', combined.lower())
        for word in words:
            if word in self.TECHNICAL_TERMS:
                keywords.add(word)

        # Filter stop words
        keywords = {kw for kw in keywords if kw not in self.STOP_WORDS}

        # Rank by frequency in queries
        keyword_counts = Counter()
        for keyword in keywords:
            # Count occurrences (case-insensitive)
            count = sum(query.lower().count(keyword) for query in queries)
            keyword_counts[keyword] = count

        # Return top keywords sorted by frequency
        ranked = [kw for kw, _ in keyword_counts.most_common(10)]

        return ranked

    def _synthesize_query(
        self, queries: List[str], keywords: List[str], intent_type: str
    ) -> str:
        """
        Synthesize a search query from queries and keywords.

        Args:
            queries: Original queries
            keywords: Extracted keywords
            intent_type: Detected intent type

        Returns:
            Synthesized search query string
        """
        if not keywords:
            # Fall back to last query if no keywords
            return queries[-1] if queries else ''

        # Build query based on intent type
        if intent_type == 'implementation':
            # Focus on "how to" implement with keywords
            return f"implement {' '.join(keywords[:5])}"

        elif intent_type == 'debugging':
            # Focus on fixing/debugging
            return f"fix debug {' '.join(keywords[:5])}"

        elif intent_type == 'learning':
            # Focus on examples and explanations
            return f"example {' '.join(keywords[:5])}"

        elif intent_type == 'exploration':
            # Focus on finding related content
            return f"find {' '.join(keywords[:5])}"

        else:  # general
            # Just use top keywords
            return ' '.join(keywords[:5])
