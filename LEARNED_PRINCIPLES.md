# Learned Principles

Behavioral adjustments derived from user feedback analysis.
This file is updated by `/retro` sessions and should be referenced alongside CLAUDE.md.

**Last updated:** 2025-11-27
**Total retrospectives:** 2
**Active principles:** 9

---

## Active Principles

### LP-001: Discuss Design Before Implementing
**Source:** Retro 2025-11-25 (4 positive signals)
**Pattern:** User praised collaborative design discussions before coding
**Rule:** When building new features or systems, engage in thorough design discussion with the user before writing any code. Present architecture options, ask clarifying questions, and confirm the approach before implementation.
**Rationale:** Multiple instances of praise ("This was such a good session", "that's really awesome", "amazing") came after collaborative design discussions where the user shaped the approach through iterative Q&A before any code was written.

### LP-002: Demonstrate Working Results, Not Just Completion
**Source:** Retro 2025-11-25 (2 positive signals)
**Pattern:** User showed enthusiasm when seeing systems work in real-time
**Rule:** When implementing features, show concrete evidence of functionality rather than just reporting completion. Demonstrate live output, show captured data, or run examples that prove the system works.
**Rationale:** Strong positive reactions ("Hahahaha, that's so cool", "YES!!!!") occurred when the system demonstrated itself working - like seeing the first feedback entry captured during development.

### LP-003: Explain Reasoning Behind Recommendations
**Source:** Retro 2025-11-25 (2 positive signals)
**Pattern:** User appreciated when recommendations came with clear rationale
**Rule:** When presenting options or making recommendations, explain the reasoning behind each choice. Include trade-offs, implications, and why one approach might be preferred over another.
**Rationale:** User responded positively ("that's a good question", "fascinating") when given thorough explanations of design considerations and trade-offs rather than just bare recommendations.

### LP-004: Use Structured Debugging for Complex Bugs
**Source:** Retro 2025-11-27 (1 explicit signal + journal META_LEARNING entry)
**Pattern:** User explicitly noted Claude performs better with specific debugging strategies
**Rule:** When debugging complex or persistent issues, employ one of these strategies: (1) Simulate a pair programming session between two engineers analyzing the problem, or (2) Perform a differential diagnosis considering the problem from multiple angles to systematically narrow down root causes.
**Rationale:** User directly observed: "you seem to do better figuring out bugs when you employ either of the following strategies: simulate a pair programming session between two engineers debugging the issue, or consider the problem from all angles and do a differential diagnosis that will help you pinpoint the root cause." Journal confirms this led to spending ~1 hour in inefficient debugging loops when not applied.

### LP-005: Analyze Available Data Before Proposing New Actions
**Source:** Retro 2025-11-27 (2 corrective signals + journal evidence)
**Pattern:** Proposed gathering new data when existing data was available
**Rule:** When asked about results, status, or data, first review what has already been collected or produced in the current session before proposing to gather new information. Check for existing test runs, search results, or analysis outputs.
**Rationale:** User corrections like "Hang on, you have several results already. I'm asking about runs you've already done" indicate a pattern of jumping to action before reviewing existing context. Journal shows multiple test runs existed but Claude proposed running new ones instead of analyzing existing results.

### LP-006: Provide Thorough Reports and Status Updates
**Source:** Retro 2025-11-27 (3 positive signals)
**Pattern:** User appreciated detailed reporting on project status and task outcomes
**Rule:** When completing multi-step tasks or when asked about status, provide thorough reports that cover: what was done, what the results were, and what remains. Don't just say "done" - show the evidence.
**Rationale:** Multiple positive reactions to thorough reporting: "thank you for the thorough report", "This report is excellent", and implicit praise for detailed status updates.

### LP-007: Coordinate Carefully in Multi-Agent Scenarios
**Source:** Retro 2025-11-27 (2 corrective signals + 3 journal entries)
**Pattern:** Parallel agent work caused conflicts and rework
**Rule:** When multiple agents are working in parallel (either spawned by you or by the user), be aware that config changes, test file modifications, or code refactors in one session may conflict with another. Before making broad changes, check if the work might conflict with parallel sessions. When conflicts are detected, pause and coordinate with the user.
**Rationale:** Journal documents significant time lost to agent conflicts: "Made things worse before better: tried to fix config access issues incrementally, causing failures to balloon from 10 → 126" and "Parallel agent conflict caused work to be undone repeatedly."

### LP-008: Use Git Worktrees for All Non-Trivial Work
**Source:** Workflow analysis 2025-11-27
**Pattern:** Agents drifted from worktree workflow during crisis period, habit persisted
**Rule:** Always create a git worktree for tasks that will involve multiple commits or touch multiple files. Only commit directly to main for single-file hotfixes that are immediately verifiable. Before starting any task with an ID (FEAT-XXX, BUG-XXX, etc.), create a worktree.
**Rationale:** After CI failures in Nov 2025, agents bypassed worktrees for speed during urgent fixes. This became habit even after the crisis passed—175 commits in one week with only 23% being proper merges. Direct commits to main increase conflict risk and lose the isolation benefits the workflow provides.

### LP-009: Validate Infrastructure with Real Usage, Not Just Test Coverage
**Source:** Session 2025-11-27 (direct observation + journal META_LEARNING entry)
**Pattern:** Infrastructure marked "complete" with 97% test coverage failed on first real use
**Rule:** Before marking infrastructure code (connection pools, caches, stores, etc.) as complete, exercise it in a real scenario that includes failure and recovery. Mock-based unit tests verify code logic; integration tests with real dependencies validate assumptions. "Complete" requires at least one real usage scenario passing, not just unit test coverage.
**Rationale:** Connection pool was marked COMPLETE with "97% coverage" and "56 tests," but all tests used mocks. First real usage failed immediately due to a bug *documented in the code comments*. Tests verified the code was consistent with assumptions; they didn't verify assumptions were correct. Verification ≠ Validation.
**Related:** Extends LP-002 (Demonstrate Working Results) to the testing domain. Also: known technical debt in code comments should become TODO.md items—invisible debt is unfixable debt.

---

## Retired Principles

*Principles that were later found unhelpful or superseded will be moved here.*

---

## Statistics

| Metric | Value |
|--------|-------|
| Total feedback entries processed | 74 |
| Genuine feedback (after filtering) | 46 |
| Journal entries analyzed | 20+ session summaries |
| Claude log entries sampled | 3,804 |
| Patterns identified | 11 |
| Principles generated | 9 |
| Principles retired | 0 |

---

## How This Works

1. **Feedback Capture:** As you interact with Claude, sentiment keywords in your messages trigger automatic logging to `.claude/feedback/feedback_log.jsonl`

2. **Retrospective Analysis:** Running `/retro` analyzes accumulated feedback, filters false positives, identifies patterns, and generates candidate principles

3. **Principle Generation:** Patterns that recur (2+ instances) become candidate principles for your approval

4. **Application:** Approved principles are added to this file and referenced during future sessions

See `planning_docs/FEAT-050_behavioral_reinforcement_system.md` for full documentation.
