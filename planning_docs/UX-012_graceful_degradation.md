# UX-012: Graceful Degradation

## TODO Reference
- TODO.md: "UX-012: Graceful degradation (~2 days)"
- Estimated time: 2 days
- Priority: Tier 3 (UX improvements)

## Objective

Implement graceful degradation to ensure the system continues working when optional dependencies are unavailable:
1. **Qdrant unavailable** → Auto-fallback to SQLite-only mode
2. **Rust parser unavailable** → Auto-fallback to Python parser
3. Warn users about performance implications
4. Provide upgrade paths for later

## Current State

### What Exists
- SQLite storage backend (already implemented)
- Python parser fallback (already implemented in UX-011)
- Qdrant as primary vector store
- Rust parser as primary code parser

### What's Missing
- Automatic detection and fallback when Qdrant is unavailable
- Graceful handling of Rust parser failures
- User warnings about performance degradation
- Clear upgrade instructions

## Implementation Plan

### Phase 1: Qdrant Fallback Detection

**File**: `src/store/store_factory.py` (or create if doesn't exist)

```python
async def create_memory_store_with_fallback(config: ServerConfig) -> MemoryStore:
    """
    Create memory store with automatic fallback.

    Priority:
    1. Try Qdrant (if configured and available)
    2. Fallback to SQLite

    Warns user about performance implications.
    """
    if config.storage_backend == "qdrant":
        try:
            # Try to connect to Qdrant
            store = QdrantMemoryStore(config)
            await store.initialize()
            return store
        except QdrantConnectionError:
            logger.warning(
                "⚠️  Qdrant unavailable, falling back to SQLite. "
                "Performance will be reduced. "
                "See docs/troubleshooting.md for Qdrant setup."
            )
            # Fallback to SQLite
            config.storage_backend = "sqlite"

    # Use SQLite
    store = SQLiteMemoryStore(config)
    await store.initialize()
    return store
```

**Changes needed**:
- Create `src/store/store_factory.py` or enhance existing `create_memory_store()`
- Add detection logic with try/except
- Log warnings with actionable guidance
- Update `src/core/server.py` to use fallback logic

### Phase 2: Rust Parser Fallback

**File**: `src/memory/incremental_indexer.py` (already has Python fallback)

**Current implementation check**:
- Does it already gracefully fallback to Python parser?
- If not, add detection and fallback logic
- Ensure warnings are user-friendly

**Enhancement needed**:
```python
def _parse_file(self, file_path: str) -> Optional[ParsedFile]:
    """Parse file with automatic fallback."""
    try:
        # Try Rust parser first (fast)
        return self._rust_parse(file_path)
    except (ImportError, RustParsingError):
        logger.warning(
            f"⚠️  Rust parser unavailable for {file_path}, using Python fallback. "
            f"Performance will be ~10x slower. "
            f"Run: cd rust_core && maturin develop"
        )
        return self._python_parse(file_path)
```

### Phase 3: Performance Warning System

**File**: `src/core/degradation_warnings.py` (new)

```python
class DegradationWarning:
    """Track and report system degradations."""

    def __init__(self):
        self.warnings = []
        self.degradation_mode = None

    def add_warning(self, component: str, message: str, upgrade_path: str):
        """Add a degradation warning."""
        self.warnings.append({
            "component": component,
            "message": message,
            "upgrade_path": upgrade_path,
            "timestamp": datetime.now(UTC)
        })

    def get_summary(self) -> str:
        """Get human-readable summary of all degradations."""
        if not self.warnings:
            return "✓ All components running at full performance"

        summary = ["⚠️  System running in degraded mode:\n"]
        for warning in self.warnings:
            summary.append(f"  • {warning['component']}: {warning['message']}")
            summary.append(f"    → Upgrade: {warning['upgrade_path']}")

        return "\n".join(summary)
```

**Display warnings**:
- On server startup
- In health dashboard
- In status command output

### Phase 4: Configuration Updates

**File**: `src/config.py`

Add fields:
```python
class ServerConfig:
    # Existing fields...

    # Degradation settings
    allow_qdrant_fallback: bool = True
    allow_rust_fallback: bool = True
    warn_on_degradation: bool = True
```

### Phase 5: User Documentation

**File**: `docs/troubleshooting.md` (enhance existing or create)

Add sections:
- "Running without Qdrant" - SQLite-only mode explanation
- "Running without Rust" - Python parser performance characteristics
- "Upgrading from degraded mode" - Step-by-step upgrade instructions

### Phase 6: Testing

**Create**: `tests/unit/test_graceful_degradation.py`

Test scenarios:
- Qdrant unavailable → SQLite fallback works
- Rust unavailable → Python parser fallback works
- Warnings are logged appropriately
- Configuration controls fallback behavior
- Upgrade paths are clear and actionable

**Create**: `tests/integration/test_degradation_scenarios.py`

Integration scenarios:
- Full workflow with Qdrant down
- Full workflow with Rust unavailable
- Both degraded simultaneously
- Recovery after components become available

## Progress Tracking

- [ ] Phase 1: Qdrant fallback detection
  - [ ] Create/enhance store factory with fallback logic
  - [ ] Add connection testing
  - [ ] Implement warning messages
  - [ ] Update server initialization

- [ ] Phase 2: Rust parser fallback
  - [ ] Check current implementation
  - [ ] Enhance if needed
  - [ ] Improve warning messages
  - [ ] Test fallback behavior

- [ ] Phase 3: Warning system
  - [ ] Create DegradationWarning class
  - [ ] Integrate with store factory
  - [ ] Integrate with parser
  - [ ] Display in status/health commands

- [ ] Phase 4: Configuration
  - [ ] Add fallback control fields
  - [ ] Update config validation
  - [ ] Document configuration options

- [ ] Phase 5: Documentation
  - [ ] Troubleshooting guide updates
  - [ ] Upgrade path documentation
  - [ ] Performance comparison tables

- [ ] Phase 6: Testing
  - [ ] Unit tests for fallback logic
  - [ ] Integration tests for degraded scenarios
  - [ ] Test warning display
  - [ ] Test upgrade paths

- [ ] Phase 7: CHANGELOG and PR
  - [ ] Update CHANGELOG.md
  - [ ] Commit changes
  - [ ] Create PR
  - [ ] Clean up worktree

## Test Cases

### Unit Tests
1. **test_qdrant_fallback_connection_error**
   - Mock Qdrant connection failure
   - Verify SQLite fallback
   - Check warning logged

2. **test_qdrant_fallback_disabled**
   - Set allow_qdrant_fallback = False
   - Verify error raised instead of fallback
   - No fallback occurs

3. **test_rust_parser_fallback**
   - Mock Rust parser unavailable
   - Verify Python parser used
   - Check warning logged

4. **test_degradation_warning_tracking**
   - Add multiple warnings
   - Verify summary format
   - Check timestamp tracking

### Integration Tests
1. **test_full_workflow_no_qdrant**
   - Start server without Qdrant
   - Store and retrieve memories
   - Verify SQLite used
   - Check performance warning displayed

2. **test_full_workflow_no_rust**
   - Index code without Rust parser
   - Verify Python parser used
   - Check slower performance noted

3. **test_both_degraded**
   - No Qdrant, no Rust
   - Verify system still functional
   - Both warnings displayed

## Notes & Decisions

- **Decision**: Allow fallback by default
  - Rationale: Better UX, system works out of box
  - Users can disable if they want strict dependency enforcement

- **Decision**: Log warnings on first occurrence only
  - Rationale: Avoid spam, but make degradation visible
  - User can check status command for full details

- **Decision**: Performance warnings show relative slowdown
  - Rationale: Help users understand impact
  - Example: "~10x slower", "~3-5x slower"

## Files to Modify

**Create**:
- `src/store/store_factory.py` (or enhance existing)
- `src/core/degradation_warnings.py`
- `tests/unit/test_graceful_degradation.py`
- `tests/integration/test_degradation_scenarios.py`

**Modify**:
- `src/core/server.py` - Use fallback store creation
- `src/config.py` - Add degradation configuration
- `src/memory/incremental_indexer.py` - Enhance parser fallback (if needed)
- `src/cli/status_command.py` - Show degradation warnings
- `docs/troubleshooting.md` - Add degradation documentation
- `CHANGELOG.md` - Document changes

## Expected Impact

**User Experience**:
- System works even with missing dependencies
- Clear warnings about performance
- Easy upgrade path when ready

**Installation Success Rate**:
- Fewer installation failures
- Users can start quickly, optimize later
- Reduces support burden

**Performance**:
- No impact when all dependencies available
- Degraded but functional when dependencies missing
- Clear communication of trade-offs

---

## Completion Summary

**Status:** ✅ Complete
**Date:** 2025-11-17

### What Was Built

**Core Modules** (410 lines):
- `src/core/degradation_warnings.py` (150 lines) - Degradation tracking system
- `src/store/__init__.py` - Enhanced with fallback logic (96 lines)
- `src/memory/incremental_indexer.py` - Enhanced with degradation tracking (10 lines added)
- `src/cli/status_command.py` - Added degradation warnings display (24 lines added)
- `src/config.py` - Added graceful degradation configuration (3 fields)

**Test Coverage** (15 tests, 226 lines):
- `test_graceful_degradation.py` - 15 tests covering all degradation scenarios

### Key Features

1. **Qdrant Fallback**: Automatic fallback to SQLite when Qdrant unavailable
2. **Rust Parser Fallback**: Automatic fallback to Python parser (already existed, enhanced with tracking)
3. **Degradation Tracking**: Centralized system to track all degradations
4. **User Warnings**: Clear warnings in status command with upgrade paths
5. **Configuration Control**: Users can disable fallback if desired

### Impact

- System works even with missing optional dependencies
- Clear communication about performance implications
- Easy upgrade path when ready
- Reduces installation friction
- Better first-time user experience

**UX-012 Complete!** ✅
