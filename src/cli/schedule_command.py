"""CLI commands for managing backup schedules."""

import asyncio
import logging
from pathlib import Path
from typing import Optional
import sys

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.backup.scheduler import BackupScheduler, BackupScheduleConfig
from src.config import get_config

logger = logging.getLogger(__name__)
console = Console()


async def schedule_enable(
    frequency: str = "daily",
    time: str = "02:00",
    retention_days: int = 30,
    max_backups: int = 10,
    format: str = "archive",
) -> int:
    """
    Enable automated backup scheduling.

    Args:
        frequency: Backup frequency (hourly, daily, weekly, monthly)
        time: Time for backup (HH:MM format, for daily/weekly/monthly)
        retention_days: Keep backups for N days
        max_backups: Maximum number of backups to keep
        format: Backup format (archive or json)

    Returns:
        Exit code
    """
    try:
        config = get_config()
        schedule_config_path = config.data_dir / "backup_schedule.json"

        # Create schedule configuration
        schedule_config = BackupScheduleConfig(
            enabled=True,
            frequency=frequency,
            time=time,
            retention_days=retention_days,
            max_backups=max_backups,
            backup_format=format,
        )

        # Save configuration
        BackupScheduler.save_config_to_file(schedule_config, schedule_config_path)

        console.print()
        console.print(
            Panel.fit(
                f"[bold green]Backup Schedule Enabled[/bold green]\n\n"
                f"[cyan]Frequency:[/cyan] {frequency}\n"
                f"[cyan]Time:[/cyan] {time}\n"
                f"[cyan]Retention:[/cyan] {retention_days} days\n"
                f"[cyan]Max Backups:[/cyan] {max_backups}\n"
                f"[cyan]Format:[/cyan] {format}",
                border_style="green",
            )
        )
        console.print()
        console.print(
            "[yellow]Note:[/yellow] Scheduler will start automatically when the MCP server runs."
        )
        console.print(
            "[yellow]To start it immediately:[/yellow] python -m src.mcp_server\n"
        )

        return 0

    except Exception as e:
        console.print(f"\n[bold red]Error:[/bold red] {e}\n")
        logger.error(f"Failed to enable backup schedule: {e}", exc_info=True)
        return 1


async def schedule_disable() -> int:
    """
    Disable automated backup scheduling.

    Returns:
        Exit code
    """
    try:
        config = get_config()
        schedule_config_path = config.data_dir / "backup_schedule.json"

        if not schedule_config_path.exists():
            console.print("\n[yellow]Backup schedule is not configured.[/yellow]\n")
            return 0

        # Load and disable
        schedule_config = BackupScheduler.load_config_from_file(schedule_config_path)
        schedule_config.enabled = False

        # Save configuration
        BackupScheduler.save_config_to_file(schedule_config, schedule_config_path)

        console.print()
        console.print(
            Panel.fit(
                "[bold yellow]Backup Schedule Disabled[/bold yellow]\n\n"
                "Automated backups will no longer run.",
                border_style="yellow",
            )
        )
        console.print()

        return 0

    except Exception as e:
        console.print(f"\n[bold red]Error:[/bold red] {e}\n")
        logger.error(f"Failed to disable backup schedule: {e}", exc_info=True)
        return 1


async def schedule_status() -> int:
    """
    Show backup schedule status.

    Returns:
        Exit code
    """
    try:
        config = get_config()
        schedule_config_path = config.data_dir / "backup_schedule.json"

        if not schedule_config_path.exists():
            console.print()
            console.print(
                Panel.fit(
                    "[bold yellow]No Backup Schedule Configured[/bold yellow]\n\n"
                    "Run [cyan]schedule enable[/cyan] to set up automated backups.",
                    border_style="yellow",
                )
            )
            console.print()
            return 0

        # Load configuration
        schedule_config = BackupScheduler.load_config_from_file(schedule_config_path)

        # Create status table
        table = Table(title="Backup Schedule Status", show_header=True)
        table.add_column("Setting", style="cyan", width=20)
        table.add_column("Value", style="white")

        status_emoji = "✅" if schedule_config.enabled else "❌"
        table.add_row("Status", f"{status_emoji} {'Enabled' if schedule_config.enabled else 'Disabled'}")
        table.add_row("Frequency", schedule_config.frequency)
        table.add_row("Time", schedule_config.time)
        table.add_row("Retention", f"{schedule_config.retention_days} days")
        table.add_row("Max Backups", str(schedule_config.max_backups))
        table.add_row("Format", schedule_config.backup_format)

        if schedule_config.backup_dir:
            table.add_row("Backup Directory", schedule_config.backup_dir)
        else:
            table.add_row("Backup Directory", str(config.data_dir / "backups"))

        console.print()
        console.print(table)
        console.print()

        if schedule_config.enabled:
            console.print(
                "[green]→[/green] Automated backups are enabled and will run when the MCP server is active.\n"
            )
        else:
            console.print(
                "[yellow]→[/yellow] Automated backups are disabled. "
                "Run [cyan]schedule enable[/cyan] to activate.\n"
            )

        return 0

    except Exception as e:
        console.print(f"\n[bold red]Error:[/bold red] {e}\n")
        logger.error(f"Failed to get schedule status: {e}", exc_info=True)
        return 1


