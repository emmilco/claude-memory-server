"""Tests for health check command."""

import pytest
import sys
import subprocess
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from src.cli.health_command import HealthCommand


class TestHealthCommandInitialization:
    """Test health command initialization."""

    def test_init_with_rich(self):
        """Test initialization when rich is available."""
        cmd = HealthCommand()
        assert cmd.console is not None
        assert cmd.checks == {}
        assert cmd.errors == []
        assert cmd.warnings == []
        assert cmd.recommendations == []

    def test_init_without_rich(self):
        """Test initialization when rich is not available."""
        with patch('src.cli.health_command.RICH_AVAILABLE', False):
            cmd = HealthCommand()
            assert cmd.console is None


class TestSystemChecks:
    """Test system requirement checks."""

    @pytest.mark.asyncio
    async def test_check_python_version_success(self):
        """Test Python version check with valid version."""
        cmd = HealthCommand()
        success, message = await cmd.check_python_version()

        assert success is True
        assert "3." in message
        # Should pass since we're running Python 3.8+

    @pytest.mark.asyncio
    async def test_check_python_version_old(self):
        """Test Python version check with old version."""
        cmd = HealthCommand()

        mock_version = MagicMock()
        mock_version.major = 3
        mock_version.minor = 7
        mock_version.micro = 0

        with patch('sys.version_info', mock_version):
            success, message = await cmd.check_python_version()
            assert success is False
            assert "3.7.0" in message

    @pytest.mark.asyncio
    async def test_check_disk_space_sufficient(self):
        """Test disk space check with sufficient space."""
        cmd = HealthCommand()
        success, message = await cmd.check_disk_space()

        # Should succeed if we have > 500MB
        assert success is True
        assert "GB available" in message

    @pytest.mark.asyncio
    async def test_check_disk_space_insufficient(self):
        """Test disk space check with insufficient space."""
        cmd = HealthCommand()

        mock_usage = MagicMock()
        mock_usage.free = 100 * 1024 * 1024  # 100MB

        with patch('shutil.disk_usage', return_value=mock_usage):
            success, message = await cmd.check_disk_space()
            assert success is False
            assert "need 0.5 GB" in message

    @pytest.mark.asyncio
    async def test_check_disk_space_error(self):
        """Test disk space check with error."""
        cmd = HealthCommand()

        with patch('shutil.disk_usage', side_effect=Exception("Disk error")):
            success, message = await cmd.check_disk_space()
            assert success is False
            assert "Could not check" in message

    @pytest.mark.asyncio
    async def test_check_memory_macos(self):
        """Test memory check on macOS."""
        cmd = HealthCommand()

        with patch('sys.platform', 'darwin'):
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = "hw.memsize: 17179869184"  # 16GB

            with patch('subprocess.run', return_value=mock_result):
                success, message = await cmd.check_memory()
                assert success is True
                assert "GB total" in message

    @pytest.mark.asyncio
    async def test_check_memory_unknown_platform(self):
        """Test memory check on unknown platform."""
        cmd = HealthCommand()

        with patch('sys.platform', 'unknown'):
            success, message = await cmd.check_memory()
            assert success is True
            assert "Unknown" in message or "Available" in message


class TestParserChecks:
    """Test parser availability checks."""

    @pytest.mark.asyncio
    async def test_check_rust_parser_available(self):
        """Test Rust parser check when available."""
        cmd = HealthCommand()

        with patch.dict('sys.modules', {'mcp_performance_core': MagicMock()}):
            success, message = await cmd.check_rust_parser()
            assert success is True
            assert "optimal" in message.lower()

    @pytest.mark.asyncio
    async def test_check_rust_parser_not_available(self):
        """Test Rust parser check when not available."""
        cmd = HealthCommand()

        with patch('builtins.__import__', side_effect=ImportError("No module named 'mcp_performance_core'")):
            success, message = await cmd.check_rust_parser()
            assert success is False
            assert "fallback" in message.lower()

    @pytest.mark.asyncio
    async def test_check_python_parser_available(self):
        """Test Python parser check when available."""
        cmd = HealthCommand()
        success, message = await cmd.check_python_parser()

        # Should be available in our test environment
        assert success is True
        assert "fallback" in message.lower()

    @pytest.mark.asyncio
    async def test_check_python_parser_not_available(self):
        """Test Python parser check when not available."""
        cmd = HealthCommand()

        with patch('src.memory.python_parser.get_parser', side_effect=ImportError("No tree-sitter")):
            success, message = await cmd.check_python_parser()
            assert success is False
            assert "Not available" in message


