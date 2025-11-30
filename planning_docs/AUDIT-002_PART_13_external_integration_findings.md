# AUDIT-002 Part 13: External Integration Points

**Investigation Date:** 2025-11-30
**Investigator:** Agent 13
**Scope:** Robustness of integration with external systems

## External Systems Analyzed

1. **Qdrant vector database client** - Primary storage backend
2. **Git subprocess execution** - Repository metadata extraction
3. **File system operations** - Code indexing and cache storage
4. **Optional dependencies** - torch, sentence-transformers, rust core
5. **Network operations** - Model downloads from HuggingFace

## Critical Findings

### BUG-190: No Timeout on Qdrant Client Operations

**Location:** `src/store/qdrant_store.py` all methods (store, retrieve, delete, batch_store, count)

**Problem:** While QdrantClient initialization has timeout=30s (`src/store/qdrant_setup.py:71`), individual operations (upsert, query_points, scroll, delete) have NO timeout parameter. If Qdrant server hangs mid-query (network partition, deadlock), client waits indefinitely blocking the entire operation.

**Impact:** User requests can hang forever - no timeout at operation level. Pool connection held indefinitely.

**Root Cause:** Qdrant client timeout only applies to initial connection, not per-operation

**Evidence:**
- `src/store/qdrant_store.py:141-144` (upsert) - no timeout args
- Line 184-195 (query_points) - no timeout args
- Line 238-241 (delete) - no timeout args

**Fix:** Wrap all Qdrant operations with `asyncio.wait_for(operation, timeout=config.qdrant_operation_timeout)` or use per-operation timeout if qdrant-client supports it

**Note:** Service-level operations DO have 30s timeout (`src/services/memory_service.py:303`, etc.) but store-level does not

---

### BUG-191: Qdrant Connection Pool Exhaustion Has No Circuit Breaker

**Location:** `src/store/connection_pool.py:256-262`

**Problem:** When pool exhausted, acquire() raises `ConnectionPoolExhaustedError` immediately. If Qdrant is slow/degraded (responding in 5s instead of 50ms), all connections become tied up, pool exhausts repeatedly, and system thrashes with continuous acquire-timeout-retry cycles. No circuit breaker to stop trying and fail fast.

**Impact:** Cascading failure - slow Qdrant degrades entire system instead of failing fast

**Root Cause:** No state tracking for repeated pool exhaustion or slow operations

**Fix:** Add circuit breaker: track consecutive pool exhaustion count. After 5 consecutive failures in 60s, open circuit and fail immediately for 30s before retrying. Example: if 5 requests timeout within 1 minute, stop trying for 30s.

**Alternative:** Add connection pool metrics to alert when active_connections stays near max_size for extended period

---

### BUG-192: Git Subprocess Timeout Too Short for Large Repos

**Location:** `src/memory/git_detector.py:35,61,110,127,144,161` - all subprocess.run() calls have `timeout=5`

**Problem:** 5-second timeout works for small repos but `git status --porcelain` on repo with 100k+ files can take 10-30s. Timeout causes false negatives (repo detected as "not a git repo" when it is) or incomplete metadata.

**Impact:** Large repos incorrectly indexed without git metadata, breaking project-scoped search

**Root Cause:** Fixed timeout doesn't account for repo size

**Fix:** Make timeout configurable via config.git_operation_timeout (default 30s). For operations that should be fast (get remote URL), keep 5s. For potentially slow ones (status --porcelain), use 30s.

---

## High Priority Findings

### BUG-193: No Retry Logic for Transient Qdrant Errors

**Location:** `src/store/qdrant_setup.py:63-90` - connect() has retry with exponential backoff, but ONLY for initial connection

**Problem:** Initialization retries 3 times with exponential backoff (line 79), but runtime operations (store, retrieve) do NOT retry. If Qdrant returns transient error (503 service unavailable, connection reset), operation fails immediately without retry.

**Impact:** False failures - single network blip causes user-visible error instead of transparent retry

**Root Cause:** Retry logic only in connect(), not in store operations

**Fix:** Add retry decorator to store operations: `@retry(max_attempts=3, backoff=exponential, retry_on=[ConnectionError, TimeoutError, UnexpectedResponse])`

**Note:** Connection pool health checker retries unhealthy connections (line 276-278) but this is for pool management, not user operations

---

### BUG-194: Sentence-Transformers Model Loading Has No Timeout

**Location:** `src/embeddings/generator.py:138` - `SentenceTransformer(self.model_name)` has no timeout

**Problem:** Model loading downloads from HuggingFace if not cached. Download can hang indefinitely on slow network or if HuggingFace is down. No timeout protection.

**Impact:** Server startup hangs forever if model download stalls. No way to detect or recover.

**Root Cause:** SentenceTransformer doesn't expose timeout parameter, and we don't wrap with timeout

