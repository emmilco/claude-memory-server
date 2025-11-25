# REF-016: Split MemoryRAGServer God Class

## Reference
- **Code Review:** ARCH-001 (Critical severity)
- **Issue:** MemoryRAGServer is 4,767 lines with 62+ methods - violates Single Responsibility Principle
- **Priority:** High (architectural debt blocking maintainability)
- **Estimated Effort:** 1 week
- **Template:** REF-013 Phase 1 (HealthService extraction) - use as implementation model

---

## 1. Overview

### Problem Summary

The `MemoryRAGServer` class in `src/core/server.py` has grown to an unmaintainable 4,767 lines with 62+ methods, making it the largest "god class" anti-pattern in the codebase. This violates the Single Responsibility Principle by managing:

- 20+ component initializations
- Memory storage, retrieval, and lifecycle operations
- Code indexing and semantic search
- Analytics and usage tracking
- Health monitoring and alerting
- Cross-project consent management
- Proactive suggestions
- Direct coupling to 15+ external modules

### Impact

**Current Pain Points:**
- **Testing:** Impossible to test services in isolation - requires full server initialization
- **Understanding:** 4,767 lines are too large to comprehend in one sitting
- **Modification Risk:** Changing any feature risks breaking unrelated features
- **Merge Conflicts:** 6 concurrent agents working on same 4,767-line file
- **Performance:** No way to lazy-load unused services
- **Reusability:** Services tightly coupled to MCP server context

**Quantified Impact:**
- Average PR review time: 2-3 hours (code navigation overhead)
- Test setup complexity: 20+ mocks required for simple unit tests
- Bug introduction rate: High (side effects across unrelated features)
- Onboarding time: +2 days for new contributors to understand server.py

### Success After Refactoring

- `MemoryRAGServer` reduced to <800 lines (thin facade/coordinator)
- Each service class: 200-600 lines (single responsibility)
- Unit tests can mock individual services (not 20+ dependencies)
- Services reusable outside MCP context (e.g., CLI, web dashboard)
- Parallel development: 6 agents work on different services without conflicts

---

## 2. Current State Analysis

### File Structure

**Location:** `src/core/server.py` - 4,767 lines

**Class Hierarchy:**
```
MemoryRAGServer (single class)
├── __init__() - Lines 73-143 (71 lines)
│   └── Initializes 20+ component references (all None)
├── initialize() - Lines 144-341 (198 lines)
│   └── Conditional initialization of all subsystems
├── Memory Operations (8 methods, ~600 lines)
│   ├── store_memory()
│   ├── retrieve_memories()
│   ├── delete_memory()
│   ├── get_memory_by_id()
│   └── update_memory(), list_memories(), export_memories(), import_memories()
├── Code Search Operations (6 methods, ~800 lines)
│   ├── index_codebase()
│   ├── search_code()
│   ├── find_similar_code()
│   └── get_indexed_files(), reindex_project(), search_git_history()
├── Analytics Operations (5 methods, ~400 lines)
│   ├── get_usage_statistics()
│   ├── get_top_queries()
│   ├── get_frequently_accessed_code()
│   └── get_pattern_analysis(), get_project_insights()
├── Health/Monitoring Operations (4 methods, ~300 lines)
│   ├── get_health_score()
│   ├── get_performance_metrics()
│   └── get_alerts(), get_capacity_forecast()
├── Project Operations (4 methods, ~200 lines)
│   ├── list_projects()
│   ├── get_project_details()
│   └── archive_project(), switch_project()
├── Status/Admin Operations (3 methods, ~150 lines)
│   ├── get_status()
│   └── cleanup(), _detect_project()
└── Internal Stats Tracking (~2,118 lines)
    └── Inline self.stats mutations scattered throughout
```

### Dependencies Analysis

**Direct External Dependencies (15+ modules):**
```python
from src.store import MemoryStore
from src.embeddings.generator import EmbeddingGenerator
from src.embeddings.cache import EmbeddingCache
from src.memory.usage_tracker import UsageTracker
from src.memory.pruner import MemoryPruner
from src.memory.conversation_tracker import ConversationTracker
from src.memory.query_expander import QueryExpander
from src.memory.suggestion_engine import SuggestionEngine
from src.memory.duplicate_detector import DuplicateDetector
from src.analysis.complexity_analyzer import ComplexityAnalyzer
from src.analysis.quality_analyzer import QualityAnalyzer
from src.search.hybrid_search import HybridSearcher
from src.analytics.usage_tracker import UsagePatternTracker
from src.monitoring.metrics_collector import MetricsCollector
from src.monitoring.alert_engine import AlertEngine
from src.monitoring.health_reporter import HealthReporter
from src.monitoring.capacity_planner import CapacityPlanner
```

**Configuration Dependencies:**
- 30+ feature flags from `ServerConfig` (REF-017 will consolidate these)
- Conditional initialization based on flags (17 `if self.config.enable_*` blocks)

