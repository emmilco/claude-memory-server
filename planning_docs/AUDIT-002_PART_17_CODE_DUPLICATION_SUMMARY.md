# AUDIT-002 Part 17: Code Duplication Investigation Summary

**Date:** 2025-11-30
**Agent:** Investigation Agent 17
**Scope:** Read-only investigation of code duplication and consistency issues

## Executive Summary

Investigated 178 Python files across the codebase for code duplication, inconsistent patterns, and potential bugs arising from copy-paste programming. Found **15 significant duplication issues** ranging from critical data corruption risks to maintenance tech debt.

## Critical Findings

### 1. Embedding Model Dimensions Duplicated 9 Times (REF-140)
**Risk Level:** CRITICAL - Data Corruption

The mapping of embedding models to vector dimensions is hardcoded in 9 separate locations:
- `src/config.py` (canonical source)
- `src/store/qdrant_setup.py`
- `src/store/call_graph_store.py`
- `src/embeddings/generator.py`
- `src/embeddings/parallel_generator.py`
- `tests/conftest.py` (3 instances)
- `tests/e2e/conftest.py`

**Impact:** If a new model is added and not updated in all locations:
- Qdrant creates collection with wrong vector size
- Embeddings generated don't match schema
- Silent insertion failures or index corruption

**Example:**
```python
# Duplicated in 9 locations:
model_dims = {
    "all-MiniLM-L6-v2": 384,
    "all-MiniLM-L12-v2": 384,
    "all-mpnet-base-v2": 768,
}
```

### 2. 200+ Lines Duplicated Between Server and Service Layer (REF-141)
**Risk Level:** CRITICAL - Logic Drift

Nearly identical implementations of `index_codebase_incremental` and `reindex_codebase` exist in both:
- `src/core/server.py` (200+ lines)
- `src/services/code_indexing_service.py` (200+ lines)

**Impact:**
- Bug fixes must be applied twice
- Already diverged: server has fallback logic service doesn't
- Maintenance nightmare

**Solution:** Server should delegate to service, not duplicate implementation.

### 3. Timeout Hardcoded to 30.0 in 50+ Locations (REF-145)
**Risk Level:** HIGH - No Tunability

The value `30.0` seconds appears in:
- 21 instances in `src/services/memory_service.py`
- 7 instances in `src/services/code_indexing_service.py`
- 5 instances in `src/embeddings/cache.py`
- Many more across the codebase

**Impact:**
- Cannot tune timeout for slow operations
- No config knob for users experiencing timeouts
- Changing default requires 50+ line changes

### 4. Path Validation Duplicated 30+ Times (REF-143)
**Risk Level:** HIGH - Inconsistent Behavior

Same validation pattern repeated throughout:
```python
dir_path = Path(directory_path).resolve()
if not dir_path.exists():
    raise ValueError(f"Directory does not exist: {directory_path}")
if not dir_path.is_dir():
    raise ValueError(f"Path is not a directory: {directory_path}")
```

**Inconsistencies:**
- Some use `Path.resolve()`, others `os.path.abspath()`
- Different symlink handling
- Varying error messages

## High Priority Issues

### 5. Config Defaulting Pattern Duplicated 15+ Times (REF-144)
Every module has:
```python
if config is None:
    from src.config import get_config
    config = get_config()
```

Creates circular import risk and testing difficulties.

### 6. Error Logging Inconsistent (REF-146)
- Some modules: `logger.error(..., exc_info=True)` (includes stack trace)
- Other modules: `logger.error(...)` (no stack trace)

Production debugging impaired when errors lack tracebacks.

### 7. Logger Initialization in 136 Files (REF-147)
Every module: `logger = logging.getLogger(__name__)`

Cannot enforce:
- Structured logging (JSON format)
- Custom formatters globally
- Correlation ID injection

## Medium Priority Issues

### 8. DateTime Formatting Inconsistent (REF-149)
- 40+ instances: `datetime.now()` (naive, local timezone)
- 125 instances: `datetime.now(UTC)` (timezone-aware)

Mixing causes comparison failures and ambiguous logs.

### 9. String Validation Duplicated 20+ Times (REF-148)
Pattern `if not text or not text.strip():` repeated with varying behavior.

