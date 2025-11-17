# CLAUDE.md - AI Agent Guide

## Purpose
This document provides essential context for AI agents working on the Claude Memory RAG Server. Keep this document updated as you work.

## Project Overview

### What This Is
A Model Context Protocol (MCP) server providing persistent memory, documentation search, and semantic code search capabilities for Claude. Production-ready with comprehensive testing and documentation.

### Core Capabilities
- **Semantic code search** - Find code by meaning, not keywords (7-13ms latency)
- **Memory management** - Store/retrieve memories with context stratification
- **Documentation RAG** - Search project documentation semantically
- **Code indexing** - Parse and index 6 languages using tree-sitter
- **Real-time watching** - Auto-reindex on file changes

### Technology Stack
- **Language:** Python 3.13+ with type hints
- **Performance:** Rust module via PyO3 for parsing (1-6ms per file)
- **Vector DB:** Qdrant (Docker, localhost:6333)
- **Embeddings:** all-MiniLM-L6-v2 (384 dimensions)
- **Framework:** MCP (Model Context Protocol)
- **Testing:** pytest with 712 tests passing (85% coverage)

## Essential Files

### Documentation (Always Check First)
- `CHANGELOG.md` - Development history and version changes
- `TODO.md` - Current tasks and future work (with unique IDs)
- `README.md` - User-facing documentation
- `docs/` - Comprehensive guides (Architecture, API, Setup, etc.)
- `planning_docs/` - Working documents for active tasks (see Planning System below)

### Core Implementation
- `src/core/server.py` - Main MCP server with all tools
- `src/memory/incremental_indexer.py` - Code indexing logic with progress callbacks
- `src/store/qdrant_store.py` - Vector database operations (with project stats methods)
- `src/store/sqlite_store.py` - SQLite storage backend (with project stats methods)
- `src/embeddings/generator.py` - Embedding generation
- `src/config.py` - Configuration management
- `src/cli/status_command.py` - Status reporting with project statistics
- `src/cli/index_command.py` - Indexing CLI with progress indicators
- `rust_core/src/parsing.rs` - Fast code parsing

### Testing
- `tests/unit/` - Unit tests for all modules
  - `test_store_project_stats.py` - Project statistics functionality (15 tests)
  - `test_indexing_progress.py` - Progress callback system (11 tests)
  - `test_status_command.py` - Status command with file watcher info (38 tests)
- `tests/integration/` - End-to-end workflow tests
- `tests/security/` - Security validation tests

### Configuration
- `.env` - Environment variables (create if needed)
- `docker-compose.yml` - Qdrant setup
- `requirements.txt` - Python dependencies

## Working Instructions

### Before Starting Any Task

1. **Update yourself on recent changes:**
   ```bash
   git status
   git log --oneline -10
   ```

2. **Check documentation status:**
   - Read `TODO.md` for current tasks
   - Check `CHANGELOG.md` for recent changes
   - Review this file for any updates

3. **Verify system health:**
   ```bash
   # Check Qdrant
   curl http://localhost:6333/health

   # Run tests
   pytest tests/ -v --tb=short
   ```

### When Making Changes

1. **Update documentation incrementally:**
   - Add entry to `CHANGELOG.md` under "Unreleased" section
   - Update relevant items in `TODO.md` (mark completed, add new discoveries)
   - Update this file if you discover important patterns or files

2. **Follow existing patterns:**
   - Use type hints for all function parameters and returns
   - Write docstrings for public functions
   - Create tests for new functionality
   - Use async/await for I/O operations

3. **Test your changes:**
   ```bash
   # Run affected tests
   pytest tests/unit/test_[module].py -v

   # Check coverage
   pytest tests/ --cov=src --cov-report=term-missing
   ```

4. **Maintain test coverage standards:**
   - **REQUIRED:** Maintain minimum 85% test coverage for all new features
   - Write tests for all new functionality before marking work as complete
   - Include unit tests for individual components
   - Include integration tests for end-to-end workflows
   - Test both success and error paths

## Planning & Tracking System

### Overview
All detailed planning, implementation notes, and working documents are stored in the `planning_docs/` folder. This keeps the root clean while providing a structured way to track complex work.

