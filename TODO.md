# TODO

## 🚨 CRITICAL BUGS FOUND IN E2E TESTING (2025-11-20)

- [x] **BUG-015**: Health Check False Negative for Qdrant ✅ **FIXED** (2025-11-21)
  - **Component:** `src/cli/health_command.py:143`
  - **Issue:** Health check reports Qdrant as unreachable even when functional
  - **Root Cause:** Using wrong endpoint `/health` instead of `/`
  - **Fix:** Already using correct `/` endpoint with JSON validation
  - **Verification:** `curl http://localhost:6333/` returns version info successfully
  - **Status:** Code was already correct, bug may have been user-specific or already fixed

### BUG-016: list_memories Returns Incorrect Total Count ⚠️ MEDIUM
**Component:** Memory management API
**Issue:** `list_memories()` returns `total: 0` when memories exist in results array
**Impact:** Breaks pagination, incorrect analytics
**Fix:** Update method to properly count and return total

### BUG-018: Memory Retrieval Not Finding Recently Stored Memories ⚠️ HIGH
**Component:** Semantic search / memory retrieval
**Issue:** Memories stored via `store_memory()` not immediately retrievable via `retrieve_memories()`
**Impact:** Core functionality appears broken, poor user experience
**Investigation Required:** Check embedding timing, vector store indexing delay, similarity threshold

- [x] **BUG-019**: Docker Container Shows "Unhealthy" Despite Working ✅ **FIXED**
  - **Error:** `docker ps` shows Qdrant as "(unhealthy)", health check exits with -1
  - **Root Cause:** Health check uses `curl` command which doesn't exist in Qdrant container
  - **Location:** `docker-compose.yml` and `planning_docs/TEST-006_docker_compose.yml`
  - **Fix:** Changed health check from `curl -f http://localhost:6333/` to TCP socket test: `timeout 1 bash -c 'cat < /dev/null > /dev/tcp/localhost/6333' || exit 1`
  - **Result:** Container now shows "(healthy)" status, ExitCode: 0, FailingStreak: 0

### BUG-020: Inconsistent Return Value Structures ⚠️ MEDIUM
**Component:** API design consistency
**Issue:** Different methods use different success indicators:
  - `delete_memory`: `{"status": "success"}`
  - Expected by tests: `{"success": true}`
**Impact:** Confusing API, error-prone client code
**Recommendation:** Standardize on consistent return structure

- [x] **BUG-021**: PHP Parser Initialization Warning ✅ **FIXED** (2025-11-21)
  - **Component:** `src/memory/python_parser.py`
  - **Issue:** Warning: "Failed to initialize php parser"
  - **Root Cause:** DUPLICATE of BUG-025 - optional language imports breaking entire parser
  - **Fix:** Resolved by BUG-025 fix (lazy imports) - optional languages now skipped gracefully

- [x] **BUG-022**: Code Indexer Extracts Zero Semantic Units ✅ **RESOLVED** (2025-11-21)
  - **Component:** Code indexing / parsing
  - **Issue:** `index_codebase()` extracts 0 semantic units
  - **Root Cause:** BUG-025 broke parser initialization
  - **Fix:** Resolved by fixing BUG-025
  - **Verification:** Parser now extracts functions/classes correctly (tested with 2 units from test file)

- [x] **BUG-024**: Tests Importing Removed Modules ✅ **FIXED** (2025-11-21)
  - **Error:** 11 test files fail collection with `ModuleNotFoundError`
  - **Root Cause:** REF-010/011 removed sqlite_store/retrieval_gate modules but tests not updated
  - **Impact:** 11 test files blocked, ~150+ tests couldn't run
  - **Fix:** Updated all tests to use QdrantMemoryStore, deleted obsolete tests
  - **Result:** 2677 tests now collect successfully (up from 2569 with 11 errors)
  - **Files:** See `planning_docs/BUG-024-026_execution_summary.md`

- [x] **BUG-025**: PythonParser Fails Due to Optional Language Imports ✅ **FIXED** (2025-11-21)
  - **Error:** Parser initialization fails if ANY optional language missing
  - **Root Cause:** Module-level import of ALL languages - if any missing, entire parser disabled
  - **Impact:** Parser fallback mode completely broken, related to BUG-022
  - **Fix:** Lazy import individual language parsers, skip missing languages gracefully
  - **Result:** Parser initializes with 6 installed languages, skips 4 optional ones

