# Bug Hunting Sprint Plan

**Created:** 2025-11-29
**Status:** ACTIVE
**Goal:** Systematic bug hunting initiative for claude-memory-server v4.0 hardening

## Overview

Systematic bug hunting initiative for claude-memory-server. Organized into 8 themed workstreams that can be executed in parallel by different team members.

---

## Workstream 1: Storage & Connection Reliability
**Owner:** TBD
**Priority:** CRITICAL
**Estimated Tasks:** 12-15

### Focus Areas
- Qdrant connection pool exhaustion under load
- Connection leak detection (connections created vs returned)
- Timeout handling in store operations
- Batch operation failure modes
- Connection health checker edge cases

### Specific Tasks
1. **BUG-HUNT-001**: Test connection pool under sustained load (100+ concurrent operations)
2. **BUG-HUNT-002**: Verify connection release in all error paths (`src/store/qdrant_store.py`)
3. **BUG-HUNT-003**: Test behavior when Qdrant is unavailable mid-operation
4. **BUG-HUNT-004**: Audit `batch_store()` partial failure handling
5. **BUG-HUNT-005**: Test connection recycling based on age
6. **BUG-HUNT-006**: Verify health checker doesn't mask connection issues
7. **BUG-HUNT-007**: Test embedding dimension mismatch detection
8. **BUG-HUNT-008**: Audit `_get_client()` / `_release_client()` symmetry

### Key Files
- `src/store/qdrant_store.py` (2,989 lines)
- `src/store/connection_pool.py` (615 lines)
- `src/store/connection_health_checker.py`

---

## Workstream 2: Async & Concurrency Bugs
**Owner:** TBD
**Priority:** CRITICAL
**Estimated Tasks:** 10-12

### Focus Areas
- Race conditions in parallel operations
- Async/await correctness (78 async methods in server.py)
- Event loop handling in tests and production
- Task cancellation safety
- Deadlock potential in process pools

### Specific Tasks
1. **BUG-HUNT-010**: Audit all `asyncio.gather()` calls for proper exception handling
2. **BUG-HUNT-011**: Test parallel search + indexing simultaneously
3. **BUG-HUNT-012**: Verify EmbeddingCache thread-safety under concurrent access
4. **BUG-HUNT-013**: Test process pool executor shutdown under load
5. **BUG-HUNT-014**: Audit async initialization order dependencies in server
6. **BUG-HUNT-015**: Test file watcher event ordering under rapid changes
7. **BUG-HUNT-016**: Verify no async operations in `__init__` methods
8. **BUG-HUNT-017**: Test connection pool under concurrent acquire/release

### Key Files
- `src/core/server.py` (5,429 lines, 78 async methods)
- `src/embeddings/parallel_generator.py`
- `src/embeddings/cache.py`
- `src/memory/file_watcher.py`

---

## Workstream 3: Memory & Resource Leaks
**Owner:** TBD
**Priority:** HIGH
**Estimated Tasks:** 8-10

### Focus Areas
- Process pool memory management (PERF-009 context)
- Embedding cache growth bounds
- Metrics collector memory over time
- File handle leaks
- Background task accumulation

### Specific Tasks
1. **BUG-HUNT-020**: Profile memory during extended indexing sessions
2. **BUG-HUNT-021**: Verify embedding cache has proper LRU eviction
3. **BUG-HUNT-022**: Test MetricsCollector memory after 10K+ operations
4. **BUG-HUNT-023**: Audit file handle cleanup in incremental indexer
5. **BUG-HUNT-024**: Test parallel generator worker process cleanup
6. **BUG-HUNT-025**: Verify background health jobs don't accumulate
7. **BUG-HUNT-026**: Check for unbounded growth in tracking data structures

### Key Files
- `src/embeddings/parallel_generator.py` (PERF-009 fix location)
- `src/embeddings/cache.py`
- `src/monitoring/metrics_collector.py`
- `src/memory/incremental_indexer.py`

---

## Workstream 4: CLI Command Validation
**Owner:** TBD
**Priority:** HIGH
**Estimated Tasks:** 15-20

### Focus Areas
- 31 untested CLI modules - systematic validation
- Argument parsing edge cases
- Error message quality
- Exit codes correctness
- Output format consistency

