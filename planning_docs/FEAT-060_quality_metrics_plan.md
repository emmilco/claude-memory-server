# FEAT-060: Code Quality Metrics & Hotspots

## TODO Reference
- **ID:** FEAT-060
- **Location:** TODO.md lines 306-318, Phase 2: Structural Analysis
- **Priority:** Tier 2 - Core Functionality Extensions (High impact)
- **Estimated Time:** 2 weeks

## Objective
Implement automated code quality analysis tools to detect complexity hotspots, semantic duplicates, and maintainability issues. Provide three new MCP tools and integrate quality metrics into existing search results. Replace manual 30-minute QA review process with automated 30-second analysis (60x speedup).

## Problem Statement

### Current Gap
- **No code quality analysis:** No way to detect complex functions, duplicates, or code smells
- **Manual QA process:** QA review requires 30+ minutes of manual searching
- **Missing metrics:** Search results lack quality indicators (complexity, duplication, maintainability)
- **No hotspot detection:** Cannot identify high-risk areas requiring refactoring

### User Impact
**QA Review Use Case:**
- Current: Manually search for code smells, complex functions, duplicates (30+ minutes)
- Proposed: Automated hotspot detection in 30 seconds (60x faster)

**Search Enhancement:**
- Current: Search results show semantic matches but no quality context
- Proposed: Results include complexity, duplication score, maintainability index

## Proposed Solution

### Three New MCP Tools

#### 1. find_quality_hotspots(project)
Returns top 20 quality issues across all categories:
- High cyclomatic complexity (>10)
- Long functions (>100 lines)
- Deep nesting (>4 levels)
- Semantic duplicates (>0.85 similarity)
- Missing documentation
- High parameter count (>5)

#### 2. find_duplicates(similarity_threshold=0.85)
Semantic duplicate detection using embeddings:
- Uses existing embedding infrastructure
- Configurable similarity threshold (0.75-0.95)
- Groups duplicates into clusters
- Returns duplicate pairs with similarity scores

#### 3. get_complexity_report(file_or_project)
Comprehensive complexity breakdown:
- Cyclomatic complexity distribution
- Function length distribution
- Nesting depth analysis
- Maintainability index calculation
- Top 10 most complex functions

### Enhanced Search Results
Add quality metrics to `search_code()` results:
- `complexity`: Cyclomatic complexity score
- `duplication_score`: Similarity to other code (0-1)
- `maintainability_index`: Overall quality score (0-100)
- `quality_flags`: ["long_function", "high_complexity", "duplicate"]

### New Search Filters
Add quality-based filters to `search_code()`:
- `min_complexity` / `max_complexity`: Filter by cyclomatic complexity
- `has_duplicates`: Boolean filter for duplicate code
- `long_functions`: Filter for functions >100 lines
- `maintainability_min`: Filter by maintainability index

## Technical Design

### Architecture

```
Quality Analysis System
│
├── src/analysis/quality_analyzer.py (NEW)
│   ├── QualityAnalyzer class
│   ├── calculate_quality_metrics()
│   ├── find_quality_hotspots()
│   └── generate_quality_report()
│
├── src/analysis/complexity_analyzer.py (EXISTING - ENHANCE)
│   ├── ComplexityAnalyzer class (already exists)
│   ├── calculate_maintainability_index() (NEW)
│   └── classify_complexity() (NEW)
│
├── src/analysis/duplicate_detector.py (EXISTING - ENHANCE)
│   ├── DuplicateDetector class (already exists)
│   ├── find_all_duplicates() (already exists)
│   ├── cluster_duplicates() (NEW)
│   └── calculate_duplication_score() (NEW)
│
└── src/core/server.py (ENHANCE)
    ├── find_quality_hotspots() - NEW MCP tool
    ├── find_duplicates() - NEW MCP tool
    ├── get_complexity_report() - NEW MCP tool
    └── search_code() - ADD quality metrics to results
```

### Data Models

