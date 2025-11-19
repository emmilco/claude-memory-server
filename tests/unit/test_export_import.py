"""Tests for memory export/import functionality."""

import pytest
import pytest_asyncio
import json
import tempfile
from pathlib import Path
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from src.core.server import MemoryRAGServer
from src.core.exceptions import ValidationError, StorageError
from src.config import ServerConfig


@pytest.fixture
def mock_config():
    """Create a mock server config."""
    config = MagicMock()
    config.storage_backend = "sqlite"
    config.qdrant_url = "http://localhost:6333"
    config.collection_name = "test_memories"
    config.embedding_model = "all-MiniLM-L6-v2"
    config.data_dir = Path("~/.claude-rag").expanduser()
    config.current_project = None
    config.read_only_mode = False
    config.enable_cache = False
    config.cache_dir = Path("/tmp/test_cache")
    return config


@pytest_asyncio.fixture
async def server(mock_config):
    """Create a MemoryRAGServer instance for testing."""
    server = MemoryRAGServer(mock_config)

    # Mock the store and embedding generator
    server.store = AsyncMock()
    server.embedding_gen = AsyncMock()
    server.embedding_gen.generate = AsyncMock(return_value=[0.1] * 384)

    # Mock list_memories to return sample data
    server.list_memories = AsyncMock(return_value={
        "memories": [
            {
                "memory_id": "mem_1",
                "content": "Test memory 1",
                "category": "fact",
                "context_level": "SESSION_STATE",
                "scope": "global",
                "importance": 0.8,
                "tags": ["test", "python"],
                "created_at": "2025-01-01T10:00:00",
                "updated_at": "2025-01-01T10:00:00"
            },
            {
                "memory_id": "mem_2",
                "content": "Test memory 2",
                "category": "preference",
                "context_level": "USER_PREFERENCE",
                "scope": "project",
                "project_name": "test-project",
                "importance": 0.9,
                "tags": ["preference"],
                "created_at": "2025-01-02T10:00:00",
                "updated_at": "2025-01-02T10:00:00"
            }
        ],
        "total_count": 2,
        "returned_count": 2,
        "offset": 0,
        "limit": 20,
        "has_more": False
    })

    yield server

    # Cleanup
    if hasattr(server, "store"):
        await server.store.close()


