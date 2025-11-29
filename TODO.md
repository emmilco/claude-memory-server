# TODO

## 🚨 CRITICAL BUGS - Code Audit 2025-11-29

**Source:** Comprehensive 3-agent parallel code review analyzing core server, storage, memory/indexing, and embeddings/CLI.
**Audit Report:** `~/.claude/plans/ancient-sleeping-gehret.md`

### 🔴 Critical - Will Crash in Production

- [ ] **BUG-038**: Undefined Variable `PYTHON_PARSER_AVAILABLE`
  - **File:** `src/memory/incremental_indexer.py:186`
  - **Issue:** References `PYTHON_PARSER_AVAILABLE` but variable is never defined
  - **Impact:** `NameError` crash when Rust parser import fails
  - **Root Cause:** REF-020 removed Python parser but missed this reference
  - **Fix:** Remove the entire condition (Rust parser is now required, no fallback)
  - **Effort:** 5 minutes

- [ ] **BUG-039**: SQLite Cache Uses Wrong Constructor
  - **File:** `src/embeddings/cache.py:63`
  - **Issue:** Uses `sqlite3.Connection()` instead of `sqlite3.connect()`
  - **Impact:** `TypeError: 'type' object is not callable` - embedding cache completely broken
  - **Fix:** Change `sqlite3.Connection(...)` to `sqlite3.connect(...)`
  - **Effort:** 5 minutes

- [ ] **BUG-040**: Unreachable Code After `raise` Statement
  - **File:** `src/store/qdrant_store.py:2061-2064`
  - **Issue:** `logger.error()` and second `raise` are unreachable after unconditional `raise`
  - **Impact:** Error logging silently skipped during memory migration failures
  - **Fix:** Move logger.error before raise, or remove dead code
  - **Effort:** 10 minutes

- [ ] **BUG-041**: MPS Generator Never Closed (Apple Silicon Memory Leak)
  - **File:** `src/embeddings/parallel_generator.py:505-509`
  - **Issue:** `close()` method doesn't close `self._mps_generator`
  - **Impact:** Memory/resource leak on Apple Silicon systems
  - **Fix:** Add `if self._mps_generator: await self._mps_generator.close()` in close()
  - **Effort:** 10 minutes

- [ ] **BUG-042**: Executor Null Check Missing in close()
  - **File:** `src/embeddings/parallel_generator.py:511-521`
  - **Issue:** `_close_sync()` calls `self.executor.shutdown()` without null check
  - **Impact:** `AttributeError` if close() called twice
  - **Fix:** Add `if self.executor is not None:` guard
  - **Effort:** 5 minutes

- [ ] **BUG-043**: Cache Return Type Mismatch
  - **File:** `src/embeddings/cache.py:271, 276`
  - **Issue:** Method returns `{}` (dict) when disabled, but signature says `List[Optional[List[float]]]`
  - **Impact:** Runtime type errors when callers iterate expecting list
  - **Fix:** Return `[]` instead of `{}`
  - **Effort:** 5 minutes

---

## 🟠 High Severity - Resource Leaks & Race Conditions

- [ ] **BUG-044**: Resource Leak in update() - Nested Client Acquisitions
  - **File:** `src/store/qdrant_store.py:443-550`
  - **Issue:** `update()` acquires client, then calls `get_by_id()` which acquires another
  - **Impact:** Potential pool exhaustion, deadlock under load
  - **Fix:** Pass existing client to get_by_id() or refactor to avoid nested acquisition
  - **Effort:** 30 minutes

- [ ] **BUG-045**: Race Condition in Cache Stats
  - **File:** `src/embeddings/cache.py:410-416`
  - **Issue:** `self.hits` and `self.misses` accessed outside `_db_lock`
  - **Impact:** Corrupted statistics, negative hit rates possible
  - **Fix:** Move stats access inside `_db_lock` context
  - **Effort:** 15 minutes

