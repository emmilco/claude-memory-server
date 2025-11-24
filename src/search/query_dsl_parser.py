"""Query DSL parser for advanced search filtering (FEAT-018)."""

import re
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass, field


@dataclass
class ParsedQuery:
    """Parsed query with semantic terms and structured filters."""

    semantic_query: str  # Free-text semantic search terms
    filters: Dict[str, Any] = field(default_factory=dict)  # Structured filters
    exclusions: List[str] = field(default_factory=list)  # Exclusion patterns

    def __str__(self) -> str:
        """Human-readable representation."""
        parts = []
        if self.semantic_query:
            parts.append(f"Query: '{self.semantic_query}'")
        if self.filters:
            parts.append(f"Filters: {self.filters}")
        if self.exclusions:
            parts.append(f"Exclusions: {self.exclusions}")
        return " | ".join(parts)


class QueryDSLParser:
    """
    Parse query DSL expressions into structured queries.

    Supports GitHub-style filter syntax:
    - language:python, lang:py - Language filter
    - file:pattern, path:pattern - File path pattern (glob)
    - project:name - Project name filter
    - created:>2024-01-01 - Creation date filter
    - modified:<2024-12-31 - Modified date filter
    - author:username - Git author filter
    - category:fact - Memory category filter
    - scope:global - Memory scope filter
    - -file:test - Exclusion (NOT filter)

    Examples:
        "error handling language:python file:src/**/*.py"
        "authentication created:>2024-01-01 -file:test"
        "API design project:web-app author:john"
    """

    # Filter patterns
    FILTER_PATTERN = re.compile(
        r'(-)?(\w+):((?:"[^"]+"|[^\s]+))',
        re.IGNORECASE
    )

    # Date operators
    DATE_OPERATORS = {
        '>': 'gt',
        '>=': 'gte',
        '<': 'lt',
        '<=': 'lte',
        '=': 'eq',
    }

    # Filter aliases
    FILTER_ALIASES = {
        'lang': 'language',
        'path': 'file',
        'proj': 'project',
        'cat': 'category',
    }

    # Supported filters
    SUPPORTED_FILTERS = {
        'language', 'file', 'project', 'created', 'modified',
        'author', 'category', 'scope'
    }

    def parse(self, query_string: str) -> ParsedQuery:
        """
        Parse DSL query string into structured query.

        Args:
            query_string: Query string with optional filters

        Returns:
            ParsedQuery with semantic query and filters

        Examples:
            >>> parser = QueryDSLParser()
            >>> q = parser.parse("error handling language:python")
            >>> q.semantic_query
            'error handling'
            >>> q.filters
            {'language': 'python'}
        """
        if not query_string or not query_string.strip():
            return ParsedQuery(semantic_query="", filters={}, exclusions=[])

        # Extract filters and semantic terms
        filters, exclusions, semantic_terms = self._extract_filters(query_string)

        # Build semantic query from remaining terms
        semantic_query = " ".join(semantic_terms).strip()

        return ParsedQuery(
            semantic_query=semantic_query,
            filters=filters,
            exclusions=exclusions
        )

    def _extract_filters(
        self, query_string: str
    ) -> Tuple[Dict[str, Any], List[str], List[str]]:
        """
        Extract filters from query string.

        Returns:
            Tuple of (filters dict, exclusions list, semantic terms list)
        """
        filters: Dict[str, Any] = {}
        exclusions: List[str] = []
        semantic_terms: List[str] = []

        # Find all filter matches
        last_end = 0
        for match in self.FILTER_PATTERN.finditer(query_string):
            # Extract semantic terms between filters
            semantic_part = query_string[last_end:match.start()].strip()
            if semantic_part:
                semantic_terms.append(semantic_part)

            # Parse filter
            is_exclusion = match.group(1) == '-'
            filter_key = match.group(2).lower()
            filter_value = match.group(3)

            # Remove quotes if present
            if filter_value.startswith('"') and filter_value.endswith('"'):
                filter_value = filter_value[1:-1]

            # Resolve aliases
            filter_key = self.FILTER_ALIASES.get(filter_key, filter_key)

            # Validate filter
            if filter_key not in self.SUPPORTED_FILTERS:
                # If not a recognized filter, treat as semantic term
                semantic_terms.append(match.group(0))
                last_end = match.end()
                continue

            # Handle exclusions
            if is_exclusion:
                if filter_key == 'file':
                    exclusions.append(filter_value)
                # Other exclusions not yet supported
                last_end = match.end()
                continue

            # Parse filter value
            parsed_value = self._parse_filter_value(filter_key, filter_value)

            # Store filter (merge for date ranges)
            if filter_key in ('created', 'modified'):
                if filter_key not in filters:
                    filters[filter_key] = {}
                filters[filter_key].update(parsed_value)
            else:
                filters[filter_key] = parsed_value

            last_end = match.end()

        # Add remaining semantic terms
        remaining = query_string[last_end:].strip()
        if remaining:
            semantic_terms.append(remaining)

        return filters, exclusions, semantic_terms

    def _parse_filter_value(self, filter_key: str, value: str) -> Any:
        """
        Parse filter value based on filter type.

        Args:
            filter_key: Filter name (e.g., 'language', 'created')
            value: Filter value (e.g., 'python', '>2024-01-01')

        Returns:
            Parsed filter value
        """
        # Date filters
        if filter_key in ('created', 'modified'):
            return self._parse_date_filter(value)

        # String filters
        return value

    def _parse_date_filter(self, value: str) -> Dict[str, str]:
        """
        Parse date filter with operator.

        Formats:
            >2024-01-01 - After date
            >=2024-01-01 - On or after
            <2024-12-31 - Before date
            <=2024-12-31 - On or before
            =2024-06-15 - Exact date
            2024-01-01..2024-12-31 - Date range

        Returns:
            Dict with operator and date value
        """
        # Check for range
        if '..' in value:
            start, end = value.split('..', 1)
            return {
                'gte': self._validate_date(start.strip()),
                'lte': self._validate_date(end.strip())
            }

        # Check for operator prefix (check longer operators first)
        operators_sorted = sorted(
            self.DATE_OPERATORS.items(),
            key=lambda x: len(x[0]),
            reverse=True
        )
        for op_str, op_key in operators_sorted:
            if value.startswith(op_str):
                date_str = value[len(op_str):].strip()
                return {op_key: self._validate_date(date_str)}

        # Default to exact match
        return {'eq': self._validate_date(value)}

    def _validate_date(self, date_str: str) -> str:
        """
        Validate date string format.

        Args:
            date_str: Date string in YYYY-MM-DD format

        Returns:
            Validated date string

        Raises:
            ValueError: If date format is invalid
        """
        try:
            # Parse and validate
            datetime.strptime(date_str, '%Y-%m-%d')
            return date_str
        except ValueError:
            raise ValueError(
                f"Invalid date format: '{date_str}'. Use YYYY-MM-DD format."
            )

    def get_filter_help(self) -> str:
        """
        Get help text for supported filters.

        Returns:
            Formatted help text
        """
        help_text = """
Query DSL Filter Reference:

Basic Filters:
  language:python       Filter by programming language
  file:src/**/*.py      Filter by file path (glob pattern)
  project:web-app       Filter by project name
  author:username       Filter by git author
  category:fact         Filter by memory category
  scope:global          Filter by memory scope

Date Filters:
  created:>2024-01-01   Created after date
  created:>=2024-01-01  Created on or after date
  created:<2024-12-31   Created before date
  created:<=2024-12-31  Created on or before date
  created:=2024-06-15   Created on exact date
  created:2024-01-01..2024-12-31  Created in date range

Exclusions:
  -file:test            Exclude files matching pattern

Filter Aliases:
  lang: → language:
  path: → file:
  proj: → project:
  cat: → category:

Examples:
  error handling language:python
  authentication file:src/**/*.py -file:test
  API design project:web-app created:>2024-01-01
  login author:john modified:<2024-12-31
"""
        return help_text.strip()
