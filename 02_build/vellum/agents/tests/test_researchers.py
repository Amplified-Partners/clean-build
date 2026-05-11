"""Unit tests for researcher agents.

Tests use httpx MockTransport to avoid real API calls.

Signed-by: Devon-ae57 (daughter session of Devon-3397)
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import patch

import httpx
import pytest

from .. import ResearcherOutput
from ..researcher_calendar import CalendarResearcher
from ..researcher_searxng import SearxngResearcher
from ..researcher_stripe import StripeResearcher
from ..synthesiser import Synthesiser

# Save real client before any patching
_RealAsyncClient = httpx.AsyncClient


def _patched_client(handler):
    """Context manager that patches httpx.AsyncClient to inject a mock transport."""
    transport = httpx.MockTransport(handler)
    return patch(
        "httpx.AsyncClient",
        side_effect=lambda **kwargs: _RealAsyncClient(**{**kwargs, "transport": transport}),
    )


# --- Stripe Researcher Tests ---


class TestStripeResearcher:
    """Tests for StripeResearcher."""

    @pytest.fixture
    def researcher(self, monkeypatch: pytest.MonkeyPatch) -> StripeResearcher:
        monkeypatch.setenv("STRIPE_API_KEY_JESMOND", "sk_test_fake123")
        return StripeResearcher()

    @pytest.mark.asyncio
    async def test_fetch_success(self, researcher: StripeResearcher) -> None:
        """Happy path: returns structured revenue data."""
        charges_response = {
            "data": [
                {"id": "ch_1", "amount": 15000, "status": "succeeded", "description": "Boiler Repair"},
                {"id": "ch_2", "amount": 8500, "status": "succeeded", "description": "Emergency Callout"},
            ]
        }
        refunds_response: dict = {"data": []}
        disputes_response: dict = {"data": []}

        def handler(request: httpx.Request) -> httpx.Response:
            url = str(request.url)
            if "/charges" in url:
                return httpx.Response(200, json=charges_response)
            if "/refunds" in url:
                return httpx.Response(200, json=refunds_response)
            if "/disputes" in url:
                return httpx.Response(200, json=disputes_response)
            return httpx.Response(404)

        with _patched_client(handler):
            date = datetime(2026, 5, 11, 8, 0, tzinfo=timezone.utc)
            result = await researcher.fetch("jesmond", date)

        assert result.source == "stripe"
        assert result.data["total_revenue_gbp"] == 235.0
        assert result.data["transaction_count"] == 2
        assert result.data["refund_count"] == 0
        assert result.data["dispute_count"] == 0
        assert "£235.00" in result.summary
        assert result.summary != "[unavailable]"

    @pytest.mark.asyncio
    async def test_fetch_with_refunds(self, researcher: StripeResearcher) -> None:
        """Refunds are reported in summary."""
        charges_response = {
            "data": [{"id": "ch_1", "amount": 10000, "status": "succeeded", "description": "Repair"}]
        }
        refunds_response = {"data": [{"id": "re_1", "amount": 5000}]}
        disputes_response: dict = {"data": []}

        def handler(request: httpx.Request) -> httpx.Response:
            url = str(request.url)
            if "/charges" in url:
                return httpx.Response(200, json=charges_response)
            if "/refunds" in url:
                return httpx.Response(200, json=refunds_response)
            if "/disputes" in url:
                return httpx.Response(200, json=disputes_response)
            return httpx.Response(404)

        with _patched_client(handler):
            date = datetime(2026, 5, 11, 8, 0, tzinfo=timezone.utc)
            result = await researcher.fetch("jesmond", date)

        assert result.data["refund_count"] == 1
        assert "refund" in result.summary.lower()

    @pytest.mark.asyncio
    async def test_fetch_api_error_returns_unavailable(self, researcher: StripeResearcher) -> None:
        """On API failure, returns [unavailable] without crashing."""

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(401, json={"error": "Unauthorized"})

        with _patched_client(handler):
            date = datetime(2026, 5, 11, 8, 0, tzinfo=timezone.utc)
            result = await researcher.fetch("jesmond", date)

        assert result.source == "stripe"
        assert result.summary == "[unavailable]"

    @pytest.mark.asyncio
    async def test_fetch_no_api_key_returns_unavailable(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Missing API key triggers graceful failure."""
        monkeypatch.delenv("STRIPE_API_KEY_JESMOND", raising=False)
        researcher = StripeResearcher()

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(401, json={"error": "No API key"})

        with _patched_client(handler):
            date = datetime(2026, 5, 11, 8, 0, tzinfo=timezone.utc)
            result = await researcher.fetch("jesmond", date)

        assert result.summary == "[unavailable]"


# --- Calendar Researcher Tests ---


