# FEAT-020: Usage Patterns Tracking

## TODO Reference
- **ID:** FEAT-020
- **Location:** TODO.md, Tier 5: Advanced/Future Features
- **Description:** Track most searched queries, identify frequently accessed code, user behavior analytics

## Objective
Implement usage pattern tracking to understand how users interact with the system, identify frequently accessed code, and track search patterns to improve recommendations and system optimization.

## Current State
- The system stores and retrieves memories but doesn't track usage patterns
- No analytics on which queries are most common
- No tracking of which code files/functions are accessed most frequently
- No insights into user behavior for optimization

## User Impact
- **Value:** Surface frequently used code automatically
- **Use case:** "Show me the code I reference most often"
- **Optimization:** Identify hot paths for caching/pre-loading
- **Analytics:** Understand user behavior to improve features

## Implementation Plan

### Phase 1: Database Schema (1 hour)
**File:** `src/store/usage_tracker_schema.py`

Create tables for tracking:
1. **query_history** - Track all search queries
   - id, timestamp, query_text, result_count, execution_time_ms, user_session

2. **code_access_log** - Track accessed code files/functions
   - id, timestamp, file_path, function_name, access_type (search, retrieve, view), user_session

3. **usage_statistics** - Aggregated stats (updated periodically)
   - query_text, access_count, last_accessed, avg_result_count
   - file_path, function_name, access_count, last_accessed

### Phase 2: UsageTracker Class (2-3 hours)
**File:** `src/analytics/usage_tracker.py`

```python
class UsageTracker:
    """Track usage patterns for analytics and optimization."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._setup_database()

    async def track_query(self, query: str, result_count: int, execution_time_ms: float):
        """Log a search query."""
        pass

    async def track_code_access(self, file_path: str, function_name: Optional[str], access_type: str):
        """Log code access."""
        pass

    async def get_top_queries(self, limit: int = 10, days: int = 30) -> List[dict]:
        """Get most frequent queries."""
        pass

    async def get_frequently_accessed_code(self, limit: int = 10, days: int = 30) -> List[dict]:
        """Get most accessed code files/functions."""
        pass

    async def get_usage_stats(self, days: int = 30) -> dict:
        """Get overall usage statistics."""
        pass
```

### Phase 3: Integration with Server (1-2 hours)
**File:** `src/core/server.py`

Integrate tracking into existing methods:
- `retrieve_memories()` - Track query and accessed memories
- `search_code()` - Track code search queries
- `get_semantic_units()` - Track code unit access

Add tracking calls:
```python
# In retrieve_memories
await self.usage_tracker.track_query(query, len(results), execution_time)

# In search_code
await self.usage_tracker.track_code_access(file_path, function_name, "search")
```

### Phase 4: MCP Tools for Analytics (1-2 hours)
**Files:** `src/core/server.py`, `src/mcp_server.py`

Add new MCP tools:
1. **get_usage_statistics** - Get overall usage stats
2. **get_top_queries** - Get most searched queries
3. **get_frequently_accessed_code** - Get most accessed code

### Phase 5: Testing (2 hours)
**File:** `tests/unit/test_usage_tracker.py`

Test coverage:
- Query tracking and retrieval
- Code access tracking
- Top queries calculation
- Frequently accessed code calculation
- Statistics generation
- Time-based filtering
- Database operations

**Expected:** 15-20 tests, aiming for 90%+ coverage

### Phase 6: Documentation (30 min)
**Files to update:**
- `docs/API.md` - Document new MCP tools
- `CHANGELOG.md` - Add FEAT-020 entry
- `README.md` - Mention analytics features (optional)

## Technical Design

### Database Schema Details

```sql
CREATE TABLE query_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    query_text TEXT NOT NULL,
    result_count INTEGER,
    execution_time_ms REAL,
    user_session TEXT,
    query_type TEXT  -- 'memory', 'code', 'doc'
);

CREATE TABLE code_access_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    file_path TEXT NOT NULL,
    function_name TEXT,
    access_type TEXT,  -- 'search', 'retrieve', 'view'
    user_session TEXT
);

CREATE TABLE usage_statistics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stat_type TEXT,  -- 'query' or 'code_access'
    item_key TEXT,  -- query text or file path
    access_count INTEGER DEFAULT 1,
    last_accessed DATETIME,
    avg_result_count REAL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(stat_type, item_key)
);

-- Indexes for performance
CREATE INDEX idx_query_timestamp ON query_history(timestamp);
CREATE INDEX idx_code_access_timestamp ON code_access_log(timestamp);
CREATE INDEX idx_usage_stats_type ON usage_statistics(stat_type, access_count DESC);
```

