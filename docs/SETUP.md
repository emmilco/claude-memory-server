# Setup Guide

**Last Updated:** November 20, 2025
**Version:** 4.0 (Production-Ready)

---

## Prerequisites

### Required
- **Python:** 3.8 or higher (3.13+ recommended for best performance)
  - **Note:** Developed and tested on Python 3.13.6, should work on 3.8+
- **Disk Space:** 1GB minimum (10GB recommended for large codebases)
- **RAM:** 2GB minimum (4GB recommended)

### Optional (Recommended for Production)
- **Rust:** 1.91 or higher (for optimized parsing, 50-100x faster)
- **Docker:** For Qdrant vector database (better performance than SQLite)
- **Git:** For cloning the repository

---

## Quick Start (Recommended)

### Interactive Setup Wizard

The easiest way to get started is with the interactive setup wizard:

```bash
# Clone repository
git clone https://github.com/yourorg/claude-memory-server.git
cd claude-memory-server

# Run setup wizard
python setup.py

# Follow prompts to choose:
# - minimal: SQLite + Python parser (no dependencies, ~3 min)
# - standard: SQLite + Rust parser (faster, ~5 min)
# - full: Qdrant + Rust parser (production, ~10 min)
```

The wizard will:
1. Check prerequisites
2. Install Python dependencies
3. Set up storage backend (SQLite or Qdrant)
4. Build Rust module (optional)
5. Verify installation with sample project
6. Run health checks

### Manual Setup (Alternative)

If you prefer manual setup:

### 1. Clone the Repository

```bash
git clone https://github.com/yourorg/claude-memory-server.git
cd claude-memory-server
```

### 2. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 3. Start Qdrant (Optional - for production)

```bash
# Only needed if using Qdrant instead of SQLite
docker-compose up -d
```

Verify Qdrant is running:
```bash
curl http://localhost:6333/health
# Should return: OK
```

**Note:** SQLite works out-of-the-box with no Docker required!

### 4. Build Rust Module (Optional - for performance)

```bash
# Only needed for 50-100x faster parsing
cd rust_core
maturin develop
cd ..
```

**Note:** Pure Python parser works automatically if Rust is not available!

### 5. Run Health Check

```bash
python -m src.cli health
# Checks storage, parser, embedding model, resources
```

### 6. Index Your First Codebase

```bash
python -m src.cli index ./src --project-name claude-memory
```

### 7. View Status

```bash
python -m src.cli status
# Shows indexed projects, statistics, configuration
```

---

## Detailed Installation

### Python Environment Setup

#### Option 1: Using venv (Recommended)

```bash
python3.13 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
```

#### Option 2: Using pyenv

```bash
pyenv install 3.13.6
pyenv local 3.13.6
pip install -r requirements.txt
```

**Important for pyenv users:** When configuring the MCP server for Claude Code, you must use an **absolute Python path** to avoid environment isolation issues. If you use relative paths like `python`, the MCP server will fail when you're in a directory with a different pyenv environment.

**Recommended MCP Configuration:**
```bash
# Get the absolute path to the Python interpreter with dependencies installed
PYTHON_PATH=$(which python)
PROJECT_DIR=/Users/you/path/to/claude-memory-server  # Update this path!

# Use this in your MCP configuration with absolute script path
claude mcp add --transport stdio --scope user \
  claude-memory-rag -- \
  $PYTHON_PATH "$PROJECT_DIR/src/mcp_server.py"
```

**Important:** Use the full path to `mcp_server.py` instead of `-m src.mcp_server`. The `cwd` parameter is not reliably respected in all Claude Code versions, so absolute paths ensure the server works from any directory.

Or manually configure with the absolute paths:
- Command: `/Users/you/.pyenv/versions/3.13.6/bin/python`
- Args: `/Users/you/path/to/claude-memory-server/src/mcp_server.py`

#### Option 3: Using conda

```bash
conda create -n claude-memory python=3.13
conda activate claude-memory
pip install -r requirements.txt
```

### Rust Toolchain Setup

#### macOS/Linux

```bash
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
source $HOME/.cargo/env
rustc --version  # Verify: should show 1.91+
```

#### Windows

Download and run: https://rustup.rs/

Verify installation:
```cmd
rustc --version
```

### Building the Rust Module

The Rust module provides high-performance code parsing (50-100x faster than Python).

```bash
cd rust_core

# Development build (faster compilation)
maturin develop

# Production build (optimized)
maturin build --release

cd ..
```

Verify:
```python
python -c "import mcp_performance_core; print('OK')"
```

### Qdrant Setup

#### Docker Compose (Recommended)

```bash
# Start Qdrant
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f qdrant

# Stop Qdrant
docker-compose down
```

#### Docker Command (Alternative)

```bash
docker run -p 6333:6333 -p 6334:6334 \
  -v $(pwd)/qdrant_storage:/qdrant/storage \
  qdrant/qdrant:latest
```

#### Health Check

```bash
curl http://localhost:6333/health
# Expected: OK

# Detailed info
curl http://localhost:6333/collections
```

---

## Configuration

### Environment Variables

Create a `.env` file in the project root:

