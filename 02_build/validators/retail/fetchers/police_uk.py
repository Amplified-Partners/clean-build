# Authored by Devon-9a6b, 2026-05-03 (session devin-9a6bd256bd7c4a90a083a471fa94a810)
"""Police.uk Crime Data API.

Free, no key required. Used for INS-067 (shoplifting) and INS-072 (postcode crime).
Docs: https://data.police.uk/docs/
"""
from __future__ import annotations

from .common import fetch_json, Fetched

BASE = "https://data.police.uk/api"


def crimes_at_location(
    category: str,
    lat: float,
    lng: float,
    date: str | None = None,
) -> Fetched:
    """Crimes within a 1-mile radius of (lat,lng) for the given YYYY-MM date.

    category: 'shoplifting' | 'all-crime' | 'burglary' | etc.
    date: YYYY-MM (defaults to latest available).
    Returns up to ~10,000 crimes per call; 1-mile radius is API default.
    """
    url = f"{BASE}/crimes-street/{category}"
    params: dict = {"lat": lat, "lng": lng}
    if date:
        params["date"] = date
    return fetch_json("police_uk", url, params=params)


def availability() -> Fetched:
    """List of (date, force) pairs available — used to pick a recent month."""
    return fetch_json("police_uk", f"{BASE}/crimes-street-dates")


# Curated retail-postcode anchor points (centroid lat/lng).
# Keep this short and named so verdicts are reproducible by humans.
RETAIL_AREAS = {
    # Newcastle — Jesmond Plumbing canonical postcodes (NE1-NE3) + Eldon Square retail core
    "NE1_eldon_square": (54.9744, -1.6131),
    "NE2_jesmond_acorn_rd": (54.9929, -1.6092),
    "NE3_gosforth_high_st": (55.0083, -1.6233),
    # Major retail high streets across UK regions (cross-vertical signal)
    "M3_manchester_arndale": (53.4838, -2.2381),
    "B5_birmingham_bullring": (52.4775, -1.8941),
    "L1_liverpool_one": (53.4030, -2.9870),
    "G1_glasgow_buchanan_st": (55.8617, -4.2530),
    "BS1_bristol_cabot_circus": (51.4576, -2.5867),
    "LS1_leeds_briggate": (53.7975, -1.5430),
    "EH1_edinburgh_princes_st": (55.9525, -3.1880),
    "W1_oxford_st_london": (51.5147, -0.1426),
    "SE1_borough_market_london": (51.5055, -0.0905),
}
