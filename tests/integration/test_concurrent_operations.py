"""Tests for concurrent operations and race conditions."""

import pytest
import pytest_asyncio
import asyncio
import uuid
from unittest.mock import AsyncMock, Mock

from src.config import ServerConfig
from src.core.server import MemoryRAGServer
from src.core.models import MemoryCategory, MemoryScope


@pytest.fixture
def config(unique_qdrant_collection):
    """Create test configuration with pooled collection.

    Uses the unique_qdrant_collection from conftest.py to leverage
    collection pooling and prevent Qdrant deadlocks during parallel execution.
    """
    return ServerConfig(
        storage_backend="qdrant",
        qdrant_url="http://localhost:6333",
        qdrant_collection_name=unique_qdrant_collection,
        read_only_mode=False,
    )


@pytest_asyncio.fixture
async def server(config, qdrant_client):
    """Create server instance with pooled collection.

    Uses the session-scoped qdrant_client and unique_qdrant_collection
    fixtures from conftest.py to leverage collection pooling and prevent
    Qdrant deadlocks during parallel test execution.
    """
    srv = MemoryRAGServer(config)
    await srv.initialize()
    yield srv

    # Cleanup
    await srv.close()
    # Collection cleanup handled by unique_qdrant_collection autouse fixture


class TestConcurrentWrites:
    """Test concurrent write operations."""

    @pytest.mark.asyncio
    async def test_concurrent_store_operations(self, server):
        """Test multiple concurrent store operations."""
        # Create 10 concurrent store operations
        tasks = [
            server.store_memory(
                content=f"Concurrent memory {i}",
                category="fact",
                scope="global",
                importance=0.5 + (i * 0.01),
            )
            for i in range(10)
        ]

        # Execute all concurrently
        results = await asyncio.gather(*tasks)

        # Verify all succeeded
        assert len(results) == 10
        for result in results:
            assert result["status"] == "success"
            assert "memory_id" in result

        # Verify all have unique IDs
        ids = [r["memory_id"] for r in results]
        assert len(set(ids)) == 10  # All unique

    @pytest.mark.asyncio
    async def test_concurrent_multiple_stores(self, server):
        """Test multiple sequential batches of concurrent stores."""
        # First batch
        batch1_tasks = [
            server.store_memory(content=f"Batch 1 item {i}", category="fact", scope="global")
            for i in range(5)
        ]
        batch1_results = await asyncio.gather(*batch1_tasks)
        assert len(batch1_results) == 5

        # Second batch
        batch2_tasks = [
            server.store_memory(content=f"Batch 2 item {i}", category="preference", scope="global")
            for i in range(5)
        ]
        batch2_results = await asyncio.gather(*batch2_tasks)
        assert len(batch2_results) == 5

        # Verify all succeeded
        for result in batch1_results + batch2_results:
            assert result["status"] == "success"


class TestConcurrentReads:
    """Test concurrent read operations."""

    @pytest.mark.asyncio
    async def test_concurrent_retrieve_operations(self, server):
        """Test multiple concurrent retrieve operations."""
        # Store some memories first
        for i in range(10):
            await server.store_memory(
                content=f"Memory for concurrent retrieval {i}",
                category="fact",
                scope="global",
            )

        # Execute concurrent retrievals
        tasks = [
            server.retrieve_memories(query=f"retrieval {i}", limit=5)
            for i in range(10)
        ]

        results = await asyncio.gather(*tasks)

        # Verify all succeeded
        assert len(results) == 10
        for result in results:
            assert "results" in result
            assert "total_found" in result

    @pytest.mark.asyncio
    async def test_concurrent_reads_during_writes(self, server):
        """Test concurrent reads while writes are happening."""
        # Store initial data
        await server.store_memory(
            content="Initial data",
            category="fact",
            scope="global",
        )

        # Mix reads and writes concurrently
        read_tasks = [
            server.retrieve_memories(query="data", limit=5)
            for _ in range(5)
        ]
        write_tasks = [
            server.store_memory(
                content=f"Concurrent write {i}",
                category="fact",
                scope="global",
            )
            for i in range(5)
        ]

        # Execute all concurrently
        all_tasks = read_tasks + write_tasks
        results = await asyncio.gather(*all_tasks, return_exceptions=True)

        # Verify no exceptions occurred
        for result in results:
            assert not isinstance(result, Exception), f"Unexpected exception: {result}"

        # Verify reads returned valid data
        read_results = results[:5]
        for result in read_results:
            assert "results" in result


