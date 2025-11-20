# BUG-021: PHP Parser Initialization Warning

## TODO Reference
- ID: BUG-021
- Severity: LOW
- Component: Python parser fallback

## Objective
Fix PHP parser initialization warning: "Failed to initialize php parser: module 'tree_sitter_php' has no attribute 'language'"

## Current State
Warning appears during Python parser initialization:
```
WARNING:src.memory.python_parser:Failed to initialize php parser: module 'tree_sitter_php' has no attribute 'language'
```

## Root Cause Analysis

### Investigation Results
Checked `tree_sitter_php` module attributes:
```python
>>> import tree_sitter_php
>>> dir(tree_sitter_php)
['HIGHLIGHTS_QUERY', 'INJECTIONS_QUERY', 'TAGS_QUERY', ..., 'language_php', 'language_php_only']
```

❌ **ROOT CAUSE: API mismatch - attribute is `language_php`, not `language`**

**Location:** `src/memory/python_parser.py:52`

**Problem:** Code expects all parsers to have `language` attribute, but PHP parser uses `language_php`.

**Current code:**
```python
LANGUAGE_MODULES = {
    ...
    "php": (tree_sitter_php, "language") if TREE_SITTER_AVAILABLE else None,  # ❌ Wrong
    ...
}
```

**Correct API:**
- `tree_sitter_php.language_php` - Full PHP parser
- `tree_sitter_php.language_php_only` - PHP-only (no HTML)

### Solution
Change function name from `"language"` to `"language_php"`.

## Implementation Plan

1. ✅ Identify root cause (API mismatch)
2. ✅ Update LANGUAGE_MODULES dict
3. ✅ Test PHP parser initialization
4. ⏭️ Update CHANGELOG.md
5. ⏭️ Commit and merge

## Testing Results

**Before Fix:**
```
WARNING:src.memory.python_parser:Failed to initialize php parser: module 'tree_sitter_php' has no attribute 'language'
Available parsers: ['python', 'javascript', 'typescript', 'java', 'go', 'rust', 'ruby', 'swift', 'kotlin']
❌ PHP parser not loaded
```

**After Fix:**
```
✅ Parser initialized successfully
Available parsers: ['python', 'javascript', 'typescript', 'java', 'go', 'rust', 'php', 'ruby', 'swift', 'kotlin']
✅ PHP parser loaded successfully
```

## Completion Summary

**Status:** ✅ Fixed
**Date:** 2025-11-20
**Implementation Time:** 15 minutes

### What Was Changed
- Fixed LANGUAGE_MODULES dict in `src/memory/python_parser.py:52`
- Changed from `"language"` to `"language_php"` to match tree-sitter-php API
- Added inline comment referencing BUG-021

### Impact
- **Functionality:** PHP files can now be indexed by Python parser fallback
- **User Experience:** No more warning noise in logs
- **Scope:** Affects users without Rust parser who index PHP code

### Files Changed
- Modified: `src/memory/python_parser.py` (line 52)
- Created: `planning_docs/BUG-021_php_parser_fix.md`
