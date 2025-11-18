"""CLI command for project archival operations."""

import asyncio
import sys
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.memory.project_archival import ProjectArchivalManager, ProjectState
from src.memory.archive_compressor import ArchiveCompressor
from src.memory.archive_exporter import ArchiveExporter
from src.memory.archive_importer import ArchiveImporter
from src.config import get_config


console = Console()


def show_status():
    """Show status of all projects."""
    config = get_config()
    archival_file = Path.home() / ".claude-rag" / "project_states.json"
    manager = ProjectArchivalManager(str(archival_file))

    all_projects = manager.get_all_projects()

    if not all_projects:
        console.print("[yellow]No projects found.[/yellow]")
        return

    # Create table
    table = Table(title="Project States", show_header=True, header_style="bold magenta")
    table.add_column("Project", style="cyan")
    table.add_column("State", style="green")
    table.add_column("Last Activity", style="yellow")
    table.add_column("Days Inactive", style="red")
    table.add_column("Searches", justify="right")
    table.add_column("Files", justify="right")

    for project_name, data in sorted(all_projects.items()):
        state = data.get("state", "active")
        last_activity = data.get("last_activity", "Unknown")[:10]  # Date part only
        days_inactive = f"{manager.get_days_since_activity(project_name):.1f}"
        searches = str(data.get("searches_count", 0))
        files = str(data.get("files_indexed", 0))

        # Color state
        state_colored = state
        if state == "active":
            state_colored = f"[green]{state}[/green]"
        elif state == "archived":
            state_colored = f"[red]{state}[/red]"
        elif state == "paused":
            state_colored = f"[yellow]{state}[/yellow]"

        table.add_row(project_name, state_colored, last_activity, days_inactive, searches, files)

    console.print(table)

    # Show inactive projects
    inactive = manager.get_inactive_projects()
    if inactive:
        console.print(f"\n[yellow]⚠️  {len(inactive)} project(s) inactive for 45+ days (candidates for archival):[/yellow]")
        for proj in inactive:
            days = manager.get_days_since_activity(proj)
            console.print(f"  - {proj} ({days:.0f} days inactive)")


def archive_project(project_name: str):
    """Archive a project."""
    archival_file = Path.home() / ".claude-rag" / "project_states.json"
    manager = ProjectArchivalManager(str(archival_file))

    result = manager.archive_project(project_name)

    if result["success"]:
        console.print(f"[green]✓ {result['message']}[/green]")
    else:
        console.print(f"[red]✗ {result['message']}[/red]")


def reactivate_project(project_name: str):
    """Reactivate a project."""
    archival_file = Path.home() / ".claude-rag" / "project_states.json"
    manager = ProjectArchivalManager(str(archival_file))

    result = manager.reactivate_project(project_name)

    if result["success"]:
        console.print(f"[green]✓ {result['message']}[/green]")
    else:
        console.print(f"[red]✗ {result['message']}[/red]")


def export_project(project_name: str, output_path: str = None, include_readme: bool = True):
    """Export a project archive to a portable file."""
    config = get_config()
    archive_root = Path.home() / ".claude-rag" / "archives"

    compressor = ArchiveCompressor(
        archive_root=str(archive_root),
        compression_level=6,
    )
    exporter = ArchiveExporter(
        archive_compressor=compressor,
        compression_level=6,
    )

    console.print(f"[cyan]Exporting project '{project_name}'...[/cyan]")

    result = asyncio.run(exporter.export_project_archive(
        project_name=project_name,
        output_path=Path(output_path) if output_path else None,
        include_readme=include_readme,
    ))

    if result["success"]:
        console.print(f"[green]✓ Successfully exported to {result['export_file']}[/green]")
        console.print(f"  Size: {result['export_size_mb']:.2f} MB")
    else:
        console.print(f"[red]✗ Export failed: {result['error']}[/red]")


