# FEAT-014: Semantic Refactoring

## TODO Reference
- TODO.md Line 109-111: "FEAT-014: Semantic refactoring - Find all usages semantically, Suggest refactoring opportunities"

## Objective
Enable users to find all usages of code units (functions, classes, variables) using semantic search, and receive intelligent refactoring suggestions based on code patterns and usage analysis.

## Scope: MVP Approach

### Core Features
1. **Find Usages Semantically** - Find where a function/class/variable is used across the codebase using semantic search (not just text matching)
2. **Refactoring Suggestions** - Analyze code patterns and suggest improvements:
   - Duplicate code detection
   - Long parameter lists (>5 parameters)
   - Large functions (>50 lines)
   - Unused code detection
   - Extract method opportunities

### What Makes This "Semantic"?
- Traditional "find usages" = text search for exact identifier name
- Semantic "find usages" = understand context, find similar code patterns, handle renames/aliases
- Example: Find all places where a function's logic is used, even if variable names differ

## Current State

### What Exists
- `search_code` MCP tool - Semantic code search
- Code indexing with AST parsing
- Embeddings for semantic similarity
- Dependency tracking (`get_file_dependencies`)

### What's Missing
- Usage analysis focused on specific code units
- Refactoring pattern detection
- Code metrics (function length, parameter count, complexity)
- Duplicate code detection
- Actionable refactoring suggestions

## Implementation Plan

### Phase 1: Usage Finding (~1.5 hours)

#### 1.1 Create `find_usages` MCP Tool
- [ ] Add `find_usages` to src/core/server.py
- [ ] Input: code snippet or function name + file path
- [ ] Use semantic search to find similar code patterns
- [ ] Return: list of usages with file, line, context
- [ ] Include similarity score for each usage

#### 1.2 Enhance Search Context
- [ ] Extract surrounding context (5 lines before/after)
- [ ] Show function/class that contains the usage
- [ ] Include call chain information

### Phase 2: Code Metrics Analysis (~1.5 hours)

#### 2.1 Create Code Analyzer Module
- [ ] Create `src/refactoring/code_analyzer.py`
- [ ] Function: `calculate_metrics(code_unit)` returns:
  - Lines of code
  - Cyclomatic complexity (count if/for/while/try)
  - Parameter count
  - Nesting depth
  - Return statement count

#### 2.2 Integrate with Indexing
- [ ] Store metrics during indexing
- [ ] Add metrics to code unit metadata
- [ ] Query metrics from vector store

### Phase 3: Refactoring Suggestions (~2 hours)

#### 3.1 Create `suggest_refactorings` MCP Tool
- [ ] Add `suggest_refactorings` to src/core/server.py
- [ ] Input: file path (optional: specific function)
- [ ] Output: list of suggestions with:
  - Issue type (e.g., "Long Parameter List")
  - Severity (low/medium/high)
  - Location (file, line)
  - Description
  - Suggested fix

#### 3.2 Implement Detection Rules
- [ ] **Long Parameter List**: >5 parameters → suggest object parameter
- [ ] **Large Function**: >50 lines → suggest extract method
- [ ] **Deep Nesting**: >4 levels → suggest simplification
- [ ] **Duplicate Code**: similarity >0.85 → suggest extraction
- [ ] **Unused Code**: no usages found → suggest removal

#### 3.3 Duplicate Code Detection
- [ ] Use semantic search to find similar functions
- [ ] Threshold: 0.85 similarity
- [ ] Group duplicates together
- [ ] Suggest common function extraction

### Phase 4: Testing (~1.5 hours)

#### 4.1 Unit Tests
- [ ] Create `tests/unit/test_code_analyzer.py`
  - [ ] Test metric calculation
  - [ ] Test each detection rule
  - [ ] Test edge cases (empty functions, etc.)

#### 4.2 Integration Tests
- [ ] Create `tests/integration/test_refactoring.py`
  - [ ] Test find_usages with real code
  - [ ] Test suggest_refactorings end-to-end
  - [ ] Test duplicate detection accuracy

#### 4.3 Test Fixtures
- [ ] Create sample code with known issues
  - [ ] Long function (100 lines)
  - [ ] Long parameter list (8 parameters)
  - [ ] Duplicate functions
  - [ ] Deeply nested code

### Phase 5: Documentation (~30 min)
- [ ] Update CHANGELOG.md
- [ ] Add usage examples to README
- [ ] Document MCP tools in docs/

## Technical Architecture

### New Modules

