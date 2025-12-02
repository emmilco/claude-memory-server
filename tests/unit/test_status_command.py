"""Tests for status command."""

import pytest
from pathlib import Path
from datetime import datetime, timedelta, UTC
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from src.cli.status_command import StatusCommand


class TestStatusCommandInitialization:
    """Test status command initialization."""

    def test_init_with_rich(self):
        """Test initialization when rich is available."""
        cmd = StatusCommand()
        assert cmd.console is not None

    def test_init_without_rich(self):
        """Test initialization when rich is not available."""
        with patch("src.cli.status_command.RICH_AVAILABLE", False):
            cmd = StatusCommand()
            assert cmd.console is None


class TestHelperMethods:
    """Test helper methods for formatting."""

    def test_format_size_bytes(self):
        """Test formatting bytes."""
        cmd = StatusCommand()
        assert "B" in cmd._format_size(500)

    def test_format_size_kb(self):
        """Test formatting kilobytes."""
        cmd = StatusCommand()
        result = cmd._format_size(2048)
        assert "KB" in result or "B" in result

    def test_format_size_mb(self):
        """Test formatting megabytes."""
        cmd = StatusCommand()
        result = cmd._format_size(5 * 1024 * 1024)
        assert "MB" in result

    def test_format_size_gb(self):
        """Test formatting gigabytes."""
        cmd = StatusCommand()
        result = cmd._format_size(3 * 1024 * 1024 * 1024)
        assert "GB" in result

    def test_format_time_ago_never(self):
        """Test formatting None datetime."""
        cmd = StatusCommand()
        result = cmd._format_time_ago(None)
        assert result == "Never"

    def test_format_time_ago_just_now(self):
        """Test formatting recent datetime."""
        cmd = StatusCommand()
        now = datetime.now(UTC)
        result = cmd._format_time_ago(now)
        assert result == "Just now"

    def test_format_time_ago_minutes(self):
        """Test formatting minutes ago."""
        cmd = StatusCommand()
        dt = datetime.now(UTC) - timedelta(minutes=5)
        result = cmd._format_time_ago(dt)
        assert "m ago" in result

    def test_format_time_ago_hours(self):
        """Test formatting hours ago."""
        cmd = StatusCommand()
        dt = datetime.now(UTC) - timedelta(hours=2)
        result = cmd._format_time_ago(dt)
        assert "h ago" in result

    def test_format_time_ago_days(self):
        """Test formatting days ago."""
        cmd = StatusCommand()
        dt = datetime.now(UTC) - timedelta(days=3)
        result = cmd._format_time_ago(dt)
        assert "d ago" in result

    def test_format_time_ago_naive_datetime(self):
        """Test formatting naive datetime."""
        cmd = StatusCommand()
        dt = datetime.now() - timedelta(minutes=5)
        result = cmd._format_time_ago(dt)
        assert "m ago" in result or "Just now" in result

    def test_format_time_ago_future(self):
        """Test formatting future datetime (clock skew)."""
        cmd = StatusCommand()
        dt = datetime.now(UTC) + timedelta(hours=1)
        result = cmd._format_time_ago(dt)
        assert result == "In the future"


