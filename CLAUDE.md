# CLAUDE.md

MCP server for semantic code search and persistent memory. Python 3.13+, Qdrant vector DB.

## Scope Calibration

**Quick fix** (1 file, obvious change): Direct commit to main, no tracking needed.

**Tracked task** (TODO.md item, multi-file, 3+ commits): Use worktree workflow below.

**Investigation** (no code change expected): No tracking, just report findings.

## Key Files

Workflow tracking: `TODO.md` → `IN_PROGRESS.md` → `REVIEW.md` → `TESTING.md` → `CHANGELOG.md`

**Critical rule**: Each task exists in exactly ONE file. "Move" = delete from source, add to destination. See `ORCHESTRATION.md` for full workflow.

Entry points: `src/core/server.py` (MCP server), `src/store/` (Qdrant), `src/memory/` (indexing)

Scripts: `scripts/setup.py --fix` (environment), `scripts/verify-complete.py` (pre-merge gates), `scripts/assemble-changelog.py` (merge changelog fragments)

When to read other docs:
- Multi-agent orchestration → `ORCHESTRATION.md`
- Stuck/errors → `DEBUGGING.md`
- Git conflicts → `ADVANCED.md`
- Testing patterns → `TESTING_GUIDE.md`

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
2. Create changelog fragment: `changelog.d/<TASK-ID>.md`
3. Gates pass: `python scripts/verify-complete.py` (all 9 required)
4. Move task: `IN_PROGRESS.md` → `REVIEW.md` (delete from source, add to destination)
5. After review: move to `TESTING.md`, run targeted tests, merge to main
6. After merge: run `python scripts/assemble-changelog.py`, remove from tracking files

Gates check: CI green, Qdrant up, syntax OK, deps bounded, SPEC valid, skipped tests ≤150, tests 100%, coverage ≥80% core, changelog fragment exists.

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
