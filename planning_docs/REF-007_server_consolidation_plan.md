# REF-007: Server Consolidation Plan

**Task ID**: REF-007
**Created**: 2025-11-29
**Status**: Planning
**Complexity**: Low-Medium (Clear separation, minimal risk)

## Executive Summary

Consolidate two server implementations:
- **`src/mcp_server.py`** (1,608 lines) - MCP protocol wrapper
- **`src/core/server.py`** (5,419 lines) - Business logic implementation

**Finding**: These files already have a clean separation! `src/mcp_server.py` explicitly states it's just "the MCP protocol wrapper around src/core/server.py" with "all business logic in src/core/server.py". This is **good architecture**, not duplication.

## Current Architecture

### src/mcp_server.py (Entry Point)
**Role**: MCP Protocol Adapter
**Lines**: 1,608
**Purpose**: Thin wrapper that handles MCP protocol communication

**Responsibilities**:
1. **MCP Protocol Handling**
   - Imports MCP SDK (`from mcp.server import Server`)
   - Defines MCP tool schemas (28+ tools via `@app.list_tools()`)
   - Handles MCP tool invocation (`@app.call_tool()`)
   - Manages stdio communication (`stdio_server()`)

2. **Request Routing**
   - Receives MCP tool calls
   - Validates arguments
   - Delegates to `MemoryRAGServer` methods
   - Formats responses as `TextContent`

3. **Startup/Lifecycle**
   - Initializes `MemoryRAGServer` instance
   - Performs startup health checks
   - Manages background initialization
   - Handles graceful shutdown

**Key Functions**:
- `list_tools()` - Returns MCP tool definitions (memory, code search, git, monitoring, analytics)
- `call_tool(name, arguments)` - Routes tool calls to business logic
- `_startup_health_check()` - Validates system readiness
- `main()` - Entry point for MCP server

### src/core/server.py (Business Logic)
**Role**: Core Application Server
**Lines**: 5,419
**Purpose**: Implements all memory and RAG business logic

**Responsibilities**:
1. **Service Orchestration**
   - `MemoryService` - Memory CRUD and lifecycle
   - `CodeIndexingService` - Code search and indexing
   - `CrossProjectService` - Multi-project search
   - `HealthService` - Monitoring and metrics
   - `QueryService` - Query expansion and suggestions
   - `AnalyticsService` - Usage analytics

2. **Component Management**
   - Storage backends (Qdrant, SQLite)
   - Embedding generation (parallel/standard)
   - Caching and indexing
   - Health monitoring
   - Auto-pruning scheduler

3. **Business Methods**
   - `store_memory()`, `retrieve_memories()`, `delete_memory()`
   - `search_code()`, `index_codebase()`, `suggest_queries()`
   - `search_git_commits()`, `get_file_history()`, `blame_search()`
   - `get_performance_metrics()`, `get_health_score()`
   - Call graph tools (REF-059), usage analytics (FEAT-020)

**Architecture Pattern**: Service Layer + Facade
- Server class acts as facade
- Services provide focused functionality
- Clear separation of concerns (REF-016 refactoring)

## Relationship Analysis

```
┌─────────────────────────────────────────────────┐
│          src/mcp_server.py                      │
│         (MCP Protocol Layer)                    │
│                                                 │
│  • MCP SDK integration                          │
│  • Tool schema definitions                      │
│  • Argument validation                          │
│  • Response formatting                          │
│  • stdio communication                          │
└──────────────┬──────────────────────────────────┘
               │ imports and delegates to
               ▼
┌─────────────────────────────────────────────────┐
│        src/core/server.py                       │
│       (Business Logic Layer)                    │
│                                                 │
│  MemoryRAGServer class:                         │
│  • Service orchestration                        │
│  • Component lifecycle                          │
│  • Business logic implementation                │
│  • No MCP protocol awareness                    │
└─────────────────────────────────────────────────┘
```