async def schedule_test() -> int:
    """
    Test backup schedule by running a backup immediately.

    Returns:
        Exit code
    """
    try:
        config = get_config()
        schedule_config_path = config.data_dir / "backup_schedule.json"

        if not schedule_config_path.exists():
            console.print("\n[bold red]Error:[/bold red] No backup schedule configured.\n")
            console.print("Run [cyan]schedule enable[/cyan] first.\n")
            return 1

        # Load configuration
        schedule_config = BackupScheduler.load_config_from_file(schedule_config_path)

        console.print("\n[bold blue]Testing Backup Schedule[/bold blue]\n")
        console.print("Running backup with current schedule settings...\n")

        # Create scheduler and run backup
        scheduler = BackupScheduler(schedule_config)
        result = await scheduler.trigger_backup_now()

        if result["status"] == "success":
            console.print(
                Panel.fit(
                    f"[bold green]Test Backup Successful[/bold green]\n\n"
                    f"[cyan]Path:[/cyan] {result['backup_path']}\n"
                    f"[cyan]Time:[/cyan] {result['backup_time']}",
                    border_style="green",
                )
            )
            console.print()
            return 0
        else:
            console.print(
                Panel.fit(
                    "[bold red]Test Backup Failed[/bold red]\n\n"
                    "Check logs for details.",
                    border_style="red",
                )
            )
            console.print()
            return 1

    except Exception as e:
        console.print(f"\n[bold red]Error:[/bold red] {e}\n")
        logger.error(f"Test backup failed: {e}", exc_info=True)
        return 1


def main():
    """Main entry point for schedule commands."""
    import argparse

    parser = argparse.ArgumentParser(description="Manage backup schedules")
    subparsers = parser.add_subparsers(dest="command", help="Schedule command")

    # Enable command
    enable_parser = subparsers.add_parser("enable", help="Enable backup schedule")
    enable_parser.add_argument(
        "--frequency",
        choices=["hourly", "daily", "weekly", "monthly"],
        default="daily",
        help="Backup frequency",
    )
    enable_parser.add_argument(
        "--time", default="02:00", help="Time for backup (HH:MM)"
    )
    enable_parser.add_argument(
        "--retention-days",
        type=int,
        default=30,
        help="Keep backups for N days",
    )
    enable_parser.add_argument(
        "--max-backups",
        type=int,
        default=10,
        help="Maximum number of backups to keep",
    )
    enable_parser.add_argument(
        "--format",
        choices=["archive", "json"],
        default="archive",
        help="Backup format",
    )

    # Disable command
    subparsers.add_parser("disable", help="Disable backup schedule")

    # Status command
    subparsers.add_parser("status", help="Show schedule status")

    # Test command
    subparsers.add_parser("test", help="Test backup schedule")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    # Execute command
    if args.command == "enable":
        return asyncio.run(
            schedule_enable(
                frequency=args.frequency,
                time=args.time,
                retention_days=args.retention_days,
                max_backups=args.max_backups,
                format=args.format,
            )
        )
    elif args.command == "disable":
        return asyncio.run(schedule_disable())
    elif args.command == "status":
        return asyncio.run(schedule_status())
    elif args.command == "test":
        return asyncio.run(schedule_test())


if __name__ == "__main__":
    sys.exit(main())
