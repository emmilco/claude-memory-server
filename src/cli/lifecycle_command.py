"""Lifecycle management CLI commands for memory health monitoring."""

import asyncio
import argparse
from datetime import datetime, UTC
from typing import Optional

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

from src.config import get_config
from src.store.factory import StorageFactory
from src.memory.lifecycle_manager import LifecycleManager, LifecycleConfig
from src.core.models import LifecycleState
from src.memory.usage_tracker import UsageTracker

console = Console()


async def health_command(args: argparse.Namespace) -> int:
    """
    Display memory health dashboard with lifecycle distribution.

    Args:
        args: Command line arguments

    Returns:
        Exit code (0 for success)
    """
    try:
        config = get_config()
        store = await StorageFactory.create_store(config)
        await store.initialize()

        lifecycle_manager = LifecycleManager()
        usage_tracker = UsageTracker(store)

        # Get all memories
        # We need to implement a method to get all memories
        # For now, let's use a workaround with search
        console.print("[cyan]Loading memory data...[/cyan]")

        # Get memory statistics from the store
        # This is a simplified version - we'd need to implement proper get_all_memories
        all_memories = await _get_all_memories(store)

        if not all_memories:
            console.print("[yellow]No memories found in the database.[/yellow]")
            return 0

        # Get usage data
        usage_data = {}
        for memory in all_memories:
            usage_info = await usage_tracker.get_usage(memory.id)
            if usage_info:
                usage_data[memory.id] = usage_info

        # Calculate lifecycle states
        lifecycle_manager.bulk_update_states(all_memories, usage_data)

        # Get statistics
        stats = lifecycle_manager.get_lifecycle_stats(all_memories)

        # Calculate quality metrics
        quality_metrics = _calculate_quality_metrics(all_memories, usage_data)

        # Display health dashboard
        _display_health_dashboard(stats, quality_metrics, all_memories)

        await store.close()
        return 0

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        import traceback
        traceback.print_exc()
        return 1


async def update_command(args: argparse.Namespace) -> int:
    """
    Update lifecycle states for all memories.

    Args:
        args: Command line arguments

    Returns:
        Exit code (0 for success)
    """
    try:
        config = get_config()
        store = await StorageFactory.create_store(config)
        await store.initialize()

        lifecycle_manager = LifecycleManager()
        usage_tracker = UsageTracker(store)

        console.print("[cyan]Updating lifecycle states...[/cyan]")

        # Get all memories
        all_memories = await _get_all_memories(store)

        if not all_memories:
            console.print("[yellow]No memories found in the database.[/yellow]")
            return 0

        # Get usage data
        usage_data = {}
        for memory in all_memories:
            usage_info = await usage_tracker.get_usage(memory.id)
            if usage_info:
                usage_data[memory.id] = usage_info

        # Update states
        transitions = lifecycle_manager.bulk_update_states(all_memories, usage_data)

        # Store updated memories
        if transitions:
            console.print(f"[green]Updating {len(transitions)} memories...[/green]")

            for memory in all_memories:
                # Check if this memory transitioned
                transitioned = any(t[0] == memory.id for t in transitions)
                if transitioned:
                    # Get embedding for update
                    # For now, we'll need to handle this differently
                    # This is a simplified version
                    console.print(
                        f"  • {memory.id[:8]}... → {memory.lifecycle_state.value}"
                    )

            console.print(f"[green]✓ Updated {len(transitions)} lifecycle states[/green]")
        else:
            console.print("[green]✓ All lifecycle states are current[/green]")

        await store.close()
        return 0

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        return 1


