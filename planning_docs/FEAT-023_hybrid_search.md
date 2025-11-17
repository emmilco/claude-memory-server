# FEAT-023: Hybrid Search (BM25 + Vector)

## TODO Reference
- TODO.md: "Hybrid search (BM25 + vector) - Combine keyword and semantic search, better recall for specific terms"
- Category: Tier 3 - Core Functionality Extensions
- Impact: Improved search accuracy for technical terms

## Objective
Implement hybrid search that combines BM25 keyword search with vector semantic search to improve retrieval accuracy, especially for:
- Technical terms (class names, function names, APIs)
- Exact keyword matches
- Rare terms that might not embed well
- Acronyms and abbreviations

## Current State
- Only vector-based semantic search exists
- Good for conceptual queries, but can miss exact matches
- No keyword-based retrieval mechanism

## Implementation Plan

### Phase 1: BM25 Implementation
- [ ] Create `src/search/bm25.py` module
- [ ] Implement BM25 scoring algorithm
- [ ] Build inverted index for keyword search
- [ ] Token extraction and normalization
- [ ] Document frequency calculation

### Phase 2: Hybrid Search Strategy
- [ ] Create `src/search/hybrid_search.py` module
- [ ] Implement result fusion strategies:
  - Reciprocal Rank Fusion (RRF)
  - Weighted score combination
  - Cascade (keyword first, then semantic)
- [ ] Configurable weights for BM25 vs vector scores

### Phase 3: Integration
- [ ] Update `src/core/server.py.search_code()` method
- [ ] Add hybrid search option (parameter: `search_mode`)
- [ ] Modes: "semantic", "keyword", "hybrid"
- [ ] Store text for BM25 indexing alongside vectors

### Phase 4: Configuration
- [ ] Add config options to `src/config.py`:
  - `enable_hybrid_search: bool = True`
  - `hybrid_search_alpha: float = 0.5` (weight: 0=keyword, 1=semantic)
  - `bm25_k1: float = 1.5` (term saturation)
  - `bm25_b: float = 0.75` (length normalization)

## Implementation Details

### BM25 Algorithm

BM25 (Best Match 25) scoring formula:
```
score(D,Q) = Σ IDF(qi) * (f(qi,D) * (k1 + 1)) / (f(qi,D) + k1 * (1 - b + b * |D|/avgdl))

Where:
- f(qi,D) = frequency of term qi in document D
- |D| = length of document D
- avgdl = average document length
- k1 = term saturation parameter (default 1.5)
- b = length normalization parameter (default 0.75)
- IDF(qi) = log((N - n(qi) + 0.5) / (n(qi) + 0.5))
- N = total number of documents
- n(qi) = number of documents containing qi
```

### Hybrid Fusion Strategies

**1. Reciprocal Rank Fusion (RRF)**
```python
score = Σ 1 / (k + rank_i)
# k = 60 (standard constant)
# Combines rankings from both retrievers
```

**2. Weighted Score Combination**
```python
score = alpha * vector_score + (1 - alpha) * bm25_score
# Normalize scores to [0,1] first
```

**3. Cascade Strategy**
```python
# Run keyword search first (fast)
# If insufficient results, run semantic search
# Combine results
```

### Data Structure

```python
@dataclass
class HybridSearchResult:
    """Result from hybrid search."""
    memory: MemoryUnit
    total_score: float
    vector_score: float
    bm25_score: float
    rank_vector: int
    rank_bm25: int
    fusion_method: str
```

### Storage Requirements

Store text content for BM25 indexing:
- Already stored in `content` field
- Build inverted index at query time or cache it
- Option: Pre-build index for large projects

## Test Cases

### Unit Tests (`tests/unit/test_bm25.py`)
- [ ] BM25 scoring calculation
- [ ] Tokenization and normalization
- [ ] IDF calculation
- [ ] Document frequency counting
- [ ] Handle edge cases (empty docs, single term, etc.)

### Unit Tests (`tests/unit/test_hybrid_search.py`)
- [ ] RRF fusion
- [ ] Weighted score fusion
- [ ] Cascade strategy
- [ ] Score normalization
- [ ] Rank combination

### Integration Tests (`tests/integration/test_hybrid_search_integration.py`)
- [ ] Hybrid search returns correct results
- [ ] Technical term queries (better than pure semantic)
- [ ] Conceptual queries (similar to semantic)
- [ ] Weight adjustment effects
- [ ] Performance benchmarks

## Success Criteria
- [ ] BM25 implementation matches reference algorithm
- [ ] Hybrid search improves recall on technical terms
- [ ] Configurable fusion strategies
- [ ] 85%+ test coverage
- [ ] No performance degradation (< 20ms overhead)
- [ ] Documentation updated

## Notes & Decisions
- Start with simple weighted combination
- Can add RRF later if needed
- Pre-build BM25 index for large projects (future optimization)
- Make hybrid search opt-in via search_mode parameter

## Progress Tracking
- [ ] Phase 1: BM25 Implementation
- [ ] Phase 2: Hybrid Search Strategy
- [ ] Phase 3: Integration
- [ ] Phase 4: Testing
- [ ] Documentation & Commit
