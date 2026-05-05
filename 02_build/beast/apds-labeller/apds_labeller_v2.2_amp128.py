#!/usr/bin/env python3
"""
APDS Labeller v2.2 -- AMP-128 hardened pass.

v2.1 (rescue, 2026-05-05 12:37 UTC) walked the deduped JSONL set and stored docs
ONE MERGE PER CALL with verify-and-retry. That worked, but it produced the
sustained writer-queue load that exposed FalkorDB #1056 / AMP-128 (silent loss
on container recycle, MERGE-queue overflow under streaming pressure).

v2.2 changes (AMP-128 closure plan):
- UNWIND-batched MERGE (batch_size=50). One Cypher call per 50 docs instead of
  50 calls. ~50x fewer writer-queue entries, ~50x fewer GraphBLAS delta flushes.
- Batch-level verify-and-retry. After the UNWIND lands, read-back counts every
  doc_id in the batch. If any are missing, retry the whole batch up to N times,
  then fall back to per-doc store_with_retry as defence-in-depth.
- Keeps store_with_retry intact so it can still be called per-doc if needed
  (e.g., as the fallback path, or by external callers).

This file pairs with the AMP-128 compose changes (AOF + back-pressure knobs +
pinned image v4.18.3) and host sysctl (vm.overcommit_memory=1). Without those,
the batching alone won't close the silent-loss window — they're a stack.

Invocation:
    python3 apds_labeller_v2_rescue.py --run-id 20260505_094320

Signed-by: Devon-85d1 | 2026-05-05 | session devin-85d1c5d9cee24844adaa4187084c0e64
"""

import argparse
import glob
import json
import os
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import redis

FALKORDB_HOST = os.getenv("FALKORDB_HOST", "172.18.0.22")
FALKORDB_PORT = int(os.getenv("FALKORDB_PORT", "6379"))
GRAPH_NAME = "business_knowledge"
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://172.18.0.12:11434")
LOG_DIR = Path(os.getenv("LOG_DIR", "/opt/amplified/apds/logs"))
BATCH_SIZE = int(os.getenv("APDS_BATCH_SIZE", "50"))

PUDDING_PROMPT = """You are a PUDDING taxonomy labeller. Assign exactly one label per dimension.

Dimensions:
- WHAT: FIN | OPS | MKT | TECH | PPL | GOV | EXT
- HOW: METRIC | PROCESS | ASSET | RISK | OPPORTUNITY | RELATIONSHIP | KNOWLEDGE
- SCALE: NANO | MICRO | MESO | MACRO | MEGA | META | TEMPORAL
- TIME: NOW | NEAR | MID | FAR | EVERGREEN | CYCLICAL | LEGACY
- PATTERN: LOG-CAU | LOG-ANA | LOG-SYN | SYS-FB | SYS-EM | SYS-HM | SYS-BM | HUM-TRUST | HUM-INCENT | HUM-COG | HUM-CULT | VAL-EFF | VAL-ACC | VAL-ROB | VAL-ADAPT | VAL-ETH

Output ONLY valid JSON:
{"WHAT": "...", "HOW": "...", "SCALE": "...", "TIME": "...", "PATTERN": "...", "confidence": 0.0-1.0}

Text to label:
"""


def get_ollama_label(text: str, model: str = "llama3.1:8b") -> dict:
    payload = json.dumps({
        "model": model,
        "prompt": PUDDING_PROMPT + (text or "")[:2000],
        "stream": False,
        "format": "json",
        "options": {"temperature": 0.1, "num_predict": 150},
    }).encode()
    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read())
            result = json.loads(data.get("response", "{}"))
            required = {"WHAT", "HOW", "SCALE", "TIME", "PATTERN"}
            if required.issubset(result.keys()):
                return result
            return {k: "UNKNOWN" for k in required} | {"confidence": 0.0}
    except Exception as e:
        return {
            "WHAT": "UNKNOWN", "HOW": "UNKNOWN", "SCALE": "UNKNOWN",
            "TIME": "UNKNOWN", "PATTERN": "UNKNOWN", "confidence": 0.0,
            "_error": str(e)[:120],
        }


def escape_cypher(s: str) -> str:
    return (s or "").replace("\\", "\\\\").replace("'", "\\'").replace("\n", " ").replace("\r", " ")


def cypher_string(s: str | None) -> str:
    """Cypher single-quoted string literal."""
    return "'" + escape_cypher(s or "") + "'"


def cypher_value(v) -> str:
    """Render a Python value as a Cypher literal."""
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return repr(v)
    if isinstance(v, str):
        return cypher_string(v)
    raise TypeError(f"Unsupported type for Cypher literal: {type(v).__name__}")


