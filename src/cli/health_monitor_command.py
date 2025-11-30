"""
Health monitoring CLI commands.

Provides commands for viewing health status, generating reports,
and applying automated fixes.
"""

import asyncio
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.layout import Layout
from rich.progress import Progress, SpinnerColumn, TextColumn
from datetime import datetime, timedelta

from src.config import get_config
from src.store.factory import create_store
from src.monitoring.metrics_collector import MetricsCollector
from src.monitoring.alert_engine import AlertEngine, AlertSeverity
from src.monitoring.health_reporter import HealthReporter, HealthStatus
from src.monitoring.remediation import RemediationEngine, RemediationTrigger
from src.memory.project_archival import ProjectArchivalManager


console = Console()


class HealthMonitorCommand:
    """Health monitoring CLI command handler."""

    def __init__(self):
        """Initialize health monitor command."""
        self.config = get_config()
        self.db_path = str(Path.home() / ".claude-rag" / "metrics.db")

    async def run(self, args):
        """
        Execute health monitor command.

        Args:
            args: Parsed command arguments
        """
        # Dispatch to appropriate subcommand
        if hasattr(args, "subcommand"):
            if args.subcommand == "status":
                await self.show_status(args)
            elif args.subcommand == "report":
                await self.show_report(args)
            elif args.subcommand == "fix":
                await self.apply_fixes(args)
            elif args.subcommand == "history":
                await self.show_history(args)
            else:
                await self.show_status(args)
        else:
            # Default: show status
            await self.show_status(args)

    async def show_status(self, args):
        """
        Show current health status with active alerts.

        Args:
            args: Parsed command arguments
        """
        console.print("\n[bold cyan]Memory Health Monitor[/bold cyan]\n")

        try:
            # Initialize components
            store = await create_store(self.config)

            # Initialize archival manager (REF-011)
            config_dir = os.path.dirname(self.db_path)
            archival_file = os.path.join(config_dir, "project_states.json")
            archival_manager = ProjectArchivalManager(
                state_file_path=archival_file,
                inactivity_threshold_days=self.config.memory.archival_threshold_days
            )

            collector = MetricsCollector(self.db_path, store, archival_manager)
            alert_engine = AlertEngine(self.db_path)
            reporter = HealthReporter()

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task("Collecting health metrics...", total=None)

                # Collect current metrics
                metrics = await collector.collect_metrics()

                progress.update(task, description="Evaluating alerts...")

                # Evaluate alerts
                alerts = alert_engine.evaluate_metrics(metrics)
                alert_engine.store_alerts(alerts)
                active_alerts = alert_engine.get_active_alerts()

                progress.update(task, description="Calculating health score...")

                # Calculate health score
                health_score = reporter.calculate_health_score(metrics, active_alerts)

            # Display health score
            self._display_health_score(health_score)

            # Display active alerts
            if active_alerts:
                self._display_alerts(active_alerts)
            else:
                console.print(
                    "\n[green]✓ No active alerts - System is healthy[/green]"
                )

            # Display key metrics
            self._display_key_metrics(metrics)

        except Exception as e:
            console.print(f"\n[red]Error: {e}[/red]")
            raise

    async def show_report(self, args):
        """
        Generate detailed weekly/monthly report.

        Args:
            args: Parsed command arguments (period)
        """
        console.print("\n[bold cyan]Health Report[/bold cyan]\n")

        try:
            # Initialize components
            store = await create_store(self.config)

            # Initialize archival manager (REF-011)
            config_dir = os.path.dirname(self.db_path)
            archival_file = os.path.join(config_dir, "project_states.json")
            archival_manager = ProjectArchivalManager(
                state_file_path=archival_file,
                inactivity_threshold_days=self.config.memory.archival_threshold_days
            )

            collector = MetricsCollector(self.db_path, store, archival_manager)
            alert_engine = AlertEngine(self.db_path)
            reporter = HealthReporter()

            # Get period
            period_days = getattr(args, "period_days", 7)

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task("Generating report...", total=None)

                # Get current and historical metrics
                current_metrics = await collector.collect_metrics()
                historical_metrics = collector.get_metrics_history(days=period_days)

                # Get current alerts
                active_alerts = alert_engine.get_active_alerts()

                # Generate report
                report = reporter.generate_weekly_report(
                    current_metrics, active_alerts, historical_metrics
                )

            # Display report
            self._display_weekly_report(report)

        except Exception as e:
            console.print(f"\n[red]Error: {e}[/red]")
            raise

    async def apply_fixes(self, args):
        """
        Apply automated remediation actions.

        Args:
            args: Parsed command arguments (auto, dry_run)
        """
        console.print("\n[bold cyan]Health Remediation[/bold cyan]\n")

        try:
            # Initialize components
            store = await create_store(self.config)
            remediation = RemediationEngine(self.db_path, store)

            dry_run = getattr(args, "dry_run", False)
            auto = getattr(args, "auto", False)

            if dry_run:
                console.print("[yellow]DRY RUN MODE - No changes will be made[/yellow]\n")

            # Get available actions
            actions = remediation.get_available_actions()

            if auto:
                # Execute all automatic actions
                console.print("Executing automatic remediation actions...\n")

                results = remediation.execute_automatic_actions(dry_run=dry_run)

                # Display results
                self._display_remediation_results(results, dry_run)
            else:
                # Show available actions and prompt user
                console.print("Available remediation actions:\n")

                table = Table(show_header=True)
                table.add_column("Action", style="cyan")
                table.add_column("Description")
                table.add_column("Automatic", justify="center")

                for i, action in enumerate(actions, 1):
                    table.add_row(
                        f"{i}. {action.name}",
                        action.description,
                        "✓" if action.automatic else "Manual",
                    )

                console.print(table)

                # Prompt user
                console.print(
                    "\n[bold]Options:[/bold]"
                    "\n  • Enter action number to execute"
                    "\n  • Enter 'all' to execute all automatic actions"
                    "\n  • Enter 'q' to quit"
                )

                choice = console.input("\n[bold cyan]Your choice:[/bold cyan] ").strip()

                if choice.lower() == "q":
                    console.print("Cancelled.")
                    return
                elif choice.lower() == "all":
                    results = remediation.execute_automatic_actions(dry_run=dry_run)
                    self._display_remediation_results(results, dry_run)
                elif choice.isdigit() and 1 <= int(choice) <= len(actions):
                    action = actions[int(choice) - 1]
                    result = remediation.execute_action(
                        action.name,
                        dry_run=dry_run,
                        triggered_by=RemediationTrigger.USER,
                    )
                    self._display_remediation_results({action.name: result}, dry_run)
                else:
                    console.print("[red]Invalid choice[/red]")

        except Exception as e:
            console.print(f"\n[red]Error: {e}[/red]")
            raise

    async def show_history(self, args):
        """
        Show historical metrics and trends.

        Args:
            args: Parsed command arguments (days)
        """
        console.print("\n[bold cyan]Health History[/bold cyan]\n")

        try:
            # Initialize components
            store = await create_store(self.config)

            # Initialize archival manager (REF-011)
            config_dir = os.path.dirname(self.db_path)
            archival_file = os.path.join(config_dir, "project_states.json")
            archival_manager = ProjectArchivalManager(
                state_file_path=archival_file,
                inactivity_threshold_days=self.config.memory.archival_threshold_days
            )

            collector = MetricsCollector(self.db_path, store, archival_manager)

            days = getattr(args, "days", 30)

            # Get historical metrics
            history = collector.get_daily_aggregate(days=days)

            if not history:
                console.print("[yellow]No historical data available[/yellow]")
                return

            # Display historical trends
            self._display_history(history)

        except Exception as e:
            console.print(f"\n[red]Error: {e}[/red]")
            raise

    def _display_health_score(self, health_score):
        """Display overall health score with status."""
        # Color based on status
        if health_score.status == HealthStatus.EXCELLENT:
            color = "green"
            emoji = "✓"
        elif health_score.status == HealthStatus.GOOD:
            color = "green"
            emoji = "✓"
        elif health_score.status == HealthStatus.FAIR:
            color = "yellow"
            emoji = "⚠"
        elif health_score.status == HealthStatus.POOR:
            color = "red"
            emoji = "⚠"
        else:  # CRITICAL
            color = "red"
            emoji = "✗"

        title = f"[{color}]{emoji} Health Score: {health_score.overall_score}/100 ({health_score.status.value})[/{color}]"

        # Component breakdown table
        table = Table(show_header=True, box=None, padding=(0, 2))
        table.add_column("Component", style="cyan")
        table.add_column("Score", justify="right")

        table.add_row("Performance", f"{health_score.performance_score}/100")
        table.add_row("Quality", f"{health_score.quality_score}/100")
        table.add_row("Database Health", f"{health_score.database_health_score}/100")
        table.add_row("Usage Efficiency", f"{health_score.usage_efficiency_score}/100")

        panel = Panel(table, title=title, border_style=color)
        console.print(panel)

    def _display_alerts(self, alerts):
        """Display active alerts."""
        console.print("\n[bold red]Active Alerts[/bold red]\n")

        for alert in alerts:
            # Color by severity
            if alert.severity == AlertSeverity.CRITICAL:
                color = "red"
                icon = "✗"
            elif alert.severity == AlertSeverity.WARNING:
                color = "yellow"
                icon = "⚠"
            else:
                color = "cyan"
                icon = "ℹ"

            console.print(f"[{color}]{icon} {alert.severity.value}:[/{color}] {alert.message}")
            console.print(f"   Metric: {alert.metric_name}")
            console.print(
                f"   Current: {alert.current_value:.2f}, "
                f"Threshold: {alert.threshold_value:.2f}"
            )

            if alert.recommendations:
                console.print("   [bold]Recommendations:[/bold]")
                for rec in alert.recommendations[:2]:  # Show top 2
                    console.print(f"     • {rec}")

            console.print()

    def _display_key_metrics(self, metrics):
        """Display key metrics summary."""
        console.print("\n[bold]Key Metrics[/bold]\n")

        table = Table(show_header=True)
        table.add_column("Metric", style="cyan")
        table.add_column("Value", justify="right")

        table.add_row("Avg Search Latency", f"{metrics.avg_search_latency_ms:.1f}ms")
        table.add_row("Avg Relevance", f"{metrics.avg_result_relevance:.2f}")
        table.add_row("Noise Ratio", f"{metrics.noise_ratio * 100:.1f}%")
        table.add_row("Cache Hit Rate", f"{metrics.cache_hit_rate * 100:.1f}%")
        table.add_row("Total Memories", f"{metrics.total_memories:,}")
        table.add_row("Active Memories", f"{metrics.active_memories:,}")
        table.add_row("Stale Memories", f"{metrics.stale_memories:,}")
        table.add_row("Database Size", f"{metrics.database_size_mb:.1f}MB")

        console.print(table)

    def _display_weekly_report(self, report):
        """Display weekly health report."""
        # Period
        console.print(
            f"[bold]Report Period:[/bold] {report.period_start.strftime('%Y-%m-%d')} "
            f"to {report.period_end.strftime('%Y-%m-%d')}\n"
        )

        # Health score
        self._display_health_score(report.current_health)

        # Improvements
        if report.improvements:
            console.print("\n[bold green]🟢 Improvements:[/bold green]")
            for improvement in report.improvements:
                console.print(f"  • {improvement}")

        # Concerns
        if report.concerns:
            console.print("\n[bold yellow]⚠️  Concerns:[/bold yellow]")
            for concern in report.concerns:
                console.print(f"  • {concern}")

        # Usage summary
        console.print("\n[bold]📊 Usage Summary:[/bold]")
        console.print(f"  • Queries per day: {report.usage_summary['queries_per_day']:.1f}")
        console.print(
            f"  • Memories created per day: {report.usage_summary['memories_created_per_day']:.1f}"
        )
        console.print(
            f"  • Avg results per query: {report.usage_summary['avg_results_per_query']:.1f}"
        )

        # Recommendations
        if report.recommendations:
            console.print("\n[bold]🎯 Recommendations:[/bold]")
            for rec in report.recommendations[:5]:  # Top 5
                console.print(f"  • {rec}")

    def _display_remediation_results(self, results, dry_run):
        """Display remediation action results."""
        console.print()

        for action_name, result in results.items():
            if result.success:
                if dry_run:
                    console.print(
                        f"[cyan]Would {action_name}:[/cyan] "
                        f"{result.items_affected} items"
                    )
                else:
                    console.print(
                        f"[green]✓ {action_name}:[/green] "
                        f"{result.items_affected} items affected"
                    )
            else:
                console.print(
                    f"[red]✗ {action_name} failed:[/red] {result.error_message}"
                )

        console.print()

    def _display_history(self, history):
        """Display historical metrics."""
        if not history:
            console.print("[yellow]No historical data[/yellow]")
            return

        table = Table(show_header=True)
        table.add_column("Date", style="cyan")
        table.add_column("Health", justify="right")
        table.add_column("Latency", justify="right")
        table.add_column("Relevance", justify="right")
        table.add_column("Noise", justify="right")
        table.add_column("Memories", justify="right")

        for metrics in history[-14:]:  # Last 14 days
            table.add_row(
                metrics.timestamp.strftime("%Y-%m-%d"),
                f"{metrics.health_score}/100",
                f"{metrics.avg_search_latency_ms:.1f}ms",
                f"{metrics.avg_result_relevance:.2f}",
                f"{metrics.noise_ratio * 100:.0f}%",
                f"{metrics.total_memories:,}",
            )

        console.print(table)
