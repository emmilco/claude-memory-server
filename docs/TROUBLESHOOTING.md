# Troubleshooting Guide

**Last Updated:** November 20, 2025
**Version:** 4.0 (Production-Ready)

---

## Quick Validation

**First-time users:** Run the installation validator to check your setup:

```bash
python -m src.cli validate-install
```

This will check:
- System prerequisites (Python, Docker, Rust, Git)
- Python package dependencies
- Qdrant connectivity
- Code parser availability
- Embedding model loading

The validator provides specific, OS-dependent install instructions for any missing components.

---

## Installation Prerequisites

### Python Version Too Old

**Error:** `Python 3.9+ is required`

**Check version:**
```bash
python --version
# or
python3 --version
```

**Solution:**

**macOS:**
```bash
brew install python@3.11
# Add to PATH if needed
```

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install python3.11 python3.11-venv python3.11-dev
```

**Fedora/RHEL:**
```bash
sudo dnf install python3.11
```

**Windows:**
- Download from https://www.python.org/downloads/
- During install, check "Add Python to PATH"

---

### pip Not Installed

**Error:** `pip: command not found`

**Solution:**

**macOS:**
```bash
python3 -m ensurepip --upgrade
# or
brew install python  # Includes pip
```

**Ubuntu/Debian:**
```bash
sudo apt-get install python3-pip
```

**Fedora/RHEL:**
```bash
sudo dnf install python3-pip
```

**Windows:**
```bash
python -m ensurepip --upgrade
```

---

### Missing Python Packages

**Error:** `ModuleNotFoundError: No module named 'sentence_transformers'`

**Solution:**

1. **Install all dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **If using virtual environment:**
   ```bash
   # Create venv
   python -m venv venv

   # Activate
   source venv/bin/activate  # macOS/Linux
   venv\Scripts\activate     # Windows

   # Install dependencies
   pip install -r requirements.txt
   ```

3. **Verify installation:**
   ```bash
   python -c "import sentence_transformers; print('OK')"
   ```

---

### pyenv Environment Isolation Issues

**Error:** MCP server fails to load or reports missing dependencies when switching between project directories

**Symptoms:**
- MCP server works in one directory but fails in another
- Error: `ModuleNotFoundError` for packages you know are installed
- MCP server won't start when in a different project directory
- Dependencies are installed but Claude can't find them

**Root Cause:**

pyenv creates isolated Python environments per project directory. When you:
1. Install dependencies in environment A (e.g., `claude-memory-server` project)
2. Configure MCP with relative path `python -m src.mcp_server`
3. Switch to environment B (e.g., `olympus-storage` project with different `.python-version`)

The MCP server tries to use environment B's Python (which doesn't have the dependencies), causing it to fail.

**Solution 1: Use Absolute Python Path (Recommended)**

Configure MCP to use the absolute path to the Python interpreter where dependencies are installed:

```bash
# 1. Navigate to claude-memory-server directory
cd ~/path/to/claude-memory-server

# 2. Activate the correct pyenv environment (if using pyenv local/shell)
# This should happen automatically if you have .python-version file

# 3. Get the absolute Python path
which python
# Example output: /Users/you/.pyenv/versions/3.13.9/bin/python

# 4. Use this absolute path in your MCP configuration
claude mcp add --transport stdio --scope user \
  claude-memory-rag -- \
  /Users/you/.pyenv/versions/3.13.9/bin/python \
  ~/path/to/claude-memory-server/src/mcp_server.py
```

**Critical:** Use the full path to `mcp_server.py` instead of `-m src.mcp_server`. The `cwd` parameter is not reliably respected in some Claude Code versions, so absolute script paths ensure the server works from any directory.

**Solution 2: Create Dedicated MCP Environment**

Create a dedicated pyenv virtualenv for MCP servers:

```bash
# 1. Create dedicated environment
pyenv virtualenv 3.13.9 claude-mcp-servers

# 2. Activate it
pyenv activate claude-mcp-servers

