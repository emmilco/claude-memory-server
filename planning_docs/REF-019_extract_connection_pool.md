# REF-019: Extract ConnectionPool from QdrantStore

**Task ID:** REF-019
**Type:** Refactoring / Architecture
**Priority:** High
**Estimated Effort:** ~3 days
**Status:** Assessment Complete - Partially Done
**Created:** 2025-11-25
**Assessed:** 2025-11-25

---

## Assessment Summary (2025-11-25)

### What's Already Done ✅

1. **ConnectionPool Exists** - `src/store/connection_pool.py` (540 lines)
   - QdrantConnectionPool class fully implemented
   - Features: min/max pool sizing, health checking, age-based recycling, acquisition timeout, performance metrics
   - Well-structured with PoolStats dataclass and PooledConnection wrapper
   - All 44 unit tests passing (100% pass rate)

2. **Health Checking** - `src/store/connection_health_checker.py`
   - ConnectionHealthChecker class integrated with pool
   - Provides fast health checks on acquire
   - Health stats tracking available

3. **Monitoring** - `src/store/connection_pool_monitor.py`
   - ConnectionPoolMonitor for background monitoring
   - Optional monitoring with get_stats() support

### What Still Needs Work ❌

1. **Separation of Concerns**
   - QdrantStore still manages pool lifecycle directly (lines 52-74 in initialize())
   - Store directly sets pool.enable_health_checks and pool._health_checker (lines 72-74)
   - Tight coupling between store initialization and pool setup

2. **Try/Finally Boilerplate (Major Issue)**
   - 37 try blocks in qdrant_store.py
   - 30 finally blocks with manual client release
   - 62 calls to _get_client() and _release_client()
   - Every method has 6 lines of boilerplate (3 acquire + 3 release)

3. **File Size**
   - qdrant_store.py: 2,983 lines (target: <800)
   - 45 methods total (target: <20 business logic methods)
   - Methods mix connection management with business logic

4. **No Abstraction Layer**
   - Missing QdrantClientProvider interface
   - Missing PooledClientProvider implementation
   - Missing SingleClientProvider for testing
   - Can't easily swap pool vs single client vs mock

### Metrics

| Metric | Current | Target | Gap |
|--------|---------|--------|-----|
| QdrantStore LOC | 2,983 | <800 | -2,183 lines |
| Methods | 45 | <20 | -25 methods |
| Try/finally blocks | 37/30 | 0 | -37/-30 |
| Connection calls | 62 | 0 | -62 calls |
| Provider abstraction | 0 files | 3 files | +3 files needed |
| Tests passing | 44/44 | 44/44 | ✅ All passing |

### Benefits of Completing Extraction

1. **Code Reduction**: 83% reduction in boilerplate (6 lines → 1 line per method)
2. **Testability**: Inject SingleClientProvider for fast unit tests (no pool overhead)
3. **Flexibility**: Easy to swap pool/single/mock implementations
4. **Safety**: Context managers prevent resource leaks
5. **Clarity**: Business logic separated from connection management

### Next Steps

To complete this refactoring:
1. Create QdrantClientProvider interface (abstract base class)
2. Create PooledClientProvider (wraps existing QdrantConnectionPool)
3. Create SingleClientProvider (simple implementation for testing)
4. Refactor QdrantStore to use provider with context managers
5. Update all 45 methods to use `async with provider.get_client() as client:`
6. Remove _get_client() and _release_client() methods
7. Update tests to inject providers

---

## 1. Overview

### Problem Summary
The `QdrantMemoryStore` class (2,953 lines, 45 methods) violates the Single Responsibility Principle by mixing connection pooling logic with business logic. This creates:

- **Tight coupling**: Can't test business logic without connection pool
- **Poor reusability**: Can't reuse connection pool for other stores
- **Complex initialization**: 100+ lines of pool setup code embedded in store
- **Maintenance burden**: Connection pool bugs require editing massive store file

**Current State:**
- Connection pool logic: ~400 lines scattered across `qdrant_store.py`
- Separate `connection_pool.py` exists but is underutilized
- Store directly manages pool lifecycle (create, health checks, monitoring)
- Pool configuration mixed with store configuration

**Good News:** A `QdrantConnectionPool` class already exists in `src/store/connection_pool.py`, but it's not properly extracted/separated from business logic.

### Impact Assessment

**Code Quality:**
- `qdrant_store.py`: 2,953 lines (should be <500)
- Methods: 45 (should be ~15 for business logic)
- Responsibilities: Connection pooling + vector operations + metadata management + call graph + project stats + file tracking

**Testing Challenges:**
- Can't unit test store without mocking pool
- Can't unit test pool without mocking Qdrant
- Integration tests conflate pool and store failures
- 50+ test files mock both store and pool

**Maintenance Issues:**
- Bug fix in pool requires understanding entire store
- Performance tuning pool affects store code
- Can't reuse pool for other vector stores (future: Pinecone, Weaviate)

**Risk Level:** **HIGH** - Monolithic design prevents proper testing and evolution

---

## 2. Current State Analysis

### Existing Connection Pool Implementation

#### What Already Exists

**File:** `src/store/connection_pool.py` (exists!)

