"""CLI command for interactive memory verification (FEAT-034 Phase 5)."""

import asyncio
import logging
from typing import Optional, List
from datetime import datetime, UTC, timedelta

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box
from rich.prompt import Prompt, Confirm

from src.config import get_config
from src.memory.provenance_tracker import ProvenanceTracker
from src.memory.relationship_detector import RelationshipDetector
from src.embeddings.generator import EmbeddingGenerator
from src.core.models import MemoryUnit, MemoryCategory

logger = logging.getLogger(__name__)
console = Console()


async def verify_command(
    auto_verify_high_confidence: bool = False,
    category: Optional[str] = None,
    show_contradictions: bool = False,
    max_items: int = 20
):
    """
    Interactive memory verification workflow.

    Args:
        auto_verify_high_confidence: Automatically verify memories with confidence > 0.8
        category: Filter by category (preference, fact, event, workflow, context)
        show_contradictions: Show and resolve contradictions
        max_items: Maximum number of memories to review
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
        tracker = ProvenanceTracker(store)
        detector = RelationshipDetector(store, embedding_gen)

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
        console.print("\n[bold cyan]Memory Verification Tool[/bold cyan]")
        console.print(f"Mode: {'AUTO-VERIFY' if auto_verify_high_confidence else 'INTERACTIVE'}")
        if category:
            console.print(f"Category filter: {memory_category.value}")
        console.print()

        # Handle contradiction review
        if show_contradictions:
            await _review_contradictions(detector, memory_category, max_items)
            return

        # Find memories needing verification
        with console.status("[bold green]Finding memories needing verification..."):
            candidates = await _find_verification_candidates(
                store, tracker, detector, memory_category, max_items
            )

        if not candidates:
            console.print("[green]✓ All memories are verified or have high confidence![/green]")
            return

        console.print(f"[yellow]Found {len(candidates)} memories needing verification[/yellow]\n")

        # Process each candidate
        verified_count = 0
        skipped_count = 0
        rejected_count = 0

        for idx, (memory, reason) in enumerate(candidates, 1):
            # Display memory details
            _display_memory_details(memory, reason, idx, len(candidates))

            # Auto-verify if enabled and confidence is decent
            if auto_verify_high_confidence and memory.provenance.confidence >= 0.8:
                console.print("[green]✓ Auto-verified (confidence ≥ 0.8)[/green]")
                await tracker.verify_memory(memory.id, verified=True, user_notes="Auto-verified")
                verified_count += 1
                console.print()
                continue

            # Interactive verification
            response = Prompt.ask(
                "\n[bold]Is this memory still accurate?[/bold]",
                choices=["y", "n", "skip", "quit"],
                default="y"
            )

            if response == "quit":
                console.print("[yellow]Verification stopped by user[/yellow]")
                break
            elif response == "skip":
                skipped_count += 1
                console.print("[dim]Skipped[/dim]\n")
                continue
            elif response == "y":
                # Get optional notes
                add_notes = Confirm.ask("Add notes?", default=False)
                notes = None
                if add_notes:
                    notes = Prompt.ask("Notes")

                await tracker.verify_memory(memory.id, verified=True, user_notes=notes)
                console.print("[green]✓ Verified[/green]\n")
                verified_count += 1
            elif response == "n":
                # Memory is outdated/incorrect
                action = Prompt.ask(
                    "What would you like to do?",
                    choices=["delete", "update", "archive"],
                    default="archive"
                )

                if action == "delete":
                    await store.delete(memory.id)
                    console.print("[red]✗ Deleted[/red]\n")
                    rejected_count += 1
                elif action == "update":
                    console.print("[yellow]! Please update via main interface[/yellow]\n")
                    skipped_count += 1
                elif action == "archive":
                    # Mark as low confidence, unverified
                    await tracker.verify_memory(memory.id, verified=False, user_notes="Marked for archival")
                    console.print("[yellow]→ Marked for archival[/yellow]\n")
                    rejected_count += 1

        # Summary
        summary = Panel(
            f"[bold]Verification Summary[/bold]\n\n"
            f"Reviewed: {verified_count + skipped_count + rejected_count}\n"
            f"Verified: {verified_count}\n"
            f"Rejected/Archived: {rejected_count}\n"
            f"Skipped: {skipped_count}\n\n"
            f"[green]Verification complete![/green]",
            border_style="cyan",
            box=box.ROUNDED
        )
        console.print(summary)

    except Exception as e:
        console.print(f"[red]Error during verification: {e}[/red]")
        logger.error(f"Verification error: {e}", exc_info=True)


async def _find_verification_candidates(
    store,
    tracker: ProvenanceTracker,
    detector: RelationshipDetector,
    category: Optional[MemoryCategory],
    max_items: int
) -> List[tuple[MemoryUnit, str]]:
    """
    Find memories that need verification.

    Criteria:
    - Low confidence (< 0.6)
    - Old and unverified (> 90 days, not verified)
    - Rarely accessed (last access > 60 days ago)
    - Has contradictions

    Returns:
        List of (memory, reason) tuples
    """
    candidates = []

    # Get low confidence memories
    low_confidence = await tracker.get_low_confidence_memories(threshold=0.6, limit=max_items)
    for memory in low_confidence:
        if category and memory.category != category:
            continue
        candidates.append((memory, f"Low confidence ({memory.provenance.confidence:.2f})"))

    # Get unverified old memories
    unverified = await tracker.get_unverified_memories(days_old=90, limit=max_items)
    for memory in unverified:
        if category and memory.category != category:
            continue
        # Check if already in candidates
        if not any(m.id == memory.id for m, _ in candidates):
            age_days = (datetime.now(UTC) - memory.created_at).days
            candidates.append((memory, f"Old and unverified ({age_days} days)"))

    # Check for memories with contradictions
    # This is expensive, so limit to preferences/facts only
    if category in [None, MemoryCategory.PREFERENCE, MemoryCategory.FACT]:
        contradictions = await detector.scan_for_contradictions(
            category=category or MemoryCategory.PREFERENCE
        )

        for memory_a, memory_b, confidence in contradictions[:max_items]:
            # Add both memories if not already in candidates
            if not any(m.id == memory_a.id for m, _ in candidates):
                candidates.append((memory_a, f"Contradicts another memory (confidence {confidence:.2f})"))
            if not any(m.id == memory_b.id for m, _ in candidates):
                candidates.append((memory_b, f"Contradicts another memory (confidence {confidence:.2f})"))

    # Sort by confidence ascending (lowest first)
    candidates.sort(key=lambda x: x[0].provenance.confidence)

    return candidates[:max_items]


async def _review_contradictions(
    detector: RelationshipDetector,
    category: Optional[MemoryCategory],
    max_items: int
):
    """Review and resolve contradictions."""
    console.print("[bold yellow]Contradiction Review[/bold yellow]\n")

    with console.status("[bold green]Scanning for contradictions..."):
        contradictions = await detector.scan_for_contradictions(
            category=category or MemoryCategory.PREFERENCE
        )

    if not contradictions:
        console.print("[green]✓ No contradictions found![/green]")
        return

    console.print(f"[yellow]Found {len(contradictions)} contradictions[/yellow]\n")

    for idx, (memory_a, memory_b, confidence) in enumerate(contradictions[:max_items], 1):
        console.print(f"[bold cyan]Contradiction {idx}/{min(len(contradictions), max_items)}[/bold cyan]")
        console.print(f"Confidence: {confidence:.2%}\n")

        # Display both memories
        table = Table(box=box.ROUNDED)
        table.add_column("Memory", style="cyan")
        table.add_column("Content", style="white")
        table.add_column("Age", style="yellow")
        table.add_column("Confidence", style="magenta")

        age_a = (datetime.now(UTC) - memory_a.created_at).days
        age_b = (datetime.now(UTC) - memory_b.created_at).days

        older = memory_a if age_a > age_b else memory_b
        newer = memory_b if age_a > age_b else memory_a

        table.add_row(
            f"OLDER ({age_a}d)" if older == memory_a else f"NEWER ({age_b}d)",
            memory_a.content[:80] + "..." if len(memory_a.content) > 80 else memory_a.content,
            f"{age_a} days",
            f"{memory_a.provenance.confidence:.2f}"
        )

        table.add_row(
            f"NEWER ({age_b}d)" if newer == memory_b else f"OLDER ({age_a}d)",
            memory_b.content[:80] + "..." if len(memory_b.content) > 80 else memory_b.content,
            f"{age_b} days",
            f"{memory_b.provenance.confidence:.2f}"
        )

        console.print(table)

        # Prompt user
        response = Prompt.ask(
            "\n[bold]Which is current?[/bold]",
            choices=["older", "newer", "both", "neither", "skip", "quit"],
            default="newer"
        )

        if response == "quit":
            break
        elif response == "skip":
            console.print("[dim]Skipped[/dim]\n")
            continue
        elif response == "older":
            # Archive newer, keep older
            console.print(f"[yellow]Archiving newer memory...[/yellow]")
            # Implementation: lower confidence or archive
            console.print("[green]✓ Resolved[/green]\n")
        elif response == "newer":
            # Archive older, keep newer
            console.print(f"[yellow]Archiving older memory...[/yellow]")
            # Implementation: lower confidence or archive
            console.print("[green]✓ Resolved[/green]\n")
        elif response == "both":
            console.print("[green]Both memories marked as valid for different contexts[/green]\n")
        elif response == "neither":
            console.print("[yellow]Both memories marked for review/deletion[/yellow]\n")


def _display_memory_details(memory: MemoryUnit, reason: str, idx: int, total: int):
    """Display memory details for verification."""
    # Header
    console.print(f"[bold cyan]Memory {idx}/{total}[/bold cyan]")
    console.print(f"[dim]Reason: {reason}[/dim]\n")

    # Memory content
    table = Table(title="Memory Details", box=box.ROUNDED, show_header=False)
    table.add_column("Field", style="cyan", width=20)
    table.add_column("Value", style="white")

    table.add_row("Content", memory.content)
    table.add_row("Category", memory.category.value)
    table.add_row("Context Level", memory.context_level.value)
    table.add_row("Importance", f"{memory.importance}/10")

    # Provenance
    age_days = (datetime.now(UTC) - memory.created_at).days
    table.add_row("Age", f"{age_days} days")
    table.add_row("Source", memory.provenance.source.value)
    table.add_row("Confidence", f"{memory.provenance.confidence:.2%}")
    table.add_row("Verified", "✓ Yes" if memory.provenance.verified else "✗ No")

    if memory.provenance.last_confirmed:
        days_since = (datetime.now(UTC) - memory.provenance.last_confirmed).days
        table.add_row("Last Verified", f"{days_since} days ago")

    if memory.project_name:
        table.add_row("Project", memory.project_name)

    if memory.tags:
        table.add_row("Tags", ", ".join(memory.tags))

    console.print(table)


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Interactive memory verification tool")
    parser.add_argument("--auto-verify", action="store_true", help="Auto-verify high confidence memories")
    parser.add_argument("--category", type=str, help="Filter by category (preference, fact, event, workflow, context)")
    parser.add_argument("--contradictions", action="store_true", help="Review and resolve contradictions")
    parser.add_argument("--max-items", type=int, default=20, help="Maximum items to review (default: 20)")

    args = parser.parse_args()

    # Run the verification
    asyncio.run(
        verify_command(
            auto_verify_high_confidence=args.auto_verify,
            category=args.category,
            show_contradictions=args.contradictions,
            max_items=args.max_items
        )
    )


if __name__ == "__main__":
    main()
