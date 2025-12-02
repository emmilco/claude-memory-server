#!/usr/bin/env python3
"""Automated installation validation script."""

import asyncio
import sys
import subprocess
import importlib
from pathlib import Path
from typing import List
import argparse

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel

    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

    class Console:
        def print(self, *args, **kwargs):
            print(*args)


console = Console()


class ValidationResult:
    """Result of a validation check."""

    def __init__(self, name: str, passed: bool, message: str = ""):
        self.name = name
        self.passed = passed
        self.message = message

    def __str__(self):
        status = "✅ PASS" if self.passed else "❌ FAIL"
        msg = f": {self.message}" if self.message else ""
        return f"{status} - {self.name}{msg}"


class InstallationValidator:
    """Validates Claude Memory RAG Server installation."""

    def __init__(self, preset: str):
        self.preset = preset
        self.results: List[ValidationResult] = []

    def add_result(self, name: str, passed: bool, message: str = ""):
        """Add a validation result."""
        result = ValidationResult(name, passed, message)
        self.results.append(result)
        return result

    def check_python_version(self) -> bool:
        """Check Python version is 3.13+."""
        version = sys.version_info
        passed = version.major == 3 and version.minor >= 13

        self.add_result(
            "Python Version", passed, f"{version.major}.{version.minor}.{version.micro}"
        )
        return passed

    def check_dependencies(self) -> bool:
        """Check required Python packages are installed."""
        required_packages = [
            "sentence_transformers",
            "qdrant_client",
            "apscheduler",
            "rich",
            "pydantic",
        ]

        all_installed = True
        missing = []

        for package in required_packages:
            try:
                importlib.import_module(package)
            except ImportError:
                all_installed = False
                missing.append(package)

        if missing:
            self.add_result("Dependencies", False, f"Missing: {', '.join(missing)}")
        else:
            self.add_result("Dependencies", True, "All required packages installed")

        return all_installed

    def check_configuration(self) -> bool:
        """Check configuration files exist."""
        try:
            from src.config import get_config

            config = get_config()
            passed = True

            # Check data directory
            if not config.data_dir.exists():
                passed = False
                self.add_result(
                    "Data Directory", False, f"Not found: {config.data_dir}"
                )
            else:
                self.add_result("Data Directory", True, str(config.data_dir))

            return passed

        except Exception as e:
            self.add_result("Configuration", False, str(e))
            return False

    def check_parser(self) -> bool:
        """Check parser availability.

        Note: Python parser fallback was removed (it was broken).
        Rust parser (mcp_performance_core) is now required for all presets.
        """
        # Rust parser is now required for all presets
        try:
            from mcp_performance_core import parse_source_file

            # Test it works
            test_code = "def test(): pass"
            parse_source_file("test.py", test_code)

            self.add_result("Rust Parser", True, "Compiled and working")
            return True
        except ImportError as e:
            self.add_result(
                "Rust Parser",
                False,
                f"Not installed: {e}\n"
                "Install with: cd rust_core && maturin build --release && pip install target/wheels/*.whl",
            )
            return False
        except Exception as e:
            self.add_result("Rust Parser", False, str(e))
            return False

    def check_storage_backend(self) -> bool:
        """Check storage backend based on preset."""
        if self.preset in ["minimal", "standard"]:
            # SQLite should work
            try:
                from src.store.sqlite_store import SQLiteStore
                from src.config import get_config

                config = get_config()

                # Try to create a store instance
                SQLiteStore(config)
                self.add_result("SQLite Backend", True, "Available")
                return True
            except Exception as e:
                self.add_result("SQLite Backend", False, str(e))
                return False

        elif self.preset == "full":
            # Qdrant should be accessible
            try:
                import requests

                response = requests.get("http://localhost:6333/health", timeout=5)

                if response.status_code == 200:
                    self.add_result("Qdrant Backend", True, "Running and accessible")
                    return True
                else:
                    self.add_result(
                        "Qdrant Backend", False, f"HTTP {response.status_code}"
                    )
                    return False
            except Exception as e:
                self.add_result("Qdrant Backend", False, str(e))
                return False

    async def check_core_functionality(self) -> bool:
        """Check core server functionality."""
        try:
            from src.core.server import MemoryRAGServer
            from src.config import get_config

            config = get_config()
            server = MemoryRAGServer(config)

            # Initialize server
            await server.initialize()

            # Test store memory
            result = await server.store_memory(
                content="Test memory for validation",
                category="FACT",
                importance=0.5,
                tags=["test", "validation"],
            )

            memory_id = result.get("id")

            if not memory_id:
                self.add_result("Store Memory", False, "No memory ID returned")
                await server.close()
                return False

            # Test retrieve
            results = await server.retrieve_memories("test validation", limit=1)

            if not results.get("memories"):
                self.add_result("Retrieve Memories", False, "No results found")
                await server.close()
                return False

            # Test delete
            await server.delete_memory(memory_id)

            await server.close()

            self.add_result(
                "Core Functionality", True, "Store, retrieve, delete working"
            )
            return True

        except Exception as e:
            self.add_result("Core Functionality", False, str(e))
            return False

    def check_cli_commands(self) -> bool:
        """Check CLI commands are accessible."""
        commands_to_test = [
            ["python", "-m", "src.cli", "health", "--help"],
            ["python", "-m", "src.cli", "index", "--help"],
            ["python", "-m", "src.cli", "search", "--help"],
        ]

        all_passed = True

        for cmd in commands_to_test:
            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=10,
                )

                if result.returncode == 0:
                    cmd[3]  # Extract command name
                else:
                    all_passed = False

            except Exception:
                all_passed = False

        self.add_result("CLI Commands", all_passed, "All commands accessible")
        return all_passed

    async def run_all_checks(self) -> bool:
        """Run all validation checks."""
        console.print("\n[bold blue]Validating Installation[/bold blue]")
        console.print(f"[cyan]Preset:[/cyan] {self.preset}\n")

        # Run checks
        checks = [
            ("Python Version", self.check_python_version),
            ("Dependencies", self.check_dependencies),
            ("Configuration", self.check_configuration),
            ("Parser", self.check_parser),
            ("Storage Backend", self.check_storage_backend),
            ("Core Functionality", self.check_core_functionality),
            ("CLI Commands", self.check_cli_commands),
        ]

        for check_name, check_func in checks:
            console.print(f"[dim]Checking {check_name}...[/dim]", end=" ")

            if asyncio.iscoroutinefunction(check_func):
                passed = await check_func()
            else:
                passed = check_func()

            if passed:
                console.print("[green]✓[/green]")
            else:
                console.print("[red]✗[/red]")

        # Print results
        console.print("\n[bold]Validation Results:[/bold]\n")

        if RICH_AVAILABLE:
            table = Table(show_header=True)
            table.add_column("Check", style="cyan")
            table.add_column("Status", style="white")
            table.add_column("Details", style="dim")

            for result in self.results:
                status = "✅ PASS" if result.passed else "❌ FAIL"
                status_color = "green" if result.passed else "red"
                table.add_row(
                    result.name,
                    f"[{status_color}]{status}[/{status_color}]",
                    result.message,
                )

            console.print(table)
        else:
            for result in self.results:
                console.print(str(result))

        # Overall result
        passed_count = sum(1 for r in self.results if r.passed)
        total_count = len(self.results)
        all_passed = passed_count == total_count

        console.print()
        if all_passed:
            console.print(
                Panel.fit(
                    f"[bold green]✅ All Checks Passed ({passed_count}/{total_count})[/bold green]\n\n"
                    "Installation is valid and ready to use!",
                    border_style="green",
                )
                if RICH_AVAILABLE
                else f"✅ All checks passed ({passed_count}/{total_count})"
            )
        else:
            console.print(
                Panel.fit(
                    f"[bold red]❌ Some Checks Failed ({passed_count}/{total_count})[/bold red]\n\n"
                    "Please review the failures above and fix any issues.",
                    border_style="red",
                )
                if RICH_AVAILABLE
                else f"❌ Some checks failed ({passed_count}/{total_count})"
            )

        console.print()
        return all_passed


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Validate Claude Memory RAG Server installation"
    )
    parser.add_argument(
        "--preset",
        choices=["minimal", "standard", "full"],
        default="minimal",
        help="Installation preset to validate",
    )
    parser.add_argument(
        "--automated", action="store_true", help="Run in automated mode (for CI/CD)"
    )

    args = parser.parse_args()

    validator = InstallationValidator(args.preset)
    success = await validator.run_all_checks()

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
