"""Extract and process docstrings from source code.

This module provides functionality to extract documentation strings from
various programming languages and link them to their corresponding code units.
"""

import logging
import re
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class DocstringStyle(Enum):
    """Docstring styles for different languages."""
    PYTHON = "python"          # Triple quotes: """...""" or '''...'''
    JSDOC = "jsdoc"            # /** ... */
    JAVADOC = "javadoc"        # /** ... */
    GODOC = "godoc"            # // ... (consecutive single-line comments)
    RUSTDOC = "rustdoc"        # /// ... or //! ...
    MARKDOWN = "markdown"      # # ... (for some languages)


@dataclass
class Docstring:
    """Represents an extracted docstring."""
    content: str
    style: DocstringStyle
    start_line: int
    end_line: int
    unit_name: Optional[str] = None
    unit_type: Optional[str] = None

    def clean_content(self) -> str:
        """Return cleaned docstring content without comment markers."""
        return self.content.strip()


class DocstringExtractor:
    """
    Extract docstrings from source code in multiple languages.

    Supports:
    - Python: Triple-quoted strings
    - JavaScript/TypeScript: JSDoc comments
    - Java: Javadoc comments
    - Go: GoDoc comments
    - Rust: RustDoc comments
    """

    # Language-specific patterns
    PYTHON_DOCSTRING_PATTERN = r'(?:"""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\')'
    JSDOC_PATTERN = r'/\*\*[\s\S]*?\*/'
    SINGLE_LINE_COMMENT_PATTERN = r'//[/!].*?$'

    def __init__(self):
        """Initialize docstring extractor."""
        self.stats = {
            "docstrings_extracted": 0,
            "languages_processed": set(),
        }

    def extract_from_code(
        self,
        source_code: str,
        language: str,
        file_path: str = "",
    ) -> List[Docstring]:
        """
        Extract all docstrings from source code.

        Args:
            source_code: Source code content
            language: Programming language
            file_path: Path to source file (for context)

        Returns:
            List of extracted docstrings
        """
        language = language.lower()
        self.stats["languages_processed"].add(language)

        if language == "python":
            return self._extract_python_docstrings(source_code)
        elif language in ("javascript", "typescript", "tsx", "jsx"):
            return self._extract_jsdoc_docstrings(source_code)
        elif language == "java":
            return self._extract_javadoc_docstrings(source_code)
        elif language == "go":
            return self._extract_godoc_docstrings(source_code)
        elif language == "rust":
            return self._extract_rustdoc_docstrings(source_code)
        else:
            logger.warning(f"Unsupported language for docstring extraction: {language}")
            return []

    def _extract_python_docstrings(self, source_code: str) -> List[Docstring]:
        """Extract Python docstrings (triple-quoted strings)."""
        docstrings = []
        lines = source_code.split('\n')

        i = 0
        while i < len(lines):
            line = lines[i].strip()

            # Check for triple-quoted string
            if line.startswith('"""') or line.startswith("'''"):
                quote_char = '"""' if line.startswith('"""') else "'''"
                start_line = i + 1  # 1-indexed
                doc_lines = []

                # Check if it's a one-line docstring
                if line.count(quote_char) >= 2:
                    content = line[3:-3].strip()
                    if content:
                        docstrings.append(Docstring(
                            content=content,
                            style=DocstringStyle.PYTHON,
                            start_line=start_line,
                            end_line=start_line,
                        ))
                    i += 1
                    continue

                # Multi-line docstring
                doc_lines.append(line[3:])
                i += 1

                # Find closing quotes
                while i < len(lines):
                    line = lines[i]
                    if quote_char in line:
                        # Found end
                        end_idx = line.index(quote_char)
                        doc_lines.append(line[:end_idx])
                        break
                    doc_lines.append(line)
                    i += 1

                content = '\n'.join(doc_lines).strip()
                if content:
                    docstrings.append(Docstring(
                        content=content,
                        style=DocstringStyle.PYTHON,
                        start_line=start_line,
                        end_line=i + 1,
                    ))

            i += 1

        self.stats["docstrings_extracted"] += len(docstrings)
        return docstrings

    def _extract_jsdoc_docstrings(self, source_code: str) -> List[Docstring]:
        """Extract JSDoc-style comments (/** ... */)."""
        docstrings = []

        # Find all /** ... */ blocks
        pattern = re.compile(r'/\*\*([\s\S]*?)\*/', re.MULTILINE)

        for match in pattern.finditer(source_code):
            content = match.group(1)

            # Clean up the content (remove leading * from each line)
            lines = content.split('\n')
            cleaned_lines = []
            for line in lines:
                line = line.strip()
                if line.startswith('*'):
                    line = line[1:].strip()
                if line:
                    cleaned_lines.append(line)

            if cleaned_lines:
                # Calculate line numbers
                start_pos = match.start()
                start_line = source_code[:start_pos].count('\n') + 1
                end_line = start_line + content.count('\n')

                docstrings.append(Docstring(
                    content='\n'.join(cleaned_lines),
                    style=DocstringStyle.JSDOC,
                    start_line=start_line,
                    end_line=end_line,
                ))

        self.stats["docstrings_extracted"] += len(docstrings)
        return docstrings

    def _extract_javadoc_docstrings(self, source_code: str) -> List[Docstring]:
        """Extract Javadoc-style comments (same as JSDoc)."""
        docstrings = self._extract_jsdoc_docstrings(source_code)

        # Update style to Javadoc
        for doc in docstrings:
            doc.style = DocstringStyle.JAVADOC

        return docstrings

    def _extract_godoc_docstrings(self, source_code: str) -> List[Docstring]:
        """Extract GoDoc-style comments (consecutive // lines)."""
        docstrings = []
        lines = source_code.split('\n')

        i = 0
        while i < len(lines):
            line = lines[i].strip()

            # Check for comment block
            if line.startswith('//'):
                start_line = i + 1
                doc_lines = []

                # Collect consecutive comment lines
                while i < len(lines) and lines[i].strip().startswith('//'):
                    comment = lines[i].strip()[2:].strip()
                    if comment:
                        doc_lines.append(comment)
                    i += 1

                if doc_lines:
                    docstrings.append(Docstring(
                        content='\n'.join(doc_lines),
                        style=DocstringStyle.GODOC,
                        start_line=start_line,
                        end_line=i,
                    ))
                continue

            i += 1

        self.stats["docstrings_extracted"] += len(docstrings)
        return docstrings

    def _extract_rustdoc_docstrings(self, source_code: str) -> List[Docstring]:
        """Extract RustDoc-style comments (/// or //!)."""
        docstrings = []
        lines = source_code.split('\n')

        i = 0
        while i < len(lines):
            line = lines[i].strip()

            # Check for doc comment
            if line.startswith('///') or line.startswith('//!'):
                start_line = i + 1
                doc_lines = []
                marker = '///' if line.startswith('///') else '//!'

                # Collect consecutive doc comment lines
                while i < len(lines):
                    line = lines[i].strip()
                    if line.startswith(marker):
                        comment = line[3:].strip()
                        if comment:
                            doc_lines.append(comment)
                        i += 1
                    else:
                        break

                if doc_lines:
                    docstrings.append(Docstring(
                        content='\n'.join(doc_lines),
                        style=DocstringStyle.RUSTDOC,
                        start_line=start_line,
                        end_line=i,
                    ))
                continue

            i += 1

        self.stats["docstrings_extracted"] += len(docstrings)
        return docstrings

    def link_docstrings_to_units(
        self,
        docstrings: List[Docstring],
        units: List["SemanticUnit"],
    ) -> List[Tuple[Docstring, Optional["SemanticUnit"]]]:
        """
        Link extracted docstrings to their corresponding semantic units.

        Args:
            docstrings: List of extracted docstrings
            units: List of semantic units (functions, classes, etc.)

        Returns:
            List of (docstring, unit) tuples. Unit may be None if no match found.
        """
        linked = []

        for docstring in docstrings:
            # Find the unit that corresponds to this docstring
            matching_unit = None

            for unit in units:
                # For Python-style (docstrings inside the unit)
                if docstring.style == DocstringStyle.PYTHON:
                    # Docstring should be inside the unit (first statement)
                    if unit.start_line < docstring.start_line <= unit.end_line:
                        matching_unit = unit
                        break
                else:
                    # For other languages (docstrings before the unit)
                    # Docstring should be right before the unit
                    # Allow a small gap (e.g., decorators, annotations)
                    if unit.start_line >= docstring.end_line and \
                       unit.start_line <= docstring.end_line + 5:
                        matching_unit = unit
                        break

            if matching_unit:
                docstring.unit_name = matching_unit.name
                docstring.unit_type = matching_unit.unit_type

            linked.append((docstring, matching_unit))

        return linked

    def extract_and_link(
        self,
        source_code: str,
        language: str,
        units: List["SemanticUnit"],
        file_path: str = "",
    ) -> List[Tuple[Docstring, Optional["SemanticUnit"]]]:
        """
        Extract docstrings and link them to semantic units in one step.

        Args:
            source_code: Source code content
            language: Programming language
            units: Semantic units from the same source
            file_path: Path to source file

        Returns:
            List of (docstring, unit) tuples
        """
        docstrings = self.extract_from_code(source_code, language, file_path)
        return self.link_docstrings_to_units(docstrings, units)

    def get_stats(self) -> Dict[str, Any]:
        """Get extraction statistics."""
        return {
            "docstrings_extracted": self.stats["docstrings_extracted"],
            "languages_processed": list(self.stats["languages_processed"]),
        }


def format_docstring_for_search(docstring: Docstring, unit_name: str = "") -> str:
    """
    Format docstring content for indexing/search.

    Args:
        docstring: Docstring object
        unit_name: Name of the associated unit

    Returns:
        Formatted string for indexing
    """
    parts = []

    if unit_name:
        parts.append(f"Documentation for {unit_name}:")

    parts.append(docstring.clean_content())

    return '\n'.join(parts)


def extract_summary(docstring_content: str, max_length: int = 200) -> str:
    """
    Extract a brief summary from docstring content.

    Args:
        docstring_content: Full docstring content
        max_length: Maximum summary length

    Returns:
        Summary string
    """
    # Get first paragraph or sentence
    paragraphs = docstring_content.split('\n\n')
    first_para = paragraphs[0].strip() if paragraphs else docstring_content

    # Take first sentence
    sentences = re.split(r'[.!?]\s+', first_para)
    summary = sentences[0] if sentences else first_para

    # Truncate if too long
    if len(summary) > max_length:
        summary = summary[:max_length-3] + "..."

    return summary
