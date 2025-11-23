# FEAT-061: Git/Historical Integration - Implementation Plan

## TODO Reference
- **ID:** FEAT-061
- **TODO.md Line:** 320-332
- **Priority:** Tier 4 - Advanced Features
- **Estimated Time:** ~1 week
- **Status:** Planning Phase

## Objective

Add comprehensive git history analysis capabilities to enable:
1. **Evolution understanding** - Search commit history semantically to understand how code evolved
2. **Unstable code identification** - Identify files/functions with high churn as refactoring candidates
3. **Domain expertise mapping** - Find who wrote specific code patterns via blame integration
4. **Recent activity tracking** - Understand what changed recently and why
5. **Architecture discovery** - Answer questions like "what files change together?" and "what's been refactored?"

## Current State

### Existing Git Capabilities ✅

The project already has **foundational git infrastructure** in place:

**Files:**
- `/src/memory/git_indexer.py` (438 lines) - Indexes commits and diffs with embeddings
- `/src/memory/git_detector.py` (212 lines) - Detects git repos and extracts metadata
- `/src/cli/git_index_command.py` (167 lines) - CLI for indexing git history
- `/src/cli/git_search_command.py` (151 lines) - CLI for searching commits

**Current Features:**
1. **Commit indexing** - Extract commits with metadata (author, date, message, stats)
2. **Diff extraction** - Parse file changes with line counts and diff content
3. **Semantic embedding** - Generate embeddings for commit messages and diffs
4. **Basic search** - Search commits by message similarity
5. **Repository detection** - Auto-detect git repos and extract metadata

**Config Support (src/config.py:92-99):**
```python
enable_git_indexing: bool = True
git_index_commit_count: int = 1000
git_index_branches: str = "current"  # current|all
git_index_tags: bool = True
git_index_diffs: bool = True  # Auto-disabled for large repos
git_auto_size_threshold_mb: int = 500
git_diff_size_limit_kb: int = 10  # Skip diffs larger than this
```

**Storage Methods (partially implemented):**
- `store.search_git_commits()` - Referenced in git_search_command.py
- `store.store_git_commits()` - Referenced in git_index_command.py
- `store.store_git_file_changes()` - Referenced in git_index_command.py

### Gaps (What FEAT-061 Adds) ❌

**Missing MCP Tools (5 new tools needed):**
1. ❌ `search_git_history(query, since, until)` - Semantic commit search (MCP tool)
2. ❌ `get_change_frequency(file_or_function)` - How often does this change?
3. ❌ `get_churn_hotspots(project)` - Files with highest change frequency
4. ❌ `get_recent_changes(project, days=30)` - Recent modifications with context
5. ❌ `blame_search(pattern)` - Who wrote code matching this pattern?

**Missing Storage Methods:**
- ❌ `store.get_file_change_frequency()` - Calculate change frequency for files
- ❌ `store.get_churn_hotspots()` - Identify high-churn files
- ❌ `store.get_recent_changes()` - Get recent file changes
- ❌ `store.search_git_blame()` - Search by author/pattern

**Missing Analysis Logic:**
- ❌ Change frequency calculation algorithm
- ❌ Churn detection (threshold: changes/time period)
- ❌ Git blame integration with pattern matching
- ❌ Co-change analysis (files that change together)

**Test Coverage:**
- Current: `tests/unit/test_git_storage.py` - All tests SKIPPED (feature not implemented)
- Current: `tests/unit/test_git_indexer.py` - Exists but needs expansion
- Need: 15-20 new tests for FEAT-061 functionality

## Problem Statement

From architecture discovery session (TODO.md context):
- ❌ **Can't identify "frequently changed files"** - No change frequency tracking
- ❌ **Can't find "recent refactorings"** - No time-based change analysis
- ❌ **Can't discover domain experts** - No git blame integration
- ❌ **Can't understand evolution** - Limited to basic commit search

**Developer Use Cases:**
1. "Show me files that change a lot" → Identify unstable code
2. "What changed in the last month?" → Understand recent work
3. "Who wrote the authentication logic?" → Find domain expert
4. "What files always change together?" → Discover hidden dependencies
5. "Is this code stable or churning?" → Inform refactoring decisions

## Technical Design

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     MCP Server (server.py)                   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ New MCP Tools (5 methods)                            │   │
│  │  - search_git_history()                              │   │
│  │  - get_change_frequency()                            │   │
│  │  - get_churn_hotspots()                              │   │
│  │  - get_recent_changes()                              │   │
│  │  - blame_search()                                    │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│              Storage Layer (qdrant_store.py)                 │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ New Storage Methods (4 methods)                      │   │
│  │  - search_git_commits() [EXISTS - enhance]           │   │
│  │  - get_file_change_frequency() [NEW]                 │   │
│  │  - get_churn_hotspots() [NEW]                        │   │
│  │  - get_recent_changes() [NEW]                        │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│            Git Analysis Layer (NEW MODULE)                   │
│              src/memory/git_analyzer.py                      │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ GitAnalyzer class:                                   │   │
│  │  - calculate_change_frequency()                      │   │
│  │  - detect_churn_hotspots()                           │   │
│  │  - analyze_recent_changes()                          │   │
│  │  - search_blame()                                    │   │
│  │  - find_co_changing_files()                          │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                   Qdrant Collections                         │
│  ┌────────────────────┐  ┌─────────────────────────────┐   │
│  │  git_commits       │  │  git_file_changes           │   │
│  │  (existing)        │  │  (existing)                 │   │
│  │  - commit_hash     │  │  - commit_hash + file_path  │   │
│  │  - message         │  │  - change_type              │   │
│  │  - author          │  │  - lines_added/deleted      │   │
│  │  - date            │  │  - diff_content             │   │
│  │  - stats           │  │  - diff_embedding           │   │
│  └────────────────────┘  └─────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### Data Model