```python
# Quality Metrics (added to search results)
class CodeQualityMetrics(BaseModel):
    """Quality metrics for a code unit."""
    cyclomatic_complexity: int
    line_count: int
    nesting_depth: int
    parameter_count: int
    has_documentation: bool
    duplication_score: float  # 0-1, similarity to closest duplicate
    maintainability_index: int  # 0-100, Microsoft formula
    quality_flags: List[str]  # ["long_function", "high_complexity", etc.]

# Quality Hotspot
class QualityHotspot(BaseModel):
    """A code quality issue."""
    severity: Literal["critical", "high", "medium", "low"]
    category: Literal["complexity", "duplication", "length", "nesting", "documentation"]
    file_path: str
    unit_name: str
    start_line: int
    end_line: int
    metric_value: float  # The actual metric (complexity=15, similarity=0.92, etc.)
    threshold: float  # The threshold exceeded (complexity>10, similarity>0.85)
    recommendation: str  # Specific refactoring suggestion

# Duplicate Cluster
class DuplicateCluster(BaseModel):
    """Group of similar code units."""
    canonical_id: str  # ID of the "best" version (most documented, lowest complexity)
    members: List[DuplicateMember]
    average_similarity: float
    cluster_size: int

class DuplicateMember(BaseModel):
    """Member of a duplicate cluster."""
    id: str
    file_path: str
    unit_name: str
    similarity_to_canonical: float
    line_count: int

# Complexity Report
class ComplexityReport(BaseModel):
    """Comprehensive complexity analysis."""
    scope: Literal["file", "project"]
    scope_name: str
    total_units: int
    average_complexity: float
    median_complexity: float
    max_complexity: int
    distribution: Dict[str, int]  # {"0-5": 120, "6-10": 45, "11-20": 12, ">20": 3}
    top_complex: List[ComplexFunction]
    maintainability_index: int  # Weighted average
    recommendations: List[str]

class ComplexFunction(BaseModel):
    """A particularly complex function."""
    file_path: str
    unit_name: str
    complexity: int
    line_count: int
    nesting_depth: int
    maintainability_index: int
```

### Algorithms

#### 1. Cyclomatic Complexity (Already Implemented)
**Location:** `src/analysis/complexity_analyzer.py:89-139`

**Algorithm:**
```
complexity = 1  # Base
for each decision point:
    - if/elif/else
    - for/while/do
    - case/switch
    - try/catch/except
    - logical operators (&&, ||, and, or)
    - ternary operators (?:)
    complexity += 1
return complexity
```

**Enhancement needed:** Add classification method
```python
def classify_complexity(complexity: int) -> Tuple[str, str]:
    """Classify complexity into risk levels."""
    if complexity <= 5:
        return "low", "Simple function, easy to maintain"
    elif complexity <= 10:
        return "medium", "Moderate complexity, acceptable"
    elif complexity <= 20:
        return "high", "Complex, consider refactoring"
    else:
        return "critical", "Very complex, refactor immediately"
```

#### 2. Maintainability Index (NEW)
**Formula:** Microsoft Maintainability Index
```
MI = max(0, (171 - 5.2 * ln(V) - 0.23 * G - 16.2 * ln(L)) * 100 / 171)

Where:
- V = Halstead Volume (approximation: V ≈ N * log2(n))
  - N = total operators + operands
  - n = unique operators + operands
- G = Cyclomatic Complexity
- L = Lines of Code (excluding blank/comment lines)

Simplified approximation (good enough for ranking):
MI ≈ max(0, 100 - (G * 2) - (L / 10))
```

**Classification:**
- 85-100: Highly maintainable (green)
- 65-84: Moderately maintainable (yellow)
- <65: Difficult to maintain (red)

**Implementation:**
```python
def calculate_maintainability_index(
    cyclomatic_complexity: int,
    line_count: int,
    has_documentation: bool = False
) -> int:
    """Calculate Microsoft Maintainability Index (0-100)."""
    # Simplified formula (close approximation)
    mi = 100 - (cyclomatic_complexity * 2) - (line_count / 10)

    # Documentation bonus
    if has_documentation:
        mi += 5

    # Clamp to 0-100 range
    return max(0, min(100, int(mi)))
```

#### 3. Semantic Duplicate Detection (ENHANCE EXISTING)
**Location:** `src/memory/duplicate_detector.py` (already exists)

**Current Implementation:**
- Uses cosine similarity between embeddings
- Configurable thresholds (high: 0.95, medium: 0.85, low: 0.75)
- Already detects duplicates via `find_duplicates(memory, min_threshold)`

**Enhancements Needed:**