def cypher_map(d: dict) -> str:
    """Render a flat Python dict as a Cypher map literal."""
    parts = [f"{k}: {cypher_value(v)}" for k, v in d.items()]
    return "{" + ", ".join(parts) + "}"


def cypher_list_of_maps(items: list[dict]) -> str:
    """Render a list of flat dicts as a Cypher list-of-maps literal."""
    return "[" + ", ".join(cypher_map(d) for d in items) + "]"


def doc_exists(r, doc_id: str) -> bool:
    """True iff a Document with that id is in the graph."""
    res = r.execute_command(
        "GRAPH.QUERY", GRAPH_NAME,
        f"MATCH (d:Document {{id: {cypher_string(doc_id)}}}) RETURN count(d)"
    )
    if not res or len(res) < 2 or not res[1]:
        return False
    row = res[1][0]
    if isinstance(row, list) and row:
        return int(row[0]) >= 1
    return False


def docs_present(r, doc_ids: list[str]) -> set[str]:
    """Return the subset of doc_ids that already exist in the graph (one query)."""
    if not doc_ids:
        return set()
    ids_literal = "[" + ", ".join(cypher_string(i) for i in doc_ids) + "]"
    cypher = (
        f"MATCH (d:Document) WHERE d.id IN {ids_literal} "
        "RETURN d.id"
    )
    res = r.execute_command("GRAPH.QUERY", GRAPH_NAME, cypher)
    found: set[str] = set()
    if res and len(res) >= 2 and res[1]:
        for row in res[1]:
            if isinstance(row, list) and row:
                found.add(row[0])
    return found


def _doc_props(doc_id: str, rec: dict, labels: dict, query: str, engine: str,
               harvest_run_id: str, source: str, labelled_at: str) -> dict:
    return {
        "id": doc_id,
        "title": (rec.get("title") or "")[:200],
        "url": (rec.get("url") or "")[:500],
        "source": source,
        "WHAT": labels.get("WHAT", "UNKNOWN"),
        "HOW": labels.get("HOW", "UNKNOWN"),
        "SCALE": labels.get("SCALE", "UNKNOWN"),
        "TIME": labels.get("TIME", "UNKNOWN"),
        "PATTERN": labels.get("PATTERN", "UNKNOWN"),
        "confidence": float(labels.get("confidence", 0.0)),
        "query": (query or "")[:200],
        "engine": (engine or "")[:50],
        "harvest_run_id": (harvest_run_id or "")[:50],
        "labelled_at": labelled_at,
    }


# Cypher fragment shared by batched writer and per-doc writer.
_DOC_SET_CLAUSE = (
    "SET d.title = doc.title, "
    "    d.url = doc.url, "
    "    d.source = doc.source, "
    "    d.WHAT = doc.WHAT, "
    "    d.HOW = doc.HOW, "
    "    d.SCALE = doc.SCALE, "
    "    d.TIME = doc.TIME, "
    "    d.PATTERN = doc.PATTERN, "
    "    d.confidence = doc.confidence, "
    "    d.query = doc.query, "
    "    d.engine = doc.engine, "
    "    d.harvest_run_id = doc.harvest_run_id, "
    "    d.labelled_at = doc.labelled_at"
)


def store_with_retry(r, doc_id: str, title: str, url: str, labels: dict,
                     query: str, engine: str, harvest_run_id: str,
                     source: str = "APDS",
                     max_attempts: int = 5) -> tuple[bool, int]:
    """MERGE one doc, verify, retry on silent loss. Defence-in-depth fallback."""
    rec = {"title": title, "url": url}
    labelled_at = datetime.now(timezone.utc).isoformat()
    payload = _doc_props(doc_id, rec, labels, query, engine, harvest_run_id, source, labelled_at)
    cypher = (
        f"WITH {cypher_map(payload)} AS doc "
        "MERGE (d:Document {id: doc.id}) "
        f"{_DOC_SET_CLAUSE} "
        "RETURN d.id"
    )
    for attempt in range(1, max_attempts + 1):
        try:
            r.execute_command("GRAPH.QUERY", GRAPH_NAME, cypher)
        except Exception as e:
            print(f"    attempt {attempt}: write exception: {e}")
            time.sleep(attempt)
            continue
        try:
            if doc_exists(r, doc_id):
                return True, attempt
        except Exception as e:
            print(f"    attempt {attempt}: verify exception: {e}")
        time.sleep(attempt)
    return False, max_attempts


