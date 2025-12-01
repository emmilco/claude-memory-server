# Changelog Fragments

This directory contains changelog fragments - individual files that describe changes made in each branch/task. These fragments are automatically assembled into `CHANGELOG.md` when merging to main.

## Why Fragments?

When multiple branches add entries to `CHANGELOG.md` at the same location, merge conflicts occur. The fragment system eliminates this by giving each change its own file.

## How to Create a Fragment

1. **Create a file named after your task ID:**
   ```
   changelog.d/BUG-274.md
   changelog.d/FEAT-050.md
   changelog.d/TEST-012.md
   ```

2. **Use this format:**
   ```markdown
   ### Fixed
   - **BUG-274: Brief description of what was fixed**
     - Key detail about the change
     - Files: src/path/to/file.py
   ```

3. **Use the appropriate section header:**
   - `### Added` - New features, files, commands, tools
   - `### Changed` - Changes to existing functionality
   - `### Fixed` - Bug fixes
   - `### Removed` - Removed features

4. **Commit the fragment with your changes.**

## Fragment Assembly

When merging to main, run:
```bash
python scripts/assemble-changelog.py
```

This will:
1. Read all `.md` files in `changelog.d/` (except README.md)
2. Group entries by type (Added, Changed, Fixed, Removed)
3. Prepend to `CHANGELOG.md` under `## [Unreleased]` with today's date
4. Delete the processed fragment files
5. Stage the changes for commit

## Example Fragment

**File: `changelog.d/BUG-274.md`**
```markdown
### Fixed
- **BUG-274: MemoryStore.update() Abstract Method Signature Mismatch**
  - Added `new_embedding` parameter to abstract method signature
  - Files: src/store/base.py, src/store/readonly_wrapper.py
```

## Pre-commit Hook

The pre-commit hook checks that either:
- `CHANGELOG.md` has changes, OR
- A fragment file exists in `changelog.d/`

This ensures every commit documents its changes.
