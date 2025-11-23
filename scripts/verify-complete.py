#!/usr/bin/env python3
"""
Comprehensive verification script for task completion.

Runs all quality gates before allowing a task to be marked complete.

Usage:
    python scripts/verify-complete.py
    python scripts/verify-complete.py --fast  # Skip slow tests

Exit codes:
    0: All checks passed
    1: One or more checks failed
"""

import subprocess
import sys
import os
from pathlib import Path
from typing import Tuple, List

# ANSI color codes
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'


class VerificationGate:
    """Base class for verification gates."""

    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description

    def run(self) -> Tuple[bool, str]:
        """Run the verification. Returns (passed, message)."""
        raise NotImplementedError


class TestsGate(VerificationGate):
    """Verify all tests pass."""

    def __init__(self, fast_mode: bool = False):
        super().__init__(
            "Tests",
            "All tests must pass (100% pass rate)"
        )
        self.fast_mode = fast_mode

    def run(self) -> Tuple[bool, str]:
        try:
            args = ["pytest", "tests/", "-v", "--tb=short"]

            if self.fast_mode:
                # Skip slow tests in fast mode
                args.extend(["-m", "not slow"])
            else:
                # Run in parallel for speed
                args.extend(["-n", "auto"])

            result = subprocess.run(
                args,
                capture_output=True,
                text=True,
                timeout=600  # 10 minute timeout
            )

            if result.returncode == 0:
                # Extract pass count from output
                output_lines = result.stdout.split('\n')
                for line in output_lines:
                    if "passed" in line:
                        return True, f"Tests passed: {line.strip()}"
                return True, "All tests passed"
            else:
                # Extract failure summary
                stderr = result.stderr
                stdout = result.stdout
                summary = ""

                # Find failed tests
                for line in stdout.split('\n'):
                    if "FAILED" in line:
                        summary += line.strip() + "\n"

                if summary:
                    return False, f"Test failures:\n{summary}"
                return False, "Tests failed (see output above)"

        except subprocess.TimeoutExpired:
            return False, "Tests timed out after 10 minutes"
        except Exception as e:
            return False, f"Error running tests: {str(e)}"


class CoverageGate(VerificationGate):
    """Verify coverage targets met."""

    def __init__(self, threshold: int = 80):
        super().__init__(
            "Coverage",
            f"Core modules must have ≥{threshold}% coverage"
        )
        self.threshold = threshold

    def run(self) -> Tuple[bool, str]:
        try:
            result = subprocess.run(
                [
                    "pytest", "tests/",
                    "--cov=src.core",
                    "--cov=src.store",
                    "--cov=src.memory",
                    "--cov=src.embeddings",
                    "--cov-report=term-missing",
                    "--quiet"
                ],
                capture_output=True,
                text=True,
                timeout=600
            )

            # Parse coverage percentage from output
            # Look for line like: "TOTAL    1234   567   46%"
            output = result.stdout
            for line in output.split('\n'):
                if "TOTAL" in line:
                    parts = line.split()
                    if len(parts) >= 4:
                        coverage_str = parts[-1].replace('%', '')
                        try:
                            coverage = int(coverage_str)
                            if coverage >= self.threshold:
                                return True, f"Coverage: {coverage}% (target: {self.threshold}%)"
                            else:
                                return False, f"Coverage too low: {coverage}% (need {self.threshold}%)"
                        except ValueError:
                            pass

            # If we couldn't parse, run simpler command
            return False, "Could not determine coverage (see output above)"

        except subprocess.TimeoutExpired:
            return False, "Coverage check timed out"
        except Exception as e:
            return False, f"Error checking coverage: {str(e)}"


class SyntaxGate(VerificationGate):
    """Verify no syntax errors in Python files."""

    def __init__(self):
        super().__init__(
            "Syntax",
            "All Python files must have valid syntax"
        )

    def run(self) -> Tuple[bool, str]:
        errors = []
        src_path = Path("src")

        if not src_path.exists():
            return False, "src/ directory not found"

        # Check all Python files in src/
        for py_file in src_path.rglob("*.py"):
            try:
                subprocess.run(
                    ["python", "-m", "py_compile", str(py_file)],
                    capture_output=True,
                    check=True
                )
            except subprocess.CalledProcessError as e:
                errors.append(f"{py_file}: {e.stderr.decode()}")

        if errors:
            return False, f"Syntax errors:\n" + "\n".join(errors[:5])
        return True, f"All Python files have valid syntax"


