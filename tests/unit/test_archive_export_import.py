"""
Unit tests for archive export and import functionality.

Tests export, import, validation, conflict resolution, and roundtrip integrity.
"""

import pytest
import pytest_asyncio
import tempfile
import json
from pathlib import Path
from datetime import datetime, UTC

from src.memory.archive_exporter import ArchiveExporter
from src.memory.archive_importer import ArchiveImporter
from src.memory.archive_compressor import ArchiveCompressor


@pytest.fixture
def temp_dirs():
    """Create temporary directories for testing."""
    temp_root = Path(tempfile.mkdtemp())
    archive_root = temp_root / "archives"
    export_dir = temp_root / "exports"
    import_root = temp_root / "imports"
    index_dir = temp_root / "index"

    # Create index directory with test files
    index_dir.mkdir(parents=True)
    (index_dir / "file1.txt").write_text("Test content " * 100)
    (index_dir / "file2.json").write_text('{"key": "value"}' * 50)

    export_dir.mkdir(parents=True)

    yield {
        "archive_root": archive_root,
        "export_dir": export_dir,
        "import_root": import_root,
        "index_dir": index_dir,
    }


@pytest.fixture
def compressor(temp_dirs):
    """Create an ArchiveCompressor instance."""
    return ArchiveCompressor(
        archive_root=str(temp_dirs["archive_root"]),
        compression_level=6,
    )


@pytest.fixture
def importer_compressor(temp_dirs):
    """Create a separate ArchiveCompressor for import testing."""
    return ArchiveCompressor(
        archive_root=str(temp_dirs["import_root"]),
        compression_level=6,
    )


@pytest.fixture
def exporter(compressor):
    """Create an ArchiveExporter instance."""
    return ArchiveExporter(
        archive_compressor=compressor,
        compression_level=6,
    )


@pytest.fixture
def importer(importer_compressor):
    """Create an ArchiveImporter instance."""
    return ArchiveImporter(
        archive_compressor=importer_compressor,
    )


@pytest_asyncio.fixture
async def sample_archive(compressor, temp_dirs):
    """Create a sample archived project for testing."""
    project_name = "test-export-project"

    # Compress a sample project
    result = await compressor.compress_project_index(
        project_name=project_name,
        index_path=temp_dirs["index_dir"],
        project_stats={
            "total_files": 2,
            "total_semantic_units": 100,
            "total_memories": 10,
        },
    )

    assert result["success"] is True
    return project_name


class TestArchiveExporter:
    """Test ArchiveExporter functionality."""

    def test_initialization(self, exporter, compressor):
        """Test exporter initialization."""
        assert exporter.compressor == compressor
        assert exporter.compression_level == 6

    @pytest.mark.asyncio
    async def test_export_project_success(self, exporter, sample_archive, temp_dirs):
        """Test successful project export."""
        export_path = temp_dirs["export_dir"] / "export_test.tar.gz"

        result = await exporter.export_project_archive(
            project_name=sample_archive,
            output_path=export_path,
            include_readme=True,
        )

        assert result["success"] is True
        assert result["project_name"] == sample_archive
        assert Path(result["export_file"]).exists()
        assert result["export_size_mb"] >= 0  # Small test files may round to 0
        assert "manifest" in result

    @pytest.mark.asyncio
    async def test_export_project_default_path(self, exporter, sample_archive):
        """Test export with default output path."""
        result = await exporter.export_project_archive(
            project_name=sample_archive,
        )

        assert result["success"] is True
        export_file = Path(result["export_file"])
        assert export_file.exists()
        assert export_file.name.startswith(sample_archive)
        assert export_file.suffix == ".gz"

        # Cleanup
        export_file.unlink()

    @pytest.mark.asyncio
    async def test_export_nonexistent_project(self, exporter):
        """Test exporting a non-existent project."""
        result = await exporter.export_project_archive(
            project_name="nonexistent-project",
        )

        assert result["success"] is False
        assert "not found" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_export_without_readme(self, exporter, sample_archive, temp_dirs):
        """Test export without README."""
        export_path = temp_dirs["export_dir"] / "export_no_readme.tar.gz"

        result = await exporter.export_project_archive(
            project_name=sample_archive,
            output_path=export_path,
            include_readme=False,
        )

        assert result["success"] is True
        assert Path(result["export_file"]).exists()

    def test_list_exportable_projects(self, exporter):
        """Test listing exportable projects."""
        result = exporter.list_exportable_projects()

        assert result["success"] is True
        assert "exportable_projects" in result
        assert result["total_projects"] >= 0
        assert result["total_size_mb"] >= 0


