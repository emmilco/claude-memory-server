# Call Graph User Guide

**Quick start guide for using the Call Graph MCP tools**

---

## Table of Contents

1. [Introduction](#introduction)
2. [Getting Started](#getting-started)
3. [Common Use Cases](#common-use-cases)
4. [Step-by-Step Tutorials](#step-by-step-tutorials)
5. [Tips and Tricks](#tips-and-tricks)
6. [FAQ](#faq)

---

## Introduction

### What is the Call Graph?

The Call Graph is a powerful feature that maps all function calls in your codebase, enabling you to:

- 🔍 **Find relationships** - See what calls what
- 🔗 **Trace execution** - Follow code paths from A to B
- 🏗️ **Understand architecture** - Visualize system structure
- 🛡️ **Analyze impact** - Know what breaks when you change code

### Who should use this?

- **Developers** - Understanding unfamiliar codebases
- **Architects** - Analyzing system design
- **Code reviewers** - Assessing change impact
- **Maintainers** - Finding dead code and dependencies

### What you need

- Claude Memory RAG Server installed and running
- Your project indexed (`python -m src.cli index /path/to/code`)
- Basic familiarity with your codebase

---

## Getting Started

### Step 1: Index Your Project

Before using call graph queries, index your project:

```bash
# Index your project
python -m src.cli index /path/to/your/project --project-name my-app

# Verify indexing
python -m src.cli stats my-app
```

**Output:**
```
✓ Indexed 523 functions
✓ Found 1,247 function calls
✓ Discovered 45 interfaces/abstract classes
✓ Mapped 87 implementations
```

### Step 2: Verify the Server is Running

```bash
# Check server status
curl http://localhost:6333/

# Start if not running
python -m src.mcp_server
```

### Step 3: Make Your First Query

Try a simple query to get started:

```python
# Python example
from src.core.server import MemoryRAGServer

server = MemoryRAGServer()
await server.initialize()

# Find what calls a common function
result = await server.find_callers(
    function_name="log",
    project_name="my-app"
)

print(f"Found {result['total_count']} callers of 'log'")
```

---

## Common Use Cases

### Use Case 1: "What calls this function?"

**Scenario:** You want to understand where a function is used before modifying it.

**Solution:** Use `find_callers`

```python
result = await server.find_callers(
    function_name="send_email",
    project_name="my-app",
    include_indirect=False  # Just direct callers
)

# Output:
{
    "total_count": 12,
    "direct_callers": [
        {"qualified_name": "UserController.register", "file_path": "/app/controllers/user.py"},
        {"qualified_name": "PasswordReset.send_reset", "file_path": "/app/auth/reset.py"},
        # ... 10 more
    ]
}
```

**Interpretation:**
- 12 places call `send_email` directly
- Check each location before changing the function signature
- Consider adding a deprecation notice if refactoring

---

### Use Case 2: "What does this function depend on?"

**Scenario:** You want to know what a function calls to understand its complexity.

**Solution:** Use `find_callees`

```python
result = await server.find_callees(
    function_name="UserController.create_user",
    project_name="my-app",
    include_indirect=False
)

# Output shows what create_user calls:
{
    "total_count": 8,
    "direct_callees": [
        {"qualified_name": "validate_email", ...},
        {"qualified_name": "hash_password", ...},
        {"qualified_name": "Database.insert", ...},
        {"qualified_name": "send_welcome_email", ...},
        # ... 4 more
    ]
}
```

**Interpretation:**
- Function has 8 direct dependencies
- Calls validation, database, and email functions
- Moderate complexity (8 dependencies is reasonable)

---

### Use Case 3: "How does data flow from A to B?"

**Scenario:** You need to trace how user input reaches the database.

**Solution:** Use `get_call_chain`

```python
result = await server.get_call_chain(
    from_function="api_endpoint",
    to_function="Database.execute",
    project_name="my-app",
    max_paths=5
)

# Output shows all paths:
{
    "path_count": 3,
    "paths": [
        {
            "path": ["api_endpoint", "UserController.get_user",
                     "UserService.find", "Database.execute"],
            "length": 4
        },
        {
            "path": ["api_endpoint", "CacheService.get",
                     "UserRepository.query", "Database.execute"],
            "length": 4
        },
        # ... 1 more path
    ]
}
```

**Interpretation:**
- 3 different execution paths exist
- One path goes through cache, another doesn't
- All paths are 4 hops (reasonable depth)

---

### Use Case 4: "What implements this interface?"

**Scenario:** You have a `Storage` interface and want to find all implementations.

**Solution:** Use `find_implementations`

```python
result = await server.find_implementations(
    interface_name="Storage",
    project_name="my-app"
)

# Output:
{
    "total_count": 5,
    "implementations": [
        {"implementation_name": "RedisStorage", "file_path": "/app/storage/redis.py"},
        {"implementation_name": "S3Storage", "file_path": "/app/storage/s3.py"},
        {"implementation_name": "DatabaseStorage", "file_path": "/app/storage/db.py"},
        {"implementation_name": "MemoryStorage", "file_path": "/app/storage/memory.py"},
        {"implementation_name": "FileStorage", "file_path": "/app/storage/file.py"}
    ]
}
```

**Interpretation:**
- 5 implementations of `Storage` interface
- Located in different files in `/app/storage/`
- Use this for strategy pattern selection

---

### Use Case 5: "What depends on this file?"

**Scenario:** You want to remove or refactor a utility module.

**Solution:** Use `find_dependents`

```python
result = await server.find_dependents(
    file_path="/app/utils/crypto.py",
    project_name="my-app",
    include_transitive=False
)

# Output:
{
    "total_count": 23,
    "direct_dependents": [
        {"file_path": "/app/auth/password.py", "import_names": ["hash_password"]},
        {"file_path": "/app/auth/token.py", "import_names": ["generate_token", "verify_token"]},
        # ... 21 more
    ]
}
```

**Interpretation:**
- 23 files import from `crypto.py`
- Most import specific functions (`hash_password`, `generate_token`, etc.)
- Breaking changes will affect 23 files

---

## Step-by-Step Tutorials

### Tutorial 1: Refactoring a Function Safely

**Goal:** Rename `process_payment` to `process_transaction` without breaking anything.

**Steps:**

1. **Find all callers:**
   ```python
   callers = await server.find_callers(
       function_name="process_payment",
       project_name="my-app",
       include_indirect=True,
       max_depth=3
   )
   ```

2. **Review the results:**
   ```python
   print(f"Direct callers: {len(callers['direct_callers'])}")
   print(f"Indirect callers: {len(callers['indirect_callers'])}")
   print(f"Total affected: {callers['total_count']}")
   ```

3. **Create a deprecation plan:**
   - Add `@deprecated` decorator to `process_payment`
   - Create new `process_transaction` function
   - Update all callers one by one
   - Remove `process_payment` after migration

4. **Verify migration:**
   ```python
   # After migration, verify no callers remain
   remaining = await server.find_callers(
       function_name="process_payment",
       project_name="my-app"
   )
   assert remaining['total_count'] == 0, "Migration incomplete!"
   ```

**Result:** Safe refactoring with zero breakage.

---

### Tutorial 2: Understanding a Complex Function

**Goal:** Understand what `UserController.create_user` does by analyzing its call tree.

**Steps:**

1. **Find direct dependencies:**
   ```python
   callees = await server.find_callees(
       function_name="UserController.create_user",
       project_name="my-app",
       include_indirect=False
   )
   ```

2. **Categorize dependencies:**
   ```python
   validation = [c for c in callees['direct_callees'] if 'validate' in c['name'].lower()]
   database = [c for c in callees['direct_callees'] if 'database' in c['qualified_name'].lower()]
   external = [c for c in callees['direct_callees'] if 'email' in c['name'].lower() or 'sms' in c['name'].lower()]

   print(f"Validation functions: {len(validation)}")
   print(f"Database operations: {len(database)}")
   print(f"External services: {len(external)}")
   ```

3. **Analyze transitive dependencies:**
   ```python
   all_callees = await server.find_callees(
       function_name="UserController.create_user",
       project_name="my-app",
       include_indirect=True,
       max_depth=5
   )

   print(f"Total dependency tree size: {all_callees['total_count']}")
   ```

4. **Draw conclusions:**
   - High validation count → Good input checking
   - Multiple database calls → Potential performance issue
   - External service calls → Network latency risk
   - Large dependency tree → Complex function, consider refactoring

**Result:** Deep understanding of function behavior and complexity.

---

### Tutorial 3: Security Audit

**Goal:** Verify that user input is validated before reaching sensitive operations.

**Steps:**

1. **Find all paths from input to sensitive function:**
   ```python
   paths = await server.get_call_chain(
       from_function="parse_user_request",
       to_function="Database.raw_execute",
       project_name="my-app",
       max_paths=10
   )
   ```

2. **Analyze each path for validation:**
   ```python
   vulnerable_paths = []

   for path_info in paths['paths']:
       path = path_info['path']

       # Check if any validation function is in the path
       has_validation = any(
           'validate' in func.lower() or 'sanitize' in func.lower()
           for func in path
       )

       if not has_validation:
           vulnerable_paths.append({
               'path': path,
               'length': path_info['length']
           })

   print(f"Found {len(vulnerable_paths)} vulnerable paths!")
   ```

3. **Report findings:**
   ```python
   if vulnerable_paths:
       print("\n⚠️  SECURITY ISSUES FOUND:")
       for i, vp in enumerate(vulnerable_paths, 1):
           print(f"\n{i}. Path without validation:")
           print(" -> ".join(vp['path']))
   ```

4. **Fix issues:**
   - Add validation to each vulnerable path
   - Re-run audit to verify fixes

**Result:** Secure code with validated input paths.

---

### Tutorial 4: Dead Code Detection

**Goal:** Find functions that are never called (dead code).

**Steps:**

1. **Get all functions in project:**
   ```python
   # Load the call graph
   from src.store.call_graph_store import QdrantCallGraphStore

   store = QdrantCallGraphStore()
   await store.initialize()

   graph = await store.load_call_graph("my-app")
   all_functions = list(graph.nodes.keys())
   ```

2. **Check each function for callers:**
   ```python
   dead_functions = []

   for func_name in all_functions:
       callers = await server.find_callers(
           function_name=func_name,
           project_name="my-app",
           include_indirect=False
       )

       if callers['total_count'] == 0:
           # No callers = potentially dead code
           func_node = graph.nodes[func_name]

           # Exclude entry points and public APIs
           if not func_node.is_exported and 'main' not in func_name.lower():
               dead_functions.append(func_node)
   ```

3. **Review and remove:**
   ```python
   print(f"Found {len(dead_functions)} potentially dead functions:")
   for func in dead_functions[:10]:  # Show first 10
       print(f"  - {func.qualified_name} ({func.file_path}:{func.start_line})")
   ```

4. **Verify before deletion:**
   - Check if function is a test helper
   - Check if function is called dynamically
   - Check if function is part of public API

**Result:** Cleaner codebase with less maintenance burden.

---

## Tips and Tricks

### Tip 1: Use Depth Wisely

```python
# ❌ Too deep - slow query, too much data
result = await server.find_callers(
    function_name="common_util",
    include_indirect=True,
    max_depth=10
)

# ✅ Reasonable depth - fast and useful
result = await server.find_callers(
    function_name="common_util",
    include_indirect=True,
    max_depth=3  # Usually sufficient
)
```

**Rule of thumb:**
- Depth 1-2: Direct relationships
- Depth 3-4: Architectural understanding
- Depth 5+: Rarely needed

---

### Tip 2: Limit Large Result Sets

```python
# ❌ Unbounded results
result = await server.find_callers(
    function_name="logger",
    project_name="my-app"
)
# Could return thousands of results!

# ✅ Limited results
result = await server.find_callers(
    function_name="logger",
    project_name="my-app",
    limit=50
)
# Returns top 50 most relevant
```

---

### Tip 3: Combine Queries for Complex Analysis

```python
async def analyze_function_impact(func_name: str):
    """Comprehensive impact analysis."""

    # Find callers (who uses it?)
    callers = await server.find_callers(
        function_name=func_name,
        project_name="my-app",
        include_indirect=True
    )

    # Find callees (what does it depend on?)
    callees = await server.find_callees(
        function_name=func_name,
        project_name="my-app"
    )

    return {
        "impact_scope": callers['total_count'],
        "dependency_count": callees['total_count'],
        "complexity_score": callers['total_count'] + callees['total_count'],
        "risk_level": "high" if callers['total_count'] > 50 else "low"
    }
```

---

### Tip 4: Cache Expensive Queries

```python
import functools

@functools.lru_cache(maxsize=100)
async def get_callers_cached(func_name: str, project: str):
    """Cached version of find_callers."""
    return await server.find_callers(
        function_name=func_name,
        project_name=project
    )

# First call: fetches from database
result1 = await get_callers_cached("process_payment", "my-app")

# Second call: returns cached result
result2 = await get_callers_cached("process_payment", "my-app")
```

---

### Tip 5: Export Results for Reporting

```python
import json

async def export_call_graph_report(func_name: str, output_file: str):
    """Export call graph analysis to JSON."""

    callers = await server.find_callers(
        function_name=func_name,
        project_name="my-app",
        include_indirect=True
    )

    callees = await server.find_callees(
        function_name=func_name,
        project_name="my-app"
    )

    report = {
        "function": func_name,
        "timestamp": datetime.now().isoformat(),
        "callers": callers,
        "callees": callees,
        "summary": {
            "total_callers": callers['total_count'],
            "total_callees": callees['total_count']
        }
    }

    with open(output_file, 'w') as f:
        json.dump(report, f, indent=2)

    print(f"Report saved to {output_file}")
```

---

## FAQ

### Q: How often should I re-index my project?

**A:** Re-index after significant code changes:
- After major refactoring
- After adding/removing many functions
- After merging feature branches
- Daily for active development projects

### Q: Can I search across multiple projects?

**A:** Not directly, but you can query each project separately:
```python
for project in ["frontend", "backend", "shared"]:
    result = await server.find_callers(
        function_name="common_util",
        project_name=project
    )
    print(f"{project}: {result['total_count']} callers")
```

### Q: What languages are supported?

**A:** Currently:
- ✅ Python (full support)
- 🔄 JavaScript/TypeScript (coming soon)
- 🔄 Other languages (planned)

### Q: Why doesn't it find some function calls?

**A:** Limitations:
- **Dynamic calls** - `getattr()`, `eval()`, reflection not detected
- **Cross-language calls** - Currently Python-only
- **Dynamically generated code** - Not analyzed
- **Indirect references** - Function pointers, callbacks may be missed

**Solution:** Add type hints and use static calls where possible.

### Q: How do I handle large codebases (100k+ lines)?

**A:**
1. Index in batches by directory
2. Use `limit` parameter aggressively
3. Query specific modules instead of entire project
4. Use `include_indirect=False` for faster queries
5. Consider upgrading server resources

### Q: Can I visualize the call graph?

**A:** Yes! Export data and use visualization tools:
```python
# Export call tree
result = await server.find_callees(
    function_name="main",
    project_name="my-app",
    include_indirect=True,
    max_depth=3
)

# Convert to format for viz tools (Graphviz, D3.js, etc.)
# See examples in docs/examples/
```

### Q: What's the difference between `find_callers` and `find_dependents`?

**A:**
- `find_callers` - **Function-level**: What functions call this function?
- `find_dependents` - **File-level**: What files import this file?

Use `find_callers` for code analysis, `find_dependents` for module organization.

---

## Next Steps

Now that you understand the basics:

1. **Try it yourself** - Index your project and run queries
2. **Read the API docs** - `docs/CALL_GRAPH_API.md` for detailed reference
3. **Explore examples** - `tests/integration/test_call_graph_tools.py` for code examples
4. **Build workflows** - Integrate call graph into your development process

---

## Resources

- **API Reference:** `docs/CALL_GRAPH_API.md`
- **Examples:** `tests/integration/test_call_graph_tools.py`
- **CLI Commands:** `python -m src.cli --help`
- **Source Code:** `src/graph/`, `src/store/call_graph_store.py`

---

**Last Updated:** 2025-11-23
**Version:** 1.0
**Feedback:** GitHub Issues