class TestStorageStats:
    """Test storage statistics retrieval."""

    @pytest.mark.asyncio
    async def test_get_storage_stats_sqlite_exists(self):
        """Test getting SQLite storage stats when database exists."""
        cmd = StatusCommand()

        with patch("src.config.get_config") as mock_config:
            config = MagicMock()
            config.storage_backend = "sqlite"
            config.sqlite_path_expanded = Path("/tmp/test.db")
            mock_config.return_value = config

            with patch("src.store.create_memory_store") as mock_create:
                mock_store = AsyncMock()
                mock_store.initialize = AsyncMock()
                mock_create.return_value = mock_store

                with patch.object(Path, "exists", return_value=True):
                    with patch.object(Path, "stat") as mock_stat:
                        mock_stat.return_value.st_size = 2 * 1024 * 1024  # 2MB

                        stats = await cmd.get_storage_stats()

                        assert stats["backend"] == "sqlite"
                        assert stats["connected"] is True
                        assert "path" in stats
                        assert stats["size"] == 2 * 1024 * 1024

    @pytest.mark.asyncio
    async def test_get_storage_stats_sqlite_not_exists(self):
        """Test getting SQLite storage stats when database doesn't exist."""
        cmd = StatusCommand()

        with patch("src.config.get_config") as mock_config:
            config = MagicMock()
            config.storage_backend = "sqlite"
            config.sqlite_path_expanded = Path("/tmp/test.db")
            mock_config.return_value = config

            with patch("src.store.create_memory_store") as mock_create:
                mock_store = AsyncMock()
                mock_store.initialize = AsyncMock()
                mock_create.return_value = mock_store

                with patch.object(Path, "exists", return_value=False):
                    stats = await cmd.get_storage_stats()

                    assert stats["backend"] == "sqlite"
                    assert stats["connected"] is True
                    assert "path" in stats
                    assert stats["size"] == 0

    @pytest.mark.asyncio
    async def test_get_storage_stats_qdrant(self):
        """Test getting Qdrant storage stats."""
        cmd = StatusCommand()

        with patch("src.config.get_config") as mock_config:
            config = MagicMock()
            config.storage_backend = "qdrant"
            config.qdrant_url = "http://localhost:6333"
            config.qdrant_collection_name = "test_collection"
            mock_config.return_value = config

            with patch("src.store.create_memory_store") as mock_create:
                mock_store = AsyncMock()
                mock_store.initialize = AsyncMock()
                mock_create.return_value = mock_store

                stats = await cmd.get_storage_stats()

                assert stats["backend"] == "qdrant"
                assert stats["connected"] is True
                assert stats["url"] == "http://localhost:6333"
                assert stats["collection"] == "test_collection"

    @pytest.mark.asyncio
    async def test_get_storage_stats_error(self):
        """Test getting storage stats with error."""
        cmd = StatusCommand()

        with patch("src.config.get_config") as mock_config:
            config = MagicMock()
            config.storage_backend = "sqlite"
            mock_config.return_value = config

            with patch("src.store.create_memory_store") as mock_create:
                mock_store = AsyncMock()
                mock_store.initialize = AsyncMock(side_effect=Exception("Store error"))
                mock_create.return_value = mock_store

                stats = await cmd.get_storage_stats()

                assert stats["backend"] == "sqlite"
                assert stats["connected"] is False
                assert "error" in stats


class TestCacheStats:
    """Test cache statistics retrieval."""

    @pytest.mark.asyncio
    async def test_get_cache_stats_exists(self):
        """Test getting cache stats when cache exists."""
        cmd = StatusCommand()

        with patch("src.config.get_config") as mock_config:
            config = MagicMock()
            config.embedding_cache_path_expanded = Path("/tmp/cache.db")
            mock_config.return_value = config

            with patch.object(Path, "exists", return_value=True):
                with patch.object(Path, "stat") as mock_stat:
                    mock_stat.return_value.st_size = 5 * 1024 * 1024  # 5MB

                    with patch("src.embeddings.cache.EmbeddingCache") as mock_cache:
                        mock_instance = MagicMock()
                        mock_instance.get_stats.return_value = {
                            "total_entries": 1000,
                            "hits": 850,
                            "misses": 150,
                            "hit_rate": 0.85,
                        }
                        mock_cache.return_value = mock_instance

                        stats = await cmd.get_cache_stats()

                        assert stats["exists"] is True
                        assert stats["size"] == 5 * 1024 * 1024
                        assert stats["total_entries"] == 1000
                        assert stats["hit_rate"] == 0.85

    @pytest.mark.asyncio
    async def test_get_cache_stats_not_exists(self):
        """Test getting cache stats when cache doesn't exist."""
        cmd = StatusCommand()

        with patch("src.config.get_config") as mock_config:
            config = MagicMock()
            config.embedding_cache_path_expanded = Path("/tmp/cache.db")
            mock_config.return_value = config

            with patch.object(Path, "exists", return_value=False):
                stats = await cmd.get_cache_stats()

                assert stats["exists"] is False
                assert "path" in stats

    @pytest.mark.asyncio
    async def test_get_cache_stats_error(self):
        """Test getting cache stats with error."""
        cmd = StatusCommand()

        with patch("src.config.get_config") as mock_config:
            config = MagicMock()
            config.embedding_cache_path_expanded = Path("/tmp/cache.db")
            mock_config.return_value = config

            with patch.object(Path, "exists", return_value=True):
                with patch(
                    "src.embeddings.cache.EmbeddingCache",
                    side_effect=Exception("Cache error"),
                ):
                    stats = await cmd.get_cache_stats()

                    assert "error" in stats


