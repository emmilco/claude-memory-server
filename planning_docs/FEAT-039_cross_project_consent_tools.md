# FEAT-039: Cross-Project Consent Tools

## TODO Reference
- **ID:** FEAT-039
- **TODO.md:** Lines 47-58
- **Priority:** CRITICAL 🔥🔥🔥
- **Estimate:** 2-3 days

## Objective
Implement cross-project search privacy controls that are currently documented in API.md but missing from the actual implementation. This fixes a critical API documentation gap.

## Current State

### What Exists
- `search_all_projects` MCP tool exists and works
- API.md documents consent tools (lines 782-853)
- Multi-project infrastructure is in place

### What's Missing
- `opt_in_cross_project` MCP tool
- `opt_out_cross_project` MCP tool
- `list_opted_in_projects` MCP tool
- Persistent consent storage
- Privacy enforcement in cross-project search

### The Problem
API documentation promises privacy controls that don't exist. Users expect to control which projects are searchable across project boundaries, but currently all indexed projects are searchable by default (privacy violation).

## Implementation Plan

### Phase 1: Core Infrastructure (Day 1, ~6 hours)

#### 1.1 Create CrossProjectConsentManager Class
**File:** `src/memory/cross_project_consent.py` (~250 lines)

```python
class CrossProjectConsentManager:
    """Manages cross-project search consent preferences."""

    def __init__(self, storage_path: Path):
        """
        Args:
            storage_path: Path to consent database (SQLite)
        """
        self.storage_path = storage_path
        self.db_path = storage_path / "cross_project_consent.db"
        self._initialize_db()

    def _initialize_db(self) -> None:
        """Create consent database schema."""
        # Table: project_consent
        # Columns: project_name (TEXT PRIMARY KEY),
        #          opted_in (BOOLEAN),
        #          opted_in_at (TIMESTAMP),
        #          opted_out_at (TIMESTAMP)
        pass

    async def opt_in(self, project_name: str) -> bool:
        """Enable cross-project search for a project."""
        pass

    async def opt_out(self, project_name: str) -> bool:
        """Disable cross-project search for a project."""
        pass

    async def is_opted_in(self, project_name: str) -> bool:
        """Check if project has cross-project search enabled."""
        pass

    async def list_opted_in(self) -> List[str]:
        """Get all projects with cross-project search enabled."""
        pass

    async def get_consent_info(self, project_name: str) -> Dict[str, Any]:
        """Get detailed consent information for a project."""
        pass
```

**Key Design Decisions:**
- Use SQLite for consent storage (simple, persistent, no extra dependencies)
- Store both opt-in and opt-out timestamps for audit trail
- Default: projects are NOT opted in (privacy-first)
- Exception: current project is always searchable

#### 1.2 Database Schema
```sql
CREATE TABLE IF NOT EXISTS project_consent (
    project_name TEXT PRIMARY KEY,
    opted_in BOOLEAN NOT NULL DEFAULT 0,
    opted_in_at TIMESTAMP,
    opted_out_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_opted_in ON project_consent(opted_in);
```

### Phase 2: MCP Tool Implementation (Day 1-2, ~4 hours)

#### 2.1 Add MCP Tools to Server
**File:** `src/core/server.py`

```python
async def opt_in_cross_project(self, project_name: str) -> Dict[str, Any]:
    """
    Enable cross-project search for a specific project.

    Args:
        project_name: Name of project to opt in

    Returns:
        {
            "project_name": str,
            "opted_in": True,
            "message": str,
            "opted_in_at": ISO timestamp
        }
    """
    if not self.cross_project_consent:
        raise StorageError("Cross-project consent manager not initialized")

    # Validate project exists
    if not await self._project_exists(project_name):
        raise ValidationError(f"Project '{project_name}' not found")

    success = await self.cross_project_consent.opt_in(project_name)

    if success:
        return {
            "project_name": project_name,
            "opted_in": True,
            "message": f"Project '{project_name}' is now searchable in cross-project queries",
            "opted_in_at": datetime.now(UTC).isoformat()
        }
    else:
        raise StorageError(f"Failed to opt in project '{project_name}'")


async def opt_out_cross_project(self, project_name: str) -> Dict[str, Any]:
    """
    Disable cross-project search for a specific project.

    Args:
        project_name: Name of project to opt out

    Returns:
        {
            "project_name": str,
            "opted_in": False,
            "message": str,
            "opted_out_at": ISO timestamp
        }
    """
    # Similar to opt_in but calls opt_out
    pass


async def list_opted_in_projects(self) -> Dict[str, Any]:
    """
    List all projects that have cross-project search enabled.

    Returns:
        {
            "opted_in_projects": List[str],
            "count": int,
            "includes_current": bool
        }
    """
    if not self.cross_project_consent:
        raise StorageError("Cross-project consent manager not initialized")

    projects = await self.cross_project_consent.list_opted_in()

    return {
        "opted_in_projects": projects,
        "count": len(projects),
        "includes_current": self.project_name in projects if self.project_name else False
    }
```