def store_documents_batched(
    r,
    items: list[tuple[str, dict, dict, str, str, str]],
    *,
    source: str = "APDS",
    batch_size: int = BATCH_SIZE,
    max_batch_attempts: int = 3,
) -> tuple[int, int, int]:
    """UNWIND-batched MERGE with batch verify + per-doc fallback.

    `items` is a list of tuples: (doc_id, rec, labels, query, engine, harvest_run_id).
    Returns (ok, failed, total_attempts).

    Strategy:
      1. Slice items into chunks of batch_size.
      2. For each chunk: build one Cypher UNWIND with the chunk inlined as a list
         of map literals; fire one GRAPH.QUERY; read-back-verify all ids.
      3. If verify fails, retry the whole batch up to max_batch_attempts.
      4. If still failing, fall back to per-doc store_with_retry on the misses.
    """
    ok = 0
    failed = 0
    total_attempts = 0

    for start in range(0, len(items), batch_size):
        chunk = items[start : start + batch_size]
        chunk_ids = [t[0] for t in chunk]
        labelled_at = datetime.now(timezone.utc).isoformat()
        payload = [
            _doc_props(doc_id, rec, labels, query, engine, harvest_run_id, source, labelled_at)
            for (doc_id, rec, labels, query, engine, harvest_run_id) in chunk
        ]
        cypher = (
            f"UNWIND {cypher_list_of_maps(payload)} AS doc "
            "MERGE (d:Document {id: doc.id}) "
            f"{_DOC_SET_CLAUSE} "
            "RETURN count(d)"
        )

        landed = False
        missing: list[str] = []
        for attempt in range(1, max_batch_attempts + 1):
            total_attempts += 1
            try:
                r.execute_command("GRAPH.QUERY", GRAPH_NAME, cypher)
            except Exception as e:
                print(f"  batch attempt {attempt}: write exception: {e}")
                time.sleep(attempt)
                continue
            try:
                present = docs_present(r, chunk_ids)
            except Exception as e:
                print(f"  batch attempt {attempt}: verify exception: {e}")
                time.sleep(attempt)
                continue
            missing = [i for i in chunk_ids if i not in present]
            if not missing:
                ok += len(chunk)
                landed = True
                break
            print(f"  batch attempt {attempt}: {len(missing)}/{len(chunk)} missing post-MERGE")
            time.sleep(attempt)

        if landed:
            continue

        # Per-doc fallback for misses (or whole batch if every attempt errored).
        fallback_targets = missing or chunk_ids
        fallback_set = set(fallback_targets)
        chunk_by_id = {t[0]: t for t in chunk}
        for doc_id in fallback_targets:
            if doc_id not in chunk_by_id:
                continue
            _, rec, labels, query, engine, harvest_run_id = chunk_by_id[doc_id]
            doc_ok, attempts = store_with_retry(
                r, doc_id, rec.get("title", ""), rec.get("url", ""), labels,
                query=query, engine=engine, harvest_run_id=harvest_run_id, source=source,
            )
            total_attempts += attempts
            if doc_ok:
                ok += 1
            else:
                failed += 1
        # Anything in the chunk NOT in fallback_set is already in the graph from
        # the batch attempt; count it as ok.
        ok += sum(1 for t in chunk if t[0] not in fallback_set)

    return ok, failed, total_attempts


class BatchedFlusher:
    """Buffer items and flush in UNWIND-batched MERGE chunks."""

    def __init__(self, r, batch_size: int = BATCH_SIZE, on_flush=None):
        self.r = r
        self.batch_size = batch_size
        self.buffer: list[tuple[str, dict, dict, str, str, str]] = []
        self.ok = 0
        self.failed = 0
        self.total_attempts = 0
        self.flushes = 0
        self._on_flush = on_flush

    def add(self, doc_id: str, rec: dict, labels: dict,
            query: str, engine: str, harvest_run_id: str) -> None:
        self.buffer.append((doc_id, rec, labels, query, engine, harvest_run_id))
        if len(self.buffer) >= self.batch_size:
            self.flush()

    def flush(self) -> None:
        if not self.buffer:
            return
        batch = self.buffer
        self.buffer = []
        before = (self.ok, self.failed, self.total_attempts)
        ok, failed, attempts = store_documents_batched(
            self.r, batch, batch_size=self.batch_size
        )
        self.ok += ok
        self.failed += failed
        self.total_attempts += attempts
        self.flushes += 1
        if self._on_flush:
            self._on_flush(self.flushes, len(batch), ok, failed, attempts)


def load_deduped(input_glob: str) -> list[dict]:
    paths = [Path(p) for p in sorted(glob.glob(input_glob))]
    records = []
    for p in paths:
        with open(p) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                records.append({
                    "title": rec.get("title") or "Untitled",
                    "url": rec.get("url") or "",
                    "content": rec.get("content") or "",
                    "query": rec.get("query") or "",
                    "engine": rec.get("engine") or "",
                    "run_id": rec.get("run_id") or "jsonl",
                })
    seen = set()
    out = []
    for r in records:
        k = (r.get("url") or "").strip().lower()
        if not k or k in seen:
            continue
        seen.add(k)
        out.append(r)
    return out


