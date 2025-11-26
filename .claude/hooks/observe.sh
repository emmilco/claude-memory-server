#!/bin/bash
# Claude Code Observability Hook
# Logs workflow events, prompts journal entries, and captures behavioral feedback
# Note: We don't use set -e because we want graceful degradation on parse errors

LOGS_DIR="${CLAUDE_WORKSPACE:-.}/.claude/logs"
FEEDBACK_DIR="${CLAUDE_WORKSPACE:-.}/.claude/feedback"
LOG_FILE="${LOGS_DIR}/CLAUDE_LOGS.jsonl"
FEEDBACK_FILE="${FEEDBACK_DIR}/feedback_log.jsonl"
LAST_INTERVAL_FILE="${LOGS_DIR}/.last_interval_prompt"
mkdir -p "$LOGS_DIR" "$FEEDBACK_DIR"

# Read hook input from stdin
INPUT=$(cat)
EVENT_TYPE="$1"

# Extract fields from JSON input (handle parse failures gracefully)
SESSION_ID=$(echo "$INPUT" | jq -r '.session_id // "unknown"' 2>/dev/null) || SESSION_ID="unknown"
TIMESTAMP=$(date -u '+%Y-%m-%dT%H:%M:%SZ')
NOW_EPOCH=$(date "+%s")

# Shorten session ID for readability (first 8 chars)
SHORT_SESSION=$(echo "$SESSION_ID" | cut -c1-8)

# Human-readable timestamp for journal entries
HUMAN_TS=$(date '+%Y-%m-%d %H:%M')

# ─────────────────────────────────────────────────────────────
# LOG THE EVENT
# ─────────────────────────────────────────────────────────────

case "$EVENT_TYPE" in
  session_start)
    cat >> "$LOG_FILE" << EOF
{"ts":"$TIMESTAMP","event":"SESSION_START","session":"$SESSION_ID"}
EOF
    echo "$NOW_EPOCH" > "$LAST_INTERVAL_FILE"
    ;;

  user_prompt)
    PROMPT=$(echo "$INPUT" | jq -r '.prompt // ""' 2>/dev/null) || PROMPT=""
    # Escape and truncate for JSON safety
    PROMPT_PREVIEW=$(echo "$PROMPT" | head -c 100 | tr '\n' ' ' | sed 's/"/\\"/g')
    cat >> "$LOG_FILE" << EOF
{"ts":"$TIMESTAMP","event":"USER_PROMPT","session":"$SESSION_ID","preview":"$PROMPT_PREVIEW"}
EOF
    ;;

  task_start)
    TASK_PROMPT=$(echo "$INPUT" | jq -r '.tool_input.prompt // ""' 2>/dev/null | head -c 100 | tr '\n' ' ' | sed 's/"/\\"/g') || TASK_PROMPT=""
    AGENT_TYPE=$(echo "$INPUT" | jq -r '.tool_input.subagent_type // "unknown"' 2>/dev/null) || AGENT_TYPE="unknown"
    cat >> "$LOG_FILE" << EOF
{"ts":"$TIMESTAMP","event":"TASK_START","session":"$SESSION_ID","agent_type":"$AGENT_TYPE","preview":"$TASK_PROMPT"}
EOF
    ;;

  task_end)
    AGENT_TYPE=$(echo "$INPUT" | jq -r '.tool_input.subagent_type // "unknown"' 2>/dev/null) || AGENT_TYPE="unknown"
    cat >> "$LOG_FILE" << EOF
{"ts":"$TIMESTAMP","event":"TASK_END","session":"$SESSION_ID","agent_type":"$AGENT_TYPE"}
EOF
    ;;

  stop)
    cat >> "$LOG_FILE" << EOF
{"ts":"$TIMESTAMP","event":"STOP","session":"$SESSION_ID"}
EOF
    ;;

  session_end)
    cat >> "$LOG_FILE" << EOF
{"ts":"$TIMESTAMP","event":"SESSION_END","session":"$SESSION_ID"}
EOF
    ;;

  tool_use)
    # Extract tool name and create appropriate preview based on tool type
    TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // "unknown"' 2>/dev/null) || TOOL_NAME="unknown"

    case "$TOOL_NAME" in
      Edit)
        FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // ""' 2>/dev/null | sed 's|.*/||') || FILE_PATH=""
        OLD_STR=$(echo "$INPUT" | jq -r '.tool_input.old_string // ""' 2>/dev/null | head -c 50 | tr '\n' ' ' | sed 's/"/\\"/g') || OLD_STR=""
        PREVIEW="$FILE_PATH: \"$OLD_STR...\""
        ;;
      Write)
        FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // ""' 2>/dev/null | sed 's|.*/||') || FILE_PATH=""
        PREVIEW="$FILE_PATH"
        ;;
      Bash)
        CMD=$(echo "$INPUT" | jq -r '.tool_input.command // ""' 2>/dev/null | head -c 80 | tr '\n' ' ' | sed 's/"/\\"/g') || CMD=""
        PREVIEW="$CMD"
        ;;
      Read)
        FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // ""' 2>/dev/null | sed 's|.*/||') || FILE_PATH=""
        PREVIEW="$FILE_PATH"
        ;;
      Grep)
        PATTERN=$(echo "$INPUT" | jq -r '.tool_input.pattern // ""' 2>/dev/null | head -c 40 | sed 's/"/\\"/g') || PATTERN=""
        PREVIEW="/$PATTERN/"
        ;;
      Glob)
        PATTERN=$(echo "$INPUT" | jq -r '.tool_input.pattern // ""' 2>/dev/null | head -c 40 | sed 's/"/\\"/g') || PATTERN=""
        PREVIEW="$PATTERN"
        ;;
      *)
        PREVIEW="(unknown tool)"
        ;;
    esac

    cat >> "$LOG_FILE" << EOF
{"ts":"$TIMESTAMP","event":"TOOL_USE","session":"$SESSION_ID","tool":"$TOOL_NAME","preview":"$PREVIEW"}
EOF
    ;;
