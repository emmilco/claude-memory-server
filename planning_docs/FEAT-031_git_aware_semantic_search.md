# FEAT-031: Git-Aware Semantic Search

## TODO Reference
- TODO.md: "Git-Aware Semantic Search (~1-2 weeks)"
- Location: Tier 2 - High-Impact Core Functionality Improvements

## Objective
Enable semantic search over git history, allowing users to find code changes by meaning, track function evolution, and perform code archeology through natural language queries.

## Current State
- Code search exists for current codebase state
- No git history integration
- No ability to search commits or track code evolution
- No temporal code analysis

## User Requirements (from TODO)
- Index git history semantically (commits, diffs, blame)
- Support queries like:
  - "code changed last week related to auth"
  - "Find functions modified by commits fixing bug #123"
  - "Show evolution of this function over time"
- Integration with GitPython or libgit2
- Metadata: commit hash, author, date, message
- Configurable index depth (default: 1000 commits)

## Design Discussion Status
**Status:** In Progress (awaiting user feedback)

### Key Design Questions

#### 1. Git Library Choice
**Options:**
- **GitPython** - Pure Python, easier install, slower
- **libgit2 (pygit2)** - C-based, faster, harder install

**Recommendation:** Start with GitPython, add pygit2 as optional optimization

#### 2. What to Index
**Proposed:**
- **Commit Metadata** (always): hash, author, date, message, branches, tags
- **File-Level Changes** (always): files modified, lines added/removed
- **Diff Content** (configurable): full diff text for semantic search

**Question:** Index full diffs by default or make opt-in?

#### 3. Storage Architecture
**Options:**
- **Option A:** Separate git collection/table (recommended)
- **Option B:** Mixed with code index as special memory type

**Recommendation:** Separate storage - different query patterns

#### 4. Indexing Scope
**Proposed Config:**
- `git_index_commit_count`: Default 1000
- `git_index_branches`: Default current branch only
- `git_index_all_branches`: Default False
- `git_index_tags`: Default True
- `git_index_diffs`: Auto-detect based on repo size
- `git_auto_size_threshold`: Default 500MB

**Question:** Current branch only or all branches?

#### 5. Query Capabilities
**Proposed MCP Tools:**
- `search_git_history()` - Semantic search with time/author/file filters
- `show_function_evolution()` - Track changes to specific functions
- `index_git_history()` - Index a repository's git history

**Question:** Any additional query patterns needed?

#### 6. Code Unit Linking
**Question:** Auto-link git commits to code units in existing index?

## Implementation Plan

### Phase 1: Basic Commit Indexing (~3-4 days)
- [ ] Install and test GitPython
- [ ] Design git storage schema (separate collection/table)
- [ ] Implement commit metadata extraction
- [ ] Implement commit message embedding
- [ ] Create `index_git_history` CLI command
- [ ] Create `search_git_history` MCP tool
- [ ] Add time and author filtering
- [ ] Write unit tests

### Phase 2: Diff Indexing (~2-3 days)
- [ ] Implement file change extraction
- [ ] Implement diff content extraction
- [ ] Add diff embedding (optional, configurable)
- [ ] Add file-based filtering
- [ ] Auto-size detection for diffs
- [ ] Write integration tests

### Phase 3: Code Unit Linking (~2-3 days)
- [ ] Cross-reference commits with code units
- [ ] Add git metadata to code units
- [ ] Implement `show_function_evolution` tool
- [ ] Track first_seen_commit, last_modified_commit
- [ ] Write end-to-end tests

### Phase 4: Optimizations (~1-2 days)
- [ ] Batch commit processing
- [ ] Parallel diff parsing
- [ ] Progress reporting
- [ ] Storage optimization
- [ ] Performance testing

## Schema Design

### GitCommit Table/Collection
```python
{
  "id": str,  # commit hash
  "repository_path": str,
  "author_name": str,
  "author_email": str,
  "author_date": datetime,
  "committer_name": str,
  "committer_date": datetime,
  "message": str,
  "message_embedding": List[float],
  "branch_names": List[str],
  "tags": List[str],
  "parent_hashes": List[str],
}
```

### GitFileChange Table/Collection
```python
{
  "id": str,  # commit_hash + file_path
  "commit_hash": str,  # foreign key
  "file_path": str,
  "change_type": str,  # added|modified|deleted
  "lines_added": int,
  "lines_deleted": int,
  "diff_content": Optional[str],
  "diff_embedding": Optional[List[float]],
  "affected_functions": List[str],  # if linkable
}
```

## Configuration (to add to src/config.py)
```python
# Git history indexing
enable_git_indexing: bool = True
git_index_commit_count: int = 1000
git_index_branches: str = "current"  # current|all
git_index_tags: bool = True
git_index_diffs: bool = True  # Auto-disabled for large repos
git_auto_size_threshold_mb: int = 500
git_diff_size_limit_kb: int = 10  # Skip diffs larger than this
```

## CLI Commands
```bash
# Index git history
python -m src.cli git-index ./path/to/repo --commits 1000

# Search git history
python -m src.cli git-search "authentication bug fix" --since "last month"

# Show function evolution
python -m src.cli git-evolution src/auth/login.py:authenticate --commits 20

# Status (extended)
python -m src.cli status  # Shows git index stats
```

## Test Plan
- [ ] Unit tests for git extraction
- [ ] Unit tests for commit metadata
- [ ] Unit tests for diff parsing
- [ ] Integration tests for indexing workflow
- [ ] Integration tests for search queries
- [ ] End-to-end tests for function evolution
- [ ] Performance tests for large repos
- [ ] Error handling tests

## Performance Targets
- Indexing: 10-50 commits/sec
- Search: <50ms for commit messages, <200ms for diffs
- Storage: <1MB per 100 commits (without diffs), <10MB with diffs

## Risks & Mitigations
- **Risk:** Large diffs bloat storage
  - **Mitigation:** Auto-disable for large repos, size limits
- **Risk:** Slow indexing on huge repos (Linux kernel)
  - **Mitigation:** Batch processing, progress reporting, configurable limits
- **Risk:** libgit2 installation issues
  - **Mitigation:** Start with GitPython, pygit2 optional

## Notes & Decisions
- **Library choice:** GitPython (start here, add pygit2 optimization later)
- **Diff indexing:** ✅ Enable by default, auto-disable for repos >500MB
- **Branch scope:** ✅ Current branch only (users can request all branches explicitly)
- **Code linking:** ✅ Yes - auto-link commits to code units
- **Query patterns:** ✅ Support time/author/file filters as proposed
- **Implementation:** ✅ All 4 phases approved

## Progress Tracking
- [x] Design proposal created
- [x] User feedback received
- [x] Design finalized
- [x] Implementation started
- [x] Phase 1 complete ✅
  - [x] GitPython integration
  - [x] Git indexer module
  - [x] Commit metadata extraction
  - [x] Commit message embedding
  - [x] SQLite storage methods
  - [x] CLI command created
  - [x] Tested successfully (5 commits indexed)
- [ ] Phase 2 complete
- [ ] Phase 3 complete
- [ ] Phase 4 complete
- [ ] Tests complete
- [ ] Documentation complete
- [ ] Feature committed

## Related Files
- TODO.md - Task definition
- CLAUDE.md - Project guide
- src/config.py - Configuration
- src/memory/incremental_indexer.py - Code indexing (reference)
- src/store/qdrant_store.py - Storage backend
- src/store/sqlite_store.py - Storage backend
