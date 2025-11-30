# Multi-Agent Orchestration Workflow

This document describes the orchestration workflow for parallel task execution using multiple Claude agents.

## Pipeline Overview

```
TODO.md → IN_PROGRESS.md → REVIEW.md → TESTING.md → CHANGELOG.md
            │                  │            │
        Task Agents        Reviewers    Testers
        (implement)       (code review) (test → merge queue)
```

## Roles & Responsibilities

### 1. Orchestrator (Main Session)

**Count:** 1

**Responsibilities:**
- Run pre-flight validation before spawning agents
- Pick tasks from TODO.md based on priority
- Move tasks to IN_PROGRESS.md **before** spawning agents
- Update tracking files (IN_PROGRESS.md, REVIEW.md, TESTING.md)
- Spawn up to 6 agents in parallel (shared pool across all roles)
- Coordinate merge queue (serial merges)
- Handle escalations from failed retries
- Monitor progress, launch new agents as capacity opens
- Report status to user

**Does NOT:**
- Implement fixes directly (delegates to agents)
- Run tests (delegates to Testers)

---

### 2. Task Agents

**Count:** Up to 6 in parallel (shared pool)

**Responsibilities:**
- Create git worktree for assigned task: `git worktree add .worktrees/$TASK_ID -b $TASK_ID`
- Read relevant files, understand the issue
- Implement the fix
- Update CHANGELOG.md under "Unreleased" section
- Commit changes with clear message
- Report: what was found, what was fixed, files changed

