"""CLI command for backup management."""

import asyncio
import logging
from pathlib import Path
from typing import List, Optional
from datetime import datetime, UTC
import sys

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Confirm

from src.backup.exporter import DataExporter
from src.backup.importer import DataImporter, ConflictStrategy
from src.store.factory import create_store
from src.config import get_config

logger = logging.getLogger(__name__)
console = Console()


async def backup_create(
    destination: Optional[str] = None,
    format: str = "archive",
    project: Optional[str] = None,
) -> int:
    """
    Create a backup of memories.

    Args:
        destination: Backup destination directory (default: ~/.claude-rag/backups/)
        format: Backup format (json or archive)
        project: Only backup this project

    Returns:
        Exit code
    """
    try:
        # Determine backup destination
        if destination:
            backup_dir = Path(destination).expanduser()
        else:
            config = get_config()
            backup_dir = config.data_dir / "backups"

        backup_dir.mkdir(parents=True, exist_ok=True)

        # Generate backup filename
        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        if format == "archive":
            filename = f"backup_{timestamp}.tar.gz"
        else:
            filename = f"backup_{timestamp}.json"

        backup_path = backup_dir / filename

        console.print(f"\n[bold blue]Creating Backup[/bold blue]\n")
        console.print(f"[cyan]Destination:[/cyan] {backup_path}\n")

        # Initialize store and create backup
        config = get_config()
        store = create_store(config)
        await store.initialize()

        exporter = DataExporter(store)

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Creating backup...", total=None)

            if format == "archive":
                stats = await exporter.create_portable_archive(
                    output_path=backup_path,
                    project_name=project,
                    include_embeddings=True,
                )
            else:
                stats = await exporter.export_to_json(
                    output_path=backup_path,
                    project_name=project,
                )

            progress.update(task, completed=True)

        # Display results
        results_table = Table(show_header=False, box=None)
        results_table.add_row("[green]✓[/green] Backup created successfully")
        results_table.add_row("")
        results_table.add_row("[cyan]Backup File:[/cyan]", str(backup_path))
        results_table.add_row("[cyan]Memories:[/cyan]", str(stats["memory_count"]))
        results_table.add_row("[cyan]Size:[/cyan]", f"{stats['file_size_bytes']:,} bytes")

        console.print(Panel(results_table, title="Backup Created", border_style="green"))
        console.print()

        await store.close()
        return 0

    except Exception as e:
        console.print(f"\n[red]Error:[/red] Backup creation failed: {e}")
        logger.error(f"Backup create failed: {e}", exc_info=True)
        return 1


async def backup_list(destination: Optional[str] = None) -> int:
    """
    List available backups.

    Args:
        destination: Backup destination directory

    Returns:
        Exit code
    """
    try:
        # Determine backup directory
        if destination:
            backup_dir = Path(destination).expanduser()
        else:
            config = get_config()
            backup_dir = config.data_dir / "backups"

        if not backup_dir.exists():
            console.print(f"\n[yellow]No backups found at {backup_dir}[/yellow]\n")
            return 0

        # Find backup files
        backups = []
        for pattern in ["backup_*.tar.gz", "backup_*.json"]:
            backups.extend(backup_dir.glob(pattern))

        backups.sort(key=lambda p: p.stat().st_mtime, reverse=True)

        if not backups:
            console.print(f"\n[yellow]No backups found at {backup_dir}[/yellow]\n")
            return 0

        # Display backups
        console.print(f"\n[bold blue]Available Backups[/bold blue]\n")

        table = Table(show_header=True)
        table.add_column("Filename", style="cyan")
        table.add_column("Created", style="yellow")
        table.add_column("Size", justify="right")
        table.add_column("Format")

        for backup_file in backups:
            stat = backup_file.stat()
            created = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            size = f"{stat.st_size:,} bytes"
            format_type = "Archive" if backup_file.suffix == ".gz" else "JSON"

            table.add_row(backup_file.name, created, size, format_type)

        console.print(table)
        console.print(f"\n[cyan]Backup Directory:[/cyan] {backup_dir}\n")

        return 0

    except Exception as e:
        console.print(f"\n[red]Error:[/red] Failed to list backups: {e}")
        logger.error(f"Backup list failed: {e}", exc_info=True)
        return 1


