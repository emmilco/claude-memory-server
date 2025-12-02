"""Tests for system prerequisite checking."""

from unittest.mock import Mock, patch
from src.core.system_check import SystemChecker, SystemRequirement


class TestSystemRequirement:
    """Tests for SystemRequirement dataclass."""

    def test_requirement_creation(self):
        """Test creating a system requirement."""
        req = SystemRequirement(
            name="Python",
            installed=True,
            version="3.11.0",
            minimum_version="3.9.0",
            install_command="brew install python",
            priority="required",
        )

        assert req.name == "Python"
        assert req.installed is True
        assert req.version == "3.11.0"
        assert req.minimum_version == "3.9.0"
        assert req.install_command == "brew install python"
        assert req.priority == "required"


class TestSystemChecker:
    """Tests for SystemChecker."""

    def test_checker_initialization(self):
        """Test checker initializes with OS detection."""
        checker = SystemChecker()

        assert checker.os_type in ["Darwin", "Linux", "Windows"]
        assert checker.os_version is not None
        assert checker.os_platform is not None

    def test_check_python_version(self):
        """Test Python version check."""
        checker = SystemChecker()
        req = checker.check_python_version()

        assert req.name == "Python"
        assert req.installed is True  # We're running Python
        assert req.priority == "required"
        assert req.minimum_version == "3.9.0"
        # Version should be valid format
        assert "." in req.version

    def test_check_pip(self):
        """Test pip availability check."""
        checker = SystemChecker()
        req = checker.check_pip()

        assert req.name == "pip"
        assert req.priority == "required"
        # pip should be installed if tests are running
        assert req.installed is True

    @patch("subprocess.run")
    def test_check_docker_installed(self, mock_run):
        """Test Docker detection when installed and running."""
        # Mock docker --version
        version_result = Mock()
        version_result.returncode = 0
        version_result.stdout = "Docker version 24.0.6, build ed223bc"

        # Mock docker ps
        ps_result = Mock()
        ps_result.returncode = 0

        mock_run.side_effect = [version_result, ps_result]

        checker = SystemChecker()
        req = checker.check_docker()

        assert req.name == "Docker"
        assert req.installed is True
        assert req.priority == "recommended"
        assert "24.0.6" in req.version

    @patch("subprocess.run")
    def test_check_docker_not_running(self, mock_run):
        """Test Docker detection when installed but not running."""
        # Mock docker --version (installed)
        version_result = Mock()
        version_result.returncode = 0
        version_result.stdout = "Docker version 24.0.6, build ed223bc"

        # Mock docker ps (not running)
        ps_result = Mock()
        ps_result.returncode = 1

        mock_run.side_effect = [version_result, ps_result]

        checker = SystemChecker()
        req = checker.check_docker()

        assert req.name == "Docker"
        assert req.installed is False  # Not running = not usable
        assert "not running" in req.version

    @patch("subprocess.run")
    def test_check_docker_not_installed(self, mock_run):
        """Test Docker detection when not installed."""
        mock_run.side_effect = FileNotFoundError()

        checker = SystemChecker()
        req = checker.check_docker()

        assert req.name == "Docker"
        assert req.installed is False
        assert req.priority == "recommended"

    @patch("subprocess.run")
    def test_check_rust_installed(self, mock_run):
        """Test Rust detection when installed."""
        result = Mock()
        result.returncode = 0
        result.stdout = "cargo 1.75.0 (1d8b05cdd 2023-11-20)"
        mock_run.return_value = result

        checker = SystemChecker()
        req = checker.check_rust()

        assert req.name == "Rust"
        assert req.installed is True
        assert req.priority == "optional"
        assert "1.75.0" in req.version

    @patch("subprocess.run")
    def test_check_rust_not_installed(self, mock_run):
        """Test Rust detection when not installed."""
        mock_run.side_effect = FileNotFoundError()

        checker = SystemChecker()
        req = checker.check_rust()

        assert req.name == "Rust"
        assert req.installed is False
        assert req.priority == "optional"

    @patch("subprocess.run")
    def test_check_git_installed(self, mock_run):
        """Test Git detection when installed."""
        result = Mock()
        result.returncode = 0
        result.stdout = "git version 2.39.2"
        mock_run.return_value = result

        checker = SystemChecker()
        req = checker.check_git()

        assert req.name == "Git"
        assert req.installed is True
        assert req.priority == "recommended"
        assert "2.39.2" in req.version

    def test_check_all(self):
        """Test checking all requirements."""
        checker = SystemChecker()
        requirements = checker.check_all()

        assert len(requirements) == 5  # Python, pip, Git, Docker, Rust

        # Should have all priorities
        required = [r for r in requirements if r.priority == "required"]
        recommended = [r for r in requirements if r.priority == "recommended"]
        optional = [r for r in requirements if r.priority == "optional"]

        assert len(required) >= 2  # At least Python and pip
        assert len(recommended) >= 1  # At least one recommended
        assert len(optional) >= 1  # At least Rust

    def test_has_critical_failures(self):
        """Test detecting critical failures."""
        checker = SystemChecker()

        # All OK
        requirements = [
            SystemRequirement("Test1", True, "1.0", None, "", "required"),
            SystemRequirement("Test2", True, "1.0", None, "", "recommended"),
        ]
        assert not checker.has_critical_failures(requirements)

        # Required failure
        requirements = [
            SystemRequirement("Test1", False, None, None, "", "required"),
            SystemRequirement("Test2", True, "1.0", None, "", "recommended"),
        ]
        assert checker.has_critical_failures(requirements)

        # Only optional failure
        requirements = [
            SystemRequirement("Test1", True, "1.0", None, "", "required"),
            SystemRequirement("Test2", False, None, None, "", "optional"),
        ]
        assert not checker.has_critical_failures(requirements)

    def test_get_summary(self):
        """Test summary generation."""
        checker = SystemChecker()

        # All OK
        requirements = [
            SystemRequirement("Test1", True, "1.0", None, "", "required"),
            SystemRequirement("Test2", True, "1.0", None, "", "recommended"),
            SystemRequirement("Test3", True, "1.0", None, "", "optional"),
        ]
        summary = checker.get_summary(requirements)
        assert "All requirements met" in summary

        # Required OK, optional missing
        requirements = [
            SystemRequirement("Test1", True, "1.0", None, "", "required"),
            SystemRequirement("Test2", True, "1.0", None, "", "recommended"),
            SystemRequirement("Test3", False, None, None, "", "optional"),
        ]
        summary = checker.get_summary(requirements)
        assert "optional missing" in summary

        # Required missing
        requirements = [
            SystemRequirement("Test1", False, None, None, "", "required"),
        ]
        summary = checker.get_summary(requirements)
        assert "Required prerequisites missing" in summary

    def test_print_report(self, capsys):
        """Test report printing."""
        checker = SystemChecker()

        requirements = [
            SystemRequirement(
                "Python", True, "3.11.0", "3.9.0", "brew install python", "required"
            ),
            SystemRequirement(
                "Docker", False, None, None, "docker install", "recommended"
            ),
        ]

        checker.print_report(requirements, show_install_commands=True)
        captured = capsys.readouterr()

        assert "System Requirements Check" in captured.out
        assert "Python" in captured.out
        assert "Docker" in captured.out
        assert "Required:" in captured.out
        assert "Recommended:" in captured.out

    @patch("platform.system")
    def test_os_specific_install_commands_darwin(self, mock_system):
        """Test install commands are OS-specific (macOS)."""
        mock_system.return_value = "Darwin"

        checker = SystemChecker()
        python_req = checker.check_python_version()

        assert "brew" in python_req.install_command.lower()

    @patch("platform.system")
    def test_os_specific_install_commands_linux(self, mock_system):
        """Test install commands are OS-specific (Linux)."""
        mock_system.return_value = "Linux"

        checker = SystemChecker()
        python_req = checker.check_python_version()

        assert (
            "apt-get" in python_req.install_command
            or "dnf" in python_req.install_command
        )

    @patch("platform.system")
    def test_os_specific_install_commands_windows(self, mock_system):
        """Test install commands are OS-specific (Windows)."""
        mock_system.return_value = "Windows"

        checker = SystemChecker()
        python_req = checker.check_python_version()

        assert "python.org" in python_req.install_command.lower()
