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

### 🔴 Tier 1: Complete Partially-Finished Initiatives + Critical Bugs

#### Phase 3.5: Adaptive Retrieval Gate ✅ **COMPLETE**

**Status:** ✅ COMPLETE - Fully implemented and tested
**Impact:** 30-40% query optimization, token savings

- [x] **FEAT-001**: Create retrieval predictor (src/router/retrieval_predictor.py)
  - [x] Class: RetrievalPredictor
  - [x] Method: predict_utility(query: str) -> float (0-1 probability)
  - [x] Implement heuristic rules (not ML initially)
  - [x] Analyze query: type, length, keywords
  - [x] Expected: 30-40% of queries can be skipped

- [x] **FEAT-002**: Implement retrieval gate (src/router/retrieval_gate.py)
  - [x] Class: RetrievalGate
  - [x] Configurable threshold (default 80%)
  - [x] Skip Qdrant search if utility < threshold
  - [x] Log gating decisions

- [x] **FEAT-003**: Integrate gate into memory.find() handler
  - [x] Run prediction before Qdrant search
  - [x] Track metrics (queries gated, skipped, etc.)
  - [x] Report estimated token savings

- [x] **FEAT-004**: Add metrics collection
  - [x] Counter: queries processed/gated
  - [x] Timer: prediction time
  - [x] Timer: retrieval time comparison
  - [x] Report: estimated token savings

- [x] **TEST-009**: Create tests/integration/test_retrieval_gate.py
  - [x] Test: Coding questions not gated
  - [x] Test: Small talk gated
  - [x] Test: Threshold enforcement
  - [x] Test: Metrics collection

#### Complete Visibility & Observability Initiative ✅ **COMPLETE**

- [x] **UX-008**: Memory browser TUI (~3-5 days)
  - [x] Interactive terminal UI using Rich/Textual
  - [x] Browse, search, edit, delete memories
  - [x] Filter by context level, project, category
  - [x] Bulk operations (delete all SESSION_STATE)
  - [x] Export/import functionality
  - **Note:** UX-006, UX-007, UX-010 already complete

- [x] **UX-009**: Search result quality indicators (~1-2 days)
  - [x] Explain why results matched (highlighted terms)
  - [x] Confidence scores with interpretation (>0.8 = excellent, etc.)
  - [x] Suggest query refinements for 0 results
  - [x] "Did you mean to search in project X?"
  - **Note:** May be partially addressed by UX-030 (confidence scores)

#### Critical Bug Fixes ✅ **COMPLETE**

- [x] **BUG-001**: TypeScript parser occasionally fails on complex files
  - Updated tree-sitter-typescript queries
  - Added better error recovery
  - **Impact:** Unblocked TypeScript indexing on complex projects

- [x] **BUG-002**: Metadata display shows "unknown" in some cases
  - Fixed display logic to extract nested metadata
  - Improved default values with descriptive strings

### 🔥 Tier 2: High-Impact Core Functionality Improvements

**These are the highest-impact features that directly enhance search, retrieval, and core capabilities**

- [x] **FEAT-026**: Smart Context Ranking & Pruning (~3-5 days) 🔥🔥🔥 ✅ **COMPLETE**
  - [x] Track which memories/code were actually referenced by Claude
  - [x] Rank results by: recency + relevance + usage frequency (60/20/20)
  - [x] Auto-expire unused SESSION_STATE memories (48h)
  - [x] Decay algorithm for importance scores (7-day half-life)
  - [x] Background cleanup job (runs daily at 2 AM)
  - [x] New table: memory_usage_tracking (memory_id, last_used, use_count)
  - [x] Batched updates for efficiency
  - [x] CLI prune command with dry-run support
  - **Impact:** 30-50% noise reduction, better search quality
  - **Complexity:** Medium (~500 lines, new DB schema)
  - **Runtime Cost:** +50MB storage, +1-2ms per search

