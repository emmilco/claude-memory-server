# TODO

## 🚨 CRITICAL BUGS FOUND IN E2E TESTING (2025-11-20)

### BUG-015: Health Check False Negative for Qdrant ⚠️ HIGH
**Component:** `src/cli/health_command.py:143`
**Issue:** Health check reports Qdrant as unreachable even when functional
**Root Cause:** Using wrong endpoint `/health` instead of `/`
**Impact:** Misleading error messages, conflicts with validate-install
**Fix:** Change endpoint check from `/health` to `/` with JSON validation

### BUG-016: list_memories Returns Incorrect Total Count ⚠️ MEDIUM
**Component:** Memory management API
**Issue:** `list_memories()` returns `total: 0` when memories exist in results array
**Impact:** Breaks pagination, incorrect analytics
**Fix:** Update method to properly count and return total

### BUG-017: Documentation Claims Incorrect API Parameter Names ⚠️ MEDIUM
**Component:** Documentation (README.md, API.md)
**Issue:** Examples use wrong parameter names:
  - `index_codebase(path=...)` should be `directory_path=...`
  - `opt_in_project()` should be `opt_in_cross_project()`
  - `get_stats()` should be `get_status()`
**Impact:** Documentation examples fail when copy-pasted
**Fix:** Audit and update all documentation examples

### BUG-018: Memory Retrieval Not Finding Recently Stored Memories ⚠️ HIGH
**Component:** Semantic search / memory retrieval
**Issue:** Memories stored via `store_memory()` not immediately retrievable via `retrieve_memories()`
**Impact:** Core functionality appears broken, poor user experience
**Investigation Required:** Check embedding timing, vector store indexing delay, similarity threshold

### BUG-019: Docker Container Shows "Unhealthy" Despite Working ⚠️ LOW
**Component:** `docker-compose.yml` healthcheck
**Issue:** `docker ps` shows Qdrant as "(unhealthy)" even though fully functional
**Impact:** User confusion, unnecessary container restarts
**Fix:** Update Docker healthcheck configuration

### BUG-020: Inconsistent Return Value Structures ⚠️ MEDIUM
**Component:** API design consistency
**Issue:** Different methods use different success indicators:
  - `delete_memory`: `{"status": "success"}`
  - Expected by tests: `{"success": true}`
**Impact:** Confusing API, error-prone client code
**Recommendation:** Standardize on consistent return structure

### BUG-021: PHP Parser Initialization Warning ⚠️ LOW
**Component:** `src/memory/python_parser.py`
**Issue:** Warning: "Failed to initialize php parser: module 'tree_sitter_php' has no attribute 'language'"
**Impact:** PHP files cannot be indexed, log noise
**Investigation Required:** Check tree-sitter-php installation and API version

### BUG-022: Code Indexer Extracts Zero Semantic Units ⚠️ HIGH
**Component:** Code indexing / parsing
**Issue:** `index_codebase()` successfully indexes 11 files but extracts 0 semantic units
**Impact:** Code search returns no meaningful results, semantic analysis broken
**Expected:** Should extract functions, classes, methods from Python files
**Investigation Required:** Check parser configuration, semantic unit extraction logic

**Full E2E Test Report:** See `E2E_TEST_REPORT.md` for detailed findings

---

## ID System
Each item has a unique ID for tracking and association with planning documents in `planning_docs/`.
Format: `{TYPE}-{NUMBER}` where TYPE = FEAT|BUG|TEST|DOC|PERF|REF|UX

## Priority System

**Prioritization Rules:**
1. Complete partially finished initiatives before starting new ones
2. Prioritize items that have greater user impact over items that have less impact

## Current Sprint

### 🔴 Critical Bugs (Blocking)

**These bugs completely break core functionality and must be fixed immediately**