#### Existing Collections (Already Defined)

**git_commits collection** (from git_indexer.py GitCommitData):
```python
{
    "id": "commit_hash",
    "commit_hash": str,
    "repository_path": str,
    "author_name": str,
    "author_email": str,
    "author_date": datetime,
    "committer_name": str,
    "committer_date": datetime,
    "message": str,
    "message_embedding": List[float],  # 384 dimensions
    "branch_names": List[str],
    "tags": List[str],
    "parent_hashes": List[str],
    "stats": {
        "files_changed": int,
        "insertions": int,
        "deletions": int,
    }
}
```

**git_file_changes collection** (from git_indexer.py GitFileChangeData):
```python
{
    "id": "commit_hash:file_path",
    "commit_hash": str,
    "file_path": str,
    "change_type": "added|modified|deleted|renamed",
    "lines_added": int,
    "lines_deleted": int,
    "diff_content": Optional[str],
    "diff_embedding": Optional[List[float]],  # 384 dimensions
}
```

#### New Derived Metrics (Computed On-Demand)

**Change Frequency Metric:**
```python
{
    "file_path": str,
    "total_changes": int,
    "first_change": datetime,
    "last_change": datetime,
    "time_span_days": float,
    "changes_per_week": float,
    "unique_authors": int,
    "change_types": Dict[str, int],  # {"modified": 10, "renamed": 1}
    "total_lines_added": int,
    "total_lines_deleted": int,
    "churn_score": float,  # 0.0-1.0 normalized score
}
```

**Churn Hotspot:**
```python
{
    "file_path": str,
    "churn_score": float,  # 0.0-1.0
    "total_changes": int,
    "recent_changes_30d": int,
    "authors": List[str],
    "avg_change_size": float,  # Average lines changed per commit
    "instability_indicator": str,  # "high|medium|low"
}
```

**Recent Change Summary:**
```python
{
    "file_path": str,
    "commit_hash": str,
    "commit_date": datetime,
    "author": str,
    "message": str,
    "change_type": str,
    "lines_added": int,
    "lines_deleted": int,
    "days_ago": int,
}
```

**Blame Result:**
```python
{
    "file_path": str,
    "line_number": int,
    "author": str,
    "commit_hash": str,
    "commit_date": datetime,
    "commit_message": str,
    "code_snippet": str,
}
```

### Storage Strategy

**Option A: Qdrant Collections (RECOMMENDED)**

Pros:
- ✅ Consistent with existing architecture
- ✅ Semantic search on commit messages and diffs
- ✅ Fast vector similarity search
- ✅ Already partially implemented (store_git_commits exists)

Cons:
- ❌ Need to compute metrics on-demand (no aggregation)
- ❌ Higher latency for complex queries

**Decision:** Use Qdrant for raw data, compute metrics in GitAnalyzer

**Collection Structure:**
1. `{project}_git_commits` - Store all commits
2. `{project}_git_file_changes` - Store all file changes
3. Compute change frequency, churn, etc. on-demand from file_changes

### New Module: src/memory/git_analyzer.py

