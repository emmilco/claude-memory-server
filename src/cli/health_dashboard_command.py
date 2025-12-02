"""Health dashboard CLI command for memory lifecycle monitoring.

Displays health metrics, lifecycle distribution, and recommendations in a
formatted dashboard view.
"""

import asyncio
import json

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

from src.config import get_config
from src.store import create_memory_store
from src.memory.health_scorer import HealthScorer
from src.memory.lifecycle_manager import LifecycleManager

console = Console()


def create_health_bar(score: float, width: int = 10) -> str:
    """
    Create a visual health bar.

    Args:
        score: Score from 0-100
        width: Width of the bar in characters

    Returns:
        String with filled and empty circles
    """
    filled = int((score / 100) * width)
    empty = width - filled
    return "●" * filled + "○" * empty


def get_score_color(score: float) -> str:
    """Get color for a score."""
    if score >= 90:
        return "green"
    elif score >= 75:
        return "yellow"
    elif score >= 60:
        return "orange"
    else:
        return "red"


def get_metric_bar(value: float, threshold: float, good_low: bool = True) -> str:
    """
    Create a metric progress bar.

    Args:
        value: Metric value (0-1)
        threshold: Threshold value (0-1)
        good_low: True if low values are good

    Returns:
        String representation
    """
    value * 100
    width = 10

    if good_low:
        # Low is good (noise, duplicates, contradictions)
        if value <= threshold:
            color = "green"
        elif value <= threshold * 1.5:
            color = "yellow"
        else:
            color = "red"
    else:
        # High is good (distribution score)
        if value >= threshold:
            color = "green"
        elif value >= threshold * 0.75:
            color = "yellow"
        else:
            color = "red"

    filled = int((value) * width)
    empty = width - filled
    bar = "█" * filled + "░" * empty

    return f"[{color}]{bar}[/{color}]"


async def health_dashboard(
    detailed: bool = False,
    json_output: bool = False,
) -> None:
    """
    Display health dashboard.

    Args:
        detailed: Show detailed metrics
        json_output: Output as JSON instead of formatted display
    """
    config = get_config()

    # Initialize components
    store = create_memory_store(config=config)
    await store.initialize()

    try:
        health_scorer = HealthScorer(store)

        # Calculate health score
        console.print("[dim]Calculating health metrics...[/dim]")
        health_score = await health_scorer.calculate_overall_health()

        if json_output:
            # JSON output
            print(json.dumps(health_score.to_dict(), indent=2))
            return

        # Rich formatted output
        console.clear()

        # Header
        header = Panel(
            Text("Memory System Health Dashboard", justify="center", style="bold"),
            border_style="blue",
        )
        console.print(header)
        console.print()

        # Overall Health Score
        score_color = get_score_color(health_score.overall)
        health_bar = create_health_bar(health_score.overall)

        overall_table = Table(show_header=False, box=None, padding=(0, 2))
        overall_table.add_row(
            "Overall Health:",
            f"[{score_color}]{health_score.overall:.1f}/100[/{score_color}]",
            f"({health_score.grade})",
            health_bar,
        )
        console.print(overall_table)
        console.print()

        # Quality Metrics
        console.print("[bold]Quality Metrics:[/bold]")

        metrics_table = Table(show_header=False, box=None, padding=(0, 2))

        # Noise Ratio
        noise_bar = get_metric_bar(
            health_score.noise_ratio, health_scorer.NOISE_THRESHOLD
        )
        noise_status = (
            "✓" if health_score.noise_ratio <= health_scorer.NOISE_THRESHOLD else "⚠"
        )
        metrics_table.add_row(
            f"  {noise_status} Noise Ratio:",
            f"{health_score.noise_ratio:.1%}",
            noise_bar,
            f"(target: <{health_scorer.NOISE_THRESHOLD:.0%})",
        )

        # Duplicate Rate
        dup_bar = get_metric_bar(
            health_score.duplicate_rate, health_scorer.DUPLICATE_THRESHOLD
        )
        dup_status = (
            "✓"
            if health_score.duplicate_rate <= health_scorer.DUPLICATE_THRESHOLD
            else "⚠"
        )
        metrics_table.add_row(
            f"  {dup_status} Duplicate Rate:",
            f"{health_score.duplicate_rate:.1%}",
            dup_bar,
            f"(target: <{health_scorer.DUPLICATE_THRESHOLD:.0%})",
        )

        # Contradiction Rate
        contra_bar = get_metric_bar(
            health_score.contradiction_rate, health_scorer.CONTRADICTION_THRESHOLD
        )
        contra_status = (
            "✓"
            if health_score.contradiction_rate <= health_scorer.CONTRADICTION_THRESHOLD
            else "⚠"
        )
        metrics_table.add_row(
            f"  {contra_status} Contradiction Rate:",
            f"{health_score.contradiction_rate:.1%}",
            contra_bar,
            f"(target: <{health_scorer.CONTRADICTION_THRESHOLD:.0%})",
        )

        console.print(metrics_table)
        console.print()

        # Lifecycle Distribution
        console.print("[bold]Lifecycle Distribution:[/bold]")

        total = health_score.total_count
        if total > 0:
            dist_table = Table(show_header=False, box=None, padding=(0, 2))

            # ACTIVE
            active_pct = health_score.active_count / total
            active_bar_width = int(active_pct * 20)
            dist_table.add_row(
                "  ACTIVE (0-7d):",
                f"{health_score.active_count:4d}",
                f"({active_pct:.0%})",
                "[green]" + "█" * active_bar_width + "[/green]",
            )

            # RECENT
            recent_pct = health_score.recent_count / total
            recent_bar_width = int(recent_pct * 20)
            dist_table.add_row(
                "  RECENT (7-30d):",
                f"{health_score.recent_count:4d}",
                f"({recent_pct:.0%})",
                "[yellow]" + "█" * recent_bar_width + "[/yellow]",
            )

            # ARCHIVED
            archived_pct = health_score.archived_count / total
            archived_bar_width = int(archived_pct * 20)
            dist_table.add_row(
                "  ARCHIVED (30-180d):",
                f"{health_score.archived_count:4d}",
                f"({archived_pct:.0%})",
                "[orange1]" + "█" * archived_bar_width + "[/orange1]",
            )

            # STALE
            stale_pct = health_score.stale_count / total
            stale_bar_width = int(stale_pct * 20)
            dist_table.add_row(
                "  STALE (180d+):",
                f"{health_score.stale_count:4d}",
                f"({stale_pct:.0%})",
                "[red]" + "█" * stale_bar_width + "[/red]",
            )

            console.print(dist_table)
        else:
            console.print("  [dim]No memories found[/dim]")

        console.print()

        # Recommendations
        console.print("[bold]Recommendations:[/bold]")
        for rec in health_score.recommendations:
            console.print(f"  {rec}")

        console.print()

        # Actions
        if health_score.stale_count > 0 or health_score.overall < 75:
            console.print("[bold]Suggested Actions:[/bold]")

            if health_score.stale_count > 0:
                console.print(
                    f"  • Run [cyan]lifecycle cleanup --dry-run[/cyan] to preview cleanup of {health_score.stale_count} STALE memories"
                )

            if health_score.duplicate_rate > health_scorer.DUPLICATE_THRESHOLD:
                console.print(
                    "  • Run [cyan]consolidate --auto[/cyan] to merge duplicate memories"
                )

            if health_score.noise_ratio > health_scorer.NOISE_THRESHOLD:
                console.print(
                    "  • Run [cyan]lifecycle archive-stale[/cyan] to archive old memories"
                )

            console.print()

        # Detailed metrics (if requested)
        if detailed:
            console.print("[bold]Detailed Metrics:[/bold]")
            console.print(f"  Total Memories: {total}")
            console.print(
                f"  Distribution Score: {health_score.distribution_score:.1f}/100"
            )
            console.print(f"  Timestamp: {health_score.timestamp.isoformat()}")
            console.print()

    finally:
        await store.close()


