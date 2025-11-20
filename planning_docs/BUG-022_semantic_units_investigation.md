# BUG-022: Code Indexer Extracts Zero Semantic Units

## TODO Reference
- ID: BUG-022
- Severity: HIGH
- Component: Code indexing / parsing

## Objective
Fix code indexer to properly extract semantic units (functions, classes, methods) from source files.

## Current State
```bash
$ python -m src.cli index ./src/core --project-name test
✅ Indexed 11 files
❌ Semantic units: 0  # Should be hundreds!
```

## Root Cause Analysis

### Investigation Results
✅ Parser is working correctly
✅ Parser is extracting units correctly
✅ Storage backend is working correctly

❌ **ROOT CAUSE: Path filtering logic is too aggressive**

**Location:** `src/memory/incremental_indexer.py:436`

**Problem:** The code filters out ALL paths containing any part that starts with `.`:
```python
files_to_index = [
    f for f in all_files
    if not any(part.startswith(".") for part in f.parts)
]
```

This breaks when:
1. Running from git worktrees (`.worktrees/BUG-022/...`)
2. Indexing any project with dots in parent directories
3. Using paths like `/home/.config/project/...`

**Example:**
```
Path: /Users/elliot/.../claude-memory-server/.worktrees/BUG-022/src/core/exceptions.py
Parts: [..., '.worktrees', 'BUG-022', 'src', 'core', 'exceptions.py']
Result: FILTERED OUT (because '.worktrees' starts with '.')
```

### Solution
Only filter out known unwanted directories, not all paths with dots. Use a blocklist approach instead of checking all path parts.

**Directories to filter:**
- `.git` - Git repository internals
- `.venv`, `venv`, `.virtualenv` - Python virtual environments
- `__pycache__` - Python bytecode cache
- `node_modules` - Node.js dependencies
- `.pytest_cache` - Pytest cache
- `.mypy_cache` - Mypy type checker cache
- `.tox` - Tox test environments

## Implementation Plan

1. ✅ Identify root cause (path filtering too aggressive)
2. ✅ Replace aggressive filter with targeted blocklist
3. ✅ Test with worktree paths
4. ✅ Test with actual indexing
5. ⏭️ Update tests to cover this case
6. ⏭️ Update CHANGELOG.md
7. ⏭️ Commit and merge

## Testing Results

**Before Fix:**
```
Path: .worktrees/BUG-022/src/core/exceptions.py
Filtered: ✅ (incorrectly, because .worktrees starts with .)
Files indexed: 0
Units extracted: 0
```

**After Fix:**
```
Path: .worktrees/BUG-022/src/core/exceptions.py
Filtered: ❌ (correctly, only excluded dirs in relative path checked)
Files indexed: 11
Units extracted: 867 ✅
```

## Completion Summary

**Status:** ✅ Fixed
**Date:** 2025-11-20
**Implementation Time:** 1 hour

### What Was Changed
- Modified path filtering logic in `src/memory/incremental_indexer.py:433-451`
- Changed from checking ALL path parts for dots to only checking relative paths within indexed directory
- Used targeted blocklist of common unwanted directories (.git, .venv, __pycache__, etc.)
- Added inline comment referencing BUG-022

### Impact
- **Functionality:** Code indexing now works from git worktrees and directories with dots
- **Scope:** Fixes indexing for any project with dots in parent directories (common on Linux: /home/.config/...)
- **Results:** 867 semantic units extracted from 11 files (was 0 before)

### Files Changed
- Modified: `src/memory/incremental_indexer.py` (lines 433-451)
- Updated: `planning_docs/BUG-022_semantic_units_investigation.md`