**Does NOT:**
- Run tests (Tester's job)
- Merge to main (Tester's job)

**Prompt Template:**
```
**ROLE: TASK AGENT** (15 min max)
**TASK: {TASK_ID}** - {Description}

**HARDENING SPRINT:** Leave NO tech debt.

**Problem:** {Problem description}
**Location:** {file:line references}
**Required Fix:** {Fix description}

**INSTRUCTIONS:**
1. Create worktree: `git worktree add .worktrees/{TASK_ID} -b {TASK_ID}`
2. Read relevant files
3. Implement fix
4. Update CHANGELOG.md under "Unreleased" section
5. Commit all changes
6. DO NOT run tests, DO NOT merge
7. Report: what found, what fixed, files changed
```

---

### 3. Reviewers

**Count:** Up to 6 in parallel (shared pool)

**Responsibilities:**
- Navigate to worktree: `cd .worktrees/$TASK_ID`
- Code review the changes
- Check code quality, patterns, anti-patterns
- Fix any issues found (style, logic, edge cases)
- Commit review fixes if needed
- Evaluate: did the Task Agent do what was asked?
- Report: review findings, fixes made, ready for testing (yes/no)

**Does NOT:**
- Run full test suite (Tester's job)
- Merge to main (Tester's job)

**Prompt Template:**
```
**ROLE: REVIEWER** (10 min max)
**TASK: {TASK_ID}** - {Description}
**WORKTREE:** .worktrees/{TASK_ID}

**REVIEW CHECKLIST:**
1. Navigate to worktree
2. Review all changes: `git diff main...HEAD`
3. Check code quality:
   - Correct fix for the issue?
   - Edge cases handled?
   - No new bugs introduced?
   - Code style consistent?
   - Comments/docstrings if needed?
4. Fix any issues found, commit fixes
5. DO NOT run tests, DO NOT merge
6. Report: review findings, fixes made, ready for testing (yes/no)
```

---

### 4. Testers

**Count:** Multiple in parallel for testing, serialized for merging

**Responsibilities:**
- **Testing phase (parallel):** Run tests in assigned worktrees
- **Merge phase (serial):** Queue for merge, one at a time

**Testing Phase:**
- Navigate to worktree: `cd .worktrees/$TASK_ID`
- Pull latest from main: `git fetch origin main && git merge origin/main`
- Run **targeted tests** based on changed files:
  ```bash
  # Identify changed files
  git diff --name-only main...HEAD

  # Run related tests (examples)
  pytest tests/unit/test_<module>.py -v      # Unit tests for changed module
  pytest tests/integration/ -k "<keyword>"   # Integration tests by keyword
  ```
- Fix any test failures (own them!)
- Report: tests passed/failed, files tested, ready for merge queue

**Why targeted testing:**
- Faster feedback (seconds vs minutes)
- Reduces context needed by Tester
- Full suite runs in CI after merge

**Merge Phase (serial):**
- Wait for turn in merge queue
- `git checkout main && git pull origin main`
- Merge: `git merge --no-ff $TASK_ID`
- Push: `git push origin main`
- Cleanup: `git worktree remove .worktrees/$TASK_ID && git branch -d $TASK_ID`

**Batch Merge Option:** Non-conflicting tasks (different files) can be merged together:
1. Identify tasks touching disjoint files
2. Merge all to main in sequence (no pull between)
3. Single push at end
4. If any merge conflicts: fall back to serial

**Prompt Template:**
```
**ROLE: TESTER** (15 min max)
**TASK: {TASK_ID}** - {Description}
**WORKTREE:** .worktrees/{TASK_ID}
**CHANGED FILES:** {list of files from Task Agent report}

**INSTRUCTIONS:**
1. cd .worktrees/{TASK_ID}
2. git fetch origin main && git merge origin/main
3. Identify tests related to changed files
4. Run targeted tests (NOT full suite)
5. Fix any test failures
6. Report: tests passed/failed, which tests ran, ready for merge

(Orchestrator handles merge queue coordination)
(Full test suite runs in CI after merge)
```

---

## Tracking Files

| Stage | File | Who Updates |
|-------|------|-------------|
| Backlog | TODO.md | Orchestrator |
| In Progress | IN_PROGRESS.md | Orchestrator |
| Ready for Review | REVIEW.md | Orchestrator (after Task Agent completes) |
| Testing Queue | TESTING.md | Orchestrator (after Reviewer approves) |
| Complete | CHANGELOG.md | Task Agent (entry), Tester (after merge) |

---

## State Transitions

```
TODO.md → IN_PROGRESS.md → REVIEW.md → TESTING.md → CHANGELOG.md
   │            │              │            │
   │            │              │            └── Tester merges successfully
   │            │              └── Reviewer approves
   │            └── Task Agent reports done
   └── Orchestrator picks task (BEFORE spawning agent)
```

**Transition Ownership:**

| Transition | Who | When | Action |
|------------|-----|------|--------|
| TODO → IN_PROGRESS | Orchestrator | Task is picked | Move entry, THEN spawn Task Agent |
| IN_PROGRESS → REVIEW | Orchestrator | Task Agent reports complete | Move entry, spawn Reviewer |
| REVIEW → TESTING | Orchestrator | Reviewer approves | Move entry, add to merge queue |
| TESTING → CHANGELOG | Tester | Merge succeeds | Remove from TESTING.md, entry already in CHANGELOG |

**Important:** Move task to IN_PROGRESS.md **before** spawning the agent. This ensures tracking is accurate even if the agent fails to start.

---

## Key Rules

1. **Task Agents don't run tests** - Speeds up implementation, reduces context
2. **Reviewers don't run full suite** - Focus on code quality, not CI
3. **Testers run targeted tests** - Test changed modules only, full suite in CI
4. **6 total agents max** - Shared pool between all roles
5. **15-minute timeout** - Kill agents that run longer
6. **Use haiku model** - Faster completion for focused tasks (optional)
7. **Worktrees for everything** - Isolation, parallel work, clean rollback

---

## Failure Paths

**Principle:** Retry once in place, then escalate to Orchestrator.

| Stage | Failure | First Response | On Second Failure |
|-------|---------|----------------|-------------------|
| Task Agent | Incomplete/wrong fix | New Task Agent, same worktree | Escalate: Orchestrator decides (manual fix, different approach, or deprioritize) |
| Reviewer | "Approach is wrong" | Back to Task Agent with feedback | Escalate: may need re-scoping in TODO.md |
| Tester | Tests fail | Tester attempts fix in worktree | Escalate: back to REVIEW.md with failure notes |

**Escalation means Orchestrator chooses:**
- Manual intervention (Orchestrator fixes directly)
- Re-scope the task (update TODO.md with new approach)
- Deprioritize (move to bottom of TODO.md with blocker notes)
- Abandon (remove from TODO.md, document why in CHANGELOG.md)

**Tracking failures:** Add `[RETRY]` or `[ESCALATED]` prefix to task in tracking file.

---

## Capacity Management

- Maximum 6 concurrent tasks in IN_PROGRESS.md
- When at capacity: complete existing tasks before starting new ones
- Prioritize completing nearly-done tasks over starting new work

---

## Pre-flight Validation

**Orchestrator checks before spawning any agents:**

```bash
# 1. Qdrant running
curl -sf http://localhost:6333/readyz > /dev/null || echo "Qdrant down"

# 2. Git status clean (no uncommitted changes in tracked files)
git diff --quiet && git diff --cached --quiet || echo "Uncommitted changes"

# 3. Not at capacity
# Count tasks in IN_PROGRESS.md < 6
```

**Agent minimal checks on start:**
- Worktree path doesn't already exist (or is the expected branch)
- Can read required source files
- Git operations work in worktree

**If pre-flight fails:** Orchestrator reports to user, does not spawn agents until resolved.

---

## Example Session Flow

```
1. Orchestrator runs pre-flight validation
2. Orchestrator picks 6 tasks from TODO.md
3. Moves tasks to IN_PROGRESS.md (before spawning)
4. Spawns 6 Task Agents in parallel
5. Task Agents complete, report back
6. Orchestrator moves completed tasks to REVIEW.md
7. Spawns Reviewers in parallel
8. Reviewers complete, report back
9. Orchestrator moves approved tasks to TESTING.md
10. Spawns Testers in parallel (testing phase)
11. Testers report ready for merge
12. Orchestrator coordinates merge queue (serial)
13. Testers merge one at a time, cleanup
14. Orchestrator picks next batch, repeats
```

---

## Troubleshooting

**Worktree already exists:**
```bash
git worktree remove .worktrees/$TASK_ID
git branch -D $TASK_ID
```

**Merge conflicts:**
- Tester resolves conflicts in worktree before merging
- If complex, escalate to Orchestrator

**Test failures:**
- Tester owns fixing test failures
- If fix is non-trivial, may need to spawn new Task Agent

**Agent timeout:**
- Kill the agent
- Assess partial work in worktree
- Respawn or complete manually