```python
"""Git history analysis and metrics calculation."""

import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta, UTC
from collections import defaultdict
from pathlib import Path

from src.config import ServerConfig
from src.store import MemoryStore

logger = logging.getLogger(__name__)


class GitAnalyzer:
    """
    Analyze git history for change patterns and metrics.

    Computes:
    - Change frequency per file/function
    - Churn hotspots (high change areas)
    - Recent change summaries
    - Author expertise mapping (via blame)
    """

    def __init__(self, store: MemoryStore, config: ServerConfig):
        self.store = store
        self.config = config

    async def calculate_change_frequency(
        self,
        file_path: str,
        project_name: str,
        since: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Calculate how often a file changes.

        Algorithm:
        1. Query git_file_changes for all changes to file_path
        2. Group by time period (week/month)
        3. Count changes per period
        4. Calculate churn score:
           churn_score = (changes / weeks) * (avg_change_size / 100)
           Normalized to 0.0-1.0 scale

        Args:
            file_path: File path to analyze
            project_name: Project scope
            since: Optional start date (default: all time)

        Returns:
            Change frequency metrics (see data model above)
        """
        # Get all changes for this file
        changes = await self.store.get_file_changes_by_path(
            file_path=file_path,
            project_name=project_name,
            since=since,
        )

        if not changes:
            return {
                "file_path": file_path,
                "total_changes": 0,
                "churn_score": 0.0,
            }

        # Calculate metrics
        total_changes = len(changes)
        dates = [c["author_date"] for c in changes]
        first_change = min(dates)
        last_change = max(dates)
        time_span_days = (last_change - first_change).total_seconds() / 86400

        # Calculate changes per week
        time_span_weeks = max(time_span_days / 7, 0.1)  # Avoid div by zero
        changes_per_week = total_changes / time_span_weeks

        # Calculate average change size
        total_lines_added = sum(c["lines_added"] for c in changes)
        total_lines_deleted = sum(c["lines_deleted"] for c in changes)
        avg_change_size = (total_lines_added + total_lines_deleted) / total_changes

        # Compute churn score (0.0-1.0)
        # Formula: (changes_per_week / 5) * (avg_change_size / 100)
        # Assumptions: >5 changes/week = very high, >100 lines/change = large
        churn_score = min(1.0, (changes_per_week / 5.0) * (avg_change_size / 100.0))

        # Get unique authors
        unique_authors = len(set(c["author_email"] for c in changes))

        # Count change types
        change_types = defaultdict(int)
        for change in changes:
            change_types[change["change_type"]] += 1

        return {
            "file_path": file_path,
            "total_changes": total_changes,
            "first_change": first_change,
            "last_change": last_change,
            "time_span_days": time_span_days,
            "changes_per_week": changes_per_week,
            "unique_authors": unique_authors,
            "change_types": dict(change_types),
            "total_lines_added": total_lines_added,
            "total_lines_deleted": total_lines_deleted,
            "churn_score": churn_score,
        }

    async def detect_churn_hotspots(
        self,
        project_name: str,
        limit: int = 10,
        min_changes: int = 5,
        days: int = 90,
    ) -> List[Dict[str, Any]]:
        """
        Find files with highest change frequency (churn hotspots).

        Algorithm:
        1. Get all file changes in last N days
        2. Group by file_path
        3. Calculate churn score for each file
        4. Sort by churn score descending
        5. Filter by min_changes threshold
        6. Return top N

        Args:
            project_name: Project to analyze
            limit: Max results to return
            min_changes: Minimum changes to qualify
            days: Look back period (default: 90 days)

        Returns:
            List of churn hotspot dicts sorted by score descending
        """
        since = datetime.now(UTC) - timedelta(days=days)

        # Get all file changes in time period
        all_changes = await self.store.get_all_file_changes(
            project_name=project_name,
            since=since,
        )

        # Group by file_path
        files = defaultdict(list)
        for change in all_changes:
            files[change["file_path"]].append(change)

        # Calculate churn for each file
        hotspots = []
        for file_path, changes in files.items():
            if len(changes) < min_changes:
                continue

            # Calculate metrics
            total_changes = len(changes)
            recent_changes_30d = sum(
                1 for c in changes
                if (datetime.now(UTC) - c["author_date"]).days <= 30
            )

            authors = set(c["author_email"] for c in changes)

            avg_lines_changed = sum(
                c["lines_added"] + c["lines_deleted"] for c in changes
            ) / total_changes

            # Churn score (0.0-1.0)
            # Higher score = more changes, more recent activity, bigger changes
            churn_score = min(1.0, (
                (total_changes / 20.0) * 0.4 +  # Total activity (max 20)
                (recent_changes_30d / 10.0) * 0.4 +  # Recent activity (max 10)
                (avg_lines_changed / 100.0) * 0.2  # Change size (max 100)
            ))

            # Instability indicator
            if churn_score > 0.7:
                instability = "high"
            elif churn_score > 0.4:
                instability = "medium"
            else:
                instability = "low"

            hotspots.append({
                "file_path": file_path,
                "churn_score": churn_score,
                "total_changes": total_changes,
                "recent_changes_30d": recent_changes_30d,
                "authors": sorted(authors),
                "avg_change_size": avg_lines_changed,
                "instability_indicator": instability,
            })

        # Sort by churn score descending
        hotspots.sort(key=lambda x: x["churn_score"], reverse=True)

        return hotspots[:limit]

    async def analyze_recent_changes(
        self,
        project_name: str,
        days: int = 30,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        Get recent file changes with context.

        Args:
            project_name: Project to analyze
            days: Look back period
            limit: Max results

        Returns:
            List of recent change summaries sorted by date descending
        """
        since = datetime.now(UTC) - timedelta(days=days)

        # Get recent changes
        changes = await self.store.get_all_file_changes(
            project_name=project_name,
            since=since,
        )

        # Sort by date descending (most recent first)
        changes.sort(key=lambda x: x["author_date"], reverse=True)

        # Format results
        results = []
        for change in changes[:limit]:
            days_ago = (datetime.now(UTC) - change["author_date"]).days

            results.append({
                "file_path": change["file_path"],
                "commit_hash": change["commit_hash"],
                "commit_date": change["author_date"],
                "author": change["author_name"],
                "message": change["commit_message"],  # Need to join with commits
                "change_type": change["change_type"],
                "lines_added": change["lines_added"],
                "lines_deleted": change["lines_deleted"],
                "days_ago": days_ago,
            })

        return results

    async def search_blame(
        self,
        pattern: str,
        project_name: str,
        file_pattern: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        Find who wrote code matching a pattern.

        Algorithm:
        1. Search git_file_changes for diff_content matching pattern
        2. Use semantic search on diff_embedding if pattern is natural language
        3. Extract author information from matching changes
        4. Group by file_path + author
        5. Return results with code context

        Args:
            pattern: Code pattern or natural language query
            project_name: Project scope
            file_pattern: Optional file path filter (glob)
            limit: Max results

        Returns:
            List of blame results showing who wrote matching code
        """
        # Determine if pattern is code or natural language
        is_semantic = len(pattern.split()) > 2 or not any(
            c in pattern for c in ["(", ")", "{", "}", ";", "="]
        )

        if is_semantic:
            # Use semantic search on diff embeddings
            from src.embeddings.generator import EmbeddingGenerator

            embedding_gen = EmbeddingGenerator(self.config)
            await embedding_gen.initialize()

            query_embedding = await embedding_gen.generate(pattern)

            results = await self.store.search_git_diffs_semantic(
                query_embedding=query_embedding,
                project_name=project_name,
                limit=limit,
            )
        else:
            # Use keyword search on diff_content
            results = await self.store.search_git_diffs_keyword(
                pattern=pattern,
                project_name=project_name,
                file_pattern=file_pattern,
                limit=limit,
            )

        # Format blame results
        blame_results = []
        for result in results:
            # Extract code snippet from diff
            snippet = self._extract_code_snippet(
                result["diff_content"],
                pattern,
                context_lines=3,
            )

            blame_results.append({
                "file_path": result["file_path"],
                "line_number": result.get("line_number", 0),  # Estimate
                "author": result["author_name"],
                "commit_hash": result["commit_hash"],
                "commit_date": result["author_date"],
                "commit_message": result["commit_message"],
                "code_snippet": snippet,
            })

        return blame_results

    def _extract_code_snippet(
        self,
        diff_content: str,
        pattern: str,
        context_lines: int = 3,
    ) -> str:
        """Extract code snippet from diff content."""
        lines = diff_content.split("\n")

        # Find lines matching pattern
        matching_lines = []
        for i, line in enumerate(lines):
            if pattern.lower() in line.lower():
                matching_lines.append(i)

        if not matching_lines:
            # Return first few lines as fallback
            return "\n".join(lines[:5])

        # Extract context around first match
        match_idx = matching_lines[0]
        start = max(0, match_idx - context_lines)
        end = min(len(lines), match_idx + context_lines + 1)

        snippet_lines = lines[start:end]
        return "\n".join(snippet_lines)
```