**Current Implementation:**
```python
class QdrantConnectionPool:
    """Connection pool for QdrantClient instances.

    Manages a pool of QdrantClient connections with:
    - Min/max pool sizing
    - Connection health checking
    - Age-based recycling
    - Acquisition timeout
    - Performance metrics
    """

    def __init__(
        self,
        config: ServerConfig,
        min_size: int = 1,
        max_size: int = 5,
        timeout: float = 10.0,
        recycle: int = 3600,
        enable_health_checks: bool = True,
        enable_monitoring: bool = False,
    ):
        # ... initialization ...

    async def initialize(self) -> None:
        """Initialize the pool and create minimum connections."""

    async def acquire(self) -> QdrantClient:
        """Acquire a connection from the pool."""

    async def release(self, client: QdrantClient) -> None:
        """Release a connection back to the pool."""

    async def close(self) -> None:
        """Close all connections in the pool."""

    def get_stats(self) -> PoolStats:
        """Get pool statistics."""
```

**Key Features:**
- Connection lifecycle management
- Health checking
- Performance monitoring
- Statistics tracking

**Size:** ~600 lines (well-scoped)

#### What's Still Mixed in QdrantStore

**File:** `src/store/qdrant_store.py` (2,953 lines)

**Connection-Related Code Still in Store:**

1. **Pool Initialization (lines 49-84)**
```python
async def initialize(self) -> None:
    """Initialize the Qdrant connection/pool and collection."""
    try:
        if self.use_pool:
            # Create connection pool - disable health checks during initialization
            await self.setup.create_pool(
                enable_health_checks=False,
                enable_monitoring=False,
            )
            # Acquire a temporary client to ensure collection exists
            client = await self.setup.pool.acquire()
            try:
                # Use temporary client for setup
                old_client = self.setup.client
                self.setup.client = client
                self.setup.ensure_collection_exists()
                self.setup.client = old_client
            finally:
                await self.setup.pool.release(client)

            # Now enable health checks since collection exists
            if self.setup.pool:
                self.setup.pool.enable_health_checks = True
                from src.store.connection_health_checker import ConnectionHealthChecker
                self.setup.pool._health_checker = ConnectionHealthChecker()
```

**Problems:**
- Store knows about pool internals (`enable_health_checks`, `_health_checker`)
- Temporary client acquisition is awkward
- Health check enable/disable logic is fragile

2. **Client Acquisition (lines 85-101)**
```python
async def _get_client(self) -> QdrantClient:
    """Get a Qdrant client (from pool or single client)."""
    if self.use_pool:
        if self.setup.pool is None:
            await self.initialize()
        return await self.setup.pool.acquire()
    else:
        if self.client is None:
            await self.initialize()
        return self.client
```

**Problems:**
- Mixed responsibility (pool vs single client mode)
- Lazy initialization hidden in getter
- No clear ownership of client lifecycle

3. **Client Release Pattern (repeated 40+ times)**
```python
async def batch_store(self, memories: List[MemoryUnit]) -> List[str]:
    """Store multiple memories."""
    client = None
    try:
        client = await self._get_client()
        # ... business logic ...
    finally:
        if client is not None and self.use_pool:
            await self.setup.pool.release(client)
```

**Problems:**
- Repetitive try/finally blocks (40+ occurrences)
- Easy to forget release (resource leak risk)
- Verbose (5 lines of boilerplate per method)

4. **Pool Configuration (mixed with store config)**
```python
# src/store/qdrant_setup.py
async def create_pool(
    self,
    min_size: int = 2,
    max_size: int = 10,
    timeout: float = 30.0,
    recycle: int = 3600,
    enable_health_checks: bool = True,
    enable_monitoring: bool = False,
) -> None:
    """Create connection pool with specified parameters."""
```

**Problems:**
- Pool config spread across multiple files
- No single source of truth
- Hard to change pool defaults

### Separation Needed

#### What Should Be in ConnectionPool

**Responsibility:** Manage lifecycle of QdrantClient connections

**Methods:**
- `initialize()` - Create initial connections
- `acquire()` - Get connection from pool
- `release(client)` - Return connection to pool
- `close()` - Shutdown pool
- `get_stats()` - Pool metrics
- `health_check()` - Verify pool health

**Dependencies:**
- `QdrantClient` (Qdrant SDK)
- `ServerConfig` (for connection parameters)
- `ConnectionHealthChecker` (for health checks)
- `ConnectionPoolMonitor` (for metrics)

**No Dependencies On:**
- MemoryStore interface
- MemoryUnit models
- Search logic
- Collection management

#### What Should Be in QdrantStore

**Responsibility:** Business logic for memory storage and retrieval

**Methods:**
- `store(memory)` - Store single memory
- `batch_store(memories)` - Store multiple memories
- `retrieve(memory_id)` - Get memory by ID
- `search(query, filters)` - Search memories
- `update(memory_id, updates)` - Update memory
- `delete(memory_id)` - Delete memory
- `list_memories(filters, pagination)` - List memories

**Dependencies:**
- `ConnectionPool` (or client provider interface)
- `MemoryUnit` models
- `SearchFilters` models
- Collection schema

**No Dependencies On:**
- Pool implementation details
- Health checking logic
- Connection recycling

---

## 3. Proposed Solution

### Architecture: Layered Separation

