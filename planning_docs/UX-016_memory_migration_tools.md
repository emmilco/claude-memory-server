# UX-016: Memory Migration Tools

## TODO Reference
- TODO.md: "Memory migration tools (~1-2 days)"

## Objective
Implement memory migration and transformation tools to allow users to:
1. Move memories between scopes (global ↔ project)
2. Bulk reclassify memories (change context level)
3. Merge duplicate memories
4. Export/import with project context preservation

## Requirements (from TODO.md)

### Core Features
- Move memory between scopes (global ↔ project)
- Bulk reclassification (change context level)
- Memory merging (combine duplicate memories)
- Memory export/import with project context

## Current State

### Existing Infrastructure
- **Memory Model:** `src/core/models.py` has MemoryUnit with:
  - `project_name: Optional[str]` - for project scoping
  - `context_level: ContextLevel` - CRITICAL/CORE/DETAIL/ARCHIVE
  - `category: MemoryCategory` - CONVERSATION/CODE/DOCUMENTATION/etc.
- **Storage Backends:** Both SQLite and Qdrant support:
  - Updating memories via store()
  - Retrieving memories by ID
  - Searching with filters
- **Export/Import:** FEAT-038 implemented export/import but without specific migration focus

### What's Missing
- Scope migration methods (change project_name)
- Bulk update methods (change context_level or category)
- Duplicate detection and merging logic
- Migration-focused CLI commands

## Implementation Plan

### Phase 1: Storage Backend Migration Methods
- [ ] Add `migrate_memory_scope()` to stores
  - [ ] Change project_name from one value to another
  - [ ] Support global ↔ project migration (None ↔ "project-name")
- [ ] Add `bulk_update_context_level()` to stores
  - [ ] Update context_level for multiple memories
  - [ ] Support filtering by project, category, date range
- [ ] Add `find_duplicate_memories()` to stores
  - [ ] Detect similar content (embedding similarity)
  - [ ] Return candidate groups for merging
- [ ] Add `merge_memories()` to stores
  - [ ] Combine multiple memories into one
  - [ ] Preserve metadata from all sources

### Phase 2: MCP Tools in Server
- [ ] Add `migrate_memory_scope(memory_id, new_project_name)` method
  - [ ] Validate memory exists
  - [ ] Update project scope
  - [ ] Return confirmation
- [ ] Add `bulk_reclassify(filters, new_context_level)` method
  - [ ] Filter memories by criteria
  - [ ] Update context level in bulk
  - [ ] Return count updated
- [ ] Add `find_duplicates(project_name, similarity_threshold)` method
  - [ ] Search for similar memories
  - [ ] Return duplicate groups
- [ ] Add `merge_memories(memory_ids, keep_metadata_from)` method
  - [ ] Combine memories
  - [ ] Delete duplicates
  - [ ] Return merged memory

### Phase 3: CLI Commands
- [ ] Create `src/cli/migrate_command.py` with subcommands:
  - [ ] `migrate scope <memory-id> --to-project <name>` - Change scope
  - [ ] `migrate scope <memory-id> --to-global` - Move to global
  - [ ] `migrate reclassify --project <name> --from <level> --to <level>` - Bulk reclassify
  - [ ] `migrate find-duplicates --project <name> --threshold 0.95` - Find duplicates
  - [ ] `migrate merge <id1> <id2> ...` - Merge memories

### Phase 4: Testing
- [ ] Unit tests for migration methods
- [ ] Integration tests for bulk operations
- [ ] CLI command tests

## Design Decisions

### Scope Migration
- Global memories have `project_name = None`
- Project memories have `project_name = "name"`
- Migration validates target project exists (if not global)
- Preserves all other metadata

### Bulk Reclassification
- Support filtering by:
  - Project name
  - Current context level
  - Category
  - Date range
- Atomic operations where possible
- Return count of updated memories

### Duplicate Detection
- Use embedding similarity (cosine similarity)
- Default threshold: 0.95 (95% similar)
- Group by similarity clusters
- Present for user review before merging

### Memory Merging
- Combine content intelligently:
  - Concatenate if different
  - Keep unique parts if similar
- Preserve provenance metadata
- Allow user to choose which metadata to keep

## Success Criteria
- [ ] Can move memories between global and project scopes
- [ ] Can bulk reclassify memories by context level
- [ ] Can detect duplicate memories by similarity
- [ ] Can merge duplicate memories
- [ ] Tests pass with 85%+ coverage
- [ ] Documentation updated

## Files to Create/Modify

**Create:**
- `src/cli/migrate_command.py` - CLI for migration operations
- `tests/unit/test_memory_migration.py` - Unit tests
- `planning_docs/UX-016_memory_migration_tools.md` - This file

**Modify:**
- `src/store/sqlite_store.py` - Add migration methods
- `src/store/qdrant_store.py` - Add migration methods
- `src/core/server.py` - Add MCP tools for migration
- `CHANGELOG.md` - Document feature

## Progress Tracking
- [x] Phase 1: Storage Backend Migration Methods (COMPLETE)
  - Added `migrate_memory_scope()` to SQLite and Qdrant
  - Added `bulk_update_context_level()` to SQLite and Qdrant
  - Added `find_duplicate_memories()` to SQLite and Qdrant
  - Added `merge_memories()` to SQLite and Qdrant
- [x] Phase 2: MCP Tools (COMPLETE - 2025-11-18)
  - Added `migrate_memory_scope()` to server.py
  - Added `bulk_reclassify()` to server.py
  - Added `find_duplicate_memories()` to server.py
  - Added `merge_memories()` to server.py
  - All methods include read-only mode protection
  - Proper error handling and logging
- [x] Phase 4: Testing (COMPLETE - 2025-11-18)
  - Created `tests/unit/test_memory_migration.py` with 18 tests
  - All tests passing (5 migrate, 4 reclassify, 3 find duplicates, 5 merge, 1 integration)
  - Tests cover success paths, error handling, read-only mode, and edge cases
- [ ] Phase 3: CLI Commands (DEFERRED - can be added later if needed)
