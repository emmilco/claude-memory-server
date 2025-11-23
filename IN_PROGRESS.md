# IN_PROGRESS - Active Work

**Maximum Concurrent Tasks: 6**
**Current Active: 1/6**

---

## Guidelines

- **Task Limit**: Maximum 6 concurrent tasks to maintain focus and quality
- **Task Format**: `[TASK-ID]: Brief description`
- **Assignment**: Include assigned agent/developer if working in team
- **Status Updates**: Update daily with progress notes
- **Completion**: Move to REVIEW.md when ready for review, then to CHANGELOG.md when merged

## Active Tasks

### [FEAT-056]: Advanced Filtering & Sorting
**Started**: 2025-11-23
**Assigned**: Backend Engineer (Claude Code Agent)
**Branch**: .worktrees/FEAT-056
**Blocked By**: None
**Status**: In Progress - Re-implementing after FEAT-058 conflict

**Progress Notes**:
- 2025-11-23: Discovered FEAT-056 was merged (d2614e1) but reverted by FEAT-058 merge (ed12a21)
- 2025-11-23: FEAT-058 overwrote search_code signature, removing FEAT-056 parameters
- 2025-11-23: Need to re-add: file_pattern (glob), complexity_min/max, line_count_min/max, modified_after/before, sort_by, exclude_patterns
- 2025-11-23: Must preserve FEAT-058 parameters: pattern, pattern_mode

**Next Steps**:
- [ ] Update src/core/server.py - Add FEAT-056 parameters to search_code signature
- [ ] Implement glob pattern matching logic
- [ ] Implement complexity filtering logic
- [ ] Implement date range filtering logic
- [ ] Implement sorting logic
- [ ] Update src/mcp_server.py - Update MCP tool schema
- [ ] Remove skip markers from tests/unit/test_advanced_filtering.py
- [ ] Run tests to verify implementation
- [ ] Update CHANGELOG.md
- [ ] Run verify-complete.py

**See**: planning_docs/FEAT-056_advanced_filtering_plan.md, TODO.md line 263

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
