"""Existence test — does the data exist at the granularity required?

Cheapest test class. Runs first. Confirms the source URL is reachable and
that any required substring (e.g. a SIC code, a sector name, a deadline date)
appears somewhere in the response.

Signed-by: Devon-ab74 (devin-ab740f2c78ee477a9c16ea3b6ed15293) - 2026-05-03
"""

from __future__ import annotations

from dataclasses import dataclass

from ..core import EvidenceBundle, EvidenceItem, TestClass, Verdict, VerdictBand


@dataclass(frozen=True)
class ExistenceCheck:
    """A single existence check.

    `must_contain` may be empty — the bare presence of a 200 OK is enough to
    confirm the data product exists. When non-empty, all substrings must be
    present in the response body.
    """

    description: str
    must_contain: tuple[str, ...] = ()


def existence_test(
    *,
    insight_id: str,
    vertical: str,
    method: str,
    body: bytes,
    evidence_item: EvidenceItem,
    checks: list[ExistenceCheck],
    extra_evidence: list[EvidenceItem] | None = None,
) -> Verdict:
    """Run a list of existence checks against a fetched body.

    PROVEN if every required substring is present.
    DISPROVEN if any required substring is missing (the data product moved or
    the claim was wrong about what it contained).
    """
    text = body.decode("utf-8", errors="replace") if isinstance(body, bytes) else body
    missing: list[str] = []
    for check in checks:
        for needle in check.must_contain:
            if needle not in text:
                missing.append(f"{check.description}: '{needle}'")

    bundle = EvidenceBundle(items=[evidence_item, *(extra_evidence or [])])

    if not missing:
        finding = (
            f"All {sum(len(c.must_contain) for c in checks)} required tokens "
            "present in the public source response."
        )
        if not any(c.must_contain for c in checks):
            finding = "Source URL is reachable; no substring requirements set."
        return Verdict(
            insight_id=insight_id,
            vertical=vertical,
            band=VerdictBand.PROVEN,
            test_class=TestClass.EXISTENCE,
            method=method,
            finding=finding,
            statistic={"checks_passed": len(checks), "checks_failed": 0},
            evidence=bundle,
        )

    return Verdict(
        insight_id=insight_id,
        vertical=vertical,
        band=VerdictBand.DISPROVEN,
        test_class=TestClass.EXISTENCE,
        method=method,
        finding=f"{len(missing)} required tokens missing: {missing[:5]}",
        statistic={
            "checks_passed": len(checks) - len(missing),
            "checks_failed": len(missing),
            "missing": missing,
        },
        evidence=bundle,
    )
