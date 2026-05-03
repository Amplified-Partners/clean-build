# Authored by Devon-9a6b, 2026-05-03 (session devin-9a6bd256bd7c4a90a083a471fa94a810)
"""Verdict object + writer.

Each insight runner returns a Verdict. The runner CLI persists every verdict
to results/<INS-NNN>/verdict.json with a stable schema so it can be picked up
later by the catalogue updater and the master report.
"""
from __future__ import annotations

import dataclasses
import json
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

RESULTS_ROOT = Path(__file__).resolve().parent / "results"
RESULTS_ROOT.mkdir(parents=True, exist_ok=True)

SESSION_ID = "devin-9a6bd256bd7c4a90a083a471fa94a810"
AGENT = "Devon-9a6b"


def _git_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=str(Path(__file__).resolve().parent),
            stderr=subprocess.DEVNULL,
        ).decode().strip()
    except Exception:
        return "unknown"


@dataclass
class Verdict:
    insight_id: str           # e.g. INS-067
    title: str
    vertical: str             # 'Retail'
    verdict: str              # PROVEN | PLAUSIBLE | DISPROVEN | DEFERRED
    test_class: str           # base_rate | correlation | distribution | existence | manual
    summary: str              # one-line
    evidence: list[dict[str, Any]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    confidence: int = 70      # 0-100, OPINION confidence per 00_authority/OPINION_CONFIDENCE.md
    run_at_utc: str = ""
    git_sha: str = ""
    session_id: str = SESSION_ID
    signed_by: str = AGENT

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)

    def write(self) -> Path:
        if not self.run_at_utc:
            self.run_at_utc = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        if not self.git_sha:
            self.git_sha = _git_sha()
        out_dir = RESULTS_ROOT / self.insight_id
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / "verdict.json"
        path.write_text(json.dumps(self.to_dict(), indent=2, default=str))
        return path


VERDICT_BANDS = ("PROVEN", "PLAUSIBLE", "DISPROVEN", "DEFERRED", "BLOCKED")