```bash
# Server
CLAUDE_RAG_SERVER_NAME=claude-memory-rag
CLAUDE_RAG_READ_ONLY_MODE=false

# Qdrant
CLAUDE_RAG_QDRANT_URL=http://localhost:6333
CLAUDE_RAG_COLLECTION_NAME=memory

# Embeddings
CLAUDE_RAG_EMBEDDING_MODEL=all-MiniLM-L6-v2
CLAUDE_RAG_EMBEDDING_DIMENSION=384
CLAUDE_RAG_EMBEDDING_BATCH_SIZE=32
CLAUDE_RAG_ENABLE_PARALLEL_EMBEDDINGS=true  # 4-8x faster indexing
CLAUDE_RAG_EMBEDDING_PARALLEL_WORKERS=auto  # auto-detects CPU count

# Features
CLAUDE_RAG_ENABLE_FILE_WATCHER=true
CLAUDE_RAG_WATCH_DEBOUNCE_MS=1000
CLAUDE_RAG_ENABLE_HYBRID_SEARCH=true  # Semantic + keyword search
CLAUDE_RAG_HYBRID_SEARCH_ALPHA=0.5  # Weight: 0=BM25 only, 1=semantic only

# Storage
CLAUDE_RAG_STORAGE_BACKEND=qdrant  # or sqlite
CLAUDE_RAG_DATA_DIR=~/.claude-rag

# Logging
CLAUDE_RAG_LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR
```

### File Locations

- **Config:** `.env` in project root
- **Embedding Cache:** `~/.claude-rag/embedding_cache.db`
- **Security Logs:** `~/.claude-rag/security.log`
- **Qdrant Data:** `./qdrant_storage/` (Docker volume)

---

## Verification

### Run All Tests

```bash
# All tests
pytest tests/ -v

# With coverage
pytest tests/ --cov=src --cov-report=term

# Specific test suites
pytest tests/unit/ -v
pytest tests/integration/ -v
pytest tests/security/ -v
```

### Test Code Indexing

```bash
# Index this codebase
python -m src.cli index ./src --project-name test-project

# Expected output:
# Indexing [1/29]: server.py
# Indexed 63 units from server.py (5.61ms parse)
# ...
# Directory indexing complete: 29 files, 175 units indexed
```

### Test Code Search

```bash
python test_code_search.py

# Expected: Search results with 7-13ms latency
```

---

## Platform-Specific Notes

### macOS

**M1/M2 (Apple Silicon):**
- Ensure Rosetta 2 is installed: `softwareupdate --install-rosetta`
- Use native ARM builds when possible

**Homebrew:**
```bash
brew install python@3.13 rust
```

### Linux (Ubuntu/Debian)

```bash
# Install dependencies
sudo apt update
sudo apt install python3.13 python3.13-venv python3-pip
sudo apt install build-essential curl

# Install Rust
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh

# Install Docker
sudo apt install docker.io docker-compose
sudo usermod -aG docker $USER  # Add user to docker group
# Log out and back in for group changes to take effect
```

### Windows

**Requirements:**
- Visual Studio Build Tools (for Rust)
- Windows Subsystem for Linux (WSL2) recommended

**Using WSL2 (Recommended):**
```bash
# Inside WSL2 Ubuntu
follow Linux instructions above
```

**Native Windows:**
```cmd
# Install Rust from rustup.rs
# Install Python 3.13 from python.org
# Install Docker Desktop

pip install -r requirements.txt
cd rust_core
maturin develop
```

---

## Troubleshooting Setup

### Qdrant Won't Start

```bash
# Check if port is already in use
lsof -i :6333

# Remove old volumes and restart
docker-compose down -v
docker-compose up -d
```

### Rust Module Build Fails

```bash
# Ensure Rust is in PATH
source $HOME/.cargo/env

# Update Rust
rustup update

# Clean and rebuild
cd rust_core
cargo clean
maturin develop
```

### Import Errors

```bash
# Reinstall requirements
pip install --force-reinstall -r requirements.txt

# Check Python version
python --version  # Should be 3.13+

# Verify virtual environment is activated
which python
```

### Permission Errors

```bash
# macOS/Linux: Use user installs
pip install --user -r requirements.txt

# Or fix venv permissions
chmod -R u+w venv/
```

---

## Next Steps

After setup is complete:

1. **Read Usage Guide:** [USAGE.md](USAGE.md) - Learn how to use the tools
2. **Read API Reference:** [API.md](API.md) - Understand all available tools
3. **Index Your Projects:** Start indexing your codebases
4. **Connect to Claude:** Configure MCP connection

---

## Performance Optimization

### Enable Parallel Embeddings (4-8x faster)

Add to `.env`:
```bash
CLAUDE_RAG_ENABLE_PARALLEL_EMBEDDINGS=true
CLAUDE_RAG_EMBEDDING_PARALLEL_WORKERS=auto  # Uses CPU count
```

### Enable Hybrid Search (Better accuracy)

Add to `.env`:
```bash
CLAUDE_RAG_ENABLE_HYBRID_SEARCH=true
CLAUDE_RAG_HYBRID_SEARCH_ALPHA=0.5  # 0.5 = balanced semantic+keyword
CLAUDE_RAG_HYBRID_FUSION_METHOD=weighted  # weighted, rrf, or cascade
```

### Use Qdrant for Production

For better performance at scale:
- **SQLite**: Good for <10K memories, no Docker required
- **Qdrant**: Recommended for >10K memories, better scalability

Switch by changing `CLAUDE_RAG_STORAGE_BACKEND=qdrant` in `.env`

---

**Setup Complete!** You're ready to use the Claude Memory RAG Server.

**Document Version:** 2.0
**Last Updated:** November 17, 2025
