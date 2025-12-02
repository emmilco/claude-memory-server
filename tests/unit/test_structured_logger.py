"""Tests for structured logging module."""

import json
import logging
from io import StringIO
from pathlib import Path
import tempfile
import pytest

from src.log_utils.structured_logger import (
    configure_logging,
    get_logger,
    is_json_logging,
    JSONFormatter,
    StructuredLogger,
)


@pytest.fixture
def reset_logging():
    """Reset logging configuration after each test."""
    # Store original state
    original_logger_class = logging.getLoggerClass()
    original_handlers = logging.root.handlers[:]

    yield

    # Restore original state
    logging.setLoggerClass(original_logger_class)
    logging.root.handlers = original_handlers


@pytest.fixture
def captured_log_stream():
    """Capture log output to a StringIO stream."""
    stream = StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JSONFormatter())

    logger = logging.getLogger("test_logger")
    logger.handlers = [handler]
    logger.setLevel(logging.DEBUG)

    yield stream, logger

    logger.handlers = []


class TestJSONFormatter:
    """Tests for JSONFormatter class."""

    def test_basic_json_formatting(self, captured_log_stream):
        """Test that logs are formatted as valid JSON."""
        stream, logger = captured_log_stream

        logger.info("Test message")
        output = stream.getvalue()

        # Should be valid JSON
        log_data = json.loads(output.strip())

        assert log_data["level"] == "INFO"
        assert log_data["message"] == "Test message"
        assert "timestamp" in log_data
        assert "logger" in log_data

    def test_json_contains_standard_fields(self, captured_log_stream):
        """Test that JSON output contains all standard fields."""
        stream, logger = captured_log_stream

        logger.warning("Warning message")
        output = stream.getvalue()

        log_data = json.loads(output.strip())

        # Check all standard fields present
        assert "timestamp" in log_data
        assert "level" in log_data
        assert "logger" in log_data
        assert "message" in log_data
        assert "module" in log_data
        assert "function" in log_data
        assert "line" in log_data

    def test_json_with_context(self, captured_log_stream):
        """Test JSON formatting with context data."""
        stream, logger = captured_log_stream

        # Log with extra context
        logger.info(
            "Cache hit", extra={"context": {"cache_key": "abc123", "hit_rate": 0.85}}
        )
        output = stream.getvalue()

        log_data = json.loads(output.strip())

        assert "context" in log_data
        assert log_data["context"]["cache_key"] == "abc123"
        assert log_data["context"]["hit_rate"] == 0.85

    def test_json_with_exception(self, captured_log_stream):
        """Test JSON formatting with exception info."""
        stream, logger = captured_log_stream

        try:
            raise ValueError("Test error")
        except ValueError:
            logger.error("Error occurred", exc_info=True)

        output = stream.getvalue()
        log_data = json.loads(output.strip())

        assert "exception" in log_data
        assert "ValueError" in log_data["exception"]
        assert "Test error" in log_data["exception"]


