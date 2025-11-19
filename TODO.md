# TODO

## ID System
Each item has a unique ID for tracking and association with planning documents in `planning_docs/`.
Format: `{TYPE}-{NUMBER}` where TYPE = FEAT|BUG|TEST|DOC|PERF|REF|UX

## Priority System

**Prioritization Rules:**
1. Complete partially finished initiatives before starting new ones
2. Prioritize items that have greater user impact over items that have less impact

## Current Sprint

### 🔴 Tier 0: Critical Production Blockers (MUST FIX BEFORE v4.1 RELEASE)

**These items block production readiness and must be resolved immediately**

- [ ] **BUG-011**: Health Check Config Error (~2-4 hours) 🔥🔥🔥🔥🔥
  - **BLOCKING:** Health check command fails with `'ServerConfig' object has no attribute 'cache_dir_expanded'`
  - **Location:** `src/cli/health_command.py:38`
  - [ ] Fix ServerConfig to include cache_dir_expanded attribute
  - [ ] Add test coverage for health check command
  - [ ] Verify health check works with both SQLite and Qdrant backends
  - **Impact:** Core diagnostic tool is broken, blocks user troubleshooting
  - **Priority:** P0 - Production blocker

- [ ] **BUG-012**: Fix FEAT-040 Integration Test Failures (~1-2 days) 🔥🔥🔥🔥🔥
  - **BLOCKING:** 15/15 integration tests failing for memory update operations
  - **Status:** FEAT-040 implementation exists but integration tests all fail
  - **Failed tests:** `tests/integration/test_memory_update_integration.py` (15 failures)
  - [ ] Debug why update_memory integration tests fail
  - [ ] Fix MCP tool registration or implementation issues
  - [ ] Verify embedding regeneration works correctly
  - [ ] Fix timestamp preservation logic
  - [ ] Fix read-only mode protection
  - **Impact:** Memory update operations not production-ready
  - **Priority:** P0 - Core CRUD operation broken

- [ ] **BUG-013**: Fix Query Synonym Test Failures (~2-4 hours) 🔥🔥🔥
  - **BLOCKING:** 2 query synonym tests failing
  - **Failed tests:**
    - `tests/unit/test_query_synonyms.py::TestSpecificUseCases::test_api_search`
    - `tests/unit/test_query_synonyms.py::TestSpecificUseCases::test_error_handling_search`
  - [ ] Debug query expansion failures
  - [ ] Fix environment-dependent query expansion behavior
  - **Impact:** Hybrid search quality may be degraded
  - **Priority:** P0 - Test suite must be 100% passing

- [ ] **FEAT-040**: Memory Update/Edit Operations - VERIFICATION NEEDED (~1 day) 🔥🔥🔥🔥
  - **STATUS:** Implementation exists but ALL 15 integration tests failing (see BUG-012)
  - **BLOCKED BY:** BUG-012
  - [ ] Fix all integration test failures (see BUG-012)
  - [ ] Run end-to-end manual verification
  - [ ] Test via MCP protocol (not just unit tests)
  - [ ] Document known limitations if any
  - **Impact:** Essential CRUD operation - currently can only create/delete, not update
  - **Use case:** "I changed my mind about preferring tabs - update to spaces"
  - **Priority:** P0 - Fundamental CRUD gap

- [ ] **FEAT-041**: Memory Listing and Browsing - VERIFICATION NEEDED (~1 day) 🔥🔥🔥
  - **STATUS:** Recently implemented (2025-11-18), needs integration testing
  - [ ] Verify list_memories() works via MCP protocol
  - [ ] Test all filters (category, scope, tags, importance, dates)
  - [ ] Test pagination with large datasets (1000+ memories)
  - [ ] Test sorting options (created_at, updated_at, importance)
  - [ ] Document usage examples in API.md
  - **Impact:** Memory discoverability without requiring semantic search
  - **Priority:** P0 - Core CRUD operation needs verification