- [x] **BUG-026**: Test Helper Classes Named "Test*" ✅ **FIXED** (2025-11-21)
  - **Warning:** `PytestCollectionWarning: cannot collect test class 'TestNotificationBackend'`
  - **Root Cause:** Helper class name starts with "Test" and has `__init__` constructor
  - **Fix:** Renamed `TestNotificationBackend` → `MockNotificationBackend` in 2 files
  - **Result:** Warnings removed

**Full E2E Test Report:** See `E2E_TEST_REPORT.md` for detailed findings
**Bug Hunt Report:** See `planning_docs/BUG-HUNT_2025-11-21_comprehensive_report.md`
**Fix Execution:** See `planning_docs/BUG-024-026_execution_summary.md`
**Full E2E Test Plan:** See `planning_docs/TEST-006_e2e_test_plan.md`, `planning_docs/TEST-006_e2e_bug_tracker.md`, and `planning_docs/TEST-006_e2e_testing_guide.md` for comprehensive manual testing documentation

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

- [x] **BUG-027**: Incomplete SQLite Removal (REF-010) ✅ **FIXED** (2025-11-21)
  - **Error:** 185 ERROR tests with "Input should be 'qdrant'" validation errors
  - **Impact:** 16+ test files broken, 185 runtime test errors
  - **Root Cause:** REF-010 removed SQLite backend but tests still try to use it
  - **Location:** Config validation in `src/config.py:19` only accepts "qdrant"
  - **Fix:** Updated 12 test files to use storage_backend="qdrant", removed sqlite_path parameters
  - **Result:** All integration and unit tests now use Qdrant backend correctly
  - **See:** planning_docs/BUG-HUNT_2025-11-21_runtime_failures.md

- [x] **BUG-028**: Dict vs Object Type Mismatch in Health Components ✅ **FIXED** (2025-11-21)
  - **Error:** "'dict' object has no attribute 'content'" and "'dict' object has no attribute 'created_at'"
  - **Impact:** 8+ FAILED tests, health monitoring system broken
  - **Root Cause:** get_all_memories() returns List[Dict] but consumers expect List[MemoryUnit] objects
  - **Location:** src/memory/health_scorer.py:240, src/memory/health_jobs.py:168
  - **Fix:** Changed all memory.attribute to memory['attribute'], added enum conversions and datetime parsing
  - **Result:** Health monitoring system now works correctly with dictionary access
  - **See:** planning_docs/BUG-HUNT_2025-11-21_runtime_failures.md

- [x] **BUG-029**: Category Changed from "context" to "code" ✅ **FIXED** (2025-11-21)
  - **Error:** "AssertionError: assert 'code' == 'context'"
  - **Impact:** 2+ FAILED tests, outdated documentation
  - **Root Cause:** Code indexing category changed to MemoryCategory.CODE but tests/comments not updated
  - **Location:** tests/integration/test_indexing_integration.py:133, src/core/server.py:3012 comment
  - **Fix:** Updated test assertions to expect "code", updated outdated comment
  - **Result:** All indexing tests now pass with correct category expectations
  - **See:** planning_docs/BUG-HUNT_2025-11-21_runtime_failures.md

- [x] **BUG-030**: Invalid Qdrant Point IDs in Test Fixtures ✅ **FIXED** (2025-11-21)
  - **Error:** "400 Bad Request: value test-1 is not a valid point ID"
  - **Impact:** 4+ ERROR tests in backup/export functionality
  - **Root Cause:** Tests use string IDs like "test-1" but Qdrant requires integers or UUIDs
  - **Location:** tests/unit/test_backup_export.py:30, 44
  - **Fix:** Replaced "test-1", "test-2" with str(uuid.uuid4())
  - **Result:** Test fixtures now use valid UUID format for Point IDs
  - **See:** planning_docs/BUG-HUNT_2025-11-21_runtime_failures.md