### Specific Tasks
1. **BUG-HUNT-030**: Test each CLI command with missing required args
2. **BUG-HUNT-031**: Test each CLI command with invalid input types
3. **BUG-HUNT-032**: Verify all commands handle Qdrant unavailable gracefully
4. **BUG-HUNT-033**: Test `export_command.py` with non-writable paths
5. **BUG-HUNT-034**: Test `import_command.py` with malformed data
6. **BUG-HUNT-035**: Verify `git_search_command.py` in non-git directories
7. **BUG-HUNT-036**: Test health commands when services degraded
8. **BUG-HUNT-037**: Verify consistent JSON output format across commands
9. **BUG-HUNT-038**: Test lifecycle_command edge cases
10. **BUG-HUNT-039**: Test prune_command with active operations

### Untested CLI Files (Priority)
- `analytics_command.py`, `export_command.py`, `import_command.py`
- `git_search_command.py`, `health_monitor_command.py`
- `lifecycle_command.py`, `tags_command.py`, `perf_command.py`
- `project_command.py`, `prune_command.py`, `repository_command.py`
- `schedule_command.py`, `session_summary_command.py`

---

## Workstream 5: Data Integrity & Backup
**Owner:** TBD
**Priority:** CRITICAL
**Estimated Tasks:** 8-10

### Focus Areas
- Backup/restore data consistency
- Partial failure recovery
- Corruption detection
- Concurrent backup during writes
- Scheduler reliability

### Specific Tasks
1. **BUG-HUNT-040**: Test backup during active indexing
2. **BUG-HUNT-041**: Test restore with corrupted tar files
3. **BUG-HUNT-042**: Verify partial restore rollback
4. **BUG-HUNT-043**: Test hash verification on restore
5. **BUG-HUNT-044**: Test backup scheduler under system load
6. **BUG-HUNT-045**: Verify archival operations are atomic
7. **BUG-HUNT-046**: Test export with concurrent memory modifications
8. **BUG-HUNT-047**: Verify import validation catches malformed data

### Key Files
- `src/backup/exporter.py`
- `src/backup/importer.py`
- `src/backup/scheduler.py` (no tests!)

---

## Workstream 6: Search & Retrieval Correctness
**Owner:** TBD
**Priority:** HIGH
**Estimated Tasks:** 10-12

### Focus Areas
- Hybrid search (BM25 + vector) fusion correctness
- Cross-project search privacy/scoping
- Query result ranking consistency
- Edge cases in similarity detection
- Deduplication false positives/negatives

### Specific Tasks
1. **BUG-HUNT-050**: Test hybrid search with empty BM25 or vector results
2. **BUG-HUNT-051**: Verify cross-project search respects consent boundaries
3. **BUG-HUNT-052**: Test search with special characters in queries
4. **BUG-HUNT-053**: Verify deduplication doesn't merge distinct memories
5. **BUG-HUNT-054**: Test retrieval predictor edge cases (code snippets, complex queries)
6. **BUG-HUNT-055**: Verify search results are deterministic (same query = same order)
7. **BUG-HUNT-056**: Test multi-project filtering correctness
8. **BUG-HUNT-057**: Audit similarity threshold edge cases

### Key Files
- `src/search/hybrid_searcher.py`
- `src/memory/cross_project_search.py`
- `src/memory/duplicate_detector.py`
- `src/router/retrieval_predictor.py`

---

## Workstream 7: Monitoring & Health System
**Owner:** TBD
**Priority:** MEDIUM
**Estimated Tasks:** 8-10

### Focus Areas
- Alert storm prevention
- Remediation loop detection
- Metric collection overhead
- Health check accuracy
- Background job stability

### Specific Tasks
1. **BUG-HUNT-060**: Test alert deduplication under rapid failures
2. **BUG-HUNT-061**: Verify remediation doesn't trigger cascading actions
3. **BUG-HUNT-062**: Test health reporter under degraded conditions
4. **BUG-HUNT-063**: Verify metrics collection doesn't impact performance
5. **BUG-HUNT-064**: Test capacity planner with edge case data
6. **BUG-HUNT-065**: Audit background health job error handling
7. **BUG-HUNT-066**: Test health dashboard with partial data

### Key Files
- `src/monitoring/alert_engine.py` (18,509 lines)
- `src/monitoring/health_reporter.py` (17,483 lines)
- `src/monitoring/remediation.py` (17,244 lines)
- `src/memory/health_jobs.py`

---

## Workstream 8: Edge Cases & Boundary Conditions
**Owner:** TBD
**Priority:** MEDIUM
**Estimated Tasks:** 10-12