class TestParserInfo:
    """Test parser information retrieval."""

    @pytest.mark.asyncio
    async def test_get_parser_info_rust(self):
        """Test getting parser info when Rust is available."""
        cmd = StatusCommand()

        with patch("src.memory.incremental_indexer.RUST_AVAILABLE", True):
            info = await cmd.get_parser_info()

            assert info["mode"] == "rust"
            assert info["rust_available"] is True
            assert "optimal" in info["description"].lower()

    @pytest.mark.asyncio
    async def test_get_parser_info_unavailable(self):
        """Test getting parser info when Rust is not available."""
        cmd = StatusCommand()

        with patch("src.memory.incremental_indexer.RUST_AVAILABLE", False):
            info = await cmd.get_parser_info()

            assert info["mode"] == "unavailable"
            assert info["rust_available"] is False
            assert "required" in info["description"].lower()


class TestEmbeddingInfo:
    """Test embedding model information retrieval."""

    @pytest.mark.asyncio
    async def test_get_embedding_model_info(self):
        """Test getting embedding model info."""
        cmd = StatusCommand()

        with patch("src.config.get_config") as mock_config:
            config = MagicMock()
            config.embedding_model = "all-mpnet-base-v2"
            config.embedding_batch_size = 32
            mock_config.return_value = config

            info = await cmd.get_embedding_model_info()

            assert info["model"] == "all-mpnet-base-v2"
            assert info["dimensions"] == 768
            assert info["batch_size"] == 32


class TestIndexedProjects:
    """Test indexed projects retrieval."""

    @pytest.mark.asyncio
    async def test_get_indexed_projects_empty(self):
        """Test getting indexed projects when none exist."""
        cmd = StatusCommand()

        with patch("src.config.get_config") as mock_config:
            config = MagicMock()
            mock_config.return_value = config

            with patch("src.store.create_memory_store") as mock_create:
                mock_store = AsyncMock()
                mock_store.initialize = AsyncMock()
                mock_create.return_value = mock_store

                projects = await cmd.get_indexed_projects()

                assert isinstance(projects, list)
                assert len(projects) == 0

    @pytest.mark.asyncio
    async def test_get_indexed_projects_error(self):
        """Test getting indexed projects with error."""
        cmd = StatusCommand()

        with patch("src.config.get_config") as mock_config:
            config = MagicMock()
            mock_config.return_value = config

            with patch("src.store.create_memory_store") as mock_create:
                mock_store = AsyncMock()
                mock_store.initialize = AsyncMock(side_effect=Exception("Store error"))
                mock_create.return_value = mock_store

                projects = await cmd.get_indexed_projects()

                assert isinstance(projects, list)
                assert len(projects) == 0


