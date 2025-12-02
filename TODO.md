# TODO

Last updated: 2025-11-30

## ID Registry

**Next Available IDs:**
| Prefix | Next ID | Description |
|--------|---------|-------------|
| BUG | 457 | Bug fixes |
| REF | 400 | Refactoring/tech debt |
| PERF | 035 | Performance improvements |
| SEC | 001 | Security issues |
| TEST | 043 | Testing improvements |
| DOC | 030 | Documentation |
| FEAT | 063 | New features |
| UX | 067 | User experience |

**Workflow:** `TODO.md` → `IN_PROGRESS.md` → `REVIEW.md` → `TESTING.md` → `CHANGELOG.md`

**Critical Rule: One File Per Task**
- Each task exists in exactly ONE tracking file at any time
- "Move" = DELETE from source file, ADD to destination file
- See `ORCHESTRATION.md` for full workflow details

**ID Rules:**
1. **Creating a task:** Use the next available ID from the table above, then increment it
2. **Starting a task:** DELETE from TODO.md, ADD to IN_PROGRESS.md (task moves, not copied)
3. **IDs are permanent:** Never reuse an ID, even after the task is completed
4. **Counter only increases:** The "Next ID" values only go UP when creating new tasks

## Priority Guide

- **Critical (🔴):** Crashes, data loss, security vulnerabilities, race conditions, resource leaks
- **High (🟡):** Incorrect behavior, validation issues, performance problems
- **Medium (🟢):** Code quality, tech debt, documentation gaps
- **Low:** Nice-to-haves, polish, cosmetic issues

Task IDs: BUG-XXX (bugs), REF-XXX (refactoring), FEAT-XXX (features), TEST-XXX (testing), PERF-XXX (performance), SEC-XXX (security), DOC-XXX (documentation), UX-XXX (user experience)

---

## 🔴 Critical Priority

## 🟡 High Priority

## Bugs (BUG-*)

- [ ] **BUG-086**: Health Scorer Distribution Calculation Can Hit Memory Limit
  - **Location:** `src/memory/health_scorer.py:162-227`
  - **Problem:** The `_get_lifecycle_distribution()` method loads ALL memories with `all_memories = await self.store.get_all_memories()` (line 178), then has a check at line 190-195 that returns empty distribution if count > MAX_MEMORIES_PER_OPERATION (50,000). However, the damage is already done at line 178 - if there are 100,000 memories, they're all loaded into memory before the check. This can cause OOM crash. The comment at line 193 says "Aborting to prevent memory exhaustion" but it's too late.
  - **Fix:** Add count-only query before fetching: `total = await self.store.count_memories(); if total > MAX_MEMORIES_PER_OPERATION: return distribution`. Or use streaming/cursor-based fetching instead of loading all at once.

- [ ] **BUG-092**: Orphaned Tag Associations After Memory Deletion
  - **Location:** `src/services/memory_service.py:536-571` (delete_memory), `src/tagging/tag_manager.py` (no cleanup hook)
  - **Problem:** When a memory is deleted via `MemoryService.delete_memory()`, it only deletes from Qdrant store. The `memory_tags` table in SQLite is never cleaned up, creating orphaned associations that accumulate over time.
  - **Impact:** Database bloat, incorrect tag usage statistics, memory leaks in tag-related queries
  - **Evidence:** 
    - `delete_memory()` calls `await self.store.delete(request.memory_id)` but never touches tag_manager
    - `tag_manager.py` has no method to clean up tags by memory_id deletion event
    - No event system or callback mechanism connects MemoryService to TagManager
  - **Fix:** 
    1. Add `tag_manager.cleanup_memory_tags(memory_id: str)` method
    2. Call from `MemoryService.delete_memory()` after successful store deletion
    3. Also add batch cleanup method for `StorageOptimizer.execute_cleanup()` to catch historical orphans

- [ ] **BUG-284**: MemoryStore Abstract Methods Missing from QdrantMemoryStore - Dead Code
  - **Location:** Methods in base.py NOT implemented in qdrant_store.py
  - **Problem:** QdrantMemoryStore has 25 additional methods not declared in abstract base class:
    - `migrate_memory_scope`, `bulk_update_context_level`, `find_duplicate_memories`, `merge_memories`
    - `get_all_projects`, `get_project_stats`, `get_recent_activity`
    - `delete_by_filter`, `delete_code_units_by_project`
    - `find_memories_by_criteria`, `find_unused_memories`, `get_all_memories`
    - Git-related: `store_git_commits`, `search_git_commits`, `get_git_commit`, `get_commits_by_file`, `store_git_file_changes`
    - Usage tracking: `get_usage_stats`, `update_usage`, `get_all_usage_stats`, `batch_update_usage`, `delete_usage_tracking`, `cleanup_orphaned_usage_tracking`
  - **Impact:** MEDIUM - These methods are Qdrant-specific and won't be available in other MemoryStore implementations. Services depending on them are tightly coupled to Qdrant. Future store backends will silently lack these features.
  - **Fix:** Either (1) promote commonly-used methods to abstract base class OR (2) create separate feature interfaces/mixins (e.g., GitTrackingMixin, UsageTrackingMixin) that stores can optionally implement

- [ ] **BUG-292**: Client Map Race Condition in Connection Pool
  - **Location:** `src/store/connection_pool.py:311,342`
  - **Code:**
    ```python

- [ ] **BUG-294**: Binary File Detection Division by Zero on Empty Chunk
  - **Location:** `src/memory/optimization_analyzer.py:290`: `text_chars / len(chunk) < 0.7 if chunk else False`
  - **Problem:** Uses ternary to guard division, but if `chunk` is empty bytes object, `len(chunk)=0` causes division by zero
  - **Impact:** The guard `if chunk` catches empty case, so this is actually safe, but confusing code
  - **Fix:** Clarify: `(text_chars / len(chunk) < 0.7) if chunk else False` or better: `if not chunk: return False; return text_chars / len(chunk) < 0.7`

- [ ] **BUG-298**: Datetime strptime Without Timezone Can Cause Ambiguity
  - **Locations:**
    - `src/services/memory_service.py:229`: `datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=UTC)`
    - `src/core/server.py:4739`: Same pattern
    - `src/search/query_dsl_parser.py:264`: `datetime.strptime(date_str, '%Y-%m-%d')` - no timezone replacement
  - **Problem:** Parses date strings without timezone, then adds UTC. If date_str contains timezone info, it will fail or be ignored. Also doesn't validate date is within reasonable bounds (e.g., year > 9999 causes issues in some systems)
  - **Impact:** Can accept invalid dates, DST transitions not handled, year 2038 problem for 32-bit timestamps
  - **Fix:** Add validation: `dt = datetime.strptime(...); if dt.year > 2100 or dt.year < 1970: raise ValidationError("Date out of valid range")`

- [ ] **BUG-306**: Undefined Variable `memory_rag_server` in MCP Tool Handlers
  - **Location:** `src/mcp_server.py:1484, 1505, 1524`
  - **Problem:** Three tool handlers reference undefined variable `memory_rag_server` instead of the global `memory_server`. This causes AttributeError on tool invocation.
  - **Affected Tools:** `get_usage_statistics`, `get_top_queries`, `get_frequently_accessed_code`
  - **Impact:** FEAT-020 usage analytics tools completely non-functional - runtime crash on every invocation
  - **Fix:** Replace all `memory_rag_server` references with `memory_server` (lines 1484, 1505, 1524)

- [ ] **BUG-315**: Triple Definition of `export_memories` Method
  - **Location:** `src/core/server.py:1660, 4886, 5101`
  - **Problem:** Three different implementations of `export_memories` with incompatible signatures
    - Line 1660: `output_path: Optional[str]`, uses store directly
    - Line 4886: `output_path: str` (required), uses DataExporter
    - Line 5101: `output_path: str` (required), uses DataExporter (duplicate of 4886)
  - **Impact:** Last definition (line 5101) shadows all previous ones. First implementation (comprehensive, handles both file and string output) is unreachable. MCP tool calls unpredictable behavior.
  - **Fix:** Keep only one implementation - consolidate features from all three, remove duplicates

- [ ] **BUG-319**: Triple Definition of `import_memories` Method
  - **Location:** `src/core/server.py:1824, 4950, 5165`
  - **Problem:** Three different implementations with incompatible signatures
    - Line 1824: `file_path: Optional[str]`, `content: Optional[str]`, `conflict_mode: str = "skip"`
    - Line 4950: `input_path: str`, `conflict_strategy: str = "keep_newer"` (different param names!)
    - Line 5165: Identical to 4950 (exact duplicate)
  - **Impact:** Last definition shadows previous ones. Different parameter names (`conflict_mode` vs `conflict_strategy`) break API contract. MCP tool schema inconsistent with actual implementation.
  - **Fix:** Keep only one implementation with consolidated API, update MCP tool schema to match

- [ ] **BUG-320**: Potential Resource Leak in HealthService.start_dashboard
  - **Location:** `src/services/health_service.py:321-360`
  - **Problem:** Starts DashboardServer with `await server.start()` but doesn't track the server instance or provide a way to stop it later. If called multiple times, could leak server instances.
  - **Fix:** Store server instance in `self.dashboard_server`, add `stop_dashboard()` method for cleanup. Prevent starting if already running.

- [ ] **BUG-323**: Missing Call Graph Store Cleanup in IncrementalIndexer.close()
  - **Location:** `src/memory/incremental_indexer.py:1202-1206`
  - **Problem:** The `close()` method closes `self.store` and `self.embedding_generator`, but does NOT close `self.call_graph_store` which was initialized at line 224. This creates a resource leak - the call graph store's Qdrant connections remain open indefinitely.
  - **Fix:** Add `await self.call_graph_store.close()` before closing other resources

- [ ] **BUG-324**: Missing Implementation for `suggest_queries` Tool
  - **Location:** `src/mcp_server.py:269-297, 1010-1046` (tool declared), `src/core/server.py` (no implementation found)
  - **Problem:** MCP server declares `suggest_queries` tool and has handler that calls `memory_server.suggest_queries(**arguments)`, but MemoryRAGServer class has no such method
  - **Impact:** FEAT-057 query suggestions completely broken - AttributeError on every invocation
  - **Fix:** Either implement `suggest_queries` method in MemoryRAGServer or remove tool declaration from MCP server

- [ ] **BUG-332**: Division by Zero Risk in Nesting Depth Calculation
  - **Location:** `src/analysis/complexity_analyzer.py:184`
  - **Problem:** `depth = leading // indent_size` where `indent_size` could be 0 if language not in `indent_chars` dict and subsequent logic fails. Line 184 checks `if indent_size > 0` but the else clause sets `depth = 0`, which means files with tabs or non-standard indentation are scored as having zero nesting depth regardless of actual nesting.
  - **Fix:** Fall back to detecting mixed tabs/spaces: `indent_size = 4 if '\t' not in line else 1` and warn about unrecognized indentation style

- [ ] **BUG-344**: Missing Client Release in Two QdrantStore Methods
  - **Location:** `src/store/qdrant_store.py` - 32 acquires but only 30 releases
  - **Problem:** Connection pool leak - two methods acquire client via `await self._get_client()` but don't have matching `await self._release_client(client)` in their finally blocks. This causes connections to leak from the pool over time. Analysis shows:
    - Acquire at line 1639 (`get_project_stats`) - has release at 1722 ✓
    - Acquire at line 2286 (`bulk_update_context_level`) - likely missing release
    - Further investigation needed to identify the second leak
  - **Impact:** Connection pool will eventually exhaust under load, causing `ConnectionPoolExhaustedError`
  - **Fix:** Audit all methods with `client = await self._get_client()` and ensure each has `await self._release_client(client)` in finally block

- [ ] **BUG-346**: Missing Error Handling in Linear Regression Causes Silent Failures
  - **Location:** `src/monitoring/capacity_planner.py:392-444`
  - **Problem:** The `_calculate_linear_growth_rate()` method can fail silently if historical metrics contain invalid data (NaN, infinity, or extremely large values). Line 439 checks `if abs(denominator) < 1e-10` to avoid division by zero, but doesn't validate input data. If `sum_xy` or `sum_x_squared` overflow to infinity (possible with 10,000+ data points over years), the calculation returns garbage values without warning. This leads to incorrect capacity forecasts.
  - **Fix:** Add input validation: `if any(not math.isfinite(getattr(m, metric_name, 0)) for m in historical_metrics): logger.warning("Invalid metric values detected"); return 0.0`. Wrap calculation in try/except to catch OverflowError.

- [ ] **BUG-348**: Exception Swallowed in Connection Release with Comment Justification
  - **Location:** `src/store/connection_pool.py:375-377`
  - **Problem:** `release()` catches all exceptions and logs error but explicitly doesn't raise with comment "Don't raise - connection is lost but we continue". This violates exception handling best practices - swallowing exceptions hides bugs. If release fails repeatedly due to bug (e.g., lock corruption, client_map corruption), caller never knows pool is degrading. This masks serious issues like connection leaks.
  - **Fix:** At minimum add metrics tracking for failed releases and raise alert if failure rate > 1%. Better: only swallow expected exceptions (asyncio.QueueFull), re-raise unexpected ones.

- [ ] **BUG-356**: Health Scheduler Resource Leak on Restart
  - **Location:** `src/memory/health_scheduler.py:304-317`
  - **Problem:** The `update_config()` method calls `await self.stop()` (line 309) which closes the store (line 151), then creates a new AsyncIOScheduler (line 313) and calls `await self.start()` (line 316) which creates a NEW store instance (line 73). The old store's Qdrant connections are closed, but the store object itself may still be referenced by old job callbacks. If a scheduled job runs during the restart window, it will use the closed store and fail. Additionally, the `health_jobs` instance is not recreated, so it holds a reference to the old (closed) store.
  - **Fix:** In `update_config()`, also recreate `self.health_jobs = None` before calling `start()`. Add state check in job callbacks: `if not self.health_jobs or not self.health_jobs.store: logger.error("Store not available"); return`

- [ ] **BUG-366**: Missing Keyboard Interrupt Handling in Many Commands
  - **Location:** `src/cli/watch_command.py:74` has `KeyboardInterrupt` handler, but most other async commands don't
  - **Problem:** Only watch, main, and a few commands handle Ctrl+C gracefully. Commands like index, git-index, health-monitor will crash with ugly Python traceback on Ctrl+C instead of clean exit message.
  - **Impact:** Poor UX - users see Python stack traces when interrupting long operations
  - **Fix:** Wrap all async command `run()` methods with `try/except KeyboardInterrupt` and print friendly "Operation cancelled by user"

- [ ] **BUG-375**: Silent ValueError to Default State Conversion Hides Data Corruption
  - **Location:** `src/memory/health_scorer.py:215-218`, same pattern in store/qdrant_store.py:1526
  - **Problem:** `except ValueError: state = LifecycleState.ACTIVE` silently converts invalid lifecycle states to ACTIVE without logging. If database contains corrupted state values (e.g., "ARCHIVD" typo), code hides corruption by defaulting to ACTIVE. Users see incorrect lifecycle stats. This is data integrity issue disguised as graceful degradation.
  - **Fix:** Log warning with value that failed to parse: `logger.warning(f"Invalid lifecycle state '{state}', defaulting to ACTIVE")`. Consider adding data validation job to detect corruption.

- [ ] **BUG-396**: ConversationTracker.sessions Dict Modified Without Lock
  - **Location:** `src/memory/conversation_tracker.py:140-144, 172-177`
  - **Problem:** `self.sessions` dict is modified in `create_session()` and `end_session()` without lock protection. If two threads/tasks call these methods concurrently, dict corruption or race conditions could occur. While GIL provides some protection, async context switches between dict operations can still cause issues.
  - **Fix:** Add `self._sessions_lock = asyncio.Lock()` and wrap all dict mutations in async context manager

- [ ] **BUG-398**: Dashboard Web Server Swallows All Exceptions and Returns Generic 500
  - **Location:** `src/dashboard/web_server.py:236`, :267, :304, :332, :453, :508, :572, :610, :657
  - **Problem:** Every endpoint has `except Exception as e: logger.error(...); self._send_error_response(500, str(e))`. This returns raw exception messages to HTTP clients, potentially leaking sensitive information (file paths, database schemas, internal IPs). Also returns 500 for client errors (ValidationError should be 400).
  - **Fix:** Map exception types to HTTP status codes: ValidationError -> 400, NotFoundError -> 404, StorageError -> 503. Sanitize exception messages: return generic message to client, log full details server-side.

- [ ] **BUG-403**: UsageTracker Stats Counters Have Partial Lock Coverage
  - **Location:** `src/memory/usage_tracker.py:146-147`
  - **Problem:** Lines 146-147 increment `self.stats["total_tracked"]` with `self._counter_lock` protection (good), but line 147 is inside `async with self._lock:` which is already held. This creates nested locking pattern that could cause deadlock if other code acquires locks in different order. Additionally, other stats updates at lines 207-209 are NOT protected by counter_lock.
  - **Fix:** Ensure all stats counter updates use threading.Lock consistently, separate from asyncio.Lock for data structure access

- [ ] **BUG-405**: asyncio.timeout Context Manager Missing in 30+ Locations
  - **Location:** Compare files with `asyncio.timeout()` (35 uses) vs async operations without timeout (100+ async def methods)
  - **Problem:** Most async operations have 30s timeout via `async with asyncio.timeout(30.0)`, but many don't (e.g., connection_pool.py acquire, health checks, background indexing). Without timeouts, operations can hang indefinitely on network issues, deadlocks, or Qdrant hangs. This violates fail-fast principle.
  - **Fix:** Audit all async methods that do I/O (network, disk) and add timeouts. Create wrapper decorator `@with_timeout(seconds=30)` to enforce consistently.

- [ ] **BUG-410**: Call Graph Store Never Closed - Resource Leak
  - **Location:** `src/services/code_indexing_service.py` creates CallGraphStore but never calls close()
  - **Problem:** CallGraphStore likely holds resources (connections, file handles) but the service never closes it. Same pattern in health_service.py with various stores. Python GC will eventually close, but explicit cleanup is better practice, especially for connection pools.
  - **Fix:** Add `async def close()` to service layer, call store.close() in it. Add context manager support: `async with CodeIndexingService(...) as svc:`

- [ ] **BUG-451**: Max Depth Calculation Ignores Cycles - Infinite Loop Risk
  - **Location:** `src/graph/dependency_graph.py:314-325`
  - **Problem:** `get_stats()` calculates max_depth using BFS from root nodes, but doesn't track visited set across different root traversals. If graph has cycles (which find_circular_dependencies explicitly detects), the BFS at line 318-325 has `visited: Set[str] = {root}` scoped per root, meaning it can loop infinitely within a strongly connected component.
  - **Example:** Graph with cycle A->B->C->A and no roots (all nodes have incoming edges). Line 311 finds roots=[], loop never executes, max_depth stays 0. But if roots=[A] and A->B->C->A cycle exists, BFS adds B to queue, then C, then A again (A not in visited for this iteration).
  - **Impact:** Infinite loop causing process hang, incorrect max_depth=0 for cyclic graphs
  - **Fix:** Move `visited` set outside the roots loop OR use global visited set OR skip max_depth calculation if circular dependencies detected

- [ ] **BUG-081**: Missing Validation for Empty Embeddings Array in Duplicate Detector
  - **Location:** `src/analysis/code_duplicate_detector.py:159-163`
  - **Problem:** Line 159 checks `if embeddings.size == 0: raise ValueError("Embeddings array is empty")`, but this check happens AFTER the function signature promises to return an ndarray. An empty array is a valid input in some contexts (e.g., empty codebase), but raising ValueError breaks the contract. Additionally, returning an empty similarity matrix (0x0) might be more appropriate than failing.
  - **Fix:** Return `np.array([])` (empty 0x0 matrix) for empty input instead of raising, or document that empty input is invalid in docstring

- [ ] **BUG-087**: Trend Analysis Direction Logic Has Edge Case Bug
  - **Location:** `src/monitoring/health_reporter.py:353-363`
  - **Problem:** The trend direction determination uses compound ternary expressions that are hard to reason about. Line 353-356 for "higher_is_better" case: `direction = "improving" if change_percent > 5 else "degrading" if change_percent < -5 else "stable"`. This means a change of +4% is "stable", but -4% is also "stable". However, for "lower is better" metrics (line 359-362), the logic is flipped but uses the SAME thresholds. This means a 4.9% increase in noise_ratio is marked "stable" when it should be "degrading".
  - **Fix:** Use clearer threshold constants: `TREND_SIGNIFICANT_CHANGE = 5.0`. Break compound ternary into explicit if/elif for readability. Consider separate thresholds for improvement vs degradation (e.g., 5% improvement is good, but 3% degradation is concerning).

- [ ] **BUG-088**: Weekly Report Missing Alert History Comparison
  - **Location:** `src/monitoring/health_reporter.py:378-457`
  - **Problem:** The `generate_weekly_report()` method calculates `previous_health` score from `previous_metrics` (line 399-403), but comment at line 402 says "Note: We don't have previous alerts, so approximate". This means the previous health score is calculated with ZERO alerts (empty list), making it artificially high. The week-over-week health comparison is therefore inaccurate - current health might be 65 (with 5 alerts), previous health is 85 (with 0 alerts assumed), suggesting health degraded when alerts may have existed then too.
  - **Fix:** Either: (1) Store historical alerts in database and fetch them, or (2) Document this limitation in WeeklyReport.previous_health docstring and add a warning field: `previous_health_note: "Calculated without historical alerts"`.

- [ ] **BUG-093**: Collection Membership Not Enforced or Updated
  - **Location:** `src/tagging/collection_manager.py:194-227` (add_to_collection), no validation logic
  - **Problem:** Collections have `tag_filter` (e.g., `{"tags": ["python", "async"], "op": "AND"}`) but there's no code that:
    1. Validates memories match the filter when added
    2. Auto-updates collection membership when tags change
    3. Removes memories from collections when tags no longer match
  - **Impact:** Collections become stale and inaccurate over time; manual add_to_collection ignores tag_filter completely
  - **Fix:**
    1. Add validation in `add_to_collection()` to check memory tags match collection.tag_filter
    2. Add `refresh_collection(collection_id)` method to re-evaluate all members against filter
    3. Consider event-driven updates when tags are added/removed from memories

- [ ] **BUG-094**: Tag Name Validation Rejects Valid Unicode Characters
  - **Location:** `src/tagging/models.py:26-30`
  - **Problem:** Validator only allows `c.isalnum() or c in "-_"`, which rejects valid Unicode alphanumeric chars (e.g., "日本語", "Ελληνικά", "文档")
  - **Impact:** Non-English users cannot create natural language tags
  - **Fix:** Replace `c.isalnum()` with proper Unicode category check: `unicodedata.category(c) in ('Lu', 'Ll', 'Lt', 'Lm', 'Lo', 'Nd', 'Pc', 'Pd')`

- [ ] **BUG-098**: Archive Import Overwrites Conflict Without Validation
  - **Location:** `src/memory/archive_importer.py:122-124`
  - **Problem:** In "overwrite" conflict resolution, calls `self.compressor.delete_archive(target_project_name)` without checking if delete succeeded. If delete fails (permission error, file locked), import continues and may corrupt data.
  - **Fix:** Check return value of delete_archive() and raise error if deletion failed

- [ ] **BUG-100**: Import Checksum Verification Skips on Missing File
  - **Location:** `src/backup/importer.py:442-466`
  - **Problem:** `_verify_checksums()` logs warning "No checksums file found, skipping verification" (line 442-443) but continues import. This allows importing corrupted archives without detection.
  - **Fix:** Make checksum verification mandatory for archives created after version 1.0.0; add manifest field for "requires_checksum" validation

- [ ] **BUG-102**: Import Version Check Fails on Pre-Release Versions
  - **Location:** `src/backup/importer.py:374-377`
  - **Problem:** Version validation checks `if not version.startswith("1.")` which rejects valid versions like "1.0.0-beta" or "1.2.0rc1"
  - **Fix:** Use proper semver parsing (e.g., `packaging.version.parse()`) to validate major version compatibility

- [ ] **BUG-151**: TimeoutError from asyncio.timeout() Not Wrapped in Custom Exception
  - **Location:** `src/services/memory_service.py:320-322`, `src/services/code_indexing_service.py:271-273`, and 30+ other locations
  - **Problem:** `except TimeoutError: logger.error(...); raise StorageError("... timed out")` loses original timeout context and doesn't indicate which operation timed out or what the timeout value was
  - **Impact:** User sees generic "Memory store operation timed out" without knowing if it was Qdrant connection, embedding generation, or something else
  - **Fix:** Include operation name and timeout value in error message: `raise StorageError(f"Memory store operation timed out after 30s (operation: {op_name})", solution="Increase timeout or check Qdrant performance")`

- [ ] **BUG-310**: Missing Timeout Handling in MemoryService Import Path
  - **Location:** `src/services/memory_service.py:1259-1264`
  - **Problem:** In `import_memories()`, the `async with asyncio.timeout(30.0)` only wraps the `get_by_id()` call during conflict checking, but NOT the subsequent `store.update()` or `store.store()` calls within the same loop iteration. This creates inconsistent timeout protection - some operations time out after 30s, others never time out.
  - **Fix:** Wrap each store operation (lines 1285-1290, 1313-1319, 1352-1362) with separate timeout blocks. REF-027 marked "FIXED" but missed this code path.

- [ ] **BUG-316**: Missing Validation in CrossProjectService.search_all_projects
  - **Location:** `src/services/cross_project_service.py:69-200`
  - **Problem:** Method doesn't validate `limit` parameter (accepts any value including 0, negative, or extremely large). Could cause performance issues or OOM if someone passes limit=1000000. MemoryService validates limit in list_memories (line 773-774).
  - **Fix:** Add validation: `if not (1 <= limit <= 100): raise ValidationError("limit must be 1-100")`

- [ ] **BUG-317**: Missing Validation in CrossProjectService.search_all_projects
  - **Location:** `src/services/cross_project_service.py:69-200`
  - **Problem:** Method doesn't validate `limit` parameter (accepts any value including 0, negative, or extremely large). Could cause performance issues or OOM if someone passes limit=1000000. MemoryService validates limit in list_memories (line 773-774).
  - **Fix:** Add validation: `if not (1 <= limit <= 100): raise ValidationError("limit must be 1-100")`

- [ ] **BUG-318**: Batch Cache Get Returns Wrong Type on Timeout
  - **Location:** `src/embeddings/cache.py:294`
  - **Problem:** `batch_get()` returns `[None] * len(texts)` on timeout, but internal `_batch_get_sync()` has dict type hint mismatch
  - **Impact:** Type confusion - callers expect `List[Optional[List[float]]]` but signature suggests dict
  - **Fix:** Fix return type annotation of `_batch_get_sync()` to match `batch_get()`

