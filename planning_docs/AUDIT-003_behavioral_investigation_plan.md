# AUDIT-003: Behavioral & Semantic Investigation Plan (Third Pass)

**Created:** 2025-11-30
**Scope:** Third exhaustive pass with behavioral and semantic focus
**Methodology:** User journey analysis, failure modes, semantic correctness, anti-patterns
**Output:** TODO.md items with properly ranked priorities, no duplicates

---

## Investigation Philosophy

- AUDIT-001: Module-by-module structural analysis
- AUDIT-002: Cross-cutting technical concerns
- AUDIT-003: **Behavioral correctness, semantic meaning, user experience, failure recovery**

This pass focuses on whether the code does what it's *supposed* to do from a user's perspective.

---

## Investigation Parts

### PART 1: User Journey - Memory Storage & Retrieval
**Focus:** Trace complete user workflows for memory operations
**Scenarios to Test (mentally):**
- Store a memory → retrieve it immediately
- Store duplicate content → what happens?
- Update memory → search for old content
- Delete memory → ensure it's gone everywhere
- Store with invalid data → error handling

**Checklist:**
- [ ] Memory stored but not findable via search
- [ ] Deleted memories still appearing in results
- [ ] Updated memories returning stale data
- [ ] Duplicate detection working correctly
- [ ] Error messages actionable for users

---

### PART 2: User Journey - Code Indexing & Search
**Focus:** Trace complete indexing and code search workflows
**Scenarios:**
- Index a codebase → search for function
- Modify file → re-index → search reflects change
- Delete file → index updated
- Large codebase indexing → progress/completion
- Search with typo → helpful suggestions

**Checklist:**
- [ ] Indexed code not searchable
- [ ] File changes not reflected in search
- [ ] Deleted files still in index
- [ ] Progress indicators accurate
- [ ] Search suggestions helpful

---

### PART 3: Failure Mode Analysis - Storage Layer
**Focus:** What happens when storage fails?
**Failure Scenarios:**
- Qdrant unavailable at startup
- Qdrant dies mid-operation
- Qdrant returns corrupted data
- Disk full during write
- Network timeout during batch operation

**Checklist:**
- [ ] Clear error message for each failure
- [ ] System recoverable after failure
- [ ] No data corruption from partial writes
- [ ] Retry logic appropriate
- [ ] User can diagnose issue from error

---

### PART 4: Failure Mode Analysis - Embedding Generation
**Focus:** What happens when embedding generation fails?
**Failure Scenarios:**
- Model file missing/corrupted
- GPU out of memory
- Text too long for model
- Unicode that breaks tokenizer
- Parallel worker crashes

**Checklist:**
- [ ] Graceful fallback to CPU
- [ ] Large text handled (truncate or chunk)
- [ ] Worker crash doesn't lose work
- [ ] Error messages explain the issue
- [ ] Recovery without restart

---

### PART 5: State Machine Analysis - Memory Lifecycle
**Focus:** Are memory state transitions valid?
**States:** created → active → accessed → updated → archived → deleted
**Checklist:**
- [ ] Invalid state transitions prevented
- [ ] State consistent across operations
- [ ] Archived memories behave correctly
- [ ] Lifecycle hooks fire correctly
- [ ] State visible to users

---

### PART 6: State Machine Analysis - Indexing Jobs
**Focus:** Are indexing job states valid?
**States:** queued → running → completed/failed → retrying
**Checklist:**
- [ ] Jobs can't get stuck in invalid state
- [ ] Failed jobs properly marked
- [ ] Retry logic has max attempts
- [ ] Concurrent job handling correct
- [ ] Job status queryable

---

### PART 7: Semantic Correctness - Search Relevance
**Focus:** Do search results make semantic sense?
**Checklist:**
- [ ] Exact matches ranked highest
- [ ] Similar content found (not just keywords)
- [ ] Irrelevant results not included
- [ ] Empty queries handled sensibly
- [ ] Score explanations meaningful

---