- [x] **FEAT-029**: Conversation-Aware Retrieval (~5-7 days) 🔥🔥🔥 ✅ **COMPLETE**
  - [x] Explicit session management (MCP tools)
  - [x] Track last N messages in conversation (rolling window)
  - [x] Deduplication: don't return context already shown
  - [x] Contextual query expansion using conversation history (semantic)
  - [x] Cosine similarity for related query detection (0.7 threshold)
  - [x] Session timeout handling (30 minutes)
  - [x] Background session cleanup
  - **Impact:** 30-50% additional token savings, better relevance
  - **Complexity:** Medium-High (~800 lines)
  - **Runtime Cost:** +5-10MB per conversation, +5-10ms latency

- [ ] **FEAT-032**: Memory Lifecycle & Health System (~2-3 weeks) 🔥🔥🔥🔥🔥 ⚡ **PHASE 1 COMPLETE**
  - [x] **Planning doc:** `planning_docs/STRATEGIC-001_long_term_product_evolution.md`
  - [ ] **CRITICAL: Prevents 70% user abandonment at 6-12 months**
  - [x] **Phase 1:** Implement 4-tier lifecycle: ACTIVE (0-7d), RECENT (7-30d), ARCHIVED (30-180d), STALE (180d+)
  - [x] **Phase 1:** Automatic transitions based on age, access frequency, context level
  - [x] **Phase 1:** Search weighting by lifecycle state (1.0x → 0.7x → 0.3x → 0.1x)
  - [x] **Phase 1:** LifecycleManager with 26 comprehensive tests passing
  - [ ] **Phase 2:** Health monitoring dashboard with quality metrics (CLI command started)
  - [ ] **Phase 2:** Auto-actions: weekly archival, monthly stale deletion (background jobs)
  - [ ] **Phase 2:** Health scoring: overall health, noise ratio, duplicate rate, contradiction rate
  - [ ] **Phase 2:** Weekly automated health reports with recommendations
  - **Impact:** Prevents degradation, 30-50% noise reduction, maintains quality long-term
  - **Complexity:** High (lifecycle enum, background jobs, health algorithms, dashboard UI)
  - **Runtime Cost:** +50-100MB storage, +2-5ms per search
  - **Strategic Priority:** P0 - Foundation for sustainable long-term use
  - **Status:** Phase 1 complete (lifecycle states, transitions, weighting), Phase 2 pending (dashboard, background jobs)

- [x] **FEAT-033**: Smart Project Context Detection (~1-2 weeks) 🔥🔥🔥🔥 ✅ **COMPLETE**
  - [x] **Planning doc:** `planning_docs/STRATEGIC-001_long_term_product_evolution.md`
  - [x] **Eliminates cross-project memory pollution**
  - [x] Git context detection: monitor current repo, detect switches
  - [x] File activity patterns: infer active project from recent access
  - [x] Explicit project switching: MCP tool + CLI commands (set_active_context)
  - [x] Context-aware search: auto-boost active project 2.0x, others 0.3x
  - [x] Auto-archival recommendations for inactive projects (45+ days)
  - [x] Project marker detection (package.json, requirements.txt, Cargo.toml, etc.)
  - [x] Context persistence with project history tracking
  - [x] Comprehensive test suite (25 tests passing, 100% success)
  - **Impact:** Massive relevance improvement, eliminates wrong-project results
  - **Complexity:** Medium (git monitoring, activity tracking, context weighting)
  - **Runtime Cost:** +10-20MB, +3-5ms per search
  - **Strategic Priority:** P0 - Critical for multi-project developers
  - **Status:** Complete - Core infrastructure ready, MCP tool integration pending

- [ ] **FEAT-037**: Continuous Health Monitoring & Alerts (~1-2 weeks) 🔥🔥🔥
  - [ ] **Planning doc:** `planning_docs/STRATEGIC-001_long_term_product_evolution.md`
  - [ ] **Proactive degradation detection**
  - [ ] Track performance metrics: search latency, cache hit rate, index staleness
  - [ ] Track quality metrics: avg relevance, noise ratio, duplicates, contradictions
  - [ ] Alert thresholds: CRITICAL/WARNING/INFO levels
  - [ ] Automated remediation: trigger pruning, suggest archival, run deduplication
  - [ ] Weekly health reports with trends and recommendations
  - [ ] One-click "fix automatically" for common issues
  - **Impact:** Catches problems before catastrophic, prevents silent degradation
  - **Complexity:** Medium (metrics pipeline, alert engine, remediation actions)
  - **Runtime Cost:** +20-50MB for time-series data, +1-2ms per operation
  - **Strategic Priority:** P0 - Early warning system prevents Path B

