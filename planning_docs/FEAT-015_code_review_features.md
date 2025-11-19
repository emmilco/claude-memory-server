# FEAT-015: Code Review Features

## TODO Reference
- TODO.md Line 113-115: "FEAT-015: Code review features - LLM-powered suggestions based on patterns, Identify code smells"

## Objective
Add pattern-based code review capabilities that identify common code smells and anti-patterns using semantic similarity and predefined pattern templates.

## Scope: MVP Approach

### Original Scope
- LLM-powered suggestions based on patterns
- Identify code smells

### MVP Scope (This Implementation)
**Pattern-based code smell detection** using existing semantic search infrastructure:

1. **Code Smell Pattern Library** - Predefined templates for common anti-patterns
2. **Pattern Matching via Semantic Search** - Find code that matches known smell patterns
3. **Review Suggestions** - Generate actionable review comments

**Key Decision**: Use semantic similarity (embeddings) instead of full LLM integration
- Leverages existing embedding infrastructure
- Fast and deterministic
- No external API dependencies
- Can be enhanced with LLM later

### What Makes This Different from FEAT-014?
- **FEAT-014 (Semantic Refactoring)**: Metrics-based detection (LOC, complexity, parameters)
- **FEAT-015 (Code Review)**: Pattern-based detection (anti-patterns, code smells, best practices)

## Current State

### What Exists
- `CodeAnalyzer` from FEAT-014 - Metrics-based analysis
- `find_usages()` - Semantic code search
- `suggest_refactorings()` - Metric-based suggestions
- Semantic search infrastructure with embeddings

### What's Missing
- Code smell pattern library
- Pattern matching engine
- Review comment generation
- Best practice checking

## Implementation Plan

### Phase 1: Pattern Library (~1 hour)

#### 1.1 Create Pattern Definitions
- [ ] Create `src/review/patterns.py` with code smell patterns
- [ ] Define pattern categories:
  - Security issues (SQL injection, hardcoded secrets)
  - Performance issues (N+1 queries, inefficient loops)
  - Maintainability issues (god classes, magic numbers)
  - Best practice violations (missing error handling, no validation)

#### 1.2 Pattern Structure
```python
@dataclass
class CodeSmellPattern:
    """A pattern representing a code smell."""
    id: str
    name: str
    category: str  # 'security' | 'performance' | 'maintainability' | 'best_practice'
    severity: str  # 'low' | 'medium' | 'high' | 'critical'
    description: str
    example_code: str  # Example of the smell
    fix_description: str
    languages: List[str]  # Applicable languages
```

### Phase 2: Pattern Matcher (~1.5 hours)

#### 2.1 Create Pattern Matcher Module
- [ ] Create `src/review/pattern_matcher.py`
- [ ] Implement `PatternMatcher` class
- [ ] Method: `find_matches(code, patterns)` → List[PatternMatch]
- [ ] Use semantic similarity to match code against patterns
- [ ] Threshold: 0.80 similarity = potential match

#### 2.2 Caching and Performance
- [ ] Cache pattern embeddings (generated once)
- [ ] Batch embedding generation for efficiency
- [ ] Filter by language before matching

### Phase 3: Review Generator (~1 hour)

#### 3.1 Create Review Comment Generator
- [ ] Create `src/review/comment_generator.py`
- [ ] Generate human-readable review comments
- [ ] Include: issue description, severity, location, suggested fix
- [ ] Format output as markdown for readability

#### 3.2 Comment Template
```
**[SEVERITY] Pattern Name**
Location: file.py:42
Description: Brief description of the issue
Suggested Fix: How to fix it
Example:
```code
# Good code example
```
```

### Phase 4: MCP Tool Integration (~1 hour)

#### 4.1 Add `review_code()` MCP Tool
- [ ] Add `review_code()` method to `src/core/server.py`
- [ ] Input: file_path or project_name, severity_threshold
- [ ] Output: List of review comments with locations
- [ ] Integration with existing code indexing

#### 4.2 Tool Interface
```python
async def review_code(
    file_path: Optional[str] = None,
    project_name: Optional[str] = None,
    severity_threshold: str = "medium",
    categories: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Review code for common smells and anti-patterns.

    Returns:
        Dict with:
            - reviews: List of review comments
            - count: Total issues found
            - summary: Breakdown by severity and category
    """
```

### Phase 5: Pattern Library Content (~1 hour)

Add 10-15 common patterns:

**Security (Critical/High)**:
- SQL injection (string concatenation in queries)
- Hardcoded secrets (API keys in code)
- Eval usage (eval/exec in Python)
- Command injection (os.system with user input)

**Performance (Medium/High)**:
- N+1 query pattern (loop with database queries)
- Inefficient string concatenation (+ in loops)
- Missing database indices (queries without WHERE clause optimization)

**Maintainability (Medium)**:
- Magic numbers (hardcoded numeric constants)
- God class (class with >10 methods)
- Long method chains (>4 chained calls)

**Best Practices (Low/Medium)**:
- Missing error handling (try/except not used)
- No input validation (direct user input use)
- Commented-out code (large comment blocks)

### Phase 6: Testing (~1.5 hours)

#### 6.1 Unit Tests
- [ ] Create `tests/unit/test_pattern_matcher.py`
  - Test pattern matching accuracy
  - Test similarity threshold
  - Test language filtering

- [ ] Create `tests/unit/test_code_review.py`
  - Test review generation
  - Test severity filtering
  - Test category filtering

