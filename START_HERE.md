# 🚀 START HERE - New Claude Agent Guide

**Last Updated:** November 16, 2025

## Quick Context

You're working on the **Claude Memory RAG Server** - an MCP server that provides:
- 🧠 Persistent memory for Claude
- 📚 Documentation search
- 🔍 **Semantic code search** (NEW!)

## 📊 Current Status: PRODUCTION READY ✅

**What's Working:**
- ✅ Semantic code search through MCP tools
- ✅ Index entire codebases (6 languages: Python, JS, TS, Java, Go, Rust)
- ✅ Real-time file watching with auto-reindexing
- ✅ CLI tools for indexing and watching
- ✅ Vector database (Qdrant) with sub-10ms search
- ✅ 68/68 tests passing

**Performance:**
- 🚀 7-13ms semantic code search latency
- 🚀 2.45 files/sec indexing speed
- 🚀 1-6ms Rust parsing per file

## 🗺️ Project Structure

```
claude-memory-server/
├── src/
│   ├── core/              # Core MCP server
│   │   ├── server.py      # Main MemoryRAGServer with search_code/index_codebase
│   │   ├── models.py      # Pydantic data models
│   │   └── exceptions.py  # Custom exceptions
│   ├── store/             # Vector storage
│   │   ├── qdrant_store.py    # Qdrant implementation (PRIMARY)
│   │   ├── sqlite_store.py    # SQLite fallback
│   │   └── base.py            # Abstract interface
│   ├── embeddings/        # Embedding generation
│   │   ├── generator.py   # Async embedding engine
│   │   ├── cache.py       # Embedding cache (SQLite)
│   │   └── rust_bridge.py # Rust integration
│   ├── memory/            # Code indexing
│   │   ├── incremental_indexer.py  # Main indexer (395 lines)
│   │   ├── file_watcher.py         # Auto-reindexing
│   │   └── indexing_service.py     # Service integration
│   ├── cli/               # CLI commands
│   │   ├── index_command.py   # Manual indexing
│   │   └── watch_command.py   # File watching
│   ├── mcp_server.py      # MCP entry point (OLD architecture bridge)
│   └── config.py          # Configuration
├── rust_core/             # Rust parsing module
│   ├── src/
│   │   ├── lib.rs         # PyO3 bindings
│   │   └── parsing.rs     # Tree-sitter parsing (6 languages)
│   └── Cargo.toml
├── tests/                 # Test suite (68/68 passing)
│   ├── unit/              # Unit tests
│   └── integration/       # Integration tests
└── docs/                  # Documentation
```

## 📖 Essential Reading (In Order)

1. **PROJECT_STATUS.md** - Comprehensive current state
2. **README.md** - User-facing documentation (needs update)
3. **EXECUTABLE_DEVELOPMENT_CHECKLIST.md** - Detailed task tracking
4. **PHASE_3_COMPLETION_REPORT.md** - Technical specs for code indexing

## 🎯 What You Can Do Right Now

### As a User
```bash
# Index a codebase
python -m src.cli index ./src --project-name my-project

# Watch for changes
python -m src.cli watch ./src

# Test code search (requires Qdrant running)
python test_code_search.py
```

### As a Developer
```bash
# Run tests
pytest tests/ -v  # All 68 tests should pass

# Run benchmarks
python benchmark_indexing.py

# Check Qdrant
curl http://localhost:6333/health  # Should return OK
```

## 🔧 Key Technologies

- **Python 3.13.6** - Main language
- **Rust 1.91.1** - Fast parsing (tree-sitter)
- **Qdrant** - Vector database (Docker, localhost:6333)
- **PyO3** - Python-Rust bridge
- **Pydantic v2** - Data validation
- **sentence-transformers** - Embeddings (all-MiniLM-L6-v2, 384-dim)

## ⚡ Quick Commands