### Method Categorization

**1. Memory Service Methods (8 methods):**
- `store_memory()` - Store memory unit with validation
- `retrieve_memories()` - Query with filters and ranking
- `delete_memory()` - Remove memory by ID
- `get_memory_by_id()` - Retrieve single memory
- `update_memory()` - Update existing memory
- `list_memories()` - List with pagination
- `export_memories()` - Export to JSON
- `import_memories()` - Import from JSON

**Dependencies:** `MemoryStore`, `EmbeddingGenerator`, `EmbeddingCache`, `UsageTracker`, `DuplicateDetector`

**2. Indexing Service Methods (6 methods):**
- `index_codebase()` - Index directory recursively
- `search_code()` - Semantic code search
- `find_similar_code()` - Find similar code units
- `get_indexed_files()` - List indexed files
- `reindex_project()` - Re-index project
- `search_git_history()` - Search git commits

**Dependencies:** `MemoryStore`, `EmbeddingGenerator`, `IncrementalIndexer`, `HybridSearcher`, `ComplexityAnalyzer`, `QualityAnalyzer`

**3. Analytics Service Methods (5 methods):**
- `get_usage_statistics()` - Usage metrics
- `get_top_queries()` - Most frequent queries
- `get_frequently_accessed_code()` - Hot code paths
- `get_pattern_analysis()` - Usage patterns
- `get_project_insights()` - Project-level analytics

**Dependencies:** `UsagePatternTracker`, `MemoryStore`, `MetricsCollector`

**4. Health Service Methods (4 methods):**
- `get_health_score()` - Overall health
- `get_performance_metrics()` - Performance stats
- `get_alerts()` - Active alerts
- `get_capacity_forecast()` - Capacity planning

**Dependencies:** `HealthReporter`, `MetricsCollector`, `AlertEngine`, `CapacityPlanner`

**Note:** REF-013 Phase 1 already extracted these into standalone HealthService class - use as template!

**5. Project Service Methods (4 methods):**
- `list_projects()` - List all projects
- `get_project_details()` - Project metadata
- `archive_project()` - Archive project
- `switch_project()` - Change active project

**Dependencies:** `MemoryStore`, `ProjectIndexTracker`

**6. Admin/Status Methods (3 methods):**
- `get_status()` - Server status
- `cleanup()` - Shutdown cleanup
- `_detect_project()` - Git project detection

**Dependencies:** All components (status aggregation)

---

## 3. Proposed Solution

### Architecture Overview

**Facade Pattern Implementation:**

```
┌─────────────────────────────────────────────────────────┐
│          MemoryRAGServer (Thin Facade)                  │
│  - Component initialization                             │
│  - MCP tool registration                                │
│  - Request routing to services                          │
│  - Lifecycle management (initialize/cleanup)            │
│  (~600 lines)                                           │
└─────────────────────────────────────────────────────────┘
                          │
        ┌─────────────────┼─────────────────┐
        │                 │                 │
        ▼                 ▼                 ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│  Memory      │  │  Indexing    │  │  Analytics   │
│  Service     │  │  Service     │  │  Service     │
│              │  │              │  │              │
│ - CRUD ops   │  │ - Indexing   │  │ - Usage      │
│ - Ranking    │  │ - Search     │  │ - Patterns   │
│ - Pruning    │  │ - Similarity │  │ - Insights   │
│ (~500 lines) │  │ (~600 lines) │  │ (~400 lines) │
└──────────────┘  └──────────────┘  └──────────────┘

┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│  Health      │  │  Project     │  │  Stats       │
│  Service     │  │  Service     │  │  Tracker     │
│  (DONE!)     │  │              │  │              │
│              │  │ - List/Get   │  │ - Metrics    │
│ - Health     │  │ - Archive    │  │ - Counters   │
│ - Metrics    │  │ - Switch     │  │ - Timestamps │
│ - Alerts     │  │ (~200 lines) │  │ (~200 lines) │
└──────────────┘  └──────────────┘  └──────────────┘
```

### Service Interface Design

**Base Service Protocol:**

```python
# src/core/services/base_service.py

from typing import Protocol, runtime_checkable
from src.config import ServerConfig

@runtime_checkable
class Service(Protocol):
    """Base protocol for all services."""

    async def initialize(self) -> None:
        """Initialize async resources."""
        ...

    async def cleanup(self) -> None:
        """Cleanup resources."""
        ...

    def get_stats(self) -> dict:
        """Get service-specific statistics."""
        ...
```

**1. MemoryService Interface:**

