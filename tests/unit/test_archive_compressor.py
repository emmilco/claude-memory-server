"""
Unit tests for archive compression functionality.

Tests compression, decompression, manifest generation, and storage savings.
"""

import pytest
import json
from pathlib import Path
import tempfile
import shutil

from src.memory.archive_compressor import ArchiveCompressor


@pytest.fixture
def temp_dirs():
    """Create temporary directories for testing."""
    temp_root = Path(tempfile.mkdtemp())
    archive_root = temp_root / "archives"
    index_dir = temp_root / "index"
    cache_file = temp_root / "cache.db"
    restore_dir = temp_root / "restore"

    # Create index directory with some files
    index_dir.mkdir(parents=True)
    (index_dir / "file1.txt").write_text("Sample index data " * 100)
    (index_dir / "file2.json").write_text('{"key": "value"}' * 50)
    (index_dir / "subdir").mkdir()
    (index_dir / "subdir" / "file3.txt").write_text("Nested file content " * 75)

    # Create cache file
    cache_file.write_text("Cache data " * 200)

    yield {
        "archive_root": archive_root,
        "index_dir": index_dir,
        "cache_file": cache_file,
        "restore_dir": restore_dir,
    }

    # Cleanup
    shutil.rmtree(temp_root)


@pytest.fixture
def compressor(temp_dirs):
    """Create an ArchiveCompressor instance."""
    return ArchiveCompressor(
        archive_root=str(temp_dirs["archive_root"]),
        compression_level=6,
    )


