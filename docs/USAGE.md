# Usage Guide

**Last Updated:** November 16, 2025

---

## Quick Start

### Storing Memories

```python
# Via Claude (natural language)
"Remember that I prefer Python for backend development"
# Claude will use the store_memory tool automatically

# Programmatically
from src.core.server import MemoryRAGServer
server = MemoryRAGServer()
await server.initialize()

result = await server.store_memory(
    content="I prefer Python for backend development",
    category="preference",
    importance=0.8
)
```

### Retrieving Memories

```python
# Via Claude
"What are my preferences for backend development?"
# Claude will use retrieve_memories

# Programmatically
results = await server.retrieve_memories(
    query="backend development preferences",
    limit=5
)
```

### Code Indexing

```bash
# Index a codebase
python -m src.cli index ./my-project --project-name my-app

# Watch for changes
python -m src.cli watch ./my-project
```

### Code Search

```python
# Via Claude
"Find the authentication logic in my codebase"
# Claude will use search_code

# Programmatically
results = await server.search_code(
    query="authentication logic",
    project_name="my-app",
    language="python"
)
```

---

## Memory Management

### Memory Categories

**preference** - User preferences and style choices
- "I prefer tabs over spaces"
- "Always use TypeScript for frontend"

**fact** - Factual information
- "The database password is stored in AWS Secrets Manager"
- "The API rate limit is 1000 requests/hour"

**event** - Things that happened
- "Deployed v2.0 to production on Nov 15"
- "Fixed the authentication bug in commit abc123"

**workflow** - Process and procedures
- "Always run tests before pushing to main"
- "Use conventional commits for PR titles"

**context** - General project context
- "This project uses FastAPI for the backend"
- "We follow Google's Python style guide"

### Context Levels (Auto-Classified)

**USER_PREFERENCE** - Personal preferences
- Automatically applied to most "preference" category memories
- Filtered with `retrieve_preferences` tool

**PROJECT_CONTEXT** - Project-specific information
- Auto-detected from project names and technical content
- Filtered with `retrieve_project_context` tool

**SESSION_STATE** - Current work state
- Detected from temporal language ("currently", "just", "working on")
- Filtered with `retrieve_session_state` tool

### Importance Scores

| Score | Meaning | Example |
|-------|---------|---------|
| 0.9-1.0 | Critical | Security credentials, critical bugs |
| 0.7-0.9 | High | Strong preferences, key decisions |
| 0.5-0.7 | Medium | General preferences, facts |
| 0.3-0.5 | Low | Minor preferences, FYI info |
| 0.0-0.3 | Very Low | Trivial information |

---

## Code Intelligence

### Indexing Workflows

**Initial Index:**
```bash
# Index entire project
python -m src.cli index ./src --project-name my-app

# Non-recursive (single directory)
python -m src.cli index ./src --no-recursive
```

**Incremental Updates:**
```bash
# Re-index (only changed files)
python -m src.cli index ./src

# With file watching (auto-reindex on changes)
python -m src.cli watch ./src
```

**Multiple Projects:**
```bash
python -m src.cli index ./project-a --project-name proj-a
python -m src.cli index ./project-b --project-name proj-b

# Search specific project
results = await server.search_code(
    query="authentication",
    project_name="proj-a"
)
```

### Search Patterns

**Finding Functions:**
```python
await server.search_code(
    query="user authentication function"
)
```

**Finding Classes:**
```python
await server.search_code(
    query="database connection class"
)
```

**By File Pattern:**
```python
await server.search_code(
    query="error handling",
    file_pattern="*/api/*"
)
```

**By Language:**
```python
await server.search_code(
    query="async request handler",
    language="python"
)
```

---

## Advanced Usage

### Specialized Retrieval

**Get Only Preferences:**
```python
# Via specialized tool
preferences = await server.retrieve_preferences(
    query="coding style",
    limit=10
)
```

**Get Project Context:**
```python
context = await server.retrieve_project_context(
    query="architecture decisions",
    project_name="my-app"
)
```

**Get Session State:**
```python
state = await server.retrieve_session_state(
    query="current progress"
)
```

### Filtering Results

