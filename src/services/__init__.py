"""Service layer for Claude Memory RAG Server.

This module provides focused service classes extracted from the monolithic
MemoryRAGServer class (REF-016). Each service has a single responsibility:

- MemoryService: Memory CRUD operations and lifecycle management
- CodeIndexingService: Code indexing, search, and dependency analysis
- CrossProjectService: Multi-project search and consent management
- HealthService: Health monitoring, metrics, and alerting
- QueryService: Query expansion, conversation tracking, suggestions
- AnalyticsService: Usage analytics and pattern tracking
"""

from src.services.memory_service import MemoryService
from src.services.code_indexing_service import CodeIndexingService
from src.services.cross_project_service import CrossProjectService
from src.services.health_service import HealthService
from src.services.query_service import QueryService
from src.services.analytics_service import AnalyticsService

__all__ = [
    "MemoryService",
    "CodeIndexingService",
    "CrossProjectService",
    "HealthService",
    "QueryService",
    "AnalyticsService",
]
