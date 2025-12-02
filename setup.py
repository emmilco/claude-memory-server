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
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Tuple

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
                parts = result.stdout.strip().split()
                version = parts[1] if len(parts) > 1 else "unknown"
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
            self.print_step(
                steps.index((key, name, check_func)) + 1, len(steps), f"Checking {name}"
            )
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

        console.print(
            f"[dim]Recommended mode based on your system: [bold]{recommended}[/bold][/dim]\n"
        )

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
                    [
                        sys.executable,
                        "-m",
                        "pip",
                        "install",
                        "-r",
                        str(requirements_file),
                    ],
                    capture_output=True,
                    text=True,
                )

                progress.update(task, completed=True)

            if result.returncode == 0:
                console.print("[green]✓ Dependencies installed successfully[/green]\n")
                return True
            else:
                console.print("[red]✗ Failed to install dependencies:[/red]")
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
            console.print(
                "[yellow]⚠ rust_core directory not found, skipping[/yellow]\n"
            )
            return True

        # Check if maturin is installed
        try:
            subprocess.run(
                ["maturin", "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
        except FileNotFoundError:
            # maturin not found, ask user if they want to install it
            console.print(
                "[yellow]maturin not found (required to build Rust parser)[/yellow]\n"
            )

            if Confirm.ask("Install maturin now?", default=True):
                try:
                    console.print("Installing maturin...", end=" ")
                    result = subprocess.run(
                        [sys.executable, "-m", "pip", "install", "maturin"],
                        capture_output=True,
                        text=True,
                    )
                    if result.returncode == 0:
                        console.print("[green]✓[/green]\n")
                    else:
                        console.print("[red]✗[/red]")
                        console.print(
                            "[yellow]Could not install maturin, falling back to Python parser[/yellow]\n"
                        )
                        self.config["parser"] = "python"
                        return True
                except Exception as e:
                    console.print(f"[yellow]⚠ Error installing maturin: {e}[/yellow]")
                    console.print("[yellow]Falling back to Python parser[/yellow]\n")
                    self.config["parser"] = "python"
                    return True
            else:
                console.print(
                    "[yellow]Skipping Rust parser build, will use Python parser fallback[/yellow]\n"
                )
                self.config["parser"] = "python"
                return True

        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task(
                    "Building Rust module (this may take a few minutes)...", total=None
                )

                # Use 'maturin build' instead of 'develop' to avoid virtualenv requirement
                result = subprocess.run(
                    ["maturin", "build", "--release"],
                    cwd=rust_dir,
                    capture_output=True,
                    text=True,
                )

                progress.update(task, completed=True)

            if result.returncode == 0:
                # Find the built wheel
                wheels_dir = rust_dir / "target" / "wheels"
                if wheels_dir.exists():
                    wheels = list(wheels_dir.glob("*.whl"))
                    if wheels:
                        # Install the wheel
                        console.print("[green]✓ Rust module built[/green]")
                        console.print("Installing Rust module...", end=" ")

                        install_result = subprocess.run(
                            [
                                sys.executable,
                                "-m",
                                "pip",
                                "install",
                                "--force-reinstall",
                                str(wheels[0]),
                            ],
                            capture_output=True,
                            text=True,
                        )

                        if install_result.returncode == 0:
                            console.print("[green]✓[/green]\n")
                            return True
                        else:
                            console.print("[red]✗[/red]")
                            console.print(
                                f"[yellow]Failed to install wheel: {install_result.stderr[:200]}[/yellow]\n"
                            )
                            self.config["parser"] = "python"
                            return True

                console.print(
                    "[yellow]⚠ Could not find built wheel, falling back to Python parser[/yellow]\n"
                )
                self.config["parser"] = "python"
                return True
            else:
                console.print(
                    "[yellow]⚠ Rust build failed, will use Python parser fallback[/yellow]"
                )
                console.print(f"[dim]{result.stderr[:200]}...[/dim]\n")
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

            # Create .env file with SQLite configuration
            self._write_env_config({"CLAUDE_RAG_STORAGE_BACKEND": "sqlite"})

            console.print(f"[green]✓ SQLite storage configured at {data_dir}[/green]\n")
            return True

        elif self.config["storage"] == "qdrant":
            # Check if Qdrant is already running
            qdrant_running = await self._check_qdrant_health()

            if not qdrant_running:
                console.print("[yellow]⚠ Qdrant not running, starting...[/yellow]")

                # Check if Docker is available
                docker_available, _ = await self.check_docker()
                if not docker_available:
                    console.print(
                        "[yellow]⚠ Docker not available, falling back to SQLite[/yellow]\n"
                    )
                    self.config["storage"] = "sqlite"
                    return await self.setup_storage()

                try:
                    # Try to start docker-compose
                    result = subprocess.run(
                        ["docker-compose", "up", "-d"],
                        cwd=self.project_root,
                        capture_output=True,
                        text=True,
                    )

                    if result.returncode == 0:
                        # Wait a moment for Qdrant to start
                        import asyncio

                        await asyncio.sleep(2)

                        # Verify Qdrant is responsive
                        if await self._check_qdrant_health():
                            console.print(
                                "[green]✓ Qdrant started successfully[/green]\n"
                            )
                        else:
                            console.print(
                                "[yellow]⚠ Qdrant started but not responding, falling back to SQLite[/yellow]\n"
                            )
                            self.config["storage"] = "sqlite"
                            return await self.setup_storage()
                    else:
                        console.print(
                            "[yellow]⚠ Could not start Qdrant, falling back to SQLite[/yellow]\n"
                        )
                        self.config["storage"] = "sqlite"
                        return await self.setup_storage()

                except Exception as e:
                    console.print(f"[yellow]⚠ Error starting Qdrant: {e}[/yellow]")
                    console.print("[yellow]Falling back to SQLite[/yellow]\n")
                    self.config["storage"] = "sqlite"
                    return await self.setup_storage()
            else:
                console.print("[green]✓ Qdrant already running[/green]\n")

            # Create .env file with Qdrant configuration
            self._write_env_config({"CLAUDE_RAG_STORAGE_BACKEND": "qdrant"})
            console.print("[green]✓ Configuration written to .env[/green]\n")
            return True

        return True

    async def _check_qdrant_health(self) -> bool:
        """Check if Qdrant is running and healthy."""
        try:
            import urllib.request
            import json

            # Qdrant doesn't have /health, use root endpoint instead
            req = urllib.request.Request("http://localhost:6333/", method="GET")
            with urllib.request.urlopen(req, timeout=2) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode())
                    # Verify it's actually Qdrant by checking for version
                    return "version" in data and "title" in data
            return False
        except Exception:
            return False

    def _write_env_config(self, config: Dict[str, str]):
        """Write configuration to .env file."""
        env_path = self.project_root / ".env"

        # Read existing .env if it exists
        existing_config = {}
        if env_path.exists():
            with open(env_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, value = line.split("=", 1)
                        existing_config[key.strip()] = value.strip()

        # Update with new config
        existing_config.update(config)

        # Write back to .env
        with open(env_path, "w") as f:
            f.write("# Claude Memory RAG Server Configuration\n")
            f.write(
                f"# Generated by setup.py on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            )
            for key, value in existing_config.items():
                f.write(f"{key}={value}\n")

    async def verify_installation(self) -> bool:
        """Verify installation with basic tests."""
        console.print("[bold]Verifying installation...[/bold]\n")

        tests = [
            ("Import core modules", self.test_imports),
            ("Check storage connection", self.test_storage),
            ("Verify storage backend", self.test_storage_backend),
            ("Load embedding model", self.test_embedding_model),
            ("Test code parsing", self.test_code_parsing),
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

    async def test_storage_backend(self):
        """Test that the correct storage backend is configured."""
        from src.config import get_config

        config = get_config()
        expected_backend = self.config["storage"]

        if expected_backend == "qdrant":
            assert (
                config.storage_backend == "qdrant"
            ), f"Expected qdrant backend, got {config.storage_backend}"
        else:
            assert (
                config.storage_backend == "sqlite"
            ), f"Expected sqlite backend, got {config.storage_backend}"

    async def test_code_parsing(self):
        """Test code parsing and SemanticUnit structure."""
        import tempfile

        # Test if Rust parser is available, otherwise use Python
        try:
            from mcp_performance_core import parse_source_file, SemanticUnit
        except ImportError:
            from src.memory.incremental_indexer import parse_source_file

        # Create a simple test file
        test_code = '''
def test_function():
    """Test function."""
    return 42

class TestClass:
    """Test class."""
    def method(self):
        return "test"
'''

        # Write to temp file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(test_code)
            temp_path = f.name

        try:
            # Parse the file
            result = parse_source_file(temp_path, test_code)

            # Verify units were found
            assert len(result.units) > 0, "No semantic units found"

            # Verify SemanticUnit has required fields
            unit = result.units[0]
            assert hasattr(unit, "unit_type"), "SemanticUnit missing unit_type"
            assert hasattr(unit, "name"), "SemanticUnit missing name"
            assert hasattr(unit, "start_line"), "SemanticUnit missing start_line"
            assert hasattr(unit, "end_line"), "SemanticUnit missing end_line"
            assert hasattr(unit, "start_byte"), "SemanticUnit missing start_byte"
            assert hasattr(unit, "end_byte"), "SemanticUnit missing end_byte"
            assert hasattr(unit, "signature"), "SemanticUnit missing signature"

        finally:
            # Clean up
            os.unlink(temp_path)

    def _format_upgrade_options(self) -> str:
        """Format upgrade options based on current configuration."""
        upgrade_options = []

        # Only suggest Rust parser if currently using Python
        if self.config["parser"] == "python":
            upgrade_options.append(
                "  • Build Rust parser (10-20x faster): [dim]python setup.py --build-rust[/dim]"
            )

        # Only suggest Qdrant if currently using SQLite
        if self.config["storage"] == "sqlite":
            upgrade_options.append(
                "  • Upgrade to Qdrant (better scalability): [dim]python setup.py --upgrade-to-qdrant[/dim]"
            )

        # Only show section if there are upgrade options
        if upgrade_options:
            return "[bold]Upgrade Options:[/bold]\n" + "\n".join(upgrade_options) + "\n"
        else:
            return ""

    def _detect_pyenv(self) -> Tuple[bool, Optional[str]]:
        """Detect if pyenv is in use and get the absolute Python path.

        Returns:
            Tuple of (is_pyenv, absolute_python_path)
        """
        python_path = sys.executable

        # Check if Python is running from pyenv
        is_pyenv = ".pyenv" in python_path

        return is_pyenv, python_path

    def print_success(self):
        """Print success message with next steps."""
        console.print()

        # Show .env file location
        env_path = self.project_root / ".env"
        env_exists = env_path.exists()

        # Detect pyenv and get absolute Python path
        is_pyenv, python_path = self._detect_pyenv()

        # Format MCP configuration command with absolute script path
        mcp_server_path = self.project_root / "src" / "mcp_server.py"
        mcp_command = (
            f"     [dim]claude mcp add --transport stdio --scope user \\\n"
            f"       claude-memory-rag -- \\\n"
            f"       {python_path} {mcp_server_path}[/dim]"
        )

        # Add pyenv warning if detected
        pyenv_warning = ""
        if is_pyenv:
            pyenv_warning = (
                "\n\n"
                "[yellow]⚠ pyenv detected:[/yellow] Using absolute Python path to avoid environment isolation issues.\n"
                f"     Python: [cyan]{python_path}[/cyan]\n"
                f"     If you use multiple pyenv environments, this ensures the MCP server\n"
                f"     always uses the correct Python installation with required dependencies."
            )

        console.print(
            Panel.fit(
                "[bold green]Installation Successful! 🎉[/bold green]\n\n"
                f"[bold]Configuration:[/bold]\n"
                f"  • Storage: [cyan]{self.config['storage'].upper()}[/cyan] "
                f"({'Qdrant on localhost:6333' if self.config['storage'] == 'qdrant' else '~/.claude-rag/memory.db'})\n"
                f"  • Parser: [cyan]{self.config['parser'].upper()}[/cyan] "
                f"({'optimal performance' if self.config['parser'] == 'rust' else '10-20x slower fallback'})\n"
                f"  • Config file: [cyan].env[/cyan] {'✓ created' if env_exists else '⚠ not found'}\n"
                f"  • Python: [cyan]{python_path}[/cyan] {'[yellow](pyenv)[/yellow]' if is_pyenv else ''}\n\n"
                "[bold]Next Steps:[/bold]\n"
                "  1. Verify configuration:\n"
                "     [dim]cat .env[/dim]\n\n"
                "  2. Check system health:\n"
                "     [dim]python -m src.cli health[/dim]\n\n"
                "  3. Index your first project:\n"
                "     [dim]python -m src.cli index ./your-project[/dim]\n\n"
                "  4. Add to Claude Code (optional):\n"
                + mcp_command
                + "\n\n"
                + self._format_upgrade_options()
                + pyenv_warning,
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
            console.print(
                "[yellow]⚠ Some verification tests failed, but basic installation is complete[/yellow]"
            )
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
        console.print(
            "[dim]For now, manually start Qdrant and update CLAUDE_RAG_STORAGE_BACKEND=qdrant[/dim]\n"
        )
        return

    # Run full setup
    success = await wizard.run()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
