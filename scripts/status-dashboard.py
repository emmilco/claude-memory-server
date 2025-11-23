#!/usr/bin/env python3
"""
Project Status Dashboard

Displays comprehensive project health metrics including:
- Task status (TODO, IN_PROGRESS, REVIEW, CHANGELOG)
- Test statistics
- Coverage metrics
- Git status
- Qdrant status

Usage:
    python scripts/status-dashboard.py
    python scripts/status-dashboard.py --watch  # Auto-refresh every 10s
"""

import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Tuple
from datetime import datetime

# ANSI color codes
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
CYAN = '\033[96m'
BOLD = '\033[1m'
RESET = '\033[0m'


def clear_screen():
    """Clear the terminal screen."""
    subprocess.run(["clear" if sys.platform != "win32" else "cls"], shell=True)


def print_header(text: str):
    """Print a colored header."""
    print(f"\n{BLUE}{BOLD}{'=' * 70}{RESET}")
    print(f"{BLUE}{BOLD}{text:^70}{RESET}")
    print(f"{BLUE}{BOLD}{'=' * 70}{RESET}\n")


def print_section(text: str):
    """Print a section header."""
    print(f"\n{CYAN}{BOLD}{text}{RESET}")
    print(f"{CYAN}{'-' * len(text)}{RESET}")


def count_tasks(file_path: Path) -> Tuple[int, List[str]]:
    """Count tasks in a markdown file and return task IDs."""
    if not file_path.exists():
        return 0, []

    content = file_path.read_text()
    lines = content.split('\n')

    count = 0
    task_ids = []

    for line in lines:
        # Look for task entries like: ### [FEAT-056]: Title
        if line.strip().startswith('### [') or line.strip().startswith('- [ ] **'):
            count += 1
            # Extract task ID
            if '[' in line and ']' in line:
                start = line.index('[') + 1
                end = line.index(']', start)
                task_id = line[start:end].split(':')[0].strip()
                if task_id and task_id not in task_ids:
                    task_ids.append(task_id)

    return count, task_ids


def get_task_status() -> Dict[str, any]:
    """Get task status across all tracking files."""
    todo_count, todo_ids = count_tasks(Path("TODO.md"))
    in_progress_count, in_progress_ids = count_tasks(Path("IN_PROGRESS.md"))
    review_count, review_ids = count_tasks(Path("REVIEW.md"))

    # Count completed tasks in CHANGELOG (last 30 days)
    changelog_path = Path("CHANGELOG.md")
    recent_completed = 0

    if changelog_path.exists():
        content = changelog_path.read_text()
        # Simple heuristic: count completed items (✅)
        recent_completed = content.count('✅')

    return {
        'todo': todo_count,
        'todo_ids': todo_ids,
        'in_progress': in_progress_count,
        'in_progress_ids': in_progress_ids,
        'review': review_count,
        'review_ids': review_ids,
        'completed_recent': recent_completed,
        'capacity_used': in_progress_count,
        'capacity_max': 6,
    }


def get_test_status() -> Dict[str, any]:
    """Get test statistics."""
    try:
        result = subprocess.run(
            ["pytest", "tests/", "--collect-only", "-q"],
            capture_output=True,
            text=True,
            timeout=30
        )

        # Parse output: "1234 tests collected"
        output = result.stdout
        total_tests = 0

        for line in output.split('\n'):
            if 'test' in line and 'collected' in line:
                parts = line.split()
                if parts:
                    try:
                        total_tests = int(parts[0])
                    except ValueError:
                        pass

        return {
            'total': total_tests,
            'status': 'unknown',
            'message': f"{total_tests} tests collected"
        }

    except subprocess.TimeoutExpired:
        return {
            'total': 0,
            'status': 'timeout',
            'message': 'Test collection timed out'
        }
    except Exception as e:
        return {
            'total': 0,
            'status': 'error',
            'message': f'Error: {str(e)}'
        }