### Analytics Calculations

**Top Queries (by frequency):**
```sql
SELECT query_text, COUNT(*) as count,
       AVG(result_count) as avg_results,
       MAX(timestamp) as last_used
FROM query_history
WHERE timestamp > datetime('now', '-30 days')
GROUP BY query_text
ORDER BY count DESC
LIMIT 10;
```

**Frequently Accessed Code:**
```sql
SELECT file_path, function_name, COUNT(*) as count,
       MAX(timestamp) as last_accessed
FROM code_access_log
WHERE timestamp > datetime('now', '-30 days')
GROUP BY file_path, function_name
ORDER BY count DESC
LIMIT 10;
```

### Privacy Considerations
- User session IDs are optional and can be anonymized
- No personal information stored
- Data retention policy (auto-delete after 90 days)
- Option to disable tracking via config

## Test Plan

### Unit Tests
1. **Database Operations:**
   - Create tables
   - Insert query history
   - Insert code access log
   - Query aggregations

2. **Tracking Functions:**
   - Track query correctly
   - Track code access correctly
   - Handle duplicate entries
   - Time-based filtering

3. **Analytics Functions:**
   - Top queries calculation
   - Frequently accessed code
   - Usage statistics
   - Empty data handling

4. **Edge Cases:**
   - No data in time range
   - Very large datasets
   - Concurrent access
   - Invalid inputs

### Integration Tests
1. **End-to-End:**
   - Search → Track → Retrieve stats
   - Code access → Track → Retrieve stats

2. **MCP Tools:**
   - get_usage_statistics works correctly
   - get_top_queries returns expected data
   - get_frequently_accessed_code filters properly

## Implementation Checklist

- [ ] Create `src/analytics/usage_tracker.py`
- [ ] Implement database schema setup
- [ ] Implement query tracking
- [ ] Implement code access tracking
- [ ] Implement top queries retrieval
- [ ] Implement frequently accessed code retrieval
- [ ] Implement usage statistics calculation
- [ ] Integrate with `src/core/server.py` retrieve_memories
- [ ] Integrate with code search methods
- [ ] Add `get_usage_statistics()` MCP tool
- [ ] Add `get_top_queries()` MCP tool
- [ ] Add `get_frequently_accessed_code()` MCP tool
- [ ] Register tools in `src/mcp_server.py`
- [ ] Create comprehensive test suite (15-20 tests)
- [ ] Update `docs/API.md`
- [ ] Update `CHANGELOG.md`
- [ ] Run full test suite
- [ ] Commit following project protocol

## Code Examples

### Usage Tracking Integration
```python
# In server.py retrieve_memories
async def retrieve_memories(self, request):
    start_time = time.time()

    # Existing retrieval logic
    results = await self._do_retrieval(request.query)

    # Track usage
    execution_time = (time.time() - start_time) * 1000
    if self.usage_tracker:
        await self.usage_tracker.track_query(
            query=request.query,
            result_count=len(results),
            execution_time_ms=execution_time
        )

    return results
```

### MCP Tool Example
```python
async def get_usage_statistics(self, days: int = 30) -> dict:
    """Get usage statistics for the past N days."""
    if not self.usage_tracker:
        raise ValueError("Usage tracking not enabled")

    stats = await self.usage_tracker.get_usage_stats(days=days)

    return {
        "period_days": days,
        "total_queries": stats["total_queries"],
        "unique_queries": stats["unique_queries"],
        "total_code_accesses": stats["total_code_accesses"],
        "unique_files_accessed": stats["unique_files"],
        "avg_query_time_ms": stats["avg_query_time"],
        "most_active_day": stats["most_active_day"]
    }
```

## Success Criteria

1. ✅ Usage tracking database schema created and tested
2. ✅ Query tracking working for all search operations
3. ✅ Code access tracking working for code searches
4. ✅ Top queries API returns accurate results
5. ✅ Frequently accessed code API works correctly
6. ✅ 15-20 tests, all passing, 90%+ coverage
7. ✅ Documentation updated in API.md
8. ✅ Full test suite passes (maintain 99%+ pass rate)

## Progress Tracking

**Status:** In Progress
**Started:** 2025-11-18

### Completed
- [ ] Planning document created

### In Progress
- [ ] Implementation

### Blocked
- None

## Notes & Decisions

- **Storage:** Using SQLite for usage tracking (separate from main memory store)
- **Privacy:** Anonymous by default, optional session tracking
- **Performance:** Async operations, don't block main request path
- **Retention:** Auto-cleanup data older than 90 days
- **Configuration:** New config option `enable_usage_tracking` (default: true)

## Completion Summary
(To be filled in when complete)
