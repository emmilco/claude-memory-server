---
description: Run a behavioral retrospective to analyze user feedback and refine values
---

You are conducting a behavioral retrospective session. Your goal is to analyze accumulated user feedback and refine the VALUES.md file.

## Overview

This retrospective analyzes feedback captured from user messages (positive praise, negative criticism, corrective guidance) and either:
1. Adds calibrations to existing values
2. Proposes new values (rare - only for genuinely new orientations)

## Step 1: Load Data

Read the following files:

1. `.claude/feedback/feedback_log.jsonl` - Accumulated feedback entries
2. `VALUES.md` - Current values and calibrations
3. `CLAUDE_JOURNAL.md` - Work journal with session summaries and META_LEARNING entries
4. `.claude/logs/CLAUDE_LOGS.jsonl` - Activity logs (sample if large)
5. `.claude/feedback/retro_history.md` - Previous retro dates

**Determine the date range:** Check when the last retro was run (from `retro_history.md`). Only analyze entries **since the last retro**.

If `feedback_log.jsonl` doesn't exist or is empty:
> "No feedback has been captured yet. Run `/retro` again after a few sessions."

Then stop.

## Step 2: Parse and Filter

### 2a. Feedback Log
Read entries since last retro. Each entry:
```json
{
  "timestamp": "2025-11-25T18:00:00Z",
  "session_id": "abc12345",
  "sentiment": "positive|negative|corrective",
  "user_message": "The actual message"
}
```

### 2b. Journal Entries
Extract SESSION_SUMMARY and META_LEARNING entries since last retro. These provide the "why" behind feedback.

### 2c. Filter False Positives
The feedback detector over-captures. Filter out:
- Keywords in different context ("great number of files")
- Generic sign-offs ("thanks")
- Discussion of external systems, not Claude behavior

Report: "Analyzed X entries: Y genuine, Z filtered."

If no genuine feedback: "No actionable feedback. Run `/retro` later." Then stop.

## Step 3: Identify Patterns

Group genuine feedback by sentiment. Look for:
- Clusters around action types (editing, searching, debugging)
- Clusters around contexts (tests, config, documentation)
- Repeated themes across sessions

Cross-reference with journal "What went poorly" and META_LEARNING entries.

**Pattern threshold:** 2+ supporting data points, or 1 strong META_LEARNING entry.

## Step 4: Map to Values

For each pattern, determine:

1. **Does it fit an existing value?** → Add as calibration
2. **Is it genuinely new orientation?** → Propose new value (rare)
3. **Is it a process/workflow issue?** → Note for CLAUDE.md, not VALUES.md

Most patterns should become calibrations on existing values, not new values.

### Calibration Format
```markdown
### V-00X: [Value name]
- **[Context]**: [Specific guidance]
```

### New Value Format (rare)
```markdown
### V-00X: [Short name]
[One-sentence orientation statement]
```

## Step 5: Present Findings

---

## Retrospective Summary

**Feedback analyzed:** X entries (Y genuine, Z filtered)
**Date range:** [start] to [end]
**Patterns found:** N

### Patterns Identified

1. [Pattern] (N signals) → Maps to V-00X
2. [Pattern] (N signals) → Maps to V-00Y

### Proposed Changes

**Calibrations to add:**
- V-001: [new calibration]
- V-003: [new calibration]

**New values (if any):**
- V-009: [proposed value]

---

**Ask:** "Do you approve these changes to VALUES.md?"

## Step 6: Apply Changes

After approval:

### Update VALUES.md
- Add approved calibrations under appropriate values
- Add new values (if any)
- Update Value History table

### Update retro_history.md
Append:
```markdown
---

## Retro: [date]

**Feedback analyzed:** X entries (Y genuine)
**Date range:** [start] to [end]

### Changes Made
- Added calibration to V-001: [description]
- Added calibration to V-003: [description]
```

### Report Completion
> "Retrospective complete. Updated VALUES.md with N calibrations."

## Key Differences from Old System

- **Values are stable orientations** - they rarely change
- **Calibrations are context-specific refinements** - these accumulate
- **No LP-XXX IDs** - values use V-XXX, calibrations are bullets under values
- **Simpler format** - one sentence per value, not paragraphs
