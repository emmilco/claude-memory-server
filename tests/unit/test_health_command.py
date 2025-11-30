"""Tests for health check command."""

import pytest
import sys
import subprocess
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from src.cli.health_command import HealthCommand
from conftest import mock_embedding


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
    async def test_check_python_parser_removed(self):
        """Test Python parser check - always returns removed (Rust required)."""
        cmd = HealthCommand()
        success, message = await cmd.check_python_parser()

        # Python parser was removed - Rust parser is now required
        assert success is False
        assert "Removed" in message or "Rust" in message


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
            mock_result.stdout = '{"version":"v1.0.0"}'

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
            mock_instance.generate = AsyncMock(return_value=mock_embedding(value=0.1))
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


@pytest.mark.slow
class TestRunChecks:
    """Test the full check run.

    Marked slow because run_checks performs comprehensive system checks
    that take 5-7 seconds each due to the mocking overhead.
    """

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

        # Verify actual behavior - no errors/warnings accumulated
        assert len(cmd.errors) == 0
        assert len(cmd.warnings) == 0
        # Verify checks were actually called
        cmd.check_python_version.assert_called_once()
        cmd.check_storage_backend.assert_called_once()

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

        # Verify actual behavior - errors accumulated
        assert len(cmd.errors) > 0
        assert "Python 3.8+ required" in cmd.errors
        assert "No parser available" in cmd.errors
        # Verify critical checks were called
        cmd.check_python_version.assert_called_once()
        cmd.check_rust_parser.assert_called_once()
        cmd.check_python_parser.assert_called_once()
        cmd.check_storage_backend.assert_called_once()

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

        # Verify actual behavior - warnings and recommendations accumulated
        assert len(cmd.warnings) > 0
        assert len(cmd.recommendations) > 0
        # Verify warning content is meaningful
        assert any("disk" in w.lower() or "space" in w.lower() for w in cmd.warnings)


class TestPrintMethods:
    """Test print helper methods."""

    def test_print_section_with_rich(self):
        """Test print_section with rich available."""
        cmd = HealthCommand()
        with patch.object(cmd, 'console') as mock_console:
            cmd.print_section("Test Section")
            # Verify console.print was called to display section
            assert mock_console.print.called
            # Verify section title was included in output
            call_args = str(mock_console.print.call_args)
            assert "Test Section" in call_args

    def test_print_section_without_rich(self):
        """Test print_section without rich."""
        with patch('src.cli.health_command.RICH_AVAILABLE', False):
            cmd = HealthCommand()
            cmd.console = None
            # Mock print to verify fallback behavior
            with patch('builtins.print') as mock_print:
                cmd.print_section("Test Section")
                # Verify print fallback was used
                assert mock_print.called
                # Verify section title was printed
                call_args = str(mock_print.call_args_list)
                assert "Test Section" in call_args

    def test_print_check_success(self):
        """Test print_check with success."""
        cmd = HealthCommand()
        with patch.object(cmd, 'console') as mock_console:
            cmd.print_check("Test", True, "Success message")
            # Verify console.print was called
            assert mock_console.print.called
            # Verify success indicator and message were displayed
            call_args = str(mock_console.print.call_args)
            assert "Success message" in call_args

    def test_print_check_failure(self):
        """Test print_check with failure."""
        cmd = HealthCommand()
        with patch.object(cmd, 'console') as mock_console:
            cmd.print_check("Test", False, "Failure message")
            # Verify console.print was called
            assert mock_console.print.called
            # Verify failure indicator and message were displayed
            call_args = str(mock_console.print.call_args)
            assert "Failure message" in call_args

    def test_print_warning(self):
        """Test print_warning."""
        cmd = HealthCommand()
        with patch.object(cmd, 'console') as mock_console:
            cmd.print_warning("Test", "Warning message")
            # Verify console.print was called
            assert mock_console.print.called
            # Verify warning message was displayed
            call_args = str(mock_console.print.call_args)
            assert "Warning message" in call_args

    def test_print_summary_all_healthy(self):
        """Test print_summary when all healthy."""
        cmd = HealthCommand()
        cmd.errors = []
        cmd.warnings = []
        cmd.recommendations = []
        with patch.object(cmd, 'console') as mock_console:
            cmd.print_summary()
            # Verify console.print was called to display summary
            assert mock_console.print.called
            # Verify healthy status message was shown
            call_args = str(mock_console.print.call_args_list)
            # Should contain success/healthy indicator
            assert any(keyword in call_args.lower() for keyword in ['healthy', 'success', 'ready', 'ok'])

    def test_print_summary_with_errors(self):
        """Test print_summary with errors."""
        cmd = HealthCommand()
        cmd.errors = ["Error 1", "Error 2"]
        cmd.warnings = ["Warning 1"]
        cmd.recommendations = ["Rec 1"]
        with patch.object(cmd, 'console') as mock_console:
            cmd.print_summary()
            # Verify console.print was called to display summary
            assert mock_console.print.called
            # Verify errors and warnings were displayed
            call_args = str(mock_console.print.call_args_list)
            assert "Error 1" in call_args or "2" in call_args  # Error count or content
            # Should indicate problems found
            assert any(keyword in call_args.lower() for keyword in ['error', 'warning', 'issue', 'problem'])


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

        # Verify behavior - exits with success code when no errors
        assert exc_info.value.code == 0
        # Verify run_checks was actually called
        cmd.run_checks.assert_called_once()

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

        # Verify behavior - exits with error code when errors present
        assert exc_info.value.code == 1
        # Verify run_checks was actually called
        cmd.run_checks.assert_called_once()
        # Verify errors were captured
        assert len(cmd.errors) == 2


