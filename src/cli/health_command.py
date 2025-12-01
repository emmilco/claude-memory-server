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
        self.storage_backend = None

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
                    parts = result.stdout.split(":")
                    if len(parts) > 1:
                        mem_bytes = int(parts[1].strip())
                        mem_gb = mem_bytes / (1024**3)
                        return True, f"{mem_gb:.1f} GB total"

            # Generic fallback
            return True, "Available (exact amount unknown)"
        except Exception as e:
            logger.debug(f"Failed to check memory: {e}")
            return True, "Unknown"

    async def check_rust_parser(self) -> Tuple[bool, str]:
        """Check if Rust parser is available."""
        try:
            import mcp_performance_core
            return True, "Available (optimal performance)"
        except ImportError:
            return False, "Not available (using Python fallback)"

    async def check_python_parser(self) -> Tuple[bool, str]:
        """Check if Python parser fallback is available.

        Note: Python parser fallback was removed (it was broken, returned 0 units).
        Rust parser is now required. This method is kept for backward compatibility.
        """
        # Python parser was removed - Rust parser is now required
        return False, "Removed (Rust parser is now required)"

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
                    ["curl", "-s", f"{config.qdrant_url}/"],
                    capture_output=True,
                    text=True,
                    timeout=2,
                )
                # Qdrant root endpoint returns JSON with "version" field
                if result.returncode == 0 and "version" in result.stdout.lower():
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
            except Exception as e:
                logger.debug(f"Failed to get cache stats: {e}")
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

            # Get all projects
            projects = await store.get_all_projects()

            # Get stats for each project
            project_stats = []
            for project_name in projects:
                try:
                    stats = await store.get_project_stats(project_name)
                    project_stats.append(stats)
                except Exception as e:
                    logger.debug(f"Failed to get stats for project '{project_name}': {e}")

            await store.close()

            return True, f"{len(projects)} projects indexed", project_stats
        except Exception as e:
            return False, f"Error checking: {str(e)[:50]}", []

    async def check_qdrant_latency(self) -> Tuple[bool, str, Optional[float]]:
        """Check Qdrant query latency."""
        try:
            from src.store import create_memory_store
            from src.config import get_config
            import time

            config = get_config()

            # Only check if using Qdrant
            if config.storage_backend != "qdrant":
                return True, "N/A (using SQLite)", None

            store = create_memory_store(config=config)
            await store.initialize()

            # Perform a simple query and time it
            start = time.time()
            try:
                # Try a simple retrieval or count operation
                if hasattr(store, 'client'):
                    # For Qdrant, do a simple collection check
                    store.client.get_collection(store.collection_name)
            except Exception as e:
                logger.debug(f"Qdrant collection check failed during latency test: {e}")
            latency_ms = (time.time() - start) * 1000

            await store.close()

            if latency_ms < 20:
                return True, f"{latency_ms:.1f}ms (excellent)", latency_ms
            elif latency_ms < 50:
                return True, f"{latency_ms:.1f}ms (good)", latency_ms
            else:
                return False, f"{latency_ms:.1f}ms (slow - check Docker resources)", latency_ms

        except Exception as e:
            return False, f"Could not measure: {str(e)[:40]}", None

    async def check_cache_hit_rate(self) -> Tuple[bool, str, Optional[float]]:
        """Check embedding cache hit rate."""
        try:
            from src.embeddings.cache import EmbeddingCache
            from src.config import get_config

            config = get_config()
            cache = EmbeddingCache(config)

            stats = cache.get_stats()
            total = stats.get("total_queries", 0)
            hits = stats.get("cache_hits", 0)

            if total == 0:
                return True, "No queries yet", None

            hit_rate = (hits / total) * 100

            if hit_rate >= 70:
                return True, f"{hit_rate:.1f}% ({hits}/{total} hits)", hit_rate
            else:
                return False, f"{hit_rate:.1f}% (low - consider re-indexing)", hit_rate

        except Exception as e:
            return False, f"Could not check: {str(e)[:40]}", None

    async def check_stale_projects(self) -> Tuple[bool, str, List[Dict[str, Any]]]:
        """Check for projects not indexed recently."""
        try:
            from src.store import create_memory_store
            from src.config import get_config
            from datetime import datetime, timedelta, UTC

            config = get_config()
            store = create_memory_store(config=config)
            await store.initialize()

            # Get all projects with stats
            projects = await store.get_all_projects()
            stale_projects = []

            threshold = datetime.now(UTC) - timedelta(days=30)

            for project_name in projects:
                try:
                    stats = await store.get_project_stats(project_name)
                    last_updated = stats.get("last_updated")

                    if last_updated:
                        if isinstance(last_updated, str):
                            last_updated = datetime.fromisoformat(last_updated.replace('Z', '+00:00'))

                        # Make timezone-aware if needed
                        if last_updated.tzinfo is None:
                            last_updated = last_updated.replace(tzinfo=UTC)

                        if last_updated < threshold:
                            days_old = (datetime.now(UTC) - last_updated).days
                            stale_projects.append({
                                "name": project_name,
                                "days_old": days_old,
                                "last_updated": last_updated
                            })
                except Exception as e:
                    logger.debug(f"Failed to check staleness for project '{project_name}': {e}")

            await store.close()

            if not stale_projects:
                return True, "All projects current", []
            else:
                return False, f"{len(stale_projects)} projects not indexed in 30+ days", stale_projects

        except Exception as e:
            return False, f"Could not check: {str(e)[:40]}", []

    async def estimate_token_savings(self) -> Tuple[bool, str, Optional[int]]:
        """Estimate tokens saved via caching this week."""
        try:
            from src.embeddings.cache import EmbeddingCache
            from src.config import get_config

            config = get_config()
            cache = EmbeddingCache(config)

            stats = cache.get_stats()
            hits = stats.get("cache_hits", 0)

            if hits == 0:
                return True, "No cache hits yet", 0

            # Estimate: average embedding text ~100 tokens
            # Each cache hit saves ~100 tokens from not re-processing
            estimated_tokens = hits * 100

            if estimated_tokens >= 1000000:
                return True, f"~{estimated_tokens/1000000:.1f}M tokens saved ({hits:,} cache hits)", estimated_tokens
            elif estimated_tokens >= 1000:
                return True, f"~{estimated_tokens/1000:.1f}K tokens saved ({hits:,} cache hits)", estimated_tokens
            else:
                return True, f"~{estimated_tokens} tokens saved ({hits:,} cache hits)", estimated_tokens

        except Exception as e:
            return False, f"Could not estimate: {str(e)[:40]}", None

    async def get_project_stats_summary(self) -> Dict[str, Any]:
        """Get overall project statistics summary."""
        try:
            from src.store import create_memory_store
            from src.config import get_config
            from pathlib import Path

            config = get_config()
            store = create_memory_store(config=config)
            await store.initialize()

            projects = await store.get_all_projects()
            total_memories = 0
            total_files = 0

            for project_name in projects:
                try:
                    stats = await store.get_project_stats(project_name)
                    total_memories += stats.get("total_memories", 0)
                    total_files += stats.get("total_files", 0)
                except Exception as e:
                    logger.debug(f"Failed to get stats for project '{project_name}' during index size check: {e}")

            await store.close()

            # Get index size
            index_size = 0
            if config.storage_backend == "sqlite":
                db_path = config.sqlite_path_expanded
                if db_path.exists():
                    index_size = db_path.stat().st_size

            # Get cache size
            cache_path = config.embedding_cache_path_expanded
            if cache_path.exists():
                index_size += cache_path.stat().st_size

            return {
                "total_projects": len(projects),
                "total_memories": total_memories,
                "total_files": total_files,
                "index_size_bytes": index_size,
            }

        except Exception as e:
            logger.error(f"Error getting project stats: {e}")
            return {
                "total_projects": 0,
                "total_memories": 0,
                "total_files": 0,
                "index_size_bytes": 0,
            }

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
        # Store backend for later use
        self.storage_backend = backend if success else None

        if success:
            self.print_check(backend, True, msg)
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

        # Performance Metrics
        self.print_section("Performance Metrics")

        success, msg, latency = await self.check_qdrant_latency()
        if success:
            self.print_check("Qdrant latency", True, msg)
        else:
            self.print_warning("Qdrant latency", msg)
            if latency and latency >= 50:
                self.warnings.append(f"Slow Qdrant latency ({latency:.1f}ms)")
                self.recommendations.append(
                    "Increase Docker resources (CPU/RAM) or check network connectivity"
                )

        success, msg, hit_rate = await self.check_cache_hit_rate()
        if success:
            self.print_check("Cache hit rate", True, msg)
        else:
            self.print_warning("Cache hit rate", msg)
            if hit_rate is not None and hit_rate < 70:
                self.warnings.append(f"Low cache hit rate ({hit_rate:.1f}%)")
                self.recommendations.append(
                    "Consider re-indexing projects to improve cache performance"
                )

        success, msg, tokens = await self.estimate_token_savings()
        if success:
            self.print_check("Token savings", True, msg)
        else:
            self.print_warning("Token savings", msg)

        # Project Health
        self.print_section("Project Health")

        success, msg, stale = await self.check_stale_projects()
        if success:
            self.print_check("Stale projects", True, msg)
        else:
            self.print_warning("Stale projects", msg)
            if stale:
                self.warnings.append(f"{len(stale)} stale projects (30+ days old)")
                for project in stale[:3]:  # Show up to 3
                    project_name = project['name']
                    days = project['days_old']
                    self.recommendations.append(
                        f"Re-index '{project_name}' ({days} days old): python -m src.cli index <path>"
                    )

        # Get project stats summary
        stats = await self.get_project_stats_summary()
        if stats['total_projects'] > 0:
            size_mb = stats['index_size_bytes'] / (1024 * 1024)
            summary_msg = f"{stats['total_projects']} projects | {stats['total_memories']:,} memories | {size_mb:.1f} MB"
            self.print_check("Project summary", True, summary_msg)

            # Add smart recommendations based on stats
            if self.storage_backend == "SQLite" and stats['total_memories'] > 10000:
                self.recommendations.append(
                    f"📊 Using SQLite with {stats['total_memories']:,} memories - consider upgrading to Qdrant for better performance"
                )
                self.recommendations.append(
                    "   → Run: docker-compose up -d && python setup.py --upgrade-to-qdrant"
                )

            if size_mb > 500:
                self.recommendations.append(
                    f"💾 Large index size ({size_mb:.0f} MB) - consider archiving old memories"
                )
        else:
            self.print_warning("Project summary", "No projects indexed yet")
            self.recommendations.append(
                "🚀 Get started: python -m src.cli index ./your-project --project-name my-project"
            )

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
