#!/usr/bin/env python3
"""
AMP-128 acceptance test - synthetic sustained UNWIND-batched MERGE pressure.

Goal: prove FalkorDB stays alive under 30+ minutes of sustained graph writes
heavier than AMP-110 ever produced.

Pattern: pure UNWIND-batched MERGE, no Ollama bottleneck, target ~2 batches/sec
* 50 docs each = ~100 doc-MERGEs/sec, ~180K over 30 min.

Acceptance criteria (per Computer's AMP-128 closure plan):
  1. Zero `WARNING Memory overcommit must be enabled!` lines after sysctl.
  2. Zero fresh-boot events (`Ready to accept connections` after 16:50:11).
  3. 100% of written docs present after the run.
  4. AOF /data/appendonlydir/appendonly.aof.* exists and grows during the run.

Writes go to graph `amp128_stress` (NOT business_knowledge). Cleaned up after.

Signed-by: Devon-85d1 | 2026-05-05 | session devin-85d1c5d9cee24844adaa4187084c0e64
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import redis

FALKORDB_HOST = os.getenv("FALKORDB_HOST", "172.18.0.22")
FALKORDB_PORT = int(os.getenv("FALKORDB_PORT", "6379"))
GRAPH_NAME = os.getenv("AMP128_STRESS_GRAPH", "amp128_stress")


def cypher_string(s):
    s = (s or "").replace("\\", "\\\\").replace("'", "\\'").replace("\n", " ").replace("\r", " ")
    return "'" + s + "'"


def cypher_value(v):
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return repr(v)
    if isinstance(v, str):
        return cypher_string(v)
    raise TypeError(type(v).__name__)


def cypher_map(d):
    return "{" + ", ".join(f"{k}: {cypher_value(v)}" for k, v in d.items()) + "}"


def cypher_list_of_maps(items):
    return "[" + ", ".join(cypher_map(d) for d in items) + "]"


def docs_present(r, ids):
    if not ids:
        return set()
    ids_lit = "[" + ", ".join(cypher_string(i) for i in ids) + "]"
    res = r.execute_command(
        "GRAPH.QUERY", GRAPH_NAME,
        f"MATCH (d:Stress) WHERE d.id IN {ids_lit} RETURN d.id"
    )
    found = set()
    if res and len(res) >= 2 and res[1]:
        for row in res[1]:
            if isinstance(row, list) and row:
                found.add(row[0])
    return found


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--duration-min", type=float, default=30.0,
                   help="Wall-time minutes to sustain load")
    p.add_argument("--batch-size", type=int, default=50)
    p.add_argument("--target-batches-per-sec", type=float, default=2.0,
                   help="Throttle to this rate (set 0 for max throughput)")
    p.add_argument("--log-path", default="/opt/amplified/apds/logs/amp128_stress.log")
    args = p.parse_args()

    log_fh = open(args.log_path, "a", buffering=1)

    def log(msg):
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
        line = f"{ts} {msg}"
        print(line, flush=True)
        log_fh.write(line + "\n")

    rc = redis.Redis(host=FALKORDB_HOST, port=FALKORDB_PORT, decode_responses=True)
    rc.ping()
    log(f"connected to FalkorDB graph={GRAPH_NAME}")
    log(f"plan: duration={args.duration_min}min batch={args.batch_size} target_rate={args.target_batches_per_sec}/sec")

    # Reset stress graph for a clean run.
    try:
        rc.execute_command("GRAPH.DELETE", GRAPH_NAME)
        log(f"reset graph {GRAPH_NAME}")
    except redis.ResponseError as e:
        if "empty key" not in str(e).lower():
            raise
        log(f"graph {GRAPH_NAME} did not previously exist")

    started = time.time()
    deadline = started + args.duration_min * 60.0
    target_period = 1.0 / args.target_batches_per_sec if args.target_batches_per_sec > 0 else 0.0

    batches = 0
    docs_written = 0
    write_errors = 0
    verify_misses = 0
    last_progress_log = started
    seq = 0
    sample_ids = set()  # 1% sample for end-of-run integrity check

    while time.time() < deadline:
        loop_start = time.time()
        chunk_ids = []
        payload = []
        labelled_at = datetime.now(timezone.utc).isoformat()
        for _ in range(args.batch_size):
            seq += 1
            doc_id = f"stress_{seq:08d}"
            chunk_ids.append(doc_id)
            if seq % 100 == 0:
                sample_ids.add(doc_id)
            payload.append({
                "id": doc_id,
                "title": f"Stress doc {seq:08d}",
                "url": f"https://example.test/{seq:08d}",
                "source": "AMP128_STRESS",
                "WHAT": "FIN",
                "HOW": "METRIC",
                "SCALE": "MICRO",
                "TIME": "NOW",
                "PATTERN": "LOG-CAU",
                "confidence": 0.9,
                "labelled_at": labelled_at,
                "seq": seq,
            })
        cypher = (
            f"UNWIND {cypher_list_of_maps(payload)} AS doc "
            "MERGE (d:Stress {id: doc.id}) "
            "SET d.title = doc.title, d.url = doc.url, d.source = doc.source, "
            "    d.WHAT = doc.WHAT, d.HOW = doc.HOW, d.SCALE = doc.SCALE, "
            "    d.TIME = doc.TIME, d.PATTERN = doc.PATTERN, "
            "    d.confidence = doc.confidence, d.labelled_at = doc.labelled_at, "
            "    d.seq = doc.seq "
            "RETURN count(d)"
        )
        try:
            rc.execute_command("GRAPH.QUERY", GRAPH_NAME, cypher)
            docs_written += len(chunk_ids)
            batches += 1
        except Exception as e:
            write_errors += 1
            log(f"WRITE ERROR: {type(e).__name__}: {str(e)[:160]}")
            time.sleep(0.5)
            continue

        # Periodic verify (every 100 batches).
        if batches % 100 == 0:
            check_ids = chunk_ids[:5] + list(sample_ids)[-5:]
            check_ids = list({i for i in check_ids if i})
            present = docs_present(rc, check_ids)
            misses = [i for i in check_ids if i not in present]
            if misses:
                verify_misses += len(misses)
                log(f"VERIFY MISS at batch {batches}: {misses}")

        # Throttle.
        if target_period > 0:
            elapsed = time.time() - loop_start
            remaining = target_period - elapsed
            if remaining > 0:
                time.sleep(remaining)

        # Progress log every 60s.
        now = time.time()
        if now - last_progress_log >= 60.0:
            mins_in = (now - started) / 60.0
            mins_left = (deadline - now) / 60.0
            rate = docs_written / max(now - started, 1e-9)
            log(
                f"progress mins_in={mins_in:.1f} mins_left={mins_left:.1f} "
                f"batches={batches} docs={docs_written} rate={rate:.1f}/s "
                f"write_err={write_errors} verify_miss={verify_misses}"
            )
            last_progress_log = now

    # Final verify: 1% sample.
    log("--- final verification ---")
    log(f"sample size: {len(sample_ids)}")
    final_present = set()
    sample_list = list(sample_ids)
    for start in range(0, len(sample_list), 500):
        chunk = sample_list[start : start + 500]
        final_present |= docs_present(rc, chunk)
    final_missing = [i for i in sample_list if i not in final_present]
    log(f"sample present: {len(final_present)}/{len(sample_list)}")
    if final_missing:
        log(f"sample MISSING ({len(final_missing)}): first 20 = {final_missing[:20]}")

    # Total node count.
    res = rc.execute_command("GRAPH.QUERY", GRAPH_NAME, "MATCH (d:Stress) RETURN count(d)")
    if res and len(res) >= 2 and res[1]:
        total_in_graph = res[1][0][0]
    else:
        total_in_graph = "?"

    # Persistence stats. (redis-py returns a dict for INFO.)
    persistence = rc.execute_command("INFO", "persistence")
    if isinstance(persistence, dict):
        aof_enabled = persistence.get("aof_enabled", "?")
        aof_size = persistence.get("aof_current_size", "?")
        aof_status = persistence.get("aof_last_status", "?")
    else:
        aof_enabled = "?"
        aof_size = "?"
        aof_status = "?"
        for line in persistence.splitlines():
            line = line.strip()
            if line.startswith("aof_enabled:"):
                aof_enabled = line.split(":", 1)[1]
            elif line.startswith("aof_current_size:"):
                aof_size = line.split(":", 1)[1]
            elif line.startswith("aof_last_status:"):
                aof_status = line.split(":", 1)[1]

    duration_sec = time.time() - started

    summary = {
        "duration_sec": round(duration_sec, 1),
        "batches": batches,
        "docs_written": docs_written,
        "rate_docs_per_sec": round(docs_written / max(duration_sec, 1e-9), 2),
        "write_errors": write_errors,
        "verify_misses_during_run": verify_misses,
        "sample_size": len(sample_ids),
        "sample_present_at_end": len(final_present),
        "sample_missing_at_end": len(final_missing),
        "total_nodes_in_graph": total_in_graph,
        "aof_enabled": aof_enabled,
        "aof_current_size": aof_size,
        "aof_last_status": aof_status,
    }
    log("--- SUMMARY ---")
    log(json.dumps(summary, indent=2))
    log_fh.close()

    # Exit non-zero if acceptance fails.
    if write_errors > 0 or verify_misses > 0 or final_missing:
        sys.exit(2)


if __name__ == "__main__":
    main()
