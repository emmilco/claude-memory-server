"""Tests for memory pruning functionality."""

import pytest
from datetime import datetime, UTC, timedelta
from unittest.mock import AsyncMock, Mock

from src.memory.pruner import MemoryPruner, PruneResult
from src.config import ServerConfig
from src.core.models import ContextLevel


class MockStore:
    """Mock storage backend for testing."""

    def __init__(self):
        self.memories = {}
        self.deleted_ids = []

    async def find_memories_by_criteria(self, context_level=None, older_than=None):
        """Find memories matching criteria."""
        results = []
        for mem_id, mem_data in self.memories.items():
            # Check context level
            if context_level and mem_data.get("context_level") != context_level.value:
                continue

            # Check age
            if older_than:
                last_used = mem_data.get("last_used") or mem_data.get("created_at")
                if isinstance(last_used, str):
                    last_used = datetime.fromisoformat(last_used)
                if last_used >= older_than:
                    continue

            results.append({
                "id": mem_id,
                "created_at": mem_data.get("created_at"),
                "last_used": mem_data.get("last_used"),
            })

        return results

    async def find_unused_memories(self, cutoff_time, exclude_context_levels=None):
        """Find unused memories."""
        results = []
        for mem_id, mem_data in self.memories.items():
            # Check context level exclusions
            if exclude_context_levels:
                context_level = mem_data.get("context_level")
                if context_level in [cl.value for cl in exclude_context_levels]:
                    continue

            # Check if unused
            use_count = mem_data.get("use_count", 0)
            if use_count > 0:
                continue

            # Check age
            last_used = mem_data.get("last_used") or mem_data.get("created_at")
            if isinstance(last_used, str):
                last_used = datetime.fromisoformat(last_used)

            if last_used >= cutoff_time:
                continue

            results.append({
                "id": mem_id,
                "created_at": mem_data.get("created_at"),
                "context_level": mem_data.get("context_level"),
                "last_used": mem_data.get("last_used"),
                "use_count": use_count,
            })

        return results

    async def delete(self, memory_id):
        """Delete a memory."""
        if memory_id in self.memories:
            del self.memories[memory_id]
            self.deleted_ids.append(memory_id)
            return True
        return False

    async def delete_usage_tracking(self, memory_id):
        """Delete usage tracking."""
        return True

    async def cleanup_orphaned_usage_tracking(self):
        """Cleanup orphaned tracking."""
        return 0


@pytest.fixture
def config():
    """Create test configuration."""
    return ServerConfig(
        session_state_ttl_hours=48,
        enable_auto_pruning=True,
    )


@pytest.fixture
def mock_store():
    """Create mock storage backend."""
    return MockStore()


@pytest.fixture
def pruner(config, mock_store):
    """Create pruner."""
    return MemoryPruner(config, mock_store)


@pytest.mark.asyncio
async def test_prune_result_creation():
    """Test PruneResult creation."""
    result = PruneResult()

    assert result.memories_deleted == 0
    assert result.memories_scanned == 0
    assert len(result.errors) == 0
    assert len(result.deleted_ids) == 0


@pytest.mark.asyncio
async def test_find_expired_sessions(pruner, mock_store):
    """Test finding expired SESSION_STATE memories."""
    now = datetime.now(UTC)
    old_time = now - timedelta(hours=72)  # 3 days ago

    # Add expired session
    mock_store.memories["expired1"] = {
        "context_level": "SESSION_STATE",
        "created_at": old_time.isoformat(),
        "last_used": old_time.isoformat(),
    }

    # Add recent session
    mock_store.memories["recent1"] = {
        "context_level": "SESSION_STATE",
        "created_at": now.isoformat(),
        "last_used": now.isoformat(),
    }

    expired = await pruner.find_expired_sessions(ttl_hours=48)

    # Should only find the expired one
    expired_ids = [m["id"] for m in expired]
    assert "expired1" in expired_ids
    assert "recent1" not in expired_ids


@pytest.mark.asyncio
async def test_prune_expired_dry_run(pruner, mock_store):
    """Test pruning expired memories (dry run)."""
    now = datetime.now(UTC)
    old_time = now - timedelta(hours=72)

    # Add expired session
    mock_store.memories["expired1"] = {
        "context_level": "SESSION_STATE",
        "created_at": old_time.isoformat(),
        "last_used": old_time.isoformat(),
    }

    result = await pruner.prune_expired(dry_run=True, ttl_hours=48)

    assert result.memories_deleted == 1
    assert "expired1" in result.deleted_ids
    # Dry run - nothing actually deleted
    assert "expired1" in mock_store.memories
    assert len(mock_store.deleted_ids) == 0


