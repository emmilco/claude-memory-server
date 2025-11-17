# FEAT-028: Proactive Context Suggestions

## TODO Reference
- TODO.md: "Proactive Context Suggestions (~3-4 days)"
- Analyze conversation context to suggest relevant code/memories
- Pattern matching for similar implementations
- Automatic context injection (high confidence only)
- MCP tool auto-invocation based on conversation

## User Design Decisions

Based on user preferences collected 2025-11-17:

1. **Automation Level**: Automatic with notification
   - System automatically injects context when confident
   - Shows notification: "I found similar code..."
   - Balance of speed and transparency

2. **Trigger Patterns** (all 4 enabled):
   - Implementation requests: "I need to add X"
   - Error debugging: "Why isn't X working?"
   - Code questions: "How does X work?"
   - Refactoring/changes: "Change X to Y"

3. **Low Confidence Handling**: Adaptive threshold
   - Start conservative
   - Learn from user feedback (accepts/ignores suggestions)
   - Adjust threshold based on usage patterns

## Objective

Build a proactive suggestion system that analyzes conversation context and automatically provides relevant code/memory suggestions with minimal intrusion. The system should:
- Detect 4 types of patterns in user messages
- Automatically search and inject context at high confidence (>0.9)
- Show notification about injected context
- Learn from user feedback to improve threshold over time

## Current State

Existing infrastructure:
- `src/memory/conversation_tracker.py` - Tracks conversations and shown context
- `src/router/retrieval_gate.py` - Adaptive gating with metrics
- `src/router/retrieval_predictor.py` - Query utility prediction
- `src/memory/query_expander.py` - Query expansion for better search
- `src/core/server.py` - Main MCP server with all tools

What's missing:
- Pattern detection for conversation analysis
- Suggestion engine with auto-injection
- Feedback tracking for adaptive learning
- MCP tool integration

## Implementation Plan

### Phase 1: Pattern Detection Module ✅
**File**: `src/memory/pattern_detector.py`

```python
class PatternDetector:
    """Detect conversation patterns that suggest relevant context."""

    def detect_patterns(self, message: str) -> List[DetectedPattern]
    # Returns patterns with confidence scores

    # Pattern types:
    # - IMPLEMENTATION_REQUEST: "I need to add X", "implement Y"
    # - ERROR_DEBUGGING: "why isn't X working", "error in Y"
    # - CODE_QUESTION: "how does X work", "what is Y"
    # - REFACTORING_CHANGE: "change X to Y", "refactor Z"
```

Features:
- Regex + keyword-based pattern matching
- Confidence scoring (0-1)
- Extract key entities (what user is asking about)
- Support for multi-pattern detection per message

### Phase 2: Suggestion Engine with Adaptive Learning ✅
**File**: `src/memory/suggestion_engine.py`

```python
class SuggestionEngine:
    """Generate proactive context suggestions with adaptive learning."""

    def __init__(self, config: ServerConfig, store: MemoryStore)

    async def analyze_message(
        self,
        message: str,
        session_id: Optional[str] = None
    ) -> SuggestionResult

    def record_feedback(self, suggestion_id: str, accepted: bool)
    # Track whether user found suggestion useful

    def update_threshold(self)
    # Adjust confidence threshold based on feedback
```

Features:
- Pattern detection using PatternDetector
- Automatic search when patterns detected
- High confidence (>0.9) -> auto-inject
- Medium confidence (0.7-0.9) -> include in footnote
- Low confidence (<0.7) -> skip
- Feedback tracking (implicit: user uses/ignores suggestion)
- Adaptive threshold adjustment (weekly recalibration)

### Phase 3: MCP Tool Integration ✅
**File**: `src/core/server.py` modifications

New MCP tools:
1. `analyze_conversation` - Analyze current message for patterns
2. `get_suggestion_stats` - View suggestion metrics and threshold
3. `provide_feedback` - Explicitly mark suggestion as useful/not useful
4. `set_suggestion_mode` - Enable/disable proactive suggestions

Integration:
- Hook into existing conversation tracker
- Add suggestion engine to server initialization
- Inject suggestions into responses

### Phase 4: Feedback & Adaptive Learning ✅
**File**: `src/memory/feedback_tracker.py`

```python
class FeedbackTracker:
    """Track user feedback on suggestions."""

    def record_suggestion(self, suggestion_id, pattern_type, confidence)
    def record_feedback(self, suggestion_id, accepted, implicit=True)
    def get_acceptance_rate(self, pattern_type) -> float
    def recommend_threshold_adjustment() -> float
```

Features:
- Track suggestions shown vs accepted
- Separate metrics per pattern type
- Calculate optimal threshold (target 70% acceptance)
- Weekly automatic adjustment

### Phase 5: Testing ✅
**Files**:
- `tests/unit/test_pattern_detector.py`
- `tests/unit/test_suggestion_engine.py`
- `tests/unit/test_feedback_tracker.py`
- `tests/integration/test_proactive_suggestions.py`

Test coverage:
- Pattern detection for all 4 types
- Edge cases (no patterns, multiple patterns)
- Confidence scoring accuracy
- Auto-injection behavior
- Adaptive threshold learning
- MCP tool integration

### Phase 6: Documentation ✅
- Update CHANGELOG.md
- Update TODO.md (mark FEAT-028 complete)
- Add docs/proactive_suggestions.md guide
- Update README.md with new MCP tools

## Progress Tracking

- [ ] Phase 1: Pattern Detection Module
- [ ] Phase 2: Suggestion Engine with Adaptive Learning
- [ ] Phase 3: MCP Tool Integration
- [ ] Phase 4: Feedback & Adaptive Learning
- [ ] Phase 5: Testing (85%+ coverage)
- [ ] Phase 6: Documentation

