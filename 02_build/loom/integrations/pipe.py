"""Pipe integration — submit proposals and rollbacks.

The pipe is sovereign over Brain admissions. The loom proposes;
the pipe disposes. No back doors.

In v1 this is a stub that records submissions in-memory for
testing. Production will call the pipe's REST API.

Dana | 2026-05-20 | From Computer's Loom spec §2.2
"""

from __future__ import annotations

import logging
from uuid import uuid4

log = logging.getLogger("loom.integrations.pipe")


class PipeClient:
    """Adapter for submitting proposals to the ingestion pipe.

    v1: in-memory stub. Records submissions for testing.
    v2: HTTP client to the pipe's meta-change API.
    """

    def __init__(self) -> None:
        self._submissions: list[dict] = []
        self._rollbacks: list[str] = []

    async def submit(self, submission: dict) -> dict:
        """Submit a proposal through the pipe.

        Returns a receipt with a witness_id.
        The pipe validates, routes, and records. The loom
        never writes the Brain directly.
        """
        witness_id = str(uuid4())
        record = {
            "witness_id": witness_id,
            "status": "submitted",
            "submission": submission,
        }
        self._submissions.append(record)
        log.info("Pipe submission: %s (witness: %s)", submission.get("kind"), witness_id)
        return record

    async def rollback(self, proposal_id: str) -> dict:
        """Roll back a proposal through the pipe.

        Rollbacks are first-class events — they're witnessed,
        not silently undone.
        """
        self._rollbacks.append(proposal_id)
        log.info("Pipe rollback requested: %s", proposal_id)
        return {"status": "rolled_back", "proposal_id": proposal_id}

    def get_submissions(self) -> list[dict]:
        """For testing — return all submissions."""
        return list(self._submissions)

    def get_rollbacks(self) -> list[str]:
        """For testing — return all rollback requests."""
        return list(self._rollbacks)

    def clear(self) -> None:
        """For testing — reset state."""
        self._submissions.clear()
        self._rollbacks.clear()
