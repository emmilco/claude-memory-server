# TESTING - Merge Queue

Tasks that have passed code review and are awaiting testing and merge.

---

## Guidelines

- **Review Approved**: Code review complete, Reviewer approved
- **Testing**: Run targeted tests for changed modules (not full suite)
- **Merge Queue**: Serial merges to prevent conflicts
- **Full Suite**: Runs in CI after merge

## Merge Queue

*No tasks currently in merge queue.*

---

## Recently Merged

*Moved to CHANGELOG.md after merge.*

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
