# API Reference

**Last Updated:** November 17, 2025
**Version:** 3.1

---

## Overview

The Claude Memory RAG Server exposes tools through the Model Context Protocol (MCP). All tools are accessible to Claude via MCP tool calls.

### Available Tools

| Tool Name | Purpose | Category |
|-----------|---------|----------|
| `store_memory` | Store a new memory | Memory Management |
| `retrieve_memories` | Search memories by query | Memory Management |
| `retrieve_preferences` | Get user preferences only | Specialized Retrieval |
| `retrieve_project_context` | Get project context only | Specialized Retrieval |
| `retrieve_session_state` | Get session state only | Specialized Retrieval |
| `delete_memory` | Delete a memory by ID | Memory Management |
| `get_memory_stats` | Get statistics | System |
| `show_current_context` | Debug context (dev only) | System |
| `search_code` | Semantic code search with hybrid mode | Code Intelligence |
| `index_codebase` | Index code files | Code Intelligence |
| `get_file_dependencies` | Get file imports/dependencies | Code Intelligence |
| `get_file_dependents` | Get files that import this file | Code Intelligence |
| `find_dependency_path` | Find import path between files | Code Intelligence |
| `get_dependency_stats` | Get dependency statistics | Code Intelligence |
| `start_conversation_session` | Start a conversation session | Session Management |
| `end_conversation_session` | End a conversation session | Session Management |
| `list_conversation_sessions` | List active sessions | Session Management |

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

**Document Version:** 1.1
**Last Updated:** November 17, 2025
