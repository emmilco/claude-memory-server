"""Tests for StorageOptimizer."""

import pytest
from datetime import datetime, timedelta, UTC
from unittest.mock import AsyncMock, Mock, patch

from src.memory.storage_optimizer import (
    StorageOptimizer,
    LifecycleConfig,
    OptimizationOpportunity,
    StorageAnalysisResult,
)
from src.core.models import MemoryUnit, MemoryCategory, ContextLevel, MemoryScope, LifecycleState


@pytest.fixture
def lifecycle_config():
    """Create test lifecycle configuration."""
    return LifecycleConfig(
        session_expiry_hours=48,
        importance_decay_half_life_days=7,
        auto_archive_threshold_days=180,
        auto_delete_threshold_days=365,
        compression_size_threshold_kb=10,
        enable_auto_compression=True,
        enable_auto_archival=True,
    )


@pytest.fixture
def mock_store():
    """Create mock memory store."""
    store = AsyncMock()
    store.search = AsyncMock()
    store.delete = AsyncMock()
    store.close = AsyncMock()
    return store


@pytest.fixture
def sample_memories():
    """Create sample memories for testing."""
    now = datetime.now(UTC)

    memories = []

    # Active memories (recent)
    for i in range(10):
        memories.append(
            MemoryUnit(
                id=f"active-{i}",
                content=f"Active memory {i}",
                category=MemoryCategory.FACT,
                context_level=ContextLevel.PROJECT_CONTEXT,
                scope=MemoryScope.GLOBAL,
                importance=0.8,
                created_at=now - timedelta(days=3),
                last_accessed=now - timedelta(days=1),
                lifecycle_state=LifecycleState.ACTIVE,
            )
        )

    # Recent memories (7-30 days old)
    for i in range(15):
        memories.append(
            MemoryUnit(
                id=f"recent-{i}",
                content=f"Recent memory {i}",
                category=MemoryCategory.FACT,
                context_level=ContextLevel.PROJECT_CONTEXT,
                scope=MemoryScope.GLOBAL,
                importance=0.6,
                created_at=now - timedelta(days=20),
                last_accessed=now - timedelta(days=15),
                lifecycle_state=LifecycleState.RECENT,
            )
        )

    # Stale memories (180+ days old)
    for i in range(20):
        memories.append(
            MemoryUnit(
                id=f"stale-{i}",
                content=f"Stale memory {i}",
                category=MemoryCategory.FACT,
                context_level=ContextLevel.PROJECT_CONTEXT,
                scope=MemoryScope.GLOBAL,
                importance=0.3,
                created_at=now - timedelta(days=200),
                last_accessed=now - timedelta(days=190),
                lifecycle_state=LifecycleState.STALE,
            )
        )

    # Large memories (>10KB)
    for i in range(5):
        large_content = "x" * (12 * 1024)  # 12KB
        memories.append(
            MemoryUnit(
                id=f"large-{i}",
                content=large_content,
                category=MemoryCategory.FACT,
                context_level=ContextLevel.PROJECT_CONTEXT,
                scope=MemoryScope.GLOBAL,
                importance=0.5,
                created_at=now - timedelta(days=50),
                last_accessed=now - timedelta(days=45),
                lifecycle_state=LifecycleState.ARCHIVED,
            )
        )

    # SESSION_STATE memories (should be expired)
    for i in range(8):
        memories.append(
            MemoryUnit(
                id=f"session-{i}",
                content=f"Session state {i}",
                category=MemoryCategory.CONTEXT,
                context_level=ContextLevel.SESSION_STATE,
                scope=MemoryScope.GLOBAL,
                importance=0.5,
                created_at=now - timedelta(hours=60),  # 60 hours old (> 48h)
                last_accessed=now - timedelta(hours=60),
                lifecycle_state=LifecycleState.RECENT,
            )
        )

    return memories


