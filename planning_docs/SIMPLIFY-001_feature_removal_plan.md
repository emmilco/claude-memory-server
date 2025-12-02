# SIMPLIFY-001: Feature Removal and Codebase Simplification

**Status:** Planning
**Created:** 2025-12-01
**Priority:** Critical
**Estimated Effort:** Major (multi-day)

## Executive Summary

This plan removes ~10,000 LOC of underutilized features to reduce bug surface area by ~50% and create a stable foundation for future development. The removal covers: dependency graph visualization, import/export archives, tagging system, and health monitoring/remediation.

### Goals
1. Remove identified features completely with zero orphaned code
2. Eliminate ~115 open bugs/REFs associated with removed features
3. Reduce SQLite usage from 17 tables to 3-5 essential tables
4. Leave codebase in a clean, consistent, fully-tested state
5. Multiple review passes to ensure nothing is missed

### Non-Goals
- Adding new features
- Refactoring kept code (beyond what's necessary for removal)
- Performance optimization

---

## Features to Remove

### Tier 1: Complete Module Deletion
| Module | LOC | SQLite Tables | Bugs/REFs |
|--------|-----|---------------|-----------|
| `src/graph/` | 1,233 | 0 | ~30 |
| `src/backup/` | 1,694 | 0 | ~20 |
| `src/tagging/` | 1,335 | 4 | ~18 |

### Tier 2: Monitoring Reduction
| File | LOC | SQLite Tables | Bugs/REFs |
|------|-----|---------------|-----------|
| `src/monitoring/health_reporter.py` | 532 | 0 | ~5 |
| `src/monitoring/capacity_planner.py` | 612 | 0 | ~5 |
| `src/monitoring/remediation.py` | 536 | 1 | ~8 |
| `src/monitoring/alert_engine.py` | 569 | 1 | ~3 |

**Keep in monitoring:**
- `metrics_collector.py` - Basic metrics
- `performance_tracker.py` - Performance tracking

### Tier 3: Memory Module Cleanup
| File | LOC | Bugs/REFs |
|------|-----|-----------|
| `src/memory/health_scheduler.py` | 354 | ~3 |
| `src/memory/health_scorer.py` | 487 | ~5 |
| `src/memory/health_jobs.py` | 407 | ~2 |
| `src/memory/graph_generator.py` | 477 | ~3 |
| `src/memory/archive_exporter.py` | 267 | ~2 |
| `src/memory/archive_importer.py` | 314 | ~2 |
| `src/memory/archive_compressor.py` | 400 | ~1 |
| `src/memory/dependency_graph.py` | 369 | ~2 |

### Tier 4: CLI Command Removal
| File | LOC | Reason |
|------|-----|--------|
| `src/cli/health_dashboard_command.py` | ~350 | Uses health_scorer |
| `src/cli/health_monitor_command.py` | ~450 | Uses alert_engine, remediation |
| `src/cli/health_schedule_command.py` | ~300 | Uses health_scheduler |
| `src/cli/tags_command.py` | TBD | Uses tagging module |
| `src/cli/collections_command.py` | TBD | Uses tagging module |
| `src/cli/auto_tag_command.py` | TBD | Uses auto_tagger |
| `src/cli/graph_command.py` (if exists) | TBD | Uses graph module |
| `src/cli/backup_command.py` (if exists) | TBD | Uses backup module |

### Tier 5: Analytics Removal
| File | LOC | SQLite Tables |
|------|-----|---------------|
| `src/analytics/usage_tracker.py` | TBD | 3 |
| `src/analytics/token_tracker.py` | TBD | 1 |

---

## What We Keep

### Core (Untouched)
- `src/core/` - Server, models, exceptions
- `src/store/` - Qdrant store, connection pool
- `src/embeddings/` - Generation + cache (essential SQLite)
- `src/search/` - Hybrid search, BM25, reranking
- `src/services/` - Business logic layer
- `src/mcp_server.py` - MCP protocol
- `src/config.py` - Configuration

### Memory (Keep Core)
- `incremental_indexer.py`
- `repository_registry.py`
- `bulk_operations.py`
- `duplicate_detector.py`
- `workspace_manager.py`
- `multi_repository_indexer.py`
- `multi_repository_search.py`
- `background_indexer.py`
- `auto_indexing_service.py`
- `file_watcher.py`
- `git_indexer.py`
- `usage_tracker.py`
- And other core indexing files

### Monitoring (Keep Basic)
- `metrics_collector.py`
- `performance_tracker.py`

### CLI (Keep Core)
- `health_command.py` (simplified)
- `index_command.py`
- `search_command.py`
- `status_command.py`
- `config_command.py`
- And other core commands

---

## Execution Strategy

### Approach: Feature Branches with Phased Merges

We will use **3 feature branches** that merge sequentially to main:

1. **Branch: `simplify/phase1-mapping`** - Dependency mapping only (no deletions)
2. **Branch: `simplify/phase2-removal`** - All deletions and import fixes
3. **Branch: `simplify/phase3-cleanup`** - Dead code removal, test fixes, polish

Each branch requires:
- All tests passing before merge
- Static analysis clean (no unused imports)
- Code review by agent before merge

---

## Phase 1: Dependency Mapping (No Code Changes)

**Goal:** Create a complete map of what depends on what before deleting anything.

**Duration:** 2-3 hours
**Agents:** 6 parallel agents (one per major audit task)

### Task 1.1: Module Import Graph
**Agent 1**

Create a file listing every import of modules we're removing.

```
For each module in removal list:
  - grep -r "from src.graph" src/
  - grep -r "import src.graph" src/
  - grep -r "from src.backup" src/
  - grep -r "from src.tagging" src/
  - grep -r "from src.analytics" src/
  - grep -r "from src.monitoring.health_reporter" src/
  - grep -r "from src.monitoring.alert_engine" src/
  - grep -r "from src.monitoring.remediation" src/
  - grep -r "from src.monitoring.capacity_planner" src/
  - grep -r "from src.memory.health_" src/
  - grep -r "from src.memory.archive_" src/
  - grep -r "from src.memory.graph_generator" src/
  - grep -r "from src.memory.dependency_graph" src/

Also search for class names as type hints:
  - grep -r "TagManager" src/
  - grep -r "CollectionManager" src/
  - grep -r "HealthScorer" src/
  - grep -r "HealthScheduler" src/
  - grep -r "AlertEngine" src/
  - grep -r "RemediationEngine" src/
  - grep -r "DependencyGraph" src/
  - grep -r "CallGraph" src/
```

**Output:** `planning_docs/SIMPLIFY-001_import_map.md`

### Task 1.2: MCP Tool Audit
**Agent 2**

List all MCP tools that reference removed features.

```
Search mcp_server.py for:
  - Tool definitions using removed modules
  - Tool handlers calling removed functions
  - Response formatting for removed features
  - Any conditional logic based on removed features

Specifically look for tools related to:
  - Tags, collections, auto-tagging
  - Health scores, remediation
  - Dependency graphs, call graphs
  - Import/export, backup/restore
  - Usage analytics
```

**Output:** `planning_docs/SIMPLIFY-001_mcp_tools_to_remove.md`

### Task 1.3: CLI Command Audit
**Agent 3**

List all CLI commands and their dependencies.

```
For each file in src/cli/:
  - List imports from removed modules
  - Identify if entire command should be removed
  - Identify if command needs modification
  - Check for command registration in main.py or __init__.py

Pay special attention to:
  - health_*.py commands
  - tags_command.py, collections_command.py, auto_tag_command.py
  - Any graph or backup related commands
  - Commands that call removed services
```

**Output:** `planning_docs/SIMPLIFY-001_cli_audit.md`

### Task 1.4: Server & Services Deep Audit
**Agent 4**

Deep audit of core server and services layer.

```
In src/core/server.py:
  - Find all imports from removed modules
  - Find all method calls to removed features
  - Find initialization code for removed subsystems
  - Find feature flag checks for removed features
  - Identify methods that should be removed entirely

In src/services/:
  - Audit each service file for dependencies on removed modules
  - Check health_service.py specifically
  - Check for injected dependencies (TagManager, etc.)
  - Identify service methods to remove

In src/dashboard/:
  - Determine if dashboard exposes removed features via HTTP
  - List endpoints to remove
  - Decide: remove entire dashboard or trim?
```

**Output:** `planning_docs/SIMPLIFY-001_server_services_audit.md`

### Task 1.5: Test & Fixture Audit
**Agent 5**

List all test files and fixtures for removed features.

```
For each removed module:
  - Find corresponding test file(s) in tests/unit/
  - Find integration tests in tests/integration/
  - Find e2e tests in tests/e2e/ (if exists)

Audit conftest.py files:
  - tests/conftest.py
  - tests/unit/conftest.py
  - tests/integration/conftest.py
  - Any subdirectory conftest.py files

For each conftest.py:
  - List fixtures that create removed objects
  - List fixtures that depend on removed modules
  - Identify fixtures that need modification vs deletion
```

**Output:** `planning_docs/SIMPLIFY-001_tests_to_remove.md`

### Task 1.6: Config & SQLite Audit
**Agent 6**

Audit configuration and SQLite tables.

```
In src/config.py:
  - List fields used only by removed modules
  - List validators for removed features
  - List feature flags for removed features
  - Identify field groups that reference removed features

SQLite Tables - for each CREATE TABLE found:
  - Identify which module creates it
  - Identify all modules that query it
  - Mark as KEEP or REMOVE
  - Document any cross-references between tables

Also check:
  - src/memory/lifecycle_manager.py - is it purely health-related?
  - Any other files that might be borderline keep/remove
```

**Output:** `planning_docs/SIMPLIFY-001_config_sqlite_audit.md`

### Phase 1 Gate
- [ ] All 6 audit documents created
- [ ] Each document reviewed by creating agent for completeness
- [ ] No surprises - all dependencies accounted for
- [ ] Borderline files (lifecycle_manager, dashboard) have clear keep/remove decision
- [ ] All `__init__.py` exports identified for cleanup

---

## Phase 2: Surgical Removal

**Goal:** Delete modules in correct order (leaves first, then branches).

**Duration:** 4-6 hours
**Agents:** 6 parallel agents in Wave A, then sequential cleanup

### Pre-Phase 2: Create Rollback Point

```bash
# Create a checkpoint before any deletions
git add -A
git commit -m "CHECKPOINT: Pre-SIMPLIFY-001 removal (rollback point)"
git tag simplify-001-checkpoint
```

This allows `git reset --hard simplify-001-checkpoint` if we discover a critical issue.

### Execution Structure

Phase 2 runs in three waves to avoid race conditions:

- **Wave A (Parallel):** Delete all files - 6 agents work on separate directories
- **Wave B (Sequential):** Fix all broken imports - 1 agent systematically repairs
- **Wave C (Sequential):** Clean MCP + Config + __init__.py files - 1 agent

### Wave A: Parallel Deletion (6 Agents)

All agents delete files simultaneously. No import fixes yet - just deletions.

#### Task 2.1: Remove CLI Commands
**Agent 1**

```
Delete files (based on Phase 1 audit):
  - src/cli/health_dashboard_command.py
  - src/cli/health_monitor_command.py
  - src/cli/health_schedule_command.py
  - src/cli/tags_command.py
  - src/cli/collections_command.py
  - src/cli/auto_tag_command.py
  - src/cli/graph_command.py (if exists)
  - src/cli/backup_command.py (if exists)
  - Any other CLI files identified in Phase 1

DO NOT update imports yet - just delete files.
```

#### Task 2.2: Remove Analytics Module
**Agent 2**

```
Delete entire directory:
  - src/analytics/

DO NOT update imports yet - just delete files.
```

#### Task 2.3: Remove Backup Module
**Agent 3**

```
Delete entire directory:
  - src/backup/

DO NOT update imports yet - just delete files.
```

#### Task 2.4: Remove Tagging Module
**Agent 4**

```
Delete entire directory:
  - src/tagging/

DO NOT update imports yet - just delete files.
```

#### Task 2.5: Remove Graph Module
**Agent 5**

```
Delete entire directory:
  - src/graph/

Delete related files in src/memory/:
  - src/memory/graph_generator.py
  - src/memory/dependency_graph.py

DO NOT update imports yet - just delete files.
```

#### Task 2.6: Remove Health/Monitoring/Archive Files
**Agent 6**

```
Delete files in src/memory/:
  - src/memory/health_scheduler.py
  - src/memory/health_scorer.py
  - src/memory/health_jobs.py
  - src/memory/archive_exporter.py
  - src/memory/archive_importer.py
  - src/memory/archive_compressor.py
  - src/memory/lifecycle_manager.py (if Phase 1 determined it's health-only)

Delete files in src/monitoring/:
  - src/monitoring/health_reporter.py
  - src/monitoring/capacity_planner.py
  - src/monitoring/remediation.py
  - src/monitoring/alert_engine.py

DO NOT update imports yet - just delete files.
```

#### Wave A Gate
- [ ] All 6 agents report completion
- [ ] All targeted files deleted (verified via ls/find)
- [ ] Git status shows all deletions staged

### Wave B: Import Repair (Sequential)

**Agent 7 (or reuse Agent 1)**

Now fix all broken imports systematically:

```
1. Run: find src -name "*.py" -exec python -m py_compile {} \; 2>&1
   - This will list all files with import errors

2. For each file with errors:
   a. Open the file
   b. Remove import lines for deleted modules
   c. Remove any code that used those imports (functions, method calls, etc.)
   d. If a parameter references a deleted type, update the signature
   e. Save and verify: python -m py_compile <file>

3. Update __init__.py files:
   - src/cli/__init__.py - remove exports for deleted commands
   - src/memory/__init__.py - remove exports for deleted files
   - src/monitoring/__init__.py - remove exports for deleted files
   - src/analytics/__init__.py - DELETE this file (directory gone)
   - src/backup/__init__.py - DELETE this file (directory gone)
   - src/tagging/__init__.py - DELETE this file (directory gone)
   - src/graph/__init__.py - DELETE this file (directory gone)

4. Verify: python -c "import src" succeeds
```

#### Wave B Gate
- [ ] `python -c "import src"` - No import errors
- [ ] `python -m py_compile src/**/*.py` - All files compile

### Wave C: Clean MCP, Config, Server (Sequential)

**Agent 8 (or reuse Agent 2)**

```
1. Clean src/mcp_server.py:
   - Remove tool definitions for deleted features (from Phase 1 audit)
   - Remove tool handlers for deleted features
   - Remove any remaining imports of deleted modules
   - Clean up conditional logic for removed features
   - Verify: python -m py_compile src/mcp_server.py

2. Clean src/config.py:
   - Remove fields for deleted features (from Phase 1 audit)
   - Remove validators for deleted features
   - Update feature flag groups
   - Verify: python -m py_compile src/config.py

3. Clean src/core/server.py:
   - Remove imports of deleted modules
   - Remove method implementations that used deleted features
   - Remove initialization code for deleted subsystems
   - Update any feature flag checks
   - Verify: python -m py_compile src/core/server.py

4. Clean src/services/:
   - Remove or update health_service.py as needed
   - Remove imports from all service files
   - Update any service methods that called deleted code
   - Verify: python -m py_compile src/services/*.py

5. Clean src/dashboard/ (if keeping):
   - Remove endpoints for deleted features
   - Remove imports of deleted modules
   - Or delete entire directory if Phase 1 determined it should go
```

### Phase 2 Gate
- [ ] All targeted files deleted
- [ ] `python -c "import src"` - No import errors
- [ ] `python -m py_compile src/**/*.py` - All files compile
- [ ] `ruff check src/ --select E,F` - No syntax/import errors
- [ ] Git commit: "SIMPLIFY-001: Delete modules (Phase 2 complete)"

---

## Phase 3: Cleanup Cascade

**Goal:** Find and fix all orphaned code, dead paths, and broken tests.

**Duration:** 4-6 hours
**Agents:** 6 parallel agents

### Task 3.1: Dead Code Analysis & Removal
**Agent 1**

```
Run static analysis with ruff (now installed):

1. Check for unused imports:
   ruff check src/ --select F401 --output-format text
   - Fix all unused imports

2. Check for other dead code:
   ruff check src/ --select F811,F841 --output-format text
   - F811: Redefinition of unused name
   - F841: Local variable assigned but never used
   - Fix all issues

3. Manual scan for orphaned code:
   - Functions that only called removed code
   - Classes that only supported removed features
   - Method parameters that only passed to removed functions
   - Constants/variables only used by removed code
   - Empty try/except blocks where the try body was removed

4. Remove all identified dead code

5. Verify:
   ruff check src/ --select F401,F811,F841  # Should return clean
   python -c "import src"  # Should succeed
```

### Task 3.2: Delete Test Files for Removed Modules
**Agent 2**

```
Delete test files (based on Phase 1 audit):

In tests/unit/:
  - test_graph*.py
  - test_backup*.py
  - test_tag*.py, test_tagging*.py
  - test_collection*.py
  - test_health_scorer*.py
  - test_health_scheduler*.py
  - test_health_jobs*.py
  - test_alert*.py
  - test_remediation*.py
  - test_capacity*.py
  - test_archive*.py
  - test_analytics*.py
  - test_usage_tracker*.py (if analytics-related)
  - test_token_tracker*.py

In tests/integration/:
  - Any files testing removed features

In tests/e2e/ (if exists):
  - Any files testing removed features

Verify: ls tests/unit/ | grep -E "(graph|backup|tag|collection|health_s|alert|remed|capacity|archive|analytics)"
Should return nothing.
```

### Task 3.3: Fix Remaining Test Files
**Agent 3**

```
For each remaining test file that imports removed modules:

1. Run: grep -r "from src.graph\|from src.backup\|from src.tagging" tests/
   - List all affected test files

2. For each affected file:
   - Remove imports of deleted modules
   - Remove test cases that test deleted features
   - Remove test class methods that used deleted objects
   - Update any parametrized tests that included removed cases

3. Fix conftest.py files:
   - tests/conftest.py
   - tests/unit/conftest.py
   - tests/integration/conftest.py
   - Remove fixtures that created deleted objects
   - Update fixtures that injected deleted dependencies

Verify: pytest tests/ --collect-only (should collect without import errors)
```

### Task 3.4: Simplify health_command.py
**Agent 4**

```
The basic health_command.py is kept but needs trimming.

Remove references to:
  - HealthScorer (if imported)
  - LifecycleManager (if removed)
  - Any health metrics from monitoring module

Keep only:
  - check_python_version()
  - check_disk_space()
  - check_memory()
  - check_rust_parser()
  - check_python_parser()
  - check_storage_backend() - Qdrant connectivity
  - check_embedding_model()
  - check_embedding_cache()
  - check_indexed_projects()
  - check_qdrant_latency()

Remove or stub:
  - Any methods that called deleted modules
  - Sections of run_checks() that used deleted features

Verify: python -c "from src.cli.health_command import HealthCommand"
```

### Task 3.5: Clean Documentation & README
**Agent 5**

```
Update README.md:
  - Remove mentions of dependency graph visualization
  - Remove mentions of import/export functionality
  - Remove mentions of tagging and collections
  - Remove mentions of health monitoring, alerts, remediation
  - Update feature list to reflect current capabilities

Update CLAUDE.md:
  - Remove any references to deleted features
  - Update key files list if needed

Check docs/ directory (if exists):
  - Remove or update documentation for deleted features

Update any comments in kept code that reference deleted features.
```

### Task 3.6: Clean TODO.md and Tracking Files
**Agent 6**

```
In TODO.md, remove entries for deleted features:
  - All BUG-* entries referencing: graph, backup, tagging, tag, collection,
    health_scorer, health_scheduler, alert, remediation, capacity, archive,
    analytics, token_tracker
  - All REF-* entries referencing deleted modules
  - All FEAT-* entries for removed features

Count entries before and after for reporting.

Check other tracking files:
  - IN_PROGRESS.md - remove any in-progress items for deleted features
  - REVIEW.md - same
  - TESTING.md - same

Update CHANGELOG.md draft section if exists.
```

### Phase 3 Gate
- [ ] `ruff check src/ --select F401,F811,F841` - Clean (no dead code)
- [ ] `python -c "import src"` - No import errors
- [ ] `pytest tests/ --collect-only` - No collection errors
- [ ] `pytest tests/unit/ -x` - Unit tests pass
- [ ] No test files exist for deleted modules
- [ ] health_command.py imports cleanly
- [ ] README.md updated
- [ ] TODO.md entries removed (report count)
- [ ] Git commit: "SIMPLIFY-001: Cleanup tests and docs (Phase 3 complete)"

---

## Phase 4: Verification

**Goal:** Multi-pass verification that nothing was missed.

**Duration:** 2-3 hours
**Agents:** 4 parallel review agents, then 1 integration agent

### Task 4.1: Static Analysis Deep Dive
**Agent 1**

```
Run comprehensive static analysis:

1. Ruff full check:
   ruff check src/ --select ALL --ignore D,ANN,ERA
   - Document any issues found
   - Fix or justify each

2. Import verification:
   python -c "
   import ast
   import os
   for root, dirs, files in os.walk('src'):
       for f in files:
           if f.endswith('.py'):
               path = os.path.join(root, f)
               try:
                   with open(path) as file:
                       ast.parse(file.read())
                   print(f'OK: {path}')
               except SyntaxError as e:
                   print(f'ERROR: {path}: {e}')
   "

3. Circular import check:
   python -c "import src; print('No circular imports')"

4. Type checking (if mypy configured):
   mypy src/ --ignore-missing-imports

Output: Report all findings with PASS/FAIL/FIXED status
```

### Task 4.2: Reference Grep Verification
**Agent 2**

```
Exhaustive grep for any remaining references to removed modules.

Module references (should return ZERO results):
  grep -rn "from src\.graph" src/ tests/
  grep -rn "from src\.backup" src/ tests/
  grep -rn "from src\.tagging" src/ tests/
  grep -rn "from src\.analytics" src/ tests/
  grep -rn "import src\.graph" src/ tests/
  grep -rn "import src\.backup" src/ tests/
  grep -rn "import src\.tagging" src/ tests/
  grep -rn "import src\.analytics" src/ tests/

Class/function references (should return ZERO or justified results):
  grep -rn "HealthScorer" src/ tests/
  grep -rn "HealthScheduler" src/ tests/
  grep -rn "HealthJobs" src/ tests/
  grep -rn "AlertEngine" src/ tests/
  grep -rn "RemediationEngine" src/ tests/
  grep -rn "CapacityPlanner" src/ tests/
  grep -rn "TagManager" src/ tests/
  grep -rn "CollectionManager" src/ tests/
  grep -rn "AutoTagger" src/ tests/
  grep -rn "DependencyGraph" src/ tests/
  grep -rn "CallGraph" src/ tests/
  grep -rn "GraphGenerator" src/ tests/
  grep -rn "ArchiveExporter" src/ tests/
  grep -rn "ArchiveImporter" src/ tests/

String references in code (may have false positives - review each):
  grep -rn "health_score" src/ --include="*.py"
  grep -rn "dependency_graph" src/ --include="*.py"
  grep -rn "call_graph" src/ --include="*.py"

For each hit:
  - If in comment/docstring referencing deleted feature: REMOVE
  - If variable name collision (unrelated): JUSTIFY and KEEP
  - If actual reference to deleted code: FIX

Output: Report with line-by-line disposition
```

### Task 4.3: Full Test Suite Execution
**Agent 3**

```
Run complete test suite with detailed output:

1. Unit tests:
   pytest tests/unit/ -v --tb=short -x 2>&1 | tee test_unit.log

2. Integration tests:
   pytest tests/integration/ -v --tb=short -x 2>&1 | tee test_integration.log

3. Full suite with coverage:
   pytest tests/ --cov=src --cov-report=term-missing 2>&1 | tee test_full.log

4. Check for skipped tests mentioning removed features:
   grep -n "skip.*graph\|skip.*backup\|skip.*tag\|skip.*health" tests/**/*.py

5. Check test collection is clean:
   pytest tests/ --collect-only 2>&1 | grep -i "error\|warning"

For any failures:
  - Document the failure
  - Determine if it's related to removal
  - Fix or escalate

Output: Test results summary with PASS/FAIL counts
```

### Task 4.4: Smoke Test - Core Functionality
**Agent 4**

```
Manual verification that core functionality still works:

1. Server startup:
   python -c "from src.core.server import MemoryRAGServer; print('Server imports OK')"

2. MCP server startup:
   python -c "from src.mcp_server import create_mcp_server; print('MCP imports OK')"

3. Store operations (requires Qdrant running):
   - docker-compose up -d
   - Run: python -c "
     import asyncio
     from src.store import create_memory_store
     from src.config import get_config

     async def test():
         config = get_config()
         store = await create_memory_store(config)
         # Test basic connectivity
         health = await store.health_check()
         print(f'Store health: {health}')
         await store.close()

     asyncio.run(test())
     "

4. CLI health command:
   python -m src.cli.main health
   - Should run without import errors
   - Should report Qdrant status

5. Embedding generation:
   python -c "
   from src.embeddings.generator import EmbeddingGenerator
   gen = EmbeddingGenerator()
   print(f'Model: {gen.model_name}, Dim: {gen.embedding_dim}')
   "

Output: Smoke test report with PASS/FAIL for each check
```

### Task 4.5: Integration Review & Issue Resolution
**Agent 5 (runs after 4.1-4.4 complete)**

```
Collect and review all findings from Tasks 4.1-4.4:

1. Gather outputs:
   - Static analysis report from 4.1
   - Grep verification report from 4.2
   - Test results from 4.3
   - Smoke test report from 4.4

2. Create consolidated issue list:
   - List each issue found
   - Categorize: CRITICAL / MAJOR / MINOR
   - Assign disposition: FIX / DEFER / WONTFIX

3. Fix all CRITICAL and MAJOR issues:
   - Make necessary code changes
   - Re-run relevant verification
   - Document resolution

4. Create final verification report:
   - Summary of all checks
   - List of any deferred issues with justification
   - Confirmation that all gates pass
```

### Phase 4 Gate
- [ ] Static analysis clean (Task 4.1)
- [ ] Zero grep hits for removed modules (Task 4.2)
- [ ] All tests pass (Task 4.3)
- [ ] Smoke tests pass (Task 4.4)
- [ ] All CRITICAL/MAJOR issues resolved (Task 4.5)
- [ ] Verification report created
- [ ] Git commit: "SIMPLIFY-001: Verification complete (Phase 4)"

---

## Phase 5: Final Polish

**Goal:** Documentation, cleanup, and final commit.

**Duration:** 1-2 hours
**Agent:** 1 (solo, thorough)

### Task 5.1: Update CHANGELOG.md

Add comprehensive entry documenting the removal:

```markdown
## [Unreleased]

### Removed
- **SIMPLIFY-001: Feature Removal for Stability**
  - Removed dependency graph visualization (`src/graph/`)
    - DependencyGraphBuilder, CallGraphAnalyzer
    - Mermaid, DOT, JSON formatters
  - Removed import/export archive system (`src/backup/`)
    - BackupManager, RestoreManager
    - Archive scheduling
  - Removed tagging and collections system (`src/tagging/`)
    - TagManager, CollectionManager, AutoTagger
    - Hierarchical tag support
  - Removed health monitoring subsystem
    - HealthScorer, HealthScheduler, HealthJobs
    - LifecycleManager
  - Removed alerting and remediation (`src/monitoring/` partial)
    - AlertEngine, RemediationEngine, CapacityPlanner
    - HealthReporter
  - Removed analytics tracking (`src/analytics/`)
    - UsageTracker, TokenTracker
  - Removed CLI commands
    - health-dashboard, health-monitor, health-schedule
    - tags, collections, auto-tag
    - graph, backup (if existed)
  - Stats: ~10,000 LOC removed, ~115 bugs/REFs eliminated
  - SQLite tables reduced from 17 to ~4
```

### Task 5.2: Final TODO.md Cleanup

If not already done in Phase 3:

```
1. Count current entries:
   grep -c "^\- \[ \]" TODO.md

2. Remove entries for deleted features (script or manual):
   - Search for module names: graph, backup, tagging, tag, collection,
     health_scorer, health_scheduler, alert, remediation, capacity,
     archive, analytics, token_tracker, lifecycle_manager
   - Remove matching BUG-*, REF-*, FEAT-* entries

3. Count after cleanup:
   grep -c "^\- \[ \]" TODO.md

4. Report: "Removed X entries, Y remain"
```

### Task 5.3: Archive Obsolete planning_docs

Create archive directory and move obsolete docs:

```bash
mkdir -p planning_docs/archived_simplify001

# Move docs for removed features
mv planning_docs/FEAT-048_dependency_graph*.md planning_docs/archived_simplify001/
mv planning_docs/FEAT-038_data_export*.md planning_docs/archived_simplify001/
mv planning_docs/UX-033_memory_tagging*.md planning_docs/archived_simplify001/
mv planning_docs/FEAT-062_architecture_visualization*.md planning_docs/archived_simplify001/

# Check for others referencing removed features
grep -l "graph\|backup\|tagging\|health_scorer\|remediation" planning_docs/*.md
# Review and move as appropriate
```

### Task 5.4: Final Code Review

One last pass through key files to ensure quality:

```
Review these files for any remaining cleanup:
  - src/mcp_server.py - tool list should be clean
  - src/config.py - no orphaned fields
  - src/core/server.py - no dead methods
  - src/cli/__init__.py - clean exports
  - README.md - accurate feature list
  - CLAUDE.md - accurate description
```

### Task 5.5: Final Commit & Tag

```bash
# Stage all changes
git add -A

# Create final commit
git commit -m "$(cat <<'EOF'
SIMPLIFY-001: Remove graph, backup, tagging, and health monitoring

Major simplification to reduce bug surface and establish stable foundation.

Removed modules:
- src/graph/ (dependency/call graph visualization)
- src/backup/ (import/export archives)
- src/tagging/ (hierarchical tags, collections)
- src/analytics/ (usage/token tracking)

Removed from src/memory/:
- health_scheduler.py, health_scorer.py, health_jobs.py
- archive_exporter.py, archive_importer.py, archive_compressor.py
- graph_generator.py, dependency_graph.py
- lifecycle_manager.py

Removed from src/monitoring/:
- health_reporter.py, capacity_planner.py
- remediation.py, alert_engine.py

Removed CLI commands:
- health-dashboard, health-monitor, health-schedule
- tags, collections, auto-tag

Kept core functionality:
- Memory storage and semantic search
- Code indexing with file watching
- Embedding generation with cache
- Basic health checks (Qdrant, disk, memory)
- Performance metrics collection

Stats:
- ~10,000 LOC removed
- ~115 bugs/REFs eliminated
- SQLite tables: 17 -> 4

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)"

# Tag the completion
git tag -a simplify-001-complete -m "SIMPLIFY-001 feature removal complete"

# Verify
git log --oneline -3
git tag -l | grep simplify
```

### Task 5.6: Post-Completion Verification

Final sanity checks:

```bash
# Full test suite one more time
./scripts/test-isolated.sh tests/ -v

# Verify gates
python scripts/verify-complete.py

# Check nothing was missed
find src -name "*.py" | wc -l  # Should be significantly less than before
```

### Phase 5 Gate
- [ ] CHANGELOG.md has detailed removal entry
- [ ] TODO.md cleaned (report entry count reduction)
- [ ] planning_docs obsolete files archived
- [ ] Final code review complete
- [ ] Final commit created with comprehensive message
- [ ] Git tag `simplify-001-complete` created
- [ ] `./scripts/test-isolated.sh tests/ -v` passes
- [ ] `python scripts/verify-complete.py` passes

---

## Execution Summary

### Total Agent Allocation

| Phase | Parallel Agents | Sequential Steps | Est. Duration |
|-------|-----------------|------------------|---------------|
| Phase 1 | 6 | 0 | 2-3 hours |
| Phase 2 | 6 (Wave A) | 2 (Waves B, C) | 4-6 hours |
| Phase 3 | 6 | 0 | 3-4 hours |
| Phase 4 | 4 | 1 (integration) | 2-3 hours |
| Phase 5 | 1 | 0 | 1-2 hours |

**Total estimated: 12-18 hours of wall-clock time**
(Much faster than serial due to parallelism)

### Checkpoints & Rollback

| Checkpoint | Location | Purpose |
|------------|----------|---------|
| `simplify-001-checkpoint` | Before Phase 2 | Full rollback if critical issue |
| Phase 2 commit | After deletions | Partial rollback point |
| Phase 3 commit | After test cleanup | Partial rollback point |
| Phase 4 commit | After verification | Near-final state |
| `simplify-001-complete` | After Phase 5 | Final tagged release |

### Key Outputs

| Phase | Output Files |
|-------|--------------|
| 1 | `SIMPLIFY-001_import_map.md`, `SIMPLIFY-001_mcp_tools_to_remove.md`, `SIMPLIFY-001_cli_audit.md`, `SIMPLIFY-001_server_services_audit.md`, `SIMPLIFY-001_tests_to_remove.md`, `SIMPLIFY-001_config_sqlite_audit.md` |
| 4 | Verification report (inline or separate file) |
| 5 | Updated CHANGELOG.md, cleaned TODO.md |

---

## Risk Mitigation

### Risk: Hidden Dependencies
**Mitigation:** Phase 1 mapping catches these before any deletion.

### Risk: Breaking Core Functionality
**Mitigation:**
- Tests run after each phase
- Manual smoke test in Phase 4
- Can revert individual commits if needed

### Risk: Incomplete Removal
**Mitigation:**
- Grep verification in Phase 4
- Multiple agent reviews
- Static analysis catches unused code

### Risk: Merge Conflicts
**Mitigation:**
- All development paused during this effort
- Single-threaded merges to main
- Each phase is a clean commit

---

## Success Criteria

1. **Zero references** to removed modules in src/
2. **All tests pass** (excluding deleted test files)
3. **Static analysis clean** (ruff, mypy if used)
4. **Core functionality works:**
   - Store memory
   - Search memory
   - Index project
   - Health check (basic)
5. **Documentation updated** (CHANGELOG, TODO, README)
6. **Code reviewed** by at least one agent per phase

---

## Appendix: File Inventory

To be populated during Phase 1 with exact file lists.

### Files to Delete
```
TBD - Phase 1 output
```

### Files to Modify
```
TBD - Phase 1 output
```

### Tests to Delete
```
TBD - Phase 1 output
```

### Config Fields to Remove
```
TBD - Phase 1 output
```
