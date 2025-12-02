#!/usr/bin/env python3
"""
Assemble changelog fragments into CHANGELOG.md.

This script reads all .md files from changelog.d/, groups them by type
(Added, Changed, Fixed, Removed), and prepends them to CHANGELOG.md
under the [Unreleased] section with today's date.

Usage:
    python scripts/assemble-changelog.py           # Assemble and delete fragments
    python scripts/assemble-changelog.py --dry-run # Preview without changes
    python scripts/assemble-changelog.py --keep    # Assemble but keep fragments

Exit codes:
    0: Success (or no fragments to process)
    1: Error during processing
"""

import argparse
import re
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Dict, List, Tuple

# ANSI color codes
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
RESET = "\033[0m"

# Section type order (for consistent output)
SECTION_ORDER = ["Added", "Changed", "Fixed", "Removed", "Planning"]

# Pattern to match section headers like "### Added" or "### Fixed"
SECTION_PATTERN = re.compile(
    r"^###\s+(Added|Changed|Fixed|Removed|Planning)\s*$", re.IGNORECASE
)


def find_project_root() -> Path:
    """Find the project root directory."""
    # Start from script location
    current = Path(__file__).resolve().parent.parent

    # Verify it looks like the project root
    if (current / "CHANGELOG.md").exists() and (current / "changelog.d").exists():
        return current

    # Fallback to cwd
    cwd = Path.cwd()
    if (cwd / "CHANGELOG.md").exists():
        return cwd

    raise FileNotFoundError("Cannot find project root (no CHANGELOG.md found)")


def get_fragment_files(changelog_d: Path) -> List[Path]:
    """Get all fragment files (excluding README.md and .gitkeep)."""
    fragments = []
    for f in changelog_d.glob("*.md"):
        if f.name.lower() not in ("readme.md",):
            fragments.append(f)
    return sorted(fragments)


def parse_fragment(filepath: Path) -> Dict[str, List[str]]:
    """
    Parse a fragment file and extract entries by section type.

    Returns:
        Dict mapping section type (e.g., 'Fixed') to list of entry lines
    """
    sections: Dict[str, List[str]] = defaultdict(list)
    current_section = None
    current_lines: List[str] = []

    content = filepath.read_text()
    lines = content.split("\n")

    for line in lines:
        # Check for section header
        match = SECTION_PATTERN.match(line.strip())
        if match:
            # Save previous section if any
            if current_section and current_lines:
                # Join and strip trailing whitespace, then split back
                section_content = "\n".join(current_lines).strip()
                if section_content:
                    sections[current_section].append(section_content)

            # Start new section
            current_section = match.group(1).capitalize()
            current_lines = []
        elif current_section:
            # Accumulate lines for current section
            current_lines.append(line)

    # Don't forget the last section
    if current_section and current_lines:
        section_content = "\n".join(current_lines).strip()
        if section_content:
            sections[current_section].append(section_content)

    return dict(sections)


def merge_fragments(fragments: List[Path]) -> Tuple[Dict[str, List[str]], List[str]]:
    """
    Parse and merge all fragments.

    Returns:
        Tuple of (merged sections dict, list of processed filenames)
    """
    merged: Dict[str, List[str]] = defaultdict(list)
    processed = []

    for frag in fragments:
        sections = parse_fragment(frag)
        for section_type, entries in sections.items():
            merged[section_type].extend(entries)
        processed.append(frag.name)

    return dict(merged), processed


def format_changelog_entry(sections: Dict[str, List[str]], today: str) -> str:
    """Format merged sections into changelog entry text."""
    if not sections:
        return ""

    lines = []

    for section_type in SECTION_ORDER:
        if section_type in sections and sections[section_type]:
            lines.append(f"### {section_type} - {today}")
            for entry in sections[section_type]:
                lines.append(entry)
            lines.append("")  # Blank line after section

    return "\n".join(lines)


