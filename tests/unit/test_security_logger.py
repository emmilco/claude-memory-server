"""Comprehensive tests for security_logger.py - TEST-007 Phase 1.1

Target Coverage: 0% → 85%+
Test Count: 30 tests
"""

import pytest
import json
import logging
import tempfile
from pathlib import Path
from datetime import datetime

from src.core.security_logger import (
    SecurityLogger,
    SecurityEventType,
    get_security_logger,
    set_security_logger,
)


class TestSecurityLoggerInitialization:
    """Tests for SecurityLogger initialization and configuration."""

    def test_initialization_default_dir(self):
        """Test logger initializes with default directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = SecurityLogger(log_dir=tmpdir)

            assert logger.log_dir == Path(tmpdir).expanduser()
            assert logger.log_file == Path(tmpdir) / "security.log"
            assert logger.logger is not None
            assert logger.logger.level == logging.INFO

    def test_initialization_creates_directory(self):
        """Test logger creates log directory if it doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir) / "subdir" / "logs"
            logger = SecurityLogger(log_dir=str(log_dir))

            assert log_dir.exists()
            assert logger.log_file == log_dir / "security.log"

    def test_initialization_expands_tilde(self):
        """Test logger expands ~ in log directory path."""
        logger = SecurityLogger(log_dir="~/test-security-logs")

        assert "~" not in str(logger.log_dir)
        assert logger.log_dir.is_absolute()

    def test_logger_handlers_configured(self):
        """Test file and console handlers are properly configured."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = SecurityLogger(log_dir=tmpdir)

            # Should have 2 handlers: file and console
            assert len(logger.logger.handlers) == 2

            # Find file and console handlers
            file_handler = None
            console_handler = None
            for handler in logger.logger.handlers:
                if isinstance(handler, logging.FileHandler):
                    file_handler = handler
                elif isinstance(handler, logging.StreamHandler):
                    console_handler = handler

            assert file_handler is not None
            assert console_handler is not None
            assert file_handler.level == logging.INFO
            assert console_handler.level == logging.WARNING

    def test_logger_does_not_propagate(self):
        """Test security logger doesn't propagate to root logger."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = SecurityLogger(log_dir=tmpdir)

            assert logger.logger.propagate is False