### 10. Date Format Strings Duplicated (REF-150)
- `"%Y-%m-%d %H:%M:%S"` - 15 instances
- `"%Y-%m-%d"` - 12 instances
- No centralized constants

## Metrics

| Category | Count |
|----------|-------|
| Total Issues Found | 15 |
| Critical Issues | 4 |
| High Priority | 4 |
| Medium Priority | 4 |
| Low Priority | 3 |
| Files with Duplication | 50+ |
| Duplicate Lines Estimated | 500+ |

## Anti-Patterns Identified

1. **No Single Source of Truth**: Model dimensions, timeouts, formats defined in 5-50 locations each
2. **Copy-Paste Programming**: 200+ line blocks duplicated between layers
3. **Inconsistent Validation**: Same check implemented differently (logging vs silent)
4. **Magic Numbers Everywhere**: Timeout=30.0, dimension=768 - not configurable
5. **Mixed API Styles**: Path/os.path, datetime.now()/datetime.now(UTC)
6. **No Shared Utilities**: Validation, trimming, error messages all duplicated

## Diagnosability Impact

From duplication alone, **cannot:**
- Add new embedding model safely (9 places to update)
- Change timeout for slow operations (50+ hardcoded values)
- Ensure all errors include stack traces (inconsistent exc_info)
- Debug server vs service differences (200 lines of drift)
- Switch to JSON logging globally (136 logger initializations)

## Recommended Fix Priority

### Phase 1 (Critical - Week 1)
1. **REF-140**: Centralize embedding dimensions → `src.config`
2. **REF-141**: Eliminate server/service duplication → delegate to service
3. **REF-142**: Fix empty query logging inconsistency

### Phase 2 (High - Week 2)
4. **REF-143**: Create `src/utils/path_validation.py`
5. **REF-145**: Add timeout config to `ServerConfig`
6. **REF-146**: Document "Always use exc_info=True for ERROR"

### Phase 3 (Medium - Week 3)
7. **REF-147**: Introduce logger factory pattern
8. **REF-149**: Fix datetime timezone consistency
9. **REF-148**: Create string validation utilities

### Long-term
- Add linting rules (pre-commit hooks)
- Document coding standards (STYLE_GUIDE.md)
- Create architectural decision records (ADR)

## Files Requiring Changes

**Critical:**
- `src/store/qdrant_setup.py`
- `src/store/call_graph_store.py`
- `src/embeddings/generator.py`
- `src/embeddings/parallel_generator.py`
- `src/core/server.py` (200+ lines to remove)
- `src/services/code_indexing_service.py`

**High:**
- `src/services/memory_service.py` (21 timeout instances)
- `src/store/connection_pool.py` (add exc_info)
- `src/analytics/usage_tracker.py` (add exc_info)

**Medium:**
- 136 files (logger initialization)
- 40+ files (datetime.now() → datetime.now(UTC))

## Test Coverage Needed

- Test that all modules use same dimension for same model
- Test that server delegates to service (not duplicates)
- Test that empty queries logged consistently
- Test that path validation rejects invalid paths uniformly
- Test that timeouts configurable via env vars

## Investigation Methodology

1. Used `Grep` to search for patterns across 178 Python files
2. Identified duplication by searching for common function signatures
3. Read specific file sections to compare implementations
4. Analyzed inconsistencies in validation, logging, and error handling
5. Counted instances of hardcoded values (timeouts, dimensions, formats)

## Key Locations for Further Investigation

- `src/core/server.py:3310-3438` - Major duplication with service layer
- `src/config.py:16-20` - Canonical model dimensions (should be only definition)
- `src/services/memory_service.py` - 21 hardcoded timeouts
- `tests/conftest.py` - Test fixtures duplicating model dimensions

## Next Steps

1. Create tickets for REF-140 through REF-154 in TODO.md ✓
2. Prioritize REF-140 (dimension mismatch) and REF-141 (200+ line duplication)
3. Create `src/utils/` directory for shared validation utilities
4. Document coding standards to prevent re-introduction
5. Add pre-commit hooks for linting rules

---

**Investigation Complete:** 2025-11-30
**Findings Logged:** TODO.md (REF-140 through REF-154)
**Planning Doc:** This file
