# Architecture Documentation

**Last Updated:** November 20, 2025
**Version:** 4.0 (Production-Ready Enterprise Features)
**Components:** 159 Python modules (~58K LOC), 17 file type parsers (14 languages + 3 config), 30 CLI commands, 16 MCP tools

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
- **Memory Lifecycle Management:** 4-tier lifecycle system (ACTIVE/RECENT/ARCHIVED/STALE) with automatic transitions
- **Memory Provenance & Trust:** Track memory sources, relationships, and confidence scoring
- **Intelligent Consolidation:** Automatic duplicate detection and merging with conflict resolution
- **Hybrid Code Search:** Combines semantic (vector) and keyword (BM25) search with 3 fusion methods
- **Multi-Language Support:** 17 file types total:
  - **14 Programming Languages:** Python, JavaScript, TypeScript, Java, Go, Rust, Ruby, Swift, Kotlin, PHP, C, C++, C#, SQL
  - **3 Config Formats:** JSON, YAML, TOML
- **Git History Indexing:** Semantic search over commit history with temporal queries
- **Dependency Tracking:** Import/dependency analysis with circular dependency detection
- **Multi-Project Management:** Project context detection, archival, and cross-project search
- **Conversation-Aware Retrieval:** Query expansion, deduplication, and session tracking
- **Smart Context Ranking:** Usage-based ranking with automatic pruning and lifecycle weighting
- **Health Monitoring:** Continuous health tracking with automated remediation
- **Context Stratification:** Auto-classify memories into three levels (USER_PREFERENCE, PROJECT_CONTEXT, SESSION_STATE)
- **Security:** Comprehensive input validation and injection prevention (267+ patterns blocked)
- **Real-time Indexing:** Auto-reindex code files on changes with background job management
- **Token Analytics:** Track token savings and ROI from semantic search
- **Parallel Processing:** Multi-core embedding generation (4-8x faster) and parallel test execution (2.55x faster)

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

**Core Indexing**

**incremental_indexer.py** (26KB, comprehensive)
- Indexes code files incrementally with change detection
- Parse → Extract → Embed → Store → Track hash
- Supports 17 file types:
  - **14 Languages:** Python, JavaScript, TypeScript, Java, Go, Rust, Ruby, Swift, Kotlin, PHP, C, C++, C#, SQL
  - **3 Config Formats:** JSON, YAML, TOML
- Real-time progress callbacks with rich UI
- Parallel embedding generation support (4-8x faster)
- Incremental caching with 98% hit rate (5-10x faster re-indexing)

**auto_indexing_service.py** (16KB)
- Orchestrates automatic foreground/background indexing
- Project staleness detection and auto-reindexing
- Integration with file watcher for real-time updates

**background_indexer.py** (15KB)
- Async background indexing service
- Job queue management with priorities
- Status tracking and progress reporting

**file_watcher.py** (12KB)
- Watches directories for changes with watchdog
- Debounces rapid changes (1000ms default)
- Async operation in background

**python_parser.py** (11KB)
- Pure Python fallback parser using tree-sitter Python bindings
- No Rust dependency required
- Supports all 14 programming languages (10-20x slower than Rust but fully functional)
- Automatic graceful degradation when Rust parser unavailable

**Memory Classification & Lifecycle**

**classifier.py** (8KB)
- Auto-classifies memories into context levels
- Pattern matching on content

**lifecycle_manager.py** (9KB)
- 4-tier lifecycle: ACTIVE, RECENT, ARCHIVED, STALE
- Automatic state transitions based on age and access
- Search weight multipliers (1.0x → 0.7x → 0.3x → 0.1x)

**storage_optimizer.py** (18KB)
- Analyzes memory storage for optimization opportunities
- Detects large memories, stale data, duplicates
- Estimates storage savings with risk classification

**Code Understanding**

**import_extractor.py** (16KB)
- Extracts imports from all supported languages
- Handles absolute, relative, wildcard, and aliased imports
- Language-specific import patterns

**dependency_graph.py** (11KB)
- Builds and queries file dependency graphs
- Transitive dependency resolution
- Circular dependency detection

**docstring_extractor.py** (13KB)
- Multi-language docstring extraction
- Links documentation to code units
- Supports Python, JSDoc, Javadoc, GoDoc, RustDoc

