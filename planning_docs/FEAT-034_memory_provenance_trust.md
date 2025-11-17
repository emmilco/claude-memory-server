# FEAT-034: Memory Provenance & Trust Signals

## TODO Reference
- TODO.md: "FEAT-034: Memory Provenance & Trust Signals (~2-3 weeks) 🔥🔥🔥🔥"
- Strategic Doc: `planning_docs/STRATEGIC-001_long_term_product_evolution.md` #3

## Objective
Make memory retrieval transparent and trustworthy through comprehensive provenance tracking, relationship graphs, trust signals, and interactive verification.

## Strategic Context
**Problem:** Users lose trust in the system because it's a "black box" - they don't know:
- Why specific results were returned
- Where memories came from
- If memories are still accurate
- When memories conflict with each other

**Impact:** This is a P1 strategic priority that reduces Path B abandonment probability by 15% (20% → 5%).

## Current State
- Memories have basic metadata (created_at, updated_at, importance)
- Usage tracking exists (last_used, use_count)
- No provenance tracking
- No relationship tracking
- No trust signals or explanations
- No verification workflows
- No contradiction detection

## Implementation Plan

### Phase 1: Database Schema & Models (Day 1-2)

#### 1.1 Extend MemoryUnit Model
Add provenance fields to `src/core/models.py`:
```python
class ProvenanceSource(str, Enum):
    USER_EXPLICIT = "user_explicit"  # User directly stated
    CLAUDE_INFERRED = "claude_inferred"  # Claude inferred from conversation
    DOCUMENTATION = "documentation"  # From code docs
    AUTO_CLASSIFIED = "auto_classified"  # Auto-classified category
    IMPORTED = "imported"  # Imported from external source

class MemoryProvenance(BaseModel):
    source: ProvenanceSource
    created_by: str  # "user_statement", "auto_classification", etc.
    created_at: datetime
    last_accessed: Optional[datetime] = None
    access_count: int = 0
    last_confirmed: Optional[datetime] = None
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    verified: bool = False
    conversation_id: Optional[str] = None
    file_context: List[str] = Field(default_factory=list)
```

Add to MemoryUnit:
```python
provenance: MemoryProvenance = Field(default_factory=...)
```

#### 1.2 Create Relationship Tracking
New model in `src/core/models.py`:
```python
class RelationshipType(str, Enum):
    SUPPORTS = "supports"  # Memory A supports/reinforces memory B
    CONTRADICTS = "contradicts"  # Memory A contradicts memory B
    RELATED = "related"  # Memories are related/similar
    SUPERSEDES = "supersedes"  # Memory A replaces memory B

class MemoryRelationship(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    source_memory_id: str
    target_memory_id: str
    relationship_type: RelationshipType
    confidence: float = Field(ge=0.0, le=1.0)
    detected_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    detected_by: str  # "auto", "user", "system"
    notes: Optional[str] = None
```

#### 1.3 Database Schema Updates
**SQLite Tables:**
```sql
-- Add provenance columns to memories table
ALTER TABLE memories ADD COLUMN provenance_source TEXT DEFAULT 'user_explicit';
ALTER TABLE memories ADD COLUMN provenance_created_by TEXT DEFAULT 'user_statement';
ALTER TABLE memories ADD COLUMN provenance_last_confirmed TEXT;
ALTER TABLE memories ADD COLUMN provenance_confidence REAL DEFAULT 0.8;
ALTER TABLE memories ADD COLUMN provenance_verified INTEGER DEFAULT 0;
ALTER TABLE memories ADD COLUMN provenance_conversation_id TEXT;
ALTER TABLE memories ADD COLUMN provenance_file_context TEXT;  -- JSON array

-- Create relationships table
CREATE TABLE IF NOT EXISTS memory_relationships (
    id TEXT PRIMARY KEY,
    source_memory_id TEXT NOT NULL,
    target_memory_id TEXT NOT NULL,
    relationship_type TEXT NOT NULL,
    confidence REAL NOT NULL,
    detected_at TEXT NOT NULL,
    detected_by TEXT NOT NULL,
    notes TEXT,
    FOREIGN KEY (source_memory_id) REFERENCES memories(id) ON DELETE CASCADE,
    FOREIGN KEY (target_memory_id) REFERENCES memories(id) ON DELETE CASCADE
);

CREATE INDEX idx_rel_source ON memory_relationships(source_memory_id);
CREATE INDEX idx_rel_target ON memory_relationships(target_memory_id);
CREATE INDEX idx_rel_type ON memory_relationships(relationship_type);
```

