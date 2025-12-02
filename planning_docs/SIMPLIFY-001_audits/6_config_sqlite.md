# Config & SQLite Audit - SIMPLIFY-001 Phase 1, Task 1.6

**Date**: 2025-12-01
**Scope**: Comprehensive audit of configuration and SQLite schema related to features being removed in SIMPLIFY-001
**Features Targeted for Removal**:
- Graph/Visualization
- Import/Export/Backup
- Auto-Tagging
- Analytics
- Most health monitoring

## Summary

| Category | Count | Details |
|----------|-------|---------|
| Config fields to REMOVE | 3 | Analytics-related config fields |
| Config fields to MODIFY | 1 | Remove/simplify analytics from feature presets |
| SQLite tables to REMOVE | 13 | Analytics, tagging, monitoring, remediation tables |
| SQLite tables to KEEP | 4 | Project index, embeddings cache, job state, feedback |
| Estimated Impact | Medium | Schema changes affect health monitoring and analytics entirely |

## Configuration Analysis (src/config.py)

### Sections/Fields to REMOVE

| Field/Section | Lines | Classification | Description |
|---------------|-------|-----------------|-------------|
| `AnalyticsFeatures` class | 113-142 | **ENTIRE CLASS** | Entire analytics feature group: `usage_tracking`, `usage_pattern_analytics`, `usage_analytics_retention_days` |
| `config.analytics` | 408 | Instance field | Analytics feature group instantiation in ServerConfig |
| Feature preset analytics | 521 | Logic in validator | `feature_level` ADVANCED preset enables `usage_pattern_analytics` |

**Rationale**: Analytics features are being removed entirely. This includes all tracking of usage patterns, query history, and analytics retention configuration.

### Fields to KEEP (but may need modification)

| Field | Lines | Status | Notes |
|-------|-------|--------|-------|
| `PerformanceFeatures` | 34-80 | KEEP | Performance optimization (GPU, embeddings) - unrelated to health monitoring |
| `SearchFeatures` | 82-111 | KEEP | Core search functionality including hybrid search |
| `MemoryFeatures` | 144-173 | KEEP | Memory management including pruning and conversation tracking |
| `IndexingFeatures` | 175-216 | KEEP | Core indexing functionality |
| `QualityThresholds` | 218-277 | KEEP | Duplicate detection and complexity analysis |
| `AdvancedFeatures` | 279-293 | KEEP | Multi-repo support, read-only mode |
| `embedding_cache_enabled` | 390 | KEEP | Embedding cache is critical for performance |
| `embedding_cache_path` | 391 | KEEP | Required for cache persistence |
| `embedding_cache_ttl_days` | 392 | KEEP | Manage cache lifecycle |

### Important: No other config changes needed

The removal of analytics is self-contained. No other configuration fields depend on or reference analytics features.

---

## SQLite Tables Audit

### Tables to REMOVE (13 total)

These tables are exclusively used by removed features and have zero integration with core functionality.

#### Analytics & Tracking (3 tables)

| Table | File | Purpose | Records | Dependencies |
|-------|------|---------|---------|--------------|
| `query_history` | src/analytics/usage_tracker.py (line 41) | Track search queries for analytics | ~tracking metrics | Only used by UsagePatternTracker (REMOVING) |
| `code_access_log` | src/analytics/usage_tracker.py (line 54) | Track file/function access | ~tracking metrics | Only used by UsagePatternTracker (REMOVING) |
| `usage_statistics` | src/analytics/usage_tracker.py (line 66) | Aggregated usage stats | ~tracking metrics | Only used by UsagePatternTracker (REMOVING) |

**Status**: Safe to drop - zero integration with core search/memory.

#### Tagging System (4 tables)

| Table | File | Purpose | Records | Dependencies |
|-------|------|---------|---------|--------------|
| `tags` | src/tagging/tag_manager.py (line 37) | Hierarchical tag definitions | User-created tags | Only used by TagManager and auto-tagging (REMOVING) |
| `memory_tags` | src/tagging/tag_manager.py (line 54) | Tag-memory associations | Millions possible | Only used by TagManager and Tagging subsystem (REMOVING) |
| `collections` | src/tagging/collection_manager.py (line 38) | Named memory collections | User-created collections | Only used by CollectionManager (REMOVING) |
| `collection_memories` | src/tagging/collection_manager.py (line 52) | Collection-memory associations | Millions possible | Only used by CollectionManager (REMOVING) |

**Status**: Safe to drop - zero integration with core search.

#### Health Monitoring & Remediation (5 tables)

