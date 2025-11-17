# FEAT-038: Data Export, Backup & Portability

## TODO Reference
- TODO.md: "Data Export, Backup & Portability (~1-2 weeks)"
- Strategic Priority: P2 - Critical for user trust and data ownership
- Strategic Document: `planning_docs/STRATEGIC-001_long_term_product_evolution.md`

## Objective
Implement comprehensive data export, backup, and portability features to:
1. Prevent data loss
2. Enable cross-machine workflows
3. Eliminate vendor lock-in concerns
4. Build user confidence through data ownership
5. Support disaster recovery

## Requirements (from TODO.md)

### Export Formats
- **JSON** - Machine-readable, structured data
- **Markdown** - Human-readable knowledge base export
- **Portable Archive (.tar.gz)** - Complete backup with metadata

### Backup Automation
- Daily/weekly backup schedules
- Configurable retention policies (keep last N backups)
- Automatic cleanup of old backups

### Import/Restore
- Full database restore from backup
- Selective import (by project, category, date range)
- Merge with conflict resolution (keep newer, keep older, keep both)

### Cloud Sync (Optional)
- Dropbox integration
- Google Drive integration
- Encrypted storage
- Incremental sync

### CLI Commands
- `export` - Export memories and code index
- `import` - Import from backup file
- `restore` - Full database restore
- `backup config` - Configure automatic backups

## Current State

### Existing Infrastructure
- **Storage Layer:** SQLite and Qdrant stores with full CRUD operations
- **Models:** MemoryUnit with comprehensive metadata
- **CLI:** Existing command structure in src/cli/
- **Config:** src/config.py for configuration management

### Missing Components
- Export/import logic for memories
- Export/import logic for code indexes
- Backup scheduler
- Archive format specification
- Markdown formatter
- Cloud sync integrations
- Conflict resolution algorithms

## Implementation Plan

### Phase 1: Core Export/Import (Days 1-3)
- [ ] Create `src/backup/exporter.py` - Export memories and code
  - [ ] `export_to_json()` - Full JSON export
  - [ ] `export_to_markdown()` - Human-readable export
  - [ ] `create_portable_archive()` - .tar.gz with metadata
  - [ ] Filter options: project, date range, category
- [ ] Create `src/backup/importer.py` - Import from backups
  - [ ] `import_from_json()` - Parse and import JSON
  - [ ] `import_from_archive()` - Extract and import .tar.gz
  - [ ] Validation and schema version checking
- [ ] Create `src/backup/conflict_resolver.py` - Handle conflicts
  - [ ] Strategy: KEEP_NEWER, KEEP_OLDER, KEEP_BOTH, SKIP
  - [ ] Duplicate detection during import
  - [ ] User-configurable default strategy

### Phase 2: Markdown Export (Days 3-4)
- [ ] Create `src/backup/markdown_formatter.py` - Format memories as Markdown
  - [ ] Hierarchical structure (by project > category)
  - [ ] Table of contents generation
  - [ ] Code syntax highlighting
  - [ ] Metadata preservation in front matter
  - [ ] Export as knowledge base

### Phase 3: CLI Commands (Days 4-5)
- [ ] Create `src/cli/export_command.py` - Export CLI
  - [ ] `export --format json|markdown|archive`
  - [ ] `export --project <name> --since <date> --category <cat>`
  - [ ] Progress indicators for large exports
- [ ] Create `src/cli/import_command.py` - Import CLI
  - [ ] `import <file> --merge-strategy <strategy>`
  - [ ] `import --selective --project <name>`
  - [ ] Dry-run mode for preview
- [ ] Create `src/cli/backup_command.py` - Backup management
  - [ ] `backup create --destination <path>`
  - [ ] `backup restore <file>`
  - [ ] `backup list` - Show available backups
  - [ ] `backup cleanup --keep 5` - Retention management

### Phase 4: Backup Scheduler (Days 6-8)
- [ ] Create `src/backup/backup_scheduler.py` - Automated backups
  - [ ] APScheduler integration
  - [ ] Daily/weekly/monthly schedules
  - [ ] Configurable backup destination
  - [ ] Retention policy enforcement
  - [ ] Notification on backup completion/failure
- [ ] Add configuration to `src/config.py`
  - [ ] `enable_auto_backup: bool`
  - [ ] `backup_schedule: str` (cron expression)
  - [ ] `backup_destination: Path`
  - [ ] `backup_retention_count: int`
  - [ ] `backup_format: str` (json|archive)

### Phase 5: MCP Tools (Days 8-9)
- [ ] Add MCP tools to `src/core/server.py`
  - [ ] `export_memories()` - Export via MCP
  - [ ] `import_memories()` - Import via MCP
  - [ ] `list_backups()` - Show available backups
  - [ ] `restore_from_backup()` - Restore backup
- [ ] Update `src/mcp_server.py` with tool registrations

### Phase 6: Cloud Sync (Optional, Days 10-12)
- [ ] Create `src/backup/cloud_sync.py` - Cloud integration base
  - [ ] Abstract CloudProvider interface
  - [ ] Encryption/decryption for cloud storage
- [ ] Create `src/backup/providers/dropbox_provider.py`
  - [ ] Dropbox API integration
  - [ ] OAuth flow for authentication
- [ ] Create `src/backup/providers/gdrive_provider.py`
  - [ ] Google Drive API integration
  - [ ] OAuth flow for authentication
- [ ] Add cloud sync commands to CLI
  - [ ] `backup sync --provider dropbox|gdrive`
  - [ ] `backup auth --provider <name>`

