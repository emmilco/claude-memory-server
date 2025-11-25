# UX-049: Add exc_info=True to Error Logs

## TODO Reference
- ID: UX-049
- Severity: HIGH
- Component: Error Handling / Observability
- Estimated Effort: ~2 days

## Objective
Add `exc_info=True` parameter to all `logger.error()` calls throughout the codebase to ensure full stack traces are logged, dramatically improving production debugging capabilities.

## Current State Analysis

### Problem Statement
Error logs across the codebase lack stack traces, making production debugging extremely difficult:

```python
# Current pattern (100+ instances)
except Exception as e:
    logger.error(f"Failed to store memory: {e}")  # No traceback!
    raise StorageError(f"Failed to store: {e}")
```

**Impact:**
- Production errors show only error messages, not stack traces
- Debugging requires reproducing issues locally
- Root cause analysis takes 10x longer
- No visibility into error propagation chains

### Current Coverage
Based on grep analysis, there are **100+ `logger.error()` calls** across 73+ files:

**High-frequency modules:**
- `src/core/server.py` - 19+ error logs (main server logic)
- `src/store/qdrant_store.py` - 15+ error logs (vector operations)
- `src/embeddings/generator.py` - 8+ error logs (embedding generation)
- `src/memory/incremental_indexer.py` - 10+ error logs (indexing operations)
- `src/cli/*.py` - 20+ error logs (CLI commands)
- `src/memory/*.py` - 30+ error logs (memory operations)
- `src/monitoring/*.py` - 5+ error logs (health monitoring)
- `src/backup/*.py` - 3+ error logs (backup/export)

### Example Current Patterns

**Pattern 1: Exception in try-except (NEEDS exc_info)**
```python
# src/core/server.py:467
except Exception as e:
    logger.error(f"Failed to store memory: {e}")  # Should have exc_info=True
    self.stats["storage_errors"] += 1
    raise StorageError(f"Failed to store memory: {e}") from e
```

**Pattern 2: Validation errors (MAY NOT NEED exc_info)**
```python
# src/core/server.py:464
except ValidationError as e:
    logger.error(f"Validation error: {e}")  # ValidationError might not need traceback
    self.stats["validation_errors"] += 1
    raise
```

**Pattern 3: Expected errors (NO exc_info needed)**
```python
# Not common in codebase, but example:
if not file.exists():
    logger.error(f"File not found: {file}")  # Not an exception, no exc_info
    return None
```

## Proposed Solution

### Implementation Strategy

Add `exc_info=True` to `logger.error()` calls that occur within exception handlers. Use judgment for validation/expected errors.

**After pattern:**
```python
except Exception as e:
    logger.error(f"Failed to store memory: {e}", exc_info=True)  # Full traceback
    self.stats["storage_errors"] += 1
    raise StorageError(f"Failed to store memory: {e}") from e
```

### Categorization Rules

**Category 1: ALWAYS add exc_info=True**
- Generic `Exception` handlers
- Infrastructure errors (database, network, file I/O)
- Unexpected errors during normal operations
- Integration failures
- Resource exhaustion
- **Examples:** StorageError, ConnectionError, RuntimeError, IndexError, KeyError

**Category 2: CONDITIONAL (use judgment)**
- Validation errors (ValidationError) - May skip if message is sufficient
- Expected business logic errors - May skip if well-understood
- Permission/auth errors - Include if debugging needed
- **Decision:** Include exc_info unless error is trivial/expected

**Category 3: NEVER add exc_info=True**
- Errors logged outside exception context (no active exception)
- User input validation at API boundary (before processing)
- Expected workflow errors (e.g., "project not found" in list operation)
- **Key indicator:** Not in a try-except block

### Before/After Examples

**Example 1: src/core/server.py (Generic exception)**
```python
# BEFORE
async def store_memory(self, request: StoreMemoryRequest) -> str:
    try:
        # ... code ...
    except Exception as e:
        logger.error(f"Failed to store memory: {e}")
        raise StorageError(f"Failed to store memory: {e}") from e

# AFTER
async def store_memory(self, request: StoreMemoryRequest) -> str:
    try:
        # ... code ...
    except Exception as e:
        logger.error(f"Failed to store memory: {e}", exc_info=True)
        raise StorageError(f"Failed to store memory: {e}") from e
```

**Example 2: src/store/qdrant_store.py (Infrastructure error)**
```python
# BEFORE
except Exception as e:
    logger.error(f"Failed to connect to Qdrant: {e}")
    raise StorageError(f"Connection failed: {e}") from e

# AFTER
except Exception as e:
    logger.error(f"Failed to connect to Qdrant: {e}", exc_info=True)
    raise StorageError(f"Connection failed: {e}") from e
```

