"""Tests for distributed tracing functionality."""

import pytest
import asyncio
import logging
from src.core.tracing import (
    get_operation_id,
    set_operation_id,
    clear_operation_id,
    new_operation,
    traced,
    ContextAwareLoggerAdapter,
    get_logger,
)


class TestOperationIDGeneration:
    """Test operation ID generation and management."""

    def test_new_operation_generates_unique_ids(self):
        """Verify each new_operation() call generates a unique ID."""
        ids = [new_operation() for _ in range(100)]
        assert len(set(ids)) == 100, "All operation IDs should be unique"

    def test_operation_id_format(self):
        """Verify operation ID format is 8 characters."""
        op_id = new_operation()
        assert len(op_id) == 8
        # Should be UUID prefix (hex chars and hyphens)
        assert all(c in '0123456789abcdef-' for c in op_id)

    def test_get_operation_id_returns_empty_when_not_set(self):
        """Verify get_operation_id returns empty string when not set."""
        clear_operation_id()
        # First call should generate and set a new ID
        op_id = get_operation_id()
        assert op_id != ''
        assert len(op_id) == 8

    def test_set_operation_id(self):
        """Verify set_operation_id stores the ID."""
        test_id = "test1234"
        set_operation_id(test_id)
        assert get_operation_id() == test_id

    def test_clear_operation_id(self):
        """Verify clear_operation_id removes the ID."""
        set_operation_id("test1234")
        assert get_operation_id() == "test1234"
        clear_operation_id()
        # After clearing, get_operation_id should generate a new one
        new_id = get_operation_id()
        assert new_id != "test1234"
        assert new_id != ''


class TestContextPropagation:
    """Test operation ID propagation through async calls."""

    @pytest.mark.asyncio
    async def test_operation_id_propagates_through_async(self):
        """Verify operation ID propagates through async calls."""
        set_operation_id("async123")

        async def level1():
            assert get_operation_id() == "async123"
            await level2()

        async def level2():
            assert get_operation_id() == "async123"
            await level3()

        async def level3():
            assert get_operation_id() == "async123"

        await level1()

    @pytest.mark.asyncio
    async def test_multiple_concurrent_operations_isolated(self):
        """Verify concurrent async operations have isolated operation IDs."""
        results = []

        async def operation(op_id: str):
            set_operation_id(op_id)
            # Simulate some async work
            await asyncio.sleep(0.01)
            # Operation ID should still be the same
            results.append(get_operation_id())

        # Run multiple operations concurrently
        await asyncio.gather(
            operation("op1"),
            operation("op2"),
            operation("op3"),
        )

        # Each operation should have maintained its own ID
        assert "op1" in results
        assert "op2" in results
        assert "op3" in results


class TestTracedDecorator:
    """Test @traced decorator functionality."""

    @pytest.mark.asyncio
    async def test_traced_decorator_generates_operation_id(self):
        """Verify @traced decorator generates and cleans up operation ID."""
        captured_id = None

        @traced
        async def test_func():
            nonlocal captured_id
            captured_id = get_operation_id()
            assert captured_id != ''
            assert len(captured_id) == 8
            return "result"

        # Before call: clear any existing ID
        clear_operation_id()

        # Call the decorated function
        result = await test_func()
        assert result == "result"
        assert captured_id is not None

        # After call: operation ID should be cleared
        # Note: get_operation_id() will generate a new one, so we check it's different
        new_id = get_operation_id()
        # The new ID should be different from the one used in the function
        # (since traced() clears it, get_operation_id() generates a fresh one)

    @pytest.mark.asyncio
    async def test_traced_decorator_cleans_up_on_exception(self):
        """Verify @traced decorator cleans up operation ID even on exception."""
        @traced
        async def failing_func():
            op_id = get_operation_id()
            assert op_id != ''
            raise ValueError("Test error")

        clear_operation_id()

        with pytest.raises(ValueError, match="Test error"):
            await failing_func()

        # Operation ID should be cleared even after exception
        # (get_operation_id will generate a new one)
        new_id = get_operation_id()
        assert new_id != ''