class TestPerformanceChecks:
    """Test performance metric checks."""

    @pytest.mark.asyncio
    async def test_check_cache_hit_rate_success(self):
        """Test cache hit rate check with good hit rate."""
        cmd = HealthCommand()

        with patch('src.embeddings.cache.EmbeddingCache') as mock_cache_cls:
            mock_cache = MagicMock()
            mock_cache.get_stats.return_value = {
                "total_queries": 100,
                "cache_hits": 85
            }
            mock_cache_cls.return_value = mock_cache

            with patch('src.config.get_config') as mock_config:
                config = MagicMock()
                mock_config.return_value = config

                success, message, hit_rate = await cmd.check_cache_hit_rate()

                # Verify actual behavior - success status, correct calculations
                assert success is True
                assert hit_rate == 85.0
                assert "85.0%" in message
                # Verify cache was properly initialized
                mock_cache_cls.assert_called_once_with(config)
                # Verify stats were retrieved
                mock_cache.get_stats.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_cache_hit_rate_low(self):
        """Test cache hit rate check with low hit rate."""
        cmd = HealthCommand()

        with patch('src.embeddings.cache.EmbeddingCache') as mock_cache_cls:
            mock_cache = MagicMock()
            mock_cache.get_stats.return_value = {
                "total_queries": 100,
                "cache_hits": 50
            }
            mock_cache_cls.return_value = mock_cache

            with patch('src.config.get_config') as mock_config:
                config = MagicMock()
                mock_config.return_value = config

                success, message, hit_rate = await cmd.check_cache_hit_rate()

                assert success is False
                assert hit_rate == 50.0
                assert "50.0%" in message
                assert "low" in message.lower()

    @pytest.mark.asyncio
    async def test_check_cache_hit_rate_no_queries(self):
        """Test cache hit rate check with no queries yet."""
        cmd = HealthCommand()

        with patch('src.embeddings.cache.EmbeddingCache') as mock_cache_cls:
            mock_cache = MagicMock()
            mock_cache.get_stats.return_value = {
                "total_queries": 0,
                "cache_hits": 0
            }
            mock_cache_cls.return_value = mock_cache

            with patch('src.config.get_config') as mock_config:
                config = MagicMock()
                mock_config.return_value = config

                success, message, hit_rate = await cmd.check_cache_hit_rate()

                assert success is True
                assert hit_rate is None
                assert "No queries yet" in message

    @pytest.mark.asyncio
    async def test_check_cache_hit_rate_error(self):
        """Test cache hit rate check with error."""
        cmd = HealthCommand()

        with patch('src.embeddings.cache.EmbeddingCache', side_effect=Exception("Cache error")):
            success, message, hit_rate = await cmd.check_cache_hit_rate()

            assert success is False
            assert hit_rate is None
            assert "Could not check" in message


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