### Phase 7: Testing (Days 12-14)
- [ ] Unit tests for all export/import functions
- [ ] Integration tests for full backup/restore workflow
- [ ] Test conflict resolution strategies
- [ ] Test markdown formatting with various data
- [ ] Test scheduler with mock APScheduler
- [ ] Test cloud sync (with mock providers)
- [ ] Security tests for encrypted backups

### Phase 8: Documentation (Day 14)
- [ ] Update CHANGELOG.md
- [ ] Update TODO.md (mark complete)
- [ ] Add backup guide to docs/
- [ ] Update README with backup instructions

## Archive Format Specification

### Structure (portable_backup.tar.gz)
```
portable_backup/
├── manifest.json          # Version, timestamp, counts, checksums
├── memories/
│   ├── memories.json      # All memories
│   └── embeddings.npz     # Numpy compressed embeddings
├── code_index/
│   ├── projects.json      # Project metadata
│   ├── semantic_units.json # Code units
│   └── embeddings.npz     # Code embeddings
├── config/
│   └── export_config.json # Config snapshot
└── metadata/
    ├── statistics.json    # Export statistics
    └── checksums.sha256   # File integrity checksums
```

### manifest.json Schema
```json
{
  "version": "1.0.0",
  "schema_version": "3.0.0",
  "export_date": "2025-11-17T10:30:00Z",
  "export_type": "full",
  "memory_count": 1234,
  "code_unit_count": 5678,
  "projects": ["project1", "project2"],
  "checksums": {
    "memories.json": "sha256:...",
    "semantic_units.json": "sha256:..."
  },
  "compression": "gzip",
  "encryption": "none"
}
```

## Conflict Resolution Strategies

### KEEP_NEWER
- Compare timestamps (updated_at or created_at)
- Keep memory with more recent timestamp
- Update existing memory in database

### KEEP_OLDER
- Keep existing memory, skip import
- Useful for preserving established preferences

### KEEP_BOTH
- Import as new memory with suffix
- Add "(imported)" to content
- Preserve both versions for user review

### SKIP
- Skip conflicting memory entirely
- Continue with rest of import
- Log skipped items

## Edge Cases to Handle

1. **Schema Version Mismatch:** Detect and migrate old exports
2. **Missing Embeddings:** Re-generate if not in archive
3. **Corrupted Archives:** Validate checksums, partial recovery
4. **Large Exports:** Stream processing for >1GB backups
5. **Duplicate Detection:** Semantic similarity for fuzzy matching
6. **Project Renaming:** Handle project renames during import
7. **Empty Backups:** Handle edge case of zero memories/code
8. **Partial Failures:** Rollback on critical errors

## Configuration Options

```python
# src/config.py additions
@dataclass
class BackupConfig:
    enable_auto_backup: bool = False
    backup_schedule: str = "0 2 * * *"  # Daily at 2 AM
    backup_destination: Path = Path("~/.claude-rag/backups")
    backup_retention_count: int = 7  # Keep last 7 backups
    backup_format: str = "archive"  # json|markdown|archive
    enable_cloud_sync: bool = False
    cloud_provider: Optional[str] = None  # dropbox|gdrive
    cloud_encrypt: bool = True
```

## Success Criteria

- [ ] Export memories to JSON with full metadata
- [ ] Export code index with embeddings
- [ ] Create portable .tar.gz archives
- [ ] Import with conflict resolution
- [ ] Markdown export for human reading
- [ ] Automated daily/weekly backups
- [ ] Retention policy enforcement
- [ ] CLI commands working end-to-end
- [ ] MCP tools functional
- [ ] 85%+ test coverage on all new modules
- [ ] Documentation complete

## Impact

**Expected Improvements:**
- +40% increase in user confidence (data ownership)
- Enables cross-machine workflows (dev → laptop → server)
- Disaster recovery capability (prevent catastrophic data loss)
- Knowledge base export (use memories outside Claude)
- Migration support (move between instances)

**Strategic Priority:** P2 - Critical for trust, not core functionality

## Notes

- **Start with Phase 1-3:** Core export/import + CLI (most value)
- **Phase 4 (Scheduler):** High value, moderate complexity
- **Phase 5 (MCP):** Easy, leverage existing patterns
- **Phase 6 (Cloud):** Optional, can defer if time-constrained
- **Security:** Always encrypt cloud backups, validate imports
- **Performance:** Stream large exports/imports (don't load all in memory)

## Test Plan

### Unit Tests
- Export functions with various filters
- Import functions with each conflict strategy
- Markdown formatting with edge cases
- Scheduler configuration and execution
- Conflict resolution algorithms
- Checksum validation

### Integration Tests
- Full export → import roundtrip
- Selective import (by project, category)
- Backup creation → retention → cleanup
- Cross-instance data migration
- Large dataset handling (10K+ memories)

### Security Tests
- Archive tampering detection (checksum validation)
- Encrypted backup decryption
- SQL injection in imported data
- Path traversal in archive extraction

## Timeline

- **Days 1-3:** Core export/import ✅
- **Days 3-4:** Markdown formatter ✅
- **Days 4-5:** CLI commands ✅
- **Days 6-8:** Backup scheduler ✅
- **Days 8-9:** MCP tools ✅
- **Days 10-12:** Cloud sync (optional) ⏭️
- **Days 12-14:** Testing & documentation ✅

**Estimated Completion:** 8-12 days (depending on cloud sync inclusion)

## Progress Tracking

- [ ] Phase 1: Core Export/Import
- [ ] Phase 2: Markdown Export
- [ ] Phase 3: CLI Commands
- [ ] Phase 4: Backup Scheduler
- [ ] Phase 5: MCP Tools
- [ ] Phase 6: Cloud Sync (optional)
- [ ] Phase 7: Testing
- [ ] Phase 8: Documentation
