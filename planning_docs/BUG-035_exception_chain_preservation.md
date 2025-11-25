# BUG-035: Add Exception Chain Preservation

**Status:** TODO
**Priority:** CRITICAL
**Estimated Effort:** 1 day
**Category:** Bug Fix
**Area:** Error Handling & Observability

---

## 1. Overview

### Problem Summary
Throughout the codebase (95+ locations across `/Users/elliotmilco/Documents/GitHub/claude-memory-server/src/`), exceptions are re-raised without preserving the original exception chain using `from e`. This loses critical debugging information including the original exception type, traceback, and context, making production debugging extremely difficult.

### Impact Assessment
**Severity:** CRITICAL - Production debugging capability

**Consequences:**
- **Lost Stack Traces:** Original exception location is lost, making debugging 10x harder
- **Lost Exception Types:** Can't distinguish between ValueError, ConnectionError, etc. in logs
- **Lost Context:** `__cause__` and `__context__` attributes unavailable in debuggers
- **Support Burden:** Support team can't diagnose root causes from logs
- **Delayed Incident Resolution:** Production issues take much longer to debug

**Example Problem:**
```python
# Current (BAD - loses traceback)
try:
    result = some_complex_operation()
except Exception as e:
    logger.error(f"Failed to do operation: {e}")  # Only message, no traceback
    raise StorageError(f"Failed to do operation: {e}")  # Original exception lost

# When this fails in production, you see:
# ERROR: Failed to do operation: name 'undefined_var' is not defined
# StorageError: Failed to do operation: name 'undefined_var' is not defined
# Traceback: ... (only shows raise StorageError line)
# ❌ Can't see WHERE in some_complex_operation() the NameError occurred!

# Correct (GOOD - preserves chain)
try:
    result = some_complex_operation()
except Exception as e:
    logger.error(f"Failed to do operation: {e}", exc_info=True)  # Full traceback in logs
    raise StorageError(f"Failed to do operation: {e}") from e  # Chain preserved

# When this fails in production, you see:
# ERROR: Failed to do operation: name 'undefined_var' is not defined
# Traceback: ... (full stack trace from some_complex_operation())
# The above exception was the direct cause of the following exception:
# StorageError: Failed to do operation: name 'undefined_var' is not defined
# ✅ Can see EXACTLY where in some_complex_operation() the NameError occurred!
```

### Business Justification
- **Production Readiness:** Must fix before v4.0 release - critical for operations
- **Operational Efficiency:** Reduces MTTR (Mean Time To Resolution) for incidents
- **Support Cost:** Reduces back-and-forth with users during debugging
- **Code Quality:** Follows Python best practices (PEP 3134)

---

## 2. Current State Analysis

### Affected Files

Based on grep analysis, 95 instances across 18 files:

**Primary Offenders (by instance count):**
1. `/Users/elliotmilco/Documents/GitHub/claude-memory-server/src/store/qdrant_store.py` - 30+ instances
2. `/Users/elliotmilco/Documents/GitHub/claude-memory-server/src/embeddings/generator.py` - 10+ instances
3. `/Users/elliotmilco/Documents/GitHub/claude-memory-server/src/embeddings/parallel_generator.py` - 8+ instances
4. `/Users/elliotmilco/Documents/GitHub/claude-memory-server/src/memory/incremental_indexer.py` - 10+ instances
5. `/Users/elliotmilco/Documents/GitHub/claude-memory-server/src/store/call_graph_store.py` - 6+ instances
6. `/Users/elliotmilco/Documents/GitHub/claude-memory-server/src/backup/exporter.py` - 5+ instances
7. `/Users/elliotmilco/Documents/GitHub/claude-memory-server/src/backup/importer.py` - 5+ instances
8. `/Users/elliotmilco/Documents/GitHub/claude-memory-server/src/store/qdrant_setup.py` - 4+ instances
9. `/Users/elliotmilco/Documents/GitHub/claude-memory-server/src/tagging/tag_manager.py` - 3+ instances
10. `/Users/elliotmilco/Documents/GitHub/claude-memory-server/src/tagging/collection_manager.py` - 3+ instances
11. `/Users/elliotmilco/Documents/GitHub/claude-memory-server/src/search/pattern_matcher.py` - 2+ instances
12. `/Users/elliotmilco/Documents/GitHub/claude-memory-server/src/core/server.py` - scattered instances

