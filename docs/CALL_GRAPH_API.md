# Call Graph API Documentation

**FEAT-059: Structural/Relational Queries**

This document describes the 6 new MCP tools for call graph analysis and structural queries.

---

## Overview

The Call Graph API enables semantic analysis of function relationships and call chains in your codebase. It provides:

- **Function call tracking** - Find what calls a function or what a function calls
- **Call chain discovery** - Trace execution paths between functions
- **Interface implementations** - Find all implementations of interfaces/abstract classes
- **Dependency analysis** - Analyze function and file dependencies
- **Architecture understanding** - Visualize code structure and relationships

**Status:** Production-ready (v4.0)
**Languages Supported:** Python (JavaScript/TypeScript coming soon)

---

## MCP Tools

### 1. `find_callers` - Find Functions Calling a Target

Find all functions that call a specific function, with optional indirect caller discovery.

#### Request Schema

```typescript
{
  function_name: string;        // Required: Function to find callers for
  project_name: string;         // Required: Project context
  include_indirect?: boolean;   // Optional: Include indirect callers (default: false)
  max_depth?: number;           // Optional: Maximum traversal depth (default: 3)
  limit?: number;               // Optional: Maximum results (default: 50)
}
```

#### Response Schema

```typescript
{
  function_name: string;
  project_name: string;
  total_count: number;
  returned_count: number;
  direct_callers: Array<{
    name: string;
    qualified_name: string;
    file_path: string;
    language: string;
    start_line: number;
    end_line: number;
    is_async: boolean;
  }>;
  indirect_callers?: Array<{
    name: string;
    qualified_name: string;
    file_path: string;
    language: string;
    depth: number;              // How many hops away
  }>;
  max_depth: number;
}
```

#### Examples

**Find direct callers:**
```python
result = await server.find_callers(
    function_name="process_payment",
    project_name="my-ecommerce-app",
    include_indirect=False
)

# Response:
{
    "function_name": "process_payment",
    "project_name": "my-ecommerce-app",
    "total_count": 3,
    "returned_count": 3,
    "direct_callers": [
        {
            "name": "checkout",
            "qualified_name": "CheckoutController.checkout",
            "file_path": "/app/controllers/checkout.py",
            "language": "python",
            "start_line": 45,
            "end_line": 78,
            "is_async": True
        },
        {
            "name": "retry_payment",
            "qualified_name": "PaymentService.retry_payment",
            "file_path": "/app/services/payment.py",
            "language": "python",
            "start_line": 120,
            "end_line": 135,
            "is_async": True
        },
        {
            "name": "batch_process",
            "qualified_name": "BatchProcessor.batch_process",
            "file_path": "/app/batch/processor.py",
            "language": "python",
            "start_line": 200,
            "end_line": 250,
            "is_async": False
        }
    ],
    "indirect_callers": [],
    "max_depth": 1
}
```

**Find indirect callers (multi-hop):**
```python
result = await server.find_callers(
    function_name="validate_credit_card",
    project_name="my-ecommerce-app",
    include_indirect=True,
    max_depth=5
)

# Finds:
# - Direct callers: process_payment
# - Indirect callers (depth 2): checkout, retry_payment
# - Indirect callers (depth 3): user_checkout_api, admin_retry_api
```

#### Use Cases

- **Impact analysis** - "What breaks if I change this function?"
- **Refactoring safety** - "Where is this function used?"
- **API usage tracking** - "Who's calling my API endpoint?"
- **Dead code detection** - "Is this function called by anyone?"

---

### 2. `find_callees` - Find Functions Called by a Function

Find all functions called by a specific function, with optional transitive callees.

#### Request Schema

```typescript
{
  function_name: string;        // Required: Function to find callees for
  project_name: string;         // Required: Project context
  include_indirect?: boolean;   // Optional: Include indirect callees (default: false)
  max_depth?: number;           // Optional: Maximum traversal depth (default: 3)
  limit?: number;               // Optional: Maximum results (default: 50)
}
```

#### Response Schema

