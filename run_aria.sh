#!/bin/bash
# ═══════════════════════════════════════════════════
#  ARIA — Daily Intelligence Pipeline Runner
#  Runs at 6:30 PM IST (13:00 UTC) via cron.
#  Cron entry:
#    0 13 * * * /home/pravin/Documents/projects/agent-setup/aria/run_aria.sh
# ═══════════════════════════════════════════════════

set -euo pipefail

# ── Config ───────────────────────────────────────────
PROJECT_DIR="/home/pravin/Documents/projects/agent-setup/aria"
VENV="$PROJECT_DIR/.venv/bin/activate"
LOGS_DIR="$PROJECT_DIR/logs"
DATE=$(date +%Y-%m-%d)
LOG_FILE="$LOGS_DIR/aria_$DATE.log"

# ── Setup ─────────────────────────────────────────────
mkdir -p "$LOGS_DIR"

echo "════════════════════════════════════════" >> "$LOG_FILE"
echo "  ARIA Pipeline — $DATE $(date +%H:%M:%S IST)" >> "$LOG_FILE"
echo "════════════════════════════════════════" >> "$LOG_FILE"

# ── Activate venv ─────────────────────────────────────
source "$VENV"

# ── Run pipeline ──────────────────────────────────────
cd "$PROJECT_DIR"
python main.py 2>&1 | tee -a "$LOG_FILE"

echo "" >> "$LOG_FILE"
echo "  Run completed at $(date +%H:%M:%S)" >> "$LOG_FILE"
echo "════════════════════════════════════════" >> "$LOG_FILE"
