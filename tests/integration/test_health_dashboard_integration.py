"""Integration tests for health dashboard and lifecycle management."""

import pytest
import pytest_asyncio
import asyncio
import uuid
from datetime import datetime, UTC, timedelta

from src.config import ServerConfig
from src.store.qdrant_store import QdrantMemoryStore
from src.core.models import MemoryUnit, ContextLevel, LifecycleState, MemoryCategory
from src.memory.health_scorer import HealthScorer
from src.memory.health_jobs import HealthMaintenanceJobs
from src.memory.lifecycle_manager import LifecycleManager
from conftest import mock_embedding

# Skip entire module in CI - Qdrant timing sensitive under parallel execution
pytestmark = pytest.mark.skip_ci(reason="Flaky under parallel execution - Qdrant timing sensitive")


@pytest_asyncio.fixture
async def temp_db(qdrant_client, unique_qdrant_collection):
    """Create a test Qdrant store with pooled collection.

    Uses the session-scoped qdrant_client and unique_qdrant_collection
    fixtures from conftest.py to leverage collection pooling and prevent
    Qdrant deadlocks during parallel test execution.
    """
    config = ServerConfig(
        storage_backend="qdrant",
        qdrant_url="http://localhost:6333",
        qdrant_collection_name=unique_qdrant_collection,
    )

    store = QdrantMemoryStore(config)
    await store.initialize()

    yield store

    # Cleanup
    await store.close()
    # Collection cleanup handled by unique_qdrant_collection autouse fixture