- [ ] **TEST-004**: Performance Testing at Scale (~3-5 days) 🔥🔥🔥
  - **CRITICAL:** No benchmarks for realistic database sizes
  - [ ] Generate test database with 10K memories
  - [ ] Generate test database with 50K memories
  - [ ] Benchmark search latency at scale (target: <50ms p95)
  - [ ] Benchmark memory retrieval at scale
  - [ ] Test health dashboard with large datasets
  - [ ] Identify and document performance degradation points
  - [ ] Create performance regression test suite
  - **Impact:** Unknown performance at real-world scale, could be unusable for heavy users
  - **Priority:** P0 - Required for production readiness

- [ ] **TEST-005**: First-Run Experience Testing (~2-3 days) 🔥🔥
  - **CRITICAL:** Setup wizard needs validation with real users
  - [ ] Test minimal preset end-to-end (clean machine)
  - [ ] Test standard preset end-to-end
  - [ ] Test full preset end-to-end
  - [ ] Verify sample project indexing works
  - [ ] Test common failure scenarios (missing deps, wrong Python version)
  - [ ] Measure actual installation time vs. documented estimates
  - [ ] Document all prerequisites clearly
  - **Impact:** Installation friction = user abandonment
  - **Priority:** P0 - First impression is critical

- [ ] **DOC-009**: Error Recovery Workflows (~2-3 days) 🔥🔥
  - **CRITICAL:** No documentation for common failure recovery
  - [ ] Document: "What if Qdrant corrupts?"
  - [ ] Document: "What if indexing breaks mid-way?"
  - [ ] Document: "What if database gets polluted?"
  - [ ] Document: "How to reset and start fresh?"
  - [ ] Document: "How to recover from backup?"
  - [ ] Create troubleshooting decision tree
  - **Impact:** Users stuck with broken systems have no recovery path
  - **Priority:** P0 - Production support requirement

---

### 🔥 Tier 1: High-Impact Core Functionality Improvements

**These are the highest-impact features that directly enhance search, retrieval, and core capabilities**

- [ ] **FEAT-032**: Memory Lifecycle & Health System - Phase 2 (~1-2 weeks) 🔥🔥🔥🔥🔥
  - **Planning doc:** `planning_docs/STRATEGIC-001_long_term_product_evolution.md`
  - **CRITICAL: Prevents 70% user abandonment at 6-12 months**
  - [ ] Health monitoring dashboard with quality metrics (CLI command started)
  - [ ] Auto-actions: weekly archival, monthly stale deletion (background jobs)
  - [ ] Health scoring: overall health, noise ratio, duplicate rate, contradiction rate
  - [ ] Weekly automated health reports with recommendations
  - **Impact:** Prevents degradation, 30-50% noise reduction, maintains quality long-term
  - **Strategic Priority:** P0 - Foundation for sustainable long-term use
  - **Status:** Phase 1 complete (lifecycle states, transitions, weighting), Phase 2 pending

- [ ] **FEAT-038**: Data Export, Backup & Portability (~1-2 weeks) 🔥🔥🔥🔥
  - **Planning doc:** `planning_docs/STRATEGIC-001_long_term_product_evolution.md`
  - **CRITICAL:** Required for user trust and data ownership
  - **Status:** Partial implementation via FEAT-044 (export/import MCP tools complete)
  - [ ] Backup automation: daily/weekly schedules, retention policies (NOT YET IMPLEMENTED)
  - [ ] Export to Markdown knowledge base: human-readable memory export
  - [ ] Cloud sync (optional): Dropbox/Google Drive integration, encrypted
  - [ ] CLI commands for backup scheduling and automation
  - [ ] Cross-machine workflow documentation and testing
  - **Completed:**
    - ✅ Export memories to JSON/Markdown (FEAT-044)
    - ✅ Import memories from JSON with conflict resolution (FEAT-044)
    - ✅ Project archival export/import (FEAT-036 Phase 2.4)
  - **Impact:** Prevents data loss and lock-in, enables migration, disaster recovery
  - **Priority:** P1 - Critical for production trust