- [ ] **BUG-328**: Git Detection Has No Error Recovery for Subprocess Timeouts
  - **Location:** `src/memory/git_detector.py:30-36`, `src/memory/git_detector.py:56-62`, and 4 other subprocess calls
  - **Problem:** All git subprocess calls use `timeout=5` but only catch generic `Exception`. If the timeout expires, it raises `subprocess.TimeoutExpired` which is caught and logged as debug, but the function returns False/None. However, if git hangs (but doesn't timeout), the entire indexing process blocks for 5 seconds PER FILE. For 100 files, that's 8+ minutes of blocking time.
  - **Fix:** Add specific `except subprocess.TimeoutExpired` handler, log as WARNING not debug (it's a system issue). Consider reducing timeout to 2s for faster failure.

- [ ] **BUG-339**: Embedding Model Configuration Mismatch Between config.py and allowed_fields.py
  - **Location:** `src/config.py:16-20` vs `src/core/allowed_fields.py:80-86`
  - **Problem:** config.py defines 3 supported embedding models (`EMBEDDING_MODEL_DIMENSIONS`): "all-MiniLM-L6-v2", "all-MiniLM-L12-v2", "all-mpnet-base-v2". But allowed_fields.py only allows "all-MiniLM-L6-v2" in the validation schema. If user sets `embedding_model="all-mpnet-base-v2"` (the DEFAULT), validation will reject it as invalid.
  - **Fix:** Update `allowed_fields.py:84` to `"allowed_values": ["all-MiniLM-L6-v2", "all-MiniLM-L12-v2", "all-mpnet-base-v2"]`

- [ ] **BUG-341**: Embedding Model Configuration Mismatch Between config.py and allowed_fields.py
  - **Location:** `src/config.py:16-20` vs `src/core/allowed_fields.py:80-86`
  - **Problem:** config.py defines 3 supported embedding models (`EMBEDDING_MODEL_DIMENSIONS`): "all-MiniLM-L6-v2", "all-MiniLM-L12-v2", "all-mpnet-base-v2". But allowed_fields.py only allows "all-MiniLM-L6-v2" in the validation schema. If user sets `embedding_model="all-mpnet-base-v2"` (the DEFAULT), validation will reject it as invalid.
  - **Fix:** Update `allowed_fields.py:84` to `"allowed_values": ["all-MiniLM-L6-v2", "all-MiniLM-L12-v2", "all-mpnet-base-v2"]`

- [ ] **BUG-352**: Missing Validation for Empty Embeddings Array in Duplicate Detector
  - **Location:** `src/analysis/code_duplicate_detector.py:159-163`
  - **Problem:** Line 159 checks `if embeddings.size == 0: raise ValueError("Embeddings array is empty")`, but this check happens AFTER the function signature promises to return an ndarray. An empty array is a valid input in some contexts (e.g., empty codebase), but raising ValueError breaks the contract. Additionally, returning an empty similarity matrix (0x0) might be more appropriate than failing.
  - **Fix:** Return `np.array([])` (empty 0x0 matrix) for empty input instead of raising, or document that empty input is invalid in docstring

- [ ] **BUG-357**: Inconsistent Exit Code Handling Across Commands  
  - **Location:** `src/cli/__init__.py:453` (prune uses sys.exit), vs `src/cli/__init__.py:476` (validate-install uses sys.exit), vs all other commands that don't
  - **Problem:** Only `prune` and `validate-install` commands properly return exit codes via `sys.exit()`. All other commands in `main_async()` don't set exit codes on failure. Shell scripts/CI cannot detect command failures.
  - **Impact:** Silent failures in automation - a failing `index` or `health` command will return exit code 0
  - **Fix:** Standardize: all async command methods should return int, `main_async()` should `sys.exit(code)` based on return value

- [ ] **BUG-359**: No Validation for User Config File Schema
  - **Location:** `src/config.py:692-696`
  - **Problem:** `_load_user_config_overrides()` loads arbitrary JSON and passes it as `**user_overrides` to `ServerConfig()`. If user puts invalid keys in config.json (typos, removed fields, nested dicts in wrong format), Pydantic's `extra="ignore"` silently discards them. User has no way to know their config is being ignored.
  - **Fix:** Add validation mode: if config file exists, validate keys against ServerConfig fields. Log WARNING for unrecognized keys. Add `--strict-config` mode that raises error on unknown keys.

- [ ] **BUG-361**: No Validation for User Config File Schema
  - **Location:** `src/config.py:692-696`
  - **Problem:** `_load_user_config_overrides()` loads arbitrary JSON and passes it as `**user_overrides` to `ServerConfig()`. If user puts invalid keys in config.json (typos, removed fields, nested dicts in wrong format), Pydantic's `extra="ignore"` silently discards them. User has no way to know their config is being ignored.
  - **Fix:** Add validation mode: if config file exists, validate keys against ServerConfig fields. Log WARNING for unrecognized keys. Add `--strict-config` mode that raises error on unknown keys.

- [ ] **BUG-384**: Feature Level Preset Modifies Config After Validation
  - **Location:** `src/config.py:394-419`
  - **Problem:** The `apply_feature_level_preset()` model_validator runs in mode='after', meaning it modifies config values AFTER Pydantic has validated them. If BASIC preset sets `self.memory.proactive_suggestions = False` but user explicitly enabled it via environment variable `CLAUDE_RAG_MEMORY__PROACTIVE_SUGGESTIONS=true`, the preset silently overrides user's explicit choice. No warning is logged.
  - **Fix:** Check if value was explicitly set (not default) before overriding. Add logging: "BASIC preset overriding proactive_suggestions from True to False". Or run preset in mode='before' so user values take precedence.

- [ ] **BUG-391**: TimeoutError Re-raised as Generic StorageError Loses Exception Type
  - **Location:** `src/services/memory_service.py:320-322`, and 20+ similar locations
  - **Problem:** Pattern `except TimeoutError: raise StorageError("operation timed out")` loses the original TimeoutError type. Callers can't distinguish timeouts from other storage errors (connection refused, disk full, etc.). This makes retry logic impossible - code that should retry on timeout will retry on all StorageErrors, including unretriable ones like disk full.
  - **Fix:** Create TimeoutError subclass of StorageError: `raise StorageTimeoutError("operation timed out") from e`. Update callers to catch and retry only TimeoutError.

- [ ] **BUG-402**: Trend Analysis Direction Logic Has Edge Case Bug
  - **Location:** `src/monitoring/health_reporter.py:353-363`
  - **Problem:** The trend direction determination uses compound ternary expressions that are hard to reason about. Line 353-356 for "higher_is_better" case: `direction = "improving" if change_percent > 5 else "degrading" if change_percent < -5 else "stable"`. This means a change of +4% is "stable", but -4% is also "stable". However, for "lower is better" metrics (line 359-362), the logic is flipped but uses the SAME thresholds. This means a 4.9% increase in noise_ratio is marked "stable" when it should be "degrading".
  - **Fix:** Use clearer threshold constants: `TREND_SIGNIFICANT_CHANGE = 5.0`. Break compound ternary into explicit if/elif for readability. Consider separate thresholds for improvement vs degradation (e.g., 5% improvement is good, but 3% degradation is concerning).

- [ ] **BUG-406**: No Validation for cross_project_default_mode Enum
  - **Location:** `src/config.py:87`
  - **Problem:** `cross_project_default_mode: str = "current"` has comment saying `"current" or "all"` but no validation enforces this. Should be `Literal["current", "all"]` type hint for Pydantic to validate.
  - **Fix:** Change to `cross_project_default_mode: Literal["current", "all"] = "current"`

- [ ] **BUG-408**: No Validation for cross_project_default_mode Enum
  - **Location:** `src/config.py:87`
  - **Problem:** `cross_project_default_mode: str = "current"` has comment saying `"current" or "all"` but no validation enforces this. Should be `Literal["current", "all"]` type hint for Pydantic to validate.
  - **Fix:** Change to `cross_project_default_mode: Literal["current", "all"] = "current"`

- [ ] **BUG-409**: Weekly Report Missing Alert History Comparison
  - **Location:** `src/monitoring/health_reporter.py:378-457`
  - **Problem:** The `generate_weekly_report()` method calculates `previous_health` score from `previous_metrics` (line 399-403), but comment at line 402 says "Note: We don't have previous alerts, so approximate". This means the previous health score is calculated with ZERO alerts (empty list), making it artificially high. The week-over-week health comparison is therefore inaccurate - current health might be 65 (with 5 alerts), previous health is 85 (with 0 alerts assumed), suggesting health degraded when alerts may have existed then too.
  - **Fix:** Either: (1) Store historical alerts in database and fetch them, or (2) Document this limitation in WeeklyReport.previous_health docstring and add a warning field: `previous_health_note: "Calculated without historical alerts"`.

- [ ] **BUG-411**: hybrid_fusion_method Has No Validation
  - **Location:** `src/config.py:369`
  - **Problem:** `hybrid_fusion_method: str = "weighted"` accepts any string. Valid values are likely "weighted", "rrf" (reciprocal rank fusion), "linear". No validation means user could set "invalid" and only discover at search time.
  - **Fix:** Add allowed values validation. Search codebase for where this is used to determine valid options, then add `Literal` type hint or field validator.

- [ ] **BUG-413**: hybrid_fusion_method Has No Validation
  - **Location:** `src/config.py:369`
  - **Problem:** `hybrid_fusion_method: str = "weighted"` accepts any string. Valid values are likely "weighted", "rrf" (reciprocal rank fusion), "linear". No validation means user could set "invalid" and only discover at search time.
  - **Fix:** Add allowed values validation. Search codebase for where this is used to determine valid options, then add `Literal` type hint or field validator.

- [ ] **BUG-415**: No Maximum Limit for analytics_retention_days
  - **Location:** `src/config.py:113`
  - **Problem:** `usage_analytics_retention_days: int = 90` has no validation. User could set to 36500 (100 years), causing analytics data to never be cleaned up, leading to unbounded storage growth.
  - **Fix:** Add field validator with reasonable upper bound (e.g., max 730 days / 2 years)

- [ ] **BUG-416**: No Maximum Limit for analytics_retention_days
  - **Location:** `src/config.py:113`
  - **Problem:** `usage_analytics_retention_days: int = 90` has no validation. User could set to 36500 (100 years), causing analytics data to never be cleaned up, leading to unbounded storage growth.
  - **Fix:** Add field validator with reasonable upper bound (e.g., max 730 days / 2 years)

- [ ] **BUG-419**: Auto-Tagger Regex Patterns Have High False Positive Rate
  - **Location:** `src/tagging/auto_tagger.py:21-121` (all pattern dictionaries)
  - **Problem:** Overly broad regex patterns trigger on unrelated content:
    - `r"\bimport\b"` matches "import taxes" discussion → tagged as "python"
    - `r"\bclass\b"` matches "world class developer" → tagged as "java"
    - `r"\bconst\b"` matches "constitutional law" → tagged as "javascript"
    - `r"\btest\b"` matches "test results" in medical context → tagged as "testing"
  - **Impact:** Tag pollution, reduced search precision, misleading auto-collections
  - **Fix:** Add context validation - patterns should require technical context:
    ```python

- [ ] **BUG-420**: Timing Dependencies in 30+ Tests (Flakiness Source)
  - **Location:** Tests using `asyncio.sleep()` or `time.sleep()` for synchronization
  - **Problem:** Found 30+ instances of sleep-based synchronization:
    - `test_file_watcher.py:85`: `await asyncio.sleep(0.05)` for debounce testing
    - `test_background_indexer.py:47,224,302,385,529`: Multiple sleeps for job status polling
    - `test_connection_health_checker.py:102,170,241`: Blocking sleeps for timeout tests
    - `test_usage_tracker.py:124,145`: Sleeps for flush timing
    - `test_connection_pool.py:346`: 1.5s sleep for recycling test
  - **Impact:** Tests are timing-dependent and flaky under load or in CI. Many marked `@pytest.mark.skip_ci` to hide the problem.
  - **Fix:** Replace sleeps with event-based synchronization (asyncio.Event, threading.Event) or mock time

- [ ] **BUG-421**: Timing Dependencies in 30+ Tests (Flakiness Source)
  - **Location:** Tests using `asyncio.sleep()` or `time.sleep()` for synchronization
  - **Problem:** Found 30+ instances of sleep-based synchronization:
    - `test_file_watcher.py:85`: `await asyncio.sleep(0.05)` for debounce testing
    - `test_background_indexer.py:47,224,302,385,529`: Multiple sleeps for job status polling
    - `test_connection_health_checker.py:102,170,241`: Blocking sleeps for timeout tests
    - `test_usage_tracker.py:124,145`: Sleeps for flush timing
    - `test_connection_pool.py:346`: 1.5s sleep for recycling test
  - **Impact:** Tests are timing-dependent and flaky under load or in CI. Many marked `@pytest.mark.skip_ci` to hide the problem.
  - **Fix:** Replace sleeps with event-based synchronization (asyncio.Event, threading.Event) or mock time

- [ ] **BUG-423**: Auto-Tagger Regex Patterns Have High False Positive Rate
  - **Location:** `src/tagging/auto_tagger.py:21-121` (all pattern dictionaries)
  - **Problem:** Overly broad regex patterns trigger on unrelated content:
    - `r"\bimport\b"` matches "import taxes" discussion - tagged as "python"
    - `r"\bclass\b"` matches "world class developer" - tagged as "java"
    - `r"\bconst\b"` matches "constitutional law" - tagged as "javascript"
    - `r"\btest\b"` matches "test results" in medical context - tagged as "testing"
  - **Impact:** Tag pollution, reduced search precision, misleading auto-collections
  - **Fix:** Add context validation - patterns should require technical context. Consider requiring 2+ patterns match before tagging a language

- [ ] **BUG-432**: filter_by_depth Off-By-One Error - Max Depth Not Inclusive
  - **Location:** `src/graph/dependency_graph.py:217`
  - **Problem:** Line 217 checks `if depth < max_depth:` before exploring neighbors, meaning a node at exactly max_depth won't have its children explored. Docstring says "max_depth: Maximum traversal depth (0 = root only, 1 = root + direct deps, etc.)" which suggests max_depth should be inclusive. With current code, max_depth=1 gives root only (depth 0), not root + direct deps.
  - **Example:** Root A → B → C, max_depth=1 should include A and B, but only includes A because B is at depth 1 and `1 < 1` is false
  - **Impact:** Filter returns one fewer level than documented, user confusion
  - **Fix:** Change to `if depth <= max_depth:` OR update docstring to clarify exclusive behavior

- [ ] **BUG-434**: filter_by_depth Off-By-One Error - Max Depth Not Inclusive
  - **Location:** `src/graph/dependency_graph.py:217`
  - **Problem:** Line 217 checks `if depth < max_depth:` before exploring neighbors, meaning a node at exactly max_depth won't have its children explored. Docstring says "max_depth: Maximum traversal depth (0 = root only, 1 = root + direct deps, etc.)" which suggests max_depth should be inclusive. With current code, max_depth=1 gives root only (depth 0), not root + direct deps.
  - **Example:** Root A → B → C, max_depth=1 should include A and B, but only includes A because B is at depth 1 and `1 < 1` is false
  - **Impact:** Filter returns one fewer level than documented, user confusion
  - **Fix:** Change to `if depth <= max_depth:` OR update docstring to clarify exclusive behavior

- [ ] **BUG-435**: Archive Import Overwrites Conflict Without Validation
  - **Location:** `src/memory/archive_importer.py:122-124`
  - **Problem:** In "overwrite" conflict resolution, calls `self.compressor.delete_archive(target_project_name)` without checking if delete succeeded. If delete fails (permission error, file locked), import continues and may corrupt data.
  - **Fix:** Check return value of delete_archive() and raise error if deletion failed

- [ ] **BUG-449**: Collection Membership Not Enforced or Updated
  - **Location:** `src/tagging/collection_manager.py:194-227` (add_to_collection), no validation logic
  - **Problem:** Collections have `tag_filter` (e.g., `{"tags": ["python", "async"], "op": "AND"}`) but there's no code that:
    1. Validates memories match the filter when added
    2. Auto-updates collection membership when tags change
    3. Removes memories from collections when tags no longer match
  - **Impact:** Collections become stale and inaccurate over time; manual add_to_collection ignores tag_filter completely
  - **Fix:**
    1. Add validation in `add_to_collection()` to check memory tags match collection.tag_filter
    2. Add `refresh_collection(collection_id)` method to re-evaluate all members against filter
    3. Consider event-driven updates when tags are added/removed from memories

- [ ] **BUG-452**: Tag Name Validation Rejects Valid Unicode Characters
  - **Location:** `src/tagging/models.py:26-30`
  - **Problem:** Validator only allows `c.isalnum() or c in "-_"`, which rejects valid Unicode alphanumeric chars (e.g., non-ASCII text in various languages)
  - **Impact:** Non-English users cannot create natural language tags
  - **Fix:** Replace `c.isalnum()` with proper Unicode category check using unicodedata module

- [ ] **BUG-066**: Cache Key Collision Risk for Unicode Text
  - **Location:** `src/embeddings/cache.py:108`
  - **Problem:** SHA256 hashes text as UTF-8 bytes, but doesn't normalize Unicode (NFC vs NFD forms)
  - **Impact:** Same text in different Unicode normalizations produces different cache keys, reducing hit rate
  - **Example:** "café" (NFC) vs "café" (NFD with combining accent) hash differently
  - **Fix:** Add `unicodedata.normalize('NFC', text)` before hashing

- [ ] **BUG-067**: GPU Memory Fraction Set Globally Affects All Processes
  - **Location:** `src/embeddings/generator.py:148-149`
  - **Problem:** `torch.cuda.set_per_process_memory_fraction()` affects entire process, not just this generator
  - **Impact:** Multiple EmbeddingGenerator instances will conflict, last one wins
  - **Fix:** Document this limitation or track if already set globally

- [ ] **BUG-068**: Keyword Boost Uses Substring Matching Instead of Word Boundaries
  - **Location:** `src/search/reranker.py:265-268`
  - **Problem:** `kw in content_lower` matches substrings, so "auth" matches "author", "authenticate", "unauthorized", inflating boost scores
  - **Fix:** Use word boundary regex: `re.search(rf'\b{re.escape(kw)}\b', content_lower)`

- [ ] **BUG-069**: Cascade Fusion Loses Vector Scores for Dual-Appearing Results
  - **Location:** `src/search/hybrid_search.py:312-321`
  - **Problem:** When a memory appears in both BM25 and vector results, cascade fusion includes it from BM25 with `vector_score=0.0` (line 316) but never updates this even though the vector score is available
  - **Fix:** After adding BM25 results, iterate through vector results for already-seen IDs and update their vector_score field

- [ ] **BUG-071**: Query Synonyms Non-Deterministic Due to Set Ordering
  - **Location:** `src/search/query_synonyms.py:223` and `src/search/query_synonyms.py:264`
  - **Problem:** `list(word_synonyms)[:max_synonyms]` iterates over unordered set, causing non-deterministic query expansion (different results on different runs)
  - **Fix:** Sort before slicing: `sorted(word_synonyms)[:max_synonyms]`

- [ ] **BUG-072**: Tokenization Mismatch Between BM25 and Query Expansion
  - **Location:** `src/search/bm25.py:96` preserves underscores, `src/search/query_synonyms.py:259` splits on underscores
  - **Problem:** BM25 tokenizes "user_id" as one token `["user_id"]`, but query expansion tokenizes as `["user", "id"]`, causing synonym mismatch
  - **Fix:** Align tokenization - either both preserve or both split underscores; recommend preserving for code identifiers

- [ ] **BUG-074**: Invalid Filter Exclusions Include Minus Sign in Semantic Query
  - **Location:** `src/search/query_dsl_parser.py:148`
  - **Problem:** Unrecognized filters like `-unknown:value` are treated as semantic terms by appending `match.group(0)`, which includes the `-` prefix
  - **Fix:** Append `match.group(0).lstrip('-')` to remove exclusion prefix from semantic terms

- [ ] **BUG-076**: JavaScript Call Extractor Fails Silently on tree-sitter Import Failure
  - **Location:** `src/analysis/call_extractors.py:232-242`
  - **Problem:** If `tree-sitter` or `tree-sitter-javascript` packages are not installed, `JavaScriptCallExtractor.__init__()` catches ImportError and sets `self.parser = None`, then all subsequent `extract_calls()` calls log warning and return empty list. This silently breaks call graph construction for JS/TS projects with no visible error to the user—they just get incomplete importance scores.
  - **Fix:** Either make tree-sitter a required dependency, or raise clear error on first use: "Install tree-sitter-javascript to analyze JavaScript files: pip install tree-sitter tree-sitter-javascript"

- [ ] **BUG-078**: Call Graph State Leak Between Files in UsageAnalyzer
  - **Location:** `src/analysis/usage_analyzer.py:124-126`
  - **Problem:** The code checks `if all_units and not self.call_graph:` before building call graph. This means if `calculate_importance()` is called with `all_units=None` after a previous call with `all_units=[...]`, the old call graph persists and affects the new calculation. If the user analyzes file A, then file B without calling `reset()`, file B's usage metrics will include caller counts from file A's call graph.
  - **Fix:** Always rebuild call graph when `all_units` is provided: change condition to `if all_units:` (remove `and not self.call_graph`)

- [ ] **BUG-085**: Capacity Forecasting Fails with Single Data Point
  - **Location:** `src/monitoring/capacity_planner.py:407-408`
  - **Problem:** The `_calculate_linear_growth_rate()` method checks `if len(historical_metrics) < 2: return 0.0` at line 407, but the check happens AFTER extracting data_points (line 411-414) and sorting (line 417). If someone passes a single-item list, the code continues to line 421-425 where it tries to compute x_values and y_values from a 1-element list, then line 428 checks `if len(x_values) < 2` again. This is redundant and confusing - the early return at line 407 should prevent this, but it's checked twice.
  - **Fix:** Move the `if len(historical_metrics) < 2` check to line 398 (top of function), before any processing. Remove redundant check at line 428.

- [ ] **BUG-089**: Remediation History Query Performance Degrades Over Time
  - **Location:** `src/monitoring/remediation.py:454-499`
  - **Problem:** The `get_remediation_history()` method queries `remediation_history` table with `WHERE timestamp >= ?` (line 474). If the table grows to 10,000+ rows over months, and caller requests `days=30`, the database must scan all rows to filter by timestamp. There's an index on timestamp (line 97-100), but SQLite's query planner might not use it efficiently if the retention_days is very large.
  - **Fix:** Add explicit `ORDER BY timestamp DESC LIMIT ?` to query, or use EXPLAIN QUERY PLAN to verify index usage. Consider adding a cleanup job to delete old remediation history (currently only `cleanup_old_alerts()` exists, no cleanup for remediation history).

- [ ] **BUG-090**: Health Scheduler Notification Callback Not Awaited
  - **Location:** `src/memory/health_scheduler.py:173-174`, `src/memory/health_scheduler.py:187-188`, `src/memory/health_scheduler.py:208-209`, `src/memory/health_scheduler.py:240-241`, `src/memory/health_scheduler.py:254-255`
  - **Problem:** The scheduler calls `await self.config.notification_callback(...)` at lines 174, 188, 209, 241, 255. However, `notification_callback` is typed as `Optional[Callable]` with no async specification (line 42). If user provides a synchronous callback function, the `await` will fail with "TypeError: object is not awaitable". If user provides an async callback, it works fine. The type annotation doesn't enforce async.
  - **Fix:** Change type annotation to `Optional[Callable[..., Awaitable[None]]]` to require async callbacks. Or detect sync vs async: `if asyncio.iscoroutinefunction(self.config.notification_callback): await callback(...) else: callback(...)`

- [ ] **BUG-095**: Missing Client Release on Export Scroll Loop Failure
  - **Location:** `src/backup/exporter.py:332-386`
  - **Problem:** In `_get_filtered_memories()`, if scroll loop raises exception (lines 366-379), client is only released in finally block at line 385. However, if exception occurs before finally (e.g., KeyError in line 378), client may not be released back to pool.
  - **Fix:** Wrap entire scroll loop in try/finally, ensure client release happens in finally block even on early exception

- [ ] **BUG-096**: Import Merge Metadata Uses Wrong Embedding
  - **Location:** `src/backup/importer.py:343-353`
  - **Problem:** In MERGE_METADATA conflict strategy (line 343-353), merges metadata from imported memory into existing, but then calls `_update_memory(existing, imported_embedding)` with imported embedding (line 351). This updates existing memory with wrong embedding vector.
  - **Fix:** Fetch existing embedding via `_get_embedding(existing.id)` or skip embedding update entirely in merge mode

- [ ] **BUG-097**: Backup Scheduler Creates Store Without Closing on Error
  - **Location:** `src/backup/scheduler.py:153-168`
  - **Problem:** `_run_backup_job()` creates store (line 154) and exporter (line 157), but if exception occurs between lines 159-166, store.close() at line 168 is never reached (no try/finally)
  - **Fix:** Wrap in try/finally to ensure store cleanup even on error

- [ ] **BUG-099**: Export Doesn't Validate Embedding Dimension Match
  - **Location:** `src/backup/exporter.py:149-153`
  - **Problem:** When creating portable archive with embeddings, exports numpy array without validating all embeddings have same dimension (line 151). Mismatched dimensions (e.g., after model change) will cause import failures.
  - **Fix:** Validate all embeddings have same shape before np.savez_compressed; log warning and skip malformed embeddings

- [ ] **BUG-105**: Import Keep Both Strategy Doesn't Prevent ID Collision
  - **Location:** `src/backup/importer.py:329-336`
  - **Problem:** KEEP_BOTH strategy appends "_imported" to ID (line 332), but if that ID also exists, will cause unique constraint violation on second import
  - **Fix:** Use UUID suffix instead: `imported.id = f"{imported.id}_{uuid.uuid4().hex[:8]}"`

- [ ] **BUG-106**: Bulk Archival Progress Callback Not Protected Against Exceptions
  - **Location:** `src/memory/bulk_archival.py:106-107`, `src/memory/bulk_archival.py:222-223`
  - **Problem:** Calls `progress_callback(project_name, idx, len(project_names))` without try/except. If user callback raises exception, entire bulk operation fails.
  - **Fix:** Wrap in try/except, log warning and continue on callback failure

- [ ] **BUG-152**: Silent Embedding Cache Failure Falls Back Without Warning
  - **Location:** `src/embeddings/cache.py:93`, `src/embeddings/cache.py:193`, `src/embeddings/cache.py:239`
  - **Problem:** Cache get/set operations catch all exceptions and silently log at debug level, returning None without warning user
  - **Impact:** Performance degradation from cache misses goes unnoticed; corrupted cache never surfaces as error
  - **Fix:** Log cache failures at WARNING level and include cache stats in health checks; consider emitting metric for cache error rate

- [ ] **BUG-153**: Connection Pool Errors Don't Distinguish Exhaustion from Health Check Failure
  - **Location:** `src/store/connection_pool.py:252-278`
  - **Problem:** `acquire()` raises generic exception whether pool is exhausted, health check fails, or connection creation fails
  - **Impact:** User can't tell if they need more connections, if Qdrant is down, or if there's a network issue
  - **Fix:** Create specific exception types: `PoolExhaustedError`, `HealthCheckFailedError`, `ConnectionCreationError` with actionable guidance

- [ ] **BUG-157**: File System Errors During Indexing Don't Include File Path
  - **Location:** `src/memory/incremental_indexer.py` (inferred from services)
  - **Problem:** PermissionError/FileNotFoundError during file parsing wrapped in generic IndexingError without showing which file failed
  - **Fix:** Include file path in all indexing errors: `raise IndexingError(f"Failed to parse {file_path}: {e}")`

- [ ] **BUG-158**: Float Division for Noise Ratio Without Zero Check
  - **Location:** `src/monitoring/metrics_collector.py:298`: `return float(stale) / float(total)`
  - **Problem:** No check if `total == 0` before division
  - **Impact:** ZeroDivisionError if no memories exist in database
  - **Fix:** Add guard in exception handler or before: `if total == 0: return 0.0`

- [ ] **BUG-159**: Module-Level Mutable Constant Risk
  - **Location:** Multiple files have module-level mutable constants
  - **Examples:**
    - `tests/conftest.py:490` - `COLLECTION_POOL = [f"test_pool_{i}" for i in range(4)]` (list)
    - All other instances are immutable (tuples, lists of strings used as constants)
  - **Problem:** While most are effectively immutable (lists of strings not modified), if code ever appends/modifies these, changes persist across test runs. Only real risk is COLLECTION_POOL if tests mutate it.
  - **Impact:** Test isolation violations, flaky tests
  - **Fix:** Convert to tuple or make defensive copy in fixture

- [ ] **BUG-277**: ThreadPoolExecutor Cleanup Uses __del__ in Generator
  - **Location:** `src/embeddings/generator.py:420-426`
  - **Problem:** `__del__()` fallback cleanup with `wait=False` means threads may not finish cleanly, potentially leaving file handles or database connections open
  - **Impact:** Under load, rapid generator creation/destruction could accumulate zombie threads
  - **Fix:** Same as BUG-150 - ensure `close()` is always called via signal handlers or context managers

- [ ] **BUG-278**: Unsafe Counter Increments Without Lock Protection
  - **Location:** 200+ instances of `self.stats["key"] += 1` across services
  - **Examples:**
    - `src/services/memory_service.py:127,131,325,459,497,563` (stats dict updates)
    - `src/services/analytics_service.py:81,118,159,202` (analytics_queries counter)
    - `src/services/health_service.py:112,145,367` (health_checks counter)
    - `src/memory/file_watcher.py:169,173,179,182,186,190,198,201,229,233,241,252` (event stats)
  - **Problem:** Read-modify-write race. `x += 1` expands to `x = x + 1` (read x, add 1, write back). Two concurrent increments can result in only +1 instead of +2 due to lost update.
  - **Impact:** Underreported metrics, incorrect statistics, violated invariants (e.g., total != sum of parts)
  - **Fix:** Protect with `threading.Lock` (for sync code) or use `asyncio.Lock` (for async). See existing pattern in `src/memory/usage_tracker.py:40,146` and `src/embeddings/cache.py:154,166,188,195` which correctly use `with self._counter_lock:`
  - **Note:** Some counters already protected (REF-030 fixes in connection_pool.py, usage_tracker.py, cache.py), but 150+ remain vulnerable

- [ ] **BUG-279**: bulk_operations.py MemoryStore Protocol Incomplete - Missing Required Methods
  - **Location:** `src/memory/bulk_operations.py:56-70` (Protocol definition), `src/store/base.py:8-318` (actual interface)
  - **Problem:** Protocol defines only 3 methods (delete, update, get_by_id) but BulkOperations class likely needs more store methods. Real MemoryStore ABC has 14 abstract methods. If BulkOperations uses any method not in Protocol, it will fail at runtime.
  - **Impact:** MEDIUM - Protocol doesn't enforce full contract, type checkers won't catch missing method errors
  - **Fix:** Either (1) extend Protocol to match MemoryStore ABC or (2) use MemoryStore ABC directly instead of Protocol

- [ ] **BUG-287**: Temporary Directory Cleanup in Tests Ignores Errors Silently
  - **Location:** Multiple test files use `shutil.rmtree(temp_dir, ignore_errors=True)` (e.g., `tests/integration/test_hybrid_search_integration.py:56`)
  - **Problem:** If files are still open (due to leaked handles), cleanup fails silently, leaving temp directories on disk
  - **Impact:** Test suite can leak dozens of temp directories over time, eventually filling disk on CI runners
  - **Fix:** Remove `ignore_errors=True`, let cleanup failures raise to expose handle leaks; add explicit file close checks before rmtree

- [ ] **BUG-290**: Pagination P95 Calculation Can Access Wrong Index
  - **Location:** `src/monitoring/metrics_collector.py:359-360`
  - **Problem:** `p95_index = int(len(latencies) * 0.95)` can equal `len(latencies)` for certain list sizes (e.g., len=20 → index=19, but len=21 → index=19, len=1 → index=0 which is valid but len=0 → index=0 but list is empty)
  - **Impact:** For exactly 20 items: `int(20 * 0.95) = 19` which is valid (last index). But the issue is when `latencies` is empty, index=0 causes IndexError. Already caught by empty check at line 356-357, but still a boundary risk.
  - **Fix:** Ensure index is clamped: `p95_index = min(int(len(latencies) * 0.95), len(latencies) - 1)`

- [ ] **BUG-293**: Pagination P95 Calculation Can Access Wrong Index
  - **Location:** `src/monitoring/metrics_collector.py:359-360`
  - **Problem:** `p95_index = int(len(latencies) * 0.95)` can equal `len(latencies)` for certain list sizes (e.g., len=20 → index=19, but len=21 → index=19, len=1 → index=0 which is valid but len=0 → index=0 but list is empty)
  - **Impact:** For exactly 20 items: `int(20 * 0.95) = 19` which is valid (last index). But the issue is when `latencies` is empty, index=0 causes IndexError. Already caught by empty check at line 356-357, but still a boundary risk.
  - **Fix:** Ensure index is clamped: `p95_index = min(int(len(latencies) * 0.95), len(latencies) - 1)`

- [ ] **BUG-295**: SQLite Connection Closed in __del__ Without Commit
  - **Location:** `src/embeddings/cache.py:499-515`
  - **Problem:** `close()` attempts to commit before closing, but if `close()` is never called and `__del__` runs, no commit happens - pending writes are lost
  - **Impact:** Cache entries written but not committed will be lost on abnormal shutdown
  - **Fix:** Add `try: self.conn.commit()` in `__del__` before close, or require explicit `close()` via context manager

- [ ] **BUG-299**: File Descriptor Leak in mkstemp Usage
  - **Location:** `tests/unit/test_usage_pattern_tracker.py:18-19`, `setup.py:606`, and similar
  - **Problem:** `fd, path = tempfile.mkstemp()` returns file descriptor, but only some call sites close it with `os.close(fd)`. Others just use path and leave fd open.
  - **Impact:** Each test that leaks fd consumes one file descriptor; running 1000 tests can exhaust ulimit
  - **Fix:** Audit all mkstemp usage and ensure `os.close(fd)` is called immediately after, or use NamedTemporaryFile with context manager

- [ ] **BUG-300**: SQLite Cache Read-Modify-Write Race (access_count)
  - **Location:** `src/embeddings/cache.py:171-178`
  - **Code:**
    ```python
    row = cursor.fetchone()  # Read access_count
    self.conn.execute("""UPDATE embeddings SET access_count = ?""",
        (access_count + 1, cache_key))  # Write incremented value
    ```
  - **Problem:** Classic lost update. Two concurrent get() calls read same access_count (e.g., 5), both increment to 6, both write 6. Result: access_count = 6 instead of 7.
  - **Impact:** Underreported access counts, incorrect LRU/popularity metrics
  - **Fix:** Use SQLite atomic increment: `UPDATE embeddings SET access_count = access_count + 1 WHERE cache_key = ?`

- [ ] **BUG-304**: ContextVar Leakage Risk in Tracing
  - **Location:** `src/core/tracing.py:11,69-76`
  - **Code:**
    ```python
    operation_id: ContextVar[str] = ContextVar('operation_id', default='')
    
    async def wrapper(*args, **kwargs):
        op_id = new_operation()  # Sets context
        try:
            return await func(*args, **kwargs)
        finally:
            clear_operation_id()  # Clears on exit
    ```
  - **Problem:** If function raises exception before clear_operation_id(), AND asyncio reuses the context, next operation inherits stale ID. While finally should execute, asyncio.CancelledError could interrupt cleanup.
  - **Impact:** Cross-request operation ID pollution, incorrect distributed tracing
  - **Fix:** Use context manager or ensure cleanup with try/except CancelledError explicitly

- [ ] **BUG-313**: Service Boundary Violation - MemoryService Directly Uses Store Methods Not in Interface
  - **Location:** `src/services/memory_service.py:1082-1089` (export_memories), `src/services/memory_service.py:683-690` (reindex_project)
  - **Problem:** MemoryService calls `store.list_memories()` and `store.delete_code_units_by_project()` directly, but these may not be implemented by all store backends (SQLite vs Qdrant). This creates tight coupling and violates store abstraction.
  - **Fix:** Add these methods to MemoryStore abstract interface or move operations to dedicated services (CodeIndexingService should own delete_code_units_by_project).

- [ ] **BUG-314**: Service Boundary Violation - MemoryService Directly Uses Store Methods Not in Interface
  - **Location:** `src/services/memory_service.py:1082-1089` (export_memories), `src/services/memory_service.py:683-690` (reindex_project)
  - **Problem:** MemoryService calls `store.list_memories()` and `store.delete_code_units_by_project()` directly, but these may not be implemented by all store backends (SQLite vs Qdrant). This creates tight coupling and violates store abstraction.
  - **Fix:** Add these methods to MemoryStore abstract interface or move operations to dedicated services (CodeIndexingService should own delete_code_units_by_project).

- [ ] **BUG-325**: Normalization Returns Max Score for All-Zero Results
  - **Location:** `src/search/hybrid_search.py:365-367`
  - **Problem:** When all scores are identical (including all 0.0), `_normalize_scores` returns `[1.0] * len(scores)`, giving maximum normalized score to zero-relevance results
  - **Fix:** Check if `max_score == 0.0` and return `[0.0] * len(scores)` instead of `[1.0]`

- [ ] **BUG-327**: Circular Dependency Detection Has False Negatives
  - **Location:** `src/memory/dependency_graph.py:279-312`
  - **Problem:** The `detect_circular_dependencies()` method uses DFS with visited/rec_stack tracking, but only starts DFS from nodes that are keys in `self.dependencies` dict (line 308). If a file B imports A, but A doesn't import anything, then A won't be in `dependencies.keys()` and won't be explored. This misses cycles like: A -> B -> C -> A where A has no outgoing dependencies in the dict.
  - **Fix:** Change line 308 to iterate over `set(self.dependencies.keys()) | set(self.dependents.keys())` to ensure all nodes are explored

- [ ] **BUG-329**: File Change Hashing Doesn't Handle Large Files Efficiently
  - **Location:** `src/memory/incremental_indexer.py:283-284`
  - **Problem:** The code reads entire file into memory with `f.read()` to parse it, regardless of size. For files >100MB, this can cause memory pressure. The indexer supports files up to gigabytes (no size limit check), which could OOM the process.
  - **Fix:** Add file size check before reading: `if file_path.stat().st_size > 10*1024*1024: logger.warning("File too large, skipping"); return {...}`. Set max file size limit (10MB default, configurable).

- [ ] **BUG-330**: Missing Encoding Declaration in Import Extractor
  - **Location:** `src/memory/import_extractor.py:96-98`, and all language-specific extractors
  - **Problem:** The `extract_imports()` method receives `source_code` as a string parameter but doesn't document required encoding. If caller passes source_code decoded with wrong encoding (e.g., latin-1 instead of utf-8), regex matching will fail silently or produce garbage results. The incremental_indexer opens files with `encoding="utf-8"` (line 283) but import_extractor has no encoding awareness.
  - **Fix:** Document that source_code must be UTF-8 decoded. Add encoding parameter with default 'utf-8'. Handle UnicodeDecodeError gracefully.

- [ ] **BUG-337**: Missing Command Integration for browse, tutorial, validate-setup, perf
  - **Location:** `src/cli/__init__.py:166-169` (browse declared), `src/cli/__init__.py:69` (tutorial in help text), `src/cli/__init__.py:68` (validate-setup in help text)
  - **Problem:** Commands declared in help text and parsers created but NOT integrated into `main_async()`. The `browse` parser exists (line 166) and `tutorial`/`validate-setup` appear in help but NO handler in `main_async()` (lines 428-485). Users will see these commands but get "No command specified" error when trying to use them.
  - **Impact:** User-facing features completely broken - tutorial for onboarding new users, browse for memory exploration, validate-setup for diagnostics all non-functional
  - **Fix:** Add handlers in `main_async()`: `elif args.command == "browse": await run_memory_browser()`, `elif args.command == "tutorial": ...`, `elif args.command == "validate-setup": cmd = ValidateSetupCommand(); await cmd.run(args)`

- [ ] **BUG-347**: perf Commands Import But No Parser Created
  - **Location:** `src/cli/__init__.py:23` imports `perf_report_command, perf_history_command` but no subparser added
  - **Problem:** Performance command functions imported but never registered with argparse. Users cannot invoke `claude-rag perf report` or `claude-rag perf history` - the commands don't exist in CLI
  - **Impact:** Performance monitoring functionality completely inaccessible via CLI
  - **Fix:** Add perf subparser similar to health-monitor (lines 354-410): create `perf_parser` with `report` and `history` subcommands

- [ ] **BUG-349**: Config File JSON Parse Errors Are Silently Ignored
  - **Location:** `src/config.py:671-677`
  - **Problem:** `_load_user_config_overrides()` catches all exceptions with generic `except Exception as e` and returns empty dict. If user creates malformed JSON in `~/.claude-rag/config.json` (missing comma, trailing comma, syntax error), the config is silently ignored with only a WARNING log. User thinks config is applied but defaults are used instead.
  - **Fix:** Catch `json.JSONDecodeError` specifically and raise `ConfigurationError` with helpful message showing the JSON syntax error location. Only catch `FileNotFoundError` silently.

- [ ] **BUG-351**: Config File JSON Parse Errors Are Silently Ignored
  - **Location:** `src/config.py:671-677`
  - **Problem:** `_load_user_config_overrides()` catches all exceptions with generic `except Exception as e` and returns empty dict. If user creates malformed JSON in `~/.claude-rag/config.json` (missing comma, trailing comma, syntax error), the config is silently ignored with only a WARNING log. User thinks config is applied but defaults are used instead.
  - **Fix:** Catch `json.JSONDecodeError` specifically and raise `ConfigurationError` with helpful message showing the JSON syntax error location. Only catch `FileNotFoundError` silently.

- [ ] **BUG-364**: Unsafe Dict Append in MultiRepositoryIndexer Without Lock
  - **Location:** `src/memory/multi_repository_indexer.py:392-401`
  - **Problem:** `repository_results.append(result)` is called from multiple concurrent tasks created by `asyncio.gather()`. The `repository_results` list is mutated concurrently without synchronization. While CPython's GIL makes `list.append()` atomic at bytecode level, this is NOT guaranteed in other Python implementations or under asyncio context switches.
  - **Fix:** Use `asyncio.Lock()` to protect the append operation, or use `asyncio.Queue` for thread-safe result collection

- [ ] **BUG-365**: Unsafe Dict Append in MultiRepositoryIndexer Without Lock
  - **Location:** `src/memory/multi_repository_indexer.py:392-401`
  - **Problem:** `repository_results.append(result)` is called from multiple concurrent tasks created by `asyncio.gather()`. The `repository_results` list is mutated concurrently without synchronization. While CPython's GIL makes `list.append()` atomic at bytecode level, this is NOT guaranteed in other Python implementations or under asyncio context switches.
  - **Fix:** Use `asyncio.Lock()` to protect the append operation, or use `asyncio.Queue` for thread-safe result collection

- [ ] **BUG-372**: Fire-and-Forget create_task in FileWatcher Debounce
  - **Location:** `src/memory/file_watcher.py:271-273`
  - **Problem:** `self.debounce_task = asyncio.create_task(self._execute_debounced_callback())` is created but if the task raises an exception, it's never awaited or checked. The exception will be silently lost. This is different from the fixed BUG-055/056 because the task IS stored in `self.debounce_task`, but there's no error callback registered.
  - **Fix:** Add error callback: `self.debounce_task.add_done_callback(self._handle_task_error)` similar to usage_tracker.py pattern (lines 153, 230)

- [ ] **BUG-373**: Fire-and-Forget create_task in FileWatcher Debounce
  - **Location:** `src/memory/file_watcher.py:271-273`
  - **Problem:** `self.debounce_task = asyncio.create_task(self._execute_debounced_callback())` is created but if the task raises an exception, it's never awaited or checked. The exception will be silently lost. This is different from the fixed BUG-055/056 because the task IS stored in `self.debounce_task`, but there's no error callback registered.
  - **Fix:** Add error callback: `self.debounce_task.add_done_callback(self._handle_task_error)` similar to usage_tracker.py pattern (lines 153, 230)

- [ ] **BUG-374**: analytics and session-summary Commands Not Async But Called from Async Context
  - **Location:** `src/cli/__init__.py:461-470` calls `run_analytics_command()` and `run_session_summary_command()` without await
  - **Problem:** These functions are synchronous (no async def) but called from `main_async()`. They block the event loop. If analytics needs to query Qdrant, it should be async. Currently works but violates async patterns.
  - **Impact:** Performance degradation - synchronous database access blocks event loop
  - **Fix:** Convert `run_analytics_command()` and `run_session_summary_command()` to async, add await in main_async()

- [ ] **BUG-380**: Missing Lock Around file_watcher.py pending_files Access
  - **Location:** `src/memory/file_watcher.py:256-273`
  - **Problem:** `_debounce_callback()` acquires lock to add to `pending_files` (line 256-257), releases lock, cancels old task (262-268), then re-acquires lock (270). Between lock releases, another watchdog event could fire and try to modify `pending_files` or `debounce_task`. This creates race window where task cancellation could target wrong task.
  - **Fix:** Hold lock for entire duration: acquire once at line 256, don't release until after creating new task at line 273

- [ ] **BUG-381**: Missing Lock Around file_watcher.py pending_files Access
  - **Location:** `src/memory/file_watcher.py:256-273`
  - **Problem:** `_debounce_callback()` acquires lock to add to `pending_files` (line 256-257), releases lock, cancels old task (262-268), then re-acquires lock (270). Between lock releases, another watchdog event could fire and try to modify `pending_files` or `debounce_task`. This creates race window where task cancellation could target wrong task.
  - **Fix:** Hold lock for entire duration: acquire once at line 256, don't release until after creating new task at line 273

- [ ] **BUG-382**: Click-Based Commands Not Integrated with Main CLI  
  - **Location:** `src/cli/auto_tag_command.py:17` uses `@click.command`, `src/cli/collections_command.py:16` uses `@click.group`, `src/cli/tags_command.py:16` uses `@click.group`
  - **Problem:** Three commands use Click decorators but main CLI uses argparse. These commands have separate entry points and aren't discoverable via `claude-rag --help`. Users don't know these features exist.
  - **Impact:** Hidden features - auto-tagging, collection management, tag management completely undiscoverable
  - **Fix:** Either (1) convert Click commands to argparse and integrate into main CLI, or (2) add to help text with note "Run separately: python -m src.cli.tags --help"

- [ ] **BUG-383**: Exception in Nested Import Loop Lost Without Context
  - **Location:** `src/services/memory_service.py:1366`, nested inside another exception handler at line 1385
  - **Problem:** Import loop at line 1251-1367 catches exceptions per-memory and appends to errors list. The outer exception handler at 1385 catches general exceptions but logs "Failed to import memories" without including the accumulated errors list. If 50 of 100 memories fail with different errors, only the last exception is logged, losing all diagnostic information about the 49 other failures.
  - **Fix:** Include errors list in outer exception log: `logger.error(f"Failed to import memories: {e}. Errors: {errors[:10]}", exc_info=True)` (limit to first 10 to avoid log spam)

- [ ] **BUG-385**: Exception in Nested Import Loop Lost Without Context
  - **Location:** `src/services/memory_service.py:1366`, nested inside another exception handler at line 1385
  - **Problem:** Import loop at line 1251-1367 catches exceptions per-memory and appends to errors list. The outer exception handler at 1385 catches general exceptions but logs "Failed to import memories" without including the accumulated errors list. If 50 of 100 memories fail with different errors, only the last exception is logged, losing all diagnostic information about the 49 other failures.
  - **Fix:** Include errors list in outer exception log: `logger.error(f"Failed to import memories: {e}. Errors: {errors[:10]}", exc_info=True)` (limit to first 10 to avoid log spam)

- [ ] **BUG-387**: Capacity Forecasting Fails with Single Data Point
  - **Location:** `src/monitoring/capacity_planner.py:407-408`
  - **Problem:** The `_calculate_linear_growth_rate()` method checks `if len(historical_metrics) < 2: return 0.0` at line 407, but the check happens AFTER extracting data_points (line 411-414) and sorting (line 417). If someone passes a single-item list, the code continues to line 421-425 where it tries to compute x_values and y_values from a 1-element list, then line 428 checks `if len(x_values) < 2` again. This is redundant and confusing - the early return at line 407 should prevent this, but it's checked twice.
  - **Fix:** Move the `if len(historical_metrics) < 2` check to line 398 (top of function), before any processing. Remove redundant check at line 428.

- [ ] **BUG-388**: BackgroundIndexer._active_tasks Dict Modified During Iteration
  - **Location:** `src/memory/background_indexer.py:488-492`
  - **Problem:** `finally` block deletes from `_active_tasks` dict, but if multiple jobs complete simultaneously, one job's cleanup could modify dict while another job is being cleaned up. While current code checks `if job_id in self._active_tasks`, this is not atomic with the deletion.
  - **Fix:** Use `self._active_tasks.pop(job_id, None)` instead of `del self._active_tasks[job_id]` (already documented in BUG-067)

- [ ] **BUG-389**: BackgroundIndexer._active_tasks Dict Modified During Iteration
  - **Location:** `src/memory/background_indexer.py:488-492`
  - **Problem:** `finally` block deletes from `_active_tasks` dict, but if multiple jobs complete simultaneously, one job's cleanup could modify dict while another job is being cleaned up. While current code checks `if job_id in self._active_tasks`, this is not atomic with the deletion.
  - **Fix:** Use `self._active_tasks.pop(job_id, None)` instead of `del self._active_tasks[job_id]` (already documented in BUG-067)

- [ ] **BUG-392**: Recency Decay Halflife Only Validates >0, Not Range
  - **Location:** `src/config.py:550-551`
  - **Problem:** `recency_decay_halflife_days` only checks `<= 0` but has no upper bound. User could set it to 100 years (36500 days), making all memories equally "recent" and breaking recency scoring. Typical useful range is 1-90 days.
  - **Fix:** Add upper bound check: `if recency_decay_halflife_days > 365: raise ValueError("recency_decay_halflife_days should not exceed 1 year (365 days)")`

- [ ] **BUG-394**: Recency Decay Halflife Only Validates >0, Not Range
  - **Location:** `src/config.py:550-551`
  - **Problem:** `recency_decay_halflife_days` only checks `<= 0` but has no upper bound. User could set it to 100 years (36500 days), making all memories equally "recent" and breaking recency scoring. Typical useful range is 1-90 days.
  - **Fix:** Add upper bound check: `if recency_decay_halflife_days > 365: raise ValueError("recency_decay_halflife_days should not exceed 1 year (365 days)")`

- [ ] **BUG-414**: Remediation History Query Performance Degrades Over Time
  - **Location:** `src/monitoring/remediation.py:454-499`
  - **Problem:** The `get_remediation_history()` method queries `remediation_history` table with `WHERE timestamp >= ?` (line 474). If the table grows to 10,000+ rows over months, and caller requests `days=30`, the database must scan all rows to filter by timestamp. There's an index on timestamp (line 97-100), but SQLite's query planner might not use it efficiently if the retention_days is very large.
  - **Fix:** Add explicit `ORDER BY timestamp DESC LIMIT ?` to query, or use EXPLAIN QUERY PLAN to verify index usage. Consider adding a cleanup job to delete old remediation history (currently only `cleanup_old_alerts()` exists, no cleanup for remediation history).

- [ ] **BUG-417**: Health Scheduler Notification Callback Not Awaited
  - **Location:** `src/memory/health_scheduler.py:173-174`, `src/memory/health_scheduler.py:187-188`, `src/memory/health_scheduler.py:208-209`, `src/memory/health_scheduler.py:240-241`, `src/memory/health_scheduler.py:254-255`
  - **Problem:** The scheduler calls `await self.config.notification_callback(...)` at lines 174, 188, 209, 241, 255. However, `notification_callback` is typed as `Optional[Callable]` with no async specification (line 42). If user provides a synchronous callback function, the `await` will fail with "TypeError: object is not awaitable". If user provides an async callback, it works fine. The type annotation doesn't enforce async.
  - **Fix:** Change type annotation to `Optional[Callable[..., Awaitable[None]]]` to require async callbacks. Or detect sync vs async: `if asyncio.iscoroutinefunction(self.config.notification_callback): await callback(...) else: callback(...)`

- [ ] **BUG-418**: Missing Client Release on Export Scroll Loop Failure
  - **Location:** `src/backup/exporter.py:332-386`
  - **Problem:** In `_get_filtered_memories()`, if scroll loop raises exception (lines 366-379), client is only released in finally block at line 385. However, if exception occurs before finally (e.g., KeyError in line 378), client may not be released back to pool.
  - **Fix:** Wrap entire scroll loop in try/finally, ensure client release happens in finally block even on early exception

- [ ] **BUG-422**: Mermaid Formatter Missing Newline Escaping in Labels
  - **Location:** `src/graph/formatters/mermaid_formatter.py:94, 102`
  - **Problem:** Node labels include file names and metadata with `<br/>` HTML tags (line 94), but if filename contains literal `\n` or special chars like `"`, `[`, `]`, these aren't escaped. Mermaid syntax uses `[label]` for nodes - a filename with `]` will break parsing.
  - **Example:** File `/project/test[1].py` → node syntax `A["test[1].py"]` breaks Mermaid parser
  - **Impact:** Invalid Mermaid output for files with brackets, quotes, or special characters
  - **Fix:** Add `_escape_mermaid_label()` method that escapes `"`, `[`, `]`, and converts `\n` to `<br/>`

- [ ] **BUG-424**: Mermaid Formatter Missing Newline Escaping in Labels
  - **Location:** `src/graph/formatters/mermaid_formatter.py:94, 102`
  - **Problem:** Node labels include file names and metadata with `<br/>` HTML tags (line 94), but if filename contains literal `\n` or special chars like `"`, `[`, `]`, these aren't escaped. Mermaid syntax uses `[label]` for nodes - a filename with `]` will break parsing.
  - **Example:** File `/project/test[1].py` → node syntax `A["test[1].py"]` breaks Mermaid parser
  - **Impact:** Invalid Mermaid output for files with brackets, quotes, or special characters
  - **Fix:** Add `_escape_mermaid_label()` method that escapes `"`, `[`, `]`, and converts `\n` to `<br/>`

- [ ] **BUG-425**: Import Merge Metadata Uses Wrong Embedding
  - **Location:** `src/backup/importer.py:343-353`
  - **Problem:** In MERGE_METADATA conflict strategy (line 343-353), merges metadata from imported memory into existing, but then calls `_update_memory(existing, imported_embedding)` with imported embedding (line 351). This updates existing memory with wrong embedding vector.
  - **Fix:** Fetch existing embedding via `_get_embedding(existing.id)` or skip embedding update entirely in merge mode

- [ ] **BUG-426**: Tag Case Sensitivity Inconsistent with Retrieval
  - **Location:** `src/tagging/tag_manager.py:86` (normalizes to lowercase), but `get_tag_by_path:177` also lowercases
  - **Problem:** Tags are normalized to lowercase ("API" → "api", "FastAPI" → "fastapi") but this is only enforced in tag_manager. If external code queries tags or if user searches, case mismatches can occur. Additionally, hierarchical paths like "language/Python" get normalized to "language/python" which loses readability.
  - **Impact:** User searches for "API" won't find memories tagged "api"; confusion about canonical tag names
  - **Fix:** 
    1. Document case normalization policy clearly
    2. Add case-insensitive search option for user-facing queries
    3. Consider preserving display_name (original case) separate from normalized search key

- [ ] **BUG-427**: DOT Formatter Incomplete Escaping - Missing Newline Handling
  - **Location:** `src/graph/formatters/dot_formatter.py:177-191`
  - **Problem:** `_escape_dot_string()` escapes backslashes and quotes, but doesn't handle literal newlines (`\n` in file paths) or other DOT special chars like `<`, `>`, `{`, `}`. If a file path contains newline, the DOT output will have literal line break inside quoted string, breaking syntax.
  - **Example:** File path `/tmp/test\nfile.py` (unlikely but possible on Linux) → DOT: `label="/tmp/test` (line break) `file.py"` (syntax error)
  - **Impact:** Malformed DOT output for edge-case file paths, Graphviz rendering fails
  - **Fix:** Extend escaping to replace `\n` → `\\n`, `\r` → `\\r`, `\t` → `\\t`

- [ ] **BUG-428**: Tag Case Sensitivity Inconsistent with Retrieval
  - **Location:** `src/tagging/tag_manager.py:86` (normalizes to lowercase), but `get_tag_by_path:177` also lowercases
  - **Problem:** Tags are normalized to lowercase ("API" becomes "api", "FastAPI" becomes "fastapi") but this is only enforced in tag_manager. If external code queries tags or if user searches, case mismatches can occur. Additionally, hierarchical paths like "language/Python" get normalized to "language/python" which loses readability.
  - **Impact:** User searches for "API" won't find memories tagged "api"; confusion about canonical tag names
  - **Fix:**
    1. Document case normalization policy clearly
    2. Add case-insensitive search option for user-facing queries
    3. Consider preserving display_name (original case) separate from normalized search key

- [ ] **BUG-429**: DOT Formatter Incomplete Escaping - Missing Newline Handling
  - **Location:** `src/graph/formatters/dot_formatter.py:177-191`
  - **Problem:** `_escape_dot_string()` escapes backslashes and quotes, but doesn't handle literal newlines (`\n` in file paths) or other DOT special chars like `<`, `>`, `{`, `}`. If a file path contains newline, the DOT output will have literal line break inside quoted string, breaking syntax.
  - **Example:** File path `/tmp/test\nfile.py` (unlikely but possible on Linux) → DOT: `label="/tmp/test` (line break) `file.py"` (syntax error)
  - **Impact:** Malformed DOT output for edge-case file paths, Graphviz rendering fails
  - **Fix:** Extend escaping to replace `\n` → `\\n`, `\r` → `\\r`, `\t` → `\\t`

- [ ] **BUG-430**: Backup Scheduler Creates Store Without Closing on Error
  - **Location:** `src/backup/scheduler.py:153-168`
  - **Problem:** `_run_backup_job()` creates store (line 154) and exporter (line 157), but if exception occurs between lines 159-166, store.close() at line 168 is never reached (no try/finally)
  - **Fix:** Wrap in try/finally to ensure store cleanup even on error

- [ ] **BUG-431**: Collection Tag Filter Not Applied in get_collection_memories
  - **Location:** `src/tagging/collection_manager.py:257-274`
  - **Problem:** `get_collection_memories()` just returns all memory_ids from `collection_memories` table. It completely ignores the collection's `tag_filter`. Auto-generated collections (line 301-372) have tag_filter but it's never actually used for retrieval.
  - **Impact:** Collections with tag_filter are purely manual membership lists; auto-collection feature is non-functional
  - **Fix:** 
    1. If collection.tag_filter exists, query memory_tags to find memories matching filter
    2. If collection.tag_filter is None, fall back to current manual membership list
    3. Add `auto_update: bool` flag to collections to control behavior

- [ ] **BUG-433**: Collection Tag Filter Not Applied in get_collection_memories
  - **Location:** `src/tagging/collection_manager.py:257-274`
  - **Problem:** `get_collection_memories()` just returns all memory_ids from `collection_memories` table. It completely ignores the collection's `tag_filter`. Auto-generated collections (line 301-372) have tag_filter but it's never actually used for retrieval.
  - **Impact:** Collections with tag_filter are purely manual membership lists; auto-collection feature is non-functional
  - **Fix:**
    1. If collection.tag_filter exists, query memory_tags to find memories matching filter
    2. If collection.tag_filter is None, fall back to current manual membership list
    3. Add `auto_update: bool` flag to collections to control behavior

- [ ] **BUG-436**: ContextLevelClassifier Has Overlapping Score Boosts
  - **Location:** `src/memory/classifier.py:116-151`
  - **Problem:** Classification applies category boost (line 121-128), then applies keyword boost (line 134-143), then applies code pattern boost (line 146-147). These can stack multiplicatively. E.g., a PREFERENCE category memory with "prefer" keyword gets +0.5 +0.2 = +0.7 boost, almost guaranteeing USER_PREFERENCE classification regardless of actual content.
  - **Impact:** Classifier is too easily biased by category hint; actual content analysis is overshadowed
  - **Fix:** Make boosts mutually exclusive or use weighted combination instead of additive stacking

- [ ] **BUG-437**: Call Graph BFS Doesn't Mark Starting Node as Visited
  - **Location:** `src/graph/call_graph.py:175-176, 229-230`
  - **Problem:** `_find_callers_bfs` and `_find_callees_bfs` initialize queue with `[(function_name, 0)]` but visited set is empty. The starting function is only added to visited when popped from queue (line 178/232 is inside the while loop). If starting function calls itself (recursion), it gets added to queue again before being marked visited.
  - **Example:** Function `factorial` calls itself → queue starts with `[('factorial', 0)]`, loop processes it, adds `factorial` to visited, but if it was already processed once, visited already has it. However, if self-recursion creates multiple queue entries before first pop, duplicates accumulate.
  - **Impact:** Potential duplicate processing, inefficiency for recursive functions
  - **Fix:** Add `visited.add(function_name)` before initializing queue, OR add to visited set in queue initialization: `visited = {function_name}`

- [ ] **BUG-438**: ContextLevelClassifier Has Overlapping Score Boosts
  - **Location:** `src/memory/classifier.py:116-151`
  - **Problem:** Classification applies category boost (line 121-128), then applies keyword boost (line 134-143), then applies code pattern boost (line 146-147). These can stack multiplicatively. E.g., a PREFERENCE category memory with "prefer" keyword gets +0.5 +0.2 = +0.7 boost, almost guaranteeing USER_PREFERENCE classification regardless of actual content.
  - **Impact:** Classifier is too easily biased by category hint; actual content analysis is overshadowed
  - **Fix:** Make boosts mutually exclusive or use weighted combination instead of additive stacking

- [ ] **BUG-439**: Call Graph BFS Doesn't Mark Starting Node as Visited
  - **Location:** `src/graph/call_graph.py:175-176, 229-230`
  - **Problem:** `_find_callers_bfs` and `_find_callees_bfs` initialize queue with `[(function_name, 0)]` but visited set is empty. The starting function is only added to visited when popped from queue (line 178/232 is inside the while loop). If starting function calls itself (recursion), it gets added to queue again before being marked visited.
  - **Example:** Function `factorial` calls itself → queue starts with `[('factorial', 0)]`, loop processes it, adds `factorial` to visited, but if it was already processed once, visited already has it. However, if self-recursion creates multiple queue entries before first pop, duplicates accumulate.
  - **Impact:** Potential duplicate processing, inefficiency for recursive functions
  - **Fix:** Add `visited.add(function_name)` before initializing queue, OR add to visited set in queue initialization: `visited = {function_name}`

- [ ] **BUG-440**: Export Doesn't Validate Embedding Dimension Match
  - **Location:** `src/backup/exporter.py:149-153`
  - **Problem:** When creating portable archive with embeddings, exports numpy array without validating all embeddings have same dimension (line 151). Mismatched dimensions (e.g., after model change) will cause import failures.
  - **Fix:** Validate all embeddings have same shape before np.savez_compressed; log warning and skip malformed embeddings

- [ ] **BUG-441**: Tag Confidence Score Formulas Are Arbitrary
  - **Location:** `src/tagging/auto_tagger.py:239`, `253`, `267`, `281`, `355`
  - **Problem:** Confidence formulas like `min(0.9, 0.5 + (matches * 0.1))` are hardcoded magic numbers with no justification. Why is language detection capped at 0.9 but frameworks at 0.95? Why linear scaling?
  - **Impact:** Confidence scores don't reflect actual accuracy; can't be tuned or calibrated
  - **Fix:**
    1. Move all confidence parameters to class __init__ or config
    2. Add calibration data/tests showing confidence correlates with precision
    3. Consider logistic regression on match counts instead of linear

- [ ] **BUG-442**: DependencyGraphGenerator Assumes graph.dependencies Dict Exists
  - **Location:** `src/memory/graph_generator.py:129, 154`
  - **Problem:** Lines 129 and 154 access `self.graph.dependencies` but DependencyGraph class (src/graph/dependency_graph.py) doesn't have this attribute. DependencyGraph uses `_adjacency_list` internally and exposes `nodes` and `edges` attributes. This causes AttributeError on every call.
  - **Example:** `filtered_nodes = set(self.graph.dependencies.keys())` → AttributeError: 'DependencyGraph' object has no attribute 'dependencies'
  - **Impact:** DependencyGraphGenerator completely broken, cannot generate any graphs
  - **Fix:** Refactor to use `self.graph.nodes.keys()` and `self.graph.edges` instead of non-existent dependencies/dependents dicts

- [ ] **BUG-443**: Tag Confidence Score Formulas Are Arbitrary
  - **Location:** `src/tagging/auto_tagger.py:239`, `253`, `267`, `281`, `355`
  - **Problem:** Confidence formulas like `min(0.9, 0.5 + (matches * 0.1))` are hardcoded magic numbers with no justification. Why is language detection capped at 0.9 but frameworks at 0.95? Why linear scaling?
  - **Impact:** Confidence scores don't reflect actual accuracy; can't be tuned or calibrated
  - **Fix:**
    1. Move all confidence parameters to class __init__ or config
    2. Add calibration data/tests showing confidence correlates with precision
    3. Consider logistic regression on match counts instead of linear

- [ ] **BUG-444**: DependencyGraphGenerator Assumes graph.dependencies Dict Exists
  - **Location:** `src/memory/graph_generator.py:129, 154`
  - **Problem:** Lines 129 and 154 access `self.graph.dependencies` but DependencyGraph class (src/graph/dependency_graph.py) doesn't have this attribute. DependencyGraph uses `_adjacency_list` internally and exposes `nodes` and `edges` attributes. This causes AttributeError on every call.
  - **Example:** `filtered_nodes = set(self.graph.dependencies.keys())` → AttributeError: 'DependencyGraph' object has no attribute 'dependencies'
  - **Impact:** DependencyGraphGenerator completely broken, cannot generate any graphs
  - **Fix:** Refactor to use `self.graph.nodes.keys()` and `self.graph.edges` instead of non-existent dependencies/dependents dicts

- [ ] **BUG-445**: Cycle Detection Produces Incorrect Cycles with Duplicate Nodes
  - **Location:** `src/graph/dependency_graph.py:163-167`
  - **Problem:** When back edge is detected, cycle construction is `cycle = path[cycle_start_idx:] + [neighbor]`. This duplicates the neighbor node (it's already at cycle_start_idx AND appended at end). For cycle A->B->C->A, this creates [A, B, C, A] which is correct, but the CircularDependency.length counts the duplicate (length=4 instead of 3 unique nodes). Additionally, the cycle marking logic at lines 178-181 expects the duplicate, but this makes cycle representation inconsistent.
  - **Example:** Path [A, B, C], neighbor=A, cycle_start_idx=0 → cycle = [A, B, C] + [A] = [A, B, C, A] (4 nodes for 3-node cycle)
  - **Impact:** Incorrect cycle statistics, confusing visualization (A appears twice), edge marking misses some circular edges
  - **Fix:** Either (1) Don't append duplicate: `cycle = path[cycle_start_idx:]` and update edge marking logic, OR (2) Document that cycles intentionally include start/end duplicate and update CircularDependency to expose both raw cycle and unique_nodes count

- [ ] **BUG-447**: Cycle Detection Produces Incorrect Cycles with Duplicate Nodes
  - **Location:** `src/graph/dependency_graph.py:163-167`
  - **Problem:** When back edge is detected, cycle construction is `cycle = path[cycle_start_idx:] + [neighbor]`. This duplicates the neighbor node (it's already at cycle_start_idx AND appended at end). For cycle A->B->C->A, this creates [A, B, C, A] which is correct, but the CircularDependency.length counts the duplicate (length=4 instead of 3 unique nodes). Additionally, the cycle marking logic at lines 178-181 expects the duplicate, but this makes cycle representation inconsistent.
  - **Example:** Path [A, B, C], neighbor=A, cycle_start_idx=0 → cycle = [A, B, C] + [A] = [A, B, C, A] (4 nodes for 3-node cycle)
  - **Impact:** Incorrect cycle statistics, confusing visualization (A appears twice), edge marking misses some circular edges
  - **Fix:** Either (1) Don't append duplicate: `cycle = path[cycle_start_idx:]` and update edge marking logic, OR (2) Document that cycles intentionally include start/end duplicate and update CircularDependency to expose both raw cycle and unique_nodes count

- [ ] **BUG-448**: DependencyGraphGenerator.generate Returns Tuple of Wrong Length
  - **Location:** `src/memory/graph_generator.py:118`
  - **Problem:** Function signature says `-> tuple[str, Dict[str, Any]]` (2 elements) but line 118 returns `return graph_data, stats, circular_groups` (3 elements). This causes unpacking errors for any caller expecting 2-tuple.
  - **Example:** `graph, stats = generator.generate()` will raise `ValueError: too many values to unpack (expected 2)`
  - **Impact:** Runtime error on every call to generate()
  - **Fix:** Update return type to `-> tuple[str, Dict[str, Any], List[List[str]]]` or change return to 2-tuple by embedding circular_groups in stats dict

- [ ] **BUG-450**: DependencyGraphGenerator.generate Returns Tuple of Wrong Length
  - **Location:** `src/memory/graph_generator.py:118`
  - **Problem:** Function signature says `-> tuple[str, Dict[str, Any]]` (2 elements) but line 118 returns `return graph_data, stats, circular_groups` (3 elements). This causes unpacking errors for any caller expecting 2-tuple.
  - **Example:** `graph, stats = generator.generate()` will raise `ValueError: too many values to unpack (expected 2)`
  - **Impact:** Runtime error on every call to generate()
  - **Fix:** Update return type to `-> tuple[str, Dict[str, Any], List[List[str]]]` or change return to 2-tuple by embedding circular_groups in stats dict

- [ ] **BUG-454**: Pending Updates Dict Accessed Without Full Lock Coverage
  - **Location:** `src/memory/usage_tracker.py:137-153`
  - **Code:**
    ```python
    async with self._lock:
        if memory_id in self._pending_updates:
            self._pending_updates[memory_id].update_usage(search_score)
        else:
            self._pending_updates[memory_id] = UsageStats(...)

- [ ] **BUG-455**: Float Division for Noise Ratio Without Zero Check
  - **Location:** `src/monitoring/metrics_collector.py:298`: `return float(stale) / float(total)`
  - **Problem:** No check if `total == 0` before division
  - **Impact:** ZeroDivisionError if no memories exist in database
  - **Fix:** Add guard in exception handler or before: `if total == 0: return 0.0`

- [ ] **BUG-080**: Comment Filtering in Line Count Is Too Aggressive
  - **Location:** `src/analysis/complexity_analyzer.py:141-151`
  - **Problem:** Line 148 filters out lines starting with `#, //, /*, *, """, '''` as comments. But this incorrectly excludes valid code: string literals starting with `"""` at line start, dictionary keys like `"#channel"`, and Python decorators like `@property` (the `*` pattern matches multiplication operators at line start after auto-formatting). This undercounts lines and underestimates complexity.
  - **Fix:** Only filter lines where the comment marker is the first non-whitespace character AND not inside a string. Use language-specific logic instead of one-size-fits-all.

- [ ] **BUG-082**: Export Detection Regex Can Match Inside String Literals
  - **Location:** `src/analysis/usage_analyzer.py:260-264`
  - **Problem:** Line 261 searches for `export\s+(function|class|const|let|var)\s+{name}\b` in full file content, which can match inside multi-line string literals or comments (e.g., documentation showing example code: `"Example: export function foo()"`). This incorrectly marks non-exported functions as exported.
  - **Fix:** Add negative lookbehind to exclude matches inside strings/comments, or use proper AST-based export detection instead of regex

- [ ] **BUG-091**: Stale Memory Count Logic Uses Hardcoded Access Threshold
  - **Location:** `src/memory/health_jobs.py:267`
  - **Problem:** The monthly cleanup job checks `if use_count > config.quality.stale_memory_usage_threshold` (line 267) to skip frequently accessed memories. However, this threshold is from ServerConfig.quality settings, which is intended for quality scoring, not lifecycle management. The comment at line 264 says "Check usage (skip if frequently accessed)" but doesn't explain what "frequently" means. If the config value is set too low (e.g., 1), all stale memories with any usage are kept forever.
  - **Fix:** Add dedicated `lifecycle.stale_deletion_min_access_count` config setting with clear documentation. Default to 5. Don't reuse quality threshold for deletion decisions.

- [ ] **BUG-107**: Archive Importer Doesn't Validate Manifest Archive Version
  - **Location:** `src/memory/archive_importer.py:105-111`
  - **Problem:** Loads manifest.json but never checks `archive_version` field for compatibility. Future breaking changes will cause silent import failures.
  - **Fix:** Add version compatibility check: `if manifest['archive_version'] not in SUPPORTED_VERSIONS: raise ValueError(...)`

- [ ] **BUG-322**: Undefined Variable PYTHON_PARSER_AVAILABLE Referenced But Never Defined
  - **Location:** `src/memory/incremental_indexer.py:188`
  - **Problem:** Line 188 checks `if not RUST_AVAILABLE and not PYTHON_PARSER_AVAILABLE` but PYTHON_PARSER_AVAILABLE is never imported or defined anywhere in the file. This will raise NameError if RUST_AVAILABLE is False. The Python parser fallback was intentionally removed (line 12 comment says it was broken), but the check wasn't updated.
  - **Fix:** Remove `and not PYTHON_PARSER_AVAILABLE` from line 188, change to `if not RUST_AVAILABLE: raise RuntimeError("Rust parser required...")`

- [ ] **BUG-331**: TODO Comment Indicates Missing Return Type Extraction
  - **Location:** `src/memory/incremental_indexer.py:1079`
  - **Problem:** Comment says `return_type=None, # TODO: Extract from signature if available`. This means call graph function nodes don't track return types, limiting the usefulness of call graph analysis for type checking or refactoring tools.
  - **Fix:** Implement return type extraction from signature string (regex for `-> ReturnType:`) or get from Rust parser if available

- [ ] **BUG-334**: Cyclomatic Complexity Double-Counts Ternary Operators
  - **Location:** `src/analysis/complexity_analyzer.py:89-139`
  - **Problem:** The pattern `r'\?.*:'` on line 111 matches ternary operators but also matches unrelated `?` characters in regex, comments, or strings (e.g., `"What is this?:"`). This inflates complexity scores incorrectly. Additionally, the regex `r'\?.*:'` is greedy and matches across multiple lines, potentially double-counting multiple ternaries as a single match.
  - **Fix:** Use non-greedy pattern `r'\?[^:]*:'` and add word boundaries. Better: only count `?` followed by `:` on same line with balanced parens.

- [ ] **BUG-335**: Cyclomatic Complexity Double-Counts Ternary Operators
  - **Location:** `src/analysis/complexity_analyzer.py:89-139`
  - **Problem:** The pattern `r'\?.*:'` on line 111 matches ternary operators but also matches unrelated `?` characters in regex, comments, or strings (e.g., `"What is this?:"`). This inflates complexity scores incorrectly. Additionally, the regex `r'\?.*:'` is greedy and matches across multiple lines, potentially double-counting multiple ternaries as a single match.
  - **Fix:** Use non-greedy pattern `r'\?[^:]*:'` and add word boundaries. Better: only count `?` followed by `:` on same line with balanced parens.

- [ ] **BUG-342**: Comment Filtering in Line Count Is Too Aggressive
  - **Location:** `src/analysis/complexity_analyzer.py:141-151`
  - **Problem:** Line 148 filters out lines starting with `#, //, /*, *, """, '''` as comments. But this incorrectly excludes valid code: string literals starting with `"""` at line start, dictionary keys like `"#channel"`, and Python decorators like `@property` (the `*` pattern matches multiplication operators at line start after auto-formatting). This undercounts lines and underestimates complexity.
  - **Fix:** Only filter lines where the comment marker is the first non-whitespace character AND not inside a string. Use language-specific logic instead of one-size-fits-all.

- [ ] **BUG-358**: Incomplete Logging in Health Scorer Exception Handler
  - **Location:** `src/memory/health_scorer.py:222-225`
  - **Problem:** Catches `Exception as e`, logs error, then has dead code `pass` after comment "Return empty distribution on error". The function continues to line 227 `return distribution` regardless. If exception happens, returns partially-filled distribution dict without any indication data is incomplete. Callers receive corrupted data. Missing `exc_info=True` makes debugging impossible.
  - **Fix:** Add `exc_info=True` to log, return empty dict immediately after logging (don't fall through to return statement), document that empty dict means error occurred.

- [ ] **BUG-360**: Incomplete Logging in Health Scorer Exception Handler
  - **Location:** `src/memory/health_scorer.py:222-225`
  - **Problem:** Catches `Exception as e`, logs error, then has dead code `pass` after comment "Return empty distribution on error". The function continues to line 227 `return distribution` regardless. If exception happens, returns partially-filled distribution dict without any indication data is incomplete. Callers receive corrupted data. Missing `exc_info=True` makes debugging impossible.
  - **Fix:** Add `exc_info=True` to log, return empty dict immediately after logging (don't fall through to return statement), document that empty dict means error occurred.

- [ ] **BUG-362**: Export Detection Regex Can Match Inside String Literals
  - **Location:** `src/analysis/usage_analyzer.py:260-264`
  - **Problem:** Line 261 searches for `export\s+(function|class|const|let|var)\s+{name}\b` in full file content, which can match inside multi-line string literals or comments (e.g., documentation showing example code: `"Example: export function foo()"`). This incorrectly marks non-exported functions as exported.
  - **Fix:** Add negative lookbehind to exclude matches inside strings/comments, or use proper AST-based export detection instead of regex

## Refactoring (REF-*)

- [ ] **REF-014**: Extract Qdrant-Specific Logic (~1-2 months) 🔥
  - **Current State:** Qdrant-specific code leaks into business logic
  - **Problem:** 2,328-line `qdrant_store.py` with complex Qdrant queries, tight coupling
  - **Impact:** Difficult to swap backends, test business logic, understand data flow
  - **Proposed Solution:** Repository pattern with clear domain models

- [ ] **REF-036**: Inconsistent Point ID Format Across Store Operations
  - **Location:** `src/store/qdrant_store.py:238-241` (delete uses list), vs `src/store/qdrant_store.py:2527` (uses PointIdsList)
  - **Problem:** Some operations use `points_selector=[memory_id]` (list) while others use `PointIdsList(points=[...])` for deletion
  - **Fix:** Standardize all deletion operations to use PointIdsList for consistency with Qdrant API best practices

- [ ] **REF-037**: Scroll Operations Fetch Too Much Data for Large Collections
  - **Location:** `src/store/qdrant_store.py:2619` fetches limit*10 (up to 1000 points) just to sort and return limit
  - **Problem:** Inefficient memory usage - fetches 10x more data than needed because Qdrant doesn't support sorting by payload fields
  - **Fix:** Document limitation and add warning comment; consider using external sorting service for large result sets

- [ ] **REF-038**: SQLite Direct Access in Qdrant Store Violates Separation of Concerns
  - **Location:** `src/store/qdrant_store.py:2557-2596`
  - **Problem:** `get_recent_activity()` directly opens SQLite feedback.db, mixing storage backends
  - **Fix:** Extract feedback database access to separate FeedbackService, inject as dependency

- [ ] **REF-039**: Duplicate Vector Retrieval in Git Commit Operations
  - **Location:** `src/store/qdrant_store.py:2945` and `src/store/qdrant_store.py:2965` both set `with_vectors=True`
  - **Problem:** Many operations retrieve vectors just to pass them through without using them
  - **Fix:** Only fetch vectors when actually needed (e.g., for similarity computation); add TODO comments documenting why vectors are needed

- [ ] **REF-040**: Inconsistent Datetime Timezone Handling
  - **Location:** `src/store/qdrant_store.py:1492-1496`, `src/store/qdrant_store.py:1500-1504` manually check and add timezone
  - **Problem:** Repetitive timezone-naive -> timezone-aware conversion code in 10+ locations
  - **Fix:** Extract to helper method `_ensure_utc_datetime(dt: Optional[datetime]) -> Optional[datetime]`

- [ ] **REF-042**: Type Hint Incompleteness in _build_payload
  - **Location:** `src/store/qdrant_store.py:1177-1249`
  - **Problem:** Returns `Tuple[str, Dict[str, Any]]` but Dict values are actually specific types (str, int, float, list, None)
  - **Fix:** Use TypedDict for payload structure to improve type safety

- [ ] **REF-052**: Duplicate Language Pattern Definitions Between Analyzers
  - **Location:** `src/analysis/complexity_analyzer.py:104-129`, `src/analysis/criticality_analyzer.py:173-198`, `src/analysis/usage_analyzer.py:217-230`
  - **Problem:** Each analyzer defines its own language-specific patterns dictionaries for keywords/operators. The JavaScript/TypeScript patterns are duplicated in complexity and criticality analyzers. If a new language is added or pattern is fixed (e.g., Rust match syntax), must update multiple files.
  - **Fix:** Extract to shared `src/analysis/language_patterns.py` module with pattern definitions for each language, imported by all analyzers

- [ ] **REF-054**: Hardcoded Entry Point Names Without Configurability
  - **Location:** `src/analysis/criticality_analyzer.py:94-97`, `src/analysis/usage_analyzer.py:306-307`
  - **Problem:** Both analyzers define `ENTRY_POINT_NAMES` sets with hardcoded values like "main", "index", "app". For projects with custom entry points (e.g., FastAPI with "application.py", Django with "wsgi.py"), these won't be detected as entry points, leading to incorrect criticality/usage scores.
  - **Fix:** Make entry point names configurable via ServerConfig: `criticality.entry_point_names = ["main", "index", ...]` with defaults, allow user override

- [ ] **REF-057**: Duplicate Emoji Constants in Capacity Recommendations
  - **Location:** `src/monitoring/capacity_planner.py:457-516`
  - **Problem:** The `_generate_capacity_recommendations()` method uses hardcoded emoji strings (🔴, ⚠️, 📈, ✅) inline in 8 different locations. If recommendations need to be rendered in a non-emoji-supporting terminal or UI, must change 8+ places. Also makes testing harder (must match exact emoji strings).
  - **Fix:** Define constants at module level: `EMOJI_CRITICAL = "🔴"`, `EMOJI_WARNING = "⚠️"`, etc. Or make emojis optional via config flag.

- [ ] **REF-078**: DOT Sanitization Removes Dots from Node IDs - Causes Collisions
  - **Location:** `src/graph/formatters/dot_formatter.py:167-168`
  - **Problem:** `_make_node_id()` replaces `.` with `_`, so `file.py` and `file_py` both become `file_py`, causing node ID collision. If graph has both `/src/test.py` and `/src/test_py`, they'll have the same DOT node ID, causing one to overwrite the other.
  - **Example:** Files `util.py` and `util_py` both → node ID `util_py`
  - **Impact:** Silent data loss in DOT export, missing nodes in visualization
  - **Fix:** Use unique separator or hash-based IDs: `node_id = hashlib.md5(file_path.encode()).hexdigest()[:8]` OR keep dots and use quoted node IDs

- [ ] **REF-103**: Store Layer Doesn't Validate Embedding Dimension Before Insert
  - **Location:** `src/store/qdrant_store.py:129-161` (store method)
  - **Problem:** If embedding dimension doesn't match collection config (384 vs 768), Qdrant rejects insert but error is cryptic
  - **Fix:** Add dimension validation before insert: `if len(embedding) != self.embedding_dim: raise ValidationError(...)`

- [ ] **REF-105**: Duplicate Detection in Store Layer Silently Catches Exceptions
  - **Location:** `src/store/qdrant_store.py:2594` (inferred from grep results)
  - **Problem:** Exception during payload parsing in deduplication loop is caught and logged but that memory is skipped without user notification
  - **Fix:** Collect failed memory IDs and include in response: `"warnings": ["Failed to process memories: {ids}"]`

- [ ] **REF-107**: Session Dictionary Grows Unbounded Without Lock
  - **Location:** `src/memory/conversation_tracker.py:141,173,254`
  - **Problem:** Sessions dict modified in start_session, end_session, _cleanup_expired_sessions without any lock. While individual dict operations are atomic in CPython, the dict can grow unbounded if cleanup fails or is too slow.
  - **Impact:** Memory leak if sessions accumulate faster than cleanup
  - **Fix:** Add lock protecting sessions dict, add max_sessions limit with LRU eviction

- [ ] **REF-239**: Inconsistent Lock Usage Across Services
  - **Location:** Connection pool uses both `asyncio.Lock` (self._lock) and `threading.Lock` (self._counter_lock)
  - **Files:** `src/store/connection_pool.py:131,132,230,299,363,526,569` (asyncio.Lock), line 300,364,527 (threading.Lock)
  - **Pattern:** Async lock protects structural changes (pool state), thread lock protects counters (stats)
  - **Problem:** Mixing lock types is correct BUT confusing. Why use threading.Lock for stats when all code is async? Thread lock only needed if stats accessed from sync context.
  - **Impact:** Cognitive overhead, potential deadlock if future code calls from sync context
  - **Fix:** Document the rationale in comments, or use asyncio.Lock exclusively if no sync access needed

- [ ] **REF-243**: Lock Acquisition Without Timeout in Connection Pool
  - **Location:** `src/store/connection_pool.py:230` (`async with self._lock`)
  - **Problem:** Acquiring `_lock` has no timeout; if lock holder deadlocks, all future acquisitions hang forever
  - **Impact:** Under rare race conditions, entire connection pool can freeze
  - **Fix:** Use `asyncio.timeout(10.0)` wrapper around lock acquisition; raise ConnectionPoolExhaustedError on timeout

- [ ] **REF-244**: No Deadlock Prevention Strategy Visible
  - **Location:** Multiple services/managers acquire locks in different orders
  - **Examples:**
    - `WorkspaceManager` modifies workspaces, calls `RepositoryRegistry.remove_from_workspace`
    - `RepositoryRegistry.unregister` iterates repositories, modifies other_repo.depends_on
    - No documented lock ordering invariant (e.g., "always acquire workspace lock before repo lock")
  - **Problem:** Without consistent lock ordering, future code changes could introduce ABBA deadlock (Thread 1: lock A then B, Thread 2: lock B then A)
  - **Impact:** Deadlock risk increases as codebase grows
  - **Fix:** Document lock hierarchy in ARCHITECTURE.md, enforce ordering via lint rules or runtime checks

- [ ] **REF-245**: MemoryStore.update() Doesn't Document new_embedding Parameter Behavior
  - **Location:** `src/store/base.py:152-166`, `src/store/qdrant_store.py:621-637`
  - **Problem:** Abstract method docstring says "Update a memory's metadata" but doesn't mention embedding updates. Implementation accepts `new_embedding` but base class docs don't specify when/how to use it.
  - **Impact:** LOW - Documentation mismatch, unclear contract
  - **Fix:** Update base.py docstring to document new_embedding parameter: "Args: new_embedding: Optional new embedding vector (e.g., when content changes)"

- [ ] **REF-247**: Max Score Calculation Assumes Non-Empty List
  - **Location:** `src/services/code_indexing_service.py:140`: `max_score = max(scores)`
  - **Problem:** `max()` on empty sequence raises ValueError
  - **Impact:** Crash if results list is empty (though line 139 creates scores from results, so this implies results is non-empty, but not explicit)
  - **Fix:** Add assertion or guard: `if not scores: return {"quality": "poor", ...}`

- [ ] **REF-249**: Conversation Tracker Cleanup Iterator Pattern Unsafe
  - **Location:** `src/memory/conversation_tracker.py:252-260`
  - **Code:**
    ```python
    expired_sessions = [
        session_id
        for session_id, session in self.sessions.items()  # Iteration
        if session.is_expired(...)
    ]
    for session_id in expired_sessions:
        self.end_session(session_id)  # Deletes from self.sessions
    ```
  - **Problem:** Creates list snapshot (good!), but if concurrent request calls end_session() during cleanup loop, session already deleted, end_session returns False (harmless but inefficient).
  - **Impact:** Minor inefficiency, no data corruption
  - **Fix:** Add lock protection or use try/except to ignore already-deleted sessions

- [ ] **REF-258**: Missing Documentation on Resource Cleanup Order
  - **Location:** `src/core/server.py:5591-5623`
  - **Problem:** Cleanup order matters (e.g., stop schedulers before closing stores), but no comments explain why
  - **Impact:** Future refactoring could reorder cleanup and cause hangs/errors
  - **Fix:** Add comments explaining dependency order: "Stop background tasks -> Wait for pending ops -> Close connections -> Close executors"

- [ ] **REF-259**: Task Cancellation Leaves Partial State
  - **Location:** `src/memory/background_indexer.py:141-155` (pause_job)
  - **Code:**
    ```python
    self._cancel_events[job_id].set()  # Signal cancellation
    self.job_manager.update_job_status(job_id, JobStatus.PAUSED)  # Update DB
    if job_id in self._active_tasks:
        await asyncio.wait_for(self._active_tasks[job_id], timeout=5.0)  # Wait for task
    ```
  - **Problem:** If task doesn't respect cancellation event, timeout fires, but job is marked PAUSED even though task still running. Subsequent resume could start duplicate task.
  - **Impact:** Duplicate indexing jobs, resource waste, data corruption
  - **Fix:** After timeout, force cancel task.cancel(), verify task.done(), update status to FAILED if timeout

- [ ] **REF-263**: No Centralized Resource Registry
  - **Location:** Resources scattered across server.py, with manual tracking
  - **Problem:** Easy to forget to close a new resource added to initialization
  - **Impact:** New features may leak resources if developer forgets to add cleanup
  - **Fix:** Consider resource manager pattern: register all resources on creation, automatic cleanup in reverse order

- [ ] **REF-264**: No Starvation Prevention for Locks
  - **Location:** All asyncio.Lock usage lacks fairness guarantees
  - **Problem:** Python's asyncio.Lock is unfair - waiting coroutines are not guaranteed FIFO ordering. Long-running critical sections could starve waiting tasks.
  - **Impact:** Potential starvation under high concurrency
  - **Fix:** If starvation observed, use queue-based fair lock or limit critical section duration

- [ ] **REF-268**: No Protection Against asyncio.create_task Orphaning
  - **Location:** Multiple locations create tasks without tracking
  - **Examples:**
    - `src/memory/usage_tracker.py:151` - Creates flush task but doesn't await or track for cleanup
    - `src/store/connection_pool_monitor.py:135` - Monitor task stored but no graceful shutdown check
  - **Problem:** Tasks created with create_task() keep running until complete. If parent object destroyed, tasks become orphaned, keep running in background, potentially access destroyed resources.
  - **Impact:** Resource leaks, undefined behavior on shutdown
  - **Fix:** Store all tasks in instance variable, await all tasks in cleanup/shutdown method

- [ ] **REF-269**: SearchFilters.to_dict() May Return None Values - Breaking Qdrant Filters
  - **Location:** `src/core/models.py` (SearchFilters), `src/store/qdrant_store.py:2697-2800` (filter building)
  - **Problem:** SearchFilters has many Optional fields that default to None. When converted to dict, None values are included. Qdrant filter builder does `if filters.category:` checks but if filters are passed as dict (e.g., in list_memories), None values could cause issues.
  - **Impact:** LOW - Potential filter building errors
  - **Fix:** Add `to_dict(exclude_none=True)` method or filter None values in store layer

- [ ] **REF-271**: Inconsistent State Management - Server Stats Not Thread-Safe
  - **Location:** `src/core/server.py:127-157` (stats dict), accessed in 62+ methods
  - **Problem:** Direct mutations `self.stats["key"] += 1` across async methods without locking
  - **Impact:** Race conditions in concurrent operations cause lost stat updates, incorrect metrics
  - **Fix:** Already tracked as UX-050 (completed per TODO.md line 199), verify implementation or reopen
  - **Note:** This may be a duplicate finding - verify UX-050 fix actually deployed

- [ ] **REF-274**: God Class Still Large After REF-016 Extraction
  - **Location:** `src/core/server.py` (5,620 lines, 80+ methods)
  - **Problem:** Despite service layer extraction, MemoryRAGServer still acts as facade with 80+ public methods
  - **Impact:** High cognitive load, difficult testing, unclear separation of concerns
  - **Analysis:** REF-016 extracted services but kept all methods as delegation points
  - **Fix:** Consider second-phase refactoring:
    1. Move MCP tool adapter methods to separate `MCPToolAdapter` class
    2. Make services the primary API, not the server class
    3. Reduce MemoryRAGServer to initialization and lifecycle only

- [ ] **REF-277**: Duplicate Code Between server.py and services/
  - **Location:** `src/core/server.py` method bodies vs `src/services/*.py`
  - **Problem:** Many server methods duplicate validation and error handling already in services
  - **Impact:** Maintenance burden - same logic updated in 2+ places, risk of divergence
  - **Fix:** Remove redundant validation from server methods, trust service layer contracts

- [ ] **REF-280**: MCP Response Formatting Scattered Across 40+ Handlers
  - **Location:** `src/mcp_server.py:842-1541` (call_tool function body)
  - **Problem:** Each of 40+ tool handlers contains custom response formatting logic
  - **Impact:** Inconsistent response structures, difficult to enforce MCP protocol compliance
  - **Fix:** Extract response formatters to separate module:
    - `MCPResponseFormatter` class with typed methods per tool category
    - Standard error response format
    - Centralized TextContent creation

- [ ] **REF-283**: Inconsistent Error Handling Between Tool Handlers
  - **Location:** `src/mcp_server.py` - varies by handler
  - **Problem:** Some handlers catch specific exceptions, others use bare `Exception`, inconsistent logging
  - **Examples:**
    - Lines 2851-2873: Detailed error handling with actionable messages
    - Lines 1546-1548: Generic try-catch with minimal context
  - **Impact:** Debugging difficulty, inconsistent user experience
  - **Fix:** Standardize error handling pattern across all handlers

- [ ] **REF-304**: Hardcoded Score Ranges Duplicated Across Analyzers
  - **Location:** `src/analysis/complexity_analyzer.py:36-43`, `src/analysis/usage_analyzer.py:85-90`, `src/analysis/criticality_analyzer.py:70-71`
  - **Problem:** Each analyzer defines its own MIN/MAX score ranges (0.3-0.7, 0.0-0.2, 0.0-0.3) as class constants. These ranges are tightly coupled to the importance scorer's normalization logic (line 244-250 in importance_scorer.py). If we want to adjust score ranges, must update 4 files consistently. Magic numbers antipattern.
  - **Fix:** Define score range constants in a shared `src/analysis/constants.py` module. Use named constants like `COMPLEXITY_SCORE_RANGE = (0.3, 0.7)` and import in all analyzers.

- [ ] **REF-310**: Generic Exception Re-wrapping Loses Specific Error Types
  - **Location:** `src/core/server.py:2864-2873`, and similar in multiple store operations
  - **Problem:** Pattern `except Exception as e: raise RetrievalError(...)` catches specific exceptions (ConnectionError, ValidationError) and re-wraps as generic error. Original exception type information is lost. Callers can't implement error-specific handling (e.g., retry on connection errors but not validation errors).
  - **Fix:** Preserve original exception in chain: `raise RetrievalError(...) from e` (already done in most places, missing in ~10 locations). Better: catch specific exception types separately and re-raise with appropriate custom exception.

- [ ] **REF-318**: Duplicate Error Message Construction in Exception Handlers
  - **Location:** `src/core/server.py:2860-2873` constructs multi-line error messages, repeated in 5+ locations
  - **Problem:** Error message templates like "Solution: Run 'docker-compose up -d'..." are duplicated across exception handlers. If we change Qdrant setup instructions, must update 10+ locations. Error message inconsistency between similar operations.
  - **Fix:** Extract error messages to constants or use custom exception classes with built-in messages (QdrantConnectionError already does this). Create ErrorMessages enum for common failure scenarios.

- [ ] **REF-332**: DashboardServer Event Loop Thread Lifecycle Issues
  - **Location:** `src/dashboard/web_server.py:88-99, 149-159`
  - **Problem:** `start()` creates daemon thread with event loop (line 93-98), but `stop()` attempts to stop loop with `loop.call_soon_threadsafe(loop.stop)` (line 151) without joining thread or ensuring clean shutdown. Daemon threads are killed on process exit, which can corrupt state or leave resources open.
  - **Fix:** Make thread non-daemon, add `self.loop_thread.join(timeout=5)` in stop(), handle timeout case

- [ ] **REF-352**: NotificationManager.backends List Modified via append Without Lock
  - **Location:** `src/memory/notification_manager.py:346`
  - **Problem:** `add_backend()` directly appends to `self.backends` list without lock. If multiple threads call add_backend concurrently, list corruption possible (though unlikely in typical usage since this is usually called during initialization).
  - **Fix:** Add `self._backends_lock = threading.Lock()` to protect list modifications, or document that add_backend() must only be called during initialization

- [ ] **REF-372**: Tag Deletion Doesn't Clean Up Empty Parent Tags
  - **Location:** `src/tagging/tag_manager.py:267-305`
  - **Problem:** When deleting a tag with `cascade=True`, all descendants are deleted, but if this leaves parent tags with no children and no direct memory associations, those parent tags remain as orphaned hierarchy nodes.
  - **Impact:** Tag hierarchy accumulates dead branches over time
  - **Fix:** After cascade delete, walk up parent chain and delete any ancestors with no children and no memory associations

- [ ] **REF-398**: MCP Tool Schemas Not Validated Against Implementation Signatures
  - **Location:** `src/core/tools.py` (MCP tool definitions would be in server.py or tools registry)
  - **Problem:** No automated validation that MCP tool JSON schemas match actual Python method signatures. Schema drift could cause runtime errors when tools are called.
  - **Impact:** LOW - Manual verification required, risk of schema/code mismatch over time
  - **Fix:** Add CI test that validates tool schemas against service method signatures using inspect module

- [ ] **REF-043**: Inconsistent Error Logging Between Sync and Async Cache Methods
  - **Location:** `src/embeddings/cache.py:193-197, 240`
  - **Problem:** Sync methods (`_get_sync`, `_set_sync`) log errors with full details, but timeout handlers log minimal context
  - **Impact:** Debugging timeout issues harder than other cache errors
  - **Fix:** Standardize error logging to include operation type, text hash, and model name

- [ ] **REF-044**: Hardcoded Timeout Values in Cache Operations
  - **Location:** `src/embeddings/cache.py:128, 213, 291, 392, 472`
  - **Problem:** All async cache operations use hardcoded `asyncio.timeout(30.0)` - not configurable
  - **Impact:** Cannot tune timeouts for slow storage or fast SSDs
  - **Fix:** Add `cache_operation_timeout_seconds` to ServerConfig.performance

- [ ] **REF-050**: Date Validation Returns Original String After Normalizing Different Value
  - **Location:** `src/search/query_dsl_parser.py:255, 260`
  - **Problem:** Validates `normalized` (with 'Z' replaced by '+00:00') but returns original `date_str` (with 'Z'), potentially confusing downstream consumers
  - **Fix:** Return normalized string consistently or document that original format is preserved

- [ ] **REF-056**: Missing Input Validation in Alert Snooze Duration
  - **Location:** `src/monitoring/alert_engine.py:469-493`
  - **Problem:** The `snooze_alert()` method accepts `hours` parameter with no validation. Caller can pass `hours=-10` (snooze in the past, meaningless), `hours=0` (immediate un-snooze), or `hours=1000000` (snooze for 114 years). Negative or extreme values create confusing behavior - snoozed alerts might reappear immediately or never.
  - **Fix:** Add validation: `if not (0 < hours <= 168): raise ValueError("Snooze duration must be 1-168 hours (1 week max)")`. Document reasonable range.

- [ ] **REF-062**: No Validation That project_name Pattern Matches Actual Usage
  - **Location:** `src/core/allowed_fields.py:52` defines pattern `r"^[a-zA-Z0-9_\-\.]+$"`, but `src/core/validation.py:483` uses same pattern
  - **Problem:** The project_name pattern is duplicated between allowed_fields.py and validation.py. If one is updated but not the other, validation becomes inconsistent. Regex patterns should be defined once and imported.
  - **Fix:** Define `PROJECT_NAME_PATTERN = r"^[a-zA-Z0-9_\-\.]+$"` in a constants module, import in both files

- [ ] **REF-073**: No Bulk Tag Operations
  - **Location:** `src/tagging/tag_manager.py:355-390` (tag_memory is single-item only)
  - **Problem:** Tagging memories one-by-one in loops (see `auto_tag_command.py:89-94`) is inefficient. Each call is a separate DB transaction.
  - **Impact:** Auto-tagging 1000 memories = 1000+ DB commits; slow and high DB contention
  - **Fix:** Add `tag_memories_bulk(associations: List[Tuple[memory_id, tag_id, confidence]])` with single transaction

- [ ] **REF-084**: DependencyGraph Doesn't Validate Node Existence on add_edge
  - **Location:** `src/graph/dependency_graph.py:117-120`
  - **Problem:** `add_edge()` ensures nodes exist in `_adjacency_list` but doesn't check if they exist in `self.nodes` dict. Can create edges between nodes that were never added via `add_node()`, resulting in incomplete metadata.
  - **Impact:** Graph can have edges to phantom nodes without language/metadata
  - **Fix:** Add validation: `if edge.source not in self.nodes: logger.warning(f"Adding edge from unknown node {edge.source}")` OR require nodes to exist

- [ ] **REF-085**: Call Graph BFS Max Depth Check Uses >= Instead of >
  - **Location:** `src/graph/call_graph.py:180, 234`
  - **Problem:** Lines 180 and 234 check `if depth >= max_depth: continue`, which means a node at exactly max_depth is skipped. Combined with the starting depth of 0, this gives max_depth=1 → only direct neighbors (depth 1), not transitive at depth 2. Docstring says "max_depth: Maximum depth" which is ambiguous about inclusive/exclusive.
  - **Impact:** Off-by-one in transitive caller/callee search
  - **Fix:** Change to `if depth > max_depth:` OR clarify docstring as "exclusive depth limit"

- [ ] **REF-101**: Error Code Gaps and Overlaps in Exception Hierarchy
  - **Location:** `src/core/exceptions.py:1-239`
  - **Problem:** Error codes E000-E015 are defined but not systematically assigned across all exception types; StorageError/RetrievalError have same base code E001/E004
  - **Fix:** Create error code registry with ranges: E001-E050 (Storage), E051-E100 (Retrieval), E101-E150 (Validation), E151-E200 (Embedding), etc.

- [ ] **REF-104**: Missing Timeout Context in All Storage Operations
  - **Location:** All `async with asyncio.timeout(30.0):` blocks (30+ locations)
  - **Problem:** Hardcoded 30s timeout with no indication to user of what operation timed out or how to increase timeout
  - **Fix:** Add timeout to config, include operation name in timeout error: `except TimeoutError: raise StorageError(f"{operation} timed out after {timeout}s", solution="Increase config.timeout_seconds")`

- [ ] **REF-108**: No Timeout on Asyncio.gather() in Concurrent Operations
  - **Location:** Suggested for `src/services/cross_project_service.py:124-159`
  - **Problem:** Future concurrent implementation (per PERF-001) would use `asyncio.gather(*tasks)` without timeout. If one project search hangs, entire cross-project search hangs forever.
  - **Impact:** Availability risk from slow dependencies
  - **Fix:** Wrap in `asyncio.wait_for(asyncio.gather(...), timeout=30.0)` or use `asyncio.wait()` with timeout

- [ ] **REF-109**: Service Methods Mix Business Logic with I/O - Hard to Test
  - **Location:** All service classes in `src/services/`
  - **Problem:** Methods like `memory_service.store_memory()` combine validation, embedding generation, storage, and stats updates in one method. Hard to test individual pieces, hard to mock I/O.
  - **Impact:** LOW - Testing difficulty, maintainability
  - **Fix:** Extract pure business logic into separate methods, use composition over long methods

---

- [ ] **REF-252**: Off-by-One Risk in Line Offset Calculation
  - **Location:** `src/search/pattern_matcher.py:169`: `line_offsets.append(line_offsets[-1] + len(line) + 1)`
  - **Problem:** Assumes last line has newline (`+1`), but last line in file may not. This could cause line number to be off by one for matches on last line.
  - **Impact:** Incorrect line numbers for pattern matches on last line of files without trailing newline
  - **Fix:** Check if line is last: `newline_len = 1 if i < len(lines) - 1 else 0; line_offsets.append(line_offsets[-1] + len(line) + newline_len)`

- [ ] **REF-262**: Large Integer Risk in Timestamp Conversion
  - **Location:** Datetime to Unix timestamp conversions throughout
  - **Problem:** Year 2038 problem (32-bit signed int overflow) not addressed. Python handles this, but Qdrant or SQLite might not.
  - **Impact:** Dates after 2038-01-19 could overflow in 32-bit systems
  - **Fix:** Document that system requires 64-bit integers for timestamps, or add validation rejecting dates after 2037

- [ ] **REF-290**: Missing Validation for RRF K Parameter
  - **Location:** `src/search/hybrid_search.py:48-62`
  - **Problem:** `rrf_k` parameter is used in division (line 258, 261) but never validated to be positive; zero or negative values would cause errors
  - **Fix:** Add validation in `__init__`: `if rrf_k <= 0: raise ValueError("rrf_k must be positive")`

- [ ] **REF-294**: Hardcoded Diversity Similarity Threshold
  - **Location:** `src/search/reranker.py:302`
  - **Problem:** Diversity penalty threshold `0.8` is hardcoded with no configuration option; too high for some use cases, too low for others
  - **Fix:** Add `diversity_similarity_threshold` parameter to `ResultReranker.__init__` with default 0.8

- [ ] **REF-297**: Hardcoded Git Subprocess Timeout Duplicated 6 Times
  - **Location:** `src/memory/git_detector.py:35`, `src/memory/git_detector.py:61`, `src/memory/git_detector.py:110`, `src/memory/git_detector.py:127`, `src/memory/git_detector.py:144`, `src/memory/git_detector.py:161`
  - **Problem:** The value `timeout=5` appears 6 times in subprocess.run() calls. If we need to tune git timeout (e.g., for slow filesystems), must change 6 locations. Magic number antipattern.
  - **Fix:** Define `GIT_SUBPROCESS_TIMEOUT = 5.0` as module constant at top of file, use in all subprocess calls

- [ ] **REF-306**: Inconsistent Exception Logging Patterns Across Services
  - **Location:** `src/services/*.py` - mix of `exc_info=True` and no exc_info
  - **Problem:** Services have inconsistent exception logging. Some use `exc_info=True` (memory_service.py:335-339), others don't (analytics_service.py:163-164). Code reviewer or new developer can't tell which is intentional. Grep shows ~80% of exception logs have exc_info=True (from UX-049 fix), but remaining 20% may be bugs or intentional.
  - **Fix:** Document exception logging policy in CONTRIBUTING.md: always use exc_info=True for unexpected exceptions, omit for expected validation errors. Add linting rule to enforce.

- [ ] **REF-314**: Missing Docstring Raises Sections for 90% of Functions
  - **Location:** Entire codebase - functions raise custom exceptions but don't document in docstring
  - **Problem:** Only ~10% of functions document raised exceptions in docstring Raises section. Functions like `store()` raise ValidationError, StorageError, ReadOnlyError but docstring doesn't list them (src/services/memory_service.py:241-340). Callers don't know what exceptions to catch.
  - **Fix:** Add Raises section to all public API docstrings. Use ruff/pydocstyle to enforce. Example template in CONTRIBUTING.md.

- [ ] **REF-324**: No Validation for Cron Expression Format in pruning_schedule
  - **Location:** `src/config.py:131`
  - **Problem:** `pruning_schedule: str = "0 2 * * *"` accepts any string value. If user enters invalid cron syntax ("2am daily", "*/5 * *", "garbage"), it will only fail at runtime when the scheduler tries to parse it. No validation happens during config load.
  - **Fix:** Add field validator that uses `croniter` or cron regex to validate syntax: `@field_validator('pruning_schedule')` that raises ValueError on invalid cron format.

- [ ] **REF-329**: Inconsistent Validation Location - Some in Field Validators, Some in Model Validators
  - **Location:** Throughout `src/config.py`
  - **Problem:** Some validation is done in `@field_validator` decorators (e.g., `parallel_workers` line 49, `gpu_memory_fraction` line 57), while other identical validation is done in the massive `validate_config()` model_validator (e.g., `embedding_batch_size` line 510-513, `embedding_cache_ttl_days` line 521-524). This inconsistency makes it hard to find where validation happens.
  - **Fix:** Move all single-field range checks to `@field_validator` decorators. Keep only interdependency checks in model_validator. This improves error locality and makes validation discoverable.

- [ ] **REF-337**: ConnectionHealthChecker Run in Executor Without Timeout
  - **Location:** `src/store/connection_health_checker.py:170-173, 200-203, 234-237, 245-248`
  - **Problem:** All health checks use `await loop.run_in_executor(None, ...)` to run sync QdrantClient operations. The executor is `None` (ThreadPoolExecutor), but there's no outer timeout on the executor call itself - only on the `asyncio.wait_for()` wrapper. If the executor's thread pool is exhausted, the task could hang indefinitely.
  - **Fix:** Add max_workers limit to default executor or use bounded ThreadPoolExecutor

- [ ] **REF-339**: Magic Number 50000 for Content Max Length Not Centralized
  - **Location:** `src/core/allowed_fields.py:24` and `src/core/validation.py:259`
  - **Problem:** The value 50000 (max content length in chars) appears in allowed_fields as a constraint and is hardcoded in validation.py as the default max_bytes (51200 = ~50KB). These should be linked or use a shared constant.
  - **Fix:** Define `MAX_CONTENT_CHARS = 50000` and `MAX_CONTENT_BYTES = 51200` as module constants in a shared location

- [ ] **REF-344**: Validation Error Messages Don't Include Current Value for All Fields
  - **Location:** Throughout `src/config.py` validation
  - **Problem:** Some validators include current value in error message (e.g., line 513 `"embedding_batch_size must not exceed 256 (memory constraint)"`), but don't show what value was provided. Compare to line 64 which shows `(got {v})`. Inconsistent error message quality.
  - **Fix:** Standardize all validation errors to include `(got {value})` for debugging

- [ ] **REF-366**: Tag Hierarchy Depth Validation Happens Too Late
  - **Location:** `src/tagging/tag_manager.py:96-97`
  - **Problem:** Hierarchy depth check happens after parent lookup and path construction. If validation fails, DB was queried unnecessarily. Also, error message says "4 levels" but check is `>= 3`, which allows levels 0-3 (actually 4 levels total) - confusing.
  - **Fix:**
    1. Check parent's level immediately: `if parent_tag and parent_tag.level >= 3: raise ValidationError`
    2. Clarify error message: "Tag hierarchy limited to 4 levels (0-3)"
    3. Add constant: `MAX_TAG_DEPTH = 3`

- [ ] **REF-008**: Remove deprecated API usage
  - Update to latest Qdrant APIs
  - Update to latest MCP SDK

- [ ] **REF-012**: Implement rollback support for bulk operations

- [ ] **REF-045**: Worker Model Loading Error Messages Lost to Main Process
  - **Location:** `src/embeddings/parallel_generator.py:106-107`
  - **Problem:** Worker process logs model loading errors with `exc_info=True`, but logs may not propagate to main process
  - **Impact:** Model loading failures in workers hard to debug - user only sees generic "embedding generation failed"
  - **Fix:** Serialize exception details in raised `EmbeddingError` message

- [ ] **REF-046**: Diversity Signature Uses Only First 100 Characters
  - **Location:** `src/search/reranker.py:296`
  - **Problem:** For code, first 100 chars might miss important differences in function bodies (e.g., similar imports/signatures)
  - **Fix:** Make signature length configurable or use content hash for better diversity detection

- [ ] **REF-047**: Pattern Matcher Long Lines Regex Won't Match (Missing DOTALL)
  - **Location:** `src/search/pattern_matcher.py:39`
  - **Problem:** Pattern `^.{120,}$` with MULTILINE expects `.` to match newlines, but default `.` doesn't match `\n` (needs DOTALL flag at line 98)
  - **Fix:** Either use DOTALL flag or change pattern to `^[^\n]{120,}$`

- [ ] **REF-048**: Duplicate Synonym Entry for "exception"/"exceptions"
  - **Location:** `src/search/query_synonyms.py:66-67`
  - **Problem:** Both "exception" and "exceptions" have separate entries with similar synonyms; maintenance burden
  - **Fix:** Use stemming or normalize plurals before lookup to consolidate entries

- [ ] **REF-051**: Python Call Extractor Doesn't Reset State Between Calls
  - **Location:** `src/analysis/call_extractors.py:59-61`, `src/analysis/call_extractors.py:78-80`
  - **Problem:** The `extract_calls()` method sets `self.current_class = None` and `self.current_function = None` at the start (lines 78-80), but these are instance variables that could leak state if an exception is raised mid-extraction. If parsing fails after setting `current_class = "Foo"`, the next call to `extract_calls()` for a different file will still have `current_class = "Foo"` in context.
  - **Fix:** Use local variables instead of instance variables for tracking context within a single file parse, or use a context manager to ensure cleanup

- [ ] **REF-053**: Missing Type Hints for Return Values in Call Extractors
  - **Location:** `src/analysis/call_extractors.py:310-325`, `src/analysis/call_extractors.py:379-393`
  - **Problem:** Helper methods like `_extract_function_name()`, `_extract_callee_name()`, and `_extract_method_name()` return `Optional[str]` but the return statements don't use explicit None returns in all paths. Lines 324, 392 have bare `pass` in except blocks, then implicitly return None. This makes it unclear whether None is intentional or a bug.
  - **Fix:** Add explicit `return None` in all exception handlers and document when/why None is returned

- [ ] **REF-055**: Hardcoded Health Status Thresholds Duplicated Across Files
  - **Location:** `src/monitoring/health_reporter.py:293-304`, `src/monitoring/capacity_planner.py:108-117`, `src/memory/health_scorer.py:126-133`
  - **Problem:** Three different files define their own health status thresholds (EXCELLENT >= 90, GOOD >= 75, etc.). While the values are currently identical, they're hardcoded magic numbers in each file. If we need to adjust thresholds (e.g., make "GOOD" >= 70 instead of 75), must change 3+ files. This creates inconsistency risk where different components report different health statuses for the same score.
  - **Fix:** Extract to shared constants in `src/monitoring/constants.py`: `HEALTH_STATUS_THRESHOLDS = {"EXCELLENT": 90, "GOOD": 75, "FAIR": 60, "POOR": 40}`. Import in all files.

- [ ] **REF-058**: Job History Unbounded Growth in Health Jobs
  - **Location:** `src/memory/health_jobs.py:83-84`, `src/memory/health_jobs.py:195`, `src/memory/health_jobs.py:306`, `src/memory/health_jobs.py:369`
  - **Problem:** The `HealthMaintenanceJobs` class appends every job result to `self.job_history` list (lines 195, 306, 369) with no size limit. If jobs run every week for a year, that's 52 * 3 = 156 entries minimum. If jobs run daily (via manual trigger), that's 1000+ entries. The list grows unbounded and is never cleared except manually via `clear_job_history()` (line 404). In contrast, HealthJobScheduler limits history to last 100 entries (line 164).
  - **Fix:** Add automatic trimming in job methods: `self.job_history.append(result); if len(self.job_history) > 100: self.job_history = self.job_history[-100:]`

- [ ] **REF-060**: Inconsistent Dry-Run Behavior Across Remediation Actions
  - **Location:** `src/monitoring/remediation.py:230-254`, `src/monitoring/remediation.py:256-285`
  - **Problem:** The `_dry_run_action()` method handles dry-run for `prune_stale_memories` and `cleanup_old_sessions` specially (lines 235-248), but for all other actions returns `RemediationResult(success=True, items_affected=0, details={"action": "dry_run", "note": "count not available"})` (line 250-254). This means dry-run for `archive_inactive_projects`, `merge_duplicates`, and `optimize_database` doesn't provide useful information - it just says "would run" with no impact estimate. Users can't make informed decisions.
  - **Fix:** Implement proper dry-run for all actions. `optimize_database` could report current DB size, `archive_inactive_projects` could count inactive projects, etc.

- [ ] **REF-061**: Database Optimization Uses Blocking Operations
  - **Location:** `src/monitoring/remediation.py:367-387`
  - **Problem:** The `_optimize_database()` method runs `VACUUM` (line 372) and `ANALYZE` (line 375) on SQLite database. Both are blocking operations that can take 10+ seconds on large databases (1GB+). The entire remediation engine (and any other code using the same database connection) is blocked during this time. If called during a busy period, this causes user-visible latency spikes.
  - **Fix:** Add warning log before optimization: `logger.warning("Starting database optimization - may block for 10+ seconds")`. Consider running VACUUM in a separate transaction or thread. Document that this should only run during maintenance windows.

- [ ] **REF-063**: Duplicate Checksum Calculation Code
  - **Location:** `src/backup/exporter.py:523-537` and `src/backup/importer.py:468-482`
  - **Problem:** Identical `_calculate_checksum()` method duplicated in both exporter and importer
  - **Fix:** Extract to shared utility module `src/backup/checksum_utils.py`

- [ ] **REF-064**: Archive Compression Level Hardcoded Without Rationale
  - **Location:** `src/backup/scheduler.py:146`, `src/memory/archive_compressor.py:34`, `src/memory/archive_exporter.py:27`
  - **Problem:** Compression level defaults to 6 in multiple places without explanation of tradeoff (speed vs size)
  - **Fix:** Document rationale in constant: `DEFAULT_COMPRESSION_LEVEL = 6  # Balanced: ~85% of gzip -9 size at 2x speed`

- [ ] **REF-066**: Markdown Export Hardcoded Timezone Format
  - **Location:** `src/backup/exporter.py:232`, `src/backup/exporter.py:271-272`
  - **Problem:** Uses `strftime('%Y-%m-%d %H:%M:%S UTC')` hardcoded to UTC without user preference
  - **Fix:** Add timezone parameter to export_to_markdown(), default to UTC but allow override

- [ ] **REF-068**: Export Markdown Slugify Allows Collision
  - **Location:** `src/backup/exporter.py:564-578`
  - **Problem:** `_slugify()` removes special chars but doesn't handle collisions. "Project-A" and "Project_A" both become "project-a"
  - **Fix:** Add uniqueness check and append counter suffix for collisions

- [ ] **REF-069**: Import Store/Update Memory Methods Duplicate Metadata Building
  - **Location:** `src/backup/importer.py:484-515`
  - **Problem:** Both `_store_memory()` and `_update_memory()` build identical metadata dict (lines 489-503). Update then deletes and re-stores (line 511-512).
  - **Fix:** Extract metadata building to helper, consider using store.update() API if available instead of delete+store

- [ ] **REF-070**: Auto-Tagger Stopword List Incomplete
  - **Location:** `src/tagging/auto_tagger.py:292-338`
  - **Problem:** Stopword list has 37 words but misses common technical terms that aren't good tags: "then", "than", "into", "also", "just", "when", "where", "what", "how", "why", "like", "more", "some", "been"
  - **Impact:** Low-value keyword tags pollute results
  - **Fix:** Expand stopword list or use NLTK/spaCy stopword corpus

- [ ] **REF-071**: Collection Auto-Generate Patterns Not User-Extensible
  - **Location:** `src/tagging/collection_manager.py:320-329`
  - **Problem:** Default tag patterns for auto-generation are hardcoded. Users can't add their own patterns without modifying source code.
  - **Fix:** Load patterns from config file (e.g., `~/.config/claude-memory/collection_patterns.yaml`)

- [ ] **REF-072**: Tag Statistics Not Tracked
  - **Location:** `src/tagging/tag_manager.py` (no usage tracking)
  - **Problem:** No visibility into tag usage: how many memories have each tag? Which tags are most/least used? Are auto-generated tags accurate?
  - **Impact:** Can't optimize tagging strategy or clean up unused tags
  - **Fix:** Add `get_tag_statistics()` method returning tag usage counts, confidence distributions, auto vs manual ratios

- [ ] **REF-074**: Classifier Default Fallback Always Returns PROJECT_CONTEXT
  - **Location:** `src/memory/classifier.py:164-165`, `179-186`
  - **Problem:** When all scores are low (<0.3), classifier falls back to `_default_for_category()`. But for 3 out of 5 categories (FACT, WORKFLOW, CONTEXT), default is PROJECT_CONTEXT. This creates bias toward PROJECT_CONTEXT.
  - **Impact:** Ambiguous memories are over-classified as project context
  - **Fix:** Consider returning UNKNOWN context level or using uniform distribution when confidence is low

- [ ] **REF-075**: Tag Full Path Separator Hardcoded
  - **Location:** `src/tagging/tag_manager.py:102`, `src/tagging/models.py:40-42`
  - **Problem:** "/" separator is hardcoded throughout. If user wants to create tag named "react/hooks" as flat tag (not hierarchy), it's impossible.
  - **Impact:** Naming restrictions; potential conflicts with file path tags
  - **Fix:** Either:
    1. Add escaping mechanism ("react\/hooks" for literal)
    2. Use different separator (e.g., "::" for hierarchy)
    3. Document limitation clearly

- [ ] **REF-076**: DependencyGraphGenerator._get_language Hardcoded - Duplicates Logic
  - **Location:** `src/memory/graph_generator.py:273-300`
  - **Problem:** Language detection from file extension is hardcoded in generator. If language mapping changes or new languages are added, must update in multiple places. Consider extracting to shared utility or configuration.
  - **Impact:** Maintenance burden, inconsistency risk
  - **Fix:** Extract language mapping to `src/graph/language_detector.py` or config file, reuse across codebase

- [ ] **REF-080**: Missing Type Hints for _adjacency_list Private Attribute
  - **Location:** `src/graph/dependency_graph.py:87`
  - **Problem:** Line 87 initializes `_adjacency_list: Dict[str, List[str]] = {}` with type hint in __init__, but class doesn't declare it at class level. Modern Python style is to declare all attributes at class level with type annotations for better IDE support.
  - **Impact:** Reduced IDE autocomplete, type checker warnings
  - **Fix:** Add class-level annotation: `_adjacency_list: Dict[str, List[str]]` before `__init__`

- [ ] **REF-081**: Call Graph Forward/Reverse Index Use defaultdict but Initialized as Regular Dict
  - **Location:** `src/graph/call_graph.py:96-97`
  - **Problem:** Lines 96-97 use `defaultdict(set)` which is good, but throughout the code (e.g., lines 120, 123, 159, 184) there are calls like `self.forward_index.get(node, set())`. This .get() pattern is redundant for defaultdict - can just use `self.forward_index[node]`.
  - **Impact:** Unnecessary defensive code, slight inefficiency
  - **Fix:** Replace all `.get(key, set())` with `[key]` for defaultdict attributes OR document why defensive .get() is preferred

- [ ] **REF-082**: Mermaid Formatter Doesn't Escape Pipe Character in Labels
  - **Location:** `src/graph/formatters/mermaid_formatter.py:94, 462`
  - **Problem:** Mermaid uses `|` for edge labels (e.g., `A -->|label| B`). If label text contains `|`, it can break parsing. File names rarely have pipes, but metadata like "5 units | 2KB" would break.
  - **Impact:** Rare but possible syntax errors in Mermaid output
  - **Fix:** Escape `|` to `\|` or use different metadata separator

- [ ] **REF-083**: JSON Formatter ensure_ascii=False May Cause Issues for Some Clients
  - **Location:** `src/graph/formatters/json_formatter.py:42`
  - **Problem:** `json.dumps(..., ensure_ascii=False)` outputs Unicode characters directly. While this is more readable, some older JSON parsers or tools expect ASCII-only JSON. The test at line 359 shows Unicode file paths are supported, but this could break clients.
  - **Impact:** Potential compatibility issues with strict JSON parsers
  - **Fix:** Add parameter to control ensure_ascii, default to True for safety

- [ ] **REF-100**: Inconsistent Error Message Format Across Exception Types
  - **Location:** `src/core/exceptions.py` (has structured errors with codes) vs store/service layers (plain strings)
  - **Problem:** StorageError/RetrievalError constructed with plain strings don't use error_code/solution/docs_url mechanism
  - **Fix:** Update all exception instantiation to use structured format: `StorageError(message, solution="...", error_code="E0XX")`

- [ ] **REF-102**: Embedding Generation Errors Don't Include Text Length or Model Name
  - **Location:** `src/embeddings/generator.py:206-207`
  - **Problem:** Generic "Failed to generate embedding" doesn't indicate if text was too long, too short, or model-specific issue
  - **Fix:** Include context in error: `raise EmbeddingError(f"Failed to generate embedding (text_len={len(text)}, model={self.model_name}): {e}")`

- [ ] **REF-106**: Hardcoded 384-Dimension Embedding Vectors in Tests 🔥
  - **Location:** 150+ test files with `[0.1] * 384` patterns
  - **Problem:** Default model changed from `all-MiniLM-L6-v2` (384 dims) to `all-mpnet-base-v2` (768 dims), but tests still hardcode 384
  - **Impact:** Tests fail with "Vector dimension error: expected dim: 384, got 768" when hitting real Qdrant collections
  - **Files affected:**
    - `tests/unit/test_advanced_filtering.py` (25+ instances)
    - `tests/unit/test_confidence_scores.py` (6 instances)
    - `tests/unit/test_services/*.py` (20+ instances)
    - `tests/integration/test_*.py` (30+ instances)
    - `tests/unit/test_git_*.py` (15+ instances)
    - Many more (~150 total occurrences)
  - **Fix:**

- [ ] **REF-237**: Inconsistent Empty List Handling in Aggregations
  - **Locations:** Many functions guard with ternary `if results else 0.0`, others use try/except
  - **Problem:** Inconsistent patterns make code hard to review. Examples:
    - `src/services/memory_service.py:522`: `avg_relevance = sum(...) / len(...) if memory_results else 0.0` (good)
    - `src/services/code_indexing_service.py:141`: `avg_score = sum(scores) / len(scores)` (missing guard)
  - **Fix:** Standardize on ternary guard pattern for all average calculations

- [ ] **REF-238**: Inconsistent Resource Ownership in IndexingService
  - **Location:** `src/memory/indexing_service.py:50-61` and `close()` at line 173-180
  - **Problem:** `_owns_indexer` flag determines cleanup, but if caller passes indexer then forgets to close it, resources leak. Ownership transfer is implicit.
  - **Impact:** Complex cleanup logic makes it easy to leak ProcessPoolExecutor when indexer is shared
  - **Fix:** Document ownership model clearly; consider builder pattern or making indexer always owned (clone if needed)

- [ ] **REF-240**: Service __init__ Methods Accept Too Many Optional Dependencies
  - **Location:** `src/services/memory_service.py:59-70`, `src/services/code_indexing_service.py:50-61`, `src/services/query_service.py:30-38`
  - **Problem:** Services accept 5-8 optional dependencies with default None. Example: `MemoryService.__init__(store, embedding_generator, embedding_cache, config, usage_tracker=None, conversation_tracker=None, query_expander=None, metrics_collector=None, project_name=None)`. This makes it hard to know which dependencies are actually required. Methods later do `if self.usage_tracker:` checks, making behavior inconsistent based on initialization.
  - **Impact:** MEDIUM - Unclear which features are active, hard to test, runtime failures when optional features are used but not initialized
  - **Fix:** Use builder pattern or dependency injection container, OR split into core service + feature extensions

- [ ] **REF-241**: Inconsistent Empty List Handling in Aggregations
  - **Locations:** Many functions guard with ternary `if results else 0.0`, others use try/except
  - **Problem:** Inconsistent patterns make code hard to review. Examples:
    - `src/services/memory_service.py:522`: `avg_relevance = sum(...) / len(...) if memory_results else 0.0` (good)
    - `src/services/code_indexing_service.py:141`: `avg_score = sum(scores) / len(scores)` (missing guard)
  - **Fix:** Standardize on ternary guard pattern for all average calculations

- [ ] **REF-242**: Unicode Normalization Missing in Text Splitting
  - **Location:** `src/search/pattern_matcher.py:166`: `lines = content.split("\n")`
  - **Problem:** Splits on `\n` but doesn't handle `\r\n` (Windows) or `\r` (old Mac) line endings. Can cause line number mismatches.
  - **Impact:** Incorrect line numbers reported for matches in Windows files
  - **Fix:** Use `content.splitlines()` instead of `split("\n")`

- [ ] **REF-246**: Unicode Normalization Missing in Text Splitting
  - **Location:** `src/search/pattern_matcher.py:166`: `lines = content.split("\n")`
  - **Problem:** Splits on `\n` but doesn't handle `\r\n` (Windows) or `\r` (old Mac) line endings. Can cause line number mismatches.
  - **Impact:** Incorrect line numbers reported for matches in Windows files
  - **Fix:** Use `content.splitlines()` instead of `split("\n")`

- [ ] **REF-248**: Duplicate Cache Close Logic Between close() and __del__
  - **Location:** `src/embeddings/cache.py:499-515` (close) and implicit in various generators
  - **Problem:** close() and __del__ both attempt cleanup; if close() partially fails, __del__ may re-attempt causing errors
  - **Impact:** Noisy error logs during cleanup, potential double-free issues
  - **Fix:** Add `_closed` flag; skip cleanup in __del__ if already closed

- [ ] **REF-250**: SpecializedRetrievalTools Methods Return List[MemoryResult] - Inconsistent with Store
  - **Location:** `src/core/tools.py:42-334` (SpecializedRetrievalTools methods)
  - **Problem:** Methods like `retrieve_preferences()` return `List[MemoryResult]` but underlying `store.search_with_filters()` returns `List[Tuple[MemoryUnit, float]]`. Tools convert tuples to MemoryResult objects, but this conversion logic is duplicated across 4 methods (lines 93-95, 154-156, 211-213, 259-261).
  - **Impact:** LOW - Code duplication, inconsistent return types across layers
  - **Fix:** Extract conversion to helper method `_convert_to_results(results: List[Tuple[MemoryUnit, float]]) -> List[MemoryResult]`

- [ ] **REF-253**: Inconsistent Context Manager Usage for Temporary Files
  - **Location:** Some tests use `with tempfile.TemporaryDirectory()`, others use `mkdtemp()` + finally block
  - **Problem:** Mixing patterns makes code harder to audit for leaks
  - **Fix:** Standardize on context managers (`with TemporaryDirectory()`) for all temp file/dir usage

- [ ] **REF-254**: Background Task Tracking Set Not Protected
  - **Location:** `src/memory/usage_tracker.py:84,152-153`
  - **Code:**
    ```python
    self._background_tasks: set = set()  # Instance variable

- [ ] **REF-255**: BaseCodeIndexer Abstract Class Not Used - IncrementalIndexer Doesn't Inherit
  - **Location:** `src/memory/incremental_indexer.py:76-147` (BaseCodeIndexer ABC), `src/memory/incremental_indexer.py:150+` (IncrementalIndexer class)
  - **Problem:** BaseCodeIndexer defines abstract interface with 5 methods but IncrementalIndexer in same file doesn't inherit from it. The ABC appears to be unused dead code or a planned interface never implemented.
  - **Impact:** LOW - Dead code, unclear design intent
  - **Fix:** Either (1) remove BaseCodeIndexer if unused OR (2) make IncrementalIndexer inherit from it

- [ ] **REF-257**: No NaN or Infinity Checks in Numeric Inputs
  - **Location:** Throughout codebase, numeric parameters (scores, importance) not validated for NaN/Inf
  - **Problem:** Python allows `float('nan')` and `float('inf')` which pass through Pydantic validators (they are valid floats)
  - **Impact:** Could corrupt vector databases or cause unexpected comparison behavior
  - **Fix:** Add validators in Pydantic models: `@field_validator('importance') def check_finite(v): if not math.isfinite(v): raise ValueError(...); return v`

- [ ] **REF-260**: BaseCallExtractor Abstract Methods Don't Specify Return Type Consistency
  - **Location:** `src/analysis/call_extractors.py:14-52`
  - **Problem:** `extract_calls()` and `extract_implementations()` return `List[Dict[str, Any]]` but don't specify required dict keys. Implementations (PythonCallExtractor, etc.) may return different dict structures, breaking callers.
  - **Impact:** MEDIUM - Type safety issue, callers can't rely on dict structure
  - **Fix:** Define TypedDict or Pydantic model for call/implementation records

- [ ] **REF-261**: No NaN or Infinity Checks in Numeric Inputs
  - **Location:** Throughout codebase, numeric parameters (scores, importance) not validated for NaN/Inf
  - **Problem:** Python allows `float('nan')` and `float('inf')` which pass through Pydantic validators (they are valid floats)
  - **Impact:** Could corrupt vector databases or cause unexpected comparison behavior
  - **Fix:** Add validators in Pydantic models: `@field_validator('importance') def check_finite(v): if not math.isfinite(v): raise ValueError(...); return v`

- [ ] **REF-265**: NotificationBackend Abstract Method Missing Error Handling Contract
  - **Location:** `src/memory/notification_manager.py:18-23`
  - **Problem:** `notify()` method is abstract but doesn't specify whether it should raise exceptions or return error status. Implementations may have inconsistent error behavior.
  - **Impact:** LOW - Unclear error handling contract
  - **Fix:** Document in base class: "Raises: NotificationError if delivery fails" or "Returns: bool for success/failure"

- [ ] **REF-272**: Duplicated Embedding Retrieval Logic Across Services
  - **Location:** `src/services/memory_service.py:113-139`, `src/services/code_indexing_service.py:99-107`
  - **Problem:** Both MemoryService and CodeIndexingService implement nearly identical `_get_embedding()` methods with cache checking. MemoryService tracks cache hit/miss stats, CodeIndexingService doesn't. This violates DRY principle and creates maintenance burden.
  - **Fix:** Extract to shared `EmbeddingService` or utility class. Centralize cache hit/miss tracking. Estimated 30-40 lines of duplicate code eliminated.

- [ ] **REF-273**: Duplicated Embedding Retrieval Logic Across Services
  - **Location:** `src/services/memory_service.py:113-139`, `src/services/code_indexing_service.py:99-107`
  - **Problem:** Both MemoryService and CodeIndexingService implement nearly identical `_get_embedding()` methods with cache checking. MemoryService tracks cache hit/miss stats, CodeIndexingService doesn't. This violates DRY principle and creates maintenance burden.
  - **Fix:** Extract to shared `EmbeddingService` or utility class. Centralize cache hit/miss tracking. Estimated 30-40 lines of duplicate code eliminated.

- [ ] **REF-275**: Inconsistent Service Initialization Parameters
  - **Location:** All service `__init__` methods
  - **Problem:** Services have inconsistent optional dependency patterns. MemoryService takes 9 parameters (4 required, 5 optional), CodeIndexingService takes 8 (4 required, 4 optional), CrossProjectService takes 5, etc. No standard interface or base class. Makes it hard to refactor or add new services.
  - **Fix:** Create `BaseService` abstract class with standard initialization pattern. Use dependency injection container. Define clear interfaces for optional components (usage_tracker, metrics_collector, etc.).

- [ ] **REF-276**: Inconsistent Service Initialization Parameters
  - **Location:** All service `__init__` methods
  - **Problem:** Services have inconsistent optional dependency patterns. MemoryService takes 9 parameters (4 required, 5 optional), CodeIndexingService takes 8 (4 required, 4 optional), CrossProjectService takes 5, etc. No standard interface or base class. Makes it hard to refactor or add new services.
  - **Fix:** Create `BaseService` abstract class with standard initialization pattern. Use dependency injection container. Define clear interfaces for optional components (usage_tracker, metrics_collector, etc.).

- [ ] **REF-278**: Error Handling Inconsistency Between Services
  - **Location:** All services
  - **Problem:** Services handle errors inconsistently. MemoryService wraps most operations in try/except with `StorageError` or `RetrievalError`. QueryService raises `StorageError` for disabled features. HealthService sometimes returns `{"status": "disabled"}` dict instead of raising. CrossProjectService returns error dicts in some methods, raises exceptions in others.
  - **Fix:** Standardize error handling pattern across all services. Define when to raise exceptions vs return error dicts. Document in service layer guidelines.

- [ ] **REF-279**: Error Handling Inconsistency Between Services
  - **Location:** All services
  - **Problem:** Services handle errors inconsistently. MemoryService wraps most operations in try/except with `StorageError` or `RetrievalError`. QueryService raises `StorageError` for disabled features. HealthService sometimes returns `{"status": "disabled"}` dict instead of raising. CrossProjectService returns error dicts in some methods, raises exceptions in others.
  - **Fix:** Standardize error handling pattern across all services. Define when to raise exceptions vs return error dicts. Document in service layer guidelines.

- [ ] **REF-281**: Incomplete Stats Tracking in Services
  - **Location:** `src/services/code_indexing_service.py:87-94`, `src/services/analytics_service.py:58-61`
  - **Problem:** CodeIndexingService tracks 4 stats counters but doesn't track cache hits/misses (MemoryService does). AnalyticsService only tracks 1 counter ("analytics_queries"). Inconsistent granularity makes cross-service monitoring difficult.
  - **Fix:** Define standard metrics all services should track (operation_count, error_count, avg_latency_ms, cache_stats). Implement in base service class.

- [ ] **REF-282**: Incomplete Stats Tracking in Services
  - **Location:** `src/services/code_indexing_service.py:87-94`, `src/services/analytics_service.py:58-61`
  - **Problem:** CodeIndexingService tracks 4 stats counters but doesn't track cache hits/misses (MemoryService does). AnalyticsService only tracks 1 counter ("analytics_queries"). Inconsistent granularity makes cross-service monitoring difficult.
  - **Fix:** Define standard metrics all services should track (operation_count, error_count, avg_latency_ms, cache_stats). Implement in base service class.

- [ ] **REF-284**: Circular Import Risk Between Services
  - **Location:** `src/services/code_indexing_service.py:567-588` (imports IncrementalIndexer), `src/services/cross_project_service.py:112-118` (imports MultiRepositorySearcher)
  - **Problem:** Services import from `src.memory.*` modules within method bodies (not at module level), suggesting potential circular dependency. If memory modules later need to import services, this creates a cycle.
  - **Fix:** Use dependency injection to pass indexer/searcher instances to services instead of constructing them internally. Move to constructor parameters.

- [ ] **REF-285**: Circular Import Risk Between Services
  - **Location:** `src/services/code_indexing_service.py:567-588` (imports IncrementalIndexer), `src/services/cross_project_service.py:112-118` (imports MultiRepositorySearcher)
  - **Problem:** Services import from `src.memory.*` modules within method bodies (not at module level), suggesting potential circular dependency. If memory modules later need to import services, this creates a cycle.
  - **Fix:** Use dependency injection to pass indexer/searcher instances to services instead of constructing them internally. Move to constructor parameters.

- [ ] **REF-286**: Duplicated Query Quality Analysis Logic
  - **Location:** `src/services/code_indexing_service.py:119-191` (search_code quality analysis), `src/services/code_indexing_service.py:537-551` (find_similar_code interpretation)
  - **Problem:** Both methods implement similar result quality assessment logic (score thresholds, suggestions, interpretation). ~50 lines of duplicated pattern-matching logic.
  - **Fix:** Extract to shared `ResultQualityAnalyzer` class or utility module. Use strategy pattern for different analysis types (code search vs similarity vs memory retrieval).

- [ ] **REF-287**: Duplicated Query Quality Analysis Logic
  - **Location:** `src/services/code_indexing_service.py:119-191` (search_code quality analysis), `src/services/code_indexing_service.py:537-551` (find_similar_code interpretation)
  - **Problem:** Both methods implement similar result quality assessment logic (score thresholds, suggestions, interpretation). ~50 lines of duplicated pattern-matching logic.
  - **Fix:** Extract to shared `ResultQualityAnalyzer` class or utility module. Use strategy pattern for different analysis types (code search vs similarity vs memory retrieval).

- [ ] **REF-288**: Hardcoded Magic Numbers in Quality Score Calculations
  - **Location:** `src/services/health_service.py:73-95` (_calculate_simple_health_score)
  - **Problem:** Health score calculation uses hardcoded thresholds (100ms latency = -10 score, 50ms = -10, error_rate > 0.1 = -30, etc.). These magic numbers should be configurable.
  - **Fix:** Move thresholds to ServerConfig as health_score_config dict. Allow tuning per deployment.

- [ ] **REF-289**: Hardcoded Magic Numbers in Quality Score Calculations
  - **Location:** `src/services/health_service.py:73-95` (_calculate_simple_health_score)
  - **Problem:** Health score calculation uses hardcoded thresholds (100ms latency = -10 score, 50ms = -10, error_rate > 0.1 = -30, etc.). These magic numbers should be configurable.
  - **Fix:** Move thresholds to ServerConfig as health_score_config dict. Allow tuning per deployment.

- [ ] **REF-293**: Module Resolution Only Handles Relative Imports
  - **Location:** `src/memory/dependency_graph.py:78-143`
  - **Problem:** The `_resolve_module_to_file()` method only resolves relative imports (lines 109-138). Absolute imports within the project are silently ignored (line 142 returns None). This means the dependency graph is incomplete - it won't track absolute imports like `from src.core.models import Memory` even though they're internal to the project.
  - **Fix:** Add project-root-aware absolute import resolution. For Python: check if module path starts with project package name, resolve to `project_root / module.replace('.', '/')`. Document this limitation or implement full resolution.

- [ ] **REF-298**: Weighted Fusion Default Score Penalizes Single-Method Results
  - **Location:** `src/search/hybrid_search.py:186`
  - **Problem:** When memory only appears in one result set, default score is 0.0 for the other, which reduces combined score by `(1-alpha)` or `alpha`; this unfairly penalizes good results from one method
  - **Fix:** Consider using geometric mean or not penalizing missing scores; document current behavior

- [ ] **REF-299**: Import Extractor Has No Language Version Handling
  - **Location:** `src/memory/import_extractor.py:50-78`
  - **Problem:** The import regex patterns are language-version-agnostic. Python 3.10+ supports `match`/`case`, TypeScript 5.0 changed import syntax, Rust 2021 edition has different module paths. The extractor will miss or incorrectly parse newer syntax.
  - **Fix:** Add optional `language_version` parameter to `extract_imports()`. Use version-specific regex patterns. Document supported language versions.

- [ ] **REF-300**: Inconsistent Error Handling Between File and Directory Indexing
  - **Location:** `src/memory/incremental_indexer.py:255-388` (index_file) vs `src/memory/incremental_indexer.py:390-546` (index_directory)
  - **Problem:** `index_file()` raises `StorageError` on failure (line 388), forcing caller to handle exception. `index_directory()` catches all exceptions, logs them, and returns failure in `failed_files` list (line 489). Inconsistent error contract makes it unclear when to expect exceptions vs error results.
  - **Fix:** Standardize on one pattern. Recommend: index_file raises exceptions (caller decides), index_directory catches and aggregates (batch operation). Document in docstrings.

- [ ] **REF-301**: Duplicate Code in Index File Path Resolution
  - **Location:** `src/memory/incremental_indexer.py:271`, `src/memory/incremental_indexer.py:412`, `src/memory/incremental_indexer.py:558`
  - **Problem:** Three methods all call `Path(file_path).resolve()` to normalize paths. This pattern is repeated without abstraction. If path resolution logic needs to change (e.g., to handle symlinks differently), must update 3+ places.
  - **Fix:** Extract to `_resolve_file_path(self, file_path: Path) -> Path` helper method

- [ ] **REF-303**: Function Signature Parsing Regex Is Fragile
  - **Location:** `src/memory/incremental_indexer.py:1165-1200`
  - **Problem:** The `_extract_parameters()` method uses simple regex to parse function signatures. It will break on: nested generics `func(a: Dict[str, List[Tuple[int, int]]])`, lambda parameters, decorators with parameters, async generator syntax. Only handles simple cases.
  - **Fix:** Use proper AST parsing for parameter extraction instead of regex. The Rust parser already provides this info - extract from `unit.signature` structure instead of string parsing.

- [ ] **REF-305**: Duplicate Rich Console Availability Checks
  - **Location:** `src/cli/health_command.py:11-17`, `src/cli/status_command.py:10-18`, `src/cli/index_command.py:10-16`, and 8+ other files
  - **Problem:** Every command file has identical `try: from rich import Console; RICH_AVAILABLE = True except: RICH_AVAILABLE = False` boilerplate (50+ lines total)
  - **Fix:** Create `src/cli/console_utils.py` with `get_console() -> Optional[Console]` that handles import + fallback once

- [ ] **REF-309**: Duplicate Date Parsing Logic in git_search_command
  - **Location:** `src/cli/git_search_command.py:50-71` (since parsing) and `git_search_command.py:73-89` (until parsing)
  - **Problem:** Nearly identical date parsing code duplicated for 'since' and 'until' parameters. Both handle "today", "yesterday", "last week", ISO format, etc.
  - **Fix:** Extract to `_parse_date_filter(date_str: str) -> Optional[datetime]` method

- [ ] **REF-312**: Python Call Extractor Doesn't Reset State Between Calls
  - **Location:** `src/analysis/call_extractors.py:59-61`, `src/analysis/call_extractors.py:78-80`
  - **Problem:** The `extract_calls()` method sets `self.current_class = None` and `self.current_function = None` at the start (lines 78-80), but these are instance variables that could leak state if an exception is raised mid-extraction. If parsing fails after setting `current_class = "Foo"`, the next call to `extract_calls()` for a different file will still have `current_class = "Foo"` in context.
  - **Fix:** Use local variables instead of instance variables for tracking context within a single file parse, or use a context manager to ensure cleanup

- [ ] **REF-317**: Inconsistent Table Width Settings
  - **Location:** `src/cli/repository_command.py:234` sets `max_width=15`, `src/cli/workspace_command.py:282` sets `max_width=20`, many others have no max_width
  - **Problem:** Some tables constrain column width, others don't. Long project names or descriptions cause ugly table wrapping inconsistently.
  - **Fix:** Define standard table width constants: `ID_COL_WIDTH = 15`, `NAME_COL_WIDTH = 30`, `DESC_COL_WIDTH = 50`

- [ ] **REF-320**: Missing Type Hints for Return Values in Call Extractors
  - **Location:** `src/analysis/call_extractors.py:310-325`, `src/analysis/call_extractors.py:379-393`
  - **Problem:** Helper methods like `_extract_function_name()`, `_extract_callee_name()`, and `_extract_method_name()` return `Optional[str]` but the return statements don't use explicit None returns in all paths. Lines 324, 392 have bare `pass` in except blocks, then implicitly return None. This makes it unclear whether None is intentional or a bug.
  - **Fix:** Add explicit `return None` in all exception handlers and document when/why None is returned

- [ ] **REF-321**: Duplicate watch_debounce_ms Field Definitions
  - **Location:** `src/config.py:162` (in IndexingFeatures) and `src/config.py:341` (in ServerConfig)
  - **Problem:** `watch_debounce_ms` is defined twice - once as a feature group field (IndexingFeatures.watch_debounce_ms = 1000) and once as a top-level ServerConfig field (ServerConfig.watch_debounce_ms = 1000). This creates confusion about which value is used and potential inconsistency.
  - **Fix:** Remove line 341 duplication. Use `self.indexing.watch_debounce_ms` consistently throughout codebase. This is the same issue as the old BUG-034 duplicate config field that was fixed.

- [ ] **REF-322**: Duplicate watch_debounce_ms Field Definitions
  - **Location:** `src/config.py:162` (in IndexingFeatures) and `src/config.py:341` (in ServerConfig)
  - **Problem:** `watch_debounce_ms` is defined twice - once as a feature group field (IndexingFeatures.watch_debounce_ms = 1000) and once as a top-level ServerConfig field (ServerConfig.watch_debounce_ms = 1000). This creates confusion about which value is used and potential inconsistency.
  - **Fix:** Remove line 341 duplication. Use `self.indexing.watch_debounce_ms` consistently throughout codebase. This is the same issue as the old BUG-034 duplicate config field that was fixed.

- [ ] **REF-323**: Hardcoded Health Status Thresholds Duplicated Across Files
  - **Location:** `src/monitoring/health_reporter.py:293-304`, `src/monitoring/capacity_planner.py:108-117`, `src/memory/health_scorer.py:126-133`
  - **Problem:** Three different files define their own health status thresholds (EXCELLENT >= 90, GOOD >= 75, etc.). While the values are currently identical, they're hardcoded magic numbers in each file. If we need to adjust thresholds (e.g., make "GOOD" >= 70 instead of 75), must change 3+ files. This creates inconsistency risk where different components report different health statuses for the same score.
  - **Fix:** Extract to shared constants in `src/monitoring/constants.py`: `HEALTH_STATUS_THRESHOLDS = {"EXCELLENT": 90, "GOOD": 75, "FAIR": 60, "POOR": 40}`. Import in all files.

- [ ] **REF-327**: Inconsistent Error Callback Pattern Across create_task Calls
  - **Location:** `src/memory/usage_tracker.py:152-153` (has callback), `src/memory/conversation_tracker.py:104` (no callback), `src/memory/background_indexer.py:112` (no callback), `src/memory/auto_indexing_service.py:363` (no callback)
  - **Problem:** Only usage_tracker adds error callback to background tasks via `task.add_done_callback(self._handle_background_task_done)`. Other components (conversation_tracker, background_indexer, auto_indexing_service) create background tasks without error callbacks, risking silent exception loss.
  - **Fix:** Standardize pattern - all fire-and-forget tasks should have error callback that logs exceptions

- [ ] **REF-328**: Inconsistent Error Callback Pattern Across create_task Calls
  - **Location:** `src/memory/usage_tracker.py:152-153` (has callback), `src/memory/conversation_tracker.py:104` (no callback), `src/memory/background_indexer.py:112` (no callback), `src/memory/auto_indexing_service.py:363` (no callback)
  - **Problem:** Only usage_tracker adds error callback to background tasks via `task.add_done_callback(self._handle_background_task_done)`. Other components (conversation_tracker, background_indexer, auto_indexing_service) create background tasks without error callbacks, risking silent exception loss.
  - **Fix:** Standardize pattern - all fire-and-forget tasks should have error callback that logs exceptions

- [ ] **REF-331**: Duplicate Emoji Constants in Capacity Recommendations
  - **Location:** `src/monitoring/capacity_planner.py:457-516`
  - **Problem:** The `_generate_capacity_recommendations()` method uses hardcoded emoji strings inline in 8 different locations. If recommendations need to be rendered in a non-emoji-supporting terminal or UI, must change 8+ places. Also makes testing harder (must match exact emoji strings).
  - **Fix:** Define constants at module level or make emojis optional via config flag.

- [ ] **REF-334**: Query Expansion Similarity Threshold Redundantly Validated Twice
  - **Location:** `src/config.py:364` and `src/config.py:575-580`
  - **Problem:** `query_expansion_similarity_threshold` is validated in the large `validate_config()` model_validator (lines 575-580) to be in [0.0, 1.0]. This should be a `@field_validator` for consistency and better error messages.
  - **Fix:** Add `@field_validator('query_expansion_similarity_threshold')` and remove from validate_config()

- [ ] **REF-335**: Query Expansion Similarity Threshold Redundantly Validated Twice
  - **Location:** `src/config.py:364` and `src/config.py:575-580`
  - **Problem:** `query_expansion_similarity_threshold` is validated in the large `validate_config()` model_validator (lines 575-580) to be in [0.0, 1.0]. This should be a `@field_validator` for consistency and better error messages.
  - **Fix:** Add `@field_validator('query_expansion_similarity_threshold')` and remove from validate_config()

- [ ] **REF-336**: Job History Unbounded Growth in Health Jobs
  - **Location:** `src/memory/health_jobs.py:83-84`, `src/memory/health_jobs.py:195`, `src/memory/health_jobs.py:306`, `src/memory/health_jobs.py:369`
  - **Problem:** The `HealthMaintenanceJobs` class appends every job result to `self.job_history` list (lines 195, 306, 369) with no size limit. If jobs run every week for a year, that's 52 * 3 = 156 entries minimum. If jobs run daily (via manual trigger), that's 1000+ entries. The list grows unbounded and is never cleared except manually via `clear_job_history()` (line 404). In contrast, HealthJobScheduler limits history to last 100 entries (line 164).
  - **Fix:** Add automatic trimming in job methods: `self.job_history.append(result); if len(self.job_history) > 100: self.job_history = self.job_history[-100:]`

- [ ] **REF-342**: ParallelGenerator._background_tasks Set Never Cleaned Up
  - **Location:** `src/embeddings/parallel_generator.py:84, 152-153`
  - **Problem:** UsageTracker maintains `self._background_tasks: set = set()` to track fire-and-forget flush tasks (line 84), and adds/removes tasks properly (lines 152-153, 221). However, if many tasks are created rapidly, the set could grow unbounded since tasks are only removed on completion. No periodic cleanup or size limit.
  - **Fix:** Add periodic cleanup or max size check, log warning if set exceeds threshold (e.g., 100 tasks)

- [ ] **REF-343**: ParallelGenerator._background_tasks Set Never Cleaned Up
  - **Location:** `src/embeddings/parallel_generator.py:84, 152-153`
  - **Problem:** UsageTracker maintains `self._background_tasks: set = set()` to track fire-and-forget flush tasks (line 84), and adds/removes tasks properly (lines 152-153, 221). However, if many tasks are created rapidly, the set could grow unbounded since tasks are only removed on completion. No periodic cleanup or size limit.
  - **Fix:** Add periodic cleanup or max size check, log warning if set exceeds threshold (e.g., 100 tasks)

- [ ] **REF-346**: Inconsistent Dry-Run Behavior Across Remediation Actions
  - **Location:** `src/monitoring/remediation.py:230-254`, `src/monitoring/remediation.py:256-285`
  - **Problem:** The `_dry_run_action()` method handles dry-run for `prune_stale_memories` and `cleanup_old_sessions` specially (lines 235-248), but for all other actions returns `RemediationResult(success=True, items_affected=0, details={"action": "dry_run", "note": "count not available"})` (line 250-254). This means dry-run for `archive_inactive_projects`, `merge_duplicates`, and `optimize_database` doesn't provide useful information - it just says "would run" with no impact estimate. Users can't make informed decisions.
  - **Fix:** Implement proper dry-run for all actions. `optimize_database` could report current DB size, `archive_inactive_projects` could count inactive projects, etc.

- [ ] **REF-349**: Path Expansion Creates Directories on Config Load
  - **Location:** `src/config.py:641` and `src/config.py:648`
  - **Problem:** The properties `embedding_cache_path_expanded` and `sqlite_path_expanded` call `path.parent.mkdir(parents=True, exist_ok=True)` as a side effect of accessing the property. This violates principle of least surprise - simply loading config should not create filesystem changes. If user has wrong permissions, config load will fail unexpectedly.
  - **Fix:** Remove mkdir from properties. Create directories lazily when first writing to those paths (in EmbeddingCache.__init__, etc.)

- [ ] **REF-350**: Path Expansion Creates Directories on Config Load
  - **Location:** `src/config.py:641` and `src/config.py:648`
  - **Problem:** The properties `embedding_cache_path_expanded` and `sqlite_path_expanded` call `path.parent.mkdir(parents=True, exist_ok=True)` as a side effect of accessing the property. This violates principle of least surprise - simply loading config should not create filesystem changes. If user has wrong permissions, config load will fail unexpectedly.
  - **Fix:** Remove mkdir from properties. Create directories lazily when first writing to those paths (in EmbeddingCache.__init__, etc.)

- [ ] **REF-351**: Database Optimization Uses Blocking Operations
  - **Location:** `src/monitoring/remediation.py:367-387`
  - **Problem:** The `_optimize_database()` method runs `VACUUM` (line 372) and `ANALYZE` (line 375) on SQLite database. Both are blocking operations that can take 10+ seconds on large databases (1GB+). The entire remediation engine (and any other code using the same database connection) is blocked during this time. If called during a busy period, this causes user-visible latency spikes.
  - **Fix:** Add warning log before optimization: `logger.warning("Starting database optimization - may block for 10+ seconds")`. Consider running VACUUM in a separate transaction or thread. Document that this should only run during maintenance windows.

- [ ] **REF-355**: Export Falls Back to Dummy Vector for Non-Qdrant Stores
  - **Location:** `src/backup/exporter.py:387-410`
  - **Problem:** For non-Qdrant stores, creates dummy embedding `[0.0] * 768` (line 398) which is misleading. User won't know export is incomplete until import fails.
  - **Fix:** Raise NotImplementedError for non-Qdrant stores with clear message directing user to Qdrant-only export

- [ ] **REF-356**: Export Falls Back to Dummy Vector for Non-Qdrant Stores
  - **Location:** `src/backup/exporter.py:387-410`
  - **Problem:** For non-Qdrant stores, creates dummy embedding `[0.0] * 768` (line 398) which is misleading. User won't know export is incomplete until import fails.
  - **Fix:** Raise NotImplementedError for non-Qdrant stores with clear message directing user to Qdrant-only export

- [ ] **REF-357**: Inconsistent Async Test Patterns
  - **Location:** Mix of `@pytest.mark.asyncio` and `pytest_asyncio.fixture` usage
  - **Problem:** Some tests use `@pytest.mark.asyncio`, others use `pytest_asyncio.fixture`, some mix both. No clear pattern.
  - **Impact:** Confusion about which pattern to use for new tests
  - **Fix:** Standardize on pytest-asyncio patterns, document in TESTING_GUIDE.md

- [ ] **REF-358**: Inconsistent Async Test Patterns
  - **Location:** Mix of `@pytest.mark.asyncio` and `pytest_asyncio.fixture` usage
  - **Problem:** Some tests use `@pytest.mark.asyncio`, others use `pytest_asyncio.fixture`, some mix both. No clear pattern.
  - **Impact:** Confusion about which pattern to use for new tests
  - **Fix:** Standardize on pytest-asyncio patterns, document in TESTING_GUIDE.md

- [ ] **REF-359**: Duplicate Checksum Calculation Code
  - **Location:** `src/backup/exporter.py:523-537` and `src/backup/importer.py:468-482`
  - **Problem:** Identical `_calculate_checksum()` method duplicated in both exporter and importer
  - **Fix:** Extract to shared utility module `src/backup/checksum_utils.py`

- [ ] **REF-360**: Test Data in test_data/ Directory Unused
  - **Location:** `tests/test_data/` directory exists
  - **Problem:** Directory is present but unclear what it contains or which tests use it
  - **Impact:** Potentially unused test data accumulating
  - **Fix:** Document test data directory purpose or remove if unused

- [ ] **REF-361**: Test Data in test_data/ Directory Unused
  - **Location:** `tests/test_data/` directory exists
  - **Problem:** Directory is present but unclear what it contains or which tests use it
  - **Impact:** Potentially unused test data accumulating
  - **Fix:** Document test data directory purpose or remove if unused

- [ ] **REF-362**: Archive Compression Level Hardcoded Without Rationale
  - **Location:** `src/backup/scheduler.py:146`, `src/memory/archive_compressor.py:34`, `src/memory/archive_exporter.py:27`
  - **Problem:** Compression level defaults to 6 in multiple places without explanation of tradeoff (speed vs size)
  - **Fix:** Document rationale in constant: `DEFAULT_COMPRESSION_LEVEL = 6  # Balanced: ~85% of gzip -9 size at 2x speed`

- [ ] **REF-368**: Markdown Export Hardcoded Timezone Format
  - **Location:** `src/backup/exporter.py:232`, `src/backup/exporter.py:271-272`
  - **Problem:** Uses `strftime('%Y-%m-%d %H:%M:%S UTC')` hardcoded to UTC without user preference
  - **Fix:** Add timezone parameter to export_to_markdown(), default to UTC but allow override

- [ ] **REF-369**: Auto-Tagger Hierarchical Inference Hardcoded and Incomplete
  - **Location:** `src/tagging/auto_tagger.py:175-226`
  - **Problem:** `infer_hierarchical_tags()` has hardcoded mappings (python→language/python, react→framework/react) but:
    1. Only handles 6 languages, 6 frameworks, 4 patterns, 4 domains
    2. Doesn't handle new tags added by users
    3. Logic like "if async in tags and python in tags → language/python/async" is fragile (what about other languages with async?)
  - **Impact:** Auto-tagging produces flat tags for most content; hierarchical organization is incomplete
  - **Fix:**
    1. Make hierarchy rules configurable (YAML/JSON file)
    2. Add auto-detection: if tag contains "/" already, don't infer hierarchy
    3. Use parent_id in tag creation instead of string path manipulation

- [ ] **REF-370**: Auto-Tagger Hierarchical Inference Hardcoded and Incomplete
  - **Location:** `src/tagging/auto_tagger.py:175-226`
  - **Problem:** `infer_hierarchical_tags()` has hardcoded mappings (python to language/python, react to framework/react) but:
    1. Only handles 6 languages, 6 frameworks, 4 patterns, 4 domains
    2. Doesn't handle new tags added by users
    3. Logic like "if async in tags and python in tags then language/python/async" is fragile (what about other languages with async?)
  - **Impact:** Auto-tagging produces flat tags for most content; hierarchical organization is incomplete
  - **Fix:**
    1. Make hierarchy rules configurable (YAML/JSON file)
    2. Add auto-detection: if tag contains "/" already, don't infer hierarchy
    3. Use parent_id in tag creation instead of string path manipulation

- [ ] **REF-374**: Export Markdown Slugify Allows Collision
  - **Location:** `src/backup/exporter.py:564-578`
  - **Problem:** `_slugify()` removes special chars but doesn't handle collisions. "Project-A" and "Project_A" both become "project-a"
  - **Fix:** Add uniqueness check and append counter suffix for collisions

- [ ] **REF-375**: Tag Merge Doesn't Update Collection Filters
  - **Location:** `src/tagging/tag_manager.py:307-353` (merge_tags), `src/tagging/collection_manager.py` (no update logic)
  - **Problem:** When merging tags (e.g., merge "js" into "javascript"), collections with tag_filter referencing "js" are not updated to reference "javascript" instead.
  - **Impact:** Collections break silently after tag merges; filter becomes invalid
  - **Fix:** Add collection filter update to merge_tags():
    ```python

- [ ] **REF-376**: Tag Merge Doesn't Update Collection Filters
  - **Location:** `src/tagging/tag_manager.py:307-353` (merge_tags), `src/tagging/collection_manager.py` (no update logic)
  - **Problem:** When merging tags (e.g., merge "js" into "javascript"), collections with tag_filter referencing "js" are not updated to reference "javascript" instead.
  - **Impact:** Collections break silently after tag merges; filter becomes invalid
  - **Fix:** Add collection filter update to merge_tags() - after merging memory_tags, also update collection filters

- [ ] **REF-377**: Import Store/Update Memory Methods Duplicate Metadata Building
  - **Location:** `src/backup/importer.py:484-515`
  - **Problem:** Both `_store_memory()` and `_update_memory()` build identical metadata dict (lines 489-503). Update then deletes and re-stores (line 511-512).
  - **Fix:** Extract metadata building to helper, consider using store.update() API if available instead of delete+store

- [ ] **REF-378**: Classifier Keyword Lists Are Not Comprehensive
  - **Location:** `src/memory/classifier.py:16-70`
  - **Problem:** Keyword patterns are limited (13 user pref, 14 project, 10 session). Many common patterns missing:
    - User preferences: "my approach", "I typically", "my workflow", "my convention"
    - Project context: "tech stack", "repo", "repository", "codebase structure"
    - Session state: "wip", "todo", "fixing", "debugging", "implementing"
  - **Impact:** Legitimate classification signals are missed; classifier falls back to defaults more often than needed
  - **Fix:** Expand keyword lists based on corpus analysis; consider making lists configurable/extensible

- [ ] **REF-379**: Classifier Keyword Lists Are Not Comprehensive
  - **Location:** `src/memory/classifier.py:16-70`
  - **Problem:** Keyword patterns are limited (13 user pref, 14 project, 10 session). Many common patterns missing:
    - User preferences: "my approach", "I typically", "my workflow", "my convention"
    - Project context: "tech stack", "repo", "repository", "codebase structure"
    - Session state: "wip", "todo", "fixing", "debugging", "implementing"
  - **Impact:** Legitimate classification signals are missed; classifier falls back to defaults more often than needed
  - **Fix:** Expand keyword lists based on corpus analysis; consider making lists configurable/extensible

- [ ] **REF-380**: Circular Dependency Detection Runs on Every get_stats Call
  - **Location:** `src/graph/dependency_graph.py:304`
  - **Problem:** `get_stats()` calls `find_circular_dependencies()` which runs full DFS cycle detection. While the result is cached in `_circular_deps`, the cache is invalidated if graph is modified. If user calls `get_stats()` repeatedly (e.g., in a monitoring loop), and graph is rebuilt each time, full DFS runs every time.
  - **Impact:** O(V+E) performance cost on every stats call for large graphs
  - **Fix:** Add `skip_circular_check=False` parameter to get_stats(), document that circular_dependency_count will be 0 if skipped

- [ ] **REF-381**: Auto-Tagger Stopword List Incomplete
  - **Location:** `src/tagging/auto_tagger.py:292-338`
  - **Problem:** Stopword list has 37 words but misses common technical terms that aren't good tags: "then", "than", "into", "also", "just", "when", "where", "what", "how", "why", "like", "more", "some", "been"
  - **Impact:** Low-value keyword tags pollute results
  - **Fix:** Expand stopword list or use NLTK/spaCy stopword corpus

- [ ] **REF-382**: Circular Dependency Detection Runs on Every get_stats Call
  - **Location:** `src/graph/dependency_graph.py:304`
  - **Problem:** `get_stats()` calls `find_circular_dependencies()` which runs full DFS cycle detection. While the result is cached in `_circular_deps`, the cache is invalidated if graph is modified. If user calls `get_stats()` repeatedly (e.g., in a monitoring loop), and graph is rebuilt each time, full DFS runs every time.
  - **Impact:** O(V+E) performance cost on every stats call for large graphs
  - **Fix:** Add `skip_circular_check=False` parameter to get_stats(), document that circular_dependency_count will be 0 if skipped

- [ ] **REF-383**: Mermaid linkStyle Uses Edge Index Which Changes with Filtering
  - **Location:** `src/graph/formatters/mermaid_formatter.py:66, 148-164`
  - **Problem:** Line 66 uses `_get_edge_index()` to find edge position for styling, but if graph is filtered (e.g., by language or pattern), edge indices change. A circular edge might be at index 5 in full graph but index 2 in filtered graph, causing wrong edge to be styled red.
  - **Example:** Full graph has edges [A→B, B→C, C→D, C→A (circular), D→E]. After filtering to just [A,B,C], edges are [A→B, B→C, C→A]. Original index was 3, new index is 2.
  - **Impact:** Red circular styling applied to wrong edges in filtered graphs
  - **Fix:** Count edges as they're emitted instead of using global index, or track edges by (source, target) tuple

- [ ] **REF-384**: Collection Auto-Generate Patterns Not User-Extensible
  - **Location:** `src/tagging/collection_manager.py:320-329`
  - **Problem:** Default tag patterns for auto-generation are hardcoded. Users can't add their own patterns without modifying source code.
  - **Fix:** Load patterns from config file (e.g., `~/.config/claude-memory/collection_patterns.yaml`)

- [ ] **REF-385**: Mermaid linkStyle Uses Edge Index Which Changes with Filtering
  - **Location:** `src/graph/formatters/mermaid_formatter.py:66, 148-164`
  - **Problem:** Line 66 uses `_get_edge_index()` to find edge position for styling, but if graph is filtered (e.g., by language or pattern), edge indices change. A circular edge might be at index 5 in full graph but index 2 in filtered graph, causing wrong edge to be styled red.
  - **Example:** Full graph has edges [A→B, B→C, C→D, C→A (circular), D→E]. After filtering to just [A,B,C], edges are [A→B, B→C, C→A]. Original index was 3, new index is 2.
  - **Impact:** Red circular styling applied to wrong edges in filtered graphs
  - **Fix:** Count edges as they're emitted instead of using global index, or track edges by (source, target) tuple

- [ ] **REF-386**: DOT Formatter DEFAULT_COLOR is Invalid - Should Be "#808080"
  - **Location:** `src/graph/formatters/dot_formatter.py:36`
  - **Problem:** Line 36 sets `DEFAULT_COLOR = "#gray"` but DOT/Graphviz doesn't recognize "#gray" as valid hex color (hex colors must be #RRGGBB or #RRGGBBAA). The `#` prefix indicates hex, but "gray" is a named color without `#`. This causes rendering issues or fallback to black.
  - **Impact:** Unknown language nodes appear black instead of gray
  - **Fix:** Change to `DEFAULT_COLOR = "gray"` (named color) OR `DEFAULT_COLOR = "#808080"` (hex gray)

- [ ] **REF-387**: Tag Statistics Not Tracked
  - **Location:** `src/tagging/tag_manager.py` (no usage tracking)
  - **Problem:** No visibility into tag usage: how many memories have each tag? Which tags are most/least used? Are auto-generated tags accurate?
  - **Impact:** Can't optimize tagging strategy or clean up unused tags
  - **Fix:** Add `get_tag_statistics()` method returning tag usage counts, confidence distributions, auto vs manual ratios

- [ ] **REF-388**: DOT Formatter DEFAULT_COLOR is Invalid - Should Be "#808080"
  - **Location:** `src/graph/formatters/dot_formatter.py:36`
  - **Problem:** Line 36 sets `DEFAULT_COLOR = "#gray"` but DOT/Graphviz doesn't recognize "#gray" as valid hex color (hex colors must be #RRGGBB or #RRGGBBAA). The `#` prefix indicates hex, but "gray" is a named color without `#`. This causes rendering issues or fallback to black.
  - **Impact:** Unknown language nodes appear black instead of gray
  - **Fix:** Change to `DEFAULT_COLOR = "gray"` (named color) OR `DEFAULT_COLOR = "#808080"` (hex gray)

- [ ] **REF-392**: filter_by_pattern Matches Against Both Full Path and Basename
  - **Location:** `src/graph/dependency_graph.py:248-250`
  - **Problem:** Filter matches pattern against both full file_path and `Path(file_path).name` (basename). For pattern `"*.py"`, this is fine, but for pattern `"src/*.py"`, matching against basename will include `/other/src/test.py` even though path doesn't match `src/*.py`. The OR logic is too permissive.
  - **Example:** Pattern `"src/*.py"` should match `/project/src/utils.py` but not `/other/src/utils.py`. Current code matches both because basename matches.
  - **Impact:** Filter includes more files than expected, confusing results
  - **Fix:** Document behavior OR only match basename for simple patterns (no `/`), full path for path-like patterns

- [ ] **REF-393**: Classifier Default Fallback Always Returns PROJECT_CONTEXT
  - **Location:** `src/memory/classifier.py:164-165`, `179-186`
  - **Problem:** When all scores are low (<0.3), classifier falls back to `_default_for_category()`. But for 3 out of 5 categories (FACT, WORKFLOW, CONTEXT), default is PROJECT_CONTEXT. This creates bias toward PROJECT_CONTEXT.
  - **Impact:** Ambiguous memories are over-classified as project context
  - **Fix:** Consider returning UNKNOWN context level or using uniform distribution when confidence is low

- [ ] **REF-394**: filter_by_pattern Matches Against Both Full Path and Basename
  - **Location:** `src/graph/dependency_graph.py:248-250`
  - **Problem:** Filter matches pattern against both full file_path and `Path(file_path).name` (basename). For pattern `"*.py"`, this is fine, but for pattern `"src/*.py"`, matching against basename will include `/other/src/test.py` even though path doesn't match `src/*.py`. The OR logic is too permissive.
  - **Example:** Pattern `"src/*.py"` should match `/project/src/utils.py` but not `/other/src/utils.py`. Current code matches both because basename matches.
  - **Impact:** Filter includes more files than expected, confusing results
  - **Fix:** Document behavior OR only match basename for simple patterns (no `/`), full path for path-like patterns

- [ ] **REF-395**: CallGraph Statistics Count Interfaces but Not Interface Methods
  - **Location:** `src/graph/call_graph.py:343-344`
  - **Problem:** `get_statistics()` counts total interfaces (line 343) and total implementations (344), but doesn't count total methods across implementations. This makes it hard to assess complexity of interface hierarchies.
  - **Impact:** Incomplete statistics for polymorphic codebases
  - **Fix:** Add `"total_interface_methods": sum(len(impl.methods) for impls in self.implementations.values() for impl in impls)` to stats dict

- [ ] **REF-396**: Tag Full Path Separator Hardcoded
  - **Location:** `src/tagging/tag_manager.py:102`, `src/tagging/models.py:40-42`
  - **Problem:** "/" separator is hardcoded throughout. If user wants to create tag named "react/hooks" as flat tag (not hierarchy), it's impossible.
  - **Impact:** Naming restrictions; potential conflicts with file path tags
  - **Fix:** Either:
    1. Add escaping mechanism ("react\/hooks" for literal)
    2. Use different separator (e.g., "::" for hierarchy)
    3. Document limitation clearly

- [ ] **REF-397**: CallGraph Statistics Count Interfaces but Not Interface Methods
  - **Location:** `src/graph/call_graph.py:343-344`
  - **Problem:** `get_statistics()` counts total interfaces (line 343) and total implementations (344), but doesn't count total methods across implementations. This makes it hard to assess complexity of interface hierarchies.
  - **Impact:** Incomplete statistics for polymorphic codebases
  - **Fix:** Add `"total_interface_methods": sum(len(impl.methods) for impls in self.implementations.values() for impl in impls)` to stats dict

- [ ] **REF-399**: MemoryService Methods Return Dict[str, Any] - Overly Generic
  - **Location:** `src/services/memory_service.py` - all public methods return `Dict[str, Any]`
  - **Problem:** Return type is too generic, callers can't rely on dict structure. Example: `store_memory()` returns `{"memory_id": str, "status": str, "context_level": str}` but this isn't enforced by types.
  - **Impact:** LOW - Reduced type safety, harder to refactor
  - **Fix:** Define Pydantic response models (e.g., `StoreMemoryResponse`, `RetrieveMemoriesResponse`)

- [ ] **REF-041**: Magic Number 1000 for History Limits
  - **Location:** `src/store/connection_pool.py:591`, `src/store/connection_pool_monitor.py:202-204`, `src/store/connection_pool_monitor.py:299`
  - **Problem:** Hardcoded limit `1000` appears in multiple places without explanation
  - **Fix:** Extract to named constant `MAX_HISTORY_SIZE = 1000` with comment explaining memory tradeoff

- [ ] **REF-049**: BM25 Tokenization Doesn't Handle Non-ASCII Characters
  - **Location:** `src/search/bm25.py:96`
  - **Problem:** Regex `[a-z0-9_]+` excludes non-ASCII (accented chars, emoji, CJK), which appear in code comments/strings
  - **Fix:** Update to `[\w]+` with re.UNICODE flag or `[a-z0-9_\u00C0-\uFFFF]+` to include Unicode word chars

- [ ] **REF-059**: Magic Numbers for Lifecycle Distribution Ideals
  - **Location:** `src/memory/health_scorer.py:79-84`
  - **Problem:** The IDEAL_DISTRIBUTION dictionary hardcodes percentages (60% ACTIVE, 25% RECENT, etc.) with no explanation of why these values are ideal. These ratios are domain-specific assumptions that may not apply to all use cases. A read-heavy system might prefer 80% ACTIVE, while a write-heavy system might prefer 40% ARCHIVED.
  - **Fix:** Make IDEAL_DISTRIBUTION configurable via ServerConfig: `health.ideal_distribution_percentages`. Document rationale for default values in comments.

- [ ] **REF-065**: Backup Config Serialization Drops notification_callback
  - **Location:** `src/backup/scheduler.py:329-346`
  - **Problem:** `save_config_to_file()` drops `notification_callback` field (line 344 omits it) without documenting why. User might expect callback to persist.
  - **Fix:** Add comment explaining callbacks can't be serialized, or add error if callback is set when saving

- [ ] **REF-067**: Archive Manifest Uses String for Estimated Restore Time
  - **Location:** `src/memory/archive_compressor.py:89`
  - **Problem:** Calculates `estimated_restore_time_seconds: max(5, compressed_size_mb / 2)` with simplistic formula that doesn't account for CPU speed, disk I/O, etc.
  - **Fix:** Either remove estimate (unreliable) or add disclaimer comment that it's rough heuristic for reference only

- [ ] **REF-077**: Mermaid Node IDs Limited to 26 Files (A-Z)
  - **Location:** `src/memory/graph_generator.py:429`
  - **Problem:** Line 429 generates node IDs as `chr(65 + i)` for i < 26, else `f"N{i}"`. This works but creates inconsistent ID format (A-Z for first 26, then N26, N27, etc). Also, comment or docstring should warn that very large graphs (>26 nodes) get numeric IDs.
  - **Impact:** Inconsistent node ID format in Mermaid output, potential confusion
  - **Fix:** Use consistent format like `f"N{i}"` for all nodes OR document the A-Z then numeric pattern

- [ ] **REF-079**: graph_generator.py Hardcodes "dependencies" as Graph Title Comment
  - **Location:** `src/memory/graph_generator.py:310, 424`
  - **Problem:** DOT output says `digraph dependencies {` and Mermaid has comment `graph LR` but no title. The `title` parameter from generate() is never passed to these format methods (only to JSON metadata). User's title is ignored for DOT/Mermaid.
  - **Impact:** All DOT/Mermaid graphs have generic title, not user-specified title
  - **Fix:** Pass title to `_to_dot()` and `_to_mermaid()`, add as comment or graph label

- [ ] **REF-267**: Empty String Split Creates Single-Element List
  - **Location:** Various `.split()` calls assume multiple elements
  - **Problem:** `"".split("x")` returns `[""]`, not `[]`. Code checking `if len(parts) > 1` will be false for empty string.
  - **Impact:** Minor logic errors on empty input
  - **Fix:** Check for empty string before split: `if not text: return default; parts = text.split(...)`

- [ ] **REF-270**: Empty String Split Creates Single-Element List
  - **Location:** Various `.split()` calls assume multiple elements
  - **Problem:** `"".split("x")` returns `[""]`, not `[]`. Code checking `if len(parts) > 1` will be false for empty string.
  - **Impact:** Minor logic errors on empty input
  - **Fix:** Check for empty string before split: `if not text: return default; parts = text.split(...)`

- [ ] **REF-291**: Unused Metrics Collector Parameter in Multiple Services
  - **Location:** `src/services/memory_service.py:521-528`, `src/services/code_indexing_service.py:394-401`, `src/services/cross_project_service.py:169-176`
  - **Problem:** Services check `if self.metrics_collector` and log queries, but this pattern is duplicated 3 times. If metrics_collector interface changes, need to update 3+ places.
  - **Fix:** Create MetricsCollectorMixin or decorator for automatic metric logging. Reduces duplication from ~20 lines to ~3.

- [ ] **REF-292**: Unused Metrics Collector Parameter in Multiple Services
  - **Location:** `src/services/memory_service.py:521-528`, `src/services/code_indexing_service.py:394-401`, `src/services/cross_project_service.py:169-176`
  - **Problem:** Services check `if self.metrics_collector` and log queries, but this pattern is duplicated 3 times. If metrics_collector interface changes, need to update 3+ places.
  - **Fix:** Create MetricsCollectorMixin or decorator for automatic metric logging. Reduces duplication from ~20 lines to ~3.

- [ ] **REF-295**: Missing Logging in QueryService State Transitions
  - **Location:** `src/services/query_service.py:69-139`
  - **Problem:** start_conversation_session() and end_conversation_session() have minimal logging (only success case). Missing logs for: session already exists, session not found, cleanup errors.
  - **Fix:** Add structured logging for all state transitions. Include session_id, duration, query_count in end_session log.

- [ ] **REF-296**: Missing Logging in QueryService State Transitions
  - **Location:** `src/services/query_service.py:69-139`
  - **Problem:** start_conversation_session() and end_conversation_session() have minimal logging (only success case). Missing logs for: session already exists, session not found, cleanup errors.
  - **Fix:** Add structured logging for all state transitions. Include session_id, duration, query_count in end_session log.

- [ ] **REF-302**: Magic Number for Git Worktrees Exclusion Pattern
  - **Location:** `src/memory/incremental_indexer.py:428`
  - **Problem:** The EXCLUDED_DIRS set includes ".worktrees" with a comment "Git worktrees for parallel development". This is project-specific knowledge hardcoded in the indexer. Users with different worktree setups (e.g., `_worktrees/`, `tmp/worktrees/`) won't get proper filtering.
  - **Fix:** Make EXCLUDED_DIRS configurable via ServerConfig. Add `indexing.excluded_dirs` config option with defaults.

- [ ] **REF-313**: Magic Number 10 for Top Results Display
  - **Location:** `src/cli/index_command.py:68-71` shows first 10 failed files, `src/cli/prune_command.py:101-103` shows first 10 deleted IDs
  - **Problem:** Hardcoded `[:10]` appears in multiple places without explanation. If user has 500 errors, only seeing 10 may hide important patterns.
  - **Fix:** Extract to constant `MAX_DISPLAYED_ITEMS = 10` with comment, or add --show-all flag

- [ ] **REF-341**: Magic Numbers for Lifecycle Distribution Ideals
  - **Location:** `src/memory/health_scorer.py:79-84`
  - **Problem:** The IDEAL_DISTRIBUTION dictionary hardcodes percentages (60% ACTIVE, 25% RECENT, etc.) with no explanation of why these values are ideal. These ratios are domain-specific assumptions that may not apply to all use cases. A read-heavy system might prefer 80% ACTIVE, while a write-heavy system might prefer 40% ARCHIVED.
  - **Fix:** Make IDEAL_DISTRIBUTION configurable via ServerConfig: `health.ideal_distribution_percentages`. Document rationale for default values in comments.

- [ ] **REF-347**: File Watcher Uses mtime Then Hash for Change Detection
  - **Location:** `src/memory/file_watcher.py:129-165`
  - **Problem:** `_has_changed()` first checks mtime (quick), then computes SHA256 hash (expensive) for verification. This is correct and efficient, but comment at line 133-134 suggests this is for "conflict resolution" which is misleading. The hash is actually for catching false watchdog events (editor temp files, etc.), not conflicts.
  - **Fix:** Update comment to clarify: "Step 3: Verify with hash to catch watchdog false positives (temp files, touch without content change)"

- [ ] **REF-348**: File Watcher Uses mtime Then Hash for Change Detection
  - **Location:** `src/memory/file_watcher.py:129-165`
  - **Problem:** `_has_changed()` first checks mtime (quick), then computes SHA256 hash (expensive) for verification. This is correct and efficient, but comment at line 133-134 suggests this is for "conflict resolution" which is misleading. The hash is actually for catching false watchdog events (editor temp files, etc.), not conflicts.
  - **Fix:** Update comment to clarify: "Step 3: Verify with hash to catch watchdog false positives (temp files, touch without content change)"

- [ ] **REF-363**: Comment-Only Test Documentation (No Docstrings in Some Files)
  - **Location:** Multiple test files use `# Test X` comments instead of docstrings
  - **Problem:** Some test functions have docstrings, others have comments, inconsistent
  - **Impact:** Harder to generate test documentation, pytest output less informative
  - **Fix:** Standardize on docstrings for all test functions

- [ ] **REF-364**: Comment-Only Test Documentation (No Docstrings in Some Files)
  - **Location:** Multiple test files use `# Test X` comments instead of docstrings
  - **Problem:** Some test functions have docstrings, others have comments, inconsistent
  - **Impact:** Harder to generate test documentation, pytest output less informative
  - **Fix:** Standardize on docstrings for all test functions

- [ ] **REF-365**: Backup Config Serialization Drops notification_callback
  - **Location:** `src/backup/scheduler.py:329-346`
  - **Problem:** `save_config_to_file()` drops `notification_callback` field (line 344 omits it) without documenting why. User might expect callback to persist.
  - **Fix:** Add comment explaining callbacks can't be serialized, or add error if callback is set when saving

- [ ] **REF-371**: Archive Manifest Uses String for Estimated Restore Time
  - **Location:** `src/memory/archive_compressor.py:89`
  - **Problem:** Calculates `estimated_restore_time_seconds: max(5, compressed_size_mb / 2)` with simplistic formula that doesn't account for CPU speed, disk I/O, etc.
  - **Fix:** Either remove estimate (unreliable) or add disclaimer comment that it's rough heuristic for reference only

- [ ] **REF-389**: JSON Formatter Silently Omits Metadata for Nodes Without Unit/Size
  - **Location:** `src/graph/formatters/json_formatter.py:101-107`
  - **Problem:** When `include_metadata=True`, the code only adds unit_count/file_size if they're > 0. For a file with 0 units and 0 bytes, metadata is completely omitted from JSON, making it indistinguishable from `include_metadata=False`. This inconsistency makes client-side parsing harder.
  - **Impact:** Inconsistent JSON schema - some nodes have metadata fields, others don't
  - **Fix:** Always include fields when `include_metadata=True`, use explicit 0 values OR add comment documenting intentional omission

- [ ] **REF-391**: JSON Formatter Silently Omits Metadata for Nodes Without Unit/Size
  - **Location:** `src/graph/formatters/json_formatter.py:101-107`
  - **Problem:** When `include_metadata=True`, the code only adds unit_count/file_size if they're > 0. For a file with 0 units and 0 bytes, metadata is completely omitted from JSON, making it indistinguishable from `include_metadata=False`. This inconsistency makes client-side parsing harder.
  - **Impact:** Inconsistent JSON schema - some nodes have metadata fields, others don't
  - **Fix:** Always include fields when `include_metadata=True`, use explicit 0 values OR add comment documenting intentional omission

## Performance (PERF-*)

- [ ] **PERF-12**: Missing await in Embedding Cache Operations
  - **Location:** `src/core/server.py:4754-4762` (_get_embedding method)
  - **Problem:** Cache get/set operations use `await` but EmbeddingCache may not be fully async
  - **Impact:** Potential blocking on cache I/O in async context
  - **Fix:** Verify EmbeddingCache is truly async, add proper async/await or use run_in_executor

- [ ] **PERF-19**: Embedding Cache Uses Synchronous SQLite in Async Context
  - **Location:** `src/embeddings/cache.py:127-129` wraps all DB ops in `asyncio.to_thread()`
  - **Problem:** While correct for async compatibility, creates thread overhead on every cache hit (10-20μs per thread spawn)
  - **Impact:** High cache hit rate (95%+) means most embedding requests pay thread spawn cost unnecessarily
  - **Fix:** Consider using aiosqlite for native async SQLite, or batch cache operations to amortize thread cost

- [ ] **PERF-001**: Inefficient Project Loop in CrossProjectService.search_all_projects
  - **Location:** `src/services/cross_project_service.py:124-159`
  - **Problem:** Searches opted-in projects sequentially in a for loop. For 10 projects, this could take 10x as long as searching 1 project. Should use concurrent search with asyncio.gather().
  - **Fix:** Collect search tasks in list, use `results = await asyncio.gather(*tasks, return_exceptions=True)`. Handle exceptions per-project.

- [ ] **PERF-008**: Connection Health Check Creates New Client on Recycling Failure
  - **Location:** `src/store/connection_pool.py:276-278`
  - **Problem:** When recycled connection fails health check, creates new connection synchronously during acquire, blocking caller
  - **Fix:** Consider background pre-warming of replacement connections or fail-fast with retry from pool

- [ ] **PERF-009**: Scroll Loop Inefficiency - No Batch Size Optimization
  - **Location:** All scroll loops use fixed `limit=100` regardless of total expected results
  - **Problem:** Small queries (limit=10) still fetch in batches of 100, wasting bandwidth
  - **Fix:** Use adaptive batch sizing: `batch_size = min(100, max(limit, 10))`

- [ ] **PERF-010**: Unnecessary List Reversal in get_metrics_history
  - **Location:** `src/store/connection_pool_monitor.py:330`
  - **Problem:** `list(reversed(self._metrics_history[-limit:]))` creates two intermediate lists
  - **Fix:** Use slice notation: `self._metrics_history[-limit:][::-1]` (single operation)

- [ ] **PERF-011**: BM25 Discards Single-Character Tokens Common in Code
  - **Location:** `src/search/bm25.py:99`
  - **Problem:** Filters out `len(t) < 2`, removing single-char identifiers like "x", "y", "i" common in math/loop code
  - **Fix:** Add configuration option `min_token_length` with default 1 for code search; update to `[t for t in tokens if len(t) >= self.min_token_length]`

- [ ] **PERF-012**: Redundant File Resolution in Cleanup Operations
  - **Location:** `src/memory/incremental_indexer.py:705-707`
  - **Problem:** In `_cleanup_stale_entries()`, for each indexed file, code calls `file_path.relative_to(dir_path)` inside a try/except to check if file is in directory. This is expensive for 1000+ files. The `current_file_paths` set (line 695) already contains resolved absolute paths - just check if file starts with dir_path string.
  - **Fix:** Replace `file_path.relative_to(dir_path)` with `file_path_str.startswith(str(dir_path.resolve()))` for 10x speedup

- [ ] **PERF-013**: Unused Semaphore Value Calculation
  - **Location:** `src/memory/incremental_indexer.py:464`
  - **Problem:** Creates `asyncio.Semaphore(max_concurrent)` to limit concurrency, but the semaphore value is never checked or monitored. If max_concurrent=4 but system can only handle 2 concurrent operations, there's no backpressure mechanism or resource monitoring.
  - **Fix:** Add optional `adaptive_concurrency` mode that monitors memory/CPU usage and adjusts semaphore limit dynamically

- [ ] **PERF-13**: Parallel Generator Initializes Executor Even for Small Batches
  - **Location:** `src/embeddings/parallel_generator.py:240-260`
  - **Problem:** `initialize()` creates ProcessPoolExecutor upfront, even if workload is too small to benefit
  - **Impact:** Wasted resources (process pool overhead) for applications that only use small batches
  - **Fix:** Lazy-initialize executor on first large batch (>= `parallel_threshold`)

- [ ] **PERF-014**: O(N²) Duplicate Pair Extraction Without Early Exit
  - **Location:** `src/analysis/code_duplicate_detector.py:250-262`
  - **Problem:** `get_duplicate_pairs()` checks upper triangle of similarity matrix (O(N²)) but doesn't stop early when max_pairs limit is reached. For 10,000 units with threshold=0.5 (many matches), this creates hundreds of thousands of DuplicatePair objects, consuming gigabytes of RAM, even if caller only needs top 100 pairs.
  - **Fix:** Add `max_pairs: Optional[int] = None` parameter and break early after reaching limit. Since pairs are sorted descending, can use heap to maintain top-K pairs during iteration.

- [ ] **PERF-14**: ConnectionPoolMonitor Uses Sequential Notify Instead of Gather
  - **Location:** `src/store/connection_pool_monitor.py:306-311`
  - **Problem:** `_raise_alert()` iterates through backends and awaits each notification sequentially (line 309). If there are multiple backends (console, log, callback, etc.), a slow backend blocks all others. Should use `asyncio.gather()` for parallel notification.
  - **Fix:** Collect tasks in list, use `await asyncio.gather(*notify_tasks, return_exceptions=True)`

- [ ] **PERF-015**: Duplicate Clustering Performs Redundant Similarity Lookups
  - **Location:** `src/analysis/code_duplicate_detector.py:356-383`
  - **Problem:** The inner loop (lines 378-382) accesses `similarity_matrix[idx_i][idx_j]` for each pair in cluster to calculate average similarity. For a cluster of size 100, this performs 4,950 matrix accesses (100 choose 2). Since the matrix is symmetric, could cache or use matrix slicing for batch access.
  - **Fix:** Use vectorized NumPy operations: extract cluster submatrix with `cluster_similarities = similarity_matrix[np.ix_(indices, indices)]`, then compute mean of upper triangle

- [ ] **PERF-15**: ConnectionPoolMonitor Uses Sequential Notify Instead of Gather
  - **Location:** `src/store/connection_pool_monitor.py:306-311`
  - **Problem:** `_raise_alert()` iterates through backends and awaits each notification sequentially (line 309). If there are multiple backends (console, log, callback, etc.), a slow backend blocks all others. Should use `asyncio.gather()` for parallel notification.
  - **Fix:** Collect tasks in list, use `await asyncio.gather(*notify_tasks, return_exceptions=True)`

- [ ] **PERF-016**: Regex Recompilation on Every Function Call
  - **Location:** `src/analysis/complexity_analyzer.py:135-137`, and 20+ other locations in analyzers
  - **Problem:** All regex patterns are defined as raw strings in loops (e.g., `r'\bif\b'`) and passed to `re.findall()` or `re.search()`, which compiles the regex on every call. For analyzing 10,000 functions, this recompiles the same patterns 10,000 times.
  - **Fix:** Pre-compile patterns as module-level constants: `IF_PATTERN = re.compile(r'\bif\b')`, then use `IF_PATTERN.findall(content)`

- [ ] **PERF-16**: Inefficient File Extension Matching in Directory Indexing
  - **Location:** `src/memory/incremental_indexer.py:418-421`
  - **Problem:** For each supported extension, calls `dir_path.glob(f"{pattern}{ext}")` separately, then concatenates results. For 20 supported extensions, this performs 20 separate filesystem traversals. For large directories (10,000+ files), this is extremely slow.
  - **Fix:** Use single glob pattern with set filtering: `all_files = dir_path.glob(pattern); files = [f for f in all_files if f.suffix in SUPPORTED_EXTENSIONS]`. Reduces 20 traversals to 1.

- [ ] **PERF-017**: Redundant Call to len() in Median Calculation
  - **Location:** `src/analysis/importance_scorer.py:360-364`
  - **Problem:** Line 360 calls `n = len(sorted_scores)`, then line 361-364 checks `if n % 2 == 1` to decide median calculation. But the `sorted_scores` list was already created on line 357 with a length known at that point. The `n` variable is used only for median calculation, so this is a micro-optimization opportunity.
  - **Fix:** Inline: `if len(sorted_scores) % 2 == 1: median = sorted_scores[len(sorted_scores) // 2]` (or keep as-is for readability)

- [ ] **PERF-17**: Export Loads All Embeddings Into Memory
  - **Location:** `src/backup/exporter.py:150-153`
  - **Problem:** For large exports (100K+ memories), line 151 `embeddings = np.array([emb for m, emb in memory_embeddings])` loads all 768-dim vectors into single array, consuming gigabytes of RAM
  - **Fix:** Stream embeddings to npz file in chunks using np.savez with append mode or split into multiple files

- [ ] **PERF-18**: Export Loads All Embeddings Into Memory
  - **Location:** `src/backup/exporter.py:150-153`
  - **Problem:** For large exports (100K+ memories), line 151 `embeddings = np.array([emb for m, emb in memory_embeddings])` loads all 768-dim vectors into single array, consuming gigabytes of RAM
  - **Fix:** Stream embeddings to npz file in chunks using np.savez with append mode or split into multiple files

- [ ] **PERF-20**: Scroll Loop Fetches Vectors Unnecessarily
  - **Location:** `src/backup/exporter.py:359` sets `with_vectors=True` even for non-embedding exports
  - **Problem:** When `include_embeddings=False`, still fetches vectors from Qdrant (expensive for large collections)
  - **Fix:** Conditionally set `with_vectors=include_embeddings` parameter

- [ ] **PERF-21**: Scroll Loop Fetches Vectors Unnecessarily
  - **Location:** `src/backup/exporter.py:359` sets `with_vectors=True` even for non-embedding exports
  - **Problem:** When `include_embeddings=False`, still fetches vectors from Qdrant (expensive for large collections)
  - **Fix:** Conditionally set `with_vectors=include_embeddings` parameter

- [ ] **PERF-25**: Redundant Store Initialization in project_command
  - **Location:** `src/cli/project_command.py:32` and `project_command.py:94` both create and initialize MemoryRAGServer
  - **Problem:** Each project subcommand initializes a new server instance. If user runs `project list && project stats myproject`, server initialized twice. Server initialization includes Qdrant connection, embedding model load - expensive.
  - **Fix:** Cache server instance at module level or pass through command context

- [ ] **PERF-28**: O(N²) Duplicate Pair Extraction Without Early Exit
  - **Location:** `src/analysis/code_duplicate_detector.py:250-262`
  - **Problem:** `get_duplicate_pairs()` checks upper triangle of similarity matrix (O(N²)) but doesn't stop early when max_pairs limit is reached. For 10,000 units with threshold=0.5 (many matches), this creates hundreds of thousands of DuplicatePair objects, consuming gigabytes of RAM, even if caller only needs top 100 pairs.
  - **Fix:** Add `max_pairs: Optional[int] = None` parameter and break early after reaching limit. Since pairs are sorted descending, can use heap to maintain top-K pairs during iteration.

- [ ] **PERF-30**: filter_by_depth Creates New Graph with Deep Copy of Nodes
  - **Location:** `src/graph/dependency_graph.py:224-227`
  - **Problem:** Lines 225-227 add nodes to filtered graph by calling `filtered.add_node(self.nodes[node_path])`. This doesn't deep copy the GraphNode object, but if GraphNode is later modified, the filtered graph shares references. For read-only use this is fine, but for mutable operations it's risky.
  - **Impact:** Potential unexpected mutation if filtered graph nodes are modified
  - **Fix:** Document that filtered graphs share node references OR deep copy nodes: `filtered.add_node(dataclasses.replace(self.nodes[node_path]))`

- [ ] **PERF-31**: filter_by_depth Creates New Graph with Deep Copy of Nodes
  - **Location:** `src/graph/dependency_graph.py:224-227`
  - **Problem:** Lines 225-227 add nodes to filtered graph by calling `filtered.add_node(self.nodes[node_path])`. This doesn't deep copy the GraphNode object, but if GraphNode is later modified, the filtered graph shares references. For read-only use this is fine, but for mutable operations it's risky.
  - **Impact:** Potential unexpected mutation if filtered graph nodes are modified
  - **Fix:** Document that filtered graphs share node references OR deep copy nodes: `filtered.add_node(dataclasses.replace(self.nodes[node_path]))`

- [ ] **PERF-33**: Duplicate Clustering Performs Redundant Similarity Lookups
  - **Location:** `src/analysis/code_duplicate_detector.py:356-383`
  - **Problem:** The inner loop (lines 378-382) accesses `similarity_matrix[idx_i][idx_j]` for each pair in cluster to calculate average similarity. For a cluster of size 100, this performs 4,950 matrix accesses (100 choose 2). Since the matrix is symmetric, could cache or use matrix slicing for batch access.
  - **Fix:** Use vectorized NumPy operations: extract cluster submatrix with `cluster_similarities = similarity_matrix[np.ix_(indices, indices)]`, then compute mean of upper triangle

- [ ] **PERF-22**: Cycle Detection Creates New Path List on Every Recursive Call
  - **Location:** `src/graph/dependency_graph.py:157, 170`
  - **Problem:** DFS passes `path` list by reference and mutates it (append line 157, pop line 170), which is correct. However, if there are many cycles, the path list is repeatedly grown/shrunk. Consider pre-allocating or using deque for O(1) append/pop.
  - **Impact:** Minor performance cost for graphs with hundreds of cycles
  - **Fix:** Change `path: List[str]` to `path: collections.deque` for O(1) operations

- [ ] **PERF-23**: Cycle Detection Creates New Path List on Every Recursive Call
  - **Location:** `src/graph/dependency_graph.py:157, 170`
  - **Problem:** DFS passes `path` list by reference and mutates it (append line 157, pop line 170), which is correct. However, if there are many cycles, the path list is repeatedly grown/shrunk. Consider pre-allocating or using deque for O(1) append/pop.
  - **Impact:** Minor performance cost for graphs with hundreds of cycles
  - **Fix:** Change `path: List[str]` to `path: collections.deque` for O(1) operations

- [ ] **PERF-24**: No Pagination in Remediation Action Execution
  - **Location:** `src/monitoring/remediation.py:256-285`, `src/monitoring/remediation.py:337-365`
  - **Problem:** The `_prune_stale_memories()` and `_cleanup_old_sessions()` methods (and others) process ALL candidates in a single loop without pagination. If there are 50,000 STALE memories, this creates a massive transaction and holds a database lock for minutes. The comment at line 270-271 says "Would actually delete here" with a placeholder, suggesting real implementation will use `store.delete_by_lifecycle()` which might not have pagination either.
  - **Fix:** Add batch processing: `for i in range(0, len(candidates), 1000): batch = candidates[i:i+1000]; await self.store.delete_batch(batch)`. Commit after each batch to reduce lock duration.

- [ ] **PERF-26**: Unnecessary String Formatting in Logger Calls Before Exception Handling
  - **Location:** Throughout codebase - `logger.error(f"Failed to X: {e}")` before checking if logging is enabled
  - **Problem:** Python evaluates f-strings before passing to logger, even if log level is INFO and error logs are disabled. This wastes CPU cycles formatting strings that are never logged. In tight loops (e.g., indexing 10K files), this adds up.
  - **Fix:** Use lazy logging: `logger.error("Failed to X: %s", e)` with %-formatting. Logger only formats if level is enabled. Python logging best practice.

- [ ] **PERF-27**: Unnecessary String Formatting in Logger Calls Before Exception Handling
  - **Location:** Throughout codebase - `logger.error(f"Failed to X: {e}")` before checking if logging is enabled
  - **Problem:** Python evaluates f-strings before passing to logger, even if log level is INFO and error logs are disabled. This wastes CPU cycles formatting strings that are never logged. In tight loops (e.g., indexing 10K files), this adds up.
  - **Fix:** Use lazy logging: `logger.error("Failed to X: %s", e)` with %-formatting. Logger only formats if level is enabled. Python logging best practice.

- [ ] **PERF-29**: No Pagination in Remediation Action Execution
  - **Location:** `src/monitoring/remediation.py:256-285`, `src/monitoring/remediation.py:337-365`
  - **Problem:** The `_prune_stale_memories()` and `_cleanup_old_sessions()` methods (and others) process ALL candidates in a single loop without pagination. If there are 50,000 STALE memories, this creates a massive transaction and holds a database lock for minutes. The comment at line 270-271 says "Would actually delete here" with a placeholder, suggesting real implementation will use `store.delete_by_lifecycle()` which might not have pagination either.
  - **Fix:** Add batch processing: `for i in range(0, len(candidates), 1000): batch = candidates[i:i+1000]; await self.store.delete_batch(batch)`. Commit after each batch to reduce lock duration.

- [ ] **PERF-32**: Duplicate Detection Has O(N²) Complexity
  - **Location:** `src/memory/health_scorer.py:259-313`
  - **Problem:** The `_calculate_duplicate_rate()` method iterates through all memories and builds a `content_map` dictionary to detect exact duplicates (lines 291-306). For N memories, this is O(N) which is fine. However, the comment at lines 263-268 suggests the INTENDED implementation is pairwise similarity checks, which would be O(N²). If anyone implements the full version without optimization, it could take hours for 10,000+ memories. The current implementation only detects exact duplicates (case-insensitive), missing near-duplicates.
  - **Fix:** Document that semantic duplicate detection is NOT implemented (only exact matches). Add TODO for LSH (Locality-Sensitive Hashing) based approximate duplicate detection which is O(N).

- [ ] **PERF-34**: Duplicate Detection Has O(N^2) Complexity
  - **Location:** `src/memory/health_scorer.py:259-313`
  - **Problem:** The `_calculate_duplicate_rate()` method iterates through all memories and builds a `content_map` dictionary to detect exact duplicates (lines 291-306). For N memories, this is O(N) which is fine. However, the comment at lines 263-268 suggests the INTENDED implementation is pairwise similarity checks, which would be O(N^2). If anyone implements the full version without optimization, it could take hours for 10,000+ memories. The current implementation only detects exact duplicates (case-insensitive), missing near-duplicates.
  - **Fix:** Document that semantic duplicate detection is NOT implemented (only exact matches). Add TODO for LSH (Locality-Sensitive Hashing) based approximate duplicate detection which is O(N).

## Testing (TEST-*)

- [ ] **TEST-007**: Increase Test Coverage to 80%+ (~2-3 months) 🔥🔥
  - **Progress:** Phase 1 critical modules complete (2025-11-29)
  - **Completed:**

- [ ] **TEST-036**: No Cleanup in 30+ Database/File Fixtures (Resource Leaks)
  - **Location:** Tests using tempfile, sqlite, file watchers without proper cleanup
  - **Problem:** 
    - `test_usage_pattern_tracker.py`: 12 tests manually call `conn.close()` instead of fixture cleanup
    - File watchers in tests may not stop properly on test failure
    - Temp directories created without context managers in some tests
  - **Impact:** Resource leaks in test suite. Test failures leave garbage. CI runner disk fills up.
  - **Fix:** Use pytest fixtures with yield, context managers, or addFinalizer for all resource cleanup

- [ ] **TEST-039**: Heavy Mock Usage Without Integration Tests (4670 Mock Instances)
  - **Location:** 4670 `mock` or `Mock` references across test suite
  - **Problem:** 
    - Unit tests extensively mock dependencies (good for isolation)
    - But only 37 integration tests vs 165+ unit tests
    - Critical paths like store→indexer→search are mostly tested with mocks
  - **Impact:** Mocks drift from reality. Integration bugs slip through.
  - **Fix:** Add integration tests for each critical workflow, reduce mocking in "integration" tests

- [ ] **TEST-031**: 79+ Skipped Tests Never Re-enabled (Validation Theater)
  - **Location:** Multiple files with `@pytest.mark.skip` and `pytest.skip()`
  - **Problem:** Found 79+ skipped tests across the suite. Key examples:
    - `test_kotlin_parsing.py`: 262 lines, all tests skipped (Kotlin not supported by parser)
    - `test_swift_parsing.py`: 189 lines, all tests skipped (Swift not supported by parser)
    - `test_services/test_cross_project_service.py`: 12/12 tests skipped (MultiRepositorySearcher not implemented)
    - `test_services/test_health_service.py`: 3 tests skipped (DashboardServer not available)
    - `test_auto_indexing_service.py`: Test skipped (auto_index_enabled config not implemented)
    - `test_index_codebase_initialization.py`: Test skipped (incorrect mock setup)
  - **Impact:** These skipped tests create illusion of comprehensive coverage while testing nothing. They rot over time as code changes.
  - **Fix:** Add TODO tickets for each skip reason, set timeline for implementation or deletion. Mark skipped tests with issue numbers.

- [ ] **TEST-032**: Entire Test File Has Only Two `assert True` Statements
  - **Location:** `tests/unit/test_server_extended.py:471,592`
  - **Problem:** File has extensive setup for code search tests but only two assertions are literal `assert True` (lines 471, 592). This is validation theater - tests that appear to verify behavior but actually verify nothing.
  - **Impact:** False confidence. Tests pass even if code is completely broken.
  - **Fix:** Add real assertions or delete the tests

- [ ] **TEST-037**: Polling Loops Without Timeouts in Test Helpers
  - **Location:** `tests/unit/test_background_indexer.py:28-47` (wait_for_job_status helper)
  - **Problem:** Helper function uses `while True` loop with timeout check, but polls every 10ms. If job never reaches status, test hangs until timeout (default 5s). This pattern appears in multiple test files.
  - **Impact:** Slow tests, timeout failures hide real bugs
  - **Fix:** Use pytest-timeout plugin, reduce polling interval to 100ms, add debug logging for timeout failures

- [ ] **TEST-040**: 61 Parametrized Tests Only (Missed Opportunities)
  - **Location:** Only 61 uses of `@pytest.mark.parametrize` across 202 test files
  - **Problem:** Many test files have repetitive tests with only input data changing:
    - `test_refinement_advisor.py`: 11 separate test functions for different result counts (should be parameterized)
    - `test_spelling_suggester.py`: 7 tests with similar patterns
    - `test_ragignore_manager.py`: 22 tests, many test pattern validation with different inputs
  - **Impact:** Verbose test suite, harder to add new test cases
  - **Fix:** Identify test patterns and convert to parameterized tests

- [ ] **TEST-041**: Exception Testing Without Message Validation (Many pytest.raises)
  - **Location:** Tests using `with pytest.raises(SomeError):` without match parameter
  - **Problem:** Tests verify exception type but not message. Examples in:
    - `test_store/test_connection_pool.py`: 5 validation tests check exception type only
    - Many MCP error handling tests don't validate error messages
  - **Impact:** Tests pass even if error messages are unhelpful or wrong
  - **Fix:** Add `match=` parameter to pytest.raises to validate error messages

- [ ] **TEST-006**: Comprehensive E2E Manual Testing (~10-15 hours) 🔄 **IN PROGRESS**

- [ ] **TEST-029**: No Tests for Duplicate Method Shadowing
  - **Location:** Test suite (missing coverage)
  - **Problem:** Triple definitions of export/import_memories went undetected
  - **Impact:** Method shadowing bugs can reach production
  - **Fix:** Add tests that verify only one definition exists per method name using AST inspection

- [ ] **TEST-030**: Manual Test File Has Zero Assertions (435 Lines of Dead Code)
  - **Location:** `tests/manual/test_all_features.py` (435 lines, 0 assertions)
  - **Problem:** This file contains a `FeatureTester` class with extensive feature testing code (code search, memory CRUD, indexing, analytics, etc.) but uses `print()` statements and manual verification instead of assertions. Tests never fail programmatically - they require human inspection of output. This is not a test, it's a demo script masquerading as a test.
  - **Impact:** False confidence in test coverage metrics. File is counted in test suite but provides zero automated verification.
  - **Fix:** Either (1) convert to real assertions and move to integration/, or (2) move to `scripts/` and remove from test suite, or (3) delete if obsolete

- [ ] **TEST-033**: Excessive Fixture Complexity Creates Maintenance Burden
  - **Location:** `tests/conftest.py` (630+ lines), multiple conftest files
  - **Problem:** 
    - Session-scoped fixtures mix concerns (embedding mocks, Qdrant pooling, auto-indexing disable)
    - Mock embedding generator in conftest uses complex hash-based embeddings (lines 160-209)
    - Collection pooling logic is fragile (session-scoped `unique_qdrant_collection`)
    - 6 different conftest files with overlapping responsibilities
  - **Impact:** Hard to understand what any test is actually testing. Changes to fixtures break unrelated tests.
  - **Fix:** Document fixture dependencies, split into focused conftest files by concern, consider factory patterns

- [ ] **TEST-034**: Weak Assertions Provide False Confidence (359 Instances)
  - **Location:** 359 occurrences of `assert ... is not None` with no follow-up checks
  - **Problem:** Tests check object existence but not correctness. Examples:
    - Retrieve memory → assert result is not None → done (doesn't check content)
    - Index files → assert job is not None → done (doesn't check files were actually indexed)
    - Parse code → assert units is not None → done (doesn't check parsing correctness)
  - **Impact:** Tests pass when code returns garbage, as long as it's not None
  - **Fix:** Follow `is not None` with specific attribute/value checks

- [ ] **TEST-038**: Missing Parametrization Opportunities (5 Language Files)
  - **Location:** 5 separate parsing test files when one parameterized file would suffice
  - **Problem:** 
    - `test_cpp_parsing.py`, `test_php_parsing.py`, `test_ruby_parsing.py`, `test_kotlin_parsing.py`, `test_swift_parsing.py`
    - Each follows identical test pattern (file recognition, class extraction, function extraction, edge cases)
    - Only Ruby is consolidated into `test_language_parsing_parameterized.py` (per TEST-029)
  - **Impact:** Code duplication, inconsistent test coverage across languages, harder to add new languages
  - **Fix:** Consolidate all language parsing tests into parameterized suite like TEST-029 did for Ruby

- [ ] **TEST-042**: Test File Organization Issues
  - **Location:** `tests/unit/test_services/`, `tests/unit/test_store/` vs `tests/unit/store/`
  - **Problem:** 
    - Two separate test_store directories (`test_store/` and `store/`)
    - `test_services/` has 5 test files, 4 of which have skipped tests
    - Mixing graph tests in `tests/unit/graph/` vs other unit tests
  - **Impact:** Hard to find tests, unclear structure
  - **Fix:** Consolidate test directories to match src/ structure

- [ ] **TEST-035**: Language Parsing Tests for Unsupported Languages (451+ Dead Lines)
  - **Location:** 
    - `test_kotlin_parsing.py`: 262 lines (Kotlin not supported)
    - `test_swift_parsing.py`: 189 lines (Swift not supported)
  - **Problem:** Comprehensive test suites exist for languages the parser doesn't support. All tests are skipped. Tests use inconsistent assertion styles (accessing dict keys vs attributes) suggesting they were written without running.
  - **Impact:** Dead code maintenance burden. False coverage metrics.
  - **Fix:** Delete these files or move to `tests/future/` directory with clear timeline for support

## Documentation (DOC-*)

- [ ] **DOC-011**: Missing Docstrings for Private Helper Methods
  - **Location:** `src/core/server.py` - methods starting with `_`
  - **Examples:** `_classify_context_level`, `_parse_relative_date`, `_get_embedding`
  - **Impact:** Difficult for maintainers to understand internal logic
  - **Fix:** Add comprehensive docstrings following existing pattern

- [ ] **DOC-012**: get_by_id() Docstring Missing Resource Leak Warning
  - **Location:** `src/store/base.py:120-133`
  - **Problem:** Abstract method docstring says "Raises: StorageError: If retrieval operation fails" but doesn't mention that implementations MUST release clients on early returns. The Qdrant implementation previously had this issue (fixed in BUG-063), but the base class should document this requirement to prevent future regressions.
  - **Expected:** Docstring should say "Note: Implementations must ensure proper resource cleanup even on early returns (e.g., when memory not found)"
  - **Fix:** Update base.py docstring to include resource cleanup requirement

- [ ] **DOC-019**: Misleading Variable Name in _extract_keywords()
  - **Location:** `src/tagging/auto_tagger.py:286-358`
  - **Problem:** Function is named `_extract_keywords()` but actually extracts "high-frequency words" and converts them to tags. The `min_word_length` parameter defaults to 4, but the docstring says "Extract high-frequency keywords as tags" without explaining that it's using TF (term frequency) not TF-IDF, which would be more accurate for keyword extraction.
  - **Expected:** Rename to `_extract_frequent_words()` or update docstring to say "Extract high-frequency words (simple term frequency, no IDF weighting)"
  - **Fix:** Add clarifying comment at line 287 explaining this is naive TF-based extraction

- [ ] **DOC-022**: Timeout Values Not Documented in Configuration
  - **Location:** `src/config.py` (inferred)
  - **Problem:** 30-second timeout is hardcoded in 30+ places but not exposed as config option
  - **Fix:** Add `timeout_seconds` to ServerConfig with default 30, document in README

---

- [ ] **DOC-023**: Ambiguous "Relevance" in TokenUsageEvent
  - **Location:** `src/analytics/token_tracker.py:14-26`
  - **Problem:** Dataclass field `relevance_avg: float` has comment "Average relevance score" but doesn't specify the range (0-1? 0-100?) or what it measures. Looking at usage in `track_search()` (line 145), it's passed directly from user without validation. For indexing events (line 177), it's hardcoded to 1.0 with comment "N/A for indexing".
  - **Expected:** Add to docstring: "relevance_avg: Average relevance score (0.0-1.0, 1.0 = perfect match)"
  - **Fix:** Document expected range and semantics for relevance_avg field

- [ ] **DOC-27**: Incomplete Exception Documentation in validate_store_request()
  - **Location:** `src/core/validation.py:277-332`
  - **Problem:** Docstring says "Raises: ValidationError: If validation fails" but doesn't mention that it can also raise Pydantic ValidationError (wrapped from line 331: `except ValueError as e`). The function catches Pydantic errors and re-raises as custom ValidationError, but this isn't clear from docs.
  - **Expected:** "Raises: ValidationError: If validation fails (wraps Pydantic validation errors)"
  - **Fix:** Update docstring to clarify error wrapping behavior

- [ ] **DOC-28**: Incomplete Exception Documentation in validate_store_request()
  - **Location:** `src/core/validation.py:277-332`
  - **Problem:** Docstring says "Raises: ValidationError: If validation fails" but doesn't mention that it can also raise Pydantic ValidationError (wrapped from line 331: `except ValueError as e`). The function catches Pydantic errors and re-raises as custom ValidationError, but this isn't clear from docs.
  - **Expected:** "Raises: ValidationError: If validation fails (wraps Pydantic validation errors)"
  - **Fix:** Update docstring to clarify error wrapping behavior

- [ ] **DOC-002**: Migration guides

- [ ] **DOC-003**: Video tutorials

- [ ] **DOC-005**: Add performance tuning guide for large codebases

- [ ] **DOC-007**: Document best practices for project organization

- [ ] **DOC-014**: Inconsistent Docstring Style for Async Methods
  - **Location:** `src/store/base.py:169-181`, `src/store/base.py:184-196`, `src/store/base.py:199-208`
  - **Problem:** Three abstract async methods (`health_check`, `initialize`, `close`) have identical notes explaining "This function is async for interface compatibility. Abstract methods in base classes must be async even without await to maintain consistent interface across all storage backend implementations." This is repetitive and could be stated once at the class level.
  - **Expected:** Move note to class docstring, reference it in individual methods if needed
  - **Fix:** Extract common note to MemoryStore class docstring section on "Async Method Requirements"

- [ ] **DOC-015**: cosine_similarity() Return Range Incorrect
  - **Location:** `src/embeddings/rust_bridge.py:51-72`, `src/embeddings/rust_bridge.py:101-121`
  - **Problem:** Both Python and Rust bridge implementations document cosine_similarity as returning "0.0 to 1.0" but mathematical cosine similarity ranges from -1 to 1 (negative for opposite vectors). The implementation correctly computes the full range (line 72 can produce negative values), but the docstring is wrong.
  - **Expected:** "Returns: Cosine similarity score (-1.0 to 1.0, where 1.0 = identical, 0.0 = orthogonal, -1.0 = opposite)"
  - **Fix:** Update docstrings in both functions (lines 60, 110) to reflect actual range

- [ ] **DOC-020**: Error Recovery Guidance Missing from Exception Messages
  - **Location:** All custom exceptions in `src/core/exceptions.py`
  - **Problem:** Some exceptions have `solution` field but many are constructed without it
  - **Fix:** Audit all exception instantiation and ensure 80%+ include actionable solution field

- [ ] **DOC-23**: Type Hint Missing for classify_batch()
  - **Location:** `src/memory/classifier.py:188-200`
  - **Problem:** Parameter `items` uses lowercase `tuple` in type hint: `List[tuple[str, MemoryCategory]]` instead of `Tuple` from typing module. Python 3.9+ supports lowercase tuple, but inconsistent with project style (line 5 imports `Tuple` from typing).
  - **Expected:** Use `List[Tuple[str, MemoryCategory]]` for consistency
  - **Fix:** Update line 189 type hint to use imported Tuple

- [ ] **DOC-24**: Type Hint Missing for classify_batch()
  - **Location:** `src/memory/classifier.py:188-200`
  - **Problem:** Parameter `items` uses lowercase `tuple` in type hint: `List[tuple[str, MemoryCategory]]` instead of `Tuple` from typing module. Python 3.9+ supports lowercase tuple, but inconsistent with project style (line 5 imports `Tuple` from typing).
  - **Expected:** Use `List[Tuple[str, MemoryCategory]]` for consistency
  - **Fix:** Update line 189 type hint to use imported Tuple

- [ ] **DOC-026**: Misleading Function Name: should_archive_project()
  - **Location:** `src/memory/project_context.py:263-282`
  - **Problem:** Function is named `should_archive_project()` suggesting it performs archival, but it only returns a boolean check. The caller must actually perform the archival. Name suggests action, but it's a query.
  - **Expected:** Rename to `is_project_archivable()` or `check_archival_eligibility()` to clarify it's a predicate
  - **Fix:** Rename function and update callers, or add docstring clarifying this is a check-only function

- [ ] **DOC-027**: Undocumented Side Effect in track_file_activity()
  - **Location:** `src/memory/project_context.py:213-241`
  - **Problem:** Docstring says "Track file activity to infer active project" but doesn't mention that it can AUTO-SET the current context if none is active (lines 234-240). This is a significant side effect that should be documented.
  - **Expected:** Add to docstring: "Note: If no context is currently active, this will automatically set the detected project as active."
  - **Fix:** Update docstring to document auto-context-switching behavior

- [ ] **DOC-001**: Interactive documentation

- [ ] **DOC-013**: _score_patterns() Return Type Misleading
  - **Location:** `src/memory/classifier.py:85-97`
  - **Problem:** Docstring says "Returns: Score between 0 and 1" but implementation uses formula `min(1.0, matches / max(1, len(patterns) * 0.3))` which can exceed 1.0 before the min() clamp. The comment at line 97 is misleading because it doesn't explain WHY 0.3 divisor is used (it's to allow multiple matches to boost score above threshold).
  - **Expected:** "Returns: Score normalized to 0-1 range. Uses 0.3 divisor to amplify signal from sparse patterns."
  - **Fix:** Update docstring and add inline comment explaining the normalization factor choice

- [ ] **DOC-016**: Type Hint Mismatch in retrieve_multi_level()
  - **Location:** `src/core/tools.py:268-334`
  - **Problem:** Return type annotation is `dict[ContextLevel, List[MemoryResult]]` (lowercase dict, Python 3.9+) but rest of codebase uses `Dict[...]` from typing module (Python 3.7+ compatible). This inconsistency could break type checking in environments requiring `from __future__ import annotations` or older Python versions.
  - **Expected:** Use `Dict[ContextLevel, List[MemoryResult]]` for consistency with project style
  - **Fix:** Change line 274 to use uppercase Dict imported from typing

- [ ] **DOC-017**: Missing Parameter Documentation for list_indexed_units()
  - **Location:** `src/store/base.py:274-318`
  - **Problem:** Docstring documents `file_pattern` as "Optional pattern for file paths (SQL LIKE for SQLite, glob for Qdrant)" but SQLite storage has been removed (see REF-010 in factory.py). The documentation references non-existent SQLite backend, which will confuse implementers.
  - **Expected:** "Optional pattern for file paths (glob pattern for Qdrant)"
  - **Fix:** Remove SQLite reference from all base.py method docstrings

- [ ] **DOC-018**: Stale Comment References Removed Fallback
  - **Location:** `src/store/factory.py:14-15`
  - **Problem:** Comment says "REF-010: SQLite fallback removed - Qdrant is now required for semantic code search" but this is a changelog-style comment in code, not actual documentation. Should be in CHANGELOG.md, not inline code.
  - **Expected:** Remove or move to module docstring as "History" section
  - **Fix:** Remove lines 14-15, ensure REF-010 is documented in CHANGELOG.md

- [ ] **DOC-021**: No Centralized Error Code Documentation
  - **Location:** N/A (missing)
  - **Problem:** Error codes E000-E015 are defined but not documented in user-facing docs
  - **Fix:** Create `docs/ERROR_CODES.md` with table of all error codes, causes, and solutions

- [ ] **DOC-024**: Inconsistent DateTime Timezone Documentation
  - **Location:** `src/memory/project_context.py:29`, `src/analytics/token_tracker.py:17`
  - **Problem:** ProjectContext uses `last_activity: datetime = field(default_factory=lambda: datetime.now(UTC))` with explicit UTC, but TokenUsageEvent just says `timestamp: datetime` without timezone info. Both use `datetime.now()` (line 169 in token_tracker.py) which creates naive datetime, causing inconsistency.
  - **Expected:** Document whether all datetime fields should be timezone-aware or naive
  - **Fix:** Add project-wide convention in docs, update dataclass fields to specify tz requirements

- [ ] **DOC-025**: Magic Number 0.3 in get_project_weight() Undocumented
  - **Location:** `src/memory/project_context.py:242-261`
  - **Problem:** Method returns 0.3 for inactive projects and 2.0 for active projects (lines 261, 258) but doesn't explain why these specific multipliers were chosen. No reference to where these are used or their impact on ranking.
  - **Expected:** Add comment explaining rationale, e.g., "0.3 penalty for inactive projects keeps them findable but deprioritized; 2.0 boost for active project reflects user's current focus"
  - **Fix:** Add explanatory comment and reference to search result weighting algorithm

- [ ] **DOC-25**: Example Code in Docstring References Wrong Method
  - **Location:** `src/core/tools.py:66-72`
  - **Problem:** Example shows `await tools.retrieve_preferences(query="coding style preferences", limit=10)` but the method signature has `limit: int = 5` (line 48). Example uses limit=10 which is fine, but could be clearer that it's overriding the default.
  - **Expected:** Add comment in example: `limit=10  # Override default of 5`
  - **Fix:** Enhance example to show default behavior or clarify override

- [ ] **DOC-26**: Example Code in Docstring References Wrong Method
  - **Location:** `src/core/tools.py:66-72`
  - **Problem:** Example shows `await tools.retrieve_preferences(query="coding style preferences", limit=10)` but the method signature has `limit: int = 5` (line 48). Example uses limit=10 which is fine, but could be clearer that it's overriding the default.
  - **Expected:** Add comment in example: `limit=10  # Override default of 5`
  - **Fix:** Enhance example to show default behavior or clarify override

- [ ] **DOC-028**: Comment Contradicts Implementation in _resolve_module_to_file()
  - **Location:** `src/memory/dependency_graph.py:78-143`
  - **Problem:** Comment at lines 88-91 says "This is a simplified implementation. A full implementation would need: - Language-specific module resolution rules..." but then the implementation at lines 109-137 actually DOES implement Python/JS/TS relative import resolution with multiple file extensions. The comment is stale.
  - **Expected:** Update comment to say "Currently implements relative import resolution for Python/JS/TS. TODO: Add absolute import resolution for project-internal modules"
  - **Fix:** Revise comment to reflect actual capabilities, move unimplemented items to TODO

- [ ] **DOC-029**: Stopwords Set Missing Common Code Terms
  - **Location:** `src/tagging/auto_tagger.py:292-338`
  - **Problem:** Stopwords list (lines 292-338) includes English stopwords ("the", "is", "at") but doesn't include common programming stopwords like "function", "class", "method", "return", "value" which appear frequently in code comments but aren't meaningful tags.
  - **Expected:** Add code-specific stopwords or document that this is intentionally English-only
  - **Fix:** Extend stopwords with code-specific terms or add comment explaining scope

## Features (FEAT-*)

- [ ] **FEAT-014**: Semantic refactoring

- [ ] **FEAT-015**: Code review features

- [ ] **FEAT-017**: Multi-repository support

- [ ] **FEAT-019**: IDE Integration

- [ ] **FEAT-021**: Memory lifecycle management

- [ ] **FEAT-022**: Performance monitoring dashboard

- [ ] **FEAT-050**: Track cache usage in queries

- [ ] **FEAT-052**: Map project_name to repo_path for git history

- [ ] **FEAT-053**: Enhanced file history with diff content

- [ ] **FEAT-054**: File pattern and language filtering for multi-repo search

- [ ] **FEAT-062**: Architecture Visualization & Diagrams (~4-6 weeks) 🔥
  - **Current Gap:** No visual representation of architecture, dependencies, or call graphs
  - **Problem:** Architecture discovery relied on mental modeling - difficult to understand complex systems, explain to others, or document
  - **Proposed Solution:**

## UX Improvements (UX-*)

- [ ] **UX-028**: Telemetry & analytics (opt-in) (~1 week)

- [ ] **UX-039**: Memory Relationships Graph Viewer (~10-12 hours)

- [ ] **UX-040**: Project Comparison View (~6-8 hours)

- [ ] **UX-041**: Top Insights and Recommendations (~8-10 hours)

- [ ] **UX-042**: Quick Actions Toolbar (~6-8 hours)

- [ ] **UX-043**: Export and Reporting (~6-8 hours)

- [ ] **UX-060**: Inconsistent Progress Indicator Patterns
  - **Location:** `src/cli/index_command.py:169-220` (rich Progress with callback), vs `src/cli/backup_command.py:70-89` (rich Progress with spinner), vs `src/cli/git_index_command.py:56-77` (rich Progress with bar)
  - **Problem:** Three different progress bar styles for similar operations. IndexCommand uses custom callback with task updates, BackupCommand uses simple spinner, GitIndexCommand uses BarColumn. Inconsistent UX - users can't predict what feedback they'll get.
  - **Fix:** Create shared `src/cli/progress_utils.py` with standard progress styles: `create_indexing_progress()`, `create_spinner_progress()`, `create_transfer_progress()`

- [ ] **UX-061**: No Confirmation Prompts for Destructive Operations in Multiple Commands
  - **Location:** `src/cli/project_command.py:144-164` (delete has confirmation), but `src/cli/collections_command.py:100-119` (delete uses click.confirm), `src/cli/tags_command.py:111-141` (delete uses click.confirm)
  - **Problem:** Inconsistent confirmation patterns - some use `input()`, some use `click.confirm()`, some use `rich.prompt.Confirm.ask()`. Three different confirmation UIs create confusing UX. Also, collections and tags commands use Click but aren't registered in main CLI (separate entry points).
  - **Fix:** Standardize on rich.prompt.Confirm for all confirmations. Integrate collections/tags into main CLI or document as separate tools

- [ ] **UX-063**: Missing Help Text for Complex Subcommands
  - **Location:** `src/cli/repository_command.py:413-514` has 6 subcommands but minimal epilog examples, `src/cli/workspace_command.py:477-586` similar
  - **Problem:** Complex multi-level commands (repository, workspace) don't have usage examples in help. Users must read code to understand `claude-rag repository add-dep` syntax.
  - **Fix:** Add `epilog` with examples to each subparser like git-index/git-search do (lines 206-216)

- [ ] **UX-064**: Truncated Repository IDs in Tables Inconsistently
  - **Location:** `src/cli/repository_command.py:259` truncates to `id[:12] + "..."`, but `src/cli/workspace_command.py:291` shows full ID
  - **Problem:** Repository tables truncate IDs to 12 chars + "..." but workspace tables show full IDs. Inconsistent display width makes output unpredictable.
  - **Fix:** Standardize on max_width parameter for ID columns across all tables

- [ ] **UX-065**: No Progress Indicator for Long-Running health_check Operations
  - **Location:** `src/cli/health_command.py:421-562` runs 10+ async checks sequentially with no progress
  - **Problem:** Health check can take 5-10 seconds (Qdrant latency, embedding model load, etc.) with no feedback. User sees nothing until all checks complete.
  - **Fix:** Add `with console.status("Running health checks...")` or progress bar showing N/M checks complete

- [ ] **UX-066**: prune Command Shows Confirmation Twice in Non-Dry-Run Mode  
  - **Location:** `src/cli/prune_command.py:54-75` (preview + confirmation), then `src/cli/prune_command.py:77-82` (actual execution)
  - **Problem:** User sees "Found N memories" preview, then "About to delete N memories" confirmation. Redundant - preview result shows same count as confirmation.
  - **Fix:** Combine into single confirmation: "Found N expired memories. Delete them? (yes/no)"

- [ ] **UX-062**: Inconsistent Error Message Formatting
  - **Location:** `src/cli/health_command.py:481` prints `"Cannot load embedding model"`, vs `src/cli/status_command.py:89` logs then returns error dict, vs `src/cli/index_command.py:241` prints `"ERROR: Indexing failed - {e}"`
  - **Problem:** Different error formats: some use logger.error, some use console.print with [red], some use plain print with "ERROR:" prefix. No standard error format.
  - **Fix:** Create `src/cli/error_utils.py` with `print_error(message, exc=None)` that handles logging + rich formatting consistently

## Investigations (INVEST-*)
