# FEAT-050: Behavioral Reinforcement System

## Overview

A two-component system for iterative behavioral improvement through user feedback:
1. **Feedback Logger** - Captures positive/negative signals from user messages via hook
2. **Retrospective Analyzer** - Periodically analyzes feedback patterns, extracts principles, updates guidance

The system enables Claude Code to learn from user reactions over time, progressively selecting for user-accepted behavior through explicit, auditable rules rather than opaque adjustments.

---

## Motivation

### The Problem

Claude Code receives constant implicit feedback through user reactions:
- "Great job!" → behavior was good
- "You missed the point" → behavior was bad
- "Not quite what I meant" → behavior needs adjustment

This signal currently evaporates. There's no mechanism to:
1. Capture feedback systematically
2. Identify behavioral patterns over time
3. Extract actionable principles
4. Apply learnings to future sessions

### The Solution

Create a feedback loop that:
1. **Captures** sentiment signals during normal operation (low overhead)
2. **Accumulates** feedback entries with contextual information
3. **Analyzes** patterns during periodic retrospective sessions
4. **Updates** explicit behavioral guidance based on findings

### Why This Approach

**Explicit over implicit:** Changes are written rules, not black-box weight updates. Every adjustment is auditable, explainable, and reversible.

**Human in the loop:** Conflicts and significant changes require user approval. The system suggests; the user decides.

**Mirrors human expertise development:** Accumulate experience → periodic reflection → update mental models. Natural and interpretable.

---

## System Architecture

### Component Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     Normal Operation                            │
│                                                                 │
│   User Message ──▶ feedback_detector.sh (hook)                  │
│                           │                                     │
│                           ▼                                     │
│                    Keyword match? ───no───▶ (nothing)           │
│                           │                                     │
│                          yes                                    │
│                           │                                     │
│                           ▼                                     │
│              Append to feedback_log.jsonl                       │
│              (with last 5 actions as context)                   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘

                    ... time passes ...

┌─────────────────────────────────────────────────────────────────┐
│                   Retrospective Session                         │
│                                                                 │
│   User runs /retro                                              │
│           │                                                     │
│           ▼                                                     │
│   Read feedback_log.jsonl                                       │
│   Read LEARNED_PRINCIPLES.md                                    │
│   Read CLAUDE.md                                                │
│           │                                                     │
│           ▼                                                     │
│   Filter false positives (keywords matched but not feedback)    │
│           │                                                     │
│           ▼                                                     │
│   Analyze patterns in genuine feedback                          │
│           │                                                     │
│           ▼                                                     │
│   Generate candidate principles                                 │
│           │                                                     │
│           ▼                                                     │
│   Check for conflicts with existing principles                  │
│           │                                                     │
│           ▼                                                     │
│   ┌─── Conflicts exist? ───┐                                    │
│   │                        │                                    │
│  yes                      no                                    │
│   │                        │                                    │
│   ▼                        ▼                                    │
│   Present to user     Update LEARNED_PRINCIPLES.md              │
│   for decision        Log to retro_history.md                   │
│   │                        │                                    │
│   ▼                        │                                    │
│   Update based on          │                                    │
│   user decision            │                                    │
│   │                        │                                    │
│   └────────────────────────┘                                    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## File Structure

### New Files to Create

```
.claude/
├── hooks/
│   └── feedback_detector.sh          # Hook script for sentiment detection
├── feedback/
│   ├── feedback_log.jsonl            # Raw feedback entries (append-only)
│   └── retro_history.md              # Audit trail of retrospective sessions
└── commands/
    └── retro.md                      # Slash command to trigger analysis

Project root:
└── LEARNED_PRINCIPLES.md             # Extracted behavioral rules
```

### Files to Modify

```
.claude/
└── settings.json                     # Add hook registration

Project root:
└── CLAUDE.md                         # Add reference to LEARNED_PRINCIPLES.md
```

---

## Component 1: Feedback Detection Hook

### Purpose

Detect sentiment signals in user messages and log them with context. Operates on every `UserPromptSubmit` event.

