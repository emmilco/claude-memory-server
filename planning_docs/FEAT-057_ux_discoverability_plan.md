# FEAT-057: Better UX & Discoverability for MCP RAG

## TODO Reference
- TODO.md line 262-274: "FEAT-057: Better UX & Discoverability (~1 week)"
- **Current Gap:** No query suggestions, result summaries, or interactive refinement
- **Problem:** Users don't know what queries work well, results lack context, no guidance
- **Impact:** Reduced learning curve, better discoverability
- **Tests:** 10-15 tests

## Objective

Transform the MCP RAG search experience from "black box" to guided discovery by implementing:
1. Query suggestion system to help users craft effective queries
2. Faceted search results showing data distribution across dimensions
3. Result summaries providing high-level context
4. "Did you mean?" suggestions for typos and synonyms
5. Interactive refinement hints guiding users to better results

**Success Criteria:**
- 50% reduction in "no results" queries through better suggestions
- 70% of users try refinement hints when shown
- Query success rate improves from ~60% to 85%+
- Average time-to-answer reduces by 30% through guided discovery

## Current UX Analysis

### Pain Points Identified

1. **Query Formulation Paralysis**
   - Users stare at search box not knowing what to type
   - No examples of effective queries visible
   - Unclear what's indexed or searchable
   - No differentiation between semantic vs keyword queries

2. **Result Context Deficit**
   - Results appear without summary or distribution
   - No sense of "15 results across 8 files in 3 projects"
   - Can't tell if results span many areas or focused on one
   - Missing facets: language breakdown, file type distribution

3. **Dead-End Searches**
   - Empty results with generic "try different terms" message
   - No suggestions for what worked for others
   - Typos cause total failure instead of correction
   - Similar queries not surfaced

4. **No Guidance for Refinement**
   - Results might be too broad or too narrow
   - No hints about using filters (file_pattern, language)
   - Can't tell if switching search modes would help
   - Missing progressive disclosure of advanced features

### User Confusion Areas

**From empirical evaluation (EVAL-001) and QA reviews:**
- "What kinds of queries does this understand?" - No query templates shown
- "Did it find anything or is indexing broken?" - Zero feedback on index health
- "Are these the best results or just first 5?" - No quality indicators beyond score
- "Should I use semantic or hybrid mode?" - No mode recommendations
- "How do I narrow this down?" - No refinement pathways suggested

## Technical Design

### 1. Query Suggestion System

#### Component: QuerySuggester
**Location:** `src/memory/query_suggester.py`

**Purpose:** Generate contextual query suggestions based on codebase content and user intent

**Data Sources:**
- Indexed code statistics (most common languages, file types, unit names)
- Popular patterns from conversation tracker
- Domain-specific templates (auth, database, API, error handling)
- Project-specific suggestions (extract from actual indexed content)

**API Design:**
```python
class QuerySuggester:
    """Generate contextual query suggestions for better discoverability."""

    def __init__(
        self,
        store: MemoryStore,
        config: ServerConfig,
    ):
        self.store = store
        self.config = config
        self.suggestion_cache: Dict[str, List[str]] = {}
        self.cache_ttl = 3600  # 1 hour

    async def suggest_queries(
        self,
        intent: Optional[str] = None,
        project_name: Optional[str] = None,
        context: Optional[str] = None,
        max_suggestions: int = 8,
    ) -> SuggestQueryResponse:
        """
        Generate query suggestions.

        Args:
            intent: User intent (implementation, debugging, learning, exploration, refactoring)
            project_name: Optional project to scope suggestions
            context: Optional context from conversation
            max_suggestions: Maximum suggestions to return

        Returns:
            SuggestQueryResponse with categorized suggestions
        """
```

**Suggestion Categories:**

1. **Intent-Based Templates** (if intent provided)
   - Implementation: "user authentication logic", "database connection handling"
   - Debugging: "error handling in API", "exception logging"
   - Learning: "how does pagination work", "authentication flow"
   - Exploration: "all REST endpoints", "database models"
   - Refactoring: "duplicate error handlers", "similar validation functions"