class TestPrintMethods:
    """Test print methods."""

    def test_print_header_with_rich(self):
        """Test print header with rich."""
        cmd = StatusCommand()
        with patch.object(cmd.console, "print") as mock_print:
            cmd.print_header()
            # Verify console.print was called (at least twice: blank line + panel)
            assert mock_print.call_count >= 2
            # The method should create a Panel with header text
            # We just verify it was called, as Panel objects are complex to inspect

    def test_print_header_without_rich(self):
        """Test print header without rich."""
        with patch("src.cli.status_command.RICH_AVAILABLE", False):
            cmd = StatusCommand()
            cmd.console = None
            with patch("builtins.print") as mock_print:
                cmd.print_header()
                # Verify print was called
                assert mock_print.called
                # Verify header contains expected text
                call_args = str(mock_print.call_args_list)
                assert any(
                    keyword in call_args.lower()
                    for keyword in ["status", "memory", "server"]
                )

    def test_print_storage_stats_sqlite(self):
        """Test printing SQLite storage stats."""
        cmd = StatusCommand()
        stats = {
            "backend": "sqlite",
            "connected": True,
            "path": "/tmp/test.db",
            "size": 1024 * 1024,
        }
        with patch.object(cmd.console, "print") as mock_print:
            cmd.print_storage_stats(stats)
            # Verify console.print was called
            assert mock_print.called
            # Verify output contains storage info
            call_args = str(mock_print.call_args_list)
            assert "sqlite" in call_args.lower()
            assert "test.db" in call_args or "path" in call_args.lower()

    def test_print_storage_stats_qdrant(self):
        """Test printing Qdrant storage stats."""
        cmd = StatusCommand()
        stats = {
            "backend": "qdrant",
            "connected": True,
            "url": "http://localhost:6333",
            "collection": "test",
        }
        with patch.object(cmd.console, "print") as mock_print:
            cmd.print_storage_stats(stats)
            # Verify console.print was called
            assert mock_print.called
            # Verify output contains Qdrant info
            call_args = str(mock_print.call_args_list)
            assert "qdrant" in call_args.lower()
            assert any(
                keyword in call_args for keyword in ["localhost", "test", "6333"]
            )

    def test_print_storage_stats_disconnected(self):
        """Test printing disconnected storage stats."""
        cmd = StatusCommand()
        stats = {"backend": "qdrant", "connected": False, "error": "Connection failed"}
        with patch.object(cmd.console, "print") as mock_print:
            cmd.print_storage_stats(stats)
            # Verify console.print was called
            assert mock_print.called
            # Verify error message is shown
            call_args = str(mock_print.call_args_list)
            assert any(
                keyword in call_args.lower()
                for keyword in ["error", "failed", "disconnected"]
            )

    def test_print_cache_stats_exists(self):
        """Test printing cache stats when cache exists."""
        cmd = StatusCommand()
        stats = {
            "exists": True,
            "path": "/tmp/cache.db",
            "size": 2 * 1024 * 1024,
            "total_entries": 1000,
            "hit_rate": 0.85,
        }
        with patch.object(cmd.console, "print") as mock_print:
            cmd.print_cache_stats(stats)
            # Verify console.print was called
            assert mock_print.called
            # Verify cache info is displayed
            call_args = str(mock_print.call_args_list)
            assert any(
                keyword in call_args.lower() for keyword in ["cache", "hit", "entries"]
            )

    def test_print_cache_stats_not_exists(self):
        """Test printing cache stats when cache doesn't exist."""
        cmd = StatusCommand()
        stats = {"exists": False}
        with patch.object(cmd.console, "print") as mock_print:
            cmd.print_cache_stats(stats)
            # Verify console.print was called
            assert mock_print.called
            # Verify message indicates cache doesn't exist
            call_args = str(mock_print.call_args_list)
            assert any(
                keyword in call_args.lower()
                for keyword in ["not", "no cache", "disabled"]
            )

    def test_print_parser_info_rust(self):
        """Test printing Rust parser info."""
        cmd = StatusCommand()
        info = {
            "mode": "rust",
            "rust_available": True,
            "description": "Optimal performance",
        }
        with patch.object(cmd.console, "print") as mock_print:
            cmd.print_parser_info(info)
            # Verify console.print was called
            assert mock_print.called
            # Verify Rust parser info is displayed
            call_args = str(mock_print.call_args_list)
            assert "rust" in call_args.lower()
            assert any(
                keyword in call_args.lower() for keyword in ["optimal", "performance"]
            )

    def test_print_parser_info_python(self):
        """Test printing Python parser info."""
        cmd = StatusCommand()
        info = {
            "mode": "python",
            "rust_available": False,
            "description": "Fallback mode",
        }
        with patch.object(cmd.console, "print") as mock_print:
            cmd.print_parser_info(info)
            # Verify console.print was called
            assert mock_print.called
            # Verify Python parser info is displayed
            call_args = str(mock_print.call_args_list)
            assert "python" in call_args.lower()
            assert any(keyword in call_args.lower() for keyword in ["fallback", "mode"])

    def test_print_embedding_info(self):
        """Test printing embedding info."""
        cmd = StatusCommand()
        info = {"model": "all-mpnet-base-v2", "dimensions": 768, "batch_size": 32}
        with patch.object(cmd.console, "print") as mock_print:
            cmd.print_embedding_info(info)
            # Verify console.print was called
            assert mock_print.called
            # Verify embedding model info is displayed
            call_args = str(mock_print.call_args_list)
            assert any(keyword in call_args for keyword in ["MiniLM", "768", "32"])

    def test_print_projects_table_empty(self):
        """Test printing projects table with no projects."""
        cmd = StatusCommand()
        with patch.object(cmd.console, "print") as mock_print:
            cmd.print_projects_table([])
            # Verify console.print was called
            assert mock_print.called
            # Verify message indicates no projects
            call_args = str(mock_print.call_args_list)
            assert any(
                keyword in call_args.lower() for keyword in ["no", "empty", "project"]
            )

    def test_print_projects_table_with_projects(self):
        """Test printing projects table with projects."""
        cmd = StatusCommand()
        projects = [
            {
                "project_name": "project1",
                "total_memories": 1000,
                "num_files": 100,
                "num_functions": 500,
                "num_classes": 50,
                "last_indexed": datetime.now(UTC) - timedelta(hours=2),
            }
        ]
        with patch.object(cmd.console, "print") as mock_print:
            cmd.print_projects_table(projects)
            # Verify console.print was called (header + table + blank line)
            assert mock_print.call_count >= 2
            # The method creates a Table object - we verify it was called properly

    def test_print_quick_commands(self):
        """Test printing quick commands."""
        cmd = StatusCommand()
        with patch.object(cmd.console, "print") as mock_print:
            cmd.print_quick_commands()
            # Verify console.print was called
            assert mock_print.called
            # Verify commands are displayed
            call_args = str(mock_print.call_args_list)
            assert any(
                keyword in call_args.lower()
                for keyword in ["command", "index", "search"]
            )