```python
# src/core/services/memory_service.py

from typing import Optional, List, Dict, Any
from src.core.models import MemoryUnit, MemoryResult, SearchFilters
from src.store import MemoryStore
from src.embeddings.generator import EmbeddingGenerator
from src.embeddings.cache import EmbeddingCache
from src.memory.usage_tracker import UsageTracker
from src.memory.duplicate_detector import DuplicateDetector

class MemoryService:
    """
    Handles all memory storage, retrieval, and lifecycle operations.

    Responsibilities:
    - Store/retrieve/update/delete memory units
    - Ranking and filtering
    - Deduplication
    - Usage tracking
    - Memory pruning
    """

    def __init__(
        self,
        store: MemoryStore,
        embedding_generator: EmbeddingGenerator,
        embedding_cache: EmbeddingCache,
        config: ServerConfig,
        usage_tracker: Optional[UsageTracker] = None,
        duplicate_detector: Optional[DuplicateDetector] = None,
    ):
        self.store = store
        self.embedding_generator = embedding_generator
        self.embedding_cache = embedding_cache
        self.config = config
        self.usage_tracker = usage_tracker
        self.duplicate_detector = duplicate_detector

        # Service-specific stats
        self._stats = {
            "memories_stored": 0,
            "memories_retrieved": 0,
            "memories_deleted": 0,
            "duplicates_detected": 0,
        }

    async def store_memory(self, request: StoreMemoryRequest) -> MemoryUnit:
        """Store a new memory unit."""
        ...

    async def retrieve_memories(
        self,
        query: str,
        filters: Optional[SearchFilters] = None,
        limit: int = 10
    ) -> List[MemoryResult]:
        """Retrieve memories matching query."""
        ...

    async def delete_memory(self, memory_id: str) -> bool:
        """Delete memory by ID."""
        ...

    # ... other methods
```

**2. IndexingService Interface:**

```python
# src/core/services/indexing_service.py

from pathlib import Path
from typing import List, Optional, Dict, Any
from src.memory.incremental_indexer import IncrementalIndexer
from src.store import MemoryStore
from src.embeddings.generator import EmbeddingGenerator
from src.search.hybrid_search import HybridSearcher
from src.analysis.complexity_analyzer import ComplexityAnalyzer
from src.analysis.quality_analyzer import QualityAnalyzer

class IndexingService:
    """
    Handles code indexing and semantic search.

    Responsibilities:
    - Index codebases
    - Semantic code search
    - Similarity detection
    - Quality/complexity analysis
    - Git history indexing
    """

    def __init__(
        self,
        store: MemoryStore,
        embedding_generator: EmbeddingGenerator,
        config: ServerConfig,
        hybrid_searcher: Optional[HybridSearcher] = None,
        complexity_analyzer: Optional[ComplexityAnalyzer] = None,
        quality_analyzer: Optional[QualityAnalyzer] = None,
    ):
        self.store = store
        self.embedding_generator = embedding_generator
        self.config = config
        self.hybrid_searcher = hybrid_searcher
        self.complexity_analyzer = complexity_analyzer
        self.quality_analyzer = quality_analyzer

        self._indexer: Optional[IncrementalIndexer] = None
        self._stats = {
            "files_indexed": 0,
            "code_searches": 0,
            "similarity_queries": 0,
        }

    async def index_codebase(
        self,
        path: Path,
        project_name: str,
        recursive: bool = True,
        show_progress: bool = True,
    ) -> Dict[str, Any]:
        """Index a codebase directory."""
        ...

    async def search_code(
        self,
        query: str,
        project_name: Optional[str] = None,
        file_pattern: Optional[str] = None,
        limit: int = 10,
    ) -> List[MemoryResult]:
        """Search code semantically."""
        ...

    # ... other methods
```

**3. AnalyticsService Interface:**

```python
# src/core/services/analytics_service.py

from typing import List, Dict, Any, Optional
from datetime import datetime
from src.analytics.usage_tracker import UsagePatternTracker
from src.store import MemoryStore
from src.monitoring.metrics_collector import MetricsCollector

class AnalyticsService:
    """
    Handles usage analytics and pattern analysis.

    Responsibilities:
    - Usage statistics
    - Query pattern analysis
    - Code access patterns
    - Project insights
    """

    def __init__(
        self,
        store: MemoryStore,
        metrics_collector: MetricsCollector,
        pattern_tracker: Optional[UsagePatternTracker] = None,
    ):
        self.store = store
        self.metrics_collector = metrics_collector
        self.pattern_tracker = pattern_tracker

        self._stats = {
            "queries_analyzed": 0,
            "patterns_detected": 0,
        }

    async def get_usage_statistics(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Get usage statistics for date range."""
        ...

    async def get_top_queries(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get most frequent queries."""
        ...

    # ... other methods
```

**4. ProjectService Interface:**

```python
# src/core/services/project_service.py

from typing import List, Dict, Any, Optional
from src.store import MemoryStore
from src.memory.project_index_tracker import ProjectIndexTracker

class ProjectService:
    """
    Handles project management operations.

    Responsibilities:
    - List/get projects
    - Project archival
    - Project switching
    - Project metadata
    """

    def __init__(
        self,
        store: MemoryStore,
        project_tracker: ProjectIndexTracker,
    ):
        self.store = store
        self.project_tracker = project_tracker

        self._stats = {
            "projects_listed": 0,
            "projects_archived": 0,
        }

    async def list_projects(self) -> List[Dict[str, Any]]:
        """List all indexed projects."""
        ...

    async def get_project_details(self, project_name: str) -> Dict[str, Any]:
        """Get detailed project information."""
        ...

    # ... other methods
```