**By Multiple Criteria:**
```python
results = await server.retrieve_memories(
    query="Python preferences",
    context_level="USER_PREFERENCE",
    category="preference",
    min_importance=0.7,
    tags=["python", "style"]
)
```

**By Project:**
```python
results = await server.retrieve_memories(
    query="API documentation",
    scope="project",
    project_name="my-web-app"
)
```

### Batch Operations

**Store Multiple Memories:**
```python
memories = [
    {"content": "Prefer Python", "category": "preference"},
    {"content": "Use FastAPI", "category": "fact"},
]

for memory in memories:
    await server.store_memory(**memory)
```

---

## CLI Commands

### Index Command

```bash
# Basic usage
python -m src.cli index <path>

# With options
python -m src.cli index ./src \
  --project-name my-app \
  --recursive

# Non-recursive
python -m src.cli index ./src --no-recursive
```

### Watch Command

```bash
# Watch for file changes
python -m src.cli watch ./src

# With project name
python -m src.cli watch ./src --project-name my-app
```

---

## Best Practices

### Memory Storage

1. **Be Specific:** "I prefer pytest over unittest" vs "I like pytest"
2. **Use Tags:** Tag memories for easy filtering
3. **Set Importance:** Higher importance = higher priority in search
4. **Scope Correctly:** Use "project" scope for project-specific info

### Memory Retrieval

1. **Natural Language:** Write queries as questions
2. **Use Filters:** Narrow results with context_level, category
3. **Check Scores:** Scores >0.7 are usually highly relevant
4. **Limit Results:** Default 5 is usually enough

### Code Indexing

1. **Index Incrementally:** Only changed files are re-processed
2. **Use File Watching:** Auto-reindex in development
3. **Project Names:** Use consistent project names
4. **Gitignore:** Indexer respects .gitignore

### Code Search

1. **Be Descriptive:** "JWT token validation" vs "token"
2. **Filter by Language:** Narrow results to specific languages
3. **Use File Patterns:** Search specific directories
4. **Review Scores:** Scores >0.8 are exact matches

---

## Common Workflows

### New Project Setup

```bash
# 1. Index the codebase
python -m src.cli index ./my-project --project-name my-project

# 2. Start watching for changes
python -m src.cli watch ./my-project &

# 3. Store project context
# (Claude will do this naturally during conversation)
```

### Finding Code

```python
# 1. Search for functionality
results = await server.search_code(
    query="database migration logic"
)

# 2. Review results
for r in results['results']:
    print(f"{r['file_path']}:{r['start_line']} - {r['unit_name']}")

# 3. Navigate to code
# Open file at line number
```

### Tracking Preferences

```python
# Store preferences as you work
await server.store_memory(
    content="Always use type hints in Python functions",
    category="preference",
    tags=["python", "typing"]
)

# Later, retrieve them
preferences = await server.retrieve_preferences(
    query="Python coding standards"
)
```

---

## Integration with Claude

### Natural Language

Claude automatically uses the MCP tools when appropriate:

**User:** "Remember that I prefer tabs over spaces"
**Claude:** *Uses store_memory tool* "I'll remember that preference."

**User:** "What do I prefer for indentation?"
**Claude:** *Uses retrieve_memories* "You prefer tabs over spaces."

**User:** "Find the login function in the codebase"
**Claude:** *Uses search_code* "I found the login function at src/auth.py:45"

### Manual Tool Invocation

You can also explicitly ask Claude to use tools:

**User:** "Use the search_code tool to find error handling"
**Claude:** *Uses search_code with query="error handling"*

---

## Tips and Tricks

### Performance Optimization

- Use caching: Repeated queries are <1ms (cached)
- Batch operations: Process multiple files together
- Index selectively: Only index relevant directories

### Organization

- Use consistent project names
- Tag memories systematically
- Set importance accurately
- Regular cleanup of old session state

### Search Quality

- Use descriptive queries (3-7 words optimal)
- Include context in queries
- Filter by language for polyglot projects
- Use file patterns for large codebases

---

## Next Steps

- **API Reference:** [API.md](API.md) - Detailed API documentation
- **Development Guide:** [DEVELOPMENT.md](DEVELOPMENT.md) - Contributing
- **Troubleshooting:** [TROUBLESHOOTING.md](TROUBLESHOOTING.md) - Common issues

