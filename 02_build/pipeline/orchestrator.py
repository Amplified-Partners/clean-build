"""
Unified Pipeline Orchestrator (AMP-158)
=======================================

Runs the full pipeline: Scan → Classify → Orchestrate → Write

Incremental, resumable, observable. Each item is checkpointed per stage.
Failed items go to the DLQ for structured retry.

Usage:
    from pipeline.orchestrator import PipelineOrchestrator
    orch = PipelineOrchestrator(corpus_dir="/opt/amplified/vault/store_b_clean")
    stats = orch.run()

Signed-by: Devon-220b | 2026-05-07 | session devin-220b8b8d17044c9f85ac8ec5eb4154b5
"""

from __future__ import annotations

import os
import time
import uuid
from pathlib import Path

from .checkpoint import CheckpointStore
from .dlq import DeadLetterQueue
from .logging_config import get_logger, setup_logging
from .models import ItemStatus, PipelineStats
from .stages.classify import run_classification
from .stages.memory_writer import MemoryStoreWriter
from .stages.orchestrate import orchestrate_items

logger = get_logger("orchestrator")


class PipelineOrchestrator:
    """Unified pipeline: Classify → Orchestrate → Write."""

    def __init__(
        self,
        corpus_dir: str | Path,
        db_dir: str | Path | None = None,
        log_dir: str | Path | None = None,
        max_workers: int = 12,
        batch_size: int = 50,
        dry_run: bool = False,
        classify_only: bool = False,
        skip_write: bool = False,
    ):
        self._corpus_dir = str(corpus_dir)
        self._max_workers = max_workers
        self._batch_size = batch_size
        self._dry_run = dry_run
        self._classify_only = classify_only
        self._skip_write = skip_write
        self._run_id = f"run_{uuid.uuid4().hex[:8]}_{int(time.time())}"

        # Defaults
        db_dir = db_dir or os.path.join(self._corpus_dir, ".pipeline")
        log_dir = log_dir or os.path.join(str(db_dir), "logs")
        Path(str(db_dir)).mkdir(parents=True, exist_ok=True)

        # Init components
        db_path = os.path.join(str(db_dir), "pipeline.db")
        self._checkpoint = CheckpointStore(db_path)
        self._dlq = DeadLetterQueue(db_path)
        setup_logging(log_dir=log_dir, run_id=self._run_id)

    @property
    def checkpoint(self) -> CheckpointStore:
        return self._checkpoint

    @property
    def dlq(self) -> DeadLetterQueue:
        return self._dlq

    @property
    def run_id(self) -> str:
        return self._run_id

    def run(self) -> PipelineStats:
        """Execute the full pipeline. Resumable — picks up from last checkpoint."""
        logger.info(
            "Pipeline starting: run_id=%s corpus=%s workers=%d dry_run=%s",
            self._run_id, self._corpus_dir, self._max_workers, self._dry_run,
        )
        self._checkpoint.record_run_start(self._run_id, {
            "corpus_dir": self._corpus_dir,
            "max_workers": self._max_workers,
            "dry_run": self._dry_run,
        })

        start = time.time()

        # Stage 1: Classify
        logger.info("=== Stage 1: CLASSIFY ===")
        stats = run_classification(
            corpus_dir=self._corpus_dir,
            checkpoint=self._checkpoint,
            dlq=self._dlq,
            max_workers=self._max_workers,
            dry_run=self._dry_run,
        )

        if self._classify_only:
            stats.elapsed_seconds = time.time() - start
            self._checkpoint.record_run_end(self._run_id)
            self._write_manifest()
            logger.info("Classify-only mode. Done in %.1fs.", stats.elapsed_seconds)
            return stats

        # Stage 2: Orchestrate
        logger.info("=== Stage 2: ORCHESTRATE ===")
        classified_items = self._checkpoint.get_items_by_stage(ItemStatus.CLASSIFIED)
        logger.info("Orchestrating %d classified items", len(classified_items))
        orchestrated = orchestrate_items(classified_items, self._checkpoint, self._dlq)
        logger.info("Orchestrated %d items", len(orchestrated))

        if self._skip_write:
            stats.elapsed_seconds = time.time() - start
            self._checkpoint.record_run_end(self._run_id)
            self._write_manifest()
            logger.info("Skip-write mode. Done in %.1fs.", stats.elapsed_seconds)
            return stats

        # Stage 3: Write
        logger.info("=== Stage 3: WRITE ===")
        items_to_write = self._checkpoint.get_items_by_stage(ItemStatus.ORCHESTRATED)
        if items_to_write:
            writer = MemoryStoreWriter(batch_size=self._batch_size)
            try:
                result = writer.write_items(items_to_write, self._checkpoint, self._dlq)
                stats.written = result.falkordb_created + result.qdrant_created
                logger.info(
                    "Write complete: FalkorDB %d/%d, Qdrant %d/%d, errors=%d",
                    result.falkordb_created, result.falkordb_skipped,
                    result.qdrant_created, result.qdrant_skipped,
                    len(result.errors),
                )
            finally:
                writer.close()
        else:
            logger.info("No items to write.")

        stats.elapsed_seconds = time.time() - start
        self._checkpoint.record_run_end(self._run_id)
        self._write_manifest()

        # Summary
        counts = self._checkpoint.count_by_stage()
        logger.info("Pipeline complete in %.1fs. Stage counts: %s", stats.elapsed_seconds, counts)
        dlq_count = self._dlq.count()
        if dlq_count:
            logger.warning("DLQ has %d entries. Run `pipeline retry-dlq` to retry.", dlq_count)

        return stats

    def resume(self) -> PipelineStats:
        """Resume from last checkpoint — alias for run() since it's inherently resumable."""
        logger.info("Resuming pipeline from checkpoint...")
        return self.run()

    def retry_dlq(self, max_retries: int = 3) -> int:
        """Retry items from the DLQ. Returns count of successfully retried items."""
        entries = self._dlq.get_retryable(max_retries)
        logger.info("Retrying %d DLQ entries (max_retries=%d)", len(entries), max_retries)
        success = 0

        for entry in entries:
            # Re-register as pending
            self._checkpoint.update_item(entry.file_path, ItemStatus.PENDING)
            self._dlq.remove(entry.file_path)
            success += 1

        if success:
            logger.info("Re-queued %d items. Run the pipeline again to process them.", success)
        return success

    def status(self) -> dict:
        """Return current pipeline status."""
        counts = self._checkpoint.count_by_stage()
        return {
            "total": self._checkpoint.total_count(),
            "stages": counts,
            "dlq": self._dlq.count(),
        }

    def _write_manifest(self) -> None:
        """Write the high-value manifest for downstream consumers."""
        classified = self._checkpoint.get_items_by_stage(ItemStatus.CLASSIFIED)
        orchestrated = self._checkpoint.get_items_by_stage(ItemStatus.ORCHESTRATED)
        written = self._checkpoint.get_items_by_stage(ItemStatus.WRITTEN)

        all_high_value = classified + orchestrated + written
        high = [i for i in all_high_value if i.classification and i.classification.value == "high"]
        medium = [i for i in all_high_value if i.classification and i.classification.value == "medium"]

        manifest = {
            "run_id": self._run_id,
            "total_classified": len(all_high_value),
            "high_value": len(high),
            "medium_value": len(medium),
            "high_value_files": [
                {
                    "path": i.file_path,
                    "hash": i.file_hash,
                    "type": i.taxonomy.type if i.taxonomy else "unknown",
                    "dimensions": i.taxonomy.dimensions if i.taxonomy else [],
                    "confidence": i.taxonomy.confidence if i.taxonomy else 0.0,
                }
                for i in high
            ],
            "medium_value_files": [
                {
                    "path": i.file_path,
                    "hash": i.file_hash,
                    "type": i.taxonomy.type if i.taxonomy else "unknown",
                    "dimensions": i.taxonomy.dimensions if i.taxonomy else [],
                    "confidence": i.taxonomy.confidence if i.taxonomy else 0.0,
                }
                for i in medium
            ],
        }

        manifest_path = Path(self._corpus_dir) / "high_value_for_graphiti.json"
        import json
        manifest_path.write_text(json.dumps(manifest, indent=2))
        logger.info("Manifest written: %s (%d high, %d medium)", manifest_path, len(high), len(medium))