- [x] **BUG-031**: Test Collection Count Discrepancy (Documentation) ✅ **FIXED** (2025-11-21)
  - **Issue:** Test count varies between runs (documented: 2,723, actual: 2,677-2,744)
  - **Impact:** Misleading documentation
  - **Location:** CLAUDE.md metrics section
  - **Fix:** Updated CLAUDE.md to reflect ~2,740 tests with note about environment variability
  - **Result:** Documentation now accurately reflects test count range
  - **See:** planning_docs/BUG-HUNT_2025-11-21_runtime_failures.md

- [x] **BUG-032**: Coverage Metric Discrepancy (Documentation) ✅ **FIXED** (2025-11-21)
  - **Issue:** CLAUDE.md claims 67% coverage, actual is 59.6% overall / 71.2% core modules
  - **Impact:** Misleading documentation (but core modules meet target)
  - **Location:** CLAUDE.md Current State section
  - **Fix:** Updated coverage metrics with accurate breakdown (59.6% overall, 71.2% core modules)
  - **Result:** Documentation now clearly explains overall vs core module coverage
  - **See:** planning_docs/BUG-HUNT_2025-11-21_runtime_failures.md

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

- [ ] **FEAT-055**: Git Storage and History Search (~1-2 weeks) 🔥
  - [ ] Implement `store_git_commits()` method in QdrantMemoryStore
  - [ ] Implement `store_git_file_changes()` method
  - [ ] Implement `search_git_commits()` - Semantic search over commit history
  - [ ] Implement `get_git_commit()` - Retrieve specific commit
  - [ ] Implement `get_commits_by_file()` - Get commits affecting a file
  - [ ] Index git history during codebase indexing
  - [ ] Support semantic search across commit messages and diffs
  - **Impact:** Enable semantic search over project history, find commits by intent
  - **Tests:** 27 tests currently skipped (all 3 test_git*.py files)
  - **Use case:** "Find commits related to authentication changes" or "Show history of this file"
  - **Discovered:** TEST-006 Round 4 - all 27 remaining failures require this feature
  - **See:** planning_docs/TEST-006_ROUND4_COMPLETE.md

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

#### MCP RAG Tool Enhancements

**Based on empirical evaluation (QA review + architecture discovery tasks), these enhancements address critical gaps in the MCP RAG semantic search capabilities.**

**Phase 1: Quick Wins (2 weeks)**

- [ ] **FEAT-056**: Advanced Filtering & Sorting (~1 week) 🔥🔥
  - **Current Gap:** No way to filter by file pattern, complexity, date ranges, or sort by relevance
  - **Problem:** QA review needed grep for pattern matching ("find all *.test.py files with TODO"), architecture discovery needed complexity filters
  - **Proposed Solution:**
    - [ ] Add `file_pattern` parameter to search_code (glob patterns like "*.test.py", "src/**/auth*.ts")
    - [ ] Add `complexity_min` / `complexity_max` filters (cyclomatic complexity, line count)
    - [ ] Add `modified_after` / `modified_before` date range filters
    - [ ] Add `sort_by` parameter: relevance (default), complexity, size, recency, importance
    - [ ] Add `exclude_patterns` to filter out test files, generated code, etc.
  - **Impact:** Eliminates 40% of grep usage, enables precise filtering, 3x faster targeted searches
  - **Use case:** "Find complex authentication functions modified in last 30 days" or "Show all error handlers sorted by complexity"
  - **Tests:** 15-20 tests for filtering, sorting, and edge cases
  - **See:** planning_docs/FEAT-056_advanced_filtering_plan.md

- [ ] **FEAT-057**: Better UX & Discoverability (~1 week) 🔥
  - **Current Gap:** No query suggestions, result summaries, or interactive refinement
  - **Problem:** Users don't know what queries work well, results lack context, no guidance for improvement
  - **Proposed Solution:**
    - [ ] Add `suggest_queries()` MCP tool - Returns query suggestions based on codebase and intent
    - [ ] Add faceted search results (show file counts by language, category, project)
    - [ ] Add result summaries (e.g., "Found 15 functions across 8 files in 3 projects")
    - [ ] Add "Did you mean?" suggestions for typos/synonyms
    - [ ] Add interactive refinement hints ("Try narrowing with file_pattern=*.py")
  - **Impact:** Reduced learning curve, better discoverability, improved query success rate
  - **Use case:** User asks "show me auth code" → System suggests refinements and shows distribution
  - **Tests:** 10-15 tests for suggestions, facets, summaries
  - **See:** planning_docs/FEAT-057_ux_discoverability_plan.md