## Technical Design

### Pattern Detection Algorithm

```python
PATTERNS = {
    "IMPLEMENTATION_REQUEST": {
        "triggers": [r"I need to (add|implement|create|build)"],
        "confidence_base": 0.85,
        "search_strategy": "find_similar_code",
    },
    "ERROR_DEBUGGING": {
        "triggers": [r"(why|error|not working|failing|broken)"],
        "confidence_base": 0.90,
        "search_strategy": "search_code + search_memories",
    },
    "CODE_QUESTION": {
        "triggers": [r"(how does|what is|explain|understand)"],
        "confidence_base": 0.75,
        "search_strategy": "search_code",
    },
    "REFACTORING_CHANGE": {
        "triggers": [r"(change|refactor|modify|update|replace)"],
        "confidence_base": 0.80,
        "search_strategy": "search_code",
    },
}
```

### Adaptive Threshold Algorithm

```python
def calculate_optimal_threshold(feedback_history):
    """Calculate optimal threshold based on acceptance rate."""

    # Target: 70% acceptance rate
    TARGET_ACCEPTANCE = 0.70

    # Current acceptance rate
    acceptance_rate = accepted / total_shown

    # Adjust threshold
    if acceptance_rate < TARGET_ACCEPTANCE - 0.1:
        # Too many false positives, increase threshold
        new_threshold = current_threshold + 0.05
    elif acceptance_rate > TARGET_ACCEPTANCE + 0.1:
        # Missing opportunities, decrease threshold
        new_threshold = current_threshold - 0.05
    else:
        # In target range, no change
        new_threshold = current_threshold

    # Clamp to [0.7, 0.95]
    return max(0.70, min(0.95, new_threshold))
```

### Suggestion Notification Format

```
💡 I found similar code that might help:
   - `src/auth/login.py:authenticate()` - User authentication logic
   - `src/api/middleware.py:verify_token()` - Token verification

   Search: "authentication implementation"
   Confidence: 93% (high)
```

## Test Cases

### Unit Tests

1. **Pattern Detection**:
   - ✓ Detect IMPLEMENTATION_REQUEST
   - ✓ Detect ERROR_DEBUGGING
   - ✓ Detect CODE_QUESTION
   - ✓ Detect REFACTORING_CHANGE
   - ✓ Handle no patterns found
   - ✓ Handle multiple patterns in one message
   - ✓ Confidence scoring accuracy

2. **Suggestion Engine**:
   - ✓ Auto-inject at high confidence (>0.9)
   - ✓ Footnote at medium confidence (0.7-0.9)
   - ✓ Skip at low confidence (<0.7)
   - ✓ Format notification correctly
   - ✓ Track shown suggestions
   - ✓ Deduplication with conversation tracker

3. **Feedback Tracker**:
   - ✓ Record feedback correctly
   - ✓ Calculate acceptance rate
   - ✓ Recommend threshold adjustments
   - ✓ Per-pattern metrics

### Integration Tests

1. **End-to-End Flow**:
   - User message → pattern detection → search → injection
   - Feedback recording → threshold adjustment
   - Multiple suggestions in one conversation
   - Session context integration

2. **MCP Tools**:
   - `analyze_conversation` returns suggestions
   - `get_suggestion_stats` shows metrics
   - `provide_feedback` updates learning model
   - `set_suggestion_mode` enables/disables

## Code Snippets

### Pattern Detector Interface

```python
@dataclass
class DetectedPattern:
    """A detected conversation pattern."""
    pattern_type: str  # IMPLEMENTATION_REQUEST, ERROR_DEBUGGING, etc.
    confidence: float  # 0-1
    entities: List[str]  # Extracted entities (e.g., "authentication", "login")
    trigger_text: str  # The text that triggered the pattern
    search_query: str  # Suggested search query
```

### Suggestion Result

```python
@dataclass
class SuggestionResult:
    """Result from suggestion engine analysis."""
    suggestion_id: str
    patterns: List[DetectedPattern]
    should_inject: bool
    search_results: List[MemoryResult]
    notification_text: Optional[str]
    confidence: float
    timestamp: datetime
```

## Dependencies

- Existing conversation_tracker for session management
- Existing search infrastructure (search_code, find_similar_code)
- SQLite for feedback persistence
- No new external dependencies

## Runtime Cost

- **CPU**: +5-10ms per message for pattern detection
- **Memory**: +10-20MB for feedback tracking
- **Storage**: +5-10MB for suggestion history
- **Latency**: +20-50ms when auto-injecting (search time)

## Strategic Priority

**Priority**: High (Tier 2 - High-Impact Core Functionality)

**Impact**:
- Reduces cognitive load on users
- Surfaces hidden gems from codebase
- Improves discoverability of relevant context
- Learns from user behavior over time

**Complexity**: Medium (~600 lines across 4 modules)

## Notes & Decisions

- **Decision**: Use regex + keywords rather than ML for pattern detection
  - Rationale: Faster, more predictable, easier to debug
  - Can upgrade to ML later if needed

- **Decision**: Start with threshold=0.90 for auto-injection
  - Rationale: Conservative start, adjust based on feedback
  - Target acceptance rate: 70%

- **Decision**: Implicit feedback tracking (user uses/ignores suggestion)
  - Rationale: Low friction, no extra user action required
  - Explicit feedback via MCP tool for power users

- **Decision**: Weekly automatic threshold adjustment
  - Rationale: Sufficient data, not too reactive
  - Manual override available via MCP tool

## Next Steps After Completion

- Monitor acceptance rates in production
- Consider ML-based pattern detection for v2
- Add pattern type customization per user
- Consider suggestion ranking (multiple suggestions per message)
