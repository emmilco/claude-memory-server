---
description: Run a behavioral retrospective to analyze user feedback and extract principles
---

You are conducting a behavioral retrospective session. Your goal is to analyze accumulated user feedback and extract actionable principles to improve future behavior.

## Overview

This retrospective analyzes feedback captured from user messages (positive praise, negative criticism, corrective guidance) and extracts behavioral principles that can improve your future performance.

## Step 1: Load Data

Read the following files:

1. `.claude/feedback/feedback_log.jsonl` - Accumulated feedback entries
2. `LEARNED_PRINCIPLES.md` - Existing behavioral principles (if it exists)
3. `CLAUDE.md` - Core behavioral guidance (for conflict checking)

If `feedback_log.jsonl` doesn't exist or is empty, inform the user:
> "No feedback has been captured yet. Feedback is logged automatically as you work. Run `/retro` again after a few sessions."

Then stop.

## Step 2: Parse Feedback Entries

Read all entries from `feedback_log.jsonl`. Each entry has this structure:
```json
{
  "timestamp": "2025-11-25T18:00:00Z",
  "session_id": "abc12345",
  "sentiment": "positive|negative|corrective",
  "user_message": "The actual message from the user"
}
```

To understand what Claude was doing before the feedback, also read `.claude/logs/CLAUDE_LOGS.jsonl` and correlate by timestamp and session_id. Look for TOOL_USE, USER_PROMPT, and TASK_START events preceding each feedback entry.

Create a summary:
- Total entries: X
- By sentiment: Y positive, Z negative, W corrective
- Date range: [earliest] to [latest]

## Step 3: Filter False Positives

The feedback detector uses keyword matching which can produce false positives. For each entry, determine if it represents **genuine behavioral feedback** or a **false positive**.

**Genuine feedback indicators:**
- The message is a direct reaction to something you (Claude) did
- The message evaluates your output, approach, or behavior
- The message expresses satisfaction or dissatisfaction with your results
- Examples: "Great job on that refactor!", "You missed the point", "Actually I meant the config file"

**False positive indicators:**
- The keyword appears in a different context (e.g., "great" in "a great number of files")
- The message is asking a new question that happens to contain trigger words
- The message discusses external systems, not your behavior (e.g., "the build is broken" referring to CI)
- The message is a generic sign-off (e.g., "thanks" at the end of an unrelated request)

Create two lists:
- `genuine_feedback`: Entries that are actual behavioral feedback
- `filtered_out`: Entries identified as false positives

Report:
> "Analyzed X entries: Y identified as genuine feedback, Z filtered as false positives."

If there's no genuine feedback after filtering:
> "No actionable feedback found. The X entries were false positives from keyword matching. Continue working and run `/retro` again later."

Then stop.

## Step 4: Categorize and Identify Patterns

Group genuine feedback by sentiment type:

### Positive Signals
What behaviors earned praise? List each positive feedback entry with:
- The user message
- Your inference of what action/behavior was being praised

### Negative Signals
What behaviors caused frustration? List each negative feedback entry with:
- The user message
- Your inference of what went wrong

### Corrective Signals
What misunderstandings occurred? List each corrective entry with:
- The user message
- Your inference of what the user was clarifying

Now look for **patterns** - recurring themes across multiple entries:
- Are there clusters around specific action types? (editing, searching, explaining, etc.)
- Are there clusters around specific contexts? (config files, tests, documentation, etc.)
- Are there repeated themes across different sessions?

**Pattern threshold:** Only consider patterns with **2 or more** supporting data points. Single instances are anecdotal, not patterns.

Report your findings:
> "Patterns identified:
> - Positive: [list patterns with count]
> - Negative: [list patterns with count]
> - Corrective: [list patterns with count]"

If no patterns meet the threshold:
> "Not enough data to identify reliable patterns yet. Individual feedback noted but no recurring themes found. Continue working and run `/retro` again after more feedback accumulates."

You may still proceed to generate principles from strong individual signals if they seem particularly important.

## Step 5: Generate Candidate Principles

For each identified pattern (or strong individual signal), draft a candidate principle.

**Principle format:**
```markdown
### LP-XXX: [Short descriptive title]
**Source:** Retro [today's date] ([N] [sentiment] signals)
**Pattern:** [What behavioral pattern was observed]
**Rule:** [Specific, actionable guidance - what to do differently]
**Rationale:** [Why this matters, tied to actual feedback]
```

**Good principles are:**
- **Specific:** "When editing config files, read the entire file first" not "Be careful with files"
- **Actionable:** Clear guidance on what to do or avoid
- **Justified:** Tied to actual feedback, not speculation
- **Scoped:** Apply to identifiable situations, not everything

**Avoid generating principles that:**
- Over-generalize from single data points (unless exceptionally strong signal)
- Are vague ("try harder", "be more careful", "pay attention")
- Duplicate existing principles in LEARNED_PRINCIPLES.md
- Contradict core guidance in CLAUDE.md without good reason

## Step 6: Check for Conflicts

Compare each candidate principle against:
1. Existing principles in `LEARNED_PRINCIPLES.md` (if file exists)
2. Core guidance in `CLAUDE.md`

**Conflict types to check:**
- **Direct contradiction:** New rule says X, existing rule says not-X
- **Tension:** New rule might interfere with existing rule in edge cases
- **Redundancy:** New rule essentially duplicates an existing rule (merge instead)

For each conflict found, prepare:
- What the new principle says
- What it conflicts with (quote the conflicting text)
- Why the new principle is motivated (the feedback that led to it)
- Suggested resolution options

## Step 7: Present Findings to User

Present a clear summary using this format:

---

## Retrospective Summary