2. **Project-Specific** (from indexed content)
   - Extract top 10 most common function/class names
   - "Find code calling {popular_function}"
   - "Show implementations of {common_class}"
   - "Where is {frequent_term} used"

3. **Domain-Specific Presets**
   - Authentication: "JWT token validation", "password hashing", "session management"
   - Database: "SQL query construction", "ORM models", "database migrations"
   - API: "request validation", "response formatting", "middleware"
   - Error Handling: "exception handlers", "error logging", "retry logic"

4. **General Discovery**
   - "Most complex functions"
   - "Recent changes"
   - "Frequently modified files"
   - "Entry points and main functions"

**Response Format:**
```python
@dataclass
class QuerySuggestion:
    query: str
    category: str  # template, project, domain, general
    description: str
    expected_results: Optional[int]  # Estimated result count

@dataclass
class SuggestQueryResponse:
    suggestions: List[QuerySuggestion]
    indexed_stats: Dict[str, Any]  # language counts, file counts
    project_name: Optional[str]
    total_suggestions: int
```

#### MCP Tool: suggest_queries

```json
{
  "name": "suggest_queries",
  "description": "Get contextual query suggestions based on indexed codebase and user intent",
  "inputSchema": {
    "type": "object",
    "properties": {
      "intent": {
        "type": "string",
        "enum": ["implementation", "debugging", "learning", "exploration", "refactoring"],
        "description": "User's current intent or task"
      },
      "project_name": {
        "type": "string",
        "description": "Project to scope suggestions to"
      },
      "context": {
        "type": "string",
        "description": "Additional context from conversation"
      },
      "max_suggestions": {
        "type": "integer",
        "default": 8,
        "description": "Maximum suggestions to return"
      }
    }
  }
}
```

**Example Output:**
```json
{
  "suggestions": [
    {
      "query": "JWT token validation logic",
      "category": "domain",
      "description": "Find authentication token validation code",
      "expected_results": 3
    },
    {
      "query": "UserRepository save method",
      "category": "project",
      "description": "Based on commonly used class in your project",
      "expected_results": 1
    },
    {
      "query": "error handling in API endpoints",
      "category": "template",
      "description": "Common debugging pattern",
      "expected_results": 12
    }
  ],
  "indexed_stats": {
    "total_files": 245,
    "total_units": 1834,
    "languages": {"python": 180, "typescript": 65},
    "top_classes": ["UserRepository", "AuthService", "APIClient"]
  },
  "project_name": "my-app",
  "total_suggestions": 8
}
```

### 2. Faceted Search Results

#### Enhancement to Existing search_code

**Add facets to search response:**

```python
@dataclass
class SearchFacets:
    """Faceted breakdown of search results."""
    languages: Dict[str, int]  # {"python": 8, "typescript": 2}
    unit_types: Dict[str, int]  # {"function": 7, "class": 3}
    files: Dict[str, int]  # {"auth.py": 4, "user.py": 3}
    projects: Dict[str, int]  # Only for cross-project search
    complexity_distribution: Dict[str, int]  # {"simple": 5, "moderate": 3, "complex": 2}
```

**Modified search_code return:**
```python
{
    "status": "success",
    "results": [...],
    "total_found": 15,
    "facets": {
        "languages": {"python": 12, "typescript": 3},
        "unit_types": {"function": 10, "class": 5},
        "files": {
            "/path/to/auth.py": 5,
            "/path/to/user.py": 4,
            "/path/to/api.py": 3,
            "...": 3  # Aggregated if >5 files
        },
        "directories": {
            "/src/auth": 9,
            "/src/api": 6
        }
    },
    "summary": "Found 15 functions across 8 files in Python and TypeScript",
    # ... existing fields
}
```