@pytest.mark.asyncio
async def test_analyze_empty_store(mock_store, lifecycle_config):
    """Test analysis with no memories."""
    # Setup
    mock_store.search.return_value = []
    optimizer = StorageOptimizer(mock_store, lifecycle_config)

    # Execute
    result = await optimizer.analyze()

    # Verify
    assert result.total_memories == 0
    assert result.total_size_mb == 0.0
    assert len(result.opportunities) == 0
    assert result.potential_savings_mb == 0.0


@pytest.mark.asyncio
async def test_analyze_finds_stale_memories(mock_store, lifecycle_config, sample_memories):
    """Test that analysis identifies stale memories for deletion."""
    # Setup
    mock_result = Mock()
    mock_result.memory = Mock()

    mock_store.search.return_value = [
        type('obj', (object,), {'memory': m})()
        for m in sample_memories
    ]

    optimizer = StorageOptimizer(mock_store, lifecycle_config)

    # Execute
    result = await optimizer.analyze()

    # Verify
    assert result.total_memories == len(sample_memories)

    # Should find stale memory opportunity
    stale_opps = [o for o in result.opportunities if o.type == 'delete' and 'STALE' in o.description]
    assert len(stale_opps) > 0

    stale_opp = stale_opps[0]
    assert stale_opp.affected_count == 20  # 20 stale memories
    assert stale_opp.risk_level == 'low'
    assert stale_opp.storage_savings_mb > 0


@pytest.mark.asyncio
async def test_analyze_finds_expired_sessions(mock_store, lifecycle_config, sample_memories):
    """Test that analysis identifies expired SESSION_STATE memories."""
    # Setup
    mock_store.search.return_value = [
        type('obj', (object,), {'memory': m})()
        for m in sample_memories
    ]

    optimizer = StorageOptimizer(mock_store, lifecycle_config)

    # Execute
    result = await optimizer.analyze()

    # Verify
    session_opps = [o for o in result.opportunities if 'SESSION_STATE' in o.description]
    assert len(session_opps) > 0

    session_opp = session_opps[0]
    assert session_opp.affected_count == 8  # 8 expired sessions
    assert session_opp.risk_level == 'safe'  # Session state is safe to delete
    assert session_opp.type == 'delete'


@pytest.mark.asyncio
async def test_analyze_finds_large_memories(mock_store, lifecycle_config, sample_memories):
    """Test that analysis identifies large memories for compression."""
    # Setup
    mock_store.search.return_value = [
        type('obj', (object,), {'memory': m})()
        for m in sample_memories
    ]

    optimizer = StorageOptimizer(mock_store, lifecycle_config)

    # Execute
    result = await optimizer.analyze()

    # Verify
    compress_opps = [o for o in result.opportunities if o.type == 'compress']
    assert len(compress_opps) > 0

    # Should find the 5 large (12KB) memories
    compress_opp = compress_opps[0]
    assert compress_opp.affected_count == 5
    assert compress_opp.storage_savings_mb > 0


@pytest.mark.asyncio
async def test_analyze_finds_duplicates(mock_store, lifecycle_config):
    """Test that analysis identifies potential duplicates."""
    # Create memories with similar characteristics (same category, similar size)
    now = datetime.now(UTC)
    similar_memories = []

    for i in range(5):
        similar_memories.append(
            MemoryUnit(
                id=f"similar-{i}",
                content="x" * 500,  # Same length
                category=MemoryCategory.FACT,  # Same category
                context_level=ContextLevel.PROJECT_CONTEXT,  # Same level
                scope=MemoryScope.GLOBAL,
                importance=0.5,
                created_at=now,
                last_accessed=now,
                lifecycle_state=LifecycleState.ACTIVE,
            )
        )

    # Setup
    mock_store.search.return_value = [
        type('obj', (object,), {'memory': m})()
        for m in similar_memories
    ]

    optimizer = StorageOptimizer(mock_store, lifecycle_config)

    # Execute
    result = await optimizer.analyze()

    # Verify
    dedup_opps = [o for o in result.opportunities if o.type == 'deduplicate']
    assert len(dedup_opps) > 0


