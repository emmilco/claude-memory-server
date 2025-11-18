# TODO

## ID System
Each item has a unique ID for tracking and association with planning documents in `planning_docs/`.
Format: `{TYPE}-{NUMBER}` where TYPE = FEAT|BUG|TEST|DOC|PERF|REF|UX

## Priority System

**Prioritization Rules:**
1. Complete partially finished initiatives before starting new ones
2. Prioritize core functionality improvements over UX and dev tools improvements
3. Prioritize items that have greater impact over items that have less impact

## Current Sprint

### 🔥 Tier 2: High-Impact Core Functionality Improvements

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

- [ ] **FEAT-028**: Proactive Context Suggestions (~3-4 days) 🔥🔥🔥
  - [ ] **Confirm overall feature design with user before proceeding**
  - [ ] Analyze conversation context to suggest relevant code/memories
  - [ ] Pattern matching: "I need to add X" → suggest similar implementations
  - [ ] Automatic context injection (high confidence only)
  - [ ] User sees: "I found similar registration logic - use that pattern?"
  - [ ] MCP tool auto-invocation based on conversation
  - [ ] Configurable threshold (default: 0.9 confidence)
  - **Impact:** Reduces cognitive load, surfaces hidden gems

### 🟡 Tier 3: Core Functionality Extensions

**These extend core capabilities with new features**

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

- [ ] **FEAT-040**: Memory Update/Edit Operations (~3-4 days) 🔥🔥🔥🔥
  - [ ] Implement `update_memory` MCP tool
  - [ ] Support partial updates (content, importance, tags, category)
  - [ ] Preserve memory ID, creation date, and provenance
  - [ ] Update embeddings when content changes
  - [ ] Add version history tracking (optional)
  - [ ] Validation: ensure updates maintain data integrity
  - [ ] Tests: update workflows, concurrent updates, validation
  - **Impact:** Essential CRUD operation - currently can only create/delete, not update
  - **Use case:** "I changed my mind about preferring tabs - update to spaces"
  - **Priority:** CRITICAL - fundamental gap in memory lifecycle

- [ ] **FEAT-041**: Memory Listing and Browsing (~2-3 days) 🔥🔥🔥
  - [ ] Implement `list_memories` MCP tool (pagination support)
  - [ ] Implement `get_memory_by_id` MCP tool
  - [ ] Support filtering: by category, context_level, tags, date range, project
  - [ ] Support sorting: by importance, date, relevance
  - [ ] Pagination with cursor-based or offset/limit
  - [ ] Tests: filtering, pagination, edge cases
  - **Impact:** Memory discoverability without requiring semantic search
  - **Use case:** "Show me all my Python preferences" or "Get memory by ID for reference"
  - **Priority:** HIGH - improves memory management UX significantly

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

- [ ] **FEAT-043**: Bulk Memory Operations (~2-3 days) 🔥🔥
  - [ ] Implement `bulk_delete_memories` MCP tool
  - [ ] Support filtering criteria (same as list_memories)
  - [ ] Dry-run mode (preview what will be deleted)
  - [ ] Batch processing with progress tracking
  - [ ] Rollback support (optional)
  - [ ] Safety limits (max 1000 per operation)
  - [ ] Tests: bulk operations, dry-run, safety limits
  - **Impact:** Efficient cleanup operations instead of one-by-one deletion
  - **Use case:** "Delete all SESSION_STATE memories older than 30 days"
  - **Integrates with:** FEAT-032 (lifecycle management), UX-025 (storage optimizer)

- [ ] **FEAT-044**: Memory Export/Import Tools (~3-4 days) 🔥🔥
  - [ ] Implement `export_memories` MCP tool
  - [ ] Implement `import_memories` MCP tool
  - [ ] Export formats: JSON (structured), Markdown (human-readable), portable archive
  - [ ] Support filtering for selective export
  - [ ] Import with conflict resolution (skip, overwrite, merge)
  - [ ] Preserve metadata: IDs, timestamps, provenance
  - [ ] Validation and error handling
  - [ ] Tests: export/import workflows, format validation, conflict resolution
  - **Impact:** Data portability, backup, migration, sharing memory sets
  - **Related to:** FEAT-038 (broader backup system) but focused on MCP tools
  - **Priority:** HIGH - data ownership and portability

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

