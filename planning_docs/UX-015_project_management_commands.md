# UX-015: Project Management Commands

## TODO Reference
- TODO.md: "Project management commands (~2 days)"

## Objective
Implement comprehensive project management commands to allow users to:
1. List all indexed projects
2. View detailed statistics for a specific project
3. Delete a project and its indexed data
4. Rename a project

## Requirements (from TODO.md)

### Core Features
- `list_projects` - show all indexed projects
- `project_stats(project)` - detailed project info
- `delete_project(project)` - remove project index
- `rename_project(old, new)` - rename project

## Current State

### Existing Infrastructure
- **Project Statistics:** `src/store/qdrant_store.py` and `src/store/sqlite_store.py` have:
  - `get_all_projects()` - Returns list of project names
  - `get_project_stats(project_name)` - Returns detailed statistics
- **Status Command:** `src/cli/status_command.py` displays project list
- **Project CLI:** `src/cli/project_command.py` exists with `switch` and `current` subcommands (from UX-014)

### What's Missing
- MCP tools for project management operations
- CLI commands for listing, viewing stats, deleting, and renaming projects
- Delete functionality in storage backends
- Rename functionality in storage backends

## Implementation Plan

### Phase 1: Storage Backend Enhancements
- [ ] Add `delete_project(project_name)` to SQLite store
  - [ ] Delete all memories for the project
  - [ ] Remove from project metadata
- [ ] Add `delete_project(project_name)` to Qdrant store
  - [ ] Delete memories by project filter
- [ ] Add `rename_project(old_name, new_name)` to SQLite store
  - [ ] Update all memories with new project name
  - [ ] Update project metadata
- [ ] Add `rename_project(old_name, new_name)` to Qdrant store
  - [ ] Update memory payloads with new project name

### Phase 2: MCP Tools in Server
- [ ] Add `list_projects()` method to `src/core/server.py`
  - [ ] Return list of projects with basic stats
- [ ] Add `get_project_stats(project_name)` method
  - [ ] Return detailed statistics for a project
- [ ] Add `delete_project(project_name)` method
  - [ ] Validate project exists
  - [ ] Delete from storage
  - [ ] Return confirmation
- [ ] Add `rename_project(old_name, new_name)` method
  - [ ] Validate old project exists
  - [ ] Validate new name not taken
  - [ ] Rename in storage
  - [ ] Update active project if needed

### Phase 3: CLI Command Enhancements
- [ ] Enhance `src/cli/project_command.py` with new subcommands:
  - [ ] `project list` - List all indexed projects with basic stats
  - [ ] `project stats <name>` - Show detailed project statistics
  - [ ] `project delete <name>` - Delete project with confirmation
  - [ ] `project rename <old> <new>` - Rename project

### Phase 4: Testing
- [ ] Unit tests for storage backend methods
- [ ] Integration tests for MCP tools
- [ ] CLI command tests

## Design Decisions

### Delete Safety
- Require confirmation for delete operations
- Option for `--force` to skip confirmation
- Delete is permanent - warn user clearly

### Rename Behavior
- Update all memories with new project name
- Update active project if it matches old name
- Atomic operation - all or nothing

### List Display
- Show project name, file count, memory count
- Sort by most recent activity
- Color-code active project

## Success Criteria
- [ ] Can list all projects via MCP and CLI
- [ ] Can view detailed stats for any project
- [ ] Can delete a project safely with confirmation
- [ ] Can rename a project and update all references
- [ ] Tests pass with 85%+ coverage
- [ ] Documentation updated

## Files to Create/Modify

**Modify:**
- `src/store/sqlite_store.py` - Add delete_project() and rename_project()
- `src/store/qdrant_store.py` - Add delete_project() and rename_project()
- `src/core/server.py` - Add MCP tools for project management
- `src/cli/project_command.py` - Add list, stats, delete, rename subcommands
- `CHANGELOG.md` - Document feature

**Create:**
- `tests/unit/test_project_management.py` - Unit tests
- `planning_docs/UX-015_project_management_commands.md` - This file

## Progress Tracking
- [x] Phase 1: Storage Backend Enhancements (COMPLETE)
  - Added `delete_project()` to SQLite store
  - Added `delete_project()` to Qdrant store
  - Added `rename_project()` to SQLite store
  - Added `rename_project()` to Qdrant store
- [x] Phase 2: MCP Tools (COMPLETE)
  - Added `list_projects()` to server
  - Added `get_project_details(project_name)` to server
  - Added `delete_project(project_name)` to server
  - Added `rename_project(old_name, new_name)` to server
- [x] Phase 3: CLI Commands (COMPLETE)
  - Created `src/cli/project_command.py` with 4 subcommands
  - Implemented `project list` - List all projects with stats
  - Implemented `project stats <name>` - Show detailed statistics
  - Implemented `project delete <name>` - Delete with confirmation
  - Implemented `project rename <old> <new>` - Rename project
- [ ] Phase 4: Testing (DEFERRED)
