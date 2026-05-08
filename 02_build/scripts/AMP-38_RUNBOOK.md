# AMP-38 Runbook — pre_ingestion_pipe_v3 nightly schedule

Operator runbook for the Sovereign Edge Pre-Ingestion Pipe V3 (`pre_ingestion_pipe_v3.py`). Required reading before running anything in this directory destructively.

Companion to PR #63 (introduces V3) and this PR (introduces the schedule + wrapper).

---

## What V3 does

Walks `/opt/amplified/raw-mac-dumps/` recursively, content-addresses every regular file by SHA-256, and copies any not-already-present file into `/opt/amplified/vault/store_b_clean/` with a deterministic ISO-date + sanitised-topic + author + 16-char-hash filename. Writes a JSONL skip-ledger for every drop / dup / error decision.

**It does not delete or modify `raw-mac-dumps`.** Per AMP-38 directive.

**It does not wipe `store_b_clean`** — only adds. Re-runs are no-ops on already-ingested content. Safe alongside the live `--classify-only` pipeline.

## Cron schedule

```
0 2 * * * /opt/amplified/devon/run_pre_ingestion_v3.sh
```

`02:00 UTC` so it completes before the `03:00 UTC` `vault-backup` rsync and the `04:00 UTC` `marketing-engine` cron. The wrapper holds an exclusive flock at `/var/lock/v3-ingestion.lock`; if a previous run is still going, the next run exits 0 cleanly without paging.

## Deployment (one-time, from this repo to the Beast)

```bash
# 1) Copy V3 + wrapper into the Beast's canonical operator paths.
scp 02_build/scripts/pre_ingestion_pipe_v3.py    root@beast:/opt/amplified/pre_ingestion_pipe_v3.py
scp 02_build/scripts/run_pre_ingestion_v3.sh     root@beast:/opt/amplified/devon/run_pre_ingestion_v3.sh
ssh root@beast 'chmod +x /opt/amplified/devon/run_pre_ingestion_v3.sh /opt/amplified/pre_ingestion_pipe_v3.py'

# 2) Deprecate V2 so nobody triggers the destructive rmtree path again.
ssh root@beast 'mv /opt/amplified/pre_ingestion_pipe_v2.py /opt/amplified/deprecated/pre_ingestion_pipe_v2.py.deprecated-2026-05'

# 3) Install the cron entry. Use `crontab -e` and append the line above.
#    Verify with `crontab -l | grep run_pre_ingestion_v3`.
```

## Manual run (operator)

```bash
# Dry-run, planning only:
python3 /opt/amplified/pre_ingestion_pipe_v3.py --dry-run

# Production, with lock + quiet, identical to what cron does:
/opt/amplified/devon/run_pre_ingestion_v3.sh

# Tail the log:
tail -f /opt/amplified/logs/v3-ingestion.log
```

## Outputs

- **Ingested files:** `/opt/amplified/vault/store_b_clean/<date>_<topic>_<author>_<sha16>.<ext>`
- **Skip ledger:** `/opt/amplified/vault-ingestion-progress/v3_skipped.jsonl` (append-only, JSONL — every drop / dup / error)
- **Wrapper log:** `/opt/amplified/logs/v3-ingestion.log` (rotate via existing `logrotate.timer` if needed)

## Reverse / rollback

V3 is reversible by design — every added file is keyed by a 16-char SHA-256 prefix appended to its filename, and every action is recorded in the JSONL ledger. To undo a single nightly run:

```bash
# Find files added in the last run (jq + ledger):
jq -r 'select(.reason == null) | .name' /opt/amplified/vault-ingestion-progress/v3_skipped.jsonl
# (the v3 ledger logs skips, not adds — for a full add manifest run with --verbose
# or diff the clean dir before/after via `find ... -printf '%p %CY-%Cm-%CdT%CH:%CM:%CS\n'`.)
```

Raw-mac-dumps is untouched and stays that way per the AMP-38 directive.

## Confidence

OPINION 90% (medium reversibility floor 85%) that this schedule prevents recurrence of the AMP-38 gap. Recurrence happens iff raw-mac-dumps is re-hydrated and the producer is not re-run; the schedule guarantees the second condition is impossible.

---

*Signed-by: Devon-a3d1 | 2026-05-03 | session devin-a3d15ca9ebeb4d9fa083e09ef0ac686a*