**Implementation:**
```python
def _build_facets(self, results: List[Dict]) -> SearchFacets:
    """Build faceted breakdown from results."""
    languages = Counter()
    unit_types = Counter()
    files = Counter()
    directories = Counter()

    for result in results:
        languages[result['language']] += 1
        unit_types[result['unit_type']] += 1
        files[result['file_path']] += 1

        # Extract directory
        dir_path = os.path.dirname(result['file_path'])
        directories[dir_path] += 1

    return SearchFacets(
        languages=dict(languages.most_common()),
        unit_types=dict(unit_types.most_common()),
        files=dict(files.most_common(5)),  # Top 5 files
        directories=dict(directories.most_common(5)),
        complexity_distribution=self._analyze_complexity(results)
    )
```

### 3. Result Summaries

#### Component: ResultSummarizer
**Location:** `src/memory/result_summarizer.py`

**Purpose:** Generate human-readable summaries of search results

**Templates:**

```python
class ResultSummarizer:
    """Generate readable summaries of search results."""

    @staticmethod
    def summarize(
        results: List[Dict],
        facets: SearchFacets,
        query: str,
    ) -> str:
        """Generate natural language summary."""

        count = len(results)
        if count == 0:
            return "No results found"

        # File distribution
        file_count = len(facets.files)
        file_summary = f"{file_count} file" + ("s" if file_count > 1 else "")

        # Language distribution
        if len(facets.languages) == 1:
            lang = list(facets.languages.keys())[0]
            lang_summary = f"in {lang.title()}"
        else:
            langs = " and ".join(list(facets.languages.keys())[:2])
            lang_summary = f"across {langs}"

        # Unit type distribution
        unit_summary = ResultSummarizer._format_unit_types(facets.unit_types)

        # Compose summary
        summary = f"Found {count} {unit_summary} across {file_summary} {lang_summary}"

        # Add project if multi-project
        if len(facets.projects) > 1:
            summary += f" in {len(facets.projects)} projects"

        return summary

    @staticmethod
    def _format_unit_types(types: Dict[str, int]) -> str:
        """Format unit types naturally."""
        if len(types) == 1:
            unit_type, count = list(types.items())[0]
            plural = "s" if count > 1 else ""
            return f"{unit_type}{plural}"

        # Mixed types
        type_list = [f"{count} {t}{'s' if count > 1 else ''}"
                     for t, count in list(types.items())[:2]]
        return " and ".join(type_list)
```

**Example Summaries:**
- "Found 15 functions across 8 files in Python"
- "Found 3 classes and 7 functions across 5 files in Python and TypeScript"
- "Found 23 functions across 12 files in Python in 2 projects"
- "No results found - try broadening your query or checking project is indexed"

### 4. "Did You Mean?" Suggestions

#### Component: SpellingSuggester
**Location:** `src/memory/spelling_suggester.py`

**Purpose:** Detect typos and suggest corrections using:
1. Levenshtein distance for close matches
2. Synonym lookup from existing query_synonyms.py
3. Common programming term corrections