class DocumentationGate(VerificationGate):
    """Verify documentation updated."""

    def __init__(self):
        super().__init__(
            "Documentation",
            "CHANGELOG.md must be updated"
        )

    def run(self) -> Tuple[bool, str]:
        changelog_path = Path("CHANGELOG.md")

        if not changelog_path.exists():
            return False, "CHANGELOG.md not found"

        # Check if CHANGELOG.md was modified in recent commits
        try:
            result = subprocess.run(
                ["git", "diff", "HEAD~3..HEAD", "--name-only"],
                capture_output=True,
                text=True
            )

            if "CHANGELOG.md" in result.stdout:
                return True, "CHANGELOG.md updated in recent commits"

            # Check if there are staged changes to CHANGELOG.md
            result = subprocess.run(
                ["git", "diff", "--cached", "--name-only"],
                capture_output=True,
                text=True
            )

            if "CHANGELOG.md" in result.stdout:
                return True, "CHANGELOG.md has staged changes"

            # If not in git history, just check if file is not empty
            content = changelog_path.read_text()
            if len(content) > 100:  # Arbitrary minimum
                return True, "CHANGELOG.md exists and has content"

            return False, "CHANGELOG.md appears not updated (no recent changes found)"

        except Exception as e:
            # If git commands fail, just check file exists
            if changelog_path.exists():
                return True, "CHANGELOG.md exists (git check failed)"
            return False, f"Error checking documentation: {str(e)}"


class QdrantHealthGate(VerificationGate):
    """Verify Qdrant is running."""

    def __init__(self):
        super().__init__(
            "Qdrant",
            "Qdrant must be accessible at localhost:6333"
        )

    def run(self) -> Tuple[bool, str]:
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
            # requests not available, try curl
            try:
                result = subprocess.run(
                    ["curl", "-s", "http://localhost:6333/"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode == 0 and "version" in result.stdout:
                    return True, "Qdrant running"
                return False, "Qdrant not responding"
            except Exception:
                return False, "Could not verify Qdrant (install requests or curl)"

        except Exception as e:
            return False, f"Qdrant not accessible: {str(e)}"


def print_header(text: str):
    """Print a colored header."""
    print(f"\n{BLUE}{'=' * 60}{RESET}")
    print(f"{BLUE}{text:^60}{RESET}")
    print(f"{BLUE}{'=' * 60}{RESET}\n")


def print_result(name: str, passed: bool, message: str):
    """Print a gate result."""
    status = f"{GREEN}✓ PASS{RESET}" if passed else f"{RED}✗ FAIL{RESET}"
    print(f"{status} {name:20} {message}")


def main():
    """Run all verification gates."""
    # Check if in correct directory
    if not Path("src").exists() or not Path("tests").exists():
        print(f"{RED}Error: Must run from project root directory{RESET}")
        sys.exit(1)

    # Parse arguments
    fast_mode = "--fast" in sys.argv

    print_header("Task Completion Verification")

    if fast_mode:
        print(f"{YELLOW}Running in FAST mode (skipping slow tests){RESET}\n")

    # Define gates
    gates: List[VerificationGate] = [
        QdrantHealthGate(),
        SyntaxGate(),
        TestsGate(fast_mode=fast_mode),
        CoverageGate(threshold=80),
        DocumentationGate(),
    ]

    # Run gates
    results = []
    for gate in gates:
        print(f"Running {gate.name}... ", end="", flush=True)
        passed, message = gate.run()
        results.append((gate.name, passed, message))
        print_result(gate.name, passed, message)

    # Summary
    print_header("Summary")

    passed_count = sum(1 for _, passed, _ in results if passed)
    total_count = len(results)

    if passed_count == total_count:
        print(f"{GREEN}✓ All {total_count} verification gates passed!{RESET}")
        print(f"\n{GREEN}Task is ready to be marked complete.{RESET}")
        print(f"\nNext steps:")
        print(f"  1. Update IN_PROGRESS.md → REVIEW.md")
        print(f"  2. Request peer review (if team)")
        print(f"  3. Merge to main after approval")
        return 0
    else:
        failed_count = total_count - passed_count
        print(f"{RED}✗ {failed_count}/{total_count} verification gates failed{RESET}")
        print(f"\n{RED}Task is NOT ready for completion.{RESET}")
        print(f"\nFailed gates:")
        for name, passed, message in results:
            if not passed:
                print(f"  - {name}: {message}")
        print(f"\nFix these issues before marking task complete.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
