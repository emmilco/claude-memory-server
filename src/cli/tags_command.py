"""CLI command for tag management."""

import click
from rich.console import Console
from rich.table import Table
from typing import Optional

from src.config import get_config
from src.tagging.tag_manager import TagManager
from src.tagging.models import TagCreate

console = Console()


@click.group(name="tags")
def tags_cli():
    """Manage memory tags."""
    pass


@tags_cli.command(name="list")
@click.option("--prefix", default="", help="Filter by tag path prefix")
@click.option("--parent-id", default=None, help="Filter by parent tag ID")
def list_tags(prefix: str, parent_id: Optional[str]):
    """List all tags."""
    config = get_config()
    manager = TagManager(str(config.sqlite_path_expanded))

    tags = manager.list_tags(parent_id=parent_id, prefix=prefix)

    if not tags:
        console.print("[yellow]No tags found[/yellow]")
        return

    table = Table(title="Tags")
    table.add_column("Name", style="cyan")
    table.add_column("Full Path", style="green")
    table.add_column("Level", style="magenta")
    table.add_column("ID", style="dim")

    for tag in tags:
        table.add_row(tag.name, tag.full_path, str(tag.level), tag.id)

    console.print(table)
    console.print(f"\n[green]Total: {len(tags)} tags[/green]")


@tags_cli.command(name="create")
@click.argument("name")
@click.option("--parent", default=None, help="Parent tag ID or path")
def create_tag(name: str, parent: Optional[str]):
    """Create a new tag."""
    config = get_config()
    manager = TagManager(str(config.sqlite_path_expanded))

    # If parent is a path, look it up
    parent_id = None
    if parent:
        parent_tag = manager.get_tag_by_path(parent)
        if parent_tag:
            parent_id = parent_tag.id
        else:
            # Try as ID
            parent_tag = manager.get_tag(parent)
            if parent_tag:
                parent_id = parent_tag.id
            else:
                console.print(f"[red]Parent tag not found: {parent}[/red]")
                return

    try:
        tag_create = TagCreate(name=name, parent_id=parent_id)
        tag = manager.create_tag(tag_create)
        console.print(f"[green]✓ Created tag: {tag.full_path}[/green]")
        console.print(f"  ID: {tag.id}")
        console.print(f"  Level: {tag.level}")
    except Exception as e:
        console.print(f"[red]Failed to create tag: {e}[/red]")


@tags_cli.command(name="merge")
@click.argument("source")
@click.argument("target")
def merge_tags(source: str, target: str):
    """Merge source tag into target tag."""
    config = get_config()
    manager = TagManager(str(config.sqlite_path_expanded))

    # Look up tags by path or ID
    source_tag = manager.get_tag_by_path(source) or manager.get_tag(source)
    target_tag = manager.get_tag_by_path(target) or manager.get_tag(target)

    if not source_tag:
        console.print(f"[red]Source tag not found: {source}[/red]")
        return
    if not target_tag:
        console.print(f"[red]Target tag not found: {target}[/red]")
        return

    console.print(
        f"Merging [yellow]{source_tag.full_path}[/yellow] into [green]{target_tag.full_path}[/green]"
    )

    if click.confirm("Are you sure?"):
        try:
            manager.merge_tags(source_tag.id, target_tag.id)
            console.print("[green]✓ Tags merged successfully[/green]")
        except Exception as e:
            console.print(f"[red]Failed to merge tags: {e}[/red]")


@tags_cli.command(name="delete")
@click.argument("tag")
@click.option("--cascade", is_flag=True, help="Delete all descendants")
def delete_tag(tag: str, cascade: bool):
    """Delete a tag."""
    config = get_config()
    manager = TagManager(str(config.sqlite_path_expanded))

    # Look up tag by path or ID
    tag_obj = manager.get_tag_by_path(tag) or manager.get_tag(tag)

    if not tag_obj:
        console.print(f"[red]Tag not found: {tag}[/red]")
        return

    descendants = manager.get_descendants(tag_obj.id)
    if descendants and not cascade:
        console.print(f"[yellow]Tag has {len(descendants)} descendants.[/yellow]")
        console.print("Use --cascade to delete all descendants.")
        return

    console.print(f"Deleting [yellow]{tag_obj.full_path}[/yellow]")
    if descendants:
        console.print(
            f"  [red]This will also delete {len(descendants)} descendants[/red]"
        )

    if click.confirm("Are you sure?"):
        try:
            manager.delete_tag(tag_obj.id, cascade=cascade)
            console.print("[green]✓ Tag deleted[/green]")
        except Exception as e:
            console.print(f"[red]Failed to delete tag: {e}[/red]")


if __name__ == "__main__":
    tags_cli()
