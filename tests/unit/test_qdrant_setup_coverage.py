"""Targeted tests for qdrant_setup.py uncovered lines."""

import pytest
from unittest.mock import MagicMock, patch
from qdrant_client.models import CollectionInfo, CollectionsResponse, CollectionDescription

from src.config import ServerConfig
from src.store.qdrant_setup import QdrantSetup
from src.core.exceptions import QdrantConnectionError, StorageError


class TestQdrantSetupCoverage:
    """Test uncovered paths in QdrantSetup."""

    def test_config_none_uses_get_config(self):
        """Test that config=None triggers get_config() (lines 34-35)."""
        with patch('src.config.get_config') as mock_get_config:
            mock_config = ServerConfig(qdrant_url="http://localhost:6333")
            mock_get_config.return_value = mock_config

            setup = QdrantSetup(config=None)

            mock_get_config.assert_called_once()
            assert setup.config == mock_config

    def test_connect_failure(self):
        """Test connect error handling (lines 62-63)."""
        config = ServerConfig(qdrant_url="http://invalid:9999")
        setup = QdrantSetup(config)

        with patch('src.store.qdrant_setup.QdrantClient') as mock_client_class:
            mock_client_class.side_effect = ConnectionError("Cannot connect")

            with pytest.raises(QdrantConnectionError):
                setup.connect()

    def test_collection_exists_auto_connect(self):
        """Test collection_exists auto-connects if client is None (line 76)."""
        config = ServerConfig(qdrant_url="http://localhost:6333")
        setup = QdrantSetup(config)

        assert setup.client is None

        with patch.object(setup, 'connect') as mock_connect:
            mock_client = MagicMock()
            setup.client = mock_client

            # Mock get_collections response
            mock_collection = MagicMock()
            mock_collection.name = "test_collection"
            mock_collections = MagicMock()
            mock_collections.collections = [mock_collection]
            mock_client.get_collections.return_value = mock_collections

            # Reset client to None to trigger auto-connect
            setup.client = None

            def connect_side_effect():
                setup.client = mock_client

            mock_connect.side_effect = connect_side_effect

            result = setup.collection_exists()

            mock_connect.assert_called_once()

    def test_collection_exists_error(self):
        """Test collection_exists error handling (lines 81-83)."""
        config = ServerConfig(qdrant_url="http://localhost:6333")
        setup = QdrantSetup(config)
        setup.client = MagicMock()
        setup.client.get_collections.side_effect = RuntimeError("Connection lost")

        result = setup.collection_exists()

        assert result is False

    def test_create_collection_auto_connect(self):
        """Test create_collection auto-connects if client is None (line 96)."""
        config = ServerConfig(qdrant_url="http://localhost:6333")
        setup = QdrantSetup(config)

        assert setup.client is None

        with patch.object(setup, 'connect') as mock_connect:
            with patch.object(setup, 'collection_exists', return_value=False):
                mock_client = MagicMock()
                setup.client = mock_client

                # Reset to trigger auto-connect
                setup.client = None

                def connect_side_effect():
                    setup.client = mock_client

                mock_connect.side_effect = connect_side_effect

                setup.create_collection()

                mock_connect.assert_called_once()

    def test_create_collection_recreate(self):
        """Test create_collection with recreate=True (lines 101-102)."""
        config = ServerConfig(qdrant_url="http://localhost:6333")
        setup = QdrantSetup(config)
        setup.client = MagicMock()

        # Mock collection exists
        with patch.object(setup, 'collection_exists', side_effect=[True, False]):
            setup.create_collection(recreate=True)

            # Should have deleted the collection
            setup.client.delete_collection.assert_called_once_with(setup.collection_name)

    def test_create_collection_already_exists(self):
        """Test create_collection early return if exists (lines 106-107)."""
        config = ServerConfig(qdrant_url="http://localhost:6333")
        setup = QdrantSetup(config)
        setup.client = MagicMock()

        # Mock collection exists
        with patch.object(setup, 'collection_exists', return_value=True):
            setup.create_collection(recreate=False)

            # Should not call create_collection
            setup.client.create_collection.assert_not_called()

    def test_create_collection_error(self):
        """Test create_collection error handling (lines 137-138)."""
        config = ServerConfig(qdrant_url="http://localhost:6333")
        setup = QdrantSetup(config)
        setup.client = MagicMock()

        with patch.object(setup, 'collection_exists', return_value=False):
            setup.client.create_collection.side_effect = RuntimeError("Creation failed")

            with pytest.raises(StorageError) as exc_info:
                setup.create_collection()

            assert "Failed to create collection" in str(exc_info.value)

    def test_create_payload_indices_auto_connect(self):
        """Test create_payload_indices auto-connects if client is None (line 153)."""
        config = ServerConfig(qdrant_url="http://localhost:6333")
        setup = QdrantSetup(config)

        assert setup.client is None

        with patch.object(setup, 'connect') as mock_connect:
            mock_client = MagicMock()

            def connect_side_effect():
                setup.client = mock_client

            mock_connect.side_effect = connect_side_effect

            setup.create_payload_indices()

            mock_connect.assert_called_once()

    def test_create_payload_indices_index_error(self):
        """Test create_payload_indices handles index creation errors (lines 174-176)."""
        config = ServerConfig(qdrant_url="http://localhost:6333")
        setup = QdrantSetup(config)
        setup.client = MagicMock()

        # Mock create_payload_index to raise error (index already exists)
        setup.client.create_payload_index.side_effect = Exception("Index already exists")

        # Should not raise, just log
        setup.create_payload_indices()

        # Should have attempted to create indices
        assert setup.client.create_payload_index.call_count > 0

    def test_create_payload_indices_outer_error(self):
        """Test create_payload_indices outer exception handling (lines 178-179)."""
        config = ServerConfig(qdrant_url="http://localhost:6333")
        setup = QdrantSetup(config)
        setup.client = MagicMock()

        # Make the iteration itself fail
        with patch('src.store.qdrant_setup.PayloadSchemaType', side_effect=RuntimeError("Unexpected error")):
            # Should not raise, just log warning
            setup.create_payload_indices()

    def test_ensure_collection_exists_auto_connect(self):
        """Test ensure_collection_exists auto-connects if client is None (line 188)."""
        config = ServerConfig(qdrant_url="http://localhost:6333")
        setup = QdrantSetup(config)

        assert setup.client is None

        with patch.object(setup, 'connect') as mock_connect:
            with patch.object(setup, 'collection_exists', return_value=True):
                mock_client = MagicMock()

                def connect_side_effect():
                    setup.client = mock_client

                mock_connect.side_effect = connect_side_effect

                setup.ensure_collection_exists()

                mock_connect.assert_called_once()

    def test_get_collection_info_auto_connect(self):
        """Test get_collection_info auto-connects if client is None (line 203)."""
        config = ServerConfig(qdrant_url="http://localhost:6333")
        setup = QdrantSetup(config)

        assert setup.client is None

        with patch.object(setup, 'connect') as mock_connect:
            mock_client = MagicMock()

            def connect_side_effect():
                setup.client = mock_client

            mock_connect.side_effect = connect_side_effect

            # Mock collection info
            mock_collection_info = MagicMock()
            mock_collection_info.vectors_count = 100
            mock_collection_info.points_count = 100
            mock_collection_info.status = "green"
            mock_collection_info.optimizer_status = "ok"
            mock_client.get_collection.return_value = mock_collection_info

            result = setup.get_collection_info()

            mock_connect.assert_called_once()
            assert result["vectors_count"] == 100

    def test_get_collection_info_error(self):
        """Test get_collection_info error handling (lines 215-217)."""
        config = ServerConfig(qdrant_url="http://localhost:6333")
        setup = QdrantSetup(config)
        setup.client = MagicMock()
        setup.client.get_collection.side_effect = RuntimeError("Connection lost")

        result = setup.get_collection_info()

        assert result == {}

    def test_health_check_auto_connect(self):
        """Test health_check auto-connects if client is None (line 228)."""
        config = ServerConfig(qdrant_url="http://localhost:6333")
        setup = QdrantSetup(config)

        assert setup.client is None

        with patch.object(setup, 'connect') as mock_connect:
            mock_client = MagicMock()

            def connect_side_effect():
                setup.client = mock_client

            mock_connect.side_effect = connect_side_effect

            # Mock successful health check
            mock_client.get_collections.return_value = MagicMock()

            result = setup.health_check()

            mock_connect.assert_called_once()
            assert result is True

    def test_health_check_error(self):
        """Test health_check error handling (lines 233-235)."""
        config = ServerConfig(qdrant_url="http://localhost:6333")
        setup = QdrantSetup(config)
        setup.client = MagicMock()
        setup.client.get_collections.side_effect = ConnectionError("Connection lost")

        result = setup.health_check()

        assert result is False
