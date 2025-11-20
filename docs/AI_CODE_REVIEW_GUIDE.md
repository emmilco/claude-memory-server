# AI Code Review Guide for Claude Memory Server

## Purpose
This document provides instructions for AI agents performing code review on the Claude Memory RAG Server project. It focuses on identifying common weaknesses in AI-generated code and catching issues that automated testing might miss.

---

## 🎯 Primary Focus Areas

### 1. Type Safety & Type Hints

**Common AI Code Weaknesses:**
- Incomplete or missing type hints in function signatures
- Overuse of `Any` types that should be specific
- Inconsistent typing patterns across similar functions
- Missing return type annotations
- Generic types (`List`, `Dict`) without element types

**What to Check:**
```python
# ❌ BAD: Missing type hints
def process_data(data, config):
    return data.transform(config)

# ❌ BAD: Using Any when specific type available
from typing import Any
def handle_response(response: Any) -> Any:
    return response.json()

# ✅ GOOD: Complete type hints
from typing import Dict, List
def process_data(data: List[str], config: Dict[str, int]) -> List[int]:
    return data.transform(config)
```

**Action Items:**
- [ ] Review all function signatures for complete type hints
- [ ] Replace `Any` with specific types where possible
- [ ] Add generic type parameters to collections
- [ ] Verify return types match actual returns

---

### 2. Error Handling

**Common AI Code Weaknesses:**
- Bare `except:` clauses that catch all exceptions
- Swallowed exceptions with no logging or re-raising
- Generic error messages without context
- Inconsistent error handling patterns across similar operations
- Missing validation before operations that can fail

**What to Check:**
```python
# ❌ BAD: Bare except
try:
    result = risky_operation()
except:
    pass

# ❌ BAD: No context in error
except Exception as e:
    raise ValueError("Error occurred")

# ❌ BAD: Swallowed exception
try:
    data = fetch_data()
except ConnectionError:
    data = None  # Silent failure

# ✅ GOOD: Specific exceptions with context
try:
    result = risky_operation(file_path)
except FileNotFoundError as e:
    logger.error(f"File not found: {file_path}", exc_info=True)
    raise FileNotFoundError(
        f"Could not find required file: {file_path}"
    ) from e
except PermissionError as e:
    logger.error(f"Permission denied: {file_path}", exc_info=True)
    raise PermissionError(
        f"Insufficient permissions to read {file_path}"
    ) from e
```

**Action Items:**
- [ ] Replace bare `except:` with specific exception types
- [ ] Add error context (file paths, IDs, operation details)
- [ ] Ensure exceptions are logged before re-raising
- [ ] Check for missing validation (null checks, bounds checks)
- [ ] Verify error messages are actionable

---

### 3. Async/Await Patterns

**Common AI Code Weaknesses:**
- Missing `await` keywords on async functions
- Blocking I/O operations in async functions
- Incorrect use of `asyncio.gather()` vs sequential awaits
- Not properly handling async context managers
- Creating tasks without awaiting them

**What to Check:**
```python
# ❌ BAD: Missing await
async def fetch_data():
    result = async_operation()  # Returns coroutine, not result
    return result

# ❌ BAD: Blocking I/O in async function
async def save_file(data):
    with open("file.txt", "w") as f:  # Blocking!
        f.write(data)

# ❌ BAD: Sequential when parallel is possible
async def fetch_all():
    data1 = await fetch(url1)
    data2 = await fetch(url2)  # Could be parallel
    return data1, data2

# ✅ GOOD: Proper async patterns
async def fetch_data():
    result = await async_operation()
    return result

async def save_file(data):
    async with aiofiles.open("file.txt", "w") as f:
        await f.write(data)

async def fetch_all():
    results = await asyncio.gather(
        fetch(url1),
        fetch(url2)
    )
    return results
```

**Action Items:**
- [ ] Verify all async function calls have `await`
- [ ] Check for blocking I/O (file operations, database calls)
- [ ] Identify opportunities for parallel execution
- [ ] Ensure async context managers use `async with`
- [ ] Check that tasks are properly awaited or tracked

---

### 4. Resource Management

**Common AI Code Weaknesses:**
- Missing context managers for file/connection handling
- Unclosed database connections or file handles
- Memory leaks from circular references
- Inefficient data structures (e.g., loading entire file into memory)
- Not cleaning up temporary resources

**What to Check:**
```python
# ❌ BAD: No context manager
def read_file(path):
    f = open(path)
    data = f.read()
    return data  # File never closed

# ❌ BAD: Loading entire large file
def process_log(path):
    lines = open(path).readlines()  # Memory issue for large files
    return [parse(line) for line in lines]

# ❌ BAD: Connection leak
async def query_db():
    conn = await db.connect()
    results = await conn.execute(query)
    return results  # Connection never closed

# ✅ GOOD: Proper resource management
def read_file(path):
    with open(path) as f:
        data = f.read()
    return data

def process_log(path):
    with open(path) as f:
        for line in f:  # Stream processing
            yield parse(line)

async def query_db():
    async with db.connection() as conn:
        results = await conn.execute(query)
        return results
```