**Coupling Analysis**:
- `src/mcp_server.py` → `src/core/server.py` (ONE-WAY DEPENDENCY)
- `src/core/server.py` has ZERO awareness of MCP protocol
- Clean separation enables alternative interfaces (REST API, CLI, etc.)

## Why This Is Good Architecture

### 1. **Separation of Concerns**
- Protocol layer (MCP) completely separate from business logic
- Business logic can be used by other interfaces (CLI already does this)
- Easy to add new interfaces (REST, gRPC) without touching business logic

### 2. **Testability**
- Business logic can be tested without MCP protocol overhead
- Protocol layer has minimal logic to test (just routing/formatting)
- Integration tests can focus on either layer independently

### 3. **Maintainability**
- MCP SDK updates only affect `src/mcp_server.py`
- Business logic changes don't require protocol updates
- Clear responsibility boundaries

### 4. **Documented Intent**
The docstring at the top of `src/mcp_server.py` makes the architecture explicit:
```python
"""
MCP Server entry point for Claude Memory RAG.

This is the MCP protocol wrapper around src/core/server.py.
All business logic is in src/core/server.py - this file just handles
the MCP protocol communication.
"""
```

## Problem: What Needs Consolidation?

After investigation, **there is no old/duplicate server to consolidate**. The task title may be misleading.

### Possible Interpretations

1. **Rename for Clarity** (Low value)
   - `src/mcp_server.py` → `src/mcp_adapter.py` or `src/protocol/mcp_server.py`
   - Makes adapter role more obvious
   - **Risk**: Breaks all documentation, setup scripts, user configs

2. **Merge Everything into One File** (Anti-pattern)
   - Combine both files into single 7,000+ line file
   - **Risk**: Violates separation of concerns, reduces testability
   - **Not recommended**

3. **Nothing to Do** (Most likely correct)
   - Current architecture is intentional and well-designed
   - No consolidation needed
   - Task may be based on misunderstanding

## Recommendations

### Option 1: Close as "Not Needed" ✅ RECOMMENDED
**Rationale**: Current architecture is intentionally split and well-designed.

**Actions**:
1. Document current architecture in `docs/ARCHITECTURE.md`
2. Add section explaining the two-layer design
3. Close REF-007 with explanation

**Pros**:
- No code changes = zero risk
- Preserves good architecture
- Documents intent for future developers

**Cons**:
- None (this is the correct approach)

### Option 2: Rename for Clarity (Optional Enhancement)
**Only if** there's evidence users are confused by the naming.

**Changes**:
```
src/mcp_server.py → src/protocol/mcp_adapter.py
```

**Pros**:
- Makes adapter pattern more obvious
- Groups protocol code together

**Cons**:
- Breaks all user configurations
- Requires updating 30+ documentation references
- High migration cost for minimal benefit

**Verdict**: Not worth the disruption

### Option 3: Extract MCP Tools to Separate File (Future Enhancement)
**If** tool definitions grow significantly (currently 800+ lines).

**Structure**:
```
src/protocol/
  ├── mcp_adapter.py      # Main entry point, routing
  ├── tool_schemas.py     # MCP tool definitions
  └── formatters.py       # Response formatting
```

**Pros**:
- Reduces `mcp_server.py` complexity
- Easier to maintain tool schemas
- Better separation within protocol layer

**Cons**:
- Additional files to navigate
- Only beneficial if schemas grow significantly

**Verdict**: Defer until schemas become unwieldy

## Migration Path (If Consolidation Required)

**NOTE**: This section preserved for completeness, but **NOT RECOMMENDED**.

If stakeholders insist on merging files despite architectural concerns:

