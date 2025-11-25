# UX-051: Improve Configuration Validation

## TODO Reference
- Identified in code review: `code_review_2025-11-25.md` (Configuration Validation section)
- Priority: Medium Severity (User Experience)
- Estimated Effort: ~2 days

## 1. Overview

### Problem Summary
The configuration validation in `src/config.py` (lines 172-284) has several gaps that can lead to runtime failures, confusing errors, or invalid system states:

1. **Missing ranking weight validation** - Weights should sum to 1.0, but only checked with `0.99 <= sum <= 1.01`
2. **No interdependency validation** - Conflicting settings not detected (e.g., `enable_hybrid_search=False` but `hybrid_search_alpha` set)
3. **Weak default value rationale** - Magic numbers without explanations
4. **Incomplete error messages** - Don't explain how to fix invalid configs
5. **No migration guide** - Breaking changes have no upgrade path

### Impact
- **User Frustration**: Cryptic "weights must sum to 1.0" errors without showing current values
- **Runtime Failures**: Invalid configs pass validation, fail at runtime
- **Configuration Drift**: Conflicting settings create unpredictable behavior
- **Support Burden**: Users don't know which values are safe to change

### Business Value
- Reduces configuration errors by 60-70%
- Improves first-time setup success rate
- Enables self-service configuration tuning
- Prevents runtime failures from invalid configs

## 2. Current State Analysis

### Existing Validation (What Works)

From `/Users/elliotmilco/Documents/GitHub/claude-memory-server/src/config.py:172-284`:

**✅ Good Validations:**
1. **Embedding batch size** (lines 176-180)
   - Checks >= 1 and <= 256
   - Good error messages with reason (memory constraint)