```typescript
{
  function_name: string;
  project_name: string;
  total_count: number;
  returned_count: number;
  direct_callees: Array<{
    name: string;
    qualified_name: string;
    file_path: string;
    language: string;
    start_line: number;
    end_line: number;
  }>;
  indirect_callees?: Array<{
    name: string;
    qualified_name: string;
    file_path: string;
    language: string;
    depth: number;
  }>;
  max_depth: number;
}
```

#### Examples

**Find what a controller calls:**
```python
result = await server.find_callees(
    function_name="UserController.create_user",
    project_name="my-app",
    include_indirect=False
)

# Response shows direct function calls:
{
    "function_name": "UserController.create_user",
    "total_count": 4,
    "direct_callees": [
        {"qualified_name": "UserService.validate_user_data", ...},
        {"qualified_name": "UserService.save_user", ...},
        {"qualified_name": "Logger.info", ...},
        {"qualified_name": "EmailService.send_welcome_email", ...}
    ]
}
```

**Find full dependency tree:**
```python
result = await server.find_callees(
    function_name="UserController.create_user",
    project_name="my-app",
    include_indirect=True,
    max_depth=5
)

# Finds entire call tree:
# Level 1: UserService.validate_user_data, UserService.save_user, ...
# Level 2: Database.execute_query, ValidationRules.check_email, ...
# Level 3: ConnectionPool.get_connection, RegexMatcher.match, ...
```

#### Use Cases

- **Dependency analysis** - "What does this function depend on?"
- **Performance profiling** - "What expensive operations does this call?"
- **Security auditing** - "Does this call any unsafe functions?"
- **Complexity assessment** - "How deep is this function's call tree?"

---

### 3. `get_call_chain` - Find Call Paths Between Functions

Find all execution paths from one function to another.

#### Request Schema

```typescript
{
  from_function: string;        // Required: Starting function
  to_function: string;          // Required: Target function
  project_name: string;         // Required: Project context
  max_paths?: number;           // Optional: Maximum paths to return (default: 10)
  max_depth?: number;           // Optional: Maximum path length (default: 10)
}
```

#### Response Schema

```typescript
{
  from_function: string;
  to_function: string;
  project_name: string;
  path_count: number;
  paths: Array<{
    path: string[];             // Function names in order
    length: number;             // Number of hops
    call_sites: Array<{         // Detailed call information
      caller_function: string;
      callee_function: string;
      caller_file: string;
      caller_line: number;
    }>;
  }>;
  max_depth: number;
  max_paths: number;
}
```

#### Examples

**Trace how a request reaches the database:**
```python
result = await server.get_call_chain(
    from_function="api_endpoint",
    to_function="Database.execute_query",
    project_name="my-app",
    max_paths=5
)

# Response:
{
    "from_function": "api_endpoint",
    "to_function": "Database.execute_query",
    "path_count": 2,
    "paths": [
        {
            "path": [
                "api_endpoint",
                "UserController.get_user",
                "UserService.find_by_id",
                "UserRepository.query",
                "Database.execute_query"
            ],
            "length": 5,
            "call_sites": [
                {
                    "caller_function": "api_endpoint",
                    "callee_function": "UserController.get_user",
                    "caller_file": "/app/api.py",
                    "caller_line": 45
                },
                # ... more call sites
            ]
        },
        {
            "path": [
                "api_endpoint",
                "CacheService.get_cached",
                "UserRepository.query",
                "Database.execute_query"
            ],
            "length": 4
        }
    ]
}
```

**Debug production issue:**
```python
# Question: "How does invalid input reach the crash point?"
result = await server.get_call_chain(
    from_function="validate_input",
    to_function="process_unsafe_data",
    project_name="production-app"
)

# Shows exact execution path and line numbers
```

#### Use Cases

- **Bug investigation** - "How does data flow from A to B?"
- **Architecture understanding** - "What's the execution flow?"
- **Performance optimization** - "Why is this path so long?"
- **Security analysis** - "Can untrusted input reach this function?"

---

### 4. `find_implementations` - Find Interface Implementations

Find all classes implementing a specific interface, abstract class, or trait.

#### Request Schema

```typescript
{
  interface_name: string;       // Required: Interface to find implementations for
  project_name: string;         // Required: Project context
  language?: string;            // Optional: Filter by language
  limit?: number;               // Optional: Maximum results (default: 50)
}
```

#### Response Schema

