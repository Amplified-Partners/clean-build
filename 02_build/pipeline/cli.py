#!/usr/bin/env python3
"""
Pipeline CLI — run, resume, status, retry-dlq.

Usage:
    python -m pipeline.cli run /opt/amplified/vault/store_b_clean
    python -m pipeline.cli run /opt/amplified/vault/store_b_clean --classify-only
    python -m pipeline.cli run /opt/amplified/vault/store_b_clean --dry-run
    python -m pipeline.cli resume /opt/amplified/vault/store_b_clean
    python -m pipeline.cli status /opt/amplified/vault/store_b_clean
    python -m pipeline.cli retry-dlq /opt/amplified/vault/store_b_clean

Signed-by: Devon-220b | 2026-05-07 | session devin-220b8b8d17044c9f85ac8ec5eb4154b5
"""

from __future__ import annotations

import argparse
import json

from .orchestrator import PipelineOrchestrator


def cmd_run(args: argparse.Namespace) -> None:
    orch = PipelineOrchestrator(
        corpus_dir=args.corpus_dir,
        db_dir=args.db_dir,
        log_dir=args.log_dir,
        max_workers=args.workers,
        batch_size=args.batch_size,
        dry_run=args.dry_run,
        classify_only=args.classify_only,
        skip_write=args.skip_write,
    )
    stats = orch.run()
    print(json.dumps(stats.model_dump(), indent=2))


def cmd_resume(args: argparse.Namespace) -> None:
    orch = PipelineOrchestrator(
        corpus_dir=args.corpus_dir,
        db_dir=args.db_dir,
        log_dir=args.log_dir,
        max_workers=args.workers,
        batch_size=args.batch_size,
    )
    stats = orch.resume()
    print(json.dumps(stats.model_dump(), indent=2))


def cmd_status(args: argparse.Namespace) -> None:
    orch = PipelineOrchestrator(
        corpus_dir=args.corpus_dir,
        db_dir=args.db_dir,
        dry_run=True,
    )
    status = orch.status()
    print(json.dumps(status, indent=2))


def cmd_retry_dlq(args: argparse.Namespace) -> None:
    orch = PipelineOrchestrator(
        corpus_dir=args.corpus_dir,
        db_dir=args.db_dir,
        dry_run=True,
    )
    count = orch.retry_dlq(max_retries=args.max_retries)
    print(f"Re-queued {count} items from DLQ.")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="pipeline",
        description="Amplified Partners — Unified Ingestion Pipeline",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # Common args
    def add_common(p: argparse.ArgumentParser) -> None:
        p.add_argument("corpus_dir", help="Path to the corpus directory (e.g. store_b_clean)")
        p.add_argument("--db-dir", default=None, help="Pipeline DB/checkpoint directory")
        p.add_argument("--log-dir", default=None, help="Log output directory")

    # run
    p_run = sub.add_parser("run", help="Run the full pipeline")
    add_common(p_run)
    p_run.add_argument("--workers", type=int, default=12, help="Max concurrent workers")
    p_run.add_argument("--batch-size", type=int, default=50, help="Write batch size")
    p_run.add_argument("--dry-run", action="store_true", help="Scan and register only, no classification")
    p_run.add_argument("--classify-only", action="store_true", help="Classify but skip orchestrate+write")
    p_run.add_argument("--skip-write", action="store_true", help="Classify+orchestrate but skip write")
    p_run.set_defaults(func=cmd_run)

    # resume
    p_resume = sub.add_parser("resume", help="Resume from last checkpoint")
    add_common(p_resume)
    p_resume.add_argument("--workers", type=int, default=12)
    p_resume.add_argument("--batch-size", type=int, default=50)
    p_resume.set_defaults(func=cmd_resume)

    # status
    p_status = sub.add_parser("status", help="Show pipeline status")
    add_common(p_status)
    p_status.set_defaults(func=cmd_status)

    # retry-dlq
    p_retry = sub.add_parser("retry-dlq", help="Retry items from the DLQ")
    add_common(p_retry)
    p_retry.add_argument("--max-retries", type=int, default=3)
    p_retry.set_defaults(func=cmd_retry_dlq)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
