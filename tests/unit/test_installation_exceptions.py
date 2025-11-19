"""Tests for installation-related exceptions."""

import pytest
from unittest.mock import patch
from src.core.exceptions import (
    DependencyError,
    DockerNotRunningError,
    RustBuildError,
)


class TestDependencyError:
    """Tests for DependencyError exception."""

    @patch("platform.system")
    def test_dependency_error_darwin(self, mock_system):
        """Test DependencyError on macOS."""
        mock_system.return_value = "Darwin"

        with pytest.raises(DependencyError) as exc_info:
            raise DependencyError("sentence-transformers", "required for embeddings")

        error_message = str(exc_info.value)
        assert "sentence-transformers" in error_message
        assert "required for embeddings" in error_message
        assert "pip install" in error_message
        assert "Solution:" in error_message

    @patch("platform.system")
    def test_dependency_error_linux(self, mock_system):
        """Test DependencyError on Linux."""
        mock_system.return_value = "Linux"

        with pytest.raises(DependencyError) as exc_info:
            raise DependencyError("numpy")

        error_message = str(exc_info.value)
        assert "numpy" in error_message
        assert "pip install" in error_message
        assert "apt-get" in error_message  # Should suggest system package too

    @patch("platform.system")
    def test_dependency_error_windows(self, mock_system):
        """Test DependencyError on Windows."""
        mock_system.return_value = "Windows"

        with pytest.raises(DependencyError) as exc_info:
            raise DependencyError("qdrant-client")

        error_message = str(exc_info.value)
        assert "qdrant-client" in error_message
        assert "pip install" in error_message

    def test_dependency_error_has_docs_url(self):
        """Test DependencyError includes docs URL."""
        try:
            raise DependencyError("test-package", "test context")
        except DependencyError as e:
            assert e.docs_url is not None
            assert "setup.md" in e.docs_url
            error_str = str(e)
            assert "Docs:" in error_str

    def test_dependency_error_without_context(self):
        """Test DependencyError without context."""
        with pytest.raises(DependencyError) as exc_info:
            raise DependencyError("test-package")

        error_message = str(exc_info.value)
        assert "test-package" in error_message
        assert "Solution:" in error_message

    def test_dependency_error_with_context(self):
        """Test DependencyError with context."""
        with pytest.raises(DependencyError) as exc_info:
            raise DependencyError("test-package", "needed for testing")

        error_message = str(exc_info.value)
        assert "test-package" in error_message
        assert "needed for testing" in error_message


class TestDockerNotRunningError:
    """Tests for DockerNotRunningError exception."""

    @patch("platform.system")
    def test_docker_error_darwin(self, mock_system):
        """Test DockerNotRunningError on macOS."""
        mock_system.return_value = "Darwin"

        with pytest.raises(DockerNotRunningError) as exc_info:
            raise DockerNotRunningError()

        error_message = str(exc_info.value)
        assert "Docker" in error_message
        assert "Qdrant" in error_message
        assert "Docker Desktop" in error_message
        assert "SQLite" in error_message
        assert "Solution:" in error_message

    @patch("platform.system")
    def test_docker_error_linux(self, mock_system):
        """Test DockerNotRunningError on Linux."""
        mock_system.return_value = "Linux"

        with pytest.raises(DockerNotRunningError) as exc_info:
            raise DockerNotRunningError()

        error_message = str(exc_info.value)
        assert "Docker" in error_message
        assert "systemctl" in error_message
        assert "SQLite" in error_message

    @patch("platform.system")
    def test_docker_error_windows(self, mock_system):
        """Test DockerNotRunningError on Windows."""
        mock_system.return_value = "Windows"

        with pytest.raises(DockerNotRunningError) as exc_info:
            raise DockerNotRunningError()

        error_message = str(exc_info.value)
        assert "Docker" in error_message
        assert "Docker Desktop" in error_message

    def test_docker_error_has_docs_url(self):
        """Test DockerNotRunningError includes docs URL."""
        try:
            raise DockerNotRunningError()
        except DockerNotRunningError as e:
            assert e.docs_url is not None
            assert "docker-setup" in e.docs_url.lower()
            error_str = str(e)
            assert "Docs:" in error_str

    def test_docker_error_mentions_fallback(self):
        """Test DockerNotRunningError mentions SQLite fallback."""
        with pytest.raises(DockerNotRunningError) as exc_info:
            raise DockerNotRunningError()

        error_message = str(exc_info.value)
        assert "SQLite" in error_message
        assert "fall back" in error_message.lower()


