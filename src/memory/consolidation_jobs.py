"""Background jobs for automatic memory consolidation (FEAT-035 Phase 4)."""

import logging
import asyncio
from typing import Optional
from datetime import datetime, UTC
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.job import Job

from src.config import get_config
from src.memory.duplicate_detector import DuplicateDetector
from src.memory.consolidation_engine import ConsolidationEngine, MergeStrategy
from src.embeddings.generator import EmbeddingGenerator
from src.core.models import MemoryCategory

logger = logging.getLogger(__name__)


class ConsolidationScheduler:
    """
    Automated memory consolidation scheduler.

    Runs background jobs to maintain memory database quality:
    - Daily (2 AM): Auto-merge high-confidence duplicates (>0.95)
    - Weekly (Sunday 3 AM): Scan for medium-confidence duplicates
    - Monthly (1st, 3 AM): Full contradiction scan
    """

    def __init__(
        self,
        scheduler: Optional[AsyncIOScheduler] = None,
        enable_daily: bool = True,
        enable_weekly: bool = True,
        enable_monthly: bool = True,
    ):
        """
        Initialize consolidation scheduler.

        Args:
            scheduler: Optional existing scheduler (creates new one if None)
            enable_daily: Enable daily auto-merge jobs
            enable_weekly: Enable weekly review notifications
            enable_monthly: Enable monthly contradiction scans
        """
        self.scheduler = scheduler or AsyncIOScheduler()
        self.enable_daily = enable_daily
        self.enable_weekly = enable_weekly
        self.enable_monthly = enable_monthly

        # Track job references
        self.daily_job: Optional[Job] = None
        self.weekly_job: Optional[Job] = None
        self.monthly_job: Optional[Job] = None

        # Stats tracking
        self.stats = {
            "last_daily_run": None,
            "last_weekly_run": None,
            "last_monthly_run": None,
            "total_auto_merges": 0,
            "total_review_candidates": 0,
            "total_contradictions_found": 0,
        }

        logger.info("ConsolidationScheduler initialized")

    def start(self):
        """Start the scheduler and register jobs."""
        try:
            # Register jobs
            if self.enable_daily:
                self.daily_job = self.scheduler.add_job(
                    self._daily_auto_merge,
                    trigger=CronTrigger(hour=2, minute=0),  # 2:00 AM daily
                    id="consolidation_daily_merge",
                    name="Daily Auto-Merge High-Confidence Duplicates",
                    replace_existing=True,
                )
                logger.info("Registered daily auto-merge job (2:00 AM)")

            if self.enable_weekly:
                self.weekly_job = self.scheduler.add_job(
                    self._weekly_review_scan,
                    trigger=CronTrigger(day_of_week="sun", hour=3, minute=0),  # Sunday 3:00 AM
                    id="consolidation_weekly_review",
                    name="Weekly Duplicate Review Scan",
                    replace_existing=True,
                )
                logger.info("Registered weekly review scan job (Sunday 3:00 AM)")

            if self.enable_monthly:
                self.monthly_job = self.scheduler.add_job(
                    self._monthly_contradiction_scan,
                    trigger=CronTrigger(day=1, hour=3, minute=0),  # 1st of month, 3:00 AM
                    id="consolidation_monthly_contradictions",
                    name="Monthly Contradiction Scan",
                    replace_existing=True,
                )
                logger.info("Registered monthly contradiction scan job (1st, 3:00 AM)")

            # Start scheduler if not already running
            if not self.scheduler.running:
                self.scheduler.start()
                logger.info("ConsolidationScheduler started successfully")

        except Exception as e:
            logger.error(f"Error starting ConsolidationScheduler: {e}", exc_info=True)
            raise

    def stop(self):
        """Stop the scheduler gracefully."""
        try:
            if self.scheduler.running:
                self.scheduler.shutdown(wait=True)
                logger.info("ConsolidationScheduler stopped")
        except Exception as e:
            logger.error(f"Error stopping ConsolidationScheduler: {e}", exc_info=True)

    async def _daily_auto_merge(self):
        """
        Daily job: Auto-merge high-confidence duplicates.

        Runs at 2:00 AM daily to automatically merge duplicates with >0.95 similarity.
        This is safe because high similarity indicates near-identical content.
        """
        logger.info("Starting daily auto-merge job")
        try:
            config = get_config()

            # Initialize components
            if config.storage_backend == "qdrant":
                from src.store.qdrant_store import QdrantMemoryStore
                store = QdrantMemoryStore(config)
            else:
                from src.store.sqlite_store import SQLiteMemoryStore
                store = SQLiteMemoryStore(config)

            await store.initialize()

            embedding_gen = EmbeddingGenerator()
            detector = DuplicateDetector(store, embedding_gen)
            engine = ConsolidationEngine(store)

            # Get auto-merge candidates (>0.95 similarity)
            candidates = await detector.get_auto_merge_candidates()

            merge_count = 0
            for canonical_id, duplicates in candidates.items():
                # Get canonical memory
                canonical = await store.get_by_id(canonical_id)
                if not canonical:
                    continue

                # Extract duplicate IDs
                duplicate_ids = [dup_id for dup_id, _ in duplicates]

                # Merge using KEEP_MOST_RECENT strategy
                result = await engine.merge_memories(
                    canonical_id=canonical_id,
                    duplicate_ids=duplicate_ids,
                    strategy=MergeStrategy.KEEP_MOST_RECENT,
                    dry_run=False,
                )

                if result:
                    merge_count += 1

            # Update stats
            self.stats["last_daily_run"] = datetime.now(UTC)
            self.stats["total_auto_merges"] += merge_count

            logger.info(f"Daily auto-merge completed: {merge_count} merges performed")

        except Exception as e:
            logger.error(f"Error in daily auto-merge job: {e}", exc_info=True)

    async def _weekly_review_scan(self):
        """
        Weekly job: Scan for medium-confidence duplicates.

        Runs on Sunday at 3:00 AM to identify duplicates that need user review.
        Saves results to a file for user to review via CLI.
        """
        logger.info("Starting weekly duplicate review scan")
        try:
            config = get_config()

            # Initialize components
            if config.storage_backend == "qdrant":
                from src.store.qdrant_store import QdrantMemoryStore
                store = QdrantMemoryStore(config)
            else:
                from src.store.sqlite_store import SQLiteMemoryStore
                store = SQLiteMemoryStore(config)

            await store.initialize()

            embedding_gen = EmbeddingGenerator()
            detector = DuplicateDetector(store, embedding_gen)

            # Get user review candidates (0.85-0.95 similarity)
            candidates = await detector.get_user_review_candidates()

            if candidates:
                # Save review candidates to file
                review_file = Path.home() / ".claude-rag" / "weekly_review_candidates.txt"
                review_file.parent.mkdir(parents=True, exist_ok=True)

                with review_file.open("w") as f:
                    f.write(f"Weekly Duplicate Review - {datetime.now(UTC).isoformat()}\n")
                    f.write("=" * 80 + "\n\n")
                    f.write(f"Found {len(candidates)} duplicate groups needing review.\n\n")
                    f.write("Run: python -m src.cli consolidate --interactive\n\n")

                    for idx, (canonical_id, duplicates) in enumerate(candidates.items(), 1):
                        f.write(f"{idx}. Canonical ID: {canonical_id}\n")
                        f.write(f"   Duplicates: {len(duplicates)}\n")
                        for dup_id, score in duplicates:
                            f.write(f"     - {dup_id} (similarity: {score:.3f})\n")
                        f.write("\n")

                # Update stats
                self.stats["last_weekly_run"] = datetime.now(UTC)
                self.stats["total_review_candidates"] += len(candidates)

                logger.info(
                    f"Weekly review scan completed: {len(candidates)} groups need review. "
                    f"Saved to {review_file}"
                )
            else:
                logger.info("Weekly review scan completed: No duplicates needing review")

        except Exception as e:
            logger.error(f"Error in weekly review scan job: {e}", exc_info=True)

    async def _monthly_contradiction_scan(self):
        """
        Monthly job: Full contradiction scan.

        Runs on the 1st of each month at 3:00 AM to detect contradictory
        preferences and facts. Saves results to file for user review.
        """
        logger.info("Starting monthly contradiction scan")
        try:
            config = get_config()

            # Initialize components
            if config.storage_backend == "qdrant":
                from src.store.qdrant_store import QdrantMemoryStore
                store = QdrantMemoryStore(config)
            else:
                from src.store.sqlite_store import SQLiteMemoryStore
                store = SQLiteMemoryStore(config)

            await store.initialize()

            embedding_gen = EmbeddingGenerator()
            from src.memory.relationship_detector import RelationshipDetector
            detector = RelationshipDetector(store, embedding_gen)

            # Scan for contradictions in preferences
            contradictions = await detector.scan_for_contradictions(
                category=MemoryCategory.PREFERENCE
            )

            if contradictions:
                # Save contradictions to file
                report_file = Path.home() / ".claude-rag" / "monthly_contradiction_report.txt"
                report_file.parent.mkdir(parents=True, exist_ok=True)

                with report_file.open("w") as f:
                    f.write(f"Monthly Contradiction Report - {datetime.now(UTC).isoformat()}\n")
                    f.write("=" * 80 + "\n\n")
                    f.write(f"Found {len(contradictions)} contradictions.\n\n")
                    f.write("Run: python -m src.cli verify --contradictions\n\n")

                    for idx, (memory_a, memory_b, confidence) in enumerate(contradictions, 1):
                        f.write(f"{idx}. Contradiction (confidence: {confidence:.2f})\n")
                        f.write(f"   Memory A ({memory_a.id}): {memory_a.content[:80]}...\n")
                        f.write(f"   Memory B ({memory_b.id}): {memory_b.content[:80]}...\n")
                        f.write("\n")

                # Update stats
                self.stats["last_monthly_run"] = datetime.now(UTC)
                self.stats["total_contradictions_found"] += len(contradictions)

                logger.info(
                    f"Monthly contradiction scan completed: {len(contradictions)} contradictions found. "
                    f"Saved to {report_file}"
                )
            else:
                logger.info("Monthly contradiction scan completed: No contradictions found")

        except Exception as e:
            logger.error(f"Error in monthly contradiction scan job: {e}", exc_info=True)

    def get_stats(self) -> dict:
        """Get scheduler statistics."""
        return {
            **self.stats,
            "is_running": self.scheduler.running,
            "daily_job_enabled": self.daily_job is not None,
            "weekly_job_enabled": self.weekly_job is not None,
            "monthly_job_enabled": self.monthly_job is not None,
            "next_daily_run": self.daily_job.next_run_time if self.daily_job else None,
            "next_weekly_run": self.weekly_job.next_run_time if self.weekly_job else None,
            "next_monthly_run": self.monthly_job.next_run_time if self.monthly_job else None,
        }