class TestRunCommand:
    """Test run command."""

    @pytest.mark.asyncio
    async def test_run_command(self):
        """Test running the status command."""
        cmd = StatusCommand()

        # Mock all data gathering methods with realistic return values
        storage_stats = {
            "backend": "sqlite",
            "connected": True,
            "path": "/tmp/test.db",
            "size": 1024 * 1024,
        }
        cache_stats = {"exists": True, "size": 1024 * 1024, "total_entries": 100}
        parser_info = {
            "mode": "rust",
            "rust_available": True,
            "description": "Optimal performance",
        }
        embedding_info = {
            "model": "all-mpnet-base-v2",
            "dimensions": 768,
            "batch_size": 32,
        }
        file_watcher_info = {
            "enabled": True,
            "debounce_ms": 1000,
            "supported_extensions": [".py", ".js"],
            "description": "Auto-reindex files on change",
        }
        active_project = {"name": "test-project", "path": "/tmp/test-project"}
        projects = []

        cmd.get_storage_stats = AsyncMock(return_value=storage_stats)
        cmd.get_cache_stats = AsyncMock(return_value=cache_stats)
        cmd.get_parser_info = AsyncMock(return_value=parser_info)
        cmd.get_embedding_model_info = AsyncMock(return_value=embedding_info)
        cmd.get_file_watcher_info = AsyncMock(return_value=file_watcher_info)
        cmd.get_active_project = AsyncMock(return_value=active_project)
        cmd.get_indexed_projects = AsyncMock(return_value=projects)

        # Mock print methods
        cmd.print_header = Mock()
        cmd.print_degradation_warnings = Mock()
        cmd.print_storage_stats = Mock()
        cmd.print_cache_stats = Mock()
        cmd.print_parser_info = Mock()
        cmd.print_embedding_info = Mock()
        cmd.print_file_watcher_info = Mock()
        cmd.print_active_project = Mock()
        cmd.print_projects_table = Mock()
        cmd.print_quick_commands = Mock()

        args = MagicMock()
        await cmd.run(args)

        # Verify all data gathering methods were called
        cmd.get_storage_stats.assert_called_once()
        cmd.get_cache_stats.assert_called_once()
        cmd.get_parser_info.assert_called_once()
        cmd.get_embedding_model_info.assert_called_once()
        cmd.get_file_watcher_info.assert_called_once()
        cmd.get_active_project.assert_called_once()
        cmd.get_indexed_projects.assert_called_once()

        # Verify print methods were called with correct data
        cmd.print_header.assert_called_once()
        cmd.print_degradation_warnings.assert_called_once()
        cmd.print_storage_stats.assert_called_once_with(storage_stats)
        cmd.print_cache_stats.assert_called_once_with(cache_stats)
        cmd.print_parser_info.assert_called_once_with(parser_info)
        cmd.print_embedding_info.assert_called_once_with(embedding_info)
        cmd.print_file_watcher_info.assert_called_once_with(file_watcher_info)
        cmd.print_active_project.assert_called_once_with(active_project)
        cmd.print_projects_table.assert_called_once_with(projects)
        cmd.print_quick_commands.assert_called_once()