### File: `.claude/hooks/feedback_detector.sh`

### Trigger Configuration

Add to `.claude/settings.json`:
```json
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "command": ".claude/hooks/feedback_detector.sh",
        "timeout": 5000
      }
    ]
  }
}
```

### Detection Strategy: Keyword Regex (Over-Sensitive)

**Design Decision:** Use simple keyword matching that intentionally over-triggers. Accept false positives at capture time; the retrospective analyzer filters them out. This keeps the hook fast and simple.

**Rationale:**
- Hook runs on every user message → must be fast
- Analysis runs infrequently → can afford more computation
- False positives are harmless (filtered during analysis)
- False negatives lose valuable signal (worse outcome)

### Keyword Lists

#### Positive Signals
```
great|perfect|exactly|excellent|nice|good job|well done|thanks|thank you|
love it|awesome|wonderful|brilliant|fantastic|spot on|nailed it|
that's it|yes!|correct|right|helpful|useful|works|working|fixed|solved
```

#### Negative Signals
```
wrong|broke|broken|missed|not what|frustrat|stuck|bad|fail|didn't work|
doesn't work|not right|incorrect|mistake|error|problem|issue|confused|
off track|lost|no|nope|ugh|sigh|annoying|slow|useless|unhelpful
```

#### Corrective Signals
```
actually|not quite|I meant|try again|instead|rather|let me clarify|
what I wanted|should be|supposed to|meant to|correction|rephrase|
different|other|another way|misunderstand|misunderstood
```

### Hook Logic (Pseudocode)

```bash
#!/bin/bash

# Read user message from stdin (Claude Code passes this to hooks)
USER_MESSAGE=$(cat)

# Define patterns
POSITIVE_PATTERN="great|perfect|exactly|excellent|nice|good job|well done|thanks|thank you|love it|awesome|wonderful|brilliant|fantastic|spot on|nailed it|that's it|yes!|correct|right|helpful|useful|works|working|fixed|solved"
NEGATIVE_PATTERN="wrong|broke|broken|missed|not what|frustrat|stuck|bad|fail|didn't work|doesn't work|not right|incorrect|mistake|error|problem|issue|confused|off track|lost|no|nope|ugh|sigh|annoying|slow|useless|unhelpful"
CORRECTIVE_PATTERN="actually|not quite|I meant|try again|instead|rather|let me clarify|what I wanted|should be|supposed to|meant to|correction|rephrase|different|other|another way|misunderstand|misunderstood"

# Check for matches (case-insensitive)
SENTIMENT=""
if echo "$USER_MESSAGE" | grep -iE "$POSITIVE_PATTERN" > /dev/null; then
    SENTIMENT="positive"
elif echo "$USER_MESSAGE" | grep -iE "$NEGATIVE_PATTERN" > /dev/null; then
    SENTIMENT="negative"
elif echo "$USER_MESSAGE" | grep -iE "$CORRECTIVE_PATTERN" > /dev/null; then
    SENTIMENT="corrective"
fi

# If sentiment detected, log it
if [ -n "$SENTIMENT" ]; then
    # Get timestamp
    TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

    # Get session ID from environment (Claude Code provides this)
    SESSION_ID="${CLAUDE_SESSION_ID:-unknown}"

    # Escape user message for JSON
    ESCAPED_MESSAGE=$(echo "$USER_MESSAGE" | jq -Rs '.')

    # Create log entry
    LOG_ENTRY=$(cat <<EOF
{"timestamp": "$TIMESTAMP", "session_id": "$SESSION_ID", "sentiment": "$SENTIMENT", "user_message": $ESCAPED_MESSAGE}
EOF
)

    # Append to feedback log
    echo "$LOG_ENTRY" >> .claude/feedback/feedback_log.jsonl
fi

# Always exit successfully (don't block user input)
exit 0
```

### Context via Activity Log

**Problem:** The hook runs before Claude processes the message. It doesn't have access to "what Claude was doing" because Claude hasn't responded yet.