**Example 3: ValidationError (Conditional)**
```python
# BEFORE - Simple validation
except ValidationError as e:
    logger.error(f"Invalid input: {e}")
    raise

# AFTER - Add exc_info for unexpected validation failures
except ValidationError as e:
    logger.error(f"Invalid input: {e}", exc_info=True)  # Helpful for debugging validation logic
    raise
```

### Log Output Format Changes

**Before (no traceback):**
```
2025-11-25 10:15:32,123 ERROR Failed to store memory: connection timeout
```

**After (with traceback):**
```
2025-11-25 10:15:32,123 ERROR Failed to store memory: connection timeout
Traceback (most recent call last):
  File "src/core/server.py", line 450, in store_memory
    await self.store.store(memory)
  File "src/store/qdrant_store.py", line 234, in store
    await client.upsert(points=[point])
  File "qdrant_client/async_client.py", line 445, in upsert
    response = await self._make_request(...)
  File "qdrant_client/async_client.py", line 89, in _make_request
    raise TimeoutError("Connection timeout")
TimeoutError: connection timeout
```

**Value:** Now we know the exact code path that led to the error.

## Implementation Plan

### Phase 1: Discovery & Categorization (4 hours)

**Step 1.1: Find all logger.error calls**
```bash
# Find all logger.error calls
grep -rn "logger\.error(" src/ --include="*.py" > /tmp/error_logs.txt

# Count by file
grep -r "logger\.error(" src/ --include="*.py" | cut -d: -f1 | sort | uniq -c | sort -rn
```

**Step 1.2: Categorize each occurrence**
Create spreadsheet/document with:
- File path
- Line number
- Current log message
- Context (in try-except? what exception type?)
- Category (1=always, 2=conditional, 3=never)
- Action (add exc_info=True, skip, or review)

**Step 1.3: Generate statistics**
- Total logger.error calls: ~100+
- Category 1 (must fix): ~70-80
- Category 2 (review): ~15-20
- Category 3 (skip): ~5-10

### Phase 2: Implementation by Module (8 hours)

**Priority order** (fix high-value modules first):

**Batch 1: Core Server (2 hours)**
- `src/core/server.py` (~19 calls)
- `src/core/exceptions.py` (if any error logging)
- Impact: Main request handling path

**Batch 2: Storage Layer (2 hours)**
- `src/store/qdrant_store.py` (~15 calls)
- `src/store/sqlite_store.py` (~8 calls)
- `src/store/connection_pool.py` (~3 calls)
- Impact: Database/vector store errors

**Batch 3: Embeddings & Memory (2 hours)**
- `src/embeddings/generator.py` (~8 calls)
- `src/embeddings/parallel_generator.py` (~5 calls)
- `src/memory/incremental_indexer.py` (~10 calls)
- `src/memory/file_watcher.py` (~4 calls)
- Impact: Indexing/embedding pipeline

**Batch 4: CLI & Commands (1 hour)**
- `src/cli/index_command.py`
- `src/cli/status_command.py`
- `src/cli/health_command.py`
- All other CLI commands
- Impact: User-facing command errors

**Batch 5: Supporting Modules (1 hour)**
- `src/monitoring/*.py` (metrics, alerts, health)
- `src/backup/*.py` (export/import)
- `src/analytics/*.py` (usage tracking)
- `src/memory/*.py` (remaining files)
- Impact: Supporting features

### Phase 3: Testing Strategy (4 hours)

**Test Approach:**
1. **Smoke Test:** Verify all modified files have valid syntax
2. **Error Injection:** Trigger known errors and verify logs contain tracebacks
3. **Regression Test:** Run full test suite to ensure no behavior changes
4. **Manual Verification:** Sample 10-15 log files for traceback presence

**Test Cases:**

**TC-1: Storage Error with Traceback**
```python
# tests/unit/test_logging_improvements.py
@pytest.mark.asyncio
async def test_storage_error_includes_traceback(caplog):
    """Verify storage errors include full tracebacks."""
    with caplog.at_level(logging.ERROR):
        with patch.object(QdrantStore, 'store', side_effect=Exception("Database error")):
            server = MemoryRAGServer()
            await server.initialize()

            with pytest.raises(StorageError):
                await server.store_memory(StoreMemoryRequest(...))

            # Verify traceback is in log output
            assert "Traceback (most recent call last):" in caplog.text
            assert "Database error" in caplog.text
```

**TC-2: Multiple Exception Types**
```python
def test_all_exception_types_logged(caplog):
    """Verify various exception types include tracebacks."""
    test_cases = [
        (StorageError("storage"), "storage"),
        (ValidationError("invalid"), "invalid"),
        (ConnectionError("connection"), "connection"),
    ]

    with caplog.at_level(logging.ERROR):
        for exc, expected_msg in test_cases:
            try:
                raise exc
            except Exception as e:
                logger.error(f"Test error: {e}", exc_info=True)

            assert "Traceback" in caplog.text
            assert expected_msg in caplog.text
```

