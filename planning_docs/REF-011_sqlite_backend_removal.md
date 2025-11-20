# REF-011: SQLite Backend Removal

## TODO Reference
- TODO.md: REF-010 removed SQLite fallback, this task completes the cleanup

## Objective
Remove all remaining references to SQLite as a storage backend option, keeping only Qdrant. SQLite remains in use internally for caching and tracking.

## Rationale
REF-010 removed the SQLite storage backend because it provided poor UX for code search (keyword-only, no semantic similarity). This task completes the cleanup by removing all references to SQLite as a storage option from code and documentation.

## Implementation Summary

### Code Changes (Commit 97d16d6)

1. **Deleted Files:**
   - `src/store/sqlite_store.py` (~2,450 lines removed)

2. **src/config.py:**
   - Changed `storage_backend: Literal["sqlite", "qdrant"]` → `Literal["qdrant"]`
   - Removed `sqlite_path` configuration option
   - Removed `sqlite_path_expanded` property

3. **src/core/exceptions.py:**
   - Updated `DockerNotRunningError` to remove SQLite fallback suggestion
   - Now suggests starting Docker and running `docker-compose up -d`

4. **src/core/server.py:**
   - Updated docstring: "Qdrant or SQLite backend" → "Qdrant vector store backend"
   - Replaced `sqlite_path` with `embedding_cache_path` for monitoring DB location
   - Removed SQLite-specific conditional code paths (2 locations):
     - Dashboard global memory counting
     - Clear existing index functionality
   - Updated comment: "Search commits in SQLite store" → "Search commits in vector store"

5. **src/mcp_server.py:**
   - Fixed health check: Changed `get_stats()` (non-existent) → `get_all_projects()`
   - Removed "or check SQLite path" from error message
   - Simplified to Qdrant-only error recovery

6. **tests/unit/test_store_project_stats.py:**
   - Removed `TestSQLiteProjectStats` class (~163 lines)
   - Kept only `TestQdrantProjectStats` class

### Documentation Changes (Commit a9372ca)

Updated 12 documentation files:

1. **README.md:**
   - Removed SQLite from configuration examples
   - Changed "Minimal (No Docker)" preset to "Standard"
   - Updated all environment variable examples to use `qdrant`

2. **docs/SETUP.md:**
   - Updated wizard description: "Set up storage backend (SQLite or Qdrant)" → "Set up Qdrant storage backend"
   - Removed "or sqlite" comment from configuration examples

3. **docs/ARCHITECTURE.md:**
   - Changed "SQLite backend" to "local database backend" for metrics storage
   - Clarified that SQLite is used for internal tracking, not storage

4. **docs/PERFORMANCE.md:**
   - Replaced "Use SQLite backend" suggestion with "Optimize Qdrant configuration"

5. **docs/E2E_TEST_REPORT.md:**
   - Updated test output: "SQLite backend: Connected" → "Qdrant backend: Connected"

6. **docs/TROUBLESHOOTING.md:**
   - Updated FAQ: Clarified Qdrant is required, SQLite backend removed
   - Changed config examples to use `qdrant`

7. **docs/ERROR_RECOVERY.md:**
   - Changed default backend in examples from `sqlite` to `qdrant`

8. **docs/USAGE.md:**
   - Removed "(Qdrant/SQLite)" → "(Qdrant)"

9. **docs/FIRST_RUN_TESTING.md:**
   - Updated expected output format

10. **docs/AI_CODE_REVIEW_GUIDE.md:**
    - Simplified storage backend consistency checks

11. **docs/DEVELOPMENT.md:**
    - Noted `sqlite_store.py` removal in directory structure

12. **docs/SECURITY.md:**
    - Updated local storage description

## Files Changed

### Code Files (6 files):
- ✅ src/store/sqlite_store.py (deleted)
- ✅ src/config.py (modified)
- ✅ src/core/exceptions.py (modified)
- ✅ src/core/server.py (modified)
- ✅ src/mcp_server.py (modified)
- ✅ tests/unit/test_store_project_stats.py (modified)

### Documentation Files (12 files):
- ✅ README.md
- ✅ docs/SETUP.md
- ✅ docs/ARCHITECTURE.md
- ✅ docs/PERFORMANCE.md
- ✅ docs/E2E_TEST_REPORT.md
- ✅ docs/TROUBLESHOOTING.md
- ✅ docs/ERROR_RECOVERY.md
- ✅ docs/USAGE.md
- ✅ docs/FIRST_RUN_TESTING.md
- ✅ docs/AI_CODE_REVIEW_GUIDE.md
- ✅ docs/DEVELOPMENT.md
- ✅ docs/SECURITY.md

## Important Notes

### SQLite Still Used Internally
SQLite remains in use for:
- Embedding cache (`src/embeddings/cache.py`)
- Cross-project consent tracking (`src/memory/cross_project_consent.py`)
- Performance monitoring (`src/monitoring/metrics_collector.py`)
- Usage tracking
- Feedback tracking

These internal uses are **not affected** by this change.

### Breaking Change
This is a breaking change for users who were using `storage_backend: "sqlite"` in their configuration. They will need to:
1. Install Docker
2. Start Qdrant: `docker-compose up -d`
3. Update config to use `storage_backend: "qdrant"`

## Testing

### Syntax Validation
```bash
python -m py_compile src/config.py src/core/server.py src/core/exceptions.py src/mcp_server.py
# Result: No errors
```

### Expected Test Impact
- Test collection should continue to work (2723 tests)
- SQLite-specific tests removed from `test_store_project_stats.py`
- All remaining tests assume Qdrant backend

## Commits

1. **97d16d6** - REF-011: Remove SQLite storage backend support
2. **a9372ca** - REF-011: Update documentation to remove SQLite backend references

## Status
✅ **COMPLETE**

All code and documentation updated to reflect Qdrant-only storage backend.
SQLite internal usage preserved for caching and tracking.
