"""Watch command for CLI - watches directory and auto-indexes changes."""

import asyncio
import logging
from pathlib import Path

from src.memory.indexing_service import IndexingService
from src.config import get_config

logger = logging.getLogger(__name__)


class WatchCommand:
    """Command to watch a directory and automatically index file changes."""

    def __init__(self):
        """Initialize watch command."""
        self.config = get_config()

    async def run(self, args):
        """
        Run the watch command.

        Args:
            args: Parsed command-line arguments
        """
        path = Path(args.path).resolve()

        if not path.exists():
            logger.error(f"Path does not exist: {path}")
            return

        if not path.is_dir():
            logger.error(f"Path must be a directory: {path}")
            return

        # Determine project name
        project_name = args.project_name or path.name

        logger.info(f"Setting up file watcher for project: {project_name}")
        logger.info(f"Directory: {path}")

        # Create indexing service
        service = IndexingService(
            watch_path=path,
            project_name=project_name,
        )

        try:
            # Initialize
            await service.initialize()

            # Perform initial indexing
            print(f"\nPerforming initial indexing of {path}...\n")
            result = await service.index_initial(recursive=True)

            print("\n" + "=" * 60)
            print("INITIAL INDEXING COMPLETE")
            print("=" * 60)
            print(f"Project: {project_name}")
            print(f"Files indexed: {result['indexed_files']}")
            print(f"Semantic units: {result['total_units']}")
            print("=" * 60 + "\n")

            # Start watching
            print(f"Watching {path} for changes...")
            print("Monitoring file types: .py, .js, .ts, .tsx, .jsx, .java, .go, .rs, .c, .cpp, .h, .hpp")
            print("                        .swift, .kt, .rb, .php, .cs, .sql, .json, .yaml, .yml, .toml, .md")
            print("Ignoring: .git/, node_modules/, __pycache__/, venv/, .venv/, build/, dist/")
            print("\nPress Ctrl+C to stop (will finish current file before stopping).\n")

            await service.run_until_stopped()

        except KeyboardInterrupt:
            print("\nStopping file watcher...")
        except Exception as e:
            logger.error(f"Watch failed: {e}", exc_info=True)
            print(f"\nERROR: Watch failed - {e}\n")
            raise
        finally:
            await service.close()
            print("File watcher stopped.\n")