```
┌─────────────────────────────────────┐
│      MemoryRAGServer (API Layer)    │
│  - Handles MCP tool calls           │
│  - Orchestrates operations          │
└───────────────┬─────────────────────┘
                │
                ▼
┌─────────────────────────────────────┐
│    QdrantMemoryStore (Business)     │
│  - store(), retrieve(), search()    │
│  - Business logic only              │
│  - No pool management               │
└───────────────┬─────────────────────┘
                │
                ▼
┌─────────────────────────────────────┐
│   QdrantClientProvider (Adapter)    │  ← NEW
│  - Provides client instances        │
│  - Handles acquire/release          │
│  - Abstract interface               │
└───────────────┬─────────────────────┘
                │
        ┌───────┴───────┐
        ▼               ▼
┌──────────────┐  ┌──────────────────┐
│ PooledClient │  │  SingleClient    │
│   Provider   │  │    Provider      │
│ (production) │  │ (testing/simple) │
└──────┬───────┘  └──────────────────┘
       │
       ▼
┌─────────────────────────────────────┐
│  QdrantConnectionPool (Pool Mgmt)   │
│  - Connection lifecycle             │
│  - Health checking                  │
│  - Metrics                          │
└─────────────────────────────────────┘
```

### New Abstractions

#### 1. QdrantClientProvider (Interface)

**Purpose:** Abstract how QdrantClients are provided (pool vs single vs mock)

```python
# src/store/client_provider.py
from abc import ABC, abstractmethod
from typing import AsyncContextManager
from qdrant_client import QdrantClient

class QdrantClientProvider(ABC):
    """Abstract interface for providing QdrantClient instances."""

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the provider (create pool, connect, etc.)."""

    @abstractmethod
    def get_client(self) -> AsyncContextManager[QdrantClient]:
        """Get a client instance via async context manager.

        Usage:
            async with provider.get_client() as client:
                # Use client
                ...
            # Client automatically released
        """

    @abstractmethod
    async def close(self) -> None:
        """Close all connections and cleanup."""

    @abstractmethod
    def get_stats(self) -> Dict[str, Any]:
        """Get provider statistics."""
```

**Benefits:**
- Store doesn't know if using pool or single client
- Easy to swap implementations (testing, production, mock)
- Enforces proper resource cleanup via context manager

#### 2. PooledClientProvider (Production Implementation)

**Purpose:** Provide clients from connection pool

```python
# src/store/pooled_client_provider.py
from contextlib import asynccontextmanager
from typing import AsyncIterator, Dict, Any, Optional
from qdrant_client import QdrantClient

from src.store.client_provider import QdrantClientProvider
from src.store.connection_pool import QdrantConnectionPool
from src.config import ServerConfig

class PooledClientProvider(QdrantClientProvider):
    """Provides QdrantClient instances from a connection pool."""

    def __init__(
        self,
        config: ServerConfig,
        min_size: int = 2,
        max_size: int = 10,
        timeout: float = 30.0,
        recycle: int = 3600,
        enable_health_checks: bool = True,
        enable_monitoring: bool = False,
    ):
        self.config = config
        self.pool = QdrantConnectionPool(
            config=config,
            min_size=min_size,
            max_size=max_size,
            timeout=timeout,
            recycle=recycle,
            enable_health_checks=enable_health_checks,
            enable_monitoring=enable_monitoring,
        )

    async def initialize(self) -> None:
        """Initialize the connection pool."""
        await self.pool.initialize()

    @asynccontextmanager
    async def get_client(self) -> AsyncIterator[QdrantClient]:
        """Get a client from the pool (context manager).

        Automatically acquires and releases client.
        """
        client = await self.pool.acquire()
        try:
            yield client
        finally:
            await self.pool.release(client)

    async def close(self) -> None:
        """Close the connection pool."""
        await self.pool.close()

    def get_stats(self) -> Dict[str, Any]:
        """Get pool statistics."""
        stats = self.pool.get_stats()
        return {
            "pool_size": stats.pool_size,
            "active_connections": stats.active_connections,
            "idle_connections": stats.idle_connections,
            "total_acquires": stats.total_acquires,
            "total_releases": stats.total_releases,
            "avg_acquire_time_ms": stats.avg_acquire_time_ms,
        }
```

#### 3. SingleClientProvider (Simple/Testing Implementation)

**Purpose:** Provide single client (no pooling, simpler for tests)

```python
# src/store/single_client_provider.py
from contextlib import asynccontextmanager
from typing import AsyncIterator, Dict, Any, Optional
from qdrant_client import QdrantClient

from src.store.client_provider import QdrantClientProvider
from src.config import ServerConfig

class SingleClientProvider(QdrantClientProvider):
    """Provides a single QdrantClient instance (no pooling).

    Useful for:
    - Simple deployments
    - Testing
    - Development
    """

    def __init__(self, config: ServerConfig):
        self.config = config
        self._client: Optional[QdrantClient] = None
        self._acquire_count = 0

    async def initialize(self) -> None:
        """Connect to Qdrant."""
        if self._client is None:
            self._client = QdrantClient(
                url=self.config.qdrant_url,
                api_key=self.config.qdrant_api_key,
                timeout=self.config.qdrant_timeout,
            )

    @asynccontextmanager
    async def get_client(self) -> AsyncIterator[QdrantClient]:
        """Get the single client instance (context manager).

        Note: Same client returned every time (no pooling).
        """
        if self._client is None:
            await self.initialize()

        self._acquire_count += 1
        try:
            yield self._client
        finally:
            pass  # No release needed for single client

    async def close(self) -> None:
        """Close the client connection."""
        if self._client is not None:
            self._client.close()
            self._client = None

    def get_stats(self) -> Dict[str, Any]:
        """Get simple statistics."""
        return {
            "mode": "single",
            "connected": self._client is not None,
            "total_uses": self._acquire_count,
        }
```

#### 4. Refactored QdrantMemoryStore

