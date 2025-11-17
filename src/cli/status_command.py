"""Status command showing indexed projects and system statistics."""

import asyncio
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
from collections import defaultdict

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.columns import Columns
    from rich.text import Text
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

logger = logging.getLogger(__name__)


class StatusCommand:
    """Status command to show indexed projects and statistics."""

    def __init__(self):
        """Initialize status command."""
        self.console = Console() if RICH_AVAILABLE else None

    def _format_size(self, bytes_size: int) -> str:
        """Format bytes to human-readable size."""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if bytes_size < 1024.0:
                return f"{bytes_size:.1f} {unit}"
            bytes_size /= 1024.0
        return f"{bytes_size:.1f} TB"

    def _format_time_ago(self, dt: Optional[datetime]) -> str:
        """Format datetime as time ago."""
        if not dt:
            return "Never"

        now = datetime.now(dt.tzinfo) if dt.tzinfo else datetime.now()
        delta = now - dt

        if delta.days > 0:
            return f"{delta.days}d ago"
        elif delta.seconds > 3600:
            hours = delta.seconds // 3600
            return f"{hours}h ago"
        elif delta.seconds > 60:
            minutes = delta.seconds // 60
            return f"{minutes}m ago"
        else:
            return "Just now"

    async def get_storage_stats(self) -> Dict[str, Any]:
        """Get storage backend statistics."""
        from src.config import get_config
        from src.store import create_memory_store

        config = get_config()
        store = create_memory_store(config=config)

        try:
            await store.initialize()

            stats = {
                "backend": config.storage_backend,
                "connected": True,
            }

            if config.storage_backend == "sqlite":
                db_path = config.sqlite_path_expanded
                if db_path.exists():
                    stats["path"] = str(db_path)
                    stats["size"] = db_path.stat().st_size
                else:
                    stats["path"] = str(db_path)
                    stats["size"] = 0

            elif config.storage_backend == "qdrant":
                stats["url"] = config.qdrant_url
                stats["collection"] = config.qdrant_collection_name

            return stats

        except Exception as e:
            logger.error(f"Error getting storage stats: {e}")
            return {
                "backend": config.storage_backend,
                "connected": False,
                "error": str(e),
            }

    async def get_cache_stats(self) -> Dict[str, Any]:
        """Get embedding cache statistics."""
        from src.config import get_config
        from src.embeddings.cache import EmbeddingCache

        config = get_config()
        cache_path = config.embedding_cache_path_expanded

        try:
            cache = EmbeddingCache(config)
            stats = cache.get_stats()

            result = {
                "path": str(cache_path),
                "exists": cache_path.exists(),
            }

            if cache_path.exists():
                result["size"] = cache_path.stat().st_size
                result["total_entries"] = stats.get("total_entries", 0)
                result["hits"] = stats.get("hits", 0)
                result["misses"] = stats.get("misses", 0)
                result["hit_rate"] = stats.get("hit_rate", 0.0)

            return result

        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
            return {
                "path": str(cache_path),
                "exists": cache_path.exists(),
                "error": str(e),
            }

    async def get_indexed_projects(self) -> List[Dict[str, Any]]:
        """Get list of indexed projects with statistics."""
        from src.config import get_config
        from src.store import create_memory_store

        config = get_config()
        store = create_memory_store(config=config)

        try:
            await store.initialize()

            # Get all project names
            project_names = await store.get_all_projects()

            # Get stats for each project
            projects = []
            for project_name in project_names:
                try:
                    stats = await store.get_project_stats(project_name)
                    projects.append(stats)
                except Exception as e:
                    logger.warning(f"Error getting stats for {project_name}: {e}")
                    # Add minimal info if stats fail
                    projects.append({
                        "project_name": project_name,
                        "total_memories": 0,
                        "num_files": 0,
                        "num_functions": 0,
                        "num_classes": 0,
                    })

            return projects

        except Exception as e:
            logger.error(f"Error getting indexed projects: {e}")
            return []

    async def get_parser_info(self) -> Dict[str, Any]:
        """Get parser information."""
        from src.memory.incremental_indexer import PARSER_MODE, RUST_AVAILABLE

        return {
            "mode": PARSER_MODE,
            "rust_available": RUST_AVAILABLE,
            "description": "Optimal performance" if RUST_AVAILABLE else "Fallback mode (10-20x slower)",
        }

    async def get_embedding_model_info(self) -> Dict[str, Any]:
        """Get embedding model information."""
        from src.config import get_config

        config = get_config()

        return {
            "model": config.embedding_model,
            "dimensions": 384,  # all-MiniLM-L6-v2
            "batch_size": config.embedding_batch_size,
        }

    def print_header(self):
        """Print status header."""
        if self.console:
            self.console.print()
            self.console.print(
                Panel.fit(
                    "[bold blue]Claude Memory RAG Server - Status[/bold blue]\n"
                    f"[dim]{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}[/dim]",
                    border_style="blue",
                )
            )
            self.console.print()
        else:
            print("\nClaude Memory RAG Server - Status")
            print("=" * 50)
            print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    def print_storage_stats(self, stats: Dict[str, Any]):
        """Print storage statistics."""
        if self.console:
            self.console.print("[bold cyan]Storage Backend[/bold cyan]")

            backend = stats.get("backend", "unknown")
            self.console.print(f"  Type: [yellow]{backend.upper()}[/yellow]")

            if stats.get("connected"):
                self.console.print("  Status: [green]✓ Connected[/green]")

                if backend == "sqlite":
                    path = stats.get("path", "unknown")
                    size = self._format_size(stats.get("size", 0))
                    self.console.print(f"  Path: {path}")
                    self.console.print(f"  Size: {size}")

                elif backend == "qdrant":
                    url = stats.get("url", "unknown")
                    collection = stats.get("collection", "unknown")
                    self.console.print(f"  URL: {url}")
                    self.console.print(f"  Collection: {collection}")
            else:
                self.console.print(f"  Status: [red]✗ Disconnected[/red]")
                if "error" in stats:
                    self.console.print(f"  Error: [red]{stats['error']}[/red]")

            self.console.print()
        else:
            print("Storage Backend")
            print(f"  Type: {stats.get('backend', 'unknown').upper()}")
            print(f"  Status: {'Connected' if stats.get('connected') else 'Disconnected'}")

    def print_cache_stats(self, stats: Dict[str, Any]):
        """Print cache statistics."""
        if self.console:
            self.console.print("[bold cyan]Embedding Cache[/bold cyan]")

            if stats.get("exists"):
                path = stats.get("path", "unknown")
                size = self._format_size(stats.get("size", 0))
                entries = stats.get("total_entries", 0)
                hit_rate = stats.get("hit_rate", 0.0) * 100

                self.console.print(f"  Path: {path}")
                self.console.print(f"  Size: {size}")
                self.console.print(f"  Entries: {entries:,}")

                if hit_rate > 0:
                    hit_rate_color = "green" if hit_rate > 80 else "yellow" if hit_rate > 50 else "red"
                    self.console.print(f"  Hit Rate: [{hit_rate_color}]{hit_rate:.1f}%[/{hit_rate_color}]")
            else:
                self.console.print("  [dim]No cache created yet[/dim]")

            self.console.print()
        else:
            print("\nEmbedding Cache")
            if stats.get("exists"):
                print(f"  Entries: {stats.get('total_entries', 0):,}")
                print(f"  Hit Rate: {stats.get('hit_rate', 0.0) * 100:.1f}%")
            else:
                print("  No cache created yet")

    def print_parser_info(self, info: Dict[str, Any]):
        """Print parser information."""
        if self.console:
            self.console.print("[bold cyan]Code Parser[/bold cyan]")

            mode = info.get("mode", "unknown")
            rust_available = info.get("rust_available", False)

            if rust_available:
                self.console.print(f"  Mode: [green]Rust[/green] (optimal)")
            else:
                self.console.print(f"  Mode: [yellow]Python Fallback[/yellow]")
                self.console.print("  [dim]Install Rust for 10-20x faster parsing:[/dim]")
                self.console.print("  [dim]python setup.py --build-rust[/dim]")

            self.console.print()
        else:
            print("\nCode Parser")
            print(f"  Mode: {info.get('mode', 'unknown')}")

    def print_embedding_info(self, info: Dict[str, Any]):
        """Print embedding model information."""
        if self.console:
            self.console.print("[bold cyan]Embedding Model[/bold cyan]")

            model = info.get("model", "unknown")
            dimensions = info.get("dimensions", 0)
            batch_size = info.get("batch_size", 0)

            self.console.print(f"  Model: {model}")
            self.console.print(f"  Dimensions: {dimensions}")
            self.console.print(f"  Batch Size: {batch_size}")

            self.console.print()
        else:
            print("\nEmbedding Model")
            print(f"  Model: {info.get('model', 'unknown')}")
            print(f"  Dimensions: {info.get('dimensions', 0)}")

    def print_projects_table(self, projects: List[Dict[str, Any]]):
        """Print indexed projects table."""
        if not projects:
            if self.console:
                self.console.print("[bold cyan]Indexed Projects[/bold cyan]")
                self.console.print("  [dim]No projects indexed yet[/dim]")
                self.console.print("  [dim]Run: python -m src.cli index ./your-project[/dim]")
                self.console.print()
            else:
                print("\nIndexed Projects")
                print("  No projects indexed yet")
                print("  Run: python -m src.cli index ./your-project")
            return

        if self.console:
            self.console.print("[bold cyan]Indexed Projects[/bold cyan]\n")

            table = Table(show_header=True, header_style="bold")
            table.add_column("Project", style="cyan")
            table.add_column("Memories", justify="right")
            table.add_column("Files", justify="right")
            table.add_column("Functions", justify="right")
            table.add_column("Classes", justify="right")
            table.add_column("Last Indexed", justify="right")

            for project in projects:
                table.add_row(
                    project.get("project_name", "unknown"),
                    str(project.get("total_memories", 0)),
                    str(project.get("num_files", 0)),
                    str(project.get("num_functions", 0)),
                    str(project.get("num_classes", 0)),
                    self._format_time_ago(project.get("last_indexed")),
                )

            self.console.print(table)
            self.console.print()
        else:
            print("\nIndexed Projects")
            for project in projects:
                print(f"  {project.get('project_name', 'unknown')}")
                print(f"    Memories: {project.get('total_memories', 0)}")
                print(f"    Files: {project.get('num_files', 0)}")
                print(f"    Functions: {project.get('num_functions', 0)}")
                print(f"    Classes: {project.get('num_classes', 0)}")

    def print_quick_commands(self):
        """Print quick reference commands."""
        if self.console:
            self.console.print("[bold cyan]Quick Commands[/bold cyan]")
            self.console.print("  [dim]Index a project:[/dim]   python -m src.cli index ./path/to/project")
            self.console.print("  [dim]Health check:[/dim]      python -m src.cli health")
            self.console.print("  [dim]Watch for changes:[/dim] python -m src.cli watch ./path/to/project")
            self.console.print()
        else:
            print("\nQuick Commands")
            print("  Index: python -m src.cli index ./path")
            print("  Health: python -m src.cli health")
            print("  Watch: python -m src.cli watch ./path")

    async def run(self, args):
        """Run status command."""
        self.print_header()

        # Gather all stats
        storage_stats = await self.get_storage_stats()
        cache_stats = await self.get_cache_stats()
        parser_info = await self.get_parser_info()
        embedding_info = await self.get_embedding_model_info()
        projects = await self.get_indexed_projects()

        # Print sections
        self.print_storage_stats(storage_stats)
        self.print_cache_stats(cache_stats)
        self.print_parser_info(parser_info)
        self.print_embedding_info(embedding_info)
        self.print_projects_table(projects)
        self.print_quick_commands()
