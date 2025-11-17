# FEAT-035: Intelligent Memory Consolidation

## TODO Reference
- TODO.md: "FEAT-035: Intelligent Memory Consolidation (~2-3 weeks) 🔥🔥🔥"
- Strategic Doc: `planning_docs/STRATEGIC-001_long_term_product_evolution.md` #4

## Objective
Automatically detect and merge duplicate/similar memories to prevent noise accumulation and maintain database quality over time.

## Strategic Context
**Problem:** Without automatic consolidation:
- Duplicate memories accumulate (8% after 1 month, 30%+ after 6 months)
- Contradictory preferences cause confusion
- Noise ratio grows from 5% → 50%+ over time
- Search quality degrades significantly

**Impact:** This is a P1 strategic priority that reduces noise by 40% and catches preference drift.

## Current State
- No duplicate detection
- No automatic merging
- No contradiction alerts
- Users must manually clean up duplicates
- Noise accumulates unchecked

## Implementation Plan

### Core Components

#### 1. Duplicate Detector (`src/memory/duplicate_detector.py`)
Detects similar memories using semantic similarity:

```python
class DuplicateDetector:
    async def find_duplicates(
        self,
        memory: MemoryUnit,
        threshold: float = 0.85
    ) -> List[Tuple[MemoryUnit, float]]:
        """Find similar memories above threshold."""
```

**Thresholds:**
- High confidence (>0.95): Auto-merge safe
- Medium confidence (0.85-0.95): Prompt user
- Low confidence (0.75-0.85): Flag as "related"

#### 2. Consolidation Engine (`src/memory/consolidation_engine.py`)
Merges memories intelligently:

```python
class ConsolidationEngine:
    async def merge_memories(
        self,
        canonical: MemoryUnit,
        duplicates: List[MemoryUnit],
        strategy: MergeStrategy
    ) -> MemoryUnit:
        """Merge duplicates into canonical memory."""

    async def detect_contradictions(
        self,
        category: MemoryCategory = MemoryCategory.PREFERENCE
    ) -> List[Tuple[MemoryUnit, MemoryUnit]]:
        """Find contradictory preferences."""
```

**Merge Strategies:**
1. **Preference Merging:** Keep most recent, strongest signal
2. **Fact Deduplication:** Merge similar facts, keep most informative
3. **Event Compression:** Combine related events into summary

#### 3. Background Jobs (`src/memory/consolidation_jobs.py`)
Scheduled consolidation tasks:

- **Daily (2 AM):** Auto-merge high-confidence duplicates (>0.95)
- **Weekly:** Surface medium-confidence duplicates for user review
- **Monthly:** Full contradiction scan

#### 4. User Prompts (`src/cli/consolidate_command.py`)
Interactive consolidation workflows:

```bash
$ claude-memory consolidate --dry-run
$ claude-memory consolidate --auto  # Auto-merge high-confidence
$ claude-memory consolidate --interactive  # Review each merge
```

### Contradiction Detection

Special logic for preferences:

```python
# Example contradictions:
"I prefer Vue.js for frontend" (90 days ago)
vs
"I prefer React for frontend" (10 days ago)

# Detection:
1. Extract preference subject (frontend framework)
2. Extract preference object (Vue vs React)
3. Check for mutual exclusivity
4. Flag if both ACTIVE and time gap > 30 days
```

### Undo Mechanism

Track merges for rollback:

```sql
CREATE TABLE merge_history (
    merge_id TEXT PRIMARY KEY,
    canonical_id TEXT,
    merged_ids TEXT,  -- JSON array
    merge_timestamp TEXT,
    merge_strategy TEXT,
    confidence REAL
);
```

## Files to Create

### Core Implementation
- `src/memory/duplicate_detector.py` - Similarity-based duplicate detection
- `src/memory/consolidation_engine.py` - Merge logic and strategies
- `src/memory/consolidation_jobs.py` - Background job scheduling
- `src/cli/consolidate_command.py` - Interactive CLI for consolidation