**Purpose:** Business logic only, no pool management

```python
# src/store/qdrant_store.py (refactored)
from typing import List, Optional, Dict, Any
from qdrant_client.models import PointStruct, Filter

from src.store.base import MemoryStore
from src.store.client_provider import QdrantClientProvider
from src.core.models import MemoryUnit, SearchFilters, SearchResult
from src.core.exceptions import StorageError, MemoryNotFoundError
from src.config import ServerConfig

class QdrantMemoryStore(MemoryStore):
    """Qdrant implementation of the MemoryStore interface.

    Business logic only - delegates connection management to provider.
    """

    def __init__(
        self,
        config: Optional[ServerConfig] = None,
        client_provider: Optional[QdrantClientProvider] = None,
    ):
        """
        Initialize Qdrant memory store.

        Args:
            config: Server configuration. If None, uses global config.
            client_provider: Client provider. If None, creates PooledClientProvider.
        """
        if config is None:
            from src.config import get_config
            config = get_config()

        self.config = config
        self.collection_name = config.qdrant_collection_name

        # Use provided client provider or create default
        if client_provider is None:
            from src.store.pooled_client_provider import PooledClientProvider
            self.client_provider = PooledClientProvider(
                config=config,
                min_size=config.pool_min_size,
                max_size=config.pool_max_size,
                timeout=config.pool_timeout,
            )
        else:
            self.client_provider = client_provider

    async def initialize(self) -> None:
        """Initialize the client provider and ensure collection exists."""
        await self.client_provider.initialize()

        # Ensure collection exists (using client from provider)
        async with self.client_provider.get_client() as client:
            from src.store.qdrant_setup import ensure_collection_exists
            ensure_collection_exists(client, self.collection_name, self.config)

    async def store(self, memory: MemoryUnit) -> str:
        """Store a single memory unit.

        No connection management - just business logic!
        """
        async with self.client_provider.get_client() as client:
            # Generate ID
            memory_id = str(uuid4())

            # Create point
            point = PointStruct(
                id=memory_id,
                vector=memory.embedding,
                payload={
                    "content": memory.content,
                    "category": memory.category.value,
                    "importance": memory.importance,
                    # ... other fields ...
                },
            )

            # Store in Qdrant
            client.upsert(
                collection_name=self.collection_name,
                points=[point],
            )

            return memory_id

    async def batch_store(self, memories: List[MemoryUnit]) -> List[str]:
        """Store multiple memory units.

        Notice: No try/finally, no manual acquire/release!
        Context manager handles everything.
        """
        async with self.client_provider.get_client() as client:
            memory_ids = []
            points = []

            for memory in memories:
                memory_id = str(uuid4())
                memory_ids.append(memory_id)

                points.append(PointStruct(
                    id=memory_id,
                    vector=memory.embedding,
                    payload=self._memory_to_payload(memory),
                ))

            # Batch upsert
            client.upsert(
                collection_name=self.collection_name,
                points=points,
            )

            return memory_ids

    async def retrieve(self, memory_id: str) -> MemoryUnit:
        """Retrieve a memory by ID."""
        async with self.client_provider.get_client() as client:
            points = client.retrieve(
                collection_name=self.collection_name,
                ids=[memory_id],
            )

            if not points:
                raise MemoryNotFoundError(f"Memory {memory_id} not found")

            return self._point_to_memory(points[0])

    async def search(
        self,
        query_vector: List[float],
        filters: Optional[SearchFilters] = None,
        limit: int = 10,
    ) -> List[SearchResult]:
        """Search for memories by vector similarity."""
        async with self.client_provider.get_client() as client:
            # Build filter
            qdrant_filter = self._build_filter(filters) if filters else None

            # Search
            results = client.search(
                collection_name=self.collection_name,
                query_vector=query_vector,
                query_filter=qdrant_filter,
                limit=limit,
            )

            # Convert to SearchResult
            return [
                SearchResult(
                    memory=self._point_to_memory(result),
                    score=result.score,
                    retrieval_context={},
                )
                for result in results
            ]

    async def close(self) -> None:
        """Close the client provider."""
        await self.client_provider.close()

    def get_stats(self) -> Dict[str, Any]:
        """Get store and provider statistics."""
        provider_stats = self.client_provider.get_stats()
        return {
            "provider": provider_stats,
            "collection": self.collection_name,
        }

    # ... other business logic methods ...
```

**Benefits of Refactored Store:**
- **Simplified:** No try/finally blocks (40+ removed)
- **Cleaner:** Business logic clearly separated
- **Testable:** Can inject fake provider for testing
- **Flexible:** Easy to swap pool vs single vs mock
- **Safer:** Context manager prevents resource leaks

---

## 4. Implementation Plan

### Phase 1: Create Abstractions (Day 1)

#### Morning: Define Interfaces

**Step 1.1: Create QdrantClientProvider Interface**
- [ ] Create `src/store/client_provider.py`
- [ ] Define `QdrantClientProvider` abstract class
- [ ] Add type hints and docstrings
- [ ] Create unit tests

**Files Created:**
- `src/store/client_provider.py` (~100 lines)
- `tests/unit/test_client_provider.py` (~50 lines)

**Step 1.2: Create SingleClientProvider**
- [ ] Create `src/store/single_client_provider.py`
- [ ] Implement `SingleClientProvider` class
- [ ] Add unit tests
- [ ] Test in isolation

**Files Created:**
- `src/store/single_client_provider.py` (~150 lines)
- `tests/unit/test_single_client_provider.py` (~100 lines)

