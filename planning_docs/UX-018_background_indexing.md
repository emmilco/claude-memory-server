# UX-018: Background Indexing for Large Projects

## TODO Reference
- TODO.md: "UX-018: Background Indexing for Large Projects (~3 days)"
- Requirements:
  - Start indexing in background
  - Search available on incremental results
  - Notification when complete
  - Resume interrupted indexing

## Objective
Enable background indexing for large projects, allowing users to start searching immediately on partial results while indexing continues. Support resuming interrupted indexing operations and provide notifications when complete.

## Current State

### Existing Implementation
- **Concurrent Indexing**: `IncrementalIndexer.index_directory()` already has concurrent processing with `max_concurrent=4` and semaphores (lines 411-453)
- **Progress Callbacks**: System already supports `progress_callback` parameter (lines 373, 399-443)
- **Incremental Storage**: Units are stored immediately as they're indexed via `batch_store()`
- **Real-time Search**: Vector store supports searching as soon as units are stored

### Key Files
- `src/memory/incremental_indexer.py` - Core indexing logic with concurrent processing
- `src/cli/index_command.py` - CLI with progress display
- `src/memory/indexing_service.py` - Background service infrastructure (exists)

### Current Limitations
1. **Blocking**: CLI `index` command blocks until complete (lines 210-225)
2. **No resumption**: No state tracking for interrupted indexing
3. **No notifications**: No completion notifications
4. **No background mode**: Cannot run indexing as daemon/background process

## Implementation Plan

### Phase 1: Background Indexing Service (Core)
- [ ] Create `BackgroundIndexer` class wrapping `IncrementalIndexer`
- [ ] Add task queue for indexing jobs
- [ ] Implement job state tracking (queued, running, paused, completed, failed)
- [ ] Store job state in SQLite for persistence
- [ ] Support starting/stopping/pausing jobs

### Phase 2: Resumption Support
- [ ] Track indexed files in job state
- [ ] Skip already-indexed files on resume
- [ ] Handle partial file indexing (if interrupted mid-file)
- [ ] Add `resume_job()` method
- [ ] Test resume after various interruption points

### Phase 3: Notification System
- [ ] Add notification callback interface
- [ ] Implement console notification (Rich)
- [ ] Implement desktop notification (optional, cross-platform)
- [ ] Add webhook notification support (optional)
- [ ] Notify on completion, errors, and major milestones

### Phase 4: CLI Integration
- [ ] Add `--background` flag to `index` command
- [ ] Add `index jobs` subcommand to list jobs
- [ ] Add `index status <job-id>` to check job status
- [ ] Add `index pause <job-id>` / `index resume <job-id>`
- [ ] Add `index cancel <job-id>`

### Phase 5: MCP Server Integration
- [ ] Add `start_background_indexing` tool
- [ ] Add `get_indexing_status` tool
- [ ] Add `pause_indexing` / `resume_indexing` tools
- [ ] Return job IDs for tracking

### Phase 6: Testing
- [ ] Unit tests for BackgroundIndexer
- [ ] Unit tests for job state management
- [ ] Integration tests for background indexing workflow
- [ ] Test resumption after interruption
- [ ] Test notification delivery
- [ ] Test concurrent job management

## Database Schema

### New Table: `indexing_jobs`

```sql
CREATE TABLE indexing_jobs (
    id TEXT PRIMARY KEY,
    project_name TEXT NOT NULL,
    directory_path TEXT NOT NULL,
    recursive BOOLEAN NOT NULL DEFAULT 1,
    status TEXT NOT NULL,  -- queued, running, paused, completed, failed
    created_at TEXT NOT NULL,
    started_at TEXT,
    completed_at TEXT,
    total_files INTEGER,
    indexed_files INTEGER DEFAULT 0,
    failed_files INTEGER DEFAULT 0,
    total_units INTEGER DEFAULT 0,
    error_message TEXT,
    last_indexed_file TEXT,
    indexed_file_list TEXT,  -- JSON array of indexed files
    FOREIGN KEY (project_name) REFERENCES projects(name)
)
```

### Index for Performance
```sql
CREATE INDEX idx_jobs_status ON indexing_jobs(status);
CREATE INDEX idx_jobs_project ON indexing_jobs(project_name);
```

## Architecture

### Class Hierarchy

```
BackgroundIndexer
├── IncrementalIndexer (reused)
├── JobStateManager (new)
│   ├── create_job()
│   ├── update_job_progress()
│   ├── get_job_status()
│   └── get_indexed_files()
├── NotificationManager (new)
│   ├── notify_started()
│   ├── notify_progress()
│   ├── notify_completed()
│   └── notify_failed()
└── IndexingQueue (new)
    ├── enqueue_job()
    ├── get_next_job()
    └── cancel_job()
```

### Key Methods

```python
class BackgroundIndexer:
    async def start_indexing_job(
        self,
        directory: Path,
        project_name: str,
        recursive: bool = True,
        background: bool = True,
    ) -> str:
        """Start new indexing job, return job ID."""

    async def resume_job(self, job_id: str) -> None:
        """Resume interrupted job."""

    async def pause_job(self, job_id: str) -> None:
        """Pause running job."""

    async def cancel_job(self, job_id: str) -> None:
        """Cancel job and clean up."""

    async def get_job_status(self, job_id: str) -> JobStatus:
        """Get current job status."""

    async def list_jobs(self, status: Optional[str] = None) -> List[JobStatus]:
        """List all jobs, optionally filtered by status."""
```

## Progress Tracking

