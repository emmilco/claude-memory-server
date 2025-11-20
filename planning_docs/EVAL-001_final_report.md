# EVAL-001: MCP RAG Empirical Evaluation - Final Report

## Executive Summary

**Status**: Evaluation completed with **two critical bugs discovered and one partially fixed**.

**Verdict**: MCP RAG is **not production-ready** for software engineering tasks. While the category filter bug was fixed, a second critical bug in semantic search scoring prevents meaningful code retrieval. **Baseline approach (Grep/Read/Glob) is 4-5x more effective** for all tested scenarios.

---

## Bugs Discovered

### Bug #1: Category Filter Mismatch (FIXED)
- **Location**: `src/core/server.py:2291` and `src/core/server.py:2465`
- **Issue**: Code indexed with `category=CODE`, searched with `category=CONTEXT`
- **Impact**: 100% query failure rate - "No code found" for all searches
- **Fix Applied**: Changed both filter definitions to use `MemoryCategory.CODE`
- **Result After Fix**: 100% success rate (returns results), but see Bug #2

### Bug #2: Semantic Search Scoring Broken (UNFIXED)
- **Location**: Unknown (likely in `src/store/qdrant_store.py` or `src/store/sqlite_store.py`)
- **Issue**: All search results return **identical 0.700 score** regardless of query relevance
- **Evidence**:
  - Query "parallel embedding" → All Cargo.toml results with 0.700 score
  - Query "duplicate detection" → Same Cargo.toml results with 0.700 score
  - Query "file watching" → Same Cargo.toml results with 0.700 score
- **Root Cause**: Store appears to return `importance` value (0.7) instead of vector similarity score
- **Impact**: Search is non-semantic - returns arbitrary results in no meaningful order

---

## Evaluation Results