**5. StatsTracker (Internal Component):**

```python
# src/core/services/stats_tracker.py

from typing import Dict, Any
from datetime import datetime
import threading

class StatsTracker:
    """
    Thread-safe statistics aggregation.

    Fixes ARCH-004 race condition in stats dictionary.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._stats: Dict[str, Any] = {
            "server_start_time": datetime.now().isoformat(),
            "last_query_time": None,
        }

    def increment(self, key: str, value: int = 1) -> None:
        """Thread-safe counter increment."""
        with self._lock:
            self._stats[key] = self._stats.get(key, 0) + value

    def set(self, key: str, value: Any) -> None:
        """Thread-safe value set."""
        with self._lock:
            self._stats[key] = value

    def get_all(self) -> Dict[str, Any]:
        """Get snapshot of all stats."""
        with self._lock:
            return dict(self._stats)

    def merge_service_stats(self, service_stats: Dict[str, Any]) -> None:
        """Merge stats from a service."""
        with self._lock:
            self._stats.update(service_stats)
```

### Refactored MemoryRAGServer

```python
# src/core/server.py (AFTER refactoring - ~600 lines)

from src.core.services.memory_service import MemoryService
from src.core.services.indexing_service import IndexingService
from src.core.services.analytics_service import AnalyticsService
from src.core.services.health_service import HealthService
from src.core.services.project_service import ProjectService
from src.core.services.stats_tracker import StatsTracker

class MemoryRAGServer:
    """
    MCP Server facade for memory and RAG operations.

    This class coordinates between services and handles MCP protocol.
    Business logic is delegated to specialized services.
    """

    def __init__(self, config: Optional[ServerConfig] = None):
        if config is None:
            config = get_config()

        self.config = config
        self.project_name = self._detect_project()

        # Core infrastructure (shared across services)
        self.store: Optional[MemoryStore] = None
        self.embedding_generator: Optional[EmbeddingGenerator] = None
        self.embedding_cache: Optional[EmbeddingCache] = None

        # Services (initialized lazily)
        self.memory_service: Optional[MemoryService] = None
        self.indexing_service: Optional[IndexingService] = None
        self.analytics_service: Optional[AnalyticsService] = None
        self.health_service: Optional[HealthService] = None
        self.project_service: Optional[ProjectService] = None

        # Stats tracker (thread-safe)
        self.stats_tracker = StatsTracker()

    async def initialize(self, defer_preload: bool = False) -> None:
        """Initialize server and services."""
        # Initialize core infrastructure
        self.store = create_memory_store(config=self.config)
        await self.store.initialize()

        self.embedding_generator = EmbeddingGenerator(self.config)
        if not defer_preload:
            await self.embedding_generator.initialize()

        self.embedding_cache = EmbeddingCache(self.config)

        # Initialize services
        await self._initialize_services()

    async def _initialize_services(self) -> None:
        """Initialize all enabled services."""
        # Memory service (always enabled)
        self.memory_service = MemoryService(
            store=self.store,
            embedding_generator=self.embedding_generator,
            embedding_cache=self.embedding_cache,
            config=self.config,
        )
        await self.memory_service.initialize()

        # Indexing service (always enabled)
        self.indexing_service = IndexingService(
            store=self.store,
            embedding_generator=self.embedding_generator,
            config=self.config,
        )
        await self.indexing_service.initialize()

        # Analytics service (conditional)
        if self.config.enable_usage_pattern_analytics:
            self.analytics_service = AnalyticsService(
                store=self.store,
                metrics_collector=self.metrics_collector,
            )
            await self.analytics_service.initialize()

        # Health service (always enabled)
        self.health_service = HealthService(
            store=self.store,
            config=self.config,
        )
        await self.health_service.initialize()

        # Project service (always enabled)
        self.project_service = ProjectService(
            store=self.store,
            project_tracker=self.project_tracker,
        )
        await self.project_service.initialize()

    # MCP Tool Handlers (thin wrappers - delegate to services)

    async def store_memory(self, request: StoreMemoryRequest) -> MemoryUnit:
        """MCP tool: Store a memory unit."""
        result = await self.memory_service.store_memory(request)
        self.stats_tracker.increment("memories_stored")
        return result

    async def retrieve_memories(self, request: QueryRequest) -> RetrievalResponse:
        """MCP tool: Retrieve memories."""
        results = await self.memory_service.retrieve_memories(
            query=request.query,
            filters=request.filters,
            limit=request.limit,
        )
        self.stats_tracker.increment("memories_retrieved", len(results))
        return RetrievalResponse(results=results)

    async def index_codebase(self, path: str, project_name: str) -> Dict[str, Any]:
        """MCP tool: Index a codebase."""
        return await self.indexing_service.index_codebase(
            path=Path(path),
            project_name=project_name,
        )

    async def search_code(self, query: str, **kwargs) -> List[MemoryResult]:
        """MCP tool: Search code."""
        return await self.indexing_service.search_code(query, **kwargs)

    async def get_usage_statistics(self, **kwargs) -> Dict[str, Any]:
        """MCP tool: Get usage statistics."""
        if not self.analytics_service:
            raise ValidationError("Analytics service not enabled")
        return await self.analytics_service.get_usage_statistics(**kwargs)

    async def get_health_score(self) -> Dict[str, Any]:
        """MCP tool: Get health score."""
        return await self.health_service.get_health_score()

    async def list_projects(self) -> List[Dict[str, Any]]:
        """MCP tool: List projects."""
        return await self.project_service.list_projects()

    async def get_status(self) -> StatusResponse:
        """
        MCP tool: Get server status.

        Aggregates stats from all services.
        """
        stats = self.stats_tracker.get_all()

        # Merge service stats
        if self.memory_service:
            stats.update(self.memory_service.get_stats())
        if self.indexing_service:
            stats.update(self.indexing_service.get_stats())
        if self.analytics_service:
            stats.update(self.analytics_service.get_stats())
        if self.health_service:
            stats.update(self.health_service.get_stats())

        return StatusResponse(
            status="running",
            project=self.project_name,
            stats=stats,
        )

    async def cleanup(self) -> None:
        """Cleanup all services."""
        services = [
            self.memory_service,
            self.indexing_service,
            self.analytics_service,
            self.health_service,
            self.project_service,
        ]

        for service in services:
            if service:
                await service.cleanup()

        if self.store:
            await self.store.cleanup()
```