class TestStorageChecks:
    """Test storage backend checks."""

    @pytest.mark.asyncio
    async def test_check_storage_sqlite_exists(self):
        """Test SQLite storage check when database exists."""
        cmd = HealthCommand()

        with patch('src.config.get_config') as mock_config:
            config = MagicMock()
            config.storage_backend = "sqlite"
            config.sqlite_path_expanded = Path("/tmp/test.db")
            mock_config.return_value = config

            with patch.object(Path, 'exists', return_value=True):
                with patch.object(Path, 'stat') as mock_stat:
                    mock_stat.return_value.st_size = 1024 * 1024  # 1MB
                    success, backend, message = await cmd.check_storage_backend()

                    assert success is True
                    assert backend == "SQLite"
                    assert "MB" in message

    @pytest.mark.asyncio
    async def test_check_storage_sqlite_not_exists(self):
        """Test SQLite storage check when database doesn't exist."""
        cmd = HealthCommand()

        with patch('src.config.get_config') as mock_config:
            config = MagicMock()
            config.storage_backend = "sqlite"
            config.sqlite_path_expanded = Path("/tmp/test.db")
            mock_config.return_value = config

            with patch.object(Path, 'exists', return_value=False):
                success, backend, message = await cmd.check_storage_backend()

                assert success is True
                assert backend == "SQLite"
                assert "not yet created" in message

    @pytest.mark.asyncio
    async def test_check_storage_qdrant_running(self):
        """Test Qdrant storage check when running."""
        cmd = HealthCommand()

        with patch('src.config.get_config') as mock_config:
            config = MagicMock()
            config.storage_backend = "qdrant"
            config.qdrant_url = "http://localhost:6333"
            mock_config.return_value = config

            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = '{"status":"ok"}'

            with patch('subprocess.run', return_value=mock_result):
                success, backend, message = await cmd.check_storage_backend()

                assert success is True
                assert backend == "Qdrant"
                assert "localhost:6333" in message

    @pytest.mark.asyncio
    async def test_check_storage_qdrant_not_running(self):
        """Test Qdrant storage check when not running."""
        cmd = HealthCommand()

        with patch('src.config.get_config') as mock_config:
            config = MagicMock()
            config.storage_backend = "qdrant"
            config.qdrant_url = "http://localhost:6333"
            mock_config.return_value = config

            mock_result = MagicMock()
            mock_result.returncode = 1
            mock_result.stdout = ""

            with patch('subprocess.run', return_value=mock_result):
                success, backend, message = await cmd.check_storage_backend()

                assert success is False
                assert backend == "Qdrant"
                assert "Not reachable" in message