##### 3a. Cluster Duplicates
```python
async def cluster_duplicates(
    self,
    min_threshold: float = 0.85,
    project_name: Optional[str] = None
) -> List[DuplicateCluster]:
    """
    Group similar code into clusters.

    Algorithm:
    1. Get all code units (category=CODE)
    2. For each unit, find duplicates above threshold
    3. Build clusters using union-find
    4. Select canonical member (best quality)
    5. Return clusters sorted by size
    """
    # Get all code units
    all_code = await self._get_all_code_units(project_name)

    # Build similarity graph
    edges = []
    for unit in all_code:
        duplicates = await self.find_duplicates(unit, min_threshold)
        for dup, score in duplicates:
            edges.append((unit.id, dup.id, score))

    # Union-find clustering
    clusters = self._union_find_clustering(edges)

    # Select canonical (most documented + lowest complexity)
    for cluster in clusters:
        cluster.canonical_id = self._select_canonical(cluster.members)

    return sorted(clusters, key=lambda c: c.cluster_size, reverse=True)
```

##### 3b. Calculate Duplication Score
```python
async def calculate_duplication_score(
    self,
    code_unit: MemoryUnit
) -> float:
    """
    Calculate duplication score for a single unit.

    Returns:
        0.0 = unique code (no duplicates)
        1.0 = exact duplicate exists
        0.5-0.9 = partial duplicates exist
    """
    # Find top 3 most similar code units
    duplicates = await self.find_duplicates(code_unit, min_threshold=0.75)

    if not duplicates:
        return 0.0

    # Return highest similarity score
    return duplicates[0][1]  # (unit, score)
```

#### 4. Quality Hotspot Detection (NEW)
**Algorithm:**
```python
async def find_quality_hotspots(
    self,
    project_name: str,
    max_results: int = 20
) -> List[QualityHotspot]:
    """
    Find top quality issues in a project.

    Scoring system:
    - Critical (priority 100): complexity >20 OR duplication >0.95
    - High (priority 75): complexity 11-20 OR duplication 0.85-0.95
    - Medium (priority 50): long functions (>100 lines) OR deep nesting (>4)
    - Low (priority 25): missing documentation

    Returns top 20 issues sorted by priority, then severity.
    """
    hotspots = []

    # Get all code units for project
    code_units = await self._get_all_code_units(project_name)

    for unit in code_units:
        # Calculate quality metrics
        metrics = self.quality_analyzer.analyze(unit)

        # Check thresholds and create hotspots
        if metrics.cyclomatic_complexity > 20:
            hotspots.append(QualityHotspot(
                severity="critical",
                category="complexity",
                file_path=unit.metadata["file_path"],
                unit_name=unit.metadata["unit_name"],
                metric_value=metrics.cyclomatic_complexity,
                threshold=20,
                recommendation=f"Refactor into smaller functions (target: <10)"
            ))

        # ... similar checks for other categories ...

    # Sort by severity (critical > high > medium > low)
    severity_order = {"critical": 100, "high": 75, "medium": 50, "low": 25}
    hotspots.sort(key=lambda h: severity_order[h.severity], reverse=True)

    return hotspots[:max_results]
```

### Integration with Existing Systems

#### Enhanced search_code() Results
```python
# Current search result
{
    "id": "abc123",
    "content": "def authenticate(user, password)...",
    "file_path": "src/auth.py",
    "unit_name": "authenticate",
    "similarity_score": 0.92
}

# Enhanced with quality metrics
{
    "id": "abc123",
    "content": "def authenticate(user, password)...",
    "file_path": "src/auth.py",
    "unit_name": "authenticate",
    "similarity_score": 0.92,
    "quality_metrics": {  # NEW
        "cyclomatic_complexity": 8,
        "line_count": 45,
        "nesting_depth": 3,
        "parameter_count": 2,
        "has_documentation": true,
        "duplication_score": 0.15,  # Low duplication
        "maintainability_index": 78,  # Moderate
        "quality_flags": []  # No issues
    }
}
```