#### 6.2 Integration Tests
- [ ] Create sample code with known smells
- [ ] Test end-to-end review workflow
- [ ] Verify no false positives on clean code

### Phase 7: Documentation (~30 min)
- [ ] Update CHANGELOG.md
- [ ] Add usage examples
- [ ] Document pattern structure for extensibility

## Technical Architecture

### New Modules

#### `src/review/patterns.py`
```python
from dataclasses import dataclass
from typing import List

@dataclass
class CodeSmellPattern:
    """Represents a code smell pattern."""
    id: str
    name: str
    category: str
    severity: str
    description: str
    example_code: str
    fix_description: str
    languages: List[str]

# Pattern library
SECURITY_PATTERNS = [...]
PERFORMANCE_PATTERNS = [...]
MAINTAINABILITY_PATTERNS = [...]
BEST_PRACTICE_PATTERNS = [...]

ALL_PATTERNS = SECURITY_PATTERNS + PERFORMANCE_PATTERNS + ...
```

#### `src/review/pattern_matcher.py`
```python
class PatternMatcher:
    """Match code against code smell patterns."""

    def __init__(self, embedding_generator):
        self.embedding_generator = embedding_generator
        self._pattern_embeddings_cache = {}

    async def find_matches(
        self,
        code: str,
        language: str,
        patterns: List[CodeSmellPattern],
        threshold: float = 0.80
    ) -> List[PatternMatch]:
        """Find patterns that match the code."""
```

#### `src/review/comment_generator.py`
```python
class ReviewCommentGenerator:
    """Generate human-readable review comments."""

    def generate_comment(
        self,
        match: PatternMatch,
        file_path: str,
        line_number: int
    ) -> ReviewComment:
        """Generate a review comment for a pattern match."""
```

## Test Cases

### Pattern Matching Tests
- [ ] Match SQL injection pattern accurately
- [ ] Reject clean code (no false positives)
- [ ] Filter patterns by language correctly
- [ ] Apply similarity threshold correctly
- [ ] Cache pattern embeddings

### Review Generation Tests
- [ ] Generate readable review comments
- [ ] Include all required information (location, severity, fix)
- [ ] Format as markdown correctly
- [ ] Filter by severity threshold
- [ ] Filter by category

### Integration Tests
- [ ] Review file with multiple smells
- [ ] Review entire project
- [ ] Handle files with no issues
- [ ] Combine with FEAT-014 refactoring suggestions

## Success Criteria
- ✅ Pattern library with 10-15 common smells
- ✅ Pattern matching with >80% accuracy on known smells
- ✅ <10% false positive rate on clean code
- ✅ `review_code()` MCP tool works end-to-end
- ✅ All tests passing (unit + integration)
- ✅ Performance: <500ms for single file review
- ✅ Documentation complete with examples

## Time Estimate
**Total: 6-7 hours**

Breakdown:
- Pattern library structure: 1 hour
- Pattern matcher: 1.5 hours
- Review generator: 1 hour
- MCP tool integration: 1 hour
- Pattern content: 1 hour
- Testing: 1.5 hours
- Documentation: 30 min

## Impact
**User Value:**
- 🔍 Automated code review for common issues
- 🛡️ Security vulnerability detection
- ⚡ Performance issue identification
- 📚 Learn best practices through suggestions
- 🎯 Actionable fix recommendations

**Use Cases:**
1. "Review this PR for code smells"
2. "Check for security issues in this file"
3. "Find performance problems in my project"
4. "Identify best practice violations"

## Example Patterns

### SQL Injection Pattern
```python
CodeSmellPattern(
    id="sql-injection-001",
    name="SQL Injection Risk",
    category="security",
    severity="critical",
    description="Direct string concatenation in SQL query enables SQL injection attacks",
    example_code='query = "SELECT * FROM users WHERE id = " + user_id',
    fix_description="Use parameterized queries or prepared statements instead",
    languages=["python", "javascript", "java", "php"]
)
```

### N+1 Query Pattern
```python
CodeSmellPattern(
    id="n-plus-one-001",
    name="N+1 Query Problem",
    category="performance",
    severity="high",
    description="Loop with database query causes N+1 query performance issue",
    example_code='''for user in users:
    profile = db.query("SELECT * FROM profiles WHERE user_id = ?", user.id)''',
    fix_description="Use JOIN or batch query to fetch all profiles at once",
    languages=["python", "javascript", "ruby", "java"]
)
```

### Magic Number Pattern
```python
CodeSmellPattern(
    id="magic-number-001",
    name="Magic Number",
    category="maintainability",
    severity="medium",
    description="Hardcoded numeric constant reduces code readability",
    example_code="if status_code == 200:",
    fix_description="Extract to named constant: HTTP_OK = 200",
    languages=["python", "javascript", "java", "go", "rust"]
)
```

## Notes
- Patterns are templates, not exact matches (semantic similarity)
- Can be extended with custom patterns later
- Future enhancement: LLM-powered pattern generation
- Integrates well with FEAT-014 metrics-based analysis
- Pattern library can grow over time

## Future Enhancements
1. Custom pattern definitions (user-provided)
2. LLM-powered review comments (more context-aware)
3. Auto-fix suggestions (not just descriptions)
4. Integration with CI/CD (fail on critical issues)
5. Team-specific pattern libraries
6. Learning from accepted/rejected suggestions