**Solution:** Context is obtained from `.claude/logs/CLAUDE_LOGS.jsonl`, which records all tool usage (Edit, Write, Bash, Read, Grep, Glob), task delegations, and user prompts with timestamps. During `/retro` analysis, Claude correlates feedback timestamps with preceding activity log entries to understand what was happening when feedback was given.

This keeps the feedback log minimal (just the signal) while maintaining full context availability.

### Output Format

Each feedback entry in `.claude/feedback/feedback_log.jsonl`:

```json
{
  "timestamp": "2025-11-25T18:15:00Z",
  "session_id": "3e1cfa90",
  "sentiment": "positive",
  "user_message": "Great, that's exactly what I needed!"
}
```

---

## Component 2: Feedback Log Storage

### File: `.claude/feedback/feedback_log.jsonl`

### Format: JSON Lines (JSONL)

One JSON object per line, append-only. Efficient for streaming writes, easy to parse.

### Entry Schema

```typescript
interface FeedbackEntry {
  // When the feedback was captured
  timestamp: string;  // ISO 8601 format

  // Session identifier for grouping
  session_id: string;

  // Detected sentiment category
  sentiment: "positive" | "negative" | "corrective";

  // The actual user message (for analysis)
  user_message: string;
}
```

Context is obtained separately from `.claude/logs/CLAUDE_LOGS.jsonl` during `/retro` analysis by correlating timestamps.

### Example Entries

```jsonl
{"timestamp": "2025-11-25T10:15:00Z", "session_id": "abc123", "sentiment": "positive", "user_message": "Perfect, that's exactly what I needed"}
{"timestamp": "2025-11-25T10:45:00Z", "session_id": "abc123", "sentiment": "negative", "user_message": "No, you completely missed the point. I wanted the function to return early."}
{"timestamp": "2025-11-25T14:20:00Z", "session_id": "def456", "sentiment": "corrective", "user_message": "Actually I meant the other config file, not this one"}
{"timestamp": "2025-11-25T16:30:00Z", "session_id": "ghi789", "sentiment": "positive", "user_message": "Great job on the refactoring!"}
```

### Storage Considerations

**Size estimate:**
- ~500 bytes per entry average
- ~10 feedback signals per day (estimate)
- ~5KB per day, ~150KB per month, ~1.8MB per year
- Very manageable; no rotation needed for years

**Backup:** Include in `.claude/` backup strategy if implemented.

**Privacy:** Contains user messages. Consider implications if synced or shared.

---

## Component 3: Retrospective Slash Command

### File: `.claude/commands/retro.md`

### Purpose

Trigger a retrospective analysis session where Claude:
1. Reads accumulated feedback
2. Filters false positives
3. Identifies behavioral patterns
4. Generates candidate principles
5. Checks for conflicts
6. Updates guidance (with user approval for conflicts)

### Slash Command Definition

