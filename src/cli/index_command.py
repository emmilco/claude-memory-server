"""Index command for CLI - indexes code files into vector storage."""

import asyncio
import logging
from pathlib import Path
from typing import Optional
import time

try:
    from rich.console import Console
    from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeRemainingColumn, TaskProgressColumn
    from rich.panel import Panel
    from rich.table import Table
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

from src.memory.incremental_indexer import IncrementalIndexer
from src.config import get_config

logger = logging.getLogger(__name__)


class IndexCommand:
    """Command to index code files for semantic search."""

    def __init__(self):
        """Initialize index command."""
        self.config = get_config()
        self.console = Console() if RICH_AVAILABLE else None

    def _print_rich_summary(self, project_name: str, path: Path, result: dict, elapsed: float, recursive: bool):
        """Print rich formatted summary."""
        self.console.print()

        # Create summary table
        table = Table(title="[bold green]✓ Indexing Complete[/bold green]", show_header=False)
        table.add_column("Metric", style="cyan", width=25)
        table.add_column("Value", style="white")

        table.add_row("Project", project_name)
        table.add_row("Directory", str(path))
        table.add_row("Mode", "Recursive" if recursive else "Single level")
        table.add_row("", "")  # Spacer
        table.add_row("Files found", f"{result['total_files']:,}")
        table.add_row("Files indexed", f"[green]{result['indexed_files']:,}[/green]")
        table.add_row("Files skipped", f"[yellow]{result['skipped_files']:,}[/yellow]")
        if result['failed_files']:
            table.add_row("Files failed", f"[red]{len(result['failed_files']):,}[/red]")
        table.add_row("", "")  # Spacer
        table.add_row("Semantic units", f"[bold]{result['total_units']:,}[/bold]")
        table.add_row("", "")  # Spacer
        table.add_row("Time elapsed", f"{elapsed:.2f}s")

        if result['indexed_files'] > 0:
            files_per_sec = result['indexed_files'] / elapsed
            units_per_sec = result['total_units'] / elapsed
            table.add_row("Throughput", f"{files_per_sec:.2f} files/sec, {units_per_sec:.1f} units/sec")

        self.console.print(table)

        # Show failed files if any
        if result['failed_files']:
            self.console.print()
            self.console.print(f"[bold yellow]⚠ Failed Files ({len(result['failed_files'])}):[/bold yellow]")
            for failed_file in result['failed_files'][:10]:  # Show first 10
                self.console.print(f"  [dim]• {failed_file}[/dim]")
            if len(result['failed_files']) > 10:
                self.console.print(f"  [dim]... and {len(result['failed_files']) - 10} more[/dim]")

        self.console.print()

    def _print_plain_summary(self, project_name: str, path: Path, result: dict, elapsed: float):
        """Print plain text summary."""
        print("\n" + "=" * 60)
        print("INDEXING COMPLETE")
        print("=" * 60)
        print(f"Project: {project_name}")
        print(f"Directory: {path}")
        print(f"Total files found: {result['total_files']}")
        print(f"Files indexed: {result['indexed_files']}")
        print(f"Files skipped: {result['skipped_files']}")
        print(f"Semantic units indexed: {result['total_units']}")
        print(f"Total time: {elapsed:.2f}s")

        if result['failed_files']:
            print(f"\nFailed files ({len(result['failed_files'])}):")
            for failed_file in result['failed_files']:
                print(f"  - {failed_file}")

        print("=" * 60 + "\n")

        # Calculate throughput
        if result['indexed_files'] > 0:
            files_per_sec = result['indexed_files'] / elapsed
            units_per_sec = result['total_units'] / elapsed
            print(f"Throughput: {files_per_sec:.2f} files/sec, {units_per_sec:.2f} units/sec\n")

    async def run(self, args):
        """
        Run the index command.

        Args:
            args: Parsed command-line arguments
        """
        path = Path(args.path).resolve()

        if not path.exists():
            logger.error(f"Path does not exist: {path}")
            return

        # Determine project name
        project_name = args.project_name
        if not project_name:
            if path.is_dir():
                project_name = path.name
            else:
                project_name = path.parent.name

        logger.info(f"Indexing for project: {project_name}")
        logger.info(f"Path: {path}")

        # Initialize indexer
        indexer = IncrementalIndexer(project_name=project_name)

        try:
            await indexer.initialize()

            start_time = time.time()

            if path.is_file():
                # Index single file
                logger.info(f"Indexing file: {path}")
                result = await indexer.index_file(path)

                elapsed = time.time() - start_time

                print("\n" + "=" * 60)
                print("INDEXING COMPLETE")
                print("=" * 60)
                print(f"File: {result['file_path']}")
                print(f"Language: {result.get('language', 'N/A')}")
                print(f"Units indexed: {result['units_indexed']}")
                print(f"Parse time: {result.get('parse_time_ms', 0):.2f}ms")
                print(f"Total time: {elapsed:.2f}s")
                print("=" * 60 + "\n")

            elif path.is_dir():
                # Index directory
                logger.info(f"Indexing directory: {path}")
                logger.info(f"Recursive: {args.recursive}")

                # Show nice header if Rich is available
                if self.console:
                    self.console.print()
                    self.console.print(
                        Panel.fit(
                            f"[bold blue]Indexing Project:[/bold blue] [cyan]{project_name}[/cyan]\n"
                            f"[dim]Path: {path}[/dim]\n"
                            f"[dim]Recursive: {args.recursive}[/dim]",
                            border_style="blue",
                        )
                    )
                    self.console.print()

                # Index with progress
                if self.console and RICH_AVAILABLE:
                    with Progress(
                        SpinnerColumn(),
                        TextColumn("[progress.description]{task.description}"),
                        BarColumn(),
                        TaskProgressColumn(),
                        TimeRemainingColumn(),
                        console=self.console,
                    ) as prog:
                        task = prog.add_task(
                            f"[cyan]Preparing to index {path.name}...",
                            total=None,  # Will update when we know file count
                        )

                        error_count = 0

                        def progress_callback(current: int, total: int, current_file: Optional[str], error_info: Optional[dict]):
                            """Update progress bar with indexing status."""
                            nonlocal error_count

                            # Update total if this is the first callback
                            if prog.tasks[task].total is None and total > 0:
                                prog.update(task, total=total)

                            # Update progress
                            if current_file:
                                if error_info:
                                    error_count += 1
                                    prog.update(
                                        task,
                                        completed=current,
                                        description=f"[cyan]Indexing[/cyan] [yellow]({error_count} errors)[/yellow] - [dim]{current_file}[/dim]",
                                    )
                                else:
                                    desc = f"[cyan]Indexing[/cyan]"
                                    if error_count > 0:
                                        desc += f" [yellow]({error_count} errors)[/yellow]"
                                    desc += f" - [dim]{current_file}[/dim]"
                                    prog.update(task, completed=current, description=desc)
                            else:
                                # Initial callback with total count
                                prog.update(task, total=total, description=f"[cyan]Indexing {total} files...[/cyan]")

                        result = await indexer.index_directory(
                            path,
                            recursive=args.recursive,
                            show_progress=False,  # Use our progress bar instead
                            progress_callback=progress_callback,
                        )

                        # Final update
                        prog.update(task, completed=result['total_files'], description="[green]✓ Indexing complete[/green]")
                else:
                    result = await indexer.index_directory(
                        path,
                        recursive=args.recursive,
                        show_progress=True,  # Fall back to logging
                    )

                elapsed = time.time() - start_time

                # Show summary
                if self.console and RICH_AVAILABLE:
                    self._print_rich_summary(project_name, path, result, elapsed, args.recursive)
                else:
                    self._print_plain_summary(project_name, path, result, elapsed)

            else:
                logger.error(f"Path is neither a file nor directory: {path}")

        except Exception as e:
            logger.error(f"Indexing failed: {e}", exc_info=True)
            print(f"\nERROR: Indexing failed - {e}\n")
            raise

        finally:
            await indexer.close()