- [ ] **BUG-046**: Race Condition in Executor Initialization
  - **File:** `src/embeddings/parallel_generator.py:445-446`
  - **Issue:** Multiple threads may see `executor is None` and all call `initialize()` concurrently
  - **Impact:** Undefined behavior, potential resource duplication
  - **Fix:** Use double-checked locking or async Lock
  - **Effort:** 30 minutes

- [ ] **BUG-047**: Memory Leak in FileWatcher - Unbounded Dict Growth
  - **File:** `src/memory/file_watcher.py:66-69`
  - **Issue:** `file_hashes` and `file_mtimes` dicts grow unbounded - only cleaned on delete, not rename/move
  - **Impact:** Memory growth in long-running instances with frequent file renames
  - **Fix:** Add periodic garbage collection or track file renames
  - **Effort:** 1 hour

- [ ] **BUG-048**: Race Condition in Debounce Task Assignment
  - **File:** `src/memory/file_watcher.py:254-273`
  - **Issue:** Lock released between capturing old_task and assigning new task
  - **Impact:** File events lost or processed out of order
  - **Fix:** Keep lock held for entire operation
  - **Effort:** 20 minutes

- [ ] **BUG-049**: SQLite Connection Leak on Init Failure
  - **File:** `src/memory/project_index_tracker.py:101`
  - **Issue:** Connection opened but not closed if initialization fails after connect
  - **Impact:** File descriptor exhaustion
  - **Fix:** Use context manager or add try/finally
  - **Effort:** 15 minutes

- [ ] **BUG-050**: Connection Pool Client Leak on Early Return
  - **File:** `src/memory/incremental_indexer.py:588-641`
  - **Issue:** Client acquired but method returns early on line 593 without release
  - **Impact:** Connection pool exhaustion
  - **Fix:** Ensure finally block always releases client
  - **Effort:** 15 minutes

- [ ] **BUG-051**: Missing Error Logging in update()
  - **File:** `src/store/qdrant_store.py:545-546`
  - **Issue:** Raises StorageError without logging - unlike other methods that log with exc_info=True
  - **Impact:** Lost stack traces, harder debugging
  - **Fix:** Add `logger.error(f"...", exc_info=True)` before raise
  - **Effort:** 5 minutes

- [ ] **BUG-052**: Progress Callback Not Validated as Callable
  - **File:** `src/memory/incremental_indexer.py:449-493`
  - **Issue:** `progress_callback` called without checking if callable
  - **Impact:** Cryptic errors if wrong type passed
  - **Fix:** Add `if progress_callback and callable(progress_callback):` check
  - **Effort:** 10 minutes

- [ ] **BUG-053**: Silently Swallowed Event Loop Errors
  - **File:** `src/memory/file_watcher.py:211-217`
  - **Issue:** Returns silently if no event loop, callback never executed
  - **Impact:** File changes silently ignored
  - **Fix:** Raise exception or log at ERROR level
  - **Effort:** 10 minutes

- [ ] **BUG-054**: Symlink Vulnerability in Staleness Detection
  - **File:** `src/memory/project_index_tracker.py:331-339`
  - **Issue:** Uses `stat().st_mtime` which follows symlinks
  - **Impact:** External symlinks cause constant unnecessary re-indexing
  - **Fix:** Use `lstat()` or filter symlinks
  - **Effort:** 15 minutes

---

## 🟡 Medium Severity - Tech Debt & Performance

- [ ] **REF-021**: O(n) Staleness Check on Large Directories
  - **File:** `src/memory/project_index_tracker.py:306-352`
  - **Issue:** Iterates all files with `rglob('*')` to find most recent mtime
  - **Impact:** Slow on large codebases (>100k files)
  - **Fix:** Use sampling, caching, or incremental tracking
  - **Effort:** 2-4 hours

- [ ] **REF-022**: No Timeout on File Counting
  - **File:** `src/memory/auto_indexing_service.py:195-217`
  - **Issue:** `_count_indexable_files()` blocks without timeout
  - **Impact:** UI timeout on large codebases
  - **Fix:** Add timeout or async with progress
  - **Effort:** 1 hour

