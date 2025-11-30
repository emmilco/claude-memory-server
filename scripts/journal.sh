#!/bin/bash
# scripts/journal.sh
# Append a formatted entry to CLAUDE_JOURNAL.md
#
# Usage: ./scripts/journal.sh <event_type> <content>
# Example: ./scripts/journal.sh USER_PROMPT "Investigating search bug. Will check qdrant_store first."
#
# Event types: USER_PROMPT, TASK_START, TASK_END, STOP, INTERVAL, NOTE

set -e

JOURNAL_FILE="${CLAUDE_WORKSPACE:-.}/CLAUDE_JOURNAL.md"
SESSION_FILE="${CLAUDE_WORKSPACE:-.}/.claude/logs/.current_session"

EVENT_TYPE="${1:-NOTE}"
CONTENT="${2:-}"

if [[ -z "$CONTENT" ]]; then
  echo "Usage: ./scripts/journal.sh <event_type> <content>"
  echo "Example: ./scripts/journal.sh USER_PROMPT \"Investigating bug in search.\""
  exit 1
fi

# Get session ID from file (written by observe.sh) or default
if [[ -f "$SESSION_FILE" ]]; then
  SESSION_ID=$(cat "$SESSION_FILE" | cut -c1-8)
else
  SESSION_ID="unknown"
fi

# Timestamp
TIMESTAMP=$(date '+%Y-%m-%d %H:%M')

# Create journal file if it doesn't exist
if [[ ! -f "$JOURNAL_FILE" ]]; then
  cat > "$JOURNAL_FILE" << 'EOF'
# Claude Journal

Session reflections and decision logs.

---

EOF
fi

# Append entry
cat >> "$JOURNAL_FILE" << EOF

### $TIMESTAMP | $SESSION_ID | $EVENT_TYPE
$CONTENT
EOF

echo "Journal entry added: $EVENT_TYPE"
