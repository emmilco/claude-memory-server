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
- **Embeddings:** all-MiniLM-L6-v2 (384 dimensions)
- **Search:** Hybrid (BM25 + vector)
- **Testing:** pytest (~2,740 tests, 59.6% coverage overall / 71.2% core)
- **Framework:** MCP - 16 tools + 28 CLI commands
- **Optional:** Rust module (6x faster parsing)

---

## 📁 Essential Files - Where to Find Information

### 🔄 Workflow & Tracking
**Read these to understand current work:**
- `TODO.md` → Planned work (backlog with IDs: FEAT-XXX, BUG-XXX, etc.)
- `IN_PROGRESS.md` → Active tasks (max 6 concurrent)
- `REVIEW.md` → Awaiting review/approval
- `CHANGELOG.md` → Completed work history
- `planning_docs/` → Technical planning documents

### 📚 Progressive Disclosure Guides
**Read in order as you need them:**

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

### 3. Quality Gates (Before Merging)

**Run comprehensive verification:**
```bash
python scripts/verify-complete.py
```

**Checks:**
- ✅ All tests passing (100% pass rate)
- ✅ Coverage ≥80% for core modules
- ✅ No syntax errors
- ✅ CHANGELOG.md updated
- ✅ Qdrant accessible

**If any check fails → NOT ready to merge**

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

## 💡 Tips for Success

1. **Progressive disclosure** - Read guides as you need them, not all at once
2. **Use automation** - `setup.py`, `verify-complete.py`, `status-dashboard.py` save time
3. **Track capacity** - Max 6 concurrent tasks maintains quality
4. **Test early** - Write tests alongside code, not after
5. **Document incrementally** - Update docs as you work, not at the end
6. **Ask for help** - Check DEBUGGING.md first, then ask

---

## 📝 Self-Update Protocol

**After completing work, update:**
1. **TODO.md** - Mark items complete, add new discoveries
2. **CHANGELOG.md** - Add entry under "Unreleased"
3. **planning_docs/{ID}_*.md** - Update progress, add completion summary
4. **This file (CLAUDE.md)** - Only if you discover important patterns

**Remember:** This documentation is your future self's context. Keep it current.

---

## 🎓 Full Reference

This is a **streamlined navigation hub** (~300 lines).

**For comprehensive details**, see:
- `archived_docs/CLAUDE_FULL_REFERENCE.md` (original 703-line guide)
- Progressive disclosure guides (GETTING_STARTED, TASK_WORKFLOW, etc.)

**Philosophy:** Start simple, add complexity as needed.

---

**Questions?** Check the navigation guide above to find the right document, or see DEBUGGING.md for troubleshooting.