### Focus Areas
- Empty/null input handling
- Maximum size limits
- Unicode and special character handling
- Configuration boundary values
- Error message sanitization

### Specific Tasks
1. **BUG-HUNT-070**: Test all APIs with empty strings/lists
2. **BUG-HUNT-071**: Test with maximum allowed memory content size
3. **BUG-HUNT-072**: Verify Unicode handling in memory content and paths
4. **BUG-HUNT-073**: Test configuration with boundary values (0, -1, max)
5. **BUG-HUNT-074**: Verify error messages don't leak sensitive data
6. **BUG-HUNT-075**: Test with extremely long file paths
7. **BUG-HUNT-076**: Test with symlinks and special file types
8. **BUG-HUNT-077**: Verify behavior with read-only file systems

### Key Files
- `src/core/validation.py`
- `src/config.py`
- `src/core/exceptions.py`

---

## Team Assignment (6 Agents)

Given a team of 4-6 parallel agents, here's the recommended assignment:

| Agent | Primary Workstream | Secondary Workstream | Why |
|-------|-------------------|---------------------|-----|
| **Agent 1** | WS1: Storage & Connection | WS3: Memory Leaks | Both relate to resource management |
| **Agent 2** | WS2: Async & Concurrency | - | Requires deep async expertise, full focus |
| **Agent 3** | WS4: CLI Commands | WS8: Edge Cases | CLI edge cases overlap naturally |
| **Agent 4** | WS5: Data Integrity | - | Critical path, needs careful attention |
| **Agent 5** | WS6: Search & Retrieval | WS7: Monitoring | Search depends on monitoring health |
| **Agent 6** | Fix Queue | Cross-workstream | Picks up bugs as they're found |

---

## Execution Timeline

**Day 1: Setup & Initial Sweep**
- All agents create worktrees: `git worktree add .worktrees/BUG-HUNT-WS{N} -b BUG-HUNT-WS{N}`
- Run quick smoke tests on assigned areas
- Identify obvious bugs (low-hanging fruit)
- Add initial findings to TODO.md

**Days 2-4: Deep Investigation**
- Systematic testing per workstream tasks
- Write and run edge case tests
- Log all bugs with reproduction steps
- Agent 6 begins fixing CRITICAL bugs as they're found

**Days 5-6: Cross-Stream Testing**
- Test interactions between components (e.g., backup during indexing)
- Focus on integration boundaries
- Validate fix queue progress

**Days 7-8: Fix & Verify Sprint**
- All agents shift to fixing HIGH+ severity bugs
- Each fix requires:
  1. Regression test added
  2. `pytest tests/ -n auto -v` passes
  3. `python scripts/verify-complete.py` passes

**Day 9: Final Hardening**
- Run full test suite with coverage
- Verify no test regressions
- Merge all workstream branches
- Update CHANGELOG.md

---

## Bug Severity Classification

| Severity | Description | Examples |
|----------|-------------|----------|
| **CRITICAL** | Data loss, security, or system crash | Connection leak causing OOM, backup corruption |
| **HIGH** | Feature broken, no workaround | CLI command crashes, search returns wrong results |
| **MEDIUM** | Feature degraded, workaround exists | Slow performance, incorrect error message |
| **LOW** | Minor issue, cosmetic | Typo in log message, inconsistent formatting |

---

## Success Metrics

- [ ] All 8 workstreams completed
- [ ] 100+ edge cases tested
- [ ] All CRITICAL bugs fixed before sprint ends
- [ ] Test coverage increased for undertested areas
- [ ] No new bugs introduced (verify-complete.py passes)

---

## Test Templates & Patterns

See the full plan file for 6 test templates covering:
1. Connection/Resource Testing
2. Async Race Condition Testing
3. CLI Command Validation
4. Data Integrity Testing
5. Edge Case / Boundary Testing
6. Health/Monitoring Testing

---

## Bug Tracking Format

When bugs are found, add them to TODO.md using this format:

```markdown
### BUG-1XX: [Component] Brief description
- **Workstream:** WS{N}
- **Severity:** CRITICAL/HIGH/MEDIUM/LOW
- **Found by:** [agent/owner]
- **Reproduction:** Steps to reproduce
- **Root cause:** (if known)
- **Files affected:** list of files
- **Status:** NEW/INVESTIGATING/FIXING/FIXED
```