### New MCP Tools in server.py

#### 1. search_git_history()

```python
async def search_git_history(
    self,
    query: str,
    project_name: Optional[str] = None,
    author: Optional[str] = None,
    since: Optional[str] = None,  # ISO date or "7 days ago"
    until: Optional[str] = None,
    limit: int = 20,
) -> Dict[str, Any]:
    """
    Search git history semantically.

    **PROACTIVE USE:**
    - "How was authentication implemented?" → search_git_history("authentication implementation")
    - "When did we add rate limiting?" → search_git_history("rate limiting", since="2024-01-01")
    - "What did Alice work on last month?" → search_git_history("*", author="alice@example.com", since="30 days ago")

    Searches commit messages and diffs using semantic similarity.

    Args:
        query: Natural language or keyword query
        project_name: Optional project filter (default: current project)
        author: Optional author filter (name or email)
        since: Optional start date (ISO format or relative: "7 days ago")
        until: Optional end date
        limit: Max results (default: 20)

    Returns:
        {
            "commits": [
                {
                    "commit_hash": str,
                    "author": str,
                    "date": str,
                    "message": str,
                    "files_changed": int,
                    "insertions": int,
                    "deletions": int,
                    "relevance_score": float,
                }
            ],
            "total": int,
        }

    Raises:
        ValidationError: Invalid parameters
        RetrievalError: Search failed
    """
    # Parse date filters
    since_dt = self._parse_date_filter(since) if since else None
    until_dt = self._parse_date_filter(until) if until else None

    # Generate query embedding
    query_embedding = await self.embedding_generator.generate(query)

    # Search commits
    commits = await self.store.search_git_commits(
        query_embedding=query_embedding,
        project_name=project_name or self.project_name,
        author=author,
        since=since_dt,
        until=until_dt,
        limit=limit,
    )

    # Format results
    results = []
    for commit, score in commits:
        results.append({
            "commit_hash": commit["commit_hash"],
            "author": f"{commit['author_name']} <{commit['author_email']}>",
            "date": commit["author_date"].isoformat(),
            "message": commit["message"],
            "files_changed": commit["stats"]["files_changed"],
            "insertions": commit["stats"]["insertions"],
            "deletions": commit["stats"]["deletions"],
            "relevance_score": score,
        })

    logger.info(f"Found {len(results)} commits matching '{query}'")

    return {
        "commits": results,
        "total": len(results),
    }
```

#### 2. get_change_frequency()

```python
async def get_change_frequency(
    self,
    file_or_function: str,
    project_name: Optional[str] = None,
    since: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Calculate how often a file or function changes.

    **PROACTIVE USE:**
    - Before refactoring: "How stable is this file?"
    - Code review: "Is this code churning a lot?"
    - Architecture planning: "What's our most volatile component?"

    Args:
        file_or_function: File path (e.g., "src/auth.py") or function name
        project_name: Optional project filter
        since: Optional start date for analysis

    Returns:
        {
            "file_path": str,
            "total_changes": int,
            "first_change": str,  # ISO date
            "last_change": str,
            "time_span_days": float,
            "changes_per_week": float,
            "unique_authors": int,
            "change_types": {"modified": int, "renamed": int},
            "total_lines_added": int,
            "total_lines_deleted": int,
            "churn_score": float,  # 0.0-1.0 (higher = more unstable)
            "interpretation": str,  # "high|medium|low churn"
        }
    """
    if self.git_analyzer is None:
        from src.memory.git_analyzer import GitAnalyzer
        self.git_analyzer = GitAnalyzer(self.store, self.config)

    since_dt = self._parse_date_filter(since) if since else None

    # Calculate frequency
    result = await self.git_analyzer.calculate_change_frequency(
        file_path=file_or_function,
        project_name=project_name or self.project_name,
        since=since_dt,
    )

    # Add interpretation
    if result["churn_score"] > 0.7:
        interpretation = "high churn - consider refactoring or stabilizing"
    elif result["churn_score"] > 0.4:
        interpretation = "medium churn - actively developed"
    else:
        interpretation = "low churn - stable code"

    result["interpretation"] = interpretation

    logger.info(
        f"Change frequency for {file_or_function}: "
        f"{result['total_changes']} changes, "
        f"churn_score={result['churn_score']:.2f}"
    )

    return result
```