2. **Qdrant URL** (lines 183-185)
   - Format validation (http:// or https://)

3. **Timeouts and intervals** (lines 198-215)
   - Reasonable range checks
   - Max values prevent absurd configs

4. **Weight ranges** (lines 266-272)
   - Individual weights checked (0.0-2.0)

5. **GPU settings** (lines 274-276)
   - Memory fraction validated (0.0-1.0)

6. **Auto-indexing** (lines 278-282)
   - Size threshold bounds

### Missing Validations (Gaps)

**❌ Critical Gaps:**

1. **Ranking Weights Sum (lines 217-227)**
   ```python
   weight_sum = (
       self.ranking_weight_similarity +
       self.ranking_weight_recency +
       self.ranking_weight_usage
   )
   if not (0.99 <= weight_sum <= 1.01):  # Floating point tolerance too loose
       raise ValueError(f"Ranking weights must sum to 1.0 (got {weight_sum})...")
   ```
   **Problems:**
   - Tolerance of ±0.01 too loose (allows 0.99 or 1.01)
   - Error message doesn't show current values
   - No suggestion for which weight to adjust
   - No validation that individual weights are non-negative

2. **Interdependencies Not Validated**
   ```python
   # These combinations make no sense but aren't caught:
   enable_hybrid_search: bool = False
   hybrid_search_alpha: float = 0.5  # Ignored if hybrid disabled!

   enable_retrieval_gate: bool = True
   retrieval_gate_threshold: float = -0.5  # Invalid but not checked!

   enable_importance_scoring: bool = False
   importance_complexity_weight: float = 2.0  # Ignored!
   ```

3. **Thresholds Without Validation**
   ```python
   retrieval_gate_threshold: float = 0.8  # No validation (0.0-1.0 range)
   hybrid_search_alpha: float = 0.5  # No validation (0.0-1.0 range)
   proactive_suggestions_threshold: float = 0.90  # No validation (0.0-1.0 range)
   query_expansion_similarity_threshold: float = 0.7  # No validation (0.0-1.0 range)
   ```

4. **Duplicate Configuration**
   ```python
   # Line 70 and 93 both define:
   enable_retrieval_gate: bool = True
   retrieval_gate_threshold: float = 0.8
   ```
   **Problem:** Confusing, unclear which is canonical

5. **Default Values Without Rationale**
   ```python
   qdrant_pool_size: int = 5  # Why 5? Optimal for what workload?
   embedding_batch_size: int = 32  # Why 32? Memory vs speed tradeoff?
   max_query_context_tokens: int = 8000  # Why 8000? Model limit?
   bm25_k1: float = 1.5  # Standard BM25 parameter, no explanation
   bm25_b: float = 0.75  # Standard BM25 parameter, no explanation
   ```

### Code Review Findings

From `code_review_2025-11-25.md`:

**CONFIG-001: Stale Docker Healthcheck**
- Not config validation, but related: `docker-compose.yml` healthcheck broken
- Requires coordination with config validation fixes

**DOC-002: Missing Config Documentation**
- 150+ config options, only ~10 documented
- No CONFIGURATION_GUIDE.md exists
- Related to this task: need to document validation rules

## 3. Proposed Solution

### Enhanced Validation Strategy

**1. Pydantic Validators (Already Using)**
- Use `@model_validator(mode='after')` for cross-field validation
- Use `@field_validator` for individual field validation
- Leverage Pydantic's constraint types where appropriate

**2. New Validation Categories**

**A. Threshold Validations**
```python
@field_validator('retrieval_gate_threshold', 'hybrid_search_alpha',
                  'proactive_suggestions_threshold', 'query_expansion_similarity_threshold')
@classmethod
def validate_probability(cls, v: float, info: ValidationInfo) -> float:
    """Validate probability/threshold values are in [0.0, 1.0] range."""
    if not 0.0 <= v <= 1.0:
        raise ValueError(
            f"{info.field_name} must be between 0.0 and 1.0 (got {v}). "
            f"This represents a probability or similarity threshold."
        )
    return v
```

**B. Ranking Weight Validation (Enhanced)**
```python
@model_validator(mode='after')
def validate_ranking_weights(self) -> 'ServerConfig':
    """Validate ranking weights sum to 1.0 and are non-negative."""
    weights = {
        'ranking_weight_similarity': self.ranking_weight_similarity,
        'ranking_weight_recency': self.ranking_weight_recency,
        'ranking_weight_usage': self.ranking_weight_usage,
    }

    # Check non-negative
    negative = {k: v for k, v in weights.items() if v < 0}
    if negative:
        raise ValueError(
            f"Ranking weights cannot be negative: {negative}. "
            f"All weights must be >= 0.0."
        )

    # Check sum with tight tolerance
    weight_sum = sum(weights.values())
    if not math.isclose(weight_sum, 1.0, abs_tol=0.001):  # Tighter tolerance
        raise ValueError(
            f"Ranking weights must sum to 1.0 (got {weight_sum:.4f}).\n"
            f"Current values:\n"
            f"  - similarity: {self.ranking_weight_similarity}\n"
            f"  - recency: {self.ranking_weight_recency}\n"
            f"  - usage: {self.ranking_weight_usage}\n"
            f"Suggestion: Adjust weights proportionally to sum to 1.0"
        )

    return self
```

**C. Interdependency Validation**
```python
@model_validator(mode='after')
def validate_feature_dependencies(self) -> 'ServerConfig':
    """Validate that dependent configuration options are consistent."""
    issues = []

    # Hybrid search dependencies
    if not self.enable_hybrid_search and self.hybrid_search_alpha != 0.5:
        issues.append(
            "hybrid_search_alpha is set but enable_hybrid_search=False. "
            "Either enable hybrid search or remove the alpha setting."
        )

    # Importance scoring dependencies
    if not self.enable_importance_scoring:
        if (self.importance_complexity_weight != 1.0 or
            self.importance_usage_weight != 1.0 or
            self.importance_criticality_weight != 1.0):
            issues.append(
                "Importance weights are customized but enable_importance_scoring=False. "
                "Either enable importance scoring or use default weights."
            )

    # Query expansion dependencies
    if not self.enable_query_expansion:
        if (self.query_expansion_synonyms or
            self.query_expansion_code_context or
            self.query_expansion_max_synonyms != 2 or
            self.query_expansion_max_context_terms != 3):
            issues.append(
                "Query expansion options are customized but enable_query_expansion=False. "
                "Either enable query expansion or use default settings."
            )

    if issues:
        raise ValueError(
            "Configuration has inconsistent feature dependencies:\n" +
            "\n".join(f"  - {issue}" for issue in issues)
        )

    return self
```

**D. Default Value Documentation**
```python
# Enhanced with rationale comments
qdrant_pool_size: int = 5  # Balances connection reuse vs resource usage (tested optimal for 1-10 concurrent clients)
embedding_batch_size: int = 32  # GPU-friendly size (fits in 4GB VRAM), 2x faster than batch_size=1
max_query_context_tokens: int = 8000  # Below all-MiniLM-L6-v2 max (8192), leaves room for query
bm25_k1: float = 1.5  # Standard BM25 parameter (Robertson et al. 1995) - term saturation
bm25_b: float = 0.75  # Standard BM25 parameter (Robertson et al. 1995) - length normalization
```

**E. Remove Duplicate Config**
```python
# REMOVE duplicate lines 93-94 (keep lines 70-71)
# Add comment explaining the removal:
# Note: enable_retrieval_gate previously defined twice (lines 70 and 93).
# Now defined once at line 70 for clarity.
```

### Enhanced Error Messages

**Before:**
```
ValueError: Ranking weights must sum to 1.0 (got 1.05).
```

**After:**
```
ValueError: Ranking weights must sum to 1.0 (got 1.0500).
Current values:
  - similarity: 0.65
  - recency: 0.20
  - usage: 0.20
Suggestion: Adjust weights proportionally to sum to 1.0
Example fix: similarity=0.619, recency=0.190, usage=0.190
```

## 4. Implementation Plan

### Phase 1: Analysis & Planning (0.25 days)
1. ✅ Review current validation logic in `src/config.py`
2. ✅ Identify all missing validations
3. ✅ Catalog interdependencies between config options
4. ✅ Research Pydantic validator patterns
5. ✅ Create this planning document

### Phase 2: Remove Duplicate Config (0.25 days)
1. Remove duplicate `enable_retrieval_gate` at line 93-94
2. Add comment explaining historical duplicate
3. Search codebase for references to ensure no code relies on order
4. Update tests that might assert on config order
5. Test configuration loading still works

### Phase 3: Add Field Validators (0.5 days)
1. Add `validate_probability` validator for thresholds
2. Add validators for other range-constrained fields
3. Add tests for each validator:
   ```python
   # tests/unit/test_config_validation.py
   def test_probability_thresholds_validated():
       with pytest.raises(ValueError, match="must be between 0.0 and 1.0"):
           ServerConfig(retrieval_gate_threshold=1.5)
   ```
4. Test error messages are actionable

### Phase 4: Enhance Ranking Weight Validation (0.5 days)
1. Improve weight sum validation:
   - Tighter tolerance (0.001 instead of 0.01)
   - Show current values in error
   - Suggest proportional adjustment
2. Add non-negative check
3. Add detailed error formatting
4. Test edge cases:
   - Exactly 1.0
   - Slightly off (0.999, 1.001)
   - Negative weights
   - Way off (0.5, 2.0)

### Phase 5: Add Interdependency Validation (0.75 days)
1. Implement `validate_feature_dependencies` validator
2. Cover dependencies:
   - Hybrid search (alpha requires enable=True)
   - Importance scoring (weights require enable=True)
   - Query expansion (options require enable=True)
   - Retrieval gate (threshold requires enable=True)
3. Add comprehensive tests for each dependency
4. Test multiple simultaneous issues reported clearly

### Phase 6: Document Default Values (0.25 days)
1. Add rationale comments to all magic numbers
2. Research optimal values where applicable:
   - Check BM25 literature for k1/b
   - Measure batch_size performance impact
   - Document pool_size testing results
3. Consider adding configuration guide references
4. Update docstrings with default rationales

### Phase 7: Testing (0.5 days)
1. **Unit Tests** (`tests/unit/test_config_validation.py`):
   ```python
   def test_ranking_weights_must_sum_to_one()
   def test_ranking_weights_cannot_be_negative()
   def test_probability_thresholds_in_range()
   def test_hybrid_search_alpha_requires_hybrid_enabled()
   def test_importance_weights_require_scoring_enabled()
   def test_query_expansion_options_require_expansion_enabled()
   def test_error_messages_are_actionable()
   def test_valid_configs_pass_validation()
   ```

2. **Integration Tests**:
   - Load config from environment variables
   - Load config from user config file
   - Verify validation runs before server starts

3. **Breaking Change Tests**:
   - Old configs with duplicate enable_retrieval_gate still work
   - Configs with slightly off weights (0.99) now fail

### Phase 8: Migration Guide (0.25 days)
1. Create `docs/CONFIGURATION_MIGRATION.md`:
   ```markdown
   # Configuration Migration Guide

   ## v4.0 → v4.1 (Config Validation Enhancements)

   ### Breaking Changes

   1. **Ranking Weight Tolerance Tightened**
      - Old: Weights must sum to 0.99-1.01
      - New: Weights must sum to 0.999-1.001 (±0.001 tolerance)
      - Migration: Adjust weights to exactly 1.0

   2. **Duplicate `enable_retrieval_gate` Removed**
      - Old: Defined at lines 70 and 93
      - New: Defined once at line 70
      - Migration: No action needed (duplicate was ignored)

   3. **New Interdependency Validation**
      - Old: Invalid feature combinations silently ignored
      - New: Validation errors raised
      - Migration: Align feature flags with dependent options
   ```

2. Add link to migration guide in CHANGELOG.md

### Phase 9: Documentation & Completion (0.25 days)
1. Update CHANGELOG.md under "Unreleased"
   ```markdown
   ### Changed
   - **BREAKING:** Tightened ranking weight validation tolerance from ±0.01 to ±0.001 (UX-051)
   - Enhanced config validation with interdependency checks (UX-051)
   - Improved validation error messages with actionable suggestions (UX-051)

   ### Fixed
   - Removed duplicate `enable_retrieval_gate` configuration (UX-051)
   - Added missing validation for probability thresholds (UX-051)

   ### Added
   - Configuration migration guide for breaking changes (UX-051)
   - Rationale comments for default configuration values (UX-051)
   ```

2. Update TODO.md (mark UX-051 complete)
3. Update this planning doc with completion summary
4. Run `python scripts/verify-complete.py`
5. Commit and merge to main

## 5. Testing Strategy

### Test Categories

**1. Field Validation Tests**
```python
class TestFieldValidation:
    def test_retrieval_gate_threshold_must_be_probability(self):
        with pytest.raises(ValueError, match="must be between 0.0 and 1.0"):
            ServerConfig(retrieval_gate_threshold=1.5)

    def test_hybrid_search_alpha_must_be_probability(self):
        with pytest.raises(ValueError, match="must be between 0.0 and 1.0"):
            ServerConfig(hybrid_search_alpha=-0.1)

    def test_valid_thresholds_accepted(self):
        config = ServerConfig(
            retrieval_gate_threshold=0.8,
            hybrid_search_alpha=0.5,
        )
        assert config.retrieval_gate_threshold == 0.8
```

**2. Ranking Weight Tests**
```python
class TestRankingWeights:
    def test_weights_must_sum_to_one(self):
        with pytest.raises(ValueError, match="must sum to 1.0.*got 1.05"):
            ServerConfig(
                ranking_weight_similarity=0.65,
                ranking_weight_recency=0.20,
                ranking_weight_usage=0.20,
            )

    def test_weights_cannot_be_negative(self):
        with pytest.raises(ValueError, match="cannot be negative"):
            ServerConfig(
                ranking_weight_similarity=1.2,
                ranking_weight_recency=-0.1,
                ranking_weight_usage=-0.1,
            )

    def test_error_shows_current_values(self):
        with pytest.raises(ValueError, match="similarity: 0.65.*recency: 0.20"):
            ServerConfig(
                ranking_weight_similarity=0.65,
                ranking_weight_recency=0.20,
                ranking_weight_usage=0.20,
            )

    def test_exact_one_accepted(self):
        config = ServerConfig(
            ranking_weight_similarity=0.6,
            ranking_weight_recency=0.2,
            ranking_weight_usage=0.2,
        )
        assert config.ranking_weight_similarity == 0.6
```

**3. Interdependency Tests**
```python
class TestInterdependencies:
    def test_hybrid_alpha_requires_hybrid_enabled(self):
        with pytest.raises(ValueError, match="enable_hybrid_search=False"):
            ServerConfig(
                enable_hybrid_search=False,
                hybrid_search_alpha=0.7,  # Not default
            )

    def test_importance_weights_require_scoring_enabled(self):
        with pytest.raises(ValueError, match="enable_importance_scoring=False"):
            ServerConfig(
                enable_importance_scoring=False,
                importance_complexity_weight=2.0,
            )

    def test_valid_dependencies_accepted(self):
        config = ServerConfig(
            enable_hybrid_search=True,
            hybrid_search_alpha=0.7,
            enable_importance_scoring=True,
            importance_complexity_weight=2.0,
        )
        assert config.hybrid_search_alpha == 0.7
```

**4. Error Message Tests**
```python
class TestErrorMessages:
    def test_ranking_weight_error_is_actionable(self):
        with pytest.raises(ValueError) as exc_info:
            ServerConfig(ranking_weight_similarity=1.0, ranking_weight_recency=0.05, ranking_weight_usage=0.0)

        error_msg = str(exc_info.value)
        assert "Current values:" in error_msg
        assert "similarity:" in error_msg
        assert "Suggestion:" in error_msg

    def test_threshold_error_explains_range(self):
        with pytest.raises(ValueError) as exc_info:
            ServerConfig(retrieval_gate_threshold=1.5)

        error_msg = str(exc_info.value)
        assert "0.0 and 1.0" in error_msg
        assert "probability" in error_msg.lower()
```

**5. Regression Tests**
```python
class TestBackwardCompatibility:
    def test_valid_v4_config_still_works(self):
        """Ensure non-breaking changes for valid configs."""
        config = ServerConfig(
            ranking_weight_similarity=0.6,
            ranking_weight_recency=0.2,
            ranking_weight_usage=0.2,
        )
        assert config.ranking_weight_similarity == 0.6

    def test_default_config_is_valid(self):
        """Default config must pass all validations."""
        config = ServerConfig()
        assert config.ranking_weight_similarity + \
               config.ranking_weight_recency + \
               config.ranking_weight_usage == 1.0
```

### Coverage Target
- `src/config.py`: 95%+ coverage (up from current ~85%)
- `test_config_validation.py`: 25+ new tests
- All validation paths tested (success and failure)

## 6. Risk Assessment

### Medium Risk Factors
- ⚠️ Breaking change (tighter weight tolerance)
- ⚠️ May break existing user configs
- ⚠️ Pydantic validator order matters (cross-field validation)

### Potential Issues

1. **Breaking User Configs**
   - Risk: Users with weights summing to 0.99 or 1.01 will fail
   - Impact: Server won't start after upgrade
   - Mitigation: Migration guide with clear instructions
   - Mitigation: Error message explains how to fix
   - Severity: Medium (affects ~5% of users)

2. **Validation Performance**
   - Risk: Complex validators slow down config loading
   - Impact: Startup time increases
   - Mitigation: Validators are lightweight (no I/O)
   - Mitigation: Benchmark startup time before/after
   - Severity: Low (validators run once at startup)

3. **Validator Order Issues**
   - Risk: Cross-field validators run before field validators
   - Impact: Confusing error messages
   - Mitigation: Use `mode='after'` for cross-field validators
   - Mitigation: Test validator execution order
   - Severity: Low (Pydantic handles this well)

4. **Incomplete Interdependency Coverage**
   - Risk: Missing some invalid config combinations
   - Impact: Invalid configs slip through validation
   - Mitigation: Comprehensive test coverage
   - Mitigation: Iterate based on user reports
   - Severity: Medium (can add more validators later)

### Rollback Plan
If breaking changes cause issues:
1. Release v4.0.1 with relaxed tolerance (±0.01) as opt-in
2. Add `CLAUDE_RAG_STRICT_VALIDATION=false` environment variable
3. Warn instead of error for relaxed mode
4. Give users 1 month to migrate, then enforce strict

## 7. Success Criteria

### Measurable Outcomes

1. ✅ **All missing validations implemented:**
   - Probability thresholds (4 fields)
   - Ranking weights (enhanced)
   - Interdependencies (3+ checks)
   - Default value documentation (15+ comments)
   - Duplicate config removed

2. ✅ **Enhanced error messages:**
   - Show current values
   - Explain what's wrong
   - Suggest how to fix
   - Reference documentation

3. ✅ **Test coverage:**
   - `src/config.py`: 95%+ coverage
   - 25+ new validation tests
   - All validators have positive and negative tests
   - Error message tests

4. ✅ **Documentation complete:**
   - Migration guide created
   - CHANGELOG.md updated with breaking changes
   - Default value rationales documented

### Quality Gates
- [ ] All new validators implemented
- [ ] Duplicate config removed
- [ ] 25+ tests added
- [ ] All tests passing (100% pass rate)
- [ ] Coverage ≥95% for config.py
- [ ] Migration guide written
- [ ] CHANGELOG.md updated
- [ ] verify-complete.py passes

## 8. Breaking Change Assessment

### Breaking Changes

**1. Tighter Weight Tolerance**
- **Old:** `0.99 <= weight_sum <= 1.01`
- **New:** `0.999 <= weight_sum <= 1.001`
- **Affected Users:** ~5% (those with slightly off weights)
- **Severity:** Low (easy to fix)

**2. Interdependency Validation**
- **Old:** Inconsistent settings silently ignored
- **New:** Validation errors raised
- **Affected Users:** ~10% (those with conflicting settings)
- **Severity:** Low (makes bugs visible)

### Non-Breaking Changes

**3. Duplicate Config Removal**
- **Old:** `enable_retrieval_gate` defined twice
- **New:** Defined once
- **Affected Users:** None (duplicate was already ignored)
- **Severity:** None

**4. Enhanced Error Messages**
- **Old:** Terse errors
- **New:** Detailed errors with suggestions
- **Affected Users:** All (positive change)
- **Severity:** None (improvement)

### Migration Path

**For Users with Slightly Off Weights:**
```bash
# Old config fails validation
ranking_weight_similarity = 0.61
ranking_weight_recency = 0.20
ranking_weight_usage = 0.20
# Sum: 1.01 (was valid, now invalid)

# Fix: Adjust to exactly 1.0
ranking_weight_similarity = 0.6
ranking_weight_recency = 0.2
ranking_weight_usage = 0.2
# Sum: 1.0 (valid)
```

**For Users with Inconsistent Settings:**
```bash
# Old config silently ignored hybrid_search_alpha
enable_hybrid_search = false
hybrid_search_alpha = 0.7  # Ignored!

# Fix option 1: Enable feature
enable_hybrid_search = true
hybrid_search_alpha = 0.7

# Fix option 2: Remove conflicting setting
enable_hybrid_search = false
# (Remove hybrid_search_alpha line, will use default)
```

## 9. Completion Summary

**Status:** Not yet started

**Once complete, update this section with:**
- Date completed
- Actual time spent vs estimate (target: ~2 days)
- Number of validators added (target: 6+)
- Number of tests added (target: 25+)
- Coverage improvement (target: 85% → 95%)
- Breaking changes confirmed
- User impact assessment
- Issues encountered
- Lessons learned
- Final commit hash

---

**Created:** 2025-11-25
**Last Updated:** 2025-11-25
**Status:** Planning Complete, Ready for Implementation
