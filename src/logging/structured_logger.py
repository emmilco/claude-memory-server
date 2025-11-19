"""Structured logging with JSON output for better log aggregation and searchability."""

import json
import logging
import sys
from datetime import datetime, UTC
from typing import Any, Dict, Optional
from pathlib import Path


class JSONFormatter(logging.Formatter):
    """
    Custom JSON formatter for structured logging.

    Formats log records as JSON with standard fields for easy parsing and aggregation.
    Supports both standard logging and structured logging with context data.
    """

    def format(self, record: logging.LogRecord) -> str:
        """
        Format a log record as JSON.

        Args:
            record: The log record to format.

        Returns:
            str: JSON-formatted log string.
        """
        # Build standard fields
        log_data = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add context if provided via 'extra' parameter
        if hasattr(record, "context") and record.context:
            log_data["context"] = record.context

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add stack trace if present
        if record.stack_info:
            log_data["stack_trace"] = record.stack_info

        return json.dumps(log_data)


class StructuredLogger(logging.Logger):
    """
    Extended logger with convenience methods for structured logging.

    Provides methods like info_ctx(), error_ctx() that accept context as kwargs.
    """

    def _log_with_context(
        self,
        level: int,
        msg: str,
        context: Optional[Dict[str, Any]] = None,
        exc_info: Any = None,
        **kwargs
    ) -> None:
        """
        Internal method to log with context.

        Args:
            level: Log level (logging.INFO, logging.ERROR, etc.)
            msg: Log message
            context: Dictionary of context fields
            exc_info: Exception info
            **kwargs: Additional context fields
        """
        # Merge context dict and kwargs
        final_context = {}
        if context:
            final_context.update(context)
        if kwargs:
            final_context.update(kwargs)

        # Use 'extra' to pass context to formatter
        extra = {"context": final_context} if final_context else {}

        self.log(level, msg, exc_info=exc_info, extra=extra)

    def debug_ctx(self, msg: str, context: Optional[Dict[str, Any]] = None, **kwargs) -> None:
        """
        Log debug message with context.

        Args:
            msg: Log message
            context: Dictionary of context fields
            **kwargs: Additional context fields as keyword arguments

        Example:
            logger.debug_ctx("Cache operation", operation="get", cache_key="abc123", result="hit")
        """
        self._log_with_context(logging.DEBUG, msg, context, **kwargs)

    def info_ctx(self, msg: str, context: Optional[Dict[str, Any]] = None, **kwargs) -> None:
        """
        Log info message with context.

        Args:
            msg: Log message
            context: Dictionary of context fields
            **kwargs: Additional context fields as keyword arguments

        Example:
            logger.info_ctx("Embedding generated", model="all-MiniLM-L6-v2", dimension=384)
        """
        self._log_with_context(logging.INFO, msg, context, **kwargs)

    def warning_ctx(self, msg: str, context: Optional[Dict[str, Any]] = None, **kwargs) -> None:
        """
        Log warning message with context.

        Args:
            msg: Log message
            context: Dictionary of context fields
            **kwargs: Additional context fields as keyword arguments

        Example:
            logger.warning_ctx("Cache miss", cache_key="abc123", hit_rate=0.65)
        """
        self._log_with_context(logging.WARNING, msg, context, **kwargs)

    def error_ctx(
        self,
        msg: str,
        context: Optional[Dict[str, Any]] = None,
        exc_info: Any = None,
        **kwargs
    ) -> None:
        """
        Log error message with context.

        Args:
            msg: Log message
            context: Dictionary of context fields
            exc_info: Exception info (True, exception instance, or exc_info tuple)
            **kwargs: Additional context fields as keyword arguments

        Example:
            logger.error_ctx("Database error", operation="insert", table="embeddings", exc_info=True)
        """
        self._log_with_context(logging.ERROR, msg, context, exc_info=exc_info, **kwargs)

    def critical_ctx(
        self,
        msg: str,
        context: Optional[Dict[str, Any]] = None,
        exc_info: Any = None,
        **kwargs
    ) -> None:
        """
        Log critical message with context.

        Args:
            msg: Log message
            context: Dictionary of context fields
            exc_info: Exception info (True, exception instance, or exc_info tuple)
            **kwargs: Additional context fields as keyword arguments

        Example:
            logger.critical_ctx("Server shutdown", reason="out_of_memory", available_mb=50)
        """
        self._log_with_context(logging.CRITICAL, msg, context, exc_info=exc_info, **kwargs)


# Module-level configuration
_configured = False
_use_json_format = False


def configure_logging(
    use_json: bool = True,
    level: int = logging.INFO,
    log_file: Optional[Path] = None,
) -> None:
    """
    Configure structured logging globally.

    Args:
        use_json: Whether to use JSON formatting (default: True)
        level: Default log level (default: INFO)
        log_file: Optional file path to write logs to

    Example:
        from src.logging.structured_logger import configure_logging

        # Configure JSON logging to file and console
        configure_logging(use_json=True, level=logging.DEBUG, log_file=Path("app.log"))
    """
    global _configured, _use_json_format

    # Set custom logger class
    logging.setLoggerClass(StructuredLogger)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Clear existing handlers
    root_logger.handlers.clear()

    # Choose formatter
    if use_json:
        formatter = JSONFormatter()
        _use_json_format = True
    else:
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        _use_json_format = False

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # File handler (optional)
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

    _configured = True


def get_logger(name: str) -> StructuredLogger:
    """
    Get a structured logger instance.

    This function is backward compatible with logging.getLogger() but returns
    a StructuredLogger instance with additional context methods.

    Args:
        name: Logger name (typically __name__)

    Returns:
        StructuredLogger: Logger instance with structured logging support

    Example:
        from src.logging.structured_logger import get_logger

        logger = get_logger(__name__)

        # Standard logging (backward compatible)
        logger.info("Server started")

        # Structured logging with context
        logger.info_ctx("Request processed",
            method="GET",
            path="/api/search",
            duration_ms=45
        )
    """
    # Ensure StructuredLogger is the logger class
    if not isinstance(logging.getLoggerClass(), type) or not issubclass(
        logging.getLoggerClass(), StructuredLogger
    ):
        logging.setLoggerClass(StructuredLogger)

    return logging.getLogger(name)


def is_json_logging() -> bool:
    """
    Check if JSON logging is enabled.

    Returns:
        bool: True if JSON logging is configured
    """
    return _use_json_format