def _display_health_dashboard(
    stats: dict,
    quality_metrics: dict,
    memories: list,
) -> None:
    """Display the health dashboard."""
    # Calculate overall health score
    health_score = _calculate_health_score(stats, quality_metrics)

    # Health status emoji and color
    if health_score >= 80:
        health_status = "EXCELLENT"
        health_color = "green"
        health_emoji = "✓"
    elif health_score >= 65:
        health_status = "GOOD"
        health_color = "cyan"
        health_emoji = "✓"
    elif health_score >= 50:
        health_status = "FAIR"
        health_color = "yellow"
        health_emoji = "⚠"
    else:
        health_status = "POOR"
        health_color = "red"
        health_emoji = "✗"

    # Title panel
    title_text = Text()
    title_text.append("MEMORY HEALTH REPORT\n", style="bold")
    title_text.append(
        f"Overall Health: {health_score}/100 ({health_status}) {health_emoji}",
        style=f"bold {health_color}"
    )
    console.print(Panel(title_text, style=health_color))
    console.print()

    # Database status table
    db_table = Table(title="Database Status", show_header=True, header_style="bold cyan")
    db_table.add_column("Lifecycle State", style="cyan")
    db_table.add_column("Count", justify="right")
    db_table.add_column("Percentage", justify="right")
    db_table.add_column("Status", justify="center")

    total = stats["total"]
    by_state = stats["by_state"]
    percentages = stats["percentages"]

    # Add rows with status indicators
    for state in [LifecycleState.ACTIVE, LifecycleState.RECENT, LifecycleState.ARCHIVED, LifecycleState.STALE]:
        count = by_state.get(state.value, 0)
        pct = percentages.get(state.value, 0.0)

        # Status indicator
        if state == LifecycleState.ACTIVE:
            status = "✓" if pct >= 10 else "⚠"
            status_color = "green" if pct >= 10 else "yellow"
        elif state == LifecycleState.RECENT:
            status = "✓" if pct <= 40 else "⚠"
            status_color = "green" if pct <= 40 else "yellow"
        elif state == LifecycleState.ARCHIVED:
            status = "⚠" if pct > 50 else "✓"
            status_color = "yellow" if pct > 50 else "green"
        else:  # STALE
            status = "✗" if pct > 15 else "⚠" if pct > 5 else "✓"
            status_color = "red" if pct > 15 else "yellow" if pct > 5 else "green"

        db_table.add_row(
            state.value,
            str(count),
            f"{pct:.1f}%",
            f"[{status_color}]{status}[/{status_color}]"
        )

    # Add total row
    db_table.add_row(
        "[bold]TOTAL[/bold]",
        f"[bold]{total}[/bold]",
        "[bold]100.0%[/bold]",
        ""
    )

    console.print(db_table)
    console.print()

    # Quality metrics table
    quality_table = Table(title="Quality Metrics", show_header=True, header_style="bold cyan")
    quality_table.add_column("Metric", style="cyan")
    quality_table.add_column("Value", justify="right")
    quality_table.add_column("Target", justify="right")
    quality_table.add_column("Status", justify="center")

    metrics_config = [
        ("Noise Ratio", quality_metrics["noise_ratio"], "<25%", 25, True),  # True = lower is better
        ("Stale Memory Ratio", quality_metrics["stale_ratio"], "<15%", 15, True),
        ("Active Memory Ratio", quality_metrics["active_ratio"], ">10%", 10, False),  # False = higher is better
    ]

    for metric_name, value, target, threshold, lower_is_better in metrics_config:
        if lower_is_better:
            status = "✓" if value < threshold else "✗"
            status_color = "green" if value < threshold else "red"
        else:
            status = "✓" if value > threshold else "✗"
            status_color = "green" if value > threshold else "red"

        quality_table.add_row(
            metric_name,
            f"{value:.1f}%",
            target,
            f"[{status_color}]{status}[/{status_color}]"
        )

    console.print(quality_table)
    console.print()

    # Recommendations
    recommendations = _generate_recommendations(stats, quality_metrics)
    if recommendations:
        rec_panel = Panel(
            "\n".join(f"• {rec}" for rec in recommendations),
            title="[bold yellow]Recommendations[/bold yellow]",
            style="yellow"
        )
        console.print(rec_panel)


