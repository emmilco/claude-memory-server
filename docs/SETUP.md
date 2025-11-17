# Setup Guide

**Last Updated:** November 16, 2025

---

## Prerequisites

- **Python:** 3.13 or higher
- **Rust:** 1.91 or higher (for building)
- **Docker:** For Qdrant vector database
- **Git:** For cloning the repository
- **Disk Space:** 1GB minimum (10GB recommended for large codebases)
- **RAM:** 2GB minimum (4GB recommended)

---

## Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/yourorg/claude-memory-server.git
cd claude-memory-server
```

### 2. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 3. Start Qdrant (Vector Database)

```bash
docker-compose up -d
```

Verify Qdrant is running:
```bash
curl http://localhost:6333/health
# Should return: OK
```

### 4. Build Rust Module

```bash
cd rust_core
maturin develop
cd ..
```

### 5. Run Tests

```bash
pytest tests/ -v
# Should see: 427 passed
```

### 6. Index Your First Codebase

```bash
python -m src.cli index ./src --project-name claude-memory
```

### 7. Test Code Search

```bash
python test_code_search.py
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

# Features
CLAUDE_RAG_ENABLE_FILE_WATCHER=true
CLAUDE_RAG_WATCH_DEBOUNCE_MS=1000

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

**Setup Complete!** You're ready to use the Claude Memory RAG Server.
