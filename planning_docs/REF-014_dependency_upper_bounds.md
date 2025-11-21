# REF-014: Dependency Upper Bounds Analysis

## Reference
- **TODO**: Code review recommendation #9
- **Issue**: requirements.txt only has `>=` constraints, no upper bounds
- **Risk**: Breaking changes from major version updates
- **Priority**: Medium

## Current State

All dependencies use minimum version constraints only:
```
anthropic>=0.18.0
pydantic>=2.0.0
```

## Problem

Without upper bounds, `pip install` may fetch breaking major versions:
- `pydantic>=2.0.0` could install pydantic 3.0.0 (breaking changes)
- `anthropic>=0.18.0` could install anthropic 2.0.0 (API changes)

## Proposed Approach

Add upper bounds using `<next_major` pattern:

```
# Example
pydantic>=2.0.0,<3.0.0
anthropic>=0.18.0,<1.0.0
```

## Dependency Analysis

### Core Dependencies

1. **anthropic>=0.18.0**
   - Current: 0.18.x series
   - Recommendation: `anthropic>=0.18.0,<1.0.0`
   - Rationale: Pre-1.0, expect breaking changes in 1.0

2. **pydantic>=2.0.0**
   - Current: 2.x series (already at major version)
   - Recommendation: `pydantic>=2.0.0,<3.0.0`
   - Rationale: v2 was major rewrite, v3 will likely break

3. **mcp>=0.9.0**
   - Current: Pre-1.0
   - Recommendation: `mcp>=0.9.0,<1.0.0`
   - Rationale: MCP protocol still evolving

4. **qdrant-client>=1.7.0**
   - Current: 1.x series
   - Recommendation: `qdrant-client>=1.7.0,<2.0.0`
   - Rationale: Vector DB API stability

### ML/Data Dependencies

5. **sentence-transformers>=2.2.0**
   - Current: 2.x series
   - Recommendation: `sentence-transformers>=2.2.0,<3.0.0`
   - Rationale: Stable API in 2.x

6. **numpy>=1.24.0**
   - Current: 1.x series (mature)
   - Recommendation: `numpy>=1.24.0,<2.0.0`
   - Rationale: numpy 2.0 has breaking changes

### Tree-sitter Dependencies

7. **tree-sitter-*>=0.20.0**
   - All tree-sitter bindings
   - Recommendation: `tree-sitter-*>=0.20.0,<1.0.0`
   - Rationale: Pre-1.0, API may change

**Exceptions:**
- `tree-sitter-swift>=0.0.1` - keep as-is (very early)
- `tree-sitter-kotlin>=0.2.0` - change to `<1.0.0`
- `tree-sitter-sql>=0.3.0` - change to `<1.0.0`

### Utilities

8. **rich>=13.0.0, textual>=0.40.0**
   - Both mature libraries
   - Recommendation: `rich>=13.0.0,<14.0.0`, `textual>=0.40.0,<1.0.0`

9. **watchdog>=3.0.0**
   - Recommendation: `watchdog>=3.0.0,<4.0.0`

10. **apscheduler>=3.10.0**
    - Recommendation: `apscheduler>=3.10.0,<4.0.0`

11. **GitPython>=3.1.40**
    - Recommendation: `GitPython>=3.1.40,<4.0.0`

12. **pytest-xdist>=3.5.0, pytest-asyncio>=0.21.0**
    - Test dependencies (less critical)
    - Recommendation: Add bounds anyway for reproducibility

## Alternative: Use requirements-lock.txt

**Better approach for production:**
- Keep requirements.txt with ranges for development flexibility
- Use requirements-lock.txt (already generated) for production deploys
- Lock file has exact versions: `anthropic==0.18.1`

**Benefits:**
- Development: Flexible (can upgrade within bounds)
- Production: Exact (reproducible builds)
- CI/CD: Use lock file for consistency

## Recommendation

**Option 1: Add Upper Bounds (Defensive)**
- Pros: Protects against breaking changes
- Cons: Need to manually bump bounds for major upgrades

**Option 2: Use Lock File Only (Pragmatic)**
- Pros: Flexibility + reproducibility when needed
- Cons: Developers might accidentally install breaking versions

**Recommended: Hybrid Approach**
1. Add conservative upper bounds to requirements.txt
2. Use requirements-lock.txt for production/CI
3. Regenerate lock file periodically (monthly)

## Implementation

### Updated requirements.txt

```
anthropic>=0.18.0,<1.0.0
sentence-transformers>=2.2.0,<3.0.0
numpy>=1.24.0,<2.0.0
mcp>=0.9.0,<1.0.0
python-dotenv>=1.0.0,<2.0.0
markdown>=3.4.0,<4.0.0
qdrant-client>=1.7.0,<2.0.0
watchdog>=3.0.0,<4.0.0
pydantic>=2.0.0,<3.0.0
pydantic-settings>=2.0.0,<3.0.0
rich>=13.0.0,<14.0.0
textual>=0.40.0,<1.0.0
tree-sitter>=0.20.0,<1.0.0
tree-sitter-python>=0.20.0,<1.0.0
tree-sitter-javascript>=0.20.0,<1.0.0
tree-sitter-typescript>=0.20.0,<1.0.0
tree-sitter-java>=0.20.0,<1.0.0
tree-sitter-go>=0.20.0,<1.0.0
tree-sitter-rust>=0.20.0,<1.0.0
tree-sitter-cpp>=0.20.0,<1.0.0
tree-sitter-php>=0.20.0,<1.0.0
tree-sitter-ruby>=0.20.0,<1.0.0
tree-sitter-swift>=0.0.1,<1.0.0
tree-sitter-kotlin>=0.2.0,<1.0.0
tree-sitter-sql>=0.3.0,<1.0.0
apscheduler>=3.10.0,<4.0.0
GitPython>=3.1.40,<4.0.0
pytest-xdist>=3.5.0,<4.0.0
pytest-asyncio>=0.21.0,<1.0.0
```

## Testing Plan

After adding bounds:
1. Create fresh venv
2. pip install -r requirements.txt
3. Run test suite
4. Verify all imports work
5. Test MCP server starts

## Rollout

1. Add bounds to requirements.txt
2. Regenerate requirements-lock.txt
3. Test in CI
4. Document update process in DEVELOPMENT.md
5. Set calendar reminder to review bounds quarterly

---

**Status:** Planning complete - ready for implementation
**Risk:** Low (can revert if issues)
**Effort:** 30 minutes
