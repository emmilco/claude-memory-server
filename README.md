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
│  • Code files (Python, JS, TS, Java, Go, Rust, PHP)     │
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

**Status:** v4.0 RC1 • ✅ 2723 tests (BUG-023 fixed) • 67% coverage • 7-13ms search latency

**Version:** 4.0 (Production-Ready Enterprise Features)

## Features

### 🔍 Semantic Code Search (NEW!)

Search your codebase by meaning, not keywords. Ask questions in natural language and find relevant code based on semantics, not just text matching.

**Example Searches:**

```
📌 Find authentication logic:
You: "Find the authentication logic"
→ auth/handlers.py:45-67 - login() async function
→ auth/middleware.py:23-45 - authenticate_request()
→ auth/token.py:12-34 - verify_jwt_token()

📌 Find error handling:
You: "Where do we handle database errors?"
→ db/connection.py:89-105 - handle_db_exception()
→ models/base.py:34-56 - retry_on_connection_error() decorator
→ api/error_handlers.py:12-28 - database_error_handler()

📌 Find API endpoints:
You: "Show me all the user-related API routes"
→ api/routes/users.py:23-45 - GET /api/users endpoint
→ api/routes/users.py:67-89 - POST /api/users/create endpoint
→ api/routes/users.py:102-124 - PUT /api/users/{id} endpoint

📌 Find initialization code:
You: "How does the application start up?"
→ main.py:12-34 - initialize_app() function
→ config/startup.py:45-78 - load_configuration()
→ db/init.py:23-45 - setup_database_connection()
```

**Why It Works:**
- **Semantic Understanding**: Finds code based on what it *does*, not just variable names
- **Hybrid Mode**: Combines semantic search with keyword matching for precision
- **Context-Aware**: Understands relationships between functions, classes, and modules
- **Fast**: 7-13ms search latency, even on large codebases

**Supported Languages:**
- **Programming:** Python, JavaScript, TypeScript, Java, Go, Rust, Ruby, Swift, Kotlin, PHP, C, C++, C#, SQL (14 languages)
- **Configuration:** JSON, YAML, TOML (3 formats)
- **Total:** 17 file formats supported

**Performance:**
- 7-13ms search latency (hybrid search: 10-18ms)
- 10-20 files/sec indexing (with parallel embeddings, 4-8x faster)
- 98% cache hit rate for re-indexing (5-10x faster)
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
- **Required:**
  - Python 3.8+ (Python 3.13+ recommended for best performance)
  - Docker (for Qdrant vector database - **required for semantic code search**)
- **Optional:** Rust (for faster code parsing, falls back to Python if unavailable)
- ~1GB disk space (10GB recommended for large codebases)

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
- ✅ Configure storage (Qdrant vector database for semantic search)
- ✅ Start Qdrant via Docker (required for code search)
- ✅ Set up parser (Python fallback if Rust unavailable)
- ✅ Verify everything works

**Result:** Working installation in 2-5 minutes!

**Note:** Semantic code search requires Qdrant running on Docker. Use `claude-rag validate-setup` to check your setup.

### Add to Claude Code

```bash
# Step 1: Get absolute Python path (important for pyenv users!)
PYTHON_PATH=$(which python)
echo "Python path: $PYTHON_PATH"  # Verify the path

# Step 2: Get project directory (make sure you're in claude-memory-server directory!)
PROJECT_DIR=$(pwd)
echo "Project directory: $PROJECT_DIR"  # Verify the path

# Step 3: Add MCP server with absolute paths
claude mcp add --transport stdio --scope user \
  claude-memory-rag -- \
  $PYTHON_PATH "$PROJECT_DIR/src/mcp_server.py"
```

**What these variables mean:**
- `$PYTHON_PATH`: The full path to your Python interpreter (e.g., `/usr/local/bin/python3`)
- `$PROJECT_DIR`: The full path to this project directory (e.g., `/Users/you/claude-memory-server`)
- These are bash shell variables that get automatically replaced with the actual paths when you run the commands above

**Important Configuration Notes:**
- **For pyenv users:** Using the absolute Python path (`$PYTHON_PATH`) ensures the MCP server uses the correct Python environment with installed dependencies, even when you switch between different project directories with different pyenv environments.
- **Use absolute script path:** The configuration uses the full path to `mcp_server.py` instead of `-m src.mcp_server` to ensure it works from any directory. The `cwd` parameter is not reliably respected in all Claude Code versions.

### Verify Installation

```bash
# Quick health check
python -m src.cli health

# Comprehensive validation (checks Python, dependencies, Qdrant, parsers)
python -m src.cli validate-install

# If validation fails, follow the actionable error messages provided
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
export CLAUDE_RAG_STORAGE_BACKEND=qdrant
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

**Browse memories interactively:**
```bash
# Launch the interactive memory browser (TUI)
python -m src.cli browse

# Features:
# - Full-text search across all memories
# - Filter by category, context level, or project
# - View detailed memory metadata (provenance, trust score, usage stats)
# - Navigate with keyboard shortcuts
# - Real-time search as you type
```

### Project Archival

**Archive inactive projects:**
```bash
# View project status
python -m src.cli archival status
# Shows active, paused, archived projects with inactivity metrics