- [ ] **REF-023**: return_type Extraction Not Implemented
  - **File:** `src/memory/incremental_indexer.py:1078`
  - **Issue:** Hardcoded `return_type=None` with TODO comment
  - **Impact:** Call graph analysis lacks return type info
  - **Effort:** 2 hours

- [ ] **REF-024**: Hardcoded Extension List Differs from SUPPORTED_EXTENSIONS
  - **File:** `src/memory/auto_indexing_service.py:203`
  - **Issue:** File extensions hardcoded differently than `SUPPORTED_EXTENSIONS`
  - **Impact:** Auto-indexing counts different files than actual indexer
  - **Fix:** Import and use SUPPORTED_EXTENSIONS constant
  - **Effort:** 15 minutes

- [ ] **REF-025**: Incomplete EXPERIMENTAL Feature Level
  - **File:** `src/config.py:253-278`
  - **Issue:** EXPERIMENTAL feature level only logs warning, doesn't enable anything
  - **Impact:** Users think they're enabling features but nothing happens
  - **Fix:** Document or implement experimental features
  - **Effort:** 1-2 hours

- [ ] **REF-026**: String-Based Error Classification (Fragile)
  - **File:** `src/store/qdrant_store.py:220-223`
  - **Issue:** Error classification by string matching ("connection", "refused", etc.)
  - **Impact:** Fragile - breaks if Qdrant changes error messages
  - **Fix:** Use exception types where possible
  - **Effort:** 2 hours

- [ ] **REF-027**: Direct Private Attribute Access
  - **File:** `src/store/qdrant_store.py:72, 75`
  - **Issue:** Accesses `self.setup.pool._health_checker` (private attribute)
  - **Impact:** Fragile to refactoring of ConnectionPool internals
  - **Fix:** Add public setter method
  - **Effort:** 30 minutes

- [ ] **REF-028**: Hardcoded Health Check Timeout Values
  - **File:** `src/store/qdrant_store.py:75-79`
  - **Issue:** Health check timeouts hardcoded (0.5s, 1.0s, 2.0s)
  - **Impact:** Can't tune for different deployment environments
  - **Fix:** Move to ServerConfig
  - **Effort:** 30 minutes

- [ ] **REF-029**: Race Condition in Shutdown
  - **File:** `src/embeddings/parallel_generator.py:514-515`
  - **Issue:** No guard against concurrent access during shutdown
  - **Impact:** Potential crash if generating while closing
  - **Fix:** Add shutdown flag or lock
  - **Effort:** 30 minutes

- [ ] **REF-030**: Missing Argument Validation in CLI
  - **File:** `src/cli/__init__.py:224-230` (git-index command)
  - **Issue:** No validation that `--project-name` is valid identifier
  - **Impact:** Invalid project names could corrupt storage
  - **Fix:** Add validation regex
  - **Effort:** 20 minutes

- [ ] **REF-031**: Inefficient SQL in batch_get_sync
  - **File:** `src/embeddings/cache.py:287-295`
  - **Issue:** Dynamic placeholder generation for IN clause
  - **Impact:** Potential issues with very large batches
  - **Fix:** Use parameterized chunking
  - **Effort:** 1 hour

---

## 🟢 Low Severity - Minor Issues

- [ ] **UX-052**: get_by_id() Silent Failure
  - **File:** `src/store/qdrant_store.py:396-398`
  - **Issue:** Returns `None` on error instead of raising
  - **Impact:** Can't distinguish "not found" from "retrieval error"
  - **Fix:** Add optional `raise_on_error` parameter

- [ ] **UX-053**: count() Returns 0 on Error
  - **File:** `src/store/qdrant_store.py:436-438`
  - **Issue:** Returns 0 on error, indistinguishable from empty collection
  - **Fix:** Return -1 on error or add optional exception raising

- [ ] **DOC-011**: Typo in spelling_suggester
  - **File:** `src/memory/spelling_suggester.py:134`
  - **Issue:** "excepton" should be "exception"

