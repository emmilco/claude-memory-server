"""Performance regression detection CLI commands."""

import asyncio
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.progress import Progress, SpinnerColumn, TextColumn
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

from src.monitoring.performance_tracker import (
    PerformanceTracker,
    PerformanceMetric,
    RegressionSeverity,
)
from src.config import get_config

logger = logging.getLogger(__name__)


class PerfCommand:
    """Performance regression detection commands."""

    def __init__(self):
        """Initialize performance command."""
        self.console = Console() if RICH_AVAILABLE else None
        config = get_config()

        # Performance metrics database
        metrics_dir = Path.home() / ".cache" / "claude-memory" / "metrics"
        metrics_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = str(metrics_dir / "performance.db")

        self.tracker = PerformanceTracker(self.db_path)

    def print_section(self, title: str):
        """Print section header."""
        if self.console:
            self.console.print(f"\n[bold cyan]{title}[/bold cyan]")
        else:
            print(f"\n{title}")
            print("=" * len(title))

    def print_metric(self, name: str, current: float, baseline: Optional[float], unit: str):
        """Print metric comparison."""
        if baseline is None:
            if self.console:
                self.console.print(f"  {name:30s} [yellow]{current:.2f}{unit}[/yellow] (no baseline)")
            else:
                print(f"  {name:30s} {current:.2f}{unit} (no baseline)")
            return

        # Calculate change
        if "latency" in name.lower():
            # For latency, higher is worse
            change_percent = ((current - baseline) / baseline) * 100
        else:
            # For throughput/hit rate, lower is worse
            change_percent = ((baseline - current) / baseline) * 100

        # Color code based on change
        if change_percent > 10:
            color = "red"
            symbol = "↑" if "latency" in name.lower() else "↓"
        elif change_percent < -10:
            color = "green"
            symbol = "↓" if "latency" in name.lower() else "↑"
        else:
            color = "yellow"
            symbol = "→"

        if self.console:
            self.console.print(
                f"  {name:30s} [{color}]{current:.2f}{unit}[/{color}] "
                f"(baseline: {baseline:.2f}{unit}, {symbol} {abs(change_percent):.1f}%)"
            )
        else:
            print(
                f"  {name:30s} {current:.2f}{unit} "
                f"(baseline: {baseline:.2f}{unit}, {symbol} {abs(change_percent):.1f}%)"
            )

    def print_regression(self, regression):
        """Print regression details."""
        # Severity color
        severity_colors = {
            RegressionSeverity.MINOR: "yellow",
            RegressionSeverity.MODERATE: "yellow",
            RegressionSeverity.SEVERE: "red",
            RegressionSeverity.CRITICAL: "red bold",
        }
        color = severity_colors.get(regression.severity, "yellow")

        if self.console:
            self.console.print(
                f"\n  [{color}]{regression.severity.value} REGRESSION[/{color}]: "
                f"{regression.metric.value}"
            )
            self.console.print(
                f"    Current: {regression.current_value:.2f} | "
                f"Baseline: {regression.baseline_value:.2f} | "
                f"Degradation: {regression.degradation_percent:.1f}%"
            )
            self.console.print(f"\n  [bold]Recommendations:[/bold]")
            for i, rec in enumerate(regression.recommendations, 1):
                self.console.print(f"    {i}. {rec}")
        else:
            print(
                f"\n  {regression.severity.value} REGRESSION: {regression.metric.value}"
            )
            print(
                f"    Current: {regression.current_value:.2f} | "
                f"Baseline: {regression.baseline_value:.2f} | "
                f"Degradation: {regression.degradation_percent:.1f}%"
            )
            print(f"\n  Recommendations:")
            for i, rec in enumerate(regression.recommendations, 1):
                print(f"    {i}. {rec}")

    async def run_report(self, period_days: int = 7) -> int:
        """
        Generate performance regression report.

        Args:
            period_days: Number of days to analyze

        Returns:
            Exit code (0 = success, 1 = regressions detected)
        """
        try:
            self.print_section("Performance Regression Report")

            if self.console:
                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    console=self.console,
                ) as progress:
                    task = progress.add_task("Analyzing performance metrics...", total=None)
                    report = self.tracker.generate_report(period_days)
                    progress.update(task, completed=True)
            else:
                print("Analyzing performance metrics...")
                report = self.tracker.generate_report(period_days)

            # Print summary
            self.print_section(f"Report Summary (Last {period_days} days)")

            if self.console:
                status_color = "red" if report.has_regressions else "green"
                self.console.print(
                    f"  Status: [{status_color}]{'REGRESSIONS DETECTED' if report.has_regressions else 'HEALTHY'}[/{status_color}]"
                )
                if report.has_regressions:
                    self.console.print(
                        f"  Total Regressions: [yellow]{report.total_regressions}[/yellow]"
                    )
                    self.console.print(
                        f"  Worst Severity: [{severity_colors.get(report.worst_severity, 'yellow')}]{report.worst_severity.value}[/{severity_colors.get(report.worst_severity, 'yellow')}]"
                    )
            else:
                print(f"  Status: {'REGRESSIONS DETECTED' if report.has_regressions else 'HEALTHY'}")
                if report.has_regressions:
                    print(f"  Total Regressions: {report.total_regressions}")
                    print(f"  Worst Severity: {report.worst_severity.value}")

            # Print current metrics vs baselines
            self.print_section("Current Metrics vs Baseline")

            metric_display = {
                PerformanceMetric.SEARCH_LATENCY_P50: ("Search Latency (P50)", "ms"),
                PerformanceMetric.SEARCH_LATENCY_P95: ("Search Latency (P95)", "ms"),
                PerformanceMetric.SEARCH_LATENCY_P99: ("Search Latency (P99)", "ms"),
                PerformanceMetric.INDEXING_THROUGHPUT: ("Indexing Throughput", " files/sec"),
                PerformanceMetric.CACHE_HIT_RATE: ("Cache Hit Rate", "%"),
            }

            for metric, (display_name, unit) in metric_display.items():
                current = report.current_metrics.get(metric)
                baseline = report.baselines.get(metric)

                if current is not None:
                    baseline_value = baseline.mean if baseline else None

                    # Adjust cache hit rate display (0.0-1.0 -> 0-100%)
                    if metric == PerformanceMetric.CACHE_HIT_RATE:
                        current = current * 100
                        baseline_value = baseline_value * 100 if baseline_value is not None else None

                    self.print_metric(display_name, current, baseline_value, unit)
                else:
                    if self.console:
                        self.console.print(f"  {display_name:30s} [dim]No data[/dim]")
                    else:
                        print(f"  {display_name:30s} No data")

            # Print regressions
            if report.regressions:
                self.print_section("Detected Regressions")

                for regression in report.regressions:
                    self.print_regression(regression)

                # Print summary advice
                if self.console:
                    self.console.print(
                        f"\n[yellow]⚠ Found {len(report.regressions)} performance regression(s).[/yellow]"
                    )
                    self.console.print(
                        "[dim]Run specific fixes or review recommendations above.[/dim]"
                    )
                else:
                    print(f"\n⚠ Found {len(report.regressions)} performance regression(s).")
                    print("Run specific fixes or review recommendations above.")

                return 1  # Exit code 1 indicates regressions found
            else:
                if self.console:
                    self.console.print(
                        f"\n[green]✓ No performance regressions detected.[/green]"
                    )
                else:
                    print(f"\n✓ No performance regressions detected.")

                return 0

        except Exception as e:
            logger.error(f"Failed to generate performance report: {e}", exc_info=True)
            if self.console:
                self.console.print(f"[red]Error: {e}[/red]")
            else:
                print(f"Error: {e}")
            return 1

    async def run_history(self, metric: Optional[str] = None, days: int = 30) -> int:
        """
        Show historical performance metrics.

        Args:
            metric: Specific metric to show (or None for all)
            days: Number of days of history

        Returns:
            Exit code (0 = success, 1 = error)
        """
        try:
            self.print_section(f"Performance Metrics History (Last {days} days)")

            # Determine which metrics to show
            if metric:
                try:
                    metrics_to_show = [PerformanceMetric(metric)]
                except ValueError:
                    if self.console:
                        self.console.print(
                            f"[red]Invalid metric: {metric}[/red]\n"
                            f"Valid metrics: {', '.join(m.value for m in PerformanceMetric)}"
                        )
                    else:
                        print(
                            f"Invalid metric: {metric}\n"
                            f"Valid metrics: {', '.join(m.value for m in PerformanceMetric)}"
                        )
                    return 1
            else:
                metrics_to_show = list(PerformanceMetric)

            # Display history for each metric
            for perf_metric in metrics_to_show:
                history = self.tracker.get_metric_history(perf_metric, days)
                baseline = self.tracker.get_baseline(perf_metric)

                if not history:
                    if self.console:
                        self.console.print(
                            f"\n[yellow]{perf_metric.value}:[/yellow] [dim]No data[/dim]"
                        )
                    else:
                        print(f"\n{perf_metric.value}: No data")
                    continue

                # Create table
                if self.console:
                    table = Table(title=perf_metric.value)
                    table.add_column("Date", style="cyan")
                    table.add_column("Value", style="yellow")
                    table.add_column("vs Baseline", style="green")

                    for timestamp, value in history[-10:]:  # Last 10 data points
                        date_str = timestamp.strftime("%Y-%m-%d %H:%M")
                        value_str = f"{value:.2f}"

                        if baseline:
                            diff = value - baseline.mean
                            diff_pct = (diff / baseline.mean) * 100
                            baseline_str = f"{diff:+.2f} ({diff_pct:+.1f}%)"
                        else:
                            baseline_str = "N/A"

                        table.add_row(date_str, value_str, baseline_str)

                    self.console.print(table)

                    # Print baseline info
                    if baseline:
                        self.console.print(
                            f"  [dim]Baseline (30d avg): {baseline.mean:.2f} "
                            f"(±{baseline.stddev:.2f}, n={baseline.sample_count})[/dim]"
                        )
                else:
                    print(f"\n{perf_metric.value}:")
                    print(f"{'Date':<20} {'Value':<12} {'vs Baseline'}")
                    print("-" * 50)

                    for timestamp, value in history[-10:]:  # Last 10 data points
                        date_str = timestamp.strftime("%Y-%m-%d %H:%M")
                        value_str = f"{value:.2f}"

                        if baseline:
                            diff = value - baseline.mean
                            diff_pct = (diff / baseline.mean) * 100
                            baseline_str = f"{diff:+.2f} ({diff_pct:+.1f}%)"
                        else:
                            baseline_str = "N/A"

                        print(f"{date_str:<20} {value_str:<12} {baseline_str}")

                    # Print baseline info
                    if baseline:
                        print(
                            f"  Baseline (30d avg): {baseline.mean:.2f} "
                            f"(±{baseline.stddev:.2f}, n={baseline.sample_count})"
                        )

            # Show regression history
            self.print_section("Recent Regressions")

            regressions = self.tracker.get_regression_history(days)

            if not regressions:
                if self.console:
                    self.console.print("[green]No regressions detected in this period.[/green]")
                else:
                    print("No regressions detected in this period.")
            else:
                for regression in regressions[:5]:  # Show last 5
                    severity_colors = {
                        RegressionSeverity.MINOR: "yellow",
                        RegressionSeverity.MODERATE: "yellow",
                        RegressionSeverity.SEVERE: "red",
                        RegressionSeverity.CRITICAL: "red bold",
                    }
                    color = severity_colors.get(regression.severity, "yellow")

                    date_str = regression.detected_at.strftime("%Y-%m-%d %H:%M")

                    if self.console:
                        self.console.print(
                            f"  [{color}]{regression.severity.value}[/{color}] "
                            f"{regression.metric.value} on {date_str} "
                            f"({regression.degradation_percent:+.1f}%)"
                        )
                    else:
                        print(
                            f"  {regression.severity.value} {regression.metric.value} "
                            f"on {date_str} ({regression.degradation_percent:+.1f}%)"
                        )

            return 0

        except Exception as e:
            logger.error(f"Failed to show performance history: {e}", exc_info=True)
            if self.console:
                self.console.print(f"[red]Error: {e}[/red]")
            else:
                print(f"Error: {e}")
            return 1


async def perf_report_command(period_days: int = 7) -> int:
    """
    CLI entry point for perf-report command.

    Args:
        period_days: Number of days to analyze

    Returns:
        Exit code
    """
    cmd = PerfCommand()
    return await cmd.run_report(period_days)


async def perf_history_command(metric: Optional[str] = None, days: int = 30) -> int:
    """
    CLI entry point for perf-history command.

    Args:
        metric: Specific metric to show
        days: Number of days of history

    Returns:
        Exit code
    """
    cmd = PerfCommand()
    return await cmd.run_history(metric, days)
