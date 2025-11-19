# UX-024: Usage Feedback Mechanisms

## TODO Reference
- TODO.md: "Usage feedback mechanisms (~2-3 days)"

## Objective
Implement feedback collection and learning mechanisms to improve search quality based on user behavior.

## Requirements (from TODO.md)

### Core Features
1. "Was this helpful?" for search results
2. Learning from user behavior
3. Query refinement suggestions
4. Result quality metrics

## Implementation Plan

### Phase 1: Feedback Storage Schema
- [ ] Create database schema for feedback tracking
  - `search_feedback` table: query, results, rating, timestamp
  - `result_quality_metrics` table: aggregated statistics
- [ ] Add feedback tracking to SQLite store
- [ ] Add feedback tracking to Qdrant store (metadata)

### Phase 2: Feedback Collection API
- [ ] Add `submit_search_feedback()` method to server.py
  - Parameters: search_id, rating (helpful/not helpful), optional comment
  - Store feedback with query and result context
- [ ] Add `get_search_quality_metrics()` method
  - Return aggregated quality statistics
  - Useful for monitoring and optimization

### Phase 3: Learning from Feedback
- [ ] Create `src/feedback/feedback_analyzer.py`
  - Analyze feedback patterns
  - Identify low-quality result patterns
  - Generate improvement suggestions
- [ ] Implement query refinement suggestions
  - Based on failed searches (low ratings)
  - Suggest alternative queries or filters

### Phase 4: Integration with Search
- [ ] Track search sessions with unique IDs
  - Associate feedback with specific searches
- [ ] Add result quality scoring
  - Incorporate historical feedback into ranking
  - Boost results with positive feedback

### Phase 5: MCP Tools
- [ ] `submit_search_feedback(search_id, rating, comment)`
- [ ] `get_quality_metrics(time_range, project_name)`
- [ ] `get_query_suggestions(query)`

### Phase 6: Testing
- [ ] Unit tests for feedback storage
- [ ] Unit tests for feedback analysis
- [ ] Integration tests for MCP tools
- [ ] Tests for quality metrics calculation

## Database Schema

### search_feedback
```sql
CREATE TABLE IF NOT EXISTS search_feedback (
    id TEXT PRIMARY KEY,
    search_id TEXT NOT NULL,
    query TEXT NOT NULL,
    result_ids TEXT,  -- JSON array of result memory IDs
    rating TEXT NOT NULL,  -- 'helpful' or 'not_helpful'
    comment TEXT,
    project_name TEXT,
    timestamp TEXT NOT NULL,
    user_id TEXT  -- Optional for multi-user scenarios
);
```

### result_quality_metrics
```sql
CREATE TABLE IF NOT EXISTS result_quality_metrics (
    id TEXT PRIMARY KEY,
    time_window TEXT NOT NULL,  -- 'hour', 'day', 'week'
    window_start TEXT NOT NULL,
    total_searches INTEGER DEFAULT 0,
    helpful_count INTEGER DEFAULT 0,
    not_helpful_count INTEGER DEFAULT 0,
    avg_result_count REAL DEFAULT 0,
    project_name TEXT,
    updated_at TEXT NOT NULL
);
```

## Design Decisions

### Feedback Granularity
- Collect feedback per search (not per individual result)
- Allow optional comments for detailed feedback
- Track which results were shown to understand context

### Privacy
- No PII collection by default
- Optional user_id for multi-user scenarios
- Feedback stored locally, not sent to external services

### Learning Approach
- Statistical analysis of feedback patterns
- Identify common characteristics of helpful vs not helpful results
- Query refinement based on successful searches

### Quality Metrics
- Calculate hourly, daily, and weekly metrics
- Track by project for project-specific insights
- Helpfulness rate = helpful / (helpful + not_helpful)

## Success Criteria
- [ ] Can submit feedback for search results
- [ ] Feedback is stored persistently
- [ ] Quality metrics are calculated correctly
- [ ] Query suggestions generated based on feedback
- [ ] Tests pass with 85%+ coverage
- [ ] Documentation updated

## Files to Create/Modify

**Create:**
- `src/feedback/feedback_analyzer.py` - Feedback analysis and learning
- `src/feedback/feedback_store.py` - Feedback storage interface
- `tests/unit/test_feedback_system.py` - Unit tests
- `planning_docs/UX-024_usage_feedback_mechanisms.md` - This file

**Modify:**
- `src/store/sqlite_store.py` - Add feedback tables and methods
- `src/core/server.py` - Add feedback MCP tools
- `src/core/models.py` - Add feedback models (FeedbackSubmission, QualityMetrics)
- `CHANGELOG.md` - Document feature

## Progress Tracking
- [x] Phase 1: Feedback Storage Schema (COMPLETE - 2025-11-18)
  - Added `search_feedback` table to SQLite store
  - Created indices for efficient querying
- [x] Phase 2: Feedback Collection API (COMPLETE - 2025-11-18)
  - Implemented `submit_search_feedback()` in SQLite store
  - Implemented `get_quality_metrics()` in SQLite store
- [x] Phase 5: MCP Tools (COMPLETE - 2025-11-18)
  - Added `submit_search_feedback()` to server.py
  - Added `get_quality_metrics()` to server.py
- [x] Phase 6: Testing (COMPLETE - 2025-11-18)
  - Created 10 comprehensive tests (all passing)
  - Covers submission, metrics, error handling, integration
- [ ] Phase 3: Learning from Feedback (DEFERRED - future enhancement)
- [ ] Phase 4: Integration with Search (DEFERRED - future enhancement)

## Implementation Notes

**MVP Delivered:**
- Core feedback collection and metrics tracking implemented
- Database schema and storage methods complete
- MCP tools functional and tested
- 10/10 tests passing

**Deferred for Future:**
- Query refinement suggestions based on feedback patterns
- Machine learning from feedback to improve search ranking
- Advanced analytics and visualization
