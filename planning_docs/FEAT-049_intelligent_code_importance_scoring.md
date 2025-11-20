# FEAT-049: Intelligent Code Importance Scoring

## TODO Reference
- TODO.md line 121-146: "Intelligent Code Importance Scoring (~1-2 weeks)"
- Priority: Tier 2 (Core Functionality Extensions)

## Objective
Implement dynamic importance calculation for indexed code units to replace the current fixed importance score of 0.7. This will make importance scores meaningful for discrimination between critical functions and trivial utilities in medium-to-large codebases (10,000+ code units).

## Problem Statement

### Current State
All code units receive a fixed importance score of 0.7 regardless of actual significance:
- Location: `src/memory/incremental_indexer.py:888`
- Code: `"importance": 0.7,  # Code units have moderate importance`
- User memories default to 0.5

### Issues
1. **No discrimination**: A critical authentication function gets the same score as a trivial helper
2. **Meaningless filtering**: `min_importance` filter provides no value when all code is 0.7
3. **Poor ranking**: Search results can't prioritize important code over utilities
4. **Wasted metadata**: Importance field exists but conveys no information

### Impact
For a 10,000-unit codebase:
- 100% of code has identical importance
- Filtering by importance is useless
- Search ranking ignores code significance
- Users can't identify critical functions

## Proposed Solution

### Scoring Algorithm

**Multi-factor scoring with three components:**

1. **Complexity Score (base 0.3-0.7 range):**
   - Cyclomatic complexity (branching/loops)
   - Line count (normalized)
   - Nesting depth
   - Parameter count
   - Documentation presence

2. **Usage Score (boost +0.0 to +0.2):**
   - Call graph centrality (number of callers)
   - Public vs private API (name prefix)
   - Export status (explicitly exported vs internal)

3. **Criticality Score (boost +0.0 to +0.2):**
   - Security keywords: auth, crypto, permission, token, session
   - Error handling: try/catch, error handling patterns
   - Decorators/annotations: @critical, @security, @deprecated
   - File-level signals: proximity to entry points (main, __init__)

**Final formula:**
```
importance = min(1.0, complexity_score + usage_boost + criticality_boost)
```

### Configuration

Add to `src/config.py`:
```python
# Importance scoring configuration
enable_importance_scoring: bool = True
importance_complexity_weight: float = 1.0  # Weight for complexity factors
importance_usage_weight: float = 1.0       # Weight for usage/centrality factors
importance_criticality_weight: float = 1.0  # Weight for keyword/pattern factors
```

## Implementation Plan

### Phase 1: Analysis (Current Stage)
- [x] Review existing parser infrastructure
- [x] Understand code unit extraction
- [x] Design scoring algorithm
- [x] Create planning document

### Phase 2: Complexity Analyzer
- [ ] Create `src/analysis/complexity_analyzer.py`
- [ ] Implement cyclomatic complexity calculation
- [ ] Implement line count normalization
- [ ] Implement nesting depth calculation
- [ ] Implement parameter count analysis
- [ ] Detect documentation presence (docstrings)
- [ ] Unit tests: test_complexity_analyzer.py (target: >85% coverage)

### Phase 3: Usage Analyzer (Call Graph)
- [ ] Create `src/analysis/usage_analyzer.py`
- [ ] Build lightweight call graph during parsing
- [ ] Calculate centrality scores (incoming calls)
- [ ] Detect public vs private (naming conventions)
- [ ] Detect explicit exports (from X import Y patterns)
- [ ] Unit tests: test_usage_analyzer.py (target: >85% coverage)

### Phase 4: Criticality Analyzer
- [ ] Create `src/analysis/criticality_analyzer.py`
- [ ] Define security keyword lists
- [ ] Implement keyword matching with context awareness
- [ ] Detect error handling patterns
- [ ] Parse decorators/annotations
- [ ] Calculate file-level proximity scores
- [ ] Unit tests: test_criticality_analyzer.py (target: >85% coverage)

### Phase 5: Importance Scorer
- [ ] Create `src/analysis/importance_scorer.py`
- [ ] Integrate all three analyzers
- [ ] Implement weighted scoring formula
- [ ] Add configurable weights from config
- [ ] Normalize scores to 0.0-1.0 range
- [ ] Unit tests: test_importance_scorer.py (target: >85% coverage)

### Phase 6: Integration
- [ ] Update `src/memory/incremental_indexer.py`:
  - Replace fixed `importance: 0.7`
  - Call importance scorer for each code unit
  - Pass parsed code unit data
  - Handle scoring errors gracefully (fallback to 0.5)
