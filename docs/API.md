# API Reference

**Last Updated:** November 18, 2025
**Version:** 4.0 (Production-Ready with Advanced Features)

---

## Overview

The Claude Memory RAG Server exposes tools through the Model Context Protocol (MCP). All tools are accessible to Claude via MCP tool calls.

**Total Tools:** 16 MCP tools + 28 CLI commands

### Available MCP Tools

| Tool Name | Purpose | Category |
|-----------|---------|----------|
| `store_memory` | Store a new memory | Memory Management |
| `retrieve_memories` | Search memories by query | Memory Management |
| `list_memories` | Browse and filter memories | Memory Management |
| `update_memory` | Update an existing memory | Memory Management |
| `get_memory_by_id` | Get a memory by ID | Memory Management |
| `delete_memory` | Delete a memory by ID | Memory Management |
| `get_status` | Get system statistics | System |
| `show_context` | Debug context (dev only) | System |
| `search_code` | Semantic code search with hybrid mode | Code Intelligence |
| `index_codebase` | Index code files | Code Intelligence |
| `find_similar_code` | Find similar code snippets | Code Intelligence |
| `search_all` | Search all indexed content | Search |
| `search_all_projects` | Cross-project code search | Multi-Project |
| `opt_in_cross_project` | Enable cross-project search | Multi-Project |
| `opt_out_cross_project` | Disable cross-project search | Multi-Project |
| `list_opted_in_projects` | List projects with cross-search enabled | Multi-Project |
| `ingest_docs` | Ingest documentation files | Documentation |
| `get_performance_metrics` | Get current performance snapshot | Performance Monitoring |
| `get_active_alerts` | Get active system alerts | Performance Monitoring |
| `get_health_score` | Get overall health score (0-100) | Performance Monitoring |
| `get_capacity_forecast` | Get capacity planning forecast | Performance Monitoring |
| `resolve_alert` | Mark an alert as resolved | Performance Monitoring |
| `get_weekly_report` | Get comprehensive weekly health report | Performance Monitoring |

**Note:** Additional specialized retrieval tools are available via the SpecializedRetrievalTools class (retrieve_preferences, retrieve_project_context, retrieve_session_state) and dependency tracking tools (get_file_dependencies, get_file_dependents, find_dependency_path, get_dependency_stats) are available via the server API.

---

## Memory Management Tools

### store_memory

Store a new memory with automatic classification.

**Input Schema:**
```json
{
  "content": "string (required, 1-50000 chars)",
  "category": "preference|fact|event|workflow|context (required)",
  "scope": "global|project (default: global)",
  "project_name": "string (optional)",
  "importance": "float 0.0-1.0 (default: 0.5)",
  "tags": ["string"] (optional),
  "metadata": {} (optional),
  "context_level": "USER_PREFERENCE|PROJECT_CONTEXT|SESSION_STATE (optional, auto-detected)"
}
```

**Example Request:**
```json
{
  "content": "I prefer Python over JavaScript for backend development",
  "category": "preference",
  "scope": "global",
  "importance": 0.8,
  "tags": ["python", "backend", "languages"]
}
```

**Response:**
```json
{
  "memory_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "stored",
  "context_level": "USER_PREFERENCE"
}
```

**Validation:**
- Content checked for injection patterns (SQL, prompt, command)
- Null bytes and control characters removed
- Size limited to 50KB
- Metadata sanitized

---

### retrieve_memories

Search memories using vector similarity.

**Input Schema:**
```json
{
  "query": "string (required, 1-1000 chars)",
  "limit": "integer 1-100 (default: 5)",
  "context_level": "USER_PREFERENCE|PROJECT_CONTEXT|SESSION_STATE (optional)",
  "scope": "global|project (optional)",
  "project_name": "string (optional)",
  "category": "preference|fact|event|workflow|context (optional)",
  "min_importance": "float 0.0-1.0 (default: 0.0)",
  "tags": ["string"] (optional)
}
```

**Example Request:**
```json
{
  "query": "Python preferences for data science",
  "limit": 3,
  "context_level": "USER_PREFERENCE",
  "min_importance": 0.5
}
```

**Response:**
```json
{
  "results": [
    {
      "memory_id": "550e8400-...",
      "content": "I prefer pandas over numpy for data analysis",
      "category": "preference",
      "context_level": "USER_PREFERENCE",
      "importance": 0.8,
      "score": 0.92,
      "created_at": "2025-11-16T12:00:00Z"
    },
    {
      "memory_id": "660f9511-...",
      "content": "Use seaborn for visualization in data science projects",
      "category": "preference",
      "context_level": "USER_PREFERENCE",
      "importance": 0.7,
      "score": 0.87,
      "created_at": "2025-11-16T11:30:00Z"
    }
  ],
  "count": 2
}
```

---

### retrieve_preferences

Specialized tool to retrieve only USER_PREFERENCE level memories.

**Input Schema:**
```json
{
  "query": "string (required)",
  "limit": "integer (default: 5)"
}
```

**Example:**
```json
{
  "query": "coding style preferences"
}
```

**Note:** Automatically filters to `context_level: USER_PREFERENCE`

---

### retrieve_project_context

Specialized tool to retrieve only PROJECT_CONTEXT level memories.

**Input Schema:**
```json
{
  "query": "string (required)",
  "limit": "integer (default: 5)",
  "project_name": "string (optional)"
}
```

**Example:**
```json
{
  "query": "API authentication",
  "project_name": "my-web-app"
}
```

---

### retrieve_session_state

Specialized tool to retrieve only SESSION_STATE level memories.

