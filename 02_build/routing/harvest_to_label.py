#!/usr/bin/env python3
"""
Harvest-to-Label adapter — bridges APDS Harvest output to the PUDDING Labeler.

Pipeline position:  Harvest --> [this adapter] --> Label

The Harvest stage produces ``RawItem`` objects (NightScout fetchers) or raw
content files (Porch Watcher incoming/). This adapter normalises both into a
common ``HarvestRecord`` and runs the deterministic PUDDING labeler, producing
a ``LabeledRecord`` ready for the Extract/Match stages.

Designed for two execution modes:
    1. **Streaming** — called per-item inside the NightScout pipeline.
    2. **Batch** — scans a directory of harvested files (Porch convention).

Usage:
    # Single item (NightScout integration)
    from harvest_to_label import label_harvested_item
    labeled = label_harvested_item(raw_item)

    # Batch (Porch directory scan)
    from harvest_to_label import label_harvest_batch
    results = label_harvest_batch("/opt/amplified-machine/porch/incoming")

Signed-by: Devon (Devin session f32d587cc3e54f959c5309d93f72bc97) - 2026-05-01
"""

from __future__ import annotations

import hashlib
import json
import logging
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Allow imports from sibling directories
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from pudding_labeler import label_document

logger = logging.getLogger("apds.harvest_to_label")


# ---------------------------------------------------------------------------
# Data contracts
# ---------------------------------------------------------------------------

@dataclass
class HarvestRecord:
    """Normalised harvest output — the common shape between NightScout
    RawItems and Porch Watcher file drops."""

    source_name: str
    external_id: str
    title: str
    content: str
    url: str | None = None
    published_at: datetime | None = None
    source_tier: str = "T1"
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def content_hash(self) -> str:
        return hashlib.sha256(self.content.encode()).hexdigest()[:16]


@dataclass
class LabeledRecord:
    """A harvest record enriched with PUDDING taxonomy labels."""

    harvest: HarvestRecord
    pudding_label: str
    pudding_base: str
    what: str
    how: str
    scale: str
    time: str
    patterns: list[str]
    word_count: int
    labeled_at: str
    label_source: str = "deterministic"

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        if self.harvest.published_at:
            d["harvest"]["published_at"] = self.harvest.published_at.isoformat()
        return d


# ---------------------------------------------------------------------------
# NightScout RawItem adapter
# ---------------------------------------------------------------------------

def from_raw_item(raw_item: Any) -> HarvestRecord:
    """Convert a NightScout ``RawItem`` (or any object with matching attrs)
    into a ``HarvestRecord``.

    Accepts dataclass instances and plain dicts.
    """
    if isinstance(raw_item, dict):
        return HarvestRecord(
            source_name=raw_item.get("source_name", "unknown"),
            external_id=raw_item.get("external_id", ""),
            title=raw_item.get("title", ""),
            content=raw_item.get("content", ""),
            url=raw_item.get("url"),
            published_at=raw_item.get("published_at"),
            metadata=raw_item.get("metadata", {}),
        )
    return HarvestRecord(
        source_name=getattr(raw_item, "source_name", "unknown"),
        external_id=getattr(raw_item, "external_id", ""),
        title=getattr(raw_item, "title", ""),
        content=getattr(raw_item, "content", ""),
        url=getattr(raw_item, "url", None),
        published_at=getattr(raw_item, "published_at", None),
        metadata=getattr(raw_item, "metadata", {}),
    )


# ---------------------------------------------------------------------------
# Core labeling logic
# ---------------------------------------------------------------------------

def _label_text(title: str, content: str, tmp_dir: Path | None = None) -> dict:
    """Write content to a temp file and run the PUDDING labeler.

    The existing ``label_document()`` expects a file path, so we materialise
    the text. Uses ``/tmp/apds_harvest/`` by default.
    """
    work_dir = tmp_dir or Path("/tmp/apds_harvest")
    work_dir.mkdir(parents=True, exist_ok=True)

    slug = hashlib.sha256(f"{title}{content[:200]}".encode()).hexdigest()[:12]
    tmp_file = work_dir / f"{slug}.md"
    tmp_file.write_text(f"# {title}\n\n{content}", encoding="utf-8")

    try:
        result = label_document(str(tmp_file))
    finally:
        tmp_file.unlink(missing_ok=True)

    return result


