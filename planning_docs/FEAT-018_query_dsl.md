# FEAT-018: Query DSL (Domain Specific Language)

## TODO Reference
- **ID:** FEAT-018
- **Location:** TODO.md, Tier 5: Advanced/Future Features
- **Description:** Query DSL with advanced filters (by file pattern, date, author, etc.) and complex query expressions

## Objective
Implement a query Domain Specific Language (DSL) to enable advanced filtering and complex search expressions beyond simple keyword queries. Allow users to combine semantic search with structured filters for precise code and memory retrieval.

## Current State
- The system currently supports:
  - Simple text queries for semantic search
  - Basic filters: project_name, language, file_pattern (glob), category, scope
  - Separate keyword search (BM25) and hybrid search modes
- No support for:
  - Complex boolean expressions (AND, OR, NOT)
  - Date range filters (created_at, modified_at)
  - Author filters (for git-indexed code)
  - Combined semantic + structured filtering in one query
  - Query composition and nesting

## User Impact
- **Value:** Power users can construct precise queries combining semantic and structured filters
- **Use cases:**
  - "Find authentication code modified after 2024-01-01 by author:john"
  - "Search for error handling NOT in test files"
  - "Find API endpoints in (Python OR TypeScript) files"
- **Benefits:**
  - Reduced false positives
  - More precise results
  - Faster workflows for power users

## Implementation Plan

### Phase 1: DSL Design (1 hour)
**Decision:** DSL Syntax Options

**Option A - Natural Language Style:**
```
"error handling" in:python author:john after:2024-01-01 NOT test
```

**Option B - Structured Query Style:**
```json
{
  "query": "error handling",
  "filters": {
    "language": "python",
    "author": "john",
    "after": "2024-01-01",
    "exclude": "test"
  }
}
```

**Option C - GitHub-style DSL:** (RECOMMENDED)
```
error handling language:python author:john created:>2024-01-01 -file:test
```

**Chosen:** Option C (GitHub-style) - familiar, expressive, easy to parse

### Phase 2: DSL Parser (3-4 hours)
**File:** `src/search/query_dsl_parser.py`

```python
class QueryDSL:
    """Parse and execute query DSL expressions."""

    def parse(self, query_string: str) -> ParsedQuery:
        """
        Parse DSL query string into structured query.

        Supports:
        - language:python, lang:py
        - author:username
        - file:pattern, path:pattern
        - created:>2024-01-01, modified:<2024-12-31
        - project:name
        - category:fact
        - scope:global
        - -file:test (exclusion)
        - AND, OR, NOT operators
        """
        pass

    def execute(self, parsed_query: ParsedQuery) -> List[SearchResult]:
        """Execute parsed query against the store."""
        pass
```

**Parser Components:**
1. **Tokenizer** - Split query into tokens (terms, filters, operators)
2. **Filter Extractor** - Extract key:value pairs
3. **Boolean Parser** - Handle AND, OR, NOT, parentheses
4. **Semantic Extractor** - Identify free-text search terms
5. **Validator** - Check filter values are valid

### Phase 3: Filter Implementation (2-3 hours)
**Files:** `src/search/query_dsl_parser.py`, `src/core/server.py`

**Filters to Implement:**
1. `language:` - Language filter (existing, needs integration)
2. `file:` / `path:` - File path pattern (glob)
3. `author:` - Git author filter (requires git metadata)
4. `created:` - Creation date filter (`>`, `<`, `>=`, `<=`, `=`)
5. `modified:` - Modified date filter
6. `project:` - Project name filter (existing)
7. `category:` - Memory category filter (existing)
8. `scope:` - Memory scope filter (existing)
9. `-filter:value` - Exclusion (NOT filter)

**Date Filter Syntax:**
- `created:>2024-01-01` - After date
- `created:<2024-12-31` - Before date
- `created:2024-01-01..2024-12-31` - Range

**Boolean Operators:**
- Implicit AND between terms: `python authentication` = `python AND authentication`
- Explicit `OR`: `python OR typescript`
- Explicit `NOT`: `NOT test`
- Parentheses: `(python OR typescript) AND authentication`

### Phase 4: Integration with Search (2 hours)
**Files:** `src/core/server.py`, `src/mcp_server.py`

1. Update `search_code()` to accept DSL queries
2. Add `search_dsl()` MCP tool for advanced queries
3. Maintain backward compatibility with simple queries
4. Integrate with hybrid search

### Phase 5: MCP Tools (1 hour)
**Files:** `src/core/server.py`, `src/mcp_server.py`, `src/core/models.py`

Add new MCP tool:
- `search_dsl(query: str, limit: int = 10)` - Execute DSL query

Models:
- `SearchDSLRequest` - Request with DSL query string
- `SearchDSLResponse` - Standard search response

### Phase 6: Testing (3 hours)
**File:** `tests/unit/test_query_dsl.py`

Test coverage:
1. **Parser Tests (10 tests)**
   - Parse simple filters
   - Parse date ranges
   - Parse boolean expressions
   - Parse exclusions
   - Handle invalid syntax

2. **Filter Tests (15 tests)**
   - Language filter
   - File pattern filter
   - Author filter
   - Date range filter
   - Exclusion filter
   - Combined filters

3. **Integration Tests (10 tests)**
   - End-to-end DSL queries
   - Backward compatibility
   - Error handling
   - Edge cases

