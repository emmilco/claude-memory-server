# FEAT-044: Memory Export/Import Tools

## TODO Reference
- TODO.md: "Memory Export/Import Tools (~3-4 days)"

## Objective
Implement MCP tools to export and import memories with support for multiple formats, filtering, and conflict resolution.

## Requirements (from TODO.md)

### Export Tool
- [ ] Implement `export_memories` MCP tool
- [ ] Export formats: JSON (structured), Markdown (human-readable), portable archive
- [ ] Support filtering for selective export
- [ ] Preserve metadata: IDs, timestamps, provenance

### Import Tool
- [ ] Implement `import_memories` MCP tool
- [ ] Import with conflict resolution (skip, overwrite, merge)
- [ ] Validation and error handling

### Testing
- [ ] Export/import workflows
- [ ] Format validation
- [ ] Conflict resolution
- [ ] Metadata preservation

## Implementation Plan

### Phase 1: Core Export Functionality
1. Add `export_memories()` method to `src/core/server.py`
   - Accept filters (same as list_memories)
   - Support format parameter: "json", "markdown", "archive"
   - Return file path or content

2. JSON Export Format:
   ```json
   {
     "version": "1.0",
     "exported_at": "2025-11-18T12:00:00Z",
     "total_count": 150,
     "memories": [
       {
         "id": "mem_123",
         "content": "...",
         "category": "technical",
         "importance": 0.8,
         "tags": ["python", "async"],
         "metadata": {...},
         "created_at": "...",
         "updated_at": "...",
         "provenance": {...}
       }
     ]
   }
   ```

3. Markdown Export Format:
   ```markdown
   # Memory Export
   Exported: 2025-11-18 12:00:00
   Total Memories: 150

   ## Memory: mem_123
   **Category:** technical
   **Importance:** 0.8
   **Tags:** python, async
   **Created:** 2025-11-18 10:00:00

   Content goes here...

   ---
   ```

4. Archive Format (ZIP):
   - memories.json (structured data)
   - memories.md (human-readable)
   - metadata.json (export info)

### Phase 2: Core Import Functionality
1. Add `import_memories()` method to `src/core/server.py`
   - Accept file path or content
   - Detect format automatically
   - Support conflict resolution mode: "skip", "overwrite", "merge"

2. Import Logic:
   - Parse file based on format
   - Validate schema
   - For each memory:
     - Check if ID exists
     - Apply conflict resolution
     - Store or update
   - Return import summary (created, updated, skipped, errors)

3. Conflict Resolution Modes:
   - **skip**: Keep existing, don't import duplicates
   - **overwrite**: Replace existing with imported
   - **merge**: Update non-null fields, keep existing for null fields

### Phase 3: MCP Tool Registration
1. Register `export_memories` in `src/mcp_server.py`
   - Schema with filters, format, output_path parameters
   - Handler that calls server method and returns summary

2. Register `import_memories` in `src/mcp_server.py`
   - Schema with file_path, format, conflict_mode parameters
   - Handler that calls server method and returns summary

### Phase 4: Testing
1. Create `tests/unit/test_export_import.py`
   - Test JSON export/import
   - Test Markdown export (import optional for markdown)
   - Test archive export/import
   - Test filtering during export
   - Test conflict resolution modes
   - Test metadata preservation
   - Test error handling (invalid format, missing file, etc.)

## Files to Create/Modify

### New Files
- `tests/unit/test_export_import.py` - Comprehensive test suite

### Modified Files
- `src/core/server.py` - Add export_memories() and import_memories() methods
- `src/mcp_server.py` - Register MCP tools and handlers
- `CHANGELOG.md` - Add FEAT-044 entry

## Success Criteria
- [ ] Can export memories to JSON with all metadata preserved
- [ ] Can import JSON with all three conflict modes working
- [ ] Can export to Markdown for human readability
- [ ] Can export to archive (ZIP) with multiple formats
- [ ] All filters from list_memories work for export
- [ ] Import validates schema and handles errors gracefully
- [ ] 100% test pass rate for export/import functionality
- [ ] Documentation updated in CHANGELOG.md

## Progress Tracking
- [x] Created planning document
- [x] Implemented export_memories() in server.py
- [x] Implemented import_memories() in server.py
- [x] Registered MCP tools in mcp_server.py
- [x] Created comprehensive tests (19 tests)
- [x] All tests passing (19/19)
- [x] Updated CHANGELOG.md
- [ ] Committed to feature branch
- [ ] Merged to main

## Notes

### Design Decisions
- **Format Detection**: Will auto-detect based on file extension (.json, .md, .zip)
- **File Handling**: Export will write to user-specified path or return content as string
- **Validation**: Will use JSON schema validation for imported data
- **Embeddings**: Will NOT include embeddings in export (they can be regenerated)

### Dependencies
- Uses existing store methods (retrieve, store, update, etc.)
- Uses existing validation from MemoryUnit
- May need to add utility functions for ZIP handling

### Questions/Decisions Needed
- Should we include embeddings in export? (Initial decision: NO - too large, can regenerate)
- Should archive format be optional? (Initial decision: YES - nice to have but not critical)
- Should we support CSV export? (Initial decision: NO - focus on JSON/MD first)
