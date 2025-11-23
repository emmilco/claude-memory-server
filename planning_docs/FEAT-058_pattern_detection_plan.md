# FEAT-058: Pattern Detection (Regex + Semantic Hybrid)

## TODO Reference
- **ID:** FEAT-058
- **Priority:** 🔥🔥 High-impact core functionality improvement
- **Status:** Planning
- **Category:** MCP RAG Tool Enhancement (Phase 1: Quick Wins)
- **Estimated Time:** ~1 week

## Objective

Implement hybrid pattern detection that combines **regex pattern matching** with **semantic search** to enable precise code smell detection and targeted searches. This eliminates 60% of grep usage by allowing users to find code that matches both structural patterns (e.g., "except: blocks") and semantic meaning (e.g., "error handling code").

**Example Use Case:**
- **Before:** User runs grep for "except:" → gets 200 results → manually filters for error handling → 30 minutes
- **After:** `search_code("error handling code", pattern="except:", pattern_mode="require")` → 12 relevant results → 30 seconds

## Current State

### Existing Search Capabilities
The system currently provides:
1. **Semantic search** - Find code by meaning (7-13ms latency)
2. **Keyword search** - Find code by exact text (3-7ms latency)
3. **Hybrid search** - BM25 + vector similarity (10-18ms latency)
4. **Basic filtering** - project_name, language, file_pattern

### Current Limitations
- **No regex pattern matching** within search results
- **No AST-based structural queries** (e.g., "all functions with >3 parameters")
- **Cannot combine patterns with semantics** (must use grep → manual filtering)
- **No pattern presets** for common code smells

### Why Regex + Semantic Hybrid is Needed

**QA Review Scenario (from TODO.md):**
- User needs to find all `except:` blocks (bare exception handlers - a code smell)
- But only in error handling code (not test fixtures, mock objects, etc.)
- Current approach: grep "except:" → 200 results → manual filtering → 30 min
- With hybrid: `search_code("error handling", pattern="except:", pattern_mode="require")` → 12 results → 30 sec

**Other Use Cases:**
- Find all TODO/FIXME comments in authentication code
- Detect deprecated APIs only in production code (exclude tests)
- Find security keywords (password, secret, token) in configuration files
- Locate error handlers with specific patterns (bare except, broad catch)

## Technical Design

### 1. Regex Pattern Matching Implementation

**Pattern Parameter:**
```python
async def search_code(
    self,
    query: str,
    project_name: Optional[str] = None,
    limit: int = 5,
    file_pattern: Optional[str] = None,
    language: Optional[str] = None,
    search_mode: str = "semantic",
    pattern: Optional[str] = None,  # NEW: Regex pattern to match
    pattern_mode: str = "filter",   # NEW: How to use pattern (filter/boost/require)
) -> Dict[str, Any]:
```

**Pattern Matching Logic:**
```python
import re
from typing import Optional, Pattern

class PatternMatcher:
    """Handles regex pattern matching on code content."""

    def __init__(self):
        self._pattern_cache: Dict[str, Pattern] = {}

    def compile_pattern(self, pattern: str) -> Pattern:
        """Compile regex pattern with caching."""
        if pattern not in self._pattern_cache:
            try:
                self._pattern_cache[pattern] = re.compile(pattern, re.MULTILINE | re.DOTALL)
            except re.error as e:
                raise ValidationError(f"Invalid regex pattern: {e}")
        return self._pattern_cache[pattern]

    def match(self, pattern: str, content: str) -> bool:
        """Check if pattern matches content."""
        compiled = self.compile_pattern(pattern)
        return compiled.search(content) is not None

    def find_matches(self, pattern: str, content: str) -> List[re.Match]:
        """Find all pattern matches in content."""
        compiled = self.compile_pattern(pattern)
        return list(compiled.finditer(content))

    def get_match_count(self, pattern: str, content: str) -> int:
        """Count number of pattern matches."""
        return len(self.find_matches(pattern, content))
```

### 2. Three Pattern Modes

#### Mode 1: "filter" (Post-Filter)
**Algorithm:**
1. Perform semantic search (retrieve top N results)
2. Filter results to keep only those matching pattern
3. Return filtered results with original semantic scores

**Pros:** Simple, preserves semantic relevance ranking
**Cons:** May return fewer results than requested if pattern is rare

**Implementation:**
```python
if pattern_mode == "filter":
    # Retrieve extra results to compensate for filtering
    retrieval_limit = limit * 3
    semantic_results = await self.store.retrieve(
        query_embedding=query_embedding,
        filters=filters,
        limit=retrieval_limit,
    )

    # Filter by pattern
    pattern_matcher = PatternMatcher()
    filtered_results = [
        (memory, score)
        for memory, score in semantic_results
        if pattern_matcher.match(pattern, memory.content)
    ]

    # Return top N filtered results
    results = filtered_results[:limit]
```

#### Mode 2: "boost" (Score Boosting)
**Algorithm:**
1. Perform semantic search (retrieve top N*2 results)
2. For each result, check pattern match
3. Boost semantic score by configurable factor if pattern matches
4. Re-rank by boosted scores and return top N

**Pros:** Balances pattern and semantics, doesn't exclude non-matching results
**Cons:** More complex scoring, requires tuning boost factor

