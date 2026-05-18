"""Ledger Interceptor — middleware that records every agent action.

Architecture:
    Agent Action → Interceptor → POST /api/v1/council/speak → Ledger records it
                                → POST /api/v1/submit → Ingestion gate validates it

The interceptor fires BEFORE the action executes (intent) and AFTER
(result). This gives the Ledger a complete timeline:
    [13:01:00] Devon STARTING: deploying vellum-v6
    [13:01:03] Devon COMPLETED: deploying vellum-v6 (3.2s)

If the action fails:
    [13:01:00] Devon STARTING: deploying vellum-v6
    [13:01:05] Devon FAILED: deploying vellum-v6 — ConnectionError

Devon-b5dc | 2026-05-18
"""

from __future__ import annotations

import datetime as dt
import functools
import time
import traceback
from contextlib import contextmanager
from typing import Any, Callable

import httpx


class LedgerInterceptor:
    """Middleware that auto-posts agent actions to the Ledger.

    Every agent gets one instance. It carries the agent's identity
    (name, model, cutoff) and fires to the Ledger on every action.
    """

    def __init__(
        self,
        agent_name: str,
        ledger_url: str = "http://135.181.161.131:8410",
        model: str | None = None,
        knowledge_cutoff: str | None = None,
        session_id: str | None = None,
        communication_mode: str = "ASYNC",
        timeout: float = 5.0,
    ) -> None:
        self.agent_name = agent_name
        self.ledger_url = ledger_url.rstrip("/")
        self.model = model
        self.knowledge_cutoff = knowledge_cutoff
        self.session_id = session_id
        self.communication_mode = communication_mode
        self._client = httpx.Client(timeout=timeout)

    def _post_to_mesh(
        self,
        message: str,
        epistemic_tier: str = "STRUCTURED",
        communication_mode: str | None = None,
    ) -> dict[str, Any] | None:
        """Fire a message to the Ledger mesh. Best-effort — never blocks the action."""
        try:
            payload: dict[str, Any] = {
                "speaker": self.agent_name,
                "message": message,
                "epistemic_tier": epistemic_tier,
                "communication_mode": communication_mode or self.communication_mode,
            }
            if self.model:
                payload["model"] = self.model
            if self.knowledge_cutoff:
                payload["knowledge_cutoff"] = self.knowledge_cutoff
            resp = self._client.post(
                f"{self.ledger_url}/api/v1/council/speak",
                json=payload,
            )
            resp.raise_for_status()
            return resp.json()
        except Exception:
            return None

    def record(
        self,
        message: str,
        epistemic_tier: str = "STRUCTURED",
        communication_mode: str | None = None,
    ) -> dict[str, Any] | None:
        """Direct fire-and-forget record to the Ledger."""
        return self._post_to_mesh(message, epistemic_tier, communication_mode)

    def action(self, description: str, epistemic_tier: str = "STRUCTURED") -> Callable:
        """Decorator that records action start + completion/failure to the Ledger."""

        def decorator(func: Callable) -> Callable:
            @functools.wraps(func)
            def wrapper(*args: Any, **kwargs: Any) -> Any:
                self._post_to_mesh(
                    f"STARTING: {description}",
                    epistemic_tier=epistemic_tier,
                )
                start = time.monotonic()
                try:
                    result = func(*args, **kwargs)
                    elapsed = time.monotonic() - start
                    self._post_to_mesh(
                        f"COMPLETED: {description} ({elapsed:.1f}s)",
                        epistemic_tier=epistemic_tier,
                    )
                    return result
                except Exception as exc:
                    elapsed = time.monotonic() - start
                    self._post_to_mesh(
                        f"FAILED: {description} — {type(exc).__name__}: {exc} ({elapsed:.1f}s)",
                        epistemic_tier="INTUITED",
                    )
                    raise

            return wrapper

        return decorator

    @contextmanager
    def action_context(self, description: str, epistemic_tier: str = "STRUCTURED"):
        """Context manager that records action start + completion/failure."""
        self._post_to_mesh(
            f"STARTING: {description}",
            epistemic_tier=epistemic_tier,
        )
        start = time.monotonic()
        try:
            yield
            elapsed = time.monotonic() - start
            self._post_to_mesh(
                f"COMPLETED: {description} ({elapsed:.1f}s)",
                epistemic_tier=epistemic_tier,
            )
        except Exception as exc:
            elapsed = time.monotonic() - start
            self._post_to_mesh(
                f"FAILED: {description} — {type(exc).__name__}: {exc} ({elapsed:.1f}s)",
                epistemic_tier="INTUITED",
            )
            raise

    def write_baton(
        self,
        state: str = "sleeping",
        last_action: str | None = None,
        pending_tasks: list[str] | None = None,
        decisions_made: list[str] | None = None,
        mesh_cursor: int = 0,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """Write the baton pass to the Ledger — agent going to sleep."""
        try:
            payload = {
                "session_id": self.session_id or "unknown",
                "state": state,
                "last_action": last_action,
                "pending_tasks": pending_tasks or [],
                "decisions_made": decisions_made or [],
                "mesh_cursor": mesh_cursor,
                "context": context or {},
            }
            resp = self._client.post(
                f"{self.ledger_url}/api/v1/baton",
                json=payload,
            )
            resp.raise_for_status()
            return resp.json()
        except Exception:
            return None

    def read_baton(self) -> dict[str, Any] | None:
        """Read the baton — agent waking up, getting context."""
        try:
            resp = self._client.get(f"{self.ledger_url}/api/v1/baton")
            resp.raise_for_status()
            return resp.json()
        except Exception:
            return None

    def close(self) -> None:
        """Close the HTTP client."""
        self._client.close()

    def __enter__(self) -> "LedgerInterceptor":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()
