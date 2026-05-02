"""
LLM integration — routes inference requests through LiteLLM proxy.

Each entity has a model override; the LiteLLM proxy handles
key management and provider abstraction.

Authored by Devon | 2026-05-02 | devin-701075c43e444229aa32f993bf60b36a
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

import httpx

logger = logging.getLogger(__name__)


@dataclass
class LLMResponse:
    content: str
    model: str
    tokens_used: int = 0
    latency_ms: float = 0.0
    finish_reason: str = ""


@dataclass
class LLMClient:
    """Async client for LiteLLM proxy."""

    base_url: str = "http://litellm:4000"
    api_key: str = ""
    timeout: float = 120.0
    _client: httpx.AsyncClient | None = field(default=None, repr=False)

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            headers: dict[str, str] = {"Content-Type": "application/json"}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=headers,
                timeout=self.timeout,
            )
        return self._client

    async def chat(
        self,
        model: str,
        system_prompt: str,
        messages: list[dict[str, str]],
        temperature: float = 0.0,
        max_tokens: int = 8192,
    ) -> LLMResponse:
        """Send a chat completion request to LiteLLM."""
        client = await self._get_client()
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                *messages,
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        start = time.monotonic()
        try:
            resp = await client.post("/chat/completions", json=payload)
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPStatusError as exc:
            logger.error("LiteLLM HTTP error: %s %s", exc.response.status_code, exc.response.text)
            raise
        except httpx.RequestError as exc:
            logger.error("LiteLLM request error: %s", exc)
            raise

        latency = (time.monotonic() - start) * 1000
        choice = data.get("choices", [{}])[0]
        usage = data.get("usage", {})

        return LLMResponse(
            content=choice.get("message", {}).get("content", ""),
            model=data.get("model", model),
            tokens_used=usage.get("total_tokens", 0),
            latency_ms=round(latency, 1),
            finish_reason=choice.get("finish_reason", ""),
        )

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