class TestExportMemories:
    """Tests for export_memories functionality."""

    @pytest.mark.asyncio
    async def test_export_json_to_file(self, server):
        """Test exporting memories to JSON file."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            temp_path = f.name

        try:
            result = await server.export_memories(
                output_path=temp_path,
                format="json"
            )

            assert result["status"] == "success"
            assert result["format"] == "json"
            assert result["count"] == 2
            assert "file_path" in result

            # Verify file was created and has valid JSON
            with open(temp_path, 'r') as f:
                data = json.load(f)

            assert data["version"] == "1.0"
            assert data["total_count"] == 2
            assert len(data["memories"]) == 2
            assert data["memories"][0]["memory_id"] == "mem_1"
            assert data["memories"][1]["memory_id"] == "mem_2"

        finally:
            Path(temp_path).unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_export_json_as_string(self, server):
        """Test exporting memories as JSON string without file."""
        result = await server.export_memories(
            output_path=None,
            format="json"
        )

        assert result["status"] == "success"
        assert result["format"] == "json"
        assert result["count"] == 2
        assert "content" in result
        assert "file_path" not in result

        # Verify content is valid JSON
        data = json.loads(result["content"])
        assert data["version"] == "1.0"
        assert data["total_count"] == 2

    @pytest.mark.asyncio
    async def test_export_markdown(self, server):
        """Test exporting memories to Markdown format."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.md') as f:
            temp_path = f.name

        try:
            result = await server.export_memories(
                output_path=temp_path,
                format="markdown"
            )

            assert result["status"] == "success"
            assert result["format"] == "markdown"
            assert result["count"] == 2

            # Verify file was created and has markdown content
            with open(temp_path, 'r') as f:
                content = f.read()

            assert "# Memory Export" in content
            assert "## Memory: mem_1" in content
            assert "## Memory: mem_2" in content
            assert "**Category:** technical" in content
            assert "Test memory 1" in content

        finally:
            Path(temp_path).unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_export_with_filtering(self, server):
        """Test exporting memories with filtering."""
        result = await server.export_memories(
            output_path=None,
            format="json",
            category="fact",
            min_importance=0.7
        )

        assert result["status"] == "success"

        # Verify list_memories was called with correct filters
        server.list_memories.assert_called_once()
        call_args = server.list_memories.call_args[1]
        assert call_args["category"] == "fact"
        assert call_args["min_importance"] == 0.7

    @pytest.mark.asyncio
    async def test_export_invalid_format(self, server):
        """Test exporting with invalid format raises error."""
        with pytest.raises(ValidationError, match="Invalid export format"):
            await server.export_memories(
                output_path=None,
                format="invalid"
            )

    @pytest.mark.asyncio
    async def test_export_creates_parent_directories(self, server):
        """Test that export creates parent directories if they don't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_path = Path(tmpdir) / "subdir" / "export.json"

            result = await server.export_memories(
                output_path=str(temp_path),
                format="json"
            )

            assert result["status"] == "success"
            assert temp_path.exists()
            assert temp_path.parent.exists()


class TestImportMemories:
    """Tests for import_memories functionality."""

    @pytest.fixture
    def sample_export_data(self):
        """Create sample export data for import tests."""
        return {
            "version": "1.0",
            "exported_at": "2025-01-01T12:00:00",
            "total_count": 3,
            "memories": [
                {
                    "memory_id": "mem_new_1",
                    "content": "New memory 1",
                    "category": "fact",
                    "context_level": "SESSION_STATE",
                    "scope": "global",
                    "importance": 0.7,
                    "tags": ["new"],
                    "created_at": "2025-01-01T10:00:00",
                    "updated_at": "2025-01-01T10:00:00"
                },
                {
                    "memory_id": "mem_existing",
                    "content": "Updated content",
                    "category": "preference",
                    "context_level": "USER_PREFERENCE",
                    "scope": "global",
                    "importance": 0.9,
                    "tags": ["updated"],
                    "created_at": "2024-12-01T10:00:00",
                    "updated_at": "2025-01-01T10:00:00"
                },
                {
                    "memory_id": "mem_new_2",
                    "content": "New memory 2",
                    "category": "fact",
                    "context_level": "PROJECT_CONTEXT",
                    "scope": "project",
                    "project_name": "test-project",
                    "importance": 0.8,
                    "tags": [],
                    "created_at": "2025-01-02T10:00:00",
                    "updated_at": "2025-01-02T10:00:00"
                }
            ]
        }

    @pytest.mark.asyncio
    async def test_import_from_file_skip_mode(self, server, sample_export_data):
        """Test importing memories from file with skip mode."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            json.dump(sample_export_data, f)
            temp_path = f.name

        try:
            # Mock get_by_id to return existing for one memory
            server.store.get_by_id = AsyncMock(side_effect=lambda id:
                MagicMock() if id == "mem_existing" else None
            )
            server.store.store = AsyncMock(return_value="new_id")

            result = await server.import_memories(
                file_path=temp_path,
                conflict_mode="skip"
            )

            assert result["status"] == "success"
            assert result["created"] == 2  # mem_new_1 and mem_new_2
            assert result["updated"] == 0
            assert result["skipped"] == 1  # mem_existing
            assert result["total_processed"] == 3
            assert len(result["errors"]) == 0

        finally:
            Path(temp_path).unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_import_from_file_overwrite_mode(self, server, sample_export_data):
        """Test importing memories with overwrite mode."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            json.dump(sample_export_data, f)
            temp_path = f.name

        try:
            # Mock get_by_id to return existing for one memory
            server.store.get_by_id = AsyncMock(side_effect=lambda id:
                MagicMock() if id == "mem_existing" else None
            )
            server.store.store = AsyncMock(return_value="new_id")
            server.store.update = AsyncMock(return_value=True)

            result = await server.import_memories(
                file_path=temp_path,
                conflict_mode="overwrite"
            )

            assert result["status"] == "success"
            assert result["created"] == 2  # mem_new_1 and mem_new_2
            assert result["updated"] == 1  # mem_existing
            assert result["skipped"] == 0
            assert result["total_processed"] == 3

        finally:
            Path(temp_path).unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_import_from_file_merge_mode(self, server, sample_export_data):
        """Test importing memories with merge mode."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            json.dump(sample_export_data, f)
            temp_path = f.name

        try:
            # Mock get_by_id to return existing for one memory
            server.store.get_by_id = AsyncMock(side_effect=lambda id:
                MagicMock() if id == "mem_existing" else None
            )
            server.store.store = AsyncMock(return_value="new_id")
            server.store.update = AsyncMock(return_value=True)

            result = await server.import_memories(
                file_path=temp_path,
                conflict_mode="merge"
            )

            assert result["status"] == "success"
            assert result["created"] == 2
            assert result["updated"] == 1  # mem_existing merged
            assert result["skipped"] == 0

        finally:
            Path(temp_path).unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_import_from_content_string(self, server, sample_export_data):
        """Test importing memories from content string."""
        content = json.dumps(sample_export_data)

        server.store.get_by_id = AsyncMock(return_value=None)
        server.store.store = AsyncMock(return_value="new_id")

        result = await server.import_memories(
            content=content,
            conflict_mode="skip"
        )

        assert result["status"] == "success"
        assert result["created"] == 3
        assert result["total_processed"] == 3

    @pytest.mark.asyncio
    async def test_import_invalid_conflict_mode(self, server):
        """Test that invalid conflict mode raises error."""
        with pytest.raises(ValidationError, match="Invalid conflict mode"):
            await server.import_memories(
                file_path="/tmp/test.json",
                conflict_mode="invalid"
            )

    @pytest.mark.asyncio
    async def test_import_missing_file(self, server):
        """Test that missing file raises error."""
        with pytest.raises(ValidationError, match="Import file not found"):
            await server.import_memories(
                file_path="/nonexistent/file.json",
                conflict_mode="skip"
            )

    @pytest.mark.asyncio
    async def test_import_no_input(self, server):
        """Test that no file_path or content raises error."""
        with pytest.raises(ValidationError, match="Must provide either file_path or content"):
            await server.import_memories(
                conflict_mode="skip"
            )

    @pytest.mark.asyncio
    async def test_import_invalid_json(self, server):
        """Test that invalid JSON raises error."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            f.write("invalid json {")
            temp_path = f.name

        try:
            with pytest.raises(ValidationError, match="Invalid JSON format"):
                await server.import_memories(
                    file_path=temp_path,
                    conflict_mode="skip"
                )
        finally:
            Path(temp_path).unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_import_missing_memories_key(self, server):
        """Test that missing 'memories' key raises error."""
        data = {"version": "1.0", "total_count": 0}

        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            json.dump(data, f)
            temp_path = f.name

        try:
            with pytest.raises(ValidationError, match="must contain 'memories' key"):
                await server.import_memories(
                    file_path=temp_path,
                    conflict_mode="skip"
                )
        finally:
            Path(temp_path).unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_import_with_errors(self, server):
        """Test import with some memories causing errors."""
        data = {
            "version": "1.0",
            "memories": [
                {
                    # Missing memory_id - should cause error
                    "content": "Test",
                    "category": "fact"
                },
                {
                    "memory_id": "mem_valid",
                    "content": "Valid memory",
                    "category": "fact"
                }
            ]
        }

        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            json.dump(data, f)
            temp_path = f.name

        try:
            server.store.get_by_id = AsyncMock(return_value=None)
            server.store.store = AsyncMock(return_value="new_id")

            result = await server.import_memories(
                file_path=temp_path,
                conflict_mode="skip"
            )

            assert result["status"] == "partial"  # Some errors occurred
            assert result["created"] == 1  # Only valid memory created
            assert len(result["errors"]) == 1  # One error for missing ID
            assert "Missing memory_id/id" in result["errors"][0]

        finally:
            Path(temp_path).unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_import_auto_detect_format(self, server, sample_export_data):
        """Test that format is auto-detected from file extension."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            json.dump(sample_export_data, f)
            temp_path = f.name

        try:
            server.store.get_by_id = AsyncMock(return_value=None)
            server.store.store = AsyncMock(return_value="new_id")

            # Don't specify format - should auto-detect from .json extension
            result = await server.import_memories(
                file_path=temp_path,
                conflict_mode="skip"
            )

            assert result["status"] == "success"

        finally:
            Path(temp_path).unlink(missing_ok=True)