- [x] **BUG-012**: MemoryCategory.CODE attribute missing ✅ **FIXED**
  - **Error:** `type object 'MemoryCategory' has no attribute 'CODE'`
  - **Impact:** Code indexing completely broken - 91% of files fail to index (10/11 failures)
  - **Location:** `src/memory/incremental_indexer.py:884` uses `MemoryCategory.CODE.value`
  - **Root Cause:** MemoryCategory enum only has: PREFERENCE, FACT, EVENT, WORKFLOW, CONTEXT
  - **Fix:** Added CODE = "code" to MemoryCategory enum in `src/core/models.py:26`
  - **Result:** All files now index successfully (11/11), 867 semantic units extracted

- [x] **BUG-013**: Parallel embeddings PyTorch model loading failure ✅ **FIXED**
  - **Error:** "Cannot copy out of meta tensor; no data! Please use torch.nn.Module.to_empty() instead of torch.nn.Module.to()"
  - **Impact:** Parallel embedding generation fails, blocks indexing with parallel mode enabled
  - **Location:** `src/embeddings/parallel_generator.py:41` - `model.to("cpu")`
  - **Root Cause:** Worker processes can't use `.to()` on models loaded from main process
  - **Fix:** Changed to `SentenceTransformer(model_name, device="cpu")` instead of `.to("cpu")`
  - **Result:** Parallel embeddings work with 9.7x speedup (37.17 files/sec vs 3.82)

- [x] **BUG-014**: cache_dir_expanded attribute missing from ServerConfig ✅ **FIXED**
  - **Error:** `'ServerConfig' object has no attribute 'cache_dir_expanded'`
  - **Impact:** Health check command crashes when checking cache statistics
  - **Location:** `src/cli/health_command.py:371`
  - **Root Cause:** Code references non-existent attribute; cache is a file, not a directory
  - **Fix:** Changed to use `embedding_cache_path_expanded` and check file size directly
  - **Result:** Health command works perfectly, shows all system statistics

### 🟡 Tier 2: Core Functionality Extensions

**These extend core capabilities with new features (nice-to-have)**

#### Code Intelligence Enhancements

- [x] **FEAT-046**: Indexed Content Visibility ✅ **COMPLETE**
  - [x] Implement `get_indexed_files` MCP tool
  - [x] Implement `list_indexed_units` MCP tool (functions, classes, etc.)
  - [x] Filter by project, language, file_pattern, unit_type
  - [x] Show indexing metadata: last indexed, unit count
  - [x] Pagination with auto-capped limits (1-500)
  - [x] Tests: 17 tests, all passing
  - **Impact:** Transparency into what's indexed, debugging aid
  - **Use case:** "What files are indexed in this project?" or "Show all Python functions indexed"
  - **Enhances:** `get_status` (which only shows counts)

- [ ] **FEAT-049**: Intelligent Code Importance Scoring (~1-2 weeks) 🔥
  - [ ] **Current State:** All code units have fixed importance=0.7, making importance meaningless for discrimination
  - [ ] **Problem:** In medium-to-large projects (10,000+ code units), importance scores provide zero discrimination between critical authentication functions and trivial helpers
  - [ ] **Proposed Solution:** Implement dynamic importance calculation based on:
    - **Complexity metrics:** Cyclomatic complexity, line count, nesting depth, parameter count
    - **Usage patterns:** Call frequency, number of callers (centrality in call graph), public vs private API
    - **Code characteristics:** Security keywords (auth, crypto, permission), error handling, documentation quality, decorators/annotations
    - **File-level signals:** Core vs utility modules, proximity to entry points, git change frequency, bug fix history
  - [ ] **Scoring Algorithm:**
    - Base score calculation from complexity (0.3-0.7 range)
    - Usage boost (+0.0 to +0.2 based on call graph centrality)
    - Security/critical keyword boost (+0.1 to +0.2)
    - Normalization to 0.0-1.0 range
  - [ ] **Implementation:**
    - [ ] Add complexity analyzer to code parser
    - [ ] Build lightweight call graph during indexing
    - [ ] Implement scoring heuristics in incremental_indexer.py
    - [ ] Add configuration options for scoring weights
    - [ ] Update tests to validate scoring ranges
  - [ ] **Validation:**
    - [ ] Verify distribution (not all 0.7)
    - [ ] Spot-check critical functions have higher scores
    - [ ] Ensure performance impact is acceptable (<10% indexing slowdown)
  - **Impact:** Make importance scores actually useful for retrieval ranking, filtering, and prioritization
  - **Use case:** "Show me the most important functions in this codebase" should return core logic, not utilities
  - **Enhances:** retrieve_memories, search_code, list_memories (all support min_importance filtering)