# 3. Install dependencies
cd ~/path/to/claude-memory-server
pip install -r requirements.txt

# 4. Get the absolute path
which python
# Example: /Users/you/.pyenv/versions/claude-mcp-servers/bin/python

# 5. Use this in MCP configuration
claude mcp add --transport stdio --scope user \
  claude-memory-rag -- \
  /Users/you/.pyenv/versions/claude-mcp-servers/bin/python \
  ~/path/to/claude-memory-server/src/mcp_server.py
```

**Solution 3: Install in Multiple Environments (Not Recommended)**

Install dependencies in every pyenv environment where you want to use the MCP server. This wastes disk space and requires maintenance.

**Verification:**

After updating your MCP configuration:

1. **Test from different directories:**
   ```bash
   cd ~/some-other-project-with-different-pyenv
   # Now restart Claude Code and verify MCP server loads
   ```

2. **Check Python path in MCP config:**
   - Your MCP configuration should show an absolute path like:
     `/Users/you/.pyenv/versions/3.13.9/bin/python`
   - **NOT** a relative path like `python` or `$(which python)`

3. **Verify dependencies are available:**
   ```bash
   /Users/you/.pyenv/versions/3.13.9/bin/python -c "import sentence_transformers, qdrant_client; print('OK')"
   ```

**Pro Tip:** The setup wizard (`python setup.py`) automatically detects pyenv and provides the correct absolute path for your MCP configuration. Look for the yellow warning message at the end of setup!

---

### MCP Server "Failed to Connect" Error

**Error:** `claude mcp list` shows "✗ Failed to connect" or `ModuleNotFoundError: No module named 'src'`

**Symptoms:**
- MCP server shows as connected in one directory but fails in others
- Error: `Error while finding module specification for 'src.mcp_server'`
- `claude mcp list` shows connection failure

**Root Cause:**

The `cwd` (current working directory) parameter in MCP configuration is not reliably respected in all Claude Code versions. When using `-m src.mcp_server` (module syntax), Python tries to find the `src` module from the current directory instead of the configured `cwd`.

**Solution: Use Absolute Script Path**

Instead of using `-m src.mcp_server`, use the full path to `mcp_server.py`:

```bash
# Remove old configuration
claude mcp remove claude-memory-rag

# Add with absolute script path
PYTHON_PATH=/Users/you/.pyenv/versions/3.13.9/bin/python  # Your Python path
SCRIPT_PATH=/Users/you/path/to/claude-memory-server/src/mcp_server.py

claude mcp add --transport stdio --scope user \
  claude-memory-rag -- \
  $PYTHON_PATH $SCRIPT_PATH
```

**Or manually edit `~/.claude.json`:**

Change this:
```json
{
  "mcpServers": {
    "claude-memory-rag": {
      "command": "/Users/you/.pyenv/versions/3.13.9/bin/python",
      "args": ["-m", "src.mcp_server"],
      "cwd": "/Users/you/path/to/claude-memory-server"
    }
  }
}
```

To this:
```json
{
  "mcpServers": {
    "claude-memory-rag": {
      "command": "/Users/you/.pyenv/versions/3.13.9/bin/python",
      "args": ["/Users/you/path/to/claude-memory-server/src/mcp_server.py"]
    }
  }
}
```

**Verification:**

```bash
# Test from any directory
cd ~/some-other-project
claude mcp list
# Should show: ✓ Connected
```

---

### Docker Not Installed

**Error:** `Docker is required but not installed`

**Note:** Docker is only required if you want to use Qdrant for vector search. The system can run with SQLite fallback.

**Solution:**

**macOS:**
```bash
# Option 1: Homebrew
brew install --cask docker

# Option 2: Direct download
# Visit https://www.docker.com/products/docker-desktop
# Download Docker Desktop for Mac

# Start Docker Desktop from Applications
```

**Ubuntu/Debian:**
```bash
# Install Docker Engine
curl -fsSL https://get.docker.com | sh

