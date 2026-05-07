"""
PUDDING Classification Stage (AMP-155)
======================================

Scalable, resumable classification of vault files using Ollama.
Evolved from Beast's pudding_pre_filter.py + pudding_extractor.py.

Flow:
  1. Scan store_b_clean for unclassified .md/.txt files
  2. Skip boilerplate (license, readme, changelog, etc.)
  3. Skip already-classified files (frontmatter with dimensions:)
  4. Classify via Ollama (llama3.1:8b) with configurable concurrency
  5. Write checkpoint per item for crash-safe resume
  6. Output manifest (high_value_for_graphiti.json)

Signed-by: Devon-220b | 2026-05-07 | session devin-220b8b8d17044c9f85ac8ec5eb4154b5
"""

from __future__ import annotations

import json
import os
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Optional

from ..checkpoint import CheckpointStore
from ..dlq import DeadLetterQueue
from ..logging_config import get_logger
from ..models import (
    Classification,
    ItemStatus,
    PipelineItem,
    PipelineStats,
    PuddingTaxonomy,
)

logger = get_logger("classify")

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://172.18.0.12:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:8b")

BOILERPLATE_KEYWORDS = frozenset([
    "license", "readme", "changelog", "code-of-conduct", "contributing",
    "security.md", "package.json", "tsconfig", "eslint", "prettier",
    "gitignore", "dockerfile", "makefile", ".plist", "node_modules",
])

TAXONOMY_PROMPT = """You are the PUDDING Neutral Extractor.
Extract the core mechanism using the PUDDING 2026 Taxonomy.
Return ONLY this JSON:
{
  "type": "principle|framework|sop|technique|case_study|hypothesis|recipe",
  "dimensions": ["customer_acquisition", "pricing", ...],
  "expert": "UNKNOWN or surname",
  "actionable": "principle_only|needs_adaptation|ready_to_use|automated",
  "status": "hypothesis|canonical|proven|tested_internal|tested_client",
  "confidence": 0.0
}
Document:
"""


def is_boilerplate(filepath: Path) -> bool:
    """Check if a file is likely boilerplate based on filename."""
    name_lower = filepath.name.lower()
    return any(kw in name_lower for kw in BOILERPLATE_KEYWORDS)


def is_already_classified(filepath: Path) -> bool:
    """Check if file already has PUDDING taxonomy in frontmatter."""
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            head = f.read(2000)
        if not head.startswith("---"):
            return False
        parts = head.split("---", 2)
        if len(parts) < 3:
            return False
        frontmatter = parts[1]
        return "dimensions:" in frontmatter or "pudding_score:" in frontmatter
    except OSError:
        return False


