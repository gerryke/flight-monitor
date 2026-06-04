#!/bin/bash
set -euo pipefail
REPO="/Users/keyipeng/Dev/ticketmonitor"
VENV="$REPO/.venv/bin/python"
LOG="/tmp/flightmonitor_local.log"
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
echo "=== $(date) start ===" >> "$LOG"
"$VENV" "$REPO/scripts/fetch_prices.py" >> "$LOG" 2>&1
echo "=== $(date) done ===" >> "$LOG"
