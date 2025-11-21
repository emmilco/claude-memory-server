# REF-013: server.py Refactoring Strategy

## Reference
- **TODO**: Code review recommendation #6
- **Issue**: server.py is 5155 lines - very large for maintainability
- **Priority**: Medium (plan now, execute later)

## Current State

**File:** `src/core/server.py` - 5155 lines

**Contains:**
- MemoryRAGServer class (main MCP server)
- 16+ MCP tool implementations
- Stats tracking
- Multiple subsystem integrations (monitoring, search, memory, etc.)

## Problem

Large files (>1000 lines) are harder to:
- Navigate and understand
- Review in PRs
- Test in isolation
- Maintain over time
- Collaborate on (merge conflicts)

## Proposed Strategy

### Option 1: Extract MCP Tool Handlers (Recommended)

Create `src/core/handlers/` directory with one file per tool category:

```
src/core/handlers/
├── __init__.py
├── memory_handlers.py      # store_memory, retrieve_memories, delete_memory
├── code_handlers.py         # index_codebase, search_code, find_similar_code
├── project_handlers.py      # list_projects, get_project_details, etc.
├── monitoring_handlers.py   # get_health_score, get_performance_metrics, etc.
├── git_handlers.py          # search_git_history, get_file_history
└── admin_handlers.py        # get_status, export_memories, import_memories
```

**Benefits:**
- Clear separation of concerns
- Easier to find specific tool implementations
- Better testability
- Reduced merge conflicts

**Implementation:**
1. Create handlers/ directory
2. Move tool methods to appropriate handler files
3. Keep initialization and core logic in server.py
4. Import handlers in server.py
5. Register handlers with MCP

**Estimated Effort:** 4-6 hours

### Option 2: Split by Subsystem

Create separate files for each subsystem:

```
src/core/
├── server.py          # Main server class, initialization (~800 lines)
├── memory_service.py  # Memory operations
├── code_service.py    # Code indexing/search
├── monitoring_service.py  # Health monitoring
└── stats.py           # Statistics tracking
```

**Benefits:**
- Logical grouping
- Can be tested independently

**Drawbacks:**
- More complex than Option 1
- May introduce circular dependencies

### Option 3: Keep As-Is with Better Organization

Add clear section comments and improve navigation:

```python
# ============================================================================
# INITIALIZATION
# ============================================================================

# ============================================================================
# MEMORY OPERATIONS (Lines 100-500)
# ============================================================================

# ============================================================================
# CODE SEARCH OPERATIONS (Lines 500-1000)
# ============================================================================
```

**Benefits:**
- No refactoring needed
- Low risk

**Drawbacks:**
- Doesn't solve the fundamental size issue
- Still hard to navigate

## Recommendation

**Implement Option 1: Extract MCP Tool Handlers**

This provides the best balance of:
- ✅ Clear organization
- ✅ Maintainability
- ✅ Testability
- ✅ Low risk (handlers are independent)
- ✅ Moderate effort

## Implementation Plan

### Phase 1: Preparation
- [ ] Analyze tool methods and group by category
- [ ] Create handlers/ directory structure
- [ ] Write handler base class/protocol if needed

### Phase 2: Extract Handlers (one category at a time)
- [ ] Extract memory handlers
- [ ] Extract code handlers
- [ ] Extract project handlers
- [ ] Extract monitoring handlers
- [ ] Extract git handlers
- [ ] Extract admin handlers

### Phase 3: Cleanup
- [ ] Update imports in server.py
- [ ] Run tests after each extraction
- [ ] Update documentation
- [ ] Add handler documentation

## Target Metrics

**After refactoring:**
- server.py: <1000 lines (core initialization, routing)
- Each handler file: 200-400 lines
- Total files: 7 (1 server + 6 handlers)

## Testing Strategy

- Run full test suite after each handler extraction
- Ensure no functionality changes
- Test all MCP tools still work
- Check performance hasn't regressed

## Risks

**Low risk because:**
- Tool methods are already independent
- No shared state between tools
- Easy to roll back
- Can do incrementally (one handler at a time)

## Next Steps

1. Get approval for Option 1 approach
2. Create REF-013 task in TODO.md
3. Create handlers/ directory
4. Extract first handler (memory_handlers.py)
5. Test and iterate

---

**Status:** Planning complete - ready for implementation
**Estimated Duration:** 4-6 hours
**Complexity:** Medium
**Risk:** Low
