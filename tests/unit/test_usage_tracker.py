"""Tests for usage tracking functionality."""

import pytest
import pytest_asyncio
import asyncio
from datetime import datetime, UTC, timedelta

from src.memory.usage_tracker import UsageTracker, UsageStats
from src.config import ServerConfig


class MockStore:
    """Mock storage backend for testing."""

    def __init__(self):
        self.usage_data = {}

    async def batch_update_usage(self, usage_data_list):
        for data in usage_data_list:
            self.usage_data[data["memory_id"]] = data
        return True

    async def get_usage_stats(self, memory_id):
        return self.usage_data.get(memory_id)

    async def get_all_usage_stats(self):
        return list(self.usage_data.values())


@pytest.fixture
def config():
    """Create test configuration."""
    return ServerConfig(
        analytics={"usage_tracking": True},
        usage_batch_size=10,
        usage_flush_interval_seconds=1,
        ranking_weight_similarity=0.6,
        ranking_weight_recency=0.2,
        ranking_weight_usage=0.2,
        recency_decay_halflife_days=7.0,
    )


@pytest.fixture
def mock_store():
    """Create mock storage backend."""
    return MockStore()


@pytest_asyncio.fixture
async def usage_tracker(config, mock_store):
    """Create usage tracker."""
    tracker = UsageTracker(config, mock_store)
    await tracker.start()
    yield tracker
    await tracker.stop()


@pytest.mark.asyncio
async def test_usage_stats_creation():
    """Test UsageStats creation."""
    stats = UsageStats(
        memory_id="test_id",
        first_seen=datetime.now(UTC),
        last_used=datetime.now(UTC),
        use_count=5,
        last_search_score=0.9,
    )

    assert stats.memory_id == "test_id"
    assert stats.use_count == 5
    assert stats.last_search_score == 0.9


@pytest.mark.asyncio
async def test_usage_stats_update():
    """Test updating usage statistics."""
    stats = UsageStats(memory_id="test_id")
    initial_count = stats.use_count

    stats.update_usage(search_score=0.85)

    assert stats.use_count == initial_count + 1
    assert stats.last_search_score == 0.85
    assert stats.last_used is not None


@pytest.mark.asyncio
async def test_record_usage(usage_tracker):
    """Test recording usage."""
    await usage_tracker.record_usage("mem1", search_score=0.9)

    assert usage_tracker.stats["total_tracked"] == 1
    assert len(usage_tracker._pending_updates) == 1


@pytest.mark.asyncio
async def test_batch_record_usage(usage_tracker):
    """Test recording batch usage."""
    memory_ids = ["mem1", "mem2", "mem3"]
    scores = [0.9, 0.8, 0.7]

    await usage_tracker.record_batch(memory_ids, scores)

    assert usage_tracker.stats["total_tracked"] == 3
    assert len(usage_tracker._pending_updates) == 3


@pytest.mark.asyncio
async def test_auto_flush_on_batch_size(config, mock_store):
    """Test automatic flush when batch size is reached."""
    config.usage_batch_size = 3
    tracker = UsageTracker(config, mock_store)
    await tracker.start()

    try:
        # Record 3 usages (should trigger flush)
        await tracker.record_usage("mem1")
        await tracker.record_usage("mem2")
        await tracker.record_usage("mem3")

        # Give a moment for async flush
        await asyncio.sleep(0.1)

        # Pending updates should be cleared after flush
        assert len(tracker._pending_updates) == 0
        assert tracker.stats["flush_count"] >= 1

    finally:
        await tracker.stop()


@pytest.mark.asyncio
async def test_periodic_flush(config, mock_store):
    """Test periodic flush."""
    config.usage_flush_interval_seconds = 1
    tracker = UsageTracker(config, mock_store)
    await tracker.start()

    try:
        await tracker.record_usage("mem1")

        # Wait for periodic flush
        await asyncio.sleep(1.5)

        # Should have flushed
        assert tracker.stats["flush_count"] >= 1
        assert len(tracker._pending_updates) == 0

    finally:
        await tracker.stop()


@pytest.mark.asyncio
async def test_composite_score_calculation(usage_tracker):
    """Test composite score calculation."""
    # New memory, never used
    score1 = usage_tracker.calculate_composite_score(
        similarity_score=0.9,
        created_at=datetime.now(UTC),
        last_used=None,
        use_count=0,
    )

    # Old memory, frequently used
    old_time = datetime.now(UTC) - timedelta(days=14)
    score2 = usage_tracker.calculate_composite_score(
        similarity_score=0.9,
        created_at=old_time,
        last_used=datetime.now(UTC),
        use_count=100,
    )

    # score2 should be higher due to usage (even with same similarity)
    assert 0.0 <= score1 <= 1.0
    assert 0.0 <= score2 <= 1.0


@pytest.mark.asyncio
async def test_recency_decay(usage_tracker):
    """Test recency decay calculation."""
    now = datetime.now(UTC)

    # Very recent memory
    recent_score = usage_tracker.calculate_composite_score(
        similarity_score=0.5,
        created_at=now,
        last_used=now,
        use_count=1,
    )

    # Old memory (14 days = 2 half-lives)
    old_time = now - timedelta(days=14)
    old_score = usage_tracker.calculate_composite_score(
        similarity_score=0.5,
        created_at=old_time,
        last_used=old_time,
        use_count=1,
    )

    # Recent should score higher
    assert recent_score > old_score


@pytest.mark.asyncio
async def test_usage_frequency_scoring(usage_tracker):
    """Test usage frequency component."""
    now = datetime.now(UTC)

    # Rarely used
    rare_score = usage_tracker.calculate_composite_score(
        similarity_score=0.5,
        created_at=now,
        last_used=now,
        use_count=1,
    )

    # Frequently used
    frequent_score = usage_tracker.calculate_composite_score(
        similarity_score=0.5,
        created_at=now,
        last_used=now,
        use_count=100,
    )

    # Frequent should score higher
    assert frequent_score > rare_score


@pytest.mark.asyncio
async def test_get_tracker_stats(usage_tracker):
    """Test getting tracker statistics."""
    await usage_tracker.record_usage("mem1")

    stats = usage_tracker.get_tracker_stats()

    assert "total_tracked" in stats
    assert "total_flushed" in stats
    assert "flush_count" in stats
    assert "running" in stats
    assert stats["running"] is True


@pytest.mark.asyncio
async def test_stop_flushes_remaining(config, mock_store):
    """Test that stop() flushes remaining updates."""
    tracker = UsageTracker(config, mock_store)
    await tracker.start()

    await tracker.record_usage("mem1")
    await tracker.record_usage("mem2")

    # Stop should flush
    await tracker.stop()

    # Check that data was flushed to store
    assert "mem1" in mock_store.usage_data
    assert "mem2" in mock_store.usage_data
