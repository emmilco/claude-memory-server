"""Spelling suggestions for query improvement."""

import logging
from typing import List, Set, Optional
import difflib

from src.store import MemoryStore
from src.search.query_synonyms import PROGRAMMING_SYNONYMS

logger = logging.getLogger(__name__)


class SpellingSuggester:
    """Suggest corrections for misspelled queries."""

    def __init__(self, store: MemoryStore):
        """Initialize spelling suggester.

        Args:
            store: Memory store instance
        """
        self.store = store
        self.indexed_terms: Set[str] = set()
        self._terms_loaded = False

    async def load_indexed_terms(self, project_name: Optional[str] = None):
        """Extract all function/class names from indexed code.

        Args:
            project_name: Optional project filter
        """
        if self._terms_loaded:
            return

        try:
            from src.core.models import SearchFilters, MemoryScope, MemoryCategory, ContextLevel

            filters = SearchFilters(
                scope=MemoryScope.PROJECT if project_name else MemoryScope.GLOBAL,
                project_name=project_name,
                category=MemoryCategory.CODE,
                context_level=ContextLevel.PROJECT_CONTEXT,
            )

            # Get sample of memories to extract terms
            memories = await self.store.list_memories(
                filters=filters,
                limit=500,  # Limit to avoid huge queries
            )

            # Extract unit names
            for memory in memories:
                metadata = memory.get("metadata", {}) if isinstance(memory, dict) else {}
                unit_name = metadata.get("unit_name", "")
                if unit_name:
                    # Add the name and its lowercase version
                    self.indexed_terms.add(unit_name)
                    self.indexed_terms.add(unit_name.lower())

                    # Also add individual words from multi-word names
                    for word in unit_name.replace("_", " ").replace("-", " ").split():
                        if len(word) > 2:  # Skip very short words
                            self.indexed_terms.add(word.lower())

            self._terms_loaded = True
            logger.info(f"Loaded {len(self.indexed_terms)} indexed terms for spelling suggestions")

        except Exception as e:
            logger.warning(f"Failed to load indexed terms: {e}")

    def suggest_corrections(
        self,
        query: str,
        max_distance: int = 2,
        max_suggestions: int = 3,
    ) -> List[str]:
        """Generate spelling corrections.

        Args:
            query: Original query
            max_distance: Maximum edit distance (not used with difflib)
            max_suggestions: Maximum corrections to return

        Returns:
            List of suggested corrections
        """
        suggestions = []
        query_terms = query.lower().split()

        for term in query_terms:
            # Skip very short terms
            if len(term) <= 2:
                continue

            # Check synonyms first - offer alternative term if available
            if term in PROGRAMMING_SYNONYMS:
                for synonym in list(PROGRAMMING_SYNONYMS[term])[:2]:
                    if synonym not in query_terms:
                        corrected_query = query.lower().replace(term, synonym)
                        if corrected_query not in suggestions:
                            suggestions.append(corrected_query)

            # Check indexed terms for close matches
            if self.indexed_terms:
                close_matches = self._find_close_matches(
                    term,
                    self.indexed_terms,
                )

                for match in close_matches[:2]:
                    corrected_query = query.lower().replace(term, match)
                    if corrected_query not in suggestions:
                        suggestions.append(corrected_query)

        # Common programming typos
        common_typos = {
            "athentication": "authentication",
            "autherization": "authorization",
            "databse": "database",
            "funciton": "function",
            "conifg": "config",
            "valiation": "validation",
            "excepton": "exception",
            "connction": "connection",
            "initialze": "initialize",
            "retreive": "retrieve",
        }

        for typo, correction in common_typos.items():
            if typo in query.lower():
                corrected = query.lower().replace(typo, correction)
                if corrected not in suggestions:
                    suggestions.append(corrected)

        return suggestions[:max_suggestions]

    @staticmethod
    def _find_close_matches(
        term: str,
        candidates: Set[str],
        cutoff: float = 0.6,
    ) -> List[str]:
        """Find terms within edit distance using difflib.

        Args:
            term: Term to find matches for
            candidates: Set of candidate terms
            cutoff: Similarity threshold (0.0 to 1.0)

        Returns:
            List of close matches
        """
        # Convert set to list for difflib
        candidate_list = list(candidates)

        # Get close matches
        matches = difflib.get_close_matches(
            term,
            candidate_list,
            n=5,
            cutoff=cutoff,
        )

        # Filter out exact matches
        return [m for m in matches if m.lower() != term.lower()]