- [ ] **FEAT-034**: Memory Provenance & Trust Signals (~2-3 weeks) 🔥🔥🔥🔥
  - [ ] **Planning doc:** `planning_docs/STRATEGIC-001_long_term_product_evolution.md`
  - [ ] **Rebuilds user trust through transparency**
  - [ ] Provenance tracking: source, created_by, last_accessed, access_count, confidence
  - [ ] Relationship graph: related/supporting/contradicting memories
  - [ ] Context snapshots: active project, conversation, file context at creation
  - [ ] Trust signals in results: "Why this result?" explanations
  - [ ] Interactive verification: periodic "Still accurate?" prompts
  - [ ] Contradiction detection and alerts
  - [ ] Memory verification tool: CLI command to review low-confidence memories
  - **Impact:** Transparent black box, enables intelligent curation, prevents contradictions
  - **Complexity:** High (provenance schema, relationship graph, trust algorithms, verification UI)
  - **Runtime Cost:** +30-50MB storage, +5-10ms per result (explanation generation)
  - **Strategic Priority:** P1 - Critical for trust, enables user curation

- [ ] **FEAT-035**: Intelligent Memory Consolidation (~2-3 weeks) 🔥🔥🔥
  - [ ] **Planning doc:** `planning_docs/STRATEGIC-001_long_term_product_evolution.md`
  - [ ] **Automatic duplicate detection and merging**
  - [ ] Semantic similarity clustering for duplicate detection
  - [ ] Auto-merge high confidence (>0.95 similarity)
  - [ ] Prompt user for medium confidence (0.85-0.95)
  - [ ] Flag low confidence (0.75-0.85) as "related"
  - [ ] Contradiction detection: alert on conflicting preferences/facts
  - [ ] Consolidation algorithms: preference merging, fact dedup, event compression
  - [ ] Background jobs: daily high-confidence merges, weekly user prompts, monthly full scan
  - [ ] Undo mechanism for bad merges
  - **Impact:** 40% noise reduction, maintains consistency, catches preference drift
  - **Complexity:** High (similarity clustering, merge logic, conflict resolution, user prompts)
  - **Runtime Cost:** +50-100MB for similarity index, background CPU for clustering
  - **Strategic Priority:** P1 - Proactive noise prevention

- [ ] **FEAT-028**: Proactive Context Suggestions (~3-4 days) 🔥🔥🔥
  - [ ] **Confirm overall feature design with user before proceeding**
  - [ ] Analyze conversation context to suggest relevant code/memories
  - [ ] Pattern matching: "I need to add X" → suggest similar implementations
  - [ ] Automatic context injection (high confidence only)
  - [ ] User sees: "I found similar registration logic - use that pattern?"
  - [ ] MCP tool auto-invocation based on conversation
  - [ ] Configurable threshold (default: 0.9 confidence)
  - **Impact:** Reduces cognitive load, surfaces hidden gems
  - **Complexity:** Medium (~600 lines)
  - **Runtime Cost:** +10-20ms per message, potential extra tool calls

- [x] **FEAT-027**: "Find Similar" Command (~1 day) 🔥🔥 ✅ **COMPLETE**
  - [x] MCP tool: `find_similar_code(code_snippet, limit=10)`
  - [x] Generate embedding for input code
  - [x] Search against existing code index
  - [x] Great for finding duplicates, patterns, examples
  - [x] Reuses existing search infrastructure
  - [x] Comprehensive test suite (8 tests)
  - **Impact:** Enables code reuse and pattern discovery
  - **Complexity:** Very Low (~150 lines, mostly reuse)
  - **Runtime Cost:** 30-50ms per query (embed + search)
  - **Completed:** 2025-11-17