def call_ollama(
    content: str,
    ollama_url: str = OLLAMA_URL,
    model: str = OLLAMA_MODEL,
    timeout: int = 120,
) -> PuddingTaxonomy:
    """Call Ollama to classify a document."""
    payload = json.dumps({
        "model": model,
        "prompt": TAXONOMY_PROMPT + content[:4000],
        "stream": False,
        "format": "json",
        "options": {"temperature": 0.1, "num_predict": 200},
    }).encode()
    req = urllib.request.Request(
        f"{ollama_url}/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read())
    result = json.loads(data.get("response", "{}"))
    return PuddingTaxonomy(
        type=result.get("type", "principle"),
        dimensions=result.get("dimensions", []),
        expert=result.get("expert", "UNKNOWN"),
        actionable=result.get("actionable", "principle_only"),
        status=result.get("status", "hypothesis"),
        confidence=float(result.get("confidence", 0.0)),
    )


def classify_value(taxonomy: PuddingTaxonomy) -> Classification:
    """Determine high/medium/low value from taxonomy."""
    t = taxonomy.type
    actionable = taxonomy.actionable
    status = taxonomy.status
    dims = taxonomy.dimensions

    if t == "hypothesis" and status == "hypothesis":
        return Classification(include=False, value="low", reason="Unproven hypothesis")
    if len(dims) < 2:
        return Classification(include=False, value="low", reason="Too few dimensions")
    if actionable in ("ready_to_use", "automated") and status in (
        "proven", "canonical", "tested_client"
    ):
        return Classification(include=True, value="high", reason="Ready to use + proven")
    if actionable == "needs_adaptation" or status in ("tested_internal", "canonical"):
        return Classification(include=True, value="medium", reason="Adaptable or tested")
    return Classification(include=False, value="low", reason="Low value")


def classify_file(
    filepath: Path,
    ollama_url: str = OLLAMA_URL,
    model: str = OLLAMA_MODEL,
) -> tuple[PuddingTaxonomy, Classification]:
    """Classify a single file. Returns (taxonomy, classification)."""
    content = filepath.read_text(encoding="utf-8", errors="ignore")
    taxonomy = call_ollama(content, ollama_url=ollama_url, model=model)
    classification = classify_value(taxonomy)
    return taxonomy, classification


def scan_corpus(corpus_dir: str | Path) -> list[str]:
    """Scan corpus for classifiable files, skipping boilerplate and already-classified."""
    corpus = Path(corpus_dir)
    eligible = []
    for fp in corpus.rglob("*"):
        if fp.suffix not in (".md", ".txt"):
            continue
        if is_boilerplate(fp):
            continue
        if is_already_classified(fp):
            continue
        eligible.append(str(fp))
    return sorted(eligible)


def run_classification(
    corpus_dir: str | Path,
    checkpoint: CheckpointStore,
    dlq: DeadLetterQueue,
    max_workers: int = 12,
    ollama_url: str = OLLAMA_URL,
    model: str = OLLAMA_MODEL,
    dry_run: bool = False,
) -> PipelineStats:
    """Run classification on all unprocessed files in the corpus.

    Resumable: skips items already at CLASSIFIED or later stages.
    """
    stats = PipelineStats()
    start = time.time()

    # Scan and register
    logger.info("Scanning corpus at %s", corpus_dir)
    file_paths = scan_corpus(corpus_dir)
    stats.total_files = len(file_paths)
    logger.info("Found %d classifiable files", stats.total_files)

    newly_registered = checkpoint.register_items(file_paths)
    logger.info("Registered %d new items in checkpoint", newly_registered)

    # Get items needing classification
    pending = checkpoint.get_items_by_stage(ItemStatus.PENDING)
    logger.info("Processing %d pending items (workers=%d)", len(pending), max_workers)

    if dry_run:
        logger.info("[DRY RUN] Would classify %d files. Exiting.", len(pending))
        stats.classified = 0
        stats.elapsed_seconds = time.time() - start
        return stats

    def _process_one(item: PipelineItem) -> Optional[PipelineItem]:
        fp = Path(item.file_path)
        try:
            checkpoint.update_item(item.file_path, ItemStatus.CLASSIFYING)
            taxonomy, classification = classify_file(fp, ollama_url=ollama_url, model=model)
            item.taxonomy = taxonomy
            item.classification = classification

            if classification.include:
                item.stage = ItemStatus.CLASSIFIED
            else:
                item.stage = ItemStatus.SKIPPED

            item.compute_hash()
            checkpoint.update_item(
                item.file_path,
                item.stage,
                file_hash=item.file_hash,
                taxonomy=taxonomy,
                classification=classification,
            )
            return item
        except Exception as exc:
            error_msg = f"{type(exc).__name__}: {exc}"[:500]
            checkpoint.update_item(item.file_path, ItemStatus.FAILED, error=error_msg)
            dlq.add(item.file_path, "classify", error_msg)
            logger.warning("Failed to classify %s: %s", fp.name, error_msg[:120])
            return None

    processed = 0
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_process_one, item): item for item in pending}
        for future in as_completed(futures):
            result = future.result()
            processed += 1
            if result:
                stats.classified += 1
                value = result.classification.value if result.classification else "low"
                if value == "high":
                    stats.high_value += 1
                elif value == "medium":
                    stats.medium_value += 1
                else:
                    stats.low_value += 1
                if result.stage == ItemStatus.SKIPPED:
                    stats.skipped += 1
            else:
                stats.failed += 1
            if processed % 200 == 0:
                logger.info(
                    "Progress: %d/%d (high=%d medium=%d low=%d failed=%d)",
                    processed, len(pending), stats.high_value, stats.medium_value,
                    stats.low_value, stats.failed,
                )

    stats.elapsed_seconds = time.time() - start
    logger.info(
        "Classification complete: %d classified (%d high, %d medium, %d low), "
        "%d skipped, %d failed in %.1fs (%.1f files/sec)",
        stats.classified, stats.high_value, stats.medium_value, stats.low_value,
        stats.skipped, stats.failed, stats.elapsed_seconds, stats.files_per_second,
    )
    return stats