---

## 4. Implementation Plan

### Phase 0: Preparation (1 day)

**Goals:**
- Set up service directory structure
- Create base protocols
- Document extraction strategy

**Tasks:**
- [ ] Create `src/core/services/` directory
- [ ] Create `src/core/services/__init__.py`
- [ ] Create `src/core/services/base_service.py` with `Service` protocol
- [ ] Create `src/core/services/stats_tracker.py` (thread-safe stats)
- [ ] Document method-to-service mapping in this file
- [ ] Review REF-013 Phase 1 (HealthService) for lessons learned

**Output:**
- Directory structure ready
- Base classes defined
- Clear roadmap for phases

---

### Phase 1: Extract MemoryService (2 days)

**Goals:**
- Extract 8 memory-related methods into standalone service
- Maintain 100% backward compatibility
- Achieve 80%+ test coverage

**Tasks:**
- [ ] Create `src/core/services/memory_service.py`
- [ ] Move memory methods from server.py:
  - `store_memory()`
  - `retrieve_memories()`
  - `delete_memory()`
  - `get_memory_by_id()`
  - `update_memory()`
  - `list_memories()`
  - `export_memories()`
  - `import_memories()`
- [ ] Update `MemoryRAGServer` to delegate to `MemoryService`
- [ ] Create `tests/unit/test_memory_service.py`
- [ ] Run full test suite - ensure 100% pass
- [ ] Update stats tracking to use `StatsTracker`

**Success Criteria:**
- [ ] All 2,740+ tests pass
- [ ] MemoryService has 80%+ coverage
- [ ] server.py reduced by ~600 lines
- [ ] Zero behavior changes (backward compatible)

---

### Phase 2: Extract IndexingService (2 days)