```markdown
---
description: Run a behavioral retrospective to analyze feedback and extract principles
---

You are conducting a behavioral retrospective session. Your goal is to analyze accumulated user feedback and extract actionable principles to improve future behavior.

## Step 1: Load Data

Read the following files:
1. `.claude/feedback/feedback_log.jsonl` - Accumulated feedback entries
2. `LEARNED_PRINCIPLES.md` - Existing behavioral principles (if exists)
3. `CLAUDE.md` - Core behavioral guidance

If feedback_log.jsonl doesn't exist or is empty, inform the user there's no feedback to analyze and exit.

## Step 2: Filter False Positives

For each feedback entry, determine if it represents genuine feedback about your behavior or a false positive from keyword matching.

**Genuine feedback indicators:**
- Message is a direct reaction to something you did
- Message contains evaluation of your output/behavior
- Message expresses satisfaction or dissatisfaction with results

**False positive indicators:**
- Keywords appear in a different context (e.g., "great" in "a great number of")
- Message is asking a new question that happens to contain trigger words
- Message is about external systems, not your behavior

Create two lists:
- `genuine_feedback`: Entries that are actual behavioral feedback
- `filtered_out`: Entries that were false positives (log these for transparency)

Report: "Analyzed X entries: Y genuine feedback, Z filtered as false positives"

## Step 3: Categorize and Analyze Patterns

Group genuine feedback by sentiment:
- **Positive signals:** What behaviors earned praise?
- **Negative signals:** What behaviors caused frustration?
- **Corrective signals:** What misunderstandings occurred?

For each category, look for patterns:
- Are there clusters around specific action types? (editing, searching, explaining, etc.)
- Are there clusters around specific contexts? (config files, tests, documentation, etc.)
- Are there repeated themes across multiple sessions?

**Pattern threshold:** Only consider patterns with 2+ supporting data points. Single instances are anecdotal, not patterns.

Report your findings:
- "Found N patterns in positive feedback: [list]"
- "Found N patterns in negative feedback: [list]"
- "Found N patterns in corrective feedback: [list]"

## Step 4: Generate Candidate Principles

For each identified pattern, draft a candidate principle:

**Principle format:**
```markdown
### LP-XXX: [Short descriptive title]
**Source:** Retro [date] ([N] [sentiment] signals)
**Pattern:** [What behavior pattern was identified]
**Rule:** [Specific, actionable guidance]
**Rationale:** [Why this matters, based on feedback]
```

**Good principles are:**
- Specific: "When editing config files, read the entire file first" not "Be careful with files"
- Actionable: Clear guidance on what to do differently
- Justified: Tied to actual feedback, not speculation
- Scoped: Apply to identifiable situations, not everything

**Avoid:**
- Over-generalizing from single data points
- Principles that conflict with core CLAUDE.md guidance
- Vague advice ("try harder", "be more careful")
- Principles for situations that won't recur

## Step 5: Check for Conflicts

Compare each candidate principle against:
1. Existing principles in `LEARNED_PRINCIPLES.md`
2. Core guidance in `CLAUDE.md`

**Conflict types:**
- **Direct contradiction:** New rule says X, existing rule says not-X
- **Tension:** New rule might interfere with existing rule in some cases
- **Redundancy:** New rule is essentially the same as existing rule

For each conflict, prepare:
- What the new principle says
- What it conflicts with
- Why the new principle is motivated (the feedback that led to it)
- Options for resolution

## Step 6: Present Findings and Get Approval

Present to the user:

### Summary
- Total feedback entries analyzed: X
- Genuine feedback after filtering: Y
- Patterns identified: Z
- Candidate principles generated: N

### Candidate Principles
[List each candidate with its justification]

### Conflicts (if any)
[For each conflict, present the dilemma and ask for user decision]

### Proposed Actions
1. Add principle LP-XXX: [title]
2. Add principle LP-YYY: [title]
3. [For conflicts] Awaiting your decision on: [conflict description]

Ask: "Do you approve these changes? For conflicts, please indicate your preference."

## Step 7: Apply Updates

After user approval:

1. **Update LEARNED_PRINCIPLES.md:**
   - Add new principles with unique IDs (LP-XXX format)
   - Increment from highest existing ID
   - If file doesn't exist, create it with header

2. **Update retro_history.md:**
   - Log this retro session
   - Include: date, entries analyzed, patterns found, principles added, conflicts resolved

3. **Mark feedback as processed:**
   - Add `"processed": true` to processed entries (or move to archive)

4. **Report completion:**
   - "Retrospective complete. Added N principles. See LEARNED_PRINCIPLES.md for details."

## Error Handling

- If feedback log doesn't exist: "No feedback log found. Feedback will accumulate as you work. Run /retro again after some sessions."
- If no genuine feedback after filtering: "No actionable feedback found. The X entries were false positives from keyword matching."
- If no patterns meet threshold: "Not enough data to identify patterns yet. Continue working and run /retro again after more feedback accumulates."
```

---

## Component 4: Learned Principles File

### File: `LEARNED_PRINCIPLES.md`

### Purpose

Store behavioral principles extracted from feedback analysis. These are explicitly learned adjustments, separate from core guidance in CLAUDE.md.

### File Structure