- [ ] **REF-032**: Unused start_async() Method (Dead Code)
  - **File:** `src/memory/file_watcher.py:376-386`
  - **Issue:** Defined but never called
  - **Fix:** Remove or document intended use

- [ ] **REF-033**: Hardcoded Parallel Threshold
  - **File:** `src/embeddings/parallel_generator.py:231`
  - **Issue:** `parallel_threshold = 10` hardcoded
  - **Fix:** Move to config

- [ ] **DOC-012**: Missing Docstrings in index_command
  - **File:** `src/cli/index_command.py:101-107`
  - **Issue:** Doesn't document args attributes or exceptions

- [ ] **REF-034**: Inconsistent Log Levels in Cache
  - **File:** `src/embeddings/cache.py`
  - **Issue:** Cache hits at DEBUG, errors at ERROR, no INFO for init

- [ ] **REF-035**: Magic Number in Generator ThreadPool
  - **File:** `src/embeddings/generator.py:63`
  - **Issue:** `ThreadPoolExecutor(max_workers=2)` - why 2?
  - **Fix:** Add comment explaining or make configurable

- [ ] **REF-036**: Double Logging on Error
  - **File:** `src/embeddings/parallel_generator.py:105-107`
  - **Issue:** Logs with exc_info then re-raises, causing double logs

- [ ] **REF-037**: Close() Not Idempotent
  - **File:** `src/embeddings/parallel_generator.py:505-521`
  - **Issue:** Calling close() twice will error
  - **Fix:** Make close() idempotent with guard

---

## ID System
Each item has a unique ID for tracking and association with planning documents in `planning_docs/`.
Format: `{TYPE}-{NUMBER}` where TYPE = FEAT|BUG|TEST|DOC|PERF|REF|UX

## Priority System

**Prioritization Rules:**
1. Complete partially finished initiatives before starting new ones
2. Prioritize items that have greater user impact over items that have less impact

---

## Current Sprint - Open Items

### 🟠 Test Suite Optimization

- [ ] **TEST-029**: Test Suite Optimization Refactoring 🔥🔥
  - **Source:** 4-agent parallel analysis (2025-11-28)
  - **Problem:** Test suite has compute waste and missed data sharing opportunities
  - **Analysis:** `planning_docs/TEST-029_test_suite_optimization_analysis.md`
  - **Phase 1 - Quick Wins (~1-2 days):**
    - [ ] Reduce performance test data volumes in `test_scalability.py` (6000→600 memories)
    - [ ] Create session-scoped `config` fixture in `tests/unit/conftest.py`
    - [ ] Remove `assert True` validation theater in `test_file_watcher_indexing.py`
    - [ ] Convert loop-based tests to `@pytest.mark.parametrize` in `test_server_extended.py`
  - **Phase 2 - Medium Effort (~3-5 days):**
    - [ ] Create session-scoped `pre_indexed_server` fixture for E2E tests
    - [ ] Parameterize fusion method tests in `test_hybrid_search_integration.py`
    - [ ] Change `sample_memories` to module scope in `test_hybrid_search.py`
    - [ ] Parameterize language parsing tests (`test_kotlin_parsing.py`, etc.)
  - **Phase 3 - Larger Refactor (~1-2 weeks):**
    - [ ] Fix/restore skipped integration tests (3 files with module-level skip)
    - [ ] Deduplicate `search_code` test coverage across multiple files
    - [ ] Reorganize benchmark tests to `tests/performance/`
    - [ ] Create read-only vs write test distinction with fixture scoping
  - **Expected Impact:** 30-50% reduction in test execution time

### 🟢 UX Improvements & Performance

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

---

### 🌐 Tier 4: Language Support Extensions

- [ ] **FEAT-007**: Add support for Ruby (~3 days)
  - [ ] tree-sitter-ruby integration
  - [ ] Method, class, module extraction

### 🚀 Tier 5: Advanced/Future Features

