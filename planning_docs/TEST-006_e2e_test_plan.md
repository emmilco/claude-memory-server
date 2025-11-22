# End-to-End Manual Test Plan
# Claude Memory RAG Server v4.0

**Date:** 2025-11-20
**Version:** 4.0 (Production-Ready Enterprise Features)
**Tester:** [Fill in]
**Test Environment:** [Fill in OS, Python version, Docker version]

---

## Table of Contents

1. [Installation & Setup Tests](#1-installation--setup-tests)
2. [MCP Tools Tests (16 Tools)](#2-mcp-tools-tests-16-tools)
3. [CLI Commands Tests (28+ Commands)](#3-cli-commands-tests-28-commands)
4. [Code Search & Indexing Tests](#4-code-search--indexing-tests)
5. [Memory Management Tests](#5-memory-management-tests)
6. [Multi-Project & Cross-Project Tests](#6-multi-project--cross-project-tests)
7. [Health Monitoring & Performance Tests](#7-health-monitoring--performance-tests)
8. [Dashboard & TUI Tests](#8-dashboard--tui-tests)
9. [Configuration & Backend Tests](#9-configuration--backend-tests)
10. [Documentation & Git History Tests](#10-documentation--git-history-tests)
11. [Security & Validation Tests](#11-security--validation-tests)
12. [Error Handling & Edge Cases](#12-error-handling--edge-cases)
13. [Performance Benchmarks](#13-performance-benchmarks)
14. [UX Quality Assessment](#14-ux-quality-assessment)

---

## Test Standards

### Quality Criteria
- **Expected Behavior:** Feature works as documented
- **Output Quality:** Results are accurate, relevant, and properly formatted
- **Ease of Use:** No workarounds required, clear error messages, intuitive UX
- **Performance:** Meets documented benchmarks (7-13ms search, etc.)
- **Experience Quality:** Professional, polished, no rough edges

### Bug Definition
**IMPORTANT:** The following are considered bugs and must be catalogued:
- ❌ Anything requiring a workaround
- ❌ Anything unimplemented or incompletely removed
- ❌ Anything not functioning to a high standard of quality and UX
- ❌ Misleading documentation or error messages
- ❌ Performance significantly below documented benchmarks
- ❌ Confusing or inconsistent user experience

### Test Result Notation
- ✅ **PASS** - Works perfectly, no issues
- ⚠️ **PASS with Notes** - Works but has minor UX issues
- ❌ **FAIL** - Does not work or requires workarounds
- 🔍 **NEEDS INVESTIGATION** - Unclear if working correctly
- ⏭️ **SKIPPED** - Unable to test (document reason)

---

## 1. Installation & Setup Tests

### 1.1 Automated Setup (setup.py)

**Test ID:** INST-001
**Scenario:** Fresh installation on clean system
**Steps:**
1. Clone repository: `git clone <repo>`
2. Run: `python setup.py`
3. Observe interactive wizard

**Expected:**
- ✅ Wizard guides through all steps
- ✅ Checks Python version (3.8+ required, 3.13+ recommended)
- ✅ Installs dependencies automatically
- ✅ Checks for Docker
- ✅ Starts Qdrant container
- ✅ Configures storage backend (Qdrant)
- ✅ Checks for Rust (offers Python fallback)
- ✅ Runs verification tests
- ✅ Completes in 2-5 minutes
- ✅ Clear success message at end

**Test:**
- [ ] All wizard steps complete without errors
- [ ] No manual intervention required
- [ ] Qdrant container starts successfully
- [ ] Verification tests pass
- [ ] Time: _____ minutes (should be 2-5 min)

**Quality Checks:**
- [ ] Error messages are actionable (not generic)
- [ ] Progress indicators work correctly
- [ ] Can recover from interruptions (Ctrl+C)
- [ ] No scary warnings or stack traces

**Result:** [ ]
**Notes:**

---

**Test ID:** INST-002
**Scenario:** Setup with Rust missing
**Steps:**
1. Ensure Rust/Cargo not in PATH
2. Run: `python setup.py`

**Expected:**
- ✅ Detects Rust unavailable
- ✅ Offers Python parser fallback
- ✅ Warns about performance implications (10-20ms vs 1-6ms)
- ✅ Continues installation successfully

**Test:**
- [ ] Fallback offered clearly
- [ ] Performance warning shown
- [ ] Setup completes with Python parser
- [ ] Parser works for code indexing

**Result:** [ ]
**Notes:**

---

**Test ID:** INST-003
**Scenario:** Setup with Docker missing
**Steps:**
1. Stop Docker daemon or uninstall Docker
2. Run: `python setup.py`

**Expected:**
- ❌ Setup should fail or warn critically
- ✅ Clear error message explaining Qdrant requirement
- ✅ Actionable next steps (install Docker)
- ✅ Link to Docker installation guide

**Test:**
- [ ] Error message is clear and actionable
- [ ] No confusing fallback to SQLite (deprecated)
- [ ] User knows exactly what to do next

**Result:** [ ]
**Notes:**

---

**Test ID:** INST-004
**Scenario:** Upgrade from older version
**Steps:**
1. Install v3.x (if available)
2. Run: `python setup.py --upgrade`

**Expected:**
- ✅ Detects existing installation
- ✅ Preserves existing data
- ✅ Migrates configuration if needed
- ✅ No data loss

**Test:**
- [ ] Upgrade completes successfully
- [ ] Existing memories still retrievable
- [ ] Existing indexed code still searchable
- [ ] Configuration preserved

**Result:** [ ]
**Notes:**

---

### 1.2 Manual Installation

**Test ID:** INST-005
**Scenario:** Manual installation following README
**Steps:**
1. `pip install -r requirements.txt`
2. `cd rust_core && maturin develop && cd ..`
3. `docker-compose up -d`
4. `export CLAUDE_RAG_STORAGE_BACKEND=qdrant`

**Expected:**
- ✅ All dependencies install without conflicts
- ✅ Rust module builds successfully
- ✅ Qdrant starts without errors
- ✅ Environment variables work

**Test:**
- [ ] Dependencies install cleanly
- [ ] No version conflicts
- [ ] Rust build succeeds
- [ ] Qdrant accessible at localhost:6333

**Result:** [ ]
**Notes:**

---

### 1.3 Validation Commands

**Test ID:** INST-006
**Scenario:** System health check after install
**Steps:**
1. Run: `python -m src.cli health`

**Expected:**
- ✅ Shows comprehensive health report
- ✅ Qdrant: Connected
- ✅ Parser: Rust or Python fallback
- ✅ All components green or with warnings

**Test:**
- [ ] Health report displays correctly
- [ ] All components show status
- [ ] No misleading false negatives (BUG-015)

**Result:** [ ]
**Notes:**

---

**Test ID:** INST-007
**Scenario:** Comprehensive installation validation
**Steps:**
1. Run: `python -m src.cli validate-install`

**Expected:**
- ✅ Checks Python version
- ✅ Checks all dependencies
- ✅ Checks Qdrant availability
- ✅ Checks parser availability
- ✅ Runs basic functionality tests
- ✅ Reports pass/fail for each component

**Test:**
- [ ] All checks run successfully
- [ ] Clear pass/fail indicators
- [ ] Actionable errors if something fails

**Result:** [ ]
**Notes:**

---

**Test ID:** INST-008
**Scenario:** Setup validation command
**Steps:**
1. Run: `python -m src.cli validate-setup`

**Expected:**
- ✅ Validates Qdrant connection
- ✅ Validates configuration
- ✅ Clear success/failure message

**Test:**
- [ ] Command runs without errors
- [ ] Qdrant check works correctly (BUG-015 fix verified)

**Result:** [ ]
**Notes:**

---

### 1.4 MCP Integration

**Test ID:** INST-009
**Scenario:** Add to Claude Code
**Steps:**
1. Get Python path: `which python`
2. Get project dir: `pwd`
3. Run: `claude mcp add --transport stdio --scope user claude-memory-rag -- $PYTHON_PATH "$PROJECT_DIR/src/mcp_server.py"`

**Expected:**
- ✅ MCP server registered successfully
- ✅ Shows up in `claude mcp list`
- ✅ Tools available to Claude Code

**Test:**
- [ ] Registration succeeds
- [ ] Server appears in list
- [ ] Tools accessible in Claude Code session
- [ ] Paths resolve correctly (especially with pyenv)

**Result:** [ ]
**Notes:**

---

**Test ID:** INST-010
**Scenario:** MCP server starts without errors
**Steps:**
1. Start Claude Code session
2. Observe MCP server logs

**Expected:**
- ✅ Server starts within 2-3 seconds
- ✅ No import errors
- ✅ All 16 tools registered
- ✅ Qdrant connection established

**Test:**
- [ ] Server starts quickly
- [ ] No errors in logs
- [ ] All tools available

**Result:** [ ]
**Notes:**

---

## 2. MCP Tools Tests (16 Tools)

### 2.1 Memory Management Tools

#### store_memory

**Test ID:** MCP-001
**Scenario:** Store a simple preference memory
**Steps:**
1. Call `store_memory` with:
   ```json
   {
     "content": "I prefer Python for backend development",
     "category": "preference",
     "importance": 0.8
   }
   ```

**Expected:**
- ✅ Returns memory_id
- ✅ Status: "stored"
- ✅ Context level auto-detected (USER_PREFERENCE)
- ✅ No errors

**Test:**
- [ ] Memory stored successfully
- [ ] ID returned and valid UUID
- [ ] Auto-classification works

**Result:** [ ]
**Notes:**

---

**Test ID:** MCP-002
**Scenario:** Store memory with tags and metadata
**Steps:**
1. Call `store_memory` with:
   ```json
   {
     "content": "This project uses FastAPI with async/await patterns",
     "category": "context",
     "scope": "project",
     "project_name": "test-project",
     "importance": 0.7,
     "tags": ["fastapi", "async", "python"],
     "metadata": {"version": "0.1.0"}
   }
   ```

**Expected:**
- ✅ Memory stored with all fields
- ✅ Tags preserved
- ✅ Metadata preserved
- ✅ Project scope applied

**Test:**
- [ ] All fields stored correctly
- [ ] Retrievable by tags
- [ ] Project scoping works

**Result:** [ ]
**Notes:**

---

**Test ID:** MCP-003
**Scenario:** Store memory with validation errors
**Steps:**
1. Try to store memory with empty content
2. Try to store memory with >50000 chars
3. Try to store memory with invalid category

**Expected:**
- ❌ Empty content rejected with clear error
- ❌ Oversized content rejected
- ❌ Invalid category rejected
- ✅ Error messages are actionable

**Test:**
- [ ] Validation works correctly
- [ ] Error messages are clear
- [ ] No silent failures

**Result:** [ ]
**Notes:**

---

#### retrieve_memories

**Test ID:** MCP-004
**Scenario:** Retrieve recently stored memory
**Steps:**
1. Store a memory: "I prefer TypeScript for frontend"
2. Immediately retrieve with query: "TypeScript preferences"

**Expected:**
- ✅ Returns stored memory
- ✅ Score > 0.8 (high relevance)
- ✅ Content matches
- ✅ Latency < 50ms

**Test:**
- [ ] Memory retrieved successfully
- [ ] High relevance score
- [ ] Fast response time: _____ ms

**Critical Check (BUG-018):**
- [ ] Memory IS immediately retrievable (not delayed)
- [ ] No "not found" errors

**Result:** [ ]
**Notes:**

---

**Test ID:** MCP-005
**Scenario:** Retrieve with filters
**Steps:**
1. Store 5 memories (different categories, importance levels)
2. Retrieve with filter: `min_importance: 0.7`
3. Retrieve with filter: `category: preference`
4. Retrieve with filter: `tags: ["python"]`

**Expected:**
- ✅ Filters apply correctly
- ✅ Only matching memories returned
- ✅ Counts accurate

**Test:**
- [ ] Importance filter works
- [ ] Category filter works
- [ ] Tag filter works
- [ ] No unmatched results leaked

**Result:** [ ]
**Notes:**

---

**Test ID:** MCP-006
**Scenario:** Retrieve with limit and pagination
**Steps:**
1. Store 20 memories
2. Retrieve with `limit: 5`
3. Verify only 5 returned
4. Retrieve next page (if pagination supported)

**Expected:**
- ✅ Limit respected
- ✅ Results truncated correctly
- ✅ Count indicates total available

**Test:**
- [ ] Limit parameter works
- [ ] Pagination works (if supported)

**Result:** [ ]
**Notes:**

---

#### list_memories

**Test ID:** MCP-007
**Scenario:** List all memories
**Steps:**
1. Store 10 diverse memories
2. Call `list_memories` with no filters

**Expected:**
- ✅ Returns all memories
- ✅ Total count matches
- ✅ Pagination info included
- ✅ Default sort: created_at desc

**Test:**
- [ ] All memories listed
- [ ] Total count correct (BUG-016 check)
- [ ] Pagination fields present

**Critical Check (BUG-016):**
- [ ] `total` field is NOT zero when results exist
- [ ] `returned_count` matches array length

**Result:** [ ]
**Notes:**

---

**Test ID:** MCP-008
**Scenario:** List with sorting and filters
**Steps:**
1. List with `sort_by: importance, sort_order: desc`
2. List with `category: preference`
3. List with date range filters

**Expected:**
- ✅ Sorting works correctly
- ✅ Filters apply correctly
- ✅ Combinations work

**Test:**
- [ ] Sorting by importance works
- [ ] Sorting by created_at works
- [ ] Filters combine correctly

**Result:** [ ]
**Notes:**

---

#### update_memory

**Test ID:** MCP-009
**Scenario:** Update memory content
**Steps:**
1. Store a memory
2. Call `update_memory` changing content

**Expected:**
- ✅ Memory updated
- ✅ Embedding regenerated
- ✅ updated_at timestamp changed
- ✅ Old content replaced

**Test:**
- [ ] Update succeeds
- [ ] New content searchable
- [ ] Timestamp updated

**Result:** [ ]
**Notes:**

---

**Test ID:** MCP-010
**Scenario:** Update memory without regenerating embedding
**Steps:**
1. Store a memory
2. Update with `regenerate_embedding: false`

**Expected:**
- ✅ Update faster
- ✅ Embedding not recalculated
- ✅ Still searchable by old semantics

**Test:**
- [ ] Update is faster
- [ ] Embedding unchanged

**Result:** [ ]
**Notes:**

---

#### get_memory_by_id

**Test ID:** MCP-011
**Scenario:** Retrieve specific memory by ID
**Steps:**
1. Store a memory and note the ID
2. Call `get_memory_by_id` with that ID

**Expected:**
- ✅ Returns exact memory
- ✅ All fields present
- ✅ Metadata preserved

**Test:**
- [ ] Correct memory returned
- [ ] All fields intact

**Result:** [ ]
**Notes:**

---

**Test ID:** MCP-012
**Scenario:** Get non-existent memory
**Steps:**
1. Call `get_memory_by_id` with fake UUID

**Expected:**
- ✅ Returns status: "not_found"
- ✅ Clear error message
- ✅ No exceptions thrown

**Test:**
- [ ] Handles missing memory gracefully
- [ ] Error message is clear

**Result:** [ ]
**Notes:**

---

#### delete_memory

**Test ID:** MCP-013
**Scenario:** Delete a memory by ID
**Steps:**
1. Store a memory
2. Delete it using `delete_memory`
3. Try to retrieve it

**Expected:**
- ✅ Delete succeeds
- ✅ Returns deleted: true
- ✅ Memory no longer retrievable

**Test:**
- [ ] Deletion succeeds
- [ ] Memory actually removed
- [ ] Subsequent retrieval fails

**Critical Check (BUG-020):**
- [ ] Return structure: `{"deleted": true}` or `{"success": true}`?
- [ ] Consistent with documentation?

**Result:** [ ]
**Notes:**

---

### 2.2 Code Intelligence Tools

#### search_code

**Test ID:** MCP-014
**Scenario:** Semantic code search - basic
**Steps:**
1. Index a Python project
2. Search: "authentication logic"

**Expected:**
- ✅ Returns auth-related functions
- ✅ Relevance scores > 0.7
- ✅ File paths and line numbers included
- ✅ Search time < 20ms

**Test:**
- [ ] Relevant results returned
- [ ] Scores indicate relevance
- [ ] Performance meets target: _____ ms

**Result:** [ ]
**Notes:**

---

**Test ID:** MCP-015
**Scenario:** Hybrid search mode
**Steps:**
1. Index code
2. Search with `search_mode: hybrid`
3. Query: "async login handler"

**Expected:**
- ✅ Combines semantic + keyword matching
- ✅ matched_keywords field populated
- ✅ Better precision than pure semantic

**Test:**
- [ ] Hybrid mode works
- [ ] Keywords highlighted
- [ ] Relevance is high

**Result:** [ ]
**Notes:**

---

**Test ID:** MCP-016
**Scenario:** Search with language filter
**Steps:**
1. Index multi-language project (Python, JS, TypeScript)
2. Search with `language: python`

**Expected:**
- ✅ Only Python files returned
- ✅ JS/TS files excluded

**Test:**
- [ ] Language filter works correctly
- [ ] No cross-language leakage

**Result:** [ ]
**Notes:**

---

**Test ID:** MCP-017
**Scenario:** Search with file pattern filter
**Steps:**
1. Index project
2. Search with `file_pattern: */auth/*`

**Expected:**
- ✅ Only files in auth directories returned
- ✅ Pattern matching works

**Test:**
- [ ] File pattern filter works
- [ ] Glob patterns supported

**Result:** [ ]
**Notes:**

---

**Test ID:** MCP-018
**Scenario:** Search on empty/unindexed project
**Steps:**
1. Search project with no indexed code

**Expected:**
- ✅ Returns empty results
- ✅ Clear message: "No code found for project X"
- ✅ No errors thrown

**Test:**
- [ ] Handles gracefully
- [ ] Message is helpful

**Result:** [ ]
**Notes:**

---

#### index_codebase

**Test ID:** MCP-019
**Scenario:** Index a small Python project
**Steps:**
1. Create test project (10-20 Python files)
2. Call `index_codebase` with directory path

**Expected:**
- ✅ Indexes all .py files
- ✅ Extracts functions, classes, methods
- ✅ Progress indicators shown
- ✅ Completes in <10 seconds
- ✅ Success summary with counts

**Test:**
- [ ] All files indexed
- [ ] Semantic units extracted (BUG-022 check)
- [ ] Time: _____ seconds
- [ ] Units extracted: _____ (should be > 0)

**Critical Check (BUG-022):**
- [ ] Semantic units count is NOT zero
- [ ] Functions and classes actually extracted

**Result:** [ ]
**Notes:**

---

**Test ID:** MCP-020
**Scenario:** Index multi-language project
**Steps:**
1. Create project with Python, JS, TypeScript, Java files
2. Index the directory

**Expected:**
- ✅ All supported languages indexed
- ✅ Language-specific parsers used
- ✅ No parser errors

**Test:**
- [ ] Python files indexed
- [ ] JavaScript files indexed
- [ ] TypeScript files indexed
- [ ] Java files indexed

**Critical Check (BUG-021):**
- [ ] PHP parser warning (if PHP files present)
- [ ] Is this expected? Or a bug?

**Result:** [ ]
**Notes:**

---

**Test ID:** MCP-021
**Scenario:** Re-index (incremental update)
**Steps:**
1. Index a project
2. Modify a file
3. Re-index

**Expected:**
- ✅ Detects changes
- ✅ Only re-indexes changed files
- ✅ Faster than full index (98% cache hit)
- ✅ Stale entries cleaned up

**Test:**
- [ ] Incremental indexing works
- [ ] Cache hit rate > 90%
- [ ] Old entries removed

**Result:** [ ]
**Notes:**

---

**Test ID:** MCP-022
**Scenario:** Index with Rust parser vs Python fallback
**Steps:**
1. Index same project with Rust parser
2. Index same project with Python parser
3. Compare speed and accuracy

**Expected:**
- ✅ Rust: 1-6ms per file
- ✅ Python: 10-20ms per file
- ✅ Same semantic units extracted
- ✅ Clear speed difference

**Test:**
- [ ] Rust parser faster
- [ ] Python fallback works
- [ ] Results equivalent
- [ ] Speed ratio: _____ x faster

**Result:** [ ]
**Notes:**

---

#### find_similar_code

**Test ID:** MCP-023
**Scenario:** Find similar code snippets
**Steps:**
1. Index a project
2. Provide a code snippet
3. Call `find_similar_code`

**Expected:**
- ✅ Returns similar code blocks
- ✅ Semantic similarity, not just text matching
- ✅ Useful for finding duplicates

**Test:**
- [ ] Similar code found
- [ ] Results make sense
- [ ] Similarity scores reasonable

**Result:** [ ]
**Notes:**

---

#### search_all

**Test ID:** MCP-024
**Scenario:** Search all indexed content
**Steps:**
1. Index code and ingest docs
2. Call `search_all` with a query

**Expected:**
- ✅ Searches both code and docs
- ✅ Results from both sources
- ✅ Relevance across domains

**Test:**
- [ ] Code results included
- [ ] Doc results included
- [ ] Unified ranking

**Result:** [ ]
**Notes:**

---

### 2.3 Multi-Project Tools

#### opt_in_cross_project

**Test ID:** MCP-025
**Scenario:** Enable cross-project search
**Steps:**
1. Index project A
2. Index project B
3. Opt both into cross-project search

**Expected:**
- ✅ Consent recorded
- ✅ Both projects searchable globally

**Test:**
- [ ] Opt-in succeeds
- [ ] Projects appear in opted-in list

**Result:** [ ]
**Notes:**

---

#### search_all_projects

**Test ID:** MCP-026
**Scenario:** Cross-project code search
**Steps:**
1. Index and opt-in 2+ projects
2. Search across all projects

**Expected:**
- ✅ Results from multiple projects
- ✅ Project names indicated
- ✅ Privacy respected (only opted-in)

**Test:**
- [ ] Multi-project results
- [ ] Project attribution clear
- [ ] Non-opted-in projects excluded

**Result:** [ ]
**Notes:**

---

#### opt_out_cross_project

**Test ID:** MCP-027
**Scenario:** Revoke cross-project consent
**Steps:**
1. Opt-in a project
2. Opt-out the same project
3. Verify exclusion from global search

**Expected:**
- ✅ Opt-out succeeds
- ✅ Project excluded from cross-search
- ✅ Still searchable individually

**Test:**
- [ ] Opt-out works
- [ ] Privacy enforced

**Result:** [ ]
**Notes:**

---

#### list_opted_in_projects

**Test ID:** MCP-028
**Scenario:** List consented projects
**Steps:**
1. Opt-in several projects
2. Call `list_opted_in_projects`

**Expected:**
- ✅ Returns all opted-in projects
- ✅ Accurate list

**Test:**
- [ ] List is correct
- [ ] Recently opted-in included
- [ ] Opted-out excluded

**Result:** [ ]
**Notes:**

---

### 2.4 Performance Monitoring Tools

#### get_performance_metrics

**Test ID:** MCP-029
**Scenario:** Fetch current performance metrics
**Steps:**
1. Run several searches and indexes
2. Call `get_performance_metrics`

**Expected:**
- ✅ Returns current metrics snapshot
- ✅ Search latency, cache hit rate, etc.
- ✅ Realistic values

**Test:**
- [ ] Metrics returned
- [ ] Values make sense
- [ ] Updated in real-time

**Result:** [ ]
**Notes:**

---

#### get_health_score

**Test ID:** MCP-030
**Scenario:** Get overall system health
**Steps:**
1. Call `get_health_score`

**Expected:**
- ✅ Returns score 0-100
- ✅ Component breakdown (performance, quality, capacity, usage)
- ✅ Realistic score

**Test:**
- [ ] Score in valid range
- [ ] Components detailed
- [ ] Score reflects system state

**Critical Check (BUG-024):**
- [ ] Quality score is NOT artificially low (should be 60-90, not stuck at 40)
- [ ] Relevance logging working

**Result:** [ ]
**Notes:**

---

#### get_active_alerts

**Test ID:** MCP-031
**Scenario:** View system alerts
**Steps:**
1. Trigger alert conditions (if possible)
2. Call `get_active_alerts`

**Expected:**
- ✅ Returns active alerts
- ✅ Severity levels shown
- ✅ Actionable messages

**Test:**
- [ ] Alerts listed
- [ ] Severity clear
- [ ] Messages helpful

**Result:** [ ]
**Notes:**

---

### 2.5 Documentation Tools

#### ingest_docs

**Test ID:** MCP-032
**Scenario:** Ingest markdown documentation
**Steps:**
1. Create docs/ folder with .md files
2. Call `ingest_docs`

**Expected:**
- ✅ All .md files ingested
- ✅ Chunked intelligently
- ✅ Searchable

**Test:**
- [ ] Docs ingested
- [ ] Chunk count reasonable
- [ ] Files processed count correct

**Result:** [ ]
**Notes:**

---

**Test ID:** MCP-033
**Scenario:** Search ingested documentation
**Steps:**
1. Ingest docs
2. Use `retrieve_memories` or `search_all` to query docs

**Expected:**
- ✅ Relevant doc sections returned
- ✅ High relevance scores

**Test:**
- [ ] Docs searchable
- [ ] Results relevant

**Result:** [ ]
**Notes:**

---

### 2.6 Utility Tools

#### get_status

**Test ID:** MCP-034
**Scenario:** System statistics overview
**Steps:**
1. Call `get_status`

**Expected:**
- ✅ Memory count
- ✅ Indexed projects count
- ✅ Total files indexed
- ✅ Total semantic units
- ✅ Storage backend info
- ✅ Parser info

**Test:**
- [ ] All stats present
- [ ] Counts accurate
- [ ] Performance metrics shown

**Result:** [ ]
**Notes:**

---

#### show_context

**Test ID:** MCP-035
**Scenario:** Debug current context (dev tool)
**Steps:**
1. Call `show_context`

**Expected:**
- ✅ Shows current session context
- ✅ Useful for debugging

**Test:**
- [ ] Context displayed
- [ ] Helpful for troubleshooting

**Result:** [ ]
**Notes:**

---

## 3. CLI Commands Tests (28+ Commands)

### 3.1 Core Commands

#### index command

**Test ID:** CLI-001
**Scenario:** Index via CLI
**Steps:**
1. Run: `python -m src.cli index ./src --project-name test-project`

**Expected:**
- ✅ Indexes all files in directory
- ✅ Progress bar/indicators
- ✅ Summary with counts
- ✅ Time estimate (if available)

**Test:**
- [ ] Command succeeds
- [ ] Progress shown
- [ ] Summary accurate
- [ ] Files indexed: _____
- [ ] Units extracted: _____
- [ ] Time: _____ seconds

**Result:** [ ]
**Notes:**

---

**Test ID:** CLI-002
**Scenario:** Index with --recursive flag
**Steps:**
1. Run: `python -m src.cli index ./src --recursive --project-name test`

**Expected:**
- ✅ Recurses into subdirectories
- ✅ All nested files indexed

**Test:**
- [ ] Recursion works
- [ ] Nested files found

**Result:** [ ]
**Notes:**

---

**Test ID:** CLI-003
**Scenario:** Index with file type filter
**Steps:**
1. Run with specific file extensions or types

**Expected:**
- ✅ Only specified file types indexed

**Test:**
- [ ] Filter works

**Result:** [ ]
**Notes:**

---

#### watch command

**Test ID:** CLI-004
**Scenario:** File watcher for auto-reindexing
**Steps:**
1. Run: `python -m src.cli watch ./src`
2. Modify a file in src/
3. Observe auto-reindex

**Expected:**
- ✅ Watcher starts without errors
- ✅ Detects file changes
- ✅ Auto-reindexes changed files
- ✅ Debouncing works (batches rapid changes)

**Test:**
- [ ] Watcher starts
- [ ] File change detected
- [ ] Auto-reindex triggered
- [ ] Debounce time: _____ ms

**Result:** [ ]
**Notes:**

---

**Test ID:** CLI-005
**Scenario:** Watch with custom debounce
**Steps:**
1. Run: `python -m src.cli watch ./src --debounce 500`

**Expected:**
- ✅ Custom debounce applied
- ✅ Batches changes within 500ms window

**Test:**
- [ ] Debounce setting works

**Result:** [ ]
**Notes:**

---

#### health command

**Test ID:** CLI-006
**Scenario:** System health check
**Steps:**
1. Run: `python -m src.cli health`

**Expected:**
- ✅ Comprehensive health report
- ✅ All components checked:
  - Storage backend (Qdrant)
  - Parser (Rust/Python)
  - Embedding model
  - Cache
  - Disk space
  - Memory usage
- ✅ Color-coded status (green/yellow/red)
- ✅ Actionable warnings

**Test:**
- [ ] Report complete
- [ ] All components shown
- [ ] Status colors visible
- [ ] Warnings actionable

**Critical Check (BUG-015):**
- [ ] Qdrant check uses correct endpoint (/ not /health)
- [ ] No false negatives

**Result:** [ ]
**Notes:**

---

#### validate-install command

**Test ID:** CLI-007
**Scenario:** Installation validation
**Steps:**
1. Run: `python -m src.cli validate-install`

**Expected:**
- ✅ Checks all dependencies
- ✅ Checks Qdrant
- ✅ Checks parsers
- ✅ Runs functionality tests
- ✅ Pass/fail for each check

**Test:**
- [ ] All checks run
- [ ] Pass/fail clear
- [ ] Errors actionable

**Result:** [ ]
**Notes:**

---

#### validate-setup command

**Test ID:** CLI-008
**Scenario:** Setup validation
**Steps:**
1. Run: `python -m src.cli validate-setup`

**Expected:**
- ✅ Validates Qdrant connection
- ✅ Validates config
- ✅ Clear success/fail

**Test:**
- [ ] Validation succeeds
- [ ] Qdrant check accurate

**Result:** [ ]
**Notes:**

---

#### status command

**Test ID:** CLI-009
**Scenario:** System status overview
**Steps:**
1. Run: `python -m src.cli status`

**Expected:**
- ✅ Same as `get_status` MCP tool
- ✅ Formatted for CLI
- ✅ Readable layout

**Test:**
- [ ] Status displayed
- [ ] Formatting good
- [ ] Info complete

**Result:** [ ]
**Notes:**

---

### 3.2 Memory Management Commands

#### browse command

**Test ID:** CLI-010
**Scenario:** Interactive memory browser (TUI)
**Steps:**
1. Store several memories
2. Run: `python -m src.cli browse`

**Expected:**
- ✅ TUI launches
- ✅ Memories listed
- ✅ Search box works
- ✅ Filters work
- ✅ Real-time search
- ✅ Keyboard navigation
- ✅ Escape to exit

**Test:**
- [ ] TUI starts without errors
- [ ] All memories shown
- [ ] Search functional
- [ ] Filters functional
- [ ] Navigation smooth
- [ ] Exit works

**UX Quality:**
- [ ] Professional appearance
- [ ] No layout glitches
- [ ] Clear instructions
- [ ] Responsive to input

**Result:** [ ]
**Notes:**

---

#### export command

**Test ID:** CLI-011
**Scenario:** Export memories to file
**Steps:**
1. Run: `python -m src.cli export --output memories.json`

**Expected:**
- ✅ Exports all memories
- ✅ Valid JSON format
- ✅ All fields preserved

**Test:**
- [ ] Export succeeds
- [ ] File created
- [ ] JSON valid
- [ ] Data complete

**Result:** [ ]
**Notes:**

---

**Test ID:** CLI-012
**Scenario:** Export to Markdown
**Steps:**
1. Run: `python -m src.cli export --format markdown --output memories.md`

**Expected:**
- ✅ Markdown format
- ✅ Readable structure
- ✅ All data included

**Test:**
- [ ] Markdown file created
- [ ] Readable and well-formatted

**Result:** [ ]
**Notes:**

---

#### import command

**Test ID:** CLI-013
**Scenario:** Import memories from file
**Steps:**
1. Export memories to file
2. Clear database (or use different instance)
3. Import: `python -m src.cli import memories.json`

**Expected:**
- ✅ Imports all memories
- ✅ Conflict resolution options
- ✅ No data loss

**Test:**
- [ ] Import succeeds
- [ ] All memories restored
- [ ] Searchable immediately

**Result:** [ ]
**Notes:**

---

#### tags command

**Test ID:** CLI-014
**Scenario:** Manage memory tags
**Steps:**
1. Run: `python -m src.cli tags list`

**Expected:**
- ✅ Lists all tags
- ✅ Shows memory count per tag
- ✅ Hierarchical display (if hierarchical tags)

**Test:**
- [ ] Tags listed
- [ ] Counts accurate

**Result:** [ ]
**Notes:**

---

#### collections command

**Test ID:** CLI-015
**Scenario:** Manage memory collections
**Steps:**
1. Run: `python -m src.cli collections list`

**Expected:**
- ✅ Lists all collections
- ✅ Shows memory count

**Test:**
- [ ] Collections shown

**Result:** [ ]
**Notes:**

---

#### auto-tag command

**Test ID:** CLI-016
**Scenario:** Auto-tag memories
**Steps:**
1. Run: `python -m src.cli auto-tag --dry-run`

**Expected:**
- ✅ Analyzes memories
- ✅ Suggests tags
- ✅ Dry-run shows preview
- ✅ Actual run applies tags

**Test:**
- [ ] Auto-tagging works
- [ ] Suggestions reasonable
- [ ] Dry-run accurate

**Result:** [ ]
**Notes:**

---

### 3.3 Project Management Commands

#### project command

**Test ID:** CLI-017
**Scenario:** List indexed projects
**Steps:**
1. Index multiple projects
2. Run: `python -m src.cli project list`

**Expected:**
- ✅ All projects listed
- ✅ Metadata shown (file count, unit count, last indexed)

**Test:**
- [ ] Projects listed
- [ ] Info accurate

**Result:** [ ]
**Notes:**

---

**Test ID:** CLI-018
**Scenario:** Project statistics
**Steps:**
1. Run: `python -m src.cli project stats <project-name>`

**Expected:**
- ✅ Detailed stats for project
- ✅ File count, unit count, languages, size

**Test:**
- [ ] Stats displayed
- [ ] All metrics present

**Result:** [ ]
**Notes:**

---

#### archival command

**Test ID:** CLI-019
**Scenario:** Archive inactive project
**Steps:**
1. Index a project
2. Run: `python -m src.cli archival archive <project-name>`

**Expected:**
- ✅ Project archived
- ✅ Compressed
- ✅ Storage reduction ~60-80%
- ✅ Still listed in archival status

**Test:**
- [ ] Archival succeeds
- [ ] Size reduction: _____ %
- [ ] Project still queryable (but archived)

**Result:** [ ]
**Notes:**

---

**Test ID:** CLI-020
**Scenario:** Reactivate archived project
**Steps:**
1. Archive a project
2. Run: `python -m src.cli archival reactivate <project-name>`

**Expected:**
- ✅ Project restored quickly (5-30s)
- ✅ Fully functional

**Test:**
- [ ] Reactivation succeeds
- [ ] Time: _____ seconds
- [ ] Searchable again

**Result:** [ ]
**Notes:**

---

**Test ID:** CLI-021
**Scenario:** Export archived project
**Steps:**
1. Archive a project
2. Run: `python -m src.cli archival export <project-name>`

**Expected:**
- ✅ Creates portable .tar.gz file
- ✅ Includes manifest and README

**Test:**
- [ ] Export file created
- [ ] Size: _____ MB
- [ ] Portable (can copy to another machine)

**Result:** [ ]
**Notes:**

---

**Test ID:** CLI-022
**Scenario:** Import archived project
**Steps:**
1. Import exported archive: `python -m src.cli archival import <file.tar.gz>`

**Expected:**
- ✅ Project imported successfully
- ✅ 100% integrity
- ✅ Searchable

**Test:**
- [ ] Import succeeds
- [ ] Data intact

**Result:** [ ]
**Notes:**

---

#### workspace command

**Test ID:** CLI-023
**Scenario:** Workspace management
**Steps:**
1. Run: `python -m src.cli workspace list`

**Expected:**
- ✅ Lists workspaces (if feature implemented)

**Test:**
- [ ] Works or returns clear "not implemented" message

**Result:** [ ]
**Notes:**

---

#### repository command

**Test ID:** CLI-024
**Scenario:** Repository management
**Steps:**
1. Run: `python -m src.cli repository list`

**Expected:**
- ✅ Lists repositories

**Test:**
- [ ] Command works

**Result:** [ ]
**Notes:**

---

### 3.4 Maintenance Commands

#### prune command

**Test ID:** CLI-025
**Scenario:** Prune old or unused memories
**Steps:**
1. Run: `python -m src.cli prune --dry-run`

**Expected:**
- ✅ Shows what would be deleted
- ✅ Actual run deletes them
- ✅ Confirmation prompt

**Test:**
- [ ] Dry-run shows candidates
- [ ] Confirmation requested
- [ ] Pruning works

**Result:** [ ]
**Notes:**

---

#### backup command

**Test ID:** CLI-026
**Scenario:** Create backup
**Steps:**
1. Run: `python -m src.cli backup create`

**Expected:**
- ✅ Creates backup file
- ✅ Includes all data
- ✅ Timestamped filename

**Test:**
- [ ] Backup created
- [ ] File size reasonable
- [ ] Timestamp in filename

**Result:** [ ]
**Notes:**

---

**Test ID:** CLI-027
**Scenario:** Restore from backup
**Steps:**
1. Create backup
2. Clear data
3. Run: `python -m src.cli backup restore <file>`

**Expected:**
- ✅ Restores all data
- ✅ No data loss

**Test:**
- [ ] Restore succeeds
- [ ] All data back

**Result:** [ ]
**Notes:**

---

#### analytics command

**Test ID:** CLI-028
**Scenario:** Usage analytics
**Steps:**
1. Run: `python -m src.cli analytics`

**Expected:**
- ✅ Shows usage statistics
- ✅ Query counts, token usage, etc.

**Test:**
- [ ] Analytics displayed
- [ ] Metrics useful

**Result:** [ ]
**Notes:**

---

#### lifecycle command

**Test ID:** CLI-029
**Scenario:** Memory lifecycle management
**Steps:**
1. Run: `python -m src.cli lifecycle status`

**Expected:**
- ✅ Shows memory lifecycle states
- ✅ Counts per state (ACTIVE, DORMANT, ARCHIVED, etc.)

**Test:**
- [ ] Lifecycle info shown

**Result:** [ ]
**Notes:**

---

### 3.5 Monitoring Commands

#### health-dashboard command

**Test ID:** CLI-030
**Scenario:** Start health dashboard
**Steps:**
1. Run: `python -m src.cli health-dashboard`

**Expected:**
- ✅ Starts web server
- ✅ Dashboard accessible in browser
- ✅ Shows real-time health metrics

**Test:**
- [ ] Server starts
- [ ] Dashboard loads in browser
- [ ] Metrics display correctly

**UX Quality:**
- [ ] Professional appearance
- [ ] Charts render correctly
- [ ] Responsive design

**Result:** [ ]
**Notes:**

---

#### schedule command

**Test ID:** CLI-031
**Scenario:** Schedule automated tasks
**Steps:**
1. Run: `python -m src.cli schedule list`

**Expected:**
- ✅ Shows scheduled tasks
- ✅ Next run times

**Test:**
- [ ] Schedules listed

**Result:** [ ]
**Notes:**

---

#### health-schedule command

**Test ID:** CLI-032
**Scenario:** Health check scheduling
**Steps:**
1. Run: `python -m src.cli health-schedule status`

**Expected:**
- ✅ Shows health check schedule

**Test:**
- [ ] Command works

**Result:** [ ]
**Notes:**

---

### 3.6 Utility Commands

#### session-summary command

**Test ID:** CLI-033
**Scenario:** Generate session summary
**Steps:**
1. Use system for a while
2. Run: `python -m src.cli session-summary`

**Expected:**
- ✅ Summarizes session activity
- ✅ Memories stored, searches run, etc.

**Test:**
- [ ] Summary generated
- [ ] Accurate stats

**Result:** [ ]
**Notes:**

---

#### tutorial command

**Test ID:** CLI-034
**Scenario:** Interactive tutorial
**Steps:**
1. Run: `python -m src.cli tutorial`

**Expected:**
- ✅ Guides user through features
- ✅ Interactive steps

**Test:**
- [ ] Tutorial runs
- [ ] Helpful and clear

**Result:** [ ]
**Notes:**

---

## 4. Code Search & Indexing Tests

### 4.1 Language Support

**Test ID:** CODE-001
**Scenario:** Python indexing and search
**Steps:**
1. Index Python project
2. Verify functions, classes, methods extracted
3. Search for specific function

**Expected:**
- ✅ All Python constructs indexed
- ✅ Accurate line numbers
- ✅ Semantic search works

**Test:**
- [ ] Functions extracted
- [ ] Classes extracted
- [ ] Methods extracted
- [ ] Search finds them

**Result:** [ ]
**Notes:**

---

**Test ID:** CODE-002
**Scenario:** JavaScript/TypeScript indexing
**Steps:**
1. Index JS/TS project
2. Verify functions, classes, arrow functions extracted

**Expected:**
- ✅ All JS/TS constructs indexed

**Test:**
- [ ] Functions extracted
- [ ] Arrow functions extracted
- [ ] Classes extracted

**Result:** [ ]
**Notes:**

---

**Test ID:** CODE-003
**Scenario:** Multi-language project
**Languages:** Python, JS, TS, Java, Go, Rust, Ruby, Swift, Kotlin, PHP, C, C++, C#, SQL
**Steps:**
1. Create project with files in all 14 languages
2. Index the project

**Expected:**
- ✅ All 14 languages parsed
- ✅ Semantic units extracted from all
- ✅ No parser errors

**Test:**
- [ ] Python: ✅/❌
- [ ] JavaScript: ✅/❌
- [ ] TypeScript: ✅/❌
- [ ] Java: ✅/❌
- [ ] Go: ✅/❌
- [ ] Rust: ✅/❌
- [ ] Ruby: ✅/❌
- [ ] Swift: ✅/❌
- [ ] Kotlin: ✅/❌
- [ ] PHP: ✅/❌ (BUG-021 check)
- [ ] C: ✅/❌
- [ ] C++: ✅/❌
- [ ] C#: ✅/❌
- [ ] SQL: ✅/❌

**Result:** [ ]
**Notes:**

---

**Test ID:** CODE-004
**Scenario:** Configuration file support
**Formats:** JSON, YAML, TOML
**Steps:**
1. Index project with config files

**Expected:**
- ✅ Config files indexed (if supported)

**Test:**
- [ ] JSON files indexed
- [ ] YAML files indexed
- [ ] TOML files indexed

**Result:** [ ]
**Notes:**

---

### 4.2 Performance Tests

**Test ID:** CODE-005
**Scenario:** Indexing speed - small project
**Size:** 10-20 files, ~100 semantic units
**Steps:**
1. Time the indexing

**Expected:**
- ✅ Completes in < 5 seconds
- ✅ 10-20 files/sec throughput

**Test:**
- [ ] Time: _____ seconds
- [ ] Throughput: _____ files/sec

**Result:** [ ]
**Notes:**

---

**Test ID:** CODE-006
**Scenario:** Indexing speed - medium project
**Size:** 100-200 files, ~1000 units
**Steps:**
1. Time the indexing

**Expected:**
- ✅ Completes in < 30 seconds
- ✅ 10-20 files/sec with parallel embeddings

**Test:**
- [ ] Time: _____ seconds
- [ ] Throughput: _____ files/sec
- [ ] Parallel embeddings enabled: Y/N

**Result:** [ ]
**Notes:**

---

**Test ID:** CODE-007
**Scenario:** Search latency
**Steps:**
1. Index a medium project
2. Run 20 searches, measure time

**Expected:**
- ✅ Semantic search: 7-13ms average
- ✅ Keyword search: 3-7ms average
- ✅ Hybrid search: 10-18ms average
- ✅ P95 latency < 50ms

**Test:**
- [ ] Semantic avg: _____ ms
- [ ] Keyword avg: _____ ms
- [ ] Hybrid avg: _____ ms
- [ ] P95: _____ ms

**Result:** [ ]
**Notes:**

---

**Test ID:** CODE-008
**Scenario:** Cache hit rate on re-index
**Steps:**
1. Index a project
2. Re-index without changes

**Expected:**
- ✅ Cache hit rate > 98%
- ✅ 5-10x faster than initial index

**Test:**
- [ ] Cache hit rate: _____ %
- [ ] Initial time: _____ s
- [ ] Re-index time: _____ s
- [ ] Speedup: _____ x

**Result:** [ ]
**Notes:**

---

### 4.3 Accuracy Tests

**Test ID:** CODE-009
**Scenario:** Semantic relevance
**Steps:**
1. Index a project
2. Search: "user authentication"
3. Manually verify results

**Expected:**
- ✅ Top 3 results are auth-related
- ✅ No irrelevant results in top 10
- ✅ Scores correlate with relevance

**Test:**
- [ ] Top 3 relevant: Y/N
- [ ] Any false positives in top 10: Y/N
- [ ] Scores make sense: Y/N

**Result:** [ ]
**Notes:**

---

**Test ID:** CODE-010
**Scenario:** Hybrid search accuracy
**Steps:**
1. Search with hybrid mode
2. Compare to pure semantic

**Expected:**
- ✅ Better precision with hybrid
- ✅ Keyword matches highlighted

**Test:**
- [ ] Hybrid more accurate than semantic alone: Y/N
- [ ] Keywords highlighted: Y/N

**Result:** [ ]
**Notes:**

---

### 4.4 Edge Cases

**Test ID:** CODE-011
**Scenario:** Large files (>10,000 lines)
**Steps:**
1. Index a very large file

**Expected:**
- ✅ Parses without memory errors
- ✅ Extracts all units
- ✅ Reasonable time

**Test:**
- [ ] Large file handled: Y/N
- [ ] Time: _____ ms

**Result:** [ ]
**Notes:**

---

**Test ID:** CODE-012
**Scenario:** Files with syntax errors
**Steps:**
1. Index a file with invalid Python syntax

**Expected:**
- ✅ Graceful error handling
- ✅ Clear error message
- ✅ Continues with other files

**Test:**
- [ ] Error handled gracefully: Y/N
- [ ] Other files still indexed: Y/N

**Result:** [ ]
**Notes:**

---

**Test ID:** CODE-013
**Scenario:** Binary files and images
**Steps:**
1. Index directory with .jpg, .png, .exe files

**Expected:**
- ✅ Binary files skipped
- ✅ No errors thrown
- ✅ Log message indicates skipping

**Test:**
- [ ] Binary files skipped: Y/N
- [ ] No errors: Y/N

**Result:** [ ]
**Notes:**

---

**Test ID:** CODE-014
**Scenario:** Very deep directory nesting
**Steps:**
1. Create directory 20+ levels deep
2. Index from root

**Expected:**
- ✅ Recurses to all levels
- ✅ No stack overflow
- ✅ All files found

**Test:**
- [ ] Deep recursion works: Y/N

**Result:** [ ]
**Notes:**

---

## 5. Memory Management Tests

### 5.1 Storage & Retrieval

**Test ID:** MEM-001
**Scenario:** Store and retrieve 1000 memories
**Steps:**
1. Store 1000 diverse memories
2. Retrieve random samples

**Expected:**
- ✅ All stored successfully
- ✅ All retrievable
- ✅ No data corruption

**Test:**
- [ ] 1000 stored: Y/N
- [ ] All retrievable: Y/N
- [ ] Sample check: ___/10 correct

**Result:** [ ]
**Notes:**

---

**Test ID:** MEM-002
**Scenario:** Memory deduplication
**Steps:**
1. Store duplicate or very similar memories
2. Check for consolidation

**Expected:**
- ✅ Duplicates detected
- ✅ Consolidation offered or automatic
- ✅ No exact duplicates stored

**Test:**
- [ ] Deduplication works: Y/N

**Result:** [ ]
**Notes:**

---

**Test ID:** MEM-003
**Scenario:** Trust scoring
**Steps:**
1. Store memories with provenance
2. Check trust scores

**Expected:**
- ✅ Trust scores calculated
- ✅ Scores reflect provenance

**Test:**
- [ ] Trust scores present: Y/N
- [ ] Scores reasonable: Y/N

**Result:** [ ]
**Notes:**

---

### 5.2 Lifecycle Management

**Test ID:** MEM-004
**Scenario:** Memory lifecycle states
**States:** ACTIVE, DORMANT, ARCHIVED, EXPIRED
**Steps:**
1. Store memories
2. Check lifecycle transitions

**Expected:**
- ✅ Lifecycle states tracked
- ✅ Transitions automatic or manual

**Test:**
- [ ] Lifecycle tracking works: Y/N
- [ ] States accurate: Y/N

**Result:** [ ]
**Notes:**

---

### 5.3 Relationships

**Test ID:** MEM-005
**Scenario:** Memory relationships
**Types:** SUPERSEDES, CONTRADICTS, RELATED_TO
**Steps:**
1. Store related memories
2. Check relationships

**Expected:**
- ✅ Relationships tracked
- ✅ Queryable

**Test:**
- [ ] Relationships stored: Y/N
- [ ] Retrievable: Y/N

**Result:** [ ]
**Notes:**

---

## 6. Multi-Project & Cross-Project Tests

### 6.1 Project Isolation

**Test ID:** PROJ-001
**Scenario:** Verify project isolation
**Steps:**
1. Index project A
2. Index project B
3. Search project A

**Expected:**
- ✅ Only project A results returned
- ✅ Project B excluded (unless cross-project search)

**Test:**
- [ ] Isolation enforced: Y/N

**Result:** [ ]
**Notes:**

---

### 6.2 Cross-Project Search

**Test ID:** PROJ-002
**Scenario:** Cross-project search with consent
**Steps:**
1. Index and opt-in 3 projects
2. Search globally

**Expected:**
- ✅ Results from all 3 projects
- ✅ Project attribution clear

**Test:**
- [ ] Multi-project search works: Y/N
- [ ] Attribution shown: Y/N

**Result:** [ ]
**Notes:**

---

**Test ID:** PROJ-003
**Scenario:** Privacy enforcement
**Steps:**
1. Opt-in project A
2. Leave project B opted-out
3. Cross-project search

**Expected:**
- ✅ Project A included
- ✅ Project B excluded

**Test:**
- [ ] Privacy respected: Y/N

**Result:** [ ]
**Notes:**

---

## 7. Health Monitoring & Performance Tests

### 7.1 Health Scoring

**Test ID:** HEALTH-001
**Scenario:** Health score calculation
**Steps:**
1. Use system normally
2. Check health score

**Expected:**
- ✅ Score in 60-90 range (healthy system)
- ✅ Component breakdown shown
- ✅ Not artificially low (BUG-024 fix verified)

**Test:**
- [ ] Overall score: _____ /100
- [ ] Performance component: _____ /100
- [ ] Quality component: _____ /100 (should NOT be stuck at 40)
- [ ] Capacity component: _____ /100
- [ ] Usage component: _____ /100

**Result:** [ ]
**Notes:**

---

### 7.2 Alerts

**Test ID:** HEALTH-002
**Scenario:** Alert generation
**Steps:**
1. Trigger alert conditions (low disk, high latency, etc.)
2. Check alerts

**Expected:**
- ✅ Alerts generated
- ✅ Severity levels correct
- ✅ Actionable messages

**Test:**
- [ ] Alerts triggered: Y/N
- [ ] Messages helpful: Y/N

**Result:** [ ]
**Notes:**

---

### 7.3 Performance Metrics

**Test ID:** HEALTH-003
**Scenario:** Metrics collection
**Steps:**
1. Perform various operations
2. Check metrics

**Expected:**
- ✅ Search latency tracked
- ✅ Cache hit rate tracked
- ✅ Index time tracked
- ✅ Token usage tracked

**Test:**
- [ ] All metrics collected: Y/N
- [ ] Values accurate: Y/N

**Result:** [ ]
**Notes:**

---

## 8. Dashboard & TUI Tests

### 8.1 Web Dashboard

**Test ID:** DASH-001
**Scenario:** Dashboard startup
**Steps:**
1. Start dashboard: `python -m src.cli health-dashboard`
2. Open in browser

**Expected:**
- ✅ Server starts on port 8080
- ✅ Dashboard loads without errors
- ✅ All sections render

**Test:**
- [ ] Server starts: Y/N
- [ ] Page loads: Y/N
- [ ] No JS errors in console: Y/N

**Result:** [ ]
**Notes:**

---

**Test ID:** DASH-002
**Scenario:** Dashboard features (Phase 4 - completed)
**Steps:**
1. Test dark mode toggle
2. Test keyboard shortcuts
3. Test tooltips
4. Test loading states
5. Test error handling

**Expected:**
- ✅ Dark mode toggles smoothly
- ✅ Keyboard shortcuts work (/, r, d, c, ?, Esc)
- ✅ Tooltips on all controls
- ✅ Skeleton screens during loading
- ✅ Toast notifications for errors
- ✅ Auto-retry on network errors

**Test:**
- [ ] Dark mode: ✅/❌
- [ ] Keyboard shortcuts: ✅/❌
- [ ] Tooltips: ✅/❌
- [ ] Skeleton screens: ✅/❌
- [ ] Error toasts: ✅/❌
- [ ] Auto-retry: ✅/❌

**Result:** [ ]
**Notes:**

---

**Test ID:** DASH-003
**Scenario:** Dashboard search and filter (UX-034 - completed)
**Steps:**
1. Use global search bar
2. Apply filters (project, category, date, lifecycle)
3. Check URL parameters
4. Clear filters

**Expected:**
- ✅ Search works with 300ms debounce
- ✅ Filters apply in real-time
- ✅ URL params update
- ✅ Shareable filtered views
- ✅ Filter badges shown
- ✅ Empty state messaging

**Test:**
- [ ] Search functional: Y/N
- [ ] Filters work: Y/N
- [ ] URL params correct: Y/N
- [ ] Shareable: Y/N
- [ ] Clear filters works: Y/N

**Result:** [ ]
**Notes:**

---

**Test ID:** DASH-004
**Scenario:** Memory detail modal (UX-035 - completed)
**Steps:**
1. Click on a memory
2. View details in modal
3. Test modal interactions

**Expected:**
- ✅ Modal opens smoothly (fadeIn, slideUp)
- ✅ Full content displayed
- ✅ Syntax highlighting for code
- ✅ All metadata shown (tags, importance, provenance, timestamps)
- ✅ Escape key closes modal
- ✅ Click outside closes modal
- ✅ Responsive on mobile

**Test:**
- [ ] Modal opens: Y/N
- [ ] Content complete: Y/N
- [ ] Syntax highlighting: Y/N
- [ ] Escape closes: Y/N
- [ ] Click-outside closes: Y/N
- [ ] Mobile responsive: Y/N

**Result:** [ ]
**Notes:**

---

**Test ID:** DASH-005
**Scenario:** Dashboard UX quality
**Steps:**
1. Review overall appearance
2. Test responsiveness
3. Check accessibility

**Expected:**
- ✅ Professional, polished design
- ✅ Responsive on mobile/tablet
- ✅ No layout glitches
- ✅ Colors consistent
- ✅ Loading states smooth

**Test:**
- [ ] Professional appearance: Y/N
- [ ] Mobile responsive: Y/N
- [ ] No glitches: Y/N
- [ ] Good color scheme: Y/N

**Result:** [ ]
**Notes:**

---

### 8.2 Memory Browser TUI

**Test ID:** TUI-001
**Scenario:** Memory browser UX
**Steps:**
1. Run: `python -m src.cli browse`
2. Test all features

**Expected:**
- ✅ Clean, professional TUI
- ✅ Search works in real-time
- ✅ Filters accessible
- ✅ Keyboard navigation smooth
- ✅ No rendering glitches

**Test:**
- [ ] Professional look: Y/N
- [ ] Search responsive: Y/N
- [ ] Navigation smooth: Y/N
- [ ] No glitches: Y/N

**Result:** [ ]
**Notes:**

---

## 9. Configuration & Backend Tests

### 9.1 Storage Backend

**Test ID:** CFG-001
**Scenario:** Qdrant backend
**Steps:**
1. Configure Qdrant backend
2. Test all operations

**Expected:**
- ✅ All features work
- ✅ Semantic search functional
- ✅ Performance meets targets

**Test:**
- [ ] Qdrant works: Y/N
- [ ] Search < 20ms: Y/N

**Result:** [ ]
**Notes:**

---

**Test ID:** CFG-002
**Scenario:** SQLite fallback (deprecated)
**Steps:**
1. Try to use SQLite backend

**Expected:**
- ❌ Should NOT fallback automatically (REF-010)
- ✅ Clear error requiring Qdrant
- ✅ Actionable setup instructions

**Test:**
- [ ] No auto-fallback: Y/N
- [ ] Clear error: Y/N
- [ ] Qdrant required: Y/N

**Result:** [ ]
**Notes:**

---

### 9.2 Parser Options

**Test ID:** CFG-003
**Scenario:** Rust parser
**Steps:**
1. Build Rust module
2. Index a project

**Expected:**
- ✅ Fast parsing (1-6ms per file)
- ✅ All languages supported

**Test:**
- [ ] Rust parser works: Y/N
- [ ] Speed: _____ ms/file (avg)

**Result:** [ ]
**Notes:**

---

**Test ID:** CFG-004
**Scenario:** Python fallback parser
**Steps:**
1. Disable Rust parser
2. Index a project

**Expected:**
- ✅ Falls back to Python
- ✅ Slower but functional (10-20ms per file)
- ✅ Same semantic units extracted

**Test:**
- [ ] Fallback works: Y/N
- [ ] Speed: _____ ms/file (avg)
- [ ] Accuracy same: Y/N

**Result:** [ ]
**Notes:**

---

### 9.3 Configuration Files

**Test ID:** CFG-005
**Scenario:** JSON configuration
**Steps:**
1. Create `~/.claude-rag/config.json`
2. Set custom options

**Expected:**
- ✅ Config file loaded
- ✅ Options applied

**Test:**
- [ ] Config loaded: Y/N
- [ ] Options work: Y/N

**Result:** [ ]
**Notes:**

---

**Test ID:** CFG-006
**Scenario:** Environment variables
**Steps:**
1. Set environment variables
2. Verify they override defaults

**Expected:**
- ✅ Env vars take precedence
- ✅ All options configurable

**Test:**
- [ ] Env vars work: Y/N

**Result:** [ ]
**Notes:**

---

## 10. Documentation & Git History Tests

### 10.1 Documentation Ingestion

**Test ID:** DOC-001
**Scenario:** Ingest markdown docs
**Steps:**
1. Create docs/ folder with .md files
2. Ingest docs

**Expected:**
- ✅ All .md files processed
- ✅ Chunking preserves structure
- ✅ Searchable

**Test:**
- [ ] Ingestion succeeds: Y/N
- [ ] Chunks: _____ (should be > file count)
- [ ] Searchable: Y/N

**Result:** [ ]
**Notes:**

---

**Test ID:** DOC-002
**Scenario:** Documentation search accuracy
**Steps:**
1. Ingest docs
2. Search for specific topics

**Expected:**
- ✅ Relevant sections returned
- ✅ High relevance scores

**Test:**
- [ ] Relevant results: Y/N
- [ ] Scores > 0.7: Y/N

**Result:** [ ]
**Notes:**

---

### 10.2 Git History Search

**Test ID:** GIT-001
**Scenario:** Index git commit history
**Steps:**
1. Index a git repository
2. Search commit history

**Expected:**
- ✅ Commits indexed
- ✅ Semantic search over commit messages
- ✅ File changes tracked

**Test:**
- [ ] Git indexing works: Y/N
- [ ] Commit search works: Y/N

**Result:** [ ]
**Notes:**

---

**Test ID:** GIT-002
**Scenario:** File history search
**Steps:**
1. Search for changes to specific file

**Expected:**
- ✅ File history returned
- ✅ Diff content searchable

**Test:**
- [ ] File history works: Y/N

**Result:** [ ]
**Notes:**

---

## 11. Security & Validation Tests

### 11.1 Input Validation

**Test ID:** SEC-001
**Scenario:** SQL injection attempts
**Steps:**
1. Try to store memory with SQL injection patterns

**Expected:**
- ✅ Injection detected
- ✅ Input sanitized or rejected

**Test:**
- [ ] SQL injection blocked: Y/N

**Result:** [ ]
**Notes:**

---

**Test ID:** SEC-002
**Scenario:** Prompt injection attempts
**Steps:**
1. Try to store memory with prompt injection

**Expected:**
- ✅ Detected and blocked

**Test:**
- [ ] Prompt injection blocked: Y/N

**Result:** [ ]
**Notes:**

---

**Test ID:** SEC-003
**Scenario:** Command injection attempts
**Steps:**
1. Try command injection in file paths or parameters

**Expected:**
- ✅ Blocked or sanitized

**Test:**
- [ ] Command injection blocked: Y/N

**Result:** [ ]
**Notes:**

---

### 11.2 Read-Only Mode

**Test ID:** SEC-004
**Scenario:** Read-only mode enforcement
**Steps:**
1. Enable read-only mode
2. Try to store memory

**Expected:**
- ❌ Write operations blocked
- ✅ Clear error message

**Test:**
- [ ] Writes blocked: Y/N
- [ ] Error message clear: Y/N

**Result:** [ ]
**Notes:**

---

## 12. Error Handling & Edge Cases

### 12.1 Connectivity Errors

**Test ID:** ERR-001
**Scenario:** Qdrant unavailable
**Steps:**
1. Stop Qdrant container
2. Try to search or index

**Expected:**
- ✅ Clear error message
- ✅ Actionable instructions (start Qdrant)
- ✅ No crash

**Test:**
- [ ] Error handled gracefully: Y/N
- [ ] Message actionable: Y/N
- [ ] No crash: Y/N

**Result:** [ ]
**Notes:**

---

**Test ID:** ERR-002
**Scenario:** Out of disk space
**Steps:**
1. Fill disk (or simulate)
2. Try to index

**Expected:**
- ✅ Error detected
- ✅ Clear message
- ✅ No data corruption

**Test:**
- [ ] Error handled: Y/N
- [ ] Data safe: Y/N

**Result:** [ ]
**Notes:**

---

### 12.2 Concurrent Operations

**Test ID:** ERR-003
**Scenario:** Concurrent indexing
**Steps:**
1. Start indexing project A
2. Start indexing project B simultaneously

**Expected:**
- ✅ Both complete successfully
- ✅ No race conditions
- ✅ No data corruption

**Test:**
- [ ] Concurrent indexing works: Y/N
- [ ] No corruption: Y/N

**Result:** [ ]
**Notes:**

---

**Test ID:** ERR-004
**Scenario:** Concurrent searches
**Steps:**
1. Run 10 searches in parallel

**Expected:**
- ✅ All return results
- ✅ No errors
- ✅ Performance stable

**Test:**
- [ ] All searches succeed: Y/N
- [ ] Avg latency: _____ ms

**Result:** [ ]
**Notes:**

---

## 13. Performance Benchmarks

### 13.1 Documented Benchmarks

**Test ID:** PERF-001
**Scenario:** Verify documented performance claims
**Claims:**
- Semantic search: 7-13ms
- Hybrid search: 10-18ms
- Indexing: 10-20 files/sec (parallel)
- Cache hit rate: 98%
- P95 search latency: < 50ms

**Steps:**
1. Run benchmarks matching documentation

**Expected:**
- ✅ All claims verified

**Test:**
- [ ] Semantic search: _____ ms (target: 7-13ms)
- [ ] Hybrid search: _____ ms (target: 10-18ms)
- [ ] Indexing: _____ files/sec (target: 10-20)
- [ ] Cache hit rate: _____ % (target: 98%)
- [ ] P95 latency: _____ ms (target: <50ms)

**Result:** [ ]
**Notes:**

---

### 13.2 Scalability

**Test ID:** PERF-002
**Scenario:** Large codebase indexing
**Size:** 1000+ files
**Steps:**
1. Index a large project

**Expected:**
- ✅ Completes without errors
- ✅ Memory usage reasonable
- ✅ Performance degrades gracefully

**Test:**
- [ ] Indexing succeeds: Y/N
- [ ] Time: _____ minutes
- [ ] Memory peak: _____ MB
- [ ] Throughput: _____ files/sec

**Result:** [ ]
**Notes:**

---

**Test ID:** PERF-003
**Scenario:** Large memory database
**Size:** 10,000+ memories
**Steps:**
1. Store 10,000 memories
2. Test search performance

**Expected:**
- ✅ Search latency stable
- ✅ No significant degradation

**Test:**
- [ ] Search still < 20ms: Y/N
- [ ] Avg latency: _____ ms

**Result:** [ ]
**Notes:**

---

## 14. UX Quality Assessment

### 14.1 First-Time User Experience

**Test ID:** UX-001
**Scenario:** Complete first-time setup and usage
**Steps:**
1. Simulate fresh user
2. Follow README instructions only

**Expected:**
- ✅ Setup completes without external help
- ✅ No confusing errors
- ✅ Clear next steps at each stage
- ✅ Success within 5 minutes

**Test:**
- [ ] Setup succeeds independently: Y/N
- [ ] Time: _____ minutes
- [ ] Confusion points: [List]
- [ ] Improvements needed: [List]

**Result:** [ ]
**Notes:**

---

### 14.2 Error Message Quality

**Test ID:** UX-002
**Scenario:** Error message assessment
**Steps:**
1. Trigger various errors
2. Review all error messages

**Expected:**
- ✅ All errors have actionable messages
- ✅ Next steps clear
- ✅ No stack traces shown to user (unless debug mode)
- ✅ No "Contact support" without trying to help

**Test:**
- [ ] All errors actionable: Y/N
- [ ] Examples of good errors: [List]
- [ ] Examples of bad errors: [List]

**Result:** [ ]
**Notes:**

---

### 14.3 Documentation Quality

**Test ID:** UX-003
**Scenario:** Documentation accuracy
**Steps:**
1. Follow all examples in README, docs/API.md, docs/USAGE.md
2. Verify accuracy

**Expected:**
- ✅ All examples work as shown
- ✅ No outdated information
- ✅ Parameter names correct (BUG-017 verified fixed)

**Test:**
- [ ] Examples accurate: Y/N
- [ ] Outdated info found: [List]
- [ ] Missing documentation: [List]

**Result:** [ ]
**Notes:**

---

### 14.4 Consistency

**Test ID:** UX-004
**Scenario:** API consistency
**Steps:**
1. Review all MCP tool return structures
2. Check for inconsistencies

**Expected:**
- ✅ Consistent return structures
- ✅ Consistent success indicators (BUG-020 check)
- ✅ Consistent error formats

**Test:**
- [ ] Return structures consistent: Y/N
- [ ] Success field standardized: Y/N
- [ ] Inconsistencies found: [List]

**Result:** [ ]
**Notes:**

---

### 14.5 Performance Perception

**Test ID:** UX-005
**Scenario:** Perceived performance
**Steps:**
1. Use system for typical tasks
2. Assess "snappiness"

**Expected:**
- ✅ Operations feel instant (<100ms)
- ✅ Long operations have progress indicators
- ✅ No freezing or hanging

**Test:**
- [ ] Feels fast: Y/N
- [ ] Progress indicators present: Y/N
- [ ] Any laggy operations: [List]

**Result:** [ ]
**Notes:**

---

## Testing Complete

**Date Completed:** _____
**Total Test Time:** _____ hours
**Tests Passed:** _____ / _____
**Tests Failed:** _____ / _____
**Bugs Found:** _____ (see E2E_BUG_TRACKER.md)

**Overall Assessment:**
- [ ] Production ready
- [ ] Needs minor fixes
- [ ] Needs major fixes
- [ ] Not ready for release

**Summary Notes:**

---

**Next Steps:**
1. Review all bugs in E2E_BUG_TRACKER.md
2. Prioritize bug fixes
3. Retest failed scenarios
4. Update documentation for any inaccuracies found