**Input Schema:**
```json
{
  "query": "string (required)",
  "limit": "integer (default: 5)"
}
```

**Example:**
```json
{
  "query": "current task progress"
}
```

---

### list_memories

Browse and filter memories without semantic search. Useful for listing memories by category, tags, importance, or date range.

**Input Schema:**
```json
{
  "category": "string (optional: 'FACT', 'PREFERENCE', 'PROJECT_CONTEXT', 'SESSION_STATE')",
  "context_level": "string (optional: 'CORE_IDENTITY', 'PROJECT_SPECIFIC', 'CONVERSATION')",
  "scope": "string (optional: 'global', 'project')",
  "project_name": "string (optional)",
  "tags": "array of strings (optional, matches ANY tag)",
  "min_importance": "float (optional, 0.0-1.0, default: 0.0)",
  "max_importance": "float (optional, 0.0-1.0, default: 1.0)",
  "date_from": "string (optional, ISO format)",
  "date_to": "string (optional, ISO format)",
  "sort_by": "string (optional: 'created_at', 'updated_at', 'importance', default: 'created_at')",
  "sort_order": "string (optional: 'asc', 'desc', default: 'desc')",
  "limit": "integer (optional, 1-100, default: 20)",
  "offset": "integer (optional, default: 0)"
}
```

**Examples:**

List all high-importance preferences:
```json
{
  "category": "PREFERENCE",
  "min_importance": 0.7,
  "sort_by": "importance",
  "sort_order": "desc",
  "limit": 50
}
```

List recent project-specific memories:
```json
{
  "context_level": "PROJECT_SPECIFIC",
  "project_name": "my-app",
  "date_from": "2025-11-01T00:00:00Z",
  "sort_by": "created_at",
  "sort_order": "desc"
}
```

List memories with pagination:
```json
{
  "limit": 20,
  "offset": 40
}
```

**Response:**
```json
{
  "memories": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "content": "User prefers tabs over spaces",
      "category": "PREFERENCE",
      "importance": 0.8,
      "tags": ["coding-style"],
      "created_at": "2025-11-18T10:00:00Z",
      "updated_at": "2025-11-18T10:00:00Z"
    }
  ],
  "total_count": 150,
  "returned_count": 20,
  "offset": 0,
  "limit": 20,
  "has_more": true
}
```

---

### update_memory

Update an existing memory. Supports partial updates - only provide fields you want to change.

**Input Schema:**
```json
{
  "memory_id": "string (required, UUID format)",
  "content": "string (optional, 1-50000 characters)",
  "category": "string (optional: 'FACT', 'PREFERENCE', 'PROJECT_CONTEXT', 'SESSION_STATE')",
  "importance": "float (optional, 0.0-1.0)",
  "tags": "array of strings (optional)",
  "metadata": "object (optional)",
  "context_level": "string (optional: 'CORE_IDENTITY', 'PROJECT_SPECIFIC', 'CONVERSATION')",
  "regenerate_embedding": "boolean (optional, default: true)"
}
```

**Examples:**

Update just the content:
```json
{
  "memory_id": "550e8400-e29b-41d4-a716-446655440000",
  "content": "User prefers 4 spaces for indentation (not tabs)"
}
```

Update importance and tags:
```json
{
  "memory_id": "550e8400-e29b-41d4-a716-446655440000",
  "importance": 0.95,
  "tags": ["coding-style", "high-priority"]
}
```

Update without regenerating embedding (faster):
```json
{
  "memory_id": "550e8400-e29b-41d4-a716-446655440000",
  "importance": 0.9,
  "regenerate_embedding": false
}
```

**Response:**
```json
{
  "status": "updated",
  "updated_fields": ["content", "importance"],
  "embedding_regenerated": true,
  "updated_at": "2025-11-18T10:30:00Z"
}
```

---

### get_memory_by_id

Retrieve a specific memory by its ID.

**Input Schema:**
```json
{
  "memory_id": "string (required, UUID format)"
}
```

