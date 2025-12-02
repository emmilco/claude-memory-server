"""Tests for memory lifecycle management."""

import pytest
from datetime import datetime, timedelta, UTC

from src.memory.lifecycle_manager import LifecycleManager, LifecycleConfig
from src.core.models import LifecycleState, MemoryUnit, MemoryCategory, ContextLevel


class TestLifecycleConfig:
    """Test LifecycleConfig dataclass."""

    def test_default_config(self):
        """Test default configuration values."""
        config = LifecycleConfig()

        assert config.active_to_recent_days == 7
        assert config.recent_to_archived_days == 30
        assert config.archived_to_stale_days == 180
        assert config.high_access_threshold == 10
        assert config.moderate_access_threshold == 3
        assert config.active_weight == 1.0
        assert config.recent_weight == 0.7
        assert config.archived_weight == 0.3
        assert config.stale_weight == 0.1

    def test_custom_config(self):
        """Test custom configuration values."""
        config = LifecycleConfig(
            active_to_recent_days=14,
            recent_to_archived_days=60,
            archived_to_stale_days=365,
            active_weight=1.5,
        )

        assert config.active_to_recent_days == 14
        assert config.recent_to_archived_days == 60
        assert config.archived_to_stale_days == 365
        assert config.active_weight == 1.5


