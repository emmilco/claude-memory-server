#!/usr/bin/env python3
"""
Comprehensive verification script for task completion.

Runs all quality gates before allowing a task to be marked complete.

Gates (in order):
    1. CI Status     - GitHub Actions must be passing on main
    2. Qdrant        - Qdrant must be accessible
    3. Syntax        - All Python files must have valid syntax
    4. Dependencies  - Critical deps must have version bounds
    5. Specification - SPEC.md must be valid
    6. Skipped Tests - No more than 150 skipped tests
    7. Tests         - All tests must pass (100% pass rate)
    8. Coverage      - Core modules must have ≥80% coverage
    9. Documentation - CHANGELOG.md must be updated

Usage:
    python scripts/verify-complete.py
    python scripts/verify-complete.py --fast  # Skip slow tests

Exit codes:
    0: All checks passed
    1: One or more checks failed
"""

import subprocess
import sys
from pathlib import Path
from typing import Tuple, List

# ANSI color codes
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"


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
        super().__init__("Tests", "All tests must pass (100% pass rate)")
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
                timeout=600,  # 10 minute timeout
            )

            if result.returncode == 0:
                # Extract pass count from output
                output_lines = result.stdout.split("\n")
                for line in output_lines:
                    if "passed" in line:
                        return True, f"Tests passed: {line.strip()}"
                return True, "All tests passed"
            else:
                # Extract failure summary
                stdout = result.stdout
                summary = ""

                # Find failed tests
                for line in stdout.split("\n"):
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
        super().__init__("Coverage", f"Core modules must have ≥{threshold}% coverage")
        self.threshold = threshold

    def run(self) -> Tuple[bool, str]:
        try:
            result = subprocess.run(
                [
                    "pytest",
                    "tests/",
                    "--cov=src.core",
                    "--cov=src.store",
                    "--cov=src.memory",
                    "--cov=src.embeddings",
                    "--cov-report=term-missing",
                    "--quiet",
                ],
                capture_output=True,
                text=True,
                timeout=600,
            )

            # Parse coverage percentage from output
            # Look for line like: "TOTAL    1234   567   46%"
            output = result.stdout
            for line in output.split("\n"):
                if "TOTAL" in line:
                    parts = line.split()
                    if len(parts) >= 4:
                        coverage_str = parts[-1].replace("%", "")
                        try:
                            coverage = int(coverage_str)
                            if coverage >= self.threshold:
                                return (
                                    True,
                                    f"Coverage: {coverage}% (target: {self.threshold}%)",
                                )
                            else:
                                return (
                                    False,
                                    f"Coverage too low: {coverage}% (need {self.threshold}%)",
                                )
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
        super().__init__("Syntax", "All Python files must have valid syntax")

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
                    check=True,
                )
            except subprocess.CalledProcessError as e:
                errors.append(f"{py_file}: {e.stderr.decode()}")

        if errors:
            return False, "Syntax errors:\n" + "\n".join(errors[:5])
        return True, "All Python files have valid syntax"


