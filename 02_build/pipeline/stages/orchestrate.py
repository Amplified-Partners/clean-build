"""
Orchestrator Integration Stage (AMP-157)
========================================

Bridges the PUDDING classifier output to the 5-stage research orchestrator,
then formats output for the Memory Writer.

Pipeline position: Classify → **Orchestrate** → Write

The research pipe stages (intake → interpreter → curator1 → search → curator2)
live in 02_build/scripts/ and are ported from corpus-raw/ewan-mac/archive/.

This stage is opt-in (ORCHESTRATOR_ENABLED=1) because the interpreter and
curator2 stages require Claude, and Anthropic billing is exhausted (AMP-142).
When disabled, classified items pass straight through to the writer.

Signed-by: Devon-220b | 2026-05-07 | session devin-220b8b8d17044c9f85ac8ec5eb4154b5
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional

from ..checkpoint import CheckpointStore
from ..dlq import DeadLetterQueue
from ..logging_config import get_logger
from ..models import ItemStatus, PipelineItem

logger = get_logger("orchestrate")

ORCHESTRATOR_ENABLED = os.getenv("ORCHESTRATOR_ENABLED", "0") == "1"

# Add scripts dir to path for research pipe imports
_SCRIPTS_DIR = str(Path(__file__).resolve().parent.parent.parent / "scripts")
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)


def _run_research_pipe(question: str, domain: str = "general") -> Optional[dict]:
    """Run the 5-stage research pipe on a question derived from the document.

    Returns curator2 output dict on success, None on failure.
    """
    try:
        from intake_research_pipe import stage_intake
        from interpreter_research_pipe import stage_interpreter
        from curator1_research_pipe import stage_curator1
        from search_research_pipe import stage_search
        from curator2_research_pipe import stage_curator2

        intake = stage_intake(question, domain=domain)
        interpreter = stage_interpreter(intake)
        curator1 = stage_curator1(interpreter)
        search = stage_search(curator1)
        curator2 = stage_curator2(search, curator1)
        return curator2
    except ImportError as exc:
        logger.warning("Research pipe import failed (missing dep): %s", exc)
        return None
    except Exception as exc:
        logger.warning("Research pipe error: %s", exc)
        return None


def _extract_question_from_item(item: PipelineItem) -> str:
    """Derive a research question from a classified item's taxonomy."""
    taxonomy = item.taxonomy
    if not taxonomy:
        return ""
    dims = ", ".join(taxonomy.dimensions) if taxonomy.dimensions else "general"
    return (
        f"What are the best methodologies for {taxonomy.type} "
        f"in the domains of {dims}?"
    )


def orchestrate_items(
    items: list[PipelineItem],
    checkpoint: CheckpointStore,
    dlq: DeadLetterQueue,
) -> list[PipelineItem]:
    """Run the orchestrator on classified items.

    If ORCHESTRATOR_ENABLED is false, items pass through unchanged
    (stage updated to ORCHESTRATED).

    Returns items ready for the writer stage.
    """
    output: list[PipelineItem] = []

    for item in items:
        checkpoint.update_item(item.file_path, ItemStatus.ORCHESTRATING)

        if not ORCHESTRATOR_ENABLED:
            item.stage = ItemStatus.ORCHESTRATED
            checkpoint.update_item(item.file_path, ItemStatus.ORCHESTRATED)
            output.append(item)
            continue

        try:
            question = _extract_question_from_item(item)
            if not question:
                item.stage = ItemStatus.ORCHESTRATED
                checkpoint.update_item(item.file_path, ItemStatus.ORCHESTRATED)
                output.append(item)
                continue

            result = _run_research_pipe(question)
            if result:
                logger.info(
                    "Orchestrated %s — verdict: %s",
                    Path(item.file_path).name,
                    result.get("sufficiency_check", {}).get("verdict", "UNKNOWN"),
                )

            item.stage = ItemStatus.ORCHESTRATED
            checkpoint.update_item(item.file_path, ItemStatus.ORCHESTRATED)
            output.append(item)

        except Exception as exc:
            error_msg = f"{type(exc).__name__}: {exc}"[:500]
            checkpoint.update_item(item.file_path, ItemStatus.FAILED, error=error_msg)
            dlq.add(item.file_path, "orchestrate", error_msg)
            logger.warning("Orchestrate failed for %s: %s", item.file_path, error_msg[:120])

    return output
