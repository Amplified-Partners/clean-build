"""Google Calendar researcher — fetches today's schedule for a tenant.

Signed-by: Devon-ae57 (daughter session of Devon-3397)
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone

import httpx

from . import ResearcherOutput


class CalendarResearcher:
    """Fetches today's Google Calendar events for the tenant."""

    def __init__(self) -> None:
        self._credentials_json: str = os.environ.get("GOOGLE_CALENDAR_CREDENTIALS_JESMOND", "")
        self._calendar_id: str = os.environ.get("GOOGLE_CALENDAR_ID_JESMOND", "primary")

    async def fetch(self, tenant_id: str, date: datetime) -> ResearcherOutput:
        """Fetch today's calendar events for the tenant."""
        try:
            return await self._fetch_internal(tenant_id, date)
        except Exception as exc:
            return ResearcherOutput(
                source="calendar",
                data={"error": str(exc)},
                summary="[unavailable]",
            )

    async def _fetch_internal(self, tenant_id: str, date: datetime) -> ResearcherOutput:
        credentials = json.loads(self._credentials_json) if self._credentials_json else {}
        access_token = await self._get_access_token(credentials)

        day_start = datetime(date.year, date.month, date.day, tzinfo=timezone.utc)
        day_end = day_start + timedelta(days=1)

        headers = {"Authorization": f"Bearer {access_token}"}
        params = {
            "timeMin": day_start.isoformat(),
            "timeMax": day_end.isoformat(),
            "singleEvents": "true",
            "orderBy": "startTime",
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                f"https://www.googleapis.com/calendar/v3/calendars/{self._calendar_id}/events",
                headers=headers,
                params=params,
            )
            resp.raise_for_status()
            events_data = resp.json()

        events = events_data.get("items", [])
        job_count = len(events)

        # Extract times and client names
        job_times: list[str] = []
        client_names: list[str] = []
        for event in events:
            start = event.get("start", {}).get("dateTime", event.get("start", {}).get("date", ""))
            job_times.append(start)

            summary = event.get("summary", "")
            anonymised = self._anonymise_name(summary)
            client_names.append(anonymised)

        first_job = job_times[0] if job_times else None
        last_job = job_times[-1] if job_times else None

        # Detect gaps (> 2 hours between events)
        gaps = self._find_gaps(events)

        data = {
            "job_count": job_count,
            "first_job": first_job,
            "last_job": last_job,
            "client_names": client_names,
            "gaps": gaps,
            "date": day_start.strftime("%Y-%m-%d"),
        }

        # Build summary
        if job_count == 0:
            summary = "No jobs scheduled today"
        else:
            summary_parts = [f"{job_count} job(s) today"]
            if first_job:
                summary_parts.append(f"first at {self._format_time(first_job)}")
            if last_job and last_job != first_job:
                summary_parts.append(f"last at {self._format_time(last_job)}")
            if gaps:
                summary_parts.append(f"{len(gaps)} gap(s) > 2h")
            summary = ", ".join(summary_parts)

        return ResearcherOutput(
            source="calendar",
            data=data,
            summary=summary,
        )

    @staticmethod
    async def _get_access_token(credentials: dict) -> str:
        """Exchange service account credentials for an access token."""
        if not credentials:
            raise ValueError("No Google Calendar credentials configured")

        # For service accounts, use the token endpoint
        token_uri = credentials.get("token_uri", "https://oauth2.googleapis.com/token")
        client_email = credentials.get("client_email", "")
        private_key = credentials.get("private_key", "")

        if not client_email or not private_key:
            # Fall back to access_token if directly provided
            if "access_token" in credentials:
                return credentials["access_token"]
            raise ValueError("Credentials missing client_email/private_key or access_token")

        # Build JWT for service account auth
        import time

        import jwt

        now = int(time.time())
        payload = {
            "iss": client_email,
            "scope": "https://www.googleapis.com/auth/calendar.readonly",
            "aud": token_uri,
            "iat": now,
            "exp": now + 3600,
        }
        assertion = jwt.encode(payload, private_key, algorithm="RS256")

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                token_uri,
                data={
                    "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                    "assertion": assertion,
                },
            )
            resp.raise_for_status()
            return resp.json()["access_token"]

    @staticmethod
    def _anonymise_name(summary: str) -> str:
        """Anonymise client name: 'John Smith - Boiler Repair' → 'John S.'"""
        if not summary:
            return "Unknown"
        parts = summary.split("-")[0].strip().split()
        if len(parts) >= 2:
            return f"{parts[0]} {parts[1][0]}."
        if parts:
            return parts[0]
        return "Unknown"

    @staticmethod
    def _format_time(iso_time: str) -> str:
        """Format ISO time to HH:MM."""
        try:
            dt = datetime.fromisoformat(iso_time)
            return dt.strftime("%H:%M")
        except (ValueError, TypeError):
            return iso_time

    @staticmethod
    def _find_gaps(events: list[dict]) -> list[dict]:
        """Find gaps > 2 hours between consecutive events."""
        gaps: list[dict] = []
        for i in range(len(events) - 1):
            end_current = events[i].get("end", {}).get("dateTime")
            start_next = events[i + 1].get("start", {}).get("dateTime")
            if not end_current or not start_next:
                continue
            try:
                end_dt = datetime.fromisoformat(end_current)
                start_dt = datetime.fromisoformat(start_next)
                gap_minutes = (start_dt - end_dt).total_seconds() / 60
                if gap_minutes > 120:
                    gaps.append({
                        "after": events[i].get("summary", ""),
                        "before": events[i + 1].get("summary", ""),
                        "gap_minutes": int(gap_minutes),
                    })
            except (ValueError, TypeError):
                continue
        return gaps
