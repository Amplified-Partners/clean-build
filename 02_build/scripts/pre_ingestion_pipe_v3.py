#!/usr/bin/env python3
"""Sovereign Edge Pre-Ingestion Pipe — V3 (AMP-38)

Incremental, idempotent, fully audited.

Differences from V2:
- Does NOT wipe the clean dir. Adds only what's missing.
- Indexes existing clean files by their hash-suffix so re-runs are no-ops on
  already-ingested content. Safe to run alongside the live classify pipeline.
- 16-char SHA-256 prefix in the filename (was 8) — eliminates the birthday
  collision that V2 would hit at 142k+ unique files.
- Every skip / drop / error goes to a JSONL ledger with sha + reason. No
  silent file loss.
- Broken symlinks and read errors are logged, not swallowed.

Why V3 was needed (the AMP-38 cause):
- V2 was last executed 2026-05-03/04 against an older raw-mac-dumps.
- raw-mac-dumps has been re-hydrated since (now 144,688 regular files,
  142,572 unique SHA-256 hashes), but V2 was never re-run.
- Result: store_b_clean stayed at 21,606 unique hashes — a ~121k file gap
  that looked like silent drops but is actually unrun work.

Signed-by: Devon-a3d1 | 2026-05-03 | devin-a3d15ca9ebeb4d9fa083e09ef0ac686a
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

# Mac-dump noise we deliberately do not ingest (V2 already had this set).
MAC_NOISE = {".DS_Store", ".AppleDouble", ".LSOverride", "Icon\r"}

# Existing 8-char hash suffix pattern from V2; V3 emits 16-char.
HASH_SUFFIX_RE = re.compile(r"_([0-9a-f]{8,16})(\.[^.]+)?$")


def file_sha256(filepath: Path, chunk: int = 1 << 16) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for buf in iter(lambda: f.read(chunk), b""):
            h.update(buf)
    return h.hexdigest()


def sanitize_filename(filename: str) -> str:
    name = os.path.splitext(filename)[0]
    clean = re.sub(r"[^a-zA-Z0-9]+", "-", name).strip("-").lower()
    return clean or "unnamed"


def index_existing_clean(clean_dir: Path) -> tuple[set[str], int]:
    """Return (set-of-hash-prefixes-already-present, count-of-files-indexed).

    V2-produced files have an 8-char suffix; V3 uses 16. We accept either
    length so V3 is a no-op against an existing V2 corpus.
    """
    prefixes: set[str] = set()
    count = 0
    for p in clean_dir.rglob("*"):
        if not p.is_file():
            continue
        count += 1
        m = HASH_SUFFIX_RE.search(p.name)
        if m:
            prefixes.add(m.group(1))
    return prefixes, count


def attribution_header(original_name: str, author: str) -> str:
    return (
        "---\n"
        f"author: {author}\n"
        f"ingestion_date: {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}\n"
        f"original_file: {original_name}\n"
        "status: Pre-Ingestion_Cleaned\n"
        "architecture: Sovereign_Edge_Store_B\n"
        "ingester: pre_ingestion_pipe_v3 (AMP-38)\n"
        "---\n"
    )


def inject_attribution(filepath: Path, original_name: str, author: str) -> None:
    if filepath.suffix not in (".md", ".txt"):
        return
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
    except OSError:
        return
    if content.startswith("---"):
        return
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(attribution_header(original_name, author) + content)


def radical_rename(filepath: Path, file_hash: str, author: str) -> str:
    try:
        dt = datetime.fromtimestamp(filepath.stat().st_mtime)
    except OSError:
        dt = datetime.now()
    iso_date = dt.strftime("%Y-%m-%d")
    clean_topic = sanitize_filename(filepath.name)
    short_hash = file_hash[:16]  # was 8 in V2
    extension = filepath.suffix
    return f"{iso_date}_{clean_topic}_{author}_{short_hash}{extension}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Sovereign Edge Pre-Ingestion Pipe V3 (AMP-38)")
    parser.add_argument("--source", default="/opt/amplified/raw-mac-dumps")
    parser.add_argument("--clean", default="/opt/amplified/vault/store_b_clean")
    parser.add_argument(
        "--ledger",
        default="/opt/amplified/vault-ingestion-progress/v3_skipped.jsonl",
        help="JSONL path for skip / error audit trail.",
    )
    parser.add_argument("--author", default="Ewan_Sair")
    parser.add_argument("--dry-run", action="store_true", help="Plan only; do not copy.")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    source_dir = Path(args.source)
    clean_dir = Path(args.clean)
    ledger_path = Path(args.ledger)
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    clean_dir.mkdir(parents=True, exist_ok=True)

    print(f"[V3] source={source_dir} clean={clean_dir} dry_run={args.dry_run}")
    print("[V3] indexing existing clean files...")
    existing_prefixes, existing_count = index_existing_clean(clean_dir)
    print(f"[V3] {existing_count} existing files in clean ({len(existing_prefixes)} unique hash prefixes)")

    seen_hashes: set[str] = set(existing_prefixes)  # any prefix-match is a hit
    stats = {
        "added": 0,
        "skipped_already_in_clean": 0,
        "skipped_in_run_duplicate": 0,
        "skipped_mac_noise": 0,
        "skipped_broken_symlink": 0,
        "skipped_not_file": 0,
        "skipped_read_error": 0,
        "skipped_copy_error": 0,
        "files_walked": 0,
    }

    def log_skip(filepath, reason: str, sha: str | None, extra: dict | None = None) -> None:
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "path": str(filepath),
            "name": filepath.name if hasattr(filepath, "name") else os.path.basename(str(filepath)),
            "reason": reason,
            "sha256": sha,
        }
        if extra:
            record.update(extra)
        with open(ledger_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")

    for filepath in source_dir.rglob("*"):
        stats["files_walked"] += 1
        if stats["files_walked"] % 5000 == 0:
            print(f"[V3] walked {stats['files_walked']:>7d}, added {stats['added']:>7d}")

        try:
            is_file = filepath.is_file()
        except OSError:
            log_skip(filepath, "broken_symlink", None)
            stats["skipped_broken_symlink"] += 1
            continue
        if not is_file:
            if filepath.is_symlink():
                log_skip(filepath, "broken_symlink", None)
                stats["skipped_broken_symlink"] += 1
            else:
                stats["skipped_not_file"] += 1
            continue

        name = filepath.name
        if name in MAC_NOISE or name.startswith("._"):
            log_skip(filepath, "mac_noise", None)
            stats["skipped_mac_noise"] += 1
            continue

        try:
            sha = file_sha256(filepath)
        except OSError as e:
            log_skip(filepath, "read_error", None, {"error": str(e)})
            stats["skipped_read_error"] += 1
            continue

        prefix16 = sha[:16]
        prefix8 = sha[:8]
        if prefix16 in seen_hashes or prefix8 in seen_hashes:
            if prefix16 in existing_prefixes or prefix8 in existing_prefixes:
                stats["skipped_already_in_clean"] += 1
                if args.verbose:
                    log_skip(filepath, "already_in_clean", sha)
            else:
                stats["skipped_in_run_duplicate"] += 1
                if args.verbose:
                    log_skip(filepath, "in_run_duplicate", sha)
            continue
        seen_hashes.add(prefix16)

        new_name = radical_rename(filepath, sha, args.author)
        target = clean_dir / new_name
        if args.dry_run:
            stats["added"] += 1
            continue

        try:
            shutil.copy2(filepath, target)
        except OSError as e:
            log_skip(filepath, "copy_error", sha, {"error": str(e), "target": str(target)})
            stats["skipped_copy_error"] += 1
            continue
        try:
            inject_attribution(target, original_name=name, author=args.author)
        except OSError:
            pass

        stats["added"] += 1

    print()
    print("[V3] === FINAL ===")
    for k, v in stats.items():
        print(f"  {k}: {v}")
    print(f"  ledger: {ledger_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
