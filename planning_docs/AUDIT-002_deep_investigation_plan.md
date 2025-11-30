# AUDIT-002: Deep Investigation Plan (Second Pass)

**Created:** 2025-11-30
**Scope:** Second exhaustive pass with different investigation angles
**Methodology:** Cross-cutting concerns, data flow analysis, behavioral correctness
**Output:** TODO.md items with properly ranked priorities, no duplicates

---

## Investigation Philosophy

AUDIT-001 analyzed the codebase by module/component. AUDIT-002 uses **cross-cutting analysis** to find issues that span multiple modules and wouldn't be caught by component-focused review.

---

## Investigation Parts

### PART 1: Data Flow & State Mutation Analysis
**Focus:** Track data as it flows through the system, find mutation bugs
**Investigation Areas:**
- Memory objects: creation → storage → retrieval → update → deletion
- Embedding vectors: generation → caching → storage → search
- Configuration: load → validate → propagate → use
- Search results: query → expand → search → rank → filter → return

**Checklist:**
- [ ] Data modified after validation (TOCTOU bugs)
- [ ] Stale cache serving outdated data
- [ ] Partial updates leaving inconsistent state
- [ ] Missing defensive copies (mutable default args, shared references)
- [ ] State not reset between operations
- [ ] Data transformations losing information
- [ ] Type coercion causing data loss
- [ ] Encoding/decoding asymmetry

---

### PART 2: API Contract & Interface Compliance
**Focus:** Verify all implementations match their declared contracts
**Investigation Areas:**
- Abstract base class implementations
- Protocol/interface compliance
- Return type consistency
- Parameter validation at boundaries
- Documented vs actual behavior

**Checklist:**
- [ ] Abstract methods not fully implemented
- [ ] Return types don't match signatures
- [ ] Optional parameters with non-None defaults
- [ ] Subclasses violating Liskov Substitution Principle
- [ ] Public API behavior differs from docstrings
- [ ] Breaking changes in method signatures
- [ ] Inconsistent null handling across implementations

---

### PART 3: Error Propagation & Recovery Paths
**Focus:** Trace error handling from origin to user-visible result
**Investigation Areas:**
- Exception paths from store → service → server → MCP → user
- Error message quality and actionability
- Recovery mechanisms and their effectiveness
- Graceful degradation vs hard failure

**Checklist:**
- [ ] Errors losing context as they propagate
- [ ] Generic error messages hiding root cause
- [ ] Recovery that makes things worse
- [ ] Silent fallback to incorrect behavior
- [ ] Error handling that blocks retry
- [ ] Missing error codes for programmatic handling
- [ ] Inconsistent error response formats

---

### PART 4: Boundary Conditions & Limits
**Focus:** What happens at the edges of valid input ranges?
**Investigation Areas:**
- Numeric limits (0, 1, MAX_INT, negative)
- String limits (empty, whitespace, very long, unicode edge cases)
- Collection limits (empty, single item, very large)
- Time limits (past, future, epoch, timezone boundaries)

**Checklist:**
- [ ] Division by zero not guarded
- [ ] Integer overflow/underflow
- [ ] Empty string vs None confusion
- [ ] Off-by-one errors in loops/slices
- [ ] Pagination at boundaries (page 0, last page, beyond last)
- [ ] Date/time edge cases (DST, leap seconds, year 2038)
- [ ] Unicode normalization inconsistencies

---

### PART 5: Concurrency Invariants & Atomicity
**Focus:** What invariants could be violated under concurrent access?
**Investigation Areas:**
- Check-then-act patterns
- Read-modify-write without locks
- Collection modification during iteration
- Shared mutable state across async tasks

**Checklist:**
- [ ] TOCTOU (time-of-check-time-of-use) bugs
- [ ] Lost updates from concurrent writes
- [ ] Phantom reads during iteration
- [ ] Deadlock potential from lock ordering
- [ ] Starvation from unfair locking
- [ ] Memory visibility issues
- [ ] Async context variable leakage

---

### PART 6: Resource Lifecycle Management
**Focus:** Are all resources properly acquired, used, and released?
**Investigation Areas:**
- Database connections
- File handles
- Network sockets
- Thread pools and executors
- Temporary files and directories

**Checklist:**
- [ ] Resources acquired but never released
- [ ] Resources released in wrong order
- [ ] Resources used after release
- [ ] Missing cleanup in error paths
- [ ] Cleanup that can throw exceptions
- [ ] Resource exhaustion under load
- [ ] Orphaned resources on restart

---

### PART 7: Configuration Consistency & Coherence
**Focus:** Do configuration options work together correctly?
**Investigation Areas:**
- Feature flag combinations
- Performance tuning parameters
- Integration settings
- Environment-specific configs

**Checklist:**
- [ ] Conflicting feature flags
- [ ] Config values that contradict each other
- [ ] Settings that only work in certain combinations
- [ ] Missing validation of config relationships
- [ ] Config changes not taking effect
- [ ] Hot reload bugs
- [ ] Default values that cause immediate failure

---

### PART 8: Logging & Observability Completeness
**Focus:** Can operators diagnose problems from logs alone?
**Investigation Areas:**
- Log coverage of error paths
- Log level appropriateness
- Structured logging consistency
- Metric accuracy and completeness

**Checklist:**
- [ ] Error paths without logging
- [ ] DEBUG logs in production code paths
- [ ] Missing correlation IDs
- [ ] Inconsistent log formats
- [ ] Sensitive data in logs
- [ ] Metrics that don't reflect reality
- [ ] Missing health indicators

---

