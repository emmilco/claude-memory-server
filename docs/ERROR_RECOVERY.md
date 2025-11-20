# Error Recovery & Troubleshooting Guide

**Last Updated:** November 20, 2025
**Version:** 4.0

---

## Overview

This guide provides step-by-step recovery procedures for common failure scenarios. Use the decision tree below to quickly identify your situation and jump to the appropriate recovery workflow.

## Quick Decision Tree

```
┌─────────────────────────────────────┐
│ What's the problem?                 │
└───────────┬─────────────────────────┘
            │
    ┌───────┴────────┬─────────────────┬────────────────┬──────────────┐
    │                │                 │                │              │
┌───▼────┐   ┌──────▼──────┐   ┌─────▼──────┐   ┌────▼───────┐  ┌──▼──────┐
│Qdrant  │   │Indexing     │   │Database    │   │Installation│  │Other    │
│Issues  │   │Failed       │   │Corrupted   │   │Failed      │  │Issues   │
└───┬────┘   └──────┬──────┘   └─────┬──────┘   └────┬───────┘  └──┬──────┘
    │               │                │               │              │
    ▼               ▼                ▼               ▼              ▼
Section 1       Section 2        Section 3       Section 4      Section 5
```

---

## Section 1: Qdrant Connection & Corruption Issues

### Problem: Qdrant won't start or connection fails

**Symptoms:**
- `Connection refused` errors
- `Failed to connect to Qdrant` messages
- Health check fails with Qdrant errors

**Recovery Steps:**

#### Step 1: Check Qdrant Status
```bash
# Check if Qdrant is running
docker ps | grep qdrant

# Check Qdrant health
curl http://localhost:6333/health
```

#### Step 2: Restart Qdrant
```bash
# Stop Qdrant
docker-compose down

# Start Qdrant
docker-compose up -d

# Verify it's running
curl http://localhost:6333/health
# Should return: {"status":"ok"}
```

#### Step 3: If Qdrant Still Fails

**Option A: Fresh Qdrant Install**
```bash
# Stop and remove old containers
docker-compose down -v  # WARNING: -v removes volumes (data loss)

# Remove Qdrant data directory
rm -rf ~/.qdrant/

# Start fresh
docker-compose up -d

# Verify
curl http://localhost:6333/health
```

**Option B: Switch to SQLite (No Docker Required)**
```bash
# Edit .env file
echo "STORAGE_BACKEND=qdrant" > .env
echo "SQLITE_DB_PATH=~/.claude-rag/sqlite.db" >> .env

# Restart server
# No Docker needed - SQLite runs in-process
```

### Problem: Qdrant Data Corrupted

**Symptoms:**
- Search returns errors
- Collections not found
- Data inconsistencies

**Recovery Steps:**

#### Option 1: Restore from Backup (Recommended)
```bash
# If you have a backup
python -m src.cli backup restore --file ~/backups/memory-backup-YYYY-MM-DD.tar.gz

# Verify restoration
python -m src.cli health
```

#### Option 2: Rebuild from Scratch
```bash
# WARNING: This deletes all data

# 1. Stop server
docker-compose down

# 2. Delete Qdrant data
docker volume rm claude-memory-server_qdrant-data
# OR
rm -rf ~/.qdrant/

# 3. Start fresh
docker-compose up -d

# 4. Re-index your code (if you have the source)
python -m src.cli index /path/to/your/code --project-name my-project

# 5. Re-create memories (restore from export if available)
python -m src.cli import ~/backups/memories-export.json
```

---

## Section 2: Indexing Failures

### Problem: Indexing breaks mid-way

**Symptoms:**
- Indexing stops with errors
- Partial project indexing
- Some files indexed, others missing

**Recovery Steps:**

#### Step 1: Check What's Indexed
```bash
# Get project status
python -m src.cli status

# List indexed files
python -m src.cli list-files --project-name my-project
```

#### Step 2: Resume Indexing
```bash
# The indexer is incremental - just re-run it
python -m src.cli index /path/to/code --project-name my-project

# It will skip already-indexed files and only process new/changed ones
```

#### Step 3: If Errors Persist

**Check for problematic files:**
```bash
# Run with verbose logging
python -m src.cli index /path/to/code --project-name my-project --verbose

# Check logs
tail -f ~/.claude-rag/indexing.log
```

**Common Issues:**

| Error | Cause | Solution |
|-------|-------|----------|
| `Permission denied` | File not readable | `chmod +r problematic_file.py` |
| `File too large` | File exceeds size limit | Skip large files or increase limit in config |
| `Encoding error` | Non-UTF-8 file | Convert to UTF-8 or skip file |
| `Parser failed` | Corrupted/invalid syntax | Fix syntax or skip file |

**Skip problematic files:**
```bash
# Add to .gitignore-style exclude file
echo "problematic_file.py" >> ~/.claude-rag/index-exclude.txt

# Re-run indexing
python -m src.cli index /path/to/code --project-name my-project
```

#### Step 4: Force Full Re-index
```bash
# Delete project index and start fresh
python -m src.cli delete-project --project-name my-project

# Re-index from scratch
python -m src.cli index /path/to/code --project-name my-project
```

