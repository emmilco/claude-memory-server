"""CLI command for viewing token usage analytics (UX-029)."""

import logging
from typing import Optional
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

from src.analytics.token_tracker import TokenTracker

logger = logging.getLogger(__name__)
console = Console()


def format_number(num: int) -> str:
    """Format large numbers with commas."""
    return f"{num:,}"


def format_currency(amount: float) -> str:
    """Format currency with $ sign."""
    return f"${amount:.2f}"


def format_percentage(ratio: float) -> str:
    """Format ratio as percentage."""
    return f"{ratio * 100:.1f}%"


def run_analytics_command(
    period_days: int = 30,
    session_id: Optional[str] = None,
    project_name: Optional[str] = None,
    show_top_sessions: bool = False,
) -> None:
    """
    Display token usage analytics.

    Args:
        period_days: Number of days to analyze (default 30)
        session_id: Filter by specific session ID
        project_name: Filter by specific project
        show_top_sessions: Show top sessions by savings
    """
    try:
        tracker = TokenTracker()

        # Get analytics
        analytics = tracker.get_analytics(
            period_days=period_days,
            session_id=session_id,
            project_name=project_name,
        )

        # Display summary panel
        _display_summary(analytics, period_days, session_id, project_name)

        # Display detailed stats
        _display_detailed_stats(analytics)

        # Optionally show top sessions
        if show_top_sessions:
            _display_top_sessions(tracker)

    except Exception as e:
        logger.error(f"Failed to get analytics: {e}")
        console.print(f"[red]✗ Error getting analytics: {e}[/red]")
        raise


def _display_summary(
    analytics,
    period_days: int,
    session_id: Optional[str],
    project_name: Optional[str],
) -> None:
    """Display high-level summary panel."""
    # Build title
    title_parts = ["Token Usage Analytics"]
    if session_id:
        title_parts.append(f"Session: {session_id[:8]}...")
    elif project_name:
        title_parts.append(f"Project: {project_name}")
    else:
        title_parts.append(f"Last {period_days} days")

    title = " - ".join(title_parts)

    # Build summary text
    summary = Text()
    summary.append("💰 Cost Savings: ", style="bold")
    summary.append(
        f"{format_currency(analytics.cost_savings_usd)}\n", style="bold green"
    )

    summary.append("⚡ Efficiency: ", style="bold")
    summary.append(
        f"{format_percentage(analytics.efficiency_ratio)}\n", style="bold cyan"
    )

    summary.append("🔍 Searches: ", style="bold")
    summary.append(f"{format_number(analytics.total_searches)}\n")

    summary.append("📁 Files Indexed: ", style="bold")
    summary.append(f"{format_number(analytics.total_files_indexed)}\n")

    # Create panel
    panel = Panel(summary, title=title, border_style="green", padding=(1, 2))
    console.print(panel)


def _display_detailed_stats(analytics) -> None:
    """Display detailed statistics table."""
    table = Table(title="Detailed Statistics", show_header=True, header_style="bold")

    table.add_column("Metric", style="cyan", width=30)
    table.add_column("Value", style="white", justify="right")
    table.add_column("Details", style="dim")

    # Tokens used
    table.add_row(
        "Tokens Used",
        format_number(analytics.total_tokens_used),
        "Actual tokens consumed",
    )

    # Tokens saved
    table.add_row(
        "Tokens Saved",
        format_number(analytics.total_tokens_saved),
        "vs. manual paste approach",
    )

    # Efficiency ratio
    efficiency_color = "green" if analytics.efficiency_ratio > 0.6 else "yellow"
    table.add_row(
        "Efficiency Ratio",
        f"[{efficiency_color}]{format_percentage(analytics.efficiency_ratio)}[/{efficiency_color}]",
        "tokens saved / total tokens",
    )

    # Cost savings
    table.add_row(
        "Estimated Cost Savings",
        f"[green]{format_currency(analytics.cost_savings_usd)}[/green]",
        f"@ ${TokenTracker.INPUT_COST_PER_MILLION}/M tokens",
    )

    # Average relevance
    relevance_color = (
        "green"
        if analytics.avg_relevance > 0.8
        else "yellow"
        if analytics.avg_relevance > 0.6
        else "red"
    )
    table.add_row(
        "Average Relevance",
        f"[{relevance_color}]{analytics.avg_relevance:.2f}[/{relevance_color}]",
        "Search result quality",
    )

    # Searches performed
    table.add_row(
        "Total Searches",
        format_number(analytics.total_searches),
        f"{analytics.period_start.strftime('%Y-%m-%d')} to {analytics.period_end.strftime('%Y-%m-%d')}",
    )

    # Files indexed
    table.add_row(
        "Files Indexed", format_number(analytics.total_files_indexed), "Code indexed"
    )

    console.print(table)


def _display_top_sessions(tracker: TokenTracker, limit: int = 10) -> None:
    """Display top sessions by tokens saved."""
    top_sessions = tracker.get_top_sessions(limit=limit)

    if not top_sessions:
        console.print("\n[dim]No sessions with saved tokens found.[/dim]")
        return

    table = Table(
        title=f"Top {limit} Sessions by Tokens Saved",
        show_header=True,
        header_style="bold",
    )

    table.add_column("Rank", style="dim", width=6)
    table.add_column("Session ID", style="cyan")
    table.add_column("Tokens Saved", style="green", justify="right")
    table.add_column("Events", style="white", justify="right")

    for rank, session in enumerate(top_sessions, start=1):
        table.add_row(
            f"#{rank}",
            session["session_id"][:12] + "...",
            format_number(session["tokens_saved"]),
            str(session["events"]),
        )

    console.print()
    console.print(table)


if __name__ == "__main__":
    # For testing
    logging.basicConfig(level=logging.INFO)
    run_analytics_command(period_days=30, show_top_sessions=True)