- [ ] **FEAT-048**: Dependency Graph Visualization (~2-3 days) 🔥
  - [ ] Implement `get_dependency_graph` MCP tool
  - [ ] Export formats: DOT (Graphviz), JSON (D3.js), Mermaid
  - [ ] Filter by depth, file pattern, language
  - [ ] Highlight circular dependencies
  - [ ] Include node metadata (file size, unit count, last modified)
  - [ ] Tests: graph generation, format validation, circular detection
  - **Impact:** Architecture visualization and understanding
  - **Use case:** "Export dependency graph for visualization in Graphviz"
  - **Enhances:** Existing dependency tools (get_file_dependencies, etc.)

### 🟢 Tier 3: UX Improvements & Performance Optimizations

**User experience and performance improvements**

#### Error Handling & Graceful Degradation

- [x] **UX-012**: Graceful degradation ✅ **COMPLETE**
  - [x] Auto-fallback: Qdrant unavailable → SQLite
  - [x] Auto-fallback: Rust unavailable → Python parser
  - [x] Warn user about performance implications
  - [x] Option to upgrade later
  - **Implementation:** Config flags `allow_qdrant_fallback`, `allow_rust_fallback`, `warn_on_degradation`
  - **Files:** `src/store/factory.py`, `src/memory/incremental_indexer.py`, `src/core/degradation_warnings.py`
  - **Tests:** 15 tests in `test_graceful_degradation.py`, all passing
  - **Impact:** Better first-run experience, no hard failures for missing dependencies

#### Health & Monitoring

- [ ] **UX-032**: Health Check Improvements (~2 days) 🔥🔥
  - [ ] **Confirm overall feature design with user before proceeding**
  - [ ] Extend existing health check command
  - [ ] Add: Qdrant latency monitoring (warn if >20ms)
  - [ ] Add: Cache hit rate display (warn if <70%)
  - [ ] Add: Token savings this week
  - [ ] Add: Stale project detection (not indexed in 30+ days)
  - [ ] Proactive recommendations: "Consider upgrading to Qdrant"
  - [ ] Show indexed projects count and size
  - **Impact:** Proactive issue detection, optimization guidance

#### Performance Optimizations

- [ ] **PERF-002**: GPU acceleration (~1-2 weeks)
  - [ ] Use CUDA for embedding model
  - [ ] Target: 50-100x speedup
  - **Impact:** Massive speedup (requires GPU hardware)

---

### 🌐 Tier 4: Language Support Extensions

- [ ] **FEAT-007**: Add support for Ruby (~3 days)
  - [ ] tree-sitter-ruby integration
  - [ ] Method, class, module extraction

- [x] **FEAT-008**: Add support for PHP ✅ **COMPLETE**
  - [x] tree-sitter-php integration
  - [x] Function, class, trait extraction

- [x] **FEAT-009**: Add support for Swift ✅ **COMPLETE**
  - [x] tree-sitter-swift integration
  - [x] Function, struct, class extraction

- [x] **FEAT-010**: Add support for Kotlin ✅ **COMPLETE**
  - [x] tree-sitter-kotlin integration
  - [x] Function, class, object extraction

### 🚀 Tier 5: Advanced/Future Features

- [ ] **FEAT-016**: Auto-indexing
  - [ ] Automatically index on project open
  - [ ] Background indexing for large projects

- [ ] **FEAT-017**: Multi-repository support
  - [ ] Index across multiple repositories
  - [ ] Cross-repo code search

- [ ] **FEAT-018**: Query DSL
  - [ ] Advanced filters (by file pattern, date, author, etc.)
  - [ ] Complex query expressions

- [ ] **FEAT-014**: Semantic refactoring
  - [ ] Find all usages semantically
  - [ ] Suggest refactoring opportunities

- [ ] **FEAT-015**: Code review features
  - [ ] LLM-powered suggestions based on patterns
  - [ ] Identify code smells

