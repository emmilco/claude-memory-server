# API Reference

**Last Updated:** November 16, 2025
**Version:** 3.0

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
| `search_code` | Semantic code search | Code Intelligence |
| `index_codebase` | Index code files | Code Intelligence |

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

Semantic search across indexed code.

**Input Schema:**
```json
{
  "query": "string (required)",
  "project_name": "string (optional, defaults to current project)",
  "limit": "integer 1-50 (default: 10)",
  "file_pattern": "string (optional, e.g., '*/auth/*')",
  "language": "python|javascript|typescript|java|go|rust (optional)"
}
```

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
      "content": "def authenticate_user(token: str) -> User:\n    ..."
    }
  ],
  "count": 2,
  "search_time_ms": 12
}
```

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

**Document Version:** 1.0
**Last Updated:** November 16, 2025