# Start Docker service
sudo systemctl enable docker
sudo systemctl start docker

# Add user to docker group (optional, requires re-login)
sudo usermod -aG docker $USER
newgrp docker  # Or log out/in

# Verify
docker ps
```

**Fedora/RHEL:**
```bash
sudo dnf install docker
sudo systemctl enable docker
sudo systemctl start docker
sudo usermod -aG docker $USER
```

**Windows:**
- Download Docker Desktop from https://www.docker.com/products/docker-desktop
- Run installer
- Restart Windows
- Start Docker Desktop from Start menu

**Without Docker (SQLite fallback):**
```bash
# Set in .env file:
CLAUDE_RAG_STORAGE_BACKEND=qdrant

# Or export:
export CLAUDE_RAG_STORAGE_BACKEND=qdrant
```

---

### Docker Daemon Not Running

**Error:** `Cannot connect to the Docker daemon`

**Solution:**

**macOS:**
```bash
# Start Docker Desktop application
open -a Docker

# Wait for Docker to start (check menu bar icon)
```

**Linux:**
```bash
# Check status
sudo systemctl status docker

# Start if not running
sudo systemctl start docker

# Enable on boot
sudo systemctl enable docker
```

**Windows:**
```bash
# Start Docker Desktop from Start menu
# Wait for "Docker Desktop is running" notification
```

**Verify:**
```bash
docker ps
# Should show empty list or running containers (not error)
```

---

### Rust Not Installed (Required)

**Error:** `Failed to build Rust parser` or `mcp_performance_core not installed`

**Note:** Rust parser is required for code indexing. There is no Python fallback.

**To install Rust:**

**macOS/Linux:**
```bash
# Install Rust via rustup
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh

# Follow prompts (default installation is fine)

# Activate Rust in current shell
source $HOME/.cargo/env

# Verify installation
cargo --version
rustc --version

# Build the parser
cd rust_core
maturin develop
cd ..
```

**Windows:**
```bash
# Download and run rustup-init.exe from:
# https://rustup.rs/

# Follow installer prompts

# Open new command prompt and verify:
cargo --version

# Build the parser
cd rust_core
maturin develop
cd ..
```

**Verify Rust parser is loaded:**
```bash
python -c "import rust_core; print('Rust parser available')"
```

**Skip Rust (use Python fallback):**
- Simply don't build the Rust module
- The system automatically detects and uses Python parser
- Performance: ~10-20x slower, but fully functional
- Check status: `python -m src.cli status` (shows parser mode)

---

## Code Parsing Issues

### File Fails to Parse (Syntax Errors)

**Symptom:** File skipped during indexing with "Parse error" message

**Common Causes:**
1. **Syntax errors in source code**
   - Incomplete functions, missing braces, etc.
   - Mixed Python 2/3 syntax
   - Invalid language-specific constructs

2. **File encoding issues**
   - Non-UTF-8 encoding (Latin-1, Windows-1252, etc.)
   - Binary data in text files
   - Invalid UTF-8 sequences

3. **Unsupported language features**
   - Experimental syntax not in tree-sitter grammar
   - Language-specific macros or preprocessor directives

**Solutions:**

**Check file syntax:**
```bash
# Python
python -m py_compile problematic_file.py

# JavaScript/TypeScript
npx eslint problematic_file.js

# Java
javac -Xlint problematic_file.java
```

**Check file encoding:**
```bash
# Detect encoding
file -I problematic_file.py
# Output: text/x-python; charset=utf-8

# Convert to UTF-8 if needed
iconv -f ISO-8859-1 -t UTF-8 file.py > file_utf8.py
```

**Workaround for unparseable files:**
```bash
# Option 1: Fix syntax errors in the file
# Option 2: Exclude from indexing (.ragignore)
echo "path/to/problematic/files/*" >> .ragignore

