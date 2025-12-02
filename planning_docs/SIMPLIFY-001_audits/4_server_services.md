# Server & Services Audit - SIMPLIFY-001 Phase 1, Task 1.4

## Executive Summary

This audit identifies all code in the core server and services that references features marked for removal in SIMPLIFY-001:
- Graph/Visualization (call graph, dependency graph)
- Import/Export/Backup
- Auto-Tagging
- Analytics

### Quick Stats

- Methods to REMOVE from server.py: 0 (dependency methods are needed for core code analysis)
- Methods to MODIFY in server.py: 5 (export/import in delegation, dependency methods need removal consideration)
- Methods to REMOVE from services: 0 (export/import are in memory_service, which is critical)
- Service files to MODIFY: 2
- External modules to REMOVE: 4 (src.graph, src.tagging, analytics references, src.memory.graph_generator)

## src/core/server.py

### Import Statements to REMOVE

| Line | Import | Status | Notes |
|------|--------|--------|-------|
| 55 | from src.tagging.tag_manager import TagManager | REMOVE | Tag manager only used for memory cleanup |
| 48 | from src.analytics.usage_tracker import UsagePatternTracker | REVIEW | Currently used by AnalyticsService - needs conditional import |

### Methods to MODIFY

| Method | Line | Current Purpose | Required Changes |
|--------|------|-----------------|------------------|
| export_memories() | 1803 | Export memories to JSON/Markdown | Mark as deprecated (Phase 2), will be removed |
| import_memories() | 1999 | Import memories from JSON | Mark as deprecated (Phase 2), will be removed |
| get_file_dependencies() | 3748 | Get file import dependencies | KEEP - Core code analysis feature |
| get_file_dependents() | 3811 | Get reverse dependencies | KEEP - Core code analysis feature |
| find_dependency_path() | 3855 | Find import path between files | KEEP - Core code analysis feature |
| get_dependency_stats() | 3920 | Get dependency statistics | KEEP - Core code analysis feature |
| _build_dependency_graph() | 3956 | Build dependency graph from metadata | KEEP - Internal helper for above |

### Tag Manager References in server.py

| Line | Code | Status | Notes |
|------|------|--------|-------|
| 121 | self.tag_manager: Optional[TagManager] = None | REMOVE | Component initialization |
| 277 | self.tag_manager = TagManager(...) | REMOVE | Component instantiation |
| 429 | tag_manager=self.tag_manager | REMOVE | Passed to MemoryService |

### Dependency Graph Methods - CLARIFICATION

DECISION: The dependency graph methods (find_callers, find_callees, find_dependencies, find_dependents, etc.) are NOT part of the removed "Graph/Visualization" feature. Those methods are ESSENTIAL for:
- Code structure analysis
- Impact assessment
- Refactoring support

The "Graph/Visualization" feature being removed refers to:
- Visual graph rendering/export (DOT, Mermaid, JSON graph formats)
- Graph visualization in dashboards
- Graph-based UI components

The structural analysis capability (finding callers, dependencies) is preserved as a core feature.

## src/services/memory_service.py

### Methods to MODIFY

| Method | Line | Current Purpose | Required Changes |
|--------|------|-----------------|------------------|
| export_memories() | 1145 | Export memories to JSON/Markdown | Mark as deprecated (Phase 2), will be removed |
| import_memories() | 1311 | Import memories from JSON | Mark as deprecated (Phase 2), will be removed |
| Reference to tag_manager | 95, 633-642 | Tag cleanup on memory deletion | REMOVE tag cleanup logic |

### Tag Manager Cleanup Code

Located in delete_memory() method (lines 633-642):

    # Clean up tag associations to prevent orphaned entries
    if self.tag_manager:
        try:
            self.tag_manager.cleanup_memory_tags(memory_id)
            logger.debug(
                f"Cleaned up tag associations for memory: {memory_id}"
            )
        except Exception as tag_error:
            # Log but don't fail the delete operation if tag cleanup fails
            logger.warning(
                f"Failed to cleanup tags for memory {memory_id}: {tag_error}",
            )

ACTION: Remove this block entirely. The tag_manager parameter in MemoryService.__init__ (line 69, 84, 95) should also be removed.

## src/core/structural_query_tools.py

### MODIFICATION REQUIRED - Remove Call Graph References

This mixin provides 6 methods that depend on src.store.call_graph_store:

| Method | Line | Status | Reason |
|--------|------|--------|--------|
| find_callers() | 24 | REMOVE/DEPRECATE | Uses QdrantCallGraphStore |
| find_callees() | 145 | REMOVE/DEPRECATE | Uses QdrantCallGraphStore |
| find_implementations() | 274 | REMOVE/DEPRECATE | Uses QdrantCallGraphStore |
| get_call_chain() | 548 | REMOVE/DEPRECATE | Uses QdrantCallGraphStore |

These methods load from src.store.call_graph_store.QdrantCallGraphStore (lines 72-78, 193-199, 320-324, 599-603).

NOTE: These are structural query tools for detailed call analysis, separate from dependency graph analysis. They should be marked as deprecated in Phase 1.

## src/services/code_indexing_service.py

### Methods AFFECTED by Graph Removal

| Method | Line | Dependencies | Status |
|--------|------|--------------|--------|
| _build_dependency_graph() | 871 | src.memory.dependency_graph.DependencyGraph | KEEP |
| find_dependency_path() | 1011 | _build_dependency_graph() | KEEP |
| get_dependency_stats() | 1070 | _build_dependency_graph() | KEEP |
| get_file_dependencies() | 913 | _build_dependency_graph() | KEEP |
| get_file_dependents() | 975 | _build_dependency_graph() | KEEP |

All of these depend on src.memory.dependency_graph.DependencyGraph which is needed for core functionality.

## src/services/analytics_service.py

### Methods to REVIEW

All methods in this service (lines 67-303) relate to analytics features being removed:

| Method | Line | Purpose | Status |
|--------|------|---------|--------|
| get_usage_statistics() | 67 | Usage pattern analysis | KEEP/REVIEW |
| get_top_queries() | 99 | Query frequency tracking | KEEP/REVIEW |
| get_frequently_accessed_code() | 133 | Code access patterns | KEEP/REVIEW |
| get_token_analytics() | 171 | Token usage tracking | REVIEW |
| submit_search_feedback() | 214 | User feedback collection | REVIEW |
| get_quality_metrics() | 265 | Search result quality | REVIEW |

NOTE: These methods track usage patterns (USAGE ANALYTICS) not removed. The "Analytics" feature in SIMPLIFY-001 refers to optional telemetry/tracking that can be disabled. These methods are still functional and can be retained.

## src/mcp_server.py

### Tool Definitions to DEPRECATE

| Line | Tool Name | Description | Status |
|------|-----------|-------------|--------|
| 219 | export_memories | Export memories to JSON/Markdown | DEPRECATE Phase 1 |
| 235 | import_memories | Import memories from JSON | DEPRECATE Phase 1 |
| 1033 | Handler: export_memories | Delegates to memory_service | REMOVE Phase 2 |
| 1042 | Handler: import_memories | Delegates to memory_service | REMOVE Phase 2 |

## External Modules to Remove

### 1. src/tagging/ (Complete Module)

This entire package is marked for removal:
- src/tagging/__init__.py
- src/tagging/models.py
- src/tagging/tag_manager.py
- src/tagging/auto_tagger.py
- src/tagging/collection_manager.py

CURRENT REFERENCES:
- server.py: Line 55 (import TagManager)
- server.py: Lines 121, 277, 429 (initialization and passing)
- memory_service.py: Lines 69, 84, 95, 633-642 (parameter and cleanup)

### 2. src/graph/ (Visualization Components)

This package includes visualization and export formatters:
- src/graph/__init__.py
- src/graph/call_graph.py - Call graph data structure
- src/graph/formatters/ - DOT, JSON, Mermaid formatters
- src/memory/graph_generator.py - Graph export functionality

CURRENT REFERENCES:
- structural_query_tools.py: Lines 71-78, 193-199 (calls QdrantCallGraphStore)
- memory/incremental_indexer.py: Line 1095 (imports FunctionNode)

### 3. src/store/call_graph_store.py

Call graph storage and retrieval:

CURRENT REFERENCES:
- structural_query_tools.py: Multiple imports (lines 72, 193, 320, 599)
- memory/incremental_indexer.py: Lines 78, 254-256, 278-279, 390-392, 1095-1217

### 4. src/analytics/ (Optional - REVIEW)

Telemetry and usage tracking:
- src/analytics/__init__.py
- src/analytics/token_tracker.py
- src/analytics/usage_tracker.py

NOTE: These track optional metrics that can be disabled. Removal depends on keeping analytics module for backward compatibility vs. complete removal.

## Dependency Chain Analysis