#### Implementation in search_code()
```python
async def search_code(
    self,
    query: str,
    project_name: Optional[str] = None,
    limit: int = 10,
    min_complexity: Optional[int] = None,  # NEW FILTER
    max_complexity: Optional[int] = None,  # NEW FILTER
    has_duplicates: Optional[bool] = None,  # NEW FILTER
    long_functions: Optional[bool] = None,  # NEW FILTER
    maintainability_min: Optional[int] = None,  # NEW FILTER
) -> List[CodeSearchResult]:
    """Search code with quality filtering."""

    # 1. Perform semantic search (existing logic)
    results = await self._semantic_search(query, project_name, limit)

    # 2. Calculate quality metrics for each result
    for result in results:
        # Get code unit metadata
        code_unit = {
            "content": result.content,
            "signature": result.metadata.get("signature", ""),
            "unit_type": result.metadata.get("unit_type", "function"),
            "language": result.metadata.get("language", "python")
        }

        # Calculate complexity metrics
        complexity_metrics = self.complexity_analyzer.analyze(code_unit)

        # Calculate duplication score
        duplication_score = await self.duplicate_detector.calculate_duplication_score(result)

        # Calculate maintainability index
        mi = self.complexity_analyzer.calculate_maintainability_index(
            complexity_metrics.cyclomatic_complexity,
            complexity_metrics.line_count,
            complexity_metrics.has_documentation
        )

        # Determine quality flags
        quality_flags = []
        if complexity_metrics.cyclomatic_complexity > 10:
            quality_flags.append("high_complexity")
        if complexity_metrics.line_count > 100:
            quality_flags.append("long_function")
        if complexity_metrics.nesting_depth > 4:
            quality_flags.append("deep_nesting")
        if duplication_score > 0.85:
            quality_flags.append("duplicate")
        if not complexity_metrics.has_documentation:
            quality_flags.append("missing_docs")

        # Attach metrics to result
        result.quality_metrics = CodeQualityMetrics(
            cyclomatic_complexity=complexity_metrics.cyclomatic_complexity,
            line_count=complexity_metrics.line_count,
            nesting_depth=complexity_metrics.nesting_depth,
            parameter_count=complexity_metrics.parameter_count,
            has_documentation=complexity_metrics.has_documentation,
            duplication_score=duplication_score,
            maintainability_index=mi,
            quality_flags=quality_flags
        )

    # 3. Apply quality filters
    filtered_results = results

    if min_complexity is not None:
        filtered_results = [
            r for r in filtered_results
            if r.quality_metrics.cyclomatic_complexity >= min_complexity
        ]

    if max_complexity is not None:
        filtered_results = [
            r for r in filtered_results
            if r.quality_metrics.cyclomatic_complexity <= max_complexity
        ]

    if has_duplicates is not None:
        filtered_results = [
            r for r in filtered_results
            if (r.quality_metrics.duplication_score > 0.85) == has_duplicates
        ]

    if long_functions is not None:
        filtered_results = [
            r for r in filtered_results
            if (r.quality_metrics.line_count > 100) == long_functions
        ]

    if maintainability_min is not None:
        filtered_results = [
            r for r in filtered_results
            if r.quality_metrics.maintainability_index >= maintainability_min
        ]

    return filtered_results
```

## Implementation Plan

### Phase 1: Core Quality Analyzer (Days 1-2)
**File:** `src/analysis/quality_analyzer.py` (NEW)

**Tasks:**
- [ ] Create QualityAnalyzer class
- [ ] Implement calculate_quality_metrics() (integrates complexity + duplication)
- [ ] Implement classify_complexity() helper
- [ ] Implement calculate_maintainability_index()
- [ ] Implement quality flag detection logic
- [ ] Unit tests: test_quality_analyzer.py (20 tests)

**Deliverable:** QualityAnalyzer module with comprehensive metrics calculation

### Phase 2: Enhanced Duplicate Detection (Day 3)
**Files:** `src/memory/duplicate_detector.py` (ENHANCE)

**Tasks:**
- [ ] Implement cluster_duplicates() method
- [ ] Implement calculate_duplication_score() method
- [ ] Implement _select_canonical() helper (choose best duplicate)
- [ ] Implement _union_find_clustering() helper
- [ ] Unit tests: test_duplicate_clustering.py (15 tests)

**Deliverable:** Duplicate clustering and scoring functionality

### Phase 3: MCP Tool #1 - find_quality_hotspots (Day 4)
**Files:** `src/core/server.py`, `src/mcp_server.py`

**Tasks:**
- [ ] Implement find_quality_hotspots() in MemoryRAGServer
- [ ] Define request/response schemas
- [ ] Implement severity classification logic
- [ ] Implement priority sorting (critical > high > medium > low)
- [ ] Register MCP tool
- [ ] Unit tests: test_find_quality_hotspots.py (12 tests)

**Deliverable:** Working find_quality_hotspots() MCP tool

