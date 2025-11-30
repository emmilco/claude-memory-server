#!/usr/bin/env python3
"""
Deduplicate TODO.md and create clean TODO_NEW.md

Usage: python scripts/deduplicate_todo.py
"""

import re
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Set, Tuple

# Next available IDs for conflicts
NEXT_IDS = {
    'BUG': 271,
    'REF': 237,
    'PERF': 12,
    'TEST': 29,
    'SEC': 1,
    'DOC': 23,
    'FEAT': 1,
    'UX': 52,
    'INVEST': 7
}

def extract_task_id(line: str) -> str | None:
    """Extract task ID like BUG-123 from checkbox line"""
    match = re.search(r'\*\*([A-Z]+-\d+)\*\*:', line)
    return match.group(1) if match else None

def parse_task(lines: List[str], start_idx: int) -> Tuple[str, List[str], int]:
    """Parse a full task starting from checkbox line. Returns (task_id, task_lines, next_idx)"""
    first_line = lines[start_idx]
    task_id = extract_task_id(first_line)

    if not task_id:
        return None, [], start_idx + 1

    task_lines = [first_line]
    i = start_idx + 1

    # Collect all indented lines belonging to this task
    while i < len(lines):
        line = lines[i]
        # Stop at next task or section header
        if line.strip().startswith('- [ ]') or line.strip().startswith('- [x]'):
            break
        if line.strip().startswith('#'):
            break
        if line.strip().startswith('**'):
            break
        task_lines.append(line)
        i += 1

    return task_id, task_lines, i

def get_task_signature(task_lines: List[str]) -> str:
    """Get a signature for deduplication - location field"""
    for line in task_lines:
        if '**Location:**' in line:
            return line.strip()
    return ""

def is_completed(first_line: str) -> bool:
    """Check if task is marked completed"""
    return first_line.strip().startswith('- [x]')

def get_task_prefix(task_id: str) -> str:
    """Get prefix like BUG, REF from task ID"""
    return task_id.split('-')[0]

def read_todo_file(file_path: Path) -> List[str]:
    """Read TODO.md and return lines"""
    with open(file_path, 'r', encoding='utf-8') as f:
        return f.readlines()

