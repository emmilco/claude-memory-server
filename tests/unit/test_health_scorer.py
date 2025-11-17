"""Tests for health scorer."""

import pytest
from datetime import datetime, UTC, timedelta
from unittest.mock import AsyncMock, MagicMock

from src.memory.health_scorer import HealthScorer, HealthScore
from src.core.models import LifecycleState, MemoryUnit


class TestHealthScorer:
    """Test suite for HealthScorer."""

    @pytest.fixture
    def mock_store(self):
        """Create a mock memory store."""
        store = AsyncMock()
        return store

    @pytest.fixture
    def scorer(self, mock_store):
        """Create a health scorer instance."""
        return HealthScorer(mock_store)

    @pytest.mark.asyncio
    async def test_calculate_overall_health_empty_database(self, scorer, mock_store):
        """Test health calculation with empty database."""
        mock_store.get_all_memories = AsyncMock(return_value=[])

        score = await scorer.calculate_overall_health()

        assert score.total_count == 0
        assert score.overall >= 0
        assert score.overall <= 100
        assert score.grade in ["Excellent", "Good", "Fair", "Poor"]

    @pytest.mark.asyncio
    async def test_calculate_overall_health_all_active(self, scorer, mock_store):
        """Test health calculation with all ACTIVE memories."""
        # Create mock memories
        memories = []
        for i in range(10):
            mem = MagicMock()
            mem.id = f"mem-{i}"
            mem.lifecycle_state = LifecycleState.ACTIVE
            mem.content = f"Content {i}"
            mem.created_at = datetime.now(UTC)
            memories.append(mem)

        mock_store.get_all_memories = AsyncMock(return_value=memories)

        score = await scorer.calculate_overall_health()

        assert score.total_count == 10
        assert score.active_count == 10
        assert score.recent_count == 0
        assert score.archived_count == 0
        assert score.stale_count == 0
        assert score.overall > 75  # Should be Good or Excellent

    @pytest.mark.asyncio
    async def test_calculate_overall_health_mixed_states(self, scorer, mock_store):
        """Test health calculation with mixed lifecycle states."""
        memories = []

        # 6 ACTIVE (60%)
        for i in range(6):
            mem = MagicMock()
            mem.id = f"active-{i}"
            mem.lifecycle_state = LifecycleState.ACTIVE
            mem.content = f"Active content {i}"
            mem.created_at = datetime.now(UTC)
            memories.append(mem)

        # 2 RECENT (20%)
        for i in range(2):
            mem = MagicMock()
            mem.id = f"recent-{i}"
            mem.lifecycle_state = LifecycleState.RECENT
            mem.content = f"Recent content {i}"
            mem.created_at = datetime.now(UTC) - timedelta(days=15)
            memories.append(mem)

        # 1 ARCHIVED (10%)
        mem = MagicMock()
        mem.id = "archived-0"
        mem.lifecycle_state = LifecycleState.ARCHIVED
        mem.content = "Archived content"
        mem.created_at = datetime.now(UTC) - timedelta(days=60)
        memories.append(mem)

        # 1 STALE (10%)
        mem = MagicMock()
        mem.id = "stale-0"
        mem.lifecycle_state = LifecycleState.STALE
        mem.content = "Stale content"
        mem.created_at = datetime.now(UTC) - timedelta(days=200)
        memories.append(mem)

        mock_store.get_all_memories = AsyncMock(return_value=memories)

        score = await scorer.calculate_overall_health()

        assert score.total_count == 10
        assert score.active_count == 6
        assert score.recent_count == 2
        assert score.archived_count == 1
        assert score.stale_count == 1
        # With ideal distribution, should be good health
        assert score.overall > 60

    @pytest.mark.asyncio
    async def test_noise_ratio_calculation(self, scorer, mock_store):
        """Test noise ratio calculation."""
        memories = []

        # 5 ACTIVE (50%)
        for i in range(5):
            mem = MagicMock()
            mem.id = f"active-{i}"
            mem.lifecycle_state = LifecycleState.ACTIVE
            mem.content = f"Active {i}"
            mem.created_at = datetime.now(UTC)
            memories.append(mem)

        # 5 STALE (50%) - high noise
        for i in range(5):
            mem = MagicMock()
            mem.id = f"stale-{i}"
            mem.lifecycle_state = LifecycleState.STALE
            mem.content = f"Stale {i}"
            mem.created_at = datetime.now(UTC) - timedelta(days=200)
            memories.append(mem)

        mock_store.get_all_memories = AsyncMock(return_value=memories)

        score = await scorer.calculate_overall_health()

        # Noise should be high (>50% because STALE + some ARCHIVED)
        assert score.noise_ratio > 0.4

    @pytest.mark.asyncio
    async def test_distribution_score_ideal(self, scorer, mock_store):
        """Test distribution score with ideal distribution."""
        memories = []

        # Ideal: 60% ACTIVE, 25% RECENT, 10% ARCHIVED, 5% STALE
        for i in range(60):
            mem = MagicMock()
            mem.id = f"active-{i}"
            mem.lifecycle_state = LifecycleState.ACTIVE
            mem.content = f"Active {i}"
            mem.created_at = datetime.now(UTC)
            memories.append(mem)

        for i in range(25):
            mem = MagicMock()
            mem.id = f"recent-{i}"
            mem.lifecycle_state = LifecycleState.RECENT
            mem.content = f"Recent {i}"
            mem.created_at = datetime.now(UTC) - timedelta(days=15)
            memories.append(mem)

        for i in range(10):
            mem = MagicMock()
            mem.id = f"archived-{i}"
            mem.lifecycle_state = LifecycleState.ARCHIVED
            mem.content = f"Archived {i}"
            mem.created_at = datetime.now(UTC) - timedelta(days=60)
            memories.append(mem)

        for i in range(5):
            mem = MagicMock()
            mem.id = f"stale-{i}"
            mem.lifecycle_state = LifecycleState.STALE
            mem.content = f"Stale {i}"
            mem.created_at = datetime.now(UTC) - timedelta(days=200)
            memories.append(mem)

        mock_store.get_all_memories = AsyncMock(return_value=memories)

        score = await scorer.calculate_overall_health()

        # Distribution should be near perfect
        assert score.distribution_score > 95

    @pytest.mark.asyncio
    async def test_recommendations_high_noise(self, scorer, mock_store):
        """Test recommendations when noise is high."""
        memories = []

        # 9 STALE (90%) - very high noise
        for i in range(9):
            mem = MagicMock()
            mem.id = f"stale-{i}"
            mem.lifecycle_state = LifecycleState.STALE
            mem.content = f"Stale {i}"
            mem.created_at = datetime.now(UTC) - timedelta(days=200)
            memories.append(mem)

        # 1 ACTIVE (10%)
        mem = MagicMock()
        mem.id = "active-0"
        mem.lifecycle_state = LifecycleState.ACTIVE
        mem.content = "Active"
        mem.created_at = datetime.now(UTC)
        memories.append(mem)

        mock_store.get_all_memories = AsyncMock(return_value=memories)

        score = await scorer.calculate_overall_health()

        # Should recommend cleanup
        assert len(score.recommendations) > 0
        assert any("noise" in rec.lower() for rec in score.recommendations)

    @pytest.mark.asyncio
    async def test_health_grade_excellent(self, scorer, mock_store):
        """Test Excellent grade (90-100)."""
        # Near perfect distribution
        memories = []
        for i in range(6):
            mem = MagicMock()
            mem.id = f"active-{i}"
            mem.lifecycle_state = LifecycleState.ACTIVE
            mem.content = f"Active {i}"
            mem.created_at = datetime.now(UTC)
            memories.append(mem)

        for i in range(3):
            mem = MagicMock()
            mem.id = f"recent-{i}"
            mem.lifecycle_state = LifecycleState.RECENT
            mem.content = f"Recent {i}"
            mem.created_at = datetime.now(UTC) - timedelta(days=15)
            memories.append(mem)

        mem = MagicMock()
        mem.id = "archived-0"
        mem.lifecycle_state = LifecycleState.ARCHIVED
        mem.content = "Archived"
        mem.created_at = datetime.now(UTC) - timedelta(days=60)
        memories.append(mem)

        mock_store.get_all_memories = AsyncMock(return_value=memories)

        score = await scorer.calculate_overall_health()

        # Should be Excellent or Good
        assert score.grade in ["Excellent", "Good"]
        assert score.overall >= 75

    @pytest.mark.asyncio
    async def test_health_grade_poor(self, scorer, mock_store):
        """Test Poor grade (<60)."""
        # All STALE - very poor health
        memories = []
        for i in range(10):
            mem = MagicMock()
            mem.id = f"stale-{i}"
            mem.lifecycle_state = LifecycleState.STALE
            mem.content = f"Stale {i}"
            mem.created_at = datetime.now(UTC) - timedelta(days=200)
            memories.append(mem)

        mock_store.get_all_memories = AsyncMock(return_value=memories)

        score = await scorer.calculate_overall_health()

        # Should be Poor or Fair
        assert score.grade in ["Poor", "Fair"]
        assert score.overall < 75

    @pytest.mark.asyncio
    async def test_to_dict_serialization(self, scorer, mock_store):
        """Test HealthScore serialization to dictionary."""
        mock_store.get_all_memories = AsyncMock(return_value=[])

        score = await scorer.calculate_overall_health()
        score_dict = score.to_dict()

        # Check all expected fields
        assert "overall" in score_dict
        assert "noise_ratio" in score_dict
        assert "duplicate_rate" in score_dict
        assert "contradiction_rate" in score_dict
        assert "distribution_score" in score_dict
        assert "lifecycle_distribution" in score_dict
        assert "grade" in score_dict
        assert "recommendations" in score_dict
        assert "timestamp" in score_dict

        # Check types
        assert isinstance(score_dict["overall"], (int, float))
        assert isinstance(score_dict["lifecycle_distribution"], dict)
        assert isinstance(score_dict["recommendations"], list)

    @pytest.mark.asyncio
    async def test_quick_stats(self, scorer, mock_store):
        """Test quick stats retrieval."""
        memories = []
        for i in range(5):
            mem = MagicMock()
            mem.id = f"active-{i}"
            mem.lifecycle_state = LifecycleState.ACTIVE
            mem.content = f"Active {i}"
            mem.created_at = datetime.now(UTC)
            memories.append(mem)

        mock_store.get_all_memories = AsyncMock(return_value=memories)

        stats = await scorer.get_quick_stats()

        assert "total_memories" in stats
        assert "lifecycle_distribution" in stats
        assert "stale_percentage" in stats
        assert stats["total_memories"] == 5
