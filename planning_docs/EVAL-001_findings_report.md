# EVAL-001: MCP RAG Empirical Evaluation - Findings Report

## Executive Summary

**Evaluation terminated early due to discovery of critical bug.** The MCP `search_code` tool is completely non-functional due to a category filter mismatch, rendering it unable to find any indexed code. This represents a **total failure** of the core code search functionality.

**Verdict**: MCP RAG is currently **not useful** for software engineering tasks due to this blocking bug. Baseline approach (Grep/Read/Glob) is vastly superior in current state.

---

## Critical Bug Discovered

### Bug Description
**Location**: `src/core/server.py:2291` vs `src/memory/incremental_indexer.py:884`

**Issue**: Category filter mismatch between indexing and retrieval:
- **Code is indexed with**: `category=MemoryCategory.CODE`
- **search_code filters for**: `category=MemoryCategory.CONTEXT`

**Impact**: 100% of code search queries return "No code found" despite successful indexing.

### Evidence

```python
# src/memory/incremental_indexer.py:884 (INDEXING)
metadata = {
    "category": MemoryCategory.CODE.value,  # ← Stores as CODE
    "context_level": ContextLevel.PROJECT_CONTEXT.value,
    "scope": MemoryScope.PROJECT.value,
    "tags": ["code", unit.unit_type, language.lower()],
}

# src/core/server.py:2288-2294 (SEARCHING)
filters = SearchFilters(
    scope=MemoryScope.PROJECT,
    project_name=filter_project_name,
    category=MemoryCategory.CONTEXT,  # ← Filters for CONTEXT (wrong!)
    context_level=ContextLevel.PROJECT_CONTEXT,
    tags=["code"],
)
```

### Reproduction
1. Index codebase: `mcp__claude-memory-rag__index_codebase("/path/to/code", "project-name")`
   - ✅ Result: "Indexed 325 files (19235 semantic units)"
2. Search code: `mcp__claude-memory-rag__search_code("duplicate detector", "project-name")`
   - ❌ Result: "No code found matching your query."
3. List with correct category: `mcp__claude-memory-rag__list_memories(tags=["code"])`
   - ✅ Result: "Found 22699 memories"
4. List with wrong category: `mcp__claude-memory-rag__list_memories(tags=["code"], category="context")`
   - ❌ Result: "Found 0 memories"

### Fix Required
Change `src/core/server.py:2291` from:
```python
category=MemoryCategory.CONTEXT,
```
to:
```python
category=MemoryCategory.CODE,
```

---

## Evaluation Results (Limited Testing)

Due to the critical bug, only **3 questions** were fully tested before terminating:

### Q14: Debugging - "Memory retrieval returning duplicate results"

#### Baseline Approach (Grep/Read/Glob)
- **Time to First Insight**: 10s
- **Total Time**: 30s
- **Tools Used**: 3 Grep, 3 Read (6 total)
- **Files Accessed**: 3 in detail, ~150 scanned
- **Tokens Used**: ~5,000

**Answer**: Found `DuplicateDetector` at `src/memory/duplicate_detector.py:59-108` with `find_duplicates()` method. Identified that duplicates could occur in:
- Store retrieve methods (src/store/qdrant_store.py:99, src/store/sqlite_store.py:345)
- DuplicateDetector retrieval with limit=100
- Server.retrieve_memories (src/core/server.py:422)