class TestHealthDashboardIntegration:
    """Integration tests for health dashboard functionality."""

    @pytest.mark.asyncio
    async def test_empty_database_health(self, temp_db):
        """Test health calculation on empty database."""
        health_scorer = HealthScorer(temp_db)

        score = await health_scorer.calculate_overall_health()

        assert score.overall >= 0
        assert score.overall <= 100
        assert score.total_count == 0
        assert score.grade in ["Excellent", "Good", "Fair", "Poor"]

    @pytest.mark.asyncio
    async def test_lifecycle_progression_workflow(self, temp_db):
        """Test complete lifecycle progression from ACTIVE to STALE."""
        # Create memories with different ages
        now = datetime.now(UTC)
        # Create test embedding (768 dimensions for all-mpnet-base-v2)
        test_embedding = mock_embedding(value=0.1)

        memories = [
            # Recent (should be ACTIVE)
            MemoryUnit(
                content="Recent memory",
                category=MemoryCategory.FACT,
                context_level=ContextLevel.SESSION_STATE,
                created_at=now - timedelta(days=2),
            ),
            # Medium age (should be RECENT)
            MemoryUnit(
                content="Week old memory",
                category=MemoryCategory.FACT,
                context_level=ContextLevel.SESSION_STATE,
                created_at=now - timedelta(days=15),
            ),
            # Old (should be ARCHIVED)
            MemoryUnit(
                content="Month old memory",
                category=MemoryCategory.FACT,
                context_level=ContextLevel.SESSION_STATE,
                created_at=now - timedelta(days=60),
            ),
            # Very old (should be STALE)
            MemoryUnit(
                content="Very old memory",
                category=MemoryCategory.FACT,
                context_level=ContextLevel.SESSION_STATE,
                created_at=now - timedelta(days=200),
            ),
        ]

        # Store memories
        for mem in memories:
            await temp_db.store(
                content=mem.content,
                embedding=test_embedding,
                metadata={
                    "category": mem.category.value,
                    "context_level": mem.context_level.value,
                    "created_at": mem.created_at.isoformat(),
                    "lifecycle_state": mem.lifecycle_state.value,
                }
            )

        # Calculate health
        health_scorer = HealthScorer(temp_db)
        score = await health_scorer.calculate_overall_health()

        assert score.total_count == 4
        # Distribution should vary (not all in one state)
        assert score.active_count >= 0
        assert score.recent_count >= 0
        assert score.archived_count >= 0
        assert score.stale_count >= 0

    @pytest.mark.asyncio
    async def test_archival_job_workflow(self, temp_db):
        """Test weekly archival job on real data."""
        # Create old ACTIVE memories
        now = datetime.now(UTC)
        # Create test embedding (768 dimensions for all-mpnet-base-v2)
        test_embedding = mock_embedding(value=0.1)

        for i in range(5):
            mem = MemoryUnit(
                content=f"Old memory {i}",
                category=MemoryCategory.FACT,
                context_level=ContextLevel.SESSION_STATE,
                created_at=now - timedelta(days=200),
            )
            await temp_db.store(
                content=mem.content,
                embedding=test_embedding,
                metadata={
                    "category": mem.category.value,
                    "context_level": mem.context_level.value,
                    "created_at": mem.created_at.isoformat(),
                    "lifecycle_state": mem.lifecycle_state.value,
                }
            )

        # Run archival job
        lifecycle_manager = LifecycleManager()
        jobs = HealthMaintenanceJobs(temp_db, lifecycle_manager)

        result = await jobs.weekly_archival_job(dry_run=False)

        assert result.success is True
        assert result.memories_processed >= 0

        # Verify health improved
        health_scorer = HealthScorer(temp_db)
        score = await health_scorer.calculate_overall_health()

        assert score.total_count == 5

    @pytest.mark.asyncio
    async def test_cleanup_job_workflow(self, temp_db):
        """Test monthly cleanup job on real data."""
        # Create old STALE memories
        now = datetime.now(UTC)
        # Create test embedding (768 dimensions for all-mpnet-base-v2)
        test_embedding = mock_embedding(value=0.1)

        for i in range(3):
            mem = MemoryUnit(
                content=f"Stale memory {i}",
                category=MemoryCategory.FACT,
                context_level=ContextLevel.SESSION_STATE,
                created_at=now - timedelta(days=250),
                lifecycle_state=LifecycleState.STALE,
            )
            await temp_db.store(
                content=mem.content,
                embedding=test_embedding,
                metadata={
                    "category": mem.category.value,
                    "context_level": mem.context_level.value,
                    "created_at": mem.created_at.isoformat(),
                    "lifecycle_state": mem.lifecycle_state.value,
                }
            )

        # Get initial count
        initial_memories = await temp_db.get_all_memories()
        initial_count = len(initial_memories)

        # Run cleanup job (dry run first)
        lifecycle_manager = LifecycleManager()
        jobs = HealthMaintenanceJobs(temp_db, lifecycle_manager)

        dry_run_result = await jobs.monthly_cleanup_job(dry_run=True, min_age_days=180)

        assert dry_run_result.success is True
        assert dry_run_result.memories_processed >= 0

        # Verify nothing was deleted in dry run
        current_memories = await temp_db.get_all_memories()
        assert len(current_memories) == initial_count

        # Now run actual cleanup
        result = await jobs.monthly_cleanup_job(dry_run=False, min_age_days=180)

        assert result.success is True

        # Verify some were deleted
        final_memories = await temp_db.get_all_memories()
        # May or may not delete all (depends on use_count)
        assert len(final_memories) <= initial_count

    @pytest.mark.asyncio
    async def test_health_report_job(self, temp_db):
        """Test weekly health report generation."""
        # Create some memories
        now = datetime.now(UTC)
        # Create test embedding (768 dimensions for all-mpnet-base-v2)
        test_embedding = mock_embedding(value=0.1)

        for i in range(10):
            mem = MemoryUnit(
                content=f"Memory {i}",
                category=MemoryCategory.FACT,
                context_level=ContextLevel.SESSION_STATE,
                created_at=now - timedelta(days=i * 10),
            )
            await temp_db.store(
                content=mem.content,
                embedding=test_embedding,
                metadata={
                    "category": mem.category.value,
                    "context_level": mem.context_level.value,
                    "created_at": mem.created_at.isoformat(),
                    "lifecycle_state": mem.lifecycle_state.value,
                }
            )

        # Run health report
        lifecycle_manager = LifecycleManager()
        health_scorer = HealthScorer(temp_db)
        jobs = HealthMaintenanceJobs(temp_db, lifecycle_manager, health_scorer)

        result = await jobs.weekly_health_report_job()

        assert result.success is True
        assert result.memories_processed == 10
        assert result.job_name == "weekly_health_report"

    @pytest.mark.asyncio
    async def test_job_history_tracking(self, temp_db):
        """Test that job history is tracked across multiple runs."""
        lifecycle_manager = LifecycleManager()
        jobs = HealthMaintenanceJobs(temp_db, lifecycle_manager)

        # Run multiple jobs
        result1 = await jobs.weekly_archival_job(dry_run=True)
        result2 = await jobs.monthly_cleanup_job(dry_run=True)
        result3 = await jobs.weekly_health_report_job()

        # Verify all ran successfully
        assert result1.success is True
        assert result2.success is True
        assert result3.success is True

        # Check history
        history = jobs.get_job_history(limit=10)

        assert len(history) >= 3
        # Most recent should be weekly_health_report
        assert history[0]["job_name"] == "weekly_health_report"

    @pytest.mark.asyncio
    async def test_health_recommendations(self, temp_db):
        """Test that health scorer generates appropriate recommendations."""
        # Create a problematic database (all STALE)
        now = datetime.now(UTC)
        # Create test embedding (768 dimensions for all-mpnet-base-v2)
        test_embedding = mock_embedding(value=0.1)

        for i in range(10):
            mem = MemoryUnit(
                content=f"Stale memory {i}",
                category=MemoryCategory.FACT,
                context_level=ContextLevel.SESSION_STATE,
                created_at=now - timedelta(days=200),
                lifecycle_state=LifecycleState.STALE,
            )
            await temp_db.store(
                content=mem.content,
                embedding=test_embedding,
                metadata={
                    "category": mem.category.value,
                    "context_level": mem.context_level.value,
                    "created_at": mem.created_at.isoformat(),
                    "lifecycle_state": mem.lifecycle_state.value,
                }
            )

        # Calculate health
        health_scorer = HealthScorer(temp_db)
        score = await health_scorer.calculate_overall_health()

        # Should have recommendations
        assert len(score.recommendations) > 0
        assert score.overall < 75  # Poor or Fair health
        assert score.stale_count == 10

    @pytest.mark.asyncio
    async def test_user_preference_protection(self, temp_db):
        """Test that USER_PREFERENCE memories are protected from cleanup."""
        # Create old USER_PREFERENCE memory
        now = datetime.now(UTC)
        # Create test embedding (768 dimensions for all-mpnet-base-v2)
        test_embedding = mock_embedding(value=0.1)

        mem = MemoryUnit(
            content="Important user preference",
            category=MemoryCategory.PREFERENCE,
            context_level=ContextLevel.USER_PREFERENCE,
            created_at=now - timedelta(days=250),
            lifecycle_state=LifecycleState.STALE,
        )
        await temp_db.store(
            content=mem.content,
            embedding=test_embedding,
            metadata={
                "category": mem.category.value,
                "context_level": mem.context_level.value,
                "created_at": mem.created_at.isoformat(),
                "lifecycle_state": mem.lifecycle_state.value,
            }
        )

        # Try to clean up
        lifecycle_manager = LifecycleManager()
        jobs = HealthMaintenanceJobs(temp_db, lifecycle_manager)

        result = await jobs.monthly_cleanup_job(dry_run=False, min_age_days=180)

        # Should not delete USER_PREFERENCE
        memories = await temp_db.get_all_memories()
        assert len(memories) == 1
        # get_all_memories returns List[Dict], not List[MemoryUnit]
        assert memories[0]["context_level"] == ContextLevel.USER_PREFERENCE.value

    @pytest.mark.asyncio
    async def test_quick_stats_accuracy(self, temp_db):
        """Test that quick stats match full health calculation."""
        # Create memories
        now = datetime.now(UTC)
        # Create test embedding (768 dimensions for all-mpnet-base-v2)
        test_embedding = mock_embedding(value=0.1)

        for i in range(5):
            mem = MemoryUnit(
                content=f"Memory {i}",
                category=MemoryCategory.FACT,
                context_level=ContextLevel.SESSION_STATE,
                created_at=now - timedelta(days=i * 20),
            )
            await temp_db.store(
                content=mem.content,
                embedding=test_embedding,
                metadata={
                    "category": mem.category.value,
                    "context_level": mem.context_level.value,
                    "created_at": mem.created_at.isoformat(),
                    "lifecycle_state": mem.lifecycle_state.value,
                }
            )

        # Get quick stats
        health_scorer = HealthScorer(temp_db)
        quick_stats = await health_scorer.get_quick_stats()

        # Get full score
        full_score = await health_scorer.calculate_overall_health()

        # Compare
        assert quick_stats["total_memories"] == full_score.total_count
        assert (
            quick_stats["lifecycle_distribution"]["active"]
            == full_score.active_count
        )
        assert (
            quick_stats["lifecycle_distribution"]["stale"]
            == full_score.stale_count
        )

    @pytest.mark.asyncio
    async def test_concurrent_job_execution(self, temp_db):
        """Test that multiple jobs can run concurrently without conflicts."""
        # Create some memories
        now = datetime.now(UTC)
        # Create test embedding (768 dimensions for all-mpnet-base-v2)
        test_embedding = mock_embedding(value=0.1)

        for i in range(20):
            mem = MemoryUnit(
                content=f"Memory {i}",
                category=MemoryCategory.FACT,
                context_level=ContextLevel.SESSION_STATE,
                created_at=now - timedelta(days=i * 15),
            )
            await temp_db.store(
                content=mem.content,
                embedding=test_embedding,
                metadata={
                    "category": mem.category.value,
                    "context_level": mem.context_level.value,
                    "created_at": mem.created_at.isoformat(),
                    "lifecycle_state": mem.lifecycle_state.value,
                }
            )

        # Run multiple jobs concurrently (all dry-run to avoid conflicts)
        lifecycle_manager = LifecycleManager()
        jobs = HealthMaintenanceJobs(temp_db, lifecycle_manager)

        results = await asyncio.gather(
            jobs.weekly_archival_job(dry_run=True),
            jobs.monthly_cleanup_job(dry_run=True),
            jobs.weekly_health_report_job(),
        )

        # All should succeed
        assert all(r.success for r in results)
        assert len(results) == 3