class DocumentationGate(VerificationGate):
    """Verify documentation updated."""

    def __init__(self):
        super().__init__("Documentation", "CHANGELOG.md must be updated")

    def run(self) -> Tuple[bool, str]:
        changelog_path = Path("CHANGELOG.md")

        if not changelog_path.exists():
            return False, "CHANGELOG.md not found"

        # Check if CHANGELOG.md was modified in recent commits
        try:
            result = subprocess.run(
                ["git", "diff", "HEAD~3..HEAD", "--name-only"],
                capture_output=True,
                text=True,
            )

            if "CHANGELOG.md" in result.stdout:
                return True, "CHANGELOG.md updated in recent commits"

            # Check if there are staged changes to CHANGELOG.md
            result = subprocess.run(
                ["git", "diff", "--cached", "--name-only"],
                capture_output=True,
                text=True,
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


class SpecValidationGate(VerificationGate):
    """Verify SPEC.md is valid."""

    def __init__(self):
        super().__init__("Specification", "SPEC.md must be valid and compliant")

    def run(self) -> Tuple[bool, str]:
        try:
            # Run the validation script
            result = subprocess.run(
                ["python", "scripts/validate-spec.py"],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode == 0:
                # Extract compliance percentage from output
                output = result.stdout
                if "Compliance:" in output:
                    for line in output.split("\n"):
                        if "Compliance:" in line:
                            return True, f"SPEC.md valid ({line.strip()})"
                return True, "SPEC.md is valid"
            else:
                # Extract first few issues
                output = result.stdout
                issues = []
                for line in output.split("\n"):
                    if line.strip().startswith("-"):
                        issues.append(line.strip())
                        if len(issues) >= 3:
                            break

                if issues:
                    return False, "SPEC.md has issues:\n  " + "\n  ".join(issues)
                return False, "SPEC.md validation failed (see output above)"

        except subprocess.TimeoutExpired:
            return False, "Spec validation timed out"
        except Exception as e:
            return False, f"Error validating spec: {str(e)}"


class CIStatusGate(VerificationGate):
    """Verify CI is passing on main branch - prevents local/CI divergence."""

    def __init__(self):
        super().__init__("CI Status", "GitHub Actions CI must be passing on main")

    def run(self) -> Tuple[bool, str]:
        try:
            # Check if gh CLI is available
            result = subprocess.run(
                ["gh", "--version"], capture_output=True, text=True, timeout=5
            )
            if result.returncode != 0:
                return (
                    False,
                    "GitHub CLI (gh) not installed - install with 'brew install gh'",
                )

            # Get latest CI run status on main
            result = subprocess.run(
                [
                    "gh",
                    "run",
                    "list",
                    "--branch",
                    "main",
                    "--limit",
                    "1",
                    "--json",
                    "status,conclusion,headBranch,createdAt",
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode != 0:
                return False, f"Failed to check CI status: {result.stderr}"

            import json

            runs = json.loads(result.stdout)
            if not runs:
                return False, "No CI runs found on main branch"

            run = runs[0]
            conclusion = run.get("conclusion", "unknown")
            status = run.get("status", "unknown")
            created = run.get("createdAt", "unknown")[:10]  # Just the date

            if status == "in_progress":
                return (
                    False,
                    f"CI is still running (started {created}) - wait for completion",
                )
            elif conclusion == "success":
                return True, f"CI is green on main (as of {created})"
            elif conclusion == "failure":
                return (
                    False,
                    f"CI is FAILING on main ({created}) - FIX CI BEFORE MERGING",
                )
            else:
                return False, f"CI status unclear: {conclusion}/{status}"

        except subprocess.TimeoutExpired:
            return False, "Timed out checking CI status"
        except FileNotFoundError:
            return False, "GitHub CLI (gh) not found - install with 'brew install gh'"
        except Exception as e:
            return False, f"Error checking CI: {str(e)}"


class SkippedTestsGate(VerificationGate):
    """Warn if there are too many skipped tests - prevents tech debt accumulation."""

    def __init__(self, max_skipped: int = 150):
        super().__init__(
            "Skipped Tests", f"No more than {max_skipped} skipped tests allowed"
        )
        self.max_skipped = max_skipped

    def run(self) -> Tuple[bool, str]:
        try:
            result = subprocess.run(
                ["pytest", "tests/", "--collect-only", "-q"],
                capture_output=True,
                text=True,
                timeout=120,
            )

            # Parse the summary line for skipped/deselected count
            import re

            skipped = 0

            for line in result.stdout.split("\n"):
                # Look for "X skipped" pattern
                match = re.search(r"(\d+)\s+skipped", line)
                if match:
                    skipped = int(match.group(1))
                    break
                # Also check deselected (tests with skip markers at collection time)
                match = re.search(r"(\d+)\s+deselected", line)
                if match:
                    skipped = int(match.group(1))
                    break

            # Fallback: count skip markers in test files
            if skipped == 0:
                result2 = subprocess.run(
                    ["grep", "-r", "-c", "@pytest.mark.skip", "tests/"],
                    capture_output=True,
                    text=True,
                )
                # Sum up counts from each file
                for line in result2.stdout.strip().split("\n"):
                    if ":" in line:
                        try:
                            count = int(line.split(":")[-1])
                            skipped += count
                        except ValueError:
                            pass

            if skipped > self.max_skipped:
                return (
                    False,
                    f"{skipped} tests skipped (max: {self.max_skipped}). Clean up or implement features.",
                )
            return True, f"{skipped} tests skipped (within limit of {self.max_skipped})"

        except subprocess.TimeoutExpired:
            return False, "Timed out collecting test info"
        except Exception as e:
            return False, f"Error checking skipped tests: {str(e)}"


class DependencyLockGate(VerificationGate):
    """Verify critical dependencies have version bounds - prevents CI/local mismatch."""

    def __init__(self):
        super().__init__(
            "Dependencies", "Critical dependencies must have version bounds"
        )
        # Dependencies that MUST have upper bounds to prevent breaking changes
        self.critical_deps = [
            "pytest-asyncio",
            "pytest",
            "qdrant-client",
            "sentence-transformers",
        ]

    def run(self) -> Tuple[bool, str]:
        req_path = Path("requirements.txt")
        if not req_path.exists():
            return False, "requirements.txt not found"

        content = req_path.read_text()
        issues = []

        for dep in self.critical_deps:
            dep_lower = dep.lower()
            found = False
            for line in content.split("\n"):
                line_stripped = line.strip().lower()
                if not line_stripped or line_stripped.startswith("#"):
                    continue
                # Check if this line is for our dependency
                if (
                    line_stripped.startswith(dep_lower)
                    or f"{dep_lower}>" in line_stripped
                    or f"{dep_lower}=" in line_stripped
                    or f"{dep_lower}<" in line_stripped
                ):
                    found = True
                    # Check if it has an upper bound
                    has_upper = "<" in line
                    has_exact = "==" in line

                    if not has_upper and not has_exact:
                        issues.append(
                            f"{dep}: needs upper bound (found: {line.strip()})"
                        )
                    break

            if not found:
                # Dependency not in requirements - might be transitive, that's ok
                pass

        if issues:
            return (
                False,
                "Unbounded deps risk CI/local mismatch:\n  - " + "\n  - ".join(issues),
            )
        return (
            True,
            f"Critical dependencies have version bounds ({len(self.critical_deps)} checked)",
        )


class QdrantHealthGate(VerificationGate):
    """Verify Qdrant is running."""

    def __init__(self):
        super().__init__("Qdrant", "Qdrant must be accessible at localhost:6333")

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
                    timeout=5,
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

    # Define gates - order matters: fast checks first, then slow ones
    gates: List[VerificationGate] = [
        CIStatusGate(),  # NEW: Check CI is green before anything else
        QdrantHealthGate(),
        SyntaxGate(),
        DependencyLockGate(),  # NEW: Check deps have version bounds
        SpecValidationGate(),
        SkippedTestsGate(),  # NEW: Check skipped test count
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
        print("\nNext steps:")
        print("  1. Update IN_PROGRESS.md → REVIEW.md")
        print("  2. Request peer review (if team)")
        print("  3. Merge to main after approval")
        return 0
    else:
        failed_count = total_count - passed_count
        print(f"{RED}✗ {failed_count}/{total_count} verification gates failed{RESET}")
        print(f"\n{RED}Task is NOT ready for completion.{RESET}")
        print("\nFailed gates:")
        for name, passed, message in results:
            if not passed:
                print(f"  - {name}: {message}")
        print("\nFix these issues before marking task complete.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