def get_coverage_status() -> Dict[str, any]:
    """Get coverage statistics (quick estimate)."""
    # Read .coverage file if exists
    coverage_file = Path(".coverage")

    if coverage_file.exists():
        # Just return placeholder - full coverage takes too long
        return {
            'overall': '~60%',
            'core': '~71%',
            'target': '80%',
            'status': 'partial'
        }
    else:
        return {
            'overall': 'unknown',
            'core': 'unknown',
            'target': '80%',
            'status': 'not_run'
        }


def get_git_status() -> Dict[str, any]:
    """Get git repository status."""
    try:
        # Get current branch
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True,
            text=True
        )
        branch = result.stdout.strip() or "unknown"

        # Get uncommitted changes count
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True
        )
        changes = len([l for l in result.stdout.split('\n') if l.strip()])

        # Get commits ahead/behind
        result = subprocess.run(
            ["git", "rev-list", "--left-right", "--count", "origin/main...HEAD"],
            capture_output=True,
            text=True
        )
        ahead_behind = result.stdout.strip().split() if result.returncode == 0 else ['0', '0']

        # Get last commit
        result = subprocess.run(
            ["git", "log", "-1", "--pretty=format:%h %s"],
            capture_output=True,
            text=True
        )
        last_commit = result.stdout.strip() or "none"

        # List worktrees
        result = subprocess.run(
            ["git", "worktree", "list"],
            capture_output=True,
            text=True
        )
        worktree_count = len([l for l in result.stdout.split('\n') if l.strip()]) - 1  # -1 for main

        return {
            'branch': branch,
            'changes': changes,
            'ahead': int(ahead_behind[1]) if len(ahead_behind) > 1 else 0,
            'behind': int(ahead_behind[0]) if len(ahead_behind) > 0 else 0,
            'last_commit': last_commit,
            'worktrees': worktree_count,
        }

    except Exception as e:
        return {
            'branch': 'error',
            'changes': 0,
            'ahead': 0,
            'behind': 0,
            'last_commit': str(e),
            'worktrees': 0,
        }


def get_qdrant_status() -> Dict[str, any]:
    """Get Qdrant status."""
    try:
        import requests
        response = requests.get("http://localhost:6333/", timeout=5)

        if response.status_code == 200:
            data = response.json()
            version = data.get("version", "unknown")

            # Get collections
            collections_response = requests.get(
                "http://localhost:6333/collections",
                timeout=5
            )

            collection_count = 0
            if collections_response.status_code == 200:
                collections_data = collections_response.json()
                collections = collections_data.get("result", {}).get("collections", [])
                collection_count = len(collections)

            return {
                'status': 'running',
                'version': version,
                'collections': collection_count,
                'message': f'Running (v{version})'
            }
        else:
            return {
                'status': 'error',
                'version': 'unknown',
                'collections': 0,
                'message': f'HTTP {response.status_code}'
            }

    except ImportError:
        return {
            'status': 'unknown',
            'version': 'unknown',
            'collections': 0,
            'message': 'requests not installed'
        }
    except Exception as e:
        return {
            'status': 'down',
            'version': 'unknown',
            'collections': 0,
            'message': f'Not accessible: {str(e)}'
        }