```typescript
{
  interface_name: string;
  project_name: string;
  total_count: number;
  implementations: Array<{
    implementation_name: string;
    file_path: string;
    language: string;
    methods: string[];          // Implemented method names
    start_line: number;
    end_line: number;
  }>;
  language_filter?: string;
}
```

#### Examples

**Find all storage implementations:**
```python
result = await server.find_implementations(
    interface_name="Storage",
    project_name="my-app"
)

# Response:
{
    "interface_name": "Storage",
    "total_count": 4,
    "implementations": [
        {
            "implementation_name": "RedisStorage",
            "file_path": "/app/storage/redis.py",
            "language": "python",
            "methods": ["get", "set", "delete", "exists"],
            "start_line": 10,
            "end_line": 85
        },
        {
            "implementation_name": "S3Storage",
            "file_path": "/app/storage/s3.py",
            "language": "python",
            "methods": ["get", "set", "delete", "exists", "list"],
            "start_line": 15,
            "end_line": 120
        },
        {
            "implementation_name": "MemoryStorage",
            "file_path": "/app/storage/memory.py",
            "language": "python",
            "methods": ["get", "set", "delete", "exists", "clear"],
            "start_line": 5,
            "end_line": 45
        },
        {
            "implementation_name": "DatabaseStorage",
            "file_path": "/app/storage/database.py",
            "language": "python",
            "methods": ["get", "set", "delete", "exists", "query"],
            "start_line": 20,
            "end_line": 150
        }
    ]
}
```

**Find Python-specific implementations:**
```python
result = await server.find_implementations(
    interface_name="Serializer",
    project_name="my-app",
    language="python"
)
```

#### Use Cases

- **Polymorphism discovery** - "What implementations exist?"
- **Strategy pattern usage** - "What strategies are available?"
- **Plugin system** - "What plugins are installed?"
- **Testing** - "Which implementations need tests?"

---

### 5. `find_dependencies` - Find File Dependencies

Find all files that a given file depends on (imports/requires).

#### Request Schema

```typescript
{
  file_path: string;            // Required: File to analyze
  project_name: string;         // Required: Project context
  include_transitive?: boolean; // Optional: Include transitive deps (default: false)
  max_depth?: number;           // Optional: Maximum depth (default: 5)
  limit?: number;               // Optional: Maximum results (default: 100)
}
```

#### Response Schema

```typescript
{
  file_path: string;
  project_name: string;
  total_count: number;
  direct_dependencies: Array<{
    file_path: string;
    import_type: string;        // "local", "third_party", "standard_library"
    import_names: string[];     // What was imported
  }>;
  transitive_dependencies?: Array<{
    file_path: string;
    depth: number;
  }>;
  max_depth: number;
}
```

#### Examples

**Find what a module imports:**
```python
result = await server.find_dependencies(
    file_path="/app/services/payment.py",
    project_name="my-app",
    include_transitive=False
)

# Response:
{
    "file_path": "/app/services/payment.py",
    "total_count": 8,
    "direct_dependencies": [
        {
            "file_path": "/app/models/payment.py",
            "import_type": "local",
            "import_names": ["Payment", "PaymentStatus"]
        },
        {
            "file_path": "/app/utils/validation.py",
            "import_type": "local",
            "import_names": ["validate_credit_card"]
        },
        {
            "file_path": "stripe",
            "import_type": "third_party",
            "import_names": ["stripe"]
        }
    ]
}
```

#### Use Cases

- **Build optimization** - "What needs to be bundled?"
- **Circular dependency detection** - "Are there import cycles?"
- **Module cleanup** - "Can I remove this dependency?"
- **Impact analysis** - "What depends on this file?"

---

### 6. `find_dependents` - Find Reverse File Dependencies

Find all files that depend on a given file (reverse dependencies).

#### Request Schema

```typescript
{
  file_path: string;            // Required: File to analyze
  project_name: string;         // Required: Project context
  include_transitive?: boolean; // Optional: Include transitive dependents
  max_depth?: number;           // Optional: Maximum depth (default: 5)
  limit?: number;               // Optional: Maximum results (default: 100)
}
```

#### Response Schema

