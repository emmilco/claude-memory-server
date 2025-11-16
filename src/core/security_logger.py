"""Security event logging for Claude Memory RAG Server."""

import logging
import json
from datetime import datetime, UTC
from pathlib import Path
from typing import Optional, Dict, Any
from enum import Enum


class SecurityEventType(str, Enum):
    """Types of security events."""

    VALIDATION_FAILURE = "validation_failure"
    INJECTION_ATTEMPT = "injection_attempt"
    READONLY_VIOLATION = "readonly_violation"
    UNAUTHORIZED_ACCESS = "unauthorized_access"
    SUSPICIOUS_PATTERN = "suspicious_pattern"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    INVALID_INPUT = "invalid_input"
    SIZE_LIMIT_EXCEEDED = "size_limit_exceeded"


class SecurityLogger:
    """
    Dedicated logger for security events.

    Logs security-related events to a separate file for audit and monitoring.
    All events are logged in JSON format for easy parsing and analysis.
    """

    def __init__(self, log_dir: str = "~/.claude-rag"):
        """
        Initialize security logger.

        Args:
            log_dir: Directory for security logs
        """
        self.log_dir = Path(log_dir).expanduser()
        self.log_dir.mkdir(parents=True, exist_ok=True)

        self.log_file = self.log_dir / "security.log"

        # Create dedicated logger
        self.logger = logging.getLogger("security")
        self.logger.setLevel(logging.INFO)
        self.logger.propagate = False  # Don't propagate to root logger

        # Remove existing handlers
        self.logger.handlers.clear()

        # File handler for security log
        file_handler = logging.FileHandler(self.log_file)
        file_handler.setLevel(logging.INFO)

        # Format: timestamp | level | message
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        file_handler.setFormatter(formatter)

        self.logger.addHandler(file_handler)

        # Also log to console for critical events
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.WARNING)
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)

    def _log_event(
        self,
        event_type: SecurityEventType,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        level: int = logging.WARNING,
    ) -> None:
        """
        Log a security event.

        Args:
            event_type: Type of security event
            message: Human-readable message
            details: Additional details
            level: Log level
        """
        event = {
            "timestamp": datetime.now(UTC).isoformat(),
            "event_type": event_type.value,
            "message": message,
        }

        if details:
            event["details"] = details

        # Log as JSON for easy parsing
        json_event = json.dumps(event)
        self.logger.log(level, json_event)

    def log_validation_failure(
        self,
        endpoint: str,
        error: str,
        payload_preview: Optional[str] = None,
    ) -> None:
        """
        Log a validation failure.

        Args:
            endpoint: Endpoint where validation failed
            error: Validation error message
            payload_preview: Preview of the payload (sanitized)
        """
        details = {
            "endpoint": endpoint,
            "error": error,
        }

        if payload_preview:
            # Truncate to avoid logging sensitive data
            details["payload_preview"] = payload_preview[:200]

        self._log_event(
            SecurityEventType.VALIDATION_FAILURE,
            f"Validation failed on {endpoint}: {error}",
            details,
            level=logging.WARNING,
        )

    def log_injection_attempt(
        self,
        pattern_type: str,
        pattern: str,
        content_preview: str,
        endpoint: Optional[str] = None,
    ) -> None:
        """
        Log a potential injection attack attempt.

        Args:
            pattern_type: Type of injection (SQL, prompt, command)
            pattern: Pattern that was detected
            content_preview: Preview of malicious content
            endpoint: Endpoint where attempt occurred
        """
        details = {
            "pattern_type": pattern_type,
            "pattern": pattern,
            "content_preview": content_preview[:200],  # Truncate
        }

        if endpoint:
            details["endpoint"] = endpoint

        self._log_event(
            SecurityEventType.INJECTION_ATTEMPT,
            f"{pattern_type} injection attempt detected: {pattern}",
            details,
            level=logging.ERROR,  # Injection attempts are critical
        )

    def log_readonly_violation(
        self,
        operation: str,
        endpoint: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Log an attempt to perform write operation in read-only mode.

        Args:
            operation: Operation that was attempted (store, delete, etc.)
            endpoint: Endpoint where violation occurred
            details: Additional details
        """
        event_details = {
            "operation": operation,
            "endpoint": endpoint,
        }

        if details:
            event_details.update(details)

        self._log_event(
            SecurityEventType.READONLY_VIOLATION,
            f"Read-only mode violation: {operation} attempted on {endpoint}",
            event_details,
            level=logging.WARNING,
        )

    def log_suspicious_pattern(
        self,
        pattern: str,
        content_preview: str,
        reason: str,
    ) -> None:
        """
        Log detection of a suspicious pattern.

        Args:
            pattern: Pattern that was detected
            content_preview: Preview of content
            reason: Reason why pattern is suspicious
        """
        details = {
            "pattern": pattern,
            "content_preview": content_preview[:200],
            "reason": reason,
        }

        self._log_event(
            SecurityEventType.SUSPICIOUS_PATTERN,
            f"Suspicious pattern detected: {reason}",
            details,
            level=logging.WARNING,
        )

    def log_invalid_input(
        self,
        field: str,
        value_preview: str,
        error: str,
    ) -> None:
        """
        Log invalid input detection.

        Args:
            field: Field that had invalid input
            value_preview: Preview of invalid value
            error: Error description
        """
        details = {
            "field": field,
            "value_preview": value_preview[:100],
            "error": error,
        }

        self._log_event(
            SecurityEventType.INVALID_INPUT,
            f"Invalid input in field '{field}': {error}",
            details,
            level=logging.INFO,
        )

    def log_size_limit_exceeded(
        self,
        actual_size: int,
        max_size: int,
        content_type: str = "content",
    ) -> None:
        """
        Log size limit violation.

        Args:
            actual_size: Actual size in bytes
            max_size: Maximum allowed size
            content_type: Type of content (content, metadata, etc.)
        """
        details = {
            "actual_size": actual_size,
            "max_size": max_size,
            "content_type": content_type,
        }

        self._log_event(
            SecurityEventType.SIZE_LIMIT_EXCEEDED,
            f"Size limit exceeded for {content_type}: {actual_size} > {max_size}",
            details,
            level=logging.WARNING,
        )

    def log_unauthorized_access(
        self,
        resource: str,
        reason: str,
    ) -> None:
        """
        Log unauthorized access attempt.

        Args:
            resource: Resource that was accessed
            reason: Reason for denial
        """
        details = {
            "resource": resource,
            "reason": reason,
        }

        self._log_event(
            SecurityEventType.UNAUTHORIZED_ACCESS,
            f"Unauthorized access to {resource}: {reason}",
            details,
            level=logging.ERROR,
        )

    def get_recent_events(self, n: int = 100) -> list[str]:
        """
        Get recent security events.

        Args:
            n: Number of events to retrieve

        Returns:
            List of recent event log lines
        """
        try:
            if not self.log_file.exists():
                return []

            with open(self.log_file, "r") as f:
                lines = f.readlines()
                return lines[-n:]
        except Exception as e:
            self.logger.error(f"Failed to read security log: {e}")
            return []

    def get_stats(self) -> Dict[str, Any]:
        """
        Get security log statistics.

        Returns:
            Dictionary with statistics
        """
        stats = {
            "log_file": str(self.log_file),
            "log_exists": self.log_file.exists(),
            "log_size_bytes": 0,
            "event_counts": {},
        }

        if self.log_file.exists():
            stats["log_size_bytes"] = self.log_file.stat().st_size

            # Count events by type
            try:
                with open(self.log_file, "r") as f:
                    for line in f:
                        try:
                            event = json.loads(line.split("|", 2)[-1].strip())
                            event_type = event.get("event_type", "unknown")
                            stats["event_counts"][event_type] = (
                                stats["event_counts"].get(event_type, 0) + 1
                            )
                        except (json.JSONDecodeError, IndexError):
                            continue
            except Exception as e:
                self.logger.error(f"Failed to compute stats: {e}")

        return stats


# Global security logger instance
_security_logger: Optional[SecurityLogger] = None


def get_security_logger() -> SecurityLogger:
    """
    Get or create the global security logger instance.

    Returns:
        SecurityLogger instance
    """
    global _security_logger
    if _security_logger is None:
        _security_logger = SecurityLogger()
    return _security_logger


def set_security_logger(logger: SecurityLogger) -> None:
    """
    Set the global security logger (mainly for testing).

    Args:
        logger: SecurityLogger instance
    """
    global _security_logger
    _security_logger = logger
