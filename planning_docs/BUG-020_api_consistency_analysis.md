# BUG-020: Inconsistent Return Value Structures

## TODO Reference
- ID: BUG-020
- Severity: MEDIUM
- Component: API design consistency

## Objective
Standardize return value structures across all MCP server methods.

## Current State

Different methods use different patterns for indicating success/failure:

### Pattern 1: `{"status": "success"|"error", ...data}`
```python
# delete_memory
{"status": "success", "memory_id": "abc123"}

# store_memory
{"status": "success", "memory_id": "abc123", ...}
```

### Pattern 2: Direct data return
```python
# list_memories
{"memories": [...], "total_count": 10, "returned_count": 10, ...}

# search_code
{"results": [...], "total": 5, "query_time_ms": 12}
```

### Pattern 3: `{"success": bool, ...}` (expected by some tests)
```python
# Test expectations
{"success": True, "memory_id": "..."}
```

## Analysis

### Impact Assessment

**Breaking Change Risk:** HIGH
- Changing return structures would break existing client code
- MCP protocol consumers depend on current API
- Would require major version bump (v5.0)

**Current Functionality:** WORKING
- All methods return predictable structures
- Inconsistency is aesthetic/DX issue, not a bug
- No functionality is broken

**User Impact:** LOW
- Users adapt to each method's return structure
- IDEs/type hints help with discovery
- Documentation covers return formats

### Recommendation

**Reclassify as ENHANCEMENT** (not a bug)

This is a design improvement that should be:
1. **Deferred** to next major version (v5.0)
2. **Discussed** with users for feedback
3. **Planned** with migration guide
4. **Tested** extensively before release

Reasons:
- Not a functional bug - everything works
- Breaking change requires careful planning
- Low priority compared to functional bugs
- Better handled as deliberate API redesign

### If Pursued (Future Work)

**Recommended Standard:**
```python
# Option A: Consistent envelope
{
    "status": "success" | "error",
    "data": { method-specific results },
    "error": null | { error details }
}

# Option B: Hybrid (current pattern, documented)
# Keep current patterns but document them clearly
# Add TypeScript types for return values
```

**Implementation Steps:**
1. Create RFC document for community feedback
2. Add new methods with `_v2` suffix
3. Deprecate old methods with warnings
4. Provide migration period (6-12 months)
5. Remove old methods in v6.0

**Estimated Effort:** 40-60 hours
- API redesign: 8-12 hours
- Implementation: 15-20 hours
- Testing: 10-15 hours
- Documentation: 7-10 hours
- Migration guide: 5-8 hours

## Conclusion

**Decision:** Close as "Won't Fix" (in this bug batch)

**Rationale:**
- Not a bug - API works correctly
- Breaking change requires major version
- Low priority vs functional issues
- Better as planned feature in v5.0

**Next Steps:**
1. Create FEAT-XXX for v5.0 API standardization
2. Update TODO.md to reclassify
3. Document current patterns clearly
4. Close BUG-020 as reclassified

## Status

**Resolution:** Reclassified as future enhancement
**Date:** 2025-11-20
**Reason:** Breaking change, low priority, better as planned feature