**Algorithm:**
```python
class SpellingSuggester:
    """Suggest corrections for misspelled queries."""

    def __init__(self, store: MemoryStore):
        self.store = store
        self.indexed_terms: Set[str] = set()
        self.load_indexed_terms()

    async def load_indexed_terms(self):
        """Extract all function/class names from indexed code."""
        # Get unique unit names from CODE category memories
        # Build searchable term index
        pass

    def suggest_corrections(
        self,
        query: str,
        max_distance: int = 2,
        max_suggestions: int = 3
    ) -> List[str]:
        """
        Generate spelling corrections.

        Args:
            query: Original query
            max_distance: Maximum edit distance
            max_suggestions: Maximum corrections to return

        Returns:
            List of suggested corrections
        """
        suggestions = []
        query_terms = query.lower().split()

        for term in query_terms:
            # Check synonyms first
            if term in PROGRAMMING_SYNONYMS:
                # Offer synonym if not in original query
                for synonym in PROGRAMMING_SYNONYMS[term]:
                    if synonym not in query_terms:
                        suggestions.append(
                            query.replace(term, synonym)
                        )

            # Check indexed terms
            close_matches = self._find_close_matches(
                term,
                self.indexed_terms,
                max_distance
            )

            for match in close_matches[:max_suggestions]:
                corrected_query = query.replace(term, match)
                if corrected_query not in suggestions:
                    suggestions.append(corrected_query)

        return suggestions[:max_suggestions]

    @staticmethod
    def _find_close_matches(
        term: str,
        candidates: Set[str],
        max_distance: int
    ) -> List[str]:
        """Find terms within edit distance using Levenshtein."""
        import difflib
        # Use difflib.get_close_matches for simplicity
        # Or implement custom Levenshtein for more control
        return difflib.get_close_matches(
            term,
            candidates,
            n=5,
            cutoff=0.6
        )
```

**Integration with search_code:**
```python
# In search_code method, when results are empty or low quality:
if len(code_results) == 0 or quality_info["quality"] == "poor":
    spelling_suggester = SpellingSuggester(self.store)
    corrections = spelling_suggester.suggest_corrections(query)

    if corrections:
        return {
            # ... existing fields
            "did_you_mean": corrections,
            "suggestions": [
                f"Did you mean '{correction}'?"
                for correction in corrections
            ] + existing_suggestions
        }
```

### 5. Interactive Refinement Hints

#### Component: RefinementAdvisor
**Location:** `src/memory/refinement_advisor.py`

**Purpose:** Analyze search results and suggest refinements

**Refinement Strategies:**

```python
class RefinementAdvisor:
    """Suggest ways to refine search results."""

    @staticmethod
    def analyze_and_suggest(
        results: List[Dict],
        facets: SearchFacets,
        query: str,
        filters: Dict[str, Any],
    ) -> List[str]:
        """Generate refinement suggestions based on result characteristics."""

        hints = []

        # Too many results → suggest narrowing
        if len(results) >= 50:
            hints.append(
                "💡 Too many results. Try adding file_pattern to narrow down "
                "(e.g., file_pattern='*/auth/*')"
            )

            # Suggest specific language filter if multi-language
            if len(facets.languages) > 1:
                main_lang = max(facets.languages.items(), key=lambda x: x[1])[0]
                hints.append(
                    f"💡 Filter by language: language='{main_lang}' "
                    f"to focus on {facets.languages[main_lang]} results"
                )

        # Too few results → suggest broadening
        elif len(results) < 3:
            hints.append(
                "💡 Few results found. Try broadening your query or "
                "removing filters"
            )

            # Suggest hybrid search if using semantic
            if filters.get("search_mode") == "semantic":
                hints.append(
                    "💡 Try hybrid search mode for better recall: "
                    "search_mode='hybrid'"
                )

        # Results span many files → suggest focusing
        if len(facets.files) > 10:
            top_file = max(facets.files.items(), key=lambda x: x[1])[0]
            top_dir = os.path.dirname(top_file)
            hints.append(
                f"💡 Results are scattered. Try file_pattern='{top_dir}/*' "
                f"to focus on the main directory"
            )

        # Mixed unit types → suggest filtering
        if len(facets.unit_types) > 1:
            if facets.unit_types.get("function", 0) > facets.unit_types.get("class", 0):
                hints.append(
                    "💡 Add 'function' to your query to focus on functions only"
                )

        # Query lacks context → suggest more specific terms
        if len(query.split()) < 3:
            hints.append(
                "💡 Try adding more context to your query "
                "(e.g., 'user authentication' → 'JWT user authentication logic')"
            )

        # Keyword search might be better for specific names
        if any(term.startswith('_') or term[0].isupper() for term in query.split()):
            hints.append(
                "💡 Searching for specific names? Try search_mode='keyword' "
                "for exact matching"
            )

        return hints[:3]  # Max 3 hints to avoid overwhelming
```

