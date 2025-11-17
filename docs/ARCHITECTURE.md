# Architecture Documentation

**Last Updated:** November 16, 2025
**Version:** 3.0 (Security & Context Enabled)

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Component Architecture](#component-architecture)
3. [Data Flow](#data-flow)
4. [Storage Layer](#storage-layer)
5. [Python-Rust Integration](#python-rust-integration)
6. [Security Architecture](#security-architecture)

---

## System Overview

The Claude Memory RAG Server is a Model Context Protocol (MCP) server that provides persistent memory and semantic code search capabilities for Claude AI.

### Key Capabilities

- **Persistent Memory:** Store and retrieve user preferences, project context, and session state
- **Semantic Code Search:** Search codebases by meaning, not just keywords
- **Context Stratification:** Auto-classify memories into three levels
- **Security:** Comprehensive input validation and injection prevention
- **Real-time Indexing:** Auto-reindex code files on changes

### Technology Stack

```
┌─────────────────────────────────────────┐
│           Claude via MCP                 │
└─────────────────┬───────────────────────┘
                  │
┌─────────────────▼───────────────────────┐
│         Python 3.13 Application          │
│  - FastAPI/MCP Server Layer              │
│  - Business Logic Layer                  │
│  - Data Access Layer                     │
└─────────────────┬───────────────────────┘
                  │
    ┌─────────────┼─────────────┐
    ▼             ▼             ▼
┌─────────┐  ┌─────────┐  ┌──────────────┐
│ Qdrant  │  │ Rust    │  │ sentence-    │
│ Vector  │  │ Parser  │  │ transformers │
│ DB      │  │ (PyO3)  │  │ (embeddings) │
└─────────┘  └─────────┘  └──────────────┘
```

---

## Component Architecture

### 1. Core Server (src/core/)

**server.py** - Main MCP server (186 lines, 64% coverage)
- Tool registration for MCP protocol
- Async request handling
- Integration with all subsystems
- Key methods: store_memory(), retrieve_memories(), search_code(), index_codebase()

**models.py** (133 lines, 98% coverage)
- Pydantic v2 models for type safety
- MemoryUnit, QueryRequest, SearchFilters
- Enums: MemoryCategory, ContextLevel, MemoryScope

**validation.py** (130 lines, 97% coverage)
- Injection pattern detection (SQL, prompt, command, path traversal)
- Text sanitization (null bytes, control characters)
- Content size validation (max 50KB)
- 267/267 attack patterns blocked

**exceptions.py** (35 lines, 80% coverage)
- ValidationError, StorageError, ReadOnlyError, SecurityError

### 2. Memory & Code Indexing (src/memory/)

**incremental_indexer.py** (140 lines, 86% coverage)
- Indexes code files incrementally with change detection
- Parse → Extract → Embed → Store → Track hash
- Supports 6 languages: Python, JS, TS, Java, Go, Rust

**file_watcher.py** (129 lines, 70% coverage)
- Watches directories for changes with watchdog
- Debounces rapid changes (1000ms default)
- Async operation in background

**classifier.py** (71 lines, 90% coverage)
- Auto-classifies memories into context levels
- Pattern matching on content

### 3. Vector Storage (src/store/)

**base.py** (37 lines, 70% coverage)
- Abstract interface for storage backends

**qdrant_store.py** (171 lines, 74% coverage)
- Production vector DB implementation
- HNSW indexing (m=16, ef_construct=200)
- 7-13ms search latency
- Batch operations (5x faster)

**sqlite_store.py** (183 lines, 58% coverage)
- Fallback/development storage
- No external dependencies

**readonly_wrapper.py** (33 lines, 100% coverage)
- Blocks writes in production mode

### 4. Embeddings (src/embeddings/)

**generator.py** (88 lines, 89% coverage)
- Model: all-MiniLM-L6-v2 (384 dimensions)
- Async batch processing

**cache.py** (130 lines, 65% coverage)
- SQLite-based caching
- ~90% cache hit rate
- <1ms cache retrieval

### 5. Rust Parsing Module (rust_core/)

**parsing.rs** (Rust)
- Tree-sitter AST parsing
- 1-6ms per file (50-100x faster than Python)
- Extracts functions, classes, methods with metadata

---

## Data Flow

### Memory Storage Flow

```
Claude (MCP)
     │ store_memory(content, category, ...)
     ▼
[1. Validation]
     │ - Injection detection
     │ - Size limits
     │ - Sanitization
     ▼
[2. Classification]
     │ - Auto-detect context level
     ▼
[3. Embedding Generation]
     │ - Check cache
     │ - Generate if miss
     ▼
[4. Vector Storage]
     │ - Insert point with metadata
     ▼
Claude ← {"memory_id": "550e8400-...", "status": "stored"}
```

### Memory Retrieval Flow

```
Claude (MCP)
     │ retrieve_memories(query, filters)
     ▼
[1. Validation]
     ▼
[2. Embedding Generation]
     │ - Generate query embedding
     ▼
[3. Vector Search]
     │ - Similarity search
     │ - Apply filters
     │ - Rank by score
     ▼
Claude ← [{"content": "...", "score": 0.92, ...}, ...]
```

### Code Indexing Flow

```
CLI: python -m src.cli index ./src
     │
     ▼
[1. File Discovery]
     │ - Scan directory
     │ - Check file hashes
     │ - Identify changed files
     ▼
[2. Rust Parsing]
     │ - Tree-sitter AST parsing
     │ - Extract functions/classes
     │ - 1-6ms per file
     ▼
[3. Content Preparation]
     │ - Build searchable content
     │ - Format: file:line + signature
     ▼
[4. Batch Embedding]
     │ - Generate embeddings
     ▼
[5. Batch Storage]
     │ - Upsert points in Qdrant
     ▼
"Indexed 175 units from 4 files in 2.99s"
```

### Code Search Flow

```
Claude (MCP)
     │ search_code(query="auth logic", project="my-app")
     ▼
[1. Query Embedding]
     ▼
[2. Vector Search]
     │ - Similarity search
     │ - Filter by project/language
     │ - 7-13ms latency
     ▼
Claude ← [{
  "file_path": "src/auth/handlers.py",
  "start_line": 45,
  "unit_name": "login",
  "signature": "async def login(...)",
  "score": 0.89
}, ...]
```

---

## Storage Layer

### Qdrant Vector Database

**Collection Schema:**
```python
{
    "collection_name": "memory",
    "vector_config": {
        "size": 384,  # all-MiniLM-L6-v2
        "distance": "Cosine"
    },
    "hnsw_config": {
        "m": 16,
        "ef_construct": 200
    },
    "quantization_config": {
        "scalar": {"type": "int8"}  # 75% memory savings
    }
}
```

**Payload Indices:**
- category, context_level, scope, project_name (KEYWORD)
- unit_type, language (KEYWORD) - for code
- importance (FLOAT_RANGE)

**Point Structure:**
```python
{
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "vector": [0.123, -0.456, ...],  # 384 dims
    "payload": {
        # Memory fields
        "content": "I prefer Python for ML",
        "category": "preference",
        "context_level": "USER_PREFERENCE",
        
        # Code fields (if applicable)
        "file_path": "src/auth/handlers.py",
        "unit_type": "function",
        "unit_name": "login",
        "start_line": 45,
        "end_line": 67,
        "language": "python"
    }
}
```

---

## Python-Rust Integration

### PyO3 Bridge

**Compilation:**
```bash
cd rust_core
maturin develop  # Development
maturin build --release  # Production
```

**Python Import:**
```python
import mcp_performance_core

# Available functions:
# - parse_source_file(path, source) -> dict
# - batch_parse_files(files) -> List[dict]
```

**Performance:**
```
Python parser:  50-100ms per file
Rust parser:    1-6ms per file
Speedup:        8-100x faster
```

---

## Security Architecture

### Defense in Depth

```
Layer 1: MCP Protocol Validation
    ↓
Layer 2: Pydantic Model Validation
    ↓
Layer 3: Injection Detection (267/267 patterns blocked)
    ↓
Layer 4: Text Sanitization
    ↓
Layer 5: Read-Only Mode (Optional)
    ↓
Layer 6: Security Logging
```

### Read-Only Mode

**Activation:**
```bash
export CLAUDE_RAG_READ_ONLY_MODE=true
# or
python -m src.mcp_server --read-only
```

**Behavior:**
- All writes raise ReadOnlyError
- All reads work normally
- Production safety mode

---

## Performance Characteristics

| Operation | Target | Actual | Status |
|-----------|--------|--------|--------|
| Parse file (Rust) | <10ms | 1-6ms | ✅ |
| Indexing speed | >1 file/sec | 2.45 files/sec | ✅ |
| Vector search | <50ms | 7-13ms | ✅ |
| Embedding (cached) | <5ms | <1ms | ✅ |

### Scalability

- **Vector DB:** Up to 10M points per collection
- **Code Indexing:** 2.45 files/sec, 83 units/sec
- **Memory Usage:** ~100MB base + ~5MB per 1K memories

---

**Document Version:** 1.0
**Last Updated:** November 16, 2025
