"""Tests for backup export functionality."""

import pytest
import pytest_asyncio
from pathlib import Path
import json
import tempfile
import uuid
from datetime import datetime, UTC

from src.backup.exporter import DataExporter
from src.core.models import MemoryUnit, MemoryCategory, ContextLevel, MemoryScope, LifecycleState
from src.store.qdrant_store import QdrantMemoryStore
from src.config import ServerConfig


@pytest_asyncio.fixture
async def temp_store(qdrant_client, unique_qdrant_collection):
    """Create a temporary Qdrant store for testing with unique collection.

    Uses the session-scoped qdrant_client and unique_qdrant_collection
    fixtures from conftest.py to leverage collection pooling and prevent
    Qdrant deadlocks during parallel test execution.
    """
    config = ServerConfig(
        storage_backend="qdrant",
        qdrant_url="http://localhost:6333",
        qdrant_collection_name=unique_qdrant_collection,
    )
    store = QdrantMemoryStore(config)
    await store.initialize()

    # Add some test memories
    memories = [
            MemoryUnit(
                id=str(uuid.uuid4()),
                content="Test memory 1",
                category=MemoryCategory.PREFERENCE,
                context_level=ContextLevel.USER_PREFERENCE,
                scope=MemoryScope.GLOBAL,
                project_name="test-project",
                importance=0.8,
                embedding_model="test-model",
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
                last_accessed=datetime.now(UTC),
                lifecycle_state=LifecycleState.ACTIVE,
            ),
            MemoryUnit(
                id=str(uuid.uuid4()),
                content="Test memory 2",
                category=MemoryCategory.FACT,
                context_level=ContextLevel.PROJECT_CONTEXT,
                scope=MemoryScope.PROJECT,
                project_name="test-project",
                importance=0.6,
                embedding_model="test-model",
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
                last_accessed=datetime.now(UTC),
                lifecycle_state=LifecycleState.ACTIVE,
            ),
    ]

    # Embeddings stored separately
    embeddings = [[0.1] * 384, [0.2] * 384]

    for memory, embedding in zip(memories, embeddings):
        await store.store(
            content=memory.content,
            embedding=embedding,
            metadata={
                "id": memory.id,
                "category": memory.category.value,
                "context_level": memory.context_level.value,
                "scope": memory.scope.value,
                "project_name": memory.project_name,
                "importance": memory.importance,
                "embedding_model": memory.embedding_model,
                "created_at": memory.created_at.isoformat(),
                "updated_at": memory.updated_at.isoformat(),
                "last_accessed": memory.last_accessed.isoformat(),
                "lifecycle_state": memory.lifecycle_state.value,
            }
        )

    yield store

    # Cleanup
    await store.close()
    # Collection cleanup handled by unique_qdrant_collection autouse fixture


@pytest.mark.asyncio
async def test_export_to_json(temp_store):
    """Test exporting memories to JSON."""
    exporter = DataExporter(temp_store)

    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "export.json"

        stats = await exporter.export_to_json(output_path)

        # Verify export completed
        assert stats["format"] == "json"
        assert stats["memory_count"] == 2
        assert output_path.exists()

        # Verify JSON content
        with open(output_path, 'r') as f:
            data = json.load(f)

        assert data["version"] == "1.0.0"
        assert data["memory_count"] == 2
        assert len(data["memories"]) == 2


@pytest.mark.asyncio
async def test_export_with_project_filter(temp_store):
    """Test exporting memories with project filter."""
    exporter = DataExporter(temp_store)

    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "export.json"

        stats = await exporter.export_to_json(output_path, project_name="test-project")

        assert stats["memory_count"] == 2
        assert output_path.exists()


@pytest.mark.asyncio
async def test_create_portable_archive(temp_store):
    """Test creating portable archive."""
    exporter = DataExporter(temp_store)

    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "backup.tar.gz"

        stats = await exporter.create_portable_archive(output_path, include_embeddings=True)

        # Verify archive created
        assert stats["format"] == "archive"
        assert stats["memory_count"] == 2
        assert stats["includes_embeddings"] is True
        assert output_path.exists()

        # Verify archive contains expected files
        import tarfile
        with tarfile.open(output_path, 'r:gz') as tar:
            names = tar.getnames()
            assert "memories.json" in names
            assert "embeddings.npz" in names
            assert "manifest.json" in names
            assert "checksums.sha256" in names


@pytest.mark.asyncio
async def test_export_to_markdown(temp_store):
    """Test exporting memories to Markdown."""
    exporter = DataExporter(temp_store)

    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "export.md"

        stats = await exporter.export_to_markdown(output_path, include_metadata=True)

        # Verify export completed
        assert stats["format"] == "markdown"
        assert stats["memory_count"] == 2
        assert output_path.exists()

        # Verify Markdown content
        content = output_path.read_text()
        assert "# Memory Export" in content
        assert "test-project" in content
        assert "Test memory 1" in content
        assert "Test memory 2" in content
