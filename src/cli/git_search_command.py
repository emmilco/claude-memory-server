"""CLI command for searching git history."""

import logging
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from src.config import get_config
from src.store.sqlite_store import SQLiteMemoryStore

logger = logging.getLogger(__name__)
console = Console()


class GitSearchCommand:
    """Command to search git history."""

    async def run(self, args):
        """
        Run the git search command.

        Args:
            args: Parsed command-line arguments
        """
        config = get_config()
        query = args.query
        project_name = args.project_name
        author = args.author
        since = args.since
        until = args.until
        limit = args.limit

        console.print(
            Panel.fit(
                f"[bold cyan]Searching Git History[/bold cyan]\n"
                f"Query: {query}",
                border_style="cyan",
            )
        )

        try:
            # Initialize storage
            with console.status("[bold green]Searching..."):
                store = SQLiteMemoryStore(config)
                await store.initialize()

                # Parse date filters
                since_dt = None
                until_dt = None

                if since:
                    from datetime import datetime, timedelta, UTC
                    # Simple date parsing
                    if since == "today":
                        since_dt = datetime.now(UTC)
                    elif since == "yesterday":
                        since_dt = datetime.now(UTC) - timedelta(days=1)
                    elif since == "last week":
                        since_dt = datetime.now(UTC) - timedelta(weeks=1)
                    elif since == "last month":
                        since_dt = datetime.now(UTC) - timedelta(days=30)
                    else:
                        try:
                            since_dt = datetime.fromisoformat(since).replace(tzinfo=UTC)
                        except Exception as e:
                            logger.debug(f"Failed to parse 'since' date as ISO format '{since}': {e}")
                            try:
                                since_dt = datetime.strptime(since, "%Y-%m-%d").replace(tzinfo=UTC)
                            except Exception as e2:
                                logger.warning(f"Failed to parse 'since' date '{since}' in any format: {e2}")
                                console.print(f"[yellow]Warning: Could not parse 'since' date: {since}[/yellow]")

                if until:
                    from datetime import datetime, timedelta, UTC
                    if until == "today":
                        until_dt = datetime.now(UTC)
                    elif until == "yesterday":
                        until_dt = datetime.now(UTC) - timedelta(days=1)
                    else:
                        try:
                            until_dt = datetime.fromisoformat(until).replace(tzinfo=UTC)
                        except Exception as e:
                            logger.debug(f"Failed to parse 'until' date as ISO format '{until}': {e}")
                            try:
                                until_dt = datetime.strptime(until, "%Y-%m-%d").replace(tzinfo=UTC)
                            except Exception as e2:
                                logger.warning(f"Failed to parse 'until' date '{until}' in any format: {e2}")
                                console.print(f"[yellow]Warning: Could not parse 'until' date: {until}[/yellow]")

                # Search commits
                commits = await store.search_git_commits(
                    query=query,
                    repository_path=None,
                    author=author,
                    since=since_dt,
                    until=until_dt,
                    limit=limit,
                )

            # Display results
            if not commits:
                console.print("\n[yellow]No matching commits found.[/yellow]")
                return

            table = Table(title=f"Search Results ({len(commits)} commits)")
            table.add_column("Hash", style="cyan", no_wrap=True)
            table.add_column("Author", style="green")
            table.add_column("Date", style="blue")
            table.add_column("Message", style="white")

            for commit in commits:
                # Truncate message for display
                message = commit["message"].split("\n")[0]  # First line only
                if len(message) > 60:
                    message = message[:57] + "..."

                # Format date
                date_str = commit["author_date"]
                if isinstance(date_str, str):
                    try:
                        from datetime import datetime
                        dt = datetime.fromisoformat(date_str)
                        date_str = dt.strftime("%Y-%m-%d %H:%M")
                    except Exception as e:
                        logger.debug(f"Failed to format commit date '{date_str}': {e}")

                table.add_row(
                    commit["commit_hash"][:8],
                    commit["author_name"],
                    date_str,
                    message,
                )

            console.print(table)

            # Show filters
            filters_str = ""
            if author:
                filters_str += f" | Author: {author}"
            if since:
                filters_str += f" | Since: {since}"
            if until:
                filters_str += f" | Until: {until}"

            if filters_str:
                console.print(f"\n[dim]Filters:{filters_str}[/dim]")

        except Exception as e:
            console.print(f"[bold red]✗ Error:[/bold red] {e}")
            logger.exception("Failed to search git history")
            raise
