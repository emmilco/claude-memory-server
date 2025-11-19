# FEAT-046: Indexed Content Visibility

## TODO Reference
- TODO.md: "FEAT-046: Indexed Content Visibility (~2-3 days)"
- Implement `get_indexed_files` and `list_indexed_units` MCP tools
- Filter by project, language, file pattern
- Show indexing metadata: last indexed, hash, unit count
- Pagination for large projects

## Objective
Provide transparency into indexed content by implementing MCP tools and store methods that allow users to:
1. List all files that have been indexed for a project
2. List specific code units (functions, classes) with detailed metadata
3. Filter results by project, language, and file patterns
4. View indexing metadata (last indexed time, file hash, unit counts)
5. Paginate results for large projects

## Current State
- Code units are stored in `memories` table with category='code'
- Metadata JSON field includes `file_path`, language, and import info
- SemanticUnits have: unit_type, name, signature, start_line, end_line, content, language, file_path
- No current way to list indexed files or units
- `get_status` only shows counts, not details

## Implementation Plan

### Phase 1: Store Methods (SQLite and Qdrant)
- [ ] Add `get_indexed_files(project_name, limit, offset)` to both stores
- [ ] Add `list_indexed_units(project_name, language, file_pattern, unit_type, limit, offset)` to both stores
- [ ] Return metadata: file_path, language, last_indexed, unit_count, file_hash

### Phase 2: MCP Tools (server.py)
- [ ] Implement `get_indexed_files()` MCP tool
- [ ] Implement `list_indexed_units()` MCP tool
- [ ] Add pagination parameters (limit, offset)
- [ ] Add filtering parameters (project, language, file_pattern, unit_type)

### Phase 3: Testing
- [ ] Unit tests for SQLite store methods (10-12 tests)
- [ ] Unit tests for Qdrant store methods (10-12 tests)
- [ ] Integration tests for MCP tools (8-10 tests)
- [ ] Test pagination and filtering
- [ ] Test with large datasets

## Progress Tracking

### Completed
- [x] Created planning document
- [x] Reviewed existing code structure
- [x] Identified metadata fields available

### In Progress
- [ ] Implementing store methods

### Pending
- [ ] MCP tool implementation
- [ ] Testing
- [ ] Documentation updates

## Notes & Decisions

### Metadata Structure
From code analysis, each CODE memory includes:
- `file_path`: Absolute path to source file
- `language`: Programming language (Python, JavaScript, etc.)
- `created_at`: Timestamp of when indexed
- `updated_at`: Timestamp of last update
- Import metadata: `dependencies`, `imports_extracted`

### Database Schema
The `memories` table has:
- `id`: Memory ID
- `content`: Code content
- `category`: 'code' for code units
- `project_name`: Project scope
- `metadata`: JSON with file_path, language, etc.
- `created_at`, `updated_at`: Timestamps

### Filtering Strategy
- **Project**: Filter by `project_name` column
- **Language**: Parse `metadata` JSON for language field
- **File pattern**: Use SQL LIKE on metadata->file_path
- **Unit type**: Parse `content` or metadata for unit_type

### Pagination
- Use SQL LIMIT and OFFSET for pagination
- Default limit: 50 items
- Max limit: 500 items
- Return total count for UI pagination

## Test Cases

### get_indexed_files
1. List all files for a project
2. Filter by language (.py, .js, .rs)
3. Pagination (offset, limit)
4. Empty result handling
5. Non-existent project
6. Large file list (1000+ files)

### list_indexed_units
1. List all units for a project
2. Filter by language
3. Filter by file pattern (*.py, src/*)
4. Filter by unit_type (function, class)
5. Pagination
6. Combined filters
7. Empty results
8. Large unit list (10000+ units)

## Code Snippets

### Store Method Signature (SQLite)
```python
async def get_indexed_files(
    self,
    project_name: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> Dict[str, Any]:
    """
    Get list of indexed files with metadata.

    Returns:
        {
            "files": [
                {
                    "file_path": str,
                    "language": str,
                    "last_indexed": str (ISO timestamp),
                    "unit_count": int,
                    "file_hash": str (if available),
                }
            ],
            "total": int,
            "limit": int,
            "offset": int,
        }
    """
```

### MCP Tool Signature
```python
async def get_indexed_files(
    self,
    project_name: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    """List all indexed files with metadata."""
```

## Implementation Strategy

1. **Start with SQLite** - Implement and test SQLite methods first
2. **Then Qdrant** - Adapt for Qdrant (may have different query patterns)
3. **Add MCP tools** - Expose store methods via MCP
4. **Test thoroughly** - Ensure pagination, filtering work correctly
5. **Document** - Update CHANGELOG.md and API docs

## Next Steps

1. Implement SQLite `get_indexed_files()` method
2. Test with sample data
3. Implement SQLite `list_indexed_units()` method
4. Test filtering and pagination
5. Replicate for Qdrant store
6. Add MCP tools to server.py
7. Write comprehensive tests
8. Update documentation