### PART 9: Backwards Compatibility & Migration
**Focus:** What breaks when upgrading?
**Investigation Areas:**
- Data format versioning
- API versioning
- Config file compatibility
- Database schema evolution

**Checklist:**
- [ ] Breaking changes without migration path
- [ ] Old data formats not readable
- [ ] Config options silently ignored
- [ ] Database schema assumptions
- [ ] Hardcoded version checks
- [ ] Missing deprecation warnings
- [ ] Import/export format changes

---

### PART 10: Default Behavior & Implicit Assumptions
**Focus:** What happens when users don't specify options?
**Investigation Areas:**
- Default parameter values
- Implicit behavior without user consent
- Assumed environment conditions
- Magic values and sentinel values

**Checklist:**
- [ ] Surprising default behavior
- [ ] Defaults that differ from documentation
- [ ] Implicit side effects
- [ ] Assumed file system layout
- [ ] Assumed network availability
- [ ] Magic numbers without explanation
- [ ] Sentinel values that could be valid data

---

### PART 11: Search & Retrieval Correctness
**Focus:** Does search actually return the right results?
**Investigation Areas:**
- Query parsing and interpretation
- Relevance scoring accuracy
- Filter application correctness
- Result ordering determinism

**Checklist:**
- [ ] Queries that should match but don't
- [ ] False positives in search results
- [ ] Inconsistent ordering between runs
- [ ] Filters that don't filter
- [ ] Score calculations that overflow
- [ ] Missing results due to pagination bugs
- [ ] Search returning deleted items

---

### PART 12: Indexing & Data Integrity
**Focus:** Is indexed data accurate and complete?
**Investigation Areas:**
- Code parsing accuracy
- Metadata extraction
- Relationship detection
- Update propagation

**Checklist:**
- [ ] Parsed code doesn't match source
- [ ] Missing relationships between entities
- [ ] Stale index after file changes
- [ ] Partial indexing on error
- [ ] Index corruption scenarios
- [ ] Duplicate entries
- [ ] Orphaned index entries

---

### PART 13: External Integration Points
**Focus:** How robust is interaction with external systems?
**Investigation Areas:**
- Qdrant client interactions
- Git command execution
- File system operations
- Optional dependency handling

**Checklist:**
- [ ] External service timeout handling
- [ ] Retry logic with backoff
- [ ] Circuit breaker patterns
- [ ] Graceful degradation
- [ ] Version compatibility checks
- [ ] Error translation from external errors
- [ ] Connection pool management

---

### PART 14: Memory Management & Performance
**Focus:** What causes memory bloat or performance degradation?
**Investigation Areas:**
- Large collection handling
- Streaming vs batch processing
- Cache sizing and eviction
- Object lifecycle and GC pressure

**Checklist:**
- [ ] Unbounded collections
- [ ] Large objects held too long
- [ ] Inefficient data structures
- [ ] N+1 query patterns
- [ ] Missing pagination
- [ ] Cache that never expires
- [ ] Memory leaks from callbacks/closures

---

### PART 15: CLI Behavioral Correctness
**Focus:** Do CLI commands do what users expect?
**Investigation Areas:**
- Command semantics
- Argument handling
- Output correctness
- Side effect management

**Checklist:**
- [ ] Commands that silently do nothing
- [ ] Destructive commands without confirmation
- [ ] Output that doesn't match action taken
- [ ] Arguments that are parsed but ignored
- [ ] Missing input validation
- [ ] Inconsistent behavior across commands
- [ ] Exit codes that lie

---

### PART 16: Test-Code Divergence
**Focus:** Do tests actually test the code they claim to?
**Investigation Areas:**
- Test setup vs production setup
- Mock behavior vs real behavior
- Test data vs production data
- Coverage vs correctness

**Checklist:**
- [ ] Tests that pass but don't test anything
- [ ] Mocks with wrong behavior
- [ ] Tests for removed code
- [ ] Tests that assume specific timing
- [ ] Fixtures that differ from production
- [ ] Tests that modify global state
- [ ] Assertions on wrong values

---

### PART 17: Code Duplication & Consistency
**Focus:** Where is logic duplicated and potentially inconsistent?
**Investigation Areas:**
- Copy-pasted code with slight differences
- Reimplemented standard patterns
- Inconsistent naming conventions
- Similar functions with different bugs

**Checklist:**
- [ ] Same logic in multiple places
- [ ] Validation done differently in different places
- [ ] Error messages with different formats
- [ ] Date formatting inconsistencies
- [ ] Path handling differences
- [ ] Collection processing differences
- [ ] Retry logic implemented differently

---

### PART 18: Hidden Dependencies & Coupling
**Focus:** What unexpected dependencies exist between components?
**Investigation Areas:**
- Import graph analysis
- Shared global state
- Implicit ordering requirements
- Hidden communication channels

**Checklist:**
- [ ] Circular import risks
- [ ] Global state mutations
- [ ] Order-dependent initialization
- [ ] Side effects through shared objects
- [ ] Implicit singleton assumptions
- [ ] Hidden file system dependencies
- [ ] Undocumented environment requirements

---

## Execution Plan

**Wave 1:** Parts 1-6 (Data flow, Contracts, Errors, Boundaries, Concurrency, Resources)
**Wave 2:** Parts 7-12 (Config, Logging, Compat, Defaults, Search, Indexing)
**Wave 3:** Parts 13-18 (External, Performance, CLI, Tests, Duplication, Dependencies)

## Ticket Numbering

To avoid conflicts with AUDIT-001 findings, use these prefixes:
- Start from BUG-150, REF-100, PERF-030, TEST-050, DOC-040, SEC-020, UX-080
