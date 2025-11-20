# REF-010: Remove SQLite Fallback, Require Qdrant

## TODO Reference
- **ID:** REF-010
- **TODO.md:** "Remove SQLite fallback, require Qdrant (~1 day)"
- **Priority:** 🔥 Tier 6 (Refactoring & Tech Debt)

## Objective
Remove SQLite fallback from the codebase and require Qdrant as the sole vector database backend for code search. This refactoring simplifies architecture, improves UX by removing misleading degraded mode, and sets clear expectations for users.

## Rationale
From EVAL-001 empirical evaluation:
- **SQLite mode provides poor UX for code search:**
  - Keyword-only search (no semantic similarity)
  - All scores return constant 0.700 (misleading)
  - Returns arbitrary results regardless of query relevance
  - No vector similarity calculation
- **Baseline (Grep/Read/Glob) is more effective than SQLite mode:**
  - Baseline: 4.5/5 quality, 100% success rate
  - SQLite mode: 1.2/5 quality, 0% success rate
- **Adds complexity without value:**
  - Graceful degradation hides the fact that semantic search isn't working
  - Users get misleading results and constant 0.700 scores
  - Better to fail fast with clear error messages

## Current State

### Files to Modify
1. `src/store/__init__.py:49-84` - SQLite fallback logic
2. `src/config.py` - ServerConfig with `allow_qdrant_fallback` option
3. `src/core/server.py` - Code search tools (add Qdrant requirement check)
4. `src/store/sqlite_store.py` - Either remove or deprecate
5. Documentation files (README.md, docs/*)
6. Test files - Update to mock Qdrant instead of using SQLite

### Key Questions
- [ ] Should we completely remove `sqlite_store.py` or keep it for non-code-search use cases (memories only)?
- [ ] Do we need migration path for existing SQLite users?
- [ ] Should we provide cloud Qdrant option or embedded vector DB alternative?

## Implementation Plan

### Phase 1: Understand Current Implementation ✅ COMPLETE
- [x] Read `src/store/__init__.py` to understand fallback logic
- [x] Read `src/config.py` to find all `allow_qdrant_fallback` references
- [x] Read `src/store/factory.py` - async version of store creation
- [x] Identified tests that rely on SQLite fallback
- [x] Found two factory functions with fallback logic

#### Key Findings:
1. **Two Factory Functions:**
   - `src/store/__init__.py::create_memory_store()` - Synchronous (14 usages)
   - `src/store/factory.py::create_store()` - Async (6 usages)
   - Both implement fallback logic

2. **Config Option:**
   - `src/config.py:50` - `allow_qdrant_fallback: bool = True`
   - Default storage_backend is "sqlite" (line 19) - should change to "qdrant"
   - Config uses env_prefix "CLAUDE_RAG_"

3. **Tests Affected:**
   - `test_graceful_degradation.py` - 15 tests specifically for fallback behavior
   - 37 total test files reference SQLiteMemoryStore
   - Tests use both factory functions

4. **Degradation Tracking:**
   - `src/core/degradation_warnings.py` - System to track degraded components
   - `add_degradation_warning()` called when fallback occurs
   - Should remove/simplify this for Qdrant requirement

### Phase 2: Remove Fallback Logic
- [ ] Remove SQLite fallback from `src/store/__init__.py`
- [ ] Update `create_memory_store()` to fail fast if Qdrant unavailable
- [ ] Add clear error message: "Start Qdrant with: docker-compose up -d"
- [ ] Remove `allow_qdrant_fallback` config option from ServerConfig
- [ ] Update config validation

### Phase 3: Update Code Search Tools
- [ ] Add Qdrant availability check in code search tools
- [ ] Fail fast with actionable error if Qdrant not available
- [ ] Update error messages to guide users to setup steps

### Phase 4: Handle SQLite Store
- [ ] Decision: Remove completely or keep for memories?
- [ ] If keeping: Add deprecation warnings
- [ ] If removing: Delete file and all references
- [ ] Update imports across codebase

### Phase 5: Update Tests
- [ ] Identify all tests using SQLite fallback
- [ ] Update to mock Qdrant instead
- [ ] Ensure 99.9%+ pass rate maintained
- [ ] Add tests for Qdrant unavailable error handling

### Phase 6: Update Documentation
- [ ] README.md - Require Qdrant in prerequisites
- [ ] docs/SETUP.md - Add Qdrant requirement
- [ ] docs/TROUBLESHOOTING.md - Qdrant setup issues
- [ ] CHANGELOG.md - Breaking change notice

### Phase 7: Add Validation Script
- [ ] Create setup validation script
- [ ] Check Qdrant availability at localhost:6333
- [ ] Provide clear setup instructions if unavailable
- [ ] Add to CLI as `validate-setup` command

### Phase 8: Testing & Verification
- [ ] Run full test suite
- [ ] Test with Qdrant running
- [ ] Test with Qdrant stopped (should fail gracefully)
- [ ] Verify error messages are clear and actionable
- [ ] Check all documentation updated

## Progress Tracking

### Completed
- [x] Created planning document
- [x] Set up worktree for REF-010

### In Progress
- [ ] Reading current implementation

### Blocked
- None

## Notes & Decisions

### Decision Log
- **2025-11-19:** Created planning doc, starting investigation

### Code Snippets
(Will add relevant code snippets as we discover them)

### Test Cases
- [ ] Test code search with Qdrant running (should work)
- [ ] Test code search with Qdrant stopped (should fail with clear error)
- [ ] Test setup validation script
- [ ] Test all existing tests still pass

## Files to Create
- `src/cli/validate_setup.py` - Setup validation script

## Files to Modify
- `src/store/__init__.py` - Remove fallback logic
- `src/config.py` - Remove allow_qdrant_fallback option
- `src/core/server.py` - Add Qdrant checks in code search tools
- `README.md` - Require Qdrant
- `docs/SETUP.md` - Require Qdrant
- `docs/TROUBLESHOOTING.md` - Qdrant issues
- `CHANGELOG.md` - Breaking change
- Multiple test files - Mock Qdrant

## Files to Delete (TBD)
- `src/store/sqlite_store.py` - If not keeping for memories

## Benefits After Completion
- ✅ Simpler architecture (one backend instead of two)
- ✅ Clear expectations (Qdrant required for code search)
- ✅ Better error messages (no silent degradation)
- ✅ No misleading degraded mode with 0.700 scores
- ✅ Easier maintenance (fewer code paths)
- ✅ Better UX (fail fast with clear guidance)

## Migration Path
- Provide clear setup instructions for Qdrant
- Consider cloud Qdrant option (Qdrant Cloud)
- Consider embedded vector DB alternative (e.g., Chroma, LanceDB)
- Document migration for existing SQLite users

## Estimated Time
- Investigation: 1-2 hours
- Implementation: 4-6 hours
- Testing: 2-3 hours
- Documentation: 1-2 hours
- **Total:** ~1 day (8-13 hours)
