"""Index command for CLI - indexes code files into vector storage."""

import asyncio
import logging
from pathlib import Path
from typing import Optional
import time

from src.memory.incremental_indexer import IncrementalIndexer
from src.config import get_config

logger = logging.getLogger(__name__)


class IndexCommand:
    """Command to index code files for semantic search."""

    def __init__(self):
        """Initialize index command."""
        self.config = get_config()

    async def run(self, args):
        """
        Run the index command.

        Args:
            args: Parsed command-line arguments
        """
        path = Path(args.path).resolve()

        if not path.exists():
            logger.error(f"Path does not exist: {path}")
            return

        # Determine project name
        project_name = args.project_name
        if not project_name:
            if path.is_dir():
                project_name = path.name
            else:
                project_name = path.parent.name

        logger.info(f"Indexing for project: {project_name}")
        logger.info(f"Path: {path}")

        # Initialize indexer
        indexer = IncrementalIndexer(project_name=project_name)

        try:
            await indexer.initialize()

            start_time = time.time()

            if path.is_file():
                # Index single file
                logger.info(f"Indexing file: {path}")
                result = await indexer.index_file(path)

                elapsed = time.time() - start_time

                print("\n" + "=" * 60)
                print("INDEXING COMPLETE")
                print("=" * 60)
                print(f"File: {result['file_path']}")
                print(f"Language: {result.get('language', 'N/A')}")
                print(f"Units indexed: {result['units_indexed']}")
                print(f"Parse time: {result.get('parse_time_ms', 0):.2f}ms")
                print(f"Total time: {elapsed:.2f}s")
                print("=" * 60 + "\n")

            elif path.is_dir():
                # Index directory
                logger.info(f"Indexing directory: {path}")
                logger.info(f"Recursive: {args.recursive}")

                result = await indexer.index_directory(
                    path,
                    recursive=args.recursive,
                    show_progress=True,
                )

                elapsed = time.time() - start_time

                print("\n" + "=" * 60)
                print("INDEXING COMPLETE")
                print("=" * 60)
                print(f"Project: {project_name}")
                print(f"Directory: {path}")
                print(f"Total files found: {result['total_files']}")
                print(f"Files indexed: {result['indexed_files']}")
                print(f"Files skipped: {result['skipped_files']}")
                print(f"Semantic units indexed: {result['total_units']}")
                print(f"Total time: {elapsed:.2f}s")

                if result['failed_files']:
                    print(f"\nFailed files ({len(result['failed_files'])}):")
                    for failed_file in result['failed_files']:
                        print(f"  - {failed_file}")

                print("=" * 60 + "\n")

                # Calculate throughput
                if result['indexed_files'] > 0:
                    files_per_sec = result['indexed_files'] / elapsed
                    units_per_sec = result['total_units'] / elapsed
                    print(f"Throughput: {files_per_sec:.2f} files/sec, {units_per_sec:.2f} units/sec\n")

            else:
                logger.error(f"Path is neither a file nor directory: {path}")

        except Exception as e:
            logger.error(f"Indexing failed: {e}", exc_info=True)
            print(f"\nERROR: Indexing failed - {e}\n")
            raise

        finally:
            await indexer.close()
