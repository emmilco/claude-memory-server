# CLAUDE.md - AI Agent Guide

**Essential context for AI agents working on the Claude Memory RAG Server.**

---

## 🚀 Quick Start (30 Seconds)

**First time here?**
1. Read **GETTING_STARTED.md** (5 minutes) → Environment setup and basics
2. Check **TODO.md** → Find a task
3. Follow **TASK_WORKFLOW.md** → Complete lifecycle guide

**Returning contributor?**
1. Check **TODO.md** and **IN_PROGRESS.md** → What's happening
2. Run `python scripts/status-dashboard.py` → Project health
3. Continue where you left off

**Quick health check:**
```bash
python scripts/setup.py              # Validate environment
python scripts/status-dashboard.py   # View status
```

---

## 📖 What This Project Is

A **Model Context Protocol (MCP) server** providing persistent memory, documentation search, and semantic code search for Claude.

**Core Capabilities:**
- **Semantic code search** - Find code by meaning, not keywords (7-13ms latency)
- **Memory management** - Store/retrieve with lifecycle and provenance tracking
- **Code indexing** - 17 file formats (14 languages + 3 config types)
- **Parallel embeddings** - 4-8x faster indexing with multi-process architecture
- **Health monitoring** - Continuous monitoring with automated remediation
- **Multi-project support** - Cross-project search with privacy consent

**Status:** Production-ready (v4.0 RC1)

---

## 🛠️ Technology Stack

- **Language:** Python 3.13+ (159 modules, ~4MB code)
- **Vector DB:** Qdrant (Docker, localhost:6333)
- **Embeddings:** all-mpnet-base-v2 (768 dimensions)
- **Search:** Hybrid (BM25 + vector)
- **Testing:** pytest (~2,740 tests, 59.6% coverage overall / 71.2% core)
- **Framework:** MCP - 16 tools + 28 CLI commands
- **Parser:** Rust module (mcp_performance_core) - required for code indexing

---

## 📁 Essential Files - Where to Find Information

### 🔄 Workflow & Tracking
**Read these to understand current work:**
- `TODO.md` → Planned work (backlog with IDs: FEAT-XXX, BUG-XXX, etc.)
- `IN_PROGRESS.md` → Active tasks (max 6 concurrent)
- `REVIEW.md` → Awaiting review/approval
- `CHANGELOG.md` → Completed work history
- `planning_docs/` → Technical planning documents
### Core Implementation
- `src/core/server.py` - Main MCP server with all tools
- `src/memory/incremental_indexer.py` - Code indexing logic with progress callbacks
- `src/store/qdrant_store.py` - Vector database operations (with project stats methods)
- `src/store/sqlite_store.py` - SQLite storage backend (with project stats methods)
- `src/embeddings/generator.py` - Standard embedding generation (single-threaded)
- `src/embeddings/parallel_generator.py` - **NEW:** Parallel embedding generation (4-8x faster)
- `src/embeddings/cache.py` - Embedding cache for incremental indexing
- `src/core/exceptions.py` - **ENHANCED:** Actionable error messages with solutions
- `src/config.py` - Configuration management
- `src/cli/status_command.py` - Status reporting with project statistics
- `src/cli/index_command.py` - Indexing CLI with progress indicators
- `rust_core/src/parsing.rs` - Fast code parsing
### Core Implementation
- `src/core/server.py` - Main MCP server with all tools
- `src/memory/incremental_indexer.py` - Code indexing logic with progress callbacks
- `src/memory/project_index_tracker.py` - **NEW:** Project indexing metadata and staleness tracking
- `src/memory/auto_indexing_service.py` - **NEW:** Auto-indexing orchestration with foreground/background modes
- `src/store/qdrant_store.py` - Vector database operations (with project stats methods)
- `src/store/sqlite_store.py` - SQLite storage backend (with project stats methods)
- `src/embeddings/generator.py` - Standard embedding generation (single-threaded)
- `src/embeddings/parallel_generator.py` - **NEW:** Parallel embedding generation (4-8x faster)
- `src/embeddings/cache.py` - Embedding cache for incremental indexing
- `src/core/exceptions.py` - **ENHANCED:** Actionable error messages with solutions
- `src/config.py` - Configuration management (11 new auto-indexing options)
- `src/cli/status_command.py` - Status reporting with project statistics
- `src/cli/index_command.py` - Indexing CLI with progress indicators
- `rust_core/src/parsing.rs` - Fast code parsing