esac

# ─────────────────────────────────────────────────────────────
# BEHAVIORAL FEEDBACK DETECTION
# ─────────────────────────────────────────────────────────────

# Only check for feedback on user prompts
if [[ "$EVENT_TYPE" == "user_prompt" ]]; then
  # Get prompt, handling potential jq failures gracefully
  PROMPT=$(echo "$INPUT" | jq -r '.prompt // ""' 2>/dev/null) || PROMPT=""

  if [[ -n "$PROMPT" ]]; then
    # Keyword patterns (case-insensitive matching)
    # Philosophy: over-sensitive triggers, filter false positives during /retro analysis
    POSITIVE_PATTERN="(^|\s)(great|perfect|exactly|excellent|nice|good job|well done|thanks|thank you|love it|awesome|wonderful|brilliant|fantastic|spot on|nailed it|that's it|yes!|correct|right|helpful|useful|works|working|fixed|solved|amazing|impressive|beautiful|elegant|clever|smart|cool|nice work|good work|solid|clean|neat|sweet|superb|outstanding|exceptional|incredible|remarkable|splendid|terrific|marvelous|delightful|pleased|happy|glad|excited|appreciate|grateful|that's perfect|exactly right|just what I needed|you got it|bingo|precisely|indeed|absolutely|definitely|certainly|affirmative|approved|accepted|confirmed|legit|fire|chef's kiss|10\/10|A\+|\+1)(\s|$|[!.,])"
    NEGATIVE_PATTERN="(^|\s)(wrong|broke|broken|missed|not what|frustrat|stuck|bad|fail|didn't work|doesn't work|not right|incorrect|mistake|error|problem|issue|confused|off track|lost|ugh|sigh|annoying|slow|useless|unhelpful|terrible|awful|horrible|disaster|mess|ugly|hacky|gross|hate|dislike|disappointed|unfortunate|sadly|worse|stupid|dumb|silly|ridiculous|absurd|weird|strange|odd|unexpected|surprising|concerning|worrying|scary|yikes|oops|ouch|damn|crap|cmon|come on|seriously|really\?|what\?|huh\?|wtf|smh|facepalm|no no|nope|nah|not even close|way off|completely wrong|totally wrong|dead wrong)(\s|$|[!.,])"
    CORRECTIVE_PATTERN="(^|\s)(actually|not quite|I meant|try again|instead|rather|let me clarify|what I wanted|should be|supposed to|meant to|correction|rephrase|misunderstand|misunderstood|wait|hold on|stop|hang on|pause|let me explain|to clarify|to be clear|what I'm saying|what I mean|I was asking|I wanted|I need|different|other|another|else|alternative|change|modify|adjust|revise|redo|again|back to|go back|revert|original|previous|before|earlier|no I|not that|the other|wrong one|wrong file|wrong thing)(\s|$|[!.,])"

    SENTIMENT=""
    if echo "$PROMPT" | grep -iE "$POSITIVE_PATTERN" > /dev/null 2>&1; then
      SENTIMENT="positive"
    elif echo "$PROMPT" | grep -iE "$NEGATIVE_PATTERN" > /dev/null 2>&1; then
      SENTIMENT="negative"
    elif echo "$PROMPT" | grep -iE "$CORRECTIVE_PATTERN" > /dev/null 2>&1; then
      SENTIMENT="corrective"
    fi

    # If sentiment detected, log to feedback file
    if [[ -n "$SENTIMENT" ]]; then
      # Use jq to create properly escaped JSON
      jq -n \
        --arg ts "$TIMESTAMP" \
        --arg sid "$SESSION_ID" \
        --arg sent "$SENTIMENT" \
        --arg msg "$PROMPT" \
        '{timestamp: $ts, session_id: $sid, sentiment: $sent, user_message: $msg}' \
        >> "$FEEDBACK_FILE" 2>/dev/null || true
    fi
  fi
fi

# ─────────────────────────────────────────────────────────────
# LEARNED PRINCIPLES INJECTION (new sessions only)
# ─────────────────────────────────────────────────────────────

PRINCIPLES_OUTPUT=""
SEEN_SESSIONS_FILE="${LOGS_DIR}/.seen_sessions"
touch "$SEEN_SESSIONS_FILE" 2>/dev/null || true