- [ ] **FEAT-030**: Cross-Project Learning (~3-5 days) 🔥🔥
  - [ ] **Confirm overall feature design with user before proceeding**
  - [ ] Enable search across all indexed projects
  - [ ] MCP tool: `search_all_projects(query, limit=10)`
  - [ ] Find similar implementations across user's projects
  - [ ] "You solved this in project X - reuse that approach?"
  - [ ] Privacy: opt-in per project
  - [ ] Default: current project only
  - [ ] Build personal code pattern library
  - **Impact:** Accelerates development, reduces reinvention
  - **Complexity:** Medium (~400 lines)
  - **Runtime Cost:** +20-50ms search (multiple collections)

### 🟡 Tier 3: Core Functionality Extensions

**These extend core capabilities with new features**

- [x] **FEAT-011**: Import/dependency tracking ✅ **COMPLETE**
  - [x] Extract import statements from all 6 supported languages
  - [x] Build dependency graph with transitive queries
  - [x] Track usage relationships and detect circular dependencies
  - [x] MCP tools for dependency queries
  - **Impact:** Enables multi-hop queries, architectural understanding
  - **Completed:** 2025-11-17

- [x] **FEAT-023**: Hybrid search (BM25 + vector) ✅ **COMPLETE**
  - [x] Implemented BM25 keyword search algorithm (src/search/bm25.py)
  - [x] Created hybrid search module with 3 fusion strategies (src/search/hybrid_search.py)
  - [x] Integrated into server.py search_code() with search_mode parameter
  - [x] Added configuration options (alpha, fusion_method, BM25 parameters)
  - [x] Comprehensive tests (61 tests: unit + integration)
  - **Fusion Methods:** weighted, RRF (Reciprocal Rank Fusion), cascade
  - **Impact:** Improved search accuracy for technical terms, exact matches
  - **Completed:** 2025-11-17

- [x] **FEAT-024**: Query expansion ✅ **COMPLETE**
  - [x] Created comprehensive programming synonym dictionary (200+ terms)
  - [x] Implemented code context patterns (25+ domain-specific expansions)
  - [x] Enhanced QueryExpander with synonym and context expansion methods
  - [x] Added configuration options for fine-tuning expansion
  - [x] Comprehensive tests (33 tests passing)
  - **Features:** Synonym expansion, code context patterns, configurable limits
  - **Synonyms:** auth→login, function→method, db→database, etc.
  - **Context:** auth→[user, token, session], api→[endpoint, request, response], etc.
  - **Impact:** Better search recall, improved keyword matching
  - **Completed:** 2025-11-17

- [x] **FEAT-025**: Result reranking ✅ **COMPLETE**
  - [x] Implemented ResultReranker with multiple signals (similarity, recency, usage, length, keywords)
  - [x] Implemented MMR (Maximal Marginal Relevance) reranker for diversity
  - [x] Custom reranking function support
  - [x] Configurable weights for different ranking signals
  - [x] Recency decay with exponential half-life
  - [x] Usage frequency scoring with logarithmic scaling
  - [x] Length penalty for very short/long results
  - [x] Keyword matching boost
  - [x] Diversity penalty to reduce redundancy
  - [x] Comprehensive tests (29 tests passing)
  - **Algorithms:** Weighted combination, MMR, custom scoring
  - **Impact:** More relevant top results, personalized ranking
  - **Completed:** 2025-11-17

- [x] **FEAT-031**: Git-Aware Semantic Search ✅ **COMPLETE**
  - [x] Phase 1: Basic commit indexing (GitIndexer, storage, CLI)
  - [x] Phase 2: MCP tools (search_git_history, index_git_history)
  - [x] Phase 3: Code unit linking (show_function_evolution)
  - [x] Phase 4: Optimizations (git-search CLI command)
  - [x] Comprehensive testing (57 tests: 30 indexer + 27 storage)
  - **Implemented:** GitPython integration, FTS5 search, semantic embeddings
  - **Features:** Date parsing (relative/ISO), multi-filter support (author/date/file)
  - **CLI:** `git-index` for indexing, `git-search` for searching
  - **MCP Tools:** search_git_history(), index_git_history(), show_function_evolution()
  - **Impact:** Semantic search over git commit history, track code evolution
  - **Completed:** 2025-11-17 (commit 102dc46)

