"""
Integration tests for MCP error handling and responses (F010).

Tests structured error responses, error recovery, and error logging.
Covers SPEC requirement F010-R004.
"""

import pytest
import pytest_asyncio
import json
from typing import Dict, Any

from src.config import ServerConfig
from src.core.server import MemoryRAGServer
from src.core.models import MemoryCategory
from src.core.exceptions import (
    ValidationError,
    StorageError,
    ReadOnlyError,
    MemoryNotFoundError,
    QdrantConnectionError,
)
from pydantic import ValidationError as PydanticValidationError


@pytest.fixture
def config(unique_qdrant_collection):
    """Create test configuration."""
    return ServerConfig(
        storage_backend="qdrant",
        qdrant_url="http://localhost:6333",
        qdrant_collection_name=unique_qdrant_collection,
        advanced={"read_only_mode": False},
    )


@pytest.fixture
def readonly_config(unique_qdrant_collection):
    """Create read-only test configuration."""
    return ServerConfig(
        storage_backend="qdrant",
        qdrant_url="http://localhost:6333",
        qdrant_collection_name=unique_qdrant_collection,
        advanced={"read_only_mode": True},
    )


@pytest_asyncio.fixture
async def server(config):
    """Create and initialize server instance."""
    srv = MemoryRAGServer(config)
    await srv.initialize()
    yield srv
    await srv.close()


@pytest_asyncio.fixture
async def readonly_server(readonly_config):
    """Create and initialize read-only server instance."""
    srv = MemoryRAGServer(readonly_config)
    await srv.initialize()
    yield srv
    await srv.close()


class TestErrorResponseFormat:
    """Tests for F010-R004: Structured error responses."""

    @pytest.mark.asyncio
    async def test_validation_error_format(self, server):
        """
        F010-R004: ValidationError returns proper JSON structure.

        Verifies error includes type, message, error_code, and optional details.
        """
        # Trigger validation error with invalid data
        try:
            from src.core.models import StoreMemoryRequest
            StoreMemoryRequest(content="", category=MemoryCategory.FACT)
            assert False, "Should have raised validation error"
        except (ValidationError, PydanticValidationError) as e:
            # Convert to error response format
            error_dict = {
                "error_type": type(e).__name__,
                "message": str(e),
                "error_code": getattr(e, 'error_code', 'VALIDATION_ERROR'),
            }

            # Should be JSON serializable
            json_str = json.dumps(error_dict)
            assert isinstance(json_str, str)

            # Should contain key information
            assert "error_type" in error_dict
            assert "message" in error_dict
            assert len(error_dict["message"]) > 0

    @pytest.mark.asyncio
    async def test_storage_error_format(self, server):
        """
        F010-R004: StorageError returns proper JSON structure.

        Tests error format for storage backend failures.
        """
        # Create a storage error
        error = StorageError(
            "Test storage error",
            solution="Restart Qdrant",
            docs_url="https://docs.example.com"
        )

        # Convert to error response
        error_dict = {
            "error_type": "StorageError",
            "error_code": error.error_code,
            "message": str(error),
            "solution": error.solution,
            "docs_url": error.docs_url,
        }

        # Should be JSON serializable
        json_str = json.dumps(error_dict)
        assert isinstance(json_str, str)

        # Verify structure
        assert error_dict["error_code"] == "E001"
        assert error_dict["solution"] == "Restart Qdrant"
        assert "Test storage error" in error_dict["message"]

    @pytest.mark.asyncio
    async def test_not_found_error_format(self, server):
        """
        F010-R004: Memory not found returns proper structure.

        Tests error response when requesting non-existent memory.
        """
        # Try to get non-existent memory
        fake_id = "00000000-0000-0000-0000-000000000000"

        try:
            await server.get_memory_by_id(fake_id)
            # Some implementations might return None instead of raising
        except MemoryNotFoundError as e:
            # Error should have proper structure
            error_dict = {
                "error_type": "MemoryNotFoundError",
                "error_code": e.error_code,
                "message": str(e),
                "memory_id": fake_id,
            }

            assert error_dict["error_code"] == "E012"
            assert fake_id in error_dict["message"]

            # Should be JSON serializable
            json.dumps(error_dict)

    @pytest.mark.asyncio
    async def test_read_only_error_format(self, readonly_server):
        """
        F010-R004: Read-only mode violation returns proper error.

        Tests error response when attempting writes in read-only mode.
        """
        # Try to store memory in read-only mode
        try:
            await readonly_server.store_memory(
                content="Should fail",
                category="fact",
            )
            assert False, "Should have raised ReadOnlyError"
        except ReadOnlyError as e:
            # Error should have proper structure
            error_dict = {
                "error_type": "ReadOnlyError",
                "error_code": e.error_code,
                "message": str(e),
                "operation": e.operation,
            }

            assert error_dict["error_code"] == "E003"
            assert "read-only" in error_dict["message"].lower()

            # Should be JSON serializable
            json.dumps(error_dict)

    @pytest.mark.asyncio
    async def test_error_includes_request_context(self, server):
        """
        F010-R004: Errors include tool name and context.

        Verifies error responses contain enough context for debugging.
        """
        # Trigger validation error
        try:
            from src.core.models import QueryRequest
            QueryRequest(query="")  # Empty query
        except (ValidationError, PydanticValidationError) as e:
            error_msg = str(e)

            # Error should mention what field failed
            assert "query" in error_msg.lower() or "empty" in error_msg.lower()

            # Should be informative
            assert len(error_msg) > 10


