"""CLI command for memory consolidation (FEAT-035 Phase 5)."""

import asyncio
import logging
from typing import Optional

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

from src.config import get_config
from src.memory.duplicate_detector import DuplicateDetector
from src.memory.consolidation_engine import ConsolidationEngine, MergeStrategy
from src.embeddings.generator import EmbeddingGenerator
from src.core.models import MemoryCategory

logger = logging.getLogger(__name__)
console = Console()


async def consolidate_command(
    auto: bool = False,
    interactive: bool = False,
    dry_run: bool = True,
    category: Optional[str] = None
):
    """
    Run memory consolidation to find and merge duplicates.

    Args:
        auto: Automatically merge high-confidence duplicates
        interactive: Review each merge suggestion interactively
        dry_run: Show what would be done without actually doing it
        category: Filter by category (preference, fact, event, workflow, context)
    """
    try:
        config = get_config()

        # Initialize components
        if config.storage_backend == "qdrant":
            from src.store.qdrant_store import QdrantMemoryStore
            store = QdrantMemoryStore(config)
        else:
            from src.store.sqlite_store import SQLiteMemoryStore
            store = SQLiteMemoryStore(config)

        await store.initialize()

        embedding_gen = EmbeddingGenerator()
        detector = DuplicateDetector(store, embedding_gen)
        engine = ConsolidationEngine(store)

        # Parse category
        memory_category = None
        if category:
            try:
                memory_category = MemoryCategory(category.lower())
            except ValueError:
                console.print(f"[red]Invalid category: {category}[/red]")
                console.print("Valid categories: preference, fact, event, workflow, context")
                return

        # Display header
        console.print("\n[bold cyan]Memory Consolidation Tool[/bold cyan]")
        console.print(f"Mode: {'AUTO-MERGE' if auto else 'INTERACTIVE' if interactive else 'DRY-RUN'}")
        if category:
            console.print(f"Category filter: {memory_category.value}")
        console.print()

        # Get consolidation suggestions
        with console.status("[bold green]Analyzing memories for duplicates..."):
            suggestions = await engine.get_consolidation_suggestions(
                category=memory_category,
                limit=50
            )

        if not suggestions:
            console.print("[green]✓ No duplicates found! Your memory database is clean.[/green]")
            return

        console.print(f"[yellow]Found {len(suggestions)} consolidation suggestions[/yellow]\n")

        # Process suggestions
        merged_count = 0
        skipped_count = 0

        for idx, suggestion in enumerate(suggestions, 1):
            suggestion_type = suggestion["type"]
            canonical = suggestion["canonical"]
            duplicate_ids = suggestion["duplicates"]
            confidence = suggestion["confidence"]
            action = suggestion["action"]

            # Fetch duplicate memories
            duplicates = []
            for dup_id in duplicate_ids:
                dup = await store.get_by_id(dup_id)
                if dup:
                    duplicates.append(dup)

            if not duplicates:
                continue

            # Display suggestion
            table = Table(title=f"Suggestion {idx}/{len(suggestions)}", box=box.ROUNDED)
            table.add_column("Type", style="cyan")
            table.add_column("Canonical Memory", style="green")
            table.add_column("Duplicates", style="yellow")
            table.add_column("Confidence", style="magenta")

            canonical_preview = canonical.content[:100] + "..." if len(canonical.content) > 100 else canonical.content
            duplicates_preview = f"{len(duplicates)} duplicate(s)"

            table.add_row(
                suggestion_type,
                canonical_preview,
                duplicates_preview,
                confidence
            )

            console.print(table)

            # Show duplicate details
            console.print("[dim]Duplicates:[/dim]")
            for dup in duplicates:
                dup_preview = dup.content[:80] + "..." if len(dup.content) > 80 else dup.content
                console.print(f"  • {dup_preview}")

            console.print()

            # Decide action
            should_merge = False

            if auto and confidence == "high":
                should_merge = True
                console.print("[green]✓ Auto-merging (high confidence)[/green]")
            elif interactive:
                response = console.input(
                    "[bold]Merge these duplicates? (y/n/skip all): [/bold]"
                ).strip().lower()

                if response == "y":
                    should_merge = True
                elif response == "skip all":
                    console.print("[yellow]Skipping remaining suggestions[/yellow]")
                    break
                else:
                    console.print("[dim]Skipped[/dim]")
                    skipped_count += 1
            elif dry_run:
                console.print(f"[dim]Would merge (dry-run mode)[/dim]")
                merged_count += 1  # Count for summary

            # Perform merge if requested
            if should_merge and not dry_run:
                try:
                    strategy = MergeStrategy.KEEP_MOST_RECENT
                    result = await engine.merge_memories(
                        canonical_id=canonical.id,
                        duplicate_ids=duplicate_ids,
                        strategy=strategy,
                        dry_run=False
                    )

                    if result:
                        console.print("[green]✓ Merged successfully[/green]")
                        merged_count += 1
                    else:
                        console.print("[red]✗ Merge failed[/red]")
                except Exception as e:
                    console.print(f"[red]✗ Error during merge: {e}[/red]")

            console.print()

        # Summary
        summary = Panel(
            f"[bold]Consolidation Summary[/bold]\n\n"
            f"Suggestions found: {len(suggestions)}\n"
            f"{'Would merge' if dry_run else 'Merged'}: {merged_count}\n"
            f"Skipped: {skipped_count}\n\n"
            f"{'[dim]Run without --dry-run to apply changes[/dim]' if dry_run else '[green]Changes applied successfully[/green]'}",
            border_style="cyan",
            box=box.ROUNDED
        )
        console.print(summary)

    except Exception as e:
        console.print(f"[red]Error during consolidation: {e}[/red]")
        logger.error(f"Consolidation error: {e}", exc_info=True)


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Memory consolidation tool")
    parser.add_argument("--auto", action="store_true", help="Auto-merge high-confidence duplicates")
    parser.add_argument("--interactive", action="store_true", help="Review each merge interactively")
    parser.add_argument("--dry-run", action="store_true", default=True, help="Show what would be done (default)")
    parser.add_argument("--execute", action="store_true", help="Actually perform merges (disables dry-run)")
    parser.add_argument("--category", type=str, help="Filter by category (preference, fact, event, workflow, context)")

    args = parser.parse_args()

    # If --execute is specified, disable dry-run
    if args.execute:
        args.dry_run = False

    # Run the consolidation
    asyncio.run(
        consolidate_command(
            auto=args.auto,
            interactive=args.interactive,
            dry_run=args.dry_run,
            category=args.category
        )
    )


if __name__ == "__main__":
    main()