#### 3. get_churn_hotspots()

```python
async def get_churn_hotspots(
    self,
    project_name: Optional[str] = None,
    limit: int = 10,
    min_changes: int = 5,
    days: int = 90,
) -> Dict[str, Any]:
    """
    Find files with highest change frequency (churn hotspots).

    **PROACTIVE USE:**
    - Architecture review: "What code is most unstable?"
    - Refactoring planning: "What should we prioritize stabilizing?"
    - Risk assessment: "What files break most often?"

    Hotspots indicate:
    - Frequently changing code (potential design issues)
    - High maintenance burden
    - Refactoring candidates
    - Test coverage gaps

    Args:
        project_name: Optional project filter
        limit: Max results (default: 10)
        min_changes: Minimum changes to qualify (default: 5)
        days: Analysis window in days (default: 90)

    Returns:
        {
            "hotspots": [
                {
                    "file_path": str,
                    "churn_score": float,  # 0.0-1.0
                    "total_changes": int,
                    "recent_changes_30d": int,
                    "authors": List[str],
                    "avg_change_size": float,
                    "instability_indicator": "high|medium|low",
                }
            ],
            "analysis_period_days": int,
            "total_files_analyzed": int,
        }
    """
    if self.git_analyzer is None:
        from src.memory.git_analyzer import GitAnalyzer
        self.git_analyzer = GitAnalyzer(self.store, self.config)

    hotspots = await self.git_analyzer.detect_churn_hotspots(
        project_name=project_name or self.project_name,
        limit=limit,
        min_changes=min_changes,
        days=days,
    )

    logger.info(f"Found {len(hotspots)} churn hotspots in last {days} days")

    return {
        "hotspots": hotspots,
        "analysis_period_days": days,
        "total_files_analyzed": len(hotspots),
    }
```

#### 4. get_recent_changes()

```python
async def get_recent_changes(
    self,
    project_name: Optional[str] = None,
    days: int = 30,
    limit: int = 50,
    file_pattern: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Get recent file modifications with context.

    **PROACTIVE USE:**
    - Daily standup: "What changed yesterday?"
    - Code review: "What's been modified this week?"
    - Onboarding: "What's the team working on?"
    - Bug investigation: "What changed before this broke?"

    Args:
        project_name: Optional project filter
        days: Look back period (default: 30)
        limit: Max results (default: 50)
        file_pattern: Optional file filter (e.g., "src/api/*.py")

    Returns:
        {
            "changes": [
                {
                    "file_path": str,
                    "commit_hash": str,
                    "commit_date": str,
                    "author": str,
                    "message": str,
                    "change_type": "added|modified|deleted|renamed",
                    "lines_added": int,
                    "lines_deleted": int,
                    "days_ago": int,
                }
            ],
            "period_days": int,
            "total_changes": int,
        }
    """
    if self.git_analyzer is None:
        from src.memory.git_analyzer import GitAnalyzer
        self.git_analyzer = GitAnalyzer(self.store, self.config)

    changes = await self.git_analyzer.analyze_recent_changes(
        project_name=project_name or self.project_name,
        days=days,
        limit=limit,
    )

    # Apply file pattern filter if specified
    if file_pattern:
        import fnmatch
        changes = [
            c for c in changes
            if fnmatch.fnmatch(c["file_path"], file_pattern)
        ]

    logger.info(f"Found {len(changes)} recent changes in last {days} days")

    return {
        "changes": changes,
        "period_days": days,
        "total_changes": len(changes),
    }
```

#### 5. blame_search()

```python
async def blame_search(
    self,
    pattern: str,
    project_name: Optional[str] = None,
    file_pattern: Optional[str] = None,
    limit: int = 20,
) -> Dict[str, Any]:
    """
    Find who wrote code matching a pattern (git blame integration).

    **PROACTIVE USE:**
    - Find domain expert: "Who wrote the JWT validation logic?"
    - Code ownership: "Who maintains the payment processing?"
    - Bug investigation: "Who added this TODO?"
    - Knowledge transfer: "Who knows about Redis caching?"

    Searches git diffs semantically or by keyword to identify authors.

    Args:
        pattern: Code pattern or natural language query
                 Examples:
                 - "JWT validation" (semantic)
                 - "def validate_token" (keyword)
                 - "TODO: refactor" (keyword)
        project_name: Optional project filter
        file_pattern: Optional file filter (e.g., "src/auth/*.py")
        limit: Max results (default: 20)

    Returns:
        {
            "results": [
                {
                    "file_path": str,
                    "line_number": int,  # Approximate
                    "author": str,
                    "commit_hash": str,
                    "commit_date": str,
                    "commit_message": str,
                    "code_snippet": str,  # Context around match
                }
            ],
            "pattern": str,
            "total_matches": int,
        }
    """
    if self.git_analyzer is None:
        from src.memory.git_analyzer import GitAnalyzer
        self.git_analyzer = GitAnalyzer(self.store, self.config)

    results = await self.git_analyzer.search_blame(
        pattern=pattern,
        project_name=project_name or self.project_name,
        file_pattern=file_pattern,
        limit=limit,
    )

    logger.info(f"Found {len(results)} blame matches for pattern '{pattern}'")

    return {
        "results": results,
        "pattern": pattern,
        "total_matches": len(results),
    }
```

### New Storage Methods (qdrant_store.py)

Add to `QdrantMemoryStore` class:

