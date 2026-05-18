"""Vellum Ingestion Gate — the hard gate.

Everything that wants to enter Vellum goes through here.
Correct or reject. Nothing in between.

Proforma validation → epistemic check → sign → store or reject.
Inputs are untrusted by definition. It doesn't matter who sent it.
It matters: does this pass the gate?

Devon-b5dc | 2026-05-14
"""

from vellum.ingestion.models import (
    GateVerdict,
    Proforma,
    ProformaField,
    SignedRecord,
    Submission,
    WriterType,
)
from vellum.ingestion.registry import ProformaRegistry
from vellum.ingestion.gate import IngestionGate

__all__ = [
    "GateVerdict",
    "IngestionGate",
    "Proforma",
    "ProformaField",
    "ProformaRegistry",
    "SignedRecord",
    "Submission",
    "WriterType",
]
