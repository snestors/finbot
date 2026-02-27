#!/bin/bash
# Auto-recovery script for FinBot.
# Called by systemd ExecStopPost ONLY on actual crashes.
# Rolls back to last git auto-checkpoint and restarts.

PROJECT_DIR="/home/nestor/finbot"
LOG="/tmp/finbot-recovery.log"
MAX_RETRIES=3
RETRY_FILE="/tmp/finbot-recovery-count"

# Skip if this is a manual stop/restart (not a crash)
if [ -f /tmp/finbot-manual-restart ]; then
    rm -f /tmp/finbot-manual-restart
    echo "$(date): Skipping recovery — manual restart detected" >> "$LOG"
    exit 0
fi

echo "$(date): Recovery triggered (exit=$EXIT_STATUS service=$SERVICE_RESULT)" >> "$LOG"

# Count retries to avoid infinite loops
COUNT=0
if [ -f "$RETRY_FILE" ]; then
    COUNT=$(cat "$RETRY_FILE")
fi
COUNT=$((COUNT + 1))
echo "$COUNT" > "$RETRY_FILE"

if [ "$COUNT" -gt "$MAX_RETRIES" ]; then
    echo "$(date): Max retries ($MAX_RETRIES) exceeded. Giving up." >> "$LOG"
    rm -f "$RETRY_FILE"
    exit 1
fi

cd "$PROJECT_DIR" || exit 1

# Find last auto-checkpoint
CHECKPOINT=$(git log --oneline -20 | grep "\[auto-checkpoint\]" | head -1 | awk '{print $1}')

if [ -z "$CHECKPOINT" ]; then
    echo "$(date): No auto-checkpoint found. Trying git stash." >> "$LOG"
    git stash >> "$LOG" 2>&1
else
    echo "$(date): Rolling back to checkpoint $CHECKPOINT (attempt $COUNT)" >> "$LOG"
    git reset --hard "$CHECKPOINT" >> "$LOG" 2>&1
fi

# Clear retry count on next successful start (handled by ExecStartPost)
echo "$(date): Rollback complete, systemd will retry start" >> "$LOG"
