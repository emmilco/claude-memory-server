# Error Handling Guide

**Comprehensive guide to exception handling in the Claude Memory RAG Server.**

---

## Table of Contents

- [Overview](#overview)
- [Exception Hierarchy](#exception-hierarchy)
- [Quick Reference](#quick-reference)
- [Exception Catalog](#exception-catalog)
  - [Base Exception](#base-exception)
  - [Storage Errors](#storage-errors)
  - [Validation & Security Errors](#validation--security-errors)
  - [Processing Errors](#processing-errors)
  - [Dependency Errors](#dependency-errors)
- [Common Error Scenarios](#common-error-scenarios)
- [Best Practices](#best-practices)
- [Error Recovery Patterns](#error-recovery-patterns)

---

## Overview

The Claude Memory RAG Server uses a comprehensive exception system designed to provide **actionable error messages** with specific solutions. Every exception includes:

- **Error Code** (E000-E015) - For tracking and logging
- **Clear Message** - What went wrong
- **Solution** - How to fix it (when available)
- **Documentation Link** - Where to learn more (when available)

### Error Code System

Error codes are organized by category:

- **E000**: Base exception
- **E001-E012**: Storage errors
- **E002-E005**: Validation and security
- **E006-E009**: Processing errors
- **E013-E015**: Dependency errors

### Philosophy

Errors should be:

1. **Actionable** - Tell users exactly how to fix the problem
2. **Informative** - Provide enough context to diagnose issues
3. **Recoverable** - Distinguish transient from permanent failures
4. **Consistent** - Use predictable patterns across the codebase

---

## Exception Hierarchy

```
MemoryRAGError (E000)                    [Base class for all errors]
├── StorageError (E001)                  [Storage backend failures]
│   ├── QdrantConnectionError (E010)     [Qdrant connection issues]
│   ├── CollectionNotFoundError (E011)   [Collection doesn't exist]
│   └── MemoryNotFoundError (E012)       [Memory ID not found]
├── ValidationError (E002)               [Input validation failures]
├── ReadOnlyError (E003)                 [Write in read-only mode]
├── RetrievalError (E004)                [Memory retrieval failures]
├── SecurityError (E005)                 [Security violations]
├── EmbeddingError (E006)                [Embedding generation failures]
├── ParsingError (E007)                  [Code parsing failures]
├── IndexingError (E008)                 [Code indexing failures]
├── ConfigurationError (E009)            [Invalid configuration]
├── DependencyError (E013)               [Missing dependencies]
├── DockerNotRunningError (E014)         [Docker not running]
└── RustBuildError (E015)                [Rust parser build failures]
```

---

## Quick Reference

| Code | Exception | Category | Transient? | Common Cause | First Action |
|------|-----------|----------|------------|--------------|--------------|
| E000 | MemoryRAGError | Base | - | Internal error | Check logs |
| E001 | StorageError | Storage | Maybe | Qdrant issue | Check Qdrant logs |
| E002 | ValidationError | Input | No | Invalid input | Fix input parameters |
| E003 | ReadOnlyError | Config | No | Read-only mode | Disable read-only mode |
| E004 | RetrievalError | Storage | Maybe | Connection lost | Retry operation |
| E005 | SecurityError | Security | No | Violation detected | Check permissions |
| E006 | EmbeddingError | Dependency | No | Missing package | Install sentence-transformers |
| E007 | ParsingError | Input | No | Invalid code | Fix code syntax |
| E008 | IndexingError | Processing | Maybe | Processing failed | Check logs, retry |
| E009 | ConfigurationError | Config | No | Invalid config | Fix configuration |
| E010 | QdrantConnectionError | Setup | No | Qdrant not running | Start Qdrant |
| E011 | CollectionNotFoundError | Usage | No | Not indexed yet | Index project first |
| E012 | MemoryNotFoundError | Usage | No | Invalid ID | Verify memory ID |
| E013 | DependencyError | Setup | No | Package missing | Install package |
| E014 | DockerNotRunningError | Setup | No | Docker stopped | Start Docker |
| E015 | RustBuildError | Setup | No | Rust missing | Install Rust or use Python |

---

## Exception Catalog

### Base Exception

#### E000: MemoryRAGError

**Inherits from:** `Exception`

**When raised:**
- Base class for all custom exceptions
- Rarely raised directly (use specific subclasses)

**Common causes:**
1. Internal errors not covered by specific exceptions
2. Unexpected system states
3. Programming errors

**How to handle:**
```python
from src.core.exceptions import MemoryRAGError

try:
    # Any operation
    await server.some_operation()
except MemoryRAGError as e:
    # Catch all Memory RAG errors
    logger.error(f"Memory RAG error: {e}", exc_info=True)
    print(f"Error: {e}")
```

**Recovery strategy:**
1. Check error message for specific details
2. Review logs with full stack trace
3. File a bug report if unexpected

**Transient?** Depends on specific subclass

---

### Storage Errors

#### E001: StorageError

**Inherits from:** `MemoryRAGError` (E000)

**When raised:**
- Failed to store memories in Qdrant
- Failed to delete memories or code units
- Failed to update memory metadata
- Failed to list memories or indexed files
- Failed to retrieve project statistics
- General storage backend failures

**Common causes:**
1. Qdrant connection issues (network, timeout)
2. Collection doesn't exist
3. Invalid data format
4. Disk full or storage quota exceeded
5. Qdrant internal errors

**How to handle:**
```python
from src.core.exceptions import StorageError

try:
    await store.store_memory(memory)
except StorageError as e:
    logger.error(f"Storage failed: {e}", exc_info=True)
    # Option 1: Retry with backoff
    await retry_with_backoff(store.store_memory, memory, max_attempts=3)
    # Option 2: Fall back to alternative storage
    await fallback_store.store_memory(memory)
```

**Recovery strategy:**
1. Check Qdrant is running: `docker ps`
2. Check Qdrant logs: `docker logs qdrant`
3. Verify network connectivity
4. Check disk space: `df -h`
5. Retry operation

**Transient?** Maybe - network/timeout issues are transient, data errors are not

**Related errors:**
- E010: QdrantConnectionError (connection-specific)
- E011: CollectionNotFoundError (collection missing)
- E012: MemoryNotFoundError (memory not found)

---

#### E010: QdrantConnectionError

**Inherits from:** `StorageError` (E001)

**When raised:**
- Server startup when Qdrant is unreachable
- Any storage operation if connection fails
- Health checks if Qdrant container stopped
- Connection pool initialization

**Common causes:**
1. Qdrant not started (`docker-compose up -d` not run)
2. Wrong URL in config (`CLAUDE_RAG_QDRANT_URL`)
3. Qdrant crashed or container exited
4. Network issues (firewall, Docker network)
5. Port conflict (6333 already in use)

**How to handle:**
```python
from src.core.exceptions import QdrantConnectionError

try:
    server = MemoryRAGServer(config)
    await server.initialize()
except QdrantConnectionError as e:
    print(f"Cannot connect to Qdrant: {e}")
    # Option 1: Exit and ask user to fix
    print("Please start Qdrant: docker-compose up -d")
    sys.exit(1)
    # Option 2: Retry with backoff
    await retry_with_backoff(server.initialize, max_attempts=3, delay=5)
```

**Recovery strategy:**
1. Check if Docker is running: `docker ps`
2. Check if Qdrant container exists: `docker-compose ps`
3. Start Qdrant: `docker-compose up -d`
4. Verify health: `curl http://localhost:6333/health`
5. Wait 5-10 seconds for startup
6. Retry operation

**Transient?** No - requires manual intervention to start Qdrant

**Related errors:**
- E014: DockerNotRunningError (Docker not installed/running)
- E001: StorageError (generic storage failures)

**See also:**
- Setup guide: [docs/SETUP.md](SETUP.md#qdrant-setup)
- Troubleshooting: [docs/TROUBLESHOOTING.md](TROUBLESHOOTING.md#qdrant-connection-issues)

---

#### E011: CollectionNotFoundError

**Inherits from:** `StorageError` (E001)

**When raised:**
- Searching a project that hasn't been indexed
- Retrieving memories from non-existent collection
- Attempting operations on deleted collections

**Common causes:**
1. Project never indexed (first-time use)
2. Collection deleted manually
3. Qdrant data directory cleared
4. Wrong project name in query

**How to handle:**
```python
from src.core.exceptions import CollectionNotFoundError

try:
    results = await store.search(query, project_name="myproject")
except CollectionNotFoundError as e:
    print(f"Project not indexed yet: {e}")
    # Option 1: Index the project first
    await indexer.index_codebase("./myproject", "myproject")
    # Then retry
    results = await store.search(query, project_name="myproject")
```

**Recovery strategy:**
1. Verify project name is correct
2. Index the project: `python -m src.cli index ./path --project-name myproject`
3. Wait for indexing to complete
4. Retry operation

**Transient?** No - collection must be created before use

**Related errors:**
- E008: IndexingError (indexing failures)
- E001: StorageError (generic storage errors)

---

#### E012: MemoryNotFoundError

**Inherits from:** `StorageError` (E001)

**When raised:**
- Retrieving memory with non-existent ID
- Updating or deleting memory that doesn't exist
- Merging memories with invalid IDs

**Common causes:**
1. Memory ID typo or incorrect ID
2. Memory deleted by another operation
3. Searching in wrong collection
4. Memory expired or archived

**How to handle:**
```python
from src.core.exceptions import MemoryNotFoundError

try:
    memory = await store.get_memory_by_id(memory_id)
except MemoryNotFoundError as e:
    logger.warning(f"Memory not found: {e}")
    # Option 1: Return None or default
    memory = None
    # Option 2: Search for similar memories
    memories = await store.search(query, limit=1)
    if memories:
        memory = memories[0]
```

**Recovery strategy:**
1. Verify memory ID is correct
2. List available memories: `python -m src.cli list-memories`
3. Search for the content instead of ID
4. Check if memory was deleted

**Transient?** No - memory doesn't exist

**Related errors:**
- E004: RetrievalError (retrieval failures)
- E001: StorageError (generic storage errors)

---

### Validation & Security Errors

#### E002: ValidationError

**Inherits from:** `MemoryRAGError` (E000)

**When raised:**
- Invalid memory content (empty, too long)
- Invalid search parameters (negative limit, invalid filters)
- Invalid tag format or injection detected
- Invalid batch size or empty batch
- Malformed JSON in import

**Common causes:**
1. Content length violations (must be 1-50,000 characters)
2. Importance out of range (must be 0.0-1.0)
3. Invalid tag format (max 50 chars, no special chars)
4. Security injection patterns detected
5. Invalid parameter types or ranges

**How to handle:**
```python
from src.core.exceptions import ValidationError

try:
    await server.store_memory(content="", tags=["valid"])
except ValidationError as e:
    print(f"Invalid input: {e}")
    # Fix the input and retry
    content = "Valid content here"
    await server.store_memory(content=content, tags=["valid"])
```

**Recovery strategy:**
1. Read the error message for specific constraint
2. Fix the input to meet requirements
3. Retry with corrected input

**Transient?** No - input must be corrected

**Validation rules:**
- Content: 1-50,000 characters
- Importance: 0.0-1.0
- Tags: Strings ≤50 chars, no injection patterns
- Memory ID: Non-empty, sanitized
- Batch size: 1-1,000 items

**Related errors:**
- E005: SecurityError (security violations)

---

#### E003: ReadOnlyError

**Inherits from:** `MemoryRAGError` (E000)

**When raised:**
- Attempting to store memory in read-only mode
- Attempting to delete memory in read-only mode
- Attempting to update memory in read-only mode
- Attempting to index code in read-only mode

**Common causes:**
1. Server configured with `read_only_mode=True`
2. Using read-only wrapper around store
3. Production safety mode enabled

**How to handle:**
```python
from src.core.exceptions import ReadOnlyError

try:
    await server.store_memory(content="test")
except ReadOnlyError as e:
    print(f"Read-only mode active: {e}")
    # Option 1: Inform user
    print("Server is in read-only mode. Write operations disabled.")
    # Option 2: Check if read-only is expected
    if not config.read_only_mode:
        logger.error("Unexpected read-only mode!")
```

**Recovery strategy:**
1. Check if read-only mode is intentional
2. Disable read-only mode in configuration
3. Restart server with write permissions
4. Use separate write-enabled instance

**Transient?** No - requires configuration change

**Configuration:**
```python
# Disable read-only mode
config = Config(read_only_mode=False)
server = MemoryRAGServer(config)
```

---

#### E004: RetrievalError

**Inherits from:** `MemoryRAGError` (E000)

**When raised:**
- Failed to retrieve memories from Qdrant
- Failed to search across projects
- Failed to find similar code
- Failed to get file dependencies
- Connection lost during search

**Common causes:**
1. Qdrant connection lost mid-query
2. Invalid search parameters
3. Collection deleted during query
4. Network timeout
5. Qdrant internal error

**How to handle:**
```python
from src.core.exceptions import RetrievalError

try:
    results = await store.search(query)
except RetrievalError as e:
    logger.error(f"Search failed: {e}", exc_info=True)
    # Option 1: Retry with backoff
    results = await retry_with_backoff(store.search, query, max_attempts=3)
    # Option 2: Return empty results
    results = []
```

**Recovery strategy:**
1. Check Qdrant connection
2. Verify search parameters are valid
3. Retry with exponential backoff
4. Fall back to cached results if available

**Transient?** Maybe - connection issues are transient, parameter errors are not

**Related errors:**
- E010: QdrantConnectionError (connection lost)
- E002: ValidationError (invalid parameters)

---

#### E005: SecurityError

**Inherits from:** `MemoryRAGError` (E000)

**When raised:**
- Security violations detected in input
- Injection patterns found in tags or filters
- Unauthorized access attempts

**Common causes:**
1. SQL injection patterns in input
2. NoSQL injection patterns in filters
3. Path traversal attempts
4. XSS patterns in tags

**How to handle:**
```python
from src.core.exceptions import SecurityError

try:
    await server.store_memory(content="test", tags=["'; DROP TABLE--"])
except SecurityError as e:
    logger.warning(f"Security violation: {e}", exc_info=True)
    # Sanitize input and retry
    safe_tags = sanitize_tags(tags)
    await server.store_memory(content="test", tags=safe_tags)
```

**Recovery strategy:**
1. Review the input for malicious patterns
2. Sanitize or reject the input
3. Log the attempt for security monitoring
4. Consider blocking the source

**Transient?** No - input must be sanitized

**Security patterns detected:**
- SQL injection: `'; DROP TABLE`, `1=1--`, etc.
- NoSQL injection: `$where`, `{$ne: null}`, etc.
- Path traversal: `../`, `..\\`, etc.
- XSS: `<script>`, `javascript:`, etc.

---

### Processing Errors

#### E006: EmbeddingError

**Inherits from:** `MemoryRAGError` (E000)

**When raised:**
- Failed to generate embeddings for text
- Missing sentence-transformers package
- Empty text passed to embedding generator
- Model loading failed
- Insufficient memory for model

**Common causes:**
1. `sentence-transformers` not installed
2. Invalid model name
3. Insufficient memory (model needs ~100MB)
4. Empty or too-long text (max ~8,000 tokens)
5. GPU/CPU compatibility issues

**How to handle:**
```python
from src.core.exceptions import EmbeddingError

try:
    embedding = await generator.generate(text)
except EmbeddingError as e:
    logger.error(f"Embedding failed: {e}", exc_info=True)
    # Option 1: Check dependencies
    import subprocess
    subprocess.run(["pip", "install", "sentence-transformers"])
    # Option 2: Fall back to keyword search
    results = await keyword_search(text)
```

**Recovery strategy:**
1. Install sentence-transformers: `pip install sentence-transformers`
2. Verify model is valid (all-MiniLM-L6-v2, all-mpnet-base-v2)
3. Check text is not empty
4. Check sufficient memory available
5. Retry operation

**Transient?** No - requires dependency installation or text fix

**Supported models:**
- `all-MiniLM-L6-v2` (default, 384 dimensions)
- `all-mpnet-base-v2` (768 dimensions)

**Related errors:**
- E013: DependencyError (missing package)

---

#### E007: ParsingError

**Inherits from:** `MemoryRAGError` (E000)

**When raised:**
- Failed to parse code file
- Invalid syntax in code
- Unsupported file format
- File encoding issues

**Common causes:**
1. Syntax errors in code file
2. Unsupported programming language
3. Corrupted file
4. Wrong file encoding (expected UTF-8)
5. Binary file mistaken for code

**How to handle:**
```python
from src.core.exceptions import ParsingError

try:
    units = await parser.parse_file(file_path)
except ParsingError as e:
    logger.warning(f"Parse failed for {file_path}: {e}")
    # Option 1: Skip the file
    print(f"Skipping unparseable file: {file_path}")
    # Option 2: Try alternative parser
    units = await fallback_parser.parse_file(file_path)
```

**Recovery strategy:**
1. Check file has valid syntax
2. Verify file type is supported
3. Check file encoding (should be UTF-8)
4. Verify Rust parser is installed (mcp_performance_core)
5. Skip file if parsing not critical

**Transient?** No - file must be fixed or skipped

**Supported languages:**
- Python, JavaScript, TypeScript, Java, C, C++, Rust, Go, Ruby, PHP, Swift, Kotlin, C#, Shell

**Related errors:**
- E008: IndexingError (indexing failures after parsing)

---

#### E008: IndexingError

**Inherits from:** `MemoryRAGError` (E000)

**When raised:**
- Failed to index codebase
- Failed to process parsed code units
- Embedding generation failed during indexing
- Storage failed during bulk insert

**Common causes:**
1. Parsing errors in multiple files
2. Embedding generation failures
3. Storage connection lost during indexing
4. Insufficient disk space
5. Process killed/interrupted

**How to handle:**
```python
from src.core.exceptions import IndexingError

try:
    await indexer.index_codebase(project_path, project_name)
except IndexingError as e:
    logger.error(f"Indexing failed: {e}", exc_info=True)
    # Option 1: Retry with smaller batch
    await indexer.index_codebase(project_path, project_name, batch_size=50)
    # Option 2: Clean up partial index and retry
    await store.delete_project(project_name)
    await indexer.index_codebase(project_path, project_name)
```

**Recovery strategy:**
1. Check logs for specific error
2. Verify Qdrant is running and healthy
3. Check disk space is sufficient
4. Retry with smaller batch size
5. Clean up partial index if needed

**Transient?** Maybe - connection issues are transient, file errors are not

**Related errors:**
- E007: ParsingError (parsing failures)
- E006: EmbeddingError (embedding failures)
- E001: StorageError (storage failures)

---

#### E009: ConfigurationError

**Inherits from:** `MemoryRAGError` (E000)

**When raised:**
- Invalid configuration values
- Missing required configuration
- Configuration conflicts
- Environment variables malformed

**Common causes:**
1. Invalid Qdrant URL format
2. Invalid embedding dimensions
3. Invalid file size limits
4. Conflicting feature flags
5. Missing environment variables

**How to handle:**
```python
from src.core.exceptions import ConfigurationError

try:
    config = Config.from_env()
except ConfigurationError as e:
    print(f"Invalid configuration: {e}")
    # Option 1: Use defaults
    config = Config()
    # Option 2: Provide explicit values
    config = Config(
        qdrant_url="http://localhost:6333",
        embedding_dimension=384
    )
```

**Recovery strategy:**
1. Review error message for specific issue
2. Check configuration file or environment variables
3. Verify values match documented ranges
4. Use default configuration as baseline
5. Validate configuration with `python scripts/setup.py`

**Transient?** No - configuration must be corrected

**Common configuration issues:**
- Qdrant URL must start with `http://` or `https://`
- Embedding dimension must be 384 or 768
- Max file size must be positive integer
- Feature flags must not conflict (e.g., GPU + CPU)

---

### Dependency Errors

#### E013: DependencyError

**Inherits from:** `MemoryRAGError` (E000)

**When raised:**
- Required Python package not installed
- Package version incompatible
- System library missing

**Common causes:**
1. `sentence-transformers` not installed
2. `qdrant-client` not installed
3. Optional dependencies missing (e.g., `PyMuPDF`)
4. Virtual environment not activated

**How to handle:**
```python
from src.core.exceptions import DependencyError

try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    raise DependencyError("sentence-transformers", "Required for embeddings")

# Alternative: graceful degradation
try:
    from sentence_transformers import SentenceTransformer
    use_embeddings = True
except ImportError:
    logger.warning("sentence-transformers not available, using keyword search only")
    use_embeddings = False
```

**Recovery strategy:**
1. Install missing package: `pip install <package>`
2. Install all dependencies: `pip install -r requirements.txt`
3. Check virtual environment is activated
4. Verify Python version is 3.13+

**Transient?** No - package must be installed

**OS-specific install commands:**
- **macOS/Linux**: `pip install sentence-transformers`
- **Ubuntu/Debian**: `sudo apt-get install python3-sentence-transformers` (if available)
- **Windows**: `pip install sentence-transformers`

**Related errors:**
- E006: EmbeddingError (embedding generation failures)

**See also:**
- Troubleshooting: [docs/TROUBLESHOOTING.md](TROUBLESHOOTING.md#dependency-issues)

---

#### E014: DockerNotRunningError

**Inherits from:** `MemoryRAGError` (E000)

**When raised:**
- Docker daemon not running
- Cannot connect to Docker socket
- Docker not installed

**Common causes:**
1. Docker Desktop not started
2. Docker service not running (Linux)
3. Docker not installed
4. Insufficient permissions to access Docker

**How to handle:**
```python
from src.core.exceptions import DockerNotRunningError

try:
    # Check if Docker is available
    import subprocess
    subprocess.run(["docker", "ps"], check=True, capture_output=True)
except FileNotFoundError:
    raise DockerNotRunningError()

# Handle the error
try:
    setup_qdrant()
except DockerNotRunningError as e:
    print(f"Docker required: {e}")
    print("Please start Docker and try again")
    sys.exit(1)
```

**Recovery strategy:**

**macOS:**
1. Open Docker Desktop application
2. Wait for Docker to start (icon in menu bar)
3. Verify: `docker ps`

**Linux:**
1. Start Docker service: `sudo systemctl start docker`
2. Enable on boot: `sudo systemctl enable docker`
3. Verify: `docker ps`

**Windows:**
1. Start Docker Desktop
2. Wait for Docker to be ready
3. Verify: `docker ps`

**Transient?** No - requires manual Docker startup

**Related errors:**
- E010: QdrantConnectionError (Qdrant not started)

**See also:**
- Setup: [docs/SETUP.md](SETUP.md#docker-setup)

---

#### E015: RustBuildError

**Inherits from:** `MemoryRAGError` (E000)

**When raised:**
- Failed to compile Rust parser
- Rust toolchain not installed
- Maturin build failed
- Compiler errors in Rust code

**Common causes:**
1. Rust not installed
2. Wrong Rust version (needs stable)
3. Missing system build tools (gcc, etc.)
4. Cargo build cache corrupted

**How to handle:**
```python
from src.core.exceptions import RustBuildError

try:
    from rust_core import parse_code
    use_rust = True
except ImportError as e:
    raise RustBuildError(str(e))

# Rust parser is required for code indexing
try:
    from mcp_performance_core import parse_code
except ImportError:
    logger.error("Rust parser not available - required for code indexing")
    raise RustBuildError("Code indexing requires Rust parser module")
```

**Recovery strategy:**

**Install Rust and build parser:**
```bash
# Install Rust
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
source $HOME/.cargo/env

# Build Rust parser
cd rust_core
maturin develop
```

**Transient?** No - requires Rust installation

**Performance:**
- **Rust parser**: ~1000 files/sec
- Code indexing features require the Rust parser
- Memory storage/retrieval works without Rust parser

**See also:**
- Troubleshooting: [docs/TROUBLESHOOTING.md](TROUBLESHOOTING.md#rust-parser-issues)

---

## Common Error Scenarios

### Scenario 1: First-Time Setup

**Problem:** User installs claude-memory-server and immediately tries to index code without setting up Qdrant.

**Exception:** `QdrantConnectionError` (E010)

**Error message:**
```
[E010] Cannot connect to Qdrant at http://localhost:6333: Connection refused

💡 Solution:
Steps to fix:
1. Start Qdrant: docker-compose up -d
2. Check Qdrant is running: curl http://localhost:6333/health
3. Verify Docker is running: docker ps
4. Use validate-setup command: claude-rag validate-setup

📖 Docs: See docs/SETUP.md for detailed setup instructions
```

**Solution steps:**
1. Ensure Docker is installed and running
2. Navigate to project directory
3. Run: `docker-compose up -d`
4. Wait 5-10 seconds for Qdrant to start
5. Verify: `curl http://localhost:6333/health` should return `{"status":"ok"}`
6. Retry indexing command

**Prevention:**
- Run `python scripts/setup.py` before first use
- Check setup documentation

**Code example:**
```python
import subprocess
import asyncio
from src.core.exceptions import QdrantConnectionError

async def setup_and_index(project_path: str):
    try:
        # Try to index
        await index_project(project_path)
    except QdrantConnectionError:
        print("Qdrant not running. Starting it now...")
        subprocess.run(["docker-compose", "up", "-d"], check=True)
        print("Waiting for Qdrant to start...")
        await asyncio.sleep(10)
        # Retry
        await index_project(project_path)
```

---

### Scenario 2: Memory Not Found

**Problem:** User tries to retrieve a memory using an incorrect ID.

**Exception:** `MemoryNotFoundError` (E012)

**Error message:**
```
[E012] Memory with ID 'abc-123-wrong' not found
```

**Solution steps:**
1. Verify memory ID is correct (check for typos)
2. List available memories: `python -m src.cli list-memories`
3. Search by content instead: `await store.search("query")`
4. Check if memory was deleted

**Code example:**
```python
from src.core.exceptions import MemoryNotFoundError

async def get_or_search(memory_id: str, fallback_query: str):
    try:
        memory = await store.get_memory_by_id(memory_id)
        return memory
    except MemoryNotFoundError:
        # Fall back to search
        results = await store.search(fallback_query, limit=1)
        if results:
            return results[0]
        return None
```

---

### Scenario 3: Collection Not Found

**Problem:** User searches a project that hasn't been indexed yet.

**Exception:** `CollectionNotFoundError` (E011)

**Error message:**
```
[E011] Collection 'my-project' not found

💡 Solution: The collection will be created automatically on first write.
To create it manually: python -m src.cli index ./your-code --project-name my-project
```

**Solution steps:**
1. Index the project first: `python -m src.cli index ./path --project-name my-project`
2. Wait for indexing to complete
3. Retry search

**Code example:**
```python
from src.core.exceptions import CollectionNotFoundError

async def search_or_index(query: str, project_path: str, project_name: str):
    try:
        results = await store.search(query, project_name=project_name)
        return results
    except CollectionNotFoundError:
        print(f"Project not indexed. Indexing {project_path}...")
        await indexer.index_codebase(project_path, project_name)
        # Retry
        results = await store.search(query, project_name=project_name)
        return results
```

---

### Scenario 4: Read-Only Mode

**Problem:** User tries to store memory while server is in read-only mode.

**Exception:** `ReadOnlyError` (E003)

**Error message:**
```
[E003] Cannot perform store operation: server is in read-only mode
```

**Solution steps:**
1. Check if read-only mode is intentional
2. Disable read-only mode: `Config(read_only_mode=False)`
3. Restart server with write permissions

**Code example:**
```python
from src.core.exceptions import ReadOnlyError

async def store_if_allowed(content: str):
    try:
        await server.store_memory(content=content)
    except ReadOnlyError:
        print("Server is in read-only mode. Cannot store new memories.")
        print("Set read_only_mode=False in configuration to enable writes.")
        return None
```

---

### Scenario 5: Missing Dependencies

**Problem:** User tries to generate embeddings without sentence-transformers installed.

**Exception:** `EmbeddingError` (E006) or `DependencyError` (E013)

**Error message:**
```
[E006] Failed to generate embedding: sentence-transformers not installed

💡 Solution: Check:
1. sentence-transformers is installed: pip install sentence-transformers
2. Model is valid: all-MiniLM-L6-v2, all-mpnet-base-v2
3. Sufficient memory available (model requires ~100MB)
4. Text is not empty or too long (max ~8000 tokens)
```

**Solution steps:**
1. Install sentence-transformers: `pip install sentence-transformers`
2. Verify installation: `python -c "import sentence_transformers"`
3. Retry operation

**Code example:**
```python
from src.core.exceptions import EmbeddingError, DependencyError

async def generate_or_fallback(text: str):
    try:
        embedding = await generator.generate(text)
        return embedding
    except (EmbeddingError, DependencyError):
        print("Embeddings not available. Using keyword search only.")
        # Fall back to keyword search
        return None
```

---

### Scenario 6: Code Parsing Failure

**Problem:** Indexer encounters file with syntax errors.

**Exception:** `ParsingError` (E007) or `IndexingError` (E008)

**Error message:**
```
[E007] Failed to parse file: invalid syntax at line 42
```

**Solution steps:**
1. Check file for syntax errors
2. Fix syntax or skip file
3. Verify file encoding is UTF-8
4. Check file type is supported

**Code example:**
```python
from src.core.exceptions import ParsingError

async def index_with_error_handling(file_paths: list[str]):
    successful = []
    failed = []

    for file_path in file_paths:
        try:
            units = await parser.parse_file(file_path)
            successful.append(file_path)
        except ParsingError as e:
            logger.warning(f"Skipping {file_path}: {e}")
            failed.append((file_path, str(e)))

    print(f"Parsed {len(successful)} files, skipped {len(failed)} files")
    return successful, failed
```

---

### Scenario 7: Configuration Errors

**Problem:** User provides invalid configuration values.

**Exception:** `ConfigurationError` (E009)

**Error message:**
```
[E009] Invalid configuration: embedding_dimension must be 384 or 768, got 512
```

**Solution steps:**
1. Review configuration values
2. Check documentation for valid ranges
3. Use default configuration as baseline
4. Validate with `python scripts/setup.py`

**Code example:**
```python
from src.core.exceptions import ConfigurationError
from src.config import Config

def load_config_safely():
    try:
        config = Config.from_env()
        return config
    except ConfigurationError as e:
        print(f"Invalid configuration: {e}")
        print("Using default configuration")
        return Config()  # Use defaults
```

---

## Best Practices

### 1. Catch Specific Exceptions

**Good:**
```python
from src.core.exceptions import QdrantConnectionError, StorageError

try:
    await store.save(memory)
except QdrantConnectionError:
    # Handle connection issues specifically
    print("Qdrant not available. Please start it.")
except StorageError:
    # Handle other storage issues
    print("Storage operation failed")
```

**Bad:**
```python
try:
    await store.save(memory)
except Exception:
    # Too broad - catches everything
    print("Something went wrong")
```

### 2. Use Error Codes for Logging

```python
from src.core.exceptions import MemoryRAGError

try:
    await operation()
except MemoryRAGError as e:
    # Log with error code for tracking
    logger.error(
        f"Operation failed with {e.error_code}: {e}",
        exc_info=True,
        extra={"error_code": e.error_code}
    )
```

### 3. Preserve Exception Chains

```python
try:
    result = await risky_operation()
except ValueError as e:
    # Preserve original exception for debugging
    raise ValidationError(f"Invalid input: {e}") from e
```

### 4. Log with Full Stack Traces

```python
import logging

logger = logging.getLogger(__name__)

try:
    await operation()
except StorageError as e:
    # exc_info=True includes full stack trace
    logger.error(f"Storage failed: {e}", exc_info=True)
```

### 5. User-Friendly vs Debug Messages

```python
try:
    await operation()
except MemoryRAGError as e:
    # User-friendly message
    print(f"Error: {e}")

    # Debug details in logs
    logger.error(
        f"Operation failed: {e}",
        exc_info=True,
        extra={
            "error_code": e.error_code,
            "solution": e.solution,
            "docs_url": e.docs_url
        }
    )
```

### 6. Don't Swallow Exceptions

**Good:**
```python
try:
    await operation()
except StorageError as e:
    logger.error(f"Storage failed: {e}", exc_info=True)
    raise  # Re-raise for caller to handle
```

**Bad:**
```python
try:
    await operation()
except StorageError:
    pass  # Silently ignores error
```

---

## Error Recovery Patterns

### Pattern 1: Retry with Exponential Backoff

```python
import asyncio
from src.core.exceptions import QdrantConnectionError, RetrievalError

async def retry_with_backoff(
    operation,
    *args,
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    **kwargs
):
    """Retry operation with exponential backoff."""
    for attempt in range(max_attempts):
        try:
            return await operation(*args, **kwargs)
        except (QdrantConnectionError, RetrievalError) as e:
            if attempt == max_attempts - 1:
                # Last attempt, give up
                raise

            # Calculate delay: 1s, 2s, 4s, 8s, ...
            delay = min(base_delay * (2 ** attempt), max_delay)
            logger.warning(
                f"Attempt {attempt + 1}/{max_attempts} failed: {e}. "
                f"Retrying in {delay}s..."
            )
            await asyncio.sleep(delay)

# Usage
results = await retry_with_backoff(
    store.search,
    query="test",
    max_attempts=3
)
```

### Pattern 2: Graceful Degradation

```python
from src.core.exceptions import EmbeddingError, DependencyError

class SearchService:
    def __init__(self):
        try:
            from src.embeddings.generator import EmbeddingGenerator
            self.generator = EmbeddingGenerator()
            self.embedding_available = True
        except (EmbeddingError, DependencyError):
            logger.warning("Embeddings not available. Using keyword search only.")
            self.embedding_available = False

    async def search(self, query: str):
        if self.embedding_available:
            # Semantic search (preferred)
            return await self.semantic_search(query)
        else:
            # Fall back to keyword search
            return await self.keyword_search(query)
```

### Pattern 3: Circuit Breaker

```python
import time
from src.core.exceptions import StorageError

class CircuitBreaker:
    def __init__(self, failure_threshold: int = 5, timeout: float = 60.0):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failures = 0
        self.last_failure_time = None
        self.state = "closed"  # closed, open, half-open

    async def call(self, operation, *args, **kwargs):
        if self.state == "open":
            # Circuit is open, check if timeout passed
            if time.time() - self.last_failure_time > self.timeout:
                self.state = "half-open"
            else:
                raise StorageError("Circuit breaker is open")

        try:
            result = await operation(*args, **kwargs)
            # Success - reset failures
            self.failures = 0
            self.state = "closed"
            return result
        except StorageError:
            self.failures += 1
            self.last_failure_time = time.time()

            if self.failures >= self.failure_threshold:
                self.state = "open"
                logger.error("Circuit breaker opened due to repeated failures")

            raise

# Usage
breaker = CircuitBreaker()
result = await breaker.call(store.save, memory)
```

### Pattern 4: Cleanup in Finally Blocks

```python
from src.core.exceptions import IndexingError

async def index_with_cleanup(project_path: str, project_name: str):
    temp_files = []

    try:
        # Create temporary files
        temp_files = await prepare_indexing(project_path)

        # Index the project
        await indexer.index_codebase(project_path, project_name)

    except IndexingError as e:
        logger.error(f"Indexing failed: {e}", exc_info=True)
        # Clean up partial index
        await store.delete_project(project_name)
        raise

    finally:
        # Always clean up temporary files
        for temp_file in temp_files:
            try:
                os.unlink(temp_file)
            except OSError:
                pass
```

### Pattern 5: User Notification

```python
from src.core.exceptions import MemoryRAGError

def format_user_error(error: MemoryRAGError) -> dict:
    """Format error for user-friendly display."""
    message = {
        "error": str(error),
        "code": error.error_code,
        "severity": "error"
    }

    if error.solution:
        message["solution"] = error.solution

    if error.docs_url:
        message["documentation"] = error.docs_url

    return message

# Usage
try:
    await operation()
except MemoryRAGError as e:
    error_message = format_user_error(e)
    print(json.dumps(error_message, indent=2))
    logger.error(f"Operation failed: {e}", exc_info=True)
```

---

## See Also

- [Troubleshooting Guide](TROUBLESHOOTING.md) - Common issues and solutions
- [Setup Guide](SETUP.md) - Installation and configuration
- [Debugging Guide](../DEBUGGING.md) - Debugging workflows
- [API Documentation](API.md) - API reference
- [Architecture](ARCHITECTURE.md) - System design

---

**Last Updated:** 2025-11-25
**Version:** 4.0 RC1
