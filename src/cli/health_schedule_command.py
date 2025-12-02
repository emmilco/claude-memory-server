"""CLI commands for managing health job schedules."""

import asyncio
import logging
import sys

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.memory.health_scheduler import HealthJobScheduler, HealthScheduleConfig
from src.config import get_config

logger = logging.getLogger(__name__)
console = Console()


async def health_schedule_enable() -> int:
    """
    Enable automated health maintenance jobs.

    Returns:
        Exit code
    """
    try:
        config = get_config()
        schedule_config_path = config.data_dir / "health_schedule.json"

        # Create default schedule configuration
        schedule_config = HealthScheduleConfig(
            enabled=True,
            weekly_archival_enabled=True,
            weekly_archival_day=6,  # Sunday
            weekly_archival_time="01:00",
            weekly_archival_threshold_days=90,
            monthly_cleanup_enabled=True,
            monthly_cleanup_day=1,  # 1st of month
            monthly_cleanup_time="02:00",
            monthly_cleanup_threshold_days=180,
            weekly_report_enabled=True,
            weekly_report_day=0,  # Monday
            weekly_report_time="09:00",
        )

        # Save configuration
        HealthJobScheduler.save_config_to_file(schedule_config, schedule_config_path)

        console.print()
        console.print(
            Panel.fit(
                "[bold green]Health Maintenance Schedule Enabled[/bold green]\n\n"
                "[cyan]Weekly Archival:[/cyan] Sundays at 01:00 (memories older than 90 days)\n"
                "[cyan]Monthly Cleanup:[/cyan] 1st of month at 02:00 (stale memories older than 180 days)\n"
                "[cyan]Weekly Reports:[/cyan] Mondays at 09:00\n",
                border_style="green",
            )
        )
        console.print()
        console.print(
            "[yellow]Note:[/yellow] Jobs will start automatically when the MCP server runs."
        )
        console.print(
            "[yellow]To start immediately:[/yellow] python -m src.mcp_server\n"
        )
        console.print(
            "[dim]Tip: Use 'health-schedule status' to see next run times[/dim]\n"
        )

        return 0

    except Exception as e:
        console.print(f"\n[bold red]Error:[/bold red] {e}\n")
        logger.error(f"Failed to enable health schedule: {e}", exc_info=True)
        return 1


async def health_schedule_disable() -> int:
    """
    Disable automated health maintenance jobs.

    Returns:
        Exit code
    """
    try:
        config = get_config()
        schedule_config_path = config.data_dir / "health_schedule.json"

        if not schedule_config_path.exists():
            console.print("\n[yellow]Health schedule is not configured.[/yellow]\n")
            return 0

        # Load and disable
        schedule_config = HealthJobScheduler.load_config_from_file(schedule_config_path)
        schedule_config.enabled = False

        # Save configuration
        HealthJobScheduler.save_config_to_file(schedule_config, schedule_config_path)

        console.print()
        console.print(
            Panel.fit(
                "[bold yellow]Health Maintenance Schedule Disabled[/bold yellow]\n\n"
                "Automated health jobs will no longer run.",
                border_style="yellow",
            )
        )
        console.print()

        return 0

    except Exception as e:
        console.print(f"\n[bold red]Error:[/bold red] {e}\n")
        logger.error(f"Failed to disable health schedule: {e}", exc_info=True)
        return 1


async def health_schedule_status() -> int:
    """
    Show health maintenance schedule status.

    Returns:
        Exit code
    """
    try:
        config = get_config()
        schedule_config_path = config.data_dir / "health_schedule.json"

        if not schedule_config_path.exists():
            console.print()
            console.print(
                Panel.fit(
                    "[bold yellow]No Health Schedule Configured[/bold yellow]\n\n"
                    "Run [cyan]health-schedule enable[/cyan] to set up automated health maintenance.",
                    border_style="yellow",
                )
            )
            console.print()
            return 0

        # Load configuration
        schedule_config = HealthJobScheduler.load_config_from_file(schedule_config_path)

        # Create status table
        table = Table(title="Health Maintenance Schedule", show_header=True)
        table.add_column("Job", style="cyan", width=25)
        table.add_column("Status", style="white", width=15)
        table.add_column("Schedule", style="white")

        status_emoji = "✅" if schedule_config.enabled else "❌"
        overall_status = (
            f"{status_emoji} {'Enabled' if schedule_config.enabled else 'Disabled'}"
        )

        # Weekly archival
        archival_status = (
            "✅ Enabled" if schedule_config.weekly_archival_enabled else "❌ Disabled"
        )
        archival_schedule = (
            f"Sundays at {schedule_config.weekly_archival_time}\n"
            f"(memories older than {schedule_config.weekly_archival_threshold_days} days)"
        )
        table.add_row("Weekly Archival", archival_status, archival_schedule)

        # Monthly cleanup
        cleanup_status = (
            "✅ Enabled" if schedule_config.monthly_cleanup_enabled else "❌ Disabled"
        )
        cleanup_schedule = (
            f"Day {schedule_config.monthly_cleanup_day} at {schedule_config.monthly_cleanup_time}\n"
            f"(stale memories older than {schedule_config.monthly_cleanup_threshold_days} days)"
        )
        table.add_row("Monthly Cleanup", cleanup_status, cleanup_schedule)

        # Weekly report
        report_status = (
            "✅ Enabled" if schedule_config.weekly_report_enabled else "❌ Disabled"
        )
        days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        report_schedule = f"{days[schedule_config.weekly_report_day]}s at {schedule_config.weekly_report_time}"
        table.add_row("Weekly Health Report", report_status, report_schedule)

        console.print()
        console.print(f"[bold]Overall Status:[/bold] {overall_status}\n")
        console.print(table)
        console.print()

        if schedule_config.enabled:
            console.print(
                "[green]→[/green] Automated health jobs are enabled and will run when the MCP server is active.\n"
            )
        else:
            console.print(
                "[yellow]→[/yellow] Automated health jobs are disabled. "
                "Run [cyan]health-schedule enable[/cyan] to activate.\n"
            )

        return 0

    except Exception as e:
        console.print(f"\n[bold red]Error:[/bold red] {e}\n")
        logger.error(f"Failed to get health schedule status: {e}", exc_info=True)
        return 1