#### Afternoon: Create PooledClientProvider

**Step 1.3: Create PooledClientProvider**
- [ ] Create `src/store/pooled_client_provider.py`
- [ ] Implement `PooledClientProvider` wrapping existing `QdrantConnectionPool`
- [ ] Add unit tests
- [ ] Integration tests with real Qdrant

**Files Created:**
- `src/store/pooled_client_provider.py` (~200 lines)
- `tests/unit/test_pooled_client_provider.py` (~150 lines)
- `tests/integration/test_pooled_provider_integration.py` (~100 lines)

**Validation:**
```bash
# Run new tests
pytest tests/unit/test_*_client_provider.py -v
pytest tests/integration/test_pooled_provider_integration.py -v

# Verify coverage
pytest tests/unit/test_*_client_provider.py --cov=src/store --cov-report=term-missing
```

### Phase 2: Refactor QdrantStore (Day 2)

#### Morning: Update Store Constructor

**Step 2.1: Add client_provider Parameter**
- [ ] Update `QdrantMemoryStore.__init__()` to accept `client_provider`
- [ ] Create default provider if not provided
- [ ] Update tests to use `SingleClientProvider` for speed

**Changes:**
- `src/store/qdrant_store.py` (constructor only)
- Update 10+ test files to inject provider

**Step 2.2: Refactor initialize() Method**
- [ ] Remove pool creation logic
- [ ] Delegate to `client_provider.initialize()`
- [ ] Simplify collection creation

**Before:**
```python
async def initialize(self) -> None:
    # 35 lines of pool setup
```

**After:**
```python
async def initialize(self) -> None:
    """Initialize the client provider and ensure collection exists."""
    await self.client_provider.initialize()

    async with self.client_provider.get_client() as client:
        ensure_collection_exists(client, self.collection_name, self.config)
```

#### Afternoon: Refactor Business Methods

**Step 2.3: Refactor store() and batch_store()**
- [ ] Replace try/finally with context manager
- [ ] Remove `_get_client()` and `_release_client()` calls
- [ ] Simplify error handling

**Step 2.4: Refactor retrieve(), search(), update(), delete()**
- [ ] Apply same context manager pattern
- [ ] Remove connection management boilerplate

**Step 2.5: Refactor Metadata Methods**
- [ ] `get_project_stats()`
- [ ] `list_projects()`
- [ ] `get_file_info()`
- [ ] etc. (~20 methods)

**Estimate:** 40+ methods need refactoring

**Strategy:**
- Use search/replace for common patterns
- Refactor in batches (5-10 methods at a time)
- Run tests after each batch

### Phase 3: Update Dependent Code (Day 3)

#### Morning: Update Tests

**Step 3.1: Update Unit Tests**
- [ ] Inject `SingleClientProvider` for fast tests
- [ ] Remove connection pool mocks
- [ ] Simplify test setup

**Example:**
```python
# Before
mock_store = MagicMock()
mock_store.client = MagicMock()
mock_store._get_client = AsyncMock(return_value=mock_client)
# ... 10 more lines ...

# After
provider = SingleClientProvider(config)
store = QdrantMemoryStore(config, client_provider=provider)
```

**Files to Update:** ~30 test files

**Step 3.2: Update Integration Tests**
- [ ] Use `PooledClientProvider` for integration tests
- [ ] Test connection pool behavior explicitly
- [ ] Verify resource cleanup

#### Afternoon: Update Server Code

**Step 3.3: Update MemoryRAGServer**
- [ ] Update server initialization to create provider
- [ ] Pass provider to QdrantMemoryStore
- [ ] Update config handling

**Step 3.4: Update CLI Commands**
- [ ] Update `index_command.py`
- [ ] Update `status_command.py`
- [ ] Update any other commands using store

**Step 3.5: Update Documentation**
- [ ] Update ARCHITECTURE.md
- [ ] Update API.md
- [ ] Update TESTING_GUIDE.md
- [ ] Add examples to README.md

---

## 5. Testing Strategy

### Unit Tests

#### Test QdrantClientProvider Interface
```python
# tests/unit/test_client_provider.py
import pytest
from src.store.client_provider import QdrantClientProvider

def test_client_provider_is_abstract():
    """Test that QdrantClientProvider cannot be instantiated."""
    with pytest.raises(TypeError):
        provider = QdrantClientProvider()
```

#### Test SingleClientProvider
```python
# tests/unit/test_single_client_provider.py
import pytest
from src.store.single_client_provider import SingleClientProvider
from src.config import ServerConfig

@pytest.mark.unit
@pytest.mark.asyncio
async def test_single_provider_initialization():
    """Test single provider initializes client."""
    config = ServerConfig(qdrant_url="http://localhost:6333")
    provider = SingleClientProvider(config)

    await provider.initialize()

    stats = provider.get_stats()
    assert stats["mode"] == "single"
    assert stats["connected"] is True

@pytest.mark.unit
@pytest.mark.asyncio
async def test_single_provider_context_manager():
    """Test context manager provides client."""
    config = ServerConfig(qdrant_url="http://localhost:6333")
    provider = SingleClientProvider(config)
    await provider.initialize()

    async with provider.get_client() as client:
        assert client is not None
        # Same client every time
        async with provider.get_client() as client2:
            assert client is client2

    await provider.close()
```