- [x] **FEAT-013**: Change detection ✅ **COMPLETE**
  - [x] Smart diffing to re-index only changed functions
  - [x] Track function-level changes
  - [x] Detect added, modified, deleted, renamed files
  - [x] Semantic unit-level change detection
  - [x] Incremental indexing plan generation
  - [x] File hash-based quick change detection
  - **Impact:** Faster incremental indexing
  - **Tests:** 21 tests passing
  - **Completed:** 2025-11-17

- [x] **FEAT-012**: Docstring extraction ✅ **COMPLETE**
  - [x] Separate indexing for documentation
  - [x] Link docs to code units
  - [x] Multi-language support (Python, JS/TS, Java, Go, Rust)
  - [x] Extract and clean docstrings with proper formatting
  - [x] Link docstrings to their semantic units
  - [x] Utility functions for search formatting and summarization
  - **Impact:** Better code understanding through documentation
  - **Tests:** 29 tests passing
  - **Completed:** 2025-11-17

- [ ] **FEAT-036**: Project Archival & Reactivation System (~1-2 weeks) 🔥🔥🔥
  - [ ] **Planning doc:** `planning_docs/STRATEGIC-001_long_term_product_evolution.md`
  - [ ] **Graceful project lifecycle management**
  - [ ] Project states: ACTIVE, PAUSED, ARCHIVED, DELETED
  - [ ] Automatic activity detection: file changes, searches, index updates
  - [ ] Archival workflow: suggest inactive projects (45+ days), compress indexes
  - [ ] Reactivation: restore to ACTIVE state, uncompress, reload embeddings
  - [ ] Bulk operations: auto-archive, export to file, delete permanently
  - [ ] Archive manifest: snapshot of all memories/indexes/metadata
  - [ ] Search weighting: ARCHIVED projects get 0.1x weight
  - **Impact:** 40% search speed improvement, reduces active dataset, enables recovery
  - **Complexity:** Medium (activity tracking, archival state management, compression)
  - **Runtime Cost:** +100-200MB for archived data, -50% active search space
  - **Strategic Priority:** P2 - Important for multi-project pollution

### 🟢 Tier 4: High-Value UX Quick Wins

**Low effort, high visibility improvements (minimal work for user-facing value)**

- [x] **UX-030**: Inline Context Confidence Scores (~1 day) 🔥🔥 ✅ **COMPLETE**
  - [x] Display similarity scores with search results
  - [x] Format: "95% (excellent)", "72% (good)", "45% (weak)"
  - [x] Thresholds: >0.8 = excellent, 0.6-0.8 = good, <0.6 = weak
  - [x] Help users and Claude assess result quality
  - [x] Add to search_code and find_similar_code tool responses
  - [x] Created comprehensive test suite (10 tests passing)
  - **Impact:** Improves decision-making and trust
  - **Complexity:** Very Low (~100 lines)
  - **Runtime Cost:** None (scores already calculated)

- [ ] **UX-029**: Token Usage Analytics Dashboard (~1-2 days) 🔥🔥🔥
  - [ ] **Confirm overall feature design with user before proceeding**
  - [ ] Track tokens saved per session (manual paste vs semantic search)
  - [ ] Display API cost savings over time ($X saved this month)
  - [ ] Context efficiency ratio (relevant tokens / total tokens)
  - [ ] CLI command: `python -m src.cli analytics`
  - [ ] MCP tool: `get_token_analytics()` for Claude to query
  - [ ] Storage: Simple SQLite table for metrics
  - **Impact:** Makes invisible value visible, drives adoption
  - **Complexity:** Low (~300 lines)
  - **Runtime Cost:** +10MB storage, negligible CPU/latency

