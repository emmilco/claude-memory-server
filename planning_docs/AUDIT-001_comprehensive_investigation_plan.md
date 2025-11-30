# AUDIT-001: Comprehensive Bug Hunting & Tech Debt Investigation Plan

**Created:** 2025-11-30
**Scope:** Exhaustive 18-part investigation of entire codebase
**Methodology:** Read-only analysis by 18 parallel investigation agents
**Output:** TODO.md items with properly ranked priorities, no duplicates with existing tickets

---

## Codebase Overview

- **Size:** ~70,386 lines Python across ~160 modules
- **Test Files:** 202 test files across unit/integration/e2e/performance/security
- **Key Directories:**
  - `src/core/` - Server, validation, tools, exceptions (4,780+ lines in server.py alone)
  - `src/store/` - Qdrant storage (3,181 lines in qdrant_store.py)
  - `src/memory/` - Memory management, indexing (~56 modules)
  - `src/services/` - Service layer (6 services extracted from god class)
  - `src/embeddings/` - Embedding generation, caching
  - `src/search/` - Hybrid search, reranking
  - `src/cli/` - CLI commands (~30 command files)
  - `src/analysis/` - Code analysis (complexity, importance, criticality)
  - `src/monitoring/` - Health, alerts, capacity planning
  - `src/graph/` - Dependency graph generation

---

## Investigation Parts

### PART 1: Core Server & MCP Protocol Analysis
**Agent Assignment:** Agent 1
**Focus Files:**
- `src/core/server.py` (4,780 lines)
- `src/core/tools.py`
- `src/mcp_server.py` (76,900 lines total)

**Investigation Checklist:**
- [ ] Remaining god class smells after REF-016 extraction
- [ ] MCP protocol compliance issues
- [ ] Request/response lifecycle gaps
- [ ] Tool registration correctness
- [ ] Handler method signature consistency
- [ ] Duplicate code between server.py and mcp_server.py
- [ ] State management across requests
- [ ] Missing tool implementations (declared but empty)
- [ ] Incorrect tool schema definitions
- [ ] Response format inconsistencies

**What to Report:**
- Bug IDs with exact file:line locations
- Severity: CRITICAL/HIGH/MEDIUM/LOW
- One-sentence problem description
- Expected fix approach

---

### PART 2: Qdrant Store & Connection Management
**Agent Assignment:** Agent 2
**Focus Files:**
- `src/store/qdrant_store.py` (3,181 lines)
- `src/store/connection_pool.py` (620 lines)
- `src/store/connection_health_checker.py`
- `src/store/connection_pool_monitor.py`
- `src/store/qdrant_setup.py`

**Investigation Checklist:**
- [ ] Connection leak paths (acquire without release)
- [ ] Pool exhaustion scenarios
- [ ] Connection recycling correctness
- [ ] Health check accuracy
- [ ] Retry logic completeness
- [ ] Transaction semantics violations
- [ ] Point ID format inconsistencies
- [ ] Collection schema drift risks
- [ ] Batch operation atomicity
- [ ] Timeout handling in all paths

**What to Report:**
- Connection safety issues with lifecycle analysis
- Data corruption risks
- Recovery mechanism gaps

---

### PART 3: Embedding Generation & Caching
**Agent Assignment:** Agent 3
**Focus Files:**
- `src/embeddings/rust_bridge.py`
- `src/embeddings/parallel_generator.py`
- `src/embeddings/cache.py`
- `src/embeddings/executor.py`
- `src/embeddings/fallback_executor.py`
- `src/embeddings/gpu_utils.py`

**Investigation Checklist:**
- [ ] Model loading failure recovery
- [ ] GPU/CPU fallback correctness
- [ ] Cache invalidation bugs
- [ ] Parallel worker lifecycle
- [ ] Memory leaks in tensor operations
- [ ] Batch size optimization issues
- [ ] Dimension mismatch bugs
- [ ] Rust bridge error handling
- [ ] Worker process cleanup
- [ ] Cache size management

**What to Report:**
- Memory safety issues
- Performance bottlenecks
- Failure mode analysis

---

### PART 4: Search & Retrieval Pipeline
**Agent Assignment:** Agent 4
**Focus Files:**
- `src/search/hybrid_search.py`
- `src/search/reranker.py`
- `src/search/bm25.py`
- `src/search/query_synonyms.py`
- `src/search/query_expansion.py`
- `src/search/pattern_matcher.py`