- [ ] **FEAT-017**: Multi-repository support
  - [ ] Index across multiple repositories
  - [ ] Cross-repo code search

- [ ] **FEAT-014**: Semantic refactoring
  - [ ] Find all usages semantically
  - [ ] Suggest refactoring opportunities

- [ ] **FEAT-015**: Code review features
  - [ ] LLM-powered suggestions based on patterns
  - [ ] Identify code smells

- [ ] **FEAT-050**: Track cache usage in queries
  - [ ] Add cache hit/miss tracking to retrieve_memories()
  - [ ] Include used_cache flag in QueryResponse
  - **Location:** src/core/server.py:631
  - **Discovered:** 2025-11-20 during code review

- [ ] **FEAT-051**: Query-based deletion for Qdrant
  - [ ] Implement deletion by query filters instead of memory IDs
  - [ ] Support clearing entire project indexes
  - **Location:** src/core/server.py:2983
  - **Discovered:** 2025-11-20 during code review

- [ ] **FEAT-052**: Map project_name to repo_path for git history
  - [ ] Add configuration mapping between project names and repository paths
  - [ ] Enable git history search by project_name instead of hardcoded paths
  - **Location:** src/core/server.py:3448
  - **Discovered:** 2025-11-20 during code review

- [ ] **FEAT-053**: Enhanced file history with diff content
  - [ ] Include diff content analysis in file history search
  - [ ] Match changes in diff content, not just commit messages
  - **Location:** src/core/server.py:3679
  - **Discovered:** 2025-11-20 during code review

- [ ] **FEAT-054**: File pattern and language filtering for multi-repo search
  - [ ] Add file_pattern parameter to cross-project search
  - [ ] Add language filter support to search_all_projects()
  - **Location:** src/memory/multi_repository_search.py:221
  - **Discovered:** 2025-11-20 during code review

- [ ] **REF-011**: Integrate ProjectArchivalManager with metrics
  - [ ] Connect metrics_collector to ProjectArchivalManager
  - [ ] Enable accurate active vs archived project counts
  - **Location:** src/monitoring/metrics_collector.py:201
  - **Discovered:** 2025-11-20 during code review

- [ ] **REF-012**: Implement rollback support for bulk operations
  - [ ] Add soft delete capability for bulk operations
  - [ ] Enable rollback of bulk deletions
  - **Location:** src/memory/bulk_operations.py:394
  - **Discovered:** 2025-11-20 during code review

#### Web Dashboard Enhancements (Post-MVP)

**Phase 2: Advanced Analytics (~32-40 hours, 1-2 weeks)**

- [ ] **UX-039**: Memory Relationships Graph Viewer (~10-12 hours)
  - [ ] Interactive graph using D3.js or vis.js
  - [ ] Click memory to see relationships (SUPERSEDES, CONTRADICTS, RELATED_TO)
  - [ ] Color-coded by relationship type
  - [ ] Zoom/pan controls
  - **Impact**: Understand knowledge structure, discover related content

- [ ] **UX-040**: Project Comparison View (~6-8 hours)
  - [ ] Select 2-4 projects to compare side-by-side
  - [ ] Bar charts: memory count, file count, function count
  - [ ] Category distribution comparison
  - [ ] Performance metrics comparison (index time, search latency)
  - **Impact**: Identify outliers, understand relative project complexity

- [ ] **UX-041**: Top Insights and Recommendations (~8-10 hours)
  - [ ] Automatic insight detection
  - [ ] Priority/severity levels
  - [ ] One-click actions ("Index Now", "View Memories", "Adjust Settings")
  - **Impact**: Proactive guidance to improve memory system usage

**Phase 3: Productivity Features (~16-22 hours, 1 week)**

- [ ] **UX-042**: Quick Actions Toolbar (~6-8 hours)
  - [ ] Buttons for: Index Project, Create Memory, Export Data, Run Health Check
  - [ ] Forms with validation
  - [ ] Status feedback (loading, success, error)
  - **Impact**: Avoid switching to CLI for frequent tasks

