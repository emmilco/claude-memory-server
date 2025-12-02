"""CLI command for session summaries (UX-031)."""

import logging
from typing import Optional
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.table import Table

from src.analytics.token_tracker import TokenTracker

logger = logging.getLogger(__name__)
console = Console()


def run_session_summary_command(session_id: Optional[str] = None) -> None:
    """
    Display a summary of the current or specified session.

    Args:
        session_id: Session ID to summarize (if None, shows recent sessions)
    """
    try:
        tracker = TokenTracker()

        if session_id:
            # Show specific session summary
            _display_session_summary(tracker, session_id)
        else:
            # Show recent top sessions
            _display_recent_sessions(tracker)

    except Exception as e:
        logger.error(f"Failed to get session summary: {e}")
        console.print(f"[red]✗ Error getting session summary: {e}[/red]")
        raise


def _display_session_summary(tracker: TokenTracker, session_id: str) -> None:
    """Display summary for a specific session."""
    summary = tracker.get_session_summary(session_id)

    # Create title
    title = f"Session Summary: {session_id[:16]}..."

    # Build summary text
    summary_text = Text()
    summary_text.append("🔍 Searches: ", style="bold")
    summary_text.append(f"{summary['searches']}\n", style="cyan")

    summary_text.append("📁 Files Indexed: ", style="bold")
    summary_text.append(f"{summary['files_indexed']}\n", style="cyan")

    summary_text.append("💾 Tokens Used: ", style="bold")
    summary_text.append(f"{summary['tokens_used']:,}\n")

    summary_text.append("⚡ Tokens Saved: ", style="bold")
    summary_text.append(f"{summary['tokens_saved']:,}\n", style="green")

    summary_text.append("💰 Cost Savings: ", style="bold")
    summary_text.append(f"${summary['cost_savings_usd']:.2f}\n", style="bold green")

    summary_text.append("📊 Efficiency: ", style="bold")
    summary_text.append(f"{summary['efficiency_ratio']:.1f}%\n", style="cyan")

    summary_text.append("⭐ Avg Relevance: ", style="bold")
    relevance_color = (
        "green"
        if summary["avg_relevance"] > 0.8
        else "yellow"
        if summary["avg_relevance"] > 0.6
        else "red"
    )
    summary_text.append(
        f"{summary['avg_relevance']:.2f}\n", style=f"bold {relevance_color}"
    )

    # Create panel
    panel = Panel(summary_text, title=title, border_style="green", padding=(1, 2))
    console.print(panel)


def _display_recent_sessions(tracker: TokenTracker, limit: int = 10) -> None:
    """Display summary of recent top sessions."""
    console.print(
        Panel(
            "[cyan]💡 Tip:[/cyan] Specify a session ID to see detailed summary\n"
            "[dim]Example: python -m src.cli session-summary --session-id abc123[/dim]",
            title="Session Summaries",
            border_style="blue",
        )
    )

    top_sessions = tracker.get_top_sessions(limit=limit)

    if not top_sessions:
        console.print("\n[dim]No sessions found yet.[/dim]")
        console.print(
            "[dim]Sessions are created automatically when you use the MCP server.[/dim]"
        )
        return

    # Create table
    table = Table(
        title=f"Top {len(top_sessions)} Sessions (by Tokens Saved)",
        show_header=True,
        header_style="bold",
    )

    table.add_column("Rank", style="dim", width=6)
    table.add_column("Session ID", style="cyan")
    table.add_column("Tokens Saved", style="green", justify="right")
    table.add_column("Events", style="white", justify="right")
    table.add_column("Est. Savings", style="green", justify="right")

    for rank, session in enumerate(top_sessions, start=1):
        # Calculate estimated cost savings
        savings_usd = (session["tokens_saved"] / 1_000_000) * 3.00

        table.add_row(
            f"#{rank}",
            session["session_id"][:16] + "...",
            f"{session['tokens_saved']:,}",
            str(session["events"]),
            f"${savings_usd:.2f}",
        )

    console.print()
    console.print(table)
    console.print()
    console.print(
        "[dim]💡 Use --session-id <ID> to see detailed summary for a specific session[/dim]"
    )


if __name__ == "__main__":
    # For testing
    logging.basicConfig(level=logging.INFO)
    run_session_summary_command()