#### 2.2 Helper Methods
```python
async def _project_exists(self, project_name: str) -> bool:
    """Check if a project exists in the index."""
    # Query store for project existence
    # Check both Qdrant and SQLite backends
    pass
```

### Phase 3: Privacy Enforcement (Day 2, ~4 hours)

#### 3.1 Update search_all_projects
**File:** `src/core/server.py`

Modify existing `search_all_projects` to enforce consent:

```python
async def search_all_projects(
    self,
    query: str,
    limit: int = 10,
    file_pattern: Optional[str] = None,
    language: Optional[str] = None,
    search_mode: str = "semantic"
) -> Dict[str, Any]:
    """
    Search code across all opted-in projects.

    Privacy: Only searches projects that have been explicitly opted-in
    via opt_in_cross_project. Current project is always searchable.
    """
    # Get opted-in projects
    opted_in = await self.cross_project_consent.list_opted_in()

    # Always include current project
    if self.project_name and self.project_name not in opted_in:
        opted_in.append(self.project_name)

    if not opted_in:
        return {
            "results": [],
            "count": 0,
            "projects_searched": [],
            "message": "No projects opted in for cross-project search. Use opt_in_cross_project to enable."
        }

    # Filter search to only opted-in projects
    # ... existing search logic but filtered by opted_in list
```

### Phase 4: Integration & Initialization (Day 2, ~2 hours)

#### 4.1 Update Server Initialization
**File:** `src/core/server.py` - `__init__` method

```python
def __init__(self, config: Optional[ServerConfig] = None):
    # ... existing init code ...

    # Initialize cross-project consent manager
    consent_path = Path.home() / ".claude-rag" / "consent"
    consent_path.mkdir(parents=True, exist_ok=True)
    self.cross_project_consent = CrossProjectConsentManager(consent_path)
```

#### 4.2 Update MCP Server
**File:** `src/mcp_server.py`

Register new tools in MCP tool list:
```python
{
    "name": "opt_in_cross_project",
    "description": "Enable cross-project search for a specific project",
    "inputSchema": {
        "type": "object",
        "properties": {
            "project_name": {"type": "string"}
        },
        "required": ["project_name"]
    }
},
# ... similar for opt_out and list_opted_in
```

### Phase 5: Testing (Day 3, ~6 hours)

#### 5.1 Unit Tests
**File:** `tests/unit/test_cross_project_consent.py` (~25 tests)

```python
class TestCrossProjectConsentManager:
    """Test consent manager functionality."""

    async def test_opt_in_new_project(self):
        """Test opting in a new project."""
        pass

    async def test_opt_out_project(self):
        """Test opting out a project."""
        pass

    async def test_list_opted_in(self):
        """Test listing opted-in projects."""
        pass

    async def test_is_opted_in(self):
        """Test checking opt-in status."""
        pass

    async def test_consent_persistence(self):
        """Test that consent survives restart."""
        pass

    async def test_opt_in_already_opted_in(self):
        """Test opting in an already opted-in project (idempotent)."""
        pass

    async def test_opt_out_not_opted_in(self):
        """Test opting out a project that's not opted in."""
        pass

    async def test_consent_timestamps(self):
        """Test that timestamps are recorded correctly."""
        pass
```

#### 5.2 Integration Tests
**File:** `tests/integration/test_cross_project_privacy.py` (~15 tests)

```python
class TestCrossProjectPrivacy:
    """Test privacy enforcement in cross-project search."""

    async def test_search_all_respects_consent(self):
        """Test that search_all_projects only searches opted-in projects."""
        pass

    async def test_current_project_always_searchable(self):
        """Test that current project is always included in search."""
        pass

    async def test_opt_in_enables_search(self):
        """Test that opting in makes project searchable."""
        pass

    async def test_opt_out_removes_from_search(self):
        """Test that opting out removes project from search."""
        pass

    async def test_no_opted_in_projects(self):
        """Test behavior when no projects are opted in."""
        pass

    async def test_mcp_tool_integration(self):
        """Test MCP tools work end-to-end."""
        pass
```

#### 5.3 CLI Tests
**File:** `tests/unit/test_consent_cli.py` (if CLI command added)

Test CLI commands if we add them for convenience.

### Phase 6: Documentation (Day 3, ~2 hours)

#### 6.1 Update API.md
Verify existing documentation is accurate, add examples:

```markdown
### opt_in_cross_project

**Status:** ✅ IMPLEMENTED

Enable cross-project search for a specific project.

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
  "message": "Project 'my-web-app' is now searchable in cross-project queries",
  "opted_in_at": "2025-11-17T12:00:00Z"
}
```
```

#### 6.2 Update USAGE.md
Add section on cross-project privacy:

```markdown
## Cross-Project Search Privacy

By default, projects are NOT included in cross-project searches. You must explicitly opt-in:

```python
# Opt in a project
await server.opt_in_cross_project(project_name="my-app")

# Now my-app is searchable in cross-project queries
results = await server.search_all_projects(query="authentication")

# Opt out later
await server.opt_out_cross_project(project_name="my-app")
```

**Note:** Your current project is always searchable, regardless of opt-in status.
```

## Files to Create

1. `src/memory/cross_project_consent.py` (~250 lines) - Core consent manager
2. `tests/unit/test_cross_project_consent.py` (~400 lines) - Unit tests
3. `tests/integration/test_cross_project_privacy.py` (~300 lines) - Integration tests

## Files to Modify

1. `src/core/server.py` - Add 3 MCP tools, update search_all_projects, update __init__
2. `src/mcp_server.py` - Register new MCP tools
3. `docs/API.md` - Add implementation status, update examples
4. `docs/USAGE.md` - Add privacy section

## Testing Strategy

### Test Coverage Goals
- 95%+ coverage for CrossProjectConsentManager
- 100% coverage for MCP tool methods
- Full integration test coverage for privacy enforcement

### Test Scenarios
1. **Basic Operations**
   - Opt in new project
   - Opt out project
   - List opted-in projects
   - Check opt-in status

2. **Edge Cases**
   - Opt in already opted-in project (idempotent)
   - Opt out not-opted-in project (no-op)
   - Opt in non-existent project (error)
   - Empty opted-in list

3. **Privacy Enforcement**
   - Search only includes opted-in projects
   - Current project always included
   - Opting out removes from search results
   - No projects opted in returns empty results

4. **Persistence**
   - Consent survives server restart
   - Timestamps are accurate
   - Database corruption handling

## Success Criteria

- [ ] All 3 MCP tools implemented and working
- [ ] Privacy enforcement active in search_all_projects
- [ ] 40+ tests passing (25 unit + 15 integration)
- [ ] 95%+ test coverage
- [ ] Documentation updated and accurate
- [ ] API.md matches implementation
- [ ] No regression in existing tests

## Migration Path

### For Existing Users
1. First run after upgrade: All projects are NOT opted in (privacy-first)
2. Show one-time message: "Cross-project search now requires opt-in. Use opt_in_cross_project."
3. Current project remains always searchable

### Backward Compatibility
- Existing `search_all_projects` calls work but respect consent
- No breaking changes to API
- Additive feature only

## Security Considerations

1. **Privacy First:** Default is opt-out, not opt-in
2. **Audit Trail:** Track when projects are opted in/out
3. **Validation:** Verify projects exist before allowing opt-in
4. **Isolation:** Consent database separate from main data
5. **Current Project Exception:** Always allow searching current project (user's own data)

## Performance Impact

- **Storage:** +10KB per 100 projects (consent database)
- **Search Latency:** +1-2ms (consent check via indexed query)
- **Memory:** +500KB (consent manager in memory)
- **Overall:** Negligible performance impact

## Open Questions

1. **CLI commands?** Should we add `python -m src.cli consent opt-in <project>`?
   - **Decision:** Add in follow-up PR if users request it

2. **Bulk operations?** Opt in multiple projects at once?
   - **Decision:** Not needed for MVP, add if requested

3. **Consent expiry?** Should consent expire after X months?
   - **Decision:** No expiry for MVP, permanent until explicit opt-out

## Implementation Notes

- Use async/await throughout for consistency
- Follow existing error handling patterns (ValidationError, StorageError)
- Use typing for all function signatures
- Add docstrings with examples
- Log all consent changes for audit

## Completion Checklist

- [ ] CrossProjectConsentManager implemented
- [ ] Database schema created and tested
- [ ] opt_in_cross_project MCP tool implemented
- [ ] opt_out_cross_project MCP tool implemented
- [ ] list_opted_in_projects MCP tool implemented
- [ ] search_all_projects privacy enforcement added
- [ ] Server initialization updated
- [ ] MCP server registration updated
- [ ] Unit tests written and passing (25+)
- [ ] Integration tests written and passing (15+)
- [ ] Documentation updated (API.md, USAGE.md)
- [ ] Manual testing completed
- [ ] Code review completed
- [ ] CHANGELOG.md updated