- [x] **UX-026**: Web dashboard MVP ✅ **COMPLETE**
  - [x] Basic web UI with statistics
  - [x] Project breakdown display
  - [x] Category and lifecycle charts
  - [x] Recent activity view
  - **Status**: MVP complete, see enhancements below

#### Web Dashboard Enhancements (Post-MVP)

**Phase 1: Core Usability (~20-24 hours, 1-2 weeks)**

**Progress**: 2/15 features complete (13%). See `planning_docs/UX-034-048_dashboard_enhancements_progress.md` for comprehensive implementation guide for remaining 13 features.

- [x] **UX-034**: Dashboard Search and Filter Panel ✅ **COMPLETE** (~3 hours)
  - [x] Global search bar for memories (with 300ms debouncing)
  - [x] Filter dropdowns: project, category, date range, lifecycle state
  - [x] Real-time filtering of displayed data (client-side)
  - [x] URL parameters for shareable filtered views
  - [x] Empty state messaging and filter badge
  - [x] Responsive mobile design
  - **Impact**: Users can find specific memories/projects quickly
  - **Implementation**: Client-side filtering, ~300 lines of code added
  - **Reference**: planning_docs/UX-034_search_filter_panel.md

- [x] **UX-035**: Memory Detail Modal ✅ **COMPLETE** (~1 hour)
  - [x] Click any memory to see full details
  - [x] Full content with syntax highlighting for code
  - [x] Display all metadata: tags, importance, provenance, timestamps
  - [x] Modal with smooth animations (fadeIn, slideUp)
  - [x] Escape key support and click-outside-to-close
  - [x] Responsive mobile design
  - **Impact**: Transform from view-only to interactive tool
  - **Implementation**: Modal overlay with basic syntax highlighting (~350 lines)
  - **Reference**: planning_docs/UX-034-048_dashboard_enhancements_progress.md

- [ ] **UX-036**: Health Dashboard Widget (~4-6 hours)
  - [ ] Health score gauge (0-100) with color coding
  - [ ] Active alerts count with severity badges
  - [ ] Performance metrics: search latency, cache hit rate
  - [ ] Link to full health command output
  - **Impact**: Proactive monitoring, surface issues immediately
  - **Data Source**: Existing get_health_score() and get_active_alerts() MCP tools
  - **Reference**: planning_docs/UX-026_dashboard_enhancement_analysis.md

- [ ] **UX-037**: Interactive Time Range Selector (~3-4 hours)
  - [ ] Preset buttons: Last Hour, Today, Last 7 Days, Last 30 Days, All Time
  - [ ] Custom date picker
  - [ ] Update all charts/activity based on selection
  - [ ] Persist selection in localStorage
  - **Impact**: Understand trends and historical patterns
  - **Reference**: planning_docs/UX-026_dashboard_enhancement_analysis.md

**Phase 2: Advanced Analytics (~32-40 hours, 1-2 weeks)**

- [ ] **UX-038**: Trend Charts and Sparklines (~8-10 hours)
  - [ ] Line charts for memory count over time (daily/weekly)
  - [ ] Search volume heatmap (by hour/day)
  - [ ] Performance trend (latency over time)
  - [ ] Use Chart.js or ApexCharts (lightweight library)
  - **Impact**: Understand usage patterns and identify anomalies
  - **Backend**: Add time-series aggregation endpoints
  - **Reference**: planning_docs/UX-026_dashboard_enhancement_analysis.md

- [ ] **UX-039**: Memory Relationships Graph Viewer (~10-12 hours)
  - [ ] Interactive graph using D3.js or vis.js
  - [ ] Click memory to see relationships (SUPERSEDES, CONTRADICTS, RELATED_TO)
  - [ ] Color-coded by relationship type
  - [ ] Zoom/pan controls
  - **Impact**: Understand knowledge structure, discover related content
  - **Data Source**: Existing MemoryRelationship model in database
  - **Reference**: planning_docs/UX-026_dashboard_enhancement_analysis.md