```markdown
# Learned Principles

Behavioral adjustments derived from user feedback analysis.
This file is updated by `/retro` sessions and should be referenced alongside CLAUDE.md.

**Last updated:** [date]
**Total retrospectives:** [count]
**Active principles:** [count]

---

## Active Principles

### LP-001: [Title]
**Source:** Retro [date] ([N] [sentiment] signals)
**Pattern:** [What was observed]
**Rule:** [What to do]
**Rationale:** [Why]

### LP-002: [Title]
...

---

## Retired Principles

Principles that were later found unhelpful or superseded.

### LP-000: [Title]
**Retired:** [date]
**Reason:** [Why retired]
**Original rule:** [What it said]

---

## Statistics

| Metric | Value |
|--------|-------|
| Total feedback entries processed | X |
| Genuine feedback (after filtering) | Y |
| Patterns identified | Z |
| Principles generated | N |
| Principles retired | M |
```

### Example Content

```markdown
# Learned Principles

Behavioral adjustments derived from user feedback analysis.
This file is updated by `/retro` sessions and should be referenced alongside CLAUDE.md.

**Last updated:** 2025-11-25
**Total retrospectives:** 3
**Active principles:** 4

---

## Active Principles

### LP-001: Read config files completely before editing
**Source:** Retro 2025-11-20 (3 negative signals)
**Pattern:** User frustrated when edits to config files missed important context that was elsewhere in the file.
**Rule:** Always read the entire config file (JSON, YAML, TOML, INI) before making edits, even if the edit seems localized.
**Rationale:** Config files often have interdependencies. Partial reads led to edits that broke other settings.

### LP-002: Prefer concise explanations unless asked
**Source:** Retro 2025-11-22 (4 positive signals)
**Pattern:** User praised brevity multiple times; no complaints about explanations being too short.
**Rule:** Keep explanations to 2-3 sentences unless the user explicitly asks for more detail or the topic is genuinely complex.
**Rationale:** User values efficiency. Verbose explanations waste time.

### LP-003: Confirm destructive operations before executing
**Source:** Retro 2025-11-23 (2 negative signals)
**Pattern:** User upset when files were deleted or overwritten without warning.
**Rule:** Before any operation that deletes, overwrites, or significantly modifies existing work, briefly state what will be affected and confirm.
**Rationale:** Destructive operations are not easily reversible. A moment of confirmation prevents regret.

### LP-004: Show file paths in search results
**Source:** Retro 2025-11-25 (2 positive signals)
**Pattern:** User appreciated when search results included clickable file paths.
**Rule:** When presenting search results or code references, always include the full file path in a format the user can easily navigate to.
**Rationale:** Makes it easy to jump to the relevant location.

---

## Retired Principles

(None yet)

---

## Statistics

| Metric | Value |
|--------|-------|
| Total feedback entries processed | 47 |
| Genuine feedback (after filtering) | 31 |
| Patterns identified | 6 |
| Principles generated | 4 |
| Principles retired | 0 |
```

---

## Component 5: Retrospective History

### File: `.claude/feedback/retro_history.md`

### Purpose

Audit trail of all retrospective sessions. Enables tracking what changed when, reviewing past decisions, and identifying meta-patterns in the feedback system itself.

### Structure

```markdown
# Retrospective History

Audit trail of behavioral retrospective sessions.

---

## Retro: [DATE]

**Session ID:** [retro-YYYYMMDD-HHMMSS]
**Feedback analyzed:** [N] entries ([X] genuine, [Y] filtered)
**Time range:** [earliest entry date] to [latest entry date]

### Patterns Identified
- [Pattern 1 description]
- [Pattern 2 description]

### Actions Taken
- Added LP-XXX: [title]
- Added LP-YYY: [title]
- Conflict resolved: [description of resolution]

### Filtered Entries (False Positives)
- [N] entries filtered as false positives
- Common false positive triggers: [list]

### User Decisions
- [Any conflicts that required user input and how they were resolved]

---

## Retro: [PREVIOUS DATE]
...
```

### Example Content