**Qdrant Payload:**
Add provenance fields to payload in both stores.

### Phase 2: Provenance Tracking (Day 3-4)

#### 2.1 Auto-Capture Provenance
Create `src/memory/provenance_tracker.py`:
```python
class ProvenanceTracker:
    """Track and manage memory provenance."""

    async def capture_provenance(
        self,
        content: str,
        source: ProvenanceSource,
        context: Dict[str, Any]
    ) -> MemoryProvenance:
        """Capture provenance metadata for a new memory."""

    async def update_access(self, memory_id: str) -> None:
        """Update last_accessed when memory is retrieved."""

    async def verify_memory(self, memory_id: str, verified: bool) -> None:
        """Mark memory as verified by user."""

    async def calculate_confidence(self, memory: MemoryUnit) -> float:
        """Calculate confidence score based on multiple factors."""
```

#### 2.2 Integrate Provenance Capture
Update `src/core/server.py`:
- Capture provenance when storing memories
- Update last_accessed during retrieval
- Track conversation_id and file_context

### Phase 3: Relationship Graph (Day 5-7)

#### 3.1 Relationship Detection
Create `src/memory/relationship_detector.py`:
```python
class RelationshipDetector:
    """Detect relationships between memories."""

    async def detect_contradictions(
        self,
        new_memory: MemoryUnit,
        existing_memories: List[MemoryUnit]
    ) -> List[MemoryRelationship]:
        """Detect if new memory contradicts existing ones."""

    async def detect_duplicates(
        self,
        new_memory: MemoryUnit,
        similarity_threshold: float = 0.9
    ) -> List[MemoryRelationship]:
        """Detect duplicate/similar memories."""

    async def detect_support(
        self,
        memory_a: MemoryUnit,
        memory_b: MemoryUnit
    ) -> Optional[MemoryRelationship]:
        """Detect if memories support each other."""
```

#### 3.2 Storage Methods
Add to both stores:
```python
async def store_relationship(self, relationship: MemoryRelationship) -> str
async def get_relationships(
    self,
    memory_id: str,
    relationship_type: Optional[RelationshipType] = None
) -> List[MemoryRelationship]
async def delete_relationship(self, relationship_id: str) -> bool
```

### Phase 4: Trust Signals & Explanations (Day 8-10)

#### 4.1 Trust Signal Generator
Create `src/memory/trust_signals.py`:
```python
class TrustSignalGenerator:
    """Generate trust signals and explanations for search results."""

    async def explain_result(
        self,
        memory: MemoryUnit,
        query: str,
        score: float,
        rank: int
    ) -> Dict[str, Any]:
        """Generate 'Why this result?' explanation."""

    async def calculate_trust_score(
        self,
        memory: MemoryUnit
    ) -> float:
        """Calculate overall trust score (0-1)."""

    async def generate_confidence_explanation(
        self,
        confidence: float
    ) -> str:
        """Convert confidence score to human-readable explanation."""
```

Example output:
```python
{
    "why_shown": [
        "Exact semantic match to your query (0.89)",
        "From current project: my-web-app",
        "Accessed 8 times this week (HIGH CONFIDENCE)",
        "You verified this 2 days ago",
        "Related to 3 other error handling memories"
    ],
    "trust_score": 0.92,
    "confidence_level": "excellent",
    "last_verified": "2 days ago",
    "provenance": {
        "source": "user_explicit",
        "age_days": 15
    }
}
```

#### 4.2 Enhanced Search Results
Update `MemoryResult` model:
```python
class MemoryResult(BaseModel):
    memory: MemoryUnit
    score: float
    relevance_reason: Optional[str] = None
    trust_signals: Optional[Dict[str, Any]] = None  # NEW
    explanation: Optional[List[str]] = None  # NEW
```

### Phase 5: Verification Tool (Day 11-13)

