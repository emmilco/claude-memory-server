# TESTING - Merge Queue

Tasks that have passed code review and are awaiting testing and merge.

---

## Guidelines

- **Review Approved**: Code review complete, Reviewer approved
- **Testing**: Run targeted tests for changed modules (not full suite)
- **Merge Queue**: Serial merges to prevent conflicts
- **Full Suite**: Runs in CI after merge

## Merge Queue

### [BUG-086]: Health Scorer Distribution Calculation Can Hit Memory Limit
**Review Approved**: 2025-11-30
**Changed Files**: src/memory/health_scorer.py, tests/unit/test_health_scorer.py
**Tests to Run**: tests/unit/test_health_scorer.py
**Status**: Testing

### [BUG-092]: Orphaned Tag Associations After Memory Deletion
**Review Approved**: 2025-11-30
**Changed Files**: src/services/memory_service.py, src/tagging/tag_manager.py, src/core/server.py
**Tests to Run**: tests/unit/test_memory_service.py, tests/unit/test_tag_manager.py
**Status**: Testing

### [BUG-101]: Backup Cleanup Race Condition with Scheduler
**Review Approved**: 2025-11-30
**Changed Files**: src/backup/scheduler.py, src/cli/backup_command.py, src/backup/file_lock.py (new)
**Tests to Run**: tests/unit/test_scheduler.py, tests/unit/test_backup_command.py
**Status**: Testing

### [BUG-103]: Export JSON Missing Schema Version Validation
**Review Approved**: 2025-11-30
**Changed Files**: src/backup/importer.py
**Tests to Run**: tests/unit/test_importer.py
**Status**: Testing

### [BUG-156]: Index Out of Range Errors in Result Processing
**Review Approved**: 2025-11-30
**Changed Files**: src/store/qdrant_store.py
**Tests to Run**: tests/unit/test_qdrant_store.py
**Status**: Testing

---

## Recently Merged (2025-12-01)

- [x] BUG-409: Weekly Report Missing Alert History Comparison - MERGED
- [x] BUG-410: Call Graph Store Never Closed - Resource Leak - MERGED
- [x] BUG-411: Add validation for hybrid_fusion_method config field - MERGED
- [x] BUG-432: Clarified filter_by_depth Documentation - MERGED
- [x] BUG-435: Archive Import Overwrites Conflict Without Validation - MERGED
- [x] BUG-446: Orphaned Tag Associations (Duplicate of BUG-092) - MERGED

*See CHANGELOG.md for details.*

---

## Testing Process

1. **Navigate**: `cd .worktrees/{TASK_ID}`
2. **Sync**: `git fetch origin main && git merge origin/main`
3. **Identify**: `git diff --name-only main...HEAD` to see changed files
4. **Test**: Run targeted tests for changed modules
   ```bash
   pytest tests/unit/test_<module>.py -v
   pytest tests/integration/ -k "<keyword>"
   ```
5. **Fix**: Own any test failures, fix in worktree
6. **Report**: Tests passed/failed, which tests ran

## Merge Process (Serial)

1. **Wait**: For turn in merge queue (Orchestrator coordinates)
2. **Merge**:
   ```bash
   cd ../..  # back to main repo
   git checkout main && git pull origin main
   git merge --no-ff {TASK_ID}
   git push origin main
   ```
3. **Cleanup**:
   ```bash
   git worktree remove .worktrees/{TASK_ID}
   git branch -d {TASK_ID}
   ```
4. **Update**: Remove from this file (entry already in CHANGELOG.md)

---

## Task Template

```markdown
### [TASK-XXX]: Task Title
**Review Approved**: YYYY-MM-DD
**Changed Files**: file1.py, file2.py
**Tests to Run**: tests/unit/test_file1.py, tests/unit/test_file2.py
**Status**: Queued | Testing | Ready to Merge | Merging
**Tester**: Agent name (if assigned)

**Notes**:
- Tests passed/failed
- Any fixes made
```

---

## Batch Merge (Optional)

Non-conflicting tasks (disjoint files) can be merged together:

1. Identify tasks touching different files
2. All tests pass individually
3. Merge all to main in sequence (no pull between)
4. Single push at end
5. If any merge conflicts: fall back to serial

**Batch candidates must have no file overlap in `Changed Files`.**
