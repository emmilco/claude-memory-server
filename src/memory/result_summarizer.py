"""Result summarization for better search UX."""

import logging
from typing import List, Dict, Any
from dataclasses import dataclass
from collections import Counter

logger = logging.getLogger(__name__)


@dataclass
class SearchFacets:
    """Faceted breakdown of search results."""

    languages: Dict[str, int]  # {"python": 8, "typescript": 2}
    unit_types: Dict[str, int]  # {"function": 7, "class": 3}
    files: Dict[str, int]  # Top files by result count
    directories: Dict[str, int]  # Top directories by result count
    projects: Dict[str, int]  # Only for cross-project search


class ResultSummarizer:
    """Generate readable summaries of search results."""

    @staticmethod
    def build_facets(
        results: List[Dict[str, Any]],
        include_projects: bool = False,
    ) -> SearchFacets:
        """Build faceted breakdown from results.

        Args:
            results: List of search results
            include_projects: Whether to include project facet

        Returns:
            SearchFacets with counts by dimension
        """
        languages = Counter()
        unit_types = Counter()
        files = Counter()
        directories = Counter()
        projects = Counter()

        for result in results:
            # Count languages
            lang = result.get("language", "")
            if lang and lang != "(unknown language)":
                languages[lang] += 1

            # Count unit types
            unit_type = result.get("unit_type", "")
            if unit_type and unit_type != "(unknown type)":
                unit_types[unit_type] += 1

            # Count files
            file_path = result.get("file_path", "")
            if file_path and file_path != "(no path)":
                files[file_path] += 1

                # Extract directory
                import os
                dir_path = os.path.dirname(file_path)
                if dir_path:
                    directories[dir_path] += 1

            # Count projects (if applicable)
            if include_projects:
                project = result.get("project_name", "")
                if project:
                    projects[project] += 1

        return SearchFacets(
            languages=dict(languages.most_common()),
            unit_types=dict(unit_types.most_common()),
            files=dict(files.most_common(5)),  # Top 5 files
            directories=dict(directories.most_common(5)),  # Top 5 directories
            projects=dict(projects.most_common()) if include_projects else {},
        )

    @staticmethod
    def summarize(
        results: List[Dict[str, Any]],
        facets: SearchFacets,
        query: str,
    ) -> str:
        """Generate natural language summary.

        Args:
            results: List of search results
            facets: Faceted breakdown
            query: Original query

        Returns:
            Human-readable summary string
        """
        count = len(results)

        if count == 0:
            return "No results found - try broadening your query or checking project is indexed"

        # File distribution
        file_count = len(facets.files)
        if file_count == 0:
            file_summary = "unknown location"
        elif file_count == 1:
            file_summary = "1 file"
        else:
            file_summary = f"{file_count} files"

        # Language distribution
        if len(facets.languages) == 0:
            lang_summary = ""
        elif len(facets.languages) == 1:
            lang = list(facets.languages.keys())[0]
            lang_summary = f" in {lang.title()}"
        elif len(facets.languages) == 2:
            langs = " and ".join(list(facets.languages.keys()))
            lang_summary = f" across {langs}"
        else:
            # More than 2 languages
            top_langs = list(facets.languages.keys())[:2]
            lang_summary = f" across {', '.join(top_langs)} and {len(facets.languages) - 2} other language(s)"

        # Unit type distribution
        unit_summary = ResultSummarizer._format_unit_types(facets.unit_types)

        # Compose base summary
        summary = f"Found {count} {unit_summary} across {file_summary}{lang_summary}"

        # Add project count if multi-project
        if len(facets.projects) > 1:
            summary += f" in {len(facets.projects)} projects"

        return summary

    @staticmethod
    def _format_unit_types(types: Dict[str, int]) -> str:
        """Format unit types naturally.

        Args:
            types: Dict of unit_type -> count

        Returns:
            Formatted string like "3 functions" or "2 classes and 5 functions"
        """
        if len(types) == 0:
            return "items"

        if len(types) == 1:
            unit_type, count = list(types.items())[0]
            # Handle irregular plurals
            if unit_type == "class":
                plural_type = "classes" if count > 1 else "class"
            else:
                plural_type = f"{unit_type}{'s' if count > 1 else ''}"
            return plural_type

        # Mixed types - show top 2
        type_list = []
        for unit_type, count in list(types.items())[:2]:
            # Handle irregular plurals
            if unit_type == "class":
                plural_type = "classes" if count > 1 else "class"
            else:
                plural_type = f"{unit_type}{'s' if count > 1 else ''}"
            type_list.append(f"{count} {plural_type}")

        if len(types) > 2:
            # More than 2 types
            return ", ".join(type_list[:-1]) + f", and {type_list[-1]}"
        else:
            return " and ".join(type_list)