class TestCalendarResearcher:
    """Tests for CalendarResearcher."""

    @pytest.fixture
    def researcher(self, monkeypatch: pytest.MonkeyPatch) -> CalendarResearcher:
        creds = json.dumps({"access_token": "ya29.fake_token"})
        monkeypatch.setenv("GOOGLE_CALENDAR_CREDENTIALS_JESMOND", creds)
        monkeypatch.setenv("GOOGLE_CALENDAR_ID_JESMOND", "primary")
        return CalendarResearcher()

    @pytest.mark.asyncio
    async def test_fetch_success(self, researcher: CalendarResearcher) -> None:
        """Happy path: returns job count and schedule."""
        events_response = {
            "items": [
                {
                    "summary": "John Smith - Boiler Repair",
                    "start": {"dateTime": "2026-05-11T09:00:00+01:00"},
                    "end": {"dateTime": "2026-05-11T10:30:00+01:00"},
                },
                {
                    "summary": "Mary Jones - Leak Fix",
                    "start": {"dateTime": "2026-05-11T11:00:00+01:00"},
                    "end": {"dateTime": "2026-05-11T12:00:00+01:00"},
                },
                {
                    "summary": "David Wilson - Annual Service",
                    "start": {"dateTime": "2026-05-11T14:30:00+01:00"},
                    "end": {"dateTime": "2026-05-11T16:00:00+01:00"},
                },
            ]
        }

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=events_response)

        with _patched_client(handler):
            date = datetime(2026, 5, 11, 8, 0, tzinfo=timezone.utc)
            result = await researcher.fetch("jesmond", date)

        assert result.source == "calendar"
        assert result.data["job_count"] == 3
        assert "John S." in result.data["client_names"]
        assert "Mary J." in result.data["client_names"]
        assert "3 job(s) today" in result.summary

    @pytest.mark.asyncio
    async def test_fetch_empty_calendar(self, researcher: CalendarResearcher) -> None:
        """No events returns appropriate summary."""

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"items": []})

        with _patched_client(handler):
            date = datetime(2026, 5, 11, 8, 0, tzinfo=timezone.utc)
            result = await researcher.fetch("jesmond", date)

        assert result.data["job_count"] == 0
        assert "No jobs" in result.summary

    @pytest.mark.asyncio
    async def test_fetch_api_error_returns_unavailable(self, researcher: CalendarResearcher) -> None:
        """On API failure, returns [unavailable]."""

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(403, json={"error": "Forbidden"})

        with _patched_client(handler):
            date = datetime(2026, 5, 11, 8, 0, tzinfo=timezone.utc)
            result = await researcher.fetch("jesmond", date)

        assert result.summary == "[unavailable]"

    def test_anonymise_name(self) -> None:
        """Name anonymisation works correctly."""
        assert CalendarResearcher._anonymise_name("John Smith - Boiler Repair") == "John S."
        assert CalendarResearcher._anonymise_name("Mary") == "Mary"
        assert CalendarResearcher._anonymise_name("") == "Unknown"
        assert CalendarResearcher._anonymise_name("A B C - Job") == "A B."

    def test_find_gaps(self) -> None:
        """Gap detection finds > 2h gaps between events."""
        events = [
            {
                "summary": "Job A",
                "start": {"dateTime": "2026-05-11T09:00:00+01:00"},
                "end": {"dateTime": "2026-05-11T10:00:00+01:00"},
            },
            {
                "summary": "Job B",
                "start": {"dateTime": "2026-05-11T14:00:00+01:00"},
                "end": {"dateTime": "2026-05-11T15:00:00+01:00"},
            },
        ]
        gaps = CalendarResearcher._find_gaps(events)
        assert len(gaps) == 1
        assert gaps[0]["gap_minutes"] == 240


# --- SearXNG Researcher Tests ---