- [ ] **UX-040**: Project Comparison View (~6-8 hours)
  - [ ] Select 2-4 projects to compare side-by-side
  - [ ] Bar charts: memory count, file count, function count
  - [ ] Category distribution comparison
  - [ ] Performance metrics comparison (index time, search latency)
  - **Impact**: Identify outliers, understand relative project complexity
  - **Reference**: planning_docs/UX-026_dashboard_enhancement_analysis.md

- [ ] **UX-041**: Top Insights and Recommendations (~8-10 hours)
  - [ ] Automatic insight detection:
    - "Project X hasn't been indexed in 45 days"
    - "Search latency increased 40% this week"
    - "15 memories marked 'not helpful' - consider cleanup"
    - "Cache hit rate below 70% - consider increasing cache size"
  - [ ] Priority/severity levels
  - [ ] One-click actions ("Index Now", "View Memories", "Adjust Settings")
  - **Impact**: Proactive guidance to improve memory system usage
  - **Backend**: Add insight detection logic
  - **Reference**: planning_docs/UX-026_dashboard_enhancement_analysis.md

**Phase 3: Productivity Features (~16-22 hours, 1 week)**

- [ ] **UX-042**: Quick Actions Toolbar (~6-8 hours)
  - [ ] Buttons for: Index Project, Create Memory, Export Data, Run Health Check
  - [ ] Forms with validation
  - [ ] Status feedback (loading, success, error)
  - **Impact**: Avoid switching to CLI for frequent tasks
  - **Reference**: planning_docs/UX-026_dashboard_enhancement_analysis.md

- [ ] **UX-043**: Export and Reporting (~6-8 hours)
  - [ ] Export formats: JSON, CSV, Markdown, PDF (summary report)
  - [ ] Filters: by project, date range, category
  - [ ] Optional: Scheduled reports (daily/weekly email)
  - **Impact**: Share insights, backup data, integration with other tools
  - **Data Source**: Existing export_memories() MCP tool
  - **Reference**: planning_docs/UX-026_dashboard_enhancement_analysis.md

**Phase 4: UX Polish (~12-17 hours, 3-5 days)**

- [ ] **UX-044**: Dark Mode Toggle (~2-3 hours)
  - [ ] Alternative dark color scheme
  - [ ] Toggle switch in header
  - [ ] CSS variables for theming
  - [ ] Persist preference in localStorage
  - **Impact**: Reduce eye strain, user preference
  - **Reference**: planning_docs/UX-026_dashboard_enhancement_analysis.md

- [ ] **UX-045**: Keyboard Shortcuts (~2-3 hours)
  - [ ] `/` - Focus search
  - [ ] `n` - New memory
  - [ ] `h` - Health check
  - [ ] `?` - Show help modal
  - [ ] `Esc` - Close modals
  - **Impact**: Faster navigation for power users
  - **Reference**: planning_docs/UX-026_dashboard_enhancement_analysis.md

- [ ] **UX-046**: Responsive Tooltips and Help (~3-4 hours)
  - [ ] Tooltip library (tippy.js or similar)
  - [ ] Help icon (?) next to complex features
  - [ ] Onboarding tour for first-time users
  - **Impact**: Improve discoverability, reduce learning curve
  - **Reference**: planning_docs/UX-026_dashboard_enhancement_analysis.md

- [ ] **UX-047**: Loading States and Skeleton Screens (~2-3 hours)
  - [ ] Skeleton screens instead of "Loading..."
  - [ ] Smooth transitions
  - [ ] Progress indicators for long operations
  - **Impact**: Perceived performance improvement
  - **Reference**: planning_docs/UX-026_dashboard_enhancement_analysis.md

- [ ] **UX-048**: Error Handling and Retry (~3-4 hours)
  - [ ] Toast notifications for errors
  - [ ] Retry button
  - [ ] Detailed error messages (from backend)
  - [ ] Offline detection
  - **Impact**: Better UX when things go wrong
  - **Reference**: planning_docs/UX-026_dashboard_enhancement_analysis.md

- [ ] **UX-027**: VS Code extension (~2-3 weeks)
  - [ ] Inline code search results
  - [ ] Memory panel
  - [ ] Quick indexing actions
  - [ ] Status bar integration

