"""CLI command for project management operations."""

import asyncio
import logging
import sys

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.core.server import MemoryRAGServer
from src.config import get_config

logger = logging.getLogger(__name__)
console = Console()


async def project_list() -> int:
    """
    List all indexed projects.

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    try:
        console.print("\n[bold blue]Indexed Projects[/bold blue]\n")

        # Initialize server
        config = get_config()
        server = MemoryRAGServer(config)
        await server.initialize()

        # Get project list
        result = await server.list_projects()

        if result["status"] != "success":
            console.print(
                f"[red]Error:[/red] {result.get('message', 'Unknown error')}\n"
            )
            await server.close()
            return 1

        projects = result.get("projects", [])

        if not projects:
            console.print("[dim]No projects indexed yet[/dim]")
            console.print("[dim]Run: python -m src.cli index ./your-project[/dim]\n")
            await server.close()
            return 0

        # Create projects table
        table = Table(show_header=True, header_style="bold cyan")
        table.add_column("Project Name", style="green")
        table.add_column("Memories", justify="right")
        table.add_column("Files", justify="right")
        table.add_column("Functions", justify="right")
        table.add_column("Classes", justify="right")

        for project in projects:
            table.add_row(
                project["name"],
                str(project.get("total_memories", 0)),
                str(project.get("total_files", 0)),
                str(project.get("total_functions", 0)),
                str(project.get("total_classes", 0)),
            )

        console.print(table)
        console.print(f"\n[dim]Total: {len(projects)} projects[/dim]\n")

        await server.close()
        return 0

    except Exception as e:
        console.print(f"\n[red]Error:[/red] Failed to list projects: {e}\n")
        logger.error(f"List projects failed: {e}", exc_info=True)
        return 1


async def project_stats(project_name: str) -> int:
    """
    Show detailed statistics for a project.

    Args:
        project_name: Name of project

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    try:
        console.print(f"\n[bold blue]Project Statistics: {project_name}[/bold blue]\n")

        # Initialize server
        config = get_config()
        server = MemoryRAGServer(config)
        await server.initialize()

        # Get project stats
        result = await server.get_project_details(project_name)

        if result["status"] != "success":
            console.print(
                f"[red]Error:[/red] {result.get('message', 'Unknown error')}\n"
            )
            await server.close()
            return 1

        stats = result.get("statistics", {})

        # Display statistics
        info_table = Table(show_header=False, box=None)
        info_table.add_row("[cyan]Project Name:[/cyan]", project_name)
        info_table.add_row(
            "[cyan]Total Memories:[/cyan]", str(stats.get("total_memories", 0))
        )
        info_table.add_row(
            "[cyan]Total Files:[/cyan]", str(stats.get("total_files", 0))
        )
        info_table.add_row(
            "[cyan]Total Functions:[/cyan]", str(stats.get("total_functions", 0))
        )
        info_table.add_row(
            "[cyan]Total Classes:[/cyan]", str(stats.get("total_classes", 0))
        )

        if stats.get("last_updated"):
            info_table.add_row("[cyan]Last Updated:[/cyan]", str(stats["last_updated"]))

        # Show category breakdown
        if stats.get("categories"):
            info_table.add_row("", "")
            info_table.add_row("[bold]Category Breakdown:[/bold]", "")
            for category, count in stats["categories"].items():
                info_table.add_row(f"  {category}:", str(count))

        # Show context level breakdown
        if stats.get("context_levels"):
            info_table.add_row("", "")
            info_table.add_row("[bold]Context Levels:[/bold]", "")
            for level, count in stats["context_levels"].items():
                info_table.add_row(f"  {level}:", str(count))

        console.print(
            Panel(info_table, title="Project Statistics", border_style="blue")
        )
        console.print()

        await server.close()
        return 0

    except Exception as e:
        console.print(f"\n[red]Error:[/red] Failed to get project stats: {e}\n")
        logger.error(f"Get project stats failed: {e}", exc_info=True)
        return 1


async def project_delete(project_name: str, force: bool = False) -> int:
    """
    Delete a project and all its data.

    Args:
        project_name: Name of project to delete
        force: Skip confirmation prompt

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    try:
        console.print(f"\n[bold red]Delete Project: {project_name}[/bold red]\n")

        # Confirmation prompt
        if not force:
            console.print(
                "[yellow]WARNING: This will permanently delete all memories, files, and data for this project![/yellow]"
            )
            confirmation = input("\nType the project name to confirm deletion: ")
            if confirmation != project_name:
                console.print("\n[dim]Deletion cancelled.[/dim]\n")
                return 0

        # Initialize server
        config = get_config()
        server = MemoryRAGServer(config)
        await server.initialize()

        # Delete project
        result = await server.delete_project(project_name)

        if result["status"] != "success":
            console.print(
                f"[red]Error:[/red] {result.get('message', 'Unknown error')}\n"
            )
            await server.close()
            return 1

        console.print(f"[green]✓[/green] {result['message']}")
        console.print(f"[dim]Deleted {result['memories_deleted']} memories[/dim]\n")

        await server.close()
        return 0

    except Exception as e:
        console.print(f"\n[red]Error:[/red] Failed to delete project: {e}\n")
        logger.error(f"Delete project failed: {e}", exc_info=True)
        return 1


async def project_rename(old_name: str, new_name: str) -> int:
    """
    Rename a project.

    Args:
        old_name: Current project name
        new_name: New project name

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    try:
        console.print("\n[bold blue]Rename Project[/bold blue]\n")
        console.print(f"[cyan]{old_name}[/cyan] → [green]{new_name}[/green]\n")

        # Initialize server
        config = get_config()
        server = MemoryRAGServer(config)
        await server.initialize()

        # Rename project
        result = await server.rename_project(old_name, new_name)

        if result["status"] != "success":
            console.print(
                f"[red]Error:[/red] {result.get('message', 'Unknown error')}\n"
            )
            await server.close()
            return 1

        console.print(f"[green]✓[/green] {result['message']}")
        console.print(f"[dim]Updated {result['memories_updated']} memories[/dim]\n")

        await server.close()
        return 0

    except Exception as e:
        console.print(f"\n[red]Error:[/red] Failed to rename project: {e}\n")
        logger.error(f"Rename project failed: {e}", exc_info=True)
        return 1


def main():
    """Main entry point for project command."""
    import argparse

    parser = argparse.ArgumentParser(description="Project management operations")
    subparsers = parser.add_subparsers(dest="command", help="Project commands")

    # list command
    subparsers.add_parser("list", help="List all indexed projects")

    # stats command
    stats_parser = subparsers.add_parser(
        "stats", help="Show detailed project statistics"
    )
    stats_parser.add_argument("project_name", help="Name of project")

    # delete command
    delete_parser = subparsers.add_parser(
        "delete", help="Delete a project and all its data"
    )
    delete_parser.add_argument("project_name", help="Name of project to delete")
    delete_parser.add_argument(
        "--force", action="store_true", help="Skip confirmation prompt"
    )

    # rename command
    rename_parser = subparsers.add_parser("rename", help="Rename a project")
    rename_parser.add_argument("old_name", help="Current project name")
    rename_parser.add_argument("new_name", help="New project name")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Run appropriate command
    if args.command == "list":
        exit_code = asyncio.run(project_list())
    elif args.command == "stats":
        exit_code = asyncio.run(project_stats(args.project_name))
    elif args.command == "delete":
        exit_code = asyncio.run(project_delete(args.project_name, args.force))
    elif args.command == "rename":
        exit_code = asyncio.run(project_rename(args.old_name, args.new_name))
    else:
        parser.print_help()
        exit_code = 1

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