class TestRustBuildError:
    """Tests for RustBuildError exception."""

    def test_rust_build_error(self):
        """Test RustBuildError with build failure message."""
        with pytest.raises(RustBuildError) as exc_info:
            raise RustBuildError("maturin: command not found")

        error_message = str(exc_info.value)
        assert "Rust parser" in error_message
        assert "maturin: command not found" in error_message
        assert "Solution:" in error_message

    def test_rust_build_error_mentions_fallback(self):
        """Test RustBuildError mentions Python fallback."""
        with pytest.raises(RustBuildError) as exc_info:
            raise RustBuildError("build failed")

        error_message = str(exc_info.value)
        assert "Python parser" in error_message
        assert "fall back" in error_message.lower()
        assert "automatically" in error_message.lower()

    def test_rust_build_error_has_install_instructions(self):
        """Test RustBuildError includes Rust install instructions."""
        with pytest.raises(RustBuildError) as exc_info:
            raise RustBuildError("cargo not found")

        error_message = str(exc_info.value)
        assert "rustup" in error_message
        assert "curl" in error_message
        assert "maturin develop" in error_message

    def test_rust_build_error_has_docs_url(self):
        """Test RustBuildError includes docs URL."""
        try:
            raise RustBuildError("build failed")
        except RustBuildError as e:
            assert e.docs_url is not None
            assert "rust-parser" in e.docs_url.lower()
            error_str = str(e)
            assert "Docs:" in error_str

    def test_rust_build_error_mentions_performance(self):
        """Test RustBuildError mentions performance impact."""
        with pytest.raises(RustBuildError) as exc_info:
            raise RustBuildError("build failed")

        error_message = str(exc_info.value)
        assert "10-20x slower" in error_message or "slower" in error_message


class TestExceptionInheritance:
    """Tests for exception inheritance."""

    def test_dependency_error_is_memory_rag_error(self):
        """Test DependencyError inherits from MemoryRAGError."""
        from src.core.exceptions import MemoryRAGError

        error = DependencyError("test")
        assert isinstance(error, MemoryRAGError)

    def test_docker_error_is_memory_rag_error(self):
        """Test DockerNotRunningError inherits from MemoryRAGError."""
        from src.core.exceptions import MemoryRAGError

        error = DockerNotRunningError()
        assert isinstance(error, MemoryRAGError)

    def test_rust_build_error_is_memory_rag_error(self):
        """Test RustBuildError inherits from MemoryRAGError."""
        from src.core.exceptions import MemoryRAGError

        error = RustBuildError("test")
        assert isinstance(error, MemoryRAGError)


class TestExceptionFormatting:
    """Tests for exception message formatting."""

    def test_exception_has_solution_section(self):
        """Test exceptions have clear Solution section."""
        error = DependencyError("test-package")
        error_str = str(error)

        assert "💡 Solution:" in error_str or "Solution:" in error_str

    def test_exception_has_docs_section(self):
        """Test exceptions have Docs section."""
        error = DependencyError("test-package")
        error_str = str(error)

        assert "📖 Docs:" in error_str or "Docs:" in error_str

    def test_solution_attribute_accessible(self):
        """Test solution attribute is accessible."""
        error = DependencyError("test-package")
        assert error.solution is not None
        assert "pip install" in error.solution

    def test_docs_url_attribute_accessible(self):
        """Test docs_url attribute is accessible."""
        error = DependencyError("test-package")
        assert error.docs_url is not None
        assert "http" in error.docs_url
