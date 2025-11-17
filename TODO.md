# TODO

## ID System
Each item has a unique ID for tracking and association with planning documents in `planning_docs/`.
Format: `{TYPE}-{NUMBER}` where TYPE = FEAT|BUG|TEST|DOC|PERF|REF|UX

## Current Sprint

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

### Code Quality

**Deferred from Refactoring Sprint**

- [ ] **REF-001**: Fix Async/Await Patterns (~1 hour)
  - Requires profiling first
  - Optimize async patterns for better performance

- [ ] **REF-002**: Add Structured Logging (~1.5 hours)
  - Requires logging format decision
  - Implement consistent logging across modules

- [ ] **REF-003**: Split Validation Module (~2 hours)
  - Requires careful refactoring for circular imports
  - Separate validation concerns

### Minor Issues (Non-Blocking)

- [ ] **REF-004**: Update datetime.utcnow() to datetime.now(UTC)
  - Low priority, cosmetic fix for deprecation warnings

- [ ] **REF-005**: Update to Pydantic v2 ConfigDict style
  - Low priority, modernize configuration

- [ ] **REF-006**: Update Qdrant search() to query_points()
  - Low priority, will be required in future Qdrant versions

## User Experience Improvements

### 🔴 Critical - Setup & Onboarding (Highest Impact) ✅ COMPLETED

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

### 🟡 High Priority - Visibility & Observability

- [ ] **UX-006**: Status/stats command (~2 days)
  - [ ] `python -m src.cli status` showing indexed projects
  - [ ] Number of files, functions, classes per project
  - [ ] Storage used, cache hit rates
  - [ ] Recent indexing activity
  - [ ] Memory stats by category/context level

- [ ] **UX-007**: Indexing progress indicators (~1 day)
  - [ ] Real-time progress bar during indexing
  - [ ] File count, estimated time remaining
  - [ ] Current file being processed
  - [ ] Errors encountered (with continue option)

- [ ] **UX-008**: Memory browser TUI (~3-5 days)
  - [ ] Interactive terminal UI using Rich/Textual
  - [ ] Browse, search, edit, delete memories
  - [ ] Filter by context level, project, category
  - [ ] Bulk operations (delete all SESSION_STATE)
  - [ ] Export/import functionality

- [ ] **UX-009**: Search result quality indicators (~1-2 days)
  - [ ] Explain why results matched (highlighted terms)
  - [ ] Confidence scores with interpretation (>0.8 = excellent, etc.)
  - [ ] Suggest query refinements for 0 results
  - [ ] "Did you mean to search in project X?"

- [ ] **UX-010**: File watcher status visibility (~1 day)
  - [ ] Show active watchers in status command
  - [ ] MCP tool to start/stop file watcher
  - [ ] Notifications when reindexing occurs
  - [ ] Watch statistics (files changed, reindex count)

### 🟡 High Priority - Error UX & Recovery

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

### 🟢 Medium Priority - Project & Context Management

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

### 🟢 Medium Priority - Performance Visibility

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

### 🟢 Medium Priority - Language Support Gaps

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

### ⚪ Low Priority - Advanced Features

- [ ] **UX-024**: Usage feedback mechanisms (~2-3 days)
  - [ ] "Was this helpful?" for search results
  - [ ] Learning from user behavior
  - [ ] Query refinement suggestions
  - [ ] Result quality metrics

- [ ] **UX-025**: Memory lifecycle management (~2-3 days)
  - [ ] Auto-expire SESSION_STATE memories
  - [ ] Importance decay over time
  - [ ] Archive old project contexts
  - [ ] Storage optimization suggestions

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

## Phase 3.5: Adaptive Retrieval Gate (Optional Optimization)

### Intelligent Retrieval Skipping

- [ ] **FEAT-001**: Create retrieval predictor (src/router/retrieval_predictor.py)
  - [ ] Class: RetrievalPredictor
  - [ ] Method: predict_utility(query: str) -> float (0-1 probability)
  - [ ] Implement heuristic rules (not ML initially)
  - [ ] Analyze query: type, length, keywords
  - [ ] Expected: 30-40% of queries can be skipped

- [ ] **FEAT-002**: Implement retrieval gate (src/router/retrieval_gate.py)
  - [ ] Class: RetrievalGate
  - [ ] Configurable threshold (default 80%)
  - [ ] Skip Qdrant search if utility < threshold
  - [ ] Log gating decisions

- [ ] **FEAT-003**: Integrate gate into memory.find() handler
  - [ ] Run prediction before Qdrant search
  - [ ] Track metrics (queries gated, skipped, etc.)
  - [ ] Report estimated token savings

