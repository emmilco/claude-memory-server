"""Query suggestion system for better discoverability."""

import logging
from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass
from collections import Counter

from src.store import MemoryStore
from src.config import ServerConfig
from src.core.models import MemoryCategory, MemoryScope

logger = logging.getLogger(__name__)


@dataclass
class QuerySuggestion:
    """A single query suggestion."""

    query: str
    category: str  # template, project, domain, general
    description: str
    expected_results: Optional[int] = None


@dataclass
class SuggestQueryResponse:
    """Response from suggest_queries."""

    suggestions: List[QuerySuggestion]
    indexed_stats: Dict[str, Any]
    project_name: Optional[str]
    total_suggestions: int


class QuerySuggester:
    """Generate contextual query suggestions for better discoverability."""

    # Intent-based templates
    INTENT_TEMPLATES = {
        "implementation": [
            "user authentication logic",
            "database connection handling",
            "API request validation",
            "error handling middleware",
            "data validation functions",
        ],
        "debugging": [
            "error handling in API",
            "exception logging",
            "retry logic",
            "validation failures",
            "error recovery mechanisms",
        ],
        "learning": [
            "how does pagination work",
            "authentication flow",
            "request processing pipeline",
            "data transformation logic",
            "caching strategy",
        ],
        "exploration": [
            "all REST endpoints",
            "database models",
            "utility functions",
            "middleware components",
            "service layer",
        ],
        "refactoring": [
            "duplicate error handlers",
            "similar validation functions",
            "repeated database queries",
            "common patterns",
            "code complexity hotspots",
        ],
    }

    # Domain-specific presets
    DOMAIN_PRESETS = {
        "auth": [
            QuerySuggestion(
                query="JWT token validation",
                category="domain",
                description="Find authentication token validation code",
            ),
            QuerySuggestion(
                query="password hashing logic",
                category="domain",
                description="Find password encryption and verification",
            ),
            QuerySuggestion(
                query="session management",
                category="domain",
                description="Find session creation and validation",
            ),
        ],
        "database": [
            QuerySuggestion(
                query="SQL query construction",
                category="domain",
                description="Find database query building code",
            ),
            QuerySuggestion(
                query="ORM models",
                category="domain",
                description="Find database model definitions",
            ),
            QuerySuggestion(
                query="database migrations",
                category="domain",
                description="Find schema migration code",
            ),
        ],
        "api": [
            QuerySuggestion(
                query="request validation",
                category="domain",
                description="Find API request validation logic",
            ),
            QuerySuggestion(
                query="response formatting",
                category="domain",
                description="Find API response construction",
            ),
            QuerySuggestion(
                query="middleware",
                category="domain",
                description="Find API middleware functions",
            ),
        ],
        "error": [
            QuerySuggestion(
                query="exception handlers",
                category="domain",
                description="Find error handling code",
            ),
            QuerySuggestion(
                query="error logging",
                category="domain",
                description="Find error logging mechanisms",
            ),
            QuerySuggestion(
                query="retry logic",
                category="domain",
                description="Find retry and recovery code",
            ),
        ],
    }

    # General discovery suggestions
    GENERAL_SUGGESTIONS = [
        QuerySuggestion(
            query="most complex functions",
            category="general",
            description="Find functions with high complexity",
        ),
        QuerySuggestion(
            query="entry points and main functions",
            category="general",
            description="Find application entry points",
        ),
        QuerySuggestion(
            query="configuration loading",
            category="general",
            description="Find configuration initialization code",
        ),
        QuerySuggestion(
            query="utility and helper functions",
            category="general",
            description="Find common utility code",
        ),
    ]

    def __init__(
        self,
        store: MemoryStore,
        config: ServerConfig,
    ):
        """Initialize query suggester.

        Args:
            store: Memory store instance
            config: Server configuration
        """
        self.store = store
        self.config = config
        self.suggestion_cache: Dict[str, List[QuerySuggestion]] = {}
        self.cache_ttl = 3600  # 1 hour

    async def suggest_queries(
        self,
        intent: Optional[str] = None,
        project_name: Optional[str] = None,
        context: Optional[str] = None,
        max_suggestions: int = 8,
    ) -> SuggestQueryResponse:
        """Generate query suggestions.

        Args:
            intent: User intent (implementation, debugging, learning, exploration, refactoring)
            project_name: Optional project to scope suggestions
            context: Optional context from conversation
            max_suggestions: Maximum suggestions to return

        Returns:
            SuggestQueryResponse with categorized suggestions
        """
        suggestions: List[QuerySuggestion] = []

        # Get indexed stats
        indexed_stats = await self._get_indexed_stats(project_name)

        # 1. Intent-based templates (if intent provided)
        if intent and intent in self.INTENT_TEMPLATES:
            for template in self.INTENT_TEMPLATES[intent][:3]:
                suggestions.append(QuerySuggestion(
                    query=template,
                    category="template",
                    description=f"Common {intent} pattern",
                ))

        # 2. Project-specific suggestions (from indexed content)
        project_suggestions = await self._get_project_suggestions(
            project_name,
            indexed_stats,
        )
        suggestions.extend(project_suggestions[:2])

        # 3. Domain-specific presets (detect from context or stats)
        domain = self._detect_domain(context, indexed_stats)
        if domain and domain in self.DOMAIN_PRESETS:
            suggestions.extend(self.DOMAIN_PRESETS[domain][:2])

        # 4. General discovery suggestions
        suggestions.extend(self.GENERAL_SUGGESTIONS[:2])

        # Limit to max_suggestions
        suggestions = suggestions[:max_suggestions]

        logger.info(
            f"Generated {len(suggestions)} query suggestions "
            f"(intent: {intent}, project: {project_name})"
        )

        return SuggestQueryResponse(
            suggestions=suggestions,
            indexed_stats=indexed_stats,
            project_name=project_name,
            total_suggestions=len(suggestions),
        )

    async def _get_indexed_stats(
        self,
        project_name: Optional[str],
    ) -> Dict[str, Any]:
        """Get statistics about indexed code.

        Args:
            project_name: Optional project filter

        Returns:
            Dict with stats: total_files, total_units, languages, top_classes
        """
        try:
            # Get all code memories for this project
            from src.core.models import SearchFilters, ContextLevel

            filters = SearchFilters(
                scope=MemoryScope.PROJECT if project_name else MemoryScope.GLOBAL,
                project_name=project_name,
                category=MemoryCategory.CODE,
                context_level=ContextLevel.PROJECT_CONTEXT,
            )

            # Get sample of memories to extract stats (limit to avoid huge queries)
            memories = await self.store.list_memories(
                filters=filters,
                limit=1000,
            )

            # Extract statistics
            languages = Counter()
            files = set()
            top_classes = Counter()

            for memory in memories:
                metadata = memory.get("metadata", {}) if isinstance(memory, dict) else {}

                # Count languages
                lang = metadata.get("language", "")
                if lang:
                    languages[lang] += 1

                # Count unique files
                file_path = metadata.get("file_path", "")
                if file_path:
                    files.add(file_path)

                # Extract class/function names
                unit_type = metadata.get("unit_type", "")
                unit_name = metadata.get("unit_name", "")
                if unit_type == "class" and unit_name:
                    top_classes[unit_name] += 1

            return {
                "total_files": len(files),
                "total_units": len(memories),
                "languages": dict(languages.most_common()),
                "top_classes": [name for name, _ in top_classes.most_common(10)],
            }

        except Exception as e:
            logger.warning(f"Failed to get indexed stats: {e}")
            return {
                "total_files": 0,
                "total_units": 0,
                "languages": {},
                "top_classes": [],
            }

    async def _get_project_suggestions(
        self,
        project_name: Optional[str],
        indexed_stats: Dict[str, Any],
    ) -> List[QuerySuggestion]:
        """Generate project-specific suggestions based on indexed content.

        Args:
            project_name: Optional project filter
            indexed_stats: Statistics from _get_indexed_stats

        Returns:
            List of project-specific suggestions
        """
        suggestions = []

        # Extract top classes
        top_classes = indexed_stats.get("top_classes", [])

        if top_classes:
            # Suggest searching for most common class
            class_name = top_classes[0]
            suggestions.append(QuerySuggestion(
                query=f"{class_name} implementation",
                category="project",
                description=f"Based on commonly used class in your project",
            ))

        # Suggest based on languages
        languages = indexed_stats.get("languages", {})
        if languages:
            main_lang = max(languages.items(), key=lambda x: x[1])[0]
            suggestions.append(QuerySuggestion(
                query=f"{main_lang} utility functions",
                category="project",
                description=f"Explore {main_lang} helpers in this project",
            ))

        return suggestions

    def _detect_domain(
        self,
        context: Optional[str],
        indexed_stats: Dict[str, Any],
    ) -> Optional[str]:
        """Detect the domain from context or indexed stats.

        Args:
            context: Optional context string
            indexed_stats: Indexed statistics

        Returns:
            Detected domain (auth, database, api, error) or None
        """
        # Check context for domain keywords
        if context:
            context_lower = context.lower()
            if any(word in context_lower for word in ["auth", "login", "password", "token"]):
                return "auth"
            if any(word in context_lower for word in ["database", "sql", "query", "db"]):
                return "database"
            if any(word in context_lower for word in ["api", "endpoint", "route", "rest"]):
                return "api"
            if any(word in context_lower for word in ["error", "exception", "catch", "try"]):
                return "error"

        # Check top classes for domain hints
        top_classes = indexed_stats.get("top_classes", [])
        if top_classes:
            classes_str = " ".join(top_classes).lower()
            if any(word in classes_str for word in ["auth", "user", "session"]):
                return "auth"
            if any(word in classes_str for word in ["repository", "model", "entity"]):
                return "database"
            if any(word in classes_str for word in ["controller", "handler", "endpoint"]):
                return "api"

        return None