class TestExportImportIntegration:
    """Integration tests for export/import round-trip."""

    @pytest.mark.asyncio
    async def test_export_import_round_trip(self, server):
        """Test exporting and re-importing memories."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            export_path = f.name

        try:
            # Export
            export_result = await server.export_memories(
                output_path=export_path,
                format="json"
            )

            assert export_result["status"] == "success"
            assert export_result["count"] == 2

            # Re-import
            server.store.get_by_id = AsyncMock(return_value=None)
            server.store.store = AsyncMock(return_value="new_id")

            import_result = await server.import_memories(
                file_path=export_path,
                conflict_mode="skip"
            )

            assert import_result["status"] == "success"
            assert import_result["created"] == 2
            assert import_result["total_processed"] == 2

        finally:
            Path(export_path).unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_metadata_preservation(self, server):
        """Test that all metadata is preserved in export/import."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            export_path = f.name

        try:
            # Export
            await server.export_memories(
                output_path=export_path,
                format="json"
            )

            # Read exported data
            with open(export_path, 'r') as f:
                data = json.load(f)

            mem = data["memories"][0]

            # Verify all fields are present
            required_fields = [
                "memory_id", "content", "category", "context_level",
                "scope", "importance", "tags", "created_at", "updated_at"
            ]

            for field in required_fields:
                assert field in mem, f"Field {field} missing from export"

        finally:
            Path(export_path).unlink(missing_ok=True)
