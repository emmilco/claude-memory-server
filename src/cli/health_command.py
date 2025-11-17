"""Health check command for diagnosing system status."""

import asyncio
import sys
import subprocess
import shutil
import logging
from pathlib import Path
from typing import Dict, Any, Tuple, Optional, List

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

logger = logging.getLogger(__name__)


class HealthCommand:
    """Health check command to diagnose system status."""

    def __init__(self):
        """Initialize health check command."""
        self.console = Console() if RICH_AVAILABLE else None
        self.checks = {}
        self.errors = []
        self.warnings = []
        self.recommendations = []

    def print_section(self, title: str):
        """Print section header."""
        if self.console:
            self.console.print(f"\n[bold cyan]{title}[/bold cyan]")
        else:
            print(f"\n{title}")
            print("=" * len(title))

    def print_check(self, name: str, status: bool, message: str):
        """Print individual check result."""
        if self.console:
            if status:
                self.console.print(f"  [green]✓[/green] {name:30s} {message}")
            else:
                self.console.print(f"  [red]✗[/red] {name:30s} {message}")
        else:
            symbol = "✓" if status else "✗"
            print(f"  {symbol} {name:30s} {message}")

    def print_warning(self, name: str, message: str):
        """Print warning."""
        if self.console:
            self.console.print(f"  [yellow]⚠[/yellow] {name:30s} {message}")
        else:
            print(f"  ⚠ {name:30s} {message}")

    async def check_python_version(self) -> Tuple[bool, str]:
        """Check Python version."""
        version = sys.version_info
        version_str = f"{version.major}.{version.minor}.{version.micro}"

        if version.major >= 3 and version.minor >= 8:
            return True, version_str
        else:
            return False, f"{version_str} (requires 3.8+)"

    async def check_disk_space(self) -> Tuple[bool, str]:
        """Check available disk space."""
        try:
            home = Path.home()
            stat = shutil.disk_usage(home)
            free_gb = stat.free / (1024**3)

            if free_gb >= 0.5:
                return True, f"{free_gb:.1f} GB available"
            else:
                return False, f"{free_gb:.1f} GB (need 0.5 GB minimum)"
        except Exception as e:
            return False, f"Could not check: {e}"

    async def check_memory(self) -> Tuple[bool, str]:
        """Check available memory."""
        try:
            # Try to get memory info (platform-specific)
            if sys.platform == "darwin":  # macOS
                result = subprocess.run(
                    ["sysctl", "hw.memsize"],
                    capture_output=True,
                    text=True,
                    timeout=2,
                )
                if result.returncode == 0:
                    mem_bytes = int(result.stdout.split(":")[1].strip())
                    mem_gb = mem_bytes / (1024**3)
                    return True, f"{mem_gb:.1f} GB total"

            # Generic fallback
            return True, "Available (exact amount unknown)"
        except Exception:
            return True, "Unknown"

    async def check_rust_parser(self) -> Tuple[bool, str]:
        """Check if Rust parser is available."""
        try:
            import mcp_performance_core
            return True, "Available (optimal performance)"
        except ImportError:
            return False, "Not available (using Python fallback)"

    async def check_python_parser(self) -> Tuple[bool, str]:
        """Check if Python parser fallback is available."""
        try:
            from src.memory.python_parser import get_parser
            parser = get_parser()
            return True, "Available (fallback mode)"
        except ImportError as e:
            return False, f"Not available: {e}"

    async def check_storage_backend(self) -> Tuple[bool, str, str]:
        """Check storage backend."""
        from src.config import get_config

        config = get_config()
        backend = config.storage_backend

        if backend == "sqlite":
            # Check SQLite
            db_path = config.sqlite_path_expanded
            if db_path.exists():
                size_mb = db_path.stat().st_size / (1024**2)
                return True, "SQLite", f"{db_path} ({size_mb:.1f} MB)"
            else:
                return True, "SQLite", f"{db_path} (not yet created)"

        elif backend == "qdrant":
            # Check Qdrant connection
            try:
                result = subprocess.run(
                    ["curl", "-s", f"{config.qdrant_url}/health"],
                    capture_output=True,
                    text=True,
                    timeout=2,
                )
                if result.returncode == 0 and "ok" in result.stdout.lower():
                    return True, "Qdrant", f"Running at {config.qdrant_url}"
                else:
                    return False, "Qdrant", f"Not reachable at {config.qdrant_url}"
            except Exception as e:
                return False, "Qdrant", f"Error checking: {e}"

        return False, "Unknown", "Unknown backend"

    async def check_embedding_model(self) -> Tuple[bool, str]:
        """Check if embedding model can be loaded."""
        try:
            from src.embeddings.generator import EmbeddingGenerator
            from src.config import get_config

            config = get_config()
            gen = EmbeddingGenerator(config)

            # Try to generate a test embedding
            embedding = await gen.generate("test")
            return True, f"{config.embedding_model} ({len(embedding)} dimensions)"
        except Exception as e:
            return False, f"Error loading: {str(e)[:50]}"

    async def check_embedding_cache(self) -> Tuple[bool, str]:
        """Check embedding cache."""
        from src.config import get_config

        config = get_config()
        cache_path = config.embedding_cache_path_expanded

        if cache_path.exists():
            size_mb = cache_path.stat().st_size / (1024**2)

            # Try to get cache stats
            try:
                from src.embeddings.cache import EmbeddingCache
                cache = EmbeddingCache(config)
                stats = cache.get_stats()
                hit_rate = stats.get("hit_rate", 0)
                return True, f"{cache_path} ({size_mb:.1f} MB, {hit_rate*100:.1f}% hit rate)"
            except Exception:
                return True, f"{cache_path} ({size_mb:.1f} MB)"
        else:
            return True, "Not yet created"

    async def check_indexed_projects(self) -> Tuple[bool, str, List[Dict[str, Any]]]:
        """Check indexed projects."""
        try:
            from src.store import create_memory_store
            from src.config import get_config

            config = get_config()
            store = create_memory_store(config=config)
            await store.initialize()

            # Try to get project stats
            # This is a simplified check - actual implementation would query the store
            projects = []  # Would need to implement project listing

            return True, f"{len(projects)} projects indexed", projects
        except Exception as e:
            return False, f"Error checking: {str(e)[:50]}", []

    async def run_checks(self):
        """Run all health checks."""
        # System Requirements
        self.print_section("System Requirements")

        success, msg = await self.check_python_version()
        self.print_check("Python version", success, msg)
        if not success:
            self.errors.append("Python 3.8+ required")

        success, msg = await self.check_disk_space()
        if success:
            self.print_check("Disk space", True, msg)
        else:
            self.print_warning("Disk space", msg)
            self.warnings.append("Low disk space")

        success, msg = await self.check_memory()
        self.print_check("Memory (RAM)", success, msg)

        # Parser
        self.print_section("Code Parser")

        rust_available, rust_msg = await self.check_rust_parser()
        python_available, python_msg = await self.check_python_parser()

        if rust_available:
            self.print_check("Rust parser", True, rust_msg)
        else:
            self.print_warning("Rust parser", rust_msg)
            if python_available:
                self.print_check("Python fallback", True, python_msg)
                self.recommendations.append(
                    "Install Rust parser for 10-20x faster indexing: python setup.py --build-rust"
                )
            else:
                self.print_check("Python fallback", False, python_msg)
                self.errors.append("No parser available")

        # Storage Backend
        self.print_section("Storage Backend")

        success, backend, msg = await self.check_storage_backend()
        if success:
            self.print_check(backend, True, msg)
            if backend == "SQLite":
                self.recommendations.append(
                    "Consider upgrading to Qdrant for better performance: python setup.py --upgrade-to-qdrant"
                )
        else:
            self.print_check(backend, False, msg)
            self.errors.append(f"{backend} not accessible")

        # Embedding Model
        self.print_section("Embedding Model")

        success, msg = await self.check_embedding_model()
        if success:
            self.print_check("Model loaded", True, msg)
        else:
            self.print_check("Model loaded", False, msg)
            self.errors.append("Cannot load embedding model")

        success, msg = await self.check_embedding_cache()
        if success:
            self.print_check("Embedding cache", True, msg)
        else:
            self.print_warning("Embedding cache", msg)

    def print_summary(self):
        """Print health check summary."""
        self.print_section("Summary")

        if not self.errors and not self.warnings:
            if self.console:
                self.console.print("\n[bold green]✓ All systems healthy![/bold green]\n")
            else:
                print("\n✓ All systems healthy!\n")
        else:
            if self.errors:
                if self.console:
                    self.console.print(f"\n[bold red]✗ {len(self.errors)} error(s) found:[/bold red]")
                    for error in self.errors:
                        self.console.print(f"  • {error}")
                else:
                    print(f"\n✗ {len(self.errors)} error(s) found:")
                    for error in self.errors:
                        print(f"  • {error}")

            if self.warnings:
                if self.console:
                    self.console.print(f"\n[bold yellow]⚠ {len(self.warnings)} warning(s):[/bold yellow]")
                    for warning in self.warnings:
                        self.console.print(f"  • {warning}")
                else:
                    print(f"\n⚠ {len(self.warnings)} warning(s):")
                    for warning in self.warnings:
                        print(f"  • {warning}")

        if self.recommendations:
            if self.console:
                self.console.print(f"\n[bold cyan]Recommendations:[/bold cyan]")
                for rec in self.recommendations:
                    self.console.print(f"  • {rec}")
            else:
                print("\nRecommendations:")
                for rec in self.recommendations:
                    print(f"  • {rec}")

        print()

    async def run(self, args):
        """Run health check command."""
        if self.console:
            self.console.print()
            self.console.print(
                Panel.fit(
                    "[bold blue]Claude Memory RAG Server - Health Check[/bold blue]",
                    border_style="blue",
                )
            )
        else:
            print("\nClaude Memory RAG Server - Health Check")
            print("=" * 50)

        await self.run_checks()
        self.print_summary()

        # Exit with error code if there are errors
        if self.errors:
            sys.exit(1)
        else:
            sys.exit(0)