### Phase 4: MCP Tool #2 - find_duplicates (Day 4)
**Files:** `src/core/server.py`, `src/mcp_server.py`

**Tasks:**
- [ ] Implement find_duplicates() in MemoryRAGServer
- [ ] Define request/response schemas (similarity threshold, project filter)
- [ ] Integrate with DuplicateDetector.cluster_duplicates()
- [ ] Format results with cluster information
- [ ] Register MCP tool
- [ ] Unit tests: test_find_duplicates_mcp.py (10 tests)

**Deliverable:** Working find_duplicates() MCP tool

### Phase 5: MCP Tool #3 - get_complexity_report (Day 5)
**Files:** `src/core/server.py`, `src/mcp_server.py`

**Tasks:**
- [ ] Implement get_complexity_report() in MemoryRAGServer
- [ ] Define request/response schemas (scope: file or project)
- [ ] Calculate complexity distribution (histogram)
- [ ] Generate top 10 most complex functions
- [ ] Calculate project-level maintainability index
- [ ] Generate recommendations based on metrics
- [ ] Register MCP tool
- [ ] Unit tests: test_get_complexity_report.py (12 tests)

**Deliverable:** Working get_complexity_report() MCP tool

### Phase 6: Enhanced search_code() (Day 6)
**Files:** `src/core/server.py`

**Tasks:**
- [ ] Add quality metric calculation to search_code()
- [ ] Add new filter parameters (min_complexity, max_complexity, etc.)
- [ ] Update CodeSearchResult model with quality_metrics field
- [ ] Implement filter logic for quality-based filters
- [ ] Update existing search tests to verify metrics present
- [ ] New tests: test_search_code_quality_filters.py (15 tests)

**Deliverable:** search_code() returns quality metrics and supports quality filters

### Phase 7: Performance Optimization (Day 7)
**Focus:** Ensure quality analysis doesn't slow down search/indexing

**Tasks:**
- [ ] Cache quality metrics in Qdrant payload (avoid recalculation)
- [ ] Batch quality calculation during indexing (not per-search)
- [ ] Add config flag: enable_quality_metrics (default: true)
- [ ] Measure performance impact (<10% overhead target)
- [ ] Optimize duplicate detection (use vector DB for similarity, not brute force)
- [ ] Add performance tests

**Deliverable:** Quality metrics with <10% performance overhead

### Phase 8: Integration Testing (Day 8)
**Files:** `tests/integration/test_quality_system.py`

**Tasks:**
- [ ] End-to-end test: index project → find hotspots → verify correctness
- [ ] End-to-end test: index project → find duplicates → verify clusters
- [ ] End-to-end test: get complexity report → verify distribution
- [ ] End-to-end test: search with quality filters → verify filtering
- [ ] Edge case: empty project (no code)
- [ ] Edge case: single file project
- [ ] Edge case: large project (1000+ units)

**Deliverable:** Comprehensive integration test suite (25 tests)

### Phase 9: Documentation & Completion (Day 9)
**Files:** `docs/API.md`, `CHANGELOG.md`, `TODO.md`, `README.md`

**Tasks:**
- [ ] Update docs/API.md with 3 new MCP tools
- [ ] Add quality metrics documentation to API.md
- [ ] Update CHANGELOG.md with FEAT-060 entry
- [ ] Mark TODO.md FEAT-060 as complete
- [ ] Add quality metrics example to README.md
- [ ] Update this planning doc with completion summary

**Deliverable:** Complete documentation

### Phase 10: Validation (Day 10)
**Manual Testing:**
- [ ] Index this codebase (claude-memory-server)
- [ ] Run find_quality_hotspots() - verify top 20 issues
- [ ] Run find_duplicates() - verify any duplicate clusters
- [ ] Run get_complexity_report() - verify distribution makes sense
- [ ] Run search_code with quality filters - verify filtering works
- [ ] Spot-check 5-10 hotspots for correctness
- [ ] Measure end-to-end QA review time (target: <30 seconds)

**Performance Validation:**
- [ ] Measure indexing time with/without quality metrics (<10% slowdown)
- [ ] Measure search_code latency with quality metrics (<5% slowdown)

**Deliverable:** Validated feature ready for production

## Test Plan

### Unit Tests (65-70 tests total)

**test_quality_analyzer.py (20 tests):**
- Complexity classification (low, medium, high, critical)
- Maintainability index calculation
- Quality flag detection
- Edge cases (empty function, huge function)