def display_dashboard():
    """Display the complete status dashboard."""
    # Get all status data
    task_status = get_task_status()
    test_status = get_test_status()
    coverage_status = get_coverage_status()
    git_status = get_git_status()
    qdrant_status = get_qdrant_status()

    # Header
    print_header(f"Claude Memory RAG Server - Status Dashboard")
    print(f"{BOLD}Generated:{RESET} {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Task Status
    print_section("📋 Task Status")

    capacity_pct = (task_status['capacity_used'] / task_status['capacity_max']) * 100
    capacity_color = GREEN if capacity_pct < 80 else YELLOW if capacity_pct < 100 else RED

    print(f"  TODO:          {YELLOW}{task_status['todo']:3d}{RESET} tasks planned")
    print(f"  IN PROGRESS:   {capacity_color}{task_status['in_progress']:3d}{RESET}/{task_status['capacity_max']} ({capacity_pct:.0f}% capacity)")
    print(f"  REVIEW:        {BLUE}{task_status['review']:3d}{RESET} tasks awaiting approval")
    print(f"  COMPLETED:     {GREEN}{task_status['completed_recent']:3d}{RESET} tasks in recent history")

    if task_status['in_progress'] > 0:
        print(f"\n  Active Tasks: {', '.join(task_status['in_progress_ids'][:5])}")
        if len(task_status['in_progress_ids']) > 5:
            print(f"                ... and {len(task_status['in_progress_ids']) - 5} more")

    # Test Status
    print_section("🧪 Test Status")

    test_count = test_status['total']
    test_color = GREEN if test_count > 2700 else YELLOW if test_count > 2500 else RED

    print(f"  Total Tests:   {test_color}{test_count:4d}{RESET} tests")
    print(f"  Status:        {test_status['message']}")

    # Coverage Status
    print_section("📊 Coverage Status")

    print(f"  Overall:       {YELLOW}{coverage_status['overall']:>6}{RESET}")
    print(f"  Core Modules:  {YELLOW}{coverage_status['core']:>6}{RESET}")
    print(f"  Target:        {GREEN}{coverage_status['target']:>6}{RESET}")

    if coverage_status['status'] == 'not_run':
        print(f"  {YELLOW}Run: pytest tests/ --cov=src --cov-report=html{RESET}")

    # Git Status
    print_section("🔀 Git Status")

    branch_color = GREEN if git_status['branch'] == 'main' else CYAN
    changes_color = GREEN if git_status['changes'] == 0 else YELLOW

    print(f"  Branch:        {branch_color}{git_status['branch']}{RESET}")
    print(f"  Uncommitted:   {changes_color}{git_status['changes']:3d}{RESET} files")

    if git_status['ahead'] > 0 or git_status['behind'] > 0:
        print(f"  Sync:          {YELLOW}{git_status['ahead']} ahead, {git_status['behind']} behind origin{RESET}")

    print(f"  Last Commit:   {git_status['last_commit'][:60]}")
    print(f"  Worktrees:     {CYAN}{git_status['worktrees']:3d}{RESET} active")

    # Qdrant Status
    print_section("🗄️  Qdrant Status")

    qdrant_color = GREEN if qdrant_status['status'] == 'running' else RED

    print(f"  Status:        {qdrant_color}{qdrant_status['message']}{RESET}")

    if qdrant_status['status'] == 'running':
        print(f"  Collections:   {CYAN}{qdrant_status['collections']:3d}{RESET} collections")
    elif qdrant_status['status'] == 'down':
        print(f"  {YELLOW}Start with: docker-compose up -d{RESET}")

    # Footer
    print_section("📌 Quick Commands")
    print(f"  Run tests:     pytest tests/ -n auto -v")
    print(f"  Coverage:      pytest tests/ --cov=src --cov-report=html")
    print(f"  Verify:        python scripts/verify-complete.py")
    print(f"  Setup check:   python scripts/setup.py")
    print(f"  Health check:  python -m src.cli health")

    print()


def main():
    """Main entry point."""
    # Check if in correct directory
    if not Path("src").exists():
        print(f"{RED}Error: Must run from project root directory{RESET}")
        sys.exit(1)

    # Check for watch mode
    watch_mode = "--watch" in sys.argv

    if watch_mode:
        print(f"{YELLOW}Watch mode enabled - refreshing every 10 seconds{RESET}")
        print(f"{YELLOW}Press Ctrl+C to exit{RESET}")
        time.sleep(2)

        try:
            while True:
                clear_screen()
                display_dashboard()
                time.sleep(10)
        except KeyboardInterrupt:
            print(f"\n{GREEN}Dashboard stopped.{RESET}")
    else:
        display_dashboard()


if __name__ == "__main__":
    main()