async def health_schedule_test(job: str = "all") -> int:
    """
    Test health jobs by running them immediately.

    Args:
        job: Which job to test (archival, cleanup, report, all)

    Returns:
        Exit code
    """
    try:
        config = get_config()
        schedule_config_path = config.data_dir / "health_schedule.json"

        if not schedule_config_path.exists():
            console.print(
                "\n[bold red]Error:[/bold red] No health schedule configured.\n"
            )
            console.print("Run [cyan]health-schedule enable[/cyan] first.\n")
            return 1

        # Load configuration
        schedule_config = HealthJobScheduler.load_config_from_file(schedule_config_path)

        console.print("\n[bold blue]Testing Health Maintenance Jobs[/bold blue]\n")

        # Create scheduler
        scheduler = HealthJobScheduler(schedule_config)
        await scheduler.start()

        results = []

        try:
            if job in ["archival", "all"]:
                console.print("[cyan]Running weekly archival (dry-run)...[/cyan]")
                result = await scheduler.trigger_archival_now(dry_run=True)
                results.append(("Archival", result))
                console.print(
                    f"  → Would archive {result.memories_archived} memories\n"
                )

            if job in ["cleanup", "all"]:
                console.print("[cyan]Running monthly cleanup (dry-run)...[/cyan]")
                result = await scheduler.trigger_cleanup_now(dry_run=True)
                results.append(("Cleanup", result))
                console.print(
                    f"  → Would delete {result.memories_deleted} stale memories\n"
                )

            if job in ["report", "all"]:
                console.print("[cyan]Generating weekly health report...[/cyan]")
                result = await scheduler.trigger_report_now()
                results.append(("Report", result))
                console.print("  → Report generated successfully\n")

        finally:
            await scheduler.stop()

        # Summary
        all_success = all(r[1].success for r in results)

        if all_success:
            console.print(
                Panel.fit(
                    "[bold green]Test Successful[/bold green]\n\n"
                    "All health jobs completed without errors.",
                    border_style="green",
                )
            )
            console.print()
            return 0
        else:
            console.print(
                Panel.fit(
                    "[bold red]Test Failed[/bold red]\n\n"
                    "Some jobs encountered errors. Check logs for details.",
                    border_style="red",
                )
            )
            console.print()
            return 1

    except Exception as e:
        console.print(f"\n[bold red]Error:[/bold red] {e}\n")
        logger.error(f"Test health jobs failed: {e}", exc_info=True)
        return 1


def main():
    """Main entry point for health schedule commands."""
    import argparse

    parser = argparse.ArgumentParser(description="Manage health maintenance schedules")
    subparsers = parser.add_subparsers(dest="command", help="Schedule command")

    # Enable command
    subparsers.add_parser("enable", help="Enable health maintenance schedule")

    # Disable command
    subparsers.add_parser("disable", help="Disable health maintenance schedule")

    # Status command
    subparsers.add_parser("status", help="Show schedule status")

    # Test command
    test_parser = subparsers.add_parser("test", help="Test health jobs")
    test_parser.add_argument(
        "--job",
        choices=["archival", "cleanup", "report", "all"],
        default="all",
        help="Which job to test",
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    # Execute command
    if args.command == "enable":
        return asyncio.run(health_schedule_enable())
    elif args.command == "disable":
        return asyncio.run(health_schedule_disable())
    elif args.command == "status":
        return asyncio.run(health_schedule_status())
    elif args.command == "test":
        return asyncio.run(health_schedule_test(args.job))


if __name__ == "__main__":
    sys.exit(main())