```python
async def get_file_changes_by_path(
    self,
    file_path: str,
    project_name: str,
    since: Optional[datetime] = None,
) -> List[Dict[str, Any]]:
    """Get all changes for a specific file."""
    # Query git_file_changes collection
    # Filter by file_path and project_name
    # Optionally filter by date
    pass

async def get_all_file_changes(
    self,
    project_name: str,
    since: Optional[datetime] = None,
) -> List[Dict[str, Any]]:
    """Get all file changes for a project."""
    # Query git_file_changes collection
    # Filter by project_name
    # Optionally filter by date
    pass

async def search_git_diffs_semantic(
    self,
    query_embedding: List[float],
    project_name: str,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """Search diffs using semantic similarity."""
    # Search git_file_changes by diff_embedding
    pass

async def search_git_diffs_keyword(
    self,
    pattern: str,
    project_name: str,
    file_pattern: Optional[str] = None,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """Search diffs using keyword matching."""
    # Search git_file_changes by diff_content (text search)
    pass
```

## Implementation Phases

### Phase 1: Storage Layer (2 days)

**Goal:** Implement storage methods for querying git data

**Tasks:**
1. ✅ Review existing `store_git_commits()` and `store_git_file_changes()` (already called in git_index_command.py)
2. ⬜ Implement `get_file_changes_by_path()` in qdrant_store.py
3. ⬜ Implement `get_all_file_changes()` in qdrant_store.py
4. ⬜ Implement `search_git_diffs_semantic()` in qdrant_store.py
5. ⬜ Implement `search_git_diffs_keyword()` in qdrant_store.py
6. ⬜ Add to base.py interface (abstract methods)
7. ⬜ Write unit tests for storage methods (8 tests)

**Validation:**
- Run `pytest tests/unit/test_git_storage.py -v`
- All storage queries return expected data

### Phase 2: Analysis Layer (2 days)

**Goal:** Create GitAnalyzer class with metric calculations

**Tasks:**
1. ⬜ Create `src/memory/git_analyzer.py`
2. ⬜ Implement `calculate_change_frequency()`
3. ⬜ Implement `detect_churn_hotspots()`
4. ⬜ Implement `analyze_recent_changes()`
5. ⬜ Implement `search_blame()`
6. ⬜ Implement helper `_extract_code_snippet()`
7. ⬜ Write unit tests for GitAnalyzer (7 tests)

**Validation:**
- Test change frequency calculation accuracy
- Test churn scoring algorithm
- Test blame search results

### Phase 3: MCP Tools (1.5 days)

**Goal:** Add 5 new MCP tools to server.py

**Tasks:**
1. ⬜ Implement `search_git_history()` in server.py
2. ⬜ Implement `get_change_frequency()` in server.py
3. ⬜ Implement `get_churn_hotspots()` in server.py
4. ⬜ Implement `get_recent_changes()` in server.py
5. ⬜ Implement `blame_search()` in server.py
6. ⬜ Add helper `_parse_date_filter()` for date parsing
7. ⬜ Register tools in MCP server setup
8. ⬜ Update tool registry/documentation

**Validation:**
- Test each tool via MCP interface
- Verify error handling
- Check parameter validation

### Phase 4: Integration & Testing (1.5 days)

**Goal:** End-to-end testing and integration

**Tasks:**
1. ⬜ Create integration tests (test_git_integration.py) - 5 tests
2. ⬜ Test full workflow: index → analyze → query
3. ⬜ Test edge cases (no commits, single commit, empty repo)
4. ⬜ Test performance with large history (1000+ commits)
5. ⬜ Update `tests/unit/test_git_storage.py` (remove skip marker)
6. ⬜ Test date filter parsing ("7 days ago", ISO dates)
7. ⬜ Verify churn score accuracy with real repos

**Validation:**
- All 20+ tests passing
- No performance regressions
- Accurate results on real repositories

### Phase 5: Documentation & Polish (1 day)

**Goal:** Document features and update guides

**Tasks:**
1. ⬜ Update `CHANGELOG.md` with FEAT-061 entry
2. ⬜ Update `docs/API.md` with 5 new tools
3. ⬜ Update `docs/USAGE.md` with git analysis examples
4. ⬜ Update `README.md` feature list
5. ⬜ Add examples to docstrings
6. ⬜ Create example script: `examples/git_analysis_demo.py`
7. ⬜ Update `TODO.md` (mark FEAT-061 complete)

**Validation:**
- Documentation accurate and complete
- Examples work correctly
- All references updated

## Code Examples

### Example 1: Search Git History

```python
# User: "How was authentication implemented?"
result = await server.search_git_history(
    query="authentication implementation",
    since="2024-01-01",
    limit=10,
)

print(f"Found {result['total']} commits")
for commit in result['commits']:
    print(f"{commit['commit_hash'][:8]} - {commit['author']}")
    print(f"  {commit['message']}")
    print(f"  Relevance: {commit['relevance_score']:.2f}")
```

### Example 2: Find Churn Hotspots

```python
# User: "What code is most unstable?"
result = await server.get_churn_hotspots(
    limit=5,
    days=90,
)

print(f"Top {len(result['hotspots'])} churn hotspots:")
for hotspot in result['hotspots']:
    print(f"{hotspot['file_path']}")
    print(f"  Churn score: {hotspot['churn_score']:.2f} ({hotspot['instability_indicator']})")
    print(f"  Changes: {hotspot['total_changes']} total, {hotspot['recent_changes_30d']} in last 30 days")
    print(f"  Authors: {', '.join(hotspot['authors'][:3])}")
```

### Example 3: Get Change Frequency

