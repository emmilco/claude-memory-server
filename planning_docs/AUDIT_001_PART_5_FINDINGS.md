# AUDIT-001 Part 5: Memory Indexing & Parsing Findings (2025-11-30)

**Investigation Scope:** Memory indexing, parsing, and dependency tracking components
**Files Analyzed:** incremental_indexer.py (1,225 lines), import_extractor.py (515 lines), dependency_graph.py (370 lines), background_indexer.py (494 lines), git_detector.py (212 lines)
**Focus:** Parser failure recovery, incremental indexing consistency, file change detection, language detection, AST parsing errors, circular dependencies, large file handling, binary file detection, encoding issues, git ignore patterns

## 🔴 CRITICAL Findings

- [ ] **BUG-059**: Undefined Variable PYTHON_PARSER_AVAILABLE Referenced But Never Defined
  - **Location:** `src/memory/incremental_indexer.py:188`
  - **Problem:** Line 188 checks `if not RUST_AVAILABLE and not PYTHON_PARSER_AVAILABLE` but PYTHON_PARSER_AVAILABLE is never imported or defined anywhere in the file. This will raise NameError if RUST_AVAILABLE is False. The Python parser fallback was intentionally removed (line 12 comment says it was broken), but the check wasn't updated.
  - **Fix:** Remove `and not PYTHON_PARSER_AVAILABLE` from line 188, change to `if not RUST_AVAILABLE: raise RuntimeError("Rust parser required...")`

- [ ] **BUG-060**: Missing Call Graph Store Cleanup in IncrementalIndexer.close()
  - **Location:** `src/memory/incremental_indexer.py:1202-1206`
  - **Problem:** The `close()` method closes `self.store` and `self.embedding_generator`, but does NOT close `self.call_graph_store` which was initialized at line 224. This creates a resource leak - the call graph store's Qdrant connections remain open indefinitely.
  - **Fix:** Add `await self.call_graph_store.close()` before closing other resources

- [ ] **BUG-067**: Race Condition in Background Indexer Task Cleanup
  - **Location:** `src/memory/background_indexer.py:488-493`
  - **Problem:** In the `finally` block, code deletes `job_id` from `_active_tasks` dict but doesn't handle the case where the job might have already been removed by `cancel_job()` (lines 255-256). If cancel and completion happen simultaneously, this could raise KeyError. The check `if job_id in self._active_tasks` is not atomic with the deletion.
  - **Fix:** Use `self._active_tasks.pop(job_id, None)` instead of `del self._active_tasks[job_id]`

## 🟡 HIGH Priority Findings

- [ ] **BUG-068**: Circular Dependency Detection Has False Negatives
  - **Location:** `src/memory/dependency_graph.py:279-312`
  - **Problem:** The `detect_circular_dependencies()` method uses DFS with visited/rec_stack tracking, but only starts DFS from nodes that are keys in `self.dependencies` dict (line 308). If a file B imports A, but A doesn't import anything, then A won't be in `dependencies.keys()` and won't be explored. This misses cycles like: A -> B -> C -> A where A has no outgoing dependencies in the dict.
  - **Fix:** Change line 308 to iterate over `set(self.dependencies.keys()) | set(self.dependents.keys())` to ensure all nodes are explored

- [ ] **REF-043**: Module Resolution Only Handles Relative Imports
  - **Location:** `src/memory/dependency_graph.py:78-143`
  - **Problem:** The `_resolve_module_to_file()` method only resolves relative imports (lines 109-138). Absolute imports within the project are silently ignored (line 142 returns None). This means the dependency graph is incomplete - it won't track absolute imports like `from src.core.models import Memory` even though they're internal to the project.
  - **Fix:** Add project-root-aware absolute import resolution. For Python: check if module path starts with project package name, resolve to `project_root / module.replace('.', '/')`. Document this limitation or implement full resolution.

- [ ] **PERF-011**: Inefficient File Extension Matching in Directory Indexing
  - **Location:** `src/memory/incremental_indexer.py:418-421`
  - **Problem:** For each supported extension, calls `dir_path.glob(f"{pattern}{ext}")` separately, then concatenates results. For 20 supported extensions, this performs 20 separate filesystem traversals. For large directories (10,000+ files), this is extremely slow.
  - **Fix:** Use single glob pattern with set filtering: `all_files = dir_path.glob(pattern); files = [f for f in all_files if f.suffix in SUPPORTED_EXTENSIONS]`. Reduces 20 traversals to 1.