### 📚 Progressive Disclosure Guides
**Read in order as you need them:**
### Testing
- `tests/unit/` - Unit tests for all modules
  - `test_store_project_stats.py` - Project statistics functionality (15 tests)
  - `test_indexing_progress.py` - Progress callback system (11 tests)
  - `test_status_command.py` - Status command with file watcher info (38 tests)
  - `test_parallel_embeddings.py` - **NEW:** Parallel embedding and cache tests (21 tests)
  - `test_actionable_errors.py` - **NEW:** Actionable error message tests (6 tests)
- `tests/integration/` - End-to-end workflow tests
- `tests/security/` - Security validation tests
### Testing
- `tests/unit/` - Unit tests for all modules
  - `test_project_index_tracker.py` - **NEW:** Project metadata tracking (26 tests, 100% passing)
  - `test_auto_indexing_service.py` - **NEW:** Auto-indexing orchestration (33 tests, 23 passing)
  - `test_store_project_stats.py` - Project statistics functionality (15 tests)
  - `test_indexing_progress.py` - Progress callback system (11 tests)
  - `test_status_command.py` - Status command with file watcher info (38 tests)
  - `test_parallel_embeddings.py` - **NEW:** Parallel embedding and cache tests (21 tests)
  - `test_actionable_errors.py` - **NEW:** Actionable error message tests (6 tests)
- `tests/integration/` - End-to-end workflow tests
- `tests/security/` - Security validation tests

**Level 1 - Start Here:**
- `GETTING_STARTED.md` → Quick start for new contributors (read first!)

**Level 2 - Core Workflows:**
- `TASK_WORKFLOW.md` → Complete task lifecycle (TODO → IN_PROGRESS → REVIEW → CHANGELOG)
- `TESTING_GUIDE.md` → Testing strategies, coverage requirements, debugging tests

**Level 3 - When You Need Help:**
- `DEBUGGING.md` → Troubleshooting common issues (Qdrant, imports, indexing, tests)
- `ADVANCED.md` → Complex scenarios (conflicts, multi-agent coordination, optimization)

### 🤖 Automation
**Use these frequently:**
- `scripts/setup.py` → Environment validation (`--fix` to auto-fix)
- `scripts/verify-complete.py` → Quality gates (run before merging)
- `scripts/status-dashboard.py` → Project health (`--watch` for live updates)

### 📖 Reference
- `README.md` → User-facing documentation
- `docs/` → Comprehensive technical guides (Architecture, API, Setup, etc.)
- `archived_docs/CLAUDE_FULL_REFERENCE.md` → Full version of this file (703 lines)

---

## ⚡ Critical Rules (Must Know)

### 1. Git Worktree Workflow (REQUIRED)

**Always work in git worktrees to avoid conflicts:**

```bash
# Starting a task
TASK_ID="FEAT-042"  # Use exact task ID from TODO.md
git worktree add .worktrees/$TASK_ID -b $TASK_ID
cd .worktrees/$TASK_ID

# When complete
cd ../..
git checkout main
git pull origin main
git merge --no-ff $TASK_ID
git push origin main
git worktree remove .worktrees/$TASK_ID
git branch -d $TASK_ID
```

**Why?** Enables parallel work without conflicts (up to 6 tasks).

**When Direct Commits to Main Are Acceptable:**
- Single-file typo/documentation fixes
- Emergency hotfixes with immediate verification
- CI configuration adjustments during active debugging

**When Worktrees Are Required:**
- Any task with an ID (FEAT-XXX, BUG-XXX, TEST-XXX, etc.)
- Changes touching 3+ files
- Any work expected to take multiple commits

**Details:** See TASK_WORKFLOW.md and ADVANCED.md for complete workflow and conflict resolution.

### 2. Task Tracking

**Track work through these stages:**

```
TODO.md → IN_PROGRESS.md → REVIEW.md → CHANGELOG.md
  (plan)     (working)        (done)      (merged)
```

- **Maximum 6 concurrent tasks** in IN_PROGRESS.md (maintain focus)
- **Update tracking files** as you progress
- **Use unique IDs**: FEAT-XXX, BUG-XXX, TEST-XXX, DOC-XXX, PERF-XXX, REF-XXX, UX-XXX

**Details:** See TASK_WORKFLOW.md for complete lifecycle.

### 3. Quality Gates (MANDATORY Before Moving to REVIEW.md)

**⚠️ CRITICAL WORKFLOW REQUIREMENT:**

**Run comprehensive verification:**
```bash
python scripts/verify-complete.py
```

**Checks (ALL 6 gates MUST pass):**
- ✅ All tests passing (100% pass rate - ZERO failures)
- ✅ Coverage ≥80% for core modules
- ✅ No syntax errors
- ✅ CHANGELOG.md updated
- ✅ Qdrant accessible
- ✅ Git status clean (no conflicts)