class TestStructuredLogger:
    """Tests for StructuredLogger class."""

    def test_get_logger_returns_structured_logger(self):
        """Test that get_logger returns a StructuredLogger instance."""
        logger = get_logger("test.module")

        assert isinstance(logger, StructuredLogger)
        assert hasattr(logger, "info_ctx")
        assert hasattr(logger, "error_ctx")

    def test_backward_compatibility(self, captured_log_stream):
        """Test that standard logging methods still work."""
        stream, _ = captured_log_stream
        logger = get_logger("test.module")
        logger.handlers = [logging.StreamHandler(stream)]
        logger.handlers[0].setFormatter(JSONFormatter())
        logger.setLevel(logging.DEBUG)  # Ensure all levels are logged

        # Standard logging should work
        logger.info("Standard info message")
        logger.warning("Standard warning")
        logger.error("Standard error")

        output = stream.getvalue()
        lines = [line for line in output.strip().split("\n") if line]

        assert len(lines) == 3
        for line in lines:
            log_data = json.loads(line)
            assert "message" in log_data
            assert "Standard" in log_data["message"]

    def test_info_ctx(self, captured_log_stream):
        """Test info_ctx method with context."""
        stream, _ = captured_log_stream
        logger = get_logger("test.module")
        logger.handlers = [logging.StreamHandler(stream)]
        logger.handlers[0].setFormatter(JSONFormatter())
        logger.setLevel(logging.DEBUG)  # Ensure all levels are logged

        logger.info_ctx("Operation completed", operation="index", duration_ms=150)

        output = stream.getvalue()
        log_data = json.loads(output.strip())

        assert log_data["message"] == "Operation completed"
        assert log_data["context"]["operation"] == "index"
        assert log_data["context"]["duration_ms"] == 150

    def test_error_ctx_with_exception(self, captured_log_stream):
        """Test error_ctx method with exception info."""
        stream, _ = captured_log_stream
        logger = get_logger("test.module")
        logger.handlers = [logging.StreamHandler(stream)]
        logger.handlers[0].setFormatter(JSONFormatter())

        try:
            raise RuntimeError("Test runtime error")
        except RuntimeError:
            logger.error_ctx(
                "Database error", table="embeddings", operation="insert", exc_info=True
            )

        output = stream.getvalue()
        log_data = json.loads(output.strip())

        assert log_data["message"] == "Database error"
        assert log_data["context"]["table"] == "embeddings"
        assert log_data["context"]["operation"] == "insert"
        assert "exception" in log_data
        assert "RuntimeError" in log_data["exception"]

    def test_debug_ctx(self, captured_log_stream):
        """Test debug_ctx method."""
        stream, _ = captured_log_stream
        logger = get_logger("test.module")
        logger.handlers = [logging.StreamHandler(stream)]
        logger.handlers[0].setFormatter(JSONFormatter())
        logger.setLevel(logging.DEBUG)

        logger.debug_ctx("Debug info", cache_key="xyz789", result="miss")

        output = stream.getvalue()
        log_data = json.loads(output.strip())

        assert log_data["level"] == "DEBUG"
        assert log_data["message"] == "Debug info"
        assert log_data["context"]["cache_key"] == "xyz789"

    def test_warning_ctx(self, captured_log_stream):
        """Test warning_ctx method."""
        stream, _ = captured_log_stream
        logger = get_logger("test.module")
        logger.handlers = [logging.StreamHandler(stream)]
        logger.handlers[0].setFormatter(JSONFormatter())

        logger.warning_ctx("High memory usage", usage_mb=1500, threshold_mb=1000)

        output = stream.getvalue()
        log_data = json.loads(output.strip())

        assert log_data["level"] == "WARNING"
        assert log_data["context"]["usage_mb"] == 1500

    def test_critical_ctx(self, captured_log_stream):
        """Test critical_ctx method."""
        stream, _ = captured_log_stream
        logger = get_logger("test.module")
        logger.handlers = [logging.StreamHandler(stream)]
        logger.handlers[0].setFormatter(JSONFormatter())

        logger.critical_ctx("System failure", reason="out_of_memory")

        output = stream.getvalue()
        log_data = json.loads(output.strip())

        assert log_data["level"] == "CRITICAL"
        assert log_data["context"]["reason"] == "out_of_memory"

    def test_context_dict_and_kwargs(self, captured_log_stream):
        """Test mixing context dict and kwargs."""
        stream, _ = captured_log_stream
        # Use unique logger name to avoid cross-test interference in parallel execution
        import uuid

        logger = get_logger(f"test.module.{uuid.uuid4().hex[:8]}")
        logger.handlers = [logging.StreamHandler(stream)]
        logger.handlers[0].setFormatter(JSONFormatter())

        context = {"key1": "value1"}
        logger.info_ctx("Mixed context", context=context, key2="value2")

        output = stream.getvalue()
        log_data = json.loads(output.strip())

        assert log_data["context"]["key1"] == "value1"
        assert log_data["context"]["key2"] == "value2"


