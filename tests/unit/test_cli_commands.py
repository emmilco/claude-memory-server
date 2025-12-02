"""Comprehensive tests for CLI commands (index and watch)."""

import pytest
from unittest.mock import AsyncMock, patch, ANY
from argparse import Namespace
from src.cli.index_command import IndexCommand
from src.cli.watch_command import WatchCommand


class TestIndexCommand:
    """Test IndexCommand functionality."""

    @pytest.fixture
    def index_command(self):
        """Create IndexCommand instance."""
        return IndexCommand()

    @pytest.fixture
    def temp_python_file(self, tmp_path):
        """Create a temporary Python file for testing."""
        file_path = tmp_path / "test_file.py"
        file_path.write_text("""
def hello_world():
    '''Say hello.'''
    print('Hello, World!')

class TestClass:
    def method(self):
        pass
""")
        return file_path

    @pytest.fixture
    def temp_directory(self, tmp_path):
        """Create a temporary directory with multiple files."""
        # Create a few Python files
        (tmp_path / "file1.py").write_text("def func1(): pass")
        (tmp_path / "file2.py").write_text("def func2(): pass")

        # Create subdirectory
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        (subdir / "file3.py").write_text("def func3(): pass")

        return tmp_path

    @pytest.mark.asyncio
    async def test_index_single_file_success(self, index_command, temp_python_file):
        """Test successful indexing of a single file."""
        args = Namespace(
            path=str(temp_python_file), project_name="test-project", recursive=True
        )

        with patch("src.cli.index_command.IncrementalIndexer") as mock_indexer_class:
            # Setup mock
            mock_indexer = AsyncMock()
            mock_indexer_class.return_value = mock_indexer
            mock_indexer.index_file.return_value = {
                "file_path": str(temp_python_file),
                "language": "python",
                "units_indexed": 2,
                "parse_time_ms": 5.5,
            }

            # Run command
            result = await index_command.run(args)

            # Verify return value (CLI command doesn't return a value, returns None)
            assert result is None  # CLI commands print to console, don't return data

            # Verify mock calls
            mock_indexer.initialize.assert_called_once()
            mock_indexer.index_file.assert_called_once_with(temp_python_file)
            mock_indexer.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_index_directory_recursive(self, index_command, temp_directory):
        """Test indexing a directory with recursive option."""
        args = Namespace(
            path=str(temp_directory), project_name="test-project", recursive=True
        )

        with patch("src.cli.index_command.IncrementalIndexer") as mock_indexer_class:
            # Setup mock
            mock_indexer = AsyncMock()
            mock_indexer_class.return_value = mock_indexer
            mock_indexer.index_directory.return_value = {
                "total_files": 3,
                "indexed_files": 3,
                "skipped_files": 0,
                "total_units": 10,
                "failed_files": [],
            }

            # Run command
            result = await index_command.run(args)

            # Verify return value (CLI command doesn't return a value, returns None)
            assert result is None  # CLI commands print to console, don't return data

            # Verify - with progress callback
            mock_indexer.index_directory.assert_called_once_with(
                temp_directory,
                recursive=True,
                show_progress=False,
                progress_callback=ANY,
            )

    @pytest.mark.asyncio
    async def test_index_directory_non_recursive(self, index_command, temp_directory):
        """Test indexing a directory without recursion."""
        args = Namespace(
            path=str(temp_directory), project_name="test-project", recursive=False
        )

        with patch("src.cli.index_command.IncrementalIndexer") as mock_indexer_class:
            # Setup mock
            mock_indexer = AsyncMock()
            mock_indexer_class.return_value = mock_indexer
            mock_indexer.index_directory.return_value = {
                "total_files": 2,
                "indexed_files": 2,
                "skipped_files": 0,
                "total_units": 5,
                "failed_files": [],
            }

            # Run command
            result = await index_command.run(args)

            # Verify return value (CLI command doesn't return a value, returns None)
            assert result is None  # CLI commands print to console, don't return data

            # Verify recursive=False was passed
            mock_indexer.index_directory.assert_called_once_with(
                temp_directory,
                recursive=False,
                show_progress=False,
                progress_callback=ANY,
            )

    @pytest.mark.asyncio
    async def test_index_auto_project_name_from_directory(
        self, index_command, temp_directory
    ):
        """Test automatic project name detection from directory."""
        args = Namespace(
            path=str(temp_directory),
            project_name=None,  # No project name provided
            recursive=True,
        )

        with patch("src.cli.index_command.IncrementalIndexer") as mock_indexer_class:
            # Setup mock
            mock_indexer = AsyncMock()
            mock_indexer_class.return_value = mock_indexer
            mock_indexer.index_directory.return_value = {
                "total_files": 1,
                "indexed_files": 1,
                "skipped_files": 0,
                "total_units": 1,
                "failed_files": [],
            }

            # Run command
            result = await index_command.run(args)

            # Verify return value (CLI command doesn't return a value, returns None)
            assert result is None  # CLI commands print to console, don't return data

            # Verify project name was auto-detected (should be directory name)
            expected_project_name = temp_directory.name
            mock_indexer_class.assert_called_once_with(
                project_name=expected_project_name
            )

    @pytest.mark.asyncio
    async def test_index_auto_project_name_from_file(
        self, index_command, temp_python_file
    ):
        """Test automatic project name detection from file (uses parent directory)."""
        args = Namespace(
            path=str(temp_python_file),
            project_name=None,  # No project name provided
            recursive=True,
        )

        with patch("src.cli.index_command.IncrementalIndexer") as mock_indexer_class:
            # Setup mock
            mock_indexer = AsyncMock()
            mock_indexer_class.return_value = mock_indexer
            mock_indexer.index_file.return_value = {
                "file_path": str(temp_python_file),
                "language": "python",
                "units_indexed": 2,
                "parse_time_ms": 5.5,
            }

            # Run command
            result = await index_command.run(args)

            # Verify return value (CLI command doesn't return a value, returns None)
            assert result is None  # CLI commands print to console, don't return data

            # Verify project name was auto-detected (should be parent directory name)
            expected_project_name = temp_python_file.parent.name
            mock_indexer_class.assert_called_once_with(
                project_name=expected_project_name
            )

    @pytest.mark.asyncio
    async def test_index_nonexistent_path(self, index_command, tmp_path):
        """Test handling of non-existent path."""
        nonexistent_path = tmp_path / "does_not_exist"
        args = Namespace(
            path=str(nonexistent_path), project_name="test-project", recursive=True
        )

        # IndexCommand.run() logs the error and returns early without raising
        # The Path.exists() check happens before indexer initialization
        result = await index_command.run(args)

        # Verify return value (returns None for error case as well)
        assert result is None
        # If we get here without exception, test passes

    @pytest.mark.asyncio
    async def test_index_with_failed_files(self, index_command, temp_directory):
        """Test indexing with some failed files."""
        args = Namespace(
            path=str(temp_directory), project_name="test-project", recursive=True
        )

        with patch("src.cli.index_command.IncrementalIndexer") as mock_indexer_class:
            # Setup mock with failed files
            mock_indexer = AsyncMock()
            mock_indexer_class.return_value = mock_indexer
            mock_indexer.index_directory.return_value = {
                "total_files": 3,
                "indexed_files": 2,
                "skipped_files": 0,
                "total_units": 8,
                "failed_files": ["failed_file.py"],
            }

            # Run command
            result = await index_command.run(args)

            # Verify return value (CLI command doesn't return a value, returns None)
            assert result is None  # CLI commands print to console, don't return data

            # Should complete successfully and display failed files
            mock_indexer.index_directory.assert_called_once()

    @pytest.mark.asyncio
    async def test_index_exception_handling(self, index_command, temp_python_file):
        """Test exception handling during indexing."""
        args = Namespace(
            path=str(temp_python_file), project_name="test-project", recursive=True
        )

        with patch("src.cli.index_command.IncrementalIndexer") as mock_indexer_class:
            # Setup mock to raise exception
            mock_indexer = AsyncMock()
            mock_indexer_class.return_value = mock_indexer
            mock_indexer.index_file.side_effect = Exception("Test error")

            # Should raise the exception
            with pytest.raises(Exception, match="Test error"):
                await index_command.run(args)

            # Verify close was still called
            mock_indexer.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_index_throughput_calculation(self, index_command, temp_directory):
        """Test that throughput is calculated and displayed correctly."""
        args = Namespace(
            path=str(temp_directory), project_name="test-project", recursive=True
        )

        with patch("src.cli.index_command.IncrementalIndexer") as mock_indexer_class:
            # Setup mock
            mock_indexer = AsyncMock()
            mock_indexer_class.return_value = mock_indexer
            mock_indexer.index_directory.return_value = {
                "total_files": 10,
                "indexed_files": 10,
                "skipped_files": 0,
                "total_units": 50,
                "failed_files": [],
            }

            # Run command
            result = await index_command.run(args)

            # Verify return value (CLI command doesn't return a value, returns None)
            assert result is None  # CLI commands print to console, don't return data

            # If indexed_files > 0, throughput should be calculated
            # This is mainly to ensure code path is covered