class TestStaleProjectChecks:
    """Test stale project detection."""

    @pytest.mark.asyncio
    async def test_check_stale_projects_all_current(self):
        """Test stale projects check when all projects are current."""
        cmd = HealthCommand()

        with patch('src.store.create_memory_store') as mock_create:
            mock_store = AsyncMock()
            mock_store.initialize = AsyncMock()
            mock_store.get_all_projects = AsyncMock(return_value=["project1", "project2"])

            from datetime import datetime, UTC
            recent_date = datetime.now(UTC).isoformat()

            mock_store.get_project_stats = AsyncMock(return_value={
                "last_updated": recent_date
            })
            mock_store.close = AsyncMock()
            mock_create.return_value = mock_store

            with patch('src.config.get_config') as mock_config:
                config = MagicMock()
                mock_config.return_value = config

                success, message, stale = await cmd.check_stale_projects()

                assert success is True
                assert "All projects current" in message
                assert stale == []

    @pytest.mark.asyncio
    async def test_check_stale_projects_has_stale(self):
        """Test stale projects check when there are stale projects."""
        cmd = HealthCommand()

        with patch('src.store.create_memory_store') as mock_create:
            mock_store = AsyncMock()
            mock_store.initialize = AsyncMock()
            mock_store.get_all_projects = AsyncMock(return_value=["old_project"])

            from datetime import datetime, timedelta, UTC
            old_date = (datetime.now(UTC) - timedelta(days=45)).isoformat()

            mock_store.get_project_stats = AsyncMock(return_value={
                "last_updated": old_date
            })
            mock_store.close = AsyncMock()
            mock_create.return_value = mock_store

            with patch('src.config.get_config') as mock_config:
                config = MagicMock()
                mock_config.return_value = config

                success, message, stale = await cmd.check_stale_projects()

                assert success is False
                assert "30+ days" in message
                assert len(stale) == 1
                assert stale[0]["name"] == "old_project"
                assert stale[0]["days_old"] >= 45

    @pytest.mark.asyncio
    async def test_check_stale_projects_error(self):
        """Test stale projects check with error."""
        cmd = HealthCommand()

        with patch('src.store.create_memory_store', side_effect=Exception("Store error")):
            success, message, stale = await cmd.check_stale_projects()

            assert success is False
            assert "Could not check" in message
            assert stale == []