#### Test PooledClientProvider
```python
# tests/unit/test_pooled_client_provider.py
import pytest
from src.store.pooled_client_provider import PooledClientProvider
from src.config import ServerConfig

@pytest.mark.unit
@pytest.mark.asyncio
async def test_pooled_provider_initialization():
    """Test pooled provider creates pool."""
    config = ServerConfig(qdrant_url="http://localhost:6333")
    provider = PooledClientProvider(
        config=config,
        min_size=2,
        max_size=5,
    )

    await provider.initialize()

    stats = provider.get_stats()
    assert stats["pool_size"] >= 2  # Min connections created
    assert stats["idle_connections"] >= 2

    await provider.close()

@pytest.mark.unit
@pytest.mark.asyncio
async def test_pooled_provider_concurrent_access():
    """Test pool handles concurrent client acquisition."""
    config = ServerConfig(qdrant_url="http://localhost:6333")
    provider = PooledClientProvider(config, min_size=2, max_size=5)
    await provider.initialize()

    # Acquire 3 clients concurrently
    async def use_client():
        async with provider.get_client() as client:
            await asyncio.sleep(0.1)
            return client

    clients = await asyncio.gather(
        use_client(),
        use_client(),
        use_client(),
    )

    # All clients should be returned
    stats = provider.get_stats()
    assert stats["total_acquires"] == 3
    assert stats["total_releases"] == 3

    await provider.close()
```

#### Test Refactored QdrantStore
```python
# tests/unit/test_qdrant_store_refactored.py
import pytest
from src.store.qdrant_store import QdrantMemoryStore
from src.store.single_client_provider import SingleClientProvider
from src.core.models import MemoryUnit, MemoryCategory

@pytest.mark.unit
@pytest.mark.asyncio
async def test_store_uses_provided_client_provider():
    """Test store uses injected client provider."""
    provider = SingleClientProvider(config)
    store = QdrantMemoryStore(config, client_provider=provider)

    assert store.client_provider is provider

@pytest.mark.unit
@pytest.mark.asyncio
async def test_store_creates_default_provider_if_none():
    """Test store creates PooledClientProvider if none provided."""
    store = QdrantMemoryStore(config)

    assert store.client_provider is not None
    assert isinstance(store.client_provider, PooledClientProvider)
```

### Integration Tests

```python
# tests/integration/test_pooled_store_integration.py
import pytest
from src.store.qdrant_store import QdrantMemoryStore
from src.store.pooled_client_provider import PooledClientProvider
from src.core.models import MemoryUnit, MemoryCategory

@pytest.mark.integration
@pytest.mark.requires_docker
async def test_pooled_store_concurrent_operations(clean_qdrant_container):
    """Test store with pooled provider handles concurrent operations."""
    config = ServerConfig(qdrant_url="http://localhost:6334")
    provider = PooledClientProvider(config, min_size=3, max_size=10)
    store = QdrantMemoryStore(config, client_provider=provider)

    await store.initialize()

    # Store 100 memories concurrently
    memories = [
        MemoryUnit(content=f"Memory {i}", category=MemoryCategory.SYSTEM)
        for i in range(100)
    ]

    async def store_memory(memory):
        return await store.store(memory)

    memory_ids = await asyncio.gather(*[store_memory(m) for m in memories])

    assert len(memory_ids) == 100

    # Verify pool stats
    stats = store.get_stats()
    assert stats["provider"]["total_acquires"] >= 100

    await store.close()
```

### Performance Tests

```python
# tests/performance/test_pool_vs_single.py
import pytest
import time
from src.store.qdrant_store import QdrantMemoryStore
from src.store.pooled_client_provider import PooledClientProvider
from src.store.single_client_provider import SingleClientProvider

@pytest.mark.slow
@pytest.mark.asyncio
async def test_pooled_provider_faster_than_single(clean_qdrant_container):
    """Test pooled provider is faster for concurrent operations."""
    config = ServerConfig(qdrant_url="http://localhost:6334")

    # Test with single provider
    single_provider = SingleClientProvider(config)
    single_store = QdrantMemoryStore(config, client_provider=single_provider)
    await single_store.initialize()

    start = time.time()
    tasks = [single_store.store(MemoryUnit(content=f"Memory {i}")) for i in range(100)]
    await asyncio.gather(*tasks)
    single_time = time.time() - start

    await single_store.close()

    # Test with pooled provider
    pooled_provider = PooledClientProvider(config, min_size=5, max_size=10)
    pooled_store = QdrantMemoryStore(config, client_provider=pooled_provider)
    await pooled_store.initialize()

    start = time.time()
    tasks = [pooled_store.store(MemoryUnit(content=f"Memory {i}")) for i in range(100)]
    await asyncio.gather(*tasks)
    pooled_time = time.time() - start

    await pooled_store.close()

    # Pooled should be faster
    assert pooled_time < single_time
    print(f"Single: {single_time:.2f}s, Pooled: {pooled_time:.2f}s")
    print(f"Speedup: {single_time / pooled_time:.2f}x")
```

---

## 6. Risk Assessment

### High Risks

#### Risk 1: Breaking Existing Code
**Likelihood:** High
**Impact:** High
**Mitigation:**
- Implement provider abstraction first
- Add backward compatibility layer
- Refactor incrementally (method by method)
- Run full test suite after each change
- Use feature flag to toggle between old/new

#### Risk 2: Performance Regression
**Likelihood:** Medium
**Impact:** High
**Mitigation:**
- Add performance benchmarks
- Test with real workloads
- Monitor pool metrics
- Compare before/after metrics
- Load testing before production

