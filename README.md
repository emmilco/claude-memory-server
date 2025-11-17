# Claude Memory + RAG Server

**A semantic memory and code understanding layer for Claude**

This is an MCP server that sits between Claude and your development environment, maintaining a persistent understanding of your codebase, preferences, and context. Think of it as giving Claude a long-term memory and the ability to semantically search your code.

### The System

```
┌─────────────────────────────────────────────────────────┐
│  Claude Code                                             │
│  "Find the authentication logic"                         │
│  "Remember I prefer Python"                              │
└────────────────┬────────────────────────────────────────┘
                 │ MCP Protocol
┌────────────────▼────────────────────────────────────────┐
│  Memory RAG Server                                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │   Memories   │  │     Code     │  │   Git Hist   │  │
│  │ (preferences,│  │   (indexed   │  │  (commits &  │  │
│  │  workflows)  │  │  functions)  │  │   changes)   │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
│         Semantic Vector Search (7ms)                     │
└─────────────────────────────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────────────┐
│  Your Development Environment                            │
│  • Code files (Python, JS, TS, Java, Go, Rust)          │
│  • Documentation (Markdown)                              │
│  • Git repository                                        │
└─────────────────────────────────────────────────────────┘
```

### How It Works

**1. Indexing:** The server parses your code (using Rust for speed), extracts semantic units (functions, classes), and stores them in a vector database with embeddings.

**2. Memory Storage:** As you work with Claude, the server automatically stores preferences, project context, and decisions. These are classified and embedded for semantic retrieval.

**3. Semantic Search:** When Claude needs information, it queries the server using natural language. The server returns relevant code, memories, or git history based on *meaning*, not keywords.

**4. Context Maintenance:** Across sessions, Claude retains understanding of your codebase structure, your preferences, and project-specific knowledge.

### What This Enables

- **Code Understanding:** Ask "where's the auth logic?" instead of grepping for function names
- **Persistent Preferences:** Claude remembers you prefer Python, use async/await, etc.
- **Project Memory:** Claude knows this project uses FastAPI, PostgreSQL, and follows specific patterns
- **Git Awareness:** Search commit history semantically, track how code evolved
- **Hybrid Search:** Combines semantic understanding with keyword precision

**Status:** Production ready • 1379/1414 tests passing • 67% coverage • 7-13ms search latency

## Features

### 🔍 Semantic Code Search (NEW!)

Search your codebase by meaning, not keywords:

```
You: Find the authentication logic
Claude: [Searches semantically]
       → auth/handlers.py:45-67 - login() function
       → auth/middleware.py:23-45 - authenticate_request()
```

**Supported Languages:**
- Python, JavaScript, TypeScript, Java, Go, Rust

**Performance:**
- 7-13ms search latency
- 2.45 files/sec indexing
- Real-time file watching with auto-reindexing

### 🧠 Automatic Memory

Claude automatically remembers:
- **Preferences**: "I prefer Python", "I always use async/await"
- **Workflows**: "I usually run tests before committing"
- **Project Facts**: "This API uses FastAPI", "Database is PostgreSQL"
- **Events**: "Fixed auth bug on Nov 15", "Deployed to production"

### 📚 Documentation Search

- Ingest markdown documentation (README, docs/ folder)
- Semantic search across all docs
- Project-specific context
- Smart chunking preserves structure

## Quick Start

### Prerequisites
- **Required:** Python 3.8+ only!
- **Optional:** Rust (for faster parsing), Docker (for better scalability)
- ~500MB disk space

### Installation (One Command!)

```bash
# Clone and setup
git clone https://github.com/yourusername/claude-memory-server.git
cd claude-memory-server
python setup.py

# That's it! The setup wizard handles everything.
```

The interactive wizard will:
- ✅ Check your system
- ✅ Install dependencies
- ✅ Configure storage (SQLite by default, no Docker needed!)
- ✅ Set up parser (Python fallback if Rust unavailable)
- ✅ Verify everything works

**Result:** Working installation in 2-5 minutes!

### Add to Claude Code

```bash
claude mcp add --transport stdio --scope user claude-memory-rag -- \
  python "$(pwd)/src/mcp_server.py"
```

### Verify Installation

```bash
python -m src.cli health
```

### Optional: Upgrade for Better Performance

```bash
# Add Rust parser (10-20x faster indexing)
python setup.py --build-rust

# Upgrade to Qdrant (better for large datasets)
python setup.py --upgrade-to-qdrant
```

<details>
<summary><b>Advanced: Manual Installation</b></summary>

If you prefer manual control:

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. (Optional) Build Rust module
cd rust_core && maturin develop && cd ..

# 3. (Optional) Start Qdrant
docker-compose up -d

# 4. Configure (edit .env or set environment variables)
export CLAUDE_RAG_STORAGE_BACKEND=sqlite  # or qdrant
```

</details>

## Usage

### Code Search

**Index a codebase:**
```bash
# Via CLI
python -m src.cli index ./src --project-name my-project

