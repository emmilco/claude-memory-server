"""Connection health checking for Qdrant connection pool.

Provides multi-tiered health checking:
- Fast check (<50ms): Basic ping/readiness
- Medium check (<100ms): Collection listing
- Deep check (<200ms): Actual query test

Supports auto-healing by identifying unhealthy connections for replacement.

PERF-007: Connection Pooling - Day 2 Health Checking
Note: Timeouts increased from (1ms/10ms/50ms) to be more realistic for CI and production
"""

import asyncio
import logging
import time
from enum import Enum
from typing import Optional
from dataclasses import dataclass

from qdrant_client import QdrantClient
from qdrant_client.http.exceptions import UnexpectedResponse, ResponseHandlingException

logger = logging.getLogger(__name__)


class HealthCheckLevel(Enum):
    """Health check thoroughness levels."""

    FAST = "fast"      # <1ms: ping/readiness check
    MEDIUM = "medium"  # <10ms: collection list
    DEEP = "deep"      # <50ms: actual query test


@dataclass
class HealthCheckResult:
    """Result of a health check operation."""

    healthy: bool
    level: HealthCheckLevel
    duration_ms: float
    error: Optional[str] = None

    def __repr__(self) -> str:
        status = "healthy" if self.healthy else "unhealthy"
        error_info = f", error={self.error}" if self.error else ""
        return f"HealthCheckResult({status}, {self.level.value}, {self.duration_ms:.2f}ms{error_info})"