- [ ] **FEAT-058**: Pattern Detection (Regex + Semantic Hybrid) (~1 week) 🔥🔥
  - **Current Gap:** No way to combine regex patterns with semantic search
  - **Problem:** QA review needed "find except: blocks" (regex) but only in error handling code (semantic)
  - **Proposed Solution:**
    - [ ] Add `pattern` parameter to search_code (regex pattern)
    - [ ] Add `pattern_mode`: "filter" (semantic first, regex filter), "boost" (regex match boosts score), "require" (must match both)
    - [ ] Add common pattern presets: error_handlers, TODO_comments, security_keywords, deprecated_apis
    - [ ] Combine tree-sitter AST patterns with semantic similarity
  - **Impact:** Eliminates 60% of grep usage, enables precise code smell detection, 10x faster QA reviews
  - **Use case:** "Find all TODO markers in authentication code" or "Show error handlers with bare except:"
  - **Tests:** 15-20 tests for pattern modes, presets, hybrid search
  - **See:** planning_docs/FEAT-058_pattern_detection_plan.md

**Phase 2: Structural Analysis (4 weeks)**

- [ ] **FEAT-059**: Structural/Relational Queries (~2 weeks) 🔥🔥🔥
  - **Current Gap:** No call graph analysis, dependency traversal, or relationship queries
  - **Problem:** Architecture discovery needed "find all callers of this function" and "show dependency chains" - impossible with current tools
  - **Proposed Solution:**
    - [ ] Add `find_callers(function_name, project)` - Find all functions calling this function
    - [ ] Add `find_callees(function_name, project)` - Find all functions called by this function
    - [ ] Add `find_implementations(interface_name)` - Find all implementations of interface/trait
    - [ ] Add `find_dependencies(file_path)` - Get dependency graph for a file (imports/requires)
    - [ ] Add `find_dependents(file_path)` - Get reverse dependencies (what imports this file)
    - [ ] Add `get_call_chain(from_function, to_function)` - Show call path between functions
  - **Impact:** Enables architectural analysis, refactoring planning, impact analysis - transforms discovery from 45min → 5min
  - **Use case:** "Show me all callers of authenticate()" or "What's the call chain from main() to database?"
  - **Tests:** 25-30 tests for call graph, dependencies, edge cases
  - **See:** planning_docs/FEAT-059_structural_queries_plan.md

- [ ] **FEAT-060**: Code Quality Metrics & Hotspots (~2 weeks) 🔥🔥
  - **Current Gap:** No code quality analysis, duplication detection, or complexity metrics
  - **Problem:** QA review manually searched for code smells, complex functions, duplicates - took 30+ minutes
  - **Proposed Solution:**
    - [ ] Add `find_quality_hotspots(project)` - Returns top 20 issues: high complexity, duplicates, long functions, deep nesting
    - [ ] Add `find_duplicates(similarity_threshold=0.85)` - Semantic duplicate detection
    - [ ] Add `get_complexity_report(file_or_project)` - Cyclomatic complexity breakdown
    - [ ] Add quality metrics to search results (complexity, duplication score, maintainability index)
    - [ ] Add filters: `min_complexity`, `has_duplicates`, `long_functions` (>100 lines)
  - **Impact:** Automated code review, 60x faster than manual (30min → 30sec), objective quality metrics
  - **Use case:** "Show me the most complex functions in this project" or "Find duplicate authentication logic"
  - **Tests:** 20-25 tests for metrics, hotspots, duplication
  - **See:** planning_docs/FEAT-060_quality_metrics_plan.md

- [ ] **FEAT-061**: Git/Historical Integration (~1 week) 🔥
  - **Current Gap:** No git history, change frequency, or churn analysis
  - **Problem:** Architecture discovery couldn't identify "frequently changed files" or "recent refactorings"
  - **Proposed Solution:**
    - [ ] Add `search_git_history(query, since, until)` - Semantic search over commit messages and diffs
    - [ ] Add `get_change_frequency(file_or_function)` - How often does this change? (commits/month)
    - [ ] Add `get_churn_hotspots(project)` - Files with highest change frequency
    - [ ] Add `get_recent_changes(project, days=30)` - Recent modifications with semantic context
    - [ ] Add `blame_search(pattern)` - Who wrote code matching this pattern?
  - **Impact:** Understand evolution, identify unstable code, find domain experts
  - **Use case:** "Show files changed most frequently in auth code" or "Who worked on the API layer recently?"
  - **Tests:** 15-20 tests for git integration, change analysis
  - **See:** planning_docs/FEAT-061_git_integration_plan.md

