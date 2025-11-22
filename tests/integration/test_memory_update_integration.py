"""Integration tests for memory update operations."""

import pytest
import pytest_asyncio
import asyncio
import uuid
from datetime import datetime, UTC
from pathlib import Path
from src.core.server import MemoryRAGServer
from src.core.models import (
    MemoryCategory,
    MemoryScope,
    ContextLevel,
)
from src.config import ServerConfig
from src.core.exceptions import ReadOnlyError


@pytest_asyncio.fixture
async def test_server(tmp_path, qdrant_client, unique_qdrant_collection):
    """Create a test server with pooled collection.

    Uses the session-scoped qdrant_client and unique_qdrant_collection
    fixtures from conftest.py to leverage collection pooling and prevent
    Qdrant deadlocks during parallel test execution.
    """
    config = ServerConfig(
        storage_backend="qdrant",
        qdrant_url="http://localhost:6333",
        qdrant_collection_name=unique_qdrant_collection,
        read_only_mode=False,
        embedding_model="all-MiniLM-L6-v2",
    )
    server = MemoryRAGServer(config)
    await server.initialize()
    yield server

    # Cleanup
    await server.close()
    # Collection cleanup handled by unique_qdrant_collection autouse fixture


@pytest_asyncio.fixture
async def test_memory_id(test_server):
    """Create a test memory and return its ID."""
    result = await test_server.store_memory(
        content="Original content",
        category="fact",
        importance=0.5,
        tags=["test", "original"],
        metadata={"source": "test"},
    )
    return result["memory_id"]