class TestTokenSavingsEstimation:
    """Test token savings estimation."""

    @pytest.mark.asyncio
    async def test_estimate_token_savings_no_hits(self):
        """Test token savings estimation with no cache hits."""
        cmd = HealthCommand()

        with patch('src.embeddings.cache.EmbeddingCache') as mock_cache_cls:
            mock_cache = MagicMock()
            mock_cache.get_stats.return_value = {
                "cache_hits": 0
            }
            mock_cache_cls.return_value = mock_cache

            with patch('src.config.get_config') as mock_config:
                config = MagicMock()
                mock_config.return_value = config

                success, message, tokens = await cmd.estimate_token_savings()

                assert success is True
                assert "No cache hits yet" in message
                assert tokens == 0

    @pytest.mark.asyncio
    async def test_estimate_token_savings_small(self):
        """Test token savings estimation with small number of hits."""
        cmd = HealthCommand()

        with patch('src.embeddings.cache.EmbeddingCache') as mock_cache_cls:
            mock_cache = MagicMock()
            mock_cache.get_stats.return_value = {
                "cache_hits": 5
            }
            mock_cache_cls.return_value = mock_cache

            with patch('src.config.get_config') as mock_config:
                config = MagicMock()
                mock_config.return_value = config

                success, message, tokens = await cmd.estimate_token_savings()

                assert success is True
                assert "500 tokens saved" in message
                assert tokens == 500

    @pytest.mark.asyncio
    async def test_estimate_token_savings_thousands(self):
        """Test token savings estimation with thousands of tokens."""
        cmd = HealthCommand()

        with patch('src.embeddings.cache.EmbeddingCache') as mock_cache_cls:
            mock_cache = MagicMock()
            mock_cache.get_stats.return_value = {
                "cache_hits": 50
            }
            mock_cache_cls.return_value = mock_cache

            with patch('src.config.get_config') as mock_config:
                config = MagicMock()
                mock_config.return_value = config

                success, message, tokens = await cmd.estimate_token_savings()

                assert success is True
                assert "5.0K tokens saved" in message
                assert tokens == 5000

    @pytest.mark.asyncio
    async def test_estimate_token_savings_millions(self):
        """Test token savings estimation with millions of tokens."""
        cmd = HealthCommand()

        with patch('src.embeddings.cache.EmbeddingCache') as mock_cache_cls:
            mock_cache = MagicMock()
            mock_cache.get_stats.return_value = {
                "cache_hits": 50000
            }
            mock_cache_cls.return_value = mock_cache

            with patch('src.config.get_config') as mock_config:
                config = MagicMock()
                mock_config.return_value = config

                success, message, tokens = await cmd.estimate_token_savings()

                assert success is True
                assert "5.0M tokens saved" in message
                assert tokens == 5000000

    @pytest.mark.asyncio
    async def test_estimate_token_savings_error(self):
        """Test token savings estimation with error."""
        cmd = HealthCommand()

        with patch('src.embeddings.cache.EmbeddingCache', side_effect=Exception("Cache error")):
            success, message, tokens = await cmd.estimate_token_savings()

            assert success is False
            assert "Could not estimate" in message
            assert tokens is None


class TestQdrantLatencyChecks:
    """Test Qdrant latency monitoring."""

    @pytest.mark.asyncio
    async def test_check_qdrant_latency_excellent(self):
        """Test Qdrant latency check with excellent performance."""
        cmd = HealthCommand()

        with patch('src.store.create_memory_store') as mock_create:
            mock_store = AsyncMock()
            mock_store.initialize = AsyncMock()
            mock_store.client = MagicMock()
            mock_store.collection_name = "test_collection"
            mock_store.client.get_collection = MagicMock()
            mock_store.close = AsyncMock()
            mock_create.return_value = mock_store

            with patch('src.config.get_config') as mock_config:
                config = MagicMock()
                config.storage_backend = "qdrant"
                mock_config.return_value = config

                with patch('time.time', side_effect=[0, 0.010]):  # 10ms
                    success, message, latency = await cmd.check_qdrant_latency()

                    assert success is True
                    assert "excellent" in message.lower()
                    assert latency < 20

    @pytest.mark.asyncio
    async def test_check_qdrant_latency_warning(self):
        """Test Qdrant latency check with warning threshold."""
        cmd = HealthCommand()

        with patch('src.store.create_memory_store') as mock_create:
            mock_store = AsyncMock()
            mock_store.initialize = AsyncMock()
            mock_store.client = MagicMock()
            mock_store.collection_name = "test_collection"
            mock_store.client.get_collection = MagicMock()
            mock_store.close = AsyncMock()
            mock_create.return_value = mock_store

            with patch('src.config.get_config') as mock_config:
                config = MagicMock()
                config.storage_backend = "qdrant"
                mock_config.return_value = config

                with patch('time.time', side_effect=[0, 0.060]):  # 60ms
                    success, message, latency = await cmd.check_qdrant_latency()

                    assert success is False
                    assert "slow" in message.lower()
                    assert latency >= 50

    @pytest.mark.asyncio
    async def test_check_qdrant_latency_sqlite_backend(self):
        """Test Qdrant latency check when using SQLite."""
        cmd = HealthCommand()

        with patch('src.config.get_config') as mock_config:
            config = MagicMock()
            config.storage_backend = "sqlite"
            mock_config.return_value = config

            success, message, latency = await cmd.check_qdrant_latency()

            assert success is True
            assert "N/A" in message
            assert latency is None


