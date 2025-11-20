"""CLI command for pruning expired and stale memories."""

import asyncio
import logging
from typing import Optional

from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from src.config import get_config
from src.store import create_memory_store
from src.memory.pruner import MemoryPruner

logger = logging.getLogger(__name__)
console = Console()


async def prune_command(
    dry_run: bool = False,
    ttl_hours: Optional[int] = None,
    verbose: bool = False,
    stale_days: Optional[int] = None,
    yes: bool = False,
) -> int:
    """
    Prune expired and stale memories.

    Args:
        dry_run: If True, don't actually delete, just report
        ttl_hours: Time-to-live for SESSION_STATE in hours
        verbose: Show detailed output
        stale_days: Also prune memories unused for N days
        yes: Skip confirmation prompts

    Returns:
        Exit code (0 for success)
    """
    config = get_config()

    try:
        # Initialize storage
        store = create_memory_store(config)
        await store.initialize()

        # Create pruner
        pruner = MemoryPruner(config, store)

        # Prune expired SESSION_STATE memories
        console.print("\n[bold]Pruning Expired SESSION_STATE Memories[/bold]")
        console.print(f"TTL: {ttl_hours or config.session_state_ttl_hours} hours")
        console.print(f"Mode: {'DRY RUN' if dry_run else 'EXECUTE'}\n")

        # First, do a dry run to see what would be deleted
        preview_result = await pruner.prune_expired(
            dry_run=True,
            ttl_hours=ttl_hours,
            safety_check=True,
        )

        # Show preview
        console.print(f"[yellow]Found {preview_result.memories_deleted} expired memories to delete[/yellow]")

        # If not in dry-run mode, ask for confirmation (unless --yes flag is set)
        if not dry_run and preview_result.memories_deleted > 0 and not yes:
            console.print()
            response = console.input(
                f"[bold yellow]⚠️  About to delete {preview_result.memories_deleted} memories. "
                "This cannot be undone. Continue? (yes/no): [/bold yellow]"
            )
            if response.lower() not in ["yes", "y"]:
                console.print("[yellow]Aborted. No memories were deleted.[/yellow]")
                await store.close()
                return 0
            console.print()

        # Execute actual pruning
        result = await pruner.prune_expired(
            dry_run=dry_run,
            ttl_hours=ttl_hours,
            safety_check=True,
        )

        # Display results
        table = Table(title="Expired Memory Pruning Results")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")

        table.add_row("Memories Scanned", str(result.memories_scanned))
        table.add_row("Memories Deleted", str(result.memories_deleted))
        table.add_row("Errors", str(len(result.errors)))

        console.print(table)

        if result.errors and verbose:
            console.print("\n[bold red]Errors:[/bold red]")
            for error in result.errors:
                console.print(f"  • {error}")

        if verbose and result.deleted_ids:
            console.print(f"\n[dim]Deleted IDs: {', '.join(result.deleted_ids[:10])}")
            if len(result.deleted_ids) > 10:
                console.print(f"[dim]...and {len(result.deleted_ids) - 10} more")

        # Prune stale memories if requested
        if stale_days:
            console.print(f"\n[bold]Pruning Stale Memories[/bold]")
            console.print(f"Unused for: {stale_days} days\n")

            # Preview stale memories
            stale_preview = await pruner.prune_stale(
                days_unused=stale_days,
                dry_run=True,
            )

            console.print(f"[yellow]Found {stale_preview.memories_deleted} stale memories to delete[/yellow]")

            # Confirmation for stale deletion (unless --yes flag is set)
            if not dry_run and stale_preview.memories_deleted > 0 and not yes:
                console.print()
                response = console.input(
                    f"[bold yellow]⚠️  About to delete {stale_preview.memories_deleted} stale memories. "
                    "This cannot be undone. Continue? (yes/no): [/bold yellow]"
                )
                if response.lower() not in ["yes", "y"]:
                    console.print("[yellow]Skipped stale memory deletion.[/yellow]")
                    stale_result = stale_preview
                else:
                    console.print()
                    stale_result = await pruner.prune_stale(
                        days_unused=stale_days,
                        dry_run=dry_run,
                    )
            else:
                stale_result = await pruner.prune_stale(
                    days_unused=stale_days,
                    dry_run=dry_run,
                )

            stale_table = Table(title="Stale Memory Pruning Results")
            stale_table.add_column("Metric", style="cyan")
            stale_table.add_column("Value", style="green")

            stale_table.add_row("Memories Scanned", str(stale_result.memories_scanned))
            stale_table.add_row("Memories Deleted", str(stale_result.memories_deleted))
            stale_table.add_row("Errors", str(len(stale_result.errors)))

            console.print(stale_table)

        # Cleanup orphaned usage tracking
        if not dry_run:
            console.print("\n[bold]Cleaning Up Orphaned Usage Tracking[/bold]")
            orphaned_count = await pruner.cleanup_orphaned_usage_tracking()
            console.print(f"Cleaned up {orphaned_count} orphaned tracking records")

        # Summary
        total_deleted = result.memories_deleted
        if stale_days:
            total_deleted += stale_result.memories_deleted

        if dry_run:
            console.print(
                f"\n[yellow]DRY RUN: Would delete {total_deleted} total memories[/yellow]"
            )
            console.print("[yellow]Run without --dry-run to actually delete[/yellow]")
        else:
            console.print(
                Panel(
                    f"[green]Successfully deleted {total_deleted} memories[/green]",
                    title="Pruning Complete",
                )
            )

        # Close store
        await store.close()

        return 0

    except Exception as e:
        console.print(f"[red]Error during pruning: {e}[/red]")
        logger.error(f"Pruning error: {e}", exc_info=True)
        return 1


def main():
    """Main entry point for prune command."""
    import argparse

    parser = argparse.ArgumentParser(description="Prune expired and stale memories")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Don't actually delete, just show what would be deleted",
    )
    parser.add_argument(
        "--ttl-hours",
        type=int,
        help="Time-to-live for SESSION_STATE in hours (default from config)",
    )
    parser.add_argument(
        "--stale-days",
        type=int,
        help="Also prune memories unused for N days",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Show detailed output",
    )
    parser.add_argument(
        "-y", "--yes",
        action="store_true",
        help="Skip confirmation prompts (use with caution!)",
    )

    args = parser.parse_args()

    exit_code = asyncio.run(
        prune_command(
            dry_run=args.dry_run,
            ttl_hours=args.ttl_hours,
            verbose=args.verbose,
            stale_days=args.stale_days,
            yes=args.yes,
        )
    )

    return exit_code


if __name__ == "__main__":
    exit(main())