**Phase 3: Visualization (4-6 weeks)**

- [ ] **FEAT-062**: Architecture Visualization & Diagrams (~4-6 weeks) 🔥
  - **Current Gap:** No visual representation of architecture, dependencies, or call graphs
  - **Problem:** Architecture discovery relied on mental modeling - difficult to understand complex systems, explain to others, or document
  - **Proposed Solution:**
    - [ ] Add `visualize_architecture(project)` - Generate architecture diagram (components, layers, boundaries)
    - [ ] Add `visualize_dependencies(file_or_module)` - Dependency graph with depth control
    - [ ] Add `visualize_call_graph(function_name)` - Call graph showing function relationships
    - [ ] Export formats: Graphviz DOT, Mermaid, D3.js JSON, PNG/SVG images
    - [ ] Interactive web viewer with zoom, pan, filtering
    - [ ] Highlight patterns: circular dependencies, deep nesting, tight coupling
  - **Impact:** 10x faster architecture understanding, shareable diagrams, documentation automation
  - **Use case:** "Show me the architecture diagram for this project" or "Visualize dependencies for the auth module"
  - **Tests:** 20-25 tests for visualization, exports, patterns
  - **See:** planning_docs/FEAT-062_architecture_visualization_plan.md

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

- [x] **UX-026**: Web dashboard MVP ✅ **COMPLETE**
  - [x] Basic web UI with statistics
  - [x] Project breakdown display
  - [x] Category and lifecycle charts
  - [x] Recent activity view
  - **Status**: MVP complete, see enhancements below

#### Web Dashboard Enhancements (Post-MVP)

**Phase 1: Core Usability (~20-24 hours, 1-2 weeks)**

**Progress**: 7/15 features complete (47%). See `planning_docs/UX-034-048_dashboard_enhancements_progress.md` for comprehensive implementation guide. All Phase 4 "Quick Wins" features completed!

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

**Phase 4: UX Polish (~12-17 hours, 3-5 days)** ✅ **COMPLETE**

- [x] **UX-044**: Dark Mode Toggle ✅ **COMPLETE** (~2 hours)
  - [x] Dark color scheme with CSS variables
  - [x] Toggle switch in header with sun/moon icons
  - [x] localStorage persistence
  - [x] Keyboard shortcut 'd' for toggle
  - **Impact**: Reduced eye strain, professional appearance
  - **Implementation**: Theme management with data-theme attribute, ~80 lines
  - **Reference**: planning_docs/UX-034-048_dashboard_enhancements_progress.md

- [x] **UX-045**: Keyboard Shortcuts ✅ **COMPLETE** (~2 hours)
  - [x] `/` - Focus search
  - [x] `r` - Refresh data
  - [x] `d` - Toggle dark mode
  - [x] `c` - Clear filters
  - [x] `?` - Show keyboard shortcuts help
  - [x] `Esc` - Close modals
  - **Impact**: Power user productivity boost
  - **Implementation**: Global keydown handler + help modal, ~90 lines
  - **Reference**: planning_docs/UX-034-048_dashboard_enhancements_progress.md

- [x] **UX-046**: Tooltips and Help System ✅ **COMPLETE** (~3 hours)
  - [x] Tippy.js integration from CDN
  - [x] Tooltips on all filter controls
  - [x] Help icons (ⓘ) on section headers
  - [x] Detailed explanations for categories, lifecycle, etc.
  - **Impact**: Reduced learning curve, better discoverability
  - **Implementation**: Tippy.js with data attributes, ~46 lines
  - **Reference**: planning_docs/UX-034-048_dashboard_enhancements_progress.md

- [x] **UX-047**: Loading States and Skeleton Screens ✅ **COMPLETE** (~2 hours)
  - [x] Animated skeleton screens with gradient
  - [x] Different skeleton types (cards, lists, stats)
  - [x] Applied to all loading points
  - **Impact**: Professional UX, perceived performance improvement
  - **Implementation**: CSS animations + JavaScript injection, ~55 lines
  - **Reference**: planning_docs/UX-034-048_dashboard_enhancements_progress.md

