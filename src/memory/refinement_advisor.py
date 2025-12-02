"""Refinement hints for improving search results."""

import logging
from typing import List, Dict, Any
import os

from src.memory.result_summarizer import SearchFacets

logger = logging.getLogger(__name__)


class RefinementAdvisor:
    """Suggest ways to refine search results."""

    @staticmethod
    def analyze_and_suggest(
        results: List[Dict[str, Any]],
        facets: SearchFacets,
        query: str,
        filters: Dict[str, Any],
    ) -> List[str]:
        """Generate refinement suggestions based on result characteristics.

        Args:
            results: List of search results
            facets: Faceted breakdown
            query: Original query
            filters: Current search filters

        Returns:
            List of refinement hint strings
        """
        hints = []

        # Too many results → suggest narrowing
        if len(results) >= 50:
            hints.append(
                "💡 Too many results. Try adding file_pattern to narrow down "
                "(e.g., file_pattern='*/auth/*')"
            )

            # Suggest specific language filter if multi-language
            if len(facets.languages) > 1:
                main_lang = max(facets.languages.items(), key=lambda x: x[1])[0]
                hints.append(
                    f"💡 Filter by language: language='{main_lang}' "
                    f"to focus on {facets.languages[main_lang]} results"
                )

        # Too few results → suggest broadening
        elif 0 < len(results) < 3:
            hints.append(
                "💡 Few results found. Try broadening your query or removing filters"
            )

            # Suggest hybrid search if using semantic
            search_mode = filters.get("search_mode", "semantic")
            if search_mode == "semantic":
                hints.append(
                    "💡 Try hybrid search mode for better recall: search_mode='hybrid'"
                )

            # Suggest removing file_pattern if present
            if filters.get("file_pattern"):
                hints.append(
                    "💡 Try removing file_pattern filter to search across all files"
                )

        # Results span many files → suggest focusing
        elif len(facets.files) > 10:
            top_file = max(facets.files.items(), key=lambda x: x[1])[0]
            top_dir = os.path.dirname(top_file)
            if top_dir:
                hints.append(
                    f"💡 Results are scattered. Try file_pattern='{top_dir}/*' "
                    f"to focus on the main directory"
                )

        # Results span many directories but concentrated in one
        elif len(facets.directories) >= 3:
            # Find directory with most results
            top_dir = max(facets.directories.items(), key=lambda x: x[1])[0]
            top_dir_count = facets.directories[top_dir]
            total_results = len(results)

            # If >50% of results are in one directory, suggest focusing there
            if top_dir_count / total_results > 0.5:
                hints.append(
                    f"💡 Most results ({top_dir_count}/{total_results}) are in '{top_dir}'. "
                    f"Try file_pattern='{top_dir}/*' to focus there"
                )

        # Mixed unit types → suggest filtering
        if len(facets.unit_types) > 1:
            # Suggest focusing on dominant type
            if facets.unit_types.get("function", 0) > facets.unit_types.get("class", 0):
                hints.append(
                    "💡 Add 'function' to your query to focus on functions only"
                )
            elif facets.unit_types.get("class", 0) > facets.unit_types.get(
                "function", 0
            ):
                hints.append("💡 Add 'class' to your query to focus on classes only")

        # Query lacks context → suggest more specific terms
        if len(query.split()) < 3:
            hints.append(
                "💡 Try adding more context to your query "
                "(e.g., 'user authentication' → 'JWT user authentication logic')"
            )

        # Keyword search might be better for specific names
        # Check if query contains identifiers (CamelCase, snake_case, or starts with _)
        has_identifier = any(
            term[0].isupper()  # CamelCase
            or "_" in term  # snake_case
            or term.startswith("_")  # private identifier
            for term in query.split()
        )
        if has_identifier and filters.get("search_mode") != "keyword":
            hints.append(
                "💡 Searching for specific names? Try search_mode='keyword' "
                "for exact matching"
            )

        # Return max 3 hints to avoid overwhelming
        return hints[:3]
