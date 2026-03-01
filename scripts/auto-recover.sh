#!/bin/bash
# Auto-recovery script for FinBot.
# Called by systemd ExecStopPost ONLY on actual crashes.
# SAFE: only logs and restarts. Does NOT revert git changes.

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

# Just log the crash — do NOT revert git changes
echo "$(date): Service crashed (attempt $COUNT/$MAX_RETRIES). Letting systemd restart." >> "$LOG"
echo "$(date): Current HEAD: $(git log --oneline -1)" >> "$LOG"

# Clear retry count on next successful start (handled by ExecStartPost)