- [x] **UX-048**: Error Handling and Retry ✅ **COMPLETE** (~3-4 hours)
  - [x] Toast notification system (error, warning, success, info)
  - [x] Automatic retry with exponential backoff (3 attempts)
  - [x] Offline detection and reconnection handling
  - [x] Auto-dismiss after 5 seconds
  - **Impact**: Better error UX, resilient to network issues
  - **Implementation**: Toast system + fetchWithRetry + offline listeners, ~140 lines
  - **Reference**: planning_docs/UX-034-048_dashboard_enhancements_progress.md

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

- [ ] **REF-013**: Split Monolithic Core Server (~4-6 months) 🔥🔥🔥
  - **Current State:** `src/core/server.py` is 5,192 lines - violates Single Responsibility Principle
  - **Problem:** Difficult to test, understand, modify, and maintain. High coupling, low cohesion.
  - **Impact:** Slows down development, increases bug risk, makes onboarding difficult
  - **Proposed Solution:** Extract into domain-specific service modules:
    - `MemoryService` - Memory storage, retrieval, lifecycle management
    - `CodeIndexingService` - Code indexing, search, similar code
    - `HealthService` - Monitoring, metrics, alerts, remediation
    - `CrossProjectService` - Multi-repository search and consent
    - `QueryService` - Query expansion, intent detection, hybrid search
  - **Approach:**
    - [ ] Create service interfaces with clear contracts
    - [ ] Extract one service at a time (incremental refactor)
    - [ ] Maintain 100% backward compatibility during transition
    - [ ] Add integration tests for each service
    - [ ] Update MCP server to use new services
    - [ ] Remove deprecated monolithic methods
  - **Success Criteria:** No file >1000 lines, clear separation of concerns, improved test coverage
  - **Priority:** Critical for long-term maintainability
  - **See:** `planning_docs/REF-013_split_server_implementation_plan.md`

- [ ] **TEST-007**: Increase Test Coverage to 80%+ (~2-3 months) 🔥🔥
  - **Current State:** 63.68% overall coverage (7,291 of 20,076 lines uncovered)
  - **Critical Gaps:**
    - `src/core/security_logger.py` - 0% (99 lines) 🔴 CRITICAL
    - `src/dashboard/web_server.py` - 0% (299 lines) 🔴 CRITICAL
    - `src/memory/health_scheduler.py` - 0% (172 lines) 🔴 CRITICAL
    - `src/memory/duplicate_detector.py` - 0% (93 lines)
    - `src/router/retrieval_predictor.py` - 0% (82 lines)
    - 20+ modules below 60% coverage
  - **Target:** 80%+ for core modules (src/core, src/store, src/memory, src/embeddings)
  - **Approach:**
    - [ ] Phase 1: Critical modules (security_logger, web_server, health_scheduler) - 0% → 80%
    - [ ] Phase 2: Low coverage modules (<30%) to 60%+
    - [ ] Phase 3: Medium coverage modules (60-79%) to 80%+
    - [ ] Add missing integration tests for end-to-end workflows
    - [ ] Add edge case and error path tests
  - **Impact:** Increased confidence, fewer regressions, better code quality
  - **Priority:** High - essential for production readiness
  - **See:** `planning_docs/TEST-007_coverage_improvement_plan.md`

- [ ] **REF-014**: Extract Qdrant-Specific Logic (~1-2 months) 🔥
  - **Current State:** Qdrant-specific code leaks into business logic
  - **Problem:** 2,328-line `qdrant_store.py` with complex Qdrant queries, tight coupling
  - **Impact:** Difficult to swap backends, test business logic, understand data flow
  - **Proposed Solution:** Repository pattern with clear domain models
    - [ ] Define domain repository interface (independent of Qdrant)
    - [ ] Create domain models for search results, filters, pagination
    - [ ] Implement mapper layer (domain models ↔ Qdrant models)
    - [ ] Refactor QdrantStore to implement domain repository
    - [ ] Update business logic to use domain models only
    - [ ] Add integration tests with mock repository
  - **Benefits:** Cleaner architecture, easier testing, potential for alternative backends
  - **Priority:** High - improves architecture quality
  - **See:** `planning_docs/REF-014_repository_pattern_plan.md`

