"""Repository management commands for CLI."""

import asyncio
import logging
from pathlib import Path
from typing import Optional, List

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

from src.config import get_config
from src.memory.repository_registry import RepositoryRegistry, RepositoryStatus

logger = logging.getLogger(__name__)


class RepositoryCommand:
    """Command for repository management operations."""

    def __init__(self):
        """Initialize repository command."""
        self.config = get_config()
        self.console = Console() if RICH_AVAILABLE else None

    async def run(self, args):
        """
        Execute repository command.

        Args:
            args: Command arguments from argparse
        """
        # Map subcommands to handlers
        handlers = {
            'list': self._list_repositories,
            'register': self._register_repository,
            'unregister': self._unregister_repository,
            'info': self._get_repository_info,
            'add-dep': self._add_dependency,
            'remove-dep': self._remove_dependency,
        }

        handler = handlers.get(args.repo_subcommand)
        if handler:
            await handler(args)
        else:
            self._print_error(f"Unknown subcommand: {args.repo_subcommand}")

    async def _list_repositories(self, args):
        """List all repositories."""
        try:
            # Initialize registry
            registry = RepositoryRegistry(self.config)
            await registry.initialize()

            # Parse status filter
            status_filter = None
            if args.status:
                try:
                    status_filter = RepositoryStatus(args.status.upper())
                except ValueError:
                    self._print_error(f"Invalid status: {args.status}")
                    self._print_info("Valid statuses: INDEXED, INDEXING, STALE, ERROR, NOT_INDEXED")
                    return

            # Get repositories
            repositories = await registry.list_repositories(
                status=status_filter,
                workspace_id=args.workspace,
                tags=args.tags.split(',') if args.tags else None
            )

            if not repositories:
                self._print_info("No repositories found")
                return

            # Display results
            if self.console:
                self._print_rich_repositories(repositories)
            else:
                self._print_plain_repositories(repositories)

        except Exception as e:
            self._print_error(f"Failed to list repositories: {e}")
            logger.error(f"Failed to list repositories: {e}", exc_info=True)

    async def _register_repository(self, args):
        """Register a new repository."""
        try:
            # Validate path
            path = Path(args.path).resolve()
            if not path.exists():
                self._print_error(f"Path does not exist: {path}")
                return

            if not path.is_dir():
                self._print_error(f"Path is not a directory: {path}")
                return

            # Initialize registry
            registry = RepositoryRegistry(self.config)
            await registry.initialize()

            # Register repository
            repo_id = await registry.register_repository(
                path=str(path),
                name=args.name,
                git_url=args.git_url,
                tags=args.tags.split(',') if args.tags else []
            )

            # Get repository details
            repository = await registry.get_repository(repo_id)

            self._print_success(f"Repository registered: {repository.name}")
            self._print_info(f"Repository ID: {repo_id}")
            self._print_info(f"Path: {repository.path}")
            if repository.git_url:
                self._print_info(f"Git URL: {repository.git_url}")
            if repository.tags:
                self._print_info(f"Tags: {', '.join(repository.tags)}")

        except Exception as e:
            self._print_error(f"Failed to register repository: {e}")
            logger.error(f"Failed to register repository: {e}", exc_info=True)

    async def _unregister_repository(self, args):
        """Unregister a repository."""
        try:
            # Initialize registry
            registry = RepositoryRegistry(self.config)
            await registry.initialize()

            # Get repository info first
            repository = await registry.get_repository(args.repo_id)
            if not repository:
                self._print_error(f"Repository not found: {args.repo_id}")
                return

            repo_name = repository.name

            # Unregister
            success = await registry.unregister_repository(args.repo_id)

            if success:
                self._print_success(f"Repository unregistered: {repo_name}")
                self._print_info(f"Repository ID: {args.repo_id}")
            else:
                self._print_error(f"Failed to unregister repository: {args.repo_id}")

        except Exception as e:
            self._print_error(f"Failed to unregister repository: {e}")
            logger.error(f"Failed to unregister repository: {e}", exc_info=True)

    async def _get_repository_info(self, args):
        """Get detailed repository information."""
        try:
            # Initialize registry
            registry = RepositoryRegistry(self.config)
            await registry.initialize()

            # Get repository
            repository = await registry.get_repository(args.repo_id)
            if not repository:
                self._print_error(f"Repository not found: {args.repo_id}")
                return

            # Get dependencies
            dependencies = await registry.get_dependencies(args.repo_id)

            # Display results
            if self.console:
                self._print_rich_repository_info(repository, dependencies)
            else:
                self._print_plain_repository_info(repository, dependencies)

        except Exception as e:
            self._print_error(f"Failed to get repository info: {e}")
            logger.error(f"Failed to get repository info: {e}", exc_info=True)

    async def _add_dependency(self, args):
        """Add a dependency relationship."""
        try:
            # Initialize registry
            registry = RepositoryRegistry(self.config)
            await registry.initialize()

            # Verify both repositories exist
            repo = await registry.get_repository(args.repo_id)
            if not repo:
                self._print_error(f"Repository not found: {args.repo_id}")
                return

            dep_repo = await registry.get_repository(args.depends_on)
            if not dep_repo:
                self._print_error(f"Dependency repository not found: {args.depends_on}")
                return

            # Add dependency
            await registry.add_dependency(args.repo_id, args.depends_on)

            self._print_success(f"Dependency added: {repo.name} → {dep_repo.name}")

        except ValueError as e:
            self._print_error(f"Cannot add dependency: {e}")
        except Exception as e:
            self._print_error(f"Failed to add dependency: {e}")
            logger.error(f"Failed to add dependency: {e}", exc_info=True)

    async def _remove_dependency(self, args):
        """Remove a dependency relationship."""
        try:
            # Initialize registry
            registry = RepositoryRegistry(self.config)
            await registry.initialize()

            # Remove dependency
            await registry.remove_dependency(args.repo_id, args.depends_on)

            self._print_success(f"Dependency removed: {args.repo_id} → {args.depends_on}")

        except Exception as e:
            self._print_error(f"Failed to remove dependency: {e}")
            logger.error(f"Failed to remove dependency: {e}", exc_info=True)

    def _print_rich_repositories(self, repositories):
        """Print repositories in rich format."""
        table = Table(title="[bold cyan]Repositories[/bold cyan]")
        table.add_column("Name", style="cyan", no_wrap=True)
        table.add_column("ID", style="dim", max_width=15)
        table.add_column("Status", style="bold")
        table.add_column("Type", style="white")
        table.add_column("Files", justify="right")
        table.add_column("Units", justify="right")
        table.add_column("Workspaces", style="yellow", max_width=20)

        for repo in repositories:
            # Color status
            status_color = {
                RepositoryStatus.INDEXED: "green",
                RepositoryStatus.INDEXING: "blue",
                RepositoryStatus.STALE: "yellow",
                RepositoryStatus.ERROR: "red",
                RepositoryStatus.NOT_INDEXED: "dim",
            }.get(repo.status, "white")

            status_text = f"[{status_color}]{repo.status.value}[/{status_color}]"

            workspaces = ", ".join(repo.workspace_ids[:2]) if repo.workspace_ids else "-"
            if len(repo.workspace_ids) > 2:
                workspaces += f" +{len(repo.workspace_ids) - 2}"

            table.add_row(
                repo.name,
                repo.id[:12] + "...",
                status_text,
                repo.repo_type.value,
                f"{repo.file_count:,}" if repo.file_count else "-",
                f"{repo.unit_count:,}" if repo.unit_count else "-",
                workspaces
            )

        self.console.print()
        self.console.print(table)
        self.console.print(f"\n[dim]Total: {len(repositories)} repositories[/dim]")
        self.console.print()

    def _print_plain_repositories(self, repositories):
        """Print repositories in plain format."""
        print("\nRepositories:")
        print("=" * 80)
        for repo in repositories:
            print(f"\nName: {repo.name}")
            print(f"  ID: {repo.id}")
            print(f"  Status: {repo.status.value}")
            print(f"  Type: {repo.repo_type.value}")
            print(f"  Path: {repo.path}")
            if repo.file_count:
                print(f"  Files: {repo.file_count:,}")
            if repo.unit_count:
                print(f"  Units: {repo.unit_count:,}")
            if repo.workspace_ids:
                print(f"  Workspaces: {', '.join(repo.workspace_ids)}")
            if repo.tags:
                print(f"  Tags: {', '.join(repo.tags)}")
        print(f"\nTotal: {len(repositories)} repositories")
        print("=" * 80 + "\n")

    def _print_rich_repository_info(self, repository, dependencies):
        """Print detailed repository info in rich format."""
        # Main info table
        table = Table(title=f"[bold cyan]Repository: {repository.name}[/bold cyan]", show_header=False)
        table.add_column("Field", style="cyan", width=20)
        table.add_column("Value", style="white")

        table.add_row("ID", repository.id)
        table.add_row("Name", repository.name)
        table.add_row("Path", repository.path)

        if repository.git_url:
            table.add_row("Git URL", repository.git_url)

        table.add_row("Type", repository.repo_type.value)

        # Color status
        status_color = {
            RepositoryStatus.INDEXED: "green",
            RepositoryStatus.INDEXING: "blue",
            RepositoryStatus.STALE: "yellow",
            RepositoryStatus.ERROR: "red",
            RepositoryStatus.NOT_INDEXED: "dim",
        }.get(repository.status, "white")
        status_text = f"[{status_color}]{repository.status.value}[/{status_color}]"
        table.add_row("Status", status_text)

        if repository.file_count:
            table.add_row("Files Indexed", f"{repository.file_count:,}")
        if repository.unit_count:
            table.add_row("Semantic Units", f"{repository.unit_count:,}")

        if repository.indexed_at:
            table.add_row("Last Indexed", repository.indexed_at.strftime("%Y-%m-%d %H:%M:%S"))

        if repository.tags:
            table.add_row("Tags", ", ".join(repository.tags))

        if repository.workspace_ids:
            table.add_row("Workspaces", ", ".join(repository.workspace_ids))

        self.console.print()
        self.console.print(table)

        # Dependencies
        if dependencies:
            total_deps = sum(len(deps) for deps in dependencies.values())
            if total_deps > 0:
                self.console.print()
                dep_table = Table(title=f"[bold cyan]Dependencies ({total_deps})[/bold cyan]")
                dep_table.add_column("Depth", justify="center", style="cyan")
                dep_table.add_column("Repository IDs", style="white")

                for depth, dep_ids in sorted(dependencies.items()):
                    if dep_ids:
                        dep_table.add_row(str(depth), ", ".join(dep_ids))

                self.console.print(dep_table)

        self.console.print()

    def _print_plain_repository_info(self, repository, dependencies):
        """Print detailed repository info in plain format."""
        print("\nRepository Information:")
        print("=" * 80)
        print(f"ID: {repository.id}")
        print(f"Name: {repository.name}")
        print(f"Path: {repository.path}")
        if repository.git_url:
            print(f"Git URL: {repository.git_url}")
        print(f"Type: {repository.repo_type.value}")
        print(f"Status: {repository.status.value}")

        if repository.file_count:
            print(f"Files Indexed: {repository.file_count:,}")
        if repository.unit_count:
            print(f"Semantic Units: {repository.unit_count:,}")

        if repository.indexed_at:
            print(f"Last Indexed: {repository.indexed_at.strftime('%Y-%m-%d %H:%M:%S')}")

        if repository.tags:
            print(f"Tags: {', '.join(repository.tags)}")

        if repository.workspace_ids:
            print(f"Workspaces: {', '.join(repository.workspace_ids)}")

        # Dependencies
        if dependencies:
            total_deps = sum(len(deps) for deps in dependencies.values())
            if total_deps > 0:
                print(f"\nDependencies ({total_deps}):")
                for depth, dep_ids in sorted(dependencies.items()):
                    if dep_ids:
                        print(f"  Depth {depth}: {', '.join(dep_ids)}")

        print("=" * 80 + "\n")

    def _print_success(self, message: str):
        """Print success message."""
        if self.console:
            self.console.print(f"[bold green]✓[/bold green] {message}")
        else:
            print(f"✓ {message}")

    def _print_error(self, message: str):
        """Print error message."""
        if self.console:
            self.console.print(f"[bold red]✗[/bold red] {message}", style="red")
        else:
            print(f"✗ {message}")

    def _print_info(self, message: str):
        """Print info message."""
        if self.console:
            self.console.print(f"  {message}", style="dim")
        else:
            print(f"  {message}")


