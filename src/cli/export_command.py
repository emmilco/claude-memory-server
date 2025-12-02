"""CLI command for exporting memories and code indexes."""

import asyncio
import logging
from pathlib import Path
from datetime import datetime, UTC
from typing import Optional
import sys

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

from src.backup.exporter import DataExporter
from src.store.factory import create_store
from src.config import get_config
from src.core.models import MemoryCategory, ContextLevel

logger = logging.getLogger(__name__)
console = Console()


async def export_command(
    output: str,
    format: str = "json",
    project: Optional[str] = None,
    category: Optional[str] = None,
    context_level: Optional[str] = None,
    since: Optional[str] = None,
    until: Optional[str] = None,
    include_embeddings: bool = True,
    include_metadata: bool = True,
) -> int:
    """
    Export memories to various formats.

    Args:
        output: Output file path
        format: Export format (json, markdown, archive)
        project: Filter by project name
        category: Filter by category
        context_level: Filter by context level
        since: Filter by creation date (after this date)
        until: Filter by creation date (before this date)
        include_embeddings: Include embeddings in archive (archive format only)
        include_metadata: Include metadata in markdown (markdown format only)

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    try:
        console.print("\n[bold blue]Memory Export[/bold blue]\n")

        # Initialize store
        config = get_config()
        store = create_store(config)
        await store.initialize()

        # Create exporter
        exporter = DataExporter(store)

        # Parse filters
        category_filter = MemoryCategory(category) if category else None
        context_level_filter = ContextLevel(context_level) if context_level else None

        # Parse dates
        since_date = None
        if since:
            since_date = datetime.fromisoformat(since)
            if since_date.tzinfo is None:
                since_date = since_date.replace(tzinfo=UTC)

        until_date = None
        if until:
            until_date = datetime.fromisoformat(until)
            if until_date.tzinfo is None:
                until_date = until_date.replace(tzinfo=UTC)

        # Display export configuration
        config_table = Table(show_header=False, box=None)
        config_table.add_row("[cyan]Format:[/cyan]", format)
        config_table.add_row("[cyan]Output:[/cyan]", output)
        if project:
            config_table.add_row("[cyan]Project Filter:[/cyan]", project)
        if category:
            config_table.add_row("[cyan]Category Filter:[/cyan]", category)
        if context_level:
            config_table.add_row("[cyan]Context Level Filter:[/cyan]", context_level)
        if since:
            config_table.add_row("[cyan]Since Date:[/cyan]", since)
        if until:
            config_table.add_row("[cyan]Until Date:[/cyan]", until)

        console.print(
            Panel(config_table, title="Export Configuration", border_style="blue")
        )
        console.print()

        # Perform export with progress indicator
        output_path = Path(output).expanduser()

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Exporting memories...", total=None)

            if format == "json":
                stats = await exporter.export_to_json(
                    output_path=output_path,
                    project_name=project,
                    category=category_filter,
                    context_level=context_level_filter,
                    since_date=since_date,
                    until_date=until_date,
                )
            elif format == "markdown":
                stats = await exporter.export_to_markdown(
                    output_path=output_path,
                    project_name=project,
                    include_metadata=include_metadata,
                )
            elif format == "archive":
                stats = await exporter.create_portable_archive(
                    output_path=output_path,
                    project_name=project,
                    include_embeddings=include_embeddings,
                )
            else:
                console.print(f"[red]Error:[/red] Unknown format: {format}")
                console.print("Supported formats: json, markdown, archive")
                return 1

            progress.update(task, completed=True)

        # Display results
        results_table = Table(show_header=False, box=None)
        results_table.add_row("[green]✓[/green] Export completed successfully")
        results_table.add_row("")
        results_table.add_row(
            "[cyan]Memories Exported:[/cyan]", str(stats["memory_count"])
        )
        results_table.add_row("[cyan]Output File:[/cyan]", stats["output_path"])
        results_table.add_row(
            "[cyan]File Size:[/cyan]", f"{stats['file_size_bytes']:,} bytes"
        )

        if format == "archive":
            results_table.add_row(
                "[cyan]Includes Embeddings:[/cyan]",
                "Yes" if stats["includes_embeddings"] else "No",
            )

        console.print(
            Panel(results_table, title="Export Results", border_style="green")
        )
        console.print()

        # Cleanup
        await store.close()

        return 0

    except Exception as e:
        console.print(f"\n[red]Error:[/red] Export failed: {e}")
        logger.error(f"Export command failed: {e}", exc_info=True)
        return 1


def main():
    """Main entry point for export command."""
    import argparse

    parser = argparse.ArgumentParser(description="Export memories to various formats")
    parser.add_argument("output", help="Output file path")
    parser.add_argument(
        "--format",
        choices=["json", "markdown", "archive"],
        default="json",
        help="Export format (default: json)",
    )
    parser.add_argument("--project", help="Filter by project name")
    parser.add_argument(
        "--category",
        choices=["preference", "fact", "event", "workflow", "context"],
        help="Filter by category",
    )
    parser.add_argument(
        "--context-level",
        choices=["USER_PREFERENCE", "PROJECT_CONTEXT", "SESSION_STATE"],
        help="Filter by context level",
    )
    parser.add_argument("--since", help="Filter by creation date (after), ISO format")
    parser.add_argument("--until", help="Filter by creation date (before), ISO format")
    parser.add_argument(
        "--no-embeddings",
        action="store_true",
        help="Exclude embeddings from archive (archive format only)",
    )
    parser.add_argument(
        "--no-metadata",
        action="store_true",
        help="Exclude metadata from markdown (markdown format only)",
    )

    args = parser.parse_args()

    # Run async command
    exit_code = asyncio.run(
        export_command(
            output=args.output,
            format=args.format,
            project=args.project,
            category=args.category,
            context_level=args.context_level,
            since=args.since,
            until=args.until,
            include_embeddings=not args.no_embeddings,
            include_metadata=not args.no_metadata,
        )
    )

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
