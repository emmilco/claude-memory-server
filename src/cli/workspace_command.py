"""Workspace management commands for CLI."""

import logging

try:
    from rich.console import Console
    from rich.table import Table

    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

from src.config import get_config
from src.memory.repository_registry import RepositoryRegistry
from src.memory.workspace_manager import WorkspaceManager

logger = logging.getLogger(__name__)


class WorkspaceCommand:
    """Command for workspace management operations."""

    def __init__(self):
        """Initialize workspace command."""
        self.config = get_config()
        self.console = Console() if RICH_AVAILABLE else None

    async def run(self, args):
        """
        Execute workspace command.

        Args:
            args: Command arguments from argparse
        """
        # Map subcommands to handlers
        handlers = {
            "list": self._list_workspaces,
            "create": self._create_workspace,
            "delete": self._delete_workspace,
            "info": self._get_workspace_info,
            "add-repo": self._add_repository,
            "remove-repo": self._remove_repository,
            "repos": self._list_repositories,
        }

        handler = handlers.get(args.workspace_subcommand)
        if handler:
            await handler(args)
        else:
            self._print_error(f"Unknown subcommand: {args.workspace_subcommand}")

    async def _list_workspaces(self, args):
        """List all workspaces."""
        try:
            # Initialize managers
            registry = RepositoryRegistry(self.config.repository_storage_path)
            await registry.initialize()

            workspace_manager = WorkspaceManager(registry, self.config)
            await workspace_manager.initialize()

            # Get workspaces
            workspaces = await workspace_manager.list_workspaces(
                tags=args.tags.split(",") if args.tags else None
            )

            if not workspaces:
                self._print_info("No workspaces found")
                return

            # Display results
            if self.console:
                self._print_rich_workspaces(workspaces)
            else:
                self._print_plain_workspaces(workspaces)

        except Exception as e:
            self._print_error(f"Failed to list workspaces: {e}")
            logger.error(f"Failed to list workspaces: {e}", exc_info=True)

    async def _create_workspace(self, args):
        """Create a new workspace."""
        try:
            # Initialize managers
            registry = RepositoryRegistry(self.config.repository_storage_path)
            await registry.initialize()

            workspace_manager = WorkspaceManager(registry, self.config)
            await workspace_manager.initialize()

            # Generate workspace ID from name
            import re

            workspace_id = re.sub(r"[^a-z0-9]+", "-", args.name.lower()).strip("-")

            # Parse repository IDs
            repo_ids = []
            if args.repos:
                repo_ids = [r.strip() for r in args.repos.split(",")]

            # Create workspace
            workspace = await workspace_manager.create_workspace(
                workspace_id=workspace_id,
                name=args.name,
                description=args.description,
                repository_ids=repo_ids,
                auto_index=not args.no_auto_index,
                cross_repo_search_enabled=not args.no_cross_search,
            )

            self._print_success(f"Workspace created: {workspace.name}")
            self._print_info(f"Workspace ID: {workspace.id}")
            if workspace.description:
                self._print_info(f"Description: {workspace.description}")
            if workspace.repository_ids:
                self._print_info(f"Repositories: {len(workspace.repository_ids)}")
            self._print_info(f"Auto-index: {workspace.auto_index}")
            self._print_info(
                f"Cross-repo search: {workspace.cross_repo_search_enabled}"
            )

        except Exception as e:
            self._print_error(f"Failed to create workspace: {e}")
            logger.error(f"Failed to create workspace: {e}", exc_info=True)

    async def _delete_workspace(self, args):
        """Delete a workspace."""
        try:
            # Initialize managers
            registry = RepositoryRegistry(self.config.repository_storage_path)
            await registry.initialize()

            workspace_manager = WorkspaceManager(registry, self.config)
            await workspace_manager.initialize()

            # Get workspace info first
            workspace = await workspace_manager.get_workspace(args.workspace_id)
            if not workspace:
                self._print_error(f"Workspace not found: {args.workspace_id}")
                return

            workspace_name = workspace.name

            # Delete workspace
            success = await workspace_manager.delete_workspace(args.workspace_id)

            if success:
                self._print_success(f"Workspace deleted: {workspace_name}")
                self._print_info(f"Workspace ID: {args.workspace_id}")
            else:
                self._print_error(f"Failed to delete workspace: {args.workspace_id}")

        except Exception as e:
            self._print_error(f"Failed to delete workspace: {e}")
            logger.error(f"Failed to delete workspace: {e}", exc_info=True)

    async def _get_workspace_info(self, args):
        """Get detailed workspace information."""
        try:
            # Initialize managers
            registry = RepositoryRegistry(self.config.repository_storage_path)
            await registry.initialize()

            workspace_manager = WorkspaceManager(registry, self.config)
            await workspace_manager.initialize()

            # Get workspace
            workspace = await workspace_manager.get_workspace(args.workspace_id)
            if not workspace:
                self._print_error(f"Workspace not found: {args.workspace_id}")
                return

            # Get repository details
            repositories = []
            for repo_id in workspace.repository_ids:
                repo = await registry.get_repository(repo_id)
                if repo:
                    repositories.append(repo)

            # Display results
            if self.console:
                self._print_rich_workspace_info(workspace, repositories)
            else:
                self._print_plain_workspace_info(workspace, repositories)

        except Exception as e:
            self._print_error(f"Failed to get workspace info: {e}")
            logger.error(f"Failed to get workspace info: {e}", exc_info=True)

    async def _add_repository(self, args):
        """Add a repository to a workspace."""
        try:
            # Initialize managers
            registry = RepositoryRegistry(self.config.repository_storage_path)
            await registry.initialize()

            workspace_manager = WorkspaceManager(registry, self.config)
            await workspace_manager.initialize()

            # Verify workspace exists
            workspace = await workspace_manager.get_workspace(args.workspace_id)
            if not workspace:
                self._print_error(f"Workspace not found: {args.workspace_id}")
                return

            # Verify repository exists
            repo = await registry.get_repository(args.repo_id)
            if not repo:
                self._print_error(f"Repository not found: {args.repo_id}")
                return

            # Add repository
            await workspace_manager.add_repository(args.workspace_id, args.repo_id)

            self._print_success(
                f"Repository added to workspace: {repo.name} → {workspace.name}"
            )

        except Exception as e:
            self._print_error(f"Failed to add repository to workspace: {e}")
            logger.error(f"Failed to add repository to workspace: {e}", exc_info=True)

    async def _remove_repository(self, args):
        """Remove a repository from a workspace."""
        try:
            # Initialize managers
            registry = RepositoryRegistry(self.config.repository_storage_path)
            await registry.initialize()

            workspace_manager = WorkspaceManager(registry, self.config)
            await workspace_manager.initialize()

            # Remove repository
            await workspace_manager.remove_repository(args.workspace_id, args.repo_id)

            self._print_success("Repository removed from workspace")
            self._print_info(f"Workspace ID: {args.workspace_id}")
            self._print_info(f"Repository ID: {args.repo_id}")

        except Exception as e:
            self._print_error(f"Failed to remove repository from workspace: {e}")
            logger.error(
                f"Failed to remove repository from workspace: {e}", exc_info=True
            )

    async def _list_repositories(self, args):
        """List repositories in a workspace."""
        try:
            # Initialize managers
            registry = RepositoryRegistry(self.config.repository_storage_path)
            await registry.initialize()

            workspace_manager = WorkspaceManager(registry, self.config)
            await workspace_manager.initialize()

            # Get workspace
            workspace = await workspace_manager.get_workspace(args.workspace_id)
            if not workspace:
                self._print_error(f"Workspace not found: {args.workspace_id}")
                return

            if not workspace.repository_ids:
                self._print_info(f"No repositories in workspace '{workspace.name}'")
                return

            # Get repository details
            repositories = []
            for repo_id in workspace.repository_ids:
                repo = await registry.get_repository(repo_id)
                if repo:
                    repositories.append(repo)

            # Display results
            if self.console:
                self._print_rich_repositories(workspace.name, repositories)
            else:
                self._print_plain_repositories(workspace.name, repositories)

        except Exception as e:
            self._print_error(f"Failed to list repositories in workspace: {e}")
            logger.error(
                f"Failed to list repositories in workspace: {e}", exc_info=True
            )

    def _print_rich_workspaces(self, workspaces):
        """Print workspaces in rich format."""
        table = Table(title="[bold cyan]Workspaces[/bold cyan]")
        table.add_column("Name", style="cyan", no_wrap=True)
        table.add_column("ID", style="dim", max_width=20)
        table.add_column("Description", style="white", max_width=40)
        table.add_column("Repos", justify="right")
        table.add_column("Auto-Index", justify="center")
        table.add_column("Cross-Search", justify="center")

        for ws in workspaces:
            table.add_row(
                ws.name,
                ws.id,
                ws.description or "-",
                str(len(ws.repository_ids)),
                "✓" if ws.auto_index else "✗",
                "✓" if ws.cross_repo_search_enabled else "✗",
            )

        self.console.print()
        self.console.print(table)
        self.console.print(f"\n[dim]Total: {len(workspaces)} workspaces[/dim]")
        self.console.print()

    def _print_plain_workspaces(self, workspaces):
        """Print workspaces in plain format."""
        print("\nWorkspaces:")
        print("=" * 80)
        for ws in workspaces:
            print(f"\nName: {ws.name}")
            print(f"  ID: {ws.id}")
            if ws.description:
                print(f"  Description: {ws.description}")
            print(f"  Repositories: {len(ws.repository_ids)}")
            print(f"  Auto-index: {ws.auto_index}")
            print(f"  Cross-repo search: {ws.cross_repo_search_enabled}")
            if ws.tags:
                print(f"  Tags: {', '.join(ws.tags)}")
        print(f"\nTotal: {len(workspaces)} workspaces")
        print("=" * 80 + "\n")

    def _print_rich_workspace_info(self, workspace, repositories):
        """Print detailed workspace info in rich format."""
        # Main info table
        table = Table(
            title=f"[bold cyan]Workspace: {workspace.name}[/bold cyan]",
            show_header=False,
        )
        table.add_column("Field", style="cyan", width=20)
        table.add_column("Value", style="white")

        table.add_row("ID", workspace.id)
        table.add_row("Name", workspace.name)

        if workspace.description:
            table.add_row("Description", workspace.description)

        table.add_row("Repositories", str(len(workspace.repository_ids)))
        table.add_row("Auto-index", "✓" if workspace.auto_index else "✗")
        table.add_row(
            "Cross-repo search", "✓" if workspace.cross_repo_search_enabled else "✗"
        )

        if workspace.tags:
            table.add_row("Tags", ", ".join(workspace.tags))

        table.add_row("Created", workspace.created_at.strftime("%Y-%m-%d %H:%M:%S"))
        table.add_row("Updated", workspace.updated_at.strftime("%Y-%m-%d %H:%M:%S"))

        self.console.print()
        self.console.print(table)

        # Repositories
        if repositories:
            self.console.print()
            repo_table = Table(
                title=f"[bold cyan]Repositories ({len(repositories)})[/bold cyan]"
            )
            repo_table.add_column("Name", style="cyan")
            repo_table.add_column("Status", style="bold")
            repo_table.add_column("Files", justify="right")
            repo_table.add_column("Units", justify="right")

            for repo in repositories:
                from src.memory.repository_registry import RepositoryStatus

                status_color = {
                    RepositoryStatus.INDEXED: "green",
                    RepositoryStatus.INDEXING: "blue",
                    RepositoryStatus.STALE: "yellow",
                    RepositoryStatus.ERROR: "red",
                    RepositoryStatus.NOT_INDEXED: "dim",
                }.get(repo.status, "white")

                status_text = f"[{status_color}]{repo.status.value}[/{status_color}]"

                repo_table.add_row(
                    repo.name,
                    status_text,
                    f"{repo.file_count:,}" if repo.file_count else "-",
                    f"{repo.unit_count:,}" if repo.unit_count else "-",
                )

            self.console.print(repo_table)

        self.console.print()

    def _print_plain_workspace_info(self, workspace, repositories):
        """Print detailed workspace info in plain format."""
        print("\nWorkspace Information:")
        print("=" * 80)
        print(f"ID: {workspace.id}")
        print(f"Name: {workspace.name}")
        if workspace.description:
            print(f"Description: {workspace.description}")
        print(f"Repositories: {len(workspace.repository_ids)}")
        print(f"Auto-index: {workspace.auto_index}")
        print(f"Cross-repo search: {workspace.cross_repo_search_enabled}")
        if workspace.tags:
            print(f"Tags: {', '.join(workspace.tags)}")
        print(f"Created: {workspace.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Updated: {workspace.updated_at.strftime('%Y-%m-%d %H:%M:%S')}")

        # Repositories
        if repositories:
            print(f"\nRepositories ({len(repositories)}):")
            for repo in repositories:
                print(f"  - {repo.name} ({repo.status.value})")
                if repo.file_count:
                    print(f"    Files: {repo.file_count:,}, Units: {repo.unit_count:,}")

        print("=" * 80 + "\n")

    def _print_rich_repositories(self, workspace_name, repositories):
        """Print repositories in rich format."""
        table = Table(
            title=f"[bold cyan]Repositories in '{workspace_name}'[/bold cyan]"
        )
        table.add_column("Name", style="cyan")
        table.add_column("ID", style="dim", max_width=15)
        table.add_column("Status", style="bold")
        table.add_column("Files", justify="right")
        table.add_column("Units", justify="right")

        for repo in repositories:
            from src.memory.repository_registry import RepositoryStatus

            status_color = {
                RepositoryStatus.INDEXED: "green",
                RepositoryStatus.INDEXING: "blue",
                RepositoryStatus.STALE: "yellow",
                RepositoryStatus.ERROR: "red",
                RepositoryStatus.NOT_INDEXED: "dim",
            }.get(repo.status, "white")

            status_text = f"[{status_color}]{repo.status.value}[/{status_color}]"

            table.add_row(
                repo.name,
                repo.id[:12] + "...",
                status_text,
                f"{repo.file_count:,}" if repo.file_count else "-",
                f"{repo.unit_count:,}" if repo.unit_count else "-",
            )

        self.console.print()
        self.console.print(table)
        self.console.print(f"\n[dim]Total: {len(repositories)} repositories[/dim]")
        self.console.print()

    def _print_plain_repositories(self, workspace_name, repositories):
        """Print repositories in plain format."""
        print(f"\nRepositories in '{workspace_name}':")
        print("=" * 80)
        for repo in repositories:
            print(f"\n{repo.name}")
            print(f"  ID: {repo.id}")
            print(f"  Status: {repo.status.value}")
            if repo.file_count:
                print(f"  Files: {repo.file_count:,}")
            if repo.unit_count:
                print(f"  Units: {repo.unit_count:,}")
        print(f"\nTotal: {len(repositories)} repositories")
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