### TODO ID System
Every item in `TODO.md` should have a unique ID in the format:
- Feature items: `FEAT-XXX` (e.g., FEAT-001)
- Bug fixes: `BUG-XXX` (e.g., BUG-001)
- Testing items: `TEST-XXX` (e.g., TEST-001)
- Documentation: `DOC-XXX` (e.g., DOC-001)
- Performance: `PERF-XXX` (e.g., PERF-001)
- Refactoring: `REF-XXX` (e.g., REF-001)
- UX improvements: `UX-XXX` (e.g., UX-001)

### Planning Document Naming
**ALL planning documents MUST be stored in `planning_docs/` and prefixed with their TODO ID.**

**Format:** `planning_docs/{ID}_{description}.md`

**Examples:**
- `planning_docs/TEST-001_cli_commands_testing.md`
- `planning_docs/FEAT-002_retrieval_gate_implementation.md`
- `planning_docs/BUG-003_typescript_parser_fix.md`
- `planning_docs/UX-001_setup_friction_reduction.md`

**This includes:**
- ✅ Planning documents (before starting work)
- ✅ Progress tracking documents (during work)
- ✅ Implementation summaries (after completion)
- ✅ Session summaries related to specific TODOs
- ✅ Design documents for features
- ✅ Any other task-related documentation

**Do NOT create task-related documents in the root directory.**
Root-level docs should only be:
- README.md (user-facing)
- CHANGELOG.md (version history)
- TODO.md (task list)
- CLAUDE.md (this file)

### Planning Document Contents
Each planning document should include:
1. **Reference**: Link to the TODO item
2. **Objective**: Clear goal statement
3. **Current State**: What exists now
4. **Implementation Plan**: Step-by-step approach
5. **Progress Tracking**: Checklist of completed steps
6. **Notes & Decisions**: Important findings, decisions made
7. **Test Cases**: How to verify completion
8. **Code Snippets**: Relevant code examples or patches

### Working Process
1. **Starting a task**:
   - Find the TODO item and its ID
   - Check `planning_docs/` for existing `{ID}_*.md` file
   - Create one if it doesn't exist
   - Review any existing notes before starting

2. **During work**:
   - Update the planning doc with progress
   - Add code snippets, test results, decisions
   - Note any blockers or issues discovered

3. **Completing a task**:
   - Update the planning doc with final state
   - Add a "Completion Summary" section to the planning doc
   - Mark the TODO item as complete in TODO.md
   - Update CHANGELOG.md if significant
   - Keep the planning doc for historical reference
   - **IMPORTANT**: Do NOT create separate completion summaries in the root directory

### Completion Summaries
When completing complex tasks (especially multi-feature efforts), add a comprehensive summary to the existing planning document:

**Format:**
- Add to the existing `planning_docs/{ID}_*.md` file
- Add a "## Completion Summary" section at the end
- Include: what was built, impact, files changed, next steps

**Example:**
```markdown
# UX-001: Setup Friction Reduction

[... existing planning content ...]

## Completion Summary

**Status:** ✅ Complete
**Date:** 2025-11-16
**Implementation Time:** 3 days

### What Was Built
- Interactive setup wizard (setup.py)
- Python parser fallback
- SQLite-first configuration
- Health check command
- Post-install verification

### Impact
- Installation time: 30min → 3min (-90%)
- Success rate: 30% → 90% (+200%)
- Prerequisites: 4 → 1 (-75%)

### Files Changed
- Created: setup.py, src/memory/python_parser.py, ...
- Modified: src/config.py, requirements.txt, README.md

### Next Steps
- Beta testing
- Update documentation
```

**For multi-TODO summaries** (e.g., completing UX-001 through UX-005):
- Choose the primary TODO ID (e.g., UX-001)
- Add summary to `planning_docs/UX-001_setup_friction_reduction.md`
- Reference related TODOs in the summary
- OR create `planning_docs/UX-001-005_setup_complete.md` if preferred

### Example Planning Document
```markdown
# TEST-001: CLI Commands Testing

## TODO Reference
- TODO.md: "CLI commands testing (~15 tests) → +5.5%"

## Objective
Add comprehensive test coverage for CLI commands (index and watch) to increase overall coverage by ~5.5%.

## Current State
- CLI commands exist but have 0% test coverage
- Files: src/cli/index_command.py, src/cli/watch_command.py

## Implementation Plan
- [ ] Create tests/unit/test_cli_index.py
- [ ] Create tests/unit/test_cli_watch.py
- [ ] Mock file system operations
- [ ] Test success paths
- [ ] Test error handling
- [ ] Test argument parsing

## Progress
- [x] Created test file structure
- [ ] Implemented index command tests
- [ ] Implemented watch command tests

## Notes
- Need to mock asyncio for watch command
- Consider using pytest-asyncio fixtures
```