@pytest.mark.slow
class TestEnhancedRunChecks:
    """Test enhanced run_checks with new features.

    Marked slow because run_checks performs comprehensive system checks.
    """

    @pytest.mark.asyncio
    async def test_run_checks_includes_token_savings(self):
        """Test that run_checks includes token savings check."""
        cmd = HealthCommand()

        # Mock all checks
        cmd.check_python_version = AsyncMock(return_value=(True, "3.13.6"))
        cmd.check_disk_space = AsyncMock(return_value=(True, "100 GB"))
        cmd.check_memory = AsyncMock(return_value=(True, "16 GB"))
        cmd.check_rust_parser = AsyncMock(return_value=(True, "Available"))
        cmd.check_python_parser = AsyncMock(return_value=(True, "Available"))
        cmd.check_storage_backend = AsyncMock(return_value=(True, "SQLite", "OK"))
        cmd.check_embedding_model = AsyncMock(return_value=(True, "Model OK"))
        cmd.check_embedding_cache = AsyncMock(return_value=(True, "Cache OK"))
        cmd.check_qdrant_latency = AsyncMock(return_value=(True, "10ms", 10.0))
        cmd.check_cache_hit_rate = AsyncMock(return_value=(True, "85%", 85.0))
        cmd.estimate_token_savings = AsyncMock(return_value=(True, "5.0K tokens", 5000))
        cmd.check_stale_projects = AsyncMock(return_value=(True, "All current", []))
        cmd.get_project_stats_summary = AsyncMock(return_value={
            "total_projects": 1,
            "total_memories": 100,
            "total_files": 50,
            "index_size_bytes": 1024 * 1024
        })

        await cmd.run_checks()

        # Verify token savings check was called
        cmd.estimate_token_savings.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_checks_low_cache_hit_adds_recommendation(self):
        """Test that low cache hit rate adds recommendations."""
        cmd = HealthCommand()

        # Mock all checks
        cmd.check_python_version = AsyncMock(return_value=(True, "3.13.6"))
        cmd.check_disk_space = AsyncMock(return_value=(True, "100 GB"))
        cmd.check_memory = AsyncMock(return_value=(True, "16 GB"))
        cmd.check_rust_parser = AsyncMock(return_value=(True, "Available"))
        cmd.check_python_parser = AsyncMock(return_value=(True, "Available"))
        cmd.check_storage_backend = AsyncMock(return_value=(True, "SQLite", "OK"))
        cmd.check_embedding_model = AsyncMock(return_value=(True, "Model OK"))
        cmd.check_embedding_cache = AsyncMock(return_value=(True, "Cache OK"))
        cmd.check_qdrant_latency = AsyncMock(return_value=(True, "10ms", 10.0))
        cmd.check_cache_hit_rate = AsyncMock(return_value=(False, "50% (low)", 50.0))
        cmd.estimate_token_savings = AsyncMock(return_value=(True, "1.0K tokens", 1000))
        cmd.check_stale_projects = AsyncMock(return_value=(True, "All current", []))
        cmd.get_project_stats_summary = AsyncMock(return_value={
            "total_projects": 1,
            "total_memories": 100,
            "total_files": 50,
            "index_size_bytes": 1024 * 1024
        })

        await cmd.run_checks()

        # Verify warning and recommendation were added
        assert any("cache hit rate" in w.lower() for w in cmd.warnings)
        assert any("re-indexing" in r.lower() for r in cmd.recommendations)
