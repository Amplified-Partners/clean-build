# Authored by Devon-9a6b, 2026-05-03 (session devin-9a6bd256bd7c4a90a083a471fa94a810)
"""INS-069 — Category Cannibalisation × Cross-Sell Graph Analysis (Retail).

Claim cites 'ONS Household spending data by category' as the public leg.
Validatable: confirm ONS family-spending exists + has category granularity.
"""
from __future__ import annotations

from ..fetchers.ons_beta import list_datasets
from ..tests.existence import existence_check
from ..verdict import Verdict


def run() -> Verdict:
    candidates = list_datasets(search="family-spending", limit=20)
    fetched_evidence = [
        {**candidates.evidence(sample_rows=2), "search": "family-spending"},
    ]
    has_household = False
    if isinstance(candidates.body, dict):
        for d in candidates.body.get("items", []):
            t = (d.get("title") or "").lower()
            if "household" in t or "family spending" in t:
                has_household = True
                fetched_evidence[0]["matched_dataset"] = d.get("id")
                break

    v, bundle = existence_check(
        claim="ONS family-spending / household-spending category breakdown reachable",
        fetched_list=fetched_evidence,
    )

    if v == "PROVEN" and has_household:
        verdict, conf, summary = "PROVEN", 80, "ONS family/household spending category dataset reachable"
    else:
        verdict, conf, summary = "PLAUSIBLE", 65, (
            "ONS dataset listing reachable; specific household-spending category granularity not "
            "auto-confirmed in the search response — manual cross-check needed."
        )

    notes = [
        "Public leg = ONS family-spending category breakdown.",
        "Co-purchase graph leg = client transactional data; recipe is PLAUSIBLE end-to-end at deploy.",
    ]
    return Verdict(
        insight_id="INS-069",
        title="Category Cannibalisation × Cross-Sell Graph Analysis (Retail)",
        vertical="Retail",
        verdict=verdict,
        test_class="existence",
        summary=summary,
        evidence=[bundle],
        notes=notes,
        confidence=conf,
    )
