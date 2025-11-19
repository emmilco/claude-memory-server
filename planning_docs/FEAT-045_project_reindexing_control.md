# FEAT-045: Project Reindexing Control

## TODO Reference
- TODO.md: "FEAT-045: Project Reindexing Control (~2 days)"
- Implement `reindex_project` MCP tool
- Force full re-index (bypass incremental cache)
- Option to clear existing index first
- Progress tracking and cancellation support
- Tests: full reindex, cache clearing, error recovery

## Objective
Provide users with the ability to force a full re-index of a project from scratch, useful for:
- Recovering from index corruption
- Applying configuration changes
- Clearing cache issues
- Starting fresh after major code changes

## Current State
- Incremental indexing uses embedding cache (98% hit rate)
- No way to force full re-index
- No way to clear existing index before re-indexing
- Cache entries persist indefinitely (with 30-day TTL)

## Implementation Plan

### Phase 1: Server Method
- [ ] Add `reindex_project()` method to MemoryRAGServer
- [ ] Parameters: project_name, clear_existing, bypass_cache, progress_callback
- [ ] Clear existing index if requested (delete all CODE memories for project)
- [ ] Clear cache entries for project files if bypass_cache=True
- [ ] Call incremental indexer with cache bypass flag
- [ ] Track progress and support cancellation

### Phase 2: Cache Bypass Support
- [ ] Add `bypass_cache` parameter to IncrementalIndexer.index_file()
- [ ] Pass bypass flag to embedding generator
- [ ] Ensure embeddings are regenerated when cache is bypassed
- [ ] Update cache after generating new embeddings

### Phase 3: MCP Tool
- [ ] Add `reindex_project` MCP tool to server.py
- [ ] Expose all parameters (project_name, clear_existing, bypass_cache)
- [ ] Return progress updates and final stats

### Phase 4: Testing
- [ ] Test full reindex without clearing (incremental)
- [ ] Test full reindex with clearing (fresh start)
- [ ] Test cache bypass functionality
- [ ] Test progress tracking
- [ ] Test error recovery (interrupted reindex)

## Progress Tracking

### Completed
- [x] Created planning document

### In Progress
- [ ] Implementing server method

### Pending
- [ ] Cache bypass support
- [ ] MCP tool
- [ ] Testing

## Notes & Decisions

### Clear Existing vs Bypass Cache
- **Clear existing**: Delete all indexed units for the project (fresh start)
- **Bypass cache**: Skip cache lookups, regenerate all embeddings (cache stays intact)
- Both can be combined for a complete reset

### Progress Tracking
Use existing progress callback system from IncrementalIndexer:
```python
progress_callback(current, total, current_file, error_info)
```

### Cancellation Support
Not strictly required for MVP but nice to have. Can be added in future iteration.

## Test Cases

### reindex_project
1. Reindex existing project (incremental mode)
2. Reindex with clear_existing=True (fresh start)
3. Reindex with bypass_cache=True (regenerate embeddings)
4. Reindex with both flags=True (complete reset)
5. Reindex non-existent project (error handling)
6. Progress tracking accuracy
7. Final stats correctness

## Code Snippets

### Server Method Signature
```python
async def reindex_project(
    self,
    project_name: str,
    directory: str,
    clear_existing: bool = False,
    bypass_cache: bool = False,
    progress_callback: Optional[callable] = None,
) -> Dict[str, Any]:
    """
    Force re-indexing of a project.

    Args:
        project_name: Project to reindex
        directory: Directory path to index
        clear_existing: Delete existing index first
        bypass_cache: Bypass embedding cache (regenerate all)
        progress_callback: Progress updates

    Returns:
        {
            "project_name": str,
            "files_indexed": int,
            "units_indexed": int,
            "time_elapsed": float,
            "cache_bypassed": bool,
            "index_cleared": bool,
        }
    """
```

### Cache Bypass in Indexer
```python
# In IncrementalIndexer.index_file()
if bypass_cache:
    # Force regeneration
    embeddings = await self.embedding_generator.batch_generate(
        contents,
        show_progress=False,
        bypass_cache=True,  # New parameter
    )
else:
    # Normal (cached) generation
    embeddings = await self.embedding_generator.batch_generate(
        contents,
        show_progress=False,
    )
```

## Implementation Strategy

1. **Start with server method** - Core reindexing logic
2. **Add cache bypass** - Modify embedding generator
3. **Add MCP tool** - Expose functionality
4. **Test thoroughly** - All scenarios
5. **Document** - Update CHANGELOG and API docs

## Next Steps

1. Implement `reindex_project()` in MemoryRAGServer
2. Add logic to clear existing index (delete CODE memories)
3. Add cache bypass parameter to embedding generator
4. Create MCP tool
5. Write comprehensive tests
6. Update documentation