**Additional Affected:**
- Planning docs (not code, ignore)
- Test output logs (not code, ignore)
- TODO.md (documentation, ignore)

### Pattern Inventory

**Pattern 1: Simple re-raise (most common - ~70 instances)**
```python
except Exception as e:
    logger.error(f"Error message: {e}")
    raise SomeError(f"Error message: {e}")  # ❌ Missing "from e"
```

**Pattern 2: Re-raise with different exception type (~20 instances)**
```python
except ValueError as e:
    raise ValidationError(f"Invalid input: {e}")  # ❌ Missing "from e"
except ConnectionError as e:
    raise StorageError(f"Connection failed: {e}")  # ❌ Missing "from e"
```

**Pattern 3: Nested try-except with multiple raises (~5 instances)**
```python
try:
    try:
        operation()
    except SpecificError as e:
        raise SpecificError(f"Inner error: {e}")  # ❌ Missing "from e"
except Exception as e:
    raise GenericError(f"Outer error: {e}")  # ❌ Missing "from e"
```

### Grep Patterns to Find All Instances

**Primary Pattern:**
```bash
# Find all raise XxxError(f"...{e}") without "from e"
grep -rn "raise.*Error(.*{e}" src/ --include="*.py" | grep -v "from e"
```

**Secondary Pattern:**
```bash
# Find raise XxxError(...) inside except blocks (broader, may have false positives)
grep -B5 "raise.*Error(" src/ --include="*.py" | grep -A5 "except.*as e:"
```

**Comprehensive Search:**
```bash
# Find all except blocks with raises
grep -rn "except.*as e:" src/ --include="*.py" -A10 | grep "raise.*Error"
```

### Why This Pattern Exists

Looking at the codebase, this appears to be:

1. **Knowledge Gap:** Developers unfamiliar with PEP 3134 (exception chaining)
2. **Copy-Paste Propagation:** Early code had this pattern, later code copied it
3. **Pre-Python 3 Habits:** Python 2 didn't have `from e` syntax (added in Python 3.3)
4. **Inconsistent Review:** Code reviews didn't catch this anti-pattern
5. **No Linting Rule:** pylint/flake8 not configured to enforce exception chaining

### Current Testing Coverage

**Tests Don't Catch This:**
- Unit tests with mocking don't test exception chains
- Integration tests focus on happy paths
- No tests explicitly validate `__cause__` or `__context__` attributes
- No tests for exception chain length or traceback preservation