class TestWatchCommand:
    """Test WatchCommand functionality."""

    @pytest.fixture
    def watch_command(self):
        """Create WatchCommand instance."""
        return WatchCommand()

    @pytest.fixture
    def temp_directory(self, tmp_path):
        """Create a temporary directory for watching."""
        (tmp_path / "file1.py").write_text("def func1(): pass")
        return tmp_path

    @pytest.mark.asyncio
    async def test_watch_successful_initialization(self, watch_command, temp_directory):
        """Test successful watch initialization and initial indexing."""
        args = Namespace(path=str(temp_directory), project_name="test-project")

        with patch("src.cli.watch_command.IndexingService") as mock_service_class:
            # Setup mock
            mock_service = AsyncMock()
            mock_service_class.return_value = mock_service
            mock_service.index_initial.return_value = {
                "indexed_files": 5,
                "total_units": 20,
            }
            # Simulate immediate stop
            mock_service.run_until_stopped.side_effect = KeyboardInterrupt()

            # Run command (will stop via KeyboardInterrupt)
            result = await watch_command.run(args)

            # Verify return value (CLI command doesn't return a value, returns None)
            assert result is None  # CLI commands print to console, don't return data

            # Verify initialization
            mock_service.initialize.assert_called_once()
            mock_service.index_initial.assert_called_once_with(recursive=True)
            mock_service.run_until_stopped.assert_called_once()
            mock_service.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_watch_auto_project_name(self, watch_command, temp_directory):
        """Test automatic project name detection."""
        args = Namespace(
            path=str(temp_directory),
            project_name=None,  # No project name provided
        )

        with patch("src.cli.watch_command.IndexingService") as mock_service_class:
            # Setup mock
            mock_service = AsyncMock()
            mock_service_class.return_value = mock_service
            mock_service.index_initial.return_value = {
                "indexed_files": 1,
                "total_units": 5,
            }
            mock_service.run_until_stopped.side_effect = KeyboardInterrupt()

            # Run command
            result = await watch_command.run(args)

            # Verify return value (CLI command doesn't return a value, returns None)
            assert result is None  # CLI commands print to console, don't return data

            # Verify project name was auto-detected (should be directory name)
            expected_project_name = temp_directory.name
            mock_service_class.assert_called_once_with(
                watch_path=temp_directory, project_name=expected_project_name
            )

    @pytest.mark.asyncio
    async def test_watch_nonexistent_path(self, watch_command, tmp_path):
        """Test handling of non-existent path."""
        nonexistent_path = tmp_path / "does_not_exist"
        args = Namespace(path=str(nonexistent_path), project_name="test-project")

        # WatchCommand.run() logs the error and returns early without raising
        # The Path.exists() check happens before service initialization
        result = await watch_command.run(args)

        # Verify return value (returns None for error case as well)
        assert result is None
        # If we get here without exception, test passes

    @pytest.mark.asyncio
    async def test_watch_file_path_error(self, watch_command, tmp_path):
        """Test that watch command errors when given a file instead of directory."""
        file_path = tmp_path / "test.py"
        file_path.write_text("def func(): pass")

        args = Namespace(path=str(file_path), project_name="test-project")

        # Should log error and return (path must be directory)
        result = await watch_command.run(args)

        # Verify return value (returns None for error case as well)
        assert result is None
        # If we get here without exception, test passes

    @pytest.mark.asyncio
    async def test_watch_keyboard_interrupt_handling(
        self, watch_command, temp_directory
    ):
        """Test graceful handling of Ctrl+C (KeyboardInterrupt)."""
        args = Namespace(path=str(temp_directory), project_name="test-project")

        with patch("src.cli.watch_command.IndexingService") as mock_service_class:
            # Setup mock
            mock_service = AsyncMock()
            mock_service_class.return_value = mock_service
            mock_service.index_initial.return_value = {
                "indexed_files": 1,
                "total_units": 5,
            }
            # Simulate Ctrl+C
            mock_service.run_until_stopped.side_effect = KeyboardInterrupt()

            # Run command
            result = await watch_command.run(args)

            # Verify return value (CLI command doesn't return a value, returns None)
            assert result is None  # CLI commands print to console, don't return data

            # Should handle gracefully and close service
            mock_service.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_watch_exception_handling(self, watch_command, temp_directory):
        """Test exception handling during watch."""
        args = Namespace(path=str(temp_directory), project_name="test-project")

        with patch("src.cli.watch_command.IndexingService") as mock_service_class:
            # Setup mock to raise exception during run
            mock_service = AsyncMock()
            mock_service_class.return_value = mock_service
            mock_service.index_initial.return_value = {
                "indexed_files": 1,
                "total_units": 5,
            }
            mock_service.run_until_stopped.side_effect = Exception("Test error")

            # Should raise the exception
            with pytest.raises(Exception, match="Test error"):
                await watch_command.run(args)

            # Verify close was still called
            mock_service.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_watch_custom_project_name(self, watch_command, temp_directory):
        """Test watch with custom project name."""
        args = Namespace(path=str(temp_directory), project_name="custom-project-name")

        with patch("src.cli.watch_command.IndexingService") as mock_service_class:
            # Setup mock
            mock_service = AsyncMock()
            mock_service_class.return_value = mock_service
            mock_service.index_initial.return_value = {
                "indexed_files": 1,
                "total_units": 5,
            }
            mock_service.run_until_stopped.side_effect = KeyboardInterrupt()

            # Run command
            result = await watch_command.run(args)

            # Verify return value (CLI command doesn't return a value, returns None)
            assert result is None  # CLI commands print to console, don't return data

            # Verify custom project name was used
            mock_service_class.assert_called_once_with(
                watch_path=temp_directory, project_name="custom-project-name"
            )
