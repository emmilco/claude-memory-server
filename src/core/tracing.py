"""Distributed tracing support using context variables."""

import asyncio
import uuid
from contextvars import ContextVar
from typing import Optional
import functools
import logging

# Context variable for operation ID (propagates automatically through async/await)
operation_id: ContextVar[str] = ContextVar('operation_id', default='')


def get_operation_id() -> str:
    """
    Get current operation ID or generate new one.

    Returns:
        Current operation ID (8 chars) or empty string if not set.
    """
    op_id = operation_id.get()
    if not op_id:
        op_id = str(uuid.uuid4())[:8]
        operation_id.set(op_id)
    return op_id


def set_operation_id(op_id: str) -> None:
    """
    Set operation ID for current context.

    Args:
        op_id: Operation ID to set (typically 8 chars from uuid).
    """
    operation_id.set(op_id)


def clear_operation_id() -> None:
    """Clear operation ID from current context."""
    operation_id.set('')


def new_operation() -> str:
    """
    Start a new operation with fresh ID.

    Returns:
        Generated operation ID (8 chars).
    """
    op_id = str(uuid.uuid4())[:8]
    operation_id.set(op_id)
    return op_id


def traced(func):
    """
    Decorator to add operation ID to function calls.

    For async functions, automatically generates a new operation ID
    if one doesn't exist, and clears it after execution.

    Args:
        func: Function to decorate (must be async).

    Returns:
        Wrapped function with operation ID management.
    """
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        # Generate new operation ID for this request
        op_id = new_operation()
        try:
            return await func(*args, **kwargs)
        finally:
            # Clean up operation ID after request completes
            clear_operation_id()
    return wrapper


class ContextAwareLoggerAdapter(logging.LoggerAdapter):
    """
    Logger adapter that includes operation_id in log records.

    Automatically prepends [operation_id] to all log messages when
    an operation ID is set in the current context.
    """

    def process(self, msg: str, kwargs: dict) -> tuple[str, dict]:
        """
        Add operation_id to log message if available.

        Args:
            msg: Original log message.
            kwargs: Additional logging kwargs.

        Returns:
            Tuple of (modified message, kwargs).
        """
        op_id = operation_id.get()
        if op_id:
            msg = f"[{op_id}] {msg}"
        return msg, kwargs


def get_logger(name: str) -> logging.LoggerAdapter:
    """
    Get a context-aware logger for the given module.

    Args:
        name: Logger name (typically __name__).

    Returns:
        Logger adapter that includes operation IDs in all log messages.
    """
    base_logger = logging.getLogger(name)
    return ContextAwareLoggerAdapter(base_logger, {})