---

## Section 3: Database Corruption & Pollution

### Problem: Database is corrupted

**Symptoms:**
- Inconsistent search results
- Missing memories
- Database errors in logs

**Recovery Steps:**

#### Step 1: Verify Database Health
```bash
# Run health check
python -m src.cli health

# Check for corruption indicators
python -m src.cli health --verbose
```

#### Step 2: Backup Current State (Even if Corrupted)
```bash
# Create emergency backup
python -m src.cli backup create --output ~/emergency-backup-$(date +%Y%m%d).tar.gz

# Export memories to JSON (human-readable)
python -m src.cli export ~/emergency-export.json
```

#### Step 3: Attempt Repair

**For SQLite:**
```bash
# SQLite has built-in integrity check
sqlite3 ~/.claude-rag/sqlite.db "PRAGMA integrity_check;"

# If errors found, try to recover
python -m src.cli repair-database
```

**For Qdrant:**
```bash
# Qdrant doesn't have repair - need to rebuild
# See "Qdrant Data Corrupted" section above
```

#### Step 4: Restore from Backup
```bash
# Stop server
# (If using Qdrant)
docker-compose down

# Restore from most recent backup
python -m src.cli backup restore --file ~/backups/memory-backup-YYYY-MM-DD.tar.gz

# Verify restoration
python -m src.cli health
```

### Problem: Database polluted with incorrect data

**Symptoms:**
- Irrelevant search results
- Too many low-quality memories
- Duplicate memories

**Recovery Steps:**

#### Step 1: Identify Bad Data
```bash
# List all memories (paginated)
python -m src.cli list --limit 100

# Filter by category
python -m src.cli list --category FACT --limit 100

# Search for specific issues
python -m src.cli search "problematic content" --limit 50
```

#### Step 2: Delete Bad Memories

**Single memory:**
```bash
# Delete by ID
python -m src.cli delete <memory-id>
```

**Bulk delete:**
```bash
# Use bulk delete with filters
python -m src.cli bulk-delete \
  --category SESSION_STATE \
  --max-age-days 7 \
  --dry-run  # Preview what will be deleted

# Remove dry-run to actually delete
python -m src.cli bulk-delete \
  --category SESSION_STATE \
  --max-age-days 7
```

**Delete entire category:**
```bash
# Export first (backup!)
python -m src.cli export ~/backup-before-cleanup.json

# Delete all session state memories
python -m src.cli bulk-delete --category SESSION_STATE --force
```

#### Step 3: Run Consolidation
```bash
# Find and merge duplicate memories
python -m src.cli consolidate \
  --similarity-threshold 0.9 \
  --auto-merge

# Review merge candidates
python -m src.cli consolidate --dry-run
```

---

## Section 4: Installation & Setup Failures

### Problem: Installation fails

**Common Scenarios & Solutions:**

#### Scenario 1: Python Version Too Old

**Error:** `Python 3.13+ required`

**Solution:**
```bash
# Install Python 3.13+
# macOS:
brew install python@3.13

# Ubuntu:
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt update
sudo apt install python3.13 python3.13-venv

# Verify
python3.13 --version
```

#### Scenario 2: Docker Not Available

**Error:** `Cannot connect to Docker daemon`

**Solution A: Install Docker**
```bash
# Follow: https://docs.docker.com/get-docker/
```

**Solution B: Use SQLite (No Docker Required)**
```bash
# Run setup with minimal preset
python setup.py --preset minimal

# This uses SQLite instead of Qdrant - no Docker needed
```

#### Scenario 3: Rust Build Fails

**Error:** `Rust compiler not found` or `cargo build failed`

**Solution A: Install Rust**
```bash
# Install Rust toolchain
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh

# Restart terminal
source ~/.cargo/env

# Retry setup
python setup.py
```

**Solution B: Use Python Parser (No Rust Required)**
```bash
# Run setup with Python parser
python setup.py --preset minimal

# Or manually configure
echo "USE_RUST_PARSER=false" >> .env
```

#### Scenario 4: Dependencies Install Failed

**Error:** `Failed to install requirements`

**Solution:**
```bash
# Try manual installation
python3.13 -m pip install --upgrade pip
python3.13 -m pip install -r requirements.txt

# If specific package fails, install individually
python3.13 -m pip install sentence-transformers
python3.13 -m pip install qdrant-client
# etc.

# Check for conflicts
python3.13 -m pip check
```

### Problem: Setup wizard fails

**Recovery Steps:**

```bash
# 1. Check prerequisites
python setup.py --check-only

# 2. Run minimal setup (fastest, fewest dependencies)
python setup.py --preset minimal

# 3. If still fails, manual setup
python3.13 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 4. Configure manually
cp .env.example .env
# Edit .env with your settings

# 5. Verify
python -m src.cli health
```

---

## Section 5: Other Common Issues

### Problem: Slow search performance

**Diagnosis:**
```bash
# Run performance benchmark
python scripts/benchmark_scale.py

# Check cache hit rate
python -m src.cli health | grep "Cache"

# Check database size
python -m src.cli stats
```

**Solutions:**