### Maintenance Rules
1. **Always maintain ID consistency** between TODO.md and planning_docs/
2. **Never delete planning docs** - they serve as implementation history
3. **Update both TODO and planning doc** when status changes
4. **Check for existing planning docs** before starting any TODO item
5. **Create planning doc for complex items** (anything requiring multiple steps)

### Common Tasks

#### Index a Codebase
```bash
python -m src.cli index ./path/to/code --project-name my-project
```

#### Run File Watcher
```bash
python -m src.cli watch ./path/to/code
```

#### Test Code Search
```python
# Via test script
python test_code_search.py
```

#### Start MCP Server
```bash
python -m src.mcp_server
```

## Project Structure

```
/
├── src/
│   ├── core/           # MCP server, models, validation
│   ├── store/          # Storage backends (Qdrant, SQLite)
│   ├── embeddings/     # Embedding generation and caching
│   ├── memory/         # Code indexing and file watching
│   ├── cli/            # Command-line interface
│   └── mcp_server.py   # MCP entry point
├── rust_core/          # Rust parsing module
├── tests/              # Comprehensive test suite
├── docs/               # User documentation
└── [config files]      # .env, requirements.txt, etc.
```

## Current State (Auto-Update This Section)

### Metrics
- **Test Status:** 712/712 passing ✅
- **Coverage:** 85.02% overall (ACHIEVED TARGET! 🎉)
- **Languages:** Python, JavaScript, TypeScript, Java, Go, Rust
- **Performance:** 7-13ms search, 2.45 files/sec indexing

### Active Development
- ✅ **COMPLETED (Nov 16):** Test coverage reached 85% (21.3% improvement)
- ✅ **COMPLETED (Nov 17):** UX improvements (UX-006, UX-007, UX-010)
  - Enhanced status command with real project statistics
  - Real-time indexing progress indicators with rich UI
  - File watcher status visibility in status command
- **IN PROGRESS:** Additional UX improvements (UX-008, UX-009)
- Phase 3.5: Adaptive Retrieval Gate (optional)
- Additional language support planning

### Known Issues
- None critical - test suite is comprehensive and passing

## Key Commands Reference

### Development
```bash
# Install dependencies
pip install -r requirements.txt

# Build Rust module
cd rust_core && maturin develop && cd ..

# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=src --cov-report=html

# Start Qdrant
docker-compose up -d
```

### Testing Specific Modules
```bash
# Unit tests only
pytest tests/unit/ -v

# Integration tests
pytest tests/integration/ -v

# Security tests
pytest tests/security/ -v
```

### Debugging
```bash
# Check Qdrant health
curl http://localhost:6333/health

# View logs
tail -f ~/.claude-rag/security.log

# Python shell with project
python -c "from src.core.server import MemoryRAGServer; print('Import successful')"
```

## Important Patterns

### Error Handling
- Use specific exceptions from `src/core/exceptions.py`
- Always provide context in error messages
- Log errors before re-raising

### Async Operations
- Use `async def` for I/O operations
- Batch operations when possible
- Use `asyncio.gather()` for parallel operations

### Testing
- Mock external dependencies in unit tests
- Use fixtures for common test data
- Test both success and failure paths

### Documentation
- Update CHANGELOG.md with all changes
- Mark TODO.md items as complete
- Keep this file current

## Self-Update Protocol

After completing any session, update the following:

### 1. CLAUDE.md (this file)
- Any new important files discovered
- Updated metrics (tests, coverage)
- New patterns or conventions found
- Active development focus changes

### 2. TODO.md
- Assign IDs to any new items added
- Mark completed items with ~~strikethrough~~
- Update status/progress notes
- Maintain ID consistency

### 3. Planning Documents
- Create planning docs for new complex tasks
- Update progress in existing planning docs
- Note important decisions or blockers
- Add test results and code snippets

### 4. CHANGELOG.md
- Add entries under "Unreleased" for significant changes
- Include ID references where applicable

Remember: This documentation system is your future self's context. Keep it accurate, organized, and useful.