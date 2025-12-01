"""Analytics Service - Usage analytics and pattern tracking.

Extracted from MemoryRAGServer (REF-016) to provide focused analytics operations.

Responsibilities:
- Track usage patterns
- Analyze query performance
- Provide usage statistics
- Monitor frequently accessed code
"""

import asyncio
import logging
import threading
from typing import Optional, Dict, Any

from src.config import ServerConfig
from src.store import MemoryStore
from src.core.exceptions import StorageError
from src.core.tracing import get_logger

logger = get_logger(__name__)


class AnalyticsService:
    """
    Service for usage analytics and pattern tracking.

    This service tracks usage patterns, analyzes query performance,
    and provides insights into frequently accessed content.
    """

    def __init__(
        self,
        store: MemoryStore,
        config: ServerConfig,
        usage_tracker: Optional[Any] = None,
        pattern_tracker: Optional[Any] = None,
        metrics_collector: Optional[Any] = None,
    ):
        """
        Initialize the Analytics Service.

        Args:
            store: Memory store backend
            config: Server configuration
            usage_tracker: Usage tracker for memory access patterns
            pattern_tracker: Pattern tracker for usage analytics
            metrics_collector: Metrics collector for performance tracking
        """
        self.store = store
        self.config = config
        self.usage_tracker = usage_tracker
        self.pattern_tracker = pattern_tracker
        self.metrics_collector = metrics_collector

        # Service statistics
        self.stats = {
            "analytics_queries": 0,
        }
        self._stats_lock = threading.Lock()

    def get_stats(self) -> Dict[str, Any]:
        """Get analytics service statistics."""
        with self._stats_lock:
            return self.stats.copy()

    async def get_usage_statistics(self, days: int = 30) -> Dict[str, Any]:
        """
        Get overall usage statistics.

        Args:
            days: Number of days to look back

        Returns:
            Dict with usage statistics

        Raises:
            StorageError: If pattern tracker is not configured or retrieval fails
        """
        with self._stats_lock:
            self.stats["analytics_queries"] += 1

        if not self.pattern_tracker:
            raise StorageError("Usage pattern tracking is not configured")

        try:
            stats = self.pattern_tracker.get_usage_statistics(days=days)

            return {
                "status": "success",
                "statistics": stats,
                "period_days": days,
            }

        except Exception as e:
            logger.error(f"Failed to get usage statistics: {e}", exc_info=True)
            raise StorageError(f"Failed to get usage statistics: {e}") from e

    async def get_top_queries(
        self,
        limit: int = 10,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Get most frequently executed queries.

        Args:
            limit: Maximum number of queries to return
            days: Number of days to look back

        Returns:
            Dict with top queries

        Raises:
            StorageError: If pattern tracker is not configured or retrieval fails
        """
        with self._stats_lock:
            self.stats["analytics_queries"] += 1

        if not self.pattern_tracker:
            raise StorageError("Usage pattern tracking is not configured")

        try:
            queries = self.pattern_tracker.get_top_queries(
                limit=limit,
                days=days
            )

            return {
                "status": "success",
                "queries": queries,
                "total_count": len(queries),
                "period_days": days,
            }

        except Exception as e:
            logger.error(f"Failed to get top queries: {e}", exc_info=True)
            raise StorageError(f"Failed to get top queries: {e}") from e

    async def get_frequently_accessed_code(
        self,
        limit: int = 10,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Get most frequently accessed code files and functions.

        Args:
            limit: Maximum number of items to return
            days: Number of days to look back

        Returns:
            Dict with frequently accessed code

        Raises:
            StorageError: If pattern tracker is not configured or retrieval fails
        """
        with self._stats_lock:
            self.stats["analytics_queries"] += 1

        if not self.pattern_tracker:
            raise StorageError("Usage pattern tracking is not configured")

        try:
            code = self.pattern_tracker.get_frequently_accessed_code(
                limit=limit,
                days=days
            )

            return {
                "status": "success",
                "frequently_accessed": code,
                "total_count": len(code),
                "period_days": days,
            }

        except Exception as e:
            logger.error(f"Failed to get frequently accessed code: {e}", exc_info=True)
            raise StorageError(f"Failed to get frequently accessed code: {e}") from e

    async def get_token_analytics(
        self,
        period_days: int = 30,
        session_id: Optional[str] = None,
        project_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get token usage analytics and cost savings.

        Args:
            period_days: Number of days to analyze
            session_id: Filter by specific session ID
            project_name: Filter by specific project

        Returns:
            Dict with token analytics

        Raises:
            StorageError: If usage tracker is not configured or retrieval fails
        """
        with self._stats_lock:
            self.stats["analytics_queries"] += 1

        if not self.usage_tracker:
            raise StorageError("Usage tracking is not configured")

        try:
            analytics = await self.usage_tracker.get_token_analytics(
                period_days=period_days,
                session_id=session_id,
                project_name=project_name,
            )

            return {
                "status": "success",
                "analytics": analytics,
                "period_days": period_days,
            }

        except Exception as e:
            logger.error(f"Failed to get token analytics: {e}", exc_info=True)
            raise StorageError(f"Failed to get token analytics: {e}") from e

    async def submit_search_feedback(
        self,
        search_id: str,
        query: str,
        result_ids: list,
        rating: str,
        comment: Optional[str] = None,
        project_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Submit user feedback for a search query.

        Args:
            search_id: Unique ID of the search
            query: Search query text
            result_ids: List of result memory IDs
            rating: 'helpful' or 'not_helpful'
            comment: Optional user comment
            project_name: Optional project context

        Returns:
            Dict with feedback ID and status
        """
        try:
            try:
                async with asyncio.timeout(30.0):
                    feedback_id = await self.store.submit_search_feedback(
                        search_id=search_id,
                        query=query,
                        result_ids=result_ids,
                        rating=rating,
                        comment=comment,
                        project_name=project_name,
                    )
            except TimeoutError:
                logger.error("Submit search feedback operation timed out after 30s")
                raise StorageError("Submit search feedback operation timed out")

            logger.info(f"Submitted feedback {feedback_id} for search {search_id}")

            return {
                "status": "success",
                "feedback_id": feedback_id,
                "search_id": search_id,
                "rating": rating,
            }

        except Exception as e:
            logger.error(f"Failed to submit search feedback: {e}", exc_info=True)
            raise StorageError(f"Failed to submit search feedback: {e}") from e

    async def get_quality_metrics(
        self,
        time_range_hours: int = 24,
        project_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get aggregated quality metrics for search results.

        Args:
            time_range_hours: Number of hours to look back
            project_name: Optional project filter

        Returns:
            Dict with quality metrics
        """
        try:
            try:
                async with asyncio.timeout(30.0):
                    metrics = await self.store.get_quality_metrics(
                        time_range_hours=time_range_hours,
                        project_name=project_name,
                    )
            except TimeoutError:
                logger.error("Get quality metrics operation timed out after 30s")
                raise StorageError("Get quality metrics operation timed out")

            logger.info(
                f"Retrieved quality metrics: {metrics.get('total_searches', 0)} searches, "
                f"{metrics.get('helpfulness_rate', 0):.2%} helpful"
            )

            return {
                "status": "success",
                "metrics": metrics,
            }

        except Exception as e:
            logger.error(f"Failed to retrieve quality metrics: {e}", exc_info=True)
            raise StorageError(f"Failed to retrieve quality metrics: {e}") from e