# Global scheduler instance
_global_scheduler: Optional[ConsolidationScheduler] = None


def get_global_scheduler() -> ConsolidationScheduler:
    """
    Get the global consolidation scheduler instance.

    Creates and starts the scheduler if it doesn't exist.

    Returns:
        Global scheduler instance
    """
    global _global_scheduler

    if _global_scheduler is None:
        _global_scheduler = ConsolidationScheduler()
        _global_scheduler.start()
        logger.info("Global consolidation scheduler created and started")

    return _global_scheduler


def stop_global_scheduler():
    """Stop the global consolidation scheduler."""
    global _global_scheduler

    if _global_scheduler is not None:
        _global_scheduler.stop()
        _global_scheduler = None
        logger.info("Global consolidation scheduler stopped")


# Standalone execution for testing
async def run_daily_job():
    """Run daily job once for testing."""
    scheduler = ConsolidationScheduler(enable_daily=True, enable_weekly=False, enable_monthly=False)
    await scheduler._daily_auto_merge()
    logger.info("Daily job completed")


async def run_weekly_job():
    """Run weekly job once for testing."""
    scheduler = ConsolidationScheduler(enable_daily=False, enable_weekly=True, enable_monthly=False)
    await scheduler._weekly_review_scan()
    logger.info("Weekly job completed")


async def run_monthly_job():
    """Run monthly job once for testing."""
    scheduler = ConsolidationScheduler(enable_daily=False, enable_weekly=False, enable_monthly=True)
    await scheduler._monthly_contradiction_scan()
    logger.info("Monthly job completed")


if __name__ == "__main__":
    # Test by running all jobs once
    import argparse

    parser = argparse.ArgumentParser(description="Test consolidation jobs")
    parser.add_argument("--job", choices=["daily", "weekly", "monthly", "all"], default="all")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    if args.job in ["daily", "all"]:
        asyncio.run(run_daily_job())

    if args.job in ["weekly", "all"]:
        asyncio.run(run_weekly_job())

    if args.job in ["monthly", "all"]:
        asyncio.run(run_monthly_job())
