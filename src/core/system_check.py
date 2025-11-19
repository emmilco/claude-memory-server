"""System prerequisite checking for installation validation."""

import platform
import subprocess
import sys
from dataclasses import dataclass
from typing import Optional, List


@dataclass
class SystemRequirement:
    """A system requirement check result."""

    name: str
    installed: bool
    version: Optional[str]
    minimum_version: Optional[str]
    install_command: str
    priority: str  # "required", "recommended", "optional"


class SystemChecker:
    """Check system prerequisites for installation."""

    def __init__(self):
        """Initialize system checker with OS detection."""
        self.os_type = platform.system()  # 'Darwin', 'Linux', 'Windows'
        self.os_version = platform.release()
        self.os_platform = platform.platform()

    def check_python_version(self) -> SystemRequirement:
        """Check Python version meets requirements."""
        version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        major_minor = f"{sys.version_info.major}.{sys.version_info.minor}"
        meets_requirements = sys.version_info >= (3, 9)

        if self.os_type == "Darwin":
            install = "brew install python@3.11"
        elif self.os_type == "Linux":
            install = (
                "# Ubuntu/Debian:\n"
                "sudo apt-get update && sudo apt-get install python3.11\n"
                "# Fedora:\n"
                "sudo dnf install python3.11\n"
                "# RHEL/CentOS:\n"
                "sudo yum install python3.11"
            )
        else:  # Windows
            install = "Download from https://www.python.org/downloads/"

        return SystemRequirement(
            name="Python",
            installed=meets_requirements,
            version=version,
            minimum_version="3.9.0",
            install_command=install,
            priority="required",
        )

    def check_pip(self) -> SystemRequirement:
        """Check if pip is installed and up to date."""
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            installed = result.returncode == 0

            if installed:
                # Extract version from output like "pip 23.0.1 from ..."
                version_line = result.stdout.split()[1]
                version = version_line
            else:
                version = None
        except (FileNotFoundError, subprocess.TimeoutExpired):
            installed = False
            version = None

        if self.os_type == "Darwin":
            install = "python3 -m ensurepip --upgrade\n# Or: brew install python"
        elif self.os_type == "Linux":
            install = (
                "# Ubuntu/Debian:\n"
                "sudo apt-get install python3-pip\n"
                "# Fedora/RHEL:\n"
                "sudo dnf install python3-pip"
            )
        else:  # Windows
            install = "python -m ensurepip --upgrade"

        return SystemRequirement(
            name="pip",
            installed=installed,
            version=version,
            minimum_version="20.0",
            install_command=install,
            priority="required",
        )

    def check_docker(self) -> SystemRequirement:
        """Check if Docker is installed and running."""
        installed = False
        version = None
        running = False

        try:
            # Check if Docker is installed
            result = subprocess.run(
                ["docker", "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            installed = result.returncode == 0

            if installed:
                # Extract version from output like "Docker version 24.0.6, build ..."
                version_parts = result.stdout.split()
                if len(version_parts) >= 3:
                    version = version_parts[2].rstrip(",")

            # Check if Docker daemon is running
            if installed:
                daemon_result = subprocess.run(
                    ["docker", "ps"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                running = daemon_result.returncode == 0

        except (FileNotFoundError, subprocess.TimeoutExpired):
            installed = False
            version = None
            running = False

        if self.os_type == "Darwin":
            install = (
                "# Option 1: Homebrew\n"
                "brew install --cask docker\n\n"
                "# Option 2: Direct download\n"
                "Download Docker Desktop from https://www.docker.com/products/docker-desktop"
            )
        elif self.os_type == "Linux":
            install = (
                "# Install Docker Engine\n"
                "curl -fsSL https://get.docker.com | sh\n\n"
                "# Start Docker service\n"
                "sudo systemctl enable docker\n"
                "sudo systemctl start docker\n\n"
                "# Add user to docker group (optional, requires re-login)\n"
                "sudo usermod -aG docker $USER"
            )
        else:  # Windows
            install = "Download Docker Desktop from https://www.docker.com/products/docker-desktop"

        # If installed but not running, show how to start it
        if installed and not running:
            version = f"{version} (not running)"
            if self.os_type == "Darwin":
                install = "Open Docker Desktop application"
            elif self.os_type == "Linux":
                install = "sudo systemctl start docker"
            else:  # Windows
                install = "Start Docker Desktop"

        return SystemRequirement(
            name="Docker",
            installed=installed and running,
            version=version,
            minimum_version=None,
            install_command=install,
            priority="recommended",  # Required only for Qdrant
        )

    def check_rust(self) -> SystemRequirement:
        """Check if Rust/cargo is installed."""
        try:
            result = subprocess.run(
                ["cargo", "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            installed = result.returncode == 0

            if installed:
                # Extract version from output like "cargo 1.75.0 (1d8b05cdd 2023-11-20)"
                version_parts = result.stdout.split()
                if len(version_parts) >= 2:
                    version = version_parts[1]
                else:
                    version = "installed"
            else:
                version = None
        except (FileNotFoundError, subprocess.TimeoutExpired):
            installed = False
            version = None

        # Rust install is same on all platforms
        install = (
            "# Install Rust via rustup\n"
            "curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh\n\n"
            "# After installation, activate Rust\n"
            "source $HOME/.cargo/env\n\n"
            "# Verify installation\n"
            "cargo --version"
        )

        if self.os_type == "Windows":
            install = (
                "# Download and run rustup-init.exe from:\n"
                "https://rustup.rs/\n\n"
                "# Or use Windows Subsystem for Linux (WSL) and follow Linux instructions"
            )

        return SystemRequirement(
            name="Rust",
            installed=installed,
            version=version,
            minimum_version=None,
            install_command=install,
            priority="optional",  # Only for fast parser
        )

    def check_git(self) -> SystemRequirement:
        """Check if Git is installed."""
        try:
            result = subprocess.run(
                ["git", "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            installed = result.returncode == 0

            if installed:
                # Extract version from output like "git version 2.39.2"
                version_parts = result.stdout.split()
                if len(version_parts) >= 3:
                    version = version_parts[2]
                else:
                    version = "installed"
            else:
                version = None
        except (FileNotFoundError, subprocess.TimeoutExpired):
            installed = False
            version = None

        if self.os_type == "Darwin":
            install = (
                "# Option 1: Xcode Command Line Tools\n"
                "xcode-select --install\n\n"
                "# Option 2: Homebrew\n"
                "brew install git"
            )
        elif self.os_type == "Linux":
            install = (
                "# Ubuntu/Debian:\n"
                "sudo apt-get install git\n"
                "# Fedora/RHEL:\n"
                "sudo dnf install git"
            )
        else:  # Windows
            install = "Download from https://git-scm.com/download/win"

        return SystemRequirement(
            name="Git",
            installed=installed,
            version=version,
            minimum_version="2.0",
            install_command=install,
            priority="recommended",
        )

    def check_all(self) -> List[SystemRequirement]:
        """Check all system requirements."""
        return [
            self.check_python_version(),
            self.check_pip(),
            self.check_git(),
            self.check_docker(),
            self.check_rust(),
        ]

    def print_report(
        self, requirements: List[SystemRequirement], show_install_commands: bool = True
    ):
        """
        Print a formatted report of system checks.

        Args:
            requirements: List of system requirements to report
            show_install_commands: If True, show install commands for missing requirements
        """
        print("\n📋 System Requirements Check\n")
        print(f"OS: {self.os_type} {self.os_version}\n")
        print(f"Platform: {self.os_platform}\n")

        # Group by priority
        required = [r for r in requirements if r.priority == "required"]
        recommended = [r for r in requirements if r.priority == "recommended"]
        optional = [r for r in requirements if r.priority == "optional"]

        def print_requirement(req: SystemRequirement):
            status = "✅" if req.installed else "❌"
            version_str = f" ({req.version})" if req.version else ""
            priority_str = req.priority.upper()

            print(f"{status} {req.name}{version_str} [{priority_str}]")

            if not req.installed and show_install_commands:
                print(f"\n   📦 Install:")
                for line in req.install_command.split("\n"):
                    print(f"   {line}")
                print()

        if required:
            print("Required:")
            for req in required:
                print_requirement(req)
            print()

        if recommended:
            print("Recommended:")
            for req in recommended:
                print_requirement(req)
            print()

        if optional:
            print("Optional (for performance):")
            for req in optional:
                print_requirement(req)
            print()

    def has_critical_failures(self, requirements: List[SystemRequirement]) -> bool:
        """Check if there are any critical (required) failures."""
        return any(not req.installed for req in requirements if req.priority == "required")

    def get_summary(self, requirements: List[SystemRequirement]) -> str:
        """
        Get a one-line summary of the system check.

        Args:
            requirements: List of system requirements

        Returns:
            Summary string
        """
        required = [r for r in requirements if r.priority == "required"]
        required_ok = all(r.installed for r in required)

        recommended = [r for r in requirements if r.priority == "recommended"]
        recommended_ok = all(r.installed for r in recommended)

        optional = [r for r in requirements if r.priority == "optional"]
        optional_ok = all(r.installed for r in optional)

        if required_ok and recommended_ok and optional_ok:
            return "✅ All requirements met"
        elif required_ok and recommended_ok:
            return "⚠️  Required and recommended met, optional missing"
        elif required_ok:
            return "⚠️  Required met, recommended/optional missing"
        else:
            return "❌ Required prerequisites missing"