- [ ] **UX-028**: Telemetry & analytics (opt-in) (~1 week)
  - [ ] Usage patterns (opt-in, privacy-preserving)
  - [ ] Error frequency tracking
  - [ ] Performance metrics
  - [ ] Feature adoption rates
  - [ ] Helps identify UX issues in the wild

### 🔨 Tier 6: Refactoring & Tech Debt

- [x] **REF-010**: Remove SQLite fallback, require Qdrant ✅ **COMPLETE** (~1 day) 🔥
  - **Rationale:** SQLite mode provides poor UX for code search (keyword-only, no semantic similarity, misleading 0.700 scores). Empirical evaluation (EVAL-001) showed it adds complexity without value.
  - [x] Remove SQLite fallback logic from `src/store/__init__.py` and `src/store/factory.py`
  - [x] Remove `allow_qdrant_fallback` config option from ServerConfig (deprecated configs ignored for backward compatibility)
  - [x] Update `create_memory_store()` and `create_store()` to fail fast if Qdrant unavailable
  - [x] Update error messages with actionable setup instructions
  - [x] Keep `src/store/sqlite_store.py` for backward compatibility (deprecated, shows warning)
  - [x] Update documentation to require Qdrant for code search (README.md)
  - [x] Add `validate-setup` CLI command to check Qdrant availability
  - [x] Update tests: `test_graceful_degradation.py`, `test_config.py`, `test_actionable_errors.py`
  - [x] Add clear error in `QdrantConnectionError` with setup instructions
  - **Benefits:** Simpler architecture, clear expectations, better error messages, no misleading degraded mode
  - **Implemented:** 2025-11-19

- [ ] **REF-007**: Consolidate two server implementations
  - Merge old mcp_server.py with new src/core/
  - Unified architecture

- [ ] **REF-008**: Remove deprecated API usage
  - Update to latest Qdrant APIs
  - Update to latest MCP SDK

- [x] **REF-002**: Add Structured Logging ✅ **COMPLETE** (~1 hour)
  - Created `src/logging/structured_logger.py` with JSON formatter
  - 19 comprehensive tests, all passing
  - Backward compatible with existing logging patterns

- [x] **REF-003**: Split Validation Module ✅ **COMPLETE** (~1.5 hours)
  - Split monolithic validation.py (532 lines) into separate modules
  - Prevents circular import issues by separating concerns
  - Maintains backward compatibility through __init__.py exports

- [x] **REF-005**: Update to Pydantic v2 ConfigDict style ✅ **COMPLETE**
  - Already using model_config = ConfigDict() throughout codebase

- [x] **REF-006**: Update Qdrant search() to query_points() ✅ **COMPLETE**
  - Replaced deprecated API for future Qdrant compatibility
  - Enhanced error handling for payload parsing

### 📚 Tier 7: Documentation & Monitoring

- [ ] **PERF-006**: Performance Regression Detection (~3-5 days)
  - [ ] **Confirm overall feature design with user before proceeding**
  - [ ] Time-series metrics: search latency, index time, cache hit rate
  - [ ] Baseline establishment (rolling 30-day average)
  - [ ] Anomaly detection (alert if >40% degradation)
  - [ ] Alert examples: "Search latency increased 40% this week"
  - [ ] Recommendations: "Enable quantization" or "Collection too large"
  - [ ] CLI command: `python -m src.cli perf-report`
  - **Impact:** Maintain quality at scale, early warning system

- [x] **DOC-004**: Update README with code search examples ✅ **COMPLETE**
- [ ] **DOC-005**: Add performance tuning guide for large codebases
- [x] **DOC-006**: Create troubleshooting guide for common parser issues ✅ **COMPLETE**
  - Added comprehensive "Code Parsing Issues" section to TROUBLESHOOTING.md
  - Covers: syntax errors, encoding, performance, memory, unsupported languages, skipped files
  - 6 subsections with practical solutions and code examples
- [ ] **DOC-007**: Document best practices for project organization