**Investigation Checklist:**
- [ ] Ranking algorithm correctness
- [ ] Score normalization issues
- [ ] Empty result handling
- [ ] Query expansion edge cases
- [ ] BM25 tokenization bugs
- [ ] Fusion strategy correctness
- [ ] Relevance score interpretation
- [ ] Filter application order
- [ ] Pagination cursor stability
- [ ] Sort order consistency

**What to Report:**
- Algorithmic bugs affecting search quality
- Performance issues in hot paths
- Edge case failures

---

### PART 5: Memory Indexing & Parsing
**Agent Assignment:** Agent 5
**Focus Files:**
- `src/memory/incremental_indexer.py`
- `src/memory/python_parser.py`
- `src/memory/import_extractor.py`
- `src/memory/dependency_graph.py`
- `src/memory/background_indexer.py`
- `src/memory/git_detector.py`

**Investigation Checklist:**
- [ ] Parser failure recovery
- [ ] Incremental indexing consistency
- [ ] File change detection accuracy
- [ ] Language detection edge cases
- [ ] AST parsing error handling
- [ ] Circular dependency handling
- [ ] Large file handling
- [ ] Binary file detection
- [ ] Encoding issues (UTF-8, etc.)
- [ ] Git ignore pattern handling

**What to Report:**
- Data consistency bugs
- Silent parsing failures
- Index corruption risks

---

### PART 6: Service Layer Integrity
**Agent Assignment:** Agent 6
**Focus Files:**
- `src/services/memory_service.py` (1,579 lines)
- `src/services/code_indexing_service.py`
- `src/services/cross_project_service.py`
- `src/services/health_service.py`
- `src/services/query_service.py`
- `src/services/analytics_service.py`

**Investigation Checklist:**
- [ ] Service boundary violations
- [ ] Circular dependencies between services
- [ ] Inconsistent error handling across services
- [ ] Missing transaction boundaries
- [ ] State leakage between service calls
- [ ] Duplicated business logic
- [ ] Interface contract violations
- [ ] Logging inconsistencies
- [ ] Timeout propagation issues
- [ ] Resource cleanup in error paths

**What to Report:**
- Architectural issues
- Service contract bugs
- Cross-service consistency problems

---

### PART 7: Configuration & Validation
**Agent Assignment:** Agent 7
**Focus Files:**
- `src/config.py` (29,206 lines)
- `src/core/validation.py`
- `src/core/allowed_fields.py`

**Investigation Checklist:**
- [ ] Missing range validators for numeric fields
- [ ] Interdependent config not validated together
- [ ] Default values that cause failures
- [ ] Environment variable parsing bugs
- [ ] Config file loading edge cases
- [ ] Feature flag conflicts
- [ ] Deprecated config options still accepted
- [ ] Config migration gaps
- [ ] Validation error message quality
- [ ] Secret value handling in logs

**What to Report:**
- Configuration bugs that cause runtime failures
- Validation gaps
- Default value issues

---

### PART 8: CLI Commands & User Experience
**Agent Assignment:** Agent 8
**Focus Files:**
- `src/cli/__main__.py`
- `src/cli/__init__.py`
- All `src/cli/*_command.py` files (~30 files)

**Investigation Checklist:**
- [ ] Missing command implementations
- [ ] Inconsistent argument parsing
- [ ] Missing help text
- [ ] Error message quality
- [ ] Output format inconsistencies
- [ ] Progress indicator issues
- [ ] Exit code correctness
- [ ] Keyboard interrupt handling
- [ ] File path validation
- [ ] Color/formatting issues

**What to Report:**
- User-facing bugs
- CLI contract violations
- Usability issues

---

### PART 9: Async/Concurrency Safety
**Agent Assignment:** Agent 9
**Focus Files:**
- All files using `asyncio`, `threading`, `concurrent.futures`
- Focus on `src/store/`, `src/embeddings/`, `src/services/`

**Investigation Checklist:**
- [ ] Missing await keywords
- [ ] Fire-and-forget tasks without error handling
- [ ] Race conditions in shared state
- [ ] Deadlock risks
- [ ] Lock ordering issues
- [ ] Event loop blocking
- [ ] Task cancellation handling
- [ ] Timeout implementation correctness
- [ ] Thread-safe collection usage
- [ ] Asyncio.gather error propagation