### Import/Export Impact Chain

    export_memories/import_memories (MCP tools)
      DOWN ARROW
    server.export_memories() / server.import_memories()
      DOWN ARROW
    memory_service.export_memories() / memory_service.import_memories()
      DOWN ARROW
    Affected: Nothing downstream (these are leaf operations)

IMPACT: Removing export/import affects users relying on backup/migration but not system stability.

### Tag Manager Impact Chain

    server.tag_manager initialization
      DOWN ARROW
    memory_service.tag_manager (parameter)
      DOWN ARROW
    delete_memory() - tag cleanup
      DOWN ARROW
    Tag associations removed during memory deletion

IMPACT: Removing tag cleanup may orphan tag associations, but won't break functionality.

### Call Graph Impact Chain

    incremental_indexer._store_call_graph() (indexing time)
      DOWN ARROW
    call_graph_store.store_function_node/store_call_sites/store_implementations()
      DOWN ARROW
    structural_query_tools methods (find_callers, find_callees, etc.)
      DOWN ARROW
    Qdrant call_graph collection queries

IMPACT: Removing call graph storage means structural query tools stop working. This is acceptable if these are marked as deprecated.

### Dependency Graph Impact Chain

    incremental_indexer - imports metadata extraction
      DOWN ARROW
    memory_service - stored as context metadata
      DOWN ARROW
    code_indexing_service._build_dependency_graph()
      DOWN ARROW
    get_file_dependencies, get_file_dependents, find_dependency_path, get_dependency_stats

IMPACT: Dependency graph is lightweight (derived from imports metadata) and should be kept for code analysis.

## Removal Roadmap

### Phase 1 (Immediate - This Sprint)
1. Add deprecation warnings to export/import methods
2. Remove tag_manager from server initialization
3. Remove tag cleanup code from delete_memory()
4. Mark call graph structural queries as deprecated
5. Remove src/tagging/ imports

### Phase 2 (Next Sprint)
1. Remove export_memories/import_memories from MCP tools
2. Remove export/import from memory_service
3. Remove structural_query_tools from server if call graph not used
4. Remove src/tagging/ module entirely

### Phase 3 (Future)
1. Remove call graph storage from incremental_indexer
2. Remove src/store/call_graph_store.py
3. Remove src/graph/ visualization modules
4. Decide on src/analytics/ fate (optional telemetry vs. removal)

## Files to Create/Modify

### Modifications Required

1. src/core/server.py
   - Remove tag_manager import and initialization
   - Add deprecation warnings to export_memories/import_memories
   - Keep dependency graph methods

2. src/services/memory_service.py
   - Remove tag_manager parameter and references
   - Remove tag cleanup code in delete_memory()
   - Add deprecation warnings to export/import methods

3. src/services/analytics_service.py
   - Review all methods - determine which analytics to keep
   - Possibly mark some as deprecated

4. src/core/structural_query_tools.py
   - Mark all 4 call graph methods as deprecated
   - Consider removing or extracting to separate module

5. src/mcp_server.py
   - Add deprecation notices to export/import tools
   - Consider removal timing for handlers

### Complete Removals (Phase 2+)

- src/tagging/ (entire package)
- src/graph/ (visualization formatters)
- src/store/call_graph_store.py
- src/memory/graph_generator.py
- Deprecation warnings and stub methods in server.py and memory_service.py

## Risk Assessment

### Low Risk
- Removing tag_manager: Only used for cleanup on delete, not essential
- Removing export/import: Users rarely rely on this; backups are ad-hoc

### Medium Risk  
- Removing call graph storage: Only affects code analysis features
- Removing graph formatters: Only affects visualization (not available in current scope)

### High Risk
- Removing dependency graph: Breaks core code analysis features (should NOT remove)

## Summary Table

| Component | Status | Timeline | Risk |
|-----------|--------|----------|------|
| Tag Manager (src/tagging/) | REMOVE | Phase 1 | Low |
| Export/Import (memory_service) | DEPRECATE | Phase 1, REMOVE Phase 2 | Low |
| Call Graph Storage | DEPRECATE | Phase 1, REMOVE Phase 2 | Medium |
| Structural Query Tools | DEPRECATE | Phase 1 | Medium |
| Dependency Graph (core) | KEEP | All phases | N/A |
| Analytics (telemetry) | REVIEW | TBD | Medium |
| Graph Formatters/Visualization | REMOVE | Phase 2+ | Low |