**Implementation:**
```python
if pattern_mode == "boost":
    # Retrieve extra results for boosting
    retrieval_limit = limit * 2
    semantic_results = await self.store.retrieve(
        query_embedding=query_embedding,
        filters=filters,
        limit=retrieval_limit,
    )

    # Calculate boosted scores
    pattern_matcher = PatternMatcher()
    boosted_results = []

    for memory, score in semantic_results:
        if pattern_matcher.match(pattern, memory.content):
            # Boost score by 50% (configurable)
            boosted_score = score * 1.5
            pattern_matched = True
        else:
            boosted_score = score
            pattern_matched = False

        boosted_results.append({
            "memory": memory,
            "score": boosted_score,
            "pattern_matched": pattern_matched,
        })

    # Re-rank by boosted score
    boosted_results.sort(key=lambda x: x["score"], reverse=True)
    results = [(r["memory"], r["score"]) for r in boosted_results[:limit]]
```

#### Mode 3: "require" (Strict AND)
**Algorithm:**
1. Perform semantic search (retrieve top N*5 results for larger pool)
2. Filter to keep ONLY results matching both pattern AND semantic query
3. Return filtered results ranked by semantic score

**Pros:** Most precise, guarantees pattern match
**Cons:** May return no results if pattern is very specific

**Implementation:**
```python
if pattern_mode == "require":
    # Retrieve large pool for strict filtering
    retrieval_limit = limit * 5
    semantic_results = await self.store.retrieve(
        query_embedding=query_embedding,
        filters=filters,
        limit=retrieval_limit,
    )

    # Strict filter: MUST match pattern
    pattern_matcher = PatternMatcher()
    required_results = [
        (memory, score)
        for memory, score in semantic_results
        if pattern_matcher.match(pattern, memory.content)
    ]

    # Return top N (may be < limit if pattern is rare)
    results = required_results[:limit]
```

### 3. Pattern Preset Library

**Common Pattern Presets:**
```python
PATTERN_PRESETS = {
    # Error Handling
    "error_handlers": r"(try|catch|except|rescue)\s*[:\{]",
    "bare_except": r"except\s*:",  # Python code smell
    "broad_catch": r"catch\s*\(\s*Exception",  # Java/C# code smell
    "empty_catch": r"catch\s*\([^)]+\)\s*\{\s*\}",  # Empty catch blocks

    # Code Comments
    "TODO_comments": r"(TODO|FIXME|HACK|XXX|NOTE)[:|\s]",
    "deprecated_markers": r"@deprecated|@Deprecated|DEPRECATED",

    # Security Keywords
    "security_keywords": r"(password|secret|token|api[_-]?key|private[_-]?key)",
    "auth_patterns": r"(authenticate|authorize|permission|access[_-]?control)",

    # API Patterns
    "deprecated_apis": r"(deprecated\(|@Deprecated|__deprecated__|OBSOLETE)",
    "async_patterns": r"(async\s+def|await\s+|Promise\.|async\s+function)",

    # Code Smells
    "magic_numbers": r"\b\d{3,}\b",  # Numbers > 100 (likely magic numbers)
    "long_lines": r"^.{120,}$",  # Lines > 120 chars
    "multiple_returns": r"return\s+.*\n.*return\s+",  # Multiple returns in function

    # Configuration
    "config_keys": r"(config\.|env\[|process\.env\.|getenv\()",
    "hardcoded_urls": r"https?://[^\s\"']+",
}
```

**Usage:**
```python
# Use preset pattern
results = await search_code(
    query="authentication logic",
    pattern="@preset:security_keywords",
    pattern_mode="boost"
)

# Or provide custom pattern
results = await search_code(
    query="error handling",
    pattern=r"except\s*\w*Error:",
    pattern_mode="require"
)
```

### 4. Tree-sitter AST Pattern Integration

**AST-based structural queries** (future enhancement beyond FEAT-058):
```python
class ASTPatternMatcher:
    """Match AST patterns using tree-sitter."""

    def __init__(self, parser: PythonParser):
        self.parser = parser

    def match_structure(
        self,
        content: str,
        language: str,
        node_type: str,
        **constraints
    ) -> List[Dict[str, Any]]:
        """
        Match structural patterns in AST.

        Examples:
        - All functions with >3 parameters
        - All classes without docstrings
        - All if statements with >5 branches
        """
        tree = self.parser.parse_content(content, language)
        matches = []

        for node in tree.root_node.descendants:
            if node.type == node_type:
                if self._check_constraints(node, constraints):
                    matches.append({
                        "type": node.type,
                        "start_line": node.start_point[0],
                        "end_line": node.end_point[0],
                        "text": node.text.decode("utf-8"),
                    })

        return matches

    def _check_constraints(self, node, constraints: Dict[str, Any]) -> bool:
        """Check if node meets all constraints."""
        # Example: param_count > 3
        if "param_count_gt" in constraints:
            param_count = len([c for c in node.children if c.type == "parameters"])
            if param_count <= constraints["param_count_gt"]:
                return False
        return True
```

**AST Pattern Examples:**
```python
# Find all functions with >3 parameters
results = await search_code(
    query="complex business logic",
    ast_pattern={
        "node_type": "function_definition",
        "param_count_gt": 3,
    }
)

# Find all classes without docstrings
results = await search_code(
    query="undocumented classes",
    ast_pattern={
        "node_type": "class_definition",
        "has_docstring": False,
    }
)
```

### 5. Hybrid Scoring Algorithm

**Combined Scoring Formula:**
```
final_score = (alpha * semantic_score) + (beta * pattern_score)

Where:
- semantic_score: Vector similarity (0.0-1.0)
- pattern_score: Pattern match quality (0.0-1.0)
  - 0.0 = no match
  - 0.5 = partial match (pattern in content but low quality)
  - 1.0 = perfect match (pattern in key location, high quality)
- alpha: Semantic weight (default 0.7)
- beta: Pattern weight (default 0.3)
```