class TestMemoryUpdateIntegration:
    """Integration tests for memory update operations."""

    @pytest.mark.asyncio
    async def test_update_content(self, test_server, test_memory_id):
        """Test updating memory content."""
        result = await test_server.update_memory(
            memory_id=test_memory_id,
            content="Updated content",
        )

        assert result["status"] == "updated"
        assert "content" in result["updated_fields"]
        assert result["embedding_regenerated"] is True

        # Verify the update
        retrieved = await test_server.get_memory_by_id(test_memory_id)
        assert retrieved["status"] == "success"
        assert retrieved["memory"]["content"] == "Updated content"

    @pytest.mark.asyncio
    async def test_update_importance(self, test_server, test_memory_id):
        """Test updating memory importance."""
        result = await test_server.update_memory(
            memory_id=test_memory_id,
            importance=0.9,
        )

        assert result["status"] == "updated"
        assert "importance" in result["updated_fields"]
        assert result["embedding_regenerated"] is False

        # Verify the update
        retrieved = await test_server.get_memory_by_id(test_memory_id)
        assert retrieved["memory"]["importance"] == 0.9

    @pytest.mark.asyncio
    async def test_update_category(self, test_server, test_memory_id):
        """Test updating memory category."""
        result = await test_server.update_memory(
            memory_id=test_memory_id,
            category="preference",
        )

        assert result["status"] == "updated"
        assert "category" in result["updated_fields"]

        # Verify the update
        retrieved = await test_server.get_memory_by_id(test_memory_id)
        assert retrieved["memory"]["category"] == "preference"

    @pytest.mark.asyncio
    async def test_update_tags(self, test_server, test_memory_id):
        """Test updating memory tags."""
        result = await test_server.update_memory(
            memory_id=test_memory_id,
            tags=["updated", "tags", "new"],
        )

        assert result["status"] == "updated"
        assert "tags" in result["updated_fields"]

        # Verify the update
        retrieved = await test_server.get_memory_by_id(test_memory_id)
        assert set(retrieved["memory"]["tags"]) == {"updated", "tags", "new"}

    @pytest.mark.asyncio
    async def test_update_metadata(self, test_server, test_memory_id):
        """Test updating memory metadata."""
        result = await test_server.update_memory(
            memory_id=test_memory_id,
            metadata={"updated": True, "version": 2},
        )

        assert result["status"] == "updated"
        assert "metadata" in result["updated_fields"]

        # Verify the update
        retrieved = await test_server.get_memory_by_id(test_memory_id)
        assert retrieved["memory"]["metadata"]["updated"] is True
        assert retrieved["memory"]["metadata"]["version"] == 2

    @pytest.mark.asyncio
    async def test_update_context_level(self, test_server, test_memory_id):
        """Test updating memory context level."""
        result = await test_server.update_memory(
            memory_id=test_memory_id,
            context_level="USER_PREFERENCE",
        )

        assert result["status"] == "updated"
        assert "context_level" in result["updated_fields"]

        # Verify the update
        retrieved = await test_server.get_memory_by_id(test_memory_id)
        assert retrieved["memory"]["context_level"] == "USER_PREFERENCE"

    @pytest.mark.asyncio
    async def test_update_multiple_fields(self, test_server, test_memory_id):
        """Test updating multiple fields at once."""
        result = await test_server.update_memory(
            memory_id=test_memory_id,
            content="Multi-field update",
            importance=0.95,
            tags=["multi", "update"],
            category="preference",
        )

        assert result["status"] == "updated"
        assert len(result["updated_fields"]) == 4
        assert "content" in result["updated_fields"]
        assert "importance" in result["updated_fields"]
        assert "tags" in result["updated_fields"]
        assert "category" in result["updated_fields"]
        assert result["embedding_regenerated"] is True

        # Verify all updates
        retrieved = await test_server.get_memory_by_id(test_memory_id)
        memory = retrieved["memory"]
        assert memory["content"] == "Multi-field update"
        assert memory["importance"] == 0.95
        assert set(memory["tags"]) == {"multi", "update"}
        assert memory["category"] == "preference"

    @pytest.mark.asyncio
    async def test_update_nonexistent_memory(self, test_server):
        """Test updating a memory that doesn't exist."""
        result = await test_server.update_memory(
            memory_id="nonexistent-id",
            content="This should fail",
        )

        assert result["status"] == "not_found"
        assert "nonexistent-id" in result["message"]

    @pytest.mark.asyncio
    async def test_update_preserves_timestamps_by_default(self, test_server, test_memory_id):
        """Test that update preserves created_at by default."""
        # Get original memory
        original = await test_server.get_memory_by_id(test_memory_id)
        original_created_at = original["memory"]["created_at"]

        # Wait a bit to ensure timestamp would differ
        await asyncio.sleep(0.1)

        # Update memory
        result = await test_server.update_memory(
            memory_id=test_memory_id,
            content="Updated content",
        )

        assert result["status"] == "updated"

        # Verify created_at is preserved
        updated = await test_server.get_memory_by_id(test_memory_id)
        assert updated["memory"]["created_at"] == original_created_at

    @pytest.mark.asyncio
    async def test_update_without_embedding_regeneration(self, test_server, test_memory_id):
        """Test updating content without regenerating embedding."""
        result = await test_server.update_memory(
            memory_id=test_memory_id,
            content="Updated without new embedding",
            regenerate_embedding=False,
        )

        assert result["status"] == "updated"
        assert "content" in result["updated_fields"]
        assert result["embedding_regenerated"] is False

    @pytest.mark.asyncio
    async def test_get_memory_by_id_success(self, test_server, test_memory_id):
        """Test retrieving memory by ID."""
        result = await test_server.get_memory_by_id(test_memory_id)

        assert result["status"] == "success"
        assert "memory" in result
        assert result["memory"]["id"] == test_memory_id
        assert result["memory"]["content"] == "Original content"
        assert result["memory"]["category"] == "fact"
        assert result["memory"]["importance"] == 0.5

    @pytest.mark.asyncio
    async def test_get_memory_by_id_not_found(self, test_server):
        """Test retrieving non-existent memory by ID."""
        result = await test_server.get_memory_by_id("nonexistent-id")

        assert result["status"] == "not_found"
        assert "nonexistent-id" in result["message"]

    @pytest.mark.asyncio
    async def test_update_in_read_only_mode(self, tmp_path, unique_qdrant_collection):
        """Test that update fails in read-only mode."""
        config = ServerConfig(
            storage_backend="qdrant",
            qdrant_url="http://localhost:6333",
            qdrant_collection_name=unique_qdrant_collection,
            read_only_mode=True,
        )
        server = MemoryRAGServer(config)
        await server.initialize()

        try:
            with pytest.raises(ReadOnlyError):
                await server.update_memory(
                    memory_id="test-id",
                    content="This should fail",
                )
        finally:
            await server.close()

    @pytest.mark.asyncio
    async def test_update_stats_tracking(self, test_server, test_memory_id):
        """Test that update increments stats counter."""
        initial_stats = test_server.stats.get("memories_updated", 0)

        await test_server.update_memory(
            memory_id=test_memory_id,
            importance=0.7,
        )

        assert test_server.stats["memories_updated"] == initial_stats + 1

    @pytest.mark.asyncio
    async def test_update_and_retrieve_workflow(self, test_server, test_memory_id):
        """Test full update and retrieve workflow."""
        # Update the memory
        update_result = await test_server.update_memory(
            memory_id=test_memory_id,
            content="Updated in workflow test",
            importance=0.85,
            tags=["workflow", "test"],
            metadata={"workflow": "integration"},
        )

        assert update_result["status"] == "updated"
        assert len(update_result["updated_fields"]) == 4

        # Retrieve and verify
        get_result = await test_server.get_memory_by_id(test_memory_id)
        memory = get_result["memory"]

        assert memory["content"] == "Updated in workflow test"
        assert memory["importance"] == 0.85
        assert set(memory["tags"]) == {"workflow", "test"}
        assert memory["metadata"]["workflow"] == "integration"