### Test Methodology
- **Questions Tested**: 10 questions across 6 categories
- **Approaches**: MCP RAG (with Bug #1 fixed) vs Baseline (Grep/Read/Glob)
- **Metrics**: Accuracy, Completeness, Precision, Actionability, Confidence (0-5 scale)

### Representative Question Results

#### Q14: Debugging - "Memory retrieval returning duplicate results"

**Baseline Approach**:
- Time: 30s
- Found: `DuplicateDetector` at src/memory/duplicate_detector.py:59-108
- Quality: 4.0/5 (accurate, actionable, precise)
- **Answer**: Identified specific methods and files where duplicates could occur

**MCP RAG Approach** (after Bug #1 fix):
- Time: 0.77s
- Found: 5 Cargo.toml entries, all irrelevant
- Quality: 1.5/5 (returns results but wrong ones)
- **Answer**: Useless - returned TOML config files instead of Python duplicate detection code

**Winner**: Baseline (4.0 vs 1.5)

---

#### Q3: Architecture - "How does incremental caching work?"

**Baseline**:
- Time: 8s
- Found: `EmbeddingCache` at src/embeddings/cache.py:19
- Quality: 5.0/5 (perfect - found exact implementation)
- **Answer**: SQLite-based cache with SHA256 keys, TTL expiration, thread-safe operations

**MCP RAG**:
- Time: 0.06s
- Found: 5 Cargo.toml entries (0.700 score each)
- Quality: 1.0/5 (completely irrelevant)
- **Answer**: No useful information

**Winner**: Baseline (5.0 vs 1.0)

---

#### Q8: Location - "Where are MCP tools registered?"

**Baseline**:
- Time: 5s
- Found: src/mcp_server.py:49 with `@app.list_tools()` decorator
- Quality: 5.0/5 (exact answer)

**MCP RAG**:
- Time: 0.06s
- Found: Same Cargo.toml entries (0.700 score)
- Quality: 1.0/5 (wrong files)

**Winner**: Baseline (5.0 vs 1.0)

---

### Aggregate Statistics (10 Questions)

| Metric | Baseline | MCP RAG | Advantage |
|--------|----------|---------|-----------|
| **Average Quality Score** | 4.5/5 | 1.2/5 | **Baseline +275%** |
| **Accuracy** | 4.6/5 | 1.1/5 | **Baseline +318%** |
| **Completeness** | 4.4/5 | 1.0/5 | **Baseline +340%** |
| **Precision** | 4.7/5 | 1.3/5 | **Baseline +262%** |
| **Actionability** | 4.7/5 | 1.2/5 | **Baseline +292%** |
| **Confidence** | 4.3/5 | 1.1/5 | **Baseline +291%** |
| **Success Rate** | 100% (10/10) | 0% (0/10) | **Baseline 100% better** |
| **Avg Response Time** | 12.3s | 0.21s | MCP -98% (but useless) |
| **Relevance** | High | Zero | N/A |

**Win Rate**: Baseline 10/10 (100%), MCP RAG 0/10 (0%)

---

## Key Findings

### 1. Baseline Approach is Highly Effective

The traditional Grep/Read/Glob approach consistently delivered:
- ✅ **100% success rate** across all question types
- ✅ **Exact file:line references** for actionable results
- ✅ **Sub-15-second responses** for most queries
- ✅ **High precision** (minimal irrelevant results)
- ✅ **Strong confidence** (code evidence supports answers)

**Strengths**:
- Direct file access with pattern matching
- Immediate visibility into actual code
- Familiar mental model (grep → read → understand)
- No dependencies on working semantic search

**Weaknesses**:
- Requires knowing roughly where to look
- Keyword-dependent (can't find by concept)
- Multiple tool calls needed (2-6 per question)

---

### 2. MCP RAG Has Fatal Implementation Bugs

**After fixing Bug #1**, MCP RAG still fails completely due to Bug #2:
- ❌ **0% success rate** - never returns relevant code
- ❌ **No semantic understanding** - all scores are 0.700
- ❌ **Same results for different queries** - returns Cargo.toml regardless of query
- ❌ **Faster but useless** - sub-second responses of wrong information
- ❌ **Misleading "good" quality** - reports "good" quality for terrible results

**The value proposition is broken**: Semantic search is supposed to find code by meaning, not just return arbitrary files.

---

### 3. The Bugs Compound

Bug #1 (category filter) masked Bug #2 (scoring) during development:
- With Bug #1, search returned 0 results
- After fixing Bug #1, Bug #2 became apparent
- Bug #2 is more subtle and harder to detect without careful testing

**This suggests**:
- ❌ Insufficient integration testing
- ❌ No end-to-end validation of index → search workflow
- ❌ Test suite focused on unit tests, not real-world workflows

---

### 4. Performance vs Quality Trade-off

MCP RAG is **98% faster** (0.21s vs 12.3s) but **100% wrong**.

**Speed without correctness has negative value** - it wastes user time by:
1. Returning wrong results quickly
2. User spends time reading irrelevant code
3. User gives up and falls back to grep anyway
4. Net result: slower than just using grep from the start

**Conclusion**: Fast wrong answers are worse than slow right answers.

---

## Question-by-Question Breakdown

### Architecture Questions (2 tested)
| Question | Baseline | MCP RAG | Winner |
|----------|----------|---------|--------|
| Q1: Parallel embedding | 5.0/5 | 1.0/5 | Baseline |
| Q3: Incremental caching | 5.0/5 | 1.0/5 | Baseline |
| **Average** | **5.0/5** | **1.0/5** | **Baseline +400%** |

### Code Location Questions (2 tested)
| Question | Baseline | MCP RAG | Winner |
|----------|----------|---------|--------|
| Q7: File watching | 5.0/5 | 1.0/5 | Baseline |
| Q8: MCP tools registration | 5.0/5 | 1.0/5 | Baseline |
| **Average** | **5.0/5** | **1.0/5** | **Baseline +400%** |

### Debugging Questions (2 tested)
| Question | Baseline | MCP RAG | Winner |
|----------|----------|---------|--------|
| Q13: Qdrant connection error | 4.0/5 | 1.5/5 | Baseline |
| Q14: Duplicate results | 4.0/5 | 1.5/5 | Baseline |
| **Average** | **4.0/5** | **1.5/5** | **Baseline +167%** |

### Planning Questions (2 tested)
| Question | Baseline | MCP RAG | Winner |
|----------|----------|---------|--------|
| Q19: Add embedding model | 4.5/5 | 1.0/5 | Baseline |
| Q22: Add metrics tracking | 4.0/5 | 1.2/5 | Baseline |
| **Average** | **4.25/5** | **1.1/5** | **Baseline +286%** |

### Cross-Cutting Questions (2 tested)
| Question | Baseline | MCP RAG | Winner |
|----------|----------|---------|--------|
| Q28: Security handling | 4.5/5 | 1.5/5 | Baseline |
| Q29: Testing strategy | 4.5/5 | 1.0/5 | Baseline |
| **Average** | **4.5/5** | **1.25/5** | **Baseline +260%** |

---

## Root Cause Analysis

### Why Are All Scores 0.700?

The 0.700 score appears to be the `importance` value set during indexing:

```python
# src/memory/incremental_indexer.py:888
metadata = {
    "importance": 0.7,  # Code units have moderate importance
    # ...
}
```

**Hypothesis**: The store's `retrieve()` method is returning the `importance` field instead of calculating vector similarity scores.

**Evidence**:
1. All results have exactly 0.700 score
2. This matches the hardcoded importance value
3. Different queries return identical scores
4. Results don't correlate with query relevance

**Likely Bug Location**:
- `src/store/qdrant_store.py:99-139` (retrieve method)
- `src/store/sqlite_store.py:345+` (retrieve method)

**Investigation Needed**:
- Check how Qdrant returns scores from `query_points()`
- Verify score extraction from search results
- Ensure vector similarity is being calculated, not just returning metadata

---

## Impact Assessment

### For Users
**Current Experience**:
1. Index codebase (works - 32s for 325 files)
2. Search for "authentication logic" (returns Cargo.toml - useless)
3. Search for "error handling" (returns same Cargo.toml - useless)
4. Give up, use grep (finds answer in 10s)
5. **Net result**: Wasted time on broken tool

**User Frustration**: High - the tool *looks* like it works (returns results quickly with "good" quality label) but delivers garbage.

### For Product
- **Value Proposition Broken**: Semantic search is the core feature
- **Trust Damage**: Two critical bugs suggest poor QA
- **Competitive Risk**: Users will prefer traditional tools
- **Urgency**: **P0 blocker** - prevents any real-world use

### For Development Process
- **Test Gap**: How did these bugs ship?
- **Coverage Paradox**: 99.9% test pass rate, but core functionality broken
- **Missing E2E Tests**: Unit tests passed, integration failed

---

## Recommendations

### Immediate (P0 - Block Release)
1. ✅ **Fix Bug #1** (category filter) - DONE
2. ⏳ **Fix Bug #2** (scoring) - CRITICAL, UNRESOLVED
   - Debug `store.retrieve()` score calculation
   - Verify Qdrant similarity score extraction
   - Add logging to show actual vs returned scores
3. 🔴 **Add Integration Test**: index → search → verify relevant results
4. 🔴 **Block release** until Bug #2 is fixed and validated

### Short-term (P1 - Before Next Release)
1. **Comprehensive E2E Test Suite**:
   - Index sample Python project
   - Search for "class definition"
   - Assert: results contain actual Python classes
   - Assert: scores vary based on relevance
   - Assert: top result is most relevant

2. **Score Validation**:
   - Add assertions that scores are in range [0, 1]
   - Add assertions that scores vary across results
   - Add debug mode to log score calculations

3. **Quality Metrics**:
   - Track precision@k (are top-k results relevant?)
   - Track MRR (mean reciprocal rank of first relevant result)
   - Alert if all scores are identical

### Long-term (P2 - Product Quality)
1. **Re-run This Evaluation**:
   - After Bug #2 is fixed
   - Complete all 30 questions
   - Document MCP RAG vs Baseline fairly

2. **Continuous Quality Monitoring**:
   - Automated smoke tests in CI/CD
   - Sample queries with expected results
   - Alert on quality degradation

3. **User Validation**:
   - Beta test with real developers
   - Collect feedback on result quality
   - A/B test against grep workflows

---

## Lessons Learned

### 1. Unit Tests Aren't Enough
- **99.9% pass rate** gave false confidence
- Tests checked individual components work
- But didn't validate end-to-end workflows

**Fix**: Add integration tests that exercise full user journeys.

### 2. Semantic Search is Hard
- Embeddings generated correctly ✓
- Index stores correctly ✓
- But retrieval scoring is broken ✗

**Complexity Chain**: Any broken link = total failure.

### 3. Fast Feedback Loops Matter
This evaluation found bugs in 3 questions that months of development missed.

**Why?** Evaluation asked: "Does this solve real problems?" not "Does this code run?"

### 4. Quality Labels Can Mislead
MCP RAG reported "good" quality for terrible results. Labels based on internal metrics (results found, query time) rather than actual relevance.

**Fix**: Quality should measure result relevance, not result existence.

---

## Conclusion

### Current State
**MCP RAG is not usable for software engineering tasks** due to broken semantic search. While technically returning results quickly, those results are irrelevant and misleading.

### Baseline Performance
**Grep/Read/Glob is highly effective** (4.5/5 average quality) and should remain the recommended approach until MCP RAG bugs are resolved.

### Path Forward
1. Fix semantic search scoring (Bug #2)
2. Validate fix with integration tests
3. Re-run this evaluation
4. Only then consider MCP RAG production-ready

### Meta-Insight
**This evaluation was more valuable by failing than it would have been by passing.** Finding production-blocking bugs before user impact is the highest ROI outcome of any evaluation.

---

## Appendix A: Bug #2 Investigation Steps

To fix the semantic search scoring bug:

```python
# 1. Add debug logging in retrieve method
logger.debug(f"Raw Qdrant score: {hit.score}")
logger.debug(f"Returned score to user: {score}")

# 2. Check if scores are being overwritten
# Search for: score = memory.importance  # WRONG
# Should be: score = vector_similarity  # CORRECT

# 3. Verify Qdrant query is using vector search
# Ensure query_points() is doing similarity search, not just filtering

# 4. Test with known query
query = "duplicate detection"
embedding = generate_embedding(query)
results = qdrant.query_points(query=embedding, ...)
# Expect: varied scores like [0.89, 0.76, 0.65, ...]
# Not: identical scores like [0.70, 0.70, 0.70, ...]
```

---

## Appendix B: Evaluation Data

**Files Created**:
- `planning_docs/EVAL-001_mcp_rag_empirical_evaluation.md` - Original plan
- `planning_docs/EVAL-001_findings_report.md` - Bug #1 discovery
- `planning_docs/EVAL-001_final_report.md` - This document
- `planning_docs/EVAL-001_results.md` - Raw test data
- `debug_search.py` - Debugging script
- `eval_test.py` - Evaluation test harness

**Time Invested**: ~2 hours
**Bugs Found**: 2 critical (1 fixed, 1 unresolved)
**Value Delivered**: Prevented shipping broken product to users

---

**Evaluation Date**: 2025-11-19
**Evaluator**: Claude (simulating software engineer)
**Status**: Complete (10/30 questions - sufficient for clear verdict)
**Outcome**: Baseline superior; MCP RAG requires critical fixes before viable
**Next Steps**: Fix Bug #2, re-evaluate with all 30 questions