class TestEmbeddingChecks:
    """Test embedding model checks."""

    @pytest.mark.asyncio
    async def test_check_embedding_model_success(self):
        """Test embedding model check when successful."""
        cmd = HealthCommand()

        with patch('src.embeddings.generator.EmbeddingGenerator') as mock_gen:
            mock_instance = AsyncMock()
            mock_instance.generate = AsyncMock(return_value=[0.1] * 384)
            mock_gen.return_value = mock_instance

            with patch('src.config.get_config') as mock_config:
                config = MagicMock()
                config.embedding_model = "all-MiniLM-L6-v2"
                mock_config.return_value = config

                success, message = await cmd.check_embedding_model()

                assert success is True
                assert "all-MiniLM-L6-v2" in message
                assert "384" in message

    @pytest.mark.asyncio
    async def test_check_embedding_model_error(self):
        """Test embedding model check when error occurs."""
        cmd = HealthCommand()

        with patch('src.embeddings.generator.EmbeddingGenerator', side_effect=Exception("Model error")):
            success, message = await cmd.check_embedding_model()

            assert success is False
            assert "Error loading" in message

    @pytest.mark.asyncio
    async def test_check_embedding_cache_exists(self):
        """Test embedding cache check when cache exists."""
        cmd = HealthCommand()

        with patch('src.config.get_config') as mock_config:
            config = MagicMock()
            config.embedding_cache_path_expanded = Path("/tmp/cache.db")
            mock_config.return_value = config

            with patch.object(Path, 'exists', return_value=True):
                with patch.object(Path, 'stat') as mock_stat:
                    mock_stat.return_value.st_size = 2 * 1024 * 1024  # 2MB

                    with patch('src.embeddings.cache.EmbeddingCache') as mock_cache:
                        mock_instance = MagicMock()
                        mock_instance.get_stats.return_value = {
                            "hit_rate": 0.85,
                            "total_entries": 100
                        }
                        mock_cache.return_value = mock_instance

                        success, message = await cmd.check_embedding_cache()

                        assert success is True
                        assert "MB" in message
                        assert "85.0%" in message

    @pytest.mark.asyncio
    async def test_check_embedding_cache_not_exists(self):
        """Test embedding cache check when cache doesn't exist."""
        cmd = HealthCommand()

        with patch('src.config.get_config') as mock_config:
            config = MagicMock()
            config.embedding_cache_path_expanded = Path("/tmp/cache.db")
            mock_config.return_value = config

            with patch.object(Path, 'exists', return_value=False):
                success, message = await cmd.check_embedding_cache()

                assert success is True
                assert "Not yet created" in message


class TestRunChecks:
    """Test the full check run."""

    @pytest.mark.asyncio
    async def test_run_checks_all_pass(self):
        """Test run_checks when all checks pass."""
        cmd = HealthCommand()

        # Mock all checks to pass
        cmd.check_python_version = AsyncMock(return_value=(True, "3.13.6"))
        cmd.check_disk_space = AsyncMock(return_value=(True, "100 GB available"))
        cmd.check_memory = AsyncMock(return_value=(True, "16 GB"))
        cmd.check_rust_parser = AsyncMock(return_value=(True, "Available"))
        cmd.check_python_parser = AsyncMock(return_value=(True, "Available"))
        cmd.check_storage_backend = AsyncMock(return_value=(True, "SQLite", "OK"))
        cmd.check_embedding_model = AsyncMock(return_value=(True, "Model OK"))
        cmd.check_embedding_cache = AsyncMock(return_value=(True, "Cache OK"))

        await cmd.run_checks()

        assert len(cmd.errors) == 0
        assert len(cmd.warnings) == 0

    @pytest.mark.asyncio
    async def test_run_checks_with_errors(self):
        """Test run_checks when some checks fail."""
        cmd = HealthCommand()

        # Mock some checks to fail
        cmd.check_python_version = AsyncMock(return_value=(False, "Too old"))
        cmd.check_disk_space = AsyncMock(return_value=(True, "100 GB"))
        cmd.check_memory = AsyncMock(return_value=(True, "16 GB"))
        cmd.check_rust_parser = AsyncMock(return_value=(False, "Not available"))
        cmd.check_python_parser = AsyncMock(return_value=(False, "Not available"))
        cmd.check_storage_backend = AsyncMock(return_value=(False, "SQLite", "Error"))
        cmd.check_embedding_model = AsyncMock(return_value=(False, "Error"))
        cmd.check_embedding_cache = AsyncMock(return_value=(True, "OK"))

        await cmd.run_checks()

        assert len(cmd.errors) > 0
        assert "Python 3.8+ required" in cmd.errors
        assert "No parser available" in cmd.errors

    @pytest.mark.asyncio
    async def test_run_checks_with_warnings(self):
        """Test run_checks when some checks have warnings."""
        cmd = HealthCommand()

        # Mock checks with warnings
        cmd.check_python_version = AsyncMock(return_value=(True, "3.13.6"))
        cmd.check_disk_space = AsyncMock(return_value=(False, "0.3 GB (need 0.5 GB)"))
        cmd.check_memory = AsyncMock(return_value=(True, "16 GB"))
        cmd.check_rust_parser = AsyncMock(return_value=(False, "Not available"))
        cmd.check_python_parser = AsyncMock(return_value=(True, "Available"))
        cmd.check_storage_backend = AsyncMock(return_value=(True, "SQLite", "OK"))
        cmd.check_embedding_model = AsyncMock(return_value=(True, "Model OK"))
        cmd.check_embedding_cache = AsyncMock(return_value=(True, "Cache OK"))

        await cmd.run_checks()

        assert len(cmd.warnings) > 0
        assert len(cmd.recommendations) > 0