class TestSecurityEventLogging:
    """Tests for individual security event logging methods."""

    @pytest.fixture
    def temp_logger(self):
        """Create a SecurityLogger with temporary directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = SecurityLogger(log_dir=tmpdir)
            yield logger

    def test_log_validation_failure(self, temp_logger):
        """Test validation failure events are logged with correct format."""
        temp_logger.log_validation_failure(
            endpoint="/api/store",
            error="Invalid category",
            payload_preview="test payload",
        )

        # Read log file
        with open(temp_logger.log_file, "r") as f:
            log_line = f.read().strip()

        # Extract JSON part (after timestamp and level)
        json_part = log_line.split("|")[-1].strip()
        event = json.loads(json_part)

        assert event["event_type"] == "validation_failure"
        assert event["message"] == "Validation failed on /api/store: Invalid category"
        assert event["details"]["endpoint"] == "/api/store"
        assert event["details"]["error"] == "Invalid category"
        assert event["details"]["payload_preview"] == "test payload"

    def test_log_validation_failure_without_payload(self, temp_logger):
        """Test validation failure without payload preview."""
        temp_logger.log_validation_failure(
            endpoint="/api/retrieve", error="Missing query parameter"
        )

        with open(temp_logger.log_file, "r") as f:
            log_line = f.read().strip()

        json_part = log_line.split("|")[-1].strip()
        event = json.loads(json_part)

        assert event["event_type"] == "validation_failure"
        assert "payload_preview" not in event["details"]

    def test_log_injection_attempt(self, temp_logger):
        """Test injection attempts logged as ERROR level with pattern."""
        temp_logger.log_injection_attempt(
            pattern_type="SQL",
            pattern="DROP TABLE",
            content_preview="'; DROP TABLE users; --",
            endpoint="/api/query",
        )

        with open(temp_logger.log_file, "r") as f:
            log_line = f.read().strip()

        # Should be ERROR level
        assert "ERROR" in log_line

        json_part = log_line.split("|")[-1].strip()
        event = json.loads(json_part)

        assert event["event_type"] == "injection_attempt"
        assert event["message"] == "SQL injection attempt detected: DROP TABLE"
        assert event["details"]["pattern_type"] == "SQL"
        assert event["details"]["pattern"] == "DROP TABLE"
        assert event["details"]["endpoint"] == "/api/query"

    def test_log_injection_attempt_without_endpoint(self, temp_logger):
        """Test injection attempt logging without endpoint."""
        temp_logger.log_injection_attempt(
            pattern_type="prompt",
            pattern="Ignore instructions",
            content_preview="Ignore all previous instructions and...",
        )

        with open(temp_logger.log_file, "r") as f:
            log_line = f.read().strip()

        json_part = log_line.split("|")[-1].strip()
        event = json.loads(json_part)

        assert "endpoint" not in event["details"]

    def test_log_readonly_violation(self, temp_logger):
        """Test read-only violations logged with operation details."""
        temp_logger.log_readonly_violation(
            operation="store_memory",
            endpoint="/api/store",
            details={"user": "test_user"},
        )

        with open(temp_logger.log_file, "r") as f:
            log_line = f.read().strip()

        json_part = log_line.split("|")[-1].strip()
        event = json.loads(json_part)

        assert event["event_type"] == "readonly_violation"
        assert (
            event["message"]
            == "Read-only mode violation: store_memory attempted on /api/store"
        )
        assert event["details"]["operation"] == "store_memory"
        assert event["details"]["endpoint"] == "/api/store"
        assert event["details"]["user"] == "test_user"

    def test_log_suspicious_pattern(self, temp_logger):
        """Test suspicious pattern detection logged."""
        temp_logger.log_suspicious_pattern(
            pattern="base64_encoded_data",
            content_preview="YmFzZTY0IGVuY29kZWQ=",
            reason="Unusual base64 encoding in user input",
        )

        with open(temp_logger.log_file, "r") as f:
            log_line = f.read().strip()

        json_part = log_line.split("|")[-1].strip()
        event = json.loads(json_part)

        assert event["event_type"] == "suspicious_pattern"
        assert event["details"]["pattern"] == "base64_encoded_data"
        assert event["details"]["reason"] == "Unusual base64 encoding in user input"

    def test_log_invalid_input(self, temp_logger):
        """Test invalid input logged with field and value preview."""
        temp_logger.log_invalid_input(
            field="importance",
            value_preview="-5",
            error="Importance must be between 0 and 10",
        )

        with open(temp_logger.log_file, "r") as f:
            log_line = f.read().strip()

        # Should be INFO level (not WARNING)
        assert "INFO" in log_line

        json_part = log_line.split("|")[-1].strip()
        event = json.loads(json_part)

        assert event["event_type"] == "invalid_input"
        assert (
            event["message"]
            == "Invalid input in field 'importance': Importance must be between 0 and 10"
        )
        assert event["details"]["field"] == "importance"
        assert event["details"]["value_preview"] == "-5"

    def test_log_size_limit_exceeded(self, temp_logger):
        """Test size limit violations logged with actual/max sizes."""
        temp_logger.log_size_limit_exceeded(
            actual_size=1048576, max_size=524288, content_type="metadata"
        )

        with open(temp_logger.log_file, "r") as f:
            log_line = f.read().strip()

        json_part = log_line.split("|")[-1].strip()
        event = json.loads(json_part)

        assert event["event_type"] == "size_limit_exceeded"
        assert event["message"] == "Size limit exceeded for metadata: 1048576 > 524288"
        assert event["details"]["actual_size"] == 1048576
        assert event["details"]["max_size"] == 524288
        assert event["details"]["content_type"] == "metadata"

    def test_log_unauthorized_access(self, temp_logger):
        """Test unauthorized access attempts logged as ERROR."""
        temp_logger.log_unauthorized_access(
            resource="/admin/settings", reason="User not authenticated"
        )

        with open(temp_logger.log_file, "r") as f:
            log_line = f.read().strip()

        # Should be ERROR level
        assert "ERROR" in log_line

        json_part = log_line.split("|")[-1].strip()
        event = json.loads(json_part)

        assert event["event_type"] == "unauthorized_access"
        assert (
            event["message"]
            == "Unauthorized access to /admin/settings: User not authenticated"
        )


class TestEventTruncation:
    """Tests for content truncation to prevent log spam."""

    @pytest.fixture
    def temp_logger(self):
        """Create a SecurityLogger with temporary directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = SecurityLogger(log_dir=tmpdir)
            yield logger

    def test_validation_payload_truncated_to_200_chars(self, temp_logger):
        """Test payload preview truncated to 200 chars."""
        long_payload = "A" * 300
        temp_logger.log_validation_failure(
            endpoint="/test", error="Test error", payload_preview=long_payload
        )

        with open(temp_logger.log_file, "r") as f:
            log_line = f.read().strip()

        json_part = log_line.split("|")[-1].strip()
        event = json.loads(json_part)

        assert len(event["details"]["payload_preview"]) == 200

    def test_injection_content_truncated_to_200_chars(self, temp_logger):
        """Test injection content preview truncated to 200 chars."""
        long_content = "B" * 300
        temp_logger.log_injection_attempt(
            pattern_type="test", pattern="test", content_preview=long_content
        )

        with open(temp_logger.log_file, "r") as f:
            log_line = f.read().strip()

        json_part = log_line.split("|")[-1].strip()
        event = json.loads(json_part)

        assert len(event["details"]["content_preview"]) == 200

    def test_suspicious_pattern_truncated_to_200_chars(self, temp_logger):
        """Test suspicious pattern content truncated to 200 chars."""
        long_content = "C" * 300
        temp_logger.log_suspicious_pattern(
            pattern="test", content_preview=long_content, reason="test"
        )

        with open(temp_logger.log_file, "r") as f:
            log_line = f.read().strip()

        json_part = log_line.split("|")[-1].strip()
        event = json.loads(json_part)

        assert len(event["details"]["content_preview"]) == 200

    def test_invalid_input_value_truncated_to_100_chars(self, temp_logger):
        """Test invalid input value preview truncated to 100 chars."""
        long_value = "D" * 150
        temp_logger.log_invalid_input(
            field="test", value_preview=long_value, error="test"
        )

        with open(temp_logger.log_file, "r") as f:
            log_line = f.read().strip()

        json_part = log_line.split("|")[-1].strip()
        event = json.loads(json_part)

        assert len(event["details"]["value_preview"]) == 100


