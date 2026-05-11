"""Synthesiser — composes a narrative brief from researcher outputs.

Uses LiteLLM on Beast to generate a 30-second-read morning summary.

Signed-by: Devon-ae57 (daughter session of Devon-3397)
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

import httpx

from . import ResearcherOutput

BRIEF_SYSTEM_PROMPT = (
    "You are writing a morning operational brief for Bob, a plumber in Jesmond, "
    "Newcastle. Write in plain English, no jargon. Focus on: what happened yesterday "
    "(money), what's happening today (schedule), what to watch for (weather/demand). "
    "Keep it under 150 words."
)


class Synthesiser:
    """Composes a narrative brief from multiple ResearcherOutput objects."""

    def __init__(self) -> None:
        self._litellm_url: str = os.environ.get("LITELLM_URL", "http://localhost:4000")
        self._litellm_key: str = os.environ.get("LITELLM_API_KEY", "")
        self._model: str = os.environ.get("BRIEF_LLM_MODEL", "gpt-4o-mini")

    async def synthesise(self, outputs: list[ResearcherOutput], date: datetime) -> str:
        """Take researcher outputs and compose a narrative brief.

        Returns the brief text, or a fallback summary on failure.
        """
        try:
            return await self._synthesise_internal(outputs, date)
        except Exception as exc:
            return self._fallback_brief(outputs, date, error=str(exc))

    async def _synthesise_internal(self, outputs: list[ResearcherOutput], date: datetime) -> str:
        # Build the data context for the LLM
        context_parts: list[str] = []
        for output in outputs:
            if output.summary == "[unavailable]":
                context_parts.append(f"[{output.source}]: Data unavailable")
            else:
                context_parts.append(f"[{output.source}]: {output.summary}")
                # Include structured data for richer generation
                for key, value in output.data.items():
                    if key != "error":
                        context_parts.append(f"  {key}: {value}")

        user_message = (
            f"Date: {date.strftime('%A %d %B %Y')}\n\n"
            f"Data from researchers:\n" + "\n".join(context_parts)
        )

        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self._litellm_key:
            headers["Authorization"] = f"Bearer {self._litellm_key}"

        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": BRIEF_SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            "max_tokens": 300,
            "temperature": 0.7,
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{self._litellm_url}/v1/chat/completions",
                headers=headers,
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()

        choices = data.get("choices", [])
        if not choices:
            raise ValueError("LLM returned no choices")

        return choices[0]["message"]["content"].strip()

    @staticmethod
    def _fallback_brief(outputs: list[ResearcherOutput], date: datetime, error: str) -> str:
        """Generate a minimal fallback if LLM is unavailable."""
        lines = [f"Morning Brief — {date.strftime('%A %d %B %Y')}", ""]
        for output in outputs:
            if output.summary != "[unavailable]":
                lines.append(f"• {output.source.title()}: {output.summary}")
            else:
                lines.append(f"• {output.source.title()}: Data unavailable")
        lines.append("")
        lines.append(f"[Auto-generated fallback — LLM error: {error}]")
        return "\n".join(lines)