**change_detector.py** (11KB)
- Smart diffing for incremental indexing
- File and function-level change detection
- Rename detection via content similarity

**Git Integration**

**git_indexer.py** (14KB)
- Indexes git commit history semantically
- Extracts commit metadata (author, date, message, stats)
- Configurable commit count and branch filtering
- Auto-detects large repos to disable diffs

**Project Management**

**project_context.py** (11KB)
- Smart project context detection
- Git-aware project switching
- Activity pattern tracking
- Auto-archival recommendations

**project_archival.py** (10KB)
- Project lifecycle states: ACTIVE, PAUSED, ARCHIVED, DELETED
- Activity tracking and search weighting
- Archival workflow management

**project_index_tracker.py** (14KB)
- Project indexing metadata tracking
- Staleness detection
- Index freshness monitoring

**multi_repository_indexer.py** (19KB)
- Multi-repository indexing orchestration
- Cross-repo dependency tracking

**multi_repository_search.py** (18KB)
- Search across multiple indexed repositories
- Consent-based privacy controls

**repository_registry.py** (21KB)
- Central registry for all indexed repositories
- Repository metadata and status tracking

**workspace_manager.py** (19KB)
- Workspace-level repository management
- Multi-project coordination

**Memory Intelligence**

**provenance_tracker.py** (13KB)
- Memory provenance tracking (source, created_by, confidence)
- Verification and trust scoring
- Multi-factor confidence calculation

**relationship_detector.py** (16KB)
- Detects memory relationships (supports, contradicts, duplicates)
- Framework-aware conflict detection
- Temporal reasoning for preference changes

**trust_signals.py** (12KB)
- Trust signal generation for search results
- Multi-factor trust scoring
- Human-readable confidence explanations

**duplicate_detector.py** (9KB)
- Semantic similarity-based duplicate detection
- Three-tier confidence system (auto-merge, review, related)
- Cluster analysis for duplicate groups

**consolidation_engine.py** (11KB)
- Memory merging with 5 strategies
- Merge history tracking for undo
- Consolidation suggestions

**consolidation_jobs.py** (14KB)
- Automated consolidation scheduler (daily/weekly/monthly)
- APScheduler integration
- Background duplicate merging

**Context & Retrieval**

**usage_tracker.py** (9KB)
- Tracks memory access patterns
- Batched updates for efficiency
- Composite scoring (60% similarity + 20% recency + 20% usage)

**pruner.py** (11KB)
- Auto-expires stale SESSION_STATE memories (48h)
- Background cleanup via APScheduler (daily at 2 AM)
- Safety checks and dry-run support

**conversation_tracker.py** (8KB)
- Explicit session management
- Rolling query history (last 5 queries)
- Session timeout (30 minutes idle)
- Background session cleanup

**query_expander.py** (10KB)
- Semantic query expansion using cosine similarity
- Synonym and code context expansion
- Deduplication of previously shown context

**cross_project_consent.py** (4KB)
- Privacy-respecting consent management
- Per-project opt-in for cross-project search

**Optimization & Analysis**

**optimization_analyzer.py** (17KB)
- Project structure analysis
- Detects directories/files to exclude
- Performance impact estimation

**ragignore_manager.py** (10KB)
- .ragignore file management (gitignore syntax)
- Pattern matching and merging

**pattern_detector.py** (11KB)
- Code pattern detection and analysis
- Framework and library usage tracking

**Health & Monitoring**

**health_jobs.py** (12KB)
- Health monitoring background jobs
- Lifecycle health checks
- Automated remediation triggers

**health_scorer.py** (13KB)
- Health score calculation
- Performance, quality, database health metrics
- Trend analysis

**Feedback & Notifications**

**feedback_tracker.py** (12KB)
- User feedback collection
- Search result quality tracking

**notification_manager.py** (11KB)
- User notification system
- Alert delivery and management

**suggestion_engine.py** (12KB)
- Proactive suggestion generation
- Context-aware recommendations

**Utilities**

**indexing_service.py** (5KB)
- Service wrapper for indexing operations

**indexing_metrics.py** (5KB)
- Indexing performance metrics tracking

**time_estimator.py** (6KB)
- Indexing time estimation

**job_state_manager.py** (11KB)
- Background job state management
- Job queue and status tracking

