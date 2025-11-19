# FEAT-039: Cross-Project Consent Tools

## TODO Reference
- TODO.md: "FEAT-039: Cross-Project Consent Tools (~2-3 days)"
- Implement opt_in_cross_project MCP tool
- Implement opt_out_cross_project MCP tool
- Implement list_opted_in_projects MCP tool
- Create CrossProjectConsentManager class
- Store consent preferences persistently
- Integrate with existing search_all_projects tool
- Add comprehensive tests (consent workflow, privacy enforcement)

## Objective
Implement privacy controls for cross-project search functionality, allowing users to explicitly opt-in/opt-out projects from being included in cross-project searches. This addresses a critical gap where the API documentation promises this feature but it's not yet implemented.

## Current State
- `search_all_projects()` tool exists and works
- API documentation (docs/API.md) describes consent tools but they're not implemented
- No persistent storage for consent preferences
- No CrossProjectConsentManager class

## Implementation Plan

### Phase 1: CrossProjectConsentManager Class
- [ ] Create `src/memory/cross_project_consent.py`
- [ ] Implement CrossProjectConsentManager with SQLite-based storage
- [ ] Methods:
  - `opt_in(project_name: str) -> Dict[str, Any]`
  - `opt_out(project_name: str) -> Dict[str, Any]`
  - `is_opted_in(project_name: str) -> bool`
  - `list_opted_in_projects() -> List[str]`
  - `get_consent_stats() -> Dict[str, Any]`
- [ ] Store preferences in ~/.claude-rag/consent.db (SQLite)

### Phase 2: MCP Tools in server.py
- [ ] Add `opt_in_cross_project(project_name: str)` MCP tool
- [ ] Add `opt_out_cross_project(project_name: str)` MCP tool
- [ ] Add `list_opted_in_projects()` MCP tool
- [ ] Initialize ConsentManager in MemoryRAGServer.__init__()
- [ ] Integrate consent checking with `search_all_projects()`

### Phase 3: Integration
- [ ] Modify `search_all_projects()` to respect consent
- [ ] Only search projects that are opted-in
- [ ] Return consent status in search results metadata

### Phase 4: Testing
- [ ] Create `tests/unit/test_cross_project_consent.py`
- [ ] Test opt-in/opt-out workflow
- [ ] Test persistent storage
- [ ] Test integration with search_all_projects
- [ ] Test privacy enforcement (opted-out projects excluded)
- [ ] Test edge cases (duplicate opt-in, non-existent projects, etc.)

## Progress Tracking

### Completed
- [x] Created planning document

### In Progress
- [ ] Implementing CrossProjectConsentManager

### Pending
- [ ] MCP tools
- [ ] Integration with search_all_projects
- [ ] Testing

## Notes & Decisions

### Storage Design
Use SQLite database at `~/.claude-rag/consent.db` with schema:
```sql
CREATE TABLE project_consent (
    project_name TEXT PRIMARY KEY,
    opted_in BOOLEAN NOT NULL DEFAULT 1,
    opted_in_at TIMESTAMP,
    opted_out_at TIMESTAMP,
    updated_at TIMESTAMP NOT NULL
);
```

### Default Behavior
- **NEW projects:** Opt-in by default (privacy-friendly but user-controlled)
- **Explicit opt-out:** User can explicitly opt-out specific projects
- **search_all_projects:** Only searches opted-in projects

### Integration Points
- `search_all_projects()` in server.py needs to filter projects by consent
- Each project search should log whether consent was checked
- Return consent status in search metadata for transparency

## Test Cases

### CrossProjectConsentManager
1. Opt-in new project (should create entry and set opted_in=True)
2. Opt-out existing project (should update entry and set opted_in=False)
3. Re-opt-in previously opted-out project
4. Check consent status for opted-in project (should return True)
5. Check consent status for opted-out project (should return False)
6. Check consent status for non-existent project (should return False - default)
7. List all opted-in projects (should return correct list)
8. Persistence (restart and verify consent persists)

### MCP Tools
9. Call opt_in_cross_project MCP tool
10. Call opt_out_cross_project MCP tool
11. Call list_opted_in_projects MCP tool

### Integration with search_all_projects
12. Search with all projects opted-in (should search all)
13. Search with some projects opted-out (should exclude those)
14. Search with all projects opted-out (should return empty results)
15. Verify consent status in search metadata

## Implementation Strategy

1. **Start with ConsentManager** - Core consent logic and storage
2. **Add MCP tools** - Expose functionality via MCP
3. **Integrate with search** - Modify search_all_projects
4. **Test thoroughly** - All consent workflows
5. **Update documentation** - Ensure API.md is accurate

## Next Steps

1. Create `src/memory/cross_project_consent.py`
2. Implement CrossProjectConsentManager with all methods
3. Add MCP tools to server.py
4. Integrate consent checking into search_all_projects
5. Write comprehensive tests
6. Update API.md if needed
