# CLI Command Audit - SIMPLIFY-001

## Summary

- **Total CLI command files:** 31
- **Files to REMOVE entirely:** 10
- **Files to MODIFY:** 7
- **Files to KEEP (no changes):** 14

## Commands to REMOVE

### 1. health_dashboard_command.py
- **Purpose:** Display health dashboard with memory lifecycle metrics
- **Imports from removed modules:**
  - `src.memory.health_scorer`
  - `src.memory.lifecycle_manager`
  - `src.memory.health_jobs`
- **Reason:** Entirely depends on removed health modules

### 2. health_monitor_command.py
- **Purpose:** Continuous health monitoring with alerts and auto-remediation
- **Imports from removed modules:**
  - `src.monitoring.alert_engine`
  - `src.monitoring.health_reporter`
  - `src.monitoring.remediation`
  - `src.memory.project_archival`
- **Registration:** Lines 18, 360-404, 477-479 in `__init__.py`
- **Reason:** Depends on removed monitoring modules

### 3. health_schedule_command.py
- **Purpose:** Configure automated health maintenance schedules
- **Imports from removed modules:**
  - `src.memory.health_scheduler`
  - `src.memory.health_jobs`
- **Reason:** Entirely depends on removed health_scheduler

### 4. tags_command.py
- **Purpose:** Tag CRUD operations
- **Imports from removed modules:**
  - `src.tagging.tag_manager`
  - `src.tagging.models`
- **Reason:** Entire tagging system being removed

### 5. collections_command.py
- **Purpose:** Memory collection management
- **Imports from removed modules:**
  - `src.tagging.collection_manager`
  - `src.tagging.models`
- **Reason:** Tagging system being removed

### 6. auto_tag_command.py
- **Purpose:** Auto-tag memories based on content analysis
- **Imports from removed modules:**
  - `src.tagging.auto_tagger`
  - `src.tagging.tag_manager`
- **Reason:** Auto-tagging feature being removed

### 7. analytics_command.py
- **Purpose:** View token usage analytics
- **Imports from removed modules:**
  - `src.analytics.token_tracker`
- **Registration:** Lines 16, 317-345, 466-472 in `__init__.py`
- **Reason:** Analytics module being removed

### 8. backup_command.py
- **Purpose:** Backup/restore memory database
- **Imports from removed modules:**
  - `src.backup.exporter`
  - `src.backup.importer`
  - `src.backup.file_lock`
- **Reason:** Entire backup module being removed

### 9. export_command.py
- **Purpose:** Export memories to multiple formats
- **Imports from removed modules:**
  - `src.backup.exporter`
- **Reason:** Depends on removed backup module

### 10. import_command.py
- **Purpose:** Import memories from backup files
- **Imports from removed modules:**
  - `src.backup.importer`
- **Reason:** Depends on removed backup module

## Commands to MODIFY

### 1. __init__.py (PRIORITY 1)
**Changes required:**
- Remove import line 16: `from src.cli.analytics_command import run_analytics_command`
- Remove import line 18: `from src.cli.health_monitor_command import HealthMonitorCommand`
- Remove lines 317-345: analytics_parser definition
- Remove lines 360-404: health_monitor_parser definition
- Remove lines 466-472: analytics command handler
- Remove lines 477-479: health-monitor command handler

### 2. health_command.py
**Changes required:**
- Remove `check_python_parser()` references (lines 110-123)
- Remove recommendations about removed features

### 3. archival_command.py
**Changes required:**
- Remove `export_project()` function (uses ArchiveExporter)
- Remove `import_project()` function (uses ArchiveImporter)
- Remove `list_exportable()` function
- Keep `show_status()`, `archive_project()`, `reactivate_project()`

### 4. session_summary_command.py
- Audit for analytics module references

### 5. status_command.py
- Audit for analytics/health monitoring references

### 6. index_command.py
- Audit for analytics usage

### 7. prune_command.py
- Review for lifecycle/archival dependencies

## File Actions

### DELETE (10 files)
```
src/cli/health_dashboard_command.py
src/cli/health_monitor_command.py
src/cli/health_schedule_command.py
src/cli/tags_command.py
src/cli/collections_command.py
src/cli/auto_tag_command.py
src/cli/analytics_command.py
src/cli/backup_command.py
src/cli/export_command.py
src/cli/import_command.py
```

### MODIFY (7 files)
```
src/cli/__init__.py (PRIORITY 1)
src/cli/health_command.py
src/cli/archival_command.py
src/cli/session_summary_command.py
src/cli/status_command.py
src/cli/index_command.py
src/cli/prune_command.py
```

## Estimated LOC Removal

| Feature | Files | LOC |
|---------|-------|-----|
| Health Monitoring | 3 | ~1,100 |
| Tagging System | 3 | ~550 |
| Analytics | 1 | ~210 |
| Backup/Export/Import | 3 | ~1,150 |
| **TOTAL** | 10 | **~3,010** |
