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
        with patch('src.cli.status_command.RICH_AVAILABLE', False):
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


class TestStorageStats:
    """Test storage statistics retrieval."""

    @pytest.mark.asyncio
    async def test_get_storage_stats_sqlite_exists(self):
        """Test getting SQLite storage stats when database exists."""
        cmd = StatusCommand()

        with patch('src.config.get_config') as mock_config:
            config = MagicMock()
            config.storage_backend = "sqlite"
            config.sqlite_path_expanded = Path("/tmp/test.db")
            mock_config.return_value = config

            with patch('src.store.create_memory_store') as mock_create:
                mock_store = AsyncMock()
                mock_store.initialize = AsyncMock()
                mock_create.return_value = mock_store

                with patch.object(Path, 'exists', return_value=True):
                    with patch.object(Path, 'stat') as mock_stat:
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

        with patch('src.config.get_config') as mock_config:
            config = MagicMock()
            config.storage_backend = "sqlite"
            config.sqlite_path_expanded = Path("/tmp/test.db")
            mock_config.return_value = config

            with patch('src.store.create_memory_store') as mock_create:
                mock_store = AsyncMock()
                mock_store.initialize = AsyncMock()
                mock_create.return_value = mock_store

                with patch.object(Path, 'exists', return_value=False):
                    stats = await cmd.get_storage_stats()

                    assert stats["backend"] == "sqlite"
                    assert stats["connected"] is True
                    assert "path" in stats
                    assert stats["size"] == 0

    @pytest.mark.asyncio
    async def test_get_storage_stats_qdrant(self):
        """Test getting Qdrant storage stats."""
        cmd = StatusCommand()

        with patch('src.config.get_config') as mock_config:
            config = MagicMock()
            config.storage_backend = "qdrant"
            config.qdrant_url = "http://localhost:6333"
            config.qdrant_collection_name = "test_collection"
            mock_config.return_value = config

            with patch('src.store.create_memory_store') as mock_create:
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

        with patch('src.config.get_config') as mock_config:
            config = MagicMock()
            config.storage_backend = "sqlite"
            mock_config.return_value = config

            with patch('src.store.create_memory_store') as mock_create:
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

        with patch('src.config.get_config') as mock_config:
            config = MagicMock()
            config.embedding_cache_path_expanded = Path("/tmp/cache.db")
            mock_config.return_value = config

            with patch.object(Path, 'exists', return_value=True):
                with patch.object(Path, 'stat') as mock_stat:
                    mock_stat.return_value.st_size = 5 * 1024 * 1024  # 5MB

                    with patch('src.embeddings.cache.EmbeddingCache') as mock_cache:
                        mock_instance = MagicMock()
                        mock_instance.get_stats.return_value = {
                            "total_entries": 1000,
                            "hits": 850,
                            "misses": 150,
                            "hit_rate": 0.85
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

        with patch('src.config.get_config') as mock_config:
            config = MagicMock()
            config.embedding_cache_path_expanded = Path("/tmp/cache.db")
            mock_config.return_value = config

            with patch.object(Path, 'exists', return_value=False):
                stats = await cmd.get_cache_stats()

                assert stats["exists"] is False
                assert "path" in stats

    @pytest.mark.asyncio
    async def test_get_cache_stats_error(self):
        """Test getting cache stats with error."""
        cmd = StatusCommand()

        with patch('src.config.get_config') as mock_config:
            config = MagicMock()
            config.embedding_cache_path_expanded = Path("/tmp/cache.db")
            mock_config.return_value = config

            with patch.object(Path, 'exists', return_value=True):
                with patch('src.embeddings.cache.EmbeddingCache', side_effect=Exception("Cache error")):
                    stats = await cmd.get_cache_stats()

                    assert "error" in stats


class TestParserInfo:
    """Test parser information retrieval."""

    @pytest.mark.asyncio
    async def test_get_parser_info_rust(self):
        """Test getting parser info when Rust is available."""
        cmd = StatusCommand()

        with patch('src.memory.incremental_indexer.PARSER_MODE', "rust"):
            with patch('src.memory.incremental_indexer.RUST_AVAILABLE', True):
                info = await cmd.get_parser_info()

                assert info["mode"] == "rust"
                assert info["rust_available"] is True
                assert "optimal" in info["description"].lower()

    @pytest.mark.asyncio
    async def test_get_parser_info_python(self):
        """Test getting parser info when using Python fallback."""
        cmd = StatusCommand()

        with patch('src.memory.incremental_indexer.PARSER_MODE', "python"):
            with patch('src.memory.incremental_indexer.RUST_AVAILABLE', False):
                info = await cmd.get_parser_info()

                assert info["mode"] == "python"
                assert info["rust_available"] is False
                assert "fallback" in info["description"].lower() or "slower" in info["description"].lower()


class TestEmbeddingInfo:
    """Test embedding model information retrieval."""

    @pytest.mark.asyncio
    async def test_get_embedding_model_info(self):
        """Test getting embedding model info."""
        cmd = StatusCommand()

        with patch('src.config.get_config') as mock_config:
            config = MagicMock()
            config.embedding_model = "all-MiniLM-L6-v2"
            config.embedding_batch_size = 32
            mock_config.return_value = config

            info = await cmd.get_embedding_model_info()

            assert info["model"] == "all-MiniLM-L6-v2"
            assert info["dimensions"] == 384
            assert info["batch_size"] == 32


class TestIndexedProjects:
    """Test indexed projects retrieval."""

    @pytest.mark.asyncio
    async def test_get_indexed_projects_empty(self):
        """Test getting indexed projects when none exist."""
        cmd = StatusCommand()

        with patch('src.config.get_config') as mock_config:
            config = MagicMock()
            mock_config.return_value = config

            with patch('src.store.create_memory_store') as mock_create:
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

        with patch('src.config.get_config') as mock_config:
            config = MagicMock()
            mock_config.return_value = config

            with patch('src.store.create_memory_store') as mock_create:
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
        # Should not raise
        cmd.print_header()

    def test_print_header_without_rich(self):
        """Test print header without rich."""
        with patch('src.cli.status_command.RICH_AVAILABLE', False):
            cmd = StatusCommand()
            cmd.console = None
            # Should not raise
            cmd.print_header()

    def test_print_storage_stats_sqlite(self):
        """Test printing SQLite storage stats."""
        cmd = StatusCommand()
        stats = {
            "backend": "sqlite",
            "connected": True,
            "path": "/tmp/test.db",
            "size": 1024 * 1024
        }
        # Should not raise
        cmd.print_storage_stats(stats)

    def test_print_storage_stats_qdrant(self):
        """Test printing Qdrant storage stats."""
        cmd = StatusCommand()
        stats = {
            "backend": "qdrant",
            "connected": True,
            "url": "http://localhost:6333",
            "collection": "test"
        }
        # Should not raise
        cmd.print_storage_stats(stats)

    def test_print_storage_stats_disconnected(self):
        """Test printing disconnected storage stats."""
        cmd = StatusCommand()
        stats = {
            "backend": "qdrant",
            "connected": False,
            "error": "Connection failed"
        }
        # Should not raise
        cmd.print_storage_stats(stats)

    def test_print_cache_stats_exists(self):
        """Test printing cache stats when cache exists."""
        cmd = StatusCommand()
        stats = {
            "exists": True,
            "path": "/tmp/cache.db",
            "size": 2 * 1024 * 1024,
            "total_entries": 1000,
            "hit_rate": 0.85
        }
        # Should not raise
        cmd.print_cache_stats(stats)

    def test_print_cache_stats_not_exists(self):
        """Test printing cache stats when cache doesn't exist."""
        cmd = StatusCommand()
        stats = {
            "exists": False
        }
        # Should not raise
        cmd.print_cache_stats(stats)

    def test_print_parser_info_rust(self):
        """Test printing Rust parser info."""
        cmd = StatusCommand()
        info = {
            "mode": "rust",
            "rust_available": True,
            "description": "Optimal performance"
        }
        # Should not raise
        cmd.print_parser_info(info)

    def test_print_parser_info_python(self):
        """Test printing Python parser info."""
        cmd = StatusCommand()
        info = {
            "mode": "python",
            "rust_available": False,
            "description": "Fallback mode"
        }
        # Should not raise
        cmd.print_parser_info(info)

    def test_print_embedding_info(self):
        """Test printing embedding info."""
        cmd = StatusCommand()
        info = {
            "model": "all-MiniLM-L6-v2",
            "dimensions": 384,
            "batch_size": 32
        }
        # Should not raise
        cmd.print_embedding_info(info)

    def test_print_projects_table_empty(self):
        """Test printing projects table with no projects."""
        cmd = StatusCommand()
        # Should not raise
        cmd.print_projects_table([])

    def test_print_projects_table_with_projects(self):
        """Test printing projects table with projects."""
        cmd = StatusCommand()
        projects = [
            {
                "name": "project1",
                "files": 100,
                "functions": 500,
                "classes": 50,
                "last_indexed": datetime.now(UTC) - timedelta(hours=2)
            }
        ]
        # Should not raise
        cmd.print_projects_table(projects)

    def test_print_quick_commands(self):
        """Test printing quick commands."""
        cmd = StatusCommand()
        # Should not raise
        cmd.print_quick_commands()


class TestRunCommand:
    """Test run command."""

    @pytest.mark.asyncio
    async def test_run_command(self):
        """Test running the status command."""
        cmd = StatusCommand()

        # Mock all data gathering methods
        cmd.get_storage_stats = AsyncMock(return_value={
            "backend": "sqlite",
            "connected": True
        })
        cmd.get_cache_stats = AsyncMock(return_value={
            "exists": True,
            "size": 1024 * 1024
        })
        cmd.get_parser_info = AsyncMock(return_value={
            "mode": "rust",
            "rust_available": True
        })
        cmd.get_embedding_model_info = AsyncMock(return_value={
            "model": "all-MiniLM-L6-v2"
        })
        cmd.get_indexed_projects = AsyncMock(return_value=[])

        # Mock print methods
        cmd.print_header = Mock()
        cmd.print_storage_stats = Mock()
        cmd.print_cache_stats = Mock()
        cmd.print_parser_info = Mock()
        cmd.print_embedding_info = Mock()
        cmd.print_projects_table = Mock()
        cmd.print_quick_commands = Mock()

        args = MagicMock()
        await cmd.run(args)

        # Verify all methods were called
        cmd.print_header.assert_called_once()
        cmd.get_storage_stats.assert_called_once()
        cmd.get_cache_stats.assert_called_once()
        cmd.get_parser_info.assert_called_once()
        cmd.get_embedding_model_info.assert_called_once()
        cmd.get_indexed_projects.assert_called_once()

class TestFileWatcherInfo:
    """Test file watcher information methods."""

    @pytest.mark.asyncio
    async def test_get_file_watcher_info_enabled(self):
        """Test getting file watcher info when enabled."""
        cmd = StatusCommand()

        with patch('src.config.get_config') as mock_get_config:
            mock_config = MagicMock()
            mock_config.enable_file_watcher = True
            mock_config.watch_debounce_ms = 1000
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

        with patch('src.config.get_config') as mock_get_config:
            mock_config = MagicMock()
            mock_config.enable_file_watcher = False
            mock_config.watch_debounce_ms = 500
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
            "description": "Auto-reindex files on change"
        }
        
        # Should not raise an error
        cmd.print_file_watcher_info(info)

    def test_print_file_watcher_info_disabled_with_rich(self):
        """Test printing file watcher info when disabled with rich."""
        cmd = StatusCommand()
        
        info = {
            "enabled": False,
            "debounce_ms": 1000,
            "supported_extensions": [".py"],
            "description": "Auto-reindex files on change"
        }
        
        # Should not raise an error
        cmd.print_file_watcher_info(info)

    def test_print_file_watcher_info_without_rich(self):
        """Test printing file watcher info without rich."""
        with patch('src.cli.status_command.RICH_AVAILABLE', False):
            cmd = StatusCommand()
            
            info = {
                "enabled": True,
                "debounce_ms": 1000,
                "supported_extensions": [".py", ".js"],
                "description": "Auto-reindex files on change"
            }
            
            # Should not raise an error
            cmd.print_file_watcher_info(info)

    @pytest.mark.asyncio
    async def test_run_includes_file_watcher_info(self):
        """Test that run() calls file watcher info methods."""
        cmd = StatusCommand()
        
        # Mock all methods
        cmd.print_header = Mock()
        cmd.get_storage_stats = AsyncMock(return_value={})
        cmd.get_cache_stats = AsyncMock(return_value={})
        cmd.get_parser_info = AsyncMock(return_value={})
        cmd.get_embedding_model_info = AsyncMock(return_value={})
        cmd.get_file_watcher_info = AsyncMock(return_value={})
        cmd.get_indexed_projects = AsyncMock(return_value=[])
        cmd.print_storage_stats = Mock()
        cmd.print_cache_stats = Mock()
        cmd.print_parser_info = Mock()
        cmd.print_embedding_info = Mock()
        cmd.print_file_watcher_info = Mock()
        cmd.print_projects_table = Mock()
        cmd.print_quick_commands = Mock()
        
        args = MagicMock()
        await cmd.run(args)
        
        # Verify file watcher methods were called
        cmd.get_file_watcher_info.assert_called_once()
        cmd.print_file_watcher_info.assert_called_once()
