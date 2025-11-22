# E2E Testing Bug Tracker
# Claude Memory RAG Server v4.0

**Test Session:** [Date]
**Tester:** [Name]
**Version:** 4.0
**Environment:** [OS, Python version, Docker version]

---

## Bug Classification

### Severity Levels
- **🔴 CRITICAL** - Completely blocks core functionality, data loss, security issue
- **🟠 HIGH** - Major feature broken, significant UX degradation, requires workaround
- **🟡 MEDIUM** - Feature partially broken, moderate UX issue, has workaround
- **🟢 LOW** - Minor issue, cosmetic problem, enhancement

### Bug Categories
- **FUNC** - Functional bug (feature doesn't work)
- **PERF** - Performance issue (works but too slow)
- **UX** - User experience issue (confusing, requires workaround)
- **DOC** - Documentation inaccuracy or missing info
- **DATA** - Data integrity or consistency issue
- **SEC** - Security vulnerability
- **API** - API inconsistency or design issue

---

## Known Bugs (From TODO.md)

### 🔴 CRITICAL - HIGH PRIORITY

#### BUG-018: Memory Retrieval Not Finding Recently Stored Memories ⚠️ HIGH
**Test ID:** MCP-004
**Category:** FUNC, DATA
**Severity:** 🟠 HIGH
**Component:** Semantic search / memory retrieval
**Status:** NEEDS INVESTIGATION

**Description:**
Memories stored via `store_memory()` are not immediately retrievable via `retrieve_memories()`. Core functionality appears broken.

**Steps to Reproduce:**
1. Store a memory: "I prefer TypeScript for frontend"
2. Immediately retrieve with query: "TypeScript preferences"
3. Memory not found or very low score

**Expected Behavior:**
- Memory should be immediately retrievable
- High relevance score (>0.8)

**Actual Behavior:**
- Memory not found OR very low score
- Appears to work after some delay

**Impact:**
- Core functionality broken
- Poor user experience
- Appears system is not working

**Investigation Required:**
- [ ] Check embedding generation timing
- [ ] Check vector store indexing delay
- [ ] Check similarity threshold configuration
- [ ] Verify Qdrant collection refresh

**Workaround:** Wait a few seconds after storing before retrieving (UNACCEPTABLE)

**Related Tests:** MCP-001, MCP-004

---

#### BUG-022: Code Indexer Extracts Zero Semantic Units ⚠️ HIGH
**Test ID:** MCP-019
**Category:** FUNC
**Severity:** 🟠 HIGH
**Component:** Code indexing / parsing
**Status:** NEEDS INVESTIGATION

**Description:**
`index_codebase()` successfully indexes files but extracts 0 semantic units. Code search returns no meaningful results.

**Steps to Reproduce:**
1. Create test project with Python files containing functions and classes
2. Call `index_codebase` on the directory
3. Observe: "Indexed 11 files, 0 semantic units"

**Expected Behavior:**
- Should extract functions, classes, methods from Python files
- Example: 11 files → 50-100+ semantic units

**Actual Behavior:**
- Files indexed: 11
- Semantic units: 0
- Code search returns no results

**Impact:**
- Code search completely non-functional
- Semantic analysis broken
- Major feature unusable

**Investigation Required:**
- [ ] Check parser configuration (Rust vs Python)
- [ ] Verify tree-sitter grammar loading
- [ ] Check semantic unit extraction logic in incremental_indexer.py
- [ ] Test with different file types
- [ ] Verify MemoryCategory.CODE is used correctly

**Related Tests:** MCP-019, CODE-001, CODE-003

**Note:** May be related to BUG-012 (MemoryCategory.CODE), verify fix was complete

---

### 🟡 MEDIUM PRIORITY

#### BUG-015: Health Check False Negative for Qdrant ⚠️ MEDIUM
**Test ID:** CLI-006, INST-006
**Category:** UX, FUNC
**Severity:** 🟡 MEDIUM
**Component:** `src/cli/health_command.py:143`
**Status:** NEEDS FIX

**Description:**
Health check reports Qdrant as unreachable even when functional. Using wrong endpoint `/health` instead of `/`.

**Steps to Reproduce:**
1. Ensure Qdrant is running and functional
2. Run: `python -m src.cli health`
3. Observe: "Qdrant: ❌ Unreachable"
4. But: `curl http://localhost:6333/` returns valid JSON

**Expected Behavior:**
- Health check should report Qdrant as connected
- Green status indicator

**Actual Behavior:**
- Reports unreachable even when working
- Conflicts with validate-install

**Impact:**
- Misleading error messages
- Users restart Qdrant unnecessarily
- Conflicts with other commands

**Root Cause:**
- Using `/health` endpoint instead of `/`
- `/health` endpoint may not exist in Qdrant

**Fix:**
Change endpoint check from `/health` to `/` with JSON validation

**Related Tests:** CLI-006, INST-006

---

#### BUG-016: list_memories Returns Incorrect Total Count ⚠️ MEDIUM
**Test ID:** MCP-007
**Category:** DATA, API
**Severity:** 🟡 MEDIUM
**Component:** Memory management API
**Status:** NEEDS FIX

**Description:**
`list_memories()` returns `total: 0` even when results array contains memories.

**Steps to Reproduce:**
1. Store 10 memories
2. Call `list_memories` with no filters
3. Observe response: `{"memories": [...10 items...], "total": 0, "returned_count": 10}`

**Expected Behavior:**
```json
{
  "memories": [...],
  "total": 10,
  "returned_count": 10
}
```

**Actual Behavior:**
```json
{
  "memories": [...],
  "total": 0,  // WRONG
  "returned_count": 10  // Correct
}
```

**Impact:**
- Breaks pagination (can't determine total pages)
- Incorrect analytics
- Confusing API behavior

**Fix:**
Update `list_memories()` method to properly count and return total

**Related Tests:** MCP-007

---

#### BUG-020: Inconsistent Return Value Structures ⚠️ MEDIUM
**Test ID:** MCP-013
**Category:** API, UX
**Severity:** 🟡 MEDIUM
**Component:** API design consistency
**Status:** NEEDS STANDARDIZATION

**Description:**
Different methods use different success indicators. API is inconsistent.

**Examples:**
- `delete_memory`: Returns `{"deleted": true, "memory_id": "..."}`
- Tests expect: `{"success": true}`
- Other methods use: `{"status": "success"}`

**Expected Behavior:**
Consistent return structure across all methods:
- Option A: Always use `{"success": true}` or `{"success": false}`
- Option B: Always use `{"status": "success"}` or `{"status": "error"}`

**Actual Behavior:**
Mix of `success`, `status`, `deleted`, custom fields

**Impact:**
- Confusing API
- Error-prone client code
- Difficult to write generic error handlers

**Fix:**
Standardize on one approach across all MCP tools

**Related Tests:** MCP-013, UX-004

---

#### BUG-021: PHP Parser Initialization Warning ⚠️ LOW
**Test ID:** CODE-003
**Category:** FUNC, UX
**Severity:** 🟢 LOW
**Component:** `src/memory/python_parser.py`
**Status:** NEEDS INVESTIGATION

**Description:**
Warning displayed: "Failed to initialize php parser: module 'tree_sitter_php' has no attribute 'language'"

**Steps to Reproduce:**
1. Index a project containing PHP files
2. Observe warning in logs

**Expected Behavior:**
- PHP files indexed without warnings
- PHP parser initializes correctly

**Actual Behavior:**
- Warning shown
- PHP files may not be indexed correctly

**Impact:**
- PHP file indexing broken
- Log noise
- Language support incomplete (claims 17 languages, but PHP doesn't work)

**Investigation Required:**
- [ ] Check tree-sitter-php installation
- [ ] Verify tree-sitter-php API version
- [ ] Check if language() function exists
- [ ] Test with known-good PHP file

**Related Tests:** CODE-003

---

### 🟢 LOW PRIORITY / COSMETIC

#### BUG-019: Docker Container Shows "Unhealthy" Despite Working ⚠️ LOW
**Test ID:** INST-005
**Category:** UX
**Severity:** 🟢 LOW
**Component:** `docker-compose.yml` healthcheck
**Status:** NEEDS FIX

**Description:**
`docker ps` shows Qdrant as "(unhealthy)" even though fully functional.

**Steps to Reproduce:**
1. Start Qdrant: `docker-compose up -d`
2. Wait 30 seconds
3. Run: `docker ps`
4. Observe: STATUS shows "(unhealthy)"
5. But: System works perfectly, searches succeed

**Expected Behavior:**
- Docker healthcheck passes
- Shows "(healthy)"

**Actual Behavior:**
- Shows "(unhealthy)"
- Causes user confusion

**Impact:**
- User confusion
- Unnecessary container restarts
- Looks broken even though working

**Fix:**
Update Docker healthcheck configuration in docker-compose.yml

**Related Tests:** INST-005

---

## New Bugs Found During E2E Testing

### Template

```markdown
#### BUG-XXX: [Short Description] ⚠️ [PRIORITY]
**Test ID:** [Test ID from E2E_TEST_PLAN.md]
**Category:** [FUNC/PERF/UX/DOC/DATA/SEC/API]
**Severity:** [🔴/🟠/🟡/🟢]
**Component:** [File path or component name]
**Status:** [NEW/INVESTIGATING/IN PROGRESS/FIXED/WONTFIX]
**Discovered:** [Date]

**Description:**
[Clear description of the bug]

**Steps to Reproduce:**
1. Step 1
2. Step 2
3. Step 3

**Expected Behavior:**
[What should happen]

**Actual Behavior:**
[What actually happens]

**Impact:**
[How this affects users]

**Root Cause:**
[If known]

**Fix:**
[Proposed fix or workaround]

**Screenshots/Logs:**
[If applicable]

**Related Tests:** [Test IDs]
```

---

### Installation & Setup Bugs

<!-- Add bugs found during Installation & Setup tests here -->

---

### MCP Tools Bugs

<!-- Add bugs found during MCP tools tests here -->

---

### CLI Commands Bugs

<!-- Add bugs found during CLI tests here -->

---

### Code Search & Indexing Bugs

<!-- Add bugs found during Code Search tests here -->

---

### Memory Management Bugs

<!-- Add bugs found during Memory Management tests here -->

---

### Multi-Project Bugs

<!-- Add bugs found during Multi-Project tests here -->

---

### Health Monitoring Bugs

<!-- Add bugs found during Health Monitoring tests here -->

---

### Dashboard & TUI Bugs

<!-- Add bugs found during Dashboard tests here -->

---

### Configuration Bugs

<!-- Add bugs found during Configuration tests here -->

---

### Documentation Bugs

<!-- Add bugs found during Documentation tests here -->

---

### Security Bugs

<!-- Add bugs found during Security tests here -->

---

### Performance Bugs

<!-- Add bugs found during Performance tests here -->

---

### UX & Consistency Bugs

<!-- Add bugs found during UX tests here -->

---

## Bug Summary

**Total Bugs Found:** _____

### By Severity
- 🔴 CRITICAL: _____
- 🟠 HIGH: _____
- 🟡 MEDIUM: _____
- 🟢 LOW: _____

### By Category
- FUNC: _____
- PERF: _____
- UX: _____
- DOC: _____
- DATA: _____
- SEC: _____
- API: _____

### By Status
- NEW: _____
- INVESTIGATING: _____
- IN PROGRESS: _____
- FIXED: _____
- WONTFIX: _____

---

## Critical Issues Blocking Release

**Must fix before production:**
1. [List critical bugs that block release]
2. [...]

---

## Recommended Fix Priority

### Sprint 1 (Week 1)
- [ ] BUG-XXX: [Critical bug 1]
- [ ] BUG-XXX: [Critical bug 2]

### Sprint 2 (Week 2)
- [ ] BUG-XXX: [High priority bug 1]
- [ ] BUG-XXX: [High priority bug 2]

### Sprint 3 (Week 3)
- [ ] BUG-XXX: [Medium priority bugs]

### Backlog
- [ ] BUG-XXX: [Low priority / cosmetic]

---

## Testing Notes

### Environment Issues
[Note any environment-specific problems]

### Test Coverage Gaps
[Areas that need more testing]

### Positive Findings
[What worked really well]

### Recommendations
[General recommendations for improvement]

---

**Last Updated:** [Date]
**Next Review:** [Date]
