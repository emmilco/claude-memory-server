# REVIEW - Awaiting Review

Tasks that are implementation-complete and awaiting review before merging.

---

## Guidelines

- **Code Complete**: Implementation finished, tests passing
- **Documentation Updated**: CHANGELOG.md, README.md, docs/ updated as needed
- **Verification Passed**: `python scripts/verify-complete.py` passes
- **Review Criteria**: Code quality, test coverage, documentation, breaking changes
- **Approval**: After review approval, move to CHANGELOG.md

## Awaiting Review

<!-- No tasks currently in review -->

---

## Review Template

```markdown
### [TASK-XXX]: Task Title
**Completed**: YYYY-MM-DD
**Author**: Agent/Developer name
**Branch**: worktrees/TASK-XXX
**Type**: Feature | Bug Fix | Refactoring | Performance | Documentation

**Changes**:
- Brief description of what was implemented
- Key files modified
- Impact on existing functionality

**Testing**:
- [ ] Unit tests added (XX tests)
- [ ] Integration tests added (XX tests)
- [ ] All tests passing (X,XXX/X,XXX)
- [ ] Coverage maintained/improved (XX% → XX%)

**Verification**:
- [ ] `python scripts/verify-complete.py` passes
- [ ] Manual testing completed
- [ ] Documentation updated
- [ ] No breaking changes (or documented if unavoidable)

**Review Checklist**:
- [ ] Code quality acceptable
- [ ] Test coverage adequate (>80% for new code)
- [ ] Documentation clear and complete
- [ ] No security vulnerabilities
- [ ] Performance impact acceptable
- [ ] Follows existing patterns

**See**: planning_docs/TASK-XXX_*.md
```

---

## Review Process

1. **Self-Review**: Author reviews own changes
2. **Verification**: Run `python scripts/verify-complete.py`
3. **Move to REVIEW.md**: Add entry when ready
4. **Peer Review**: Another agent/developer reviews (if team)
5. **Approval**: Resolve comments, get approval
6. **Merge**: Merge to main branch
7. **Update CHANGELOG.md**: Move entry from REVIEW.md to CHANGELOG.md

## Quality Standards

**Must Pass:**
- All tests passing (100% pass rate)
- Coverage ≥80% for new code
- No critical security issues
- Documentation updated

**Should Have:**
- Performance benchmarks (if applicable)
- Integration tests for new features
- Migration guide (if breaking changes)