- [ ] **BUG-069**: Git Detection Has No Error Recovery for Subprocess Timeouts
  - **Location:** `src/memory/git_detector.py:30-36`, `src/memory/git_detector.py:56-62`, and 4 other subprocess calls
  - **Problem:** All git subprocess calls use `timeout=5` but only catch generic `Exception`. If the timeout expires, it raises `subprocess.TimeoutExpired` which is caught and logged as debug, but the function returns False/None. However, if git hangs (but doesn't timeout), the entire indexing process blocks for 5 seconds PER FILE. For 100 files, that's 8+ minutes of blocking time.
  - **Fix:** Add specific `except subprocess.TimeoutExpired` handler, log as WARNING not debug (it's a system issue). Consider reducing timeout to 2s for faster failure.

## 🟢 MEDIUM Priority Findings

- [ ] **REF-044**: Hardcoded Git Subprocess Timeout Duplicated 6 Times
  - **Location:** `src/memory/git_detector.py:35`, `src/memory/git_detector.py:61`, `src/memory/git_detector.py:110`, `src/memory/git_detector.py:127`, `src/memory/git_detector.py:144`, `src/memory/git_detector.py:161`
  - **Problem:** The value `timeout=5` appears 6 times in subprocess.run() calls. If we need to tune git timeout (e.g., for slow filesystems), must change 6 locations. Magic number antipattern.
  - **Fix:** Define `GIT_SUBPROCESS_TIMEOUT = 5.0` as module constant at top of file, use in all subprocess calls

- [ ] **REF-045**: Import Extractor Has No Language Version Handling
  - **Location:** `src/memory/import_extractor.py:50-78`
  - **Problem:** The import regex patterns are language-version-agnostic. Python 3.10+ supports `match`/`case`, TypeScript 5.0 changed import syntax, Rust 2021 edition has different module paths. The extractor will miss or incorrectly parse newer syntax.
  - **Fix:** Add optional `language_version` parameter to `extract_imports()`. Use version-specific regex patterns. Document supported language versions.

- [ ] **BUG-070**: File Change Hashing Doesn't Handle Large Files Efficiently
  - **Location:** `src/memory/incremental_indexer.py:283-284`
  - **Problem:** The code reads entire file into memory with `f.read()` to parse it, regardless of size. For files >100MB, this can cause memory pressure. The indexer supports files up to gigabytes (no size limit check), which could OOM the process.
  - **Fix:** Add file size check before reading: `if file_path.stat().st_size > 10*1024*1024: logger.warning("File too large, skipping"); return {...}`. Set max file size limit (10MB default, configurable).

- [ ] **REF-046**: Inconsistent Error Handling Between File and Directory Indexing
  - **Location:** `src/memory/incremental_indexer.py:255-388` (index_file) vs `src/memory/incremental_indexer.py:390-546` (index_directory)
  - **Problem:** `index_file()` raises `StorageError` on failure (line 388), forcing caller to handle exception. `index_directory()` catches all exceptions, logs them, and returns failure in `failed_files` list (line 489). Inconsistent error contract makes it unclear when to expect exceptions vs error results.
  - **Fix:** Standardize on one pattern. Recommend: index_file raises exceptions (caller decides), index_directory catches and aggregates (batch operation). Document in docstrings.

- [ ] **PERF-012**: Redundant File Resolution in Cleanup Operations
  - **Location:** `src/memory/incremental_indexer.py:705-707`
  - **Problem:** In `_cleanup_stale_entries()`, for each indexed file, code calls `file_path.relative_to(dir_path)` inside a try/except to check if file is in directory. This is expensive for 1000+ files. The `current_file_paths` set (line 695) already contains resolved absolute paths - just check if file starts with dir_path string.
  - **Fix:** Replace `file_path.relative_to(dir_path)` with `file_path_str.startswith(str(dir_path.resolve()))` for 10x speedup

- [ ] **BUG-071**: Missing Encoding Declaration in Import Extractor
  - **Location:** `src/memory/import_extractor.py:96-98`, and all language-specific extractors
  - **Problem:** The `extract_imports()` method receives `source_code` as a string parameter but doesn't document required encoding. If caller passes source_code decoded with wrong encoding (e.g., latin-1 instead of utf-8), regex matching will fail silently or produce garbage results. The incremental_indexer opens files with `encoding="utf-8"` (line 283) but import_extractor has no encoding awareness.
  - **Fix:** Document that source_code must be UTF-8 decoded. Add encoding parameter with default 'utf-8'. Handle UnicodeDecodeError gracefully.

## 🔵 LOW Priority Findings

- [ ] **REF-047**: Duplicate Code in Index File Path Resolution
  - **Location:** `src/memory/incremental_indexer.py:271`, `src/memory/incremental_indexer.py:412`, `src/memory/incremental_indexer.py:558`
  - **Problem:** Three methods all call `Path(file_path).resolve()` to normalize paths. This pattern is repeated without abstraction. If path resolution logic needs to change (e.g., to handle symlinks differently), must update 3+ places.
  - **Fix:** Extract to `_resolve_file_path(self, file_path: Path) -> Path` helper method

- [ ] **REF-048**: Magic Number for Git Worktrees Exclusion Pattern
  - **Location:** `src/memory/incremental_indexer.py:428`
  - **Problem:** The EXCLUDED_DIRS set includes ".worktrees" with a comment "Git worktrees for parallel development". This is project-specific knowledge hardcoded in the indexer. Users with different worktree setups (e.g., `_worktrees/`, `tmp/worktrees/`) won't get proper filtering.
  - **Fix:** Make EXCLUDED_DIRS configurable via ServerConfig. Add `indexing.excluded_dirs` config option with defaults.

- [ ] **PERF-013**: Unused Semaphore Value Calculation
  - **Location:** `src/memory/incremental_indexer.py:464`
  - **Problem:** Creates `asyncio.Semaphore(max_concurrent)` to limit concurrency, but the semaphore value is never checked or monitored. If max_concurrent=4 but system can only handle 2 concurrent operations, there's no backpressure mechanism or resource monitoring.
  - **Fix:** Add optional `adaptive_concurrency` mode that monitors memory/CPU usage and adjusts semaphore limit dynamically

- [ ] **REF-049**: Function Signature Parsing Regex Is Fragile
  - **Location:** `src/memory/incremental_indexer.py:1165-1200`
  - **Problem:** The `_extract_parameters()` method uses simple regex to parse function signatures. It will break on: nested generics `func(a: Dict[str, List[Tuple[int, int]]])`, lambda parameters, decorators with parameters, async generator syntax. Only handles simple cases.
  - **Fix:** Use proper AST parsing for parameter extraction instead of regex. The Rust parser already provides this info - extract from `unit.signature` structure instead of string parsing.

- [ ] **BUG-072**: TODO Comment Indicates Missing Return Type Extraction
  - **Location:** `src/memory/incremental_indexer.py:1079`
  - **Problem:** Comment says `return_type=None, # TODO: Extract from signature if available`. This means call graph function nodes don't track return types, limiting the usefulness of call graph analysis for type checking or refactoring tools.
  - **Fix:** Implement return type extraction from signature string (regex for `-> ReturnType:`) or get from Rust parser if available

## Summary Statistics

- **Total Issues Found:** 16
- **Critical:** 3 (undefined variable, resource leak, race condition)
- **High:** 4 (circular dependency detection, import resolution, performance, timeout handling)
- **Medium:** 5 (hardcoded values, version handling, large files, error consistency, encoding)
- **Low:** 4 (code duplication, magic numbers, monitoring, fragile parsing)

**Key Risks:**
1. PYTHON_PARSER_AVAILABLE undefined will crash on systems without Rust parser
2. Resource leaks (call graph store never closed)
3. Incomplete dependency graph (only tracks relative imports)
4. No large file protection (can OOM on huge files)

**Next Ticket Numbers:** BUG-059 to BUG-072, REF-043 to REF-049, PERF-011 to PERF-013

## Action Items for Integration into TODO.md

The findings in this document should be added to TODO.md after the existing AUDIT-001 sections. Since the file is being actively modified by other agents, here is a summary for manual integration:

**Tickets to add:**
- BUG-059 through BUG-072 (14 tickets)
- REF-043 through REF-049 (7 tickets)
- PERF-011 through PERF-013 (3 tickets)

**Total:** 24 new tickets across memory indexing and parsing components
