#!/bin/bash
# AMP-38 — Sovereign Edge Pre-Ingestion Pipe V3 nightly wrapper.
#
# Cron-friendly entrypoint for pre_ingestion_pipe_v3.py. Holds an exclusive
# flock so overlapping runs are impossible; appends to a single rotated log;
# returns 0 cleanly when the lock is already held (so cron does not page).
#
# Intended cron entry (root crontab on the Beast):
#   0 2 * * * /opt/amplified/devon/run_pre_ingestion_v3.sh
#
# This file is the canonical source. Deploy it to /opt/amplified/devon/ next
# to beast-health-check.sh and entity-monitor.sh — same pattern as the other
# Beast operator scripts.
#
# Signed-by: Devon-a3d1 | 2026-05-03 | session devin-a3d15ca9ebeb4d9fa083e09ef0ac686a
set -euo pipefail

V3=/opt/amplified/pre_ingestion_pipe_v3.py
LOG=/opt/amplified/logs/v3-ingestion.log
LOCK=/var/lock/v3-ingestion.lock

mkdir -p "$(dirname "$LOG")"

{
    echo "=== $(date -Iseconds) v3 nightly ingestion start ==="
    if [[ ! -x "$V3" && ! -f "$V3" ]]; then
        echo "ERROR: $V3 not found. Deploy from clean-build/02_build/scripts/."
        exit 1
    fi
    python3 "$V3" --quiet --lock-file "$LOCK"
    rc=$?
    echo "=== $(date -Iseconds) v3 nightly ingestion end (rc=$rc) ==="
    exit $rc
} >> "$LOG" 2>&1
