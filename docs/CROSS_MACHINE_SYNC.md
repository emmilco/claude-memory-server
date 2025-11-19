# Cross-Machine Synchronization Guide

**Last Updated:** November 18, 2025
**Version:** 4.0

---

## Overview

This guide explains how to synchronize your Claude Memory RAG Server data across multiple machines, enabling you to maintain a consistent memory base on your laptop, desktop, and work machine.

## Table of Contents

1. [Quick Start](#quick-start)
2. [Synchronization Methods](#synchronization-methods)
3. [Automated Sync Setup](#automated-sync-setup)
4. [Manual Sync Workflows](#manual-sync-workflows)
5. [Conflict Resolution](#conflict-resolution)
6. [Best Practices](#best-practices)
7. [Troubleshooting](#troubleshooting)

---

## Quick Start

### 30-Second Setup

**On Machine A (Primary):**
```bash
# Create a backup
python -m src.cli backup create --output ~/Dropbox/claude-memory/backup.tar.gz
```

**On Machine B (Secondary):**
```bash
# Restore the backup
python -m src.cli backup restore --file ~/Dropbox/claude-memory/backup.tar.gz
```

Done! Your memories are now synced.

---

## Synchronization Methods

### Method 1: Cloud Storage (Recommended)

**Best for:** Automatic synchronization with minimal setup

**Supported Services:**
- Dropbox
- Google Drive
- iCloud Drive
- OneDrive
- Any mounted cloud folder

**Pros:**
- ✅ Automatic synchronization
- ✅ Version history
- ✅ Works across all platforms
- ✅ No manual intervention

**Cons:**
- ⚠️ Requires cloud storage account
- ⚠️ May incur storage costs
- ⚠️ Depends on internet connection

### Method 2: Git Repository (Advanced)

**Best for:** Version control and team collaboration

**Pros:**
- ✅ Full version history
- ✅ Branching and merging
- ✅ Team collaboration
- ✅ Fine-grained control

**Cons:**
- ⚠️ More complex setup
- ⚠️ Requires Git knowledge
- ⚠️ Manual commit/push workflow

### Method 3: Network Share (LAN)

**Best for:** Home/office networks with multiple machines

**Pros:**
- ✅ Fast synchronization
- ✅ No cloud dependency
- ✅ Low latency

**Cons:**
- ⚠️ Machines must be on same network
- ⚠️ No remote access
- ⚠️ Requires network setup

### Method 4: Manual Export/Import

**Best for:** Occasional synchronization or offline scenarios

**Pros:**
- ✅ Complete control
- ✅ Works offline
- ✅ No dependencies

**Cons:**
- ⚠️ Manual process
- ⚠️ Easy to forget
- ⚠️ Potential for conflicts

---

## Automated Sync Setup

### Option A: Cloud Storage + Scheduled Backups

#### Step 1: Set Up Cloud Folder

**Dropbox Example:**
```bash
# Create sync folder in Dropbox
mkdir -p ~/Dropbox/claude-memory/backups

# Configure backup scheduler to use this location
python -m src.cli schedule enable \
  --frequency daily \
  --time "02:00" \
  --retention-days 30 \
  --max-backups 10

# Edit the backup config to use Dropbox
# Edit ~/.claude-rag/backup_schedule.json
# Set: "backup_dir": "~/Dropbox/claude-memory/backups"
```

**Google Drive Example:**
```bash
# Create sync folder
mkdir -p ~/Google\ Drive/claude-memory/backups

# Configure scheduler
python -m src.cli schedule enable \
  --frequency daily \
  --time "02:00" \
  --retention-days 30
```

#### Step 2: Automatic Restore on Other Machines

Create a restore script on each secondary machine:

```bash
#!/bin/bash
# restore-latest.sh - Auto-restore from cloud backup

BACKUP_DIR="$HOME/Dropbox/claude-memory/backups"
LATEST_BACKUP=$(ls -t "$BACKUP_DIR"/auto_backup_*.tar.gz 2>/dev/null | head -1)

if [ -z "$LATEST_BACKUP" ]; then
    echo "No backups found in $BACKUP_DIR"
    exit 1
fi

echo "Restoring from: $(basename "$LATEST_BACKUP")"

# Restore
python -m src.cli backup restore --file "$LATEST_BACKUP" --strategy merge

echo "Restore complete!"
```

**Make it executable:**
```bash
chmod +x restore-latest.sh
```

**Run periodically (add to crontab):**
```bash
# Edit crontab
crontab -e

# Add line to restore every 6 hours
0 */6 * * * /path/to/restore-latest.sh >> /path/to/restore.log 2>&1
```

### Option B: Git-Based Sync

#### Step 1: Initialize Git Repository

**On Primary Machine:**
```bash
# Create git repo for memories
mkdir -p ~/claude-memory-sync
cd ~/claude-memory-sync
git init

# Export memories to JSON (easier to diff than binary)
python -m src.cli export memories.json

# Commit
git add memories.json
git commit -m "Initial memory export"

# Push to remote (GitHub/GitLab/etc.)
git remote add origin https://github.com/yourusername/claude-memories.git
git push -u origin main
```

#### Step 2: Set Up Automatic Sync

Create sync script:

```bash
#!/bin/bash
# sync-memories.sh - Bidirectional sync via Git

SYNC_DIR="$HOME/claude-memory-sync"
EXPORT_FILE="$SYNC_DIR/memories.json"

cd "$SYNC_DIR"

# Pull latest changes
git pull origin main

# Import any remote changes
if [ -f "$EXPORT_FILE" ]; then
    python -m src.cli import "$EXPORT_FILE" --strategy merge
fi

# Export local memories
python -m src.cli export "$EXPORT_FILE"

# Commit and push if changes
if ! git diff --quiet "$EXPORT_FILE"; then
    git add "$EXPORT_FILE"
    git commit -m "Sync from $(hostname) at $(date -Iseconds)"
    git push origin main
fi

echo "Sync complete!"
```

**Schedule it:**
```bash
# Run every 4 hours
0 */4 * * * /path/to/sync-memories.sh >> /path/to/sync.log 2>&1
```

---

## Manual Sync Workflows

### Scenario 1: Moving from Laptop to Desktop

**On Laptop:**
```bash
# 1. Create backup
python -m src.cli backup create --output ~/backup-laptop.tar.gz

# 2. Transfer file to Desktop
# Via USB, email, cloud, etc.
```

**On Desktop:**
```bash
# 3. Restore backup
python -m src.cli backup restore --file ~/backup-laptop.tar.gz --strategy merge
```

### Scenario 2: Syncing Recent Changes Only

**Export recent memories from Laptop:**
```bash
# Export memories from last 7 days
python -m src.cli export recent.json \
  --date-from $(date -d '7 days ago' -Iseconds)

# Transfer recent.json to Desktop
```

**Import on Desktop:**
```bash
# Import with merge strategy (preserves existing)
python -m src.cli import recent.json --strategy merge
```

### Scenario 3: Selective Project Sync

**Export specific project from Machine A:**
```bash
# Export only "work-project"
python -m src.cli export work-memories.json \
  --project-name work-project
```

**Import on Machine B:**
```bash
python -m src.cli import work-memories.json --strategy merge
```

---

## Conflict Resolution

### Understanding Conflict Strategies

When importing/restoring, you can choose how to handle conflicts:

| Strategy | Behavior | Use Case |
|----------|----------|----------|
| `skip` | Skip conflicting memories, keep existing | Conservative, prevent overwrites |
| `overwrite` | Replace existing with imported | Trust remote more than local |
| `merge` | Intelligently combine both | Default, safest option |

**Example:**
```bash
# Merge strategy (recommended)
python -m src.cli backup restore --file backup.tar.gz --strategy merge

# Skip conflicts (keep local)
python -m src.cli import memories.json --strategy skip

# Overwrite (trust remote)
python -m src.cli import memories.json --strategy overwrite
```

### Handling Duplicate Detection

The system automatically detects duplicates during merge:

```bash
# Preview what will be merged without applying
python -m src.cli import memories.json --strategy merge --dry-run

# Review duplicate candidates
python -m src.cli consolidate --dry-run

# Auto-merge confirmed duplicates
python -m src.cli consolidate --auto-merge --similarity-threshold 0.9
```

---

## Best Practices

### 1. Primary-Secondary Architecture

Designate one machine as "primary" for authoritative data:

**Primary Machine:**
- Daily automated backups to cloud storage
- All manual memory creation happens here
- Source of truth for conflicts

**Secondary Machines:**
- Periodic restore from cloud (read-mostly)
- Local changes exported and merged back to primary
- Use `merge` strategy when syncing

### 2. Regular Backup Schedule

```bash
# On primary machine
python -m src.cli schedule enable \
  --frequency daily \
  --time "02:00" \
  --retention-days 30 \
  --max-backups 10
```

### 3. Pre-Sync Backup

Always backup before major sync operations:

```bash
# Safety backup before restore
python -m src.cli backup create --output ~/pre-sync-backup.tar.gz

# Now safe to restore
python -m src.cli backup restore --file ~/cloud-backup.tar.gz --strategy merge
```

### 4. Version Naming Convention

Use descriptive backup names:

```bash
# Include machine name and purpose
python -m src.cli backup create --output ~/backups/laptop-presync-$(date +%Y%m%d).tar.gz
```

### 5. Verify After Sync

```bash
# Check memory count after sync
python -m src.cli stats

# Run health check
python -m src.cli health

# Test search to verify
python -m src.cli search "test query"
```

---

## Example Multi-Machine Setups

### Setup 1: Laptop + Desktop (Dropbox)

**Configuration:**
- Laptop: Primary (creates memories)
- Desktop: Secondary (reads memories)
- Dropbox: Central storage

**Laptop Setup:**
```bash
# Automated daily backup to Dropbox
python -m src.cli schedule enable \
  --frequency daily \
  --time "01:00"

# Configure backup location
# Edit ~/.claude-rag/backup_schedule.json
# "backup_dir": "~/Dropbox/claude-memory/backups"
```

**Desktop Setup:**
```bash
# Automated restore every 6 hours
# Add to crontab:
0 */6 * * * python -m src.cli backup restore \
  --file ~/Dropbox/claude-memory/backups/auto_backup_*.tar.gz \
  --strategy merge
```

### Setup 2: Work + Home + Laptop (Git)

**Configuration:**
- Git repository as central sync point
- All machines can create/modify
- Automatic sync every 4 hours

**All Machines:**
```bash
# Clone sync repository
git clone https://github.com/you/claude-memories.git ~/claude-sync

# Install sync script (see Git-Based Sync section)
# Schedule sync every 4 hours via cron
```

### Setup 3: Air-Gapped Machines (USB)

**Configuration:**
- No internet connectivity
- Manual USB transfer
- Weekly sync cycle

**Process:**
```bash
# Machine A: Export to USB
python -m src.cli backup create --output /media/usb/backup-$(date +%Y%m%d).tar.gz

# Transfer USB to Machine B

# Machine B: Import from USB
python -m src.cli backup restore --file /media/usb/backup-*.tar.gz --strategy merge
```

---

## Troubleshooting

### Problem: Backup file not syncing to cloud

**Diagnosis:**
```bash
# Check if cloud folder is mounted
ls -la ~/Dropbox/claude-memory/

# Check backup location
python -m src.cli schedule status
```

**Solution:**
```bash
# Ensure cloud sync client is running
# Verify backup directory is within synced folder
# Manually trigger backup to test
python -m src.cli schedule test
```

### Problem: Import fails with encoding errors

**Solution:**
```bash
# Try importing with error handling
python -m src.cli import memories.json --ignore-errors

# Or export to archive format instead (more robust)
python -m src.cli backup create --output backup.tar.gz
```

### Problem: Slow sync over network

**Solution:**
```bash
# Use compressed archive format
python -m src.cli backup create --output backup.tar.gz

# For incremental sync, export only recent changes
python -m src.cli export recent.json --date-from 2025-11-01T00:00:00Z
```

### Problem: Different machines have conflicting data

**Diagnosis:**
```bash
# Check for duplicates
python -m src.cli consolidate --dry-run

# Compare stats
python -m src.cli stats
```

**Solution:**
```bash
# 1. Backup both machines
python -m src.cli backup create --output machine-a-backup.tar.gz

# 2. Choose authoritative source and overwrite
python -m src.cli backup restore --file authoritative-backup.tar.gz --strategy overwrite

# 3. Or merge and manually review
python -m src.cli backup restore --file backup.tar.gz --strategy merge
python -m src.cli consolidate --dry-run
```

---

## Advanced: Cloud Sync Services Integration

### Dropbox API (Programmatic)

For fully automated cloud sync:

```python
# Example: Auto-upload to Dropbox after backup
import dropbox

def upload_to_dropbox(local_file, dropbox_path):
    dbx = dropbox.Dropbox(ACCESS_TOKEN)
    with open(local_file, 'rb') as f:
        dbx.files_upload(f.read(), dropbox_path, mode=WriteMode.overwrite)
```

### Webhook-Based Sync

Set up webhooks to trigger syncs on changes:

```bash
# When backup completes, trigger webhook
curl -X POST https://your-sync-service.com/webhook \
  -H "Content-Type: application/json" \
  -d '{"event": "backup_completed", "machine": "laptop"}'
```

---

## Security Considerations

### Encrypted Backups

For sensitive data:

```bash
# Encrypt backup before cloud upload
gpg --symmetric --cipher-algo AES256 backup.tar.gz

# Results in: backup.tar.gz.gpg

# Decrypt on other machine
gpg --decrypt backup.tar.gz.gpg > backup.tar.gz
```

### SSH-Based Transfer

For direct machine-to-machine sync:

```bash
# Create backup and transfer via SSH
python -m src.cli backup create --output /tmp/backup.tar.gz
scp /tmp/backup.tar.gz user@remote-machine:~/backups/

# On remote machine
ssh user@remote-machine "python -m src.cli backup restore --file ~/backups/backup.tar.gz"
```

---

## Summary

**Recommended Setup:**
1. Enable automated daily backups on primary machine
2. Save backups to cloud storage (Dropbox/Google Drive)
3. Set up periodic restore on secondary machines
4. Use `merge` strategy for conflict resolution
5. Keep 30 days of backup history

**Quick Commands:**
```bash
# Setup automation
python -m src.cli schedule enable --frequency daily --time "02:00"

# Manual sync
python -m src.cli backup create --output ~/Dropbox/claude-memory/backup.tar.gz
python -m src.cli backup restore --file ~/Dropbox/claude-memory/backup.tar.gz --strategy merge

# Check status
python -m src.cli schedule status
python -m src.cli stats
```

---

**Document Version:** 1.0
**Covers:** Claude Memory RAG Server v4.0
**Last Verified:** November 18, 2025