- [ ] Add config options to `src/config.py`
- [ ] Update `src/memory/code_unit.py` if needed (add complexity fields)
- [ ] Integration tests: test_indexing_with_importance.py

### Phase 7: Validation
- [ ] Index a real codebase (e.g., this project)
- [ ] Verify score distribution (not all 0.7)
- [ ] Spot-check critical functions (auth, crypto) have high scores
- [ ] Spot-check utilities (getters, helpers) have lower scores
- [ ] Measure performance impact (<10% indexing slowdown)
- [ ] Generate distribution report (histogram of scores)

### Phase 8: Documentation & Completion
- [ ] Update CHANGELOG.md (under "Unreleased")
- [ ] Update TODO.md (mark FEAT-049 as complete)
- [ ] Update README.md (mention intelligent scoring)
- [ ] Update USAGE.md (explain importance scoring)
- [ ] Add completion summary to this planning doc
- [ ] Commit and merge to main

## Architecture

### New Modules

```
src/analysis/
├── __init__.py
├── complexity_analyzer.py    # Cyclomatic complexity, line count, nesting
├── usage_analyzer.py          # Call graph, centrality, public/private
├── criticality_analyzer.py    # Keywords, error handling, decorators
└── importance_scorer.py       # Main scorer integrating all analyzers
```

### Data Flow

```
Code File → Parser (tree-sitter)
         ↓
    Code Units (functions, classes, methods)
         ↓
    Complexity Analyzer → complexity_score
    Usage Analyzer      → usage_boost
    Criticality Analyzer → criticality_boost
         ↓
    Importance Scorer → final_importance (0.0-1.0)
         ↓
    incremental_indexer.py → store with importance
         ↓
    Qdrant/Vector DB
```

## Test Strategy

### Unit Tests (>85% coverage target)
1. **test_complexity_analyzer.py**:
   - Test cyclomatic complexity on if/else, loops, try/catch
   - Test line count normalization (short vs long functions)
   - Test nesting depth calculation
   - Test parameter count analysis
   - Test docstring detection

2. **test_usage_analyzer.py**:
   - Test call graph construction
   - Test centrality calculation (0 callers vs many)
   - Test public vs private detection (__name, _name)
   - Test export detection (from X import Y)

3. **test_criticality_analyzer.py**:
   - Test security keyword detection (auth, crypto, token)
   - Test error handling pattern detection
   - Test decorator parsing (@critical, @deprecated)
   - Test file proximity scoring

4. **test_importance_scorer.py**:
   - Test integration of all analyzers
   - Test weighted scoring formula
   - Test normalization to 0.0-1.0
   - Test configurable weights
   - Test edge cases (empty function, huge function)

### Integration Tests
5. **test_indexing_with_importance.py**:
   - Index a small test project
   - Verify importance scores are assigned
   - Verify scores are not all 0.7
   - Verify scores are in valid range (0.0-1.0)
   - Verify scoring can be disabled via config

### Validation Tests
6. **Manual validation**:
   - Index the claude-memory-server itself
   - Generate distribution histogram
   - Spot-check 10-20 functions for reasonable scores
   - Verify critical functions (auth, security) score higher
   - Verify utilities (getters, simple helpers) score lower

## Expected Outcomes

### Score Distribution (Target)
- 0.0-0.3: 20% (trivial utilities, getters, simple helpers)
- 0.3-0.5: 30% (moderate complexity, standard functions)
- 0.5-0.7: 30% (important functions, business logic)
- 0.7-0.9: 15% (critical functions, complex algorithms)
- 0.9-1.0: 5% (core security, authentication, critical paths)

### Performance Impact
- Target: <10% indexing slowdown
- Baseline: ~10-20 files/sec (parallel mode)
- Acceptable: >9 files/sec (with scoring enabled)
- Measure: Index 100-file project with and without scoring

### Example Scores (Hypothetical)

**High importance (0.8-0.95):**
- `authenticate_user(username, password)` - security critical
- `encrypt_data(data, key)` - cryptographic operation
- `process_payment(amount, card)` - business critical
- `validate_permissions(user, resource)` - access control

**Medium importance (0.4-0.6):**
- `format_date(date_obj)` - utility function
- `get_user_by_id(user_id)` - database accessor
- `parse_config(config_str)` - data transformation

**Low importance (0.2-0.4):**
- `is_empty(value)` - trivial predicate
- `get_name()` - simple getter
- `capitalize(text)` - one-line helper

## Configuration Options

Add to `src/config.py`:

```python
class ServerConfig(BaseModel):
    # ... existing fields ...

    # Importance Scoring Configuration
    enable_importance_scoring: bool = Field(
        default=True,
        description="Enable intelligent importance scoring for code units"
    )
    importance_complexity_weight: float = Field(
        default=1.0,
        ge=0.0,
        le=2.0,
        description="Weight for complexity factors (cyclomatic, lines, nesting)"
    )
    importance_usage_weight: float = Field(
        default=1.0,
        ge=0.0,
        le=2.0,
        description="Weight for usage factors (call graph centrality, public API)"
    )
    importance_criticality_weight: float = Field(
        default=1.0,
        ge=0.0,
        le=2.0,
        description="Weight for criticality factors (security keywords, error handling)"
    )
```

## Risks & Mitigations

### Risk 1: Performance Impact
- **Mitigation**: Measure and optimize, target <10% slowdown
- **Fallback**: Add config flag to disable scoring

### Risk 2: Inaccurate Scores
- **Mitigation**: Extensive validation and spot-checking
- **Adjustment**: Weights are configurable for tuning

### Risk 3: Language-Specific Issues
- **Mitigation**: Test across multiple languages (Python, JS, TS, Java)
- **Fallback**: Language-specific scoring adjustments

### Risk 4: Breaking Changes
- **Mitigation**: Maintain backward compatibility (default enabled, fallback to 0.5 on error)
- **Testing**: Comprehensive integration tests

## Success Criteria

- [ ] All unit tests pass (>85% coverage for new modules)
- [ ] Integration tests pass (importance scores assigned correctly)
- [ ] Score distribution is non-uniform (not all 0.7)
- [ ] Critical functions score higher than utilities (spot-check validation)
- [ ] Performance impact <10% (measured on 100-file project)
- [ ] Documentation updated (CHANGELOG, TODO, README, USAGE)
- [ ] Feature can be disabled via config
- [ ] Backward compatible (no breaking changes)

## Progress Tracking

### Day 1-2: Analysis & Design ✅
- [x] Review existing code
- [x] Design algorithm
- [x] Create planning document

### Day 3-5: Core Implementation
- [ ] Complexity analyzer
- [ ] Usage analyzer
- [ ] Criticality analyzer
- [ ] Importance scorer

### Day 6-8: Integration
- [ ] Update incremental_indexer.py
- [ ] Add configuration options
- [ ] Integration tests

### Day 9-10: Validation & Polish
- [ ] Validate score distribution
- [ ] Performance testing
- [ ] Documentation
- [ ] Merge to main

## Notes & Decisions

### 2025-11-20: Initial Planning
- Decision: Use three-factor model (complexity, usage, criticality)
- Decision: Make all weights configurable
- Decision: Target <10% performance impact
- Decision: Keep fixed 0.7 as fallback on error
- Note: Will need to handle tree-sitter parsing results for complexity
- Note: Call graph will be lightweight (just count callers, not full graph)
- Note: Security keywords should be context-aware (avoid false positives)

## Code Snippets

### Current Code (to be replaced)
```python
# src/memory/incremental_indexer.py:888
metadata = {
    "id": deterministic_id,
    "category": MemoryCategory.CODE.value,
    "importance": 0.7,  # Fixed score - TO BE REPLACED
    "tags": ["code", unit.unit_type, language.lower()],
    ...
}
```

### Proposed Code (after implementation)
```python
# src/memory/incremental_indexer.py (updated)
from src.analysis.importance_scorer import ImportanceScorer

# In IncrementalIndexer.__init__
self.importance_scorer = ImportanceScorer(config=self.config)

# In _index_file
try:
    importance = self.importance_scorer.calculate_importance(
        code_unit=unit,
        file_path=file_path,
        language=language,
        call_graph=call_graph  # Built during parsing
    )
except Exception as e:
    logger.warning(f"Failed to calculate importance for {unit.name}: {e}")
    importance = 0.5  # Fallback

metadata = {
    "id": deterministic_id,
    "category": MemoryCategory.CODE.value,
    "importance": importance,  # Dynamic score
    "tags": ["code", unit.unit_type, language.lower()],
    ...
}
```

## Related Work

### Similar Features in Other Tools
- **GitHub Code Search**: Uses TF-IDF and PageRank for importance
- **Sourcegraph**: Uses call graph centrality
- **Understand (IDE)**: Uses cyclomatic complexity for highlighting

### Academic Research
- "Code Complexity Metrics and Software Quality" (IEEE 2019)
- "Call Graph Analysis for Security" (ACM 2020)
- "Identifying Critical Code Using Program Slicing" (ICSE 2021)

## Future Enhancements (Post-FEAT-049)

### Possible V2 Features
1. **Machine learning-based scoring**: Train on labeled datasets
2. **Historical importance**: Factor in git change frequency, bug fixes
3. **Team importance**: Track which code is most queried/viewed
4. **Custom importance rules**: User-defined patterns and weights
5. **Importance decay**: Reduce importance of deprecated/unused code over time