# Only inject on user_prompt (first user message triggers injection)
if [[ "$EVENT_TYPE" == "user_prompt" ]]; then
  if ! grep -q "^${SESSION_ID}$" "$SEEN_SESSIONS_FILE" 2>/dev/null; then
    # New session - mark as seen
    echo "$SESSION_ID" >> "$SEEN_SESSIONS_FILE"

    # Keep only last 100 sessions (prevents unbounded growth)
    tail -n 100 "$SEEN_SESSIONS_FILE" > "${SEEN_SESSIONS_FILE}.tmp" 2>/dev/null && \
      mv "${SEEN_SESSIONS_FILE}.tmp" "$SEEN_SESSIONS_FILE" 2>/dev/null || true

    # Read principles file
    SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
    PRINCIPLES_FILE="${SCRIPT_DIR}/../../LEARNED_PRINCIPLES.md"

    if [[ -f "$PRINCIPLES_FILE" ]]; then
      # Extract Active Principles section (between "## Active Principles" and "## Retired")
      # Note: Use sed '$d' twice instead of head -n -2 (macOS head doesn't support negative counts)
      PRINCIPLES=$(sed -n '/^## Active Principles/,/^## Retired/p' "$PRINCIPLES_FILE" 2>/dev/null | sed '$d' | sed '$d')

      # Only output if there are actual principles (not the placeholder text)
      if [[ -n "$PRINCIPLES" ]] && [[ "$PRINCIPLES" != *"No principles yet"* ]]; then
        PRINCIPLES_OUTPUT="[LEARNED PRINCIPLES - Behavioral guidelines from user feedback analysis:]
$PRINCIPLES"
      fi
    fi
  fi
fi

# ─────────────────────────────────────────────────────────────
# GENERATE JOURNAL PROMPTS
# ─────────────────────────────────────────────────────────────

JOURNAL_PROMPT=""

case "$EVENT_TYPE" in
  user_prompt)
    JOURNAL_PROMPT="[JOURNAL:$SHORT_SESSION] New user request. Add to CLAUDE_JOURNAL.md: ### $HUMAN_TS | $SHORT_SESSION | USER_PROMPT followed by: What is being asked? Initial approach?"
    ;;

  task_start)
    AGENT_TYPE=$(echo "$INPUT" | jq -r '.tool_input.subagent_type // "unknown"' 2>/dev/null) || AGENT_TYPE="unknown"
    JOURNAL_PROMPT="[JOURNAL:$SHORT_SESSION] Spawning subagent. Add to CLAUDE_JOURNAL.md: ### $HUMAN_TS | $SHORT_SESSION | TASK_START ($AGENT_TYPE) followed by: Why delegate? What should it accomplish?"
    ;;

  task_end)
    AGENT_TYPE=$(echo "$INPUT" | jq -r '.tool_input.subagent_type // "unknown"' 2>/dev/null) || AGENT_TYPE="unknown"
    JOURNAL_PROMPT="[JOURNAL:$SHORT_SESSION] Subagent finished. Add to CLAUDE_JOURNAL.md: ### $HUMAN_TS | $SHORT_SESSION | TASK_END ($AGENT_TYPE) followed by: Did it succeed? What did you learn?"
    ;;

  stop)
    JOURNAL_PROMPT="[JOURNAL:$SHORT_SESSION] Response complete. Add to CLAUDE_JOURNAL.md: ### $HUMAN_TS | $SHORT_SESSION | STOP followed by: What was accomplished? Any concerns?"
    ;;
esac

# ─────────────────────────────────────────────────────────────
# 10-MINUTE INTERVAL CHECK
# ─────────────────────────────────────────────────────────────

if [[ -f "$LAST_INTERVAL_FILE" ]]; then
  LAST_INTERVAL_EPOCH=$(cat "$LAST_INTERVAL_FILE")
  ELAPSED_MINS=$(( (NOW_EPOCH - LAST_INTERVAL_EPOCH) / 60 ))

  if [[ $ELAPSED_MINS -ge 10 ]]; then
    cat >> "$LOG_FILE" << EOF
{"ts":"$TIMESTAMP","event":"INTERVAL_PROMPT","session":"$SESSION_ID","elapsed_mins":$ELAPSED_MINS}
EOF
    echo "$NOW_EPOCH" > "$LAST_INTERVAL_FILE"
    JOURNAL_PROMPT="[JOURNAL:$SHORT_SESSION] 10-minute checkpoint. Add to CLAUDE_JOURNAL.md: ### $HUMAN_TS | $SHORT_SESSION | INTERVAL followed by: What progress? Stuck anywhere? Approach working?"
  fi
fi

# ─────────────────────────────────────────────────────────────
# OUTPUT - Return context to Claude if needed
# ─────────────────────────────────────────────────────────────

# Output principles first (if new session), then journal prompt
if [[ -n "$PRINCIPLES_OUTPUT" ]]; then
  echo "$PRINCIPLES_OUTPUT"
  echo ""
fi

if [[ -n "$JOURNAL_PROMPT" ]]; then
  echo "$JOURNAL_PROMPT"
fi

exit 0
