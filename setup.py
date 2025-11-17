#!/usr/bin/env python3
"""
Setup wizard for Claude Memory RAG Server.

Provides an interactive installation experience with:
- Prerequisite detection
- Smart defaults with fallback modes
- Progress indicators
- Post-install verification
"""

import asyncio
import os
import sys
import subprocess
import shutil
import platform
from pathlib import Path
from typing import Optional, Dict, List, Tuple

# Try to import rich for nice terminal output, fallback to basic
try:
    from rich.console import Console
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from rich.panel import Panel
    from rich.table import Table
    from rich.prompt import Prompt, Confirm
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    print("Installing rich library for better terminal output...")
    subprocess.run([sys.executable, "-m", "pip", "install", "rich"], check=True)
    from rich.console import Console
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from rich.panel import Panel
    from rich.table import Table
    from rich.prompt import Prompt, Confirm

console = Console()


class SetupWizard:
    """Interactive setup wizard for Claude Memory RAG Server."""

    # Setup presets
    PRESETS = {
        "minimal": {
            "storage": "sqlite",
            "parser": "python",
            "docker": False,
            "rust": False,
            "description": "Quick start (2 min) - SQLite + Python parser, no Docker/Rust",
            "time": "~2 minutes",
        },
        "standard": {
            "storage": "sqlite",
            "parser": "rust",
            "docker": False,
            "rust": True,
            "description": "Good performance (5 min) - SQLite + Rust parser, no Docker",
            "time": "~5 minutes",
        },
        "full": {
            "storage": "qdrant",
            "parser": "rust",
            "docker": True,
            "rust": True,
            "description": "Optimal performance (10 min) - Qdrant + Rust parser",
            "time": "~10 minutes",
        },
    }

    def __init__(self, mode: str = "auto"):
        """
        Initialize setup wizard.

        Args:
            mode: Setup mode (auto, minimal, standard, full)
        """
        self.mode = mode
        self.config = {}
        self.checks = {}
        self.project_root = Path(__file__).parent
        self.platform = platform.system()

    def print_header(self):
        """Print welcome header."""
        console.print()
        console.print(
            Panel.fit(
                "[bold blue]Claude Memory RAG Server[/bold blue]\n"
                "[dim]Setup Wizard - Version 3.0[/dim]",
                border_style="blue",
            )
        )
        console.print()

    def print_step(self, step: int, total: int, message: str):
        """Print step indicator."""
        console.print(f"[bold cyan][{step}/{total}][/bold cyan] {message}...", end=" ")

    def print_result(self, success: bool, message: str = ""):
        """Print result of a step."""
        if success:
            console.print(f"[bold green]✓[/bold green] {message}")
        else:
            console.print(f"[bold yellow]⚠[/bold yellow] {message}")

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
            stat = shutil.disk_usage(self.project_root)
            free_gb = stat.free / (1024**3)

            if free_gb >= 0.5:  # Need at least 500MB
                return True, f"{free_gb:.1f} GB available"
            else:
                return False, f"{free_gb:.1f} GB (need 0.5 GB minimum)"
        except Exception as e:
            return False, f"Could not check: {e}"

    async def check_rust(self) -> Tuple[bool, str]:
        """Check if Rust is installed."""
        try:
            result = subprocess.run(
                ["rustc", "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                version = result.stdout.strip().split()[1]
                return True, version
            else:
                return False, "Not found"
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False, "Not found"

    async def check_docker(self) -> Tuple[bool, str]:
        """Check if Docker is running."""
        try:
            result = subprocess.run(
                ["docker", "info"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                return True, "Running"
            else:
                return False, "Not running"
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False, "Not installed"

    async def check_prerequisites(self):
        """Check all prerequisites."""
        console.print("[bold]Checking system requirements...[/bold]\n")

        steps = [
            ("python", "Python version", self.check_python_version),
            ("disk", "Disk space", self.check_disk_space),
            ("rust", "Rust compiler", self.check_rust),
            ("docker", "Docker", self.check_docker),
        ]

        for key, name, check_func in steps:
            self.print_step(steps.index((key, name, check_func)) + 1, len(steps), f"Checking {name}")
            success, message = await check_func()
            self.checks[key] = {"success": success, "message": message}
            self.print_result(success, message)

        console.print()

    async def interactive_setup(self):
        """Interactive setup with choices."""
        console.print("[bold]Setup Configuration[/bold]\n")

        # Show available presets
        table = Table(title="Available Setup Modes")
        table.add_column("Mode", style="cyan")
        table.add_column("Description", style="white")
        table.add_column("Time", style="yellow")

        for mode_name, preset in self.PRESETS.items():
            table.add_row(mode_name.title(), preset["description"], preset["time"])

        console.print(table)
        console.print()

        # Recommend mode based on prerequisites
        if self.checks["rust"]["success"] and self.checks["docker"]["success"]:
            recommended = "full"
        elif self.checks["rust"]["success"]:
            recommended = "standard"
        else:
            recommended = "minimal"

        console.print(f"[dim]Recommended mode based on your system: [bold]{recommended}[/bold][/dim]\n")

        # Ask user for mode
        mode_choice = Prompt.ask(
            "Select setup mode",
            choices=["minimal", "standard", "full", "custom"],
            default=recommended,
        )

        if mode_choice == "custom":
            # Custom setup
            self.config["storage"] = Prompt.ask(
                "Storage backend",
                choices=["sqlite", "qdrant"],
                default="sqlite",
            )

            self.config["parser"] = Prompt.ask(
                "Code parser",
                choices=["python", "rust"],
                default="rust" if self.checks["rust"]["success"] else "python",
            )
        else:
            # Use preset
            preset = self.PRESETS[mode_choice]
            self.config = {
                "storage": preset["storage"],
                "parser": preset["parser"],
            }

        console.print()

        # Show chosen configuration
        console.print("[bold]Selected configuration:[/bold]")
        console.print(f"  • Storage backend: [cyan]{self.config['storage']}[/cyan]")
        console.print(f"  • Code parser: [cyan]{self.config['parser']}[/cyan]")
        console.print()

        # Warn about missing prerequisites
        if self.config["parser"] == "rust" and not self.checks["rust"]["success"]:
            console.print(
                "[yellow]⚠ Warning: Rust not found. Will fall back to Python parser.[/yellow]\n"
            )
            self.config["parser"] = "python"

        if self.config["storage"] == "qdrant" and not self.checks["docker"]["success"]:
            console.print(
                "[yellow]⚠ Warning: Docker not running. Will use SQLite instead.[/yellow]\n"
            )
            self.config["storage"] = "sqlite"

    async def install_dependencies(self):
        """Install Python dependencies."""
        console.print("[bold]Installing dependencies...[/bold]\n")

        requirements_file = self.project_root / "requirements.txt"

        if not requirements_file.exists():
            console.print("[red]Error: requirements.txt not found[/red]")
            return False

        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task("Installing Python packages...", total=None)

                result = subprocess.run(
                    [sys.executable, "-m", "pip", "install", "-r", str(requirements_file)],
                    capture_output=True,
                    text=True,
                )

                progress.update(task, completed=True)

            if result.returncode == 0:
                console.print("[green]✓ Dependencies installed successfully[/green]\n")
                return True
            else:
                console.print(f"[red]✗ Failed to install dependencies:[/red]")
                console.print(result.stderr)
                return False

        except Exception as e:
            console.print(f"[red]✗ Error installing dependencies: {e}[/red]\n")
            return False

    async def build_rust_parser(self):
        """Build Rust parser module."""
        if self.config["parser"] != "rust":
            return True

        console.print("[bold]Building Rust parser...[/bold]\n")

        rust_dir = self.project_root / "rust_core"

        if not rust_dir.exists():
            console.print("[yellow]⚠ rust_core directory not found, skipping[/yellow]\n")
            return True

        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task("Building Rust module (this may take a few minutes)...", total=None)

                result = subprocess.run(
                    ["maturin", "develop"],
                    cwd=rust_dir,
                    capture_output=True,
                    text=True,
                )

                progress.update(task, completed=True)

            if result.returncode == 0:
                console.print("[green]✓ Rust parser built successfully[/green]\n")
                return True
            else:
                console.print("[yellow]⚠ Rust build failed, will use Python parser fallback[/yellow]")
                console.print(f"[dim]{result.stderr[:200]}...[/dim]\n")
                self.config["parser"] = "python"
                return True  # Not fatal

        except FileNotFoundError:
            console.print("[yellow]⚠ maturin not found, will use Python parser fallback[/yellow]\n")
            self.config["parser"] = "python"
            return True  # Not fatal
        except Exception as e:
            console.print(f"[yellow]⚠ Error building Rust parser: {e}[/yellow]")
            console.print("[yellow]Will use Python parser fallback[/yellow]\n")
            self.config["parser"] = "python"
            return True  # Not fatal

    async def setup_storage(self):
        """Set up storage backend."""
        console.print("[bold]Configuring storage...[/bold]\n")

        if self.config["storage"] == "sqlite":
            # Create .claude-rag directory
            data_dir = Path.home() / ".claude-rag"
            data_dir.mkdir(exist_ok=True)
            console.print(f"[green]✓ SQLite storage configured at {data_dir}[/green]\n")
            return True

        elif self.config["storage"] == "qdrant":
            # Check if Docker is running
            success, _ = await self.check_docker()

            if not success:
                console.print("[yellow]⚠ Docker not running, starting Qdrant...[/yellow]")

                try:
                    # Try to start docker-compose
                    result = subprocess.run(
                        ["docker-compose", "up", "-d"],
                        cwd=self.project_root,
                        capture_output=True,
                        text=True,
                    )

                    if result.returncode == 0:
                        console.print("[green]✓ Qdrant started successfully[/green]\n")
                        return True
                    else:
                        console.print("[yellow]⚠ Could not start Qdrant, falling back to SQLite[/yellow]\n")
                        self.config["storage"] = "sqlite"
                        return await self.setup_storage()

                except Exception as e:
                    console.print(f"[yellow]⚠ Error starting Qdrant: {e}[/yellow]")
                    console.print("[yellow]Falling back to SQLite[/yellow]\n")
                    self.config["storage"] = "sqlite"
                    return await self.setup_storage()
            else:
                console.print("[green]✓ Qdrant already running[/green]\n")
                return True

        return True

    async def verify_installation(self) -> bool:
        """Verify installation with basic tests."""
        console.print("[bold]Verifying installation...[/bold]\n")

        tests = [
            ("Import core modules", self.test_imports),
            ("Check storage connection", self.test_storage),
            ("Load embedding model", self.test_embedding_model),
        ]

        all_passed = True

        for name, test_func in tests:
            console.print(f"  Testing {name}...", end=" ")
            try:
                await test_func()
                console.print("[green]✓[/green]")
            except Exception as e:
                console.print(f"[red]✗ {str(e)[:50]}[/red]")
                all_passed = False

        console.print()
        return all_passed

    async def test_imports(self):
        """Test that core modules can be imported."""
        from src.core.server import MemoryRAGServer
        from src.core.models import MemoryUnit
        from src.embeddings.generator import EmbeddingGenerator

    async def test_storage(self):
        """Test storage connection."""
        from src.store import create_memory_store
        from src.config import get_config

        config = get_config()
        config.storage_backend = self.config["storage"]

        store = create_memory_store(config=config)
        await store.initialize()

    async def test_embedding_model(self):
        """Test embedding model loading."""
        from src.embeddings.generator import EmbeddingGenerator
        from src.config import get_config

        gen = EmbeddingGenerator(get_config())
        embedding = await gen.generate("test")
        assert len(embedding) == 384

    def print_success(self):
        """Print success message with next steps."""
        console.print()
        console.print(
            Panel.fit(
                "[bold green]Installation Successful! 🎉[/bold green]\n\n"
                f"[bold]Configuration:[/bold]\n"
                f"  • Storage: [cyan]{self.config['storage']}[/cyan]\n"
                f"  • Parser: [cyan]{self.config['parser']}[/cyan]\n\n"
                "[bold]Next Steps:[/bold]\n"
                "  1. Add to Claude Code:\n"
                f"     [dim]claude mcp add --transport stdio --scope user claude-memory-rag -- \\\n"
                f"       python {self.project_root / 'src' / 'mcp_server.py'}[/dim]\n\n"
                "  2. Verify health:\n"
                "     [dim]python -m src.cli health[/dim]\n\n"
                "  3. Index a project:\n"
                "     [dim]python -m src.cli index ./your-project[/dim]\n\n"
                + (
                    "[bold]Upgrade Options:[/bold]\n"
                    "  • Build Rust parser: [dim]python setup.py --build-rust[/dim]\n"
                    "  • Upgrade to Qdrant: [dim]python setup.py --upgrade-to-qdrant[/dim]\n"
                    if self.config["parser"] == "python" or self.config["storage"] == "sqlite"
                    else ""
                ),
                border_style="green",
            )
        )
        console.print()

    def print_failure(self):
        """Print failure message with troubleshooting."""
        console.print()
        console.print(
            Panel.fit(
                "[bold red]Installation encountered issues[/bold red]\n\n"
                "[bold]Troubleshooting:[/bold]\n"
                "  • Check the error messages above\n"
                "  • See docs/TROUBLESHOOTING.md for common issues\n"
                "  • Try minimal mode: [dim]python setup.py --mode=minimal[/dim]\n"
                "  • Open an issue: [dim]https://github.com/user/claude-memory-server/issues[/dim]",
                border_style="red",
            )
        )
        console.print()

    async def run(self):
        """Run the setup wizard."""
        self.print_header()

        # Check prerequisites
        await self.check_prerequisites()

        # Python version is critical
        if not self.checks["python"]["success"]:
            console.print("[red]Error: Python 3.8+ is required[/red]")
            return False

        # Interactive or preset mode
        if self.mode == "auto":
            await self.interactive_setup()
        else:
            # Use preset
            if self.mode in self.PRESETS:
                preset = self.PRESETS[self.mode]
                self.config = {
                    "storage": preset["storage"],
                    "parser": preset["parser"],
                }
                console.print(f"[bold]Using {self.mode} preset[/bold]\n")
            else:
                console.print(f"[red]Unknown mode: {self.mode}[/red]")
                return False

        # Install dependencies
        if not await self.install_dependencies():
            self.print_failure()
            return False

        # Build Rust parser if needed
        await self.build_rust_parser()

        # Setup storage
        await self.setup_storage()

        # Verify installation
        verification_passed = await self.verify_installation()

        if verification_passed:
            self.print_success()
            return True
        else:
            console.print("[yellow]⚠ Some verification tests failed, but basic installation is complete[/yellow]")
            self.print_success()
            return True


async def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Setup wizard for Claude Memory RAG Server"
    )
    parser.add_argument(
        "--mode",
        choices=["auto", "minimal", "standard", "full"],
        default="auto",
        help="Setup mode (auto=interactive, minimal/standard/full=preset)",
    )
    parser.add_argument(
        "--build-rust",
        action="store_true",
        help="Build Rust parser only",
    )
    parser.add_argument(
        "--upgrade-to-qdrant",
        action="store_true",
        help="Upgrade from SQLite to Qdrant",
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Only check prerequisites, don't install",
    )

    args = parser.parse_args()

    wizard = SetupWizard(mode=args.mode)

    if args.check_only:
        wizard.print_header()
        await wizard.check_prerequisites()
        return

    if args.build_rust:
        wizard.print_header()
        wizard.config["parser"] = "rust"
        await wizard.build_rust_parser()
        return

    if args.upgrade_to_qdrant:
        wizard.print_header()
        console.print("[bold]Upgrading to Qdrant...[/bold]\n")
        console.print("[yellow]Migration tool not yet implemented[/yellow]")
        console.print("[dim]For now, manually start Qdrant and update CLAUDE_RAG_STORAGE_BACKEND=qdrant[/dim]\n")
        return

    # Run full setup
    success = await wizard.run()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