async def lifecycle_cleanup(dry_run: bool = True, min_age_days: int = 180) -> None:
    """
    Run lifecycle cleanup job.

    Args:
        dry_run: If True, only preview the operation
        min_age_days: Minimum age for deletion
    """
    from src.memory.health_jobs import HealthMaintenanceJobs

    config = get_config()
    store = create_memory_store(config=config)
    await store.initialize()

    try:
        lifecycle_manager = LifecycleManager()
        jobs = HealthMaintenanceJobs(store, lifecycle_manager)

        if dry_run:
            console.print("[bold]DRY RUN - No changes will be made[/bold]\n")

        console.print("[dim]Running cleanup job...[/dim]\n")

        result = await jobs.monthly_cleanup_job(
            dry_run=dry_run, min_age_days=min_age_days
        )

        # Display results
        if result.success:
            console.print("[green]✓[/green] Cleanup completed successfully")
            console.print(f"  Processed: {result.memories_processed} memories")
            if dry_run:
                console.print(
                    f"  [yellow]Would delete:[/yellow] {result.memories_deleted} memories"
                )
            else:
                console.print(f"  Deleted: {result.memories_deleted} memories")

            if result.errors:
                console.print(f"  [red]Errors:[/red] {len(result.errors)}")
                for error in result.errors[:5]:
                    console.print(f"    • {error}")

        else:
            console.print("[red]✗[/red] Cleanup failed")
            for error in result.errors:
                console.print(f"  • {error}")

    finally:
        await store.close()


async def lifecycle_archive_stale() -> None:
    """Run lifecycle archival job."""
    from src.memory.health_jobs import HealthMaintenanceJobs

    config = get_config()
    store = create_memory_store(config=config)
    await store.initialize()

    try:
        lifecycle_manager = LifecycleManager()
        jobs = HealthMaintenanceJobs(store, lifecycle_manager)

        console.print("[dim]Running archival job...[/dim]\n")

        result = await jobs.weekly_archival_job(dry_run=False)

        # Display results
        if result.success:
            console.print("[green]✓[/green] Archival completed successfully")
            console.print(f"  Processed: {result.memories_processed} memories")
            console.print(f"  Archived: {result.memories_archived} memories")

            if result.errors:
                console.print(f"  [red]Errors:[/red] {len(result.errors)}")
                for error in result.errors[:5]:
                    console.print(f"    • {error}")

        else:
            console.print("[red]✗[/red] Archival failed")
            for error in result.errors:
                console.print(f"  • {error}")

    finally:
        await store.close()


def main():
    """Main entry point for health dashboard command."""
    import argparse

    parser = argparse.ArgumentParser(description="Memory System Health Dashboard")
    parser.add_argument("--detailed", action="store_true", help="Show detailed metrics")
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    asyncio.run(health_dashboard(detailed=args.detailed, json_output=args.json))


if __name__ == "__main__":
    main()
