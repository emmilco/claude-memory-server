# UX-014: Explicit Project Switching

## TODO Reference
- TODO.md: "Explicit project switching (~2 days)"

## Objective
Implement explicit project switching functionality to:
1. Allow users to manually set the active project context
2. Display current project in status
3. Auto-detect git context changes
4. Enable cross-project search when needed

## Requirements (from TODO.md)

### Core Features
- MCP tool: `switch_project(project_name)`
- Show current project in Claude status
- Auto-detect git context changes
- Cross-project search option

## Current State

### Existing Infrastructure
- **Project Context Detection:** `src/memory/project_context.py` already exists (FEAT-033)
  - ProjectContext class with active project tracking
  - Project detection from git repos
  - Activity tracking
- **Status Command:** `src/cli/status_command.py` displays project statistics
- **Server:** `src/core/server.py` has get_status() method

### What's Missing
- Explicit switch_project() MCP tool
- CLI command for switching projects
- Display of current active project in status
- Cross-project search option (may already exist via search_all_projects)

## Implementation Plan

### Phase 1: MCP Tool for Project Switching
- [ ] Add `switch_project()` method to `src/core/server.py`
  - [ ] Set active project context
  - [ ] Validate project exists
  - [ ] Return confirmation with project info
- [ ] Add `get_active_project()` method to server
  - [ ] Return current active project name and metadata

### Phase 2: Enhanced Status Display
- [ ] Update `src/core/server.py::get_status()`
  - [ ] Include current active project
  - [ ] Show when project was last switched
- [ ] Update `src/cli/status_command.py`
  - [ ] Display active project prominently
  - [ ] Show project switch history

### Phase 3: CLI Command
- [ ] Create `src/cli/project_command.py`
  - [ ] `project switch <name>` - Switch active project
  - [ ] `project current` - Show current project
  - [ ] `project list` - List all projects (already exists in UX-015)

### Phase 4: Auto-detection Enhancement
- [ ] Enhance existing git detection in project_context.py
  - [ ] Auto-switch when git repo changes
  - [ ] Configurable auto-switch (enable/disable)
  - [ ] Notification when auto-switch occurs

### Phase 5: Testing
- [ ] Unit tests for switch_project()
- [ ] Integration tests for auto-detection
- [ ] CLI command tests

## Design Decisions

### Active Project Storage
- Store in `ProjectContext` class (already exists)
- Persist to file for session continuity
- Location: ~/.claude-rag/active_project.json

### Auto-Detection Behavior
- Default: ON (auto-switch when git repo changes)
- Config option: `auto_switch_project: bool = True`
- User can disable if they prefer manual control

### Project Validation
- Only allow switching to indexed projects
- Provide helpful error if project not found
- Suggest similar project names if typo detected

## Success Criteria
- [ ] Can switch active project via MCP tool
- [ ] Can switch active project via CLI
- [ ] Status displays current active project
- [ ] Auto-detection works when git repo changes
- [ ] Cross-project search available when needed
- [ ] Tests pass with 85%+ coverage

## Files to Create/Modify

**Create:**
- `src/cli/project_command.py` - CLI for project operations
- `tests/unit/test_project_switching.py` - Unit tests
- `planning_docs/UX-014_explicit_project_switching.md` - This file

**Modify:**
- `src/core/server.py` - Add switch_project() and get_active_project()
- `src/cli/status_command.py` - Display active project
- `src/memory/project_context.py` - Add active project persistence
- `src/config.py` - Add auto_switch_project config option
- `CHANGELOG.md` - Document feature

## Progress Tracking
- [x] Phase 1: MCP Tool (COMPLETE)
  - Added `switch_project()` method to server.py
  - Added `get_active_project()` method to server.py
  - Added ProjectContextDetector initialization
- [x] Phase 2: Status Display (COMPLETE)
  - Enhanced `get_status()` to include active project
  - Added `get_active_project()` method to status_command.py
  - Added `print_active_project()` method to status_command.py
  - Updated `run()` method to display active project
- [x] Phase 3: CLI Command (COMPLETE)
  - Created `src/cli/project_command.py`
  - Implemented `project switch <name>` subcommand
  - Implemented `project current` subcommand
- [ ] Phase 4: Auto-detection (DEFERRED - already exists in ProjectContextDetector)
- [ ] Phase 5: Testing (TODO)