**test_duplicate_clustering.py (15 tests):**
- Cluster formation (2-member, 5-member, 10-member clusters)
- Canonical selection (prefer documented, lower complexity)
- Duplication score calculation (0.0, 0.5, 0.9, 1.0)
- Edge cases (no duplicates, all duplicates)

**test_find_quality_hotspots.py (12 tests):**
- Hotspot detection (complexity, duplication, length, nesting)
- Severity classification
- Priority sorting
- Limit enforcement (top 20)
- Empty project handling

**test_find_duplicates_mcp.py (10 tests):**
- Threshold filtering (0.75, 0.85, 0.95)
- Cluster formatting
- Project filtering
- Empty result handling

**test_get_complexity_report.py (12 tests):**
- File-level reports
- Project-level reports
- Distribution calculation
- Top 10 selection
- Maintainability index aggregation
- Recommendation generation

**test_search_code_quality_filters.py (15 tests):**
- min_complexity filter
- max_complexity filter
- has_duplicates filter
- long_functions filter
- maintainability_min filter
- Combined filters
- Quality metrics presence in results

### Integration Tests (25 tests)

**test_quality_system.py:**
- Index small project → find hotspots → verify accuracy
- Index project with duplicates → cluster duplicates → verify clusters
- Generate complexity report → verify statistics
- Search with quality filters → verify filtering
- Large project performance (1000+ units)
- Quality metrics caching (second search faster)

### Expected Coverage
- New modules: >85% coverage
- Enhanced modules: Maintain existing >85% coverage
- Integration tests: Cover all critical paths

## Performance Impact Analysis

### Indexing Overhead
**Current:** ~10-20 files/sec (parallel mode)

**Additional work per file:**
- Quality metric calculation: ~2-5ms per unit
- Duplication scoring: Deferred to search time (not calculated during indexing)
- Total overhead: ~2-5ms × units_per_file

**Mitigation strategies:**
1. Cache quality metrics in Qdrant payload
2. Calculate during indexing (not during search)
3. Make quality metrics optional (config flag)
4. Batch calculations with existing importance scoring

**Target:** <10% slowdown (acceptable: >9 files/sec)

### Search Overhead
**Current:** 7-13ms semantic search latency

**Additional work per search:**
- Quality metrics already cached in payload (0ms)
- Filter application: ~0.1-0.5ms
- Total overhead: <1ms

**Target:** <5% slowdown (acceptable: <14ms latency)

### Duplicate Detection Performance
**Naive approach:** O(n²) comparisons (slow for large codebases)

**Optimized approach:**
- Use vector DB for similarity search (already indexed)
- Each unit: find_duplicates() = single vector search (~7-13ms)
- Total for n units: O(n × log n) = 10,000 units × 10ms = 100 seconds
- Parallelization: 100s / 8 workers = 12.5 seconds

**Caching strategy:**
- Calculate duplication scores during nightly background job
- Store in metadata: `{"duplication_score": 0.15}`
- Search reads cached value (no recalculation)

### Memory Impact
**Additional metadata per code unit:**
- Quality metrics: ~200 bytes (9 fields)
- 10,000 units × 200 bytes = 2MB (negligible)

## Code Examples

### Example 1: Find Quality Hotspots
```python
# MCP Tool Usage
response = await server.find_quality_hotspots(
    project_name="my-app",
    max_results=20
)

# Response
{
    "hotspots": [
        {
            "severity": "critical",
            "category": "complexity",
            "file_path": "src/auth.py",
            "unit_name": "validate_permissions",
            "start_line": 145,
            "end_line": 210,
            "metric_value": 24,
            "threshold": 20,
            "recommendation": "Refactor into smaller functions (target: <10)"
        },
        {
            "severity": "high",
            "category": "duplication",
            "file_path": "src/utils.py",
            "unit_name": "format_date",
            "start_line": 45,
            "end_line": 67,
            "metric_value": 0.91,
            "threshold": 0.85,
            "recommendation": "Extract common logic into shared utility"
        },
        # ... 18 more hotspots
    ],
    "summary": {
        "total_scanned": 850,
        "critical_count": 5,
        "high_count": 12,
        "medium_count": 35,
        "low_count": 78
    }
}
```