**Pattern Score Calculation:**
```python
def calculate_pattern_score(
    self,
    content: str,
    pattern: str,
    unit_type: str,  # function, class, method
) -> float:
    """
    Calculate pattern match quality score.

    Factors:
    1. Match exists (0/1 binary)
    2. Match count (more matches = higher score)
    3. Match location (signature vs body)
    4. Match density (matches / total_lines)
    """
    matches = self.pattern_matcher.find_matches(pattern, content)

    if not matches:
        return 0.0

    # Base score for match existence
    score = 0.5

    # Bonus for multiple matches (diminishing returns)
    match_count = len(matches)
    score += min(0.2, match_count * 0.05)

    # Bonus for matches in signature (first 2 lines)
    lines = content.split("\n")
    signature_matches = sum(
        1 for m in matches
        if m.start() < len("\n".join(lines[:2]))
    )
    if signature_matches > 0:
        score += 0.2

    # Bonus for high density (matches per line)
    density = match_count / max(len(lines), 1)
    score += min(0.1, density * 10)

    return min(1.0, score)
```

**Hybrid Search Flow:**
```
1. Generate query embedding
   ↓
2. Semantic search → retrieve top N*5 results
   ↓
3. For each result:
   a. Calculate semantic score (from vector similarity)
   b. Calculate pattern score (from regex/AST match)
   c. Combine: final_score = alpha*semantic + beta*pattern
   ↓
4. Re-rank by final_score
   ↓
5. Return top N results
```

## Implementation Phases

### Phase 1: Core Pattern Matching (Days 1-2)
**Goal:** Basic regex pattern support with filter mode

**Tasks:**
- [ ] Create `PatternMatcher` class in `src/search/pattern_matcher.py`
  - [ ] Pattern compilation with caching
  - [ ] Match validation and error handling
  - [ ] Match finding and counting
- [ ] Add `pattern` and `pattern_mode` parameters to `search_code()` method
- [ ] Implement `filter` mode (post-filter results)
- [ ] Add pattern validation and error messages
- [ ] Write 8-10 unit tests for pattern matching

**Files to Create:**
- `src/search/pattern_matcher.py` (~150 lines)

**Files to Modify:**
- `src/core/server.py` - Add pattern parameters to search_code()
- `src/core/models.py` - Add PatternMode enum

**Tests:**
```python
# Test basic pattern matching
def test_pattern_match_basic():
    matcher = PatternMatcher()
    assert matcher.match(r"except:", "try:\n    pass\nexcept:")

# Test pattern compilation caching
def test_pattern_cache():
    matcher = PatternMatcher()
    p1 = matcher.compile_pattern(r"test")
    p2 = matcher.compile_pattern(r"test")
    assert p1 is p2  # Same object from cache

# Test invalid pattern error handling
def test_invalid_pattern():
    matcher = PatternMatcher()
    with pytest.raises(ValidationError):
        matcher.match(r"(?P<invalid", "content")

# Test filter mode
async def test_search_code_filter_mode(server):
    results = await server.search_code(
        query="error handling",
        pattern=r"except:",
        pattern_mode="filter"
    )
    # All results must contain "except:"
    for result in results["results"]:
        assert "except:" in result["code_snippet"]
```

**Deliverable:** Basic pattern filtering working, 8 tests passing

### Phase 2: Pattern Modes (Days 2-3)
**Goal:** Implement boost and require modes with score calculation

**Tasks:**
- [ ] Implement `boost` mode (score boosting)
  - [ ] Basic pattern score calculation
  - [ ] Score combination formula
  - [ ] Re-ranking logic
- [ ] Implement `require` mode (strict AND)
- [ ] Add configurable boost factor to ServerConfig
- [ ] Write 5-7 tests for each mode

**Configuration:**
```python
# src/config.py
class ServerConfig(BaseModel):
    # ... existing config ...

    # Pattern search configuration
    pattern_boost_factor: float = 1.5  # Score multiplier for pattern matches
    pattern_score_alpha: float = 0.7   # Semantic score weight
    pattern_score_beta: float = 0.3    # Pattern score weight
```

**Tests:**
```python
# Test boost mode increases scores for pattern matches
async def test_pattern_boost_mode(server):
    results = await server.search_code(
        query="error handling",
        pattern=r"except:",
        pattern_mode="boost"
    )
    # Pattern-matching results should rank higher
    assert results["results"][0]["pattern_matched"] == True

# Test require mode excludes non-matching results
async def test_pattern_require_mode(server):
    results = await server.search_code(
        query="error handling",
        pattern=r"except:",
        pattern_mode="require"
    )
    # ALL results must match pattern
    assert all(r["pattern_matched"] for r in results["results"])
```

**Deliverable:** All 3 modes working, 12 additional tests passing

### Phase 3: Pattern Preset Library (Day 4)
**Goal:** Common pattern presets for code smells and security

**Tasks:**
- [ ] Create `PATTERN_PRESETS` dictionary in `pattern_matcher.py`
- [ ] Implement preset resolution (`@preset:name` syntax)
- [ ] Add 10+ common presets (error handling, security, code smells)
- [ ] Add preset listing method (`get_available_presets()`)
- [ ] Write 3-5 tests for preset resolution

**Preset Categories:**
1. **Error Handling:** bare_except, broad_catch, empty_catch
2. **Code Comments:** TODO_comments, deprecated_markers
3. **Security:** security_keywords, auth_patterns
4. **Code Smells:** magic_numbers, long_lines
5. **API Patterns:** deprecated_apis, async_patterns