class TestArchiveImporter:
    """Test ArchiveImporter functionality."""

    def test_initialization(self, importer, importer_compressor):
        """Test importer initialization."""
        assert importer.compressor == importer_compressor

    @pytest.mark.asyncio
    async def test_import_project_success(
        self, exporter, importer, sample_archive, temp_dirs
    ):
        """Test successful project import."""
        # First export
        export_path = temp_dirs["export_dir"] / "import_test.tar.gz"
        export_result = await exporter.export_project_archive(
            project_name=sample_archive,
            output_path=export_path,
        )
        assert export_result["success"] is True

        # Then import
        import_result = await importer.import_project_archive(
            archive_path=export_path,
        )

        assert import_result["success"] is True
        assert import_result["project_name"] == sample_archive
        assert import_result["import_size_mb"] >= 0  # Small test files may round to 0
        assert "manifest" in import_result

        # Verify import worked
        imported_info = importer.compressor.get_archive_info(sample_archive)
        assert imported_info is not None
        assert imported_info["project_name"] == sample_archive

    @pytest.mark.asyncio
    async def test_import_with_custom_name(
        self, exporter, importer, sample_archive, temp_dirs
    ):
        """Test import with custom project name."""
        # Export
        export_path = temp_dirs["export_dir"] / "custom_name_test.tar.gz"
        export_result = await exporter.export_project_archive(
            project_name=sample_archive,
            output_path=export_path,
        )
        assert export_result["success"] is True

        # Import with custom name
        custom_name = "imported-custom-name"
        import_result = await importer.import_project_archive(
            archive_path=export_path,
            project_name=custom_name,
        )

        assert import_result["success"] is True
        assert import_result["project_name"] == custom_name
        assert import_result["original_name"] == sample_archive

        # Verify
        imported_info = importer.compressor.get_archive_info(custom_name)
        assert imported_info is not None

    @pytest.mark.asyncio
    async def test_import_conflict_skip(
        self, exporter, importer, sample_archive, temp_dirs
    ):
        """Test import conflict with skip resolution."""
        # Export
        export_path = temp_dirs["export_dir"] / "conflict_skip_test.tar.gz"
        export_result = await exporter.export_project_archive(
            project_name=sample_archive,
            output_path=export_path,
        )
        assert export_result["success"] is True

        # First import
        import_result1 = await importer.import_project_archive(
            archive_path=export_path,
        )
        assert import_result1["success"] is True

        # Second import (conflict)
        import_result2 = await importer.import_project_archive(
            archive_path=export_path,
            conflict_resolution="skip",
        )

        assert import_result2["success"] is False
        assert "conflict" in import_result2
        assert import_result2["conflict"] is True

    @pytest.mark.asyncio
    async def test_import_conflict_overwrite(
        self, exporter, importer, sample_archive, temp_dirs
    ):
        """Test import conflict with overwrite resolution."""
        # Export
        export_path = temp_dirs["export_dir"] / "conflict_overwrite_test.tar.gz"
        export_result = await exporter.export_project_archive(
            project_name=sample_archive,
            output_path=export_path,
        )
        assert export_result["success"] is True

        # First import
        import_result1 = await importer.import_project_archive(
            archive_path=export_path,
        )
        assert import_result1["success"] is True

        # Second import with overwrite
        import_result2 = await importer.import_project_archive(
            archive_path=export_path,
            conflict_resolution="overwrite",
        )

        assert import_result2["success"] is True
        assert import_result2["conflict_resolution"] == "overwrite"

    @pytest.mark.asyncio
    async def test_import_nonexistent_file(self, importer):
        """Test importing a non-existent file."""
        result = await importer.import_project_archive(
            archive_path=Path("/nonexistent/archive.tar.gz"),
        )

        assert result["success"] is False
        assert "not found" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_validate_archive_file(
        self, exporter, importer, sample_archive, temp_dirs
    ):
        """Test archive validation without importing."""
        # Export
        export_path = temp_dirs["export_dir"] / "validate_test.tar.gz"
        export_result = await exporter.export_project_archive(
            project_name=sample_archive,
            output_path=export_path,
        )
        assert export_result["success"] is True

        # Validate
        validation_result = importer.validate_archive_file(export_path)

        assert validation_result["valid"] is True
        assert validation_result["project_name"] == sample_archive
        assert "manifest" in validation_result
        assert validation_result["archive_size_mb"] >= 0  # Small test files may round to 0

    def test_validate_nonexistent_archive(self, importer):
        """Test validating a non-existent archive."""
        result = importer.validate_archive_file(Path("/nonexistent/archive.tar.gz"))

        assert result["valid"] is False
        assert "not found" in result["error"].lower()


