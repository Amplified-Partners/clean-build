"""
Pipeline data models — shared Pydantic schemas for all stages.

Signed-by: Devon-220b | 2026-05-07 | session devin-220b8b8d17044c9f85ac8ec5eb4154b5
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field


class ItemStatus(str, Enum):
    PENDING = "pending"
    CLASSIFYING = "classifying"
    CLASSIFIED = "classified"
    ORCHESTRATING = "orchestrating"
    ORCHESTRATED = "orchestrated"
    WRITING = "writing"
    WRITTEN = "written"
    FAILED = "failed"
    SKIPPED = "skipped"


class PuddingTaxonomy(BaseModel):
    """PUDDING 2026 taxonomy classification result."""
    type: str = "principle"
    dimensions: list[str] = Field(default_factory=list)
    expert: str = "UNKNOWN"
    actionable: str = "principle_only"
    status: str = "hypothesis"
    confidence: float = 0.0


class Classification(BaseModel):
    """Value classification from the pre-filter."""
    include: bool = False
    value: str = "low"  # high | medium | low
    reason: str = ""


class PipelineItem(BaseModel):
    """A single file moving through the pipeline."""
    file_path: str
    file_hash: str = ""
    stage: ItemStatus = ItemStatus.PENDING
    taxonomy: Optional[PuddingTaxonomy] = None
    classification: Optional[Classification] = None
    error: Optional[str] = None
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    updated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def compute_hash(self) -> str:
        """SHA-256 of file content for dedup."""
        content = Path(self.file_path).read_bytes()
        self.file_hash = hashlib.sha256(content).hexdigest()
        return self.file_hash


class IngestResult(BaseModel):
    """Result from the memory writer stage."""
    file_path: str
    falkordb_created: int = 0
    falkordb_skipped: int = 0
    qdrant_created: int = 0
    qdrant_skipped: int = 0
    errors: list[str] = Field(default_factory=list)

    @property
    def success(self) -> bool:
        return len(self.errors) == 0


class PipelineStats(BaseModel):
    """Aggregate pipeline run statistics."""
    total_files: int = 0
    classified: int = 0
    high_value: int = 0
    medium_value: int = 0
    low_value: int = 0
    skipped: int = 0
    written: int = 0
    failed: int = 0
    elapsed_seconds: float = 0.0

    @property
    def files_per_second(self) -> float:
        if self.elapsed_seconds <= 0:
            return 0.0
        return round(self.classified / self.elapsed_seconds, 2)