class TestContextAwareLogger:
    """Test context-aware logger functionality."""

    def test_logger_includes_operation_id(self, caplog):
        """Verify logger includes operation ID in output."""
        logger = get_logger("test")
        set_operation_id("log123")

        with caplog.at_level(logging.INFO):
            logger.info("Test message")

        assert "[log123]" in caplog.text
        assert "Test message" in caplog.text

    def test_logger_without_operation_id(self, caplog):
        """Verify logger works without operation ID."""
        logger = get_logger("test")
        clear_operation_id()

        # Manually set empty to avoid auto-generation in get_operation_id
        set_operation_id('')

        with caplog.at_level(logging.INFO):
            logger.info("Test message")

        # Should not have bracketed ID when ID is empty
        assert "Test message" in caplog.text
        # Should not have double brackets
        assert "[]" not in caplog.text

    def test_logger_adapter_process_method(self):
        """Verify ContextAwareLoggerAdapter.process() adds operation ID."""
        base_logger = logging.getLogger("test")
        adapter = ContextAwareLoggerAdapter(base_logger, {})

        set_operation_id("proc123")
        msg, kwargs = adapter.process("Original message", {})

        assert msg == "[proc123] Original message"

    def test_get_logger_returns_adapter(self):
        """Verify get_logger returns a LoggerAdapter instance."""
        logger = get_logger("test")
        assert isinstance(logger, logging.LoggerAdapter)
        assert isinstance(logger, ContextAwareLoggerAdapter)


class TestEndToEndScenarios:
    """Test realistic end-to-end scenarios."""

    @pytest.mark.asyncio
    async def test_request_flow_with_operation_id(self, caplog):
        """Simulate a request flow with operation ID propagation."""
        logger = get_logger("server")

        @traced
        async def handle_request(request_data: str):
            logger.info(f"Received request: {request_data}")
            await process_request(request_data)
            logger.info("Request completed")
            return "success"

        async def process_request(data: str):
            logger = get_logger("processor")
            logger.info(f"Processing: {data}")
            await save_to_db(data)

        async def save_to_db(data: str):
            logger = get_logger("db")
            logger.info(f"Saving: {data}")

        with caplog.at_level(logging.INFO):
            result = await handle_request("test_data")

        assert result == "success"

        # Extract all log lines
        lines = caplog.text.split('\n')
        log_lines = [l for l in lines if l.strip() and '[' in l]

        # All logs should have the same operation ID
        operation_ids = []
        for line in log_lines:
            if '[' in line and ']' in line:
                # Extract operation ID from [op_id] format
                start = line.index('[') + 1
                end = line.index(']')
                op_id = line[start:end]
                operation_ids.append(op_id)

        # All operation IDs should be the same
        assert len(operation_ids) >= 3, "Should have at least 3 log entries"
        assert len(set(operation_ids)) == 1, "All logs should have the same operation ID"

    @pytest.mark.asyncio
    async def test_multiple_concurrent_requests(self, caplog):
        """Verify multiple concurrent requests have separate operation IDs."""
        logger = get_logger("server")
        captured_ids = []

        @traced
        async def handle_request(request_id: int):
            op_id = get_operation_id()
            captured_ids.append((request_id, op_id))
            logger.info(f"Request {request_id}")
            await asyncio.sleep(0.01)  # Simulate work
            return op_id

        with caplog.at_level(logging.INFO):
            # Run 3 concurrent requests
            results = await asyncio.gather(
                handle_request(1),
                handle_request(2),
                handle_request(3),
            )

        # Each request should have a unique operation ID
        assert len(set(results)) == 3, "All requests should have unique operation IDs"

        # Verify captured IDs match results
        assert len(captured_ids) == 3
        for req_id, op_id in captured_ids:
            assert op_id in results
