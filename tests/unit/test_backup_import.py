"""Tests for backup import functionality.

Tests the DataImporter class which handles importing memories from backups:
- Import from JSON with conflict resolution strategies
- Import from portable archives (tar.gz)
- Dry-run mode for previewing imports
- Various conflict strategies: keep_newer, keep_older, keep_both, skip, merge_metadata

These tests use the real QdrantMemoryStore with pooled connections.
"""

import pytest

# Run sequentially on single worker - Qdrant connection sensitive under parallel execution
pytestmark = pytest.mark.xdist_group("qdrant_sequential")
import pytest_asyncio
import uuid
from pathlib import Path
import json
import tempfile
import os
from datetime import datetime, UTC

from src.backup.exporter import DataExporter
from src.backup.importer import DataImporter, ConflictStrategy
from src.core.models import MemoryUnit, MemoryCategory, ContextLevel, MemoryScope, LifecycleState
from src.store.qdrant_store import QdrantMemoryStore
from src.config import ServerConfig


@pytest_asyncio.fixture
async def temp_store(qdrant_client, unique_qdrant_collection):
    """Create a temporary Qdrant store for testing with pooled collection.

    Uses the session-scoped qdrant_client and unique_qdrant_collection
    fixtures from conftest.py to leverage collection pooling and prevent
    Qdrant deadlocks during parallel test execution.
    """
    # Use environment variable for Qdrant URL (supports isolated test runner)
    qdrant_url = os.getenv("QDRANT_URL") or os.getenv("CLAUDE_RAG_QDRANT_URL", "http://localhost:6333")
    config = ServerConfig(
        storage_backend="qdrant",
        qdrant_url=qdrant_url,
        qdrant_collection_name=unique_qdrant_collection,
    )
    store = QdrantMemoryStore(config)
    await store.initialize()
    yield store

    # Cleanup
    await store.close()
    # Collection cleanup handled by unique_qdrant_collection autouse fixture


