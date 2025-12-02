#!/usr/bin/env python3
"""
Environment setup and validation script.

Verifies that the development environment is correctly configured.

Usage:
    python scripts/setup.py
    python scripts/setup.py --fix  # Attempt to fix issues
"""

import subprocess
import sys
from pathlib import Path
from typing import Tuple

# ANSI color codes
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"


class SetupCheck:
    """Base class for setup checks."""

    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description

    def check(self) -> Tuple[bool, str]:
        """Check if requirement is met. Returns (passed, message)."""
        raise NotImplementedError

    def fix(self) -> Tuple[bool, str]:
        """Attempt to fix the issue. Returns (fixed, message)."""
        return False, "Auto-fix not available"


class PythonVersionCheck(SetupCheck):
    """Check Python version."""

    def __init__(self):
        super().__init__("Python Version", "Python 3.8+ required (3.13+ recommended)")

    def check(self) -> Tuple[bool, str]:
        version = sys.version_info
        if version >= (3, 13):
            return (
                True,
                f"Python {version.major}.{version.minor}.{version.micro} (optimal)",
            )
        elif version >= (3, 8):
            return (
                True,
                f"Python {version.major}.{version.minor}.{version.micro} (acceptable)",
            )
        else:
            return (
                False,
                f"Python {version.major}.{version.minor}.{version.micro} is too old (need 3.8+)",
            )


class DependenciesCheck(SetupCheck):
    """Check if dependencies are installed."""

    def __init__(self):
        super().__init__("Dependencies", "All Python dependencies must be installed")

    def check(self) -> Tuple[bool, str]:
        try:
            # Check critical dependencies
            critical_deps = [
                ("qdrant_client", "Qdrant client"),
                ("sentence_transformers", "Embeddings"),
                ("anthropic", "MCP SDK"),
                ("pytest", "Testing"),
            ]

            missing = []
            for module, name in critical_deps:
                try:
                    __import__(module)
                except ImportError:
                    missing.append(name)

            if missing:
                return False, f"Missing dependencies: {', '.join(missing)}"
            return True, "All critical dependencies installed"

        except Exception as e:
            return False, f"Error checking dependencies: {str(e)}"

    def fix(self) -> Tuple[bool, str]:
        try:
            print(f"  {YELLOW}Installing dependencies...{RESET}")
            result = subprocess.run(
                ["pip", "install", "-r", "requirements.txt"],
                capture_output=True,
                text=True,
            )

            if result.returncode == 0:
                return True, "Dependencies installed successfully"
            else:
                return False, f"Failed to install dependencies: {result.stderr}"

        except Exception as e:
            return False, f"Error installing dependencies: {str(e)}"