### Integration Opportunities
1. **Search ranking**: Use importance for result ranking
2. **Dashboard visualization**: Show importance distribution charts
3. **Health monitoring**: Alert on changes to critical (high-importance) code
4. **Backup prioritization**: Backup high-importance code first

---

## Implementation Status

**Status**: 🟢 Core Implementation Complete, Testing In Progress

### Completed (2025-11-20)

#### Phase 1: Analysis & Design ✅
- [x] Reviewed existing code infrastructure
- [x] Designed three-factor scoring algorithm
- [x] Created comprehensive planning document

#### Phase 2: Core Analyzers ✅
- [x] ComplexityAnalyzer (300+ lines)
  - Cyclomatic complexity calculation
  - Line count (excluding comments/blank lines)
  - Nesting depth calculation
  - Parameter counting
  - Documentation detection
  - Normalized scoring (0.3-0.7 range)

- [x] UsageAnalyzer (250+ lines)
  - Lightweight call graph construction
  - Centrality/caller counting
  - Public/private API detection
  - Export status detection
  - Usage boost calculation (0.0-0.2 range)

- [x] CriticalityAnalyzer (230+ lines)
  - Security keyword detection (60+ keywords)
  - Error handling pattern detection
  - Critical decorator detection
  - File proximity scoring
  - Criticality boost calculation (0.0-0.2 range)

#### Phase 3: Integration Module ✅
- [x] ImportanceScorer (170+ lines)
  - Integrates all three analyzers
  - Configurable weights (0.0-2.0 for each factor)
  - Batch scoring for efficiency
  - Summary statistics generation
  - Error handling with graceful fallback

#### Phase 4: Configuration ✅
- [x] Added 4 new config options to src/config.py:
  - `enable_importance_scoring` (default: True)
  - `importance_complexity_weight` (default: 1.0)
  - `importance_usage_weight` (default: 1.0)
  - `importance_criticality_weight` (default: 1.0)
- [x] Added validation (0.0-2.0 range enforcement)

#### Phase 5: Indexer Integration ✅
- [x] Updated IncrementalIndexer.__init__ to create scorer
- [x] Modified _store_units to use batch scoring
- [x] Replaced fixed importance=0.7 with dynamic calculation
- [x] Added graceful fallback (0.5 on error, 0.7 if disabled)
- [x] Maintained full backward compatibility

#### Phase 6: Testing (In Progress) 🟡
- [x] test_complexity_analyzer.py: 40 tests, 100% passing
  - 8 cyclomatic complexity tests
  - 5 line count tests
  - 4 nesting depth tests
  - 7 parameter count tests
  - 5 documentation detection tests
  - 4 overall scoring tests
  - 4 multi-language tests
  - 3 edge case tests
- [ ] test_usage_analyzer.py: Not yet created
- [ ] test_criticality_analyzer.py: Not yet created
- [ ] test_importance_scorer.py: Not yet created
- [ ] test_indexer_integration.py: Not yet created

### Remaining Work

#### Phase 7: Additional Tests (Est: 3-4 hours)
- [ ] Create test_usage_analyzer.py (~30 tests)
- [ ] Create test_criticality_analyzer.py (~25 tests)
- [ ] Create test_importance_scorer.py (~20 tests)
- [ ] Create integration tests with incremental_indexer
- [ ] Verify >85% coverage for all new modules

#### Phase 8: Validation (Est: 2-3 hours)
- [ ] Index this codebase (claude-memory-server)
- [ ] Generate score distribution report
- [ ] Verify non-uniform distribution (not all 0.7)
- [ ] Spot-check 10-20 functions:
  - Security functions should score high (>0.7)
  - Simple utilities should score low (<0.5)
- [ ] Measure performance impact (<10% target)

#### Phase 9: Documentation (Est: 1-2 hours)
- [ ] Update CHANGELOG.md with FEAT-049 entry
- [ ] Update TODO.md (mark FEAT-049 complete)
- [ ] Update README.md (mention intelligent scoring)
- [ ] Update USAGE.md (explain scoring system)

#### Phase 10: Completion
- [ ] Add completion summary to this document
- [ ] Commit final changes
- [ ] Merge FEAT-049 to main
- [ ] Clean up worktree

**Next Steps**: Create remaining test files (usage, criticality, scorer, integration)
**Estimated Time Remaining**: 6-9 hours

---

**Status**: 🟡 In Progress (Phase 1-6 complete, Phase 7-10 remaining)
**Next Steps**: Create test_usage_analyzer.py, test_criticality_analyzer.py
