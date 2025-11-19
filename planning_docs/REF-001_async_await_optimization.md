# REF-001: Async/Await Pattern Optimization

## Objective
Optimize async/await patterns for better performance by fixing 194 async functions that don't use await.

## Analysis Summary

### Total Issues: 194 async functions without await

**Breakdown by Category:**
- Cache Operations (5): `cache.get()`, `cache.set()`, `batch_get()`, `clean_old()`, `clear()`
- Generators (3): `close()` methods in generator.py and parallel_generator.py
- MCP Handlers (7): Protocol-required async methods in mcp_server.py
- Server Methods (13): Methods in core/server.py
- Other (166): Various utility and service methods

## Strategy

### Phase 1: Cache Operations (5 functions) ✅ IN PROGRESS
**Issue**: SQLite operations are synchronous/blocking but wrapped in async
**Impact**: HIGH - called frequently during indexing
**Approach**: Keep async signature but use `await asyncio.to_thread()` for blocking ops
**Files**: `src/embeddings/cache.py`

### Phase 2: MCP Handlers (7 functions)
**Issue**: No await in handlers
**Impact**: LOW - required by MCP protocol
**Approach**: Keep as-is, add documentation comment
**Files**: `src/mcp_server.py`

### Phase 3: Generator Methods (3 functions)
**Issue**: `close()` methods don't await
**Impact**: MEDIUM - cleanup operations
**Approach**: Convert to sync or add proper async cleanup

### Phase 4: Server Methods (13 functions)
**Issue**: Various patterns
**Impact**: MEDIUM-HIGH
**Approach**: Case-by-case analysis

### Phase 5: Other Methods (166 functions)
**Issue**: Various utility functions
**Impact**: Variable
**Approach**: Systematic review and conversion

## Current Progress

- [x] Analysis complete
- [ ] Phase 1: Cache operations
- [ ] Phase 2: MCP handlers
- [ ] Phase 3: Generators
- [ ] Phase 4: Server methods
- [ ] Phase 5: Other methods
- [ ] Testing
- [ ] Merge

## Test Plan

1. Run full test suite after each phase
2. Performance benchmarks for cache operations
3. Verify MCP protocol compatibility
4. Integration tests for embedding generation

## Notes

- MCP handlers MUST stay async (protocol requirement)
- SQLite operations are blocking - should run in thread pool
- Some functions may need to stay async for API compatibility