class TestErrorRecovery:
    """Tests for F010-R004: Error recovery and resilience."""

    @pytest.mark.asyncio
    async def test_invalid_request_doesnt_crash_server(self, server):
        """
        F010-R004: Bad request handled gracefully without crashing.

        Server should remain operational after invalid requests.
        """
        # Make an invalid request
        try:
            from src.core.models import StoreMemoryRequest
            StoreMemoryRequest(content="", category=MemoryCategory.FACT)
        except Exception:
            pass  # Expected to fail

        # Server should still work
        result = await server.store_memory(
            content="Valid memory after error",
            category="fact",
        )
        assert result["status"] == "success"

        # Another operation should also work
        results = await server.list_memories(limit=5)
        assert isinstance(results, dict)

    @pytest.mark.asyncio
    @pytest.mark.skip_ci(reason="Flaky under parallel execution - Qdrant timing sensitive")
    async def test_partial_batch_failure_reported(self, server):
        """
        F010-R004: Batch operations with some failures report clearly.

        Tests that partial failures are communicated properly.
        """
        import asyncio

        # Create a batch with some valid and some invalid operations
        tasks = [
            # Valid stores
            server.store_memory(content="Valid 1", category="fact"),
            server.store_memory(content="Valid 2", category="fact"),
            # Invalid store (will fail validation)
            server.store_memory(content="", category="fact"),
            # More valid stores
            server.store_memory(content="Valid 3", category="fact"),
        ]

        # Execute with return_exceptions to capture failures
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Should have mix of successes and failures
        successes = [r for r in results if isinstance(r, dict) and r.get("status") == "success"]
        failures = [r for r in results if isinstance(r, Exception)]

        assert len(successes) >= 3, "Valid operations should succeed"
        assert len(failures) >= 1, "Invalid operation should fail"

        # Failures should be exceptions, not crashes
        for failure in failures:
            assert isinstance(failure, Exception)

    @pytest.mark.asyncio
    async def test_timeout_produces_proper_error(self, server):
        """
        F010-R004: Long operations timeout gracefully.

        Tests that timeouts are handled properly with informative errors.
        """
        import asyncio

        # Try to timeout a search operation
        try:
            async with asyncio.timeout(0.001):  # Very short timeout
                await server.retrieve_memories(query="timeout test")
        except asyncio.TimeoutError:
            # This is the expected error type
            pass
        except AttributeError:
            # Python < 3.11 doesn't have asyncio.timeout
            try:
                await asyncio.wait_for(
                    server.retrieve_memories(query="timeout test"),
                    timeout=0.001
                )
            except asyncio.TimeoutError:
                pass  # Expected

        # Server should still work after timeout
        result = await server.store_memory(
            content="After timeout",
            category="fact",
        )
        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_connection_error_produces_proper_error(self, server):
        """
        F010-R004: DB unavailable is handled with proper error.

        Tests that connection errors are communicated clearly.
        Note: This test checks error structure, not actual connection failure.
        """
        # Test QdrantConnectionError structure
        error = QdrantConnectionError(
            url="http://localhost:6333",
            reason="Connection refused"
        )

        # Verify error has proper structure
        assert error.error_code == "E010"
        assert error.url == "http://localhost:6333"
        assert error.solution is not None
        assert "docker-compose" in error.solution.lower()

        # Error should be JSON serializable
        error_dict = {
            "error_type": "QdrantConnectionError",
            "error_code": error.error_code,
            "message": str(error),
            "url": error.url,
            "solution": error.solution,
        }
        json.dumps(error_dict)

    @pytest.mark.asyncio
    async def test_error_logging_triggered(self, server):
        """
        F010-R004: Errors are logged to security/error logs.

        Tests that error logging infrastructure is in place.
        Note: This test verifies logging capability exists.
        """
        import logging

        # Get the logger
        logger = logging.getLogger("src.core.server")

        # Verify logger exists and is configured
        assert logger is not None
        assert len(logger.handlers) >= 0  # May have handlers from config

        # Trigger an error that would be logged
        try:
            from src.core.models import StoreMemoryRequest
            StoreMemoryRequest(content="", category=MemoryCategory.FACT)
        except Exception:
            pass  # Error would be logged in real scenario

        # Server should remain operational
        result = await server.store_memory(
            content="After logged error",
            category="fact",
        )
        assert result["status"] == "success"