```python
# User: "How stable is this file?"
result = await server.get_change_frequency(
    file_or_function="src/auth/jwt_validator.py",
)

print(f"File: {result['file_path']}")
print(f"Total changes: {result['total_changes']}")
print(f"Changes per week: {result['changes_per_week']:.1f}")
print(f"Churn score: {result['churn_score']:.2f}")
print(f"Interpretation: {result['interpretation']}")
```

### Example 4: Recent Changes

```python
# User: "What changed this week?"
result = await server.get_recent_changes(
    days=7,
    limit=20,
)

print(f"Recent changes ({result['period_days']} days):")
for change in result['changes']:
    print(f"{change['file_path']} - {change['days_ago']} days ago")
    print(f"  {change['author']}: {change['message']}")
    print(f"  +{change['lines_added']} -{change['lines_deleted']}")
```

### Example 5: Blame Search

```python
# User: "Who wrote the JWT validation logic?"
result = await server.blame_search(
    pattern="JWT validation",
    file_pattern="src/auth/*.py",
)

print(f"Found {result['total_matches']} matches for '{result['pattern']}'")
for match in result['results']:
    print(f"{match['file_path']} - {match['author']}")
    print(f"  Commit: {match['commit_hash'][:8]} ({match['commit_date']})")
    print(f"  {match['commit_message']}")
    print(f"  Code:\n{match['code_snippet']}")
```

## Test Plan

### Unit Tests (15 tests)

**test_git_analyzer.py (7 tests):**
1. `test_calculate_change_frequency_single_file` - Basic frequency calculation
2. `test_calculate_change_frequency_no_changes` - Empty result handling
3. `test_detect_churn_hotspots_top_files` - Hotspot detection
4. `test_detect_churn_hotspots_min_changes_filter` - Threshold filtering
5. `test_analyze_recent_changes_date_range` - Recent changes within range
6. `test_search_blame_semantic` - Semantic blame search
7. `test_search_blame_keyword` - Keyword blame search

**test_git_storage.py (8 tests) - Remove skip marker:**
1. `test_get_file_changes_by_path` - Query changes for specific file
2. `test_get_file_changes_by_path_with_date_filter` - Date filtering
3. `test_get_all_file_changes` - Get all project changes
4. `test_search_git_diffs_semantic` - Semantic diff search
5. `test_search_git_diffs_keyword` - Keyword diff search
6. `test_file_changes_empty_result` - No changes found
7. `test_file_changes_pagination` - Large result sets
8. `test_file_changes_project_isolation` - Multi-project filtering

### Integration Tests (5 tests)

**test_git_integration.py:**
1. `test_end_to_end_workflow` - Index → analyze → query
2. `test_churn_detection_accuracy` - Verify churn scores
3. `test_date_filter_parsing` - Relative dates ("7 days ago")
4. `test_cross_tool_consistency` - Same data across tools
5. `test_performance_large_history` - 1000+ commits

### Manual Tests (3 scenarios)

1. **Real repository analysis:**
   - Index a real project (e.g., this project)
   - Find churn hotspots
   - Verify results match actual git history

2. **Blame search accuracy:**
   - Search for known code patterns
   - Verify authors are correct
   - Check code snippet context

3. **Date filter testing:**
   - Test various date formats
   - Test relative dates ("yesterday", "last week")
   - Verify results match expected timeframe

## Performance Considerations

### Git Operations Can Be Slow ⚠️

**Problem:** Git operations (log, diff, blame) are I/O intensive

**Solutions:**

1. **Indexing is one-time cost:**
   - Git history indexed once via `git_index_command.py`
   - Stored in Qdrant for fast queries
   - Re-index only when needed (not on every query)

2. **Limit commit count:**
   - Default: 1000 commits (`git_index_commit_count`)
   - Configurable via config
   - Focus on recent history

3. **Skip large diffs:**
   - Config: `git_diff_size_limit_kb = 10`
   - Skip diffs >10KB to avoid embedding overhead
   - Auto-disable diffs for repos >500MB

4. **Batch processing:**
   - Index commits in batches
   - Use parallel embedding generation (4-8x faster)
   - Cache embeddings for re-indexing

5. **Lazy loading:**
   - Don't load git data until requested
   - Compute metrics on-demand
   - Cache analysis results (future optimization)

### Performance Targets

| Operation | Target | Strategy |
|-----------|--------|----------|
| Index 1000 commits | <60s | Parallel embeddings |
| Search commits | <100ms | Qdrant vector search |
| Calculate churn | <500ms | Aggregate file changes |
| Blame search | <200ms | Semantic diff search |
| Recent changes | <50ms | Date-filtered query |

### Optimization Opportunities (Future)

1. **Materialized views:**
   - Pre-compute churn scores daily
   - Store in separate collection
   - Update incrementally

2. **Result caching:**
   - Cache frequent queries (hotspots, recent changes)
   - TTL: 1 hour
   - Invalidate on new commits

3. **Incremental git indexing:**
   - Only index new commits since last run
   - Track indexed commits in ProjectIndexTracker
   - Automatic when file watcher detects .git changes

## Success Criteria

### Functional Requirements ✅

1. ✅ **5 new MCP tools implemented:**
   - `search_git_history()` - Search commits semantically
   - `get_change_frequency()` - File/function churn analysis
   - `get_churn_hotspots()` - Top unstable files
   - `get_recent_changes()` - Recent activity summary
   - `blame_search()` - Find code authors by pattern

2. ✅ **Storage layer complete:**
   - Query methods for git data
   - Semantic and keyword search
   - Date filtering
   - Project isolation

3. ✅ **Analysis algorithms working:**
   - Change frequency calculation
   - Churn scoring (0.0-1.0)
   - Recent change detection
   - Blame pattern matching

