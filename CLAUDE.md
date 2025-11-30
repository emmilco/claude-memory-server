# CLAUDE.md

MCP server for semantic code search and persistent memory. Python 3.13+, Qdrant vector DB.

## Scope Calibration

**Quick fix** (1 file, obvious change): Direct commit to main, no tracking needed.

**Tracked task** (TODO.md item, multi-file, 3+ commits): Use worktree workflow below.

**Investigation** (no code change expected): No tracking, just report findings.

## Key Files

Workflow tracking: `TODO.md` → `IN_PROGRESS.md` → `REVIEW.md` → `CHANGELOG.md`

Entry points: `src/core/server.py` (MCP server), `src/store/` (Qdrant), `src/memory/` (indexing)

Scripts: `scripts/setup.py --fix` (environment), `scripts/verify-complete.py` (pre-merge gates)

When to read other docs:
- Stuck/errors → `DEBUGGING.md`
- Git conflicts, multi-agent → `ADVANCED.md`
- Testing patterns → `TESTING_GUIDE.md`
- CI fails differently than local → `DEBUGGING.md`

## Worktree Workflow

For tracked tasks. Task IDs come from TODO.md (format: FEAT-XXX, BUG-XXX, TEST-XXX, etc.)

```bash
# Start
git worktree add .worktrees/$TASK_ID -b $TASK_ID && cd .worktrees/$TASK_ID

# Before completing: merge main and re-test
git fetch origin main && git merge origin/main
./scripts/test-isolated.sh tests/ -v

# Finish
cd ../.. && git checkout main && git pull origin main
git merge --no-ff $TASK_ID && git push origin main
git worktree remove .worktrees/$TASK_ID && git branch -d $TASK_ID
```

## Completing a Task

1. Tests pass: `./scripts/test-isolated.sh tests/ -v`
2. Gates pass: `python scripts/verify-complete.py` (all 6 required)
3. Move task: `IN_PROGRESS.md` → `REVIEW.md` (request code review)
4. After review approved: merge to main, `git push origin main`
5. Move task: `REVIEW.md` → `CHANGELOG.md` under "Unreleased"

Gates check: tests 100%, coverage ≥80% core, no syntax errors, CHANGELOG updated, Qdrant up, git clean.

## Commands

```bash
# Setup
docker-compose up -d                                # Start Qdrant
python scripts/setup.py --fix                       # Validate environment

# Testing
./scripts/test-isolated.sh tests/ -v                # All tests (handles Qdrant)
./scripts/test-isolated.sh tests/unit/ -v --tb=short  # Unit tests only
pytest tests/ -n auto --cov=src --cov-report=html   # With coverage

# Verification
python scripts/verify-complete.py                   # Pre-merge gates
```

## Quick Fixes

Qdrant down? `docker-compose up -d`
Tests hanging? Look for missing `await` or infinite loops. Kill with Ctrl+C.
Pre-commit hook blocks commit? Stage CHANGELOG.md or use `--no-verify`.

## Constraints

- Max 6 concurrent tasks in IN_PROGRESS.md
- Complex tasks (3+ steps): create `planning_docs/{ID}_*.md`

## Hooks

This project uses a feedback loop to evolve agent behavior over time. Journal entries and feedback are analyzed periodically (`/retro`) to refine the VALUES that guide future sessions.

- **VALUES** are injected on session start - working orientations from past analysis
- **Journal prompts** (`[JOURNAL]`) appear on key events - write entries to feed the improvement cycle

```bash
./scripts/journal.sh EVENT_TYPE "your entry here"
```