class QdrantCheck(SetupCheck):
    """Check if Qdrant is accessible."""

    def __init__(self):
        super().__init__("Qdrant", "Qdrant vector database must be running")

    def check(self) -> Tuple[bool, str]:
        try:
            import requests

            response = requests.get("http://localhost:6333/", timeout=5)

            if response.status_code == 200:
                data = response.json()
                version = data.get("version", "unknown")
                return True, f"Qdrant running (version: {version})"
            else:
                return False, f"Qdrant returned status {response.status_code}"

        except ImportError:
            # Try with curl
            try:
                result = subprocess.run(
                    ["curl", "-s", "http://localhost:6333/"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if result.returncode == 0 and "version" in result.stdout:
                    return True, "Qdrant running"
                return False, "Qdrant not responding"
            except Exception:
                return False, "Qdrant not accessible"

        except Exception as e:
            return False, f"Qdrant not accessible: {str(e)}"

    def fix(self) -> Tuple[bool, str]:
        # Check if Docker is available
        try:
            result = subprocess.run(
                ["docker", "--version"], capture_output=True, text=True
            )
            if result.returncode != 0:
                return False, "Docker not available. Install Docker first."
        except FileNotFoundError:
            return False, "Docker not found. Install Docker first."

        # Try to start Qdrant with docker-compose
        if Path("docker-compose.yml").exists():
            print(f"  {YELLOW}Starting Qdrant with docker-compose...{RESET}")
            try:
                result = subprocess.run(
                    ["docker-compose", "up", "-d"],
                    capture_output=True,
                    text=True,
                    timeout=60,
                )

                if result.returncode == 0:
                    # Wait a moment for Qdrant to start
                    import time

                    time.sleep(3)

                    # Check if it's now accessible
                    passed, msg = self.check()
                    if passed:
                        return True, "Qdrant started successfully"
                    else:
                        return (
                            False,
                            "Qdrant started but not yet accessible (wait a moment)",
                        )
                else:
                    return False, f"Failed to start Qdrant: {result.stderr}"

            except subprocess.TimeoutExpired:
                return False, "docker-compose timed out"
            except Exception as e:
                return False, f"Error starting Qdrant: {str(e)}"
        else:
            return False, "docker-compose.yml not found"


class DirectoryStructureCheck(SetupCheck):
    """Check if directory structure is correct."""

    def __init__(self):
        super().__init__("Directory Structure", "Required directories must exist")

    def check(self) -> Tuple[bool, str]:
        required_dirs = ["src", "tests", "docs", "planning_docs", ".worktrees"]

        missing = []
        for dir_name in required_dirs:
            if not Path(dir_name).exists():
                missing.append(dir_name)

        if missing:
            return False, f"Missing directories: {', '.join(missing)}"
        return True, "All required directories exist"

    def fix(self) -> Tuple[bool, str]:
        # Create missing directories
        required_dirs = ["planning_docs", ".worktrees"]

        created = []
        for dir_name in required_dirs:
            dir_path = Path(dir_name)
            if not dir_path.exists():
                try:
                    dir_path.mkdir(parents=True, exist_ok=True)
                    created.append(dir_name)
                except Exception as e:
                    return False, f"Failed to create {dir_name}: {str(e)}"

        if created:
            return True, f"Created directories: {', '.join(created)}"
        return True, "All directories already exist"


class GitConfigCheck(SetupCheck):
    """Check git configuration."""

    def __init__(self):
        super().__init__("Git Config", "Git should be configured")

    def check(self) -> Tuple[bool, str]:
        try:
            # Check if we're in a git repo
            result = subprocess.run(
                ["git", "rev-parse", "--git-dir"], capture_output=True, text=True
            )

            if result.returncode != 0:
                return False, "Not a git repository"

            # Check git user config
            result = subprocess.run(
                ["git", "config", "user.name"], capture_output=True, text=True
            )

            if not result.stdout.strip():
                return False, "Git user.name not configured"

            result = subprocess.run(
                ["git", "config", "user.email"], capture_output=True, text=True
            )

            if not result.stdout.strip():
                return False, "Git user.email not configured"

            return True, "Git configured correctly"

        except FileNotFoundError:
            return False, "Git not found"
        except Exception as e:
            return False, f"Error checking git: {str(e)}"


class RustModuleCheck(SetupCheck):
    """Check if Rust module is built (optional)."""

    def __init__(self):
        super().__init__(
            "Rust Module (Optional)", "Rust parser provides 6x faster parsing"
        )

    def check(self) -> Tuple[bool, str]:
        try:
            from src.memory import rust_parser

            return True, "Rust parser available (6x faster parsing)"
        except ImportError:
            return False, "Rust parser not available (using Python fallback)"

    def fix(self) -> Tuple[bool, str]:
        # Check if Rust is installed
        try:
            result = subprocess.run(
                ["rustc", "--version"], capture_output=True, text=True
            )
            if result.returncode != 0:
                return False, "Rust not installed. Install from https://rustup.rs"
        except FileNotFoundError:
            return False, "Rust not found. Install from https://rustup.rs"

        # Try to build Rust module
        rust_core_path = Path("rust_core")
        if not rust_core_path.exists():
            return False, "rust_core/ directory not found"

        print(f"  {YELLOW}Building Rust module (this may take a few minutes)...{RESET}")
        try:
            result = subprocess.run(
                ["maturin", "develop", "--release"],
                cwd=rust_core_path,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minutes
            )

            if result.returncode == 0:
                return True, "Rust module built successfully"
            else:
                return False, f"Failed to build Rust module: {result.stderr}"

        except FileNotFoundError:
            return False, "Maturin not found. Install with: pip install maturin"
        except subprocess.TimeoutExpired:
            return False, "Build timed out"
        except Exception as e:
            return False, f"Error building Rust module: {str(e)}"


def print_header(text: str):
    """Print a colored header."""
    print(f"\n{BLUE}{'=' * 60}{RESET}")
    print(f"{BLUE}{text:^60}{RESET}")
    print(f"{BLUE}{'=' * 60}{RESET}\n")


def print_result(name: str, passed: bool, message: str, optional: bool = False):
    """Print a check result."""
    if optional:
        status = f"{YELLOW}○ OPTIONAL{RESET}" if not passed else f"{GREEN}✓ OK{RESET}"
    else:
        status = f"{GREEN}✓ OK{RESET}" if passed else f"{RED}✗ FAIL{RESET}"

    print(f"{status} {name:25} {message}")


def main():
    """Run all setup checks."""
    # Check if in correct directory
    if not Path("src").exists():
        print(f"{RED}Error: Must run from project root directory{RESET}")
        sys.exit(1)

    # Parse arguments
    fix_mode = "--fix" in sys.argv

    print_header("Development Environment Setup")

    if fix_mode:
        print(f"{YELLOW}Running in FIX mode (will attempt to fix issues){RESET}\n")

    # Define checks
    checks = [
        (PythonVersionCheck(), False),
        (DependenciesCheck(), False),
        (QdrantCheck(), False),
        (DirectoryStructureCheck(), False),
        (GitConfigCheck(), False),
        (RustModuleCheck(), True),  # Optional
    ]

    # Run checks
    results = []
    for check, is_optional in checks:
        print(f"Checking {check.name}... ", end="", flush=True)
        passed, message = check.check()
        results.append((check, passed, message, is_optional))

        if not passed and fix_mode and not is_optional:
            print(f"\n  {YELLOW}Attempting to fix...{RESET}")
            fixed, fix_msg = check.fix()
            if fixed:
                # Re-check
                passed, message = check.check()
                results[-1] = (check, passed, f"{fix_msg} → {message}", is_optional)
            else:
                message = f"{message} (fix failed: {fix_msg})"
                results[-1] = (check, passed, message, is_optional)

        print_result(check.name, passed, message, is_optional)

    # Summary
    print_header("Summary")

    required_checks = [(c, p, m) for c, p, m, opt in results if not opt]
    optional_checks = [(c, p, m) for c, p, m, opt in results if opt]

    required_passed = sum(1 for _, p, _ in required_checks if p)
    total_required = len(required_checks)

    if required_passed == total_required:
        print(f"{GREEN}✓ All {total_required} required checks passed!{RESET}")
        print(f"\n{GREEN}Environment is ready for development.{RESET}")

        # Show optional check status
        if optional_checks:
            print("\nOptional features:")
            for check, passed, message, _ in results:
                if any(c == check for c, _, _ in optional_checks):
                    status = "✓" if passed else "✗"
                    print(f"  {status} {check.name}: {message}")

        print("\nNext steps:")
        print("  1. Read GETTING_STARTED.md")
        print("  2. Pick a task from TODO.md")
        print(
            "  3. Create a git worktree: git worktree add .worktrees/TASK-XXX -b TASK-XXX"
        )
        print("  4. Start coding!")

        return 0
    else:
        failed_count = total_required - required_passed
        print(f"{RED}✗ {failed_count}/{total_required} required checks failed{RESET}")
        print(f"\n{RED}Environment is NOT ready for development.{RESET}")
        print("\nFailed checks:")
        for check, passed, message, is_optional in results:
            if not passed and not is_optional:
                print(f"  - {check.name}: {message}")

        if not fix_mode:
            print("\nTry running with --fix to automatically fix issues:")
            print("  python scripts/setup.py --fix")

        return 1


if __name__ == "__main__":
    sys.exit(main())
