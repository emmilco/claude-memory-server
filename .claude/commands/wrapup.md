---
description: Write a session summary before ending
---

You are wrapping up this session. Write a summary journal entry to `CLAUDE_JOURNAL.md`.

## Instructions

1. **Read the current journal** to see the format and recent entries:
   - File: `CLAUDE_JOURNAL.md`

2. **Reflect on this session** and write an entry with this format:

```markdown
### [YYYY-MM-DD HH:MM] | [session_id] | SESSION_SUMMARY

**Duration:** [estimate based on timestamps]
**Main work:** [1-2 sentence summary of what was accomplished]

**What went well:**
- [bullet points]

**What went poorly or was difficult:**
- [bullet points, or "Nothing notable" if smooth session]

**Open threads:**
- [anything left incomplete or worth noting for next session]
```

3. **Be honest and specific:**
   - Don't just say "everything went well" - note specific wins
   - If you got stuck, made mistakes, or had to backtrack, note that
   - If the user seemed frustrated at any point, reflect on why
   - Open threads help future sessions pick up where you left off

4. **Append the entry** to `CLAUDE_JOURNAL.md`

5. **Brief confirmation** to user: "Session summary added to CLAUDE_JOURNAL.md"

## Example Entry

```markdown
### 2025-11-25 19:30 | 3e1cfa90 | SESSION_SUMMARY

**Duration:** ~90 minutes
**Main work:** Designed and implemented behavioral reinforcement system (FEAT-050)

**What went well:**
- Collaborative design discussion before implementation - user engaged and provided clear direction
- Incremental implementation with testing at each step
- Quick debugging of hook JSON escaping issue

**What went poorly or was difficult:**
- Initial over-engineering of context capture (simplified after discussion)
- Had to restart session for hook settings to take effect (expected but caused brief confusion)

**Open threads:**
- Keyword lists may need tuning based on false positive rates
- No negative feedback captured yet to test that flow
```