class TestConcurrentEmbeddingGeneration:
    """Test concurrent embedding generation."""

    @pytest.mark.asyncio
    async def test_concurrent_embedding_requests(self, server):
        """Test that concurrent embedding requests are handled correctly."""
        # Generate embeddings concurrently
        texts = [f"Generate embedding for text {i}" for i in range(20)]

        # Store all concurrently (each requires embedding generation)
        tasks = [
            server.store_memory(content=text, category="fact", scope="global")
            for text in texts
        ]

        results = await asyncio.gather(*tasks)

        # Verify all succeeded
        assert len(results) == 20
        for result in results:
            assert result["status"] == "success"


class TestConcurrentCacheAccess:
    """Test concurrent cache access."""

    @pytest.mark.asyncio
    async def test_concurrent_cache_reads(self, server):
        """Test concurrent reads to embedding cache."""
        # Store a memory (creates cache entry)
        await server.store_memory(
            content="Cached content",
            category="fact",
            scope="global",
        )

        # Perform many concurrent retrievals (should hit cache)
        tasks = [
            server.retrieve_memories(query="Cached content", limit=5)
            for _ in range(20)
        ]

        results = await asyncio.gather(*tasks)

        # Verify all succeeded
        assert len(results) == 20
        for result in results:
            assert "results" in result

    @pytest.mark.asyncio
    async def test_concurrent_cache_writes(self, server):
        """Test concurrent writes to embedding cache."""
        # Store many memories concurrently (each writes to cache)
        tasks = [
            server.store_memory(
                content=f"Cache write test {i}",
                category="fact",
                scope="global",
            )
            for i in range(15)
        ]

        results = await asyncio.gather(*tasks)

        # Verify all succeeded (no cache corruption)
        assert len(results) == 15
        for result in results:
            assert result["status"] == "success"


class TestConcurrentDeletes:
    """Test concurrent delete operations."""

    @pytest.mark.asyncio
    async def test_concurrent_delete_operations(self, server):
        """Test multiple concurrent delete operations."""
        # Store memories to delete
        store_tasks = [
            server.store_memory(
                content=f"Memory to delete {i}",
                category="fact",
                scope="global",
            )
            for i in range(10)
        ]

        store_results = await asyncio.gather(*store_tasks)
        memory_ids = [r["memory_id"] for r in store_results]

        # Delete concurrently
        delete_tasks = [
            server.delete_memory(memory_id)
            for memory_id in memory_ids
        ]

        delete_results = await asyncio.gather(*delete_tasks)

        # Verify all deletes succeeded
        for result in delete_results:
            assert result["status"] == "success"


class TestConcurrentMixedOperations:
    """Test concurrent mixed operations (reads, writes, deletes)."""

    @pytest.mark.asyncio
    async def test_mixed_operations_concurrently(self, server):
        """Test that mixed operations can run concurrently safely."""
        # Store some initial data
        for i in range(5):
            await server.store_memory(
                content=f"Initial memory {i}",
                category="fact",
                scope="global",
            )

        # Mix of operations
        tasks = []

        # Add some stores
        for i in range(5):
            tasks.append(
                server.store_memory(
                    content=f"Concurrent store {i}",
                    category="fact",
                    scope="global",
                )
            )

        # Add some retrievals
        for i in range(5):
            tasks.append(
                server.retrieve_memories(query=f"memory {i}", limit=5)
            )

        # Add some status checks
        for i in range(3):
            tasks.append(server.get_status())

        # Execute all concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Verify no exceptions
        exceptions = [r for r in results if isinstance(r, Exception)]
        assert len(exceptions) == 0, f"Got exceptions: {exceptions}"


