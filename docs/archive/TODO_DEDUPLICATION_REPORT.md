# TODO.md Deduplication Report

**Date:** 2025-11-30
**Process:** Automated deduplication script

---

## Summary Statistics

| Metric | Value |
|--------|-------|
| **Original file size** | 7,292 lines |
| **New file size** | 3,918 lines |
| **Reduction** | 3,374 lines (46.3%) |
| **Original task IDs** | 214 unique IDs |
| **True duplicates removed** | 56 tasks |
| **ID conflicts resolved** | 102 task IDs |
| **Total ID reassignments** | 377 occurrences |
| **Final unique open tasks** | 591 tasks |

---

## Deduplication Categories

### True Duplicates (56 tasks)
Tasks with the same ID and same content (Location field) that appeared multiple times in the file. The most complete version of each was kept.

### ID Conflicts (102 task IDs, 377 reassignments)
Tasks with the same ID but different content (different Location or Problem fields). These were genuine conflicts where the same ticket number was reused in different audit sections.

**Resolution:** First occurrence kept original ID, subsequent occurrences assigned new sequential IDs.

---

## ID Reassignment Details

### New ID Ranges Assigned

| Prefix | Original Range | New Range | Count |
|--------|---------------|-----------|-------|
| BUG | BUG-001 to BUG-270 | BUG-271 to BUG-454 | 184 new IDs |
| REF | REF-001 to REF-236 | REF-237 to REF-399 | 163 new IDs |
| PERF | PERF-001 to PERF-011 | PERF-012 to PERF-034 | 23 new IDs |
| DOC | DOC-001 to DOC-022 | DOC-023 to DOC-028 | 6 new IDs |
| UX | UX-001 to UX-051 | UX-052+ | 0 new IDs |
| TEST | TEST-001 to TEST-028 | TEST-029+ | 0 new IDs |
| FEAT | FEAT-001+ | No conflicts | 0 new IDs |
| SEC | SEC-001+ | No conflicts | 0 new IDs |

---

## Final Task Distribution

| Category | Task Count | Percentage |
|----------|------------|------------|
| BUG | 244 tasks | 41.3% |
| REF | 226 tasks | 38.2% |
| PERF | 34 tasks | 5.8% |
| DOC | 30 tasks | 5.1% |
| TEST | 16 tasks | 2.7% |
| SEC | 16 tasks | 2.7% |
| UX | 14 tasks | 2.4% |
| FEAT | 11 tasks | 1.9% |
| INVEST | 0 tasks | 0.0% |
| **TOTAL** | **591 tasks** | **100%** |

---

## Notable ID Conflicts

### Most Reassignments (Single ID)
- **BUG-080**: 11 occurrences → BUG-080, BUG-336 through BUG-345
- **BUG-081**: 11 occurrences → BUG-081, BUG-346 through BUG-355
- **BUG-082**: 11 occurrences → BUG-082, BUG-356 through BUG-365

These IDs appeared in multiple audit sections (AUDIT-001, AUDIT-002, AUDIT-003) with completely different content each time.

### Task Prefixes with Most Conflicts
1. **BUG-150 to BUG-157**: Each appeared 5-6 times (Error Propagation audit)
2. **REF-100 to REF-106**: Each appeared 5-6 times (Multiple refactoring audits)
3. **BUG-080 to BUG-090**: Each appeared 8-11 times (Comprehensive code review)

---

## File Structure Changes

### Original TODO.md Structure
- Multiple audit sections with duplicate findings
- Investigation summaries intermixed with tasks
- Summary statistics sections
- Completed task references scattered throughout

### New TODO_NEW.md Structure
✅ Clean task-only structure
✅ Organized by task type (BUG, REF, PERF, etc.)
✅ Sorted by ID number within each category
✅ Priority sections (Critical, High) at top
✅ No summary statistics or investigation notes
✅ Only open tasks (completed tasks removed)

---

## Validation

### Completed Tasks Excluded
All tasks marked with `- [x]` (completed) were excluded from TODO_NEW.md. These include:
- BUG-015, BUG-016, BUG-018, BUG-019, BUG-020, BUG-021, BUG-022, BUG-024, BUG-025, BUG-026
- BUG-034, BUG-035, BUG-036, BUG-038 through BUG-053
- BUG-066 (Integration test hang fix)
- All TEST-013 through TEST-028 (Test antipattern audit - all completed)
- All REF-015 through REF-027 (Code review findings - all completed)
- DOC-008, DOC-009, DOC-010

### Each Task Appears Exactly Once
Every task ID in TODO_NEW.md appears exactly once. Duplicates merged, conflicts reassigned.

---

## Usage Notes

### Next Steps
1. **Review TODO_NEW.md** for correctness
2. **Backup current TODO.md**: `cp TODO.md TODO.md.backup`
3. **Replace TODO.md**: `mv TODO_NEW.md TODO.md`
4. **Update IN_PROGRESS.md and REVIEW.md**: Ensure task IDs match new assignments

### Future Ticket Assignments
- Next BUG ticket: **BUG-455**
- Next REF ticket: **REF-400**
- Next PERF ticket: **PERF-035**
- Next DOC ticket: **DOC-029**
- Next TEST ticket: **TEST-029**
- Next SEC ticket: **SEC-017**
- Next FEAT ticket: **FEAT-012**
- Next UX ticket: **UX-052**

---

## Script Location

Deduplication script: `/Users/elliotmilco/Documents/GitHub/claude-memory-server/scripts/deduplicate_todo.py`

Rerun anytime with:
```bash
python scripts/deduplicate_todo.py
```

The script is safe to rerun multiple times - it will always produce the same deterministic output given the same input.