def add_repository_parser(subparsers):
    """Add repository command parser."""
    repo_parser = subparsers.add_parser(
        'repository',
        aliases=['repo'],
        help='Manage code repositories'
    )

    repo_subparsers = repo_parser.add_subparsers(
        dest='repo_subcommand',
        help='Repository subcommands'
    )

    # List repositories
    list_parser = repo_subparsers.add_parser(
        'list',
        help='List all repositories'
    )
    list_parser.add_argument(
        '--status',
        help='Filter by status (INDEXED, INDEXING, STALE, ERROR, NOT_INDEXED)'
    )
    list_parser.add_argument(
        '--workspace',
        help='Filter by workspace ID'
    )
    list_parser.add_argument(
        '--tags',
        help='Filter by tags (comma-separated)'
    )

    # Register repository
    register_parser = repo_subparsers.add_parser(
        'register',
        help='Register a new repository'
    )
    register_parser.add_argument(
        'path',
        help='Path to repository'
    )
    register_parser.add_argument(
        '--name',
        help='Repository name (defaults to directory name)'
    )
    register_parser.add_argument(
        '--git-url',
        help='Git repository URL'
    )
    register_parser.add_argument(
        '--tags',
        help='Tags (comma-separated)'
    )

    # Unregister repository
    unregister_parser = repo_subparsers.add_parser(
        'unregister',
        help='Unregister a repository'
    )
    unregister_parser.add_argument(
        'repo_id',
        help='Repository ID'
    )

    # Get repository info
    info_parser = repo_subparsers.add_parser(
        'info',
        help='Get detailed repository information'
    )
    info_parser.add_argument(
        'repo_id',
        help='Repository ID'
    )

    # Add dependency
    add_dep_parser = repo_subparsers.add_parser(
        'add-dep',
        help='Add a dependency relationship'
    )
    add_dep_parser.add_argument(
        'repo_id',
        help='Repository ID'
    )
    add_dep_parser.add_argument(
        'depends_on',
        help='Dependency repository ID'
    )

    # Remove dependency
    remove_dep_parser = repo_subparsers.add_parser(
        'remove-dep',
        help='Remove a dependency relationship'
    )
    remove_dep_parser.add_argument(
        'repo_id',
        help='Repository ID'
    )
    remove_dep_parser.add_argument(
        'depends_on',
        help='Dependency repository ID'
    )

    return repo_parser


async def main(args):
    """Main entry point for repository command."""
    command = RepositoryCommand()
    await command.run(args)
