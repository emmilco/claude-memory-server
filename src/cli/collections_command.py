"""CLI command for collection management."""

import click
from rich.console import Console
from rich.table import Table
from typing import Optional
import json

from src.config import get_config
from src.tagging.collection_manager import CollectionManager
from src.tagging.models import CollectionCreate

console = Console()


@click.group(name="collections")
def collections_cli():
    """Manage memory collections."""
    pass


@collections_cli.command(name="list")
def list_collections():
    """List all collections."""
    config = get_config()
    manager = CollectionManager(str(config.sqlite_path_expanded))

    collections = manager.list_collections()

    if not collections:
        console.print("[yellow]No collections found[/yellow]")
        return

    table = Table(title="Collections")
    table.add_column("Name", style="cyan")
    table.add_column("Description", style="white")
    table.add_column("Auto", style="magenta")
    table.add_column("ID", style="dim")

    for collection in collections:
        auto_marker = "✓" if collection.auto_generated else ""
        desc = collection.description or ""
        table.add_row(collection.name, desc[:50], auto_marker, collection.id)

    console.print(table)
    console.print(f"\n[green]Total: {len(collections)} collections[/green]")


@collections_cli.command(name="create")
@click.argument("name")
@click.option("--description", default=None, help="Collection description")
@click.option("--tags", default=None, help="Comma-separated tags for auto-filter")
def create_collection(name: str, description: Optional[str], tags: Optional[str]):
    """Create a new collection."""
    config = get_config()
    manager = CollectionManager(str(config.sqlite_path_expanded))

    tag_filter = None
    if tags:
        tag_list = [t.strip() for t in tags.split(",")]
        tag_filter = {"tags": tag_list, "op": "AND"}

    try:
        collection_create = CollectionCreate(
            name=name, description=description, tag_filter=tag_filter
        )
        collection = manager.create_collection(collection_create)
        console.print(f"[green]✓ Created collection: {collection.name}[/green]")
        console.print(f"  ID: {collection.id}")
        if tag_filter:
            console.print(f"  Tag filter: {json.dumps(tag_filter, indent=2)}")
    except Exception as e:
        console.print(f"[red]Failed to create collection: {e}[/red]")


@collections_cli.command(name="show")
@click.argument("name")
def show_collection(name: str):
    """Show collection details and memories."""
    config = get_config()
    manager = CollectionManager(str(config.sqlite_path_expanded))

    collection = manager.get_collection_by_name(name)
    if not collection:
        console.print(f"[red]Collection not found: {name}[/red]")
        return

    console.print(f"\n[bold cyan]{collection.name}[/bold cyan]")
    console.print(f"ID: {collection.id}")
    console.print(f"Description: {collection.description or 'N/A'}")
    console.print(f"Auto-generated: {'Yes' if collection.auto_generated else 'No'}")

    if collection.tag_filter:
        console.print(f"Tag filter: {json.dumps(collection.tag_filter, indent=2)}")

    memory_ids = manager.get_collection_memories(collection.id)
    console.print(f"\n[green]Memories: {len(memory_ids)}[/green]")


@collections_cli.command(name="delete")
@click.argument("name")
def delete_collection(name: str):
    """Delete a collection."""
    config = get_config()
    manager = CollectionManager(str(config.sqlite_path_expanded))

    collection = manager.get_collection_by_name(name)
    if not collection:
        console.print(f"[red]Collection not found: {name}[/red]")
        return

    console.print(f"Deleting collection [yellow]{collection.name}[/yellow]")

    if click.confirm("Are you sure?"):
        try:
            manager.delete_collection(collection.id)
            console.print(f"[green]✓ Collection deleted[/green]")
        except Exception as e:
            console.print(f"[red]Failed to delete collection: {e}[/red]")


@collections_cli.command(name="auto-generate")
def auto_generate_collections():
    """Auto-generate collections from common tag patterns."""
    config = get_config()
    manager = CollectionManager(str(config.sqlite_path_expanded))

    console.print("Auto-generating collections...")

    try:
        collections = manager.auto_generate_collections()

        if not collections:
            console.print("[yellow]No new collections generated (all exist)[/yellow]")
            return

        console.print(f"[green]✓ Generated {len(collections)} collections:[/green]")
        for collection in collections:
            console.print(f"  • {collection.name}")
    except Exception as e:
        console.print(f"[red]Failed to auto-generate collections: {e}[/red]")


if __name__ == "__main__":
    collections_cli()