**Usage:**
```python
# List available presets
presets = pattern_matcher.get_available_presets()
# Returns: ["error_handlers", "bare_except", "TODO_comments", ...]

# Use preset in search
results = await search_code(
    query="authentication code",
    pattern="@preset:security_keywords",
    pattern_mode="boost"
)
```

**Tests:**
```python
# Test preset resolution
def test_preset_resolution():
    matcher = PatternMatcher()
    pattern = matcher.resolve_preset("@preset:bare_except")
    assert pattern == r"except\s*:"

# Test preset listing
def test_list_presets():
    matcher = PatternMatcher()
    presets = matcher.get_available_presets()
    assert "bare_except" in presets
    assert "TODO_comments" in presets
```

**Deliverable:** 10+ presets available, 5 tests passing

### Phase 4: Advanced Pattern Scoring (Day 5)
**Goal:** Sophisticated pattern scoring based on match quality

**Tasks:**
- [ ] Implement advanced `calculate_pattern_score()` method
  - [ ] Match count scoring (with diminishing returns)
  - [ ] Match location scoring (signature vs body)
  - [ ] Match density scoring
- [ ] Add pattern match metadata to results (match_count, match_locations)
- [ ] Optimize scoring for performance (<1ms overhead)
- [ ] Write 5-7 tests for scoring algorithm

**Pattern Score Factors:**
```
1. Match exists (binary): +0.5
2. Match count (diminishing): +0.2 max
3. Signature match: +0.2
4. High density: +0.1
Total max: 1.0
```

**Result Enrichment:**
```python
# Add pattern metadata to results
{
    "code_snippet": "...",
    "relevance_score": 0.85,
    "pattern_matched": True,
    "pattern_score": 0.75,
    "pattern_match_count": 3,
    "pattern_match_locations": [
        {"line": 5, "column": 10, "text": "except:"},
        {"line": 12, "column": 8, "text": "except:"},
    ]
}
```

**Tests:**
```python
# Test pattern score calculation
def test_pattern_score_calculation():
    matcher = PatternMatcher()
    content = "try:\n    pass\nexcept:\n    pass"
    score = matcher.calculate_pattern_score(content, r"except:", "function")
    assert 0.5 <= score <= 1.0

# Test match location tracking
def test_match_locations():
    matcher = PatternMatcher()
    content = "try:\n    pass\nexcept:\n    log()\nexcept:\n    pass"
    locations = matcher.get_match_locations(content, r"except:")
    assert len(locations) == 2
    assert locations[0]["line"] == 3
    assert locations[1]["line"] == 5
```

**Deliverable:** Advanced scoring working, 7 tests passing, match metadata in results

### Phase 5: Integration & Documentation (Days 6-7)
**Goal:** Integration tests, documentation, and polish

**Tasks:**
- [ ] Write 5-8 integration tests (end-to-end scenarios)
- [ ] Update API documentation in `docs/API.md`
- [ ] Add pattern search examples to `docs/USAGE.md`
- [ ] Update MCP tool description for `search_code`
- [ ] Performance testing (ensure <5ms overhead)
- [ ] Add pattern search tutorial to `TUTORIAL.md`

**Integration Test Scenarios:**
```python
# Scenario 1: QA Review - Find bare except blocks in error handlers
async def test_qa_review_bare_except(indexer, server):
    # Index sample project with error handlers
    await indexer.index_directory("examples/error_handling")

    # Search for bare except blocks in error handling code
    results = await server.search_code(
        query="error handling code",
        pattern="@preset:bare_except",
        pattern_mode="require",
        limit=20
    )

    # Verify: All results are error handlers with bare except
    assert len(results["results"]) > 0
    for result in results["results"]:
        assert "error" in result["code_snippet"].lower()
        assert "except:" in result["code_snippet"]

# Scenario 2: Security Audit - Find hardcoded secrets
async def test_security_audit_secrets(indexer, server):
    await indexer.index_directory("examples/config_files")

    results = await server.search_code(
        query="configuration and settings",
        pattern="@preset:security_keywords",
        pattern_mode="boost",
        language="python"
    )

    # Verify: Security-related configs ranked higher
    assert results["results"][0]["pattern_matched"] == True

# Scenario 3: Code Smell Detection - Find TODO markers in auth code
async def test_code_smell_todos(indexer, server):
    await indexer.index_directory("examples/auth_service")

    results = await server.search_code(
        query="authentication and authorization",
        pattern="@preset:TODO_comments",
        pattern_mode="filter",
        file_pattern="**/auth/**"
    )

    # Verify: All results have TODO/FIXME markers
    for result in results["results"]:
        assert any(marker in result["code_snippet"] for marker in ["TODO", "FIXME", "HACK"])
```

**Documentation Additions:**
```markdown
# Pattern Detection Examples

## Find Bare Exception Handlers (Code Smell)
```python
results = await search_code(
    query="error handling code",
    pattern="@preset:bare_except",
    pattern_mode="require"
)
```

## Find Security Keywords in Config Files
```python
results = await search_code(
    query="configuration settings",
    pattern="@preset:security_keywords",
    pattern_mode="boost",
    file_pattern="**/config/*.py"
)
```

## Find Deprecated APIs in Production Code
```python
results = await search_code(
    query="API endpoints",
    pattern="@preset:deprecated_apis",
    pattern_mode="filter",
    file_pattern="src/**/*.py"  # Exclude tests
)
```

## Custom Pattern: Find Functions with Multiple Returns
```python
results = await search_code(
    query="complex business logic",
    pattern=r"return\s+.*\n.*return\s+",
    pattern_mode="boost"
)
```
```