def main():
    p = argparse.ArgumentParser(description="APDS Labeller v2.2 (AMP-128 hardened pass)")
    p.add_argument("--run-id", required=True,
                   help="Original labeller run_id whose missing indices we are rescuing (e.g. 20260505_094320)")
    p.add_argument("--input-glob", default="/opt/amplified/apds/logs/harvest_q*.jsonl")
    p.add_argument("--limit", type=int, default=0,
                   help="Process at most N missing records (0 = unlimited)")
    p.add_argument("--batch-size", type=int, default=BATCH_SIZE,
                   help="UNWIND batch size for MERGE (default: 50, override via APDS_BATCH_SIZE)")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    rescue_run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    log_path = LOG_DIR / f"labeller_rescue_{rescue_run_id}.log"
    log_fh = open(log_path, "a", buffering=1)

    def log(msg: str):
        print(msg, flush=True)
        log_fh.write(msg + "\n")

    log("=" * 60)
    log(f"APDS Labeller v2.2 (AMP-128) for run_id={args.run_id}")
    log(f"rescue_run_id={rescue_run_id} model=llama3.1:8b batch_size={args.batch_size}")
    log("=" * 60)

    deduped = load_deduped(args.input_glob)
    log(f"Loaded {len(deduped)} unique deduped records from glob {args.input_glob}")

    rc = redis.Redis(host=FALKORDB_HOST, port=FALKORDB_PORT, decode_responses=True)
    if not rc.ping():
        log("ERROR: cannot connect to FalkorDB")
        sys.exit(1)
    log(f"Connected to FalkorDB graph '{GRAPH_NAME}'")

    log("Scanning for missing indices...")
    all_ids = [f"apds_{args.run_id}_{i:04d}" for i in range(1, len(deduped) + 1)]
    present = set()
    # Chunk the existence scan to avoid a giant single query.
    scan_chunk = 500
    for start in range(0, len(all_ids), scan_chunk):
        present |= docs_present(rc, all_ids[start : start + scan_chunk])
    missing = [
        (i, all_ids[i - 1], deduped[i - 1])
        for i in range(1, len(deduped) + 1)
        if all_ids[i - 1] not in present
    ]
    log(f"Missing: {len(missing)} of {len(deduped)} indices")

    if args.limit and args.limit > 0:
        missing = missing[: args.limit]
        log(f"Limit applied: rescuing first {len(missing)} only")

    if args.dry_run:
        for i, doc_id, rec in missing[:20]:
            log(f"  would rescue idx {i:04d} | {rec['engine']:12s} | {rec['title'][:60]}")
        log(f"DRY-RUN: total = {len(missing)}")
        return

    ollama_errors = 0

    def on_flush(n_flushes, batch_n, ok, failed, attempts):
        log(
            f"  flush #{n_flushes}: batch={batch_n} ok={ok} fail={failed} "
            f"attempts={attempts} avg={attempts / max(batch_n, 1):.2f}"
        )

    flusher = BatchedFlusher(rc, batch_size=args.batch_size, on_flush=on_flush)

    log("-" * 60)
    for n, (i, doc_id, rec) in enumerate(missing, 1):
        labels = get_ollama_label(rec["content"])
        if "_error" in labels:
            ollama_errors += 1
        flusher.add(
            doc_id, rec, labels,
            query=rec["query"], engine=rec["engine"], harvest_run_id=rec["run_id"],
        )
        if n % 25 == 0 or n == len(missing):
            log(
                f"[{n}/{len(missing)}] ok={flusher.ok} fail={flusher.failed} "
                f"pending={len(flusher.buffer)} ollama_err={ollama_errors} | "
                f"idx {i:04d} | {rec['engine']:12s} | {rec['title'][:50]}"
            )
    flusher.flush()

    log("-" * 60)
    log(
        f"Done. ok={flusher.ok} fail={flusher.failed} "
        f"flushes={flusher.flushes} ollama_errors={ollama_errors} "
        f"total_attempts={flusher.total_attempts} input={len(missing)}"
    )

    res = rc.execute_command(
        "GRAPH.QUERY", GRAPH_NAME,
        f"MATCH (d:Document) WHERE d.id STARTS WITH 'apds_{args.run_id}' RETURN count(d)"
    )
    if res and len(res) > 1 and res[1]:
        log(f"Run {args.run_id} now has: {res[1][0][0]} docs in graph")

    log_fh.close()


if __name__ == "__main__":
    main()