async def backup_restore(
    backup_file: str,
    strategy: str = "keep_newer",
    dry_run: bool = False,
    yes: bool = False,
) -> int:
    """
    Restore from a backup file.

    Args:
        backup_file: Path to backup file
        strategy: Conflict resolution strategy
        dry_run: If True, analyze but don't actually restore
        yes: Skip confirmation prompts

    Returns:
        Exit code
    """
    try:
        console.print("\n[bold blue]Restore from Backup[/bold blue]\n")

        # Validate backup file
        backup_path = Path(backup_file).expanduser()
        if not backup_path.exists():
            console.print(f"[red]Error:[/red] Backup file not found: {backup_file}")
            return 1

        # Display restore configuration
        config_table = Table(show_header=False, box=None)
        config_table.add_row("[cyan]Backup File:[/cyan]", str(backup_path))
        config_table.add_row("[cyan]Conflict Strategy:[/cyan]", strategy)
        config_table.add_row("[cyan]Mode:[/cyan]", "[yellow]DRY RUN[/yellow]" if dry_run else "[red]LIVE RESTORE[/red]")

        console.print(Panel(config_table, title="Restore Configuration", border_style="blue"))
        console.print()

        # Confirmation prompt
        if not dry_run and not yes:
            console.print("[red]⚠ WARNING: This will restore data from the backup.[/red]")
            console.print("[yellow]Depending on your conflict strategy, this may overwrite existing memories.[/yellow]\n")

            if not Confirm.ask("[yellow]Continue with restore?[/yellow]"):
                console.print("[yellow]Restore cancelled.[/yellow]")
                return 0

        # Initialize store and restore
        config = get_config()
        store = create_store(config)
        await store.initialize()

        importer = DataImporter(store)
        conflict_strategy = ConflictStrategy(strategy)

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task(
                "Analyzing restore..." if dry_run else "Restoring backup...",
                total=None
            )

            is_archive = backup_path.suffix == ".gz" or backup_path.suffixes == [".tar", ".gz"]

            if is_archive:
                stats = await importer.import_from_archive(
                    archive_path=backup_path,
                    conflict_strategy=conflict_strategy,
                    dry_run=dry_run,
                )
            else:
                stats = await importer.import_from_json(
                    input_path=backup_path,
                    conflict_strategy=conflict_strategy,
                    dry_run=dry_run,
                )

            progress.update(task, completed=True)

        # Display results
        results_table = Table(show_header=False, box=None)

        if dry_run:
            results_table.add_row("[yellow]⚠[/yellow] Dry run completed (no changes made)")
        else:
            results_table.add_row("[green]✓[/green] Restore completed successfully")

        results_table.add_row("")
        results_table.add_row("[cyan]Total Memories:[/cyan]", str(stats["total_memories"]))
        results_table.add_row("[cyan]Restored:[/cyan]", f"[green]{stats['imported']}[/green]")
        results_table.add_row("[cyan]Skipped:[/cyan]", f"[yellow]{stats['skipped']}[/yellow]")
        results_table.add_row("[cyan]Conflicts:[/cyan]", f"[magenta]{stats['conflicts']}[/magenta]")

        console.print(Panel(results_table, title="Restore Results", border_style="green"))
        console.print()

        await store.close()
        return 0

    except Exception as e:
        console.print(f"\n[red]Error:[/red] Restore failed: {e}")
        logger.error(f"Backup restore failed: {e}", exc_info=True)
        return 1