```markdown
# Retrospective History

Audit trail of behavioral retrospective sessions.

---

## Retro: 2025-11-25

**Session ID:** retro-20251125-181500
**Feedback analyzed:** 15 entries (11 genuine, 4 filtered)
**Time range:** 2025-11-23 to 2025-11-25

### Patterns Identified
- Positive cluster: Users praised file path inclusion in results (2 instances)
- Negative cluster: None identified this session
- Corrective cluster: Users clarified which file they meant (2 instances, but different files - no pattern)

### Actions Taken
- Added LP-004: Show file paths in search results

### Filtered Entries (False Positives)
- 4 entries filtered as false positives
- Common false positive triggers: "problem" (user describing external problem, not feedback), "thanks" (generic sign-off, not praise)

### User Decisions
- None required (no conflicts)

---

## Retro: 2025-11-23

**Session ID:** retro-20251123-140000
**Feedback analyzed:** 12 entries (9 genuine, 3 filtered)
**Time range:** 2025-11-20 to 2025-11-23

### Patterns Identified
- Negative cluster: Destructive operations without confirmation (2 instances)

### Actions Taken
- Added LP-003: Confirm destructive operations before executing

### Filtered Entries (False Positives)
- 3 entries filtered
- Common false positive triggers: "wrong" (user said "wrong file" referring to their own mistake)

### User Decisions
- None required (no conflicts)

---
```

---

## Integration with CLAUDE.md

### Modification Required

Add a reference to `LEARNED_PRINCIPLES.md` in CLAUDE.md so that Claude knows to consult learned principles.

### Suggested Addition

Add to CLAUDE.md in the "Essential Files" or "Critical Rules" section:

```markdown
### Learned Behavioral Principles

In addition to the guidance in this file, consult `LEARNED_PRINCIPLES.md` for behavioral adjustments derived from user feedback analysis.

These principles are:
- Extracted from accumulated positive/negative feedback
- Updated via `/retro` retrospective sessions
- Auditable and reversible

If a learned principle conflicts with guidance in this file, CLAUDE.md takes precedence unless the learned principle was explicitly approved to override.
```

---

## Implementation Phases

### Phase 1: Feedback Logging Infrastructure
**Estimated effort:** 2-3 hours

1. Create directory structure:
   ```
   .claude/feedback/
   .claude/commands/
   ```

2. Create feedback_detector.sh hook with keyword matching

3. Update .claude/settings.json to register the hook

4. Test: Send messages with trigger keywords, verify entries appear in feedback_log.jsonl

**Deliverables:**
- `.claude/hooks/feedback_detector.sh`
- `.claude/feedback/` directory
- Updated `.claude/settings.json`

### Phase 2: Retrospective Command
**Estimated effort:** 3-4 hours

1. Create retro.md slash command with full analysis logic

2. Create LEARNED_PRINCIPLES.md template

3. Create retro_history.md template

4. Test: Run /retro with sample feedback, verify principle extraction works

**Deliverables:**
- `.claude/commands/retro.md`
- `LEARNED_PRINCIPLES.md` (template)
- `.claude/feedback/retro_history.md` (template)

### Phase 3: Integration and Polish
**Estimated effort:** 1-2 hours

1. Update CLAUDE.md to reference LEARNED_PRINCIPLES.md

2. Add conflict detection and user prompting logic

3. Test end-to-end: Accumulate feedback → run retro → verify principles added

4. Document usage in appropriate guide

**Deliverables:**
- Updated `CLAUDE.md`
- End-to-end tested system
- Usage documentation

---

## Design Decisions Summary

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Detection method | Keyword regex (over-sensitive) | Fast hook execution; filter noise during analysis |
| Context depth | Last 5 actions | Rich attribution without bloat |
| Retro trigger | Manual (`/retro`) | User controls reflection timing |
| Principle format | Contextual or prescriptive | Use whichever fits the pattern |
| Conflict resolution | Human decides | Present options, user chooses |
| Storage format | JSONL | Append-efficient, easy to parse |
| Principle storage | Separate file | Clear provenance, easy audit |

---

## Edge Cases and Considerations

### What if the feedback log gets very large?