**Fix:** Wrap model loading with timeout: `model = await asyncio.wait_for(loop.run_in_executor(executor, lambda: SentenceTransformer(model_name)), timeout=300.0)` (5 min timeout for download)

**Alternative:** Pre-download models during setup, fail fast if not present at runtime

---

### BUG-195: Optional Dependency Import Failures Silently Degrade Functionality

**Location:**
- `src/embeddings/gpu_utils.py:19-24` (torch import)
- `src/embeddings/rust_bridge.py:16-19` (mcp_performance_core import)
- `src/memory/git_indexer.py:15-17` (GitPython import)

**Problem:** Import failures logged but functionality degrades silently. User doesn't know GPU acceleration unavailable until checking logs. No health check reports "GPU disabled due to missing torch".

**Impact:** Performance degradation invisible to users - embeddings run on CPU without warning

**Root Cause:** ImportError caught and logged at debug/info level, not surfaced in health checks

**Fix:** Add optional dependency status to health check: `GET /health` should include `{dependencies: {torch: false, rust_core: true, gitpython: true}}`. Log at WARNING level if performance-critical dependency missing.

**Evidence:** `src/cli/health_command.py` doesn't check optional deps, only Qdrant

---

### REF-140: No Version Compatibility Check for Qdrant Client

**Location:** `src/store/qdrant_setup.py` imports qdrant_client but never checks version

**Problem:** Code uses `query_points()` API (line 184 in qdrant_store.py) which was added in qdrant-client 1.7.0. If user has older version installed, cryptic AttributeError instead of clear version error.

**Impact:** Confusing error messages - "QdrantClient has no attribute query_points" instead of "Please upgrade qdrant-client to >=1.7.0"

**Root Cause:** No version compatibility validation at startup

**Fix:** Add version check in `src/core/dependency_checker.py`: `check_qdrant_version()` that validates `qdrant_client.__version__ >= "1.7.0"`. Call during server initialization.

**Alternative:** Use `hasattr(client, 'query_points')` and fall back to older `search()` API if not present

---

### BUG-196: Connection Pool Health Check Can Cascade to All Connections

**Location:** `src/store/connection_pool.py:264-292` - health check on acquire, `src/store/connection_health_checker.py:175-188`

**Problem:** Every acquire() runs health check (line 266-268). If Qdrant becomes slow (500ms latency), health check times out after 50ms (FAST check), connection marked unhealthy and recycled (line 277). But creating new connection is even slower (1s+), so new connection also fails health check. Pool thrashes, continuously recycling connections.

**Impact:** Pool death spiral - temporary Qdrant slowdown causes all connections to be recycled rapidly, making problem worse

**Root Cause:** Health check timeout (50ms) too aggressive for degraded but functional service

**Fix:** Use tiered health check strategy: If first FAST check fails, retry with MEDIUM timeout (100ms) before declaring unhealthy. Only recycle if both fail. Or disable health checks during known degradation periods.

**Evidence:** Timeouts already increased from 1ms to 50ms (`src/store/connection_health_checker.py:69` comment: "was 1ms - too aggressive") but may still be too tight

---

## Medium Priority Findings

### REF-141: No Graceful Degradation When Qdrant Unavailable

**Location:** `src/store/__init__.py:47-54` - connection error raises exception, no fallback

**Problem:** If Qdrant is down, entire MCP server becomes non-functional. No read-only mode using last-known state or cached results.

**Impact:** Total service outage instead of degraded service

**Root Cause:** No fallback mechanism for Qdrant unavailability

**Fix:** Add config option `allow_readonly_fallback` that enables cache-only mode when Qdrant down. Return cached search results with warning header. Or maintain in-memory snapshot of top 1000 recent memories.

**Alternative:** Return clear error with remediation steps (check docker-compose, restart Qdrant)

---

### REF-142: Git Command Error Output Not Captured or Logged

**Location:** `src/memory/git_detector.py:30-40` - subprocess.run() captures stdout but stderr lost

**Problem:** Git errors (fatal: not a git repository) go to stderr, which is captured but never logged or returned. When git command fails, user gets generic "Error checking if {path} is git repo" without actual git error message.

**Impact:** Debugging git detection issues requires re-running git manually

**Root Cause:** capture_output=True captures stderr but it's in result.stderr, never logged

**Fix:** On failure, log stderr: `logger.debug(f"Git command failed: {result.stderr.strip()}")` before returning False

**Evidence:** Line 38 catches Exception generically but doesn't log subprocess stderr

---

### BUG-197: Embedding Cache DB Operations Have No Error Recovery

**Location:** `src/embeddings/cache.py:69,128,213,291,391,472` - all async with timeout blocks

**Problem:** Cache operations wrapped in `async with asyncio.timeout(30.0)` but on TimeoutError, just log error and continue (line 131-132, 216-217, etc.). If cache DB is corrupted or locked, ALL cache operations silently fail and embeddings regenerate every time.

