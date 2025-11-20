# Usage Guide

**Last Updated:** November 20, 2025
**Version:** 4.0 (Production-Ready with 30 CLI Commands)

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

# Programmatically - Semantic search (default)
results = await server.search_code(
    query="authentication logic",
    project_name="my-app",
    language="python"
)

# Hybrid search (BM25 + vector)
results = await server.search_code(
    query="JWT token validation",
    search_mode="hybrid"  # Combines keyword + semantic
)

# Keyword-only search (BM25)
results = await server.search_code(
    query="def authenticate",
    search_mode="keyword"  # Exact term matching
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

**Hybrid Search (Best of Both Worlds):**
```python
# Use hybrid mode for queries with specific terms
await server.search_code(
    query="JWT authentication validate_token",
    search_mode="hybrid"  # Finds both exact matches + similar concepts
)
```

---

## Dependency Tracking

### Finding Dependencies

**Get File Imports:**
```python
# Direct dependencies
deps = await server.get_file_dependencies(
    file_path="src/auth/handlers.py"
)
print(deps['direct_dependencies'])
# ['src/auth/models.py', 'src/database/connection.py', ...]

# Include transitive dependencies
deps = await server.get_file_dependencies(
    file_path="src/auth/handlers.py",
    transitive=True
)
print(deps['transitive_dependencies'])
# All files this file depends on, recursively
```

**Get Reverse Dependencies:**
```python
# Find what imports this file
dependents = await server.get_file_dependents(
    file_path="src/auth/models.py"
)
print(dependents['direct_dependents'])
# ['src/auth/handlers.py', 'src/api/routes.py', ...]
```

**Find Import Path:**
```python
# Find how two files are connected
path = await server.find_dependency_path(
    source_file="src/api/routes.py",
    target_file="src/database/connection.py"
)
if path['path_found']:
    print(" -> ".join(path['path']))
    # src/api/routes.py -> src/auth/handlers.py -> src/database/connection.py
```

**Get Dependency Statistics:**
```python
# Project-wide dependency analysis
stats = await server.get_dependency_stats(
    project_name="my-app"
)
print(f"Total files: {stats['total_files']}")
print(f"Circular dependencies: {len(stats['circular_dependencies'])}")
print(f"Most imported: {stats['most_imported_files'][0]['file']}")
```

---

## Conversation Sessions

### Managing Sessions

**Start a Session:**
```python
session = await server.start_conversation_session(
    session_name="debugging-auth"
)
print(f"Session ID: {session['session_id']}")

# Sessions enable:
# - Query expansion based on conversation history
# - Deduplication of previously shown results
# - Automatic timeout after 30 minutes
```

**End a Session:**
```python
result = await server.end_conversation_session(
    session_id=session['session_id']
)
print(f"Duration: {result['duration_minutes']} minutes")
print(f"Queries: {result['queries_processed']}")
```

**List Active Sessions:**
```python
sessions = await server.list_conversation_sessions()
for s in sessions['active_sessions']:
    print(f"{s['session_name']}: {s['queries_processed']} queries")
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

### Git Index Command

```bash
# Index git history
python -m src.cli git-index <repo-path> --project-name my-app

# Index specific number of commits
python -m src.cli git-index ./my-repo \
  --project-name my-app \
  --commit-count 500

# Index all branches (default: current branch only)
python -m src.cli git-index ./my-repo \
  --all-branches
```

### Watch Command

```bash
# Watch for file changes
python -m src.cli watch ./src

# With project name
python -m src.cli watch ./src --project-name my-app
```

### Status Command

```bash
# View indexed projects and statistics
python -m src.cli status

# Shows:
# - Indexed projects with file/function/class counts
# - Storage backend status
# - File watcher configuration
# - Cache statistics
```

### Health Check Command

```bash
# Check system health
python -m src.cli health

# Checks:
# - Storage connection (Qdrant/SQLite)
# - Parser availability (Rust/Python)
# - Embedding model
# - Disk space and memory
```

### Project Management Commands

```bash
# List all indexed projects
python -m src.cli project list

# Get detailed project statistics
python -m src.cli project stats my-app

# Switch active project context
python -m src.cli project switch my-app

# Archive inactive project
python -m src.cli project archive old-project

# Rename project
python -m src.cli project rename old-name new-name

# Delete project (requires confirmation)
python -m src.cli project delete old-project
```

### Memory Management Commands

```bash
# Interactive memory browser (TUI)
python -m src.cli memory-browser

# Find and consolidate duplicates
python -m src.cli consolidate --interactive --execute

# Verify memories and resolve contradictions
python -m src.cli verify --auto-verify
python -m src.cli verify --contradictions

# Prune stale memories
python -m src.cli prune --dry-run
python -m src.cli prune --execute

# Lifecycle management
python -m src.cli lifecycle health
python -m src.cli lifecycle update
python -m src.cli lifecycle optimize --execute
```

### Git Integration Commands

```bash
# Index git commit history
python -m src.cli git-index ./repo --project-name my-app

# Search git history semantically
python -m src.cli git-search "authentication bug fix" --since "last week"
python -m src.cli git-search "refactor" --author "john@example.com"
```

### Health Monitoring Commands

```bash
# Continuous health monitoring status
python -m src.cli health-monitor status

# Generate health report
python -m src.cli health-monitor report --period weekly

# Apply automated fixes
python -m src.cli health-monitor fix --auto

# View health history
python -m src.cli health-monitor history --days 30

# Interactive health dashboard
python -m src.cli health-dashboard
```

### Analytics & Reporting Commands

```bash
# Token usage analytics
python -m src.cli analytics --period-days 30
python -m src.cli analytics --project-name my-app

# Session summary
python -m src.cli session-summary
python -m src.cli session-summary --session-id abc123
```

### Data Management Commands

```bash
# Backup memories
python -m src.cli backup create
python -m src.cli backup list

# Export data
python -m src.cli export --format json --output backup.json
python -m src.cli export --format markdown --output memories.md

# Import data
python -m src.cli import --file backup.json

# Repository management
python -m src.cli repository list
python -m src.cli repository add ./path/to/repo --name my-repo

# Workspace management
python -m src.cli workspace list
python -m src.cli workspace create my-workspace
```

### Tagging Commands

```bash
# Auto-tag memories
python -m src.cli auto-tag

# Manage tags
python -m src.cli tags list
python -m src.cli tags add <memory-id> tag1 tag2
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
5. **Choose Search Mode:**
   - `semantic`: Best for concepts and meaning
   - `keyword`: Best for exact terms (variable names, function names)
   - `hybrid`: Best for mixed queries with specific terms
6. **Check Quality Indicators:** Review `matched_keywords` and `interpretation` fields

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

## Multi-Project Features

### Cross-Project Code Search

```python
# Search across all opted-in projects
results = await server.search_all_projects(
    query="authentication patterns",
    limit=10
)

# Opt-in project for cross-project search
await server.opt_in_cross_project("my-web-app")

# List opted-in projects
projects = await server.list_opted_in_projects()

# Opt-out project
await server.opt_out_cross_project("old-project")
```

### Find Similar Code

```python
# Find similar code snippets
results = await server.find_similar_code(
    code_snippet="""
    async def login(username, password):
        user = await db.authenticate(username, password)
        return create_token(user)
    """,
    limit=5
)

# Interpretation:
# >0.95: Likely duplicates
# 0.80-0.95: Similar patterns
# <0.80: Related but different
```

### Git History Search

```python
# Search git commits semantically
results = await server.search_git_history(
    query="authentication bug",
    since="2024-01-01",
    author="john@example.com"
)

# Track function evolution
evolution = await server.show_function_evolution(
    file_path="src/auth/handlers.py",
    function_name="login"
)
```

---

## Advanced Features

### Memory Lifecycle Management

Memories automatically transition through lifecycle states:
- **ACTIVE** (0-7 days): 1.0x search weight
- **RECENT** (7-30 days): 0.7x search weight
- **ARCHIVED** (30-180 days): 0.3x search weight
- **STALE** (180+ days): 0.1x search weight

```bash
# View lifecycle health
python -m src.cli lifecycle health

# Update lifecycle states
python -m src.cli lifecycle update

# Optimize storage
python -m src.cli lifecycle optimize --execute
```

### Memory Provenance & Trust

```bash
# Verify memories with low confidence
python -m src.cli verify --auto-verify

# Review contradictions
python -m src.cli verify --contradictions

# Filter by category
python -m src.cli verify --category preference
```

### Intelligent Consolidation

```bash
# Find duplicates (dry-run by default)
python -m src.cli consolidate --interactive

# Auto-merge high-confidence duplicates
python -m src.cli consolidate --auto --execute

# Filter by category
python -m src.cli consolidate --category fact --execute
```

### Health Monitoring

```bash
# Check current health status
python -m src.cli health-monitor status

# Generate weekly report
python -m src.cli health-monitor report --period weekly

# Auto-fix issues
python -m src.cli health-monitor fix --auto

# View trends
python -m src.cli health-monitor history --days 30
```

### Token Analytics

```bash
# View token savings
python -m src.cli analytics --period-days 30

# Project-specific analytics
python -m src.cli analytics --project-name my-app

# Top sessions by savings
python -m src.cli analytics --top-sessions
```

---

## Complete CLI Command Reference

**Total:** 28 commands across 7 categories

### 1. Indexing & Watching (3 commands)
- `index` - Index code files
- `watch` - Watch for file changes
- `auto-tag` - Auto-tag memories

### 2. Project Management (4 commands)
- `project` - Project lifecycle (list, stats, switch, archive, rename, delete)
- `repository` - Repository management (add, remove, list)
- `workspace` - Workspace coordination (create, list)
- `collections` - Memory collection management

### 3. Memory Management (6 commands)
- `memory-browser` - Interactive TUI
- `consolidate` - Duplicate consolidation
- `verify` - Memory verification
- `prune` - Prune stale memories
- `lifecycle` - Lifecycle management
- `tags` - Tag management

### 4. Git Integration (2 commands)
- `git-index` - Index git history
- `git-search` - Search commits

### 5. Health & Monitoring (3 commands)
- `health` - Health checks
- `health-monitor` - Continuous monitoring
- `health-dashboard` - Interactive dashboard

### 6. Analytics & Reporting (3 commands)
- `status` - System status
- `analytics` - Token analytics
- `session-summary` - Session summaries

### 7. Data Management (4 commands)
- `backup` - Backup creation
- `export` - Data export
- `import` - Data import
- `archival` - Project archival

**Usage:** `python -m src.cli <command> [options]`

---

## Next Steps

- **API Reference:** [API.md](API.md) - Detailed API documentation
- **Development Guide:** [DEVELOPMENT.md](DEVELOPMENT.md) - Contributing
- **Troubleshooting:** [TROUBLESHOOTING.md](TROUBLESHOOTING.md) - Common issues

**Document Version:** 2.0
**Last Updated:** November 17, 2025
**Status:** Comprehensive update with all 28 CLI commands documented

