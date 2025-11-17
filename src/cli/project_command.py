"""CLI command for project management operations."""

import asyncio
import logging
import sys
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.core.server import MemoryRAGServer
from src.config import get_config

logger = logging.getLogger(__name__)
console = Console()


async def project_switch(project_name: str) -> int:
    """
    Switch to a different project.

    Args:
        project_name: Name of project to switch to

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    try:
        console.print(f"\n[bold blue]Switching to Project: {project_name}[/bold blue]\n")

        # Initialize server
        config = get_config()
        server = MemoryRAGServer(config)
        await server.initialize()

        # Switch project
        result = await server.switch_project(project_name)

        # Display results
        info_table = Table(show_header=False, box=None)
        info_table.add_row("[green]✓[/green] Project switched successfully")
        info_table.add_row("")
        info_table.add_row("[cyan]Project Name:[/cyan]", result["project_name"])
        if result.get("project_path"):
            info_table.add_row("[cyan]Project Path:[/cyan]", result["project_path"])
        if result.get("git_repo"):
            info_table.add_row("[cyan]Git Repository:[/cyan]", result["git_repo"])
        if result.get("git_branch"):
            info_table.add_row("[cyan]Git Branch:[/cyan]", result["git_branch"])

        # Show statistics if available
        if result.get("statistics"):
            stats = result["statistics"]
            info_table.add_row("")
            info_table.add_row("[bold]Project Statistics:[/bold]", "")
            info_table.add_row("  Total Memories:", str(stats.get("total_memories", 0)))
            info_table.add_row("  Files Indexed:", str(stats.get("total_files", 0)))
            info_table.add_row("  Functions:", str(stats.get("total_functions", 0)))
            info_table.add_row("  Classes:", str(stats.get("total_classes", 0)))

        console.print(Panel(info_table, title="Project Switch", border_style="green"))
        console.print()

        await server.close()
        return 0

    except ValueError as e:
        console.print(f"\n[red]Error:[/red] {e}\n")
        return 1
    except Exception as e:
        console.print(f"\n[red]Error:[/red] Failed to switch project: {e}\n")
        logger.error(f"Project switch failed: {e}", exc_info=True)
        return 1


async def project_current() -> int:
    """
    Show current active project.

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    try:
        console.print("\n[bold blue]Current Active Project[/bold blue]\n")

        # Initialize server
        config = get_config()
        server = MemoryRAGServer(config)
        await server.initialize()

        # Get active project
        result = await server.get_active_project()

        if result["status"] != "success":
            console.print(f"[yellow]{result['message']}[/yellow]\n")
            await server.close()
            return 0

        # Display current project
        info_table = Table(show_header=False, box=None)
        info_table.add_row("[cyan]Project Name:[/cyan]", result["project_name"])
        if result.get("project_path"):
            info_table.add_row("[cyan]Project Path:[/cyan]", result["project_path"])
        if result.get("git_repo"):
            info_table.add_row("[cyan]Git Repository:[/cyan]", result["git_repo"])
        if result.get("git_branch"):
            info_table.add_row("[cyan]Git Branch:[/cyan]", result["git_branch"])
        if result.get("last_activity"):
            info_table.add_row("[cyan]Last Activity:[/cyan]", result["last_activity"])
        info_table.add_row("[cyan]File Activity Count:[/cyan]", str(result.get("file_activity_count", 0)))

        # Show statistics if available
        if result.get("statistics"):
            stats = result["statistics"]
            info_table.add_row("")
            info_table.add_row("[bold]Project Statistics:[/bold]", "")
            info_table.add_row("  Total Memories:", str(stats.get("total_memories", 0)))
            info_table.add_row("  Files Indexed:", str(stats.get("total_files", 0)))
            info_table.add_row("  Functions:", str(stats.get("total_functions", 0)))
            info_table.add_row("  Classes:", str(stats.get("total_classes", 0)))

        console.print(Panel(info_table, title="Active Project", border_style="blue"))
        console.print()

        await server.close()
        return 0

    except Exception as e:
        console.print(f"\n[red]Error:[/red] Failed to get active project: {e}\n")
        logger.error(f"Get active project failed: {e}", exc_info=True)
        return 1


def main():
    """Main entry point for project command."""
    import argparse

    parser = argparse.ArgumentParser(description="Project management operations")
    subparsers = parser.add_subparsers(dest="command", help="Project commands")

    # switch command
    switch_parser = subparsers.add_parser("switch", help="Switch to a different project")
    switch_parser.add_argument("project_name", help="Name of project to switch to")

    # current command
    current_parser = subparsers.add_parser("current", help="Show current active project")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Run appropriate command
    if args.command == "switch":
        exit_code = asyncio.run(project_switch(args.project_name))
    elif args.command == "current":
        exit_code = asyncio.run(project_current())
    else:
        parser.print_help()
        exit_code = 1

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
