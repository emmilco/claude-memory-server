# Plan: Achieve 100% Test Pass Rate

**Goal:** Fix remaining 177 failures + 64 errors = 241 test issues
**Strategy:** Divide into 5 parallel workstreams by failure category
**Current:** 90.6% pass rate (2,424 / 2,677)
**Target:** 100% pass rate (2,677 / 2,677)

---

## Failure Pattern Analysis

From sampling test failures, the main categories are:

1. **SQLite Module Import Errors** (~20-30 failures)
   - Source files still importing removed `src.store.sqlite_store`
   - Affects backup/export functionality

2. **Test Isolation Issues** (~40-60 failures)
   - Tests expecting empty Qdrant collections but finding leftover data
   - Health dashboard tests especially affected

3. **Logic/Assertion Bugs** (~30-50 failures)
   - delete_file_index returns wrong count
   - Incorrect test expectations vs actual behavior

4. **Configuration/Fixture Issues** (~30-50 failures)
   - Tests still using deprecated config options
   - Fixture setup/teardown problems

5. **Integration/Race Conditions** (~40-60 failures)
   - Async timing issues
   - Resource cleanup problems
   - Background task coordination

---

## 5-Agent Parallel Workstream Plan

### Agent 1: Remove SQLite Imports from Source Code
**Task ID:** FIX-SQLITE-IMPORTS
**Estimated Impact:** ~20-40 test fixes
**Priority:** HIGH (blocking backup/export tests)

**Files to Fix:**
1. `src/backup/exporter.py` - Remove SQLite import, use only Qdrant
2. `src/store/__init__.py` - Remove SQLite exports
3. `src/store/factory.py` - Remove SQLite from store factory

**Approach:**
- Remove all `from src.store.sqlite_store import` lines
- Update any code that references SQLite classes
- Ensure backup/export works with Qdrant only
- Run tests: `pytest tests/unit/test_backup_export.py -v`

**Success Criteria:**
- No "ModuleNotFoundError: No module named 'src.store.sqlite_store'" errors
- All backup/export tests pass

---

### Agent 2: Fix Test Isolation (Qdrant Collection Cleanup)
**Task ID:** FIX-TEST-ISOLATION
**Estimated Impact:** ~40-60 test fixes
**Priority:** HIGH (widespread issue)

**Problem:**
Tests expecting empty database but finding 174+ memories from previous tests.

**Approach:**
1. **Add unique collection names per test:**
   ```python
   import uuid
   collection_name = f"test_{test_name}_{uuid.uuid4().hex[:8]}"
   ```

2. **Add proper cleanup in fixtures:**
   ```python
   @pytest_asyncio.fixture
   async def temp_db():
       collection = f"test_{uuid.uuid4().hex[:8]}"
       config = ServerConfig(qdrant_collection_name=collection)
       store = QdrantMemoryStore(config)
       await store.initialize()
       yield store
       await store.close()
       # Clean up collection
       if store.client:
           try:
               store.client.delete_collection(collection)
           except:
               pass
   ```

**Files to Fix:**
- `tests/integration/test_health_dashboard_integration.py`
- `tests/integration/test_indexing_integration.py`
- All test fixtures using shared Qdrant collections

**Success Criteria:**
- Tests pass consistently on multiple runs
- No "assert 174 == 0" type failures

---

### Agent 3: Fix Logic Bugs and Incorrect Assertions
**Task ID:** FIX-LOGIC-BUGS
**Estimated Impact:** ~30-50 test fixes
**Priority:** MEDIUM

**Examples Found:**
1. `test_delete_file_index` - expects 15 deletions but gets 4
2. Category mismatches
3. Count discrepancies

**Approach:**
1. Run each failing test individually with verbose output
2. Determine if bug is in:
   - Test expectation (fix test)
   - Implementation logic (fix source code)
3. Fix whichever is incorrect
4. Add regression test

**Files to Investigate:**
- `tests/integration/test_indexing_integration.py::test_delete_file_index`
- Any test with "AssertionError: assert X == Y" where X and Y differ