class ConnectionHealthChecker:
    """Health checker for Qdrant connections.

    Provides three levels of health checking:
    1. Fast (<50ms): Basic connectivity via collection listing
    2. Medium (<100ms): Collection listing with validation
    3. Deep (<200ms): Actual search query

    Example:
        >>> checker = ConnectionHealthChecker()
        >>> result = await checker.check_health(client, HealthCheckLevel.FAST)
        >>> if not result.healthy:
        >>>     # Replace connection
        >>>     pass
    """

    def __init__(
        self,
        fast_timeout: float = 0.05,     # 50ms (was 1ms - too aggressive)
        medium_timeout: float = 0.1,    # 100ms (was 10ms)
        deep_timeout: float = 0.2,      # 200ms (was 50ms)
    ):
        """Initialize health checker.

        Args:
            fast_timeout: Timeout for fast health checks (seconds)
            medium_timeout: Timeout for medium health checks (seconds)
            deep_timeout: Timeout for deep health checks (seconds)
        """
        self.fast_timeout = fast_timeout
        self.medium_timeout = medium_timeout
        self.deep_timeout = deep_timeout

        # Stats
        self.total_checks = 0
        self.total_failures = 0
        self.checks_by_level = {level: 0 for level in HealthCheckLevel}
        self.failures_by_level = {level: 0 for level in HealthCheckLevel}

        logger.debug(
            f"Health checker initialized: fast={fast_timeout*1000:.1f}ms, "
            f"medium={medium_timeout*1000:.1f}ms, deep={deep_timeout*1000:.1f}ms"
        )

    async def check_health(
        self,
        client: QdrantClient,
        level: HealthCheckLevel = HealthCheckLevel.FAST,
    ) -> HealthCheckResult:
        """Check connection health at specified level.

        Args:
            client: QdrantClient to check
            level: Health check level (FAST, MEDIUM, or DEEP)

        Returns:
            HealthCheckResult with health status and timing
        """
        self.total_checks += 1
        self.checks_by_level[level] += 1

        start_time = time.perf_counter()

        try:
            if level == HealthCheckLevel.FAST:
                healthy = await self._fast_check(client)
            elif level == HealthCheckLevel.MEDIUM:
                healthy = await self._medium_check(client)
            elif level == HealthCheckLevel.DEEP:
                healthy = await self._deep_check(client)
            else:
                raise ValueError(f"Unknown health check level: {level}")

            duration_ms = (time.perf_counter() - start_time) * 1000

            if not healthy:
                self.total_failures += 1
                self.failures_by_level[level] += 1

            return HealthCheckResult(
                healthy=healthy,
                level=level,
                duration_ms=duration_ms,
            )

        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            self.total_failures += 1
            self.failures_by_level[level] += 1

            logger.warning(f"Health check failed: {e}")

            return HealthCheckResult(
                healthy=False,
                level=level,
                duration_ms=duration_ms,
                error=str(e),
            )

    async def _fast_check(self, client: QdrantClient) -> bool:
        """Fast health check using root endpoint.

        Args:
            client: QdrantClient to check

        Returns:
            bool: True if healthy
        """
        try:
            # Use asyncio timeout to enforce <1ms limit
            async def check():
                # Try to access root endpoint or healthz
                # For Qdrant, we'll use a lightweight operation
                # Note: QdrantClient is sync, so we run in executor
                loop = asyncio.get_event_loop()
                return await loop.run_in_executor(
                    None,
                    lambda: client.get_collections()  # Lightweight operation
                )

            await asyncio.wait_for(check(), timeout=self.fast_timeout)
            return True

        except asyncio.TimeoutError:
            logger.debug(f"Fast health check timeout (>{self.fast_timeout*1000:.1f}ms)")
            return False
        except (UnexpectedResponse, ResponseHandlingException, ConnectionError) as e:
            logger.debug(f"Fast health check connection error: {e}")
            return False
        except Exception as e:
            logger.debug(f"Fast health check failed: {e}")
            return False

    async def _medium_check(self, client: QdrantClient) -> bool:
        """Medium health check using collection listing.

        Args:
            client: QdrantClient to check

        Returns:
            bool: True if healthy
        """
        try:
            async def check():
                loop = asyncio.get_event_loop()
                collections = await loop.run_in_executor(
                    None,
                    client.get_collections
                )
                # Verify we got a valid response
                return collections is not None

            result = await asyncio.wait_for(check(), timeout=self.medium_timeout)
            return result

        except asyncio.TimeoutError:
            logger.debug(f"Medium health check timeout (>{self.medium_timeout*1000:.1f}ms)")
            return False
        except (UnexpectedResponse, ResponseHandlingException, ConnectionError) as e:
            logger.debug(f"Medium health check connection error: {e}")
            return False
        except Exception as e:
            logger.debug(f"Medium health check failed: {e}")
            return False

    async def _deep_check(self, client: QdrantClient) -> bool:
        """Deep health check using actual query.

        Args:
            client: QdrantClient to check

        Returns:
            bool: True if healthy
        """
        try:
            async def check():
                loop = asyncio.get_event_loop()

                # Get collections first
                collections = await loop.run_in_executor(
                    None,
                    client.get_collections
                )

                if not collections or not collections.collections:
                    # No collections to query, but connection works
                    return True

                # Try to count points in first collection (lightweight query)
                first_collection = collections.collections[0].name
                count = await loop.run_in_executor(
                    None,
                    client.count,
                    first_collection
                )

                return count is not None

            result = await asyncio.wait_for(check(), timeout=self.deep_timeout)
            return result

        except asyncio.TimeoutError:
            logger.debug(f"Deep health check timeout (>{self.deep_timeout*1000:.1f}ms)")
            return False
        except (UnexpectedResponse, ResponseHandlingException, ConnectionError) as e:
            logger.debug(f"Deep health check connection error: {e}")
            return False
        except Exception as e:
            logger.debug(f"Deep health check failed: {e}")
            return False

    def get_stats(self) -> dict:
        """Get health checker statistics.

        Returns:
            dict: Statistics including total checks, failures, and per-level metrics
        """
        failure_rate = (self.total_failures / self.total_checks * 100) if self.total_checks > 0 else 0.0

        return {
            "total_checks": self.total_checks,
            "total_failures": self.total_failures,
            "failure_rate_percent": round(failure_rate, 2),
            "checks_by_level": {
                level.value: count
                for level, count in self.checks_by_level.items()
            },
            "failures_by_level": {
                level.value: count
                for level, count in self.failures_by_level.items()
            },
        }

    def reset_stats(self) -> None:
        """Reset health check statistics."""
        self.total_checks = 0
        self.total_failures = 0
        self.checks_by_level = {level: 0 for level in HealthCheckLevel}
        self.failures_by_level = {level: 0 for level in HealthCheckLevel}
        logger.debug("Health checker stats reset")
