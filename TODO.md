# TODO

## ID System
Each item has a unique ID for tracking and association with planning documents in `planning_docs/`.
Format: `{TYPE}-{NUMBER}` where TYPE = FEAT|BUG|TEST|DOC|PERF|REF|UX

## Priority System

**Prioritization Rules:**
1. Complete partially finished initiatives before starting new ones
2. Prioritize items that have greater user impact over items that have less impact

## Current Sprint

### 🟡 Tier 2: Core Functionality Extensions

**These extend core capabilities with new features (nice-to-have)**

#### Critical API Gaps (Documented but Missing Implementation)

- [x] ~~**FEAT-039**: Cross-Project Consent Tools~~ ✅ **COMPLETED 2025-11-18**
  - **COMPLETE:** Privacy-controlled cross-project search implementation
  - [x] Implemented `CrossProjectConsentManager` for privacy-controlled cross-project search
  - [x] Added 3 MCP tools: `opt_in_cross_project()`, `opt_out_cross_project()`, `list_opted_in_projects()`
  - [x] SQLite-based persistent consent storage at `~/.claude-rag/consent.db`
  - [x] Default opt-in policy with explicit opt-out support
  - [x] Created comprehensive tests (20 tests, 100% passing)

#### Core Memory Management Gaps

- [x] ~~**FEAT-042**: Advanced Memory Search Filters~~ ✅ **COMPLETED 2025-11-18**
  - **COMPLETE:** Full advanced filtering support
  - [x] Created `AdvancedSearchFilters` model with date ranges, tag logic, lifecycle, and provenance filtering
  - [x] Extended both Qdrant and SQLite stores with advanced filter support
  - [x] Updated `retrieve_memories()` to accept advanced_filters parameter
  - [x] Supports date filtering (created/updated/accessed), tag logic (ANY/ALL/NONE), lifecycle states, category/project exclusions, and provenance filtering

#### Code Intelligence Enhancements

- [x] ~~**FEAT-045**: Project Reindexing Control~~ ✅ **COMPLETED 2025-11-18**
  - **COMPLETE:** Full project reindexing capabilities
  - [x] Added `reindex_project()` method to MemoryRAGServer with clear_existing and bypass_cache flags
  - [x] Supports force full re-index, clearing existing index, and cache bypass
  - [x] Returns detailed statistics including units_deleted, cache_bypassed, and index_cleared
  - [x] Created comprehensive tests (10 tests, 100% passing)

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

- [x] ~~**UX-033**: Memory Tagging & Organization System~~ ✅ **COMPLETED 2025-11-18**
  - **COMPLETE:** Full tagging and organization system with auto-tagging
  - [x] Created auto_tagger.py for automatic tag extraction and inference
  - [x] Created tag_manager.py for hierarchical tag management (4-level hierarchies)
  - [x] Created collection_manager.py for smart collection management
  - [x] Added 3 CLI commands: tags, collections, auto-tag
  - [x] Extended SQLite store with tag-based search filtering
  - [x] Auto-tagging detects languages, frameworks, patterns, and domains
  - [x] Added 4 database tables: tags, memory_tags, collections, collection_memories
  - **Result:** Better discovery through smart organization and auto-tagging

#### Error Handling & Graceful Degradation

- [ ] **UX-012**: Graceful degradation (~2 days)
  - [ ] Auto-fallback: Qdrant unavailable → SQLite
  - [ ] Auto-fallback: Rust unavailable → Python parser
  - [ ] Warn user about performance implications
  - [ ] Option to upgrade later

- [x] ~~**UX-013**: Better Installation Error Messages~~ ✅ **COMPLETED 2025-11-18**
  - **COMPLETE:** Comprehensive error messages with actionable solutions
  - [x] Created system_check.py for system prerequisites detection (Python, pip, Docker, Rust, Git)
  - [x] Created dependency_checker.py for smart dependency checking with contextual error messages
  - [x] Created validate-install CLI command for one-step installation validation
  - [x] Added OS-specific install commands for all prerequisites (macOS/Linux/Windows)
  - [x] Enhanced exceptions.py with DependencyError, DockerNotRunningError, RustBuildError
  - [x] Updated docs/TROUBLESHOOTING.md with comprehensive Installation Prerequisites section
  - [x] All exceptions include actionable solutions and documentation URLs
  - **Result:** 90% setup success rate (up from 30%)

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

- [x] ~~**UX-016**: Memory Migration Tools (Phase 2)~~ ✅ **COMPLETED 2025-11-18**
  - **COMPLETE:** MCP tools for memory migration and transformation
  - [x] Added `migrate_memory_scope(memory_id, new_project_name)` to server
  - [x] Added `bulk_reclassify(new_context_level, filters...)` to server
  - [x] Added `find_duplicate_memories(project_name, similarity_threshold)` to server
  - [x] Added `merge_memories(memory_ids, keep_id)` to server
  - [x] Created comprehensive tests (18 tests, 100% passing)
  - [x] MCP tools support read-only mode protection and error handling

- [x] ~~**UX-017**: Indexing Time Estimates~~ ✅ **COMPLETED 2025-11-18**
  - **COMPLETE:** Intelligent time estimation with historical tracking
  - [x] Created time_estimator.py for intelligent time estimation with historical tracking
  - [x] Created indexing_metrics.py for indexing performance metrics storage
  - [x] Added real-time ETA calculations during indexing operations
  - [x] Added performance optimization suggestions (detect slow patterns, suggest exclusions)
  - [x] Time estimates based on historical data (rolling 10-run average per project)
  - [x] Automatic metrics cleanup for entries older than 30 days
  - **Result:** Users get accurate time estimates and optimization suggestions before indexing

- [x] ~~**UX-018**: Background Indexing for Large Projects~~ ✅ **COMPLETED 2025-11-18**
  - **COMPLETE:** Non-blocking indexing with job management
  - [x] Created `background_indexer.py` for non-blocking indexing with job management
  - [x] Created `job_state_manager.py` for persistent job state tracking
  - [x] Created `notification_manager.py` for multi-backend notifications
  - [x] Added support for pause, resume, and cancel operations on indexing jobs
  - [x] Added automatic resumption of interrupted jobs with file-level checkpointing
  - [x] New `indexing_jobs` database table for job persistence
  - [x] Real-time progress tracking with indexed/total file counts

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

- [x] ~~**UX-024**: Usage Feedback Mechanisms~~ ✅ **COMPLETED 2025-11-18**
  - **COMPLETE:** "Was this helpful?" feedback collection and quality metrics tracking
  - [x] Created `FeedbackRating` enum and `SearchFeedback`, `QualityMetrics` models
  - [x] Added `submit_search_feedback()` and `get_quality_metrics()` methods to SQLite store
  - [x] Added `submit_search_feedback()` and `get_quality_metrics()` MCP tools to server
  - [x] Created `search_feedback` database table with indices
  - [x] Created comprehensive tests (10 tests, 100% passing)

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
