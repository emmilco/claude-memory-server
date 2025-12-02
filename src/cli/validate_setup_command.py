"""Setup validation command for checking system prerequisites."""

import sys
import subprocess
import logging
import threading
from typing import Dict, Any, Tuple
import requests

try:
    from rich.console import Console
    from rich.panel import Panel

    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

from src.config import get_config

logger = logging.getLogger(__name__)


class ValidateSetupCommand:
    """Validate setup command to check system prerequisites."""

    def __init__(self):
        """Initialize validate setup command."""
        self.console = Console() if RICH_AVAILABLE else None
        self.checks_passed = 0
        self.checks_failed = 0
        self.warnings = []
        self._counter_lock = threading.Lock()  # REF-030: Atomic counter operations

    def print_header(self, message: str):
        """Print header message."""
        if self.console:
            self.console.print(f"\n[bold cyan]{message}[/bold cyan]")
        else:
            print(f"\n{message}")
            print("=" * len(message))

    def print_check(self, name: str, status: bool, message: str):
        """Print individual check result."""
        with self._counter_lock:  # REF-030: Atomic counter operations
            if status:
                self.checks_passed += 1
            else:
                self.checks_failed += 1

        if self.console:
            if status:
                self.console.print(f"  [green]✓[/green] {name:30s} {message}")
            else:
                self.console.print(f"  [red]✗[/red] {name:30s} {message}")
        else:
            symbol = "✓" if status else "✗"
            print(f"  {symbol} {name:30s} {message}")

    def print_warning(self, message: str):
        """Print warning message."""
        if self.console:
            self.console.print(f"  [yellow]⚠[/yellow] {message}")
        else:
            print(f"  ⚠ {message}")

    def print_info(self, message: str):
        """Print info message."""
        if self.console:
            self.console.print(f"  [blue]ℹ[/blue] {message}")
        else:
            print(f"  ℹ {message}")

    def check_docker(self) -> Tuple[bool, str]:
        """Check if Docker is installed and running."""
        try:
            result = subprocess.run(
                ["docker", "ps"], capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                return True, "Docker is running"
            else:
                return False, f"Docker not running: {result.stderr.strip()}"
        except FileNotFoundError:
            return False, "Docker not installed"
        except subprocess.TimeoutExpired:
            return False, "Docker command timed out"
        except Exception as e:
            return False, f"Docker check failed: {e}"

    def check_qdrant(self, url: str) -> Tuple[bool, str]:
        """Check if Qdrant is accessible."""
        try:
            health_url = f"{url}/health"
            response = requests.get(health_url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                status = data.get("status", "unknown")
                return True, f"Qdrant is healthy (status: {status})"
            else:
                return False, f"Qdrant returned status {response.status_code}"
        except requests.exceptions.ConnectionError:
            return False, "Cannot connect to Qdrant (connection refused)"
        except requests.exceptions.Timeout:
            return False, "Qdrant health check timed out"
        except Exception as e:
            return False, f"Qdrant check failed: {e}"

    def check_python_version(self) -> Tuple[bool, str]:
        """Check Python version."""
        version = sys.version_info
        if version >= (3, 8):
            return True, f"Python {version.major}.{version.minor}.{version.micro}"
        else:
            return False, f"Python {version.major}.{version.minor} (3.8+ required)"

    def check_config(self) -> Tuple[bool, str, Dict[str, Any]]:
        """Check configuration."""
        try:
            config = get_config()
            backend = config.storage_backend
            url = config.qdrant_url

            if backend == "qdrant":
                return (
                    True,
                    f"Configured for Qdrant at {url}",
                    {"backend": backend, "url": url},
                )
            else:
                return (
                    False,
                    f"Configured for {backend} (Qdrant required)",
                    {"backend": backend, "url": url},
                )
        except Exception as e:
            return False, f"Config error: {e}", {}

    def run(self) -> int:
        """Run setup validation checks."""
        self.print_header("🔍 Claude Memory RAG Server - Setup Validation")

        # Python version check
        self.print_header("Python Environment")
        py_ok, py_msg = self.check_python_version()
        self.print_check("Python Version", py_ok, py_msg)

        # Configuration check
        self.print_header("Configuration")
        config_ok, config_msg, config_data = self.check_config()
        self.print_check("Configuration", config_ok, config_msg)

        # Docker check
        self.print_header("Docker")
        docker_ok, docker_msg = self.check_docker()
        self.print_check("Docker Status", docker_ok, docker_msg)

        if not docker_ok:
            self.print_warning("Docker is required to run Qdrant")
            self.print_info("Install Docker from: https://docs.docker.com/get-docker/")

        # Qdrant check
        self.print_header("Qdrant Vector Database")
        if config_data.get("backend") == "qdrant":
            qdrant_url = config_data.get("url", "http://localhost:6333")
            qdrant_ok, qdrant_msg = self.check_qdrant(qdrant_url)
            self.print_check("Qdrant Connection", qdrant_ok, qdrant_msg)

            if not qdrant_ok and docker_ok:
                self.print_warning("Qdrant is not running")
                self.print_info("Start Qdrant with: docker-compose up -d")
                self.print_info(f"Check health at: {qdrant_url}/health")
            elif not qdrant_ok and not docker_ok:
                self.print_warning("Cannot start Qdrant without Docker")
        else:
            self.print_info(
                f"Backend set to {config_data.get('backend')} - skipping Qdrant check"
            )
            self.print_warning("SQLite backend is deprecated for code search")
            self.print_info("Update config to use Qdrant for semantic search")

        # Summary
        self.print_header("Summary")
        total = self.checks_passed + self.checks_failed

        if self.console:
            if self.checks_failed == 0:
                self.console.print(
                    Panel(
                        f"[green]✓ All checks passed ({self.checks_passed}/{total})[/green]\n"
                        "Your setup is ready for semantic code search!",
                        title="Setup Status",
                        border_style="green",
                    )
                )
            else:
                self.console.print(
                    Panel(
                        f"[red]✗ {self.checks_failed} check(s) failed ({self.checks_passed}/{total} passed)[/red]\n"
                        "Please fix the issues above before using semantic code search.",
                        title="Setup Status",
                        border_style="red",
                    )
                )
        else:
            if self.checks_failed == 0:
                print(f"\n✓ All checks passed ({self.checks_passed}/{total})")
                print("Your setup is ready for semantic code search!")
            else:
                print(
                    f"\n✗ {self.checks_failed} check(s) failed ({self.checks_passed}/{total} passed)"
                )
                print("Please fix the issues above before using semantic code search.")

        # Return exit code
        return 0 if self.checks_failed == 0 else 1


def main():
    """Main entry point for validate-setup command."""
    command = ValidateSetupCommand()
    exit_code = command.run()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
