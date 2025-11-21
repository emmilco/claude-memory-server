"""CLI command for indexing git history."""

import logging
from pathlib import Path
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
from rich.panel import Panel
from rich.table import Table

from src.config import get_config
from src.memory.git_indexer import GitIndexer
from src.embeddings.generator import EmbeddingGenerator
from src.store.qdrant_store import QdrantMemoryStore

logger = logging.getLogger(__name__)
console = Console()


class GitIndexCommand:
    """Command to index git history."""

    async def run(self, args):
        """
        Run the git index command.

        Args:
            args: Parsed command-line arguments
        """
        config = get_config()
        repo_path = Path(args.repo_path).resolve()
        project_name = args.project_name
        num_commits = args.commits
        include_diffs = args.diffs

        console.print(
            Panel.fit(
                f"[bold cyan]Indexing Git History[/bold cyan]\n"
                f"Repository: {repo_path}\n"
                f"Project: {project_name}",
                border_style="cyan",
            )
        )

        try:
            # Initialize components
            with console.status("[bold green]Initializing..."):
                embedding_generator = EmbeddingGenerator(config)
                await embedding_generator.initialize()

                git_indexer = GitIndexer(config, embedding_generator)

                # Initialize storage
                store = QdrantMemoryStore(config)
                await store.initialize()

            # Index repository
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                TimeElapsedColumn(),
                console=console,
            ) as progress:
                task = progress.add_task(
                    f"Indexing git history (commits: {num_commits or config.git_index_commit_count})...",
                    total=None,
                )

                # Index the repository
                commits_data, file_changes_data = await git_indexer.index_repository(
                    str(repo_path),
                    project_name,
                    num_commits=num_commits,
                    include_diffs=include_diffs,
                )

                progress.update(task, completed=True)

            # Store in database
            with console.status("[bold green]Storing in database..."):
                # Convert commit data objects to dicts
                commits_dicts = [
                    {
                        "commit_hash": c.commit_hash,
                        "repository_path": c.repository_path,
                        "author_name": c.author_name,
                        "author_email": c.author_email,
                        "author_date": c.author_date,
                        "committer_name": c.committer_name,
                        "committer_date": c.committer_date,
                        "message": c.message,
                        "message_embedding": c.message_embedding,
                        "branch_names": c.branch_names,
                        "tags": c.tags,
                        "parent_hashes": c.parent_hashes,
                        "stats": c.stats,
                    }
                    for c in commits_data
                ]

                # Convert file change data objects to dicts
                file_changes_dicts = [
                    {
                        "id": f.id,
                        "commit_hash": f.commit_hash,
                        "file_path": f.file_path,
                        "change_type": f.change_type,
                        "lines_added": f.lines_added,
                        "lines_deleted": f.lines_deleted,
                        "diff_content": f.diff_content,
                        "diff_embedding": f.diff_embedding,
                    }
                    for f in file_changes_data
                ]

                # Store commits
                commits_stored = await store.store_git_commits(commits_dicts)

                # Store file changes
                if file_changes_dicts:
                    changes_stored = await store.store_git_file_changes(file_changes_dicts)
                else:
                    changes_stored = 0

            # Display results
            stats = git_indexer.get_stats()

            table = Table(title="Indexing Results", show_header=False)
            table.add_column("Metric", style="cyan")
            table.add_column("Value", style="green")

            table.add_row("Repository", str(repo_path))
            table.add_row("Project", project_name)
            table.add_row("Commits Indexed", str(stats["commits_indexed"]))
            table.add_row("Commits Stored", str(commits_stored))
            table.add_row("File Changes Indexed", str(stats["file_changes_indexed"]))
            table.add_row("File Changes Stored", str(changes_stored))
            table.add_row("Diffs Embedded", str(stats["diffs_embedded"]))
            if stats["errors"] > 0:
                table.add_row("Errors", str(stats["errors"]), style="red")

            console.print(table)

            if stats["errors"] > 0:
                console.print(
                    f"\n[yellow]⚠ {stats['errors']} errors occurred during indexing. "
                    "Check logs for details.[/yellow]"
                )

            console.print("\n[bold green]✓ Git history indexed successfully![/bold green]")

        except ImportError as e:
            console.print(
                f"[bold red]✗ Error:[/bold red] GitPython not installed.\n"
                f"Install with: pip install GitPython>=3.1.40"
            )
            raise

        except ValueError as e:
            console.print(f"[bold red]✗ Error:[/bold red] {e}")
            raise

        except Exception as e:
            console.print(f"[bold red]✗ Error:[/bold red] {e}")
            logger.exception("Failed to index git history")
            raise
