"""CLI command for auto-tagging memories."""

import asyncio
import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from src.config import get_config
from src.store import create_memory_store
from src.tagging.auto_tagger import AutoTagger
from src.tagging.tag_manager import TagManager

console = Console()


@click.command(name="auto-tag")
@click.option(
    "--dry-run", is_flag=True, help="Show what would be tagged without applying"
)
@click.option("--memory-ids", default=None, help="Comma-separated memory IDs to tag")
@click.option(
    "--min-confidence", default=0.6, type=float, help="Minimum tag confidence (0-1)"
)
def auto_tag_command(dry_run: bool, memory_ids: str, min_confidence: float):
    """Auto-tag memories based on content analysis."""
    asyncio.run(_auto_tag(dry_run, memory_ids, min_confidence))


async def _auto_tag(dry_run: bool, memory_ids_str: str, min_confidence: float):
    """Async implementation of auto-tagging."""
    config = get_config()

    # Initialize components
    store = create_memory_store(config=config)
    await store.initialize()

    tagger = AutoTagger(min_confidence=min_confidence)
    tag_manager = TagManager(str(config.sqlite_path_expanded))

    # Get memories to tag
    if memory_ids_str:
        memory_ids = [mid.strip() for mid in memory_ids_str.split(",")]
        memories = []
        for mid in memory_ids:
            memory = await store.get_by_id(mid)
            if memory:
                memories.append(memory)
    else:
        # Get all memories
        from src.core.models import SearchFilters

        results = await store.retrieve([], SearchFilters(), limit=1000)
        memories = [mem for mem, _ in results]

    if not memories:
        console.print("[yellow]No memories found to tag[/yellow]")
        return

    console.print(f"[cyan]Auto-tagging {len(memories)} memories...[/cyan]")
    console.print(f"Min confidence: {min_confidence}")

    tagged_count = 0
    total_tags = 0

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Processing memories...", total=len(memories))

        for memory in memories:
            progress.update(task, description=f"Processing {memory.id[:8]}...")

            # Extract tags
            tag_tuples = tagger.extract_tags(memory.content, max_tags=10)

            if not tag_tuples:
                progress.advance(task)
                continue

            # Infer hierarchical tags
            flat_tags = [tag for tag, _ in tag_tuples]
            hierarchical_tags = tagger.infer_hierarchical_tags(flat_tags)

            if dry_run:
                console.print(f"\n[bold]{memory.id}[/bold] would be tagged with:")
                for tag, conf in tag_tuples:
                    console.print(f"  • {tag} ({conf:.2f})")
                console.print(f"  Hierarchical: {', '.join(hierarchical_tags)}")
            else:
                # Apply tags
                for tag_name, confidence in tag_tuples:
                    # Get or create tag
                    tag = tag_manager.get_or_create_tag(tag_name)
                    # Associate with memory
                    tag_manager.tag_memory(
                        memory.id, tag.id, confidence, auto_generated=True
                    )
                    total_tags += 1

                # Apply hierarchical tags
                for h_tag in hierarchical_tags:
                    if h_tag not in flat_tags:  # Don't duplicate
                        tag = tag_manager.get_or_create_tag(h_tag)
                        tag_manager.tag_memory(
                            memory.id, tag.id, 0.8, auto_generated=True
                        )
                        total_tags += 1

                tagged_count += 1

            progress.advance(task)

    if dry_run:
        console.print("\n[yellow]Dry run complete - no tags applied[/yellow]")
    else:
        console.print(
            f"\n[green]✓ Tagged {tagged_count} memories with {total_tags} total tags[/green]"
        )

    await store.close()


if __name__ == "__main__":
    auto_tag_command()