```typescript
{
  file_path: string;
  project_name: string;
  total_count: number;
  direct_dependents: Array<{
    file_path: string;
    import_names: string[];     // What was imported from this file
  }>;
  transitive_dependents?: Array<{
    file_path: string;
    depth: number;
  }>;
  max_depth: number;
}
```

#### Examples

**Find what uses a utility module:**
```python
result = await server.find_dependents(
    file_path="/app/utils/crypto.py",
    project_name="my-app",
    include_transitive=True,
    max_depth=3
)

# Response shows:
# - Direct dependents: Files importing crypto.py
# - Transitive dependents: Files importing those files (up to depth 3)
```

#### Use Cases

- **Refactoring impact** - "What breaks if I change this file?"
- **API stability** - "How widely used is this module?"
- **Deprecation planning** - "What needs updating?"
- **Testing priority** - "Which tests are most important?"

---

## Error Handling

All tools return structured errors for common failure cases:

### Common Errors

**Function not found:**
```json
{
  "error": "FunctionNotFound",
  "message": "Function 'nonexistent_func' not found in project 'my-app'",
  "function_name": "nonexistent_func",
  "project_name": "my-app"
}
```

**Invalid parameters:**
```json
{
  "error": "ValidationError",
  "message": "function_name cannot be empty",
  "field": "function_name"
}
```

**Storage errors:**
```json
{
  "error": "StorageError",
  "message": "Failed to query call graph: Connection timeout",
  "details": "Qdrant connection timed out after 30s"
}
```

---

## Performance Characteristics

| Operation | Complexity | Typical Latency | Notes |
|-----------|-----------|-----------------|-------|
| `find_callers` (direct) | O(1) | <5ms | Reverse index lookup |
| `find_callees` (direct) | O(1) | <5ms | Forward index lookup |
| `find_callers` (indirect, depth=3) | O(V+E) | 10-50ms | BFS traversal |
| `find_callees` (indirect, depth=3) | O(V+E) | 10-50ms | BFS traversal |
| `get_call_chain` | O(V+E) | 20-100ms | BFS with path reconstruction |
| `find_implementations` | O(n) | <10ms | Interface index scan |
| `find_dependencies` | O(1) | <5ms | Dependency index lookup |
| `find_dependents` | O(1) | <5ms | Reverse dependency lookup |

**Optimization Tips:**
- Use `limit` to cap result size for large graphs
- Use `max_depth` to prevent deep traversals
- Use `include_indirect=False` for faster queries
- Cache results for frequently queried functions

---

## Integration Examples

### Example 1: Refactoring Impact Analysis

```python
async def analyze_refactoring_impact(function_name: str, project: str):
    """Analyze the impact of refactoring a function."""

    # Find all callers
    callers = await server.find_callers(
        function_name=function_name,
        project_name=project,
        include_indirect=True,
        max_depth=5
    )

    # Find all callees
    callees = await server.find_callees(
        function_name=function_name,
        project_name=project,
        include_indirect=False
    )

    return {
        "affected_functions": callers["total_count"],
        "direct_callers": len(callers["direct_callers"]),
        "indirect_callers": len(callers["indirect_callers"]),
        "dependencies": len(callees["direct_callees"]),
        "risk_level": "high" if callers["total_count"] > 20 else "low"
    }
```

### Example 2: Security Audit

```python
async def check_security_path(sensitive_function: str, project: str):
    """Check if user input can reach a sensitive function."""

    # Find all paths from user input to sensitive operation
    paths = await server.get_call_chain(
        from_function="parse_user_input",
        to_function=sensitive_function,
        project_name=project,
        max_paths=10
    )

    # Analyze each path for validation
    vulnerable_paths = []
    for path_info in paths["paths"]:
        has_validation = any("validate" in func.lower() for func in path_info["path"])
        if not has_validation:
            vulnerable_paths.append(path_info)

    return {
        "total_paths": paths["path_count"],
        "vulnerable_paths": len(vulnerable_paths),
        "paths": vulnerable_paths
    }
```

### Example 3: Architecture Visualization

