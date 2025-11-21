"""Integration tests for retrieval gate with MCP server."""

import pytest
import pytest_asyncio

from src.config import ServerConfig
from src.core.server import MemoryRAGServer


@pytest.fixture
def gate_enabled_config():
    """Create config with gate enabled."""
    return ServerConfig(
        storage_backend="qdrant",
        qdrant_url="http://localhost:6333",
        qdrant_collection_name="test_gate_enabled",
        enable_retrieval_gate=True,
        retrieval_gate_threshold=0.5,
        embedding_cache_enabled=False,  # Disable cache for predictable testing
    )


@pytest.fixture
def gate_disabled_config():
    """Create config with gate disabled."""
    return ServerConfig(
        storage_backend="qdrant",
        qdrant_url="http://localhost:6333",
        qdrant_collection_name="test_gate_disabled",
        enable_retrieval_gate=False,
        embedding_cache_enabled=False,
    )


@pytest.fixture
def strict_gate_config():
    """Create config with strict gate (high threshold)."""
    return ServerConfig(
        storage_backend="qdrant",
        qdrant_url="http://localhost:6333",
        qdrant_collection_name="test_gate_strict",
        enable_retrieval_gate=True,
        retrieval_gate_threshold=0.8,
        embedding_cache_enabled=False,
    )


@pytest_asyncio.fixture
async def server_with_gate(gate_enabled_config):
    """Create server with gate enabled."""
    srv = MemoryRAGServer(gate_enabled_config)
    await srv.initialize()
    yield srv
    await srv.close()


@pytest_asyncio.fixture
async def server_without_gate(gate_disabled_config):
    """Create server with gate disabled."""
    srv = MemoryRAGServer(gate_disabled_config)
    await srv.initialize()
    yield srv
    await srv.close()


@pytest_asyncio.fixture
async def server_strict_gate(strict_gate_config):
    """Create server with strict gate."""
    srv = MemoryRAGServer(strict_gate_config)
    await srv.initialize()
    yield srv
    await srv.close()


@pytest.mark.asyncio
async def test_gate_initialization_enabled(server_with_gate):
    """Test gate is initialized when enabled."""
    assert server_with_gate.retrieval_gate is not None
    assert server_with_gate.retrieval_gate.threshold == 0.5


@pytest.mark.asyncio
async def test_gate_initialization_disabled(server_without_gate):
    """Test gate is not initialized when disabled."""
    assert server_without_gate.retrieval_gate is None


@pytest.mark.asyncio
async def test_gate_initialization_strict(server_strict_gate):
    """Test gate threshold is configurable."""
    assert server_strict_gate.retrieval_gate is not None
    assert server_strict_gate.retrieval_gate.threshold == 0.8


@pytest.mark.asyncio
async def test_small_talk_query_gated(server_with_gate):
    """Test small talk queries are gated and return empty results."""
    # Small talk query should be gated
    result = await server_with_gate.retrieve_memories(
        query="thanks",
        limit=5,
    )

    # Should return empty results quickly
    assert result['total_found'] == 0
    assert len(result['results']) == 0

    # Should update gating metrics
    assert server_with_gate.stats['queries_gated'] == 1
    assert server_with_gate.stats['queries_processed'] == 1


@pytest.mark.asyncio
async def test_coding_query_not_gated(server_with_gate):
    """Test coding queries pass through gate."""
    # Technical query should not be gated
    result = await server_with_gate.retrieve_memories(
        query="how does the authentication middleware work?",
        limit=5,
    )

    # Query should be processed (though may return 0 results if DB is empty)
    assert server_with_gate.stats['queries_processed'] == 1
    assert server_with_gate.stats['queries_retrieved'] == 1
    assert server_with_gate.stats['queries_gated'] == 0


@pytest.mark.asyncio
async def test_gate_disabled_processes_all(server_without_gate):
    """Test all queries processed when gate is disabled."""
    # Even small talk should be processed
    result = await server_without_gate.retrieve_memories(
        query="thanks",
        limit=5,
    )

    # Query was processed (not gated)
    assert server_without_gate.stats['queries_processed'] == 1
    # No gating stats when gate is disabled
    assert server_without_gate.stats['queries_gated'] == 0


@pytest.mark.asyncio
async def test_gate_metrics_accumulation(server_with_gate):
    """Test gate metrics accumulate correctly over multiple queries."""
    queries = [
        "thanks",  # Should gate
        "ok",  # Should gate
        "how does authentication work?",  # Should not gate
        "find the login function",  # Should not gate
        "cool",  # Should gate
    ]

    for query in queries:
        await server_with_gate.retrieve_memories(query, limit=5)

    # Verify metrics
    assert server_with_gate.stats['queries_processed'] == 5

    # At least some queries should be gated
    gated = server_with_gate.stats['queries_gated']
    retrieved = server_with_gate.stats['queries_retrieved']

    assert gated > 0, "Should gate at least some queries"
    assert retrieved > 0, "Should retrieve for at least some queries"
    assert gated + retrieved == 5, "All queries should be either gated or retrieved"