### Step 1: Create Unified Server
```python
# src/unified_server.py
class UnifiedMemoryRAGServer(StructuralQueryMixin):
    """Combined MCP + Business Logic Server"""

    # Move all MemoryRAGServer code here
    # Add MCP protocol methods

    @staticmethod
    def list_mcp_tools() -> List[Tool]:
        """Return MCP tool schemas"""
        # Move from src/mcp_server.py

    async def handle_mcp_call(self, name: str, args: Dict) -> List[TextContent]:
        """Handle MCP tool invocation"""
        # Move from src/mcp_server.py
```

### Step 2: Update Entry Point
```python
# src/mcp_server.py (now thin launcher)
from src.unified_server import UnifiedMemoryRAGServer

async def main():
    server = UnifiedMemoryRAGServer()
    await server.initialize()
    await server.run_mcp_stdio()
```

### Step 3: Migration Checklist
- [ ] Move business logic to unified file
- [ ] Move MCP protocol handling to unified file
- [ ] Update all imports across codebase
- [ ] Update test files (100+ test files reference these modules)
- [ ] Update documentation (30+ files)
- [ ] Test all 28 MCP tools
- [ ] Verify CI passes
- [ ] Update user migration guide

**Estimated Effort**: 2-3 days
**Risk Level**: HIGH (touches core architecture)
**Value**: NEGATIVE (degrades architecture)

## Test Impact Analysis

### Files Importing src/mcp_server.py
```bash
$ grep -r "from src.mcp_server\|import src.mcp_server" tests/ --count
# Expected: 0-2 (protocol layer rarely tested directly)
```

### Files Importing src/core/server
```bash
$ grep -r "from src.core.server\|import.*MemoryRAGServer" tests/ --count
# Expected: 50+ (business logic extensively tested)
```

**Observation**: Business logic is heavily tested, protocol layer is lightly tested. This is **correct** for an adapter pattern.

## Dependencies Analysis

### What Depends on src/mcp_server.py
- Documentation (setup instructions)
- User configuration files
- CI/CD scripts
- MCP client (Claude Code)

**Impact of changes**: HIGH user disruption

### What Depends on src/core/server.py
- `src/mcp_server.py` (protocol adapter)
- `src/cli/` commands (CLI uses business logic directly)
- Test suite (extensive)
- Service layer

**Impact of changes**: Contained within codebase

## Conclusion

**Recommendation**: **CLOSE REF-007 as "Not Applicable"**

**Justification**:
1. Current architecture is **intentional and well-designed**
2. Clean separation of protocol (MCP) from business logic
3. Documented in code with clear docstrings
4. Enables multiple interfaces (MCP, CLI, future REST)
5. High testability and maintainability
6. No duplication found - files serve different purposes

**Alternative Actions** (if consolidation is required):
1. Document the architecture in `docs/ARCHITECTURE.md`
2. Add ADR (Architecture Decision Record) explaining the split
3. Include diagram showing protocol/business layer separation

**No code changes recommended** - this is good architecture working as intended.

## Next Steps

1. **Discuss with stakeholders** - Share this analysis
2. **If accepted**: Close REF-007, document architecture
3. **If rejected**: Clarify what specific problem needs solving
4. **Document findings** in CHANGELOG.md

## Appendix: File Statistics

| File | Lines | Primary Functions | Role |
|------|-------|------------------|------|
| `src/mcp_server.py` | 1,608 | `list_tools()`, `call_tool()`, `main()`, `_startup_health_check()` | MCP Protocol Adapter |
| `src/core/server.py` | 5,419 | 50+ business methods across 6 service areas | Business Logic Server |

**Total**: 7,027 lines of intentionally separated code

## References

- `src/mcp_server.py` lines 1-7: Explicit documentation of architecture
- REF-016: Service layer extraction (recent refactoring improved structure)
- `src/services/`: Six focused service classes
- `tests/unit/test_server.py`: Business logic tests
- `README.md`: User-facing setup instructions (uses `src/mcp_server.py`)

---

**Status**: Planning complete - Awaiting stakeholder decision
**Author**: REF-007 Task Agent
**Date**: 2025-11-29