**If ANY gate fails:**
1. **DO NOT** move task to REVIEW.md
2. **DO NOT** report task as complete
3. **FIX** all issues immediately
4. **RE-RUN** verify-complete.py
5. **REPEAT** until ALL 6 gates pass

**Only after verify-complete.py shows "✅ Task is ready for completion" can you:**
- Move task from IN_PROGRESS.md to REVIEW.md
- Report task as complete
- Request peer review

**Details:** See TESTING_GUIDE.md for testing strategies.

### 4. Documentation Updates

**Pre-commit hook enforces CHANGELOG.md updates:**
```bash
git commit -m "message"  # Requires CHANGELOG.md staged
```

**Always update:**
- `CHANGELOG.md` → Add entry for your changes
- `TODO.md` → Mark completed items
- `planning_docs/{ID}_*.md` → Update progress (for complex tasks)

**Bypass (use sparingly):**
```bash
git commit --no-verify -m "message"  # Only if docs verified current
```

### 5. Testing Requirements

- **Minimum 80% coverage** for core modules (src/core, src/store, src/memory, src/embeddings)
- **Write tests** alongside code (unit + integration)
- **Run tests frequently:**
  ```bash
  pytest tests/unit/test_module.py -v           # Specific test
  pytest tests/ -n auto -v                      # All tests (parallel, 2.55x faster!)
  pytest tests/ --cov=src --cov-report=html     # With coverage
  ```

**Details:** See TESTING_GUIDE.md for comprehensive strategies.

### 6. Planning Documents

**For complex tasks (3+ steps):**
- Create `planning_docs/{ID}_{description}.md`
- Update with progress, decisions, blockers
- Add completion summary at end

**Examples:**
- `planning_docs/FEAT-056_advanced_filtering_plan.md`
- `planning_docs/BUG-023_test_suite_fix.md`

**Do NOT create task docs in root** - only in `planning_docs/`

---

## 📋 Common Commands

### Workflow Automation
```bash
# Environment setup
python scripts/setup.py --fix

# Project status (live updates)
python scripts/status-dashboard.py --watch

# Pre-merge verification
python scripts/verify-complete.py
python scripts/verify-complete.py --fast  # Skip slow tests
```

### Testing
```bash
# Parallel (recommended - 2.55x faster!)
pytest tests/ -n auto -v

# With coverage
pytest tests/ -n auto --cov=src --cov-report=html

# Specific test
pytest tests/unit/test_module.py::test_function -v
```

### Development
```bash
# Install dependencies
pip install -r requirements.txt

# Start Qdrant
docker-compose up -d

# Index codebase
python -m src.cli index ./path/to/code --project-name my-project

# Start MCP server
python -m src.mcp_server
```

---

## 🎯 Before Starting Any Task

1. **Check capacity:**
   ```bash
   # Ensure <6 tasks in progress
   python scripts/status-dashboard.py
   ```

2. **Sync with latest:**
   ```bash
   git checkout main
   git pull origin main
   git log --oneline -10  # Review recent changes
   ```

3. **Read documentation:**
   - `TODO.md` → Available tasks
   - `IN_PROGRESS.md` → What others are working on
   - `CHANGELOG.md` → Recent changes

4. **Verify health:**
   ```bash
   python scripts/setup.py           # Environment check
   curl http://localhost:6333/       # Qdrant running?
   pytest tests/ -n auto -v --tb=short  # Tests passing?
   ```