**Integration:**
```python
# In search_code return
refinement_hints = RefinementAdvisor.analyze_and_suggest(
    code_results,
    facets,
    query,
    {"search_mode": search_mode}
)

return {
    # ... existing fields
    "refinement_hints": refinement_hints,
}
```

## Implementation Phases

### Phase 1: Foundation (Days 1-2)
**Focus:** Core components and data structures

- [ ] Create `src/memory/query_suggester.py`
- [ ] Create `src/memory/result_summarizer.py`
- [ ] Create `src/memory/spelling_suggester.py`
- [ ] Create `src/memory/refinement_advisor.py`
- [ ] Define data models (QuerySuggestion, SearchFacets, etc.)
- [ ] Implement query template system
- [ ] Write unit tests for each component (4 tests per component = 16 tests)

**Deliverables:**
- 4 new Python modules
- 4 new data models
- 16 unit tests
- Template system with 20+ query templates

### Phase 2: Query Suggestions (Day 3)
**Focus:** suggest_queries MCP tool

- [ ] Implement project-specific suggestion extraction
- [ ] Implement domain-specific preset suggestions
- [ ] Implement intent-based template selection
- [ ] Add `suggest_queries()` MCP tool to server.py
- [ ] Write integration tests (5 tests)
- [ ] Test with real codebases

**Deliverables:**
- Working suggest_queries MCP tool
- 5 integration tests
- Documentation in tool description

### Phase 3: Enhanced Search Results (Days 4-5)
**Focus:** Facets, summaries, and refinement hints

- [ ] Implement facet building in search_code
- [ ] Implement result summarization
- [ ] Implement refinement hint generation
- [ ] Integrate SpellingSuggester with search_code
- [ ] Update search_code return format
- [ ] Write integration tests (6 tests)
- [ ] Update existing tests for new format

**Deliverables:**
- Enhanced search_code with facets, summary, hints
- "Did you mean?" suggestions on low-quality results
- 6 integration tests
- Updated response model

### Phase 4: Polish & Testing (Days 6-7)
**Focus:** Edge cases, performance, documentation

- [ ] Performance testing (facet building on 1000+ results)
- [ ] Edge case testing (empty results, single result, etc.)
- [ ] Update CHANGELOG.md
- [ ] Update API documentation
- [ ] User testing and feedback collection
- [ ] Bug fixes and refinements

**Deliverables:**
- Performance benchmarks (facets <5ms on 1000 results)
- Comprehensive test coverage (15+ tests total)
- Updated documentation
- Production-ready code

## Code Examples

### Example 1: Using suggest_queries

```python
# User opens search interface
response = await server.suggest_queries(
    intent="debugging",
    project_name="my-app"
)

# Returns:
{
    "suggestions": [
        {
            "query": "exception handling in API endpoints",
            "category": "template",
            "description": "Common debugging pattern",
            "expected_results": 8
        },
        {
            "query": "UserService.authenticate error handling",
            "category": "project",
            "description": "Based on your indexed code",
            "expected_results": 2
        },
        # ... more suggestions
    ],
    "indexed_stats": {
        "total_files": 124,
        "total_units": 856,
        "languages": {"python": 98, "typescript": 26}
    }
}
```

### Example 2: Enhanced Search Results

```python
# User searches
response = await server.search_code(
    query="authentication token validation",
    limit=10
)

# Returns:
{
    "status": "success",
    "results": [
        # ... 10 code results
    ],
    "total_found": 10,
    "summary": "Found 7 functions and 3 classes across 5 files in Python",
    "facets": {
        "languages": {"python": 10},
        "unit_types": {"function": 7, "class": 3},
        "files": {
            "/src/auth/jwt_validator.py": 4,
            "/src/auth/token_service.py": 3,
            "/src/middleware/auth.py": 2,
            "/src/api/auth_routes.py": 1
        },
        "directories": {
            "/src/auth": 7,
            "/src/middleware": 2,
            "/src/api": 1
        }
    },
    "refinement_hints": [
        "💡 Results focused in /src/auth. Try file_pattern='/src/auth/*' to explore related code"
    ],
    "did_you_mean": [],  # Empty since query was good
    "quality": "excellent",
    "confidence": "very_high",
    # ... other fields
}
```