# Via Claude (MCP)
You: Please index the src directory
Claude: ✅ Indexed 175 semantic units from 4 files in 2.99s
```

**Search code:**
```bash
# Via Claude (MCP)
You: Find code related to database connections
Claude: [Shows relevant functions with file paths and line numbers]
```

**Watch for changes:**
```bash
python -m src.cli watch ./src
# Auto-reindexes when files change
```

### Memory & Documentation

**Store a preference:**
```
You: I prefer TypeScript for all new projects
Claude: ✅ Stored preference memory (global scope)
```

**Ingest documentation:**
```
You: Please analyze this directory and ingest all documentation
Claude: ✅ Documentation Ingestion Complete
        Files processed: 15
        Total chunks created: 87
```

**Query documentation:**
```
You: How does authentication work in this project?
Claude: Based on the documentation:
        [Shows relevant sections from docs]
```

## Available MCP Tools

Claude has access to these tools:

### Code Search Tools (NEW!)
- **`search_code`** - Semantic code search across indexed files
- **`index_codebase`** - Index a directory for code search

### Memory Tools
- **`store_memory`** - Store a memory (usually automatic)
- **`retrieve_memories`** - Search memories and/or docs
- **`delete_memory`** - Delete a specific memory by ID

### Documentation Tools
- **`ingest_docs`** - Ingest markdown documentation
- **`search_all`** - Explicit search without routing

### Utility Tools
- **`get_stats`** - View memory and indexing statistics
- **`show_context`** - Debug tool to see current context

## Architecture

```
┌─────────────────────────────────────┐
│          Claude via MCP              │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│      MCP Server (mcp_server.py)      │
│  ┌───────────────────────────────┐  │
│  │   search_code                 │  │
│  │   index_codebase              │  │
│  │   store_memory                │  │
│  │   retrieve_memories           │  │
│  └───────────────────────────────┘  │
└───────┬──────────────────┬──────────┘
        │                  │
        ▼                  ▼
┌──────────────┐    ┌──────────────┐
│  Incremental │    │   Qdrant     │
│   Indexer    │───▶│  Vector DB   │
│              │    │ (localhost   │
│ Rust Parser  │    │  :6333)      │
│ 1-6ms/file   │    │ 7-13ms search│
└──────────────┘    └──────────────┘
```

## Technology Stack

### Core
- **Python 3.13** - Main application
- **Rust 1.91** - Fast code parsing (tree-sitter)
- **Qdrant** - Vector database
- **PyO3** - Python-Rust bridge

### AI/ML
- **sentence-transformers** - Embedding generation
- **all-MiniLM-L6-v2** - Embedding model (384 dims)

### Storage
- **Qdrant** - Primary vector storage
- **SQLite** - Fallback + embedding cache

## Performance

| Metric | Performance |
|--------|-------------|
| Code Search | 7-13ms latency |
| Indexing | 2.45 files/sec |
| Parsing | 1-6ms per file (Rust) |
| Embedding | ~30ms per text |
| Embedding (cached) | <1ms |
| Tests | 427/427 passing ✅ |
| Code Coverage | 61.47% (active code) |

## Project Structure

```
claude-memory-server/
├── src/
│   ├── core/              # Main server logic
│   │   ├── server.py      # MemoryRAGServer with all tools
│   │   ├── models.py      # Pydantic data models
│   │   └── exceptions.py  # Custom exceptions
│   ├── store/             # Vector storage
│   │   ├── qdrant_store.py    # Qdrant (primary)
│   │   └── sqlite_store.py    # SQLite (fallback)
│   ├── embeddings/        # Embedding generation & cache
│   ├── memory/            # Code indexing
│   │   ├── incremental_indexer.py  # Main indexer
│   │   └── file_watcher.py         # Auto-reindexing
│   ├── cli/               # CLI commands (index, watch)
│   ├── mcp_server.py      # MCP entry point
│   └── config.py          # Configuration
├── rust_core/             # Rust parsing module
│   └── src/parsing.rs     # Tree-sitter parsing
├── tests/                 # 68 tests (all passing)
├── docker-compose.yml     # Qdrant setup
└── README.md              # This file
```

## Documentation

📖 **Essential Documentation:**
1. **[CLAUDE.md](CLAUDE.md)** - Guide for AI agents working on this project
2. **[CHANGELOG.md](CHANGELOG.md)** - Version history and changes
3. **[TODO.md](TODO.md)** - Current tasks and future work
4. **[README.md](README.md)** - This file (user guide)

### Comprehensive Guides (docs/)
- **[SETUP.md](docs/SETUP.md)** - Installation and setup instructions
- **[USAGE.md](docs/USAGE.md)** - How to use all features
- **[ARCHITECTURE.md](docs/ARCHITECTURE.md)** - System architecture deep-dive
- **[API.md](docs/API.md)** - Complete API reference for all MCP tools
- **[DEVELOPMENT.md](docs/DEVELOPMENT.md)** - Contributing and development guide
- **[SECURITY.md](docs/SECURITY.md)** - Security model and best practices
- **[PERFORMANCE.md](docs/PERFORMANCE.md)** - Performance benchmarks and tuning
- **[TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)** - Common issues and solutions

### Technical Documentation
- **[PHASE_3_COMPLETION_REPORT.md](PHASE_3_COMPLETION_REPORT.md)** - Code intelligence specs
- **[MCP_INTEGRATION_COMPLETE.md](MCP_INTEGRATION_COMPLETE.md)** - MCP integration details
- **[PERFORMANCE_BENCHMARK_REPORT.md](PERFORMANCE_BENCHMARK_REPORT.md)** - Performance testing

### Archived Docs
- Session summaries in `docs/archive/`

## Configuration

### Environment Variables

Create `.env` file (optional):
```bash
# Qdrant
CLAUDE_RAG_QDRANT_URL=http://localhost:6333
CLAUDE_RAG_COLLECTION_NAME=memory

