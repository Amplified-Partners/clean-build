"""
Structured logging for the pipeline.

JSON lines to file + human-readable to stderr. Langfuse integration is
optional (enabled via LANGFUSE_PUBLIC_KEY env var).

Signed-by: Devon-220b | 2026-05-07 | session devin-220b8b8d17044c9f85ac8ec5eb4154b5
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path


class JSONFormatter(logging.Formatter):
    """Emit log records as single-line JSON."""

    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info and record.exc_info[0]:
            entry["exc"] = self.formatException(record.exc_info)
        extra = {
            k: v for k, v in record.__dict__.items()
            if k not in logging.LogRecord("", 0, "", 0, None, None, None).__dict__
            and k not in ("message", "msg", "args")
        }
        if extra:
            entry["extra"] = extra
        return json.dumps(entry, default=str)


def setup_logging(
    log_dir: str | Path | None = None,
    level: int = logging.INFO,
    run_id: str = "",
) -> logging.Logger:
    """Configure pipeline logging.

    - JSON lines → ``{log_dir}/pipeline_{run_id}.jsonl``
    - Human-readable → stderr
    """
    logger = logging.getLogger("amplified.pipeline")
    if logger.handlers:
        return logger
    logger.setLevel(level)
    logger.propagate = False

    # stderr handler (human-readable)
    stderr = logging.StreamHandler(sys.stderr)
    stderr.setFormatter(
        logging.Formatter("[%(asctime)s] %(levelname)-7s %(name)s — %(message)s", datefmt="%H:%M:%S")
    )
    logger.addHandler(stderr)

    # File handler (JSON lines)
    if log_dir:
        log_path = Path(log_dir)
        log_path.mkdir(parents=True, exist_ok=True)
        suffix = f"_{run_id}" if run_id else ""
        fh = logging.FileHandler(log_path / f"pipeline{suffix}.jsonl", encoding="utf-8")
        fh.setFormatter(JSONFormatter())
        logger.addHandler(fh)

    return logger


def get_logger(name: str = "") -> logging.Logger:
    """Get a child logger under amplified.pipeline."""
    base = "amplified.pipeline"
    return logging.getLogger(f"{base}.{name}" if name else base)