### Models & Config
- Add `MergeStrategy` enum to `src/core/models.py`
- Add consolidation config to `src/config.py`
- Create `merge_history` table in SQLite

### Tests
- `tests/unit/test_duplicate_detector.py`
- `tests/unit/test_consolidation_engine.py`
- `tests/integration/test_consolidation_workflow.py`

## Database Schema

```sql
-- Merge history for undo
CREATE TABLE IF NOT EXISTS merge_history (
    merge_id TEXT PRIMARY KEY,
    canonical_memory_id TEXT NOT NULL,
    merged_memory_ids TEXT NOT NULL,  -- JSON array
    merge_timestamp TEXT NOT NULL,
    merge_strategy TEXT NOT NULL,
    confidence REAL NOT NULL,
    performed_by TEXT NOT NULL DEFAULT 'auto',
    FOREIGN KEY (canonical_memory_id) REFERENCES memories(id)
);

CREATE INDEX idx_merge_timestamp ON merge_history(merge_timestamp);
```

## Testing Strategy

1. **Unit Tests:**
   - Duplicate detection with various thresholds
   - Merge strategy correctness
   - Contradiction detection accuracy

2. **Integration Tests:**
   - End-to-end merge workflow
   - Undo mechanism
   - Background job execution

3. **Test Scenarios:**
   - Exact duplicates (content identical)
   - Semantic duplicates (same meaning, different wording)
   - Contradictory preferences with time gaps
   - Event compression
   - Preference drift detection

## Success Criteria

- [  ] Duplicate detector accurately finds similar memories
- [  ] High-confidence duplicates (>0.95) merge automatically
- [  ] Medium-confidence duplicates prompt user appropriately
- [  ] Contradiction detection catches preference conflicts
- [  ] Undo mechanism works correctly
- [  ] Background jobs run on schedule
- [  ] CLI commands functional
- [  ] 85%+ test coverage
- [  ] All tests passing

## Configuration Options

```python
# In src/config.py
enable_auto_consolidation: bool = True
consolidation_high_threshold: float = 0.95  # Auto-merge
consolidation_medium_threshold: float = 0.85  # Prompt user
consolidation_low_threshold: float = 0.75  # Flag as related
consolidation_schedule_daily: str = "02:00"  # 2 AM daily
consolidation_schedule_weekly: str = "SUN:03:00"  # Sunday 3 AM
contradiction_detection_enabled: bool = True
enable_merge_undo: bool = True
merge_undo_retention_days: int = 90
```

## Rollout Plan

### Phase 1: Core Detection (Day 1-3)
- Implement duplicate detector
- Implement similarity clustering
- Basic tests

### Phase 2: Merge Engine (Day 4-7)
- Implement merge strategies
- Add merge history tracking
- Undo mechanism

### Phase 3: Contradiction Detection (Day 8-10)
- Preference contradiction logic
- Fact conflict detection
- User prompts

### Phase 4: Background Jobs (Day 11-13)
- APScheduler integration
- Daily/weekly/monthly jobs
- Job monitoring

### Phase 5: CLI Tools (Day 14-16)
- Consolidate command
- Interactive workflows
- Dry-run support

### Phase 6: Integration & Testing (Day 17-21)
- Comprehensive tests
- Integration with server
- Performance optimization

## Notes

- Start with conservative thresholds to avoid bad merges
- Allow users to dismiss false positive duplicates
- Store dismissals to avoid re-alerting
- Track merge quality metrics for tuning
- Consider user feedback for threshold adjustment

## Progress Tracking

- [ ] Phase 1: Core Detection
- [ ] Phase 2: Merge Engine
- [ ] Phase 3: Contradiction Detection
- [ ] Phase 4: Background Jobs
- [ ] Phase 5: CLI Tools
- [ ] Phase 6: Integration & Testing
