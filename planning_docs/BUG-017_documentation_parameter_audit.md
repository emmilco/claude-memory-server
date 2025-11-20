# BUG-017: Documentation Parameter Names Incorrect

## TODO Reference
- ID: BUG-017
- Severity: MEDIUM
- Component: Documentation

## Objective
Audit and fix all documentation to use correct API parameter names.

## Known Issues from E2E Report

1. **index_codebase**: Docs say `path`, actual is `directory_path`
2. **opt_in/opt_out**: Docs say `opt_in_project()`, actual is `opt_in_cross_project()`
3. **get_stats**: Docs reference `get_stats()`, actual is `get_status()`

## Investigation Plan

1. ✅ Read E2E test report
2. ✅ Check actual MCP server API signatures
3. ✅ Audit README.md for incorrect parameter names
4. ✅ Audit API.md for incorrect parameter names
5. ✅ Audit other docs/ files
6. ✅ Create comprehensive list of corrections needed
7. ⏭️ Apply fixes to all documentation
8. ⏭️ Update CHANGELOG.md
9. ⏭️ Commit and merge

## Audit Results

### Incorrect Method Name: `get_stats` → `get_status`

**Actual API:** `async def get_status()`

**Files to fix:**
1. `README.md:350` - "**`get_stats`** - View memory and indexing statistics"
2. `docs/API.md:24` - "| `get_stats` | Get system statistics | System |"
3. `docs/TROUBLESHOOTING.md:913` - "stats = cache.get_stats()"
4. `docs/PERFORMANCE.md:330` - "stats = cache.get_stats()"
5. `TUTORIAL.md:1238` - "**get_stats** - System statistics"

**Note:** The cache.get_stats() calls in TROUBLESHOOTING.md and PERFORMANCE.md appear to be referring to cache statistics, not the MCP server method, so may be correct.

### Incorrect Method Names: opt_in/opt_out

**Actual API:**
- `async def opt_in_cross_project(project_name: str)`
- `async def opt_out_cross_project(project_name: str)`

**Need to search for any references to:**
- `opt_in_project` (should be `opt_in_cross_project`)
- `opt_out_project` (should be `opt_out_cross_project`)

**Files found:** None found in main documentation (good!)

### Parameter Name: index_codebase

**Actual API:** `async def index_codebase(directory_path: str, ...)`

**Files to check:**
- No incorrect usage found in main documentation
- Only found in bug reports (E2E_TEST_REPORT.md, BUG_FIXING_STATUS.md, TODO.md)

## Summary of Fixes Needed

Total files to fix: **3 files** (cache.get_stats() is correct - different class)

1. ✅ README.md - Changed `get_stats` to `get_status`
2. ✅ docs/API.md - Changed `get_stats` to `get_status`
3. ✅ TUTORIAL.md - Changed `get_stats` to `get_status`

**Note:** docs/TROUBLESHOOTING.md and docs/PERFORMANCE.md use `cache.get_stats()` which is correct - it's a method on the `EmbeddingCache` class, not the MCP server.

## Completion Summary

**Status:** ✅ Fixed
**Date:** 2025-11-20
**Implementation Time:** 30 minutes

### What Was Changed
- Fixed method name from `get_stats` to `get_status` in 3 documentation files
- Verified cache.get_stats() usage is correct (different class)

### Impact
- **User Experience:** Users following documentation will now use correct method names
- **Scope:** Fixes all user-facing documentation
- **Accuracy:** Documentation now matches actual API

### Files Changed
- Modified: `README.md` (line 350)
- Modified: `docs/API.md` (line 24)
- Modified: `TUTORIAL.md` (line 1238)
- Created: `planning_docs/BUG-017_documentation_parameter_audit.md`