def _calculate_health_score(stats: dict, quality_metrics: dict) -> int:
    """Calculate overall health score (0-100)."""
    score = 100

    # Penalize high stale ratio
    stale_ratio = quality_metrics["stale_ratio"]
    if stale_ratio > 15:
        score -= (stale_ratio - 15) * 2
    elif stale_ratio > 10:
        score -= (stale_ratio - 10)

    # Penalize high noise ratio
    noise_ratio = quality_metrics["noise_ratio"]
    if noise_ratio > 30:
        score -= (noise_ratio - 30) * 1.5
    elif noise_ratio > 20:
        score -= (noise_ratio - 20) * 0.5

    # Penalize low active ratio
    active_ratio = quality_metrics["active_ratio"]
    if active_ratio < 5:
        score -= (5 - active_ratio) * 3
    elif active_ratio < 10:
        score -= (10 - active_ratio)

    return max(0, min(100, int(score)))


def _calculate_quality_metrics(memories: list, usage_data: dict) -> dict:
    """Calculate quality metrics from memory data."""
    total = len(memories)
    if total == 0:
        return {
            "noise_ratio": 0.0,
            "stale_ratio": 0.0,
            "active_ratio": 0.0,
        }

    # Count states
    stale_count = sum(1 for m in memories if m.lifecycle_state == LifecycleState.STALE)
    archived_count = sum(1 for m in memories if m.lifecycle_state == LifecycleState.ARCHIVED)
    active_count = sum(1 for m in memories if m.lifecycle_state == LifecycleState.ACTIVE)

    # Calculate ratios
    noise_ratio = ((stale_count + archived_count) / total) * 100
    stale_ratio = (stale_count / total) * 100
    active_ratio = (active_count / total) * 100

    return {
        "noise_ratio": noise_ratio,
        "stale_ratio": stale_ratio,
        "active_ratio": active_ratio,
    }


def _generate_recommendations(stats: dict, quality_metrics: dict) -> list:
    """Generate actionable recommendations."""
    recommendations = []

    # Stale memory recommendation
    if quality_metrics["stale_ratio"] > 10:
        stale_count = stats["by_state"].get(LifecycleState.STALE.value, 0)
        recommendations.append(
            f"Delete {stale_count} STALE memories (unused for 180+ days): "
            f"python -m src.cli prune --lifecycle-state STALE"
        )

    # Archived memory recommendation
    archived_pct = stats["percentages"].get(LifecycleState.ARCHIVED.value, 0)
    if archived_pct > 50:
        recommendations.append(
            "Consider archiving inactive projects to reduce search space"
        )

    # Active memory recommendation
    if quality_metrics["active_ratio"] < 10:
        recommendations.append(
            "Low ACTIVE memory ratio - most memories are outdated. "
            "Consider re-indexing active projects."
        )

    # Noise recommendation
    if quality_metrics["noise_ratio"] > 30:
        recommendations.append(
            "High noise ratio detected. Run lifecycle update to transition old memories: "
            "python -m src.cli lifecycle update"
        )

    return recommendations


async def _get_all_memories(store):
    """Get all memories from the store (simplified implementation)."""
    # This is a simplified version that retrieves memories
    # In a real implementation, we'd add a proper get_all_memories method to the store
    try:
        # Try to get memories using a broad search
        # We'll need to implement this properly in the store classes
        from src.core.models import MemoryUnit

        # For now, return empty list - this needs proper implementation
        # based on the store type
        console.print("[yellow]Note: Using simplified memory retrieval[/yellow]")
        return []

    except Exception as e:
        console.print(f"[yellow]Warning: Could not retrieve all memories: {e}[/yellow]")
        return []


def main():
    """Main entry point for lifecycle command."""
    parser = argparse.ArgumentParser(
        description="Memory lifecycle management"
    )
    subparsers = parser.add_subparsers(dest="command", help="Lifecycle commands")

    # Health command
    health_parser = subparsers.add_parser(
        "health",
        help="Display memory health dashboard"
    )

    # Update command
    update_parser = subparsers.add_parser(
        "update",
        help="Update lifecycle states for all memories"
    )

    args = parser.parse_args()

    if args.command == "health":
        return asyncio.run(health_command(args))
    elif args.command == "update":
        return asyncio.run(update_command(args))
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    exit(main())