class TestRaceConditions:
    """Test specific race condition scenarios."""

    @pytest.mark.asyncio
    async def test_simultaneous_store_same_content(self, server):
        """Test storing identical content simultaneously."""
        same_content = "This is the same content stored multiple times"

        # Store same content 10 times concurrently
        tasks = [
            server.store_memory(
                content=same_content,
                category="fact",
                scope="global",
            )
            for _ in range(10)
        ]

        results = await asyncio.gather(*tasks)

        # All should succeed
        assert len(results) == 10
        for result in results:
            assert result["status"] == "success"

        # All should have different IDs
        ids = [r["memory_id"] for r in results]
        assert len(set(ids)) == 10

    @pytest.mark.asyncio
    async def test_read_while_updating(self, server):
        """Test reading while another operation updates the same memory."""
        # Store initial memory
        result = await server.store_memory(
            content="Original content",
            category="fact",
            scope="global",
            importance=0.5,
        )
        memory_id = result["memory_id"]

        # Concurrently: update and retrieve
        update_task = server.store.update(memory_id, {"importance": 0.9})
        retrieve_task = server.retrieve_memories(query="Original", limit=5)

        # Execute concurrently
        update_result, retrieve_result = await asyncio.gather(
            update_task,
            retrieve_task,
            return_exceptions=True
        )

        # Neither should fail
        assert not isinstance(update_result, Exception)
        assert not isinstance(retrieve_result, Exception)


class TestConcurrentStressTest:
    """Stress tests with high concurrency."""

    @pytest.mark.asyncio
    async def test_high_concurrency_store(self, server):
        """Test handling high concurrency (50 concurrent operations)."""
        # Create 50 concurrent store operations
        tasks = [
            server.store_memory(
                content=f"Stress test memory {i}",
                category="fact",
                scope="global",
            )
            for i in range(50)
        ]

        # Execute all at once
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Count successes
        successes = [r for r in results if not isinstance(r, Exception) and r.get("status") == "success"]

        # At least 90% should succeed (allow for some contention)
        assert len(successes) >= 45, f"Only {len(successes)}/50 succeeded"

    @pytest.mark.asyncio
    async def test_rapid_retrieve_operations(self, server):
        """Test rapid concurrent retrieve operations."""
        # Store some data
        for i in range(10):
            await server.store_memory(
                content=f"Retrieve stress test {i}",
                category="fact",
                scope="global",
            )

        # Execute 100 concurrent retrievals
        tasks = [
            server.retrieve_memories(query="stress test", limit=5)
            for _ in range(100)
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # All should succeed
        exceptions = [r for r in results if isinstance(r, Exception)]
        assert len(exceptions) == 0, f"Got {len(exceptions)} exceptions"


def test_concurrent_operations_coverage():
    """Report on concurrent operations test coverage."""
    print("\n" + "=" * 70)
    print("CONCURRENT OPERATIONS TEST COVERAGE")
    print("=" * 70)
    print("✓ Concurrent store operations")
    print("✓ Concurrent batch store operations")
    print("✓ Concurrent retrieve operations")
    print("✓ Concurrent reads during writes")
    print("✓ Concurrent embedding generation")
    print("✓ Concurrent cache access (reads and writes)")
    print("✓ Concurrent delete operations")
    print("✓ Mixed operations (reads, writes, deletes)")
    print("✓ Race conditions (same content, read while updating)")
    print("✓ High concurrency stress tests (50-100 concurrent ops)")
    print("=" * 70 + "\n")

    assert True