@pytest.mark.asyncio
async def test_lifecycle_distribution(mock_store, lifecycle_config, sample_memories):
    """Test that lifecycle distribution is calculated correctly."""
    # Setup
    mock_store.search.return_value = [
        type('obj', (object,), {'memory': m})()
        for m in sample_memories
    ]

    optimizer = StorageOptimizer(mock_store, lifecycle_config)

    # Execute
    result = await optimizer.analyze()

    # Verify distribution counts
    assert result.by_lifecycle_state['ACTIVE'] == 10
    assert result.by_lifecycle_state['RECENT'] == 23  # 15 + 8 SESSION_STATE
    assert result.by_lifecycle_state['ARCHIVED'] == 5
    assert result.by_lifecycle_state['STALE'] == 20


@pytest.mark.asyncio
async def test_estimate_memory_size(mock_store, lifecycle_config):
    """Test memory size estimation."""
    now = datetime.now(UTC)

    # Small memory
    small_memory = MemoryUnit(
        id="small",
        content="x" * 100,
        category=MemoryCategory.FACT,
        context_level=ContextLevel.PROJECT_CONTEXT,
        scope=MemoryScope.GLOBAL,
        importance=0.5,
        created_at=now,
        last_accessed=now,
    )

    # Large memory (max 50KB, so use 40KB to be safe)
    large_memory = MemoryUnit(
        id="large",
        content="x" * (40 * 1024),  # 40KB
        category=MemoryCategory.FACT,
        context_level=ContextLevel.PROJECT_CONTEXT,
        scope=MemoryScope.GLOBAL,
        importance=0.5,
        created_at=now,
        last_accessed=now,
    )

    optimizer = StorageOptimizer(mock_store, lifecycle_config)

    small_size = optimizer._estimate_memory_size_mb(small_memory)
    large_size = optimizer._estimate_memory_size_mb(large_memory)

    assert large_size > small_size
    assert small_size < 0.01  # < 10KB
    assert large_size > 0.04  # > 40KB


@pytest.mark.asyncio
async def test_apply_optimization_dry_run(mock_store, lifecycle_config):
    """Test that dry run doesn't actually delete anything."""
    opportunity = OptimizationOpportunity(
        type='delete',
        description="Test deletion",
        affected_count=5,
        storage_savings_mb=1.0,
        risk_level='safe',
        details={'memory_ids': ['mem1', 'mem2', 'mem3', 'mem4', 'mem5']},
    )

    optimizer = StorageOptimizer(mock_store, lifecycle_config)

    # Execute in dry-run mode
    count = await optimizer.apply_optimization(opportunity, dry_run=True)

    # Verify
    assert count == 5
    mock_store.delete.assert_not_called()  # Should NOT delete in dry-run


@pytest.mark.asyncio
async def test_apply_optimization_live(mock_store, lifecycle_config):
    """Test that live mode actually deletes memories."""
    opportunity = OptimizationOpportunity(
        type='delete',
        description="Test deletion",
        affected_count=3,
        storage_savings_mb=1.0,
        risk_level='safe',
        details={'memory_ids': ['mem1', 'mem2', 'mem3']},
    )

    optimizer = StorageOptimizer(mock_store, lifecycle_config)

    # Execute in live mode
    count = await optimizer.apply_optimization(opportunity, dry_run=False)

    # Verify
    assert count == 3
    assert mock_store.delete.call_count == 3