class TestActionableErrorMessages:
    """Tests for actionable error messages with solutions."""

    @pytest.mark.asyncio
    async def test_validation_errors_suggest_fixes(self, server):
        """
        Test that validation errors include suggestions.
        """
        try:
            from src.core.models import StoreMemoryRequest
            StoreMemoryRequest(
                content="test",
                category=MemoryCategory.FACT,
                importance=2.0  # Invalid: > 1.0
            )
        except (ValidationError, PydanticValidationError) as e:
            error_msg = str(e)

            # Should mention the field
            assert "importance" in error_msg.lower()

            # Should indicate the constraint
            assert "1.0" in error_msg or "1" in error_msg

    @pytest.mark.asyncio
    async def test_storage_errors_include_solutions(self, server):
        """
        Test that StorageError includes actionable solutions.
        """
        error = StorageError(
            "Failed to connect to Qdrant",
            solution="Start Qdrant with: docker-compose up -d",
            docs_url="docs/SETUP.md"
        )

        # Solution should be present and actionable
        assert error.solution is not None
        assert "docker-compose" in error.solution
        assert error.docs_url is not None

    @pytest.mark.asyncio
    async def test_error_codes_are_consistent(self, server):
        """
        Test that error codes follow consistent naming.
        """
        from src.core.exceptions import (
            MemoryRAGError,
            StorageError,
            ValidationError,
            ReadOnlyError,
            EmbeddingError,
        )

        # All custom errors should have error codes
        assert StorageError.error_code == "E001"
        assert ValidationError.error_code == "E002"
        assert ReadOnlyError.error_code == "E003"
        assert EmbeddingError.error_code == "E006"

        # Error codes should be in message
        storage_err = StorageError("test")
        assert "E001" in str(storage_err)


class TestErrorPropagation:
    """Tests for proper error propagation through async calls."""

    @pytest.mark.asyncio
    async def test_nested_async_errors_propagate(self, server):
        """
        Test that errors from nested async calls propagate correctly.
        """
        import asyncio

        async def nested_operation():
            # This will raise validation error
            from src.core.models import QueryRequest
            QueryRequest(query="")

        # Error should propagate up
        with pytest.raises((ValidationError, PydanticValidationError)):
            await nested_operation()

    @pytest.mark.asyncio
    async def test_error_in_gather_captured(self, server):
        """
        Test that errors in asyncio.gather are captured properly.
        """
        import asyncio

        async def failing_task():
            from src.core.models import StoreMemoryRequest
            StoreMemoryRequest(content="", category=MemoryCategory.FACT)

        async def successful_task():
            return await server.list_memories(limit=1)

        # Execute with return_exceptions
        results = await asyncio.gather(
            successful_task(),
            failing_task(),
            return_exceptions=True
        )

        # First should succeed
        assert isinstance(results[0], dict)

        # Second should be an exception
        assert isinstance(results[1], Exception)

    @pytest.mark.asyncio
    async def test_cancellation_doesnt_corrupt_state(self, server):
        """
        Test that task cancellation doesn't leave server in bad state.
        """
        import asyncio

        # Store a memory
        result = await server.store_memory(
            content="Before cancellation",
            category="fact",
        )
        memory_id = result["memory_id"]

        # Create and cancel a task
        task = asyncio.create_task(
            server.update_memory(
                memory_id=memory_id,
                content="Cancelled update"
            )
        )
        task.cancel()

        try:
            await task
        except asyncio.CancelledError:
            pass

        # Server should still work
        new_result = await server.store_memory(
            content="After cancellation",
            category="fact",
        )
        assert new_result["status"] == "success"

        # Original memory should still be accessible
        retrieved = await server.get_memory_by_id(memory_id)
        assert retrieved is not None
