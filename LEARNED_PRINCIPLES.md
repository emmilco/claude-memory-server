# Learned Principles

Behavioral adjustments derived from user feedback analysis.
This file is updated by `/retro` sessions and should be referenced alongside CLAUDE.md.

**Last updated:** 2025-11-25
**Total retrospectives:** 1
**Active principles:** 3

---

## Active Principles

### LP-001: Discuss Design Before Implementing
**Source:** Retro 2025-11-25 (4 positive signals)
**Pattern:** User praised collaborative design discussions before coding
**Rule:** When building new features or systems, engage in thorough design discussion with the user before writing any code. Present architecture options, ask clarifying questions, and confirm the approach before implementation.
**Rationale:** Multiple instances of praise ("This was such a good session", "that's really awesome", "amazing") came after collaborative design discussions where the user shaped the approach through iterative Q&A before any code was written.

### LP-002: Demonstrate Working Results, Not Just Completion
**Source:** Retro 2025-11-25 (2 positive signals)
**Pattern:** User showed enthusiasm when seeing systems work in real-time
**Rule:** When implementing features, show concrete evidence of functionality rather than just reporting completion. Demonstrate live output, show captured data, or run examples that prove the system works.
**Rationale:** Strong positive reactions ("Hahahaha, that's so cool", "YES!!!!") occurred when the system demonstrated itself working - like seeing the first feedback entry captured during development.

### LP-003: Explain Reasoning Behind Recommendations
**Source:** Retro 2025-11-25 (2 positive signals)
**Pattern:** User appreciated when recommendations came with clear rationale
**Rule:** When presenting options or making recommendations, explain the reasoning behind each choice. Include trade-offs, implications, and why one approach might be preferred over another.
**Rationale:** User responded positively ("that's a good question", "fascinating") when given thorough explanations of design considerations and trade-offs rather than just bare recommendations.

---

## Retired Principles

*Principles that were later found unhelpful or superseded will be moved here.*

---

## Statistics

| Metric | Value |
|--------|-------|
| Total feedback entries processed | 12 |
| Genuine feedback (after filtering) | 8 |
| Patterns identified | 3 |
| Principles generated | 3 |
| Principles retired | 0 |

---

## How This Works

1. **Feedback Capture:** As you interact with Claude, sentiment keywords in your messages trigger automatic logging to `.claude/feedback/feedback_log.jsonl`

2. **Retrospective Analysis:** Running `/retro` analyzes accumulated feedback, filters false positives, identifies patterns, and generates candidate principles

3. **Principle Generation:** Patterns that recur (2+ instances) become candidate principles for your approval

4. **Application:** Approved principles are added to this file and referenced during future sessions

See `planning_docs/FEAT-050_behavioral_reinforcement_system.md` for full documentation.