### Quality Requirements ✅

1. ✅ **Test coverage:** 15-20 tests (unit + integration)
2. ✅ **Documentation:** All tools documented with examples
3. ✅ **Error handling:** Graceful degradation, clear error messages
4. ✅ **Performance:** Meets targets above

### User Impact ✅

1. ✅ **Architecture discovery:**
   - Can answer "what files change together?"
   - Can identify "frequently changed files"
   - Can find "recent refactorings"

2. ✅ **Developer productivity:**
   - Find domain experts quickly
   - Identify unstable code
   - Understand recent activity
   - Answer "why did this change?"

3. ✅ **Refactoring support:**
   - Data-driven refactoring decisions
   - Churn hotspots = priorities
   - Change frequency = risk indicator

## Dependencies

### Required
- ✅ GitPython >= 3.1.40 (already in requirements.txt)
- ✅ Existing git indexer (src/memory/git_indexer.py)
- ✅ Qdrant store with git collections
- ✅ Embedding generator for semantic search

### Optional
- ⬜ Git command-line tools (for advanced blame)
- ⬜ libgit2 for faster git operations (future optimization)

## Risks & Mitigations

### Risk 1: Git operations too slow
**Mitigation:** One-time indexing, limit commit count, skip large diffs

### Risk 2: Churn scoring algorithm inaccurate
**Mitigation:** Test on real repos, allow score customization, document assumptions

### Risk 3: Blame search doesn't find authors
**Mitigation:** Combine semantic + keyword search, show diff context, link to commits

### Risk 4: Large repositories (>10K commits)
**Mitigation:** Configurable limits, focus on recent history, incremental indexing

## Future Enhancements (Post-FEAT-061)

1. **Co-change analysis:**
   - Find files that change together
   - Identify hidden dependencies
   - Suggest refactoring boundaries

2. **Author expertise scoring:**
   - Rank authors by contribution to file/module
   - Show expertise heatmap
   - Recommend reviewers

3. **Change prediction:**
   - ML model: "This file will likely change soon"
   - Based on historical patterns
   - Risk indicators

4. **Visual git history:**
   - Timeline view of commits
   - Churn heatmap over time
   - Author contribution graphs

5. **Incremental git indexing:**
   - Auto-index new commits
   - File watcher integration
   - Near real-time updates

## Completion Checklist

### Implementation
- [ ] Phase 1: Storage layer (2 days)
- [ ] Phase 2: Analysis layer (2 days)
- [ ] Phase 3: MCP tools (1.5 days)
- [ ] Phase 4: Integration & testing (1.5 days)
- [ ] Phase 5: Documentation (1 day)

### Testing
- [ ] 15+ unit tests passing
- [ ] 5 integration tests passing
- [ ] Manual testing on real repos
- [ ] Performance targets met

### Documentation
- [ ] CHANGELOG.md updated
- [ ] docs/API.md updated (5 new tools)
- [ ] docs/USAGE.md updated (examples)
- [ ] README.md updated
- [ ] TODO.md updated (mark complete)

### Validation
- [ ] All use cases working:
  - [ ] Find frequently changed files ✓
  - [ ] Find recent refactorings ✓
  - [ ] Identify domain experts ✓
  - [ ] Understand evolution ✓
  - [ ] Churn-based refactoring ✓

---

## Notes & Decisions

**2025-11-22 - Planning Session:**
- Discovered extensive existing git infrastructure
- Git indexing already implemented (git_indexer.py, git_detector.py)
- CLI commands already exist (git_index_command.py, git_search_command.py)
- Storage methods partially implemented (search_git_commits, store_git_commits)
- **Decision:** Build on existing foundation rather than starting from scratch
- **Focus:** Add 5 MCP tools + analysis layer + complete storage methods
- **Complexity reduction:** ~40% less work than estimated (existing infra reusable)

**Key architectural decision:**
- Use Qdrant for raw data storage (commits, diffs)
- Compute metrics on-demand in GitAnalyzer
- Avoid materialized views for now (premature optimization)
- Can add caching later if needed

**Churn scoring formula:**
```
churn_score = min(1.0, (
    (total_changes / 20.0) * 0.4 +       # Total activity weight
    (recent_changes_30d / 10.0) * 0.4 +  # Recent activity weight
    (avg_change_size / 100.0) * 0.2      # Change size weight
))
```
Assumptions: >20 total changes = very active, >10 in 30 days = volatile, >100 lines/change = large

**Date filter parsing:**
Support both ISO dates and relative dates:
- ISO: "2024-01-01", "2024-01-01T00:00:00Z"
- Relative: "yesterday", "7 days ago", "last week", "last month"

## References

- **Existing code:**
  - `/src/memory/git_indexer.py` - Commit/diff indexing
  - `/src/memory/git_detector.py` - Repository detection
  - `/src/cli/git_index_command.py` - CLI indexing
  - `/src/cli/git_search_command.py` - CLI search

- **Tests:**
  - `/tests/unit/test_git_storage.py` - Storage tests (currently skipped)
  - `/tests/unit/test_git_indexer.py` - Indexer tests
  - `/tests/unit/test_git_detector.py` - Detector tests

- **Config:**
  - `/src/config.py:92-99` - Git indexing configuration

- **TODO:**
  - `TODO.md:320-332` - FEAT-061 specification

- **Similar patterns:**
  - `src/core/server.py:search_code()` - Semantic code search (reference for MCP tool structure)
  - `src/core/server.py:index_codebase()` - Code indexing (reference for validation patterns)