### 3. Vector Storage (src/store/)

**base.py** (37 lines, 70% coverage)
- Abstract interface for storage backends

**qdrant_store.py** (171 lines, 87% coverage)
- Production vector DB implementation
- HNSW indexing (m=16, ef_construct=200)
- 7-13ms search latency
- Batch operations (5x faster)
- Project statistics methods (get_all_projects, get_project_stats)

**sqlite_store.py** (183 lines, 58% coverage)
- Fallback/development storage
- No external dependencies
- Git storage tables (git_commits, git_file_changes)
- Full-text search (FTS5) for commit messages
- Project statistics support

**readonly_wrapper.py** (33 lines, 100% coverage)
- Blocks writes in production mode

### 4. Embeddings (src/embeddings/)

**generator.py** (11KB)
- Model: all-MiniLM-L6-v2 (384 dimensions)
- Async batch processing
- Automatic model initialization and lifecycle management
- Smart batch sizing based on text length

**parallel_generator.py** (14KB)
- Multi-process embedding generation using ProcessPoolExecutor
- 4-8x faster indexing on multi-core systems
- Automatic worker count detection (CPU count)
- Smart threshold: parallel for >10 texts, single-threaded for small batches
- Model caching per worker process
- Integrated with incremental indexer

**cache.py** (14KB)
- SQLite-based embedding cache with SHA256 content hashing
- ~98% cache hit rate for unchanged code
- <1ms cache retrieval via batch_get optimization
- 5-10x faster re-indexing with cache
- Automatic TTL management (30 days default)
- Integrated with both standard and parallel generators

**rust_bridge.py** (3KB)
- FFI integration for Rust-accelerated vector operations
- Optional performance optimization

### 5. Rust Parsing Module (rust_core/)

**parsing.rs** (Rust)
- Tree-sitter AST parsing
- 1-6ms per file (50-100x faster than Python)
- Extracts functions, classes, methods with metadata
- Separate queries for JavaScript and TypeScript
- Improved error recovery

### 6. Search Components (src/search/)

**bm25.py** (8KB)
- BM25+ ranking algorithm implementation
- Token-based keyword matching with IDF scoring
- Configurable parameters (k1=1.5, b=0.75, delta=1.0)
- Better handling of long documents
- Document frequency tracking and term statistics

**hybrid_search.py** (11KB)
- Three fusion strategies:
  - **Weighted**: Alpha-based combination (default alpha=0.5)
  - **RRF**: Reciprocal Rank Fusion (k=60)
  - **Cascade**: BM25-first with semantic re-ranking
- Configurable via environment variables
- Score normalization and combining
- Integrated into server.py search_code() method

**query_synonyms.py** (11KB)
- Comprehensive programming synonym dictionary (200+ terms)
- Code context patterns (25+ domains)
- Synonym expansion: auth→authentication→login→verify
- Context expansion: auth→[user, token, session, credential]
- Improves search recall for technical terms

**reranker.py** (14KB)
- Multi-signal result reranking with configurable weights
- Signals: similarity (60%), recency (20%), usage (20%), length, keywords, diversity
- MMR (Maximal Marginal Relevance) algorithm for diversity
- Exponential recency decay (7-day half-life)
- Logarithmic usage frequency scaling
- Custom reranking function support

### 7. CLI Commands (src/cli/)

The project includes 28 CLI commands for comprehensive system management:

**Core Indexing & Watching**
- **index_command.py** - Code indexing with real-time progress indicators and Rich UI
- **watch_command.py** - File watching with auto-reindexing and debouncing
- **auto_tag_command.py** - Automatic memory tagging

**Project Management**
- **project_command.py** - Project lifecycle management (list, stats, delete, rename, switch, archive)
- **repository_command.py** - Repository management (add, remove, list, update)
- **workspace_command.py** - Workspace-level multi-project coordination
- **collections_command.py** - Memory collection management

**Memory Management**
- **memory_browser.py** - Interactive TUI for browsing and managing memories
- **consolidate_command.py** - Interactive duplicate consolidation with merge strategies
- **verify_command.py** - Memory verification and contradiction resolution
- **prune_command.py** - Manual memory pruning with safety checks
- **lifecycle_command.py** - Lifecycle management (health, update, optimize, auto, config)
- **tags_command.py** - Tag management and organization