#### 5.1 CLI Verification Command
Create `src/cli/verify_command.py`:
```python
async def verify_memories():
    """Interactive verification of memories."""
    # Find memories needing verification
    # Display with context
    # Prompt user for verification
    # Update provenance
```

#### 5.2 Verification Criteria
Memories need verification if:
- confidence < 0.6
- age > 90 days AND not verified
- last_accessed > 60 days ago
- detected contradictions exist

### Phase 6: Contradiction Detection (Day 14-16)

#### 6.1 Contradiction Detector
Enhance `relationship_detector.py`:
```python
async def scan_for_contradictions(
    self,
    category: MemoryCategory = MemoryCategory.PREFERENCE
) -> List[Tuple[MemoryUnit, MemoryUnit, float]]:
    """Scan all memories for contradictions."""

    # Special logic for preferences:
    # - "I prefer X" vs "I prefer Y" (X != Y)
    # - "Always use X" vs "Never use X"
    # - Framework preferences that changed
```

#### 6.2 Contradiction Reporting
Add to verify command:
```bash
$ claude-memory verify --contradictions

CONTRADICTIONS DETECTED
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Your preferences seem to have changed:

OLD (90 days ago): "I prefer Vue.js for frontend"
  • Confidence: 45% (LOW)
  • Last used: 60 days ago

NEW (10 days ago): "I prefer React for frontend"
  • Confidence: 85% (HIGH)
  • Last used: 2 days ago

Which is current?
[1] React (archive the Vue preference)
[2] Vue (archive the React preference)
[3] Both (I use different frameworks for different projects)
[4] Neither (I've moved to something else)
```

### Phase 7: Integration & Testing (Day 17-21)

#### 7.1 Integration Points
- Update store() to capture provenance
- Update retrieve() to add trust signals
- Add relationship detection on memory creation
- Periodic background jobs for contradiction scanning

#### 7.2 Test Coverage
Create comprehensive tests:
- `tests/unit/test_provenance_tracker.py`
- `tests/unit/test_relationship_detector.py`
- `tests/unit/test_trust_signals.py`
- `tests/unit/test_verify_command.py`
- `tests/integration/test_provenance_integration.py`

Target: 85%+ coverage on all new modules

## Files to Create
- `src/core/models.py` - Add provenance models
- `src/memory/provenance_tracker.py` - Provenance tracking logic
- `src/memory/relationship_detector.py` - Relationship detection
- `src/memory/trust_signals.py` - Trust signal generation
- `src/cli/verify_command.py` - Verification CLI
- Migration script for database schema

## Files to Modify
- `src/core/server.py` - Integrate provenance capture and trust signals
- `src/store/sqlite_store.py` - Add schema and methods
- `src/store/qdrant_store.py` - Add payload fields and methods
- `src/cli/__init__.py` - Add verify command

## Testing Strategy
1. Unit tests for each new module
2. Integration tests for end-to-end workflows
3. Test provenance capture during store()
4. Test trust signal generation during retrieve()
5. Test contradiction detection
6. Test verification workflows

## Success Criteria
- [  ] Provenance tracked for all new memories
- [  ] Relationship graph functional
- [  ] Trust signals displayed in search results
- [  ] Verification tool working
- [  ] Contradiction detection accurate
- [  ] 85%+ test coverage
- [  ] All tests passing
- [  ] Documentation updated

## Migration Strategy
For existing memories:
- Set default provenance values
- confidence = 0.5 (medium, since unverified)
- source = "user_explicit" (assume user-created)
- created_by = "legacy"
- verified = False

## Notes
- Keep trust signals optional to avoid overwhelming users
- Make verification tool gentle, not annoying
- Start with conservative contradiction detection (high precision, lower recall)
- Allow users to dismiss false positive contradictions
- Store dismissals to avoid re-alerting

## Progress Tracking
- [  ] Phase 1: Database Schema & Models
- [  ] Phase 2: Provenance Tracking
- [  ] Phase 3: Relationship Graph
- [  ] Phase 4: Trust Signals & Explanations
- [  ] Phase 5: Verification Tool
- [  ] Phase 6: Contradiction Detection
- [  ] Phase 7: Integration & Testing