**TC-3: Verify No Behavior Changes**
```bash
# Run full test suite
pytest tests/ -n auto -v

# Verify same pass/fail counts as before changes
# Target: 2,740 tests, 59.6% coverage maintained
```

**TC-4: Manual Log Inspection**
```python
# Create deliberate error in test environment
async def test_manual_traceback_verification():
    """Manual test: verify production-like logs include tracebacks."""
    # 1. Start server in test mode
    # 2. Trigger known errors (invalid memory, connection failure, etc.)
    # 3. Inspect log files manually
    # 4. Verify each error log includes full traceback
    pass
```

### Phase 4: Documentation & Rollout (2 hours)

**4.1: Update Developer Guidelines**
Create or update `docs/LOGGING_GUIDELINES.md`:
```markdown
# Logging Guidelines

## Error Logging Best Practices

### Always Include exc_info=True in Exception Handlers

```python
# ✅ CORRECT
try:
    risky_operation()
except Exception as e:
    logger.error(f"Operation failed: {e}", exc_info=True)
    raise CustomError(f"Wrapped: {e}") from e

# ❌ INCORRECT
try:
    risky_operation()
except Exception as e:
    logger.error(f"Operation failed: {e}")  # Missing exc_info!
    raise CustomError(f"Wrapped: {e}") from e
```

### When to Skip exc_info

- No active exception (logging outside try-except)
- Expected validation errors with clear messages
- User input errors at API boundary
```

**4.2: Update CHANGELOG.md**
```markdown
## [Unreleased]

### Improved
- **Observability:** Added `exc_info=True` to 100+ error logs across codebase for full stack traces in production (UX-049)
  - Affects: All modules with error handling
  - Impact: 10x faster debugging of production issues
  - Breaking: None (log format change only)
```

**4.3: Update CLAUDE.md (if logging section exists)**
Add note about logging standards.

## Performance Considerations

### Traceback Generation Overhead

**Cost Analysis:**
- Traceback generation: ~0.5-2ms per exception
- Log formatting: ~0.1-0.5ms additional
- **Total overhead: <2.5ms per error**

**When overhead matters:**
- High-frequency error paths (>100 errors/sec)
- Performance-critical hot paths
- **Mitigation:** These should be rare; errors should not be frequent