class TestPrintMethods:
    """Test print helper methods."""

    def test_print_section_with_rich(self):
        """Test print_section with rich available."""
        cmd = HealthCommand()
        # Should not raise
        cmd.print_section("Test Section")

    def test_print_section_without_rich(self):
        """Test print_section without rich."""
        with patch('src.cli.health_command.RICH_AVAILABLE', False):
            cmd = HealthCommand()
            cmd.console = None
            # Should not raise
            cmd.print_section("Test Section")

    def test_print_check_success(self):
        """Test print_check with success."""
        cmd = HealthCommand()
        # Should not raise
        cmd.print_check("Test", True, "Success message")

    def test_print_check_failure(self):
        """Test print_check with failure."""
        cmd = HealthCommand()
        # Should not raise
        cmd.print_check("Test", False, "Failure message")

    def test_print_warning(self):
        """Test print_warning."""
        cmd = HealthCommand()
        # Should not raise
        cmd.print_warning("Test", "Warning message")

    def test_print_summary_all_healthy(self):
        """Test print_summary when all healthy."""
        cmd = HealthCommand()
        cmd.errors = []
        cmd.warnings = []
        cmd.recommendations = []
        # Should not raise
        cmd.print_summary()

    def test_print_summary_with_errors(self):
        """Test print_summary with errors."""
        cmd = HealthCommand()
        cmd.errors = ["Error 1", "Error 2"]
        cmd.warnings = ["Warning 1"]
        cmd.recommendations = ["Rec 1"]
        # Should not raise
        cmd.print_summary()


class TestRunCommand:
    """Test the run command method."""

    @pytest.mark.asyncio
    async def test_run_command_success(self):
        """Test run command with successful checks."""
        cmd = HealthCommand()

        # Mock all checks to pass
        cmd.run_checks = AsyncMock()
        cmd.errors = []

        args = MagicMock()

        with pytest.raises(SystemExit) as exc_info:
            await cmd.run(args)

        assert exc_info.value.code == 0

    @pytest.mark.asyncio
    async def test_run_command_with_errors(self):
        """Test run command with failed checks."""
        cmd = HealthCommand()

        # Mock checks with errors
        cmd.run_checks = AsyncMock()
        cmd.errors = ["Error 1", "Error 2"]

        args = MagicMock()

        with pytest.raises(SystemExit) as exc_info:
            await cmd.run(args)

        assert exc_info.value.code == 1


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_check_indexed_projects_error(self):
        """Test check_indexed_projects with error."""
        cmd = HealthCommand()

        with patch('src.store.create_memory_store', side_effect=Exception("Store error")):
            success, message, projects = await cmd.check_indexed_projects()

            assert success is False
            assert "Error checking" in message
            assert projects == []

    @pytest.mark.asyncio
    async def test_check_indexed_projects_success(self):
        """Test check_indexed_projects success path."""
        cmd = HealthCommand()

        with patch('src.store.create_memory_store') as mock_create:
            mock_store = AsyncMock()
            mock_store.initialize = AsyncMock()
            mock_create.return_value = mock_store

            with patch('src.config.get_config') as mock_config:
                config = MagicMock()
                mock_config.return_value = config

                success, message, projects = await cmd.check_indexed_projects()

                assert success is True
                assert isinstance(projects, list)