- [ ] **FEAT-028**: Proactive Context Suggestions (~3-4 days) 🔥🔥🔥
  - **Status:** Partial implementation via FEAT-047 (suggest_memories tool complete)
  - [ ] **Confirm overall feature design with user before proceeding**
  - [ ] MCP tool auto-invocation based on conversation (NOT YET IMPLEMENTED)
  - [ ] Automatic context injection (high confidence only)
  - [ ] User sees: "I found similar registration logic - use that pattern?"
  - [ ] Configurable threshold (default: 0.9 confidence)
  - **Completed:**
    - ✅ Intent detection (FEAT-047)
    - ✅ Pattern matching (FEAT-047)
    - ✅ suggest_memories() MCP tool (FEAT-047)
  - **Impact:** Reduces cognitive load, surfaces hidden gems

### 🟡 Tier 2: Core Functionality Extensions

**These extend core capabilities with new features (nice-to-have)**

#### Critical API Gaps (Documented but Missing Implementation)

- [ ] **FEAT-039**: Cross-Project Consent Tools (~2-3 days) 🔥🔥🔥
  - **CRITICAL:** Currently documented in API.md but not implemented in server.py
  - [ ] Implement `opt_in_cross_project` MCP tool
  - [ ] Implement `opt_out_cross_project` MCP tool
  - [ ] Implement `list_opted_in_projects` MCP tool
  - [ ] Create CrossProjectConsentManager class
  - [ ] Store consent preferences persistently
  - [ ] Integrate with existing `search_all_projects` tool
  - [ ] Add comprehensive tests (consent workflow, privacy enforcement)
  - **Impact:** Privacy controls for cross-project search, fixes API documentation gap
  - **Dependencies:** None - standalone feature
  - **Priority:** HIGH - API documentation promises this feature

#### Core Memory Management Gaps

- [ ] **FEAT-042**: Advanced Memory Search Filters (~2-3 days) 🔥🔥
  - [ ] Extend `retrieve_memories` with advanced filters
  - [ ] Date range filtering (created_at, updated_at, last_accessed)
  - [ ] Tag combinations (AND/OR logic: "auth AND security" OR "python")
  - [ ] Provenance filtering (source, trust score)
  - [ ] Exclude filters (NOT tag, NOT category)
  - [ ] Complex query DSL support (optional)
  - [ ] Tests: filter combinations, edge cases, performance
  - **Impact:** Power-user memory organization and retrieval
  - **Use case:** "Show memories created this week tagged with 'authentication' OR 'security'"

#### Code Intelligence Enhancements

- [ ] **FEAT-045**: Project Reindexing Control (~2 days) 🔥🔥
  - [ ] Implement `reindex_project` MCP tool
  - [ ] Force full re-index (bypass incremental cache)
  - [ ] Option to clear existing index first
  - [ ] Progress tracking and cancellation support
  - [ ] Tests: full reindex, cache clearing, error recovery
  - **Impact:** Recovery from corruption, config changes, or cache issues
  - **Use case:** "Something went wrong with indexing - start from scratch"

- [ ] **FEAT-046**: Indexed Content Visibility (~2-3 days) 🔥🔥
  - [ ] Implement `get_indexed_files` MCP tool
  - [ ] Implement `list_indexed_units` MCP tool (functions, classes, etc.)
  - [ ] Filter by project, language, file pattern
  - [ ] Show indexing metadata: last indexed, hash, unit count
  - [ ] Pagination for large projects
  - [ ] Tests: listing, filtering, pagination
  - **Impact:** Transparency into what's indexed, debugging aid
  - **Use case:** "What files are indexed in this project?" or "Show all Python functions indexed"
  - **Enhances:** `get_status` (which only shows counts)

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

#### UX Quick Wins

- [ ] **UX-033**: Memory Tagging & Organization System (~1 week) 🔥🔥
  - **Planning doc:** `planning_docs/STRATEGIC-001_long_term_product_evolution.md`
  - [ ] Auto-tagging: extract keywords from content, infer categories
  - [ ] Hierarchical tags: language/python/async, architecture/microservices
  - [ ] Smart collections: auto-create thematic groups (e.g., "Python async patterns")
  - [ ] Tag-based search and filtering
  - [ ] Collection management: create, add, browse by theme
  - [ ] Manual tag curation and editing
  - **Impact:** Better discovery through smart organization

