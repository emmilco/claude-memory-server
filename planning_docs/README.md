# Planning Documents

This folder contains detailed planning and implementation documents for tasks tracked in `TODO.md`.

## Purpose
- Keep detailed implementation plans separate from the main TODO list
- Maintain work continuity across multiple sessions
- Document decisions, code snippets, and progress
- Preserve implementation history for future reference

## File Naming Convention
Files must be named with their TODO ID prefix:
```
{ID}_{description}.md
```

Examples:
- `TEST-001_cli_commands_testing.md`
- `FEAT-002_retrieval_gate_implementation.md`
- `BUG-003_typescript_parser_fix.md`

## ID Format
- `TEST-XXX` - Testing tasks
- `FEAT-XXX` - Feature implementations
- `BUG-XXX` - Bug fixes
- `REF-XXX` - Refactoring tasks
- `PERF-XXX` - Performance optimizations
- `DOC-XXX` - Documentation tasks

## Document Template
Each planning document should include:
1. TODO Reference (ID and description)
2. Objective (clear goal statement)
3. Current State (what exists now)
4. Implementation Plan (step-by-step)
5. Progress Tracking (checklist)
6. Notes & Decisions (important findings)
7. Test Cases (verification approach)
8. Code Snippets (relevant examples)

See `TEST-001_cli_commands_testing.md` for a complete example.

## Usage Guidelines

### For AI Agents
1. **Before starting any TODO item**, check for existing planning doc
2. **Create planning doc** for any complex task (multiple steps)
3. **Update progress** as you work
4. **Never delete** planning docs (they're historical records)

### Maintaining Consistency
- Keep TODO IDs synchronized between `TODO.md` and planning docs
- Update both files when status changes
- Mark TODO items complete but keep planning docs for reference

## Current Active Plans
- `TEST-001_cli_commands_testing.md` - CLI test coverage improvement

## Archive Policy
Planning documents are never deleted. They serve as:
- Implementation history
- Decision documentation
- Reference for similar future tasks
- Knowledge base for the project