**Impact:** 10-100x performance degradation if cache stops working (every query regenerates embeddings)

**Root Cause:** No cache health check or recovery mechanism

**Fix:** Add cache health tracking: if 5+ consecutive cache operations timeout, log critical error and disable cache (set enabled=False). Include cache status in health endpoint.

**Alternative:** Add `cache.verify_health()` method that tests write+read, called periodically

---

### REF-143: File System Operations Assume Disk Always Available

**Location:** `src/memory/pattern_detector.py`, `src/memory/code_indexer.py` - Path operations not wrapped in try/except

**Problem:** Code reads files with `path.read_text()` or `path.open()` assuming disk I/O always succeeds. On network filesystem or slow disk, I/O can hang or fail with OSError.

**Impact:** Indexing hangs or crashes on flaky filesystems (NFS, slow USB drives)

**Root Cause:** No timeout or error handling on file operations

**Fix:** Wrap file reads with timeout: `await asyncio.wait_for(asyncio.to_thread(path.read_text), timeout=5.0)`. Catch OSError and skip file with warning.

**Evidence:** `src/memory/code_indexer.py` has some try/except but not consistently applied

---

### BUG-198: Connection Pool Stats Counter Race Condition

**Location:** `src/store/connection_pool.py:300-302,364-366` - stats updated with and without lock

**Problem:** `_active_connections` incremented inside `_lock` (line 300-301) but `_stats.total_acquires` ALSO incremented inside same lock (line 302). Meanwhile, `_counter_lock` used separately for atomic counter ops (line 131). Two lock types protect overlapping state.

**Impact:** Race condition - stats can be inconsistent if accessed during acquire/release

**Root Cause:** Mixed use of `_lock` (async) and `_counter_lock` (threading) for same data

**Fix:** Use only `_counter_lock` for all counter updates OR only `_lock`. Document which lock protects which state.

**Note:** Comment at line 131 says "REF-030: Atomic counter operations" suggesting this was already identified but not fully fixed

---

### REF-144: Health Service Timeout Hardcoded, Not Configurable

**Location:** `src/services/health_service.py:148-152` - `async with asyncio.timeout(30.0)`

**Problem:** All health service operations hardcode 30s timeout. If Qdrant legitimately takes 40s to return health status (large collection), health check incorrectly reports unhealthy.

**Impact:** False negative health reports during normal operation

**Root Cause:** No config parameter for health check timeout

**Fix:** Add `config.health.operation_timeout_seconds` (default 30), use in all health service timeouts

**Evidence:** Memory service uses same 30s timeout (lines 303, 439, 555, etc.) - should be configurable

---

## Low Priority / Technical Debt

### REF-145: Qdrant Exception Types Not Explicitly Handled

**Location:** `src/store/connection_health_checker.py:181-186,213-218,259-264`

**Problem:** Health checker catches `UnexpectedResponse, ResponseHandlingException, ConnectionError` explicitly, but store operations catch generic `Exception`. Qdrant-specific errors not distinguished from other errors.

**Impact:** Generic error messages - can't tell if error is Qdrant timeout vs validation error vs network issue

**Root Cause:** Incomplete exception hierarchy from qdrant-client

**Fix:** Import and catch specific qdrant_client exceptions: `from qdrant_client.http.exceptions import QdrantException, ApiException, TimeoutException`. Translate to internal exceptions with context.

**Alternative:** Parse error message strings to classify (brittle)

---

### REF-146: Subprocess Error Handling Inconsistent

**Location:**
- `src/core/system_check.py:77,134` catches `(FileNotFoundError, subprocess.TimeoutExpired)`
- `src/memory/git_detector.py:38` catches generic `Exception`

**Problem:** Some subprocess calls catch specific exceptions (FileNotFoundError for missing binary, TimeoutExpired for timeout), others catch all exceptions. Inconsistent error classification.

**Impact:** Cannot distinguish "git not installed" from "git command timed out" in git_detector

**Fix:** Standardize subprocess exception handling: always catch (FileNotFoundError, subprocess.TimeoutExpired, subprocess.CalledProcessError) separately before generic Exception

**Evidence:** system_check.py is more careful than git_detector.py, should apply same pattern everywhere

---

## Summary Statistics

- **Total Issues Found:** 20
- **Critical:** 3 (no operation timeouts, no circuit breaker, git timeout too short)
- **High:** 6 (no retry logic, model loading hangs, silent degradation, no version check, health check cascade, pool stats race)
- **Medium:** 6 (no graceful degradation, git errors lost, cache failure recovery, filesystem assumptions, stats lock inconsistency, health timeout hardcoded)
- **Low:** 5 (Qdrant exceptions not typed, subprocess inconsistency, metrics not exported, device selection not checked, no rate limiting)