### Medium Risks

#### Risk 3: Context Manager Overhead
**Likelihood:** Low
**Impact:** Medium
**Mitigation:**
- Benchmark context manager performance
- Should be negligible (async overhead is tiny)
- Can optimize if needed

#### Risk 4: Test Suite Complexity Increases
**Likelihood:** Medium
**Impact:** Low
**Mitigation:**
- Create helper fixtures for common patterns
- Document test patterns in TESTING_GUIDE.md
- Provide examples

### Low Risks

#### Risk 5: Configuration Confusion
**Likelihood:** Low
**Impact:** Low
**Mitigation:**
- Document clearly in README.md
- Provide sensible defaults
- Add validation

---

## 7. Success Criteria

### Quantitative Metrics

| Metric | Before | After | Measurement |
|--------|--------|-------|-------------|
| QdrantStore LOC | 2,953 | <800 | `wc -l src/store/qdrant_store.py` |
| QdrantStore methods | 45 | <20 | Count public methods |
| Try/finally blocks | 40+ | 0 | `grep -c "try:" src/store/qdrant_store.py` |
| Connection imports in store | 5+ | 0 | `grep "ConnectionPool" src/store/qdrant_store.py` |
| Provider abstraction LOC | 0 | ~450 | New files total |
| Test setup lines (avg) | ~15 | ~3 | Lines to create test store |
| Unit test speed | ~45s | ~20s | Faster with SingleClientProvider |

### Qualitative Metrics

#### Code Quality
- [ ] Store has single responsibility (business logic only)
- [ ] Connection pool fully extracted and reusable
- [ ] Clear separation of concerns
- [ ] No leaky abstractions

#### Testing Improvements
- [ ] Unit tests don't need pool mocking
- [ ] Integration tests explicitly test pool behavior
- [ ] Faster test execution (no pool overhead in unit tests)
- [ ] Easier to write new tests

#### Developer Experience
- [ ] Simpler store code (easier to understand)
- [ ] Context managers prevent resource leaks
- [ ] Clear provider interface (easy to add new providers)
- [ ] Better error messages

### Definition of Done

**This task is complete when:**

1. **Abstractions created** (`QdrantClientProvider`, `PooledClientProvider`, `SingleClientProvider`)
2. **QdrantStore refactored** (uses provider, <800 LOC, <20 methods)
3. **All try/finally removed** (replaced with context managers)
4. **Tests updated** (inject provider, faster unit tests)
5. **Integration tests added** (test pool behavior explicitly)
6. **Performance validated** (no regression, preferably improvement)
7. **Documentation updated** (ARCHITECTURE.md, API.md, TESTING_GUIDE.md)
8. **All tests passing** (100% pass rate)
9. **Coverage maintained** (≥80% on core modules)
10. **verify-complete.py passes** (all 6 gates)

**Approval Required From:**
- Lead architect (design review)
- Lead developer (code review)

---

## 8. Before/After Comparison

### Before: Monolithic Store

**File Structure:**
```
src/store/
├── qdrant_store.py          (2,953 lines - GOD CLASS)
├── connection_pool.py       (600 lines - underutilized)
└── qdrant_setup.py          (400 lines - mixed concerns)
```

**Store Method (Before):**
```python
async def batch_store(self, memories: List[MemoryUnit]) -> List[str]:
    """Store multiple memory units."""
    client = None  # ← Manual tracking
    try:
        # ← 3 lines just to get client
        client = await self._get_client()

        # Business logic (10 lines)
        memory_ids = []
        points = []
        for memory in memories:
            memory_id = str(uuid4())
            memory_ids.append(memory_id)
            points.append(self._create_point(memory_id, memory))

        client.upsert(collection_name=self.collection_name, points=points)

        return memory_ids
    finally:
        # ← 3 lines just to release client
        if client is not None and self.use_pool:
            await self.setup.pool.release(client)
```

**Problems:**
- 6 lines of boilerplate (3 acquire + 3 release)
- Manual client tracking (error-prone)
- Easy to forget release (resource leak)
- Repeated 40+ times across file

### After: Layered Architecture

**File Structure:**
```
src/store/
├── client_provider.py              (100 lines - interface)
├── single_client_provider.py       (150 lines - simple impl)
├── pooled_client_provider.py       (200 lines - pool impl)
├── qdrant_store.py                 (800 lines - business only)
├── connection_pool.py              (600 lines - unchanged)
└── qdrant_setup.py                 (200 lines - simplified)
```

**Store Method (After):**
```python
async def batch_store(self, memories: List[MemoryUnit]) -> List[str]:
    """Store multiple memory units."""
    async with self.client_provider.get_client() as client:  # ← 1 line
        # Business logic (10 lines) - UNCHANGED
        memory_ids = []
        points = []
        for memory in memories:
            memory_id = str(uuid4())
            memory_ids.append(memory_id)
            points.append(self._create_point(memory_id, memory))

        client.upsert(collection_name=self.collection_name, points=points)

        return memory_ids
    # ← Client automatically released
```

**Improvements:**
- 6 lines → 1 line (83% reduction in boilerplate)
- No manual tracking (safer)
- Impossible to forget release (guaranteed cleanup)
- Clearer business logic (no noise)

### Test Setup (Before vs After)