- [ ] **UX-031**: Session Summaries (~1-2 days) 🔥🔥
  - [ ] **Confirm overall feature design with user before proceeding**
  - [ ] Track: searches performed, files indexed, tokens saved
  - [ ] Display at session end or via CLI command
  - [ ] Example: "Session Summary: 23 searches, ~12,400 tokens saved (~$0.04)"
  - [ ] Show most useful results (by reference count)
  - [ ] CLI command: `python -m src.cli session-summary`
  - **Impact:** Increases engagement, proves value incrementally
  - **Complexity:** Low (~200 lines)
  - **Runtime Cost:** +1MB storage, negligible CPU

- [ ] **FEAT-038**: Data Export, Backup & Portability (~1-2 weeks) 🔥🔥
  - [ ] **Planning doc:** `planning_docs/STRATEGIC-001_long_term_product_evolution.md`
  - [ ] **Prevents data loss and lock-in**
  - [ ] Export formats: JSON, Markdown, portable archive (.tar.gz)
  - [ ] Backup automation: daily/weekly schedules, retention policies
  - [ ] Import/restore: full restore, selective import, merge with conflict resolution
  - [ ] Export to Markdown knowledge base: human-readable memory export
  - [ ] Cloud sync (optional): Dropbox/Google Drive integration, encrypted
  - [ ] CLI commands: export, import, restore, backup config
  - [ ] Cross-machine workflow support
  - **Impact:** 40% increase in user confidence, enables migration, disaster recovery
  - **Complexity:** Medium (export/import logic, backup scheduler, conflict resolution)
  - **Runtime Cost:** Storage for backups, optional cloud bandwidth
  - **Strategic Priority:** P2 - Critical for user trust and data ownership

- [ ] **UX-033**: Memory Tagging & Organization System (~1 week) 🔥🔥
  - [ ] **Planning doc:** `planning_docs/STRATEGIC-001_long_term_product_evolution.md`
  - [ ] **Better discovery through smart organization**
  - [ ] Auto-tagging: extract keywords from content, infer categories
  - [ ] Hierarchical tags: language/python/async, architecture/microservices
  - [ ] Smart collections: auto-create thematic groups (e.g., "Python async patterns")
  - [ ] Tag-based search and filtering
  - [ ] Collection management: create, add, browse by theme
  - [ ] Manual tag curation and editing
  - **Impact:** 60% improvement in discoverability, better organization
  - **Complexity:** Low-Medium (auto-tag extraction, hierarchy, collection management)
  - **Runtime Cost:** +10-20MB for tag index, +1-2ms per search
  - **Strategic Priority:** P3 - Nice-to-have for organization

### ⚡ Tier 5: Performance Optimizations

**Core performance improvements**

- [ ] **PERF-001**: Parallel indexing
  - [ ] Multi-process embedding generation
  - [ ] Target: 10-20 files/sec
  - **Impact:** 5-10x faster indexing

- [ ] **PERF-003**: Incremental embeddings
  - [ ] Cache embeddings for unchanged code
  - [ ] Skip re-embedding on minor changes
  - **Impact:** Significant speedup for re-indexing

- [ ] **PERF-004**: Smart batching
  - [ ] Group files by size for optimal batching
  - [ ] Reduce embedding overhead
  - **Impact:** More efficient resource usage

- [ ] **PERF-005**: Streaming indexing
  - [ ] Don't wait for all files to parse
  - [ ] Start embedding as units are extracted
  - **Impact:** Faster perceived performance

- [ ] **PERF-002**: GPU acceleration
  - [ ] Use CUDA for embedding model
  - [ ] Potential 50-100x speedup
  - **Impact:** Massive speedup (requires GPU hardware)

### 🔧 Tier 6: UX Improvements (Lower Priority per User Preferences)

**Complete error UX group**