**Example:**
```json
{
  "memory_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Response (success):**
```json
{
  "status": "success",
  "memory": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "content": "User prefers tabs over spaces",
    "category": "PREFERENCE",
    "importance": 0.8,
    "tags": ["coding-style"],
    "metadata": {},
    "context_level": "CORE_IDENTITY",
    "scope": "global",
    "created_at": "2025-11-18T10:00:00Z",
    "updated_at": "2025-11-18T10:00:00Z"
  }
}
```

**Response (not found):**
```json
{
  "status": "not_found",
  "message": "Memory 550e8400-e29b-41d4-a716-446655440000 not found"
}
```

---

### delete_memory

Delete a memory by its ID.

**Input Schema:**
```json
{
  "memory_id": "string (required, UUID format)"
}
```

**Example:**
```json
{
  "memory_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Response:**
```json
{
  "deleted": true,
  "memory_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

---

## Code Intelligence Tools

### search_code

Semantic search across indexed code with hybrid search support (BM25 + vector).

**Input Schema:**
```json
{
  "query": "string (required)",
  "project_name": "string (optional, defaults to current project)",
  "limit": "integer 1-50 (default: 10)",
  "file_pattern": "string (optional, e.g., '*/auth/*')",
  "language": "python|javascript|typescript|java|go|rust (optional)",
  "search_mode": "semantic|keyword|hybrid (default: semantic)"
}
```

**Search Modes:**
- **semantic**: Vector similarity search only (best for concept matching)
- **keyword**: BM25 keyword search only (best for exact terms)
- **hybrid**: Combines both with configurable fusion (best for mixed queries)

**Example Request:**
```json
{
  "query": "user authentication and login logic",
  "project_name": "my-web-app",
  "limit": 5,
  "language": "python"
}
```

**Response:**
```json
{
  "results": [
    {
      "file_path": "src/auth/handlers.py",
      "start_line": 45,
      "end_line": 67,
      "unit_type": "function",
      "unit_name": "login",
      "signature": "async def login(request: Request) -> Response",
      "language": "python",
      "score": 0.89,
      "matched_keywords": ["login", "authentication"],
      "content": "async def login(request: Request) -> Response:\n    ..."
    },
    {
      "file_path": "src/auth/middleware.py",
      "start_line": 12,
      "end_line": 28,
      "unit_type": "function",
      "unit_name": "authenticate_user",
      "signature": "def authenticate_user(token: str) -> User",
      "language": "python",
      "score": 0.85,
      "matched_keywords": ["authenticate", "user"],
      "content": "def authenticate_user(token: str) -> User:\n    ..."
    }
  ],
  "count": 2,
  "search_time_ms": 12,
  "interpretation": "Excellent match - results highly relevant to query"
}
```

**Quality Indicators:**
- `matched_keywords`: Keywords from query found in results (helps explain why results matched)
- `interpretation`: Human-readable quality assessment based on scores
  - "Excellent match" (avg score >0.8)
  - "Good match" (avg score 0.6-0.8)
  - "Weak match" (avg score <0.6)
  - Custom suggestions for zero results

**Supported Languages:**
- Python (.py)
- JavaScript (.js, .jsx)
- TypeScript (.ts, .tsx)
- Java (.java)
- Go (.go)
- Rust (.rs)
- Ruby (.rb)
- Swift (.swift)
- Kotlin (.kt, .kts)
- C (.c, .h)
- C++ (.cpp, .hpp, .cc, .hh)
- C# (.cs)
- SQL (.sql)

**Supported Config Files:**
- JSON (.json)
- YAML (.yaml, .yml)
- TOML (.toml)

**Total:** 15 file formats supported

---

### index_codebase

Index code files for semantic search.

**Input Schema:**
```json
{
  "directory_path": "string (required, absolute path)",
  "project_name": "string (optional, defaults to directory name)",
  "recursive": "boolean (default: true)"
}
```

**Example Request:**
```json
{
  "directory_path": "/Users/me/projects/my-app/src",
  "project_name": "my-app",
  "recursive": true
}
```

**Response:**
```json
{
  "status": "completed",
  "files_indexed": 29,
  "semantic_units_extracted": 175,
  "indexing_time_seconds": 2.99,
  "project_name": "my-app"
}
```

**Process:**
1. Scans directory for supported files
2. Checks file hashes for changes (incremental)
3. Parses files with Rust tree-sitter (1-6ms each)
4. Extracts functions, classes, methods
5. Generates embeddings
6. Stores in vector database

**Performance:** ~2.45 files/second

---

### get_file_dependencies

Get imports and dependencies for a file.

**Input Schema:**
```json
{
  "file_path": "string (required, relative path)",
  "project_name": "string (optional)",
  "transitive": "boolean (default: false)"
}
```

**Example Request:**
```json
{
  "file_path": "src/auth/handlers.py",
  "transitive": false
}
```

**Response:**
```json
{
  "file_path": "src/auth/handlers.py",
  "direct_dependencies": [
    "src/auth/models.py",
    "src/database/connection.py",
    "fastapi"
  ],
  "transitive_dependencies": [],
  "import_count": 3
}
```

**With transitive=true:**
```json
{
  "file_path": "src/auth/handlers.py",
  "direct_dependencies": ["src/auth/models.py", "..."],
  "transitive_dependencies": [
    "src/database/connection.py",
    "src/config.py"
  ],
  "import_count": 5
}
```

---

### get_file_dependents

Get files that import/depend on this file (reverse dependencies).

**Input Schema:**
```json
{
  "file_path": "string (required, relative path)",
  "project_name": "string (optional)",
  "transitive": "boolean (default: false)"
}
```

**Example Request:**
```json
{
  "file_path": "src/auth/models.py"
}
```

**Response:**
```json
{
  "file_path": "src/auth/models.py",
  "direct_dependents": [
    "src/auth/handlers.py",
    "src/auth/middleware.py",
    "src/api/routes.py"
  ],
  "transitive_dependents": [],
  "dependent_count": 3
}
```

---

### find_dependency_path

Find the import path between two files.

**Input Schema:**
```json
{
  "source_file": "string (required)",
  "target_file": "string (required)",
  "project_name": "string (optional)"
}
```

**Example Request:**
```json
{
  "source_file": "src/api/routes.py",
  "target_file": "src/database/connection.py"
}
```

**Response:**
```json
{
  "path_found": true,
  "path": [
    "src/api/routes.py",
    "src/auth/handlers.py",
    "src/database/connection.py"
  ],
  "path_length": 3
}
```

**No Path:**
```json
{
  "path_found": false,
  "message": "No dependency path exists between these files"
}
```

---

### get_dependency_stats

Get dependency statistics and detect circular dependencies.

**Input Schema:**
```json
{
  "project_name": "string (optional)"
}
```

**Response:**
```json
{
  "total_files": 45,
  "files_with_dependencies": 38,
  "total_dependencies": 127,
  "average_dependencies_per_file": 3.35,
  "circular_dependencies": [
    ["src/module_a.py", "src/module_b.py", "src/module_a.py"]
  ],
  "most_imported_files": [
    {"file": "src/config.py", "import_count": 15},
    {"file": "src/database/connection.py", "import_count": 12}
  ],
  "most_dependent_files": [
    {"file": "src/utils/helpers.py", "dependency_count": 8}
  ]
}
```

---

### get_dependency_graph

Generate a dependency graph visualization in multiple export formats (DOT/Graphviz, JSON/D3.js, or Mermaid).

**Input Schema:**
```json
{
  "project_name": "string (required)",
  "format": "string (optional, default: 'dot', options: 'dot', 'json', 'mermaid')",
  "max_depth": "number (optional, default: unlimited)",
  "file_pattern": "string (optional, glob pattern like '*.py' or 'src/**/*.ts')",
  "language": "string (optional, filter by language like 'python' or 'javascript')",
  "include_metadata": "boolean (optional, default: true)",
  "highlight_circular": "boolean (optional, default: true)"
}
```

**Response:**
```json
{
  "format": "dot",
  "graph_data": "digraph dependencies { ... }",
  "stats": {
    "node_count": 45,
    "edge_count": 127,
    "circular_dependency_count": 2
  },
  "circular_dependencies": [
    ["src/module_a.py", "src/module_b.py", "src/module_a.py"],
    ["src/utils/helper.py", "src/utils/validator.py", "src/utils/helper.py"]
  ]
}
```

**Supported Formats:**

1. **DOT (Graphviz)**: Industry-standard format for graph visualization
   - Renders with Graphviz tools: `dot -Tpng graph.dot -o graph.png`
   - Includes node metadata (file size), circular dependency highlighting (red edges)

2. **JSON (D3.js)**: Web-friendly format compatible with D3.js and other visualization libraries
   - Includes nodes array with metadata (id, label, size, language, last_modified)
   - Includes links array with source/target references
   - Circular dependencies grouped separately

3. **Mermaid**: Modern diagram format that renders in GitHub/GitLab markdown
   - Automatic node labeling with metadata
   - Dashed arrows for circular dependencies
   - Styled nodes for circular dependency highlighting

**Filtering Options:**
- `max_depth`: Limit graph to N levels of dependencies (e.g., 2 = direct + 1 level deep)
- `file_pattern`: Glob pattern to include only matching files (e.g., "src/**/*.py" for Python files in src/)
- `language`: Filter by file extension/language (e.g., "python", "typescript")

**Example Usage:**
```json
{
  "project_name": "my-project",
  "format": "mermaid",
  "max_depth": 3,
  "file_pattern": "src/**/*.py",
  "highlight_circular": true
}
```

---

## Session Management Tools

### start_conversation_session

Start a conversation session for context-aware retrieval.

**Input Schema:**
```json
{
  "session_name": "string (optional, auto-generated if not provided)"
}
```

**Response:**
```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "session_name": "my-session",
  "created_at": "2025-11-17T12:00:00Z",
  "status": "active"
}
```

**Purpose:** Sessions enable conversation-aware retrieval with:
- Query expansion based on conversation history
- Deduplication of previously shown results
- Automatic timeout after 30 minutes of inactivity

---

### end_conversation_session

End an active conversation session.

**Input Schema:**
```json
{
  "session_id": "string (required, UUID)"
}
```

**Response:**
```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "ended",
  "duration_minutes": 45,
  "queries_processed": 12
}
```

---

### list_conversation_sessions

List all active conversation sessions.

**Input Schema:**
```json
{}
```

**Response:**
```json
{
  "active_sessions": [
    {
      "session_id": "550e8400-...",
      "session_name": "my-session",
      "created_at": "2025-11-17T12:00:00Z",
      "last_activity": "2025-11-17T12:15:00Z",
      "queries_processed": 5
    }
  ],
  "count": 1
}
```

---

## System Tools

### get_memory_stats

Get system statistics.

**Input Schema:**
```json
{}
```

**Response:**
```json
{
  "total_memories": 1234,
  "by_category": {
    "preference": 456,
    "fact": 321,
    "event": 234,
    "workflow": 123,
    "context": 100
  },
  "by_context_level": {
    "USER_PREFERENCE": 456,
    "PROJECT_CONTEXT": 567,
    "SESSION_STATE": 211
  },
  "storage_backend": "qdrant",
  "read_only_mode": false,
  "cache_stats": {
    "hits": 1500,
    "misses": 250,
    "hit_rate": 0.857
  }
}
```

---

### show_current_context

Debug tool to show what memories would be retrieved for a query.

**Input Schema:**
```json
{
  "query": "string (optional)"
}
```

**Note:** Development/debugging only

---

## Performance Monitoring Tools (FEAT-022)

### Overview

The Performance Monitoring Dashboard provides real-time metrics visualization, automated alerting, and capacity planning capabilities. These tools enable proactive monitoring and optimization of the Claude Memory RAG Server.

**Key Features:**
- Real-time performance metrics (search latency, cache hit rate, query volume)
- Automated alerting with severity levels (CRITICAL, WARNING, INFO)
- Health scoring (0-100) with component breakdown
- Capacity planning with 7-90 day forecasting
- Weekly health reports with trend analysis

**Use Cases:**
- Monitor system performance and detect degradation
- Plan capacity and resource needs
- Track system health over time
- Identify and resolve performance issues

---

### get_performance_metrics

Get current performance metrics with optional historical comparison.

**Input Schema:**
```json
{
  "include_history_days": "integer 1-30 (default: 1)"
}
```

**Example Request:**
```json
{
  "include_history_days": 7
}
```

**Response:**
```json
{
  "current_metrics": {
    "avg_search_latency_ms": 8.5,
    "p95_search_latency_ms": 12.3,
    "cache_hit_rate": 0.98,
    "index_staleness_ratio": 0.05,
    "queries_per_day": 245.0,
    "avg_results_per_query": 7.2,
    "timestamp": "2025-11-18T10:30:00Z"
  },
  "historical_average": {
    "avg_search_latency_ms": 9.1,
    "p95_search_latency_ms": 13.2,
    "cache_hit_rate": 0.96,
    "index_staleness_ratio": 0.08,
    "queries_per_day": 230.5,
    "avg_results_per_query": 6.8,
    "timestamp": "7-day average"
  }
}
```

**Metrics Explained:**
- **avg_search_latency_ms**: Average search response time
- **p95_search_latency_ms**: 95th percentile latency (worst 5% of queries)
- **cache_hit_rate**: Ratio of cache hits to total requests (0.0-1.0)
- **index_staleness_ratio**: Ratio of stale indices to total indices
- **queries_per_day**: Average daily query volume
- **avg_results_per_query**: Average number of results returned

---

### get_active_alerts

Get active system alerts with optional severity filtering.

**Input Schema:**
```json
{
  "severity_filter": "CRITICAL|WARNING|INFO (optional)",
  "include_snoozed": "boolean (default: false)"
}
```

**Example Request:**
```json
{
  "severity_filter": "CRITICAL"
}
```

**Response:**
```json
{
  "alerts": [
    {
      "alert_id": "550e8400-e29b-41d4-a716-446655440000",
      "metric_name": "p95_search_latency_ms",
      "severity": "CRITICAL",
      "current_value": 85.5,
      "threshold_value": 50.0,
      "message": "P95 search latency exceeded critical threshold",
      "recommendation": "Check database performance and optimize slow queries",
      "triggered_at": "2025-11-18T10:25:00Z",
      "is_snoozed": false
    }
  ],
  "total_alerts": 1,
  "critical_count": 1,
  "warning_count": 0,
  "info_count": 0
}
```

**Severity Levels:**
- **CRITICAL**: Immediate action required
- **WARNING**: Action recommended soon
- **INFO**: Informational, monitor

---

### get_health_score

Get overall system health score (0-100) with component breakdown.

**Input Schema:**
```json
{}
```

**Response:**
```json
{
  "health_score": 87,
  "status": "GOOD",
  "performance_score": 92,
  "quality_score": 85,
  "database_health_score": 88,
  "usage_efficiency_score": 79,
  "total_alerts": 2,
  "critical_alerts": 0,
  "warning_alerts": 2,
  "recommendations": [
    "Consider archiving projects older than 180 days",
    "Cache hit rate is excellent - no action needed"
  ],
  "timestamp": "2025-11-18T10:30:00Z"
}
```

**Health Score Interpretation:**
- **90-100**: Excellent - System performing optimally
- **75-89**: Good - Minor issues, routine maintenance
- **60-74**: Fair - Action recommended to prevent degradation
- **<60**: Poor - Immediate action required

**Component Scores:**
- **performance_score**: Search latency and throughput
- **quality_score**: Result relevance and accuracy
- **database_health_score**: Database size and integrity
- **usage_efficiency_score**: Resource utilization

---

### get_capacity_forecast

Get capacity planning forecast for 7-90 days ahead.

**Input Schema:**
```json
{
  "days_ahead": "integer 7-90 (default: 30)"
}
```

**Example Request:**
```json
{
  "days_ahead": 30
}
```

**Response:**
```json
{
  "forecast_days": 30,
  "database_growth": {
    "current_size_mb": 245.3,
    "projected_size_mb": 312.7,
    "growth_rate_mb_per_day": 2.24,
    "days_until_warning": 731,
    "days_until_critical": 1095,
    "trend": "GROWING",
    "status": "HEALTHY"
  },
  "memory_capacity": {
    "current_memories": 12453,
    "projected_memories": 15234,
    "creation_rate_per_day": 92.7,
    "days_until_warning": 405,
    "days_until_critical": 542,
    "trend": "GROWING",
    "status": "HEALTHY"
  },
  "project_capacity": {
    "current_active_projects": 8,
    "projected_active_projects": 11,
    "project_addition_rate_per_week": 0.75,
    "days_until_warning": 120,
    "days_until_critical": 180,
    "trend": "GROWING",
    "status": "HEALTHY"
  },
  "recommendations": [
    "Database growth is steady - no action needed",
    "Consider archiving projects older than 180 days to optimize"
  ],
  "overall_status": "HEALTHY",
  "timestamp": "2025-11-18T10:30:00Z"
}
```

**Capacity Thresholds:**
- **Database**: WARNING at 1.5GB, CRITICAL at 2GB
- **Memories**: WARNING at 40k, CRITICAL at 50k
- **Projects**: WARNING at 15 active, CRITICAL at 20 active

**Status Levels:**
- **HEALTHY**: No concerns, sufficient capacity
- **WARNING**: Approaching limits, plan action
- **CRITICAL**: Near capacity, immediate action required

**Trend Indicators:**
- **GROWING**: Increasing usage over time
- **STABLE**: Consistent usage
- **DECLINING**: Decreasing usage

---

### resolve_alert

Mark an alert as resolved.

**Input Schema:**
```json
{
  "alert_id": "string (required, UUID format)"
}
```

**Example Request:**
```json
{
  "alert_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Response:**
```json
{
  "alert_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "resolved",
  "resolved_at": "2025-11-18T10:30:00Z",
  "message": "Alert resolved successfully"
}
```

**Use Cases:**
- Mark alerts as resolved after taking action
- Clear false positives
- Acknowledge known issues

---

### get_weekly_report

Get comprehensive weekly health report with trends and analysis.

**Input Schema:**
```json
{}
```

**Response:**
```json
{
  "week_start": "2025-11-11T00:00:00Z",
  "week_end": "2025-11-18T00:00:00Z",
  "overall_health_score": 87,
  "status": "GOOD",
  "metrics_summary": {
    "avg_search_latency_ms": 8.5,
    "p95_search_latency_ms": 12.3,
    "cache_hit_rate": 0.98,
    "total_queries": 1715,
    "total_memories": 12453,
    "active_projects": 8
  },
  "trends": [
    {
      "metric": "avg_search_latency_ms",
      "trend": "IMPROVING",
      "change_percent": -5.2,
      "interpretation": "Search latency improved by 5.2%"
    },
    {
      "metric": "cache_hit_rate",
      "trend": "IMPROVING",
      "change_percent": 2.1,
      "interpretation": "Cache efficiency increased"
    }
  ],
  "notable_events": [
    "No critical alerts this week",
    "Database growth within normal range",
    "Cache performance excellent"
  ],
  "improvements": [
    "Search latency reduced by 5.2%",
    "Cache hit rate improved to 98%"
  ],
  "concerns": [
    "2 projects approaching staleness threshold"
  ],
  "recommendations": [
    "Continue current monitoring practices",
    "Consider re-indexing stale projects"
  ],
  "total_alerts": 2,
  "critical_alerts": 0,
  "warning_alerts": 2,
  "timestamp": "2025-11-18T10:30:00Z"
}
```

**Report Sections:**
- **metrics_summary**: Key metrics for the week
- **trends**: Week-over-week changes with interpretation
- **notable_events**: Significant events or milestones
- **improvements**: Positive changes observed
- **concerns**: Issues requiring attention
- **recommendations**: Actionable next steps

---

## Error Responses

All tools return errors in this format:

```json
{
  "error": {
    "type": "ValidationError|StorageError|ReadOnlyError|SecurityError",
    "message": "Detailed error description",
    "details": {}
  }
}
```

**Common Errors:**

**ValidationError:**
```json
{
  "error": {
    "type": "ValidationError",
    "message": "Potential security threat detected: SQL injection pattern",
    "details": {"pattern": "'; DROP TABLE"}
  }
}
```

**ReadOnlyError:**
```json
{
  "error": {
    "type": "ReadOnlyError",
    "message": "Server is in read-only mode. Write operations are disabled."
  }
}
```

**StorageError:**
```json
{
  "error": {
    "type": "StorageError",
    "message": "Failed to connect to Qdrant: Connection refused"
  }
}
```

---

## Multi-Project Tools

### search_all_projects

Search code across all opted-in projects with consent-based privacy.

**Input Schema:**
```json
{
  "query": "string (required)",
  "limit": "integer 1-50 (default: 10)",
  "file_pattern": "string (optional)",
  "language": "python|javascript|typescript|java|go|rust|c|cpp|csharp|sql (optional)",
  "search_mode": "semantic|keyword|hybrid (default: semantic)"
}
```

**Example Request:**
```json
{
  "query": "user authentication patterns",
  "limit": 10,
  "language": "python"
}
```

**Response:**
```json
{
  "results": [
    {
      "project_name": "web-app",
      "file_path": "src/auth/handlers.py",
      "unit_name": "login",
      "score": 0.92,
      "language": "python",
      "content": "async def login(...)..."
    },
    {
      "project_name": "api-service",
      "file_path": "auth/middleware.py",
      "unit_name": "authenticate",
      "score": 0.88,
      "language": "python",
      "content": "def authenticate(...)..."
    }
  ],
  "count": 2,
  "projects_searched": ["web-app", "api-service"],
  "interpretation": "Found similar authentication patterns across 2 projects"
}
```

**Privacy:** Only searches projects that have been explicitly opted-in via `opt_in_cross_project`. Current project is always searchable.

---

### opt_in_cross_project

Enable cross-project search for a specific project.

**Input Schema:**
```json
{
  "project_name": "string (required)"
}
```

**Example:**
```json
{
  "project_name": "my-web-app"
}
```

**Response:**
```json
{
  "project_name": "my-web-app",
  "opted_in": true,
  "message": "Project 'my-web-app' is now searchable in cross-project queries"
}
```

---

### opt_out_cross_project

Disable cross-project search for a specific project.

**Input Schema:**
```json
{
  "project_name": "string (required)"
}
```

**Response:**
```json
{
  "project_name": "my-web-app",
  "opted_in": false,
  "message": "Project 'my-web-app' removed from cross-project search"
}
```

---

### list_opted_in_projects

List all projects that have cross-project search enabled.

**Input Schema:**
```json
{}
```

**Response:**
```json
{
  "opted_in_projects": [
    "web-app",
    "api-service",
    "mobile-backend"
  ],
  "count": 3
}
```

---

## Advanced Code Intelligence Tools

### find_similar_code

Find similar code snippets based on semantic similarity.

**Input Schema:**
```json
{
  "code_snippet": "string (required, the code to find similar examples of)",
  "project_name": "string (optional)",
  "limit": "integer 1-50 (default: 10)",
  "file_pattern": "string (optional)",
  "language": "string (optional)"
}
```

**Example Request:**
```json
{
  "code_snippet": "async def login(username, password):\n    user = await db.authenticate(username, password)\n    return create_token(user)",
  "limit": 5,
  "language": "python"
}
```

**Response:**
```json
{
  "results": [
    {
      "file_path": "src/auth/handlers.py",
      "unit_name": "login",
      "score": 0.95,
      "confidence_label": "excellent",
      "confidence_display": "95% (excellent)",
      "content": "async def login(...)...",
      "interpretation": "Duplicate or very similar implementation"
    },
    {
      "file_path": "src/admin/auth.py",
      "unit_name": "admin_login",
      "score": 0.82,
      "confidence_label": "good",
      "confidence_display": "82% (good)",
      "content": "async def admin_login(...)...",
      "interpretation": "Similar pattern, different context"
    }
  ],
  "count": 2,
  "interpretation": "Found similar authentication patterns",
  "use_cases": [
    "Duplicate detection (>0.95 similarity)",
    "Pattern discovery (>0.80 similarity)",
    "Code reuse opportunities (<0.80 similarity)"
  ]
}
```

**Similarity Interpretation:**
- **>0.95**: Likely duplicates - consider consolidating
- **0.80-0.95**: Similar patterns - good for reference
- **<0.80**: Related but different - may provide ideas

---

### search_all

Search all indexed content (code + documentation + memories).

**Input Schema:**
```json
{
  "query": "string (required)",
  "limit": "integer 1-100 (default: 10)",
  "content_types": ["code", "docs", "memories"] (optional, default: all)
}
```

**Example:**
```json
{
  "query": "authentication best practices",
  "limit": 10,
  "content_types": ["code", "docs"]
}
```

**Response:**
```json
{
  "results": [
    {
      "type": "code",
      "file_path": "src/auth/handlers.py",
      "score": 0.89,
      "content": "..."
    },
    {
      "type": "docs",
      "file_path": "docs/SECURITY.md",
      "score": 0.85,
      "content": "..."
    }
  ],
  "count": 2,
  "breakdown": {
    "code": 1,
    "docs": 1,
    "memories": 0
  }
}
```

---

## Documentation Tools

### ingest_docs

Ingest and index documentation files (Markdown, text, etc.).

**Input Schema:**
```json
{
  "directory_path": "string (required, absolute path)",
  "project_name": "string (optional)",
  "file_patterns": ["*.md", "*.txt"] (optional, default: *.md)
}
```

**Example:**
```json
{
  "directory_path": "/Users/me/projects/my-app/docs",
  "project_name": "my-app",
  "file_patterns": ["*.md"]
}
```

**Response:**
```json
{
  "status": "completed",
  "files_ingested": 15,
  "chunks_created": 45,
  "indexing_time_seconds": 1.23,
  "project_name": "my-app"
}
```

**Process:**
1. Scans directory for matching file patterns
2. Chunks documents intelligently (preserves structure)
3. Generates embeddings for each chunk
4. Stores in vector database with doc metadata

---

## Project Archival Tools

### Overview

The archival system provides complete project lifecycle management with compression, export/import for portability, and automated scheduling for graceful storage optimization.

**Archival Features:**
- **Compression**: 60-80% storage reduction for archived projects
- **Export/Import**: Portable .tar.gz archives with manifest and README
- **Bulk Operations**: Archive or reactivate multiple projects at once
- **Automatic Scheduling**: Configurable auto-archival based on inactivity
- **CLI Commands**: Full CLI support for all archival operations

### export_project_archive (CLI)

Export an archived project to a portable .tar.gz file for backup, migration, or sharing.

**Usage:**
```bash
# Export with auto-generated filename
python -m src.cli archival export my-project

# Export to specific path
python -m src.cli archival export my-project -o /backups/my-project.tar.gz

# Export without README
python -m src.cli archival export my-project --no-readme
```

**Export Contents:**
- `archive.tar.gz` - Compressed project index and embedding cache
- `manifest.json` - Project metadata, statistics, and compression info
- `README.txt` - Human-readable documentation with import instructions (optional)

**Manifest Schema:**
```json
{
  "project_name": "my-project",
  "archive_version": "1.0",
  "archived_at": "2025-11-18T10:30:00Z",
  "archived_by": "automatic|manual",
  "statistics": {
    "total_files": 1250,
    "total_semantic_units": 8500,
    "total_memories": 342
  },
  "compression_info": {
    "original_size_mb": 125.5,
    "compressed_size_mb": 28.3,
    "compression_ratio": 0.226,
    "savings_percent": 77.4
  },
  "last_activity": {
    "date": "2025-10-01T14:20:00Z",
    "days_inactive": 48,
    "searches_count": 1423,
    "index_updates_count": 67
  }
}
```

**Performance:**
- Export time: ~5-30 seconds (depending on project size)
- Compression ratio: 0.20-0.30 (70-80% savings)

---

### import_project_archive (CLI)

Import a project archive from a portable .tar.gz file, with validation and conflict resolution.

**Usage:**
```bash
# Import with original name
python -m src.cli archival import /path/to/my-project_archive.tar.gz

# Import with custom name
python -m src.cli archival import /path/to/archive.tar.gz -n new-project-name

# Import with conflict overwrite
python -m src.cli archival import /path/to/archive.tar.gz --conflict overwrite
```

**Conflict Resolution Strategies:**
- `skip` (default): Fail if project already exists (safest)
- `overwrite`: Delete existing archive and import new one

**Validation:**
- Archive structure validation (required files present)
- Manifest schema validation (required fields)
- Tar.gz integrity checking
- Automatic project name sanitization

**Import Process:**
1. Extract archive to temporary directory
2. Validate archive structure and manifest
3. Check for conflicts with existing projects
4. Apply conflict resolution strategy if needed
5. Copy archive to destination
6. Update manifest with import metadata

**Performance:**
- Import time: ~5-20 seconds (depending on project size)
- Full roundtrip integrity (export → import → verify)

---

### list_exportable_projects (CLI)

List all archived projects available for export with size and compression statistics.

**Usage:**
```bash
python -m src.cli archival list-exportable
```

**Output:**
```
Exportable Projects
┌──────────────────┬──────────────┬───────────┬─────────────┐
│ Project          │ Archived At  │ Size (MB) │ Compression │
├──────────────────┼──────────────┼───────────┼─────────────┤
│ old-project      │ 2025-09-15   │ 45.23     │ 0.25        │
│ legacy-api       │ 2025-10-01   │ 128.67    │ 0.22        │
│ test-project     │ 2025-11-10   │ 12.45     │ 0.28        │
└──────────────────┴──────────────┴───────────┴─────────────┘

Total: 3 projects (186.35 MB)
```

---

### Additional Archival CLI Commands

**Status and Management:**
```bash
# Show all project states
python -m src.cli archival status

# Archive a project manually
python -m src.cli archival archive my-project

# Reactivate an archived project
python -m src.cli archival reactivate my-project
```

**Programmatic Access:**

While archival tools are primarily CLI-based, you can access them programmatically:

```python
from src.memory.archive_exporter import ArchiveExporter
from src.memory.archive_importer import ArchiveImporter
from src.memory.archive_compressor import ArchiveCompressor
from pathlib import Path

# Setup compressor
compressor = ArchiveCompressor(
    archive_root="~/.claude-rag/archives",
    compression_level=6,
)

# Export a project
exporter = ArchiveExporter(
    archive_compressor=compressor,
    compression_level=6,
)

result = await exporter.export_project_archive(
    project_name="my-project",
    output_path=Path("/backups/my-project.tar.gz"),
    include_readme=True,
)

# Import a project
importer = ArchiveImporter(
    archive_compressor=compressor,
)

result = await importer.import_project_archive(
    archive_path=Path("/backups/my-project.tar.gz"),
    project_name="restored-project",  # Optional custom name
    conflict_resolution="skip",
)

# Validate an archive without importing
validation = importer.validate_archive_file(
    Path("/backups/my-project.tar.gz")
)
print(f"Valid: {validation['valid']}")
print(f"Project: {validation['project_name']}")
print(f"Size: {validation['archive_size_mb']} MB")
```

**Storage Optimization:**

Archival provides significant storage savings:

| Project Size | Active (MB) | Archived (MB) | Savings |
|--------------|-------------|---------------|---------|
| Small (100 files) | 8.5 | 2.1 | 75% |
| Medium (1000 files) | 125.3 | 28.4 | 77% |
| Large (5000 files) | 623.7 | 142.8 | 77% |

**Best Practices:**
- Export projects before long-term archival for external backups
- Use descriptive project names for easier archive management
- Include README in exports for human documentation
- Test import in non-production environment first
- Keep original exports until import is verified

---

## Rate Limits

No rate limits currently enforced. Recommended client-side limits:
- Memory storage: 100 requests/minute
- Memory retrieval: 300 requests/minute
- Code search: 100 requests/minute
- Code indexing: 10 requests/hour

---

## Best Practices

### Memory Storage

1. **Use meaningful content:** Provide clear, descriptive content
2. **Set importance correctly:** 0.0-1.0 scale, default 0.5
3. **Tag appropriately:** Use consistent tags for filtering
4. **Choose correct category:** preference, fact, event, workflow, or context

### Memory Retrieval

1. **Write clear queries:** Use natural language
2. **Use filters:** Narrow down results with context_level, project_name, etc.
3. **Set appropriate limits:** Default 5, max 100
4. **Check scores:** Results with score >0.7 are usually relevant

### Code Search

1. **Be specific:** "authentication logic" vs "code"
2. **Use filters:** Filter by language or file pattern
3. **Index incrementally:** Only changed files are re-indexed
4. **Project scoping:** Use project_name to search specific projects

---

## Programmatic Usage

### Python Example

```python
import asyncio
from src.core.server import MemoryRAGServer

async def main():
    server = MemoryRAGServer()
    await server.initialize()
    
    # Store a memory
    result = await server.store_memory(
        content="I prefer Python for backend APIs",
        category="preference",
        scope="global"
    )
    print(f"Stored: {result['memory_id']}")
    
    # Search memories
    results = await server.retrieve_memories(
        query="backend preferences",
        limit=3
    )
    for memory in results['results']:
        print(f"{memory['score']:.2f}: {memory['content']}")
    
    # Search code
    code_results = await server.search_code(
        query="user authentication",
        language="python",
        limit=5
    )
    for result in code_results['results']:
        print(f"{result['file_path']}:{result['start_line']} - {result['unit_name']}")

asyncio.run(main())
```

---

## CLI Commands Reference

In addition to the 14 MCP tools, the system provides 28 CLI commands for direct system management. See `docs/USAGE.md` for complete CLI reference.

**Categories:**
- **Indexing & Watching** (3 commands): index, watch, auto-tag
- **Project Management** (4 commands): project, repository, workspace, collections
- **Memory Management** (5 commands): memory-browser, consolidate, verify, prune, lifecycle, tags
- **Git Integration** (2 commands): git-index, git-search
- **Health & Monitoring** (3 commands): health, health-monitor, health-dashboard
- **Analytics & Reporting** (3 commands): status, analytics, session-summary
- **Data Management** (4 commands): backup, export, import, archival

**Usage:** `python -m src.cli <command> [options]`

---

**Document Version:** 2.0
**Last Updated:** November 17, 2025
**Status:** Major update with all new MCP tools and CLI commands documented