**Before:**
```python
# tests/unit/test_qdrant_store.py
@pytest.mark.asyncio
async def test_batch_store():
    """Test batch store operation."""
    # Mock setup (15 lines)
    mock_pool = MagicMock()
    mock_client = MagicMock()
    mock_pool.acquire = AsyncMock(return_value=mock_client)
    mock_pool.release = AsyncMock()

    mock_setup = MagicMock()
    mock_setup.pool = mock_pool

    config = ServerConfig(qdrant_url="http://localhost:6333")
    store = QdrantMemoryStore(config)
    store.setup = mock_setup
    store.use_pool = True

    # Test (5 lines)
    memories = [MemoryUnit(content="Test")]
    memory_ids = await store.batch_store(memories)

    # Assertions (3 lines)
    assert len(memory_ids) == 1
    mock_pool.acquire.assert_called_once()
    mock_pool.release.assert_called_once()
```

**After:**
```python
# tests/unit/test_qdrant_store.py
@pytest.mark.unit
@pytest.mark.asyncio
async def test_batch_store():
    """Test batch store operation."""
    # Setup (3 lines) - 80% reduction!
    provider = SingleClientProvider(config)
    store = QdrantMemoryStore(config, client_provider=provider)
    await store.initialize()

    # Test (5 lines) - UNCHANGED
    memories = [MemoryUnit(content="Test")]
    memory_ids = await store.batch_store(memories)

    # Assertions (2 lines) - SIMPLER
    assert len(memory_ids) == 1
    # No need to assert on mock calls - testing behavior!
```

---

## 9. Migration Path

### Backward Compatibility Strategy

To avoid breaking existing code, we'll use a phased migration:

#### Phase 1: Dual Mode Support (Weeks 1-2)

**Add provider support but keep old code path:**
```python
class QdrantMemoryStore(MemoryStore):
    def __init__(
        self,
        config: Optional[ServerConfig] = None,
        use_pool: bool = True,  # ← Keep for backward compat
        client_provider: Optional[QdrantClientProvider] = None,  # ← New
    ):
        if client_provider is not None:
            # New path: use provider
            self.client_provider = client_provider
            self._use_provider = True
        else:
            # Old path: use legacy pool
            self.use_pool = use_pool
            self._use_provider = False
            # ... old initialization ...

    async def _get_client_new(self) -> AsyncContextManager[QdrantClient]:
        """New provider-based client acquisition."""
        return self.client_provider.get_client()

    async def _get_client_old(self) -> QdrantClient:
        """Legacy client acquisition (deprecated)."""
        # ... old code ...
```

**Benefits:**
- Existing code keeps working
- New code can use provider
- Gradual migration possible

#### Phase 2: Deprecation Warnings (Week 3)

**Add warnings to legacy code path:**
```python
import warnings

def __init__(self, config, use_pool=True, client_provider=None):
    if client_provider is None:
        warnings.warn(
            "Creating QdrantMemoryStore without client_provider is deprecated. "
            "Please pass a QdrantClientProvider instance. "
            "Legacy mode will be removed in v5.0.",
            DeprecationWarning,
            stacklevel=2,
        )
```

#### Phase 3: Remove Legacy Code (Week 4+)

**After all tests and server code migrated:**
- Remove `use_pool` parameter
- Remove old `_get_client()` method
- Require `client_provider` parameter

---

## 10. Appendix

### Analysis Script: Count Connection Code

```python
#!/usr/bin/env python3
"""Analyze connection-related code in QdrantStore."""

import re
from pathlib import Path

def analyze_qdrant_store():
    """Count connection-related lines in qdrant_store.py."""
    file_path = Path("src/store/qdrant_store.py")
    content = file_path.read_text()
    lines = content.splitlines()

    # Count try/finally blocks
    try_count = len(re.findall(r'^\s*try:', content, re.MULTILINE))

    # Count client acquire/release
    acquire_count = len(re.findall(r'_get_client|pool\.acquire', content))
    release_count = len(re.findall(r'pool\.release|_release_client', content))

    # Count pool-related lines
    pool_lines = [i for i, line in enumerate(lines) if 'pool' in line.lower()]

    print(f"QdrantStore Analysis:")
    print(f"  Total lines: {len(lines)}")
    print(f"  Try/finally blocks: {try_count}")
    print(f"  Client acquisitions: {acquire_count}")
    print(f"  Client releases: {release_count}")
    print(f"  Pool-related lines: {len(pool_lines)}")
    print(f"  Pool-related %: {len(pool_lines) / len(lines) * 100:.1f}%")

if __name__ == "__main__":
    analyze_qdrant_store()
```

**Usage:**
```bash
python scripts/analyze_connection_code.py
```

### Verification Checklist

```bash
# 1. Verify new files created
ls -l src/store/client_provider.py
ls -l src/store/single_client_provider.py
ls -l src/store/pooled_client_provider.py

# 2. Verify store refactored
wc -l src/store/qdrant_store.py  # Should be <800
grep -c "try:" src/store/qdrant_store.py  # Should be 0
grep -c "finally:" src/store/qdrant_store.py  # Should be 0

# 3. Run tests
pytest tests/unit/test_*_client_provider.py -v
pytest tests/unit/test_qdrant_store.py -v
pytest tests/integration/ -v

# 4. Verify performance
pytest tests/performance/test_pool_vs_single.py -v

# 5. Run full suite
pytest tests/ -n auto -v
python scripts/verify-complete.py
```

---

**Next Steps:**
1. Review this plan with team
2. Get architecture approval
3. Create git worktree: `git worktree add .worktrees/REF-019 -b REF-019`
4. Begin Phase 1 implementation
5. Update this document with progress notes
