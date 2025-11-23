# IN_PROGRESS - Active Work

**Maximum Concurrent Tasks: 6**
**Current Active: 0/6**

---

## Guidelines

- **Task Limit**: Maximum 6 concurrent tasks to maintain focus and quality
- **Task Format**: `[TASK-ID]: Brief description`
- **Assignment**: Include assigned agent/developer if working in team
- **Status Updates**: Update daily with progress notes
- **Completion**: Move to REVIEW.md when ready for review, then to CHANGELOG.md when merged

## Active Tasks

<!-- No tasks currently in progress -->

---

## Task Template

```markdown
### [TASK-XXX]: Task Title
**Started**: YYYY-MM-DD
**Assigned**: Agent/Developer name
**Branch**: worktrees/TASK-XXX
**Blocked By**: None | [TASK-YYY]
**Status**: In Progress | Blocked | Nearly Complete

**Progress Notes**:
- YYYY-MM-DD: Started work, created worktree
- YYYY-MM-DD: Implemented X, discovered Y
- YYYY-MM-DD: Fixed issue Z, 80% complete

**Next Steps**:
- [ ] Complete remaining implementation
- [ ] Write tests
- [ ] Update documentation
- [ ] Run verify-complete.py

**See**: planning_docs/TASK-XXX_*.md
```

---

## Capacity Management

When at 6/6 capacity:
1. **Complete existing tasks** before starting new ones
2. **Move to REVIEW.md** when ready for review
3. **Prioritize** completing nearly-done tasks over starting new work
4. **Coordinate** with other agents to avoid conflicts

## Workflow

```
TODO.md → IN_PROGRESS.md → REVIEW.md → CHANGELOG.md
           (start work)      (ready)     (merged)
```