**What to Report:**
- Race conditions with reproduction steps
- Deadlock patterns
- Concurrency correctness bugs

---

### PART 10: Exception Handling & Error Recovery
**Agent Assignment:** Agent 10
**Focus Files:**
- `src/core/exceptions.py`
- All files with try/except blocks (grep for "except")

**Investigation Checklist:**
- [ ] Exception chain preservation (raise...from e)
- [ ] Bare except clauses
- [ ] Swallowed exceptions (except: pass)
- [ ] Overly broad exception catching
- [ ] Missing exception types in raises
- [ ] Error recovery mechanism gaps
- [ ] Exception message quality
- [ ] Logging in exception handlers
- [ ] Resource cleanup in finally blocks
- [ ] Exception hierarchy correctness

**What to Report:**
- Silent failure patterns
- Missing error recovery
- Debugging difficulty issues

---

### PART 11: Code Analysis & Quality Scoring
**Agent Assignment:** Agent 11
**Focus Files:**
- `src/analysis/complexity_analyzer.py`
- `src/analysis/importance_scorer.py`
- `src/analysis/criticality_analyzer.py`
- `src/analysis/usage_analyzer.py`
- `src/analysis/code_duplicate_detector.py`
- `src/analysis/call_extractors.py`

**Investigation Checklist:**
- [ ] Algorithm correctness
- [ ] Score calculation bugs
- [ ] Metric consistency
- [ ] Language-specific handling
- [ ] Edge case handling (empty files, etc.)
- [ ] Performance for large codebases
- [ ] Cache correctness
- [ ] Dependency analysis accuracy
- [ ] Cyclomatic complexity calculation
- [ ] Dead code detection accuracy

**What to Report:**
- Algorithmic bugs
- Incorrect metrics
- Performance issues

---

### PART 12: Monitoring & Health Systems
**Agent Assignment:** Agent 12
**Focus Files:**
- `src/monitoring/health_reporter.py`
- `src/monitoring/alert_engine.py`
- `src/monitoring/capacity_planner.py`
- `src/monitoring/remediation.py`
- `src/memory/health_scheduler.py`
- `src/memory/health_jobs.py`

**Investigation Checklist:**
- [ ] Health check accuracy
- [ ] Alert threshold correctness
- [ ] Metric collection bugs
- [ ] Remediation action safety
- [ ] Scheduler reliability
- [ ] Job state management
- [ ] Capacity planning accuracy
- [ ] Performance impact of monitoring
- [ ] False positive/negative rates
- [ ] Recovery action effectiveness

**What to Report:**
- Health check bugs
- Monitoring accuracy issues
- Alert reliability problems

---

### PART 13: Backup, Export & Import
**Agent Assignment:** Agent 13
**Focus Files:**
- `src/backup/scheduler.py`
- `src/cli/backup_command.py`
- `src/cli/export_command.py`
- `src/cli/import_command.py`
- `src/memory/archive_exporter.py`
- `src/memory/archive_importer.py`
- `src/memory/archive_compressor.py`

**Investigation Checklist:**
- [ ] Data integrity during export
- [ ] Import validation completeness
- [ ] Version compatibility handling
- [ ] Large dataset handling
- [ ] Partial failure recovery
- [ ] Compression correctness
- [ ] File format versioning
- [ ] Migration path clarity
- [ ] Backup scheduling reliability
- [ ] Restore verification

**What to Report:**
- Data integrity bugs
- Import/export failures
- Recovery gaps

---

### PART 14: Graph Generation & Visualization
**Agent Assignment:** Agent 14
**Focus Files:**
- `src/graph/dependency_graph.py`
- `src/graph/call_graph.py`
- `src/graph/formatters/dot_formatter.py`
- `src/graph/formatters/json_formatter.py`
- `src/graph/formatters/mermaid_formatter.py`
- `src/memory/graph_generator.py`

**Investigation Checklist:**
- [ ] Graph cycle detection correctness
- [ ] Node/edge escaping in formatters
- [ ] Large graph handling
- [ ] Format specification compliance
- [ ] Missing edge cases
- [ ] Performance for large codebases
- [ ] Depth limiting correctness
- [ ] Filter application accuracy
- [ ] Metadata completeness
- [ ] Cross-file reference accuracy