def add_workspace_parser(subparsers):
    """Add workspace command parser."""
    workspace_parser = subparsers.add_parser(
        "workspace", aliases=["ws"], help="Manage workspaces"
    )

    workspace_subparsers = workspace_parser.add_subparsers(
        dest="workspace_subcommand", help="Workspace subcommands"
    )

    # List workspaces
    list_parser = workspace_subparsers.add_parser("list", help="List all workspaces")
    list_parser.add_argument("--tags", help="Filter by tags (comma-separated)")

    # Create workspace
    create_parser = workspace_subparsers.add_parser(
        "create", help="Create a new workspace"
    )
    create_parser.add_argument("name", help="Workspace name")
    create_parser.add_argument("--description", help="Workspace description")
    create_parser.add_argument(
        "--repos", help="Repository IDs to add (comma-separated)"
    )
    create_parser.add_argument(
        "--no-auto-index", action="store_true", help="Disable auto-indexing"
    )
    create_parser.add_argument(
        "--no-cross-search", action="store_true", help="Disable cross-repo search"
    )

    # Delete workspace
    delete_parser = workspace_subparsers.add_parser("delete", help="Delete a workspace")
    delete_parser.add_argument("workspace_id", help="Workspace ID")

    # Get workspace info
    info_parser = workspace_subparsers.add_parser(
        "info", help="Get detailed workspace information"
    )
    info_parser.add_argument("workspace_id", help="Workspace ID")

    # Add repository to workspace
    add_repo_parser = workspace_subparsers.add_parser(
        "add-repo", help="Add a repository to a workspace"
    )
    add_repo_parser.add_argument("workspace_id", help="Workspace ID")
    add_repo_parser.add_argument("repo_id", help="Repository ID")

    # Remove repository from workspace
    remove_repo_parser = workspace_subparsers.add_parser(
        "remove-repo", help="Remove a repository from a workspace"
    )
    remove_repo_parser.add_argument("workspace_id", help="Workspace ID")
    remove_repo_parser.add_argument("repo_id", help="Repository ID")

    # List repositories in workspace
    repos_parser = workspace_subparsers.add_parser(
        "repos", help="List repositories in a workspace"
    )
    repos_parser.add_argument("workspace_id", help="Workspace ID")

    return workspace_parser


async def main(args):
    """Main entry point for workspace command."""
    command = WorkspaceCommand()
    await command.run(args)