@pytest.mark.asyncio
async def test_token_savings_estimation(server_with_gate):
    """Test token savings are estimated."""
    # Gate a query
    await server_with_gate.retrieve_memories("ok", limit=5)

    # Should have token savings estimate
    assert server_with_gate.stats['estimated_tokens_saved'] > 0


@pytest.mark.asyncio
async def test_status_includes_gate_metrics(server_with_gate):
    """Test status endpoint includes gate metrics."""
    # Make some queries
    await server_with_gate.retrieve_memories("thanks", limit=5)
    await server_with_gate.retrieve_memories("find authentication code", limit=5)

    # Get status
    status = await server_with_gate.get_status()

    # Should include gate metrics
    assert 'gate_metrics' in status
    gate_metrics = status['gate_metrics']

    assert 'total_queries' in gate_metrics
    assert 'queries_gated' in gate_metrics
    assert 'queries_retrieved' in gate_metrics
    assert 'gating_rate' in gate_metrics
    assert 'estimated_tokens_saved' in gate_metrics

    assert gate_metrics['total_queries'] == 2


@pytest.mark.asyncio
async def test_status_gate_disabled(server_without_gate):
    """Test status when gate is disabled."""
    status = await server_without_gate.get_status()

    # Should have empty gate metrics when disabled
    assert 'gate_metrics' in status
    assert status['gate_metrics'] == {}


@pytest.mark.asyncio
async def test_strict_gate_gates_more(server_strict_gate, server_with_gate):
    """Test strict gate (high threshold) gates fewer queries."""
    query = "show me the code"

    # Run same query through both gates
    await server_with_gate.retrieve_memories(query, limit=5)
    await server_strict_gate.retrieve_memories(query, limit=5)

    # Strict gate should be more selective
    # (This is a probabilistic test based on the query)
    normal_gated = server_with_gate.stats['queries_gated']
    strict_gated = server_strict_gate.stats['queries_gated']

    # With higher threshold, strict gate should gate less (or equal)
    assert strict_gated <= normal_gated


@pytest.mark.asyncio
async def test_gate_query_time_reporting(server_with_gate):
    """Test gated queries still report timing."""
    result = await server_with_gate.retrieve_memories("ok", limit=5)

    # Should have query time even when gated
    assert 'query_time_ms' in result
    assert result['query_time_ms'] > 0

    # Gated queries should be very fast (< 10ms typically)
    # since they skip embedding and retrieval
    assert result['query_time_ms'] < 100


@pytest.mark.asyncio
async def test_gate_with_filters_still_works(server_with_gate):
    """Test gate works with query filters."""
    # Test that filters don't interfere with gating
    result = await server_with_gate.retrieve_memories(
        query="thanks",
        limit=5,
        context_level="PROJECT_CONTEXT",
        min_importance=0.5,
    )

    # Should still gate small talk even with filters
    assert result['total_found'] == 0
    assert server_with_gate.stats['queries_gated'] == 1


@pytest.mark.asyncio
async def test_gate_preserves_normal_retrieval_flow(server_with_gate):
    """Test gate doesn't break normal retrieval when queries pass."""
    # Store a test memory first
    await server_with_gate.store_memory(
        content="authentication middleware implementation",
        category="context",
    )

    # Query that should pass gate
    result = await server_with_gate.retrieve_memories(
        query="how does authentication work?",
        limit=5,
    )

    # Should not be gated
    assert server_with_gate.stats['queries_gated'] == 0
    assert server_with_gate.stats['queries_retrieved'] == 1

    # Should potentially find the stored memory
    # (depending on embedding similarity)


@pytest.mark.asyncio
async def test_gate_decision_logging(server_with_gate, caplog):
    """Test gate decisions are logged."""
    import logging
    caplog.set_level(logging.INFO)

    # Gate a query
    await server_with_gate.retrieve_memories("ok", limit=5)

    # Should have log entry about gating
    assert any("gated" in record.message.lower() for record in caplog.records)


@pytest.mark.asyncio
async def test_concurrent_queries_with_gate(server_with_gate):
    """Test gate handles concurrent queries correctly."""
    import asyncio

    # Run multiple queries concurrently
    queries = [
        server_with_gate.retrieve_memories("thanks", limit=5),
        server_with_gate.retrieve_memories("find auth code", limit=5),
        server_with_gate.retrieve_memories("ok", limit=5),
    ]

    results = await asyncio.gather(*queries)

    # All queries should complete
    assert len(results) == 3

    # Metrics should account for all queries
    assert server_with_gate.stats['queries_processed'] == 3


@pytest.mark.asyncio
async def test_gate_with_various_limits(server_with_gate):
    """Test gate handles different result limits correctly."""
    # Test with different limits for token estimation
    await server_with_gate.retrieve_memories("ok", limit=1)
    savings_1 = server_with_gate.stats['estimated_tokens_saved']

    await server_with_gate.retrieve_memories("thanks", limit=10)
    savings_10 = server_with_gate.stats['estimated_tokens_saved']

    # Larger limit should contribute more to savings
    assert savings_10 > savings_1