**Git Integration**
- **git_index_command.py** - Git history indexing with configurable options
- **git_search_command.py** - Semantic git history search with filters

**Health & Monitoring**
- **health_command.py** - Comprehensive system health checks with diagnostics
- **health_monitor_command.py** - Continuous health monitoring (status, report, fix, history)
- **health_dashboard_command.py** - Interactive health dashboard

**Analytics & Reporting**
- **status_command.py** - Project statistics, file watcher status, system metrics
- **analytics_command.py** - Token usage analytics and cost savings
- **session_summary_command.py** - Session-specific usage summaries

**Data Management**
- **backup_command.py** - Backup creation and management
- **export_command.py** - Data export in multiple formats
- **import_command.py** - Data import and restoration
- **archival_command.py** - Project archival operations

All commands support Rich-formatted output with tables, progress bars, and color-coded status indicators.

### 8. Monitoring & Health (src/monitoring/)

**metrics_collector.py** (24KB)
- Comprehensive metrics collection pipeline
- Performance metrics: search latency, cache hit rate, index staleness
- Quality metrics: avg relevance, noise ratio, duplicate/contradiction rates
- Database health: memory counts by lifecycle state, DB size
- Usage patterns: queries/day, memories created/day
- Time-series storage in local database with 90-day retention
- Daily and weekly metric aggregation

**alert_engine.py** (18KB)
- Alert rule evaluation and management
- Three severity levels: CRITICAL, WARNING, INFO
- Configurable thresholds for 10+ metrics
- Alert history tracking with resolution and snooze
- Automatic alert storage and retrieval

**health_reporter.py** (17KB)
- Overall health score (0-100) with 4-component breakdown
- Performance score (30%): latency, cache hit rate, staleness
- Quality score (40%): relevance, noise ratio, duplicates
- Database health score (20%): lifecycle distribution, size
- Usage efficiency score (10%): query activity, results efficiency
- Status categories: EXCELLENT, GOOD, FAIR, POOR, CRITICAL
- Trend analysis and weekly health reports

**remediation.py** (17KB)
- Automated remediation actions
- 5 actions: prune stale, archive projects, merge duplicates, cleanup sessions, optimize DB
- Dry-run mode for safety
- Remediation history tracking
- Integration with existing pruning and lifecycle systems

### 9. Analytics & Tracking (src/analytics/)

**token_tracker.py** (350+ lines)
- Token usage tracking with local database backend
- Automatic savings estimation: manual paste vs RAG search
- Cost calculation ($3/M input tokens for Claude Sonnet 3.5)
- Session-level analytics with filtering
- Metrics: tokens used/saved, cost savings, efficiency ratio, avg relevance

### 10. Backup & Data Management (src/backup/)

**importer.py** - Data import and restoration
**exporter.py** - Multi-format data export (JSON, Markdown, archives)

### 11. Tagging & Organization (src/tagging/)

**tag_manager.py** - Tag management and organization
**auto_tagger.py** - Automatic tag extraction and categorization

### 12. Router & Retrieval (src/router/)

**retrieval_predictor.py** - Heuristic-based query utility prediction
**retrieval_gate.py** - Configurable gating mechanism (threshold 0.8)
- Gate checks before embedding generation for efficiency
- Target: 30-40% query optimization

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

## Architecture Summary

The Claude Memory RAG Server is a production-ready enterprise system consisting of:

- **123 Python modules** totaling ~500KB of production code
- **44 memory/indexing modules** covering all aspects of code intelligence
- **28 CLI commands** for comprehensive system management
- **12 supported formats**: 9 programming languages + 3 config formats
- **4 major subsystems**: Memory, Search, Monitoring, Project Management
- **3-tier security** architecture with 267+ attack patterns blocked
- **Multi-process architecture** with 4-8x parallel embedding speedup
- **Real-time monitoring** with automated health remediation

The system achieves:
- **7-13ms search latency** (vector + hybrid search)
- **98% cache hit rate** for unchanged code
- **10-20 files/sec indexing** with parallel embeddings
- **99.9% test pass rate** (1413/1414 tests passing)
- **67% overall coverage** (80-85% on core modules)

---

**Document Version:** 2.0
**Last Updated:** November 17, 2025
**Status:** Comprehensive rewrite reflecting all recent features