def main():
    todo_path = Path('/Users/elliotmilco/Documents/GitHub/claude-memory-server/TODO.md')
    output_path = Path('/Users/elliotmilco/Documents/GitHub/claude-memory-server/TODO_NEW.md')

    print("Reading TODO.md...")
    lines = read_todo_file(todo_path)
    print(f"Total lines: {len(lines)}")

    # Parse all tasks
    tasks: Dict[str, List[List[str]]] = defaultdict(list)  # task_id -> list of occurrences
    open_tasks: Dict[str, List[str]] = {}  # task_id -> task_lines (for open tasks only)

    i = 0
    while i < len(lines):
        line = lines[i]
        if line.strip().startswith('- [ ]'):
            task_id, task_lines, next_i = parse_task(lines, i)
            if task_id:
                tasks[task_id].append(task_lines)
                # Track open tasks
                if not is_completed(task_lines[0]):
                    if task_id not in open_tasks:
                        open_tasks[task_id] = task_lines
            i = next_i
        else:
            i += 1

    print(f"\nTotal task IDs found: {len(tasks)}")

    # Identify duplicates and conflicts
    duplicates = []
    conflicts = []
    id_reassignments = {}

    for task_id, occurrences in tasks.items():
        if len(occurrences) > 1:
            # Check if they're true duplicates (same location) or conflicts (different locations)
            signatures = [get_task_signature(occ) for occ in occurrences]
            unique_sigs = set(sig for sig in signatures if sig)

            if len(unique_sigs) <= 1:
                # True duplicate - same location or no location
                duplicates.append(task_id)
                # Keep the most complete version
                longest = max(occurrences, key=lambda x: len(''.join(x)))
                open_tasks[task_id] = longest
            else:
                # Conflict - same ID, different locations
                conflicts.append(task_id)
                # Keep first, reassign rest
                for idx, occ in enumerate(occurrences[1:], start=1):
                    prefix = get_task_prefix(task_id)
                    new_id = f"{prefix}-{NEXT_IDS[prefix]}"
                    NEXT_IDS[prefix] += 1

                    # Update task ID in lines
                    updated_lines = []
                    for line in occ:
                        updated_line = line.replace(f"**{task_id}**:", f"**{new_id}**:")
                        updated_lines.append(updated_line)

                    open_tasks[new_id] = updated_lines
                    id_reassignments[f"{task_id} (occurrence {idx+1})"] = new_id

    print(f"\nDuplicates (same content): {len(duplicates)}")
    print(f"Conflicts (same ID, different content): {len(conflicts)}")
    print(f"ID reassignments: {len(id_reassignments)}")

    # Organize tasks by category
    categories = {
        'SEC': [],
        'BUG': [],
        'REF': [],
        'PERF': [],
        'TEST': [],
        'DOC': [],
        'FEAT': [],
        'UX': [],
        'INVEST': []
    }

    for task_id, task_lines in sorted(open_tasks.items()):
        prefix = get_task_prefix(task_id)
        if prefix in categories:
            categories[prefix].append((task_id, task_lines))

    # Sort each category by ID number
    for prefix in categories:
        categories[prefix].sort(key=lambda x: int(x[0].split('-')[1]))

    # Write output file
    print(f"\nWriting TODO_NEW.md...")
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("# TODO\n\n")
        f.write("Last updated: 2025-11-30\n\n")

        f.write("## How to Use This File\n\n")
        f.write("- Task IDs: BUG-XXX (bugs), REF-XXX (refactoring), FEAT-XXX (features), TEST-XXX (testing), PERF-XXX (performance), SEC-XXX (security), DOC-XXX (documentation), UX-XXX (user experience)\n")
        f.write("- Priority: Tasks marked 🔴 are critical, 🟡 are high priority, 🟢 are medium\n\n")
        f.write("---\n\n")

        # Critical priority section
        f.write("## 🔴 Critical Priority\n\n")
        critical_count = 0
        for prefix in ['SEC', 'BUG']:
            for task_id, task_lines in categories[prefix]:
                # Check if task is marked critical in first line
                first_line = task_lines[0]
                if any(marker in first_line for marker in ['CRITICAL', '🔴', '🔥']):
                    for line in task_lines:
                        f.write(line)
                    f.write('\n')
                    critical_count += 1

        # High priority section
        f.write("## 🟡 High Priority\n\n")
        high_count = 0
        for prefix in ['BUG', 'REF', 'PERF']:
            for task_id, task_lines in categories[prefix]:
                first_line = task_lines[0]
                if any(marker in first_line for marker in ['HIGH', '🟡']) and not any(marker in first_line for marker in ['CRITICAL', '🔴']):
                    for line in task_lines:
                        f.write(line)
                    f.write('\n')
                    high_count += 1

        # Category sections
        f.write("## Bugs (BUG-*)\n\n")
        bug_count = 0
        for task_id, task_lines in categories['BUG']:
            first_line = task_lines[0]
            # Skip if already in critical/high
            if not any(marker in first_line for marker in ['CRITICAL', '🔴', 'HIGH', '🟡']):
                for line in task_lines:
                    f.write(line)
                f.write('\n')
                bug_count += 1

        f.write("## Refactoring (REF-*)\n\n")
        ref_count = 0
        for task_id, task_lines in categories['REF']:
            first_line = task_lines[0]
            if not any(marker in first_line for marker in ['CRITICAL', '🔴', 'HIGH', '🟡']):
                for line in task_lines:
                    f.write(line)
                f.write('\n')
                ref_count += 1

        f.write("## Performance (PERF-*)\n\n")
        for task_id, task_lines in categories['PERF']:
            first_line = task_lines[0]
            if not any(marker in first_line for marker in ['CRITICAL', '🔴', 'HIGH', '🟡']):
                for line in task_lines:
                    f.write(line)
                f.write('\n')

        f.write("## Testing (TEST-*)\n\n")
        for task_id, task_lines in categories['TEST']:
            for line in task_lines:
                f.write(line)
            f.write('\n')

        f.write("## Documentation (DOC-*)\n\n")
        for task_id, task_lines in categories['DOC']:
            for line in task_lines:
                f.write(line)
            f.write('\n')

        f.write("## Features (FEAT-*)\n\n")
        for task_id, task_lines in categories['FEAT']:
            for line in task_lines:
                f.write(line)
            f.write('\n')

        f.write("## UX Improvements (UX-*)\n\n")
        for task_id, task_lines in categories['UX']:
            for line in task_lines:
                f.write(line)
            f.write('\n')

        f.write("## Investigations (INVEST-*)\n\n")
        for task_id, task_lines in categories['INVEST']:
            for line in task_lines:
                f.write(line)
            f.write('\n')

    # Count lines in new file
    with open(output_path, 'r', encoding='utf-8') as f:
        new_lines = len(f.readlines())

    # Summary
    print("\n" + "="*60)
    print("DEDUPLICATION SUMMARY")
    print("="*60)
    print(f"Unique open tasks: {len(open_tasks)}")
    print(f"True duplicates removed: {len(duplicates)}")
    print(f"ID conflicts resolved: {len(conflicts)}")
    print(f"\nID Reassignments:")
    for old_id, new_id in id_reassignments.items():
        print(f"  {old_id} → {new_id}")
    print(f"\nTask counts by category:")
    for prefix, tasks_list in categories.items():
        print(f"  {prefix}: {len(tasks_list)} tasks")
    print(f"\nOriginal file: {len(lines)} lines")
    print(f"New file: {new_lines} lines")
    print(f"Reduction: {len(lines) - new_lines} lines ({100*(len(lines)-new_lines)/len(lines):.1f}%)")
    print("="*60)

if __name__ == '__main__':
    main()
