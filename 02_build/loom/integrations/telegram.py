"""Telegram integration — critical alerts only.

Never warnings. Critical only. Ewan's chat.

v1: in-memory stub for testing.
Production: HTTP POST to Telegram Bot API.

Dana | 2026-05-20 | From Computer's Loom spec §2.2
"""

from __future__ import annotations

import logging

log = logging.getLogger("loom.integrations.telegram")


class TelegramClient:
    """Adapter for sending Telegram alerts."""

    def __init__(self) -> None:
        self._alerts: list[dict] = []

    async def alert(self, message: str, evidence: dict | None = None) -> dict:
        """Send a critical alert to Ewan's Telegram.

        Only called for severity=critical findings.
        Never called for warnings or info.
        """
        record = {
            "message": message,
            "evidence": evidence or {},
            "status": "sent",
        }
        self._alerts.append(record)
        log.warning("TELEGRAM ALERT: %s", message)
        return record

    def get_alerts(self) -> list[dict]:
        """For testing."""
        return list(self._alerts)

    def clear(self) -> None:
        """For testing."""
        self._alerts.clear()