### PART 8: Semantic Correctness - Code Analysis
**Focus:** Is code analysis semantically accurate?
**Checklist:**
- [ ] Function signatures parsed correctly
- [ ] Class hierarchies detected
- [ ] Import relationships accurate
- [ ] Complexity metrics meaningful
- [ ] Language detection correct

---

### PART 9: Anti-Pattern Detection - God Objects
**Focus:** Find classes/functions doing too much
**Checklist:**
- [ ] Classes with 20+ methods
- [ ] Functions with 100+ lines
- [ ] Methods with 10+ parameters
- [ ] Files with 1000+ lines
- [ ] Cyclomatic complexity > 20

---

### PART 10: Anti-Pattern Detection - Code Smells
**Focus:** Common bad patterns
**Checklist:**
- [ ] Long parameter lists
- [ ] Deep nesting (5+ levels)
- [ ] Boolean parameters changing behavior
- [ ] Comments explaining bad code
- [ ] Commented-out code
- [ ] TODO/FIXME/HACK comments

---

### PART 11: Dead Code & Unused Features
**Focus:** Code that serves no purpose
**Checklist:**
- [ ] Functions never called
- [ ] Classes never instantiated
- [ ] Parameters always same value
- [ ] Branches never taken
- [ ] Features documented but not implemented
- [ ] Config options that do nothing

---

### PART 12: Naming & Semantic Clarity
**Focus:** Do names reflect actual behavior?
**Checklist:**
- [ ] Function names that lie (get* that modifies)
- [ ] Variables with misleading names
- [ ] Inconsistent naming conventions
- [ ] Abbreviations without explanation
- [ ] Generic names (data, result, temp)

---

### PART 13: Magic Values & Hardcoding
**Focus:** Unexplained literal values
**Checklist:**
- [ ] Numbers without constants (0.7, 100, 30)
- [ ] Strings without constants ("error", paths)
- [ ] Repeated magic values (same number in multiple places)
- [ ] Environment assumptions (localhost, port numbers)
- [ ] Hardcoded credentials or paths

---

### PART 14: Rollback & Recovery Mechanisms
**Focus:** Can operations be undone?
**Checklist:**
- [ ] Failed batch operations recoverable
- [ ] Import/export reversible
- [ ] Configuration changes reversible
- [ ] Accidental deletion recoverable
- [ ] Upgrade path has rollback

---

### PART 15: Event Ordering & Sequencing
**Focus:** Do events happen in correct order?
**Checklist:**
- [ ] Initialization order dependencies
- [ ] Cleanup order (reverse of init)
- [ ] Event handlers fire in expected order
- [ ] Async operations complete before dependent ops
- [ ] Race conditions in event handling

---

### PART 16: Input Validation Completeness
**Focus:** Are all inputs validated?
**Checklist:**
- [ ] MCP tool parameters validated
- [ ] CLI arguments validated
- [ ] Config values validated
- [ ] File paths validated
- [ ] User-provided queries validated
- [ ] Validation errors helpful

---

### PART 17: Output Contract Verification
**Focus:** Do outputs match documented contracts?
**Checklist:**
- [ ] Return types match signatures
- [ ] Error responses follow format
- [ ] Success responses consistent
- [ ] Pagination works correctly
- [ ] Metadata complete and accurate

---

### PART 18: Future-Proofing & Extensibility
**Focus:** How hard is it to extend this code?
**Checklist:**
- [ ] Adding new storage backend
- [ ] Adding new language parser
- [ ] Adding new search algorithm
- [ ] Adding new MCP tool
- [ ] Modifying memory schema

---

## Execution Plan

**Wave 1:** Parts 1-6 (User journeys, Failure modes, State machines)
**Wave 2:** Parts 7-12 (Semantic correctness, Anti-patterns, Dead code, Naming)
**Wave 3:** Parts 13-18 (Magic values, Rollback, Events, Validation, Output, Future)

## Ticket Numbering

Start from: BUG-210, REF-160, PERF-060, TEST-080, UX-110, SEC-040, ARCH-010