@pytest.mark.asyncio
async def test_import_from_json(temp_store):
    """Test importing memories from JSON."""
    # Use valid UUID for Qdrant
    test_id = str(uuid.uuid4())

    # Create test data
    test_data = {
        "version": "1.0.0",
        "schema_version": "3.0.0",
        "export_date": datetime.now(UTC).isoformat(),
        "export_type": "full",
        "filters": {},
        "memory_count": 1,
        "memories": [
            {
                "id": test_id,
                "content": "Imported memory",
                "category": "preference",
                "context_level": "USER_PREFERENCE",
                "scope": "global",
                "project_name": "import-project",
                "importance": 0.7,
                "embedding_model": "test-model",
                "embedding": [0.3] * 768,
                "created_at": datetime.now(UTC).isoformat(),
                "updated_at": datetime.now(UTC).isoformat(),
                "last_accessed": datetime.now(UTC).isoformat(),
                "lifecycle_state": "ACTIVE",
                "tags": [],
                "metadata": {},
            }
        ],
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        # Write test JSON
        input_path = Path(tmpdir) / "import.json"
        with open(input_path, 'w') as f:
            json.dump(test_data, f)

        # Import
        importer = DataImporter(temp_store)
        stats = await importer.import_from_json(input_path)

        # Verify import
        assert stats["format"] == "json"
        assert stats["total_memories"] == 1
        assert stats["imported"] == 1
        assert stats["conflicts"] == 0
        assert stats["errors"] == 0

        # Verify memory was stored
        memory = await temp_store.get_by_id(test_id)
        assert memory.content == "Imported memory"


@pytest.mark.asyncio
async def test_import_conflict_keep_newer(temp_store):
    """Test import conflict resolution: keep newer."""
    # Use valid UUID for Qdrant
    test_id = str(uuid.uuid4())

    # Store an existing memory
    old_time = datetime(2024, 1, 1, 0, 0, 0, tzinfo=UTC)
    await temp_store.store(
        content="Old content",
        embedding=[0.1] * 768,
        metadata={
            "id": test_id,
            "category": MemoryCategory.PREFERENCE.value,
            "context_level": ContextLevel.USER_PREFERENCE.value,
            "scope": MemoryScope.GLOBAL.value,
            "project_name": "test",
            "importance": 0.5,
            "embedding_model": "test-model",
            "created_at": old_time.isoformat(),
            "updated_at": old_time.isoformat(),
            "last_accessed": old_time.isoformat(),
            "lifecycle_state": LifecycleState.ACTIVE.value,
        }
    )

    # Create import data with newer memory
    new_time = datetime.now(UTC)
    test_data = {
        "version": "1.0.0",
        "schema_version": "3.0.0",
        "export_date": new_time.isoformat(),
        "export_type": "full",
        "filters": {},
        "memory_count": 1,
        "memories": [
            {
                "id": test_id,
                "content": "New content",
                "category": "preference",
                "context_level": "USER_PREFERENCE",
                "scope": "global",
                "project_name": "test",
                "importance": 0.8,
                "embedding_model": "test-model",
                "embedding": [0.2] * 768,
                "created_at": new_time.isoformat(),
                "updated_at": new_time.isoformat(),
                "last_accessed": new_time.isoformat(),
                "lifecycle_state": "ACTIVE",
                "tags": [],
                "metadata": {},
            }
        ],
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = Path(tmpdir) / "import.json"
        with open(input_path, 'w') as f:
            json.dump(test_data, f)

        # Import with KEEP_NEWER strategy
        importer = DataImporter(temp_store)
        stats = await importer.import_from_json(
            input_path,
            conflict_strategy=ConflictStrategy.KEEP_NEWER,
        )

        # Verify conflict was detected and resolved
        assert stats["conflicts"] == 1
        assert stats["conflict_resolutions"]["kept_newer"] == 1

        # Verify new content was kept
        memory = await temp_store.get_by_id(test_id)
        assert memory.content == "New content"


@pytest.mark.asyncio
async def test_import_dry_run(temp_store):
    """Test dry run import (no changes)."""
    test_data = {
        "version": "1.0.0",
        "schema_version": "3.0.0",
        "export_date": datetime.now(UTC).isoformat(),
        "export_type": "full",
        "filters": {},
        "memory_count": 1,
        "memories": [
            {
                "id": "dry-run-test",
                "content": "Dry run memory",
                "category": "preference",
                "context_level": "USER_PREFERENCE",
                "scope": "global",
                "project_name": "test",
                "importance": 0.7,
                "embedding_model": "test-model",
                "embedding": [0.3] * 768,
                "created_at": datetime.now(UTC).isoformat(),
                "updated_at": datetime.now(UTC).isoformat(),
                "last_accessed": datetime.now(UTC).isoformat(),
                "lifecycle_state": "ACTIVE",
                "tags": [],
                "metadata": {},
            }
        ],
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = Path(tmpdir) / "import.json"
        with open(input_path, 'w') as f:
            json.dump(test_data, f)

        # Dry run import
        importer = DataImporter(temp_store)
        stats = await importer.import_from_json(input_path, dry_run=True)

        # Verify analysis was performed
        assert stats["total_memories"] == 1
        assert stats["imported"] == 1

        # Verify no actual import happened
        memory = await temp_store.get_by_id("dry-run-test")
        assert memory is None


@pytest.mark.asyncio
async def test_import_from_archive(temp_store):
    """Test importing from portable archive."""
    # Use valid UUID for Qdrant
    test_id = str(uuid.uuid4())

    # First create an archive by storing a memory
    now = datetime.now(UTC)
    await temp_store.store(
        content="Archive memory",
        embedding=[0.4] * 768,
        metadata={
            "id": test_id,
            "category": MemoryCategory.PREFERENCE.value,
            "context_level": ContextLevel.USER_PREFERENCE.value,
            "scope": MemoryScope.GLOBAL.value,
            "project_name": "archive-project",
            "importance": 0.7,
            "embedding_model": "test-model",
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
            "last_accessed": now.isoformat(),
            "lifecycle_state": LifecycleState.ACTIVE.value,
        }
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        # Export to archive
        exporter = DataExporter(temp_store)
        archive_path = Path(tmpdir) / "test.tar.gz"
        await exporter.create_portable_archive(archive_path)

        # Clear the store
        await temp_store.delete(test_id)

        # Import from archive
        importer = DataImporter(temp_store)
        stats = await importer.import_from_archive(archive_path)

        # Verify import
        assert stats["format"] == "archive"
        assert stats["imported"] == 1

        # Verify memory was restored
        restored = await temp_store.get_by_id(test_id)
        assert restored.content == "Archive memory"