class TestRoundtripIntegrity:
    """Test export → import roundtrip integrity."""

    @pytest.mark.asyncio
    async def test_roundtrip_basic(
        self, exporter, importer, sample_archive, temp_dirs
    ):
        """Test basic export → import roundtrip."""
        # Export
        export_path = temp_dirs["export_dir"] / "roundtrip_basic.tar.gz"
        export_result = await exporter.export_project_archive(
            project_name=sample_archive,
            output_path=export_path,
        )
        assert export_result["success"] is True

        # Import
        import_result = await importer.import_project_archive(
            archive_path=export_path,
        )
        assert import_result["success"] is True

        # Verify imported archive exists
        imported_info = importer.compressor.get_archive_info(sample_archive)
        assert imported_info is not None
        assert imported_info["project_name"] == sample_archive

    @pytest.mark.asyncio
    async def test_roundtrip_manifest_preservation(
        self, exporter, importer, sample_archive, temp_dirs
    ):
        """Test that manifest is preserved through export → import."""
        # Get original manifest
        original_info = exporter.compressor.get_archive_info(sample_archive)
        original_manifest = original_info

        # Export
        export_path = temp_dirs["export_dir"] / "roundtrip_manifest.tar.gz"
        await exporter.export_project_archive(
            project_name=sample_archive,
            output_path=export_path,
        )

        # Import
        await importer.import_project_archive(
            archive_path=export_path,
        )

        # Get imported manifest
        imported_info = importer.compressor.get_archive_info(sample_archive)

        # Compare key fields
        assert imported_info["project_name"] == original_manifest["project_name"]
        assert imported_info["archive_version"] == original_manifest["archive_version"]
        assert (
            imported_info["statistics"] == original_manifest["statistics"]
        )
        assert (
            imported_info["compression_info"]["original_size_mb"]
            == original_manifest["compression_info"]["original_size_mb"]
        )

    @pytest.mark.asyncio
    async def test_roundtrip_with_rename(
        self, exporter, importer, sample_archive, temp_dirs
    ):
        """Test export → import with project rename."""
        # Export
        export_path = temp_dirs["export_dir"] / "roundtrip_rename.tar.gz"
        await exporter.export_project_archive(
            project_name=sample_archive,
            output_path=export_path,
        )

        # Import with different name
        new_name = "renamed-project"
        import_result = await importer.import_project_archive(
            archive_path=export_path,
            project_name=new_name,
        )

        assert import_result["success"] is True
        assert import_result["project_name"] == new_name
        assert import_result["original_name"] == sample_archive

        # Verify renamed project exists
        renamed_info = importer.compressor.get_archive_info(new_name)
        assert renamed_info is not None
        assert renamed_info["project_name"] == new_name

    @pytest.mark.asyncio
    async def test_multiple_export_import_cycles(
        self, exporter, importer, sample_archive, temp_dirs
    ):
        """Test multiple export → import cycles."""
        for i in range(3):
            # Export
            export_path = temp_dirs["export_dir"] / f"roundtrip_cycle_{i}.tar.gz"
            export_result = await exporter.export_project_archive(
                project_name=sample_archive,
                output_path=export_path,
            )
            assert export_result["success"] is True

            # Import with unique name
            import_name = f"import-cycle-{i}"
            import_result = await importer.import_project_archive(
                archive_path=export_path,
                project_name=import_name,
            )
            assert import_result["success"] is True

            # Verify
            imported_info = importer.compressor.get_archive_info(import_name)
            assert imported_info is not None