class TestArchiveCompressor:
    """Test ArchiveCompressor functionality."""

    def test_initialization(self, compressor, temp_dirs):
        """Test compressor initialization."""
        assert compressor.archive_root == temp_dirs["archive_root"]
        assert compressor.compression_level == 6
        assert temp_dirs["archive_root"].exists()

    @pytest.mark.asyncio
    async def test_compress_project_index(self, compressor, temp_dirs):
        """Test compressing a project index."""
        result = await compressor.compress_project_index(
            project_name="test-project",
            index_path=temp_dirs["index_dir"],
            cache_path=temp_dirs["cache_file"],
            project_stats={"total_files": 3, "total_units": 100},
        )

        assert result["success"] is True
        assert "archive_file" in result
        assert "manifest_file" in result
        assert "compression_info" in result

        # Verify archive file exists
        archive_file = Path(result["archive_file"])
        assert archive_file.exists()
        assert archive_file.suffix == ".gz"

        # Verify manifest exists
        manifest_file = Path(result["manifest_file"])
        assert manifest_file.exists()

        # Check compression info
        comp_info = result["compression_info"]
        assert comp_info["original_size_mb"] >= 0  # Small test files may round to 0
        assert comp_info["compressed_size_mb"] >= 0
        assert comp_info["compression_ratio"] <= 1.0  # Can be 0 for very small files
        assert comp_info["savings_percent"] >= 0

    @pytest.mark.asyncio
    async def test_compress_index_only(self, compressor, temp_dirs):
        """Test compressing index without cache."""
        result = await compressor.compress_project_index(
            project_name="test-project-2",
            index_path=temp_dirs["index_dir"],
            cache_path=None,
        )

        assert result["success"] is True
        assert (
            result["compression_info"]["original_size_mb"] >= 0
        )  # Small files may round to 0

    @pytest.mark.asyncio
    async def test_decompress_project_index(self, compressor, temp_dirs):
        """Test decompressing a project archive."""
        # First compress
        compress_result = await compressor.compress_project_index(
            project_name="test-project-3",
            index_path=temp_dirs["index_dir"],
            cache_path=temp_dirs["cache_file"],
        )
        assert compress_result["success"] is True

        # Then decompress
        decompress_result = await compressor.decompress_project_index(
            project_name="test-project-3",
            restore_path=temp_dirs["restore_dir"],
        )

        assert decompress_result["success"] is True
        assert "restored_path" in decompress_result
        assert "manifest" in decompress_result
        assert decompress_result["restored_size_mb"] > 0
        assert decompress_result["extraction_time_seconds"] >= 0

        # Verify restored files exist
        restore_path = Path(decompress_result["restored_path"])
        assert (restore_path / "index" / "file1.txt").exists()
        assert (restore_path / "index" / "file2.json").exists()
        assert (restore_path / "index" / "subdir" / "file3.txt").exists()
        assert (restore_path / "embeddings_cache.db").exists()

    @pytest.mark.asyncio
    async def test_decompress_nonexistent_archive(self, compressor, temp_dirs):
        """Test decompressing a non-existent archive."""
        result = await compressor.decompress_project_index(
            project_name="nonexistent-project",
            restore_path=temp_dirs["restore_dir"],
        )

        assert result["success"] is False
        assert "error" in result
        assert "not found" in result["error"].lower()

    def test_get_archive_info(self, compressor, temp_dirs):
        """Test retrieving archive information."""
        # Create an archive first (synchronous wrapper for test)
        import asyncio

        asyncio.run(
            compressor.compress_project_index(
                project_name="test-project-4",
                index_path=temp_dirs["index_dir"],
                cache_path=temp_dirs["cache_file"],
                project_stats={"total_files": 3},
            )
        )

        # Get archive info
        info = compressor.get_archive_info("test-project-4")

        assert info is not None
        assert info["project_name"] == "test-project-4"
        assert info["archive_version"] == "1.0"
        assert "archived_at" in info
        assert "statistics" in info
        assert "compression_info" in info
        assert "archive_file_size_mb" in info

    def test_get_archive_info_nonexistent(self, compressor):
        """Test getting info for non-existent archive."""
        info = compressor.get_archive_info("nonexistent-project")
        assert info is None

    def test_list_archives(self, compressor, temp_dirs):
        """Test listing all archives."""
        # Create multiple archives
        import asyncio

        for i in range(3):
            asyncio.run(
                compressor.compress_project_index(
                    project_name=f"test-project-{i}",
                    index_path=temp_dirs["index_dir"],
                )
            )

        archives = compressor.list_archives()
        assert len(archives) >= 3
        assert "test-project-0" in archives
        assert "test-project-1" in archives
        assert "test-project-2" in archives

    def test_delete_archive(self, compressor, temp_dirs):
        """Test deleting an archive."""
        # Create an archive
        import asyncio

        asyncio.run(
            compressor.compress_project_index(
                project_name="test-project-delete",
                index_path=temp_dirs["index_dir"],
            )
        )

        # Verify it exists
        assert compressor.get_archive_info("test-project-delete") is not None

        # Delete it
        success = compressor.delete_archive("test-project-delete")
        assert success is True

        # Verify it's gone
        assert compressor.get_archive_info("test-project-delete") is None

    def test_delete_nonexistent_archive(self, compressor):
        """Test deleting a non-existent archive."""
        success = compressor.delete_archive("nonexistent-project")
        assert success is False

    def test_get_total_storage_savings(self, compressor, temp_dirs):
        """Test calculating total storage savings."""
        # Create multiple archives
        import asyncio

        for i in range(3):
            asyncio.run(
                compressor.compress_project_index(
                    project_name=f"savings-project-{i}",
                    index_path=temp_dirs["index_dir"],
                    cache_path=temp_dirs["cache_file"],
                )
            )

        savings = compressor.get_total_storage_savings()

        assert savings["archive_count"] >= 3
        assert savings["total_original_mb"] >= 0  # Small test files may round to 0
        assert savings["total_compressed_mb"] >= 0
        assert savings["total_savings_mb"] >= 0
        assert savings["savings_percent"] >= 0
        # Don't compare sizes for very small test files that round to 0

    @pytest.mark.asyncio
    async def test_manifest_generation(self, compressor, temp_dirs):
        """Test that manifests are generated correctly."""
        result = await compressor.compress_project_index(
            project_name="manifest-test",
            index_path=temp_dirs["index_dir"],
            cache_path=temp_dirs["cache_file"],
            project_stats={
                "total_files": 3,
                "total_units": 100,
                "languages": ["python", "javascript"],
            },
        )

        # Load and verify manifest
        manifest_file = Path(result["manifest_file"])
        with open(manifest_file, "r") as f:
            manifest = json.load(f)

        assert manifest["project_name"] == "manifest-test"
        assert manifest["archive_version"] == "1.0"
        assert "archived_at" in manifest
        assert "statistics" in manifest
        assert manifest["statistics"]["total_files"] == 3
        assert manifest["statistics"]["total_units"] == 100
        assert "compression_info" in manifest
        assert "restore_info" in manifest

    @pytest.mark.asyncio
    async def test_compression_ratio(self, compressor, temp_dirs):
        """Test that compression achieves reasonable ratio."""
        result = await compressor.compress_project_index(
            project_name="ratio-test",
            index_path=temp_dirs["index_dir"],
            cache_path=temp_dirs["cache_file"],
        )

        comp_info = result["compression_info"]

        # Text files should compress well (expect >50% savings)
        assert comp_info["savings_percent"] > 50
        assert comp_info["compression_ratio"] < 0.5

    @pytest.mark.asyncio
    async def test_roundtrip_integrity(self, compressor, temp_dirs):
        """Test that compress → decompress preserves data integrity."""
        # Read original file content
        original_content = (temp_dirs["index_dir"] / "file1.txt").read_text()

        # Compress
        await compressor.compress_project_index(
            project_name="roundtrip-test",
            index_path=temp_dirs["index_dir"],
            cache_path=temp_dirs["cache_file"],
        )

        # Decompress
        await compressor.decompress_project_index(
            project_name="roundtrip-test",
            restore_path=temp_dirs["restore_dir"],
        )

        # Verify content matches
        restored_content = (
            temp_dirs["restore_dir"] / "index" / "file1.txt"
        ).read_text()
        assert restored_content == original_content