**Action Items:**
- [ ] Ensure all file operations use context managers
- [ ] Check database connections are properly closed
- [ ] Look for memory-intensive operations on large data
- [ ] Verify cleanup in `__del__` or `close()` methods
- [ ] Check for circular references in class relationships

---

### 5. Testing Gaps

**Common AI Code Weaknesses:**
- Only testing happy paths
- Missing edge case tests (empty inputs, None values, boundaries)
- Outdated test assertions that don't match current behavior
- Incomplete mocking (external dependencies not mocked)
- Tests that depend on external state or ordering

**What to Check:**
```python
# ❌ BAD: Only happy path
def test_divide():
    assert divide(10, 2) == 5

# ❌ BAD: Missing edge cases
def test_find_user():
    user = find_user("john")
    assert user.name == "John"
    # Missing: user not found, invalid input, etc.

# ✅ GOOD: Comprehensive testing
def test_divide():
    # Happy path
    assert divide(10, 2) == 5

    # Edge cases
    with pytest.raises(ZeroDivisionError):
        divide(10, 0)

    assert divide(0, 5) == 0
    assert divide(-10, 2) == -5

def test_find_user():
    # User exists
    user = find_user("john")
    assert user.name == "John"

    # User not found
    with pytest.raises(UserNotFoundError):
        find_user("nonexistent")

    # Invalid input
    with pytest.raises(ValueError):
        find_user("")
    with pytest.raises(ValueError):
        find_user(None)
```

**Action Items:**
- [ ] Check for error path testing (exceptions, failures)
- [ ] Verify edge cases: None, empty, zero, negative, max values
- [ ] Ensure external dependencies are mocked
- [ ] Check test isolation (no shared state between tests)
- [ ] Verify async tests use proper fixtures

---

### 6. Documentation Drift

**Common AI Code Weaknesses:**
- Docstrings that don't match current function behavior
- Comments describing what was planned, not what exists
- Outdated examples in documentation
- Missing documentation for public APIs
- Inconsistent documentation style

**What to Check:**
```python
# ❌ BAD: Outdated docstring
def search_code(query: str, limit: int = 10) -> List[Result]:
    """
    Search code using keyword matching.  # ← WRONG! Now uses semantic search

    Args:
        query: Search keywords
        # Missing: limit parameter documented
    """
    return semantic_search(query, limit)

# ✅ GOOD: Accurate documentation
def search_code(query: str, limit: int = 10) -> List[Result]:
    """
    Search code using semantic similarity.

    Generates embeddings for the query and finds the most similar
    code snippets using vector search.

    Args:
        query: Natural language description of desired code
        limit: Maximum number of results to return (default: 10)

    Returns:
        List of Result objects sorted by relevance score

    Raises:
        EmbeddingError: If embedding generation fails
        ValueError: If query is empty or limit is negative

    Example:
        >>> results = search_code("async file reading", limit=5)
        >>> print(results[0].code)
    """
    return semantic_search(query, limit)
```

**Action Items:**
- [ ] Verify docstrings match actual behavior
- [ ] Check that all parameters are documented
- [ ] Ensure raised exceptions are documented
- [ ] Update examples to reflect current API
- [ ] Remove outdated TODOs and comments

---

### 7. Code Duplication

**Common AI Code Weaknesses:**
- Copy-pasted code with minor variations
- Similar logic in multiple places that could be unified
- Repeated validation or transformation logic
- Duplicated error handling patterns

**What to Check:**
```python
# ❌ BAD: Duplicated logic
def validate_user_input(data):
    if not data:
        raise ValueError("Input cannot be empty")
    if len(data) > 1000:
        raise ValueError("Input too long")
    return data.strip()

def validate_query(query):
    if not query:
        raise ValueError("Query cannot be empty")
    if len(query) > 1000:
        raise ValueError("Query too long")
    return query.strip()

# ✅ GOOD: Unified validation
def validate_string_input(
    value: str,
    field_name: str,
    max_length: int = 1000
) -> str:
    """Generic string input validation."""
    if not value:
        raise ValueError(f"{field_name} cannot be empty")
    if len(value) > max_length:
        raise ValueError(f"{field_name} too long (max: {max_length})")
    return value.strip()

def validate_user_input(data: str) -> str:
    return validate_string_input(data, "Input")

def validate_query(query: str) -> str:
    return validate_string_input(query, "Query")
```

**Action Items:**
- [ ] Identify repeated code blocks (>5 lines)
- [ ] Look for similar functions with minor variations
- [ ] Check for repeated validation logic
- [ ] Find duplicated error handling patterns
- [ ] Consider extracting common logic to utilities

---

### 8. Security Issues

**Common AI Code Weaknesses:**
- SQL injection vulnerabilities (string concatenation in queries)
- Path traversal risks (unsanitized file paths)
- Command injection (unsanitized shell commands)
- Exposure of sensitive data in logs or errors
- Missing input validation/sanitization

