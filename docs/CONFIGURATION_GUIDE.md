# Configuration Guide

**Last Updated:** November 26, 2025
**Version:** 4.0 (Production-Ready)

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Configuration Methods](#configuration-methods)
3. [Feature Level Presets](#feature-level-presets)
4. [Core Settings](#core-settings)
5. [Feature Groups](#feature-groups)
   - [Performance Features](#performance-features)
   - [Search Features](#search-features)
   - [Analytics Features](#analytics-features)
   - [Memory Features](#memory-features)
   - [Indexing Features](#indexing-features)
   - [Advanced Features](#advanced-features)
6. [Storage Configuration](#storage-configuration)
7. [Performance Tuning](#performance-tuning)
8. [Ranking and Scoring](#ranking-and-scoring)
9. [Common Configuration Profiles](#common-configuration-profiles)
10. [Troubleshooting Misconfigurations](#troubleshooting-misconfigurations)
11. [Migration from Legacy Configuration](#migration-from-legacy-configuration)
12. [Complete Options Reference](#complete-options-reference)

---

## Quick Start

### Minimal Configuration (Get Started Fast)

Create `~/.claude-rag/config.json`:

```json
{
  "storage_backend": "qdrant",
  "qdrant_url": "http://localhost:6333",
  "feature_level": "basic"
}
```

This gives you:
- Qdrant vector storage (requires Docker)
- All stable, production-ready features
- Sensible defaults for everything else

### View Current Configuration

```bash
# See all active settings
python -m src.cli status

# Validate configuration
python -m src.cli validate-install
```

---

## Configuration Methods

The server supports three configuration methods with clear priority:

### Priority Order (Highest to Lowest)

1. **Environment Variables** (`CLAUDE_RAG_*`)
2. **User Config File** (`~/.claude-rag/config.json`)
3. **Built-in Defaults**

### Method 1: JSON Configuration (Recommended)

**Location:** `~/.claude-rag/config.json`

**Benefits:**
- Persistent across all projects
- Easy to read and edit
- Version control friendly
- No environment variable conflicts

**Example:**
```json
{
  "server_name": "claude-memory-rag",
  "log_level": "INFO",
  "storage_backend": "qdrant",
  "qdrant_url": "http://localhost:6333",
  "performance": {
    "parallel_embeddings": true,
    "parallel_workers": 4,
    "gpu_enabled": true
  },
  "indexing": {
    "auto_index_enabled": true,
    "auto_index_on_startup": true,
    "file_watcher": true
  }
}
```

### Method 2: Environment Variables

**When to Use:**
- Override global settings for specific projects
- CI/CD environments
- Temporary configuration changes

**Example (.env file):**
```bash
# Core Settings
CLAUDE_RAG_SERVER_NAME=claude-memory-rag
CLAUDE_RAG_LOG_LEVEL=INFO

# Storage
CLAUDE_RAG_STORAGE_BACKEND=qdrant
CLAUDE_RAG_QDRANT_URL=http://localhost:6333

# Feature Groups (new format)
CLAUDE_RAG_PERFORMANCE__PARALLEL_EMBEDDINGS=true
CLAUDE_RAG_PERFORMANCE__PARALLEL_WORKERS=4
CLAUDE_RAG_INDEXING__AUTO_INDEX_ENABLED=true
```

**Note:** Feature group options use double underscores (`__`) to separate group from option.

### Method 3: Built-in Defaults

If no configuration is provided, the server uses sensible defaults optimized for:
- Small to medium codebases (< 10,000 files)
- Standard hardware (4-8 CPU cores, 8-16GB RAM)
- Local development environments

---

## Feature Level Presets

**NEW in v4.0!** Configure everything with a single setting.

### `feature_level` Options

| Level | Description | Use Case |
|-------|-------------|----------|
| `"basic"` | Stable, production-ready features only | Production deployments, critical systems |
| `"advanced"` | All stable features including power-user features | Development, advanced users |
| `"experimental"` | All features including unstable/bleeding-edge | Testing, feature exploration |

### Basic Level (Default)

```json
{
  "feature_level": "basic"
}
```

**Enables:**
- Core semantic search
- Memory management
- File watching
- Parallel embeddings
- Hybrid search

**Disables:**
- Proactive suggestions (experimental)
- Git diff indexing (performance impact)
- Multi-repository features (complex)

### Advanced Level

```json
{
  "feature_level": "advanced"
}
```

**Adds to Basic:**
- Proactive memory suggestions
- Git commit indexing
- Usage pattern analytics
- Query expansion
- Cross-project search

### Experimental Level

```json
{
  "feature_level": "experimental"
}
```

**Enables Everything:**
- All basic and advanced features
- Git diff indexing
- Multi-repository coordination
- Experimental performance optimizations

**Warning:** May include unstable features. Not recommended for production.

---

## Core Settings

### Server Configuration

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `server_name` | string | `"claude-memory-rag"` | MCP server name identifier |
| `log_level` | string | `"INFO"` | Logging level: DEBUG, INFO, WARNING, ERROR, CRITICAL |

**Example:**
```json
{
  "server_name": "my-memory-server",
  "log_level": "DEBUG"
}
```

### Storage Backend

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `storage_backend` | string | `"qdrant"` | Vector storage backend (only "qdrant" supported in v4.0) |
| `qdrant_url` | string | `"http://localhost:6333"` | Qdrant server URL |
| `qdrant_api_key` | string | `null` | Optional API key for Qdrant Cloud |
| `qdrant_collection_name` | string | `"memory"` | Collection name for vectors |

**Example - Local Qdrant:**
```json
{
  "storage_backend": "qdrant",
  "qdrant_url": "http://localhost:6333"
}
```

**Example - Qdrant Cloud:**
```json
{
  "storage_backend": "qdrant",
  "qdrant_url": "https://xyz.qdrant.io",
  "qdrant_api_key": "your-api-key-here"
}
```

### Connection Pooling

**NEW in PERF-007!** Optimize Qdrant connections for high-throughput workloads.

| Option | Type | Default | Description | Valid Range |
|--------|------|---------|-------------|-------------|
| `qdrant_pool_size` | int | `5` | Maximum connections in pool | 1-20 |
| `qdrant_pool_min_size` | int | `1` | Minimum connections to maintain | 1-pool_size |
| `qdrant_pool_timeout` | float | `10.0` | Max wait for connection (seconds) | 1.0-60.0 |
| `qdrant_pool_recycle` | int | `3600` | Recycle connections after N seconds | 300-86400 |
| `qdrant_prefer_grpc` | bool | `false` | Use gRPC for better performance | true/false |
| `qdrant_health_check_interval` | int | `60` | Health check interval (seconds) | 10-600 |

**Example - High Throughput:**
```json
{
  "qdrant_pool_size": 10,
  "qdrant_pool_min_size": 3,
  "qdrant_prefer_grpc": true
}
```

**When to Use:**
- Large pool (10-20): High concurrency, many simultaneous searches
- Small pool (2-5): Low concurrency, resource-constrained environments
- gRPC: Production deployments, low-latency requirements

### Embedding Configuration

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `embedding_model` | string | `"all-MiniLM-L6-v2"` | Sentence transformer model |
| `embedding_batch_size` | int | `32` | Batch size for embedding generation |
| `embedding_cache_enabled` | bool | `true` | Enable embedding cache for faster re-indexing |
| `embedding_cache_path` | string | `"~/.claude-rag/embedding_cache.db"` | SQLite cache file path |
| `embedding_cache_ttl_days` | int | `30` | Cache entry time-to-live |

**Valid Ranges:**
- `embedding_batch_size`: 1-256 (higher = faster but more memory)
- `embedding_cache_ttl_days`: 1-3650 (10 years max)

**Example - Performance Optimized:**
```json
{
  "embedding_model": "all-MiniLM-L6-v2",
  "embedding_batch_size": 64,
  "embedding_cache_enabled": true,
  "embedding_cache_ttl_days": 90
}
```

### SQLite Metadata Storage

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `sqlite_path` | string | `"~/.claude-rag/metadata.db"` | SQLite database for project metadata |

**Note:** SQLite is used for metadata tracking (project statistics, indexing status), not vector storage. Qdrant handles all vector operations.

---

## Feature Groups

Configuration is organized into logical feature groups for better manageability.

### Performance Features

**Group:** `performance`

Optimize computational performance and resource usage.

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `parallel_embeddings` | bool | `true` | Use multiprocessing for embedding generation (4-8x faster) |
| `parallel_workers` | int | `null` | Number of worker processes (null = auto-detect CPU count) |
| `hybrid_search` | bool | `true` | Enable BM25 + vector hybrid search |
| `importance_scoring` | bool | `true` | Intelligent importance scoring for code units |
| `gpu_enabled` | bool | `true` | Auto-use GPU if available for embeddings |
| `gpu_memory_fraction` | float | `0.8` | Max GPU memory to use (0.0-1.0) |
| `force_cpu` | bool | `false` | Force CPU-only mode (overrides GPU detection) |

**Validation:**
- `gpu_enabled` and `force_cpu` cannot both be true
- `gpu_memory_fraction` must be between 0.0 and 1.0

**Example - High Performance:**
```json
{
  "performance": {
    "parallel_embeddings": true,
    "parallel_workers": 8,
    "hybrid_search": true,
    "importance_scoring": true,
    "gpu_enabled": true,
    "gpu_memory_fraction": 0.9
  }
}
```

**Example - Resource Constrained:**
```json
{
  "performance": {
    "parallel_embeddings": false,
    "force_cpu": true,
    "gpu_enabled": false
  }
}
```

**Performance Impact:**
- `parallel_embeddings=true`: 4-8x faster indexing
- `gpu_enabled=true`: 2-3x faster embeddings (if GPU available)
- `hybrid_search=true`: 30-50% higher search quality, ~2x latency

### Search Features

**Group:** `search`

Configure search behavior and retrieval quality.

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `hybrid_search` | bool | `true` | BM25 + vector hybrid search |
| `retrieval_gate_enabled` | bool | `true` | Filter low-quality results |
| `retrieval_gate_threshold` | float | `0.8` | Minimum similarity threshold (0.0-1.0) |
| `cross_project_enabled` | bool | `true` | Allow searching across projects |
| `cross_project_default_mode` | string | `"current"` | Default scope: "current" or "all" |
| `query_expansion_enabled` | bool | `true` | Expand queries with synonyms/context |
| `query_expansion_synonyms` | bool | `true` | Add programming term synonyms |
| `query_expansion_code_context` | bool | `true` | Add code domain patterns |
| `query_expansion_max_synonyms` | int | `2` | Max synonyms per term |
| `query_expansion_max_context_terms` | int | `3` | Max context terms to add |

**Example - High Precision:**
```json
{
  "search": {
    "hybrid_search": true,
    "retrieval_gate_enabled": true,
    "retrieval_gate_threshold": 0.85,
    "query_expansion_enabled": true,
    "query_expansion_max_synonyms": 3
  }
}
```

**Example - High Recall:**
```json
{
  "search": {
    "hybrid_search": true,
    "retrieval_gate_enabled": false,
    "query_expansion_enabled": true,
    "query_expansion_max_synonyms": 4,
    "query_expansion_max_context_terms": 5
  }
}
```

**Search Modes Explained:**
- **Semantic Only** (`hybrid_search=false`): Understanding-based, finds related concepts
- **Hybrid** (`hybrid_search=true`): Best of both worlds, balances precision and recall
- **Keyword Focus** (adjust `hybrid_search_alpha` to 0.2): Prioritizes exact term matches

### Analytics Features

**Group:** `analytics`

Usage tracking and pattern analysis.

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `usage_tracking` | bool | `true` | Track memory access patterns |
| `usage_pattern_analytics` | bool | `true` | Analyze patterns for insights |
| `usage_analytics_retention_days` | int | `90` | How long to keep analytics data |

**Validation:**
- `usage_pattern_analytics` requires `usage_tracking=true`

**Example - Full Analytics:**
```json
{
  "analytics": {
    "usage_tracking": true,
    "usage_pattern_analytics": true,
    "usage_analytics_retention_days": 180
  }
}
```

**Example - Privacy Focused:**
```json
{
  "analytics": {
    "usage_tracking": false,
    "usage_pattern_analytics": false
  }
}
```

**Privacy Note:** All analytics are stored locally. No data is sent to external services.

### Memory Features

**Group:** `memory`

Memory management and lifecycle.

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `auto_pruning` | bool | `true` | Automatic cleanup of old memories |
| `pruning_schedule` | string | `"0 2 * * *"` | Cron schedule (2 AM daily by default) |
| `session_state_ttl_hours` | int | `48` | Session state TTL (1-720 hours) |
| `conversation_tracking` | bool | `true` | Track conversation context |
| `conversation_session_timeout_minutes` | int | `30` | Session timeout (1-1440 minutes) |
| `proactive_suggestions` | bool | `true` | Analyze messages for context patterns |
| `proactive_suggestions_threshold` | float | `0.90` | Confidence threshold (0.0-1.0) |

**Example - Aggressive Cleanup:**
```json
{
  "memory": {
    "auto_pruning": true,
    "pruning_schedule": "0 */6 * * *",
    "session_state_ttl_hours": 24
  }
}
```

**Example - Long Retention:**
```json
{
  "memory": {
    "auto_pruning": true,
    "pruning_schedule": "0 2 * * 0",
    "session_state_ttl_hours": 168
  }
}
```

**Cron Schedule Examples:**
- `"0 2 * * *"` - Every day at 2 AM
- `"0 */6 * * *"` - Every 6 hours
- `"0 2 * * 0"` - Every Sunday at 2 AM
- `"0 0 1 * *"` - First day of every month

### Indexing Features

**Group:** `indexing`

Code indexing and file watching.

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `file_watcher` | bool | `true` | Watch for file changes |
| `watch_debounce_ms` | int | `1000` | Debounce delay (milliseconds) |
| `auto_index_enabled` | bool | `true` | Enable automatic indexing |
| `auto_index_on_startup` | bool | `true` | Index on MCP server startup |
| `auto_index_size_threshold` | int | `500` | Files threshold for background mode |
| `auto_index_recursive` | bool | `true` | Recursive directory indexing |
| `auto_index_show_progress` | bool | `true` | Show progress indicators |
| `auto_index_exclude_patterns` | list | See below | Patterns to exclude from indexing |
| `git_indexing` | bool | `true` | Index git commit history |
| `git_index_commit_count` | int | `1000` | Max commits to index (1-100000) |
| `git_index_branches` | string | `"current"` | "current" or "all" |
| `git_index_tags` | bool | `true` | Index git tags |
| `git_index_diffs` | bool | `true` | Index commit diffs (experimental) |

**Default Exclude Patterns:**
```json
[
  "node_modules/**",
  ".git/**",
  "venv/**",
  "__pycache__/**",
  "*.pyc",
  "dist/**",
  "build/**",
  ".next/**",
  "target/**",
  "*.min.js",
  "*.map"
]
```

**Validation:**
- `auto_index_on_startup` requires `auto_index_enabled=true`
- `auto_index_size_threshold`: 1-100000

**Example - Auto-Indexing Enabled:**
```json
{
  "indexing": {
    "auto_index_enabled": true,
    "auto_index_on_startup": true,
    "auto_index_size_threshold": 1000,
    "file_watcher": true,
    "watch_debounce_ms": 500
  }
}
```

**Example - Manual Indexing Only:**
```json
{
  "indexing": {
    "auto_index_enabled": false,
    "file_watcher": false,
    "git_indexing": false
  }
}
```

**Example - Git Heavy:**
```json
{
  "indexing": {
    "git_indexing": true,
    "git_index_commit_count": 5000,
    "git_index_branches": "all",
    "git_index_tags": true,
    "git_index_diffs": true
  }
}
```

**Auto-Index Modes:**
- **Foreground** (< threshold): Blocks startup, completes in 30-60s
- **Background** (>= threshold): Non-blocking, continues in background

### Advanced Features

**Group:** `advanced`

Advanced and experimental features.

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `multi_repository` | bool | `true` | Enable multi-repository features |
| `multi_repo_max_parallel` | int | `3` | Max concurrent repository operations (1-10) |
| `rust_fallback` | bool | `true` | Fall back to Python parser if Rust unavailable |
| `warn_on_degradation` | bool | `true` | Show warnings in degraded mode |
| `read_only_mode` | bool | `false` | Restrict to read-only operations |
| `input_validation` | bool | `true` | Validate all inputs |

**Example - Production Hardening:**
```json
{
  "advanced": {
    "read_only_mode": false,
    "input_validation": true,
    "warn_on_degradation": true,
    "rust_fallback": true
  }
}
```

**Example - Multi-Repository:**
```json
{
  "advanced": {
    "multi_repository": true,
    "multi_repo_max_parallel": 5
  }
}
```

---

## Storage Configuration

### Qdrant-Specific Settings

**Full connection configuration:**

```json
{
  "storage_backend": "qdrant",
  "qdrant_url": "http://localhost:6333",
  "qdrant_api_key": null,
  "qdrant_collection_name": "memory",
  "qdrant_pool_size": 5,
  "qdrant_pool_min_size": 1,
  "qdrant_pool_timeout": 10.0,
  "qdrant_pool_recycle": 3600,
  "qdrant_prefer_grpc": false,
  "qdrant_health_check_interval": 60
}
```

### File Paths

All paths support `~` (home directory) and environment variable expansion.

| Option | Default | Description |
|--------|---------|-------------|
| `embedding_cache_path` | `~/.claude-rag/embedding_cache.db` | Embedding cache SQLite file |
| `sqlite_path` | `~/.claude-rag/metadata.db` | Metadata SQLite database |
| `cross_project_opt_in_file` | `~/.claude-rag/cross_project_consent.json` | Cross-project consent |
| `repository_storage_path` | `~/.claude-rag/repositories.json` | Repository metadata |
| `workspace_storage_path` | `~/.claude-rag/workspaces.json` | Workspace metadata |

**Example - Custom Paths:**
```json
{
  "embedding_cache_path": "/mnt/cache/embeddings.db",
  "sqlite_path": "/var/lib/claude-rag/metadata.db"
}
```

---

## Performance Tuning

### Timeouts and Limits

| Option | Type | Default | Description | Valid Range |
|--------|------|---------|-------------|-------------|
| `retrieval_timeout_ms` | int | `500` | Search timeout (milliseconds) | 100-30000 |
| `max_query_context_tokens` | int | `8000` | Max context tokens | 1000-100000 |
| `max_memory_size_bytes` | int | `10240` | Max memory size (10KB) | 1024+ |

**Example - Fast Searches:**
```json
{
  "retrieval_timeout_ms": 200,
  "max_query_context_tokens": 4000
}
```

**Example - Thorough Searches:**
```json
{
  "retrieval_timeout_ms": 2000,
  "max_query_context_tokens": 16000
}
```

### Batch Processing

| Option | Type | Default | Description | Valid Range |
|--------|------|---------|-------------|-------------|
| `embedding_batch_size` | int | `32` | Embedding generation batch size | 1-256 |
| `usage_batch_size` | int | `100` | Usage tracking batch size | 1-10000 |
| `usage_flush_interval_seconds` | int | `60` | Usage data flush interval | 1+ |

**Example - High Throughput:**
```json
{
  "embedding_batch_size": 128,
  "usage_batch_size": 500,
  "usage_flush_interval_seconds": 30
}
```

### Hybrid Search Tuning

| Option | Type | Default | Description | Valid Range |
|--------|------|---------|-------------|-------------|
| `hybrid_search_alpha` | float | `0.5` | BM25 vs vector weight (0=BM25 only, 1=vector only) | 0.0-1.0 |
| `hybrid_fusion_method` | string | `"weighted"` | Fusion method: "weighted" or "rrf" | - |
| `bm25_k1` | float | `1.5` | BM25 term frequency saturation | 0.0-3.0 |
| `bm25_b` | float | `0.75` | BM25 length normalization | 0.0-1.0 |

**Example - Keyword Focused:**
```json
{
  "hybrid_search_alpha": 0.3,
  "bm25_k1": 1.8,
  "bm25_b": 0.8
}
```

**Example - Semantic Focused:**
```json
{
  "hybrid_search_alpha": 0.8,
  "bm25_k1": 1.2,
  "bm25_b": 0.5
}
```

**Alpha Values Explained:**
- `0.0` - Pure keyword search (BM25 only)
- `0.3` - Keyword-heavy hybrid
- `0.5` - Balanced hybrid (default)
- `0.7` - Semantic-heavy hybrid
- `1.0` - Pure semantic search (vector only)

---

## Ranking and Scoring

### Ranking Weights

**IMPORTANT:** Weights must sum to 1.0 (±0.01 tolerance).

| Option | Type | Default | Description | Valid Range |
|--------|------|---------|-------------|-------------|
| `ranking_weight_similarity` | float | `0.6` | Semantic similarity weight | 0.0-1.0 |
| `ranking_weight_recency` | float | `0.2` | Recency weight | 0.0-1.0 |
| `ranking_weight_usage` | float | `0.2` | Usage frequency weight | 0.0-1.0 |

**Example - Similarity Focused:**
```json
{
  "ranking_weight_similarity": 0.8,
  "ranking_weight_recency": 0.1,
  "ranking_weight_usage": 0.1
}
```

**Example - Recency Focused:**
```json
{
  "ranking_weight_similarity": 0.4,
  "ranking_weight_recency": 0.4,
  "ranking_weight_usage": 0.2
}
```

### Importance Scoring Weights

Configure how code importance is calculated (requires `performance.importance_scoring=true`).

| Option | Type | Default | Description | Valid Range |
|--------|------|---------|-------------|-------------|
| `importance_complexity_weight` | float | `1.0` | Cyclomatic complexity weight | 0.0-2.0 |
| `importance_usage_weight` | float | `1.0` | Usage frequency weight | 0.0-2.0 |
| `importance_criticality_weight` | float | `1.0` | Criticality score weight | 0.0-2.0 |

**Example - Complexity Focused:**
```json
{
  "importance_complexity_weight": 1.5,
  "importance_usage_weight": 0.8,
  "importance_criticality_weight": 0.7
}
```

### Recency Configuration

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `recency_decay_halflife_days` | float | `7.0` | Half-life for recency decay (days) | Must be > 0 |

**Halflife Examples:**
- `3.5` - Aggressive decay, recent items strongly favored
- `7.0` - Balanced (default)
- `14.0` - Gentle decay, older items remain relevant longer

### Conversation and Deduplication

| Option | Type | Default | Description | Valid Range |
|--------|------|---------|-------------|-------------|
| `conversation_query_history_size` | int | `5` | Query history size | 1-50 |
| `query_expansion_similarity_threshold` | float | `0.7` | Similarity threshold for expansion | 0.0-1.0 |
| `deduplication_fetch_multiplier` | int | `3` | Fetch multiplier for deduplication | 1-10 |

---

## Common Configuration Profiles

### Minimal (Fast Setup, No Docker)

**Use Case:** Quick testing, no external dependencies

```json
{
  "storage_backend": "qdrant",
  "qdrant_url": "http://localhost:6333",
  "feature_level": "basic",
  "performance": {
    "parallel_embeddings": false,
    "force_cpu": true
  },
  "indexing": {
    "auto_index_enabled": false,
    "file_watcher": false,
    "git_indexing": false
  }
}
```

**Characteristics:**
- Requires Qdrant running
- Single-threaded, CPU-only
- Manual indexing only
- ~3 minutes setup

### Development (Balanced)

**Use Case:** Daily development, local machine

```json
{
  "storage_backend": "qdrant",
  "qdrant_url": "http://localhost:6333",
  "feature_level": "advanced",
  "log_level": "DEBUG",
  "performance": {
    "parallel_embeddings": true,
    "parallel_workers": 4,
    "gpu_enabled": true
  },
  "indexing": {
    "auto_index_enabled": true,
    "auto_index_on_startup": true,
    "auto_index_size_threshold": 500,
    "file_watcher": true,
    "git_indexing": true
  },
  "search": {
    "hybrid_search": true,
    "query_expansion_enabled": true
  }
}
```

**Characteristics:**
- Full features enabled
- Auto-indexing on startup
- File watching for changes
- 4 worker processes

### Production (Optimized)

**Use Case:** Production deployment, high performance

```json
{
  "storage_backend": "qdrant",
  "qdrant_url": "http://localhost:6333",
  "feature_level": "advanced",
  "log_level": "INFO",
  "qdrant_pool_size": 10,
  "qdrant_pool_min_size": 3,
  "qdrant_prefer_grpc": true,
  "performance": {
    "parallel_embeddings": true,
    "parallel_workers": 8,
    "gpu_enabled": true,
    "gpu_memory_fraction": 0.9,
    "hybrid_search": true,
    "importance_scoring": true
  },
  "embedding_batch_size": 64,
  "indexing": {
    "auto_index_enabled": true,
    "auto_index_on_startup": true,
    "auto_index_size_threshold": 1000,
    "file_watcher": true,
    "watch_debounce_ms": 500,
    "git_indexing": true,
    "git_index_commit_count": 5000
  },
  "search": {
    "hybrid_search": true,
    "retrieval_gate_enabled": true,
    "retrieval_gate_threshold": 0.85,
    "query_expansion_enabled": true
  },
  "analytics": {
    "usage_tracking": true,
    "usage_pattern_analytics": true
  }
}
```

**Characteristics:**
- 10 connection pool
- gRPC for low latency
- 8 worker processes
- GPU acceleration
- Background indexing for large projects

### High-Performance (Latency Optimized)

**Use Case:** Real-time applications, latency-critical

```json
{
  "storage_backend": "qdrant",
  "qdrant_url": "http://localhost:6333",
  "qdrant_pool_size": 15,
  "qdrant_prefer_grpc": true,
  "retrieval_timeout_ms": 200,
  "performance": {
    "parallel_embeddings": true,
    "parallel_workers": 12,
    "gpu_enabled": true,
    "hybrid_search": false
  },
  "embedding_batch_size": 128,
  "embedding_cache_enabled": true,
  "search": {
    "hybrid_search": false,
    "retrieval_gate_enabled": false,
    "query_expansion_enabled": false
  }
}
```

**Characteristics:**
- Semantic search only (faster than hybrid)
- Large connection pool
- Aggressive caching
- Short timeout (200ms)
- Disabled features that add latency

### Privacy-Focused

**Use Case:** Sensitive codebases, compliance requirements

```json
{
  "storage_backend": "qdrant",
  "qdrant_url": "http://localhost:6333",
  "analytics": {
    "usage_tracking": false,
    "usage_pattern_analytics": false
  },
  "memory": {
    "auto_pruning": true,
    "pruning_schedule": "0 */6 * * *",
    "session_state_ttl_hours": 24
  },
  "search": {
    "cross_project_enabled": false
  },
  "advanced": {
    "input_validation": true
  }
}
```

**Characteristics:**
- No usage tracking
- Aggressive pruning (every 6 hours)
- Short TTL (24 hours)
- No cross-project search
- Strict input validation

### Resource-Constrained (Low Memory/CPU)

**Use Case:** Laptops, VMs with limited resources

```json
{
  "storage_backend": "qdrant",
  "qdrant_url": "http://localhost:6333",
  "performance": {
    "parallel_embeddings": false,
    "force_cpu": true,
    "gpu_enabled": false,
    "hybrid_search": false
  },
  "embedding_batch_size": 16,
  "max_query_context_tokens": 4000,
  "indexing": {
    "auto_index_size_threshold": 200,
    "git_indexing": false
  },
  "search": {
    "query_expansion_enabled": false
  }
}
```

**Characteristics:**
- Single-threaded
- CPU-only
- Small batches
- Limited context
- No git indexing

---

## Troubleshooting Misconfigurations

### Silent Failures

**Symptom:** Feature doesn't work, no error message

**Common Causes:**

1. **Dependent feature disabled**
   ```json
   {
     "analytics": {
       "usage_tracking": false,
       "usage_pattern_analytics": true
     }
   }
   ```
   **Fix:** Enable `usage_tracking=true`

2. **Conflicting options**
   ```json
   {
     "performance": {
       "gpu_enabled": true,
       "force_cpu": true
     }
   }
   ```
   **Fix:** Choose one: `gpu_enabled=true, force_cpu=false` OR `gpu_enabled=false, force_cpu=true`

3. **Invalid weight sum**
   ```json
   {
     "ranking_weight_similarity": 0.7,
     "ranking_weight_recency": 0.2,
     "ranking_weight_usage": 0.2
   }
   ```
   **Fix:** Ensure weights sum to 1.0: `0.6 + 0.2 + 0.2 = 1.0`

### Validation Errors

The server validates configuration on startup. Common errors:

**Error:** "ranking weights must sum to 1.0"
```json
{
  "ranking_weight_similarity": 0.5,
  "ranking_weight_recency": 0.3,
  "ranking_weight_usage": 0.3
}
```
**Fix:** `0.5 + 0.3 + 0.2 = 1.0`

**Error:** "auto_index_on_startup requires auto_index_enabled=true"
```json
{
  "indexing": {
    "auto_index_enabled": false,
    "auto_index_on_startup": true
  }
}
```
**Fix:** Enable parent feature: `auto_index_enabled=true`

**Error:** "hybrid_search_alpha must be between 0.0 and 1.0"
```json
{
  "hybrid_search_alpha": 1.5
}
```
**Fix:** Use valid range: `0.0 <= alpha <= 1.0`

### Performance Issues

**Slow Indexing:**
1. Check `performance.parallel_embeddings=true`
2. Increase `performance.parallel_workers` (2-3x CPU cores)
3. Enable `embedding_cache_enabled=true`
4. Increase `embedding_batch_size` (64-128)

**Slow Searches:**
1. Reduce `retrieval_timeout_ms` to fail fast
2. Disable `search.hybrid_search` (semantic-only is faster)
3. Disable `search.query_expansion_enabled`
4. Increase `qdrant_pool_size` for concurrent queries
5. Enable `qdrant_prefer_grpc=true`

**High Memory Usage:**
1. Reduce `embedding_batch_size` (16-32)
2. Reduce `max_query_context_tokens` (4000)
3. Disable `performance.parallel_embeddings`
4. Reduce `performance.parallel_workers`

### Connection Issues

**Qdrant connection failed:**
```bash
# Check Qdrant is running
curl http://localhost:6333/health

# Check configuration
python -m src.cli status

# Restart Qdrant
docker-compose restart
```

**Configuration:**
```json
{
  "qdrant_url": "http://localhost:6333",
  "qdrant_pool_timeout": 10.0
}
```

---

## Migration from Legacy Configuration

**DEPRECATED in v4.0:** Flat feature flags will be removed in v5.0.0.

### Legacy to Feature Group Mapping

| Legacy Flag | New Feature Group Option |
|-------------|-------------------------|
| `enable_parallel_embeddings` | `performance.parallel_embeddings` |
| `embedding_parallel_workers` | `performance.parallel_workers` |
| `enable_importance_scoring` | `performance.importance_scoring` |
| `enable_gpu` | `performance.gpu_enabled` |
| `force_cpu` | `performance.force_cpu` |
| `enable_hybrid_search` | `search.hybrid_search` |
| `enable_retrieval_gate` | `search.retrieval_gate_enabled` |
| `enable_cross_project_search` | `search.cross_project_enabled` |
| `enable_query_expansion` | `search.query_expansion_enabled` |
| `enable_usage_tracking` | `analytics.usage_tracking` |
| `enable_usage_pattern_analytics` | `analytics.usage_pattern_analytics` |
| `enable_auto_pruning` | `memory.auto_pruning` |
| `enable_conversation_tracking` | `memory.conversation_tracking` |
| `enable_proactive_suggestions` | `memory.proactive_suggestions` |
| `enable_file_watcher` | `indexing.file_watcher` |
| `auto_index_enabled` | `indexing.auto_index_enabled` |
| `auto_index_on_startup` | `indexing.auto_index_on_startup` |
| `enable_git_indexing` | `indexing.git_indexing` |
| `enable_multi_repository` | `advanced.multi_repository` |
| `allow_rust_fallback` | `advanced.rust_fallback` |
| `enable_input_validation` | `advanced.input_validation` |
| `read_only_mode` | `advanced.read_only_mode` |

### Migration Example

**Old Configuration (DEPRECATED):**
```json
{
  "enable_parallel_embeddings": true,
  "embedding_parallel_workers": 4,
  "enable_hybrid_search": true,
  "enable_file_watcher": true,
  "auto_index_enabled": true,
  "enable_usage_tracking": true
}
```

**New Configuration (v4.0+):**
```json
{
  "performance": {
    "parallel_embeddings": true,
    "parallel_workers": 4,
    "hybrid_search": true
  },
  "indexing": {
    "file_watcher": true,
    "auto_index_enabled": true
  },
  "analytics": {
    "usage_tracking": true
  }
}
```

**Migration Steps:**

1. **Backup current config:**
   ```bash
   cp ~/.claude-rag/config.json ~/.claude-rag/config.json.backup
   ```

2. **Convert to feature groups** (see mapping above)

3. **Test configuration:**
   ```bash
   python -m src.cli validate-install
   ```

4. **Check for deprecation warnings:**
   ```bash
   python -m src.cli status
   # Look for "DEPRECATION WARNING" in logs
   ```

**Note:** Legacy flags still work in v4.0 but will log deprecation warnings. They will be removed in v5.0.0.

---

## Complete Options Reference

### Alphabetical List (All 150+ Options)

**Core Settings (2):**
- `server_name` - string, default: "claude-memory-rag"
- `log_level` - string, default: "INFO"

**Storage (11):**
- `storage_backend` - string, default: "qdrant"
- `qdrant_url` - string, default: "http://localhost:6333"
- `qdrant_api_key` - string, default: null
- `qdrant_collection_name` - string, default: "memory"
- `qdrant_pool_size` - int, default: 5
- `qdrant_pool_min_size` - int, default: 1
- `qdrant_pool_timeout` - float, default: 10.0
- `qdrant_pool_recycle` - int, default: 3600
- `qdrant_prefer_grpc` - bool, default: false
- `qdrant_health_check_interval` - int, default: 60
- `sqlite_path` - string, default: "~/.claude-rag/metadata.db"

**Embeddings (6):**
- `embedding_model` - string, default: "all-MiniLM-L6-v2"
- `embedding_batch_size` - int, default: 32
- `embedding_cache_enabled` - bool, default: true
- `embedding_cache_path` - string, default: "~/.claude-rag/embedding_cache.db"
- `embedding_cache_ttl_days` - int, default: 30
- `max_query_context_tokens` - int, default: 8000

**Performance Features (7):**
- `performance.parallel_embeddings` - bool, default: true
- `performance.parallel_workers` - int, default: null (auto-detect)
- `performance.hybrid_search` - bool, default: true
- `performance.importance_scoring` - bool, default: true
- `performance.gpu_enabled` - bool, default: true
- `performance.gpu_memory_fraction` - float, default: 0.8
- `performance.force_cpu` - bool, default: false

**Search Features (10):**
- `search.hybrid_search` - bool, default: true
- `search.retrieval_gate_enabled` - bool, default: true
- `search.retrieval_gate_threshold` - float, default: 0.8
- `search.cross_project_enabled` - bool, default: true
- `search.cross_project_default_mode` - string, default: "current"
- `search.query_expansion_enabled` - bool, default: true
- `search.query_expansion_synonyms` - bool, default: true
- `search.query_expansion_code_context` - bool, default: true
- `search.query_expansion_max_synonyms` - int, default: 2
- `search.query_expansion_max_context_terms` - int, default: 3

**Analytics Features (3):**
- `analytics.usage_tracking` - bool, default: true
- `analytics.usage_pattern_analytics` - bool, default: true
- `analytics.usage_analytics_retention_days` - int, default: 90

**Memory Features (7):**
- `memory.auto_pruning` - bool, default: true
- `memory.pruning_schedule` - string, default: "0 2 * * *"
- `memory.session_state_ttl_hours` - int, default: 48
- `memory.conversation_tracking` - bool, default: true
- `memory.conversation_session_timeout_minutes` - int, default: 30
- `memory.proactive_suggestions` - bool, default: true
- `memory.proactive_suggestions_threshold` - float, default: 0.90

**Indexing Features (16):**
- `indexing.file_watcher` - bool, default: true
- `indexing.watch_debounce_ms` - int, default: 1000
- `indexing.auto_index_enabled` - bool, default: true
- `indexing.auto_index_on_startup` - bool, default: true
- `indexing.auto_index_size_threshold` - int, default: 500
- `indexing.auto_index_recursive` - bool, default: true
- `indexing.auto_index_show_progress` - bool, default: true
- `indexing.auto_index_exclude_patterns` - list, default: [see above]
- `indexing.git_indexing` - bool, default: true
- `indexing.git_index_commit_count` - int, default: 1000
- `indexing.git_index_branches` - string, default: "current"
- `indexing.git_index_tags` - bool, default: true
- `indexing.git_index_diffs` - bool, default: true
- `watch_debounce_ms` - int, default: 1000 (also in indexing group)
- `git_auto_size_threshold_mb` - int, default: 500
- `git_diff_size_limit_kb` - int, default: 10

**Advanced Features (6):**
- `advanced.multi_repository` - bool, default: true
- `advanced.multi_repo_max_parallel` - int, default: 3
- `advanced.rust_fallback` - bool, default: true
- `advanced.warn_on_degradation` - bool, default: true
- `advanced.read_only_mode` - bool, default: false
- `advanced.input_validation` - bool, default: true

**Performance Tuning (3):**
- `retrieval_timeout_ms` - int, default: 500
- `max_memory_size_bytes` - int, default: 10240
- `usage_batch_size` - int, default: 100
- `usage_flush_interval_seconds` - int, default: 60

**Ranking and Scoring (10):**
- `ranking_weight_similarity` - float, default: 0.6
- `ranking_weight_recency` - float, default: 0.2
- `ranking_weight_usage` - float, default: 0.2
- `recency_decay_halflife_days` - float, default: 7.0
- `importance_complexity_weight` - float, default: 1.0
- `importance_usage_weight` - float, default: 1.0
- `importance_criticality_weight` - float, default: 1.0
- `conversation_query_history_size` - int, default: 5
- `query_expansion_similarity_threshold` - float, default: 0.7
- `deduplication_fetch_multiplier` - int, default: 3

**Hybrid Search (4):**
- `hybrid_search_alpha` - float, default: 0.5
- `hybrid_fusion_method` - string, default: "weighted"
- `bm25_k1` - float, default: 1.5
- `bm25_b` - float, default: 0.75

**File Paths (3):**
- `cross_project_opt_in_file` - string, default: "~/.claude-rag/cross_project_consent.json"
- `repository_storage_path` - string, default: "~/.claude-rag/repositories.json"
- `workspace_storage_path` - string, default: "~/.claude-rag/workspaces.json"

**Feature Level Preset (1):**
- `feature_level` - string, default: null (options: "basic", "advanced", "experimental")

**Legacy Flags (46 - DEPRECATED, use feature groups instead):**
See [Migration from Legacy Configuration](#migration-from-legacy-configuration)

---

## Environment Variable Reference

All options can be set via environment variables with the `CLAUDE_RAG_` prefix.

### Feature Group Environment Variables

Use double underscores (`__`) to separate group from option:

```bash
# Performance
CLAUDE_RAG_PERFORMANCE__PARALLEL_EMBEDDINGS=true
CLAUDE_RAG_PERFORMANCE__PARALLEL_WORKERS=8
CLAUDE_RAG_PERFORMANCE__GPU_ENABLED=true

# Search
CLAUDE_RAG_SEARCH__HYBRID_SEARCH=true
CLAUDE_RAG_SEARCH__RETRIEVAL_GATE_ENABLED=true
CLAUDE_RAG_SEARCH__RETRIEVAL_GATE_THRESHOLD=0.85

# Indexing
CLAUDE_RAG_INDEXING__AUTO_INDEX_ENABLED=true
CLAUDE_RAG_INDEXING__FILE_WATCHER=true

# Analytics
CLAUDE_RAG_ANALYTICS__USAGE_TRACKING=true
CLAUDE_RAG_ANALYTICS__USAGE_PATTERN_ANALYTICS=true

# Memory
CLAUDE_RAG_MEMORY__AUTO_PRUNING=true
CLAUDE_RAG_MEMORY__SESSION_STATE_TTL_HOURS=48

# Advanced
CLAUDE_RAG_ADVANCED__MULTI_REPOSITORY=true
CLAUDE_RAG_ADVANCED__INPUT_VALIDATION=true
```

### Core Environment Variables

```bash
# Server
CLAUDE_RAG_SERVER_NAME=claude-memory-rag
CLAUDE_RAG_LOG_LEVEL=INFO

# Storage
CLAUDE_RAG_STORAGE_BACKEND=qdrant
CLAUDE_RAG_QDRANT_URL=http://localhost:6333
CLAUDE_RAG_QDRANT_API_KEY=your-key-here

# Embeddings
CLAUDE_RAG_EMBEDDING_MODEL=all-MiniLM-L6-v2
CLAUDE_RAG_EMBEDDING_BATCH_SIZE=32
```

---

## Summary

This guide documented **150+ configuration options** across:
- 2 core settings
- 11 storage options
- 6 embedding options
- 7 performance features
- 10 search features
- 3 analytics features
- 7 memory features
- 16 indexing features
- 6 advanced features
- 20+ performance tuning options
- 46 deprecated legacy flags (still supported)

**Key Takeaways:**

1. **Use JSON config** (`~/.claude-rag/config.json`) for persistent settings
2. **Use feature level presets** for quick setup ("basic", "advanced", "experimental")
3. **Validate configuration** with `python -m src.cli validate-install`
4. **Migrate legacy flags** to feature groups (legacy support ends in v5.0.0)
5. **Check for conflicts** - ensure dependent features are enabled
6. **Monitor performance** - tune based on your workload

**Next Steps:**
- [SETUP.md](SETUP.md) - Installation and setup
- [USAGE.md](USAGE.md) - How to use all features
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) - Common issues and solutions
- [PERFORMANCE.md](PERFORMANCE.md) - Performance benchmarks and tuning

---

**Questions?** See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) or check the [GitHub Issues](https://github.com/yourorg/claude-memory-server/issues).
