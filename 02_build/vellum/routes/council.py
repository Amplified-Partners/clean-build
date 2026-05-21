"""Council route — submit questions to the Council of Three.

POST /api/v1/sheets/{sheet_id}/council
  - Creates a council_question entry on the sheet
  - Dispatches to 3 heterogeneous frontier models in parallel
  - Stores each response as a council_answer entry
  - Returns aggregated verdict + minority report

§3.4 verdict mapping (2026-05-20):
  UNANIMOUS → council_answer, epistemic_tier=STRUCTURED
  MAJORITY  → council_answer, epistemic_tier=STRUCTURED, dissent_recorded=True
  SPLIT     → decision entry "escalated_to_human", epistemic_tier=INTUITED
  
The SPLIT case is critical: do NOT write a synthesised verdict when
the Council could not agree. Doing so would launder a non-decision
into a recorded decision.

Devon-b5dc | 2026-05-14
Hardened by Dana | 2026-05-20 | §3.4 council verdict mapping
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from vellum.council.context import CouncilContext
from vellum.council.engine import CouncilResult, Verdict, run_council
from vellum.models.entry import SheetEntry
from vellum.storage import get_store

log = logging.getLogger("vellum.council")
router = APIRouter(prefix="/api/v1", tags=["council"])


class CouncilRequest(BaseModel):
    """Request body for a council question."""

    question: str = Field(..., min_length=10, description="The question for the council")
    author: str = Field(default="ewan", description="Who is asking")
    options: list[str] = Field(default_factory=list, description="Options under consideration")
    constraints: list[str] = Field(default_factory=list, description="Binding constraints")
    success_criteria: str = Field(default="", description="What 'worked' means")
    failure_modes: list[str] = Field(default_factory=list, description="Top failure modes to avoid")
    prior_decisions: list[str] = Field(default_factory=list, description="Prior analogous decisions")
    additional_context: str = Field(default="", description="Any extra context")


class CouncilResponse(BaseModel):
    """Response from a council deliberation."""

    question_entry_id: str
    verdict: str
    agreement_score: float
    escalate: bool
    escalation_reason: str
    answer_entry_ids: list[str]
    round_2_needed: bool
    round_2_entry_ids: list[str]


@router.post("/sheets/{sheet_id}/council", response_model=CouncilResponse)
async def submit_council_question(sheet_id: str, body: CouncilRequest) -> CouncilResponse:
    """Submit a question to the Council of Three.

    The question is stored as a council_question entry, then dispatched
    to three heterogeneous frontier models in parallel. Each response is
    stored as a council_answer entry on the same hash chain.
    """
    store = get_store()
    sheet = await store.get_sheet(sheet_id)
    if sheet is None:
        raise HTTPException(status_code=404, detail=f"Sheet {sheet_id} not found")

    # --- Entry 1: the question itself ---
    question_entry = SheetEntry(
        sheet_id=sheet_id,
        author=body.author,
        content=body.question,
        prev_hash=sheet.latest_hash,
        entry_type="council_question",
        metadata={
            "layer": "council",
            "options": body.options,
            "constraints": body.constraints,
            "success_criteria": body.success_criteria,
            "failure_modes": body.failure_modes,
        },
    )
    await store.append_entry(sheet_id, question_entry)
    log.info("Council question stored: %s", question_entry.id)

    # --- Run the council ---
    ctx = CouncilContext(
        decision_statement=body.question,
        options=body.options,
        constraints=body.constraints,
        success_criteria=body.success_criteria,
        failure_modes=body.failure_modes,
        prior_decisions=body.prior_decisions,
        additional_context=body.additional_context,
    )

    result: CouncilResult = await run_council(body.question, ctx)

    # --- Store each council answer as an entry ---
    answer_entry_ids: list[str] = []
    for resp in result.responses:
        if resp.error:
            continue
        sheet = await store.get_sheet(sheet_id)
        answer_entry = SheetEntry(
            sheet_id=sheet_id,
            author=f"council-{resp.label.lower()}",
            content=resp.recommendation,
            prev_hash=sheet.latest_hash if sheet else "",
            entry_type="council_answer",
            metadata={
                "layer": "council",
                "model_label": resp.label,
                "source_question_id": question_entry.id,
                "latency_ms": resp.latency_ms,
                "round": 1,
            },
        )
        await store.append_entry(sheet_id, answer_entry)
        answer_entry_ids.append(answer_entry.id)

    # --- Store Round 2 answers if debate happened ---
    round_2_entry_ids: list[str] = []
    if result.round_2_responses:
        for resp in result.round_2_responses:
            if resp.error:
                continue
            sheet = await store.get_sheet(sheet_id)
            debate_entry = SheetEntry(
                sheet_id=sheet_id,
                author=f"council-{resp.label.lower()}-r2",
                content=resp.recommendation,
                prev_hash=sheet.latest_hash if sheet else "",
                entry_type="council_answer",
                metadata={
                    "layer": "council",
                    "model_label": resp.label,
                    "source_question_id": question_entry.id,
                    "latency_ms": resp.latency_ms,
                    "round": 2,
                },
            )
            await store.append_entry(sheet_id, debate_entry)
            round_2_entry_ids.append(debate_entry.id)

    # --- §3.4: Store verdict entry with epistemic tier mapping ---
    sheet = await store.get_sheet(sheet_id)
    verdict_entry = _build_verdict_entry(
        sheet_id=sheet_id,
        prev_hash=sheet.latest_hash if sheet else "",
        result=result,
        question_entry_id=question_entry.id,
    )
    await store.append_entry(sheet_id, verdict_entry)

    return CouncilResponse(
        question_entry_id=question_entry.id,
        verdict=result.verdict.value,
        agreement_score=result.agreement_score,
        escalate=result.escalate,
        escalation_reason=result.escalation_reason,
        answer_entry_ids=answer_entry_ids,
        round_2_needed=result.round_2_needed,
        round_2_entry_ids=round_2_entry_ids,
    )


def _build_verdict_entry(
    *,
    sheet_id: str,
    prev_hash: str,
    result: CouncilResult,
    question_entry_id: str,
) -> SheetEntry:
    """Build the verdict entry with §3.4 epistemic tier mapping.

    UNANIMOUS → council_answer, STRUCTURED
    MAJORITY  → council_answer, STRUCTURED, dissent_recorded=True
    SPLIT     → decision "escalated_to_human", INTUITED (no synthesised verdict)
    """
    if result.verdict == Verdict.SPLIT:
        # SPLIT: do NOT synthesise a verdict. Write an escalation marker.
        # This prevents laundering a non-decision into a recorded decision.
        return SheetEntry(
            sheet_id=sheet_id,
            author="council-aggregator",
            content="Council split — escalated to human. No synthesised verdict recorded.",
            prev_hash=prev_hash,
            entry_type="decision",
            epistemic_tier="INTUITED",
            metadata={
                "layer": "council_verdict",
                "verdict": "split",
                "escalate": True,
                "escalation_reason": result.escalation_reason,
                "source_question_id": question_entry_id,
                "requires_human_followup": True,
            },
        )

    # UNANIMOUS or MAJORITY — write as STRUCTURED council_answer
    verdict_content = _format_verdict(result)
    verdict_metadata: dict = {
        "layer": "council_verdict",
        "verdict": result.verdict.value,
        "agreement_score": result.agreement_score,
        "escalate": result.escalate,
        "escalation_reason": result.escalation_reason,
        "source_question_id": question_entry_id,
    }

    if result.verdict == Verdict.MAJORITY:
        verdict_metadata["dissent_recorded"] = True

    return SheetEntry(
        sheet_id=sheet_id,
        author="council-aggregator",
        content=verdict_content,
        prev_hash=prev_hash,
        entry_type="council_answer",
        epistemic_tier="STRUCTURED",
        metadata=verdict_metadata,
    )


def _format_verdict(result: CouncilResult) -> str:
    """Format the council verdict as human-readable text."""
    parts: list[str] = []

    parts.append(f"## Council Verdict: {result.verdict.value.upper()}")
    parts.append(f"Agreement score: {result.agreement_score:.0%}")

    if result.escalate:
        parts.append(f"\n⚠️ ESCALATION: {result.escalation_reason}")

    if result.majority_position:
        parts.append(f"\n### Majority Position\n{result.majority_position[:500]}")

    if result.minority_report:
        parts.append(f"\n### Minority Report\n{result.minority_report[:500]}")

    valid = [r for r in result.responses if not r.error]
    parts.append(f"\n### Vote Tally\n{len(valid)} of {len(result.responses)} members responded")

    if result.round_2_needed:
        parts.append("\n### Debate\nRound 2 adversarial exchange was triggered")
        if result.round_2_responses:
            valid_r2 = [r for r in result.round_2_responses if not r.error]
            parts.append(f"{len(valid_r2)} members participated in debate")

    return "\n".join(parts)
