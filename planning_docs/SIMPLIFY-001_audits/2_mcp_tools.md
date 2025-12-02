# MCP Tool Audit - SIMPLIFY-001 Phase 1, Task 1.2

## Summary
- **Total MCP tools:** 45
- **Tools to REMOVE:** 5
- **Tools to KEEP:** 40

## Features Being Removed

This audit covers removal of:
- **Export/Import tools** (Backup/Restore operations)
- **Analytics tools** (Usage pattern tracking and reporting)

NOTE: Graph/Visualization and Auto-Tagging tools are being deferred. Only Export/Import and Analytics tools are being removed in this phase.

---

## Tools to REMOVE

### 1. `export_memories`

**Location:** 
- Tool registration: `src/mcp_server.py` lines 219-233
- Handler: `src/mcp_server.py` lines 1033-1040
- Implementation: `src/core/server.py` lines 1803-1997
- Service: May also be in `src/services/memory_service.py`

**Handler Function:** `export_memories` in `src/core/server.py`

**Calls/Dependencies:**
- `SearchFilters` (src/core/models.py)
- `self.store.list_memories()` - store interface
- `MemoryCategory`, `ContextLevel`, `MemoryScope` - enums
- `Path` operations for file I/O
- `json` module
- `datetime` module

**Description:** 
Exports memories to JSON or Markdown format with filtering capabilities (by category, context level, scope, project, tags, importance, date range). Can write to file or return content as string.

**Reason for Removal:** 
Simplification of MCP surface area - backup/export functionality can be handled by external tools or moved to CLI-only commands.

---

### 2. `import_memories`

**Location:**
- Tool registration: `src/mcp_server.py` lines 235-248
- Handler: `src/mcp_server.py` lines 1042-1050
- Implementation: `src/core/server.py` lines 1999-2150+ (continues beyond)
- Service: May also be in `src/services/memory_service.py`

**Handler Function:** `import_memories` in `src/core/server.py`

**Calls/Dependencies:**
- `Path` operations for file I/O
- `json.loads()` for parsing
- `ValidationError`, `StorageError` exceptions
- `self.store.store_memory()` - to save imported memories
- Conflict resolution logic (skip/overwrite/merge modes)
- `MemoryCategory`, `ContextLevel`, `MemoryScope` - enums

**Description:**
Imports memories from JSON files with conflict resolution (skip, overwrite, or merge modes). Supports both file path and direct content parameters. Auto-detects format from file extension.

**Reason for Removal:**
Simplification of MCP surface area - import/restore functionality can be handled by external tools or moved to CLI-only commands.

---

### 3. `get_usage_statistics`

**Location:**
- Tool registration: `src/mcp_server.py` lines 849-862
- Handler: `src/mcp_server.py` lines 1673-1691
- Implementation: `src/core/server.py` lines 5563-5608
- Service: `src/services/analytics_service.py` (may contain related code)

**Handler Function:** `get_usage_statistics` in `src/core/server.py`

**Calls/Dependencies:**
- `self.pattern_tracker` - UsagePatternTracker instance
- `self.pattern_tracker.get_usage_stats(days=days)` - main call
- `ValidationError` exceptions
- Uses `/analytics/usage_tracker.py` backend (UsagePatternTracker)

**Description:**
Returns overall usage statistics including:
- Total and unique queries
- Average query time and result count
- Code access metrics (total accesses, unique files, unique functions)
- Most active day information

Time window: configurable 1-365 days (default 30).

**Reason for Removal:**
Part of analytics simplification. Usage tracking and reporting can be moved to monitoring dashboards or external analytics systems.

---

### 4. `get_top_queries`

**Location:**
- Tool registration: `src/mcp_server.py` lines 864-883
- Handler: `src/mcp_server.py` lines 1693-1714
- Implementation: `src/core/server.py` lines 5610-5655
- Service: `src/services/analytics_service.py` (may contain related code)

**Handler Function:** `get_top_queries` in `src/core/server.py`

**Calls/Dependencies:**
- `self.pattern_tracker` - UsagePatternTracker instance
- `self.pattern_tracker.get_top_queries(limit=limit, days=days)` - main call
- `ValidationError` exceptions
- Uses `/analytics/usage_tracker.py` backend

**Description:**
Returns most frequently executed queries with statistics:
- Query text
- Execution count
- Average result count
- Average execution time
- Last used timestamp

Parameters: limit (1-100, default 10), days (1-365, default 30).

**Reason for Removal:**
Part of analytics simplification. Query pattern analysis can be handled through external monitoring systems or CLI-only commands.

---

### 5. `get_frequently_accessed_code`

**Location:**
- Tool registration: `src/mcp_server.py` lines 885-904
- Handler: `src/mcp_server.py` lines 1716-1736
- Implementation: `src/core/server.py` lines 5657-5706
- Service: `src/services/analytics_service.py` (may contain related code)

**Handler Function:** `get_frequently_accessed_code` in `src/core/server.py`

**Calls/Dependencies:**
- `self.pattern_tracker` - UsagePatternTracker instance
- `self.pattern_tracker.get_frequently_accessed_code(limit=limit, days=days)` - main call
- `ValidationError` exceptions
- Uses `/analytics/usage_tracker.py` backend

**Description:**
Returns most frequently accessed code files and functions with:
- File/function paths
- Access counts
- Last accessed timestamps
- Language information

Parameters: limit (1-100, default 10), days (1-365, default 30).

**Reason for Removal:**
Part of analytics simplification. Code access patterns can be tracked through other monitoring systems or deferred to future analytics service.

---

## Tools to KEEP

### Memory Management Tools (KEEP)
1. `store_memory` - Core memory storage
2. `retrieve_memories` - Core memory retrieval
3. `list_memories` - Memory browsing/filtering
4. `delete_memory` - Individual memory deletion
5. `delete_memories_by_query` - Batch deletion with filters