**What to Check:**
```python
# ❌ BAD: SQL injection risk
def get_user(username):
    query = f"SELECT * FROM users WHERE name = '{username}'"
    return db.execute(query)

# ❌ BAD: Path traversal risk
def read_file(filename):
    path = f"/data/{filename}"
    return open(path).read()

# ❌ BAD: Command injection
def process_file(filename):
    os.system(f"convert {filename} output.pdf")

# ❌ BAD: Sensitive data in logs
def login(username, password):
    logger.info(f"Login attempt: {username}:{password}")

# ✅ GOOD: Secure practices
def get_user(username):
    query = "SELECT * FROM users WHERE name = ?"
    return db.execute(query, (username,))

def read_file(filename):
    # Sanitize path
    safe_name = os.path.basename(filename)
    path = os.path.join("/data", safe_name)
    if not path.startswith("/data/"):
        raise ValueError("Invalid path")
    return open(path).read()

def process_file(filename):
    # Use subprocess with argument list
    subprocess.run(["convert", filename, "output.pdf"], check=True)

def login(username, password):
    logger.info(f"Login attempt for user: {username}")  # No password
```

**Action Items:**
- [ ] Check all database queries for parameterization
- [ ] Verify file paths are sanitized and validated
- [ ] Ensure shell commands use subprocess with lists
- [ ] Look for sensitive data in logs/errors
- [ ] Check input validation at API boundaries

---

## 🔍 Review Methodology

### Step 1: High-Level Architecture Review
1. Check for proper separation of concerns
2. Verify consistent error handling patterns
3. Look for circular dependencies
4. Identify missing abstraction layers

### Step 2: Module-by-Module Review
For each Python file:
1. Read the module docstring
2. Check imports for unnecessary dependencies
3. Review each class/function against focus areas
4. Document issues with severity: CRITICAL, HIGH, MEDIUM, LOW

### Step 3: Cross-Cutting Concerns
1. **Logging**: Consistent logging levels and messages?
2. **Configuration**: Hardcoded values that should be configurable?
3. **Performance**: Obvious bottlenecks or inefficiencies?
4. **Maintainability**: Complex functions (>50 lines) that should be split?

### Step 4: Documentation Artifacts
Check for stale or outdated:
- [ ] README.md examples
- [ ] CHANGELOG.md entries
- [ ] TODO.md items
- [ ] Planning docs in `planning_docs/`
- [ ] Docstrings and comments
- [ ] Test descriptions

---

## 📊 Issue Severity Guidelines

### CRITICAL
- Security vulnerabilities
- Data loss risks
- Resource leaks causing crashes
- Breaking API changes without migration

### HIGH
- Silent failures (swallowed exceptions)
- Missing error handling in core paths
- Type safety issues causing runtime errors
- Performance bottlenecks (>2x slowdown)

### MEDIUM
- Missing type hints
- Incomplete test coverage on important paths
- Code duplication (>10 lines repeated)
- Documentation drift
- Inefficient but functional code

### LOW
- Style inconsistencies
- Minor documentation issues
- Opportunities for refactoring
- TODO comments

---

## 📝 Review Output Format

For each issue found, document:

```markdown
### [SEVERITY] Module: `src/module/file.py:line_number`

**Issue:** Brief description of the problem

**Current Code:**
```python
# Problematic code snippet
```

**Suggested Fix:**
```python
# Improved code snippet
```

**Rationale:** Why this is an issue and how the fix improves it

**Impact:** What could go wrong if not fixed
```

---

## ✅ Final Checklist

Before completing review:
- [ ] All `src/` modules reviewed
- [ ] Test suite reviewed for gaps
- [ ] Documentation checked for drift
- [ ] Security scan completed
- [ ] Issues categorized by severity
- [ ] Refactoring opportunities identified
- [ ] No vestigial code artifacts left behind

---

## 🎯 Project-Specific Considerations

### This Codebase Characteristics
- **Heavy async/await usage**: Extra attention to async patterns
- **Multiple storage backends**: Check consistency for Qdrant
- **Tree-sitter parsing**: Verify error handling for parse failures
- **Embedding generation**: Watch for performance bottlenecks
- **MCP server**: Ensure all tools have proper validation

### Common Patterns to Validate
1. **Progress callbacks**: Consistent signature and error handling
2. **Context managers**: Proper cleanup in all stores
3. **Configuration**: All new features have config options
4. **CLI commands**: Proper argument validation and help text
5. **Background jobs**: Proper lifecycle and error handling

---

## 🚀 After Review

### Implementation Priorities
1. **Critical issues first**: Security, data loss, crashes
2. **High-impact improvements**: Error handling, type safety
3. **Quality of life**: Refactoring, documentation
4. **Nice-to-have**: Style, minor optimizations

### Testing Requirements
- All fixes must maintain or improve test coverage
- New refactored code needs tests
- Run full test suite before committing
- Target: 99.9%+ test pass rate maintained

---

## Additional Resources

- **Python Type Hints**: https://docs.python.org/3/library/typing.html
- **Async Best Practices**: https://docs.python.org/3/library/asyncio-dev.html
- **OWASP Top 10**: https://owasp.org/www-project-top-ten/
- **pytest Documentation**: https://docs.pytest.org/