@pytest.mark.asyncio
async def test_prune_expired_execute(pruner, mock_store):
    """Test actually pruning expired memories."""
    now = datetime.now(UTC)
    old_time = now - timedelta(hours=72)

    # Add expired session
    mock_store.memories["expired1"] = {
        "context_level": "SESSION_STATE",
        "created_at": old_time.isoformat(),
        "last_used": old_time.isoformat(),
    }

    result = await pruner.prune_expired(dry_run=False, ttl_hours=48)

    assert result.memories_deleted == 1
    assert "expired1" in result.deleted_ids
    # Actually deleted
    assert "expired1" not in mock_store.memories
    assert "expired1" in mock_store.deleted_ids


@pytest.mark.asyncio
async def test_prune_safety_check(pruner, mock_store):
    """Test safety check prevents deletion of recently used memories."""
    now = datetime.now(UTC)
    old_created = now - timedelta(hours=72)
    recent_used = now - timedelta(hours=12)  # Used 12 hours ago

    # Add memory that's old but was used recently
    mock_store.memories["safe1"] = {
        "context_level": "SESSION_STATE",
        "created_at": old_created.isoformat(),
        "last_used": recent_used.isoformat(),
    }

    result = await pruner.prune_expired(
        dry_run=False,
        ttl_hours=48,
        safety_check=True,
    )

    # Should not delete (used in last 24h)
    assert result.memories_deleted == 0
    assert "safe1" in mock_store.memories


@pytest.mark.asyncio
async def test_find_stale_memories(pruner, mock_store):
    """Test finding stale (unused) memories."""
    now = datetime.now(UTC)
    old_time = now - timedelta(days=60)

    # Add stale, unused memory
    mock_store.memories["stale1"] = {
        "context_level": "SESSION_STATE",
        "created_at": old_time.isoformat(),
        "last_used": old_time.isoformat(),
        "use_count": 0,
    }

    # Add stale but used memory
    mock_store.memories["used1"] = {
        "context_level": "SESSION_STATE",
        "created_at": old_time.isoformat(),
        "last_used": old_time.isoformat(),
        "use_count": 5,
    }

    stale = await pruner.find_stale_memories(days_unused=30)

    # Should only find unused one
    stale_ids = [m["id"] for m in stale]
    assert "stale1" in stale_ids
    assert "used1" not in stale_ids


@pytest.mark.asyncio
async def test_prune_stale(pruner, mock_store):
    """Test pruning stale memories."""
    now = datetime.now(UTC)
    old_time = now - timedelta(days=60)

    # Add stale memory
    mock_store.memories["stale1"] = {
        "context_level": "SESSION_STATE",
        "created_at": old_time.isoformat(),
        "last_used": old_time.isoformat(),
        "use_count": 0,
    }

    result = await pruner.prune_stale(days_unused=30, dry_run=False)

    assert result.memories_deleted == 1
    assert "stale1" in result.deleted_ids
    assert "stale1" not in mock_store.memories


@pytest.mark.asyncio
async def test_pruner_stats(pruner, mock_store):
    """Test pruner statistics tracking."""
    now = datetime.now(UTC)
    old_time = now - timedelta(hours=72)

    # Add expired memory
    mock_store.memories["expired1"] = {
        "context_level": "SESSION_STATE",
        "created_at": old_time.isoformat(),
        "last_used": old_time.isoformat(),
    }

    await pruner.prune_expired(dry_run=False)

    stats = pruner.get_stats()

    assert stats["total_prunes"] == 1
    assert stats["total_deleted"] == 1
    assert stats["last_prune_time"] is not None
    assert stats["last_prune_deleted"] == 1


@pytest.mark.asyncio
async def test_prune_excludes_user_preference(pruner, mock_store):
    """Test that USER_PREFERENCE memories are not pruned as stale."""
    now = datetime.now(UTC)
    old_time = now - timedelta(days=60)

    # Add old USER_PREFERENCE memory
    mock_store.memories["pref1"] = {
        "context_level": "USER_PREFERENCE",
        "created_at": old_time.isoformat(),
        "last_used": old_time.isoformat(),
        "use_count": 0,
    }

    stale = await pruner.find_stale_memories(days_unused=30)

    # Should not find USER_PREFERENCE
    stale_ids = [m["id"] for m in stale]
    assert "pref1" not in stale_ids


@pytest.mark.asyncio
async def test_prune_excludes_project_context(pruner, mock_store):
    """Test that PROJECT_CONTEXT memories are not pruned as stale."""
    now = datetime.now(UTC)
    old_time = now - timedelta(days=60)

    # Add old PROJECT_CONTEXT memory
    mock_store.memories["proj1"] = {
        "context_level": "PROJECT_CONTEXT",
        "created_at": old_time.isoformat(),
        "last_used": old_time.isoformat(),
        "use_count": 0,
    }

    stale = await pruner.find_stale_memories(days_unused=30)

    # Should not find PROJECT_CONTEXT
    stale_ids = [m["id"] for m in stale]
    assert "proj1" not in stale_ids