class TestFileWatcherInfo:
    """Test file watcher information methods."""

    @pytest.mark.asyncio
    async def test_get_file_watcher_info_enabled(self):
        """Test getting file watcher info when enabled."""
        cmd = StatusCommand()

        with patch("src.config.get_config") as mock_get_config:
            mock_config = MagicMock()
            mock_config.indexing.file_watcher = True
            mock_config.indexing.watch_debounce_ms = 1000
            mock_get_config.return_value = mock_config

            info = await cmd.get_file_watcher_info()

            assert info["enabled"] is True
            assert info["debounce_ms"] == 1000
            assert "supported_extensions" in info
            assert ".py" in info["supported_extensions"]
            assert ".js" in info["supported_extensions"]

    @pytest.mark.asyncio
    async def test_get_file_watcher_info_disabled(self):
        """Test getting file watcher info when disabled."""
        cmd = StatusCommand()

        with patch("src.config.get_config") as mock_get_config:
            mock_config = MagicMock()
            mock_config.indexing.file_watcher = False
            mock_config.indexing.watch_debounce_ms = 500
            mock_get_config.return_value = mock_config

            info = await cmd.get_file_watcher_info()

            assert info["enabled"] is False
            assert info["debounce_ms"] == 500

    def test_print_file_watcher_info_enabled_with_rich(self):
        """Test printing file watcher info when enabled with rich."""
        cmd = StatusCommand()

        info = {
            "enabled": True,
            "debounce_ms": 1000,
            "supported_extensions": [".py", ".js", ".ts"],
            "description": "Auto-reindex files on change",
        }

        with patch.object(cmd.console, "print") as mock_print:
            cmd.print_file_watcher_info(info)
            # Verify console.print was called
            assert mock_print.called
            # Verify file watcher info is displayed
            call_args = str(mock_print.call_args_list)
            assert any(
                keyword in call_args.lower()
                for keyword in ["watcher", "enabled", "auto"]
            )

    def test_print_file_watcher_info_disabled_with_rich(self):
        """Test printing file watcher info when disabled with rich."""
        cmd = StatusCommand()

        info = {
            "enabled": False,
            "debounce_ms": 1000,
            "supported_extensions": [".py"],
            "description": "Auto-reindex files on change",
        }

        with patch.object(cmd.console, "print") as mock_print:
            cmd.print_file_watcher_info(info)
            # Verify console.print was called
            assert mock_print.called
            # Verify disabled state is shown
            call_args = str(mock_print.call_args_list)
            assert any(
                keyword in call_args.lower()
                for keyword in ["watcher", "disabled", "off"]
            )

    def test_print_file_watcher_info_without_rich(self):
        """Test printing file watcher info without rich."""
        with patch("src.cli.status_command.RICH_AVAILABLE", False):
            cmd = StatusCommand()

            info = {
                "enabled": True,
                "debounce_ms": 1000,
                "supported_extensions": [".py", ".js"],
                "description": "Auto-reindex files on change",
            }

            with patch("builtins.print") as mock_print:
                cmd.print_file_watcher_info(info)
                # Verify print was called
                assert mock_print.called
                # Verify file watcher info is displayed
                call_args = str(mock_print.call_args_list)
                assert any(
                    keyword in call_args.lower()
                    for keyword in ["watcher", "enabled", "auto"]
                )

    @pytest.mark.asyncio
    async def test_run_includes_file_watcher_info(self):
        """Test that run() calls file watcher info methods."""
        cmd = StatusCommand()

        # Mock all methods with realistic return values
        file_watcher_info = {
            "enabled": True,
            "debounce_ms": 1000,
            "supported_extensions": [".py", ".js"],
            "description": "Auto-reindex files on change",
        }

        cmd.print_header = Mock()
        cmd.print_degradation_warnings = Mock()
        cmd.get_storage_stats = AsyncMock(
            return_value={"backend": "sqlite", "connected": True}
        )
        cmd.get_cache_stats = AsyncMock(return_value={"exists": False})
        cmd.get_parser_info = AsyncMock(return_value={"mode": "rust"})
        cmd.get_embedding_model_info = AsyncMock(
            return_value={"model": "all-mpnet-base-v2"}
        )
        cmd.get_file_watcher_info = AsyncMock(return_value=file_watcher_info)
        cmd.get_active_project = AsyncMock(return_value=None)
        cmd.get_indexed_projects = AsyncMock(return_value=[])
        cmd.print_storage_stats = Mock()
        cmd.print_cache_stats = Mock()
        cmd.print_parser_info = Mock()
        cmd.print_embedding_info = Mock()
        cmd.print_file_watcher_info = Mock()
        cmd.print_active_project = Mock()
        cmd.print_projects_table = Mock()
        cmd.print_quick_commands = Mock()

        args = MagicMock()
        await cmd.run(args)

        # Verify file watcher methods were called
        cmd.get_file_watcher_info.assert_called_once()
        cmd.print_file_watcher_info.assert_called_once_with(file_watcher_info)
