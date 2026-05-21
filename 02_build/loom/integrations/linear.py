"""Linear integration — create issues, label, transition state.

v1: in-memory stub for testing.
Production: GraphQL client to Linear API.

Dana | 2026-05-20 | From Computer's Loom spec §2.2
"""

from __future__ import annotations

import logging
from uuid import uuid4

log = logging.getLogger("loom.integrations.linear")


class LinearClient:
    """Adapter for Linear issue management."""

    def __init__(self) -> None:
        self._issues: list[dict] = []
        self._closed: list[dict] = []

    async def create_issue(self, issue_data: dict) -> dict:
        """Create a Linear issue.

        Returns a dict with the issue ID.
        """
        issue_id = str(uuid4())
        record = {
            "id": issue_id,
            "title": issue_data.get("title", ""),
            "body": issue_data.get("body", ""),
            "label": issue_data.get("label", ""),
            "metadata": issue_data.get("metadata", {}),
            "status": "open",
        }
        self._issues.append(record)
        log.info("Linear issue created: %s — %s", issue_id, record["title"])
        return record

    async def close_issue(self, proposal_id: str, label: str) -> dict:
        """Close a Linear issue by proposal ID."""
        record = {
            "proposal_id": proposal_id,
            "label": label,
            "status": "closed",
        }
        self._closed.append(record)
        log.info("Linear issue closed: %s (%s)", proposal_id, label)
        return record

    def get_issues(self) -> list[dict]:
        """For testing."""
        return list(self._issues)

    def get_closed(self) -> list[dict]:
        """For testing."""
        return list(self._closed)

    def clear(self) -> None:
        """For testing."""
        self._issues.clear()
        self._closed.clear()