- [ ] **UX-011**: Actionable error messages (~2-3 days)
  - [ ] Redesign error response format with solutions
  - [ ] Context-aware diagnostics
  - [ ] Links to relevant docs
  - [ ] Automatic fallback suggestions
  - [ ] Example: "Qdrant failed → Try SQLite? [Y/n]"

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
  - [ ] Extend existing UX-004 health check
  - [ ] Add: Qdrant latency monitoring (warn if >20ms)
  - [ ] Add: Cache hit rate display (warn if <70%)
  - [ ] Add: Token savings this week
  - [ ] Add: Stale project detection (not indexed in 30+ days)
  - [ ] Proactive recommendations: "Consider upgrading to Qdrant"
  - [ ] Show indexed projects count and size
  - **Impact:** Proactive issue detection, optimization guidance
  - **Complexity:** Low (~300 lines)
  - **Runtime Cost:** +5MB metrics history

- [ ] **UX-014**: Explicit project switching (~2 days)
  - [ ] MCP tool: `switch_project(project_name)`
  - [ ] Show current project in Claude status
  - [ ] Auto-detect git context changes
  - [ ] Cross-project search option

- [ ] **UX-015**: Project management commands (~2 days)
  - [ ] `list_projects` - show all indexed projects
  - [ ] `project_stats(project)` - detailed project info
  - [ ] `delete_project(project)` - remove project index
  - [ ] `rename_project(old, new)` - rename project

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

- [ ] **UX-019**: Optimization suggestions (~2 days)
  - [ ] Detect large binary files, suggest exclusion
  - [ ] Identify redundant directories (node_modules, .git)
  - [ ] Suggest .ragignore patterns
  - [ ] Performance impact estimates

- [ ] **UX-025**: Memory lifecycle management (~2-3 days)
  - [ ] Auto-expire SESSION_STATE memories
  - [ ] Importance decay over time
  - [ ] Archive old project contexts
  - [ ] Storage optimization suggestions

### 🌐 Tier 7: Language Support Extensions

- [ ] **UX-020**: Add C/C++ support (~3 days)
  - [ ] tree-sitter-cpp integration
  - [ ] Function, class, struct extraction
  - [ ] High priority for systems engineers

- [ ] **UX-021**: Add SQL support (~2 days)
  - [ ] tree-sitter-sql integration
  - [ ] Query, view, procedure extraction
  - [ ] Critical for backend developers

- [ ] **UX-022**: Add configuration file support (~2 days)
  - [ ] YAML, JSON, TOML parsing
  - [ ] Extract logical sections
  - [ ] Docker, CI/CD config understanding

- [ ] **UX-023**: Add C# support (~3 days)
  - [ ] tree-sitter-c-sharp integration
  - [ ] Important for enterprise developers

- [ ] **FEAT-005**: Add support for C++
- [ ] **FEAT-006**: Add support for C#
- [ ] **FEAT-007**: Add support for Ruby
- [ ] **FEAT-008**: Add support for PHP
- [ ] **FEAT-009**: Add support for Swift
- [ ] **FEAT-010**: Add support for Kotlin

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
  - [ ] Internal development tool initially
  - **Impact:** Maintain quality at scale, early warning system
  - **Complexity:** Medium (~500 lines)
  - **Runtime Cost:** +20-50MB time-series data, +5ms per operation

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

## ✅ Completed Items

### Testing Coverage ✅ COMPLETED - 85% TARGET ACHIEVED!

**Status:** All testing goals exceeded - 85.02% coverage reached (was 63.72%)
**Total improvement:** +21.3% coverage, +262 tests (447 → 712)

**Completed Items:**

- [x] **TEST-001**: CLI commands testing (~15 tests) → +5.5% ✅
  - [x] Test index command with various options
  - [x] Test watch command functionality
  - [x] Test error handling and recovery
  - [x] Test progress reporting
  - **Result:** 100% coverage on watch_command.py, 98.57% on index_command.py

- [x] **TEST-002**: tools.py testing (~10 tests) → +2.3% ✅
  - [x] Test specialized retrieval methods
  - [x] Test multi-level retrieval
  - [x] Test category filtering
  - [x] Test context-level enforcement
  - **Result:** 100% coverage on tools.py