# Option 3: Skip and index rest of project
python -m src.cli index ./project  # Continues despite parse errors
```

---

### Slow Parsing Performance

**Symptom:** Indexing takes minutes for small projects

**Check parser mode:**
```bash
python -m src.cli status
# Look for: "Parser: Python (fallback)" vs "Parser: Rust"
```

**Solutions:**

**1. Install Rust parser (10-20x faster):**
```bash
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
source $HOME/.cargo/env
cd rust_core && maturin develop && cd ..
```

**2. Enable parallel embeddings:**
```bash
# Add to .env
CLAUDE_RAG_ENABLE_PARALLEL_EMBEDDINGS=true
CLAUDE_RAG_EMBEDDING_PARALLEL_WORKERS=auto
```

**3. Use incremental indexing:**
```bash
# First index (slow)
python -m src.cli index ./project

# Re-index (5-10x faster, only changed files)
python -m src.cli index ./project
```

---

### Large Files Cause Memory Issues

**Symptom:** Out of memory errors or system slowdown during indexing

**Check file sizes:**
```bash
find ./project -type f -size +1M | head -10
```

**Solutions:**

**1. Exclude large files:**
```bash
# Add to .ragignore
*.min.js
*.bundle.js
**/dist/**
**/build/**
**/node_modules/**
```

**2. Reduce batch size:**
```bash
# Add to .env
CLAUDE_RAG_EMBEDDING_BATCH_SIZE=16  # Default: 32
```

**3. Increase system memory:**
```bash
# Allocate more memory to Python process
ulimit -v 8388608  # 8GB limit
```

---

### Unicode/Encoding Errors

**Error:** `UnicodeDecodeError: 'utf-8' codec can't decode byte`

**Solutions:**

**1. Identify problematic files:**
```bash
# Find non-UTF-8 files
find ./project -type f -exec file -I {} \; | grep -v utf-8
```

**2. Convert files to UTF-8:**
```bash
# Batch convert
for file in $(find . -name "*.py"); do
    iconv -f ISO-8859-1 -t UTF-8 "$file" > "${file}.utf8"
    mv "${file}.utf8" "$file"
done
```

**3. Configure parser to handle errors:**
The parser automatically uses `errors='ignore'` when reading files, so most encoding issues are handled gracefully. Files with encoding errors will be skipped with a warning.

---

### Unsupported Language

**Symptom:** Files indexed but no semantic units extracted

**Check supported languages:**
```bash
python -m src.cli status
# Shows: 15 supported file formats
```

**Supported languages:** Python, JavaScript, TypeScript, Java, Go, Rust, C, C++, C#, Ruby, Swift, Kotlin, SQL, JSON, YAML, TOML

**Solutions:**

**1. Verify file extension:**
```bash
# Correct extensions
.py   → Python
.js   → JavaScript
.ts   → TypeScript
.java → Java
.go   → Go
.rs   → Rust
.c, .h    → C
.cpp, .hpp → C++
.cs   → C#
.rb   → Ruby
.swift → Swift
.kt   → Kotlin
.sql  → SQL
```

**2. For unsupported languages:**
- Request language support (create GitHub issue)
- Files will be skipped during indexing
- No semantic search for those files

---

### Files Skipped Silently

**Symptom:** Expected files not appearing in index

**Debug indexing:**
```bash
# Enable debug logging
export CLAUDE_RAG_LOG_LEVEL=DEBUG
python -m src.cli index ./project

# Check which files were processed
python -m src.cli list-indexed-files --project myproject
```

**Common reasons:**

1. **File in .ragignore or .gitignore**
   ```bash
   cat .ragignore
   cat .gitignore
   ```

2. **Unsupported extension**
   - Only processes known file extensions
   - See "Supported languages" above

3. **File too large**
   - Default max: No hard limit, but very large files (>10MB) may timeout
   - Check logs for timeout errors

4. **Binary file**
   - Binary files are automatically skipped
   - Check with: `file filename`

**Solution:**
```bash
# Force re-index with verbose output
python -m src.cli index ./project --verbose
```

---

### Git Not Installed (Recommended)

**Error:** `git: command not found`

**Solution:**

**macOS:**
```bash
# Option 1: Xcode Command Line Tools (recommended)
xcode-select --install

# Option 2: Homebrew
brew install git
```

**Ubuntu/Debian:**
```bash
sudo apt-get install git
```

**Fedora/RHEL:**
```bash
sudo dnf install git
```

**Windows:**
- Download from https://git-scm.com/download/win
- Run installer (use default options)
- Restart terminal

**Verify:**
```bash
git --version
```

---

## Common Issues

### Installation Issues

#### Qdrant Won't Start

**Symptoms:**
```
ERROR: Cannot connect to Qdrant at localhost:6333
```

**Solutions:**

1. **Check if Qdrant is running**
   ```bash
   docker-compose ps
   # Should show qdrant as "Up"
   ```

2. **Start Qdrant**
   ```bash
   docker-compose up -d
   ```

3. **Check for port conflicts**
   ```bash
   lsof -i :6333
   # If another process is using 6333, stop it or change port
   ```

4. **Remove old volumes and restart**
   ```bash
   docker-compose down -v
   docker-compose up -d
   ```

5. **Check Docker is running**
   ```bash
   docker ps
   # Should list running containers
   ```

---

#### Rust Module Won't Build

**Symptoms:**
```
ERROR: Command 'maturin develop' failed
```

**Solutions:**

1. **Ensure Rust is installed** (required for code indexing)
   ```bash
   rustc --version
   # Should show: rustc 1.91+
   ```

3. **Update Rust**
   ```bash
   rustup update
   ```

4. **Add Rust to PATH**
   ```bash
   source $HOME/.cargo/env
   ```

5. **Clean and rebuild**
   ```bash
   cd rust_core
   cargo clean
   maturin develop
   ```

6. **Install build dependencies (Linux)**
   ```bash
   sudo apt install build-essential
   ```

---

#### Import Errors

**Symptoms:**
```python
ImportError: No module named 'mcp_performance_core'
```

**Solutions:**

1. **Build Rust module**
   ```bash
   cd rust_core && maturin develop && cd ..
   ```

2. **Reinstall Python dependencies**
   ```bash
   pip install --force-reinstall -r requirements.txt
   ```

3. **Check virtual environment**
   ```bash
   which python  # Should point to venv
   source venv/bin/activate
   ```

4. **Verify Python version**
   ```bash
   python --version  # Should be 3.13+
   ```

---

### Runtime Issues

#### Slow Indexing

**Symptoms:**
- Indexing takes >10 minutes for small projects
- Parse times >100ms per file

**Solutions:**

1. **Check Rust module is being used**
   ```python
   import mcp_performance_core
   print("Rust module loaded")
   # If ImportError, rebuild Rust module
   ```

2. **Enable incremental indexing**
   ```bash
   # First index will be slow
   python -m src.cli index ./src
   
   # Subsequent indexes should be fast
   python -m src.cli index ./src
   ```

3. **Check Qdrant connection**
   ```bash
   curl http://localhost:6333/health
   ```

4. **Reduce batch size** (if memory limited)
   ```python
   # In config.py
   EMBEDDING_BATCH_SIZE = 16  # Default: 32
   ```

---

#### Slow Search

**Symptoms:**
- Search takes >100ms
- Queries time out

**Solutions:**

1. **Use filters to reduce search space**
   ```python
   # Add project_name or language filters
   results = await server.search_code(
       query="auth",
       project_name="my-app"  # Reduces search space
   )
   ```

2. **Reduce limit**
   ```python
   results = await server.search_code(
       query="auth",
       limit=5  # Default: 10
   )
   ```

3. **Check embedding cache**
   ```python
   # Cache should have high hit rate
   stats = cache.get_stats()
   print(f"Hit rate: {stats['hit_rate']}")  # Should be >80%
   ```

4. **Optimize Qdrant**
   ```bash
   # Restart Qdrant to clear memory
   docker-compose restart qdrant
   ```

---

#### Memory Errors

**Symptoms:**
```
MemoryError: Cannot allocate memory
```

**Solutions:**

1. **Enable quantization** (saves 75% memory)
   ```python
   # In qdrant_setup.py, ensure quantization enabled
   quantization_config={"scalar": {"type": "int8"}}
   ```

2. **Reduce batch size**
   ```python
   # In config.py
   EMBEDDING_BATCH_SIZE = 16  # Reduce from 32
   ```

3. **Limit concurrent operations**
   ```bash
   # Index fewer files at once
   python -m src.cli index ./src/core  # Not entire src/
   ```

4. **Clear embedding cache**
   ```bash
   rm ~/.claude-rag/embedding_cache.db
   ```

---

### Test Failures

#### Tests Fail to Start

**Symptoms:**
```
ERROR: Qdrant not available
```

**Solutions:**

1. **Start Qdrant before tests**
   ```bash
   docker-compose up -d
   pytest tests/
   ```

2. **Check test configuration**
   ```bash
   # Ensure test database is accessible
   ls ~/.claude-rag/
   ```

---

#### Security Tests Fail

**Symptoms:**
```
FAILED tests/security/test_injection_attacks.py
```

**Solutions:**

1. **This is actually good!** Security tests verify that attacks are blocked.
   - Tests SHOULD pass (meaning attacks were blocked)
   - Tests FAILING means attacks got through (bad)

2. **Check validation module**
   ```python
   from src.core.validation import detect_injection_patterns
   result = detect_injection_patterns("'; DROP TABLE--")
   assert result is not None  # Should detect pattern
   ```

---

### Search Quality Issues

#### No Results Found

**Symptoms:**
- Search returns empty results
- Known code not found

**Solutions:**

1. **Check status first**
   ```bash
   python -m src.cli status
   # Verify project is indexed with files
   ```

2. **Verify indexing completed**
   ```bash
   # Re-index with verbose output
   python -m src.cli index ./src
   ```

3. **Check collection exists**
   ```bash
   curl http://localhost:6333/collections/memory
   # Should show points_count > 0
   ```

4. **Try different search modes**
   ```python
   # Try semantic search
   results = await server.search_code(
       query="authentication",
       search_mode="semantic"
   )

   # Try keyword search
   results = await server.search_code(
       query="authenticate",
       search_mode="keyword"
   )

   # Try hybrid search
   results = await server.search_code(
       query="authenticate user",
       search_mode="hybrid"
   )
   ```

5. **Try broader query**
   ```python
   # Instead of: "JWT token validation function"
   # Try: "token validation"
   ```

6. **Remove filters temporarily**
   ```python
   # Remove project_name, language filters to test
   results = await server.search_code(query="auth")
   ```

---

#### Irrelevant Results

**Symptoms:**
- Search returns wrong results
- Low relevance scores

**Solutions:**

1. **Be more specific**
   ```python
   # Instead of: "function"
   # Use: "user authentication function"
   ```

2. **Use filters**
   ```python
   results = await server.search_code(
       query="parse function",
       language="python",  # Narrow by language
       file_pattern="*/parsers/*"  # Narrow by path
   )
   ```

3. **Check score threshold**
   ```python
   # Filter out low-confidence results
   results = [r for r in results if r['score'] > 0.7]
   ```

---

### Configuration Issues

#### Environment Variables Not Loaded

**Symptoms:**
```
Using default settings instead of .env values
```

**Solutions:**

1. **Create .env file in project root**
   ```bash
   touch .env
   # Add your variables
   ```

2. **Load .env explicitly**
   ```python
   from dotenv import load_dotenv
   load_dotenv()
   ```

3. **Export manually**
   ```bash
   export CLAUDE_RAG_QDRANT_URL=http://localhost:6333
   python -m src.mcp_server
   ```

---

## Error Messages

### ValidationError

**Message:**
```
ValidationError: Potential security threat detected: SQL injection pattern
```

**Meaning:** Input contains suspicious patterns (SQL, prompt, or command injection)

**Solution:**
- This is working correctly - the input is being blocked for security
- Review input content
- If legitimate, rephrase to avoid trigger patterns

---

### ReadOnlyError

**Message:**
```
ReadOnlyError: Server is in read-only mode
```

**Meaning:** Attempting to write while in read-only mode

**Solution:**
```bash
# Disable read-only mode
export CLAUDE_RAG_READ_ONLY_MODE=false
# or remove --read-only flag
```

---

### StorageError

**Message:**
```
StorageError: Failed to connect to Qdrant
```

**Meaning:** Cannot reach Qdrant database

**Solutions:**
1. Start Qdrant: `docker-compose up -d`
2. Check URL: `curl http://localhost:6333/health`
3. Check firewall settings

---

## Debugging Tips

### Run Health Check

```bash
python -m src.cli health
# Shows comprehensive system status
```

### Check Status

```bash
python -m src.cli status
# Shows indexed projects, storage, file watcher, cache
```

### Enable Debug Logging

```python
import logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
```

Or via environment:
```bash
export CLAUDE_RAG_LOG_LEVEL=DEBUG
```

### Check Qdrant Status

```bash
# Health check
curl http://localhost:6333/health

# Collections list
curl http://localhost:6333/collections

# Collection details
curl http://localhost:6333/collections/memory

# Point count
curl http://localhost:6333/collections/memory | jq '.result.points_count'
```

### Verify Parser

```python
# Test Rust import
try:
    import mcp_performance_core
    print("✓ Rust module available (fast parsing)")
    print(f"Functions: {dir(mcp_performance_core)}")
except ImportError as e:
    print(f"⚠ Using Python parser fallback (slower but works)")
    print(f"Error: {e}")
```

### Test Embedding Generation

```python
from src.embeddings.generator import EmbeddingGenerator

gen = EmbeddingGenerator()
emb = await gen.generate("test text")
print(f"Embedding dimensions: {len(emb)}")  # Should be 384
```

### Test Search Modes

```python
# Test all search modes
for mode in ["semantic", "keyword", "hybrid"]:
    results = await server.search_code(
        query="authenticate",
        search_mode=mode
    )
    print(f"{mode}: {len(results['results'])} results")
```

---

## Getting Help

### Before Asking for Help

1. **Check logs:**
   - Application logs (stdout)
   - Security logs (`~/.claude-rag/security.log`)
   - Qdrant logs (`docker-compose logs qdrant`)

2. **Run diagnostics:**
   ```bash
   # Check versions
   python --version
   rustc --version
   docker --version
   
   # Check services
   docker-compose ps
   curl http://localhost:6333/health
   
   # Run tests
   pytest tests/ -v
   ```

3. **Gather information:**
   - OS and version
   - Python version
   - Error message (full traceback)
   - Steps to reproduce

### Where to Get Help

1. **Documentation:** Check other docs in `docs/`
2. **Issues:** GitHub Issues (if public repo)
3. **Tests:** Look at test files for usage examples
4. **Code:** Read source code comments

---

## Frequently Asked Questions

**Q: Why is the first query slow?**
A: Model loading takes ~1s. Subsequent queries use cached model and are fast.

**Q: Can I use SQLite instead of Qdrant?**
A: Qdrant is required for semantic code search. SQLite backend has been removed.

**Q: How do I reset everything?**
A: 
```bash
docker-compose down -v
rm -rf ~/.claude-rag/
rm -rf qdrant_storage/
```

**Q: Why are some files not indexed?**
A: Only supported languages are indexed (.py, .js, .ts, .java, .go, .rs). Check file extensions.

**Q: Can I index private repositories?**
A: Yes, everything is local. No data leaves your machine.

---

**Still having issues? Check the documentation or create an issue.**