**Example Test That Would Fail (doesn't exist):**
```python
def test_exception_chain_preserved():
    """Verify exception chains are preserved for debugging."""
    store = QdrantMemoryStore()

    with pytest.raises(StorageError) as exc_info:
        # Trigger some internal error
        store.store_invalid_data()

    # Check exception chain
    assert exc_info.value.__cause__ is not None  # Currently FAILS
    assert isinstance(exc_info.value.__cause__, ValueError)  # Currently FAILS
```

---

## 3. Proposed Solution

### Transformation Rules

**Rule 1: Add `from e` to all exception re-raises**

```python
# Before:
except Exception as e:
    raise SomeError(f"Message: {e}")

# After:
except Exception as e:
    raise SomeError(f"Message: {e}") from e
```

**Rule 2: Add `exc_info=True` to all error logs**

```python
# Before:
logger.error(f"Error occurred: {e}")

# After:
logger.error(f"Error occurred: {e}", exc_info=True)
```

**Rule 3: Keep exception variable name consistent**

```python
# Before (inconsistent):
except ValueError as err:
    raise ValidationError(f"Invalid: {err}") from err

# After (consistent):
except ValueError as e:
    raise ValidationError(f"Invalid: {e}") from e
```

### Special Cases

**Case 1: Bare `raise` (no transformation needed)**
```python
# This is already correct - re-raises with chain
except Exception as e:
    logger.error(f"Error: {e}", exc_info=True)
    raise  # ✅ Automatically preserves chain
```

**Case 2: Suppress chaining (rare, explicit intent)**
```python
# Explicitly suppress chain when not useful (rare!)
except KeyError as e:
    raise ValidationError(f"Missing required field") from None  # Intentional suppression
```

**Case 3: Multiple exception types**
```python
# Before:
except (ValueError, TypeError) as e:
    raise ValidationError(f"Invalid input: {e}")

# After:
except (ValueError, TypeError) as e:
    raise ValidationError(f"Invalid input: {e}") from e
```

---

## 4. Implementation Plan

### Phase 1: Preparation (2 hours)

**Step 1.1: Create comprehensive inventory**

```bash
# Create worktree
TASK_ID="BUG-035"
git worktree add .worktrees/$TASK_ID -b $TASK_ID
cd .worktrees/$TASK_ID

# Generate complete list of files and line numbers
grep -rn "raise.*Error(.*{e}" src/ --include="*.py" | grep -v "from e" > /tmp/bug035_instances.txt

# Count instances per file
cat /tmp/bug035_instances.txt | cut -d: -f1 | sort | uniq -c | sort -rn > /tmp/bug035_by_file.txt

# Show summary
echo "Total instances: $(wc -l < /tmp/bug035_instances.txt)"
echo "Files affected: $(cat /tmp/bug035_instances.txt | cut -d: -f1 | sort -u | wc -l)"
echo ""
echo "Top 10 files by instance count:"
head -10 /tmp/bug035_by_file.txt
```

**Step 1.2: Create automated fix script**

Create `/Users/elliotmilco/Documents/GitHub/claude-memory-server/scripts/fix_exception_chains.py`:

```python
#!/usr/bin/env python3
"""
Automated script to add exception chain preservation.

Transforms:
    raise XxxError(f"...{e}")
To:
    raise XxxError(f"...{e}") from e

And:
    logger.error(f"...{e}")
To:
    logger.error(f"...{e}", exc_info=True)
"""
import re
import sys
from pathlib import Path
from typing import List, Tuple

def fix_file(filepath: Path) -> Tuple[int, List[str]]:
    """Fix exception chains in a single file.

    Returns:
        (changes_made, list_of_changes)
    """
    content = filepath.read_text()
    lines = content.split('\n')
    changes = []
    modified = False

    i = 0
    while i < len(lines):
        line = lines[i]

        # Pattern 1: raise XxxError(...{e}) without "from e"
        # Must check it's not already "from e" on same line or next line
        if 'raise' in line and 'Error(' in line and '{e}' in line and 'from e' not in line:
            # Check next line doesn't have "from e"
            if i + 1 >= len(lines) or 'from e' not in lines[i + 1]:
                # Check if line ends with closing paren
                if line.rstrip().endswith(')'):
                    # Simple case: add "from e" on same line
                    old_line = line
                    lines[i] = line.rstrip() + ' from e'
                    changes.append(f"Line {i+1}: Added 'from e'")
                    modified = True
                elif line.rstrip().endswith(',') or i + 1 < len(lines):
                    # Multi-line raise - need to find closing paren
                    # For safety, we'll mark this for manual review
                    changes.append(f"Line {i+1}: MANUAL REVIEW - Multi-line raise")

        # Pattern 2: logger.error(f"...{e}") without exc_info=True
        if 'logger.error(' in line and '{e}' in line and 'exc_info' not in line:
            # Check if this is inside an except block (heuristic)
            # Look back up to 10 lines for "except"
            in_except = any('except' in lines[j] for j in range(max(0, i-10), i))

            if in_except:
                # Find closing paren
                if ')' in line:
                    # Simple case: single line
                    old_line = line
                    # Insert exc_info=True before closing paren
                    lines[i] = re.sub(r'\)(\s*)$', r', exc_info=True)\1', line)
                    if lines[i] != old_line:
                        changes.append(f"Line {i+1}: Added exc_info=True")
                        modified = True

        i += 1

    if modified:
        filepath.write_text('\n'.join(lines))

    return len(changes), changes

def main():
    src_dir = Path("src")

    if not src_dir.exists():
        print("Error: src/ directory not found", file=sys.stderr)
        return 1

    total_changes = 0
    files_modified = 0

    # Process all Python files
    for filepath in src_dir.rglob("*.py"):
        changes_count, changes = fix_file(filepath)
        if changes_count > 0:
            print(f"\n{filepath}: {changes_count} changes")
            for change in changes:
                print(f"  {change}")
            total_changes += changes_count
            files_modified += 1

    print(f"\n" + "="*60)
    print(f"Summary: {total_changes} changes across {files_modified} files")
    print("="*60)

    # Check for instances that need manual review
    manual_review = []
    for filepath in src_dir.rglob("*.py"):
        content = filepath.read_text()
        for i, line in enumerate(content.split('\n'), 1):
            if 'MANUAL REVIEW' in line:
                manual_review.append(f"{filepath}:{i}")

    if manual_review:
        print(f"\n⚠️  {len(manual_review)} instances need manual review:")
        for item in manual_review:
            print(f"  {item}")

    return 0

if __name__ == '__main__':
    sys.exit(main())
```

**Step 1.3: Create verification script**

Create `/Users/elliotmilco/Documents/GitHub/claude-memory-server/scripts/verify_exception_chains.py`:

```python
#!/usr/bin/env python3
"""Verify all exception chains are preserved."""
import re
import sys
from pathlib import Path
from typing import List, Tuple

def check_file(filepath: Path) -> Tuple[bool, List[str]]:
    """Check if file has proper exception chain preservation.

    Returns:
        (is_clean, list_of_issues)
    """
    content = filepath.read_text()
    lines = content.split('\n')
    issues = []

    # Check for raise XxxError(...{e}) without "from e"
    for i, line in enumerate(lines, 1):
        if 'raise' in line and 'Error(' in line and '{e}' in line and 'from e' not in line:
            # Check next line
            if i >= len(lines) or 'from e' not in lines[i]:
                issues.append(f"Line {i}: raise without 'from e': {line.strip()}")

    # Check for logger.error with {e} but no exc_info
    in_except_block = False
    for i, line in enumerate(lines, 1):
        if 'except' in line and ' as e:' in line:
            in_except_block = True
        elif line and not line[0].isspace() and 'def ' in line:
            in_except_block = False

        if in_except_block and 'logger.error(' in line and '{e}' in line:
            if 'exc_info' not in line:
                issues.append(f"Line {i}: logger.error without exc_info=True: {line.strip()}")

    return len(issues) == 0, issues

def main():
    src_dir = Path("src")

    if not src_dir.exists():
        print("Error: src/ directory not found", file=sys.stderr)
        return 1

    all_issues = []
    files_with_issues = 0

    # Check all Python files
    for filepath in src_dir.rglob("*.py"):
        is_clean, issues = check_file(filepath)
        if not is_clean:
            print(f"\n❌ {filepath}: {len(issues)} issues")
            for issue in issues:
                print(f"   {issue}")
            all_issues.extend(issues)
            files_with_issues += 1

    print(f"\n" + "="*60)
    if all_issues:
        print(f"❌ Found {len(all_issues)} issues across {files_with_issues} files")
        print("="*60)
        return 1
    else:
        print("✅ All exception chains properly preserved!")
        print("="*60)
        return 0

if __name__ == '__main__':
    sys.exit(main())
```

---

### Phase 2: Implementation (4-5 hours)

**Strategy:** Fix files in priority order (by instance count), running tests after each file.

**Step 2.1: Automated fixes for simple cases (2 hours)**

```bash
# Run automated fix script
python scripts/fix_exception_chains.py > /tmp/bug035_auto_fixes.log

# Review changes
cat /tmp/bug035_auto_fixes.log

# Check git diff to verify changes are correct
git diff src/
```

**Step 2.2: Manual fixes for complex cases (2-3 hours)**

Based on automated script output, manually fix instances marked as "MANUAL REVIEW":

**Priority Order (by impact and instance count):**

**Group 1: Storage Layer (critical path - 40+ instances, 1.5 hours)**
- `src/store/qdrant_store.py`
- `src/store/qdrant_setup.py`
- `src/store/call_graph_store.py`

```bash
# After fixing each file, run tests
pytest tests/unit/test_qdrant_store.py -v
pytest tests/unit/test_call_graph_store.py -v
```

**Group 2: Embeddings Layer (performance-critical - 18+ instances, 1 hour)**
- `src/embeddings/generator.py`
- `src/embeddings/parallel_generator.py`

```bash
pytest tests/unit/test_embeddings.py -v
pytest tests/unit/test_parallel_embeddings.py -v
```

**Group 3: Indexing Layer (10+ instances, 45 min)**
- `src/memory/incremental_indexer.py`

```bash
pytest tests/unit/test_incremental_indexer.py -v
pytest tests/unit/test_indexing_progress.py -v
```

**Group 4: Backup/Restore (10+ instances, 30 min)**
- `src/backup/exporter.py`
- `src/backup/importer.py`

```bash
pytest tests/unit/test_backup.py -v
pytest tests/integration/test_backup_restore.py -v
```

**Group 5: Supporting Modules (12+ instances, 1 hour)**
- `src/tagging/tag_manager.py`
- `src/tagging/collection_manager.py`
- `src/search/pattern_matcher.py`
- `src/core/server.py` (scattered instances)

```bash
pytest tests/unit/test_tagging.py -v
pytest tests/unit/test_pattern_matcher.py -v
pytest tests/unit/test_server.py -v
```

**Step 2.3: Verification (30 min)**

```bash
# Run verification script
python scripts/verify_exception_chains.py

# Should output: ✅ All exception chains properly preserved!

# Double-check with grep
grep -rn "raise.*Error(.*{e}" src/ --include="*.py" | grep -v "from e"
# Should return: (empty)
```

---

### Phase 3: Testing (2 hours)

**Step 3.1: Add exception chain tests (1 hour)**

Create `/Users/elliotmilco/Documents/GitHub/claude-memory-server/tests/unit/test_exception_chains.py`:

```python
"""Tests for exception chain preservation."""
import pytest
from unittest.mock import patch, MagicMock
from src.store.qdrant_store import QdrantMemoryStore
from src.embeddings.generator import EmbeddingGenerator
from src.memory.incremental_indexer import IncrementalIndexer
from src.core.exceptions import StorageError, ValidationError, EmbeddingError

class TestExceptionChainPreservation:
    """Verify exception chains are preserved for debugging."""

    @pytest.mark.asyncio
    async def test_storage_error_preserves_chain(self):
        """Storage errors preserve original exception chain."""
        store = QdrantMemoryStore()

        # Mock _get_client to raise ConnectionError
        with patch.object(store, '_get_client', side_effect=ConnectionError("Network down")):
            with pytest.raises(StorageError) as exc_info:
                await store.store("content", [0.1] * 384, {})

        # Verify exception chain exists
        assert exc_info.value.__cause__ is not None
        assert isinstance(exc_info.value.__cause__, ConnectionError)
        assert "Network down" in str(exc_info.value.__cause__)

    @pytest.mark.asyncio
    async def test_validation_error_preserves_chain(self):
        """Validation errors preserve original exception chain."""
        store = QdrantMemoryStore()

        # Mock _build_payload to raise ValueError
        with patch.object(store, '_build_payload', side_effect=ValueError("Invalid schema")):
            with pytest.raises(ValidationError) as exc_info:
                await store.store("content", [0.1] * 384, {})

        # Verify chain
        assert exc_info.value.__cause__ is not None
        assert isinstance(exc_info.value.__cause__, ValueError)
        assert "Invalid schema" in str(exc_info.value.__cause__)

    def test_embedding_error_preserves_chain(self):
        """Embedding generation errors preserve chain."""
        generator = EmbeddingGenerator()

        # Mock model to raise RuntimeError
        with patch.object(generator, 'model', MagicMock(
            side_effect=RuntimeError("Model crashed")
        )):
            with pytest.raises(EmbeddingError) as exc_info:
                generator.generate_embeddings(["test"])

        # Verify chain
        assert exc_info.value.__cause__ is not None
        assert isinstance(exc_info.value.__cause__, RuntimeError)
        assert "Model crashed" in str(exc_info.value.__cause__)

    @pytest.mark.asyncio
    async def test_indexing_error_preserves_chain(self):
        """Indexing errors preserve exception chain."""
        indexer = IncrementalIndexer()

        # Mock file read to raise OSError
        with patch('builtins.open', side_effect=OSError("Permission denied")):
            with pytest.raises(Exception) as exc_info:
                await indexer.index_file("/fake/path.py")

        # Should have chain (exact exception type depends on implementation)
        # At minimum, should not lose OSError
        assert "Permission denied" in str(exc_info.value) or (
            exc_info.value.__cause__ is not None and
            "Permission denied" in str(exc_info.value.__cause__)
        )

    def test_exception_chain_depth(self):
        """Verify multi-level exception chains are preserved."""
        # This tests nested try-except blocks

        def inner():
            raise ValueError("Inner error")

        def middle():
            try:
                inner()
            except ValueError as e:
                raise ValidationError("Middle error") from e

        def outer():
            try:
                middle()
            except ValidationError as e:
                raise StorageError("Outer error") from e

        with pytest.raises(StorageError) as exc_info:
            outer()

        # Verify full chain
        assert exc_info.value.__cause__ is not None  # ValidationError
        assert exc_info.value.__cause__.__cause__ is not None  # ValueError
        assert isinstance(exc_info.value.__cause__.__cause__, ValueError)
```

**Step 3.2: Run full test suite (30 min)**

```bash
# Run all unit tests
pytest tests/unit/ -v --tb=short

# Run new exception chain tests
pytest tests/unit/test_exception_chains.py -v

# Run integration tests
pytest tests/integration/ -v --tb=short

# Check coverage
pytest tests/ --cov=src --cov-report=term-missing
```

**Step 3.3: Manual testing (30 min)**

```bash
# Start MCP server
python -m src.mcp_server &
SERVER_PID=$!

# Trigger various errors and check logs for full tracebacks
# Example: Try to store invalid data
python -c "
from src.core.client import MemoryClient
client = MemoryClient()
# Trigger some error...
"

# Check logs show full exception chains
tail -f logs/mcp_server.log | grep -A20 "ERROR"

kill $SERVER_PID
```

---

### Phase 4: Documentation & Review (1 hour)

**Step 4.1: Update CHANGELOG.md (10 min)**

```markdown
### Fixed
- **BUG-035**: Added exception chain preservation throughout codebase
  - Added `from e` to 95+ exception re-raises across 18 files
  - Added `exc_info=True` to error logs for full tracebacks
  - Improves production debugging with complete stack traces
  - Follows PEP 3134 best practices for exception chaining
  - Added unit tests for exception chain verification
```

**Step 4.2: Update planning document (10 min)**

Add completion summary to this document.

**Step 4.3: Create coding standards document (20 min)**

Create `/Users/elliotmilco/Documents/GitHub/claude-memory-server/docs/EXCEPTION_HANDLING.md`:

```markdown
# Exception Handling Best Practices

## Always Preserve Exception Chains

When re-raising exceptions, **always** use `from e` to preserve the original exception:

```python
# ✅ GOOD - Preserves chain
try:
    operation()
except ValueError as e:
    logger.error(f"Operation failed: {e}", exc_info=True)
    raise ValidationError(f"Invalid input: {e}") from e

# ❌ BAD - Loses chain
try:
    operation()
except ValueError as e:
    logger.error(f"Operation failed: {e}")
    raise ValidationError(f"Invalid input: {e}")
```

## Why This Matters

Exception chains provide critical debugging information:
- **Original exception type** (ValueError vs ConnectionError vs OSError)
- **Complete stack trace** from the original error location
- **`__cause__` attribute** for debugger inspection
- **Multi-level chains** for nested error handling

## Logging Errors

Always include `exc_info=True` when logging exceptions:

```python
logger.error(f"Failed to process: {e}", exc_info=True)
```

This logs the full traceback, not just the message.

## Special Cases

### Intentional Chain Suppression (rare!)

If you explicitly want to hide the original exception:

```python
except KeyError as e:
    raise ValidationError("Missing required field") from None
```

**Use sparingly** - only when original exception is not useful for debugging.

### Bare `raise`

If not changing exception type, use bare `raise`:

```python
try:
    operation()
except Exception as e:
    logger.error(f"Failed: {e}", exc_info=True)
    raise  # Automatically preserves chain
```

## References

- [PEP 3134 - Exception Chaining](https://www.python.org/dev/peps/pep-3134/)
- [Python Exception Handling Best Practices](https://docs.python.org/3/tutorial/errors.html)
```

**Step 4.4: Update linting configuration (20 min)**

Add to `.pylintrc`:

```ini
[MASTER]
enable=raise-missing-from
```

Add to `pyproject.toml`:

```toml
[tool.flake8]
# Require "from e" when re-raising exceptions
select = E,W,F,C,N,B,G,SIM,TRY
ignore = E501,W503
per-file-ignores =
    tests/*: TRY002,TRY003

[tool.ruff]
select = ["E", "F", "W", "C", "N", "B", "TRY"]
ignore = ["E501", "TRY003"]

[tool.ruff.per-file-ignores]
"tests/*" = ["TRY002", "TRY003"]
```

---

## 5. Testing Strategy

### Test Coverage Goals
- **Unit Tests:** All exception re-raise paths have tests verifying `__cause__`
- **Integration Tests:** Real error scenarios preserve full stack traces
- **Manual Tests:** Production-like errors show complete debugging information

### Test Pyramid

**Level 1: Unit Tests (5 new tests)**
- Storage error chain preservation
- Validation error chain preservation
- Embedding error chain preservation
- Indexing error chain preservation
- Multi-level chain depth

**Level 2: Integration Tests (use existing + manual verification)**
- Real Qdrant connection errors preserve chains
- File I/O errors preserve chains
- Embedding model errors preserve chains

**Level 3: Observability Tests**
- Log files contain full tracebacks with `exc_info=True`
- Exception monitoring tools receive complete chains
- Debuggers can access `__cause__` attributes

### Linting Enforcement
- pylint: `raise-missing-from` check enabled
- ruff/flake8: TRY exception checks enabled
- Pre-commit hooks run linting on all changed files

---

## 6. Risk Assessment

### Technical Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Break existing error handling | Low | High | Comprehensive test suite, incremental deployment |
| Change exception semantics | Very Low | Medium | `from e` preserves type, only adds chain |
| Performance regression from logging | Very Low | Very Low | `exc_info=True` has negligible overhead |
| Linting false positives | Low | Low | Configure per-file ignores for tests |

### Deployment Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Logging volume increase | Low | Low | Logs are already at ERROR level, won't spam |
| Exception monitoring alerts | Very Low | Low | Exceptions already being raised, just more context |
| Backward compatibility | Very Low | Very Low | No API changes, internal implementation only |

### Rollback Plan

**If issues discovered:**

1. **Immediate:** Revert commit
   ```bash
   git revert <commit-hash>
   git push origin main
   ```

2. **Selective:** Revert specific files if only some are problematic

3. **Fix-forward:** If minor issues, fix them instead of full rollback

**Rollback Risk:** VERY LOW - Exception chaining is additive, doesn't break existing functionality.

---

## 7. Success Criteria

### Functional Success
- ✅ All 95+ instances have `from e` added
- ✅ All error logs have `exc_info=True`
- ✅ Verification script reports 0 issues
- ✅ No instances of `raise XxxError(...{e})` without `from e`

### Quality Success
- ✅ All existing tests pass
- ✅ New exception chain tests pass (5/5)
- ✅ Integration tests pass
- ✅ Linting checks pass
- ✅ `python scripts/verify-complete.py` passes all gates

### Observability Success
- ✅ Production logs show full stack traces
- ✅ Exception chains visible in debuggers
- ✅ MTTR for production issues reduced

### Documentation Success
- ✅ CHANGELOG.md updated
- ✅ EXCEPTION_HANDLING.md created
- ✅ Linting configuration updated
- ✅ Planning document has completion summary

---

## 8. Timeline

| Phase | Duration | Dependencies |
|-------|----------|--------------|
| Preparation | 2 hours | None |
| Implementation | 4-5 hours | Preparation complete |
| Testing | 2 hours | Implementation complete |
| Documentation & Review | 1 hour | Testing complete |
| **Total** | **1 day (9-10 hours)** | |

---

## 9. Dependencies

### Upstream Dependencies
- REF-015 (Unsafe Resource Cleanup) - naturally co-changes, can do in parallel

### Downstream Dependencies
- None - no tasks blocked by this

### Related Tasks
- ERR-001 (Exception Chains Lost) - this task directly addresses it
- ERR-003 (Missing exc_info=True) - also addressed by this task
- TEST-002 (Excessive Mocking) - better tests with real exception chains

---

## 10. Notes & Lessons Learned

### Why This Is Critical

**Real-World Impact:**
- Production incident takes 4 hours instead of 30 minutes to debug
- Support engineers can't reproduce issues without full context
- Users churn due to long resolution times

**Example from Code Review:**
From `/Users/elliotmilco/Documents/code_review_2025-11-25.md`:
> **ERR-001: Exception Chains Lost Throughout Codebase** - Only 10 uses of `raise ... from e` in entire codebase.
> **Impact:** Debugging production failures becomes 10x harder

### Prevention Strategies

1. **Linting:** Enable `raise-missing-from` in pylint
2. **Code Review Checklist:** "All exception re-raises use `from e`"
3. **IDE Configuration:** Configure PyCharm/VS Code to warn on missing `from e`
4. **Developer Education:** Add to onboarding docs and CONTRIBUTING.md

### Related Improvements (Future Tasks)

Out of scope for BUG-035, but should be tracked:

- **Structured Logging:** Add correlation IDs to trace requests
- **Exception Monitoring:** Integrate with Sentry or similar
- **Error Classification:** Add exception hierarchies for different error types
- **Retry Logic:** Add exponential backoff with exception chain preservation

---

## 11. Appendix

### A. Example Before/After

**Before (no exception chain):**
```python
async def store(self, content: str, embedding: List[float], metadata: Dict[str, Any]) -> str:
    client = await self._get_client()
    try:
        memory_id, payload = self._build_payload(content, embedding, metadata)
        point = PointStruct(id=memory_id, vector=embedding, payload=payload)
        client.upsert(collection_name=self.collection_name, points=[point])
        logger.debug(f"Stored memory: {memory_id}")
        return memory_id
    except ValueError as e:
        logger.error(f"Invalid payload for storage: {e}")
        raise ValidationError(f"Invalid memory payload: {e}")
    except ConnectionError as e:
        logger.error(f"Connection error during store: {e}")
        raise StorageError(f"Failed to connect to Qdrant: {e}")
    except Exception as e:
        logger.error(f"Unexpected error storing memory: {e}")
        raise StorageError(f"Failed to store memory: {e}")
    finally:
        if client is not None:
            await self._release_client(client)
```

**After (with exception chains):**
```python
async def store(self, content: str, embedding: List[float], metadata: Dict[str, Any]) -> str:
    client = None
    try:
        client = await self._get_client()
        memory_id, payload = self._build_payload(content, embedding, metadata)
        point = PointStruct(id=memory_id, vector=embedding, payload=payload)
        client.upsert(collection_name=self.collection_name, points=[point])
        logger.debug(f"Stored memory: {memory_id}")
        return memory_id
    except ValueError as e:
        logger.error(f"Invalid payload for storage: {e}", exc_info=True)
        raise ValidationError(f"Invalid memory payload: {e}") from e
    except ConnectionError as e:
        logger.error(f"Connection error during store: {e}", exc_info=True)
        raise StorageError(f"Failed to connect to Qdrant: {e}") from e
    except Exception as e:
        logger.error(f"Unexpected error storing memory: {e}", exc_info=True)
        raise StorageError(f"Failed to store memory: {e}") from e
    finally:
        if client is not None:
            await self._release_client(client)
```

**Log Output Comparison:**

Before:
```
ERROR: Invalid payload for storage: 'required_field' is missing
StorageError: Failed to store memory: 'required_field' is missing
Traceback (most recent call last):
  File "src/core/server.py", line 123, in handle_store
    await store.store(content, embedding, metadata)
  File "src/store/qdrant_store.py", line 142, in store
    raise ValidationError(f"Invalid memory payload: {e}")
```

After:
```
ERROR: Invalid payload for storage: 'required_field' is missing
Traceback (most recent call last):
  File "src/store/qdrant_store.py", line 121, in store
    memory_id, payload = self._build_payload(content, embedding, metadata)
  File "src/store/qdrant_store.py", line 456, in _build_payload
    raise ValueError("'required_field' is missing")
ValueError: 'required_field' is missing

The above exception was the direct cause of the following exception:

Traceback (most recent call last):
  File "src/core/server.py", line 123, in handle_store
    await store.store(content, embedding, metadata)
  File "src/store/qdrant_store.py", line 142, in store
    raise ValidationError(f"Invalid memory payload: {e}") from e
ValidationError: Invalid memory payload: 'required_field' is missing
```

**Notice:** After shows EXACTLY where the error originated (`_build_payload` line 456), not just where it was re-raised.

### B. PEP 3134 Summary

From [PEP 3134](https://www.python.org/dev/peps/pep-3134/):

> When an exception is raised, the interpreter automatically chains it to the previously active exception (if any) by setting the `__context__` attribute. The `from` clause allows the programmer to set the `__cause__` attribute to indicate that one exception is a direct consequence of another.

**Key attributes:**
- `__cause__`: Explicitly chained exception (via `from e`)
- `__context__`: Implicitly chained exception (automatic)
- `__traceback__`: Traceback object with full stack trace

### C. Related Code Review Findings

From `/Users/elliotmilco/Documents/code_review_2025-11-25.md`:

- **ERR-001:** Exception Chains Lost Throughout Codebase (40+ locations)
- **ERR-003:** Missing `exc_info=True` in Error Logs (100+ locations)

This task addresses **both** findings comprehensively.

---

**Last Updated:** 2025-11-25
**Status:** Ready for implementation
**Assigned To:** [TBD]