def insert_into_changelog(changelog_path: Path, new_content: str) -> str:
    """
    Insert new content into CHANGELOG.md after [Unreleased] header.

    Returns the updated changelog content.
    """
    content = changelog_path.read_text()

    # Find the [Unreleased] section
    unreleased_pattern = re.compile(r"^## \[Unreleased\]\s*$", re.MULTILINE)
    match = unreleased_pattern.search(content)

    if not match:
        raise ValueError("Could not find '## [Unreleased]' section in CHANGELOG.md")

    # Insert after the [Unreleased] line
    insert_pos = match.end()

    # Make sure we have proper spacing
    new_content_formatted = "\n\n" + new_content.strip() + "\n"

    updated = (
        content[:insert_pos] + new_content_formatted + content[insert_pos:].lstrip("\n")
    )

    return updated


def main():
    parser = argparse.ArgumentParser(
        description="Assemble changelog fragments into CHANGELOG.md"
    )
    parser.add_argument(
        "--dry-run",
        "-n",
        action="store_true",
        help="Preview changes without modifying files",
    )
    parser.add_argument(
        "--keep",
        "-k",
        action="store_true",
        help="Keep fragment files after assembly (do not delete)",
    )
    parser.add_argument(
        "--no-stage", action="store_true", help="Do not stage changes in git"
    )
    args = parser.parse_args()

    try:
        root = find_project_root()
    except FileNotFoundError as e:
        print(f"{RED}Error: {e}{RESET}")
        return 1

    changelog_d = root / "changelog.d"
    changelog_path = root / "CHANGELOG.md"

    if not changelog_d.exists():
        print(f"{RED}Error: changelog.d/ directory not found{RESET}")
        return 1

    if not changelog_path.exists():
        print(f"{RED}Error: CHANGELOG.md not found{RESET}")
        return 1

    # Get fragment files
    fragments = get_fragment_files(changelog_d)

    if not fragments:
        print(f"{YELLOW}No changelog fragments found in changelog.d/{RESET}")
        return 0

    print(f"{BLUE}Found {len(fragments)} fragment(s):{RESET}")
    for f in fragments:
        print(f"  - {f.name}")

    # Parse and merge
    sections, processed = merge_fragments(fragments)

    if not sections:
        print(f"{YELLOW}No valid changelog entries found in fragments{RESET}")
        return 0

    # Format entry
    today = date.today().strftime("%Y-%m-%d")
    new_content = format_changelog_entry(sections, today)

    print(f"\n{BLUE}Generated changelog entry:{RESET}")
    print("-" * 40)
    print(new_content)
    print("-" * 40)

    if args.dry_run:
        print(f"\n{YELLOW}Dry run - no changes made{RESET}")
        return 0

    # Update CHANGELOG.md
    try:
        updated_changelog = insert_into_changelog(changelog_path, new_content)
        changelog_path.write_text(updated_changelog)
        print(f"\n{GREEN}Updated CHANGELOG.md{RESET}")
    except ValueError as e:
        print(f"{RED}Error: {e}{RESET}")
        return 1

    # Delete fragments (unless --keep)
    if not args.keep:
        for frag in fragments:
            frag.unlink()
            print(f"  Deleted {frag.name}")
        print(f"{GREEN}Deleted {len(fragments)} fragment file(s){RESET}")
    else:
        print(f"{YELLOW}Keeping fragment files (--keep){RESET}")

    # Stage changes in git (unless --no-stage)
    if not args.no_stage:
        import subprocess

        try:
            # Stage CHANGELOG.md
            subprocess.run(["git", "add", str(changelog_path)], check=True, cwd=root)

            # Stage deleted fragments
            if not args.keep:
                for frag in fragments:
                    subprocess.run(["git", "add", str(frag)], check=False, cwd=root)

            print(f"{GREEN}Staged changes in git{RESET}")
        except subprocess.CalledProcessError:
            print(f"{YELLOW}Warning: Could not stage changes in git{RESET}")

    print(f"\n{GREEN}Done! Review and commit the changes.{RESET}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