**Goals:**
- Extract 6 indexing/search methods
- Consolidate hybrid search logic
- Enable lazy initialization (don't index unless needed)

**Tasks:**
- [ ] Create `src/core/services/indexing_service.py`
- [ ] Move indexing methods from server.py:
  - `index_codebase()`
  - `search_code()`
  - `find_similar_code()`
  - `get_indexed_files()`
  - `reindex_project()`
  - `search_git_history()`
- [ ] Update `MemoryRAGServer` to delegate to `IndexingService`
- [ ] Create `tests/unit/test_indexing_service.py`
- [ ] Run full test suite

**Success Criteria:**
- [ ] All tests pass
- [ ] IndexingService has 80%+ coverage
- [ ] server.py reduced by ~800 lines (total ~1,400 removed)

---

### Phase 3: Extract AnalyticsService (1 day)

**Goals:**
- Extract 5 analytics methods
- Make service optional (only if analytics enabled)

**Tasks:**
- [ ] Create `src/core/services/analytics_service.py`
- [ ] Move analytics methods from server.py:
  - `get_usage_statistics()`
  - `get_top_queries()`
  - `get_frequently_accessed_code()`
  - `get_pattern_analysis()`
  - `get_project_insights()`
- [ ] Update server.py with conditional initialization
- [ ] Create `tests/unit/test_analytics_service.py`

**Success Criteria:**
- [ ] All tests pass
- [ ] AnalyticsService has 80%+ coverage
- [ ] server.py reduced by ~400 lines (total ~1,800 removed)

---

### Phase 4: Extract ProjectService (1 day)

**Goals:**
- Extract 4 project management methods
- Consolidate project metadata logic

**Tasks:**
- [ ] Create `src/core/services/project_service.py`
- [ ] Move project methods from server.py:
  - `list_projects()`
  - `get_project_details()`
  - `archive_project()`
  - `switch_project()`
- [ ] Update server.py delegation
- [ ] Create `tests/unit/test_project_service.py`

**Success Criteria:**
- [ ] All tests pass
- [ ] ProjectService has 80%+ coverage
- [ ] server.py reduced by ~200 lines (total ~2,000 removed)

---

### Phase 5: Verify HealthService Integration (0.5 days)

**Goals:**
- Verify REF-013 Phase 1 HealthService works with new architecture
- Ensure consistent service patterns

**Tasks:**
- [ ] Review `src/core/services/health_service.py` (already exists)
- [ ] Ensure HealthService follows same patterns as new services
- [ ] Update server.py integration if needed
- [ ] Verify health service tests still pass

**Success Criteria:**
- [ ] HealthService matches new service patterns
- [ ] All health tests pass

---

### Phase 6: Final Cleanup and Documentation (1 day)

**Goals:**
- Clean up server.py
- Update all documentation
- Verify quality gates

**Tasks:**
- [ ] Remove commented-out code from server.py
- [ ] Verify server.py is <800 lines
- [ ] Update `src/core/services/__init__.py` with exports
- [ ] Update CHANGELOG.md
- [ ] Update ARCHITECTURE.md with new service layer
- [ ] Update CLAUDE.md essential files section
- [ ] Run `python scripts/verify-complete.py` - all gates must pass

**Success Criteria:**
- [ ] server.py <800 lines
- [ ] All 2,740+ tests pass
- [ ] Coverage ≥80% for all services
- [ ] Documentation updated

---

## 5. Testing Strategy

### Unit Testing Approach

**Per-Service Test Suites:**

```python
# tests/unit/test_memory_service.py

import pytest
from src.core.services.memory_service import MemoryService
from src.store import MemoryStore
from src.embeddings.generator import EmbeddingGenerator
from src.config import ServerConfig

@pytest.fixture
async def memory_service(mock_store, mock_embedding_generator):
    """Create MemoryService with mocked dependencies."""
    config = ServerConfig()
    service = MemoryService(
        store=mock_store,
        embedding_generator=mock_embedding_generator,
        embedding_cache=MagicMock(),
        config=config,
    )
    await service.initialize()
    yield service
    await service.cleanup()

class TestMemoryService:
    """Test MemoryService in isolation."""

    async def test_store_memory_success(self, memory_service):
        """Test storing a memory unit."""
        request = StoreMemoryRequest(
            content="Test memory",
            context_level=ContextLevel.SESSION_STATE,
        )

        result = await memory_service.store_memory(request)

        assert result.id is not None
        assert result.content == "Test memory"
        assert memory_service.get_stats()["memories_stored"] == 1

    async def test_retrieve_memories_with_filters(self, memory_service):
        """Test retrieval with filters."""
        filters = SearchFilters(
            context_level=ContextLevel.PROJECT_CONTEXT,
            project_name="test-project",
        )

        results = await memory_service.retrieve_memories(
            query="test query",
            filters=filters,
            limit=10,
        )

        assert isinstance(results, list)
        assert memory_service.get_stats()["memories_retrieved"] >= 0

    # ... 20+ more tests for MemoryService
```

**Key Testing Principles:**
1. **Mock External Dependencies:** Each service test mocks `MemoryStore`, `EmbeddingGenerator`, etc.
2. **Test Service Logic:** Focus on business logic, not infrastructure
3. **Verify Stats Tracking:** Assert stats counters update correctly
4. **Test Error Handling:** Verify exceptions propagate correctly
5. **Test Cleanup:** Ensure `cleanup()` releases resources

### Integration Testing

**Service Integration Tests:**

```python
# tests/integration/test_service_integration.py

async def test_memory_to_indexing_flow():
    """Test memory service -> indexing service interaction."""
    # Real store, real services
    store = await create_memory_store()
    embedding_gen = EmbeddingGenerator(config)

    memory_service = MemoryService(store, embedding_gen, ...)
    indexing_service = IndexingService(store, embedding_gen, ...)

    # Store memory via memory service
    memory = await memory_service.store_memory(...)

    # Search via indexing service - should find it
    results = await indexing_service.search_code(query=memory.content)

    assert len(results) > 0
    assert results[0].id == memory.id
```

### Regression Testing

**Before/After Behavior Verification:**

```python
# tests/regression/test_ref016_compatibility.py

async def test_server_api_unchanged():
    """
    Verify MemoryRAGServer API is identical before/after refactoring.

    This ensures existing code (MCP clients, CLI, etc.) works unchanged.
    """
    server = MemoryRAGServer(config)
    await server.initialize()

    # All original methods still exist
    assert hasattr(server, 'store_memory')
    assert hasattr(server, 'retrieve_memories')
    assert hasattr(server, 'index_codebase')
    assert hasattr(server, 'search_code')
    assert hasattr(server, 'get_usage_statistics')
    assert hasattr(server, 'get_health_score')
    assert hasattr(server, 'list_projects')
    assert hasattr(server, 'get_status')

    # Behavior unchanged
    result = await server.store_memory(StoreMemoryRequest(...))
    assert isinstance(result, MemoryUnit)
```

### Coverage Requirements

**Per-Service Targets:**
- MemoryService: ≥85% (high criticality)
- IndexingService: ≥85% (high criticality)
- AnalyticsService: ≥80% (medium criticality)
- ProjectService: ≥80% (medium criticality)
- StatsTracker: ≥90% (must handle concurrency correctly)

**Overall Target:**
- Maintain or improve current 71.2% core coverage
- New services must achieve 80%+ coverage before merge

---

## 6. Risk Assessment

### Breaking Changes

**Risk:** Refactoring introduces subtle behavior changes

**Likelihood:** Medium (despite careful planning, edge cases exist)

**Mitigation:**
1. **Extract one service at a time** - incremental approach limits blast radius
2. **Run full test suite after each phase** - catch regressions immediately
3. **Regression test suite** - verify API compatibility
4. **Manual smoke testing** - test real-world workflows
5. **Rollback plan** - each phase is a separate commit, can revert

### Test Failures

**Risk:** Existing tests fail due to import/initialization changes

**Likelihood:** High (many tests import `MemoryRAGServer` directly)

**Impact:** High (blocks merge until fixed)

**Mitigation:**
1. **Update test fixtures incrementally** - fix tests in same commit as service extraction
2. **Create compatibility shims** - temporary wrappers if needed
3. **Parallel PR approach** - create service extraction PR, fix tests in separate PR, merge both
4. **Test early, test often** - run `pytest tests/` after every file change

### Performance Regression

**Risk:** Service indirection adds latency

**Likelihood:** Low (method calls are cheap in Python)

**Impact:** Medium (7-13ms search latency is key metric)

**Mitigation:**
1. **Benchmark before/after** - measure key operations:
   - `store_memory()` latency
   - `search_code()` latency
   - `index_codebase()` throughput
2. **Profile hot paths** - use `cProfile` to find bottlenecks
3. **Inline critical paths** - if delegation adds >1ms, optimize
4. **Monitor in production** - MetricsCollector tracks latency

**Acceptance Criteria:**
- `store_memory()` latency: <50ms (no change)
- `search_code()` latency: 7-13ms (no change)
- `index_codebase()` throughput: 10-20 files/sec (no change)

### Merge Conflicts

**Risk:** 6 concurrent agents editing server.py

**Likelihood:** Very High (server.py is hotspot)

**Impact:** High (delays all PRs)

**Mitigation:**
1. **Prioritize this refactoring** - complete before other server.py changes
2. **Use git worktrees** - isolate refactoring work
3. **Coordinate with team** - announce server.py freeze during refactoring
4. **Incremental merges** - merge each phase immediately (don't let branch diverge)

### Resource Leaks

**Risk:** Service cleanup not called properly

**Likelihood:** Medium (async cleanup is error-prone)

**Impact:** High (connection pool exhaustion)

**Mitigation:**
1. **Context manager pattern** - use `async with` where possible
2. **Explicit cleanup tests** - verify `cleanup()` releases resources
3. **Resource leak detection** - monitor Qdrant connection count
4. **Pytest fixtures** - ensure cleanup in `yield` fixtures

---

## 7. Success Criteria

### Quantitative Metrics

**Code Size:**
- [ ] MemoryRAGServer: 4,767 lines → <800 lines (83% reduction)
- [ ] MemoryService: ~500 lines
- [ ] IndexingService: ~600 lines
- [ ] AnalyticsService: ~400 lines
- [ ] ProjectService: ~200 lines
- [ ] HealthService: ~300 lines (already exists)
- [ ] StatsTracker: ~200 lines

**Test Coverage:**
- [ ] MemoryService: ≥85%
- [ ] IndexingService: ≥85%
- [ ] AnalyticsService: ≥80%
- [ ] ProjectService: ≥80%
- [ ] Overall core coverage: ≥71.2% (maintain current level)

**Test Pass Rate:**
- [ ] All 2,740+ tests pass (100% pass rate)
- [ ] Zero flaky tests introduced
- [ ] Zero behavior changes (regression tests pass)

**Performance:**
- [ ] `store_memory()` latency: <50ms (no regression)
- [ ] `search_code()` latency: 7-13ms (no regression)
- [ ] `index_codebase()` throughput: 10-20 files/sec (no regression)

### Qualitative Outcomes

**Developer Experience:**
- [ ] New contributor can understand MemoryService in <30 min
- [ ] Unit tests can mock single service (not 20+ dependencies)
- [ ] PR review time for service changes: <1 hour (down from 2-3 hours)
- [ ] Merge conflicts reduced by 80% (smaller surface area)

**Maintainability:**
- [ ] Each service has single, clear responsibility
- [ ] Dependencies explicit in `__init__()` (no hidden coupling)
- [ ] Services reusable outside MCP context (CLI, web dashboard)
- [ ] Can add new service without modifying existing services

**Testing:**
- [ ] Can test MemoryService without initializing Qdrant
- [ ] Can test IndexingService without loading embedding model
- [ ] Faster test execution (less setup overhead)
- [ ] Easier to write focused tests (smaller scope)

### Documentation

- [ ] ARCHITECTURE.md updated with service layer diagram
- [ ] Each service has comprehensive docstring
- [ ] CLAUDE.md updated with new file structure
- [ ] CHANGELOG.md documents refactoring
- [ ] This planning doc updated with completion summary

---

## Appendix A: Method Inventory

**Complete list of MemoryRAGServer methods categorized by service:**

### MemoryService (8 methods)
1. `store_memory()` - Store memory unit
2. `retrieve_memories()` - Query with ranking
3. `delete_memory()` - Delete by ID
4. `get_memory_by_id()` - Get single memory
5. `update_memory()` - Update existing
6. `list_memories()` - List with pagination
7. `export_memories()` - Export to JSON
8. `import_memories()` - Import from JSON

### IndexingService (6 methods)
1. `index_codebase()` - Index directory
2. `search_code()` - Semantic search
3. `find_similar_code()` - Similarity detection
4. `get_indexed_files()` - List indexed files
5. `reindex_project()` - Re-index project
6. `search_git_history()` - Git search

### AnalyticsService (5 methods)
1. `get_usage_statistics()` - Usage metrics
2. `get_top_queries()` - Frequent queries
3. `get_frequently_accessed_code()` - Hot code
4. `get_pattern_analysis()` - Usage patterns
5. `get_project_insights()` - Project analytics

### HealthService (4 methods) - ALREADY EXTRACTED
1. `get_health_score()` - Health check
2. `get_performance_metrics()` - Performance stats
3. `get_alerts()` - Active alerts
4. `get_capacity_forecast()` - Capacity planning

### ProjectService (4 methods)
1. `list_projects()` - List all projects
2. `get_project_details()` - Project metadata
3. `archive_project()` - Archive project
4. `switch_project()` - Change project

### Server Core (3 methods - remain in server.py)
1. `initialize()` - Initialize services
2. `cleanup()` - Cleanup services
3. `get_status()` - Aggregate status

### Internal Helpers (remain in server.py)
1. `_detect_project()` - Git project detection
2. `_initialize_services()` - Service initialization

**Total:** 30 public methods → 6 services + core

---

## Appendix B: Dependency Graph

```
┌─────────────────────────────────────────────────────┐
│                  MemoryRAGServer                    │
│                  (Orchestrator)                     │
└─────────────────────────────────────────────────────┘
                        │
        ┌───────────────┼───────────────┐
        │               │               │
        ▼               ▼               ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│ MemoryStore  │ │  Embedding   │ │EmbeddingCache│
│  (Shared)    │ │  Generator   │ │   (Shared)   │
│              │ │   (Shared)   │ │              │
└──────────────┘ └──────────────┘ └──────────────┘
        │               │               │
        └───────────────┼───────────────┘
                        │
        ┌───────────────┼───────────────┐
        │               │               │
        ▼               ▼               ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│    Memory    │ │   Indexing   │ │  Analytics   │
│   Service    │ │   Service    │ │   Service    │
└──────────────┘ └──────────────┘ └──────────────┘
        │               │               │
        ▼               ▼               ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│ UsageTracker │ │ HybridSearch │ │UsagePattern  │
│ Duplicate    │ │ Complexity   │ │  Tracker     │
│  Detector    │ │  Analyzer    │ │              │
└──────────────┘ └──────────────┘ └──────────────┘
```

**Key Insight:** Services share infrastructure (store, embedding_generator, cache) but have independent logic.

---

## Completion Summary

**Status:** Planning complete - ready for implementation
**Next Steps:**
1. Get approval for service extraction approach
2. Create REF-016 in TODO.md
3. Begin Phase 0 (directory setup)
4. Extract services incrementally (one phase at a time)

**Estimated Timeline:** 1 week (5 phases × 1-2 days each)
**Risk Level:** Medium (large refactoring, but incremental approach mitigates)
**Impact:** High (improves maintainability for all future development)