class TestLogRetrieval:
    """Tests for retrieving recent security events."""

    @pytest.fixture
    def temp_logger(self):
        """Create a SecurityLogger with temporary directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = SecurityLogger(log_dir=tmpdir)
            yield logger

    def test_get_recent_events_returns_last_n(self, temp_logger):
        """Test get_recent_events returns last N events."""
        # Log 5 events
        for i in range(5):
            temp_logger.log_invalid_input(f"field{i}", f"value{i}", f"error{i}")

        events = temp_logger.get_recent_events(n=3)

        assert len(events) == 3
        # Should be the last 3 events
        assert "field2" in events[0] or "field3" in events[0] or "field4" in events[0]

    def test_get_recent_events_empty_log(self, temp_logger):
        """Test get_recent_events returns empty list when no log exists."""
        events = temp_logger.get_recent_events()

        assert events == []

    def test_get_recent_events_handles_file_read_error(self, temp_logger):
        """Test get_recent_events handles file read errors gracefully."""
        # Create log file then make it unreadable
        temp_logger.log_invalid_input("test", "value", "error")
        temp_logger.log_file.chmod(0o000)

        try:
            events = temp_logger.get_recent_events()
            assert events == []
        finally:
            # Restore permissions for cleanup
            temp_logger.log_file.chmod(0o644)


class TestLogStatistics:
    """Tests for get_stats method."""

    @pytest.fixture
    def temp_logger(self):
        """Create a SecurityLogger with temporary directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = SecurityLogger(log_dir=tmpdir)
            yield logger

    def test_get_stats_with_empty_log(self, temp_logger):
        """Test get_stats returns valid structure for empty log file."""
        stats = temp_logger.get_stats()

        assert "log_file" in stats
        assert stats["log_exists"] is True  # File created on initialization
        assert stats["log_size_bytes"] == 0  # But empty
        assert stats["event_counts"] == {}

    def test_get_stats_computes_file_size(self, temp_logger):
        """Test stats computation includes file size."""
        temp_logger.log_invalid_input("test", "value", "error")

        stats = temp_logger.get_stats()

        assert stats["log_exists"] is True
        assert stats["log_size_bytes"] > 0

    def test_get_stats_counts_events_by_type(self, temp_logger):
        """Test event_counts dict correctly aggregates by event_type."""
        # Log different types of events
        temp_logger.log_invalid_input("field1", "value1", "error1")
        temp_logger.log_invalid_input("field2", "value2", "error2")
        temp_logger.log_validation_failure("/test", "error")
        temp_logger.log_injection_attempt("SQL", "DROP", "test content")

        stats = temp_logger.get_stats()

        assert stats["event_counts"]["invalid_input"] == 2
        assert stats["event_counts"]["validation_failure"] == 1
        assert stats["event_counts"]["injection_attempt"] == 1

    def test_get_stats_handles_malformed_lines(self, temp_logger):
        """Test stats computation skips non-JSON lines gracefully."""
        # Write a malformed line directly to log file
        with open(temp_logger.log_file, "w") as f:
            f.write("This is not a valid log line\n")
            f.write("2025-01-15 10:00:00 | INFO | Not JSON either\n")

        # Log a proper event
        temp_logger.log_invalid_input("test", "value", "error")

        stats = temp_logger.get_stats()

        # Should count only the valid event
        assert stats["event_counts"]["invalid_input"] == 1

    def test_get_stats_handles_file_read_error(self, temp_logger):
        """Test get_stats handles file read errors gracefully."""
        # Create log then make unreadable
        temp_logger.log_invalid_input("test", "value", "error")
        temp_logger.log_file.chmod(0o000)

        try:
            stats = temp_logger.get_stats()
            # Should return basic stats without event_counts
            assert "log_file" in stats
        finally:
            # Restore permissions
            temp_logger.log_file.chmod(0o644)