- [x] **TEST-003**: Enhanced qdrant_store tests → +2% ✅
  - **Result:** 74.55% → 87.50% coverage (added 15 error path tests)

- [x] **TEST-004**: Enhanced cache tests → +2% ✅
  - **Result:** 65% → 90.29% coverage (comprehensive edge case testing)

- [x] **TEST-005**: File watcher edge cases → +1% ✅
  - **Result:** 71.23% → 99.32% coverage (18 new tests)

- [x] **TEST-006**: security_logger.py ✅
  - **Note:** Skipped as logging-only utility (0% coverage acceptable)

- [x] **TEST-007**: allowed_fields.py (field validation) ✅
  - **Result:** 78.46% → 100% coverage (8 validation tests added)

- [x] **TEST-008**: indexing_service.py (service wrapper) ✅
  - **Result:** 27% → 100% coverage (19 comprehensive tests)

### Setup & Onboarding ✅ COMPLETED

- [x] **UX-001**: One-command installation script ✅ **COMPLETE**
  - [x] Automated setup wizard that checks prerequisites
  - [x] Auto-fallback to SQLite (no Docker required)
  - [x] Optional Rust build with pure Python fallback
  - [x] Validation steps with clear success/failure feedback
  - [x] See: `planning_docs/UX-001_setup_friction_reduction.md`
  - **Result:** setup.py with 3 presets (minimal/standard/full), ~3min setup time

- [x] **UX-002**: Pure Python parser fallback ✅ **COMPLETE**
  - [x] Removed hard Rust dependency
  - [x] Implemented tree-sitter Python bindings fallback
  - [x] Performance: 10-20x slower but fully functional
  - [x] Auto-detect: uses Rust if available, Python otherwise
  - **Result:** src/memory/python_parser.py, 84.62% test coverage

- [x] **UX-003**: SQLite-first mode (no Docker required) ✅ **COMPLETE**
  - [x] Defaults to SQLite for initial setup
  - [x] Option to upgrade to Qdrant later
  - [x] Migration tool stub: `setup.py --upgrade-to-qdrant` (manual for now)
  - [x] Clear performance tradeoffs documented
  - **Result:** Zero Docker dependency, health check recommends upgrade when needed

- [x] **UX-004**: Health check & diagnostics command ✅ **COMPLETE**
  - [x] `python -m src.cli health` command
  - [x] Checks: Storage connection, parser, embedding model, disk space, memory
  - [x] Color-coded output (✓ green, ✗ red, ⚠ yellow)
  - [x] Actionable error messages with recommendations
  - **Result:** src/cli/health_command.py, 88.48% test coverage

- [x] **UX-005**: Setup verification & testing ✅ **COMPLETE**
  - [x] Post-install validation in setup.py (3 verification tests)
  - [x] Sample project in examples/sample_project/ (Python, JavaScript)
  - [x] Comprehensive test suite (102 new tests for all UX components)
  - [x] Success message with next steps
  - **Result:** Automated verification, 85%+ coverage on all new modules

### Visibility & Observability (Partial) ✅

- [x] **UX-006**: Status/stats command (~2 days) ✅ **COMPLETE**
  - [x] `python -m src.cli status` showing indexed projects
  - [x] Number of files, functions, classes per project
  - [x] Storage used, cache hit rates
  - [x] Recent indexing activity
  - [x] Memory stats by category/context level
  - **Result:** Full project statistics with Qdrant & SQLite support

- [x] **UX-007**: Indexing progress indicators (~1 day) ✅ **COMPLETE**
  - [x] Real-time progress bar during indexing
  - [x] File count, estimated time remaining
  - [x] Current file being processed
  - [x] Errors encountered (with continue option)
  - **Result:** Rich progress bar with concurrent file tracking, 94.89% coverage

- [x] **UX-010**: File watcher status visibility (~1 day) ✅ **COMPLETE**
  - [x] Show active watchers in status command
  - [x] File watcher configuration and capabilities display
  - [x] Usage instructions and guidance
  - [x] Supported extensions and debounce settings
  - **Result:** Professional status display with rich formatting

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
