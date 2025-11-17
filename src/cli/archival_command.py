"""CLI command for project archival operations."""

import asyncio
import sys
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.memory.project_archival import ProjectArchivalManager, ProjectState
from src.config import get_config


console = Console()


def show_status():
    """Show status of all projects."""
    config = get_config()
    archival_file = Path.home() / ".claude-rag" / "project_states.json"
    manager = ProjectArchivalManager(str(archival_file))

    all_projects = manager.get_all_projects()

    if not all_projects:
        console.print("[yellow]No projects found.[/yellow]")
        return

    # Create table
    table = Table(title="Project States", show_header=True, header_style="bold magenta")
    table.add_column("Project", style="cyan")
    table.add_column("State", style="green")
    table.add_column("Last Activity", style="yellow")
    table.add_column("Days Inactive", style="red")
    table.add_column("Searches", justify="right")
    table.add_column("Files", justify="right")

    for project_name, data in sorted(all_projects.items()):
        state = data.get("state", "active")
        last_activity = data.get("last_activity", "Unknown")[:10]  # Date part only
        days_inactive = f"{manager.get_days_since_activity(project_name):.1f}"
        searches = str(data.get("searches_count", 0))
        files = str(data.get("files_indexed", 0))

        # Color state
        state_colored = state
        if state == "active":
            state_colored = f"[green]{state}[/green]"
        elif state == "archived":
            state_colored = f"[red]{state}[/red]"
        elif state == "paused":
            state_colored = f"[yellow]{state}[/yellow]"

        table.add_row(project_name, state_colored, last_activity, days_inactive, searches, files)

    console.print(table)

    # Show inactive projects
    inactive = manager.get_inactive_projects()
    if inactive:
        console.print(f"\n[yellow]⚠️  {len(inactive)} project(s) inactive for 45+ days (candidates for archival):[/yellow]")
        for proj in inactive:
            days = manager.get_days_since_activity(proj)
            console.print(f"  - {proj} ({days:.0f} days inactive)")


def archive_project(project_name: str):
    """Archive a project."""
    archival_file = Path.home() / ".claude-rag" / "project_states.json"
    manager = ProjectArchivalManager(str(archival_file))

    result = manager.archive_project(project_name)

    if result["success"]:
        console.print(f"[green]✓ {result['message']}[/green]")
    else:
        console.print(f"[red]✗ {result['message']}[/red]")


def reactivate_project(project_name: str):
    """Reactivate a project."""
    archival_file = Path.home() / ".claude-rag" / "project_states.json"
    manager = ProjectArchivalManager(str(archival_file))

    result = manager.reactivate_project(project_name)

    if result["success"]:
        console.print(f"[green]✓ {result['message']}[/green]")
    else:
        console.print(f"[red]✗ {result['message']}[/red]")


def main():
    """Main entry point for archival CLI."""
    import argparse

    parser = argparse.ArgumentParser(description="Project archival and lifecycle management")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Status command
    subparsers.add_parser("status", help="Show status of all projects")

    # Archive command
    archive_parser = subparsers.add_parser("archive", help="Archive a project")
    archive_parser.add_argument("project_name", help="Name of project to archive")

    # Reactivate command
    reactivate_parser = subparsers.add_parser("reactivate", help="Reactivate an archived project")
    reactivate_parser.add_argument("project_name", help="Name of project to reactivate")

    args = parser.parse_args()

    if args.command == "status":
        show_status()
    elif args.command == "archive":
        archive_project(args.project_name)
    elif args.command == "reactivate":
        reactivate_project(args.project_name)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