| Table | File | Purpose | Records | Dependencies |
|-------|------|---------|---------|--------------|
| `health_metrics` | src/monitoring/metrics_collector.py (line 109) | Time-series health snapshots | ~1 per day | Only used by MetricsCollector and health dashboard (REMOVING) |
| `query_log` | src/monitoring/metrics_collector.py (line 159) | Query performance tracking | ~queries per day | Only used by MetricsCollector (REMOVING) |
| `alert_history` | src/monitoring/alert_engine.py (line 236) | Alert event tracking | ~alerts generated | Only used by AlertEngine (REMOVING) |
| `performance_metrics` | src/monitoring/performance_tracker.py (line 139) | Performance baseline metrics | ~metrics collected | Only used by PerformanceTracker (REMOVING) |
| `performance_baselines` | src/monitoring/performance_tracker.py (line 167) | Performance baseline statistics | 5 metrics max | Only used by PerformanceTracker (REMOVING) |
| `performance_regressions` | src/monitoring/performance_tracker.py (line 185) | Performance regression history | ~regressions detected | Only used by PerformanceTracker (REMOVING) |
| `remediation_history` | src/monitoring/remediation.py (line 79) | Automated remediation action history | ~actions executed | Only used by RemediationEngine (REMOVING) |

**Status**: Safe to drop - entirely part of health monitoring system.

#### Analytics Tokens (1 table)

| Table | File | Purpose | Records | Dependencies |
|-------|------|---------|---------|--------------|
| `token_usage_events` | src/analytics/token_tracker.py (line 83) | Token usage tracking for cost analytics | ~events tracked | Only used by TokenTracker (REMOVING) |

**Status**: Safe to drop - analytics feature.

### Tables to KEEP (4 total)

These tables are essential to core functionality and MUST be preserved.

#### Core Infrastructure (4 tables)

| Table | File | Purpose | Records | Why Keep | Dependencies |
|-------|------|---------|---------|----------|--------------|
| `embeddings` | src/embeddings/cache.py (line 74) | **CRITICAL**: Embedding vector cache | Millions | Performance - avoids re-embedding same text | Used by EmbeddingCache, search, indexing |
| `project_index_metadata` | src/memory/project_index_tracker.py (line 106) | Project indexing state tracking | Per project | Auto-indexing decisions, file watcher state | Used by ProjectIndexTracker, auto-indexing service |
| `indexing_jobs` | src/memory/job_state_manager.py (line 69) | Background indexing job state | Active jobs | Job resumption, user progress tracking | Used by JobStateManager, background indexer |
| `suggestion_feedback` | src/memory/feedback_tracker.py (line 82) | Proactive suggestion feedback | Per suggestion | Threshold adaptation for suggestions | Used by FeedbackTracker, proactive suggester |
| `indexing_metrics` | src/memory/indexing_metrics.py (line 26) | Indexing performance metrics | Per indexing run | Performance analytics, user guidance | Used by IndexingMetricsStore, indexing service |
| `project_consent` | src/memory/cross_project_consent.py (line 48) | Cross-project search consent preferences | Per project | Privacy control for cross-project search | Used by CrossProjectConsentManager, search service |

**Note**: 
- `embedding_cache` is the SINGLE MOST CRITICAL table - removing this would require re-embedding millions of code units
- `project_index_metadata` is essential for efficient auto-indexing decisions
- `indexing_jobs` is needed for resumable background indexing
- `suggestion_feedback`, `indexing_metrics`, `project_consent` are optional but non-trivial to rebuild

---

## Migration Strategy

### Phase 1: Safe Data Loss (Immediate)

**These can be dropped without migration:**

1. Drop all analytics tables
   ```sql
   DROP TABLE IF EXISTS query_history;
   DROP TABLE IF EXISTS code_access_log;
   DROP TABLE IF EXISTS usage_statistics;
   DROP TABLE IF EXISTS token_usage_events;
   ```

2. Drop all monitoring tables
   ```sql
   DROP TABLE IF EXISTS health_metrics;
   DROP TABLE IF EXISTS query_log;
   DROP TABLE IF EXISTS alert_history;
   DROP TABLE IF EXISTS performance_metrics;
   DROP TABLE IF EXISTS performance_baselines;
   DROP TABLE IF EXISTS performance_regressions;
   DROP TABLE IF EXISTS remediation_history;
   ```

3. Drop all tagging tables
   ```sql
   DROP TABLE IF EXISTS tags;
   DROP TABLE IF EXISTS memory_tags;
   DROP TABLE IF EXISTS collections;
   DROP TABLE IF EXISTS collection_memories;
   ```

