"""Targeted tests for qdrant_store error handling paths."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.config import ServerConfig
from src.store.qdrant_store import QdrantMemoryStore
from src.core.models import MemoryCategory, MemoryScope, ContextLevel
from src.core.exceptions import StorageError, ValidationError, RetrievalError
from tests.conftest import mock_embedding


class TestQdrantStoreErrorPaths:
    """Test error handling in qdrant_store."""

    def test_config_none_uses_get_config(self):
        """Test that config=None triggers get_config() path (lines 38-39)."""
        with patch("src.config.get_config") as mock_get_config:
            mock_config = ServerConfig(qdrant_url="http://localhost:6333")
            mock_get_config.return_value = mock_config

            # Create store without config (use_pool=False for mocking)
            store = QdrantMemoryStore(config=None, use_pool=False)

            # Should have called get_config
            mock_get_config.assert_called_once()
            assert store.config == mock_config

    @pytest.mark.asyncio
    async def test_initialize_raises_storage_error_on_connection_failure(self):
        """Test initialization failure error handling (lines 52-53)."""
        config = ServerConfig(qdrant_url="http://invalid:9999")
        store = QdrantMemoryStore(config, use_pool=False)

        with patch.object(
            store.setup, "connect", side_effect=ConnectionError("Cannot connect")
        ):
            with pytest.raises(StorageError) as exc_info:
                await store.initialize()

            assert "Failed to initialize Qdrant store" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_store_auto_initialize(self):
        """Test store auto-initializes if client is None (line 63)."""
        config = ServerConfig(qdrant_url="http://localhost:6333")
        store = QdrantMemoryStore(config, use_pool=False)

        # Client should be None initially
        assert store.client is None

        with patch.object(store, "initialize", new_callable=AsyncMock) as mock_init:
            mock_client = MagicMock()

            async def init_side_effect():
                store.client = mock_client

            mock_init.side_effect = init_side_effect
            mock_client.upsert = MagicMock()

            await store.store(
                content="test",
                embedding=mock_embedding(value=0.1),
                metadata={
                    "category": MemoryCategory.FACT.value,
                    "context_level": ContextLevel.PROJECT_CONTEXT.value,
                    "scope": MemoryScope.GLOBAL.value,
                },
            )

            # Should have called initialize
            mock_init.assert_called_once()
            # Behavior: client should now be set
            assert store.client is not None
            assert store.client == mock_client

    @pytest.mark.asyncio
    async def test_store_validation_error(self):
        """Test store ValueError handling (lines 85-88)."""
        config = ServerConfig(qdrant_url="http://localhost:6333")
        store = QdrantMemoryStore(config, use_pool=False)
        store.client = MagicMock()

        # Mock _build_payload to raise ValueError
        with patch.object(
            store, "_build_payload", side_effect=ValueError("Invalid payload")
        ):
            with pytest.raises(ValidationError) as exc_info:
                await store.store(
                    content="test", embedding=mock_embedding(value=0.1), metadata={}
                )

            assert "Invalid memory payload" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_store_connection_error(self):
        """Test store ConnectionError handling (lines 89-92)."""
        config = ServerConfig(qdrant_url="http://localhost:6333")
        store = QdrantMemoryStore(config, use_pool=False)
        store.client = MagicMock()
        store.client.upsert = MagicMock(side_effect=ConnectionError("Connection lost"))

        with pytest.raises(StorageError) as exc_info:
            await store.store(
                content="test",
                embedding=mock_embedding(value=0.1),
                metadata={
                    "category": MemoryCategory.FACT.value,
                    "context_level": ContextLevel.PROJECT_CONTEXT.value,
                    "scope": MemoryScope.GLOBAL.value,
                },
            )

        assert "Failed to connect to Qdrant" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_store_generic_error(self):
        """Test store generic Exception handling (lines 93-96)."""
        config = ServerConfig(qdrant_url="http://localhost:6333")
        store = QdrantMemoryStore(config, use_pool=False)
        store.client = MagicMock()
        store.client.upsert = MagicMock(side_effect=RuntimeError("Unknown error"))

        with pytest.raises(StorageError) as exc_info:
            await store.store(
                content="test",
                embedding=mock_embedding(value=0.1),
                metadata={
                    "category": MemoryCategory.FACT.value,
                    "context_level": ContextLevel.PROJECT_CONTEXT.value,
                    "scope": MemoryScope.GLOBAL.value,
                },
            )

        assert "Failed to store memory" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_retrieve_returns_empty_list_on_invalid_payload(self):
        """Test retrieve ValueError when parsing payload (lines 138-140)."""
        config = ServerConfig(qdrant_url="http://localhost:6333")
        store = QdrantMemoryStore(config, use_pool=False)
        store.client = MagicMock()

        # Mock search response with invalid payload
        mock_hit = MagicMock()
        mock_hit.payload = {"invalid": "data"}  # Missing required fields
        mock_hit.score = 0.95

        # Mock query_points response
        mock_response = MagicMock()
        mock_response.points = [mock_hit]
        store.client.query_points = MagicMock(return_value=mock_response)

        # Should handle ValueError and skip the bad result
        results = await store.retrieve(mock_embedding(value=0.1))

        # Should return empty list since the only result was invalid
        assert results == []

    @pytest.mark.asyncio
    async def test_retrieve_raises_retrieval_error_on_connection_failure(self):
        """Test retrieve ConnectionError handling (lines 145-147)."""
        config = ServerConfig(qdrant_url="http://localhost:6333")
        store = QdrantMemoryStore(config, use_pool=False)
        store.client = MagicMock()
        store.client.query_points = MagicMock(
            side_effect=ConnectionError("Connection lost")
        )

        with pytest.raises(RetrievalError) as exc_info:
            await store.retrieve(mock_embedding(value=0.1))

        assert "Failed to connect to Qdrant" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_retrieve_raises_retrieval_error_on_invalid_filter(self):
        """Test retrieve ValueError handling (lines 148-150)."""
        from src.core.models import SearchFilters, MemoryCategory

        config = ServerConfig(qdrant_url="http://localhost:6333")
        store = QdrantMemoryStore(config, use_pool=False)
        store.client = MagicMock()

        # Mock _build_filter to raise ValueError
        with patch.object(
            store, "_build_filter", side_effect=ValueError("Invalid filter")
        ):
            with pytest.raises(RetrievalError) as exc_info:
                # Pass filters to trigger _build_filter call
                filters = SearchFilters(category=MemoryCategory.FACT)
                await store.retrieve(mock_embedding(value=0.1), filters=filters)

            assert "Invalid search parameters" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_retrieve_raises_retrieval_error_on_runtime_error(self):
        """Test retrieve generic Exception handling (lines 151-153)."""
        config = ServerConfig(qdrant_url="http://localhost:6333")
        store = QdrantMemoryStore(config, use_pool=False)
        store.client = MagicMock()
        store.client.query_points = MagicMock(side_effect=RuntimeError("Unknown error"))

        with pytest.raises(RetrievalError) as exc_info:
            await store.retrieve(mock_embedding(value=0.1))

        assert "Failed to retrieve memories" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_delete_auto_initialize(self):
        """Test delete auto-initializes if client is None (line 158)."""
        config = ServerConfig(qdrant_url="http://localhost:6333")
        store = QdrantMemoryStore(config, use_pool=False)

        assert store.client is None

        with patch.object(store, "initialize", new_callable=AsyncMock) as mock_init:
            mock_client = MagicMock()

            async def init_side_effect():
                store.client = mock_client

            mock_init.side_effect = init_side_effect

            # Mock delete response
            mock_result = MagicMock()
            mock_result.status = "completed"
            mock_client.delete = MagicMock(return_value=mock_result)

            await store.delete("test-id")

            mock_init.assert_called_once()
            # Behavior: client should now be set
            assert store.client is not None
            assert store.client == mock_client
            # Verify delete was actually called on the client
            mock_client.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_raises_storage_error_on_runtime_error(self):
        """Test delete error handling (lines 171-172)."""
        config = ServerConfig(qdrant_url="http://localhost:6333")
        store = QdrantMemoryStore(config, use_pool=False)
        store.client = MagicMock()
        store.client.delete = MagicMock(side_effect=RuntimeError("Delete failed"))

        with pytest.raises(StorageError) as exc_info:
            await store.delete("test-id")

        assert "Failed to delete memory" in str(exc_info.value)


class TestQdrantStoreEdgeCases:
    """Additional edge cases for qdrant_store."""

    @pytest.mark.asyncio
    async def test_batch_store_auto_initialize(self):
        """Test batch_store auto-initializes if needed."""
        config = ServerConfig(qdrant_url="http://localhost:6333")
        store = QdrantMemoryStore(config, use_pool=False)

        assert store.client is None

        with patch.object(store, "initialize", new_callable=AsyncMock) as mock_init:
            mock_client = MagicMock()

            async def init_side_effect():
                store.client = mock_client

            mock_init.side_effect = init_side_effect
            mock_client.upsert = MagicMock()

            items = [
                (
                    "test",
                    mock_embedding(value=0.1),
                    {
                        "category": MemoryCategory.FACT.value,
                        "context_level": ContextLevel.PROJECT_CONTEXT.value,
                        "scope": MemoryScope.GLOBAL.value,
                    },
                )
            ]

            await store.batch_store(items)

            mock_init.assert_called_once()
            # Behavior: client should now be set
            assert store.client is not None
            assert store.client == mock_client
            # Verify batch upsert was called
            mock_client.upsert.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_by_id_auto_initialize(self):
        """Test get_by_id auto-initializes if needed."""
        config = ServerConfig(qdrant_url="http://localhost:6333")
        store = QdrantMemoryStore(config, use_pool=False)

        assert store.client is None

        with patch.object(store, "initialize", new_callable=AsyncMock) as mock_init:
            mock_client = MagicMock()

            async def init_side_effect():
                store.client = mock_client

            mock_init.side_effect = init_side_effect
            mock_client.retrieve = MagicMock(return_value=[])

            result = await store.get_by_id("test-id")

            mock_init.assert_called_once()
            # Behavior: client should now be set
            assert store.client is not None
            assert store.client == mock_client
            # Verify retrieve was called
            mock_client.retrieve.assert_called_once()
            # Verify return value when no results
            assert result is None

    @pytest.mark.asyncio
    async def test_update_auto_initialize(self):
        """Test update auto-initializes if needed."""
        config = ServerConfig(qdrant_url="http://localhost:6333")
        store = QdrantMemoryStore(config, use_pool=False)

        assert store.client is None

        with patch.object(store, "initialize", new_callable=AsyncMock) as mock_init:
            mock_client = MagicMock()

            async def init_side_effect():
                store.client = mock_client

            mock_init.side_effect = init_side_effect

            # Mock get_by_id to return None (not found)
            with patch.object(
                store, "get_by_id", new_callable=AsyncMock, return_value=None
            ):
                result = await store.update("test-id", {"importance": 0.9})

            mock_init.assert_called_once()
            # Behavior: client should now be set
            assert store.client is not None
            assert store.client == mock_client
            # Verify return value when item not found
            assert result is False