```python
async def generate_architecture_diagram(entry_point: str, project: str):
    """Generate data for architecture visualization."""

    # Get call tree from entry point
    callees = await server.find_callees(
        function_name=entry_point,
        project_name=project,
        include_indirect=True,
        max_depth=3
    )

    # Build visualization data
    nodes = []
    edges = []

    for callee in callees["direct_callees"]:
        nodes.append({
            "id": callee["qualified_name"],
            "label": callee["name"],
            "file": callee["file_path"],
            "level": 1
        })
        edges.append({
            "from": entry_point,
            "to": callee["qualified_name"]
        })

    # Add indirect callees...

    return {"nodes": nodes, "edges": edges}
```

---

## Best Practices

### 1. Use Appropriate Depth Limits

```python
# ❌ Bad: Unbounded traversal
result = await server.find_callers(
    function_name="common_util",
    project_name="large-app",
    include_indirect=True,
    max_depth=999  # Will traverse entire graph!
)

# ✅ Good: Reasonable depth
result = await server.find_callers(
    function_name="common_util",
    project_name="large-app",
    include_indirect=True,
    max_depth=3  # Most useful callers
)
```

### 2. Limit Result Sets

```python
# ❌ Bad: Fetching thousands of results
result = await server.find_callers(
    function_name="logger.log",
    project_name="my-app",
    limit=10000
)

# ✅ Good: Paginated results
result = await server.find_callers(
    function_name="logger.log",
    project_name="my-app",
    limit=50  # First page
)
```

### 3. Cache Expensive Queries

```python
# Cache call graph queries that don't change often
from functools import lru_cache

@lru_cache(maxsize=100)
async def get_cached_callers(func_name: str, project: str):
    return await server.find_callers(
        function_name=func_name,
        project_name=project
    )
```

### 4. Use Direct Queries When Possible

```python
# ❌ Slower: Indirect traversal for simple queries
result = await server.find_callers(
    function_name="simple_func",
    project_name="my-app",
    include_indirect=True  # Unnecessary!
)

# ✅ Faster: Direct lookup
result = await server.find_callers(
    function_name="simple_func",
    project_name="my-app",
    include_indirect=False  # Just direct callers
)
```

---

## Troubleshooting

### Issue: "Function not found"

**Cause:** Function hasn't been indexed yet
**Solution:**
```bash
# Re-index the project
python -m src.cli index /path/to/code --project-name my-app
```

### Issue: Slow queries on large codebases

**Cause:** Deep traversal or large result sets
**Solution:**
- Reduce `max_depth` (use 2-3 instead of 5-10)
- Add `limit` parameter (50-100 results)
- Use `include_indirect=False` for direct queries only

### Issue: Missing call relationships

**Cause:** Dynamic calls, reflection, or unsupported language features
**Solution:**
- Python: Static analysis can't detect `getattr()`, `eval()`, etc.
- Add explicit type hints for better detection
- Manually document dynamic relationships

### Issue: Outdated call graph

**Cause:** Code changed since last index
**Solution:**
```bash
# Re-index specific files
python -m src.cli index /path/to/changed/files --project-name my-app

# Or re-index entire project
python -m src.cli index /path/to/project --project-name my-app --force
```

---

## Migration Guide

### From Manual grep/ack Searches

**Before:**
```bash
# Find callers manually
grep -r "process_payment" app/
# Manually parse results, check context, verify calls...
```

**After:**
```python
result = await server.find_callers(
    function_name="process_payment",
    project_name="my-app"
)
# Structured data with file paths, line numbers, metadata
```

### From IDE "Find References"

**IDE limitations:**
- Only works in single IDE session
- No persistent storage
- No indirect caller discovery
- No batch processing

**Call Graph API advantages:**
- Persistent across sessions
- Indirect caller/callee discovery
- Batch queries via API
- Project-wide analysis

---

## API Versioning

**Current Version:** v1.0
**Stability:** Stable
**Breaking Changes:** None planned for v1.x

Future additions (backwards-compatible):
- v1.1: JavaScript/TypeScript support
- v1.2: Cross-language call tracking
- v1.3: Call frequency statistics
- v1.4: Performance profiling integration

---

## Support

- **Documentation:** This file
- **Examples:** `tests/integration/test_call_graph_tools.py`
- **Issues:** GitHub Issues
- **Discussions:** GitHub Discussions

---

**Last Updated:** 2025-11-23
**Version:** 1.0
**Status:** Production Ready