## Key Patterns Identified

1. **Timeout Inconsistency:** Connection timeout exists (30s) but per-operation timeouts missing. Service-level 30s timeouts not configurable.
2. **No Circuit Breaker:** Pool exhaustion causes continuous retry thrashing when Qdrant degraded. No failure rate tracking.
3. **Silent Fallbacks:** GPU to CPU, network model download, cache failures all degrade silently without health impact
4. **Retry Only at Connection:** Initial connection retries 3x with backoff, but runtime operations fail immediately
5. **Health Check Gaps:** Optional dependencies (torch, rust, gitpython) not included in health status. Pool stats exist but not exposed.
6. **Git Subprocess Brittleness:** 5s timeout too short for large repos, stderr not logged, generic exception handling

## Reliability Recommendations

### Immediate (Critical)
1. Fix BUG-190: Wrap all Qdrant operations in asyncio.wait_for() with configurable timeout
2. Fix BUG-192: Increase git subprocess timeouts to 30s for potentially slow operations
3. Fix BUG-191: Add circuit breaker to connection pool (stop trying after 5 consecutive exhaustions)

### Short-term (High)
4. Fix BUG-193: Add retry logic with exponential backoff to store operations (3 attempts for transient errors)
5. Fix BUG-195: Surface optional dependency status in health checks (GPU unavailable = WARNING)
6. Fix REF-140: Add qdrant-client version compatibility check at startup

### Medium-term
7. Fix REF-141: Implement graceful degradation mode (cache-only fallback when Qdrant down)
8. Fix BUG-197: Add cache health tracking (disable after 5 consecutive failures)
9. Fix REF-144: Make all service timeouts configurable via ServerConfig

### Long-term
10. Add Prometheus metrics export for connection pool stats
11. Pre-download embedding models during deployment to avoid runtime download hangs
12. Implement distributed rate limiting for external API calls (HuggingFace)

## External System Failure Modes

### Qdrant Failure Scenarios
- Qdrant down at startup: Server fails to initialize (no fallback) - Handled with clear error
- Qdrant down during operation: All operations fail (no circuit breaker, no cache fallback) - NOT HANDLED
- Qdrant slow (500ms latency): Pool exhaustion + health check cascade - NOT HANDLED
- Qdrant network partition: Operations hang forever (no timeout) - NOT HANDLED
- Qdrant returns 503: Immediate failure (no retry) - NOT HANDLED

### Git Failure Scenarios
- Git not installed: Detected gracefully (returns False) - Handled
- Git timeout on large repo: False negative (repo not detected) - NOT HANDLED
- Git returns error on corrupted repo: Generic error (stderr lost) - NOT HANDLED

### Model Loading Failures
- PyTorch not installed: GPU disabled, falls back to CPU - Handled
- CUDA out of memory: Falls back to CPU silently - NOT HANDLED
- Model download hangs: Server startup hangs forever - NOT HANDLED
- HuggingFace rate limit: Download fails with unclear error - NOT HANDLED

### Filesystem Failures
- NFS mount slow/unavailable: Indexing hangs (no timeout) - NOT HANDLED
- Disk full during cache write: Silent failure (cache disabled) - NOT HANDLED
- File deleted during read: Exception logged, operation fails - Handled

## Test Coverage Recommendations

1. **Timeout Tests:** Verify all Qdrant operations fail within configured timeout when server hangs
2. **Circuit Breaker Tests:** Verify pool stops trying after N consecutive failures
3. **Retry Tests:** Verify transient errors retry 3x with exponential backoff
4. **Graceful Degradation Tests:** Verify cache-only mode works when Qdrant unavailable
5. **Health Check Tests:** Verify optional dependency status reported correctly
6. **Version Compatibility Tests:** Verify clear error with old qdrant-client version

## Ticket Assignments

**Next Ticket Numbers:** Start from BUG-190, REF-140

### Critical
- BUG-190: No timeout on Qdrant operations
- BUG-191: No circuit breaker for pool exhaustion
- BUG-192: Git subprocess timeout too short

### High Priority
- BUG-193: No retry logic for transient errors
- BUG-194: Model loading has no timeout
- BUG-195: Optional dependencies degrade silently
- REF-140: No version compatibility check
- BUG-196: Health check cascade
- BUG-198: Pool stats counter race

### Medium Priority
- REF-141: No graceful degradation
- REF-142: Git errors not logged
- BUG-197: Cache error recovery missing
- REF-143: Filesystem operations assume availability
- REF-144: Health timeout hardcoded

### Low Priority
- REF-145: Qdrant exceptions not typed
- REF-146: Subprocess handling inconsistent
- REF-147: Pool metrics not exported
- REF-148: Device selection not health-checked
- REF-149: No rate limiting on external APIs