- [ ] **UX-043**: Export and Reporting (~6-8 hours)
  - [ ] Export formats: JSON, CSV, Markdown, PDF (summary report)
  - [ ] Filters: by project, date range, category
  - [ ] Optional: Scheduled reports (daily/weekly email)
  - **Impact**: Share insights, backup data, integration with other tools

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

### 🔨 Tier 6: Refactoring & Tech Debt

- [ ] **REF-020**: Remove Python Parser Fallback References (Remaining)
  - **Remaining (low priority, doc updates):**
    - [ ] Update CLAUDE.md references to Python parser fallback
    - [ ] Update docs/setup.md - Rust parser is now required, not optional

- [ ] **REF-007**: Consolidate two server implementations
  - Merge old mcp_server.py with new src/core/
  - Unified architecture

- [ ] **REF-008**: Remove deprecated API usage
  - Update to latest Qdrant APIs
  - Update to latest MCP SDK

- [ ] **REF-013**: Split Monolithic Core Server (~4-6 months) 🔥🔥🔥
  - **Current State:** `src/core/server.py` is 5,192 lines - violates Single Responsibility Principle
  - **Remaining Phases:** Extract remaining services (MemoryService, CodeIndexingService, QueryService, CrossProjectService)
  - **Next:** Phase 2 - MemoryService extraction recommended
  - **See:** `planning_docs/REF-013_split_server_implementation_plan.md`

- [ ] **TEST-007**: Increase Test Coverage to 80%+ (~2-3 months) 🔥🔥
  - **Current State:** 63.68% overall coverage (7,291 of 20,076 lines uncovered)
  - **Critical Gaps:**
    - `src/core/security_logger.py` - 0% (99 lines) 🔴 CRITICAL
    - `src/dashboard/web_server.py` - 0% (299 lines) 🔴 CRITICAL
    - `src/memory/health_scheduler.py` - 0% (172 lines) 🔴 CRITICAL
  - **Target:** 80%+ for core modules (src/core, src/store, src/memory, src/embeddings)
  - **See:** `planning_docs/TEST-007_coverage_improvement_plan.md`

- [ ] **REF-014**: Extract Qdrant-Specific Logic (~1-2 months) 🔥
  - **Current State:** Qdrant-specific code leaks into business logic
  - **Problem:** 2,328-line `qdrant_store.py` with complex Qdrant queries, tight coupling
  - **See:** `planning_docs/REF-014_repository_pattern_plan.md`

### 📚 Tier 7: Documentation & Monitoring

- [ ] **TEST-006**: Comprehensive E2E Manual Testing (~10-15 hours) 🔄 **IN PROGRESS**
  - [ ] Implement automated test logic (currently MANUAL_REQUIRED placeholders)
  - [ ] Execute full E2E test plan (200+ test scenarios)
  - [ ] Test all 16 MCP tools for functionality and UX
  - [ ] Test all 28+ CLI commands end-to-end
  - [ ] Generate final production readiness report
  - **Planning Docs:** `planning_docs/TEST-006_*.md`

- [ ] **DOC-005**: Add performance tuning guide for large codebases
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

- [ ] **FEAT-021**: Memory lifecycle management
  - [ ] Auto-expire old memories
  - [ ] Memory importance decay
  - [ ] Storage optimization

- [ ] **FEAT-022**: Performance monitoring dashboard
  - [ ] Real-time metrics visualization
  - [ ] Alerting for performance degradation
  - [ ] Capacity planning tools

**Phase 2: Structural Analysis (4 weeks)**