**Mitigation:**
- Mark entries as `processed: true` after each retro
- Future retros can optionally skip processed entries
- If needed, archive old entries to `.claude/feedback/archive/`

### What if learned principles become stale?

**Mitigation:**
- Principles include source date
- During retro, optionally review old principles against recent feedback
- Retire principles that no longer seem relevant

### What if the user never runs /retro?

**Impact:** Feedback accumulates but is never analyzed. No harm, but no benefit either.

**Mitigation:**
- Periodic reminder in CLAUDE.md to run /retro
- Could add an automated suggestion after N feedback entries

### What if conflicts can't be resolved?

**Mitigation:**
- User always has final say
- Can defer decision: "Keep both for now, revisit later"
- Can retire one principle in favor of another

### What about privacy?

**Consideration:** Feedback log contains user messages.

**Mitigation:**
- Keep in `.claude/` which is typically gitignored
- Document that this file contains conversation excerpts
- User can delete feedback_log.jsonl at any time

### What if the keyword detector has too many false positives?

**Mitigation:**
- Analysis phase filters them out
- Over time, can tune keyword lists based on filter patterns in retro_history.md
- High false positive rate noted in retro history enables refinement

---

## Future Enhancements

### Automatic Retro Suggestions
After N feedback entries accumulate, suggest running /retro:
"You have 15 unprocessed feedback entries. Consider running /retro to analyze patterns."

### Sentiment Confidence Scoring
Instead of binary keyword matching, use a lightweight scoring system:
- Multiple positive keywords = higher confidence
- Keywords in context (sentence structure) = higher confidence
- Log confidence score; filter low-confidence during analysis

### Cross-Session Pattern Detection
Look for patterns that span multiple sessions:
- "User consistently prefers X across 5 sessions"
- Stronger signal than single-session patterns

### Principle Effectiveness Tracking
After adding a principle, track whether related negative feedback decreases:
- "LP-003 added on Nov 23. Destructive operation complaints: 2 before, 0 after."

### Integration with Memory System
Store principles in the memory server for semantic search:
- "What have I learned about config file editing?"
- Could surface relevant principles proactively

---

## Testing Strategy

### Unit Tests

1. **Keyword detection:** Verify each keyword triggers correctly
2. **JSONL parsing:** Verify log entries are valid JSON
3. **False positive filtering:** Test known false positive patterns
4. **Principle ID generation:** Verify unique, incrementing IDs

### Integration Tests

1. **End-to-end flow:** Send feedback → run retro → verify principle created
2. **Conflict detection:** Add conflicting principle → verify user prompted
3. **History logging:** Run retro → verify retro_history.md updated

### Manual Testing

1. **Real usage:** Use Claude Code normally for a day, run retro, evaluate results
2. **Edge cases:** Test with empty log, single entry, all false positives
3. **Conflict scenarios:** Deliberately create conflicts, verify handling

---

## Success Criteria

1. **Feedback is captured:** Messages with sentiment keywords appear in feedback_log.jsonl
2. **False positives are filtered:** /retro correctly identifies non-feedback entries
3. **Patterns are identified:** /retro surfaces genuine behavioral patterns
4. **Principles are actionable:** Generated principles are specific and useful
5. **Conflicts are handled:** User is prompted for conflicting principles
6. **History is maintained:** retro_history.md provides clear audit trail
7. **System is non-intrusive:** Normal operation unaffected by feedback logging

---

## Open Questions

1. **How should context be reconstructed during analysis?** Current plan is deferred population, but specifics TBD.

2. **Should there be a "feedback decay" where old feedback matters less?** Current thinking: no, because retro recency handles this naturally.

3. **What's the right threshold for pattern detection?** Currently 2+ instances. May need tuning.

4. **Should principles have expiration dates?** Could add "review after 30 days" metadata.

---

## References

- Conversation designing this system: 2025-11-25
- Related: CLAUDE_JOURNAL.md (manual reflection system)
- Related: Hook system documentation

---

## Changelog

| Date | Change |
|------|--------|
| 2025-11-25 | Initial planning document created |