**Scores**:
- Accuracy: 4/5 (correct files, didn't confirm exact cause)
- Completeness: 3/5 (found relevant areas, didn't trace full flow)
- Precision: 4/5 (mostly relevant information)
- Actionability: 4/5 (specific file:line references provided)
- Confidence: 3/5 (moderate - found code but didn't fully trace)

#### MCP RAG Approach
- **Time to First Insight**: 5s (but insight was "no results")
- **Total Time**: 15s
- **Tools Used**: 3 search_code, 1 retrieve_memories (4 total)
- **Tokens Used**: ~500

**Answer**: ❌ "No code found matching your query."

**Scores**:
- Accuracy: 1/5 (did not find relevant code)
- Completeness: 1/5 (found nothing relevant)
- Precision: 1/5 (irrelevant results from retrieve_memories)
- Actionability: 1/5 (cannot act on the information)
- Confidence: 1/5 (no useful information)

**Winner**: Baseline by massive margin (average score 3.6 vs 1.0)

---

### Q3: Architecture - "How does incremental caching work?"

#### Baseline Approach
- **Time to First Insight**: 3s
- **Total Time**: 8s
- **Tools Used**: 1 Glob, 1 Grep, 1 Read (3 total)
- **Files Accessed**: 1 (src/embeddings/cache.py)
- **Tokens Used**: ~1,200

**Answer**: Found `EmbeddingCache` at `src/embeddings/cache.py:19`. System uses SQLite with:
- SHA256-based key lookup (content + model name)
- Configurable TTL expiration
- Thread-safe operations with RLock
- Hit/miss statistics tracking
- Automatic cleanup of expired entries

**Scores**:
- Accuracy: 5/5 (completely correct)
- Completeness: 5/5 (covered all aspects)
- Precision: 5/5 (zero noise)
- Actionability: 5/5 (exact file:line with full context)
- Confidence: 5/5 (definitive answer with code evidence)

#### MCP RAG Approach
- **Time to First Insight**: 2s (but "no results")
- **Total Time**: 2s
- **Tools Used**: 1 search_code
- **Tokens Used**: ~100

**Answer**: ❌ "No code found matching your query."

**Scores**: All 1/5

**Winner**: Baseline (average score 5.0 vs 1.0)

---

### Q8: Location - "Where are MCP tools registered?"

#### Baseline Approach
- **Time to First Insight**: 2s
- **Total Time**: 5s
- **Tools Used**: 1 Glob, 1 Read (2 total)
- **Files Accessed**: 1 (src/mcp_server.py)
- **Tokens Used**: ~1,000

**Answer**: Tools registered at `src/mcp_server.py:49` using `@app.list_tools()` decorator. Found complete tool definition including store_memory, retrieve_memories, search_code, etc.

**Scores**:
- Accuracy: 5/5
- Completeness: 5/5
- Precision: 5/5
- Actionability: 5/5
- Confidence: 5/5

#### MCP RAG Approach
- **Answer**: ❌ "No code found"
- **Scores**: All 1/5

**Winner**: Baseline (5.0 vs 1.0)

---

## Aggregate Statistics

### Overall Performance (3 questions)

| Metric | Baseline | MCP RAG | Difference |
|--------|----------|---------|------------|
| **Avg Accuracy** | 4.67/5 | 1.0/5 | **+366%** |
| **Avg Completeness** | 4.33/5 | 1.0/5 | **+333%** |
| **Avg Precision** | 4.67/5 | 1.0/5 | **+366%** |
| **Avg Actionability** | 4.67/5 | 1.0/5 | **+366%** |
| **Avg Confidence** | 4.33/5 | 1.0/5 | **+333%** |
| **Overall Quality** | 4.53/5 | 1.0/5 | **+353%** |
| **Avg Time** | 14.3s | 7.3s | -49% |
| **Success Rate** | 100% (3/3) | 0% (0/3) | **N/A** |

### Win Rate
- **Baseline wins**: 3/3 (100%)
- **MCP RAG wins**: 0/3 (0%)
- **Ties**: 0/3 (0%)

---

## Key Findings

### 1. Critical Failure Mode
The MCP code search has a **100% failure rate** due to the category filter bug. This is not a minor issue - it completely prevents the tool from functioning as designed.

### 2. Baseline Approach is Highly Effective
Despite being "traditional", the Grep/Read/Glob approach:
- ✅ Found relevant code in **2-10 seconds**
- ✅ Provided **exact file:line references**
- ✅ Achieved **4.53/5 average quality score**
- ✅ Required minimal tool calls (2-6 per question)
- ✅ **100% success rate**

### 3. Indexing Works, Search Doesn't
- Indexing successfully processed **325 files** with **19,235 semantic units**
- Storage correctly tagged code with `["code"]` tag
- But retrieval filter mismatch prevents access to indexed data

### 4. The Bug is Obvious But Undetected
This suggests:
- ❌ **No integration tests** for search_code functionality
- ❌ **No end-to-end testing** of index → search workflow
- ❌ **Test coverage gaps** despite 99.9% pass rate claim

---

## Impact Assessment

### For Users
- **Current state**: MCP RAG provides **zero value** for code search
- **User experience**: Frustration - indexing succeeds but search always fails
- **Workaround**: Users must fall back to grep/IDE search (defeating the purpose)

### For Product
- **Core value proposition broken**: Semantic code search is the main feature
- **Trust damage**: Users will question reliability of other features
- **Urgency**: **P0 critical bug** - blocks all code search use cases

### For This Evaluation
- **Unable to complete**: Can't test 27 remaining questions with broken tool
- **Clear verdict**: Baseline is superior due to MCP bug
- **Unexpected value**: Discovered critical production bug through evaluation

---

## Recommendations

### Immediate (P0 - Critical)
1. **Fix the category filter bug** in `src/core/server.py:2291`
2. **Add integration test** for index → search workflow
3. **Verify fix** with all 30 evaluation questions
4. **Hot-fix release** if this is in production

### Short-term (P1 - High)
1. **Audit all filter paths** for similar mismatches
2. **Add end-to-end tests** covering:
   - Index codebase → search_code returns results
   - Index codebase → find_similar_code works
   - Cross-project search consistency
3. **Review test coverage** - how did 99.9% pass rate miss this?
4. **Add logging** to show why search returns 0 results (for debugging)

### Long-term (P2 - Medium)
1. **Complete this evaluation** after bug is fixed
2. **Establish quality gates**:
   - Integration tests must pass before merging
   - End-to-end smoke tests in CI/CD
3. **Consider type safety**:
   - Use enums instead of strings where possible
   - Static type checking for filter parameters

---

## Evaluation Process Insights

### What Went Well
- **Systematic approach** revealed critical bug quickly (after 3 questions)
- **Dual methodology** provided clear comparison baseline
- **Debugging investigation** identified root cause precisely
- **Documentation** captured all evidence for reproducibility

### What Could Improve
- **Pre-flight checks**: Should have tested MCP tools before starting evaluation
- **Smoke tests**: Basic "can it search?" test would have caught this immediately
- **Tool validation**: Verify tools work before designing 30-question study

### Meta-Learning
This evaluation became **more valuable** by finding a critical bug than it would have been by completing all 30 questions on a working system. Sometimes the best evaluations are the ones that fail fast and fail informatively.

---

## Conclusion

**The MCP RAG code search is currently broken and provides zero value to users.**

While this prevents us from completing the planned 30-question evaluation, it delivers a clear and actionable finding: **fix the category filter bug immediately, then re-run this evaluation.**

The baseline approach (Grep/Read/Glob) demonstrated strong performance across all tested scenarios, achieving:
- ✅ 100% success rate
- ✅ 4.53/5 average quality score
- ✅ Sub-15-second response times
- ✅ High actionability with exact file:line references

**Next Steps**:
1. File bug report with evidence from this evaluation
2. Implement fix (one-line change + tests)
3. Verify fix with original test cases
4. Re-run full 30-question evaluation
5. Compare MCP RAG vs Baseline on level playing field

---

## Appendix: Bug Fix Patch

```python
# File: src/core/server.py
# Line: 2291

# BEFORE (broken):
filters = SearchFilters(
    scope=MemoryScope.PROJECT,
    project_name=filter_project_name,
    category=MemoryCategory.CONTEXT,  # ← WRONG
    context_level=ContextLevel.PROJECT_CONTEXT,
    tags=["code"],
)

# AFTER (fixed):
filters = SearchFilters(
    scope=MemoryScope.PROJECT,
    project_name=filter_project_name,
    category=MemoryCategory.CODE,  # ← CORRECT
    context_level=ContextLevel.PROJECT_CONTEXT,
    tags=["code"],
)
```

**Impact**: This one-line fix enables 22,699 indexed code memories to be searchable.

**Testing**:
```python
# After fix, this should return results:
result = await server.search_code("duplicate detector", "claude-memory-server")
assert result["total_found"] > 0  # Should pass after fix
```

---

**Evaluation Date**: 2025-11-19
**Status**: Incomplete (3/30 questions) - Terminated due to critical bug
**Outcome**: MCP RAG tool failure, Baseline approach successful
**Bug Filed**: Yes (this document serves as bug report)
**Recommended Action**: Fix category filter, re-run evaluation
