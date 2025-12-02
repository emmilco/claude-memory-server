# Advanced Topics

Advanced workflows, techniques, and scenarios for experienced contributors.

---

## Table of Contents

1. [Git Worktree Advanced Scenarios](#git-worktree-advanced-scenarios)
2. [Merge Conflict Resolution](#merge-conflict-resolution)
3. [Multi-Agent Coordination](#multi-agent-coordination)
4. [Performance Optimization](#performance-optimization)
5. [Architecture Patterns](#architecture-patterns)
6. [CI/CD Integration](#cicd-integration)

---

## Git Worktree Advanced Scenarios

### Syncing Worktree with Main

**Scenario**: Main branch has advanced while you're working in a worktree.

**Solution: Rebase** (cleaner history)
```bash
# In your worktree
cd .worktrees/FEAT-056

# Fetch latest from main
git fetch origin main

# Rebase your changes on top of main
git rebase origin/main

# If conflicts, resolve and continue
git rebase --continue

# Or abort if too complex
git rebase --abort
```

**Solution: Merge** (preserves history)
```bash
# In your worktree
cd .worktrees/FEAT-056

# Merge main into your branch
git merge origin/main

# Resolve conflicts if any
git commit
```

**When to use which:**
- **Rebase**: Clean linear history, easier to review
- **Merge**: Preserves complete history, safer for shared branches

### Multiple Worktrees for Same Feature

**Scenario**: Need to test different approaches for same feature.

```bash
# Create worktrees for different approaches
git worktree add .worktrees/FEAT-056-approach-a -b FEAT-056-approach-a
git worktree add .worktrees/FEAT-056-approach-b -b FEAT-056-approach-b

# Work in both
cd .worktrees/FEAT-056-approach-a  # Implement approach A
cd .worktrees/FEAT-056-approach-b  # Implement approach B

# Compare results, pick winner
git diff FEAT-056-approach-a FEAT-056-approach-b

# Merge winner to main
git checkout main
git merge --no-ff FEAT-056-approach-a

# Clean up loser
git worktree remove .worktrees/FEAT-056-approach-b
git branch -D FEAT-056-approach-b
```

### Stashing Work in Worktrees

```bash
# Save work in progress
git stash push -m "WIP: filtering logic"

# List stashes
git stash list

# Apply stash later
git stash pop

# Apply stash without removing
git stash apply stash@{0}
```

### Recovering from Worktree Issues

**Scenario**: Worktree is corrupted or out of sync.

```bash
# List worktrees
git worktree list

# Remove corrupted worktree (WARNING: loses uncommitted changes)
git worktree remove .worktrees/FEAT-056 --force

# Recreate from existing branch
git worktree add .worktrees/FEAT-056 FEAT-056

# Or prune stale worktree references
git worktree prune
```

---

## Merge Conflict Resolution

### Understanding Conflict Markers

```python
<<<<<<< HEAD  # Current branch (main)
def process_data(data):
    return data.upper()
=======  # Separator
def process_data(data, transform=True):
    return data.upper() if transform else data
>>>>>>> FEAT-056  # Your branch
```

**Markers:**
- `<<<<<<< HEAD`: Start of main branch version
- `=======`: Separator between versions
- `>>>>>>> FEAT-056`: End of your branch version

### Resolution Strategy

**1. Understand both versions**
```bash
# View file before conflict
git show HEAD:src/module.py  # Main version
git show FEAT-056:src/module.py  # Your version
```

**2. Decide resolution**

**Option A**: Keep main version
```python
def process_data(data):
    return data.upper()
```

**Option B**: Keep your version
```python
def process_data(data, transform=True):
    return data.upper() if transform else data
```

**Option C**: Merge both (often best)
```python
def process_data(data, transform=True):
    # Merged: parameter from FEAT-056, logic from both
    result = data.upper() if transform else data
    return result
```

**3. Remove conflict markers**
```bash
# Remove <<<<<<, =======, >>>>>> lines completely
# Save the file
```

**4. Test resolution**
```bash
# Verify syntax
python -m py_compile src/module.py

# Run tests
pytest tests/unit/test_module.py -v
```

**5. Mark as resolved**
```bash
git add src/module.py
```

**6. Complete merge**
```bash
git commit  # Auto-generates merge commit message
```

### Common Conflict Zones

**CHANGELOG.md conflicts**

**Strategy**: Keep both entries, order by date or feature ID

```markdown
<<<<<<< HEAD
## 2025-11-22
- FEAT-055: Git Storage
=======
## 2025-11-22
- FEAT-056: Advanced Filtering
>>>>>>> FEAT-056
```

**Resolution**:
```markdown
## 2025-11-22
- FEAT-055: Git Storage
- FEAT-056: Advanced Filtering
```

**src/core/server.py conflicts** (common due to size)

**Strategy**: Merge both methods/changes

```python
<<<<<<< HEAD
def method_a(self):
    # Implementation from main
    pass
=======
def method_b(self):
    # Implementation from FEAT-056
    pass
>>>>>>> FEAT-056
```

**Resolution**: Keep both methods
```python
def method_a(self):
    # Implementation from main
    pass

def method_b(self):
    # Implementation from FEAT-056
    pass
```

**TODO.md conflicts**

**Strategy**: Merge task lists carefully

```markdown
<<<<<<< HEAD
- [ ] FEAT-055: Git Storage
- [ ] FEAT-057: UX Improvements
=======
- [ ] FEAT-055: Git Storage
- [ ] FEAT-056: Advanced Filtering
>>>>>>> FEAT-056
```

**Resolution**: Keep all unique tasks
```markdown
- [ ] FEAT-055: Git Storage
- [ ] FEAT-056: Advanced Filtering
- [ ] FEAT-057: UX Improvements
```

### Prevention Strategies

**1. Merge frequently**
```bash
# Sync with main daily
cd .worktrees/FEAT-056
git fetch origin main
git merge origin/main
```

**2. Small changesets**
- Smaller PRs = fewer conflicts
- Focus on one feature at a time

**3. Coordinate with team**
- Check IN_PROGRESS.md for overlapping work
- Communicate in task notes

**4. Avoid editing same lines**
- Add new code instead of modifying existing
- Extract to new modules instead of changing shared code

---

## Multi-Agent Coordination

### Dependency Management

**Scenario**: FEAT-057 depends on FEAT-056

**Critical Rule**: Each task exists in exactly ONE file at a time. See `ORCHESTRATION.md`.

**FEAT-056 in IN_PROGRESS.md** (being worked on):
```markdown
### [FEAT-056]: Advanced Filtering
**Assigned**: Agent A
**Status**: In Progress (80% complete)
```

**FEAT-057 in TODO.md** (waiting, not yet started):
```markdown
- [ ] **FEAT-057**: UX Discoverability (~1 week)
  - **Blocked By**: FEAT-056
```

**When FEAT-056 completes:**
1. FEAT-056 moves: IN_PROGRESS → REVIEW → TESTING → merged → removed from tracking
2. FEAT-057 is picked: DELETE from TODO.md, ADD to IN_PROGRESS.md
3. Agent syncs worktree: `git merge origin/main`
4. Agent works on FEAT-057

**Remember**: "Move" = delete from source + add to destination. Never duplicate entries.

### Parallel Work on Different Modules

**Best Case**: No conflicts

```
Agent A: src/search/filters.py (new file)
Agent B: src/memory/suggester.py (new file)
```

**Strategy**: Work independently, merge in any order

### Parallel Work on Same Module

**Challenge**: Both modify `src/core/server.py`

**Strategy:**
1. **Coordinate timing**: Agent A merges first
2. **Agent B rebases**: `git rebase origin/main` after A merges
3. **Resolve conflicts**: Agent B resolves any conflicts
4. **Test thoroughly**: Ensure both features work together

**Communication in IN_PROGRESS.md:**
```markdown
### [FEAT-056]: Advanced Filtering
**Assigned**: Agent A
**Files**: src/core/server.py (add search_code filters)
**Status**: Moving to REVIEW.md soon
**Note**: FEAT-057 will rebase after this merges

### [FEAT-057]: UX Discoverability
**Assigned**: Agent B
**Files**: src/core/server.py (add suggest_queries method)
**Status**: Will rebase after FEAT-056 merges
```

(Both tasks shown here because both are actively being worked on - each exists only in IN_PROGRESS.md)

### Capacity Management

**Rule**: Maximum 6 concurrent tasks

**Enforcement:**
```bash
# Check IN_PROGRESS.md before starting
grep -c "###" IN_PROGRESS.md  # Should be ≤6

# If at capacity, complete existing work first
```

**Priority:**
1. Complete nearly-done tasks (80%+)
2. Unblock blocked tasks
3. Start new high-priority tasks

---

## Performance Optimization

### Indexing Optimization

**Enable all performance features:**

```bash
# In .env
CLAUDE_RAG_ENABLE_PARALLEL_EMBEDDINGS=true
CLAUDE_RAG_EMBEDDING_BATCH_SIZE=100
CLAUDE_RAG_ENABLE_INCREMENTAL_INDEXING=true
CLAUDE_RAG_ENABLE_CACHING=true

# Build Rust parser
cd rust_core && maturin develop --release && cd ..
```

**Expected performance:**
- **Parallel embeddings**: 4-8x faster (10-20 files/sec vs 3-5 files/sec)
- **Rust parser**: 6x faster (1-6ms vs 10-20ms per file)
- **Incremental caching**: 5-10x faster re-indexing (98% cache hit rate)

### Search Optimization

**Choose search mode:**

```python
# Semantic only (fastest, 7-13ms)
results = await server.search_code(query, search_mode="semantic")

# Keyword only (very fast, 3-7ms)
results = await server.search_code(query, search_mode="keyword")

# Hybrid (best quality, 10-18ms)
results = await server.search_code(query, search_mode="hybrid")
```

**Limit results:**
```python
# Return fewer results for faster response
results = await server.search_code(query, limit=10)  # Default: 50
```

### Memory Optimization

**Reduce memory usage during indexing:**

```bash
# Disable parallel embeddings (uses less memory but slower)
export CLAUDE_RAG_ENABLE_PARALLEL_EMBEDDINGS=false

# Reduce batch size
export CLAUDE_RAG_EMBEDDING_BATCH_SIZE=32  # Default: 100
```

### Database Optimization

**Qdrant optimization** (in `docker-compose.yml`):

```yaml
services:
  qdrant:
    image: qdrant/qdrant:latest
    environment:
      QDRANT__SERVICE__GRPC_PORT: 6334
      QDRANT__SERVICE__HTTP_PORT: 6333
    ulimits:
      nofile:
        soft: 65536
        hard: 65536
    mem_limit: 4g  # Increase for large projects
    volumes:
      - ./qdrant_storage:/qdrant/storage  # Persist data
```

---

## Architecture Patterns

### Adding New MCP Tools

**1. Define tool in server.py:**

```python
# In src/core/server.py

async def my_new_tool(
    self,
    param1: str,
    param2: Optional[int] = None
) -> Dict[str, Any]:
    """
    Brief description of what tool does.

    Args:
        param1: Description of param1
        param2: Description of param2

    Returns:
        Dictionary with results
    """
    # Implementation
    result = await self._process(param1, param2)
    return {"status": "success", "result": result}
```

**2. Register in mcp_server.py:**

```python
# In src/mcp_server.py

@app.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
    if name == "my_new_tool":
        result = await memory_server.my_new_tool(
            param1=arguments["param1"],
            param2=arguments.get("param2")
        )
        return [TextContent(type="text", text=f"Result: {result}")]
```

**3. Add tool metadata:**

```python
# In src/mcp_server.py (tools list)

Tool(
    name="my_new_tool",
    description="Brief description of tool",
    inputSchema={
        "type": "object",
        "properties": {
            "param1": {"type": "string", "description": "Description"},
            "param2": {"type": "integer", "description": "Description"}
        },
        "required": ["param1"]
    }
)
```

**4. Write tests:**

```python
# tests/unit/test_my_new_tool.py

@pytest.mark.asyncio
async def test_my_new_tool_success(server):
    result = await server.my_new_tool(param1="test")
    assert result["status"] == "success"
```

### Adding New CLI Commands

**1. Create command module:**

```python
# src/cli/my_command.py

import asyncio
from ..core.server import MemoryRAGServer

async def my_command(args):
    """Execute my command."""
    server = MemoryRAGServer()
    await server.initialize()

    result = await server.my_new_tool(
        param1=args.param1,
        param2=args.param2
    )

    print(f"Result: {result}")

def add_my_command_parser(subparsers):
    """Add my command to CLI."""
    parser = subparsers.add_parser(
        "mycommand",
        help="Brief description"
    )
    parser.add_argument("param1", help="Description")
    parser.add_argument("--param2", type=int, help="Description")
    parser.set_defaults(func=lambda args: asyncio.run(my_command(args)))
```

**2. Register in __main__.py:**

```python
# src/cli/__main__.py

from .my_command import add_my_command_parser

# In main()
add_my_command_parser(subparsers)
```

---

## CI/CD Integration

### GitHub Actions Example

```yaml
# .github/workflows/test.yml

name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    services:
      qdrant:
        image: qdrant/qdrant:latest
        ports:
          - 6333:6333

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.13'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt

      - name: Run tests
        run: |
          pytest tests/ -n auto --cov=src --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          file: ./coverage.xml
```

### Pre-Commit Hooks

```bash
# .git/hooks/pre-commit (create this file)

#!/bin/bash
set -e

echo "Running pre-commit checks..."

# Run verification script
python scripts/verify-complete.py

# If verification fails, prevent commit
if [ $? -ne 0 ]; then
    echo "❌ Pre-commit verification failed"
    echo "Fix issues or use 'git commit --no-verify' to bypass"
    exit 1
fi

echo "✅ Pre-commit verification passed"
```

```bash
# Make it executable
chmod +x .git/hooks/pre-commit
```

---

## Next Steps

You've mastered the advanced topics! Now you can:

1. **Handle complex scenarios** with confidence
2. **Coordinate effectively** in multi-agent environments
3. **Optimize performance** for large-scale projects
4. **Extend the system** with new tools and commands

**Further Reading:**
- `ORCHESTRATION.md` - Multi-agent orchestration workflow (authoritative reference)
- `CLAUDE.md` - Quick reference and key commands
- `planning_docs/` - Feature-specific implementation details
- `docs/ARCHITECTURE.md` - System design deep dive

**Ready to contribute?** Pick a challenging task from `TODO.md` and apply these advanced techniques!