**Success Criteria:**
- All assertion-based failures resolved
- Logic bugs documented and fixed

---

### Agent 4: Fix Configuration and Fixture Issues
**Task ID:** FIX-CONFIG-FIXTURES
**Estimated Impact:** ~30-50 test fixes
**Priority:** MEDIUM

**Issues:**
- Deprecated config options still in use
- Fixture setup/teardown not working
- Missing dependencies in test fixtures

**Approach:**
1. Audit all `@pytest.fixture` and `@pytest_asyncio.fixture` definitions
2. Ensure proper cleanup (yield with try/finally)
3. Check for deprecated config usage
4. Verify fixture dependencies are loaded in correct order

**Files to Fix:**
- All `conftest.py` files
- Test fixtures using old config patterns
- Tests with ERROR status (vs FAILED)

**Success Criteria:**
- All ERROR tests converted to either PASS or FAILED
- Fixture setup/teardown works reliably

---

### Agent 5: Fix Integration and Race Conditions
**Task ID:** FIX-INTEGRATION-RACE
**Estimated Impact:** ~40-60 test fixes
**Priority:** MEDIUM-LOW

**Issues:**
- Async/await timing problems
- Resource cleanup races
- Background task coordination

**Approach:**
1. Add proper `await` for async operations
2. Use `asyncio.wait_for()` with timeouts
3. Add cleanup delays where needed
4. Fix resource leaks (file handles, connections)

**Common Patterns:**
```python
# Bad
background_task()  # Fire and forget

# Good
await background_task()  # Wait for completion

# Or
task = asyncio.create_task(background_task())
await asyncio.sleep(0.1)  # Let it start
await task  # Wait for completion
```

**Files to Fix:**
- Tests with intermittent failures
- Tests involving background workers
- Tests with file watchers or schedulers

**Success Criteria:**
- All async tests pass reliably
- No race condition failures

---

## Execution Plan

### Phase 1: Launch All 5 Agents in Parallel
```bash
# Agent 1
git worktree add .worktrees/FIX-SQLITE-IMPORTS -b FIX-SQLITE-IMPORTS

# Agent 2
git worktree add .worktrees/FIX-TEST-ISOLATION -b FIX-TEST-ISOLATION

# Agent 3
git worktree add .worktrees/FIX-LOGIC-BUGS -b FIX-LOGIC-BUGS

# Agent 4
git worktree add .worktrees/FIX-CONFIG-FIXTURES -b FIX-CONFIG-FIXTURES

# Agent 5
git worktree add .worktrees/FIX-INTEGRATION-RACE -b FIX-INTEGRATION-RACE
```

### Phase 2: Merge and Verify
1. Merge each branch as completed
2. Run full test suite after each merge
3. Track progress: target is 2,677 / 2,677 (100%)

### Phase 3: Final Validation
```bash
# Run full test suite 3 times to ensure stability
pytest tests/ -v
pytest tests/ -v
pytest tests/ -v

# Should get 100% pass rate on all 3 runs
```

---

## Success Metrics

- **Current:** 2,424 / 2,677 = 90.6%
- **Target:** 2,677 / 2,677 = 100.0%
- **Gap:** 253 tests to fix

**Estimated Agent Impact:**
- Agent 1: +20-40 tests (backup/export)
- Agent 2: +40-60 tests (isolation)
- Agent 3: +30-50 tests (logic)
- Agent 4: +30-50 tests (config)
- Agent 5: +40-60 tests (async)
- **Total:** +160-260 tests (sufficient to reach 100%)

---

## Risk Mitigation

1. **Overlapping Fixes:** Some issues may span multiple categories
   - Agents should communicate via CHANGELOG.md
   - Merge conflicts resolved by keeping both fixes

2. **New Issues Discovered:** Fixing one test may break another
   - Run full test suite after each agent completes
   - Document any new issues found

3. **Time Constraints:** Some issues may be more complex than estimated
   - Prioritize HIGH items first
   - Medium/Low items can be follow-up

---

**Created:** 2025-11-21
**Status:** Ready to execute
**Next Step:** Launch all 5 agents in parallel