### Code Search Tools (KEEP)
6. `search_code` - Semantic code search
7. `suggest_queries` - Query suggestions
8. `index_codebase` - Code indexing
9. `find_similar_code` - Code similarity search
10. `search_all_projects` - Cross-project search

### Cross-Project Tools (KEEP)
11. `opt_in_cross_project` - Project opt-in
12. `opt_out_cross_project` - Project opt-out
13. `list_opted_in_projects` - List opted-in projects

### Git History Tools (KEEP)
14. `search_git_commits` - Commit semantic search
15. `get_file_history` - File history
16. `get_change_frequency` - Change frequency analysis
17. `get_churn_hotspots` - Find frequently changing files
18. `get_recent_changes` - Recent modifications
19. `blame_search` - Git blame integration
20. `get_code_authors` - Author contribution tracking

### Monitoring Tools (KEEP)
21. `get_performance_metrics` - Performance monitoring
22. `get_health_score` - System health
23. `get_active_alerts` - Active alerts
24. `start_dashboard` - Web dashboard server

### Call Graph / Structural Query Tools (KEEP)
25. `find_callers` - Find functions calling target
26. `find_callees` - Find functions called by target
27. `get_call_chain` - Find call paths
28. `find_implementations` - Find interface implementations
29. `find_dependencies` - File dependency analysis
30. `find_dependents` - Reverse dependency analysis

---

## Removal Checklist

### Phase 1: Tool Registration Removal
- [ ] Remove `export_memories` tool registration from `@app.list_tools()` (lines 219-233)
- [ ] Remove `import_memories` tool registration from `@app.list_tools()` (lines 235-248)
- [ ] Remove `get_usage_statistics` tool registration from `@app.list_tools()` (lines 849-862)
- [ ] Remove `get_top_queries` tool registration from `@app.list_tools()` (lines 864-883)
- [ ] Remove `get_frequently_accessed_code` tool registration from `@app.list_tools()` (lines 885-904)

### Phase 2: Handler Function Removal
- [ ] Remove `export_memories` handler from `call_tool()` (lines 1033-1040 in src/mcp_server.py)
- [ ] Remove `import_memories` handler from `call_tool()` (lines 1042-1050 in src/mcp_server.py)
- [ ] Remove `get_usage_statistics` handler from `call_tool()` (lines 1673-1691 in src/mcp_server.py)
- [ ] Remove `get_top_queries` handler from `call_tool()` (lines 1693-1714 in src/mcp_server.py)
- [ ] Remove `get_frequently_accessed_code` handler from `call_tool()` (lines 1716-1736 in src/mcp_server.py)

### Phase 3: Implementation Function Removal
- [ ] Remove `async def export_memories()` from MemoryRAGServer (lines 1803-1997 in src/core/server.py)
- [ ] Remove `async def import_memories()` from MemoryRAGServer (lines 1999-2150+ in src/core/server.py)
- [ ] Remove `async def get_usage_statistics()` from MemoryRAGServer (lines 5563-5608 in src/core/server.py)
- [ ] Remove `async def get_top_queries()` from MemoryRAGServer (lines 5610-5655 in src/core/server.py)
- [ ] Remove `async def get_frequently_accessed_code()` from MemoryRAGServer (lines 5657-5706 in src/core/server.py)

### Phase 4: Service Layer Cleanup
- [ ] Check `src/services/memory_service.py` for export/import methods - remove if found
- [ ] Check `src/services/analytics_service.py` for usage stats methods - remove if found
- [ ] Verify no other MCP tool handlers call removed functions

### Phase 5: Module Cleanup (Deferred)
- [ ] Evaluate whether to keep/remove `src/backup/` module (depends on CLI needs)
- [ ] Evaluate whether to keep/remove `src/analytics/` module (depends on monitoring needs)
- [ ] Note: `src/tagging/` and `src/graph/` modules are NOT being removed in this phase

---

## Implementation Notes

### Dependencies to Verify
- **No other tools currently depend on removed tools** - these are self-contained handlers
- **Pattern tracker (`self.pattern_tracker`)** is initialized elsewhere - removing analytics tools does not break initialization
- **Store interface** remains unchanged - removal does not affect core storage operations

### Testing Impact
- Remove test cases for these 5 tools from test files
- Run full integration test suite to verify no indirect dependencies
- Verify MCP protocol tests still pass with reduced tool set

### Documentation Updates Needed
- Update API documentation to reflect removed tools
- Remove from CLI help/documentation
- Update CHANGELOG with removals

---

## Deferred Items (NOT in this phase)

**Graph/Visualization Tools** - Deferred until Phase 2:
- Call graph building/visualization functions
- Dependency graph visualization
- Related formatters (dot, mermaid, json formatters)

**Auto-Tagging Tools** - Deferred until Phase 2:
- Auto-tagging engine
- Tag suggestion functions
- Related tag management CLI commands

**These will be audited in a separate task (SIMPLIFY-001 Phase 1, Task 1.3)**

---

## References

- MCP Server entry point: `/Users/elliotmilco/Documents/GitHub/claude-memory-server/src/mcp_server.py`
- Core server impl: `/Users/elliotmilco/Documents/GitHub/claude-memory-server/src/core/server.py`
- Memory service: `/Users/elliotmilco/Documents/GitHub/claude-memory-server/src/services/memory_service.py`
- Analytics service: `/Users/elliotmilco/Documents/GitHub/claude-memory-server/src/services/analytics_service.py`
- Backup module: `/Users/elliotmilco/Documents/GitHub/claude-memory-server/src/backup/`
- Analytics module: `/Users/elliotmilco/Documents/GitHub/claude-memory-server/src/analytics/`

