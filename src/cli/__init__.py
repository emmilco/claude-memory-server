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
from src.cli.git_index_command import GitIndexCommand
from src.cli.git_search_command import GitSearchCommand
from src.cli.analytics_command import run_analytics_command
from src.cli.session_summary_command import run_session_summary_command
from src.cli.health_monitor_command import HealthMonitorCommand
from src.cli.verify_command import verify_command
from src.cli.consolidate_command import consolidate_command
from src.cli.repository_command import add_repository_parser, RepositoryCommand
from src.cli.workspace_command import add_workspace_parser, WorkspaceCommand


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

    # Git index command
    git_index_parser = subparsers.add_parser(
        "git-index",
        help="Index git history for semantic search",
    )
    git_index_parser.add_argument(
        "repo_path",
        type=Path,
        help="Path to git repository",
    )
    git_index_parser.add_argument(
        "--project-name",
        "-p",
        type=str,
        required=True,
        help="Project name for organization",
    )
    git_index_parser.add_argument(
        "--commits",
        "-n",
        type=int,
        help="Number of commits to index (default from config)",
    )
    git_index_parser.add_argument(
        "--diffs",
        action="store_true",
        dest="diffs",
        help="Include diff content",
    )
    git_index_parser.add_argument(
        "--no-diffs",
        action="store_false",
        dest="diffs",
        help="Don't include diff content",
    )
    git_index_parser.set_defaults(diffs=None)
    git_index_parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Verbose output",
    )

    # Git search command
    git_search_parser = subparsers.add_parser(
        "git-search",
        help="Search git commit history",
    )
    git_search_parser.add_argument(
        "query",
        type=str,
        help="Search query (e.g., 'authentication bug fix')",
    )
    git_search_parser.add_argument(
        "--project-name",
        "-p",
        type=str,
        help="Filter by project name",
    )
    git_search_parser.add_argument(
        "--author",
        "-a",
        type=str,
        help="Filter by author email",
    )
    git_search_parser.add_argument(
        "--since",
        "-s",
        type=str,
        help="Filter by date (e.g., '2024-01-01', 'last week')",
    )
    git_search_parser.add_argument(
        "--until",
        "-u",
        type=str,
        help="Filter by date (e.g., '2024-12-31', 'yesterday')",
    )
    git_search_parser.add_argument(
        "--limit",
        "-l",
        type=int,
        default=10,
        help="Maximum results (default: 10)",
    )

    # Analytics command
    analytics_parser = subparsers.add_parser(
        "analytics",
        help="View token usage analytics and cost savings",
    )
    analytics_parser.add_argument(
        "--period-days",
        "-d",
        type=int,
        default=30,
        help="Number of days to analyze (default: 30)",
    )
    analytics_parser.add_argument(
        "--session-id",
        "-s",
        type=str,
        help="Filter by specific session ID",
    )
    analytics_parser.add_argument(
        "--project-name",
        "-p",
        type=str,
        help="Filter by specific project",
    )
    analytics_parser.add_argument(
        "--top-sessions",
        "-t",
        action="store_true",
        help="Show top sessions by tokens saved",
    )

    # Session summary command
    session_summary_parser = subparsers.add_parser(
        "session-summary",
        help="View summary of current or recent sessions",
    )
    session_summary_parser.add_argument(
        "--session-id",
        "-s",
        type=str,
        help="Specific session ID to summarize",
    )

    # Health monitor command
    health_monitor_parser = subparsers.add_parser(
        "health-monitor",
        help="Continuous health monitoring and alerts",
    )
    health_monitor_subparsers = health_monitor_parser.add_subparsers(
        dest="subcommand",
        help="Health monitoring subcommands",
    )

    # Health monitor status
    status_sub = health_monitor_subparsers.add_parser(
        "status",
        help="Show current health status (default)",
    )

    # Health monitor report
    report_sub = health_monitor_subparsers.add_parser(
        "report",
        help="Generate detailed health report",
    )
    report_sub.add_argument(
        "--period-days",
        "-d",
        type=int,
        default=7,
        help="Report period in days (default: 7)",
    )

    # Health monitor fix
    fix_sub = health_monitor_subparsers.add_parser(
        "fix",
        help="Apply automated remediation",
    )
    fix_sub.add_argument(
        "--auto",
        "-a",
        action="store_true",
        help="Automatically apply all fixes without prompts",
    )
    fix_sub.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be fixed without applying",
    )

    # Health monitor history
    history_sub = health_monitor_subparsers.add_parser(
        "history",
        help="View historical health metrics",
    )
    history_sub.add_argument(
        "--days",
        "-d",
        type=int,
        default=30,
        help="Number of days of history (default: 30)",
    )

    # Verify command
    verify_parser = subparsers.add_parser(
        "verify",
        help="Interactive memory verification workflow",
    )
    verify_parser.add_argument(
        "--auto-verify",
        action="store_true",
        help="Auto-verify high confidence memories (>0.8)",
    )
    verify_parser.add_argument(
        "--category",
        "-c",
        type=str,
        help="Filter by category (preference, fact, event, workflow, context)",
    )
    verify_parser.add_argument(
        "--contradictions",
        action="store_true",
        help="Review and resolve contradictions",
    )
    verify_parser.add_argument(
        "--max-items",
        "-n",
        type=int,
        default=20,
        help="Maximum items to review (default: 20)",
    )

    # Consolidate command
    consolidate_parser = subparsers.add_parser(
        "consolidate",
        help="Find and merge duplicate memories",
    )
    consolidate_parser.add_argument(
        "--auto",
        action="store_true",
        help="Auto-merge high-confidence duplicates (>0.95)",
    )
    consolidate_parser.add_argument(
        "--interactive",
        action="store_true",
        help="Review each merge interactively",
    )
    consolidate_parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Show what would be done (default, safe)",
    )
    consolidate_parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually perform merges (disables dry-run)",
    )
    consolidate_parser.add_argument(
        "--category",
        "-c",
        type=str,
        help="Filter by category (preference, fact, event, workflow, context)",
    )

    # Repository command
    add_repository_parser(subparsers)

    # Workspace command
    add_workspace_parser(subparsers)

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
    elif args.command == "git-index":
        cmd = GitIndexCommand()
        await cmd.run(args)
    elif args.command == "git-search":
        cmd = GitSearchCommand()
        await cmd.run(args)
    elif args.command == "analytics":
        run_analytics_command(
            period_days=args.period_days,
            session_id=args.session_id,
            project_name=args.project_name,
            show_top_sessions=args.top_sessions,
        )
    elif args.command == "session-summary":
        run_session_summary_command(
            session_id=args.session_id,
        )
    elif args.command == "health-monitor":
        cmd = HealthMonitorCommand()
        await cmd.run(args)
    elif args.command == "verify":
        await verify_command(
            auto_verify_high_confidence=args.auto_verify,
            category=args.category,
            show_contradictions=args.contradictions,
            max_items=args.max_items,
        )
    elif args.command == "consolidate":
        # Handle --execute flag to disable dry-run
        dry_run = args.dry_run
        if args.execute:
            dry_run = False

        await consolidate_command(
            auto=args.auto,
            interactive=args.interactive,
            dry_run=dry_run,
            category=args.category,
        )
    elif args.command in ("repository", "repo"):
        cmd = RepositoryCommand()
        await cmd.run(args)
    elif args.command in ("workspace", "ws"):
        cmd = WorkspaceCommand()
        await cmd.run(args)
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