# Archive a project to save storage
python -m src.cli archival archive old-project
# ✅ Compressed and archived (77% storage reduction)

# Reactivate when needed
python -m src.cli archival reactivate old-project
# ✅ Restored in ~10 seconds
```

**Export for backup or migration:**
```bash
# Export archived project to portable file
python -m src.cli archival export my-project
# Creates: my-project_archive_20251118_103000.tar.gz (28.3 MB)
# Includes: compressed index, manifest, README

# Import on another machine
python -m src.cli archival import my-project_archive_20251118_103000.tar.gz
# ✅ Imported project 'my-project' (28.3 MB)

# List available exports
python -m src.cli archival list-exportable
# Shows all archived projects ready for export
```

**Storage Optimization:**
- **Compression**: 60-80% storage reduction for archived projects
- **Portable**: Export to .tar.gz for backups or sharing
- **Automatic**: Configure auto-archival based on inactivity
- **Fast**: Restore archived projects in 5-30 seconds

**Example Savings:**
```
Before: 623.7 MB (5000 files, active project)
After:  142.8 MB (archived with compression)
Saved:  77% storage reduction
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
- **`get_status`** - View memory and indexing statistics
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
- **Python 3.8+** - Main application (3.13+ recommended)
- **Rust 1.91** - Fast code parsing (tree-sitter, optional)
- **Qdrant** - Vector database (optional, SQLite fallback available)
- **PyO3** - Python-Rust bridge (optional)

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
1. **[TUTORIAL.md](TUTORIAL.md)** - 🚀 **START HERE!** Complete beginner-friendly tutorial (macOS + Qdrant)
2. **[README.md](README.md)** - This file (user guide and quick reference)
3. **[CLAUDE.md](CLAUDE.md)** - Guide for AI agents working on this project
4. **[CHANGELOG.md](CHANGELOG.md)** - Version history and changes
5. **[TODO.md](TODO.md)** - Current tasks and future work

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

The server can be configured using either **JSON config file** (recommended) or **environment variables**.

**Configuration Priority (highest to lowest):**
1. Environment variables (`CLAUDE_RAG_*`)
2. JSON config file (`~/.claude-rag/config.json`)
3. Built-in defaults

### Option 1: JSON Configuration (Recommended)

Create `~/.claude-rag/config.json`:

```json
{
  "storage_backend": "qdrant",
  "embedding_model": "all-MiniLM-L6-v2",
  "enable_parallel_embeddings": true,
  "enable_file_watcher": true,
  "watch_debounce_ms": 1000
}
```

**Benefits:**
- Easier to read and edit
- Persistent across all projects
- No environment variable conflicts
- See `config.json.example` for all options with comments

**Common Presets:**

```json
// Standard
{
  "storage_backend": "qdrant",
  "qdrant_url": "http://localhost:6333",
  "enable_parallel_embeddings": true
}

// High Performance
{
  "storage_backend": "qdrant",
  "enable_parallel_embeddings": true,
  "embedding_parallel_workers": 8,
  "embedding_batch_size": 64,
  "enable_hybrid_search": true
}
```

### Option 2: Environment Variables

Create `.env` file (project-specific configuration):

```bash
# Storage Backend
CLAUDE_RAG_STORAGE_BACKEND=qdrant
CLAUDE_RAG_QDRANT_URL=http://localhost:6333

# Embeddings
CLAUDE_RAG_EMBEDDING_MODEL=all-MiniLM-L6-v2
CLAUDE_RAG_ENABLE_PARALLEL_EMBEDDINGS=true

# File Watching
CLAUDE_RAG_ENABLE_FILE_WATCHER=true
CLAUDE_RAG_WATCH_DEBOUNCE_MS=1000
```

**When to use:**
- Override global settings for specific projects
- Temporary configuration changes
- CI/CD environments
- See `.env.example` for all available variables

### Quick Configuration Guide

```bash
# View current configuration
python -m src.cli status

# Configure storage backend
export CLAUDE_RAG_STORAGE_BACKEND=qdrant
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

### Code Indexing
- **Files indexed:** 29
- **Semantic units:** 981
- **Time:** 11.82 seconds
- **Success rate:** 100%
- **Search latency:** 6.3ms average
- **Throughput:** 2.45 files/sec

### Project Archival
- **Compression ratio:** 0.20-0.30 (70-80% reduction)
- **Archive time:** 5-30 seconds (varies by project size)
- **Restore time:** 5-20 seconds
- **Export/import roundtrip:** 100% integrity
- **Storage savings:** 60-80% for archived projects

**Example Archival Performance:**
| Project Size | Files | Units | Archive Time | Compressed Size | Savings |
|--------------|-------|-------|--------------|-----------------|---------|
| Small        | 100   | 500   | ~5s          | 2.1 MB          | 75%     |
| Medium       | 1000  | 5000  | ~15s         | 28.4 MB         | 77%     |
| Large        | 5000  | 25000 | ~30s         | 142.8 MB        | 77%     |

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

**🚀 Ready to get started? Follow the complete [TUTORIAL.md](TUTORIAL.md) for step-by-step setup!**