**Performance Targets:**
- Pattern matching overhead: <5ms per search
- Filter mode: <2ms additional latency
- Boost mode: <3ms additional latency
- Require mode: <5ms additional latency

**Deliverable:** 8 integration tests passing, full documentation, tutorial examples

## Code Examples

### Usage Patterns

**Example 1: QA Review - Find Code Smells**
```python
# Find all bare except blocks in error handling code
results = await server.search_code(
    query="error handling and exception management",
    pattern="@preset:bare_except",
    pattern_mode="require",
    limit=20
)

print(f"Found {results['total_found']} bare except blocks")
for result in results["results"]:
    print(f"{result['file_path']}:{result['start_line']}")
    print(f"  Pattern matches: {result['pattern_match_count']}")
    print(f"  Snippet: {result['code_snippet'][:100]}...")
```

**Example 2: Security Audit - Find Hardcoded Secrets**
```python
# Find security-sensitive config with hardcoded values
results = await server.search_code(
    query="configuration and environment variables",
    pattern="@preset:security_keywords",
    pattern_mode="boost",
    file_pattern="**/config/*.py"
)

# Security matches ranked higher due to boost mode
for result in results["results"]:
    if result["pattern_matched"]:
        print(f"⚠️ SECURITY: {result['file_path']}:{result['start_line']}")
        for match in result["pattern_match_locations"]:
            print(f"  Line {match['line']}: {match['text']}")
```

**Example 3: Technical Debt - Find TODO Markers**
```python
# Find all TODOs in authentication code
results = await server.search_code(
    query="authentication and authorization logic",
    pattern="@preset:TODO_comments",
    pattern_mode="filter",
    file_pattern="**/auth/**/*.py"
)

# Group by file for reporting
from collections import defaultdict
todos_by_file = defaultdict(list)

for result in results["results"]:
    todos_by_file[result["file_path"]].append({
        "line": result["start_line"],
        "text": result["code_snippet"]
    })

for file_path, todos in todos_by_file.items():
    print(f"\n{file_path}: {len(todos)} TODOs")
    for todo in todos:
        print(f"  Line {todo['line']}: {todo['text'][:80]}...")
```

### Implementation Example

**Pattern Matcher Class:**
```python
# src/search/pattern_matcher.py

import re
from typing import List, Dict, Any, Optional, Pattern
from src.core.exceptions import ValidationError

# Pattern presets for common use cases
PATTERN_PRESETS = {
    "bare_except": r"except\s*:",
    "broad_catch": r"catch\s*\(\s*Exception",
    "TODO_comments": r"(TODO|FIXME|HACK|XXX|NOTE)[:|\s]",
    "security_keywords": r"(password|secret|token|api[_-]?key|private[_-]?key)",
    "deprecated_apis": r"(deprecated\(|@Deprecated|__deprecated__|OBSOLETE)",
    # ... more presets
}

class PatternMatcher:
    """Handles regex pattern matching on code content."""

    def __init__(self):
        self._pattern_cache: Dict[str, Pattern] = {}

    def compile_pattern(self, pattern: str) -> Pattern:
        """Compile regex pattern with caching and validation."""
        # Resolve preset if pattern starts with @preset:
        if pattern.startswith("@preset:"):
            preset_name = pattern[8:]  # Remove "@preset:" prefix
            if preset_name not in PATTERN_PRESETS:
                raise ValidationError(
                    f"Unknown pattern preset: {preset_name}. "
                    f"Available presets: {', '.join(PATTERN_PRESETS.keys())}"
                )
            pattern = PATTERN_PRESETS[preset_name]

        # Check cache
        if pattern not in self._pattern_cache:
            try:
                self._pattern_cache[pattern] = re.compile(
                    pattern,
                    re.MULTILINE | re.DOTALL
                )
            except re.error as e:
                raise ValidationError(f"Invalid regex pattern '{pattern}': {e}")

        return self._pattern_cache[pattern]

    def match(self, pattern: str, content: str) -> bool:
        """Check if pattern matches content."""
        compiled = self.compile_pattern(pattern)
        return compiled.search(content) is not None

    def find_matches(self, pattern: str, content: str) -> List[re.Match]:
        """Find all pattern matches in content."""
        compiled = self.compile_pattern(pattern)
        return list(compiled.finditer(content))

    def get_match_count(self, pattern: str, content: str) -> int:
        """Count number of pattern matches."""
        return len(self.find_matches(pattern, content))

    def get_match_locations(
        self,
        pattern: str,
        content: str
    ) -> List[Dict[str, Any]]:
        """
        Get detailed match locations with line numbers.

        Returns:
            List of dicts with keys: line, column, text
        """
        matches = self.find_matches(pattern, content)
        locations = []

        lines = content.split("\n")
        line_offsets = [0]
        for line in lines:
            line_offsets.append(line_offsets[-1] + len(line) + 1)  # +1 for newline

        for match in matches:
            # Find line number from byte offset
            start_pos = match.start()
            line_num = 0
            for i, offset in enumerate(line_offsets):
                if offset > start_pos:
                    line_num = i
                    break

            # Find column
            column = start_pos - line_offsets[line_num - 1] if line_num > 0 else start_pos

            locations.append({
                "line": line_num,
                "column": column,
                "text": match.group(0),
                "start": match.start(),
                "end": match.end(),
            })

        return locations

    def calculate_pattern_score(
        self,
        content: str,
        pattern: str,
        unit_type: str = "function",
    ) -> float:
        """
        Calculate pattern match quality score (0.0-1.0).

        Factors:
        - Match exists (binary): +0.5
        - Match count (diminishing): +0.2 max
        - Signature match: +0.2
        - High density: +0.1
        """
        matches = self.find_matches(pattern, content)

        if not matches:
            return 0.0

        # Base score for match existence
        score = 0.5

        # Bonus for multiple matches (diminishing returns)
        match_count = len(matches)
        score += min(0.2, match_count * 0.05)

        # Bonus for matches in signature (first 2 lines)
        lines = content.split("\n")
        signature_text = "\n".join(lines[:2])
        signature_matches = sum(
            1 for m in matches
            if m.start() < len(signature_text)
        )
        if signature_matches > 0:
            score += 0.2

        # Bonus for high density (matches per line)
        line_count = max(len(lines), 1)
        density = match_count / line_count
        score += min(0.1, density * 10)

        return min(1.0, score)

    def get_available_presets(self) -> List[str]:
        """Get list of available pattern presets."""
        return sorted(PATTERN_PRESETS.keys())
```