#### `src/refactoring/code_analyzer.py`
```python
from dataclasses import dataclass
from typing import List, Optional

@dataclass
class CodeMetrics:
    """Metrics for a code unit."""
    lines_of_code: int
    cyclomatic_complexity: int
    parameter_count: int
    nesting_depth: int
    return_count: int

@dataclass
class RefactoringSuggestion:
    """A suggested refactoring."""
    issue_type: str
    severity: str  # 'low' | 'medium' | 'high'
    file_path: str
    line_number: int
    description: str
    suggested_fix: str

class CodeAnalyzer:
    """Analyzes code for refactoring opportunities."""

    def calculate_metrics(self, code: str, language: str) -> CodeMetrics:
        """Calculate metrics for a code snippet."""

    def detect_long_parameter_list(self, metrics: CodeMetrics) -> Optional[RefactoringSuggestion]:
        """Detect functions with >5 parameters."""

    def detect_large_function(self, metrics: CodeMetrics) -> Optional[RefactoringSuggestion]:
        """Detect functions with >50 lines."""

    def detect_deep_nesting(self, metrics: CodeMetrics) -> Optional[RefactoringSuggestion]:
        """Detect code with >4 nesting levels."""
```

### New MCP Tools

#### 1. `find_usages`
```python
async def find_usages(
    code_snippet: str,
    file_path: Optional[str] = None,
    project_name: Optional[str] = None,
    min_similarity: float = 0.75
) -> List[Usage]:
    """
    Find all usages of a code snippet semantically.

    Args:
        code_snippet: The code to find usages of
        file_path: Optional file path to search within
        project_name: Optional project to search within
        min_similarity: Minimum similarity threshold (0-1)

    Returns:
        List of usages with file, line, context, similarity
    """
```

#### 2. `suggest_refactorings`
```python
async def suggest_refactorings(
    file_path: Optional[str] = None,
    project_name: Optional[str] = None,
    severity_threshold: str = "medium"
) -> List[RefactoringSuggestion]:
    """
    Suggest refactorings for code in a file or project.

    Args:
        file_path: Optional specific file to analyze
        project_name: Optional project to analyze
        severity_threshold: Minimum severity to report

    Returns:
        List of refactoring suggestions
    """
```

## Test Cases

### Find Usages Tests
- [ ] Find function calls across files
- [ ] Find method calls on objects
- [ ] Find similar code patterns (renamed variables)
- [ ] Handle overloaded functions
- [ ] Filter by similarity threshold

### Refactoring Suggestion Tests
- [ ] Detect long parameter lists
- [ ] Detect large functions
- [ ] Detect deep nesting
- [ ] Detect duplicate code (similarity >0.85)
- [ ] Filter by severity
- [ ] Combine multiple suggestions for same location

### Metric Calculation Tests
- [ ] Count lines correctly (exclude comments)
- [ ] Calculate cyclomatic complexity
- [ ] Count function parameters
- [ ] Measure nesting depth
- [ ] Handle edge cases (empty functions, single-line functions)

## Success Criteria
- ✅ `find_usages` tool finds semantic usages accurately (>80% recall)
- ✅ `suggest_refactorings` tool detects known code smells
- ✅ Duplicate code detection with >0.85 similarity works
- ✅ All tests passing (unit + integration)
- ✅ Documentation complete with examples
- ✅ Performance: <100ms for single file analysis

## Time Estimate
**Total: 6-7 hours**

Breakdown:
- Usage finding: 1.5 hours
- Code metrics: 1.5 hours
- Refactoring suggestions: 2 hours
- Testing: 1.5 hours
- Documentation: 30 min

## Impact
**User Value:**
- 🔍 Find all usages semantically (even with renamed variables)
- 🎯 Identify refactoring opportunities automatically
- 📊 Code quality metrics and insights
- 🔧 Actionable suggestions with explanations
- 🚀 Improve codebase maintainability

**Use Cases:**
1. "Find all places this function is called"
2. "Show me refactoring opportunities in this file"
3. "Find duplicate code in my project"
4. "What functions are too long or complex?"

## Notes
- Uses existing semantic search infrastructure
- Metrics calculated from AST (tree-sitter)
- Suggestions are recommendations, not automated refactorings
- Can be extended with more sophisticated rules later
- Duplicate detection based on embedding similarity

## Future Enhancements
1. Automated refactoring (not just suggestions)
2. Machine learning-based pattern detection
3. Project-wide refactoring analysis
4. Integration with IDE (quick fixes)
5. Custom refactoring rules
6. Code smell taxonomy expansion