def label_harvested_item(
    raw_item: Any,
    *,
    source_tier: str = "T1",
) -> LabeledRecord:
    """Label a single harvested item with the PUDDING taxonomy.

    ``raw_item`` can be a NightScout ``RawItem``, a dict, or a
    ``HarvestRecord``.

    Returns a ``LabeledRecord`` ready for downstream stages.
    """
    if isinstance(raw_item, HarvestRecord):
        harvest = raw_item
    else:
        harvest = from_raw_item(raw_item)

    harvest.source_tier = source_tier

    label_result = _label_text(harvest.title, harvest.content)

    if "error" in label_result:
        logger.warning("Labeling failed for %s: %s", harvest.external_id, label_result["error"])
        return LabeledRecord(
            harvest=harvest,
            pudding_label="UNLABELED",
            pudding_base="UNLABELED",
            what="?", how="?", scale="?", time="?",
            patterns=[],
            word_count=len(harvest.content.split()),
            labeled_at=datetime.now(timezone.utc).isoformat(),
        )

    return LabeledRecord(
        harvest=harvest,
        pudding_label=label_result.get("pudding_label", ""),
        pudding_base=label_result.get("pudding_base", ""),
        what=label_result.get("what", ""),
        how=label_result.get("how", ""),
        scale=label_result.get("scale", ""),
        time=label_result.get("time", ""),
        patterns=label_result.get("patterns", []),
        word_count=label_result.get("word_count", 0),
        labeled_at=datetime.now(timezone.utc).isoformat(),
    )


# ---------------------------------------------------------------------------
# Batch mode (Porch directory scan)
# ---------------------------------------------------------------------------

SUPPORTED_EXTENSIONS = {".md", ".txt", ".json", ".yaml", ".yml", ".csv"}


def label_harvest_batch(
    directory: str | Path,
    *,
    source_tier: str = "T1",
    output_jsonl: str | Path | None = None,
) -> list[LabeledRecord]:
    """Label all supported files in a directory.

    Optionally writes results to a JSONL file for downstream consumption.
    """
    dirpath = Path(directory)
    if not dirpath.is_dir():
        raise FileNotFoundError(f"Harvest directory not found: {dirpath}")

    files = sorted(
        f for f in dirpath.iterdir()
        if f.is_file() and f.suffix in SUPPORTED_EXTENSIONS
    )

    if not files:
        logger.info("No files to label in %s", dirpath)
        return []

    logger.info("Labeling %d files from %s", len(files), dirpath)
    results: list[LabeledRecord] = []

    for filepath in files:
        content = filepath.read_text(encoding="utf-8", errors="replace")
        record = HarvestRecord(
            source_name=f"porch:{filepath.name}",
            external_id=hashlib.sha256(filepath.name.encode()).hexdigest()[:16],
            title=filepath.stem.replace("-", " ").replace("_", " ").title(),
            content=content,
            source_tier=source_tier,
            metadata={"origin": "porch", "filename": filepath.name},
        )
        labeled = label_harvested_item(record, source_tier=source_tier)
        results.append(labeled)
        logger.debug(
            "  [%s] %s -> %s",
            labeled.pudding_label,
            filepath.name,
            labeled.what,
        )

    if output_jsonl:
        out = Path(output_jsonl)
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "a", encoding="utf-8") as f:
            for r in results:
                f.write(json.dumps(r.to_dict(), default=str) + "\n")
        logger.info("Wrote %d records to %s", len(results), out)

    return results


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(name)s %(levelname)s %(message)s")

    parser = argparse.ArgumentParser(description="APDS Harvest-to-Label adapter")
    parser.add_argument("directory", help="Directory of harvested files to label")
    parser.add_argument("--tier", default="T1", help="Source tier (T1-T4)")
    parser.add_argument("--output", help="JSONL output file")
    args = parser.parse_args()

    results = label_harvest_batch(args.directory, source_tier=args.tier, output_jsonl=args.output)
    print(f"\nLabeled {len(results)} items:")
    for r in results:
        print(f"  [{r.pudding_label}] {r.harvest.title}")