**Integration in search_code():**
```python
# src/core/server.py

async def search_code(
    self,
    query: str,
    project_name: Optional[str] = None,
    limit: int = 5,
    file_pattern: Optional[str] = None,
    language: Optional[str] = None,
    search_mode: str = "semantic",
    pattern: Optional[str] = None,
    pattern_mode: str = "filter",
) -> Dict[str, Any]:
    """Search code with optional pattern matching."""

    # ... existing code for semantic search ...

    # Apply pattern matching if pattern is provided
    if pattern:
        if not hasattr(self, '_pattern_matcher'):
            from src.search.pattern_matcher import PatternMatcher
            self._pattern_matcher = PatternMatcher()

        pattern_matcher = self._pattern_matcher

        # Validate pattern mode
        valid_modes = ["filter", "boost", "require"]
        if pattern_mode not in valid_modes:
            raise ValidationError(
                f"Invalid pattern_mode: {pattern_mode}. "
                f"Must be one of: {', '.join(valid_modes)}"
            )

        # Apply pattern matching based on mode
        if pattern_mode == "filter":
            # Retrieve extra results to compensate for filtering
            retrieval_limit = limit * 3
            semantic_results = await self.store.retrieve(
                query_embedding=query_embedding,
                filters=filters,
                limit=retrieval_limit,
            )

            # Filter by pattern
            filtered_results = []
            for memory, score in semantic_results:
                if pattern_matcher.match(pattern, memory.content):
                    # Add pattern metadata
                    match_count = pattern_matcher.get_match_count(pattern, memory.content)
                    match_locations = pattern_matcher.get_match_locations(pattern, memory.content)

                    filtered_results.append({
                        "memory": memory,
                        "score": score,
                        "pattern_matched": True,
                        "pattern_match_count": match_count,
                        "pattern_match_locations": match_locations,
                    })

                if len(filtered_results) >= limit:
                    break

            results = filtered_results

        elif pattern_mode == "boost":
            # Retrieve extra results for boosting
            retrieval_limit = limit * 2
            semantic_results = await self.store.retrieve(
                query_embedding=query_embedding,
                filters=filters,
                limit=retrieval_limit,
            )

            # Calculate boosted scores
            boosted_results = []
            for memory, score in semantic_results:
                pattern_matched = pattern_matcher.match(pattern, memory.content)

                if pattern_matched:
                    # Calculate pattern quality score
                    pattern_score = pattern_matcher.calculate_pattern_score(
                        memory.content,
                        pattern,
                        unit_type=memory.metadata.get("unit_type", "function")
                    )

                    # Combine scores: alpha*semantic + beta*pattern
                    alpha = self.config.pattern_score_alpha  # 0.7
                    beta = self.config.pattern_score_beta    # 0.3
                    final_score = (alpha * score) + (beta * pattern_score)

                    match_count = pattern_matcher.get_match_count(pattern, memory.content)
                    match_locations = pattern_matcher.get_match_locations(pattern, memory.content)
                else:
                    final_score = score
                    match_count = 0
                    match_locations = []

                boosted_results.append({
                    "memory": memory,
                    "score": final_score,
                    "pattern_matched": pattern_matched,
                    "pattern_match_count": match_count,
                    "pattern_match_locations": match_locations,
                })

            # Re-rank by boosted score
            boosted_results.sort(key=lambda x: x["score"], reverse=True)
            results = boosted_results[:limit]

        elif pattern_mode == "require":
            # Retrieve large pool for strict filtering
            retrieval_limit = limit * 5
            semantic_results = await self.store.retrieve(
                query_embedding=query_embedding,
                filters=filters,
                limit=retrieval_limit,
            )

            # Strict filter: MUST match pattern
            required_results = []
            for memory, score in semantic_results:
                if pattern_matcher.match(pattern, memory.content):
                    match_count = pattern_matcher.get_match_count(pattern, memory.content)
                    match_locations = pattern_matcher.get_match_locations(pattern, memory.content)

                    required_results.append({
                        "memory": memory,
                        "score": score,
                        "pattern_matched": True,
                        "pattern_match_count": match_count,
                        "pattern_match_locations": match_locations,
                    })

                if len(required_results) >= limit:
                    break

            results = required_results

    # Format results (existing code)
    # ...
```

## Test Plan

### Unit Tests (15-20 tests)

**Pattern Matching Tests (8 tests):**
1. ✅ `test_pattern_compile_basic` - Basic pattern compilation
2. ✅ `test_pattern_compile_cache` - Pattern caching works
3. ✅ `test_pattern_invalid` - Invalid pattern raises ValidationError
4. ✅ `test_pattern_match_simple` - Simple pattern matches content
5. ✅ `test_pattern_match_complex` - Complex regex with groups
6. ✅ `test_pattern_find_matches` - Find all matches in content
7. ✅ `test_pattern_match_count` - Count matches correctly
8. ✅ `test_pattern_match_locations` - Extract match locations with line numbers

