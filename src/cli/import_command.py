"""CLI command for importing memories from backups."""

import asyncio
import logging
from pathlib import Path
from typing import Optional
import sys

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Confirm

from src.backup.importer import DataImporter, ConflictStrategy
from src.store.factory import create_store
from src.config import get_config
from src.core.models import MemoryCategory

logger = logging.getLogger(__name__)
console = Console()


async def import_command(
    input_file: str,
    conflict_strategy: str = "keep_newer",
    dry_run: bool = False,
    project: Optional[str] = None,
    category: Optional[str] = None,
    yes: bool = False,
) -> int:
    """
    Import memories from backup file.

    Args:
        input_file: Input file path (JSON or .tar.gz archive)
        conflict_strategy: How to handle conflicts (keep_newer, keep_older, keep_both, skip, merge_metadata)
        dry_run: If True, analyze but don't actually import
        project: Only import this project (selective import)
        category: Only import this category (selective import)
        yes: Skip confirmation prompts

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    try:
        console.print("\n[bold blue]Memory Import[/bold blue]\n")

        # Initialize store
        config = get_config()
        store = create_store(config)
        await store.initialize()

        # Create importer
        importer = DataImporter(store)

        # Parse strategy
        try:
            strategy = ConflictStrategy(conflict_strategy)
        except ValueError:
            console.print(f"[red]Error:[/red] Invalid conflict strategy: {conflict_strategy}")
            console.print(f"Valid strategies: {', '.join(s.value for s in ConflictStrategy)}")
            return 1

        # Parse category filter
        category_filter = MemoryCategory(category) if category else None

        # Detect file format
        input_path = Path(input_file).expanduser()
        if not input_path.exists():
            console.print(f"[red]Error:[/red] File not found: {input_file}")
            return 1

        is_archive = input_path.suffix == ".gz" or input_path.suffixes == [".tar", ".gz"]

        # Display import configuration
        config_table = Table(show_header=False, box=None)
        config_table.add_row("[cyan]Input File:[/cyan]", str(input_path))
        config_table.add_row("[cyan]Format:[/cyan]", "Archive (.tar.gz)" if is_archive else "JSON")
        config_table.add_row("[cyan]Conflict Strategy:[/cyan]", strategy.value)
        config_table.add_row("[cyan]Mode:[/cyan]", "[yellow]DRY RUN[/yellow]" if dry_run else "[green]LIVE IMPORT[/green]")
        if project:
            config_table.add_row("[cyan]Project Filter:[/cyan]", project)
        if category:
            config_table.add_row("[cyan]Category Filter:[/cyan]", category)

        console.print(Panel(config_table, title="Import Configuration", border_style="blue"))
        console.print()

        # Confirmation prompt (skip if --yes or dry-run)
        if not dry_run and not yes:
            if not Confirm.ask("[yellow]⚠ This will modify your database. Continue?[/yellow]"):
                console.print("[yellow]Import cancelled.[/yellow]")
                return 0

        # Perform import with progress indicator
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task(
                "Analyzing import..." if dry_run else "Importing memories...",
                total=None
            )

            if is_archive:
                stats = await importer.import_from_archive(
                    archive_path=input_path,
                    conflict_strategy=strategy,
                    dry_run=dry_run,
                    selective_project=project,
                )
            else:
                stats = await importer.import_from_json(
                    input_path=input_path,
                    conflict_strategy=strategy,
                    dry_run=dry_run,
                    selective_project=project,
                    selective_category=category_filter,
                )

            progress.update(task, completed=True)

        # Display results
        results_table = Table(show_header=False, box=None)

        if dry_run:
            results_table.add_row("[yellow]⚠[/yellow] Dry run completed (no changes made)")
        else:
            results_table.add_row("[green]✓[/green] Import completed successfully")

        results_table.add_row("")
        results_table.add_row("[cyan]Total Memories in File:[/cyan]", str(stats["total_memories"]))
        results_table.add_row("[cyan]Imported:[/cyan]", f"[green]{stats['imported']}[/green]")
        results_table.add_row("[cyan]Skipped:[/cyan]", f"[yellow]{stats['skipped']}[/yellow]")
        results_table.add_row("[cyan]Conflicts:[/cyan]", f"[magenta]{stats['conflicts']}[/magenta]")
        if stats["errors"] > 0:
            results_table.add_row("[cyan]Errors:[/cyan]", f"[red]{stats['errors']}[/red]")

        # Conflict resolution breakdown
        if stats["conflicts"] > 0:
            results_table.add_row("")
            results_table.add_row("[bold]Conflict Resolutions:[/bold]", "")
            resolutions = stats["conflict_resolutions"]
            if resolutions["kept_newer"] > 0:
                results_table.add_row("  Kept Newer:", str(resolutions["kept_newer"]))
            if resolutions["kept_older"] > 0:
                results_table.add_row("  Kept Older:", str(resolutions["kept_older"]))
            if resolutions["kept_both"] > 0:
                results_table.add_row("  Kept Both:", str(resolutions["kept_both"]))
            if resolutions["skipped"] > 0:
                results_table.add_row("  Skipped:", str(resolutions["skipped"]))
            if resolutions["merged"] > 0:
                results_table.add_row("  Merged:", str(resolutions["merged"]))

        border_style = "yellow" if dry_run else "green"
        title = "Dry Run Results" if dry_run else "Import Results"
        console.print(Panel(results_table, title=title, border_style=border_style))
        console.print()

        if dry_run:
            console.print("[yellow]💡 Tip:[/yellow] Remove --dry-run to perform the actual import")
            console.print()

        # Cleanup
        await store.close()

        return 0

    except Exception as e:
        console.print(f"\n[red]Error:[/red] Import failed: {e}")
        logger.error(f"Import command failed: {e}", exc_info=True)
        return 1


def main():
    """Main entry point for import command."""
    import argparse

    parser = argparse.ArgumentParser(description="Import memories from backup file")
    parser.add_argument("input_file", help="Input file path (JSON or .tar.gz archive)")
    parser.add_argument(
        "--strategy",
        dest="conflict_strategy",
        choices=["keep_newer", "keep_older", "keep_both", "skip", "merge_metadata"],
        default="keep_newer",
        help="Conflict resolution strategy (default: keep_newer)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Analyze import without making changes"
    )
    parser.add_argument("--project", help="Only import this project (selective import)")
    parser.add_argument(
        "--category",
        choices=["preference", "fact", "event", "workflow", "context"],
        help="Only import this category (selective import)"
    )
    parser.add_argument(
        "-y", "--yes",
        action="store_true",
        help="Skip confirmation prompts"
    )

    args = parser.parse_args()

    # Run async command
    exit_code = asyncio.run(
        import_command(
            input_file=args.input_file,
            conflict_strategy=args.conflict_strategy,
            dry_run=args.dry_run,
            project=args.project,
            category=args.category,
            yes=args.yes,
        )
    )

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