```bash
# Start Qdrant (if not running)
docker-compose up -d

# Install Rust module
cd rust_core && maturin develop && cd ..

# Run full test suite
pytest tests/ -v --cov=src

# Index this codebase
python -m src.cli index ./src

# Search code (programmatically)
python test_code_search.py
```

## 🐛 Common Issues

### Qdrant not running
```bash
docker-compose up -d
curl http://localhost:6333/health
```

### Rust module not found
```bash
cd rust_core
maturin develop
cd ..
```

### Import errors
```bash
pip install -r requirements.txt
```

## 📋 What's Next?

Based on **EXECUTABLE_DEVELOPMENT_CHECKLIST.md**:

### Completed ✅
- Phase 1: Foundation (100%)
- Phase 2: Security & Context (100%)
- Phase 3.1-3.4: Code intelligence (100%)
- Phase 3.6: MCP integration (100%)

### Not Started / Optional
- Phase 3.5: Adaptive Retrieval Gate (optional optimization)
- Phase 4: Comprehensive testing docs (40% done)

### Potential Next Steps
1. **Documentation** - Expand user guides (Phase 4.2)
2. **Phase 3.5** - Implement retrieval gate (optional optimization)
3. **Testing** - Increase coverage beyond current 80%+ (Phase 4.1)
4. **More languages** - Add C++, C#, Ruby, PHP support
5. **Performance** - Additional optimization work

## 💡 Key Files to Know

### Most Important
- `src/core/server.py` - Main MCP server with all tools
- `src/memory/incremental_indexer.py` - Code indexing logic
- `src/store/qdrant_store.py` - Vector DB operations
- `rust_core/src/parsing.rs` - Fast Rust parsing

### Configuration
- `src/config.py` - All settings
- `docker-compose.yml` - Qdrant setup
- `.env` - Environment variables (create if needed)

### Tests
- `tests/unit/test_incremental_indexer.py` - Indexer tests
- `tests/integration/test_indexing_integration.py` - E2E tests
- `test_code_search.py` - MCP code search tests

## 🎓 Understanding the Flow

### Code Indexing Flow
```
1. File → Rust parser (1-6ms)
2. Extract functions/classes → Semantic units
3. Build indexable content (file:line + signature + code)
4. Generate embeddings (384-dim vectors)
5. Store in Qdrant with metadata
```

### Code Search Flow
```
1. Query → Generate embedding
2. Vector search in Qdrant (7-13ms)
3. Filter by project/language/file pattern
4. Return results with file paths & line numbers
```

### MCP Integration Flow
```
Claude → MCP Protocol → mcp_server.py
                            ↓
                    src/core/server.py
                            ↓
              ┌─────────────┴─────────────┐
              ↓                           ↓
    search_code()                index_codebase()
              ↓                           ↓
    IncrementalIndexer ← → Qdrant Vector DB
```

## 🔗 Architecture Notes

**Two Server Implementations:**
- **OLD:** `src/mcp_server.py` - Uses legacy database.py from root
- **NEW:** `src/core/server.py` - Uses Qdrant, Pydantic, modern arch
- **Bridge:** mcp_server.py calls src/core/server.py for code search

This was done for incremental migration. Future work could consolidate.

## 📞 Need Help?

1. Check **PROJECT_STATUS.md** for detailed current state
2. Check **EXECUTABLE_DEVELOPMENT_CHECKLIST.md** for task status
3. Check test files for usage examples
4. Read completion reports in root for technical details

## 🎉 Recent Wins

- **November 16, 2025:** Phase 2 Security & Context Complete! 🎉
  - Completed all input validation with 267/267 injection attack tests passing
  - Implemented read-only mode for production safety
  - Added context stratification (USER_PREFERENCE, PROJECT_CONTEXT, SESSION_STATE)
  - Specialized retrieval tools for context-level filtering
  - MCP code search integration complete
  - All tests passing (68/68)
  - Sub-10ms search latency achieved

---

**You're ready to go! Start with PROJECT_STATUS.md for full context.**