#### Error Handling & Graceful Degradation

- [ ] **UX-012**: Graceful degradation (~2 days)
  - [ ] Auto-fallback: Qdrant unavailable → SQLite
  - [ ] Auto-fallback: Rust unavailable → Python parser
  - [ ] Warn user about performance implications
  - [ ] Option to upgrade later

- [ ] **UX-013**: Better installation error messages (~1 day)
  - [ ] Detect missing prerequisites with install instructions
  - [ ] OS-specific help (apt-get vs brew vs chocolatey)
  - [ ] Common error patterns with solutions
  - [ ] Link to troubleshooting guide

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

- [ ] **UX-016**: Memory migration tools (~1-2 days)
  - [ ] Move memory between scopes (global ↔ project)
  - [ ] Bulk reclassification (change context level)
  - [ ] Memory merging (combine duplicate memories)
  - [ ] Memory export/import with project context

- [ ] **UX-017**: Indexing time estimates (~1 day)
  - [ ] Estimate time based on file count and historical data
  - [ ] Show estimate before starting large indexes
  - [ ] Progress updates with time remaining
  - [ ] Performance tips (exclude tests, node_modules)

- [ ] **UX-018**: Background indexing for large projects (~3 days)
  - [ ] Start indexing in background
  - [ ] Search available on incremental results
  - [ ] Notification when complete
  - [ ] Resume interrupted indexing

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

- [ ] **FEAT-008**: Add support for PHP (~3 days)
  - [ ] tree-sitter-php integration
  - [ ] Function, class, trait extraction

- [ ] **FEAT-009**: Add support for Swift (~3 days)
  - [ ] tree-sitter-swift integration
  - [ ] Function, struct, class extraction

- [ ] **FEAT-010**: Add support for Kotlin (~3 days)
  - [ ] tree-sitter-kotlin integration
  - [ ] Function, class, object extraction

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

- [ ] **UX-024**: Usage feedback mechanisms (~2-3 days)
  - [ ] "Was this helpful?" for search results
  - [ ] Learning from user behavior
  - [ ] Query refinement suggestions
  - [ ] Result quality metrics

- [ ] **UX-026**: Web dashboard (~1-2 weeks)
  - [ ] Optional web UI for visibility
  - [ ] Visual project explorer
  - [ ] Memory graph/relationships
  - [ ] Usage analytics

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

- [ ] **REF-007**: Consolidate two server implementations
  - Merge old mcp_server.py with new src/core/
  - Unified architecture

- [ ] **REF-008**: Remove deprecated API usage
  - Update to latest Qdrant APIs
  - Update to latest MCP SDK

- [ ] **REF-001**: Fix Async/Await Patterns (~1 hour)
  - Requires profiling first
  - Optimize async patterns for better performance

- [ ] **REF-002**: Add Structured Logging (~1.5 hours)
  - Requires logging format decision
  - Implement consistent logging across modules

- [ ] **REF-003**: Split Validation Module (~2 hours)
  - Requires careful refactoring for circular imports
  - Separate validation concerns

- [ ] **REF-004**: Update datetime.utcnow() to datetime.now(UTC)
  - Low priority, cosmetic fix for deprecation warnings

- [ ] **REF-005**: Update to Pydantic v2 ConfigDict style
  - Low priority, modernize configuration

- [ ] **REF-006**: Update Qdrant search() to query_points()
  - Low priority, will be required in future Qdrant versions

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

- [ ] **DOC-004**: Update README with code search examples
- [ ] **DOC-005**: Add performance tuning guide for large codebases
- [ ] **DOC-006**: Create troubleshooting guide for common parser issues
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

## Completed Recently (2025-11-18)

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

- [x] **FEAT-041**: Memory Listing and Browsing ✅ **COMPLETE** (needs verification - see Tier 0)
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