@pytest.mark.asyncio
async def test_get_safe_optimizations(mock_store, lifecycle_config):
    """Test filtering for safe optimizations only."""
    opportunities = [
        OptimizationOpportunity(
            type='delete',
            description="Safe op",
            affected_count=10,
            storage_savings_mb=1.0,
            risk_level='safe',
        ),
        OptimizationOpportunity(
            type='delete',
            description="Low risk op",
            affected_count=5,
            storage_savings_mb=0.5,
            risk_level='low',
        ),
        OptimizationOpportunity(
            type='compress',
            description="Medium risk op",
            affected_count=3,
            storage_savings_mb=0.3,
            risk_level='medium',
        ),
    ]

    analysis = StorageAnalysisResult(
        total_memories=100,
        total_size_mb=10.0,
        by_lifecycle_state={},
        by_lifecycle_size_mb={},
        opportunities=opportunities,
        potential_savings_mb=1.8,
    )

    optimizer = StorageOptimizer(mock_store, lifecycle_config)

    # Execute
    safe_opps = await optimizer.get_safe_optimizations(analysis)

    # Verify
    assert len(safe_opps) == 1
    assert safe_opps[0].risk_level == 'safe'


@pytest.mark.asyncio
async def test_auto_optimize_dry_run(mock_store, lifecycle_config, sample_memories):
    """Test auto-optimization in dry-run mode."""
    # Setup
    mock_store.search.return_value = [
        type('obj', (object,), {'memory': m})()
        for m in sample_memories
    ]

    optimizer = StorageOptimizer(mock_store, lifecycle_config)

    # Execute
    result = await optimizer.auto_optimize(dry_run=True)

    # Verify
    assert result['total_memories'] == len(sample_memories)
    assert result['opportunities_found'] > 0
    assert result['safe_opportunities'] > 0  # Should have SESSION_STATE expiry (safe)
    assert result['dry_run'] is True
    mock_store.delete.assert_not_called()


@pytest.mark.asyncio
async def test_auto_optimize_live(mock_store, lifecycle_config, sample_memories):
    """Test auto-optimization in live mode."""
    # Setup
    mock_store.search.return_value = [
        type('obj', (object,), {'memory': m})()
        for m in sample_memories
    ]

    optimizer = StorageOptimizer(mock_store, lifecycle_config)

    # Execute
    result = await optimizer.auto_optimize(dry_run=False)

    # Verify
    assert result['total_memories'] == len(sample_memories)
    assert result['opportunities_found'] > 0
    assert result['applied'] > 0  # Should apply safe optimizations
    assert result['dry_run'] is False
    assert mock_store.delete.call_count > 0  # Should actually delete


@pytest.mark.asyncio
async def test_opportunity_sorting(mock_store, lifecycle_config):
    """Test that opportunities are sorted by savings (descending) and risk (ascending)."""
    opportunities = [
        OptimizationOpportunity(
            type='compress',
            description="Small savings, high risk",
            affected_count=10,
            storage_savings_mb=0.5,
            risk_level='high',
        ),
        OptimizationOpportunity(
            type='delete',
            description="Large savings, low risk",
            affected_count=50,
            storage_savings_mb=10.0,
            risk_level='low',
        ),
        OptimizationOpportunity(
            type='compress',
            description="Medium savings, medium risk",
            affected_count=20,
            storage_savings_mb=5.0,
            risk_level='medium',
        ),
    ]

    # Sort opportunities
    sorted_opps = sorted(opportunities)

    # Verify order: highest savings first
    assert sorted_opps[0].storage_savings_mb == 10.0
    assert sorted_opps[1].storage_savings_mb == 5.0
    assert sorted_opps[2].storage_savings_mb == 0.5


@pytest.mark.asyncio
async def test_storage_analysis_summary(mock_store, lifecycle_config, sample_memories):
    """Test that analysis summary is formatted correctly."""
    # Setup
    mock_store.search.return_value = [
        type('obj', (object,), {'memory': m})()
        for m in sample_memories
    ]

    optimizer = StorageOptimizer(mock_store, lifecycle_config)

    # Execute
    result = await optimizer.analyze()
    summary = result.get_summary()

    # Verify
    assert "Total Memories:" in summary
    assert "Total Storage:" in summary
    assert "Lifecycle Distribution:" in summary
    assert "Optimization Opportunities:" in summary
    assert "Potential Savings:" in summary


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