class TestConfigureLogging:
    """Tests for configure_logging function."""

    def test_configure_json_logging(self, reset_logging):
        """Test configuring JSON logging."""
        configure_logging(use_json=True, level=logging.DEBUG)

        assert is_json_logging()
        assert logging.root.level == logging.DEBUG
        assert len(logging.root.handlers) > 0

    def test_configure_standard_logging(self, reset_logging):
        """Test configuring standard (non-JSON) logging."""
        configure_logging(use_json=False, level=logging.WARNING)

        assert not is_json_logging()
        assert logging.root.level == logging.WARNING

    def test_configure_with_file(self, reset_logging):
        """Test configuring logging with file output."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".log") as f:
            log_file = Path(f.name)

        try:
            configure_logging(use_json=True, log_file=log_file)

            # Should have both console and file handlers
            assert len(logging.root.handlers) == 2

            # Write a log message
            logger = get_logger("test.file")
            logger.info_ctx("Test message", key="value")

            # Check that file was written
            assert log_file.exists()
            content = log_file.read_text()
            assert len(content) > 0

            # Verify JSON format
            log_data = json.loads(content.strip())
            assert log_data["message"] == "Test message"

        finally:
            # Cleanup
            if log_file.exists():
                log_file.unlink()

    def test_logger_class_changed(self, reset_logging):
        """Test that configure_logging sets StructuredLogger as the logger class."""
        configure_logging(use_json=True)

        logger = logging.getLogger("test.class")
        assert isinstance(logger, StructuredLogger)


class TestIntegration:
    """Integration tests for structured logging."""

    def test_multiple_loggers_same_format(self, reset_logging):
        """Test that multiple loggers use the same JSON format."""
        stream = StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(JSONFormatter())

        configure_logging(use_json=True)
        logging.root.handlers = [handler]

        logger1 = get_logger("module1")
        logger2 = get_logger("module2")

        logger1.info_ctx("Message from module1", value=1)
        logger2.info_ctx("Message from module2", value=2)

        output = stream.getvalue()
        lines = [line for line in output.strip().split("\n") if line]

        assert len(lines) == 2

        log1 = json.loads(lines[0])
        log2 = json.loads(lines[1])

        assert log1["logger"] == "module1"
        assert log2["logger"] == "module2"
        assert log1["context"]["value"] == 1
        assert log2["context"]["value"] == 2

    def test_performance_overhead(self, reset_logging):
        """Test that JSON formatting has minimal performance overhead."""
        import time

        stream = StringIO()
        handler = logging.StreamHandler(stream)

        # Measure JSON formatting
        handler.setFormatter(JSONFormatter())
        logger = get_logger("perf.test")
        logger.handlers = [handler]

        start = time.time()
        for i in range(1000):
            logger.info_ctx("Performance test", iteration=i, value=i * 2)
        json_time = time.time() - start

        # Should complete 1000 logs in reasonable time (< 500ms)
        assert json_time < 0.5, f"JSON logging too slow: {json_time:.3f}s"

    def test_no_context_fields(self, captured_log_stream):
        """Test logging without any context fields."""
        stream, _ = captured_log_stream
        # Use unique logger name to avoid cross-test interference in parallel execution
        import uuid

        logger = get_logger(f"test.no_context.{uuid.uuid4().hex[:8]}")
        logger.handlers = [logging.StreamHandler(stream)]
        logger.handlers[0].setFormatter(JSONFormatter())

        logger.info_ctx("Message without context")

        output = stream.getvalue()
        log_data = json.loads(output.strip())

        assert log_data["message"] == "Message without context"
        # Context field should not be present if empty
        assert "context" not in log_data or not log_data.get("context")