**Verdict:** Negligible impact. Error logging is not in the hot path (happy path doesn't log errors).

### Log Volume Impact

**Current state:** ~50-100 MB/day of logs (estimated)
**After change:** ~200-500 MB/day (4-5x increase due to tracebacks)

**Mitigations:**
- Log rotation (already in place)
- Compression (gzip logs after rotation)
- Retention policies (keep 7 days, archive older)
- Filtering (only ERROR level goes to persistent storage)

**Verdict:** Acceptable. Modern systems handle 500MB/day easily.

### Alternatives Considered

**Alt 1: Conditional exc_info based on log level**
```python
logger.error(f"Error: {e}", exc_info=logger.isEnabledFor(logging.DEBUG))
```
**Rejected:** Still no tracebacks in production (prod runs at INFO level)

**Alt 2: Sample tracebacks (only log 10% of errors)**
```python
if random.random() < 0.1:
    logger.error(f"Error: {e}", exc_info=True)
```
**Rejected:** Might miss critical errors, adds complexity

**Alt 3: Store tracebacks separately (structured logging)**
```python
logger.error(f"Error: {e}", extra={"traceback": traceback.format_exc()})
```
**Deferred:** Good future enhancement but requires structured logging infrastructure (see PERF-008)

## Phased Rollout Strategy

### Week 1: Critical Path (Core + Storage)
- Day 1-2: `src/core/server.py`, `src/core/exceptions.py`
- Day 3: `src/store/qdrant_store.py`, `src/store/sqlite_store.py`
- Day 4: Testing + verification
- Day 5: Deploy to staging, monitor log volume

**Gate:** No production deployment until staging validates log volume is acceptable.

### Week 2: Full Codebase (Embeddings + Memory + CLI)
- Day 1-2: Embeddings and memory modules
- Day 3: CLI commands
- Day 4: Supporting modules (monitoring, backup, analytics)
- Day 5: Final testing + merge to main

**Gate:** All tests passing, no log volume issues in staging.

## Risk Assessment

### Risk 1: Log Volume Explosion
**Probability:** Medium
**Impact:** Medium (disk space, log aggregation costs)
**Mitigation:**
- Monitor log volume in staging before production rollout
- Implement log rotation with compression
- Set up alerts for disk space <20%

### Risk 2: Performance Degradation
**Probability:** Low
**Impact:** Low (errors are not hot path)
**Mitigation:**
- Benchmark error logging overhead (<2.5ms)
- Monitor p99 latency before/after deployment
- Rollback plan: Remove exc_info=True if latency increases >5%

### Risk 3: Breaking Log Parsers
**Probability:** Medium
**Impact:** Low (existing log parsers might expect single-line errors)
**Mitigation:**
- Document new log format in CHANGELOG
- Update any log parsing scripts (grep/awk patterns)
- Provide migration guide for custom log parsers

### Risk 4: Sensitive Data in Tracebacks
**Probability:** Low
**Impact:** High (PII or secrets in stack traces)
**Mitigation:**
- Audit exception messages for sensitive data
- Implement exception sanitization if needed
- Review security logging guidelines

### Risk 5: Incomplete Coverage
**Probability:** Low
**Impact:** Low (some errors still lack tracebacks)
**Mitigation:**
- Automated grep verification: `grep -r "logger.error(" src/ | grep -v "exc_info=True"`
- Pre-commit hook to enforce exc_info=True in new code
- Periodic audits (quarterly)

## Success Criteria

### Quantitative Metrics
- ✅ 100+ logger.error calls updated with exc_info=True
- ✅ Zero test failures after changes
- ✅ Code coverage maintained (≥59.6%)
- ✅ Log volume increase <10x (target: 4-5x)
- ✅ Error logging overhead <2.5ms

### Qualitative Metrics
- ✅ Production errors include full stack traces in logs
- ✅ Debugging time reduced by 50%+ (measured via incident resolution time)
- ✅ Fewer "cannot reproduce" bug reports
- ✅ Support team can diagnose issues from logs alone

### Verification Tests
```bash
# Verify all error logs have exc_info
grep -r "logger\.error(" src/ --include="*.py" | \
  grep -v "exc_info=True" | \
  grep -v "# no-exc-info" | \
  wc -l
# Expected: 0 (or only false positives with explanation comments)

# Verify tests pass
pytest tests/ -n auto -v
# Expected: ~2,740 tests passing

# Verify traceback in sample error
python -c "
import logging
logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger('test')
try:
    raise ValueError('test error')
except Exception as e:
    logger.error(f'Error: {e}', exc_info=True)
" 2>&1 | grep -c "Traceback"
# Expected: 1
```

## Dependencies & Blockers

### Prerequisites
- ✅ Python logging infrastructure (already in place)
- ✅ Log rotation configured (already in place)
- ✅ Test environment available

### Blockers
- ⚠️ **Potential:** Log aggregation service capacity (e.g., ELK, Splunk)
  - **Resolution:** Verify with ops team, adjust retention if needed
- ⚠️ **Potential:** Staging environment log storage
  - **Resolution:** Monitor disk space, provision additional storage if needed

### Follow-up Tasks
- **PERF-008:** Distributed tracing (operation IDs) - Complements this work
- **REF-002:** Structured logging - Natural next step after exc_info is standard
- **Future:** Automated exception sanitization for sensitive data

## Completion Checklist

### Phase 1: Discovery ✅
- [ ] Run grep to find all logger.error calls
- [ ] Categorize each call (always/conditional/never)
- [ ] Generate statistics and priority list

### Phase 2: Implementation ✅
- [ ] Batch 1: Core server (19 calls)
- [ ] Batch 2: Storage layer (26 calls)
- [ ] Batch 3: Embeddings & memory (27 calls)
- [ ] Batch 4: CLI commands (20 calls)
- [ ] Batch 5: Supporting modules (15+ calls)

### Phase 3: Testing ✅
- [ ] Write automated tests for traceback presence
- [ ] Run full test suite (verify no regressions)
- [ ] Manual log inspection (verify traceback format)
- [ ] Performance benchmarking (verify <2.5ms overhead)

### Phase 4: Documentation & Rollout ✅
- [ ] Create/update LOGGING_GUIDELINES.md
- [ ] Update CHANGELOG.md
- [ ] Update TODO.md (mark UX-049 complete)
- [ ] Deploy to staging and monitor log volume
- [ ] Deploy to production after staging validation

### Final Verification ✅
- [ ] Zero test failures
- [ ] Production logs include tracebacks
- [ ] Log volume increase acceptable (4-5x)
- [ ] No performance degradation
- [ ] Documentation complete

## Next Steps After Completion

1. **PERF-008:** Add distributed tracing with operation IDs (see planning doc)
2. **UX-050:** Add thread-safe stats counters (see planning doc)
3. **REF-002:** Implement structured logging (JSON format for log aggregation)
4. **Monitor:** Track "time to resolution" for production bugs over next 3 months
5. **Iterate:** Adjust exc_info usage based on operational feedback

---

**Status:** 📋 Planning Complete - Ready for Implementation
**Next Action:** Move to IN_PROGRESS.md and begin Phase 1 (Discovery)
**Estimated Total Effort:** 2 days (16 hours)