1. **Enable caching:**
```bash
echo "ENABLE_CACHE=true" >> .env
echo "CACHE_SIZE=10000" >> .env
```

2. **Archive old projects:**
```bash
# Archive inactive projects
python -m src.cli archive --project-name old-project

# List archived
python -m src.cli list-archives
```

3. **Clean up old data:**
```bash
# Run cleanup job
python -m src.cli cleanup \
  --archive-threshold-days 90 \
  --delete-threshold-days 180
```

### Problem: Memory retrieval returns no results

**Diagnosis:**
```bash
# Check if memories exist
python -m src.cli stats

# Try exact search
python -m src.cli search "exact content" --mode keyword

# Check if embeddings generated
python -m src.cli health --check-embeddings
```

**Solutions:**

1. **Re-generate embeddings:**
```bash
# Force embedding regeneration
python -m src.cli reindex --regenerate-embeddings
```

2. **Check search mode:**
```bash
# Try different search modes
python -m src.cli search "query" --mode semantic
python -m src.cli search "query" --mode keyword
python -m src.cli search "query" --mode hybrid
```

3. **Adjust similarity threshold:**
```bash
# Lower threshold for more results
echo "MIN_SIMILARITY=0.3" >> .env  # Default: 0.5
```

### Problem: Permission errors

**Error:** `Permission denied` when accessing files

**Solutions:**

```bash
# Fix data directory permissions
chmod -R 755 ~/.claude-rag/

# Fix cache permissions
chmod -R 755 ~/.cache/claude-rag/

# Fix log permissions
chmod -R 644 ~/.claude-rag/*.log
```

---

## Section 6: Complete System Reset

### When to use a complete reset

- All recovery attempts have failed
- Database is beyond repair
- Starting fresh is faster than fixing

### Full Reset Procedure

**WARNING: This deletes ALL data. Backup first!**

```bash
# 1. Create final backup
python -m src.cli backup create --output ~/final-backup-$(date +%Y%m%d).tar.gz
python -m src.cli export ~/final-export.json

# 2. Stop all services
docker-compose down -v

# 3. Delete all data
rm -rf ~/.claude-rag/
rm -rf ~/.cache/claude-rag/
rm -rf ~/.qdrant/

# 4. Delete project configuration
rm .env

# 5. Reinstall
python setup.py

# 6. Restore from backup (optional)
python -m src.cli backup restore --file ~/final-backup-YYYYMMDD.tar.gz

# 7. Verify
python -m src.cli health
```

---

## Backup & Prevention Best Practices

### Automated Backups

```bash
# Set up daily backups (cron)
# Add to crontab (crontab -e):
0 2 * * * python /path/to/claude-memory-server/scripts/backup.py

# Or use scheduler
python -m src.cli schedule-backup --frequency daily --time "02:00"
```

### Pre-Operation Backups

**Before risky operations, always backup:**

```bash
# Before bulk delete
python -m src.cli backup create --output ~/pre-delete-backup.tar.gz
python -m src.cli bulk-delete [...]

# Before consolidation
python -m src.cli backup create --output ~/pre-consolidate-backup.tar.gz
python -m src.cli consolidate [...]

# Before upgrade
python -m src.cli backup create --output ~/pre-upgrade-backup.tar.gz
git pull
pip install -r requirements.txt --upgrade
```

### Export Critical Data

```bash
# Export high-importance memories regularly
python -m src.cli export ~/exports/preferences-$(date +%Y%m%d).json \
  --category PREFERENCE \
  --min-importance 0.7
```

---

## Getting Help

If recovery steps don't work:

1. **Check Logs:**
   ```bash
   tail -f ~/.claude-rag/server.log
   tail -f ~/.claude-rag/security.log
   tail -f ~/.claude-rag/indexing.log
   ```

2. **Enable Debug Mode:**
   ```bash
   echo "LOG_LEVEL=DEBUG" >> .env
   python -m src.mcp_server
   ```

3. **Report Issue:**
   - GitHub Issues: https://github.com/anthropics/claude-memory-server/issues
   - Include: error message, logs, steps to reproduce
   - Use `python -m src.cli health --verbose` output

4. **Community Support:**
   - Discord: [Link to community]
   - Forum: [Link to forum]

---

## Appendix: Common Error Messages

| Error | Meaning | Quick Fix |
|-------|---------|-----------|
| `ReadOnlyError` | Attempted write in read-only mode | Remove `READ_ONLY=true` from .env |
| `ValidationError` | Invalid input data | Check input format matches schema |
| `StorageError` | Database operation failed | Check database health, try backup/restore |
| `EmbeddingError` | Embedding generation failed | Check model is downloaded, try clearing cache |
| `IndexingError` | File indexing failed | Check file permissions, syntax |
| `ConnectionError` | Can't connect to Qdrant | Restart Qdrant, or switch to SQLite |
| `CacheError` | Cache operation failed | Clear cache: `rm -rf ~/.cache/claude-rag/` |
| `SecurityError` | Blocked by security validation | Check for injection attempts, review input |

---

**Document Version:** 1.0
**Covers:** Claude Memory RAG Server v4.0
**Last Verified:** November 18, 2025