- [ ] **FEAT-047**: Proactive Memory Suggestions (~4-5 days) 🔥🔥🔥🔥
  - [ ] Implement `suggest_memories` MCP tool
  - [ ] Analyze conversation context for relevant memories
  - [ ] Pattern matching: detect user intent ("I need to add X" → suggest similar code)
  - [ ] Confidence scoring (only suggest above threshold, default 0.85)
  - [ ] Integration with conversation tracker
  - [ ] Background suggestion generation
  - [ ] Tests: context analysis, pattern matching, confidence scoring
  - **Impact:** Proactive intelligence - surfaces relevant memories without explicit query
  - **Use case:** Claude detects user asking about authentication → suggests relevant memories/code
  - **Related to:** FEAT-028 (broader proactive context suggestions)
  - **Priority:** HIGH - major UX improvement

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

- [ ] **FEAT-036**: Project Archival & Reactivation System - Phase 2 (~1 week)
  - [ ] Index compression for archived projects
  - [ ] Bulk operations (auto-archive multiple projects)
  - [ ] Archive manifests with full snapshot
  - [ ] Automatic archival scheduler
  - [ ] Export to file / import from archive
  - **Impact:** Enables graceful project lifecycle, improves search performance
  - **Status:** Phase 1 complete (core states, tracking, CLI commands)

### 🟢 Tier 4: High-Value UX Quick Wins

**Low effort, high visibility improvements (minimal work for user-facing value)**

- [ ] **FEAT-038**: Data Export, Backup & Portability (~1-2 weeks) 🔥🔥
  - **Planning doc:** `planning_docs/STRATEGIC-001_long_term_product_evolution.md`
  - [ ] Export formats: JSON, Markdown, portable archive (.tar.gz)
  - [ ] Backup automation: daily/weekly schedules, retention policies
  - [ ] Import/restore: full restore, selective import, merge with conflict resolution
  - [ ] Export to Markdown knowledge base: human-readable memory export
  - [ ] Cloud sync (optional): Dropbox/Google Drive integration, encrypted
  - [ ] CLI commands: export, import, restore, backup config
  - [ ] Cross-machine workflow support
  - **Impact:** Prevents data loss and lock-in, enables migration, disaster recovery

- [ ] **UX-033**: Memory Tagging & Organization System (~1 week) 🔥🔥
  - **Planning doc:** `planning_docs/STRATEGIC-001_long_term_product_evolution.md`
  - [ ] Auto-tagging: extract keywords from content, infer categories
  - [ ] Hierarchical tags: language/python/async, architecture/microservices
  - [ ] Smart collections: auto-create thematic groups (e.g., "Python async patterns")
  - [ ] Tag-based search and filtering
  - [ ] Collection management: create, add, browse by theme
  - [ ] Manual tag curation and editing
  - **Impact:** Better discovery through smart organization

### ⚡ Tier 5: Performance Optimizations

**Core performance improvements**

- [ ] **PERF-002**: GPU acceleration (~1-2 weeks)
  - [ ] Use CUDA for embedding model
  - [ ] Target: 50-100x speedup
  - **Impact:** Massive speedup (requires GPU hardware)

### 🔧 Tier 6: UX Improvements (Lower Priority per User Preferences)

**Complete error UX group**

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

**Other UX enhancements**

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

### 🌐 Tier 7: Language Support Extensions

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

### 🚀 Tier 8: Advanced/Future Features

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

### 🔨 Tier 9: Refactoring & Tech Debt

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

### 📚 Tier 10: Documentation & Monitoring

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

## Notes

**Priority Legend:**
- 🔴 Tier 1 - Complete partially-finished initiatives + critical bugs first
- 🔥 Tier 2 - High-impact core functionality improvements
- 🟡 Tier 3 - Core functionality extensions
- 🟢 Tier 4+ - UX improvements, language support, future features (lower priority per user preferences)

**Time Estimates:**
- Items marked with time estimates have been scoped
- Unmarked items need investigation/scoping

**Dependencies:**
- Some items depend on external library updates
- GPU acceleration requires CUDA-capable hardware
- Multi-repo support may require architectural changes

**Planning Documents:**
- Check `planning_docs/` folder for detailed implementation plans
- File format: `{ID}_{description}.md`
- Create planning doc before starting complex items
