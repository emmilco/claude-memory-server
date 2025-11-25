"""Tests for graceful degradation functionality."""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from src.core.degradation_warnings import (
    DegradationTracker,
    DegradationWarning,
    get_degradation_tracker,
    add_degradation_warning,
    has_degradations,
    get_degradation_summary,
)
from src.store import create_memory_store
from src.config import ServerConfig


class TestDegradationWarning:
    """Tests for DegradationWarning dataclass."""

    def test_degradation_warning_creation(self):
        """Test creating a degradation warning."""
        warning = DegradationWarning(
            component="Test Component",
            message="Test message",
            upgrade_path="Test upgrade",
            performance_impact="10x slower",
        )

        assert warning.component == "Test Component"
        assert warning.message == "Test message"
        assert warning.upgrade_path == "Test upgrade"
        assert warning.performance_impact == "10x slower"
        assert warning.timestamp is not None

    def test_degradation_warning_to_dict(self):
        """Test converting warning to dictionary."""
        warning = DegradationWarning(
            component="Test",
            message="Message",
            upgrade_path="Upgrade",
            performance_impact="Impact",
        )

        warning_dict = warning.to_dict()

        assert warning_dict["component"] == "Test"
        assert warning_dict["message"] == "Message"
        assert warning_dict["upgrade_path"] == "Upgrade"
        assert warning_dict["performance_impact"] == "Impact"
        assert "timestamp" in warning_dict


class TestDegradationTracker:
    """Tests for DegradationTracker."""

    def test_tracker_initialization(self):
        """Test tracker starts empty."""
        tracker = DegradationTracker()

        assert len(tracker.warnings) == 0
        assert not tracker.has_degradations()

    def test_add_warning(self):
        """Test adding a warning."""
        tracker = DegradationTracker()

        tracker.add_warning(
            component="Qdrant",
            message="Unavailable",
            upgrade_path="docker-compose up",
            performance_impact="3x slower",
        )

        assert tracker.has_degradations()
        assert len(tracker.warnings) == 1
        assert tracker.warnings[0].component == "Qdrant"

    def test_prevent_duplicate_warnings(self):
        """Test that duplicate warnings are not added."""
        tracker = DegradationTracker()

        # Add same warning twice
        tracker.add_warning("Qdrant", "Unavailable", "upgrade", "impact")
        tracker.add_warning("Qdrant", "Unavailable", "upgrade", "impact")

        assert len(tracker.warnings) == 1  # Should only have one

    def test_get_summary_empty(self):
        """Test summary when no degradations."""
        tracker = DegradationTracker()

        summary = tracker.get_summary()

        assert "All components running at full performance" in summary

    def test_get_summary_with_warnings(self):
        """Test summary with warnings."""
        tracker = DegradationTracker()

        tracker.add_warning(
            "Qdrant", "Unavailable", "docker-compose up", "3x slower"
        )
        tracker.add_warning(
            "Rust Parser", "Not built", "maturin develop", "10x slower"
        )

        summary = tracker.get_summary()

        assert "degraded mode" in summary
        assert "Qdrant" in summary
        assert "Rust Parser" in summary
        assert "3x slower" in summary
        assert "10x slower" in summary

    def test_get_warnings_list(self):
        """Test getting warnings as list of dicts."""
        tracker = DegradationTracker()

        tracker.add_warning("Test", "Message", "Upgrade", "Impact")

        warnings_list = tracker.get_warnings_list()

        assert len(warnings_list) == 1
        assert isinstance(warnings_list[0], dict)
        assert warnings_list[0]["component"] == "Test"

    def test_clear(self):
        """Test clearing all warnings."""
        tracker = DegradationTracker()

        tracker.add_warning("Test", "Message", "Upgrade", "Impact")
        assert tracker.has_degradations()

        tracker.clear()

        assert not tracker.has_degradations()
        assert len(tracker.warnings) == 0


class TestDegradationGlobalFunctions:
    """Tests for global degradation tracking functions."""

    def setup_method(self):
        """Reset singleton before each test for isolation."""
        DegradationTracker.reset_instance()

    def teardown_method(self):
        """Reset singleton after each test for cleanup."""
        DegradationTracker.reset_instance()

    def test_get_degradation_tracker_singleton(self):
        """Test global tracker is a singleton."""
        tracker1 = get_degradation_tracker()
        tracker2 = get_degradation_tracker()

        assert tracker1 is tracker2

    def test_class_based_singleton(self):
        """Test class-based singleton pattern."""
        tracker1 = DegradationTracker.get_instance()
        tracker2 = DegradationTracker.get_instance()

        assert tracker1 is tracker2

    def test_reset_instance_for_test_isolation(self):
        """Test that reset_instance provides test isolation."""
        # Add warning to first instance
        tracker1 = DegradationTracker.get_instance()
        tracker1.add_warning("Test", "Message", "Upgrade", "Impact")
        assert tracker1.has_degradations()

        # Reset singleton
        DegradationTracker.reset_instance()

        # New instance should be clean
        tracker2 = DegradationTracker.get_instance()
        assert not tracker2.has_degradations()
        assert tracker1 is not tracker2  # Different instances

    def test_add_degradation_warning_global(self):
        """Test adding warning via global function."""
        add_degradation_warning("Test", "Message", "Upgrade", "Impact")

        assert has_degradations()
        assert "Test" in get_degradation_summary()


class TestStoreCreation:
    """Tests for store creation (REF-010: fallback removed, Qdrant required)."""

    def test_qdrant_connection_error_fail_fast(self):
        """Test that Qdrant connection errors fail fast with clear message."""
        config = ServerConfig(
            storage_backend="qdrant",
        )

        # Mock Qdrant to raise connection error
        with patch("src.store.qdrant_store.QdrantMemoryStore") as mock_qdrant:
            mock_qdrant.side_effect = ConnectionError("Qdrant not available")

            # Should raise ConnectionError with helpful message
            with pytest.raises(ConnectionError) as exc_info:
                create_memory_store(config=config)

            # Check error message contains helpful instructions
            error_msg = str(exc_info.value)
            assert "Failed to connect to Qdrant" in error_msg
            assert "docker-compose up -d" in error_msg
            assert "curl" in error_msg  # Health check suggestion

    # SQLite support removed in REF-010 - test removed
    # def test_sqlite_deprecated_warning(self):
    #     """Test that SQLite shows deprecation warning."""

    def test_qdrant_success(self):
        """Test that Qdrant works when available."""
        config = ServerConfig(
            storage_backend="qdrant",
        )

        # Mock Qdrant to succeed
        with patch("src.store.qdrant_store.QdrantMemoryStore") as mock_qdrant:
            mock_store = Mock()
            mock_qdrant.return_value = mock_store

            store = create_memory_store(config=config)

            # Got the Qdrant store
            assert store is mock_store
            mock_qdrant.assert_called_once()

    # SQLite support removed in REF-010 - unsupported backend validation now happens at config level
    # def test_unsupported_backend_error(self):
    #     """Test that unsupported backends raise clear error."""
