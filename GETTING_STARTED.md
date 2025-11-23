# Getting Started

Quick start guide for new contributors to the Claude Memory RAG Server.

---

## Prerequisites

**Required:**
- Python 3.8+ (3.13+ recommended)
- pip
- Git
- Docker & Docker Compose (for Qdrant vector database)

**Optional:**
- Rust toolchain (for 6x faster parsing via Maturin)

---

## Quick Setup (5 minutes)

### 1. Clone and Setup Environment

```bash
# Clone the repository
git clone https://github.com/your-org/claude-memory-server.git
cd claude-memory-server

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Optional: Build Rust module for 6x faster parsing
cd rust_core && maturin develop && cd ..
```

### 2. Start Qdrant Vector Database

```bash
# Start Qdrant with Docker Compose
docker-compose up -d

# Verify Qdrant is running
curl http://localhost:6333/
# Should return: {"title":"qdrant - vector search engine","version":"x.x.x"}
```

### 3. Verify Installation

```bash
# Run validation script
python scripts/validate_installation.py

# Run setup verification
python scripts/setup.py

# Run a quick test
pytest tests/unit/test_config.py -v
```

### 4. Index a Sample Project

```bash
# Index the example project
python -m src.cli index ./examples/sample_project --project-name sample

# Search the indexed code
python -m src.cli search "authentication" --project sample
```

**✅ You're ready!** If all steps passed, your environment is set up correctly.

---

## Development Workflow

### Starting a New Task

1. **Find a task** in `TODO.md`
2. **Create a git worktree** (isolates your work):
   ```bash
   TASK_ID="FEAT-XXX"  # Replace with your task ID
   git worktree add .worktrees/$TASK_ID -b $TASK_ID
   cd .worktrees/$TASK_ID
   ```

3. **Update IN_PROGRESS.md** with your task
4. **Create a planning document** in `planning_docs/FEAT-XXX_*.md`
5. **Implement the feature** following existing patterns
6. **Write tests** (aim for 80%+ coverage)

### Completing a Task

1. **Run verification**:
   ```bash
   python scripts/verify-complete.py
   ```

2. **Update documentation**:
   - Add entry to `CHANGELOG.md`
   - Update `TODO.md` (mark completed)
   - Update `README.md` if needed

3. **Move to REVIEW.md** when ready for review

4. **Merge to main** after approval:
   ```bash
   cd ../..  # Back to main repo
   git checkout main
   git merge --no-ff $TASK_ID
   git push origin main
   git worktree remove .worktrees/$TASK_ID
   git branch -d $TASK_ID
   ```

---

## Project Structure

```
claude-memory-server/
├── src/               # Source code
│   ├── core/          # MCP server, models, validation
│   ├── store/         # Storage backends (Qdrant)
│   ├── embeddings/    # Embedding generation
│   ├── memory/        # Code indexing, file watching
│   └── cli/           # Command-line interface
├── tests/             # Test suite (~2,740 tests)
│   ├── unit/          # Unit tests
│   ├── integration/   # Integration tests
│   └── security/      # Security validation
├── docs/              # Documentation
├── scripts/           # Automation scripts
├── planning_docs/     # Technical planning documents
├── TODO.md            # Planned work
├── IN_PROGRESS.md     # Active tasks
├── REVIEW.md          # Awaiting review
├── CHANGELOG.md       # Completed work
└── CLAUDE.md          # Multi-agent orchestration guide
```

---

## Common Commands

### Testing

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=src --cov-report=html

# Run specific test file
pytest tests/unit/test_indexing.py -v

# Run in parallel (2.55x faster)
pytest tests/ -n auto -v

# Run with minimal output
pytest tests/ -q
```

### Code Indexing

```bash
# Index a codebase
python -m src.cli index /path/to/code --project-name my-project

# Watch for changes (auto-reindex)
python -m src.cli watch /path/to/code

# Search indexed code
python -m src.cli search "query" --project my-project

# Check indexing status
python -m src.cli status
```

### MCP Server

```bash
# Start MCP server (for Claude integration)
python -m src.mcp_server

# Test MCP tools
# (Use Claude Code or MCP inspector)
```

### Health & Monitoring

```bash
# Check system health
python -m src.cli health

# View metrics
python -m src.cli metrics

# Run status dashboard
python scripts/status-dashboard.py
```

---

## Key Files to Read

**Start Here:**
1. **This file** - Quick setup and workflow
2. `TASK_WORKFLOW.md` - Detailed task lifecycle
3. `CLAUDE.md` - Multi-agent coordination rules

**When You Need It:**
- `TESTING_GUIDE.md` - Testing strategies and patterns
- `DEBUGGING.md` - Debugging techniques
- `ADVANCED.md` - Git worktrees, conflict resolution
- `docs/ARCHITECTURE.md` - System design
- `docs/API.md` - API reference

---

## Getting Help

**Documentation Issues:**
- Check `DEBUGGING.md` for common problems
- Check `docs/TROUBLESHOOTING.md` for solutions

**Test Failures:**
- See `TESTING_GUIDE.md` for debugging strategies
- Check `.coveragerc` for coverage exclusions

**Workflow Questions:**
- See `TASK_WORKFLOW.md` for complete lifecycle
- See `CLAUDE.md` for multi-agent coordination

**Technical Questions:**
- Check `docs/` directory for comprehensive guides
- Review `planning_docs/` for feature implementation details

---

## Next Steps

After completing quick setup:

1. **Read TASK_WORKFLOW.md** - Understand the full development cycle
2. **Read CLAUDE.md** - Learn multi-agent coordination patterns
3. **Browse TODO.md** - Find a task to work on
4. **Run the test suite** - Verify everything works
5. **Index a real project** - Try the core functionality

**Ready to contribute?** Pick a task from `TODO.md` and follow the workflow in `TASK_WORKFLOW.md`!