def import_project(archive_path: str, project_name: str = None, conflict_resolution: str = "skip"):
    """Import a project archive from a portable file."""
    config = get_config()
    archive_root = Path.home() / ".claude-rag" / "archives"

    compressor = ArchiveCompressor(
        archive_root=str(archive_root),
        compression_level=6,
    )
    importer = ArchiveImporter(
        archive_compressor=compressor,
    )

    console.print(f"[cyan]Importing archive from '{archive_path}'...[/cyan]")

    result = asyncio.run(importer.import_project_archive(
        archive_path=Path(archive_path),
        project_name=project_name,
        conflict_resolution=conflict_resolution,
    ))

    if result["success"]:
        console.print(f"[green]✓ Successfully imported project '{result['project_name']}'[/green]")
        console.print(f"  Size: {result['import_size_mb']:.2f} MB")
        if result.get("original_name"):
            console.print(f"  Original name: {result['original_name']}")
    else:
        console.print(f"[red]✗ Import failed: {result['error']}[/red]")
        if result.get("conflict"):
            console.print(f"  [yellow]Tip: Use --conflict overwrite to replace existing archive[/yellow]")


def list_exportable():
    """List all projects available for export."""
    config = get_config()
    archive_root = Path.home() / ".claude-rag" / "archives"

    compressor = ArchiveCompressor(
        archive_root=str(archive_root),
        compression_level=6,
    )
    exporter = ArchiveExporter(
        archive_compressor=compressor,
        compression_level=6,
    )

    result = exporter.list_exportable_projects()

    if not result["success"]:
        console.print(f"[red]✗ {result['error']}[/red]")
        return

    if not result["exportable_projects"]:
        console.print("[yellow]No projects available for export.[/yellow]")
        return

    # Create table
    table = Table(title="Exportable Projects", show_header=True, header_style="bold magenta")
    table.add_column("Project", style="cyan")
    table.add_column("Archived At", style="yellow")
    table.add_column("Size (MB)", justify="right", style="green")
    table.add_column("Compression", justify="right", style="blue")

    for proj in sorted(result["exportable_projects"], key=lambda x: x["project_name"]):
        archived_at = proj.get("archived_at", "Unknown")[:10] if proj.get("archived_at") else "Unknown"
        size_mb = f"{proj.get('size_mb', 0):.2f}"
        compression_ratio = f"{proj.get('compression_ratio', 0):.2f}"

        table.add_row(proj["project_name"], archived_at, size_mb, compression_ratio)

    console.print(table)
    console.print(f"\n[bold]Total: {result['total_projects']} projects ({result['total_size_mb']:.2f} MB)[/bold]")


def main():
    """Main entry point for archival CLI."""
    import argparse

    parser = argparse.ArgumentParser(description="Project archival and lifecycle management")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Status command
    subparsers.add_parser("status", help="Show status of all projects")

    # Archive command
    archive_parser = subparsers.add_parser("archive", help="Archive a project")
    archive_parser.add_argument("project_name", help="Name of project to archive")

    # Reactivate command
    reactivate_parser = subparsers.add_parser("reactivate", help="Reactivate an archived project")
    reactivate_parser.add_argument("project_name", help="Name of project to reactivate")

    # Export command
    export_parser = subparsers.add_parser("export", help="Export project archive to portable file")
    export_parser.add_argument("project_name", help="Name of project to export")
    export_parser.add_argument("-o", "--output", help="Output file path (default: auto-generated)")
    export_parser.add_argument("--no-readme", action="store_true", help="Skip README generation")

    # Import command
    import_parser = subparsers.add_parser("import", help="Import project archive from portable file")
    import_parser.add_argument("archive_path", help="Path to archive file (.tar.gz)")
    import_parser.add_argument("-n", "--name", help="Custom project name (default: use name from archive)")
    import_parser.add_argument("--conflict", choices=["skip", "overwrite"], default="skip",
                                help="Conflict resolution strategy (default: skip)")

    # List exportable projects
    subparsers.add_parser("list-exportable", help="List all projects available for export")

    args = parser.parse_args()

    if args.command == "status":
        show_status()
    elif args.command == "archive":
        archive_project(args.project_name)
    elif args.command == "reactivate":
        reactivate_project(args.project_name)
    elif args.command == "export":
        export_project(args.project_name, args.output, not args.no_readme)
    elif args.command == "import":
        import_project(args.archive_path, args.name, args.conflict)
    elif args.command == "list-exportable":
        list_exportable()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