- [ ] **FEAT-004**: Add metrics collection
  - [ ] Counter: queries processed/gated
  - [ ] Timer: prediction time
  - [ ] Timer: retrieval time comparison
  - [ ] Report: estimated token savings

- [ ] **TEST-009**: Create tests/integration/test_retrieval_gate.py
  - [ ] Test: Coding questions not gated
  - [ ] Test: Small talk gated
  - [ ] Test: Threshold enforcement
  - [ ] Test: Metrics collection

## Future Enhancements

### Language Support

- [ ] **FEAT-005**: Add support for C++
- [ ] **FEAT-006**: Add support for C#
- [ ] **FEAT-007**: Add support for Ruby
- [ ] **FEAT-008**: Add support for PHP
- [ ] **FEAT-009**: Add support for Swift
- [ ] **FEAT-010**: Add support for Kotlin

### Code Intelligence

- [ ] **FEAT-011**: Import/dependency tracking
  - [ ] Extract import statements
  - [ ] Build dependency graph
  - [ ] Track usage relationships

- [ ] **FEAT-012**: Docstring extraction
  - [ ] Separate indexing for documentation
  - [ ] Link docs to code units

- [ ] **FEAT-013**: Change detection
  - [ ] Smart diffing to re-index only changed functions
  - [ ] Track function-level changes

- [ ] **FEAT-014**: Semantic refactoring
  - [ ] Find all usages semantically
  - [ ] Suggest refactoring opportunities

- [ ] **FEAT-015**: Code review features
  - [ ] LLM-powered suggestions based on patterns
  - [ ] Identify code smells

### Performance Optimizations

- [ ] **PERF-001**: Parallel indexing
  - [ ] Multi-process embedding generation
  - [ ] Target: 10-20 files/sec

- [ ] **PERF-002**: GPU acceleration
  - [ ] Use CUDA for embedding model
  - [ ] Potential 50-100x speedup

- [ ] **PERF-003**: Incremental embeddings
  - [ ] Cache embeddings for unchanged code
  - [ ] Skip re-embedding on minor changes

- [ ] **PERF-004**: Smart batching
  - [ ] Group files by size for optimal batching
  - [ ] Reduce embedding overhead

- [ ] **PERF-005**: Streaming indexing
  - [ ] Don't wait for all files to parse
  - [ ] Start embedding as units are extracted

### Deployment & Operations

- [ ] **FEAT-016**: Auto-indexing
  - [ ] Automatically index on project open
  - [ ] Background indexing for large projects

- [ ] **FEAT-017**: Multi-repository support
  - [ ] Index across multiple repositories
  - [ ] Cross-repo code search

- [ ] **FEAT-018**: Query DSL
  - [ ] Advanced filters (by file pattern, date, author, etc.)
  - [ ] Complex query expressions

- [ ] **FEAT-019**: IDE Integration
  - [ ] VS Code extension for instant code search
  - [ ] IntelliJ plugin
  - [ ] Vim/Neovim integration

### Analytics & Monitoring

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

### Advanced Retrieval

- [ ] **FEAT-023**: Hybrid search (BM25 + vector)
  - [ ] Combine keyword and semantic search
  - [ ] Better recall for specific terms

- [ ] **FEAT-024**: Query expansion
  - [ ] Expand queries with synonyms
  - [ ] Use code context for better results

- [ ] **FEAT-025**: Result reranking
  - [ ] ML-based relevance scoring
  - [ ] Personalized ranking based on usage

### Documentation & User Experience

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

## Bug Fixes & Maintenance

### Known Issues

- [ ] **BUG-001**: TypeScript parser occasionally fails on complex files
  - Need to update tree-sitter-typescript
  - Add better error recovery

- [ ] **BUG-002**: Metadata display shows "unknown" in some cases
  - Low priority, cosmetic issue
  - Fix display logic in search results

### Tech Debt

- [ ] **REF-007**: Consolidate two server implementations
  - Merge old mcp_server.py with new src/core/
  - Unified architecture

- [ ] **REF-008**: Remove deprecated API usage
  - Update to latest Qdrant APIs
  - Update to latest MCP SDK

## Documentation Updates

- [ ] **DOC-004**: Update README with code search examples
- [ ] **DOC-005**: Add performance tuning guide for large codebases
- [ ] **DOC-006**: Create troubleshooting guide for common parser issues
- [ ] **DOC-007**: Document best practices for project organization

## Notes

**Priority Legend:**
- 🔴 Critical - Blocks production use
- 🟡 High - Significantly improves functionality
- 🟢 Medium - Nice to have
- ⚪ Low - Future consideration

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