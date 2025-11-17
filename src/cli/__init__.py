"""CLI commands for Claude Memory RAG Server."""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

from src.cli.index_command import IndexCommand
from src.cli.watch_command import WatchCommand
from src.cli.health_command import HealthCommand
from src.cli.status_command import StatusCommand
from src.cli.prune_command import prune_command


def setup_logging(level: str = "INFO"):
    """Configure logging for CLI."""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def create_parser() -> argparse.ArgumentParser:
    """Create the main argument parser."""
    parser = argparse.ArgumentParser(
        prog="claude-rag",
        description="Claude Memory RAG Server - CLI for code indexing and memory management",
    )

    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Set logging level (default: INFO)",
    )

    # Subcommands
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Index command
    index_parser = subparsers.add_parser(
        "index",
        help="Index code files for semantic search",
    )
    index_parser.add_argument(
        "path",
        type=Path,
        help="File or directory to index",
    )
    index_parser.add_argument(
        "--project-name",
        type=str,
        help="Project name for scoping (defaults to directory name)",
    )
    index_parser.add_argument(
        "--recursive",
        action="store_true",
        default=True,
        help="Recursively index subdirectories (default: True)",
    )
    index_parser.add_argument(
        "--no-recursive",
        dest="recursive",
        action="store_false",
        help="Don't recursively index subdirectories",
    )

    # Health command
    health_parser = subparsers.add_parser(
        "health",
        help="Run health check diagnostics",
    )

    # Status command
    status_parser = subparsers.add_parser(
        "status",
        help="Show server and storage status",
    )

    # Watch command
    watch_parser = subparsers.add_parser(
        "watch",
        help="Watch directory for changes and auto-index",
    )
    watch_parser.add_argument(
        "path",
        type=Path,
        help="Directory to watch",
    )
    watch_parser.add_argument(
        "--project-name",
        type=str,
        help="Project name for scoping",
    )

    # Browse command
    browse_parser = subparsers.add_parser(
        "browse",
        help="Interactive memory browser (TUI)",
    )

    # Prune command
    prune_parser = subparsers.add_parser(
        "prune",
        help="Prune expired and stale memories",
    )
    prune_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Don't actually delete, just show what would be deleted",
    )
    prune_parser.add_argument(
        "--ttl-hours",
        type=int,
        help="Time-to-live for SESSION_STATE in hours (default from config)",
    )
    prune_parser.add_argument(
        "--stale-days",
        type=int,
        help="Also prune memories unused for N days",
    )
    prune_parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Show detailed output",
    )

    return parser


async def main_async(args):
    """Async main function to handle commands."""
    if args.command == "index":
        cmd = IndexCommand()
        await cmd.run(args)
    elif args.command == "health":
        cmd = HealthCommand()
        await cmd.run(args)
    elif args.command == "status":
        cmd = StatusCommand()
        await cmd.run(args)
    elif args.command == "watch":
        cmd = WatchCommand()
        await cmd.run(args)
    elif args.command == "browse":
        from src.cli.memory_browser import run_memory_browser
        await run_memory_browser()
    elif args.command == "prune":
        exit_code = await prune_command(
            dry_run=args.dry_run,
            ttl_hours=args.ttl_hours,
            verbose=args.verbose,
            stale_days=args.stale_days,
        )
        sys.exit(exit_code)
    else:
        print("No command specified. Use --help for usage information.")
        sys.exit(1)


def main():
    """Main CLI entry point."""
    parser = create_parser()
    args = parser.parse_args()

    # Setup logging
    setup_logging(args.log_level)

    # Run async main
    try:
        asyncio.run(main_async(args))
    except KeyboardInterrupt:
        print("\nInterrupted by user")
        sys.exit(0)
    except Exception as e:
        logging.error(f"Command failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