### Example 3: Typo Correction

```python
# User misspells "authentication"
response = await server.search_code(
    query="athentication logic",  # Typo
    limit=10
)

# Returns:
{
    "status": "success",
    "results": [],  # No exact matches
    "total_found": 0,
    "summary": "No results found",
    "did_you_mean": [
        "authentication logic",  # Spelling correction
        "authorization logic"   # Synonym suggestion
    ],
    "suggestions": [
        "Did you mean 'authentication logic'?",
        "Did you mean 'authorization logic'?",
        "Try using synonyms like 'auth' or 'login'",
        # ... other suggestions
    ],
    "refinement_hints": [],
    "quality": "poor",
    "confidence": "very_low"
}
```

## Test Plan

### Unit Tests (16 tests)

#### QuerySuggester (4 tests)
1. `test_intent_based_suggestions` - Verify templates for each intent type
2. `test_project_specific_suggestions` - Extract from indexed content
3. `test_domain_preset_suggestions` - Return auth/database/API templates
4. `test_suggestion_caching` - Verify cache behavior and TTL

#### ResultSummarizer (4 tests)
1. `test_single_language_summary` - "Found 5 functions in Python"
2. `test_multi_language_summary` - "Found 8 results in Python and TypeScript"
3. `test_multi_project_summary` - Include project count
4. `test_empty_results_summary` - "No results found"

#### SpellingSuggester (4 tests)
1. `test_typo_correction` - Levenshtein distance corrections
2. `test_synonym_suggestions` - Use PROGRAMMING_SYNONYMS
3. `test_indexed_term_matching` - Match against actual code
4. `test_no_suggestions_for_good_query` - Don't suggest when unnecessary

#### RefinementAdvisor (4 tests)
1. `test_too_many_results_hints` - Suggest narrowing
2. `test_too_few_results_hints` - Suggest broadening
3. `test_scattered_results_hints` - Suggest file_pattern
4. `test_mixed_types_hints` - Suggest type filtering

### Integration Tests (10 tests)

#### suggest_queries Tool (3 tests)
1. `test_suggest_queries_with_intent` - Full flow with intent
2. `test_suggest_queries_project_specific` - Extract from real index
3. `test_suggest_queries_no_index` - Handle empty project gracefully

#### Enhanced search_code (7 tests)
1. `test_search_with_facets` - Verify facet calculation
2. `test_search_with_summary` - Verify summary generation
3. `test_search_with_refinement_hints` - Verify hint logic
4. `test_search_with_typo_correction` - "Did you mean?" workflow
5. `test_search_large_result_set` - 100+ results with facets
6. `test_search_empty_results_with_suggestions` - Full suggestion flow
7. `test_search_backward_compatibility` - Existing clients still work

### Performance Tests (2 tests)
1. `test_facet_performance` - <5ms for 1000 results
2. `test_suggestion_generation_performance` - <50ms for 8 suggestions

## Success Criteria

### UX Improvements Metrics

1. **Query Success Rate:** 60% → 85%
   - Measured by: queries returning results / total queries
   - Target: 85% of searches return at least 1 result

2. **Time to Answer:** -30%
   - Measured by: time from query to satisfactory result
   - Target: Reduce from ~45s to ~30s average

3. **Refinement Adoption:** 70%
   - Measured by: users who try suggested refinements
   - Target: 70% of users shown hints try at least one

4. **Zero-Result Rate:** 40% → 10%
   - Measured by: queries returning 0 results / total queries
   - Target: Reduce "no results" from 40% to 10%