### Current Progress
- [x] Analyzed existing codebase
- [x] Created planning document
- [ ] Implement Phase 1: Background Indexing Service
- [ ] Implement Phase 2: Resumption Support
- [ ] Implement Phase 3: Notification System
- [ ] Implement Phase 4: CLI Integration
- [ ] Implement Phase 5: MCP Server Integration
- [ ] Implement Phase 6: Testing

## Notes & Decisions

### Design Decisions

1. **Reuse IncrementalIndexer**: Leverage existing concurrent indexing rather than reimplementing
2. **SQLite for State**: Store job state in SQLite for persistence across restarts
3. **Progress Callbacks**: Use existing callback system for progress tracking
4. **Async-first**: All operations async to support background execution
5. **Job IDs**: Use UUIDs for unique job identification

### Performance Considerations

- **Memory**: Track indexed files in memory during run, persist to DB periodically
- **Concurrency**: Maintain existing `max_concurrent=4` limit to prevent resource exhaustion
- **Resume Overhead**: Querying indexed files on resume should be fast (indexed by job_id)

### Edge Cases to Handle

1. **Multiple jobs for same directory**: Allow or prevent?
   - **Decision**: Allow, but warn user about potential conflicts
2. **Interrupted during file indexing**: How to handle partial file?
   - **Decision**: Re-index entire file (simpler, safer)
3. **File system changes during indexing**: Handle?
   - **Decision**: Continue with original file list, ignore changes
4. **Qdrant connection loss**: How to resume?
   - **Decision**: Fail job, allow manual resume after reconnection

### Testing Strategy

- **Unit Tests**: Mock IncrementalIndexer, test state management
- **Integration Tests**: Use temporary directories, test full workflows
- **Interruption Tests**: Simulate crashes, test resumption
- **Concurrency Tests**: Test multiple simultaneous jobs

## Test Cases

### Unit Tests (20 tests)

1. **JobStateManager**:
   - `test_create_job()` - Create new job with correct initial state
   - `test_update_job_progress()` - Update indexed file count
   - `test_get_job_status()` - Retrieve job status
   - `test_get_indexed_files()` - Retrieve list of indexed files
   - `test_mark_job_completed()` - Mark job as completed
   - `test_mark_job_failed()` - Mark job as failed with error
   - `test_list_jobs_by_status()` - Filter jobs by status

2. **BackgroundIndexer**:
   - `test_start_indexing_job()` - Start new job, returns job ID
   - `test_pause_job()` - Pause running job
   - `test_resume_job()` - Resume paused job
   - `test_cancel_job()` - Cancel job and clean up
   - `test_job_completion_notification()` - Verify completion notification
   - `test_job_failure_handling()` - Handle indexing errors
   - `test_skip_indexed_files_on_resume()` - Don't re-index completed files
   - `test_multiple_concurrent_jobs()` - Run multiple jobs in parallel

3. **NotificationManager**:
   - `test_notify_started()` - Send started notification
   - `test_notify_progress()` - Send progress notifications
   - `test_notify_completed()` - Send completion notification
   - `test_notify_failed()` - Send failure notification
   - `test_notification_throttling()` - Limit notification frequency

### Integration Tests (12 tests)

1. **End-to-End Workflows**:
   - `test_background_indexing_workflow()` - Full background indexing cycle
   - `test_search_during_indexing()` - Search returns partial results
   - `test_resume_after_interruption()` - Simulate crash and resume
   - `test_pause_resume_workflow()` - Pause, then resume successfully
   - `test_cancel_running_job()` - Cancel mid-indexing
   - `test_multiple_projects_parallel()` - Index multiple projects simultaneously

2. **CLI Integration**:
   - `test_cli_background_flag()` - CLI `--background` flag works
   - `test_cli_job_status()` - CLI `status` command shows correct info
   - `test_cli_pause_resume()` - CLI pause/resume commands work
   - `test_cli_cancel()` - CLI cancel command works

3. **MCP Integration**:
   - `test_mcp_start_background_indexing()` - MCP tool starts job
   - `test_mcp_get_indexing_status()` - MCP tool returns status

## Implementation Checklist

### Files to Create
- [ ] `src/memory/background_indexer.py` - Main background indexer class
- [ ] `src/memory/job_state_manager.py` - Job state tracking
- [ ] `src/memory/notification_manager.py` - Notification system
- [ ] `tests/unit/test_background_indexer.py` - Unit tests
- [ ] `tests/unit/test_job_state_manager.py` - Job state tests
- [ ] `tests/unit/test_notification_manager.py` - Notification tests
- [ ] `tests/integration/test_background_indexing.py` - Integration tests

### Files to Modify
- [ ] `src/cli/index_command.py` - Add `--background` flag and job management commands
- [ ] `src/core/server.py` - Add MCP tools for background indexing
- [ ] `src/store/sqlite_store.py` - Add `indexing_jobs` table schema
- [ ] `CHANGELOG.md` - Add UX-018 entry

### Documentation Updates
- [ ] README.md - Document background indexing feature
- [ ] docs/CLI.md - Document new CLI commands
- [ ] docs/API.md - Document new MCP tools

## Success Criteria

1. ✅ **Background execution**: Indexing runs without blocking CLI
2. ✅ **Immediate search**: Search returns results on partially indexed projects
3. ✅ **Resume support**: Can resume after interruption with no data loss
4. ✅ **Notifications**: User notified on completion/errors
5. ✅ **Job management**: Can list, pause, resume, cancel jobs
6. ✅ **Test coverage**: 85%+ coverage for new code
7. ✅ **Performance**: No degradation to existing indexing speed
8. ✅ **Documentation**: All features documented

## Completion Summary

(To be filled upon completion)