### Example 2: Find Duplicates
```python
# MCP Tool Usage
response = await server.find_duplicates(
    project_name="my-app",
    similarity_threshold=0.85,
    category="function"  # Optional: only functions
)

# Response
{
    "clusters": [
        {
            "canonical_id": "abc123",
            "canonical_name": "authenticate_user",
            "canonical_file": "src/auth/main.py",
            "members": [
                {
                    "id": "def456",
                    "file_path": "src/auth/legacy.py",
                    "unit_name": "old_authenticate",
                    "similarity": 0.92,
                    "line_count": 45
                },
                {
                    "id": "ghi789",
                    "file_path": "src/api/auth.py",
                    "unit_name": "api_authenticate",
                    "similarity": 0.88,
                    "line_count": 52
                }
            ],
            "average_similarity": 0.90,
            "cluster_size": 3
        },
        # ... more clusters
    ],
    "summary": {
        "total_duplicates": 28,
        "cluster_count": 8,
        "average_cluster_size": 3.5
    }
}
```

### Example 3: Get Complexity Report
```python
# MCP Tool Usage
response = await server.get_complexity_report(
    scope="project",
    scope_name="my-app"
)

# Response
{
    "scope": "project",
    "scope_name": "my-app",
    "total_units": 850,
    "average_complexity": 6.2,
    "median_complexity": 4,
    "max_complexity": 24,
    "distribution": {
        "0-5": 520,    # 61% - simple
        "6-10": 245,   # 29% - moderate
        "11-20": 78,   # 9% - complex
        ">20": 7       # 1% - very complex
    },
    "top_complex": [
        {
            "file_path": "src/auth.py",
            "unit_name": "validate_permissions",
            "complexity": 24,
            "line_count": 85,
            "nesting_depth": 5,
            "maintainability_index": 42
        },
        # ... top 10
    ],
    "maintainability_index": 72,  # Project average
    "recommendations": [
        "5 functions have critical complexity (>20). Consider refactoring.",
        "78 functions have high complexity (11-20). Monitor for growth.",
        "Project maintainability is moderate (72/100). Target: >80."
    ]
}
```

### Example 4: Search with Quality Filters
```python
# Find complex authentication code
results = await server.search_code(
    query="authentication logic",
    project_name="my-app",
    min_complexity=10,  # Only complex functions
    max_complexity=20,  # But not too complex
    has_duplicates=False,  # No duplicates
    maintainability_min=60  # Reasonably maintainable
)

# Results include quality metrics
{
    "results": [
        {
            "id": "abc123",
            "content": "def authenticate_user(username, password)...",
            "file_path": "src/auth.py",
            "unit_name": "authenticate_user",
            "similarity_score": 0.92,
            "quality_metrics": {
                "cyclomatic_complexity": 15,
                "line_count": 65,
                "nesting_depth": 4,
                "parameter_count": 2,
                "has_documentation": true,
                "duplication_score": 0.12,
                "maintainability_index": 68,
                "quality_flags": ["high_complexity"]
            }
        }
    ]
}
```

## Success Criteria

### Functional Requirements
- [ ] find_quality_hotspots() returns top 20 issues across 5 categories
- [ ] find_duplicates() correctly clusters similar code
- [ ] get_complexity_report() generates accurate statistics
- [ ] search_code() includes quality metrics in all results
- [ ] Quality filters correctly filter search results
- [ ] All 65-70 unit tests pass (>85% coverage)
- [ ] All 25 integration tests pass

### Performance Requirements
- [ ] Indexing overhead <10% (>9 files/sec with quality metrics)
- [ ] Search latency overhead <5% (<14ms with quality metrics)
- [ ] find_quality_hotspots() completes in <5 seconds for 1000-unit project
- [ ] find_duplicates() completes in <30 seconds for 1000-unit project

### User Experience Requirements
- [ ] QA review time reduced from 30 minutes to <30 seconds (60x speedup)
- [ ] Quality metrics are actionable (include recommendations)
- [ ] Duplicate clusters are clear (canonical member + similarity scores)
- [ ] Complexity reports are informative (distribution + top offenders)

### Documentation Requirements
- [ ] All 3 new MCP tools documented in API.md
- [ ] Quality metrics explained in API.md
- [ ] Examples provided for each tool
- [ ] CHANGELOG.md updated
- [ ] TODO.md marked complete

## Risks & Mitigations