class TestLifecycleManager:
    """Test LifecycleManager functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.manager = LifecycleManager()
        self.now = datetime.now(UTC)

    def test_initialization(self):
        """Test manager initialization."""
        assert self.manager.config is not None
        assert isinstance(self.manager.config, LifecycleConfig)

    def test_initialization_with_custom_config(self):
        """Test manager initialization with custom config."""
        custom_config = LifecycleConfig(active_to_recent_days=14)
        manager = LifecycleManager(custom_config)

        assert manager.config.active_to_recent_days == 14

    def test_calculate_state_active(self):
        """Test state calculation for recently accessed memory."""
        created_at = self.now - timedelta(days=2)
        last_accessed = self.now - timedelta(days=1)

        state = self.manager.calculate_state(created_at, last_accessed)

        assert state == LifecycleState.ACTIVE

    def test_calculate_state_recent(self):
        """Test state calculation for moderately old memory."""
        created_at = self.now - timedelta(days=20)
        last_accessed = self.now - timedelta(days=10)

        state = self.manager.calculate_state(created_at, last_accessed)

        assert state == LifecycleState.RECENT

    def test_calculate_state_archived(self):
        """Test state calculation for old memory."""
        created_at = self.now - timedelta(days=100)
        last_accessed = self.now - timedelta(days=50)

        state = self.manager.calculate_state(created_at, last_accessed)

        assert state == LifecycleState.ARCHIVED

    def test_calculate_state_stale(self):
        """Test state calculation for very old memory."""
        created_at = self.now - timedelta(days=365)
        last_accessed = self.now - timedelta(days=200)

        state = self.manager.calculate_state(created_at, last_accessed)

        assert state == LifecycleState.STALE

    def test_calculate_state_high_usage_keeps_active(self):
        """Test that high usage keeps memory ACTIVE even if old."""
        created_at = self.now - timedelta(days=20)
        last_accessed = self.now - timedelta(days=15)
        use_count = 15  # Above high_access_threshold

        state = self.manager.calculate_state(
            created_at, last_accessed, use_count=use_count
        )

        # With high usage, should stay ACTIVE even though 15 days old
        assert state == LifecycleState.ACTIVE

    def test_calculate_state_user_preference_ages_slower(self):
        """Test that USER_PREFERENCE memories age slower."""
        created_at = self.now - timedelta(days=20)
        last_accessed = self.now - timedelta(days=10)

        # For PROJECT_CONTEXT, this would be RECENT (>7 days)
        state_project = self.manager.calculate_state(
            created_at, last_accessed, context_level=ContextLevel.PROJECT_CONTEXT
        )

        # For USER_PREFERENCE, this should still be ACTIVE (threshold doubled)
        state_preference = self.manager.calculate_state(
            created_at, last_accessed, context_level=ContextLevel.USER_PREFERENCE
        )

        assert state_project == LifecycleState.RECENT
        assert state_preference == LifecycleState.ACTIVE

    def test_calculate_state_session_state_ages_faster(self):
        """Test that SESSION_STATE memories age faster."""
        created_at = self.now - timedelta(days=5)
        last_accessed = self.now - timedelta(days=4)

        # For PROJECT_CONTEXT, this would be ACTIVE (<7 days)
        state_project = self.manager.calculate_state(
            created_at, last_accessed, context_level=ContextLevel.PROJECT_CONTEXT
        )

        # For SESSION_STATE, this should be RECENT (threshold halved to 3.5 days)
        state_session = self.manager.calculate_state(
            created_at, last_accessed, context_level=ContextLevel.SESSION_STATE
        )

        assert state_project == LifecycleState.ACTIVE
        assert state_session == LifecycleState.RECENT

    def test_should_transition_same_state(self):
        """Test transition check for same state."""
        should_transition = self.manager.should_transition(
            LifecycleState.ACTIVE, LifecycleState.ACTIVE
        )

        assert should_transition is False

    def test_should_transition_different_state(self):
        """Test transition check for different states."""
        should_transition = self.manager.should_transition(
            LifecycleState.ACTIVE, LifecycleState.RECENT
        )

        assert should_transition is True

    def test_should_transition_backward(self):
        """Test backward transition (promotion) is allowed."""
        should_transition = self.manager.should_transition(
            LifecycleState.ARCHIVED, LifecycleState.ACTIVE
        )

        assert should_transition is True

    def test_get_search_weight_active(self):
        """Test search weight for ACTIVE state."""
        weight = self.manager.get_search_weight(LifecycleState.ACTIVE)
        assert weight == 1.0

    def test_get_search_weight_recent(self):
        """Test search weight for RECENT state."""
        weight = self.manager.get_search_weight(LifecycleState.RECENT)
        assert weight == 0.7

    def test_get_search_weight_archived(self):
        """Test search weight for ARCHIVED state."""
        weight = self.manager.get_search_weight(LifecycleState.ARCHIVED)
        assert weight == 0.3

    def test_get_search_weight_stale(self):
        """Test search weight for STALE state."""
        weight = self.manager.get_search_weight(LifecycleState.STALE)
        assert weight == 0.1

    def test_apply_lifecycle_weight(self):
        """Test applying lifecycle weight to search score."""
        base_score = 0.9

        # ACTIVE: no penalty
        active_score = self.manager.apply_lifecycle_weight(
            base_score, LifecycleState.ACTIVE
        )
        assert active_score == 0.9

        # RECENT: 30% penalty
        recent_score = self.manager.apply_lifecycle_weight(
            base_score, LifecycleState.RECENT
        )
        assert recent_score == pytest.approx(0.63, abs=0.01)

        # ARCHIVED: 70% penalty
        archived_score = self.manager.apply_lifecycle_weight(
            base_score, LifecycleState.ARCHIVED
        )
        assert archived_score == pytest.approx(0.27, abs=0.01)

        # STALE: 90% penalty
        stale_score = self.manager.apply_lifecycle_weight(
            base_score, LifecycleState.STALE
        )
        assert stale_score == pytest.approx(0.09, abs=0.01)

    def test_get_stale_memory_ids(self):
        """Test getting stale memory IDs."""
        memories = [
            MemoryUnit(
                id="mem1",
                content="Recent memory",
                category=MemoryCategory.FACT,
                last_accessed=self.now - timedelta(days=5),
            ),
            MemoryUnit(
                id="mem2",
                content="Old memory",
                category=MemoryCategory.FACT,
                last_accessed=self.now - timedelta(days=200),
            ),
            MemoryUnit(
                id="mem3",
                content="Very old memory",
                category=MemoryCategory.FACT,
                last_accessed=self.now - timedelta(days=365),
            ),
        ]

        stale_ids = self.manager.get_stale_memory_ids(memories)

        assert len(stale_ids) == 2
        assert "mem2" in stale_ids
        assert "mem3" in stale_ids
        assert "mem1" not in stale_ids

    def test_get_stale_memory_ids_with_custom_threshold(self):
        """Test getting stale memory IDs with custom threshold."""
        memories = [
            MemoryUnit(
                id="mem1",
                content="Memory",
                category=MemoryCategory.FACT,
                last_accessed=self.now - timedelta(days=100),
            ),
        ]

        # With default threshold (180), not stale
        stale_ids_default = self.manager.get_stale_memory_ids(memories)
        assert len(stale_ids_default) == 0

        # With custom threshold (90), is stale
        stale_ids_custom = self.manager.get_stale_memory_ids(
            memories, threshold_days=90
        )
        assert len(stale_ids_custom) == 1

    def test_get_lifecycle_stats(self):
        """Test lifecycle statistics calculation."""
        memories = [
            MemoryUnit(
                id="mem1",
                content="Active",
                category=MemoryCategory.FACT,
                lifecycle_state=LifecycleState.ACTIVE,
            ),
            MemoryUnit(
                id="mem2",
                content="Active",
                category=MemoryCategory.FACT,
                lifecycle_state=LifecycleState.ACTIVE,
            ),
            MemoryUnit(
                id="mem3",
                content="Recent",
                category=MemoryCategory.FACT,
                lifecycle_state=LifecycleState.RECENT,
            ),
            MemoryUnit(
                id="mem4",
                content="Archived",
                category=MemoryCategory.FACT,
                lifecycle_state=LifecycleState.ARCHIVED,
            ),
            MemoryUnit(
                id="mem5",
                content="Stale",
                category=MemoryCategory.FACT,
                lifecycle_state=LifecycleState.STALE,
            ),
        ]

        stats = self.manager.get_lifecycle_stats(memories)

        assert stats["total"] == 5
        assert stats["by_state"]["ACTIVE"] == 2
        assert stats["by_state"]["RECENT"] == 1
        assert stats["by_state"]["ARCHIVED"] == 1
        assert stats["by_state"]["STALE"] == 1
        assert stats["percentages"]["ACTIVE"] == 40.0
        assert stats["percentages"]["RECENT"] == 20.0
        assert stats["percentages"]["ARCHIVED"] == 20.0
        assert stats["percentages"]["STALE"] == 20.0

    def test_get_lifecycle_stats_empty(self):
        """Test lifecycle statistics with no memories."""
        stats = self.manager.get_lifecycle_stats([])

        assert stats["total"] == 0
        assert all(count == 0 for count in stats["by_state"].values())

    def test_bulk_update_states(self):
        """Test bulk state updates."""
        memories = [
            MemoryUnit(
                id="mem1",
                content="Old memory",
                category=MemoryCategory.FACT,
                created_at=self.now - timedelta(days=100),
                last_accessed=self.now - timedelta(days=50),
                lifecycle_state=LifecycleState.ACTIVE,  # Wrong state
            ),
            MemoryUnit(
                id="mem2",
                content="Recent memory",
                category=MemoryCategory.FACT,
                created_at=self.now - timedelta(days=5),
                last_accessed=self.now - timedelta(days=2),
                lifecycle_state=LifecycleState.ACTIVE,  # Correct state
            ),
        ]

        transitions = self.manager.bulk_update_states(memories)

        # mem1 should transition from ACTIVE to ARCHIVED
        assert len(transitions) == 1
        assert transitions[0][0] == "mem1"
        assert transitions[0][1] == LifecycleState.ACTIVE
        assert transitions[0][2] == LifecycleState.ARCHIVED

        # Check memory states were updated
        assert memories[0].lifecycle_state == LifecycleState.ARCHIVED
        assert memories[1].lifecycle_state == LifecycleState.ACTIVE

    def test_bulk_update_states_with_usage_data(self):
        """Test bulk state updates with usage tracking data."""
        memories = [
            MemoryUnit(
                id="mem1",
                content="Frequently used memory",
                category=MemoryCategory.FACT,
                created_at=self.now - timedelta(days=20),
                last_accessed=self.now - timedelta(days=15),
                lifecycle_state=LifecycleState.RECENT,
            ),
        ]

        usage_data = {
            "mem1": {"use_count": 20, "last_used": self.now - timedelta(days=15)},
        }

        transitions = self.manager.bulk_update_states(memories, usage_data)

        # With high usage (20 > 10), should promote to ACTIVE
        assert len(transitions) == 1
        assert transitions[0][2] == LifecycleState.ACTIVE
        assert memories[0].lifecycle_state == LifecycleState.ACTIVE

    def test_bulk_update_states_no_transitions(self):
        """Test bulk state updates when no transitions needed."""
        memories = [
            MemoryUnit(
                id="mem1",
                content="Correct state",
                category=MemoryCategory.FACT,
                created_at=self.now - timedelta(days=5),
                last_accessed=self.now - timedelta(days=2),
                lifecycle_state=LifecycleState.ACTIVE,
            ),
        ]

        transitions = self.manager.bulk_update_states(memories)

        assert len(transitions) == 0
        assert memories[0].lifecycle_state == LifecycleState.ACTIVE