- [ ] **PERF-007**: Add Connection Pooling for Qdrant (~5 days) 📋 **PLANNED**
  - **Current State:** No connection pool management, potential connection exhaustion
  - **Problem:** Under high load, connections may not be reused efficiently
  - **Proposed Solution:** Implement connection pooling with health checks and retry logic
    - [ ] Phase 1: Core connection pool implementation (Day 1-2)
      - [ ] Create `src/store/connection_pool.py` with QdrantConnectionPool class
      - [ ] Implement async acquire/release with timeout
      - [ ] Add connection recycling (age-based)
      - [ ] Write unit tests (15-20 tests)
    - [ ] Phase 2: Health checks & monitoring (Day 2-3)
      - [ ] Implement ConnectionHealthChecker (fast/medium/deep checks)
      - [ ] Add ConnectionPoolMonitor for metrics collection
      - [ ] Background health check scheduler
      - [ ] Write tests (10-15 tests)
    - [ ] Phase 3: Retry logic integration (Day 3-4)
      - [ ] Create RetryStrategy with exponential backoff + jitter
      - [ ] Integrate retry into QdrantMemoryStore operations
      - [ ] Add operation-specific timeouts
      - [ ] Write tests (15-20 tests)
    - [ ] Phase 4: Integration & testing (Day 4-5)
      - [ ] Refactor QdrantSetup and QdrantMemoryStore to use pool
      - [ ] Integration tests (15-20 tests)
      - [ ] Update documentation
    - [ ] Phase 5: Load testing & validation (Day 5)
      - [ ] Create benchmark script for pool performance
      - [ ] Run baseline vs pool comparison tests
      - [ ] Validate performance targets (throughput, latency, connection count)
  - **Configuration:** 11 new config options (pool size, retry, timeouts, health checks)
  - **Benefits:** Better resource utilization, improved throughput, reduced latency
  - **Impact:** Supports higher concurrent request volumes, better reliability
  - **Performance Targets:**
    - Pool acquire latency: <1ms avg, <5ms P95
    - Maintain throughput: ≥55K ops/sec
    - Maintain P95 search latency: ≤4ms
    - Connection count bounded by pool_size
  - **Priority:** Medium - important for production scale
  - **See:** `planning_docs/PERF-007_connection_pooling_plan.md` (28KB comprehensive plan)

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

- [ ] **TEST-006**: Comprehensive E2E Manual Testing (~10-15 hours) 🔄 **IN PROGRESS**
  - [x] Create comprehensive test plan (200+ test scenarios)
  - [x] Create bug tracker template with pre-populated known bugs
  - [x] Create execution guide and documentation
  - [x] Build Docker orchestration infrastructure (10 parallel agents)
  - [x] Fix Qdrant health check (BUG-019)
  - [x] Verify test agent execution and result collection
  - [ ] Implement automated test logic (currently MANUAL_REQUIRED placeholders)
  - [ ] Execute full E2E test plan (200+ test scenarios)
  - [ ] Test all 16 MCP tools for functionality and UX
  - [ ] Test all 28+ CLI commands end-to-end
  - [ ] Validate installation on clean system (<5 min setup)
  - [ ] Verify performance benchmarks (7-13ms search, 10-20 files/sec indexing)
  - [ ] Test multi-language support (all 17 file formats)
  - [ ] Assess UX quality (error messages, consistency, polish)
  - [ ] Catalogue all bugs in bug tracker (anything requiring workaround = bug)
  - [ ] Test critical known bugs: BUG-018 (memory retrieval), BUG-022 (zero units), BUG-015 (health check)
  - [ ] Generate final production readiness report
  - **Planning Docs:** `planning_docs/TEST-006_*.md` (13 files: test plan, bug tracker, guide, orchestration, Dockerfiles, status, etc.)
  - **Infrastructure Status:** ✅ Docker orchestration working (see `TEST-006_infrastructure_status.md`)
  - **Impact:** Verify production readiness, identify all quality issues before release
  - **Success Criteria:** Zero critical bugs, all core features work without workarounds, performance meets benchmarks

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