**Pattern Mode Tests (9 tests):**
9. ✅ `test_filter_mode_basic` - Filter mode excludes non-matching results
10. ✅ `test_filter_mode_empty` - Filter mode with no matches returns empty
11. ✅ `test_boost_mode_basic` - Boost mode increases scores for pattern matches
12. ✅ `test_boost_mode_ranking` - Boosted results rank higher
13. ✅ `test_require_mode_basic` - Require mode only returns pattern matches
14. ✅ `test_require_mode_strict` - Require mode excludes ALL non-matching results
15. ✅ `test_invalid_pattern_mode` - Invalid mode raises ValidationError
16. ✅ `test_pattern_mode_with_empty_query` - Empty query handled gracefully
17. ✅ `test_pattern_mode_performance` - Pattern matching <5ms overhead

**Preset Tests (5 tests):**
18. ✅ `test_preset_resolution` - @preset:name resolves to pattern
19. ✅ `test_preset_invalid` - Unknown preset raises error
20. ✅ `test_preset_list` - List available presets
21. ✅ `test_preset_bare_except` - bare_except preset works correctly
22. ✅ `test_preset_security_keywords` - security_keywords preset works

**Scoring Tests (3 tests):**
23. ✅ `test_pattern_score_basic` - Basic score calculation
24. ✅ `test_pattern_score_multiple_matches` - Multiple matches increase score
25. ✅ `test_pattern_score_signature_bonus` - Signature matches get bonus

### Integration Tests (8 tests)

**End-to-End Scenarios:**
1. ✅ `test_qa_review_bare_except` - QA review: Find bare except blocks in error handlers
2. ✅ `test_security_audit_secrets` - Security audit: Find hardcoded secrets in config
3. ✅ `test_code_smell_todos` - Technical debt: Find TODO markers in auth code
4. ✅ `test_deprecated_api_detection` - Find deprecated APIs in production code
5. ✅ `test_complex_business_logic` - Find complex functions with multiple returns
6. ✅ `test_pattern_with_file_filter` - Pattern + file_pattern filter combination
7. ✅ `test_pattern_with_language_filter` - Pattern + language filter combination
8. ✅ `test_hybrid_search_with_pattern` - Hybrid search mode + pattern matching

**Performance Tests:**
9. ✅ `test_pattern_performance_overhead` - Pattern matching adds <5ms latency
10. ✅ `test_pattern_cache_performance` - Cached patterns compile <0.1ms

### Total: 25-30 tests

## Performance Analysis

### Baseline Performance (Current)
- Semantic search: 7-13ms
- Keyword search: 3-7ms
- Hybrid search: 10-18ms

### Pattern Matching Overhead

**Filter Mode:**
- Regex compilation (first time): ~0.5ms
- Regex compilation (cached): ~0.05ms
- Pattern matching per result: ~0.2ms
- **Total overhead:** <2ms (for 10 results)

**Boost Mode:**
- Pattern matching: ~0.2ms per result
- Score calculation: ~0.1ms per result
- Re-ranking: ~0.5ms (sorting)
- **Total overhead:** <3ms (for 20 results)

**Require Mode:**
- Pattern matching: ~0.2ms per result
- Filtering: ~0.5ms (for 50 results)
- **Total overhead:** <5ms (for 50 results)

### Optimization Strategies

**1. Pattern Compilation Caching**
- Cache compiled regex patterns (already implemented)
- Reduces compilation overhead from 0.5ms to 0.05ms
- **Impact:** 90% reduction in compilation time

**2. Early Termination**
```python
# In filter/require modes, stop when we have enough results
if len(filtered_results) >= limit:
    break  # Don't process remaining results
```
- **Impact:** 50% reduction in processing time for common queries

**3. Parallel Pattern Matching**
```python
# For large result sets (>100), use parallel processing
from concurrent.futures import ThreadPoolExecutor

if len(results) > 100:
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [
            executor.submit(pattern_matcher.match, pattern, memory.content)
            for memory, _ in results
        ]
        matches = [f.result() for f in futures]
```
- **Impact:** 3-4x speedup for large result sets

**4. Pattern Complexity Analysis**
```python
# Warn if pattern is expensive (catastrophic backtracking risk)
import re

def analyze_pattern_complexity(pattern: str) -> str:
    # Check for nested quantifiers (high risk)
    if re.search(r'\*.*\*|\+.*\+', pattern):
        return "high"
    # Check for alternation (medium risk)
    elif '|' in pattern:
        return "medium"
    else:
        return "low"

# Suggest simpler patterns for high-complexity patterns
if complexity == "high":
    logger.warning(
        f"Pattern '{pattern}' has high complexity. "
        "Consider simplifying to avoid performance issues."
    )
```

### Expected Performance (With Pattern Matching)

**Filter Mode:**
- Semantic search: 7-13ms
- Pattern filtering: +2ms
- **Total: 9-15ms** (38% overhead)

**Boost Mode:**
- Semantic search: 7-13ms
- Pattern boosting: +3ms
- **Total: 10-16ms** (54% overhead)

**Require Mode:**
- Semantic search: 7-13ms
- Pattern filtering: +5ms
- **Total: 12-18ms** (85% overhead)

**All modes stay under 20ms (still fast!)**

## Success Criteria