class TestSearxngResearcher:
    """Tests for SearxngResearcher."""

    @pytest.fixture
    def researcher(self, monkeypatch: pytest.MonkeyPatch) -> SearxngResearcher:
        monkeypatch.setenv("SEARXNG_URL", "http://localhost:8080")
        return SearxngResearcher()

    @pytest.mark.asyncio
    async def test_fetch_success(self, researcher: SearxngResearcher) -> None:
        """Happy path: returns weather and demand data."""
        search_response = {
            "results": [
                {"title": "Newcastle Weather", "content": "Partly cloudy, 14C, light rain expected afternoon"},
                {"title": "Forecast", "content": "Wind NW 12mph"},
            ]
        }

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=search_response)

        with _patched_client(handler):
            date = datetime(2026, 5, 11, 8, 0, tzinfo=timezone.utc)
            result = await researcher.fetch("jesmond", date)

        assert result.source == "searxng"
        assert "weather" in result.data
        assert "demand_signals" in result.data
        assert result.summary != "[unavailable]"

    @pytest.mark.asyncio
    async def test_fetch_searxng_down_degrades_gracefully(self, researcher: SearxngResearcher) -> None:
        """If SearXNG is unreachable, degrades gracefully per sub-request."""

        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("Connection refused")

        with _patched_client(handler):
            date = datetime(2026, 5, 11, 8, 0, tzinfo=timezone.utc)
            result = await researcher.fetch("jesmond", date)

        assert result.source == "searxng"
        assert "unavailable" in result.summary.lower() or "no demand" in result.summary.lower()

    def test_summarise_demand_no_signals(self) -> None:
        """Empty signals produce clear message."""
        assert SearxngResearcher._summarise_demand([]) == "No demand signals detected"

    def test_summarise_demand_with_results(self) -> None:
        """Active queries produce count summary."""
        signals = [
            {"query": "emergency plumber", "result_count": 5},
            {"query": "boiler repair", "result_count": 3},
            {"query": "heating engineer", "result_count": 0},
        ]
        result = SearxngResearcher._summarise_demand(signals)
        assert "2/3" in result
        assert "8 results" in result


# --- Synthesiser Tests ---


class TestSynthesiser:
    """Tests for Synthesiser."""

    @pytest.fixture
    def synthesiser(self, monkeypatch: pytest.MonkeyPatch) -> Synthesiser:
        monkeypatch.setenv("LITELLM_URL", "http://localhost:4000")
        monkeypatch.setenv("LITELLM_API_KEY", "sk-fake-key")
        monkeypatch.setenv("BRIEF_LLM_MODEL", "gpt-4o-mini")
        return Synthesiser()

    @pytest.mark.asyncio
    async def test_synthesise_success(self, synthesiser: Synthesiser) -> None:
        """Happy path: LLM returns a brief."""
        llm_response = {
            "choices": [
                {
                    "message": {
                        "content": (
                            "Morning Bob. Yesterday brought in £235 from 2 jobs — "
                            "boiler repair was your big earner. Today you've got 3 jobs "
                            "lined up, first at 9am. Weather's looking cloudy with rain "
                            "this afternoon, so pack a waterproof. Good demand signals "
                            "for emergency plumbing in the area."
                        )
                    }
                }
            ]
        }

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=llm_response)

        outputs = [
            ResearcherOutput(
                source="stripe",
                data={"total_revenue_gbp": 235.0, "transaction_count": 2},
                summary="£235.00 from 2 transactions. Top: Boiler Repair",
            ),
            ResearcherOutput(
                source="calendar",
                data={"job_count": 3, "first_job": "09:00"},
                summary="3 job(s) today, first at 09:00",
            ),
            ResearcherOutput(
                source="searxng",
                data={"weather": {"summary": "Cloudy, 14C"}},
                summary="Cloudy, 14C. 3/4 demand queries active (12 results)",
            ),
        ]

        with _patched_client(handler):
            date = datetime(2026, 5, 11, 8, 0, tzinfo=timezone.utc)
            result = await synthesiser.synthesise(outputs, date)

        assert "Bob" in result
        assert "235" in result

    @pytest.mark.asyncio
    async def test_synthesise_llm_down_returns_fallback(self, synthesiser: Synthesiser) -> None:
        """If LLM is unreachable, returns a fallback brief."""

        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("Connection refused")

        outputs = [
            ResearcherOutput(
                source="stripe",
                data={"total_revenue_gbp": 100.0},
                summary="£100.00 from 1 transaction",
            ),
            ResearcherOutput(
                source="calendar",
                data={"job_count": 2},
                summary="2 job(s) today",
            ),
        ]

        with _patched_client(handler):
            date = datetime(2026, 5, 11, 8, 0, tzinfo=timezone.utc)
            result = await synthesiser.synthesise(outputs, date)

        assert "Morning Brief" in result
        assert "Stripe" in result
        assert "Calendar" in result
        assert "fallback" in result.lower()

    @pytest.mark.asyncio
    async def test_synthesise_handles_unavailable_sources(self, synthesiser: Synthesiser) -> None:
        """Unavailable sources are noted in context, not crashed on."""
        llm_response = {
            "choices": [
                {"message": {"content": "Morning Bob. Limited data today — Stripe was unavailable."}}
            ]
        }

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=llm_response)

        outputs = [
            ResearcherOutput(
                source="stripe",
                data={"error": "auth failed"},
                summary="[unavailable]",
            ),
            ResearcherOutput(
                source="calendar",
                data={"job_count": 1},
                summary="1 job today",
            ),
        ]

        with _patched_client(handler):
            date = datetime(2026, 5, 11, 8, 0, tzinfo=timezone.utc)
            result = await synthesiser.synthesise(outputs, date)

        assert "unavailable" in result.lower() or "Bob" in result