**What to Report:**
- Output format bugs
- Graph algorithm issues
- Performance problems

---

### PART 15: Tagging & Classification
**Agent Assignment:** Agent 15
**Focus Files:**
- `src/tagging/auto_tagger.py`
- `src/tagging/collection_manager.py`
- `src/tagging/tag_manager.py`
- `src/tagging/models.py`
- `src/memory/classifier.py`

**Investigation Checklist:**
- [ ] Auto-tagging accuracy
- [ ] Tag collision handling
- [ ] Classification consistency
- [ ] Tag inheritance/propagation
- [ ] Collection membership correctness
- [ ] Tag deletion cleanup
- [ ] Case sensitivity handling
- [ ] Special character handling
- [ ] Tag search correctness
- [ ] Bulk operation atomicity

**What to Report:**
- Classification bugs
- Tag management issues
- Data consistency problems

---

### PART 16: Test Suite Quality Audit
**Agent Assignment:** Agent 16
**Focus Files:**
- All files in `tests/` directory
- Focus on test patterns, not specific test logic

**Investigation Checklist:**
- [ ] Tests with no assertions
- [ ] Tests that never fail (assert True)
- [ ] Excessive mocking hiding bugs
- [ ] Missing edge case tests
- [ ] Flaky test patterns
- [ ] Test isolation issues
- [ ] Fixture cleanup problems
- [ ] Parametrization opportunities
- [ ] Missing integration tests
- [ ] Coverage gaps in critical paths

**What to Report:**
- Validation theater examples
- Coverage gap analysis
- Test quality issues

---

### PART 17: Documentation & Code Comments Accuracy
**Agent Assignment:** Agent 17
**Focus Files:**
- All docstrings in `src/`
- All inline comments
- README files

**Investigation Checklist:**
- [ ] Docstrings that don't match implementation
- [ ] Stale comments (reference removed code)
- [ ] Missing docstrings on public APIs
- [ ] Incorrect parameter documentation
- [ ] Missing return type documentation
- [ ] Example code that doesn't work
- [ ] TODO comments that should be tickets
- [ ] Misleading variable names
- [ ] Type hints that don't match runtime
- [ ] Dead code with misleading comments

**What to Report:**
- Documentation bugs
- Misleading comments
- API documentation gaps

---

### PART 18: Security & Input Validation
**Agent Assignment:** Agent 18
**Focus Files:**
- All input handling code
- File path handling
- Query construction
- External service calls

**Investigation Checklist:**
- [ ] SQL/NoSQL injection risks
- [ ] Path traversal vulnerabilities
- [ ] Command injection risks
- [ ] Unsafe deserialization
- [ ] Missing input validation
- [ ] Secrets in logs
- [ ] Unsafe file operations
- [ ] SSRF vulnerabilities
- [ ] Race condition exploits
- [ ] Denial of service vectors

**What to Report:**
- Security vulnerabilities with severity
- Input validation gaps
- Attack surface analysis

---

## Priority Guidelines for TODO Items

**CRITICAL:** Runtime crashes, data corruption, security vulnerabilities
**HIGH:** Incorrect behavior, feature completely broken, significant performance
**MEDIUM:** Edge case failures, minor incorrectness, code quality
**LOW:** Documentation, style, minor improvements

## Existing Ticket Deduplication

Before adding any TODO item, agents MUST check for:
1. Existing BUG-XXX tickets (check BUG-001 through BUG-060)
2. Existing REF-XXX tickets (check REF-001 through REF-035)
3. Existing TEST-XXX tickets (check TEST-001 through TEST-030)
4. Existing INVEST-XXX investigations already completed

Only add NEW findings that are not duplicates of existing work.

---

## Execution Plan

**Wave 1:** Agents 1-6 (Core infrastructure, storage, embeddings, search, indexing, services)
**Wave 2:** Agents 7-12 (Config, CLI, async, exceptions, analysis, monitoring)
**Wave 3:** Agents 13-18 (Backup, graph, tagging, tests, docs, security)

Each wave runs 6 agents in parallel. After each wave completes, results are consolidated.