**Expected:** 35 tests, aiming for 90%+ coverage

### Phase 7: Documentation (30 min)
**Files to update:**
- `docs/API.md` - Document `search_dsl` tool with syntax examples
- `docs/USAGE.md` - User guide for DSL queries
- `CHANGELOG.md` - Add FEAT-018 entry
- `README.md` - Mention Query DSL feature

## Technical Design

### DSL Syntax Specification

**Basic Syntax:**
```
<semantic_terms> [filter:value]* [operator]*
```

**Examples:**
```
# Simple semantic search
error handling

# With language filter
error handling language:python

# With file pattern
authentication file:src/**/*.py

# With date range
login created:>2024-01-01

# With exclusion
testing -file:test

# Complex boolean
(python OR typescript) authentication NOT deprecated

# Combined filters
error handling language:python author:john created:>2024-01-01 -file:test

# Project-scoped
API design project:web-app language:typescript
```

**Filter Reference:**
| Filter | Syntax | Example | Description |
|--------|--------|---------|-------------|
| `language:` | `language:python` | `language:python` | Filter by programming language |
| `file:` | `file:pattern` | `file:src/**/*.py` | Filter by file path (glob) |
| `path:` | `path:pattern` | `path:*/auth/*` | Alias for file: |
| `author:` | `author:name` | `author:john` | Filter by git author |
| `created:` | `created:op date` | `created:>2024-01-01` | Filter by creation date |
| `modified:` | `modified:op date` | `modified:<2024-12-31` | Filter by modified date |
| `project:` | `project:name` | `project:web-app` | Filter by project name |
| `category:` | `category:type` | `category:fact` | Filter memory by category |
| `scope:` | `scope:type` | `scope:global` | Filter memory by scope |
| `-filter:` | `-file:pattern` | `-file:test` | Exclude matches |

**Date Operators:**
- `>` - After (exclusive)
- `>=` - After or on (inclusive)
- `<` - Before (exclusive)
- `<=` - Before or on (inclusive)
- `=` - Exact date
- `..` - Range (inclusive)

**Boolean Operators:**
- `AND` - Explicit AND (implicit between adjacent terms)
- `OR` - Logical OR
- `NOT` - Logical NOT (also `-` prefix)
- `( )` - Grouping

### Parser Algorithm

```python
def parse(query_string: str) -> ParsedQuery:
    # 1. Tokenize
    tokens = tokenize(query_string)

    # 2. Extract filters
    filters, semantic_tokens = extract_filters(tokens)

    # 3. Parse boolean expression from semantic tokens
    boolean_expr = parse_boolean(semantic_tokens)

    # 4. Build ParsedQuery
    return ParsedQuery(
        semantic_query=boolean_expr,
        filters=filters
    )
```

### ParsedQuery Structure

```python
@dataclass
class ParsedQuery:
    semantic_terms: List[str]  # Free-text search terms
    filters: Dict[str, Any]    # Structured filters
    boolean_expr: BooleanExpr  # Boolean expression tree
    exclusions: List[str]      # Exclusion patterns
```

## Implementation Checklist

- [ ] Create `src/search/query_dsl_parser.py`
- [ ] Implement tokenizer
- [ ] Implement filter extractor
- [ ] Implement boolean parser
- [ ] Implement date parser
- [ ] Add language filter support
- [ ] Add file pattern filter support
- [ ] Add author filter support (requires git metadata)
- [ ] Add date range filter support
- [ ] Add exclusion support
- [ ] Integrate with `search_code()` in server.py
- [ ] Add `search_dsl()` MCP tool
- [ ] Add request/response models
- [ ] Register tool in mcp_server.py
- [ ] Create comprehensive test suite (35 tests)
- [ ] Update `docs/API.md`
- [ ] Update `docs/USAGE.md`
- [ ] Update `CHANGELOG.md`
- [ ] Run full test suite
- [ ] Commit following project protocol

## Success Criteria

1. ✅ DSL parser handles all filter types
2. ✅ Boolean operators (AND, OR, NOT) work correctly
3. ✅ Date range filters work as expected
4. ✅ Exclusion filters (-file:) work correctly
5. ✅ 35 tests, all passing, 90%+ coverage
6. ✅ Documentation updated in API.md and USAGE.md
7. ✅ Backward compatible with simple queries
8. ✅ Full test suite passes (maintain 99%+ pass rate)

## Progress Tracking

**Status:** In Progress
**Started:** 2025-11-18

### Completed
- [ ] Planning document created

### In Progress
- [ ] DSL design

### Blocked
- None

## Notes & Decisions

- **DSL Style:** GitHub-style syntax chosen for familiarity
- **Backward Compatibility:** Simple queries still work (no DSL required)
- **Author Filter:** Requires git metadata - may need to index commit info
- **Date Filters:** Use ISO 8601 format (YYYY-MM-DD)
- **Performance:** DSL parsing adds <1ms overhead per query

## Complexity Assessment

This is a **Complex** feature requiring:
- Parser implementation (moderately complex)
- Multiple filter types (straightforward but time-consuming)
- Boolean logic (moderately complex)
- Integration with existing search (straightforward)
- Comprehensive testing (time-consuming)

**Estimated Implementation Time:** 10-12 hours
**Risk Level:** Medium (parsing complexity, backward compatibility)

## Completion Summary
(To be filled in when complete)
