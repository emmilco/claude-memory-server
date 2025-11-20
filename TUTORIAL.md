# Claude Memory RAG Server - Complete Tutorial

**Version:** 4.0 (Production-Ready)
**Last Updated:** November 19, 2025
**Platform:** macOS (Apple Silicon) with Qdrant
**Audience:** Developers with command line basics

---

## Table of Contents

1. [Introduction](#introduction)
2. [What You'll Learn](#what-youll-learn)
3. [Prerequisites](#prerequisites)
4. [Installation](#installation)
5. [Initial Setup](#initial-setup)
6. [Your First Index](#your-first-index)
7. [Semantic Code Search](#semantic-code-search)
8. [Memory Management](#memory-management)
9. [Documentation Search](#documentation-search)
10. [Advanced Features](#advanced-features)
11. [Claude Code Integration](#claude-code-integration)
12. [Common Workflows](#common-workflows)
13. [Troubleshooting](#troubleshooting)

---

## Introduction

The Claude Memory RAG Server is a semantic memory and code understanding layer for Claude. It gives Claude the ability to:

- **Remember** your preferences, workflows, and project context across sessions
- **Search** your codebase semantically (by meaning, not just keywords)
- **Understand** your documentation and technical docs
- **Track** how your code evolves through git history
- **Connect** knowledge across multiple projects

Think of it as giving Claude a long-term memory and the ability to truly understand your codebase.

### How It Works

```
┌─────────────────────────────────────────────────────────┐
│  You talking to Claude                                   │
│  "Find the authentication logic"                         │
│  "Remember I prefer async/await"                         │
└────────────────┬────────────────────────────────────────┘
                 │ MCP Protocol
┌────────────────▼────────────────────────────────────────┐
│  Memory RAG Server                                       │
│  • Semantic search (7-13ms)                              │
│  • Vector embeddings                                     │
│  • Memory classification                                 │
└────────────────┬────────────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────────────┐
│  Qdrant Vector Database                                  │
│  • Stores code embeddings                                │
│  • Stores memories                                       │
│  • Stores documentation                                  │
└─────────────────────────────────────────────────────────┘
```

---

## What You'll Learn

By the end of this tutorial, you'll be able to:

✅ Install and configure the server on macOS with Apple Silicon
✅ Index your first codebase for semantic search
✅ Search code using natural language
✅ Store and retrieve memories with Claude
✅ Ingest and search documentation
✅ Use advanced features (git history, multi-project, hybrid search)
✅ Integrate with Claude Code via MCP
✅ Troubleshoot common issues

**Time to complete:** 30-45 minutes

---

## Prerequisites

### Required Software

Before we begin, you'll need:

1. **macOS** (this tutorial uses Apple Silicon, but Intel Macs work too)
2. **Python 3.13+**
3. **Homebrew** (package manager)
4. **Git** (for cloning the repository)

### Optional but Recommended

5. **Rust 1.91+** (for 50-100x faster code parsing)
6. **Docker Desktop** (for Qdrant vector database)

### System Requirements

- **Disk Space:** 1GB minimum (10GB recommended for large codebases)
- **RAM:** 2GB minimum (4GB recommended)
- **Internet:** For downloading dependencies

---

## Installation

Let's install everything step by step.

### Step 1: Install Homebrew (if not already installed)

```bash
# Check if Homebrew is installed
brew --version

# If not installed, install it
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

### Step 2: Install Python 3.13

```bash
# Install Python 3.13
brew install python@3.13

# Verify installation
python3.13 --version
# Expected output: Python 3.13.x
```

### Step 3: Install Rust (Optional but Recommended)

Rust provides 50-100x faster code parsing. Highly recommended!

```bash
# Install Rust
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh

# Follow prompts, then activate Rust
source $HOME/.cargo/env

# Verify installation
rustc --version
# Expected output: rustc 1.91.x or higher
```

### Step 4: Install Docker Desktop (Recommended)

Qdrant provides better performance and scalability than SQLite.

1. Download Docker Desktop for Mac (Apple Silicon): https://www.docker.com/products/docker-desktop/
2. Install and launch Docker Desktop
3. Verify Docker is running:

```bash
docker --version
# Expected output: Docker version 24.x.x or higher

docker ps
# Should show an empty list (no errors)
```

### Step 5: Clone the Repository

```bash
# Navigate to where you want to install
cd ~/Documents/GitHub  # or your preferred location

# Clone the repository
git clone https://github.com/yourorg/claude-memory-server.git
cd claude-memory-server
```

---

## Initial Setup

Now let's configure everything using the interactive setup wizard.

### Step 1: Run the Setup Wizard

```bash
# Run the interactive setup
python3.13 setup.py
```

The wizard will guide you through:

1. **Checking prerequisites** ✓
2. **Installing Python dependencies** ✓
3. **Choosing storage backend** (select Qdrant)
4. **Building Rust module** (if Rust is installed)
5. **Starting Qdrant** (via Docker)
6. **Verifying installation** ✓

**Expected output:**
```
=== Claude Memory RAG Server Setup ===

✓ Python 3.13.6 detected
✓ Rust 1.91.0 detected
✓ Docker detected

Choose installation mode:
1. minimal   - SQLite + Python parser (no dependencies, ~3 min)
2. standard  - SQLite + Rust parser (faster, ~5 min)
3. full      - Qdrant + Rust parser (production, ~10 min)

Selection [3]: 3

Installing dependencies...
✓ Python packages installed

Building Rust module...
✓ Rust parsing module built successfully

Starting Qdrant...
✓ Qdrant running at http://localhost:6333

Running verification...
✓ Storage backend: Connected
✓ Parser: Rust (fast mode)
✓ Embedding model: Loaded
✓ System resources: OK

Setup complete! 🚀
```

### Step 2: Verify Installation

```bash
# Check system health
python -m src.cli health
```

**Expected output:**
```
=== System Health Check ===

✓ Storage Backend: Qdrant (http://localhost:6333)
  Status: Connected
  Collections: 1 (memory)

✓ Parser: Rust (mcp_performance_core)
  Performance: 1-6ms per file

✓ Embedding Model: all-MiniLM-L6-v2
  Status: Loaded
  Dimension: 384

✓ Resources:
  Disk Space: 125 GB available
  Memory: 8 GB available

Overall Health: ✓ HEALTHY
```

### Step 3: Start Qdrant (if not already running)

```bash
# Start Qdrant in the background
docker-compose up -d

# Verify Qdrant is running
curl http://localhost:6333/health
# Expected output: OK
```

### Step 4: Create Configuration File (Optional)

The server works with defaults, but you can customize settings:

```bash
# Create .env file
cat > .env << 'EOF'
# Storage
CLAUDE_RAG_STORAGE_BACKEND=qdrant
CLAUDE_RAG_QDRANT_URL=http://localhost:6333
CLAUDE_RAG_COLLECTION_NAME=memory

# Performance
CLAUDE_RAG_ENABLE_PARALLEL_EMBEDDINGS=true
CLAUDE_RAG_EMBEDDING_PARALLEL_WORKERS=auto

# Features
CLAUDE_RAG_ENABLE_FILE_WATCHER=true
CLAUDE_RAG_ENABLE_HYBRID_SEARCH=true
CLAUDE_RAG_HYBRID_SEARCH_ALPHA=0.5

# Logging
CLAUDE_RAG_LOG_LEVEL=INFO
EOF

echo "✓ Configuration created"
```

**Configuration Explained:**
- `STORAGE_BACKEND=qdrant` - Use Qdrant instead of SQLite
- `ENABLE_PARALLEL_EMBEDDINGS=true` - 4-8x faster indexing
- `ENABLE_HYBRID_SEARCH=true` - Combine semantic + keyword search
- `HYBRID_SEARCH_ALPHA=0.5` - Balance between semantic (1.0) and keyword (0.0)

---

## Your First Index

Let's index a real codebase to enable semantic code search.

### Step 1: Choose a Project to Index

For this tutorial, we'll index the Claude Memory Server itself. You can also use any Python, JavaScript, TypeScript, Java, Go, or Rust project you have.

```bash
# Make sure you're in the repository directory
cd ~/Documents/GitHub/claude-memory-server

# Check what we're about to index
ls src/
# You should see: cli/ core/ embeddings/ memory/ store/ config.py mcp_server.py
```

### Step 2: Run the Index Command

```bash
# Index the src directory
python -m src.cli index ./src --project-name claude-memory
```

**What's happening:**
1. The indexer recursively scans `./src`
2. For each code file, it parses functions, classes, and methods using tree-sitter
3. Each semantic unit gets embedded into a 384-dimensional vector
4. Vectors are stored in Qdrant with metadata (file path, line numbers, etc.)

**Expected output:**
```
=== Indexing Directory: ./src ===

Project: claude-memory
Parser: Rust (fast mode)
Parallel Embeddings: Enabled (8 workers)

Scanning files... 29 files found

[1/29] Indexing: core/server.py
  ✓ Parsed in 5.2ms
  ✓ Found 15 functions, 3 classes
  ✓ Embedded 18 units

[2/29] Indexing: store/qdrant_store.py
  ✓ Parsed in 4.8ms
  ✓ Found 12 functions, 2 classes
  ✓ Embedded 14 units

...

[29/29] Indexing: config.py
  ✓ Parsed in 2.1ms
  ✓ Found 5 functions
  ✓ Embedded 5 units

=== Indexing Complete ===

Files processed: 29
Semantic units: 175
Total time: 11.8 seconds
Throughput: 2.45 files/sec
Cache hits: 0 (first run)

✓ Project 'claude-memory' indexed successfully
```

### Step 3: Verify the Index

```bash
# Check what's indexed
python -m src.cli status
```

**Expected output:**
```
=== Claude Memory RAG Server Status ===

Storage Backend: Qdrant
  URL: http://localhost:6333
  Status: ✓ Connected

Indexed Projects:
  📦 claude-memory
     Files: 29
     Semantic Units: 175
     Functions: 142
     Classes: 33
     Last Indexed: 2025-11-19 14:23:45

Embedding Cache:
  Total Entries: 175
  Cache Size: 1.2 MB
  Hit Rate: 0% (first run)

File Watcher: Enabled
  Active Watchers: 0
```

Excellent! You now have a fully indexed, searchable codebase.

---

## Semantic Code Search

Now for the fun part - searching your code using natural language!

### Understanding Semantic Search

**Traditional grep:**
```bash
grep -r "authenticate" .
# Finds only files containing the exact word "authenticate"
```

**Semantic search:**
```bash
python -m src.cli search "user login logic"
# Finds: authenticate(), verify_credentials(), login_user(), check_password()
# Based on MEANING, not exact keywords
```

### Basic Code Search

Let's search for different types of code:

#### Example 1: Find Authentication Logic

```bash
# Start the MCP server (in another terminal, or we'll use Python directly)
# For now, let's use Python directly

python3 << 'PYTHON'
import asyncio
from src.core.server import MemoryRAGServer

async def search():
    server = MemoryRAGServer()
    await server.initialize()

    results = await server.search_code(
        query="authentication logic",
        project_name="claude-memory",
        limit=5
    )

    print("\n=== Search Results: 'authentication logic' ===\n")
    for i, result in enumerate(results['results'], 1):
        print(f"{i}. {result['file_path']}:{result['start_line']}")
        print(f"   {result['unit_type']}: {result['unit_name']}")
        print(f"   Score: {result['score']:.3f}")
        print(f"   Preview: {result['code_snippet'][:100]}...")
        print()

asyncio.run(search())
PYTHON
```

**Expected output:**
```
=== Search Results: 'authentication logic' ===

1. src/core/server.py:245
   function: validate_api_key
   Score: 0.887
   Preview: async def validate_api_key(self, key: str) -> bool:
        """Validate API key against stored...

2. src/security/validator.py:67
   function: sanitize_input
   Score: 0.823
   Preview: def sanitize_input(content: str) -> str:
        """Sanitize user input to prevent...

3. src/core/server.py:189
   function: initialize
   Score: 0.791
   Preview: async def initialize(self):
        """Initialize the server and all...
```

#### Example 2: Find Error Handling

```python
# Search for error handling code
python3 << 'PYTHON'
import asyncio
from src.core.server import MemoryRAGServer

async def search():
    server = MemoryRAGServer()
    await server.initialize()

    results = await server.search_code(
        query="error handling and exception management",
        project_name="claude-memory"
    )

    for r in results['results'][:3]:
        print(f"• {r['file_path']}:{r['start_line']} - {r['unit_name']} (score: {r['score']:.2f})")

asyncio.run(search())
PYTHON
```

#### Example 3: Find Database Operations

```python
python3 << 'PYTHON'
import asyncio
from src.core.server import MemoryRAGServer

async def search():
    server = MemoryRAGServer()
    await server.initialize()

    # Use hybrid search for better precision
    results = await server.search_code(
        query="database connection and queries",
        project_name="claude-memory",
        search_mode="hybrid"  # Combines semantic + keyword
    )

    print("\n=== Hybrid Search: Database Operations ===\n")
    for r in results['results'][:5]:
        print(f"✓ {r['unit_name']} in {r['file_path'].split('/')[-1]}")
        print(f"  Line {r['start_line']}-{r['end_line']} | Score: {r['score']:.3f}")

asyncio.run(search())
PYTHON
```

### Search Modes Explained

The server supports three search modes:

1. **Semantic (default)** - Best for concepts and meaning
   ```python
   search_mode="semantic"
   # Example: "user authentication" finds login(), verify_user(), check_credentials()
   ```

2. **Keyword** - Best for exact terms (like grep, but smarter)
   ```python
   search_mode="keyword"
   # Example: "def authenticate" finds exact function names
   ```

3. **Hybrid** - Best of both worlds
   ```python
   search_mode="hybrid"
   # Example: "JWT token validation" finds both exact "JWT" and related concepts
   ```

### Filtering Search Results

You can narrow results by language, file pattern, or other criteria:

```python
# Search only Python files
results = await server.search_code(
    query="configuration loading",
    language="python"
)

# Search in specific directory
results = await server.search_code(
    query="API endpoints",
    file_pattern="*/api/*"
)

# Combine filters
results = await server.search_code(
    query="database models",
    language="python",
    file_pattern="*/models/*",
    limit=10
)
```

---

## Memory Management

Now let's explore how Claude can remember your preferences, facts, and project context.

### Understanding Memory Categories

The server classifies memories into 5 categories:

| Category | Description | Example |
|----------|-------------|---------|
| **preference** | Your coding preferences and style | "I prefer async/await over callbacks" |
| **fact** | Factual information | "The API key is stored in AWS Secrets Manager" |
| **event** | Things that happened | "Deployed v2.0 to production on Nov 15" |
| **workflow** | Processes and procedures | "Always run tests before committing" |
| **context** | General project knowledge | "This project uses FastAPI and PostgreSQL" |

### Storing Your First Memory

Let's store some preferences:

```python
python3 << 'PYTHON'
import asyncio
from src.core.server import MemoryRAGServer

async def store_preferences():
    server = MemoryRAGServer()
    await server.initialize()

    # Store a coding preference
    result = await server.store_memory(
        content="I prefer Python type hints for all function parameters and return values",
        category="preference",
        importance=0.8,
        tags=["python", "typing", "code-style"]
    )

    print(f"✓ Stored memory: {result['memory_id']}")
    print(f"  Context level: {result['context_level']}")

    # Store a project fact
    result = await server.store_memory(
        content="The Claude Memory Server uses Qdrant for vector storage and tree-sitter for parsing",
        category="fact",
        scope="project",
        project_name="claude-memory",
        importance=0.7,
        tags=["architecture", "technology-stack"]
    )

    print(f"✓ Stored memory: {result['memory_id']}")

    # Store a workflow preference
    result = await server.store_memory(
        content="Always run pytest with coverage before committing code changes",
        category="workflow",
        importance=0.9,
        tags=["testing", "git", "workflow"]
    )

    print(f"✓ Stored memory: {result['memory_id']}")

asyncio.run(store_preferences())
PYTHON
```

**Expected output:**
```
✓ Stored memory: 550e8400-e29b-41d4-a716-446655440000
  Context level: USER_PREFERENCE

✓ Stored memory: 660f9511-f2ac-52e5-b827-556766550111

✓ Stored memory: 770g0622-g3bd-63f6-c938-667877661222
```

### Retrieving Memories

Now let's retrieve what we stored:

```python
python3 << 'PYTHON'
import asyncio
from src.core.server import MemoryRAGServer

async def retrieve():
    server = MemoryRAGServer()
    await server.initialize()

    # Retrieve Python preferences
    results = await server.retrieve_memories(
        query="Python coding style",
        context_level="USER_PREFERENCE",
        limit=5
    )

    print("\n=== Your Python Preferences ===\n")
    for mem in results['results']:
        print(f"• {mem['content']}")
        print(f"  Importance: {mem['importance']} | Score: {mem['score']:.3f}")
        print()

asyncio.run(retrieve())
PYTHON
```

**Expected output:**
```
=== Your Python Preferences ===

• I prefer Python type hints for all function parameters and return values
  Importance: 0.8 | Score: 0.923

• Always run pytest with coverage before committing code changes
  Importance: 0.9 | Score: 0.856
```

### Specialized Retrieval

The server has specialized tools for specific memory types:

```python
# Get only preferences
from src.memory.specialized_retrieval import SpecializedRetrievalTools

tools = SpecializedRetrievalTools(server)

# Retrieve preferences
prefs = await tools.retrieve_preferences(
    query="coding style",
    limit=10
)

# Retrieve project context
context = await tools.retrieve_project_context(
    query="architecture decisions",
    project_name="claude-memory"
)

# Retrieve session state (what you're currently working on)
state = await tools.retrieve_session_state(
    query="current progress"
)
```

### Memory Lifecycle

Memories automatically age and get weighted differently over time:

- **ACTIVE** (0-7 days): 1.0x weight in search
- **RECENT** (7-30 days): 0.7x weight
- **ARCHIVED** (30-180 days): 0.3x weight
- **STALE** (180+ days): 0.1x weight

You can manage this lifecycle:

```bash
# View lifecycle health
python -m src.cli lifecycle health

# Update lifecycle states (run periodically)
python -m src.cli lifecycle update

# Clean up stale memories
python -m src.cli prune --dry-run
python -m src.cli prune --execute
```

---

## Documentation Search

Let's ingest and search documentation files.

### Ingesting Documentation

```python
python3 << 'PYTHON'
import asyncio
from src.core.server import MemoryRAGServer

async def ingest():
    server = MemoryRAGServer()
    await server.initialize()

    # Ingest all markdown files in docs/
    result = await server.ingest_docs(
        directory_path="./docs",
        project_name="claude-memory"
    )

    print("\n=== Documentation Ingestion ===\n")
    print(f"✓ Files processed: {result['files_processed']}")
    print(f"✓ Chunks created: {result['total_chunks']}")
    print(f"✓ Time: {result['elapsed_time']:.2f}s")
    print("\nIngested files:")
    for file in result['files']:
        print(f"  • {file['file']}: {file['chunks']} chunks")

asyncio.run(ingest())
PYTHON
```

**Expected output:**
```
=== Documentation Ingestion ===

✓ Files processed: 10
✓ Chunks created: 87
✓ Time: 3.45s

Ingested files:
  • SETUP.md: 12 chunks
  • USAGE.md: 18 chunks
  • API.md: 15 chunks
  • ARCHITECTURE.md: 14 chunks
  • SECURITY.md: 9 chunks
  • PERFORMANCE.md: 8 chunks
  • TROUBLESHOOTING.md: 11 chunks
```

### Searching Documentation

```python
python3 << 'PYTHON'
import asyncio
from src.core.server import MemoryRAGServer

async def search_docs():
    server = MemoryRAGServer()
    await server.initialize()

    # Search documentation
    results = await server.retrieve_memories(
        query="How do I configure hybrid search?",
        scope="project",
        project_name="claude-memory",
        limit=3
    )

    print("\n=== Documentation Search Results ===\n")
    for doc in results['results']:
        if 'file_path' in doc.get('metadata', {}):
            print(f"📄 {doc['metadata']['file_path']}")
            print(f"   {doc['content'][:200]}...")
            print(f"   Score: {doc['score']:.3f}\n")

asyncio.run(search_docs())
PYTHON
```

---

## Advanced Features

### 1. File Watching (Auto-Reindexing)

Keep your index up-to-date automatically:

```bash
# Start watching a directory
python -m src.cli watch ./src --project-name claude-memory
```

**What happens:**
- File system events trigger automatic reindexing
- Only changed files are processed (incremental)
- 98% cache hit rate makes it 5-10x faster
- Smart batching prevents too many updates

**Example output:**
```
=== File Watcher Started ===

Project: claude-memory
Directory: ./src
Debounce: 1000ms

Watching 29 files...

[15:23:45] File changed: src/core/server.py
           Re-indexing...
           ✓ Updated 3 semantic units (cache hit: 97%)

[15:24:12] File changed: src/store/qdrant_store.py
           Re-indexing...
           ✓ Updated 2 semantic units (cache hit: 98%)
```

### 2. Git History Search

Search through commit history semantically:

```bash
# Index git history first
python -m src.cli git-index . --project-name claude-memory --commit-count 100
```

Then search commits:

```python
python3 << 'PYTHON'
import asyncio
from src.core.server import MemoryRAGServer

async def search_git():
    server = MemoryRAGServer()
    await server.initialize()

    # Search git history (requires git integration feature)
    # This is a newer feature, check if available
    try:
        results = await server.search_git_history(
            query="performance optimization",
            project_name="claude-memory",
            since="2025-01-01"
        )

        for commit in results['commits'][:5]:
            print(f"✓ {commit['hash'][:7]}: {commit['message']}")
            print(f"  Author: {commit['author']} | Date: {commit['date']}")
            print()
    except AttributeError:
        print("Git history search not yet implemented in this version")

asyncio.run(search_git())
PYTHON
```

### 3. Multi-Project Search

Work with multiple codebases:

```bash
# Index multiple projects
python -m src.cli index ~/projects/web-app --project-name web-app
python -m src.cli index ~/projects/api-server --project-name api-server
python -m src.cli index ~/projects/mobile-app --project-name mobile-app
```

Enable cross-project search:

```python
python3 << 'PYTHON'
import asyncio
from src.core.server import MemoryRAGServer

async def multi_project():
    server = MemoryRAGServer()
    await server.initialize()

    # Opt-in projects for cross-project search
    await server.opt_in_cross_project("web-app")
    await server.opt_in_cross_project("api-server")
    await server.opt_in_cross_project("mobile-app")

    # Search across all opted-in projects
    results = await server.search_all_projects(
        query="authentication implementation",
        limit=10
    )

    print("\n=== Cross-Project Search ===\n")
    for r in results['results']:
        print(f"📦 {r['project_name']}")
        print(f"   {r['file_path']}:{r['start_line']} - {r['unit_name']}")
        print(f"   Score: {r['score']:.3f}\n")

asyncio.run(multi_project())
PYTHON
```

### 4. Hybrid Search Deep Dive

Hybrid search combines semantic understanding with keyword precision:

```python
python3 << 'PYTHON'
import asyncio
from src.core.server import MemoryRAGServer

async def hybrid_demo():
    server = MemoryRAGServer()
    await server.initialize()

    # Query with specific technical terms
    query = "JWT token validation and expiration"

    print(f"\n=== Comparing Search Modes for: '{query}' ===\n")

    # Semantic only
    semantic = await server.search_code(
        query=query,
        search_mode="semantic",
        project_name="claude-memory",
        limit=3
    )

    print("SEMANTIC MODE:")
    for r in semantic['results']:
        print(f"  • {r['unit_name']} (score: {r['score']:.3f})")

    # Hybrid
    hybrid = await server.search_code(
        query=query,
        search_mode="hybrid",
        project_name="claude-memory",
        limit=3
    )

    print("\nHYBRID MODE:")
    for r in hybrid['results']:
        print(f"  • {r['unit_name']} (score: {r['score']:.3f})")
        if 'matched_keywords' in r:
            print(f"    Keywords: {r['matched_keywords']}")

asyncio.run(hybrid_demo())
PYTHON
```

**When to use each mode:**
- **Semantic**: Exploring concepts ("error handling patterns")
- **Keyword**: Finding exact names ("def authenticate_user")
- **Hybrid**: Specific technical queries ("JWT token validation")

### 5. Finding Similar Code

Find code similar to a snippet:

```python
python3 << 'PYTHON'
import asyncio
from src.core.server import MemoryRAGServer

async def find_similar():
    server = MemoryRAGServer()
    await server.initialize()

    snippet = """
    async def authenticate(username: str, password: str) -> User:
        user = await db.get_user(username)
        if not user or not verify_password(password, user.password_hash):
            raise AuthenticationError()
        return user
    """

    results = await server.find_similar_code(
        code_snippet=snippet,
        limit=5
    )

    print("\n=== Similar Code Patterns ===\n")
    for r in results['results']:
        print(f"Similarity: {r['score']:.3f}")
        print(f"  {r['file_path']}:{r['start_line']}")
        print(f"  {r['unit_name']}\n")

asyncio.run(find_similar())
PYTHON
```

---

## Claude Code Integration

Now let's integrate everything with Claude Code using MCP!

### Step 1: Add to Claude Code Config

```bash
# Add the MCP server to Claude Code
claude mcp add --transport stdio --scope user claude-memory-rag -- \
  python "$(pwd)/src/mcp_server.py"
```

**What this does:**
- Registers the Memory RAG Server as an MCP server
- Makes all tools available to Claude
- Uses stdio transport (Claude talks to the server via stdin/stdout)

### Step 2: Verify MCP Connection

```bash
# List MCP servers
claude mcp list

# Should show:
# ✓ claude-memory-rag (stdio)
```

### Step 3: Start Claude Code

```bash
# Start Claude Code (or restart if already running)
claude
```

### Real Claude Code Conversations

Now you can have conversations like this:

#### Example 1: Code Search with Claude

**You:**
> Hey Claude, can you find the error handling code in my codebase?

**Claude:**
> Let me search for error handling logic in your codebase.
>
> *[Claude uses `search_code` tool with query="error handling logic"]*
>
> I found several error handling implementations:
>
> 1. **src/core/exceptions.py:15-45** - Custom exception classes
>    - `MemoryRAGError`, `ValidationError`, `StorageError`
>    - Includes actionable error messages with solutions
>
> 2. **src/core/server.py:189-215** - Server initialization error handling
>    - Handles storage connection failures
>    - Provides fallback to SQLite if Qdrant unavailable
>
> 3. **src/store/qdrant_store.py:78-95** - Database operation error handling
>    - Retry logic for transient failures
>    - Graceful degradation for network issues
>
> Would you like me to explain any of these implementations in detail?

#### Example 2: Memory Storage

**You:**
> Remember that I prefer to use dataclasses over Pydantic models for simple data structures

**Claude:**
> *[Claude uses `store_memory` tool]*
>
> I'll remember that preference. Stored as a USER_PREFERENCE with high importance (0.8).
>
> This preference will be automatically applied when we're discussing or writing Python code involving data structures.

Later in the same session or a new session:

**You:**
> How should I structure this user data?

**Claude:**
> *[Claude uses `retrieve_memories` tool to recall preferences]*
>
> Based on your preferences, I'd recommend using a dataclass for this simple user data structure:
>
> ```python
> from dataclasses import dataclass
> from datetime import datetime
>
> @dataclass
> class User:
>     username: str
>     email: str
>     created_at: datetime
>     is_active: bool = True
> ```
>
> You prefer dataclasses over Pydantic models for simple structures like this. We'd only need Pydantic if you required validation, serialization, or API schema generation.

#### Example 3: Documentation Search

**You:**
> How do I configure the file watcher?

**Claude:**
> *[Claude uses `retrieve_memories` tool with scope="project" to search docs]*
>
> Based on the documentation, here's how to configure the file watcher:
>
> 1. **Enable in environment variables (.env):**
>    ```bash
>    CLAUDE_RAG_ENABLE_FILE_WATCHER=true
>    CLAUDE_RAG_WATCH_DEBOUNCE_MS=1000
>    ```
>
> 2. **Start the watcher via CLI:**
>    ```bash
>    python -m src.cli watch ./src --project-name your-project
>    ```
>
> 3. **How it works:**
>    - Monitors file changes in real-time
>    - Auto-reindexes modified files
>    - Uses smart batching with 1000ms debounce
>    - 98% cache hit rate makes reindexing fast
>
> The watcher will keep running and automatically update your code index when files change.

#### Example 4: Multi-Step Workflow

**You:**
> I'm starting a new FastAPI project. Help me set it up with your memory system.

**Claude:**
> Great! Let me help you set up a new FastAPI project. I'll guide you through the process and remember your project structure.
>
> First, let me create the project directory and index it:
>
> *[Claude might execute commands if it has shell access, or guide you]*
>
> ```bash
> # Create project structure
> mkdir my-fastapi-app
> cd my-fastapi-app
> mkdir src tests docs
>
> # Create main file
> cat > src/main.py << 'EOF'
> from fastapi import FastAPI
>
> app = FastAPI(title="My API", version="1.0.0")
>
> @app.get("/")
> async def root():
>     return {"message": "Hello World"}
> EOF
> ```
>
> Now let me index this project:
>
> *[Claude uses `index_codebase` tool]*
>
> ```bash
> python -m src.cli index ./my-fastapi-app --project-name my-fastapi-app
> ```
>
> *[Claude uses `store_memory` tool]*
>
> I've also stored some facts about this project:
> - Project uses FastAPI framework
> - Python-based API
> - Standard project structure (src/, tests/, docs/)
>
> Would you like me to help you add authentication, database integration, or other features?

### Available MCP Tools for Claude

When talking to Claude, it automatically has access to:

- **search_code** - Semantic code search
- **index_codebase** - Index new projects
- **store_memory** - Remember preferences/facts
- **retrieve_memories** - Recall information
- **ingest_docs** - Process documentation
- **search_all** - Combined search
- **get_status** - System statistics
- And 16 more tools!

Claude decides when to use these based on your conversation.

---

## Common Workflows

### Workflow 1: Onboarding to a New Codebase

```bash
# Step 1: Index the codebase
python -m src.cli index ~/projects/new-project --project-name new-project

# Step 2: Ingest documentation
python3 << 'PYTHON'
import asyncio
from src.core.server import MemoryRAGServer

async def ingest():
    server = MemoryRAGServer()
    await server.initialize()
    await server.ingest_docs(
        directory_path="~/projects/new-project/docs",
        project_name="new-project"
    )

asyncio.run(ingest())
PYTHON

# Step 3: Start file watcher
python -m src.cli watch ~/projects/new-project --project-name new-project &

# Step 4: Chat with Claude
claude
```

Then ask Claude:
> "Give me an overview of this codebase. What's the architecture? Where's the authentication? What frameworks are being used?"

### Workflow 2: Debugging an Issue

```bash
# Step 1: Search for related code
python3 << 'PYTHON'
import asyncio
from src.core.server import MemoryRAGServer

async def debug():
    server = MemoryRAGServer()
    await server.initialize()

    # Find error handling
    results = await server.search_code(
        query="database connection error handling",
        project_name="my-app",
        search_mode="hybrid"
    )

    for r in results['results'][:3]:
        print(f"Check: {r['file_path']}:{r['start_line']}")

asyncio.run(debug())
PYTHON

# Step 2: Ask Claude
# "Look at these files and help me debug why database connections are failing"
```

### Workflow 3: Code Review Prep

```bash
# Step 1: Find similar patterns
python3 << 'PYTHON'
import asyncio
from src.core.server import MemoryRAGServer

async def review():
    server = MemoryRAGServer()
    await server.initialize()

    # Your new code
    new_code = """
    async def process_payment(amount: float, user_id: str):
        # ... implementation
    """

    # Find similar code
    similar = await server.find_similar_code(
        code_snippet=new_code,
        limit=5
    )

    print("Similar patterns in codebase:")
    for s in similar['results']:
        print(f"  {s['file_path']}:{s['start_line']} (similarity: {s['score']:.2f})")

asyncio.run(review())
PYTHON

# Step 2: Ask Claude to review
# "Here's my new payment processing code. Compare it with similar patterns in the codebase and suggest improvements."
```

### Workflow 4: Refactoring

```bash
# Step 1: Find all usage
python3 << 'PYTHON'
import asyncio
from src.core.server import MemoryRAGServer

async def find_usage():
    server = MemoryRAGServer()
    await server.initialize()

    # Find all places using old pattern
    results = await server.search_code(
        query="deprecated authentication method",
        search_mode="hybrid",
        limit=20
    )

    print(f"Found {len(results['results'])} usages to refactor")
    for r in results['results']:
        print(f"  • {r['file_path']}:{r['start_line']}")

asyncio.run(find_usage())
PYTHON

# Step 2: Ask Claude
# "Help me refactor these 15 files to use the new authentication method"
```

---

## Troubleshooting

### Qdrant Won't Start

**Problem:** `docker-compose up -d` fails or Qdrant isn't accessible

**Solutions:**

```bash
# Check if port 6333 is already in use
lsof -i :6333

# If something else is using it, kill that process or change Qdrant port
# In docker-compose.yml, change:
# ports:
#   - "6334:6333"  # Use external port 6334 instead

# Remove old containers and volumes
docker-compose down -v
docker-compose up -d

# Verify it's running
docker ps | grep qdrant
curl http://localhost:6333/health
```

### Rust Module Build Fails

**Problem:** `maturin develop` fails with compilation errors

**Solution:**

```bash
# Make sure Rust is in PATH
source $HOME/.cargo/env

# Update Rust to latest
rustup update

# Install build dependencies (macOS)
xcode-select --install

# Clean and rebuild
cd rust_core
cargo clean
maturin develop --release
cd ..

# Verify
python -c "import mcp_performance_core; print('OK')"
```

**Fallback:** The server works with pure Python parser if Rust isn't available (just slower)

### Python Import Errors

**Problem:** `ModuleNotFoundError` when running commands

**Solutions:**

```bash
# Ensure you're using Python 3.13+
python --version

# Reinstall dependencies
pip install --force-reinstall -r requirements.txt

# Check if in correct directory
pwd  # Should be in claude-memory-server/

# Try with explicit python module path
PYTHONPATH=. python -m src.cli health
```

### Embeddings Are Slow

**Problem:** Indexing takes too long

**Solutions:**

```bash
# Enable parallel embeddings in .env
echo "CLAUDE_RAG_ENABLE_PARALLEL_EMBEDDINGS=true" >> .env
echo "CLAUDE_RAG_EMBEDDING_PARALLEL_WORKERS=auto" >> .env

# Verify it's enabled
python -m src.cli status | grep "Parallel"

# Use Rust parser instead of Python
cd rust_core && maturin develop && cd ..
```

### Search Results Are Poor

**Problem:** Semantic search returns irrelevant results

**Solutions:**

1. **Try hybrid mode** for queries with specific technical terms:
   ```python
   search_mode="hybrid"
   ```

2. **Be more specific** in queries:
   - ❌ "auth"
   - ✅ "JWT token authentication and validation"

3. **Filter by language or file pattern**:
   ```python
   await server.search_code(
       query="your query",
       language="python",
       file_pattern="*/api/*"
   )
   ```

4. **Check if project is indexed**:
   ```bash
   python -m src.cli status
   ```

### Memory Usage Is High

**Problem:** Server using too much RAM

**Solutions:**

```bash
# Check memory usage
python -m src.cli health

# Reduce batch size in .env
echo "CLAUDE_RAG_EMBEDDING_BATCH_SIZE=16" >> .env  # Default is 32

# Archive old projects
python -m src.cli archival archive old-project

# Prune stale memories
python -m src.cli prune --execute
```

### File Watcher Not Working

**Problem:** Changes to files aren't triggering reindexing

**Solutions:**

```bash
# Check if file watcher is enabled
python -m src.cli status | grep "File Watcher"

# Enable in .env
echo "CLAUDE_RAG_ENABLE_FILE_WATCHER=true" >> .env

# Check if watcher process is running
ps aux | grep "watch"

# Restart watcher
# Find PID and kill it
kill $(ps aux | grep 'src.cli watch' | awk '{print $2}')

# Start new watcher
python -m src.cli watch ./src --project-name your-project
```

### MCP Connection Issues

**Problem:** Claude can't access the MCP tools

**Solutions:**

```bash
# Verify MCP server is registered
claude mcp list

# Remove and re-add
claude mcp remove claude-memory-rag
claude mcp add --transport stdio --scope user claude-memory-rag -- \
  python "$(pwd)/src/mcp_server.py"

# Test MCP server directly
python -m src.mcp_server

# Check for errors in Claude Code logs
# (location depends on your Claude Code installation)
```

---

## Next Steps

Congratulations! You now have a fully functional Claude Memory RAG Server. 🎉

### What You've Learned

✅ Installing and configuring the server on macOS
✅ Indexing codebases for semantic search
✅ Searching code using natural language
✅ Storing and retrieving memories
✅ Ingesting and searching documentation
✅ Using advanced features (git history, multi-project, hybrid search)
✅ Integrating with Claude Code via MCP
✅ Troubleshooting common issues

### Continue Learning

- **[API.md](docs/API.md)** - Complete API reference for all 23 tools
- **[USAGE.md](docs/USAGE.md)** - Comprehensive usage guide with all 28 CLI commands
- **[ARCHITECTURE.md](docs/ARCHITECTURE.md)** - Understand how it all works under the hood
- **[SECURITY.md](docs/SECURITY.md)** - Security best practices and privacy model
- **[PERFORMANCE.md](docs/PERFORMANCE.md)** - Performance tuning and benchmarks

### Real-World Usage Tips

1. **Start Small**
   - Index one project first
   - Get comfortable with search
   - Then expand to multiple projects

2. **Build Habits**
   - Tell Claude your preferences as you work
   - Let it build up context naturally
   - Review memories periodically

3. **Optimize Over Time**
   - Enable parallel embeddings once comfortable
   - Use hybrid search for technical queries
   - Archive inactive projects to save space

4. **Integrate Into Workflow**
   - Keep file watcher running during development
   - Ask Claude before grepping
   - Use memory for cross-session continuity

### Community & Support

- **Issues:** https://github.com/anthropics/claude-memory-server/issues
- **Discussions:** https://github.com/anthropics/claude-memory-server/discussions
- **Documentation:** https://github.com/anthropics/claude-memory-server/tree/main/docs

---

**Happy coding with your new AI memory! 🚀**

*Tutorial Version: 1.0*
*Last Updated: November 19, 2025*
*Tested on: macOS Sonoma (Apple Silicon) with Python 3.13, Rust 1.91, Docker 24*