### Functional Requirements
✅ All 3 pattern modes working correctly:
- ✅ Filter mode: Post-filter results by pattern
- ✅ Boost mode: Boost scores for pattern matches
- ✅ Require mode: Only return pattern-matching results

✅ Pattern preset library:
- ✅ 10+ common presets implemented
- ✅ Preset resolution (@preset:name) working
- ✅ Easy to add new presets

✅ Pattern match metadata:
- ✅ match_count in results
- ✅ match_locations with line numbers
- ✅ pattern_matched boolean flag

### Quality Requirements
✅ Test coverage:
- ✅ 15-20 unit tests (all passing)
- ✅ 8 integration tests (all passing)
- ✅ 80%+ code coverage for pattern_matcher.py

✅ Error handling:
- ✅ Invalid regex patterns → ValidationError
- ✅ Unknown presets → ValidationError with available presets
- ✅ Invalid pattern_mode → ValidationError

✅ Documentation:
- ✅ API documentation updated
- ✅ Usage examples in docs/USAGE.md
- ✅ Tutorial examples added
- ✅ MCP tool description updated

### Performance Requirements
✅ Pattern matching overhead:
- ✅ Filter mode: <2ms additional latency
- ✅ Boost mode: <3ms additional latency
- ✅ Require mode: <5ms additional latency

✅ Total search latency:
- ✅ Filter mode: <15ms total
- ✅ Boost mode: <16ms total
- ✅ Require mode: <18ms total

✅ Memory usage:
- ✅ Pattern cache: <1MB (for 100 cached patterns)
- ✅ No memory leaks in pattern compilation

### Impact Metrics (from TODO.md)
✅ **Eliminate 60% of grep usage:**
- Baseline: Users run grep 100 times/week
- After: Users run grep 40 times/week (60% reduction)
- Measured by: Grep command frequency in MCP logs

✅ **10x faster QA reviews:**
- Baseline: QA review takes 30 minutes (grep + manual filtering)
- After: QA review takes 3 minutes (pattern + semantic search)
- Measured by: Time to find code smells in 10K LOC project

✅ **User adoption:**
- ✅ 50%+ of search_code calls use pattern parameter (after 30 days)
- ✅ 10+ unique pattern presets used (shows preset library value)

## Next Steps After FEAT-058

### Related Features (from TODO.md)

**FEAT-056: Advanced Filtering & Sorting** (1 week)
- Add `file_pattern`, `complexity_min/max`, `modified_after/before` filters
- Add `sort_by` parameter (relevance, complexity, size, recency, importance)
- Synergy: Pattern matching + advanced filters = powerful search

**FEAT-059: Structural/Relational Queries** (2 weeks)
- Add AST-based structural queries (use tree-sitter integration)
- Find functions with >3 parameters, classes without docstrings
- Synergy: AST patterns complement regex patterns

**FEAT-060: Code Quality Metrics & Hotspots** (2 weeks)
- Find quality hotspots (high complexity, duplicates, long functions)
- Combine pattern matching with complexity metrics
- Synergy: Pattern presets for code smells + quality metrics

### AST Pattern Extension (Future)

After FEAT-058, extend pattern matching to support **AST-based structural queries**:

**Example: Find functions with >3 parameters**
```python
results = await search_code(
    query="complex business logic",
    ast_pattern={
        "node_type": "function_definition",
        "param_count_gt": 3,
    }
)
```

**Example: Find classes without docstrings**
```python
results = await search_code(
    query="undocumented classes",
    ast_pattern={
        "node_type": "class_definition",
        "has_docstring": False,
    }
)
```

This requires extending `PatternMatcher` with `ASTPatternMatcher` (see Technical Design section 4).

## Risks & Mitigations

### Risk 1: Catastrophic Backtracking in Complex Patterns
**Risk:** User provides complex regex with nested quantifiers → 10+ second search
**Mitigation:**
- Implement pattern complexity analysis
- Set regex timeout (default: 100ms per match)
- Warn users about high-complexity patterns
- Provide pattern optimization suggestions

### Risk 2: Pattern Cache Memory Growth
**Risk:** Unbounded pattern cache → memory leak
**Mitigation:**
- Implement LRU cache with max size (default: 100 patterns)
- Monitor cache size in health checks
- Clear cache on server restart

### Risk 3: Low Pattern Match Rate
**Risk:** User provides very specific pattern → 0 results (poor UX)
**Mitigation:**
- Suggest relaxing pattern in error message
- Provide "did you mean" suggestions for presets
- Show total results before/after pattern filtering

### Risk 4: Performance Degradation with Large Result Sets
**Risk:** Filter mode retrieves 1000 results → 500ms+ latency
**Mitigation:**
- Implement early termination (stop when limit reached)
- Use parallel pattern matching for >100 results
- Cap retrieval_limit (max 500 results)

## Conclusion

FEAT-058 adds powerful **hybrid pattern detection** to the MCP RAG search capabilities, combining:
- **Regex pattern matching** for structural queries
- **Semantic search** for meaning-based queries
- **3 flexible modes** (filter, boost, require)
- **Pattern presets** for common use cases
- **Advanced scoring** for match quality

**Expected Impact:**
- ✅ Eliminates 60% of grep usage (users stay in MCP workflow)
- ✅ 10x faster QA reviews (30 min → 3 min)
- ✅ Better code smell detection (presets for common patterns)
- ✅ Enhanced security audits (find hardcoded secrets/keys)

**Total Effort:** ~1 week (5-7 days)
**Test Coverage:** 25-30 tests
**Performance:** <5ms overhead per search

This feature positions the MCP RAG server as a **comprehensive code intelligence platform**, not just a semantic search tool.
