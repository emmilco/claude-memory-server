# FEAT-037: Continuous Health Monitoring & Alerts

## TODO Reference
- TODO.md: "FEAT-037: Continuous Health Monitoring & Alerts (~1-2 weeks) 🔥🔥🔥"
- Strategic Planning: `planning_docs/STRATEGIC-001_long_term_product_evolution.md` (Section #6)

## Objective
Implement proactive degradation detection through continuous health monitoring and automated alerts to catch problems before they become catastrophic.

## Current State
- Basic health check exists (UX-004) but only checks system prerequisites
- Status command shows stats but no quality metrics or alerts
- No proactive monitoring or trend analysis
- Users discover problems only after quality has severely degraded
- No automated remediation or recommendations

## Strategic Context

**Problem:** Without intervention, 70% of users will abandon the system at 6-12 months due to silent quality degradation.

**Solution:** Early warning system that detects degradation before it becomes catastrophic.

**Impact:**
- Prevents Path B abandonment (-10% probability)
- Provides clear feedback loop
- Enables proactive maintenance
- Builds user confidence

**Priority:** P0 - Critical foundation for long-term viability

## Implementation Plan

### Phase 1: Metrics Collection Pipeline ✅

**File:** `src/monitoring/metrics_collector.py`

**Responsibilities:**
- Collect performance metrics (search latency, cache hit rate, index staleness)
- Collect quality metrics (avg relevance, noise ratio, duplicate rate, contradiction rate)
- Collect database health metrics (memory counts by lifecycle state, project counts, size)
- Collect usage patterns (queries/day, memories created/day, results/query)
- Store time-series data for trend analysis
- Provide aggregation methods (daily, weekly, monthly)

**Data Model:**
```python
@dataclass
class HealthMetrics:
    timestamp: datetime

    # Performance metrics
    avg_search_latency_ms: float
    p95_search_latency_ms: float
    cache_hit_rate: float
    index_staleness_ratio: float

    # Quality metrics
    avg_result_relevance: float
    noise_ratio: float
    duplicate_rate: float
    contradiction_rate: float

    # Database health
    total_memories: int
    active_memories: int
    recent_memories: int
    archived_memories: int
    stale_memories: int
    active_projects: int
    archived_projects: int
    database_size_mb: float

    # Usage patterns
    queries_per_day: float
    memories_created_per_day: float
    avg_results_per_query: float
```

**Storage:**
- SQLite table: `health_metrics` with time-series data
- Retention: Keep 90 days of daily metrics, 12 months of weekly aggregates
- Indexes on timestamp for fast queries

### Phase 2: Alert Rule Engine ✅

**File:** `src/monitoring/alert_engine.py`

**Responsibilities:**
- Define alert thresholds (CRITICAL/WARNING/INFO)
- Evaluate current metrics against thresholds
- Generate alerts with severity levels
- Track alert history (prevent alert spam)
- Provide alert suppression/snooze functionality

**Alert Levels:**

**CRITICAL:**
- avg_result_relevance < 0.50 - "Search quality critically low"
- avg_search_latency_ms > 100 - "Search too slow"
- noise_ratio > 0.50 - "Database heavily polluted"

**WARNING:**
- avg_result_relevance < 0.65 - "Search quality degrading"
- avg_search_latency_ms > 50 - "Search slowing down"
- noise_ratio > 0.30 - "Database accumulating noise"
- stale_memories > 2000 - "Many stale memories"
- cache_hit_rate < 0.70 - "Cache performance poor"

**INFO:**
- database_size_mb > 1000 - "Database growing large"
- active_projects > 10 - "Many active projects"

**Alert Model:**
```python
@dataclass
class Alert:
    id: str
    severity: Literal["CRITICAL", "WARNING", "INFO"]
    metric_name: str
    current_value: float
    threshold_value: float
    message: str
    recommendations: List[str]
    timestamp: datetime
    resolved: bool
    snoozed_until: Optional[datetime]
```

### Phase 3: Health Reporter ✅

**File:** `src/monitoring/health_reporter.py`

**Responsibilities:**
- Generate overall health score (0-100)
- Create weekly health reports
- Track trends (improvements/regressions)
- Provide actionable recommendations
- Format reports for CLI display

**Health Score Algorithm:**
```python
def calculate_health_score(metrics: HealthMetrics) -> int:
    """
    Calculate overall health score (0-100)

    Weighting:
    - Performance: 30% (latency, cache hit rate)
    - Quality: 40% (relevance, noise ratio)
    - Database health: 20% (lifecycle distribution)
    - Usage efficiency: 10% (results per query)
    """
    performance_score = ...
    quality_score = ...
    db_health_score = ...
    usage_score = ...

    total = (
        performance_score * 0.30 +
        quality_score * 0.40 +
        db_health_score * 0.20 +
        usage_score * 0.10
    )

    return int(total * 100)
```

**Report Format:**
```
MEMORY HEALTH REPORT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Overall Health: 72/100 (GOOD)

Database Status:
  Total Memories: 8,450
  ├─ ACTIVE:     1,200 (14%) ✓
  ├─ RECENT:     2,400 (28%) ✓
  ├─ ARCHIVED:   3,850 (46%) ⚠️
  └─ STALE:      1,000 (12%) ❌

Quality Metrics:
  Avg Relevance:     0.68 (GOOD)
  Noise Ratio:       22% (GOOD)
  Duplicate Rate:    8% (ACCEPTABLE)
  Contradiction Rate: 3% (GOOD)

Performance:
  Search Latency:    18ms (GOOD)
  Cache Hit Rate:    78% (GOOD)
  Index Freshness:   85% (GOOD)

Recommendations:
  • Prune 1,000 STALE memories (automated)
  • Archive 5 inactive projects
  • Review 12 contradictory preferences
```

### Phase 4: Automated Remediation ✅

**File:** `src/monitoring/remediation.py`

**Responsibilities:**
- Define remediation actions for common issues
- Execute automated fixes (with user approval)
- Track remediation history
- Provide dry-run mode

**Remediation Actions:**
```python
class RemediationAction:
    name: str
    description: str
    automatic: bool  # Can run without user approval
    execute: Callable[[], RemediationResult]

actions = [
    # Automatic actions
    RemediationAction(
        name="prune_stale_memories",
        description="Delete STALE memories (>180 days, <2 accesses)",
        automatic=True,
        execute=lambda: prune_stale_memories()
    ),

    # User approval required
    RemediationAction(
        name="archive_inactive_projects",
        description="Archive projects with no activity in 45+ days",
        automatic=False,
        execute=lambda: suggest_project_archival()
    ),

    RemediationAction(
        name="merge_duplicates",
        description="Merge high-confidence duplicate memories",
        automatic=False,
        execute=lambda: run_duplicate_detection()
    ),
]
```

**Auto-Fix Triggers:**
- If avg_result_relevance < 0.65 for 7+ days → trigger aggressive pruning
- If noise_ratio > 0.30 → suggest project archival
- If duplicate_rate > 0.15 → run duplicate detection
- If stale_memories > 2000 → auto-prune stale memories

### Phase 5: CLI Commands ✅

**File:** `src/cli/health_monitor_command.py`

**Commands:**

1. **`health-monitor`** - Show current health with active alerts
```bash
python -m src.cli health-monitor

# Shows:
# - Overall health score
# - Active alerts (CRITICAL/WARNING/INFO)
# - Key metrics snapshot
# - Recommendations
```

2. **`health-report`** - Generate detailed weekly report
```bash
python -m src.cli health-report [--period weekly|monthly]

# Shows:
# - Full health report with trends
# - Week-over-week comparisons
# - Detailed recommendations
```

3. **`health-fix`** - Apply automated remediation
```bash
python -m src.cli health-fix [--auto] [--dry-run]

# --auto: Apply automatic fixes without prompts
# --dry-run: Show what would be fixed without applying
```

4. **`health-history`** - View historical metrics
```bash
python -m src.cli health-history [--days 30]

# Shows time-series data for key metrics
```

### Phase 6: Testing ✅

**Test Coverage Target:** 90%+ for all monitoring modules

**Test Files:**

1. **`tests/unit/test_metrics_collector.py`** (~12 tests)
   - Metric collection from stores
   - Time-series storage and retrieval
   - Aggregation methods (daily/weekly)
   - Edge cases (empty database, new installation)

2. **`tests/unit/test_alert_engine.py`** (~10 tests)
   - Alert threshold evaluation
   - Severity classification
   - Alert history tracking
   - Snooze functionality
   - Recommendation generation

3. **`tests/unit/test_health_reporter.py`** (~8 tests)
   - Health score calculation
   - Report generation
   - Trend analysis
   - Formatting

4. **`tests/unit/test_remediation.py`** (~8 tests)
   - Remediation action execution
   - Dry-run mode
   - Auto-fix triggers
   - History tracking

5. **`tests/integration/test_health_monitoring_integration.py`** (~5 tests)
   - End-to-end health check workflow
   - Alert → Remediation pipeline
   - CLI command integration

**Total:** ~43 tests

### Phase 7: Integration ✅

**Integrate with existing systems:**

1. **Server Integration:**
   - Hook metrics collection into search operations
   - Track search latency, relevance scores
   - Record cache hit rates

2. **Store Integration:**
   - Add metrics queries to SQLite/Qdrant stores
   - Count memories by lifecycle state
   - Calculate noise ratios

3. **Pruner Integration:**
   - Trigger pruning from remediation actions
   - Track pruning effectiveness

4. **Lifecycle Integration:**
   - Use lifecycle states for health scoring
   - Track state transitions

## Database Schema

### health_metrics table
```sql
CREATE TABLE IF NOT EXISTS health_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,

    -- Performance
    avg_search_latency_ms REAL,
    p95_search_latency_ms REAL,
    cache_hit_rate REAL,
    index_staleness_ratio REAL,

    -- Quality
    avg_result_relevance REAL,
    noise_ratio REAL,
    duplicate_rate REAL,
    contradiction_rate REAL,

    -- Database health
    total_memories INTEGER,
    active_memories INTEGER,
    recent_memories INTEGER,
    archived_memories INTEGER,
    stale_memories INTEGER,
    active_projects INTEGER,
    archived_projects INTEGER,
    database_size_mb REAL,

    -- Usage
    queries_per_day REAL,
    memories_created_per_day REAL,
    avg_results_per_query REAL,

    -- Metadata
    health_score INTEGER,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_health_metrics_timestamp ON health_metrics(timestamp);
```

### alert_history table
```sql
CREATE TABLE IF NOT EXISTS alert_history (
    id TEXT PRIMARY KEY,
    severity TEXT NOT NULL,
    metric_name TEXT NOT NULL,
    current_value REAL NOT NULL,
    threshold_value REAL NOT NULL,
    message TEXT NOT NULL,
    recommendations TEXT,  -- JSON array
    timestamp TEXT NOT NULL,
    resolved INTEGER DEFAULT 0,
    resolved_at TEXT,
    snoozed_until TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_alert_history_timestamp ON alert_history(timestamp);
CREATE INDEX IF NOT EXISTS idx_alert_history_severity ON alert_history(severity);
CREATE INDEX IF NOT EXISTS idx_alert_history_resolved ON alert_history(resolved);
```

### remediation_history table
```sql
CREATE TABLE IF NOT EXISTS remediation_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    action_name TEXT NOT NULL,
    triggered_by TEXT NOT NULL,  -- 'automatic' or 'user'
    dry_run INTEGER DEFAULT 0,
    success INTEGER DEFAULT 1,
    items_affected INTEGER DEFAULT 0,
    error_message TEXT,
    timestamp TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_remediation_history_timestamp ON remediation_history(timestamp);
```

## Configuration

Add to `src/config.py`:

```python
# Health Monitoring
ENABLE_HEALTH_MONITORING: bool = True
HEALTH_METRICS_RETENTION_DAYS: int = 90
HEALTH_CHECK_INTERVAL_HOURS: int = 24
HEALTH_AUTO_FIX_ENABLED: bool = False  # Require explicit user opt-in

# Alert Thresholds (can be customized)
ALERT_CRITICAL_RELEVANCE_THRESHOLD: float = 0.50
ALERT_WARNING_RELEVANCE_THRESHOLD: float = 0.65
ALERT_CRITICAL_LATENCY_MS: float = 100.0
ALERT_WARNING_LATENCY_MS: float = 50.0
ALERT_CRITICAL_NOISE_RATIO: float = 0.50
ALERT_WARNING_NOISE_RATIO: float = 0.30
```

## Implementation Checklist

- [x] Create planning document
- [ ] Implement metrics_collector.py
- [ ] Implement alert_engine.py
- [ ] Implement health_reporter.py
- [ ] Implement remediation.py
- [ ] Create CLI health_monitor_command.py
- [ ] Add database schemas to SQLite store
- [ ] Integrate with existing server/stores
- [ ] Write comprehensive tests (~43 tests)
- [ ] Update CHANGELOG.md
- [ ] Update TODO.md
- [ ] Run full test suite
- [ ] Commit and push

## Success Criteria

- [ ] Overall health score calculation working
- [ ] All 3 alert levels (CRITICAL/WARNING/INFO) triggering correctly
- [ ] Weekly health reports generating with trends
- [ ] At least 3 automated remediation actions implemented
- [ ] CLI commands functional and tested
- [ ] 90%+ test coverage on monitoring modules
- [ ] No regressions in existing tests
- [ ] Documentation updated

## Expected Impact

**Before:**
- Users discover problems only when quality severely degraded
- No visibility into system health trends
- Manual cleanup required
- Silent degradation leads to abandonment

**After:**
- Proactive alerts catch issues early
- Clear visibility into health metrics and trends
- Automated remediation for common issues
- Weekly reports keep users informed
- Early warning system prevents Path B abandonment

**Metrics:**
- Path B abandonment probability: -10%
- User confidence: +30%
- Manual intervention required: <10% of users
- Auto-remediation rate: >80% of degradation caught automatically

## Notes

- Keep alert thresholds conservative initially to avoid alert fatigue
- Make automated remediation opt-in by default for safety
- Provide clear explanations for all recommendations
- Use rich formatting for CLI output (tables, colors, icons)
- Consider adding MCP tools for health monitoring (future enhancement)
- Weekly reports could be emailed/logged (future enhancement)

## Future Enhancements

- Real-time monitoring dashboard (web UI)
- Email/notification system for critical alerts
- Machine learning for adaptive thresholds
- Predictive alerts (trend analysis)
- Integration with external monitoring (Prometheus, Grafana)
- Custom alert rules (user-defined thresholds)
