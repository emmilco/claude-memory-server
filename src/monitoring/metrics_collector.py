"""
Metrics collection pipeline for health monitoring.

Collects performance, quality, database health, and usage metrics
from various sources and stores time-series data for trend analysis.
"""

import sqlite3
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from pathlib import Path

from src.core.models import ContextLevel, LifecycleState
from src.store.base import MemoryStore


@dataclass
class HealthMetrics:
    """Comprehensive health metrics snapshot."""

    timestamp: datetime

    # Performance metrics
    avg_search_latency_ms: float = 0.0
    p95_search_latency_ms: float = 0.0
    cache_hit_rate: float = 0.0
    index_staleness_ratio: float = 0.0

    # Quality metrics
    avg_result_relevance: float = 0.0
    noise_ratio: float = 0.0
    duplicate_rate: float = 0.0
    contradiction_rate: float = 0.0

    # Database health
    total_memories: int = 0
    active_memories: int = 0
    recent_memories: int = 0
    archived_memories: int = 0
    stale_memories: int = 0
    active_projects: int = 0
    archived_projects: int = 0
    database_size_mb: float = 0.0

    # Usage patterns
    queries_per_day: float = 0.0
    memories_created_per_day: float = 0.0
    avg_results_per_query: float = 0.0

    # Computed
    health_score: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary with ISO timestamp."""
        result = asdict(self)
        result["timestamp"] = self.timestamp.isoformat()
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "HealthMetrics":
        """Create from dictionary with ISO timestamp."""
        data["timestamp"] = datetime.fromisoformat(data["timestamp"])
        return cls(**data)


class MetricsCollector:
    """
    Collects health metrics from various sources.

    Responsibilities:
    - Collect performance, quality, database health, and usage metrics
    - Store time-series data in SQLite
    - Provide aggregation methods (daily, weekly, monthly)
    - Calculate derived metrics (ratios, averages)
    """

    def __init__(self, db_path: str, store: Optional[MemoryStore] = None):
        """
        Initialize metrics collector.

        Args:
            db_path: Path to SQLite database for storing metrics
            store: Vector store to query for metrics
        """
        self.db_path = db_path
        self.store = store
        self._init_db()

    def _init_db(self) -> None:
        """Initialize database schema for metrics storage."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Health metrics table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS health_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,

                    -- Performance
                    avg_search_latency_ms REAL,
                    p95_search_latency_ms REAL,
                    cache_hit_rate REAL,
                    index_staleness_ratio REAL,

                    -- Quality
                    avg_result_relevance REAL,
                    noise_ratio REAL,
                    duplicate_rate REAL,
                    contradiction_rate REAL,

                    -- Database health
                    total_memories INTEGER,
                    active_memories INTEGER,
                    recent_memories INTEGER,
                    archived_memories INTEGER,
                    stale_memories INTEGER,
                    active_projects INTEGER,
                    archived_projects INTEGER,
                    database_size_mb REAL,

                    -- Usage
                    queries_per_day REAL,
                    memories_created_per_day REAL,
                    avg_results_per_query REAL,

                    -- Computed
                    health_score INTEGER,

                    -- Metadata
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_health_metrics_timestamp
                ON health_metrics(timestamp)
                """
            )

            # Query log for tracking search performance
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS query_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    query TEXT NOT NULL,
                    latency_ms REAL NOT NULL,
                    result_count INTEGER NOT NULL,
                    avg_relevance REAL,
                    timestamp TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_query_log_timestamp
                ON query_log(timestamp)
                """
            )

            conn.commit()

    async def collect_metrics(self) -> HealthMetrics:
        """
        Collect current health metrics from all sources.

        Returns:
            HealthMetrics: Complete metrics snapshot
        """
        metrics = HealthMetrics(timestamp=datetime.utcnow())

        if self.store:
            # Collect database health metrics
            metrics.total_memories = await self._count_total_memories()
            metrics.active_memories = await self._count_memories_by_lifecycle(
                LifecycleState.ACTIVE
            )
            metrics.recent_memories = await self._count_memories_by_lifecycle(
                LifecycleState.RECENT
            )
            metrics.archived_memories = await self._count_memories_by_lifecycle(
                LifecycleState.ARCHIVED
            )
            metrics.stale_memories = await self._count_memories_by_lifecycle(
                LifecycleState.STALE
            )

            # Collect project metrics
            projects = await self._get_all_projects()
            metrics.active_projects = len(
                [p for p in projects if p.get("state") == "ACTIVE"]
            )
            metrics.archived_projects = len(
                [p for p in projects if p.get("state") == "ARCHIVED"]
            )

            # Collect quality metrics
            metrics.noise_ratio = await self._calculate_noise_ratio()
            metrics.duplicate_rate = await self._calculate_duplicate_rate()
            metrics.contradiction_rate = await self._calculate_contradiction_rate()

        # Collect performance metrics from query log
        metrics.avg_search_latency_ms = self._calculate_avg_latency()
        metrics.p95_search_latency_ms = self._calculate_p95_latency()
        metrics.avg_result_relevance = self._calculate_avg_relevance()

        # Collect usage metrics
        metrics.queries_per_day = self._calculate_queries_per_day()
        metrics.memories_created_per_day = self._calculate_memories_per_day()
        metrics.avg_results_per_query = self._calculate_avg_results_per_query()

        # Calculate cache metrics
        metrics.cache_hit_rate = await self._calculate_cache_hit_rate()
        metrics.index_staleness_ratio = await self._calculate_index_staleness()

        # Calculate database size
        metrics.database_size_mb = self._get_database_size_mb()

        return metrics

    async def _count_total_memories(self) -> int:
        """Count total memories in store."""
        if not self.store:
            return 0
        try:
            # Try to get count from store
            if hasattr(self.store, "count"):
                return await self.store.count()
            return 0
        except Exception:
            return 0

    async def _count_memories_by_lifecycle(self, state: LifecycleState) -> int:
        """Count memories in specific lifecycle state."""
        if not self.store:
            return 0
        try:
            # This would need to be implemented in stores
            if hasattr(self.store, "count_by_lifecycle"):
                return await self.store.count_by_lifecycle(state)
            return 0
        except Exception:
            return 0

    async def _get_all_projects(self) -> List[Dict[str, Any]]:
        """Get list of all projects with their states."""
        if not self.store:
            return []
        try:
            if hasattr(self.store, "get_all_projects"):
                return await self.store.get_all_projects()
            return []
        except Exception:
            return []

    async def _calculate_noise_ratio(self) -> float:
        """
        Calculate ratio of low-quality memories.

        Noise defined as: stale memories + very low access count + low confidence
        """
        if not self.store:
            return 0.0

        try:
            total = await self._count_total_memories()
            if total == 0:
                return 0.0

            stale = await self._count_memories_by_lifecycle(LifecycleState.STALE)

            # Noise = stale memories / total
            # This is a simplified calculation; could be enhanced
            return float(stale) / float(total)
        except Exception:
            return 0.0

    async def _calculate_duplicate_rate(self) -> float:
        """
        Calculate estimated duplicate memory rate.

        Would integrate with FEAT-035 (Memory Consolidation) when available.
        """
        # Placeholder - would need duplicate detection
        return 0.0

    async def _calculate_contradiction_rate(self) -> float:
        """
        Calculate estimated contradiction rate.

        Would integrate with FEAT-035 (Memory Consolidation) when available.
        """
        # Placeholder - would need contradiction detection
        return 0.0

    def _calculate_avg_latency(self, days: int = 1) -> float:
        """Calculate average search latency from query log."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()

            cursor.execute(
                """
                SELECT AVG(latency_ms)
                FROM query_log
                WHERE timestamp >= ?
                """,
                (cutoff,),
            )

            result = cursor.fetchone()
            return float(result[0]) if result[0] is not None else 0.0

    def _calculate_p95_latency(self, days: int = 1) -> float:
        """Calculate 95th percentile search latency."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()

            cursor.execute(
                """
                SELECT latency_ms
                FROM query_log
                WHERE timestamp >= ?
                ORDER BY latency_ms
                """,
                (cutoff,),
            )

            latencies = [row[0] for row in cursor.fetchall()]
            if not latencies:
                return 0.0

            p95_index = int(len(latencies) * 0.95)
            return float(latencies[p95_index])

    def _calculate_avg_relevance(self, days: int = 1) -> float:
        """Calculate average result relevance from query log."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()

            cursor.execute(
                """
                SELECT AVG(avg_relevance)
                FROM query_log
                WHERE timestamp >= ? AND avg_relevance IS NOT NULL
                """,
                (cutoff,),
            )

            result = cursor.fetchone()
            return float(result[0]) if result[0] is not None else 0.0

    def _calculate_queries_per_day(self, days: int = 7) -> float:
        """Calculate average queries per day."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()

            cursor.execute(
                """
                SELECT COUNT(*) as count
                FROM query_log
                WHERE timestamp >= ?
                """,
                (cutoff,),
            )

            result = cursor.fetchone()
            count = result[0] if result[0] is not None else 0
            return float(count) / float(days)

    def _calculate_memories_per_day(self, days: int = 7) -> float:
        """Calculate average memories created per day."""
        # This would need a creation timestamp in memories
        # Placeholder for now
        return 0.0

    def _calculate_avg_results_per_query(self, days: int = 7) -> float:
        """Calculate average number of results per query."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()

            cursor.execute(
                """
                SELECT AVG(result_count)
                FROM query_log
                WHERE timestamp >= ?
                """,
                (cutoff,),
            )

            result = cursor.fetchone()
            return float(result[0]) if result[0] is not None else 0.0

    async def _calculate_cache_hit_rate(self) -> float:
        """Calculate cache hit rate."""
        # This would integrate with embedding cache when instrumented
        # Placeholder for now
        return 0.75  # Assume 75% as baseline

    async def _calculate_index_staleness(self) -> float:
        """
        Calculate ratio of stale code indexes.

        An index is stale if it hasn't been updated in 30+ days.
        """
        # This would need index update tracking
        # Placeholder for now
        return 0.10  # Assume 10% staleness

    def _get_database_size_mb(self) -> float:
        """Get database size in MB."""
        try:
            db_path = Path(self.db_path)
            if db_path.exists():
                size_bytes = db_path.stat().st_size
                return size_bytes / (1024 * 1024)
            return 0.0
        except Exception:
            return 0.0

    def log_query(
        self,
        query: str,
        latency_ms: float,
        result_count: int,
        avg_relevance: Optional[float] = None,
    ) -> None:
        """
        Log a search query for metrics collection.

        Args:
            query: Search query text
            latency_ms: Query latency in milliseconds
            result_count: Number of results returned
            avg_relevance: Average relevance score of results
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO query_log (query, latency_ms, result_count, avg_relevance, timestamp)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    query,
                    latency_ms,
                    result_count,
                    avg_relevance,
                    datetime.utcnow().isoformat(),
                ),
            )
            conn.commit()

    def store_metrics(self, metrics: HealthMetrics) -> None:
        """
        Store metrics snapshot in database.

        Args:
            metrics: Health metrics to store
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO health_metrics (
                    timestamp,
                    avg_search_latency_ms, p95_search_latency_ms,
                    cache_hit_rate, index_staleness_ratio,
                    avg_result_relevance, noise_ratio,
                    duplicate_rate, contradiction_rate,
                    total_memories, active_memories, recent_memories,
                    archived_memories, stale_memories,
                    active_projects, archived_projects, database_size_mb,
                    queries_per_day, memories_created_per_day, avg_results_per_query,
                    health_score
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    metrics.timestamp.isoformat(),
                    metrics.avg_search_latency_ms,
                    metrics.p95_search_latency_ms,
                    metrics.cache_hit_rate,
                    metrics.index_staleness_ratio,
                    metrics.avg_result_relevance,
                    metrics.noise_ratio,
                    metrics.duplicate_rate,
                    metrics.contradiction_rate,
                    metrics.total_memories,
                    metrics.active_memories,
                    metrics.recent_memories,
                    metrics.archived_memories,
                    metrics.stale_memories,
                    metrics.active_projects,
                    metrics.archived_projects,
                    metrics.database_size_mb,
                    metrics.queries_per_day,
                    metrics.memories_created_per_day,
                    metrics.avg_results_per_query,
                    metrics.health_score,
                ),
            )
            conn.commit()

    def get_latest_metrics(self) -> Optional[HealthMetrics]:
        """
        Get most recent metrics snapshot.

        Returns:
            Latest HealthMetrics or None if no metrics stored
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM health_metrics
                ORDER BY timestamp DESC
                LIMIT 1
                """
            )

            row = cursor.fetchone()
            if not row:
                return None

            return self._row_to_metrics(row)

    def get_metrics_history(
        self, days: int = 7
    ) -> List[HealthMetrics]:
        """
        Get historical metrics for the specified time period.

        Args:
            days: Number of days of history to retrieve

        Returns:
            List of HealthMetrics, ordered by timestamp
        """
        cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM health_metrics
                WHERE timestamp >= ?
                ORDER BY timestamp ASC
                """,
                (cutoff,),
            )

            return [self._row_to_metrics(row) for row in cursor.fetchall()]

    def get_daily_aggregate(self, days: int = 30) -> List[HealthMetrics]:
        """
        Get daily aggregated metrics.

        Args:
            days: Number of days to aggregate

        Returns:
            List of daily averaged HealthMetrics
        """
        cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT
                    DATE(timestamp) as date,
                    AVG(avg_search_latency_ms),
                    AVG(p95_search_latency_ms),
                    AVG(cache_hit_rate),
                    AVG(index_staleness_ratio),
                    AVG(avg_result_relevance),
                    AVG(noise_ratio),
                    AVG(duplicate_rate),
                    AVG(contradiction_rate),
                    AVG(total_memories),
                    AVG(active_memories),
                    AVG(recent_memories),
                    AVG(archived_memories),
                    AVG(stale_memories),
                    AVG(active_projects),
                    AVG(archived_projects),
                    AVG(database_size_mb),
                    AVG(queries_per_day),
                    AVG(memories_created_per_day),
                    AVG(avg_results_per_query),
                    AVG(health_score)
                FROM health_metrics
                WHERE timestamp >= ?
                GROUP BY DATE(timestamp)
                ORDER BY date ASC
                """,
                (cutoff,),
            )

            results = []
            for row in cursor.fetchall():
                # Convert date string to datetime
                date_str = row[0]
                timestamp = datetime.fromisoformat(f"{date_str}T00:00:00")

                metrics = HealthMetrics(
                    timestamp=timestamp,
                    avg_search_latency_ms=row[1] or 0.0,
                    p95_search_latency_ms=row[2] or 0.0,
                    cache_hit_rate=row[3] or 0.0,
                    index_staleness_ratio=row[4] or 0.0,
                    avg_result_relevance=row[5] or 0.0,
                    noise_ratio=row[6] or 0.0,
                    duplicate_rate=row[7] or 0.0,
                    contradiction_rate=row[8] or 0.0,
                    total_memories=int(row[9] or 0),
                    active_memories=int(row[10] or 0),
                    recent_memories=int(row[11] or 0),
                    archived_memories=int(row[12] or 0),
                    stale_memories=int(row[13] or 0),
                    active_projects=int(row[14] or 0),
                    archived_projects=int(row[15] or 0),
                    database_size_mb=row[16] or 0.0,
                    queries_per_day=row[17] or 0.0,
                    memories_created_per_day=row[18] or 0.0,
                    avg_results_per_query=row[19] or 0.0,
                    health_score=int(row[20] or 0),
                )
                results.append(metrics)

            return results

    def _row_to_metrics(self, row: tuple) -> HealthMetrics:
        """Convert database row to HealthMetrics object."""
        return HealthMetrics(
            timestamp=datetime.fromisoformat(row[1]),
            avg_search_latency_ms=row[2] or 0.0,
            p95_search_latency_ms=row[3] or 0.0,
            cache_hit_rate=row[4] or 0.0,
            index_staleness_ratio=row[5] or 0.0,
            avg_result_relevance=row[6] or 0.0,
            noise_ratio=row[7] or 0.0,
            duplicate_rate=row[8] or 0.0,
            contradiction_rate=row[9] or 0.0,
            total_memories=row[10] or 0,
            active_memories=row[11] or 0,
            recent_memories=row[12] or 0,
            archived_memories=row[13] or 0,
            stale_memories=row[14] or 0,
            active_projects=row[15] or 0,
            archived_projects=row[16] or 0,
            database_size_mb=row[17] or 0.0,
            queries_per_day=row[18] or 0.0,
            memories_created_per_day=row[19] or 0.0,
            avg_results_per_query=row[20] or 0.0,
            health_score=row[21] or 0,
        )

    def cleanup_old_metrics(self, retention_days: int = 90) -> int:
        """
        Clean up metrics older than retention period.

        Args:
            retention_days: Number of days to retain metrics

        Returns:
            Number of records deleted
        """
        cutoff = (datetime.utcnow() - timedelta(days=retention_days)).isoformat()

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Delete old metrics
            cursor.execute(
                """
                DELETE FROM health_metrics
                WHERE timestamp < ?
                """,
                (cutoff,),
            )

            deleted_metrics = cursor.rowcount

            # Delete old query logs
            cursor.execute(
                """
                DELETE FROM query_log
                WHERE timestamp < ?
                """,
                (cutoff,),
            )

            deleted_queries = cursor.rowcount

            conn.commit()

            return deleted_metrics + deleted_queries