- [ ] **FEAT-059**: Structural/Relational Queries (~2 weeks) 🔥🔥🔥
  - **Current Gap:** No call graph analysis, dependency traversal, or relationship queries
  - **Proposed Solution:**
    - [ ] Add `find_callers(function_name, project)` - Find all functions calling this function
    - [ ] Add `find_callees(function_name, project)` - Find all functions called by this function
    - [ ] Add `find_implementations(interface_name)` - Find all implementations of interface/trait
    - [ ] Add `find_dependencies(file_path)` - Get dependency graph for a file (imports/requires)
    - [ ] Add `find_dependents(file_path)` - Get reverse dependencies (what imports this file)
    - [ ] Add `get_call_chain(from_function, to_function)` - Show call path between functions
  - **Impact:** Enables architectural analysis, refactoring planning, impact analysis
  - **See:** planning_docs/FEAT-059_structural_queries_plan.md

- [ ] **FEAT-061**: Git/Historical Integration (~1 week) 🔥
  - **Current Gap:** No git history, change frequency, or churn analysis
  - **Proposed Solution:**
    - [ ] Add `search_git_history(query, since, until)` - Semantic search over commit messages and diffs
    - [ ] Add `get_change_frequency(file_or_function)` - How often does this change? (commits/month)
    - [ ] Add `get_churn_hotspots(project)` - Files with highest change frequency
    - [ ] Add `get_recent_changes(project, days=30)` - Recent modifications with semantic context
    - [ ] Add `blame_search(pattern)` - Who wrote code matching this pattern?
  - **Impact:** Understand evolution, identify unstable code, find domain experts
  - **See:** planning_docs/FEAT-061_git_integration_plan.md

**Phase 3: Visualization (4-6 weeks)**

- [ ] **FEAT-062**: Architecture Visualization & Diagrams (~4-6 weeks) 🔥
  - **Current Gap:** No visual representation of architecture, dependencies, or call graphs
  - **Proposed Solution:**
    - [ ] Add `visualize_architecture(project)` - Generate architecture diagram
    - [ ] Add `visualize_dependencies(file_or_module)` - Dependency graph with depth control
    - [ ] Add `visualize_call_graph(function_name)` - Call graph showing function relationships
    - [ ] Export formats: Graphviz DOT, Mermaid, D3.js JSON, PNG/SVG images
  - **Impact:** 10x faster architecture understanding, shareable diagrams
  - **See:** planning_docs/FEAT-062_architecture_visualization_plan.md

---

## Notes

**Priority Legend:**
- 🔴 **Critical** - Production blockers (MUST FIX immediately)
- 🟠 **High** - Resource leaks, race conditions (fix in next sprint)
- 🟡 **Medium** - Tech debt, performance (plan for)
- 🟢 **Low** - Minor issues (opportunistic)
- 🔥 **Impact** - High user impact items

**Planning Documents:**
- Check `planning_docs/` folder for detailed implementation plans
- File format: `{ID}_{description}.md`
- Create planning doc before starting complex items

---

## Archived - Completed Items

Items below are completed and archived for reference. See CHANGELOG.md for details.

### Completed 2025-11-25 to 2025-11-29:
- TEST-013 through TEST-028: Test antipattern audit (all complete)
- REF-015 through REF-019: Code review fixes (all complete)
- BUG-034 through BUG-037: Critical bugs (all fixed)
- DOC-008 through DOC-010: Documentation (all complete)
- UX-049 through UX-051: UX improvements (all complete)
- PERF-008: Distributed tracing (complete)

### Completed 2025-11-20 to 2025-11-24:
- BUG-012 through BUG-033: E2E testing bugs (all fixed)
- FEAT-046 through FEAT-060: Code intelligence features (all complete)
- UX-012, UX-034-048: Dashboard and UX features (all complete)
- PERF-002, PERF-006, PERF-007: Performance features (all complete)
- REF-002, REF-003, REF-005, REF-006, REF-010: Refactoring (all complete)

### Completed 2025-11-18 to 2025-11-19:
- FEAT-028, FEAT-036, FEAT-041, FEAT-043, FEAT-044, FEAT-047: Features (all complete)
- UX-006, UX-013, UX-017, UX-026, UX-033: UX improvements (all complete)
- BUG-008, BUG-015: Bug fixes (all complete)
- EVAL-001: MCP RAG evaluation (complete)