- [ ] **DOC-001**: Interactive documentation
  - [ ] Live examples in docs
  - [ ] Playground for testing queries

- [ ] **DOC-002**: Migration guides
  - [ ] From other code search tools
  - [ ] Database migration utilities

- [ ] **DOC-003**: Video tutorials
  - [ ] Setup walkthrough
  - [ ] Feature demonstrations
  - [ ] Best practices guide

- [ ] **FEAT-019**: IDE Integration
  - [ ] VS Code extension for instant code search
  - [ ] IntelliJ plugin
  - [ ] Vim/Neovim integration

- [ ] **FEAT-020**: Usage patterns tracking
  - [ ] Track most searched queries
  - [ ] Identify frequently accessed code
  - [ ] User behavior analytics

- [ ] **FEAT-021**: Memory lifecycle management
  - [ ] Auto-expire old memories
  - [ ] Memory importance decay
  - [ ] Storage optimization

- [ ] **FEAT-022**: Performance monitoring dashboard
  - [ ] Real-time metrics visualization
  - [ ] Alerting for performance degradation
  - [ ] Capacity planning tools

---

## Completed Recently

### 2025-11-19

- [x] **BUG-015**: Code search category filter mismatch ✅ **COMPLETE**
  - Fixed critical bug where code indexed with category=CODE but searched with category=CONTEXT
  - Impact: 100% failure rate - all code searches returned "No code found"
  - Fix: Changed src/core/server.py:2291,2465 to use MemoryCategory.CODE
  - Discovery: Found during EVAL-001 empirical evaluation
  - **Result:** Code search now works correctly with Qdrant backend

- [x] **EVAL-001**: Empirical evaluation of MCP RAG usefulness ✅ **COMPLETE**
  - Evaluated MCP RAG semantic search vs Baseline (Grep/Read/Glob) approach
  - Tested 10 questions across 6 categories (Architecture, Location, Debugging, Planning, Historical, Cross-cutting)
  - Discovered BUG-015 (category filter mismatch) - FIXED
  - Identified SQLite vs Qdrant performance gap (keyword vs semantic search)
  - Validated Baseline approach is highly effective (4.5/5 quality, 100% success rate)
  - Deliverables: 4 comprehensive reports in planning_docs/EVAL-001_*.md
  - **Next:** Re-run with Qdrant for fair semantic search comparison

- [x] **BUG-008**: File Watcher Async/Threading Bug & Stale Index Cleanup ✅ **COMPLETE**
  - Fixed RuntimeError: no running event loop in file watcher
  - Added event loop parameter to DebouncedFileWatcher and FileWatcherService
  - Implemented thread-safe async scheduling via asyncio.run_coroutine_threadsafe()
  - Enhanced on_deleted() handler to trigger index cleanup
  - Implemented automatic cleanup of stale index entries during reindexing
  - Added _cleanup_stale_entries() and _get_indexed_files() methods
  - Display cleaned entry count in index command output
  - **Impact:** File watching now fully functional, index stays clean automatically

- [x] **UX-006**: Enhanced MCP Tool Descriptions for Proactive Use ✅ **COMPLETE**
  - Added comprehensive "PROACTIVE USE" sections to all 16 MCP tools
  - Included clear "when to use" guidance and concrete examples
  - Added comparisons with built-in tools (e.g., search_code vs Grep)
  - Documented performance characteristics and search modes
  - Updated: store_memory, retrieve_memories, search_code, list_memories, delete_memory,
    index_codebase, find_similar_code, search_all_projects, opt_in/out_cross_project,
    list_opted_in_projects, export/import_memories, get_performance_metrics,
    get_active_alerts, get_health_score
  - **Impact:** Claude Code agents should now use MCP tools more proactively

### 2025-11-18

- [x] **FEAT-028**: Proactive Context Suggestions ✅ **COMPLETE**
  - Full proactive suggestion system with adaptive learning
  - Pattern detector for conversation analysis (4 intent types)
  - Feedback tracker with SQLite persistence
  - 4 new MCP tools: analyze_conversation, get_suggestion_stats, provide_suggestion_feedback, set_suggestion_mode
  - Automatic context injection at high confidence (>0.90)