async def backup_cleanup(
    keep: int = 7,
    destination: Optional[str] = None,
    yes: bool = False,
) -> int:
    """
    Clean up old backups, keeping only the N most recent.

    Args:
        keep: Number of backups to keep
        destination: Backup destination directory
        yes: Skip confirmation prompts

    Returns:
        Exit code
    """
    try:
        # Determine backup directory
        if destination:
            backup_dir = Path(destination).expanduser()
        else:
            config = get_config()
            backup_dir = config.data_dir / "backups"

        if not backup_dir.exists():
            console.print(f"\n[yellow]No backups found at {backup_dir}[/yellow]\n")
            return 0

        # Find backup files
        backups = []
        for pattern in ["backup_*.tar.gz", "backup_*.json"]:
            backups.extend(backup_dir.glob(pattern))

        backups.sort(key=lambda p: p.stat().st_mtime, reverse=True)

        if len(backups) <= keep:
            console.print(f"\n[green]No cleanup needed. Found {len(backups)} backups (keeping {keep}).[/green]\n")
            return 0

        # Determine which backups to delete
        to_delete = backups[keep:]

        console.print(f"\n[bold blue]Backup Cleanup[/bold blue]\n")
        console.print(f"[cyan]Found {len(backups)} backups, keeping {keep} most recent.[/cyan]")
        console.print(f"[yellow]Will delete {len(to_delete)} old backups:[/yellow]\n")

        for backup in to_delete:
            console.print(f"  • {backup.name}")

        console.print()

        # Confirmation
        if not yes:
            if not Confirm.ask("[yellow]Proceed with deletion?[/yellow]"):
                console.print("[yellow]Cleanup cancelled.[/yellow]")
                return 0

        # Delete old backups
        deleted_count = 0
        for backup in to_delete:
            try:
                backup.unlink()
                deleted_count += 1
            except Exception as e:
                logger.error(f"Failed to delete {backup}: {e}")
                console.print(f"[red]Failed to delete {backup.name}: {e}[/red]")

        console.print(f"\n[green]✓ Cleanup complete. Deleted {deleted_count} old backups.[/green]\n")

        return 0

    except Exception as e:
        console.print(f"\n[red]Error:[/red] Cleanup failed: {e}")
        logger.error(f"Backup cleanup failed: {e}", exc_info=True)
        return 1


def main():
    """Main entry point for backup command."""
    import argparse

    parser = argparse.ArgumentParser(description="Backup management")
    subparsers = parser.add_subparsers(dest="command", help="Backup commands")

    # create command
    create_parser = subparsers.add_parser("create", help="Create a new backup")
    create_parser.add_argument("--destination", help="Backup destination directory")
    create_parser.add_argument(
        "--format",
        choices=["json", "archive"],
        default="archive",
        help="Backup format (default: archive)"
    )
    create_parser.add_argument("--project", help="Only backup this project")

    # list command
    list_parser = subparsers.add_parser("list", help="List available backups")
    list_parser.add_argument("--destination", help="Backup destination directory")

    # restore command
    restore_parser = subparsers.add_parser("restore", help="Restore from backup")
    restore_parser.add_argument("backup_file", help="Path to backup file")
    restore_parser.add_argument(
        "--strategy",
        choices=["keep_newer", "keep_older", "keep_both", "skip", "merge_metadata"],
        default="keep_newer",
        help="Conflict resolution strategy"
    )
    restore_parser.add_argument("--dry-run", action="store_true", help="Analyze without making changes")
    restore_parser.add_argument("-y", "--yes", action="store_true", help="Skip confirmation prompts")

    # cleanup command
    cleanup_parser = subparsers.add_parser("cleanup", help="Clean up old backups")
    cleanup_parser.add_argument(
        "--keep",
        type=int,
        default=7,
        help="Number of backups to keep (default: 7)"
    )
    cleanup_parser.add_argument("--destination", help="Backup destination directory")
    cleanup_parser.add_argument("-y", "--yes", action="store_true", help="Skip confirmation prompts")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Run appropriate command
    if args.command == "create":
        exit_code = asyncio.run(backup_create(
            destination=args.destination,
            format=args.format,
            project=args.project,
        ))
    elif args.command == "list":
        exit_code = asyncio.run(backup_list(
            destination=args.destination,
        ))
    elif args.command == "restore":
        exit_code = asyncio.run(backup_restore(
            backup_file=args.backup_file,
            strategy=args.strategy,
            dry_run=args.dry_run,
            yes=args.yes,
        ))
    elif args.command == "cleanup":
        exit_code = asyncio.run(backup_cleanup(
            keep=args.keep,
            destination=args.destination,
            yes=args.yes,
        ))
    else:
        parser.print_help()
        exit_code = 1

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