5. **Create worktree** (see Critical Rules #1 above)

---

## 🔄 When Making Changes

**1. Track your work:**
- Move task: `TODO.md` → `IN_PROGRESS.md` (when starting)
- Update: `IN_PROGRESS.md` with progress notes
- Move: `IN_PROGRESS.md` → `REVIEW.md` (when ready)
- Update: `CHANGELOG.md` (after merging)

**2. Follow patterns:**
- Use type hints for all parameters/returns
- Write docstrings for public functions
- Create tests for new functionality
- Use async/await for I/O operations

**3. Test frequently:**
```bash
pytest tests/unit/test_[your_module].py -v
python scripts/verify-complete.py
```

**4. Update docs:**
- `CHANGELOG.md` under "Unreleased"
- `TODO.md` mark completed
- This file if you discover important patterns

---

## 🗺️ Navigation Guide - Where to Learn More

**Stuck or need details?** Here's where to look:

| Topic | Document | When to Read |
|-------|----------|--------------|
| **First-time setup** | GETTING_STARTED.md | Read first (5 min) |
| **Task workflow** | TASK_WORKFLOW.md | Starting your first task |
| **Testing** | TESTING_GUIDE.md | Writing tests, debugging |
| **Troubleshooting** | DEBUGGING.md | Something not working |
| **Git conflicts** | ADVANCED.md | Merge conflicts, complex scenarios |
| **Multi-agent coordination** | ADVANCED.md | Parallel work, capacity management |
| **Architecture** | docs/ARCHITECTURE.md | Understanding system design |
| **API reference** | docs/API.md | Tool/command details |
| **Full reference** | archived_docs/CLAUDE_FULL_REFERENCE.md | Original 703-line guide |

---

## 📊 Current State

**Metrics** (as of 2025-11-22):
- Tests: ~2,740 (varies: 2,677-2,744)
- Coverage: 59.6% overall / 71.2% core (target: 80%)
- Modules: 159 Python modules (~4MB)
- Performance: 7-13ms search, 10-20 files/sec indexing

**Status:** Production-ready (v4.0 RC1)

**Major Systems:**
- ✅ Memory Intelligence (lifecycle, provenance, trust)
- ✅ Multi-Project Support (cross-project search)
- ✅ Health Monitoring (alerts, remediation)
- ✅ Performance Optimization (parallel, caching)

**View live status:**
```bash
python scripts/status-dashboard.py
```

---

## 🔧 Project Structure

```
claude-memory-server/
├── TODO.md, IN_PROGRESS.md, REVIEW.md, CHANGELOG.md  # Workflow tracking
├── GETTING_STARTED.md                                # Read first!
├── TASK_WORKFLOW.md, TESTING_GUIDE.md               # Core guides
├── DEBUGGING.md, ADVANCED.md                         # When needed
├── src/                                              # Source code
│   ├── core/         # MCP server, models
│   ├── store/        # Qdrant storage
│   ├── memory/       # Code indexing
│   ├── embeddings/   # Embedding generation
│   └── cli/          # CLI commands
├── tests/            # Test suite (~2,740 tests)
├── scripts/          # Automation (setup, verify, status)
├── docs/             # Technical documentation
├── planning_docs/    # Task planning documents
└── .worktrees/       # Git worktrees (gitignored)
```

---

## 🐛 Debugging Workflows (Lessons Learned)

**When CI fails differently than local:**

1. **Check version consistency first**
   ```bash
   # Compare CI vs local dependency versions
   gh run view <run-id> --log | grep "Installing pytest"
   pip list | grep pytest-asyncio
   ```
   - **Lesson**: Lock file vs requirements.txt mismatches cause CI-only failures
   - **Example**: pytest-asyncio 1.2.0 (local) vs 0.26.0 (CI) → "Event loop is closed" errors

2. **Validate lock file matches constraints**
   ```bash
   # Before committing requirements.txt changes
   pip-compile requirements.txt --dry-run
   ```

3. **Run tests locally AND monitor CI in parallel**
   - Compare failure counts: identical = code issue, different = environment issue
   - Saves 30+ minutes vs sequential debugging

4. **Search for affected tests proactively**
   ```bash
   # When changing default values or behavior
   grep -r "assert.*old_default_value" tests/
   grep -r "expect.*old_behavior" tests/
   ```
   - **Example**: Changed `fast_timeout` from 0.001 → 0.05, search finds test to update

5. **Categorize failures before fixing**
   ```bash
   # Group by test file to identify patterns
   pytest tests/ --tb=no | grep FAILED | cut -d: -f1 | sort | uniq -c
   ```
   - Fix by category (10 filtering tests) vs one-by-one (faster, fewer commits)

6. **Use TodoWrite for complex debugging**
   - Track progress through investigation stages
   - Makes it clear what's done, what remains
   - Example: "Fix version mismatch → Test locally → Push to CI → Fix remaining failures"

**Key Insight**: CI-local consistency is the goal. Once both show same failures, you're debugging code, not environment.

---

## 💡 Tips for Success

1. **Progressive disclosure** - Read guides as you need them, not all at once
2. **Use automation** - `setup.py`, `verify-complete.py`, `status-dashboard.py` save time
3. **Track capacity** - Max 6 concurrent tasks maintains quality
4. **Test early** - Write tests alongside code, not after
5. **Document incrementally** - Update docs as you work, not at the end
6. **Ask for help** - Check DEBUGGING.md first, then ask
7. **Debug CI failures systematically** - See "Debugging Workflows" section above

---

## 📝 Self-Update Protocol

**After completing work, update:**
1. **TODO.md** - Mark items complete, add new discoveries
2. **CHANGELOG.md** - Add entry under "Unreleased"
3. **planning_docs/{ID}_*.md** - Update progress, add completion summary
4. **This file (CLAUDE.md)** - Only if you discover important patterns

**Remember:** This documentation is your future self's context. Keep it current.

---

## 📓 Work Journal Protocol

Claude Code hooks automatically prompt you to write journal entries at key moments. When you see `[JOURNAL:xxxxxxxx]` prompts, append a brief entry to `CLAUDE_JOURNAL.md`.

**Always include the session ID from the prompt** so entries from parallel sessions can be distinguished.

### Triggers
| Event | When | What to Write |
|-------|------|---------------|
| `USER_PROMPT` | User sends request | What's being asked? Initial approach? |
| `TASK_START` | Spawning subagent | Why delegate? What should it accomplish? |
| `TASK_END` | Subagent finished | Did it succeed? What did you learn? |
| `STOP` | Response complete | What was accomplished? Concerns? |
| `INTERVAL` | Every 10 minutes | Progress check. Stuck anywhere? |

### Entry Format
```markdown
### <timestamp> | <session> | <event_type>
<1-3 sentences responding to the prompt>
```

### Example
```markdown
### 2025-11-25 10:15 | a1b2c3d4 | USER_PROMPT
User wants retry logic for API client. Plan: find existing error handling, add exponential backoff.

### 2025-11-25 10:16 | a1b2c3d4 | TASK_START (Explore)
Delegating search for API call sites - too many files to check manually.

### 2025-11-25 10:17 | a1b2c3d4 | TASK_END (Explore)
Found 12 call sites across 4 files. Most have try/catch but no retry.

### 2025-11-25 10:18 | a1b2c3d4 | STOP
Added retry wrapper to utils, updated 3 critical endpoints.

### 2025-11-25 10:28 | a1b2c3d4 | INTERVAL
Implementing tests for retry logic. Going smoothly, no blockers.
```

### Purpose
These entries enable periodic retrospectives to identify:
- Where Claude gets stuck
- Inefficient approaches
- False completions (thought done, wasn't)
- Patterns that need new guidelines

**Files:**
- `CLAUDE_JOURNAL.md` - Qualitative reflections (Claude-written)
- `.claude/logs/CLAUDE_LOGS.jsonl` - Raw event log (hook-written)

---

## 🔄 Behavioral Reinforcement System

A feedback loop for iterative behavioral improvement. User reactions (praise, criticism, corrections) are captured automatically and analyzed periodically to extract actionable principles.

### How It Works

1. **Automatic Capture:** Sentiment keywords in user messages trigger logging to `.claude/feedback/feedback_log.jsonl`
2. **Periodic Analysis:** Run `/retro` to analyze feedback, filter false positives, identify patterns
3. **Principle Extraction:** Recurring patterns become candidate principles for user approval
4. **Guidance Update:** Approved principles are added to `LEARNED_PRINCIPLES.md`

### Commands

| Command | Purpose |
|---------|---------|
| `/retro` | Run a retrospective analysis session |
| `/wrapup` | Write a session summary before ending |

### Files

| File | Purpose |
|------|---------|
| `LEARNED_PRINCIPLES.md` | Extracted behavioral rules (consult alongside this file) |
| `.claude/feedback/feedback_log.jsonl` | Raw feedback entries |
| `.claude/feedback/retro_history.md` | Audit trail of retrospectives |
| `.claude/feedback/reports/` | Detailed retro reports (one per session) |
| `.claude/logs/CLAUDE_LOGS.jsonl` | Activity log (tool uses, tasks) for context correlation |

### Sentiment Detection

The system detects:
- **Positive:** "great", "perfect", "exactly", "well done", "thanks", etc.
- **Negative:** "wrong", "broke", "missed", "stuck", "frustrating", etc.
- **Corrective:** "actually", "not quite", "I meant", "try again", etc.

Detection is intentionally over-sensitive; false positives are filtered during `/retro` analysis.

### Usage

Work normally. When you've accumulated feedback (after several sessions), run `/retro` to:
1. Review genuine feedback vs false positives
2. Identify behavioral patterns
3. Generate candidate principles
4. Approve or reject proposed changes

**Full documentation:** `planning_docs/FEAT-050_behavioral_reinforcement_system.md`

---

## 🎓 Full Reference

This is a **streamlined navigation hub** (~300 lines).

**For comprehensive details**, see:
- `archived_docs/CLAUDE_FULL_REFERENCE.md` (original 703-line guide)
- Progressive disclosure guides (GETTING_STARTED, TASK_WORKFLOW, etc.)

**Philosophy:** Start simple, add complexity as needed.

---

**Questions?** Check the navigation guide above to find the right document, or see DEBUGGING.md for troubleshooting.