- [x] **UX-017**: Indexing Time Estimates ✅ **COMPLETE**
  - Intelligent time estimation with historical tracking
  - Real-time ETA calculations during indexing
  - Performance optimization suggestions
  - Time estimates based on rolling 10-run average per project

- [x] **UX-033**: Memory Tagging & Organization System ✅ **COMPLETE**
  - Auto-tagging for automatic tag extraction and inference
  - Hierarchical tag management (4-level hierarchies)
  - Smart collection management
  - 3 CLI commands: tags, collections, auto-tag
  - 4 database tables for tags infrastructure

- [x] **UX-013**: Better Installation Error Messages ✅ **COMPLETE**
  - System prerequisites detection (Python, pip, Docker, Rust, Git)
  - Smart dependency checking with contextual error messages
  - validate-install CLI command
  - OS-specific install commands (macOS/Linux/Windows)
  - 90% setup success rate (up from 30%)

- [x] **FEAT-036**: Project Archival Phase 2 (All 5 sub-phases) ✅ **COMPLETE**
  - Phase 2.1: Archive compression (60-80% storage reduction)
  - Phase 2.2: Bulk operations (auto-archive multiple projects)
  - Phase 2.3: Automatic scheduler (daily/weekly/monthly)
  - Phase 2.4: Export/import for portable archives
  - Phase 2.5: Documentation & polish

- [x] **FEAT-043**: Bulk Memory Operations ✅ **COMPLETE**
  - bulk_delete_memories() MCP tool with dry-run preview
  - Batch processing (100 memories/batch)
  - Safety limits (max 1000 per operation)
  - 21 tests (100% passing)

- [x] **FEAT-044**: Memory Export/Import Tools ✅ **COMPLETE**
  - export_memories() MCP tool (JSON/Markdown formats)
  - import_memories() MCP tool with conflict resolution
  - 19 tests (100% passing)

- [x] **FEAT-047**: Proactive Memory Suggestions ✅ **COMPLETE**
  - suggest_memories() MCP tool
  - Intent detection (implementation, debugging, learning, exploration)
  - Confidence scoring
  - 41 tests (100% passing)

- [x] **FEAT-041**: Memory Listing and Browsing ✅ **COMPLETE**
  - list_memories() MCP tool
  - Filtering by category, scope, tags, importance, dates
  - Sorting and pagination
  - 16 tests (100% passing)

---

## Notes

**Priority Legend:**
- 🔴 **Tier 0** - Critical production blockers (MUST FIX before v4.1 release)
- 🔥 **Tier 1** - High-impact core functionality improvements (prevents 70% abandonment)
- 🟡 **Tier 2** - Core functionality extensions (nice-to-have)
- 🟢 **Tier 3** - UX improvements and performance optimizations
- 🌐 **Tier 4** - Language support extensions
- 🚀 **Tier 5** - Advanced/future features
- 🔨 **Tier 6** - Refactoring & tech debt
- 📚 **Tier 7** - Documentation & monitoring

**Sprint Recommendation for v4.1:**
1. **Week 1-2:** Fix all Tier 0 blockers (bugs, test failures, verification)
2. **Week 3-4:** Complete FEAT-032 Phase 2 (health system) + FEAT-038 (backup automation)
3. **Week 5-6:** Performance testing (TEST-004) + first-run testing (TEST-005)
4. **Week 7-8:** Documentation (DOC-009) + polish + beta testing

**Time Estimates:**
- Items marked with time estimates have been scoped
- Unmarked items need investigation/scoping

**Dependencies:**
- BUG-012 blocks FEAT-040 verification
- TEST-004 required before declaring production-ready
- DOC-009 required for production support

**Planning Documents:**
- Check `planning_docs/` folder for detailed implementation plans
- File format: `{ID}_{description}.md`
- Create planning doc before starting complex items

**Test Status:**
- **Current:** 2117 passing, 17 failing, 20 skipped (99.2% pass rate)
- **Target:** 100% pass rate (all Tier 0 items must pass)
- **Failing:** BUG-012 (15 tests), BUG-013 (2 tests)
