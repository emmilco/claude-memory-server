# Task Workflow - Complete Lifecycle

Complete guide to the task lifecycle from planning to completion in the Claude Memory RAG Server project.

---

## Table of Contents

1. [Workflow Overview](#workflow-overview)
2. [Task States](#task-states)
3. [Detailed Workflow](#detailed-workflow)
4. [Git Worktree Workflow](#git-worktree-workflow)
5. [Quality Gates](#quality-gates)
6. [Multi-Agent Coordination](#multi-agent-coordination)
7. [Common Scenarios](#common-scenarios)

---

## Workflow Overview

```
┌─────────────┐
│   TODO.md   │  ← Planned work (not started)
└──────┬──────┘
       │ 1. Pick task
       │ 2. Create worktree
       ▼
┌─────────────────┐
│ IN_PROGRESS.md  │  ← Active work (max 6 concurrent)
└──────┬──────────┘
       │ 3. Implement
       │ 4. Test
       │ 5. Verify
       ▼
┌─────────────┐
│  REVIEW.md  │  ← Awaiting review
└──────┬──────┘
       │ 6. Review
       │ 7. Approve
       │ 8. Merge
       ▼
┌──────────────┐
│ CHANGELOG.md │  ← Completed work
└──────────────┘
```

**File Purposes:**
- **TODO.md**: Backlog of planned work with priorities
- **IN_PROGRESS.md**: Active tasks (max 6 to maintain focus)
- **REVIEW.md**: Implementation-complete, awaiting approval
- **CHANGELOG.md**: Historical record of completed work

---

## Task States

### TODO (Planned)

**Criteria:**
- Work is planned but not started
- Has unique ID (FEAT-XXX, BUG-XXX, etc.)
- Priority assigned
- Planning document may exist in `planning_docs/`

**Format in TODO.md:**
```markdown
- [ ] **FEAT-056**: Advanced Filtering & Sorting (~1 week) 🔥🔥
  - **Current Gap:** No way to filter by file pattern, complexity, dates
  - **Problem:** QA review needed grep for pattern matching
  - **Proposed Solution:**
    - [ ] Add `file_pattern` parameter
    - [ ] Add `complexity_min/max` filters
    - [ ] Add date range filters
  - **Impact:** Eliminates 40% of grep usage
  - **Tests:** 15-20 tests
  - **See:** planning_docs/FEAT-056_advanced_filtering_plan.md
```

### IN PROGRESS (Active)

**Criteria:**
- Work has started
- Git worktree created
- Agent/developer assigned
- Progress tracked with notes

**Maximum:** 6 concurrent tasks (enforced)

**Format in IN_PROGRESS.md:**
```markdown
### [FEAT-056]: Advanced Filtering & Sorting
**Started**: 2025-11-22
**Assigned**: Agent Alpha
**Branch**: .worktrees/FEAT-056
**Blocked By**: None
**Status**: In Progress

**Progress Notes**:
- 2025-11-22: Created worktree, reviewed planning doc
- 2025-11-22: Implemented file_pattern filter (40% complete)
- 2025-11-23: Added complexity filters, writing tests

**Next Steps**:
- [ ] Add date range filters
- [ ] Complete test suite (15-20 tests)
- [ ] Update API documentation
- [ ] Run verify-complete.py

**See**: planning_docs/FEAT-056_advanced_filtering_plan.md
```

### REVIEW (Complete, Awaiting Approval)

**Criteria:**
- Implementation complete
- All tests passing
- Documentation updated
- `verify-complete.py` passes

**Format in REVIEW.md:**
```markdown
### [FEAT-056]: Advanced Filtering & Sorting
**Completed**: 2025-11-24
**Author**: Agent Alpha
**Branch**: .worktrees/FEAT-056
**Type**: Feature

**Changes**:
- Added 5 new filter parameters to search_code()
- Added 3 new sort options
- Enhanced search result ranking

**Testing**:
- [x] Unit tests added (20 tests)
- [x] Integration tests added (5 tests)
- [x] All tests passing (2,765/2,765)
- [x] Coverage improved (71.2% → 72.8%)

**Verification**:
- [x] `python scripts/verify-complete.py` passes
- [x] Manual testing completed
- [x] Documentation updated
- [x] No breaking changes

**Review Checklist**:
- [ ] Code quality acceptable
- [ ] Test coverage adequate
- [ ] Documentation clear
- [ ] No security issues

**See**: planning_docs/FEAT-056_advanced_filtering_plan.md
```

### CHANGELOG (Completed)

**Criteria:**
- Code merged to main
- Review approved
- Historical record

**Format in CHANGELOG.md:**
```markdown
## 2025-11-24

- **FEAT-056**: Advanced Filtering & Sorting ✅ **COMPLETE**
  - Added file_pattern, complexity, and date range filters to search_code()
  - Added 5 sort options: relevance, complexity, size, recency, importance
  - Eliminates 40% of grep usage, 3x faster targeted searches
  - **Testing:** 25 tests (20 unit, 5 integration), all passing
  - **Coverage:** 72.8% (improved from 71.2%)
  - **See:** planning_docs/FEAT-056_advanced_filtering_plan.md
```

---

## Detailed Workflow

### Phase 1: Planning

**1. Select Task from TODO.md**

Look for:
- High priority items (🔥🔥🔥)
- Tasks not blocked by others
- Tasks aligned with your expertise

**2. Review Planning Document**

If `planning_docs/TASK-XXX_*.md` exists:
- Read the implementation plan
- Understand technical approach
- Note any dependencies

If planning doc doesn't exist and task is complex:
- Create one following the template in `planning_docs/README.md`
- Break down into phases
- Identify risks

**3. Check Dependencies**

- Is this blocked by other tasks?
- Does it require new dependencies?
- Will it affect other in-progress work?

### Phase 2: Setup

**4. Create Git Worktree**

```bash
# From main repository directory
TASK_ID="FEAT-056"  # Your task ID
git worktree add .worktrees/$TASK_ID -b $TASK_ID

# Navigate to worktree
cd .worktrees/$TASK_ID

# Verify isolation
git branch  # Should show FEAT-056
git status  # Should show clean worktree
```

**Why Worktrees?**
- Isolates your work from others
- Allows multiple tasks in parallel
- Easy to switch contexts
- Prevents merge conflicts

**5. Update IN_PROGRESS.md**

```bash
# In your worktree
# Add your task to IN_PROGRESS.md
# Check capacity: max 6 tasks

# Commit the update
git add IN_PROGRESS.md
git commit -m "Start FEAT-056: Advanced Filtering & Sorting"
```

### Phase 3: Implementation

**6. Develop Following Existing Patterns**

```bash
# Read similar code first
# Follow existing conventions
# Use type hints
# Write docstrings

# Example:
src/search/filters.py  # New module
tests/unit/test_filters.py  # New tests
```

**7. Write Tests Alongside Code**

- **Unit tests**: Test individual functions
- **Integration tests**: Test feature end-to-end
- **Aim for 80%+ coverage** for new code

```bash
# Run tests frequently
pytest tests/unit/test_filters.py -v

# Check coverage
pytest tests/unit/test_filters.py --cov=src.search.filters
```

**8. Update Documentation**

As you implement:
- Update docstrings
- Add examples to `docs/API.md` if API changes
- Update `README.md` if user-facing changes
- Keep planning doc updated with progress

### Phase 4: Verification

**9. Run Comprehensive Verification**

```bash
# From your worktree
python scripts/verify-complete.py
```

This checks:
- All tests passing (100% pass rate)
- Coverage targets met (80%+ for core)
- No syntax errors
- Documentation updated

**10. Manual Testing**

Test the feature manually:
```bash
# Index a test project
python -m src.cli index ./examples/sample_project --project-name test

# Test your new feature
python -m src.cli search "query" --project test --complexity-min 5
```

**11. Update CHANGELOG.md**

Add an entry under "Unreleased" or today's date:
```markdown
## 2025-11-24

- **FEAT-056**: Advanced Filtering & Sorting ✅ **COMPLETE**
  - Summary of changes
  - Impact statement
  - Test coverage
```

### Phase 5: Review

**12. Move to REVIEW.md**

Update IN_PROGRESS.md: remove your entry
Add to REVIEW.md: complete entry with all details

```bash
# Commit changes
git add IN_PROGRESS.md REVIEW.md CHANGELOG.md
git commit -m "FEAT-056: Ready for review"
```

**13. Self-Review**

Before requesting peer review:
- Read your own code changes
- Check for commented-out code
- Verify naming consistency
- Ensure no debugging print statements

**14. Peer Review (if team)**

If working with other agents/developers:
- Request review
- Address feedback
- Update code as needed
- Re-run verification

### Phase 6: Merge

**15. Merge to Main**

```bash
# Return to main repository
cd ../..  # Back to root

# Sync main with latest changes
git checkout main
git pull origin main

# Merge your feature branch
git merge --no-ff FEAT-056

# If conflicts occur, resolve them
# (See ADVANCED.md for conflict resolution)

# Push to remote
git push origin main
```

**16. Clean Up**

```bash
# Remove worktree
git worktree remove .worktrees/FEAT-056

# Delete local branch
git branch -d FEAT-056

# Optionally delete remote branch
git push origin --delete FEAT-056
```

**17. Update TODO.md**

Mark the task as complete:
```markdown
- [x] **FEAT-056**: Advanced Filtering & Sorting ✅ **COMPLETE**
```

Or remove it if it's moved to CHANGELOG.md.

---

## Git Worktree Workflow

### Creating Worktrees

```bash
# Standard workflow
TASK_ID="FEAT-XXX"
git worktree add .worktrees/$TASK_ID -b $TASK_ID
cd .worktrees/$TASK_ID
```

### Managing Worktrees

```bash
# List all worktrees
git worktree list

# Remove a worktree (after merging)
git worktree remove .worktrees/FEAT-XXX

# Prune stale worktree references
git worktree prune
```

### Worktree Best Practices

✅ **Do:**
- Create one worktree per task
- Use task ID as branch name
- Commit regularly in worktree
- Clean up after merging

❌ **Don't:**
- Mix multiple tasks in one worktree
- Edit files in main repo while worktree active
- Leave worktrees around after completion
- Share worktrees between agents

**See ADVANCED.md for:**
- Worktree conflict resolution
- Syncing worktrees with main
- Advanced worktree scenarios

---

## Quality Gates

### Definition of Done

A task is **complete** when:

✅ **Implementation**
- All planned features implemented
- Code follows existing patterns
- No hardcoded values or debug code
- Proper error handling

✅ **Testing**
- Unit tests written (isolated components)
- Integration tests written (end-to-end)
- All tests passing (100% pass rate)
- Coverage ≥80% for new code
- Manual testing completed

✅ **Documentation**
- Code has docstrings
- API changes documented in `docs/API.md`
- User-facing changes in `README.md`
- CHANGELOG.md updated
- Planning doc updated (if exists)

✅ **Verification**
- `python scripts/verify-complete.py` passes
- No linting errors
- No type checking errors (if using mypy)

✅ **Review**
- Self-review completed
- Peer review approved (if team)
- Feedback addressed

### Verification Script

```bash
# Comprehensive verification
python scripts/verify-complete.py

# What it checks:
# 1. All tests pass
# 2. Coverage targets met
# 3. No syntax errors
# 4. Documentation updated
# 5. No security issues
```

---

## Multi-Agent Coordination

### Parallel Work

**Maximum 6 concurrent tasks** to:
- Maintain focus and quality
- Reduce merge conflicts
- Enable context switching
- Track progress effectively

**Coordination Rules:**
1. **Check IN_PROGRESS.md** before starting work
2. **Avoid overlapping files** when possible
3. **Communicate blockers** in IN_PROGRESS.md
4. **Merge frequently** to reduce conflict risk

### Avoiding Conflicts

**High-Risk Files:**
- `src/core/server.py` (5,192 lines, often modified)
- `src/mcp_server.py` (MCP tool registration)
- `TODO.md`, `CHANGELOG.md` (frequently updated)

**Strategies:**
1. **Coordinate timing** - Don't modify same file simultaneously
2. **Small changesets** - Smaller PRs = fewer conflicts
3. **Sync frequently** - Rebase/merge main regularly
4. **Clear communication** - Update IN_PROGRESS.md with file list

### Resolving Conflicts

If conflicts occur during merge:

```bash
# Conflicts appear in files
git status  # Shows conflicted files

# Manually resolve each file
# Look for <<<<<<< HEAD, =======, >>>>>>> markers

# Mark as resolved
git add <resolved-file>

# Complete merge
git commit
```

**See ADVANCED.md for detailed conflict resolution strategies.**

---

## Common Scenarios

### Scenario 1: Quick Bug Fix

```bash
# 1. Create worktree
git worktree add .worktrees/BUG-XXX -b BUG-XXX

# 2. Fix bug + write regression test
# 3. Run tests
pytest tests/unit/test_module.py -v

# 4. Verify
python scripts/verify-complete.py

# 5. Update CHANGELOG.md
# 6. Merge to main (can skip REVIEW.md for trivial fixes)
git checkout main && git merge --no-ff BUG-XXX

# 7. Clean up
git worktree remove .worktrees/BUG-XXX
```

### Scenario 2: Large Feature (Multi-Week)

```bash
# 1. Create planning doc first
# planning_docs/FEAT-XXX_detailed_plan.md

# 2. Break into phases in planning doc

# 3. Create worktree
git worktree add .worktrees/FEAT-XXX -b FEAT-XXX

# 4. Implement phase by phase
#    - Commit after each phase
#    - Update planning doc with progress
#    - Sync with main periodically (git merge origin/main)

# 5. When complete, full verification
python scripts/verify-complete.py

# 6. Move to REVIEW.md (wait for approval)

# 7. Merge to main
```

### Scenario 3: Blocked Task

```markdown
### [FEAT-XXX]: My Feature
**Status**: Blocked
**Blocked By**: [FEAT-YYY]

**Progress Notes**:
- 2025-11-22: Started, discovered dependency on FEAT-YYY
- Implemented 40% of feature (parts that don't depend on FEAT-YYY)
- Waiting for FEAT-YYY to complete

**Next Steps**:
- [ ] Monitor FEAT-YYY progress
- [ ] Complete implementation when unblocked
```

**When unblocked:**
- Update status to "In Progress"
- Resume work
- Complete implementation

### Scenario 4: Multiple Agents on Related Tasks

**Agent A**: Working on FEAT-056 (filtering)
**Agent B**: Working on FEAT-057 (UX improvements)

**Both modify**: `src/core/server.py`

**Strategy:**
1. **Communicate**: Note file overlap in IN_PROGRESS.md
2. **Coordinate timing**: Agent A merges first
3. **Sync frequently**: Agent B rebases on Agent A's changes
4. **Small commits**: Easier to integrate

---

## Next Steps

After understanding the workflow:

1. **Try it**: Pick a small task from TODO.md and follow the workflow
2. **Read ADVANCED.md**: Learn conflict resolution and advanced scenarios
3. **Review CLAUDE.md**: Understand multi-agent coordination in depth
4. **Check TESTING_GUIDE.md**: Master testing strategies

**Questions?** See `DEBUGGING.md` or ask in project discussions.