5. **Typo Recovery:** 90%
   - Measured by: typo queries that lead to successful correction
   - Target: 90% of detected typos result in user trying suggestion

### Technical Quality Metrics

1. **Test Coverage:** 85%+ for new code
2. **Performance:** <5ms overhead for facets/summaries
3. **Accuracy:** 80%+ of suggestions are helpful (user testing)
4. **Backward Compatibility:** No breaking changes to existing API

## Risks & Mitigation

### Risk 1: Suggestion Quality
**Risk:** Auto-generated suggestions are irrelevant or confusing
**Impact:** HIGH - Users lose trust in system
**Mitigation:**
- Start conservative (fewer, high-confidence suggestions)
- A/B test different suggestion algorithms
- Collect feedback on suggestion helpfulness
- Allow users to dismiss/hide suggestions

### Risk 2: Performance Overhead
**Risk:** Facet building slows down search significantly
**Impact:** MEDIUM - Unacceptable latency increase
**Mitigation:**
- Implement facet caching for common queries
- Make facets optional (default on, can disable)
- Optimize facet calculation (single-pass over results)
- Set limits (e.g., only build facets for <500 results)

### Risk 3: Synonym/Spelling Dictionary Maintenance
**Risk:** Hardcoded synonyms become outdated or project-specific
**Impact:** LOW - Suggestions become less relevant over time
**Mitigation:**
- Extract terms from actual indexed code dynamically
- Allow project-specific synonym extensions via config
- Monitor suggestion click-through rates
- Quarterly review of synonym dictionary

### Risk 4: Information Overload
**Risk:** Too many suggestions/hints overwhelm users
**Impact:** MEDIUM - Paradox of choice, decision paralysis
**Mitigation:**
- Limit to 3 suggestions per category max
- Progressive disclosure (show more on request)
- Prioritize hints by impact
- A/B test different UI presentations

### Risk 5: Breaking Changes
**Risk:** Enhanced search response breaks existing clients
**Impact:** HIGH - Production systems fail
**Mitigation:**
- Make all new fields optional
- Maintain backward compatibility
- Version API if needed
- Add integration tests for old response format

## Next Steps

1. **Get user approval** on overall design and priorities
2. **Create Phase 1 branch** and implement foundation components
3. **Write unit tests** for QuerySuggester, ResultSummarizer, etc.
4. **Implement suggest_queries** MCP tool
5. **Enhance search_code** with facets and hints
6. **User testing** with real developers
7. **Iterate** based on feedback
8. **Merge to main** and update documentation

## Dependencies

- Existing: `src/search/query_synonyms.py` (synonym dictionary)
- Existing: `src/memory/conversation_tracker.py` (popular queries)
- Existing: `src/core/server.py` (search_code method)
- New: Python difflib for spell checking
- New: Data models for QuerySuggestion, SearchFacets

## Open Questions

1. **Should facets be client-side or server-side?**
   - Server-side = easier, consistent, but more payload
   - Client-side = flexible, but duplicates logic
   - **Decision:** Server-side (easier to maintain, consistent experience)

2. **How to handle cross-project facets?**
   - Include project dimension in facets?
   - Separate tool for cross-project faceted search?
   - **Decision:** Add `projects` facet only for search_all_projects

3. **Persist suggestion feedback?**
   - Track which suggestions users click
   - Use for ML-based ranking later?
   - **Decision:** Phase 2 enhancement, not MVP

4. **Should suggest_queries be proactive or on-demand?**
   - Proactive = show on empty search box
   - On-demand = only when user requests
   - **Decision:** On-demand initially, proactive in Phase 2

## References

- FEAT-047: Proactive Memory Suggestions (similar pattern detector)
- FEAT-028: Proactive Context Suggestions (intent detection)
- src/search/query_synonyms.py (existing synonym system)
- src/memory/query_expander.py (query expansion logic)
- EVAL-001: Empirical evaluation findings (UX pain points)