class TestJSONEventFormat:
    """Tests for JSON event format validation."""

    @pytest.fixture
    def temp_logger(self):
        """Create a SecurityLogger with temporary directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = SecurityLogger(log_dir=tmpdir)
            yield logger

    def test_all_events_have_timestamp(self, temp_logger):
        """Test all events logged in valid JSON format with timestamp."""
        temp_logger.log_invalid_input("test", "value", "error")

        with open(temp_logger.log_file, "r") as f:
            log_line = f.read().strip()

        json_part = log_line.split("|")[-1].strip()
        event = json.loads(json_part)

        assert "timestamp" in event
        # Verify it's ISO format
        datetime.fromisoformat(event["timestamp"].replace("Z", "+00:00"))

    def test_all_events_have_event_type(self, temp_logger):
        """Test all events have event_type field."""
        temp_logger.log_validation_failure("/test", "error")

        with open(temp_logger.log_file, "r") as f:
            log_line = f.read().strip()

        json_part = log_line.split("|")[-1].strip()
        event = json.loads(json_part)

        assert "event_type" in event
        assert event["event_type"] in [e.value for e in SecurityEventType]

    def test_all_events_have_message(self, temp_logger):
        """Test all events have human-readable message."""
        temp_logger.log_suspicious_pattern("test", "content", "reason")

        with open(temp_logger.log_file, "r") as f:
            log_line = f.read().strip()

        json_part = log_line.split("|")[-1].strip()
        event = json.loads(json_part)

        assert "message" in event
        assert isinstance(event["message"], str)
        assert len(event["message"]) > 0


class TestGlobalSecurityLogger:
    """Tests for global singleton pattern."""

    def test_get_security_logger_returns_instance(self):
        """Test get_security_logger() returns SecurityLogger instance."""
        logger = get_security_logger()

        assert isinstance(logger, SecurityLogger)

    def test_get_security_logger_returns_same_instance(self):
        """Test get_security_logger() returns same instance (singleton)."""
        logger1 = get_security_logger()
        logger2 = get_security_logger()

        assert logger1 is logger2

    def test_set_security_logger_allows_dependency_injection(self):
        """Test set_security_logger() allows dependency injection for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            custom_logger = SecurityLogger(log_dir=tmpdir)
            set_security_logger(custom_logger)

            retrieved_logger = get_security_logger()

            assert retrieved_logger is custom_logger

            # Reset global state
            set_security_logger(None)
