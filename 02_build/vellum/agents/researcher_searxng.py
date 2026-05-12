"""SearXNG researcher — weather and local demand signals.

Signed-by: Devon-ae57 (daughter session of Devon-3397)
"""

from __future__ import annotations

import os
from datetime import datetime

import httpx

from . import ResearcherOutput


class SearxngResearcher:
    """Queries SearXNG for weather and plumbing demand signals."""

    DEMAND_QUERIES: list[str] = [
        "emergency plumber newcastle",
        "boiler repair jesmond",
        "plumber jesmond newcastle",
        "heating engineer newcastle",
    ]

    def __init__(self) -> None:
        self._base_url: str = os.environ.get("SEARXNG_URL", "http://localhost:8080")

    async def fetch(self, tenant_id: str, date: datetime) -> ResearcherOutput:
        """Fetch weather + demand signals from SearXNG."""
        try:
            return await self._fetch_internal(tenant_id, date)
        except Exception as exc:
            return ResearcherOutput(
                source="searxng",
                data={"error": str(exc)},
                summary="[unavailable]",
            )

    async def _fetch_internal(self, tenant_id: str, date: datetime) -> ResearcherOutput:
        async with httpx.AsyncClient(base_url=self._base_url, timeout=30.0) as client:
            weather = await self._fetch_weather(client)
            demand = await self._fetch_demand_signals(client)

        data = {
            "weather": weather,
            "demand_signals": demand,
            "date": date.strftime("%Y-%m-%d"),
        }

        # Build summary
        weather_summary = weather.get("summary", "Weather unavailable")
        demand_summary = self._summarise_demand(demand)

        summary = f"{weather_summary}. {demand_summary}"

        return ResearcherOutput(
            source="searxng",
            data=data,
            summary=summary,
        )

    async def _fetch_weather(self, client: httpx.AsyncClient) -> dict:
        """Query SearXNG for Newcastle weather forecast."""
        try:
            resp = await client.get(
                "/search",
                params={
                    "q": "Newcastle upon Tyne weather forecast today",
                    "format": "json",
                    "engines": "duckduckgo,google",
                    "categories": "general",
                },
            )
            resp.raise_for_status()
            results = resp.json().get("results", [])

            # Extract weather info from top results
            weather_snippets: list[str] = []
            for result in results[:5]:
                content = result.get("content", "")
                if content:
                    weather_snippets.append(content)

            summary = weather_snippets[0][:200] if weather_snippets else "No weather data found"

            return {
                "summary": summary,
                "result_count": len(results),
                "top_results": [
                    {"title": r.get("title", ""), "snippet": r.get("content", "")[:150]}
                    for r in results[:3]
                ],
            }
        except Exception as exc:
            return {"summary": "Weather unavailable", "error": str(exc)}

    async def _fetch_demand_signals(self, client: httpx.AsyncClient) -> list[dict]:
        """Query SearXNG for plumbing demand signals."""
        signals: list[dict] = []
        for query in self.DEMAND_QUERIES:
            try:
                resp = await client.get(
                    "/search",
                    params={
                        "q": query,
                        "format": "json",
                        "engines": "duckduckgo,google",
                        "categories": "general",
                    },
                )
                resp.raise_for_status()
                results = resp.json().get("results", [])
                signals.append({
                    "query": query,
                    "result_count": len(results),
                    "top_result": results[0].get("title", "") if results else None,
                })
            except Exception:
                signals.append({
                    "query": query,
                    "result_count": 0,
                    "top_result": None,
                    "error": "search failed",
                })
        return signals

    @staticmethod
    def _summarise_demand(signals: list[dict]) -> str:
        """Create a one-line demand summary."""
        active_queries = [s for s in signals if s.get("result_count", 0) > 0]
        if not active_queries:
            return "No demand signals detected"
        total_results = sum(s.get("result_count", 0) for s in active_queries)
        return f"{len(active_queries)}/{len(signals)} demand queries active ({total_results} results)"