### Risk 1: Performance Impact
**Impact:** Quality analysis slows down indexing/search
**Mitigation:**
- Cache quality metrics in Qdrant payload
- Calculate during indexing, not search
- Make quality metrics optional (config flag)
- Batch calculations with existing importance scoring

### Risk 2: Duplicate Detection Accuracy
**Impact:** False positives (flagging similar but not duplicate code)
**Mitigation:**
- Use conservative default threshold (0.85)
- Allow user to adjust threshold (0.75-0.95)
- Show similarity scores so user can judge
- Cluster duplicates (not just pairs) for better context

### Risk 3: Complexity Calculation Accuracy
**Impact:** Inaccurate complexity scores (especially for new languages)
**Mitigation:**
- Use battle-tested ComplexityAnalyzer (already in codebase)
- Test across all 17 supported languages
- Provide language-specific patterns (already implemented)
- Allow manual override of thresholds via config

### Risk 4: Memory Usage
**Impact:** Quality metadata increases storage requirements
**Mitigation:**
- Metadata is small (~200 bytes per unit)
- For 10,000 units: only 2MB overhead (negligible)
- Make quality metrics optional via config
- No additional vector storage (metrics in payload only)

## Configuration Options

Add to `src/config.py`:

```python
# Quality Metrics Configuration
enable_quality_metrics: bool = Field(
    default=True,
    description="Enable quality metric calculation during indexing"
)

quality_complexity_threshold_high: int = Field(
    default=10,
    ge=5,
    le=50,
    description="Cyclomatic complexity threshold for 'high' classification"
)

quality_complexity_threshold_critical: int = Field(
    default=20,
    ge=10,
    le=100,
    description="Cyclomatic complexity threshold for 'critical' classification"
)

quality_duplicate_threshold: float = Field(
    default=0.85,
    ge=0.0,
    le=1.0,
    description="Similarity threshold for duplicate detection"
)

quality_long_function_threshold: int = Field(
    default=100,
    ge=50,
    le=500,
    description="Line count threshold for 'long function' classification"
)

quality_deep_nesting_threshold: int = Field(
    default=4,
    ge=2,
    le=10,
    description="Nesting depth threshold for 'deep nesting' classification"
)
```

## Future Enhancements (Post-FEAT-060)

### V2 Features
1. **Historical Quality Trends:** Track quality metrics over time (git history)
2. **Automated Refactoring Suggestions:** Generate specific refactoring code
3. **Quality Gates:** Block commits/PRs with critical quality issues
4. **Custom Quality Rules:** User-defined patterns and thresholds
5. **Quality Dashboard:** Web UI for visualizing quality metrics
6. **Quality Reports:** PDF export for management/stakeholders

### Integration Opportunities
1. **CI/CD Integration:** Fail builds on quality regressions
2. **Git Pre-commit Hooks:** Warn on quality degradation
3. **IDE Integration:** Real-time quality feedback in editor
4. **Health Monitoring:** Alert on quality metric changes
5. **Backup Prioritization:** Backup high-quality code first

## Progress Tracking

**Status:** Planning Complete
**Start Date:** TBD
**Expected Completion:** Start + 10 days

### Daily Breakdown
- Day 1-2: Core quality analyzer
- Day 3: Enhanced duplicate detection
- Day 4: MCP tools #1 and #2
- Day 5: MCP tool #3
- Day 6: Enhanced search_code()
- Day 7: Performance optimization
- Day 8: Integration testing
- Day 9: Documentation
- Day 10: Validation and completion

## Notes & Decisions

### Design Decisions
1. **Reuse existing analyzers:** ComplexityAnalyzer and DuplicateDetector already exist
2. **Cache quality metrics:** Store in Qdrant payload to avoid recalculation
3. **Batch calculations:** Calculate during indexing, not search
4. **Conservative thresholds:** Default to 0.85 similarity to reduce false positives
5. **Maintainability index:** Use Microsoft formula (simplified) for industry compatibility

### Open Questions
1. Should quality metrics be calculated for ALL code or opt-in per project?
   - **Decision:** Calculate for all, make optional via config flag
2. Should duplicate detection run during indexing or on-demand?
   - **Decision:** On-demand (too slow for indexing, users request when needed)
3. Should quality thresholds be global or per-project?
   - **Decision:** Global defaults, allow per-project overrides in future

---

**Planning Status:** ✅ Complete
**Next Steps:** Begin implementation (Phase 1: Core Quality Analyzer)