**Feedback analyzed:** X entries (Y genuine, Z filtered)
**Date range:** [start] to [end]
**Patterns found:** N

### Genuine Feedback Reviewed

**Positive (X entries):**
- [summary of each]

**Negative (Y entries):**
- [summary of each]

**Corrective (Z entries):**
- [summary of each]

### Patterns Identified

1. [Pattern description] (N signals)
2. [Pattern description] (N signals)

### Candidate Principles

[For each candidate principle, show the full formatted principle]

### Conflicts Detected

[If any conflicts, present them here with options]

**Conflict 1:** [New principle] vs [Existing rule]
- New principle motivation: [feedback that led to it]
- Options:
  1. Add new principle (may override existing)
  2. Modify existing principle to incorporate new insight
  3. Skip this principle

Please indicate your preference.

### Proposed Actions

1. Add principle LP-XXX: [title]
2. Add principle LP-YYY: [title]
3. [For conflicts] Awaiting your decision

---

**Ask the user:** "Do you approve adding these principles? For any conflicts, please indicate your preference (1, 2, or 3)."

## Step 8: Apply Approved Changes

After the user approves (or provides conflict resolutions):

### Update LEARNED_PRINCIPLES.md

If the file doesn't exist, create it with this template:
```markdown
# Learned Principles

Behavioral adjustments derived from user feedback analysis.
This file is updated by `/retro` sessions and should be referenced alongside CLAUDE.md.

**Last updated:** [today's date]
**Total retrospectives:** 1
**Active principles:** [count]

---

## Active Principles

[Add approved principles here]

---

## Retired Principles

(None yet)

---

## Statistics

| Metric | Value |
|--------|-------|
| Total feedback entries processed | X |
| Genuine feedback (after filtering) | Y |
| Patterns identified | Z |
| Principles generated | N |
| Principles retired | 0 |
```

If the file exists:
- Update the "Last updated" date
- Increment "Total retrospectives" counter
- Add new principles to "Active Principles" section
- Assign sequential LP-XXX IDs (increment from highest existing)
- Update Statistics table

### Generate Retro Report

Create a detailed report file at `.claude/feedback/reports/retro_[YYYY-MM-DD].md`:

```markdown
# Retrospective Report: [YYYY-MM-DD]

**Generated:** [timestamp]
**Session:** [session_id]
**Feedback analyzed:** [total] entries
**Date range:** [earliest] to [latest]

---

## Feedback Summary

| Sentiment | Count | Genuine | Filtered |
|-----------|-------|---------|----------|
| Positive | X | Y | Z |
| Negative | X | Y | Z |
| Corrective | X | Y | Z |

---

## Genuine Feedback Analyzed

### Positive (N entries)

[For each entry:]
1. **"[user message]"** ([timestamp])
   - Preceding activity: [summary of what Claude was doing]
   - Inference: [what behavior was being praised]

### Negative (N entries)

[Same format, or "(none)" if empty]

### Corrective (N genuine, M filtered)

[Same format, noting filtered entries with reason]

---

## Activity Context (from CLAUDE_LOGS.jsonl)

[Summary of activity during feedback period:]
- X TOOL_USE events (list tool types)
- Y TASK_START events
- Primary activities: [high-level summary]

---

## Patterns Identified

### Pattern 1: [descriptive title]
**Signals:** N entries
**Evidence:** [quotes from feedback]
**Observation:** [what behavioral pattern was identified]

[Repeat for each pattern]

---

## Candidate Principles

[Full formatted principles as specified in Step 5]

---

## Conflicts Detected

[List conflicts and resolutions, or "(none)"]

---

## Actions Taken

- [x] Added LP-XXX: [title]
- [x] Updated LEARNED_PRINCIPLES.md
- [x] Logged to retro_history.md
- [x] Marked N feedback entries as processed

---

## Recommendations for Next Retro

[Observations about data quality, gaps, or suggestions for what to watch for]

---

*Generated by /retro command*
```

Create the reports directory if it doesn't exist: `.claude/feedback/reports/`

### Update retro_history.md

Append a brief summary entry to `.claude/feedback/retro_history.md`:

```markdown
---

## Retro: [today's date]

**Session ID:** retro-[YYYYMMDD-HHMMSS]
**Feedback analyzed:** X entries (Y genuine, Z filtered)
**Time range:** [earliest] to [latest]
**Full report:** `.claude/feedback/reports/retro_[YYYY-MM-DD].md`

### Patterns Identified
- [Pattern 1]
- [Pattern 2]

### Actions Taken
- Added LP-XXX: [title]
- Added LP-YYY: [title]

### User Decisions
- [Any conflict resolutions]
```

### Mark Feedback as Processed

Add `"processed": true` to each entry that was analyzed. You can do this by rewriting the feedback_log.jsonl file with updated entries, or by noting in the retro history which entries were processed (by timestamp range).

### Report Completion

> "Retrospective complete.
> - Added N new principles
> - Processed X feedback entries
> - See LEARNED_PRINCIPLES.md for the full list
>
> Run `/retro` again after more feedback accumulates."

## Error Handling

- **No feedback file:** "No feedback log found at `.claude/feedback/feedback_log.jsonl`. Feedback will accumulate automatically as you work. Run `/retro` again after a few sessions."

- **Empty feedback file:** "The feedback log is empty. No feedback has been captured yet. Run `/retro` again after some work sessions."

- **All entries are false positives:** "Analyzed X entries but all were false positives (keywords in non-feedback context). No actionable feedback to process."

- **No patterns found:** "Found X genuine feedback entries but no recurring patterns. Individual notes recorded. Run `/retro` again after more feedback accumulates."

- **User declines all principles:** "No changes made. Feedback entries remain for future analysis."