# Embeddings
CLAUDE_RAG_EMBEDDING_MODEL=all-MiniLM-L6-v2

# Features
CLAUDE_RAG_ENABLE_FILE_WATCHER=true
CLAUDE_RAG_WATCH_DEBOUNCE_MS=1000
```

## Testing

```bash
# Run all tests (68/68 should pass)
pytest tests/ -v

# With coverage
pytest tests/ --cov=src --cov-report=term-missing

# Specific test suite
pytest tests/unit/ -v           # Unit tests
pytest tests/integration/ -v    # Integration tests

# Code search end-to-end
python test_code_search.py
```

## Troubleshooting

### Qdrant not connecting
```bash
# Check Qdrant status
docker-compose ps
curl http://localhost:6333/health

# Restart if needed
docker-compose restart
```

### Rust module errors
```bash
# Rebuild Rust module
cd rust_core
maturin develop
cd ..
```

### Import errors
```bash
# Reinstall dependencies
pip install -r requirements.txt
```

### Code search not working
```bash
# 1. Check Qdrant is running
curl http://localhost:6333/health

# 2. Re-index codebase
python -m src.cli index ./src

# 3. Run tests
python test_code_search.py
```

## Development

### Running Tests
```bash
pytest tests/ -v              # All tests
pytest tests/unit/ -v         # Unit only
pytest tests/integration/ -v  # Integration only
```

### Building Rust Module
```bash
cd rust_core
maturin develop --release    # For development
maturin build --release      # For distribution
cd ..
```

### Code Style
- Python: PEP 8, type hints, docstrings
- Rust: cargo fmt, clippy
- All tests must pass before merge
- **Pre-commit hook:** Enforces CHANGELOG.md updates (bypass with `--no-verify` if needed)

## Privacy & Security

- ✅ 100% local processing (no cloud sync)
- ✅ Embeddings generated locally (no external API)
- ✅ Only Claude API calls go to Anthropic
- ✅ Vector DB runs locally in Docker
- ⚠️ Database not encrypted (add SQLCipher if needed)

## Performance Benchmarks

Latest benchmark results:
- **Files indexed:** 29
- **Semantic units:** 981
- **Time:** 11.82 seconds
- **Success rate:** 100%
- **Search latency:** 6.3ms average
- **Throughput:** 2.45 files/sec

See [PERFORMANCE_BENCHMARK_REPORT.md](PERFORMANCE_BENCHMARK_REPORT.md) for details.

## Requirements

- **Python:** 3.8+ (tested on 3.13)
- **Rust:** 1.70+ (for building, not required for running)
- **Docker:** For Qdrant
- **Disk:** ~500MB (model + data)
- **RAM:** ~1GB (model loaded)

## Supported Languages

Code search currently supports:
- Python (.py)
- JavaScript (.js, .jsx)
- TypeScript (.ts, .tsx)
- Java (.java)
- Go (.go)
- Rust (.rs)

More languages can be added via tree-sitter grammars.

## Contributing

See [EXECUTABLE_DEVELOPMENT_CHECKLIST.md](EXECUTABLE_DEVELOPMENT_CHECKLIST.md) for development status and roadmap.

### Current Status
- ✅ Phase 1: Foundation (100% complete)
- ✅ Phase 2: Security & Context (100% complete)
- ✅ Phase 3: Code Intelligence (85% complete)
- ⚠️ Phase 4: Testing & docs (70% complete - 8 comprehensive guides written, coverage at 61%)

## License

MIT

## Acknowledgments

Built with:
- [Qdrant](https://qdrant.tech/) - Vector database
- [tree-sitter](https://tree-sitter.github.io/) - Code parsing
- [sentence-transformers](https://www.sbert.net/) - Embeddings
- [MCP](https://modelcontextprotocol.io/) - Model Context Protocol

---

**🚀 Ready to use! Start with [START_HERE.md](START_HERE.md) or run `python -m src.cli index ./src`**