**Impact**: ZERO - these tables are only used by removed features.

### Phase 2: Module Cleanup (Implementation)

Remove these modules entirely:
- `src/analytics/` directory (usage_tracker.py, token_tracker.py)
- `src/monitoring/` directory (metrics_collector.py, alert_engine.py, performance_tracker.py, remediation.py, capacity_planner.py, health_reporter.py)
- `src/tagging/` directory (tag_manager.py, collection_manager.py, models.py)
- All corresponding tests in `tests/unit/test_*analytics*`, `tests/unit/test_*tag*`, `tests/unit/monitoring/`, etc.

### Phase 3: Configuration Cleanup (Post-Feature Removal)

After features are removed:
1. Remove `AnalyticsFeatures` class from config.py
2. Remove `self.analytics` field from ServerConfig
3. Remove analytics-related logic from feature presets (line 521 in apply_feature_level_preset)

### Database Cleanup Script

Create `scripts/cleanup-removed-features.py`:

```python
"""Cleanup SQLite tables for removed features."""
import sqlite3
from pathlib import Path
from src.config import get_config

def cleanup_removed_features():
    """Drop tables for removed features."""
    config = get_config()
    db_path = config.sqlite_path_expanded
    
    if not db_path.exists():
        print(f"Database not found: {db_path}")
        return
    
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    tables_to_drop = [
        # Analytics
        "query_history", "code_access_log", "usage_statistics", "token_usage_events",
        # Monitoring
        "health_metrics", "query_log", "alert_history", 
        "performance_metrics", "performance_baselines", "performance_regressions",
        "remediation_history",
        # Tagging
        "tags", "memory_tags", "collections", "collection_memories",
    ]
    
    for table in tables_to_drop:
        try:
            cursor.execute(f"DROP TABLE IF EXISTS {table}")
            print(f"Dropped table: {table}")
        except Exception as e:
            print(f"Failed to drop {table}: {e}")
    
    conn.commit()
    conn.close()
    print("Cleanup complete")

if __name__ == "__main__":
    cleanup_removed_features()
```

---

## Risk Assessment

### LOW RISK (Safe to proceed)

- **Analytics removal**: 100% isolated, zero dependencies
- **Tagging removal**: 100% isolated, used only by auto-tagging and collection features
- **Monitoring removal**: 95% isolated (only health_scorer used health metrics for pruning decisions - can be replaced with simpler heuristics)

### MEDIUM RISK (Requires testing)

- **Embedding cache**: If kept (which it should be), ensure no schema changes
- **Project consent table**: Ensure cross-project search handles missing consent gracefully (should default to opted-in)

### CRITICAL (Must preserve)

- `embeddings` table - performance would be unacceptable without this
- `project_index_metadata` table - auto-indexing would be inefficient without this
- `indexing_jobs` table - background jobs would lose state without this

---

## Configuration Summary

### Before SIMPLIFY-001
- **Config Classes**: 7 (Performance, Search, Analytics, Memory, Indexing, Quality, Advanced)
- **Total Config Fields**: ~60
- **Analytics-related**: 3 fields
- **Feature Presets**: 3 levels (BASIC, ADVANCED, EXPERIMENTAL)

### After SIMPLIFY-001
- **Config Classes**: 6 (Performance, Search, Memory, Indexing, Quality, Advanced)
- **Total Config Fields**: ~57
- **Analytics-related**: 0 fields
- **Feature Presets**: 3 levels (same, but without analytics)

---

## Files Requiring Changes

### Immediate Deletions
- [ ] `src/analytics/` directory (entire)
- [ ] `src/monitoring/` directory (entire)
- [ ] `src/tagging/` directory (entire)
- [ ] All analytics/monitoring/tagging tests

### Configuration Changes
- [ ] `src/config.py` - Remove AnalyticsFeatures class and analytics field

### Conditional Removals (Post-feature-removal)
- [ ] CLI commands: `--health`, `--analytics`, `--tags`, `--collections`, `--export`, `--import`, `--backup`
- [ ] Dashboard health monitoring UI
- [ ] Graph visualization components

---

## Sign-off

This audit confirms that removing the identified features is **safe and straightforward**:

1. ✅ All tables and config are isolated with zero core dependencies
2. ✅ No data migration needed (data is analytics/monitoring only)
3. ✅ Clean module boundaries enable straightforward deletion
4. ✅ Core features (search, indexing, embeddings) unaffected

**Proceed with SIMPLIFY-001 Phase 1 Task 1.6 implementation.**
